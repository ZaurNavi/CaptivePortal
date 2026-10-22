# NI02B-EXTERNAL-PEER-DEV-RESET-ARCHITECTURE-EXCEPTION-v1

**CaptivPortal / Architect → Tech Lead**  
**Date:** 2026-10-14 (Asia/Baku)  
**Status:** `ARCHITECTURE DECISION — FOR TECH LEAD IMPLEMENTATION-CONTRACT REVIEW`  
**Reference investigated:** `ZaurNavi/CaptivePortal@f324c1e157b71802acda14a797c0e0f6747b6276` (repository source, **not** independently verified live production HEAD/TREE).  
**Authority:** Owner request `CAPTIVPORTAL-NI02B-EXTERNAL-PEER-ATTRIBUTION-ARCHITECT-REVIEW-v2-DEV-RESET-2026-10-14`; prior `TASK-DTI-NI-04-ATTRIBUTION-RECOVERY-ARCHITECTURE-CONTRACT-v1` §11, §16.  
**Authorization:** Architecture only. **No Coder task, production deletion, restart, merge or deployment is authorized by this document.**

## 1. Decision

```text
FROZEN_CONTRACT_EXCEPTION = APPROVED — NARROW
NI02B_EXTERNAL_PEER_DHCP_SHORT_CIRCUIT = APPROVED — TRUSTED NEGATIVE SCOPE ONLY
NI02B_OLD_PENDING_RECOVERY = NOT REQUIRED
OWNER_DEV_RESET = APPROVED IN PRINCIPLE — EXECUTION SEPARATELY GATED
NI01 / NI02A / VISITOR_REGISTRY / OMADA / PORTAL_AUTH = PRESERVE
```

The **only** superseded rule from Attribution Recovery v1 §11/§16 is mandatory DHCP resolution for an endpoint proven outside the admitted *guest IPv4 DHCP attribution domain*. For that endpoint NI-02B must return a distinct terminal, non-identity outcome, **not** call NI-02A, and **not** generate retry/pending. All other identity, time, Site, guest-DHCP coverage, immutable-edge and confidence semantics remain frozen. This exception is not permission to suppress actual guest attribution gaps, delete arbitrary pending during ordinary operation, or infer Internet reachability from an IP address.

The observed `159,042 → 160,057` pending increase and sampled out-of-scope records are sufficient to motivate a targeted fix; they **do not** establish that every pending entry or all disk I/O has this cause.

## 2. Trust boundary and endpoint algorithm

For each `src` and `dst` independently, use the **same NI-01 validated source observation** (`NetworkMetadataProjectionSourceRecordV1`) and its **exact generation-bound** `CaptureScopeBindingV1`. The NI-01 source read path already verifies source generation identity, `capture_source_id`, `site_id`, `network_scope_id`, binding digest, canonical IPv4 CIDRs and `within_intended_scope`. Strengthen the validation to check `event_at >= binding.valid_from_utc` before the external-side shortcut if not already proven in the trusted reader. **Never** substitute current environment CIDRs for the binding that applied to this event.

**Admission precondition:** the specific Site/source/binding digest and its IPv4 CIDR set must have an Owner/SysAdmin-reviewed proof that they represent the guest DHCP attribution domain *at this pre-NAT capture point*. Baseline DTI-00 documents pre-NAT RSPAN placement, but that historical proof must be compared to current topology/configuration before activation. `within_intended_scope` proves that at least one endpoint matched an intended IPv4 CIDR; it does **not**, by itself, prove that the other endpoint is public Internet, nor prove that topology has never changed. The implementation must pin the admitted Site + capture source + scope identity/digest for the new projection run and reject a new/unadmitted binding or unknown placement **without creating Device edges**. A change of scope/topology requires renewed admission; an unreported physical topology change cannot be detected solely from the NI-01 event schema and must not be claimed as automatically detected.

Closed per-endpoint classification:

| State | Condition | Action |
|---|---|---|
| `in_guest_scope` | Canonical IPv4 belongs to this validated/admitted event-time guest CIDR set | Existing NI-02A temporal DHCP resolution; original `resolved / ambiguous / unattributed / unavailable / outside_historical_horizon` rules |
| `outside_guest_scope` | Canonical IPv4 **does not** belong to the admitted event-time guest CIDR set, with Site, generation, digest, placement and time all trusted | New NI-02B **terminal** result `not_applicable_outside_guest_scope`; **zero** NI-02A lookups/retries for that endpoint |
| `unknown_scope` | Missing/invalid/mismatched binding or Site; changed/overlapping scope authority; unproven NAT/placement; insufficient provenance | **Fail closed**: stop/block the affected projection batch with a safe diagnosable error; no invented MAC, edge, false completeness or silent checkpoint |
| `endpoint_absent` | No endpoint address | Existing distinct terminal absence; never treat as outside scope |
| `unsupported_address_family` | IPv6 (no admitted guest DHCP-v6 authority) | Existing state; no IPv4-DHCP inference, no new guest edge |

Private IPv4, management VLAN, router/NAT peer and another Site are **not** synonymous with public Internet: a *proven* outside-guest-CIDR endpoint is **not a guest-DHCP candidate**, but remains merely `external` in the existing **relative-to-guest-scope** peer terminology. If an IP is inside the admitted CIDRs but actually belongs to statically configured infrastructure, no IP-only exception is authorized: retain original NI-02A uncertainty until separately proven.

The new terminal code is **NI-02B-owned**, never a newly invented NI-02A answer. It is distinct from `resolved`, `unattributed`, `endpoint_absent`, `unsupported_address_family` and `unavailable`. The side has no guest MAC, device ID, DHCP binding or positive attribution source. Missing scope proof may not take this branch.

## 3. Edge and pending semantics

- **Guest src → trusted outside-guest dst:** resolve `src` through NI-02A at `event_at`. If authoritative, emit **one `src` device edge** (`peer_scope=external`, `direction=outbound`, `peer_attribution_state=not_applicable_outside_guest_scope`, peer binding `null`). The `dst` does not create a guest edge or pending.
- **Trusted outside-guest src → guest dst:** mirror behavior; if guest `dst` resolves, emit **one `dst` edge** (`direction=inbound`). No fabricated remote source Device. NI-04 outbound service-feed policy remains unchanged.
- **Guest src ↔ guest dst:** independently check both sides at event time; allow **0/1/2** proven edges by the existing rules, retain actual `unavailable` pending/retry and real DHCP coverage gaps.
- **Unknown / invalid provenance:** no positive edge or downgraded fallback. An in-scope guest `unavailable` remains pending under existing bounded semantics even when its external counterpart is terminal.
- Immutable edge ID, one edge per (`source_observation_ref`, `device_endpoint_role`), exact Site+MAC, temporal binding, Registry authority, feed candidate eligibility and NI-04 confirmed-positive-vs-coverage separation remain unchanged. Never reclassify previous edges in place.

## 4. Versioned minimal change (no data-preserving migration)

The existing `peer_attribution_state` and `src_snapshot_state/dst_snapshot_state` are SQLite **closed CHECK enums**; the terminal code **cannot** simply be written into the current Core V1 file. Therefore adopt a **fresh NI-02B Core/Projection Contract V2** (new schema/algorithm identity and matching checks; no in-place alteration of old V1 DB). Keep the same edge shape and NI-04 delivery extension data model; retain extension contract V1 **only if** exact new Core-V2-plus-extension validation is explicitly implemented and tested. NI-03/NI-04 typed consumers accepting projection contract identity must be updated to V2. NI-01 schema, NI-02A result contract, matcher/rules, Guest/Auth/Omada and Registry contract stay unchanged.

Narrow production-code targets (confirm precise paths at pinned new HEAD):

```text
app/network_metadata_projection/service.py            # scope guard; terminal outcome; edge/pending
app/network_metadata_projection/models.py             # NI-02B closed outcome / V2 identity
app/network_metadata_projection/schema.py             # new Core V2 fresh-schema checks
app/network_metadata_projection/repository.py         # V2 identity; explicit reset floor consumption
app/network_metadata_projection/config.py             # admitted scope pin, if needed
app/network_metadata/projection_source.py              # minimal verified event-time/scope read proof
app/network_metadata_projection/read_service.py       # V2 read/status acceptance
app/network_metadata_projection/service_delivery_read_service.py # V2 feed candidate gate
app/network_metadata_projection/cli.py                 # optional narrowly bounded reset/bootstrap CLI
app/network_metadata_projection/telemetry.py           # only if bounded no-PII reason/counter needed
app/network_service_recognition/**                     # only exact V2 validator/admission compatibility
focused NI-02B / NI-03 / NI-04 tests
```

No generic refactor, no second DHCP database/collector, no new online lookup, no NI-01 acquisition redesign. **Do not change `ALGORITHM`/schema identity without updating all strict validators, code-generated signatures, tests and fresh initialization.**

## 5. Chosen reset: fresh NI-02B + NI-04, preserve NI-01/NI-02A

**Destructive list — exact owned files to replace, resolved from effective config and independently verified before action:**

1. `NETWORK_METADATA_PROJECTION_DB_PATH` (default `/opt/CaptivePortal/data/network_metadata_projection.sqlite3`) and its closed SQLite `-wal`, `-shm`, `-journal`: *all NI-02B Core tables including ~160k pending, edges, projection-private identities/bindings/events, runtime state, source checkpoints, runs; its NI-04 delivery extension meta, feed, authoritative binding-change index, internal schema objects*.
2. `NETWORK_SERVICE_MATERIALIZATION_DB_PATH` (default `/opt/CaptivePortal/data/network_service_intelligence.sqlite3`) and its closed SQLite sidecars: *all derived NI-04 materializations, generation state, service rollups, replay jobs and consumer cursors*.

**Explicit KEEP:** `NETWORK_METADATA_DB_PATH` (default `network_metadata.sqlite3`, NI-01), `NETWORK_ATTRIBUTION_DB_PATH` (default `network_attribution.sqlite3`, NI-02A), `VISITOR_REGISTRY_DB_PATH` (Visitor Registry), Omada, Guest Auth/CAPPORT/session data, Admin Settings/credentials, other CaptivPortal/Analytics stores, Suricata capture producer and its production Fingerprint path. NI-03 is a reader of NI-02B: it has no separately named reset DB in the inspected code. No NI historical backup is a mandatory gate.

**Important clean-start rule:** NI-01 retains old observations. Simply deleting NI-02B DB would replay old retained NI-01 data. Do **not** pretend a skipped observation was processed by forging `projection_source_checkpoints` (those remain true processed checkpoints). Introduce the smallest explicit **dev-reset source floor** in Core V2, separate from processed checkpoints: for each already existing NI-01 source generation at an exact consistent read snapshot, persist the identity/offset of its last retained normalized observation and the reset boundary. Future NI-02B polling uses `max(durable_processed_checkpoint, explicit_reset_floor)` as its *read-after* boundary; new source generations start naturally. Floors are deliberate Owner-authorized **discard boundaries**, not evidence of completed projection. Populate floors from the verified NI-01 read boundary (not guessed file size/current clock). The normal processed checkpoint is advanced only by committed new dispositions. After restart, the floor survives; a second explicit reset establishes a fresh floor. Test snapshot concurrency and retention across restart.

**Release/runbook sequence, separately authorized for operator execution:**

1. Pin **actual** GitHub/prod `HEAD`+`TREE`, current config paths and effective Site/scope, current topology/NI health, all open DB readers/writers, exact wipe file list and exit conditions. Confirm new version-compatible artifacts installed but do not start them against old V1 DB. Operator has explicit separate reset/deploy go/no-go.
2. Keep NI-01, NI-02A, Guest Auth, Omada and Visitor Registry running. Stop **NI-04 writer first, NI-02B writer second**; stop/drain the exact NI readers only as required for SQLite-safe replacement. Ordinary Admin pages may temporarily show `unavailable`, **not** historical positive facts presented as fresh. Do not stop the main CaptivPortal/auth service merely to simplify deletion. If safe reader quiescence cannot be established, **HOLD** file replacement and define a separately owner-authorized read-drain window.
3. While NI-02B is stopped, take a **single consistent read-only NI-01 generation/observation-tail snapshot**. Prepare clean V2 NI-02B DB in a staging path, atomically persist reset floors and new schema; install/validate exact NI-04 feed/binding-change extension in that new DB. Prepare fresh NI-04 DB (cursor=0, no former generations/rollups). No preserving old 160k rows, no old replay/backfill work.
4. With **all DB file handles/SQLite WAL sidecars quiesced**, replace exactly the two selected owned DB groups. Do not unlink or rename a live SQLite WAL database. Never restart a partially switched pair. If interrupted: keep NI consumers offline, repeat deterministic staging/validation of **both** stores, then resume; no opportunistic old-data migration. Before start check both schema signatures, `quick_check`, foreign keys, extension, reset floors and empty NI-04 cursors.
5. Start **NI-02B first**, validate reads of only post-floor NI-01 records, current DHCP/Registry bindings and new feed creation. Then start NI-04 in a brief bounded `shadow` validation (not multi-day); promote to `serve` only after new-data smoke and separate Owner production-activation authorization. Restore Admin NI reads. No automatic startup loop, rollback to incompatible pre-V2 code, or stale NI-04 results.

## 6. Fast admission / separation of failure causes

**Mandatory deterministic tests:** Owner request **T01–T11** in full, including guest→outside and reverse (no remote DHCP lookup/pending); guest↔guest both temporal lookups; uncertain scope/NAT/Site/IPv6; real guest coverage gap; exact two-DB reset/surviving protected stores; interrupted/repeated reset; NI-03/NI-04 new-only facts; strict enum/telemetry, concurrency and zero online recognition lookups. Explicitly test old Core V1 + new code **fails closed** rather than quietly writing inconsistent rows, and that V2 + old code is not permitted as rollback.

**Live smoke:** after stabilization, use a **15-minute** bounded window of natural load with at least one Owner-controlled client flow. Compare number/rate of new `pending`, distribution by *which endpoint* is actually awaiting guest DHCP, NI-02B source-poll lag (including p95 and trend), new edge/feed counts, NI-04 cursor convergence, NI-03/04 new facts, and disk latency/IOPS. **Pass the specific fix** only if trustworthy outside-guest endpoints cause exactly **zero** new NI-02A lookups and exactly **zero** new pending roles; legitimate guest gaps may remain pending. Treat `recognition_state=limited`, real source coverage gaps and slow disk as distinct, reportable conditions. Do not require every Device to be `usable` or claim disk recovery without measured attribution. No SQLite durability relaxation and no multi-day historical QA prerequisite.

## 7. Handoff to Tech Lead

```text
ARCHITECT_DECISION = APPROVED_NARROW_EXCEPTION
FROZEN_CONTRACT_EXCEPTION = APPROVED
DEV_RESET_BOUNDARY = NI02B + NI04 ONLY
NI01_NI02A_PRESERVE = YES
VISITOR_REGISTRY_OMADA_AUTH_PRESERVE = YES
OLD_PENDING_160K_MIGRATION = NO
CORE_VERSION = NEW V2 CLEAN INIT; NO V1 IN-PLACE MIGRATION
RESET_FLOORS = EXPLICIT DISCARDED SOURCE BOUNDARY; NOT PROCESSED CHECKPOINT
CODER = HOLD PENDING TECH LEAD EXACT TASK
DEPLOY_AND_RESET = HOLD PENDING SEPARATE OWNER AUTHORIZATION
```

Tech Lead should reconcile this decision against current HEAD/TREE and publish one bounded Coder TASK plus a separate operator-only reset runbook. Architecture accepts **verified unavailability** as a safe outcome when source-scope trust is not established; it does **not** authorize silent terminal classification in that case.
