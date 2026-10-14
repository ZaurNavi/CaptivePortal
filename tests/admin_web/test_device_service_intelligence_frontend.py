import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def test_real_node_ni05_organization_context():
    node = shutil.which("node")
    assert node is not None, "Node is required for the NI-05 frontend contract"
    result = subprocess.run(
        [node, str(ROOT / "tests/admin_web/ni05_organization_context.cjs"),
         str(ROOT / "app/admin_web/static/admin.js")],
        cwd=ROOT, capture_output=True, text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NI05_ORGANIZATION_CONTEXT_PASS" in result.stdout


def test_ni05_preserves_ni04_lifecycle_and_coverage_bytes():
    marker = "/* NI-04: independent bounded Service Intelligence coordinator. */"
    current = (ROOT / "app/admin_web/static/admin.js").read_text(encoding="utf8").split(marker)[1]
    accepted = subprocess.check_output(
        ["git", "show", "3b5f70cec467939995fecc7667169239000b7308:app/admin_web/static/admin.js"],
        cwd=ROOT, text=True,
    ).split(marker)[1]
    assert current[current.index("  function clearTimer()"):] == accepted[accepted.index("  function clearTimer()"):]
    assert current[current.index("  function coverageMessage("):current.index("  function render(v, stale)")] == (
        accepted[accepted.index("  function coverageMessage("):accepted.index("  function render(v, stale)")]
    )
    assert current.count("window.fetch(") == accepted.count("window.fetch(") == 1


@pytest.mark.parametrize("name", [
    "organizations/generic.svg", "services/generic.svg",
    "services/instagram.svg", "services/whatsapp.svg",
])
def test_ni05_local_svg_is_passive(name):
    import xml.etree.ElementTree as ET
    source = (ROOT / "app/admin_web/static/icons" / name).read_text(encoding="utf8")
    svg = ET.fromstring(source)
    assert svg.tag == "{http://www.w3.org/2000/svg}svg"
    assert "viewBox" in svg.attrib
    allowed = {"svg", "path", "rect", "defs", "style"}
    for element in svg.iter():
        assert element.tag.rsplit("}", 1)[-1] in allowed
        for key, value in element.attrib.items():
            assert not key.lower().startswith("on")
            assert key.rsplit("}", 1)[-1] not in {"href", "src"}
            assert not any(token in value.lower() for token in ("javascript:", "data:", "http:", "https:", "url("))
    assert not any(token in source.lower() for token in ("@import", "url(", "foreignobject", "<script", "<!entity"))


def test_ni05_generic_brand_exceptions_and_provenance_are_explicit():
    text = (ROOT / "app/admin_web/static/icons/README.md").read_text(encoding="utf8")
    for token in ("Owner Exception 01", "Owner Exception 02", "clause 6",
                  "Instagram_Glyph_Black.svg", "Digital_Glyph_Green_RGB_2026.svg"):
        assert token in text
    for name in ("organizations/google.svg", "organizations/meta.svg", "services/youtube.svg"):
        assert not (ROOT / "app/admin_web/static/icons" / name).exists()


@pytest.mark.parametrize("name", [
    "organizations/generic.svg", "services/generic.svg",
    "services/instagram.svg", "services/whatsapp.svg",
])
def test_ni05_assets_use_existing_flask_static_boundary(admin_app, name):
    response = admin_app.test_client().get(
        "/admin/static/icons/" + name, base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.data == (ROOT / "app/admin_web/static/icons" / name).read_bytes()


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
        # Recovery freezes the current accepted baseline, including the admitted
        # Wave-1 idle-source guard in the shared projection reader.
        accepted = subprocess.check_output(["git", "show", "5c7b4c46afa5a57d55fe044c4326da3a10b9e145:" + name], cwd=ROOT)
        current = ROOT.joinpath(name).read_bytes().replace(b"\r\n", b"\n")
        accepted = accepted.replace(b"\r\n", b"\n")
        if name == "app/network_metadata_projection/read_service.py":
            # Architecture Exception V1 explicitly authorizes only internal
            # Core/projection V2 admission. All other shared-reader bytes and
            # every NI-03/UI source above remain frozen.
            for before, after in (
                (b"schema_version=None, projection_contract_version=1,", b"schema_version=None, projection_contract_version=2,"),
                (b"defaults.update(store_state=\"available\", schema_version=1, db_bytes=total)",
                 b"defaults.update(store_state=\"available\", schema_version=2, db_bytes=total)"),
            ):
                assert accepted.count(before) == current.count(after) == 1
                accepted = accepted.replace(before, after, 1)
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
