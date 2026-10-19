# CAPTIVPORTAL — TASK-SSR-01B-1+2
## Tech Lead implementation contract v1 — bounded local Sensor → Suricata reattachment

**Date:** 2026-10-16 (Asia/Baku)  
**Owner:** CaptivPortal Owner  
**Issuing role:** CaptivPortal Tech Lead  
**Executor:** Coder (repository-only implementation)  
**STATUS:** `FINAL / CODER_IMPLEMENTATION_GO=YES / REPOSITORY-PATCH-ONLY`. This GO is issued by Tech Lead after target-version systemd Lab confirmation. **Publication, merge, installed systemd and production remain HOLD.**  
**Execution mode:** `implementation` — exact allowed-file patch and focused tests, **NOT publish/deploy**.  
**Research boundary:** production observation freeze is ACTIVE; no installed-service edit/restart; no production replay, DB or network tests.  
**Repository:** `ZaurNavi/CaptivePortal`; observed production checkout `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`, TREE `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`. Recheck exact code in own worktree, do not silently target mixed HEADs.  
**Architectural authority:** `CAPTIVPORTAL-SSR-01-CHIEF-ARCHITECT-ADR-v1-FINAL-2026-10-15.md`; `CAPTIVPORTAL-SSR-01B-CHIEF-ARCHITECT-AMENDMENT-v1-FINAL-2026-10-15.md`; `CAPTIVPORTAL-SSR-01B-2-CHIEF-ARCHITECT-AMENDMENT-v1-FINAL-2026-10-15.md` (the latter supersedes only the expressly amended numerical/socket aspects). Follow `AGENTS.md`, `docs/agents/task-contract.md`, `docs/testing-environments.md`.

## 1. Owner-visible outcome and current state

Restore **Suricata locally** after a confirmed Sensor start, explicit Sensor restart, `stop → start`, or automatic Sensor recovery, but **only when a live EVE Unix datagram endpoint is connectable** and no maintenance inhibit is set. Keep Sensor, Core/Auth, Evidence, CAPPORT, NI, Omada and other workers independent. Suricata-only crash must not restart Sensor. A deliberate long-term hold must not be bypassed by NI-01 `Wants=Suricata` or Sensor reattachment. Failures are bounded, observable and cannot turn an unavailable TLS/QUIC source into false `usable`.

Observed **installed systemd 249.11-0ubuntu3.22** from Owner's sanitized read-only manifest (2026-10-15/16):

- Sensor: `Type=simple`, `Restart=on-failure`, `RestartSec=30`, `TimeoutStopSec=20`, effective `TimeoutStart=90s`, `StartLimitBurst=5/10s`, `After=captive-portal.service`; runs `/opt/captiveportal-runtime/device-fingerprint-venv/bin/python ...`; supplemental group `fingerprint-eve`; drop-ins `network-attribution.conf`, `zz-spool-recovery.conf` (env and credentials redacted appropriately).
- Suricata: `After+BindsTo+PartOf=fingerprint-sensor.service`, `Restart=on-failure`, `RestartSec=30`, effective `TimeoutStart=90s`, `StartLimitBurst=5/10s`, five `ExecStartPre` steps including `timeout 1830 ... test -S ...`, version test 8.0.6, `suricata -T`; `ExecStart=/usr/bin/suricata ... --af-packet=enp8s0 --runmode=workers`; `User=suricata`, `SupplementaryGroups=fingerprint-eve`; no drop-ins listed.
- NI-01 (`network-metadata`): `Wants+After=fingerprint-suricata.service`; **NOT** an excuse to edit NI-01. It may independently enqueue Suricata during maintenance, so both holds must work through this existing path.
- Installed Sensor `ExecStart` differs from repo service template (venv runtime vs `/usr/bin/python3`): **no unrelated fix or adjustment** in this TASK. Do not copy/reconcile environment values from production to repo.
- Owner's read-only history query had no matching lines; *lack of journal results is not proof of absence of failures*. Repo Sensor/Suricata unit template blobs were identical between architect review `84b80376...` and observed checkout `7e84bc56...` when checked by Tech Lead.

## 2. Architecture decisions and exact allowed scope

**Allowed production source files ONLY:**

1. `deploy/device-fingerprint/fingerprint-sensor.service` — soft `Wants=fingerprint-suricata.service`, one pair-wide volatile `/run` maintenance condition. Do **not** change Sensor `Restart`, startup timeout, start limit, `ExecStart`, Python runtime, quotas or other core settings.
2. `deploy/device-fingerprint/fingerprint-suricata.service` — retain original `After+BindsTo+PartOf=Sensor`; pair-wide and Suricata-only conditions; replace stale-vulnerable `test -S` wait with bounded, non-sending `AF_UNIX/SOCK_DGRAM connect()` probe inside existing `ExecStartPre` using available Python standard library; bounded startup/retry/start-limit policy per §3.

**Additional allowed files:** directly related reproducible tests/fixtures in `tests/device_fingerprint_sensor/` (new `test_ssr01b_systemd_contract.py` permitted; optional adjacent fixture under this test directory), and a *narrow* SSR-01B maintenance/rollback section in existing `docs/deployment.md`. No unrelated tests or docs. A focused test must not require production privilege/network/capture NIC.

**Disallowed:** new production Python module, helper-file, unit/service/timer/path/daemon/poller, application lifecycle change, automatic `systemctl` from Sensor code, root/polkit/D-Bus escalation, `Upholds=`, global coordinator, edits to `network-metadata`, other NI, Core/Auth, Omada, CAPPORT, EVE API, SQLite/spool, Suricata YAML, AF_PACKET/BPF/capture interface, secrets, VLAN or resource quotas. If essential, STOP and return to Tech Lead for architect review.

## 3. Tech Lead proposed numerical candidate and evidence

**Tech Lead approved values **for a repository candidate patch and focused validation only**, not production deployment. Physical-HDD adequacy still requires independent PERF/release testing.**

| Parameter | Repository candidate value | Evidence/constraint |
|---|---:|---|
| `T_socket` (live non-sending datagram connect wait) | **30s maximum** | Installed start evidence: Sensor process recorded 15:35:52, Suricata socket preflight passed at 15:36:03 (ready by ~11 seconds on that occasion; **not a measured cold-boot percentile**). WSL delayed socket mock ready after 3s and recovered. Set 30s for conservative candidate, not claimed optimal. |
| `T_other_preflight` **budget allowance** | **20s** | Production recorded `suricata -T` from 15:36:04 to 15:36:04 at whole-second timestamp resolution. Lab 8.0.6 `-T` 20 quiet / 20 synthetic-fsync-loaded samples with maxima 0.5793s / 0.5735s. Reserve 20s for the complete remaining preflight chain + process startup, not just `-T`. |
| `T_start_total` (`TimeoutStartSec`) | **90s** (existing effective setting, make explicit only if needed) | `30 + 20 + 30 safety headroom = 80s < 90s`. Any end-to-end test overrunning this is FAIL, not a reason to ignore it. |
| `T_restart` (`RestartSec`) | **30s** (preserve) | Installed current policy; prevents fast retry storm. |
| `N_attempts` (`StartLimitBurst`) | **3** | Scaled target-systemd tests demonstrated finite terminal state; use a small number of tries per failure episode. |
| `StartLimitIntervalSec` | **600s** | `3×90 + 3×30 = 360s < 600s` through the rejected fourth start job; 330s through completion of the third attempt. Window covers the entire terminal episode. Existing `5/10s` cannot bound 30s-spaced failures. |
| `StartLimitAction` | **none** | Never shutdown/reboot/affect Auth due to capture dependency failure. |

**Evidence limitations:** WSL 22.04 virtual disk != physical production HDD. 80 measured isolated Docker/Suricata 8.0.6 runs were successful, including 40 runs under synthetic 4-KiB/fsync contention. Config test worst-case 0.5793s quiet/0.5735s synthetic; offline PCAP/EVE worst-case 0.8532s/0.8598s. These figures **do not establish production P95/P99, full cold boot, actual YAML validation time, or physical HDD overload safety**. The proposal is deliberately conservative and requires independent cold/slow environment acceptance on the **exact candidate tree** before publication/deployment. If exact integrated tests invalidate any figure, Tech Lead must approve revised numbers and rerun the evidence before acceptance. Do not quietly change them.

Recovery episode observable start: actual systemd start transaction initiated by boot, operator resume/restart or Sensor restart; successful end: Suricata starts after live socket preflight; unsuccessful end: Suricata remains `failed`/`unavailable` at rate limit and no autonomous retries. Automatic Sensor restarts **must not** use `reset-failed` or evade consumed rate limit. Operator deliberately resumes only after checking reason, via `reset-failed` and controlled start. Do not claim a late socket automatically restarts a rate-limited Suricata.

## 4. Socket and fail-closed semantics

- Existing `test -S` pathname check is **inadequate**: a stale inode passes without a live receiving socket. Probe with `socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM).connect(path)` **without sending bytes**. Probe from Suricata's existing nonprivileged identity; respect current protected socket directory and `fingerprint-eve` group. Test `ENOENT`, `ECONNREFUSED`, `EACCES`, wrong type, malformed path, stale inode and successful live datagram socket.
- Use bounded retries *within 30s*, with finite polling delay and Python standard library only; unit-level inline `ExecStartPre`, no checked-in production helper script. Avoid unsafe quoting and leaking payloads/credentials to journald. Verify exact systemd 249 parsing (`systemd-analyze verify`).
- `connect` means kernel listener bound at that moment. It **does not** attest PID/cryptographic ownership, downstream processing or EVE health. Sensor process relationship + protected path is additional independent protection. Validate protected directory mode/ownership with sanitized lab verification; if unprivileged unauthorized binder can spoof listener, HOLD and report.
- Suricata producer may stay `active` while EVE delivery fails (real lab PCAP with receiver closed: 297 drops logged, exit code 0). Do not change source-health semantics: after crash/outage mark unavailable/stale; only real source heartbeats/stats prove `usable`, not service active or successful probe. No simulated EVE frame may be sent as a readiness test.

## 5. Two maintenance inhibits — mandatory

Suggested root-controlled volatile file paths for candidate runbook (keep consistent across code, tests and operator docs):

```
/run/ssr01b-fingerprint-pair-maintenance.hold
/run/ssr01b-fingerprint-suricata-maintenance.hold
```

- Sensor `ConditionPathExists=!/run/ssr01b-fingerprint-pair-maintenance.hold`.
- Suricata `ConditionPathExists=!` for **both** paths.
- Pair maintenance: operator creates pair hold **first**, then stops pair; future NI-01 `Wants=Suricata` / `Suricata BindsTo=Sensor` must not start either. Suricata-only maintenance: create its hold first, stop Suricata; Sensor remains healthy; NI-01 or Sensor restart must not resurrect Suricata. A bare `stop Suricata` without hold is not long-term protection.
- Resume: remove intended hold explicitly, `reset-failed` if needed, start only necessary unit/pair, check EVE source-health independently. Document diagnosis and rollback; no auto clears; holds are volatile and lost at reboot; must **not** claim safe across host power failure. `ConditionPathExists` skips start job; it does not itself stop active service.
- Lab must include `NI-01 Wants` start under both holds, existing active NI, Sensor re-start after Suricata-only hold, explicit Sensor start after pair hold and operator resume. Require distinct `Condition...skipped` versus socket failure status/journal.

## 6. Coder focused acceptance and required handoff

Coder runs **focused TASK/module tests only**. Tests must be deterministic, not touch production systems, and avoid unrestricted test runs. Required:

1. `systemd-analyze verify` of emitted/sandboxed unit files on Ubuntu 22.04 **systemd 249.11-0ubuntu3.22** (outside production), plus command parsing/quoting test and `git diff --check`.
2. Positive simulated job matrix: enabled-boot-equivalent start, Sensor explicit restart, Sensor `stop → explicit start`, Sensor `SIGKILL → auto-recovery`, Suricata-only `SIGKILL → on-failure restart`; verify PID transitions and Core/NI/Evidence process identity untouched.
3. Negative: Sensor active before socket bind; live but delayed socket; stale inode; no socket beyond 30s; Unix socket permission deny; bad Suricata preflight/config; receiver dies just after `connect` (must not assert healthy); repeated near-timeout failures; start-limit saturation; incoming Sensor restart under saturation (no bypass); manual `reset-failed`/controlled resume.
4. Two holds from §5 under NI-01 pull-in, intentional stop, reboot reset semantics, interleaved restart, no uncontrolled reattach; independently report source availability/gap (no fake `usable`).
5. Recovery timing table containing start-attempt timestamps, per-attempt wait, retries and final budget; bound for missing socket must be finite with up to `3×90+3×30≤360s` through the denied fourth job (330s through end of third failed attempt), and the window of 600s. Do not confuse window with lifetime quota. Include soft dependency no Core cascade.
6. Test file names, command output, exact SHA/tree, `git diff`, `git diff --check`, changed file manifest, reproducible fixture and negative evidence. No secrets. Self-check only; no broad regression.

**Stop conditions:** inability to prove finite rate window on target systemd; unexpected NI/Core/Omada coupling; no safely bounded connect under `suricata` identity; unauthorized socket bind; new helper code/module needed; untenable numerical budget; any other change beyond listed files. State exact blocker; do **not** invent alternative architecture.

## 7. Independent acceptance, release and production boundary

Coder hands **patch only** to Tech Lead. No publication/commit/push/PR unless subsequent separately authorized acceptance/publish stage. Tech Lead reviews exact diff and target tests, defines acceptance candidate and checks proof of source-health/gap; independent Research/QA Lead validates negative tests, EVE equivalence/heartbeat/staleness, source durability and fail-open independence.

Official Central Lab / Linux integration + realistic cold/slow-storage PERF on exact candidate are **mandatory before publication**, including actual Sensor→Suricata 8.0.6 EVE datagrams, heartbeat and health, producer/receiver drop/outage, bounded backlog, restart gap, guest-auth responsiveness, absence of cascade and no unexpected durable data modification. Where real AF_PACKET capture NIC cannot be safely reproduced, independent QA-approved faithful EVE fixture equivalence must be obtained, with real-capture semantics marked `UNPROVEN` and **production activation HOLD** until separately authorized validation.

Owner controls official Windows Central Lab run (`C:\CaptivPortal-Lab`, current strict V7 when applicable), publication/merge and production deployment GO. `192.168.0.202` is not a testing environment. No production installed unit/drop-in changes, restart, socket/network action, capture-affecting action or release during this TASK. Separate SysAdmin deploy/rollback/acceptance after observation freeze.

**Required machine handoff fields:**

```
TASK=TASK-SSR-01B-1+2
MODE=implementation
CODER_FOCUSED_TEST_RESPONSIBILITY=agent
BASE_HEAD=<sha>
BASE_TREE=<tree>
FILES_CHANGED=<exact paths>
PATCH=<artifact path>
DIFF_CHECK=<PASS|FAIL>
SYSTEMD_249_MATRIX=<PASS|FAIL and evidence>
NEGATIVE_GATES=<PASS|FAIL and evidence>
BUDGET_30_90_30_3_600=<PASS|FAIL and evidence>
SOURCE_HEALTH_GATE=<what tested/what unproven>
RELEASE_ACCEPTANCE=NOT_RUN_BY_CODER
PRODUCTION_TOUCH=NO
COMMIT_PUSH_PR=NO
NEXT=TECH_LEAD_REVIEW
```

## 8. Gate ledger and signed pre-code admission (Tech Lead; pre-code versus post-code)

| Gate | Assessment | Boundary |
|---|---|---|
| G0 installed version/graph/diffs, Owner sanitized `systemctl cat/show` | **PASS for unit/dependency and redacted path manifest** | No secret contents printed; actual loaded process artifact identity not attested. |
| SSR-R05 systemd 249 semantics / recovery / hold / simple unix-datagram negative behavior | **PASS for pre-code mechanism** | Scoped mocks and actual Suricata 8.0.6 isolated PCAP/EVE, not full installed pipeline. |
| G0 source protection (directory permission / unprivileged bind spoofing) | **STRUCTURAL PASS / deployed FS attestation deferred to independent acceptance** | Repo `EveReceiver.open()` applies parent mode `0750`, group `fingerprint-eve` and socket `0660`; negative unprivileged group/permission and stale connect cases lab-tested. Verify effective deployed filesystem path before deployment, not by assumption. |
| Recovery candidate 30/90/30/3/600 | **PASS for bounded retry mechanism on target systemd 249; APPROVED FOR CODER PATCH ONLY** | Actual `RestartSec=30s`, `TimeoutStartSec=90s`, `StartLimitBurst=3`, `StartLimitIntervalSec=600s` fixture: three failed starts at 01:02:22, 01:02:52, 01:03:22 +04; fourth denied at 01:03:52 (`Start request repeated too quickly`); Sensor `active`, Suricata `failed`. `T_socket=30s`, real preflight headroom and production-HDD behavior still mandatory before release. |
| G1/G3 real Sensor↔Suricata EVE heartbeat/source-health + HDD-like PERF | **POST-CODE GATES HOLD** | Existing tests cover Suricata 8.0.6 offline EVE and WSL fsync contention only. |
| Independent QA, exact candidate Central Lab, publication | **NOT AUTHORIZED YET** | After Coder deliverable; Owner and QA actions. |
| Production change / deployment | **NO / FROZEN** | Separate Owner/SysAdmin GO. |

## 9. Tech Lead exact admission disposition, 2026-10-16

```text
TASK=TASK-SSR-01B-1+2
ARCHITECTURE=SSR-01B_v1_FINAL+SSR-01B-2_v1_FINAL
OWNER_PRODUCTION_FREEZE=YES
G0_INSTALLED_LIFECYCLE_MANIFEST=PASS_SANITIZED
SYSTEMD_TARGET=249.11-0ubuntu3.22
SSR_R05_LOCAL_SYSTEMD_MECHANISM=PASS_FOR_PRE_CODE
LIVE_UNIX_DGRAM_PROBE=PASS_FOR_LAB_THREAT_MODEL
FINITELY_BOUNDED_RESTART_POLICY=PASS_TARGET_SYSTEMD
CODER_ALLOWED_BASE=OBSERVED_HEAD_7e84bc563f1b6dd3d72da66ae25849d9a7d96540_TREE_ea664b1d49ace86fc8a0c4ab2fc52945531e574a_VERIFY_BEFORE_EDIT
CODER_IMPLEMENTATION_GO=YES_REPO_PATCH_AND_FOCUSED_TESTS_ONLY
CODER_COMMIT=NO
CODER_PUSH=NO
CODER_PR=NO
RELEASE_GATE=HOLD_PENDING_INDEPENDENT_QA_EXACT_TREE_LINUX_EVE_SOURCE_HEALTH_PERF_CENTRAL_LAB
ACTUAL_PRODUCTION_HDD_BUDGET_ATTESTED=NO
OWNER_MERGE=NO
PRODUCTION_INSTALLED_UNITS_CHANGE=NO
PRODUCTION_RESTART=NO
NEXT=CODER_PATCH_TO_TECH_LEAD_REVIEW
```

**Admission principle:** granting narrow repo-only implementation does NOT mean that the production readiness, source-health, real HDD cold-boot or official release gates passed. Those remain mandatory before publication or any installation. If focused Coder test disproves the finite limit/30s socket envelope or a new unapproved component is needed, the patch is HOLD and returns to Tech Lead without unapproved scope expansion.
