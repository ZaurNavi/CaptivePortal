# NI-04 Background Materialized Service Intelligence

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

Current policy amendment (#321 V3B): intermediate NI01/NI02 event evidence and
NI04 Device recognized observations/rollups are eligible for at most 24 hours
from original source event/ingest time, with native bounded owner GC. No schema,
index or bootstrap migration is part of this amendment. Active continuity and
identity state remains protected. NI04 unacknowledged Visit delivery is exempt
from age GC and is pruned only by the existing verified durable Visit ACK;
Visit-owned results retain their own lifetime. A future one-time cutover needs
separate Owner GO and cannot promise to recover erased history by code rollback.
The historical implementation/migration statements below are not rewritten.

Authority: Architecture Contract v1 + v1.1 Addendum and Implementation TASK v1.
Production rollout, migration, mode changes, merge and deployment require separate Owner authorization.
Historical stage statement: NI-05 and NI-06 were HOLD at this implementation checkpoint; current disposition is NI-05 Production and NI-06 CANCELLED BY OWNER.

## Baseline and verification ownership

Implementation baseline: b1442efc434716d35e21b9e3124c3b9cd2222fbe.
Baseline tree: 1ea6a2d452a5c8147d2a9cdce6c5dcecd9900575.
Implementation uses a dedicated native Git worktree and feature branch.
No other worktree is modified.

G0 code inventory identifies these projection DB consumers:

- network-metadata-projection single writer: ProjectionRepository and CLI.
- CaptivePortal/Admin NI-02B read boundary: DeviceNetworkMetadataReadService.
- NI-03 Protocol Intelligence through that read boundary.
- NI-04 legacy V2 through DeviceNetworkMetadataRecognitionReadService.

All share app/network_metadata_projection/schema.py validation.
Every declared consumer must run an accepted bridge-compatible binary before extension installation.
Unknown external consumers require an operator inventory and HOLD before production migration.

Coder runs only targeted unit/integration tests, architectural acceptance cases,
directly affected regressions and scoped laboratory load checks.
Full Project/Central/entire-repository regression gates are performed by Tech Lead after handoff.
Their pending status does not block development or the targeted-test PR handoff.

## G1 compatibility bridge

The validator accepts exactly CORE_ONLY or CORE_PLUS_EXTENSION_V1.
Core table/index/trigger DDL, metadata and user_version=1 stay unchanged.
An unknown application object, changed Core object, incomplete extension or missing
extension metadata fails closed. Only SQLite-owned sqlite_% objects are excluded.

The bridge does not install an extension automatically.
If the complete extension is present, every newly committed eligible src/outbound/external
DNS/TLS/QUIC edge produces exactly one feed row in its existing writer transaction.
Authoritative Registry establishment updates the change index in that same transaction;
periodic revalidation and safe-reason-only changes allocate no sequence.
Existing Core monotonic identity behavior is preserved.

Extension maintenance is independent of NI-04 publication mode.
An installed extension must continue receiving feed/index upkeep while publication is off.
The existing b1442efc baseline is NOT a post-migration rollback target.
The G1 bridge commit is a proposed rollback floor until independently accepted by Tech Lead.
NI04_MAT_COMPAT_BASE_SHA must be recorded from that accepted commit before production migration.

Proposed compatibility bridge commit: 36e2b462a39533c32954215e40d9097167591237.
Its exact tree is 2541384db1c6a0c4a8b307c54fc1c966ed6c4152.
This source identity is a candidate for Tech Lead acceptance; it is not an authorization to deploy.

G1 Coder targeted verification: 329 PASS / 0 FAIL / 0 SKIP.
Command: python -m pytest -q -rs tests/network_metadata_projection
tests/network_protocol_intelligence tests/network_service_recognition/test_protected_readers.py.
Environment: native Ubuntu 22.04 Git worktree, qualified Python 3.10.12 Lab virtualenv.
Changed-Python compileall and git diff --check: PASS.
The 21 new bridge cases include atomic edge/feed/checkpoint crash behavior,
legacy read-consumer compatibility, unchanged Core DDL, closed object rejection,
off-mode upkeep, idempotency, retention cascade and old-baseline incompatibility.

## Release safety boundary

Before any production operation, an operator must record current source/DB identities,
obtain a verified recoverable backup/snapshot, and confirm no NI-04 backfill is running.
Roll out the accepted bridge with publication off and installer disabled.
Restart and verify projection readers first, then the bridge writer, against Core-only DB.
Only after every declared consumer reports the bridge identity may the Owner authorize
one-time extension installation by the locked NI-02B writer.

The operator must confirm TimeoutStartSec >=180s and adequate disk-I/O startup budget.
Restart NI-02B alone for installation; no worker, shadow comparison or backfill runs concurrently.
Complete schema validation, quick_check and resumed Core checkpoint progress are mandatory.
Only then may a separately authorized shadow-to-serve sequence begin.

After migration, rollback uses the accepted bridge or a later extension-aware release.
Never restore b1442efc code against the migrated DB, drop the extension, edit sqlite_schema
or sqlite_sequence, reset source checkpoints or purge evidence to satisfy an old validator.

# G2 disposition and production authority

The original four sequential load samples remain externally retained without
rewriting. Pair 1: p95 commit +3.7100%, throughput +2.2946%. Pair 2: p95 commit
+9.0447%, throughput -6.3078%. G2 correctness: 369 targeted tests passed.
G2 performance: **ACCEPTED BY OWNER EXCEPTION**, not a formal performance PASS.
The Owner explicitly accepted the reported 6.31% throughput loss against the
normal 5% limit and cancelled the proposed 12-run retest. No further G2 load runs
or hot-path optimization were performed under that superseded request.

All commits in this development lane are local review artifacts. They do not
authorize installation, migration, restarting services, shadow activation or serve.
The G1 bridge SHA is a proposed rollback floor until Tech Lead independently
accepts and records `NI04_MAT_COMPAT_BASE_SHA`; it is not an operational approval.
