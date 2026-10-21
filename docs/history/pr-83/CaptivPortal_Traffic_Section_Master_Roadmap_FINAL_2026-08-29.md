# CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic

## FINAL v1

**Проект:** CaptivPortal  
**Продуктовая область:** Admin Console → Traffic  
**Тип документа:** Генеральная продуктовая / архитектурная дорожная карта  
**Статус:** `FINAL — APPROVED ROADMAP`  
**Дата финализации:** 2026-08-29  
**Разрешение на реализацию отдельных TASK:** `НЕ ВЫДАНО ЭТИМ ДОКУМЕНТОМ`  
**Разрешение на изменение acquisition/schema:** `НЕ ВЫДАНО ЭТИМ ДОКУМЕНТОМ`  
**Разрешение на production activation:** `НЕ ВЫДАНО ЭТИМ ДОКУМЕНТОМ`

## 0. Baseline и принятые источники

На момент финализации:

```text
main = c719525a1a2a324a0959597c993b99a82bf465b0
```

Последнее изменение `main` — PR #82 `Docs: canonicalize Central Lab testing ownership`. После него на момент финализации новых коммитов не было.

Канонические evidence sources для этой Roadmap:

```text
TECH LEAD REVIEW — Admin Console Traffic Section Roadmap v1

TRAFFIC-SOURCE-RESEARCH-01
Omada Traffic Read Surface Research

Omada_Traffic_Read_Surface_Research_Report_2026-08
Omada_Traffic_Read_Surface_Endpoint_Inventory_2026-08
Omada_Traffic_Read_Surface_Raw_Evidence_2026-08
```

Research environment:

```text
Omada Software Controller 5.14.32.3
Site: Home
Test SSID: Zefer_Parki
```

Runtime-specific findings (`dxData`, historical granularity, snapshot publication timing) считаются подтверждёнными для Controller `5.14.32.3` и не объявляются вечным universal Omada contract.

---

# 1. Цель

Создать самостоятельный domain:

```text
Admin Console → Traffic
```

Traffic становится основной product surface для:

- Current Site Network Throughput;
- Historical Site Network Throughput;
- Current/Historical AP Traffic;
- Period Statistics;
- Peak Load Period;
- AP Traffic Share;
- Online Guests Traffic;
- Completed Guest Session Traffic;
- Traffic Evidence / Quality.

Traffic должен быть reusable semantic owner. Будущий Home получает compact summaries из утверждённых Traffic contracts, а не создаёт параллельные расчёты.

---

# 2. Home остаётся frozen

В рамках Traffic Section v1:

```text
дальнейшее Traffic UI-развитие Home = FROZEN
```

Не входят:

- новые Traffic cards в Home;
- изменение Home layout;
- Home-specific Traffic calculations;
- Web Designer scope для Home.

Future Home candidates:

```text
Top Consumers by Current Rate
Top Consumers by Traffic Volume
```

Preferred:

```text
Traffic semantic owner
→ reusable summary contract
→ Home
```

---

# 3. Главный semantic invariant

Нет одной универсальной metric `Traffic`.

Минимальное разделение:

```text
A. NETWORK TRAFFIC
   AP / network throughput evidence
   unit: Mbps

B. GUEST SESSION TRAFFIC
   completed guest-session reported traffic
   unit: bytes / MB / GB
   qualifier: Estimated
```

Запрещено объединять их в Universal Traffic.

Каждая metric обязана определить:

- exact name;
- authoritative source;
- Site/scope;
- time semantics;
- unit;
- freshness;
- coverage;
- provenance;
- partial / insufficient / unavailable behavior.

---

# 4. Canonical source policy после исследования

## 4.1 Current Network Traffic

Canonical v1 path:

```text
Omada current AP primitives
→ Observation acquisition
→ persisted AP facts
→ CurrentTrafficReadService
→ Admin
```

Superior Site-wide current primitive не найден.

Следовательно:

```text
TRAFFIC-01
→ REUSE EXISTING CurrentTrafficReadService
```

Запрещено:

```text
Admin → Omada
Browser → Omada
new Current Traffic collector
second Site-current calculation owner
```

## 4.2 Historical Network Traffic

Canonical v1:

```text
persisted Observation AP history
→ TRAFFIC-02-READ
→ Site/AP/Statistics/Peak/Share
```

Native Omada:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
```

имеют роль:

```text
VALIDATION / REFERENCE
```

а не product source v1.

## 4.3 Current client traffic

Canonical base:

```text
Current State persisted current client counters/context
```

Research доказал:

```text
trafficDown / trafficUp
= cumulative bytes текущей Omada connection
```

`rxRate/txRate` = PHY/negotiated rates и запрещены как actual throughput.

`activity` = actual downlink short-window/point sample, но не symmetric Download+Upload contract.

## 4.4 Completed Guest Session Traffic

Canonical v1:

```text
Visit Lifecycle
→ visit_source_events
→ reported_traffic_total_bytes
```

Omada `past-connection` не заменяет Visit Lifecycle.

## 4.5 SSID Traffic

Trustworthy stable public SSID current/history Traffic source не найден.

Запрещено выдавать Site AP Traffic за `Zefer_Parki Traffic`, `SSID Traffic` или `Guest Network Throughput`.

## 4.6 Gateway/WAN

Cisco остаётся guest gateway/DHCP authority. Omada Gateway WAN/DPI/Application Analytics не являются authoritative Traffic source для этой topology.

---

# 5. Cross-surface semantic identity

## Current Network

При одинаковых Site/cycle/evaluation/source policy:

```text
Home Traffic Now
=
Traffic Section Current Network Throughput
```

Идентичность для:

```text
cycle_id
selected_source
Download
Upload
Total
freshness
coverage
provenance/quality
```

Preferred:

```text
CurrentTrafficReadService
→ shared application/serialization contract
→ Home + Traffic
```

## Completed Guest Sessions

При одинаковых Site/guest scope/[from,to)/watermark:

```text
Traffic Completed Guest Session Traffic
=
Home Activity Traffic
```

Presentation может отличаться, semantics/result — нет.

---

# 6. TRAFFIC-00 — Traffic Section Foundation

Обязательный первый самостоятельный TASK.

Создаёт только:

```text
AdminPage: traffic
/admin/sites/<site_id>/traffic
Traffic navigation entry
Traffic template/page shell
WEB_ADMIN_TRAFFIC_ENABLED=false
safe Site-scoped page context
Traffic frontend orchestration boundary
shared loading/error containers
```

Не создаёт Traffic calculations, historical model, direct Omada path, new acquisition или Traffic DB.

Feature flag управляет только Traffic product exposure.

Disabled:

```text
no Traffic nav/page/product APIs/frontend
```

Но НЕ:

```text
stop Observation/Analytics/CurrentTrafficReadService/
Current State/Visit Lifecycle/Home
```

```text
Traffic product flag != shared service lifecycle switch
```

---

# 7. TRAFFIC-01 — Current Network Throughput

Плашка:

```text
Download Now
Upload Now
Total Now
```

Unit: `Mbps`.

Также:

```text
selected source family
freshness
coverage
provenance/reason
```

Canonical owner: `CurrentTrafficReadService`.

Research дополнительно подтвердил direction semantics:

```text
AP Download ≈ wired down / LAN RX
AP Upload   ≈ wired up / LAN TX

LAN RX ≈ RADIO TX ≈ CLIENT DOWN
CLIENT UP ≈ RADIO RX ≈ LAN TX
```

`wired_activity_raw` — diagnostic/cross-check, не replacement directional rates.

Central Lab invariant:

```text
Traffic Current = Home Traffic Current
```

---

# 8. TRAFFIC-02-READ — Historical Network Traffic Read Foundation

Обязательный backend/read foundation и **единственный semantic owner historical Network Traffic v1**.

```text
Observation persisted AP history
→ Historical Network Traffic Read Foundation
→ canonical bounded historical contract
```

Переиспользуют:

```text
TRAFFIC-02
TRAFFIC-03
TRAFFIC-04
TRAFFIC-05
TRAFFIC-06
TRAFFIC-10
TRAFFIC-11
TRAFFIC-12
```

Запрещено пять независимых algorithms для History/Statistics/Peak/AP/Share.

---

# 9. Historical source-family selection

`TRAFFIC-02-READ` обязан определить source-selection unit.

Preferred:

```text
one canonical Site bucket
→ one selected source family
→ all comparable AP rows in bucket use same family
```

Family может меняться между buckets при evidence-driven fallback.

Запрещено в одном bucket смешивать wired и LAN между AP и затем суммировать как Site total.

Transitions входят в provenance/quality.

---

# 10. Shared Network range — v1

Один selected range используется синхронно:

```text
TRAFFIC-02 History
TRAFFIC-03 Statistics
TRAFFIC-04 Peak Load
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Traffic Share
```

Initial:

```text
24h
7d
```

Future:

```text
30d
```

Browser не вычисляет UTC boundaries.

Read/application layer возвращает:

```text
from_utc
to_utc
evaluated_at
range identifier
bucket contract
```

Canonical interval: `[from_utc, to_utc)`.

---

# 11. Historical payload budget

Historical API возвращает server-side bounded + bucketed output.

Запрещено отдавать raw 30-second history и downsample в browser.

Dedicated TASK фиксирует:

```text
max points per series
max series/APs
response-size bound
query deadline
pagination/bounded AP loading
deterministic buckets
```

---

# 12. Native Omada history — роль

## `dashboard/traffic-activities`

Status:

```text
VERIFIED USEFUL NATIVE SOURCE
```

Это Site-level **volume buckets**, не готовая instantaneous Mbps series.

Observed on 5.14.32.3:

```text
≤26h      → 5-minute
27–170h   → hourly
171h–120d → daily
≥121d     → weekly
```

Observed behavior, не вечный guarantee.

Runtime caveat:

```text
Swagger: rxData
Live: dxData
```

Missing value bucket:

```text
!= 0 traffic
```

V1 role:

```text
VALIDATION / REFERENCE
```

Future:

```text
CANDIDATE FOR DEDICATED HISTORICAL ACQUISITION REVIEW
```

## `dashboard/traffic-distribution`

Status:

```text
VERIFIED USEFUL RANGE AGGREGATE
```

V1 role:

```text
VALIDATION / REFERENCE FOR AP SHARE
```

Не становится owner TRAFFIC-06.

Principle:

```text
validation source != product source
```

---

# 13. TRAFFIC-02 — Network Traffic History

Graph:

```text
Download
Upload
```

Ranges `24h / 7d`, future `30d`.

Source only `TRAFFIC-02-READ`.

Quality сразу включает, где применимо:

```text
complete
partial
insufficient
unavailable
gaps
source-family fallback
source unavailable
counter reset
no baseline
source-specific invalid elapsed/interval evidence
```

---

# 14. TRAFFIC-03 — Period Statistics

Отвечает: **«Сколько?»**

```text
Average Download
Average Upload
Peak Download
Peak Upload
```

Optional:

```text
Average Total
Peak Total
```

Source: `TRAFFIC-02-READ`.

Average — time/interval-aware. Gaps не становятся zero. Peak — accepted evidence only.

---

# 15. TRAFFIC-04 — Peak Load Period

Отвечает: **«Когда?»**

```text
busiest canonical bucket
busiest hour
timestamp/range
average Total throughput in busiest hour
```

Preferred selection metric:

```text
Total accepted Network Throughput
= Download + Upload
```

при accepted compatible evidence обеих directions.

Не создавать independent generic Peak, уже принадлежащий TRAFFIC-03.

---

# 16. TRAFFIC-05 — Traffic by AP

Graphical historical product.

Per AP:

```text
AP identity
Download history
Upload history
Now
Average
Peak
Coverage
```

Использует shared range и `TRAFFIC-02-READ`.

Dedicated TASK определяет pagination, AP bounds, max series, max graph points, response budget, cursor/continuation.

---

# 17. TRAFFIC-06 — AP Traffic Share

Смысл:

```text
share of accepted Network Traffic evidence
within selected range
```

Не share users/Internet/guest/billing.

Permanent invariant:

```text
sample count != traffic share
```

Preferred:

```text
time-weighted or interval-integrated accepted throughput
over common comparable intervals
```

При incompatible coverage → `partial` или `insufficient`.

Native `traffic-distribution` — validation/reference only.

---

# 18. TRAFFIC-07 — Online Guests Traffic

Base:

```text
Device / identity
AP
traffic counters / volume
honest direction labels
sorting
pagination
freshness/quality
```

Source: Current State persisted current client state/counters.

Research:

```text
trafficDown / trafficUp
= current Omada connection cumulative bytes
```

После finalization они совпадают с `past-connection.download/upload`; новая connection начинает новые counters.

---

# 19. TRAFFIC-07 — Current Rate conditional

Готового authoritative symmetric per-device current Mbps нет.

Permanent prohibitions:

```text
rxRate/txRate ≠ actual throughput
client activity ≠ full symmetric Current Rate
```

Preferred candidate:

```text
consecutive persisted Current State snapshots
→ same Site/client/source scope/connection
→ monotonic counter delta
→ bounded elapsed
→ reset/gap/progress validation
→ current per-device rate
```

---

# 20. TRAFFIC-07-READ — conditional

Создаётся только если Current Rate требует substantial backend foundation.

Минимально учитывать:

```text
same Site
same client identity
same source scope
ordered snapshots
elapsed > 0
elapsed <= max gap
counter non-decreasing
connection boundary
uptime non-decreasing where applicable
source snapshot progress/freshness
```

Counter decrease/uptime reset:

```text
counter_reset → no negative synthetic rate
```

Research permanent invariants:

```text
HTTP polling interval != source snapshot elapsed

active=true != instant proof of physical presence
```

Controller snapshot может повторяться ~30s; client может оставаться `active=true` с frozen counters >5 min после physical disconnect.

Current Rate обязан отличать:

```text
source advanced + delta 0
→ valid 0 Mbps

source frozen/stale
→ stale / insufficient / unavailable
```

Если Current Rate contract не доказан, TRAFFIC-07 реализуется без него.

---

# 21. Online Guests sorting / Future Home

Base sorting:

```text
Traffic Volume
Download volume
Upload volume
AP
Device
```

Current Rate sorting — только после accepted rate contract.

Отдельный Top Consumers panel внутри Traffic не нужен.

Future Home:

```text
Top Consumers by Current Rate
Top Consumers by Traffic Volume
```

через reusable Traffic ranking contract.

---

# 22. TRAFFIC-08 — Completed Guest Session Traffic

Отдельный domain.

```text
Completed Guest Session Traffic
Estimated volume
Completed session count
Historical volume chart
Coverage
freshness/provenance
```

Canonical:

```text
Visit Lifecycle
→ visit_source_events
→ reported_traffic_total_bytes
```

`past-connection` — future diagnostics/reconciliation candidate, не v1 product owner.

Preferred shared owner:

```text
CompletedSessionTrafficReadService
or equivalent
→ Traffic + Home Activity
```

Extraction не меняет Home Activity contract.

---

# 23. TRAFFIC-09 — Consolidated Evidence / Quality

TRAFFIC-09 агрегирует уже существующие quality states.

Каждый предыдущий TASK сам сразу возвращает:

```text
freshness
coverage
partial
insufficient
unavailable
reason
provenance
```

TRAFFIC-09 не создаёт новую quality semantics.

Допустимые source-specific details:

```text
counter_reset
gap_too_large
no_baseline
source_unavailable
source-family fallback
temporal skew
reader watermark
coverage boundary
source-specific invalid elapsed/interval evidence
```

Не создавать synthetic `Traffic Quality = 87%`.

---

# 24. Missing evidence != zero

Permanent:

```text
missing / unknown / stale / insufficient / unavailable != 0
```

Research native history также подтвердил timestamp-only buckets без traffic values.

Missing native bucket ≠ `0 MB`.

---

# 25. Failure isolation

Independent panels fail independently.

Traffic problems не ломают:

```text
Captive Portal
Observation
Current State
Visit Lifecycle
Home
other Admin sections
```

---

# 26. No direct polling / no new DB by default

Canonical:

```text
persisted facts
→ bounded read/application
→ Admin API
→ Browser
```

Запрещено:

```text
Browser → Omada
Admin request → Omada
Admin request → new collection cycle
```

Default:

```text
NO Traffic DB
NO Traffic collector
NO automatic rollup
```

Derived persistence требует measured failure + separate architecture review/TASK.

---

# 27. Future native historical acquisition review

Если `traffic-activities` когда-либо принимается как persisted dependency, нужен отдельный TASK по:

```text
persistence ownership
schema
idempotency
backfill
retention
adaptive granularity
missing buckets
timezone/bucket boundaries
source versioning
restart recovery
overlap ranges
polling cadence
failure isolation
unit normalization
runtime schema compatibility
```

Не добавлять автоматически в Observation worker.

---

# 28. TRAFFIC-10 / 11 / 12 — Future

## TRAFFIC-10 — 30-day Enablement

Только после performance acceptance:

```text
query benchmark
response-size
AP cardinality
query deadline
chart payload
Central Lab
```

## TRAFFIC-11 — Traffic Heatmap

```text
day × hour → Network Traffic intensity
```

Использует `TRAFFIC-02-READ`.

## TRAFFIC-12 — Period Comparison

```text
Today vs Yesterday
24h vs previous 24h
7d vs previous 7d
```

Требует same metric/source semantics/duration/compatible coverage.

---

# 29. API / Frontend / Web Designer

Preferred page:

```text
/admin/sites/<site_id>/traffic
```

Preferred namespace:

```text
/admin/api/v1/sites/<site_id>/traffic/...
```

Every endpoint:

```text
Admin auth
Site authorization
query deadline
concurrency bounds
response-size bounds
safe serialization
no-store
```

`TRAFFIC-00` создаёт shared frontend orchestration.

Web Designer подключается после semantic/read/API/functional acceptance и не меняет semantics.

---

# 30. Panel-by-panel implementation

```text
one product increment
=
one TASK
=
one acceptance unit
```

Process:

```text
DRAFT
→ Owner + Tech Lead review
→ FINAL
→ explicit implementation authorization
→ implementation
→ Coder focused/minimal tests
→ Central Lab acceptance
→ merge
→ separate production activation if needed
```

Эта Roadmap не авторизует реализацию TASK автоматически.

---

# 31. Canonical Roadmap order

```text
TRAFFIC-00
Traffic Section Foundation
        ↓
TRAFFIC-01
Current Network Throughput
        ↓
TRAFFIC-02-READ
Historical Network Traffic Read Foundation
        ↓
TRAFFIC-02
Network Traffic History
        ↓
TRAFFIC-03
Period Statistics
        ↓
TRAFFIC-04
Peak Load Period
        ↓
TRAFFIC-05
Traffic by AP
        ↓
TRAFFIC-06
AP Traffic Share
        ↓
TRAFFIC-07-READ
CONDITIONAL
        ↓
TRAFFIC-07
Online Guests Traffic
        ↓
TRAFFIC-08
Completed Guest Session Traffic
        ↓
TRAFFIC-09
Consolidated Traffic Evidence / Quality
        ↓
TRAFFIC SECTION v1 COMPLETE
```

Future:

```text
TRAFFIC-10 — 30-day Enablement
TRAFFIC-11 — Traffic Heatmap
TRAFFIC-12 — Period Comparison
Future Home summaries
```

`TRAFFIC-02-READ` mandatory.  
`TRAFFIC-07-READ` conditional.

---

# 32. Testing / acceptance ownership

Coder:

```text
focused/minimal TASK/module tests
new regression tests for own changes
```

Owner + Tech Lead / Central Lab:

```text
cross-surface semantic checks
broader/full regression
candidate differential
official PASS/FAIL
production acceptance
```

Useful independent validation oracles:

```text
Observation-derived Site integrated evidence
vs Omada traffic-activities

Observation-derived AP share
vs Omada traffic-distribution
```

Но `validation source != product source`.

---

# 33. Product wording restrictions

Без отдельного proof не использовать:

```text
Internet Traffic
WAN Traffic
Guest-only Traffic
Zefer_Parki Traffic
SSID Traffic
Billing Traffic
```

Canonical v1:

```text
Network Throughput
Site Network Traffic
AP Traffic
```

с source/provenance context.

---

# 34. Traffic Section v1 completion

Accepted:

```text
TRAFFIC-00
TRAFFIC-01
TRAFFIC-02-READ
TRAFFIC-02
TRAFFIC-03
TRAFFIC-04
TRAFFIC-05
TRAFFIC-06
TRAFFIC-07
TRAFFIC-08
TRAFFIC-09
```

`TRAFFIC-07-READ` только если нужен.

Не входят в v1 completion:

```text
TRAFFIC-10
TRAFFIC-11
TRAFFIC-12
future Home summaries
```

---

# 35. Decisions deferred to dedicated TASK

Roadmap не фиксирует заранее:

```text
exact bucket sizes
exact max point counts
exact response bytes
exact chart implementation
exact historical source-family algorithm
exact AP Share formula
exact Peak bucket granularity
exact current-client rate thresholds/formula
exact Guest Session buckets
exact quality UI mapping
exact API endpoint names
```

Они утверждаются на актуальном baseline соответствующего TASK.

---

# 36. Final architecture

```text
Omada/source systems
→ approved acquisition
→ persisted authoritative CaptivPortal facts
→ canonical semantic/read owners
→ bounded application contracts
→ Admin Traffic product panels
→ future reusable Home summaries
```

Не:

```text
UI card → own calculation → own meaning
```

---

# 37. Final status

```text
TRAFFIC MASTER ROADMAP:
FINAL

ROADMAP ARCHITECTURE:
APPROVED

TECH LEAD ROADMAP DIRECTION:
PASS

TRAFFIC-SOURCE-RESEARCH-01:
PASS / ACCEPTED ARCHITECTURAL EVIDENCE

CURRENT REPOSITORY BASELINE:
c719525a1a2a324a0959597c993b99a82bf465b0

NEXT ROADMAP ITEM:
TRAFFIC-00 — Traffic Section Foundation

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS ROADMAP
```

После помещения Roadmap в постоянные источники следующий документ:

```text
TRAFFIC-00
Traffic Section Foundation
DRAFT
```
