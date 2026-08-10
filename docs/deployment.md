# Deployment

Status: current contract; exact production unit remains host-verified
Updated: 2026-08-10

## Подтверждённая основа

- Repository docs используют /opt/CaptivePortal.
- Repository docs называют service captive-portal.service.
- Сам unit file отсутствует в repository, поэтому точный ExecStart и user/group требуют проверки на target host.
- Код не загружает `.env` автоматически. Environment должен передаваться process manager, например systemd EnvironmentFile или approved drop-in.

## Обязательная конфигурация Omada OpenAPI

До deployment и restart процесса необходимо подготовить четыре обязательные
переменные environment: `OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID` и
`OMADA_CLIENT_SECRET`. `OMADA_URL` содержит только базовый HTTP(S)-адрес
контроллера. Без полного и корректного набора приложение завершит создание
`OmadaProvider` с `ConfigurationError` до сетевого запроса.

Код с этим контрактом запрещено перезапускать на production до проверки, что
все четыре имени уже передаются процессу. Значения и их фрагменты в вывод
проверки, deploy-отчёт и журналы не включаются.

Configuration pipeline: process environment → `app/config.py` →
`app/settings.py` → `get_settings()`. Current Git tree не содержит production
Omada literals.

## Repository defaults и production state

- `.env.example` документирует имена и безопасные defaults, но приложение его
  автоматически не читает.
- Repository defaults для Cleaner, Snapshot Collector и Visitor Registry —
  `false`.
- Production systemd EnvironmentFile/drop-ins принадлежат target host и могут
  включать эти features независимо от repository defaults.
- Проверка production configuration подтверждает только наличие нужных имён и
  enabled/disabled state без вывода значений, полного environment dump или
  secret fragments.

## Обязательный deploy TASK

Deploy требует target environment, owner, backup, feature flag, разрешённых команд, health checks и rollback. Coding TASK без deploy mode production не меняет.

## Стадия 1: deployment с feature disabled

1. Зафиксировать approved commit и clean working tree.
2. Создать backup изменяемых config/data согласно модулю.
3. Доставить код, сохранив новый feature disabled.
4. Сравнить requirements с развёрнутой версией. Устанавливать dependencies в существующий venv только если requirements изменились.
5. Выполнить Linux gate и module-specific checks.
6. Проверить EnvironmentFile без вывода secrets и убедиться, что feature flag выключен.
7. Restart captive-portal.service.
8. Проверить service status, portal/auth endpoint health, startup logs, process topology и отсутствие запуска disabled feature.

Стадия 1 завершается отдельным health-check verdict. Она не означает разрешение activation.

## Стадия 2: отдельная activation

1. Получить разрешение на activation после успешной стадии 1.
2. Изменить feature flag в environment, не выводя secrets.
3. Обязательно restart captive-portal.service: изменение environment не применяется к уже запущенному process.
4. Повторно проверить service status, portal/auth endpoint health, startup logs и process topology.
5. Проверить module start/events, storage permissions, bounded operational logs и fail-open основного портала.
6. Зафиксировать activation verdict и готовность rollback.

## Health checks

- service active, один application process;
- portal route и auth session endpoints отвечают;
- нет startup exception;
- shared provider не дублирован;
- background component start/stop events корректны;
- storage/journal writable с ожидаемыми permissions.

## Pending Session Cleaner activation

Repository default — `PENDING_SESSION_CLEANER_ENABLED=false`. Disabled deployment обязан подтвердить отсутствие worker, Omada polling и Cleaner journal creation.

После отдельного разрешения activation:

1. установить `PENDING_SESSION_CLEANER_ENABLED=true` в process environment;
2. сохранить `PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN=1` для v1;
3. выполнить обязательный restart;
4. проверить startup/state telemetry и появление `pending_session.scan.completed`;
5. на одном живом кандидате проверить две local-protection проверки, fresh preflight, `action.planned` до POST, bounded verification и `action.completed`;
6. убедиться, что основной portal остаётся доступен при Cleaner error.

Owner сообщил об успешной production activation 2026-08-04. Это эксплуатационное подтверждение не заменяет повторяемый Linux regression gate и не раскрывает EnvironmentFile.

## Последнее подтверждённое развёртывание

`main@ab776af` доставлен на `/opt/CaptivePortal` 2026-08-10 через fast-forward
и restart `captive-portal.service`; общий systemd health подтверждён как PASS.
Это historical deployment evidence, а не разрешение на новый deploy.

В представленном evidence не было отдельной post-restart проверки фактических
lifecycle events Cleaner, Snapshot Collector и Visitor Registry. Она остаётся
owner/tech-lead action и не восстанавливается из repository defaults.

## Rollback

Сначала выключить feature в environment, обязательно restart service и повторить health checks. Для Cleaner journal сохраняется; удалять audit при rollback нельзя. Если недостаточно — вернуть approved code version и совместимый config/data backup. Migration rollback определяется отдельным PLAN.

## Shutdown

Соблюдать порядок run.py и bounded timeout. SIGTERM не должен запускать новые mutation.

## Запрет

Ручное production-изменение, которое не переносится в Git и документацию, запрещено. Alloy, Loki, Grafana, reverse proxy и systemd меняются отдельными tasks.
