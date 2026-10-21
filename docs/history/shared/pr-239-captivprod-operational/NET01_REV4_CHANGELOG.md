# NET01 Part A REV4 — narrow Architect corrections

**Date:** 2026-10-14. **Review basis:** `CAPTIVPROD_NET01_REV3_INDEPENDENT_ARCH_REVIEW_2026-10-14(1).md`. **Scope:** offline-only; no target changes. **Previous accepted design:** same Docker bridge, NPM, firewall allowlist, watchdog and backend.

## P1-01: rollback status command failures fail-closed

- Replaced `if systemctl is-active --quiet` / unchecked `ss | grep` semantics with single `firewall/net01-quiescent.py`, which checks success and parses *explicit* systemd LoadState/ActiveState/SubState/Job, plus no jobs from `list-jobs` and successful complete `ss` output.
- Rollback demands root-owned MAINTENANCE barrier, quiescence, exact chain guard and second quiescence before **any** deletion. Command failure/unknown service/port => HOLD, zero deletion.

## P1-02: install and HOLD-clear

- Reused strict probe in both paths; unsupported service states, ss failures, queued jobs or active TCP 18089 block install and HOLD clearance.
- Install additionally requires verified readable policy dumps; no longer interprets a failed `iptables -S CHAIN` as proof of absence.
- Clear HOLD requires maintenance barrier; HOLD remains on all uncertain conditions; only reviewed root marker unlink is allowed.

## P1-03: activation versus rollback race

- New `MAINTENANCE` root-owned 0600 marker is created **before** stopping any NET01 services, blocks startup/watchdog, survives rollback/error until explicit recovery. Shared NET01 lock coordinates guarded startup checks and NET01 maintenance scripts.
- New admission script for watchdog and Flask `ExecStartPre`; no reverse systemd cycles. Rollback requires no pending start/stop jobs and fully stopped state. Double-checks near rule deletion.
- Added root-only clear-maintenance flow after exact reinstall/guard proof; no automatic restart.

## Tests

- Added `tests/test_rev4_negative_offline.py` and disposable command fixtures, covering failures/unknown states, pending jobs, concurrent operation locks, incomplete listener probes and marker behavior.
- Kept and adapted existing REV3 positive/negative tests to the revised safety contract. Synthetic systemd syntax checks remain offline only.
- Explicitly **not tested**: real PID1 service/job races, actual on-host iptables rollback, live listener disappearance, watchdog stop propagation, Docker recreate, NPM routing.
