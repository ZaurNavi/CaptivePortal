# TASK-RESEARCH-OMADA-CLIENT-CONTROL-01  
## Полное исследование возможностей управления клиентами через Omada Open API

**Проект:** CaptivPortal  
**Тип:** исследовательская задача / Research  
**Execution mode:** research-only  
**Исполнитель:** Omada Specialist  
**Результат:** технический исследовательский отчёт для архитектора и Tech Lead  
**Контроллер:** Omada Software Controller 5.14.31  
**Основная проверенная AP:** TP-Link EAP613(EU) v1.0  
**Цель последующей разработки:** будущий модуль `Client Control / Policy`  
**Дата постановки:** 14 августа 2026 года

---

# 1. Цель исследования

Необходимо полностью исследовать возможности **управления конечными клиентами сети через Omada Open API**.

Под клиентом понимается конечное пользовательское устройство:

- телефон;
- планшет;
- ноутбук;
- другое wired/wireless client device,

а не управляемое Omada network device вроде AP, switch или gateway.

Исследование должно ответить на главный вопрос:

> Какие действия будущая система CaptivPortal сможет безопасно выполнять над отдельным клиентом, группой клиентов или его сетевым доступом через Omada Controller?

Нас интересует не только наличие endpoint в документации, но и его **фактическая семантика на Omada Controller 5.14.31**.

Для каждой потенциальной функции необходимо определить:

1. существует ли она;
2. является ли она частью Open API;
3. поддерживает ли её фактический Controller;
4. работает ли она через используемый OAuth `client_credentials`;
5. какие permissions необходимы;
6. к каким типам клиентов применима;
7. можно ли применять её к online/offline client;
8. какое реальное действие она вызывает;
9. насколько быстро действие применяется;
10. является ли оно временным или persistent;
11. как его отменить;
12. как проверить успешность;
13. какие побочные эффекты возникают;
14. подходит ли функция для будущего CaptivPortal Client Control.

---

# 2. Причина исследования

CaptivPortal развивается от простой системы авторизации к управляемой платформе.

Уже создаются независимые уровни:

```text
Visitor / Device
        ↓
Visit Lifecycle
        ↓
Observation
        ↓
Analytics
```

Будущий самостоятельный уровень рассматривается как:

```text
Client Control / Policy
```

Его ответственность:

```text
прочитать состояние клиента
        ↓
принять административное или policy-решение
        ↓
выполнить действие через Omada
        ↓
проверить фактический результат
        ↓
сохранить audit
```

Исследование не проектирует этот модуль и не реализует его.

Его задача — определить **фактический control surface Omada**, на основании которого архитектор позже определит функции продукта.

---

# 3. Уже известный baseline

Текущая проектная документация требует строго разделять уровни подтверждения:

```text
endpoint обнаружен в документации
≠
endpoint присутствует в Swagger
≠
endpoint доступен нашему OAuth application
≠
endpoint успешно выполнен
≠
эффект операции подтверждён live
```

Наличие mutation в Swagger само по себе не разрешает считать её рабочей.

## 3.1. Уже live-tested

На Controller 5.14.31 фактически проверен:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
```

Подтверждённый эффект для pending wireless client:

```text
active=true
        ↓ reconnect
active=false
```

Клиент исчезает из active client list, но историческая карточка остаётся.

`disconnect` по ранее предполагаемому OpenAPI-пути фактически вернул HTTP 404 и не поддерживается указанным путём на проверенном Controller.

## 3.2. Schema-confirmed, но не полностью live-tested

Корневая Swagger-схема уже показывает как минимум:

```text
block
unblock
reconnect
lock-to-ap
rename client
rate limit
hotspot auth
hotspot unauth
authentication-record period modification
```

Также существуют связанные client read endpoints.

Rate Limit schema уже показывает отдельные upload/download параметры, profile/custom режимы и enable flags. Lock-to-AP также присутствует в client API.

Но большинство этих mutation пока нельзя считать полностью подтверждёнными live.

---

# 4. Главный принцип исследования

Для каждой функции применять четыре уровня доказательства.

## Level A — Documentation discovered

Функция найдена:

- в UI Open API;
- в групповой документации;
- Swagger UI;
- controller documentation.

## Level B — Schema confirmed

Определены:

- точный method;
- точный path;
- API version;
- request schema;
- response schema;
- permissions;
- документированные error codes.

## Level C — Live accepted

На тестовом клиенте Controller фактически принял запрос:

```text
HTTP
+
JSON
+
errorCode == success
```

HTTP 200 без успешного Omada `errorCode` не является успехом.

## Level D — Effect verified

После действия проверено фактическое состояние клиента и доказано, **что именно изменилось**.

Только Level D считать достаточным основанием для будущей product feature.

---

# 5. Источники исследования

Использовать в указанном порядке:

1. локальный Swagger фактического Omada Controller 5.14.31;
2. групповые OpenAPI schemas Controller;
3. фактические request/response схемы;
4. live-тесты против Controller;
5. Omada UI как дополнительный источник сравнения;
6. официальную документацию TP-Link только как вспомогательный источник.

При расхождении общей документации и локального Controller источником истины является:

```text
фактический Controller 5.14.31
+
его локальная schema
+
live behavior
```

---

# 6. Полная инвентаризация Client Control Surface

Перед live-тестами необходимо провести **полную инвентаризацию**.

Нельзя искать только известные заранее названия вроде `block` или `rate limit`.

Исследовать все API groups и endpoints, способные:

- изменить состояние клиента;
- изменить сетевой доступ клиента;
- изменить authorization;
- изменить bandwidth;
- изменить association;
- изменить IP/network properties;
- изменить persistent client settings;
- изменить policy, применяемую к клиенту;
- удалить или забыть client state;
- выполнить batch action над клиентами.

Минимально проверить группы:

```text
Client
Authorized Client / Hotspot
Authentication
Bandwidth Control
Gateway QoS
ACL
MAC Filtering
IP-MAC Binding
Application Control
Client Insight
```

Если обнаружены другие релевантные группы — включить их.

---

# 7. Отдельно исследовать версии API

Проверить:

```text
v1
v2
```

и любые другие client-facing Open API versions, реально присутствующие в Controller.

Если одна и та же операция существует в нескольких версиях:

- сравнить schemas;
- сравнить возможности;
- определить предпочтительный вариант;
- указать deprecated/legacy вариант, если это можно доказать.

---

# 8. Direct Client Actions

Полностью исследовать direct actions над одним client.

## 8.1. Block

Определить:

- можно ли block активного wireless client;
- можно ли block авторизованного клиента;
- можно ли block `authStatus=1`;
- можно ли block offline known client;
- разрывается ли существующее соединение немедленно;
- исчезает ли клиент из active list;
- меняется ли `blocked`;
- меняется ли `active`;
- меняется ли `authStatus`;
- сохраняется ли hotspot authorization record;
- может ли устройство заново association к AP;
- получает ли DHCP;
- открывается ли Captive Portal;
- что видит пользователь;
- сохраняется ли block после Wi-Fi reconnect;
- сохраняется ли block после Controller restart;
- распространяется ли block на Site или глобально;
- зависит ли действие от MAC randomization.

После этого определить точный механизм отмены.

---

# 9. Unblock

Исследовать обратное действие.

После unblock проверить:

- `blocked`;
- возможность association;
- DHCP;
- появление active client;
- необходимость повторной authorization;
- сохраняется ли предыдущая Hotspot authorization;
- требуется ли reconnect вручную;
- время до восстановления доступа.

Особенно определить:

> Unblock просто снимает administrative flag или также восстанавливает предыдущее состояние доступа?

---

# 10. Reconnect

Предыдущий pending-session сценарий уже подтверждён, но для будущего Client Control исследование расширить.

Проверить отдельно:

### Scenario R1

```text
active=true
authStatus=1
```

### Scenario R2

```text
active=true
authStatus=2
```

### Scenario R3

обычный wireless client без Captive Portal, если это возможно безопасно проверить.

Определить:

- происходит ли deassociation;
- закрывается ли текущая Omada client session;
- теряется ли authorization;
- создаётся ли при повторном подключении новая controller session;
- сохраняются ли rate limits;
- сохраняется ли lock-to-AP;
- сохраняется ли block state;
- сохраняется ли fixed IP;
- появляются ли webhook/events;
- сколько фактически занимает операция.

---

# 11. Hotspot Auth

Исследовать существующую client authorization operation не только в контексте CaptivPortal.

Для тестового pending client определить:

- обязательное исходное состояние;
- что происходит с `authStatus`;
- требуется ли `active=true`;
- происходит ли изменение без reconnect;
- появляется ли authentication record;
- какие start/end/duration значения получает record;
- можно ли auth offline client;
- что происходит при повторном Auth уже авторизованного клиента;
- идемпотентна ли операция;
- какие ошибки возвращаются.

---

# 12. Hotspot Unauth

Это одна из наиболее важных функций будущего Client Control.

Проверить на реальном авторизованном тестовом клиенте:

```text
active=true
authStatus=2
```

После Unauth определить:

- остаётся ли клиент associated;
- остаётся ли `active=true`;
- становится ли `authStatus=1`;
- прекращается ли Internet access;
- появляется ли Captive Portal;
- разрывается ли Wi-Fi;
- удаляется или изменяется authentication record;
- создаётся ли webhook/event;
- может ли client немедленно заново авторизоваться;
- чем Unauth принципиально отличается от Reconnect;
- чем Unauth отличается от Block.

Это исследование должно дать чёткое определение:

```text
Unauth = ?
Reconnect = ?
Block = ?
```

и показать три разные семантики.

---

# 13. Rate Limit — персональное ограничение скорости

Полностью исследовать индивидуальный Client Rate Limit.

Минимум определить:

- наличие custom mode;
- наличие profile mode;
- значение `mode`;
- назначение `rateLimitProfileId`;
- upload enable;
- download enable;
- upload unit;
- download unit;
- upload limit;
- download limit;
- допустимые units;
- минимальное значение;
- максимальное значение;
- поведение значения `0`;
- способ полного отключения ограничения.

Не угадывать значения enum.

Каждый enum подтвердить schema или live behavior.

---

# 14. Live Rate Limit tests

На выделенном клиенте последовательно проверить:

### RL1 — только Download Limit

### RL2 — только Upload Limit

### RL3 — оба направления

### RL4 — разные Upload/Download limits

### RL5 — снять ограничения

### RL6 — назначить profile, если profiles доступны

После каждого изменения определить:

- мгновенно ли применяется limit;
- требуется ли reconnect;
- отображается ли новое состояние в client card;
- реальная скорость соответствует установленной величине или нет;
- какую точность имеет shaping;
- сохраняется ли ограничение после reconnect;
- сохраняется ли после client offline/online;
- сохраняется ли после Controller restart;
- применяется ли к MAC либо конкретной сессии;
- отличается ли поведение wireless/wired.

Критически важно определить фактические **units**.

Нельзя выводить Mbps/Kbps только из предположения по числовому enum.

---

# 15. Rate Limit limits и capacity

Schema уже содержит отдельную ошибку, связанную с максимальным количеством клиентов, которым может быть назначен Rate Limit.

Необходимо выяснить:

- существует ли фактический controller limit;
- где он задаётся;
- зависит ли он от license/model/version;
- custom и profile entries используют один limit или разные;
- можно ли прочитать количество уже использованных entries;
- как система должна определить достижение capacity до mutation.

Не требуется заполнять production Controller сотнями записей ради достижения лимита.

Если safe live proof невозможен — зафиксировать как schema-confirmed limitation.

---

# 16. Lock Client to AP

Полностью исследовать `Lock to AP`.

Определить:

- только ли wireless clients поддерживаются;
- можно ли указать одну AP;
- можно ли указать несколько AP;
- значение enable/disable;
- формат AP identity;
- сохраняется ли настройка для offline client;
- сохраняется ли после reconnect;
- сохраняется ли после Controller restart;
- что происходит при roaming;
- что происходит, когда preferred AP недоступна;
- подключается ли клиент к другой разрешённой AP;
- что происходит, если все разрешённые AP недоступны;
- как полностью снять lock.

Отдельно проверить documented конфликт:

```text
blocked client
vs
lock-to-AP
```

Schema сообщает, что blocked client нельзя Lock to wireless device.

Подтвердить фактическое поведение и errorCode.

---

# 17. Client IP Setting

Исследовать возможность изменения client IP setting.

Schema уже показывает возможность фиксированного address configuration.

Нужно определить:

- что именно означает `useFixedAddr`;
- роль `netId`;
- роль `ip`;
- роль `serverType`;
- роль `serverMac`;
- роль `serverStackId`;
- является ли это DHCP reservation;
- требуется ли Omada Gateway/DHCP;
- работает ли функция, если DHCP обслуживает сторонний router;
- применяется ли настройка online;
- требуется ли renew/reconnect;
- можно ли назначать offline known client;
- как настройку удалить.

### Важное ограничение

Не менять production IP test client, если существует риск:

- IP conflict;
- потери management;
- нарушения DHCP.

При невозможности безопасного live-test:

```text
schema verification
+
UI correlation
+
controlled lab recommendation
```

достаточны, но Level D не присваивать.

---

# 18. Client Name

Исследовать административное переименование клиента.

Определить:

- максимальную длину;
- допустимые символы;
- Unicode;
- пустое значение;
- способ сбросить custom name;
- сохраняется ли имя offline;
- сохраняется ли после Controller restart;
- является ли имя Site-specific;
- что происходит при MAC randomization;
- отличается ли custom name от hostname/controller detected name.

---

# 19. Authentication Records

Полностью исследовать:

```text
Hotspot authentication records
```

Определить available fields минимум:

- record id;
- client MAC;
- IP;
- auth type;
- SSID/network;
- start;
- end;
- duration;
- status;
- download;
- upload.

Исследовать связь:

```text
client
↔
current authStatus
↔
authentication record
```

---

# 20. Modify Authentication Period

Исследовать mutation периода действующей authorization.

Документация Controller содержит отдельную operation изменения периода authentication record.

Определить:

- единицу `period`;
- означает ли операция именно extension или установку нового периода;
- можно ли увеличить период;
- можно ли уменьшить период;
- можно ли установить zero;
- maximum;
- minimum;
- когда начинается отсчёт;
- изменяется ли `end`;
- что происходит при уже expired record;
- можно ли изменить offline client record;
- что происходит при достижении нового срока;
- выполняется ли automatic unauth;
- разрывается ли Wi-Fi;
- требуется ли новый Captive Portal authorization.

---

# 21. Disconnect

Повторно исследовать все документированные варианты с названием:

```text
Disconnect client
Kick client
Disconnect
```

Важно:

ранее предполагаемый:

```text
POST .../clients/{clientMac}/disconnect
```

на Controller 5.14.31 дал HTTP 404 и в нашем подтверждённом OpenAPI contract считается unsupported.

Однако групповая Client-документация перечисляет `Disconnect the client`.

Поэтому необходимо выяснить:

- существует ли другой path;
- относится ли операция к internal Controller API, а не Open API;
- относится ли она только к некоторым client types;
- доступна ли через OAuth;
- является ли запись документации legacy/stale.

Ничего не предполагать.

---

# 22. Delete Client

Аналогично исследовать:

```text
Delete client
Batch delete clients
```

Нужно выяснить:

- существует ли Open API path;
- что именно удаляется:
  - active session;
  - known-client record;
  - historical data;
  - configuration;
- можно ли удалить active client;
- что происходит при повторном появлении MAC;
- остаются ли history/auth records;
- отличается ли Delete от Block;
- отличается ли Delete от Forget.

Ранее `DELETE /clients/{clientMac}` не был подтверждён корневой схемой.

Если операция является internal/private API — так и зафиксировать и **не предлагать её для CaptivPortal**.

---

# 23. Reboot Client

Групповая Client-документация также содержит операцию с названием:

```text
Reboot the client
```

Необходимо выяснить, что это означает.

Определить:

- относится ли к обычным Wi-Fi clients;
- относится ли только к VIGI/Omada-capable devices;
- какой client capability необходим;
- существует ли public Open API endpoint;
- безопасно ли действие;
- какой реальный эффект.

Не выполнять live reboot устройства, пока не доказано, что тестовое устройство является допустимой безопасной целью.

---

# 24. Batch Client Operations

Групповая документация перечисляет batch client actions.

Исследовать:

- Batch Config;
- Batch Delete;
- любые другие batch mutation.

Для каждой определить:

- public Open API или internal;
- максимальный batch size;
- atomic или partial behavior;
- response per client или общий;
- что происходит при одной ошибочной записи;
- supports mixed online/offline;
- есть ли rate limits;
- подходит ли механизм для будущих mass policies.

### Live limitation

Batch destructive action на production guest clients запрещён.

Live-test допускается только:

- на специально выделенной test group;
- если гарантирован rollback;
- без воздействия на посетителей.

---

# 25. Known / Offline Clients

Будущий Client Control должен работать не только с тем, кто online сейчас.

Исследовать возможности Open API для:

```text
known clients
offline clients
historical clients
```

Для каждой mutation определить одну из категорий:

```text
online only
known client allowed
offline configuration allowed
session-only
unknown
```

Особенно это требуется для:

- Block;
- Unblock;
- Name;
- Rate Limit;
- Lock-to-AP;
- IP Setting.

---

# 26. Persistence Matrix

Для каждого действия заполнить persistence matrix.

Проверить состояние после:

```text
immediately after action
Wi-Fi reconnect
client offline → online
AP roaming
AP restart — если безопасно и необходимо
Controller restart — только если согласовано
new Hotspot authorization
```

Минимальная классификация:

```text
session-only
persistent per client/MAC
persistent per Site
profile-based
unknown
```

---

# 27. Interaction Matrix

Отдельно исследовать взаимодействие функций.

Минимальные сочетания:

```text
Block + Rate Limit
Block + Lock-to-AP
Rate Limit + Reconnect
Rate Limit + Unauth
Rate Limit + new Auth
Lock-to-AP + Reconnect
Lock-to-AP + Block
Unauth + Reconnect
Unauth + Block
```

Для каждой комбинации определить:

- разрешена ли;
- какая операция имеет приоритет;
- сохраняется ли предыдущая настройка;
- требуется ли сначала отменить другой setting.

Не требуется проверять бессмысленные или опасные комбинации, если schema уже однозначно запрещает их. В таком случае достаточно доказательства schema + error contract.

---

# 28. Indirect Policy Control

Помимо direct client actions исследовать, существуют ли Open API механизмы, которые потенциально позволяют будущему CaptivPortal управлять одним клиентом или группой через policy.

Минимум:

```text
Bandwidth Control
Gateway QoS
ACL
MAC Filtering
Application Control
Authentication policies
IP-MAC Binding
```

Для каждого ответить:

1. можно ли policy targeting выполнить по:
   - MAC;
   - IP;
   - client ID;
   - profile;
   - group;
   - SSID;
   - network;
2. применима ли policy к одному client;
3. применяется ли мгновенно;
4. persistent ли она;
5. существует ли safe rollback;
6. отличается ли от direct client Rate Limit/Block;
7. имеет ли смысл включать её в будущий Client Control или оставить Network Policy subsystem.

Этот раздел в первую очередь discovery/schema research.

Не менять production ACL/QoS/MAC Filtering без отдельного разрешения.

---

# 29. Permissions Matrix

Для каждого endpoint определить точное необходимое Open API permission.

Например:

```text
Site Clients Manager View Only
Site Clients Manager Modify
Site Hotspot Manager View Only
Site Hotspot Manager Modify
...
```

Сформировать итоговую матрицу:

| Capability | Read permission | Modify permission |
|---|---|---|

Также определить:

- достаточно ли одной future service application;
- нужен ли более широкий permission scope;
- можно ли разделить read и control credentials в будущем.

Последний вопрос является только рекомендацией исследователя, не архитектурным решением.

---

# 30. OAuth Compatibility

Для каждой mutation подтвердить:

```text
client_credentials supported
```

или:

```text
authorization-code only
```

или:

```text
не подтверждено
```

Если endpoint присутствует, но возвращает ошибку о неподдерживаемом grant type, это отдельный результат.

---

# 31. API Rate Limits

Исследовать общие ограничения Open API:

- HTTP 429;
- request rate;
- ограничения mutation;
- cooldown;
- concurrent modification;
- client action limits;
- per-site limits.

Не проводить DoS/load testing.

Использовать schema/documented errors и ограниченные безопасные проверки.

---

# 32. Error Code Catalogue

Для каждой потенциальной Client Control операции составить список документированных и фактически наблюдавшихся error codes.

Минимально классифицировать:

```text
permission denied
client does not exist
client offline
unsupported client type
blocked client conflict
capacity limit
invalid setting
network/controller unavailable
operation already in progress
token expired
rate limited
unknown
```

Для каждого фактически полученного error code сохранить:

```text
errorCode
msg
operation
precondition
```

Без secrets.

---

# 33. Event / Webhook Effects

Для каждой live mutation проверить, вызывает ли она observable controller event или normalized webhook.

Особенно:

```text
Reconnect
Block
Unblock
Unauth
Auth
Lock-to-AP
```

Определить:

- client offline event;
- client online event;
- authorization event;
- administrative event;
- отсутствие события.

Это важно для будущего Visit Lifecycle и audit/control correlation.

Mutation не должна ошибочно интерпретироваться будущей системой как естественное пользовательское поведение, если Omada позволяет отличить administrative action.

---

# 34. Timing / Eventual Consistency

Для каждой live action измерить ориентировочно:

```text
T0 — Controller принял mutation
T1 — client detail изменился
T2 — active list изменился
T3 — физическое состояние клиента изменилось
T4 — event/webhook появился
```

Не требуется высокоточная performance benchmark.

Необходимо понять порядок величин:

```text
immediate
<1 s
несколько секунд
десятки секунд
```

Это понадобится будущему verification mechanism.

---

# 35. Verification Contract

Для каждой функции определить, каким read-back способом можно доказать успешность.

Например:

```text
Block
→ blocked == true
+ состояние association

Rate Limit
→ client.rateLimit
+ реальная traffic verification

Lock-to-AP
→ clientLockToApSetting

Unauth
→ authStatus
+ authentication record
+ Internet access
```

Общий принцип:

> `errorCode=0` означает, что Controller принял операцию, но не является достаточным доказательством достижения требуемого состояния.

Для каждой mutation должен существовать proposed verification method либо явное:

```text
reliable verification unavailable
```

---

# 36. Reversibility

Для каждой capability классифицировать:

```text
fully reversible
reversible with reconnect
reversible with separate mutation
persistent but removable
destructive
unknown
```

Указать точный conceptual rollback.

---

# 37. Security и безопасность исследования

Использовать только специально выделенные тестовые клиенты.

Запрещено выполнять mutation над случайными посетителями сети.

В отчёт запрещено помещать:

- Access Token;
- Client Secret;
- Authorization header;
- Controller admin password;
- Wi-Fi passwords;
- cookies;
- секретные response fields.

MAC тестового устройства разрешено фиксировать в техническом отчёте, если это необходимо для воспроизводимости.

---

# 38. Protection Production Network

Перед каждой live mutation:

1. подтвердить test client;
2. зафиксировать исходное состояние;
3. определить rollback;
4. выполнить только одну исследуемую mutation;
5. проверить результат;
6. выполнить rollback;
7. подтвердить восстановление нормальной работы;
8. только после этого переходить к следующему действию.

Если rollback неизвестен:

```text
mutation не выполнять
```

до определения безопасного возврата.

---

# 39. Отдельно не менять CaptivPortal

В рамках Research запрещено:

- писать новый CaptivPortal module;
- менять OmadaProvider;
- менять AuthWorker;
- менять CAPPORT;
- менять Pending Session Cleaner;
- менять Observation;
- менять Visitor Registry;
- менять Visit Lifecycle;
- менять production database;
- менять Grafana;
- менять Alloy/Loki;
- менять systemd.

Задача исследует Omada.

---

# 40. Классификация каждой обнаруженной функции

В итоговом отчёте каждой функции присвоить один status:

### VERIFIED_SAFE

Endpoint и фактическая семантика live подтверждены, есть read-back verification и rollback.

### VERIFIED_WITH_CONDITIONS

Работает, но требует определённых условий или имеет значимые ограничения.

### SCHEMA_CONFIRMED

Есть в актуальной schema, но live effect не проверен.

### DOCUMENTED_ONLY

Обнаружено в документации, но не подтверждено фактической OpenAPI schema.

### INTERNAL_NOT_OPENAPI

Controller имеет внутреннюю функцию, но она не является пригодным публичным Open API contract.

### UNSUPPORTED_ON_5_14_31

Фактический Controller не поддерживает исследованный вариант.

### UNSAFE_FOR_PRODUCT

Технически существует, но использовать её из CaptivPortal не рекомендуется.

### NOT_APPLICABLE

Функция относится не к конечным client devices.

---

# 41. Обязательная Capability Matrix

Итоговый отчёт должен содержать единую таблицу минимум с такими колонками:

| Capability | API version | Method/path | Permission | Online | Offline | Live tested | Effect verified | Persistent | Verification | Rollback | Product verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|

В неё должны попасть **все найденные client mutations**, включая неподдержанные или internal.

---

# 42. Обязательная State Effect Matrix

Отдельная таблица:

| Action | active | authStatus | blocked | Wi-Fi association | Internet | Auth record | Rate Limit | Lock-to-AP |
|---|---|---|---|---|---|---|---|---|

Значения:

```text
unchanged
changed to ...
removed
preserved
unknown
not applicable
```

Это должно наглядно показать разницу между:

```text
Reconnect
Unauth
Block
```

---

# 43. Обязательная Persistence Matrix

| Setting/Action | Reconnect | Offline/Online | New Auth | Controller Restart | Persistent identity |
|---|---|---|---|---|---|

Минимум включить:

```text
Block
Rate Limit
Lock-to-AP
Client Name
IP Setting
Authentication Period
```

---

# 44. Product Recommendation

После технических результатов специалист должен дать **не архитектуру**, а техническую рекомендацию по пригодности каждой capability.

Разделить на:

## Candidate v1

Простые, хорошо проверяемые, обратимые функции.

## Candidate later

Полезны, но требуют более сложных policy/permission/verification механизмов.

## Infrastructure-dependent

Зависят от наличия Omada Gateway/DHCP или конкретной topology.

## Do not expose

Не подходят для customer-facing Client Control.

Это только input архитектору.

---

# 45. Особо ожидаемые кандидаты будущего модуля

Исследование не должно заранее считать их утверждёнными, но после выполнения должно дать окончательный verdict минимум для:

```text
View current client state
Reconnect
Block
Unblock
Authorize
Unauthorize
Set Download Limit
Set Upload Limit
Remove Rate Limit
Apply Rate Limit Profile
Lock to AP
Unlock from AP
Rename Client
Set/Clear Fixed IP
Read Authentication Record
Extend/Modify Authorization Period
Delete/Known-client operations
Batch Client Actions
```

И добавить всё новое, что будет найдено.

---

# 46. Отдельный вопрос: что можно сделать автоматически

Для каждой VERIFIED capability указать:

```text
safe for manual administrator action
safe for automated policy with protections
manual-only recommended
not recommended
```

Примеры будущих use cases, которые необходимо оценить технически:

```text
администратор вручную блокирует посетителя

после превышения quota система ограничивает скорость

после окончания оплаченного времени система снимает authorization

VIP client получает другой Rate Limit profile

служебное устройство закрепляется за конкретной AP
```

Никакие такие автоматические policies в рамках исследования не реализовывать.

---

# 47. Отдельный вопрос: Multi-Site readiness

Для каждой настройки определить её identity scope:

```text
Controller-wide
Site-specific
client/MAC-specific
authentication-record-specific
profile-specific
```

Особенно проверить:

> Один и тот же MAC в двух Sites — является ли Block/RateLimit/Name/Lock настройкой одного Site или общей настройкой Controller?

Если live проверить невозможно, указать:

```text
not verified
```

Не делать предположение.

---

# 48. Исследование MAC Randomization

Концептуально определить влияние randomized/private MAC.

Для MAC-based actions ответить:

- идентичность привязана к конкретному MAC;
- новая randomized MAC считается новым client или нет;
- переносится ли policy;
- может ли Client Control гарантировать persistent policy для устройств с rotating MAC.

Не требуется специально обходить механизмы privacy ОС.

---

# 49. Финальный отчёт

Результат исследования оформить отдельным документом:

```text
Omada_Client_Control_OpenAPI_Research_Report_2026-08.md
```

или DOCX с аналогичным названием.

Минимальная структура:

1. Executive summary.
2. Проверенная инфраструктура.
3. Controller/API version.
4. Методика исследования.
5. Полный inventory client-control endpoints.
6. Permissions.
7. Direct Client Actions.
8. Hotspot Auth/Unauth.
9. Rate Limit.
10. Lock-to-AP.
11. IP Setting.
12. Client Name.
13. Authentication Records/Period.
14. Delete/Disconnect/Reboot.
15. Batch Operations.
16. Indirect Policy mechanisms.
17. Offline/known clients.
18. Interaction Matrix.
19. Persistence Matrix.
20. Event/Webhook behavior.
21. Timing.
22. Error codes.
23. Security/reversibility.
24. Capability Matrix.
25. Product suitability.
26. Unsupported/internal operations.
27. Open questions.
28. Final conclusions.

---

# 50. Требования к доказательствам

Для каждого live-теста фиксировать:

```text
operation
test client state before
HTTP status
Omada errorCode
safe response shape
state immediately after
state after bounded wait
active-list result
auth record result — если применимо
physical/network effect
rollback
state after rollback
```

Необходимо приводить реальные факты, а не формулировки вроде:

```text
"должно блокировать"
"скорее всего сохраняется"
"вероятно Mbps"
```

Если не проверено:

```text
NOT VERIFIED
```

---

# 51. Acceptance Criteria

Исследование считается завершённым только если одновременно:

- проинвентаризирован весь client-related Open API surface Controller 5.14.31;
- изучены v1/v2 client APIs;
- известные direct mutations не оставлены без verdict;
- Block/Unblock имеют фактическую семантику;
- Reconnect исследован и для authorized client;
- Auth/Unauth различены экспериментально;
- Rate Limit полностью разобран по schema, units и persistence;
- выполнен безопасный live Rate Limit test;
- Lock-to-AP исследован;
- IP Setting классифицирован по применимости;
- Authentication Period исследован;
- Disconnect/Delete/Reboot получили однозначную классификацию;
- batch operations классифицированы;
- indirect policy mechanisms проинвентаризированы;
- online/offline applicability указана;
- permissions указаны;
- OAuth compatibility указана;
- persistence указана;
- rollback указан;
- verification указан;
- events/webhooks указаны;
- errors перечислены;
- полный Capability Matrix подготовлен;
- Product Recommendation подготовлена;
- ни один неподтверждённый endpoint не объявлен рабочим;
- production visitors не затронуты;
- secrets в отчёт не попали;
- CaptivPortal code не изменялся.

---

# 52. Главный итог, который должен получить архитектор

После отчёта архитектор должен иметь возможность открыть одну таблицу и однозначно ответить:

```text
Что Omada позволяет CaptivPortal делать с клиентом?
```

и для каждой функции видеть:

```text
что можно сделать
кому можно сделать
при каком состоянии
как долго действует
что реально происходит
как проверить результат
как отменить
какие риски
можно ли автоматизировать
стоит ли включать в продукт
```

Ожидаемый результат исследования — фактическая техническая основа для будущего:

```text
TASK-CLIENT-CONTROL-FOUNDATION-01
```

Но архитектуру, persistence, API CaptivPortal, UI и implementation будущего модуля в рамках настоящего Research не проектировать.