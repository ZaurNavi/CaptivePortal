# Visitor Device Registry

Status: implemented-disabled
Updated: 2026-08-04

## 1. Назначение

Построить durable registry уникальных visitor devices из authorized snapshot journal.

## 2. Статус

Реализован в main; VISITOR_REGISTRY_ENABLED=false до отдельной production activation.

## 3. Граница ответственности

Читает только visitor_snapshots.log и ведёт SQLite registry. Omada API запрещён.

## 4. Входные данные

Strict JSONL captured snapshot events, включая rotated files и restart checkpoint.

## 5. Выходные данные

Device/visit aggregates, status и read-only CLI.

## 6. Основные модели

RegistryConfig, VisitorRegistryReader/Service/Repository/Worker, VisitorRegistryReadService, RegistryStatus.

## 7. Зависимости

Filesystem, SQLite, timezone и snapshot schema v1.

## 8. Fail-open

Invalid line, rotation, SQLite busy/corruption или worker failure не ломают portal; module becomes unavailable с telemetry.

## 9. Конфигурация

ENABLED, DB_PATH, snapshot log source, scan interval, shutdown timeout, max line bytes и timezone.

## 10. Data events

Потребляет visitor.client_snapshot.captured; своего persistent JSONL не создаёт.

## 11. Operational telemetry

Start/stop, scan, skip, recovery, database/source errors.

## 12. Persistence

visitor_registry.sqlite3 schema v1 с reader checkpoints и registry tables.

## 13. Lifecycle

Создаётся/стартует run.py; один fixed-delay worker на process; shutdown выполняет bounded final scan.

## 14. Тесты

tests/visitor_registry/test_device_registry.py и test_device_registry_worker.py.

## 15. Запрещённые изменения

Любой Omada call, чтение auth memory, schema change без migration, overlapping scan.

## 16. Связанные TASK

Visitor Registry v2 + обязательные дополнения — historical source; activation отдельным TASK.

## 17. Связанные ADR

Нужен при source/schema/process topology changes.
