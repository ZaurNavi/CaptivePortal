"""Exercise the actual browser script in a disposable DOM and fetch stub."""
from pathlib import Path
import subprocess
import pytest


@pytest.mark.parametrize("scenario", ["success", "noop", "conflict", "cancel", "clear", "outage", "readonly", "mutation-unavailable"])
def test_controller_browser_save_reload_behavior(scenario):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["node", str(Path(__file__).with_name("controller_settings_stage3_ui.cjs")),
        str(root / "app/admin_web/static/controller_settings.js"), scenario], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
