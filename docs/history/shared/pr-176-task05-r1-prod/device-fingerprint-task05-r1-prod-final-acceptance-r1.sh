#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
PORTAL_UNIT="captive-portal.service"
WORKER="fingerprint-classification.service"

EXPECTED_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
EXPECTED_TREE="545a48caf86adc247083db611e87a8d36820f353"

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CLASSIFICATION_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"

OLD_IID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"
NEW_IID="e8ac5702-6ab5-4af9-94ae-0582df4666af"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_R1_FINAL_ACCEPTANCE"
echo "DATABASE_WRITE=NO"
echo "CONFIG_WRITE=NO"
echo "SERVICE_WRITE=NO"
echo "TARGET_NEW_INTEGRATION_ID=$NEW_IID"

section "RUNTIME IDENTITY"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "PRODUCTION_HEAD=$HEAD"
echo "PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected production tree"
[ -z "$STATUS" ] || fail "Production worktree dirty"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" || fail "Integration not enabled"
systemctl is-active --quiet "$PORTAL_UNIT" || fail "Portal inactive"
systemctl is-active --quiet "$WORKER" || fail "Worker inactive"
systemctl is-enabled --quiet "$WORKER" || fail "Worker not enabled"
echo "PORTAL_NRESTARTS=$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS=$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
[ "$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)" = "0" ] || fail "Portal restarted"
[ "$(systemctl show "$WORKER" -p NRestarts --value --no-pager)" = "0" ] || fail "Worker restarted"
echo "RUNTIME_IDENTITY=PASS"

section "NEW CONTROLLED JOB"
INTEGRATION_DB="$INTEGRATION_DB" NEW_IID="$NEW_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute("""SELECT integration_id,auth_session_id,auth_run_number,site_id,observed_mac,
        authorized_at_utc,due_at_utc,classification_state,attempt_count,next_attempt_at_utc,
        lease_token,lease_until_utc,effective_window_start_utc,effective_window_end_utc,
        planned_classification_id,classification_id,classification_result_id,last_reason_code,
        registry_snapshot_id,device_id,visit_id,identity_state,created_at_utc,updated_at_utc
        FROM integration_jobs WHERE integration_id=?""",(os.environ["NEW_IID"],)).fetchone()
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK="+str(q))
if q!="ok": raise SystemExit("FATAL: integration quick_check failed")
if r is None: raise SystemExit("FATAL: controlled job missing")
for k in r.keys():
    print(f"NEW_{k.upper()}={'' if r[k] is None else r[k]}")
assert r["classification_state"]=="CLASSIFIED", r["classification_state"]
assert r["identity_state"]=="DEVICE_AND_VISIT_RESOLVED", r["identity_state"]
assert r["registry_snapshot_id"] and r["device_id"] and r["visit_id"]
assert r["planned_classification_id"]==r["classification_id"]
assert r["classification_result_id"]
assert r["lease_token"] is None and r["lease_until_utc"] is None
assert r["last_reason_code"] in (None,"")
print("NEW_CONTROLLED_JOB=PASS")
print("RECOVERY_PATH_USED="+("YES" if r["attempt_count"]>1 else "NO"))
PY

section "CLASSIFICATION RECORD LINKAGE"
INTEGRATION_DB="$INTEGRATION_DB" CLASSIFICATION_DB="$CLASSIFICATION_DB" NEW_IID="$NEW_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
icon=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True); icon.row_factory=sqlite3.Row
try:
    j=icon.execute("""SELECT site_id,observed_mac,planned_classification_id,
        classification_id,classification_result_id FROM integration_jobs WHERE integration_id=?""",
        (os.environ["NEW_IID"],)).fetchone()
finally:
    icon.close()
con=sqlite3.connect(f"file:{os.environ['CLASSIFICATION_DB']}?mode=ro",uri=True); con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute("""SELECT classification_id,site_id,observed_mac,execution_context,
        classification_result_id FROM classifications WHERE classification_id=?""",
        (j["planned_classification_id"],)).fetchone()
finally:
    con.close()
print("CLASSIFICATION_DB_QUICK_CHECK="+str(q))
if q!="ok": raise SystemExit("FATAL: classification quick_check failed")
if r is None: raise SystemExit("FATAL: planned classification missing")
for k in r.keys():
    print(f"CLASSIFICATION_{k.upper()}={r[k]}")
assert r["classification_id"]==j["planned_classification_id"]==j["classification_id"]
assert r["site_id"]==j["site_id"]
assert r["observed_mac"]==j["observed_mac"]
assert r["execution_context"]=="PRODUCTION"
assert r["classification_result_id"]==j["classification_result_id"]
print("CLASSIFICATION_LINKAGE=PASS")
PY

section "OLD FAILED JOB PRESERVED"
INTEGRATION_DB="$INTEGRATION_DB" OLD_IID="$OLD_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True); con.row_factory=sqlite3.Row
try:
    r=con.execute("""SELECT classification_state,attempt_count,last_reason_code,identity_state,
        planned_classification_id,classification_id,classification_result_id,
        registry_snapshot_id,device_id,visit_id FROM integration_jobs WHERE integration_id=?""",
        (os.environ["OLD_IID"],)).fetchone()
finally:
    con.close()
if r is None: raise SystemExit("FATAL: old job missing")
for k in r.keys():
    print(f"OLD_{k.upper()}={'' if r[k] is None else r[k]}")
expected=("NO_RESULT_FINAL",1,"runtime_profile_incompatible","DEVICE_AND_VISIT_RESOLVED",None,None)
actual=(r["classification_state"],r["attempt_count"],r["last_reason_code"],
        r["identity_state"],r["classification_id"],r["classification_result_id"])
assert actual==expected, actual
print("OLD_FAILED_JOB_PRESERVED=PASS")
PY

section "TIMING"
INTEGRATION_DB="$INTEGRATION_DB" NEW_IID="$NEW_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
from datetime import datetime, timezone
def p(s): return datetime.strptime(s,"%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True); con.row_factory=sqlite3.Row
try:
    r=con.execute("""SELECT authorized_at_utc,due_at_utc,updated_at_utc,attempt_count
        FROM integration_jobs WHERE integration_id=?""",(os.environ["NEW_IID"],)).fetchone()
finally:
    con.close()
a,d,u=map(p,(r["authorized_at_utc"],r["due_at_utc"],r["updated_at_utc"]))
print(f"AUTH_TO_DUE_SECONDS={(d-a).total_seconds():.3f}")
print(f"DUE_TO_FINAL_SECONDS={(u-d).total_seconds():.3f}")
print(f"AUTH_TO_FINAL_SECONDS={(u-a).total_seconds():.3f}")
print(f"ATTEMPT_COUNT={r['attempt_count']}")
PY

section "EXACT JOURNAL EVENTS"
journalctl -u "$WORKER" \
  --since "2026-10-04 02:17:00" --until "2026-10-04 02:24:30" \
  --no-pager -o short-iso-precise | grep -F "$NEW_IID" || true

section "FINAL"
echo "TASK05_R1_MERGED_CODE=PASS"
echo "TASK05_R1_PRODUCTION_RUNTIME=PASS"
echo "TASK05_R1_NEW_AUTH_JOB=PASS"
echo "TASK05_R1_EXACT_IDENTITY=PASS"
echo "TASK05_R1_CLASSIFICATION=PASS"
echo "TASK05_R1_PLANNED_ID_RECOVERY=PASS"
echo "TASK05_R1_OLD_FAILURE_EVIDENCE_PRESERVED=PASS"
echo "TASK05_R1_FINAL_ACCEPTANCE_EVIDENCE=PASS"
