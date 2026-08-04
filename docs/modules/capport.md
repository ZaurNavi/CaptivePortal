# CAPPORT

Status: active
Updated: 2026-08-04

## 1. Назначение

RFC 8908/8910 captive portal API и login bridge в общий authorization flow.

## 2. Статус

app/capport реализован; CAPPORT_ENABLED=true в snapshot default.

## 3. Граница ответственности

Определить client по разрешённому source IP, получить state из Omada и передать login в PortalEntryHandler. Не авторизовать самостоятельно.

## 4. Входные данные

Guest source IP, configured site, CAPPORT API/login request.

## 5. Выходные данные

application/captive+json state, redirect/login response или controlled error.

Если `/capport/login` временно не может определить client, endpoint
возвращает HTTP 200 с режимом `CAPPORT_DISCOVERY`, не создавая AuthSession и
не запуская AuthWorker. Страница повторяет lookup полной навигацией через
`window.location.replace()` каждые две секунды в пределах server-bounded
deadline до 60 секунд; после истечения доступен ручной retry. После обнаружения
client запрос входит в штатный `PortalClientContext → AuthSessionManager →
AuthWorker` flow.

## 6. Основные модели

CapportConfig, CapportClient, CapportState, CapportService.

## 7. Зависимости

Shared OmadaProvider, PortalEntryHandler, auth telemetry, Flask blueprint.

## 8. Fail-open

Lookup failure возвращает controlled unavailable/captive response и не ломает Omada External Portal.

## 9. Конфигурация

CAPPORT_ENABLED, SITE_ID, PUBLIC_BASE_URL, API/LOGIN paths, allowed networks и bounded cache TTL.

## 10. Data events

Нет отдельного journal.

## 11. Operational telemetry

capport.api_request, client_resolved/not_found, lookup_failed, state_response, portal_opened.

## 12. Persistence

Короткий success/failure cache только in-memory.

## 13. Lifecycle

Service/blueprint создаются в create_app() с общим controller.

Бесшовный discovery на одной открытой странице через `fetch()` не входит в
текущий контракт и отложен до оценки production-эффекта текущей реализации.

## 14. Тесты

tests/test_capport_routes.py, test_capport_service.py, test_capport_telemetry.py, test_proxy_headers.py.

## 15. Запрещённые изменения

Новый auth worker/provider, guest IP вне allowlist, независимый token cache, логирование SSID password.

## 16. Связанные TASK

Historical docs/CAPPORT.md мигрируется в этот contract.

## 17. Связанные ADR

Нужны при изменении identity strategy, proxy trust или public CAPPORT URLs.
