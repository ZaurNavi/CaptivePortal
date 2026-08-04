# Authorization telemetry

Status: active
Updated: 2026-08-04

## 1. Назначение

Техническая диагностика authorization и CAPPORT без влияния на доступ.

## 2. Статус

Реализована и default enabled.

## 3. Граница ответственности

Sanitize, JSONL formatting, rotation и safe emit. Не является analytics data journal.

## 4. Входные данные

Event name, session/context identifiers, state, reason, timing и safe error text.

## 5. Выходные данные

Одна strict JSON запись на строку.

## 6. Основные модели

AuthorizationTelemetry, JsonLineFormatter, schema helpers и event constants.

## 7. Зависимости

Filesystem и Python logging.

## 8. Fail-open

Любая ошибка emit не ломает authorization.

## 9. Конфигурация

AUTH_TELEMETRY_ENABLED, LOG_PATH, LEVEL, SCHEMA_VERSION, rotation size/count.

## 10. Data events

Не применимо: события operational.

## 11. Operational telemetry

auth.* и capport.* из app/auth_telemetry/events.py.

## 12. Persistence

/opt/CaptivePortal/logs/auth_telemetry.log с rotation.

## 13. Lifecycle

Configure в create_app(); writer не создаёт worker.

## 14. Тесты

tests/test_auth_telemetry.py и capport telemetry tests.

## 15. Запрещённые изменения

Secrets, masked MAC, unbounded error text, telemetry exception в business flow.

## 16. Связанные TASK

Module/event TASK с documentation update.

## 17. Связанные ADR

Нужен при превращении telemetry в persistent business journal.
