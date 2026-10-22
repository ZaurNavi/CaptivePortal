# NET-01 reboot lifecycle — proposed scoped change set (Owner GO required)

**Target:** `captiv-prod` (`192.168.0.99`). **Frozen baseline unchanged:** `NET01_FINAL_LOCKPATH_APPROVED_OFFLINE_2026-10-16.zip` SHA-256 `a2904ea42f7985ec266c803d81ff76e19ce563a89f300878418668eff3599e59`.

## Exact future changes after separate Owner GO

1. Read-only: verify NPM image digest/container bridge, frozen NET01 verifier PASS, unit state, no HOLD, `systemctl is-active` NPM/Omada and reliable rollback artifacts. Ensure `captive-portal.service` remains disabled/inactive.
2. Install **new**, root-owned executable `/usr/local/libexec/captiv-net01/net01-watchdog-stop-post.py` mode `0755`. Do not overwrite any original NET01 executable.
3. Install **new** `/etc/systemd/system/captiv-net01-watchdog.service.d/50-net01-reboot-lifecycle.conf` root-owned `0644`. Drop-in clears and replaces **only** `ExecStopPost` with a minimal fail-closed lifecycle helper. All `Requires=`, `After=`, `ExecStart`, `ExecStartPre`, `OnFailure` and guard settings remain intact.
4. Add persistent boot dependency via `systemctl add-wants multi-user.target captiv-net01-watchdog.service`. Creates a Wanted-by symlink; do not enable or start the absent CaptivePortal application.
5. `systemctl daemon-reload`. Confirm effective `ExecStopPost`, `Requires`, `After`, `multi-user.target` dependency, and currently active firewall/watchdog/verifier. **Do not restart or stop** the active watchdog/firewall just to install this lifecycle update.
6. No reboot of the shared host until an additional Owner-approved maintenance window, at which time check clean reboot and prior HOLD handling; existing NPM/Omada sites before/after.

**Shutdown qualification:** only if systemd reports `stopping`, a start job for an actual final shutdown target is visible, and `SERVICE_RESULT=success`. Failures, job list unavailability, uncertain state, manual stop, drift => execute original `net01-mark-hold.py watchdog-stopped`. Original lock, user, firewall, conntrack, Docker and Sensor UID untouched. Existing HOLD never cleared.

## Scoped rollback (not executed)

If still running cleanly, remove only the exact new target dependency and new drop-in; `systemctl daemon-reload`; verify original `ExecStopPost` and baseline unchanged. Preserve the helper file until no service can invoke it, then remove it if desired. **Never stop watchdog or clear HOLD as part of generic rollback.** If watchdog has already stopped/crashed or HOLD exists, treat as fail-closed and escalate to existing authorized maintenance/rollback procedure; no automatic clearing/restarts.

## Offline test evidence

- `19/19` targeted Python assertions pass.
- Real WSL2 `Ubuntu-22.04`, systemd PID1 `249`: transient `Type=notify` service executed exact helper bytes (SHA-256 `5ef76afc021f47ebaaf94b4899457acd7a16da0d1f21c7abbd9893cca8b6827d`) with **test-only substitution** of marker path and `systemctl` state source; boot target dependency, cold start, manual stop -> HOLD, SIGKILL crash -> HOLD, existing HOLD -> denied start, synthetic orderly shutdown -> no new HOLD, uncertain manager -> HOLD all PASS; temporary unit cleaned.
- **Not verified:** real OS reboot with this helper; actual systemd `stopping`/job listing availability during shutdown. Hence `NET01_REBOOT_PERSISTENCE=HOLD_REAL_REBOOT_NOT_TESTED`. This is a genuine residual, not a claim of a completed reboot test.

**Production modifications from this lifecycle request: NONE.** Current NET01 firewall/watchdog remain as they were.
