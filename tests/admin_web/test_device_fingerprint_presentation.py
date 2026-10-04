"""Task-06: advisory production-only projections without classification or writes."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.admin_web.device_fingerprint_presentation import (
    DeviceFingerprintPresentationService, present_classification,
)
from app.admin_web.models import AdminPrincipal
from app.admin_web.query_service import AdminQueryForbidden
from app.device_fingerprint.artifact_content import make_artifact_content
from app.device_fingerprint.classification_read import ClassificationReadRecord
from app.current_state import CurrentClientPage
from tests.device_fingerprint_task04_04e_read.test_classification_read import _persisted
from .conftest import SITE_ID
from .test_home_live import service, CurrentSource, client_item, snapshot
from .test_query_service import _service, DEVICE_ID

_DIMENSIONS = ("device_class_result", "platform_result", "manufacturer_result", "model_result")
_CANONICAL = ("smartphone", "android", "synthetic_manufacturer", "synthetic_model")


@pytest.fixture(scope="module")
def retained(tmp_path_factory):
    _, _, _, reader = _persisted(tmp_path_factory.mktemp("task06-retained"))
    from tests.device_fingerprint import SITE
    from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC
    record = reader.get_current(SITE, MAC)
    return ClassificationReadRecord(replace(record.core, execution_context="PRODUCTION",
                                            runtime_profile_activation_record_id="11111111-1111-4111-8111-111111111111"),
                                    record.result)


def shaped(retained, status="resolved", *, platform="android"):
    payload = retained.result.semantic_payload
    payload["global_classification_status"] = "partial"
    for field, canonical in zip(_DIMENSIONS, _CANONICAL):
        row = payload[field]
        row.update(canonical_value_id=(platform if field == "platform_result" else canonical)
                   if status == "resolved" else None, status=status,
                   support_level="medium" if status in {"resolved", "recognized_out_of_scope"} else "none",
                   supporting_origin_groups=["dhcp"], contradicting_origin_groups=["portal"],
                   not_evaluable_origin_groups=["tcp"], out_of_scope_taxon_references=["fixture-outside"],
                   explanation_codes=["fixture_explanation"], knowledge_references=[{
                       "knowledge_bundle_id": "KnowledgeBundle:v1:sha256:" + "a" * 64,
                       "knowledge_bundle_digest": "a" * 64,
                       "knowledge_provenance_id": "KnowledgeProvenanceManifest:v1:sha256:" + "b" * 64,
                       "knowledge_provenance_digest": "b" * 64,
                       "canonical_knowledge_record_id": "fixture-record",
                       "rule_or_source_record_identity": "fixture-source",
                   }])
    result = make_artifact_content("ClassificationResult", payload)
    return ClassificationReadRecord(replace(retained.core, classification_result_id=result.artifact_id,
                                             classification_result_digest=result.content_sha256), result)


@pytest.mark.parametrize("status", ["resolved", "unknown", "insufficient_evidence",
                                    "conflicting_evidence", "recognized_out_of_scope"])
def test_all_dimensions_preserve_metadata_and_only_resolved_values_are_named(retained, status):
    record = shaped(retained, status)
    projection = present_classification(record).as_dict()
    assert projection["global_classification_status"] == "partial"
    assert projection["classified_at_utc"] == record.core.classified_at_utc
    for field in _DIMENSIONS:
        original = record.result.semantic_payload[field]
        shown = projection[field]
        assert shown == {key: value for key, value in original.items()
                         if key not in {"dimension_name", "display_label_ref"}} | {"value": shown["value"]}
        assert shown["value"] == (original["canonical_value_id"].replace("_", " ").title()
                                   if status == "resolved" else "Unknown")
    assert record.result.semantic_payload_json == shaped(retained, status).result.semantic_payload_json


def test_no_result_has_no_diagnostic_or_semantic_value():
    projection = present_classification(None)
    assert projection.compact_type() == {"state": "no_result", "value": "—"}
    assert projection.as_dict() == {"state": "no_result", "global_classification_status": None,
                                   "classified_at_utc": None, **dict.fromkeys(_DIMENSIONS)}


def test_adapter_rejects_unbounded_input_and_deduplicates_canonical_macs():
    reader = ProductionReader(None)
    adapter = DeviceFingerprintPresentationService(reader)
    mac = "AA:BB:CC:DD:EE:FF"
    with pytest.raises(ValueError):
        adapter.get_many(SITE_ID, [mac] * 251)
    assert reader.calls == []
    assert list(adapter.get_many(SITE_ID, [mac, mac.lower().replace(":", "-")])) == [mac]
    assert reader.calls == [(SITE_ID, (mac,))]


class ProductionReader:
    def __init__(self, record):
        self.record = record
        self.calls = []
    def get_current_production_many(self, site, macs):
        self.calls.append((site, macs))
        if self.record is None:
            return dict.fromkeys(macs)
        return {mac: ClassificationReadRecord(replace(self.record.core, site_id=site, observed_mac=mac),
                                               self.record.result) for mac in macs}
    def get_current(self, *_args):
        pytest.fail("Presentation used unrestricted current result")
    def get_current_production(self, *_args):
        pytest.fail("Presentation used N individual reads")


@pytest.mark.parametrize("status,expected", [(None, "—"), ("resolved", "Smartphone"), ("unknown", "Unknown")])
def test_home_type_is_batched_separate_from_unchanged_controller(retained, status, expected):
    class MultipleClients(CurrentSource):
        def list_current_clients(self, site, **kwargs):
            return CurrentClientPage(snapshot(), (
                client_item(device_type=" Android "),
                client_item(client_mac="AA:BB:CC:DD:EE:02", device_type="Windows")), None)
    query = service(MultipleClients())
    reader = ProductionReader(shaped(retained, status) if status else None)
    query._fingerprint = DeviceFingerprintPresentationService(reader)
    result = query.list_current_clients(AdminPrincipal("operator"), SITE_ID).result
    assert len(reader.calls) == 1 and len(reader.calls[0][1]) == 2
    assert result["items"][0]["device_type"] == " Android "
    assert result["items"][0]["device_type_key"] == "android"
    assert result["items"][1]["device_type"] == "Windows"
    assert [item["fingerprint_type"]["value"] for item in result["items"]] == [expected, expected]
    assert all(set(item["fingerprint_type"]) == {"state", "value"} for item in result["items"])


@pytest.mark.parametrize("failure", ["storage", "candidate", "site", "malformed", "missing_db"])
def test_fingerprint_failures_leave_home_and_device_core_usable(retained, tmp_path, failure):
    class BadReader(ProductionReader):
        def get_current_production_many(self, site, macs):
            if failure == "storage":
                raise OSError("unreadable classification database")
            result = super().get_current_production_many(site, macs)
            for mac, record in result.items():
                if failure == "candidate":
                    result[mac] = ClassificationReadRecord(replace(record.core, execution_context="PRE_ACCEPTANCE_CANDIDATE"), record.result)
                elif failure == "site":
                    result[mac] = ClassificationReadRecord(replace(record.core, site_id="f" * 24), record.result)
                elif failure == "malformed":
                    result[mac] = ClassificationReadRecord(record.core, make_artifact_content("ClassificationResult", {"extra": True}))
            return result
    reader = BadReader(shaped(retained))
    if failure == "missing_db":
        from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
        reader = DeviceFingerprintClassificationReadService(tmp_path / "absent.sqlite")
    adapter = DeviceFingerprintPresentationService(reader)
    home = service(CurrentSource())
    home._fingerprint = adapter
    item = home.list_current_clients(AdminPrincipal("operator"), SITE_ID).result["items"][0]
    assert item["name"] == "Phone" and item["fingerprint_type"] == {"state": "unavailable", "value": "—"}
    device, _, _, _ = _service()
    device._fingerprint = adapter
    result = device.device_detail(AdminPrincipal("operator"), SITE_ID, DEVICE_ID).result
    assert result["identity"]["device_type"] == "phone"
    assert result["latest_snapshot"]["captured_at"]
    assert result["fingerprint"]["state"] == "unavailable"


def test_device_card_can_disagree_and_keeps_admin_site_policy(retained):
    reader = ProductionReader(shaped(retained, platform="chromeos"))
    query, devices, _, _ = _service()
    query._fingerprint = DeviceFingerprintPresentationService(reader)
    result = query.device_detail(AdminPrincipal("operator"), SITE_ID, DEVICE_ID).result
    assert result["identity"]["device_type"] == "phone"
    assert result["fingerprint"]["platform_result"]["value"] == "ChromeOS"
    assert result["fingerprint"]["device_class_result"]["support_level"] == "medium"
    assert len(reader.calls) == 1 and reader.calls[0][0] == SITE_ID
    with pytest.raises(AdminQueryForbidden):
        query.device_detail(AdminPrincipal("operator"), "f" * 24, DEVICE_ID)
    assert len(reader.calls) == 1


def test_read_service_composed_from_existing_setting_without_db_creation(tmp_path):
    import logging
    from app.admin_web import create_admin_web_runtime
    from .conftest import enabled_settings
    path = tmp_path / "readonly-not-created.sqlite"
    runtime = create_admin_web_runtime(
        enabled_settings(device_fingerprint_classification_db_path=str(path)),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "r"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "v")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "o")), logging.getLogger("task06"))
    assert runtime.state == "active"
    assert runtime.query_service._fingerprint.get(SITE_ID, "00:11:22:33:44:55").state == "unavailable"
    assert not path.exists()
