# Authorized Client Snapshot Collector

Status: implemented-disabled
Updated: 2026-08-04

## 1. Назначение

После подтверждённой authorization асинхронно получить полную карточку клиента Omada и записать устойчивый JSONL snapshot.

## 2. Статус

Реализован в main; VISITOR_SNAPSHOT_ENABLED=false по default.

## 3. Граница ответственности

Принимает immutable auth context, использует shared provider и пишет journal. Не управляет registry SQLite.

## 4. Входные данные

site_id, client MAC/IP, session/run identifiers, final auth reason и timestamp.

## 5. Выходные данные

visitor.client_snapshot.captured либо failure/skip telemetry; submit outcome caller получает немедленно.

## 6. Основные модели

AuthorizedClientSnapshotCollector, AuthorizedClientSnapshotRequest, AuthorizedClientAuthContext, NormalizedClientSnapshot, SnapshotSubmitOutcome.

## 7. Зависимости

Shared OmadaProvider.get_client_snapshot(), normalizer, writer, telemetry и bounded executor.

## 8. Fail-open

Queue full, stale job, Omada failure или writer failure не изменяют AUTHORIZED session.

## 9. Конфигурация

ENABLED, log file, max workers/pending/job age, request timeout, two retry delays, rotation и shutdown timeout.

## 10. Data events

Schema v1 JSONL; captured record сохраняет полный MAC и safe sanitized raw client result.

## 11. Operational telemetry

Submit, queue, provider retry/failure, write и lifecycle events.

## 12. Persistence

/opt/CaptivePortal/logs/visitor_snapshots.log, rotating writer.

## 13. Lifecycle

Создаётся в run.py, стартует до service loop, stop_accepting и bounded drain выполняются при shutdown.

## 14. Тесты

tests/visitor_registry/test_snapshot_*.py и integration/runtime tests.

## 15. Запрещённые изменения

Блокировать AuthWorker, создавать provider, unbounded queue/retry, писать SQLite registry напрямую.

## 16. Связанные TASK

Final collector v1.2 — historical source; текущий contract хранится здесь и в tests.

## 17. Связанные ADR

Нужен при изменении shared provider, event schema или asynchronous lifecycle.
