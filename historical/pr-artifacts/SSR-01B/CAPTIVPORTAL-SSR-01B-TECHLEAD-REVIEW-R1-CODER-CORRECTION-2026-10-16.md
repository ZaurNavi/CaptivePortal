# CAPTIVPORTAL — SSR-01B-1+2
## Tech Lead independent review R1 / focused correction directive

**Date:** 2026-10-16 (Asia/Baku)
**Verdict:** `RETURN_TO_CODER / P1 OPEN`  
**Production:** `OBSERVATION_FREEZE` — no install, restart, deployment, branch/commit/push/PR/merge authorization.
**Executor:** same Coder; **not** a new Architect round unless the permitted unit-only model proves inadequate.

### 1. Accepted evidence and identity (not final acceptance)

- Uploaded standalone patch **38,052 bytes**, SHA256 `e812fe08b5fedde1e06e7bb07dd9d4905ff72e7519805361920c53b5c10da4a8` — independently verified.
- Uploaded evidence ZIP passed CRC and all **252** SHA256 inventory checks. Standalone `HANDOFF.md` and patch match the ZIP versions byte for byte.
- Exactly five changed files, all within prior scope; changed-content Git blobs match the patch's `index ...` right-hand hashes. No changes to application, Core/Auth, NI-01, Evidence or Suricata YAML.
- Original Coder `BASE_HEAD=7e84bc563f1b6dd3d72da66ae25849d9a7d96540`, `BASE_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a` and uncommitted `CANDIDATE_TREE=58cc1c6ccdb2606345a7a469c68eae66ecd46f11` **independently reverified on WSL worktree** with a separate temporary `GIT_INDEX_FILE`; no persistent Git index/repo mutation. `git diff --cached --check=PASS` in review index.
- Coder JUnit proves **26 + 1 = 27 focused PASS**, failures/errors/skips zero, but *this did not cover the P1 case below*. Mock tests are not the official full/real-EVE/release gate.

### 2. P1 — normal successful restarts exhaust Suricata StartLimit

**ID:** `SSR01B-RV-P1-01`  
**Severity:** `P1`, breaks SSR-B01 normal `restart Sensor` return-to-service behavior.

The candidate adds `StartLimitBurst=3`, `StartLimitIntervalSec=600` to Suricata. systemd's unit start-rate limiter counts **successful** starts, not only failures. The existing positive test `test_systemd_249_positive_pid_matrix_and_no_unrelated_cascade` runs `systemctl reset-failed` between ordinary restart iterations. This resets the unit start-rate counters and **masks** the normal operational sequence.

**Independent non-production reproduction:** Owner laptop WSL Ubuntu 22.04, `systemd 249.11-0ubuntu3.22`, isolated disposable mock units, Sensor `Wants=Suricata`, Suricata `After+BindsTo+PartOf=Sensor`, `StartLimitBurst=3`, `StartLimitIntervalSec=600`, `RestartSec=30`. Both mock processes use harmless `sleep` and have no network, production credentials, EVE or capture. No `reset-failed` between restarts.

```text
COLD_SENSOR=active SUR=active
RESTART_1 SENSOR=active SUR=active RESULT=success
RESTART_2 SENSOR=active SUR=active RESULT=success
RESTART_3 SENSOR=active SUR=failed RESULT=start-limit-hit
RESTART_4 SENSOR=active SUR=failed RESULT=start-limit-hit
ssr01b-review-success-suricata.service: Start request repeated too quickly.
```

This is an architectural/safety contract failure **even though** the candidate's permanently-missing-socket retry test saturates correctly. More severe: it can leave TLS/QUIC capture unavailable after entirely successful planned Sensor restarts while Sensor/Core remain healthy, which normal mock startup checks might not detect.

### 3. Corrective instruction for Coder (focused R2, repo-only)

1. Keep approved local model: Sensor `Wants`, Suricata `After+BindsTo+PartOf`, non-sending live AF_UNIX/DGRAM check, dual maintenance holds, no new helper/service/module, no alterations to Core/NI/Evidence/app/Suricata YAML or production-installed units.
2. **First add a RED regression** using actual systemd 249: normal cold start followed by **at least three deliberate Sensor restarts inside one start-limit window**, *without `reset-failed` or artificial delay between successful starts*. Each restart must restore Suricata; Core/Evidence/NI mock process PIDs stay unchanged.
3. Add a mixed positive case: after this normal sequence, one Suricata-only crash must recover via its own `Restart=on-failure` without touching Sensor. Do not put `reset-failed` anywhere inside this positive operation sequence. Keep operator `reset-failed` testing **only** for deliberate recovery after terminal rate saturation.
4. Correct the rate-window policy so the above positive scenarios PASS *and* a **permanently missing socket** remains finitely bounded under slow failures and systemd 249. `StartLimit` limits total starts, not failures. Do not rename window-based limits as independent per-episode counters; explicitly document the tradeoff and legitimate-start budget.
5. **Tech Lead-approved R2 numeric candidate for testing only:** Suricata `StartLimitBurst=5` and `StartLimitIntervalSec=750`, retaining `T_socket=30s`, `TimeoutStartSec=90s`, `RestartSec=30s`, `StartLimitAction=none`. This allows four legitimate starts plus one Suricata-only recovery within the window and, conservatively, `5×90 + 5×30 = 600 < 750` bounds a permanently failing start sequence. **This is not accepted until the complete positive + slow-negative matrix passes.** If the case needs a different triple or reveals a conflict with B01/B02, report `HOLD` and escalate to Tech Lead before changing the contract again.
6. Update the focused unit tests, existing deployment runbook, timing table, and original exact-tree evidence to reflect the proven values. Preserve terminal saturation, stale-socket/permission errors, dual maintenance holds, NI-01 Wants attempt under hold, and explicit controlled resume. No weakening/removing previous assertions or tests. No fake EVE/health PASS.
7. Return a **full replacement R2 patch**, exact BASE_HEAD/TREE and new uncommitted CANDIDATE_TREE, patch SHA256, diff/check, focused JUnit/logs (including actual non-scaled systemd 249 repeated *successful* restarts and actual slow-failure saturation), evidence ZIP, and limitations. State prior P1 regression result and final result explicitly.

**Important operator note:** A finite unit start rate limit cannot promise an unlimited number of manual restarts in a fixed interval. The documentation must state the operational ceiling and the manual diagnostic/controlled resume procedure, without claiming arbitrary perpetual success. If the agreed SSR-B01 recovery semantics cannot be satisfied by an approved unit-only bounded mechanism, **do not invent a timer, app actuator, privileged helper or silent `reset-failed`**; return a precise `ARCHITECT_DECISION_NEEDED` blocker through Tech Lead.

### 4. Independent release and production gates unchanged

After R2 Tech Lead review, separate independent QA must validate real Sensor + Suricata 8.0.6 EVE datagrams, source-health gap/stale-to-usable contract, downstream Evidence durability, deployed nonprivileged socket permissions, Linux/cold-HDD-like PERF/Guest Auth latency, exact candidate TREE, and the current official Central Lab gate. If no real capture NIC, use only separately QA-approved faithful EVE equivalence and mark unproven AF_PACKET/production behavior. Neither the prior 27 PASS nor R2 focused tests authorize publication, merge or production installation.

### 5. Disposition

```text
TASK=TASK-SSR-01B-1+2
REVIEW=TECH_LEAD_INDEPENDENT_R1
BASE_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
CANDIDATE_TREE_R1=58cc1c6ccdb2606345a7a469c68eae66ecd46f11
R1_PACKAGE_INTEGRITY=PASS
R1_CODER_FOCUSED_JUNIT=27_PASS_CONFIRMED
P1=SSR01B-RV-P1-01_NORMAL_SUCCESSFUL_RESTARTS_EXHAUST_STARTLIMIT
R1_ACCEPTANCE=RETURN_TO_CODER
R2_REPO_ONLY_CORRECTION_GO=YES
R2_TEST_NUMERIC_CANDIDATE=30/90/30/5/750_CONDITIONAL
CODER_COMMIT_PUSH_PR=NO
PRODUCTION_TOUCH=NO
OWNER_NEXT_ACTION=PASS_THIS_R1_CORRECTION_DIRECTIVE_TO_CODER
```
