# CAPTIVPORTAL — QIO-02 / P1
## Tech Lead read-only writer & consumer audit R2 — 2026-10-16

**Status:** `P0=PASS; P1=PARTIAL/EVIDENCE_REQUIRED; H1=RESEARCH_ONLY; P2=HOLD; CODER=HOLD; PRODUCTION_MUTATION=NONE`.

**Owner/roles:** Chief Architect authorizes the eventual narrowly scoped disposable Lab experiment. Coder may only implement and run focused tests after P2 GO and a Tech Lead TASK. Tech Lead performs independent full Linux/Windows correctness, crash/replay/security and matched host performance gates. No separate independent QA role.

**Normative sources:** `QIO-02-SQLITE-SMALL-IO-ARCHITECTURE-ADMISSION-CONTRACT-v1`, Chief Architect P0/P1 clarification v1.1, previous `QIO-02-P1-READONLY-EVIDENCE-2026-10-16.md`. The architect explicitly prohibits weakening SQLite durability, eliminating authoritative scan/cycle records, or production code/service/database changes under P1.

### 1. Git and adopted runtime

- GitHub PR #219 merged as `main@191beda1f23f8f466d2431f42e57571815d85778`, tree `3f6d0a05c5d893d3139db44a1692c81e67fd6c6e`. This merge changes Visit reader operational telemetry (default OFF), **not** the five SQLite writer contracts under investigation.
- At read-only probe 2026-10-16 15:54 Asia/Baku: production `/opt/CaptivePortal` remained on `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`, `captive-portal.service=active`, PID `1887236`, `NRestarts=0`, clean tracked checkout. The Owner reserved the #219 deployment for a separate low-load night window.
- `/proc/<portal PID>/environ` contained no explicit `PUBLIC_TRAFFIC_COUNTER_ENABLED`, `PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS` or `PUBLIC_TRAFFIC_DB_PATH`. `/etc/default/captive-portal` similarly had no explicit lines for these keys. `app/config.py` defines **code defaults** enabled=`true`, scan interval=`10 s`; these are *not* independently measured adopted runtime values if other settings sources exist. The presence of `public_traffic.sqlite3` and previously observed repeated source rows is consistent with activity but is not itself a runtime configuration proof. The new Visit compact env flag was also absent (default OFF). Secrets were neither extracted nor printed.

### 2. Confirmed source writer matrix — static source analysis

This is an inventory of SQL ownership and admissibility, **not** physical HDD write attribution. Source definitions were inspected from the accepted base Git repo; the PR #219 merge is restricted to Visit reader telemetry.

| Domain | Entry / write functions | Commit/correctness boundary | Disposition under architecture v1.1 |
|---|---|---|---|
| Public Traffic | `app/public_traffic/reader.py:scan/_process_source`; `repository.py:process_offline_event`, `advance_source`, `observe_source`, `reset_source_after_reappearance`, `reset` | `BEGIN IMMEDIATE` + atomic processed-event/daily aggregate/checkpoint; source rotation/missing/truncation are durable; repeated EOF calls `observe_source` | **H1 only**: optional final same-tuple EOF observation, after proof that timestamp is not authoritative and per-operation cost is material |
| Visitor Registry | `registry_repository.py:apply_source_line`, `observe_source`, `mark_successful_scan` | Each complete successful scan has durable `last_successful_scan_at`; checkpoints/backfill and memberships protected | **KEEP** full successful-scan freshness; new `Q2-REGISTRY-FRESHNESS` contract required for any modification |
| Current State | `repository.py:publish_cycle`, `delete_cycles` | `BEGIN IMMEDIATE` cycle + client/AP rows with quality, scope/time; complete empty is authoritative negative evidence | **KEEP** every completed attempt/cycle; no H1 analogy |
| Visit Lifecycle | `repository.py:create_or_reuse_start`, `apply_journal_line`, `observe_reader_progress`, `process_pending_events`, reconciliation | `BEGIN IMMEDIATE` for auth/visit facts, checkpoints and retry progress; empty input can still advance durable retry | **KEEP** event/checkpoint/retry boundaries; #219 only changes operational log emission default OFF |
| Omada Observations | `app/observations/repository.py:create_cycle`, `finalize_cycle`, `_write` | Distinct cycle running/success/partial/failure/abandoned and quality/scope are authoritative evidence | **KEEP** all cycle facts even on unchanged client/AP data |

The method names/line locations are identification aids, not a complete timing or provenance trace. `sqlite3.connect` and `BEGIN IMMEDIATE` source presence does not prove a physical `fdatasync()` or host completed write.

### 3. H1: what is proven

1. On each discovered Public Traffic source, `_process_source()` calls `observe_source()` at the end of a successful complete EOF scan (`reader.py` around lines 217–236). Incomplete-tail branch calls a different `observe_source` and **must never be suppressed**.
2. `PublicTrafficRepository.observe_source()` (`repository.py` around lines 345–368) acquires `BEGIN IMMEDIATE`, performs `_upsert_reader_state`, and commits. `_upsert_reader_state()` (around lines 716–757) updates `updated_at` unconditionally on source-identity conflict, even if identity/path/offset/checkpoint/size/retired flag are unchanged.
3. Previous production **read-only** two-point observation: 6 `reader_state` rows at both samples 32 seconds apart; **5/6 changed only `updated_at`**; one had a source tuple change. This proves repeated timestamp updates, **not** the exact number of transactions, sync calls or physical IOPS per operation.
4. Source `ReaderState` dataclass (`models.py`, lines 85–93) has seven fields but **not** `updated_at`. `get_reader_states()` (`repository.py` around lines 183–206) selects those seven fields, excluding `reader_state.updated_at`.
5. Public `TrafficSnapshot.updated_at` is built by `repository.get_snapshot()` from **`traffic_daily.updated_at`** (`repository.py` around lines 446–489), NOT from `reader_state.updated_at`. The Analytics source gateway's `visit_reader_state.updated_at` is also a **different table/meaning**.

**Specific concurrency finding:** `PublicTrafficReader.scan()` obtains its `reader_state` snapshot **before** processing sources (`reader.py:51`), whereas `PublicTrafficRepository.observe_source()` obtains its own `BEGIN IMMEDIATE` lock later (`repository.py:357`). `PublicTrafficService.reset()` also delegates to a repository transaction. Therefore an optimization of the form `if preloaded_state == EOF_tuple: skip observe_source()` in `reader.py` would be vulnerable to a concurrent state change (TOCTOU). It **must not** be admitted as the narrow H1 implementation. Any future compare/no-op must be serialized under the existing writer ownership/transaction boundary or under an independently proven CAS contract; added reads/locks must be measured, not assumed free. This is a **source-derived design risk**, not evidence that a production race actually occurred.

### 4. Consumer search performed and precise limitations

- Source repository content search over available `app/`, `scripts/`, `tools/`, `docs/`, `tests/`: **0 literal `reader_state.updated_at`** references. `FROM reader_state` occurrences found in Public Traffic repository and in the **separate** Visitor Registry repository/tests (same table name, different database). No evidence of an application read of the Public Traffic timestamp surfaced.
- Read-only inspection of deployed `/etc/systemd/system` and `/etc/cron.*` relevant text files detected no reference to Public Traffic SQLite/`reader_state`; this is a **bounded file search**, not proof of absence of an external consumer.
- Previous live Grafana persistence scan found Loki and Prometheus datasources, no direct SQLite datasource. That excludes one consumption path only. Independent SQL tools, incident scripts, backups, forensics and external API/operational conventions are **not exhaustively inventoried**.
- **Semantic blocker remains:** even if no current code reads `reader_state.updated_at`, architecture may require that durable timestamp to mean *successful repeat scan freshness*. If so, Chief Architect v1.1 explicitly requires **`H1=REJECT`**, not an arbitrary 60-second throttle.

### 5. Physical measurements: known and unknown

Prior **simultaneously aligned** 10-minute observational window, UTC 10:54–11:04 (Baku 14:54–15:04), captured without SQL tracing or production mutation:

| Measured layer | Writes/s | Other signal |
|---|---:|---|
| `captive-portal.service` guest cgroup one device layer (`252:0`) | **6.92** | Includes all portal DBs and other writes; no per-DB partition |
| `systemd-journald` guest cgroup one layer | **6.82** | Not a QIO-02 SQLite writer |
| All guest `vda` completed writes | **48.53** | `vda` busy **97.49%**, guest full PSI **51.77%** |
| QEMU `Ubunt` VM host cgroup on device `8:0` | **43.72** | Includes all guest processes, not directly attributable to Public Traffic |
| Physical host `/dev/sda` completed writes | **66.80** | Busy **91.27%**, write await **89.21 ms**, other guests/host confound |

The host path is confirmed `Ubuntu vda → /UbuntVM/Ubunt.qcow2 → host /dev/sda1` on `OMV-HP`; cgroup guest layers `252:0`/`253:0` must **not** be summed. Different device and request-layer counters must **not** be summed or interpreted as one-to-one physical operations.

**N7-pre not yet passed.** The sampled interval is high-contention, not a quiet/matched baseline. Per-`observe_source` SQL COMMIT/fdatasync/WAL and physical cost remain unmeasured. A possible reduction in this one source operation may be small compared with other portal writes; size and timestamp-change frequency cannot establish host savings.

### 6. Next gated work (no Coder yet)

1. **Consumer/adopted Settings closure:** enumerate any Admin/health/API freshness contract and out-of-repository incident/replay tooling; ask Chief Architect to classify `Public Traffic reader_state.updated_at` explicitly as `durable successful scan proof` vs dispensable operational-only observation. Document a numerical SLA if one exists. Do not merge table names with Registry or Visits.
2. **Three quiet 10–15 minute windows** when real workload allows, with aligned UTC guest/QEMU/physical HDD counters, background/other-VM I/O, guest service IO, CPU/PSI and auth/source health. Record candid non-quiet windows as rejected candidates. No tracing, DB maintenance, artificial load, restart or data changes on production.
3. **Per-operation cost proposal:** if live read-only windows cannot separate same-tuple EOF cost from other writers, submit bounded causal inference plus a **disposable LAB REPLICATION PLAN** for explicit Chief Architect consideration; do not independently implement no-op guard before written `P2 LAB GO`.
4. **Lab correctness once admitted:** exact seven-field tuple including `missing_warning_emitted`, proper same-identity/generation; zero-byte append, incomplete tail, checkpoint mismatch, rotation/truncate, missing/reappear, retired state, concurrency/atomic comparison, crash/restart/replay; C01–C18 applicable gates and matched host physical A/B. Never weaken `PRAGMA synchronous`/WAL/commit boundaries.
5. Return `QIO-02 PER-DB PHYSICAL-WRITE & CONSUMER-SEMANTIC EVIDENCE` to Chief Architect with one of `H1 PASS_TO_LAB`, `H1 REJECT`, `ALTERNATE`, or candid **`EVIDENCE_REQUIRED`**. Today's status is `EVIDENCE_REQUIRED`.

**Do not conflate** the planned nighttime QIO-01D deployment/startup with quiet QIO-02 measurement; wait for runtime stabilization and a separate matched sample set. Cold-start SQLite reads belong to `QIO-STARTUP-READ` track.

```ini
QIO02_P0=PASS
QIO02_P1=PARTIAL_EVIDENCE_REQUIRED
QIO02_H1_LIVE_TIMESTAMP_UPDATES=CONFIRMED
QIO02_H1_DIRECT_APP_UPDATED_AT_CONSUMER=NOT_FOUND_IN_SCOPED_REVIEW
QIO02_H1_EXTERNAL_CONSUMERS=INCOMPLETE
QIO02_H1_DURABLE_FRESHNESS_MEANING=UNRESOLVED
QIO02_N7_PRE_PHYSICAL_COST=UNPROVEN
QIO02_QUIET_WINDOWS=0_OF_3
QIO02_P2_LAB=HOLD
QIO02_CODER=HOLD
QIO02_PRODUCTION=NO_CHANGES
```
