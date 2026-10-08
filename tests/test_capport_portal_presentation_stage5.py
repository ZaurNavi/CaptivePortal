from unittest.mock import Mock
import pytest
from flask import template_rendered
from app.portal_presentation import PortalPresentationConfigV1, PortalTemplatePresentationV1
from app.auth.manager import AuthSessionManager
from app.web.portal_entry import PortalEntryHandler
from tests.test_capport_routes import app_for, state


@pytest.mark.parametrize("lookup", ["normal", "discovery", "error"])
def test_capport_html_uses_exact_startup_projection_and_json_excludes_presentation(lookup):
    projection = PortalTemplatePresentationV1.compose(PortalPresentationConfigV1.from_settings({
        "portal_ui_title_az": "CAPPORT custom title", "portal_support_email": "support@example.invalid"}))
    service = Mock()
    service.resolve.return_value = state()
    service.resolve_for_login.return_value = state(found=lookup == "normal", lookup_failed=lookup == "error")
    handler = PortalEntryHandler(portal_template_presentation=projection, session_manager=AuthSessionManager(),
        auth_worker=Mock(), executor=Mock(), auth_telemetry=Mock())
    app, _ = app_for(service, handler, presentation=projection)
    contexts = []
    def capture(sender, template, context, **kwargs): contexts.append(context)
    client = app.test_client()
    options = {"base_url": "https://portal.example", "environ_base": {"REMOTE_ADDR": "192.168.1.10"}}
    with template_rendered.connected_to(capture, app): response = client.get("/capport/login", **options)
    assert response.status_code == (503 if lookup == "error" else 200)
    assert "CAPPORT custom title" in response.get_data(as_text=True)
    assert contexts[0]["portal_translations"] is projection.translations and contexts[0]["portal_support"] is projection.support
    for response in (client.get("/capport/api", **options), client.get("/capport/login", headers={"Accept": "application/json"}, **options)):
        assert response.is_json
        body = response.get_data(as_text=True)
        assert "CAPPORT custom title" not in body and "support@example.invalid" not in body
        assert "portal_support" not in body and "portal_translations" not in body
        assert response.headers["Cache-Control"] == "private, no-store"
