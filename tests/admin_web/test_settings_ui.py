from pathlib import Path
import shutil
import subprocess
from .test_settings_routes import settings_app


def test_settings_script_isolation_and_global_shell(tmp_path):
    _app, client, _runtime, _boot, _csrf = settings_app(tmp_path)
    page = client.get("/admin/settings", base_url="https://localhost")
    assert b"settings.js" in page.data and b"admin.js" not in page.data
    assert b"Global Settings" in page.data and b'data-csrf-token="' in page.data
    assert b'data-site-id="' not in page.data and b"/admin/sites/" not in page.data
    assert b"Save changes" in page.data and b"restart by an operator" in page.data
    ordinary = client.get("/admin/sites/0123456789abcdef01234567/", base_url="https://localhost")
    assert b"admin.js" in ordinary.data and b"settings.js" not in ordinary.data


def test_dedicated_js_metadata_and_security_contract():
    root = Path(__file__).resolve().parents[2]
    source = (root / "app/admin_web/static/settings.js").read_text(encoding="utf-8")
    for required in ("crypto.randomUUID()", '"X-CSRF-Token"', '"If-Match"', '"Idempotency-Key"',
                     'error.status === 412', "await load()", "item.validation.min", "item.validation.max",
                     'pagination: "Pagination / Presentation"', 'refresh: "Refresh Cadence"',
                     'node("h2", groupTitles[item.group])'):
        assert required in source
    for forbidden in ("innerHTML", "localStorage", "sessionStorage", "systemctl", "location.reload",
                      "item.validation.min_value", "item.validation.max_value"):
        assert forbidden not in source
    assert "const changes" in source and 'method: "POST"' in source
    node = shutil.which("node")
    assert node
    subprocess.run([node, "--check", str(root / "app/admin_web/static/settings.js")], check=True)
