# CAPTIVPORTAL — SSR-01 / Chief Architect Architecture Decision Record v1

**Title:** Startup, Shutdown & Recovery — fault-isolated lifecycle and resource-aware recovery  
**Date:** 2026-10-15 (Asia/Baku)  
**Author / decision authority:** Chief Architect CaptivPortal  
**Requester / implementation owner:** the same CaptivPortal Tech Lead who authored `CAPTIVPORTAL-SSR-01-TECHLEAD-TO-CHIEF-ARCHITECT-R1-2026-10-15.md`  
**Verdict:** `MODIFY → ARCHITECTURE ACCEPTED; IMPLEMENTATION ADMISSION HOLD`  
**Owner permission:** `DESIGN_ONLY`; **production observation freeze** remains in force.  
**Repository evidence:** inspected `ZaurNavi/CaptivePortal@84b80376b13002d435be28eec98b91b9cbf71c63`; repo service templates ≠ proven installed units. User-reported later deploy shows an R3 tree `ea664b1d49ace86fc8a0c4ab2fc52945531e574a` on a target checkout; SSR-01 has not verified the live loaded-artifact/unit/drop-in graph.  
**No authorization:** Coder behavioral change, privileged systemd edits, service stop/start/restart, production DB or network modification, rollout or resource changes.

---

## 0. Architecture decision in one paragraph

**Choose distributed, fault-isolated lifecycle management:** systemd owns *per-unit* process supervision/ordering, and each application owns its data correctness, readiness, bounded buffers, stop/drain and recoverability. Keep **Guest Auth / CAPPORT / Omada independent of optional Fingerprint/NI/analytics readiness**. Preserve the existing precise internal Core graceful-shutdown sequence. Distinguish *process active*, *listener responds*, *functional ready*, *source usable*, *materialization current*, and *catch-up complete*. Permit automatic **local** recovery from crashes where already authorized, not generalized cascading restarts. Preserve deliberate Sensor–Suricata socket/capture coupling but do not broaden it. Gate costly replay by measured, fair **per-service** policies if lab evidence justifies a later implementation. **No new global orchestrator, no fixed sleep chain, no data/schema/durability changes.**

This ADR answers SSR-A01..A12 and specifies exact **Research/Admission Gates** for information the current sources do not establish. A research gate is not a delegation of an architecture decision to Coder.

## 1. Frozen facts, uncertainties and non-negotiable invariants

### 1.1 Verified source mechanics (repository baseline)

1. `run.py:shutdown_handler()` is idempotent; background scheduling stops, Visit scheduling stops **before** `auth_executor.shutdown(wait=True, cancel_futures=False)`; Visit stops accepting/closes **after** Auth drain; Visitor Snapshot drains, Registry performs final scan. `signal_handler` runs this handler and exits. **Do not move this order into systemd.**
2. Sensor unit template has `After=captive-portal.service`, `Restart=on-failure`, `RestartSec=30`, `TimeoutStopSec=20`. `After=` is start ordering, not `Requires=` or application readiness.
3. Sensor CLI `wait_for_core()` currently performs a **TCP connect-only** check with bounded max wait, not a real Omada authorization test. Its timeout causes Sensor process failure; the unit's own restart policy may retry. This inherited gate cannot be represented as `AUTH_READY`.
4. Suricata template has `After=fingerprint-sensor.service`, `BindsTo=fingerprint-sensor.service`, `PartOf=fingerprint-sensor.service`, an `ExecStartPre` Unix-socket wait capped at **1830 seconds**, and local `Restart=on-failure`. `BindsTo`/`PartOf` create deliberate stop/restart relationships; no assumption that automatic restart of Sensor will necessarily re-enqueue Suricata start.
5. Evidence process takes a writer lock, initializes store, registry and maintenance, calls `mark_ready()`, then starts its direct-TLS HTTP listener. Actual **functional** readiness must include listener+authenticated request+durable-ack capability, not merely earlier `mark_ready()` or active service.
6. Sensor Evidence producer delivers authenticated HTTPS batches, TLS CA-verified. HTTP 200 permits spool ACK; 429/500/503 use retry/backoff. Do not reorder ACK before verified 200 or erase spool on failure.
7. NI-01 health distinguishes source state from capture freshness: `FingerprintCaptureHealthAdapterV1` examines TLS/QUIC health observed in a **600-second** window; missing/stale data does not become `usable` merely because units are active.
8. NI-02B/NI-04 templates have ordering via `After=`, not hard-running-dependency propagation. Their derived work can be stale/pending even with a running process.
9. The full installed systemd graph, unit overrides, sockets, evidence/registry/traffic service units and currently loaded artifacts have **not been verified** by SSR-01. Repository paths and earlier logs do not replace that evidence.

### 1.2 Permanent invariant set (`SSR-I01..I12`)

- **I01** Guest Auth/Omada/CAPPORT serve independently of optional Fingerprint, Evidence, Sensor, Suricata, NI and analytics failures. Only a proved authorization/security dependency could change this by a new ADR.
- **I02** No hard process dependency, `Requires=`, `BindsTo=`, restart cascade or health-gate from any optional unit to `captive-portal.service`.
- **I03** One owner for each durable store and checkpoint; derived consumers may not advance durable cursor beyond source data actually durable/replayable.
- **I04** No invented evidence, successful attribution, source coverage, health or recovered history from lack of messages/zero queue/systemd active.
- **I05** Stopping/restarting raw Sensor or Suricata creates a real capture coverage interval unless proved otherwise; archived/retained bytes cannot fill that gap retroactively.
- **I06** Source identity, Site scope, receiver ACL/TLS/Bearer, current admission/binding epoch and provenance remain enforced.
- **I07** No SQLite wipe/reseed/VACUUM/new migration, no weakening `synchronous=FULL`, `fsync`, transaction, lock, source generation, WAL or retention contracts.
- **I08** Safe stop drains already accepted Auth requests before Visit acceptance closes; leave `run.py` ordering intact.
- **I09** Automatic restart bounded and **local to the failed service** except reviewed Sensor↔Suricata coupling. No continuous restart storms.
- **I10** No unconditional fixed delays, whole-platform readiness barriers or global replay coordinator in Phase 1.
- **I11** Auth latency, freshness/lag, drop rate, disk latency and source continuity must be measured together; better wall-time or lower `busy` alone is not acceptance.
- **I12** Code merge, systemd installation, production restart/activation and changing recovery resource budgets are separate Owner decisions.

---

## 2. Twelve architectural decisions (`SSR-A01..A12`)

### SSR-A01 — Lifecycle authority and change scope

- **DECISION:** `systemd` owns service start/stop/restart of exact installed units. Core owns Auth/Visit/Registry/Snapshot internal lifecycle; Evidence owns writer readiness/durable-ack; Sensor owns capture/spool/transport; NI modules own checkpoints, lag and materialized states. Operators can issue planned stop/restart after authorization. Existing `Restart=on-failure` is a local automated reaction, subject to existing bounds and later storm testing. **No global application coordinator**.
- **RATIONALE:** Separate failure domains; replacing them with one dependency chain risks Auth outages.
- **FAILURE/RESTART:** A worker restart does not automatically restart the Core or unrelated workers. Hard dependencies are limited to verified inseparable local pairs (Sensor/Suricata only currently identified).
- **ADMISSION:** Read-only exact live unit graph, reverse dependencies and drop-ins (`SSR-R01`), plus isolated restart-fault Lab. Do not assume the repo templates match live units.

### SSR-A02 — Dependency topology and stop/restart policies

**Normative target edge matrix.** “No hard” means no **new** hard process coupling; an existing unverified live edge is not authorized for modification until reconciled. Stop/restart semantics of each edge are specified; “retry” means the consumer uses its already-owned bounded local retry, not a systemd cascade.

| Consumer ← input | Edge classification / start | Input failure / stop | Input returns / local restart | Data & coverage | Readiness authority |
|---|---|---|---|---|---|
| **Core/Auth ← Omada** | **Required functional serving dependency** for successful guest authorizations, but **not** a systemd dependency to optional workers | Requests fail honestly under existing Auth/Omada semantics; do not falsely mark successful login | Next authorized request follows existing Omada retry/provider behavior; do not restart whole VM | No fictitious successful Auth or Visit | Auth transaction outcome + Omada provider/authorization health, not HTTP 400 |
| **Core/Auth ↔ Evidence/Fingerprint** | `independent-fail-degraded`; **no hard edge** | Core continues guest auth; optional evidence/insights unavailable | Evidence restarts locally; Core never cascades | Optional evidence gaps reported | Core Auth owner / Evidence health separately |
| **Sensor → Core listener (legacy)** | Existing bounded **TCP-only startup check**; not a functional Auth gate; **target policy** is avoid Core dependence after separate Lab proof | Current build may not start until TCP ready; timeout→local failure/retry; no Core restart | Sensor retries locally; no automatic blanket restart | During Sensor absence, raw capture gap | TCP connector only (legacy); Sensor capture health is separate |
| **Sensor → Evidence receiver** | `independent-fail-degraded`, not systemd `Requires` | Sensor continues permitted capture into bounded durable spool, retry on 429/503/network outage; receiver refusal does not reset queue | Reconnect/TLS/auth, resend unacknowledged in existing order; do not mark delivery ready early | Bounded spool; overflow means reported loss/block, not silent completeness | Evidence authenticated ingest outcome; Sensor spool/delivery state |
| **Suricata → Sensor EVE socket** | Existing **local hard runtime coupling** (`After+BindsTo+PartOf`) only for this producer/socket pair, with bounded socket wait | If Sensor socket/process is absent, Suricata must not publish “healthy TLS/QUIC”; existing binding may stop Suricata | Re-enable Suricata only after socket and valid preflight; do not assume spontaneous Sensor recovery automatically restarts Suricata | Suricata-only loss: TLS/QUIC gap; raw DHCP/SYN can remain; Sensor loss: both affected | Socket + Suricata heartbeat + source-health timestamps |
| **NI-01 → Suricata EVE file** | `consumer-readiness gate` at file/generation read, **no hard process coupling** | NI-01 may remain alive; mark source unavailable/stale/partial per existing model, never manufacture continuity | Reopen generation, verify identity/rotation/replay, resume only from durable checkpoint | Exact gap/continuity evidence; not an automatic clean interval | NI-01 source-generation/checkpoint and capture-health |
| **NI-02B → NI-01 + Sensor attribution + Core Registry** | Soft `After` plus **data-authority gate**, not `Requires` | Continue only work backed by verified durable authority; otherwise pending/unavailable or stop the affected resolution, not whole Core | Re-evaluate pending with bounded existing retry + binding checks | No attribution by missing IP-only evidence; no cursor past guarantee | NI-02B per-record disposition, pending/lag, authority health |
| **NI-04 → NI-02B and admitted source** | Soft `After`, materialization authority gate | Last-known results may remain marked stale/unavailable, not newly current; block unjustified advancement | Resume incremental/replay from durable cursor after validating source | Materialized recency != source health | NI-04 durable feed cursor/highwater, health, freshness |
| **Fingerprint Classifier/Integration → Evidence and Auth-derived jobs** | `independent-fail-degraded` | Auth unaffected; durable jobs can pend/retry only within current accepted schedule; no fabricated classification | Worker recovers from owned persistent jobs and admitted sources | Result may be unknown/stale/NO_RESULT_FINAL per accepted contract | Integration job state, classifier admission, evidence freshness |
| **Traffic Projection → Core-owned source** | No new hard coupling to Auth, source-readiness gate | Stop/defers unjustified projection; keep last-good with explicit freshness; Core continues | Incremental/reconcile on verified source version/head | Do not overwrite source or hide divergence | Traffic projection owned version/head/read model |

**Research dependency:** Exact service name/capability for Evidence, Fingerprint classifier, Traffic, edge bridge and deployed source-of-truth must be discovered in SSR-R01. The architecture class stays fixed; any actual live hard edge inconsistent with the table returns to the Architect before change.

### SSR-A03 — Core authorization readiness

- **DECISION:** Distinguish (1) process active, (2) HTTP listen/respond, (3) application composition configured, (4) real **guest authorization ready**. `400` without CAPPORT/Omada captive parameters proves only request handling, never (4). Auth-ready requires validated configuration and a controlled **end-to-end authorized guest flow** through current Omada/CAPPORT contracts, including expected authorization result and Visit behavior. For monitoring, existing independent Auth/Omada health can indicate configured/degraded but cannot substitute for an end-to-end acceptance proof.
- **FAILURE:** If Omada unavailable, report auth unavailable/degraded under existing semantics; no dependency on NI/Fingerprint changes it.
- **ADMISSION:** First-stage use existing health/readiness telemetry and **Lab/Owner-authorized smoke**. A new auth endpoint or synthetic guest traffic is **not** approved here. Actual client smoke only with authorized test identity at a separately admitted stage.

### SSR-A04 — Evidence readiness and expensive cold start

- **DECISION:** Evidence `functional_ready` requires held exclusive writer lock, completed required accepted DB/schema/recovery checks, configured producer registry, active TLS listener, and **authenticated health request** proving correct receiver identity. `durable_ack_capable` is stronger: exercised in isolated Lab through accepted authorized evidence batch + persisted readback, not by ping or new uncontrolled production writes. `mark_ready()` before listening is a **local state transition, not network availability proof**.
- **FAILURE:** Slow/failed DB validation ⇒ `starting/recovering` or `unavailable`; never bypass accepted full-integrity checks for startup speed. Sensor buffers independently and retries without restarting Core; bounded spool may degrade, and is not lossless indefinitely.
- **ADMISSION:** `SSR-R02` file-backed cold start (empty, normal, large, corrupt/partial, contended HDD), verify timeout and resource cost. Any proposed startup-cache/partial-validation shortcut needs separate architecture and integrity proof; not permitted in SSR-01A.

### SSR-A05 — Sensor↔Suricata hard local coupling

- **DECISION:** **Retain existing `BindsTo+PartOf+After` initially**, as a purposeful exception rather than a blanket policy. Sensor's Unix EVE socket is a prerequisite for Suricata normalized delivery. Do not broaden to NI-01, Evidence or Core. `ExecStartPre` up to 1830 seconds is **a bounded but lengthy socket wait**, not overall readiness guarantee.
- **FAILURE:** Sensor planned stop/crash ⇒ Suricata should be quiesced as defined by verified systemd semantics; mark raw+TLS/QUIC gaps. Suricata alone stops ⇒ raw DHCP/TCP SYN Sensor capture may continue, TLS/QUIC becomes unavailable/stale; do not claim whole Sensor captured nothing. Evidence outage ⇒ neither must be stopped by systemd solely for receiver outage.
- **RECOVERY:** On Sensor return, re-start Suricata only if verified systemd job graph actually enqueues it; otherwise operator-controlled targeted reactivation until a separately tested localized auto-reattach is admitted. No implicit claim `BindsTo` starts/restarts dependents.
- **ADMISSION:** `SSR-R01/R05`, Lab full boot, Sensor stop/crash, Suricata-only crash, restart and EVE socket creation/removal including timeout; verify true capture health. Suricata template still pins `enp8s0`: a separate deployment configurability contract cannot be smuggled into SSR-01.

### SSR-A06 — Evidence 429/offline and bounded spool

- **DECISION:** Preserve existing Sensor bounded durable spool, at-least-once delivery and 200-before-ACK. Retry on 429 respecting valid `Retry-After`, 500/503/network with existing bounded backoff. No mutual process restart. Do not treat retry 429 as permanent source incapacity.
- **CAPACITY:** Only the existing approved spool row/byte/age constraints govern deletion/block/retry. **No new numeric queue thresholds invented here**. Raise explicit `recovering/backlog`, `degraded/near_capacity`, `unavailable/capacity_blocked` from module-owned metrics as applicable, with exact future alert thresholds selected by measured Lab admission; do not silently discard unacknowledged evidence or promise lossless raw capture under exhausted capacity.
- **ADMISSION:** `SSR-R04` determine current effective limits and safe drain rate; test 429/503/outage/slow receiver/long backlog/full disk/crash between remote 200 and local ACK for idempotent retransmission. Receiver concurrency and replay fairness assessed independently.

### SSR-A07 — NI-01 source generation, rotation, restart

- **DECISION:** Continue checkpoint-based bounded ingestion; on EVE absent/rotated/partial/unreadable mark the appropriate output/ingest/capture health, preserve source generation lineage and continuity evidence. Read only complete authoritative bytes; restart from persisted durable offset with existing replay/conflict rules. Do **not** advance on unreadable/undurable data, and never equate a new file or empty file with a gap-free interval.
- **FAILURE:** NI-01 stays local degraded or fails closed as its accepted implementation specifies; Suricata crash must not cascade into NI-01/Core restarts. NI-02B respects downstream pending/authority limits.
- **ADMISSION:** Lab file rotation/inode change, truncate, partial write, crash-before/after COMMIT, stale capture and verified gap; preserve NI-01-A state, NI-01-B remains rejected/closed unless new separate decision.

### SSR-A08 — NI-02B/NI-04/Classification/Registry authority

- **DECISION:** Use three categories, not a single global ready bit: **authoritative input unavailable → fail closed for *new claims***; **derived computation recoverable → keep durable pending/last-good, appropriately marked**; **admitted input newly available → bounded retry/reconcile**. Existing schema-specific `pending`, `unavailable`, `unknown`, `stale`, `NO_RESULT_FINAL` definitions remain authoritative; this ADR does not invent new domain enum strings.
- **FAILURE/RESTART:** NI-02B no positive MAC-IP/site binding or cross-identity attribution without accepted DHCP/Registry authority. NI-04 can expose stale last-good only with explicit freshness and MUST NOT claim current highwater. Classification must not turn missing evidence into a positive high-confidence device assertion. Registry/Core restarts may temporarily withhold readers; derived workers do not force Core restart. Replay and pending attribution remain persisted across worker restarts.
- **ADMISSION:** Lab late-binding after all partial failures, source-version change, authoritative Registry disappearance, NI backlog replay, classification job requeue, source-health stale, network service highwater and traffic projection divergence. Test no cursor leaps and no unknown→positive by omission.

### SSR-A09 — Graceful shutdown and crash/power loss

- **DECISION:** Retain `run.py` internal ordering exactly (**Visit schedule stop → Auth executor drain → Visit accepting stop → Snapshot drain → Registry final scan**). At **full VM orderly shutdown**, favor quiescing ancillary *acquisition* before closing its consumer and allow bounded spool/write completion; Evidence writer should be available to drain while possible and stop after its producers where actual topology permits. Stop NI derived writers after stopping new source acquisition/consistent source boundary, while preserving durable checkpoints. Prioritize **Core serving continuity until OS shutdown requires it**, but do not impose a global barrier or hold shutdown unboundedly.
- **TARGETED STOP:** Stop only requested unit plus deliberate Sensor→Suricata coupling, never shut down entire dependency chain. Evidence-only stop does not force Sensor/Suricata stop (spool). NI-04-only stop does not stop NI-02B; NI-02B-only stop does not stop NI-01.
- **TIMEOUT/SIGKILL:** If drain deadline reached, unacknowledged items remain in durable spool/queue, unfinished DB transaction rolls back, `ready`/success is not emitted falsely, and coverage gap is recorded; the next restart follows the module recovery contract. `TimeoutStopSec`, stop-signal and process behavior must be tested; do not assert safe `SIGKILL` while an untested writer is in-flight.
- **ADMISSION:** Measure actual stop durations and `SIGTERM`→bounded drain in Lab; full reboot, stop during Auth job/Visit close, stop with nonempty spool, WAL transaction interruption and crash recovery. No new generic `ExecStop=kill` handler.

### SSR-A10 — Recovery concurrency and HDD resource priority

- **DECISION:** Three priority classes: **P0** Auth/Omada/CAPPORT and required online state; **P1** evidence source continuity, spool safety and authoritative durable recovery; **P2** historical derived rebuild/analytics/catch-up. P2 never delays P0 readiness via a hard startup gate. **Choose per-source bounded batches and existing local retry/backoff as first-line policy**; no fixed global count or central scheduler in v1. Adjust recovery worker activity/CPU/IO weights **only after** matched Lab evidence and a separate Owner infrastructure admission.
- **FAIRNESS:** Catch-up must advance under stable capacity, yield to serving path, and preserve bounded maximum source lag/TTL acceptance existing contracts. Never indefinitely suspend retention/repair or hide permanent backlog; if a proposed throttle causes non-convergence or data age exceedance, reject it.
- **ADMISSION:** `SSR-R03/R04`: synchronized host/guest boot/recovery HDD profiles and queue progress; compare Auth latency, time-to-serving, physical completed IOPS, `await`, PSI, CPU, drain rate, risk of retention age-out. No invented global `IOPS=...`, no SSD-as-solution, no blanket `CPUQuota` or `IOWeight` changes now.

### SSR-A11 — Scenario semantics and observability

- **DECISION:** Lifecycle words are **presentation/operations labels** over each module's actual existing state; do not replace accepted module domain enums without an explicit future DTO/API decision. Authority is per component, never `systemctl is-active` alone.

| Scenario | Required truth / behavior | Authority / required observable |
|---|---|---|
| Cold VM boot | Core may become serving before optional pipelines; optional modules start in independent jobs; no false full-platform ready | Core auth smoke/health; per-unit state; each producer/consumer health |
| Planned full reboot | Preserve Auth/Visit drain; bounded spool/derived checkpoints; any capture stop interval flagged | Core lifecycle logs + durable source health and checkpoint |
| Targeted restart (Core) | Existing Core internal shutdown; optional dependent workers **not** blanket-restarted; sensor's legacy TCP gate applies only to startup | Core authenticated flow and worker-local health |
| Targeted restart (Sensor) | Suricata deliberate coupling, capture gap; Evidence/NI/Core not forcibly bounced | Sensor local capture, Suricata heartbeat, gap timestamps |
| Unexpected worker crash | Local bounded restart; no unrelated cascade; persisted unacked/replay recover | systemd unit result + owner durable store health |
| Evidence 429/503/offline | Spool/backoff, correct partial availability; capacity alarms; recovery without data clearance | 429/503 rate, spool oldest/rows/bytes, delivered/acked |
| Slow HDD | P0 responsiveness monitored; P1/P2 catch-up cost not misreported as useful serving | host completed HDD IOPS/await + guest cgroup + Auth latency |
| Evidence validation delayed | `starting/recovering`, no spurious `ready`; Sensor survives within approved buffer limits | Evidence DB initialize/lock, TLS/API health, spool trends |
| Queue near/full | Explicit state and risk of loss; no silent truncate/reset; no unconditional unlimited backlog | spool metrics + source-health/evictions/faults |
| EVE rotation/partial source | NI source may be stale/partial/unavailable; checkpoint conserved; no gap-free inference | NI generation, identity, offset, capture freshness |
| Abrupt power loss | Unfinished transactions rolled back, committed source evidence replayable, unconfirmed capture interval not fabricated | durable repository checks, WAL/foreign keys, generation lineage |

- **MINIMAL REQUIRED OBSERVABLES:** timestamped `process_up`, module-ready reason, source availability/freshness, `last_durable_source_offset/generation`, queue rows/bytes/oldest age, observed drop/gap, backoff count, pending/reconcile lag, recovery progress and stop outcome, plus artifact SHA/TREE. Use already-existing owner metrics first; gaps are evidence for a separate narrow instrumentation TASK. Do not log raw secrets, full evidence payload or personal identifiers into new telemetry.
- **ADMISSION:** Confirm each label can be derived from existing authoritative metrics; a missing label means `UNKNOWN/UNVERIFIED` operationally, not invented `ready`.

### SSR-A12 — Minimal implementation and rollback governance

- **DECISION:** **No implementation authorization today.** First deliverable is **SSR-01A Evidence & Operational Contract**: read-only installed manifest (after observation freeze and an explicit read-only Owner permit), diagram of dependency graph, current readiness/stop-state mapping and isolated Lab reproducible fault-injection test plan. This can be completed without production config edits and without modifying data-plane. It is a **Tech Lead/SysAdmin research and documentation work package**, not Coder GO for service changes.
- **SUBSEQUENT SLICES (independently gated, not pre-approved):**
  - `SSR-01B`: only minimal service/health mismatch repair revealed by R01/R05, e.g. local restart/reattachment or ready gate; **new separate** Architect scope amendment for any hard edge, startup logic, systemd drop-in or exposed health API.
  - `SSR-01C`: one measurable recovery/catch-up resource hypothesis (P1/P2), only after R03/R04 and performance review; no bulk change of all workers.
- **SEPARATION:** Repo source/test/template changes via Tech Lead→Coder PR only after Task admission. Installed unit/drop-in/cgroup/VM operations via Owner→SysAdmin instruction. Neither is authorized by a merged source-only PR. No production probes that restart services during freeze.
- **RELEASE:** Exact baseline/TREE, test gates, central release gate per applicable governance, independent QA, Owner-approved merge, separate staged service activation. Accepted merge ≠ permission to restart production.
- **ROLLBACK:** Pre-change unit/drop-in checksum plus current loaded-artifact identity; versioned change by one failure domain; ability to restore prior units and exact Git tree without DB rollback/migration. Stop or revert on Auth latency regression, incorrect readiness, unexpected cascade, elevated drops, unsustainable backlog, checkpoint or source-health loss. For actual capture gap during rollback, retain the gap evidence.

---

## 3. Research/Admission gate ledger — exact missing facts and accountable owners

| Gate | Responsible for evidence | Required result to PASS | What it unlocks |
|---|---|---|---|
| **SSR-R01 Live Graph** | SysAdmin collects after Owner read-only permission; Tech Lead independently reviews | Sanitized `systemctl cat/show`, drop-ins, reverse dependencies, socket activation, exact ExecStart/Stop, restarts/timeouts, artifact IDs, installed-vs-repo diff; complete list of Core/Evidence/Sensor/Suricata/NI/Classifier/Traffic/Edge | Only precise unit-oriented design/review; **not** change authorization |
| **SSR-R02 Evidence Cold Start** | Tech Lead + independent Lab/QA | file-backed Lab empty/normal/large/corrupt DB, no bypass of validation, measurements of startup/response, verified authenticated TLS and durable ACK, adverse HDD contention | Proposed narrow Evidence readiness/perf fix if demonstrably needed |
| **SSR-R03 Resource/Boot Profile** | Performance researcher + SysAdmin synchronized observer; Lab QA | at least representative boot/recovery/quiet/peak windows; host HDD `diskstats`, QEMU cgroup, guest per-service I/O, CPU, PSI, guest Auth latency, backlog; distinguish overlapping layer counts | Prioritize one justified recovery throttle; no target percentages invented |
| **SSR-R04 Queue/Authority Inventory** | Respective module maintainers + Tech Lead | distinct spool/NI-01 generation/NI-02B pending/NI-04 head/Traffic queue counts and age, capacity and durable ACK/commit semantics, measured convergence, no confusion with false source ready | Safe local retry and capacity-budget proposal |
| **SSR-R05 Systemd coupling Lab** | Tech Lead + SysAdmin + independent QA | cold boot, Sensor stop/crash/restart and Suricata stop/crash/restart, long EVE socket wait, no unintended hard cascade; prove whether automatic Suricata reattachment works; failure-mode matrix aligned with real units | Narrow change to Sensor–Suricata service model only if required |
| **SSR-R06 Source/document drift** | Tech Lead | current source SHA, tested merged TREE, actual loaded artifacts; no old VLAN10+20 mirror claim applied to VLAN20-only if authoritative newer record differs; update KB separately | Reliable later implementation baseline |

If a gate fails, return **precise discrepancy** to Chief Architect or source owner. **Coder cannot choose** a hard-edge policy, silently disable an integrity check or invent a recovery threshold.

## 4. Acceptance requirements for later implementation (not performed)

- **C1 Auth priority:** The candidate preserves Guest Auth, CAPPORT, Omada and Visit lifecycle behavior under cold boot, planned reboot, targeted Core restart, Sensor/Evidence failure and slow disk; measure actual functional outcome, not mere HTTP 400.
- **C2 Isolation:** For every modified unit, targeted stop/restart of each peer produces only the documented cascade. Specifically verify `BindsTo/PartOf` Sensor→Suricata including restart recovery.
- **C3 Durability:** Crash at every ACK/transaction/checkpoint boundary preserves confirmed evidence, spool identity, lineage and replay; no positive fact without durable authority.
- **C4 Health:** Source coverage gap/stale/unknown and NI partial availability remain observable; missing heartbeat/queue=0 never leads to false ready. No classification source-high confidence from missing authority.
- **C5 Performance:** In equivalent HDD-like Lab distributions, physical host writes/await/busy, guest per-service block I/O, CPU/PSI, Auth latency, readiness time, backlog trend and drops are recorded. No automatic PASS from only CPU improvements or fewer SQL VM steps.
- **C6 Operations:** Freeze lifted by Owner; new source/producer admission separate; exact before/after unit manifest; rollback proof; no secret leaks; staged one-unit-family change; independent release review per accepted project policy.
- **C7 Negative:** explicit fail for unbounded loops, unproven all-green readiness, zero gap after capture halt, cascade to Auth, no-convergence backlog, checkpoint overrun, error disguised as successful cleanup.

## 5. Required Tech Lead next deliverable

Within **SSR-01A** (research/documentation only):

1. Produce sanitized **installed unit graph** with exact version/owner and unverified cells, without accessing production until observation freeze lifted and separate read-only permission given.
2. Produce **verified source/receiver readiness map** separating `ACTIVE`, `LISTENING`, `AUTH_FUNCTIONAL`, `EVIDENCE_INGEST`, `CAPTURE_FRESH`, `SOURCE_DURABLE`, `MATERIALIZATION_CURRENT`, `CATCHUP_COMPLETE`.
3. Lab-fault matrix for Sensor↔Suricata, Evidence 429/503, NI rotation/replay and targeted Core restart with explicit expected no-cascade outcomes.
4. Measured cold-start/boot-resource hypothesis **before** implementation. If no causal issue requiring a code/unit change emerges, close SSR-01A with documentation and do not create speculative Coder tasks.
5. Return scoped `SSR-01B` or `SSR-01C` proposal only if a failed proof or measurable bottleneck demonstrates necessity. Review with the **same Tech Lead**; no extra interposed Tech Lead.

### Exact disposition

```text
REQUEST=SSR-01
ARCHITECT_VERDICT=MODIFIED_APPROVED
ARCHITECTURE_ADR=SSR-01_v1_FINAL
OWNER_APPROVAL=DESIGN_ONLY
PRODUCTION=OBSERVATION_FREEZE
LIVE_UNIT_GRAPH=UNVERIFIED
SOURCE_REVIEW=84b80376b13002d435be28eec98b91b9cbf71c63
ORCHESTRATION_MODEL=SYSTEMD_LOCAL_PLUS_APPLICATION_OWNED_STATE
GLOBAL_COORDINATOR=REJECTED_FOR_V1
GLOBAL_SLEEP_CHAIN=REJECTED
CORE_AUTH_DEPENDS_ON_OPTIONAL_NI_FP=NO
SENSOR_SURICATA_COUPLING=KEEP_PENDING_LAB_RECONCILIATION
STARTUP_IO_THROTTLE=RESEARCH_GATE_REQUIRED
FIRST_WORK_PACKAGE=SSR-01A_RESEARCH_DOCS_ONLY
CODER_GO=NO
INFRA_CHANGE_GO=NO
MERGE=NO
DEPLOY=NO
RESTART=NO
NEXT=TECH_LEAD_SSR01A_EXACT_RESEARCH_AND_IMPLEMENTATION_ADMISSION_REQUEST
```

---

## 6. Evidence index

- Request: `CAPTIVPORTAL-SSR-01-TECHLEAD-TO-CHIEF-ARCHITECT-R1-2026-10-15(1).md` provided by the Tech Lead/Owner.
- Repository source review at pinned SHA `84b80376b13002d435be28eec98b91b9cbf71c63`: `run.py`; `app/device_fingerprint/cli.py`; `app/device_fingerprint_sensor/cli.py`, `producer.py`, `runtime.py`; `app/network_metadata/health.py`; `app/network_metadata_projection/service.py`; `app/device_fingerprint_integration/worker.py`; `deploy/device-fingerprint/fingerprint-sensor.service`, `fingerprint-suricata.service`; `deploy/network-metadata-projection/network-metadata-projection.service`; `deploy/network-service-recognition/network-service-recognition.service`; `docs/architecture.md`.
- Research context: `CAPTIVPORTAL-PERF-IO-QUIET-LOAD-OPTIMIZATION-ROADMAP-v1.0-2026-10-15.md`, Chief Architect permanent memo.
- **Not claimed:** current live production systemd graph, actual installed Evidence unit, benchmark-measured startup savings, completed QA, Owner authorization of operational changes.

**End of Chief Architect ADR v1.**
