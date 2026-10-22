# TASK-CAPTIVPROD-ARCH06-TARGETED-CLOSURE-07_v2
## Новая Omada, systemd dependencies, NET-01 local Sensor path — до установки CaptivePortal

**От:** Captiv-Prod Architect  
**Кому:** Captiv-Prod SysAdmin  
**Дата:** 2026-10-15  
**Цель:** закрыть конкретные неопределённости предустановочной архитектуры на `captiv-prod` (`192.168.0.99`)  
**Режим:** READ-ONLY + OFFLINE PACKAGE/DESIGN; изменения работающей инфраструктуры — только по отдельному scoped Owner GO.  
**CAPTIVEPORTAL INSTALL:** NOT AUTHORIZED.

> **URGENT OWNER CORRECTION — SUPERSEDES ALL EARLIER CISCO INSTRUCTIONS IN ARCH-05/06/07.**
>
> **Cisco port 48 belongs to the running legacy CaptivePortal. DO NOT TOUCH it or its legacy mirror/VLAN 10/VLAN 999 configuration.**
> **Only Cisco port 45 is in scope for the NEW Captiv-Prod.** No Cisco switch configuration changes are authorized in this task, including on port 45. No investigation/reconfiguration of the legacy capture session. If a command would inspect or change the old session, do not run it.
> Any change to Cisco requires a NEW narrow plan specifying the exact port 45 interface name, proposed dedicated session and source scope, independent Owner GO, and rollback. No copying of old production SPAN/RSPAN/VLAN settings.
> Previous Cisco-related instructions in TASK-CAPTIVPROD-FULL-PREINSTALL-ARCH-05, BLOCKER-CLOSURE-06, and TARGETED-CLOSURE-07 are **VOID** wherever they conflict with this correction. Stop any Cisco activity based on those instructions.


### 0. Фиксированный baseline

- Новый сервер: `192.168.0.99`; новая Omada v5.14.32.3, UI/API endpoint `https://192.168.0.99:8043`.
- Принятый CaptivePortal release: commit `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`; tree `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`.
- Новый FQDN: `captivprod-navi.duckdns.org`; старый `.202` Portal и `.222` Omada не изменять.
- Новый NPM: Docker bridge `172.18.0.0/16`, контейнер-кандидат `172.18.0.2`, gateway `172.18.0.1`.
- Flask backend candidate: `172.18.0.1:18089` (порт Omada `8088` не менять).
- SPAN NIC-кандидат нового хоста: `enp3s0`. **Единственный рассматриваемый порт коммутатора для нового Captiv-Prod — порт 45.** Физическую коммутацию `port 45 ↔ enp3s0` нужно подтвердить без воздействия на старые порты. `enp8s0` — старый хост, **не копировать**.
- Старый production уже обновлён до принятого Git TREE; исправлять или повторно тестировать старую VM в рамках этого TASK не надо.
- Owner предоставил credentials **новой** Omada отдельно; не включать секреты, токены или их значения в документы, URL, shell history, `ps`, `journalctl` и логи. Не приводить их в ответе. Запланировать ротацию client secret перед эксплуатационным вводом.

### A. New Omada — credentialed read-only acceptance (priority 1)

Используя опубликованную OpenAPI schema **именно этой версии** и предоставленный Owner client credential, выполнить минимальные read-only проверки. Для токена использовать защищённое временное хранилище; любые нестандартные TLS trust errors — `HOLD_TLS`, не `verify=False` для credentialed requests.

1. Проверить token exchange (`client_credentials`) без раскрытия token/secret.
2. Получить настоящий **Site list** с Site IDs и Site names. Записать правильный 24-hex Site ID будущего Portal.
3. Получить read-only AP inventory: количество, adoption/connected status, controller ownership. Никаких adopt/migrate/reconnect/block.
4. Проверить WLAN/SSID, guest/hotspot, external portal URL и scopes/privileges приложения, где API поддерживает read-only GET. Нет прав — `HOLD_PERMISSION`, не угадывать.
5. Установить семантическую разницу между `Omada ID`, предоставленным Owner, `controllerId` из `/api/info` и реальным `Site ID`. **Не считать ни один 32-hex ID Site ID.**
6. Проверить TLS certificate, CA и SAN для будущего Portal→Omada API. Если доступен только недоверенный URL — оформить безопасный local-FQDN/SAN plan.
7. Уточнить текущие AP/SSID/guest CIDR и controller webhook settings **без изменения**.

**Deliverable:** `OMADA_NEW_SITE_API_INVENTORY_READONLY.md` с site name/id (non-secret), версиями, корректным API URL, permissions и blocked items. Credentials и токены не включать.

### B. Old VM systemd output — только reference (priority 2)

Owner предоставил `plink -load Ubunt` вывод с работающей старой VM (`enp8s0`, Core `127.0.0.1:8088`). Это reference для зависимостей, **не** факт о новом `.99`.

1. У старого `fingerprint-suricata.service` виден `TimeoutStartUSec=1min30s`, а один `ExecStartPre` ждёт `suricata-eve.sock` до `1830s`. Доказать, **кто и когда создаёт socket**, и нет ли потенциального циклического startup wait / stale socket. Поскольку старый production работает, изменять его нельзя.
2. Для нового сервера описать правильные startup/dependency contracts Suricata→EVE→Sensor, socket ownership, watchdog/timeouts, с учётом выбранного `enp3s0`. Отдельно проверить доступные systemd templates из принятого Git SHA.
3. Старый `edge-bridge` имеет `Requires=captive-portal.service`; `network-metadata-rotation` — timer/oneshot и `After=fingerprint-suricata.service` без явного `Requires`. Отразить эти различия, не перенести зависимости механически.
4. Старые CPUWeight/IOWeight — только reference. `IOAccounting=no` не означает запрета I/O, `IOWeight` — относительная настройка. Для нового HDD host составить план лимитов/метрик с учётом небольшой дисковой нагрузки и фактических enabled units.
5. Подготовить complete new-host systemd graph и «socket-creator first» правило без увеличения таймаута вслепую.

**Deliverable:** `NEW_HOST_SYSTEMD_SURICATA_EVE_DEPENDENCIES.md`.

### C. NET-01 package + Sensor→Core loopback (priority 1)

1. Обнаруженные вновь загруженные `NET01_REV4_*` и `PART-A_REV4.zip` **идентичны старой REV4** (`sha256:d958d029456bcca7235ae218094c049b5e2ee6edd33ce668b463838bc9daacb9`) и содержат ранее найденный P1 maintenance CLI mismatch. **Не применять**.
2. Передать полный исправленный **REV4.1** архив с исходными scripts, manifest, changelog и всеми tests, а не REV4, не только отчёт и не review-pointer. Если REV4.1 является локальной копией на Windows workstation, приложить её точный ZIP без секретов.
3. В отдельной следующей ревизии предусмотреть оба разрешённых источника на `172.18.0.1:18089`: (a) NPM Docker `172.18.0.2` через проверенный bridge; (b) **только фактически проверенный host-local/loopback route Sensor readiness**. Любое новое правило должно пройти синхронное изменение installer, verifier, watchdog, rollback и positive/negative fixtures; не ослаблять guard частичной правкой.
4. Проверить `ip route get` для локального адреса, source IP, `INPUT`/`OUTPUT`, trust boundary всех host processes, необходимость дополнительных UID/cgroup controls. Не добавлять широкое `172.18.0.0/16 ACCEPT` и не открывать Guest/LAN/WAN.
5. Доказать offline и в изолированном systemd PID1 staging: fail-closed startup, OnFailure/stop propagation, реальный verifier path в maintenance-reinstall, pending jobs, forced kill и drift. Действующий Docker/NPM не пересоздавать без scoped GO.
6. Подготовить план временного diagnostic HTTP backend на новом хосте и реальные positive/negative tests **до установки Portal**, с отдельным GO на network/firewall changes.

**Deliverable:** `NET01_REV4_1_FULL.zip` плюс следующий `NET01_SENSOR_LOCAL_PATH_DESIGN.md`; после review — одна консолидированная финальная NET01 версия для live gate.

### D. Остальные ARCH-06 gates — продолжить до полного PREINSTALL PASS

- **Cisco — только выделенный порт 45 для нового Captiv-Prod.** На уровне read-only проверить точное имя интерфейса порта 45, link/status и фактическую физическую линию `порт 45 ↔ enp3s0`. Не опрашивать, не использовать и не менять существующие legacy SPAN/RSPAN-сессии и порты. Не запускать общие команды просмотра `monitor session`, если они затрагивают старую конфигурацию. Новые source ports / source VLANs / direction, выделенная новая SPAN-session и её destination пока **НЕ УТВЕРЖДЕНЫ**: составить отдельный проект только для нового порта 45 и запросить Owner GO перед любыми изменениями. Ни один существующий источник mirroring не переиспользовать молча.
- **Новый Linux host:** отдельно изучить `enp3s0` и предложить scoped fix `net.ipv4.conf.enp3s0.forwarding=0`, если нужен для preflight Sensor. Не отключать глобальный `ip_forward`, нужный Docker; не изменять ничего на старой VM. Сначала доказать отсутствие побочных эффектов и получить Owner GO перед применением.
- Evidence Receiver: утвердить loopback HTTPS `127.0.0.1:9443`, SAN, отдельные CA/Bearer credentials для Sensor и Portal Producer, registration policy, пустые stores/spools, F-B1 Source Admission workflow.
- NPM: отдельный `captivprod-navi.duckdns.org` proxy host и сертификат; SNI/Host/XFF негативные тесты только на diagnostic backend после NET01 GO.
- Omada webhook route с корректным SNI и локальной маршрутизацией; не полагаться на IP-only caller authentication.
- Все зависимости, secrets, systemd, storage, backup, monitoring и rollback **подготовить до установки**, но не выдавать runtime-only functionality за PREINSTALL PASS.

### E. Границы полномочий

**Без отдельного scoped Owner GO запрещено:** менять NPM/его сети и Proxy Hosts, iptables/nftables, **любой Cisco port/режим, включая выделенный port 45**, Omada profiles/AP, создавать active Evidence producers, менять старые `.202`/`.222`, переносить AP, устанавливать либо запускать новый CaptivePortal. **Cisco port 48 и legacy session — полностью вне scope даже read-only исследования в этом TASK.**

### F. Отчёт

```text
TASK=TASK-CAPTIVPROD-ARCH06-TARGETED-CLOSURE-07
MODE=READ_ONLY_AND_OFFLINE
NEW_OMADA_API_IDENTITY=
NEW_OMADA_SITE_ID=
NEW_OMADA_SITE_NAME=
NEW_OMADA_AP_INVENTORY=
NEW_OMADA_OPENAPI_SCOPE=
NEW_OMADA_TLS_IDENTITY=
OMADA_ID_VS_CONTROLLER_ID_VS_SITE_ID=
LEGACY_SYSTEMD_REFERENCE_RECONCILED=
NEW_SURICATA_SOCKET_CREATOR=
NEW_SURICATA_STARTUP_ORDER=
NEW_SYSTEMD_DEPENDENCY_GRAPH=
REV4_REUPLOADED_DUPLICATE=YES
REV4_1_FULL_PACKAGE_ATTACHED=YES/NO
NET01_REV4_1_ARCH_REVIEW=
NET01_SENSOR_LOCAL_POLICY=
NET01_REAL_PID1_STAGING=
SPAN_NEW_PORT45_ONLY=
NEW_HOST_ENP3S0_FORWARDING_DECISION=
EVIDENCE_RECEIVER_TLS_PLAN=
SOURCE_REGISTRATION_F_B1_PLAN=
NEW_FQDN_PROXY_SNI_PLAN=
RUNTIME_ONLY_TESTS=
OPEN_P0=
OPEN_P1=
PREINSTALL_READY=PASS/HOLD
CAPTIVEPORTAL_INSTALL=NOT_AUTHORIZED
OLD_PRODUCTION_UNCHANGED=YES
SECRETS_IN_REPORT=NO
```

**Цель:** все сетевые и сервисные дорожки нового Captiv-Prod подготовлены, документированы, имеют точную политику доступа и проверку до начала установки CaptivePortal, **не исследуя и не меняя legacy Cisco port 48 / session**. По результату этого TASK Architect выдаст решение по каждой архитектурной зависимости; установка остаётся на HOLD.
