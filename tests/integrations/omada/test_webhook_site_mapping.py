import json
import logging
import uuid
from unittest.mock import patch

import pytest

from app.integrations.omada.webhook_site_mapping import (
    MAPPING_INVALID_EVENT,
    load_webhook_site_id_mapping,
    log_invalid_webhook_site_id_mapping,
)
from app.integrations.omada.webhook_routes import WEBHOOK_PATH


ALLOWED_IP = "192.168.0.222"
ONLINE = (
    "[client:Galaxy-A24:32-84-C9-40-38-88] "
    "(IP: 192.168.1.96) went online on "
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    'with SSID "Zefer_Parki" on channel 64.'
)


def test_exact_mapping_is_deterministic_and_case_sensitive():
    mapping = load_webhook_site_id_mapping(
        '{"Home":"site-home","Park":"site-park"}'
    )

    assert mapping.valid is True
    assert mapping.resolve("Home") == ("site-home", "resolved")
    assert mapping.resolve("Park") == ("site-park", "resolved")
    assert mapping.resolve("home") == (None, "site_unresolved")
    assert mapping.resolve(" Home ") == (None, "site_unresolved")
    assert mapping.resolve("") == (None, "site_missing")
    assert mapping.resolve("   ") == (None, "site_missing")
    assert mapping.resolve(None) == (None, "site_missing")


@pytest.mark.parametrize(
    ("raw_json", "error_code"),
    [
        ("{", "MALFORMED_JSON"),
        ("[]", "ROOT_NOT_OBJECT"),
        ("null", "ROOT_NOT_OBJECT"),
        ('{"Home":"one","Home":"two"}', "DUPLICATE_SITE_NAME"),
        ('{"   ":"site-id"}', "SITE_NAME_EMPTY"),
        ('{"Home":1}', "SITE_ID_NOT_STRING"),
        ('{"Home":"   "}', "SITE_ID_EMPTY"),
    ],
)
def test_any_invalid_entry_invalidates_the_whole_mapping(
    raw_json,
    error_code,
):
    mapping = load_webhook_site_id_mapping(raw_json)

    assert mapping.valid is False
    assert mapping.error_code == error_code
    assert dict(mapping.entries) == {}
    assert mapping.resolve("Home") == (None, "mapping_invalid")
    assert mapping.resolve(None) == (None, "mapping_invalid")


def test_mapping_entries_are_immutable():
    mapping = load_webhook_site_id_mapping('{"Home":"site-id"}')

    with pytest.raises(TypeError):
        mapping.entries["Home"] = "changed"


def test_invalid_mapping_warning_is_structured_and_secret_safe(caplog):
    raw_json = '{"Home":"secret-site-id","Home":"duplicate"}'
    mapping = load_webhook_site_id_mapping(raw_json)
    logger = logging.getLogger(
        f"test.omada.site_mapping.{uuid.uuid4()}"
    )

    with caplog.at_level(logging.WARNING, logger=logger.name):
        log_invalid_webhook_site_id_mapping(logger, mapping)

    records = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.getMessage().startswith("{")
    ]
    assert len(records) == 1
    assert records[0]["event"] == MAPPING_INVALID_EVENT
    assert records[0]["level"] == "warning"
    assert records[0]["component"] == "omada_webhook_site_mapping"
    assert records[0]["error_code"] == "DUPLICATE_SITE_NAME"
    assert raw_json not in caplog.text
    assert "secret-site-id" not in caplog.text


def test_valid_mapping_does_not_emit_configuration_warning(caplog):
    mapping = load_webhook_site_id_mapping('{"Home":"site-id"}')
    logger = logging.getLogger(
        f"test.omada.site_mapping.valid.{uuid.uuid4()}"
    )

    with caplog.at_level(logging.WARNING, logger=logger.name):
        log_invalid_webhook_site_id_mapping(logger, mapping)

    assert caplog.records == []


def test_application_wiring_uses_mapping_and_invalid_config_is_fail_open(
    tmp_path,
    caplog,
):
    import app.web.web as web_module

    raw_path = tmp_path / "raw.log"
    normalized_path = tmp_path / "normalized.log"
    settings = {
        "portal_counter_enabled": False,
        "portal_counter_db_path": "unused.db",
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": False,
        "auth_telemetry_enabled": False,
        "capport_enabled": False,
        "omada_webhook_enabled": True,
        "omada_webhook_allowed_ips": ALLOWED_IP,
        "omada_webhook_auth_mode": "ip_only",
        "omada_webhook_shared_secret": "",
        "omada_webhook_header_token": "",
        "omada_webhook_max_body_bytes": 1_048_576,
        "omada_webhook_log_file": str(raw_path),
        "omada_webhook_normalized_log_file": str(normalized_path),
        "omada_webhook_site_id_map_json": (
            '{"Home":"one","Home":"two"}'
        ),
    }

    with (
        patch.object(web_module, "get_settings", return_value=settings),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
        caplog.at_level(logging.WARNING, logger="captivportal"),
    ):
        app = web_module.create_app(portal_counter_service=None)

    response = app.test_client(use_cookies=False).post(
        WEBHOOK_PATH,
        json={
            "Site": "Home",
            "Controller": "controller",
            "timestamp": 1_785_238_468_934,
            "text": [ONLINE],
        },
        headers={"X-Forwarded-For": ALLOWED_IP},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 204
    raw_record = json.loads(
        raw_path.read_text(encoding="utf-8").splitlines()[0]
    )
    normalized = json.loads(
        normalized_path.read_text(encoding="utf-8").splitlines()[0]
    )
    assert raw_record["parsed_payload"]["Site"] == "Home"
    assert normalized["site"] == "Home"
    assert normalized["site_id"] is None
    assert normalized["site_resolution_status"] == "mapping_invalid"
    warnings = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.getMessage().startswith("{")
    ]
    assert [event["event"] for event in warnings] == [
        MAPPING_INVALID_EVENT
    ]
