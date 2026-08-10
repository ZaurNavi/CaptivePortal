# Индекс модулей

Status: current
Updated: 2026-08-10
Runtime baseline: main `ab776af3fc58dc090e17ecd20534abddc1f33ad3`

Колонка `Repository status` отражает код и default configuration этого commit. Фактическое production state приводится отдельно и не выводится из feature flag по умолчанию.

| Модуль | Repository status | Код | Документ | Feature flag | Источник | Хранилище | Events | Fail-open | Внешнее | Тесты |
|---|---|---|---|---|---|---|---|---|---|---|
| Portal authorization | active | `app/auth/`, `app/web/` | `modules/authorization.md` | нет | portal request | in-memory | auth telemetry | нет для решения доступа | Omada | `tests/test_auth_*`, `test_portal_entry.py` |
| Portal entry | active | `app/web/` | `modules/portal-entry.md` | нет | Omada redirect | in-memory | auth telemetry | нет | Flask, Omada | `tests/test_portal_*.py` |
| CAPPORT | active | `app/capport/`, `app/web/templates/portal.html` | `modules/capport.md` | `CAPPORT_ENABLED` | client IP, Omada | cache in-memory | auth telemetry | controlled errors | Omada | `tests/test_capport_*.py`, `test_auth_retry_frontend.py` |
| Auth telemetry | active | `app/auth_telemetry/` | `modules/auth-telemetry.md` | `AUTH_TELEMETRY_ENABLED` | auth flow | `auth_telemetry.log` | JSONL telemetry | да | filesystem | `tests/test_auth_telemetry.py` |
| Public authorization counter | active | `app/portal_counter/` | `modules/public-authorization-counter.md` | `PORTAL_COUNTER_ENABLED` | accepted portal open | `portal_counter.db` | operational log | да | SQLite | `tests/test_portal_counter.py` |
| Public traffic counter | active | `app/public_traffic/` | `modules/public-traffic-counter.md` | `PUBLIC_TRAFFIC_COUNTER_ENABLED` | normalized webhook journal | `public_traffic.sqlite3` | operational log | да | SQLite, journal | `tests/test_public_traffic*.py` |
| Authorized client snapshot | implemented; default disabled | `app/visitor_registry/snapshot_*` | `modules/authorized-client-snapshot.md` | `VISITOR_SNAPSHOT_ENABLED` | AUTHORIZED event + Omada | `visitor_snapshots.log` | JSONL journal/telemetry | да | Omada, filesystem | `tests/visitor_registry/test_snapshot_*.py` |
| Visitor registry | implemented; default disabled | `app/visitor_registry/registry_*` | `modules/visitor-registry.md` | `VISITOR_REGISTRY_ENABLED` | `visitor_snapshots.log` | `visitor_registry.sqlite3` | telemetry | да | filesystem, SQLite | `tests/visitor_registry/test_device_registry*.py` |
| Pending session cleaner | implemented; default disabled | `app/pending_sessions/`, `app/controllers/omada_pending_sessions.py` | `modules/pending-session-cleaner.md` | `PENDING_SESSION_CLEANER_ENABLED` | Omada inventory + local Auth protection | `pending_session_cleaner.log` + in-memory guard | JSONL data + operational telemetry | да; uncertainty blocks action | Omada, filesystem | `tests/pending_sessions/` |
| Omada webhook receiver | implemented; default disabled | `app/integrations/omada/webhook_*` | `modules/omada-webhook-receiver.md` | `OMADA_WEBHOOK_ENABLED` | HTTP webhook | `omada_webhook.log` | JSONL | да | Omada, Flask | `tests/integrations/omada/test_webhook_receiver.py` |
| Omada webhook normalizer | implemented; default disabled | `app/integrations/omada/webhook_normalizer.py` | `modules/omada-webhook-normalizer.md` | `OMADA_WEBHOOK_ENABLED` | raw webhook | `omada_webhook_normalized.log` | JSONL | да | filesystem | `tests/integrations/omada/test_webhook_*.py` |

## Production evidence

- Pending Client Session Cleaner: production active и owner-verified 2026-08-04. Fresh-token invalidation race закрыта; отдельная проверка worker/events после restart 2026-08-10 ещё не предоставлена.
- Authorized Client Snapshot и Visitor Registry: production pipeline ранее прошёл acceptance. Registry reported `state=ready`, `initial_backfill_completed=true`, `partial=false`, SQLite integrity PASS. Historical acceptance snapshot: 455 device cards и 696 snapshots; это не текущие постоянные counters.
- CAPPORT: bounded client discovery, same-page transition, monotonic progress и guarded post-`AUTHORIZED` revalidation находятся в deployed `main@ab776af`. Android captive-window live acceptance остаётся OPEN до отдельного evidence.
- Omada webhook modules: фактическая production activation этим snapshot не подтверждена.

Подробные current contracts и границы доказательств находятся в соответствующих module documents; status report целиком здесь не дублируется.
