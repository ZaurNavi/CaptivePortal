"""One pure direct-SNI matcher. No identity attribution, IO or DNS correlation."""
from dataclasses import dataclass
from app.network_metadata.validation import ni_timestamp
from .canonical import canonical_hostname, RecognitionValidationError
from .artifacts import AdmittedArtifact


@dataclass(frozen=True, slots=True)
class RecognitionMatchOutcomeV1:
    schema_version: int
    resolution_state: str
    service_id: str | None
    organization_id: str | None
    service_category_id: str | None
    evidence_strength_class: str | None
    support_state: str
    matched_rule_ids: tuple[str, ...]
    ambiguity_group_id: str | None
    ruleset_id: str
    ruleset_version: int
    ruleset_digest_sha256: str
    taxonomy_id: str
    taxonomy_version: int
    taxonomy_digest_sha256: str
    knowledge_manifest_id: str
    knowledge_manifest_version: int
    knowledge_manifest_digest_sha256: str


def rule_eligible(rule, manifest, evaluated_at):
    if not isinstance(manifest, AdmittedArtifact):
        raise RecognitionValidationError()
    reviewed, due = manifest.index[rule["rule_id"]]
    return rule["lifecycle_state"] == "active" and reviewed <= evaluated_at < due


def matching_rules(hostname, ruleset):
    host = canonical_hostname(hostname)
    if host is None:
        return ()
    if not isinstance(ruleset, AdmittedArtifact):
        raise RecognitionValidationError()
    output = []
    for target in ("service", "organization"):
        output.extend(ruleset.index.get((target + "_sni_exact", host), ()))
        labels = host.split(".")
        for index in range(len(labels)):
            output.extend(ruleset.index.get((target + "_sni_suffix", ".".join(labels[index:])), ()))
    return tuple(output)


def match_direct_sni_v1(*, hostname, signal_family, evaluated_at_utc, taxonomy, manifest, ruleset):
    if signal_family not in {"tls_sni", "quic_sni"}:
        raise RecognitionValidationError("invalid_signal_family")
    if not all(isinstance(value, AdmittedArtifact) for value in (taxonomy, manifest, ruleset)) or any(
            ruleset[kind + suffix] != parent[kind + suffix]
            for parent, kind in ((taxonomy, "taxonomy"), (manifest, "knowledge_manifest"))
            for suffix in ("_id", "_version", "_digest_sha256")):
        raise RecognitionValidationError()
    at = ni_timestamp(evaluated_at_utc, canonical=True)
    identity = {key: ruleset[key] for key in (
        "ruleset_id", "ruleset_version", "ruleset_digest_sha256", "taxonomy_id", "taxonomy_version",
        "taxonomy_digest_sha256", "knowledge_manifest_id", "knowledge_manifest_version", "knowledge_manifest_digest_sha256")}
    priority = {"service_sni_exact": 10, "service_sni_suffix": 20,
                "organization_sni_exact": 50, "organization_sni_suffix": 60}
    candidates = [rule for rule in matching_rules(hostname, ruleset) if rule_eligible(rule, manifest, at)]
    if not candidates:
        return RecognitionMatchOutcomeV1(1, "unknown", None, None, None, None, "unsupported", (), None, **identity)
    best = min((priority[row["rule_kind"]], -len(row["hostname_pattern"])) for row in candidates)
    winners = [row for row in candidates if (priority[row["rule_kind"]], -len(row["hostname_pattern"])) == best]
    if len(winners) > 1:
        return RecognitionMatchOutcomeV1(1, "ambiguous", None, None, None, None, "ambiguous",
            tuple(sorted(row["rule_id"] for row in winners)), winners[0]["ambiguity_group_id"], **identity)
    winner = winners[0]
    if winner["target_type"] == "organization":
        return RecognitionMatchOutcomeV1(1, "organization_resolved", None, winner["target_id"], None,
            "strong", "directly_supported", (winner["rule_id"],), None, **identity)
    service = taxonomy.index["services"][winner["target_id"]]
    return RecognitionMatchOutcomeV1(1, "service_resolved", service["service_id"], service["organization_id"],
        service["service_category_id"], "strong", "directly_supported", (winner["rule_id"],), None, **identity)
