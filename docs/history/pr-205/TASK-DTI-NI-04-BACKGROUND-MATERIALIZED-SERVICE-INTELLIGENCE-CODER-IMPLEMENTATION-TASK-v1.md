# TASK-DTI-NI-04 — BACKGROUND MATERIALIZED SERVICE INTELLIGENCE
## TECH LEAD IMPLEMENTATION TASK v1 — CODER

**Project:** CaptivPortal  
**Issuer:** Tech Lead / TechLead23  
**Date:** 2026-10-13  
**Priority:** P1 / product correctness + materialized-read architecture  
**Implementation status:** CODER GO — development, tests, documentation, PR only  
**Merge / production migration / deploy:** NO — separate Owner authorization  
**NI-05 / NI-06:** HOLD

## 0. Authority, inputs, and precedence

**Repo:** `ZaurNavi/CaptivePortal`  
**Frozen starting code baseline:** `main@b1442efc434716d35e21b9e3124c3b9cd2222fbe`  
**Tree:** `1ea6a2d452a5c8147d2a9cdce6c5dcecd9900575`  
**Already accepted:** PR #204, NI-04 Attribution Recovery V2.  
**Normative architecture:**

1. `TASK-DTI-NI-04-BACKGROUND-MATERIALIZED-SERVICE-INTELLIGENCE-ARCHITECTURE-CONTRACT-v1.md`.
2. `TASK-DTI-NI-04-BACKGROUND-MATERIALIZED-SERVICE-INTELLIGENCE-ARCHITECTURE-CONTRACT-v1.1-ADDENDUM.md` (overrides v1 only for TL-R1/R2/R3).
3. Previously accepted Attribution Recovery V2 and NI-04 contracts where not superseded.

This task translates the accepted architecture into implementable work. Coder MUST read both normative architecture documents in full before editing. If code at the actual branch head differs materially from the pinned baseline, STOP and report the exact drift; do not silently rebase semantics or deploy.

**Permanent principle:** _Compute when evidence arrives; persist confirmed derivation; read materialized state when a Device Card opens._ Raising the five-second on-demand deadline is explicitly **not** the fix.

## 1. Objective and definition of done

Replace the normal Device → Service Intelligence path that fetches up to thousands of NI-02B facts, rereads NI-01 in 256-observation batches, and recomputes recognition on an Admin request. Instead, a separate NI-04 worker incrementally reads an authoritative NI-02B delivery feed, obtains exact NI-01 evidence, runs the existing checked direct-SNI matcher, durably materializes device-bound positive observations and rollups, and maintains independent materialization coverage. In `serve` mode, Admin reads **only** the dedicated materialized NI-04 SQLite.

End state:

- **No Admin request-triggered bulk NI-01 reads, NI-02B 24h fact scans, matching, backfill, or heavy aggregation.**
- **Already confirmed services remain visible under unrelated/global pending attribution**, while incomplete coverage never becomes a false negative.
- Correct rolling 60-minute Recent Services and 24-hour Last Service Observation windows.
- Independently recoverable worker, exact lineage, replay-safe checkpoints, bounded I/O, privacy-safe telemetry.
- Opt-in deployment modes `off -> shadow -> serve`, with safe pre-migration bridge and explicit rollback floor.
- Laboratory and deterministic test gates pass; no production modification is performed by Coder.

## 2. Scope and protected invariants

Implement **only** WP-B1, WP-B2, WP-C, WP-D, WP-E, WP-F as specified below. Keep untouched unless tests/docs require narrow changes:

- NI-01 acquisition, parser, writer, evidence schema and event semantics.
- NI-02A authority and algorithm; NI-02B attribution/pending/retry algorithms, committed immutable edges, source checkpoints and core schema meaning.
- NI-03 public behavior; Fingerprint, Current State, Visit Lifecycle, Guest Traffic, Omada provider, Portal/Auth/CAPPORT, Admin Access Policy.
- Frozen NI-04 knowledge artifact files, admitted bundle validity rules, and pure `match_direct_sni_v1()` semantics.

Mandatory safety: SNI or current IP alone never identifies a Device; exact Site+MAC authoritative binding is needed. No cross-Site/cross-Device service facts, MAC-randomization heuristic, IP-only service inference, pending-to-positive conversion, undocumented raw-host/IP persistence, or claims of actual user viewing/content/duration. NI-04 readiness MUST NOT block captive portal authorization.

Existing code anchors (verify names/locations before changes):

- `app/network_metadata_projection/schema.py`, `repository.py`, `service.py`, `recognition_read_service.py`, `config.py`, `cli.py`.
- `app/network_metadata/recognition_read_service.py`.
- `app/network_service_recognition/read_service.py`, `models.py`, `serialization.py`, `artifacts.py`, `matcher.py`.
- `app/admin_web/runtime.py`, `query_service.py`, `routes.py`, `static/admin.js`.

### Hard boundary: development versus production

Implement on a feature branch, with reviewable commits and tests. The presence of systemd files, migrations or scripts in the PR is **not permission to run them on production**. Do not restart any production service, alter the current production SQLite, switch flags, merge or deploy. A separate Owner-authorized operator runbook will govern release.

## 3. WP-B1 — NI-02B compatibility bridge and additive delivery extension

### B1.1 Compatibility bridge MUST precede migration

Refactor current whole-database exact-signature `validate_schema()` into logically closed validation of:

- **CORE_ONLY:** exact accepted Core Projection V1 object set/DDL/metadata and PRAGMAs;
- **CORE_PLUS_EXTENSION_V1:** exact unchanged Core V1 objects **plus** exact extension V1 objects;
- all unknown application-owned tables/indexes/triggers or partial extension object sets: fail closed.

Do **not** bump `PRAGMA user_version=1`, the Core schema/algorithm identities or change Core V1 object DDL. Exclude only SQLite internal `sqlite_%` artifacts from application object comparisons. Both old and extension-aware readers/writers in the bridge must preserve current behavior when the extension is absent. The bridge must maintain extension rows **whenever it is present**, even if NI-04 publication mode is `off`.

Produce a separately testable and reviewable **compatibility bridge commit** in which extension installation remains disabled by default; record its exact accepted SHA as `NI04_MAT_COMPAT_BASE_SHA` in release evidence when Tech Lead accepts it. The currently deployed `b1442efc...` **MUST NOT** be listed as a post-migration rollback target.

### B1.2 Optional transactional installer

Extension installation is explicit/disabled by default and is executed only by the existing NI-02B single writer **after** acquiring the established writer lock. Verify accepted Core V1 first; then one `BEGIN IMMEDIATE` transaction creates all exact extension objects, seeds existing authoritative bindings in deterministic `(site_id, client_mac)` order, adds extension metadata, validates both exact signatures, and commits. Re-entry after successful installation is a no-op. Crash before commit restores exact CORE_ONLY; after commit yields exact complete extension. A pre-existing partial extension must fail closed, with no heuristic repair or table drops.

Extension V1 consists of exactly these tables and their required SQLite indexes/autoindexes:

1. `projection_service_recognition_extension_meta` singleton, `extension_contract_version=1`, installation timestamp.
2. `projection_service_recognition_feed`: `feed_seq INTEGER PRIMARY KEY AUTOINCREMENT`, `edge_id TEXT NOT NULL UNIQUE`, `committed_at_utc TEXT NOT NULL`, FK `edge_id` to the existing immutable edge with `ON DELETE CASCADE`.
3. `projection_registry_binding_change_index`: `change_seq INTEGER PRIMARY KEY AUTOINCREMENT`, `site_id`, `client_mac`, `binding_state='authoritative'`, non-null `device_id`, `evaluated_at_utc`, `UNIQUE(site_id,client_mac)`, FK `(site_id,client_mac)` to `projection_site_mac_bindings` with `ON DELETE CASCADE`.

The schema contract is `projection_service_recognition_feed_contract_version=1` within explicitly versioned extension metadata, not a stealth core schema change. No core table rebuild.

### B1.3 Atomic candidate outbox

Whenever NI-02B inserts a **new** eligible immutable edge, insert exactly one feed row in the **same writer transaction**. Eligible: `device_endpoint_role=src`, `direction=outbound`, `peer_scope=external`, `source_event_family IN (dns,tls,quic)`. Inbound, local, unknown-direction and non-candidate rows generate no feed. Idempotent replays of existing edge IDs generate no extra outbox row. Feed sequence never reused after deletion; FK cascade on authorized edge retention removes the feed row. Preserve source edge and checkpoint transactional semantics.

Provide read-only bounded internal interfaces:

- `read_service_recognition_feed(after_feed_seq, limit<=256, deadline)` -> ascending feed sequence with exact edge DTO and provenance.
- `recognition_feed_bounds()` -> retained floor and high-water, both nullable where appropriate.

Validate all DTO fields; use existing exact binding / provenance constraints; no unbounded SELECT or index-bypassing table scan. A feed retention gap is detected, **not silently skipped**.

### B1.4 Authoritative Registry change index and replay trigger (Addendum TL-R1)

**Never** use the old non-AUTOINCREMENT `projection_registry_binding_events.binding_event_id` as the durable NI-04 cursor. Retain that original audit table unchanged. The authoritative change index is a bounded current-state index (one retained row per Site+MAC), not a new append-only full Registry audit log.

- On newly established authoritative Site+MAC->Device identity: in the same NI-02B transaction as the binding update, delete prior index row for that exact Site+MAC and insert a new row to allocate a non-reused `change_seq`.
- No fresh sequence for periodic revalidation or safe-reason-only changes.
- If binding leaves authoritative state or is removed, ensure obsolete authoritative index data is no longer treated as valid: remove it in the same transaction, without allocating a new authoritative sequence; FK cascade on binding deletion must also work. This is the implementation consequence of the authoritative-only index/read invariant, not a new identity algorithm.
- Seed currently authoritative bindings at extension install even if historical Registry audit events were retained away.
- Reader `read_authoritative_binding_changes(after_change_seq, limit<=128, deadline)` returns ascending index rows, validating each against the **same-snapshot** current binding: exact Site, canonical MAC, state authoritative, non-null exact Device. Any mismatch fails closed; **never** publish a positive under an obsolete identity.

Changes are coalesced by the per-Site+MAC current-state index; missing index rows due to legitimate binding removal do not make a historical source fact positive. When worker reads a page, it must atomically enqueue deterministic replay jobs and advance `last_binding_change_seq` in its own store; separate execution of jobs is bounded/exact Site+MAC.

### B1.5 Deliverables/gates

- Exact dual-mode validator tests: baseline core-only, core+extension, unknown object, mutated core, incomplete extension, missing metadata, repeated install and crash at each DDL/DML point.
- Atomic writer/feed eligibility tests, FK/retention tests, idempotency tests, sequence non-reuse and no core contract mutation.
- Registry tests R1-QA-01 through R1-QA-08, R2-QA-01 through R2-QA-12, including original binding-event ID reuse and index cleanup on authoritative downgrade.
- Benchmark on representative workload: NI-02B p95 batch-commit latency regression <=10%; projected-edge throughput regression <=5%; checkpoint/replay semantics unchanged; no full-table scan for feed API.
- Produce compatibility-bridge proof and a migration/rollback safety runbook; **do not execute migration on production**.

## 4. WP-B2 — dedicated NI-04 materialized SQLite store

Path: `/opt/CaptivePortal/data/network_service_intelligence.sqlite3`. Owner: `app/network_service_recognition`; only background worker may write; Admin query-only reader. PRAGMAs `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=500ms`, `wal_autocheckpoint=1000`; single-writer lock analogous to established safe repository pattern. Closed/versioned schema, validation and integrity startup gates; no auto-repair of corrupt DB and no unsafe reader fallback.

Implement **the parent v1 entities amended by v1.1**, notably **do not create `device_category_rollups`**:

1. `service_materialization_schema` singleton with `schema_version=1`, contract 1, `algorithm_version=background-service-materialization.v1`, timestamp.
2. `service_materialization_generations`: exact taxonomy/manifest/ruleset IDs, versions and digests; `generation_id`, states `building|active|superseded|expired|failed`; timestamps, backfill boundary, `live_feed_start_seq`, publishability. At most one active.
3. `service_recognition_observations`: immutable positive events, deterministic `service_observation_id`, `generation_id`, `edge_id`, `source_observation_ref`, exact `site_id+device_id+client_mac`, `registry_binding_change_seq`, observed timestamp/family, service/org/category IDs, directly-supported evidence and rule lineage; unique `(generation_id,edge_id)`.
4. `device_service_rollups`: unique `(generation_id,site_id,device_id,service_id)`, bound canonical MAC, display fields, `last_observed_at`, exact latest observation ID. New confirmed observations advance latest timestamp only if later; never create duplicate UI entries.
5. `device_materialization_state`: exact generation/site/device/MAC, current authoritative binding and `registry_binding_change_seq`, source/attribution/linked-pending/recognition coverage, coverage window origin and evaluation timestamps, limitation and last materialized timestamps. **Also create/update state for a safely evaluated candidate producing `unknown`/no positive**, so no-result versus never processed can be distinguished.
6. `service_materialization_checkpoints`: per-generation live feed sequence and authoritative binding-change sequence; bounded backfill state/cursor, timestamps.
7. `service_binding_replay_jobs`: deterministic job ID from `(generation_id,change_seq,site_id,client_mac,device_id)`, generation-scoped uniqueness, exact targeted Site+MAC, bounded time window/paging cursor and job state.
8. `service_materialization_runtime`: state `initializing|backfilling|usable|lagging|source_unavailable|recognition_unavailable|capacity_halted|blocked_conflict|stopping`, current active generation, feed high-water and committed cursor, last poll/commit/coverage reconciliation, safe reason.

For **each successful live batch**, one NI-04 `BEGIN IMMEDIATE ... COMMIT` atomically persists positive observations, rollup updates, materialization coverage and feed consumer checkpoint. If transaction fails, checkpoint remains old. For authoritative-binding changes, replay enqueue plus binding cursor advance is one transaction. Crash before/after commit must replay idempotently; all insert conflicts must be verified rather than overwritten with contradictory provenance.

No raw SNI/DNS/IP, ports, packet payload or full NI-01 JSON in this DB or telemetry. Store is not an unbounded evidence archive. Observation retention <=14 days, rollup removal beyond authorized retention, at most one active and one immediate superseded generation, normally 24h rollback grace. SQLite total footprint default 512 MiB, configurable only within 128 MiB..2 GiB. If space pressure persists after authorized bounded retention and safe WAL maintenance, `capacity_halted`, preserve facts, **do not advance checkpoint**, never delete current positives to appear healthy, no hot-path `VACUUM`.

## 5. WP-C — reusable evaluator + isolated background worker

### C.1 Extract exactly one evaluator

Refactor existing NI-04 query-time evidence validation into a **single reusable evaluator**, not a copy-pasted independent matcher. Proposed interface:

`ServiceRecognitionEvaluatorV1.evaluate(projection_fact, source_evidence, authoritative_identity, recognition_bundle, evaluated_at_utc)`.

Keep `match_direct_sni_v1` and knowledge artifact files unchanged. Before positive recognition validate exact Site/MAC/Device identity, authoritative NI-02B binding, outbound/external/source role, full source observation identity and generation, capture source, scope and digest, timestamp, eligible family TLS/QUIC, retained endpoint tuple when applicable, payload exclusivity and valid retained canonical direct SNI, active/eligible unique rule and admitted digests. DNS is **not** a positive source in V1; preserve its existing contribution to limited coverage. Ambiguous, unknown, expired or missing evidence cannot become a positive. A legitimate expired evidence item marks incomplete/limited; an I/O/storage failure leaves batch checkpoint unadvanced.

Preserve source cross-checks **before positive materialization**. The evaluator must not attach any event to a Device merely because its current IP or a hostname matches.

### C.2 Worker isolation and lifecycle

Implement NI-04 worker/CLI under `app/network_service_recognition`, with deployment unit `network-service-recognition.service`. `After=network-metadata-projection.service` as soft ordering; **no hard `Requires=` coupling** to portal or NI-02B. Owns one writer process; portal still operates if worker is absent or lagging.

Cycle priority: (1) live NI-02B feed, (2) exact authoritative-binding replay queue, (3) coverage reconciliation, (4) bounded existing-24h backfill, (5) retention/maintenance. Backfill must yield to live backlog. Idle poll every 1s without idle write amplification; unchanged heartbeat persistence no more frequently than every 10s. Bounds: feed <=256, NI-01 exact refs <=256, binding changes <=128, touched Device coverage <=128 per pass, at most one active live batch, worker-local evidence batch <=30s. If deadline exceeded or required data unavailable, no source cursor advance, reflect lag/availability honestly and retry with bounded backoff (no aggressive spin under disk pressure).

Only worker may query NI-01 raw evidence. Use exact-ref reader and established validation. No full-history polling or periodic full-table scans. Process termination/restart must flush/checkpoint only already complete transactions, preserve committed state and support safe resumability.

### C.3 Late authoritative binding

When a relevant edge is committed but Device identity is not authoritative, do **not** create a Device fact. The live cursor may move because the authoritative binding change index provides targeted future replay. Read index rows and create deterministic durable replay jobs *before* advancing `last_binding_change_seq`, in the same store transaction. Each job scans **only** the exact Site+MAC with pages <=128 and retained product window; must recheck current binding and evidence before any positive. A late pending `src` resolution creates a new NI-02B edge/feed seq; a peer-only late resolution does not rewrite existing confirmed `src` evidence. No cross-MAC replay.

### C.4 Coverage and statuses

Worker reads the additive NI-02B **coverage-only** bounded interface (no Admin scan) for touched/recent/pending devices, <=128 Devices per pass, per-Device normal retry >=30s and passes every 30s when work exists. Preserve existing NI-04 V2 mapping for `pending_attribution` versus `attribution_authority_unavailable`; materialization health is an **additional independent dimension**, never hidden by repurposing source/attribution state.

Normal event-to-store latency SLO from NI-02B edge commit: p95 <=10s, p99 <=30s. `current`: caught-up feed and successful upstream verification <=10s; `lagging`: backlog or verification age >10s <=120s; `unavailable`: mandatory upstream unreadable or verification age >120s. Never advance cursor to make status look healthy; fail closed on feed retention gaps, identity contradiction and lineage conflict. Existing confirmed positives should survive worker outage, if active artifact/identity still valid.

### C.5 Rule artifact generation

Each exact admitted taxonomy+manifest+ruleset tuple owns a separate generation; no mixing in published V3. A newly admitted tuple creates `building` shadow generation, captures feed high-water, processes live feed and bounded 24h backfill, then is atomically promoted only when validated and caught up. Old active remains publication authority until promotion. An expired knowledge generation cannot silently remain current publication authority. Missing/expired historical evidence makes completeness partial; no fabricated results.

## 6. WP-D — bounded 24h historical backfill

A new materialized store starts empty; reconstruct the existing user-facing **24-hour** window, not 14 days of UI history. Capture `H` = NI-02B feed high-water when new generation is created. Consume **new** feed rows with `feed_seq>H` immediately, and independently scan the existing 24h NI-02B projection window in ordered pages `(event_at,edge_id)` <=128 per Site. Backfill maximum one page per second and only when live feed is caught up; checkpoint Site/event/edge cursor in NI-04 SQLite atomically with materialized rows. Resume after crash without rescanning from zero; deterministic observation identity handles overlap with live feed and late-binding replay.

Retained exact NI-01 evidence and authoritative identity are mandatory. Missing/expired history cannot become positive or complete coverage. Detect source/feed retention gaps. Existing seeded binding change-index rows may create replay overlapping backfill; idempotency must prevent duplicates and must not mislabel the 24h window complete. Do not run full historic reprocessing on Admin refresh, and do not block live detection waiting for backfill.

## 7. WP-E — fast materialized Admin API V3 + minimal UI update

Maintain path:

`GET /admin/api/v1/sites/{site_id}/devices/{device_id}/service-intelligence`

Mode `off` retains legacy V2 publication; `shadow` builds/compares behind legacy V2; mode `serve` composes `MaterializedDeviceServiceReadService`, returns **`api_version=admin.device.service-intelligence.v3`, `schema_version=3`**, with existing V2 fields unchanged in meaning and exactly one new nested object:

```json
"materialization": {
  "state": "current | backfilling | lagging | unavailable | capacity_halted | conflict",
  "window_coverage_state": "complete | partial | unknown",
  "last_successful_update_at_utc": "timestamp | null",
  "lag_seconds": "nonnegative integer | null"
}
```

**Serve mode read-isolation invariant:** after existing Admin policy and authorized Device gateway check, the NI-04 read service opens ONLY the NI-04 materialized SQLite in query-only mode. No NI-01, NI-02B, matcher or projection 24h scan is imported/called from this path, even when materialization fails. One runtime/generation read, one device state read, at most 13 recent service rollup rows (publish <=12), and one 24h last-service indexed row; categories computed in memory from selected <=12 service rows only. Do **not** create or independently query `device_category_rollups`.

At evaluation time T:

- Recent Services: `last_observed_at >= T-1h`, order `(last_observed_at DESC, service_id ASC)`, **LIMIT 13**; the 13th row means recognition/publication is limited; publish only first 12.
- Categories: uniquely derive from those selected first 12 rows, timestamp the latest selected observation per category, order `(last_observed_at DESC, service_category_id ASC)`.
- Last Service Observation: `last_observed_at >= T-24h`, order `(last_observed_at DESC, service_id ASC)`, LIMIT 1, with exact latest observation ID.

No write is necessary when a window simply expires. Empty results **cannot** mean "no activity". Existing positive results can be published under source/attribution/materializer lag with truthful coverage, but **no** `no_supported_result_observed_with_sufficient_coverage` unless all Architecture v1 §17 gates hold: exact authoritative identity, valid active artifact, materializer current, feed caught up, full 24h backfill/coverage from `T-24h`, usable source + attribution + recognition, no device-linked pending or unresolved limitation in window.

Add V3 `evidence_state=materialization_incomplete`, with precedence: nonauthoritative identity -> `identity_pending`; valid stored positive -> `supported_results_present`; incomplete materialization -> `materialization_incomplete`; source/attribution/recognition limitations -> existing V2 messages; only then sufficient-coverage no-result state. Preserve truthfulness of `availability_state`, freshness and V2 coverage meanings; do not fabricate evaluated timestamps or silently mix rule generations. Maintain response <=16 KiB and existing auth/access/error contracts.

Update only existing Device Service Intelligence component of `app/admin_web/static/admin.js`: validate V3 strictly and show one `Materialization: <state>` line. Positive+lag: show evidence and "Background Service Intelligence is behind; newer activity may be missing." No positive+incomplete: "Service Intelligence is not fully materialized for this window; activity is unknown." No redesign of Device Card. Do not suggest that network evidence proves watching a video or user interaction. Keep modes and V2 compatibility explicit; do not remove old path before separately approved cutover/rollback window.

Latency acceptance in representative lab: materialized reader p95 <=50ms / p99 <=100ms, authenticated API p95 <=250ms / p99 <=500ms, hard NI-04 materialized read budget <=1s. Treat outlier disk stalls as detectable degraded/unavailable, never trigger on-demand source scan to hide them.

## 8. WP-F — mode, shadow, acceptance, release and rollback

Expose one closed deployment mode `NETWORK_SERVICE_MATERIALIZATION_MODE=off|shadow|serve`, default `off`. Preserve `WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED` as existing product enablement. `off` must work against Core-only DB; `shadow` starts worker/store but API remains V2 legacy authority; `serve` reads materialized V3 only with no automatic on-demand fallback. Any mode change or prod install is a **separate Owner-approved operational action**.

Shadow admission requires: valid active generation, completed required 24h backfill, live feed caught up, no feed retention gap, current coverage reconciliation, `PRAGMA quick_check=ok`, no upstream mutation. Compare legacy and materialized confirmed **positive sets at the same evaluation time** for deterministic sampled Devices; extra materialized positives, provenance mismatch or cross-Device leak = FAIL. Legacy deadline failure is recorded distinctly, not misinterpreted as mismatched facts. Test controlled YouTube regression for MAC `C2:32:F5:4E:43:61`, Device `b7a34589-021a-5b2e-8e22-fdee235543ce`, Site `6a64f17630da7c70d232187a`, where evidence is still retained; do not put real MAC/Device IDs in logs or public telemetry. Use synthetic fixtures in public tests.

**Mandatory release order in RUNBOOK (not authorization to execute):**

1. R2-0: capture HEAD/tree, DB size/version/integrity, verified recoverable backup/snapshot; no concurrent backfill.
2. R2-1: deploy accepted compatibility bridge with mode `off` and extension installer disabled. Restart projection readers including CaptivePortal/Admin **first**, confirm Core-only reads. Then restart NI-02B bridge writer, confirm existing progress. Record `NI04_MAT_COMPAT_BASE_SHA`.
3. R2-2: only after every production projection DB consumer runs bridge-compatible code, enable one-time extension install; restart **NI-02B alone**, ensure supervisor `TimeoutStartSec >=180s` and SysAdmin startup budget. No worker/backfill concurrently. Verify complete extension schema, quick_check, runtime and checkpoints.
4. R2-3: owner-authorized `shadow`; live first, bounded 24h backfill; compare and monitor.
5. R2-4: owner-authorized `serve` after all gates PASS.

**Rollback floor:** after extension installation, NEVER use `b1442efc...` against migrated DB; use the accepted `NI04_MAT_COMPAT_BASE_SHA` or later extension-aware release. An explicit Owner rollback may switch `serve->shadow/off` or disable Service Intelligence, but extension feed/index upkeep MUST continue while installed. No destructive schema downgrade/drop/DB restoration to trick old validators into accepting schema; NI-01/NI-02B evidence stays intact.

Resource gates: NI-02B write overhead p95 <=10%, edge throughput loss <=5%; worker steady-state RSS delta <=64MiB excluding page cache; one worker batch, <=256 feed/evidence, <=128 binding/coverage and backfill, per-Device reconciliation cadence >=30s; no busy-loop during disk stalls, WAL unbounded growth, fsync-per-observation or full source scans. Portal/Auth/CAPPORT availability and latency do not regress. Simulate 30s worker deadline, full disk, unreadable database, feed gap, partial schema, conflict and slow-start conditions.

## 9. Deterministic acceptance / QA matrix — ALL REQUIRED

Implement every parent Architecture Contract v1 AC-M01..AC-M25 **plus** v1.1 Addendum R1-QA-01..08, R2-QA-01..12, R3-QA-01..06. Minimum named groups below; report test IDs, command, count and exact PASS/FAIL:

- **Recognition safety:** exact authoritative Site+Device+MAC, peer-pending allowed only with authoritative src, pending-src late edge, ambiguous/missing/expired evidence, malformed or contradictory provenance, no cross-Device/Site, no IP-only/SNI-only attribution, unchanged matcher and NI-03.
- **Feed delivery:** same-transaction eligible outbox, no ineligible feed rows, idempotent edge replay, AUTOINCREMENT non-reuse, FK retention cascade, bounds/highwater/retention-gap and no full scans.
- **Registry change index:** seeding with empty audit history, audit event ID reuse, retention, removed/re-created binding, authoritative downgrade cleanup, no extra sequence on periodic validation, exact Site+MAC replay only; crash before/after enqueue checkpoint.
- **Migration/compatibility:** CORE_ONLY/CORE_PLUS_EXTENSION validated, partial/unknown object fails, interrupted installer atomic, repeated install no-op, bridge preserves feed while mode `off`, old baseline incompatible post-migration, no unsafe reader during install, slow-start simulated.
- **Store durability:** transaction checkpoint atomicity before/after crash, replay exactly once, immutable positive facts, generation isolation and promotion, caps/retention, safe WAL, no raw sensitive fields.
- **Backfill:** `H` handoff, live-priority, 24h limits, paged resume, one page/s throttle, no duplicate with seeded binding replay, gap/incomplete status.
- **Time windows/categories:** 60m/24h expiry without worker writes or browser interaction; 13th recent service excluded and recognition limited; categories only from first 12 selected services; deterministic service/category ties and shared categories.
- **Read-only API:** fail-if-called NI-01/NI-02B/matcher doubles in `serve`; strict authorized Device identity; no fallback on unavailable store; V3 field/schema/size/error validation and V2 off/shadow compatibility.
- **Failure honesty:** worker stopped/behind, source outage, feed gap, artifact expired, DB corrupt/busy, capacity halted, registry conflict — preserve admissible positive facts without unsupported negative claim.
- **Performance:** stated reader/API/event-to-store SLOs, NI-02B write overhead and throughput gates, RAM/I/O thresholds and independent portal/auth smoke checks.

Maintain original regression tests without weakening assertions or skipping known failures. CI PASS alone does not authorize deploy.

## 10. Implementation execution order / review gates

Coder may implement one umbrella task in one feature branch, but create independently reviewable commits and evidence for these gates:

**G0 Baseline:** pinned SHA/tree, clean working tree, tests and code-location inventory, dependency/consumer inventory. If baseline drift: HOLD.

**G1 Bridge:** compatible schema validator and optional extension-aware writer/reader with installer OFF; baseline Core-only tests PASS; record proposed bridge commit and prove it is valid rollback floor. No migration performed.

**G2 B1 migration/outbox:** transactional installer, atomic feed, authoritative change index, bounded internal APIs; all R1/R2 tests, microbenchmarks, schema migration fixture evidence PASS.

**G3 B2/C:** single-writer materialized store, common pure evaluator, worker, checkpoints/replays/coverage, retention, rule generation; deterministic fail-closed and crash tests PASS.

**G4 D:** resumable live-first 24h backfill, gap tests and bounded-load tests PASS.

**G5 E:** materialized V3 API and minimal UI, bounded indexed reads, old V2 off/shadow still works; R3 category tests and read-isolation tests PASS.

**G6 F:** complete shadow comparison tooling, release/rollback runbook, performance/failure suites, independent regression gates; prepare PR. Owner authorizes production **later**.

Do not omit a gate to save time. Do not present expected results as if measured. Stop and report any architecture contradiction, unverified performance claim, migration safety issue or blocked test instead of inventing a workaround or weakening fail-closed rules.

## 11. Required handoff to Tech Lead / Research & QA

Deliver in PR plus a concise evidence bundle:

1. PR URL, branch, all exact commit SHAs and tree at HEAD; separate `NI04_MAT_COMPAT_BASE_SHA` candidate.
2. File-by-file change inventory: especially proof of untouched NI-01/NI-02A/NI-03/Portal/Auth and original NI-02B attribution algorithms.
3. Implementation map per WP and Architecture v1/v1.1 section; explicit deviations **none** or numbered HOLD items.
4. Schema DDL, indexes, validation modes, migration test results, crash/rollback simulation results, extension absent/present compatibility fixtures.
5. Durable feed/change cursor tests, gap/replay/late binding and no duplicate facts, plus safe index downgrade cleanup.
6. Worker lifecycle/status and I/O/latency results with actual test environment, number of events, durations, p95/p99; clearly distinguish lab from production.
7. Full test inventory and commands: AC-M01..25, R1-QA-01..08, R2-QA-01..12, R3-QA-01..06, existing repository regression suite; exact PASS/FAIL counts and any skipped tests (skips require review).
8. Sample anonymized V3 response, UI screenshots if safe, API V2 off/shadow compatibility and failed-source statuses; **no real user traffic/private hostnames** in PR logs.
9. Shadow comparison harness and controlled YouTube regression recipe, with sensitive MAC/device validation performed only within authorized protected environment.
10. Operator runbook with mandatory order, backups, `TimeoutStartSec>=180s`, bridge SHA rollback floor, explicit forbidden old SHA, non-destructive rollback and stop/hold conditions.
11. Explicit checklist that **merge=NO, deploy=NO, prod migration=NO**, and record of no production mutations during Coder work.

Research & QA independently verifies acceptance. Tech Lead issues separate merge recommendation only after all evidence gates PASS. Owner separately authorizes each production stage, especially bridge rollout, extension install, shadow and `serve` activation.

## 12. Final task directives

```
ARCHITECTURE = ACCEPTED (v1 + v1.1)
CODER = GO FOR IMPLEMENTATION IN FEATURE BRANCH ONLY
SCOPE = WP-B1 / WP-B2 / WP-C / WP-D / WP-E / WP-F
PRODUCTION CHANGE = NO
MIGRATION EXECUTION = NO
MERGE = NO
DEPLOY = NO
AUTO FALLBACK IN SERVE = FORBIDDEN
NI-05 = HOLD
NI-06 = HOLD
DELIVERABLE = REVIEWABLE PR + COMPLETE TEST / MIGRATION / PERFORMANCE EVIDENCE
```

**Product contract:** Discover -> validate identity and evidence -> recognize in background -> persist once -> update Device rollup -> render from ready materialized store. Opening a Device Card must not trigger a recomputation.
