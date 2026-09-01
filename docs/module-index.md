# Индекс модулей

Status: current
Updated: 2026-09-01
Runtime implementation baseline: `main@daf68e91fc759188980cf8741913e6b60a58eb62`
Runtime tree: `b0e2f028eecf6aec9d86e35542c33e7105209335`

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
| Home Live | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |
| Current Traffic | current | `app/analytics/current_traffic.py` | `modules/analytics.md` | reads Observation | no |
| Home Traffic | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |
| Home Activity | current; default disabled | `app/analytics/home_activity.py`, `app/admin_web/` | `modules/home-activity.md` | reads Visit Lifecycle | no |
| Traffic Section Foundation | current; default disabled | `app/admin_web/` | `modules/traffic.md` | none | no |
| Traffic Current Network Throughput | current; default disabled | `app/admin_web/`, `app/analytics/current_traffic.py` | `modules/traffic.md` | reads Observation | no |
| Historical Traffic Read Foundation | current | `app/analytics/historical_traffic.py`, source gateway | `modules/traffic.md` | reads Observation | no |
| Traffic Network History | current; default disabled | `app/admin_web/`, Historical Traffic | `modules/traffic.md` | none | no |
| Traffic Period Statistics | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Traffic Peak Load | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Traffic by AP | current; default disabled | `app/admin_web/`, `app/analytics/historical_traffic.py` | `modules/traffic.md` | none | no |
| Independent Traffic Range per Panel | current; default disabled | `app/admin_web/` | `modules/traffic.md` | page-local memory only | no |

## Current production evidence

Owner-provided production checkpoint 2026-09-01:

```text
HEAD: daf68e91fc759188980cf8741913e6b60a58eb62
tree: b0e2f028eecf6aec9d86e35542c33e7105209335

TRAFFIC-00: DONE
TRAFFIC-01 Current: production active
TRAFFIC-02-READ: DONE
TRAFFIC-02 History: production active
TRAFFIC-02-PERF-01: DONE
TRAFFIC-03 Statistics: production active
TRAFFIC-04 Peak: production active
TRAFFIC-05 Traffic by AP: production active
TRAFFIC-RANGE-01: production active / production acceptance PASS

WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true

captive-portal.service=active
```

## Next Traffic item

```text
TRAFFIC-06 — AP Traffic Share
NEXT / DRAFT REQUESTED / NOT IMPLEMENTED
```

Current idea only: share of accepted Network Traffic evidence within selected
range. `sample count != traffic share`.

## Production evidence rule

A historical production PASS proves a feature worked at a named artifact/time.
It does not convert repository defaults into production configuration and does
not prove current health after later changes.
