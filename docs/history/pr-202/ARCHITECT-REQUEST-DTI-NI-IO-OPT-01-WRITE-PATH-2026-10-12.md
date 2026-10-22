# ARCHITECT REQUEST — CAPTIVPORTAL
# TASK-DTI-NI-IO-OPT-01 — Safe Write-I/O Reduction Architecture Contract

**От:** TechLead23  
**Кому:** CaptivPortal Architect (и отдельному владельцу Fingerprint архитектуры)  
**Дата:** 2026-10-12  
**Статус:** REQUEST FOR ARCHITECTURE DECISION / NOT IMPLEMENTATION TASK  
**Production:** `main@88541da8d6952cb91fc945b7f77efcf7e5c46420`; **NO MUTATIONS**.  
**Evidence:** SysAdmin `TASK-INFRA-IO-01-FINAL-ROOT-CAUSE-REPORT-2026-10-12.md`, TechLead `TASK-DTI-NI-IO-OPT-01-APPLICATION-IO-ANALYSIS-2026-10-12.md`.

## Проблема

Host HDD `/dev/sda` при 143.98 write IOPS и всего 1835 KiB/s показывает 120.52 ms write await / 92.4% util. Ubuntu CaptivPortal VM — ~83.08% physical write bytes и ~85.11% write IOPS в host-cgroup sampling. Guest top writers: NI-01 428.34 KiB/s / 28.38 IOPS; Fingerprint Sensor 178.36 / 20.64; NI-02B 140.15 / 15.15; journald 77.14 / 16.16.

### Подтверждённые write-path mechanics

- **NI-01**: SQLite WAL + `synchronous=FULL`; one atomic ingest transaction per batch (max 256 records/1 MiB), 1-second idle poll, multiple rows/indices per observation, durable checkpoint and source lineage. Journal sample: 83 completed batches, 4053 records / 5 min, mean 48.83, max 256.
- **NI-02B**: SQLite WAL + `synchronous=FULL`; on empty 1-second poll does transaction + durable `UPDATE projection_runtime_state`; `maintain_capacity()` invokes PASSIVE checkpoint after *every* committed transaction, including empty-poll runtime update; TRUNCATE under capacity pressure.
- **Fingerprint Sensor**: SQLite DELETE journal + `synchronous=FULL` transport spool, enqueue → deliver/ack/delete, additional bounded stale-purge/capacity logic. Changes are fingerprint-architecture owned.
- **journald**: measured separate guest cgroup contributor, per-service attribution still needed.

**Not proven yet:** exact fsync count per process, WAL checkpoint-caused spikes, percentage of HDD congestion removed by any single change, one-to-one causality to NI01 31m lag or NI04 5s deadline. Do not invent a speedup percentage or claim `FULL` is a bug.

## Decisions requested from Architect (answer each; no Coder assumptions)

1. **Durability and source checkpoints.** What is the permitted crash-loss/replay envelope for NI-01 batches? Must observation rows/source record identity/offset/generation health commit strictly together? Are any steps allowed to move to a separate weaker-durability store?
2. **NI-01 batch pacing.** Can the writer *coalesce* up to its existing caps (`256`, `1 MiB`) before COMMIT? Define **max event-ingest delay / source backlog high-water / CPU/I/O budget / interruption behavior**. Is adaptive batching permissible, and under what deterministic rules?
3. **NI-02B empty-poll persistence.** Is `last_source_poll_at` required durable every 1s? Can unchanged `usable`/`pending_count=0` avoid SQLite UPDATE, with an explicitly bounded heartbeat interval or in-memory freshness? Define restart/crash/recovery semantics so UI never lies about source health.
4. **NI-02B checkpoint policy.** Should PASSIVE checkpoint be attempted after every commit? If changed, state exact WAL pressure/reader pin/headroom thresholds, fail-closed transitions, retention, capacity and restart behavior. Never change PRAGMA in production to experiment.
5. **Fingerprint spool.** Can enqueue/ack/deletion be batched or transport journal changed? This is a **separate owner-approved Fingerprint architecture contract**, with non-loss, ordering, retry, rejection, replay, crash atomicity, retained/expired evidence and CAPPORT isolation mandatory.
6. **Logging/telemetry.** Which `batch_committed`/delivery events are audit obligations, and which may be aggregated into closed counters/periodic summaries without losing actionable health? Define rate ceilings, cardinality, privacy, freshness, reproduction.
7. **Retention/schema.** Are periodic delete batch sizes, schemas, indices and WAL growth admissible for change? Define migration plan / no-downtime compatibility / exact rollback / bounded DB footprint. No thinning of `NetworkMetadataEnvelopeV1` provenance or `DeviceNetworkMetadataEdgeV1` without explicit supersession.
8. **Separation versus tuning.** Decide whether optimization must be preceded by dedicated SSD/vDisk placement; code optimization and moving storage are independent. No claim that either alone will fix NI-04 deadlines without contemporaneous evidence.
9. **Metrics and acceptance.** Freeze reproducible lab samples, baseline, observation window, p50/p95/p99 guest I/O latency, write IOPS and KiB/s per subsystem, fsync rate, ni01 event→ingested lag, ni02b source→projection lag, NI03/NI04 read success/deadline and no source/attribution/capture regressions. Define acceptable degradation envelopes.
10. **Versioning & reversibility.** Explicitly identify allowed changes vs immutable existing contracts; decide new config knobs/default-off, rollback compatibility, controlled activation, Owner gates, and which implementation TASK(s) should be split between NI and Fingerprint.

## Non-negotiable invariants

- CAPPORT/Auth, Portal Core and Fingerprint classification are protected: optional NI cannot block login, authorization or network access.
- Deterministic Site/capture-scope, temporal IPv4 authority, existing device_id only, no permanent IP-based device identification, no cross-MAC mixing.
- No raw payload / PCAP / unbounded identifiers or host histories added.
- Replay identity, source checkpoint, generation transitions, immutable/provenance records, idempotence, latency/freshness semantics, bounded storage/backpressure maintained.
- No shortening of crash-safe evidence or log retention without governance; false `usable` state prohibited.
- Do not solve an IOPS problem by dropping events or falsely asserting traffic=0/unknown→absent.
- No autonomous production PRAGMA changes, service restart, VACUUM/REINDEX, WAL checkpoint, SSD migration, code change or feature toggle.
- NI-05 and NI-06 **HOLD** pending Owner choice; separate Architect response does not authorize Coder.

## Requested deliverable

`ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1` with `APPROVED / REJECTED / HOLD` per candidate, exact bounded contracts, risks, migration/backward compatibility, crash/replay tests, performance acceptance gates, and proposed phased implementation task breakdown.

**TechLead gate:** After architecture, issue *profiling-only* Coder TASK/lab plan first; review measured benefits before any production optimization. SysAdmin separately owns physical storage/vDisk plan and comparative benchmarking.

```text
OWNER_APPROVAL_FOR_INVESTIGATION = YES
ARCHITECT_DECISION_REQUEST = OPEN
CODER_PRODUCTION_IMPLEMENTATION = HOLD
NO_PRODUCTION_RUNTIME_OR_CONFIG_MUTATION = TRUE
READ_ONLY_DIAGNOSTIC_HELPER_FILES = /home/admin/techlead23-ni-io-journal-{audit,five}.py
```
