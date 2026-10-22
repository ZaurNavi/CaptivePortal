#!/usr/bin/env bash

# Read-only pre-deployment inspection for CaptivPortal Home Traffic.
# This script does not fetch/pull/checkout, edit configuration, restart services,
# write databases, or activate WEB_ADMIN_HOME_TRAFFIC_ENABLED.

set -u

readonly REPOSITORY="/opt/CaptivePortal"
readonly SERVICE="captive-portal.service"
readonly EXPECTED_TARGET="3e7ef39bf08c7ead2dd701232ddda8456fe75650"
readonly EXPECTED_TARGET_PARENT="f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0"
readonly EXPECTED_FEATURE_HEAD="8116b541427ce844092521e429e47885ddd5d5b5"

stop_count=0
warning_count=0

pass() {
    printf 'PASS  %s\n' "$1"
}

warn() {
    warning_count=$((warning_count + 1))
    printf 'WARN  %s\n' "$1"
}

stop() {
    stop_count=$((stop_count + 1))
    printf 'STOP  %s\n' "$1"
}

section() {
    printf '\n[%s]\n' "$1"
}

section "IDENTITY"
printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'hostname=%s\n' "$(hostname)"
printf 'repository=%s\n' "$REPOSITORY"
printf 'service=%s\n' "$SERVICE"
printf 'expected_target=%s\n' "$EXPECTED_TARGET"
printf 'expected_target_parent=%s\n' "$EXPECTED_TARGET_PARENT"
printf 'expected_feature_head=%s\n' "$EXPECTED_FEATURE_HEAD"

section "REPOSITORY"
if [ ! -d "$REPOSITORY/.git" ]; then
    stop "production repository is unavailable"
else
    cd "$REPOSITORY" || exit 1

    current_head="$(git rev-parse HEAD 2>/dev/null || true)"
    current_branch="$(git branch --show-current 2>/dev/null || true)"
    printf 'current_head=%s\n' "${current_head:-UNAVAILABLE}"
    printf 'current_branch=%s\n' "${current_branch:-DETACHED}"
    if [ "$current_branch" = "main" ]; then
        pass "production repository is on main"
    else
        warn "production repository is not on main"
    fi

    if [ -n "$current_head" ]; then
        git show -s --format='current_subject=%s%ncurrent_commit_time=%cI' "$current_head" 2>/dev/null || true
    else
        stop "current production HEAD cannot be resolved"
    fi

    status_output="$(git status --porcelain=v1 --untracked-files=all 2>/dev/null || true)"
    if [ -z "$status_output" ]; then
        pass "working tree is clean"
    else
        stop "working tree is not clean"
        printf '%s\n' "$status_output"
    fi

    remote_main="$(git ls-remote origin refs/heads/main 2>/dev/null | awk 'NR == 1 {print $1}')"
    printf 'remote_main=%s\n' "${remote_main:-UNAVAILABLE}"
    if [ "$remote_main" = "$EXPECTED_TARGET" ]; then
        pass "remote main matches approved target"
    elif [ -z "$remote_main" ]; then
        stop "remote main could not be read"
    else
        stop "remote main differs from approved target"
    fi

    if git cat-file -e "$EXPECTED_TARGET^{commit}" 2>/dev/null; then
        pass "approved target object is already present locally"
        target_parent="$(git rev-parse "$EXPECTED_TARGET^1" 2>/dev/null || true)"
        target_second_parent="$(git rev-parse "$EXPECTED_TARGET^2" 2>/dev/null || true)"
        printf 'target_first_parent=%s\n' "${target_parent:-UNAVAILABLE}"
        printf 'target_second_parent=%s\n' "${target_second_parent:-UNAVAILABLE}"
        if [ "$target_parent" = "$EXPECTED_TARGET_PARENT" ] \
            && [ "$target_second_parent" = "$EXPECTED_FEATURE_HEAD" ]; then
            pass "approved merge parents match"
        else
            stop "approved merge parents do not match"
        fi

        if [ -n "$current_head" ] \
            && git merge-base --is-ancestor "$current_head" "$EXPECTED_TARGET" 2>/dev/null; then
            pass "production HEAD can fast-forward to approved target"
        else
            stop "production HEAD is not an ancestor of approved target"
        fi

        if [ -n "$current_head" ]; then
            if git diff --quiet "$current_head" "$EXPECTED_TARGET" -- requirements.txt 2>/dev/null; then
                pass "requirements.txt is unchanged from production HEAD"
            else
                warn "requirements.txt differs; dependency review is required before deployment"
            fi

            printf 'target_diff_summary_begin\n'
            git diff --stat "$current_head" "$EXPECTED_TARGET" -- 2>/dev/null || true
            printf 'target_diff_summary_end\n'
        fi
    else
        warn "approved target object is not local; ancestry and dependency checks remain pending until the authorized fetch stage"
    fi
fi

section "SERVICE"
active_state="$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
printf 'service_active_state=%s\n' "${active_state:-UNAVAILABLE}"
if [ "$active_state" = "active" ]; then
    pass "service is active"
else
    stop "service is not active"
fi

systemctl show "$SERVICE" \
    --property=LoadState \
    --property=ActiveState \
    --property=SubState \
    --property=MainPID \
    --property=User \
    --property=Group \
    --property=FragmentPath \
    --property=NRestarts \
    --property=ActiveEnterTimestamp \
    --no-pager 2>/dev/null || true

main_pid="$(systemctl show "$SERVICE" --property=MainPID --value 2>/dev/null || true)"
if [[ "$main_pid" =~ ^[1-9][0-9]*$ ]] && [ -r "/proc/$main_pid/status" ]; then
    pass "service MainPID is available"
    ps -o pid=,ppid=,user=,comm=,nlwp= -p "$main_pid" 2>/dev/null || true
    listener_count="$(sudo ss -ltnp 2>/dev/null | awk -v needle="pid=$main_pid," 'index($0, needle) {count++} END {print count + 0}')"
    printf 'main_pid_tcp_listener_count=%s\n' "$listener_count"
    if [ "$listener_count" -ge 1 ]; then
        pass "service MainPID owns at least one TCP listener"
    else
        warn "no TCP listener was attributed to service MainPID"
    fi
else
    stop "service MainPID is unavailable"
fi

process_count="$(pgrep -fc '/opt/CaptivePortal/run.py' 2>/dev/null || true)"
printf 'run_py_process_count=%s\n' "${process_count:-0}"
if [ "${process_count:-0}" = "1" ]; then
    pass "single-process topology is preserved"
else
    stop "expected exactly one /opt/CaptivePortal/run.py process"
fi

section "RUNNING PROCESS ENVIRONMENT"
if [[ "$main_pid" =~ ^[1-9][0-9]*$ ]] && [ -e "/proc/$main_pid/environ" ]; then
    sudo python3 - "$main_pid" <<'PY'
import sys
from pathlib import Path

pid = sys.argv[1]
raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
environment = {}
for item in raw:
    if not item or b"=" not in item:
        continue
    key, value = item.split(b"=", 1)
    environment[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")

secret_names = (
    "OMADA_URL",
    "OMADA_ID",
    "OMADA_CLIENT_ID",
    "OMADA_CLIENT_SECRET",
)
safe_names = (
    "OBSERVATION_FOUNDATION_ENABLED",
    "OBSERVATION_AP_ENABLED",
    "OBSERVATION_AP_INTERVAL_SECONDS",
    "OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS",
    "OBSERVATION_RATE_MAX_GAP_SECONDS",
    "ANALYTICS_FOUNDATION_ENABLED",
    "CURRENT_STATE_ENABLED",
    "WEB_ADMIN_ENABLED",
    "WEB_ADMIN_HOME_LIVE_ENABLED",
    "WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS",
    "WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS",
    "WEB_ADMIN_MAX_CONCURRENT_QUERIES",
    "WEB_ADMIN_MAX_QUERY_DURATION_SECONDS",
    "WEB_ADMIN_MAX_RESPONSE_BYTES",
    "WEB_ADMIN_HOME_TRAFFIC_ENABLED",
    "WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS",
    "WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS",
    "WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE",
    "WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS",
    "WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS",
    "WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS",
)

secret_contract_ok = True
for name in secret_names:
    if name not in environment:
        state = "MISSING"
    elif environment[name] == "":
        state = "EMPTY"
    else:
        state = "PRESENT"
    if state != "PRESENT":
        secret_contract_ok = False
    print(f"secret_contract_{name}={state}")

for name in safe_names:
    print(f"runtime_{name}={environment.get(name, 'MISSING')}")

if not secret_contract_ok:
    raise SystemExit(2)
PY
    environment_exit=$?
    if [ "$environment_exit" -eq 0 ]; then
        pass "running process environment was inspected through a strict allowlist"
    else
        stop "running process environment could not be inspected"
    fi
else
    stop "running process environment is unavailable"
fi

section "PERSISTENT DATA AND CAPACITY"
if [ -d "$REPOSITORY/data" ]; then
    find "$REPOSITORY/data" -maxdepth 1 -type f -name '*.sqlite3' \
        -printf 'sqlite_file=%f size_bytes=%s\n' 2>/dev/null | sort
else
    warn "repository data directory is absent"
fi

df -h "$REPOSITORY" /etc 2>/dev/null | awk 'NR == 1 || !seen[$1]++'

section "PRECHECK VERDICT"
printf 'stop_count=%s\n' "$stop_count"
printf 'warning_count=%s\n' "$warning_count"
if [ "$stop_count" -eq 0 ]; then
    printf 'verdict=PASS_TO_PREPARE_DEPLOYMENT\n'
    printf 'next_action=review_output_and_prepare_feature_disabled_deployment\n'
else
    printf 'verdict=STOP_BEFORE_DEPLOYMENT\n'
    printf 'next_action=resolve_stop_conditions_without_pull_restart_or_config_change\n'
fi

printf '\nNo fetch, pull, checkout, configuration edit, service restart, database write, or feature activation was performed.\n'
