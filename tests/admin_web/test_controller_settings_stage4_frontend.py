"""Execute the real write-only browser controller with disposable DOM/fetch."""
from pathlib import Path
import subprocess
import pytest


@pytest.mark.parametrize("scenario", [
    "readonly", "ordinary-writer", "secret-writer", "mismatch", "replace-cancel",
    "clear-cancel", "cancel", "changed", "replay", "clear-success",
    "error-422", "error-403", "error-409", "error-412", "error-413", "error-500", "error-503",
    "network-retry", "clear-network-retry", "network-switch-clear", "network-switch-replace",
    "network-cancel", "network-definitive",
])
def test_controller_secret_browser_behavior(scenario):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([
        "node", str(Path(__file__).with_name("controller_settings_stage4_ui.cjs")),
        str(root / "app/admin_web/static/controller_settings.js"),
        str(root / "app/admin_web/templates/admin/settings_controller.html"), scenario,
    ], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
