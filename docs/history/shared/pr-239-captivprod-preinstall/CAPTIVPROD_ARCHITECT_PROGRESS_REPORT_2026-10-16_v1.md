# CAPTIV-PROD — отчёт Architect о выполненных работах после последней директивы по AP Adoption

**Document ID:** `CAPTIVPROD-ARCH-PROGRESS-20261016`  
**Версия:** 1.0  
**Дата отчёта:** 16.10.2026 (Asia/Baku)  
**Период:** от переданной Owner директивы Architect «если Adoption не завершится — read-only проверить AP VLAN10, Omada TCP 29814 и журнал» до составления отчёта.  
**Основание:** фактические результаты команд и изменения в этой технической сессии, плюс два закреплённых baseline-документа.  
**Статус миграции:** `PILOT AP ADOPTION SUCCESS; FULL GUEST E2E UNVERIFIED; ALL AP MIGRATION NOT COMPLETE`.

## 1. Executive summary

- Найдена причина зависшего Adoption пилотной AP: специально установленная политика Linux `CAPTIV_OMADA_GUARD` блокировала управляющий TCP 29814 и discovery UDP 29810 на `192.168.0.99`.
- По отдельному разрешению Owner созданы **узкие постоянные исключения** для четырёх AP: `.80`, `.70`, `.60`, `.50` → `192.168.0.99` только TCP 29814 / UDP 29810. Остальные запреты, NET-01 и работа сервисов сохранены.
- **Пилотная AP** `0C-80-63-2F-FB-8D` (`192.168.0.80`, Catalyst `Gi1/0/6`) успешно прошла Adoption: Omada `adopt[auto=true] ok` (19:11:21 Баку), `CONNECTED` (19:11:24), открыто TCP-соединение `.80 → .99:29814`. При передаче конфигурации зафиксирован кратковременный `CONNECTED_ERROR`, затем повторный `CONNECTED`; end-to-end правильность всей конфигурации отдельно не принята.
- Owner самостоятельно переключил Guest SSID на VLAN 60 и добавил новый портал в **Omada Pre-Authentication Access**. Cisco выдал гостевому устройству `10.50.0.50` из `10.50.0.0/19`: L2 VLAN-tagging и DHCP нового контура фактически сработали.
- На Cisco 3845 настроена и сохранена **DHCP Option 114** только для VLAN 60: `https://captivprod-navi.duckdns.org/capport/api`. Старый VLAN 20 и его CAPPORT URL оставлены без изменений.
- На Cisco 3845 настроена и сохранена **статическая локальная DNS-запись** `captivprod-navi.duckdns.org → 192.168.0.99`, сохранив старую `captivportal-navi.duckdns.org → 192.168.0.202`. Проверено `dig @192.168.0.1`, `running-config`, `startup-config`, `write memory [OK]`.
- Выполнены два независимых 60-секундных read-only исследования загрузки дисков и серверов и live baseline маршрутизации/ACL/NAT/NET-01/NPM. Документы приложены как отдельные источники.
- **Не объявлять полный Pilot E2E PASS:** после исправления split DNS в этой сессии нет подтверждённого результата повторной попытки открытия портала/авторизации/выхода гостевого телефона в интернет.

## 2. Начальная директива и read-only диагностика Adoption

Уточнение границы: первоначальная директива Architect касалась **только трёх read-only проверок**; все последующие конфигурационные изменения выполнялись после дополнительных прямых указаний Owner.

| Проверка | Фактический результат |
|---|---|
| AP на прежнем IP management VLAN 10 | `192.168.0.80`, MAC `0C-80-63-2F-FB-8D`, ping 3/3, средняя задержка ~0,755 мс; ARP совпал |
| Новая Omada `.99` TCP 29814 | `jsvc` слушал `*:29814`, но соединения AP не устанавливались; отдельный TCP-тест из VLAN 10 провалился |
| Журнал Omada | `receive discovery when adopting, times[3] reach limit, set adopt fail`; позднее `AdoptSuccessTimeout` |
| Анализ netfilter | `CAPTIV_OMADA_GUARD` отклонял TCP 29811–29817 и сбрасывал UDP 29810 / 27001 / 19810, кроме отсутствовавших на тот момент AP-исключений |
| Packet capture до изменения | AP посылала UDP discovery и TCP SYN на `.99:29814`; приходил TCP reset; фиксировано tcpdump |

**Причина сбоя Adoption:** host firewall, а не недоступность AP в VLAN 10 и не L2 trunk VLAN 60.

## 3. Применённые изменения (с разграничением ответственности)

### 3.1 Новый сервер `captiv-prod` (`192.168.0.99`) — SysAdmin, Owner GO

Для точных IP `192.168.0.80`, `.70`, `.60`, `.50` к destination `192.168.0.99/32` добавлены правила:

- `TCP dport 29814 → RETURN` (допуск дальше по INPUT path);
- `UDP dport 29810 → RETURN`.

Остальные источники продолжают попадать под существующие `REJECT/DROP`; исключения не открывают другие Omada-порты. Правила установлены **перед** общими deny, прописаны в `/usr/local/sbin/captiv-omada-guard` (постоянное применение `captiv-omada-guard.service`). Создан backup прежнего guard-скрипта, проверен `bash -n`, NET-01 verifier: `DOCKER_IDENTITY=PASS`, `FIREWALL_FAIL_CLOSED=PASS`. Omada/Portal не перезапускались в рамках этого исправления.

**MAC/IP соответствия и AP-port baseline:**

| AP MAC | Management IP | Catalyst port | Firewall exception | Adoption новой Omada |
|---|---|---|---|---|
| `0C-80-63-2F-FB-8D` | `192.168.0.80` | `Gi1/0/6` | Да | **PASS для Adoption**; full config/E2E не принят |
| `28-EE-52-47-5C-38` | `192.168.0.70` | `Gi1/0/5` | Да | Не подтверждён данным этапом |
| `DC-62-79-1B-4A-68` | `192.168.0.60` | `Gi1/0/10` | Да | Не подтверждён данным этапом |
| `EC-75-0C-18-6F-F8` | `192.168.0.50` | `Gi1/0/15` | Да | Не подтверждён данным этапом |

*Tagged VLAN 60 на указанных четырёх AP trunk-портах Catalyst был подготовлен до рассматриваемой директивы; в данном периоде trunk не изменялся.*

### 3.2 Настройки Omada / SSID — действия Owner

- Owner установил **VLAN ID 60** для проверяемого Guest SSID `Zefer_Parki` в новой Omada.
- Owner добавил домен нового портала в **Pre-Authentication Access** (walled garden) на новой Omada.
- После VLAN change клиент получил аренду `10.50.0.50`; это подтверждает переход гостевого трафика в новый DHCP pool на Cisco.
- От SysAdmin иных изменений SSID, ACL Omada, Hotspot или прочих AP не было.

### 3.3 Cisco 3845 — DHCP Option 114, SysAdmin по Owner GO

Добавлено **только** в `ip dhcp pool CAPTIVPROD_GUEST_V60`:

```cisco
option 114 ascii https://captivprod-navi.duckdns.org/capport/api
```

Подтверждено `running-config`, `startup-config` после `write memory [OK]`. Новый pool: `10.50.0.0/19`, GW `10.50.0.1`, DNS `192.168.0.1`, NTP Option 42 `192.168.0.1`, lease 20 min. Legacy `ip dhcp pool Guest` (`192.168.8.0/22`) оставлен с **прежним** `https://captivportal-navi.duckdns.org/capport/api`.

### 3.4 Cisco 3845 — split DNS для нового Portal, SysAdmin по Owner GO

Обнаружено: Cisco DNS до исправления возвращал `85.132.110.97` для нового DDNS-домена; NAT hairpin маскировал гостевой `10.50.0.50` публичным исходным адресом, и новый CAPPORT API отвечал `HTTP 403 {"error":"client_not_allowed"}`. По архитектуре нового Portal доверенная guest-сеть — `10.50.0.0/19`; расширение trust до WAN не выполнялось.

Добавлена отдельная Cisco запись:

```cisco
ip host captivprod-navi.duckdns.org 192.168.0.99
```

**Особенность IOS:** первая попытка совпала с временным DNS cache entry и не закрепилась; команда `clear host` также удаляла статическую запись, если вызывалась после неё. Окончательное успешное выполнение: очистка только указанного DNS имени **до** добавления `ip host`, затем read-back `show hosts` = `perm, OK 192.168.0.99`; `dig @192.168.0.1` = `192.168.0.99`; `running-config`, `startup-config` и `write memory [OK]` — PASS.

Старая запись `captivportal-navi.duckdns.org → 192.168.0.202` осталась неизменной. NAT 80/443 и внешний DDNS не переключались.

## 4. Полевой тест и состояние guest CAPPORT

**Подтверждено:** pilot AP adopted/connected в Omada; клиент Guest SSID попал в VLAN 60 и получил `10.50.0.50`; DHCP Option 114 и новый split DNS верны; nginx/Portal/Omada на новом узле работали при последующих read-only снимках.

**До исправления split DNS:** `/capport/api` отвечал `403 client_not_allowed`, т.к. при hairpin до нового Portal доходил публичный исходный IP вместо адреса в `10.50.0.0/19`.

**Не подтверждено после DNS-исправления:** успешный HTTPS CAPPORT API с телефона в VLAN 60, открытие страницы приглашения, Omada Hotspot authorization read-back, завершённый пользовательский login/guest internet E2E; необходимость повторить тест на Owner-controlled устройстве.

Отдельный зафиксированный Omada issue: сразу после `adopt ok` первый `syncFullConfiguration` вернул `success=false`, `errcode=-1`, статус кратко `CONNECTED_ERROR`, затем `CONNECTED`. Не считать config-sync PASS без read-back или E2E теста.

## 5. Read-only performance baseline — новый и старый Portal

Сделаны независимые **60,002-секундные** интервалы:

- новый физический `.99`: 16.10.2026 **20:03:35–20:04:35 Baku**;
- старый VM `.202`: **20:13:52–20:14:52 Baku**.

| Метрика за 60 с | Новый `.99` (`sda`, SSD) | Старый `.202` (`vda`, VM virtual disk) |
|---|---:|---:|
| Завершённые чтения | 3 | 3 565 |
| Завершённые записи | 1 282 | 4 554 |
| Общий read + write I/O | 1 285 | 8 119 |
| Прочитано | 0,098 MiB | 17,211 MiB |
| Записано | 8,852 MiB | 46,046 MiB |
| Write await | 0,758 ms | 117,465 ms |
| Disk busy | 1,200% | 96,557% |
| Average queue depth | 0,0204 | 12,4229 |
| CPU busy | 3,55% | 33,55% |
| CPU iowait | 0,15% | 57,36% |
| PSI I/O some (total stall в выборке) | 0,125 s | 42,647 s |

**Фактический baseline:** старый узел выполнял ×6,32 больше завершённых I/O (×3,55 write ops; ×5,20 write volume). Самый заметный риск — высокая задержка и очередь виртуального диска старого VM. Но это **не A/B тест одинаковой нагрузки**: на старом работают Traffic Projection / Fingerprint / Network Metadata / Recognition, отличаются SSD и VM/vdisk, количество событий и число клиентов. Не приписывать коэффициенты исключительно оптимизациям приложения.

**Причинная атрибуция (task-attributed bytes за минуту):** новый основной Portal ~5 996 KiB write; старый Portal ~7 124 KiB write. На старой VM отдельно создавали запись Fingerprint (~13 984 KiB) и Traffic Projection (~7 092 KiB). Старый основной Portal сделал ~2 149 961 логических read syscalls при ~192 KiB task-attributed physical read; это **не** 8+ GiB физического чтения с диска.

**Исправление в исследовании:** первоначальные 252/3569, названные как число flush, получены из ошибочного индекса `/proc/diskstats` и **не являются подтверждённым количеством flush ops**. В зафиксированном источнике flush count = **N/A**. Ни один коэффициент сравнения на этих числах не строится.

Read-only; на старом production `.202` никакие службы, конфигурация или данные не изменялись.

## 6. Read-only network / routing / ACL / NPM baseline (снимок ~20:30–20:37 Baku)

- Новый host `captiv-prod`: management `enp2s0 = 192.168.0.99/24`; default route via Cisco `192.168.0.1`. Sensor `enp3s0` в PROMISC **без IP**; не участвует в IP routing. Docker bridge `172.18.0.1/16`, контейнер NPM `172.18.0.2/16`.
- Публичный HTTP(S) ingress: Cisco static NAT **TCP 80/443 → `.99`**; Docker port mapping `.99:80/81/443 → NPM .2`. NPM Host routes: старый Portal → `.202:18088`, Cloud → `.202:8082`, VPN web → `.220:51822`, новый Portal → `172.18.0.1:18089`.
- NET-01 защищает Flask backend `172.18.0.1:18089`: identity-bound NPM Docker IP/MAC, отдельные INPUT/OUTPUT guards; verifier `DOCKER_IDENTITY=PASS`, `FIREWALL_FAIL_CLOSED=PASS`. NPM Admin :81 разрешён только VLAN10 `192.168.0.0/24` через `DOCKER-USER` original-destination rules.
- Omada Linux `.99` слушает `8043`, `8088`, `8843`, `29811–29816`, UDP `29810/27001/19810`; host Omada guard допускает web/API только для management `/24` и device management для четырёх точных AP IP/портов (см. §3.1).
- Cisco 3845 маршрутизирует VLAN10 `192.168.0.0/24`, VLAN20 `192.168.8.0/22`, VLAN30 `192.168.3.0/24`, VLAN60 `10.50.0.0/19`. Входящий ACL VLAN60 разрешает DHCP, Cisco DNS/NTP, **только `192.168.0.99:443`** среди management destinations, блокирует доступ в остальные приватные сети, затем разрешает прочий интернет-трафик через PAT.
- Catalyst 2960S: четыре AP trunk-порта с native VLAN10 и allowed tagged VLAN60; uplink `Gi1/0/1` VLAN 10/20/30/50/60. SPAN Session2 VLAN60 both directions → Gi1/0/45; RSPAN Session1 legacy VLAN20 RX-only → 999. SPAN — отдельный L2 traffic copy, **не** default route.
- **Незавершённая внешняя Omada миграция:** Cisco static forwards **UDP 29810 и TCP 29814 по-прежнему → старая Omada `.222`**, не `.99`. Pilot локально идёт management VLAN10 напрямую на `.99`. Forward'ы не перенастраивались и сами по себе не являются ошибкой для этой AP.
- Host Linux global `INPUT` policy = ACCEPT; это **не default-deny хост**. Конкретные области защищены targeted guards/Cisco ACL; не приписывать общую DROP-политику.
- При снимке relevant units (Portal, Omada, NET-01, NPM, Sensor, Suricata) active. Само наличие разрешающих правил не равно полному guest E2E PASS.

## 7. Что НЕ менялось

- Старые production Portal `.202` и Windows Omada `.222` не останавливались, не перенастраивались в рамках периода; другие AP не переводились SysAdmin.
- Прежний DHCP пул Guest VLAN20, прежний CAPPORT домен и Cisco старый static DNS host сохранены.
- NAT port forwards Omada `.222`, WAN ingress TCP80/443, NPM legacy Proxy Hosts, сертификаты, guest firewall scope, новый app source/git, firewall NET-01 не изменялись указанными сетевыми исправлениями.
- Не выполнялись массовые `Adopt`/`Forget`, hardware reset, изменение firmware, перенос журналов/SQLite старого Portal или ослабление CAPPORT trust/Cisco private-network ACL.
- Baseline-измерения и network inventory были read-only (служебные диагностические результаты сохранены отдельно).

## 8. Остаточные задачи / Architect decisions

1. **Pilot Guest E2E Acceptance: HOLD / NOT VERIFIED.** Провести контролируемый телефонный тест через `Zefer_Parki` VLAN60: IP `10.50.x.x`, DNS `.99`, HTTPS `/capport/api` с корректной клиентской идентичностью, реальное открытие страницы, Hotspot authorization read-back, доступ в интернет после авторизации. Собрать evidence без персональных данных посетителей.
2. **AP configuration read-back:** проверить действующую VLAN/SSID/Portal config pilot AP и ошибки `syncFullConfiguration`, если повторятся; не трактовать transient `CONNECTED_ERROR` как скрытый PASS всех настроек.
3. **Остальные AP:** firewall готов к четырём management IP, но остальные устройства **не объявлены migrated**. Отдельный Owner/Architect GO и поштучные gates.
4. **WAN Omada forwards:** решение о переводе с `.222` на `.99` требуется **только при подтверждённой зависимости удалённых AP**; не менять по догадке.
5. **Сравнение после full AP migration:** повторить read-only 60-second I/O baseline и, при необходимости, 5–15 min sample, с учётом online AP/guest и реальных auth events; корректно считывать flush counters из исходных diskstats; сравнивать абсолютные и нормализованные показатели.
6. **Сетевые boundaries и конфигурация:** при следующих изменениях не ослаблять `CAPTIV_OMADA_GUARD`, `CAPTIV_FLASK_18089`, `DOCKER-USER` и Cisco VLAN60 ACL без отдельного reviewed scope.

## 9. Ближайшие артефакты и ссылки для Architect

1. `CAPTIVPROD_OLD_VS_NEW_IO_BASELINE_2026-10-16_v1.md` — измерения, методика, причинная атрибуция, исправление flush, шаблон сравнения после миграции.
2. `CAPTIVPROD_NETWORK_ROUTING_AND_ACCESS_BASELINE_2026-10-16_v1.md` — AS-IS Linux routing, Cisco ACL/NAT/DHCP/DNS, Docker/NPM, Omada guard, SPAN и read-only команды.
3. `CAPTIVPROD_ARCHITECTURE_AND_TEAM_RULES_v1.md` — Owner/Architect ownership и acceptance/GO/HOLD контракты.

## 10. Сводный статус для Architect

```text
AP_80_REACHABILITY_VLAN10=PASS
OMADA_ADOPTION_ROOT_CAUSE=FIREWALL_GUARD_BLOCK
AP_ALLOWLIST_4_IP_TCP29814_UDP29810=APPLIED_PERSISTENT
OMADA_AP_80_ADOPT=PASS
OMADA_AP_80_CONNECTED=OBSERVED
OMADA_AP_80_FULL_CONFIG_SYNC=NOT_VERIFIED
OTHER_3_AP_MIGRATION=NOT_CLAIMED
OWNER_SSID_VLAN60=SET
OWNER_PRE_AUTH_ACCESS=SET
VLAN60_DHCP_CLIENT_10.50.0.50=OBSERVED
CISCO_VLAN60_DHCP_OPTION114=PASS_SAVED
CISCO_NEW_FQDN_SPLIT_DNS=PASS_SAVED
CISCO_LEGACY_FQDN=UNCHANGED
CISCO_LEGACY_GUEST_VLAN20=UNCHANGED
CAPPORT_AFTER_SPLIT_DNS_E2E=NOT_VERIFIED
NET01_GUARDS=PASS
OLD_PORTAL_VM=UNCHANGED
OLD_OMADA_WAN_FORWARD=STILL_TO_192.168.0.222
IO_BASELINE_OLD_NEW=RECORDED
ROUTING_AND_ACCESS_BASELINE=RECORDED
ALL_AP_MIGRATION=NOT_COMPLETE
PRODUCTION_CUTOVER=HOLD
```

**Предлагаемый вердикт:** инфраструктурные prerequisites пилота и Adoption пилотной AP подтверждены; Guest Portal E2E и массовую миграцию нельзя считать принятыми до отдельных Owner/Architect gates.
