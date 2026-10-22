#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
PORTAL_UNIT="captive-portal.service"
WORKER="fingerprint-classification.service"
CFG="/etc/default/captive-portal"

EXPECTED_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
EXPECTED_TREE="545a48caf86adc247083db611e87a8d36820f353"

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CLASSIFICATION_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
OLD_IID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"

AUTH_WAIT_SECONDS=180
CLASSIFICATION_WAIT_SECONDS=360

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_R1_CONTROLLED_AUTH_PROOF"
echo "EXPECTED_HEAD=$EXPECTED_HEAD"
echo "EXPECTED_TREE=$EXPECTED_TREE"
echo "AUTH_WAIT_SECONDS=$AUTH_WAIT_SECONDS"
echo "CLASSIFICATION_WAIT_SECONDS=$CLASSIFICATION_WAIT_SECONDS"
echo "DATABASE_WRITE_BY_SCRIPT=NO"
echo "CONFIG_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "OLD_JOB_MUTATION_ALLOWED=NO"

section "PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "PRODUCTION_HEAD=$HEAD"
echo "PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected production tree"
[ -z "$STATUS" ] || fail "Production worktree dirty"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Task-05 integration is not enabled"
systemctl is-active --quiet "$PORTAL_UNIT" || fail "Portal inactive"
systemctl is-active --quiet "$WORKER" || fail "Classification worker inactive"
systemctl is-enabled --quiet "$WORKER" || fail "Classification worker not enabled"

PORTAL_RESTARTS_BEFORE="$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)"
WORKER_RESTARTS_BEFORE="$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS_BEFORE=$PORTAL_RESTARTS_BEFORE"
echo "WORKER_NRESTARTS_BEFORE=$WORKER_RESTARTS_BEFORE"
[ "$PORTAL_RESTARTS_BEFORE" = "0" ] || fail "Portal NRestarts non-zero before proof"
[ "$WORKER_RESTARTS_BEFORE" = "0" ] || fail "Worker NRestarts non-zero before proof"

eval "$(
INTEGRATION_DB="$INTEGRATION_DB" OLD_IID="$OLD_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3, shlex
db=os.environ["INTEGRATION_DB"]
iid=os.environ["OLD_IID"]
con=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    count=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
    r=con.execute(
        "SELECT integration_id,observed_mac,classification_state,attempt_count,"
        "last_reason_code,identity_state,planned_classification_id,"
        "classification_id,classification_result_id,registry_snapshot_id,device_id,visit_id "
        "FROM integration_jobs WHERE integration_id=?",
        (iid,)
    ).fetchone()
finally:
    con.close()
if q!="ok":
    raise SystemExit("FATAL: integration DB quick_check failed")
if r is None:
    raise SystemExit("FATAL: old controlled job missing")
expected=("NO_RESULT_FINAL",1,"runtime_profile_incompatible","DEVICE_AND_VISIT_RESOLVED")
actual=(r["classification_state"],r["attempt_count"],r["last_reason_code"],r["identity_state"])
if actual != expected:
    raise SystemExit(f"FATAL: old controlled job changed before proof: {actual!r}")
def out(k,v):
    print(f"{k}={shlex.quote('' if v is None else str(v))}")
out("OLD_JOB_COUNT",count)
out("EXPECTED_MAC",r["observed_mac"])
out("OLD_PLANNED_CLASSIFICATION_ID",r["planned_classification_id"])
out("OLD_REGISTRY_SNAPSHOT_ID",r["registry_snapshot_id"])
out("OLD_DEVICE_ID",r["device_id"])
out("OLD_VISIT_ID",r["visit_id"])
PY
)"

echo "INTEGRATION_JOB_COUNT_BEFORE=$OLD_JOB_COUNT"
echo "CONTROLLED_DEVICE_MAC=$EXPECTED_MAC"
echo "OLD_JOB_STATE=NO_RESULT_FINAL"
echo "OLD_JOB_REASON=runtime_profile_incompatible"
echo "PRECONDITIONS=PASS"

section "CONTROLLED AUTH WINDOW"
START_EPOCH_MS="$(date +%s%3N)"
START_ISO="$(date --iso-8601=seconds)"
echo "PROOF_START=$START_ISO"
echo
echo "============================================================"
echo "NOW AUTHENTICATE THE SAME CONTROLLED PHONE ON Zefer_Parki."
echo "Use the normal captive-portal flow once."
echo "The script will accept only a NEW integration job for:"
echo "MAC=$EXPECTED_MAC"
echo "============================================================"
echo

NEW_IID=""
for ((i=0; i<AUTH_WAIT_SECONDS; i++)); do
  NEW_IID="$(
    INTEGRATION_DB="$INTEGRATION_DB" EXPECTED_MAC="$EXPECTED_MAC" OLD_IID="$OLD_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    rows=con.execute(
        "SELECT integration_id FROM integration_jobs "
        "WHERE observed_mac=? AND integration_id<>? "
        "ORDER BY rowid DESC LIMIT 1",
        (os.environ["EXPECTED_MAC"], os.environ["OLD_IID"])
    ).fetchall()
finally:
    con.close()
print(rows[0]["integration_id"] if rows else "")
PY
  )"
  if [ -n "$NEW_IID" ]; then
    break
  fi
  sleep 1
done

[ -n "$NEW_IID" ] || fail "No new controlled integration job appeared within auth window"
echo "NEW_INTEGRATION_ID=$NEW_IID"

section "NEW JOB ADMISSION"
INTEGRATION_DB="$INTEGRATION_DB" NEW_IID="$NEW_IID" EXPECTED_MAC="$EXPECTED_MAC" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute("SELECT * FROM integration_jobs WHERE integration_id=?",(os.environ["NEW_IID"],)).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: new job disappeared")
for k in ("integration_id","auth_session_id","auth_run_number","site_id","observed_mac",
          "authorized_at","due_at","classification_state","attempt_count",
          "planned_classification_id","identity_state","last_reason_code"):
    if k in r.keys():
        print(f"{k.upper()}={'' if r[k] is None else r[k]}")
if r["observed_mac"] != os.environ["EXPECTED_MAC"]:
    raise SystemExit("FATAL: new job MAC mismatch")
if not r["planned_classification_id"]:
    raise SystemExit("FATAL: planned_classification_id missing")
PY

section "WAIT FOR CLASSIFICATION"
FINAL_STATE=""
for ((i=0; i<CLASSIFICATION_WAIT_SECONDS; i++)); do
  FINAL_STATE="$(
    INTEGRATION_DB="$INTEGRATION_DB" NEW_IID="$NEW_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute(
        "SELECT classification_state FROM integration_jobs WHERE integration_id=?",
        (os.environ["NEW_IID"],)
    ).fetchone()
finally:
    con.close()
print("" if r is None else r["classification_state"])
PY
  )"
  case "$FINAL_STATE" in
    CLASSIFIED|NO_RESULT_FINAL) break ;;
  esac
  sleep 1
done

echo "FINAL_CLASSIFICATION_STATE=$FINAL_STATE"
[ "$FINAL_STATE" = "CLASSIFIED" ] || fail "Controlled job did not reach CLASSIFIED"

section "FINAL JOB ASSERTIONS"
INTEGRATION_DB="$INTEGRATION_DB" NEW_IID="$NEW_IID" EXPECTED_MAC="$EXPECTED_MAC" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute(
        "SELECT integration_id,auth_session_id,auth_run_number,site_id,observed_mac,"
        "authorized_at,due_at,classification_state,attempt_count,last_reason_code,"
        "identity_state,planned_classification_id,classification_id,"
        "classification_result_id,registry_snapshot_id,device_id,visit_id "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["NEW_IID"],)
    ).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: final job missing")
for k in r.keys():
    print(f"{k.upper()}={'' if r[k] is None else r[k]}")
if r["observed_mac"] != os.environ["EXPECTED_MAC"]:
    raise SystemExit("FATAL: final MAC mismatch")
if r["classification_state"] != "CLASSIFIED":
    raise SystemExit("FATAL: final state not CLASSIFIED")
if r["identity_state"] != "DEVICE_AND_VISIT_RESOLVED":
    raise SystemExit("FATAL: identity did not resolve device+visit")
if not r["registry_snapshot_id"] or not r["device_id"] or not r["visit_id"]:
    raise SystemExit("FATAL: Registry/Visit identity fields incomplete")
if not r["planned_classification_id"]:
    raise SystemExit("FATAL: planned classification ID missing")
if r["classification_id"] != r["planned_classification_id"]:
    raise SystemExit(
        f"FATAL: classification_id != planned_classification_id: "
        f"{r['classification_id']} != {r['planned_classification_id']}"
    )
if not r["classification_result_id"]:
    raise SystemExit("FATAL: classification_result_id missing")
if r["last_reason_code"] not in (None, "", "classified"):
    raise SystemExit(f"FATAL: unexpected last_reason_code after classification: {r['last_reason_code']!r}")
PY

section "OLD TERMINAL JOB STILL IMMUTABLE"
INTEGRATION_DB="$INTEGRATION_DB" OLD_IID="$OLD_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute(
        "SELECT classification_state,attempt_count,last_reason_code,identity_state,"
        "classification_id,classification_result_id "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["OLD_IID"],)
    ).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: old job disappeared")
for k in r.keys():
    print(f"OLD_JOB_{k.upper()}={'' if r[k] is None else r[k]}")
expected=("NO_RESULT_FINAL",1,"runtime_profile_incompatible","DEVICE_AND_VISIT_RESOLVED",None,None)
actual=(r["classification_state"],r["attempt_count"],r["last_reason_code"],r["identity_state"],
        r["classification_id"],r["classification_result_id"])
if actual != expected:
    raise SystemExit(f"FATAL: old terminal job mutated: {actual!r}")
print("OLD_FAILED_JOB_PRESERVED=YES")
PY

section "RUNTIME STABILITY"
systemctl is-active --quiet "$PORTAL_UNIT" || fail "Portal inactive after proof"
systemctl is-active --quiet "$WORKER" || fail "Worker inactive after proof"
systemctl is-enabled --quiet "$WORKER" || fail "Worker not enabled after proof"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Integration flag changed during proof"

PORTAL_RESTARTS_AFTER="$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)"
WORKER_RESTARTS_AFTER="$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS_AFTER=$PORTAL_RESTARTS_AFTER"
echo "WORKER_NRESTARTS_AFTER=$WORKER_RESTARTS_AFTER"
[ "$PORTAL_RESTARTS_AFTER" = "0" ] || fail "Portal automatic restart detected"
[ "$WORKER_RESTARTS_AFTER" = "0" ] || fail "Worker automatic restart detected"

LATEST_HEALTH="$(journalctl -u "$WORKER" --since "$START_ISO" --no-pager -o cat \
  | grep '"event":"fingerprint.integration_worker_health"' | tail -n1 || true)"
echo "LATEST_WORKER_HEALTH=${LATEST_HEALTH:-<none>}"
if [ -n "$LATEST_HEALTH" ]; then
  case "$LATEST_HEALTH" in
    *'"reason_code":"ready"'*) ;;
    *) fail "Latest worker health is not ready" ;;
  esac
fi

section "FINAL"
echo "TASK05_R1_NEW_AUTH_JOB_CREATED=PASS"
echo "TASK05_R1_EXACT_MAC_MATCH=PASS"
echo "TASK05_R1_REGISTRY_IDENTITY_RESOLVED=PASS"
echo "TASK05_R1_VISIT_IDENTITY_RESOLVED=PASS"
echo "TASK05_R1_CLASSIFICATION_STATE=CLASSIFIED"
echo "TASK05_R1_PLANNED_CLASSIFICATION_ID_MATCH=PASS"
echo "TASK05_R1_CLASSIFICATION_RESULT_ID_PRESENT=PASS"
echo "TASK05_R1_OLD_FAILED_JOB_PRESERVED=PASS"
echo "TASK05_R1_PORTAL_RUNTIME_STABLE=PASS"
echo "TASK05_R1_WORKER_RUNTIME_STABLE=PASS"
echo "TASK05_R1_CONTROLLED_AUTH_PROOF=PASS"
