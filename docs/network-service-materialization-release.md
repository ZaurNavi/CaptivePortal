# NI-04 materialization: release and rollback plan

<!-- NI-V1-CURRENT-DISPOSITION:BEGIN -->
## Current disposition

**Historical / superseded as a current-state authority.**

This document is retained for implementation, migration, rollback, backfill and
decision provenance. Network Intelligence V1 is now **FUNCTIONALLY COMPLETE /
PRODUCTION DEPLOYED / CLOSED** through NI-05. NI-06 Transport Health was
**CANCELLED BY OWNER**.

Current production contract:
[Network Intelligence V1](modules/network-intelligence.md)

Current visual architecture:
[Network Intelligence Visual Architecture Atlas](network-intelligence/architecture-atlas.md)

Statements below that describe publication as pending, NI-05/NI-06 as HOLD, or
the implementation as not yet production are historical stage facts and are not
the current project status.
<!-- NI-V1-CURRENT-DISPOSITION:END -->

This is an operator plan, **not** authorization to execute it. Coder has performed
only isolated Lab development and targeted tests. Full Project/Central gates,
independent QA, production-class capacity, browser acceptance and production
preflight belong to Tech Lead/Owner. No unconditional FULL PASS is claimed.

## Ownership and defaults

`NETWORK_SERVICE_MATERIALIZATION_MODE=off|shadow|serve` is the single closed
deployment mode, default `off`. The existing
`WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED` still gates the product section.
There is no new Admin-writable setting, secret, restart authority or feature flag.

Portal/Admin reads its immutable startup settings. The separate NI-04 worker
uses its own approved environment file. Ensure the operator-selected mode agrees
across both processes; Admin must not reread the environment on requests.

The NI-04 store is `/opt/CaptivePortal/data/network_service_intelligence.sqlite3`.
The worker alone writes it, under its exclusive writer lock. Admin opens it
query-only. Default total file cap is 512 MiB, allowed range 128 MiB..2 GiB.
SQLite is WAL/FULL/FK, busy timeout 500ms, autocheckpoint 1000. No VACUUM, raw
SNI/DNS/IP/ports or packet payload is retained. Protected identity/provenance
fields exist only in the NI-04 store, not telemetry or public DTOs.

## Required deployment order — Owner-authorized only

1. Record exact current HEAD/tree, each relevant process's code identity, projection
   DB footprint/user_version/integrity, source checkpoint and a verified recoverable
   backup/snapshot. Confirm no concurrent NI-04 worker/backfill.
2. Tech Lead accepts the exact compatibility bridge and records
   `NI04_MAT_COMPAT_BASE_SHA`. The local G1 proposed bridge is
   `36e2b462a39533c32954215e40d9097167591237`, not yet an operational approval.
3. Deploy that bridge with mode `off` and extension installer disabled. Restart
   projection consumers/readers including CaptivePortal/Admin **first**, then the
   NI-02B writer. Verify Core-only reads/writes and normal checkpoint progress.
4. Declare every long-lived projection DB consumer. The immutable preflight input
   manifest must bind each to the accepted bridge identity, confirm backup and no
   backfill, and assert supervisor startup timeout >=180s. The supplied preflight
   validates these declared inputs only; it does not inspect or authorize production.
5. Under separate Owner migration authorization, enable the one-time NI-02B
   `--install-service-recognition-extension` path and restart **NI-02B alone**.
   Do not run NI-04/shadow/backfill concurrently. Partial extension is an integrity
   incident: HOLD, no heuristic drop/recreate/repair. Require exact Core+Extension
   validation, quick_check, FK integrity, runtime health and resumed checkpoint.
6. Remove the one-time installer option after successful installation. Extension
   upkeep remains mandatory whenever installed, regardless of publication mode.
7. Owner may authorize `shadow`. Start the independent NI-04 service only after
   extension admission. Live feed has priority; seed exact Registry replay jobs,
   reconcile coverage, backfill the captured 24h in pages <=128 and <=1 page/s.
8. Require current active admitted generation, completed backfill, caught-up feed,
   no unclosed gap, current coverage, store quick_check and unchanged upstream
   source rows. Compare legacy/materialized positive sets at the same supplied
   evaluation time using `compare_shadow`. Missing/extra/cross-device/provenance
   mismatch is FAIL. `LEGACY_DEADLINE_RECORDED` is not comparison PASS.
9. Only after independent Tech Lead admission and separate Owner cutover authority
   may Admin switch to `serve`. In serve, it reads only NI-04, never silently falls
   back to request-time recognition. Missing/corrupt store is unavailable/503.

## Protected control recipe

Owner/Tech Lead may check the accepted YouTube control Site/MAC/Device supplied in
the architecture inside their protected authorized environment. Do not put those
real identifiers or raw hostnames in shell output, logs, screenshots, telemetry or
public test artifacts. Public Coder tests use disposable synthetic identities.

## Rollback and stop conditions

After migration the old `b1442efc434716d35e21b9e3124c3b9cd2222fbe` binary is **not** a
rollback target. The floor is the independently accepted bridge SHA or a later
extension-aware release. Owner may explicitly stop publication/worker or switch
serve to shadow/off. Leave extension feed/change-index upkeep running in NI-02B.
Never DROP extension objects, edit sqlite_schema/sqlite_sequence, reset source
checkpoints, restore an old validator against the migrated DB or purge evidence.

Worker outage/lag never deletes confirmed positives. Unavailable inputs, deadline,
capacity or lineage conflict never advance an unsafe checkpoint. Feed gap recovery
retains the original cursor until the frozen recovery scan finishes; negative
coverage stays blocked for the affected 24h window. Empty/unmaterialized means
unknown, not no activity. Displayed source/attribution states remain the last
durably verified upstream states; materializer lag is its own V3 dimension.

SQL busy/deadline checks are bounded; kernel-level storage stalls remain an
operational admission concern. Coder's disposable reader/API/live latency samples
are not production-class capacity or disk-pressure certification.

## G2 exception and outstanding release gates

G2 correctness: 369 PASS. G2 performance: **ACCEPTED BY OWNER EXCEPTION**, not a
formal PASS. Original pair-2 throughput loss was 6.3078% (reported 6.31%) against
the normal 5% budget. Owner cancelled the proposed twelve-run retest; all original
four samples remain unchanged. This exception does not claim production efficiency.

Full Project/Central gates, production-class load/coexistence/Portal differential
latency, browser/accessibility checks, exact bridge operational admission and all
production migration/activation decisions remain with Tech Lead/Owner. Absence of
Coder full gates is intentional test ownership, not a hidden PASS or a Coder blocker.
