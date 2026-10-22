# TASK-CAPTIVPROD-OMADA-INSTALL-01 v1
## Установка второго Omada Software Controller на captiv-prod и восстановление конфигурации — БЕЗ миграции AP

**Роль исполнителя:** Captiv-Prod SysAdmin / Production Deployment Lead  
**Заказчик / право разрешения изменений:** Owner  
**Целевой сервер:** `captiv-prod`, ожидаемый management IP `192.168.0.99` (перепроверить)  
**Исходный контроллер:** Windows Server 2016, ожидаемый `192.168.0.222:8043`, ранее отмеченная версия 5.14.31 (перепроверить полный build)  
**Исходный Captive Portal:** Ubuntu VM `192.168.0.202` — без изменений  
**Стадия:** подготовительная; без cutover и без adoption AP  
**Приоритет:** безопасность работающего Guest Wi-Fi.

> **ЖЁСТКОЕ ОГРАНИЧЕНИЕ:** эта задача завершается на состоянии **новый контроллер установлен, конфигурация восстановлена, изолированно проверена, AP на старом контроллере**. Никакие команды `Migrate Devices`, `Adopt`, `Forget`, изменение inform URL, отключение старого контроллера или перевод клиентов на новый не разрешены. Сохранённая backup-конфигурация не является разрешением управлять оборудованием.

---

## 0. Для чего делаем это

Подготовить на `captiv-prod` отдельный Linux Omada Controller, максимально воспроизводящий конфигурацию действующего Omada, чтобы **позже**, по отдельному TASK и Owner GO, подключить к нему заново установленный CaptivePortal и перенести тестовую AP. Не переносить историческую базу CaptivePortal. Не изменять текущую схему Guest Wi-Fi.

Сейчас production остается по старому пути: работающие AP → Omada на Windows `.222` → текущий Portal `.202`. Новый Omada на `.99` пока не управляет AP.

### Два разных понятия

- **Restore backup**: импорт конфигурации в новый контроллер, выполняется в текущем TASK после safety gates.
- **Migration/adoption devices**: передача управления живыми точками, **строго вне scope**.

Не смешивать действия из мастера *Migration*. Если UI сразу предлагает переход к стадии переноса устройств, **остановиться**, не нажимать `Confirm` / `Migrate Devices` / `Forget Devices` без независимого анализа того, что конкретно делает кнопка в данной версии.

---

## 1. СТОП-ПРАВИЛА И НЕИЗМЕНЯЕМЫЕ ГРАНИЦЫ

Ни при каких обстоятельствах в рамках TASK не менять:

- Cisco NAT/ACL/DHCP/VLAN, DNS, Guest SSID, firmware/config/AP controller inform;
- рабочий Omada `.222`, кроме **штатного, безопасного экспорта** backup и read-only инвентаризации;
- текущую VM CaptivePortal `.202`, Portal credentials, webhook targets, site mappings;
- NPM proxy-hosts и listener 80/81/443, Hestia, публичные сертификаты;
- конфигурацию уже подключённых AP и режим внешнего Hotspot;
- публичные маршруты на новый Controller, облачную привязку, если она может затронуть текущий Controller.

**Не использовать «latest» вслепую.** Не делать массовый upgrade старого Controller ради импорта. Не устанавливать неподтверждённую комбинацию Java/MongoDB. Не менять firewall широко «заодно». Не допускать автоматического обнаружения и adoption: защита должна подтверждаться технически — адекватной сегментацией/ограничением management/device-communication paths или иным явно проверенным средством, а не только отсутствием ручного нажатия Adopt.

Любое непредвиденное изменение статуса AP/SSID/hotspot или сбой старого контроллера → **STOP, фиксировать факт, вернуть исходное состояние**, уведомить Owner.

---

## PART A — ОБСЛЕДОВАНИЕ / PREFLIGHT (NO MUTATIONS)

### A1. Исходный Windows Omada — read-only inventory

Получить и записать (без паролей, OAuth secrets, private keys):

1. Полную версию и build Omada Software Controller; ОС; метод установки.
2. Controller ID / `omadac_id` — только безопасные identifiers, не секреты.
3. Имя, число и идентификаторы Sites; особое внимание Site `Home` и SSID `Zefer_Parki`.
4. Имена SSID, WLAN groups, Hotspot/External Portal settings, guest policy и связанные Site settings; сделать screenshots/export доступных nonsecret настроек.
5. Количество действующих AP по моделям, MAC и статусам (MAC в evidence — по approved privacy policy, допустимо маскировать).
6. Текущий OpenAPI client/service account: **факт наличия** и scope/permissions; не выводить credentials.
7. Конфигурацию webhook: endpoint, TLS, Site mapping, source policy — без секрета.
8. Текущие адреса/порты UI, discovery, device management, portal, HTTPS и все custom overrides.
9. Куда уходят AP inform/management connections, reachable endpoints, DNS и controller hostname (если установлен).
10. Состояние штатного резервного копирования и размер/тип backup.

**A1 PASS:** исходный production baseline известен, версию backup можно проверить, никаких live changes нет.

### A2. Target `captiv-prod` — read-only inventory

Проверить и приложить evidence:

- hostname, OS/distro/version, архитектуру CPU, RAM/swap, свободное место и filesystem, нагрузку;
- фактические management IP/NIC, default route, DNS, доступность `.222` и предполагаемых Omada clients;
- процессы/сервисы, слушающие TCP/UDP, особенно **80/81/443**, **8043**, **8088**, **8843** и **29810–29817**, а также все target ports по точной Omada версии;
- существующий Docker/NPM deployment и публикацию портов; NPM остаётся действующим public TLS edge;
- установленную Java, MongoDB, `jsvc`, их версии и режимы запуска (ничего не менять);
- настройки локального firewall, Docker NAT и правила доступа между VLAN;
- систему резервного копирования `captiv-prod`, последний успешный backup/restore evidence.

**Порты не назначать по памяти.** Для точного release собрать таблицу `port/protocol/purpose/listener/bind/access-control/conflict`. Omada controller UI, portal, device management и discovery могут иметь собственные разные listeners.

**A2 PASS:** конфликты и ресурсы известны, нет неизвестных listeners или неожиданных WAN exposure paths.

### A3. Согласование exact target version/packaging

1. Сверить official Linux release Omada и матрицу backup compatibility. Для существующего 5.14.31 **не считать произвольный 5.15/6.x совместимым**.
2. TP-Link документирует для веток начиная с **5.13.11.41** ограничение на импорт по **Major.Minor.Patch**; проверить точную совместимость **конкретных** source backup и target build до установки.
3. Выбрать только официальный Linux installation artifact и его checksum/release/build; определить нужные Java/MongoDB/JSVC по **данной** версии и данной ОС.
4. Выбрать модель deployment: предпочтительно **vendor-supported native Linux installation** (без самостоятельной контейнеризации); если ОС/dependencies не позволяют поддерживаемую комбинацию — **HOLD** и запрос на альтернативный вариант (совместимая ОС / контейнер с явно согласованной поддержкой).
5. Явно согласовать footprint на target host, backup storage, process owner, log/retention и host paths.

Ссылки на vendor manuals:

- Linux install FAQ: https://www.tp-link.com/uk/support/faq/3272/
- Version-constrained migration guidance: https://www.tp-link.com/baltic/support/faq/3589/
- Legacy v5 controller guide: https://static.tp-link.com/upload/software/2024/202412/20241218/1910013634_Omada%20SDN%20Controller_User%20Guide_REV5.14.pdf

**A3 PASS:** точная версия и зависимости подтверждены, бинарный пакет получен из официального источника, rollback path известен.

### A4. Isolation design & safety gate — обязательно ДО restore

Составить и проверить техническую модель, исключающую самостоятельное присвоение работающих AP новым контроллером. Новый Controller может содержать сведения об AP из backup; эти сведения не дают права connect/adopt. В особенности:

- новый controller не должен принимать live AP inform/adoption от production без отдельного разрешения;
- service discovery/broadcast и network reachability не должны приводить к неожиданному controller takeover;
- API/admin доступ только management sources; **не публиковать management UI непосредственно в Internet или через NPM**;
- требуемые для будущего теста controller device-management paths документировать, но **не открывать заранее** без gate;
- сохранность `192.168.0.222` как единственного управляющего production owner подтверждать после каждого этапа.

Предъявить `ISOLATION_PLAN=PASS` до первого запуска восстановленного Controller. Если безопасная изоляция невозможна на текущей сетевой топологии, **не выполнять restore**; запросить отдельное архитектурное решение.

### A5. Backup исходного Controller

После A1–A4 получить штатный export/backup с документированным scope и опциями. Сделать две защищённые копии + контрольную сумму, запись времени и source version; проверить файл на читаемость/структурную валидность по доступным средствам. Не публиковать backup в Git, отчёты или чат: он может содержать чувствительную конфигурацию.

Извлекать backup только предусмотренными продуктом средствами; не угадывать формат и не редактировать его вручную.

**PART A PASS:** `SOURCE_INVENTORY`, `TARGET_INVENTORY`, `VERSION_COMPATIBILITY`, `ISOLATION_PLAN`, `SOURCE_BACKUP` = PASS. При любом HOLD — не продолжать.

---

## PART B — УСТАНОВКА НОВОГО LINUX CONTROLLER

**Только после Part A PASS и отдельного Owner GO на установку.** Разрешение НЕ включает миграцию AP.

### B1. Установка зависимостей

По approved матрице установить ровно нужные Java/MongoDB/JSVC и необходимые runtime packages. Для MongoDB выбрать поддерживаемую комбинацию с ОС и приложением; не использовать неподтверждённые репозитории. Сохранить версии пакетов и сервисных units без секретов.

Перед фактическим install убедиться в отсутствии конфликтов listeners и небезопасной WAN/guest reachability.

### B2. Omada Software Controller install

Установить точный approved vendor package (нативный `.deb` или vendor `tar.gz`, согласно конкретной версии). Не использовать плавающую версию, непроверенные 3rd-party Docker images, автоматический upgrade. Создать отдельный management account и включить доступную в данной версии защиту; не раскрывать credentials в evidence.

После запуска проверить:

- Controller process/service = active и воспроизводимо стартует после controlled restart;
- target HTTP(S) listeners = ожидаемые, NPM 80/81/443 = без регрессии;
- control UI reachable только из management LAN;
- Guest VLAN / WAN не имеют доступа к management interface;
- Java/MongoDB logs не содержат fatal errors, disk usage нормально;
- old Controller/AP statuses неизменны.

Если service startup не проходит — **STOP**, не корректировать NPM/Cisco и не менять версию Omada ad hoc.

### B3. Restore backup на target

1. До импорта сохранить baseline target состояния (или документировать, что target пустой).
2. Воспользоваться **штатной Backup & Restore** процедурой, не выполняя действий `Migrate Devices`.
3. Если мастер переносит в flow, требующий подтверждения на старом контроллере, **приостановить** операцию и определить эффект `Confirm` конкретной версии. Простой импорт backup ≠ разрешение финализировать миграцию.
4. После restore проверить startup/health и целостность структур (Sites, WLAN, Hotspot, AP inventory objects, OpenAPI identities, roles, certificates, external portal references).
5. Сравнить конкретные критические параметры и идентификаторы с A1, не предполагая, что SSID, Controller ID, Site ID, API client ID/secret или webhook targets сохранились буквально.
6. Если restored Controller пытается управлять production AP — сразу STOP, восстановить isolation, проверить старый Controller.

**Важно:** наличие AP в *inventory* нового контроллера после restore не считается фактом их миграции. Физические AP должны оставаться connected/managed на старом Controller; на новом не должно появиться непрошеных `Connected/Adopted` production AP.

### B4. После Restore — проверка логики (без production AP)

Проверить UI и read-only management API с разрешённого management client:

- логин, роли, Sites и настроенные WLAN/Hotspot/External Portal;
- target Controller/OpenAPI endpoint и аутентификацию **только read-only запросами**;
- `omadac_id`, Site IDs, наличие API clients, наличие Client Secret в утверждённом секретном хранилище (не выводить value);
- webhook URL и приемник: не перенаправлять production webhooks на target пока старый Portal активен; проверить настройки без отправки production events;
- SSID `Zefer_Parki` и фактические значения других network profiles; возможное расхождение SSID записать как **finding**, а не автоматически «исправить».

Нет живых AP на target → ожидаемо нельзя подтвердить client inventory, AP online, hotspot authorization и E2E гостевой вход. Это **NOT TESTED BY DESIGN**, не FAIL установки.

### B5. Safe lifecycle, target backup/restore

Создать защищённый target backup для нового Controller после restore. Проверить, что backup можно восстановить на отдельном временном/изолированном target **без подключения production AP** (либо документировать безопасный проверяемый offline restore; без этого `RESTORE_SMOKE=HOLD`). Зафиксировать автоматический/ручной backup policy, retention, file ownership, контроль диска и health monitoring, способ version-locked восстановления.

Проверить controlled restart и OS reboot persistence по согласованному окну, чтобы не уронить NPM или другие сервисы. Если reboot host может затронуть уже действующий NPM public Edge, **не выполнять reboot** без отдельного Owner GO и maintenance window; достаточно service-only restart, reboot gate = HOLD/DEFERRED.

---

## PART C — ACCEPTANCE: ЧТО СЧИТАЕТСЯ УСПЕШНЫМ

| Gate | Expected |
|---|---|
| Exact compatible controller build | PASS |
| Supported Linux/Java/MongoDB/JSVC | PASS |
| Controller service stable | PASS |
| Controller UI management-only | PASS |
| No NPM or public ingress regressions | PASS |
| Target backup imported without AP migration | PASS |
| Sites / SSID / Hotspot / External Portal config comparison | PASS or documented differences + Owner disposition |
| Controller identity & OpenAPI read-only connectivity | PASS or explicit HOLD (no false assumption of preserved secrets) |
| No AP adopted by target | PASS |
| Old controller retains all production APs | PASS |
| No active production webhook redirect | PASS |
| Target backup consistency + isolated restore smoke | PASS |
| Host restart persistence | PASS only if safely executed; otherwise DEFERRED |
| Live guest authorization via new Controller | OUT OF SCOPE / NOT TESTED |

**Постоянно проверять старую систему:** UI/health старой Omada, число и статус AP, стабильность WLAN; текущий Portal и гостевая авторизация не должны измениться. Случайное AP movement = FAIL, не «частичный успех».

**Критерий DONE:** `NEW_OMADA_PREPARED=PASS` и `PRODUCTION_AP_MIGRATION=NO`. Это **не** `NEW_OMADA_PRODUCTION=PASS`.

---

## PART D — STOP / ROLLBACK

**До restore:** остановить target Omada service и вернуться к проверенному installer snapshot/пакетам, не затрагивая working NPM, старый Controller, Portal.

**После restore:** при несовместимости/неожиданном устройстве/секретах — остановить **только новый** Controller, оставить старый работающим. Зафиксировать диагностический bundle без секретов. Не использовать `Forget Devices`, `Migrate Devices`, factory-reset AP или смену inform, даже как «быстрый rollback».

Rollback здесь — **прекращение и изоляция нового тестового Controller**, а не изменение текущей production сети.

Если зафиксирована попытка takeover, восстановление старого controller/AP ownership должно вестись по отдельному инцидентному плану, а не несанкционированными действиями данного TASK.

---

## PART E — ОТЧЁТ SYSADMIN / EVIDENCE

Заполнить и вернуть Architect + Owner (без паролей, backups, auth tokens, client secrets):

```text
TASK=TASK-CAPTIVPROD-OMADA-INSTALL-01
DATE_TIME=
SOURCE_CONTROLLER_OS=
SOURCE_CONTROLLER_IP=
SOURCE_CONTROLLER_VERSION_FULL=
SOURCE_CONTROLLER_SITE_COUNT=
SOURCE_CONTROLLER_AP_MANAGED_BEFORE=
SOURCE_CONTROLLER_AP_MANAGED_AFTER=
TARGET_HOST=
TARGET_IP=
TARGET_OS=
TARGET_OMADA_VERSION_FULL=
TARGET_ARTIFACT_SOURCE=
TARGET_ARTIFACT_SHA256=
JAVA_VERSION=
MONGODB_VERSION=
JSVC_VERSION=
INSTALL_METHOD=
TARGET_SERVICE_STATUS=
PORTS_AND_PROTOCOLS=
NPM_CONFLICTS=NONE/DETAILS
MANAGEMENT_SCOPE=
WAN_GUEST_ADMIN_ACCESS=DENIED/FAIL
SOURCE_BACKUP_TIME=
SOURCE_BACKUP_SHA256=
RESTORE_RESULT=
RESTORED_SITE_COUNT=
RESTORED_SSID_CONFIG_PARITY=
RESTORED_HOTSPOT_CONFIG_PARITY=
RESTORED_CONTROLLER_ID_PARITY=
RESTORED_SITE_ID_PARITY=
RESTORED_API_CLIENT_ID_PARITY=
RESTORED_SECRET_STATUS=CONFIRMED/REPROVISION_REQUIRED/HOLD
OPENAPI_READONLY_TEST=
WEBHOOK_PRODUCTION_ROUTE_UNCHANGED=YES/NO
TARGET_AP_ADOPTED_COUNT=0/OTHER
OLD_AP_STILL_MANAGED=PASS/FAIL
TARGET_BACKUP=PASS/FAIL
TARGET_RESTORE_SMOKE=PASS/HOLD/FAIL
SERVICE_RESTART=PASS/HOLD/FAIL
HOST_REBOOT=PASS/DEFERRED
CURRENT_PORTAL_UNCHANGED=YES/NO
CISCO_DNS_NPM_HESTIA_UNCHANGED=YES/NO
NEW_OMADA_PREPARED=PASS/HOLD/FAIL
PRODUCTION_AP_MIGRATION=NO
NEXT_TASK_AUTHORIZATION=NOT_GRANTED
OPEN_ISSUES=
```

Скриншоты — без MAC/IP посетителей, приватных токенов и sensitive config. Хранение архивов backup и ключей — только в approved protected infrastructure.

---

## FOLLOW-UP TASKS — НЕ РАЗРЕШЕНЫ ЭТИМ ДОКУМЕНТОМ

1. `TASK-CAPTIVPROD-PORTAL-INSTALL-01` — независимая установка CaptivePortal и связь с новым Controller без production cutover.
2. `TASK-CAPTIVPROD-OMADA-AP-PILOT-01` — отдельная миграция **одной согласованной тестовой AP** и ограниченный тест телефона с безопасным rollback.
3. `TASK-CAPTIVPROD-PRODUCTION-CUTOVER-01` — финальная миграция остальных AP, NPM/backend переключение и E2E acceptance.

**Architect verdict:** план установки approved как техническое задание. `AP_MIGRATION=HOLD`; `PORTAL_CUTOVER=HOLD`; `OWNER_GO` требуется перед исполнением меняющих target host шагов. Вся Part A — только наблюдение, экспорт и согласование.
