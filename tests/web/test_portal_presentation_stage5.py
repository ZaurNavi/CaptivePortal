from dataclasses import FrozenInstanceError
import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from flask import template_rendered
from app.portal_presentation import PORTAL_SETTING_DEFAULTS, PortalPresentationConfigV1, PortalTemplatePresentationV1, PortalPresentationConfigError
from app.web.localization import PORTAL_TRANSLATIONS
from app.web.web import create_app
from tests.settings_control import stack


def guest_app(**overrides):
    from app.settings import get_settings
    settings = {**get_settings(), "portal_counter_enabled": False, "portal_counter_api_enabled": False,
        "capport_enabled": False, "auth_telemetry_enabled": False, **overrides}
    return create_app(portal_counter_service=None, public_traffic_service=None, public_traffic_worker=None,
        controller=Mock(), portal_evidence_sink=None, client_hints_probe=None, settings=settings), settings


def test_complete_projection_is_immutable_and_changes_only_nine_catalog_values():
    config = PortalPresentationConfigV1.from_settings({"portal_ui_title_en": "<script>literal</script>"})
    projection = PortalTemplatePresentationV1.compose(config)
    assert set(projection.translations) == {"az", "ru", "en"}
    for language in projection.translations:
        assert set(projection.translations[language]) == set(PORTAL_TRANSLATIONS[language])
        for key, value in PORTAL_TRANSLATIONS[language].items():
            if key not in {"title", "greeting", "description"}:
                assert projection.translations[language][key] == value
    assert projection.translations["en"]["title"] == "<script>literal</script>"
    assert json.loads(json.dumps(projection.translations))["en"]["title"] == "<script>literal</script>"
    with pytest.raises(TypeError): projection.translations["en"]["title"] = "changed"
    with pytest.raises(TypeError): projection.support.update({"email": "changed"})
    with pytest.raises(FrozenInstanceError): projection.support = {}
    with pytest.raises(TypeError): PORTAL_SETTING_DEFAULTS["PORTAL_UI_TITLE_EN"] = "changed"


def test_one_startup_projection_normal_and_error_entry_escape_html_without_request_settings_io(monkeypatch):
    app, settings = guest_app(portal_ui_title_az="<b>literal title</b>", portal_ui_greeting_az="<script>alert(1)</script>",
        portal_ui_description_az="First line\nSecond line")
    projection = app.extensions["portal_template_presentation"]
    assert app.extensions["portal_entry_handler"]._portal_template_presentation is projection
    settings["portal_ui_title_az"] = "must not be adopted"
    monkeypatch.setattr("app.web.web.get_settings", lambda: pytest.fail("request Settings lookup"))
    monkeypatch.setattr("app.portal_presentation.PortalPresentationConfigV1.from_settings", lambda *a: pytest.fail("request projection rebuild"))
    monkeypatch.setattr("app.settings_control.repository.SettingsRepository.transaction", lambda *a, **k: pytest.fail("request Settings DB"))
    app.extensions["portal_entry_handler"]._executor = SimpleNamespace(submit=lambda *a, **k: None)
    seen = []
    def capture(sender, template, context, **kwargs): seen.append(context)
    with template_rendered.connected_to(capture, app):
        client = app.test_client()
        invalid = client.get("/")
        normal = client.get("/?site=fixture-site&clientMac=AA:BB:CC:DD:EE:FF&clientIp=192.168.8.10")
    assert invalid.status_code == 400 and normal.status_code == 200
    assert len(seen) == 2
    assert all(context["portal_translations"] is projection.translations and context["portal_support"] is projection.support for context in seen)
    for response in (invalid, normal):
        html = response.get_data(as_text=True)
        assert "&lt;b&gt;literal title&lt;/b&gt;" in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<script>alert(1)</script>" not in html and "must not be adopted" not in html
        assert "First line\nSecond line" in html
        assert "tel:+994504174646" in html and "mailto:zaur.navi@gmail.com" in html
        assert 'rel="noopener noreferrer"' in html
        assert "<title>Zəfər Parkı - Wi-Fi</title>" in html


def test_empty_contacts_hide_complete_support_section():
    values = {key.lower(): "" for key in PORTAL_SETTING_DEFAULTS if key.startswith("PORTAL_SUPPORT_")}
    app, _ = guest_app(**values)
    html = app.test_client().get("/").get_data(as_text=True)
    assert "mailto:" not in html and "tel:" not in html and "social-links" not in html
    assert "Texniki dəstək" not in html


@pytest.mark.parametrize("key,marker", [("phone", 'href="tel:'), ("email", 'href="mailto:'),
    ("whatsapp_url", 'aria-label="WhatsApp"'), ("telegram_url", 'aria-label="Telegram"'), ("facebook_url", 'aria-label="Facebook"')])
def test_each_empty_contact_hides_only_its_own_link(key, marker):
    app, _ = guest_app(**{"portal_support_" + key: ""})
    html = app.test_client().get("/").get_data(as_text=True)
    assert marker not in html
    assert 'class="portal-support"' in html


def test_success_page_is_not_a_portal_settings_consumer():
    app, _ = guest_app(portal_ui_title_az="custom guest-only branding")
    html = app.test_client().get("/success").get_data(as_text=True)
    assert "custom guest-only branding" not in html
    assert "portal_support" not in html


def test_operational_counter_and_controller_degradation_does_not_change_settings_adoption(tmp_path):
    boot = stack(tmp_path)
    boot.activation_service.adopt(boot.runtime_settings, None)
    # A failed worker/provider does not own Settings activation; normal error HTML still has the projection.
    app, _ = guest_app(**boot.runtime_settings)
    handler = app.extensions["portal_entry_handler"]
    handler._executor = SimpleNamespace(submit=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline worker")))
    counter = Mock()
    counter.record_open.side_effect = RuntimeError("offline counter")
    handler._portal_counter_service = counter
    handler._counter_recording_enabled = True
    response = app.test_client().get("/?site=fixture-outage&clientMac=AA:BB:CC:DD:EE:02&clientIp=192.168.8.11")
    assert response.status_code == 500  # Existing worker-start-failure contract, not an activation failure.
    counter.record_open.assert_called_once()
    assert PORTAL_SETTING_DEFAULTS["PORTAL_UI_TITLE_AZ"] in response.get_data(as_text=True)
    with boot.admin_context.read_service.repository.transaction() as db:
        assert boot.admin_context.read_service.repository.effective(db) == 0
        assert db.execute("SELECT COUNT(*) FROM settings_activation_events WHERE activation_result='failed'").fetchone()[0] == 0


@pytest.mark.parametrize("key,value", [("portal_ui_title_en", ""), ("portal_ui_description_ru", "bad\r\nline"), ("portal_support_telegram_url", "javascript:alert(1)")])
def test_invalid_startup_does_not_compose_guest_application(key, value):
    with pytest.raises(PortalPresentationConfigError): guest_app(**{key: value})


def test_failed_portal_adoption_never_serves_or_advances_effective(tmp_path, monkeypatch):
    import run as runtime
    from tests.visitor_registry.test_snapshot_runtime import _prepare_main
    events, _controller, _collector, _registry, app, _observed = _prepare_main(monkeypatch)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_: SimpleNamespace(json_line=lambda: "synthetic Portal startup"))
    boot = stack(tmp_path, host="127.0.0.1", port=8088, debug=False)
    monkeypatch.setattr(runtime, "bootstrap_settings_control", lambda **_: boot)
    monkeypatch.setattr(runtime, "create_app", lambda **_: (_ for _ in ()).throw(PortalPresentationConfigError()))
    with pytest.raises(PortalPresentationConfigError): runtime.main()
    assert not app.run_calls and "collector.start" not in events
    repository = boot.admin_context.read_service.repository
    with repository.transaction() as db:
        assert repository.effective(db) is None
        row = db.execute("SELECT activation_result,safe_error_code FROM settings_activation_events").fetchone()
        assert tuple(row) == ("failed", "portal_configuration_adoption_failed")


def test_unrelated_application_failure_not_misclassified_as_portal(tmp_path, monkeypatch):
    import run as runtime
    from tests.visitor_registry.test_snapshot_runtime import _prepare_main
    _events, _controller, _collector, _registry, app, _observed = _prepare_main(monkeypatch)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_: SimpleNamespace(json_line=lambda: "synthetic non-Portal startup"))
    boot = stack(tmp_path, host="127.0.0.1", port=8088, debug=False)
    monkeypatch.setattr(runtime, "bootstrap_settings_control", lambda **_: boot)
    monkeypatch.setattr(runtime, "create_app", lambda **_: (_ for _ in ()).throw(RuntimeError("unrelated composition failure")))
    with pytest.raises(RuntimeError): runtime.main()
    assert not app.run_calls
    with boot.admin_context.read_service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_activation_events WHERE safe_error_code='portal_configuration_adoption_failed'").fetchone()[0] == 0
