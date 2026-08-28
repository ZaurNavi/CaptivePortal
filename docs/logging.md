# Logging, telemetry and data journals

Status: current
Updated: 2026-08-28
Baseline: `main@d41888ade1814a2c0e965ff0cd51212e7dc4bd5f`

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

Home AP-24H may publish bounded `home_ap_24h.snapshot` and
`home_ap_24h.ap_snapshot` operational events through the existing
`AuthorizationTelemetry.safe_emit_system()` path into `auth_telemetry.log`.
Loki/Grafana telemetry is not the AP-24H source of truth: calculations remain
owned by `HomeAp24ReadService`. Publication is lossy and fail-open, so missing
telemetry does not imply missing persisted AP evidence. Grafana must not
reinterpret raw Current State or Observation evidence into a second AP-24H
status calculation.

### Current State startup telemetry gap

On the accepted 2026-08-26 first restart, persisted Current State cycles proved successful runtime operation, but the expected `current_state.runtime_started` event was not found in the inspected journal. This is an **observability/telemetry gap**, not an active Current State runtime defect. Track any telemetry correction separately from the closed startup defect.

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
