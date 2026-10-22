#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"
WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"

CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"

CRP_ID="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CRP_SHA="1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CLASS_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
CLASS_RPM_SHA="7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
ACCEPTANCE_ID="Task04AcceptanceManifest:v1:sha256:ca2712fbd643b332594990e67dc95ec017507d2d4d51d61f549d357bad18ca54"

FOUNDATION_PROFILE_ID="FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_PROFILE_SHA="9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
FOUNDATION_ACTIVATION_ID="76ec5dd6-a1a7-4107-8c4d-e1401f064e84"
TTL_ID="TTLCapturePlacementProof:v1:sha256:c48ffafa3856c4708a35e644bb4cc2b468275af9790df579a366d7ac71fc0ca2"
TTL_SHA="c48ffafa3856c4708a35e644bb4cc2b468275af9790df579a366d7ac71fc0ca2"

SURICATA_CONF="/etc/captive-portal/device-fingerprint/suricata.yaml"
SURICATA_UNIT="/etc/systemd/system/fingerprint-suricata.service"
SENSOR_ENV="/etc/captive-portal/device-fingerprint/sensor.env"

REPORT="/home/admin/device-fingerprint-task04-preactivate-r1.txt"

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."

step "SAFETY / DECLARATION"
date -Is
echo "MODE=READ_ONLY_PREACTIVATE"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "ACTIVATE_PROFILE_CALL=NO"
echo "SERVICE_RESTARTS=NO"

[ -f "$CONTROL_DB" ] || die "Control-plane DB missing."
[ -f "$CLASS_DB" ] || die "Classification DB missing."
[ -f "$EVIDENCE_DB" ] || die "Evidence DB missing."
[ -e "$WT/.git" ] || die "Task-04 exact worktree missing."

WT_HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
WT_TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
[ "$WT_HEAD" = "$TARGET_SHA" ] || die "Worktree HEAD mismatch."
[ "$WT_TREE" = "$TARGET_TREE" ] || die "Worktree tree mismatch."
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "Worktree dirty."
echo "WORKTREE_HEAD=$WT_HEAD"
echo "WORKTREE_TREE=$WT_TREE"
echo "WORKTREE_PROVENANCE=PASS"

CONTROL_SHA_BEFORE="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
CLASS_SHA_BEFORE="$(sha256sum "$CLASS_DB" | awk '{print $1}')"
echo "CONTROL_DB_SHA_BEFORE=$CONTROL_SHA_BEFORE"
echo "CLASS_DB_SHA_BEFORE=$CLASS_SHA_BEFORE"

PORTAL_PID_BEFORE="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_BEFORE="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_BEFORE="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_BEFORE="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

step "SERVICE HEALTH"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u is not active."
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
done
echo "ALL_REQUIRED_SERVICES_ACTIVE=PASS"

step "FOUNDATION / TASK04 CONTROL-PLANE COMPATIBILITY"
sudo -u admin env PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" \
  CLASS_RPM_ID="$CLASS_RPM_ID" CLASS_RPM_SHA="$CLASS_RPM_SHA" \
  ACCEPTANCE_ID="$ACCEPTANCE_ID" \
  FOUNDATION_PROFILE_ID="$FOUNDATION_PROFILE_ID" FOUNDATION_PROFILE_SHA="$FOUNDATION_PROFILE_SHA" \
  FOUNDATION_RPM_ID="$FOUNDATION_RPM_ID" FOUNDATION_ACTIVATION_ID="$FOUNDATION_ACTIVATION_ID" \
  TTL_ID="$TTL_ID" TTL_SHA="$TTL_SHA" \
  /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.ttl_capture_placement_proof import make_ttl_capture_placement_proof

control_db=os.environ["CONTROL_DB"]
class_db=os.environ["CLASS_DB"]

# Pure SQLite structural checks.
conn=sqlite3.connect(f"file:{control_db}?mode=ro", uri=True)
try:
    assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert conn.execute("SELECT COUNT(*) FROM active_pointers WHERE profile_kind='foundation'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM active_pointers WHERE profile_kind='classification'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM activations WHERE profile_kind='classification'").fetchone()[0] == 0
finally:
    conn.close()

store=DeviceFingerprintControlPlaneStore(control_db)

# Reconstruct the full published initial Foundation lineage after restart.
f_admit_gate, foundation_pin, foundation_admission, origin = store.load_published_initial_foundation()
assert f_admit_gate.semantic_payload["status"] == "PASS"
assert f_admit_gate.semantic_payload["gate_id"] == "F-ADMIT"

assert foundation_pin.pointer.runtime_profile_id == os.environ["FOUNDATION_PROFILE_ID"]
assert foundation_pin.pointer.runtime_profile_digest == os.environ["FOUNDATION_PROFILE_SHA"]
assert foundation_pin.pointer.activation_record_id == os.environ["FOUNDATION_ACTIVATION_ID"]
assert foundation_pin.admission_manifest.artifact_id == os.environ["FOUNDATION_RPM_ID"]
assert foundation_pin.validity_record.semantic_payload["state"] == "ACTIVE"
assert foundation_pin.validity_record.semantic_payload["inflight_commit_rule"] == "ALLOW_PINNED_INFLIGHT"

foundation_profile=foundation_pin.runtime_profile
ttl_ref=foundation_profile.semantic_payload["ttl_capture_placement_proof"]
assert ttl_ref == {"artifact_id": os.environ["TTL_ID"], "content_sha256": os.environ["TTL_SHA"]}
ttl=store.load_artifact(os.environ["TTL_ID"], os.environ["TTL_SHA"])
assert make_ttl_capture_placement_proof(ttl.semantic_payload) == ttl
tp=ttl.semantic_payload
assert tp["capture_distance_l3_hops"] == 0
assert tp["capture_topology_descriptor"]["mirror_position_relative_to_first_l3"] == "BEFORE_FIRST_L3"
assert tp["proof_valid_for_topology_identity"] == tp["capture_topology_identity"]

op=origin.semantic_payload
assert op["tcp_state"] == "ENABLED"
assert op["tcp_reason_code"] == "TTL_PROOF_VALID"
assert op["ttl_capture_placement_proof"] == ttl_ref

# Exact accepted Task-04 activation candidate.
rpm=store.load_artifact(os.environ["CLASS_RPM_ID"], os.environ["CLASS_RPM_SHA"])
crp=store.load_artifact(os.environ["CRP_ID"], os.environ["CRP_SHA"])
acceptance=store.load_artifact(os.environ["ACCEPTANCE_ID"])

rp=rpm.semantic_payload
assert rp["profile_kind"] == "classification"
assert rp["candidate_profile"] == {
    "artifact_id": os.environ["CRP_ID"],
    "content_sha256": os.environ["CRP_SHA"],
}
assert rp["update_class"] == "INITIAL_CLASSIFICATION"
assert rp["compatibility_validation_result"] == "PASS"
assert rp["previous_active_profile"] is None
assert rp["expected_previous_activation_record_id"] is None
assert rp["expected_previous_activation_generation_id"] is None
assert rp["task04_acceptance_manifest"]["artifact_id"] == acceptance.artifact_id
assert rp["foundation_runtime_profile_admission_manifest"]["artifact_id"] == os.environ["FOUNDATION_RPM_ID"]
assert crp.semantic_payload["foundation_runtime_profile"] == {
    "artifact_id": os.environ["FOUNDATION_PROFILE_ID"],
    "content_sha256": os.environ["FOUNDATION_PROFILE_SHA"],
}
assert store.get_active_pointer("classification") is None

with store._connect() as c:
    store._closure(c, crp)
    store._closure(c, rpm)

# Dormant derived store must still be pristine immediately before first activation.
c=sqlite3.connect(f"file:{class_db}?mode=ro", uri=True)
try:
    assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    counts={t:c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("artifacts","artifact_dependencies","classifications","classification_roots")}
    assert counts == {"artifacts":0,"artifact_dependencies":0,"classifications":0,"classification_roots":0}, counts
finally:
    c.close()

print("CONTROL_PLANE_QUICK_CHECK=PASS")
print("F_ADMIT_LINEAGE=PASS")
print("FOUNDATION_PIN_ACTIVE=PASS")
print("FOUNDATION_VALIDITY_ACTIVE=PASS")
print("TTL_PROOF_ID=PASS")
print(f"TTL_TOPOLOGY_IDENTITY={tp['capture_topology_identity']}")
print(f"TTL_MIRROR_SOURCE={tp['capture_topology_descriptor']['mirror_source_identity']}")
print(f"TTL_MIRROR_DESTINATION={tp['capture_topology_descriptor']['mirror_destination_identity']}")
print(f"TTL_FIRST_L3={tp['capture_topology_descriptor']['first_l3_gateway_identity']}")
print("TTL_DISTANCE_L3_HOPS=0")
print("ORIGIN_TCP_TTL_ADMISSION=PASS")
print("TASK04_ACCEPTANCE_ARTIFACT=PASS")
print("CLASSIFICATION_RPM_COMPATIBILITY=PASS")
print("CLASSIFICATION_RPM_INITIAL_PREDECESSOR=ABSENT")
print("CLASSIFICATION_CRP_CLOSURE=PASS")
print("CLASSIFICATION_RPM_CLOSURE=PASS")
print("CLASSIFICATION_POINTER_PRESTATE=ABSENT")
print("CLASSIFICATION_ACTIVATION_ROWS_PRESTATE=0")
print("CLASSIFICATION_DB_PRISTINE=PASS")
PY

step "LIVE CAPTURE TOPOLOGY / CONFIG"
[ -e /sys/class/net/enp8s0 ] || die "enp8s0 missing."
ip -details link show dev enp8s0
if ip -4 addr show dev enp8s0 | grep -q 'inet '; then
  die "enp8s0 unexpectedly has IPv4."
fi
ip -details link show dev enp8s0 | grep -Eq 'promiscuity[[:space:]]+1' || die "enp8s0 is not promiscuous."
echo "SPAN_INTERFACE_PRESENT_NO_IPV4_PROMISC=PASS"

cmp -s "$SURICATA_CONF" "$WT/deploy/device-fingerprint/suricata.yaml" || die "Live Suricata config differs from exact Git artifact."
cmp -s "$SURICATA_UNIT" "$WT/deploy/device-fingerprint/fingerprint-suricata.service" || die "Live Suricata unit differs from exact Git artifact."
grep -Fq 'interface: enp8s0' "$SURICATA_CONF" || die "Suricata interface mismatch."
grep -Fq 'bpf-filter: "net 192.168.8.0/22"' "$SURICATA_CONF" || die "Suricata BPF mismatch."
grep -Fq 'filetype: unix_dgram' "$SURICATA_CONF" || die "Suricata unix_dgram output missing."
grep -Fq 'filename: /run/captive-portal/fingerprint-sensor/suricata-eve.sock' "$SURICATA_CONF" || die "Suricata socket mismatch."
if grep -Fq 'filetype: regular' "$SURICATA_CONF" || grep -Fq 'diag-eve.json' "$SURICATA_CONF"; then
  die "Unsafe regular EVE output present."
fi
echo "SURICATA_EXACT_GIT_CONFIG=PASS"
echo "SURICATA_CAPTURE_SCOPE=PASS"

step "SENSOR SAFE ENV CONTRACT"
SENSOR_ENV="$SENSOR_ENV" /usr/bin/python3 - <<'PY'
import os
from pathlib import Path

expected={
 "DEVICE_FINGERPRINT_SENSOR_ENABLED":"true",
 "DEVICE_FINGERPRINT_SENSOR_INTERFACE":"enp8s0",
 "DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID":"sensor-zefer-01",
 "DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID":"zefer-span-01",
 "DEVICE_FINGERPRINT_SENSOR_SITE_ID":"6a64f17630da7c70d232187a",
 "DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS":"192.168.8.0/22",
 "DEVICE_FINGERPRINT_SENSOR_DHCP_SERVER_AUTHORITY":"192.168.10.1",
 "DEVICE_FINGERPRINT_SENSOR_DHCP_OPTION54_AUTHORITY":"192.168.10.1",
 "DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL":"https://192.168.0.202:9443",
}
vals={}
for raw in Path(os.environ["SENSOR_ENV"]).read_text(encoding="utf-8").splitlines():
    s=raw.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k,v=s.split("=",1)
    vals[k.strip()]=v.strip().strip('"').strip("'")
for k,v in expected.items():
    if vals.get(k)!=v:
        raise SystemExit(f"SENSOR_ENV_MISMATCH {k}: actual={vals.get(k)!r} expected={v!r}")
for k in expected:
    print(f"{k}=PASS")
print("SENSOR_SAFE_ENV_CONTRACT=PASS")
PY

step "LATEST SENSOR / EVIDENCE HEALTH"
LATEST_SENSOR="$(journalctl -u fingerprint-sensor.service -n 600 --no-pager | grep '"event":"fingerprint_sensor_metrics"' | tail -n 1 || true)"
[ -n "$LATEST_SENSOR" ] || die "No sensor metrics found."
echo "$LATEST_SENSOR"

LATEST_SENSOR="$LATEST_SENSOR" /usr/bin/python3 - <<'PY'
import json, os
line=os.environ["LATEST_SENSOR"]
obj=json.loads(line[line.index("{"):])
assert obj["runtime_state"]=="ready", obj
assert obj["suricata_process_active"] is True, obj
assert obj["eve_json_invalid"]==0, obj
assert obj["eve_datagram_truncated"]==0, obj
print(f"SENSOR_RUNTIME_STATE={obj['runtime_state']}")
print(f"SENSOR_SPOOL_ROWS={obj['spool_rows']}")
print(f"SENSOR_OLDEST_SPOOL_AGE={obj['oldest_spool_age']}")
print("SENSOR_LIVE_HEALTH=PASS")
PY

if journalctl -u fingerprint-evidence.service --since "20 minutes ago" --no-pager \
   | grep -Fq '"error_category":"concurrency_limit"'; then
  die "Recent evidence concurrency_limit observed."
fi
echo "EVIDENCE_RECENT_CONCURRENCY_LIMIT=NONE"

if [ -e /run/fingerprint-suricata/diag-eve.json ]; then
  die "diag-eve.json unexpectedly exists."
fi
echo "DIAG_EVE_PRESENT=NO"
df -h /run

step "READ-ONLY IMMUTABILITY PROOF"
CONTROL_SHA_AFTER="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
CLASS_SHA_AFTER="$(sha256sum "$CLASS_DB" | awk '{print $1}')"
echo "CONTROL_DB_SHA_AFTER=$CONTROL_SHA_AFTER"
echo "CLASS_DB_SHA_AFTER=$CLASS_SHA_AFTER"
[ "$CONTROL_SHA_BEFORE" = "$CONTROL_SHA_AFTER" ] || die "Control-plane DB changed during read-only gate."
[ "$CLASS_SHA_BEFORE" = "$CLASS_SHA_AFTER" ] || die "Classification DB changed during read-only gate."
echo "DATABASES_UNCHANGED=PASS"

PORTAL_PID_AFTER="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_AFTER="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_AFTER="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_AFTER="$(systemctl show fingerprint-suricata.service -p MainPID --value)"
[ "$PORTAL_PID_BEFORE" = "$PORTAL_PID_AFTER" ] || die "Portal restarted."
[ "$EVIDENCE_PID_BEFORE" = "$EVIDENCE_PID_AFTER" ] || die "Evidence restarted."
[ "$SENSOR_PID_BEFORE" = "$SENSOR_PID_AFTER" ] || die "Sensor restarted."
[ "$SURICATA_PID_BEFORE" = "$SURICATA_PID_AFTER" ] || die "Suricata restarted."
echo "SERVICE_PIDS_UNCHANGED=PASS"

step "FINAL"
echo "TASK04_PREACTIVATE_TECHNICAL_GATE=PASS"
echo "CURRENT_SAFETY_COMPATIBILITY_RECHECK=PASS_HOST_AND_CONTROL_PLANE"
echo "CLASSIFICATION_POINTER=ABSENT"
echo "CLASSIFICATION_ACTIVATION_ROWS=0"
echo "CLASSIFICATION_DB_PRISTINE=PASS"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "OWNER_PRODUCTION_ACTIVATION_DECISION=PENDING"
echo "OWNER_TOPOLOGY_NO_CHANGE_ASSERTION=PENDING"
echo "NOTE=Host/control-plane checks cannot independently read Catalyst SPAN configuration."
echo "REPORT=$REPORT"
