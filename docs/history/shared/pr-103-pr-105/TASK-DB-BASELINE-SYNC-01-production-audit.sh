#!/usr/bin/env bash
set -u

EXPECTED_HEAD="3761981f4b1ec30b330abe1eec1713f15191c711"
EXPECTED_TREE="2e6ac33f1033c1f0587407a2476ca852373a04e6"
APP="/opt/CaptivePortal"
SERVICE="captive-portal.service"
PROJ_SERVICE="traffic-projection.service"

fail() {
  echo "FATAL=$*"
  exit 2
}

echo "=== TASK-DB-BASELINE-SYNC-01 PRODUCTION AUDIT ==="
echo "AUDIT_STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "USER=$(id -un)"
echo "HOST=$(hostname)"

cd "$APP" || fail "cannot cd to $APP"

HEAD="$(git rev-parse HEAD 2>/dev/null)" || fail "cannot read git HEAD"
TREE="$(git rev-parse 'HEAD^{tree}' 2>/dev/null)" || fail "cannot read git tree"
STATUS="$(git status --short 2>/dev/null)" || fail "cannot read git status"

echo "PROD_HEAD=$HEAD"
echo "PROD_TREE=$TREE"
if [ -n "$STATUS" ]; then
  echo "PROD_WORKTREE=CLEAN:no"
  printf '%s\n' "$STATUS"
  fail "production worktree is not clean"
fi
echo "PROD_WORKTREE=CLEAN:yes"

[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "unexpected production tree"

CP_ACTIVE="$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
echo "CAPTIVE_PORTAL_SERVICE=$CP_ACTIVE"
[ "$CP_ACTIVE" = "active" ] || fail "captive-portal.service is not active"

PID="$(systemctl show -p MainPID --value "$SERVICE" 2>/dev/null || true)"
case "$PID" in
  ''|0) fail "captive-portal.service has no live MainPID" ;;
esac

TMP_ENV="$(mktemp)"
trap 'rm -f "$TMP_ENV"' EXIT

# Read only the allowlisted non-secret runtime variables from the actual service process.
sudo sh -c "tr '\0' '\n' < /proc/$PID/environ" \
  | grep -E '^(PUBLIC_TRAFFIC_COUNTER_ENABLED|PUBLIC_TRAFFIC_DB_PATH|VISITOR_REGISTRY_ENABLED|VISITOR_REGISTRY_DB_PATH|VISIT_LIFECYCLE_ENABLED|VISIT_LIFECYCLE_DB_PATH|OBSERVATION_FOUNDATION_ENABLED|OBSERVATION_DB_PATH|CURRENT_STATE_ENABLED|CURRENT_STATE_DB_PATH|TRAFFIC_PROJECTION_ENABLED|TRAFFIC_PROJECTION_DB_PATH|WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED)=' \
  > "$TMP_ENV" || true

echo "=== ALLOWLISTED RUNTIME DB CONFIG ==="
cat "$TMP_ENV"

# Read-only DB audit. Do not use sudo python3: project production dependencies live
# in the admin user's environment, and stdlib sqlite3 is sufficient here.
ENV_SNAPSHOT="$TMP_ENV" /usr/bin/python3 - <<'PY'
from __future__ import annotations
import json, os, sqlite3
from pathlib import Path

env = {}
with open(os.environ["ENV_SNAPSHOT"], "r", encoding="utf-8") as fh:
    for raw in fh:
        raw = raw.rstrip("\n")
        if "=" in raw:
            k, v = raw.split("=", 1)
            env[k] = v

def b(name, default):
    return env.get(name, default).strip().lower() == "true"

specs = [
    ("OBSERVATION", b("OBSERVATION_FOUNDATION_ENABLED","false"),
     env.get("OBSERVATION_DB_PATH","/opt/CaptivePortal/data/observations.sqlite3"), 1),
    ("VISITS", b("VISIT_LIFECYCLE_ENABLED","false"),
     env.get("VISIT_LIFECYCLE_DB_PATH","/opt/CaptivePortal/data/visits.sqlite3"), 2),
    ("TRAFFIC_PROJECTION", b("TRAFFIC_PROJECTION_ENABLED","false"),
     env.get("TRAFFIC_PROJECTION_DB_PATH","/opt/CaptivePortal/data/traffic_projection.sqlite3"), 1),
    ("CURRENT_STATE", b("CURRENT_STATE_ENABLED","false"),
     env.get("CURRENT_STATE_DB_PATH","/opt/CaptivePortal/data/current_state.sqlite3"), 1),
    ("VISITOR_REGISTRY", b("VISITOR_REGISTRY_ENABLED","false"),
     env.get("VISITOR_REGISTRY_DB_PATH","/opt/CaptivePortal/data/visitor_registry.sqlite3"), 1),
    ("PUBLIC_TRAFFIC", b("PUBLIC_TRAFFIC_COUNTER_ENABLED","true"),
     env.get("PUBLIC_TRAFFIC_DB_PATH","/opt/CaptivePortal/data/public_traffic.sqlite3"), 2),
    ("PORTAL_COUNTER", True,
     "/opt/CaptivePortal/data/portal_counter.db", 1),
]

results = {}
for name, enabled, path_s, expected in specs:
    path = Path(path_s)
    item = {
        "name": name,
        "enabled": enabled,
        "path": str(path),
        "exists": path.is_file(),
        "size": path.stat().st_size if path.is_file() else 0,
        "expected_schema_version": expected,
        "user_version": None,
        "quick_check": None,
        "foreign_key_violations": None,
        "tables": [],
        "indexes": [],
        "triggers": [],
        "migration_required": None,
        "migration_applied": False,
        "error": None,
    }
    if path.is_file():
        try:
            uri = path.resolve().as_uri() + "?mode=ro"
            con = sqlite3.connect(uri, uri=True, timeout=5.0)
            try:
                con.execute("PRAGMA query_only=ON")
                item["user_version"] = int(con.execute("PRAGMA user_version").fetchone()[0])
                q = [str(r[0]) for r in con.execute("PRAGMA quick_check").fetchall()]
                item["quick_check"] = "ok" if q == ["ok"] else ";".join(q)
                item["foreign_key_violations"] = len(con.execute("PRAGMA foreign_key_check").fetchall())
                rows = con.execute(
                    "SELECT type,name FROM sqlite_master "
                    "WHERE type IN ('table','index','trigger') "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
                ).fetchall()
                for typ, obj in rows:
                    item[typ + "es" if typ == "index" else typ + "s"].append(obj)
            finally:
                con.close()
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}:{exc}"
        item["migration_required"] = (
            item["user_version"] is None or item["user_version"] != expected
        )
    else:
        item["migration_required"] = bool(enabled)
    results[name] = item
    print("DB_FACT=" + json.dumps(item, ensure_ascii=False, sort_keys=True))

# Fail closed if an enabled store is absent/unhealthy/mismatched.
blocking = []
for name, item in results.items():
    if not item["enabled"]:
        continue
    if not item["exists"]:
        blocking.append(f"{name}:missing")
    elif item["quick_check"] != "ok":
        blocking.append(f"{name}:quick_check={item['quick_check']}")
    elif item["foreign_key_violations"] != 0:
        blocking.append(f"{name}:fk={item['foreign_key_violations']}")
    elif item["user_version"] != item["expected_schema_version"]:
        blocking.append(
            f"{name}:schema={item['user_version']} expected={item['expected_schema_version']}"
        )

with open("/tmp/captivportal-db-baseline-audit.json", "w", encoding="utf-8") as fh:
    json.dump({"databases": results, "blocking": blocking}, fh, ensure_ascii=False, indent=2)

print("DB_AUDIT_BLOCKERS=" + ("none" if not blocking else "|".join(blocking)))
PY

DB_BLOCKERS="$(/usr/bin/python3 - <<'PY'
import json
with open("/tmp/captivportal-db-baseline-audit.json", encoding="utf-8") as f:
    d=json.load(f)
print("none" if not d["blocking"] else "|".join(d["blocking"]))
PY
)"

if [ "$DB_BLOCKERS" != "none" ]; then
  echo "STOP_BEFORE_CHANGES=yes"
  echo "REASON=DB integrity/schema/availability blocker"
  echo "DB_AUDIT_BLOCKERS=$DB_BLOCKERS"
  exit 20
fi

PROJ_DB="$(awk -F= '$1=="TRAFFIC_PROJECTION_DB_PATH"{print substr($0,index($0,"=")+1)}' "$TMP_ENV" | tail -n1)"
[ -n "$PROJ_DB" ] || PROJ_DB="/opt/CaptivePortal/data/traffic_projection.sqlite3"

PROJ_ENABLED="$(awk -F= '$1=="TRAFFIC_PROJECTION_ENABLED"{print tolower($2)}' "$TMP_ENV" | tail -n1)"
[ -n "$PROJ_ENABLED" ] || PROJ_ENABLED="false"

PROJ_ACTIVE_PRE="$(systemctl is-active "$PROJ_SERVICE" 2>/dev/null || true)"
PROJ_ENABLED_SYSTEMD="$(systemctl is-enabled "$PROJ_SERVICE" 2>/dev/null || true)"
echo "PROJECTION_CONFIG_ENABLED=$PROJ_ENABLED"
echo "PROJECTION_SYSTEMD_ENABLED=$PROJ_ENABLED_SYSTEMD"
echo "PROJECTION_SERVICE_PRE=$PROJ_ACTIVE_PRE"

# Projection state reader using the current repository's own health classifier.
projection_state() {
  PROJ_DB="$PROJ_DB" /usr/bin/python3 - <<'PY'
from __future__ import annotations
import json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.traffic_projection.health import classify_projection_health

path = Path(os.environ["PROJ_DB"])
out = {
    "exists": path.is_file(),
    "versions": [],
    "sites": [],
    "healthy": False,
    "backlog": None,
    "divergence": True,
    "reconciliation_healthy": False,
}
if path.is_file():
    uri = path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    try:
        versions = [dict(r) for r in con.execute(
            "SELECT * FROM traffic_projection_versions ORDER BY projection_version"
        )]
        out["versions"] = versions
        status_by_version = {str(r.get("projection_version")): r.get("status") for r in versions}
        states = [dict(r) for r in con.execute(
            "SELECT * FROM traffic_projection_site_state ORDER BY projection_version,site_id"
        )]
        now = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        classified = []
        for state in states:
            version = str(state.get("projection_version"))
            build_state = status_by_version.get(version)
            h = classify_projection_health(
                state,
                now_utc=now,
                storage_available=True,
                version_available=build_state is not None,
                source_available=True,
                build_state=build_state,
            ).safe_dict()
            h["site_id"] = state.get("site_id")
            h["stored_status"] = state.get("status")
            classified.append(h)
        out["sites"] = classified
        active = [r for r in versions if r.get("status") == "active"]
        active_versions = {str(r.get("projection_version")) for r in active}
        active_sites = [r for r in classified if str(r.get("projection_version")) in active_versions]
        backlogs = [r.get("backlog_cycle_count") for r in active_sites]
        out["backlog"] = sum(int(x or 0) for x in backlogs) if active_sites else None
        out["divergence"] = any(
            r.get("status") == "diverged" or r.get("stored_status") == "diverged"
            for r in active_sites
        ) if active_sites else True
        out["healthy"] = bool(active_sites) and all(
            r.get("status") == "healthy" and int(r.get("backlog_cycle_count") or 0) == 0
            for r in active_sites
        )
        out["reconciliation_healthy"] = bool(active_sites) and all(
            r.get("last_full_reconcile_completed_at") is not None
            and r.get("status") == "healthy"
            for r in active_sites
        )
    finally:
        con.close()
print("PROJECTION_STATE=" + json.dumps(out, ensure_ascii=False, sort_keys=True))
PY
}

echo "=== PROJECTION STATE BEFORE RESTART ==="
projection_state

BACKUPS_CREATED="none"
BACKUP_QUICK_CHECK="not_required"

# Restart/catch-up validation is allowed only for an already-active worker.
# Do not silently activate/start a disabled or failed production service.
WORKER_RESTART_CATCHUP="FAIL"
if [ "$PROJ_ENABLED" = "true" ] && [ "$PROJ_ACTIVE_PRE" = "active" ]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  BKDIR="$APP/backups/db-baseline-sync-$STAMP"
  mkdir -p "$BKDIR" || fail "cannot create backup directory $BKDIR"
  BK="$BKDIR/traffic_projection.sqlite3"

  SRC="$PROJ_DB" DST="$BK" /usr/bin/python3 - <<'PY'
import os, sqlite3
from pathlib import Path
src=Path(os.environ["SRC"])
dst=Path(os.environ["DST"])
uri=src.resolve().as_uri()+"?mode=ro"
s=sqlite3.connect(uri, uri=True, timeout=5.0)
d=sqlite3.connect(dst)
try:
    s.backup(d)
finally:
    d.close(); s.close()
c=sqlite3.connect(dst)
try:
    q=[str(r[0]) for r in c.execute("PRAGMA quick_check").fetchall()]
    print("PROJECTION_BACKUP_QUICK_CHECK=" + ("ok" if q == ["ok"] else ";".join(q)))
finally:
    c.close()
print("PROJECTION_BACKUP_PATH="+str(dst))
print("PROJECTION_BACKUP_SIZE="+str(dst.stat().st_size))
PY

  BACKUPS_CREATED="$BK"
  BACKUP_QUICK_CHECK="$(BK="$BK" /usr/bin/python3 - <<'PY'
import os,sqlite3
c=sqlite3.connect(os.environ["BK"])
try:
    q=[str(r[0]) for r in c.execute("PRAGMA quick_check").fetchall()]
    print("ok" if q==["ok"] else ";".join(q))
finally:c.close()
PY
)"
  [ "$BACKUP_QUICK_CHECK" = "ok" ] || fail "projection backup quick_check failed"

  echo "=== RESTART PROJECTION WORKER ==="
  sudo systemctl restart "$PROJ_SERVICE" || fail "traffic-projection.service restart failed"

  ACTIVE_OK=no
  i=1
  while [ "$i" -le 10 ]; do
    S="$(systemctl is-active "$PROJ_SERVICE" 2>/dev/null || true)"
    echo "PROJECTION_SERVICE_WAIT[$i]=$S"
    if [ "$S" = "active" ]; then
      ACTIVE_OK=yes
      break
    fi
    sleep 3
    i=$((i+1))
  done

  if [ "$ACTIVE_OK" = "yes" ]; then
    i=1
    while [ "$i" -le 18 ]; do
      SNAP="$(projection_state)"
      echo "PROJECTION_CATCHUP[$i]=$SNAP"
      OK="$(printf '%s\n' "$SNAP" | sed -n 's/^PROJECTION_STATE=//p' | /usr/bin/python3 -c 'import json,sys; d=json.load(sys.stdin); print("yes" if d.get("healthy") and d.get("backlog")==0 and not d.get("divergence") and d.get("reconciliation_healthy") else "no")')"
      if [ "$OK" = "yes" ]; then
        WORKER_RESTART_CATCHUP="PASS"
        break
      fi
      sleep 5
      i=$((i+1))
    done
  fi
else
  echo "PROJECTION_RESTART_SKIPPED=worker was not already active+enabled"
fi

echo "=== PROJECTION STATE AFTER RESTART ==="
PROJ_AFTER="$(projection_state)"
echo "$PROJ_AFTER"

# Emit final strict report fields.
ENV_SNAPSHOT="$TMP_ENV" \
EXPECTED_HEAD="$EXPECTED_HEAD" \
BACKUPS_CREATED="$BACKUPS_CREATED" \
BACKUP_QUICK_CHECK="$BACKUP_QUICK_CHECK" \
WORKER_RESTART_CATCHUP="$WORKER_RESTART_CATCHUP" \
PROJ_AFTER="$PROJ_AFTER" \
PROJ_ACTIVE_NOW="$(systemctl is-active "$PROJ_SERVICE" 2>/dev/null || true)" \
/usr/bin/python3 - <<'PY'
from __future__ import annotations
import json, os, re

with open("/tmp/captivportal-db-baseline-audit.json", encoding="utf-8") as f:
    audit=json.load(f)
db=audit["databases"]

raw=os.environ["PROJ_AFTER"]
m=re.search(r"PROJECTION_STATE=(\{.*\})", raw)
proj=json.loads(m.group(1)) if m else {}

def yn(v): return "yes" if v else "no"
def db_pass(name):
    x=db[name]
    return (
        x["exists"] and
        x["quick_check"]=="ok" and
        x["foreign_key_violations"]==0 and
        x["user_version"]==x["expected_schema_version"]
    )

obs=db["OBSERVATION"]; vis=db["VISITS"]; tp=db["TRAFFIC_PROJECTION"]
others=["CURRENT_STATE","VISITOR_REGISTRY","PUBLIC_TRAFFIC","PORTAL_COUNTER"]
active_others=[n for n in others if db[n]["enabled"]]
other_pass=all(db_pass(n) for n in active_others)

proj_worker_active=os.environ["PROJ_ACTIVE_NOW"]=="active"
proj_healthy=bool(proj.get("healthy"))
proj_backlog=proj.get("backlog")
proj_div=bool(proj.get("divergence", True))
restart_ok=os.environ["WORKER_RESTART_CATCHUP"]=="PASS"

final = (
    db_pass("OBSERVATION") and db_pass("VISITS") and db_pass("TRAFFIC_PROJECTION")
    and other_pass and proj_worker_active and proj_healthy
    and proj_backlog == 0 and not proj_div and restart_ok
)

blockers=[]
if not db_pass("OBSERVATION"): blockers.append("OBSERVATION_DB")
if not db_pass("VISITS"): blockers.append("VISITS_DB")
if not db_pass("TRAFFIC_PROJECTION"): blockers.append("TRAFFIC_PROJECTION_DB")
if not other_pass: blockers.append("OTHER_ACTIVE_DBS")
if not proj_worker_active: blockers.append("PROJECTION_WORKER_INACTIVE")
if not proj_healthy: blockers.append("PROJECTION_NOT_HEALTHY")
if proj_backlog != 0: blockers.append(f"PROJECTION_BACKLOG={proj_backlog}")
if proj_div: blockers.append("PROJECTION_DIVERGENCE")
if not restart_ok: blockers.append("WORKER_RESTART_CATCHUP")

print()
print("TASK-DB-BASELINE-SYNC-01")
print()
print("GIT/PRODUCTION_BASELINE="+os.environ["EXPECTED_HEAD"])
print()
print("OBSERVATION_DB="+("PASS" if db_pass("OBSERVATION") else "FAIL"))
print("OBSERVATION_USER_VERSION="+str(obs["user_version"]))
print("OBSERVATION_QUICK_CHECK="+str(obs["quick_check"]))
print("OBSERVATION_FK_VIOLATIONS="+str(obs["foreign_key_violations"]))
print("OBSERVATION_MIGRATION_REQUIRED="+yn(bool(obs["migration_required"])))
print("OBSERVATION_MIGRATION_APPLIED=no")
print()
print("VISITS_DB="+("PASS" if db_pass("VISITS") else "FAIL"))
print("VISITS_USER_VERSION="+str(vis["user_version"]))
print("VISITS_QUICK_CHECK="+str(vis["quick_check"]))
print("VISITS_FK_VIOLATIONS="+str(vis["foreign_key_violations"]))
print("VISITS_MIGRATION_REQUIRED="+yn(bool(vis["migration_required"])))
print("VISITS_MIGRATION_APPLIED=no")
print()
print("TRAFFIC_PROJECTION_DB="+("PASS" if db_pass("TRAFFIC_PROJECTION") else "FAIL"))
print("TRAFFIC_PROJECTION_USER_VERSION="+str(tp["user_version"]))
print("TRAFFIC_PROJECTION_QUICK_CHECK="+str(tp["quick_check"]))
print("TRAFFIC_PROJECTION_FK_VIOLATIONS="+str(tp["foreign_key_violations"]))
print("TRAFFIC_PROJECTION_MIGRATION_REQUIRED="+yn(bool(tp["migration_required"])))
print("TRAFFIC_PROJECTION_MIGRATION_APPLIED=no")
print()
print("PROJECTION_WORKER_ACTIVE="+yn(proj_worker_active))
print("PROJECTION_HEALTHY="+yn(proj_healthy))
print("PROJECTION_BACKLOG="+str(proj_backlog))
print("PROJECTION_DIVERGENCE="+yn(proj_div))
print("WORKER_RESTART_CATCHUP="+os.environ["WORKER_RESTART_CATCHUP"])
print()
print("OTHER_ACTIVE_DBS="+(",".join(active_others) if active_others else "none"))
print("OTHER_ACTIVE_DBS_STATUS="+("PASS" if other_pass else "FAIL"))
print()
print("BACKUPS_CREATED="+os.environ["BACKUPS_CREATED"])
print("BACKUP_QUICK_CHECK="+os.environ["BACKUP_QUICK_CHECK"])
print("DATA_REWRITTEN=no")
print("DESTRUCTIVE_ACTIONS=none")
print()
req=[]
for n,x in db.items():
    if x["enabled"] and x["migration_required"]:
        req.append(f"{n}:user_version={x['user_version']} expected={x['expected_schema_version']}")
print("REQUIRED_MIGRATIONS="+("none" if not req else "; ".join(req)))
print()
print("FINAL_DB_BASELINE="+("PASS" if final else "FAIL"))
print()
print("BLOCKERS_FOR_TRAFFIC_0_8="+("none" if not blockers else "; ".join(blockers)))
PY
