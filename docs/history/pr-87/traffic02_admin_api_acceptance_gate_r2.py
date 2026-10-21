from __future__ import annotations

import hashlib
import logging
import sqlite3
import statistics
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.analytics.historical_traffic import HistoricalTrafficReadService
from app.analytics.source_gateway import AnalyticsSourceGateway
from tests.admin_web.conftest import enabled_settings, login

REPO = Path(r"C:\CaptivPortal-UI-Preview")
DB = Path(r"C:\CaptivPortal-Lab\artifacts\traffic02-observations-prod-20260829.sqlite3")
EXPECTED_HEAD = "71c5d41c510bba414420af0e8e27a269646c6791"
EXPECTED_TREE = "df35a9778ce91acf8cf5b76e3c37cda2c90c7068"
EXPECTED_SNAPSHOT_SHA256 = "74cd3325e6a5752d21d33a4c170872d8617cd3181f2384238a89cf071c7750e6"
SITE_ID = "6a64f17630da7c70d232187a"
RUNS = 5
ADMIN_DEADLINE_SECONDS = 10
BROWSER_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 1_048_576
RANGES = {
    "24h": {"seconds": 86_400, "bucket_seconds": 300, "bucket_count": 288},
    "7d": {"seconds": 604_800, "bucket_seconds": 900, "bucket_count": 672},
}
STATUS_TO_COVERAGE = {"ok": "complete", "partial": "partial", "insufficient_data": "none"}


def fail(message: str) -> None:
    raise SystemExit("FAIL: " + message)


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        fail("git command failed: " + " ".join(args) + "\n" + p.stdout + p.stderr)
    return p.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def p95(values: list[float]) -> float:
    return values[0] if len(values) == 1 else statistics.quantiles(values, n=100, method="inclusive")[94]


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class SnapshotRead:
    @contextmanager
    def analytics_read_connection(self):
        uri = DB.resolve().as_uri() + "?mode=ro"
        c = sqlite3.connect(uri, uri=True)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()


def build_service() -> HistoricalTrafficReadService:
    return HistoricalTrafficReadService(
        AnalyticsSourceGateway(SnapshotRead(), None, None),
        quality_gap_threshold_seconds=180.0,
        max_query_duration_seconds=float(ADMIN_DEADLINE_SECONDS),
    )


def build_app(service: HistoricalTrafficReadService, *, admin_deadline_seconds: int) -> Flask:
    settings = enabled_settings(
        web_admin_allowed_site_ids=SITE_ID,
        web_admin_default_site_id=SITE_ID,
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_max_query_duration_seconds=str(admin_deadline_seconds),
        web_admin_max_response_bytes=str(MAX_RESPONSE_BYTES),
        web_admin_traffic_request_timeout_seconds=str(BROWSER_TIMEOUT_SECONDS),
    )
    analytics_runtime = SimpleNamespace(
        state="active",
        visit_service=object(),
        historical_traffic_service=service,
        current_traffic_service=None,
    )

    # Admin Web composition requires concrete repository boundaries even though
    # this gate exercises only the Historical Traffic endpoint. Point all
    # unused read gateways at the immutable snapshot; the History request itself
    # is served by historical_traffic_service.
    registry_read_service = SimpleNamespace(
        repository=SimpleNamespace(
            config=SimpleNamespace(db_path=DB),
        )
    )
    visit_read_service = SimpleNamespace(
        repository=SimpleNamespace(db_path=DB),
    )
    observation_read_service = SimpleNamespace(
        _repository=SimpleNamespace(db_path=DB),
    )

    runtime = create_admin_web_runtime(
        settings,
        analytics_runtime,
        registry_read_service,
        visit_read_service,
        observation_read_service,
        logging.getLogger(f"traffic02-api-gate-{admin_deadline_seconds}s"),
    )

    if runtime.state != "active" or runtime.query_service is None:
        fail(
            "Admin Web runtime composition failed before API execution "
            f"(state={runtime.state!r}, query_service={runtime.query_service!r})"
        )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def validate_payload(label: str, raw: bytes, payload: dict) -> dict:
    expected = RANGES[label]
    if len(raw) >= MAX_RESPONSE_BYTES:
        fail(f"{label}: final HTTP response is not <1MiB ({len(raw)} bytes)")
    if payload.get("api_version") != "admin.read.v1" or payload.get("site_id") != SITE_ID:
        fail(f"{label}: envelope mismatch")
    result = payload.get("result")
    if not isinstance(result, dict):
        fail(f"{label}: result missing")
    status = result.get("status")
    if status not in STATUS_TO_COVERAGE:
        fail(f"{label}: invalid status {status!r}")
    r = result.get("range")
    coverage = result.get("coverage")
    buckets = result.get("buckets")
    if not isinstance(r, dict) or not isinstance(coverage, dict) or not isinstance(buckets, list):
        fail(f"{label}: malformed product result")
    if r.get("id") != label or r.get("unit") != "Mbps":
        fail(f"{label}: range id/unit mismatch")
    if r.get("bucket_seconds") != expected["bucket_seconds"] or r.get("bucket_count") != expected["bucket_count"]:
        fail(f"{label}: bucket contract mismatch")
    if len(buckets) != expected["bucket_count"]:
        fail(f"{label}: serialized bucket length mismatch")
    start, end, evaluated = parse_utc(r["from_utc"]), parse_utc(r["to_utc"]), parse_utc(r["evaluated_at_utc"])
    if int((end - start).total_seconds()) != expected["seconds"] or evaluated != end:
        fail(f"{label}: server UTC range contract mismatch")
    if coverage.get("status") != STATUS_TO_COVERAGE[status]:
        fail(f"{label}: status/coverage mismatch")
    complete = coverage.get("complete_bucket_count")
    partial = coverage.get("partial_bucket_count")
    missing = coverage.get("missing_bucket_count")
    if not all(type(v) is int and v >= 0 for v in (complete, partial, missing)):
        fail(f"{label}: coverage counters invalid")
    if complete + partial + missing != expected["bucket_count"]:
        fail(f"{label}: coverage counters do not sum")
    return {
        "status": status,
        "coverage": coverage.get("status"),
        "bucket_count": len(buckets),
        "complete_buckets": complete,
        "partial_buckets": partial,
        "missing_buckets": missing,
        "gap_bucket_count": coverage.get("gap_bucket_count"),
        "source_transition_count": coverage.get("source_transition_count"),
        "source_watermark_utc": coverage.get("source_watermark_utc"),
        "source_age_seconds": coverage.get("source_age_seconds"),
        "response_bytes": len(raw),
    }


print("============================================================")
print("TASK-TRAFFIC-02 R3 — ADMIN API PRODUCTION-SNAPSHOT GATE")
print("============================================================")

print("\n=== EXACT ARTIFACT PRECHECK ===")
status_before = git("status", "--porcelain")
head_before = git("rev-parse", "HEAD")
tree_before = git("rev-parse", "HEAD^{tree}")
print("status =", "CLEAN" if not status_before else status_before)
print("HEAD =", head_before)
print("tree =", tree_before)
if status_before or head_before != EXPECTED_HEAD or tree_before != EXPECTED_TREE:
    fail("exact R3 artifact precheck failed")

print("\n=== SNAPSHOT PRECHECK ===")
if not DB.is_file():
    fail("production snapshot missing")
print("db =", DB)
print("size_bytes =", DB.stat().st_size)
snapshot_sha_before = sha256_file(DB)
print("sha256_before =", snapshot_sha_before)
if snapshot_sha_before != EXPECTED_SNAPSHOT_SHA256:
    fail("snapshot SHA256 mismatch")
uri = DB.resolve().as_uri() + "?mode=ro"
c = sqlite3.connect(uri, uri=True)
try:
    integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
    user_version = c.execute("PRAGMA user_version").fetchone()[0]
    latest = c.execute(
        """SELECT MAX(finished_at) FROM observation_cycles
           WHERE site_id=? AND kind='ap_dynamic' AND state='completed'
             AND complete=1 AND result='success' AND finished_at IS NOT NULL""",
        (SITE_ID,),
    ).fetchone()[0]
finally:
    c.close()
print("integrity_check =", integrity)
print("user_version =", user_version)
print("latest_complete_ap_dynamic =", latest)
if integrity != "ok" or int(user_version) != 1 or latest is None:
    fail("snapshot preconditions failed")

service = build_service()
app = build_app(service, admin_deadline_seconds=ADMIN_DEADLINE_SECONDS)
client = app.test_client()
login_response = login(client)
print("\n=== ADMIN SESSION ===")
print("login_status =", login_response.status_code)
if login_response.status_code != 302:
    fail("Admin login failed")

for label in ("24h", "7d"):
    durations = []
    samples = []
    print(f"\n=== API RANGE {label} ===")
    for i in range(1, RUNS + 1):
        t0 = time.perf_counter()
        response = client.get(
            f"/admin/api/v1/sites/{SITE_ID}/traffic/history?range={label}",
            base_url="https://localhost",
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        durations.append(elapsed)
        raw = response.get_data()
        print(f"run_{i}: status={response.status_code} duration_ms={elapsed:.2f} response_bytes={len(raw)}")
        if response.status_code != 200:
            print(raw.decode("utf-8", errors="replace"))
            fail(f"{label}: HTTP {response.status_code}")
        payload = response.get_json()
        if not isinstance(payload, dict):
            fail(f"{label}: response is not JSON object")
        samples.append(validate_payload(label, raw, payload))
    sample = samples[-1]
    median_ms, p95_ms, max_ms = statistics.median(durations), p95(durations), max(durations)
    print("p50_ms =", f"{median_ms:.2f}")
    print("p95_ms =", f"{p95_ms:.2f}")
    print("max_ms =", f"{max_ms:.2f}")
    print("admin_deadline_seconds =", ADMIN_DEADLINE_SECONDS)
    print("browser_timeout_seconds =", BROWSER_TIMEOUT_SECONDS)
    for key, value in sample.items():
        print(key, "=", value)
    print("response_under_1MiB =", sample["response_bytes"] < MAX_RESPONSE_BYTES)
    if max_ms >= ADMIN_DEADLINE_SECONDS * 1000.0:
        fail(f"{label}: end-to-end API exceeded shared 10s budget")

print("\n=== PUBLIC CONTRACT NEGATIVE CHECKS ===")
checks = {
    "missing_range": client.get(f"/admin/api/v1/sites/{SITE_ID}/traffic/history", base_url="https://localhost"),
    "range_30d": client.get(f"/admin/api/v1/sites/{SITE_ID}/traffic/history?range=30d", base_url="https://localhost"),
    "unknown_query": client.get(f"/admin/api/v1/sites/{SITE_ID}/traffic/history?range=24h&from_utc=x", base_url="https://localhost"),
}
for name, response in checks.items():
    print(name, "=", response.status_code)
if tuple(response.status_code for response in checks.values()) != (400, 400, 400):
    fail("public query allowlist contract failed")

print("\n=== SHARED ADMIN DEADLINE PROPAGATION CHECK ===")
deadline_app = build_app(service, admin_deadline_seconds=1)
deadline_client = deadline_app.test_client()
if login(deadline_client).status_code != 302:
    fail("deadline-check login failed")
t0 = time.perf_counter()
deadline_response = deadline_client.get(
    f"/admin/api/v1/sites/{SITE_ID}/traffic/history?range=7d",
    base_url="https://localhost",
)
deadline_ms = (time.perf_counter() - t0) * 1000.0
deadline_body = deadline_response.get_data(as_text=True)
print("deadline_http_status =", deadline_response.status_code)
print("deadline_duration_ms =", f"{deadline_ms:.2f}")
print("deadline_body =", deadline_body)
if deadline_response.status_code != 503 or "query_deadline" not in deadline_body:
    fail("shared Admin deadline did not surface as query_deadline")

print("\n=== SNAPSHOT IMMUTABILITY ===")
snapshot_sha_after = sha256_file(DB)
print("sha256_after =", snapshot_sha_after)
print("immutable =", snapshot_sha_after == snapshot_sha_before == EXPECTED_SNAPSHOT_SHA256)
if snapshot_sha_after != snapshot_sha_before:
    fail("snapshot changed")

print("\n=== EXACT ARTIFACT POSTCHECK ===")
status_after = git("status", "--porcelain")
head_after = git("rev-parse", "HEAD")
tree_after = git("rev-parse", "HEAD^{tree}")
print("status =", "CLEAN" if not status_after else status_after)
print("HEAD =", head_after)
print("tree =", tree_after)
if status_after or head_after != EXPECTED_HEAD or tree_after != EXPECTED_TREE:
    fail("exact R3 artifact postcheck failed")

print("\n============================================================")
print("OVERALL = PASS")
print("============================================================")
