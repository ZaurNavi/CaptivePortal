# Индекс модулей

Status: current
Updated: 2026-08-25
Runtime baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

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
| Current Traffic | current when Analytics sources healthy | `app/analytics/current_traffic.py` | `modules/analytics.md` | none | no |
| Home Traffic | current; default disabled | `app/admin_web/` | `modules/admin-web.md` | none | no |

## Not current implementation

**Home Activity** is not present in `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`. It may be an approved external change-intent, but must not be described as merged/current until the implementation is present in `main`.

## Production evidence rule

A historical production PASS can prove that a feature worked at a particular artifact/time. It does not convert repository defaults into current production configuration and does not prove current health.
