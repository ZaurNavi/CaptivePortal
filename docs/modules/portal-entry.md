# Portal entry

Status: active
Updated: 2026-08-26

## 1. Назначение

Принять Omada redirect, валидировать client context, создать/переиспользовать AuthSession и отдать portal UI.

## 2. Статус

Основной route GET / и auth session/retry routes присутствуют.

## 3. Граница ответственности

HTTP parsing/rendering и передача в PortalEntryHandler; authorization algorithm находится в AuthWorker.

## 4. Входные данные

External Portal: `site`, `clientMac` или `clientIp`, `apMac`, canonical `ssidName`, legacy fallback `ssid`, `redirectUrl`, `radioId`.

SSID contract:
- valid `ssidName` wins when legacy `ssid` is absent;
- legacy `ssid` remains fallback;
- if both non-empty values exist and conflict, SSID is left unproven (`None`) rather than guessed;
- the resulting SSID is propagated through PortalClientContext/AuthSession into Visit opening evidence.

## 5. Выходные данные

portal.html, structured `PortalEntryResult`, JSON session state, retry response
или controlled 4xx/5xx.

## 6. Основные модели

PortalClientContext, PortalEntryResult, PortalEntryHandler, AuthSession.

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

`PortalEntryHandler.prepare_portal()` является единственной точкой
create/reuse, counter, telemetry и worker submit. HTML wrapper
`open_portal()` только рендерит полученный structured result; CAPPORT JSON
wrapper сериализует тот же результат. Поэтому один HTTP-запрос не может
повторно создать session, увеличить portal counter или запустить второй worker.

При worker-start failure authoritative snapshot менеджера возвращается вместе
с уже созданным `session_id`: `WORKER_START_FAILED` остаётся retryable, а
`CONFIGURATION_ERROR` terminal/non-retryable. Wrapper не подменяет эти признаки
собственными значениями.

## 14. Тесты

tests/test_portal_entry.py, test_portal_design.py, test_proxy_headers.py,
test_capport_discovery_frontend.py, auth retry frontend.

## 15. Запрещённые изменения

Side effects при import, отдельный provider, безусловное доверие forwarded headers.

## 16. Связанные TASK

Определяет owner задачи.

## 17. Связанные ADR

Нужны для public route contract или proxy trust topology.
