# CAPTIV-PROD — Полная read-only ревизия backend после миграции AP

**Отчёт:** `CAPTIVPROD-FULL-BACKEND-AUDIT-20261016`  
**Редакция:** `v1.0`  
**Дата:** 16 октября 2026 (Asia/Baku)  
**Время непосредственных наблюдений:** приблизительно 19:28–19:40 UTC (23:28–23:40 Asia/Baku); метрики ниже — срезы, полученные в разное время.  
**Сервер:** `captiv-prod`, `192.168.0.99`  
**Версия исходников запущенного Portal:** `b6152459421b48514ddc8af114bcc96e30351cf7` (Git checkout без локальных изменений).  
**Исполнение:** ChatGPT / Captiv-Prod Tech Lead, через сохранённую SSH-сессию PuTTY `Captiv-Prod`, учётная запись `chatgpt-admin`.  
**Режим:** read-only; никакого restart/reload/deploy, изменения env, SQLite, SSH, Omada, NPM, firewall или AP не выполнялись.

## 1. Краткий вердикт

**Общий статус: PARTIAL PASS / FUNCTIONAL HOLD.** Сервер и основные контуры приёма/хранения работают. Реальные HTTP-запросы приходят, четыре AP видны как online, авторизации превращаются в записи в нескольких базах, fingerprint-события поступают и сохраняются. Никаких признаков массового зависания процессов, критического переполнения дисков или устойчивого backlog Sensor не обнаружено.

Но два важнейших функциональных контура не завершены:

1. **P1 — Visit Lifecycle не получает offline-события.** `OMADA_WEBHOOK_ENABLED=false`, нормализованный webhook-журнал пуст (`0 байт`), `visit_source_events=0`; 20 из 20 визитов остаются `open`. В последнем полном снимке Current State были только 7 авторизованных клиентов, из 20 уникальных MAC открытых визитов только 7 совпадали с ними, 13 не присутствовали в текущем списке авторизованных. Это не доказывает, что каждый из 13 визитов завершился, но убедительно показывает, что источника закрытия нет и открытые визиты не соответствуют текущей картине клиентов.
2. **P1 — Fingerprint классификация/интеграция отсутствует в production.** Работают Sensor → Suricata → Evidence Receiver → Evidence SQLite. Однако `DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false`, отсутствуют ожидаемые `device_fingerprint_integration.sqlite3` и `device_fingerprint_classification.sqlite3`; в перечне активных сервисов нет отдельного классификационного worker. Admin Device UI читает *готовые классификационные результаты*, а не сырые evidence-события. Поэтому сбор Fingerprint PASS, но отображение классифицированных устройств в Admin — FUNCTIONAL HOLD. Нельзя устранять это простым слепым включением флага без проверки отдельного worker, схем/версий, миграций и безопасного запуска.
3. **P1/P2 — повторяющиеся HTTP 503 на Admin Devices.** После запуска текущего Portal найдено 8 ответов 503, все на `/admin/api/v1/sites/.../devices` / `inventory-summary` / `devices/:id` / `devices/:id/current`. Последний: 19:26:04 UTC. При этом прямые read-only вызовы `AdminDeviceReadGateway` под тем же системным пользователем `captivportal` работали: `summary=19`, `list=19`. Точная причина периодических 503 на уровне Admin Query/HTTP пока не доказана; отсутствие базы классификации *само по себе не обязано* вызывать HTTP 503, поскольку Fingerprint presentation слой обрабатывает исключения и возвращает `unavailable`.

## 2. Сервисы и ресурсы

| Компонент | Состояние | systemd NRestarts | Примечание |
|---|---|---:|---|
| `captive-portal.service` | active/running | 0 | PID 426358; старт 13:57:35 UTC |
| `fingerprint-sensor.service` | active/running | 0 | Sensor и метрики активны |
| `fingerprint-suricata.service` | active/running | 0 | Suricata активна, kernel drops на наблюдаемом снимке 0 |
| `fingerprint-evidence.service` | active/running | 0 | Batch receiver принимает и подтверждает |
| `tpeap.service` (Omada) | active/running | 0 | Контроллер Java и MongoDB присутствуют в process list; LSB NRestarts не исключает внутренние рестарты |
| `captiv-net01-watchdog.service` | active/running | — | Network/firewall supervisor |
| NPM Docker container | running | Docker RestartCount=0 | HTTPS-проверки успешны |
| `systemctl --failed` | 0 units | — | На момент осмотра |

**Ресурсы:** 15 GiB RAM; примерно 2,5 GiB used, 12 GiB available; swap 0; корневой LV 98 GiB / 13% used; `/srv/backups` 916 GiB / 2% used; inodes 3% и 1% соответственно. CPU load низкий (срез 0.11–0.27). `/proc/pressure/io` наблюдался на уровне порядка `some avg10≈0.11`, `full avg10≈0.09`, не свидетельствует о систематическом I/O-зависании в момент проверки. NTP синхронизирован. Значения меняются во времени; это не длительный нагрузочный тест.

**HTTP через локальный NPM ingress с проверкой действительности TLS (`ssl_verify_result=0`):** `/api/public/portal-counter` 200 примерно 62 мс; `/admin/login` 200 примерно 45 мс; `/capport/api` без guest-context ожидаемо 403 примерно 40 мс. Последнее — не ошибка обслуживания авторизованного клиента.

## 3. SQLite: физическое наличие, целостность, актуальность

Проверены **8 production SQLite файлов**, все с URI `mode=ro`, `PRAGMA query_only=ON`, `PRAGMA quick_check(1)=ok`:

| База | Ключевые факты на снимке | Вывод |
|---|---|---|
| `portal_counter.db` | 20 событий открытия | Запись есть |
| `visits.sqlite3` | 20 визитов, 20 авторизаций, **0** source events, все визиты `open` | Создание PASS; закрытие FAIL/HOLD |
| `visitor_registry.sqlite3` | 20 device snapshots, 20 processed events (`stored`), 20 visitor devices | Запись PASS |
| `current_state.sqlite3` | На исходном снимке 766 циклов; последние AP/client `success`, `complete=1`; 4 AP online | Актуальный опрос PASS |
| `observations.sqlite3` | Динамические AP- и client- наблюдения регулярно поступают | Запись PASS, история partial |
| `settings.sqlite3` | Активная DB, 1 generation, 2 activation events | Доступность PASS, семантика изменений отдельно не тестировалась |
| `evidence.sqlite3` | 12 012 evidence на срезе 19:29 UTC, 823 source-health; данные продолжали прибывать | Ingest PASS |
| `spool.sqlite3` | Очередь на срезе 0; кратковременно 2 строки и затем снова 0 | Стабильного backlog не обнаружено |

**Ограничение:** `quick_check` — не полный тест всех инвариантов приложения и не испытание восстановления из резервной копии. Случайные/постоянные отказы записи в будущем не исключены.

## 4. Проверка авторизации: согласованность записей

На последнем снимке по фактическим таблицам:

- `portal_open_events`: 20 различных `session_id`;
- `visit_authorizations`: 20 различных пар `(auth_session_id, auth_run_number)`;
- `device_snapshots`: 20 различных таких же пар;
- `visits`: 20 различных пар `(start_auth_session_id, start_auth_run_number)`.

**Сквозная сверка идентификаторов:** `auth_without_snapshot=0`, `snapshot_without_auth=0`, `visit_without_auth=0`, `auth_without_visit=0`. Все 20 session-id Portal Counter встретились среди авторизаций. Это существенно сильнее простого совпадения счётчиков.

Visitor Registry read checkpoint `source_offset=50 319` при фактическом размере входного `visitor_snapshots.log=50 319 байт`, last successful scan свежий. Средняя задержка snapshot около **27.7 мс**, максимум **48 мс**; средняя задержка задания примерно **0.5 мс**, максимум **1 мс**. В текущем выборочном окне backlog Registry не обнаружен.

**Не проверялось:** полноценное контролируемое guest E2E на телефоне с обновлением/разрывом сессии, чтобы отдельно подтвердить Omada authorize/unauthorize, фактическое предоставление доступа через сеть и CAPPORT status каждого клиента.

## 5. Visit Lifecycle: реальный функциональный дефект

- `VISIT_LIFECYCLE_ENABLED=true`, то есть создание визитов включено.
- `OMADA_WEBHOOK_ENABLED=false`.
- Источник для reader: `/opt/CaptivePortal/logs/omada_webhook_normalized.log`; размер `0`, `source_offset=0`, `last_observed_size=0`.
- `visit_source_events=0`.
- `visits`: **20 open / 0 closed**.
- В последнем полном Current State client-cycle 7 `authorized` и 1 `pending`, при этом 13 MAC из открытых визитов отсутствовали среди текущих 7 авторизованных MAC.

**Решение:** до любых изменений Architect/SysAdmin должен определить разрешённый источник Omada offline/unauthed и точный контракт нормализованного журнала, затем на одном Owner-controlled клиенте проверить последовательность `auth → visit open → offline → source event → visit closed`, повтор доставки/idempotence, отсутствие двойного закрытия и rollback. Только после Owner GO менять production.

## 6. Fingerprint: capture/ingest против classification

### Подтверждённые работающие этапы

- `DEVICE_FINGERPRINT_SENSOR_ENABLED=true`, интерфейс `enp3s0`, VLAN60 guest CIDR `10.50.0.0/19`.
- Suricata active; наблюдались `capture_kernel_drops=0`, `eve_json_invalid=0`, `eve_datagram_truncated=0`, `stale_spool_event_dropped=0`; `suricata_process_active=true` и `runtime_state=ready` в последнем metrics event.
- Evidence Receiver активен на `127.0.0.1:9443`, хранит в `/var/lib/captivprod-evidence/evidence.sqlite3`.
- На срезе 19:29: из 12 012 evidence: TCP SYN 6 545; TLS client 3 888; QUIC client 1 360; DHCP 200; portal headers 19; качество `valid` 12 004, `partial` 8.
- Source-health содержит актуальные `available` по источникам; старые `unavailable` во время старта Suricata/интерфейса есть в истории, но не являются текущим состоянием.
- В течение 10 последних минут наблюдаемого окна Receiver сообщил: 1 265 событий получено, 1 265 вставлено, `duplicate_noop=0`, HTTP 200; source-health 18 получено/18 вставлено. Spool временно 2 строки и снова 0.

### Не работающий/не включённый этап

- `DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false`;
- `device_fingerprint_integration.sqlite3` и `device_fingerprint_classification.sqlite3` отсутствуют в ожидаемом production data-каталоге;
- Нет запущенного отдельного classification/integration worker в обнаруженных systemd-службах;
- Admin Device list/detail вызывает `DeviceFingerprintClassificationReadService`/`DeviceFingerprintPresentationService` для *результатов классификации*, а не сырых evidence. При отсутствии production result отображение закономерно `no_result`/`unavailable`.

**Вывод:** Sensor и Evidence записывают, но функция определения класса/платформы устройства ещё не завершена в production. `DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false` в **Portal** не следует считать отказом отдельного Receiver: у Receiver собственное `...EVIDENCE_ENABLED=true`.

**Решение:** отдельный архитектурный/QA gate на классификатор: admission установленного кода/артефактов/схем, режимов backfill, отдельного worker, ограничений на запись и пользователей/память/диски; не включать вслепую флаг на живом сервере.

## 7. Omada / Current State / Observations

- Последний current AP cycle завершился `success/complete`, **4 items_seen / 4 stored / error_count=0**, все четыре AP имеют `status_classification=online`.
- Последний current client cycle `success/complete`, 13 source rows, 8 stored; 7 `authorized`, 1 `pending`.
- AP dynamic observation: исторически **672 partial** из-за отсутствия wired-uplink и LAN telemetry при наличии overview/radio; затем **95 последовательных success** без ошибок, сохраняя по 4 AP. Последний success на 19:34 UTC.
- Два исторических `ap_config` цикла `failed`, `ap_config_snapshots=0`. Нет основания утверждать, что будущие чтения AP config будут успешны; проверить отдельным непроизводственным acceptance.
- Client observation cycles в выборке все `success`; данные свежие, но многие строки исходного client inventory закономерно отфильтрованы согласно конфигурации SSID/guest scope.

**Вывод:** сейчас Omada AP/client polling работает. Временная проблема AP dynamic наблюдалась ранее в день миграции и восстановилась примерно с 18:46 UTC. Информация о её первопричине не подтверждена.

## 8. Admin UI, 503 и работа HTTP

После текущего startup обнаружено **8 ответов 503**, все относятся к разделу `devices`:

- `devices` и `inventory-summary`: несколько обращений;
- `devices/:id` и `devices/:id/current`: единичные обращения;
- временные точки: 15:38, 17:32, 17:50, 19:11 и 19:26 UTC.

Отдельно зарегистрированы 401 (отсутствует/истекла авторизация), 403 CAPPORT без guest-context и 400 `/` без Omada parameters; их нельзя автоматически считать backend-падением.

Проверка `AdminDeviceReadGateway` в изолированном read-only Python-вызове **под production service-user `captivportal`**: `device_inventory_summary=19`, `list_devices=19` — PASS. Базы Registry/Visit корректно имеют `PRAGMA user_version` 1 и 2. Поэтому постоянное разрушение SQLite/schema или отсутствие прав на чтение этих двух баз **не подтверждается**. Возможны временные задержки/deadline, иной путь композиции или другие условия HTTP; причина остаётся **UNRESOLVED**. В частности, отсутствие классификатора не является автоматически причиной HTTP 503 — её presentation код подавляет собственные исключения.

**Решение:** воспроизвести через существующий authenticated Admin-сценарий с bounded instrumentation без MAC/IP/PII, зарегистрировать безопасный failure category и определить точный ответственный этап.

## 9. Резервное копирование и внешние зависимости

- Основной `captiv-backup.service`: `BACKUP_STATUS=PASS`, 15 snapshots, последнее завершение `2026-10-16 03:30:28 UTC`, retention 30.
- `captiv-npm-backup-online.service`: `NPM_ONLINE_BACKUP_STATUS=PASS`, `SQLITE_INTEGRITY=ok`, LE artifacts PASS, snapshot `20261016T031012Z`.
- Omada native encrypted mirror: `MIRROR_STATUS=PASS`, 5 `.cfg` и 5 `.zip`, текущая часовая задача выполнена успешно. Однако последний **исходный native CFG** на момент диагностики имел возраст примерно **20 часов** — свежесть следующего backup Omada следует контролировать отдельно.
- NPM container running, restart count 0, TLS verification PASSED.
- NTP synchronized, root and backup volume далеко от исчерпания.

**Ограничение:** проведение restore/recovery test не разрешалось и не выполнялось. PASS backup script означает успешный job, но не доказанный успешный restore.

## 10. Обнаруженные отключённые флаги и трактовка

| Флаг | Состояние | Трактовка |
|---|---|---|
| `OMADA_WEBHOOK_ENABLED` | false | Связан с отсутствием offline source для Visit — приоритет P1 |
| `DEVICE_FINGERPRINT_INTEGRATION_ENABLED` | false | Нет этапа классификации/интеграции — P1 |
| `DEVICE_FINGERPRINT_PORTAL_ENABLED` | true | Portal headers producer активен |
| `DEVICE_FINGERPRINT_SENSOR_ENABLED` | true | Sensor активен |
| Receiver `DEVICE_FINGERPRINT_EVIDENCE_ENABLED` | true | Receiver активен |
| Portal `DEVICE_FINGERPRINT_EVIDENCE_ENABLED` | false | Не считать падением отдельного Receiver |
| `PENDING_SESSION_CLEANER_ENABLED` | false | Отдельная явно выключенная функция; не менять без анализа рисков |
| `PUBLIC_TRAFFIC_COUNTER_ENABLED` | false | Legacy/public counter worker не работает по настройке; не свидетельствует об отказе всех Admin traffic features |
| `CURRENT_STATE_ENABLED`, `OBSERVATION_FOUNDATION_ENABLED`, `VISIT_LIFECYCLE_ENABLED`, `VISITOR_REGISTRY_ENABLED` | true | Соответствующие background-системы формально включены; фактические данные проверены отдельно |

## 11. Приоритезированные дальнейшие действия

| ID | Приоритет | Задача / Acceptance |
|---|---|---|
| AUD-P1-01 | P1 | Исправить отсутствие offline lifecycle из Omada; тест на своём клиенте `auth → offline → closed`, replay/idempotence/rollback |
| AUD-P1-02 | P1 | Спроектировать и безопасно запустить fingerprint classification/integration; проверить создание production results, latency и реальный Admin UI |
| AUD-P1-03 | P1/P2 | Определить причину `503` Admin Devices с reproduction и безопасной telemetry, тест без реальных MAC в артефактах |
| AUD-P2-04 | P2 | Проверить исторические AP dynamic `partial` и AP config `failed`, сохранить ныне исправный polling |
| AUD-P2-05 | P2 | Проверить свежесть native Omada backups после миграции, отдельно спланировать restore-test |
| AUD-P2-06 | P2 | Добавить постоянные метрики `visits_open_without_offline_source`, latest classifier result age, sensor spool age, AP cycle success rate, Admin devices 503 count |
| AUD-SEC-07 | P2 | После завершения административных работ переоценить риск `chatgpt-admin` с `(ALL:ALL) NOPASSWD:ALL` и контролировать приватный ключ; без самостоятельной смены полномочий в этом аудите |

**Никакие remediation-операции не выполнялись.** Изменения в работающую сеть/Omada/Portal/SQLite/iptables/NPM требуют отдельно разрешённого контракта и Owner GO. Для реального network E2E требуется контролируемый тест на устройстве владельца; пользовательские устройства посетителей не трогались.

## 12. Что не доказано этим аудитом

- Полная проверка packet-to-DB семантики *каждого* пакета и физического сетевого mirror loss; `kernel_drops=0` относится к конкретному счётчику/интервалу, а не абсолютной гарантии отсутствия всех потерь.
- Настоящий guest E2E на мобильном устройстве, перезапуск AP, разрыв WAN, повторный webhook, физическое отключение AP.
- Полный `PRAGMA integrity_check` всех баз, восстановление backups из snapshots, fault-injection.
- Стопроцентная точность UI и производных аналитик; только подтверждённый source write и выбранные HTTP GET.
- Точная первопричина периодического Admin Devices 503 и исторических AP telemetry partial.

### Методы и границы безопасности

Применены `systemctl show/is-active/--failed`, `journalctl`, `ps`, `df`, `free`, `/proc/pressure`, `timedatectl`, `docker ps/inspect`, `curl` (только GET), Python `sqlite3` с `mode=ro`, `query_only=ON`, `quick_check`, aggregate SQL и контрольным join сравнения auth/session IDs **без вывода персональных идентификаторов**, а также просмотр source code зафиксированного checkout. Настройки `.env` читались только по whitelist несекретных ключей; сами токены, пароли, приватные ключи и значения MAC не выводились. Изменений конфигурации, исходников, PR, systemd, firewall, БД и рабочих сессий не производилось.

**Tech Lead заключение:** инфраструктура и приём данных — **PASS**; Visit Lifecycle offline/close — **P1 FAIL**; Fingerprint production classification — **P1 NOT ENABLED**; Admin device UI — **DEGRADED / P1-P2 INVESTIGATION**; полная функциональная приёмка после миграции всех AP — **HOLD**.
