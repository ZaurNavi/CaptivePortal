# Public Traffic Counter v1

Public Traffic Counter reads completed Wi-Fi sessions from the existing
Omada normalized JSONL journal and maintains per-SSID traffic totals in
a local SQLite database. It does not call Omada OpenAPI, Loki, Grafana
or Alloy.

Traffic is reported by Omada only after `omada.client_offline`, so active
sessions are intentionally absent from these totals. The result is an
informational public statistic, not billing data.

## Data flow

```text
Omada normalized JSONL
        |
        v
binary inode-aware reader
        |
        v
SQLite aggregation and deduplication
        |
        v
GET /api/public/portal-counter
        |
        v
existing portal statistics block
```

Only `omada.client_offline` records with a non-empty
`normalized_event_id` are written to `processed_events`. Valid records
have `counted=1`. Invalid target records and aggregate overflows have
`counted=0` and a stable `skip_reason`. Other event types only advance
the transactional byte offset and do not expand the database.

## Configuration

Use the values shown in `docs/public_traffic.env.example`:

```env
PUBLIC_TRAFFIC_COUNTER_ENABLED=true
PUBLIC_TRAFFIC_SSID=Zefer_Parki
PUBLIC_TRAFFIC_DB_PATH=/opt/CaptivePortal/data/public_traffic.sqlite3
PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS=10
PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS=60
```

The source log is always read from
`OMADA_WEBHOOK_NORMALIZED_LOG_FILE`. Calendar dates use
`PORTAL_COUNTER_TIMEZONE`, so portal opens and completed traffic cross
midnight together.

Invalid traffic configuration is fail-safe: the worker is not started,
the API returns `traffic.available=false`, and portal authorization
continues normally.

Changing `PUBLIC_TRAFFIC_SSID` selects another already aggregated SSID.
It does not migrate, delete, merge or rebuild stored data.

## Storage and atomicity

The independent database uses schema version 2 and the following tables:

- `traffic_daily`
- `processed_events`
- `reader_state`
- `counter_state`
- `counter_resets`

Every connection enables WAL, `synchronous=NORMAL`, and a 250 ms busy
timeout. A target event is handled in one `BEGIN IMMEDIATE`
transaction:

1. check `normalized_event_id`;
2. validate INT64 daily and total aggregates;
3. insert `processed_events`;
4. update `traffic_daily` when counted;
5. advance the source byte offset;
6. commit.

On failure, all of these operations roll back. Duplicate and rejected
events still advance their current source offset.

Traffic and session counters remain within
`0..9223372036854775807`. Overflow records are finalized with
`skip_reason=aggregate_overflow`; they are not retried after truncate
or reconciliation.

`traffic.updated_at` is the UTC commit time of the latest `counted=1`
event for the selected SSID. A zero-byte session updates it because the
completed-session count changes.

## Backfill, rotation and recovery

The worker is created by `create_app()` but started only by `run.py`.
`start()` returns immediately. `stop()` uses a stop event and a bounded
join. A thread-start failure marks traffic unavailable and does not
prevent Flask or authorization from starting.

On a new database the worker reads:

```text
.log.10 -> ... -> .log.1 -> .log
```

The database remains `traffic.available=false` until every available
complete line has been handled and
`initial_backfill_completed=1` is committed. An absent source and absent
rotations represent a valid empty history and become ready immediately.

Files are identified by `st_dev:st_ino`; offsets are byte offsets and
the input is opened in binary mode. `reader_state` also stores a SHA-256
content checkpoint covering the beginning of the file and the bytes
immediately before the saved offset. The checkpoint is validated before
the offset is reused. A mismatch means that the inode was reused or the
file was rewritten: a warning is emitted and reading restarts at byte
zero with `processed_events` providing deduplication.

A line without final `\n` waits for the next scan. Invalid UTF-8 and
invalid JSON advance the offset with a warning.

At every scan:

- a known inode resumes from its saved offset;
- a saved offset is applied only after its content checkpoint matches;
- a new inode starts at zero;
- retired files are processed before active;
- a same-inode truncate resets its offset to zero;
- `processed_events` prevents duplicate aggregation;
- a vanished non-retired inode emits one persistent warning;
- state for a vanished fully consumed retired inode is removed;
- a previously missing inode that reappears restarts at byte zero and
  relies on `processed_events` for deduplication.

Backfill start/completion and the first reconciliation of an existing
database are logged once per worker lifecycle. Normal ten-second
incremental scans do not create per-cycle info messages.

## Public API and frontend

The existing endpoint keeps its original fields and adds `traffic`:

```json
{
  "opened_today": 186,
  "opened_total": 18342,
  "day": "2026-07-29",
  "timezone": "Asia/Baku",
  "traffic": {
    "available": true,
    "ssid": "Zefer_Parki",
    "today_bytes": 3407872000,
    "today_display": "3.17 GB",
    "total_bytes": 460248236032,
    "total_display": "428.64 GB",
    "completed_sessions_today": 186,
    "completed_sessions_total": 18342,
    "updated_at": "2026-07-29T08:00:00.000Z"
  }
}
```

Before initial backfill, when disabled, or on a traffic database error:

```json
{
  "available": false,
  "ssid": "Zefer_Parki"
}
```

The endpoint remains HTTP 200 when the existing open counter succeeds.
The browser validates open counts and traffic independently. One
periodic request refreshes both sections. Traffic values use binary
units and `ROUND_HALF_UP`.

## Administrative reset

Reset one SSID:

```bash
python -m app.public_traffic.cli reset \
  --ssid "Zefer_Parki" \
  --yes
```

Reset all SSIDs:

```bash
python -m app.public_traffic.cli reset --all --yes
```

Reset is rejected until `initial_backfill_completed=1`. `--yes` is
mandatory. A reset deletes only aggregate rows and writes an audit row;
it preserves `processed_events`, `reader_state`, `counter_state`, and
the completed-backfill flag. Old source records therefore cannot
restore deleted totals.

The `--all` preview prints each SSID independently. It never combines
separate SSID totals into one INT64-limited value, so two individually
valid SSIDs cannot prevent a global reset.

## Deployment

Prepare persistent storage for the service account:

```bash
sudo install -d -o admin -g admin /opt/CaptivePortal/data
sudo install -d -o admin -g telemetry /opt/CaptivePortal/logs
```

The SQLite database and normalized logs are runtime data. Do not deploy
or delete them with Git updates.

## Verification

```bash
pytest -q
python -m compileall -q app
git diff --check
```
