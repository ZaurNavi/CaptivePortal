# CAPTIVPORTAL — QIO-01A Tech Lead Coder TASK v1.0 + историческая проверка HDD I/O

**Дата:** 2026-10-15 (Asia/Baku)  
**Роль:** Technical Lead for Performance Optimization  
**Статус реализации:** **IMPLEMENTATION TASK ISSUED; CODER IMPLEMENTATION MAY START IN ISOLATED LAB; PUBLICATION/PRODUCTION HOLD**.  
**Два независимых результата документа:** (I) однозначное задание Coder **только QIO-01A**; (II) read-only ретроспектива 23.08–06.09.2026 **без расширения реализации QIO-01A**.

## I. QIO-01A — Implementation contract for Coder

### 1. Источники и baseline

1. Architecture authority: `CAPTIVPORTAL-QIO-01A-ARCHITECTURE-DISPOSITION-A1-A4-v1.0-2026-10-15.md` — **A1–A4 APPROVED**.
2. Root cause: `CAPTIVPORTAL-QIO-01-JOURNALING-ROOT-CAUSE-ARCHITECTURE-HANDOFF-v1.0-2026-10-15.md`.
3. Repository governance: `AGENTS.md`, `docs/agents/task-contract.md`, `docs/testing-environments.md`, `docs/agents/handoff.md` at pinned source.

**Baseline for implementation:** GitHub `main@7e84bc563f1b6dd3d72da66ae25849d9a7d96540`, tree `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`. Verified GitHub branch 15.10.2026. Production checkout independently observed `84b80376b13002d435be28eec98b91b9cbf71c63`; **not same as main**. Verified blob identities of `worker.py`, `runtime.py`, `submitter.py` match between those two commits; long-lived process loaded SHA not proven. If baseline advances before work begins, **STOP and request re-pin/diff assessment**, do not silently switch.

**Execution mode:** `implementation` on isolated Coder/Lab checkout. **Task-scoped test responsibility:** `agent` (focused tests only). **Repository actions permitted:** local worktree changes and local patch/diff handoff only; **no** branch publication, remote push, PR, merge, reset of production, service restarts, or deployment. Owner/Tech Lead conduct official gates separately.

### 2. Goal and exact behavioral change

Reduce the repeated `fingerprint.integration_worker_health` with `reason_code=ready`, which current `IntegrationWorker.run()` emits around once per second in healthy idle operation. Target behavior: publish `ready` **immediately** after the first successful **lock-owned bounded cycle** and upon every recovery, then no more than approximately one unchanged `ready` per 60 monotonic seconds (on the first successful cycle at/after deadline). This optimization is for **event count**, not a promised HDD write percentage.

**Critical correctness defect to repair within scope:** current `run_once() -> bool` returns `False` both when no work was due (valid ready) and when `consumer_lock` was unavailable (not ready). `run()` must not infer lock ownership from that activity boolean.

### 3. Allowed code and design envelope

**Allowed:** `app/device_fingerprint_integration/worker.py` plus strictly necessary focused tests in `tests/device_fingerprint_integration/` (prefer one new `test_worker_health.py`, or targeted extension without disturbing existing tests). No other code/docs changes without Tech Lead approval of exact additional path.

- Preserve **public `run_once() -> bool` activity semantics**: `False` on owned idle and on lock miss; `True` when claimed job and/or identity job. Preserve public constructor/use of `IntegrationWorker` and `stop()` semantics.
- Implement a **private, invocation-local** ownership/completion outcome (`OWNED_COMPLETED`, `LOCK_MISSED`; exception remains exception) so successful owned idle is distinguishable from lock miss without mutating public return. Suggested implementation is one private internal cycle function returning `(activity_bool, owned_success_bool)` and a thin public `run_once()` adapter; alternatives acceptable if equivalently proven race-free and stale-outcome-safe. Avoid a mutable, shared `_last_outcome` susceptible to concurrent direct `run_once()` calls unless appropriately proven protected. Mocked/stubbed `run_once()` return values must not by themselves invent ownership.
- Successful owned cycle includes handled/durably recorded classification retry or no-result; **domain failures already handled by the normal pipeline do not automatically imply infrastructure unavailable**.
- `run()` health logic: initial/startup unknown → owned success emits `ready` immediately; steady owned success → suppress `ready` until elapsed monotonic >=60s; lock miss → emit `consumer_lock_unavailable` **every miss**; any unhandled exception → emit `integration_unavailable` **every failure**; first successful owned cycle after either non-ready status → emit `ready` immediately and reset heartbeat deadline. On stop/crash no synthetic ready/failure; keep `stop_event.wait(1)` cadence.
- Use `time.monotonic()` for cadence, testable deterministically via private clock injection/patch without changing public constructor; guard against backward clock jump producing premature/misleading heartbeat. Do not interrupt long job to emit a heartbeat: actual wall-clock log gap may exceed 60s.
- No telemetry envelope change: `{"event":"fingerprint.integration_worker_health","reason_code":"ready|consumer_lock_unavailable|integration_unavailable"}` for loop-level events; no new JSON keys/timestamps/counters/fields, no changes to `submitter.emit` or allowlist. Existing separate `lease_lost` with `integration_id` is untouched.
- Every failure/lock miss/domain warning is immediately emitted; **no failure dedup** or global INFO suppression. Keep all `classification_started`, `classification_succeeded`, `classification_no_result`, `classification_retry`, `integration_identity_*`, `lease_lost` and submitter-side `integration_unavailable` unchanged.
- No changes to SQLite, DB schema, claim/lease/retries/identity, transaction boundaries, lock acquisition protocol, controller/OpenAPI, service units, log collectors, TLS, MicroK8s, audit, or security. No new dependency or durable health store.

**Health outcomes:**

| Previous | Cycle outcome | Emission |
|---|---|---|
| unknown/new worker | lock-owned complete | `ready` immediately |
| steady ready, <60s | lock-owned complete | none |
| steady ready, >=60s | lock-owned complete | `ready` once |
| any | lock not acquired | `consumer_lock_unavailable` immediately for each miss |
| any | unhandled infrastructure exception | `integration_unavailable` immediately for each failure |
| any non-ready | later lock-owned complete | `ready` immediately; start new 60s deadline |

### 4. Mandatory focused tests — Coder responsibility

- Legacy `run_once()` bool semantics: idle/lock miss/job/identity due. Positive ready requires ownership, **not** bool. Include simultaneous/direct invocations or another proven no-stale-outcome case.
- Fake monotonic time: t=0 first owned success, 1-second idle loops; t=59.999 none, t=60 and t=60.001 exactly bounded; large forward jump emits one; backward jump not falsely due; another monotonic interval eligible after prior heartbeat. Avoid sleeps and dependence on actual wall clock.
- New process instance/restart: ready on first owned success independent of old deadline; initial lock miss emits non-ready.
- Lock miss immediately after ready, repeated misses every cycle, recovery after misses, lock held by another legal consumer does **not** imply global pipeline failure.
- Unhandled exception before first success, after ready, repeated same/different exceptions **every iteration**, immediate recovery and no false ready; `stop()` exits without fabricated ready.
- Handled retry/no-result + lease_lost + classification and identity events retain order, domain fields and count. Check no altered SQLite/durable state or interval logic.
- JSON schema remains minimal and sanitization unaffected, no accidental optional-field injection.
- Existing tests in `tests/device_fingerprint_integration/` pass; Coder runs only minimal task-scoped module tests, **not** full/cross-module suite. `git diff --check` mandatory.

### 5. Mandatory acceptance and ownership

| Gate | Operator | Before normal publication? | Criterion |
|---|---|---:|---|
| Scoped source/diff + invariant review | Tech Lead | Yes | Only allowlist, no domain change, transition table matches |
| Coder focused tests | Coder | Yes | Strict PASS, deterministic no-clock-sleep cases |
| Independent Linux concurrency and service lifecycle tests | Owner/Tech Lead using dedicated WSL Ubuntu-22.04 Lab | Yes | No fake ready, lock miss, recovery, exception; exact candidate tree |
| Windows Central Lab full strict V7 | Owner physical operator; Owner+Tech Lead verdict | Yes | Exact candidate tree, runner `C:\CaptivPortal-Lab\lab-test-v7-strict.cmd`, checksum verify, PASS |
| Linux/PERF matched measurements (log rate, journald I/O, service outcomes) | Owner/Tech Lead in isolated production-compatible Lab | Yes | Comparable idle/normal windows, functional evidence, no regression, causal attribution; if not possible, PENDING |
| Physical `/dev/sda` HDD impact measurement | Owner/Tech Lead, approved isolated equivalent HDD test before publication if feasible; actual production only under separate Owner GO | To claim **HDD performance PASS** | Matched host completed write IOPS/await/busy/cgroup evidence; cannot infer from fewer events |
| Git publication, PR and merge | Separate Owner authorization / Tech Lead gate | After all designated prepublication gates | Exact accepted candidate tree chain-of-custody |
| Production deploy and activation | Separate Owner approval | Separate step | Verified Git SHA, backup, health, rollback; no QIO-01A automatic GO |

**Gate feasibility note:** The existing WSL Lab may not reproduce mechanical `/dev/sda` characteristics. A WSL log-count reduction is not proof of real host HDD improvement. Do not secretly substitute post-production evidence for a mandatory pre-publication gate. If suitable mechanical-disk isolated test is absent, report the physical-HDD performance gate as **PENDING / NOT PROVEN** and obtain Owner/Tech Lead disposition of rollout/validation sequencing **before publication**; do not claim QIO-01A performance PASS.

**Rollback:** revert narrowly the worker health cadence/ownership logic via an independently accepted Git revision; no data/schema rollback or journal truncation. Confirm old event behavior would recur and source audit is preserved.

**Coder handoff required:** exact pinned source SHA/tree, changed files and full diff, unit tests and results, private outcome design rationale, unchanged source/retry/identity paths, no unexpected data writes, Windows/WSL/PERF gates `PENDING` unless genuinely executed by their operator, publication status `NOT AUTHORIZED`, production `UNTOUCHED`.

---

## II. Historical HDD I/O onset correlation — read-only investigation

### 6. User observation, scope and evidence levels

Owner reports that a coarse-scale **PRTG historical disk-load graph** shows **persistently elevated disk load already by 2026-09-01**, probably beginning several days earlier (approximately **2026-08-28/29**, but onset date is not resolved from that graph). This is an **Owner observation**, not a PRTG raw time-series export independently verified here. PRTG itself is SNMP/system monitoring and, per Owner, does not consume CaptivPortal health events; **this does not mean that PRTG's own data collection creates zero writes**. Distinguish measured `% disk busy`, latency, writes/s, and bytes/s rather than treating the graphical height as a single physical metric.

**Evidence sources collected 15.10.2026:**
- GitHub commits and merged PRs for `ZaurNavi/CaptivePortal` from Aug 20 to Sep 6 (commit timestamps in UTC). Source links below.
- Production `/opt/CaptivePortal` `git reflog --date=iso` for 26 Aug–6 Sep (timezone +04): **actual repository checkout/merge events**, though not proof that every process restarted with those bits at that moment.
- Production file **birth times** via read-only `stat` and current deployed code.
- QIO-01/QUIET-01 independent cgroup and journald measurements from 15 Oct; **these were not measured in August**, so no attribution of August disk IOPS is claimed.

### 7. Chronology: git vs production evidence

| Local date (+04) | GitHub change | Evidence of activation / significance | Evaluation |
|---|---|---|---|
| Aug 23 | PR #58, `feat(current-state): add network state foundation` — client and AP polling workers, own SQLite store | `/opt/CaptivePortal/data/current_state.sqlite3` birth **2026-08-23 17:24:06 +04**. In current-state source default polling **60s clients + 60s APs**; both publish cycles into SQLite, including zero-change cycles. | **Strong temporal/always-on candidate**; time of DB birth is not an IOPS change-point. |
| Aug 24 | PRs #59–61: Home Live and Home Traffic; current traffic read foundation | `public_traffic.sqlite3` birth **2026-07-29 12:10:20 +04**: the DB existed before this window. Admin UI adds reads; a panel itself is not a 24/7 disk writer without additional periodic activity. | Possible read amplification, not evidence of new continuous heavy writes. |
| Aug 26–27 | PRs #67, #74 and fixes: Home Activity, Home Health, Current State/Visit fixes | Production reflog records updates on **Aug 26** and **Aug 27**; timing overlaps the coarse pre-Sep1 onset. | Need per-writer idle baseline; code fixes may change contention but no causal proof. |
| Aug 28 | PRs #78/#81: AP 24-hour history and AP-24H operational telemetry | Production reflog shows several `origin/main` merges/checkouts **Aug 28 ~15:47–19:34**; in source AP-24H telemetry worker default **120-second** cadence and app telemetry output (not large dedicated DB writer). | **Strong date candidate**, weaker standalone explanation for 80+ physical writes/s. |
| Aug 29 | PRs #83/#84/#87: Traffic UI, throughput panel, history panel | Production reflog checkout **Aug 29 16:52**. Most features here introduce UI/read paths; potentially costly when queried but not automatically continuous idle writes. | **Date fits**, but not first-choice source of *steady 24/7* writes alone. |
| Aug 30 | PRs #89/#91: traffic period statistics and peak load | Production reflog updates **Aug 30 01:21 and 14:47**. | Need distinguish read execution by dashboards from autonomous writer. |
| Aug 31 | PR #93: traffic by AP | Production reflog checks out merge on **Aug 31 23:05**. | Scope primarily presentation/read. |
| Sep 1 | PRs #94–#96: independent traffic time ranges, AP share; docs #97 | Production reflog checkouts **Sep 1 10:05 and 21:12**. Owner says load already high **by Sep 1**. | These commits cannot explain a change that was already observable *several days earlier*. |
| Sep 4–5 | PR #101 introduces separate Traffic Projection engine | `/etc/systemd/system/traffic-projection.service` birth **Sep 5 00:39 +04**. | This standalone service **cannot be cause of onset before Sep 1** (can add later load). |
| Oct 4 | Classification worker service | `/etc/systemd/system/fingerprint-classification.service` birth **Oct 4 01:06 +04**. | Present-day QIO-01A source cannot be cause of Aug onset. |
| Oct 9 | Network metadata projection unit | `/etc/systemd/system/network-metadata-projection.service` birth **Oct 9 12:59 +04**. | Not original late-Aug cause in current installation. |

**GitHub links:** [PR #58](https://github.com/ZaurNavi/CaptivePortal/pull/58), [PR #59](https://github.com/ZaurNavi/CaptivePortal/pull/59), [PR #61](https://github.com/ZaurNavi/CaptivePortal/pull/61), [PR #67](https://github.com/ZaurNavi/CaptivePortal/pull/67), [PR #74](https://github.com/ZaurNavi/CaptivePortal/pull/74), [PR #78](https://github.com/ZaurNavi/CaptivePortal/pull/78), [PR #81](https://github.com/ZaurNavi/CaptivePortal/pull/81), [PR #83](https://github.com/ZaurNavi/CaptivePortal/pull/83), [PR #87](https://github.com/ZaurNavi/CaptivePortal/pull/87), [PR #89](https://github.com/ZaurNavi/CaptivePortal/pull/89), [PR #101](https://github.com/ZaurNavi/CaptivePortal/pull/101).

### 8. Confirmed mechanical path in Current State

At both the late-Aug source and checked current code: 

```text
CurrentClientWorker._run() / CurrentApWorker._run()
    -> fixed-delay poll_inventory()
    -> CurrentStateRepository.publish_cycle()
    -> BEGIN IMMEDIATE
    -> INSERT current_state_cycles (each cycle)
    -> optional INSERT current_client_state/current_ap_state
    -> COMMIT
```

This creates durable writes for **each completed poll cycle even if there is no change in the actual guest population**. **However**: two default 60-second cycles do **not** imply ~80 physical host IOPS; SQLite journal/WAL and other writers can amplify operations, but the actual per-file `fdatasync` and physical counts still require measurement. Current State is a plausible **timing-origin candidate**, not a quantified dominant physical writer.

The AP-24H telemetry addition (Aug 28) is also a plausible always-on event/file-log addition but at default 120s it is unlikely to explain a large sustained host-write baseline on its own. Traffic dashboards published Aug 29–Sep 1 should not be blamed for 24/7 writes just because their changes are temporally adjacent; prove a periodic background writer or continuously open dashboard refresh first.

### 9. Important alternative causes and present-day evidence

- On 15 Oct QUIET-01 host `/dev/sda`: **9,742 completed writes/120s (~81.2/s)**. Within Ubuntu guest, `systemd-journald` **1,982 guest block writes/120s**, portal process **1,282**, several other services including MicroK8s. Guest vs host accounting cannot be added or mapped 1:1. These values show **multiple sustained current writers**, not an Aug 28 root cause.
- MicroK8s `containerd` active since 2026-09-14 on current VM and currently has Calico CrashLoop. This timestamp is **the observed service activation**, **not validated initial installation**; do not use it to prove MicroK8s absent in August. Do not stop MicroK8s in this investigation.
- PRTG and its RRD writes, Windows VM I/O, rsyslog, host journald, Omada polling, and existing public-traffic/visitor storage are other contributors. Owner says PRTG is not integrated with Portal; nevertheless system-monitoring storage must be accounted separately.
- Existing journal on the inspected Ubuntu does **not** retain August: currently exposed `journalctl --list-boots` entries begin **Oct 2**; therefore no claim is made to have reconstructed Aug/Sept service log traffic from journald.

### 10. Ranked hypotheses and next falsifiable checks — **not part of QIO-01A Coder TASK**

1. **H1 / temporal priority:** 23–28 Aug activation of Current State poller (clients/AP), durable cycle/snapshot writes; Aug 28 additional AP-24H telemetry. Verify actual interval, no-op commit behaviour and current per-DB write/fsync counts in QIO-02/QIO-01D. Evidence supporting: source code + Aug23 DB birth + reflog. Counter-evidence to dominant-I/O claim: 2 default cycles/min cannot explain hundreds/thousands of guest writes per 120s by themselves without measured amplification.
2. **H2 / steady idle background:** pre-existing Portal/Omada/Visit/Registry/Public Traffic polls and logs possibly reconfigured/activated between Aug 25–29. Need matched physical cgroup/DB traces and exact historical service config; not proven by Git history alone.
3. **H3 / system side:** persistent journald, host RRD, MicroK8s and crash/retries, QEMU batching/checkpoints. At 15 Oct independently substantial. Need actual installation/start chronology and per-layer attribution; do not assume Calico crash started Aug.
4. **H4 / UI traffic modules:** historical/report pages cause read amplification only when actively queried, or where a separate service runs. Given apparently flat 24/7 load, lower-ranked unless dashboard auto-refresh/crawler demonstrated.

**Most decisive missing evidence:** raw PRTG sensor data (sensor identity, *metric*—disk busy/IOPS/latency/throughput, sampling/resolution, timestamp of step change, baseline before/after) around Aug 20–Sep 5. Its presence could distinguish abrupt change Aug 23, Aug 28, Aug 29 or Sep 1. No authenticated PRTG archive/API export was accessed; Owner observation must not be upgraded into quantified fact. If chart indicates `Disk Time (%)`, correlate with seek/await rather than falsely equate percentage to write IOPS.

**Safe research sequence:** (a) retrieve screenshot or CSV/historic PRTG series via Owner if available; (b) select 2–3 matched 15–30min quiet windows and classify per-process/per-DB/cgroup writes; (c) compare intervals to source scheduling and actual no-op transaction cadence; (d) lab-only one-change-at-a-time, preserving durability/audit/replay. **No unapproved production service restarts, schema/VACUUM, SQLite PRAGMA changes or blanket log muting.**

### 11. Tech Lead verdict

```text
ARCHITECT A1–A4: CLOSED / APPROVED
QIO-01A CODER: SCOPED IMPLEMENTATION TASK ISSUED, LAB-ONLY
QIO-01A ACCEPTANCE: NOT YET TESTED / ALL GATES PENDING
GITHUB PUBLISH: NOT AUTHORIZED
PRODUCTION DEPLOY / ACTIVATION: NOT AUTHORIZED
HISTORICAL STEP CHANGE: NOT PRECISELY DATED (PRTG graph coarse)
BEST TEMPORAL CANDIDATE: CURRENT STATE (Aug 23 origin) / AP-24H TELEMETRY (Aug 28)
CAUSAL HDD IOPS ATTRIBUTION: NOT PROVEN
```

**No repository, production service, disk, telemetry, PRTG, or configuration changes were made during this read-only review.**
