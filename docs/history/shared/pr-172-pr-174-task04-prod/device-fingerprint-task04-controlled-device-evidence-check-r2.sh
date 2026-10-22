#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <MAC> [window_minutes]" >&2
  exit 2
fi

MAC_RAW="$1"
WINDOW_MINUTES="${2:-15}"
SITE_ID="6a64f17630da7c70d232187a"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"

python3 - "$MAC_RAW" "$WINDOW_MINUTES" "$SITE_ID" "$EVIDENCE_DB" "$CLASS_DB" <<'PY'
import json, re, sqlite3, sys
from datetime import datetime, timedelta, timezone

raw_mac, raw_minutes, site, evidence_db, class_db = sys.argv[1:]
clean=re.sub(r"[:.\-\s]","",raw_mac).upper()
if not re.fullmatch(r"[0-9A-F]{12}",clean):
    raise SystemExit("INVALID_MAC")
mac=":".join(clean[i:i+2] for i in range(0,12,2))
try:
    minutes=int(raw_minutes)
except ValueError:
    raise SystemExit("INVALID_WINDOW")
if not 2 <= minutes <= 120:
    raise SystemExit("WINDOW_MINUTES_MUST_BE_2_TO_120")

end=datetime.now(timezone.utc)
start=end-timedelta(minutes=minutes)
fmt=lambda x:x.isoformat(timespec="milliseconds").replace("+00:00","Z")
start_s,end_s=fmt(start),fmt(end)

con=sqlite3.connect(f"file:{evidence_db}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    qc=con.execute("PRAGMA quick_check").fetchone()[0]
    if qc!="ok": raise SystemExit("EVIDENCE_DB_QUICK_CHECK_FAIL")
    total=con.execute(
        "SELECT COUNT(*) FROM device_fingerprint_evidence "
        "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<?",
        (site,mac,start_s,end_s)).fetchone()[0]
    by_kind=[dict(r) for r in con.execute(
        "SELECT source_kind,COUNT(*) AS rows,MIN(observed_at) AS first_at,MAX(observed_at) AS last_at "
        "FROM device_fingerprint_evidence "
        "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
        "GROUP BY source_kind ORDER BY source_kind",
        (site,mac,start_s,end_s))]
    latest=[dict(r) for r in con.execute(
        "SELECT source_kind,producer_id,capture_source_id,observed_at,feature_schema_version,quality_state "
        "FROM device_fingerprint_evidence "
        "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
        "ORDER BY observed_at DESC LIMIT 20",
        (site,mac,start_s,end_s))]
    health=[dict(r) for r in con.execute(
        "SELECT producer_id,capture_source_id,source_kind,MAX(observed_at) AS latest_health_at "
        "FROM device_fingerprint_source_health_events "
        "WHERE site_id=? AND observed_at<=? "
        "GROUP BY producer_id,capture_source_id,source_kind ORDER BY source_kind,producer_id,capture_source_id",
        (site,end_s))]
finally:
    con.close()

cc=sqlite3.connect(f"file:{class_db}?mode=ro",uri=True)
try:
    existing=cc.execute(
        "SELECT COUNT(*) FROM classifications WHERE site_id=? AND observed_mac=?",
        (site,mac)).fetchone()[0]
finally:
    cc.close()

print("MODE=READ_ONLY_CONTROLLED_DEVICE_EVIDENCE_CHECK")
print(f"SITE_ID={site}")
print(f"MAC={mac}")
print(f"WINDOW_START_UTC={start_s}")
print(f"WINDOW_END_UTC={end_s}")
print(f"EVIDENCE_ROWS={total}")
print(f"EXISTING_CLASSIFICATION_ROWS_FOR_MAC={existing}")
print("EVIDENCE_BY_SOURCE_KIND="+json.dumps(by_kind,sort_keys=True,separators=(",",":")))
print("LATEST_EVIDENCE="+json.dumps(latest,sort_keys=True,separators=(",",":")))
print("SOURCE_HEALTH_HEADS="+json.dumps(health,sort_keys=True,separators=(",",":")))
if total == 0:
    print("CONTROLLED_DEVICE_EVIDENCE_READY=NO")
    print("REASON=no_evidence_in_window")
    raise SystemExit(3)
print("CONTROLLED_DEVICE_EVIDENCE_READY=YES")
PY
