# CAPTIVPORTAL — TECHLEAD23 → ARCHITECT
## FINGERPRINT WRITE-I/O OPTIMIZATION / WAVE 2

**Date:** 2026-10-12  
**Status:** ARCHITECTURE DECISION REQUEST — NOT IMPLEMENTATION AUTHORIZATION  
**Repo baseline:** `main@385fecebd2bd8778c3a2034514d9e72587984753`  
**Owner decision:** Fingerprint optimization is now in scope for the second wave. The earlier Fingerprint HOLD is lifted **for architecture review**, not an authorization to alter production storage semantics.  
**Other programs:** NI-05/NI-06 remain HOLD; CAPPORT/Auth and Omada controls are out of scope.

## 1. Concrete evidence and current write path

SysAdmin's previously documented 121-s guest measurement attributed approximately:

- `fingerprint-sensor.service`: **178.36 KiB/s, 20.64 write operations/s**;
- `fingerprint-evidence.service`: **65.52 KiB/s, 4.80 write operations/s**;
- `systemd-journald`: **77.14 KiB/s, 16.16 write operations/s** *across multiple services, not exclusively Fingerprint*.

These are **window-specific** observations, not lifetime averages or exact physical HDD seek attribution. Do not add them into a causal Fingerprint total without attribution.

Source inspection at the pinned merge:

1. `app/device_fingerprint_sensor/spool.py` / `SensorSpool`: bounded SQLite transport spool, `journal_mode=DELETE`, `synchronous=FULL`. `enqueue()` calls stale purge, capacity checks and `INSERT OR IGNORE` of an event batch. HTTP success triggers separate `acknowledge()` / durable `DELETE`, and stale or capacity eviction has its own DELETE transactions.
2. `app/device_fingerprint_sensor/runtime.py`: both raw capture and EVE loops call `spool.enqueue()` on individual received inputs; one input may yield several normalized events. Local health changes and periodic publication also enqueue messages. Producer delivery loop runs on a one-second cycle; reporting and health paths must remain truthful.
3. `app/device_fingerprint_sensor/producer.py`: delivers up to the configured `delivery_batch_size` (default 100) and ACKs only after HTTP 200. Retry/no-ACK is an at-least-once delivery safeguard.
4. `app/device_fingerprint_sensor/telemetry.py`: operational success/retry/statistics logging creates additional possible journald I/O.
5. `fingerprint-evidence.service` is a separate write contributor; its actual DB write/transaction path needs code-owner-specific inspection before any change.

The protected architecture is **not** the NI-01/NI-02B architecture. The first-wave NI write-I/O contract explicitly excludes Fingerprint spool mutation and requires separate ownership/admission.

## 2. Required bounded decisions (no open-ended delegation to Coder)

**FP-W2-01 — Spool ingress grouping:** Is it permitted to coalesce multiple successfully normalized events **before** `enqueue()` within a finite, documented cap (suggest testing 50/100/250 ms and max 32 events), without reordering source/health transitions, losing stop/retry events, changing event IDs, crossing security boundaries or exceeding spool transaction bounds? Specify exact flush behavior on shutdown, exceptions, source replacement, stalled traffic, capacity pressure, health transition, and process crash. No ACK before HTTP 200.

**FP-W2-02 — Avoiding no-op writes:** Is it permitted to bypass redundant stale purge and full-capacity/eviction DELETE attempts when an authoritative cached bound guarantees no eligible stale rows / no pressure? Cache invalidation, clock rollback, crash/restart, full-queue admission, and 24h stale-drop semantics must be precise. No unbounded cache, silent skip or retention extension.

**FP-W2-03 — ACK path:** Keep the existing ACK-after-HTTP-200 contract and idempotent replay. Decide whether ACK transactions can be grouped further without expanding unacknowledged backlog or allowing partial acknowledgements. Default recommendation: **leave existing batched ACK intact**, focus on ingress and unnecessary purge writes first.

**FP-W2-04 — Spool journal mode/durability:** Declare `synchronous=FULL` and `journal_mode=DELETE` unchanged in first implementation unless a separately justified, approved and tested conversion explicitly preserves restart, power-loss, bounded capacity and at-least-once delivery semantics. Do **not** quietly switch to WAL or NORMAL.

**FP-W2-05 — Fingerprint Evidence sink:** Independently identify exact DB-owned transactions/duplicate handling, then authorize or reject bounded bulk inserts / no-op suppression. Preserve immutable evidence, classification inputs, dedup, lineage, source-health semantics and per-site privacy controls. Do not change schema or replay policy without explicit decision.

**FP-W2-06 — Sensor telemetry:** Decide whether routine delivery-success and stats events may be replaced by bounded 60-second aggregates while transitions, faults, retry/permanent failures, overflow, and security events remain immediate, without leaking identifiers or sensitive payloads.

**FP-W2-07 — Configuration, rollout and failure:** Exact default-OFF flags, strict parser semantics, independent per-feature toggle, fail-closed behavior, rollback and no migration; flags must allow one-command staged activation with evidence from PRTG/host and no automatic source drop.

## 3. Frozen requirements

- Durable sensor queue, idempotent event identity, correct FIFO/endpoint behavior, bounded disk/memory use, 24h stale policy, crash/retry delivery without loss, no ACK before successful server response.
- Attribution provenance, Device Fingerprint classification, temporal authority, CAPPORT/Auth, guest access and visitor data privacy remain unchanged.
- No schema changes, destructive purge, journal-mode weakening, SSD migration, or modification of protected production until explicit Tech Lead/Owner approval.
- Coder owns **code implementation only**. TechLead23 independently reviews/runs test suites and prepares deployment. SysAdmin/PRTG own infrastructure measurement; no physical IOPS proof assigned to Coder.

## 4. Required Architect output

Return one **closed decision contract**: exact approved algorithms and caps, prioritization (F1/F2/F3), all fallback and crash invariants, new configuration keys/defaults, reversible rollout, forbidden mutations, compatibility with accepted Fingerprint architecture, and a concise code handoff to TechLead23. Identify any existing frozen-contract exception that needs Owner approval. TechLead23 will then issue the precise code-only TASK to Coder and personally verify results.

**NO CODE CHANGE AUTHORIZED BY THIS REQUEST.**
