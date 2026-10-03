"""Dynamic admitted profile/source identity checks; no historical acceptance IDs."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import importlib
import inspect
import re
import sqlite3

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.control_plane_store import PinnedRuntimeProfile, ControlPlaneOperationError
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.runtime_profile_artifacts import (
    make_classification_runtime_profile, make_foundation_runtime_profile,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
)
from .models import IntegrationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def same_pin(left, right):
    return isinstance(left, PinnedRuntimeProfile) and isinstance(right, PinnedRuntimeProfile) and (
        left.pointer.activation_generation_id, left.pointer.activation_record_id,
        left.runtime_profile, left.admission_manifest) == (
        right.pointer.activation_generation_id, right.pointer.activation_record_id,
        right.runtime_profile, right.admission_manifest)


def load_reference(store, value, kind):
    ref = ArtifactRef.from_dict(value)
    content = store.load_artifact(ref.artifact_id, ref.content_sha256)
    ref.resolve(content, kind)
    return content


def verify_executable_identities(manifest, *, root=REPOSITORY_ROOT):
    """Validate source-backed entries, imported origin and exact on-disk bytes."""
    try:
        payload = manifest.semantic_payload
        entries = payload["adapter_implementation_identities"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("Missing executable identities")
        evidence = payload["evidence_canonical_json_compatibility_identity"]
        prefix = "EvidenceCanonicalJsonV1:"
        if not evidence.startswith(prefix):
            raise ValueError("Invalid evidence compatibility identity")
        identity, digest = evidence[len(prefix):].rsplit(":sha256:", 1)
        entries = entries + [{"implementation_id": identity, "implementation_digest": digest}]
        for entry in entries:
            prefix, relative, qualified = entry["implementation_id"].split(":", 2)
            digest = entry["implementation_digest"]
            path = PurePosixPath(relative)
            if (prefix != "python" or path.is_absolute() or ".." in path.parts
                    or not relative.startswith("app/") or path.suffix != ".py"
                    or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
                raise ValueError("Invalid source identity")
            target = (root / relative).resolve(strict=True)
            if not target.is_relative_to(root.resolve()):
                raise ValueError("Source identity escapes repository")
            module = importlib.import_module(relative[:-3].replace("/", "."))
            symbol = module
            for component in qualified.split("."):
                symbol = getattr(symbol, component)
            if Path(inspect.getsourcefile(symbol)).resolve() != target:
                raise ValueError("Loaded source origin mismatch")
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("Source digest mismatch")
    except (KeyError, ValueError, TypeError, AttributeError, OSError, ImportError) as exc:
        raise IntegrationError("runtime_profile_incompatible") from exc


@dataclass(frozen=True)
class Preflight:
    pin: object
    contents: tuple
    retention: object

    def hook(self, profile, foundation, bundle, knowledge, policy, adapters, classifier):
        # Knowledge internals are validated by the normal RequestAssembly path.
        return (profile, foundation, bundle, policy, adapters, classifier) == self.contents


def preflight(store, *, root=REPOSITORY_ROOT):
    try:
        pinned = store.pin_active_profile("classification")
        if not isinstance(pinned, PinnedRuntimeProfile):
            raise IntegrationError("activation_lineage_unavailable")
        profile, rpm = pinned.runtime_profile, pinned.admission_manifest
        if (make_classification_runtime_profile(profile.semantic_payload) != profile
                or make_runtime_profile_admission_manifest(rpm.semantic_payload) != rpm
                or make_runtime_profile_validity_record(pinned.validity_record.semantic_payload) != pinned.validity_record
                or pinned.validity_record.semantic_payload["state"] != "ACTIVE"):
            raise IntegrationError("production_profile_not_admitted")
        rp = rpm.semantic_payload
        if (rp["profile_kind"] != "classification" or rp["candidate_profile"] !=
                ArtifactRef(profile.artifact_id, profile.content_sha256).as_dict()
                or rp["compatibility_validation_result"] != "PASS"):
            raise IntegrationError("production_profile_not_admitted")
        accepted = load_reference(store, rp["task04_acceptance_manifest"], "Task04AcceptanceManifest")
        foundation_rpm = load_reference(store, rp["foundation_runtime_profile_admission_manifest"],
                                        "RuntimeProfileAdmissionManifest")
        p = profile.semantic_payload
        foundation = load_reference(store, p["foundation_runtime_profile"], "FoundationRuntimeProfile")
        if (make_foundation_runtime_profile(foundation.semantic_payload) != foundation
                or make_runtime_profile_admission_manifest(foundation_rpm.semantic_payload) != foundation_rpm
                or foundation_rpm.semantic_payload["profile_kind"] != "foundation"
                or foundation_rpm.semantic_payload["candidate_profile"] != p["foundation_runtime_profile"]
                or rp["foundation_admission_manifest"] != foundation_rpm.semantic_payload["foundation_admission_manifest"]
                or accepted.semantic_payload["foundation_admission_manifest"] != rp["foundation_admission_manifest"]
                or accepted.semantic_payload["tested_classification_runtime_profile"] != rp["candidate_profile"]
                or accepted.semantic_payload["classifier_artifact_manifest"] != p["classifier_artifact_manifest"]):
            raise IntegrationError("runtime_profile_incompatible")
        bundle, policy, adapters, classifier = tuple(load_reference(store, p[field], kind) for field, kind in (
            ("knowledge_bundle", "KnowledgeBundle"), ("classification_policy", "ClassificationPolicy"),
            ("evidence_adapter_contract_set", "EvidenceAdapterContractSet"),
            ("classifier_artifact_manifest", "ClassifierArtifactManifest")))
        verify_executable_identities(classifier, root=root)
        foundation_manifest = load_reference(store, foundation_rpm.semantic_payload["foundation_admission_manifest"],
                                             "FoundationAdmissionManifest")
        retention = load_reference(store, foundation_manifest.semantic_payload["classification_retention_policy"],
                                  "ClassificationRetentionPolicy")
        return Preflight(pinned, (profile, foundation, bundle, policy, adapters, classifier), retention)
    except IntegrationError:
        raise
    except ControlPlaneOperationError as exc:
        raise IntegrationError(exc.reason_code) from exc
    except (ValueError, KeyError, TypeError, AttributeError, DeviceFingerprintValidationError) as exc:
        raise IntegrationError("runtime_profile_incompatible") from exc


class ReadOnlyControlPlaneStoreMixin:
    """Task-05 may pin/load/check lineage, but never create or mutate control-plane DBs."""
    def _connect(self):
        conn = sqlite3.connect(f"{Path(self.database_path).resolve().as_uri()}?mode=ro", uri=True,
                               timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


class ExactPinStore:
    """Delegate the normal assembly pin; reject generation drift, including same-profile ABA."""
    def __init__(self, store, expected):
        self.store, self.expected = store, expected

    def pin_active_profile(self, kind):
        pinned = self.store.pin_active_profile(kind)
        if not same_pin(pinned, self.expected):
            raise ControlPlaneOperationError("runtime_profile_incompatible")
        return pinned

    def load_artifact(self, *args):
        return self.store.load_artifact(*args)
