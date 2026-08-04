# Public Authorization Counter

Status: active
Updated: 2026-08-04

## 1. Назначение

Посчитать принятые открытия public portal и отдать агрегат frontend/API.

## 2. Статус

app/portal_counter реализован; default enabled.

## 3. Граница ответственности

Record accepted portal open. Не подтверждает успешную Omada authorization и не считает traffic.

## 4. Входные данные

Результат PortalEntryHandler open operation.

## 5. Выходные данные

Counter snapshot и public API payload.

## 6. Основные модели

PortalCounterService, PortalCounterRepository, CounterSnapshot, RecordOpenResult.

## 7. Зависимости

SQLite, portal entry и optional public traffic service в combined API.

## 8. Fail-open

Unavailable repository не блокирует portal; API сообщает controlled unavailable.

## 9. Конфигурация

PORTAL_COUNTER_ENABLED, DB_PATH, TIMEZONE, API_ENABLED.

## 10. Data events

Нет JSONL data journal.

## 11. Operational telemetry

Application log на failure/startup; отдельная stable event schema не заявлена.

## 12. Persistence

portal_counter.db, schema version 1.

## 13. Lifecycle

Service создаётся в create_app(); отдельного thread нет.

## 14. Тесты

tests/test_portal_counter.py и portal entry tests.

## 15. Запрещённые изменения

Считать open как AUTHORIZED, блокировать portal при SQLite failure, менять schema без migration.

## 16. Связанные TASK

Определяет owner.

## 17. Связанные ADR

Нужен при изменении business meaning или persistence schema.
