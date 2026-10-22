#!/usr/bin/env bash
set -Eeuo pipefail

TASK='TASK-DTI-NI-00-RESOURCE-CLOSURE-01'

BASE='/etc/captive-portal/device-fingerprint/suricata.yaml'
CAND='/home/admin/dti-ni00/suricata-dti-ni-v1.primary.yaml'
OUT='/run/fingerprint-suricata/dti-ni-v1.eve.json'
WORK='/home/admin/dti-ni00'
BACKUP="$WORK/suricata-baseline.resource-closure-01.authorized.yaml"

BASE_SHA='28609c533bbf97c09e58d175e2b9c24effa76ac98535e03665937a9c57c6e56f'
CAND_SHA='b9fc0262fe89b1d2155e5aa633e51f0941c4bd9ba6f33df607378a26e0628a53'

NIC='enp8s0'
BASELINE_SECONDS=300
WARMUP_SECONDS=60
CANDIDATE_SECONDS=300

MAX_OUTPUT_BYTES=134217728
MIN_FREE_BEFORE=671088640
MIN_FREE_DURING=536870912
HEALTH_STALE_SECONDS=150

ACTIVE=0
ROLLING_BACK=0
ROLLBACK_RESULT='NOT_NEEDED'
SENSOR_PID_INITIAL=''
SURICATA_PID_BASELINE=''
SURICATA_PID_CANDIDATE=''
BASE_OWNER=''
BASE_GROUP=''
BASE_MODE=''
OUT_DEV=''
OUT_INODE=''

sha() { sha256sum "$1" | awk '{print $1}'; }
svc_pid() { systemctl show "$1" -p MainPID --value; }
svc_restarts() { systemctl show "$1" -p NRestarts --value; }
run_total() { df -B1 --output=size /run | tail -n1 | tr -d ' '; }
run_avail() { df -B1 --output=avail /run | tail -n1 | tr -d ' '; }

out_any() {
  sudo -u suricata test -e "$OUT" || sudo -u suricata test -L "$OUT"
}
out_is_link() { sudo -u suricata test -L "$OUT"; }
out_is_regular() { sudo -u suricata test -f "$OUT" && ! out_is_link; }
out_size() {
  if out_is_regular; then
    sudo -u suricata stat -Lc %s "$OUT"
  else
    echo 0
  fi
}
out_lstat() {
  sudo -u suricata stat -c '%F|%s|%U|%G|%a|%d|%i|%Y|%y' "$OUT"
}

proc_cpu_ticks() {
  python3 - "$1" <<'PY'
import sys
pid=sys.argv[1]
s=open(f"/proc/{pid}/stat","r",encoding="utf-8").read()
r=s.rfind(")")
if r < 0:
    raise SystemExit(2)
tail=s[r+2:].split()
# tail begins with field 3 (state); utime=field14 => tail[11], stime=field15 => tail[12]
print(tail[11], tail[12])
PY
}

ticks_to_seconds() {
  awk -v t="$1" -v hz="$2" 'BEGIN{printf "%.6f", t/hz}'
}

ratio() {
  awk -v c="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.6f",c/w; else print "NA"}'
}
pps() {
  awk -v p="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.2f",p/w; else print "NA"}'
}
mbps() {
  awk -v b="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.6f",(b*8)/(w*1000000); else print "NA"}'
}
float_sub() {
  awk -v a="$1" -v b="$2" 'BEGIN{printf "%.6f",a-b}'
}
float_ratio() {
  awk -v a="$1" -v b="$2" 'BEGIN{if(b!=0)printf "%.6f",a/b; else print "NA"}'
}

usec_to_utc() {
  python3 - "$1" <<'PY'
import datetime,sys
u=int(sys.argv[1])
print(datetime.datetime.fromtimestamp(u/1_000_000,datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z"))
PY
}

latest_sensor_metric() {
  sudo journalctl -u fingerprint-sensor.service --since '-5 min' -o json --no-pager 2>/dev/null |
  python3 -c '
import json,sys
last=None
for line in sys.stdin:
    try:
        j=json.loads(line); m=json.loads(j.get("MESSAGE",""))
    except Exception:
        continue
    if m.get("event")=="fingerprint_sensor_metrics":
        last=(int(j.get("__REALTIME_TIMESTAMP",0)),m)
if last:
    u,m=last
    vals=[u,m.get("runtime_state"),m.get("eve_json_invalid"),m.get("eve_datagram_truncated"),
          m.get("tls_eve_count"),m.get("quic_eve_count"),m.get("suricata_process_active")]
    print("|".join("" if v is None else str(v) for v in vals))
'
}

latest_suricata_stat_after() {
  local min_usec="${1:-0}"
  sudo journalctl -u fingerprint-sensor.service --since '-10 min' -o json --no-pager 2>/dev/null |
  python3 -c '
import json,sys
minu=int(sys.argv[1]); last=None
for line in sys.stdin:
    try:
        j=json.loads(line); m=json.loads(j.get("MESSAGE",""))
    except Exception:
        continue
    u=int(j.get("__REALTIME_TIMESTAMP",0))
    if u < minu or m.get("event")!="fingerprint_suricata_stats":
        continue
    p=m.get("capture_kernel_packets"); d=m.get("capture_kernel_drops")
    if isinstance(p,(int,float)) and isinstance(d,(int,float)):
        last=(u,int(p),int(d))
if last: print("|".join(map(str,last)))
' "$min_usec"
}

closest_suricata_stat_at_ns() {
  local target_ns="$1"
  local min_usec="${2:-0}"
  local target_sec=$((target_ns/1000000000))
  local since=$((target_sec-30))
  [ "$since" -lt 0 ] && since=0
  sudo journalctl -u fingerprint-sensor.service --since "@$since" -o json --no-pager 2>/dev/null |
  python3 -c '
import json,sys
target_us=int(sys.argv[1])//1000
minu=int(sys.argv[2])
best=None
for line in sys.stdin:
    try:
        j=json.loads(line); m=json.loads(j.get("MESSAGE",""))
    except Exception:
        continue
    if m.get("event")!="fingerprint_suricata_stats":
        continue
    u=int(j.get("__REALTIME_TIMESTAMP",0))
    if u < minu or u > target_us:
        continue
    p=m.get("capture_kernel_packets"); d=m.get("capture_kernel_drops")
    if not isinstance(p,(int,float)) or not isinstance(d,(int,float)):
        continue
    dist=target_us-u
    if best is None or dist < best[0]:
        best=(dist,u,int(p),int(d))
if best:
    print(f"{best[1]}|{best[2]}|{best[3]}|{best[0]/1000000:.6f}")
' "$target_ns" "$min_usec"
}

json_field_from_pipe_metric() {
  local rec="$1" idx="$2"
  IFS='|' read -r f1 f2 f3 f4 f5 f6 f7 <<<"$rec"
  case "$idx" in
    usec) echo "$f1";;
    state) echo "$f2";;
    invalid) echo "$f3";;
    truncated) echo "$f4";;
    tls) echo "$f5";;
    quic) echo "$f6";;
    suricata_active) echo "$f7";;
  esac
}

wait_engine_ready() {
  local pid="$1" since_epoch="$2" label="$3"
  local deadline=$(( $(date +%s) + 30 ))
  local data=''
  while [ "$(date +%s)" -le "$deadline" ]; do
    data="$(
      sudo journalctl _PID="$pid" --since "@$since_epoch" -o json --no-pager 2>/dev/null |
      python3 -c '
import json,sys
first=None; ready=None
for line in sys.stdin:
    try:j=json.loads(line)
    except Exception:continue
    u=int(j.get("__REALTIME_TIMESTAMP",0)); msg=j.get("MESSAGE","")
    if first is None and ("Suricata version" in msg or "stream.reassembly.depth" in msg):
        first=u
    if "Engine started." in msg:
        ready=u
        break
if first and ready:
    print(f"{first}|{ready}|{(ready-first)/1000000:.6f}")
'
    )"
    if [ -n "$data" ]; then
      echo "$data" > "$WORK/.resource-closure-${label}-ready.tmp"
      return 0
    fi
    sleep 0.25
  done
  return 1
}

validate_complete_json() {
  sudo -u suricata python3 - "$OUT" <<'PY'
import json,sys
path=sys.argv[1]
bad=0; complete=0
with open(path,"rb") as f:
    data=f.read()
parts=data.split(b"\n")
if data and not data.endswith(b"\n"):
    parts=parts[:-1]
for raw in parts:
    if not raw: continue
    complete += 1
    try: json.loads(raw)
    except Exception: bad += 1
print(f"COMPLETE_JSON_RECORDS_CHECKED={complete}")
print(f"INVALID_COMPLETE_JSON_RECORDS={bad}")
raise SystemExit(0 if bad==0 else 2)
PY
}

check_service_identity() {
  local label="$1" expected_suricata_pid="$2"
  [ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo "STOP=${label}_SURICATA_INACTIVE"; return 1; }
  [ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo "STOP=${label}_SENSOR_INACTIVE"; return 1; }
  [ "$(svc_pid fingerprint-suricata.service)" = "$expected_suricata_pid" ] || { echo "STOP=${label}_SURICATA_PID_CHANGED"; return 1; }
  [ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_INITIAL" ] || { echo "STOP=${label}_SENSOR_PID_CHANGED"; return 1; }
  return 0
}

check_candidate_output_security() {
  if ! out_any; then
    echo 'STOP=CANDIDATE_LIVE_OUTPUT_ABSENT'
    return 1
  fi
  if out_is_link || ! out_is_regular; then
    echo 'STOP=CANDIDATE_OUTPUT_TYPE_OR_SYMLINK_MISMATCH'
    return 1
  fi
  local o g m d i md
  o="$(sudo -u suricata stat -Lc %U "$OUT")"
  g="$(sudo -u suricata stat -Lc %G "$OUT")"
  m="$(sudo -u suricata stat -Lc %a "$OUT")"
  d="$(sudo -u suricata stat -Lc %d "$OUT")"
  i="$(sudo -u suricata stat -Lc %i "$OUT")"
  md=$((8#$m))
  [ "$o" = suricata ] && [ "$g" = suricata ] && [ $((md & 022)) -eq 0 ] || {
    echo "STOP=CANDIDATE_OUTPUT_SECURITY_MISMATCH OWNER=$o GROUP=$g MODE=$m"
    return 1
  }
  if [ -n "$OUT_DEV" ] && { [ "$d" != "$OUT_DEV" ] || [ "$i" != "$OUT_INODE" ]; }; then
    echo "STOP=CANDIDATE_OUTPUT_FILE_IDENTITY_CHANGED DEV=$d INODE=$i"
    return 1
  fi
  return 0
}

check_candidate_storage() {
  local sz free
  sz="$(out_size)"
  free="$(run_avail)"
  [ "$sz" -lt "$MAX_OUTPUT_BYTES" ] || { echo "STOP=CANDIDATE_OUTPUT_LIMIT_REACHED BYTES=$sz"; return 1; }
  [ "$free" -ge "$MIN_FREE_DURING" ] || { echo 'STOP=RUN_RESERVED_CAPACITY_BREACHED'; return 1; }
  return 0
}

check_candidate_health() {
  local inv0="$1" trunc0="$2"
  local rec usec state inv trunc active now_us age
  rec="$(latest_sensor_metric)"
  [ -n "$rec" ] || { echo 'STOP=FINGERPRINT_HEALTH_PUBLICATION_MISSING'; return 1; }
  usec="$(json_field_from_pipe_metric "$rec" usec)"
  state="$(json_field_from_pipe_metric "$rec" state)"
  inv="$(json_field_from_pipe_metric "$rec" invalid)"; inv="${inv:-0}"
  trunc="$(json_field_from_pipe_metric "$rec" truncated)"; trunc="${trunc:-0}"
  active="$(json_field_from_pipe_metric "$rec" suricata_active)"
  now_us=$(( $(date +%s%N) / 1000 ))
  age=$(( (now_us-usec)/1000000 ))
  [ "$age" -le "$HEALTH_STALE_SECONDS" ] || { echo "STOP=FINGERPRINT_HEALTH_PUBLICATION_STALE AGE_SECONDS=$age"; return 1; }
  [ "$state" = ready ] || { echo "STOP=FINGERPRINT_RUNTIME_STATE_NOT_READY STATE=$state"; return 1; }
  [ "$active" = True ] || [ "$active" = true ] || { echo 'STOP=FINGERPRINT_SURICATA_PROCESS_NOT_ACTIVE'; return 1; }
  [ "$inv" -le "$inv0" ] || { echo 'STOP=FINGERPRINT_EVE_INVALID_REGRESSION'; return 1; }
  [ "$trunc" -le "$trunc0" ] || { echo 'STOP=FINGERPRINT_EVE_TRUNCATED_REGRESSION'; return 1; }
  return 0
}

# Generic exact-duration resource measurement. Baseline and candidate use the
# same CPU, MemoryCurrent, NIC and capture-boundary methods.
measure_window() {
  local prefix="$1" pid="$2" duration="$3" mode="$4" stat_min_usec="${5:-0}" inv0="${6:-0}" trunc0="${7:-0}"
  local hz u0 s0 u1 s1
  local mem0 memmid mem1 mempeak memcur
  local rxp0 rxb0 rxd0 rxe0 rxp1 rxb1 rxd1 rxe1
  local start_ns end_ns deadline_ns now_ns elapsed_sec next_sample=5 mid_done=0
  local start_iso end_iso
  local stat0 stat1 metric0 metric1
  local ss0='' sp0='' sd0='' sgap0='' ss1='' sp1='' sd1='' sgap1=''
  local last_stat='' last_stat_usec='' last_drop='' drop_streak=0
  local last_nicd last_nice nic_streak=0
  local next_json_check=30
  local output_peak=0 run_free_min=0 out_now=0 run_now=0

  hz="$(getconf CLK_TCK)"
  read -r u0 s0 <<<"$(proc_cpu_ticks "$pid")"
  mem0="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
  mempeak="$mem0"
  rxp0="$(cat "/sys/class/net/$NIC/statistics/rx_packets")"
  rxb0="$(cat "/sys/class/net/$NIC/statistics/rx_bytes")"
  rxd0="$(cat "/sys/class/net/$NIC/statistics/rx_dropped")"
  rxe0="$(cat "/sys/class/net/$NIC/statistics/rx_errors")"

  start_ns="$(date +%s%N)"
  deadline_ns=$((start_ns + duration*1000000000))
  start_iso="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  stat0="$(closest_suricata_stat_at_ns "$start_ns" "$stat_min_usec")"
  metric0="$(latest_sensor_metric)"

  echo "${prefix}_WINDOW_START_UTC=$start_iso"
  echo "${prefix}_PID=$pid"
  if [ -n "$stat0" ]; then
    IFS='|' read -r ss0 sp0 sd0 sgap0 <<<"$stat0"
    echo "${prefix}_CAPTURE_BOUNDARY_START_UTC=$(usec_to_utc "$ss0")"
    echo "${prefix}_CAPTURE_KERNEL_PACKETS_START=$sp0"
    echo "${prefix}_CAPTURE_KERNEL_DROPS_START=$sd0"
    echo "${prefix}_CAPTURE_START_BOUNDARY_LAG_SECONDS=$sgap0"
    last_stat_usec="$ss0"; last_drop="$sd0"
  else
    echo "${prefix}_CAPTURE_BOUNDARY_START=UNAVAILABLE"
  fi

  if [ -n "$metric0" ]; then
    echo "${prefix}_HEALTH_START_UTC=$(usec_to_utc "$(json_field_from_pipe_metric "$metric0" usec)")"
    echo "${prefix}_HEALTH_START_STATE=$(json_field_from_pipe_metric "$metric0" state)"
    echo "${prefix}_HEALTH_START_EVE_INVALID=$(json_field_from_pipe_metric "$metric0" invalid)"
    echo "${prefix}_HEALTH_START_EVE_TRUNCATED=$(json_field_from_pipe_metric "$metric0" truncated)"
    echo "${prefix}_TLS_COUNTER_START=$(json_field_from_pipe_metric "$metric0" tls)"
    echo "${prefix}_QUIC_COUNTER_START=$(json_field_from_pipe_metric "$metric0" quic)"
  fi

  last_nicd="$rxd0"; last_nice="$rxe0"
  if [ "$mode" = candidate ]; then
    output_peak="$(out_size)"
    run_free_min="$(run_avail)"
  fi

  while :; do
    now_ns="$(date +%s%N)"
    [ "$now_ns" -ge "$deadline_ns" ] && break
    elapsed_sec=$(( (now_ns-start_ns)/1000000000 ))

    if [ "$elapsed_sec" -ge "$next_sample" ]; then
      while [ "$next_sample" -le "$elapsed_sec" ]; do next_sample=$((next_sample+5)); done

      check_service_identity "$prefix" "$pid" || return 70

      memcur="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
      [ "$memcur" -gt "$mempeak" ] && mempeak="$memcur"
      if [ "$mid_done" -eq 0 ] && [ "$elapsed_sec" -ge $((duration/2)) ]; then
        memmid="$memcur"; mid_done=1
      fi

      if [ "$mode" = candidate ]; then
        check_candidate_output_security || return 71
        check_candidate_storage || return 72
        check_candidate_health "$inv0" "$trunc0" || return 73
        out_now="$(out_size)"; run_now="$(run_avail)"
        [ "$out_now" -gt "$output_peak" ] && output_peak="$out_now"
        [ "$run_now" -lt "$run_free_min" ] && run_free_min="$run_now"

        # Sustained capture-drop growth: two consecutive NEW stats intervals
        # with increasing kernel-drop counter.
        local st su sp sd
        st="$(latest_suricata_stat_after "$stat_min_usec")"
        if [ -n "$st" ]; then
          IFS='|' read -r su sp sd <<<"$st"
          if [ -n "$last_stat_usec" ] && [ "$su" != "$last_stat_usec" ]; then
            if [ "$sd" -gt "$last_drop" ]; then
              drop_streak=$((drop_streak+1))
            else
              drop_streak=0
            fi
            last_stat_usec="$su"; last_drop="$sd"
            if [ "$drop_streak" -ge 2 ]; then
              echo 'STOP=SUSTAINED_CAPTURE_KERNEL_DROP_GROWTH'
              return 74
            fi
          elif [ -z "$last_stat_usec" ]; then
            last_stat_usec="$su"; last_drop="$sd"
          fi
        fi

        # NIC safety: do not stop on one isolated counter movement; require
        # continued growth at a subsequent normal safety sample.
        local nd ne
        nd="$(cat "/sys/class/net/$NIC/statistics/rx_dropped")"
        ne="$(cat "/sys/class/net/$NIC/statistics/rx_errors")"
        if [ "$nd" -gt "$last_nicd" ] || [ "$ne" -gt "$last_nice" ]; then
          nic_streak=$((nic_streak+1))
        else
          nic_streak=0
        fi
        last_nicd="$nd"; last_nice="$ne"
        if [ "$nic_streak" -ge 2 ]; then
          echo 'STOP=SUSTAINED_NIC_DROP_ERROR_GROWTH'
          return 75
        fi

        if [ "$elapsed_sec" -ge "$next_json_check" ]; then
          while [ "$next_json_check" -le "$elapsed_sec" ]; do next_json_check=$((next_json_check+30)); done
          validate_complete_json || { echo 'STOP=MALFORMED_CANDIDATE_EVE_JSON'; return 76; }
        fi
      fi
    fi
    sleep 0.5
  done

  end_ns="$(date +%s%N)"
  end_iso="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  read -r u1 s1 <<<"$(proc_cpu_ticks "$pid")"
  mem1="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
  [ "$mem1" -gt "$mempeak" ] && mempeak="$mem1"
  [ "$mid_done" -eq 1 ] || memmid="$mem1"
  rxp1="$(cat "/sys/class/net/$NIC/statistics/rx_packets")"
  rxb1="$(cat "/sys/class/net/$NIC/statistics/rx_bytes")"
  rxd1="$(cat "/sys/class/net/$NIC/statistics/rx_dropped")"
  rxe1="$(cat "/sys/class/net/$NIC/statistics/rx_errors")"
  stat1="$(closest_suricata_stat_at_ns "$end_ns" "$stat_min_usec")"
  metric1="$(latest_sensor_metric)"

  local wall cpu_u0 cpu_s0 cpu_u1 cpu_s1 cpu_delta
  local pdelta bdelta ddelta edelta
  wall="$(awk -v a="$start_ns" -v b="$end_ns" 'BEGIN{printf "%.6f",(b-a)/1000000000}')"
  cpu_u0="$(ticks_to_seconds "$u0" "$hz")"; cpu_s0="$(ticks_to_seconds "$s0" "$hz")"
  cpu_u1="$(ticks_to_seconds "$u1" "$hz")"; cpu_s1="$(ticks_to_seconds "$s1" "$hz")"
  cpu_delta="$(awk -v u0="$u0" -v s0="$s0" -v u1="$u1" -v s1="$s1" -v hz="$hz" 'BEGIN{printf "%.6f",((u1+s1)-(u0+s0))/hz}')"
  pdelta=$((rxp1-rxp0)); bdelta=$((rxb1-rxb0)); ddelta=$((rxd1-rxd0)); edelta=$((rxe1-rxe0))

  echo "${prefix}_WINDOW_SECONDS=$duration"
  echo "${prefix}_WALL_SECONDS=$wall"
  echo "${prefix}_WINDOW_END_UTC=$end_iso"
  echo "${prefix}_CPU_USER_SECONDS_START=$cpu_u0"
  echo "${prefix}_CPU_SYSTEM_SECONDS_START=$cpu_s0"
  echo "${prefix}_CPU_USER_SECONDS_END=$cpu_u1"
  echo "${prefix}_CPU_SYSTEM_SECONDS_END=$cpu_s1"
  echo "${prefix}_CPU_DELTA_SECONDS=$cpu_delta"
  echo "${prefix}_CPU_RATIO=$(ratio "$cpu_delta" "$wall")"
  echo "${prefix}_MEMORY_BEFORE=$mem0"
  echo "${prefix}_MEMORY_MID=$memmid"
  echo "${prefix}_MEMORY_AFTER=$mem1"
  echo "${prefix}_MEMORY_PEAK_OBSERVED=$mempeak"
  echo "${prefix}_NIC_RX_PACKETS_DELTA=$pdelta"
  echo "${prefix}_NIC_RX_BYTES_DELTA=$bdelta"
  echo "${prefix}_NIC_RX_DROPPED_DELTA=$ddelta"
  echo "${prefix}_NIC_RX_ERRORS_DELTA=$edelta"
  echo "${prefix}_INPUT_PPS=$(pps "$pdelta" "$wall")"
  echo "${prefix}_INPUT_MBIT=$(mbps "$bdelta" "$wall")"

  if [ -n "$stat1" ]; then
    IFS='|' read -r ss1 sp1 sd1 sgap1 <<<"$stat1"
    echo "${prefix}_CAPTURE_BOUNDARY_END_UTC=$(usec_to_utc "$ss1")"
    echo "${prefix}_CAPTURE_KERNEL_PACKETS_END=$sp1"
    echo "${prefix}_CAPTURE_KERNEL_DROPS_END=$sd1"
    echo "${prefix}_CAPTURE_END_BOUNDARY_LAG_SECONDS=$sgap1"
    if [ -n "${sp0:-}" ]; then
      echo "${prefix}_CAPTURE_PACKET_DELTA=$((sp1-sp0))"
      echo "${prefix}_CAPTURE_DROP_DELTA=$((sd1-sd0))"
    else
      echo "${prefix}_CAPTURE_PACKET_DELTA=UNAVAILABLE"
      echo "${prefix}_CAPTURE_DROP_DELTA=UNAVAILABLE"
    fi
  else
    echo "${prefix}_CAPTURE_BOUNDARY_END=UNAVAILABLE"
    echo "${prefix}_CAPTURE_PACKET_DELTA=UNAVAILABLE"
    echo "${prefix}_CAPTURE_DROP_DELTA=UNAVAILABLE"
  fi

  if [ -n "$metric1" ]; then
    echo "${prefix}_HEALTH_END_UTC=$(usec_to_utc "$(json_field_from_pipe_metric "$metric1" usec)")"
    echo "${prefix}_HEALTH_END_STATE=$(json_field_from_pipe_metric "$metric1" state)"
    echo "${prefix}_HEALTH_END_EVE_INVALID=$(json_field_from_pipe_metric "$metric1" invalid)"
    echo "${prefix}_HEALTH_END_EVE_TRUNCATED=$(json_field_from_pipe_metric "$metric1" truncated)"
    echo "${prefix}_TLS_COUNTER_END=$(json_field_from_pipe_metric "$metric1" tls)"
    echo "${prefix}_QUIC_COUNTER_END=$(json_field_from_pipe_metric "$metric1" quic)"
  fi
  if [ "$mode" = candidate ]; then
    out_now="$(out_size)"; run_now="$(run_avail)"
    [ "$out_now" -gt "$output_peak" ] && output_peak="$out_now"
    [ "$run_now" -lt "$run_free_min" ] && run_free_min="$run_now"
    echo "${prefix}_OUTPUT_PEAK_BYTES=$output_peak"
    echo "${prefix}_RUN_AVAILABLE_MIN_BYTES=$run_free_min"
  fi
  return 0
}

rollback() {
  local reason="${1:-unspecified}"
  [ "$ACTIVE" -eq 1 ] || return 0
  [ "$ROLLING_BACK" -eq 0 ] || return 0
  ROLLING_BACK=1
  echo
  echo "=== ROLLBACK BEGIN reason=$reason ==="

  sudo install -o "$BASE_OWNER" -g "$BASE_GROUP" -m "$BASE_MODE" "$BACKUP" "$BASE"
  echo "ROLLBACK_BASE_SHA_AFTER_RESTORE=$(sha "$BASE")"

  set +e
  sudo timeout 60s /usr/bin/suricata -T -c "$BASE"
  local trc=$?
  set -e
  echo "ROLLBACK_BASE_SURICATA_T_EXIT_CODE=$trc"

  local rb_epoch rb_pid ready_file ready_metric='' deadline rb_ready_usec=0
  rb_epoch="$(date +%s)"
  sudo systemctl restart fingerprint-suricata.service
  rb_pid="$(svc_pid fingerprint-suricata.service)"
  echo "ROLLBACK_SURICATA_PID=$rb_pid"

  if wait_engine_ready "$rb_pid" "$rb_epoch" 'rollback'; then
    ready_file="$WORK/.resource-closure-rollback-ready.tmp"
    rb_ready_usec="$(cut -d'|' -f2 "$ready_file")"
    echo "ROLLBACK_ENGINE_READY=PASS"
    echo "ROLLBACK_PROCESS_START_UTC=$(usec_to_utc "$(cut -d'|' -f1 "$ready_file")")"
    echo "ROLLBACK_ENGINE_READY_UTC=$(usec_to_utc "$rb_ready_usec")"
    echo "ROLLBACK_STARTUP_SECONDS=$(cut -d'|' -f3 "$ready_file")"
  else
    echo 'ROLLBACK_ENGINE_READY=FAIL'
  fi

  echo "ROLLBACK_BASE_SHA_FINAL=$(sha "$BASE")"
  echo "ROLLBACK_SURICATA_STATE=$(systemctl is-active fingerprint-suricata.service || true)"
  echo "ROLLBACK_SENSOR_STATE=$(systemctl is-active fingerprint-sensor.service || true)"
  echo "ROLLBACK_SENSOR_PID=$(svc_pid fingerprint-sensor.service)"
  echo "ROLLBACK_SURICATA_NRESTARTS=$(svc_restarts fingerprint-suricata.service)"
  echo "ROLLBACK_SENSOR_NRESTARTS=$(svc_restarts fingerprint-sensor.service)"

  deadline=$(( $(date +%s)+90 ))
  while [ "$(date +%s)" -le "$deadline" ]; do
    ready_metric="$(latest_sensor_metric)"
    if [ -n "$ready_metric" ]; then
      local rm_usec
      rm_usec="$(json_field_from_pipe_metric "$ready_metric" usec)"
      if [ "$rm_usec" -ge "$rb_ready_usec" ] && [ "$(json_field_from_pipe_metric "$ready_metric" state)" = ready ]; then
        break
      fi
    fi
    ready_metric=''
    sleep 2
  done
  if [ -n "$ready_metric" ]; then
    echo "ROLLBACK_FINGERPRINT_RUNTIME_STATE=$(json_field_from_pipe_metric "$ready_metric" state)"
    echo "ROLLBACK_EVE_INVALID=$(json_field_from_pipe_metric "$ready_metric" invalid)"
    echo "ROLLBACK_EVE_TRUNCATED=$(json_field_from_pipe_metric "$ready_metric" truncated)"
  else
    echo 'ROLLBACK_FINGERPRINT_RUNTIME_STATE=UNAVAILABLE'
  fi

  local raw_removed='NO'
  if ! out_any; then
    raw_removed='YES'
  elif out_is_regular; then
    local d i o g m md
    d="$(sudo -u suricata stat -Lc %d "$OUT")"
    i="$(sudo -u suricata stat -Lc %i "$OUT")"
    o="$(sudo -u suricata stat -Lc %U "$OUT")"
    g="$(sudo -u suricata stat -Lc %G "$OUT")"
    m="$(sudo -u suricata stat -Lc %a "$OUT")"
    md=$((8#$m))
    echo "RAW_CANDIDATE_OUTPUT_CLEANUP_IDENTITY=DEV:$d INODE:$i OWNER:$o GROUP:$g MODE:$m"
    if [ "$o" = suricata ] && [ "$g" = suricata ] && [ $((md & 022)) -eq 0 ] && \
       { [ -z "$OUT_DEV" ] || { [ "$d" = "$OUT_DEV" ] && [ "$i" = "$OUT_INODE" ]; }; }; then
      sudo rm -- "$OUT"
      if ! out_any; then raw_removed='YES'; fi
    else
      echo 'RAW_CANDIDATE_OUTPUT_CLEANUP=HOLD_IDENTITY_OR_SECURITY_MISMATCH'
    fi
  else
    echo 'RAW_CANDIDATE_OUTPUT_CLEANUP=HOLD_UNEXPECTED_TYPE_OR_SYMLINK'
  fi
  echo "RAW_CANDIDATE_OUTPUT_REMOVED=$raw_removed"
  echo "RUN_TMPFS_AVAILABLE_AFTER_BYTES=$(run_avail)"

  local ok='YES'
  [ "$trc" -eq 0 ] || ok='NO'
  [ "$(sha "$BASE")" = "$BASE_SHA" ] || ok='NO'
  [ "$(systemctl is-active fingerprint-suricata.service)" = active ] || ok='NO'
  [ "$(systemctl is-active fingerprint-sensor.service)" = active ] || ok='NO'
  [ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_INITIAL" ] || ok='NO'
  [ -n "$ready_metric" ] && [ "$(json_field_from_pipe_metric "$ready_metric" state)" = ready ] || ok='NO'
  [ "$raw_removed" = YES ] || ok='NO'

  if [ "$ok" = YES ]; then
    ROLLBACK_RESULT='PASS'
    echo 'PRODUCTION_ROLLBACK=PASS'
  else
    ROLLBACK_RESULT='FAIL'
    echo 'PRODUCTION_ROLLBACK=FAIL'
  fi
  ACTIVE=0
  ROLLING_BACK=0
  echo '=== ROLLBACK END ==='
}

on_exit() {
  local rc=$?
  trap - EXIT INT TERM
  if [ "$ACTIVE" -eq 1 ]; then
    rollback "unexpected_exit_rc_$rc" || true
  fi
  rm -f "$WORK/.resource-closure-"*-ready.tmp 2>/dev/null || true
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT TERM

echo '============================================================'
echo "$TASK — AUTHORIZED RESOURCE-ONLY CLOSURE"
echo '============================================================'
echo "UTC_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'PURPOSE=CLOSE_ONLY_REMAINING_DTI_NI_00_RESOURCE_ADMISSION_GAP'
echo 'SEMANTIC_RESEARCH=RETAINED_FROM_RETRY_03_DO_NOT_REPEAT'
echo 'MEMORY_PEAK_SAMPLE_CADENCE_SECONDS=5'

sudo -v

echo
echo '=== PRE-FLIGHT: AUTHORITATIVE SHA + STALE OUTPUT BEFORE candidate -T ==='
OBS_BASE_SHA="$(sha "$BASE")"
OBS_CAND_SHA="$(sha "$CAND")"
echo "BASE_CONFIG_SHA256=$OBS_BASE_SHA"
echo "CANDIDATE_CONFIG_SHA256=$OBS_CAND_SHA"
[ "$OBS_BASE_SHA" = "$BASE_SHA" ] || { echo 'PREFLIGHT=FAIL_BASE_SHA'; exit 20; }
[ "$OBS_CAND_SHA" = "$CAND_SHA" ] || { echo 'PREFLIGHT=FAIL_CANDIDATE_SHA'; exit 21; }

if out_any; then
  echo 'PRE_T_OUTPUT_ABSENT=NO'
  out_lstat || true
  echo 'STOP=STALE_OUTPUT_PRESENT_BEFORE_CANDIDATE_T'
  exit 22
fi
echo 'PRE_T_OUTPUT_ABSENT=YES'

echo
echo '=== PRE-FLIGHT: candidate suricata -T + KNOWN TEST-MODE SIDE-EFFECT HANDLING ==='
T_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
T_START_EPOCH="$(date +%s)"
echo "CANDIDATE_T_START_UTC=$T_START_UTC"
set +e
sudo timeout 60s /usr/bin/suricata -T -c "$CAND"
TRC=$?
set -e
T_END_EPOCH="$(date +%s)"
T_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
echo "CANDIDATE_T_END_UTC=$T_END_UTC"
echo "CANDIDATE_SURICATA_T_EXIT_CODE=$TRC"
[ "$TRC" -eq 0 ] || { echo 'PREFLIGHT=FAIL_CANDIDATE_T'; exit 23; }

if out_any; then
  if out_is_link || ! out_is_regular; then
    echo 'POST_T_ARTIFACT_CLASSIFICATION=UNEXPECTED_TYPE_OR_SYMLINK'
    out_lstat || true
    echo 'STOP=POST_T_ARTIFACT_UNEXPECTED'
    exit 24
  fi
  IFS='|' read -r PT_TYPE PT_SIZE PT_OWNER PT_GROUP PT_MODE PT_DEV PT_INODE PT_MTIME_EPOCH PT_MTIME_TEXT <<<"$(out_lstat)"
  echo "POST_T_OUTPUT_TYPE=$PT_TYPE"
  echo "POST_T_OUTPUT_SIZE=$PT_SIZE"
  echo "POST_T_OUTPUT_OWNER=$PT_OWNER"
  echo "POST_T_OUTPUT_GROUP=$PT_GROUP"
  echo "POST_T_OUTPUT_MODE=$PT_MODE"
  echo "POST_T_OUTPUT_DEV=$PT_DEV"
  echo "POST_T_OUTPUT_INODE=$PT_INODE"
  echo "POST_T_OUTPUT_MTIME=$PT_MTIME_TEXT"
  PT_MODE_DEC=$((8#$PT_MODE))
  if [ "$PT_SIZE" != 0 ] || [ "$PT_OWNER" != root ] || [ "$PT_GROUP" != root ] || \
     [ $((PT_MODE_DEC & 022)) -ne 0 ] || \
     [ "$PT_MTIME_EPOCH" -lt $((T_START_EPOCH-1)) ] || [ "$PT_MTIME_EPOCH" -gt $((T_END_EPOCH+2)) ]; then
    echo 'POST_T_ARTIFACT_CLASSIFICATION=UNEXPECTED'
    echo 'STOP=POST_T_ARTIFACT_UNEXPECTED'
    exit 24
  fi
  echo 'POST_T_ARTIFACT_CLASSIFICATION=EXPECTED_ZERO_BYTE_TEST_SIDE_EFFECT'
  sudo rm -- "$OUT"
  out_any && { echo 'POST_T_ARTIFACT_REMOVED=NO'; exit 25; }
  echo 'POST_T_ARTIFACT_REMOVED=YES'
else
  echo 'POST_T_OUTPUT_PRESENT=NO'
  echo 'POST_T_ARTIFACT_CLASSIFICATION=NONE'
  echo 'POST_T_ARTIFACT_REMOVED=NOT_APPLICABLE'
fi

if out_any; then
  echo 'LIVE_START_OUTPUT_ABSENT=NO'
  exit 26
fi
echo 'LIVE_START_OUTPUT_ABSENT=YES'

RUN_TOTAL="$(run_total)"
RUN_BEFORE="$(run_avail)"
echo "RUN_TMPFS_TOTAL_BYTES=$RUN_TOTAL"
echo "RUN_TMPFS_AVAILABLE_BEFORE_BYTES=$RUN_BEFORE"
[ "$RUN_BEFORE" -ge "$MIN_FREE_BEFORE" ] || { echo 'STORAGE_PREFLIGHT=FAIL'; exit 27; }
echo 'STORAGE_PREFLIGHT=PASS'

[ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo 'PREFLIGHT=SURICATA_INACTIVE'; exit 28; }
[ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'PREFLIGHT=SENSOR_INACTIVE'; exit 29; }

SENSOR_PID_INITIAL="$(svc_pid fingerprint-sensor.service)"
SURICATA_PID_BASELINE="$(svc_pid fingerprint-suricata.service)"
BASE_OWNER="$(stat -Lc %U "$BASE")"
BASE_GROUP="$(stat -Lc %G "$BASE")"
BASE_MODE="$(stat -Lc %a "$BASE")"
echo "SENSOR_PID_INITIAL=$SENSOR_PID_INITIAL"
echo "BASELINE_PID=$SURICATA_PID_BASELINE"
echo "SENSOR_NRESTARTS_INITIAL=$(svc_restarts fingerprint-sensor.service)"
echo "SURICATA_NRESTARTS_INITIAL=$(svc_restarts fingerprint-suricata.service)"

sudo cp --preserve=mode,ownership,timestamps "$BASE" "$BACKUP"
[ "$(sha "$BACKUP")" = "$BASE_SHA" ] || { echo 'PREFLIGHT=BACKUP_SHA_FAIL'; exit 30; }

echo
echo '=== FRESH BASELINE RESOURCE WINDOW — 300s ==='
measure_window BASELINE "$SURICATA_PID_BASELINE" "$BASELINE_SECONDS" baseline 0 0 0

# Immediate pre-install safety/identity recheck.
echo
echo '=== PRE-INSTALL RECHECK ==='
[ "$(sha "$BASE")" = "$BASE_SHA" ] || { echo 'PREINSTALL=BASE_SHA_DRIFT'; exit 31; }
[ "$(sha "$CAND")" = "$CAND_SHA" ] || { echo 'PREINSTALL=CANDIDATE_SHA_DRIFT'; exit 32; }
[ "$(svc_pid fingerprint-suricata.service)" = "$SURICATA_PID_BASELINE" ] || { echo 'PREINSTALL=BASELINE_SURICATA_PID_CHANGED'; exit 33; }
[ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_INITIAL" ] || { echo 'PREINSTALL=SENSOR_PID_CHANGED'; exit 34; }
if out_any; then
  echo 'PREINSTALL=OUTPUT_REAPPEARED'
  out_lstat || true
  exit 35
fi
RUN_PREINSTALL="$(run_avail)"
echo "RUN_TMPFS_AVAILABLE_PREINSTALL_BYTES=$RUN_PREINSTALL"
[ "$RUN_PREINSTALL" -ge "$MIN_FREE_BEFORE" ] || { echo 'PREINSTALL=RUN_CAPACITY_FAIL'; exit 36; }

# Capture Fingerprint cumulative safety baselines immediately before candidate.
CAND_HEALTH_PRE="$(latest_sensor_metric)"
[ -n "$CAND_HEALTH_PRE" ] || { echo 'PREINSTALL=FINGERPRINT_METRICS_MISSING'; exit 37; }
CAND_INV0="$(json_field_from_pipe_metric "$CAND_HEALTH_PRE" invalid)"; CAND_INV0="${CAND_INV0:-0}"
CAND_TR0="$(json_field_from_pipe_metric "$CAND_HEALTH_PRE" truncated)"; CAND_TR0="${CAND_TR0:-0}"
echo "CANDIDATE_HEALTH_BASELINE_UTC=$(usec_to_utc "$(json_field_from_pipe_metric "$CAND_HEALTH_PRE" usec)")"
echo "CANDIDATE_HEALTH_BASELINE_STATE=$(json_field_from_pipe_metric "$CAND_HEALTH_PRE" state)"
echo "CANDIDATE_HEALTH_BASELINE_EVE_INVALID=$CAND_INV0"
echo "CANDIDATE_HEALTH_BASELINE_EVE_TRUNCATED=$CAND_TR0"

echo
echo '=== CANDIDATE ACTIVATION ==='
sudo install -o "$BASE_OWNER" -g "$BASE_GROUP" -m "$BASE_MODE" "$CAND" "$BASE"
ACTIVE=1
INSTALLED_SHA="$(sha "$BASE")"
echo "INSTALLED_CANDIDATE_SHA256=$INSTALLED_SHA"
[ "$INSTALLED_SHA" = "$CAND_SHA" ] || { echo 'CANDIDATE_INSTALL=SHA_FAIL'; exit 40; }

CAND_RESTART_EPOCH="$(date +%s)"
sudo systemctl restart fingerprint-suricata.service
SURICATA_PID_CANDIDATE="$(svc_pid fingerprint-suricata.service)"
echo "CANDIDATE_PID=$SURICATA_PID_CANDIDATE"
[ "$SURICATA_PID_CANDIDATE" != "$SURICATA_PID_BASELINE" ] || { echo 'CANDIDATE_STARTUP=PID_DID_NOT_CHANGE'; exit 41; }
[ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_INITIAL" ] || { echo 'CANDIDATE_STARTUP=SENSOR_PID_CHANGED'; exit 42; }

if ! wait_engine_ready "$SURICATA_PID_CANDIDATE" "$CAND_RESTART_EPOCH" 'candidate'; then
  echo 'STOP=CANDIDATE_ENGINE_READY_TIMEOUT'
  sudo journalctl _PID="$SURICATA_PID_CANDIDATE" --since "@$((CAND_RESTART_EPOCH-2))" --no-pager -n 100 || true
  exit 43
fi
CAND_READY_FILE="$WORK/.resource-closure-candidate-ready.tmp"
CAND_START_USEC="$(cut -d'|' -f1 "$CAND_READY_FILE")"
CAND_READY_USEC="$(cut -d'|' -f2 "$CAND_READY_FILE")"
CAND_STARTUP_SECONDS="$(cut -d'|' -f3 "$CAND_READY_FILE")"
echo "CANDIDATE_PROCESS_START_UTC=$(usec_to_utc "$CAND_START_USEC")"
echo "CANDIDATE_ENGINE_READY_UTC=$(usec_to_utc "$CAND_READY_USEC")"
echo "CANDIDATE_STARTUP_SECONDS=$CAND_STARTUP_SECONDS"

echo
echo '=== LIVE OUTPUT GATE ==='
# Give the regular logger a short bounded chance to materialize after engine-ready.
OUT_DEADLINE=$(( $(date +%s)+10 ))
while ! out_any && [ "$(date +%s)" -le "$OUT_DEADLINE" ]; do sleep 0.25; done
if ! out_any; then
  echo 'STOP=CANDIDATE_LIVE_OUTPUT_ABSENT'
  exit 44
fi
check_candidate_output_security || exit 45
OUT_OWNER="$(sudo -u suricata stat -Lc %U "$OUT")"
OUT_GROUP="$(sudo -u suricata stat -Lc %G "$OUT")"
OUT_MODE="$(sudo -u suricata stat -Lc %a "$OUT")"
OUT_DEV="$(sudo -u suricata stat -Lc %d "$OUT")"
OUT_INODE="$(sudo -u suricata stat -Lc %i "$OUT")"
OUT_INITIAL_SIZE="$(sudo -u suricata stat -Lc %s "$OUT")"
echo "LIVE_OUTPUT_OWNER=$OUT_OWNER"
echo "LIVE_OUTPUT_GROUP=$OUT_GROUP"
echo "LIVE_OUTPUT_MODE=$OUT_MODE"
echo "LIVE_OUTPUT_DEV=$OUT_DEV"
echo "LIVE_OUTPUT_INODE=$OUT_INODE"
echo "LIVE_OUTPUT_INITIAL_SIZE=$OUT_INITIAL_SIZE"

echo
echo '=== CANDIDATE WARM-UP — 60s ==='
# Warm-up uses the same safety machinery but does not repeat semantic research.
measure_window WARMUP "$SURICATA_PID_CANDIDATE" "$WARMUP_SECONDS" candidate "$CAND_READY_USEC" "$CAND_INV0" "$CAND_TR0"
echo "CANDIDATE_OUTPUT_BYTES_AFTER_WARMUP=$(out_size)"
echo "RUN_TMPFS_AVAILABLE_AFTER_WARMUP_BYTES=$(run_avail)"

echo
echo '=== CANDIDATE RESOURCE WINDOW — 300s ==='
measure_window CANDIDATE "$SURICATA_PID_CANDIDATE" "$CANDIDATE_SECONDS" candidate "$CAND_READY_USEC" "$CAND_INV0" "$CAND_TR0"
echo "CANDIDATE_OUTPUT_BYTES_FINAL=$(out_size)"
echo "RUN_TMPFS_AVAILABLE_CANDIDATE_END_BYTES=$(run_avail)"

# Derived raw comparison aids. Final COMPARABLE/QUALIFIED adjudication is left
# to the report analysis because the Tech Lead did not define a numeric
# "material workload difference" threshold.
echo
echo '=== RAW RESOURCE COMPARISON AIDS ==='
# Values are recovered from the console output by the final report step.
echo 'RESOURCE_COMPARISON_CLASSIFICATION=PENDING_TECH_LEAD_INTERPRETATION_OF_RAW_INPUT_LOAD'
echo 'NO_ARBITRARY_MATERIALITY_THRESHOLD_APPLIED=YES'

rollback 'normal_completion'

echo
echo '=== COLLECTION STATUS ==='
echo "TASK=$TASK"
echo "BASE_CONFIG_SHA256=$BASE_SHA"
echo "CANDIDATE_CONFIG_SHA256=$CAND_SHA"
echo "BASELINE_WINDOW_SECONDS=$BASELINE_SECONDS"
echo "CANDIDATE_WARMUP_SECONDS=$WARMUP_SECONDS"
echo "CANDIDATE_WINDOW_SECONDS=$CANDIDATE_SECONDS"
echo "PRODUCTION_ROLLBACK=$ROLLBACK_RESULT"
echo "UTC_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'RESOURCE_CLOSURE_COLLECTION_COMPLETE'
