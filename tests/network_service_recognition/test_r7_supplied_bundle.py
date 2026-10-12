"""Software checks of frozen TechLead input, not research or release admission."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from app.network_service_recognition import artifacts
from app.network_service_recognition.artifacts import CATEGORIES, load_bundle, load_local_bundle
from app.network_service_recognition.canonical import RecognitionValidationError, content_digest
from app.network_service_recognition.matcher import match_direct_sni_v1, rule_eligible
from app.network_service_recognition.models import ServiceUnavailable
from app.network_service_recognition.serialization import serialize_device_service_intelligence
from app.network_metadata.validation import ni_timestamp
from .support import KNOWLEDGE, bundle as historical_v1
from .test_summary import synthetic, read

FIXTURES = Path(__file__).with_name("fixtures") / "r7-techlead"
AT = "2026-10-12T10:00:00.000000Z"
EVENT = "2026-10-12T09:59:00.123456Z"
BLOCKED = {"service.messenger", "service.viber"}
NAMES = ("recognition-taxonomy-v2.json", "recognition-knowledge-manifest-v2.json", "recognition-ruleset-v2.json")
RAW = (
    "9dfc0a2ed699f09a4f70e32f30e2d259d96f0f70eb2e8eb06366e5198486c7ee",
    "8f09b6cc685a103a9b4515367980ccefbaa9755a28134b9c6b184cad3e1834f3",
    "595c6982ddf2625de1dbf0262a8da68e5e0cfcb12894a9883cf21bc63a226db8")
SEMANTIC = (
    "0d6a9898d41e8a40863eab1582781e394752a0529b51dc4e92075c592abccfc2",
    "148bf04201080ebbb10245bfbcd7d05aef521eff3e633bb6b1f734912200b203",
    "9c6a89c5dcf4f69396fef0645d19f52ae57312944a0308f1fd541f4c92a7ffe6")
VECTORS = json.loads((FIXTURES / "TECHLEAD-55-SYNTHETIC-TEST-VECTORS.json").read_bytes())["vectors"]


@pytest.fixture(scope="module")
def r7():
    return load_local_bundle()


def test_supplied_raw_semantic_identities_and_existing_validator(r7):
    raw = tuple((KNOWLEDGE / name).read_bytes() for name in NAMES)
    assert tuple(sha256(value).hexdigest() for value in raw) == RAW
    assert load_bundle(*raw, previous=historical_v1()) == r7
    for value, kind, digest in zip((r7.taxonomy, r7.manifest, r7.ruleset), ("taxonomy", "knowledge_manifest", "ruleset"), SEMANTIC):
        assert value[kind + "_version"] == 2
        assert value[kind + "_digest_sha256"] == content_digest(value, kind + "_digest_sha256") == digest
    assert (len(r7.taxonomy["services"]), len(r7.manifest["sources"]), len(r7.ruleset["rules"])) == (55, 57, 53)
    assert {row["service_category_id"] for row in r7.taxonomy["service_categories"]} == CATEGORIES


def test_supplied_techlead_fixture_hashes_and_exact_330_inventory():
    pins = {
        "TECHLEAD-55-HOST-DECISIONS.json": "60022efb11ca4f00dc9c79ed2256b4b072c9dae408d2f083b693cbc979744151",
        "TECHLEAD-55-SYNTHETIC-TEST-VECTORS.json": "2c79d7b99d115cdef99296be26ba6663e14b319dc48f5fbe1ab5367d45535092",
        "TECHLEAD-RELEASE-BLOCKERS.json": "ced3c7b1eae65049f19b2ce1936d9c02024cf8bca658275a930521efa1146b66"}
    for name, digest in pins.items():
        assert sha256((FIXTURES / name).read_bytes()).hexdigest() == digest
    assert len(VECTORS) == 330
    assert len({row["service_id"] for row in VECTORS}) == 55
    assert set(json.loads((FIXTURES / "TECHLEAD-RELEASE-BLOCKERS.json").read_bytes())["not_admitted_service_ids"]) == BLOCKED


def test_exact_registry55_ledger_and_non_admitted_slots(r7):
    registry = json.loads(Path(__file__).parents[2].joinpath("docs/network-service-recognition/NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json").read_bytes())
    decisions = json.loads((FIXTURES / "TECHLEAD-55-HOST-DECISIONS.json").read_bytes())["services"]
    expected = {row["service_id"] for row in registry["services"]}
    assert {row["service_id"] for row in r7.taxonomy["services"]} == expected
    assert {row["service_id"] for row in decisions} == expected
    assert {row["target_id"] for row in r7.ruleset["rules"]} == expected - BLOCKED
    assert len({row["hostname_pattern"] for row in r7.ruleset["rules"]}) == 53
    assert all(row["rule_kind"] == "service_sni_exact" and row["lifecycle_state"] == "active" for row in r7.ruleset["rules"])
    assert r7.taxonomy.index["services"]["service.chatgpt"]["service_category_id"] == "category.other_supported"


def test_original_five_semantics_and_explicit_v1_rollback_unchanged(r7):
    old = load_local_bundle(version=1)
    assert old == historical_v1() and len(old.ruleset["rules"]) == 5
    for row in old.taxonomy["services"]:
        assert r7.taxonomy.index["services"][row["service_id"]] == row
    rules = {row["rule_id"]: row for row in r7.ruleset["rules"]}
    ignore = {"reviewed_at_utc", "review_due_at_utc"}
    for row in old.ruleset["rules"]:
        assert {key: value for key, value in rules[row["rule_id"]].items() if key not in ignore} == {
            key: value for key, value in row.items() if key not in ignore}


@pytest.mark.parametrize("row", VECTORS, ids=[f"{index:03d}-{row['service_id']}-{row['signal']}" for index, row in enumerate(VECTORS)])
def test_exact_330_techlead_expectations_use_production_matcher_and_read_path(r7, row):
    if row["signal"] == "dns_only":
        with pytest.raises(RecognitionValidationError):
            match_direct_sni_v1(hostname=row["hostname"], signal_family=row["signal"], evaluated_at_utc=AT,
                taxonomy=r7.taxonomy, manifest=r7.manifest, ruleset=r7.ruleset)
        family = "dns"
    else:
        outcome = match_direct_sni_v1(hostname=row["hostname"], signal_family=row["signal"], evaluated_at_utc=AT,
            taxonomy=r7.taxonomy, manifest=r7.manifest, ruleset=r7.ruleset)
        assert outcome.service_id == row["expected"]
        family = row["signal"].split("_")[0]
    result = read(*synthetic(row["hostname"], family, event=EVENT), b=r7, at=AT)
    actual = result.last_service_observation.service_id if result.last_service_observation else None
    assert actual == row["expected"]
    public = json.dumps(serialize_device_service_intelligence(result, r7))
    assert row["hostname"] not in public
    for forbidden in ("src_ip", "dst_ip", "sni", "query_name", "knowledge_refs", "source_locator", "evidence_refs"):
        assert f'"{forbidden}"' not in public


@pytest.mark.parametrize("damage", ["site", "device", "inbound", "local", "ech"])
def test_r7_preserves_protected_qualifying_context(r7, damage):
    snapshot, source = synthetic("www.youtube.com", event=EVENT)
    if damage == "site": snapshot = replace(snapshot, site_id="abcdef0123456789abcdef01")
    elif damage == "device": snapshot = replace(snapshot, bound_device_id="10000000-0000-4000-8000-000000000002")
    elif damage == "inbound": snapshot = replace(snapshot, facts=(replace(snapshot.facts[0], direction="inbound"),))
    elif damage == "local": snapshot = replace(snapshot, facts=(replace(snapshot.facts[0], peer_scope="local"),))
    else: source = replace(source, tls=replace(source.tls, sni=None, sni_presence_state="not_observed"))
    if damage == "ech":
        assert read(snapshot, source, b=r7, at=AT).last_service_observation is None
    else:
        with pytest.raises(ServiceUnavailable): read(snapshot, source, b=r7, at=AT)


def test_all_supplied_refs_eligible_at_review_and_expire_at_earliest_due(r7):
    at = ni_timestamp(AT, canonical=True)
    for rule in r7.ruleset["rules"]:
        assert rule_eligible(rule, r7.manifest, at)
        references = (rule, r7.manifest, *(row for row in r7.manifest["sources"] if row["knowledge_ref"] in rule["knowledge_refs"]))
        due = min(ni_timestamp(row["review_due_at_utc"], canonical=True) for row in references)
        assert not rule_eligible(rule, r7.manifest, due)
        assert match_direct_sni_v1(hostname=rule["hostname_pattern"], signal_family="tls_sni",
            evaluated_at_utc=due.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            taxonomy=r7.taxonomy, manifest=r7.manifest, ruleset=r7.ruleset).service_id is None


@pytest.fixture
def disposable_local_bundle(tmp_path, monkeypatch):
    target = tmp_path / "module" / "knowledge"
    target.mkdir(parents=True)
    for version in (1, 2):
        for name in ("recognition-taxonomy", "recognition-knowledge-manifest", "recognition-ruleset"):
            shutil.copyfile(KNOWLEDGE / f"{name}-v{version}.json", target / f"{name}-v{version}.json")
    monkeypatch.setattr(artifacts, "Path", lambda _: target.parent / "artifacts.py")
    return target


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("damage", ["missing", "mixed_v1", "unknown_bytes"])
def test_local_loader_no_fallback_or_unpinned_tuple(disposable_local_bundle, name, damage):
    target = disposable_local_bundle / name
    if damage == "missing": target.unlink()
    elif damage == "mixed_v1": shutil.copyfile(KNOWLEDGE / name.replace("-v2", "-v1"), target)
    else: target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(RecognitionValidationError): load_local_bundle()
    assert load_local_bundle(version=1) == historical_v1()


@pytest.mark.parametrize("version", [True, None, "2", 0, 3, 55, "../../RESEARCH-ONLY-55-RULE-PROTOTYPE-NOT-FOR-RUNTIME"])
def test_local_selection_is_closed_not_environment_or_unknown_path(version):
    with pytest.raises(RecognitionValidationError): load_local_bundle(version=version)


def test_admin_v2_composition_failure_is_isolated_and_logs_are_safe(disposable_local_bundle, tmp_path, caplog):
    import logging
    from types import SimpleNamespace
    from app.admin_web.runtime import create_admin_web_runtime
    from app.settings_control.models import ResolvedSettingsSnapshot
    from app.settings_control.features import AdminFeaturePlanV1
    from tests.admin_web.test_device_service_intelligence import enabled_settings
    (disposable_local_bundle / NAMES[2]).unlink()
    with pytest.raises(RecognitionValidationError) as caught: load_local_bundle()
    assert str(caught.value) == "recognition_configuration_unavailable"
    assert "knowledge" not in str(caught.value) and "v2.json" not in str(caught.value)
    settings = enabled_settings(web_admin_device_service_intelligence_enabled="true")
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = create_admin_web_runtime(settings, SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.db"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.db")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.db")),
        logging.getLogger("ni04-r7-composition"), feature_plan=plan)
    assert runtime.state == "active" and runtime.query_service is not None
    assert runtime.query_service._service_intelligence is None
    assert "v2.json" not in caplog.text and str(disposable_local_bundle) not in caplog.text
