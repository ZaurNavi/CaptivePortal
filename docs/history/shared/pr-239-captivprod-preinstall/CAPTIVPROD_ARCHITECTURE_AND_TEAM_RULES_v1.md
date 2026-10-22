# CAPTIV-PROD — постоянные архитектурные и командные правила

**Document ID:** `CAPTIVPROD-ARCH-RULES-01`  
**Версия:** `v1.0`  
**Дата:** `2026-10-14`  
**Владелец решений:** Owner  
**Назначение:** закрепляемый источник правил для Architect, Tech Lead, SysAdmin, Coder, Research/QA и других исполнителей проекта Captiv-Prod.  
**Статус:** принятые направления архитектуры; технические изменения разрешаются только отдельными TASK/GO.

## 1. Цель и принцип независимости

Captiv-Prod разворачивает собственную новую инфраструктуру **Omada Controller + CaptivePortal** на `captiv-prod` независимо от действующей VM Portal `192.168.0.202` и Omada Controller Windows `192.168.0.222`.

Новый Portal устанавливается **с нуля из проверенного Git-коммита**, без переноса исторических SQLite, журналов, старых сессий, snapshots и накопленной аналитики. Однако эксплуатационные настройки, идентификаторы Site, права, API credentials, trust policy и требуемые security keys создаются или воспроизводятся сознательно, с проверкой их фактического соответствия новой Omada. «Чистые данные» не означают «случайные настройки».

Работа над новым контуром не должна требовать изменения старого production до отдельно утверждённого этапа. **Независимость логическая и эксплуатационная, не физическая:** оба контура используют общий Cisco WAN/NAT, публичный адрес и NPM Edge; отказ общей инфраструктуры может затронуть оба.

## 2. Имена и публичный Edge

- **Планируемый новый FQDN:** `captivprod-navi.duckdns.org` — кандидат, пока Owner не подтвердил регистрацию и управление записью. Не считать имя существующим, свободным, работающим или выданным до проверки.
- **Существующий FQDN:** `captivportal-navi.duckdns.org` — старый production; не использовать для staging и не перенаправлять на новую установку.
- После регистрации Owner подтверждает точное имя, A/AAAA записи, актуализацию DDNS, внешний IPv4 и доступность с guest/LAN/WAN; при несовпадении имени любые зависимые изменения — HOLD.
- Публичный HTTP/HTTPS ingress остаётся за **Nginx Proxy Manager (NPM)** на `captiv-prod` (`192.168.0.99`, подтверждать live перед изменениями). Не устанавливать вторую публичную Nginx/Apache TLS-границу ради Portal.
- Для нового FQDN создаётся **отдельный Proxy Host и отдельное управление сертификатом** внутри существующего NPM, после preflight и разрешения. Не изменять старый Proxy Host, его сертификат или Hestia upstream.
- DNS разных FQDN может указывать на один публичный IP; маршрутизацию по hostname осуществляет NPM. **Cisco NAT, публичный IP и старый домен не меняются** в ходе независимой установки.
- Новый FQDN рассматривается как **постоянное имя нового Portal**, а не автоматически временный alias. Его изменение в будущем требует отдельного решения.

## 3. Контуры и Ownership

**Старый production (неизменяем во время подготовки):**

```text
Production APs → Omada Windows 192.168.0.222
Production guests → existing NPM Proxy Host → Hestia 192.168.0.202 → old CaptivePortal
FQDN: captivportal-navi.duckdns.org
```

**Новый staging (изолированно готовим):**

```text
New Omada Linux (captiv-prod), no production AP adoption
New CaptivePortal (captiv-prod), fresh application data
FQDN: captivprod-navi.duckdns.org [registration pending]
Cisco → existing NPM → dedicated new Proxy Host → approved private app backend
```

Новая Omada может быть установлена и восстановлена из backup **без миграции AP**. Наличие AP в импортированном inventory не равно передаче управления. Никакие `Migrate Devices`, `Adopt`, `Forget`, изменение inform, массовые изменения SSID/Hotspot или webhook маршрутов не разрешены автоматически.

Полный реальный guest E2E с новой Omada без управляемой ею тестовой AP имеет статус **NOT TESTED BY DESIGN**, а не PASS. Перевод одной AP допускается только отдельным TASK, Owner GO и rollback.

## 4. Право на самостоятельные изменения проекта

Команда Captiv-Prod вправе самостоятельно анализировать, проектировать, реализовывать и тестировать необходимые изменения CaptivePortal, в частности **deployment compatibility, конфигурация bind HOST/PORT, systemd, интеграция NPM, Linux compatibility, security hardening и automation**. Согласовывать каждую небольшую техническую идею со старой командой заранее не обязательно.

Это право **не** отменяет разделения ролей и обязательных проверок:

1. Architect определяет контракт, границы изменения, безопасность и acceptance criteria.
2. Tech Lead выпускает scope-bounded implementation TASK и определяет необходимые gates.
3. Coder делает изменения в отдельной ветке/worktree; не редактирует production source напрямую.
4. Research/QA либо назначенный независимый reviewer проверяет заявленные свойства и regressions.
5. Принятый код публикуется GitHub PR; утверждённый merge SHA/tree является единственным обычным источником production deploy.
6. Owner отдельно разрешает merge, установку, активацию, изменение публичных маршрутов и AP migration по соответствующим TASK.

Исходный репозиторий — `ZaurNavi/CaptivePortal`. **Предпочтительна одна общая каноническая кодовая база**, без постоянно расходящихся приватных fork. Другой команде направляется change summary/PR/evidence, а не требование выполнить всё за нас. При затрагивании критической auth/CAPPORT/Omada semantics либо общих архитектурных контрактов — согласование с ответственными архитектором/Tech Lead проекта обязательно до релиза. Временные экспериментальные ветки возможны, но не становятся отдельным production baseline без явного решения.

## 5. Flask bind и Docker NPM

В исследованном коде `app/config.py` определены `HOST = "127.0.0.1"`, `PORT = 8088`, а NPM работает в Docker bridge. Контейнерный `127.0.0.1` **не является** host loopback Linux.

**Предпочтительное архитектурное направление:** reviewed Git change, делающее bind HOST/PORT deployment-configurable через действующий pipeline `process environment → app/config.py → app/settings.py:get_settings() → run.py`, с сохранением безопасных defaults `127.0.0.1:8088` и обратной совместимости старой VM.

**Не разрешено по умолчанию:** `0.0.0.0` без утверждённой сетевой изоляции; публикация 8088 в WAN/Guest; Docker host networking для NPM ради обхода; неучтённый relay; второй публичный nginx; неподтверждённый контейнерный адрес. Адрес backend и ограничения Docker→host должны определяться **фактической network topology** и подтверждаться проверкой достижимости **только из авторизованного NPM пути**.

Изменение bind не разрешает изменение `ProxyFix` наугад. Перед NPM activation проверяются client IP, Host, Proto, Port, URI/path/query, trusted forwarded headers, защита от spoofing и privacy логов. Любая неопределённость = `NET-01 HOLD`.

## 6. Порядок независимой установки и активации

1. **Read-only preflight:** текущее состояние NPM/host/старой VM, Omada, доступные ports, DNS, сертификаты, trusted networking; точные approved commit/tree и dependency set.
2. **Новая Omada:** подтверждённая установка Linux Controller, restore конфигурации, management isolation, read-only OpenAPI, сохранение old AP ownership. Пока без AP migration.
3. **Новый FQDN:** подтверждение регистрации, DNS/DDNS и планирование независимого Proxy Host; **не** менять старый production route.
4. **Новый Portal:** свежие data stores, approved Git release, isolated settings/secrets, один `run.py` systemd process, локальный smoke и безопасное read-only соединение с новой Omada.
5. **NPM backend:** только после `NET-01 PASS` отдельный Proxy Host, сертификат и проверка header/TLS/privacy semantics, без переключения старого имени.
6. **Pilot:** отдельно разрешённая тестовая AP + Owner-controlled телефон; при необходимости выделенный тестовый SSID/Hotspot/FQDN. Проверка Omada authorized **по read-back**, а не лишь HTTP 200.
7. **Production transfer:** только после pilot PASS — отдельные decisions для остальных AP, webhook ownership, workers и optional components. Старый production сохраняется как rollback до завершения acceptance.
8. **Feature expansion:** webhook, visits, registry, observation/current state, analytics/Admin, Settings, Fingerprint/SPAN/Suricata/NI — по собственным dependency/security gates. Никаких «включить всё» или двойных cleaners/consumers.

Не допускается одновременно иметь два активных обработчика одного и того же production потока, способных отправлять конкурирующие authorization/cleaner/webhook side effects. Фоновый collection, даже без AP, оценивается по фактическому воздействию и может быть отключён на staging.

## 7. Конфигурация, данные и безопасность

- Runtime secrets никогда не публикуются в Git/PR/chat/log/evidence; в отчётах только факт наличия и источник.
- Значения `OMADA_URL`, `OMADA_ID`, `Site ID`, `OpenAPI client`, SSID, guest CIDR, webhook mapping, CAPPORT Site/FQDN проверяются **на новой Omada**, не копируются по памяти со старой.
- Часть CAPPORT и TLS параметров может быть константами кода; файлы `.env.example` не гарантируют автоматического применения. Проверять **точный принятый SHA**.
- Настройки Settings Store, если включены, имеют отдельные migration/bootstrap/secret-key/activation контракты; не считать его «ненужной историей». Данные создают собственные authoritative writers; ручное создание SQLite схем по догадке запрещено.
- Авторизация и административный доступ разделены. Admin control surfaces не публиковать произвольно в Guest/WAN.
- Тестирование действующей гостевой авторизации — только на заранее согласованной тестовой AP и владельческом устройстве; посторонних клиентов не трогать.
- Операционная наблюдаемость/backup/restore, корректность systemd и безопасная ротация журналов — обязательные условия принятия, а не факультативный косметический этап.
- Не ослаблять SQLite durability и не переносить производственные дисковые проблемы на новую среду без измерений.

## 8. STOP / GO / rollback

Без отдельного Owner GO **не разрешены**: изменение production NPM Proxy Host, Cisco NAT/DNS, перенос AP, выключение старого Omada/Portal, массовое изменение SSID/Hotspot, production webhook redirect, подмена публичного FQDN и включение управляющих фоновых функций нового Portal.

**Обязательные статусы:**

- `NEW_FQDN=PLANNED | VERIFIED`
- `NEW_OMADA_PREPARED=PASS | HOLD`
- `NEW_PORTAL_LOCAL_PREPARED=PASS | HOLD`
- `NET-01=PASS | HOLD`
- `NPM_ISOLATED_PROXY_HOST=PASS | HOLD`
- `PILOT_AP=NOT_AUTHORIZED | PASS | FAIL`
- `OLD_PORTAL_UNCHANGED=YES | NO`
- `OLD_OMADA_AP_OWNERSHIP_UNCHANGED=YES | NO`
- `PRODUCTION_CUTOVER=HOLD | AUTHORIZED | PASS | ROLLBACK`

При критическом FAIL остановить/изолировать **только новый** компонент, сохранить evidence без секретов, подтвердить здоровье старого production и вернуться к последнему проверенному состоянию. Откат AP требует отдельного безопасного плана, а не случайного `Forget` или factory reset.

## 9. Источники, приоритет и изменение правил

Основание: решения Owner в беседе Architect Captiv-Prod, `TASK-CAPTIVPROD-EDGE-NPM-01` и Architecture Amendment v3, `TASK-CAPTIVPROD-OMADA-INSTALL-01`, `TASK-CAPTIVPROD-PORTAL-FRESH-INSTALL-01`, руководство прежнего архитектора `CaptivPortal_Fresh_Install_Guide_2026-10-14.docx`, фактически проверенный код `ZaurNavi/CaptivePortal`.

Этот документ фиксирует **политику и целевую архитектуру**, но **не заменяет** конкретные TASK, точный code revision, результаты live inspection, инструкции производителя и назначенные approvals. При противоречии между живым проверенным фактом и историческим описанием фиксировать конфликт и ставить затронутый этап на HOLD; ничего не «исправлять по догадке». Особые production изменения требуют отдельного утверждения Owner.

Правила меняются только версионированной редакцией с кратким changelog и согласием Owner. Новая версия не выдаёт задним числом разрешений на старые HOLD.

---

**Architect verdict:** `INDEPENDENT_NEW_FQDN=APPROVED AS DESIGN`; `OLD_PORTAL_UNCHANGED=REQUIRED`; `SELF_IMPLEMENTED_GITHUB_PR=ALLOWED WITH REVIEW`; `PUBLIC_NPM_ROUTE/AP_MIGRATION=HOLD UNTIL SEPARATE GO`.
