#!/usr/bin/env bash
set -Eeuo pipefail

TASK='TASK-DTI-NI-00-PRIMARY-LIVE-ADMISSION-RETRY-02'
BASE='/etc/captive-portal/device-fingerprint/suricata.yaml'
CAND='/home/admin/dti-ni00/suricata-dti-ni-v1.primary.yaml'
WORK='/home/admin/dti-ni00'
BACKUP="$WORK/suricata-baseline.retry02.authorized.yaml"
OUT='/run/fingerprint-suricata/dti-ni-v1.eve.json'
OBSERVER='/tmp/dti-ni00-retry02-observer.py'
REPLAY='/tmp/dti-ni00-retry02-replay.py'
OBS_SUM="$WORK/retry02-observer-summary.json"
REPLAY_SUM="$WORK/retry02-replay-summary.json"
OBS_SUM_TMP='/tmp/dti-ni00-retry02-observer-summary.json'
REPLAY_SUM_TMP='/tmp/dti-ni00-retry02-replay-summary.json'
OBS_STDOUT="$WORK/retry02-observer-stdout.json"
OBS_STDERR="$WORK/retry02-observer-stderr.log"
REPLAY_STDOUT="$WORK/retry02-replay-stdout.json"
REPLAY_STDERR="$WORK/retry02-replay-stderr.log"
OBS_FAIL='/tmp/dti-ni00-retry02-malformed.flag'

BASE_SHA='28609c533bbf97c09e58d175e2b9c24effa76ac98535e03665937a9c57c6e56f'
CAND_SHA='b9fc0262fe89b1d2155e5aa633e51f0941c4bd9ba6f33df607378a26e0628a53'
MAX_OUT=134217728
MIN_BEFORE=671088640
MIN_DURING=536870912
GUEST_CIDR='192.168.8.0/22'
ATTEMPT01_STARTUP_SECONDS='9.16'
ATTEMPT01_STARTUP_DROPS='1739'

ACTIVE=0
FINISHED=0
OBS_PID=''
REPLAY_PID=''
BASE_OWNER=''
BASE_GROUP=''
BASE_MODE=''
SENSOR_PID_BEFORE=''
SURICATA_PID_BEFORE=''
SURICATA_PID_CAND=''
RUN_MIN=''
OUT_PEAK=0
ROLLBACK_RESULT='NOT_RUN'
ROLLBACK_STARTUP_SECONDS='UNAVAILABLE'
ROLLBACK_EARLY_DROPS='UNAVAILABLE'
ROLLBACK_EARLY_PACKETS='UNAVAILABLE'
CAND_STARTUP_SECONDS='UNAVAILABLE'
CAND_FIRST_PACKETS='UNAVAILABLE'
CAND_FIRST_DROPS='UNAVAILABLE'

sha() { sha256sum "$1" | awk '{print $1}'; }
svc_pid() { systemctl show "$1" -p MainPID --value; }
svc_restarts() { systemctl show "$1" -p NRestarts --value; }
run_total() { df -B1 --output=size /run | tail -n1 | tr -d ' '; }
run_avail() { df -B1 --output=avail /run | tail -n1 | tr -d ' '; }
out_exists() { sudo -u suricata test -e "$OUT"; }
out_is_link() { sudo -u suricata test -L "$OUT"; }
out_size() { if out_exists; then sudo -u suricata stat -Lc %s "$OUT"; else echo 0; fi; }

latest_sensor_metric() {
  sudo journalctl -u fingerprint-sensor.service -o cat --no-pager --since '-30 min' 2>/dev/null \
    | grep '"event":"fingerprint_sensor_metrics"' | tail -n1 || true
}
latest_suricata_stat() {
  sudo journalctl -u fingerprint-sensor.service -o cat --no-pager --since '-30 min' 2>/dev/null \
    | grep '"event":"fingerprint_suricata_stats"' | tail -n1 || true
}
jfield() {
  local json="$1" field="$2"
  printf '%s' "$json" | python3 -c 'import json,sys; s=sys.stdin.read().strip(); d=json.loads(s) if s else {}; v=d.get(sys.argv[1]); print("" if v is None else v)' "$field" 2>/dev/null || true
}
calc_ratio() { awk -v c="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.6f",(c/1000000000)/w;else print "NA"}'; }
calc_pps() { awk -v p="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.2f",p/w;else print "NA"}'; }
calc_mbps() { awk -v b="$1" -v w="$2" 'BEGIN{if(w>0)printf "%.6f",(b*8)/(w*1000000);else print "NA"}'; }

usec_to_utc() {
  python3 - "$1" <<'PY'
import datetime as dt,sys
u=int(sys.argv[1]); print(dt.datetime.fromtimestamp(u/1_000_000,dt.timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z'))
PY
}

pid_event_record() {
  local pid="$1" pattern="$2" since_epoch="$3"
  sudo journalctl _PID="$pid" --since "@$((since_epoch-2))" -o json --no-pager 2>/dev/null \
    | python3 -c '
import json,sys
pat=sys.argv[1]
for line in sys.stdin:
    try:d=json.loads(line)
    except Exception: continue
    if pat in str(d.get("MESSAGE","")):
        print(str(d.get("__REALTIME_TIMESTAMP",""))); break
' "$pattern"
}

stat_record_after_usec() {
  local min_usec="$1" mode="${2:-last}"
  local since_epoch=$((min_usec/1000000-2))
  sudo journalctl -u fingerprint-sensor.service --since "@$since_epoch" -o json --no-pager 2>/dev/null \
    | python3 -c '
import json,sys
minu=int(sys.argv[1]); mode=sys.argv[2]; found=[]
for line in sys.stdin:
    try:d=json.loads(line); u=int(d.get("__REALTIME_TIMESTAMP",0)); m=json.loads(d.get("MESSAGE",""))
    except Exception: continue
    if u < minu or m.get("event") != "fingerprint_suricata_stats": continue
    p=m.get("capture_kernel_packets"); dr=m.get("capture_kernel_drops")
    if p is None or dr is None: continue
    rec=(u,int(p),int(dr)); found.append(rec)
    if mode=="first": break
if found:
    u,p,dr=(found[0] if mode=="first" else found[-1]); print(f"{u}|{p}|{dr}")
' "$min_usec" "$mode"
}

metric_record_after_usec() {
  local min_usec="$1" mode="${2:-last}"
  local since_epoch=$((min_usec/1000000-2))
  sudo journalctl -u fingerprint-sensor.service --since "@$since_epoch" -o json --no-pager 2>/dev/null \
    | python3 -c '
import json,sys
minu=int(sys.argv[1]); mode=sys.argv[2]; found=[]
for line in sys.stdin:
    try:d=json.loads(line); u=int(d.get("__REALTIME_TIMESTAMP",0)); m=json.loads(d.get("MESSAGE",""))
    except Exception: continue
    if u < minu or m.get("event") != "fingerprint_sensor_metrics": continue
    found.append((u,m))
    if mode=="first": break
if found:
    u,m=(found[0] if mode=="first" else found[-1]); print(json.dumps({"journal_usec":u,**m},separators=(",",":")))
' "$min_usec" "$mode"
}

wait_engine_ready() {
  local pid="$1" since_epoch="$2" label="$3"
  local deadline=$((since_epoch+30)) ready='' start=''
  while [ "$(date +%s)" -le "$deadline" ]; do
    if [ "$(svc_pid fingerprint-suricata.service)" != "$pid" ]; then
      echo "${label}_ENGINE_READY=FAIL_PID_CHANGED"
      return 1
    fi
    ready="$(pid_event_record "$pid" 'Engine started.' "$since_epoch")"
    if [ -n "$ready" ]; then break; fi
    sleep 1
  done
  [ -n "$ready" ] || { echo "${label}_ENGINE_READY=FAIL_TIMEOUT"; return 1; }
  start="$(pid_event_record "$pid" 'This is Suricata version' "$since_epoch")"
  [ -n "$start" ] || start="$((since_epoch*1000000))"
  local start_utc ready_utc seconds
  start_utc="$(usec_to_utc "$start")"; ready_utc="$(usec_to_utc "$ready")"
  seconds="$(awk -v a="$start" -v b="$ready" 'BEGIN{printf "%.6f",(b-a)/1000000}')"
  echo "${label}_PROCESS_START_USEC=$start"
  echo "${label}_PROCESS_START_UTC=$start_utc"
  echo "${label}_ENGINE_READY_USEC=$ready"
  echo "${label}_ENGINE_READY_UTC=$ready_utc"
  echo "${label}_STARTUP_SECONDS=$seconds"
  printf '%s|%s|%s\n' "$start" "$ready" "$seconds" > "$WORK/.retry02-${label,,}-ready.tmp"
}

check_fixed_identity() {
  local label="$1"
  [ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo "STOP=${label}_SENSOR_INACTIVE"; return 1; }
  [ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo "STOP=${label}_SURICATA_INACTIVE"; return 1; }
  [ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_BEFORE" ] || { echo "STOP=${label}_SENSOR_PID_CHANGED"; return 1; }
  [ "$(svc_pid fingerprint-suricata.service)" = "$SURICATA_PID_CAND" ] || { echo "STOP=${label}_UNEXPECTED_SURICATA_PID_CHANGE"; return 1; }
}

check_storage() {
  local sz av cur_dev cur_ino
  if ! out_exists; then echo 'STOP=CANDIDATE_OUTPUT_DISAPPEARED'; return 1; fi
  cur_dev="$(sudo -u suricata stat -Lc %d "$OUT")"; cur_ino="$(sudo -u suricata stat -Lc %i "$OUT")"
  if [ -n "${OUT_DEV:-}" ] && { [ "$cur_dev" != "$OUT_DEV" ] || [ "$cur_ino" != "$OUT_INODE" ]; }; then echo 'STOP=CANDIDATE_OUTPUT_FILE_IDENTITY_CHANGED'; return 1; fi
  sz="$(out_size)"; av="$(run_avail)"
  [ "$sz" -gt "$OUT_PEAK" ] && OUT_PEAK="$sz"
  [ "$av" -lt "$RUN_MIN" ] && RUN_MIN="$av"
  if [ "$sz" -ge "$MAX_OUT" ]; then echo 'OUTPUT_VOLUME_LIMIT_REACHED=YES'; return 1; fi
  if [ "$av" -lt "$MIN_DURING" ]; then echo 'TMPFS_RESERVED_CAPACITY_BREACHED=YES'; return 1; fi
  return 0
}

validate_complete_json() {
  sudo -u suricata python3 - "$OUT" <<'PY'
import json,sys
p=sys.argv[1]; invalid=0; complete=0; partial=False
with open(p,'rb') as f:
    data=f.read()
parts=data.split(b'\n')
if parts and parts[-1] != b'': partial=True
for line in parts[:-1] if partial else parts:
    if not line: continue
    complete += 1
    try: json.loads(line)
    except Exception: invalid += 1
print(f"COMPLETE_JSON_RECORDS={complete}")
print(f"INVALID_COMPLETE_JSON_RECORDS={invalid}")
print(f"PARTIAL_FINAL_LINE_PRESENT={'YES' if partial else 'NO'}")
raise SystemExit(1 if invalid else 0)
PY
}

sanitized_snapshot() {
  if ! out_exists; then echo 'SANITIZED_RAW_SNAPSHOT=NO_FILE'; return 0; fi
  sudo -u suricata python3 - "$OUT" <<'PY'
import collections,json,os,sys
p=sys.argv[1]; c=collections.Counter(); invalid=0; complete=0
with open(p,'rb') as f:
    for raw in f:
        if not raw.endswith(b'\n'): continue
        complete += 1
        try:e=json.loads(raw)
        except Exception: invalid += 1; continue
        c[str(e.get('event_type'))]+=1
st=os.stat(p)
print('SANITIZED_RAW_SNAPSHOT=YES')
print(f'SNAPSHOT_FILE_BYTES={st.st_size}')
print(f'SNAPSHOT_COMPLETE_RECORDS={complete}')
print(f'SNAPSHOT_INVALID_JSON_RECORDS={invalid}')
for k in sorted(c): print(f'SNAPSHOT_EVENT_COUNT_{k.upper()}={c[k]}')
PY
}

family_counts_since_offset() {
  local off="$1"
  sudo -u suricata python3 - "$OUT" "$off" <<'PY'
import collections,json,sys
p=sys.argv[1]; off=int(sys.argv[2]); c=collections.Counter()
with open(p,'rb') as f:
    f.seek(off)
    while True:
        pos=f.tell(); raw=f.readline()
        if not raw: break
        if not raw.endswith(b'\n'): break
        try:e=json.loads(raw)
        except Exception: continue
        t=e.get('event_type')
        if t in ('dns','tls','quic'): c[t]+=1
print(f"{c['dns']}|{c['tls']}|{c['quic']}")
PY
}

last_complete_offset() {
  sudo -u suricata python3 - "$OUT" <<'PY'
import os,sys
p=sys.argv[1]; size=os.path.getsize(p)
if size==0: print(0); raise SystemExit
span=min(size,1048576)
with open(p,'rb') as f:
    f.seek(size-span); data=f.read(span)
i=data.rfind(b'\n')
print((size-span+i+1) if i>=0 else 0)
PY
}

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
    set +e
    sanitized_snapshot
    set -e

    sudo install -o "$BASE_OWNER" -g "$BASE_GROUP" -m "$BASE_MODE" "$BACKUP" "$BASE"
    local rsha
    rsha="$(sha "$BASE")"
    echo "ROLLBACK_BASE_SHA_AFTER_RESTORE=$rsha"
    if [ "$rsha" != "$BASE_SHA" ]; then
      echo 'PRODUCTION_ROLLBACK=FAIL_BASE_SHA_RESTORE_MISMATCH'; ROLLBACK_RESULT='FAIL'; ACTIVE=0; return 90
    fi
    set +e
    sudo timeout 60s /usr/bin/suricata -T -c "$BASE"
    local trc=$?
    set -e
    echo "ROLLBACK_BASE_SURICATA_T_EXIT_CODE=$trc"
    if [ "$trc" -ne 0 ]; then
      echo 'PRODUCTION_ROLLBACK=FAIL_BASELINE_SURICATA_T'; ROLLBACK_RESULT='FAIL'; ACTIVE=0; return 91
    fi

    local rb_epoch rb_pid rb_ready_file rb_ready_usec rb_first=''
    rb_epoch="$(date +%s)"
    sudo systemctl restart fingerprint-suricata.service
    rb_pid="$(svc_pid fingerprint-suricata.service)"
    echo "ROLLBACK_SURICATA_PID=$rb_pid"
    if ! wait_engine_ready "$rb_pid" "$rb_epoch" 'ROLLBACK_BASELINE'; then
      echo 'PRODUCTION_ROLLBACK=FAIL_ENGINE_READY'; ROLLBACK_RESULT='FAIL'; ACTIVE=0; return 92
    fi
    rb_ready_file="$WORK/.retry02-rollback_baseline-ready.tmp"
    rb_ready_usec="$(cut -d'|' -f2 "$rb_ready_file" 2>/dev/null || true)"
    ROLLBACK_STARTUP_SECONDS="$(cut -d'|' -f3 "$rb_ready_file" 2>/dev/null || echo UNAVAILABLE)"

    if [ -n "$rb_ready_usec" ]; then
      local deadline=$(( $(date +%s)+20 ))
      while [ "$(date +%s)" -le "$deadline" ]; do
        rb_first="$(stat_record_after_usec "$rb_ready_usec" first)"
        [ -n "$rb_first" ] && break
        sleep 1
      done
    fi
    if [ -n "$rb_first" ]; then
      IFS='|' read -r _ ROLLBACK_EARLY_PACKETS ROLLBACK_EARLY_DROPS <<<"$rb_first"
    fi
    echo "ROLLBACK_BASELINE_STARTUP_SECONDS=$ROLLBACK_STARTUP_SECONDS"
    echo "ROLLBACK_BASELINE_STARTUP_OR_EARLY_PACKETS=$ROLLBACK_EARLY_PACKETS"
    echo "ROLLBACK_BASELINE_STARTUP_OR_EARLY_DROPS=$ROLLBACK_EARLY_DROPS"

    echo "ROLLBACK_SURICATA_STATE=$(systemctl is-active fingerprint-suricata.service || true)"
    echo "ROLLBACK_SENSOR_STATE=$(systemctl is-active fingerprint-sensor.service || true)"
    echo "ROLLBACK_BASE_SHA_FINAL=$(sha "$BASE")"
    echo "ROLLBACK_SENSOR_PID=$(svc_pid fingerprint-sensor.service)"
    echo "ROLLBACK_SENSOR_NRESTARTS=$(svc_restarts fingerprint-sensor.service)"
    echo "ROLLBACK_SURICATA_NRESTARTS=$(svc_restarts fingerprint-suricata.service)"

    local ready_ok='NO' deadline_ready=$(( $(date +%s)+30 ))
    while [ "$(date +%s)" -le "$deadline_ready" ]; do
      local m state activeflag
      m="$(metric_record_after_usec "${rb_ready_usec:-0}" last)"; state="$(jfield "$m" runtime_state)"; activeflag="$(jfield "$m" suricata_process_active)"
      if [ "$state" = ready ] && { [ "$activeflag" = True ] || [ "$activeflag" = true ]; }; then ready_ok='YES'; break; fi
      sleep 1
    done
    echo "ROLLBACK_FINGERPRINT_RUNTIME_READY=$ready_ok"

    sudo rm -f -- "$OUT"
    if sudo -u suricata test -e "$OUT"; then
      echo 'RAW_CANDIDATE_OUTPUT_REMOVED=NO'
    else
      echo 'RAW_CANDIDATE_OUTPUT_REMOVED=YES'
    fi
    echo "RUN_TMPFS_AVAILABLE_AFTER_BYTES=$(run_avail)"
    ACTIVE=0
    if [ "$(sha "$BASE")" = "$BASE_SHA" ] && [ "$(systemctl is-active fingerprint-suricata.service)" = active ] && [ "$(systemctl is-active fingerprint-sensor.service)" = active ]; then
      ROLLBACK_RESULT='PASS'; echo 'PRODUCTION_ROLLBACK=PASS'
    else
      ROLLBACK_RESULT='FAIL'; echo 'PRODUCTION_ROLLBACK=FAIL'
    fi
    echo '=== ROLLBACK END ==='
  fi
}

cleanup_research_files() {
  rm -f -- "$OBSERVER" "$REPLAY" "$WORK/.retry02-candidate-ready.tmp" "$WORK/.retry02-rollback_baseline-ready.tmp" 2>/dev/null || true
  sudo rm -f -- "$OBS_FAIL" "$OBS_SUM_TMP" "$REPLAY_SUM_TMP" 2>/dev/null || true
}

on_exit() {
  local rc=$?
  set +e
  if [ "$FINISHED" -eq 0 ] && [ "$ACTIVE" -eq 1 ]; then rollback "unexpected_exit_rc_$rc"; fi
  cleanup_research_files
  exit "$rc"
}
trap on_exit EXIT
trap 'echo "INTERRUPTED=YES"; exit 130' INT TERM

mkdir -p "$WORK"
rm -f -- "$OBS_SUM" "$REPLAY_SUM" "$OBS_STDOUT" "$OBS_STDERR" "$REPLAY_STDOUT" "$REPLAY_STDERR" "$OBSERVER" "$REPLAY"
sudo rm -f -- "$OBS_FAIL" "$OBS_SUM_TMP" "$REPLAY_SUM_TMP"

cat > "$OBSERVER" <<'PY'
import collections, datetime as dt, ipaddress, json, os, signal, sys, time
path, start_s, duration_s, guest_cidr, controlled_ip, summary_path, fail_path = sys.argv[1:]
start_offset=int(start_s); duration=float(duration_s); guest=ipaddress.ip_network(guest_cidr)
stop=False
signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__('stop', True))
signal.signal(signal.SIGINT, lambda *_: globals().__setitem__('stop', True))
counts=collections.Counter(); bytes_by_family=collections.Counter(); max_size=0
field=collections.defaultdict(lambda: collections.Counter()); flow_counts=collections.defaultdict(collections.Counter)
dns_ids=collections.Counter(); dns_names=set(); sni_values=set(); unique_flows=set()
dns_types=collections.Counter(); dns_qtypes=collections.Counter(); dns_rcodes=collections.Counter(); dns_pairs={}
controlled=collections.Counter(); scope=collections.Counter(); lags=collections.defaultdict(list)
invalid=0; partial=False; first_offset=None; last_complete_offset=start_offset

def present(prefix,obj,key):
    if key in obj:
        field[prefix+'.'+key]['present']+=1
        if obj.get(key) is None: field[prefix+'.'+key]['null']+=1
        else: field[prefix+'.'+key]['non_null']+=1
    else: field[prefix+'.'+key]['absent']+=1

def parse_ts(v):
    if not isinstance(v,str): return None
    if v.endswith('Z'): v=v[:-1]+'+00:00'
    if len(v)>=5 and (v[-5] in '+-') and v[-3] != ':': v=v[:-2]+':'+v[-2:]
    try:
        x=dt.datetime.fromisoformat(v)
        return x.astimezone(dt.timezone.utc) if x.tzinfo else None
    except Exception:return None

def is_guest(v):
    try:
        a=ipaddress.ip_address(v); return a.version==4 and a in guest
    except Exception:return False

def pct(vals,p):
    if not vals:return None
    s=sorted(vals); k=(len(s)-1)*p; lo=int(k); hi=min(lo+1,len(s)-1); f=k-lo
    return s[lo]*(1-f)+s[hi]*f

started=time.monotonic(); buf=b''; offset=start_offset
with open(path,'rb',buffering=0) as f:
    f.seek(start_offset)
    while not stop and time.monotonic()-started < duration:
        chunk=f.read(65536)
        if not chunk:
            time.sleep(0.02); continue
        buf += chunk
        while b'\n' in buf:
            line,buf=buf.split(b'\n',1); rec_start=offset; offset+=len(line)+1; last_complete_offset=offset
            if not line:continue
            if first_offset is None:first_offset=rec_start
            max_size=max(max_size,len(line)+1)
            try:e=json.loads(line)
            except Exception:
                invalid+=1
                try:open(fail_path,'w').write(str(rec_start))
                except Exception:pass
                continue
            fam=e.get('event_type')
            if fam not in ('dns','tls','quic'):continue
            counts[fam]+=1; bytes_by_family[fam]+=len(line)+1
            flow=e.get('flow_id')
            if flow is not None:
                unique_flows.add(str(flow)); flow_counts[fam][str(flow)]+=1
            for k in ('timestamp','flow_id','src_ip','src_port','dest_ip','dest_port','proto','app_proto'):present('common',e,k)
            src=e.get('src_ip'); dst=e.get('dest_ip'); sg=is_guest(src); dg=is_guest(dst)
            if sg or dg:scope['resolved_intended_population']+=1
            elif src is not None or dst is not None:scope['resolved_other_population']+=1
            else:scope['unknown']+=1
            if controlled_ip and (src==controlled_ip or dst==controlled_ip):controlled[fam]+=1
            ts=parse_ts(e.get('timestamp'))
            if ts is not None:lags[fam].append((dt.datetime.now(dt.timezone.utc)-ts).total_seconds())
            body=e.get(fam); body=body if isinstance(body,dict) else {}
            if fam=='dns':
                for k in ('type','tx_id','id','queries','answers','rcode'):present('dns',body,k)
                dns_types[str(body.get('type'))]+=1
                if body.get('rcode') is not None:dns_rcodes[str(body.get('rcode'))]+=1
                qs=body.get('queries')
                if isinstance(qs,list):
                    for q in qs:
                        if isinstance(q,dict):
                            rn=q.get('rrname'); qt=q.get('rrtype')
                            if isinstance(rn,str):dns_names.add(rn)
                            if qt is not None:dns_qtypes[str(qt)]+=1
                tx=body.get('tx_id'); typ=body.get('type')
                if flow is not None and tx is not None and typ is not None:
                    dns_ids[(str(flow),str(tx),str(typ))]+=1
                    if ts is not None:
                        key=(str(flow),str(tx)); slot=dns_pairs.setdefault(key,{})
                        tname=str(typ).lower()
                        if tname in ('query','request') and 'q' not in slot:slot['q']=ts
                        if tname in ('answer','response') and 'r' not in slot:slot['r']=ts
            elif fam=='tls':
                for k in ('sni','version','client_alpns','server_alpns'):present('tls',body,k)
                if isinstance(body.get('sni'),str):sni_values.add(body['sni'])
            elif fam=='quic':
                for k in ('version','sni','ja4','extensions'):present('quic',body,k)
                if isinstance(body.get('sni'),str):sni_values.add(body['sni'])
partial=bool(buf)
dns_lat=[]
for slot in dns_pairs.values():
    if 'q' in slot and 'r' in slot:dns_lat.append((slot['r']-slot['q']).total_seconds())
summary={
 'duration_requested_seconds':duration,'duration_observed_seconds':round(time.monotonic()-started,3),
 'measurement_start_offset':start_offset,'first_complete_record_offset':first_offset,'last_complete_record_end_offset':last_complete_offset,
 'partial_final_line_observed':partial,'invalid_json_records':invalid,'event_counts':dict(counts),'bytes_by_family':dict(bytes_by_family),
 'max_event_size_bytes':max_size,'unique_flow_id_count':len(unique_flows),'dns_name_cardinality':len(dns_names),'sni_cardinality':len(sni_values),
 'dns_type_counts':dict(dns_types),'dns_query_type_counts':dict(dns_qtypes),'dns_rcode_counts':dict(dns_rcodes),
 'controlled_client_event_counts':dict(controlled),'network_scope_counts':dict(scope),'field_occurrence':{k:dict(v) for k,v in field.items()},
 'dns_identity_candidate_unique':len(dns_ids),'dns_identity_candidate_duplicate_occurrences':sum(max(0,v-1) for v in dns_ids.values()),
 'dns_latency_pairing_evidence':{'count':len(dns_lat),'min':min(dns_lat) if dns_lat else None,'p50':pct(dns_lat,.50),'p95':pct(dns_lat,.95),'p99':pct(dns_lat,.99),'max':max(dns_lat) if dns_lat else None},
 'family_flows_with_multiple_events':{fam:sum(1 for v in c.values() if v>1) for fam,c in flow_counts.items()},
 'family_max_events_per_flow':{fam:max(c.values()) if c else 0 for fam,c in flow_counts.items()},
 'delivery_lag_seconds':{fam:{'count':len(v),'min':min(v) if v else None,'p50':pct(v,.50),'p95':pct(v,.95),'p99':pct(v,.99),'max':max(v) if v else None} for fam,v in lags.items()}
}
with open(summary_path,'w',encoding='utf-8') as o:json.dump(summary,o,sort_keys=True,indent=2)
print(json.dumps(summary,sort_keys=True),flush=True)
PY

cat > "$REPLAY" <<'PY'
import json,os,sys,time
path=sys.argv[1]; floor=int(sys.argv[2]); out=sys.argv[3]
def scan(start,end):
    starts=[]; pos=start; partial=False
    with open(path,'rb') as f:f.seek(start); data=f.read(max(0,end-start))
    chunks=data.split(b'\n'); tail=chunks.pop() if chunks else b''; partial=(tail!=b'')
    for line in chunks:
        if line:
            json.loads(line); starts.append(pos)
        pos += len(line)+1
    return starts,pos,partial
st0=os.stat(path); size0=st0.st_size
starts0,checkpoint,partial0=scan(floor,size0)
time.sleep(20)
st1=os.stat(path); size1=st1.st_size
starts1,end1,partial1=scan(checkpoint,size1)
time.sleep(10)
st2=os.stat(path); size2=st2.st_size
starts2,end2,partial2=scan(checkpoint,size2)
head1=starts1[:8]; head2=starts2[:8]
identity=(st0.st_dev,st0.st_ino)==(st1.st_dev,st1.st_ino)==(st2.st_dev,st2.st_ino)
deterministic=(head1==head2[:len(head1)]) and (not head1 or head1[0]==checkpoint)
result={
 'file_device_id':st0.st_dev,'file_inode':st0.st_ino,
 'size_progression':[size0,size1,size2],'checkpoint_offset':checkpoint,
 'record_start_offsets_before_checkpoint_tail':starts0[-8:],
 'record_start_offsets_after_checkpoint_first_read':head1,
 'record_start_offsets_after_checkpoint_second_read':head2,
 'partial_final_line_observed':bool(partial0 or partial1 or partial2),
 'same_file_identity':identity,'first_record_after_checkpoint_starts_at_checkpoint':(not head1 or head1[0]==checkpoint),
 'deterministic_offset_sequence_on_reread':deterministic,
 'reader_restart_replay':('PASS' if identity and deterministic and len(head1)>0 else ('PARTIAL' if identity and deterministic else 'FAIL'))
}
with open(out,'w',encoding='utf-8') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True),flush=True)
PY

echo '============================================================'
echo "$TASK — AUTHORIZED CORRECTED BOUNDED RETRY"
echo '============================================================'
echo "UTC_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'ATTEMPT_01_CLASSIFICATION=ABORTED_RUNNER_DEFECT'
echo "ATTEMPT_01_STARTUP_SECONDS=$ATTEMPT01_STARTUP_SECONDS"
echo "ATTEMPT_01_STARTUP_DROPS=$ATTEMPT01_STARTUP_DROPS"

sudo -v

echo; echo '=== PRE-FLIGHT ==='
OBS_BASE_SHA="$(sha "$BASE")"; OBS_CAND_SHA="$(sha "$CAND")"
echo "BASE_CONFIG_SHA256=$OBS_BASE_SHA"
echo "CANDIDATE_CONFIG_SHA256=$OBS_CAND_SHA"
[ "$OBS_BASE_SHA" = "$BASE_SHA" ] || { echo 'PREFLIGHT=FAIL_BASE_SHA_DRIFT'; exit 20; }
[ "$OBS_CAND_SHA" = "$CAND_SHA" ] || { echo 'PREFLIGHT=FAIL_CANDIDATE_SHA_DRIFT'; exit 21; }
set +e
sudo timeout 60s /usr/bin/suricata -T -c "$CAND"
TRC=$?
set -e
echo "CANDIDATE_SURICATA_T_EXIT_CODE=$TRC"
[ "$TRC" -eq 0 ] || { echo 'PREFLIGHT=FAIL_CANDIDATE_SURICATA_T'; exit 22; }
[ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'PREFLIGHT=FAIL_SENSOR_INACTIVE'; exit 23; }
[ "$(systemctl is-active fingerprint-suricata.service)" = active ] || { echo 'PREFLIGHT=FAIL_SURICATA_INACTIVE'; exit 24; }
RUN_TOTAL="$(run_total)"; RUN_BEFORE="$(run_avail)"; RUN_MIN="$RUN_BEFORE"
echo "RUN_TMPFS_TOTAL_BYTES=$RUN_TOTAL"
echo "RUN_TMPFS_AVAILABLE_BEFORE_BYTES=$RUN_BEFORE"
[ "$RUN_BEFORE" -ge "$MIN_BEFORE" ] || { echo 'OUTPUT_CAPACITY_PREFLIGHT=FAIL'; exit 25; }
if sudo -u suricata test -e "$OUT"; then
  echo 'PREEXISTING_CANDIDATE_OUTPUT=YES'
  sudo -u suricata stat -Lc 'PATH=%n SIZE=%s MTIME=%y OWNER=%U GROUP=%G MODE=%a DEV=%d INODE=%i' "$OUT" || true
  exit 26
fi
echo 'OUTPUT_CAPACITY_PREFLIGHT=PASS'
echo 'PREEXISTING_CANDIDATE_OUTPUT=NO'

BASE_OWNER="$(stat -Lc %U "$BASE")"; BASE_GROUP="$(stat -Lc %G "$BASE")"; BASE_MODE="$(stat -Lc %a "$BASE")"
SENSOR_PID_BEFORE="$(svc_pid fingerprint-sensor.service)"; SURICATA_PID_BEFORE="$(svc_pid fingerprint-suricata.service)"
echo "SENSOR_PID_BEFORE=$SENSOR_PID_BEFORE"
echo "SURICATA_PID_BEFORE=$SURICATA_PID_BEFORE"
echo "SENSOR_NRESTARTS_BEFORE=$(svc_restarts fingerprint-sensor.service)"
echo "SURICATA_NRESTARTS_BEFORE=$(svc_restarts fingerprint-suricata.service)"
sudo cp --preserve=mode,ownership,timestamps "$BASE" "$BACKUP"
[ "$(sha "$BACKUP")" = "$BASE_SHA" ] || { echo 'PREFLIGHT=FAIL_BACKUP_SHA'; exit 27; }

# Fresh 300-second baseline
echo; echo '=== FRESH PRE_CHANGE_BASELINE_WINDOW 300s ==='
B_CPU0="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"
B_MEM0="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
B_RXP0="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; B_RXB0="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"
B_RXD0="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; B_RXE0="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
B_STAT0="$(latest_suricata_stat)"; B_MET0="$(latest_sensor_metric)"; B_T0="$(date +%s)"
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
echo "FRESH_BASELINE_WINDOW_SECONDS=$B_WALL"
echo "BASELINE_INPUT_PPS=$(calc_pps "$B_PDELTA" "$B_WALL")"
echo "BASELINE_INPUT_MBIT=$(calc_mbps "$B_BDELTA" "$B_WALL")"
echo "BASELINE_CPU_RATIO=$(calc_ratio "$B_CPUDELTA" "$B_WALL")"
echo "BASELINE_MEMORY_BEFORE=$B_MEM0 BASELINE_MEMORY_MID=${B_MEMMID:-NA} BASELINE_MEMORY_AFTER=$B_MEM1"
echo "BASELINE_CAPTURE_PACKET_DELTA=$(( ${B_KP1:-0} - ${B_KP0:-0} ))"
echo "BASELINE_CAPTURE_DROP_DELTA=$(( ${B_KD1:-0} - ${B_KD0:-0} ))"
echo "BASELINE_NIC_RX_DROPPED_DELTA=$B_DDELTA"
echo "BASELINE_NIC_RX_ERRORS_DELTA=$B_EDELTA"
echo "BASELINE_TLS_PROGRESSION=$(( ${B_TLS1:-0} - ${B_TLS0:-0} ))"
echo "BASELINE_QUIC_PROGRESSION=$(( ${B_QUIC1:-0} - ${B_QUIC0:-0} ))"
echo "BASELINE_EVE_INVALID_DELTA=$(( ${B_INV1:-0} - ${B_INV0:-0} ))"
echo "BASELINE_EVE_TRUNCATED_DELTA=$(( ${B_TR1:-0} - ${B_TR0:-0} ))"

# Immediate recheck before mutation
echo; echo '=== PRE-INSTALL RECHECK ==='
[ "$(sha "$BASE")" = "$BASE_SHA" ] || { echo 'PREINSTALL=FAIL_BASE_SHA_DRIFT'; exit 34; }
[ "$(sha "$CAND")" = "$CAND_SHA" ] || { echo 'PREINSTALL=FAIL_CANDIDATE_SHA_DRIFT'; exit 35; }
RUN_NOW="$(run_avail)"; echo "RUN_TMPFS_AVAILABLE_PREINSTALL_BYTES=$RUN_NOW"
[ "$RUN_NOW" -ge "$MIN_BEFORE" ] || { echo 'PREINSTALL=FAIL_RUN_CAPACITY'; exit 36; }
if sudo -u suricata test -e "$OUT"; then
  echo 'PREINSTALL=FAIL_STALE_OUTPUT'; sudo -u suricata stat -Lc 'PATH=%n SIZE=%s MTIME=%y OWNER=%U GROUP=%G MODE=%a DEV=%d INODE=%i' "$OUT" || true; exit 37
fi

# Reconfirm owner-controlled client
echo; echo '=== CONTROLLED OWNER CLIENT CONFIRMATION ==='
HIST_MAC='be:00:7d:9b:04:2e'
read -r -p "Current phone Wi-Fi MAC for Zefer_Parki [$HIST_MAC]: " CONTROLLED_MAC
CONTROLLED_MAC="${CONTROLLED_MAC:-$HIST_MAC}"; CONTROLLED_MAC="$(printf '%s' "$CONTROLLED_MAC" | tr 'A-F' 'a-f')"
python3 - "$CONTROLLED_MAC" <<'PY'
import re,sys
if not re.fullmatch(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}',sys.argv[1]):raise SystemExit(1)
PY
read -r -p 'Current phone IPv4 on Zefer_Parki: ' CONTROLLED_IP
python3 - "$CONTROLLED_IP" "$GUEST_CIDR" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1]); net=ipaddress.ip_network(sys.argv[2])
if ip.version!=4 or ip not in net:raise SystemExit(1)
PY
read -r -p 'Confirm phone is ONLINE on SSID Zefer_Parki now (type YES): ' SSID_OK
[ "$SSID_OK" = YES ] || { echo 'CONTROLLED_CLIENT_CONFIRMATION=FAIL'; exit 38; }
echo "CONTROLLED_CLIENT_MAC=$CONTROLLED_MAC"
echo "CONTROLLED_CLIENT_IPV4=$CONTROLLED_IP"
echo 'CONTROLLED_CLIENT_SSID=Zefer_Parki'
echo 'CONTROLLED_CLIENT_ASSOCIATION_ATTESTED=YES'

# Candidate activation
echo; echo '=== CANDIDATE ACTIVATION ==='
CAND_METRIC_PRE="$(latest_sensor_metric)"
C_INV_BASE="$(jfield "$CAND_METRIC_PRE" eve_json_invalid)"; C_INV_BASE="${C_INV_BASE:-0}"
C_TR_BASE="$(jfield "$CAND_METRIC_PRE" eve_datagram_truncated)"; C_TR_BASE="${C_TR_BASE:-0}"
C_TLS_BASE="$(jfield "$CAND_METRIC_PRE" tls_eve_count)"; C_TLS_BASE="${C_TLS_BASE:-0}"
C_QUIC_BASE="$(jfield "$CAND_METRIC_PRE" quic_eve_count)"; C_QUIC_BASE="${C_QUIC_BASE:-0}"

sudo install -o "$BASE_OWNER" -g "$BASE_GROUP" -m "$BASE_MODE" "$CAND" "$BASE"
ACTIVE=1
INSTALLED_SHA="$(sha "$BASE")"; echo "INSTALLED_CANDIDATE_SHA256=$INSTALLED_SHA"
[ "$INSTALLED_SHA" = "$CAND_SHA" ] || { echo 'CANDIDATE_INSTALL=FAIL_SHA'; exit 40; }
CAND_RESTART_EPOCH="$(date +%s)"
sudo systemctl restart fingerprint-suricata.service
SURICATA_PID_CAND="$(svc_pid fingerprint-suricata.service)"
echo "SURICATA_PID_CANDIDATE=$SURICATA_PID_CAND"
[ "$SURICATA_PID_CAND" != "$SURICATA_PID_BEFORE" ] || { echo 'CANDIDATE_STARTUP=FAIL_PID_DID_NOT_CHANGE'; exit 41; }
[ "$(systemctl is-active fingerprint-sensor.service)" = active ] || { echo 'CANDIDATE_STARTUP=FAIL_SENSOR'; exit 42; }
[ "$(svc_pid fingerprint-sensor.service)" = "$SENSOR_PID_BEFORE" ] || { echo 'CANDIDATE_STARTUP=FAIL_SENSOR_PID_CHANGED'; exit 43; }

if ! wait_engine_ready "$SURICATA_PID_CAND" "$CAND_RESTART_EPOCH" 'CANDIDATE'; then
  echo 'CANDIDATE_ENGINE_READY=FAIL';
  sudo journalctl _PID="$SURICATA_PID_CAND" --since "@$((CAND_RESTART_EPOCH-2))" --no-pager -n 80 || true
  exit 44
fi
CAND_READY_FILE="$WORK/.retry02-candidate-ready.tmp"
CAND_READY_USEC="$(cut -d'|' -f2 "$CAND_READY_FILE")"
CAND_STARTUP_SECONDS="$(cut -d'|' -f3 "$CAND_READY_FILE")"
echo 'CANDIDATE_ENGINE_READY=PASS'

# Correct privileged output creation gate
echo; echo '=== CANDIDATE OUTPUT CREATION GATE ==='
if ! sudo -u suricata test -e "$OUT"; then
  echo 'CANDIDATE_OUTPUT_CREATED=NO'
  sudo journalctl _PID="$SURICATA_PID_CAND" --since "@$((CAND_RESTART_EPOCH-2))" --no-pager -n 120 || true
  exit 45
fi
echo 'CANDIDATE_OUTPUT_CREATED=YES'
if sudo -u suricata test -L "$OUT"; then echo 'CANDIDATE_OUTPUT_SECURITY=FAIL_SYMLINK'; exit 46; fi
OUT_OWNER="$(sudo -u suricata stat -Lc %U "$OUT")"; OUT_GROUP="$(sudo -u suricata stat -Lc %G "$OUT")"; OUT_MODE="$(sudo -u suricata stat -Lc %a "$OUT")"
OUT_DEV="$(sudo -u suricata stat -Lc %d "$OUT")"; OUT_INODE="$(sudo -u suricata stat -Lc %i "$OUT")"; OUT_INITIAL_SIZE="$(sudo -u suricata stat -Lc %s "$OUT")"
echo "CANDIDATE_OUTPUT_OWNER=$OUT_OWNER"
echo "CANDIDATE_OUTPUT_GROUP=$OUT_GROUP"
echo "CANDIDATE_OUTPUT_MODE=$OUT_MODE"
echo "FILE_DEVICE_ID=$OUT_DEV"
echo "FILE_INODE=$OUT_INODE"
echo "CANDIDATE_OUTPUT_INITIAL_SIZE=$OUT_INITIAL_SIZE"
echo "OUTPUT_PARENT_OWNER=$(stat -Lc %U /run/fingerprint-suricata) OUTPUT_PARENT_GROUP=$(stat -Lc %G /run/fingerprint-suricata) OUTPUT_PARENT_MODE=$(stat -Lc %a /run/fingerprint-suricata)"
[ "$OUT_OWNER" = suricata ] || { echo 'CANDIDATE_OUTPUT_SECURITY=FAIL_OWNER'; exit 47; }
[ "$OUT_GROUP" = suricata ] || { echo 'CANDIDATE_OUTPUT_SECURITY=FAIL_GROUP'; exit 48; }
MODE_DEC=$((8#$OUT_MODE)); [ $((MODE_DEC & 022)) -eq 0 ] || { echo 'CANDIDATE_OUTPUT_SECURITY=FAIL_GROUP_OR_OTHER_WRITABLE'; exit 49; }
[ "$(stat -Lc %U /run/fingerprint-suricata)" = suricata ] && [ "$(stat -Lc %G /run/fingerprint-suricata)" = suricata ] && [ "$(stat -Lc %a /run/fingerprint-suricata)" = 750 ] || { echo 'CANDIDATE_OUTPUT_SECURITY=FAIL_PARENT'; exit 50; }

# First trustworthy STATS after engine-ready. Warm-up starts only after this anchor.
echo; echo '=== CANDIDATE FIRST STATS / STARTUP-EARLY LOSS ==='
FIRST_STAT=''; FIRST_DEADLINE=$(( $(date +%s)+20 ))
while [ "$(date +%s)" -le "$FIRST_DEADLINE" ]; do
  check_fixed_identity 'FIRST_STATS' || exit 51
  check_storage || exit 52
  FIRST_STAT="$(stat_record_after_usec "$CAND_READY_USEC" first)"
  [ -n "$FIRST_STAT" ] && break
  sleep 1
done
[ -n "$FIRST_STAT" ] || { echo 'CANDIDATE_FIRST_STATS=FAIL_NOT_OBSERVED'; exit 53; }
IFS='|' read -r CAND_FIRST_USEC CAND_FIRST_PACKETS CAND_FIRST_DROPS <<<"$FIRST_STAT"
echo "CANDIDATE_FIRST_STATS_OBSERVED_AT=$(usec_to_utc "$CAND_FIRST_USEC")"
echo "CANDIDATE_FIRST_STATS_PACKET_COUNT=$CAND_FIRST_PACKETS"
echo "CANDIDATE_FIRST_STATS_DROP_COUNT=$CAND_FIRST_DROPS"
echo 'CANDIDATE_ENGINE_READY_PACKET_COUNT=unavailable'
echo 'CANDIDATE_ENGINE_READY_DROP_COUNT=unavailable'

# Warm-up 60 seconds anchored after first trustworthy STATS
echo; echo '=== CANDIDATE WARM-UP 60s ==='
W_T0="$(date +%s)"; W_RXP0="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; W_RXB0="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"
W_LAST_USEC="$CAND_FIRST_USEC"; W_LAST_PACKETS="$CAND_FIRST_PACKETS"; W_LAST_DROPS="$CAND_FIRST_DROPS"; W_INC_STREAK=0
W_DEADLINE=$((W_T0+60)); W_NEXT_CHECK=5
while [ "$(date +%s)" -lt "$W_DEADLINE" ]; do
  sleep 1
  check_fixed_identity 'WARMUP' || exit 54
  check_storage || exit 55
  W_ELAPSED=$(( $(date +%s)-W_T0 ))
  if [ "$W_ELAPSED" -ge "$W_NEXT_CHECK" ]; then
    W_NEXT_CHECK=$((W_NEXT_CHECK+5))
    WM="$(latest_sensor_metric)"; WI="$(jfield "$WM" eve_json_invalid)"; WI="${WI:-0}"; WT="$(jfield "$WM" eve_datagram_truncated)"; WT="${WT:-0}"
    [ "$WI" -le "$C_INV_BASE" ] || { echo 'STOP=FINGERPRINT_EVE_INVALID_REGRESSION'; exit 56; }
    [ "$WT" -le "$C_TR_BASE" ] || { echo 'STOP=FINGERPRINT_EVE_TRUNCATED_REGRESSION'; exit 57; }
    REC="$(stat_record_after_usec "$CAND_FIRST_USEC" last)"
    if [ -n "$REC" ]; then
      IFS='|' read -r RU RP RD <<<"$REC"
      if [ "$RU" != "$W_LAST_USEC" ]; then
        if [ "$W_ELAPSED" -ge 30 ]; then
          if [ "$RD" -gt "$W_LAST_DROPS" ]; then W_INC_STREAK=$((W_INC_STREAK+1)); else W_INC_STREAK=0; fi
          if [ "$W_INC_STREAK" -ge 2 ]; then
            echo 'WARMUP_SUSTAINED_DROP_GROWTH=YES'; exit 58
          fi
        fi
        W_LAST_USEC="$RU"; W_LAST_PACKETS="$RP"; W_LAST_DROPS="$RD"
      fi
    fi
  fi
done
W_T1="$(date +%s)"; W_RXP1="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; W_RXB1="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"; W_WALL=$((W_T1-W_T0))
W_FINAL_REC="$(stat_record_after_usec "$CAND_FIRST_USEC" last)"; IFS='|' read -r W_END_USEC W_END_PACKETS W_END_DROPS <<<"$W_FINAL_REC"
W_OUT="$(out_size)"; echo "CANDIDATE_WARMUP_CAPTURE_PACKET_DELTA=$((W_END_PACKETS-CAND_FIRST_PACKETS))"
echo "CANDIDATE_WARMUP_CAPTURE_DROP_DELTA=$((W_END_DROPS-CAND_FIRST_DROPS))"
echo "CANDIDATE_WARMUP_INPUT_PPS=$(calc_pps "$((W_RXP1-W_RXP0))" "$W_WALL")"
echo "CANDIDATE_WARMUP_INPUT_MBIT=$(calc_mbps "$((W_RXB1-W_RXB0))" "$W_WALL")"
echo "CANDIDATE_OUTPUT_BYTES_AFTER_WARMUP=$W_OUT"
echo 'WARMUP_SUSTAINED_DROP_GROWTH=NO'
set +e
validate_complete_json
VRC=$?
set -e
[ "$VRC" -eq 0 ] || { echo 'STOP=CANDIDATE_MALFORMED_JSON_DURING_WARMUP'; exit 59; }

# Measurement boundary at last complete JSON record after warm-up
MEAS_OFFSET="$(last_complete_offset)"
echo "MEASUREMENT_START_COMPLETE_RECORD_OFFSET=$MEAS_OFFSET"
echo 'MEASURED WINDOW STARTING: for the next 300 seconds use the confirmed phone normally on Zefer_Parki. Open several normal websites/apps so DNS/TLS/QUIC-capable HTTPS has a chance to occur. Do not run a speed test or flood.'

C_CPU0="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"; C_MEM0="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
C_RXP0="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; C_RXB0="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"; C_RXD0="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; C_RXE0="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
C_STAT_START="$W_FINAL_REC"; C_MET0="$(latest_sensor_metric)"; C_T0="$(date +%s)"
C_INV0="$(jfield "$C_MET0" eve_json_invalid)"; C_INV0="${C_INV0:-0}"; C_TR0="$(jfield "$C_MET0" eve_datagram_truncated)"; C_TR0="${C_TR0:-0}"
C_TLS0="$(jfield "$C_MET0" tls_eve_count)"; C_TLS0="${C_TLS0:-0}"; C_QUIC0="$(jfield "$C_MET0" quic_eve_count)"; C_QUIC0="${C_QUIC0:-0}"

sudo -u suricata python3 "$OBSERVER" "$OUT" "$MEAS_OFFSET" 300 "$GUEST_CIDR" "$CONTROLLED_IP" "$OBS_SUM_TMP" "$OBS_FAIL" >"$OBS_STDOUT" 2>"$OBS_STDERR" &
OBS_PID=$!
( sleep 60; sudo -u suricata python3 "$REPLAY" "$OUT" "$MEAS_OFFSET" "$REPLAY_SUM_TMP" >"$REPLAY_STDOUT" 2>"$REPLAY_STDERR" ) &
REPLAY_PID=$!

M_LAST_USEC="$W_END_USEC"; M_LAST_DROPS="$W_END_DROPS"; M_INC_STREAK=0; M_LAST_NICD="$C_RXD0"; M_LAST_NICE="$C_RXE0"; M_NIC_STREAK=0
M_DEADLINE=$((C_T0+300)); M_NEXT_10=10; M_NEXT_30=30; M_MID_DONE=0
while [ "$(date +%s)" -lt "$M_DEADLINE" ]; do
  sleep 1
  check_fixed_identity 'MEASURED' || exit 60
  check_storage || exit 61
  [ ! -e "$OBS_FAIL" ] || { echo 'STOP=CANDIDATE_MALFORMED_JSON'; cat "$OBS_FAIL" 2>/dev/null || true; exit 62; }
  M_ELAPSED=$(( $(date +%s)-C_T0 ))
  if [ "$M_ELAPSED" -ge "$M_NEXT_10" ]; then
    M_NEXT_10=$((M_NEXT_10+10))
    CM="$(latest_sensor_metric)"; CI="$(jfield "$CM" eve_json_invalid)"; CI="${CI:-0}"; CT="$(jfield "$CM" eve_datagram_truncated)"; CT="${CT:-0}"
    [ "$CI" -le "$C_INV0" ] || { echo 'STOP=FINGERPRINT_EVE_INVALID_REGRESSION'; exit 63; }
    [ "$CT" -le "$C_TR0" ] || { echo 'STOP=FINGERPRINT_EVE_TRUNCATED_REGRESSION'; exit 64; }
    REC="$(stat_record_after_usec "$W_END_USEC" last)"
    if [ -n "$REC" ]; then
      IFS='|' read -r MU MP MD <<<"$REC"
      if [ "$MU" != "$M_LAST_USEC" ]; then
        if [ "$MD" -gt "$M_LAST_DROPS" ]; then M_INC_STREAK=$((M_INC_STREAK+1)); else M_INC_STREAK=0; fi
        M_LAST_USEC="$MU"; M_LAST_DROPS="$MD"
        if [ "$M_INC_STREAK" -ge 2 ]; then echo 'SUSTAINED_MEASURED_DROP_GROWTH=YES'; exit 65; fi
      fi
    fi
    NRD="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; NRE="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
    if [ "$NRD" -gt "$M_LAST_NICD" ] || [ "$NRE" -gt "$M_LAST_NICE" ]; then M_NIC_STREAK=$((M_NIC_STREAK+1)); else M_NIC_STREAK=0; fi
    M_LAST_NICD="$NRD"; M_LAST_NICE="$NRE"
    if [ "$M_NIC_STREAK" -ge 2 ]; then echo 'STOP=SUSTAINED_NIC_DROP_ERROR_GROWTH'; exit 66; fi
  fi
  if [ "$M_ELAPSED" -ge "$M_NEXT_30" ]; then
    M_NEXT_30=$((M_NEXT_30+30))
    FC="$(family_counts_since_offset "$MEAS_OFFSET")"; IFS='|' read -r _ F_TLS F_QUIC <<<"$FC"
    FM="$(latest_sensor_metric)"; FP_TLS="$(jfield "$FM" tls_eve_count)"; FP_TLS="${FP_TLS:-0}"; FP_QUIC="$(jfield "$FM" quic_eve_count)"; FP_QUIC="${FP_QUIC:-0}"
    if [ "$F_TLS" -gt 0 ] && [ "$FP_TLS" -le "$C_TLS0" ]; then echo 'STOP=PROTECTED_TLS_PATH_NOT_PROGRESSING_UNDER_OBSERVED_TLS'; exit 67; fi
    if [ "$F_QUIC" -gt 0 ] && [ "$FP_QUIC" -le "$C_QUIC0" ]; then echo 'STOP=PROTECTED_QUIC_PATH_NOT_PROGRESSING_UNDER_OBSERVED_QUIC'; exit 68; fi
  fi
  if [ "$M_MID_DONE" -eq 0 ] && [ "$M_ELAPSED" -ge 150 ]; then C_MEMMID="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"; M_MID_DONE=1; fi
done

echo 'SUSTAINED_MEASURED_DROP_GROWTH=NO'
wait "$OBS_PID" || true; OBS_PID=''
wait "$REPLAY_PID" || true; REPLAY_PID=''
if sudo -u suricata test -f "$OBS_SUM_TMP"; then sudo -u suricata cat "$OBS_SUM_TMP" > "$OBS_SUM"; fi
if sudo -u suricata test -f "$REPLAY_SUM_TMP"; then sudo -u suricata cat "$REPLAY_SUM_TMP" > "$REPLAY_SUM"; fi
C_T1="$(date +%s)"; C_WALL=$((C_T1-C_T0))
C_CPU1="$(systemctl show fingerprint-suricata.service -p CPUUsageNSec --value)"; C_MEM1="$(systemctl show fingerprint-suricata.service -p MemoryCurrent --value)"
C_RXP1="$(cat /sys/class/net/enp8s0/statistics/rx_packets)"; C_RXB1="$(cat /sys/class/net/enp8s0/statistics/rx_bytes)"; C_RXD1="$(cat /sys/class/net/enp8s0/statistics/rx_dropped)"; C_RXE1="$(cat /sys/class/net/enp8s0/statistics/rx_errors)"
C_STAT_END="$(stat_record_after_usec "$W_END_USEC" last)"; C_MET1="$(latest_sensor_metric)"
IFS='|' read -r C_K_U0 C_KP0 C_KD0 <<<"$C_STAT_START"; IFS='|' read -r C_K_U1 C_KP1 C_KD1 <<<"$C_STAT_END"
C_CPUDELTA=$((C_CPU1-C_CPU0)); C_PDELTA=$((C_RXP1-C_RXP0)); C_BDELTA=$((C_RXB1-C_RXB0)); C_DDELTA=$((C_RXD1-C_RXD0)); C_EDELTA=$((C_RXE1-C_RXE0))
C_TLS1="$(jfield "$C_MET1" tls_eve_count)"; C_TLS1="${C_TLS1:-0}"; C_QUIC1="$(jfield "$C_MET1" quic_eve_count)"; C_QUIC1="${C_QUIC1:-0}"
C_INV1="$(jfield "$C_MET1" eve_json_invalid)"; C_INV1="${C_INV1:-0}"; C_TR1="$(jfield "$C_MET1" eve_datagram_truncated)"; C_TR1="${C_TR1:-0}"
OUT_FINAL="$(out_size)"; [ "$OUT_FINAL" -gt "$OUT_PEAK" ] && OUT_PEAK="$OUT_FINAL"; RUN_END_CAND="$(run_avail)"; [ "$RUN_END_CAND" -lt "$RUN_MIN" ] && RUN_MIN="$RUN_END_CAND"
MEASURED_BYTES=$((OUT_FINAL-W_OUT)); [ "$MEASURED_BYTES" -ge 0 ] || MEASURED_BYTES=0

echo; echo '=== CANDIDATE RESOURCE RESULTS ==='
echo "CANDIDATE_MEASURED_WINDOW_SECONDS=$C_WALL"
echo "CANDIDATE_MEASURED_INPUT_PPS=$(calc_pps "$C_PDELTA" "$C_WALL")"
echo "CANDIDATE_MEASURED_INPUT_MBIT=$(calc_mbps "$C_BDELTA" "$C_WALL")"
echo "CANDIDATE_SURICATA_CPU_RATIO=$(calc_ratio "$C_CPUDELTA" "$C_WALL")"
echo "CANDIDATE_MEMORY_BEFORE=$C_MEM0 CANDIDATE_MEMORY_MID=${C_MEMMID:-NA} CANDIDATE_MEMORY_AFTER=$C_MEM1"
echo "CANDIDATE_MEASURED_CAPTURE_PACKET_DELTA=$((C_KP1-C_KP0))"
echo "CANDIDATE_MEASURED_CAPTURE_DROP_DELTA=$((C_KD1-C_KD0))"
echo "CANDIDATE_NIC_RX_DROPPED_DELTA=$C_DDELTA"
echo "CANDIDATE_NIC_RX_ERRORS_DELTA=$C_EDELTA"
echo "CANDIDATE_TLS_PROGRESSION=$((C_TLS1-C_TLS0))"
echo "CANDIDATE_QUIC_PROGRESSION=$((C_QUIC1-C_QUIC0))"
echo "CANDIDATE_EVE_INVALID_DELTA=$((C_INV1-C_INV0))"
echo "CANDIDATE_EVE_TRUNCATED_DELTA=$((C_TR1-C_TR0))"
echo "CANDIDATE_OUTPUT_BYTES_AFTER_WARMUP=$W_OUT"
echo "CANDIDATE_OUTPUT_BYTES_FINAL=$OUT_FINAL"
echo "CANDIDATE_OUTPUT_BYTES=$MEASURED_BYTES"
echo "CANDIDATE_OUTPUT_PEAK_BYTES=$OUT_PEAK"
echo "RUN_TMPFS_AVAILABLE_MIN_BYTES=$RUN_MIN"
echo 'OUTPUT_VOLUME_LIMIT_REACHED=NO'
echo 'TMPFS_RESERVED_CAPACITY_BREACHED=NO'

if [ -f "$OBS_SUM" ]; then echo; echo '=== SANITIZED OBSERVER SUMMARY ==='; cat "$OBS_SUM"; else echo 'OBSERVER_SUMMARY=FAIL_MISSING'; fi
if [ -f "$REPLAY_SUM" ]; then echo; echo '=== REPLAY/CHECKPOINT SUMMARY ==='; cat "$REPLAY_SUM"; else echo 'REPLAY_SUMMARY=PARTIAL_MISSING'; fi

# Derive modeled volume from bounded measured sample only.
if [ -f "$OBS_SUM" ]; then
  python3 - "$OBS_SUM" "$C_WALL" <<'PY'
import json,sys
p=sys.argv[1]; dur=float(sys.argv[2]); d=json.load(open(p)); cnt=sum(d.get('event_counts',{}).values()); b=sum(d.get('bytes_by_family',{}).values())
print(f'CANDIDATE_EVENT_COUNT={cnt}')
print(f'DNS_EVENT_COUNT={d.get("event_counts",{}).get("dns",0)}')
print(f'TLS_EVENT_COUNT={d.get("event_counts",{}).get("tls",0)}')
print(f'QUIC_EVENT_COUNT={d.get("event_counts",{}).get("quic",0)}')
print(f'EVENTS_PER_SECOND={(cnt/dur if dur else 0):.6f}')
print(f'BYTES_PER_SECOND={(b/dur if dur else 0):.6f}')
print(f'MAX_EVENT_SIZE={d.get("max_event_size_bytes",0)}')
print(f'UNIQUE_FLOW_ID_COUNT={d.get("unique_flow_id_count",0)}')
print(f'DNS_NAME_CARDINALITY={d.get("dns_name_cardinality",0)}')
print(f'SNI_CARDINALITY={d.get("sni_cardinality",0)}')
print(f'MODELED_BYTES_PER_DAY={(b/dur*86400 if dur else 0):.0f}')
print('MODELED_BYTES_PER_DAY_BASIS=EXTRAPOLATED_FROM_BOUNDED_SAMPLE_ONLY')
PY
fi

# Fingerprint regression result for observed same-family traffic
FINGERPRINT_REGRESSION='NO'
if [ -f "$OBS_SUM" ]; then
  read -r OBS_TLS OBS_QUIC < <(python3 - "$OBS_SUM" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); c=d.get('event_counts',{}); print(c.get('tls',0),c.get('quic',0))
PY
)
  if [ "$OBS_TLS" -gt 0 ] && [ $((C_TLS1-C_TLS0)) -le 0 ]; then FINGERPRINT_REGRESSION='YES'; fi
  if [ "$OBS_QUIC" -gt 0 ] && [ $((C_QUIC1-C_QUIC0)) -le 0 ]; then FINGERPRINT_REGRESSION='YES'; fi
fi
echo "FINGERPRINT_REGRESSION=$FINGERPRINT_REGRESSION"

# Normal rollback; also records rollback-baseline startup behavior.
rollback normal_completion
FINISHED=1
trap - EXIT
cleanup_research_files

PROD_RESTORED='NO'; [ "$(sha "$BASE")" = "$BASE_SHA" ] && PROD_RESTORED='YES'
RAW_REMOVED='NO'; if ! sudo -u suricata test -e "$OUT"; then RAW_REMOVED='YES'; fi

echo; echo '============================================================'
echo 'FINAL RETRY-02 COLLECTION STATUS'
echo '============================================================'
echo "TASK=$TASK"
echo 'ATTEMPT_01_CLASSIFICATION=ABORTED_RUNNER_DEFECT'
echo "BASE_CONFIG_SHA256=$BASE_SHA"
echo "CANDIDATE_CONFIG_SHA256=$CAND_SHA"
echo "FRESH_BASELINE_WINDOW_SECONDS=$B_WALL"
echo "BASELINE_INPUT_PPS=$(calc_pps "$B_PDELTA" "$B_WALL")"
echo "BASELINE_INPUT_MBIT=$(calc_mbps "$B_BDELTA" "$B_WALL")"
echo "BASELINE_CAPTURE_PACKET_DELTA=$(( ${B_KP1:-0} - ${B_KP0:-0} ))"
echo "BASELINE_CAPTURE_DROP_DELTA=$(( ${B_KD1:-0} - ${B_KD0:-0} ))"
echo "BASELINE_CPU_RATIO=$(calc_ratio "$B_CPUDELTA" "$B_WALL")"
echo "BASELINE_MEMORY=$B_MEM0/${B_MEMMID:-NA}/$B_MEM1"
echo "CONTROLLED_CLIENT_MAC=$CONTROLLED_MAC"
echo "CONTROLLED_CLIENT_IPV4=$CONTROLLED_IP"
echo "CANDIDATE_STARTUP_SECONDS=$CAND_STARTUP_SECONDS"
echo "CANDIDATE_FIRST_STATS_PACKET_COUNT=$CAND_FIRST_PACKETS"
echo "CANDIDATE_FIRST_STATS_DROP_COUNT=$CAND_FIRST_DROPS"
echo "CANDIDATE_WARMUP_CAPTURE_PACKET_DELTA=$((W_END_PACKETS-CAND_FIRST_PACKETS))"
echo "CANDIDATE_WARMUP_CAPTURE_DROP_DELTA=$((W_END_DROPS-CAND_FIRST_DROPS))"
echo 'WARMUP_SUSTAINED_DROP_GROWTH=NO'
echo "CANDIDATE_MEASURED_WINDOW_SECONDS=$C_WALL"
echo "CANDIDATE_MEASURED_CAPTURE_PACKET_DELTA=$((C_KP1-C_KP0))"
echo "CANDIDATE_MEASURED_CAPTURE_DROP_DELTA=$((C_KD1-C_KD0))"
echo 'SUSTAINED_MEASURED_DROP_GROWTH=NO'
echo "ATTEMPT_01_STARTUP_SECONDS=$ATTEMPT01_STARTUP_SECONDS"
echo "RETRY_02_CANDIDATE_STARTUP_SECONDS=$CAND_STARTUP_SECONDS"
echo "ATTEMPT_01_STARTUP_DROPS=$ATTEMPT01_STARTUP_DROPS"
echo "RETRY_02_STARTUP_OR_EARLY_DROPS=$CAND_FIRST_DROPS"
echo "ROLLBACK_BASELINE_STARTUP_SECONDS=$ROLLBACK_STARTUP_SECONDS"
echo "ROLLBACK_BASELINE_STARTUP_OR_EARLY_DROPS=$ROLLBACK_EARLY_DROPS"
echo "FINGERPRINT_REGRESSION=$FINGERPRINT_REGRESSION"
echo "PRODUCTION_ROLLBACK=$ROLLBACK_RESULT"
echo "RAW_CANDIDATE_OUTPUT_REMOVED=$RAW_REMOVED"
echo "PRODUCTION_CONFIG_RESTORED=$PROD_RESTORED"
echo 'SOURCE_GENERATION_FINALIZATION=REMAINS_IMPLEMENTATION_CONTRACT_DEPENDENCY'
echo 'THIRD_ATTEMPT=NOT_AUTHORIZED'
echo "UTC_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'RETRY_02_COLLECTION_COMPLETE'
