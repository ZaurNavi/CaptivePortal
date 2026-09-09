# Индекс модулей

Status: current
Updated: 2026-09-09
Runtime implementation baseline: `main@7df71a8e807efd74b123117e78cb8d992c190fa1`
Runtime tree: `8f1342f0a0f1e8242642161e02b2f3276e6ddf51`

`Repository status` describes code/defaults, not production enabled-state.

| Module | Repository status | Code | Current contract | Persistence | Omada |
|---|---|---|---|---|---|
| Portal authorization | current | `app/auth/`, `app/web/` | `modules/authorization.md` | process memory + telemetry | yes |
| Portal entry | current | `app/web/` | `modules/portal-entry.md` | process memory | via shared provider |
| CAPPORT | current | `app/capport/` | `modules/capport.md` | bounded caches | yes |
| Auth telemetry | current | `app/auth_telemetry/` | `modules/auth-telemetry.md` | JSONL | no |
| Public authorization counter | current | `app/portal_counter/` | `modules/public-authorization-counter.md` | SQLite | no |
| Public traffic counter | current | `app/public_traffic/` | `modules/public-traffic-counter.md` | SQLite | no |
| Authorized snapshot | current; default disabled | `app/visitor_registry/snapshot_*` | `modules/authorized-client-snapshot.md` | JSONL | yes |
| Visitor Registry | current; default disabled | `app/visitor_registry/registry_*` | `modules/visitor-registry.md` | SQLite | **no** |
| Webhook receiver | current; default disabled | `app/integrations/omada/` | `modules/omada-webhook-receiver.md` | raw JSONL | inbound |
| Webhook normalizer | current; default disabled | `app/integrations/omada/` | `modules/omada-webhook-normalizer.md` | normalized JSONL | no |
| Pending Cleaner | current; default disabled | `app/pending_sessions/` | `modules/pending-session-cleaner.md` | JSONL + process guard | yes |
| Visit Lifecycle | current; default disabled | `app/visit_lifecycle/` | `modules/visit-lifecycle.md` | SQLite v2 | no |
| Observation Foundation | current; default disabled | `app/observations/` | `modules/observations.md` | SQLite v1 | yes |
| Current State | current; default disabled | `app/current_state/` | `modules/current-state.md` | SQLite v1 | yes |
| Analytics | current; default disabled | `app/analytics/` | `modules/analytics.md` | none | **no** |
| Analytics internal API | current; default disabled | `app/analytics/api.py` | `modules/analytics.md` | none | no |
| Admin Web | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | process security state | **no** |
| Device Current Context | current; default disabled | `app/admin_web/`, `app/current_state/read_service.py`, `app/analytics/current_guest_traffic.py` | `modules/admin-web.md`, `modules/current-state.md`, `modules/analytics.md` | reads Current State only; no new persistence | no |
| Home Live | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |
| Current Traffic | current | `app/analytics/current_traffic.py` | `modules/analytics.md` | reads Observation | no |
| Home Traffic | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |
| Home Activity | current; default disabled | `app/analytics/home_activity.py`, `app/admin_web/` | `modules/home-activity.md` | reads Visit Lifecycle | no |
| Traffic Section Foundation | current; default disabled | `app/admin_web/` | `modules/traffic.md` | none | no |
| Traffic Current Network Throughput | current; default disabled | `app/admin_web/`, `app/analytics/current_traffic.py` | `modules/traffic.md` | reads Observation | no |
| Historical Traffic Read Foundation | current | `app/analytics/historical_traffic.py`, source gateway | `modules/traffic.md` | reads Observation | no |
| Historical Traffic Projection | current; default disabled | `app/traffic_projection/` | `modules/traffic.md` | SQLite derived projection | no |
| Traffic Network History | current; default disabled | `app/admin_web/`, Historical Traffic | `modules/traffic.md` | none | no |
| Traffic Period Statistics | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Traffic Peak Load | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Traffic by AP | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Independent Traffic Range per Panel | current; default disabled | `app/admin_web/` | `modules/traffic.md` | page-local memory only | no |
| AP Traffic Share | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Online Guest Traffic Read Foundation | current | `app/analytics/current_guest_traffic.py`, `app/current_state/read_service.py` | `modules/traffic.md`, `modules/analytics.md` | reads Current State | no |
| Online Guests Traffic | current; default disabled | `app/admin_web/`, `app/analytics/current_guest_traffic.py` | `modules/traffic.md`, `modules/admin-web.md` | reads Current State | no |
| Completed Guest Session Traffic | current; default disabled | `app/admin_web/`, `app/analytics/completed_guest_traffic.py` | `modules/traffic.md`, `modules/analytics.md`, `modules/admin-web.md` | reads Visit + Observation | no |
| Consolidated Traffic Evidence | current; default disabled | `app/admin_web/traffic_evidence.py`, serializer/routes/UI | `modules/traffic.md`, `modules/admin-web.md` | composition only; no persistence | no |

## Current production evidence

Owner-provided production checkpoint 2026-09-09:

```text
HEAD: 7df71a8e807efd74b123117e78cb8d992c190fa1
tree: 8f1342f0a0f1e8242642161e02b2f3276e6ddf51

TRAFFIC-00: DONE
TRAFFIC-01 Current: production active
TRAFFIC-02-READ: DONE
TRAFFIC-02 History: production active
TRAFFIC-02-PERF-01: DONE
TRAFFIC-03 Statistics: production active
TRAFFIC-04 Peak: production active
TRAFFIC-05 Traffic by AP: production active
TRAFFIC-RANGE-01: production active / production acceptance PASS
TRAFFIC-06 AP Traffic Share: production active / production acceptance PASS
TRAFFIC-07-READ: DONE / READ FOUNDATION IMPLEMENTED
TRAFFIC-07 Online Guests Traffic: COMPLETE / PRODUCTION ACTIVE
TASK-DB-BASELINE-SYNC-01: CLOSED / PASS
TRAFFIC-08 Completed Guest Session Traffic: CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
TRAFFIC-09 Consolidated Traffic Evidence: COMPLETED / PRODUCTION ACTIVE
TASK-DEVICE-CARD-01 Current Device Context: COMPLETE / PRODUCTION ACTIVE

WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true

captive-portal.service=active
```

## Device UI follow-on

```text
TASK-WEB-DEVICE-UI-01 = IN PROGRESS / LAB REVIEW PENDING
NOT MERGED
NOT DEPLOYED
NOT CURRENT PRODUCTION
```

This follow-on is presentation-layer work and does not change the current
authoritative DEVICE-CARD-01 functional status.

## Next Traffic item

Current closure:

```text
TASK-DB-BASELINE-SYNC-01 = CLOSED / PASS
TASK-TRAFFIC-08 = CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
TASK-TRAFFIC-09 = COMPLETED / PRODUCTION ACTIVE
TASK_TRAFFIC_09_PRODUCTION = ACTIVE
```

No next Traffic TASK is currently assigned. No successor becomes canonical until
separately approved by Owner / Tech Lead.

## Production evidence rule

A historical production PASS proves a feature worked at a named artifact/time.
It does not convert repository defaults into production configuration and does
not prove current health after later changes.
