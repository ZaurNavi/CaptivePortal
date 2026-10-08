import json
from pathlib import Path
import shutil
import subprocess
import re
import pytest
from app.settings_control.definitions import SettingsDefinitionRegistry
from app.portal_presentation import portal_validation_metadata

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("scenario", ["changed", "clear", "noop", "conflict", "invalid", "outage", "readonly", "dirty", "metadata", "pending", "environment", "badrequest", "loadoutage"])
def test_real_portal_script_uses_server_metadata_and_safe_dom(scenario):
    registry = SettingsDefinitionRegistry()
    items = [{"key": item.key, "display_label": item.display_label, "description": item.description,
        "group": item.group, "presentation_type": item.presentation_type, "configured_value": "<script>literal</script>" if index == 0 else item.repository_default_value,
        "effective_value": "<script>literal</script>" if index == 0 else item.repository_default_value,
        "default_value": item.repository_default_value,
        "pending_value": None, "persisted_override_value": "old" if index == 13 else None,
        "base_source": "repository_default", "apply_requirement": item.apply_requirement,
        "validation": portal_validation_metadata(item.key)} for index, item in enumerate(registry.for_domain("portal"))]
    model = {"api_version": "admin.settings.portal.v1", "settings": items, "configured_generation": 0, "effective_generation": 0, "restart_required": False}
    if scenario == "metadata":
        items[0]["validation"]["max_length"] = 73
        items[6]["validation"]["max_lines"] = 6
        items[12]["validation"]["allowed_hosts"] = ["links.example.invalid"]
    if scenario == "environment":
        items[0]["base_source"] = "environment"
    if scenario == "pending":
        model.update(configured_generation=1, restart_required=True)
        items[6].update(configured_value="Configured first\nConfigured second", effective_value="Effective first\nEffective second", pending_value="Configured first\nConfigured second")
    node = shutil.which("node")
    assert node
    result = subprocess.run([node, str(Path(__file__).with_name("portal_settings_stage5_ui.cjs")),
        str(ROOT / "app/admin_web/static/portal_settings.js"), scenario, json.dumps(model)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_parallel_validation_table_or_unsafe_rendering():
    source = (ROOT / "app/admin_web/static/portal_settings.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "localStorage", "sessionStorage", "systemctl", ".trim()", "wa.me", "t.me", "facebook.com", "PORTAL_UI_TITLE", "restart(", "JSON.stringify(item.validation)"):
        assert forbidden not in source
    for required in ("textContent", "item.validation.max_length", "item.presentation_type", "item.configured_value", "item.effective_value", "item.pending_value", "item.base_source", "item.apply_requirement"):
        assert required in source


def test_portal_presentation_css_hooks_are_scoped_and_responsive():
    css = (ROOT / "app/admin_web/static/admin.css").read_text(encoding="utf-8")
    def rule(selector):
        matches = list(re.finditer(re.escape(selector) + r"\s*\{([^}]+)\}", css))
        assert matches, selector
        return "\n".join(match.group(1) for match in matches)
    assert "white-space: pre-wrap" in rule("#portal-settings-page .portal-setting-value")
    assert "font-size: .7rem" in rule("#portal-settings-page .portal-setting-key")
    assert "color: var(--muted)" in rule("#portal-settings-page .muted")
    textarea = rule("#portal-settings-page textarea.portal-setting-input")
    for required in ("font: inherit", "width: 100%", "max-width: 100%", "min-height", "padding", "border", "resize: vertical"):
        assert required in textarea
    assert "outline" in rule("#portal-settings-page textarea.portal-setting-input:focus-visible")
    assert "background" in rule("#portal-settings-page .portal-setting-input:disabled, #portal-settings-page select:disabled")
    assert "grid-template-columns: minmax(0, 1fr)" in rule("#portal-settings-page .portal-settings-grid")
    assert "@media (min-width: 1120px)" in css
    assert "repeat(3, minmax(0, 1fr))" in rule("#portal-settings-page .portal-settings-grid--branding")
    assert "repeat(2, minmax(0, 1fr))" in rule("#portal-settings-page .portal-settings-grid--support")
    assert "flex-wrap: wrap" in rule(".settings-tabs")
    assert "color: var(--ink)" in rule(".settings-tabs .nav-link")
    assert "outline" in rule(".settings-tabs .nav-link:focus-visible")
    assert "background: var(--accent)" in rule('.settings-tabs .nav-link[aria-current="page"]')
    assert "border-left" in rule("#portal-settings-page .portal-support-warning")
    assert "position: sticky" in rule("#portal-settings-page .portal-settings-actions")
    assert "bottom: 0" in rule("#portal-settings-page .portal-settings-actions")
    assert "scroll-margin-bottom" in rule("#portal-settings-page .portal-setting-input")
