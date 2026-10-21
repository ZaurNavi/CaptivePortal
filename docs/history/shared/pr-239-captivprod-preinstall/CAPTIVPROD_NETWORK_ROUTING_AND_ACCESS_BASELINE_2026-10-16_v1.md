# CAPTIV-PROD — маршрутизация, ingress/egress и правила доступа

**Документ ID:** `CAPTIVPROD-NET-ROUTING-BASELINE-20261016`  
**Версия:** `1.0`  
**Дата снимка:** 16.10.2026, около 16:30–16:37 UTC / 20:30–20:37 Asia/Baku  
**Статус:** `LIVE / READ-ONLY / AS-IS`  
**Целевой узел:** `captiv-prod`, Ubuntu 22.04, `192.168.0.99`  
**Назначение:** воспроизводимый источник фактических маршрутов, сетевых границ, firewall/NAT/Docker/NPM и связи с Cisco для следующей проверки после миграции всех AP.

> **Важное правило чтения:** этот документ фиксирует **наблюдаемую конфигурацию**, а не универсальное разрешение на её изменение. `LISTEN` не означает, что порт доступен с любого адреса: между клиентом и приложением действуют маршруты, ACL Cisco, NAT, Linux netfilter, Docker и механизмы Omada. Если трафик не прошёл конкретную E2E-проверку, он обозначен как «настроен/разрешён правилами», а не как гарантированно работающий.

## 1. Резюме архитектуры

- `Cisco 3845 (192.168.0.1)` — L3-шлюз VLAN 10/20/30/60, DHCP, DNS, межсетевые ACL, NAT/PAT и upstream по `192.168.100.1`.
- `Cisco Catalyst 2960S` — L2 trunk для AP и Cisco, включая tagged VLAN 60; отдельные SPAN/RSPAN потоки.
- `captiv-prod (192.168.0.99)` — отдельный физический сервер с management NIC `enp2s0`, SPAN NIC `enp3s0`, NPM в Docker, новым Portal и новой Omada.
- Единственный общий публичный HTTP/HTTPS ingress по наблюдаемому статическому NAT Cisco: **TCP 80/443 → 192.168.0.99 → Docker NPM → upstream по Host/FQDN**.
- Новый Portal доступен NPM **не напрямую на `192.168.0.99:8088`**, а по защищённому внутреннему пути `172.18.0.2 (NPM) → 172.18.0.1:18089 (Portal)`.
- Omada Linux работает на том же узле; имя `Omada` локально разрешается в `127.0.0.1`. Управляющие AP-соединения из четырёх конкретных IP разрешены узкими правилами на TCP 29814/UDP 29810.
- Новый гостевой контур — VLAN 60 `10.50.0.0/19`; старый Guest — VLAN 20 `192.168.8.0/22`. Их DHCP Option 114 указывает на **разные** CAPPORT endpoints.
- Существующий старый Portal (`192.168.0.202`) и старый Windows Omada (`192.168.0.222`) продолжают иметь собственные ingress/управляющие маршруты. Переключение всех AP в этом снимке **не подтверждается**.

### 1.1 Схема потоков (логическая)

```text
                             Internet / DDNS
                                     |
                            upstream network
                                     |
                       Cisco 3845 Gi0/0 (192.168.100.10)
                        PAT, static port forwards, ACL
                                     |
                       Cisco 3845 Gi0/1.<VLAN>
                                     |
                          Catalyst 2960S trunk
                       +-------------+--------------+
                       |                            |
       Management VLAN10 (192.168.0.0/24)   Guest VLAN60 (10.50.0.0/19)
                       |                            |
           captiv-prod: enp2s0 .99            AP/Guest Wi-Fi
                       ^                            |
                       +---- DNS/CAPPORT/HTTPS -----+
                       |
                 TCP 80/81/443
                       |
                 Docker DNAT / NPM
                 172.18.0.2/16
                   |       |\
                   |       | +-- other proxy hosts → .202 / .220
                   |       |
                   |       +-- new Portal → 172.18.0.1:18089 (NET-01 guard)
                   |
       new Omada on host, localhost:8043; AP TCP 29814 / UDP 29810

  SPAN path, not IP route: Catalyst VLAN60 -> SPAN Gi1/0/45 -> sensor NIC
  enp3s0 (promiscuous, no IPv4 address) -> Suricata / Fingerprint Sensor
```

Схема отражает функциональные связи; **точная физическая трассировка кабеля** `Gi1/0/45 ↔ enp3s0` в рамках этого read-only снимка отдельно не доказывалась.

## 2. Linux host: интерфейсы, маршруты и forwarding

### 2.1 Интерфейсы

| Interface | Адрес/режим | Назначение | Наблюдение |
|---|---|---|---|
| `lo` | `127.0.0.1/8` | Host-local, локальное обращение к Omada | UP |
| `enp2s0` | `192.168.0.99/24`, MAC `3c:52:82:61:03:76` | Management/LAN, Linux routing, ingress/egress | UP |
| `enp3s0` | **IPv4 отсутствует**, MAC `00:0a:cd:00:0c:ce` | Изолированный SPAN/sensor receive | UP, PROMISC |
| `docker0` | `172.17.0.1/16` | Docker default bridge | Link down, нет активных членов в проверенном контейнерном составе |
| `br-627e7c1ca6d5` | `172.18.0.1/16` | Docker bridge NPM | UP |
| `veth34fed87` | виртуальная L2-пара | Соединение bridge ↔ контейнер | UP |

### 2.2 IPv4 main routing table — фактический снимок

```text
default via 192.168.0.1 dev enp2s0 proto static
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown
172.18.0.0/16 dev br-627e7c1ca6d5 proto kernel scope link src 172.18.0.1
192.168.0.0/24 dev enp2s0 proto kernel scope link src 192.168.0.99
```

IPv4 policy rules: `local` (priority 0), `main` (32766), `default` (32767). **Дополнительных `ip rule`/policy-routing таблиц для guest-подсетей не обнаружено.**

**Следствия:**

- `192.168.0.202`, `.220`, `.222` — соседние адреса on-link через `enp2s0`.
- `10.50.0.0/19` (VLAN 60), `192.168.8.0/22` (VLAN 20) и внешние IP — через gateway `192.168.0.1`.
- `172.18.0.2` (NPM) — локальный Docker bridge, без выхода через Cisco для общения с хостом на `172.18.0.1`.
- `enp3s0` не имеет IPv4-подсети и не участвует в этой таблице маршрутизации.

Проверка route lookup: `10.50.0.50 → via 192.168.0.1, enp2s0`; `192.168.0.202 → enp2s0`; `8.8.8.8 → via 192.168.0.1`.

`net.ipv4.ip_forward=1` (необходим для Docker/NAT); `rp_filter` `all=2`, `enp2s0=2` (loose). Это **не равно отсутствию firewall**: IP forwarding ограничен независимыми FORWARD/DOCKER правилами. Отдельного IPv6 default route в момент снимка не было; были только loopback и link-local маршруты.

## 3. Cisco 3845: L3 VLAN, upstream, NAT и ACL

### 3.1 Connected сети и next hop

| Cisco interface | IP / подсеть | Роль |
|---|---|---|
| `Gi0/1.10` | `192.168.0.1/24` | Home/Management VLAN 10 |
| `Gi0/1.20` | `192.168.10.1/22` (`192.168.8.0/22`) | Legacy Guest VLAN 20 |
| `Gi0/1.30` | `192.168.3.1/24` | Camera VLAN 30 |
| `Gi0/1.60` | `10.50.0.1/19` (`10.50.0.0/19`) | Новый Guest VLAN 60 |
| `Gi0/0` | `192.168.100.10/24` | Upstream, `ip nat outside` |

Все перечисленные `Gi0/1` подинтерфейсы — `up/up` при проверке. Маршрут по умолчанию Cisco:

```text
ip route 0.0.0.0 0.0.0.0 192.168.100.1
```

Дополнительный статический маршрут Cisco (не относится к Portal непосредственно): `10.192.1.0/24 via 192.168.0.220`. **На сервере `.99` этот маршрут не повторяется**: трафик иных подсетей направляется на `.1`.

### 3.2 WAN ingress — статические port forwards на Cisco

| Внешний TCP/UDP порт на `Gi0/0` | Destination | Назначение / статус |
|---|---|---|
| TCP 80 | `192.168.0.99:80` | Общий NPM HTTP ingress |
| TCP 443 | `192.168.0.99:443` | Общий NPM HTTPS ingress |
| UDP 29810 | `192.168.0.222:29810` | **Старая** Windows Omada, оставленный внешний discovery forward |
| TCP 29814 | `192.168.0.222:29814` | **Старая** Windows Omada, оставленный внешний management forward |
| TCP+UDP 6881 | `192.168.0.220:6881` | Другая служба файлового/NAS узла |
| UDP 51820, 51821 | `192.168.0.220` | Другая служба/VPN узла |

Это **только конфигурация NAT на Cisco**; внешний путь дополнительно зависит от upstream оборудования и публичного адреса. Приведённые Omada-forward'ы не направляют внешние AP на новую Omada `.99`. Пилотная AP управлялась новой Omada из management VLAN 10, то есть локальным путём — **не через эти внешние NAT-forward'ы**. В этой работе Cisco NAT **не изменялся**.

Общий PAT:

```text
ip nat inside source list 100 interface GigabitEthernet0/0 overload
```

ACL 100 в момент проверки содержит `permit ip ... any` для источников:

- `192.168.0.0/24` (VLAN 10);
- `192.168.8.0/22` (VLAN 20);
- `192.168.3.0/24` (VLAN 30);
- `10.50.0.0/19` (VLAN 60).

**Важно:** NAT ACL 100 определяет источники PAT, а **не заменяет входной security ACL** `CAPTIVPROD_GUEST_V60_IN`.

### 3.3 Входной Cisco ACL гостевой VLAN 60

На `Gi0/1.60` проверен `ip access-group CAPTIVPROD_GUEST_V60_IN in`. Существенные правила в порядке выполнения:

| Seq | Источник / назначение / протокол | Результат |
|---:|---|---|
| 10 | DHCP client UDP 68 → server UDP 67 | PERMIT |
| 20, 30 | `10.50.0.0/19 → 192.168.0.1:53` UDP/TCP | PERMIT (DNS Cisco) |
| 40 | `10.50.0.0/19 → 192.168.0.1:123` UDP | PERMIT (NTP) |
| 50 | `10.50.0.0/19 → 192.168.0.99:443` TCP | PERMIT (новый Portal через NPM) |
| 60 | `10.50.0.0/19 → 10.50.0.1`, ICMP echo | PERMIT |
| 70, 80 | DNS к прочим адресам UDP/TCP 53 | DENY |
| 90 | NTP к прочим адресам UDP 123 | DENY |
| 100–160 | Частные/reserved сети (`10/8`, `172.16/12`, `192.168/16`, CGNAT, link-local, loopback, multicast) | DENY (после названных исключений) |
| 170 | `10.50.0.0/19 → any` | PERMIT (остальной трафик, включая интернет с PAT) |

**Ключевой порядок:** исключение `10.50.0.0/19 → 192.168.0.99:443` находится **выше** запрета `192.168.0.0/16`. Поэтому разрешён ровно HTTPS на NPM/Portal, но не произвольное управление сервером из VLAN 60. Здесь описан **L3 путь на Cisco**, не состояние авторизации посетителя в Omada.

Legacy VLAN 20 использует на `Gi0/1.20` входной `GUEST_TTL_FILTER`: `deny ip any any ttl eq 62 log`, `deny ... ttl eq 126 log`, затем `permit ip any any`. В этом проверенном ACL **нет тех же частных-сетевых запретов VLAN 60**; не приписывать ему политику VLAN 60.

## 4. DNS, DHCP и CAPPORT — контроль направлений

### 4.1 DNS

Гостям VLAN 60 DHCP сообщает DNS `192.168.0.1` (Cisco). Cisco DNS-server включён, upstream DNS в `running-config`: `8.8.8.8`, `77.88.8.8`.

Локальные статические записи **сохранены отдельно**:

```text
captivprod-navi.duckdns.org   → 192.168.0.99   (new Portal)
captivportal-navi.duckdns.org → 192.168.0.202  (legacy Portal)
```

Эти ответы были перепроверены запросом `dig @192.168.0.1` в ходе снимка. Смысл split DNS для VLAN 60: клиент обращается по штатному HTTPS/FQDN **локально к `.99`**, без ненужного hairpin через внешний публичный IP, чтобы новый CAPPORT видел корректного гостевого клиента. Предыдущее наблюдение при публичном разрешении имени — `403 client_not_allowed`; в текущем снимке **полный guest E2E повторно не запускался**.

### 4.2 DHCP

| Параметр | Legacy VLAN 20 | New VLAN 60 |
|---|---|---|
| Pool | `Guest` | `CAPTIVPROD_GUEST_V60` |
| Subnet | `192.168.8.0/22` | `10.50.0.0/19` |
| Gateway | `192.168.10.1` | `10.50.0.1` |
| DNS | `192.168.0.1` | `192.168.0.1` |
| NTP option 42 | Не зафиксирован в этом pool | `192.168.0.1` |
| DHCP Option 114 | `https://captivportal-navi.duckdns.org/capport/api` | `https://captivprod-navi.duckdns.org/capport/api` |
| Lease | 20 минут | 20 минут |

Наличие DHCP Option 114 **не назначает SSID нужному VLAN**. VLAN-tag SSID определяется настройкой новой Omada/AP и L2 trunk. Ранее пилотному гостю уже выдавался адрес `10.50.0.50` после изменения SSID VLAN — это исторический результат текущей сессии, **не повторный полевой E2E-тест в этом снимке**.

## 5. Docker/NPM: границы public ingress и внутренний backend

### 5.1 Актуальная Docker сеть

```text
Container:        npm
Image:            jc21/nginx-proxy-manager:2.16.0
Network:          nginx-proxy-manager_default
Bridge:           br-627e7c1ca6d5
Bridge gateway:   172.18.0.1/16
NPM container IP: 172.18.0.2/16
NPM container MAC: b2:fa:fc:bf:d5:bc
Host ports:       192.168.0.99:80, :81, :443
```

Docker DNAT на хосте переводит `192.168.0.99:{80,81,443}` → `172.18.0.2:{80,81,443}`. Дополнительно действует Docker POSTROUTING masquerade для `172.18.0.0/16` при выходе за пределы bridge. **У NPM нет доступа к физическому NIC без Docker bridge**, по фактической топологии он один контейнер в этом network.

### 5.2 Proxy Hosts (фактические upstream'ы из конфигов)

| NPM proxy host | Публичный Host/FQDN | Внутренний upstream | Замечание |
|---|---|---|---|
| `1.conf` | `captivportal-navi.duckdns.org` | `http://192.168.0.202:18088` | Старый Portal |
| `2.conf` | `navi-cloud.duckdns.org` | `http://192.168.0.202:8082` | Cloud, старый узел |
| `3.conf` | `vpn-navi.duckdns.org` | `http://192.168.0.220:51822` | VPN-related web upstream |
| `4.conf` | `captivprod-navi.duckdns.org` | `http://172.18.0.1:18089` | Новый Portal |

Все четыре server-конфига прослушивают HTTP 80 и HTTPS 443 внутри NPM, включают SSL certificate references и Force SSL. Это **виртуальные хосты по имени**, а не четыре отдельные публичные IP. Указанные upstream-протоколы именно **HTTP на внутреннем участке**, а TLS завершается на NPM.

### 5.3 Административная панель NPM

Host port `192.168.0.99:81` — NPM Admin UI. В `DOCKER-USER` есть два правила с match по **original destination** `192.168.0.99:81`:

1. `192.168.0.0/24` → ACCEPT;
2. прочие источники на этот original destination → REJECT TCP reset.

Это ограничение **отдельно** от HTTPS/80/443 публичных Proxy Hosts. Docker's `FORWARD` default policy = DROP, далее работают `DOCKER-USER` и `DOCKER-FORWARD`. Нельзя интерпретировать открытый Docker listener порта 81 как публичный доступ отовсюду.

### 5.4 NET-01: защищённый путь к новому Portal

Portal (`captive-portal.service`, установленный checkout `/opt/captivprod-portal-v2fix`) слушает `172.18.0.1:18089`, не `0.0.0.0:8088` и не `192.168.0.99:18089`.

Guard `CAPTIV_FLASK_18089` в Linux INPUT:

- **ACCEPT** только TCP на `172.18.0.1:18089` с `172.18.0.2/32` через `br-627e7c1ca6d5`, при совпадении источника MAC `b2:fa:fc:bf:d5:bc`, `conntrack NEW/ESTABLISHED`;
- **ACCEPT** специально ограниченный local-host/loopback путь с source и dest `172.18.0.1`;
- остальные TCP на `18089` → **REJECT TCP reset**.

Дополнительный OUTPUT guard `CAPTIV_SENSOR_OUT_18089` разрешает локальный `172.18.0.1 → 172.18.0.1:18089` только при UID `998` и `-o lo`; остальные совпадающие исходящие TCP пакеты отклоняет. **UID не следует переименовывать по догадке:** правило определено по числовому владельцу.

`raw/PREROUTING` запрещает прямой вход к IP контейнера `172.18.0.2`, если пакет пришёл **не** со стороны Docker bridge. IPv6 INPUT отдельно отклоняет TCP 18089. Проверка встроенным verifier: `DOCKER_IDENTITY=PASS`, `FIREWALL_FAIL_CLOSED=PASS`.

## 6. Новая Omada: локальный API и AP management plane

### 6.1 Listener и доступ к веб-интерфейсу

Omada Linux `tpeap.service`, `jsvc`, слушает на host следующие проверенные порты:

| Transport | Port | Роль / доступ |
|---|---:|---|
| TCP | 8043, 8088, 8843 | Omada web/API/portal listeners; Linux `CAPTIV_OMADA_GUARD` допускает **только source `192.168.0.0/24`** на хосте `.99`, остальные отклоняет |
| TCP | 29811–29816 (включая 29814) | Device management/adoption; общий host guard блокирует 29811–29817 **кроме** узких исключений TCP 29814 |
| UDP | 29810, 27001, 19810 | Omada discovery; общий host guard блокирует указанные порты **кроме** узких исключений UDP 29810 |
| TCP | 27217 (`127.0.0.1`) | MongoDB Omada, loopback-only (не внешний listener) |

Техническое имя `Omada` на `captiv-prod` разрешается в `127.0.0.1`; Portal может обращаться к контроллеру локально по HTTPS `Omada:8043`. Из предыдущей проверки приложения подтверждена строгая TLS policy с проверкой trust anchor/SNI; **сетевые разрешения не означают отключения проверки сертификата**.

### 6.2 Узкие исключения для четырёх AP

На Linux `CAPTIV_OMADA_GUARD` **до** общих deny правил есть точные `RETURN` для **destination `192.168.0.99/32`**:

| AP management IP | AP MAC (подтверждённый ранее) | TCP 29814 | UDP 29810 |
|---|---|---|---|
| `192.168.0.80` | `0C-80-63-2F-FB-8D` | ALLOW | ALLOW |
| `192.168.0.70` | `28-EE-52-47-5C-38` | ALLOW | ALLOW |
| `192.168.0.60` | `DC-62-79-1B-4A-68` | ALLOW | ALLOW |
| `192.168.0.50` | `EC-75-0C-18-6F-F8` | ALLOW | ALLOW |

Остальным источникам соответствующие порты по-прежнему запрещены общими правилами (`29811:29817` TCP reject; `29810,27001,19810` UDP drop). ACL не даёт этим четырём IP универсального доступа ко всем портам Omada.

Правила записаны в постоянный startup-скрипт `/usr/local/sbin/captiv-omada-guard`, который исполняет `captiv-omada-guard.service` перед запуском Omada. Pilot AP `.80` была ранее принята новой Omada и установила TCP 29814; факт последующей успешности всех конфигурационных операций AP **не является частью этой сетевой инвентаризации**.

## 7. Catalyst 2960S: trunk, tagged VLAN 60, monitoring

### 7.1 Действующие trunk VLAN

| Switch port | Native VLAN | Allowed/forwarding VLAN | Роль |
|---|---:|---|---|
| `Gi1/0/1` | 1 | `10,20,30,50,60` | uplink в сторону Cisco/LAN |
| `Gi1/0/5` | 10 | `10,20,50,60` | AP MAC `28-EE-52-47-5C-38` (ранее подтверждено) |
| `Gi1/0/6` | 10 | `10,20,50,60` | AP MAC `0C-80-63-2F-FB-8D` |
| `Gi1/0/10` | 10 | `10,20,50,60` | AP MAC `DC-62-79-1B-4A-68` |
| `Gi1/0/15` | 10 | `10,20,50,60` | AP MAC `EC-75-0C-18-6F-F8` |
| `Gi1/0/48` | 40 | `40,999` | отдельный legacy RSPAN/trunk контур |

Native VLAN 10 на четырёх AP портах **не** менялся при добавлении tagged VLAN 60. Native VLAN uplink `Gi1/0/1` = **1**, отличен от native VLAN AP-портов; это не следует смешивать.

### 7.2 SPAN/RSPAN — это копирование, не маршрутизация

- **Session 1:** `Remote Source Session`, VLAN 20 `RX only` → RSPAN VLAN `999`. Legacy-monitoring path.
- **Session 2:** `Local Session`, VLAN 60 `both directions` → destination `Gi1/0/45`, encapsulation `Native`, ingress на SPAN destination disabled.
- На новом Linux `enp3s0` активен в promiscuous режиме **без IPv4 адреса**. Suricata, Fingerprint Sensor/Evidence units в момент проверки active.

SPAN кадры не являются IP-forwarding клиента через `.99`; `enp3s0` не является gateway VLAN 60, и его не нужно добавлять в default route.

## 8. Матрица разрешений: откуда → куда

| Поток | Решающий узел/правило | Результат по конфигурации |
|---|---|---|
| WAN/public HTTP(S) → новый/старый site по FQDN | Cisco static TCP 80/443 → `.99`, NPM Host-based routing | ROUTED, host определяется NPM |
| Guest VLAN 60 → DNS/NTP Cisco `.1` | Cisco `CAPTIVPROD_GUEST_V60_IN` 20–40 | PERMIT |
| Guest VLAN 60 → новый Portal `.99:443` | Cisco ACL 50; Docker NPM 443; NPM `4.conf`; NET-01 | PERMIT по L3 и настройке proxy; полный пользовательский E2E не измерялся в этом снимке |
| Guest VLAN 60 → `.99:81` (NPM Admin) | Cisco ACL 120; дополнительно DOCKER-USER original destination 81 | DENY |
| Guest VLAN 60 → `.99:8043`, `:29814`, `:22` | Cisco ACL 120 к `192.168/16` | DENY |
| Guest VLAN 60 → прочие RFC1918 | Cisco ACL 100–120 | DENY (с перечисленными выше исключениями) |
| Guest VLAN 60 → internet | Cisco ACL 170, затем PAT ACL 100 | PERMIT по маршрутизации/NAT; Omada authorization — отдельный уровень |
| NPM `.2` → host Portal `172.18.0.1:18089` | Docker bridge + MAC/IP/port NET-01 guard | ALLOW для проверенной identity |
| Другой источник → host TCP 18089 | CAPTIV_FLASK_18089 | REJECT (кроме строго определённого local UID path) |
| Home VLAN 10 → Omada `.99:8043/8088/8843` | Linux `CAPTIV_OMADA_GUARD` | ALLOW для source `192.168.0.0/24` |
| Внешний / не-management → Omada `.99:8043/8088/8843` | Linux `CAPTIV_OMADA_GUARD` | REJECT при достижении `.99` по `enp2s0` |
| AP `.80/.70/.60/.50` → Omada `.99:29814` TCP и `:29810` UDP | Linux per-IP/per-destination exception | ALLOW |
| Другой источник → Omada `.99:29811-29817`, UDP `29810/27001/19810` | Linux Omada guard | DENY |
| LAN → NPM Admin `.99:81` | DOCKER-USER | ALLOW для `192.168.0.0/24` |
| Иные источники → NPM Admin `.99:81` | DOCKER-USER | REJECT |
| Sensor SPAN traffic → `enp3s0` | Catalyst SPAN Session 2 | L2 copy; **не** IP-маршрутизация |
| Portal → Omada локально HTTPS | `Omada` = loopback, TCP 8043, строгая TLS policy | LOCAL PATH (из предыдущей интеграционной проверки) |

**Важная граница:** базовая Linux `iptables INPUT` policy в IPv4 = **ACCEPT**, а не общий DROP. Разрешения здесь обеспечиваются конкретными guards и ACL Cisco. Нельзя записывать в архитектуру тезис «все прочие входящие подключения на хост глобально запрещены». На уровне `ip6tables` INPUT также наблюдалась policy ACCEPT и отдельный REJECT TCP 18089, однако **публичный IPv6 ingress не проверялся**, а в маршрутах хоста отсутствовал IPv6 default route.

## 9. Что подтвердили живые проверки (evidence)

| Проверка | Результат |
|---|---|
| `ip -4 route`, `ip -4 rule`, `ip -4 route get` на `.99` | Default via `.1`, Docker bridge on-link, другие VLAN через `.1` |
| `ip -br addr` / `ip -d link` | `enp2s0` management, `enp3s0` PROMISC без IP |
| `docker ps`, `docker network inspect`, Docker NAT | NPM `.2`, bridge `.1`, host ports 80/81/443 |
| `/opt/nginx-proxy-manager/data/nginx/proxy_host/{1..4}.conf` | 4 конкретных FQDN → upstream mappings |
| `iptables -S INPUT/OUTPUT/FORWARD`, filter/nat/raw | NET-01, Omada guard, Docker Admin guard, NAT DNAT/MASQUERADE |
| NET-01 verifier | `DOCKER_IDENTITY=PASS`, `FIREWALL_FAIL_CLOSED=PASS` |
| `show ip route connected`, `show ip interface brief` на Cisco 3845 | VLAN 10/20/30/60 + upstream в статусе up/up |
| `show ip access-lists CAPTIVPROD_GUEST_V60_IN`, ACL 100 | Guest60 private deny/portal exceptions; PAT sources |
| Cisco NAT `show running-config` | 80/443 → `.99`; legacy Omada 29810/29814 → `.222` |
| `show interfaces trunk`, `show monitor session all` на Catalyst | AP trunk VLAN60 и SPAN/RSPAN Session 1/2 |
| `dig @192.168.0.1` для обоих Portal FQDN | Новый `.99`, старый `.202` |
| Services `systemctl is-active` | NPM/Docker, Omada, Portal, Sensor, Suricata, NET-01 units active (проверены соответствующие компоненты) |

Сбор выполнялся read-only по SSH. **Никаких** изменений NAT, firewall, Cisco, Omada, NPM, Portal, AP, сертификатов или доверенных узлов для создания этого документа не проводилось. Конфигурация может измениться позднее; результаты привязаны ко времени снимка.

## 10. Известные границы и темы для следующего сравнения

1. **Pilot versus full migration.** Четыре IP имеют firewall exceptions, но это **не доказательство миграции всех четырёх AP**. В будущем дополнить online/adopted inventory и независимые E2E-тесты по каждому AP/SSID.
2. **WAN Omada.** На Cisco остаются наружные port forwards Omada к старой `.222`; перед полным переносом потребуется отдельное решение по удалённым AP, если такие существуют. Самовольно переключать NAT нельзя.
3. **Внутренние права NPM.** NPM host `/81` ограничен source `/24`; backend `/18089` имеет identity-bound NET-01. При обновлении Docker/IP/MAC проверять соответствие правил; не ослаблять guards автоматически.
4. **Split DNS.** CAPPORT корректно работает только при сочетании SSID VLAN60, DHCP DNS `.1`, Option114 нового FQDN и разрешённого HTTPS `.99:443`. Публичный DNS путь может маскировать IP гостя из-за hairpin NAT; не расширять `CAPPORT_ALLOWED_CLIENT_NETWORKS` до WAN ради обхода.
5. **Linux INPUT policy.** Общая политика ACCEPT требует осознанного учёта открытых слушателей и upstream-периметра; нельзя утверждать полный host-wide default deny.
6. **IPv6.** В проверенном routing snapshot публичного IPv6 default route нет, но audit исходящих/входящих IPv6 сервисов за пределами этого снимка не проводился.
7. **SPAN.** Точность VLAN60 sensor coverage нужно оценивать независимо от успеха IP-маршрутизации. Наличие SPAN Session 2 и запущенного Suricata не доказывает полноту наблюдений.
8. **Обратный маршрут.** Путь `.99 → 10.50.0.0/19` идёт через Cisco `.1`; любые будущие host-specific guest routes должны подтверждаться `ip route get` и router route table, а не предполагаться.
9. **Конфигурация ≠ E2E.** Матрица описывает политику сети. Для полного acceptance дополнительно нужны DHCP lease, DNS answer с устройства, TLS/SNI, NPM ingress log, Portal CAPPORT response, Omada Hotspot auth и факт выхода в интернет — только с Owner-controlled устройством.

### Контрольный набор команд для следующего read-only snapshot

**Linux `.99`:**

```bash
ip -4 -br addr
ip -4 route show table main
ip -4 rule show
ip -4 route get 10.50.0.50
ip -d -br link
sysctl net.ipv4.ip_forward
sudo iptables -S INPUT
sudo iptables -S OUTPUT
sudo iptables -S FORWARD
sudo iptables -S CAPTIV_OMADA_GUARD
sudo iptables -S CAPTIV_FLASK_18089
sudo iptables -S CAPTIV_SENSOR_OUT_18089
sudo iptables -S DOCKER-USER
sudo iptables -t nat -S
sudo iptables -t raw -S
sudo ip6tables -S INPUT
sudo docker ps
sudo docker network inspect nginx-proxy-manager_default
sudo ss -lntup
sudo python3 /usr/local/libexec/captiv-net01/net01-verify.py --all
dig @192.168.0.1 captivprod-navi.duckdns.org A +short
```

**Cisco 3845:**

```text
show ip route connected
show ip interface brief
show running-config | include ^ip nat inside source
show running-config | include ^ip route
show ip access-lists CAPTIVPROD_GUEST_V60_IN
show access-lists 100
show running-config | section ^ip dhcp pool CAPTIVPROD_GUEST_V60
show running-config | section ^ip dhcp pool Guest
show running-config | include ^ip host captiv
```

**Catalyst 2960S:**

```text
show interfaces trunk
show monitor session all
show mac address-table vlan 10
show spanning-tree vlan 60
```

Дополнительный процессный и дисковый baseline — отдельный источник `CAPTIVPROD_OLD_VS_NEW_IO_BASELINE_2026-10-16_v1.md`. Не смешивать метрики I/O с сетевыми counters без привязки к одному и тому же интервалу времени/нагрузке.

---

## 11. Версионирование

| Версия | Дата | Изменение |
|---|---|---|
| `1.0` | `2026-10-16` | Первый live read-only AS-IS baseline по `.99`, Cisco 3845/2960S, NPM, NET-01, Omada и VLAN 60 после пилотной миграции AP |

**Источник истины:** живые команды на `captiv-prod` / Cisco в технической сессии 16.10.2026. Исторические проектные документы дают контекст, но не заменяют текущий `running-config` и правила netfilter. **Document verdict:** `NETWORK_ROUTING_BASELINE=RECORDED`, `CONFIGURATION_CHANGE=NONE`, `FULL_GUEST_E2E=NOT_RETESTED_IN_THIS_SNAPSHOT`.
