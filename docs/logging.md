# Logging, telemetry and data journals

Status: current
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

## Separation

Operational telemetry answers: component state/failure/quality.

Data journals store durable structured facts consumed later.

SQLite databases are persistence, not logs.

## Durable journals

| Path/default | Writer | Role |
|---|---|---|
| `auth_telemetry.log` | Auth telemetry | operational auth events |
| `visitor_snapshots.log` | Snapshot Collector | authorized snapshot data journal |
| `omada_webhook.log` | Webhook Receiver | redacted raw webhook journal |
| `omada_webhook_normalized.log` | Webhook Processor | canonical normalized events |
| `pending_session_cleaner.log` | Cleaner | scan/action audit |

The normalized webhook journal is consumed by Visit Lifecycle and Public Traffic. Visit must not reinterpret raw webhook payload independently.

## Component telemetry

Current operational events also exist for:
- Visit Lifecycle;
- Observation;
- Current State;
- Analytics/API;
- Admin Web;
- Public Traffic.

Their telemetry does not replace their persisted source data.

## Safety

Never log:
Access Token, Client Secret, Authorization header, Admin password/password hash, session cookie/token, CSRF token, Wi-Fi password or raw sensitive Omada override payload.

MAC is a technical identifier and is not masked by the current logging contract.

`SecretSafeRequestHandler` removes query strings from request-line logs for:
- `/admin` and all `/admin/...`;
- `/api/internal/analytics/v1` and descendants.

## Pending Cleaner

Audit-before-action is a safety invariant: `action.planned` must be durably written before reconnect POST. Operational telemetry is separate from the audit journal.

## Agent log handoff

Send only bounded relevant time windows/events/correlation identifiers. Do not dump multi-day logs, rotated journals or secrets into TASK/PR/handoff.
