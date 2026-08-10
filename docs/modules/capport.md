# CAPPORT

Status: active
Updated: 2026-08-10
Runtime baseline: main `ab776af3fc58dc090e17ecd20534abddc1f33ad3`

## 1. Назначение

RFC 8908/8910 captive portal API и login bridge в общий authorization flow.

## 2. Статус

`app/capport` реализован; `CAPPORT_ENABLED=true` в repository default. Изменения bounded discovery и frontend PR #31/#35–#37 находятся в deployed `main@ab776af`. Android captive-window live acceptance post-`AUTHORIZED` revalidation пока не подтверждён и остаётся отдельным gate.

## 3. Граница ответственности

Определить client по разрешённому source IP, получить state из Omada и передать login в PortalEntryHandler. Не авторизовать самостоятельно.

## 4. Входные данные

Guest source IP, configured site, CAPPORT API/login request.

## 5. Выходные данные

application/captive+json state, HTML portal, discovery JSON envelope,
`AUTH_SESSION` JSON envelope или controlled error.

Если `/capport/login` временно не может определить client, endpoint
возвращает HTTP 200 с режимом `CAPPORT_DISCOVERY`, не создавая AuthSession и
не запуская AuthWorker. Открытая страница повторяет lookup последовательными
`fetch()`-запросами без reload и без параллельных запросов в пределах текущего
server-bounded deadline до 60 секунд. После истечения автоматический polling
останавливается, а ручной retry через `restart_url` начинает новый bounded
cycle на той же странице.

JSON negotiation для `/capport/login` строгий: JSON включается только явным
media range `application/json` с `q>0`. Wildcard, отсутствующий `Accept`,
обычный browser `Accept` и `application/json;q=0` сохраняют HTML-ответ.

Discovery JSON всегда содержит `mode`, `state/status`, `terminal`, `retryable`,
`auto_retry`, `remaining_seconds`, `retry_interval_ms`, `retry_url` и
`restart_url`. До фактического создания AuthSession поле `session_id` не
возвращается. Not-found возвращает 200; lookup failure — 503 с
`error=lookup_failed`; invalid context и source IP вне allowlist — терминальные
400/403. Все login-ответы запрещают кэширование.

После обнаружения client тот же запрос входит в штатный
`PortalClientContext → AuthSessionManager → AuthWorker` flow и возвращает
`AUTH_SESSION` envelope с authoritative `initial_state`. Валидный controlled
500 после worker-start failure также сохраняет `session_id` и фактический
snapshot, поэтому frontend окончательно прекращает discovery и использует
существующий retry/final UI.

Отображаемый progress не уменьшается при переходе discovery → auth и при более
низком результате последующего poll. Начало явного нового retry является
отдельным cycle и может сбросить progress по retry contract.

После подтверждённого `AUTHORIZED` frontend ровно один раз запускает completion
flow: останавливает polling и пытается выполнить `window.close()`. Если окно
осталось открыто, при наличии `redirect_url` сохраняется существующий redirect
contract; без redirect допускается максимум один reload текущей страницы для
revalidation. Marker `captivePortalRevalidated:<session_id>` в
`sessionStorage` блокирует reload-loop. Если marker недоступен, reload не
выполняется.

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

## 14. Тесты

`tests/test_capport_routes.py`, `test_capport_discovery_frontend.py`,
`test_capport_service.py`, `test_capport_telemetry.py`, `test_proxy_headers.py`
и `test_auth_retry_frontend.py`.

Tests подтверждают static/Node contract, но не поведение конкретного Android
captive WebView. Live acceptance требует не менее пяти реальных подключений без
ручного refresh, с максимум одним same-page reload и без повторной авторизации
или reload-loop.

## 15. Запрещённые изменения

Новый auth worker/provider, guest IP вне allowlist, независимый token cache, логирование SSID password.

## 16. Связанные TASK

Historical `docs/CAPPORT.md` мигрируется в этот contract. Related changes:
bounded discovery PR #31, same-page discovery PR #35, monotonic progress PR #36
и guarded revalidation PR #37. Это history, а не отдельные current contracts.

## 17. Связанные ADR

Нужны при изменении identity strategy, proxy trust или public CAPPORT URLs.
