# Индекс модулей

Status: current
Updated: 2026-09-13
Runtime implementation baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`
Runtime tree: `8312658be3ba272998f46212d9bad76950e3867e`

`Repository status` describes code/defaults, not production enabled-state.

| Module | Repository status | Code | Current contract | Persistence | Omada |
|---|---|---|---|---|---|
| Portal authorization | current | `app/auth/`, `app/web/` | `modules/authorization.md` | process memory + telemetry | yes |
| Portal entry | current | `app/web/` | `modules/portal-entry.md` | process memory | via shared provider |
| CAPPORT | current | `app/capport/` | `modules/capport.md` | bounded caches | yes |
| Auth telemetry | current | `app/auth_telemetry/` | `modules/auth-telemetry.md` | JSONL | no |
| Device Fingerprint Evidence | current; default disabled | `app/device_fingerprint/` | `modules/device-fingerprint.md` | isolated SQLite v1 | no |
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
| Device List Context | current; production active | Admin Web + Registry + Current State | `modules/admin-web.md` | no new persistence | no |
| Devices Web Designer presentation | current production presentation | `app/admin_web/static/admin.css`, `app/admin_web/static/admin.js` | `modules/admin-web.md`, `agents/web-designer-role.md` | none | no |
| Admin Web local asset library | current production presentation | `app/admin_web/static/icons/` | `modules/admin-web.md` | static assets only | no |
| Canonical Device Type lexical key | current production foundation | `app/common/device_type.py` + read serializers/services | `architecture.md`, `modules/current-state.md`, `modules/observations.md`, `modules/visitor-registry.md`, `modules/analytics.md` | read-time additive key; raw persistence unchanged | no |
| Home Online Devices presentation | current production presentation | `app/admin_web/static/admin.css`, `app/admin_web/static/admin.js` | `modules/admin-web.md` | none | no |
| Device Type + SNR presentation | current production presentation | `app/admin_web/static/admin.css`, `app/admin_web/static/admin.js` | `modules/admin-web.md` | none | no |
| Home Live | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |
| Current Traffic | current | `app/analytics/current_traffic.py` | `modules/analytics.md` | reads Observation | no |
| Home Traffic | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |
| Home Activity | current; default disabled | `app/analytics/home_activity.py`, `app/admin_web/` | `modules/home-activity.md` | reads Visit Lifecycle | no |
| Home System Health | current; default disabled | `app/admin_web/home_health*.py` + bounded source read evidence | `modules/admin-web.md` | none | no request-time Omada |
| Home AP-24H | current; default disabled | `app/admin_web/home_ap_24h*.py` | `modules/admin-web.md` | reads Current State + Observation; no new persistence | no |
| Home AP-24H telemetry | current; default disabled | `app/admin_web/home_ap_24h_telemetry.py` | `modules/admin-web.md` | existing Authorization Telemetry sink | no |
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

Owner-provided production checkpoint 2026-09-13:

```text
HEAD: 3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
tree: 8312658be3ba272998f46212d9bad76950e3867e

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
TASK-DEVICE-LIST-CONTEXT-01: CLOSED / PRODUCTION ACTIVE
TASK-WEB-DEVICE-UI-01: CLOSED / PRODUCTION ACTIVE
TASK-WEB-ASSET-LIBRARY-01: CLOSED / PRODUCTION PASS
TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION: CLOSED / PRODUCTION PASS
TASK-TEST-BASELINE-CLEANUP-01: FINAL ACCEPTED / MERGED / DEPLOYED / PRODUCTION PASS
TASK-HOME-HEALTH-01: MERGED / repository default disabled / production flag host-verified
TASK-HOME-AP-24H-01 + fixes: MERGED / repository default disabled / production flag host-verified
TASK-HOME-AP-24H-TELEMETRY-01: MERGED / repository default disabled
Windows Central Lab current runner: V7 strict
Windows Central Lab V6 fixed: historical / audit only

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
TASK-WEB-DEVICE-UI-01 = CLOSED / PRODUCTION ACTIVE
PR #110 MERGED
PRODUCTION VERIFIED
```

This follow-on is presentation-layer work and does not change the current
authoritative DEVICE-CARD-01 functional status.

## Traffic Projection lifecycle P0 closure

```text
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01
CLOSED / PRODUCTION ACCEPTANCE PASS

FINAL-R5 + FIX-1
PR #111 merged

production=7472d67274ea5aaea2a20df6b613b78d5bb70f42
tree=3950df6d400049ed16a823032c6740396cd61137
```

Projection remains derived/rebuildable from authoritative Observation. The
accepted lifecycle fix protects frozen reconcile proof windows, resumes durable
repair after restart, and adds operational health/artifact lifecycle evidence.

Current production:

```text
Projection health=healthy
Historical Traffic=restored
traffic-projection.service=active + enabled
```

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
