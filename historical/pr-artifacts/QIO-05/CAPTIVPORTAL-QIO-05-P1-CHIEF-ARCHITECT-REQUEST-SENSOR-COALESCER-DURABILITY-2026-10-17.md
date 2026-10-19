# CaptivPortal — Chief Architect Request: QIO-05 P1 / Sensor pre-durable ingress coalescer

**Requester:** Optimization Tech Lead  
**Status:** `ARCHITECTURE_DECISION_REQUIRED / CODE_AND_PRODUCTION_HOLD`  
**Scope:** **ONE** target only — existing `IngressCoalescer` for Fingerprint Sensor evidence spool. No changes to NI-02A coverage cadence in this request.

## Question to Chief Architect

**May CaptivPortal enable the already-existing, default-OFF `DEVICE_FINGERPRINT_SENSOR_IO_INGRESS_COALESCE_ENABLED` on production Sensor, considering that the implementation temporarily stores evidence in memory before `SensorSpool` makes it durable?** If YES, define exact acceptance, failure, replay, order, freshness, and deployment contracts. If NO, explicitly reject and identify whether only post-durable batching is admissible.

## Proven evidence

- 2026-10-16 SysAdmin full matched windows: Evidence guest write wios 6750/1254 and Sensor 2691/650 over distinct 120s windows, with physical host `/dev/sda` 127.39/88.74 completed write IOPS. No per-file causal host attribution and no claim that Sensor spool accounts for all Sensor writes.
- Accepted QIO-05 P0 Lab: duplicate-only evidence request 101 SELECT, no measured request DB/WAL writes; positive evidence creates WAL writes, one transaction per request. Changing receiver duplicate handling is NOT requested.
- Unmodified source: `SensorSpool` `journal_mode=DELETE`, `synchronous=FULL`, `enqueue` supports bounded coalesced transaction; `IngressCoalescer` default OFF, max32 events, max100ms oldest wait, max262144 serialized bytes, special barriers, fail-closed fallback. Current production flag **UNKNOWN**; remote safety preflight at 01:05 AZST had PSI full 11.66/11.39%, failing required <=5%, so no intrusive production read.
- Independent WSL LAB direct-spool synthetic 100 events: single 100 transactions vs four groups; equal persisted rows/IDs. Process-level `strace -c` (includes equal init/close) yielded `pwrite64` 2614→126, `fdatasync` 404→20 and `unlink` 102→6. This is no physical HDD promise or crash safety proof.
- Current main@`cd83c3e04233593126d247b0c96c1135f4233072` has identical `spool.py`, `ingress_coalescer.py`, `config.py` blob identity to frozen QIO-05 P0 base.

## Decisions required (numbered, explicit GO/HOLD)

**A1 — durable authority boundary:** Can Sensor return from `submit` with evidence in a volatile max100ms window? Which step is authoritative *acceptance*, and what may be lost on power loss/crash? Is ANY such loss contractually admissible for passive advisory evidence? Distinguish from NI-02A trusted DHCP facts and source-health, which must never silently become lossy.

**A2 — ordering and barrier semantics:** Must source-health events, faults, shutdown and delivery barriers flush all earlier evidence and wait until durable? Is currently coded ordering/fallback sufficient in all stop/timeout/exception paths? Define exact max age/row/byte thresholds permitted, or reject all buffering.

**A3 — replay, idempotency, crash consistency:** If abrupt exit happens with pending in-memory evidence, are raw packet sources replayable? If not, can such evidence loss ever be allowed? How must the system represent an unprovable gap (unavailable/unknown, no false healthy completeness) so no downstream fingerprint/classification/NI state falsely claims completeness? No offsets may advance beyond durable data.

**A4 — required gates for activation:** Enumerate precise deterministic Lab failure injections (before enqueue, after enqueue/pre-durable, during spool txn, after durable, before source-health barrier, shutdown timeout, duplicate/retry, capacity/exhaustion), Windows/Linux focused/full gates, sustained traffic tests and production nonsecret flag/checkpoint telemetry before optional enablement.

**A5 — rollback and consumer compatibility:** Define deploy prerequisites for toggling OFF→ON, required Owner authorization/restart, expected retention of prior spool rows and `producer_event_id`, rollback ON→OFF, safe service restart/backup plan and monitoring metrics that prove no hidden drops. Should the existing code itself be repaired before any activation?

**A6 — verdict:** Issue one of `ARCHITECTURE_PASS_CONDITIONAL_LAB_ONLY`, `ARCHITECTURE_HOLD_NEEDS_EVIDENCE`, or `ARCHITECTURE_REJECT_PRE_DURABLE_BUFFER` with unambiguous conditions. **Do not** authorize production mutation, code patch, or feature activation by this response alone.

## Explicit exclusions

No changes to `network_attribution.sqlite3` verified-through cadence, `synchronous` PRAGMAs, SQLite WAL/DELETE journal, spool capacity, dedup identities, Visit/Auth/CAPPORT, MicroK8s, journal logging, Omada, DTI, source checkpoint, or existing durable evidence. No source/production writes in this architectural analysis. An architecture approval is **not** Tech Lead implementation PASS or Owner deploy GO.

## Requested deliverable

`CAPTIVPORTAL-QIO-05-P1-CHIEF-ARCHITECT-SENSOR-COALESCER-DECISION-v1` answering A1–A6 and specifying testable safety/observability contracts, fallbacks and explicit prohibited behaviors. Tech Lead will independently review it, then either prepare a bounded lab verification TASK for Coder or reject activation and continue source attribution.
