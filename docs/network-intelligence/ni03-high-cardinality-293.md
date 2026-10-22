# NI03 high-cardinality reads — NI03_TOP1_INDEX_V1

Task/architecture: [Issue #293](https://github.com/ZaurNavi/CaptivePortal/issues/293).
Source-review publication is explicitly allowed by the
[performance gate decision](https://github.com/ZaurNavi/CaptivePortal/issues/293#issuecomment-6314418738).
**PERFORMANCE HOLD — NOT MERGE READY.** Correctness and performance acceptance
are separate. Architect must dispose of the measured write/retention overhead.
Source baseline: `6abbfe6b4546d7931696061f8703a7b413303a29`.
Deployment, production access, service restarts and merge require separate Owner
authorization. This document is a **procedure**, not evidence of deployment.

## Exact read contract

NI03 V1 publishes presence and latest observation, not event counts. The new
`read_protocol_latest_snapshot` reads at most one fact for each of `dns`, `tls`,
`quic`, using `idx_projection_mac_family_event_latest`:

```sql
SELECT edge_id,event_at,source_event_family
FROM device_network_metadata_edges INDEXED BY idx_projection_mac_family_event_latest
WHERE site_id=? AND client_mac=? AND source_event_family=?
  AND event_at>=? AND event_at<?
ORDER BY event_at DESC,edge_id ASC LIMIT 1;
```

All three seeks, runtime and authoritative binding reads, and the existing
Site+MAC future-event guard share the existing read-only `BEGIN` snapshot.
`mode=ro`, `query_only`, the five-second local deadline and two shared NI03 slots
remain unchanged. Pending identity never queries edges. Exactly 24 hours are
considered, with an inclusive start/exclusive end. Recent means the latest fact
is at or after the one-hour boundary. Timestamp ties retain DNS/TLS/QUIC priority,
then the smallest edge ID. No cross-Site fallback, raw DTO fields or history
completeness claim is added.

Four additional **existence-only indexed gap seeks** reject corrupt family
values outside the CHECK-constrained vocabulary (below DNS, DNS–QUIC, QUIC–TLS,
above TLS), without enumerating valid families. They return no edge facts. This
retains the existing fail-closed unknown-family canary even if a foreign writer
has bypassed CHECK constraints. They conservatively reject such corrupt facts
in this exact identity scope regardless of age. Selected fact shapes/canonical
timestamps are validated; this is not a new full-database integrity scan on a
request. Schema and maintenance integrity validation remain separate.

The legacy `read_protocol_evidence_snapshot(max_rows=20000)` and all other NI02
and NI04 read methods are unchanged. NI02 retention remains 14/30/90 days for
the existing independent classes. NI04 matcher, storage and public NI03 DTO V1
are unchanged. A genuine unavailable source, corruption, identity mismatch or
deadline remains a failure/degradation, never a fabricated empty success.

## Schema compatibility matrix

The logical Core contract, algorithm and `PRAGMA user_version=2` stay unchanged.
The versioned operation is `NI03_TOP1_INDEX_V1`, evidenced by the exact index
signature, not by a new table or automatic startup migration.

| Code | Store without the index | Store with the exact index |
| --- | --- | --- |
| Baseline code | accepted | rejected (unknown object) |
| New code | rejected (required object missing) | accepted |

Both exact `CORE_ONLY` and `CORE_PLUS_EXTENSION_V1` variants are supported.
Partial extensions, extra objects, wrong indexes/triggers, invalid metadata,
non-WAL stores, wrong user_version and FK/integrity errors are rejected. The
maintenance module alone knows the old signature; normal readers/writers do not
silently accept both. Fresh stores include the new index from creation.

## Maintenance upgrade — SysAdmin only after independent QA and GO_DEPLOY

1. Record accepted code SHA/tree and verify deployment/environment/config source.
   Inventory the actual NI02 writer, NI03 readers and NI04 readers/workers sharing
   this store, their process identities, source path, lock path and schema variant.
2. Plan a maintenance window. Preserve an approved consistent backup and recovery
   evidence using the existing operational procedure. Do not copy a live main
   database without its committed WAL state. Do not delete/rename live sidecars.
3. Budget disk/RAM/time for the one-off B-tree build, WAL and SQLite temporary
   sort space. Use fixture measurements as context, not a production bound. Stop
   if available headroom or maintenance duration is insufficient. Do not weaken
   durability or shorten retention to fit the build.
4. Stop **all** inventoried NI02/NI03/NI04 consumers using their approved service
   procedures. The CLI confirmation is an operator attestation, not an automatic
   service-discovery/stop mechanism. The writer lock excludes another cooperative
   writer, but cannot establish that arbitrary readers have been stopped.
5. With the new accepted code staged and the established NI02 service account and
   protected environment loaded (do not paste credentials into command arguments):

   ```text
   python -m app.network_metadata_projection.ni03_top1_migration up --maintenance-confirmed
   ```

   The command requires an existing enabled configured store, acquires the SAME
   `.writer.lock` as `ProjectionRepository`, opens with `mode=rw` (never creates a
   database), keeps WAL, uses connection-local FK=ON / synchronous=FULL and one
   `BEGIN IMMEDIATE`. It validates the exact old/new schema, metadata, quick_check
   and foreign_key_check. Only `CREATE INDEX` is performed. Before/after streaming
   table digests include core, checkpoints, bindings, extension and sqlite_sequence;
   they must match. Strict postflight and record comparison precede COMMIT. The
   migration does not call retention, manual checkpoint, VACUUM or repository
   initialization/capacity upkeep. SQLite's ordinary close/recovery behavior is
   not disabled or misrepresented as zero I/O.
6. `NI03_TOP1_INDEX_V1:changed` means one transition committed; `:unchanged` means
   the exact target already validated. `:unavailable`/nonzero is HOLD, not permission
   to repair schema by hand. Capture exit status and protected logs without raw
   records/paths in public reports. A pre-commit failure/crash rolls back DDL; if
   the acknowledgement was lost, inspect/reinvoke the same operation: an exactly
   committed target is an idempotent no-op, unknown drift is never repaired.
7. Enable the matching new code only after postflight. Start inventoried consumers
   in their approved order. Verify runtime/binding/source health, real authorized
   high-volume Device NI03 HTTP 200, exact expected fields/coverage, NI04 and other
   consumers. Do not inject synthetic traffic into production. Monitor latency,
   writer backlog, DB/WAL/disk growth and I/O against approved acceptance budgets.

## Coordinated rollback

Stop all consumers again. While the new maintenance code and writer ownership
are still available, run:

```text
python -m app.network_metadata_projection.ni03_top1_migration down --maintenance-confirmed
```

This validates the exact new schema, executes only `DROP INDEX` inside the same
atomic strict preflight/postflight/record-preservation transaction and verifies
the exact old schema. A repeated exact downgrade is a no-op. Then restore the
matching old application code and restart via the approved operational procedure.
**Git checkout alone is not rollback.** Do not run old code against the new index
or new code against an old store. Unknown drift, uncertain transaction outcome,
FK/integrity errors or inability to hold the writer lock require HOLD and review.

## Focused QA and reproducible LAB measurements

New deterministic tests cover 0/1/20000/20001/28976/30000/100001 synthetic facts,
HTTP 200 with no history-completeness claim, at most three returned facts, skewed
family mixes, half-open/microsecond boundaries, future corruption, identity
isolation/rebinding, same-snapshot concurrent ingest/retention and read-only access.
Migration tests cover both extension variants, old validator compatibility,
upgrade/no-op/restart/downgrade, drift/FK rejection, failed build, abrupt process
death before COMMIT and lock recovery. NI03 seam tests still exercise two slots,
local deadline, coverage and safe failure semantics.

Run only the task-scoped suites identified in the handoff. Full repository,
official platform gates and independent RQA remain Tech Lead responsibilities.

For a **new external disposable LAB directory**:

```text
python -m tests.network_metadata_projection.ni03_top1_benchmark --root <new-lab-directory> --rows 100001 --batches 20
```

This compares identical synthetic distributions without/with the index, with the
NI04 extension, normal unchanged NI02 writer/retention and a second bounded NI04
Device read. It records query plans, returned-fact count, latency, throughput,
DB/WAL footprint, full-size maintenance build, process I/O and environment. The
reference-only old-schema validator seam is local to this benchmark and is never
installed in runtime. Optional `strace -ttt -e pwrite64,fdatasync,fsync` can be paired
with the recorded epoch intervals to exclude fixture setup from per-phase counts.

The gate decision requires at least three independent pairs. Use three fresh
external directories and alternate `--order baseline-first`, `--order index-first`,
`--order baseline-first`. Keep every raw result. Each case has a fresh DB and 20
consecutive reads; the OS cache is not flushed, so this is not a cold-disk proof.
Twenty measured 128-edge writer commits follow prepared input; existing retention
then runs normally, including NI04 feed cascades. Distinguish traced syscall probes
from untraced latency/throughput runs. Never average away adverse individual pairs.

WSL process `write_bytes`, syscalls and WAL bytes are **not physical host HDD IOPS**.
One paired synthetic run is not an independent production performance gate.
Report unavailable host/QEMU/HDD metrics explicitly; never infer production
savings. Unacceptable cost or insufficient resource headroom is Architect HOLD,
not permission for another index, cache, materialized service or durability change.
