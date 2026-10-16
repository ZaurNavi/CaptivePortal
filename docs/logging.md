# Logging, telemetry and data journals

Status: current
Updated: 2026-08-28
Baseline: `main@d41888ade1814a2c0e965ff0cd51212e7dc4bd5f`

## Device Fingerprint Evidence

The isolated service logger is `captivportal.device_fingerprint`. Its telemetry
contains bounded operational identifiers, statuses, counts, runtime state and
artifact identity only. It never logs Bearer credentials, raw request bodies,
evidence payloads, MAC addresses, or IP addresses. The dedicated Werkzeug
request handler strips the entire query string for the fingerprint namespace.

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

### Visit reader compact completed reports (QIO-01D)

`VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED=false` is the
startup-only default. OFF retains one INFO `visit.reader_scan_completed` for
each exception-free scan, including incomplete scans, with only the existing
`processed_line_count`, `scan_complete`, `duration_ms` fields. Scan frequency,
source processing, SQLite operations, retries and health are not reduced.

Opt-in ON suppresses only repeated successful complete unchanged empty scans.
Reports retain the same event, level and envelope and add:

| Field | Meaning |
|---|---|
| `reader_report_schema_version` | integer `2` |
| `report_reason` | `initial`, `activity`, `incomplete`, `progress`, `source_change`, `recovery`, `idle_transition`, `heartbeat` |
| `suppressed_empty_scans` | number of preceding suppressed healthy complete scans |
| `scans_represented` | always `suppressed_empty_scans + 1`, including this completed scan only |

Existing fields describe the **current** scan, not an aggregate. Priority is
incomplete, then activity, committed retry progress, source change, recovery,
initial, active-to-idle transition, then heartbeat/quiet suppression. Thus the
first report may be activity/progress/source_change rather than initial, but
it is always immediate. Error/deferred scans do not count as completed scans.
All existing failed/deferred/starvation/source/invalid-input events retain
their original frequency, fields and level. Source changes are detected from
already available local state, not extra database queries.

Quiet heartbeat is attempted at the first healthy complete scan whose
monotonic completion time is at least 60 seconds after the previous report.
A regressing/non-finite clock delta conservatively reports instead of hiding
scans. There is no new timer, thread or shutdown flush. With the existing
5-second cadence and 20-second budget, allow approximately 85 seconds plus
scheduler jitter; 60 seconds is not a durable delivery SLA. For enabled-reader
monitoring, report age over 120 seconds is stale/needs investigation; over
180 seconds is unavailable/unknown and requires escalation. These are
observability thresholds, not changes to source health or authorization.

Counters reset after an attempted report, even if the fail-open emitter
cannot deliver it. Restart discards unpublished counters. They are not
authoritative durable scan counts or proof of Loki delivery.

**Consumer migration is required before production activation.**
`count_over_time` on completed events measures emitted reports under ON,
not the number of completed scans. A mixed legacy/v2 consumer must count
legacy events with weight one and v2 with weight `scans_represented`.
Keep reported events, represented scans, activity, incomplete/fail/deferred
and freshness as distinct series. Missing heartbeats require investigation;
silence is not successful execution. External panel 138/alerts/consumers need
independent query validation and Owner approval. No dashboard/query rollout
or live Grafana change is authorized by this code change. Initial deployment
keeps the flag absent/OFF. Fewer messages do not prove physical HDD IOPS savings.

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

## Fingerprint sensor

Sensor telemetry is structured and allowlisted. It may report source kind,
health transition, capture/dedup counters, Suricata aggregate counters, spool
capacity and delivery outcomes. It must not contain packet bytes, destination
identity, SNI, full EVE, authorization headers or the producer credential.
