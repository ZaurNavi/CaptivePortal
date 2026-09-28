"""Pin-once Task-04 RequestAssembly; operational lineage stays outside the request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Callable

from .artifact_content import ArtifactContent, ArtifactRef
from .classification_request import make_classification_request_manifest
from .control_plane_store import (
    ControlPlaneOperationError, DeviceFingerprintControlPlaneStore, PinnedRuntimeProfile,
)
from .fe5_external_knowledge import evaluate_external_knowledge_freshness
from .fusion import FusionInputs, fuse_classification
from .knowledge_bundle import (
    KnowledgeBundleCandidate, make_knowledge_bundle, validate_knowledge_bundle_dependencies,
)
from .models import DeviceFingerprintValidationError
from .origin_assessment import DeviceFingerprintOriginAssessmentBuilder, OriginAssessmentInputs
from .snapshot_service import (
    DeviceFingerprintSnapshotService, EvidenceSnapshotMaterialization, SnapshotBuildResult,
)
from .source_evaluability import DeviceFingerprintSourceEvaluabilityBuilder
from .runtime_profile_artifacts import make_classification_runtime_profile, make_foundation_runtime_profile
from .validation import format_utc, parse_utc


class RequestAssemblyError(RuntimeError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def _knowledge_load_reason(exc: BaseException) -> str:
    """Only SQLite contention is a retryable knowledge-load failure."""
    if isinstance(exc, sqlite3.OperationalError):
        code = getattr(exc, "sqlite_errorcode", None)
        if (isinstance(code, int) and (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)):
            return "knowledge_bundle_unavailable"
        if str(exc).lower() in ("database is locked", "database is busy"):
            return "knowledge_bundle_unavailable"
    return "runtime_profile_incompatible"


@dataclass(frozen=True, slots=True)
class RequestAssemblyResult:
    execution_context: str
    classification_runtime_profile: ArtifactContent
    foundation_runtime_profile: ArtifactContent
    pinned_runtime_profile: PinnedRuntimeProfile | None
    runtime_profile_activation_record: ArtifactContent | None
    evidence_snapshot_content: ArtifactContent
    evidence_snapshot_materialization: EvidenceSnapshotMaterialization
    snapshot_record: ArtifactContent
    source_evaluability: ArtifactContent
    knowledge_bundle: ArtifactContent
    knowledge_candidate: KnowledgeBundleCandidate
    classification_policy: ArtifactContent
    evidence_adapter_contract_set: ArtifactContent
    classifier_artifact_manifest: ArtifactContent
    knowledge_evaluation_at_utc: str
    classification_request_manifest: ArtifactContent
    origin_assessments: tuple[ArtifactContent, ...]
    classification_result: ArtifactContent


class DeviceFingerprintRequestAssembly:
    """Production selects no profile from its caller; candidate mode is explicit."""

    def __init__(
        self, *, control_plane_store: DeviceFingerprintControlPlaneStore,
        read_service: object,
        compatibility_hook: Callable[..., bool] | None = None,
        utc_clock: Callable[[], str] = lambda: format_utc(datetime.now(timezone.utc)),
        process_memory_guard: Callable[[int], bool] | None = None,
    ) -> None:
        self._store = control_plane_store
        self._read_service = read_service
        self._compatibility_hook = compatibility_hook
        self._clock = utc_clock
        self._memory_guard = process_memory_guard

    def _resolve(self, reference: ArtifactRef) -> ArtifactContent:
        return self._store.load_artifact(reference.artifact_id, reference.content_sha256)

    def _dependency(self, value: dict[str, str], kind: str) -> ArtifactContent:
        reference = ArtifactRef.from_dict(value)
        if not reference.artifact_id.startswith(f"{kind}:v1:sha256:"):
            raise RequestAssemblyError("runtime_profile_incompatible")
        content = self._resolve(reference)
        reference.resolve(content, kind)
        return content

    @staticmethod
    def reconstruct_knowledge_bundle(
        bundle: ArtifactContent, resolver: Callable[[ArtifactRef], ArtifactContent],
    ) -> KnowledgeBundleCandidate:
        """Follow record-set provenance, never positional inventory assignment."""
        def dependency(value: dict[str, str], kind: str) -> ArtifactContent:
            reference = ArtifactRef.from_dict(value)
            if not reference.artifact_id.startswith(f"{kind}:v1:sha256:"):
                raise DeviceFingerprintValidationError("Wrong knowledge dependency type")
            content = resolver(reference)
            reference.resolve(content, kind)
            return content

        try:
            if make_knowledge_bundle(bundle.semantic_payload) != bundle:
                raise DeviceFingerprintValidationError("Noncanonical KnowledgeBundle")
            payload = bundle.semantic_payload
            taxonomy = dependency(payload["classification_taxonomy"], "ClassificationTaxonomy")
            aliases = dependency(payload["alias_mapping"], "AliasMapping")
            k3 = dependency(payload["k3_portal_rule_set"], "K3PortalRuleSet")
            records = {slot: dependency(payload[f"{slot}_record_set"],
                                              "CanonicalKnowledgeRecordSet")
                       for slot in ("k1", "k2b", "k4")}
            external = {}
            for slot, record_set in records.items():
                provenance = dependency(record_set.semantic_payload["knowledge_provenance"],
                                              "KnowledgeProvenanceManifest")
                provenance_payload = provenance.semantic_payload
                external[slot] = (
                    provenance,
                    dependency(provenance_payload["source_governance_record"],
                                     "SourceGovernanceRecord"),
                    dependency(provenance_payload["knowledge_freshness_policy"],
                                     "KnowledgeFreshnessPolicy"),
                )
            provenance_refs = payload["knowledge_provenance_manifests"]
            external_ids = {triple[0].artifact_id for triple in external.values()}
            internal_refs = [ref for ref in provenance_refs if ref["artifact_id"] not in external_ids]
            if len(internal_refs) != 1:
                raise DeviceFingerprintValidationError("K3 provenance is not unique")
            k3_provenance = dependency(internal_refs[0], "KnowledgeProvenanceManifest")
            candidate = KnowledgeBundleCandidate(
                classification_taxonomy=taxonomy, alias_mapping=aliases,
                k1_record_set=records["k1"], k1_provenance=external["k1"][0],
                k1_governance=external["k1"][1], k1_freshness_policy=external["k1"][2],
                k2b_record_set=records["k2b"], k2b_provenance=external["k2b"][0],
                k2b_governance=external["k2b"][1], k2b_freshness_policy=external["k2b"][2],
                k3_portal_rule_set=k3, k3_provenance=k3_provenance,
                k4_record_set=records["k4"], k4_provenance=external["k4"][0],
                k4_governance=external["k4"][1], k4_freshness_policy=external["k4"][2],
            )
            validate_knowledge_bundle_dependencies(bundle, candidate)
            return candidate
        except RequestAssemblyError:
            raise
        except (ControlPlaneOperationError, DeviceFingerprintValidationError,
                sqlite3.Error, KeyError, TypeError, AttributeError) as exc:
            raise RequestAssemblyError(_knowledge_load_reason(exc)) from exc

    def assemble_production(self, site_id: str, observed_mac: str,
                            window_start_utc: str, window_end_utc: str) -> RequestAssemblyResult:
        try:
            pinned = self._store.pin_active_profile("classification")
        except ControlPlaneOperationError as exc:
            raise RequestAssemblyError(exc.reason_code) from exc
        if not isinstance(pinned, PinnedRuntimeProfile):
            raise RequestAssemblyError("activation_lineage_unavailable")
        return self._assemble("PRODUCTION", pinned.runtime_profile, pinned, site_id,
                              observed_mac, window_start_utc, window_end_utc)

    def assemble_pre_acceptance_candidate(
        self, candidate_classification_runtime_profile: ArtifactContent,
        site_id: str, observed_mac: str, window_start_utc: str, window_end_utc: str,
    ) -> RequestAssemblyResult:
        """Acceptance-only exact candidate; no active pointer read or fake admission."""
        return self._assemble("PRE_ACCEPTANCE_CANDIDATE", candidate_classification_runtime_profile,
                              None, site_id, observed_mac, window_start_utc, window_end_utc)

    def _assemble(
        self, context: str, profile: ArtifactContent, pinned: PinnedRuntimeProfile | None,
        site_id: str, observed_mac: str, start: str, end: str,
    ) -> RequestAssemblyResult:
        try:
            if (profile.artifact_type != "ClassificationRuntimeProfile"
                    or make_classification_runtime_profile(profile.semantic_payload) != profile):
                raise RequestAssemblyError("runtime_profile_incompatible")
            p = profile.semantic_payload
            foundation = self._dependency(p["foundation_runtime_profile"], "FoundationRuntimeProfile")
            if make_foundation_runtime_profile(foundation.semantic_payload) != foundation:
                raise RequestAssemblyError("runtime_profile_incompatible")
            snapshot: SnapshotBuildResult = DeviceFingerprintSnapshotService(
                self._read_service, foundation_runtime_profile=foundation,
                artifact_resolver=self._resolve, utc_clock=self._clock,
                process_memory_guard=self._memory_guard,
            ).build(site_id, observed_mac, start, end)
            evaluability = DeviceFingerprintSourceEvaluabilityBuilder(
                foundation_runtime_profile=foundation, artifact_resolver=self._resolve,
            ).build(snapshot.evidence_snapshot_content)
            try:
                bundle = self._dependency(p["knowledge_bundle"], "KnowledgeBundle")
            except (ControlPlaneOperationError, DeviceFingerprintValidationError,
                    sqlite3.Error, KeyError, TypeError, AttributeError) as exc:
                raise RequestAssemblyError(_knowledge_load_reason(exc)) from exc
            knowledge = self.reconstruct_knowledge_bundle(bundle, self._resolve)
            policy = self._dependency(p["classification_policy"], "ClassificationPolicy")
            adapters = self._dependency(p["evidence_adapter_contract_set"], "EvidenceAdapterContractSet")
            classifier = self._dependency(p["classifier_artifact_manifest"], "ClassifierArtifactManifest")
            if self._compatibility_hook is None or not callable(self._compatibility_hook):
                raise RequestAssemblyError("runtime_profile_incompatible")
            try:
                compatible = self._compatibility_hook(
                    profile, foundation, bundle, knowledge, policy, adapters, classifier)
            except Exception as exc:
                raise RequestAssemblyError("runtime_profile_incompatible") from exc
            if compatible is not True:
                raise RequestAssemblyError("runtime_profile_incompatible")
            knowledge_time = self._clock()
            parse_utc(knowledge_time)
            for slot in ("k1", "k2b", "k4"):
                freshness = evaluate_external_knowledge_freshness(
                    getattr(knowledge, f"{slot}_provenance"),
                    getattr(knowledge, f"{slot}_freshness_policy"),
                    knowledge_evaluation_at_utc=knowledge_time)
                if freshness["failure_code"] == "negative_knowledge_age":
                    raise RequestAssemblyError("negative_knowledge_age")
            contents = {
                "evidence_snapshot_content": snapshot.evidence_snapshot_content,
                "source_evaluability": evaluability, "knowledge_bundle": bundle,
                "classification_policy": policy, "evidence_adapter_contract_set": adapters,
                "classifier_artifact_manifest": classifier,
            }
            request = make_classification_request_manifest({
                name: ArtifactRef(content.artifact_id, content.content_sha256).as_dict()
                for name, content in contents.items()
            } | {"knowledge_evaluation_at_utc": knowledge_time}, **contents)
            origins = DeviceFingerprintOriginAssessmentBuilder(OriginAssessmentInputs(
                snapshot.evidence_snapshot_content, snapshot.materialization,
                evaluability, adapters, bundle, knowledge, knowledge_time)).build_all()
            result = fuse_classification(FusionInputs(
                request.content_sha256, policy, knowledge.classification_taxonomy,
                knowledge.alias_mapping, adapters, bundle, knowledge, classifier,
                snapshot.evidence_snapshot_content, evaluability, origins))
            if result.semantic_payload["classification_request_digest"] != request.content_sha256:
                raise RequestAssemblyError("classifier_internal_error")
            return RequestAssemblyResult(
                context, profile, foundation, pinned,
                pinned.activation_record if pinned is not None else None,
                snapshot.evidence_snapshot_content, snapshot.materialization,
                snapshot.snapshot_record, evaluability, bundle, knowledge,
                policy, adapters, classifier, knowledge_time, request, origins, result)
        except RequestAssemblyError:
            raise
        except ControlPlaneOperationError as exc:
            reason = ("activation_lineage_unavailable" if exc.reason_code ==
                      "activation_lineage_unavailable" else "runtime_profile_incompatible")
            raise RequestAssemblyError(reason) from exc
        except (DeviceFingerprintValidationError, KeyError, TypeError, AttributeError) as exc:
            raise RequestAssemblyError("classifier_internal_error") from exc
