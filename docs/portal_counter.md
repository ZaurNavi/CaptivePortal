# Public Portal Open Counter v1.0

The module counts newly created server-side `AuthSession` objects. A valid
`GET /` records one event only when `AuthSessionManager.create_or_get()`
returns `created=True`. Authorization outcomes, Omada state, polling and API
reads do not affect the count.

## Configuration

The existing `app/config.py` configuration contains:

```python
PORTAL_COUNTER_ENABLED = True
PORTAL_COUNTER_DB_PATH = "/opt/CaptivePortal/data/portal_counter.db"
PORTAL_COUNTER_TIMEZONE = "Asia/Baku"
PORTAL_COUNTER_API_ENABLED = True
```

Before deployment, prepare the persistent directory for the systemd service:

```text
sudo install -d -o admin -g admin /opt/CaptivePortal/data
```

The database must not be deployed from Git or removed during application
updates.

## Public API

`GET /api/public/portal-counter` returns:

```json
{
  "opened_today": 15,
  "opened_total": 824,
  "day": "2026-07-26",
  "timezone": "Asia/Baku"
}
```

If storage is unavailable, the API returns HTTP 503 with
`{"error":"counter_unavailable"}`. Counter failures are fail-open: the portal
page, authentication worker and existing authorization flow continue normally.

## Storage

SQLite schema version 1 is managed through `PRAGMA user_version`. Events store
only `session_id`, UTC `opened_at`, and the calendar `opened_day` in
`Asia/Baku`. `session_id` is unique, and inserts use
`ON CONFLICT(session_id) DO NOTHING`.

Run the tests from the repository root:

```text
python -m unittest discover -s tests -v
```
