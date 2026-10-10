import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_real_node_protocol_frontend_contract():
    node = shutil.which("node") or str(Path(os.environ["LOCALAPPDATA"]) / "Codex/dependencies/node/bin/node.exe")
    result = subprocess.run([node, str(ROOT / "tests/admin_web/device_protocol_intelligence.cjs"),
        str(ROOT / "app/admin_web/static/device_protocol_intelligence.js")], cwd=ROOT,
        capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NI03_FRONTEND_PASS" in result.stdout


def test_static_privacy_no_persistence_or_unsafe_html():
    source = (ROOT / "app/admin_web/static/device_protocol_intelligence.js").read_text()
    for forbidden in ("innerHTML", "localStorage", "sessionStorage", "indexedDB", "document.cookie", "pushState", "console.log"):
        assert forbidden not in source
