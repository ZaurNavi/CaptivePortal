# Omada Webhook Receiver

Status: implemented-disabled
Updated: 2026-08-04

## 1. Назначение

Безопасно принять Omada webhook, проверить source/auth/body и записать redacted raw envelope.

## 2. Статус

Реализован; OMADA_WEBHOOK_ENABLED=false по default.

## 3. Граница ответственности

HTTP boundary, authentication, redaction, raw journal и передача processor. Семантический parsing принадлежит normalizer.

## 4. Входные данные

POST /api/integrations/omada/webhook, source IP, headers, query и bounded body.

## 5. Выходные данные

Controlled HTTP response и omada.webhook_received record.

## 6. Основные модели

OmadaWebhookConfig, WebhookEnvelope, OmadaWebhookReceiver, journal/security/redaction helpers.

## 7. Зависимости

Flask, filesystem raw journal и optional normalization processor.

## 8. Fail-open

Disabled receiver не влияет на portal. Invalid request отклоняется; persistence failure не выдаётся как accepted.

## 9. Конфигурация

ENABLED, allowed IPs, auth mode, shared secret/header token, max body bytes и raw/normalized paths.

## 10. Data events

omada.webhook_received с redacted headers/query/payload.

## 11. Operational telemetry

HTTP/security/persist errors через application logger.

## 12. Persistence

omada_webhook.log с rotation.

## 13. Lifecycle

Blueprint/journals/processor создаются в create_app() только при valid enabled config.

## 14. Тесты

tests/integrations/omada/test_webhook_receiver.py и normalized live tests.

## 15. Запрещённые изменения

Принимать без source/auth policy, unbounded body, secrets в raw journal, возвращать success до required persistence.

## 16. Связанные TASK

Webhook-specific TASK.

## 17. Связанные ADR

Нужен при изменении trust model или durability semantics.
