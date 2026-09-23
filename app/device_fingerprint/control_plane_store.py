"""Single-SQLite-domain R14 runtime-profile activation and validity control plane."""

from __future__ import annotations

import sqlite3
from dataclasses import astuple, dataclass
from pathlib import Path
from typing import Callable, Iterable

from .artifact_content import ArtifactContent, ArtifactRef
from .models import DeviceFingerprintValidationError
from .runtime_profile_artifacts import (
    direct_artifact_refs, make_classification_runtime_profile,
    make_foundation_runtime_profile, make_runtime_profile_activation_record,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
)

_VALIDATORS = {
    "FoundationRuntimeProfile": make_foundation_runtime_profile,
    "ClassificationRuntimeProfile": make_classification_runtime_profile,
    "RuntimeProfileAdmissionManifest": make_runtime_profile_admission_manifest,
    "RuntimeProfileActivationRecord": make_runtime_profile_activation_record,
    "RuntimeProfileValidityRecord": make_runtime_profile_validity_record,
}


class ControlPlaneOperationError(RuntimeError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ActiveProfilePointerV1:
    profile_kind: str
    runtime_profile_id: str
    runtime_profile_digest: str
    activation_record_id: str
    activation_generation_id: str


@dataclass(frozen=True, slots=True)
class PinnedRuntimeProfile:
    pointer: ActiveProfilePointerV1
    runtime_profile: ArtifactContent
    admission_manifest: ArtifactContent
    activation_record: ArtifactContent
    validity_record: ArtifactContent


class DeviceFingerprintControlPlaneStore:
    """All pointer, lineage, validity, and immutable dependency writes share one DB."""

    def __init__(self, database_path: str | Path, *, fault_hook: Callable[[str], None] | None = None):
        self.database_path = str(database_path)
        self.fault_hook = fault_hook

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _fault(self, stage: str) -> None:
        if self.fault_hook is not None:
            self.fault_hook(stage)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY, artifact_type TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL, semantic_payload_json BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifact_dependencies (
                    owner_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                    dependency_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                    dependency_digest TEXT NOT NULL,
                    PRIMARY KEY (owner_id, dependency_id)
                );
                CREATE TABLE IF NOT EXISTS activations (
                    activation_record_id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(artifact_id),
                    profile_kind TEXT NOT NULL, runtime_profile_id TEXT NOT NULL,
                    runtime_profile_digest TEXT NOT NULL, activation_generation_id TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS validities (
                    validity_record_id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(artifact_id),
                    activation_record_id TEXT NOT NULL REFERENCES activations(activation_record_id)
                );
                CREATE TABLE IF NOT EXISTS validity_heads (
                    activation_record_id TEXT PRIMARY KEY REFERENCES activations(activation_record_id),
                    validity_record_id TEXT NOT NULL REFERENCES validities(validity_record_id)
                );
                CREATE TABLE IF NOT EXISTS active_pointers (
                    profile_kind TEXT PRIMARY KEY, runtime_profile_id TEXT NOT NULL,
                    runtime_profile_digest TEXT NOT NULL,
                    activation_record_id TEXT NOT NULL REFERENCES activations(activation_record_id),
                    activation_generation_id TEXT NOT NULL
                );
            """)

    @staticmethod
    def _validated(content: ArtifactContent) -> None:
        if not isinstance(content, ArtifactContent):
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        validator = _VALIDATORS.get(content.artifact_type)
        if validator is not None and validator(content.semantic_payload).artifact_id != content.artifact_id:
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")

    @staticmethod
    def _load(conn: sqlite3.Connection, artifact_id: str, digest: str | None = None) -> ArtifactContent:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        if row is None:
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        try:
            content = ArtifactContent(row["artifact_type"], 1, row["semantic_payload_json"],
                                      row["content_sha256"], row["artifact_id"])
            DeviceFingerprintControlPlaneStore._validated(content)
        except (DeviceFingerprintValidationError, UnicodeError, TypeError, ValueError) as exc:
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable") from exc
        if digest is not None and content.content_sha256 != digest:
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        return content

    @staticmethod
    def _put(conn: sqlite3.Connection, content: ArtifactContent,
             refs: Iterable[ArtifactRef] = ()) -> None:
        DeviceFingerprintControlPlaneStore._validated(content)
        current = conn.execute("SELECT semantic_payload_json, content_sha256 FROM artifacts WHERE artifact_id=?",
                               (content.artifact_id,)).fetchone()
        if current is not None:
            if current[0] != content.semantic_payload_json or current[1] != content.content_sha256:
                raise ControlPlaneOperationError("artifact_immutable_conflict")
            return
        conn.execute("INSERT INTO artifacts VALUES (?,?,?,?)",
                     (content.artifact_id, content.artifact_type, content.content_sha256,
                      content.semantic_payload_json))
        for ref in refs:
            DeviceFingerprintControlPlaneStore._load(conn, ref.artifact_id, ref.content_sha256)
            conn.execute("INSERT INTO artifact_dependencies VALUES (?,?,?)",
                         (content.artifact_id, ref.artifact_id, ref.content_sha256))

    def persist_artifact(self, content: ArtifactContent, dependency_refs: Iterable[ArtifactRef] = ()) -> None:
        if (isinstance(content, ArtifactContent) and content.artifact_type in (
                "RuntimeProfileActivationRecord", "RuntimeProfileValidityRecord")):
            raise DeviceFingerprintValidationError(
                "Runtime control-plane record requires transactional mutation")
        refs = tuple(dependency_refs)
        if any(not isinstance(ref, ArtifactRef) for ref in refs):
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        declared = direct_artifact_refs(content)
        if content.artifact_type in (
                "FoundationRuntimeProfile", "ClassificationRuntimeProfile", "RuntimeProfileAdmissionManifest"):
            if refs != declared:
                raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._put(conn, content, refs)
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def load_artifact(self, artifact_id: str, expected_content_sha256: str | None = None) -> ArtifactContent:
        with self._connect() as conn:
            return self._load(conn, artifact_id, expected_content_sha256)

    @staticmethod
    def _closure(conn: sqlite3.Connection, content: ArtifactContent, seen: set[str] | None = None) -> None:
        seen = set() if seen is None else seen
        if content.artifact_id in seen:
            return
        seen.add(content.artifact_id)
        declared = direct_artifact_refs(content)
        edges = conn.execute("SELECT dependency_id, dependency_digest FROM artifact_dependencies "
                             "WHERE owner_id=? ORDER BY dependency_id", (content.artifact_id,)).fetchall()
        actual = tuple(ArtifactRef(row[0], row[1]) for row in edges)
        if content.artifact_type in (
                "FoundationRuntimeProfile", "ClassificationRuntimeProfile", "RuntimeProfileAdmissionManifest"):
            if actual != declared:
                raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        if content.artifact_type == "FoundationRuntimeProfile":
            payload = content.semantic_payload
            origin_ref = ArtifactRef.from_dict(payload["origin_runtime_admission"])
            origin = DeviceFingerprintControlPlaneStore._load(
                conn, origin_ref.artifact_id, origin_ref.content_sha256).semantic_payload
            if (set(origin) != {"origin_runtime_admission_contract_version", "tcp_state",
                                "tcp_reason_code", "ttl_capture_placement_proof"} or
                    type(origin["origin_runtime_admission_contract_version"]) is not int or
                    origin["origin_runtime_admission_contract_version"] < 1):
                raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
            ttl = payload["ttl_capture_placement_proof"]
            if origin["tcp_state"] == "ENABLED":
                if (origin["tcp_reason_code"] != "TTL_PROOF_VALID" or ttl is None or
                        origin["ttl_capture_placement_proof"] != ttl):
                    raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
            elif origin["tcp_state"] == "DISABLED":
                if (origin["tcp_reason_code"] not in {"TTL_PROOF_INVALID", "PROFILE_POLICY_DISABLED"}
                        or origin["ttl_capture_placement_proof"] is not None or ttl is not None):
                    raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
            else:
                raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        for ref in actual:
            dependency = DeviceFingerprintControlPlaneStore._load(conn, ref.artifact_id, ref.content_sha256)
            DeviceFingerprintControlPlaneStore._closure(conn, dependency, seen)

    @staticmethod
    def _pointer(conn: sqlite3.Connection, kind: str) -> ActiveProfilePointerV1 | None:
        row = conn.execute("SELECT * FROM active_pointers WHERE profile_kind=?", (kind,)).fetchone()
        return ActiveProfilePointerV1(**dict(row)) if row is not None else None

    def get_active_pointer(self, profile_kind: str) -> ActiveProfilePointerV1 | None:
        with self._connect() as conn:
            return self._pointer(conn, profile_kind)

    def get_validity_head(self, activation_record_id: str) -> ArtifactContent | None:
        with self._connect() as conn:
            row = conn.execute("SELECT v.artifact_id FROM validity_heads h JOIN validities v "
                               "ON v.validity_record_id=h.validity_record_id "
                               "WHERE h.activation_record_id=?", (activation_record_id,)).fetchone()
            return self._load(conn, row[0]) if row is not None else None

    @staticmethod
    def _precheck(conn: sqlite3.Connection, rpm: ArtifactContent, activation: ArtifactContent,
                  initial: ArtifactContent, predecessor: ArtifactContent | None) -> None:
        try:
            if (not all(isinstance(item, ArtifactContent) for item in (rpm, activation, initial)) or
                    (predecessor is not None and not isinstance(predecessor, ArtifactContent)) or
                    rpm.artifact_type != "RuntimeProfileAdmissionManifest" or
                    activation.artifact_type != "RuntimeProfileActivationRecord" or
                    initial.artifact_type != "RuntimeProfileValidityRecord" or
                    (predecessor is not None and
                     predecessor.artifact_type != "RuntimeProfileValidityRecord")):
                raise ValueError("wrong activation artifact type")
            DeviceFingerprintControlPlaneStore._validated(rpm)
            DeviceFingerprintControlPlaneStore._validated(activation)
            DeviceFingerprintControlPlaneStore._validated(initial)
            if predecessor is not None:
                DeviceFingerprintControlPlaneStore._validated(predecessor)
            rp = rpm.semantic_payload
            ap = activation.semantic_payload
            vp = initial.semantic_payload
            stored_rpm = DeviceFingerprintControlPlaneStore._load(conn, rpm.artifact_id, rpm.content_sha256)
            candidate = DeviceFingerprintControlPlaneStore._load(
                conn, rp["candidate_profile"]["artifact_id"], rp["candidate_profile"]["content_sha256"])
            if stored_rpm != rpm or ap["profile_kind"] != rp["profile_kind"] or (
                    ap["runtime_profile_id"], ap["runtime_profile_digest"]) != (
                    candidate.artifact_id, candidate.content_sha256) or (
                    ap["runtime_profile_admission_manifest_id"],
                    ap["runtime_profile_admission_manifest_digest"]) != (
                    rpm.artifact_id, rpm.content_sha256) or ap["activation_reason_update_class"] != rp["update_class"]:
                raise ValueError("activation/RPM mismatch")
            if (ap["previous_activation_record_id"] != rp["expected_previous_activation_record_id"] or
                    (ap["previous_active_profile_id"], ap["previous_active_profile_digest"]) != (
                        (rp["previous_active_profile"] or {}).get("artifact_id"),
                        (rp["previous_active_profile"] or {}).get("content_sha256"))):
                raise ValueError("activation predecessor mismatch")
            if (vp["state"] != "ACTIVE" or vp["previous_validity_record_id"] is not None or
                    vp["reason_code"] != ("ROLLBACK_REACTIVATED" if rp["update_class"] == "ROLLBACK_REACTIVATION"
                                          else "ACTIVATED") or
                    (vp["profile_kind"], vp["runtime_profile_id"], vp["runtime_profile_digest"],
                     vp["activation_record_id"]) != (
                        ap["profile_kind"], ap["runtime_profile_id"], ap["runtime_profile_digest"],
                        ap["activation_record_id"])):
                raise ValueError("initial validity mismatch")
            if rp["profile_kind"] == "classification":
                foundation_ref = candidate.semantic_payload["foundation_runtime_profile"]
                foundation_rpm_ref = rp["foundation_runtime_profile_admission_manifest"]
                foundation_rpm = DeviceFingerprintControlPlaneStore._load(
                    conn, foundation_rpm_ref["artifact_id"], foundation_rpm_ref["content_sha256"])
                if (foundation_rpm.semantic_payload["profile_kind"] != "foundation" or
                        foundation_rpm.semantic_payload["candidate_profile"] != foundation_ref):
                    raise ValueError("foundation admission lineage mismatch")
            if rp["update_class"] == "ROLLBACK_REACTIVATION":
                prior = conn.execute("SELECT artifact_id FROM artifacts WHERE "
                                     "artifact_type='RuntimeProfileAdmissionManifest' AND artifact_id<>?",
                                     (rpm.artifact_id,)).fetchall()
                if not any(DeviceFingerprintControlPlaneStore._load(conn, row[0]).semantic_payload[
                        "candidate_profile"] == rp["candidate_profile"] for row in prior):
                    raise ValueError("rollback target was not previously admitted")
            if predecessor is not None and (predecessor.semantic_payload["state"] != "INACTIVE" or
                    predecessor.semantic_payload["reason_code"] != "SUPERSEDED_SAFE" or
                    predecessor.semantic_payload["activation_record_id"] !=
                    rp["expected_previous_activation_record_id"]):
                raise ValueError("predecessor validity mismatch")
            DeviceFingerprintControlPlaneStore._closure(conn, stored_rpm)
            DeviceFingerprintControlPlaneStore._closure(conn, candidate)
        except (KeyError, TypeError, ValueError, DeviceFingerprintValidationError,
                ControlPlaneOperationError) as exc:
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable") from exc

    def activate_profile(self, admission_manifest: ArtifactContent, activation_record: ArtifactContent,
                         initial_validity_record: ArtifactContent, *,
                         predecessor_inactive_validity_record: ArtifactContent | None = None) -> ActiveProfilePointerV1:
        conn = self._connect()
        try:
            self._precheck(conn, admission_manifest, activation_record, initial_validity_record,
                           predecessor_inactive_validity_record)
            self._fault("BEFORE_BEGIN")
            conn.execute("BEGIN IMMEDIATE")
            self._fault("AFTER_BEGIN_BEFORE_WRITES")
            rp = admission_manifest.semantic_payload
            ap = activation_record.semantic_payload
            kind = rp["profile_kind"]
            current = self._pointer(conn, kind)
            expected_ref = rp["previous_active_profile"]
            expected = None if expected_ref is None else ActiveProfilePointerV1(
                kind, expected_ref["artifact_id"], expected_ref["content_sha256"],
                rp["expected_previous_activation_record_id"],
                rp["expected_previous_activation_generation_id"])
            if current != expected:
                raise ControlPlaneOperationError("active_profile_precondition_mismatch")
            if current is not None:
                head = self._head(conn, current.activation_record_id)
                if head.semantic_payload["state"] == "INACTIVE":
                    raise ControlPlaneOperationError("activation_lineage_unavailable")
                if head.semantic_payload["state"] == "ACTIVE":
                    old = predecessor_inactive_validity_record
                    if old is None or old.semantic_payload["previous_validity_record_id"] != (
                            head.semantic_payload["validity_record_id"]) or (
                            old.semantic_payload["profile_kind"], old.semantic_payload["runtime_profile_id"],
                            old.semantic_payload["runtime_profile_digest"]) != (
                                kind, current.runtime_profile_id, current.runtime_profile_digest):
                        raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
                    self._put(conn, old)
                    self._insert_validity(conn, old)
                    changed = conn.execute("UPDATE validity_heads SET validity_record_id=? "
                                           "WHERE activation_record_id=? AND validity_record_id=?",
                                           (old.semantic_payload["validity_record_id"], current.activation_record_id,
                                            head.semantic_payload["validity_record_id"])).rowcount
                    if changed != 1:
                        raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
                elif predecessor_inactive_validity_record is not None:
                    raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
            elif predecessor_inactive_validity_record is not None:
                raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
            self._put(conn, activation_record)
            conn.execute("INSERT INTO activations VALUES (?,?,?,?,?,?)", (
                ap["activation_record_id"], activation_record.artifact_id, kind,
                ap["runtime_profile_id"], ap["runtime_profile_digest"], ap["activation_generation_id"]))
            self._put(conn, initial_validity_record)
            self._insert_validity(conn, initial_validity_record)
            conn.execute("INSERT INTO validity_heads VALUES (?,?)", (
                ap["activation_record_id"], initial_validity_record.semantic_payload["validity_record_id"]))
            pointer = ActiveProfilePointerV1(kind, ap["runtime_profile_id"], ap["runtime_profile_digest"],
                                             ap["activation_record_id"], ap["activation_generation_id"])
            if current is None:
                conn.execute("INSERT INTO active_pointers VALUES (?,?,?,?,?)", astuple(pointer))
            else:
                changed = conn.execute("UPDATE active_pointers SET runtime_profile_id=?, "
                                       "runtime_profile_digest=?, activation_record_id=?, activation_generation_id=? "
                                       "WHERE profile_kind=? AND runtime_profile_id=? AND runtime_profile_digest=? "
                                       "AND activation_record_id=? AND activation_generation_id=?", (
                                           pointer.runtime_profile_id, pointer.runtime_profile_digest,
                                           pointer.activation_record_id, pointer.activation_generation_id,
                                           *astuple(current))).rowcount
                if changed != 1:
                    raise ControlPlaneOperationError("active_profile_precondition_mismatch")
            self._fault("AFTER_WRITES_BEFORE_COMMIT")
            conn.commit()
            self._fault("AFTER_COMMIT")
            return pointer
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _insert_validity(conn: sqlite3.Connection, content: ArtifactContent) -> None:
        vp = content.semantic_payload
        conn.execute("INSERT INTO validities VALUES (?,?,?)", (
            vp["validity_record_id"], content.artifact_id, vp["activation_record_id"]))

    @staticmethod
    def _head(conn: sqlite3.Connection, activation_record_id: str) -> ArtifactContent:
        row = conn.execute("SELECT v.artifact_id FROM validity_heads h JOIN validities v "
                           "ON v.validity_record_id=h.validity_record_id "
                           "WHERE h.activation_record_id=?", (activation_record_id,)).fetchone()
        if row is None:
            raise ControlPlaneOperationError("activation_lineage_unavailable")
        return DeviceFingerprintControlPlaneStore._load(conn, row[0])

    def transition_validity(self, new_validity_record: ArtifactContent, *,
                            expected_head_validity_record_id: str) -> ArtifactContent:
        self._validated(new_validity_record)
        if new_validity_record.artifact_type != "RuntimeProfileValidityRecord":
            raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
        vp = new_validity_record.semantic_payload
        if (vp["previous_validity_record_id"] != expected_head_validity_record_id
                or vp["state"] != "SUSPENDED_INVALIDATED"):
            raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT validity_record_id FROM validity_heads WHERE activation_record_id=?",
                               (vp["activation_record_id"],)).fetchone()
            if row is None or row[0] != expected_head_validity_record_id:
                raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
            previous = self._head(conn, vp["activation_record_id"]).semantic_payload
            if (vp["profile_kind"], vp["runtime_profile_id"], vp["runtime_profile_digest"]) != (
                    previous["profile_kind"], previous["runtime_profile_id"], previous["runtime_profile_digest"]):
                raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
            self._put(conn, new_validity_record)
            self._insert_validity(conn, new_validity_record)
            changed = conn.execute("UPDATE validity_heads SET validity_record_id=? WHERE activation_record_id=? "
                                   "AND validity_record_id=?", (vp["validity_record_id"], vp["activation_record_id"],
                                                                expected_head_validity_record_id)).rowcount
            if changed != 1:
                raise ControlPlaneOperationError("runtime_profile_validity_cas_conflict")
            conn.commit()
            return new_validity_record
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _resolve_pin(conn: sqlite3.Connection, pointer: ActiveProfilePointerV1) -> PinnedRuntimeProfile:
        try:
            row = conn.execute("SELECT * FROM activations WHERE activation_record_id=?",
                               (pointer.activation_record_id,)).fetchone()
            if row is None or (row["profile_kind"], row["runtime_profile_id"],
                               row["runtime_profile_digest"], row["activation_generation_id"]) != (
                                   pointer.profile_kind, pointer.runtime_profile_id,
                                   pointer.runtime_profile_digest, pointer.activation_generation_id):
                raise ValueError("activation index mismatch")
            activation = DeviceFingerprintControlPlaneStore._load(conn, row["artifact_id"])
            if activation.artifact_type != "RuntimeProfileActivationRecord":
                raise ValueError("activation artifact type mismatch")
            ap = activation.semantic_payload
            if (ap["activation_record_id"], ap["activation_generation_id"], ap["profile_kind"],
                    ap["runtime_profile_id"], ap["runtime_profile_digest"]) != (
                        pointer.activation_record_id, pointer.activation_generation_id, pointer.profile_kind,
                        pointer.runtime_profile_id, pointer.runtime_profile_digest):
                raise ValueError("activation mismatch")
            rpm = DeviceFingerprintControlPlaneStore._load(conn, ap["runtime_profile_admission_manifest_id"],
                                                            ap["runtime_profile_admission_manifest_digest"])
            if rpm.artifact_type != "RuntimeProfileAdmissionManifest":
                raise ValueError("admission artifact type mismatch")
            rp = rpm.semantic_payload
            if (rp["candidate_profile"], rp["profile_kind"], rp["update_class"]) != (
                    {"artifact_id": pointer.runtime_profile_id,
                     "content_sha256": pointer.runtime_profile_digest}, pointer.profile_kind,
                    ap["activation_reason_update_class"]):
                raise ValueError("admission mismatch")
            profile = DeviceFingerprintControlPlaneStore._load(conn, pointer.runtime_profile_id,
                                                                pointer.runtime_profile_digest)
            expected_type = ("FoundationRuntimeProfile" if pointer.profile_kind == "foundation"
                             else "ClassificationRuntimeProfile" if pointer.profile_kind == "classification"
                             else None)
            if profile.artifact_type != expected_type:
                raise ValueError("runtime profile artifact type mismatch")
            DeviceFingerprintControlPlaneStore._closure(conn, rpm)
            DeviceFingerprintControlPlaneStore._closure(conn, profile)
            validity = DeviceFingerprintControlPlaneStore._head(conn, pointer.activation_record_id)
            if validity.artifact_type != "RuntimeProfileValidityRecord":
                raise ValueError("validity artifact type mismatch")
            vp = validity.semantic_payload
            if (vp["activation_record_id"], vp["profile_kind"], vp["runtime_profile_id"],
                    vp["runtime_profile_digest"]) != (
                        pointer.activation_record_id, pointer.profile_kind,
                        pointer.runtime_profile_id, pointer.runtime_profile_digest):
                raise ValueError("validity mismatch")
            if vp["state"] == "INACTIVE":
                raise ValueError("active pointer has inactive validity head")
            return PinnedRuntimeProfile(pointer, profile, rpm, activation, validity)
        except (ControlPlaneOperationError, DeviceFingerprintValidationError,
                KeyError, TypeError, ValueError) as exc:
            raise ControlPlaneOperationError("activation_lineage_unavailable") from exc

    def pin_active_profile(self, profile_kind: str) -> PinnedRuntimeProfile:
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            pointer = self._pointer(conn, profile_kind)
            if pointer is None:
                raise ControlPlaneOperationError("activation_lineage_unavailable")
            pinned = self._resolve_pin(conn, pointer)
            if pinned.validity_record.semantic_payload["inflight_commit_rule"] != "ALLOW_PINNED_INFLIGHT":
                raise ControlPlaneOperationError("runtime_profile_invalidated")
            conn.commit()
            return pinned
        finally:
            conn.close()

    def check_pinned_commit_allowed(self, pinned: PinnedRuntimeProfile) -> bool:
        if not isinstance(pinned, PinnedRuntimeProfile):
            raise ControlPlaneOperationError("runtime_profile_invalidated")
        with self._connect() as conn:
            try:
                head = self._head(conn, pinned.pointer.activation_record_id)
                state = head.semantic_payload
                if (state["activation_record_id"] != pinned.pointer.activation_record_id or
                        state["runtime_profile_id"] != pinned.pointer.runtime_profile_id or
                        state["runtime_profile_digest"] != pinned.pointer.runtime_profile_digest or
                        state["inflight_commit_rule"] != "ALLOW_PINNED_INFLIGHT" or
                        state["state"] == "SUSPENDED_INVALIDATED"):
                    raise ControlPlaneOperationError("runtime_profile_invalidated")
                return True
            except ControlPlaneOperationError as exc:
                raise ControlPlaneOperationError("runtime_profile_invalidated") from exc

    def validate_startup_integrity(self) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            for row in conn.execute("SELECT * FROM active_pointers ORDER BY profile_kind"):
                self._resolve_pin(conn, ActiveProfilePointerV1(**dict(row)))
            conn.commit()
        except Exception as exc:
            raise ControlPlaneOperationError("activation_lineage_unavailable") from exc
        finally:
            conn.close()
