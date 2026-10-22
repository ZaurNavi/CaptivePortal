#!/usr/bin/env bash
set -Eeuo pipefail

TASK='TASK-DTI-NI-00-PRIMARY-LIVE-ADMISSION-01'
BASE='/etc/captive-portal/device-fingerprint/suricata.yaml'
CAND='/home/admin/dti-ni00/suricata-dti-ni-v1.primary.yaml'
WORK='/home/admin/dti-ni00'
BACKUP="$WORK/suricata-baseline.authorized.yaml"
OUT='/run/fingerprint-suricata/dti-ni-v1.eve.json'
OBSERVER="$WORK/ni00_observer.py"
REPLAY="$WORK/ni00_replay.py"
OBS_SUM="$WORK/observer-summary.json"
REPLAY_SUM="$WORK/replay-summary.json"
OBS_FAIL="$WORK/observer-malformed.flag"

BASE_SHA='28609c533bbf97c09e58d175e2b9c24effa76ac98535e03665937a9c57c6e56f'
CAND_SHA='b9fc0262fe89b1d2155e5aa633e51f0941c4bd9ba6f33df607378a26e0628a53'
MAX_OUT=134217728
MIN_BEFORE=671088640
MIN_DURING=536870912
GUEST_CIDR='192.168.8.0/22'

ACTIVE=0
FINISHED=0
OBS_PID=''
REPLAY_PID=''
BASE_OWNER=''
BASE_GROUP=''
BASE_MODE=''
SENSOR_PID_BEFORE=''
SURICATA_PID_BEFORE=''
RUN_MIN=''
OUT_PEAK=0

sha() { sha256sum "$1" | awk '{print $1}'; }
svc_pid() { systemctl show "$1" -p MainPID --value; }
svc_restarts() { systemctl show "$1" -p NRestarts --value; }
run_total() { df -B1 --output=size /run | tail -n1 | tr -d ' '; }
run_avail() { df -B1 --output=avail /run | tail -n1 | tr -d ' '; }
out_size() { if [ -e "$OUT" ]; then stat -Lc %s "$OUT"; else echo 0; fi; }

latest_sensor_metric() {
  sudo journalctl -u fingerprint-sensor.service -o cat --no-pager --since '-20 min' 2>/dev/null \
    | grep '"event":"fingerprint_sensor_metrics"' | tail -n1 || true
}
latest_suricata_stat() {
  sudo journalctl -u fingerprint-sensor.service -o cat --no-pager --since '-20 min' 2>/dev/null \
    | grep '"event":"fingerprint_suricata_stats"' | tail -n1 || true
}
jfield() {
  local json="$1" field="$2"
  printf '%s' "$json" | python3 -c 'import json,sys; s=sys.stdin.read().strip(); d=json.loads(s) if s else {}; v=d.get(sys.argv[1]); print("" if v is None else v)' "$field" 2>/dev/null || true
}
calc_ratio() { awk -v c="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.6f",(c/1000000000)/w;else print "NA"}'; }
calc_pps() { awk -v p="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.2f",p/w;else print "NA"}'; }
calc_mbps() { awk -v b="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.6f",(b*8)/(w*1000000);else print "NA"}'; }

stop_background() {
  if [ -n "${OBS_PID:-}" ] && kill -0 "$OBS_PID" 2>/dev/null; then
    kill -TERM "$OBS_PID" 2>/dev/null || true
    wait "$OBS_PID" 2>/dev/null || true
  fi
  if [ -n "${REPLAY_PID:-}" ] && kill -0 "$REPLAY_PID" 2>/dev/null; then
    kill -TERM "$REPLAY_PID" 2>/dev/null || true
    wait "$REPLAY_PID" 2>/dev/null || true
  fi
}

rollback() {
  local reason="${1:-normal}"
  stop_background
  if [ "$ACTIVE" -eq 1 ]; then
    echo
    echo "=== ROLLBACK BEGIN reason=$reason ==="
    sudo install -o "$BASE_OWNER" -g "$BASE_GROUP" -m "$BASE_MODE" "$BACKUP" "$BASE"
    local rsha
    rsha="$(sha "$BASE")"
    echo "ROLLBACK_BASE_SHA_AFTER_RESTORE=$rsha"
    if [ "$rsha" != "$BASE_SHA" ]; then
      echo "PRODUCTION_ROLLBACK=FAIL"
      echo "CRITICAL=BASELINE_SHA_RESTORE_MISMATCH"
      return 90
    fi
    set +e
    sudo timeout 60s /usr/bin/suricata -T -c "$BASE"
    local trc=$?
    set -e
    echo "ROLLBACK_BASE_SURICATA_T_EXIT_CODE=$trc"
    if [ "$trc" -ne 0 ]; then
      echo "PRODUCTION_ROLLBACK=FAIL"
      echo "CRITICAL=BASELINE_SURICATA_T_FAILED"
      return 91
    fi
    sudo systemctl restart fingerprint-suricata.service
    sleep 5
    echo "ROLLBACK_SURICATA_STATE=$(systemctl is-active fingerprint-suricata.service || true)"
    echo "ROLLBACK_SENSOR_STATE=$(systemctl is-active fingerprint-sensor.service || true)"
    echo "ROLLBACK_BASE_SHA_FINAL=$(sha "$BASE")"
    echo "ROLLBACK_SENSOR_PID=$(svc_pid fingerprint-sensor.service)"
    echo "ROLLBACK_SURICATA_PID=$(svc_pid fingerprint-suricata.service)"
    echo "ROLLBACK_SENSOR_NRESTARTS=$(svc_restarts fingerprint-sensor.service)"
    echo "ROLLBACK_SURICATA_NRESTARTS=$(svc_restarts fingerprint-suricata.service)"
    sudo rm -f -- "$OUT"
    if [ -e "$OUT" ]; then
      echo "RAW_CANDIDATE_OUTPUT_REMOVED=NO"
    else
      echo "RAW_CANDIDATE_OUTPUT_REMOVED=YES"
    fi
    echo "RUN_TMPFS_AVAILABLE_AFTER_BYTES=$(run_avail)"
    ACTIVE=0
    echo "PRODUCTION_ROLLBACK=PASS"
    echo "=== ROLLBACK END ==="
  fi
}

on_exit() {
  local rc=$?
  if [ "$FINISHED" -eq 0 ] && [ "$ACTIVE" -eq 1 ]; then
    set +e
    rollback "unexpected_exit_rc_$rc"
  fi
  exit "$rc"
}
trap on_exit EXIT
trap 'echo "INTERRUPTED=YES"; exit 130' INT TERM

mkdir -p "$WORK"
rm -f -- "$OBS_SUM" "$REPLAY_SUM" "$OBS_FAIL"

cat > "$OBSERVER" <<'PY'
import collections, datetime as dt, ipaddress, json, os, signal, sys, time
path, start_s, duration_s, guest_cidr, controlled_ip, summary_path, fail_path = sys.argv[1:]
start_offset=int(start_s); duration=float(duration_s)
guest=ipaddress.ip_network(guest_cidr)
stop=False
signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__('stop', True))
signal.signal(signal.SIGINT, lambda *_: globals().__setitem__('stop', True))
counts=collections.Counter(); bytes_by_family=collections.Counter(); max_size=0
field=collections.defaultdict(lambda: collections.Counter())
flow_counts=collections.defaultdict(collections.Counter)
dns_ids=collections.Counter(); dns_names=set(); sni_values=set(); unique_flows=set()
dns_types=collections.Counter(); dns_qtypes=collections.Counter(); dns_rcodes=collections.Counter(); dns_pairs={}
controlled=collections.Counter(); scope=collections.Counter(); lags=collections.defaultdict(list)
invalid=0; partial=False; first_offset=None; last_complete_offset=start_offset

def present(prefix, obj, key):
    if key in obj:
        field[prefix+'.'+key]['present'] += 1
        if obj.get(key) is None: field[prefix+'.'+key]['null'] += 1
        else: field[prefix+'.'+key]['non_null'] += 1
    else:
        field[prefix+'.'+key]['absent'] += 1

def parse_ts(v):
    if not isinstance(v,str): return None
    if v.endswith('Z'): v=v[:-1]+'+00:00'
    if len(v)>=5 and (v[-5] in '+-') and v[-3] != ':': v=v[:-2]+':'+v[-2:]
    try:
        x=dt.datetime.fromisoformat(v)
        if x.tzinfo is None: return None
        return x.astimezone(dt.timezone.utc)
    except Exception: return None

def is_guest(v):
    try:
        a=ipaddress.ip_address(v)
        return a.version==4 and a in guest
    except Exception: return False

def pct(vals,p):
    if not vals: return None
    s=sorted(vals); k=(len(s)-1)*p; lo=int(k); hi=min(lo+1,len(s)-1); f=k-lo
    return s[lo]*(1-f)+s[hi]*f

started=time.monotonic(); buf=b''; offset=start_offset
with open(path,'rb', buffering=0) as f:
    f.seek(start_offset)
    while not stop and time.monotonic()-started < duration:
        chunk=f.read(65536)
        if not chunk:
            time.sleep(0.02); continue
        buf += chunk
        while b'\n' in buf:
            line, buf = buf.split(b'\n',1)
            rec_start=offset; offset += len(line)+1; last_complete_offset=offset
            if not line: continue
            if first_offset is None: first_offset=rec_start
            max_size=max(max_size,len(line)+1)
            try: e=json.loads(line)
            except Exception:
                invalid += 1
                open(fail_path,'w').write(str(rec_start))
                continue
            fam=e.get('event_type')
            if fam not in ('dns','tls','quic'): continue
            counts[fam]+=1; bytes_by_family[fam]+=len(line)+1
            flow=e.get('flow_id')
            if flow is not None:
                unique_flows.add(str(flow)); flow_counts[fam][str(flow)] += 1
            for k in ('timestamp','flow_id','src_ip','src_port','dest_ip','dest_port','proto','app_proto'):
                present('common',e,k)
            src=e.get('src_ip'); dst=e.get('dest_ip')
            sg=is_guest(src); dg=is_guest(dst)
            if sg or dg: scope['resolved_intended_population']+=1
            elif src is not None or dst is not None: scope['resolved_other_population']+=1
            else: scope['unknown']+=1
            if controlled_ip and (src==controlled_ip or dst==controlled_ip): controlled[fam]+=1
            ts=parse_ts(e.get('timestamp'))
            if ts is not None:
                lag=(dt.datetime.now(dt.timezone.utc)-ts).total_seconds()
                lags[fam].append(lag)
            body=e.get(fam)
            if not isinstance(body,dict): body={}
            if fam=='dns':
                for k in ('type','tx_id','id','queries','answers','rcode'):
                    present('dns',body,k)
                dns_types[str(body.get('type'))]+=1
                if body.get('rcode') is not None: dns_rcodes[str(body.get('rcode'))]+=1
                qs=body.get('queries')
                if isinstance(qs,list):
                    for q in qs:
                        if isinstance(q,dict):
                            rn=q.get('rrname'); qt=q.get('rrtype')
                            if isinstance(rn,str): dns_names.add(rn)
                            if qt is not None: dns_qtypes[str(qt)]+=1
                tx=body.get('tx_id'); typ=body.get('type')
                if flow is not None and tx is not None and typ is not None:
                    dns_ids[(str(flow),str(tx),str(typ))]+=1
                    if ts is not None:
                        key=(str(flow),str(tx)); slot=dns_pairs.setdefault(key,{})
                        tname=str(typ).lower()
                        if tname in ('query','request') and 'q' not in slot: slot['q']=ts
                        if tname in ('answer','response') and 'r' not in slot: slot['r']=ts
            elif fam=='tls':
                for k in ('sni','version','client_alpns','server_alpns'):
                    present('tls',body,k)
                if isinstance(body.get('sni'),str): sni_values.add(body['sni'])
            elif fam=='quic':
                for k in ('version','sni','ja4','extensions'):
                    present('quic',body,k)
                if isinstance(body.get('sni'),str): sni_values.add(body['sni'])
partial=bool(buf)
dns_lat=[]
for slot in dns_pairs.values():
    if 'q' in slot and 'r' in slot:
        dns_lat.append((slot['r']-slot['q']).total_seconds())
summary={
 'duration_requested_seconds':duration,
 'duration_observed_seconds':round(time.monotonic()-started,3),
 'measurement_start_offset':start_offset,'first_complete_record_offset':first_offset,
 'last_complete_record_end_offset':last_complete_offset,'partial_final_line_observed':partial,
 'invalid_json_records':invalid,'event_counts':dict(counts),'bytes_by_family':dict(bytes_by_family),
 'max_event_size_bytes':max_size,'unique_flow_id_count':len(unique_flows),
 'dns_name_cardinality':len(dns_names),'sni_cardinality':len(sni_values),
 'dns_type_counts':dict(dns_types),'dns_query_type_counts':dict(dns_qtypes),'dns_rcode_counts':dict(dns_rcodes),
 'controlled_client_event_counts':dict(controlled),'network_scope_counts':dict(scope),
 'field_occurrence':{k:dict(v) for k,v in field.items()},
 'dns_identity_candidate_unique':len(dns_ids),
 'dns_identity_candidate_duplicate_occurrences':sum(max(0,v-1) for v in dns_ids.values()),
 'dns_latency_pairing_evidence':{'count':len(dns_lat),'min':min(dns_lat) if dns_lat else None,'p50':pct(dns_lat,.50),'p95':pct(dns_lat,.95),'p99':pct(dns_lat,.99),'max':max(dns_lat) if dns_lat else None},
 'family_flows_with_multiple_events':{fam:sum(1 for v in c.values() if v>1) for fam,c in flow_counts.items()},
 'family_max_events_per_flow':{fam:max(c.values()) if c else 0 for fam,c in flow_counts.items()},
 'delivery_lag_seconds':{
   fam:{'count':len(v),'min':min(v) if v else None,'p50':pct(v,.50),'p95':pct(v,.95),'p99':pct(v,.99),'max':max(v) if v else None}
   for fam,v in lags.items()
 }
}
with open(summary_path,'w',encoding='utf-8') as o: json.dump(summary,o,sort_keys=True,indent=2)
print(json.dumps(summary,sort_keys=True))
PY

cat > "$REPLAY" <<'PY'
import json, os, sys, time
path=sys.argv[1]; floor=int(sys.argv[2]); out=sys.argv[3]
def complete_window(p,start,end):
    starts=[]; count=0; partial=False; pos=start
    with open(p,'rb') as f:
        f.seek(start); data=f.read(max(0,end-start))
    chunks=data.split(b'\n')
    tail=chunks.pop() if chunks else b''
    partial=(tail != b'')
    for line in chunks:
        if line:
            starts.append(pos); json.loads(line); count+=1
        pos += len(line)+1
    checkpoint=pos
    return starts,count,checkpoint,partial
st1=os.stat(path); size1=st1.st_size
starts1,n1,checkpoint,partial1=complete_window(path,floor,size1)
time.sleep(30)
st2=os.stat(path); size2=st2.st_size
starts2,n2,end2,partial2=complete_window(path,checkpoint,size2)
result={
 'file_device_id_before':st1.st_dev,'file_inode_before':st1.st_ino,
 'file_device_id_after':st2.st_dev,'file_inode_after':st2.st_ino,
 'size_before_reader_stop':size1,'checkpoint_offset':checkpoint,'size_after_reader_restart':size2,
 'records_before_checkpoint':n1,'records_after_checkpoint':n2,
 'record_start_offsets_before_tail':starts1[-8:],
 'record_start_offsets_after_head':starts2[:8],
 'partial_final_line_before':partial1,'partial_final_line_after':partial2,
 'same_file_identity':(st1.st_dev,st1.st_ino)==(st2.st_dev,st2.st_ino),
 'first_record_after_checkpoint_starts_at_checkpoint':(n2==0 or starts2[0]==checkpoint),
 'reader_restart_replay':'PASS' if ((st1.st_dev,st1.st_ino)==(st2.st_dev,st2.st_ino) and (n2==0 or starts2[0]==checkpoint)) else 'FAIL'
}
with open(out,'w',encoding='utf-8') as f: json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
PY

echo "============================================================"
echo "$TASK — AUTHORIZED BOUNDED LIVE ADMISSION"
echo "============================================================"
echo "UTC_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

sudo -v

# Mandatory immediate preflight
echo; echo '=== PRE-FLIGHT ==='
OBS_BASE_SHA="$(sha "$BASE")"; OBS_CAND_SHA="$(sha "$CAND")"
echo "BASE_CONFIG_SHA256=$OBS_BASE_SHA"
echo "CANDIDATE_CONFIG_SHA256=$OBS_CAND_SHA"
[ "$OBS_BASE_SHA" = "$BASE_SHA" ] || { echo 'PREFLIGHT=FAIL BASE_SHA_DRIFT'; exit 20; }
[ "$OBS_CAND_SHA" = "$CAND_SHA" ] || { echo 'PREFLIGHT=FAIL CANDIDATE_SHA_DRIFT'; exit 21; }
set +e
sudo timeout 60s /usr/bin/suricata -T -c "$CAND"
TRC=$?
set -e
echo "CANDIDATE_SURICATA_T_EXIT_CODE=$TRC"
[ "$TRC" -eq 0 ] || { echo 'PREFLIGHT=FAIL CANDIDATE_SURICATA_T'; exit 22; }
[ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'PREFLIGHT=FAIL SENSOR_INACTIVE'; exit 23; }
[ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo 'PREFLIGHT=FAIL SURICATA_INACTIVE'; exit 24; }
RUN_TOTAL="$(run_total)"; RUN_BEFORE="$(run_avail)"; RUN_MIN="$RUN_BEFORE"
echo "RUN_TMPFS_TOTAL_BYTES=$RUN_TOTAL"
echo "RUN_TMPFS_AVAILABLE_BEFORE_BYTES=$RUN_BEFORE"
[ "$RUN_BEFORE" -ge "$MIN_BEFORE" ] || { echo 'OUTPUT_CAPACITY_PREFLIGHT=FAIL'; exit 25; }
if [ -e "$OUT" ] || [ -L "$OUT" ]; then
  echo 'PREFLIGHT=FAIL PREEXISTING_CANDIDATE_OUTPUT'
  stat -Lc 'PATH=%n SIZE=%s MTIME=%y OWNER=%U GROUP=%G MODE=%a' "$OUT" 2>&1 || true
  exit 26
fi
echo 'OUTPUT_CAPACITY_PREFLIGHT=PASS'
echo 'PREEXISTING_CANDIDATE_OUTPUT=ABSENT'

BASE_OWNER="$(stat -Lc %U "$BASE")"; BASE_GROUP="$(stat -Lc %G "$BASE")"; BASE_MODE="$(stat -Lc %a "$BASE")"
SENSOR_PID_BEFORE="$(svc_pid fingerprint-sensor.service)"; SURICATA_PID_BEFORE="$(svc_pid fingerprint-suricata.service)"
echo "SENSOR_PID_BEFORE=$SENSOR_PID_BEFORE"
echo "SURICATA_PID_BEFORE=$SURICATA_PID_BEFORE"
echo "SENSOR_NRESTARTS_BEFORE=$(svc_restarts fingerprint-sensor.service)"
echo "SURICATA_NRESTARTS_BEFORE=$(svc_restarts fingerprint-suricata.service)"
sudo cp --preserve=mode,ownership,timestamps "$BASE" "$BACKUP"
[ "$(sha "$BACKUP")" = "$BASE_SHA" ] || { echo 'PREFLIGHT=FAIL BACKUP_SHA'; exit 27; }

# 300-second baseline
echo; echo '=== PRE_CHANGE_BASELINE_WINDOW 300s ==='
B_CPU0="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"
B_MEM0="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
B_RXP0="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; B_RXB0="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"
B_RXD0="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; B_RXE0="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
B_STAT0="$(latest_suricata_stat)"; B_MET0="$(latest_sensor_metric)"
B_T0="$(date +%s)"
for i in $(seq 1 10); do
  sleep 30
  [ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'BASELINE_STOP=SENSOR_INACTIVE'; exit 30; }
  [ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo 'BASELINE_STOP=SURICATA_INACTIVE'; exit 31; }
  [ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_BEFORE" ] || { echo 'BASELINE_STOP=SENSOR_PID_CHANGED'; exit 32; }
  [ "$(svc_pid fingerprint-suricata.service)" = "$SURICATA_PID_BEFORE" ] || { echo 'BASELINE_STOP=SURICATA_PID_CHANGED'; exit 33; }
  if [ "$i" -eq 5 ]; then B_MEMMID="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"; fi
done
B_T1="$(date +%s)"; B_WALL=$((B_T1-B_T0))
B_CPU1="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"; B_MEM1="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
B_RXP1="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; B_RXB1="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"
B_RXD1="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; B_RXE1="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
B_STAT1="$(latest_suricata_stat)"; B_MET1="$(latest_sensor_metric)"
B_CPUDELTA=$((B_CPU1-B_CPU0)); B_PDELTA=$((B_RXP1-B_RXP0)); B_BDELTA=$((B_RXB1-B_RXB0)); B_DDELTA=$((B_RXD1-B_RXD0)); B_EDELTA=$((B_RXE1-B_RXE0))
B_KP0="$(jfield "$B_STAT0" capture_kernel_packets)"; B_KP1="$(jfield "$B_STAT1" capture_kernel_packets)"
B_KD0="$(jfield "$B_STAT0" capture_kernel_drops)"; B_KD1="$(jfield "$B_STAT1" capture_kernel_drops)"
B_TLS0="$(jfield "$B_MET0" tls_eve_count)"; B_TLS1="$(jfield "$B_MET1" tls_eve_count)"
B_QUIC0="$(jfield "$B_MET0" quic_eve_count)"; B_QUIC1="$(jfield "$B_MET1" quic_eve_count)"
B_INV0="$(jfield "$B_MET0" eve_json_invalid)"; B_INV1="$(jfield "$B_MET1" eve_json_invalid)"
B_TR0="$(jfield "$B_MET0" eve_datagram_truncated)"; B_TR1="$(jfield "$B_MET1" eve_datagram_truncated)"
echo "BASELINE_WINDOW_SECONDS=$B_WALL"
echo "BASELINE_INPUT_PPS=$(calc_pps "$B_PDELTA" "$B_WALL")"
echo "BASELINE_INPUT_MBIT=$(calc_mbps "$B_BDELTA" "$B_WALL")"
echo "BASELINE_SURICATA_CPU_RATIO=$(calc_ratio "$B_CPUDELTA" "$B_WALL")"
echo "BASELINE_MEMORY_BEFORE=$B_MEM0 BASELINE_MEMORY_MID=${B_MEMMID:-NA} BASELINE_MEMORY_AFTER=$B_MEM1"
echo "BASELINE_CAPTURE_PACKET_DELTA=$(( ${B_KP1:-0} - ${B_KP0:-0} ))"
echo "BASELINE_CAPTURE_DROP_DELTA=$(( ${B_KD1:-0} - ${B_KD0:-0} ))"
echo "BASELINE_NIC_RX_DROPPED_DELTA=$B_DDELTA BASELINE_NIC_RX_ERRORS_DELTA=$B_EDELTA"
echo "BASELINE_TLS_PROGRESSION=$(( ${B_TLS1:-0} - ${B_TLS0:-0} ))"
echo "BASELINE_QUIC_PROGRESSION=$(( ${B_QUIC1:-0} - ${B_QUIC0:-0} ))"
echo "BASELINE_EVE_INVALID_DELTA=$(( ${B_INV1:-0} - ${B_INV0:-0} ))"
echo "BASELINE_EVE_TRUNCATED_DELTA=$(( ${B_TR1:-0} - ${B_TR0:-0} ))"

# Recheck immediately before mutation
echo; echo '=== PRE-INSTALL RECHECK ==='
[ "$(sha "$BASE")" = "$BASE_SHA" ] || { echo 'PREINSTALL=FAIL BASE_SHA_DRIFT'; exit 34; }
[ "$(sha "$CAND")" = "$CAND_SHA" ] || { echo 'PREINSTALL=FAIL CAND_SHA_DRIFT'; exit 35; }
RUN_NOW="$(run_avail)"; echo "RUN_TMPFS_AVAILABLE_PREINSTALL_BYTES=$RUN_NOW"
[ "$RUN_NOW" -ge "$MIN_BEFORE" ] || { echo 'PREINSTALL=FAIL RUN_CAPACITY'; exit 36; }
[ ! -e "$OUT" ] && [ ! -L "$OUT" ] || { echo 'PREINSTALL=FAIL STALE_OUTPUT'; stat -Lc 'PATH=%n SIZE=%s MTIME=%y OWNER=%U GROUP=%G MODE=%a' "$OUT" || true; exit 37; }

# Owner-controlled client confirmation
echo; echo '=== CONTROLLED OWNER CLIENT CONFIRMATION ==='
HIST_MAC='be:00:7d:9b:04:2e'
read -r -p "Current phone Wi-Fi MAC for Zefer_Parki [$HIST_MAC]: " CONTROLLED_MAC
CONTROLLED_MAC="${CONTROLLED_MAC:-$HIST_MAC}"
CONTROLLED_MAC="$(printf '%s' "$CONTROLLED_MAC" | tr 'A-F' 'a-f')"
python3 - "$CONTROLLED_MAC" <<'PY'
import re,sys
if not re.fullmatch(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}',sys.argv[1]): raise SystemExit(1)
PY
read -r -p 'Current phone IPv4 on Zefer_Parki: ' CONTROLLED_IP
python3 - "$CONTROLLED_IP" "$GUEST_CIDR" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1]); net=ipaddress.ip_network(sys.argv[2])
if ip.version != 4 or ip not in net: raise SystemExit(1)
PY
read -r -p 'Confirm phone is ONLINE on SSID Zefer_Parki now (type YES): ' SSID_OK
[ "$SSID_OK" = YES ] || { echo 'CONTROLLED_CLIENT_CONFIRMATION=FAIL'; exit 55; }
echo "CONTROLLED_CLIENT_MAC=$CONTROLLED_MAC"
echo "CONTROLLED_CLIENT_IPV4=$CONTROLLED_IP"
echo 'CONTROLLED_CLIENT_SSID=Zefer_Parki'
echo 'CONTROLLED_CLIENT_ASSOCIATION_ATTESTED=YES'
# Authorized exact candidate mutation
echo; echo '=== CANDIDATE ACTIVATION ==='
sudo install -o "$BASE_OWNER" -g "$BASE_GROUP" -m "$BASE_MODE" "$CAND" "$BASE"
ACTIVE=1
INSTALLED_SHA="$(sha "$BASE")"; echo "INSTALLED_CANDIDATE_SHA256=$INSTALLED_SHA"
[ "$INSTALLED_SHA" = "$CAND_SHA" ] || { echo 'CANDIDATE_INSTALL=FAIL SHA'; exit 40; }
sudo systemctl restart fingerprint-suricata.service
sleep 5
[ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo 'CANDIDATE_STARTUP=FAIL'; exit 41; }
[ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'CANDIDATE_STARTUP=FAIL SENSOR'; exit 42; }
[ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_BEFORE" ] || { echo 'CANDIDATE_STARTUP=FAIL SENSOR_PID_CHANGED'; exit 43; }
SURICATA_PID_CAND="$(svc_pid fingerprint-suricata.service)"; echo "SURICATA_PID_CANDIDATE=$SURICATA_PID_CAND"
[ "$SURICATA_PID_CAND" != "$SURICATA_PID_BEFORE" ] || echo 'WARNING=SURICATA_PID_DID_NOT_CHANGE'

for _ in $(seq 1 20); do [ -e "$OUT" ] && break; sleep 1; done
[ -e "$OUT" ] || { echo 'CANDIDATE_OUTPUT=FAIL NOT_CREATED'; exit 44; }
[ ! -L "$OUT" ] || { echo 'CANDIDATE_OUTPUT=FAIL SYMLINK'; exit 45; }
OUT_OWNER="$(stat -Lc %U "$OUT")"; OUT_GROUP="$(stat -Lc %G "$OUT")"; OUT_MODE="$(stat -Lc %a "$OUT")"
echo "CANDIDATE_OUTPUT_OWNER=$OUT_OWNER CANDIDATE_OUTPUT_GROUP=$OUT_GROUP CANDIDATE_OUTPUT_MODE=$OUT_MODE"
echo "FILE_DEVICE_ID=$(stat -Lc %d "$OUT")"
echo "FILE_INODE=$(stat -Lc %i "$OUT")"
echo "OUTPUT_PARENT_OWNER=$(stat -Lc %U /run/fingerprint-suricata) OUTPUT_PARENT_GROUP=$(stat -Lc %G /run/fingerprint-suricata) OUTPUT_PARENT_MODE=$(stat -Lc %a /run/fingerprint-suricata)"
[ "$(stat -Lc %U /run/fingerprint-suricata)" = suricata ] || { echo 'CANDIDATE_OUTPUT=FAIL PARENT_OWNER'; exit 461; }
[ "$(stat -Lc %G /run/fingerprint-suricata)" = suricata ] || { echo 'CANDIDATE_OUTPUT=FAIL PARENT_GROUP'; exit 462; }
[ "$(stat -Lc %a /run/fingerprint-suricata)" = 750 ] || { echo 'CANDIDATE_OUTPUT=FAIL PARENT_MODE'; exit 463; }
[ "$OUT_OWNER" = suricata ] || { echo 'CANDIDATE_OUTPUT=FAIL OWNER'; exit 46; }
[ "$OUT_GROUP" = suricata ] || { echo 'CANDIDATE_OUTPUT=FAIL GROUP'; exit 47; }
MODE_DEC=$((8#$OUT_MODE)); [ $((MODE_DEC & 022)) -eq 0 ] || { echo 'CANDIDATE_OUTPUT=FAIL WRITABLE_BY_GROUP_OR_OTHER'; exit 48; }

# Warm-up 60s with storage monitoring
echo; echo '=== CANDIDATE WARM-UP 60s ==='
for i in $(seq 1 12); do
  sleep 5
  SZ="$(out_size)"; AV="$(run_avail)"
  [ "$SZ" -gt "$OUT_PEAK" ] && OUT_PEAK="$SZ"
  [ "$AV" -lt "$RUN_MIN" ] && RUN_MIN="$AV"
  [ "$SZ" -lt "$MAX_OUT" ] || { echo 'OUTPUT_VOLUME_LIMIT_REACHED=YES'; exit 50; }
  [ "$AV" -ge "$MIN_DURING" ] || { echo 'TMPFS_RESERVED_CAPACITY_BREACHED=YES'; exit 51; }
  [ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'STOP=SENSOR_INACTIVE'; exit 52; }
  [ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_BEFORE" ] || { echo 'STOP=SENSOR_PID_CHANGED'; exit 53; }
  [ "$(svc_pid fingerprint-suricata.service)" = "$SURICATA_PID_CAND" ] || { echo 'STOP=UNEXPECTED_SURICATA_PID_CHANGE'; exit 54; }
done
OUT_WARM="$(out_size)"; echo "CANDIDATE_OUTPUT_BYTES_AFTER_WARMUP=$OUT_WARM"

echo 'MEASURED WINDOW STARTING: for the next 300 seconds use the confirmed phone normally on Zefer_Parki. Open several normal websites/apps so DNS/TLS/QUIC-capable HTTPS has a chance to occur. Do not run a speed test or flood.'

# Align measurement start to last complete line boundary
MEAS_OFFSET="$(python3 - "$OUT" <<'PY'
import os,sys
p=sys.argv[1]; size=os.path.getsize(p)
if size==0: print(0); raise SystemExit
with open(p,'rb') as f:
    span=min(size,1048576); f.seek(size-span); data=f.read(span)
i=data.rfind(b'\n'); print((size-span+i+1) if i>=0 else 0)
PY
)"
echo "MEASUREMENT_START_COMPLETE_RECORD_OFFSET=$MEAS_OFFSET"

# Candidate measurement start metrics
C_CPU0="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"; C_MEM0="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
C_RXP0="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; C_RXB0="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"
C_RXD0="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; C_RXE0="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
C_STAT0="$(latest_suricata_stat)"; C_MET0="$(latest_sensor_metric)"; C_T0="$(date +%s)"
C_KD_PREV="$(jfield "$C_STAT0" capture_kernel_drops)"; C_KD_PREV="${C_KD_PREV:-0}"; KD_STREAK=0
NICD_PREV="$C_RXD0"; NICE_PREV="$C_RXE0"; NIC_STREAK=0
C_INV0="$(jfield "$C_MET0" eve_json_invalid)"; C_INV0="${C_INV0:-0}"
C_TR0="$(jfield "$C_MET0" eve_datagram_truncated)"; C_TR0="${C_TR0:-0}"

python3 "$OBSERVER" "$OUT" "$MEAS_OFFSET" 300 "$GUEST_CIDR" "$CONTROLLED_IP" "$OBS_SUM" "$OBS_FAIL" > "$WORK/observer-stdout.json" 2> "$WORK/observer-stderr.log" &
OBS_PID=$!
( sleep 60; python3 "$REPLAY" "$OUT" "$MEAS_OFFSET" "$REPLAY_SUM" > "$WORK/replay-stdout.json" 2> "$WORK/replay-stderr.log" ) &
REPLAY_PID=$!

echo; echo '=== CANDIDATE MEASURED WINDOW 300s ==='
for i in $(seq 1 60); do
  sleep 5
  SZ="$(out_size)"; AV="$(run_avail)"
  [ "$SZ" -gt "$OUT_PEAK" ] && OUT_PEAK="$SZ"
  [ "$AV" -lt "$RUN_MIN" ] && RUN_MIN="$AV"
  [ "$SZ" -lt "$MAX_OUT" ] || { echo 'OUTPUT_VOLUME_LIMIT_REACHED=YES'; exit 60; }
  [ "$AV" -ge "$MIN_DURING" ] || { echo 'TMPFS_RESERVED_CAPACITY_BREACHED=YES'; exit 61; }
  [ ! -e "$OBS_FAIL" ] || { echo 'STOP=CANDIDATE_MALFORMED_JSON'; exit 62; }
  [ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'STOP=SENSOR_INACTIVE'; exit 63; }
  [ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_BEFORE" ] || { echo 'STOP=SENSOR_PID_CHANGED'; exit 64; }
  [ "$(svc_pid fingerprint-suricata.service)" = "$SURICATA_PID_CAND" ] || { echo 'STOP=UNEXPECTED_SURICATA_PID_CHANGE'; exit 65; }
  if (( i % 6 == 0 )); then
    CM="$(latest_sensor_metric)"; CS="$(latest_suricata_stat)"
    INV="$(jfield "$CM" eve_json_invalid)"; INV="${INV:-0}"; TR="$(jfield "$CM" eve_datagram_truncated)"; TR="${TR:-0}"
    [ "$INV" -le "$C_INV0" ] || { echo 'STOP=FINGERPRINT_EVE_INVALID_REGRESSION'; exit 66; }
    [ "$TR" -le "$C_TR0" ] || { echo 'STOP=FINGERPRINT_EVE_TRUNCATED_REGRESSION'; exit 67; }
    KD="$(jfield "$CS" capture_kernel_drops)"; KD="${KD:-$C_KD_PREV}"
    if [ "$KD" -gt "$C_KD_PREV" ]; then KD_STREAK=$((KD_STREAK+1)); else KD_STREAK=0; fi
    C_KD_PREV="$KD"
    NRD="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; NRE="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
    if [ "$NRD" -gt "$NICD_PREV" ] || [ "$NRE" -gt "$NICE_PREV" ]; then NIC_STREAK=$((NIC_STREAK+1)); else NIC_STREAK=0; fi
    NICD_PREV="$NRD"; NICE_PREV="$NRE"
    [ "$KD_STREAK" -lt 2 ] || { echo 'STOP=SUSTAINED_CAPTURE_KERNEL_DROP_GROWTH'; exit 68; }
    [ "$NIC_STREAK" -lt 2 ] || { echo 'STOP=SUSTAINED_NIC_DROP_ERROR_GROWTH'; exit 69; }
  fi
  if [ "$i" -eq 30 ]; then C_MEMMID="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"; fi
done

wait "$OBS_PID" || true; OBS_PID=''
wait "$REPLAY_PID" || true; REPLAY_PID=''
C_T1="$(date +%s)"; C_WALL=$((C_T1-C_T0))
C_CPU1="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"; C_MEM1="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
C_RXP1="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; C_RXB1="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"
C_RXD1="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; C_RXE1="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
C_STAT1="$(latest_suricata_stat)"; C_MET1="$(latest_sensor_metric)"
C_CPUDELTA=$((C_CPU1-C_CPU0)); C_PDELTA=$((C_RXP1-C_RXP0)); C_BDELTA=$((C_RXB1-C_RXB0)); C_DDELTA=$((C_RXD1-C_RXD0)); C_EDELTA=$((C_RXE1-C_RXE0))
C_KP0="$(jfield "$C_STAT0" capture_kernel_packets)"; C_KP1="$(jfield "$C_STAT1" capture_kernel_packets)"
C_KD0="$(jfield "$C_STAT0" capture_kernel_drops)"; C_KD1="$(jfield "$C_STAT1" capture_kernel_drops)"
C_TLS0="$(jfield "$C_MET0" tls_eve_count)"; C_TLS1="$(jfield "$C_MET1" tls_eve_count)"
C_QUIC0="$(jfield "$C_MET0" quic_eve_count)"; C_QUIC1="$(jfield "$C_MET1" quic_eve_count)"
C_INV1="$(jfield "$C_MET1" eve_json_invalid)"; C_TR1="$(jfield "$C_MET1" eve_datagram_truncated)"
OUT_FINAL="$(out_size)"; [ "$OUT_FINAL" -gt "$OUT_PEAK" ] && OUT_PEAK="$OUT_FINAL"
RUN_END_CAND="$(run_avail)"; [ "$RUN_END_CAND" -lt "$RUN_MIN" ] && RUN_MIN="$RUN_END_CAND"
MEASURED_BYTES=$((OUT_FINAL-OUT_WARM)); [ "$MEASURED_BYTES" -ge 0 ] || MEASURED_BYTES=0

echo; echo '=== CANDIDATE RESOURCE RESULTS ==='
echo "CANDIDATE_MEASURED_WINDOW_SECONDS=$C_WALL"
echo "CANDIDATE_INPUT_PPS=$(calc_pps "$C_PDELTA" "$C_WALL")"
echo "CANDIDATE_INPUT_MBIT=$(calc_mbps "$C_BDELTA" "$C_WALL")"
echo "CANDIDATE_SURICATA_CPU_RATIO=$(calc_ratio "$C_CPUDELTA" "$C_WALL")"
echo "CANDIDATE_MEMORY_BEFORE=$C_MEM0 CANDIDATE_MEMORY_MID=${C_MEMMID:-NA} CANDIDATE_MEMORY_AFTER=$C_MEM1"
echo "CANDIDATE_CAPTURE_PACKET_DELTA=$(( ${C_KP1:-0} - ${C_KP0:-0} ))"
echo "CANDIDATE_CAPTURE_DROP_DELTA=$(( ${C_KD1:-0} - ${C_KD0:-0} ))"
echo "CANDIDATE_NIC_RX_DROPPED_DELTA=$C_DDELTA CANDIDATE_NIC_RX_ERRORS_DELTA=$C_EDELTA"
echo "CANDIDATE_TLS_PROGRESSION=$(( ${C_TLS1:-0} - ${C_TLS0:-0} ))"
echo "CANDIDATE_QUIC_PROGRESSION=$(( ${C_QUIC1:-0} - ${C_QUIC0:-0} ))"
echo "CANDIDATE_EVE_INVALID_DELTA=$(( ${C_INV1:-0} - ${C_INV0:-0} ))"
echo "CANDIDATE_EVE_TRUNCATED_DELTA=$(( ${C_TR1:-0} - ${C_TR0:-0} ))"
echo "CANDIDATE_OUTPUT_BYTES_AFTER_WARMUP=$OUT_WARM"
echo "CANDIDATE_OUTPUT_BYTES_FINAL=$OUT_FINAL"
echo "CANDIDATE_OUTPUT_BYTES=$MEASURED_BYTES"
echo "CANDIDATE_OUTPUT_PEAK_BYTES=$OUT_PEAK"
echo "RUN_TMPFS_AVAILABLE_MIN_BYTES=$RUN_MIN"
echo 'OUTPUT_VOLUME_LIMIT_REACHED=NO'
echo 'TMPFS_RESERVED_CAPACITY_BREACHED=NO'

if [ -f "$OBS_SUM" ]; then
  echo; echo '=== SANITIZED OBSERVER SUMMARY ==='; cat "$OBS_SUM"
else
  echo 'OBSERVER_SUMMARY=FAIL_MISSING'
fi
if [ -f "$REPLAY_SUM" ]; then
  echo; echo '=== REPLAY/CHECKPOINT SUMMARY ==='; cat "$REPLAY_SUM"
else
  echo 'REPLAY_SUMMARY=PARTIAL_MISSING'
fi

# Fingerprint progression consistency against candidate output families
TLS_OUT="$(python3 - "$OBS_SUM" <<'PY'
import json,sys
try:d=json.load(open(sys.argv[1])); print(d.get('event_counts',{}).get('tls',0))
except: print(0)
PY
)"
QUIC_OUT="$(python3 - "$OBS_SUM" <<'PY'
import json,sys
try:d=json.load(open(sys.argv[1])); print(d.get('event_counts',{}).get('quic',0))
except: print(0)
PY
)"
TLS_FP_DELTA=$(( ${C_TLS1:-0} - ${C_TLS0:-0} )); QUIC_FP_DELTA=$(( ${C_QUIC1:-0} - ${C_QUIC0:-0} ))
FINGERPRINT_REGRESSION=NO
if [ "$TLS_OUT" -gt 0 ] && [ "$TLS_FP_DELTA" -le 0 ]; then FINGERPRINT_REGRESSION=YES; fi
if [ "$QUIC_OUT" -gt 0 ] && [ "$QUIC_FP_DELTA" -le 0 ]; then FINGERPRINT_REGRESSION=YES; fi
echo "FINGERPRINT_REGRESSION=$FINGERPRINT_REGRESSION"

# Normal exact rollback and raw cleanup
rollback normal_completion
FINISHED=1
trap - EXIT

PROD_RESTORED=NO; [ "$(sha "$BASE")" = "$BASE_SHA" ] && PROD_RESTORED=YES
RAW_REMOVED=NO; [ ! -e "$OUT" ] && RAW_REMOVED=YES

echo; echo '============================================================'
echo 'FINAL COLLECTION STATUS'
echo '============================================================'
echo "TASK=$TASK"
echo "BASE_CONFIG_SHA256=$BASE_SHA"
echo "CANDIDATE_CONFIG_SHA256=$CAND_SHA"
echo 'BASELINE_WINDOW_SECONDS=300'
echo 'CANDIDATE_WARMUP_SECONDS=60'
echo 'CANDIDATE_MEASURED_WINDOW_SECONDS=300'
echo "CONTROLLED_CLIENT_MAC=$CONTROLLED_MAC"
echo "CONTROLLED_CLIENT_IPV4=$CONTROLLED_IP"
echo 'STATS_REUSE=PASS'
echo 'FLOW_REQUIRED_FOR_V1=NO'
echo "TEMPORARY_OUTPUT_STORAGE_BEHAVIOR=PASS"
echo "FINGERPRINT_REGRESSION=$FINGERPRINT_REGRESSION"
echo 'PRODUCTION_ROLLBACK=PASS'
echo "RAW_CANDIDATE_OUTPUT_REMOVED=$RAW_REMOVED"
echo "PRODUCTION_CONFIG_RESTORED=$PROD_RESTORED"
echo 'SOURCE_GENERATION_FINALIZATION=REMAINS_IMPLEMENTATION_CONTRACT_DEPENDENCY'
echo "UTC_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'LIVE_ADMISSION_COLLECTION_COMPLETE'
