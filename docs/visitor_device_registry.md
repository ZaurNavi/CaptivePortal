# Visitor Device Registry

Status: superseded as normative contract
Current contract: [modules/visitor-registry.md](modules/visitor-registry.md)
Historical implementation details below are retained for reference.

Visitor Device Registry is a fail-open, local persistence layer for
successful Authorized Client Snapshot events. It reads the existing
`visitor_snapshots.log` journal and its rotations; it never calls Omada
and never participates in the authorization decision.

The schema-v1 identity contract is:

```text
one canonical MAC address
-> one global technical device card
```

The stable `device_id` is UUIDv5 over the canonical MAC using namespace
`afca1c95-15b2-446d-b10d-ab47f0090b76`. Site, SSID, IP, hostname, and
Omada client ID do not affect identity.

## Configuration

The Registry remains disabled until a separate production activation is
approved:

```text
VISITOR_REGISTRY_ENABLED=false
VISITOR_REGISTRY_DB_PATH=/opt/CaptivePortal/data/visitor_registry.sqlite3
VISITOR_REGISTRY_SCAN_INTERVAL_SECONDS=5
VISITOR_REGISTRY_SHUTDOWN_TIMEOUT_SECONDS=10
VISITOR_REGISTRY_MAX_LINE_BYTES=4194304
```

The Registry reuses:

```text
VISITOR_SNAPSHOT_LOG_FILE
VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT
PORTAL_COUNTER_TIMEZONE
```

`VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT=0` is valid and makes the
Registry read only the active `visitor_snapshots.log`.

CaptivePortal does not automatically load `.env.example`; production
values still come from the environment of `captive-portal.service`.
Activation requires an explicit `VISITOR_REGISTRY_ENABLED=true` in the
service environment. Returning it to `false` is a fail-safe rollback;
rollback preserves the database, journal, and reader offsets.

Invalid enabled configuration makes only the Registry unavailable. It
does not stop CaptivePortal, alter AuthSession/AuthRun, or affect the
snapshot collector. An absent parent directory is created automatically
only under `/opt/CaptivePortal/data`, with POSIX mode `0750`. An external
absolute DB path is accepted only when its parent already exists, is a
directory, is writable by the service user, is not group-writable, has
no permissions for others on POSIX, and is not in a public web tree.
An existing DB target must be a regular file and must not be a symlink.
For a new DB, the resolved parent is validated before SQLite can create
the main, WAL, or SHM files.

The read-only CLI uses the same `lstat` target validation as runtime.
An absent ordinary DB path is reported as `database_absent` without
creating a file. A directory, FIFO, dangling symlink, or symlink to
another target is a runtime/configuration error with exit code `1`, not
an absent database.

The DB path is checked, including resolved symlinks and existing-file
identity, against the snapshot journal and rotations, portal counter
database, public traffic database, authorization telemetry, and raw and
normalized Omada webhook journals.

## Data and time semantics

Only `visitor.client_snapshot.captured` with `schema_version=1` creates
history. Failed and unknown events only advance the source offset.
Strict JSON rejects duplicate keys, non-object roots, `NaN`, and
infinities, including finite-syntax numeric overflow such as `1e400`.
Complete malformed, invalid-UTF-8, and oversized lines advance
atomically without creating a processed snapshot row.

All accepted timestamps are timezone-aware and stored as UTC with
millisecond precision. `first_seen_at` and `last_seen_at` mean the
earliest and latest successful portal authorization for which a captured
snapshot was stored. They are not physical Wi-Fi association or visit
times.

Current fields are selected by:

```text
authorized_at DESC, captured_at DESC, snapshot_id DESC
```

Current network values are copied exactly from that snapshot, including
`null`. Profile values (`last_known_*`) are the newest nonempty values by
the same ordering. Whitespace-only profile strings count as absent, but
the original string remains preserved in `client_json`.

Every complete line is applied through one `BEGIN IMMEDIATE`
transaction. A new stored snapshot, its processed marker, device
recomputation, snapshot count, reader offset/checkpoint, and
`last_snapshot_stored_at` commit together. Duplicate IDs with the same
canonical event hash are ignored. Reuse of an ID with different content
is a conflict and never overwrites history. A validated skipped event is
also final.

## Reader, rotation, and recovery

Files are discovered oldest to newest:

```text
visitor_snapshots.log.20
...
visitor_snapshots.log.1
visitor_snapshots.log
```

The reader opens each candidate in binary mode and then obtains
`st_dev:st_ino` with `fstat`. POSIX candidates are opened with
`O_NONBLOCK` and close-on-exec where supported; directories, FIFOs,
sockets, devices, and any other nonregular candidates are ignored.
Descriptors stay open while reading. One inode exposed under two names
is read once, with the active path taking name priority.

Offsets are protected by the exact
`visitor-registry-checkpoint-v1` SHA-256 checkpoint: a 2048-byte prefix,
a nonoverlapping tail of up to 2048 bytes, their encoded lengths, and
the offset. Truncate/regrow, rewrite, and reused-inode cases restart that
source at zero; `processed_snapshot_events` provides idempotency.
Incomplete lines remain pending at their starting offset and do not
degrade the Registry.

Initial backfill is complete only after a full successful scan. If no
journal and no prior reader state exist, this is a valid empty backfill.
Loss of an unfinished retired inode produces one persistent warning and
keeps the scan incomplete. Loss of a fully read retired inode is normal
cleanup.

SQLite schema version is stored in `PRAGMA user_version`. Initial schema
creation, the `registry_state` singleton, and `user_version=1` commit in
one transaction; a failure at any migration checkpoint rolls all of them
back. The synchronous startup path performs only the bounded checks
needed to open the DB:
`user_version`, required schema metadata and singleton, constraints, and
`PRAGMA quick_check`. The worker then runs the full
`PRAGMA integrity_check`, `PRAGMA foreign_key_check`, and the global
`snapshot_count` audit before it applies any journal line. This full
audit runs in the background and therefore cannot delay HTTP startup. A
future, partial, corrupt,
read-only, or unopenable database is preserved and the Registry becomes
unavailable. Temporary lock/full/write failures keep the offset unchanged
and move it to degraded for retry.

Before starting that audit, the worker persists:

```text
state=initializing
state_reason=full_audit_pending
```

Therefore an old `ready` or `stopping` state is never presented as the
current lifecycle during startup validation.

The supported runtime model is one CaptivePortal process, one Registry
worker, and one logical SQLite writer. Multiple active WSGI processes
require a future leader-election or inter-process locking design.

## Read-only CLI

The CLI does not create or migrate a database and never prints
`raw_controller_snapshot_json`, `client_json`, or `auth_context_json`.

```bash
python -m app.visitor_registry.cli status
python -m app.visitor_registry.cli stats --date 2026-07-30
python -m app.visitor_registry.cli list --limit 20
python -m app.visitor_registry.cli show --mac 1C:13:86:02:2C:29
python -m app.visitor_registry.cli snapshots \
  --device-id 00000000-0000-0000-0000-000000000000
```

All commands support `--json`. Exit codes are `0` for success, `1` for a
runtime/storage error, and `2` for invalid arguments or a missing
object. When initial backfill is incomplete, query output has
`partial=true`; text mode also prints a warning.

`stats` interprets its date in `PORTAL_COUNTER_TIMEZONE`. It counts new
devices by `first_seen_at`, distinct authorized devices by snapshot
`authorized_at`, and snapshots by `authorized_at` in the half-open UTC
interval corresponding to that local day.

The CLI keeps this timezone semantics even when
`VISITOR_REGISTRY_ENABLED=false`, so a preserved database can be queried
after rollback without silently switching daily boundaries to UTC.
`status` reports the DB and journal paths, availability, database
readiness, state, backfill progress, reader states, and the number of
persisted missing-inode warnings.

`configured_enabled` in CLI status reflects only the CLI process
environment. Confirm the service setting through the environment of its
PID and confirm the active worker through operational telemetry.

## Backup and restore

The live WAL database can comprise:

```text
visitor_registry.sqlite3
visitor_registry.sqlite3-wal
visitor_registry.sqlite3-shm
```

Do not copy only the main `.sqlite3` file while the worker is running.
Use the SQLite backup API, for example:

```bash
sqlite3 /opt/CaptivePortal/data/visitor_registry.sqlite3 \
  ".backup '/secure/path/visitor-registry-backup.sqlite3'"
```

Alternatively, stop the service and copy the database after all
connections have closed.

For recovery:

1. Stop `captive-portal.service`.
2. Preserve the damaged database as diagnostic evidence.
3. Restore a verified backup without automatically deleting or
   recreating the damaged database.
4. Run `PRAGMA integrity_check` and verify `user_version=1`.
5. Start the service and allow reconciliation to read remaining journal
   events.

Once journal rotations expire, a complete rebuild is not guaranteed
without a database backup. Schema v1 has no automatic retention, reset,
or rebuild command.

## Lifecycle and production verification

Shutdown preserves the existing Public Traffic ordering, drains the
authorization executor, drains the snapshot collector, then performs
one bounded final Registry scan under the same scan lock before stopping
the Registry. If the Registry thread outlives the first timeout, stop
remains requested but not completed; a later `stop()` can join it and
finish the lifecycle. Once the background thread has stopped, a final
scan that reaches its deadline counts as attempted: the timeout event is
emitted, the incomplete line offset remains unchanged for startup
reconciliation, and lifecycle stop completes without waiting
indefinitely. Planned shutdown and reader `reason=shutdown` do not move
the Registry to degraded, and the worker cannot overwrite the persisted
`stopping` state after a delayed audit or scan returns.

Operational events use
`AuthorizationTelemetry.safe_emit_system(component="visitor_registry")`.
Raw snapshots are never included. Repeated operational failures are
rate-limited or emitted only on state changes, and recovery from
degraded emits `visitor_registry_recovered`.

Regression fixtures include production-oriented shapes for both
`AUTHORIZED_AFTER_ATTEMPT` with null portal network fields and
`ALREADY_AUTHORIZED` with `authorization_attempt=0`. They remain unit
fixtures, not proof of the production live-gate. Before activation,
mechanically anonymize one current real
`visitor.client_snapshot.captured` line without changing its structure,
keys, JSON types, nullability, nesting, or unknown fields. A recursive,
case-insensitive test rejects known credential-bearing key names. Also
confirm the sanitized raw controller object contains no secrets. Then
verify:

```bash
python -m app.visitor_registry.cli status --json
python -m app.visitor_registry.cli stats --json
```

Authorization, CAPPORT, frontend behavior, public APIs, Snapshot
Collector schema v1, Public Traffic Counter, Alloy, Loki, Grafana, and
production systemd files are not changed by this module.
