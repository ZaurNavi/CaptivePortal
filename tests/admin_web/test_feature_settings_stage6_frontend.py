"""Dedicated feature JS integration: real script, synthetic DOM, no I/O."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from app.settings_control.definitions import SettingsDefinitionRegistry

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("scenario", ["changed", "reset", "reset_then_toggle", "conflict", "invalid",
    "outage", "readonly", "refresh", "parent_no_cascade", "loadoutage"])
def test_real_features_script_local_candidate_and_server_owned_states(scenario):
    rows = []
    for index, item in enumerate(SettingsDefinitionRegistry().for_domain("features")):
        rows.append({"key": item.key, "display_label": "<script>literal label</script>" if index == 0 else item.display_label,
            "description": item.description, "group": item.group, "configured_value": index == 5,
            "effective_value": None if index == 1 else False, "base_value": False,
            "persisted_override_value": True if index == 16 else None,
            "configured_source": "persisted_override" if index == 16 else "repository_default",
            "pending_value": True if index == 5 else None,
            "configured_feature_state": "dormant_parent_disabled" if index == 5 else "disabled",
            "effective_feature_state": "runtime_unavailable" if index == 1 else "disabled",
            "configured_blocked_by_feature_keys": ["WEB_ADMIN_TRAFFIC_ENABLED"] if index == 5 else [],
            "effective_blocked_by_feature_keys": []})
    model = {"api_version": "admin.settings.features.v1", "etag": '"settings-g0"', "features": rows}
    node = shutil.which("node")
    assert node
    result = subprocess.run([node, str(Path(__file__).with_name("feature_settings_stage6_ui.cjs")),
        str(ROOT / "app/admin_web/static/features_settings.js"), scenario, json.dumps(model)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_script_no_parallel_graph_unsafe_dom_restart_or_polling():
    source = (ROOT / "app/admin_web/static/features_settings.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
        "localStorage", "sessionStorage", "systemctl", "setInterval", "WEB_ADMIN_", "parent_feature_keys"):
        assert forbidden not in source
    for required in ("textContent", "configured_blocked_by_feature_keys", "effective_blocked_by_feature_keys",
        "configured_feature_state", "effective_feature_state", "crypto.randomUUID()", "clear_override"):
        assert required in source
