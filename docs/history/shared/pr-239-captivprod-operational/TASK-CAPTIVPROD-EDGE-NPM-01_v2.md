# TASK-CAPTIVPROD-EDGE-NPM-01
## Развёртывание Nginx Proxy Manager и перенос public HTTP/HTTPS ingress с Hestia

**Исполнитель:** CaptivPortal Production Deployment Lead / SysAdmin  
**Целевой host:** `captiv-prod`  
**Компонент:** Nginx Proxy Manager (NPM)  
**Тип работ:** Infrastructure / Reverse Proxy / TLS  
**Application code CaptivPortal:** НЕ изменяется  
**Hestia hosting configuration:** максимально НЕ изменяется  
**Cisco:** изменяется только в Part B и только существующий NAT/port-forward 80/443  
**Production cutover:** отдельное контролируемое окно
**Revision:** v2 — SysAdmin review / operational hardening

---

# 1. Архитектурная цель

Текущее состояние концептуально:

```text
Internet
   ↓
Cisco
   ↓ TCP 80/443
Hestia
   ├─ Captive Portal
   ├─ Cloud
   └─ VPN
```

После выполнения данного TASK:

```text
Internet
   ↓
Cisco
   ↓ TCP 80/443
Nginx Proxy Manager
   │
   ├─ Captive Portal ─┐
   ├─ Cloud           ├─→ Hestia:443
   └─ VPN             ┘
```

На этой стадии:

```text
PUBLIC INGRESS OWNER = NPM
PUBLIC TLS OWNER     = NPM

HOSTING/BACKEND OWNER = Hestia
```

То есть Hestia перестаёт быть публичным Edge, но пока остаётся backend reverse-proxy/hosting layer.

Следующая архитектура:

```text
NPM → Captive Portal напрямую
NPM → Cloud напрямую
NPM → VPN напрямую
```

**НЕ входит в данный TASK.**

---

# PART A — УСТАНОВКА И ПОДГОТОВКА NPM БЕЗ ПЕРЕКЛЮЧЕНИЯ PRODUCTION

## A1. Preflight

До любых изменений исполнитель обязан заново определить и зафиксировать:

```text
target host identity = captiv-prod
current IP
OS/version
Docker state
Docker Compose state

listeners:
80
81
443

free disk
RAM
CPU/load

existing firewall state
existing Nginx/Apache/Caddy/other reverse proxy state

management NIC/IP
default route
IPv4/IPv6 listeners
Docker bridge/NAT state
reachability from host to Hestia internal IP:443
current system-backup health / last successful snapshot
```

Если `80` или `443` уже заняты неизвестным сервисом:

```text
STOP
```

Не убивать listener и не перестраивать существующую архитектуру «по месту».

Отдельный системный Nginx перед NPM **не устанавливать**.

Целевая модель:

```text
Cisco → NPM → backend
```

а не:

```text
Cisco → Nginx → NPM → backend
```

## A2. NPM deployment model

Использовать штатное Docker Compose deployment Nginx Proxy Manager.

Для этого TASK зафиксировать exact image:

```text
jc21/nginx-proxy-manager:2.16.0
```

Не использовать плавающий `latest`.

Использовать встроенный SQLite.

Отдельные MariaDB/PostgreSQL для трёх proxy hosts **не создавать**.

Обязательная persistent state:

```text
/data
/etc/letsencrypt
```

Рекомендуемое размещение всего NPM deployment:

```text
/opt/nginx-proxy-manager/
```

с отдельными persistent subdirectories для:

```text
compose/config
data
letsencrypt
backup
```

Compose deployment должен дополнительно фиксировать:

```text
restart policy = unless-stopped
network mode   = bridge/default compose network
privileged     = NO
host network   = NO
Docker socket  = НЕ монтировать
```

После первого pull exact tag недостаточно считать полностью immutable. До Part B зафиксировать фактический image digest:

```text
jc21/nginx-proxy-manager:2.16.0
→ RepoDigest sha256:...
```

Предпочтительно перед cutover закрепить deployment по digest либо, минимум, включить digest в evidence и запретить непреднамеренный pull/upgrade в окно cutover.

Для Docker stdout/stderr logs задать ограниченную rotation policy, чтобы контейнерный log не рос без границ. Рекомендуемый baseline:

```text
max-size = 10m
max-file = 3
```

Compose-файлы и любые файлы с credentials должны иметь минимально необходимые permissions; секреты не печатать в evidence.

## A3. Ports

NPM получает:

```text
80/tcp  = public HTTP
443/tcp = public HTTPS
81/tcp  = NPM Administration
```

При этом:

```text
80/443 → после Part B доступны из Internet

81 → ТОЛЬКО management LAN
81 → НЕ публиковать через Cisco
81 → НЕ открывать в WAN
```

На `captiv-prod` предпочесть explicit bind к management IP `192.168.0.99`, а не wildcard publish:

```text
192.168.0.99:80  → container:80
192.168.0.99:443 → container:443
192.168.0.99:81  → container:81
```

Особенно для `81/tcp` запрещён publish вида `0.0.0.0:81:81` / `[::]:81`.

Одного отсутствия Cisco NAT недостаточно для утверждения `81 = management LAN only`, потому что другие routed VLAN могут теоретически достигать `192.168.0.99`. До Part B требуется фактическая проверка источников доступа к `81`. Если inter-VLAN routing позволяет доступ не-management сетям, применить узкое source restriction только для NPM admin port (management subnet `192.168.0.0/24`) и отдельно проверить, что Docker NAT не обходит это ограничение. Это не должно превращаться в общий firewall redesign.

PASS для admin UI означает одновременно:

```text
192.168.0.0/24 → :81 = reachable
WAN             → :81 = not reachable
Guest/other VLAN→ :81 = not reachable, если они маршрутизируются к host
```

Admin account после первого запуска должен быть заменён на собственные credentials.

Если текущая NPM-версия позволяет — включить 2FA для административной учётной записи.

Пароли, recovery codes, private keys и credentials в отчёт не включать.

## A4. Backup model

До Part B должен существовать простой backup NPM:

```text
compose/configuration
+
NPM /data
+
NPM /etc/letsencrypt
```

Контейнер рассматривается как replaceable.

Persistent NPM state — как infrastructure data.

NPM использует SQLite, поэтому обычный файловый snapshot live `/data/database.sqlite` сам по себе **не считается application-consistent backup**. До Part B должен существовать отдельный NPM-aware backup в существующей backup infrastructure, рекомендуемый target:

```text
/srv/backups/app-data/npm/
```

Минимально backup должен включать:

```text
compose/configuration
consistent SQLite copy
/data persistent state excluding only explicitly disposable runtime artifacts
/etc/letsencrypt
manifest with NPM image tag + digest
```

Consistency rule:

```text
raw rsync/cp live database без consistency mechanism = NOT ACCEPTED
```

Допустимые варианты:

1. SQLite backup API / equivalent consistent online copy;
2. краткий controlled stop NPM → copy persistent state → start NPM (допустимо до Part B, пока NPM не является public Edge).

До cutover выполнить restore-smoke из этого backup в отдельный temporary path/temporary ports либо иным способом, не затрагивающим production listeners.

```text
NPM_BACKUP_CONSISTENCY = PASS
NPM_RESTORE_SMOKE      = PASS
```

После Part B recurring NPM backup должен быть интегрирован в production backup policy отдельно от общего system snapshot.

## A5. Inventory существующих public hostnames

До создания Proxy Hosts исполнитель должен определить **точные FQDN**, а не угадывать их из названий:

```text
1. Captive Portal
2. Cloud
3. VPN
```

Для каждого зафиксировать:

```text
FQDN
current public DNS A
current public DNS AAAA, если существует
CAA, если существует
current Hestia backend IP
current HTTP behavior
current HTTPS behavior
current certificate issuer/expiry
redirect HTTP→HTTPS
WebSocket requirement
upload/body-size requirement
special timeout requirement
special headers
```

Отдельно подтвердить:

> `VPN` в данном TASK означает HTTP/HTTPS web resource.

Если под `VPN` имеется в виду непосредственно VPN transport по UDP/TCP, а не web UI:

```text
VPN WEB MIGRATION = HOLD/OUT OF SCOPE
```

Не пытаться автоматически превращать его в HTTP Proxy Host.

## A6. Создание трёх Proxy Hosts

Создать в NPM три Proxy Host **до переключения Cisco**.

Первоначально все они должны смотреть на Hestia:

```text
Captive Portal FQDN
    ↓
Hestia internal IP :443

Cloud FQDN
    ↓
Hestia internal IP :443

VPN FQDN
    ↓
Hestia internal IP :443
```

Initial upstream scheme:

```text
HTTPS
```

а не HTTP.

Причина: на Hestia сейчас уже существуют SSL/Force-SSL semantics. Мы **не хотим одновременно с миграцией Edge менять Hestia redirect behavior**.

Таким образом после cutover:

```text
Browser
   ↓ HTTPS / new NPM certificate
NPM
   ↓ HTTPS / current Hestia configuration
Hestia
```

Это временная двойная TLS-секция, специально выбранная для минимального изменения существующего Hestia runtime.

## A7. Очень важное правило upstream

В `Forward Hostname/IP` использовать:

```text
Hestia internal LAN IP
```

или отдельное internal имя, которое гарантированно резолвится непосредственно в Hestia.

**НЕ использовать публичный FQDN сайта как upstream.**

Иначе возможно:

```text
NPM
 ↓
public FQDN
 ↓
Cisco/NAT
 ↓
NPM
 ↓
loop
```

### A7.1. HTTPS upstream SNI — обязательный gate

Так как initial upstream использует `HTTPS` и `Forward Hostname/IP` может быть raw internal IP, одного HTTP `Host` header недостаточно гарантировать корректный TLS virtual host на Hestia: SNI выбирается **до** HTTP request.

До Part B для каждого hostname проверить, какой SNI реально отправляет NPM upstream.

Требуемый результат:

```text
HTTP Host header = public FQDN нужного ресурса
TLS SNI          = тот же public FQDN
TCP destination  = Hestia internal LAN IP:443
```

Если текущая NPM template не отправляет нужный SNI при upstream по IP, разрешён минимальный per-host Advanced override:

```nginx
proxy_ssl_server_name on;
proxy_ssl_name $host;
```

Не добавлять другие Advanced directives «заодно».

Если Host/SNI невозможно воспроизвести однозначно:

```text
PART B = HOLD
```

## A8. HTTP semantics

NPM обязан сохранить исходные:

```text
Host
URI/path
query string
X-Forwarded-For
X-Forwarded-Proto
X-Real-IP / equivalent client-address chain
```

Не добавлять на первой стадии:

```text
caching
authentication
Access Lists
URL rewrites
new redirects
WAF-like rules
custom security rules
```

если это не требуется для воспроизведения уже существующего поведения.

Цель первого cutover:

> **сменить Edge, а не одновременно изменить поведение сайтов.**

## A9. Captive Portal — отдельное требование

Для Captive Portal запрещены случайные:

```text
URI rewrites
query stripping
redirect modifications
authentication layer in NPM
caching
```

До Part B нужно проверить также NPM access logging.

Если URL Captive Portal содержит чувствительные client identifiers / MAC / session identifiers / token-like query values, нельзя молча создать новый persistent access-log с этими значениями.

Если стандартное NPM logging нарушает действующую privacy boundary:

```text
PART B = HOLD
```

до решения logging policy.

Проверку privacy делать не только по конфигурации, но и фактическим synthetic request с заведомым canary query value. После запроса проверить NPM persistent logs и container logs. Canary не должен сохраняться там, где policy запрещает query/session identifiers.

Если требуется отключение/изменение access logging для Captive Portal, оно должно быть минимальным и документированным. Одновременно определить retention/rotation для persistent NPM logs, чтобы `/data/logs` не рос без ограничений.

## A10. Предварительная проверка без production cutover

Через LAN провести проверку маршрутизации NPM с правильным `Host`:

```text
NPM
 ↓
Hestia
 ↓
правильный virtual host
```

Для каждого из трёх hostname подтвердить, что запрос попадает именно в нужный Hestia resource.

Проверка должна идти не только с самого host, но и через фактический NPM container path:

```text
client on management LAN
 ↓ request to 192.168.0.99 with correct Host/SNI
NPM container
 ↓ HTTPS to Hestia internal IP:443
Hestia correct virtual host
```

До Part B отдельно подтвердить:

```text
Docker container → Hestia:443 reachability = PASS
Host preservation                         = PASS
Query preservation                        = PASS
Upstream TLS/SNI                          = PASS
No redirect loop                          = PASS
```

На этой стадии:

```text
Cisco NAT = НЕ МЕНЯТЬ
DNS       = НЕ МЕНЯТЬ
Hestia SSL = НЕ МЕНЯТЬ
Hestia certificates = НЕ УДАЛЯТЬ
```

### PART A PASS criteria

```text
NPM running = PASS
restart policy = PASS
image tag = PASS
image digest captured = PASS

80 listener = PASS
443 listener = PASS
81 management-only enforcement = PASS
IPv6 exposure review = PASS

persistent /data = PASS
persistent /etc/letsencrypt = PASS
backup path = PASS
NPM backup consistency = PASS
NPM restore smoke = PASS

Captive Portal → Hestia routing = PASS
Cloud → Hestia routing = PASS
VPN web → Hestia routing = PASS/OUT
upstream Host/SNI = PASS
container → Hestia reachability = PASS

Captive Portal log privacy = PASS
NPM log rotation/retention = PASS

Cisco production unchanged = PASS
Hestia production unchanged = PASS

PART_A = PASS
PART_B = HOLD UNTIL OWNER CUTOVER GO
```

---

# PART B — CUTOVER CISCO → NPM И ПЕРЕВЫПУСК TLS-СЕРТИФИКАТОВ

Это короткое production change window.

Расчётное maintenance window:

```text
до 60 минут
```

Но Captive Portal является приоритетом №1.

Если Captive Portal нельзя вернуть в полностью рабочее состояние в разумный короткий срок после переключения, **не тратить весь час на live debugging — rollback на Hestia**.

## B1. Перед переключением

Непосредственно перед mutation сохранить evidence:

```text
current Cisco NAT 80 rule
current Cisco NAT 443 rule

Hestia HTTP reachable
Hestia HTTPS reachable

Captive Portal current functional state
Cloud current state
VPN web current state

current Hestia certificate metadata
NPM container state
NPM listeners
NPM backup
NPM image digest
NPM admin-port exposure check
NPM upstream Host/SNI preflight
```

Непосредственно перед cutover дополнительно:

```text
run one manual CaptivProd system backup = PASS
run one fresh NPM-aware backup          = PASS
verify latest pointers/manifests        = PASS
```

Никакие private keys в evidence не выводить.

## B2. DNS preflight

DNS **не должен меняться** при этой миграции.

До переключения убедиться:

```text
A records → current public WAN IP
```

Если существует `AAAA`, убедиться, что IPv6 не позволяет клиентам обходить новый NPM.

Если есть restrictive CAA — убедиться, что Let's Encrypt разрешён.

Не начинать cutover при неизвестной DNS-картине.

## B3. Единственное сетевое переключение

На Cisco изменить destination существующего HTTP/HTTPS ingress:

```text
БЫЛО:

WAN TCP 80  → Hestia
WAN TCP 443 → Hestia
```

на:

```text
СТАЛО:

WAN TCP 80  → captiv-prod / NPM :80
WAN TCP 443 → captiv-prod / NPM :443
```

Другие NAT/ACL/routing правила не менять «заодно».

В момент переключения зафиксировать точный `CUTOVER_START`. Для Captive Portal вводится hard rollback guardrail:

```text
если CAPTIVE_PORTAL_E2E != PASS в течение 15 минут после CUTOVER_START
→ rollback Cisco 80/443 обратно на Hestia
```

Продление допускается только явным Owner GO при наличии понятной причины и подтверждения, что recovery/certificate issuance реально продвигается.

## B4. Captive Portal — ПЕРВЫМ

Сразу после переключения Cisco:

```text
NPM
→ Captive Portal Proxy Host
→ Request new Let's Encrypt certificate
```

Не переносить private key старого Hestia-сертификата.

**Выпустить новый сертификат на NPM.**

После успешной выдачи:

```text
certificate → selected
Force SSL   → enabled
```

если это соответствует текущей public semantics.

Hestia certificate:

```text
НЕ удалять
НЕ отключать
НЕ менять
```

Он остаётся:

1. backend TLS certificate;
2. быстрым rollback path.

## B5. Captive Portal acceptance

Недостаточно:

```text
HTTP 200
```

Проверить полный критичный путь:

```text
public DNS
 ↓
Cisco
 ↓
NPM
 ↓ TLS
Hestia
 ↓
Captive Portal
 ↓
Omada authorization
 ↓
real client receives Internet access
```

Проверить минимум:

```text
valid public certificate
correct hostname/SAN
no browser certificate warning
HTTP → HTTPS correct
portal page opens
query parameters preserved
redirects correct
real test guest reaches Portal
authorization completes
Omada-side effect occurs
client gets expected network access
no redirect loop
no obvious client-IP regression
upstream Host/SNI correct
no sensitive query/session leakage into forbidden persistent logs
```

### Critical gate

```text
CAPTIVE_PORTAL_E2E = PASS
```

только после этого переходить к Cloud и VPN.

## B6. Cloud

После PASS Captive Portal:

```text
Cloud Proxy Host
→ request new Let's Encrypt certificate
→ enable public HTTPS
→ validate
```

Проверить не только главную страницу.

Если применимо:

```text
login
upload
download
large file
WebDAV/API
WebSocket
redirects
real client IP
```

Никакие новые ограничения upload size/timeouts не должны появиться из-за NPM.

## B7. VPN web resource

После Cloud:

```text
VPN web Proxy Host
→ new Let's Encrypt certificate
→ public HTTPS
→ functional smoke
```

Если выясняется, что hostname обслуживает не HTTP/HTTPS web UI, а собственно VPN transport:

```text
STOP that subtask
```

Не переделывать архитектуру внутри этого maintenance window.

## B8. Что означает «переезд сертификатов»

В рамках этого TASK:

```text
НЕ:
copy Hestia private keys → NPM

А:
issue fresh Let's Encrypt certificates → NPM
```

После cutover владельцем public TLS становится:

```text
NPM
```

Hestia certificates остаются временно существовать для:

```text
NPM → Hestia internal HTTPS
+
rollback
```

Их удаление/отключение **не входит в этот TASK**.

## B9. Rollback

Rollback должен быть возможен **одним сетевым действием**:

```text
Cisco:

WAN 80  → обратно Hestia
WAN 443 → обратно Hestia
```

Поскольку в рамках cutover:

```text
DNS не менялся
Hestia не демонтировалась
Hestia certificates не удалялись
Hestia vhosts не удалялись
```

после возврата NAT должна восстановиться исходная архитектура:

```text
Internet
 ↓
Cisco
 ↓
Hestia
```

NPM при rollback можно оставить установленным.

Не удалять новые NPM certificates в аварийном порядке.

После возврата NAT rollback не считается завершённым только по факту изменения Cisco. Минимально подтвердить:

```text
public HTTPS → Hestia = PASS
Captive Portal smoke  = PASS
Cloud smoke           = PASS
VPN web smoke         = PASS/OUT
```

После этого зафиксировать `ROLLBACK_END`.

## B10. Финальный accepted state

После успешного TASK:

```text
                    INTERNET
                       │
                       ↓
                    CISCO
                  TCP 80/443
                       │
                       ↓
              NGINX PROXY MANAGER
                 on captiv-prod
                 │     │     │
                 │     │     │
                 ↓     ↓     ↓
              Portal Cloud  VPN
                 \     |     /
                  \    |    /
                     HESTIA
```

Public:

```text
TLS owner = NPM
HTTP/HTTPS ingress owner = NPM
```

Transitional internal backend:

```text
NPM → HTTPS → Hestia
```

---

# ЯВНО OUT OF SCOPE

Не выполнять в этом TASK:

```text
NPM → CaptivPortal direct backend
NPM → Cloud direct backend
NPM → VPN direct backend

удаление proxy rules из Hestia
удаление SSL из Hestia
перенос Hestia
изменение application code CaptivPortal
изменение Omada
замена DNS provider
HA / standby NPM
UPS work
новые firewall/security policies
новый WAF
NPM clustering
MariaDB/PostgreSQL for NPM
```

Это защищает первый переход от «заодно».

---

# ОТЧЁТ ИСПОЛНИТЕЛЯ

После **Part A** вернуть:

```text
TASK=TASK-CAPTIVPROD-EDGE-NPM-01

NPM_VERSION=
NPM_IMAGE_DIGEST=
DOCKER_VERSION=
COMPOSE_VERSION=
COMPOSE_PATH=

NPM_DATA_PATH=
NPM_LETSENCRYPT_PATH=
BACKUP_PATH=

PORT_80=
PORT_443=
PORT_81=
ADMIN_UI_BIND=
ADMIN_UI_SCOPE=
IPV6_EXPOSURE_REVIEW=

HESTIA_INTERNAL_TARGET=
UPSTREAM_HOST_SNI_PREFLIGHT=

PORTAL_FQDN=
CLOUD_FQDN=
VPN_FQDN=

PORTAL_PROXY_PREFLIGHT=
CLOUD_PROXY_PREFLIGHT=
VPN_PROXY_PREFLIGHT=

SENSITIVE_ACCESS_LOG_REVIEW=
NPM_BACKUP_CONSISTENCY=
NPM_RESTORE_SMOKE=
NPM_LOG_RETENTION=

PART_A=
PASS / HOLD

PRODUCTION_CHANGES=
NONE
```

После **Part B** вернуть:

```text
CUTOVER_START=
CUTOVER_END=
PORTAL_ROLLBACK_DEADLINE=

CISCO_80_TARGET=
CISCO_443_TARGET=

PORTAL_CERTIFICATE=
PASS / FAIL

PORTAL_E2E=
PASS / FAIL

CLOUD_CERTIFICATE=
PASS / FAIL

CLOUD_FUNCTIONAL=
PASS / FAIL

VPN_CERTIFICATE=
PASS / FAIL / OUT

VPN_FUNCTIONAL=
PASS / FAIL / OUT

ROLLBACK_READY=
YES / NO

ROLLBACK_USED=
YES / NO

FINAL_PUBLIC_EDGE=
NPM

FINAL_PUBLIC_TLS_OWNER=
NPM

HESTIA_PRESERVED=
YES / NO

OPEN_ISSUES=
```

Секреты, passwords, tokens и private keys в отчёт **не включать**.

---

# REVISION NOTES — v2

Добавлено после SysAdmin review:

1. immutable image evidence через digest;
2. explicit Docker restart/log rotation и запрет privileged/host-network/docker.sock;
3. реальное enforcement для NPM admin `:81`, а не только отсутствие WAN NAT;
4. NPM-aware consistent SQLite backup + restore smoke;
5. обязательная проверка HTTPS upstream SNI при Hestia upstream по internal IP;
6. preflight именно через container network path;
7. synthetic canary test для privacy/access-log boundary и log retention;
8. manual system + NPM backup непосредственно перед cutover;
9. 15-minute rollback guardrail для Captive Portal;
10. post-rollback functional verification.

---

# FINAL STATUS

```text
TASK=
TASK-CAPTIVPROD-EDGE-NPM-01

PART_A=
INSTALL / PREPARE / VERIFY

PART_B=
CONTROLLED PRODUCTION CUTOVER / TLS REISSUE

APPLICATION CODE CHANGE=
NONE

DNS CHANGE=
NONE

HESTIA REMOVAL=
NO

DIRECT BACKEND MIGRATION=
OUT OF SCOPE

ROLLBACK=
CISCO 80/443 → HESTIA

PRODUCTION CHANGE BEFORE PART_A PASS=
NO
```
