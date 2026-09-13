# Visitor Device Registry

Status: current implementation; repository default disabled
Updated: 2026-09-13
Baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`

## Purpose

Build durable visitor device identity/history from the Authorized Snapshot data journal.

## Critical boundary

Visitor Registry **does not call Omada** and does not read Auth process memory.

Source:
`visitor_snapshots.log`.

Flow:
`snapshot journal → reader/checkpoint → VisitorRegistryService → visitor_registry.sqlite3 → VisitorRegistryReadService`.

## Current responsibilities

- initial backfill;
- active/rotated journal reading;
- durable reader checkpoint/state;
- duplicate/event identity handling;
- persistent device identity and history;
- integrity audit;
- ready/degraded/unavailable state;
- bounded fixed-delay worker;
- final shutdown scan.

Historical device/snapshot counts are acceptance evidence only and must not be used as current counters.

## Device Type read enrichment

Visitor Registry persistence remains raw/source-oriented.

Read boundaries now add:

```text
snapshot.device_type_key
device summary.last_known_device_type_key
```

These values are derived from the corresponding raw `device_type` /
`last_known_device_type` through the central lexical normalizer.

No migration/backfill changes the stored source value.

## Relationship to Visit Lifecycle

Visit Lifecycle is now a separate **current** subsystem at this baseline.

Registry supplies a read boundary used by Visit reconciliation and Analytics/Admin. Registry does not own physical Visit start/close semantics.

## Fail-open

Invalid journal lines, rotation issues or SQLite/worker failure must not break guest authorization. Consumers see explicit unavailable/degraded state.

## Persistence

Default DB:
`/opt/CaptivePortal/data/visitor_registry.sqlite3`.

The snapshot journal remains the recoverable source for backfill/checkpoint processing.

Writer owns Registry schema. Analytics/Admin are read consumers.

## Configuration

Prefix: `VISITOR_REGISTRY_*`; repository feature default is disabled.

Production enabled-state and live health must be verified on the target host and are not inferred from Git.
