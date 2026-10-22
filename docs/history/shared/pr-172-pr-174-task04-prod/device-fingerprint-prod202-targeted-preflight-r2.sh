#!/usr/bin/env bash
set -u

APP=/opt/CaptivePortal
DFDIR=/etc/captive-portal/device-fingerprint
OUT_MARKER="DEVICE_FINGERPRINT_PROD202_TARGETED_PREFLIGHT_R2"

section(){ printf '\n===== %s =====\n' "$1"; }

section "MARKERS"
echo "$OUT_MARKER=YES"
echo "HOST_EXPECTED=192.168.0.202"
echo "NO_CHANGES_PERFORMED=YES"

section "FILESYSTEM_RUN"
df -hT /run / 2>&1 || true
df -ih /run / 2>&1 || true
for p in /run/fingerprint-suricata /run/captive-portal/fingerprint-sensor; do
  echo "--- PATH=$p"
  if [ -e "$p" ]; then
    du -sh "$p" 2>/dev/null || true
    find "$p" -maxdepth 1 -printf '%M %u:%g %s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort || true
  else
    echo "ABSENT"
  fi
done

section "CURRENT_SURICATA_CONFIG"
for p in "$DFDIR/suricata.yaml" "$DFDIR/raw-capture.bpf"; do
  echo "--- FILE=$p"
  if [ -r "$p" ]; then
    sha256sum "$p" 2>/dev/null || true
    sed -n '1,260p' "$p" 2>/dev/null || true
  else
    echo "NOT_READABLE_OR_ABSENT"
  fi
done

section "SAFE_FINGERPRINT_ENV"
python3 - <<'PY'
import json
from pathlib import Path

FILES = [
    Path("/etc/captive-portal/device-fingerprint/evidence.env"),
    Path("/etc/captive-portal/device-fingerprint/sensor.env"),
    Path("/etc/default/captive-portal"),
]

WHITELIST = {
    # Evidence
    "DEVICE_FINGERPRINT_EVIDENCE_ENABLED",
    "DEVICE_FINGERPRINT_DB_PATH",
    "DEVICE_FINGERPRINT_WRITER_LOCK_PATH",
    "DEVICE_FINGERPRINT_BIND_ADDRESS",
    "DEVICE_FINGERPRINT_PORT",
    "DEVICE_FINGERPRINT_TLS_CERT_PATH",
    "DEVICE_FINGERPRINT_TLS_KEY_PATH",
    "DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS",
    "DEVICE_FINGERPRINT_RETENTION_DAYS",
    "DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS",
    "DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS",
    "DEVICE_FINGERPRINT_MAX_DB_BYTES",
    "DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES",
    "DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH",
    "DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES",
    "DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS",
    # Portal producer
    "DEVICE_FINGERPRINT_PORTAL_ENABLED",
    "DEVICE_FINGERPRINT_PORTAL_PRODUCER_ID",
    "DEVICE_FINGERPRINT_PORTAL_CAPTURE_SOURCE_ID",
    "DEVICE_FINGERPRINT_PORTAL_SITE_ID",
    "DEVICE_FINGERPRINT_PORTAL_GUEST_CIDRS",
    "DEVICE_FINGERPRINT_PORTAL_ALLOWED_SSIDS",
    "DEVICE_FINGERPRINT_PORTAL_EVIDENCE_BASE_URL",
    "DEVICE_FINGERPRINT_PORTAL_CA_CERT_PATH",
    "DEVICE_FINGERPRINT_PORTAL_CREDENTIAL_PATH",
    "DEVICE_FINGERPRINT_PORTAL_QUEUE_MAX_EVENTS",
    "DEVICE_FINGERPRINT_PORTAL_BATCH_SIZE",
    "DEVICE_FINGERPRINT_PORTAL_QUEUE_MAX_AGE_SECONDS",
    "DEVICE_FINGERPRINT_PORTAL_COALESCE_SECONDS",
    "DEVICE_FINGERPRINT_PORTAL_COALESCE_MAX_ENTRIES",
    "DEVICE_FINGERPRINT_PORTAL_CONNECT_TIMEOUT_SECONDS",
    "DEVICE_FINGERPRINT_PORTAL_READ_TIMEOUT_SECONDS",
    "DEVICE_FINGERPRINT_PORTAL_TRANSIENT_COOLDOWN_SECONDS",
    "DEVICE_FINGERPRINT_PORTAL_REJECT_COOLDOWN_SECONDS",
    # Sensor
    "DEVICE_FINGERPRINT_SENSOR_ENABLED",
    "DEVICE_FINGERPRINT_SENSOR_INTERFACE",
    "DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID",
    "DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID",
    "DEVICE_FINGERPRINT_SENSOR_SITE_ID",
    "DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS",
    "DEVICE_FINGERPRINT_SENSOR_DHCP_SERVER_AUTHORITY",
    "DEVICE_FINGERPRINT_SENSOR_DHCP_OPTION54_AUTHORITY",
    "DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL",
    "DEVICE_FINGERPRINT_SENSOR_CA_CERT_PATH",
    "DEVICE_FINGERPRINT_SENSOR_SPOOL_PATH",
    "DEVICE_FINGERPRINT_SENSOR_SPOOL_TOTAL_BUDGET_BYTES",
    "DEVICE_FINGERPRINT_SENSOR_SPOOL_MAIN_DB_MAX_BYTES",
    "DEVICE_FINGERPRINT_SENSOR_SPOOL_WRITE_HEADROOM_BYTES",
    "DEVICE_FINGERPRINT_SENSOR_SPOOL_MAX_EVENTS",
    "DEVICE_FINGERPRINT_SENSOR_DELIVERY_BATCH_SIZE",
    "DEVICE_FINGERPRINT_SENSOR_HTTP_TIMEOUT_SECONDS",
    "DEVICE_FINGERPRINT_SENSOR_RAW_DEDUP_MAX_ENTRIES",
    "DEVICE_FINGERPRINT_SENSOR_RAW_DEDUP_HORIZON_MS",
    "DEVICE_FINGERPRINT_SENSOR_CORE_READY_HOST",
    "DEVICE_FINGERPRINT_SENSOR_CORE_READY_PORT",
    "DEVICE_FINGERPRINT_SENSOR_CORE_READY_CONNECT_TIMEOUT_SECONDS",
    "DEVICE_FINGERPRINT_SENSOR_CORE_READY_POLL_INTERVAL_SECONDS",
    "DEVICE_FINGERPRINT_SENSOR_CORE_READY_MAX_WAIT_SECONDS",
    "DEVICE_FINGERPRINT_SENSOR_EVE_MAX_DATAGRAM_BYTES",
    "DEVICE_FINGERPRINT_SENSOR_EVE_SOCKET_PATH",
    "DEVICE_FINGERPRINT_SENSOR_EVE_SOCKET_WAIT_SECONDS",
}

def parse_env(path):
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
            v = v[1:-1]
        values[k] = v
    return values

for path in FILES:
    print(f"--- ENV_FILE={path}")
    if not path.is_file():
        print("PRESENT=NO")
        continue
    print("PRESENT=YES")
    vals = parse_env(path)
    for k in sorted(WHITELIST):
        if k in vals:
            print(f"{k}={vals[k]}")
    if "DEVICE_FINGERPRINT_PRODUCERS_JSON" in vals:
        raw = vals["DEVICE_FINGERPRINT_PRODUCERS_JSON"]
        try:
            producers = json.loads(raw)
            print(f"DEVICE_FINGERPRINT_PRODUCERS_COUNT={len(producers) if isinstance(producers, list) else 'INVALID'}")
            if isinstance(producers, list):
                for i, p in enumerate(producers):
                    if not isinstance(p, dict):
                        print(f"PRODUCER_{i}=INVALID")
                        continue
                    safe = {
                        "producer_id": p.get("producer_id"),
                        "capture_source_id": p.get("capture_source_id"),
                        "site_id": p.get("site_id"),
                        "allowed_guest_cidrs": p.get("allowed_guest_cidrs"),
                        "allowed_source_kinds": p.get("allowed_source_kinds"),
                        "bearer_token_present": bool(p.get("bearer_token")),
                        "bearer_token_length": len(p.get("bearer_token", "")) if isinstance(p.get("bearer_token"), str) else None,
                    }
                    print("PRODUCER_SAFE_" + str(i) + "=" + json.dumps(safe, sort_keys=True, separators=(",", ":")))
        except Exception as exc:
            print(f"DEVICE_FINGERPRINT_PRODUCERS_PARSE=ERROR:{type(exc).__name__}")
PY

section "EVIDENCE_DB_STORAGE"
python3 - <<'PY'
from pathlib import Path
import sqlite3

env = Path("/etc/captive-portal/device-fingerprint/evidence.env")
db = Path("/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3")
if env.is_file():
    vals={}
    for raw in env.read_text(encoding="utf-8", errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line=line[7:].lstrip()
        if "=" in line:
            k,v=line.split("=",1)
            vals[k.strip()]=v.strip().strip("'\"")
    db=Path(vals.get("DEVICE_FINGERPRINT_DB_PATH", str(db)))
    budget=vals.get("DEVICE_FINGERPRINT_MAX_DB_BYTES")
else:
    budget=None

print(f"DB_PATH={db}")
print(f"CONFIG_MAX_DB_BYTES={budget}")
for suffix in ("", "-wal", "-shm"):
    p=Path(str(db)+suffix)
    if p.exists():
        st=p.stat()
        print(f"FILE{suffix or '_MAIN'}_BYTES={st.st_size}")
    else:
        print(f"FILE{suffix or '_MAIN'}_ABSENT=YES")

if db.is_file():
    uri=f"file:{db}?mode=ro"
    try:
        conn=sqlite3.connect(uri, uri=True, timeout=5)
        conn.execute("PRAGMA query_only=ON")
        for pragma in ("journal_mode","page_size","page_count","freelist_count","auto_vacuum"):
            try:
                value=conn.execute(f"PRAGMA {pragma}").fetchone()[0]
                print(f"PRAGMA_{pragma.upper()}={value}")
            except Exception as exc:
                print(f"PRAGMA_{pragma.upper()}_ERROR={type(exc).__name__}")
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        print("TABLES=" + ",".join(tables))
        for table in ("device_fingerprint_evidence","device_fingerprint_source_health_events"):
            if table in tables:
                try:
                    row=conn.execute(f"SELECT MAX(ingest_sequence) FROM {table}").fetchone()
                    print(f"{table.upper()}_MAX_INGEST_SEQUENCE={row[0]}")
                except Exception as exc:
                    print(f"{table.upper()}_MAX_INGEST_SEQUENCE_ERROR={type(exc).__name__}")
        conn.close()
    except Exception as exc:
        print(f"DB_READ_ONLY_OPEN_ERROR={type(exc).__name__}:{exc}")
PY

section "DATA_DIRECTORY_INVENTORY"
find "$APP/data" -maxdepth 1 -type f -printf '%M %u:%g %s %TY-%Tm-%TdT%TH:%TM:%TS %f\n' 2>/dev/null | sort || true

section "DEPLOY_WORKTREES"
for d in "$APP" /home/admin/CaptivePortal-Deploy/*; do
  [ -d "$d/.git" ] || [ -f "$d/.git" ] || continue
  echo "--- WORKTREE=$d"
  git -C "$d" rev-parse HEAD 2>/dev/null | sed 's/^/HEAD=/'
  git -C "$d" rev-parse 'HEAD^{tree}' 2>/dev/null | sed 's/^/TREE=/'
  if [ -z "$(git -C "$d" status --porcelain=v1 2>/dev/null)" ]; then
    echo "CLEAN=YES"
  else
    echo "CLEAN=NO"
    git -C "$d" status --porcelain=v1 2>/dev/null | sed 's/^/CHANGE=/'
  fi
  git -C "$d" log -1 --format='COMMIT_TIME=%cI%nSUBJECT=%s' 2>/dev/null || true
done

section "LOADED_ARTIFACT_IDENTITIES"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service; do
  echo "--- UNIT=$u"
  journalctl -u "$u" --no-pager 2>/dev/null \
    | grep -E 'artifact_sha|artifact_tree|artifact_identity' \
    | tail -n 12 \
    | sed -E \
      -e 's/(Bearer[[:space:]]+)[A-Za-z0-9._-]+/\1<REDACTED>/g' \
      -e 's/((token|secret|password)[=:][[:space:]]*)[^[:space:]]+/\1<REDACTED>/Ig' \
    || true
done

section "RECENT_FINGERPRINT_ERRORS"
for u in fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- UNIT=$u"
  journalctl -u "$u" --since "7 days ago" --no-pager 2>/dev/null \
    | grep -Ei 'error|failed|failure|no space|retry|drop|runtime_state' \
    | tail -n 120 \
    | sed -E \
      -e 's/(Bearer[[:space:]]+)[A-Za-z0-9._-]+/\1<REDACTED>/g' \
      -e 's/((token|secret|password)[=:][[:space:]]*)[^[:space:]]+/\1<REDACTED>/Ig' \
    || true
done

section "CLASSIFICATION_CONTROL_PLANE_PRESENCE"
find "$APP/data" /var/lib/captive-portal -maxdepth 3 \( -iname '*classification*' -o -iname '*control*plane*' -o -iname '*runtime*profile*' \) \
  -printf '%M %u:%g %s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort || true

section "FINAL"
echo "TARGETED_PREFLIGHT_R2_COMPLETE=YES"
echo "NO_CHANGES_PERFORMED=YES"
