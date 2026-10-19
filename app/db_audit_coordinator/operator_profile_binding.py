"""Bounded OFFLINE installed-profile comparisons, never operator authorization.

All identities are supplied synthetic evidence. No stat/readlink/environment or
source access occurs here. A future live collector needs separate qualification;
neither a parsed profile nor equality of two supplied values is that proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import PurePosixPath
import re

from .operational_contracts import (DOMAIN, STORE, FileIdentity, OperatorProfile,
    SourceIdentity, Stamp, TaskIdentity, closed, digest, identifier, integer, path,
    require, stamp_check)


def _relative(value):
    require(type(value) is str and len(value) <= 240 and not value.startswith('/'), 'config_trust')
    path('/' + value)
    return value


def _blobs(value, maximum, *, empty=False):
    require(type(value) is tuple and (0 if empty else 1) <= len(value) <= maximum, 'config_trust')
    names = []
    for item in value:
        require(type(item) is tuple and len(item) == 2, 'config_trust')
        names.append(_relative(item[0])); digest(item[1])
    require(names == sorted(set(names)), 'config_trust')


@dataclass(frozen=True, repr=False)
class BoundPath:
    path: str
    identity: FileIdentity
    ancestors: tuple[tuple[str, FileIdentity], ...]

    def __post_init__(self):
        path(self.path)
        require(self.path != '/' and type(self.identity) is FileIdentity, 'filesystem_trust')
        expected = tuple(str(parent) for parent in PurePosixPath(self.path).parents)
        require(type(self.ancestors) is tuple and len(self.ancestors) == len(expected), 'filesystem_trust')
        for item, name in zip(self.ancestors, expected):
            require(type(item) is tuple and len(item) == 2 and item[0] == name
                and type(item[1]) is FileIdentity, 'filesystem_trust')

    def check(self, kind, uid):
        self.identity.check(kind, uid)
        for _, identity in self.ancestors:
            require(identity.uid in {0, uid}, 'filesystem_trust')
            identity.check('directory', identity.uid)

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls))
        require(type(data['ancestors']) in {list, tuple} and len(data['ancestors']) <= 16, 'filesystem_trust')
        pairs = []
        for item in data['ancestors']:
            require(type(item) in {list, tuple} and len(item) == 2, 'filesystem_trust')
            pairs.append((item[0], FileIdentity.parse(item[1])))
        data['ancestors'] = tuple(pairs)
        data['identity'] = FileIdentity.parse(data['identity'])
        return cls(**data)


@dataclass(frozen=True, repr=False)
class InstalledRelease:
    root: BoundPath
    working_directory: BoundPath
    source_blobs: tuple[tuple[str, str], ...]
    unit_name: str
    effective_unit_sha256: str
    dropins: tuple[tuple[str, str], ...]

    def __post_init__(self):
        require(type(self.root) is BoundPath and type(self.working_directory) is BoundPath, 'config_trust')
        _blobs(self.source_blobs, 32); _blobs(self.dropins, 16, empty=True)
        require(type(self.unit_name) is str and re.fullmatch(r'[A-Za-z0-9_.@-]{1,100}\.service', self.unit_name)
            is not None, 'config_trust')
        digest(self.effective_unit_sha256)
        require(self.working_directory.path == self.root.path or
            self.working_directory.path.startswith(self.root.path + '/'), 'filesystem_trust')

    def service_digest(self):
        effective = (self.working_directory.path, self.unit_name, self.effective_unit_sha256, self.dropins)
        return hashlib.sha256(json.dumps(effective, separators=(',', ':')).encode('ascii')).hexdigest()

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls))
        for name in ('root', 'working_directory'):
            data[name] = BoundPath.parse(data[name])
        for name, limit in (('source_blobs', 32), ('dropins', 16)):
            require(type(data[name]) in {list, tuple} and len(data[name]) <= limit, 'config_trust')
            require(all(type(item) in {list, tuple} and len(item) == 2 for item in data[name]), 'config_trust')
            data[name] = tuple(tuple(item) for item in data[name])
        return cls(**data)


@dataclass(frozen=True, repr=False)
class ProfileBinding:
    schema: str
    domain: str
    store_id: str
    profile_id: str
    task: TaskIdentity
    operator_uid: int
    owner_uid: int
    release: InstalledRelease
    source_root: BoundPath
    source_path: BoundPath
    source: SourceIdentity
    queue_root: BoundPath
    owner_lock: BoundPath
    global_lock: BoundPath
    job_cgroup: str
    job_cgroup_identity: FileIdentity
    stamp: Stamp

    def __post_init__(self):
        require(self.schema == 'coordinator.profile-binding.offline.v1' and self.domain == DOMAIN
            and self.store_id == STORE, 'config_trust')
        identifier(self.profile_id)
        require(type(self.task) is TaskIdentity and type(self.release) is InstalledRelease
            and type(self.source) is SourceIdentity and type(self.stamp) is Stamp, 'config_trust')
        integer(self.operator_uid, 0, (1 << 32) - 1); integer(self.owner_uid, 0, (1 << 32) - 1)
        for name in ('source_root', 'source_path', 'queue_root', 'owner_lock', 'global_lock'):
            require(type(getattr(self, name)) is BoundPath, 'filesystem_trust')
        require(self.source_path.path.startswith(self.source_root.path + '/'), 'filesystem_trust')
        require(self.owner_lock.path == self.queue_root.path + '/queue-owner.lock'
            and self.global_lock.path == self.queue_root.path + '/heavy.lock', 'filesystem_trust')
        require((self.owner_lock.identity.device, self.owner_lock.identity.inode) !=
            (self.global_lock.identity.device, self.global_lock.identity.inode), 'filesystem_trust')
        path(self.job_cgroup)
        require(type(self.job_cgroup_identity) is FileIdentity, 'filesystem_trust')

    @classmethod
    def parse(cls, value):
        data = dict(closed(value, cls))
        for name, factory in (('task', TaskIdentity), ('release', InstalledRelease), ('source', SourceIdentity),
                ('source_root', BoundPath), ('source_path', BoundPath), ('queue_root', BoundPath),
                ('owner_lock', BoundPath), ('global_lock', BoundPath),
                ('job_cgroup_identity', FileIdentity), ('stamp', Stamp)):
            data[name] = factory.parse(data[name])
        return cls(**data)

    def check(self, profile, now_ns, *, kind):
        require(type(profile) is OperatorProfile, 'config_trust')
        profile.check(now_ns)
        stamp_check(self.stamp, now_ns, profile.policy.max_age_ns, kind)
        stamp_check(self.source.stamp, now_ns, profile.policy.max_age_ns)
        require(self.profile_id == profile.profile_id and self.task == profile.task
            and self.owner_uid == profile.owner_uid and self.job_cgroup == profile.job_cgroup
            and self.job_cgroup_identity == profile.job_cgroup_identity, 'config_trust')
        for target in (self.release.root, self.release.working_directory, self.source_root, self.queue_root):
            target.check('directory', self.owner_uid)
        for target in (self.source_path, self.owner_lock, self.global_lock):
            target.check('file', self.owner_uid)
        identities = {}
        for target in (self.release.root, self.release.working_directory, self.source_root,
                self.source_path, self.queue_root, self.owner_lock, self.global_lock):
            for name, identity in ((target.path, target.identity), *target.ancestors):
                require(name not in identities or identities[name] == identity, 'filesystem_trust')
                identities[name] = identity
        require(self.queue_root.identity == profile.filesystem.root_identity, 'filesystem_trust')
        require((self.source_path.identity.device, self.source_path.identity.inode) ==
            (self.source.device, self.source.inode), 'source_identity')
        require(hashlib.sha256(self.source_path.path.encode('ascii')).hexdigest() ==
            self.source.locator_sha256, 'source_identity')
        require(_source_key(self.source) == _source_key(profile.source), 'source_identity')
        hashes = {value for _, value in self.release.source_blobs}
        require({self.source.writer_artifact_sha256, self.source.auditor_artifact_sha256} <= hashes
            and self.source.service_identity_sha256 == self.release.service_digest(), 'source_identity')


def _source_key(source):
    data = asdict(source); del data['stamp']
    return data


def validate_binding(configured, observed, profile, *, now_ns):
    """Exact OFFLINE comparison; returning normally is not a live capability."""
    require(type(configured) is ProfileBinding and type(observed) is ProfileBinding, 'config_trust')
    configured.check(profile, now_ns, kind='configured')
    observed.check(profile, now_ns, kind='observed')
    require(configured.stamp.receipt_id != observed.stamp.receipt_id and
        configured.stamp.captured_ns <= observed.stamp.captured_ns, 'config_trust')
    left, right = asdict(configured), asdict(observed)
    for value in (left, right):
        del value['stamp']; del value['source']['stamp']
    require(left == right, 'config_trust')
