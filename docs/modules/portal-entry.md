# Portal entry

Status: active
Updated: 2026-08-04

## 1. Назначение

Принять Omada redirect, валидировать client context, создать/переиспользовать AuthSession и отдать portal UI.

## 2. Статус

Основной route GET / и auth session/retry routes присутствуют.

## 3. Граница ответственности

HTTP parsing/rendering и передача в PortalEntryHandler; authorization algorithm находится в AuthWorker.

## 4. Входные данные

site, clientMac или clientIp, apMac, ssid, redirectUrl, radioId.

## 5. Выходные данные

portal.html, JSON session state, retry response или controlled 4xx/5xx.

## 6. Основные модели

PortalClientContext, PortalEntryHandler, AuthSession.

## 7. Зависимости

Flask, AuthSessionManager, AuthWorker, telemetry, optional counter.

## 8. Fail-open

Counter/telemetry failure не блокирует portal. Missing identity fail-closed с controlled page.

## 9. Конфигурация

Host/port/debug и module settings через get_settings().

## 10. Data events

Нет собственного persistent journal.

## 11. Operational telemetry

Portal request, auth session и worker events.

## 12. Persistence

Нет; session in-memory.

## 13. Lifecycle

Routes создаются в create_app(); worker submit идёт в shared executor.

## 14. Тесты

tests/test_portal_entry.py, test_portal_design.py, test_proxy_headers.py, auth retry frontend.

## 15. Запрещённые изменения

Side effects при import, отдельный provider, безусловное доверие forwarded headers.

## 16. Связанные TASK

Определяет owner задачи.

## 17. Связанные ADR

Нужны для public route contract или proxy trust topology.
