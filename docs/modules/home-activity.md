# Home Activity — Visits and Traffic

Status: current module contract
Updated: 2026-08-26
Baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`
TASK: `TASK-HOME-ACTIVITY-01`

## Status

Implemented. Merged. Central Lab PASS. Production deployed. Core production acceptance PASS.

Repository default remains `WEB_ADMIN_HOME_ACTIVITY_ENABLED=false`; repository default and production activation are separate facts.

## Purpose

Home Activity is a read-only Home panel comparing **Today** with a selected period using two independent product metrics:

- Authorized Visits;
- Traffic.

No Activity HTTP request polls Omada and no new collector is introduced.

## Authorized Visits

Canonical unit: one qualifying Visit opened by one successful Visit-opening authorization.

Not:
- AuthSession count;
- authorization-row count;
- people count.

Source: persisted Visit Lifecycle facts.

Guest scope: canonical `CURRENT_STATE_CLIENT_SSIDS_JSON`.

If guest scope cannot be proven, the result is `unavailable` with `guest_scope_unproven`. Unknown/unproven membership is never converted to numeric zero. Opening-evidence integrity anomalies remain visible.

## Traffic

Source: persisted Visit Lifecycle offline source events.

Semantics:
- estimated;
- completed guest sessions only;
- attribution: `completed_session_end`;
- active sessions appear only after offline evidence;
- not WAN/Internet traffic;
- not billing traffic;
- not Current State traffic.

Visits and Traffic have independent status/coverage.

There is no artificial 31-day or 90-day Home Activity ceiling.

## Ingress SSID evidence

CAPPORT:
`Omada /clients ssid → CapportClient.ssid → PortalClientContext.ssid → AuthSession.ssid → VisitStartRequest.portal_ssid → Visit Lifecycle`.

External Portal:
- canonical parameter: `ssidName`;
- legacy fallback: `ssid`;
- conflicting valid non-empty values: do not guess; SSID/scope remains unproven.

## Production coverage — 2026-08-26

Site: `6a64f17630da7c70d232187a`
Timezone: `Asia/Baku`

```text
visits_coverage_from_utc  = 2026-08-26T17:46:55.982Z
traffic_coverage_from_utc = null
```

Visits safe boundary in Asia/Baku:
`2026-08-26 21:46:55.982 +04`.

Production aggregate after the safe boundary:

```text
range: 2026-08-26T17:46:55.982Z — 2026-08-26T19:02:10.407Z
total_visits: 14
verified_guest: 14
integrity_anomalies: 0
unproven_scope: 0
first_visit: 2026-08-26T17:49:27.214Z
latest_visit: 2026-08-26T19:01:55.320Z
```

Verdict: Visit source chain after the boundary is production-proven.

Traffic coverage is **not** proven while `traffic_coverage_from_utc=null`.

## Time-based UI interpretation

These are coverage semantics, not defects:

- on the evening of 2026-08-26, Today begins before the Visits safe boundary and may legitimately be partial/unavailable;
- from 2026-08-27 00:00 Asia/Baku, Today begins after the Visits coverage boundary;
- Last 24h is fully inside the proven Visits history only after 2026-08-27 21:46:55 Asia/Baku;
- Last 7d / Last 30d require natural accumulation of full history;
- Traffic does not become Complete merely with time while its coverage start is null.

The time-based confirmations are not deployment blockers and require no new deploy.

## APIs

Current Admin API family includes Today, selected-period and range-preview Activity reads under the authenticated Site-scoped `/admin/api/v1` boundary.

## Open evidence boundary

Traffic coverage start remains unresolved. Treat it as an evidence/coverage gap, not as permission to fabricate zero or Complete status.
