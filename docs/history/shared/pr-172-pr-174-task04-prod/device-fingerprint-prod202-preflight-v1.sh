#!/usr/bin/env bash
set -u

APP=/opt/CaptivePortal
ENVFILE=/etc/default/captive-portal
DFDIR=/etc/captive-portal/device-fingerprint

section() {
  printf '\n===== %s =====\n' "$1"
}

cmd() {
  printf '\n$ %s\n' "$*"
  "$@" 2>&1 || true
}

kv_file_safe() {
  local file="$1"
  if [ ! -r "$file" ]; then
    echo "ENV_FILE_READABLE=NO"
    return
  fi
  echo "ENV_FILE_READABLE=YES"
  awk -F= '
    BEGIN {
      split("DEVICE_FINGERPRINT_EVIDENCE_ENABLED DEVICE_FINGERPRINT_DB_PATH DEVICE_FINGERPRINT_WRITER_LOCK_PATH DEVICE_FINGERPRINT_BIND_ADDRESS DEVICE_FINGERPRINT_PORT DEVICE_FINGERPRINT_TLS_CERT_PATH DEVICE_FINGERPRINT_TLS_KEY_PATH DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS DEVICE_FINGERPRINT_RETENTION_DAYS DEVICE_FINGERPRINT_MAX_DB_BYTES DEVICE_FINGERPRINT_PORTAL_ENABLED DEVICE_FINGERPRINT_PORTAL_PRODUCER_ID DEVICE_FINGERPRINT_PORTAL_CAPTURE_SOURCE_ID DEVICE_FINGERPRINT_PORTAL_SITE_ID DEVICE_FINGERPRINT_PORTAL_GUEST_CIDRS DEVICE_FINGERPRINT_PORTAL_ALLOWED_SSIDS DEVICE_FINGERPRINT_PORTAL_EVIDENCE_BASE_URL DEVICE_FINGERPRINT_PORTAL_CA_CERT_PATH DEVICE_FINGERPRINT_PORTAL_CREDENTIAL_PATH DEVICE_FINGERPRINT_SENSOR_ENABLED DEVICE_FINGERPRINT_SENSOR_INTERFACE DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID DEVICE_FINGERPRINT_SENSOR_SITE_ID DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS DEVICE_FINGERPRINT_SENSOR_DHCP_SERVER_AUTHORITY DEVICE_FINGERPRINT_SENSOR_DHCP_OPTION54_AUTHORITY DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL DEVICE_FINGERPRINT_SENSOR_CA_CERT_PATH DEVICE_FINGERPRINT_SENSOR_SPOOL_PATH DEVICE_FINGERPRINT_SENSOR_CORE_READY_HOST DEVICE_FINGERPRINT_SENSOR_CORE_READY_PORT", a, " ")
      for (i in a) wanted[a[i]]=1
    }
    /^[[:space:]]*#/ {next}
    /^[[:space:]]*$/ {next}
    {
      key=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      if (wanted[key]) print key "=" substr($0, index($0,"=")+1)
    }
  ' "$file"
  awk -F= '
    /^[[:space:]]*#/ {next}
    {
      key=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      if (key ~ /(SECRET|TOKEN|PASSWORD|BEARER|PRODUCERS_JSON)/)
        print "SECRET_KEY_PRESENT=" key
    }
  ' "$file" | sort -u
}

unit_summary() {
  local u="$1"
  echo "--- UNIT=$u"
  systemctl is-active "$u" 2>/dev/null | sed 's/^/ACTIVE=/' || echo "ACTIVE=not-found-or-inactive"
  systemctl is-enabled "$u" 2>/dev/null | sed 's/^/ENABLED=/' || echo "ENABLED=not-found-or-disabled"
  systemctl show "$u" -p LoadState -p ActiveState -p SubState -p FragmentPath -p MainPID -p User -p Group -p ExecStart --no-pager 2>/dev/null || true
}

section "IDENTITY"
cmd hostname
cmd hostname -I
cmd uname -a
if [ -r /etc/os-release ]; then
  grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release || true
fi
cmd date -Is
cmd timedatectl

section "RESOURCES"
cmd uptime
cmd free -h
cmd df -hT / /opt /var
cmd df -ih / /opt /var

section "NETWORK"
cmd ip -br link
cmd ip -br addr
cmd ip route
echo
echo "--- detailed link properties"
ip -d link show 2>&1 || true
echo
echo "--- PCI / NIC inventory"
if command -v lspci >/dev/null 2>&1; then
  lspci -nnk | grep -A4 -Ei 'ethernet|network' || true
else
  echo "LSPCI=NOT_INSTALLED"
fi
echo
echo "--- per-interface driver facts"
for n in /sys/class/net/*; do
  i="$(basename "$n")"
  [ "$i" = "lo" ] && continue
  echo "INTERFACE=$i"
  if command -v ethtool >/dev/null 2>&1; then
    ethtool -i "$i" 2>/dev/null || true
  fi
  printf 'OPERSTATE='; cat "$n/operstate" 2>/dev/null || true
  printf 'ADDRESS='; cat "$n/address" 2>/dev/null || true
done

section "LISTENERS"
if command -v ss >/dev/null 2>&1; then
  ss -lntup 2>&1 || true
else
  echo "SS=NOT_INSTALLED"
fi

section "APPLICATION GIT"
if [ -d "$APP/.git" ]; then
  (
    cd "$APP" || exit
    echo "APP_PRESENT=YES"
    git rev-parse HEAD 2>/dev/null | sed 's/^/HEAD=/'
    git rev-parse 'HEAD^{tree}' 2>/dev/null | sed 's/^/TREE=/'
    git status --porcelain=v1 2>/dev/null | sed 's/^/WORKTREE_CHANGE=/'
    if [ -z "$(git status --porcelain=v1 2>/dev/null)" ]; then
      echo "WORKTREE_CLEAN=YES"
    else
      echo "WORKTREE_CLEAN=NO"
    fi
    git branch --show-current 2>/dev/null | sed 's/^/BRANCH=/'
    git remote -v 2>/dev/null | sed 's/^/REMOTE=/'
    git log -1 --format='COMMIT_TIME=%cI%nSUBJECT=%s' 2>/dev/null || true
  )
else
  echo "APP_PRESENT=NO_OR_NOT_GIT"
fi

section "SYSTEMD UNITS"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service traffic-projection.service alloy.service; do
  unit_summary "$u"
done

section "CAPTIVE PORTAL UNIT"
systemctl cat captive-portal.service --no-pager 2>&1 | sed -E \
  -e 's/((SECRET|TOKEN|PASSWORD|BEARER)[A-Z0-9_]*=)[^[:space:]]+/\\1<REDACTED>/Ig' \
  -e 's/(Bearer[[:space:]]+)[A-Za-z0-9._-]+/\\1<REDACTED>/g' || true

section "FINGERPRINT UNIT DEFINITIONS"
for u in fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl cat "$u" --no-pager 2>&1 | sed -E \
  -e 's/((SECRET|TOKEN|PASSWORD|BEARER)[A-Z0-9_]*=)[^[:space:]]+/\\1<REDACTED>/Ig' \
  -e 's/(Bearer[[:space:]]+)[A-Za-z0-9._-]+/\\1<REDACTED>/g' || true
done

section "SAFE PRODUCTION ENV"
echo "ENV_FILE=$ENVFILE"
kv_file_safe "$ENVFILE"

section "FINGERPRINT CONFIG DIRECTORY METADATA"
if [ -e "$DFDIR" ]; then
  echo "DF_CONFIG_DIR_PRESENT=YES"
  find "$DFDIR" -maxdepth 2 -printf '%M %u:%g %s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort || true
else
  echo "DF_CONFIG_DIR_PRESENT=NO"
fi

section "FINGERPRINT DATA PATHS"
for p in "$APP/data/device_fingerprint_evidence.sqlite3" "$APP/data/device_fingerprint_evidence.writer.lock" "$APP/data/device_fingerprint_classification.sqlite3" "$APP/data/classification.sqlite3" /var/lib/captive-portal/fingerprint-sensor/spool.sqlite3 /run/captive-portal/fingerprint-sensor/suricata-eve.sock; do
  if [ -e "$p" ] || [ -S "$p" ]; then
    echo "PRESENT=$p"
    ls -ld "$p" 2>/dev/null || true
  else
    echo "ABSENT=$p"
  fi
done

section "FINGERPRINT REPOSITORY DEPLOY FILES"
if [ -d "$APP" ]; then
  for p in deploy/device-fingerprint/fingerprint-sensor.service deploy/device-fingerprint/fingerprint-suricata.service deploy/device-fingerprint/suricata.yaml deploy/device-fingerprint/raw-capture.bpf; do
    if [ -f "$APP/$p" ]; then
      echo "REPO_FILE_PRESENT=$p"
      sha256sum "$APP/$p" 2>/dev/null || true
    else
      echo "REPO_FILE_ABSENT=$p"
    fi
  done
fi

section "RUNTIME BINARIES"
for b in python3 git curl sqlite3 tcpdump suricata ethtool nft iptables; do
  if command -v "$b" >/dev/null 2>&1; then
    printf '%s=' "$b"
    command -v "$b"
  else
    echo "$b=NOT_INSTALLED"
  fi
done
python3 --version 2>&1 || true
git --version 2>&1 || true
suricata --build-info 2>/dev/null | head -n 12 || true
tcpdump --version 2>&1 | head -n 3 || true

section "FINGERPRINT PROCESSES"
ps -eo pid,user,group,etime,args | grep -E 'device_fingerprint|fingerprint-(evidence|sensor|suricata)|[s]uricata' | grep -v 'grep -E' || true

section "RECENT SERVICE LOGS"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  journalctl -u "$u" -n 40 --no-pager 2>/dev/null | sed -E -e 's/(Bearer[[:space:]]+)[A-Za-z0-9._-]+/\1<REDACTED>/g' -e 's/((token|secret|password)[=:][[:space:]]*)[^[:space:]]+/\1<REDACTED>/Ig' || true
done

section "PREFLIGHT MARKERS"
echo "TARGET_HOST_EXPECTED=192.168.0.202"
echo "EXPECTED_CURRENT_PORTAL_ROOT=/opt/CaptivePortal"
echo "EXPECTED_EVIDENCE_BIND=192.168.0.202:9443"
echo "NO_CHANGES_PERFORMED=YES"
