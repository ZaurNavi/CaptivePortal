from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import uuid

import pytest

from app.device_fingerprint.artifact_content import make_artifact_content, ArtifactRef
from app.device_fingerprint.classification_persistence import ClassificationPersistenceError
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.runtime_profile_artifacts import (
    make_classification_runtime_profile, make_foundation_runtime_profile,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
    make_runtime_profile_activation_record,
)
from app.device_fingerprint.control_plane_store import PinnedRuntimeProfile
from app.device_fingerprint_integration.compatibility import preflight, verify_executable_identities, REPOSITORY_ROOT
from app.device_fingerprint_integration.executor import ClassificationExecutor, process_memory_guard
from app.device_fingerprint_integration.models import IntegrationError, IdentityResolution, plus
from app.device_fingerprint_integration.worker import IntegrationWorker
from app.device_fingerprint_integration.read_service import FingerprintIntegrationReadService
from tests.device_fingerprint_task04_04d_persistence.test_classification_persistence import (
    setup, production_setup, persist_candidate,
)
from tests.device_fingerprint_task04_04d_request.test_request_assembly import TIME, ref
from .test_repository_identity import repository, job, resolver, SITE, MAC, A, DEVICE, SNAPSHOT


def source_identity(relative, qualified):
    return {"implementation_id": f"python:{relative}:{qualified}",
            "implementation_digest": hashlib.sha256((REPOSITORY_ROOT / relative).read_bytes()).hexdigest()}


def prepared_production(tmp_path):
    """Fully typed local preflight fixture; never today's production IDs."""
    store, control, assembly, retention = production_setup(tmp_path)
    identity = source_identity("app/device_fingerprint/origin_assessment.py",
                               "DeviceFingerprintOriginAssessmentBuilder.build/dhcp/1/FUSION")
    evidence = source_identity("app/device_fingerprint/validation.py", "canonical_json")
    manifest = make_artifact_content("ClassifierArtifactManifest", {
        "adapter_implementation_identities": [{"adapter_kind": "TASK01_EVIDENCE", "source_kind": "dhcp",
            "feature_schema_version": 1, "mode": "FUSION", **identity}],
        "evidence_canonical_json_compatibility_identity":
            f"EvidenceCanonicalJsonV1:{evidence['implementation_id']}:sha256:{evidence['implementation_digest']}",
    })
    profile = make_classification_runtime_profile({**assembly.classification_runtime_profile.semantic_payload,
                                                  "classifier_artifact_manifest": ref(manifest)})
    old_rpm = control.pinned.admission_manifest
    old_foundation_rpm = control.contents[old_rpm.semantic_payload[
        "foundation_runtime_profile_admission_manifest"]["artifact_id"]]
    foundation_manifest = make_artifact_content("FoundationAdmissionManifest", {
        "synthetic": True, "classification_retention_policy": ref(retention)})
    foundation_rpm = make_runtime_profile_admission_manifest({**old_foundation_rpm.semantic_payload,
        "foundation_admission_manifest": ref(foundation_manifest)})
    accepted = make_artifact_content("Task04AcceptanceManifest", {
        "fixture": "local-only", "tested_classification_runtime_profile": ref(profile),
        "classifier_artifact_manifest": ref(manifest), "foundation_admission_manifest": ref(foundation_manifest),
        "pre_acceptance_task04_gate_result_manifests": []})
    rpm = make_runtime_profile_admission_manifest({**old_rpm.semantic_payload,
        "candidate_profile": ref(profile), "task04_acceptance_manifest": ref(accepted),
        "foundation_admission_manifest": ref(foundation_manifest),
        "foundation_runtime_profile_admission_manifest": ref(foundation_rpm)})
    pointer = replace(control.pinned.pointer, runtime_profile_id=profile.artifact_id,
                      runtime_profile_digest=profile.content_sha256)
    activation = make_runtime_profile_activation_record({
        "activation_contract_version": 1, "activation_record_id": pointer.activation_record_id,
        "profile_kind": "classification", "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
        "runtime_profile_admission_manifest_id": rpm.artifact_id,
        "runtime_profile_admission_manifest_digest": rpm.content_sha256,
        "previous_activation_record_id": None, "previous_active_profile_id": None,
        "previous_active_profile_digest": None, "activated_at_utc": TIME,
        "activation_reason_update_class": "INITIAL_CLASSIFICATION", "activation_result": "ACTIVE",
        "activation_generation_id": pointer.activation_generation_id})
    validity = make_runtime_profile_validity_record({
        "runtime_profile_validity_contract_version": 1, "validity_record_id": str(uuid.uuid4()),
        "profile_kind": "classification", "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256, "activation_record_id": pointer.activation_record_id,
        "state": "ACTIVE", "reason_code": "ACTIVATED", "effective_at_utc": TIME,
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT", "previous_validity_record_id": None})
    control.pinned = PinnedRuntimeProfile(pointer, profile, rpm, activation, validity)
    control.contents.update({c.artifact_id: c for c in (manifest, profile, foundation_manifest,
        foundation_rpm, accepted, rpm, activation, validity, retention)})
    store._test_foundation_admission = foundation_rpm
    return store, control, assembly, retention


def executor(store, control, read_service, **kwargs):
    read = DeviceFingerprintClassificationReadService(store.database_path)
    return ClassificationExecutor(control, read_service, store, read, clock=lambda: TIME, **kwargs)


def test_normal_production_path_planned_id_and_authoritative_internal_read(tmp_path):
    store, control, assembly, _retention = prepared_production(tmp_path)
    # Use the existing deterministic Task-01 read fixture, not a second classifier path.
    from tests.device_fingerprint_task04_04d_request.test_request_assembly import prepared
    ctx, _, _, _ = prepared()
    repo = repository(tmp_path)
    original = job(repo)
    leased, _ = repo.claim(plus(A, 150))
    worker = executor(store, control, ctx.read, memory_guard=lambda _: True)
    core, start, end = worker.execute(leased)
    assert core.execution_context == "PRODUCTION"
    assert core.classification_id == original.planned_classification_id
    assert (start, end) == (plus(A, -300), plus(A, 120))
    assert repo.finish(leased, plus(A, 151), state="CLASSIFIED", core=core, start=start, end=end)
    reader = FingerprintIntegrationReadService(repo, worker.read)
    integrated = reader.get_for_auth_run(SITE, original.auth_session_id, 1)
    assert integrated.identity_state == "UNRESOLVED"
    assert integrated.classification_result == worker.read.get_by_id(core.classification_id)
    repo.save_identity(repo.get(original.integration_id),
                       IdentityResolution("DEVICE_RESOLVED", None, SNAPSHOT, DEVICE), plus(A, 152))
    assert reader.get_current_for_device(SITE, DEVICE).classification_id == core.classification_id
    assert reader.get_current_for_device("b" * 24, DEVICE) is None


def test_persist_commit_then_job_update_lost_recovers_without_duplicate(tmp_path):
    store, control, _assembly, _retention = prepared_production(tmp_path)
    from tests.device_fingerprint_task04_04d_request.test_request_assembly import prepared
    ctx, _, _, _ = prepared()
    repo = repository(tmp_path)
    original = job(repo)
    leased, _ = repo.claim(plus(A, 150))
    first = executor(store, control, ctx.read, memory_guard=lambda _: True)
    core, start, end = first.execute(leased)
    # Crash after Task-04 COMMIT; durable job remains LEASED.
    restarted, recovery_only = repo.claim(plus(A, 450))
    class Forbidden:
        def __call__(self, *_args, **_kwargs):
            raise AssertionError("Duplicate classification attempted")
    second = executor(store, control, None, assembly_factory=Forbidden(), preflight_fn=Forbidden())
    recovered, recovered_start, recovered_end = second.execute(restarted, recovery_only=recovery_only)
    assert (recovered.classification_id, recovered_start, recovered_end) == (core.classification_id, start, end)
    assert repo.finish(restarted, plus(A, 451), state="CLASSIFIED", core=recovered, start=start, end=end)
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM classifications").fetchone()[0] == 1


def test_automatic_worker_uses_normal_production_executor_and_persistence(tmp_path):
    store, control, _assembly, _retention = prepared_production(tmp_path)
    from tests.device_fingerprint_task04_04d_request.test_request_assembly import prepared
    ctx, _, _, _ = prepared()
    repo = repository(tmp_path)
    original = job(repo)
    classifier = executor(store, control, ctx.read, memory_guard=lambda _: True)
    worker = IntegrationWorker(repo, classifier, resolver(), clock=lambda: plus(A, 150))
    assert worker.run_once()
    stored = repo.get(original.integration_id)
    assert stored.classification_state == "CLASSIFIED" and stored.identity_state == "UNRESOLVED"
    assert stored.classification_id == original.planned_classification_id
    assert classifier.read.get_by_id(stored.classification_id).core.execution_context == "PRODUCTION"


@pytest.mark.parametrize("changed", [dict(site_id="b" * 24), dict(observed_mac="02:11:22:33:44:55")])
def test_existing_planned_classification_wrong_identity_is_conflict_not_overwritten(tmp_path, changed):
    store, control, _assembly, _retention = prepared_production(tmp_path)
    from tests.device_fingerprint_task04_04d_request.test_request_assembly import prepared
    ctx, _, _, _ = prepared()
    repo = repository(tmp_path)
    original = job(repo)
    classifier = executor(store, control, ctx.read, memory_guard=lambda _: True)
    core, _, _ = classifier.execute(original)
    with pytest.raises(IntegrationError, match="classification_identity_conflict"):
        classifier.execute(replace(original, **changed))
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM classifications").fetchone()[0] == 1
    assert classifier.read.get_by_id(core.classification_id).core == core


@pytest.mark.parametrize("identifier", ["not-uuid", str(uuid.uuid1()), str(uuid.uuid4()).upper(), 42])
def test_explicit_classification_id_rejected_without_change_to_default(tmp_path, identifier):
    store, _, assembly, retention = setup(tmp_path)
    with pytest.raises(ClassificationPersistenceError):
        store.persist(assembly, retention_policy=retention, classification_id=identifier,
            pre_acceptance_foundation_runtime_profile_admission_manifest=store._test_foundation_admission)
    core = persist_candidate(store, assembly, retention)
    assert uuid.UUID(core.classification_id).version == 4
    reader = DeviceFingerprintClassificationReadService(store.database_path)
    assert reader.get_by_id(core.classification_id) == reader.get_current(SITE, MAC)
    assert reader.list_history(SITE, MAC, "2026-09-01T00:00:00.000Z", "2026-10-01T00:00:00.000Z").items[0].core == core


def test_get_by_id_retained_hash_integrity_and_missing(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    core = persist_candidate(store, assembly, retention)
    reader = DeviceFingerprintClassificationReadService(store.database_path)
    assert reader.get_by_id(str(uuid.uuid4())) is None
    with store._connect() as conn:
        conn.execute("UPDATE artifacts SET semantic_payload_json='{}' WHERE artifact_id=?", (core.classification_result_id,))
    with pytest.raises(ClassificationPersistenceError):
        reader.get_by_id(core.classification_id)


@pytest.mark.parametrize("qualified", [
    "DeviceFingerprintOriginAssessmentBuilder.build/mac_registry/FUSION",
    "DeviceFingerprintOriginAssessmentBuilder.build/dhcp/1/FUSION",
    "DeviceFingerprintOriginAssessmentBuilder.build/portal_headers/2/OPTIONAL_IF_ADMITTED",
    "DeviceFingerprintOriginAssessmentBuilder.build/tcp_syn/1/NON_FUSION_HANDLER",
    "DeviceFingerprintOriginAssessmentBuilder.build",
])
def test_source_identity_resolves_symbol_without_changing_admitted_identity(tmp_path, qualified):
    _store, control, _assembly, _retention = prepared_production(tmp_path)
    manifest = control.contents[control.pinned.runtime_profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"]]
    payload = manifest.semantic_payload
    payload["adapter_implementation_identities"][0].update(
        source_identity("app/device_fingerprint/origin_assessment.py", qualified))
    candidate = make_artifact_content("ClassifierArtifactManifest", payload)
    before = candidate.semantic_payload
    identity = candidate.artifact_id
    assert verify_executable_identities(candidate) is None
    assert candidate.semantic_payload == before
    assert candidate.artifact_id == identity
    assert candidate.semantic_payload["adapter_implementation_identities"][0]["implementation_id"] == (
        f"python:app/device_fingerprint/origin_assessment.py:{qualified}")


@pytest.mark.parametrize("qualified", [
    "DeviceFingerprintOriginAssessmentBuilder.no_such_symbol/dhcp/1/FUSION",
    "/dhcp/1/FUSION",
    "DeviceFingerprintOriginAssessmentBuilder..build/dhcp/1/FUSION",
])
def test_invalid_python_symbol_fails_closed(tmp_path, qualified):
    _store, control, _assembly, _retention = prepared_production(tmp_path)
    manifest = control.contents[control.pinned.runtime_profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"]]
    payload = manifest.semantic_payload
    payload["adapter_implementation_identities"][0].update(
        source_identity("app/device_fingerprint/origin_assessment.py", qualified))
    with pytest.raises(IntegrationError, match="runtime_profile_incompatible"):
        verify_executable_identities(make_artifact_content("ClassifierArtifactManifest", payload))


@pytest.mark.parametrize("corrupted", [False, True])
def test_evidence_canonical_json_source_identity_and_digest(tmp_path, corrupted):
    _store, control, _assembly, _retention = prepared_production(tmp_path)
    manifest = control.contents[control.pinned.runtime_profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"]]
    payload = manifest.semantic_payload
    evidence = source_identity("app/device_fingerprint/validation.py", "canonical_json")
    payload["evidence_canonical_json_compatibility_identity"] = (
        f"EvidenceCanonicalJsonV1:{evidence['implementation_id']}:sha256:"
        f"{'0' * 64 if corrupted else evidence['implementation_digest']}")
    candidate = make_artifact_content("ClassifierArtifactManifest", payload)
    if corrupted:
        with pytest.raises(IntegrationError, match="runtime_profile_incompatible"):
            verify_executable_identities(candidate)
    else:
        assert verify_executable_identities(candidate) is None


def test_source_origin_mismatch_fails_closed(tmp_path, monkeypatch):
    _store, control, _assembly, _retention = prepared_production(tmp_path)
    manifest = control.contents[control.pinned.runtime_profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"]]
    monkeypatch.setattr("app.device_fingerprint_integration.compatibility.inspect.getsourcefile",
                        lambda _symbol: str(REPOSITORY_ROOT / "app/device_fingerprint/validation.py"))
    with pytest.raises(IntegrationError, match="runtime_profile_incompatible"):
        verify_executable_identities(manifest)


@pytest.mark.parametrize("bad", ["digest", "escape", "missing"])
def test_manifest_source_mismatch_blocks_execution(tmp_path, bad):
    store, control, _assembly, _ = prepared_production(tmp_path)
    assert preflight(control).pin == control.pinned
    manifest = control.contents[control.pinned.runtime_profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"]]
    payload = manifest.semantic_payload
    if bad == "digest":
        payload["adapter_implementation_identities"][0]["implementation_digest"] = "0" * 64
    elif bad == "escape":
        payload["adapter_implementation_identities"][0]["implementation_id"] = "python:app/../secret.py:symbol"
    else:
        payload["adapter_implementation_identities"] = []
    with pytest.raises(IntegrationError, match="runtime_profile_incompatible"):
        verify_executable_identities(make_artifact_content("ClassifierArtifactManifest", payload))


def test_profile_generation_switch_during_internal_pin_retries_not_torn_result(tmp_path):
    store, control, _assembly, _ = prepared_production(tmp_path)
    from tests.device_fingerprint_task04_04d_request.test_request_assembly import prepared
    ctx, _, _, _ = prepared()
    old = control.pinned
    changed = replace(old, pointer=replace(old.pointer, activation_generation_id=str(uuid.uuid4())))
    calls = []
    def pin(_kind):
        calls.append(_kind)
        return old if len(calls) == 1 else changed
    control.pin_active_profile = pin
    repo = repository(tmp_path)
    leased = job(repo)
    with pytest.raises(IntegrationError, match="profile_changed_during_job"):
        executor(store, control, ctx.read, memory_guard=lambda _: True).execute(leased)
    assert len(calls) == 3
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM classifications").fetchone()[0] == 0


@pytest.mark.parametrize("valid_from,expected", [(plus(A, -60), plus(A, -60)), (plus(A, 120), None)])
def test_foundation_clamp_only_start_or_invalid_window(tmp_path, valid_from, expected):
    store, control, assembly, retention = prepared_production(tmp_path)
    foundation = make_foundation_runtime_profile({**assembly.foundation_runtime_profile.semantic_payload,
                                                  "classification_foundation_valid_from_utc": valid_from})
    prepared = SimpleNamespace(contents=(None, foundation), pin=None, hook=None, retention=retention)
    seen = []
    class Assembly:
        def __init__(self, **kwargs):
            pass
        def assemble_production(self, site, mac, start, end):
            seen.append((start, end))
            raise IntegrationError("binding_unavailable")
    original = job(repository(tmp_path))
    execute = executor(store, control, None, preflight_fn=lambda _: prepared, assembly_factory=Assembly)
    with pytest.raises(IntegrationError, match="integration_window_not_authoritative" if expected is None else "binding_unavailable"):
        execute.execute(original)
    assert seen == ([] if expected is None else [(expected, plus(A, 120))])


def test_memory_measurement_unavailable_fails_closed(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert process_memory_guard(96 * 1024 * 1024) is False


def test_memory_guard_reads_current_resident_pages(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: "100 10 0")
    monkeypatch.setattr("os.sysconf", lambda name: 4096, raising=False)
    assert process_memory_guard(40960) and not process_memory_guard(40959)


def test_identity_hook_is_exact_not_constant_true(tmp_path):
    store, control, _assembly, _ = prepared_production(tmp_path)
    admitted = preflight(control)
    p, f, b, policy, adapter, classifier = admitted.contents
    assert admitted.hook(p, f, b, None, policy, adapter, classifier)
    assert not admitted.hook(p, f, b, None, policy, adapter,
                             make_artifact_content("ClassifierArtifactManifest", {"different": True}))


def test_inactive_profile_and_missing_admission_fail_closed(tmp_path):
    store, control, _assembly, _ = prepared_production(tmp_path)
    old = control.pinned
    inactive = make_runtime_profile_validity_record({**old.validity_record.semantic_payload,
        "state": "INACTIVE", "reason_code": "SUPERSEDED_SAFE"})
    control.pinned = replace(old, validity_record=inactive)
    with pytest.raises(IntegrationError, match="production_profile_not_admitted"):
        preflight(control)
    control.pinned = old
    accepted_id = old.admission_manifest.semantic_payload["task04_acceptance_manifest"]["artifact_id"]
    del control.contents[accepted_id]
    with pytest.raises(IntegrationError, match="runtime_profile_incompatible"):
        preflight(control)


def test_no_active_ids_or_other_domain_mutators_in_integration_source():
    directory = REPOSITORY_ROOT / "app" / "device_fingerprint_integration"
    source = "\n".join(path.read_text(encoding="utf-8") for path in directory.glob("*.py"))
    for forbidden in ("1d3a563e7ce3a8afb", "7873028b2c3a85bf", "get_device_by_mac(",
                      "get_current(site_id", "OmadaProvider", "@app.route", "gc.collect()"):
        assert forbidden not in source
    from app.device_fingerprint_integration.compatibility import ReadOnlyControlPlaneStoreMixin
    from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
    class ReadOnly(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
        pass
    readonly = ReadOnly(directory / "missing-never-created.sqlite")
    with pytest.raises(Exception):
        readonly.pin_active_profile("classification")
    assert not Path(readonly.database_path).exists()
