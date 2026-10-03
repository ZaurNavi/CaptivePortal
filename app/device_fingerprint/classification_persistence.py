"""Dedicated, atomic Task-04 classification audit storage and Level-B replay."""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .artifact_content import ArtifactContent, ArtifactRef
from .artifact_dependency_graph import ArtifactDependencyGraphError, extract_direct_artifact_refs
from .classification_request import make_classification_request_manifest
from .classification_retention_policy import (
    build_initial_classification_retention_policy_v1, make_classification_retention_policy,
)
from .control_plane_store import ControlPlaneOperationError, DeviceFingerprintControlPlaneStore
from .fusion import FusionInputs, fuse_classification
from .models import DeviceFingerprintValidationError
from .request_assembly import DeviceFingerprintRequestAssembly, RequestAssemblyResult
from .runtime_profile_artifacts import (
    make_classification_runtime_profile, make_runtime_profile_admission_manifest,
)
from .validation import format_utc, parse_utc


class ClassificationPersistenceError(RuntimeError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ClassificationCoreRecord:
    classification_id: str
    site_id: str
    observed_mac: str
    classified_at_utc: str
    execution_context: str
    classification_runtime_profile_id: str
    classification_runtime_profile_digest: str
    foundation_runtime_profile_id: str
    foundation_runtime_profile_digest: str
    runtime_profile_activation_record_id: str | None
    classification_request_manifest_id: str
    classification_request_manifest_digest: str
    classification_result_id: str
    classification_result_digest: str
    snapshot_record_id: str
    snapshot_record_digest: str
    classification_retention_policy_id: str
    classification_retention_policy_digest: str


_CORE_FIELDS = tuple(field.name for field in fields(ClassificationCoreRecord))


class DeviceFingerprintClassificationStore:
    def __init__(
        self, classification_database_path: str | Path, task01_database_path: str | Path,
        *, control_plane_store: DeviceFingerprintControlPlaneStore,
        utc_clock: Callable[[], str] = lambda: format_utc(datetime.now(timezone.utc)),
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        fault_hook: Callable[[str], None] | None = None,
    ) -> None:
        classification = Path(classification_database_path).resolve(strict=False)
        task01 = Path(task01_database_path).resolve(strict=False)
        if (os.path.normcase(str(classification)) == os.path.normcase(str(task01))
                or (classification.exists() and task01.exists()
                    and os.path.samefile(classification, task01))):
            raise ClassificationPersistenceError("persistence_unavailable")
        self.database_path = classification
        self._control = control_plane_store
        self._clock = utc_clock
        self._uuid_factory = uuid_factory
        self._fault = fault_hook

    def _connect(self) -> sqlite3.Connection:
        conn = None
        try:
            conn = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            return conn
        except sqlite3.Error as exc:
            if conn is not None:
                conn.close()
            raise ClassificationPersistenceError("persistence_unavailable") from exc

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    semantic_payload_json BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifact_dependencies (
                    owner_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                    dependency_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                    dependency_digest TEXT NOT NULL,
                    PRIMARY KEY (owner_id, dependency_id)
                );
                CREATE TABLE IF NOT EXISTS classifications (
                    classification_id TEXT PRIMARY KEY,
                    site_id TEXT NOT NULL, observed_mac TEXT NOT NULL,
                    classified_at_utc TEXT NOT NULL, execution_context TEXT NOT NULL,
                    classification_runtime_profile_id TEXT NOT NULL,
                    classification_runtime_profile_digest TEXT NOT NULL,
                    foundation_runtime_profile_id TEXT NOT NULL,
                    foundation_runtime_profile_digest TEXT NOT NULL,
                    runtime_profile_activation_record_id TEXT,
                    classification_request_manifest_id TEXT NOT NULL,
                    classification_request_manifest_digest TEXT NOT NULL,
                    classification_result_id TEXT NOT NULL,
                    classification_result_digest TEXT NOT NULL,
                    snapshot_record_id TEXT NOT NULL,
                    snapshot_record_digest TEXT NOT NULL,
                    classification_retention_policy_id TEXT NOT NULL,
                    classification_retention_policy_digest TEXT NOT NULL,
                    CHECK ((execution_context='PRODUCTION' AND runtime_profile_activation_record_id IS NOT NULL)
                        OR (execution_context='PRE_ACCEPTANCE_CANDIDATE'
                            AND runtime_profile_activation_record_id IS NULL))
                );
                CREATE TABLE IF NOT EXISTS classification_roots (
                    classification_id TEXT NOT NULL REFERENCES classifications(classification_id)
                        ON DELETE CASCADE,
                    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                    content_sha256 TEXT NOT NULL,
                    PRIMARY KEY (classification_id, artifact_id)
                );
                CREATE INDEX IF NOT EXISTS idx_classifications_device_history_v1
                ON classifications(site_id, observed_mac, classified_at_utc, classification_id);
            """)

    @staticmethod
    def _ref(content: ArtifactContent) -> ArtifactRef:
        return ArtifactRef(content.artifact_id, content.content_sha256)

    def _collect_closure(
        self, seeds: list[ArtifactContent],
    ) -> dict[str, ArtifactContent]:
        """Recursively retain every dependency needed by exact runtime replay."""
        reason = "persistence_unavailable"
        contents: dict[str, ArtifactContent] = {}
        try:
            for content in seeds:
                if not isinstance(content, ArtifactContent):
                    raise ClassificationPersistenceError(reason)
                old = contents.get(content.artifact_id)
                if old is not None and old != content:
                    raise ClassificationPersistenceError(reason)
                contents[content.artifact_id] = content
            pending = list(contents.values())
            while pending:
                content = pending.pop()
                for reference in extract_direct_artifact_refs(content):
                    dependent = contents.get(reference.artifact_id)
                    if dependent is None:
                        dependent = self._control.load_artifact(
                            reference.artifact_id, reference.content_sha256)
                        contents[dependent.artifact_id] = dependent
                        pending.append(dependent)
                    reference.resolve(dependent, dependent.artifact_type)
            return contents
        except ClassificationPersistenceError:
            raise
        except (ControlPlaneOperationError, sqlite3.Error, ArtifactDependencyGraphError,
                DeviceFingerprintValidationError, KeyError, TypeError, ValueError) as exc:
            raise ClassificationPersistenceError(reason) from exc

    def _collect_admission_closure(
        self, assembly: RequestAssemblyResult,
        foundation_admission: ArtifactContent | None,
    ) -> tuple[dict[str, ArtifactContent], dict[str, tuple[ArtifactRef, ...]]]:
        """Retain the bounded §120 admission lineage, not historical gate inputs."""
        reason = "activation_lineage_unavailable"
        contents: dict[str, ArtifactContent] = {}
        edges: dict[str, tuple[ArtifactRef, ...]] = {}

        def retain(content: ArtifactContent, kind: str) -> ArtifactContent:
            if not isinstance(content, ArtifactContent) or content.artifact_type != kind:
                raise ClassificationPersistenceError(reason)
            stored = self._control.load_artifact(content.artifact_id, content.content_sha256)
            if stored != content:
                raise ClassificationPersistenceError(reason)
            previous = contents.get(content.artifact_id)
            if previous is not None and previous != content:
                raise ClassificationPersistenceError(reason)
            contents[content.artifact_id] = content
            return content

        def follow(owner: ArtifactContent, value: dict[str, str], kind: str) -> ArtifactContent:
            reference = ArtifactRef.from_dict(value)
            if not reference.artifact_id.startswith(f"{kind}:v1:sha256:"):
                raise ClassificationPersistenceError(reason)
            target = self._control.load_artifact(reference.artifact_id,
                                                 reference.content_sha256)
            reference.resolve(target, kind)
            retain(target, kind)
            edges[owner.artifact_id] = (*edges.get(owner.artifact_id, ()), reference)
            return target

        def foundation_rpm(rpm: ArtifactContent) -> ArtifactContent:
            retain(rpm, "RuntimeProfileAdmissionManifest")
            payload = rpm.semantic_payload
            if (make_runtime_profile_admission_manifest(payload) != rpm
                    or payload["profile_kind"] != "foundation"
                    or payload["candidate_profile"] != self._ref(
                        assembly.foundation_runtime_profile).as_dict()):
                raise ClassificationPersistenceError(reason)
            follow(rpm, payload["candidate_profile"], "FoundationRuntimeProfile")
            manifest = follow(rpm, payload["foundation_admission_manifest"],
                              "FoundationAdmissionManifest")
            # The manifest is retained exactly. Its gate results are historical
            # identities, not a recursively retained classification dependency.
            edges.setdefault(manifest.artifact_id, ())
            return manifest

        try:
            if assembly.execution_context == "PRE_ACCEPTANCE_CANDIDATE":
                foundation_rpm(foundation_admission)
            else:
                pinned = assembly.pinned_runtime_profile
                activation = retain(pinned.activation_record, "RuntimeProfileActivationRecord")
                rpm = retain(pinned.admission_manifest, "RuntimeProfileAdmissionManifest")
                payload = rpm.semantic_payload
                if (make_runtime_profile_admission_manifest(payload) != rpm
                        or payload["profile_kind"] != "classification"
                        or payload["candidate_profile"] != self._ref(
                            assembly.classification_runtime_profile).as_dict()):
                    raise ClassificationPersistenceError(reason)
                activation_payload = activation.semantic_payload
                if (activation_payload["runtime_profile_id"] !=
                        assembly.classification_runtime_profile.artifact_id
                        or activation_payload["runtime_profile_digest"] !=
                        assembly.classification_runtime_profile.content_sha256
                        or activation_payload["runtime_profile_admission_manifest_id"] != rpm.artifact_id
                        or activation_payload["runtime_profile_admission_manifest_digest"] !=
                        rpm.content_sha256):
                    raise ClassificationPersistenceError(reason)
                follow(activation, {
                    "artifact_id": activation_payload["runtime_profile_id"],
                    "content_sha256": activation_payload["runtime_profile_digest"],
                }, "ClassificationRuntimeProfile")
                follow(activation, {
                    "artifact_id": activation_payload["runtime_profile_admission_manifest_id"],
                    "content_sha256": activation_payload["runtime_profile_admission_manifest_digest"],
                }, "RuntimeProfileAdmissionManifest")
                follow(rpm, payload["candidate_profile"], "ClassificationRuntimeProfile")
                foundation_manifest = follow(rpm, payload["foundation_admission_manifest"],
                                             "FoundationAdmissionManifest")
                foundation_ref = payload["foundation_runtime_profile_admission_manifest"]
                if foundation_ref is None:
                    raise ClassificationPersistenceError(reason)
                admitted_foundation = follow(rpm, foundation_ref,
                                             "RuntimeProfileAdmissionManifest")
                if foundation_rpm(admitted_foundation) != foundation_manifest:
                    raise ClassificationPersistenceError(reason)
                acceptance_ref = payload["task04_acceptance_manifest"]
                if acceptance_ref is None:
                    raise ClassificationPersistenceError(reason)
                acceptance = follow(rpm, acceptance_ref, "Task04AcceptanceManifest")
                accepted = acceptance.semantic_payload
                for field, content in (
                    ("tested_classification_runtime_profile",
                     assembly.classification_runtime_profile),
                    ("classifier_artifact_manifest", assembly.classifier_artifact_manifest),
                    ("foundation_admission_manifest", foundation_manifest),
                ):
                    if accepted[field] != self._ref(content).as_dict():
                        raise ClassificationPersistenceError(reason)
                    follow(acceptance, accepted[field], content.artifact_type)
                # Pre-acceptance gate results, like RPM prerequisites, remain
                # immutable bytes in the manifest but are not traversal edges.
            return contents, edges
        except ClassificationPersistenceError:
            raise
        except (ControlPlaneOperationError, sqlite3.Error, ArtifactDependencyGraphError,
                DeviceFingerprintValidationError, KeyError, TypeError, ValueError,
                AttributeError) as exc:
            raise ClassificationPersistenceError(reason) from exc

    def _roots(
        self, assembly: RequestAssemblyResult, retention_policy: ArtifactContent,
        pre_acceptance_foundation_runtime_profile_admission_manifest: ArtifactContent | None,
    ) -> tuple[dict[str, ArtifactContent], dict[str, tuple[ArtifactRef, ...]]]:
        semantic_seeds = [
            assembly.evidence_snapshot_content, assembly.snapshot_record,
            assembly.source_evaluability, *assembly.origin_assessments,
            assembly.classification_request_manifest, assembly.classification_result,
            assembly.foundation_runtime_profile, assembly.classification_runtime_profile,
            assembly.knowledge_bundle, assembly.classification_policy,
            assembly.evidence_adapter_contract_set, assembly.classifier_artifact_manifest,
            retention_policy, *(getattr(assembly.knowledge_candidate, field.name)
                                for field in fields(assembly.knowledge_candidate)),
        ]
        # The runtime/replay graph stays fully recursive. Admission/governance
        # lineage has a separate, explicit and bounded retention boundary.
        contents, edges = self._collect_admission_closure(
            assembly, pre_acceptance_foundation_runtime_profile_admission_manifest)
        semantic = self._collect_closure(semantic_seeds)
        for artifact_id, content in semantic.items():
            old = contents.get(artifact_id)
            if old is not None and old != content:
                raise ClassificationPersistenceError("activation_lineage_unavailable")
            contents[artifact_id] = content
            if artifact_id not in edges:
                edges[artifact_id] = extract_direct_artifact_refs(content)
        # A Foundation manifest can name current semantic artifacts as well as
        # historical gates. Only already-retained runtime artifacts gain edges.
        for content in contents.values():
            if content.artifact_type == "FoundationAdmissionManifest":
                try:
                    current = []
                    opaque = {ArtifactRef.from_dict(value).artifact_id for value in
                              content.semantic_payload.get("pre_admission_gate_result_manifests", [])}
                    for reference in extract_direct_artifact_refs(content):
                        if reference.artifact_id in opaque:
                            continue
                        target = semantic.get(reference.artifact_id)
                        if target is not None:
                            reference.resolve(target, target.artifact_type)
                            current.append(reference)
                    edges[content.artifact_id] = tuple(current)
                except (ArtifactDependencyGraphError, DeviceFingerprintValidationError,
                        KeyError, TypeError, ValueError) as exc:
                    raise ClassificationPersistenceError("activation_lineage_unavailable") from exc
        return contents, edges

    def _validate_assembly(self, assembly: RequestAssemblyResult,
                           retention_policy: ArtifactContent,
                           pre_acceptance_foundation_runtime_profile_admission_manifest: ArtifactContent | None,
                           ) -> None:
        if not isinstance(assembly, RequestAssemblyResult):
            raise ClassificationPersistenceError("persistence_unavailable")
        profile = assembly.classification_runtime_profile
        if (make_classification_runtime_profile(profile.semantic_payload) != profile
                or profile.semantic_payload["foundation_runtime_profile"] !=
                DeviceFingerprintClassificationStore._ref(
                    assembly.foundation_runtime_profile).as_dict()):
            raise ClassificationPersistenceError("persistence_unavailable")
        if retention_policy != build_initial_classification_retention_policy_v1():
            raise ClassificationPersistenceError("persistence_unavailable")
        if assembly.execution_context == "PRODUCTION":
            if pre_acceptance_foundation_runtime_profile_admission_manifest is not None:
                raise ClassificationPersistenceError("persistence_unavailable")
            pinned = assembly.pinned_runtime_profile
            if (pinned is None or assembly.runtime_profile_activation_record is None
                    or pinned.runtime_profile != profile
                    or pinned.activation_record != assembly.runtime_profile_activation_record):
                raise ClassificationPersistenceError("production_profile_not_admitted")
            admission = pinned.admission_manifest
            if not isinstance(admission, ArtifactContent):
                raise ClassificationPersistenceError("production_profile_not_admitted")
            ap = admission.semantic_payload
            if (admission.artifact_type != "RuntimeProfileAdmissionManifest"
                    or ap.get("profile_kind") != "classification"
                    or ap.get("candidate_profile") != DeviceFingerprintClassificationStore._ref(profile).as_dict()
                    or ap.get("task04_acceptance_manifest") is None
                    or ap.get("foundation_runtime_profile_admission_manifest") is None):
                raise ClassificationPersistenceError("production_profile_not_admitted")
            try:
                if make_runtime_profile_admission_manifest(ap) != admission:
                    raise ClassificationPersistenceError("activation_lineage_unavailable")
            except DeviceFingerprintValidationError as exc:
                raise ClassificationPersistenceError("activation_lineage_unavailable") from exc
            try:
                stored_admission = self._control.load_artifact(
                    admission.artifact_id, admission.content_sha256)
            except (ControlPlaneOperationError, sqlite3.Error, LookupError) as exc:
                raise ClassificationPersistenceError("activation_lineage_unavailable") from exc
            try:
                stored_activation = self._control.load_artifact(
                    pinned.activation_record.artifact_id,
                    pinned.activation_record.content_sha256)
            except (ControlPlaneOperationError, sqlite3.Error, LookupError) as exc:
                raise ClassificationPersistenceError("activation_lineage_unavailable") from exc
            if stored_admission != admission:
                raise ClassificationPersistenceError("activation_lineage_unavailable")
            if (stored_activation != pinned.activation_record
                    or pinned.activation_record.semantic_payload.get("activation_record_id") !=
                    pinned.pointer.activation_record_id
                    or pinned.activation_record.semantic_payload.get(
                        "runtime_profile_admission_manifest_id") != admission.artifact_id):
                raise ClassificationPersistenceError("activation_lineage_unavailable")
        elif assembly.execution_context == "PRE_ACCEPTANCE_CANDIDATE":
            if assembly.pinned_runtime_profile is not None or assembly.runtime_profile_activation_record is not None:
                raise ClassificationPersistenceError("persistence_unavailable")
            foundation_admission = pre_acceptance_foundation_runtime_profile_admission_manifest
            try:
                if (not isinstance(foundation_admission, ArtifactContent)
                        or foundation_admission.artifact_type != "RuntimeProfileAdmissionManifest"
                        or make_runtime_profile_admission_manifest(
                            foundation_admission.semantic_payload) != foundation_admission
                        or foundation_admission.semantic_payload["profile_kind"] != "foundation"
                        or foundation_admission.semantic_payload["candidate_profile"] !=
                        self._ref(assembly.foundation_runtime_profile).as_dict()
                        or self._control.load_artifact(
                            foundation_admission.artifact_id,
                            foundation_admission.content_sha256) != foundation_admission):
                    raise ClassificationPersistenceError("activation_lineage_unavailable")
            except (ControlPlaneOperationError, sqlite3.Error, DeviceFingerprintValidationError,
                    KeyError, TypeError, ValueError) as exc:
                raise ClassificationPersistenceError("activation_lineage_unavailable") from exc
        else:
            raise ClassificationPersistenceError("persistence_unavailable")
        if assembly.evidence_snapshot_materialization is None:
            raise ClassificationPersistenceError("persistence_unavailable")
        if assembly.snapshot_record.semantic_payload.get("evidence_snapshot_content") != (
                DeviceFingerprintClassificationStore._ref(assembly.evidence_snapshot_content).as_dict()):
            raise ClassificationPersistenceError("persistence_unavailable")
        if assembly.classification_result.semantic_payload.get("classification_request_digest") != (
                assembly.classification_request_manifest.content_sha256):
            raise ClassificationPersistenceError("persistence_unavailable")
        request = assembly.classification_request_manifest
        verified = make_classification_request_manifest(
            request.semantic_payload,
            evidence_snapshot_content=assembly.evidence_snapshot_content,
            source_evaluability=assembly.source_evaluability,
            knowledge_bundle=assembly.knowledge_bundle,
            classification_policy=assembly.classification_policy,
            evidence_adapter_contract_set=assembly.evidence_adapter_contract_set,
            classifier_artifact_manifest=assembly.classifier_artifact_manifest)
        if verified != request or request.semantic_payload["knowledge_evaluation_at_utc"] != (
                assembly.knowledge_evaluation_at_utc):
            raise ClassificationPersistenceError("persistence_unavailable")
        replayed = fuse_classification(FusionInputs(
            request.content_sha256, assembly.classification_policy,
            assembly.knowledge_candidate.classification_taxonomy,
            assembly.knowledge_candidate.alias_mapping,
            assembly.evidence_adapter_contract_set, assembly.knowledge_bundle,
            assembly.knowledge_candidate, assembly.classifier_artifact_manifest,
            assembly.evidence_snapshot_content, assembly.source_evaluability,
            assembly.origin_assessments))
        if replayed != assembly.classification_result:
            raise ClassificationPersistenceError("persistence_unavailable")

    def persist(
        self, assembly: RequestAssemblyResult, *, retention_policy: ArtifactContent,
        pre_acceptance_foundation_runtime_profile_admission_manifest: ArtifactContent | None = None,
        classification_id: str | None = None,
    ) -> ClassificationCoreRecord:
        """Commit whole closure + edges + core, or nothing; never touch Task-01."""
        try:
            self._validate_assembly(
                assembly, retention_policy,
                pre_acceptance_foundation_runtime_profile_admission_manifest)
        except ClassificationPersistenceError:
            raise
        except (DeviceFingerprintValidationError, KeyError, TypeError, AttributeError) as exc:
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        try:
            contents, edges = self._roots(
                assembly, retention_policy,
                pre_acceptance_foundation_runtime_profile_admission_manifest)
        except (ArtifactDependencyGraphError, DeviceFingerprintValidationError,
                KeyError, TypeError) as exc:
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        try:
            classification_id = (str(self._uuid_factory()) if classification_id is None
                                 else classification_id)
            if not isinstance(classification_id, str):
                raise ClassificationPersistenceError("persistence_unavailable")
            if (str(uuid.UUID(classification_id)) != classification_id
                    or uuid.UUID(classification_id).version != 4):
                raise ClassificationPersistenceError("persistence_unavailable")
            classified_at = self._clock()
            parse_utc(classified_at)
        except (ValueError, TypeError, DeviceFingerprintValidationError) as exc:
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        snapshot = assembly.evidence_snapshot_content.semantic_payload
        activation_id = (assembly.pinned_runtime_profile.pointer.activation_record_id
                         if assembly.pinned_runtime_profile is not None else None)
        core = ClassificationCoreRecord(
            classification_id, snapshot["site_id"], snapshot["observed_mac"], classified_at,
            assembly.execution_context,
            assembly.classification_runtime_profile.artifact_id,
            assembly.classification_runtime_profile.content_sha256,
            assembly.foundation_runtime_profile.artifact_id,
            assembly.foundation_runtime_profile.content_sha256,
            activation_id, assembly.classification_request_manifest.artifact_id,
            assembly.classification_request_manifest.content_sha256,
            assembly.classification_result.artifact_id,
            assembly.classification_result.content_sha256,
            assembly.snapshot_record.artifact_id, assembly.snapshot_record.content_sha256,
            retention_policy.artifact_id, retention_policy.content_sha256,
        )
        try:
            conn = self._connect()
        except sqlite3.Error as exc:
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        try:
            conn.execute("BEGIN IMMEDIATE")
            for content in contents.values():
                old = conn.execute("SELECT content_sha256, semantic_payload_json FROM artifacts "
                                   "WHERE artifact_id=?", (content.artifact_id,)).fetchone()
                if old is not None and tuple(old) != (content.content_sha256, content.semantic_payload_json):
                    raise ClassificationPersistenceError("persistence_unavailable")
                conn.execute("INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?)", (
                    content.artifact_id, content.artifact_type, content.content_sha256,
                    content.semantic_payload_json))
            for content in contents.values():
                for reference in edges[content.artifact_id]:
                    target = contents[reference.artifact_id]
                    reference.resolve(target, target.artifact_type)
                    conn.execute("INSERT OR IGNORE INTO artifact_dependencies VALUES (?,?,?)", (
                        content.artifact_id, reference.artifact_id, reference.content_sha256))
            conn.execute(
                f"INSERT INTO classifications ({','.join(_CORE_FIELDS)}) "
                f"VALUES ({','.join('?' for _ in _CORE_FIELDS)})",
                tuple(getattr(core, name) for name in _CORE_FIELDS))
            for content in contents.values():
                conn.execute("INSERT INTO classification_roots VALUES (?,?,?)", (
                    classification_id, content.artifact_id, content.content_sha256))
            if self._fault is not None:
                self._fault("before_commit")
            if assembly.execution_context == "PRODUCTION":
                try:
                    lineage = self._control.capture_pinned_commit_lineage(
                        assembly.pinned_runtime_profile)
                except ControlPlaneOperationError as exc:
                    if exc.reason_code in ("activation_lineage_unavailable", "runtime_profile_invalidated"):
                        raise ClassificationPersistenceError(exc.reason_code) from exc
                    raise ClassificationPersistenceError("activation_lineage_unavailable") from exc
                previous = None
                for validity in lineage:
                    if validity.artifact_type != "RuntimeProfileValidityRecord":
                        raise ClassificationPersistenceError("activation_lineage_unavailable")
                    old = conn.execute("SELECT content_sha256, semantic_payload_json FROM artifacts "
                                       "WHERE artifact_id=?", (validity.artifact_id,)).fetchone()
                    if old is not None and tuple(old) != (validity.content_sha256,
                                                          validity.semantic_payload_json):
                        raise ClassificationPersistenceError("persistence_unavailable")
                    conn.execute("INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?)", (
                        validity.artifact_id, validity.artifact_type, validity.content_sha256,
                        validity.semantic_payload_json))
                    for reference in extract_direct_artifact_refs(validity):
                        target = contents.get(reference.artifact_id)
                        if target is None:
                            raise ClassificationPersistenceError("activation_lineage_unavailable")
                        reference.resolve(target, target.artifact_type)
                        conn.execute("INSERT OR IGNORE INTO artifact_dependencies VALUES (?,?,?)", (
                            validity.artifact_id, reference.artifact_id, reference.content_sha256))
                    if previous is not None:
                        conn.execute("INSERT OR IGNORE INTO artifact_dependencies VALUES (?,?,?)", (
                            validity.artifact_id, previous.artifact_id, previous.content_sha256))
                    conn.execute("INSERT INTO classification_roots VALUES (?,?,?)", (
                        classification_id, validity.artifact_id, validity.content_sha256))
                    previous = validity
            conn.commit()
            return core
        except Exception as exc:
            if conn.in_transaction:
                conn.rollback()
            if isinstance(exc, ClassificationPersistenceError):
                raise
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        finally:
            conn.close()

    @staticmethod
    def _load(conn: sqlite3.Connection, reference: ArtifactRef) -> ArtifactContent:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (reference.artifact_id,)).fetchone()
        if row is None:
            raise ClassificationPersistenceError("persistence_unavailable")
        content = ArtifactContent(row["artifact_type"], 1, row["semantic_payload_json"],
                                  row["content_sha256"], row["artifact_id"])
        reference.resolve(content, content.artifact_type)
        return content

    def load_artifact(self, artifact_id: str, content_sha256: str) -> ArtifactContent:
        with self._connect() as conn:
            return self._load(conn, ArtifactRef(artifact_id, content_sha256))

    def load_core(self, classification_id: str) -> ClassificationCoreRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM classifications WHERE classification_id=?",
                               (classification_id,)).fetchone()
            if row is None:
                raise ClassificationPersistenceError("persistence_unavailable")
            return ClassificationCoreRecord(**dict(row))

    def replay_level_b(self, classification_id: str) -> ArtifactContent:
        """Verify the retained semantic result without Task-01 or a current clock."""
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM classifications WHERE classification_id=?",
                                   (classification_id,)).fetchone()
                if row is None:
                    raise ClassificationPersistenceError("persistence_unavailable")
                core = ClassificationCoreRecord(**dict(row))

                def load(value: dict[str, str]) -> ArtifactContent:
                    return self._load(conn, ArtifactRef.from_dict(value))

                profile = self._load(conn, ArtifactRef(
                    core.classification_runtime_profile_id,
                    core.classification_runtime_profile_digest))
                foundation = self._load(conn, ArtifactRef(
                    core.foundation_runtime_profile_id, core.foundation_runtime_profile_digest))
                if (make_classification_runtime_profile(profile.semantic_payload) != profile
                        or profile.semantic_payload["foundation_runtime_profile"] !=
                        self._ref(foundation).as_dict()):
                    raise ClassificationPersistenceError("replay_mismatch")
                request = self._load(conn, ArtifactRef(
                    core.classification_request_manifest_id, core.classification_request_manifest_digest))
                rp = request.semantic_payload
                named = {name: load(rp[name]) for name in (
                    "evidence_snapshot_content", "source_evaluability", "knowledge_bundle",
                    "classification_policy", "evidence_adapter_contract_set",
                    "classifier_artifact_manifest")}
                if make_classification_request_manifest(rp, **named) != request:
                    raise ClassificationPersistenceError("replay_mismatch")
                snapshot_record = self._load(conn, ArtifactRef(
                    core.snapshot_record_id, core.snapshot_record_digest))
                if snapshot_record.semantic_payload.get("evidence_snapshot_content") != (
                        self._ref(named["evidence_snapshot_content"]).as_dict()):
                    raise ClassificationPersistenceError("replay_mismatch")
                knowledge = DeviceFingerprintRequestAssembly.reconstruct_knowledge_bundle(
                    named["knowledge_bundle"], lambda ref: self._load(conn, ref))
                persisted = self._load(conn, ArtifactRef(
                    core.classification_result_id, core.classification_result_digest))
                origins = tuple(load(ref) for ref in persisted.semantic_payload["origin_assessments"])
                replayed = fuse_classification(FusionInputs(
                    request.content_sha256, named["classification_policy"],
                    knowledge.classification_taxonomy, knowledge.alias_mapping,
                    named["evidence_adapter_contract_set"], named["knowledge_bundle"],
                    knowledge, named["classifier_artifact_manifest"],
                    named["evidence_snapshot_content"], named["source_evaluability"], origins))
                if (replayed.artifact_id != persisted.artifact_id
                        or replayed.content_sha256 != persisted.content_sha256
                        or replayed.semantic_payload_json != persisted.semantic_payload_json):
                    raise ClassificationPersistenceError("replay_mismatch")
                return replayed
        except ClassificationPersistenceError:
            raise
        except (sqlite3.Error, DeviceFingerprintValidationError, KeyError, TypeError,
                ValueError, ControlPlaneOperationError) as exc:
            raise ClassificationPersistenceError("replay_mismatch") from exc

    def expire_and_gc(self, *, now_utc: str) -> int:
        """Delete eligible roots, then only artifacts unreferenced by any remaining root."""
        now = parse_utc(now_utc)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            expired = []
            for row in conn.execute("SELECT classification_id, classified_at_utc, "
                                    "classification_retention_policy_id, "
                                    "classification_retention_policy_digest FROM classifications"):
                policy = self._load(conn, ArtifactRef(
                    row["classification_retention_policy_id"],
                    row["classification_retention_policy_digest"]))
                payload = make_classification_retention_policy(policy.semantic_payload).semantic_payload
                if (payload["expiry_behavior"] == "DELETE_CLASSIFICATION_WHEN_ELIGIBLE"
                        and now >= parse_utc(row["classified_at_utc"]) + timedelta(
                            seconds=payload["classification_history_retention_seconds"])):
                    expired.append(row["classification_id"])
            for identifier in expired:
                conn.execute("DELETE FROM classifications WHERE classification_id=?", (identifier,))
            conn.execute("DELETE FROM artifact_dependencies WHERE owner_id NOT IN "
                         "(SELECT artifact_id FROM classification_roots)")
            conn.execute("DELETE FROM artifacts WHERE artifact_id NOT IN "
                         "(SELECT artifact_id FROM classification_roots)")
            conn.commit()
            return len(expired)
        except Exception as exc:
            if conn.in_transaction:
                conn.rollback()
            if isinstance(exc, ClassificationPersistenceError):
                raise
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        finally:
            conn.close()
