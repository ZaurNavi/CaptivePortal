#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"
WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"

STAGED_SEED="/tmp/task04-production-control-plane-seed.sqlite3"
EXPECTED_SEED_SHA="091334a08bde5099c26c5f53252fb83d656f9c71b8ee28f4b0a03db46483ba28"

DATA_DIR="/opt/CaptivePortal/data"
CONTROL_DB="${DATA_DIR}/device_fingerprint_control_plane.sqlite3"
CLASS_DB="${DATA_DIR}/device_fingerprint_classification.sqlite3"
EVIDENCE_DB="${DATA_DIR}/device_fingerprint_evidence.sqlite3"

FOUNDATION_PROFILE_ID="FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_PROFILE_SHA="9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_ACTIVATION_ID="76ec5dd6-a1a7-4107-8c4d-e1401f064e84"

CRP_ID="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CRP_SHA="1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
ACCEPTANCE_ID="Task04AcceptanceManifest:v1:sha256:ca2712fbd643b332594990e67dc95ec017507d2d4d51d61f549d357bad18ca54"
CLASS_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
CLASS_RPM_SHA="7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
FOUNDATION_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
FOUNDATION_ADMISSION_ID="FoundationAdmissionManifest:v1:sha256:44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"

REPORT="/home/admin/device-fingerprint-task04-control-plane-materialize.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
AUDIT_DIR="/home/admin/captivportal-recovery/task04-control-plane-materialize-${STAMP}"

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

cleanup() {
  rc=$?
  rm -f "${CONTROL_DB}.incoming.$$" 2>/dev/null || true
  if [ "$rc" -ne 0 ]; then
    echo
    echo "===== ABORT ====="
    echo "EXIT_CODE=$rc"
    echo "CLASSIFICATION_ACTIVATION=NO"
    echo "SERVICES_RESTARTED=NO"
  fi
  exit "$rc"
}
trap cleanup EXIT

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."

step "SAFETY / PRESTATE"
date -Is
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "STAGED_SEED=$STAGED_SEED"
echo "EXPECTED_SEED_SHA=$EXPECTED_SEED_SHA"
echo "CONTROL_DB=$CONTROL_DB"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "ACTIVATE_PROFILE_CALL=FORBIDDEN"
echo "SERVICES_RESTARTED=NO"

[ -f "$STAGED_SEED" ] || die "Staged seed is missing."
[ -f "$CLASS_DB" ] || die "Dormant classification DB is missing."
[ -f "$EVIDENCE_DB" ] || die "Evidence DB is missing."
[ ! -e "$CONTROL_DB" ] || die "Production control-plane DB already exists; refusing first materialization."

[ -e "$WT/.git" ] || die "Exact Task-04 worktree missing."
WT_HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
WT_TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
echo "WORKTREE_HEAD=$WT_HEAD"
echo "WORKTREE_TREE=$WT_TREE"
[ "$WT_HEAD" = "$TARGET_SHA" ] || die "Task-04 worktree HEAD mismatch."
[ "$WT_TREE" = "$TARGET_TREE" ] || die "Task-04 worktree TREE mismatch."
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "Task-04 worktree dirty."
echo "WORKTREE_PROVENANCE=PASS"

PORTAL_PID_BEFORE="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_BEFORE="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_BEFORE="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_BEFORE="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u is not active."
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
done

step "VERIFY STAGED SEED SHA"
ACTUAL_SEED_SHA="$(sha256sum "$STAGED_SEED" | awk '{print $1}')"
echo "ACTUAL_SEED_SHA=$ACTUAL_SEED_SHA"
[ "$ACTUAL_SEED_SHA" = "$EXPECTED_SEED_SHA" ] || die "Seed SHA mismatch."
echo "SEED_SHA=PASS"

step "READ-ONLY SEED VALIDATION"
env PYTHONPATH="$WT" \
  DB="$STAGED_SEED" \
  FOUNDATION_PROFILE_ID="$FOUNDATION_PROFILE_ID" \
  FOUNDATION_PROFILE_SHA="$FOUNDATION_PROFILE_SHA" \
  FOUNDATION_ACTIVATION_ID="$FOUNDATION_ACTIVATION_ID" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" \
  ACCEPTANCE_ID="$ACCEPTANCE_ID" \
  CLASS_RPM_ID="$CLASS_RPM_ID" CLASS_RPM_SHA="$CLASS_RPM_SHA" \
  FOUNDATION_RPM_ID="$FOUNDATION_RPM_ID" \
  FOUNDATION_ADMISSION_ID="$FOUNDATION_ADMISSION_ID" \
  /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

db = os.environ["DB"]

conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
try:
    assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"

    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    expected_tables = {
        "artifacts", "artifact_dependencies", "activations", "validities",
        "validity_heads", "active_pointers", "f_admit_publications",
    }
    assert expected_tables.issubset(tables), (tables, expected_tables)

    pointers = [dict(r) for r in conn.execute(
        "SELECT * FROM active_pointers ORDER BY profile_kind"
    )]
    assert len(pointers) == 1, pointers
    fp = pointers[0]
    assert fp["profile_kind"] == "foundation", fp
    assert fp["runtime_profile_id"] == os.environ["FOUNDATION_PROFILE_ID"], fp
    assert fp["runtime_profile_digest"] == os.environ["FOUNDATION_PROFILE_SHA"], fp
    assert fp["activation_record_id"] == os.environ["FOUNDATION_ACTIVATION_ID"], fp

    activation_counts = {
        r["profile_kind"]: r["n"]
        for r in conn.execute(
            "SELECT profile_kind,COUNT(*) AS n FROM activations GROUP BY profile_kind"
        )
    }
    assert activation_counts == {"foundation": 1}, activation_counts

    required = {
        os.environ["FOUNDATION_PROFILE_ID"],
        os.environ["CRP_ID"],
        os.environ["ACCEPTANCE_ID"],
        os.environ["CLASS_RPM_ID"],
        os.environ["FOUNDATION_RPM_ID"],
        os.environ["FOUNDATION_ADMISSION_ID"],
    }
    present = {
        r[0] for r in conn.execute(
            "SELECT artifact_id FROM artifacts WHERE artifact_id IN (%s)"
            % ",".join("?" for _ in required),
            tuple(required),
        )
    }
    assert present == required, (required - present)

    class_pointer = conn.execute(
        "SELECT 1 FROM active_pointers WHERE profile_kind='classification'"
    ).fetchone()
    class_activation = conn.execute(
        "SELECT 1 FROM activations WHERE profile_kind='classification' LIMIT 1"
    ).fetchone()
    assert class_pointer is None
    assert class_activation is None
finally:
    conn.close()

store = DeviceFingerprintControlPlaneStore(db)

foundation = store.pin_active_profile("foundation")
assert foundation.pointer.runtime_profile_id == os.environ["FOUNDATION_PROFILE_ID"]
assert foundation.pointer.runtime_profile_digest == os.environ["FOUNDATION_PROFILE_SHA"]
assert foundation.pointer.activation_record_id == os.environ["FOUNDATION_ACTIVATION_ID"]

assert store.get_active_pointer("classification") is None

rpm = store.load_artifact(os.environ["CLASS_RPM_ID"], os.environ["CLASS_RPM_SHA"])
crp = store.load_artifact(os.environ["CRP_ID"], os.environ["CRP_SHA"])
assert rpm.semantic_payload["profile_kind"] == "classification"
assert rpm.semantic_payload["candidate_profile"] == {
    "artifact_id": os.environ["CRP_ID"],
    "content_sha256": os.environ["CRP_SHA"],
}
assert rpm.semantic_payload["update_class"] == "INITIAL_CLASSIFICATION"
assert rpm.semantic_payload["previous_active_profile"] is None
assert rpm.semantic_payload["expected_previous_activation_record_id"] is None
assert rpm.semantic_payload["expected_previous_activation_generation_id"] is None

with store._connect() as conn:
    store._closure(conn, crp)
    store._closure(conn, rpm)

print("SEED_QUICK_CHECK=PASS")
print("FOUNDATION_PIN=PASS")
print("CLASSIFICATION_POINTER=ABSENT")
print("CLASSIFICATION_ACTIVATION_ROWS=0")
print("CLASSIFICATION_CRP_CLOSURE=PASS")
print("CLASSIFICATION_RPM_CLOSURE=PASS")
print("SEED_READONLY_VALIDATION=PASS")
PY

step "VERIFY DORMANT CLASSIFICATION STORE UNCHANGED"
env CLASS_DB="$CLASS_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
db=os.environ["CLASS_DB"]
conn=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
try:
    assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("artifacts","artifact_dependencies","classifications","classification_roots")
    }
    assert counts == {
        "artifacts": 0,
        "artifact_dependencies": 0,
        "classifications": 0,
        "classification_roots": 0,
    }, counts
    print("CLASSIFICATION_DB_EMPTY=PASS")
finally:
    conn.close()
PY

step "AUDIT MANIFEST BEFORE MATERIALIZATION"
install -d -o admin -g admin "$AUDIT_DIR"
{
  echo "TARGET_SHA=$TARGET_SHA"
  echo "TARGET_TREE=$TARGET_TREE"
  echo "SEED_SHA256=$ACTUAL_SEED_SHA"
  echo "CONTROL_DB=$CONTROL_DB"
  echo "FOUNDATION_PROFILE_ID=$FOUNDATION_PROFILE_ID"
  echo "FOUNDATION_ACTIVATION_ID=$FOUNDATION_ACTIVATION_ID"
  echo "CLASSIFICATION_PROFILE_ID=$CRP_ID"
  echo "CLASSIFICATION_RPM_ID=$CLASS_RPM_ID"
  echo "CLASSIFICATION_ACTIVATION=NO"
} > "$AUDIT_DIR/materialization-manifest.txt"
chown -R admin:admin "$AUDIT_DIR"

step "ATOMIC MATERIALIZATION"
TMP="${CONTROL_DB}.incoming.$$"

STAGED_SEED="$STAGED_SEED" TMP="$TMP" /usr/bin/python3 - <<'PY'
import os, shutil
src=os.environ["STAGED_SEED"]
dst=os.environ["TMP"]
with open(src, "rb") as r, open(dst, "xb") as w:
    shutil.copyfileobj(r, w, length=1024*1024)
    w.flush()
    os.fsync(w.fileno())
PY

chown admin:admin "$TMP"
chmod 0640 "$TMP"

TMP_SHA="$(sha256sum "$TMP" | awk '{print $1}')"
[ "$TMP_SHA" = "$EXPECTED_SEED_SHA" ] || die "Incoming control DB SHA mismatch."

mv "$TMP" "$CONTROL_DB"
sync

[ -f "$CONTROL_DB" ] || die "Control-plane DB materialization failed."
CONTROL_SHA="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
echo "CONTROL_DB_SHA256=$CONTROL_SHA"
[ "$CONTROL_SHA" = "$EXPECTED_SEED_SHA" ] || die "Installed control-plane SHA mismatch."
echo "CONTROL_PLANE_BYTE_IDENTITY=PASS"

step "POST-MATERIALIZATION CONTROL-PLANE VALIDATION"
env PYTHONPATH="$WT" \
  DB="$CONTROL_DB" \
  FOUNDATION_PROFILE_ID="$FOUNDATION_PROFILE_ID" \
  FOUNDATION_PROFILE_SHA="$FOUNDATION_PROFILE_SHA" \
  FOUNDATION_ACTIVATION_ID="$FOUNDATION_ACTIVATION_ID" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" \
  CLASS_RPM_ID="$CLASS_RPM_ID" CLASS_RPM_SHA="$CLASS_RPM_SHA" \
  /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

db=os.environ["DB"]
conn=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
try:
    assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert conn.execute(
        "SELECT COUNT(*) FROM active_pointers WHERE profile_kind='foundation'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM active_pointers WHERE profile_kind='classification'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM activations WHERE profile_kind='classification'"
    ).fetchone()[0] == 0
finally:
    conn.close()

store=DeviceFingerprintControlPlaneStore(db)
foundation=store.pin_active_profile("foundation")
assert foundation.pointer.runtime_profile_id == os.environ["FOUNDATION_PROFILE_ID"]
assert foundation.pointer.runtime_profile_digest == os.environ["FOUNDATION_PROFILE_SHA"]
assert foundation.pointer.activation_record_id == os.environ["FOUNDATION_ACTIVATION_ID"]
assert store.get_active_pointer("classification") is None

rpm=store.load_artifact(os.environ["CLASS_RPM_ID"], os.environ["CLASS_RPM_SHA"])
crp=store.load_artifact(os.environ["CRP_ID"], os.environ["CRP_SHA"])
with store._connect() as conn:
    store._closure(conn, crp)
    store._closure(conn, rpm)

print("PROD_CONTROL_QUICK_CHECK=PASS")
print("PROD_FOUNDATION_PIN=PASS")
print("PROD_CLASSIFICATION_POINTER=ABSENT")
print("PROD_CLASSIFICATION_ACTIVATION_ROWS=0")
print("PROD_CLASSIFICATION_CLOSURE=PASS")
PY

step "SERVICE IMMUTABILITY"
PORTAL_PID_AFTER="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_AFTER="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_AFTER="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_AFTER="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

[ "$PORTAL_PID_BEFORE" = "$PORTAL_PID_AFTER" ] || die "captive-portal restarted unexpectedly."
[ "$EVIDENCE_PID_BEFORE" = "$EVIDENCE_PID_AFTER" ] || die "evidence restarted unexpectedly."
[ "$SENSOR_PID_BEFORE" = "$SENSOR_PID_AFTER" ] || die "sensor restarted unexpectedly."
[ "$SURICATA_PID_BEFORE" = "$SURICATA_PID_AFTER" ] || die "suricata restarted unexpectedly."

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u is not active after materialization."
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
done
echo "EXISTING_SERVICE_PIDS_UNCHANGED=PASS"

step "FINAL"
stat -c 'CONTROL_DB path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' "$CONTROL_DB"
echo "TASK04_PROD_CONTROL_PLANE_MATERIALIZE=PASS"
echo "PROD_FOUNDATION_POINTER=ACTIVE_EXACT"
echo "PROD_CLASSIFICATION_RPM=PRESENT_ACCEPTED"
echo "PROD_CLASSIFICATION_POINTER=ABSENT"
echo "PROD_CLASSIFICATION_ACTIVATION_ROWS=0"
echo "PROD_CLASSIFICATION_EXECUTION=OFF"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "SERVICES_RESTARTED=NO"
echo "CONTROL_DB_SHA256=$CONTROL_SHA"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "REPORT=$REPORT"

trap - EXIT
