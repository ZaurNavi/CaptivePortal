# TASK-CAPTIVPROD-GUEST-VLAN50-DHCP19-01
## Выделенная гостевая VLAN 50, DHCP /19, DNS/NTP Cisco и безопасная интеграция нового Captiv-Prod

**Редакция v1.1 (Owner DNS/NTP correction).** Заменяет редакцию v1 по DHCP DNS/NTP и соответствующим allow/deny требованиям; остальные параметры и запреты сохранены. Это отложенное задание, не разрешение на работы.

**Версия:** v1.0  
**Дата:** 2026-10-16  
**Заказчик / конечный утверждающий:** Owner  
**Адресат:** Captiv-Prod SysAdmin  
**Тип:** отложенное техническое задание на конфигурацию сети Cisco + Omada + гостевого контура  
**Исполнение:** **HOLD до завершения текущей инфраструктурной задачи NET-01/TASK-07 v2 и отдельного явного Owner GO**  
**Новый сервер:** `captiv-prod`, `192.168.0.99`  
**Действующий production:** полностью защищён от изменений

---

## 1. Решение Owner и цель

Создать для **нового** Captiv-Prod **собственный гостевой L2/L3-сегмент с большим DHCP-пулом**. Сегмент не должен пересекаться со старым контуром по адресам, VLAN, управлению AP и CAPPORT/авторизации. Старый CaptivePortal продолжает работать независимо во время подготовки и пилота нового.

Причина большого DHCP-пула — **не 8190 одновременно работающих Wi-Fi-клиентов**. Открытая сеть парка привлекает проходящие телефоны: устройство получает адрес, может вовсе не авторизоваться и уходит; адрес остаётся арендованным до окончания 20-минутной аренды. Пул должен учитывать таких кратковременных и неавторизованных клиентов, особенно во время мероприятий.

**Фиксированные параметры Owner** — VLAN 50 (после проверки свободного ID), `10.50.0.0/19`, gateway `10.50.0.1`, lease 20 минут. Служебное исключение `.1–.49` и имя DHCP pool — **конкретные предложения Architect** для будущего change set. **DNS и NTP уже утверждены Owner:** единственный сервер — Cisco 3845 `192.168.0.1`, без публичных/резервных DNS. Не подменять адрес Cisco на VLAN50 gateway или адреса сторонних провайдеров. Ни один параметр SysAdmin не меняет самостоятельно.

**Целевая конфигурация:**

| Параметр | Целевое значение и статус |
|---|---|
| Новая гостевая VLAN | **50**, VLAN name `CAPTIVPROD_GUEST` |
| IPv4-сеть | **`10.50.0.0/19`** |
| Маска | **`255.255.224.0`** |
| Wildcard для IOS ACL/NAT | **`0.0.31.255`** |
| Network ID | `10.50.0.0` |
| Broadcast | `10.50.31.255` |
| Первый/последний пригодные IP | `10.50.0.1` / `10.50.31.254` |
| Всего пригодных IPv4 | **8190** |
| Gateway / L3 интерфейс | **`10.50.0.1/19`**, Cisco 3845 |
| DHCP-сервер | **Cisco 3845 IOS**, локальный DHCP pool, **без relay** |
| DHCP pool name | `CAPTIVPROD_GUEST_V50` |
| Исключённый служебный диапазон | **`10.50.0.1–10.50.0.49`** (49 адресов) |
| Выдаваемые DHCP-адреса | **`10.50.0.50–10.50.31.254`** |
| Доступно динамических аренд | **8141** |
| Lease | **0 дней 0 часов 20 минут** |
| DHCP Router Option 3 | `10.50.0.1` |
| DHCP DNS Option 6 | **`192.168.0.1` — единственный DNS; Cisco 3845** |
| DHCP NTP Option 42 | **`192.168.0.1` — единственный NTP; Cisco 3845** |
| Управляющий IP нового host | `192.168.0.99`, **без переноса в VLAN 50** |
| Новый гостевой FQDN | `captivprod-navi.duckdns.org` |
| Новый Portal subnet allowlist | `10.50.0.0/19` (после запуска нового контура) |
| Срок жизни старого контура | Не меняется в рамках этого TASK |

**Не использовать** `192.168.8.0/22` или любую старую гостевую адресацию как часть нового DHCP-пула. Историческая принадлежность `192.168.8.0/22` конкретному VLAN должна быть проверена как факт до миграции AP; этот TASK не переопределяет старую подсеть.

### 1.1. DNS и NTP — фиксированное решение Owner

**Единственный DNS для новых DHCP-клиентов — Cisco 3845 `192.168.0.1`. Единственный NTP — та же Cisco `192.168.0.1`.** Резервных или публичных DNS/NTP не выдавать; не объявлять `10.50.0.1` вторым DNS.

- DHCP Option 6: ровно один адрес `192.168.0.1`. DHCP Option 42: ровно один адрес `192.168.0.1` при подтверждённой поддержке соответствующей IOS команды. Аренда 20 минут без изменений.
- VLAN50 guest ingress ACL: допустить к **`192.168.0.1` только UDP/TCP 53 (DNS) и UDP 123 (NTP)**, помимо отдельно необходимых DHCP и NPM HTTPS. Остальные management-сервисы Cisco и другие приватные адреса остаются запрещёнными.
- Поскольку DNS/NTP находятся на адресе управляющей сети, функционально подтвердить с пилотного VLAN50 ответы DNS до/после авторизации, корректное разрешение нового FQDN и ответ NTP. Убедиться, что существующая Cisco действительно обслуживает DNS-запросы и NTP-клиентов новой сети (с соответствующей текущей политикой доступа).
- **Не изменять глобальные DNS/NTP службы, peer/server settings, конфигурацию старой сети или текущие клиентские DHCP options без отдельного GO.** Если DNS или NTP не отвечает — `HOLD_DNS_NTP`, показать точную причину, не выдавать клиентам сторонний DNS как обходной путь.

---

## 2. Границы изменений: критически важно

### РАЗРЕШЁННАЯ ЦЕЛЕВАЯ ОБЛАСТЬ после отдельного Owner GO

1. На Cisco 3845: **новый** dot1Q VLAN 50 L3-subinterface, адрес `10.50.0.1/19`, новый независимый DHCP pool с исключениями и 20-минутной арендой.
2. На Catalyst: **создать VLAN 50**, добавить его **аддитивно** к необходимому trunk к маршрутизатору и к конкретному *новому пилотному* AP. Сохранять все уже разрешённые VLAN на trunk.
3. Добавить **только** `10.50.0.0/19` в существующую корректную схему NAT и новые ограниченные правила guest-access после read-only проверки текущего NAT/ACL.
4. На **новой** Omada: подготовить отдельный guest WLAN/SSID для пилота с VLAN ID `50`, 20-минутный DHCP остаётся только на Cisco; привязать к новому Portal после его готовности.
5. Для нового пассивного SPAN использовать **только выделенный Gi1/0/45 → enp3s0**; будущая выделенная SPAN-сессия должна наблюдать **только согласованный трафик нового VLAN 50**. Состав источников/направление подлежат точечной проверке аппаратных возможностей и отдельному GO.

### СТРОГО ЗАПРЕЩЕНО

- Изменять Cisco **Gi1/0/48**, старую SPAN/RSPAN-сессию, старый мониторинговый тракт или существующие VLAN 10/999.
- Удалять, переименовывать, переназначать, `shutdown` или заменять существующий **VLAN 10** в сети. VLAN 10 может быть частью живого управления и старого Portal. **Фраза Owner «на свитче поменять VLAN 10 на новый» НЕ даёт права удалять VLAN 10: при наличии источника VLAN 10 в собственной новой SPAN-сессии Gi1/0/45 он должен быть заменён на VLAN 50 только после проверки ownership и отдельного GO. Если контекст фразы иной — приостановить именно этот пункт и уточнить его, не затрагивая старую сеть.**
- Делать `switchport trunk allowed vlan 50` **без** `add`: это может удалить остальные VLAN и остановить старые сервисы.
- Менять адреса существующих VLAN, старые DHCP pools/leases, DNS/DHCP опции других VLAN, PPPoE Dialer1, существующий NAT overload/port forwards и production ACL за пределами точной аддитивной правки.
- Перепривязывать / мигрировать рабочие AP к новой Omada; менять действующий SSID `Zefer_Parki` или старый External Portal до отдельного пилотного/cutover GO.
- Публиковать управленческие порты нового сервера в VLAN 50; подключать `enp3s0` к L3, выдавать ему IP, DHCP или использовать его как обычный trunk.
- Выполнять массовый DHCP load test, Cisco `reload`, полный сброс switch/controller, `clear ip dhcp binding *` или `clear ip nat translation *` на работающем оборудовании.

### ВАЖНО: интерфейс Gi1/0/45

`Gi1/0/45` на Catalyst уже имеет статус `MONITORING` и предназначен для отдельной пассивной NIC `captiv-prod:enp3s0` (1 Gbps full duplex, no IP). **Это SPAN destination, не обычный порт гостевого VLAN, не AP uplink и не trunk.** Ни для DHCP, ни для обычной передачи VLAN 50 этот порт не используется.

---

## 3. Этап и зависимость от текущей работы

Настоящий TASK — **проектное решение Owner, сохраняемое в источниках на будущее**, а не разрешение прямо сейчас менять сетевое оборудование.

**Порядок:**

1. Закрыть текущие NET-01 / Docker / systemd / Omada / Evidence preinstall-действия настолько, чтобы дальнейший сетевой этап не мешал действующей подготовке.
2. Перед сетевым изменением SysAdmin собирает **один короткий read-only preflight** по разделу 4 и подставляет подтверждённые фактические имена интерфейсов/транков в шаблон раздела 5.
3. Owner утверждает точный change set, pilot AP и окно. Отдельно утверждаются router/switch mutation, new SPAN session и piloting AP.
4. Изменить **только новые** объекты; проверить DHCP, NAT, DNS, изоляцию, маршрут HTTPS, мониторинг.
5. Сохранить конфигурации после PASS; оставить старую сеть неизменной.

**GO на реализацию сейчас: NO.** Не расценивать обсуждение адресного плана как разрешение немедленно менять Cisco.

---

## 4. Предварительная проверка (read-only; конкретный checklist)

Не расширять исследование без найденного конфликта. За один сеанс подтвердить:

**Cisco 3845 / IOS 15.1(4)M12a:**

- Рабочий LAN-facing 802.1Q parent (по ранее известной топологии кандидат `GigabitEthernet0/1`, **не применять по памяти**).
- Существование/отсутствие `.50`, dot1Q 50 и IP `10.50.0.1`; отсутствие совпадающего network/route/VRF/VPN/NAT.
- Доступность IOS DHCP server, отсутствие pool `CAPTIVPROD_GUEST_V50`, существующих исключений в `10.50.0.0/19`.
- Точный действующий NAT selector (standard ACL / extended ACL / route-map), единственный корректный способ **добавить** подсеть `10.50.0.0/19` без изменения остальных источников и без второго NAT overload.
- Текущие ACL/политики направления guest→management, путь наружу и возможность guest→`192.168.0.99:443`.
- Отсутствие сети `10.50.0.0/19` в известных локальных, VPN, remote, WireGuard, контейнерных или служебных маршрутах; при конфликте — **HOLD, не выбирать другую сеть самостоятельно**.
- Наличие свободных памяти и CPU для DHCP/NAT, без активного стресс-теста рабочего маршрутизатора.

Минимальные команды диагностики (показывать только необходимые фрагменты, без секретов):

```ios
show version
show ip interface brief
show ip route 10.50.0.0
show ip route 10.50.0.1
show running-config | include ^interface|encapsulation dot1Q 50|10.50.0.|CAPTIVPROD_GUEST_V50
show ip dhcp pool
show ip dhcp conflict
show ip nat statistics
show access-lists
show processes cpu sorted
show memory summary
```

`show running-config` с широкими фильтрами может выявить чувствительные данные; в отчёт включать только подтверждённые нетайные поля. Прежде чем менять NAT, дополнительно локально открыть конфигурацию **только NAT selector и связанного ACL/route-map**. Не редактировать старые NAT правила в ходе проверки.

**Catalyst (по текущему имени порта `Gi1/0/45`):**

- VLAN ID 50 свободен (`show vlan id 50`); старые VLAN не удаляются.
- Реальные router trunk и pilot AP switchport определены по соседству/CDP/LLDP/физическим соединениям, а не по номеру из старых заметок.
- VLAN 50 действительно может пройти **только дополнительно** по нужному trunk; его native VLAN/management VLAN не меняется.
- `Gi1/0/45` остаётся monitoring destination, пассивный кабель → `enp3s0`; **ни одна старая SPAN-сессия и порт 48 не осматриваются и не изменяются**.
- Новый VLAN SPAN на 45 обсуждается отдельным узким изменением после проверки возможностей Catalyst и выбранного пилотного трафика.

Минимальные команды (на целевых новых объектах):

```ios
show vlan id 50
show interfaces trunk
show interfaces Gi1/0/45 status
show interfaces Gi1/0/45 switchport
show cdp neighbors
```

`show interfaces trunk` используется только для идентификации соответствующего нового пути и сохранения существующей allowed VLAN list; **не для анализа старых SPAN/VLAN**.

**Новая Omada:** настоящий new Site ID, pilot AP ownership, guest SSID isolation, VLAN setting, captive settings; не принимать Controller ID за Site ID. Никаких изменений AP до GO.

**Обязательная фиксация preflight:** `ROUTER_PARENT`, `SWITCH_ROUTER_TRUNK`, `SWITCH_PILOT_AP_PORT`, `NAT_SELECTOR`, `NAT_STYLE`, `VLAN50_FREE=YES`, `10.50.0.0/19_NON_OVERLAP=YES`. Несовпадение → `HOLD`, без творческой замены параметров.

---

## 5. Target configuration — Cisco 3845 (только после GO)

### 5.1. Новый dot1Q интерфейс

Использовать **только фактически подтверждённый LAN parent**. Если подтвердился `GigabitEthernet0/1`, целевая конфигурация:

```ios
configure terminal
interface GigabitEthernet0/1.50
 description CAPTIVPROD_GUEST_VLAN50_NEW_ONLY
 encapsulation dot1Q 50
 ip address 10.50.0.1 255.255.224.0
 ip nat inside
 no ip redirects
 no ip proxy-arp
 no shutdown
exit
end
```

`ip nat inside` применяется только при подтверждённой текущей схеме NAT inside/outside. Если selector реализован иначе, не выполнять блок вслепую: `HOLD_NAT_MAPPING`. Новую VLAN 50 создавать как 802.1Q, **не делать native VLAN**.

### 5.2. DHCP pool

**Исключения добавить до включения DHCP-сервиса для VLAN50.** Не изменять глобальный DHCP lease и действующие пулы.

```ios
configure terminal
ip dhcp excluded-address 10.50.0.1 10.50.0.49
ip dhcp pool CAPTIVPROD_GUEST_V50
 network 10.50.0.0 255.255.224.0
 default-router 10.50.0.1
 dns-server 192.168.0.1
 option 42 ip 192.168.0.1
 lease 0 0 20
exit
end
```

Не добавлять `ip helper-address` на `.50`: DHCP сервер находится непосредственно на Cisco 3845. Отдельный DHCP на Omada/AP или Linux host **не запускать**.

**Ожидаемая выдача:** начиная с `10.50.0.50` (с учётом занятого/конфликтующего адреса), не выходя за `10.50.31.254`; broadcast и network ID никогда не выдавать. Проверить фактический lease=20 минут на клиенте, единственный DNS `192.168.0.1` (Option 6) и NTP `192.168.0.1` (Option 42). До исполнения проверить поддержку `option 42 ip` на конкретной IOS версии; при неподдерживаемой команде — `HOLD_OPTION42`, не внедрять альтернативу самовольно.

### 5.3. NAT — единственная допустимая модель изменения

NAT выполняет уже действующая инфраструктура Cisco 3845 через `Dialer1` с overload. Новый сегмент должен получить интернет без второго конкурирующего NAT policy.

- Если действующий selector — **стандартный ACL**, добавить одну узкую ACE `permit 10.50.0.0 0.0.31.255` **в существующий NAT selector** с сохранением прочих ACE.
- Если действующий selector — **extended ACL/route-map**, добавить эквивалентное разрешение source `10.50.0.0/19` в соответствующее правильное место текущего selector; **не** ставить произвольную ACE поверх deny/в другом ACL.
- Если используется иная схема, STOP и показать Architect точный селектор: **не создавать новую `ip nat inside source ... overload` команду** в обход существующей архитектуры.
- Зафиксировать в change set **точный ACL/route-map ID и строки команд** после read-only preflight. Отсутствие конкретного NAT selector = `HOLD`, а не свобода выбора.

### 5.4. Guest boundary / маршрутизация

Целевая политика: **Guest VLAN50 → интернет + DNS/NTP только Cisco `192.168.0.1` + HTTPS к новому NPM; Guest VLAN50 ↛ private/management сети, кроме точных необходимых сервисов.**

- Разрешить DHCP client↔router; **к `192.168.0.1` только UDP/TCP 53 и UDP 123**; TCP 80/443 к интернету и **только TCP443** к `192.168.0.99` (новый NPM) в рамках гостевой политики. Для частного IP `192.168.0.1` это единственные сервисные исключения из запрета management-сетей; административные порты Cisco запрещены.
- Запретить из guest прямой доступ к администрированию Cisco, Omada `8043/8088/8843`, Docker control, SSH `22`, NPM admin `81`, Sensor/Evidence, старым VM `.202`/`.222`, старому LAN и другим приватным сетям; не перекрывать контролируемый путь DNS/NTP/DHCP/NPM.
- Не использовать `permit ip any any` в качестве замены отсутствующей guest ACL. Не включать высокочастотный `log` на каждом отклонённом guest-пакете (опасно для CPU Cisco).
- Точные guest ingress ACL и их место применения сформировать **по фактической текущей guest/WLAN политике Cisco** с сохранением допустимого NAT. Перед GO предъявить короткую таблицу allow/deny и реальные ACE. Самостоятельно «унаследовать» старый ACL без анализа запретов нельзя.
- Portal/FQDN должен быть достижим из VLAN50 ещё до гостевой авторизации: если публичное разрешение имени приводит к WAN-IP, проверить hairpin; при провале **не открывать старую сеть** и не менять общий NAT. Предпочитать утверждённую внутреннюю маршрутизацию имени к `192.168.0.99:443`, если есть подходящий контролируемый DNS механизм.

Требование изоляции не отменяет возможности коротких тестов до авторизации: DHCP, DNS и NTP на Cisco, captive discovery и загрузка нового FQDN должны работать.

---

## 6. Target configuration — Catalyst и AP

### 6.1. Создание VLAN

```ios
configure terminal
vlan 50
 name CAPTIVPROD_GUEST
exit
end
```

Проверить `show vlan id 50`. **Никакого удаления или замены VLAN 10, старых access VLAN и trunk native VLAN.**

### 6.2. Router trunk

На **подтверждённом существующем trunk в сторону Cisco 3845** добавить разрешение VLAN50 (если trunk использует explicit allowed VLAN list):

```ios
configure terminal
interface <VERIFIED_SWITCH_TO_ROUTER_TRUNK>
 switchport trunk allowed vlan add 50
exit
end
```

Синтаксис команды проверяется на фактическом Catalyst IOS. Если trunk не использует explicit allowed list, не делать бессмысленной/разрушающей настройки; подтвердить фактический проход VLAN50. **Никогда не применять `switchport trunk allowed vlan 50` без `add` на общем trunk.**

### 6.3. Pilot AP port и Omada

- Тестировать на **одной отдельно одобренной пилотной AP**, которую Owner разрешил подключить именно к **новой Omada**. Старые AP/adoption untouched.
- Management/native VLAN пилотной AP — оставить таким, как подтверждено её текущей безопасной management схемой; guest VLAN 50 передавать **tagged**.
- На соответствующем AP uplink разрешить VLAN 50 аддитивно, без потери management VLAN, до изменения SSID. Выделенный guest SSID для пилота — `CaptivProd_Pilot` (временное имя, не совпадает со старым `Zefer_Parki`), **Open Wi-Fi с включённым captive portal на новой Omada** только когда новый Portal будет готов к тесту; при предварительной сетевой проверке допустим SSID без принудительного перенаправления, только на пилотной AP.
- Для клиентов гостевого SSID включить **client isolation**, если поддерживается контроллером/AP в данной конфигурации; отдельные сервисы и gateway должны оставаться доступны.
- Убедиться, что Omada является AP/controller management, **не вторым DHCP-сервером** гостевого VLAN.

### 6.4. Пассивный SPAN на Gi1/0/45

Цель нового Sensor — наблюдать согласованный трафик VLAN 50 на `enp3s0`, **не старые VLAN**. На этапе адресации **не изменять существующие monitor-сессии**. Для отдельного SPAN GO SysAdmin предъявляет проверенное и поддерживаемое Catalyst оборудование, ID собственной новой session, источник VLAN50/порты и направление, `destination Gi1/0/45`, затем позитивный тест видимости DHCP/DNS пилота. Если дополнительная session невозможна без вмешательства в старую — **HOLD_SPAN**, а не переподключение 48/переиспользование старой схемы.

---

## 7. Совместимость с CaptivPortal и Fingerprint

После подтверждения нового Site и появления отдельной пилотной AP новые компоненты должны интерпретировать клиентов VLAN50 как собственный guest scope.

1. **CAPPORT**: `CAPPORT_ALLOWED_CLIENT_NETWORKS=10.50.0.0/19` и `CAPPORT_SITE_ID=<ACTUAL_NEW_OMADA_SITE_ID>`. Конфигурация допускает другие deployment-values без изменения исходного кода.
2. **Omada External Portal**: использовать **новый** FQDN `https://captivprod-navi.duckdns.org` и только Pilot Site/AP до отдельного cutover.
3. **Fingerprint Sensor / Portal Evidence Producer**: в env матрице обновить guest CIDR на `10.50.0.0/19`, authoritative DHCP gateway на фактический `10.50.0.1`, Site/source/producer IDs от новой Omada/Receiver. Названия env-переменных брать из принятого Git SHA/TREE, **не выдумывать или переименовывать**.
4. **F-B1 source registration**: зарегистрировать **новые** source identities и network/site mapping; старые Evidence IDs и cookies/token не переносить.
5. **SPAN**: новый порт `Gi1/0/45 → enp3s0`, passive only. Management traffic остаётся на `enp2s0` / `192.168.0.99`.
6. **NET-01**: сохраняет независимую NPM + local Sensor boundary; новый guest CIDR **не должен** получить прямой TCP-доступ к Flask `172.18.0.1:18089`.
7. **NPM TLS**: Guest получает внешний HTTPS через новый Proxy Host, действующие proxy hosts и старый FQDN не меняются.

В конфигурации pilot SSID сверить настройки Pending Session Cleaner и остальные SSID allowlist, чтобы тестовый `CaptivProd_Pilot` не наследовал правила рабочего `Zefer_Parki` случайно.

Изменение guest CIDR — новое deployment setting, а **не** разрешение автоматически запускать CaptivePortal раньше окончания текущих preinstall-gates.

---

## 8. Испытания и критерии приёмки (без искусственной перегрузки)

Проводить безопасно на новой пилотной AP/одном-двух личных устройствах Owner. Конфигурацию применить только после отдельного Owner GO. Для негативных тестов использовать контролируемый тестовый клиент, а не чужие телефоны.

| № | Проверка | Приёмка |
|---|---|---|
| 1 | VLAN50 у Cisco и Catalyst | VLAN ID 50 существует; old VLAN/trunks unchanged |
| 2 | L3 | VLAN50 gateway `10.50.0.1/19`, direct connected route `10.50.0.0/19` |
| 3 | DHCP DISCOVER→OFFER→REQUEST→ACK | Клиент выдаёт `10.50.0.50–10.50.31.254`, mask `255.255.224.0`, router `.1`, DNS **только `192.168.0.1`**, NTP Option 42 **только `192.168.0.1`**, 20 min lease |
| 4 | DHCP исключения | Ни один адрес `10.50.0.1–49` не выдаётся, нет чужих/дублирующих DHCP OFFER |
| 5 | Renew, reconnect, expiry | Обновление и истечение аренды работают; отдельное устройство с randomized MAC не нарушает пул |
| 6 | Internet/NAT | Тестовый guest получает NAT через текущий Dialer1 и доступ в интернет |
| 7 | Pre-auth DNS/NTP | С VLAN50 DNS UDP/TCP 53 и NTP UDP 123 доступны на `192.168.0.1`; иные DNS/NTP не выданы по DHCP; административный доступ к Cisco остаётся закрыт |
| 8 | New Portal FQDN | Правильный SNI, доверенный HTTPS, route к **новому** NPM, нет старого upstream |
| 9 | Guest isolation | Недоступны Cisco admin, old Portal/Omada, NPM admin, SSH, Evidence, внутренние сети кроме явно нужного NPM HTTPS |
| 10 | Pilot AP | Только одобренная новая AP/SSID, DHCP из VLAN50, management AP не потерян |
| 11 | Mirror | Только после отдельного SPAN GO виден трафик пилотного VLAN50 на enp3s0; нет старого source scope |
| 12 | No-regression | Старый Portal, старые AP, DHCP pools, VLAN, NAT и NPM не изменены и работают |
| 13 | Restart/persistence | Настройки переживают контролируемый перезапуск интерфейса/тестового клиента; повторная проверка после `write memory` без reload production узлов |
| 14 | DHCP pool metrics | `show ip dhcp pool` содержит capacity 8141 после exclusions (или объяснимую IOS статистику); binding, conflict, offered/ACK и загрузка CPU наблюдаемы |

**Нагрузочный критерий:** не пытаться заполнить 8190 записей или атаковать production роутер тестами. Достаточно проверить корректность адресного пространства, выдачу/renewal на пилотных клиентах, IOS статистику и отсутствие деградации реальной сети. Массовые синтетические запросы — только на полностью изолированной лабораторной инфраструктуре по отдельному желанию Owner.

### Мониторинг после запуска

- Пул `CAPTIVPROD_GUEST_V50`: total/use/free/exhaustion, leases, DHCP conflicts, allocation rate.
- Предупреждения по заполнению: **70% warning, 85% high, 95% critical** от **8141** динамических адресов.
- Отдельно показывать: **DHCP leases**, **Wi-Fi associated clients**, **CaptivePortal authorized guests**. Эти величины не равны друг другу.
- Cisco CPU/memory и NAT translations, DHCP decline/fail, gateway connectivity; AP airtime/assoc, WAN utilization.

---

## 9. Безопасная последовательность исполнения / GO gates

**Gate 0 — сейчас:** документ утверждает адресный план, **не** запускает миграцию.

**Gate 1 — read-only:** точные router/switch interface names, VLAN50 availability, NAT selector, overlapping check, один pilot AP, окно работ, backup. Результат Architect+Owner: GO/HOLD на **новые** объекты.

**Gate 2 — Cisco router:** снимок `running-config` с защищённым хранением, добавить VLAN50 subinterface и DHCP pool, NAT allow только для новой подсети, требуемую минимальную guest ACL; не трогать старые DHCP.

**Gate 3 — Catalyst:** создать VLAN50, только `allowed vlan add 50` на подтверждённом trunk, отдельно разрешённая pilot AP связь, без правок VLAN10/999/старого SPAN.

**Gate 4 — pilot:** проверить пункты 1–10 и 12–14 из таблицы. При FAIL локально выключить только новую пилотную конфигурацию, не затрагивая старых клиентов.

**Gate 5 — optional new SPAN:** после **отдельного GO**, собственная source VLAN50 и destination Gi1/0/45; тест пассивного захвата. Если порт45 уже работает как новый мониторинговый destination, не менять его без доказанной принадлежности новой session.

**Gate 6 — новая Omada/CaptivPortal:** конфигурационные Site ID, guest CIDR, External Portal и admission включать по собственным acceptance/cutover gates. **Никакого переноса старых AP или перепривязки живого SSID в составе этого TASK.**

**Сохранять конфигурацию (`write memory`/`copy running-config startup-config`) только после успешных проверок** целевых изменений и сверки diff. Никогда не делать автоматический полный restore живого роутера/свитча: он может откатить несвязанные production-правки.

---

## 10. Точечный rollback (при FAIL)

1. Отключить пилотный guest SSID VLAN50; management pilot AP сохранить.
2. Удалить **только** добавленный VLAN50 с конкретного trunk/AP allowed list посредством `switchport trunk allowed vlan remove 50`, если это именно наш добавленный ID. Остальные VLAN list не менять.
3. Удалить **только** созданную новую router subinterface `.50`, предварительно сверив interface owner/description.
4. Удалить **только** новый DHCP pool `CAPTIVPROD_GUEST_V50` и исключение `10.50.0.1–10.50.0.49`; не делать clear-all bindings/conflicts.
5. Удалить **только** новую ACE/source `10.50.0.0 0.0.31.255` из NAT selector и новую точную guest ACL / attachment. Сначала сравнить pre/post snapshot, чтобы не удалить чужие правила.
6. `no vlan 50` только если VLAN создан этим TASK и на нём больше нет назначенных новых портов. Ни один старый VLAN не удалять.
7. Новый SPAN откатывать только по собственному отдельно согласованному plan; существующую legacy session не трогать.
8. Убедиться, что старые DHCP, AP, NPM, NAT, Portal, Internet остаются рабочими. Записать итоговый diff. Не делать Cisco reload.

**Правило rollback:** если точная принадлежность нового объекта не доказана — **STOP, не удалять по догадке**.

---

## 11. Что SysAdmin передаёт на приёмку

Один компактный handoff вместо серии больших отчётов:

```text
TASK=TASK-CAPTIVPROD-GUEST-VLAN50-DHCP19-01
OWNER_DESIGN=APPROVED
EXECUTION_GO=YES/NO
VLAN_ID=50
GUEST_SUBNET=10.50.0.0/19
GATEWAY=10.50.0.1
DHCP_POOL=CAPTIVPROD_GUEST_V50
DHCP_RANGE=10.50.0.50-10.50.31.254
DHCP_DYNAMIC_CAPACITY=8141
DHCP_LEASE_MINUTES=20
DNS=192.168.0.1_ONLY_CISCO3845
NTP=192.168.0.1_ONLY_CISCO3845
DHCP_OPTION42=192.168.0.1_SUPPORT_TO_VERIFY
ROUTER_PARENT=<VERIFIED>
SWITCH_ROUTER_TRUNK=<VERIFIED>
SWITCH_PILOT_AP_PORT=<VERIFIED>
PILOT_AP=<OWNER_APPROVED>
NAT_SELECTOR=<VERIFIED>
NON_OVERLAP=PASS/HOLD
DHCP_OFFER_ACK=PASS/HOLD/NOT_TESTED
GUEST_DNS_NAT=PASS/HOLD/NOT_TESTED
NPM_HTTPS=PASS/HOLD/NOT_TESTED
GUEST_ISOLATION=PASS/HOLD/NOT_TESTED
SPAN_PORT45=PASS/HOLD/NOT_AUTHORIZED
LEGACY_PORT48_UNTOUCHED=YES
LEGACY_VLAN10_999_UNTOUCHED=YES
OLD_PORTAL_AND_OMADA_UNCHANGED=YES
BACKUP_AND_ROLLBACK=PASS/HOLD
FINAL_STATUS=PASS/HOLD
```

Приложить: sanitized exact config diff только новых объектов, 1–2 снимка DHCP statistics/bindings с замаскированными MAC, тесты DNS/NTP/HTTPS, документированный rollback. Не включать secrets, bearer, полные MAC случайных посетителей или приватные данные устройств.

---

## 12. Итоговый архитектурный контракт

```text
NEW_GUEST_VLAN=50
NEW_GUEST_SUBNET=10.50.0.0/19
DHCP_DYNAMIC_ADDRESSES=8141
DHCP_LEASE=20_MINUTES
DHCP_SERVER=CISCO_3845
DNS_SERVER=192.168.0.1_ONLY
NTP_SERVER=192.168.0.1_ONLY
SPAN_DESTINATION=GI1/0/45_ONLY_FUTURE_SEPARATE_GO
NEW_HOST_MANAGEMENT=192.168.0.99_UNCHANGED
OLD_GUEST_NETWORK=UNCHANGED
OLD_PRODUCTION=UNTOUCHED
CURRENT_NET01_TASK=PRIORITY_FIRST
IMPLEMENTATION=DEFERRED_UNTIL_OWNER_GO
```

**Owner/Architect design accepted:** большая DHCP-подсеть нужна прежде всего для кратковременных неавторизованных прохожих. 8190 пригодных IP — ёмкость адресного пространства, а не прогноз 8190 одновременно ассоциированных AP-клиентов. Ограничения AP, радиосреды и WAN измерять отдельно. Новая VLAN50 не должна создавать зависимости от перенастройки старого CaptivePortal.
