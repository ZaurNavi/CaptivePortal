# Public completed-session traffic counter

Status: active
Updated: 2026-08-04

## 1. Назначение

Агрегировать traffic завершённых public SSID sessions из normalized Omada webhook journal.

## 2. Статус

app/public_traffic реализован; default enabled.

## 3. Граница ответственности

Последовательно читать journal, классифицировать завершённые sessions и обновлять aggregates. Не управлять Omada.

## 4. Входные данные

omada_webhook_normalized.log и configured SSID.

## 5. Выходные данные

TrafficSnapshot/API/frontend values и administrative reset summary.

## 6. Основные модели

PublicTrafficConfig, ReaderState, TrafficEvent, PublicTrafficRepository/Service/Worker.

## 7. Зависимости

Filesystem journal, SQLite, timezone и portal counter route.

## 8. Fail-open

Worker/repository failure не ломает portal; service становится unavailable.

## 9. Конфигурация

ENABLED, SSID, DB_PATH, source normalized log, scan interval и frontend refresh.

## 10. Data events

Источник — normalized webhook schema v1; собственного JSONL нет.

## 11. Operational telemetry

Start/stop, scan/error/recovery через application logger.

## 12. Persistence

public_traffic.sqlite3, schema version 2, reader checkpoints и aggregates.

## 13. Lifecycle

Worker создаётся в create_app(), запускается/останавливается run.py; fixed-delay.

## 14. Тесты

tests/test_public_traffic.py и test_public_traffic_frontend.py.

## 15. Запрещённые изменения

Обращение к Omada, overlapping scans, schema change без migration, SSID password в config/log.

## 16. Связанные TASK

Определяет owner.

## 17. Связанные ADR

Нужен при изменении event source, traffic semantics или schema.
