"""External, read-only Foundation-bound R14 T-01 Central Lab gate runner.

The CLI is reserved for Owner/TechLead execution. Importing this module does not
open a repository, read a database, or execute a gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


EXPECTED_COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"
EXPECTED_TREE = "7e93a4863909c3e807a9d8239924d13e0a0d7f71"
EXPECTED_DIGESTS = {
    "FoundationAdmissionManifest": "44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff",
    "FoundationRuntimeProfile": "9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5",
    "RuntimeProfileAdmissionManifest": "95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6",
    "GateResultManifest": "61cc6d757e369af897131c08a53e3176fdbe38773c7a288dfd1ecb6a0e1e17c5",
    "EvidenceSchemaRegistryContract": "090d763e99247ca3b10be34976069e4e7e708be0899e21a15c6e103a015f7814",
}
PROCEDURE = "T-01-snapshot-materialization-execution-v1"
GATE_CONTRACT = "R14-T-01-v1"
MAC = "AA:BB:CC:DD:EE:FF"  # Disposable fixture identity, never retained in gate output.
KNOWN_DHCP = {
    "message_type": "discover", "parameter_request_list": [1, 3, 6],
    "option_order": [53, 55], "vendor_class": "lab-t01-fixture",
    "client_identifier_kind": "mac", "maximum_message_size": 1500,
    "rapid_commit_requested": False, "capport_requested": True,
    "ipv6_only_preferred_requested": False, "hostname_present": True,
}


class Blocked(RuntimeError):
    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


@dataclass(frozen=True)
class FoundationLineage:
    manifest: Any
    profile: Any
    admission: Any
    activation: Any
    validity: Any
    gate_result: Any
    registry: Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True,
            encoding="utf-8", timeout=30, check=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY") from exc


def verify_repository(repo: Path) -> None:
    repo = repo.resolve(strict=True)
    if (Path(_git(repo, "rev-parse", "--show-toplevel")).resolve() != repo
            or _git(repo, "status", "--porcelain")
            or _git(repo, "rev-parse", "HEAD") != EXPECTED_COMMIT
            or _git(repo, "show", "-s", "--format=%T", "HEAD") != EXPECTED_TREE):
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY")


def repository_filesystem_fingerprint(repo: Path) -> dict[str, dict[str, Any]]:
    """Read every non-link regular file outside .git, including ignored files."""
    root = repo.resolve(strict=True)
    files: dict[str, dict[str, Any]] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name == ".git" or entry.is_symlink():
                    continue
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if path.resolve().is_relative_to(root):
                        pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    relative = unicodedata.normalize("NFC", path.relative_to(root).as_posix())
                    if relative in files:
                        raise OSError("Repository path normalization collision")
                    before = entry.stat(follow_symlinks=False)
                    digest = hashlib.sha256()
                    size = 0
                    with path.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                            size += len(chunk)
                    after = entry.stat(follow_symlinks=False)
                    if (size != before.st_size or size != after.st_size
                            or before.st_mtime_ns != after.st_mtime_ns):
                        raise OSError("Repository file changed during fingerprint")
                    files[relative] = {"size": size, "sha256": digest.hexdigest()}
    return {relative: files[relative] for relative in sorted(files)}


def _require_repository_unchanged(repo: Path, original: dict[str, dict[str, Any]]) -> None:
    try:
        if repository_filesystem_fingerprint(repo) != original:
            raise Blocked("BLOCKED_REPOSITORY_MUTATED")
    except OSError as exc:
        raise Blocked("BLOCKED_REPOSITORY_MUTATED") from exc


def load_repository_modules(repo: Path) -> SimpleNamespace:
    repo = repo.resolve(strict=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))
    names = {
        "artifact": "app.device_fingerprint.artifact_content",
        "foundation": "app.device_fingerprint.foundation_admission_artifacts",
        "profiles": "app.device_fingerprint.runtime_profile_artifacts",
        "schema": "app.device_fingerprint.foundation_schema_artifacts",
        "gate_result": "app.device_fingerprint.foundation_gate_artifacts",
        "gate_proof": "app.device_fingerprint.gate_proof_artifacts",
        "snapshot": "app.device_fingerprint.snapshot_service",
        "read": "app.device_fingerprint.read_service",
        "repository": "app.device_fingerprint.repository",
        "persistence": "app.device_fingerprint.classification_persistence",
        "validation": "app.device_fingerprint.validation",
    }
    try:
        modules = {key: importlib.import_module(name) for key, name in names.items()}
        for module in modules.values():
            if not Path(module.__file__).resolve().is_relative_to(repo):
                raise Blocked("BLOCKED_CANDIDATE_IDENTITY")
        return SimpleNamespace(**modules)
    except Blocked:
        raise
    except (ImportError, AttributeError, OSError) as exc:
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY") from exc


def open_foundation_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
    connection = None
    try:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro", uri=True, isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        for table in ("artifacts", "activations", "validities", "validity_heads",
                      "active_pointers", "f_admit_publications"):
            connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        return connection
    except (sqlite3.Error, OSError) as exc:
        if connection is not None:
            connection.close()
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE") from exc


def _artifact_id(kind: str, digest: str) -> str:
    return f"{kind}:v1:sha256:{digest}"


def _load_artifact(connection: sqlite3.Connection, api: SimpleNamespace,
                   kind: str, digest: str, validator: Callable[[dict], Any] | None = None):
    artifact_id = _artifact_id(kind, digest)
    row = connection.execute(
        "SELECT artifact_id, artifact_type, content_sha256, semantic_payload_json "
        "FROM artifacts WHERE artifact_id=?", (artifact_id,),
    ).fetchone()
    if row is None or row["artifact_type"] != kind or row["content_sha256"] != digest:
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
    content = api.artifact.ArtifactContent(
        row["artifact_type"], 1, row["semantic_payload_json"],
        row["content_sha256"], row["artifact_id"],
    )
    if validator is not None and validator(content.semantic_payload) != content:
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
    return content


def _resolve_artifact(connection: sqlite3.Connection, api: SimpleNamespace, reference):
    ref = api.artifact.ArtifactRef.from_dict(reference)
    kind = ref.artifact_id.split(":", 1)[0]
    content = _load_artifact(connection, api, kind, ref.content_sha256)
    ref.resolve(content, kind)
    return content


def verify_foundation(connection: sqlite3.Connection, api: SimpleNamespace) -> FoundationLineage:
    try:
        digests = EXPECTED_DIGESTS
        registry = _load_artifact(
            connection, api, "EvidenceSchemaRegistryContract",
            digests["EvidenceSchemaRegistryContract"],
            lambda payload: api.schema.validate_foundation_payload(
                "EvidenceSchemaRegistryContract", payload),
        )
        manifest = _load_artifact(
            connection, api, "FoundationAdmissionManifest",
            digests["FoundationAdmissionManifest"],
            api.foundation.make_foundation_admission_manifest,
        )
        profile = _load_artifact(
            connection, api, "FoundationRuntimeProfile",
            digests["FoundationRuntimeProfile"],
            api.profiles.make_foundation_runtime_profile,
        )
        admission = _load_artifact(
            connection, api, "RuntimeProfileAdmissionManifest",
            digests["RuntimeProfileAdmissionManifest"],
            api.profiles.make_runtime_profile_admission_manifest,
        )
        gate = _load_artifact(
            connection, api, "GateResultManifest", digests["GateResultManifest"],
            api.gate_result.make_gate_result_manifest,
        )
        accepted_registry = {"artifact_id": registry.artifact_id,
                             "content_sha256": registry.content_sha256}
        accepted_profile = {"artifact_id": profile.artifact_id,
                            "content_sha256": profile.content_sha256}
        accepted_manifest = {"artifact_id": manifest.artifact_id,
                             "content_sha256": manifest.content_sha256}
        if (profile.semantic_payload["evidence_schema_registry_contract"] != accepted_registry
                or manifest.semantic_payload["evidence_schema_registry_contract"] != accepted_registry
                or admission.semantic_payload["profile_kind"] != "foundation"
                or admission.semantic_payload["candidate_profile"] != accepted_profile
                or admission.semantic_payload["foundation_admission_manifest"] != accepted_manifest):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        pointer = connection.execute(
            "SELECT * FROM active_pointers WHERE profile_kind='foundation'",
        ).fetchone()
        if (pointer is None or pointer["runtime_profile_id"] != profile.artifact_id
                or pointer["runtime_profile_digest"] != profile.content_sha256):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        active = connection.execute(
            "SELECT * FROM activations WHERE activation_record_id=?",
            (pointer["activation_record_id"],),
        ).fetchone()
        if (active is None or active["profile_kind"] != "foundation"
                or active["runtime_profile_id"] != profile.artifact_id
                or active["runtime_profile_digest"] != profile.content_sha256
                or active["activation_generation_id"] != pointer["activation_generation_id"]):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        activation_id = active["artifact_id"]
        if not isinstance(activation_id, str) or not activation_id.startswith(
                "RuntimeProfileActivationRecord:v1:sha256:"):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        activation = _load_artifact(
            connection, api, "RuntimeProfileActivationRecord", activation_id.rsplit(":", 1)[1],
            api.profiles.make_runtime_profile_activation_record,
        )
        activation_payload = activation.semantic_payload
        if (activation_payload["activation_record_id"] != pointer["activation_record_id"]
                or activation_payload["activation_generation_id"] != pointer["activation_generation_id"]
                or activation_payload["profile_kind"] != "foundation"
                or activation_payload["runtime_profile_id"] != profile.artifact_id
                or activation_payload["runtime_profile_digest"] != profile.content_sha256
                or activation_payload["runtime_profile_admission_manifest_id"] != admission.artifact_id
                or activation_payload["runtime_profile_admission_manifest_digest"] != admission.content_sha256):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        heads = connection.execute(
            "SELECT validity_record_id FROM validity_heads WHERE activation_record_id=?",
            (pointer["activation_record_id"],),
        ).fetchall()
        if len(heads) != 1:
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        validities = connection.execute(
            "SELECT validity_record_id, artifact_id, activation_record_id FROM validities "
            "WHERE validity_record_id=?", (heads[0]["validity_record_id"],),
        ).fetchall()
        if len(validities) != 1:
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        validity_row = validities[0]
        validity_id = validity_row["artifact_id"]
        if (validity_row["validity_record_id"] != heads[0]["validity_record_id"]
                or validity_row["activation_record_id"] != pointer["activation_record_id"]
                or not isinstance(validity_id, str)
                or not validity_id.startswith("RuntimeProfileValidityRecord:v1:sha256:")):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        validity = _load_artifact(
            connection, api, "RuntimeProfileValidityRecord", validity_id.rsplit(":", 1)[1],
            api.profiles.make_runtime_profile_validity_record,
        )
        validity_payload = validity.semantic_payload
        if (validity_payload["validity_record_id"] != validity_row["validity_record_id"]
                or validity_payload["activation_record_id"] != pointer["activation_record_id"]
                or validity_payload["profile_kind"] != "foundation"
                or validity_payload["runtime_profile_id"] != profile.artifact_id
                or validity_payload["runtime_profile_digest"] != profile.content_sha256
                or validity_payload["state"] != "ACTIVE"):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        publication = connection.execute(
            "SELECT artifact_id, content_sha256 FROM f_admit_publications WHERE gate_id='F-ADMIT'",
        ).fetchone()
        if (publication is None or publication["artifact_id"] != gate.artifact_id
                or publication["content_sha256"] != gate.content_sha256
                or gate.semantic_payload["gate_id"] != "F-ADMIT"
                or gate.semantic_payload["status"] != "PASS"):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        outputs = {ref["artifact_id"]: ref["content_sha256"] for ref in gate.semantic_payload[
            "output_artifact_refs"]}
        for content in (manifest, profile, admission, activation, validity):
            if outputs.get(content.artifact_id) != content.content_sha256:
                raise Blocked("BLOCKED_FOUNDATION_LINEAGE")
        return FoundationLineage(manifest, profile, admission, activation, validity, gate, registry)
    except Blocked:
        raise
    except Exception as exc:
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE") from exc


def _ref(content: Any) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _environment_identity() -> str:
    import pytest

    return (f"{platform.system()}-{platform.release()}|"
            f"Python-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}|"
            f"SQLite-{sqlite3.sqlite_version}|pytest-{pytest.__version__}")


def execute_pytest(repo: Path, run_dir: Path) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="t01-pytest-", dir=run_dir) as temporary:
        temporary_path = Path(temporary)
        process_temp = temporary_path / "process-temp"
        process_temp.mkdir()
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--basetemp", str(temporary_path / "pytest-temp"),
                   "tests/device_fingerprint_task04_t01"]
        command_text = subprocess.list2cmdline(command)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(repo) + os.pathsep + environment.get("PYTHONPATH", "")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for name in ("TEMP", "TMP", "TMPDIR"):
            environment[name] = str(process_temp)
        environment["PYTEST_ADDOPTS"] = ""
        try:
            result = subprocess.run(
                command, cwd=repo, env=environment, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", timeout=1800,
            )
            return result.returncode, result.stdout, command_text
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, f"T-01 pytest execution failed: {type(exc).__name__}\n", command_text


def _fixture_row(api: SimpleNamespace, epoch: dict[str, Any], observed_at: str,
                 ingested_at: str, sequence: int, *, version: int = 1,
                 raw: str | None = None, hash_override: str | None = None) -> dict[str, Any]:
    payload = raw if raw is not None else api.validation.canonical_json(KNOWN_DHCP)
    return {
        "evidence_id": str(uuid.uuid4()), "source_event_id": str(uuid.uuid4()),
        "ingest_sequence": sequence, "producer_id": epoch["producer_id"],
        "source_kind": "dhcp", "source_subtype": None,
        "capture_source_id": epoch["capture_source_id"], "extractor_name": "dhcp-v1",
        "extractor_version": "1.0.0", "feature_schema_version": version,
        "rule_version": None, "site_id": epoch["site_id"],
        "observed_at": observed_at, "ingested_at": ingested_at,
        "observed_mac": MAC, "observed_ip": "192.0.2.10", "privacy_class": "P1",
        "quality_state": "valid", "payload_json": payload,
        "payload_sha256": hash_override or api.validation.canonical_sha256(payload),
    }


def _window(api: SimpleNamespace, profile: Any, resolver: Callable) -> tuple[dict, str, str, str]:
    timeline = resolver(api.artifact.ArtifactRef.from_dict(profile.semantic_payload[
        "evidence_source_binding_timeline"]))
    clock = resolver(api.artifact.ArtifactRef.from_dict(profile.semantic_payload[
        "binding_clock_policy"]))
    valid_from = api.validation.parse_utc(profile.semantic_payload[
        "classification_foundation_valid_from_utc"])
    guard = clock.semantic_payload["cutover_guard_seconds"]
    for epoch in timeline.semantic_payload["binding_epochs"]:
        if epoch["origin_group"] != "dhcp" or epoch["source_kind"] != "dhcp":
            continue
        start = max(valid_from, api.validation.parse_utc(epoch["effective_from_utc"]))
        start += timedelta(seconds=guard + 3600)
        end = start + timedelta(minutes=10)
        epoch_end = epoch["effective_to_utc"]
        if epoch_end is None or end < api.validation.parse_utc(epoch_end):
            return (epoch, api.validation.format_utc(start),
                    api.validation.format_utc(end),
                    api.validation.format_utc(start + timedelta(minutes=1)))
    raise RuntimeError("No authorized disposable DHCP fixture window")


def _create_task01(api: SimpleNamespace, path: Path, rows: list[dict],
                   *, generation: str = "11111111-1111-4111-8111-111111111111") -> None:
    store = api.repository.DeviceFingerprintRepository(path, max_db_bytes=67_108_864)
    store.initialize()
    store.close()
    with sqlite3.connect(path) as connection:
        for row in rows:
            columns = tuple(row)
            connection.execute(
                "INSERT INTO device_fingerprint_evidence (" + ",".join(columns) + ") VALUES ("
                + ",".join("?" for _ in columns) + ")",
                tuple(row[column] for column in columns),
            )
        connection.execute(
            "UPDATE device_fingerprint_storage_state SET database_generation_id=?, "
            "last_ingest_sequence=? WHERE singleton_id=1",
            (generation, max((row["ingest_sequence"] for row in rows), default=0)),
        )


def execute_matrix(run_dir: Path, api: SimpleNamespace, profile: Any,
                   resolver: Callable) -> dict[str, Any]:
    """Disposable Task-01 data, real read sessions and real snapshot service only."""
    with tempfile.TemporaryDirectory(prefix="t01-matrix-", dir=run_dir) as directory:
        return _execute_matrix(Path(directory), api, profile, resolver)


def _execute_matrix(run_dir: Path, api: SimpleNamespace, profile: Any,
                    resolver: Callable) -> dict[str, Any]:
    epoch, start, end, observed = _window(api, profile, resolver)
    ingested = api.validation.format_utc(api.validation.parse_utc(end) + timedelta(minutes=1))
    captured = api.validation.format_utc(api.validation.parse_utc(end) + timedelta(days=1))
    cases: dict[str, dict[str, Any]] = {}
    trace: dict[str, Any] = {}

    def build(case_id: str, rows: list[dict], *, page_size: int = 500,
              concurrent: bool = False):
        case_dir = run_dir / case_id
        case_dir.mkdir()
        db_path = case_dir / "task01-disposable.sqlite"
        _create_task01(api, db_path, rows)
        reader = api.read.DeviceFingerprintReadService(str(db_path), retention_days=30)
        later = _fixture_row(api, epoch, observed, ingested, len(rows) + 1)
        if concurrent:
            base = api.read.DeviceFingerprintReadService

            class ConcurrentReader(base):
                opens = 0

                def open_snapshot_read(self):
                    self.opens += 1
                    session = super().open_snapshot_read()
                    with sqlite3.connect(db_path) as writer:
                        columns = tuple(later)
                        writer.execute(
                            "INSERT INTO device_fingerprint_evidence (" + ",".join(columns)
                            + ") VALUES (" + ",".join("?" for _ in columns) + ")",
                            tuple(later[column] for column in columns),
                        )
                        writer.execute("UPDATE device_fingerprint_storage_state SET "
                                       "last_ingest_sequence=? WHERE singleton_id=1",
                                       (later["ingest_sequence"],))
                    return session

            reader = ConcurrentReader(str(db_path), retention_days=30)
        service = api.snapshot.DeviceFingerprintSnapshotService(
            reader, foundation_runtime_profile=profile, artifact_resolver=resolver,
            utc_clock=lambda: captured, process_memory_guard=lambda _limit: True,
            page_size=page_size,
        )
        result = service.build(epoch["site_id"], MAC, start, end)
        return result, reader, db_path

    def capture(case_id: str, rows: list[dict], verify: Callable[[Any, Any, Path], None],
                *, expected_failure: str | None = None, page_size: int = 500,
                concurrent: bool = False):
        fixture_hash = hashlib.sha256(_json_bytes(rows)).hexdigest()
        try:
            result, reader, path = build(case_id, rows, page_size=page_size,
                                         concurrent=concurrent)
            if expected_failure is not None:
                raise AssertionError("Expected whole-snapshot failure")
            verify(result, reader, path)
            record = result.snapshot_record.semantic_payload
            cases[case_id] = {
                "status": "PASS", "input_fixture_sha256": fixture_hash,
                "snapshot_record": _ref(result.snapshot_record),
                "evidence_snapshot_content": _ref(result.evidence_snapshot_content),
                "verified_evidence_row_count": record["verified_evidence_row_count"],
                "materialized_evidence_row_count": record["materialized_evidence_row_count"],
                "verified_payload_bytes": record["verified_payload_bytes"],
                "materialized_payload_bytes": record["materialized_payload_bytes"],
            }
            return result
        except api.snapshot.SnapshotBuildError as exc:
            cases[case_id] = {
                "status": "PASS" if exc.reason_code == expected_failure else "FAIL",
                "input_fixture_sha256": fixture_hash, "failure_reason_code": exc.reason_code,
            }
        except Exception as exc:
            cases[case_id] = {"status": "FAIL", "input_fixture_sha256": fixture_hash,
                              "failure_reason_code": type(exc).__name__}
        return None

    known = _fixture_row(api, epoch, observed, ingested, 1)
    capture("T01-M01", [known], lambda result, _reader, _path: (
        _require(len(result.materialization.ordered_entries) == 1),
        _require(len(result.evidence_snapshot_content.semantic_payload["evidence_descriptors"]) == 1),
        _require(result.snapshot_record.semantic_payload["build_outcome"] == "success"),
    ))
    capture("T01-M02", [_fixture_row(api, epoch, observed, ingested, 1,
                                    raw=api.validation.canonical_json({"unknown": "field"}))],
            lambda *_: None, expected_failure="schema_validation_failure")
    capture("T01-M03", [_fixture_row(api, epoch, observed, ingested, 1, raw="{ ")],
            lambda *_: None, expected_failure="corrupt_payload")
    capture("T01-M04", [_fixture_row(api, epoch, observed, ingested, 1, raw='{"a":1,"a":2}')],
            lambda *_: None, expected_failure="corrupt_payload")
    capture("T01-M05", [_fixture_row(api, epoch, observed, ingested, 1,
                                    raw=json.dumps(KNOWN_DHCP, sort_keys=True))],
            lambda *_: None, expected_failure="corrupt_payload")
    capture("T01-M06", [_fixture_row(api, epoch, observed, ingested, 1,
                                    hash_override="0" * 64)],
            lambda *_: None, expected_failure="payload_hash_mismatch")
    future = _fixture_row(api, epoch, observed, ingested, 1, version=99,
                          raw=api.validation.canonical_json({"future": "opaque"}))
    capture("T01-M07", [future], lambda result, _reader, _path: (
        _require(len(result.evidence_snapshot_content.semantic_payload["evidence_descriptors"]) == 1),
        _require(len(result.materialization.ordered_entries) == 0),
        _require(result.snapshot_record.semantic_payload["verified_evidence_row_count"] == 1),
        _require(result.snapshot_record.semantic_payload["materialized_evidence_row_count"] == 0),
    ))

    many = [_fixture_row(api, epoch, observed, ingested, number) for number in range(1, 503)]
    first = capture("T01-M08", many, lambda result, _reader, _path: _require(
        len(result.evidence_snapshot_content.semantic_payload["evidence_descriptors"]) == 502))
    if first is not None:
        try:
            second, _, _ = build("T01-M08-permuted", list(reversed(many)), page_size=97)
            _require(first.evidence_snapshot_content == second.evidence_snapshot_content)
        except Exception as exc:
            cases["T01-M08"]["status"] = "FAIL"
            cases["T01-M08"]["failure_reason_code"] = type(exc).__name__

    def verify_concurrent(result, reader, _path):
        record = result.snapshot_record.semantic_payload
        _require(reader.opens == 1)
        _require(record["verified_evidence_row_count"] == 1)
        _require(result.evidence_snapshot_content.semantic_payload[
            "max_committed_ingest_sequence"] == 1)
        trace.update({"read_sessions": reader.opens, "captured_watermark": 1,
                      "later_committed_sequence": 2, "selected_rows": 1})

    capture("T01-M09", [known], verify_concurrent, concurrent=True)

    def verify_transient(result, _reader, task01_path):
        normalized = result.materialization.ordered_entries[0].normalized_payload
        _require(normalized == KNOWN_DHCP)
        _require("vendor_class" not in str(result.evidence_snapshot_content.semantic_payload))
        _require("vendor_class" not in str(result.snapshot_record.semantic_payload))
        classification_path = task01_path.parent / "classification-disposable.sqlite"
        store = api.persistence.DeviceFingerprintClassificationStore(
            classification_path, task01_path, control_plane_store=object())
        store.initialize()
        with sqlite3.connect(classification_path) as connection:
            _require(connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0)

    capture("T01-M10", [known], verify_transient)

    known2 = _fixture_row(api, epoch, observed, ingested, 1)
    future2 = _fixture_row(api, epoch, observed, ingested, 2, version=99,
                           raw=api.validation.canonical_json({"future": "opaque"}))

    def verify_bytes(result, _reader, _path):
        record = result.snapshot_record.semantic_payload
        _require(record["verified_evidence_row_count"] == 2)
        _require(record["materialized_evidence_row_count"] == 1)
        _require(record["verified_payload_bytes"] == sum(
            len(row["payload_json"].encode("utf-8")) for row in (known2, future2)))
        _require(record["materialized_payload_bytes"] == len(
            known2["payload_json"].encode("utf-8")))

    capture("T01-M11", [known2, future2], verify_bytes)
    return {"cases": cases, "transaction_watermark_trace": trace,
            "all_pass": len(cases) == 11 and all(case["status"] == "PASS"
                                             for case in cases.values())}


def _require(condition: bool) -> None:
    if not condition:
        raise AssertionError("T-01 direct proof assertion failed")


def _artifact_document(content: Any, canonicalizer: Callable) -> bytes:
    return canonicalizer({
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "artifact_id": content.artifact_id,
        "content_sha256": content.content_sha256,
        "semantic_payload": content.semantic_payload,
    })


def _write_and_roundtrip(path: Path, content: Any, builder: Callable,
                         canonicalizer: Callable) -> None:
    path.write_bytes(_artifact_document(content, canonicalizer))
    document = json.loads(path.read_bytes())
    if (document["artifact_type"] != content.artifact_type
            or document["artifact_schema_version"] != 1
            or document["artifact_id"] != content.artifact_id
            or document["content_sha256"] != content.content_sha256
            or builder(document["semantic_payload"]) != content):
        raise RuntimeError("Formal artifact round-trip mismatch")


def _evidence_refs(run_dir: Path) -> list[dict[str, str]]:
    return [
        {"evidence_label": "t01-execution-evidence", "file_sha256": _sha256(
            run_dir / "t01-execution-evidence.json"), "media_type": "application/json",
         "path_or_reference": "t01-execution-evidence.json"},
        {"evidence_label": "t01-pytest-log", "file_sha256": _sha256(
            run_dir / "t01-pytest.log"), "media_type": "text/plain",
         "path_or_reference": "t01-pytest.log"},
    ]


def _formal_outputs(run_dir: Path, api: SimpleNamespace, lineage: FoundationLineage,
                    runner_sha: str, passed: bool):
    inputs = [_ref(lineage.profile), _ref(lineage.registry)]
    evidence = _evidence_refs(run_dir)
    identity = {
        "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": EXPECTED_COMMIT, "repository_tree_sha": EXPECTED_TREE,
        "procedure_or_test_suite_id": PROCEDURE,
        "environment_identity": _environment_identity(),
        "execution_artifact_sha256": runner_sha,
    }
    proof = None
    if passed:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": "SNAPSHOT_MATERIALIZATION_EXECUTION",
            "source_gate_id": "T-01", "candidate_repository_commit_sha": EXPECTED_COMMIT,
            "candidate_repository_tree_sha": EXPECTED_TREE,
            "input_artifact_refs": inputs, "procedure_or_test_suite_id": PROCEDURE,
            "proof_execution_identity": identity,
            "canonical_result_summary": "T-01:pytest=PASS;matrix=11/11 PASS",
            "retained_evidence_refs": evidence,
        })
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": "T-01", "gate_contract_version": GATE_CONTRACT,
        "status": "PASS" if passed else "FAIL",
        "candidate_repository_commit_sha": EXPECTED_COMMIT,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "input_artifact_refs": inputs,
        "output_artifact_refs": [_ref(proof)] if proof is not None else [],
        "retained_evidence_refs": evidence,
        "proof_execution_identity": identity,
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    })
    if proof is not None:
        _write_and_roundtrip(run_dir / "t01-gate-proof-artifact.json", proof,
                             api.gate_proof.make_gate_proof_artifact,
                             api.artifact.canonical_artifact_json)
    _write_and_roundtrip(run_dir / "t01-gate-result-manifest.json", result,
                         api.gate_result.make_gate_result_manifest,
                         api.artifact.canonical_artifact_json)
    (run_dir / "t01-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}\n"
        f"GATE_RESULT_MANIFEST={result.artifact_id}\n"
        f"GATE_PROOF_ARTIFACT={proof.artifact_id if proof else 'NONE'}\n",
        encoding="utf-8",
    )
    return proof, result


def _blocked(run_dir: Path, status: str) -> int:
    for filename in ("t01-execution-evidence.json", "t01-pytest.log",
                     "t01-gate-proof-artifact.json", "t01-gate-result-manifest.json"):
        (run_dir / filename).unlink(missing_ok=True)
    (run_dir / "t01-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={status}\nFORMAL_GATE_RESULT_MANIFEST=NONE\n",
        encoding="utf-8",
    )
    print(f"GATE_EXECUTION_STATUS={status}")
    return 2


def run_gate(repo: Path, foundation_db: Path, output_dir: Path) -> int:
    runner_path = Path(__file__).resolve()
    runner_sha = _sha256(runner_path)
    output_dir = output_dir.resolve()
    if output_dir.is_relative_to(repo.resolve()):
        print("GATE_EXECUTION_STATUS=BLOCKED_OUTPUT_DIR")
        return 2
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        print("GATE_EXECUTION_STATUS=BLOCKED_OUTPUT_DIR")
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / str(uuid.uuid4())
    run_dir.mkdir(exist_ok=False)
    connection = None
    try:
        verify_repository(repo)
        repository_before = repository_filesystem_fingerprint(repo)
        api = load_repository_modules(repo)
        connection = open_foundation_read_only(foundation_db)
        lineage = verify_foundation(connection, api)
        _require_repository_unchanged(repo, repository_before)
    except (Blocked, OSError) as exc:
        if connection is not None:
            try:
                connection.rollback()
            finally:
                connection.close()
        return _blocked(run_dir, exc.status if isinstance(exc, Blocked)
                        else "BLOCKED_CANDIDATE_IDENTITY")
    try:
        pytest_status, pytest_log, pytest_command = execute_pytest(repo, run_dir)
        (run_dir / "t01-pytest.log").write_text(pytest_log, encoding="utf-8")
        try:
            matrix = execute_matrix(
                run_dir, api, lineage.profile,
                lambda reference: _resolve_artifact(connection, api, reference.as_dict()),
            )
        except Exception as exc:
            matrix = {"cases": {}, "transaction_watermark_trace": {}, "all_pass": False,
                      "execution_failure_type": type(exc).__name__}
        try:
            _require_repository_unchanged(repo, repository_before)
        except Blocked as exc:
            return _blocked(run_dir, exc.status)
        evidence = {
            "candidate_repository_commit_sha": EXPECTED_COMMIT,
            "candidate_repository_tree_sha": EXPECTED_TREE,
            "runner_sha256": runner_sha,
            "foundation_lineage": {kind: _ref(content) for kind, content in (
                ("FoundationAdmissionManifest", lineage.manifest),
                ("FoundationRuntimeProfile", lineage.profile),
                ("RuntimeProfileAdmissionManifest", lineage.admission),
                ("RuntimeProfileActivationRecord", lineage.activation),
                ("RuntimeProfileValidityRecord", lineage.validity),
                ("F-ADMIT GateResultManifest", lineage.gate_result),
            )},
            "evidence_schema_registry_contract": _ref(lineage.registry),
            "matrix": matrix,
            "pytest_command": pytest_command,
            "pytest_exit_status": pytest_status,
        }
        (run_dir / "t01-execution-evidence.json").write_bytes(_json_bytes(evidence))
        if _sha256(runner_path) != runner_sha:
            return _blocked(run_dir, "BLOCKED_RUNNER_CHANGED")
        passed = pytest_status == 0 and matrix["all_pass"]
        _formal_outputs(run_dir, api, lineage, runner_sha, passed)
        try:
            _require_repository_unchanged(repo, repository_before)
        except Blocked as exc:
            return _blocked(run_dir, exc.status)
        if _sha256(runner_path) != runner_sha:
            return _blocked(run_dir, "BLOCKED_RUNNER_CHANGED")
        print(f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    finally:
        if connection is not None:
            try:
                connection.rollback()
            finally:
                connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.output_dir)


if __name__ == "__main__":
    sys.exit(main())
