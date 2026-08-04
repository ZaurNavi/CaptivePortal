# Omada Webhook Normalizer

Status: implemented-disabled
Updated: 2026-08-04

## 1. Назначение

Преобразовать raw Omada text items в стабильные schema v1 JSONL events.

## 2. Статус

Реализован вместе с disabled webhook feature. Событие omada.client_authorized в snapshot main отсутствует; отдельное ТЗ не доказывает implementation.

## 3. Граница ответственности

Deterministic parsing, event ids/time fields, normalized journal и backfill. Не вызывает Omada и не настраивает Alloy/Grafana.

## 4. Входные данные

omada.webhook_received raw records или backfill JSONL.

## 5. Выходные данные

client_online/offline/unauthorized/authentication_expired/connection_failed либо webhook_unclassified/diagnostic events.

## 6. Основные модели

normalize_webhook(), EventHandler registry, OmadaWebhookProcessor и normalized journal.

## 7. Зависимости

Raw journal schema, filesystem writer и deterministic parser helpers.

## 8. Fail-open

Unparseable text создаёт unclassified/diagnostic record; normalization failure не ломает portal.

## 9. Конфигурация

Использует OMADA_WEBHOOK_ENABLED и normalized log path; schema version 1 в code.

## 10. Data events

omada.client_online, client_offline, client_unauthorized, client_authentication_expired, client_connection_failed, webhook_unclassified и diagnostics.

## 11. Operational telemetry

Processor/write/backfill diagnostics; не подменяют data events.

## 12. Persistence

omada_webhook_normalized.log; backfill пишет отдельный target и не смешивается с live.

## 13. Lifecycle

Processor вызывается receiver; отдельного background worker нет. CLI backfill запускается отдельно.

## 14. Тесты

tests/integrations/omada/test_webhook_normalizer.py, test_webhook_backfill.py, test_webhook_normalized_live.py.

## 15. Запрещённые изменения

Менять schema/event semantics без docs/tests; сохранять secrets; считать непроверенный pattern authorized; изменять Alloy/Loki/Grafana.

## 16. Связанные TASK

ТЗ на client_authorized остаётся pending, пока main code/tests не подтверждают event.

## 17. Связанные ADR

Нужен при schema version change или изменении raw/normalized durability.
