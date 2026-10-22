"""External T-08 offline/failure-isolation acceptance gate; import is inert."""

from __future__ import annotations

import argparse
import ast
from contextlib import ExitStack, contextmanager
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import sys
import uuid

COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"
TREE = "7e93a4863909c3e807a9d8239924d13e0a0d7f71"
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:75f9d0107d852d58899e869dc9c64c7b311f7423930c60b828a0aa30d2f4c3ff"
T06A_RESULT_ID = "GateResultManifest:v1:sha256:5af29fa71f171d1d03e30b1583b26f60f8e539dd49bad97b3b96067be3883e82"
T06A_PROOF_ID = "GateProofArtifact:v1:sha256:984640314cbfe2d091fc60c54ed43144e223b730579f425c8728b40cc1e4b003"
T06A_RUN = (Path(r"C:\CaptivPortal-Lab\gates\task04\t06a") /
            "official-rebind-20260929-T06A-02" / "28f009b9-2eb7-480c-95c1-fe5e1c00e1b5")
T07_HELPER = Path(__file__).resolve().parents[1] / "t07" / "task04-t07-gate-r3.py"
T07_SHA = "1a133178530b31f4ccea7b025868afac6103447a09daf3cae75a33798ec9db01"
TASK01_SHA = "79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9"
GATE_ID = "T-08"
CONTRACT = "R14-T-08-v1"
PROOF_KIND = "OFFLINE_FAILURE_ISOLATION"
PROCEDURE = "T-08-offline-failure-isolation-no-cloud-v1"
CASES = tuple(f"T08-M{i:02}" for i in range(1, 10))
RETAINED = (
    "t08-execution-evidence.json", "t08-fault-network-matrix.json",
    "t08-network-denial-report.json", "t08-isolation-report.json",
    "t08-static-cloud-path-report.json", "t08-summary.txt",
)


class Blocked(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class MatrixFailure(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise MatrixFailure(code)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, sort_keys=True, ensure_ascii=True,
                                 allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8"))


def ref(item):
    return {"artifact_id": item.artifact_id, "content_sha256": item.content_sha256}


def helper():
    if not T07_HELPER.is_file() or sha(T07_HELPER) != T07_SHA:
        raise Blocked("BLOCKED_HELPER_IDENTITY", str(T07_HELPER))
    import importlib.util
    spec = importlib.util.spec_from_file_location("t08_pinned_t07", T07_HELPER)
    if spec is None or spec.loader is None:
        raise Blocked("BLOCKED_HELPER_IDENTITY")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def output_preflight(repo: Path, foundation: Path, task01: Path, output: Path) -> None:
    runner_tree = Path(__file__).resolve().parent
    if (output.is_relative_to(repo) or output.is_relative_to(T06A_RUN.resolve())
            or output.is_relative_to(runner_tree)
            or output in {foundation.parent, task01.parent}
            or (output.exists() and (not output.is_dir() or any(output.iterdir())))):
        raise Blocked("BLOCKED_OUTPUT_PATH")
    if foundation == task01 or not foundation.is_file() or not task01.is_file():
        raise Blocked("BLOCKED_INPUT_DATABASE")


class NetworkGuard:
    """Deny DNS and socket connections in this process, counting every attempt."""

    def __init__(self):
        self.attempts: list[str] = []
        self.saved = {}
        self.enabled = False

    def _deny(self, destination):
        self.attempts.append(repr(destination)[:256])
        raise OSError("T-08 external network denied")

    def __enter__(self):
        self.enabled = True
        patches = {
            "connect": lambda _sock, address: self._deny(address),
            "connect_ex": lambda _sock, address: self._deny(address),
            "send": lambda _sock, data, *_a, **_kw: self._deny("socket.send"),
            "sendall": lambda _sock, data, *_a, **_kw: self._deny("socket.sendall"),
            "sendto": lambda _sock, data, *args, **_kw: self._deny(args[-1] if args else "socket.sendto"),
            "getaddrinfo": lambda *args, **_kw: self._deny(args[:2]),
            "gethostbyname": lambda host: self._deny(host),
            "gethostbyname_ex": lambda host: self._deny(host),
            "gethostbyaddr": lambda host: self._deny(host),
            "getnameinfo": lambda address, *_args: self._deny(address),
            "create_connection": lambda address, *_a, **_kw: self._deny(address),
        }
        if hasattr(socket.socket, "sendmsg"):
            patches["sendmsg"] = lambda _sock, *_a, **_kw: self._deny("socket.sendmsg")
        try:
            for name, replacement in patches.items():
                target = socket.socket if name in {"connect", "connect_ex", "send", "sendall",
                                                  "sendto", "sendmsg"} else socket
                self.saved[name] = (target, getattr(target, name))
                setattr(target, name, replacement)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        for name, (target, original) in self.saved.items():
            setattr(target, name, original)
        self.saved.clear()

    def report(self):
        return {"network_guard_enabled": self.enabled, "network_attempt_count": len(self.attempts),
                "attempted_destinations": self.attempts}


@contextmanager
def replace_attribute(target, name, replacement):
    original = getattr(target, name)
    setattr(target, name, replacement)
    try:
        yield
    finally:
        setattr(target, name, original)


def static_isolation(repo: Path) -> dict:
    control_paths = [*(repo / "app" / "auth").rglob("*.py"),
                     *(repo / "app" / "capport").rglob("*.py"),
                     *(repo / "app" / "web").rglob("*.py"),
                     *(repo / "app" / "device_fingerprint_portal").rglob("*.py")]
    forbidden = ("app.device_fingerprint.request_assembly",
                 "app.device_fingerprint.classification_persistence",
                 "app.device_fingerprint.snapshot_service",
                 "app.device_fingerprint.fusion",
                 "app.device_fingerprint.classification_read")
    execution_symbols = {"DeviceFingerprintRequestAssembly",
                         "DeviceFingerprintClassificationStore",
                         "DeviceFingerprintSnapshotService",
                         "DeviceFingerprintClassificationReadService",
                         "fuse_classification"}
    call_paths = []
    for path in control_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, (ast.Name, ast.Attribute)):
                if getattr(node, "id", getattr(node, "attr", None)) in execution_symbols:
                    call_paths.append(path.relative_to(repo).as_posix())
                continue
            else:
                continue
            if any(any(name == item or name.startswith(item + ".") for item in forbidden)
                   for name in names):
                call_paths.append(path.relative_to(repo).as_posix())
    runtime_hits, reference_hits = [], []
    for path in (repo / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "fingerbank" not in source.lower():
            continue
        tree = ast.parse(source, filename=str(path))
        active = any("fingerbank" in str(getattr(node, "id", getattr(node, "attr", ""))).lower()
                     for node in ast.walk(tree) if isinstance(node, (ast.Name, ast.Attribute)))
        (runtime_hits if active else reference_hits).append(path.relative_to(repo).as_posix())
    return {"auth_capport_classification_dependency": sorted(set(call_paths)),
            "fingerbank_runtime_identifier_files": sorted(runtime_hits),
            "fingerbank_reference_only_files": sorted(reference_hits)}


def _counts(store) -> dict[str, int]:
    with store._connect() as connection:
        return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("classifications", "artifacts", "artifact_dependencies",
                              "classification_roots")}


def _assemble(api, h, profile, overlay, source, clock, epoch, start, end):
    reader = api.read.DeviceFingerprintReadService(str(source), retention_days=30)
    service = api.assembly.DeviceFingerprintRequestAssembly(
        control_plane_store=overlay, read_service=reader,
        compatibility_hook=lambda *_: True, utc_clock=lambda: clock,
        process_memory_guard=lambda _limit: True)
    result = service.assemble_pre_acceptance_candidate(
        profile, epoch["site_id"], h.helpers()[0].MAC, start, end)
    return service, result


def matrix(run_dir: Path, api, h, foundation_copy: Path, task01_copy: Path,
           profile, admission, retention, classifier, guard: NetworkGuard, results: dict):
    control = api.control.DeviceFingerprintControlPlaneStore(foundation_copy)
    overlay = h.ImmutableOverlay(control, classifier)
    foundation, knowledge, epoch, start, end, observed, clock = h._controlled_time(
        api, profile, overlay, h.helpers()[0])
    h._add_controlled_source_row(task01_copy, api, h.helpers()[0], epoch, observed, end, knowledge)
    with guard:
        service, normal = _assemble(api, h, profile, overlay, task01_copy, clock, epoch, start, end)
        require(normal.classification_runtime_profile == profile and
                normal.classification_result.artifact_type == "ClassificationResult" and
                not overlay.pin_calls and not guard.attempts, "M01_OFFLINE_CLASSIFICATION")
        results["T08-M01"] = {"status": "PASS", "classification_result": ref(normal.classification_result),
                              "network_attempt_count": 0}

        def fault(stage):
            require(stage == "before_commit", "M02_FAULT_STAGE")
            raise sqlite3.OperationalError("controlled classification database failure")

        store = api.persistence.DeviceFingerprintClassificationStore(
            run_dir / "classification-fault.sqlite3", task01_copy,
            control_plane_store=overlay, utc_clock=lambda: clock, fault_hook=fault)
        store.initialize()
        before = _counts(store)
        try:
            store.persist(normal, retention_policy=retention,
                          pre_acceptance_foundation_runtime_profile_admission_manifest=admission)
        except api.persistence.ClassificationPersistenceError as exc:
            require(exc.reason_code == "persistence_unavailable", "M02_WRONG_FAILURE")
        else:
            raise MatrixFailure("M02_PERSISTENCE_SUCCEEDED")
        require(_counts(store) == before, "M02_PARTIAL_PERSISTENCE")
        results["T08-M02"] = {"status": "PASS", "reason_code": "persistence_unavailable",
                              "before": before, "after": _counts(store)}

        bundle_id = profile.semantic_payload["knowledge_bundle"]["artifact_id"]
        original_load = overlay.load_artifact
        attempts = []
        def busy_load(artifact_id, digest=None):
            if artifact_id == bundle_id:
                attempts.append(artifact_id)
                raise sqlite3.OperationalError("database is locked")
            return original_load(artifact_id, digest)
        with replace_attribute(overlay, "load_artifact", busy_load):
            try:
                _assemble(api, h, profile, overlay, task01_copy, clock, epoch, start, end)
            except api.assembly.RequestAssemblyError as exc:
                require(exc.reason_code == "knowledge_bundle_unavailable", "M03_WRONG_FAILURE")
            else:
                raise MatrixFailure("M03_FALLBACK_SUCCEEDED")
        require(len(attempts) == 1, "M03_FALLBACK_LOAD")
        results["T08-M03"] = {"status": "PASS", "reason_code": "knowledge_bundle_unavailable",
                              "bundle_load_attempts": len(attempts)}

        base_snapshot = api.snapshot_service.DeviceFingerprintSnapshotService
        class TimedSnapshot(base_snapshot):
            def __init__(self, *args, **kwargs):
                moments = iter((0.0, 10**9))
                super().__init__(*args, monotonic_clock=lambda: next(moments), **kwargs)
        with replace_attribute(api.assembly, "DeviceFingerprintSnapshotService", TimedSnapshot):
            try:
                _assemble(api, h, profile, overlay, task01_copy, clock, epoch, start, end)
            except api.snapshot_service.SnapshotBuildError as exc:
                require(exc.reason_code == "snapshot_timeout", "M04_WRONG_FAILURE")
            else:
                raise MatrixFailure("M04_TIMEOUT_SUCCEEDED")
        results["T08-M04"] = {"status": "PASS", "reason_code": "snapshot_timeout"}

        # Read-boundary injection: one intact future-schema JSON object exceeds the
        # exact P content policy. Neither the policy nor the source DB is modified.
        policy_ref = foundation.semantic_payload["snapshot_content_policy"]
        policy = overlay.load_artifact(policy_ref["artifact_id"], policy_ref["content_sha256"])
        limit = policy.semantic_payload["max_verified_payload_bytes"]
        oversized = api.validation.canonical_json({"controlled_padding": "x" * (limit + 1)})
        reader = api.read.DeviceFingerprintReadService(str(task01_copy), retention_days=30)
        original_open = reader.open_snapshot_read
        class OversizedSession:
            def __init__(self, session): self.session = session
            def __getattr__(self, name): return getattr(self.session, name)
            def list_evidence(self, *args, **kwargs):
                page = self.session.list_evidence(*args, **kwargs)
                for row in page["items"]:
                    row.update(payload_json=oversized,
                               payload_sha256=api.validation.canonical_sha256(oversized),
                               feature_schema_version=99)
                return page
        @contextmanager
        def oversized_open():
            with original_open() as session:
                yield OversizedSession(session)
        service5 = api.assembly.DeviceFingerprintRequestAssembly(
            control_plane_store=overlay, read_service=reader,
            compatibility_hook=lambda *_: True, utc_clock=lambda: clock,
            process_memory_guard=lambda _limit: True)
        with replace_attribute(reader, "open_snapshot_read", oversized_open):
            try:
                service5.assemble_pre_acceptance_candidate(
                    profile, epoch["site_id"], h.helpers()[0].MAC, start, end)
            except api.snapshot_service.SnapshotBuildError as exc:
                require(exc.reason_code == "resource_limited", "M05_WRONG_FAILURE")
            else:
                raise MatrixFailure("M05_OVERSIZE_SUCCEEDED")
        results["T08-M05"] = {"status": "PASS", "reason_code": "resource_limited",
                              "exact_policy": ref(policy), "limit_bytes": limit,
                              "injected_verified_bytes": len(oversized.encode())}

        class ControlledClassifierFault(RuntimeError): pass
        def classifier_fault(*_args, **_kwargs): raise ControlledClassifierFault("controlled classifier fault")
        with replace_attribute(api.assembly, "fuse_classification", classifier_fault):
            try:
                _assemble(api, h, profile, overlay, task01_copy, clock, epoch, start, end)
            except ControlledClassifierFault:
                pass
            else:
                raise MatrixFailure("M06_PARTIAL_RESULT_ESCAPED")
        results["T08-M06"] = {"status": "PASS", "exception_boundary":
                              "request_assembly.fuse_classification", "persisted": False}

        k1_id = knowledge.k1_provenance.artifact_id
        freshness = api.assembly.evaluate_external_knowledge_freshness
        origin_module = api.origin_assessment
        origin_freshness = origin_module.evaluate_external_knowledge_freshness
        def expire_k1(provenance, freshness_policy, **kwargs):
            result = freshness(provenance, freshness_policy, **kwargs)
            if provenance.artifact_id == k1_id:
                return {**result, "freshness_state": "expired", "claim_eligible": False,
                        "claim_strength_cap": "NONE", "required_explanation_code":
                        "knowledge_source_expired", "failure_code": None}
            return result
        with replace_attribute(api.assembly, "evaluate_external_knowledge_freshness", expire_k1), \
             replace_attribute(origin_module, "evaluate_external_knowledge_freshness", expire_k1):
            _, expired = _assemble(api, h, profile, overlay, task01_copy, clock, epoch, start, end)
        normal_dhcp = next(row for row in normal.origin_assessments
                           if row.semantic_payload["origin_group"] == "dhcp")
        dhcp = next(row for row in expired.origin_assessments
                    if row.semantic_payload["origin_group"] == "dhcp")
        normal_other = {row.semantic_payload["origin_group"]: row for row in normal.origin_assessments
                        if row.semantic_payload["origin_group"] != "dhcp"}
        expired_other = {row.semantic_payload["origin_group"]: row for row in expired.origin_assessments
                         if row.semantic_payload["origin_group"] != "dhcp"}
        require(any(row["candidate_set"] for row in normal_dhcp.semantic_payload["dimension_assessments"])
                and normal_other == expired_other
                and all(not row["candidate_set"] for row in dhcp.semantic_payload["dimension_assessments"])
                and "knowledge_source_expired" in dhcp.semantic_payload["explanation_codes"]
                and expired.classification_result.artifact_type == "ClassificationResult" and
                len(expired.origin_assessments) == len(normal.origin_assessments),
                "M07_EXPIRED_SOURCE_NOT_ISOLATED")
        results["T08-M07"] = {"status": "PASS", "controlled_slot": "k1",
                              "freshness_state": "expired", "claim_eligible": False,
                              "other_origin_count": len(expired.origin_assessments) - 1}

        # A component-level disabled-TCP input is intentionally separate from P.
        fixture = __import__("tests.device_fingerprint_task04_t03.test_origin_assessment",
                             fromlist=["_inputs", "_network_row"])
        schema_fixture = __import__("tests.device_fingerprint.test_network_schemas",
                                    fromlist=["tcp_v2"])
        tcp_payload = schema_fixture.tcp_v2(ip_df=False, ip_id_zero=False,
                                            tcp_sequence_zero=False,
                                            tcp_header_length_bytes=20, tcp_option_records=[])
        row = fixture._network_row("tcp", version=2)
        row["payload_json"] = api.validation.canonical_json(tcp_payload)
        row["payload_sha256"] = api.validation.canonical_sha256(row["payload_json"])
        row["extractor_version"] = "2.0.0"
        disabled_inputs = fixture._inputs(evidence_rows=[row], origin="tcp", tcp_disabled=True)
        invoked = []
        def forbidden_match(*_args, **_kwargs):
            invoked.append(True)
            raise MatrixFailure("M08_MATCHER_INVOKED")
        with ExitStack() as stack:
            for name in ("adapt_tcp_syn_v2", "parse_request_signature", "match_request"):
                stack.enter_context(replace_attribute(origin_module, name, forbidden_match))
            all_disabled = origin_module.DeviceFingerprintOriginAssessmentBuilder(
                disabled_inputs).build_all()
        disabled = next(item for item in all_disabled
                        if item.semantic_payload["origin_group"] == "tcp")
        payload = disabled.semantic_payload
        require(not invoked and len(all_disabled) == 6 and
                all(item.artifact_type == "OriginAssessment" for item in all_disabled) and
                len(payload["evidence_refs"]) == 1 and
                all(item["internal_state"] == "no_claim" and not item["candidate_set"]
                    for item in payload["dimension_assessments"]) and
                "origin_runtime_disabled" in payload["explanation_codes"],
                "M08_DISABLED_TCP_CLAIM")
        results["T08-M08"] = {"status": "PASS", "controlled_component": True,
                              "tcp_evidence_count": len(payload["evidence_refs"]),
                              "matcher_invocation_count": len(invoked),
                              "safe_non_tcp_origin_count": len(all_disabled) - 1}

    require(not guard.attempts, "M01_NETWORK_ATTEMPT")
    require(all(results[case]["status"] == "PASS" for case in CASES[:-1]),
            "T08_MATRIX_INCOMPLETE")


def formal(api, h, run_dir: Path, profile, t06a_result, runner_sha: str, passed: bool):
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": COMMIT, "repository_tree_sha": TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": h.helpers()[0]._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    evidence = [{"evidence_label": name.rsplit(".", 1)[0], "file_sha256": sha(run_dir / name),
                 "media_type": "text/plain" if name.endswith((".log", ".txt")) else "application/json",
                 "path_or_reference": name} for name in RETAINED]
    inputs = sorted((ref(profile), ref(t06a_result)), key=lambda item: item["artifact_id"])
    proof = None
    if passed:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": PROOF_KIND, "source_gate_id": GATE_ID,
            "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
            "input_artifact_refs": inputs, "procedure_or_test_suite_id": PROCEDURE,
            "proof_execution_identity": identity,
            "canonical_result_summary": "exact_P=PASS;matrix=9/9 PASS;network_attempts=0;isolation=PASS",
            "retained_evidence_refs": evidence})
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": GATE_ID, "gate_contract_version": CONTRACT,
        "status": "PASS" if passed else "FAIL",
        "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
        "input_artifact_refs": inputs,
        "output_artifact_refs": [ref(proof)] if proof is not None else [],
        "retained_evidence_refs": evidence, "proof_execution_identity": identity,
        "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None,
                                "foundation_admission_evaluation_at_utc": None,
                                "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    if proof is not None:
        h.helpers()[0]._write_and_roundtrip(run_dir / "t08-gate-proof-artifact.json", proof,
            api.gate_proof.make_gate_proof_artifact, api.artifact.canonical_artifact_json)
    h.helpers()[0]._write_and_roundtrip(run_dir / "t08-gate-result-manifest.json", result,
        api.gate_result.make_gate_result_manifest, api.artifact.canonical_artifact_json)


def blocked(run_dir: Path | None, code: str) -> int:
    if run_dir is not None:
        for name in ("t08-gate-proof-artifact.json", "t08-gate-result-manifest.json"):
            (run_dir / name).unlink(missing_ok=True)
        (run_dir / "t08-summary.txt").write_text(f"GATE_EXECUTION_STATUS={code}\n", encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={code}")
    return 2


def run_gate(repo: Path, foundation_db: Path, task01_db: Path, output_dir: Path) -> int:
    """Official execution; caller must supply an empty external output directory."""
    run_dir = None
    try:
        repo, foundation_db, task01_db = (path.resolve(strict=True) for path in
                                           (repo, foundation_db, task01_db))
        output_dir = output_dir.resolve()
        output_preflight(repo, foundation_db, task01_db, output_dir)
        h = helper()
        t01, t06a = h.helpers()
        t01.verify_repository(repo)
        before_repo = t01.repository_filesystem_fingerprint(repo)
        before_foundation, before_task01 = sha(foundation_db), sha(task01_db)
        if sha(task01_db) != TASK01_SHA:
            raise Blocked("BLOCKED_TASK01_FIXTURE_IDENTITY")
        sys.path.insert(0, str(repo))
        api = h.api_for(repo, t06a)
        api.snapshot_service = h.candidate(repo, "app.device_fingerprint.snapshot_service")
        api.origin_assessment = h.candidate(repo, "app.device_fingerprint.origin_assessment")
        profile, t06a_proof, t06a_result = h.verify_t06a(T06A_RUN, api)
        with t01.open_foundation_read_only(foundation_db) as connection:
            lineage = t01.verify_foundation(connection, api)
            retention = h.resolve_retention(connection, api, t01, lineage)
        if profile.semantic_payload["foundation_runtime_profile"] != ref(lineage.profile):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        classifier = h.canonical_content(h.T06_MANIFEST_PATH, api,
            lambda payload: api.artifact.make_artifact_content("ClassifierArtifactManifest", payload),
            profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / str(uuid.uuid4())
        run_dir.mkdir(exist_ok=False)
        runner_sha = sha(Path(__file__).resolve())
        h.copy_sqlite_readonly(foundation_db, run_dir / "foundation-disposable.sqlite3")
        h.copy_sqlite_readonly(task01_db, run_dir / "task01-disposable.sqlite3")
        foundation_copy = run_dir / "foundation-disposable.sqlite3"
        task01_copy = run_dir / "task01-disposable.sqlite3"
        matrix_result = {case: {"status": "NOT_RUN"} for case in CASES}
        guard = NetworkGuard()
        failure = None
        try:
            matrix(run_dir, api, h, foundation_copy, task01_copy,
                   profile, lineage.admission, retention, classifier, guard, matrix_result)
        except MatrixFailure as exc:
            failure = exc.code
        except Exception as exc:
            failure = f"T08_MATRIX_EXCEPTION_{type(exc).__name__}"
        network = guard.report()
        static = static_isolation(repo)
        if static["auth_capport_classification_dependency"] or static["fingerbank_runtime_identifier_files"]:
            failure = failure or "T08_STATIC_ISOLATION_FAILURE"
        after_foundation, after_task01 = sha(foundation_db), sha(task01_db)
        t01._require_repository_unchanged(repo, before_repo)
        if before_foundation != after_foundation or before_task01 != after_task01:
            raise Blocked("BLOCKED_INPUT_DATABASE_MUTATED")
        if sha(Path(__file__).resolve()) != runner_sha or sha(T07_HELPER) != T07_SHA:
            raise Blocked("BLOCKED_RUNNER_CHANGED")
        matrix_result["T08-M09"] = {"status": "PASS" if not static[
            "auth_capport_classification_dependency"] and not static[
            "fingerbank_runtime_identifier_files"] and not network["network_attempt_count"] else "FAIL",
            "foundation_byte_identity": before_foundation == after_foundation,
            "task01_byte_identity": before_task01 == after_task01,
            "repository_unchanged": True}
        passed = (failure is None and
                  all(row["status"] == "PASS" for row in matrix_result.values()) and
                  network["network_attempt_count"] == 0)
        if not passed and failure is None:
            failure = "T08_MATRIX_INCOMPLETE"
        write_json(run_dir / "t08-fault-network-matrix.json", matrix_result)
        write_json(run_dir / "t08-network-denial-report.json", network)
        write_json(run_dir / "t08-static-cloud-path-report.json", static)
        write_json(run_dir / "t08-isolation-report.json", {
            "foundation_sha_before": before_foundation, "foundation_sha_after": after_foundation,
            "task01_sha_before": before_task01, "task01_sha_after": after_task01,
            "repository_unchanged": True, "auth_capport_dependency_absent": not static[
                "auth_capport_classification_dependency"]})
        write_json(run_dir / "t08-execution-evidence.json", {
            "candidate_commit": COMMIT, "candidate_tree": TREE, "exact_profile": ref(profile),
            "t06a_gate_result": ref(t06a_result), "t06a_gate_proof": ref(t06a_proof),
            "runner_sha256": runner_sha,
            "helper_hashes": {"t07": T07_SHA, "t01": h.T01_SHA, "t06a": h.T06A_SHA},
            "matrix": matrix_result, "network_attempt_count": network["network_attempt_count"],
            "foundation_sha_before": before_foundation, "foundation_sha_after": after_foundation,
            "task01_sha_before": before_task01, "task01_sha_after": after_task01,
            "repository_immutability": "PASS", "failure_code": failure, "all_pass": passed})
        (run_dir / "t08-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}\n"
            f"FAILURE_CODE={failure or 'NONE'}\n", encoding="utf-8")
        formal(api, h, run_dir, profile, t06a_result, runner_sha, passed)
        print(f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    except Blocked as exc:
        return blocked(run_dir, exc.code)
    except Exception as exc:
        return blocked(run_dir, f"BLOCKED_EXECUTION_ERROR_{type(exc).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="External T-08 offline/failure-isolation gate")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--task01-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.task01_db, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
