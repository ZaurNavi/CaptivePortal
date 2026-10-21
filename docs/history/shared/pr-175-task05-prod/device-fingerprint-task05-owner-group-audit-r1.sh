#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
DATA="/opt/CaptivePortal/data"
INTEGRATION_DB="$DATA/device_fingerprint_integration.sqlite3"
LOCK="${INTEGRATION_DB}.consumer.lock"
TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_OWNER_GROUP_AUDIT"
echo "CHANGES_ALLOWED=NO"

section "PRODUCTION"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$TARGET_TREE" ] || fail "Unexpected production tree"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive"
echo "PRODUCTION=PASS"

section "DATA DIRECTORY"
stat -c 'DATA_PATH=%n OWNER=%U:%G UID=%u GID=%g MODE=%a PERMS=%A' "$DATA"
namei -om "$DATA"

section "RUNTIME USERS"
echo "PORTAL_USER=$(systemctl show captive-portal.service -p User --value --no-pager)"
echo "PORTAL_GROUP=$(systemctl show captive-portal.service -p Group --value --no-pager)"
id admin

section "ROLLBACK CONFIG"
grep -E '^DEVICE_FINGERPRINT_(INTEGRATION_ENABLED|INTEGRATION_DB_PATH|EVIDENCE_DB_PATH|CLASSIFICATION_DB_PATH|CONTROL_PLANE_DB_PATH)=' "$CFG" || true
CFG_VALUE="$(awk -F= '
  $1=="DEVICE_FINGERPRINT_INTEGRATION_ENABLED" {
    v=substr($0,index($0,"=")+1); gsub(/^[ \t]+|[ \t]+$/,"",v); print v
  }' "$CFG" | tail -n1)"
if [ -z "$CFG_VALUE" ]; then
  echo "INTEGRATION_ENABLED=ABSENT_DEFAULT_FALSE"
else
  echo "INTEGRATION_ENABLED=$CFG_VALUE"
fi

section "CANONICAL ACTIVATION ARTIFACTS"
for p in "$INTEGRATION_DB" "$LOCK"; do
  if [ -e "$p" ]; then
    stat -c 'PRESENT=%n OWNER=%U:%G UID=%u GID=%g MODE=%a BYTES=%s' "$p"
  else
    echo "ABSENT=$p"
  fi
done

echo "UNIT_LOAD_STATE=$(systemctl show fingerprint-classification.service -p LoadState --value 2>/dev/null || true)"
echo "UNIT_ACTIVE_STATE=$(systemctl show fingerprint-classification.service -p ActiveState --value 2>/dev/null || true)"
echo "UNIT_FILE_STATE=$(systemctl show fingerprint-classification.service -p UnitFileState --value 2>/dev/null || true)"

section "ROLLBACK QUARANTINES"
find /home/admin/CaptivePortal-Deploy -maxdepth 2 \
  -type f \( -name 'device_fingerprint_integration.sqlite3' -o -name 'device_fingerprint_integration.sqlite3.consumer.lock' \) \
  -printf '%p|%u:%g|%m|%s\n' 2>/dev/null | sort || true

section "SOURCE OWNERSHIP CONTRACT"
python3 - <<'PY'
from pathlib import Path
p=Path("/opt/CaptivePortal/app/device_fingerprint_integration/repository.py")
s=p.read_text(encoding="utf-8")
needles=[
    'os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)',
    'with open(str(path) + ".consumer.lock", "a+b")',
]
for n in needles:
    print(("SOURCE_PRESENT=" if n in s else "SOURCE_MISSING=")+n)
PY

section "FINAL"
echo "TASK05_OWNER_GROUP_AUDIT=COMPLETE"
echo "CHANGES_MADE=NONE"
