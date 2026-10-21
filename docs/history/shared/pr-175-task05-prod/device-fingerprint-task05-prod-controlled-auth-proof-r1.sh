#!/usr/bin/env bash
set -Eeuo pipefail

export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
TASK04_WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"

TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
REGISTRY_DB="/opt/CaptivePortal/data/visitor_registry.sqlite3"
VISIT_DB="/opt/CaptivePortal/data/visits.sqlite3"

EXPECTED_MAC="${1:-}"
JOB_WAIT_SECONDS=600
CLASSIFICATION_WAIT_SECONDS=600
IDENTITY_WAIT_SECONDS=300

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

normalize_mac() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

if [ -n "$EXPECTED_MAC" ]; then
  EXPECTED_MAC="$(normalize_mac "$EXPECTED_MAC")"
  [[ "$EXPECTED_MAC" =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]] \
    || { echo "FATAL: expected MAC must be canonical aa:bb:cc:dd:ee:ff" >&2; exit 1; }
fi

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_CONTROLLED_AUTH_PROOF_R1"
echo "SCRIPT_DATABASE_WRITE=NO"
echo "SCRIPT_SERVICE_RESTART=NO"
echo "SCRIPT_CONFIG_WRITE=NO"
echo "SCRIPT_SYSTEMD_WRITE=NO"
echo "EXTERNAL_ACTION_REQUIRED=ONE_NORMAL_OWNER_CONTROLLED_AUTH"
echo "EXPECTED_MAC=${EXPECTED_MAC:-NOT_PREDECLARED}"
echo "AMBIGUITY_POLICY=FAIL_IF_MORE_THAN_ONE_NEW_INTEGRATION_JOB"

section "PRODUCTION PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$TARGET_TREE" ] || fail "Unexpected production tree"
[ -z "$STATUS" ] || fail "Production worktree dirty"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Task-05 integration is not enabled"

for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service fingerprint-classification.service; do
  systemctl is-active --quiet "$unit" || fail "$unit is not active"
done
systemctl is-enabled --quiet fingerprint-classification.service \
  || fail "fingerprint-classification.service is not enabled"

[ -f "$INTEGRATION_DB" ] || fail "Integration DB missing"
for db in "$CLASS_DB" "$CONTROL_DB" "$REGISTRY_DB" "$VISIT_DB"; do
  [ -f "$db" ] || fail "Required DB missing: $db"
done

echo "PORTAL_NRESTARTS_BASE=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_BASE=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
PORTAL_RESTARTS_BASE="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
WORKER_RESTARTS_BASE="$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "PRODUCTION_PRECONDITIONS=PASS"

section "TASK04 ACTIVE PROFILE"
ACTIVE_PROFILE_OUTPUT="$(
sudo -H -u admin env \
  PYTHONPATH="$TASK04_WT" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  /usr/bin/python3 -B - <<'PY'
import os
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
pin=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"]).pin_active_profile("classification")
print("ACTIVE_CRP="+pin.runtime_profile.artifact_id)
print("ACTIVE_RPM="+pin.admission_manifest.artifact_id)
print("ACTIVE_VALIDITY="+pin.validity_record.semantic_payload["state"])
if pin.validity_record.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: classification profile not ACTIVE")
PY
)"
printf '%s\n' "$ACTIVE_PROFILE_OUTPUT"
ACTIVE_CRP="$(printf '%s\n' "$ACTIVE_PROFILE_OUTPUT" | sed -n 's/^ACTIVE_CRP=//p')"
[ -n "$ACTIVE_CRP" ] || fail "Could not capture active ClassificationRuntimeProfile"
echo "TASK04_ACTIVE_PROFILE=PASS"

section "DATABASE BASELINE"
BASELINE="$(
INTEGRATION_DB="$INTEGRATION_DB" CLASS_DB="$CLASS_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
icon=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
try:
    q=icon.execute("PRAGMA quick_check").fetchone()[0]
    row=icon.execute("SELECT COALESCE(MAX(rowid),0),COUNT(*) FROM integration_jobs").fetchone()
finally:
    icon.close()
ccon=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    cq=ccon.execute("PRAGMA quick_check").fetchone()[0]
    cc=ccon.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    ccon.close()
print("INTEGRATION_QUICK_CHECK="+str(q))
print("BASELINE_MAX_ROWID="+str(row[0]))
print("BASELINE_JOB_COUNT="+str(row[1]))
print("CLASSIFICATION_QUICK_CHECK="+str(cq))
print("BASELINE_CLASSIFICATION_COUNT="+str(cc))
if q != "ok" or cq != "ok":
    raise SystemExit("FATAL: baseline quick_check failed")
PY
)"
printf '%s\n' "$BASELINE"
BASELINE_MAX_ROWID="$(printf '%s\n' "$BASELINE" | sed -n 's/^BASELINE_MAX_ROWID=//p')"
BASELINE_JOB_COUNT="$(printf '%s\n' "$BASELINE" | sed -n 's/^BASELINE_JOB_COUNT=//p')"
BASELINE_CLASSIFICATION_COUNT="$(printf '%s\n' "$BASELINE" | sed -n 's/^BASELINE_CLASSIFICATION_COUNT=//p')"
[[ "$BASELINE_MAX_ROWID" =~ ^[0-9]+$ ]] || fail "Invalid baseline rowid"

section "CONTROLLED AUTH WINDOW"
echo "BASELINE_CAPTURED_AT=$(date --iso-8601=seconds)"
echo
echo "ACTION:"
echo "  Perform exactly ONE fresh normal authorization on the Owner/test phone."
echo "  Do not authorize a second test device during this observation window."
if [ -n "$EXPECTED_MAC" ]; then
  echo "  Expected phone MAC: $EXPECTED_MAC"
else
  echo "  No MAC was supplied; proof will fail if more than one new integration job appears."
fi
echo
read -r -p "Press ENTER when you are ready for the script to watch for the new AuthRun... " _

OBSERVE_SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
echo "OBSERVATION_STARTED_AT=$(date --iso-8601=seconds)"

NEW_JOB_ROW=""
for ((i=1; i<=JOB_WAIT_SECONDS; i++)); do
  NEW_JOB_ROW="$(
    INTEGRATION_DB="$INTEGRATION_DB" BASELINE_MAX_ROWID="$BASELINE_MAX_ROWID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    rows=con.execute(
        """SELECT rowid,* FROM integration_jobs
           WHERE rowid>? ORDER BY rowid""",
        (int(os.environ["BASELINE_MAX_ROWID"]),)
    ).fetchall()
finally:
    con.close()
print("NEW_JOB_COUNT="+str(len(rows)))
for r in rows:
    print("JOB|"+"|".join(str(r[k]) if r[k] is not None else "" for k in (
        "rowid","integration_id","auth_session_id","auth_run_number","site_id",
        "observed_mac","authorized_at_utc","planned_classification_id","due_at_utc",
        "classification_state","attempt_count","identity_state"
    )))
PY
  )"
  NEW_COUNT="$(printf '%s\n' "$NEW_JOB_ROW" | sed -n 's/^NEW_JOB_COUNT=//p')"
  if [[ "$NEW_COUNT" =~ ^[0-9]+$ ]] && [ "$NEW_COUNT" -gt 0 ]; then
    sleep 2
    NEW_JOB_ROW="$(
      INTEGRATION_DB="$INTEGRATION_DB" BASELINE_MAX_ROWID="$BASELINE_MAX_ROWID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    rows=con.execute("SELECT rowid,* FROM integration_jobs WHERE rowid>? ORDER BY rowid",
                     (int(os.environ["BASELINE_MAX_ROWID"]),)).fetchall()
finally:
    con.close()
print("NEW_JOB_COUNT="+str(len(rows)))
for r in rows:
    print("JOB|"+"|".join(str(r[k]) if r[k] is not None else "" for k in (
        "rowid","integration_id","auth_session_id","auth_run_number","site_id",
        "observed_mac","authorized_at_utc","planned_classification_id","due_at_utc",
        "classification_state","attempt_count","identity_state"
    )))
PY
    )"
    break
  fi
  sleep 1
done

printf '%s\n' "$NEW_JOB_ROW"
NEW_COUNT="$(printf '%s\n' "$NEW_JOB_ROW" | sed -n 's/^NEW_JOB_COUNT=//p')"
[ "$NEW_COUNT" = "1" ] || fail "Expected exactly one new integration job; got ${NEW_COUNT:-0}"

JOB_LINE="$(printf '%s\n' "$NEW_JOB_ROW" | grep '^JOB|' | head -n1)"
IFS='|' read -r _ JOB_ROWID INTEGRATION_ID AUTH_SESSION_ID AUTH_RUN_NUMBER SITE_ID OBSERVED_MAC AUTHORIZED_AT PLANNED_ID DUE_AT INITIAL_STATE INITIAL_ATTEMPTS INITIAL_IDENTITY <<< "$JOB_LINE"

echo "CONTROLLED_JOB_ROWID=$JOB_ROWID"
echo "CONTROLLED_INTEGRATION_ID=$INTEGRATION_ID"
echo "CONTROLLED_AUTH_SESSION_ID=$AUTH_SESSION_ID"
echo "CONTROLLED_AUTH_RUN_NUMBER=$AUTH_RUN_NUMBER"
echo "CONTROLLED_SITE_ID=$SITE_ID"
echo "CONTROLLED_OBSERVED_MAC=$OBSERVED_MAC"
echo "CONTROLLED_AUTHORIZED_AT=$AUTHORIZED_AT"
echo "CONTROLLED_DUE_AT=$DUE_AT"
echo "CONTROLLED_PLANNED_CLASSIFICATION_ID=$PLANNED_ID"

if [ -n "$EXPECTED_MAC" ] && [ "$OBSERVED_MAC" != "$EXPECTED_MAC" ]; then
  fail "New integration job MAC does not match expected Owner/test phone MAC"
fi
echo "SINGLE_NEW_AUTH_JOB=PASS"

section "AUTH QUEUE TELEMETRY"
journalctl -u captive-portal.service --since "$OBSERVE_SINCE" --no-pager -o cat 2>/dev/null \
  | grep '"event":"fingerprint.integration_job_' \
  | grep "$INTEGRATION_ID" \
  | tail -n 10 || true

section "WAIT FOR CLASSIFICATION TERMINAL STATE"
TERMINAL=""
for ((i=1; i<=CLASSIFICATION_WAIT_SECONDS; i++)); do
  TERMINAL="$(
    INTEGRATION_DB="$INTEGRATION_DB" INTEGRATION_ID="$INTEGRATION_ID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute("SELECT * FROM integration_jobs WHERE integration_id=?",
                  (os.environ["INTEGRATION_ID"],)).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: controlled integration job disappeared")
for k in (
    "classification_state","attempt_count","classification_id","classification_result_id",
    "last_reason_code","effective_window_start_utc","effective_window_end_utc",
    "identity_state","identity_reason","registry_snapshot_id","device_id","visit_id"
):
    print(f"{k.upper()}="+("" if r[k] is None else str(r[k])))
PY
  )"
  STATE="$(printf '%s\n' "$TERMINAL" | sed -n 's/^CLASSIFICATION_STATE=//p')"
  if [ "$STATE" = "CLASSIFIED" ] || [ "$STATE" = "NO_RESULT_FINAL" ]; then
    break
  fi
  sleep 1
done

printf '%s\n' "$TERMINAL"
STATE="$(printf '%s\n' "$TERMINAL" | sed -n 's/^CLASSIFICATION_STATE=//p')"
[ "$STATE" = "CLASSIFIED" ] || fail "Controlled job did not reach CLASSIFIED within proof window"

CLASSIFICATION_ID="$(printf '%s\n' "$TERMINAL" | sed -n 's/^CLASSIFICATION_ID=//p')"
CLASSIFICATION_RESULT_ID="$(printf '%s\n' "$TERMINAL" | sed -n 's/^CLASSIFICATION_RESULT_ID=//p')"
IDENTITY_STATE="$(printf '%s\n' "$TERMINAL" | sed -n 's/^IDENTITY_STATE=//p')"
REGISTRY_SNAPSHOT_ID="$(printf '%s\n' "$TERMINAL" | sed -n 's/^REGISTRY_SNAPSHOT_ID=//p')"
DEVICE_ID="$(printf '%s\n' "$TERMINAL" | sed -n 's/^DEVICE_ID=//p')"
VISIT_ID="$(printf '%s\n' "$TERMINAL" | sed -n 's/^VISIT_ID=//p')"

[ "$CLASSIFICATION_ID" = "$PLANNED_ID" ] \
  || fail "Persisted classification_id does not equal crash-safe planned_classification_id"
[ -n "$CLASSIFICATION_RESULT_ID" ] || fail "Missing classification_result_id"
echo "PLANNED_CLASSIFICATION_ID_MATCH=PASS"
echo "CLASSIFICATION_TERMINAL_STATE=PASS"

section "AUTHORITATIVE CLASSIFICATION RELATION"
INTEGRATION_ID="$INTEGRATION_ID" CLASSIFICATION_ID="$CLASSIFICATION_ID" \
CLASSIFICATION_RESULT_ID="$CLASSIFICATION_RESULT_ID" SITE_ID="$SITE_ID" OBSERVED_MAC="$OBSERVED_MAC" \
ACTIVE_CRP="$ACTIVE_CRP" CLASS_DB="$CLASS_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    row=con.execute("SELECT * FROM classifications WHERE classification_id=?",
                    (os.environ["CLASSIFICATION_ID"],)).fetchone()
finally:
    con.close()
if row is None:
    raise SystemExit("FATAL: authoritative classification row missing")
checks={
    "site_id": os.environ["SITE_ID"],
    "observed_mac": os.environ["OBSERVED_MAC"],
    "execution_context": "PRODUCTION",
    "classification_result_id": os.environ["CLASSIFICATION_RESULT_ID"],
    "classification_runtime_profile_id": os.environ["ACTIVE_CRP"],
}
for key,expected in checks.items():
    actual=str(row[key])
    print(f"CLASSIFICATION_{key.upper()}={actual}")
    if actual != expected:
        raise SystemExit(f"FATAL: classification {key} mismatch: {actual} != {expected}")
print("AUTHORITATIVE_CLASSIFICATION_RELATION=PASS")
PY

section "WAIT FOR EXACT IDENTITY RELATION"
IDENTITY_FINAL=""
for ((i=1; i<=IDENTITY_WAIT_SECONDS; i++)); do
  IDENTITY_FINAL="$(
    INTEGRATION_DB="$INTEGRATION_DB" INTEGRATION_ID="$INTEGRATION_ID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute(
        "SELECT identity_state,identity_reason,registry_snapshot_id,device_id,visit_id,identity_last_attempt_at_utc "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["INTEGRATION_ID"],)
    ).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: integration job disappeared")
for k in r.keys():
    print(k.upper()+"="+("" if r[k] is None else str(r[k])))
PY
  )"
  ISTATE="$(printf '%s\n' "$IDENTITY_FINAL" | sed -n 's/^IDENTITY_STATE=//p')"
  if [ "$ISTATE" = "DEVICE_RESOLVED" ] || [ "$ISTATE" = "DEVICE_AND_VISIT_RESOLVED" ] || [ "$ISTATE" = "CONFLICT" ]; then
    break
  fi
  sleep 1
done
printf '%s\n' "$IDENTITY_FINAL"

IDENTITY_STATE="$(printf '%s\n' "$IDENTITY_FINAL" | sed -n 's/^IDENTITY_STATE=//p')"
REGISTRY_SNAPSHOT_ID="$(printf '%s\n' "$IDENTITY_FINAL" | sed -n 's/^REGISTRY_SNAPSHOT_ID=//p')"
DEVICE_ID="$(printf '%s\n' "$IDENTITY_FINAL" | sed -n 's/^DEVICE_ID=//p')"
VISIT_ID="$(printf '%s\n' "$IDENTITY_FINAL" | sed -n 's/^VISIT_ID=//p')"

[ "$IDENTITY_STATE" != "CONFLICT" ] || fail "Exact identity resolver reported CONFLICT"
[ -n "$REGISTRY_SNAPSHOT_ID" ] || fail "Registry exact relation did not resolve in proof window"
[ -n "$DEVICE_ID" ] || fail "Device exact relation did not resolve in proof window"

section "REGISTRY SOURCE PROOF"
REGISTRY_DB="$REGISTRY_DB" SNAPSHOT_ID="$REGISTRY_SNAPSHOT_ID" DEVICE_ID="$DEVICE_ID" \
AUTH_SESSION_ID="$AUTH_SESSION_ID" SITE_ID="$SITE_ID" OBSERVED_MAC="$OBSERVED_MAC" \
/usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['REGISTRY_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    row=con.execute(
        "SELECT snapshot_id,device_id,auth_session_id,site_id,requested_mac,auth_run_number "
        "FROM device_snapshots WHERE snapshot_id=?",
        (os.environ["SNAPSHOT_ID"],)
    ).fetchone()
finally:
    con.close()
if row is None:
    raise SystemExit("FATAL: Registry snapshot anchor missing")
expected={
    "snapshot_id":os.environ["SNAPSHOT_ID"],
    "device_id":os.environ["DEVICE_ID"],
    "auth_session_id":os.environ["AUTH_SESSION_ID"],
    "site_id":os.environ["SITE_ID"],
    "requested_mac":os.environ["OBSERVED_MAC"],
}
for k,v in expected.items():
    actual="" if row[k] is None else str(row[k])
    print("REGISTRY_"+k.upper()+"="+actual)
    if actual != v:
        raise SystemExit(f"FATAL: Registry exact relation mismatch for {k}")
print("REGISTRY_AUTH_RUN_NUMBER="+("" if row["auth_run_number"] is None else str(row["auth_run_number"])))
print("REGISTRY_EXACT_RELATION=PASS")
PY

section "VISIT SOURCE PROOF"
if [ -n "$VISIT_ID" ]; then
  VISIT_DB="$VISIT_DB" VISIT_ID="$VISIT_ID" AUTH_SESSION_ID="$AUTH_SESSION_ID" \
  AUTH_RUN_NUMBER="$AUTH_RUN_NUMBER" SITE_ID="$SITE_ID" OBSERVED_MAC="$OBSERVED_MAC" \
  DEVICE_ID="$DEVICE_ID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['VISIT_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    v=con.execute(
        "SELECT visit_id,site_id,client_mac,start_auth_session_id,start_auth_run_number,device_id "
        "FROM visits WHERE visit_id=?",
        (os.environ["VISIT_ID"],)
    ).fetchone()
    a=con.execute(
        "SELECT visit_id,auth_session_id,auth_run_number,authorized_at "
        "FROM visit_authorizations WHERE visit_id=? AND auth_session_id=? AND auth_run_number=?",
        (os.environ["VISIT_ID"],os.environ["AUTH_SESSION_ID"],int(os.environ["AUTH_RUN_NUMBER"]))
    ).fetchone()
finally:
    con.close()
if v is None:
    raise SystemExit("FATAL: Visit anchor missing")
checks={
    "visit_id":os.environ["VISIT_ID"],
    "site_id":os.environ["SITE_ID"],
    "client_mac":os.environ["OBSERVED_MAC"],
    "start_auth_session_id":os.environ["AUTH_SESSION_ID"],
    "start_auth_run_number":os.environ["AUTH_RUN_NUMBER"],
}
for k,expected in checks.items():
    actual="" if v[k] is None else str(v[k])
    print("VISIT_"+k.upper()+"="+actual)
    if actual != expected:
        raise SystemExit(f"FATAL: Visit exact relation mismatch for {k}")
if v["device_id"] is not None and str(v["device_id"]) != os.environ["DEVICE_ID"]:
    raise SystemExit("FATAL: Visit device_id conflicts with Registry device_id")
if a is None:
    raise SystemExit("FATAL: exact visit_authorizations relation missing")
print("VISIT_AUTHORIZED_AT="+str(a["authorized_at"]))
print("VISIT_EXACT_RELATION=PASS")
PY
else
  echo "VISIT_EXACT_RELATION=NOT_RESOLVED_IN_PROOF_WINDOW"
  echo "VISIT_RELATION_NOTE=Registry identity is exact; Visit remains absent rather than guessed"
fi

section "NO DUPLICATE / STABILITY CHECK"
sleep 5
INTEGRATION_DB="$INTEGRATION_DB" CLASS_DB="$CLASS_DB" BASELINE_MAX_ROWID="$BASELINE_MAX_ROWID" \
CLASSIFICATION_ID="$CLASSIFICATION_ID" /usr/bin/python3 - <<'PY'
import os, sqlite3
icon=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
try:
    new_jobs=icon.execute("SELECT COUNT(*) FROM integration_jobs WHERE rowid>?",
                          (int(os.environ["BASELINE_MAX_ROWID"]),)).fetchone()[0]
    q=icon.execute("PRAGMA quick_check").fetchone()[0]
finally:
    icon.close()
ccon=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro",uri=True)
try:
    rows=ccon.execute("SELECT COUNT(*) FROM classifications WHERE classification_id=?",
                      (os.environ["CLASSIFICATION_ID"],)).fetchone()[0]
finally:
    ccon.close()
print("NEW_JOB_COUNT_FINAL="+str(new_jobs))
print("CLASSIFICATION_ID_ROW_COUNT="+str(rows))
print("INTEGRATION_QUICK_CHECK_FINAL="+str(q))
if new_jobs != 1:
    raise SystemExit("FATAL: duplicate/additional integration job appeared")
if rows != 1:
    raise SystemExit("FATAL: classification identity is not unique")
if q != "ok":
    raise SystemExit("FATAL: integration DB final quick_check failed")
print("NO_DUPLICATE_RELATION=PASS")
PY

PORTAL_RESTARTS_FINAL="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
WORKER_RESTARTS_FINAL="$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS_FINAL=$PORTAL_RESTARTS_FINAL"
echo "WORKER_NRESTARTS_FINAL=$WORKER_RESTARTS_FINAL"
[ "$PORTAL_RESTARTS_FINAL" = "$PORTAL_RESTARTS_BASE" ] || fail "Portal restarted during controlled proof"
[ "$WORKER_RESTARTS_FINAL" = "$WORKER_RESTARTS_BASE" ] || fail "Worker restarted during controlled proof"
echo "RUNTIME_STABILITY=PASS"

section "WORKER TELEMETRY FOR CONTROLLED JOB"
journalctl -u fingerprint-classification.service --since "$OBSERVE_SINCE" --no-pager -o cat 2>/dev/null \
  | grep "$INTEGRATION_ID" \
  | tail -n 40 || true

section "FINAL"
echo "CONTROLLED_INTEGRATION_ID=$INTEGRATION_ID"
echo "CONTROLLED_AUTH_SESSION_ID=$AUTH_SESSION_ID"
echo "CONTROLLED_AUTH_RUN_NUMBER=$AUTH_RUN_NUMBER"
echo "CONTROLLED_OBSERVED_MAC=$OBSERVED_MAC"
echo "CONTROLLED_CLASSIFICATION_ID=$CLASSIFICATION_ID"
echo "CONTROLLED_CLASSIFICATION_RESULT_ID=$CLASSIFICATION_RESULT_ID"
echo "CONTROLLED_IDENTITY_STATE=$IDENTITY_STATE"
echo "CONTROLLED_REGISTRY_SNAPSHOT_ID=$REGISTRY_SNAPSHOT_ID"
echo "CONTROLLED_DEVICE_ID=$DEVICE_ID"
echo "CONTROLLED_VISIT_ID=${VISIT_ID:-NOT_RESOLVED}"
echo "TASK05_CONTROLLED_AUTH_CORE_PROOF=PASS"
if [ -n "$VISIT_ID" ]; then
  echo "TASK05_CONTROLLED_AUTH_EXACT_IDENTITY_PROOF=PASS_REGISTRY_AND_VISIT"
else
  echo "TASK05_CONTROLLED_AUTH_EXACT_IDENTITY_PROOF=PASS_REGISTRY_ONLY_VISIT_NOT_PROVEN"
fi
echo "TASK05_PRODUCTION_RUNTIME_STABILITY=PASS"
echo "SCRIPT_CHANGES_MADE=NONE"
