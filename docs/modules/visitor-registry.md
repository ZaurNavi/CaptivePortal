# Visitor Device Registry

Status: implemented; repository default disabled; production ready/active (historical acceptance verified)
Updated: 2026-08-10
Runtime baseline: main `ab776af3fc58dc090e17ecd20534abddc1f33ad3`

## 1. Назначение

Построить durable registry уникальных visitor devices из authorized snapshot journal.

## 2. Статус

Repository default: `VISITOR_REGISTRY_ENABLED=false`. При этом current production evidence отдельно подтверждает включённый и готовый Registry. Default в Git не используется как вывод о фактическом EnvironmentFile.

Production acceptance на момент закрытия этапа:

- `registry_state=ready`;
- `initial_backfill_completed=true` (100%);
- `partial=false`;
- SQLite integrity PASS;
- 455 device cards;
- 696 snapshots.

Последние два числа — historical acceptance snapshot, а не постоянные текущие counters. После общего restart 2026-08-10 отдельная повторная проверка Registry lifecycle/counters в status report отсутствует.

## 3. Граница ответственности

Registry читает только `visitor_snapshots.log` и ведёт SQLite registry. Omada API и auth memory запрещены. Следующий функциональный этап Visit Lifecycle не входит в завершённый Visitor Registry и требует отдельного TASK.

## 4. Входные данные

Strict JSONL `visitor.client_snapshot.captured` из active и rotated snapshot journals, включая restart checkpoint. Повторяющийся MAC сам по себе не означает duplicate: различия проверяются по `snapshot_id`, `auth_session_id`, uptime, traffic и signal fields.

## 5. Выходные данные

Device/visit aggregates, registry status и read-only CLI. Persistent all-time карточки находятся в SQLite/CLI; Loki/Grafana отображают journal events только за выбранный диапазон времени.

## 6. Основные модели

`RegistryConfig`, `VisitorRegistryReader`, `VisitorRegistryService`, `VisitorRegistryRepository`, `VisitorRegistryWorker`, `VisitorRegistryReadService`, `RegistryStatus`.

## 7. Зависимости

Filesystem, SQLite, timezone и snapshot schema v1. Registry не зависит от OmadaProvider.

## 8. Fail-open

Invalid line, rotation, SQLite busy/corruption или worker failure не ломают portal; module becomes unavailable с telemetry. PR #32 усилил SQLite error classification, startup/shutdown recovery и integration coverage.

## 9. Конфигурация

`VISITOR_REGISTRY_ENABLED`, `VISITOR_REGISTRY_DB_PATH`, source snapshot log, scan interval, shutdown timeout, max line bytes и timezone. Repository default feature state — disabled; production state проверяется отдельно.

## 10. Data events

Потребляет `visitor.client_snapshot.captured`; собственного persistent JSONL не создаёт. Успешный snapshot содержит фактический SSID в `client.ssid`. `auth_context.portal_ssid` может быть `null` и не является единственным production filter source.

## 11. Operational telemetry

Start/stop, scan, skip, recovery, database/source errors и registry state. Наблюдавшийся при controlled activation `visitor_registry_shutdown_timeout` является историческим activation event, а не active incident current baseline.

Production observability path:

    /opt/CaptivePortal/logs/visitor_snapshots.log*
    → Alloy
    → job="captive_portal_visitor_snapshots"
    → Loki
    → Grafana

Production dashboard v40 сохранил UID `captive-portal-auth-v3-fixed`, содержит 104 панели и 9 variables. Snapshot panels фильтруют успешные события по Loki field `client_ssid`, извлечённому из `client.ssid`; failed events не отбрасываются SSID-фильтром при отсутствии client object.

## 12. Persistence

`visitor_registry.sqlite3` schema v1 с reader checkpoints и registry tables. Snapshot journal остаётся источником повторного backfill/recovery; overlapping scans запрещены.

## 13. Lifecycle

Создаётся и стартует в `run.py`; один fixed-delay worker на process; shutdown выполняет bounded final scan. Module fail-open относительно portal authorization. Post-restart health после deployment 2026-08-10 остаётся отдельной verification action.

## 14. Тесты

`tests/visitor_registry/test_device_registry.py` и `test_device_registry_worker.py` покрывают persistence, reader rotation/checkpoints, classification, CLI/status, SQLite failures, worker lifecycle и shutdown behavior. Полный current-main release gate описан в `docs/testing.md` и пока не подтверждён.

## 15. Запрещённые изменения

Любой Omada call, чтение auth memory, schema change без migration, overlapping scan, подмена all-time SQLite карточек логовыми Grafana panels или трактовка повторного MAC как duplicate без проверки event identity/context.

## 16. Связанные TASK

Visitor Registry v2 и обязательные дополнения — historical sources. Production readiness закрыта PR #32. Visit Lifecycle является отдельным future functional stage.

## 17. Связанные ADR

Нужен при source/schema/process topology changes.
