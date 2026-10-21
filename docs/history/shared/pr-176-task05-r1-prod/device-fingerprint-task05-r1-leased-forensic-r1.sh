#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CLASSIFICATION_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
WORKER="fingerprint-classification.service"
IID="e8ac5702-6ab5-4af9-94ae-0582df4666af"
PROOF_START="2026-10-04 02:14:50"

section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || { echo "FATAL: run with sudo/root"; exit 1; }

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_LEASED_FORENSIC"
echo "SERVICE_WRITE=NO"
echo "DATABASE_WRITE=NO"
echo "CONFIG_WRITE=NO"
echo "TARGET_INTEGRATION_ID=$IID"

section "WORKER SERVICE"
systemctl --no-pager --full status "$WORKER" | sed -n '1,30p' || true
echo "WORKER_ACTIVE=$(systemctl is-active "$WORKER" || true)"
echo "WORKER_ENABLED=$(systemctl is-enabled "$WORKER" || true)"
echo "WORKER_NRESTARTS=$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
PID="$(systemctl show "$WORKER" -p MainPID --value --no-pager)"
echo "WORKER_PID=$PID"

if [ "$PID" != "0" ] && [ -d "/proc/$PID" ]; then
  ps -p "$PID" -o pid=,ppid=,etimes=,time=,%cpu=,%mem=,stat=,wchan=,cmd=
  echo "PROC_WCHAN=$(cat "/proc/$PID/wchan" 2>/dev/null || true)"
  echo -n "PROC_SYSCALL="
  cat "/proc/$PID/syscall" 2>/dev/null || true
  echo
  echo "OPEN_FDS:"
  ls -l "/proc/$PID/fd" 2>/dev/null | sed -n '1,80p' || true
fi

section "TARGET JOB ROW"
INTEGRATION_DB="$INTEGRATION_DB" IID="$IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
db=os.environ["INTEGRATION_DB"]; iid=os.environ["IID"]
con=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute("SELECT * FROM integration_jobs WHERE integration_id=?",(iid,)).fetchone()
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK="+str(q))
if r is None:
    raise SystemExit("FATAL: target job missing")
for k in r.keys():
    print(f"{k.upper()}={'' if r[k] is None else r[k]}")
PY

section "CLASSIFICATION PERSISTENCE CHECK"
INTEGRATION_DB="$INTEGRATION_DB" CLASSIFICATION_DB="$CLASSIFICATION_DB" IID="$IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
idb=os.environ["INTEGRATION_DB"]; cdb=os.environ["CLASSIFICATION_DB"]; iid=os.environ["IID"]
icon=sqlite3.connect(f"file:{idb}?mode=ro", uri=True); icon.row_factory=sqlite3.Row
try:
    j=icon.execute(
        "SELECT planned_classification_id,observed_mac,site_id,authorized_at_utc "
        "FROM integration_jobs WHERE integration_id=?",(iid,)
    ).fetchone()
finally:
    icon.close()
if j is None:
    raise SystemExit("FATAL: job missing")
planned=j["planned_classification_id"]
print("PLANNED_CLASSIFICATION_ID="+planned)
con=sqlite3.connect(f"file:{cdb}?mode=ro", uri=True); con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute(
        "SELECT classification_id,site_id,observed_mac,classified_at_utc,execution_context,"
        "classification_result_id,snapshot_record_id "
        "FROM classifications WHERE classification_id=?",(planned,)
    ).fetchone()
finally:
    con.close()
print("CLASSIFICATION_DB_QUICK_CHECK="+str(q))
print("PLANNED_CLASSIFICATION_PERSISTED="+("YES" if r is not None else "NO"))
if r is not None:
    for k in r.keys():
        print(f"PERSISTED_{k.upper()}={r[k]}")
PY

section "EVIDENCE WINDOW COUNTS AND QUERY PLAN"
INTEGRATION_DB="$INTEGRATION_DB" EVIDENCE_DB="$EVIDENCE_DB" IID="$IID" /usr/bin/python3 - <<'PY'
import os, sqlite3, datetime, time
idb=os.environ["INTEGRATION_DB"]; edb=os.environ["EVIDENCE_DB"]; iid=os.environ["IID"]
icon=sqlite3.connect(f"file:{idb}?mode=ro", uri=True); icon.row_factory=sqlite3.Row
try:
    j=icon.execute(
        "SELECT site_id,observed_mac,authorized_at_utc FROM integration_jobs WHERE integration_id=?",
        (iid,)
    ).fetchone()
finally:
    icon.close()
if j is None: raise SystemExit("FATAL: job missing")
def parse(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond//1000:03d}Z"
auth=parse(j["authorized_at_utc"])
start=fmt(auth-datetime.timedelta(seconds=300))
end=fmt(auth+datetime.timedelta(seconds=120))
print("WINDOW_START="+start)
print("WINDOW_END="+end)
con=sqlite3.connect(f"file:{edb}?mode=ro", uri=True); con.row_factory=sqlite3.Row
try:
    for label, sql, args in [
        ("EVIDENCE", "SELECT count(*) FROM device_fingerprint_evidence WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<?",
         (j["site_id"],j["observed_mac"],start,end)),
        ("HEALTH", "SELECT count(*) FROM device_fingerprint_source_health_events WHERE site_id=? AND observed_at>=? AND observed_at<?",
         (j["site_id"],start,end)),
    ]:
        t=time.monotonic()
        n=con.execute(sql,args).fetchone()[0]
        elapsed=(time.monotonic()-t)*1000
        print(f"{label}_ROWS={n}")
        print(f"{label}_COUNT_MS={elapsed:.3f}")
    plan=con.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM device_fingerprint_evidence "
        "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
        "ORDER BY observed_at,evidence_id LIMIT 101",
        (j["site_id"],j["observed_mac"],start,end)
    ).fetchall()
    for row in plan:
        print("EVIDENCE_QUERY_PLAN="+" | ".join(str(x) for x in row))
finally:
    con.close()
PY

section "WORKER JOURNAL SINCE PROOF START"
journalctl -u "$WORKER" --since "$PROOF_START" --no-pager -o cat | tail -n 250

section "INTEGRATION-ID JOURNAL MATCHES"
journalctl -u "$WORKER" --since "$PROOF_START" --no-pager -o cat \
  | grep -F "$IID" || true

section "FINAL"
echo "READ_ONLY_FORENSIC=PASS"
