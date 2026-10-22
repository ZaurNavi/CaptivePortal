# CAPTIV-PROD — NET01 Part A REV3: Independent Architect Review

**Task:** `TASK-CAPTIVPROD-NET01-IMPLEMENTATION-03`  
**Date:** 2026-10-14 (Asia/Baku)  
**Reviewed artifact:** `TASK-CAPTIVPROD-NET01-IMPLEMENTATION-03_PART-A_REV3(1).zip`  
**Artifact SHA-256:** `1ca2bcd1df0d1a123bfc168bc08ea77f606ac745e484e8d74e5b765256c3b75c`  
**Verdict:** `REV3=REVIEWED_WITH_P1_FINDINGS`; `PART_A_FINAL_ACCEPTANCE=HOLD`; `PART_B=NOT_AUTHORIZED`; `NET01=HOLD`.  
**Production changes:** NONE. Tests below were run only against extracted offline package and disposable mocked commands; no real firewall, Docker or systemd units were modified.

## 1. Independently verified

- ZIP opened, 33 entries; `sha256sum -c MANIFEST.sha256`: **32/32 OK**.
- `pytest` original + REV3 fixture suites: **24 passed**.
- `tests/test_systemd_verify_offline.sh`: **PASS** in synthetic unit root, **not** real PID1/systemd lifecycle.
- Bash syntax + Python AST validation: **PASS**.
- Previously reported revisions exist: root-only `ExecStartPre=+`, watchdog `Type=notify`, one-way Flask `BindsTo=` / `After=` dependency, sticky HOLD and strict firewall-only rollback guard.
- Approved *architecture candidate* remains `NPM 172.18.0.2 → host Docker bridge 172.18.0.1:18089`; no production activation GO.

## 2. P1-01: unsafe status-command failure handling permits firewall rollback

**Evidence:** `firewall/net01-fw-rollback.sh` lines 12–21 use `if systemctl is-active --quiet ...; then` and `if ss ... | awk ... | grep ...; then`. Under Bash `set -euo pipefail`, a nonzero command in an `if` condition is treated as a false condition, not a fatal error. The code does not distinguish **verified inactive/no listener** from **systemctl/ss failure**. Lines 24–36 then permit the exact firewall-only check to authorize rule deletion.

**Independent reproduction, isolated command mocks (no host firewall mutations):**

```text
SCENARIO=systemctl_and_ss_errors  ROLLBACK_RC=0  MUTATION_COUNT=5
STDOUT=NET01_ROLLBACK=COMPLETED_FOR_EXACT_REVIEWED_RULESET
```

The `net01-verify.py --firewall-only` mock was deliberately PASS, modeling a syntactically intact firewall. `systemctl` and `ss` were mocked to fail. The script nevertheless invoked five firewall deletion commands. This is an incorrect fail-closed assertion, not merely missing test coverage.

**Required correction:** Explicitly validate that systemd is reachable and the relevant units are in an approved fully stopped state; explicitly validate successful `ss` execution and absence of **any** TCP 18089 listener; treat unknown/errors as HOLD. Retain exact firewall guard, owned-object deletion and limited rollback. New negative fixtures must prove zero mutations for failed/unreachable systemd, failed `ss`, and unknown service state.

## 3. P1-02: unsafe HOLD-clear and install precondition checks

**Evidence:** `firewall/net01-clear-hold-review-only.sh` lines 6–12 use the same false-condition check; a failed `systemctl` or `ss` can be interpreted as safe. An independent mocked test made both tools return an error and made the guard return PASS:

```text
SCENARIO=both_checks_fail  RC=0  HOLD_EXISTS=False
STDOUT=HOLD marker cleared after guard PASS; backend still STOPPED
```

**Evidence:** `firewall/net01-fw-install.sh` lines 18–22 use `if ss ... | awk ... | grep ...; then`. If `ss` fails, installation can continue even though the supposed no-listener prerequisite was *not* proven. Independent test with a failed `ss` and mocked successful guard/firewall commands yielded `INSTALL_WITH_SS_FAILURE_RC=0` and 5 firewall mutations.

**Required correction:** Share one conservative, testable listener/status probe across install, rollback and HOLD-clear; never equate a tool failure to `no listener` or `inactive`. For HOLD-clear, also verify watchdog state; verify manual recovery cannot clear HOLD while app/watchdog are starting or active.

## 4. P1-03: activating/start-job race not excluded by rollback gate

**Evidence:** `firewall/net01-fw-rollback.sh` only tests whether `systemctl is-active --quiet` is successful. It does not prove a quiescent unit, absence of a queued/ongoing start transaction, or mutual exclusion with `ExecStartPre` / watchdog startup. In mocked scenario where service status represents **activating** (nonzero `is-active`), no listener yet, and firewall posture is valid:

```text
SCENARIO=unit_activating  ROLLBACK_RC=0  MUTATION_COUNT=5
```

A concurrent startup can therefore race firewall deletion. Similar concern applies to clearing HOLD. Tests cannot rely solely on string matching `is-active`, or on a snapshot of no listening socket.

**Required correction:** Propose an explicit rollback/maintenance admission mechanism that prevents a new Flask/watchdog start while protection is removed. Stop/inhibit only *new* NET01 services, verify fully quiescent systemd state and no queued starts, then remove owned firewall rules. Align start/rollback coordination; prove with a real isolated PID1 test, and avoid modifying NPM/Omada/old Portal. If perfect prevention against privileged concurrent administrator is outside scope, define that trust boundary explicitly and ensure ordinary orchestration cannot race.

## 5. Items accepted in design, pending real staging

- `ExecStartPre=+` root-only check vs unprivileged `ExecStart`; Docker socket access denied to app identity: **NOT TESTED** under actual systemd.
- `Type=notify` readiness / Flask `BindsTo=` stop propagation on watchdog manual stop, crash, SIGKILL and guard drift: **NOT TESTED** under real PID1.
- `ExecStopPost` sticky HOLD / `OnFailure` emergency stop and listener removal: **NOT TESTED** under real PID1.
- Docker Compose recreation, identity guard, firewall enforcement, `INPUT` chain position, IPv6, negative network reachability, proxy headers: **NOT TESTED** on target.
- Accepted Git SHA implementing HOST/PORT and CAPPORT FQDN/Site for new controller: **PENDING**.

`24 tests passed` means those 24 fixtures passed; it does **not** contradict the additional negative cases independently reproduced here.

## 6. Required response: narrow REV4, offline only

1. Fix P1-01, P1-02 and P1-03 in the **offline package only**.
2. Add regression fixtures for failed `systemctl`, failed `ss`, unknown/activating/deactivating state, pending start job, and concurrent startup versus rollback/HOLD-clear.
3. Run the existing test suites and add independent negative fixtures ensuring **no firewall mutation**, **HOLD remains latched** and **no Flask bind** when safety preconditions are unknown.
4. Return full REV4 ZIP, SHA-256 manifest, changelog, offline test transcript and revised staging PID1 test plan; label untested results accurately.
5. Do not execute new firewall/systemd/Docker scripts on `captiv-prod` without a separate reviewed GO.

## 7. Decision

- `NET01_ROUTE_DESIGN=APPROVED`
- `REV3_PACKAGE_INTEGRITY=PASS`
- `REV3_EXISTING_OFFLINE_TESTS=PASS`
- `P1_OPEN=3` (command failure handling, sibling install/HOLD clearance, startup/rollback race)
- `PART_A_FINAL_ACCEPTANCE=HOLD_PENDING_REV4`
- `REAL_SYSTEMD_STAGING=REQUIRED_AFTER_OFFLINE_FIX`
- `PART_B=NOT_AUTHORIZED`
- `OWNER_GO=REQUIRED`
- `OLD_PRODUCTION=UNCHANGED` (as reported by SysAdmin; not independently inspected live for this review)

**Architect:** Captiv-Prod independent review. This is a review verdict, not an instruction to modify production.
