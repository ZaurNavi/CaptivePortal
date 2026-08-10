# Pending Client Session Cleaner

Status: implemented; repository default disabled; production active (owner-confirmed)
Updated: 2026-08-10
Runtime baseline: main `ab776af3fc58dc090e17ecd20534abddc1f33ad3`

## 1. Назначение

`PendingClientSessionCleaner` безопасно завершает зависшие неавторизованные Wi-Fi-сессии Omada. Он получает полный active-client inventory, выбирает только устойчиво подтверждённых кандидатов и выполняет guarded `reconnect` после fresh preflight и двух local-protection checks.

## 2. Статус

Final module merged через PR #27; временные probe-костыли удалены PR #28. Код находится в `app/pending_sessions/`, Omada adapter — в `app/controllers/omada_pending_sessions.py`, lifecycle подключён в `run.py`.

Repository default: `PENDING_SESSION_CLEANER_ENABLED=false`. При `false` worker, journal и Omada calls не создаются. В production включение и живая работа подтверждены владельцем проекта 2026-08-04; точное состояние process environment не выводится из Git. Отдельное post-restart evidence worker/events после deployment 2026-08-10 пока не предоставлено.

## 3. Граница ответственности

Cleaner отвечает за:

- paginated inventory активных клиентов;
- строгую классификацию `active=true`, `wireless=true`, `authStatus=1`;
- SSID allowlist, uptime threshold и duplicate-MAC exclusion;
- две read-only проверки локального Auth state;
- fresh client-card preflight;
- action limits, audit-before-action и один guarded `reconnect`;
- bounded verification, JSONL data events и operational telemetry.

Cleaner не читает и не изменяет `visitor_registry.sqlite3`, не создаёт visits/device IDs и не настраивает Grafana, Alloy, Loki или systemd.

## 4. Входные данные

- `OmadaProvider.list_active_clients()`;
- `OmadaProvider.get_pending_client_state()`;
- `CAPPORT_SITE_ID` и `PENDING_SESSION_CLEANER_SSIDS`;
- immutable snapshot из `AuthSessionManager.pending_session_protection_snapshot()`;
- process settings из `app/config.py` → `app/settings.py:get_settings()`.

## 5. Выходные данные

- `pending_session.scan.completed`;
- `pending_session.action.planned`;
- `pending_session.action.completed`;
- operational events с component `pending_session_cleaner`;
- `PendingScanSummary`, возвращаемый `run_once()`.

## 6. Основные модели

Фактические модели:

- `PendingSessionCleanerConfig`;
- `PendingClientObservation`;
- `PendingClientCandidate`;
- `ClassificationResult`;
- `PaginationResult`;
- `ProtectionDecision`;
- `PendingScanSummary`;
- `ActionGuardDecision`.

Controller dictionaries копируются defensive-copy; parsed observations и decisions передаются immutable dataclasses.

## 7. Зависимости

Один `OmadaProvider` создаётся в `run.py` и совместно используется AuthWorker, snapshot collector и Cleaner. Provider теперь имеет общий thread-safe token cache на `Condition(RLock)`: одновременно token обновляет один thread, успешный refresh атомарно публикует token/expiry, а ошибка не публикует partial state.

Pending-session методы подключаются к тому же классу через `install_pending_session_methods(OmadaProvider)`. Второй OAuth client, provider или token manager отсутствует и запрещён без отдельного TASK/ADR.

При точном Omada `-44112` reconnect adapter выполняет compare-and-invalidate только для token, использованного неуспешным запросом. Cleaner recovery не выполняет повторную безусловную invalidation: thread со старым ответом не должен очистить свежий token, уже опубликованный другим thread. После этого выполняются fresh GET и две повторные local-protection checks до единственного разрешённого recovery POST.

## 8. Fail-open

При invalid config factory возвращает `UnavailablePendingSessionCleaner`; при выключенном flag — `DisabledPendingSessionCleaner`. Provider, protection, journal или internal error не должны останавливать portal authorization. Любая неопределённость запрещает POST либо оставляет результат unconfirmed.

Local protection работает fail-closed относительно действия: exception адаптера трактуется как `protected=true`.

## 9. Конфигурация

Единственный feature flag: `PENDING_SESSION_CLEANER_ENABLED`, default `false`. Dry-run, observation mode и отдельный mutation flag отсутствуют.

| Группа | Defaults |
|---|---|
| Scheduling | initial delay 10 s; fixed delay 60 s; scan budget 50 s |
| Eligibility | SSID `Zefer_Parki`; uptime 120 s; portal grace 45 s; regression tolerance 5 s |
| HTTP | request timeout 5 s; GET retry delays 1,3 s; verification delays 1,4 s |
| Inventory | page size 500; max pages 20; max clients 10000 |
| Actions | max 1 per scan; cooldown 180 s; max 3 per MAC/hour |
| Journal | `/opt/CaptivePortal/logs/pending_session_cleaner.log`; 50 MiB; 20 backups |
| Shutdown | 20 s |

При enabled mode все значения валидируются строго; invalid config не создаёт worker и не выполняет Omada requests.

## 10. Data events

`pending_session.action.planned` записывается и flush-ится до POST. Если planned event записать нельзя, reconnect запрещён.

`pending_session.action.completed` фиксирует как выполненное действие, так и deterministic skip для первоначального кандидата. Он содержит full MAC, before/after identity, число POST/verification attempts, безопасные controller metadata и result; token/header/cookie/secret/raw response отсутствуют.

`pending_session.scan.completed` содержит pagination, classification, protection, action и verification counters. Schema version текущих событий — `1`.

## 11. Operational telemetry

Фактические lifecycle/state events включают start, stop, state change, overlap suppression, scan completed/partial, unavailable, internal error, audit/writer error и recovery. Operational telemetry отделена от data journal и отправляется через `AuthorizationTelemetry` adapter.

## 12. Persistence

`JournalWriter` пишет compact UTF-8 JSONL с `allow_nan=false`, flush после каждой записи, rotation и mode `0640` на POSIX. Default path: `/opt/CaptivePortal/logs/pending_session_cleaner.log`.

ActionGuard хранит bounded in-memory cooldown/hourly-attempt state; после process restart эти ограничения начинают новый in-memory lifecycle. SQLite schema не используется и не меняется.

## 13. Lifecycle

`create_pending_session_cleaner()` вызывается в `run.py` после Flask composition и получает общий provider/auth manager/telemetry. При enabled mode создаётся один daemon thread `pending_session_cleaner_worker` на process.

Scheduling fixed-delay: initial wait → `run_once()` → interval wait. Non-blocking scan lock запрещает overlap. Shutdown сначала переводит Cleaner в `stopping`, запрещает новые scans/POST, устанавливает event и ждёт worker не дольше configured timeout; затем останавливаются остальные components по порядку `run.py`.

Multiple application processes с одновременно активным Cleaner не поддерживаются без отдельного leader-election/inter-process-lock ADR.

## 14. Тесты

`tests/pending_sessions/` содержит 11 файлов и 53 test functions для provider contracts, reconnect, token-cache concurrency, config, pagination, classification, double protection, pipeline, action guard, journal/telemetry и factory modes. Focused concurrency regression моделирует Cleaner recovery после token expiry и подтверждает отсутствие invalidation свежего current token.

Targeted gate:

    python -m pytest -q -rs tests/pending_sessions

Затем обязателен full gate из `docs/testing.md`. Живая production activation не заменяет regression suite.

## 15. Запрещённые изменения

- `disconnect`, client `DELETE`, `unauth`, `block/unblock` или device `forget` вместо `reconnect`;
- POST при incomplete inventory, active local Auth, failed protection/preflight/audit, shutdown или exhausted guard;
- blind retry POST; особый второй POST допустим только для точного Omada `-44112` после cache invalidation, fresh preflight и повторных protection checks;
- отдельный provider/token manager/cache;
- чтение Visitor Registry DB;
- изменение JSONL schema, process topology или action policy без TASK и tests.

## 16. Связанные TASK

`Pending Client Session Cleaner v1.0` — исходный change-intent contract. После merge current-state truth определяется кодом, тестами и этим документом; временные probe-материалы source of truth не являются.

История исправления token recovery: PR #30, commit `a9d2f6a`. Это related change, а не текущий active defect.

## 17. Связанные ADR

Отдельный ADR в repository для v1 не зафиксирован. Новый token lifecycle, persistence, action policy, mutation endpoint или multi-process topology требуют отдельного TASK, PLAN и устойчивого ADR. Текущий shared token cache является частью merged Cleaner implementation и покрыт concurrency tests.
