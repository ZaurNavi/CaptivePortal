from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
if not NODE:
    bundled = Path(
        r"C:\Users\Zaur Navi\.cache\codex-runtimes\codex-primary-runtime"
        r"\dependencies\node\bin\node.exe"
    )
    if bundled.exists():
        NODE = str(bundled)


def test_admin_javascript_syntax_and_state_contract(tmp_path):
    if not NODE:
        pytest.skip("Node.js is required for Admin UI behavior tests")
    source_path = (
        Path(__file__).parents[2]
        / "app" / "admin_web" / "static" / "admin.js"
    )
    source = source_path.read_text(encoding="utf-8")
    script = tmp_path / "admin-ui-contract.js"
    script.write_text(
        "global.window = {};\n"
        + source
        + "\nconst api = window.CaptivPortalAdminTest;\n"
        + r"""
function assert(value, message) {
  if (!value) throw new Error(message);
}
assert(api.canonicalMac("aa-bb-cc-dd-ee-ff") === "AA:BB:CC:DD:EE:FF", "MAC canonicalization");
assert(api.canonicalMac("not-a-mac") === null, "invalid MAC rejected");
assert(api.classifyHttp(401, {}, null).kind === "session", "401 state");
assert(api.classifyHttp(403, {}, null).kind === "forbidden", "403 state");
assert(api.classifyHttp(429, {}, "1").message.includes("1 second"), "Retry-After state");
assert(api.classifyHttp(503, {error: {code: "query_deadline"}}, null).title === "Query timed out", "deadline state");
assert(api.classifyHttp(503, {error: {code: "source_unavailable"}}, null).kind === "unavailable", "unavailable state");
assert(api.classifyHttp(500, null, null).kind === "unexpected", "malformed state");
assert(api.display(null) === "—", "null is not numeric zero");
assert(api.display(0) === "0", "real zero is preserved");
const instant = new Date("2026-08-23T12:34:00.000Z");
assert(api.localDatetimeValue(instant) === "2026-08-23T16:34", "Baku local field value");
assert(api.utcFromLocal("2026-08-23T16:34") === "2026-08-23T12:34:00.000Z", "local round trip to UTC");

const all = api.parseVisitFilters("", "", "all");
assert(all.status === null && all.fromUtc === null && all.toUtc === null, "all omits optional filters");
const open = api.parseVisitFilters("2026-08-23T15:00", "2026-08-23T16:00", "open");
const closed = api.parseVisitFilters("2026-08-23T14:00", "2026-08-23T16:00", "closed");
assert(open.status === "open" && closed.status === "closed", "canonical visit statuses");
assert(open.fromUtc === "2026-08-23T11:00:00.000Z", "initialized local value becomes correct UTC");
let sourceCalls = 0;
try {
  api.parseVisitFilters("2026-08-23T15:00", "", "all");
  sourceCalls += 1;
} catch (error) {
  assert(error.uiFailure.title === "Incomplete time range", "paired time validation");
}
assert(sourceCalls === 0, "one boundary stops before fetch");

const visits = api.createVisitQueryState(open);
visits.setCursor("open-cursor");
const unchanged = visits.parameters();
assert(unchanged.get("status") === "open" && unchanged.get("cursor") === "open-cursor", "draft edits cannot change applied cursor state");
visits.apply(closed);
assert(visits.snapshot().cursor === null, "Apply resets cursor");
visits.setCursor("closed-cursor");
const more = visits.parameters();
assert(more.get("status") === "closed" && more.get("cursor") === "closed-cursor", "Load more preserves filters");
assert(more.get("from_utc") === closed.fromUtc && more.get("to_utc") === closed.toUtc, "Load more preserves time range");
visits.resetCursor();
const refreshed = visits.parameters();
assert(refreshed.get("status") === "closed" && !refreshed.has("cursor"), "Refresh repeats filters without old cursor");
const login = api.safeReturnPath({pathname: "/admin/sites/a/devices", search: "?mac=x"});
assert(login.startsWith("/admin/login?next="), "safe login return");
assert(!login.includes("http"), "no external login target");
console.log("admin ui contract passed");
""",
        encoding="utf-8",
    )
    checked = subprocess.run(
        [NODE, "--check", str(source_path)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1", "TZ": "Asia/Baku"},
    )
    completed = subprocess.run(
        [NODE, str(script)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1", "TZ": "Asia/Baku"},
    )
    assert checked.returncode == 0, checked.stderr
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "admin ui contract passed" in completed.stdout
