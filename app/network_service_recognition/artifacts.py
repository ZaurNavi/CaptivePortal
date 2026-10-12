"""Closed immutable knowledge bundle admission. No repair or network fallback."""
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType

from app.network_metadata.validation import ni_timestamp
from .canonical import (RecognitionValidationError, canonical_hostname, content_digest,
                        strict_artifact_json, canonical_json)

CATEGORIES = frozenset("category." + value for value in (
    "video_streaming", "audio_streaming", "messaging", "social", "cloud_storage",
    "productivity_collaboration", "gaming", "software_distribution", "web_search", "other_supported"))
IDS = dict(taxonomy="captivportal.network-intelligence.recognition-taxonomy",
           knowledge_manifest="captivportal.network-intelligence.recognition-knowledge",
           ruleset="captivportal.network-intelligence.service-recognition")
_KINDS = frozenset(f"{target}_{signal}_{mode}" for target in ("service", "organization")
                   for signal in ("sni", "dns_connected") for mode in ("exact", "suffix"))


def _require(condition, reason="invalid_recognition_artifact"):
    if not condition:
        raise RecognitionValidationError(reason)


def _closed(value, fields):
    _require(type(value) is dict and set(value) == set(fields.split()))


def _text(value, maximum):
    _require(type(value) is str and 1 <= len(value) <= maximum and value == value.strip()
             and unicodedata.normalize("NFC", value) == value
             and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def _id(value, prefix, maximum=94):
    _require(type(value) is str and re.fullmatch(
        re.escape(prefix) + r"\.[a-z0-9][a-z0-9._-]{1," + str(maximum) + r"}[a-z0-9]", value) is not None)


def _ordered(rows, key, maximum, minimum=1):
    _require(type(rows) is list and minimum <= len(rows) <= maximum)
    keys = [row[key] for row in rows]
    _require(all(type(item) is str for item in keys) and keys == sorted(set(keys)))


def _review(row):
    first = ni_timestamp(row["reviewed_at_utc"], canonical=True)
    last = ni_timestamp(row["review_due_at_utc"], canonical=True)
    _require(timedelta(0) < last - first <= timedelta(days=365))
    return first, last


def _header(value, kind):
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1)
    _require(value[kind + "_id"] == IDS[kind])
    _require(type(value[kind + "_version"]) is int and value[kind + "_version"] > 0)
    digest = value[kind + "_digest_sha256"]
    _require(type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest) is not None)
    _require(content_digest(value, kind + "_digest_sha256") == digest, kind + "_digest_mismatch")


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class AdmittedArtifact(Mapping):
    """Immutable admitted content plus content-only lookup indexes, never evidence."""
    _content: object
    index: object

    def __getitem__(self, key):
        return self._content[key]

    def __iter__(self):
        return iter(self._content)

    def __len__(self):
        return len(self._content)


@dataclass(frozen=True, slots=True)
class RecognitionBundle:
    taxonomy: object
    manifest: object
    ruleset: object


def load_bundle(taxonomy_bytes, manifest_bytes, ruleset_bytes, *, previous=None):
    """Validate the complete tuple, then freeze it atomically. No subset activation."""
    try:
        taxonomy = strict_artifact_json(taxonomy_bytes)
        _closed(taxonomy, "schema_version taxonomy_id taxonomy_version taxonomy_digest_sha256 organizations service_categories services")
        _header(taxonomy, "taxonomy")
        for key, id_key, cap in (("organizations", "organization_id", 256),
                                 ("service_categories", "service_category_id", 10),
                                 ("services", "service_id", 512)):
            _ordered(taxonomy[key], id_key, cap)
        for row in taxonomy["organizations"]:
            _closed(row, "organization_id display_name organization_kind")
            _id(row["organization_id"], "org", 62)
            _text(row["display_name"], 64)
            _require(row["organization_kind"] in {"service_operator", "infrastructure_provider", "mixed"})
        for row in taxonomy["service_categories"]:
            _closed(row, "service_category_id display_name")
            _require(row["service_category_id"] in CATEGORIES)
            _text(row["display_name"], 64)
        organizations = {row["organization_id"] for row in taxonomy["organizations"]}
        categories = {row["service_category_id"] for row in taxonomy["service_categories"]}
        services = {row["service_id"]: row for row in taxonomy["services"]}
        for row in taxonomy["services"]:
            _closed(row, "service_id display_name organization_id service_category_id lifecycle_state")
            _id(row["service_id"], "service", 58)
            _text(row["display_name"], 64)
            _require(row["organization_id"] in organizations and row["service_category_id"] in categories)
            _require(row["lifecycle_state"] in {"active", "retired"})

        manifest = strict_artifact_json(manifest_bytes)
        _closed(manifest, "schema_version knowledge_manifest_id knowledge_manifest_version knowledge_manifest_digest_sha256 reviewed_at_utc review_due_at_utc sources")
        _header(manifest, "knowledge_manifest")
        manifest_review, _ = _review(manifest)
        _ordered(manifest["sources"], "knowledge_ref", 4096)
        sources = {row["knowledge_ref"]: row for row in manifest["sources"]}
        for row in sources.values():
            _closed(row, "knowledge_ref source_class publisher_or_owner source_locator claim_summary reviewed_at_utc review_due_at_utc")
            _id(row["knowledge_ref"], "knowledge")
            _require(row["source_class"] in {"first_party_public", "controlled_owner_trace", "authoritative_registry", "reviewed_internal_research"})
            for key, cap in (("publisher_or_owner", 128), ("source_locator", 2048), ("claim_summary", 512)):
                _text(row[key], cap)
            first, last = _review(row)
            _require(first <= manifest_review < last)

        ruleset = strict_artifact_json(ruleset_bytes)
        _closed(ruleset, "schema_version ruleset_id ruleset_version ruleset_digest_sha256 taxonomy_id taxonomy_version taxonomy_digest_sha256 knowledge_manifest_id knowledge_manifest_version knowledge_manifest_digest_sha256 rules")
        _header(ruleset, "ruleset")
        for parent, kind in ((taxonomy, "taxonomy"), (manifest, "knowledge_manifest")):
            for suffix in ("_id", "_version", "_digest_sha256"):
                _require(type(ruleset[kind + suffix]) is type(parent[kind + suffix])
                         and ruleset[kind + suffix] == parent[kind + suffix])
        _ordered(ruleset["rules"], "rule_id", 2048)
        matchers, groups, duplicates = {}, {}, set()
        for rule in ruleset["rules"]:
            _closed(rule, "rule_id rule_kind target_type target_id hostname_pattern knowledge_refs reviewed_at_utc review_due_at_utc lifecycle_state ambiguity_group_id")
            _id(rule["rule_id"], "rule")
            _require(rule["rule_kind"] in _KINDS and rule["target_type"] in {"service", "organization"})
            _require(rule["rule_kind"].startswith(rule["target_type"] + "_"))
            _require(rule["target_id"] in (services if rule["target_type"] == "service" else organizations))
            _require(rule["lifecycle_state"] in {"active", "retired"})
            _require(not ("dns_connected" in rule["rule_kind"] and rule["lifecycle_state"] == "active"))
            _require(canonical_hostname(rule["hostname_pattern"]) == rule["hostname_pattern"])
            refs = rule["knowledge_refs"]
            _require(type(refs) is list and 1 <= len(refs) <= 4096
                     and all(type(ref) is str and ref in sources for ref in refs)
                     and refs == sorted(set(refs)))
            first, _ = _review(rule)
            _require(first >= manifest_review and all(first >= _review(sources[ref])[0] for ref in refs))
            if rule["lifecycle_state"] == "active" and rule["target_type"] == "service":
                _require(services[rule["target_id"]]["lifecycle_state"] == "active")
            group = rule["ambiguity_group_id"]
            if group is not None:
                _id(group, "ambiguity")
                groups.setdefault(group, []).append(rule)
            key = (rule["rule_kind"], rule["hostname_pattern"])
            duplicate = (key, rule["target_type"], rule["target_id"])
            _require(duplicate not in duplicates, "duplicate_matcher_target_rule")
            duplicates.add(duplicate)
            matchers.setdefault(key, []).append(rule)
        for rules in matchers.values():
            if len(rules) > 1:
                group = rules[0]["ambiguity_group_id"]
                _require(group is not None and all(row["ambiguity_group_id"] == group
                    and row["target_type"] == "service" and row["lifecycle_state"] == "active"
                    for row in rules), "undeclared_service_matcher_collision")
        for rules in groups.values():
            _require(len(rules) >= 2 and len({(row["rule_kind"], row["hostname_pattern"]) for row in rules}) == 1)
            _require(all(row["target_type"] == "service" and row["lifecycle_state"] == "active" for row in rules))
        _require(any(row["target_type"] == "service" and row["lifecycle_state"] == "active" for row in ruleset["rules"]))
        if previous is not None:
            for new, old, kind in ((taxonomy, previous.taxonomy, "taxonomy"),
                                   (manifest, previous.manifest, "knowledge_manifest"),
                                   (ruleset, previous.ruleset, "ruleset")):
                version, digest = kind + "_version", kind + "_digest_sha256"
                if new[version] == old[version]:
                    _require(new[digest] == old[digest], "artifact_identity_conflict")
                else:
                    keys = {version, digest}
                    _require(canonical_json({k: v for k, v in new.items() if k not in keys}) !=
                             canonical_json({k: v for k, v in old.items() if k not in keys}), "noop_version_bump")
        frozen_taxonomy, frozen_manifest, frozen_ruleset = map(_freeze, (taxonomy, manifest, ruleset))
        intervals, matchers = {}, {}
        for rule in frozen_ruleset["rules"]:
            reviews = (rule, frozen_manifest, *(sources[ref] for ref in rule["knowledge_refs"]))
            intervals[rule["rule_id"]] = (max(_review(row)[0] for row in reviews),
                                         min(_review(row)[1] for row in reviews))
            matchers.setdefault((rule["rule_kind"], rule["hostname_pattern"]), []).append(rule)
        return RecognitionBundle(
            AdmittedArtifact(frozen_taxonomy, _freeze({"services": services})),
            AdmittedArtifact(frozen_manifest, MappingProxyType(intervals)),
            AdmittedArtifact(frozen_ruleset, MappingProxyType({key: tuple(rows) for key, rows in matchers.items()})))
    except RecognitionValidationError:
        raise
    except Exception:
        raise RecognitionValidationError() from None


def load_local_bundle(*, version=2):
    """Select only the frozen local tuple; v1 is explicit rollback, never fallback."""
    from hashlib import sha256
    pinned = {
        1: ("58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0",
            "6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0",
            "e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1"),
        2: ("9dfc0a2ed699f09a4f70e32f30e2d259d96f0f70eb2e8eb06366e5198486c7ee",
            "8f09b6cc685a103a9b4515367980ccefbaa9755a28134b9c6b184cad3e1834f3",
            "595c6982ddf2625de1dbf0262a8da68e5e0cfcb12894a9883cf21bc63a226db8"),
    }
    if type(version) is not int or version not in pinned:
        raise RecognitionValidationError("recognition_configuration_unavailable")
    directory = Path(__file__).parent / "knowledge"
    try:
        raw = tuple(directory.joinpath(f"{name}-v{version}.json").read_bytes() for name in (
            "recognition-taxonomy", "recognition-knowledge-manifest", "recognition-ruleset"))
        if tuple(sha256(value).hexdigest() for value in raw) != pinned[version]:
            raise RecognitionValidationError("recognition_configuration_unavailable")
        result = load_bundle(*raw)
        if any(parent[kind + "_version"] != version for parent, kind in (
                (result.taxonomy, "taxonomy"), (result.manifest, "knowledge_manifest"), (result.ruleset, "ruleset"))):
            raise RecognitionValidationError("recognition_configuration_unavailable")
        return result
    except OSError:
        raise RecognitionValidationError("recognition_configuration_unavailable") from None
