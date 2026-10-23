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


def _mask_fingerprint_span(prefix):
    start = b"  const FINGERPRINT_DIMENSIONS = ["
    end = b"  function parseVisitFilters("
    assert prefix.count(start) == prefix.count(end) == 1
    left, right = prefix.index(start), prefix.index(end)
    assert left < right
    return prefix[:left] + b"/* approved Fingerprint detail span */\n" + prefix[right:]


def _assert_legacy_prefix_unchanged(candidate, baseline):
    # Preserve the existing cross-platform line-ending policy, but mask only
    # the one approved Fingerprint span; all other prefix bytes stay protected.
    assert _mask_fingerprint_span(candidate).replace(b"\r\n", b"\n") == (
        _mask_fingerprint_span(baseline).replace(b"\r\n", b"\n"))


@pytest.mark.parametrize("side", ["before", "after"])
def test_prefix_guard_rejects_changes_outside_fingerprint_span(side):
    prefix = (ROOT / "app/admin_web/static/admin.js").read_bytes().split(
        b"/* NI-04: independent bounded Service Intelligence coordinator. */")[0].rstrip()
    offset = 0 if side == "before" else len(prefix) - 1
    assert offset < prefix.index(b"  const FINGERPRINT_DIMENSIONS = [") or offset >= prefix.index(b"  function parseVisitFilters(")
    changed = prefix[:offset] + bytes([prefix[offset] ^ 1]) + prefix[offset + 1:]
    with pytest.raises(AssertionError):
        _assert_legacy_prefix_unchanged(changed, prefix)


def test_prefix_guard_accepts_only_the_approved_fingerprint_span():
    start, end = b"  const FINGERPRINT_DIMENSIONS = [", b"  function parseVisitFilters("
    prefix = b"protected-before\n" + start + b"old details\n" + end + b"protected-after"
    changed = b"protected-before\n" + start + b"new details\n" + end + b"protected-after"
    _assert_legacy_prefix_unchanged(changed, prefix)
    assert _mask_fingerprint_span(prefix) == (
        b"protected-before\n/* approved Fingerprint detail span */\n" + end + b"protected-after")


@pytest.mark.parametrize("malformed", ["missing_start", "missing_end", "duplicate_start", "duplicate_end", "reversed"])
def test_prefix_guard_requires_unique_ordered_fingerprint_boundaries(malformed):
    start, end = b"  const FINGERPRINT_DIMENSIONS = [", b"  function parseVisitFilters("
    prefix = start + b"details\n" + end
    changed = {
        "missing_start": end,
        "missing_end": start,
        "duplicate_start": start + prefix,
        "duplicate_end": prefix + end,
        "reversed": end + start,
    }[malformed]
    with pytest.raises(AssertionError):
        _assert_legacy_prefix_unchanged(changed, prefix)
    with pytest.raises(AssertionError):
        _assert_legacy_prefix_unchanged(prefix, changed)


def _without_rich_hints_insertions(candidate):
    """TL-approved exception: remove only two additive, exact line spans."""
    begin = b"  // DF-RICH-HINTS-01:BEGIN\n"
    end = b"  // DF-RICH-HINTS-01:END\n\n"
    call = b"    content.append(observedDeviceHintsCard(result.observed_device_hints));\n"
    assert candidate.count(b"// DF-RICH-HINTS-01:BEGIN") == candidate.count(begin) == 1
    assert candidate.count(b"// DF-RICH-HINTS-01:END") == candidate.count(end) == 1
    assert candidate.count(b"content.append(observedDeviceHintsCard(result.observed_device_hints));") == candidate.count(call) == 1
    start, stop, call_start = candidate.index(begin), candidate.index(end), candidate.index(call)
    assert start < stop and stop + len(end) < call_start
    assert start == 0 or candidate[start - 1:start] == b"\n"
    assert candidate[call_start - 1:call_start] == b"\n"
    # Includes exactly the inserted newlines; no old JS span is masked.
    return candidate[:start] + candidate[stop + len(end):call_start] + candidate[call_start + len(call):]


def _rich_hints_base_prefixes():
    source = (ROOT / "app/admin_web/static/admin.js").read_bytes()
    prefix = source.split(b"/* NI-04: independent bounded Service Intelligence coordinator. */")[0].rstrip()
    # Additional exact guard against the repinned base that admitted PR #222.
    # The original historical commit/PR222 span guard below is not replaced.
    original = subprocess.check_output(["git", "show", "ae1f99491318e32e247ea5d5877d53650cc8d78e:app/admin_web/static/admin.js"], cwd=ROOT).split(
        b"/* NI-04: independent bounded Service Intelligence coordinator. */")[0].rstrip()
    # Preserve the existing CRLF-only checkout policy, without new normalization.
    return _without_visit_hook(prefix.replace(b"\r\n", b"\n")), original.replace(b"\r\n", b"\n")


def _without_visit_hook(prefix):
    # #296 authorizes exactly one additive Visit-row hook, not a replacement
    # of the old row renderer, Fingerprint span, or NI04 runtime.
    hook = b'''    // VISIT-NETWORK-296:BEGIN
    const network = node("section", "visit-network-results");
    network.dataset.visitId = item.visit_id || "";
    network.dataset.deviceId = item.device_id || "";
    network.dataset.visitStatus = item.status || "";
    network.setAttribute("aria-label", "Visit network results");
    value.append(network);
    // VISIT-NETWORK-296:END
'''
    assert prefix.count(b"// VISIT-NETWORK-296:BEGIN") == prefix.count(b"// VISIT-NETWORK-296:END") == prefix.count(hook) == 1
    assert prefix.index(b"  function visitRow(item)") < prefix.index(hook) < prefix.index(b"  async function loadVisits(")
    return prefix.replace(hook, b"", 1)


@pytest.mark.parametrize("before,after", [
    (b'    return value;\n  }\n\n  async function loadVisits', b'    return null;\n  }\n\n  async function loadVisits'),
    (b'item.reported_traffic_total_bytes', b'item.changed_traffic'),
    (b'content.append(fingerprintCard(result.fingerprint));', b'content.append(fingerprintCard(null));'),
])
def test_visit_hook_exception_preserves_every_existing_renderer_byte(before, after):
    source = (ROOT / "app/admin_web/static/admin.js").read_bytes().replace(b"\r\n", b"\n")
    assert source.count(before) == 1
    assert _without_visit_hook(source) != _without_visit_hook(source.replace(before, after, 1))


def test_visit_hook_exception_rejects_changed_or_duplicate_hook():
    source = (ROOT / "app/admin_web/static/admin.js").read_bytes().replace(b"\r\n", b"\n")
    for changed in (source.replace(b'network.dataset.visitId = item.visit_id', b'network.dataset.visitId = item.device_id'),
                    source + b'// VISIT-NETWORK-296:BEGIN'):
        with pytest.raises(AssertionError):
            _without_visit_hook(changed)


@pytest.mark.parametrize("old,new", [
    (b'  const resolved = {', b'  const resolved = { /* canary */'),
    (b'  function fingerprintCard(fingerprint)', b'  function fingerprintCard(changed)'),
    (b'card("Fingerprint Information",', b'card("Changed canonical Fingerprint",'),
    (b'  function parseVisitFilters(', b'  function changedVisitFilters('),
    (b'content.append(fingerprintCard(result.fingerprint));', b'content.append(fingerprintCard(null));'),
    (b'card("Latest Site snapshot",', b'card("Changed Site snapshot",'),
])
def test_rich_hints_exception_rejects_every_external_canary_including_canonical_fingerprint(old, new):
    prefix, original = _rich_hints_base_prefixes()
    assert prefix.count(old) == 1
    assert _without_rich_hints_insertions(prefix) == original
    with pytest.raises(AssertionError):
        assert _without_rich_hints_insertions(prefix.replace(old, new, 1)) == original


@pytest.mark.parametrize("case", ["missing_begin", "duplicate_begin", "missing_end", "duplicate_end",
                                  "end_newlines", "wrong_call_indent", "missing_call", "duplicate_call",
                                  "reversed", "call_before_block"])
def test_rich_hints_exception_rejects_nonexact_or_nonunique_boundaries(case):
    prefix, _ = _rich_hints_base_prefixes()
    begin = b"  // DF-RICH-HINTS-01:BEGIN\n"
    end = b"  // DF-RICH-HINTS-01:END\n\n"
    call = b"    content.append(observedDeviceHintsCard(result.observed_device_hints));\n"
    changes = {
        "missing_begin": (begin, b""), "duplicate_begin": (begin, begin * 2),
        "missing_end": (end, b""), "duplicate_end": (end, end * 2),
        "end_newlines": (end, end[:-1]), "wrong_call_indent": (call, call[1:]),
        "missing_call": (call, b""), "duplicate_call": (call, call * 2),
    }
    if case == "reversed":
        changed = prefix.replace(begin, b"TEMP_ANCHOR\n", 1).replace(end, begin, 1).replace(b"TEMP_ANCHOR\n", end, 1)
    elif case == "call_before_block":
        changed = prefix.replace(call, b"", 1).replace(begin, call + begin, 1)
    else:
        old, new = changes[case]
        changed = prefix.replace(old, new, 1)
    with pytest.raises(AssertionError):
        _without_rich_hints_insertions(changed)


def test_rich_hints_exception_is_limited_to_the_approved_additions():
    prefix, original = _rich_hints_base_prefixes()
    assert _without_rich_hints_insertions(prefix) == original
    changed_addition = prefix.replace(b'card("Observed Device Hints /', b'card("Allowed addition canary /', 1)
    assert changed_addition != prefix
    assert _without_rich_hints_insertions(changed_addition) == original


def _assert_frozen_ni03_asset_unchanged(name, current):
    # Keep complete-file canaries. #296 replaces the NI03 UI with the exact
    # reviewed Visit coordinator and adds one exact Visit reader to #293's
    # frozen shared reader; no arbitrary current-source span is masked.
    references = {
        "app/admin_web/static/device_protocol_intelligence.js": "9c54033c0a7f257c77f6487e254ddadb02ed54d4",
        "app/network_protocol_intelligence/models.py": "5c7b4c46afa5a57d55fe044c4326da3a10b9e145",
        "app/network_protocol_intelligence/read_service.py": "cc199c200bab71fe44b58bbd3e7d5c4b7ec44a19",
        "app/network_metadata_projection/read_service.py": "cc199c200bab71fe44b58bbd3e7d5c4b7ec44a19",
    }
    assert name in references
    accepted = subprocess.check_output(["git", "show", references[name] + ":" + name], cwd=ROOT)
    if name == "app/network_metadata_projection/read_service.py":
        reviewed = subprocess.check_output(["git", "show", "9c54033c0a7f257c77f6487e254ddadb02ed54d4:" + name], cwd=ROOT)
        begin, end = b"    def read_visit_protocol_snapshot(", b"    def _list("
        assert reviewed.count(begin) == reviewed.count(end) == accepted.count(end) == 1
        assert begin not in accepted and reviewed.index(begin) < reviewed.index(end)
        addition = reviewed[reviewed.index(begin):reviewed.index(end)]
        accepted = accepted.replace(end, addition + end, 1)
    # Preserve only the pre-existing CRLF checkout policy; no source masking.
    assert current.replace(b"\r\n", b"\n") == accepted.replace(b"\r\n", b"\n")


@pytest.mark.parametrize("name", [
    "app/admin_web/static/device_protocol_intelligence.js",
    "app/network_protocol_intelligence/models.py",
    "app/network_protocol_intelligence/read_service.py",
    "app/network_metadata_projection/read_service.py",
])
@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_ni03_asset_freeze_rejects_changes_to_each_complete_reviewed_file(name, position):
    current = ROOT.joinpath(name).read_bytes()
    _assert_frozen_ni03_asset_unchanged(name, current)
    offset = {"start": 0, "middle": len(current) // 2, "end": len(current) - 1}[position]
    changed = current[:offset] + bytes([current[offset] ^ 1]) + current[offset + 1:]
    with pytest.raises(AssertionError):
        _assert_frozen_ni03_asset_unchanged(name, changed)


def test_ni03_asset_freeze_rejects_paths_outside_the_exact_contract():
    with pytest.raises(AssertionError):
        _assert_frozen_ni03_asset_unchanged("app/network_service_recognition/read_service.py", b"")


def test_existing_admin_js_prefix_and_ni03_assets_unchanged():
    import hashlib
    import subprocess
    prefix, admitted = _rich_hints_base_prefixes()
    without_additions = _without_rich_hints_insertions(prefix)
    assert without_additions == admitted
    original = subprocess.check_output(["git", "show", "22cdde5d4168de02d142c840028a4d66167e47f7:app/admin_web/static/admin.js"], cwd=ROOT).rstrip()
    _assert_legacy_prefix_unchanged(without_additions, original)
    for name in ("app/admin_web/static/device_protocol_intelligence.js", "app/network_protocol_intelligence/read_service.py",
                 "app/network_protocol_intelligence/models.py", "app/network_metadata_projection/read_service.py"):
        _assert_frozen_ni03_asset_unchanged(name, ROOT.joinpath(name).read_bytes())


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
