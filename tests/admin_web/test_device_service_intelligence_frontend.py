import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_real_node_service_intelligence_coordinator():
    node = shutil.which("node")
    assert node is not None, "Node is required for the NI-04 frontend contract"
    result = subprocess.run([node, str(ROOT / "tests/admin_web/device_service_intelligence.cjs"),
        str(ROOT / "app/admin_web/static/admin.js")], cwd=ROOT, capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NI04_FRONTEND_PASS" in result.stdout


def test_existing_admin_js_prefix_and_ni03_assets_unchanged():
    import hashlib
    import subprocess
    source = (ROOT / "app/admin_web/static/admin.js").read_bytes()
    prefix = source.split(b"/* NI-04: independent bounded Service Intelligence coordinator. */")[0].rstrip()
    original = subprocess.check_output(["git", "show", "22cdde5d4168de02d142c840028a4d66167e47f7:app/admin_web/static/admin.js"], cwd=ROOT).rstrip()
    assert prefix.replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n")
    for name in ("app/admin_web/static/device_protocol_intelligence.js", "app/network_protocol_intelligence/read_service.py",
                 "app/network_protocol_intelligence/models.py", "app/network_metadata_projection/read_service.py"):
        accepted = subprocess.check_output(["git", "show", "22cdde5d4168de02d142c840028a4d66167e47f7:" + name], cwd=ROOT)
        current = ROOT.joinpath(name).read_bytes().replace(b"\r\n", b"\n")
        assert current == accepted.replace(b"\r\n", b"\n")


def test_full_admin_bundle_and_ni04_initializer_without_dom():
    node = shutil.which("node")
    assert node is not None, "Node is required for the DOM-less Admin contract"
    script = r'''
const assert = require("node:assert/strict"), fs = require("node:fs"), vm = require("node:vm");
const full = fs.readFileSync(process.argv[1], "utf8"), context = {window: {}};
vm.runInNewContext(full, context);
assert.equal(typeof context.document, "undefined");
assert.ok(context.window.CaptivPortalAdminTest, "Legacy Admin exports remain available without DOM");
const marker = "/* NI-04: independent bounded Service Intelligence coordinator. */";
const ni04 = full.slice(full.indexOf(marker));
assert.ok(ni04.startsWith(marker));
vm.runInNewContext(ni04, {window: new Proxy({}, {get() {throw new Error("DOM-less NI04 must not start browser work");}})});
console.log("NI04_NO_DOM_PASS");
'''
    result = subprocess.run([node, "-e", script, str(ROOT / "app/admin_web/static/admin.js")],
        cwd=ROOT, capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NI04_NO_DOM_PASS" in result.stdout


def test_ni04_css_before_byte_identical_ni03_suffix_and_scoped():
    import re
    marker = b"/* NI-03 presentation only;"
    current = (ROOT / "app/admin_web/static/admin.css").read_bytes().replace(b"\r\n", b"\n")
    accepted = subprocess.check_output(["git", "show", "22cdde5d4168de02d142c840028a4d66167e47f7:app/admin_web/static/admin.css"], cwd=ROOT)
    accepted = accepted.replace(b"\r\n", b"\n")
    assert current[current.index(marker):] == accepted[accepted.index(marker):]
    assert b"#device-service-intelligence" not in current[current.index(marker):]
    block = current[current.index(b"#device-service-intelligence"):current.index(marker)].decode("utf8")
    for selector in re.findall(r"([^{}]+)\{", block):
        if selector.strip().startswith("@media"):
            continue
        assert all(part.strip().startswith("#device-service-intelligence") for part in selector.split(","))
