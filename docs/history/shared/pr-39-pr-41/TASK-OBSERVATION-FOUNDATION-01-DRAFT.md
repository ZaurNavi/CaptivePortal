# TASK-OBSERVATION-FOUNDATION-01 — Observation Foundation v1

**Проект:** CaptivPortal  
**Тип:** master implementation TASK / архитектурное ТЗ  
**Статус документа:** DRAFT FOR REVIEW  
**Implementation authorization:** НЕ ДАНО — реализацию не начинать до отдельного утверждения owner/архитектора  
**Execution mode после утверждения:** `implementation`  
**Исполнитель:** Coder / coding agent  
**Review:** Tech Lead + архитектор + owner  
**Test responsibility:** `agent`, production acceptance — `owner/Tech Lead`  
**Дата:** 11 августа 2026 года

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

Фактический `main` на момент подготовки документа:

```text
a79e0a302fd252a98c9f6f279244ed35f2266871
```

Runtime merge:

```text
ab776af3fc58dc090e17ecd20534abddc1f33ad3
```

Проверенное сравнение `ab776af..a79e0a3` содержит только README и knowledge-base/documentation изменения. Runtime code после `ab776af` в этом диапазоне не менялся.

Перед началом реализации Coder обязан выполнить:

```bash
git fetch origin
git rev-parse origin/main
git status --short
```

Если после даты TASK появились runtime-изменения в связанных областях, остановить затронутую часть и передать Tech Lead список файлов и влияние на TASK.

### 2.2. CAPPORT acceptance

Owner сообщил примерно 20 успешных физических production-тестов на реальных телефонах, включая телефоны гостей.

Для настоящего TASK CAPPORT live acceptance считается закрытым owner evidence и не входит в scope Observation Foundation.

Формальное обновление status/debt registry выполняет Tech Lead отдельно.

### 2.3. Existing architecture

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
OBSERVATION_AP_CONFIG_INTERVAL_SECONDS=21600

OBSERVATION_REQUEST_TIMEOUT_SECONDS=5

OBSERVATION_CLIENT_PAGE_SIZE=500
OBSERVATION_CLIENT_MAX_PAGES=20
OBSERVATION_CLIENT_MAX_ROWS=10000

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

Все rows содержат `site_id`.

### Client SSIDs

`OBSERVATION_CLIENT_SSIDS`:

- optional CSV exact allowlist;
- case-sensitive;
- пустое значение = все SSID configured Sites;
- filter применяется только к Client Observation.

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

**Safe structured**

```text
ip_setting_json
rate_limit_json
client_lock_to_ap_setting_json
multi_link_json
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

### 11.1. AP inventory

AP worker держит in-memory AP inventory per Site.

Refresh default:

```text
300 sec
```

Первый cycle получает inventory сразу.

Если последующий refresh failed, допускается временно использовать последний successful cache и зафиксировать stale inventory age. После restart cache пустой.

### 11.2. Dynamic polling

Default:

```text
30 sec
```

На AP собирать best-effort sections:

```text
overview
wired_uplink
lan_traffic
radios
```

Section failures независимы. Успешные sections сохранять, row/cycle помечать partial.

### 11.3. AP overview fields

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

### 11.4. Wired uplink

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

### 11.5. LAN traffic

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

### 11.6. Radio rows

Для каждого band сохранять:

```text
site_id
ap_mac
observed_at
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

### Wired

```text
wired_download_mbps = ΔdownBytes * 8 / ΔT / 1_000_000
wired_upload_mbps   = ΔupBytes   * 8 / ΔT / 1_000_000
```

### LAN

Отдельно:

```text
lan_rx_mbps
lan_tx_mbps
```

### Radio

```text
client_download_mbps ≈ Δradio.tx * 8 / ΔT / 1_000_000
client_upload_mbps   ≈ Δradio.rx * 8 / ΔT / 1_000_000
```

Rate вычисляется только если:

- есть previous stored observation того же source identity;
- new counter >= old counter;
- elapsed > 0;
- elapsed <= 120 sec.

Если counter уменьшился:

```text
counter_reset = true
rate = NULL
```

Если gap >120 sec:

```text
rate = NULL
rate_reason = gap_too_large
```

Не выдавать long-gap average как current speed.

---

## 13. AP slow-changing configuration

Default interval:

```text
21600 sec / 6 h
```

Новый config snapshot записывать только если:

- первый successful snapshot AP;
- или safe normalized configuration изменилась.

Dedup:

```text
config_sha256
```

по canonical strict JSON.

### Safe sections

**general-config**

```text
name
led_setting_code
tag_ids
location
```

**ip-setting**

```text
mode
configured IP/mask/gateway
preferred/alternate DNS
DHCP fallback settings
```

**radio-config**

```text
radio enabled
configured channel
channel width code
TX power
TX power level code
wireless mode code
channel ranges/limits
```

**ofdma** — support/enabled flags.

**available-channel** — channels/frequencies/widths.

**rf-scan v2**

```text
time
status
status2g
status5g
status5g2
status6g
```

Unknown enum codes не расшифровывать предположением.

### Критическая безопасность `/override`

Использовать только v2 через provider method `get_ap_safe_overrides()`.

Разрешённые fields:

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
started_at TEXT NOT NULL
finished_at TEXT
complete INTEGER NOT NULL
result TEXT NOT NULL
source_rows_reported INTEGER
items_seen INTEGER NOT NULL
items_stored INTEGER NOT NULL
items_skipped INTEGER NOT NULL
error_count INTEGER NOT NULL
data_quality_warning_count INTEGER NOT NULL
created_at TEXT NOT NULL
```

`kind` v1:

```text
client
ap_dynamic
ap_config
cleanup
```

`result`:

```text
success
partial
failed
shutdown
```

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

### client_observations

Обязательные identity:

```text
row_id INTEGER PRIMARY KEY
cycle_id TEXT NOT NULL
observed_at TEXT NOT NULL
site_id TEXT NOT NULL
client_mac TEXT NOT NULL
source_inventory_complete INTEGER NOT NULL
```

Остальные normalized fields nullable.

### ap_observations

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
counter_reset INTEGER NOT NULL
```

Плюс overview/wired/LAN fields и derived rates.

### ap_radio_observations

```text
row_id INTEGER PRIMARY KEY
cycle_id TEXT NOT NULL
ap_observation_row_id INTEGER NOT NULL
observed_at TEXT NOT NULL
site_id TEXT NOT NULL
ap_mac TEXT NOT NULL
band TEXT NOT NULL
counter_reset INTEGER NOT NULL
```

Плюс radio fields/rates.

### ap_config_snapshots

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

`config_json` — strict safe allowlisted normalized JSON.

Unique:

```text
(site_id, ap_mac, config_sha256)
```

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

ap_radio_observations(site_id, ap_mac, band, observed_at, row_id)

ap_config_snapshots(site_id, ap_mac, captured_at, row_id)

observation_cycles(site_id, kind, started_at)
```

Порядок columns допускается менять только с query/benchmark justification.

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

Default:

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

Default:

```text
730 days
```

Для `ap_config_snapshots` / config cycles.

Config snapshots change-only, поэтому имеют малый volume и длинную историческую ценность.

### Cleanup Worker

Fixed-delay:

```text
initial delay 900 sec
interval 86400 sec
max runtime 30 sec
batch size 5000
```

Cleanup:

1. UTC cutoffs;
2. bounded batches;
3. shutdown check между batches;
4. max duration;
5. expired cycles cleanup;
6. lightweight optimize/maintenance;
7. summary telemetry.

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
observation.ap_counter_reset
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
counter_reset_count
cleanup_deleted_count
failure_category
http_status
error_code
```

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

## 27. Capacity assessment

До implementation complete Coder обязан измерить representative SQLite row/index overhead на synthetic/test DB и дать estimate минимум для:

```text
30 average active authorized clients
100 average active authorized clients
300 average active authorized clients
1 AP
10 AP
```

при defaults.

Отчёт:

```text
client rows/day
AP rows/day
radio rows/day
estimated MB/GB per day
estimated size at 30/90/180 days
```

Если 180-day default неразумен для фактического SQLite design, не менять retention молча: вернуть recommendation Tech Lead до production activation.

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
- subflag semantics;
- SSID parsing;
- duplicate Site IDs;
- no production values.

### Provider

- client pagination;
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
- shutdown/no overlap.

### AP normalizer/rates/worker

- overview/wired/LAN/radio normalization;
- unknown enums raw;
- channel parse failure preserves raw;
- first rate NULL;
- positive delta;
- reset;
- gap >120 sec;
- per-band reset;
- partial endpoint success;
- config hash stable;
- unchanged config dedup;
- changed config stored;
- AP inventory cache/refresh;
- no thread per AP.

### Repository/cleanup

- schema v1/user_version/indexes;
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
- stable order;
- limit/max;
- cursor no gap/duplicate;
- malformed cursor;
- invalid time/MAC;
- no cross-site leakage;
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

## 33. Existing regression tests

Обязательно:

```bash
python -m pytest -q tests/visitor_registry/test_snapshot_*.py
python -m pytest -q tests/pending_sessions
```

и targeted shared Omada/CAPPORT tests, включая `tests/test_omada_client_lookup.py` или фактические эквиваленты current main.

Acceptance:

```text
Snapshot runtime/schema changes = 0
Cleaner safety regression = 0
CAPPORT/auth provider regression = 0
```

---

## 34. Preferred targeted command

Фактические names Coder указывает в handoff.

Ожидаемо:

```bash
python -m pytest -q tests/observations tests/test_omada_observations.py --tb=short
```

После этого существующие regression groups.

---

## 35. Full gate

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
```

Зафиксировать exact SHA/passed/skipped/failed.

Unrelated baseline failure не исправлять вне scope: доказать baseline и передать Tech Lead.

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

- bounded pagination/timeouts/cleanup;
- short DB transactions;
- no unbounded queue;
- no per-client thread;
- no thread per AP;
- no concurrent page GET;
- no N+1 detail polling clients;
- AP worker sequential by default;
- no full-table load для обычного query.

Bounded AP parallelism допускается только с отдельным justification/test; default v1 — sequential AP polling.

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

Implementation готов к review только если:

1. создан независимый `app/observations` subsystem;
2. Snapshot Collector runtime files не изменены;
3. Visitor Registry schema не изменена;
4. тот же shared OmadaProvider;
5. нет второго token lifecycle;
6. client observations соответствуют eligibility v1;
7. AP dynamic использует подтверждённые endpoints;
8. slow config change-only работает;
9. `/override` password не выходит из safe provider method;
10. raw cumulative counters сохранены;
11. reset/gap rules работают;
12. все rows Site-aware;
13. schema v1/indexes созданы;
14. query contracts работают без HTTP routes;
15. retention bounded;
16. fail-open подтверждён;
17. no analytics thresholds;
18. no Grafana/Loki dependency;
19. no new external dependency;
20. targeted tests green;
21. Snapshot/Cleaner/provider regressions green;
22. full gate documented;
23. compileall PASS;
24. diff-check PASS;
25. security markers PASS;
26. capacity assessment приложен;
27. diff только allowed scope;
28. production не изменялась.

---

## 40. Stop conditions

Остановить затронутую часть, если:

- current main runtime существенно отличается;
- фактический Omada endpoint/field не подтверждается;
- endpoint требует mutation;
- safe `/override` невозможен без raw persistence;
- требуется менять Snapshot/Auth/CAPPORT/Visitor Registry;
- требуется новый provider/token manager;
- требуется external dependency;
- SQLite capacity assessment требует другой backend;
- требуется Redis/Postgres/time-series DB;
- full suite имеет unrelated failure;
- требуется Grafana/Alloy/systemd;
- требуется production credential/live controller.

Независимые безопасные части продолжить, если возможно.

---

## 41. Implementation phases

Master TASK можно разбить:

### Phase A — Storage/Foundation

```text
config
models
repository
schema
query contracts
cleanup
```

### Phase B — Client Observer

```text
provider client inventory
normalization
worker
cycle metadata
```

### Phase C — AP Observer

```text
AP inventory
dynamic endpoints
rates
safe config endpoints
change-only snapshots
```

### Phase D — Integration

```text
run.py lifecycle
telemetry
full regression
capacity assessment
```

Рекомендуемый PR split после отдельного разрешения:

```text
PR A — Observation storage + query foundation
PR B — Client Observation Collector
PR C — AP Observation Collector + lifecycle integration
```

Tech Lead может разрешить один reviewable PR.

---

## 42. Repository actions после утверждения

Разрешено после явного утверждения TASK:

- fetch;
- feature branch;
- allowed file changes;
- tests/checks;
- локальные commits после green targeted tests.

Рекомендуемая branch:

```text
feature/observation-foundation-v1
```

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

### TESTS / RESULTS

Exact commands + passed/skipped/failed.

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

## 46. Review gate

Этот документ передаётся только на ревью.

До явной команды owner/архитектора:

```text
TASK Observation Foundation v1 утверждено, начинать реализацию
```

Coder не должен создавать branch, менять code/tests, commit/push/PR/deploy.

Разрешено только review/feedback по настоящему TASK.
