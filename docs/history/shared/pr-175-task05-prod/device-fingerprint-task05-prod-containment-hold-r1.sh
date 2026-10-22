#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
CONTROLLED_IID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

wait_active() {
  local unit="$1" timeout="${2:-30}" i
  for ((i=1; i<=timeout; i++)); do
    systemctl is-active --quiet "$unit" && return 0
    sleep 1
  done
  return 1
}

wait_portal_identity() {
  local since="$1" timeout="${2:-45}" i line
  for ((i=1; i<=timeout; i++)); do
    line="$(journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      IDENTITY_LINE="$line" EXPECTED_HEAD="$TARGET_HEAD" EXPECTED_TREE="$TARGET_TREE" \
      /usr/bin/python3 - <<'PY'
import json, os
s=os.environ["IDENTITY_LINE"]
o=json.loads(s[s.index("{"):])
assert o["artifact_sha"] == os.environ["EXPECTED_HEAD"], o
assert o["artifact_tree"] == os.environ["EXPECTED_TREE"], o
assert o["service_name"] == "captive-portal.service", o
print("PORTAL_LOADED_ARTIFACT_SHA="+o["artifact_sha"])
print("PORTAL_LOADED_ARTIFACT_TREE="+o["artifact_tree"])
PY
      return 0
    fi
    sleep 1
  done
  return 1
}

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PROD_CONTAINMENT_HOLD_R1"
echo "CODE_WRITE=NO"
echo "DATABASE_WRITE=NO_BY_SCRIPT"
echo "CONFIG_CHANGE=INTEGRATION_TRUE_TO_FALSE"
echo "PORTAL_RESTART=YES"
echo "WORKER_STOP=YES"
echo "WORKER_DISABLE=YES"
echo "UNIT_REMOVAL=NO"
echo "INTEGRATION_DB_PRESERVE=YES"

section "PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$TARGET_TREE" ] || fail "Unexpected production tree"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Integration is not currently enabled=true"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker inactive before containment"
[ -f "$INTEGRATION_DB" ] || fail "Integration DB missing"

INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute("SELECT classification_state,last_reason_code,identity_state FROM integration_jobs WHERE integration_id=?",
                  (os.environ["IID"],)).fetchone()
    total=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK="+str(q))
print("INTEGRATION_JOB_COUNT="+str(total))
if r is None:
    raise SystemExit("FATAL: controlled failure evidence missing")
print("CONTROLLED_STATE="+str(r["classification_state"]))
print("CONTROLLED_REASON="+str(r["last_reason_code"]))
print("CONTROLLED_IDENTITY_STATE="+str(r["identity_state"]))
if q != "ok":
    raise SystemExit("FATAL: integration DB quick_check failed")
if r["classification_state"] != "NO_RESULT_FINAL" or r["last_reason_code"] != "runtime_profile_incompatible":
    raise SystemExit("FATAL: controlled failure evidence does not match accepted blocker")
PY
echo "PRECONDITIONS=PASS"

section "DISABLE NEW TASK05 ENQUEUE"
cp -a "$CFG" "${CFG}.task05-containment-backup-$(date '+%Y%m%dT%H%M%S%z')"
CFG="$CFG" /usr/bin/python3 - <<'PY'
import os, stat
from pathlib import Path
p=Path(os.environ["CFG"])
st=p.stat()
lines=p.read_text(encoding="utf-8").splitlines()
seen=0
out=[]
for line in lines:
    if line.startswith("DEVICE_FINGERPRINT_INTEGRATION_ENABLED="):
        seen += 1
        if seen > 1:
            raise SystemExit("FATAL: duplicate integration enabled keys")
        out.append("DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false")
    else:
        out.append(line)
if seen != 1:
    raise SystemExit("FATAL: integration enabled key not found exactly once")
tmp=p.with_name(p.name+".task05-containment.tmp")
tmp.write_text("\n".join(out)+"\n",encoding="utf-8")
os.chown(tmp,st.st_uid,st.st_gid)
os.chmod(tmp,stat.S_IMODE(st.st_mode))
os.replace(tmp,p)
PY
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG" \
  || fail "Failed to set integration false"
echo "CONFIG_INTEGRATION_ENABLED=FALSE"

section "RESTART PORTAL DISABLED"
SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
systemctl restart captive-portal.service
wait_active captive-portal.service 30 || fail "Portal did not become active"
wait_portal_identity "$SINCE" 45 || fail "Fresh Portal artifact identity not observed"
sleep 3
PORTAL_RESTARTS="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS=$PORTAL_RESTARTS"
[ "$PORTAL_RESTARTS" = "0" ] || fail "Portal automatic restart count non-zero"
echo "PORTAL_DISABLED_SUBMITTER_RUNTIME=PASS"

section "STOP AND DISABLE WORKER"
systemctl stop fingerprint-classification.service
systemctl disable fingerprint-classification.service >/dev/null
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Worker still active"
fi
if systemctl is-enabled --quiet fingerprint-classification.service; then
  fail "Worker still enabled"
fi
echo "WORKER_ACTIVE=NO"
echo "WORKER_ENABLED=NO"

section "PRESERVE FAILURE EVIDENCE"
INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute("SELECT classification_state,last_reason_code,identity_state,registry_snapshot_id,device_id,visit_id "
                  "FROM integration_jobs WHERE integration_id=?",(os.environ["IID"],)).fetchone()
    total=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK_FINAL="+str(q))
print("INTEGRATION_JOB_COUNT_FINAL="+str(total))
if r is None:
    raise SystemExit("FATAL: failure evidence disappeared")
for k in r.keys():
    print("CONTROLLED_"+k.upper()+"="+("" if r[k] is None else str(r[k])))
if q != "ok":
    raise SystemExit("FATAL: integration DB final quick_check failed")
PY

section "FINAL"
echo "TASK05_INTEGRATION_ENABLED=NO"
echo "TASK05_WORKER_ACTIVE=NO"
echo "TASK05_WORKER_ENABLED_FOR_BOOT=NO"
echo "TASK05_UNIT_FILES_PRESERVED=YES"
echo "TASK05_INTEGRATION_DB_PRESERVED=YES"
echo "TASK05_PRODUCTION_STATUS=HOLD_PENDING_CODE_REPAIR"
echo "TASK05_CONTAINMENT=PASS"
