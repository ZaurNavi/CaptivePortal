# NI-04 Background Materialized Service Intelligence

Authority: Architecture Contract v1 + v1.1 Addendum and Implementation TASK v1.
Production rollout, migration, mode changes, merge and deployment require separate Owner authorization.
NI-05 and NI-06 remain HOLD.

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
