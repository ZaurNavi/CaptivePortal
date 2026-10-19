"""Synthetic source/operator provenance; no installed path is accessed."""
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
from pathlib import PurePosixPath

import pytest

from app.db_audit_coordinator.operational_contracts import EvidenceError, FileIdentity
from app.db_audit_coordinator.operator_profile_binding import (BoundPath, InstalledRelease,
    ProfileBinding, validate_binding)
from app.db_audit_coordinator.operational_hooks import OfflineOperationalHooks, PostLockContext
from app.db_audit_coordinator.receipt_ports import (ReceiptChannel, ReleaseReceipts,
    ResourceReceipts, RootLayout)
from .test_operational_contracts import NOW, fixture_case, stamp, uid
from .test_release_fence import release_case


def bound_path(value, identity):
    directories = {'/': FileIdentity(1, 100, 0, 0o755, 'directory', 2),
        '/release': FileIdentity(1, 11, 0, 0o755, 'directory', 2),
        '/source': FileIdentity(8, 90, 0, 0o700, 'directory', 2),
        '/queue': FileIdentity(9, 40, 0, 0o700, 'directory', 2)}
    ancestors = tuple((str(parent), directories[str(parent)]) for parent in PurePosixPath(value).parents)
    return BoundPath(value, identity, ancestors)


class SyntheticPorts:
    channel = ReceiptChannel.OFFLINE_FIXTURE

    def __init__(self, resources=None, released=None):
        self.resource_value, self.release_value = resources, released
        self.calls = []

    def resources(self):
        self.calls.append('resources')
        return self.resource_value

    def release(self):
        self.calls.append('release')
        return self.release_value


def b1_case(*, released=False):
    if released:
        profile, reap, before, after, owners = release_case()
        geometry = fixture_case()[3]
    else:
        profile, before, after, geometry = fixture_case()
    root = bound_path('/release', FileIdentity(1, 11, 0, 0o755, 'directory', 2))
    release = InstalledRelease(root, root, (('audit.py', 'c'*64), ('writer.py', 'b'*64)),
        'fixture-audit.service', 'd'*64, (('10-local.conf', 'f'*64),))
    source = replace(profile.source, locator_sha256=hashlib.sha256(b'/source/evidence.sqlite3').hexdigest(),
        service_identity_sha256=release.service_digest())
    profile = replace(profile, source=source)
    geometry = replace(geometry, source=source)
    configured = ProfileBinding('coordinator.profile-binding.offline.v1', profile.domain, profile.store_id,
        profile.profile_id, profile.task, 1234, profile.owner_uid, release,
        bound_path('/source', FileIdentity(8, 90, 0, 0o700, 'directory', 2)),
        bound_path('/source/evidence.sqlite3', FileIdentity(source.device, source.inode, 0, 0o600, 'file', 1)),
        source, bound_path('/queue', profile.filesystem.root_identity),
        bound_path('/queue/queue-owner.lock', FileIdentity(9, 50, 0, 0o600, 'file', 1)),
        bound_path('/queue/heavy.lock', FileIdentity(9, 51, 0, 0o600, 'file', 1)),
        profile.job_cgroup, profile.job_cgroup_identity, stamp(101, kind='configured'))
    observed = replace(configured, stamp=stamp(102, offset=1_000_000))
    resources = ResourceReceipts(observed, before, after, geometry, RootLayout.SYNTHETIC_EXPORTED)
    releases = ReleaseReceipts(observed, reap, before, after, owners, RootLayout.SYNTHETIC_EXPORTED) if released else None
    ports = SyntheticPorts(resources, releases)
    hooks = OfflineOperationalHooks(profile, configured, ports)
    task = profile.task
    context = PostLockContext(task.job_id, task.attempt_id, task.epoch, task.run_id,
        task.worker_pid, profile.owner_uid, configured.global_lock.path,
        configured.global_lock.identity.device, configured.global_lock.identity.inode)
    return hooks, context


def test_exact_profile_is_immutable_closed_and_only_synthetic():
    hooks, context = b1_case()
    observed = hooks.ports.resource_value.binding
    validate_binding(hooks.configured, observed, hooks.profile, now_ns=NOW)
    assert ProfileBinding.parse(asdict(hooks.configured)) == hooks.configured
    with pytest.raises(FrozenInstanceError):
        hooks.configured.operator_uid = 0
    decision = hooks.preflight(context, now_ns=NOW)
    assert decision.status == 'not_admitted' and decision.admits_live is False
    assert decision.simulation.status == 'CANDIDATE_SAFE_SIMULATED'
    with pytest.raises(TypeError):
        bool(decision)


@pytest.mark.parametrize('field', list(asdict(b1_case()[0].configured)))
def test_missing_binding_fields_rejected(field):
    value = asdict(b1_case()[0].configured); del value[field]
    with pytest.raises(EvidenceError):
        ProfileBinding.parse(value)


@pytest.mark.parametrize('key', ['trusted', 'enabled', 'force', 'status', 'socket', 'admission_token'])
def test_extra_fields_cannot_be_authority(key):
    value = asdict(b1_case()[0].configured); value[key] = True
    with pytest.raises(EvidenceError):
        ProfileBinding.parse(value)


@pytest.mark.parametrize('channel', ['operator_review', 'environment', 'public_socket', 'status_file', 'UNKNOWN'])
@pytest.mark.parametrize('where', ['configured', 'observed', 'source'])
def test_public_configured_and_unknown_provenance_not_promoted(channel, where):
    hooks, _ = b1_case(); configured = hooks.configured; observed = hooks.ports.resource_value.binding
    if where == 'configured':
        configured = replace(configured, stamp=replace(configured.stamp, channel=channel))
    elif where == 'observed':
        observed = replace(observed, stamp=replace(observed.stamp, channel=channel))
    else:
        observed = replace(observed, source=replace(observed.source, stamp=replace(observed.source.stamp, channel=channel)))
    with pytest.raises(EvidenceError):
        validate_binding(configured, observed, hooks.profile, now_ns=NOW)


@pytest.mark.parametrize('field', ['profile_id', 'operator_uid', 'owner_uid', 'task', 'release',
    'source', 'source_path', 'queue_root', 'owner_lock', 'global_lock', 'job_cgroup', 'job_cgroup_identity'])
def test_release_source_site_queue_lock_epoch_and_operator_mismatch_fail(field):
    hooks, _ = b1_case(); observed = hooks.ports.resource_value.binding
    if field == 'profile_id': value = uid(999)
    elif field in {'operator_uid', 'owner_uid'}: value = 999
    elif field == 'task': value = replace(observed.task, epoch=uid(999))
    elif field == 'release': value = replace(observed.release, effective_unit_sha256='e'*64)
    elif field == 'source': value = replace(observed.source, generation=uid(999))
    elif field == 'job_cgroup': value = '/other/job'
    elif field == 'job_cgroup_identity': value = replace(observed.job_cgroup_identity, inode=999)
    else:
        old = getattr(observed, field); value = replace(old, identity=replace(old.identity, inode=999))
    with pytest.raises(EvidenceError):
        validate_binding(hooks.configured, replace(observed, **{field: value}), hooks.profile, now_ns=NOW)


@pytest.mark.parametrize('field', ['source_root', 'source_path', 'queue_root', 'owner_lock', 'global_lock'])
@pytest.mark.parametrize('bad', ['symlink', 'writable', 'links', 'ancestor'])
def test_path_symlink_hardlink_permissions_and_ancestor_are_not_trusted(field, bad):
    hooks, _ = b1_case(); value = hooks.ports.resource_value.binding; target = getattr(value, field)
    if bad == 'links' and target.identity.kind == 'directory':
        target = replace(target, identity=replace(target.identity, kind='symlink'))
    elif bad == 'ancestor':
        name, ident = target.ancestors[0]
        target = replace(target, ancestors=((name, replace(ident, kind='symlink')),)+target.ancestors[1:])
    else:
        change = {'kind': 'symlink'} if bad == 'symlink' else {'mode': 0o777} if bad == 'writable' else {'links': 2}
        target = replace(target, identity=replace(target.identity, **change))
    with pytest.raises(EvidenceError):
        validate_binding(hooks.configured, replace(value, **{field: target}), hooks.profile, now_ns=NOW)


@pytest.mark.parametrize('value', ['relative', '/source/../escape', '/source//escape', '/source/./escape'])
def test_path_escape_rejected_without_fs_access(value):
    hooks, _ = b1_case()
    with pytest.raises(EvidenceError):
        replace(hooks.configured.source_path, path=value)


def test_self_inconsistent_directory_inodes_are_rejected_even_in_both_supplied_profiles():
    hooks, _ = b1_case(); configured = hooks.configured
    lock = configured.global_lock; name, identity = lock.ancestors[0]
    lock = replace(lock, ancestors=((name, replace(identity, inode=999)),) + lock.ancestors[1:])
    configured = replace(configured, global_lock=lock)
    observed = replace(configured, stamp=stamp(888, offset=1_000_000))
    with pytest.raises(EvidenceError, match='filesystem_trust'):
        validate_binding(configured, observed, hooks.profile, now_ns=NOW)


@pytest.mark.parametrize('field', ['source_blobs', 'dropins'])
@pytest.mark.parametrize('bad', ['duplicate', 'escape', 'oversized', 'wrong_digest'])
def test_release_blob_set_is_bounded_closed_and_exact(field, bad):
    release = b1_case()[0].configured.release
    values = getattr(release, field)
    changed = (values[0], values[0]) if bad == 'duplicate' else (('../escape', 'a'*64),) if bad == 'escape' else (
        tuple((f'{i:03}.py', 'a'*64) for i in range(40)) if bad == 'oversized' else (('a.py', 'bad'),))
    with pytest.raises(EvidenceError):
        replace(release, **{field: changed})


@pytest.mark.parametrize('kind,offset', [('observed', 1_000_000), ('UNKNOWN', 1_000_000),
    ('configured', -2_000_000_000), ('configured', 20_000_000)])
def test_configured_observed_stale_and_future_are_distinct(kind, offset):
    hooks, _ = b1_case()
    with pytest.raises(EvidenceError):
        validate_binding(replace(hooks.configured, stamp=stamp(900, kind=kind, offset=offset)),
            hooks.ports.resource_value.binding, hooks.profile, now_ns=NOW)
