import json
from pathlib import Path
import shutil
import subprocess
import pytest
from app.settings_control.definitions import SettingsDefinitionRegistry
from app.portal_presentation import portal_validation_metadata

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("scenario", ["changed", "clear", "noop", "conflict", "invalid", "outage", "readonly"])
def test_real_portal_script_uses_server_metadata_and_safe_dom(scenario):
    registry = SettingsDefinitionRegistry()
    items = [{"key": item.key, "display_label": item.display_label, "description": item.description,
        "group": item.group, "presentation_type": item.presentation_type, "configured_value": "<script>literal</script>" if index == 0 else item.repository_default_value,
        "effective_value": None, "pending_value": None, "persisted_override_value": "old" if index == 13 else None,
        "base_source": "repository_default", "apply_requirement": item.apply_requirement,
        "validation": portal_validation_metadata(item.key)} for index, item in enumerate(registry.for_domain("portal"))]
    model = {"api_version": "admin.settings.portal.v1", "settings": items, "configured_generation": 0, "effective_generation": None, "restart_required": False}
    node = shutil.which("node")
    assert node
    result = subprocess.run([node, str(Path(__file__).with_name("portal_settings_stage5_ui.cjs")),
        str(ROOT / "app/admin_web/static/portal_settings.js"), scenario, json.dumps(model)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_parallel_validation_table_or_unsafe_rendering():
    source = (ROOT / "app/admin_web/static/portal_settings.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "localStorage", "sessionStorage", "systemctl", ".trim()", "wa.me", "t.me", "facebook.com", "PORTAL_UI_TITLE", "restart("):
        assert forbidden not in source
    for required in ("textContent", "item.validation.max_length", "item.presentation_type", "item.configured_value", "item.effective_value", "item.pending_value", "item.base_source", "item.apply_requirement"):
        assert required in source
