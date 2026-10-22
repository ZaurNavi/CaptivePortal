# TASK-OBSERVATION-FOUNDATION-01 — Observation Foundation v1

**Проект:** CaptivPortal  
**Тип:** master implementation TASK / архитектурное ТЗ  
**Статус документа:** DRAFT REVISION 2 — FOR FINAL REVIEW  
**Implementation authorization:** НЕ ДАНО — реализацию не начинать до отдельного утверждения owner/архитектора  
**Execution mode после утверждения:** `implementation`  
**Исполнитель:** Coder / coding agent  
**Review:** Tech Lead + архитектор + owner  
**Test responsibility:** `agent`, production acceptance — `owner/Tech Lead`  
**Дата:** 11 августа 2026 года  
**Основание REV2:** обязательные замечания Tech Lead review; архитектурная концепция PASS, implementation ещё не разрешён

---

## 1. Цель

Реализовать следующий функциональный этап дорожной карты CaptivPortal:

```text
Observation Foundation v1
```

Observation Foundation должен создать постоянный Site-aware слой систематического сбора, нормализации и хранения исторических технических наблюдений о:

- авторизованных Wi‑Fi-клиентах;
- управляемых Omada Access Point;
- радиоусловиях и radio utilization;
- Ethernet/LAN состоянии AP;
- накопительных counters и безопасно вычисляемых технических rates;
- редко меняющейся безопасной конфигурации/capabilities AP.

Главный принцип:

```text
Collect facts now.
Analyze them later.
```

Observation Foundation не является Analytics, Visit Lifecycle, Admin Console или Grafana integration.

---

## 2. Baseline и текущее состояние

### 2.1. GitHub baseline на момент подготовки TASK

Фактический `origin/main` на момент REV2:

```text
a79e0a302fd252a98c9f6f279244ed35f2266871
```

Runtime merge:

```text
ab776af3fc58dc090e17ecd20534abddc1f33ad3
```

Проверенное сравнение `ab776af..a79e0a3` содержит только README и knowledge-base/documentation изменения. Runtime code после `ab776af` в этом диапазоне не менялся.

### 2.2. Обязательный pre-change Linux regression baseline

**До первого изменения runtime/test файлов PR A** Coder обязан на чистом exact baseline выполнить:

```bash
git fetch origin
git checkout --detach a79e0a302fd252a98c9f6f279244ed35f2266871
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
git status --short
```

Зафиксировать:

```text
baseline_sha
passed
skipped
failed
compileall
 diff-check
working-tree state
```

Если к моменту фактического старта `origin/main` уже не равен `a79e0a3`:

1. зафиксировать новый `origin/main`;
2. сравнить его с `a79e0a3`;
3. если runtime не менялся — выполнить pre-change gate на новом exact `origin/main`;
4. если runtime менялся в связанных областях — stop condition и Tech Lead review до implementation.

Новый full-gate после изменения сравнивается именно с этим сохранённым pre-change baseline. Нельзя впервые запускать full suite только после реализации.

### 2.3. CAPPORT acceptance

Owner сообщил примерно 20 успешных физических production-тестов на реальных телефонах, включая телефоны гостей.

Для настоящего TASK CAPPORT live acceptance считается закрытым owner evidence и не входит в scope Observation Foundation.

Формальное обновление status/debt registry выполняет Tech Lead отдельно.

### 2.4. Existing architecture

Observation Foundation обязан уважать существующие:

```text
Portal/AuthSession/AuthWorker
CAPPORT
shared OmadaProvider
Pending Client Session Cleaner
Authorized Client Snapshot Collector
Visitor Device Registry
Public Traffic Counter
Omada Webhook modules
```

Observation Foundation — новый независимый fail-open data/operational subsystem.

---

## 3. Критическая граница — AuthorizedClientSnapshotCollector НЕ МЕНЯТЬ

Существующий Authorized Client Snapshot Collector остаётся отдельным стабильным компонентом.

Его роль:

```text
AUTHORIZED
    ↓
one detailed snapshot
    ↓
start-of-history client picture
```

Запрещено:

- менять `AuthorizedClientSnapshotCollector`;
- менять `AuthorizedClientSnapshotRequest`;
- менять `NormalizedClientSnapshot`;
- менять snapshot schema v1;
- менять `snapshot_id`/idempotency rules;
- менять `visitor_snapshots.log`;
- менять snapshot retry/queue/lifecycle;
- превращать Snapshot Collector в periodic collector;
- заставлять Snapshot Collector писать Observation DB;
- заставлять Observation Foundation писать Visitor Registry DB.

### Fail-open оговорка

Client Observation не должен требовать наличия успешно записанного snapshot row как precondition.

```text
Snapshot capture failure
must not suppress future observations.
```

Client Observation v1 допускается для клиента, который фактически:

```text
wireless == true
active == true
authStatus == 2
```

даже если Snapshot Collector временно не смог записать snapshot.

---

## 4. Не входит в TASK

Не реализовывать:

- Visit Lifecycle / `visit_id` / open/closed visit;
- offline finalization;
- Visitor Analytics;
- Wireless Analytics;
- AP-placement recommendations;
- `weak_signal`, `poor_signal`, `needs_second_ap` business flags;
- Admin API;
- Web Foundation;
- Admin Console;
- customer authentication/RBAC/Tenant;
- billing/entitlements;
- Grafana dashboard/datasource/plugin;
- Alloy/Loki configuration;
- systemd/reverse proxy;
- production activation;
- Omada Controller reconfiguration;
- remote AP adoption;
- Multi-Tenant architecture.

---

## 5. Целевая архитектура

```text
                    shared OmadaProvider
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
     Client Observation         AP Observation
          Worker                    Worker
              │                         │
              ▼                         ▼
       client normalizer           AP normalizer
              │                         │
              └────────────┬────────────┘
                           ▼
                  ObservationRepository
                           │
                           ▼
                observations.sqlite3
                           │
                           ▼
                ObservationReadService
                           │
                future consumers
```

Дополнительно:

```text
ObservationCleanupWorker
    ↓
ObservationRepository
```

Создать новый package:

```text
app/observations/
```

Рекомендуемая структура:

```text
app/observations/
├── __init__.py
├── config.py
├── models.py
├── normalizer.py
├── repository.py
├── read_service.py
├── client_worker.py
├── ap_worker.py
├── cleanup_worker.py
└── runtime.py
```

Допускается разумное объединение файлов, если ответственности остаются однозначными.

---

## 6. Общий OmadaProvider

Observation Foundation использует существующий один `OmadaProvider`, созданный `run.py`.

Запрещено:

- новый OAuth client;
- новый token manager/cache;
- новый `OmadaProvider()` внутри workers;
- новый global provider singleton;
- изменение AuthWorker provider contract;
- изменение существующего thread-safe token lifecycle без отдельного доказательства необходимости.

Предпочтительно добавить narrow read-only provider extension:

```text
app/controllers/omada_observations.py
```

по существующему pattern:

```text
install_observation_methods(OmadaProvider)
```

через `app/controllers/__init__.py`.

Минимальный логический protocol:

```python
class ObservationProvider(Protocol):
    def list_observation_clients(...): ...
    def list_access_points(...): ...
    def get_ap_overview(...): ...
    def get_ap_wired_uplink(...): ...
    def get_ap_lan_traffic(...): ...
    def get_ap_radios(...): ...
    def get_ap_general_config(...): ...
    def get_ap_ip_setting(...): ...
    def get_ap_radio_config(...): ...
    def get_ap_ofdma(...): ...
    def get_ap_available_channels(...): ...
    def get_ap_safe_overrides(...): ...
    def get_ap_rf_scan_state(...): ...
```

Каждый method обязан:

- принимать `site_id`;
- принимать bounded `timeout_seconds`;
- для AP endpoint принимать canonical AP MAC;
- возвращать существующий `Result`;
- не возвращать token/header/cookie;
- возвращать defensive copies mutable data.

---

## 7. Подтверждённые Omada endpoints

### Clients

Основной periodic source:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/clients
```

Использовать pagination.

Не делать N+1 periodic detail GET каждого клиента только ради дублирования данных, уже доступных в inventory list.

### AP inventory

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/devices
```

Выбирать только:

```text
type == "ap"
```

Не использовать отсутствующий в Controller 5.14.31:

```text
GET /devices/{deviceMac}
```

### AP dynamic

```text
GET /aps/{apMac}
GET /aps/{apMac}/wired-uplink
GET /aps/{apMac}/lan-traffic-info
GET /aps/{apMac}/radios
```

### AP slow-changing

```text
GET /aps/{apMac}/general-config
GET /aps/{apMac}/ip-setting
GET /aps/{apMac}/radio-config
GET /aps/{apMac}/ofdma
GET /aps/{apMac}/available-channel
GET /openapi/v2/.../aps/{apMac}/override
GET /openapi/v2/.../aps/{apMac}/rf-scan-result
```

### Не опрашивать регулярно

```text
/power-saving
```

В исследовании EAP613 он возвращал success без полезного `result`.

---

## 8. Omada response/error handling

Для каждого provider method порядок:

```text
transport exception
→ HTTP status
→ JSON validity/root type
→ errorCode type/value
→ endpoint-specific result type
→ normalization
```

HTTP 200 сам по себе не считается success.

`errorCode == -44112`:

- token expiry;
- invalidate только token, использованный request;
- получить fresh shared token;
- максимум один повтор GET;
- без нового token cache.

Для остальных transient failures немедленный общий retry loop в v1 не нужен: текущий cycle фиксирует failure/partial, следующий scheduled cycle является natural retry.

Unknown errorCode не получает выдуманную семантику.

---

## 9. Configuration contract

Добавить в существующий `app/config.py → app/settings.py → get_settings()` pipeline.

Repository defaults:

```text
OBSERVATION_FOUNDATION_ENABLED=false
OBSERVATION_CLIENT_ENABLED=true
OBSERVATION_AP_ENABLED=true

OBSERVATION_SITE_IDS=
OBSERVATION_CLIENT_SSIDS=

OBSERVATION_DB_PATH=/opt/CaptivePortal/data/observations.sqlite3

OBSERVATION_CLIENT_INITIAL_DELAY_SECONDS=15
OBSERVATION_CLIENT_INTERVAL_SECONDS=60

OBSERVATION_AP_INITIAL_DELAY_SECONDS=10
OBSERVATION_AP_INTERVAL_SECONDS=30
OBSERVATION_AP_INVENTORY_INTERVAL_SECONDS=300
OBSERVATION_AP_INVENTORY_MAX_STALE_SECONDS=900
OBSERVATION_AP_CONFIG_INTERVAL_SECONDS=21600

OBSERVATION_REQUEST_TIMEOUT_SECONDS=5

OBSERVATION_CLIENT_PAGE_SIZE=500
OBSERVATION_CLIENT_MAX_PAGES=20
OBSERVATION_CLIENT_MAX_ROWS=10000

OBSERVATION_AP_PAGE_SIZE=100
OBSERVATION_AP_MAX_PAGES=10
OBSERVATION_AP_MAX_ROWS=500
OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE=200
OBSERVATION_AP_CONFIG_MAX_REQUESTS_PER_CYCLE=200
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS=120
OBSERVATION_AP_CONFIG_CYCLE_MAX_DURATION_SECONDS=180
OBSERVATION_RATE_MAX_GAP_SECONDS=180

OBSERVATION_DYNAMIC_RETENTION_DAYS=180
OBSERVATION_CONFIG_RETENTION_DAYS=730
OBSERVATION_CLEANUP_INITIAL_DELAY_SECONDS=900
OBSERVATION_CLEANUP_INTERVAL_SECONDS=86400
OBSERVATION_CLEANUP_BATCH_SIZE=5000
OBSERVATION_CLEANUP_MAX_DURATION_SECONDS=30

OBSERVATION_SHUTDOWN_TIMEOUT_SECONDS=20
```

`.env.example` содержит только placeholders/безопасные defaults; production Site ID/SSID secrets не добавлять.

### Feature semantics

`OBSERVATION_FOUNDATION_ENABLED=false`:

- runtime disabled;
- Omada polling отсутствует;
- DB не обязана создаваться;
- cleanup не стартует.

При master enabled минимум один из `OBSERVATION_CLIENT_ENABLED` / `OBSERVATION_AP_ENABLED` должен быть true.

Invalid enabled config → Observation runtime `unavailable`, но CaptivPortal продолжает запускаться.

### Site IDs

`OBSERVATION_SITE_IDS`:

- CSV;
- trim whitespace;
- empty elements invalid;
- duplicates deduplicate preserving first order;
- required when master enabled;
- никакого hardcode Site ID.

Все observation rows содержат `site_id`.

### Client SSIDs

`OBSERVATION_CLIENT_SSIDS`:

- optional CSV exact allowlist;
- case-sensitive;
- пустое значение = все SSID configured Sites;
- filter применяется только к Client Observation.

### Cadence semantics

`*_INTERVAL_SECONDS` означает **fixed delay после завершения предыдущего cycle**, а не обещание fixed-rate запуска.

Для AP dynamic default:

```text
cycle deadline = 120 sec
fixed delay after cycle = 30 sec
rate max gap = 180 sec
```

Следовательно, при worst-case медленных endpoints cycle может завершиться `partial` раньше полного обхода AP. Deadline и request budget имеют приоритет над попыткой опросить все AP.

При truncation порядок AP должен быть fairness-safe: следующий cycle продолжает обработку с rotating in-memory cursor по canonical AP order, чтобы одни и те же первые AP не вытесняли остальные постоянно.

---

## 10. Client Observation Collector

### 10.1. Eligibility v1

Detailed client observation сохраняется только при:

```text
valid canonical MAC
wireless is True
active is True
authStatus == 2
SSID проходит optional allowlist
```

`authStatus == 1` не сохраняется detailed row в v1; допускается только summary count cycle telemetry.

Unknown authStatus не интерпретировать; detailed row не сохранять.

### 10.2. Pagination

Использовать bounded:

```text
pageSize = 500
max pages = 20
max rows = 10000
```

Cycle = `complete`, если inventory согласован.

Cycle = `partial`, если:

- page failed;
- limits достигнуты раньше totalRows;
- totalRows malformed/inconsistent;
- shutdown во время pagination.

Observation — read-only, поэтому валидные rows из partial inventory можно сохранить, но они обязаны нести `source_inventory_complete=false`, а cycle — `complete=false`. Будущая Analytics сможет исключить partial cycles из точных simultaneous-client counts.

### 10.3. Duplicate MAC

Если один canonical MAC встречается более одного раза в cycle:

- не выбирать произвольно;
- observation этого MAC не сохранять;
- увеличить `duplicate_mac_count`.

### 10.4. Client normalizer

Создать независимый Observation normalizer. `snapshot_normalizer.py` не менять.

Минимальный safe allowlist:

**Identity/context**

```text
client_mac
controller_client_id
name
hostname
system_name
device_type
connect_device_type
ip
ipv6_list_json
ssid
ap_name
ap_mac
```

**Radio/session**

```text
connect_type
signal_level
signal_rank
wifi_mode
radio_id
band
channel
rx_rate
tx_rate
rssi
snr
vid
uptime
last_seen_ms
auth_status
activity
wireless
power_save
blocked
guest
active
manager
```

**Traffic**

```text
traffic_down
traffic_up
down_packet
up_packet
```

**Safe structured — только recursive allowlist**

Potential top-level sources:

```text
ipSetting
rateLimit
clientLockToApSetting
multiLink
```

Они **не разрешены целиком**. Для каждого сохраняемого structured field Observation normalizer обязан иметь explicit path-based recursive allowlist подтверждённых child keys/types.

Если exact child schema не подтверждена research/current fixture/test evidence, поле в v1 **не сохранять вообще**. Unknown nested key всегда DROP.

Нельзя делать:

```text
allowed top-level object → deepcopy whole object
```

Исключить даже при наличии в source:

```text
dot1xIdentity
passwords
tokens
cookies
authorization headers
unknown secret-bearing raw fields
```

Periodic client observation не хранит полный raw controller row.

### 10.5. Type rules

- bool не integer;
- integer — exact int;
- non-finite float запрещён;
- invalid optional → NULL, не 0;
- invalid required identity → row skipped;
- MAC canonical colon uppercase;
- IP canonical;
- numeric strings не преобразовывать неявно;
- unknown enum хранить raw code без label.

Допустимая band normalization:

```text
radio_id 0 → 2.4GHz
radio_id 1 → 5GHz
other → NULL
```

raw `radio_id` сохраняется всегда.

---

## 11. AP Observation Collector

### 11.1. Bounded AP inventory pagination

Источник inventory:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/devices
```

Pagination обязательна:

```text
pageSize = OBSERVATION_AP_PAGE_SIZE        # default 100
max pages = OBSERVATION_AP_MAX_PAGES       # default 10
max rows = OBSERVATION_AP_MAX_ROWS         # default 500
```

Inventory считается complete только если pagination согласована с `totalRows`/фактическим окончанием данных.

Inventory = partial/failed, если:

- required page failed;
- result/data malformed;
- max pages/max rows достигнут раньше полного inventory;
- shutdown/deadline прервал pagination.

Выбирать только rows с подтверждённым:

```text
type == "ap"
```

### 11.2. Duplicate AP MAC

Один canonical AP MAC внутри одного inventory должен соответствовать одной AP row.

При duplicate MAC:

- строки данного MAC не использовать для polling в этом inventory;
- не выбирать row произвольно;
- увеличить `duplicate_ap_mac_count`;
- cycle получает data-quality warning.

### 11.3. AP inventory cache и bounded staleness

AP worker держит последний successful complete inventory per Site в memory.

Refresh default:

```text
300 sec
```

Maximum allowed stale age:

```text
OBSERVATION_AP_INVENTORY_MAX_STALE_SECONDS=900
```

Если refresh failed:

- cache разрешено использовать только пока `cache_age <= 900 sec`;
- telemetry/cycle фиксирует stale age;
- если cache older than max stale — **не опрашивать AP из этого cache**;
- dynamic/config cycle завершить `failed` либо `partial` с reason `inventory_stale_expired`;
- после restart cache пустой, initial inventory обязателен.

### 11.4. Dynamic polling deadline и request budget

Default fixed delay:

```text
30 sec после завершения предыдущего cycle
```

Hard boundaries:

```text
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS=120
OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE=200
OBSERVATION_REQUEST_TIMEOUT_SECONDS=5
```

AP dynamic cycle включает inventory refresh при необходимости и per-AP requests.

Перед каждым новым HTTP request worker проверяет:

- shutdown;
- monotonic cycle deadline;
- remaining request budget.

При исчерпании deadline/budget:

- новые requests не начинать;
- cycle = `partial`;
- уже полученные valid observations сохранять;
- remaining AP count фиксировать в cycle metadata/telemetry;
- rotating AP cursor обеспечивает fairness следующего cycle.

Worst-case `4 endpoints × 5 sec × 10 AP = 200 sec` **не должен** приводить к 200-second unbounded cycle: 120-second deadline обрывает старт новых requests, а уже начатый bounded request завершается по timeout.

### 11.5. Dynamic sections

На AP собирать best-effort:

```text
overview
wired_uplink
lan_traffic
radios
```

Section failures независимы. Успешные sections сохранять, AP row/cycle помечать partial.

### 11.6. Section timestamps

Каждый section хранит timestamp получения собственных source counters:

```text
overview_observed_at
wired_observed_at
lan_observed_at
radio_observed_at       # на radio row
```

Общий `ap_observations.observed_at` — время формирования AP observation row и **не используется** для rate delta отдельных sections.

### 11.7. AP overview fields

```text
site_id
ap_mac
name
ip
model
firmware_version
wlan_id
cpu_util
mem_util
uptime_seconds
```

### 11.8. Wired uplink

```text
wired_rate_raw
wired_duplex_code
wired_up_bytes
wired_down_bytes
wired_up_packets
wired_down_packets
wired_activity_raw
```

`duplex_code` не переводить в full/half без подтверждённой enum mapping.

`activity` не называть Mbps: единица не подтверждена.

### 11.9. LAN traffic

```text
lan_rx_bytes
lan_tx_bytes
lan_rx_packets
lan_tx_packets
lan_rx_drop_packets
lan_tx_drop_packets
lan_rx_error_packets
lan_tx_error_packets
```

LAN и Wired counters не объединять в один source.

### 11.10. Radio rows

Для каждого band сохранять:

```text
site_id
ap_mac
radio_observed_at
band
radio_id if available
actual_channel_raw
actual_channel
frequency_mhz
channel_width
max_tx_rate
tx_power
wireless_mode

tx_util
rx_util
interference_util
busy_util

rx_bytes
tx_bytes
rx_packets
tx_packets
rx_drop_packets
tx_drop_packets
rx_error_packets
tx_error_packets
rx_retry_packets
tx_retry_packets
```

`max_tx_rate` — PHY characteristic, не current throughput.

`busy_util` — airtime utilization, не Mbps.

---

## 12. Derived technical rates

Это допустимая deterministic acquisition metric, не Analytics.

Raw cumulative counters сохранять всегда.

### 12.1. Wired

```text
wired_download_mbps = ΔdownBytes * 8 / ΔT / 1_000_000
wired_upload_mbps   = ΔupBytes   * 8 / ΔT / 1_000_000
```

`ΔT` рассчитывается только между `wired_observed_at` текущего и previous wired source sample той же `site_id + ap_mac`.

### 12.2. LAN

```text
lan_rx_mbps
lan_tx_mbps
```

`ΔT` рассчитывается только по `lan_observed_at`.

### 12.3. Radio aggregate rates

`/radios` отдаёт cumulative counters радиоинтерфейса AP, а не отдельного клиента.

Поэтому запрещены misleading names:

```text
client_download_mbps
client_upload_mbps
```

Использовать:

```text
radio_tx_mbps = Δradio.tx_bytes * 8 / ΔT / 1_000_000
radio_rx_mbps = Δradio.rx_bytes * 8 / ΔT / 1_000_000
```

Это **aggregate radio-interface traffic**, не per-client traffic и не WAN speedtest.

`ΔT` рассчитывается только по `radio_observed_at` предыдущей radio row той же `site_id + ap_mac + band/radio identity`.

### 12.4. Per-source / per-direction rate reasons

Один общий `counter_reset` запрещён.

Хранить независимые reason/status минимум:

```text
wired_download_rate_reason
wired_upload_rate_reason
lan_rx_rate_reason
lan_tx_rate_reason
radio_rx_rate_reason      # на каждой radio row
radio_tx_rate_reason      # на каждой radio row
```

Допустимые v1 reasons:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Если reset произошёл только у одного counter/direction, только соответствующий rate = NULL. Reset wired не обнуляет LAN/radio rates; reset одного radio band не влияет на другой band.

### 12.5. Rate validity

Rate вычисляется только если:

- есть previous stored observation того же exact source identity;
- new counter >= old counter для конкретного counter;
- elapsed > 0;
- elapsed <= `OBSERVATION_RATE_MAX_GAP_SECONDS` (default 180 sec).

Если counter уменьшился:

```text
rate = NULL
rate_reason = counter_reset
```

Если gap >180 sec:

```text
rate = NULL
rate_reason = gap_too_large
```

Новое raw value становится baseline следующего sample.

Не выдавать long-gap average как current rate.

---

## 13. AP slow-changing configuration

Default fixed delay:

```text
21600 sec / 6 h после завершения предыдущего config cycle
```

Hard boundaries:

```text
OBSERVATION_AP_CONFIG_CYCLE_MAX_DURATION_SECONDS=180
OBSERVATION_AP_CONFIG_MAX_REQUESTS_PER_CYCLE=200
```

Перед каждым request проверяются shutdown, deadline и request budget.

### 13.1. Complete-only config snapshot

`ap_config_snapshots` создаётся **только для complete safe config snapshot конкретной AP**.

Для v1 complete означает successful и safely normalized response всех обязательных configured sections:

```text
general-config
ip-setting
radio-config
ofdma
available-channel
safe override v2
rf-scan-result v2
```

Если хотя бы одна обязательная section failed/malformed/unsafe:

- config snapshot для этой AP **не создавать**;
- hash не вычислять;
- `latest config` не менять;
- telemetry фиксирует AP MAC + section status/reason без raw payload;
- overall config cycle может быть partial.

Partial config никогда не должен выглядеть как новое изменение конфигурации.

### 13.2. Change-only dedup

Для complete normalized snapshot вычислять:

```text
config_sha256
```

по canonical strict JSON.

Новый row писать только если:

- это первый complete snapshot AP;
- либо hash отличается от latest complete snapshot.

### 13.3. Recursive allowlists для structured/nested data

Все nested objects/arrays проходят **path-based recursive allowlist**.

Обязательное правило:

```text
unknown nested key → DROP
not "keep and redact"
```

Для каждого structured source в code должна существовать явная allowlist-константа/схема разрешённых paths и child types.

Если точная nested schema поля не подтверждена research report/current fixtures/tests:

```text
v1 persistence for that nested field = OMIT
```

Запрещено сохранять объект целиком только потому, что его top-level key разрешён.

Это правило применяется минимум к:

```text
client ipSetting
client rateLimit
client clientLockToApSetting
client multiLink
AP ip-setting nested data
AP radio-config nested data
available-channel arrays/items
OFDMA nested structures
safe override items
RF scan nested structures
```

### 13.4. Safe sections

**general-config**

Разрешать только подтверждённые scalar/list fields:

```text
name
led_setting_code
tag_ids
location
```

Nested content внутри list/object фильтровать рекурсивно.

**ip-setting**

Сохранять только заранее перечисленные подтверждённые scalar paths (mode/address/mask/gateway/DNS/fallback). Любой дополнительный nested key drop.

**radio-config**

Сохранять только подтверждённые paths для radio enabled/channel/width/TX power/TX power level/wireless mode/channel ranges. Unknown children drop.

**ofdma** — только подтверждённые support/enabled flags per band.

**available-channel** — каждый array item нормализуется по explicit item allowlist (band/channel/frequency/width/capability fields, только если подтверждены source contract). Unknown item keys drop.

**rf-scan v2**

Сохранять только:

```text
time
status
status2g
status5g
status5g2
status6g
```

Unknown enum codes не расшифровывать предположением.

### 13.5. Критическая безопасность `/override`

Использовать только v2 через provider method `get_ap_safe_overrides()`.

Разрешённые item fields:

```text
ssidId
ssidEntryId
ssidName
band
security
vlanEnable
vlanId
ssidEnable
```

`ssidPassword` запрещено возвращать caller даже в redacted виде.

Запрещено raw `/override`:

- логировать;
- сохранять;
- включать exception;
- возвращать в Result;
- передавать telemetry.

---

## 14. Data-quality cycles

Создать таблицу:

```text
observation_cycles
```

Минимум:

```text
cycle_id TEXT PRIMARY KEY
kind TEXT NOT NULL
site_id TEXT NOT NULL
state TEXT NOT NULL
started_at TEXT NOT NULL
finished_at TEXT
abandoned_at TEXT
complete INTEGER
result TEXT
source_rows_reported INTEGER
items_seen INTEGER NOT NULL
items_stored INTEGER NOT NULL
items_skipped INTEGER NOT NULL
error_count INTEGER NOT NULL
data_quality_warning_count INTEGER NOT NULL
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
```

`kind` v1:

```text
client
ap_dynamic
ap_config
```

**Cleanup в `observation_cycles` не записывать.** Cleanup — global maintenance operation, а таблица cycles остаётся Site-scoped (`site_id NOT NULL`). Cleanup имеет только operational telemetry.

`state`:

```text
running
completed
abandoned
```

`result` для completed:

```text
success
partial
failed
shutdown
```

### 14.1. Cycle creation

До начала source polling создать provisional row:

```text
state = running
finished_at = NULL
abandoned_at = NULL
complete = NULL
result = NULL
```

Insert cycle row и network polling — разные short operations; не держать SQLite transaction во время network call.

### 14.2. Normal finalization

В конце cycle atomic update:

```text
state = completed
finished_at = <UTC>
complete = 0|1
result = success|partial|failed|shutdown
```

### 14.3. Crash recovery

При Observation Repository startup до запуска workers:

- найти rows `state=running` от предыдущего process;
- не объявлять их success/partial;
- atomic update:

```text
state = abandoned
abandoned_at = startup_utc
complete = 0
result = NULL
updated_at = startup_utc
```

`finished_at` остаётся NULL, потому что фактическое время завершения неизвестно.

Future Analytics обязана иметь возможность исключить `running/abandoned` cycles.

Cycle metadata не содержит raw controller payload/error body.

---

## 15. Persistent Observation Storage

Default:

```text
/opt/CaptivePortal/data/observations.sqlite3
```

Schema version:

```text
1
```

Observation DB принадлежит только Observation Foundation.

Не использовать Visitor Registry DB или Public Traffic DB.

Минимальные tables:

```text
observation_cycles
client_observations
ap_observations
ap_radio_observations
ap_config_snapshots
```

### 15.1. Единый UTC timestamp contract

Все persisted UTC timestamps используют один fixed-width формат:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

Пример:

```text
2026-08-11T12:34:56.123Z
```

Требования:

- всегда UTC;
- всегда `Z`;
- всегда 3-digit milliseconds;
- никакого local offset в DB;
- никакой переменной длины fractional seconds;
- формат обязан корректно сортироваться лексикографически в том же порядке, что и время.

Monotonic clock используется только для deadlines/durations внутри process и никогда не persist как wall-clock timestamp.

### 15.2. client_observations

```text
row_id INTEGER PRIMARY KEY
cycle_id TEXT NOT NULL
observed_at TEXT NOT NULL
site_id TEXT NOT NULL
client_mac TEXT NOT NULL
source_inventory_complete INTEGER NOT NULL
```

Остальные normalized fields nullable.

Idempotency:

```text
UNIQUE(cycle_id, client_mac)
```

FK:

```text
cycle_id → observation_cycles(cycle_id) ON DELETE CASCADE
```

### 15.3. ap_observations

```text
row_id INTEGER PRIMARY KEY
cycle_id TEXT NOT NULL
observed_at TEXT NOT NULL
site_id TEXT NOT NULL
ap_mac TEXT NOT NULL
partial INTEGER NOT NULL
overview_ok INTEGER NOT NULL
wired_uplink_ok INTEGER NOT NULL
lan_traffic_ok INTEGER NOT NULL
radios_ok INTEGER NOT NULL
overview_observed_at TEXT
wired_observed_at TEXT
lan_observed_at TEXT
wired_download_rate_reason TEXT
wired_upload_rate_reason TEXT
lan_rx_rate_reason TEXT
lan_tx_rate_reason TEXT
```

Плюс overview/wired/LAN fields и derived rates.

**Не использовать один generic `counter_reset` field.**

Idempotency:

```text
UNIQUE(cycle_id, ap_mac)
```

FK:

```text
cycle_id → observation_cycles(cycle_id) ON DELETE CASCADE
```

### 15.4. ap_radio_observations

```text
row_id INTEGER PRIMARY KEY
cycle_id TEXT NOT NULL
ap_observation_row_id INTEGER NOT NULL
radio_observed_at TEXT NOT NULL
site_id TEXT NOT NULL
ap_mac TEXT NOT NULL
band TEXT NOT NULL
radio_rx_rate_reason TEXT
radio_tx_rate_reason TEXT
```

Плюс radio fields/rates.

Idempotency:

```text
UNIQUE(ap_observation_row_id, band)
```

Если source имеет надёжный distinct radio identity beyond band, использовать `UNIQUE(ap_observation_row_id, radio_identity)` и документировать mapping; не разрешать silently duplicate radio rows.

FK:

```text
cycle_id → observation_cycles(cycle_id) ON DELETE CASCADE
ap_observation_row_id → ap_observations(row_id) ON DELETE CASCADE
```

### 15.5. ap_config_snapshots

```text
row_id INTEGER PRIMARY KEY
cycle_id TEXT NOT NULL
captured_at TEXT NOT NULL
site_id TEXT NOT NULL
ap_mac TEXT NOT NULL
config_sha256 TEXT NOT NULL
schema_version INTEGER NOT NULL
config_json TEXT NOT NULL
```

`config_json` — strict recursively allowlisted complete normalized JSON.

Idempotency/uniqueness:

```text
UNIQUE(cycle_id, ap_mac)
UNIQUE(site_id, ap_mac, config_sha256)
```

FK:

```text
cycle_id → observation_cycles(cycle_id) ON DELETE CASCADE
```

Partial config rows не существуют.

---

## 16. Required indexes

Минимум:

```text
client_observations(site_id, client_mac, observed_at, row_id)
client_observations(site_id, observed_at, row_id)
client_observations(site_id, ap_mac, observed_at, row_id)
client_observations(site_id, ssid, observed_at, row_id)
client_observations(site_id, radio_id, observed_at, row_id)

ap_observations(site_id, ap_mac, observed_at, row_id)
ap_observations(site_id, observed_at, row_id)

ap_radio_observations(site_id, ap_mac, band, radio_observed_at, row_id)

ap_config_snapshots(site_id, ap_mac, captured_at, row_id)

observation_cycles(site_id, kind, started_at)
observation_cycles(state, started_at)
```

Порядок columns допускается менять только с query/benchmark justification.

FK и UNIQUE constraints из section 15 являются частью schema contract и не заменяются обычными indexes.

---

## 17. SQLite initialization / transactions

При первом создании:

- safe parent directory handling по current project pattern;
- POSIX file mode `0640`;
- `PRAGMA user_version=1`;
- `foreign_keys=ON`;
- bounded `busy_timeout`;
- WAL preferred для writer + readers;
- `synchronous=NORMAL` допустим при WAL;
- schema validation;
- `PRAGMA quick_check` startup.

Не удалять corrupt DB и не пересоздавать silently schema mismatch.

Schema newer than code → Observation runtime unavailable, portal продолжает работать.

Network requests выполняются вне SQLite transaction/lock.

Repository сериализует write transactions inside process.

Предпочтительно:

```text
one short transaction per client batch
one short transaction per AP batch
one short transaction per config batch
```

---

## 18. Retention / cleanup

### Dynamic observations

Proposed default до завершения Phase A capacity gate:

```text
180 days
```

Для:

```text
client_observations
ap_observations
ap_radio_observations
client/ap_dynamic cycles
```

### Slow config history

Proposed default:

```text
730 days
```

Для complete `ap_config_snapshots` / config cycles.

### Cleanup Worker

Cleanup является global maintenance worker и **не создаёт row в `observation_cycles`**.

Fixed-delay:

```text
initial delay 900 sec
interval 86400 sec
max runtime 30 sec
batch size 5000
```

Cleanup:

1. использует UTC cutoffs в едином timestamp format;
2. удаляет expired parent cycles bounded batches там, где cascade корректно удаляет observation rows;
3. либо удаляет orphan-safe rows по явно документированной последовательности, если FK design требует этого;
4. shutdown check между batches;
5. max duration;
6. не удаляет `running` cycle текущего process;
7. `abandoned` cycles очищаются по retention соответствующего `kind`;
8. lightweight optimize/maintenance;
9. summary operational telemetry.

Automatic full `VACUUM` в обычном runtime запрещён.

Incremental vacuum допустим только если bounded и протестирован.

### Full disk / storage failure

`SQLITE_FULL`, I/O, corruption, schema error:

- Observation → degraded/unavailable;
- portal/Auth/CAPPORT/Snapshot/Cleaner/Registry не меняются;
- никаких emergency deletes вне retention;
- никакого auto-drop/recreate.

Transient busy/locked — bounded timeout, current cycle может fail, следующий cycle может восстановиться.

---

## 19. Query contracts

Создать internal read-only:

```text
ObservationReadService
```

В v1 не создавать HTTP routes/Flask blueprint.

Минимальные methods по смыслу:

```text
get_client_observations(site_id, client_mac, from_utc, to_utc, limit, cursor)
get_site_client_observations(site_id, from_utc, to_utc, ssid=None, ap_mac=None, radio_id=None, limit=..., cursor=None)
get_latest_client_observation(site_id, client_mac)

get_ap_observations(site_id, ap_mac, from_utc, to_utc, limit, cursor)
get_ap_radio_observations(site_id, ap_mac, from_utc, to_utc, band=None, limit=..., cursor=None)
get_latest_ap_observation(site_id, ap_mac)
get_latest_ap_radio_observations(site_id, ap_mac)
get_latest_ap_config(site_id, ap_mac)
```

Правила:

- `site_id` обязателен;
- cross-site query v1 не добавлять;
- MAC canonicalize common utility;
- `from_utc <= to_utc`;
- strict UTC timestamp;
- default limit 500;
- hard max 2000;
- stable order;
- opaque cursor для caller;
- continuation по `(observed_at, row_id)`;
- malformed cursor → explicit validation error;
- возвращать immutable DTOs, не `sqlite3.Row`;
- query service read-only.

Query layer возвращает facts, но не вычисляет business analytics (`weak_signal`, `needs_second_ap`, visitor return rate и т.п.).

---

## 20. Operational telemetry

Использовать existing telemetry/logger boundary.

Не создавать JSONL data journal с полным observation payload в v1.

Минимальная семантика events:

```text
observation.runtime_started
observation.runtime_stopped
observation.runtime_unavailable
observation.client_cycle_completed
observation.client_cycle_failed
observation.client_duplicate_mac
observation.ap_cycle_completed
observation.ap_cycle_failed
observation.ap_endpoint_failed
observation.ap_rate_reset
observation.ap_config_captured
observation.ap_config_unchanged
observation.ap_config_failed
observation.cleanup_completed
observation.cleanup_partial
observation.cleanup_failed
observation.storage_error
```

Названия можно привести к current telemetry style.

Summary fields:

```text
site_id
cycle_id
component
state
duration_ms
complete
items_seen
items_stored
items_skipped
error_count
duplicate_mac_count
unknown_auth_status_count
rate_reset_source
rate_reset_direction
wired_rate_reset_count
lan_rate_reset_count
radio_rate_reset_count
cleanup_deleted_count
failure_category
http_status
error_code
```

`observation.ap_rate_reset` обязан указывать `source` (`wired|lan|radio`) и direction/band, если применимо. Generic reset telemetry не заменяет per-source persisted rate reasons.

Не отправлять per-client detailed RSSI/traffic payload в operational telemetry.

Observation DB — authoritative detailed source.

---

## 21. Security / data minimization

Никогда не сохранять/логировать:

- Access Token;
- Client Secret;
- Authorization header;
- cookies;
- Controller admin credentials;
- SSID password;
- environment/settings dictionary с secrets;
- full `/override` response;
- raw response headers.

MAC сохраняется полностью.

Принцип «максимум данных» означает:

```text
максимум полезных, подтверждённых и безопасных данных
```

а не blind raw dumps.

---

## 22. Acquisition ≠ Analytics

Запрещено сохранять business interpretation как source fact:

```text
signal_quality=poor
ap_placement=bad
needs_second_ap=true
```

Сохранять факты:

```text
rssi=-78
snr=17
busy_util=82
retry counters=...
```

Future Analytics применит thresholds позже к уже накопленной истории.

Неизвестный enum не получает выдуманную расшифровку.

Missing numeric field → NULL, а не 0.

---

## 23. Lifecycle / state / shutdown

Factory/runtime, например:

```text
create_observation_foundation(settings, provider, telemetry)
```

создаётся только в `run.py`.

Никаких threads при import.

Workers:

```text
ClientObservationWorker
APObservationWorker
ObservationCleanupWorker
```

Fixed-delay, no overlap, interruptible wait, idempotent stop.

Runtime states:

```text
disabled
starting
active
degraded
unavailable
stopping
```

Transient cycle/source/busy error → degraded; successful following cycles могут вернуть active.

Fatal config/schema/corruption startup → unavailable until restart/operator action.

### Recommended shutdown order

```text
Pending Cleaner stop
→ Observation Foundation stop
→ Public Traffic stop
→ Auth executor drain
→ Snapshot Collector drain
→ Visitor Registry stop
```

Observation stop:

- no new cycles;
- interrupt waits;
- bounded current HTTP;
- finish short DB transaction;
- no new request after stopping;
- overall shutdown timeout 20 sec default.

Existing Snapshot shutdown contract не менять.

---

## 24. Fail-open invariant

```text
Observation failure
must not become CaptivPortal failure.
```

Ошибка Client/AP observer, normalization, DB, cleanup/query не должна:

- останавливать portal;
- менять AuthSession/AuthWorker;
- менять authorization result/retry;
- менять CAPPORT;
- выполнять reconnect;
- менять Cleaner;
- менять Snapshot Collector;
- менять Visitor Registry;
- показываться visitor browser.

---

## 25. Future Multi-Site Compatibility

Observation Foundation — Site-specific subsystem.

Обязательно:

- каждый persisted row содержит `site_id`;
- каждый query требует `site_id`;
- config допускает несколько Site IDs;
- нет hardcode Site/SSID;
- client MAC не объявляется global future Tenant identity;
- Site+MAC — current Site-scoped key;
- Tenant entity/tenant_id сейчас не вводятся;
- `Tenant != Site`;
- shared OmadaProvider сохраняется;
- второй Site должен добавляться config change без rewrite storage/query contracts.

---

## 26. Product / Observability Boundary

Authoritative historical source:

```text
future Analytics/Admin service
→ ObservationReadService
→ ObservationRepository
→ observations.sqlite3
```

Запрещён целевой product backend:

```text
Admin Console → Grafana API → Loki
```

Grafana/Loki/Alloy не входят в TASK.

---

## 27. Capacity assessment — обязательный Phase A gate

Capacity measurement переносится **до Client/AP implementation**.

До начала PR B и PR C PR A обязан иметь работоспособную schema/repository prototype и измерить representative SQLite row/index overhead.

При client interval 60 sec:

```text
300 average active clients
× 1 row/minute
× 1440 minutes/day
× 180 days
= 77,760,000 client rows
```

Это только client observations, без AP/radio rows и indexes. Поэтому 180-day retention является proposed default, а не автоматически принятым production contract.

Phase A обязан дать estimate минимум для:

```text
30 average active authorized clients
100 average active authorized clients
300 average active authorized clients

1 AP
10 AP
```

и минимум для candidate retentions:

```text
30 days
90 days
180 days
```

Отчёт:

```text
client rows/day
AP rows/day
radio rows/day
measured DB bytes/representative row set
index overhead
estimated MB/GB per day
estimated DB size at 30/90/180 days
cleanup cost sample
representative query latency
```

### Gate

**PR B Client Collector и PR C AP Collector нельзя начинать до review/acceptance Phase A capacity result Tech Lead/архитектором.**

Если 180-day raw retention неразумен:

- не менять silently;
- вернуть recommendation: cadence/retention/schema adjustment;
- если требуется rollup/downsampling design — это отдельное архитектурное уточнение до PR B;
- если SQLite не подходит — stop condition до выбора другого backend.

---

## 28. Backup expectations

Backup infrastructure не настраивать.

В handoff описать:

- DB/WAL/SHM files;
- consistency requirement;
- нужен ли SQLite backup API/checkpoint перед file-copy backup;
- рекомендуемый consistent backup procedure.

---

## 29. Разрешённые файлы после утверждения

### New

```text
app/observations/**
app/controllers/omada_observations.py
tests/observations/**
tests/test_omada_observations.py
```

### Modify only if required

```text
app/controllers/__init__.py
app/config.py
app/settings.py
run.py
.env.example
```

Если нужен другой runtime file — stop condition и запрос расширения scope.

---

## 30. Запрещённые области

Не изменять:

```text
app/auth/**
app/capport/**
app/web/**
app/visitor_registry/snapshot_*
app/visitor_registry/registry_*
app/pending_sessions/**
app/controllers/omada_pending_sessions.py
app/public_traffic/**
app/portal_counter/**
app/integrations/omada/webhook_*
requirements*.txt
.github/workflows/**
```

Не менять Grafana/Alloy/Loki/systemd/Nginx/production environment.

### Knowledge Base boundary

Coder в этом TASK не обновляет:

```text
docs/architecture.md
docs/module-index.md
docs/project-inventory.md
docs/modules/**
AGENTS.md
.github/copilot-instructions.md
```

После runtime acceptance отдельный Knowledge Base TASK получает начальник базы знаний.

---

## 31. Dependencies

Только stdlib + current dependencies.

Persistence:

```text
sqlite3
```

Не добавлять SQLAlchemy/Postgres/time-series DB client.

Новая dependency требует отдельного согласования.

---

## 32. Обязательные targeted tests

### Configuration

- master disabled;
- valid enabled;
- empty Site IDs invalid when enabled;
- invalid bool/interval/retention;
- AP page/max rows/max pages validation;
- AP cycle deadline/request budget validation;
- inventory max stale validation;
- rate max gap validation;
- subflag semantics;
- SSID parsing;
- duplicate Site IDs;
- no production values.

### Provider

- client pagination;
- AP `/devices` pagination complete/partial;
- AP max pages/max rows;
- duplicate AP MAC;
- malformed totalRows/result/JSON;
- HTTP errors;
- nonzero errorCode;
- exact -44112 one guarded refresh/retry;
- unknown errorCode no guessed retry;
- timeout/network;
- AP inventory type filter;
- all dynamic endpoints;
- all slow endpoints;
- safe v2 override strips password before return;
- recursive nested allowlists drop unknown children;
- defensive copies;
- invalid arguments;
- no secrets in Result.

No real Controller calls in tests.

### Client normalizer/worker

- full/minimal row;
- invalid MAC/IP;
- bool-as-int rejected;
- numeric string not silently converted;
- NaN/Infinity;
- unknown enum/radio ID;
- active/auth eligibility;
- SSID allowlist;
- duplicate MAC;
- partial inventory complete=false;
- failed first page stores no rows;
- structured nested unknown fields dropped;
- shutdown/no overlap.

### AP normalizer/rates/worker

- overview/wired/LAN/radio normalization;
- AP inventory stale within max allowed;
- AP inventory older than max stale blocks polling;
- cycle deadline truncates new requests;
- request budget truncates new requests;
- rotating AP cursor avoids starvation;
- unknown enums raw;
- channel parse failure preserves raw;
- first rate NULL/no_baseline;
- positive delta;
- wired reset does not null LAN/radio;
- LAN reset does not null wired/radio;
- one radio band reset does not affect another;
- gap > configured max;
- exact section timestamps used for delta;
- radio rates named/semantically aggregate (`radio_tx_mbps`, `radio_rx_mbps`);
- partial endpoint success;
- partial AP config does not create config snapshot/hash/latest;
- complete config hash stable;
- unchanged complete config dedup;
- changed complete config stored;
- no thread per AP.

### Repository/cleanup

- schema v1/user_version/indexes;
- FK enabled and validated;
- UNIQUE client within cycle;
- UNIQUE AP within cycle;
- UNIQUE radio within AP observation;
- cascade behavior;
- cycle running creation;
- normal finalize;
- startup recovery running→abandoned;
- cleanup absent from observation_cycles;
- timestamp fixed-width UTC lexical ordering;
- quick_check;
- schema newer mismatch;
- POSIX mode;
- atomic batches;
- config unique hash;
- CHECK/null semantics;
- busy/full/corruption classification;
- retention cutoffs;
- bounded batches/time;
- cleanup interruption;
- no auto-drop/recreate.

### Query service

- Site+MAC history;
- site filters;
- AP/radio histories;
- latest methods/config;
- latest config ignores partial attempts because partial rows do not exist;
- stable order;
- limit/max;
- cursor no gap/duplicate;
- malformed cursor;
- invalid time/MAC;
- no cross-site leakage;
- abandoned/running cycle behavior documented/filterable;
- immutable DTOs.

### Lifecycle/integration

- disabled = zero Omada calls;
- fixed-delay/no overlap;
- provider/storage failure fail-open;
- shared provider object identity preserved;
- no provider construction inside module;
- start/stop idempotent/bounded;
- no request after stopping.

---

## 33. Existing regression tests и per-PR regression gates

### Pre-change baseline

До любых изменений выполнить section 2.2 full Linux baseline на exact `a79e0a3` (либо новом exact `origin/main` по описанному правилу) и сохранить результаты.

### PR A — Storage/Foundation

После targeted storage/query/cleanup/capacity tests выполнить минимум:

```bash
python -m pytest -q tests/visitor_registry/test_device_registry*.py --tb=short
python -m pytest -q tests/visitor_registry/test_snapshot_*.py --tb=short
```

и full gate перед передачей PR A на review.

### PR B — Client Observation Collector

После targeted client/provider tests обязательно:

```bash
python -m pytest -q tests/visitor_registry/test_snapshot_*.py --tb=short
python -m pytest -q tests/pending_sessions --tb=short
python -m pytest -q tests/test_omada_client_lookup.py --tb=short
```

плюс фактические CAPPORT/shared-provider tests current main и full gate.

### PR C — AP Observation + integration

После targeted AP/provider/lifecycle tests повторить Snapshot/Cleaner/shared-provider regressions и full gate.

Acceptance для всех PR:

```text
Snapshot runtime/schema changes = 0
Cleaner safety regression = 0
CAPPORT/auth provider regression = 0
new failure vs saved pre-change baseline = 0, либо явно доказанный unrelated baseline/environment issue
```

Нельзя использовать результат предыдущего PR как замену gate текущего PR.

---

## 34. Preferred targeted commands

Фактические names Coder указывает в handoff.

PR A ожидаемо:

```bash
python -m pytest -q tests/observations/test_repository*.py tests/observations/test_read_service*.py tests/observations/test_cleanup*.py --tb=short
```

PR B ожидаемо:

```bash
python -m pytest -q tests/observations/test_client*.py tests/test_omada_observations.py --tb=short
```

PR C ожидаемо:

```bash
python -m pytest -q tests/observations/test_ap*.py tests/observations/test_runtime*.py tests/test_omada_observations.py --tb=short
```

После targeted — соответствующие section 33 regressions.

---

## 35. Full gate

Full gate выполняется:

1. один раз **до изменений** как baseline;
2. после PR A;
3. после PR B;
4. после PR C.

Команды:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
```

Зафиксировать exact SHA/passed/skipped/failed для каждого gate.

Unrelated baseline/environment failure не исправлять вне scope: сравнить с сохранённым pre-change baseline, доказать классификацию и передать Tech Lead.

PR не объявляется green только по targeted tests, если его обязательный full gate не имеет reviewable verdict.

---

## 36. Security tests

Использовать markers:

```text
TEST_ACCESS_TOKEN_SHOULD_NOT_LEAK
TEST_CLIENT_SECRET_SHOULD_NOT_LEAK
TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK
```

Доказать отсутствие markers в:

- Result data;
- exception text;
- SQLite;
- telemetry;
- captured stdout/stderr;
- config snapshots.

Не grep production environment.

---

## 37. Performance/boundedness

Обязательно:

- bounded client pagination;
- bounded AP `/devices` pagination;
- AP page/max rows/max pages;
- AP inventory max stale age;
- per-request timeout;
- AP dynamic/config request budgets;
- AP dynamic/config monotonic deadlines;
- rotating AP processing cursor при truncation;
- bounded cleanup;
- short DB transactions;
- no unbounded queue;
- no per-client thread;
- no thread per AP;
- no concurrent page GET;
- no N+1 detail polling clients;
- AP worker sequential by default;
- no full-table load для обычного query.

Bounded AP parallelism допускается только отдельным последующим architecture review; default v1 — sequential AP requests.

Cadence не считается fixed-rate SLA. Если cycle длится дольше обычного, следующий cycle начинается только после configured fixed delay.

---

## 38. Production activation НЕ входит

Repository default:

```text
OBSERVATION_FOUNDATION_ENABLED=false
```

Coder не должен:

- менять production EnvironmentFile;
- создавать production DB руками;
- restart service;
- включать long-running production polling;
- настраивать Grafana/Alloy;
- выполнять live Controller polling из tests.

После merge нужен отдельный deploy/activation TASK.

---

## 39. Acceptance criteria

Implementation готов к final review только если:

1. pre-change Linux baseline сохранён до modifications;
2. обязательный PR A/PR B/PR C split соблюдён;
3. PR B/C не начаты до capacity gate PR A;
4. создан независимый `app/observations` subsystem;
5. Snapshot Collector runtime files не изменены;
6. Visitor Registry schema не изменена;
7. тот же shared OmadaProvider;
8. нет второго token lifecycle;
9. client observations соответствуют eligibility v1;
10. AP `/devices` pagination bounded;
11. duplicate AP MAC безопасно обрабатывается;
12. AP inventory stale cache имеет hard max age;
13. AP dynamic/config cycles имеют deadline + request budget;
14. cadence и `OBSERVATION_RATE_MAX_GAP_SECONDS` согласованы;
15. radio rates названы `radio_tx_mbps/radio_rx_mbps` и документированы как aggregate AP radio traffic;
16. wired/LAN/radio rate reasons независимы;
17. cycle lifecycle поддерживает running/completed/abandoned и startup recovery;
18. cleanup не конфликтует с Site-scoped observation_cycles;
19. repository FK/UNIQUE/idempotency contracts реализованы;
20. partial AP config не создаёт hash/latest snapshot;
21. nested structured data проходит recursive allowlists; unknown children drop;
22. единый fixed-width UTC timestamp contract соблюдён;
23. section-specific timestamps используются для AP rate deltas;
24. AP dynamic использует подтверждённые endpoints;
25. slow config complete change-only работает;
26. `/override` password не выходит из safe provider method;
27. raw cumulative counters сохранены;
28. reset/gap rules работают per source/direction;
29. все observation rows Site-aware;
30. schema v1/indexes/FK/UNIQUE созданы;
31. query contracts работают без HTTP routes;
32. retention bounded и подтверждён Phase A capacity decision;
33. fail-open подтверждён;
34. no analytics thresholds;
35. no Grafana/Loki dependency;
36. no new external dependency;
37. targeted tests green;
38. per-PR regressions green/reviewed;
39. per-PR full gates documented;
40. compileall PASS;
41. diff-check PASS;
42. security markers PASS;
43. capacity assessment приложен и принят до PR B/C;
44. diff только allowed scope;
45. production не изменялась.

---

## 40. Stop conditions

Остановить затронутую часть, если:

- current main runtime существенно отличается;
- **pre-change full Linux baseline не выполнен/не зафиксирован**;
- фактический Omada endpoint/field не подтверждается;
- `/devices` pagination contract невозможно сделать bounded на подтверждённом API;
- AP cycle deadline/request budget требуют unbounded concurrency для заявленной полноты;
- safe `/override` невозможен без raw persistence;
- nested structured field нельзя сохранить без unknown-key pass-through — такой field нужно omit, а не сохранять raw;
- требуется менять Snapshot/Auth/CAPPORT/Visitor Registry;
- требуется новый provider/token manager;
- требуется external dependency;
- Phase A capacity assessment показывает неприемлемый raw volume и требуется новое retention/rollup/backend решение;
- требуется Redis/Postgres/time-series DB;
- full suite имеет unrelated failure, который нельзя классифицировать относительно baseline;
- требуется Grafana/Alloy/systemd;
- требуется production credential/live controller.

Независимые безопасные части продолжить, если возможно, но PR B/C не начинать при незакрытом capacity gate PR A.

---

## 41. Обязательное разбиение реализации

Разделение на три PR является **обязательным**, а не рекомендацией.

### PR A — Storage / Query / Cleanup / Capacity Gate

Scope:

```text
config/models needed for storage
schema
repository
FK/UNIQUE/idempotency
cycle lifecycle/recovery
query contracts
cleanup
UTC timestamp contract
capacity measurement
```

PR A не включает Omada periodic workers.

Exit gate PR A:

- targeted tests green;
- full gate verdict;
- capacity report;
- Tech Lead/архитектор принимает cadence/retention direction.

**До этого PR B и PR C не начинать.**

### PR B — Client Observation Collector

Scope:

```text
client inventory provider
client pagination
client normalizer
recursive structured allowlists
eligibility
duplicate MAC
client worker
client cycle metadata
```

Exit gate:

- targeted client/provider tests;
- Snapshot/Cleaner/CAPPORT/shared-provider regressions;
- full gate.

### PR C — AP Observation Collector + rates + lifecycle integration

Scope:

```text
AP /devices pagination
inventory cache + max stale
AP dynamic/config deadlines/request budgets
rotating AP cursor
AP dynamic endpoints
section timestamps
wired/LAN/radio rate semantics
complete-only AP config
safe recursive allowlists
safe /override
run.py lifecycle integration
telemetry
```

Exit gate:

- targeted AP/lifecycle/security tests;
- Snapshot/Cleaner/shared-provider regressions;
- full gate.

Production activation остаётся отдельным TASK после merge/acceptance PR C.

---

## 42. Repository actions после утверждения

Разрешено после явного утверждения TASK:

- fetch;
- feature branch;
- allowed file changes;
- tests/checks;
- локальные commits после green targeted tests.

После утверждения использовать отдельные feature branches для обязательных PR, например:

```text
feature/observation-storage-v1
feature/client-observation-v1
feature/ap-observation-v1
```

PR B базируется только на принятом/merged PR A baseline; PR C — на принятом/merged результате A+B по решению Tech Lead.

Без отдельного owner разрешения запрещено:

- push;
- Draft PR;
- merge;
- force/rewrite history;
- tag/release;
- deploy/restart;
- production env changes.

---

## 43. Handoff format

Coder возвращает:

### IMPLEMENTED / NOT IMPLEMENTED

Фактический scope.

### BASELINE

```text
origin/main SHA at start
branch
runtime changes since TASK draft
```

### FILES INSPECTED / FILES CHANGED

Каждый changed file + причина.

### CONTRACTS

```text
Snapshot contract changed: NO
Visitor Registry schema changed: NO
Auth/CAPPORT contract changed: NO
shared OmadaProvider preserved: YES
new token manager: NO
```

### STORAGE

```text
DB path
schema version
tables/indexes
retention
cleanup
WAL/backup notes
```

### CLIENT OBSERVATION

```text
interval
eligibility
fields
pagination
partial behavior
```

### AP OBSERVATION

```text
dynamic/inventory/config intervals
endpoints
rates/reset
safe override
```

### QUERY CONTRACTS

Фактические methods/cursors.

### PRE-CHANGE BASELINE

Exact SHA + full Linux passed/skipped/failed/compileall/diff-check до изменений.

### TESTS / RESULTS

Exact targeted/regression/full-gate commands + passed/skipped/failed для текущего PR.

### CAPACITY ASSESSMENT

Estimates table.

### SECURITY CHECK

Secret-marker verdict.

### UNVERIFIED AREAS / KNOWN RISKS

Отдельно.

### REPOSITORY ACTIONS

```text
Branch created: yes/no
Commit created: yes/no
Push completed: yes/no
Draft PR opened: yes/no
Merge completed: no
Deployment completed: no
```

### NEXT OWNER ACTION

Что должен сделать Tech Lead/owner.

---

## 44. Knowledge Base owner action после runtime acceptance

Coder в этом TASK не выполняет KB update.

После merge начальнику базы знаний отдельным TASK обновить минимум:

```text
docs/project-inventory.md
docs/architecture.md
docs/module-index.md
docs/testing.md
docs/deployment.md
docs/security.md
docs/api/omada-open-api.md
new Observation Foundation module document
```

Historical research не переписывать.

---

## 45. Итоговый invariant

```text
AuthorizedClientSnapshotCollector
=
одна стартовая фотография после AUTHORIZED

Observation Foundation
=
периодическая история фактического client/AP состояния

Visit Lifecycle
=
будущая временная бизнес-граница посещения

Analytics
=
будущий downstream consumer сохранённых фактов
```

Observation Foundation не смешивает эти ответственности.

---

## 46. REV2 correction checklist

Перед финальным утверждением ревьюер должен подтвердить, что REV2 закрывает обязательные замечания:

```text
[ ] AP /devices pagination + AP_PAGE_SIZE/MAX_PAGES/MAX_ROWS
[ ] duplicate AP MAC handling
[ ] AP dynamic/config cycle deadline + request budget
[ ] AP inventory max stale
[ ] cadence/rate-gap consistency
[ ] radio rate names are aggregate AP radio rates
[ ] wired/LAN/radio independent reset/rate reasons
[ ] running/completed/abandoned cycle lifecycle + crash recovery
[ ] cleanup removed from Site-scoped observation_cycles
[ ] repository FK + UNIQUE/idempotency
[ ] partial AP config cannot become latest/hash
[ ] recursive nested allowlists / unknown nested fields dropped
[ ] Phase A capacity gate before Client/AP implementation
[ ] pre-change exact-main Linux regression baseline
[ ] fixed-width UTC timestamp contract
[ ] source-specific AP timestamps used for rate deltas
[ ] mandatory PR A / PR B / PR C split
```

---

## 47. Review gate

Этот документ передаётся только на короткую финальную проверку.

До явной команды owner/архитектора:

```text
TASK Observation Foundation v1 утверждено, начинать PR A
```

Coder не должен создавать implementation branch, менять code/tests, commit/push/PR/deploy.

После общего approval разрешение распространяется сначала только на **PR A**. PR B и PR C разблокируются их обязательными gates из section 41.
