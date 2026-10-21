# CaptivPortal — актуальная дорожная карта проекта v2

**Тип документа:** постоянная проектная дорожная карта  
**Статус:** CURRENT  
**Версия:** 2.0  
**Дата актуализации:** 11 августа 2026 года  
**Проект:** CaptivPortal  
**Контрольная точка production по последнему подтверждённому status report:** `main@ab776af`

---

# 1. Назначение документа

Этот документ является текущей дорожной картой развития CaptivPortal.

Он определяет:

1. обязательные release/production gates;
2. завершённые фундаментальные этапы;
3. ближайшие функциональные этапы;
4. порядок построения слоя накопления данных;
5. границу между сбором данных и аналитикой;
6. порядок развития Visit Lifecycle;
7. порядок появления web-интерфейса и Admin Console;
8. дальнейшую Site-aware / Multi-Site / Multi-Tenant эволюцию;
9. место Grafana в архитектуре;
10. параллельные технические долги.

Исторические ТЗ, исследования и отчёты сохраняются как evidence/history, но не заменяют эту CURRENT roadmap при выборе следующего функционального этапа.

---

# 2. Основное изменение v2

Предыдущая CURRENT roadmap ставила следующим крупным функциональным этапом:

```text
Visit Lifecycle
```

а AP Monitoring Collector рассматривала как отдельное более позднее направление.

После повторного анализа уже проведённых исследований Omada Open API и обсуждения дальнейшей продуктовой архитектуры это решение изменено.

Новый основной порядок:

```text
текущие release gates
        ↓
Observation Foundation v1
        ↓
постоянное накопление наблюдений
        ↓
Visit Lifecycle
        ↓
Analytics Foundation
        ↓
Web Foundation
        ↓
Admin Console
```

Причина:

```text
данные имеют временную ценность
```

Чем раньше начинается систематический сбор и сохранение фактов, тем больше реальной исторической выборки будет доступно к моменту реализации Visit Lifecycle, Analytics и Admin Console.

---

# 3. Фундаментальный архитектурный принцип: Acquisition ≠ Analytics

Начиная с Observation Foundation действует постоянный инвариант:

```text
Collector собирает и сохраняет факты.

Analytics читает уже сохранённые факты
и не занимается их первичным сбором.
```

Запрещён целевой продуктовый поток:

```text
Analytics
→ Omada Open API
→ собрать недостающие данные
→ сделать вывод
```

Предпочтительный поток:

```text
Omada
   ↓
Collectors
   ↓
Normalization
   ↓
Persistent Observation Storage
   ↓
Repository / Query Contracts
   ↓
Analytics
   ↓
Grafana / Admin Console / Reports
```

Следствие:

```text
будущий аналитический модуль
не должен зависеть от того,
доступен ли Omada Controller в момент анализа.
```

Если данные за нужный исторический период были собраны, аналитика должна работать по сохранённой истории.

---

# 4. Три уровня данных

В дальнейшем следует различать три уровня.

## 4.1. Source Facts

Фактические значения, полученные из подтверждённых источников Omada.

Пример:

```text
RSSI = -81
SNR = 14
channel = 11
AP = EC:75:0C:18:6F:F8
```

---

## 4.2. Normalized Observations

Факты, приведённые к стабильному внутреннему контракту:

```text
observed_at
site_id
client_mac
ap_mac
ssid
radio_id
channel
rssi_dbm
snr_db
traffic_down_bytes
traffic_up_bytes
...
```

Здесь допускается:

- проверка типов;
- нормализация MAC;
- нормализация timestamps;
- унификация единиц;
- валидация диапазонов, если контракт подтверждён;
- явное `null` для отсутствующих значений.

Здесь НЕ должна появляться бизнес-интерпретация.

---

## 4.3. Analytics

Производные выводы:

```text
weak_signal = true
poor_signal_ratio = 23%
high_radio_utilization = true
possible_ap_relocation_candidate = true
```

Этот слой появляется позже.

Collector не должен заранее навязывать будущей аналитике thresholds и оценки.

---

# 5. Текущая контрольная точка

По последнему подтверждённому status report:

- production deploy `main@ab776af` выполнен;
- `captive-portal.service` после deploy — active/running;
- общий `OmadaProvider` используется как единая точка доступа к Omada;
- Authorization / AuthSession / AuthWorker находятся в production;
- CAPPORT находится в production;
- Pending Session Cleaner находится в production-контуре;
- Authorized Client Snapshot Collector реализован и используется;
- Visitor Registry production activation и observability закрыты с PASS;
- Omada OpenAPI credentials вынесены из current Git tree;
- CAPPORT discovery переведён на same-page flow;
- progress авторизации сделан монотонным;
- post-AUTHORIZED close/revalidation код находится в production.

Текущий release cycle нельзя считать полностью закрытым до прохождения оставшихся P0 gates.

---

# 6. НЕМЕДЛЕННЫЙ ЭТАП — закрытие текущего release cycle

## 6.1. P0 — live test captive-window

**Статус:** OPEN по последнему подтверждённому source status.

Проверить реальный production flow:

```text
AUTHORIZED / 100%
        ↓
close attempt
        ↓
при необходимости максимум одна revalidation/reload
        ↓
нет reload-loop
        ↓
captive-window закрывается автоматически
```

Критерии:

1. без ручного refresh;
2. подтверждённый `AUTHORIZED`;
3. максимум один reload/revalidation текущей страницы;
4. отсутствие повторной авторизации;
5. автоматическое закрытие окна;
6. минимум пять последовательных проверок.

---

## 6.2. P0 — полный Linux regression gate

На exact production/main revision выполнить:

```bash
python -m pytest -q -rs
python -m compileall -q app
git diff --check
```

Зафиксировать:

```text
commit SHA
passed
skipped
failed
```

Только фактически выполненный gate считается подтверждением.

---

## 6.3. P1 — post-restart health

Проверить:

- один application process;
- Pending Session Cleaner lifecycle;
- Snapshot Collector;
- Visitor Registry;
- Registry `ready`;
- Registry `partial=false`;
- поступление Cleaner/snapshot events;
- актуальные DB/journal counters.

Это эксплуатационная проверка, а не новый функциональный этап.

---

# 7. Завершённые фундаментальные этапы

## 7.1. Captive Authorization

**Статус:** ACTIVE / production.

Основной flow:

```text
Portal entry
→ PortalClientContext
→ AuthSessionManager
→ AuthWorker
→ Omada authorization
→ AUTHORIZED / FAILED / RESET
```

Не создавать второй независимый механизм авторизации.

---

## 7.2. CAPPORT

**Статус:** ACTIVE / production.

Включает:

- RFC 8908 CAPPORT endpoint;
- bounded client discovery;
- same-page transition;
- общий AuthSession/AuthWorker flow;
- post-authorization revalidation.

---

## 7.3. Pending Client Session Cleaner

**Статус:** ACTIVE operational module.

Назначение:

- находить stale unauthenticated sessions;
- проверять локальные защиты;
- выполнять безопасный Omada `reconnect`;
- подтверждать результат;
- вести отдельный audit journal.

Cleaner:

- не является Visitor Registry;
- не является Visit Lifecycle;
- не является Observation Foundation;
- остаётся fail-open относительно основного портала.

---

## 7.4. Authorized Client Snapshot Collector

**Статус:** CLOSED / production.

Snapshot Collector остаётся отдельным стабильным компонентом.

Его роль:

```text
AUTHORIZED
    ↓
один подробный snapshot
    ↓
стартовая фотография успешно авторизованного клиента
```

Он сохраняет, в зависимости от фактического Omada-ответа:

- MAC;
- Omada client ID;
- hostname/system name;
- device type;
- IP/IPv6;
- SSID;
- AP name/MAC;
- radio ID;
- channel;
- RSSI;
- SNR;
- signal level;
- Wi-Fi mode;
- RX/TX rate;
- uptime;
- traffic;
- packet counters;
- active/auth status;
- дополнительные raw-поля подтверждённого ответа.

### Ключевое решение v2

Snapshot Collector **не переделывается** в periodic observation collector.

Его назначение остаётся:

```text
зафиксировать состояние клиента
после окончательно успешной авторизации
```

Observation Foundation начинается после этого и решает другую задачу.

---

## 7.5. Visitor Device Registry

**Статус:** CLOSED / production / observability PASS.

Назначение:

- постоянная device card;
- стабильный `device_id`;
- first/last known state;
- история captured snapshots;
- SQLite persistence;
- поиск и дальнейшие связи.

Visitor Registry не превращается в универсальную time-series database для всех будущих observations.

---

# 8. СЛЕДУЮЩИЙ ФУНКЦИОНАЛЬНЫЙ ЭТАП — Observation Foundation v1

**Статус:** NEXT после закрытия текущих P0 gates.

Рабочее полное название:

```text
Client & AP Wireless Observation Foundation
```

Короткое название:

```text
Observation Foundation
```

---

# 9. Цель Observation Foundation

Создать постоянный слой систематического сбора и хранения максимально богатой, полезной и безопасной истории состояния:

1. подключённых Wi-Fi-клиентов;
2. точек доступа, которые их обслуживают;
3. радиоокружения и нагрузки;
4. связанных технических параметров Omada.

Главная задача этого этапа:

```text
собирать сейчас,
анализировать позже
```

Observation Foundation не обязан сейчас отвечать:

- хорошо ли стоит AP;
- нужен ли второй AP;
- плохой ли сигнал;
- является ли клиент «далёким»;
- какой тариф должен видеть метрику;
- какой график нужен клиенту.

Он обязан сохранить достаточные факты, чтобы эти вопросы можно было анализировать позже без повторного сбора истории.

---

# 10. Почему Observation Foundation идёт до Visit Lifecycle

Причина №1:

```text
исторические observations невозможно получить задним числом,
если они не были сохранены.
```

Причина №2:

к моменту создания Visit Lifecycle уже будет накоплена реальная история:

```text
AUTHORIZED snapshot
+
client observations
+
AP observations
+
offline/event context
```

Причина №3:

Visit Lifecycle сможет позже объединить:

```text
Visit
├── Device
├── initial Authorized Snapshot
├── Client Observations
├── AP Observations
├── start
└── finalization
```

Причина №4:

Admin Console и Analytics будут читать уже зрелое хранилище, а не начинать накопление данных после появления UI.

---

# 11. Observation Foundation — логические компоненты

Предварительная архитектурная декомпозиция:

```text
Observation Foundation
│
├── Acquisition
│   ├── Client Observation Collector
│   └── AP Observation Collector
│
├── Normalization
│
├── Persistence
│
├── Retention / lifecycle
│
└── Repository / Query Contracts
```

Analytics в этот этап не входит.

---

# 12. Client Observation Collector

Назначение:

периодически получать состояние активных Wi-Fi-клиентов Omada и сохранять нормализованные observations.

Предварительный полезный набор данных, если поле фактически доступно и подтверждено:

## Identity / Context

- `observed_at`;
- `site_id`;
- client MAC;
- Omada client ID;
- hostname;
- device type/category;
- vendor;
- IP;
- SSID;
- AP MAC/name.

## Radio / Connection

- radio ID / band;
- channel;
- Wi-Fi mode;
- RSSI;
- SNR;
- signal level;
- signal rank;
- RX rate;
- TX rate;
- power-save state, если подтверждено;
- uptime;
- active;
- auth status.

## Traffic

- traffic down;
- traffic up;
- packet counters, если доступны;
- иные безопасные session counters.

### Важное правило

Наличие поля в одном историческом ответе не означает автоматическую обязательность.

TASK должен проверить фактический OpenAPI contract и определить:

```text
required
optional
unknown/opaque
```

---

# 13. AP Observation Collector

Назначение:

периодически сохранять состояние точки доступа и радио, обслуживающих клиентов.

Исследование Omada Open API уже подтвердило read-only источники для:

## Identity / Health

- AP MAC;
- name;
- IP;
- model;
- firmware;
- uptime;
- CPU;
- memory.

## Ethernet / Uplink

- link rate;
- cumulative RX/TX bytes;
- cumulative packets;
- errors;
- drops;
- uplink state/related fields, если подтверждены.

## Radio 2.4 / 5 GHz

- configured/actual channel;
- frequency;
- channel width;
- TX power;
- Wi-Fi mode;
- cumulative RX/TX bytes;
- packets;
- errors;
- drops;
- retries;
- TX utilization;
- RX utilization;
- busy utilization;
- interference utilization;
- maximum PHY rate.

## Capabilities / slowly-changing state

- available channels;
- available widths;
- OFDMA support;
- OFDMA enabled;
- supported bands;
- selected configuration values.

## RF Scan

- timestamp/status;
- per-band status, если доступен и интерпретация подтверждена.

---

# 14. Текущая скорость AP

Omada отдаёт накопительные byte counters.

Observation Foundation должен сохранять исходные cumulative values.

Если в Collector вводится вычисление текущей скорости, оно должно быть строго производной технической метрикой:

```text
rate =
(new_counter - previous_counter)
* 8
/ real_interval
```

При:

```text
new_counter < previous_counter
```

значение считается reset/restart baseline, а не отрицательной скоростью.

### Важное архитектурное решение

Предпочтительно сохранять:

```text
cumulative counters
+
timestamp
```

даже если дополнительно сохраняется рассчитанная текущая скорость.

Это позволит будущей аналитике пересчитывать данные другими окнами и алгоритмами.

---

# 15. Dynamic и slow-changing observations

Не все Omada endpoints нужно опрашивать с одинаковой частотой.

## 15.1. Dynamic Client Data

Опрашивается относительно часто:

- active clients;
- AP association;
- radio/band;
- RSSI;
- SNR;
- rates;
- channel;
- traffic;
- uptime;
- auth status.

---

## 15.2. Dynamic AP Data

Опрашивается относительно часто:

- radio utilization;
- traffic counters;
- errors;
- drops;
- retries;
- actual channel;
- CPU/RAM;
- uplink counters.

---

## 15.3. Slow-changing / Configuration Data

Опрашивается реже либо при изменении:

- model;
- firmware;
- management IP config;
- available channels;
- radio capabilities;
- OFDMA support;
- configured radio settings.

Точные интервалы определяются отдельным TASK после оценки:

- числа клиентов;
- числа AP;
- нагрузки на Omada;
- объёма данных;
- желаемой временной детализации.

---

# 16. Persistent Observation Storage

Observation Foundation должен иметь собственное постоянное хранилище.

Visitor Registry DB не следует превращать в time-series storage.

Рабочая логическая граница:

```text
Visitor Registry
→ identity / device cards / captured snapshot history

Observation Storage
→ периодические client/AP observations
```

Предварительное имя может быть:

```text
observations.sqlite3
```

или другое нейтральное имя, утверждённое TASK.

Конкретная схема определяется отдельно.

---

# 17. Требования к Observation Storage

Хранилище должно позволять будущим слоям выполнять запросы минимум по:

- периоду времени;
- `site_id`;
- client MAC / `device_id`, когда связь доступна;
- AP MAC;
- SSID;
- band/radio;
- типу observation.

Должны поддерживаться эффективные выборки вида:

```text
дай observations конкретного клиента за период
```

```text
дай observations всех клиентов AP X за период
```

```text
дай radio observations AP X за период
```

```text
дай все client observations Site Y за сутки
```

Никакой Admin Console для этого этапа не требуется.

---

# 18. Site-aware contract

Observation Foundation сразу проектируется как:

```text
Site-aware, single-tenant
```

Обязательно:

- сохранять `site_id`;
- не хардкодить один Site внутри persistence contract;
- не вводить `tenant_id` заранее;
- не приравнивать Tenant к Site;
- не считать MAC глобальной identity будущего Tenant;
- не создавать новый OmadaProvider или token lifecycle без ADR.

---

# 19. Security и data minimization

Принцип «собрать максимум данных» означает:

```text
максимум полезных,
подтверждённых
и безопасных данных
```

а не сохранение любого ответа Omada без фильтрации.

Исследование показало, что некоторые endpoints могут возвращать чувствительные данные.

Особенно:

```text
/override
```

может содержать Wi-Fi password.

Запрещено:

- сохранять SSID passwords в Observation Storage;
- отправлять их в Loki;
- показывать их Grafana;
- включать raw sensitive response в exceptions;
- сохранять Access Token;
- сохранять Client Secret;
- сохранять Authorization header/cookies.

Если endpoint потенциально чувствительный, применяется explicit allowlist безопасных полей.

---

# 20. Raw data policy

Snapshot Collector уже имеет отдельный исторический контракт raw snapshot.

Observation Foundation не должен автоматически копировать эту модель на все polling endpoints.

Для periodic observations предпочтительно:

```text
whitelisted normalized fields
+
при необходимости safe source metadata
```

Полный raw response разрешается сохранять только если:

1. доказана его необходимость;
2. подтверждено отсутствие secrets;
3. определена retention policy;
4. определён размер/нагрузка;
5. это явно разрешено TASK.

---

# 21. Collector не делает бизнес-анализ

Запрещено в Observation Collector зашивать значения вида:

```text
weak_signal = true
poor_ap_placement = true
needs_second_ap = true
excellent_wifi = true
```

если это продуктовая/аналитическая интерпретация.

Collector сохраняет:

```text
rssi = -78
snr = 17
busy_util = 82
retries = ...
```

Будущая Analytics Foundation решает, что эти значения означают.

Преимущество:

новый алгоритм можно применить к старым сохранённым данным.

---

# 22. Data quality

Observation Foundation должен различать минимум:

```text
observation captured
observation partial
source unavailable
source malformed
counter reset
field unavailable
```

Нельзя подменять отсутствующие значения `0`, если `0` имеет реальный физический смысл.

Неизвестный enum не получает выдуманную текстовую интерпретацию.

---

# 23. Retention

Периодические observations потенциально создадут значительно больше данных, чем Snapshot Collector.

TASK Observation Foundation обязан определить:

- expected observations/day;
- expected DB growth/day;
- indexes;
- retention;
- cleanup;
- vacuum/maintenance strategy;
- backup expectations;
- поведение при full disk;
- fail-open boundary.

На первом single-site этапе допустима SQLite-реализация, если capacity assessment показывает достаточный запас.

Storage contract должен быть отделён repository boundary, чтобы backend можно было заменить при будущем масштабировании.

---

# 24. Fail-open

Observation Foundation является независимым operational/data компонентом.

Ошибка:

```text
Client Observer
AP Observer
Normalization
Observation DB
```

не должна:

- ломать Captive Portal;
- отменять авторизацию;
- менять AuthSession;
- менять AuthWorker;
- мешать CAPPORT;
- ломать Pending Session Cleaner;
- ломать Visitor Registry;
- показываться посетителю.

Главное правило:

```text
Observation failure
must not become CaptivPortal failure.
```

---

# 25. Использование общего OmadaProvider

Client/AP collectors используют существующий shared `OmadaProvider`.

Запрещено без отдельного ADR:

- создавать новый OAuth client;
- создавать отдельный token manager;
- создавать отдельный token cache;
- создавать отдельный provider на каждый collector.

Новые narrow provider methods добавляются в существующий provider при необходимости.

---

# 26. Первый operational output Observation Foundation

После реализации должны появиться:

```text
persistent observations
+
операторские health/quality indicators
```

Grafana на этом этапе используется только как:

```text
internal validation / observability
```

Например, чтобы убедиться:

- observations действительно поступают;
- sampling стабильный;
- нет провалов;
- значения RSSI/SNR реалистичны;
- AP counters меняются;
- counter resets классифицируются;
- DB/journal pipeline работает.

Это ещё не Analytics Foundation.

---

# 27. Grafana остаётся постоянным internal tool

Целевой принцип:

```text
Grafana = engineering observability
```

Grafana остаётся у владельца/технической команды для:

- диагностики;
- проверки новых collectors;
- проверки telemetry;
- исследования данных;
- временных панелей;
- сравнения Sites;
- расследования проблем;
- разработки будущих метрик.

Конечный коммерческий клиент прямого доступа к Grafana не получает.

---

# 28. ПОСЛЕ НАКОПЛЕНИЯ OBSERVATIONS — Visit Lifecycle v1

**Статус:** PLANNED AFTER OBSERVATION FOUNDATION.

Visit Lifecycle связывает уже существующие слои.

Целевая модель:

```text
Device
   ↓
AUTHORIZED
   ↓
Initial Snapshot
   ↓
Visit opened
   ↓
Client/AP Observations
   ↓
Offline / finalization
   ↓
Visit closed
```

---

# 29. Visit Lifecycle Phase A — Visit Start / Active Visits

Основная сущность:

```text
visit_id
```

Visit связывается минимум с:

- `device_id`;
- `site_id`;
- canonical MAC;
- authorization/session context;
- SSID;
- IP;
- AP;
- временем начала;
- initial Authorized Snapshot.

### Инвариант

Нельзя автоматически считать:

```text
одна AuthSession = одно физическое посещение
```

До TASK необходимо закрепить защиту от duplicate open visit.

Предпочтительный базовый принцип:

```text
не более одного open visit
на site_id + canonical MAC
```

---

# 30. Visit Lifecycle Phase B — Finalization

Offline/event signal закрывает только подходящее открытое посещение.

Хранить минимум:

- `offline_at`;
- `duration_seconds`;
- final status;
- итоговые доступные traffic values;
- reference на source event;
- финальный Site/SSID/AP context.

Старое offline-событие не должно закрыть более новое посещение.

---

# 31. Связь Visit и Observations

Visit Lifecycle не должен копировать все observations внутрь visit row.

Предпочтительный принцип:

```text
Visit задаёт временную/идентификационную границу.

Observation Repository хранит observations.

Query layer связывает их по:
site
client/device
time window
и другим подтверждённым ключам.
```

Это предотвращает duplication и позволяет применять будущую аналитику к полной истории.

---

# 32. Analytics Foundation

**Статус:** PLANNED AFTER VISIT LIFECYCLE.

Analytics Foundation является отдельной подсистемой.

Главный принцип:

```text
Analytics does not collect.
Analytics reads.
```

Источники:

- Visitor Registry;
- Visit Lifecycle;
- Observation Storage;
- другие утверждённые persistence layers.

Analytics не должна использовать Omada API как первичный источник исторического анализа.

---

# 33. Примеры будущей Wireless Analytics

На сохранённых observations можно будет строить:

- RSSI distribution;
- SNR distribution;
- median/percentiles;
- долю weak/poor observations;
- clients by AP;
- clients by band;
- clients by channel;
- roaming patterns, если контракт позволит;
- radio busy distribution;
- retries/errors;
- AP throughput;
- simultaneous client counts;
- correlation client signal ↔ AP load;
- distribution by time/day;
- quality changes over weeks.

---

# 34. Пример будущего анализа размещения AP

Возможный аналитический вопрос:

```text
Нужно ли переставить AP
или добавить вторую точку?
```

Analytics сможет использовать:

```text
client RSSI
client SNR
AP association
band distribution
simultaneous client count
radio utilization
retries
errors
traffic
time distribution
```

### Важная оговорка

RSSI не является точным расстоянием в метрах.

По данным допустимо анализировать:

```text
долю клиентов/наблюдений
в зоне слабого сигнала
```

но нельзя без отдельной radio-location model утверждать:

```text
клиент находился в N метрах от AP
```

---

# 35. Visitor Analytics

Analytics Foundation также сможет строить:

- unique visitor devices;
- new devices;
- returning devices;
- visits per device;
- return next day;
- return within seven days;
- average visit duration;
- average traffic per visit;
- frequent devices;
- distribution by device type;
- distribution by SSID;
- distribution by AP;
- посещаемость по времени.

Важно:

```text
unique MAC/device ≠ гарантированно unique person
```

В customer-facing UI это должно называться корректно.

---

# 36. Product / Observability Boundary

Если показатель становится частью будущего Admin Console, он должен иметь:

```text
application/query contract
+
authoritative data source
```

Запрещён основной продуктовый поток:

```text
Admin Console
→ Grafana API
→ Loki
```

Grafana может использоваться для инженерного анализа и прототипирования.

Продуктовые метрики должны читаться из application services/repositories.

---

# 37. Web Foundation — перед полноценным Admin Console

**Статус:** PLANNED.

Admin Console не должен появляться сразу после Visit Lifecycle как большой монолитный UI.

Перед ним создаётся небольшой application/web foundation.

Цель:

- сформировать Admin API boundaries;
- query/application services;
- read-only представления;
- Site context;
- admin authentication boundary;
- базовые permissions-ready contracts;
- UI shell/navigation;
- единый способ отображения ошибок/health.

---

# 38. Возможная первая Web Foundation функциональность

Минимальный read-only внутренний интерфейс может включать:

- Devices;
- Device Card;
- Visits;
- Observation lookup;
- простые Site-aware filters.

Это ещё не коммерческая Admin Console.

Он может использоваться владельцем для проверки application contracts до разработки большого UI.

Точный scope определяется отдельным TASK.

---

# 39. CaptivPortal Admin Console

**Статус:** LATER PRODUCT STAGE.

Admin Console является customer-facing product interface.

Предварительные разделы:

- Dashboard;
- Devices;
- Device Card;
- Visits;
- Wireless Quality;
- AP Health;
- Traffic;
- Reports;
- Portal Settings;
- Branding;
- позже — customer administration.

Admin Console должен быть Site-aware с первой версии.

---

# 40. Admin Console не заменяет Grafana

Целевая граница:

```text
Grafana
→ internal engineering

Admin Console
→ product/customer interface
```

Даже самый дорогой customer plan не обязан раскрывать internal engineering telemetry.

---

# 41. Admin authentication отдельно от visitor authentication

Будущий Admin Console не использует:

- `AuthSession`;
- `AuthWorker`;
- captive guest authorization;
- Omada guest auth status

как механизм входа администратора.

Visitor authentication и Admin authentication — разные security domains.

---

# 42. Portal Profile / Branding

После появления web/product foundation внешний вид portal постепенно оформляется как presentation profile.

Возможные свойства:

- display name;
- welcome title;
- subtitle;
- logo;
- background;
- accent style;
- button text;
- languages;
- terms;
- links;
- promotional blocks.

Branding не меняет AuthWorker / authorization lifecycle.

Operational configuration и customer-editable branding остаются разными классами настроек.

---

# 43. Site-aware, single-tenant до реальной коммерциализации

До появления реального второго клиента новые функции строятся по модели:

```text
Site-aware, single-tenant
```

Это означает:

- deployment один;
- Tenant entity пока отсутствует;
- customer RBAC пока отсутствует;
- `site_id` не теряется;
- public/application contracts не должны навсегда предполагать один Site.

---

# 44. Реальный второй Site

Первый реальный второй Site является продуктовым trigger.

Пример:

```text
CaptivPortal

Site: Zefer Park
Site: Restaurant-001
```

На этом этапе проверяются на практике:

- Site-aware storage;
- collectors;
- query contracts;
- Visit Lifecycle;
- analytics isolation;
- Admin API;
- branding context.

---

# 45. Multi-Site ADR

После появления реальной потребности выпускается отдельный ADR.

Минимальные вопросы:

- Site selection/context;
- data ownership;
- Site-aware collectors;
- shared provider;
- storage keys;
- query isolation;
- Visit relationships;
- branding per Site;
- admin authorization;
- observability labels.

---

# 46. Tenant architecture

Tenant вводится после реального business requirement.

Запрещено заранее считать:

```text
tenant_id == site_id
```

Один Tenant может иметь несколько Sites:

```text
Tenant: Restaurant Group

Site: Downtown
Site: Mall
Site: Airport
```

---

# 47. Customer accounts / RBAC

Будущая server-side модель:

```text
authenticated identity
        ↓
Tenant
        ↓
allowed Sites
        ↓
permissions
        ↓
allowed APIs/actions
```

Скрытие кнопки frontend не является security boundary.

---

# 48. Subscription / Entitlements

Будущая коммерческая модель:

```text
Plan
   ↓
Entitlements
   ↓
Backend enforcement
   ↓
UI capabilities
```

Рабочие названия могут быть:

```text
Basic
Standard
Professional
```

Но это один CaptivPortal/Admin Console, а не три forks.

---

# 49. Возможные customer capabilities

## Basic

- базовая сводка;
- visitor/device counts;
- минимальные показатели.

## Standard

Дополнительно:

- history;
- Visit Lifecycle;
- new/returning;
- временные графики;
- расширенная visitor analytics.

## Professional

Дополнительно:

- wireless quality;
- AP health;
- traffic analytics;
- RSSI/SNR;
- расширенные reports;
- дополнительные настройки.

Точные планы и цены не фиксируются этой roadmap.

---

# 50. Коммерческий managed service

Целевая модель:

## На стороне клиента

```text
Internet connection
+
совместимый router/gateway
+
рекомендуемая Omada AP
```

## На нашей стороне

```text
Omada Controller
CaptivPortal
Observation Storage
Visitor Registry
Visit Lifecycle
Analytics
Admin Console
Monitoring
Backups
Updates
```

Клиент работает только через собственный product interface.

---

# 51. Параллельные технические долги

После закрытия P0 они не должны автоматически блокировать каждый новый функциональный этап, но выполняются отдельными TASK.

## P1

### Omada Client Secret rotation

Owner-controlled rotation старого exposed secret.

### TLS verification

Перевести Omada connection с `VERIFY_SSL=false` на доверенную модель сертификата.

### Knowledge Base update

Отдельная documentation-задача владельца базы знаний.

## P2

### GitHub CI

Минимальный reproducible test/release gate.

### Repository cleanup

Решить legacy `/success` и ownership инфраструктурных artifacts.

---

# 52. Accepted limitation — single-process

Текущий production рассчитан на один application process.

Process-local остаются:

- AuthSession;
- retry guards;
- Cleaner action limits;
- workers;
- часть bounded state.

До multi-worker / HA требуется отдельный ADR:

- shared session storage;
- inter-process coordination;
- leader election/locking;
- persistent guards.

Observation Foundation v1 также должна учитывать текущую single-process модель и не создавать неявный multi-worker contract.

---

# 53. Требования к каждому будущему TASK

Каждый крупный TASK должен пройти три архитектурные проверки.

---

## 53.1. Data Acquisition / Analytics Boundary

1. Эта функция собирает факты или анализирует их?
2. Если собирает — где authoritative source?
3. Где сохраняются observations?
4. Можно ли выполнить будущий анализ без повторного обращения к Omada?
5. Не зашиты ли thresholds/оценки в Collector?
6. Сохраняются ли исходные cumulative counters, если это важно?
7. Не теряются ли timestamps и source context?
8. Не сохраняются ли secrets/raw sensitive data?
9. Определены ли retention и expected data growth?

---

## 53.2. Future Multi-Site Compatibility

1. Site-specific ли функция?
2. Сохраняется ли `site_id`?
3. Нет ли hardcode одного Site/SSID?
4. Не приравнивается ли Tenant к Site?
5. Не создаётся ли новый OmadaProvider/token lifecycle?
6. Можно ли добавить второй Site без переписывания public contract?

---

## 53.3. Product / Observability Boundary

1. Internal-only или customer-visible?
2. Какой authoritative data source?
3. Нужен ли application/API contract?
4. Не становится ли Grafana/Loki product backend?
5. Может ли функция зависеть от entitlement?
6. Выполняется ли access control backend?
7. Не раскрываются ли internal engineering details?

---

# 54. Актуальный ближайший порядок v2

```text
1. P0 live captive-window acceptance

2. P0 exact-main Linux regression gate

3. Post-restart Cleaner / Snapshot / Registry health

4. OBSERVATION FOUNDATION v1
   ├── Client Observation Collector
   ├── AP Observation Collector
   ├── Normalization
   ├── Persistent Observation Storage
   ├── Retention / cleanup
   └── Repository / Query contracts

5. Начать постоянное накопление observation history

6. Internal Grafana validation
   └── только проверка качества/полноты сбора

7. VISIT LIFECYCLE v1
   ├── Visit Start / Active Visit
   ├── Finalization
   └── связь с Snapshot + Observation history

8. ANALYTICS FOUNDATION
   ├── Wireless Analytics
   └── Visitor / Visit Analytics

9. WEB FOUNDATION
   ├── Admin API / query services
   ├── Site-aware context
   ├── read-only internal UI
   └── admin security boundary

10. CAPTIVPORTAL ADMIN CONSOLE

11. Portal Profile / Branding

12. Реальный второй Site / первый внешний клиент

13. Multi-Site ADR

14. Tenant architecture

15. Customer Accounts / RBAC

16. Subscription / Entitlements

17. Commercial Managed Captive Portal Service
```

Параллельно отдельными задачами:

```text
secret rotation
TLS verification
knowledge-base update
GitHub CI
repository cleanup
```

---

# 55. Главное направление проекта

На текущем этапе CaptivPortal эволюционирует не по принципу:

```text
сначала рисуем dashboard,
потом думаем, откуда брать данные
```

а по принципу:

```text
сначала строим надёжный слой фактов
        ↓
накапливаем историю
        ↓
связываем её с Visit Lifecycle
        ↓
строим независимую Analytics
        ↓
выдаём результаты через собственный Web/Admin Console
```

---

# 56. Итоговый архитектурный принцип v2

```text
Snapshot Collector
=
стартовая фотография успешной авторизации.
Его не переделываем.

Observation Foundation
=
периодический сбор и сохранение состояния клиента и AP.

Visit Lifecycle
=
временная бизнес-граница конкретного посещения.

Analytics
=
независимый downstream-потребитель сохранённых данных.

Grafana
=
наш постоянный internal engineering tool.

Admin Console
=
будущий product/customer interface.
```

Главная инвестиция ближайшего этапа:

```text
начать собирать качественную историю как можно раньше,
чтобы будущие Visit Lifecycle, Analytics и Admin Console
работали по уже накопленным фактам.
```
