# TASK-OBSERVATION-FOUNDATION-01C — AP Observation Collector and Runtime Integration v1

**Проект:** CaptivPortal  
**Тип:** отдельное implementation TASK, этап 3 из 3  
**Статус:** READY FOR HANDOFF — gates 01A/01B закрыты; старт только по отдельной команде owner  
**Implementation authorization:** НЕ ДАНО — документ можно передать Coder заранее, code/tests начинать только после команды из раздела 1  
**Исполнитель:** Coder / coding agent  
**Review:** Tech Lead + архитектор + owner  
**Источник:** `TASK-OBSERVATION-FOUNDATION-01-DRAFT-REV2`  
**Дата:** 11 августа 2026 года

## 1. Условие разблокировки

На 11 августа 2026 года подтверждено:

- 01A storage/query/cleanup merged/accepted в `main`;
- capacity decision закрыт: SQLite, dynamic retention 180 дней,
  config retention 730 дней, reserve не менее 150 GB;
- 01B Client Collector merged/accepted через PR `#40`;
- shared provider сохранён, Snapshot/Auth/CAPPORT regressions 01B reviewed;
- `origin/main` после merge 01B равен
  `578c7c83d687e04c620256c2a90f22410f801803`.

Остаётся только явная команда owner на старт реализации:

```text
TASK Observation Foundation 01C утверждено, начинать AP Collector v1.
```

До этой команды Coder может только прочитать ТЗ и подтвердить готовность; branch,
code и tests не начинать. После команды разрешены branch и изменения code/tests в
рабочем дереве. Commit, push, PR, merge и deploy требуют отдельных разрешений по
действующему repository process. Production activation в 01C не входит.

## 2. Место в последовательности

```text
01A Storage accepted
    +
01B Client Collector accepted
    ↓
01C AP dynamic/config + technical rates + complete runtime integration
    ↓
separate production deploy/activation TASK
```

## 3. Цель

Завершить code foundation:

- bounded AP inventory pagination;
- bounded/stale-safe AP inventory cache;
- best-effort dynamic AP observations;
- section-specific timestamps и deterministic technical rates;
- complete-only change-deduplicated safe AP config snapshots;
- AP/client/cleanup unified fail-open runtime integration using the same shared `OmadaProvider`;
- lifecycle/start/stop/telemetry/security/regression tests.

01C не включает production включение feature.

## 4. Baseline

Exact baseline 01C:

```text
origin/main@578c7c83d687e04c620256c2a90f22410f801803
PR #39 / 01A merged
PR #40 / 01B merged
```

На момент подготовки ТЗ `main` идентичен этому SHA. Reference-result принятого
после-01B Linux gate: `1059 passed, 2 failed`; оба failure были идентичны
pre-01B baseline и не относились к Observations. Это reference, а не замена
обязательного свежего pre-change gate.

До changes выполнить и сохранить:

```bash
git fetch origin
test "$(git rev-parse origin/main)" = \
  "578c7c83d687e04c620256c2a90f22410f801803"
git switch -c feature/ap-observation-v1 \
  578c7c83d687e04c620256c2a90f22410f801803
git status --short
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
```

Если ветка уже существует, не пересоздавать и не сбрасывать её: сначала сообщить
owner/Tech Lead её SHA и status. Если `origin/main` уже не равен указанному SHA,
не использовать старый baseline автоматически — stop и Tech Lead review.

Drift в `app/observations`, `app/controllers`, `run.py`, shared provider,
Snapshot/Auth/Cleaner → stop condition и Tech Lead review. Фактический
pre-change gate зафиксировать полностью, включая passed/skipped/failed и точные
причины любого отличия от reference-result.

## 5. Неподвижные инварианты

- schema/repository/query 01A меняются только при доказанном blocking defect и отдельном review;
- Client Collector 01B contract не расширяется скрыто;
- `AuthorizedClientSnapshotCollector` полностью неизменен;
- один shared `OmadaProvider`, созданный `run.py`;
- no second OAuth client/token manager/cache/provider singleton;
- AP polling sequential by default; bounded parallelism вне v1;
- failures fail-open и не влияют на visitor flow;
- no raw controller dumps/secrets/passwords;
- acquisition facts only, no Analytics/Visit Lifecycle;
- feature defaults disabled, production untouched.

## 6. Scope

### Входит

- AP settings;
- AP provider methods on existing provider;
- `/devices` bounded pagination/filter/duplicates;
- per-Site inventory cache with hard staleness;
- dynamic/config deadlines and request budgets;
- rotating AP cursor fairness;
- AP normalizer and dynamic section persistence;
- derived wired/LAN/radio rates;
- safe recursive config normalizers and complete-only snapshots;
- integrated Observation runtime factory/states/start/stop;
- `run.py` wiring with shared provider and cleanup/client/AP workers;
- operational telemetry;
- targeted/security/regression/full tests.

### Не входит

- production environment values/restart/live polling;
- AP/controller reconfiguration or remote adoption;
- Grafana/Loki/Alloy/systemd/Nginx;
- HTTP Admin/query API/UI;
- Visit Lifecycle/Analytics/business flags;
- backup infrastructure;
- KB documentation update;
- new dependency/backend/schema redesign.

## 7. Разрешённые файлы

### New/modify

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

### Запрещено

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
docs/**
production config/systemd/Grafana/Alloy/Loki
```

Другой runtime file → stop/request scope expansion.

## 8. Configuration

Итоговый contract с учётом принятого 01A capacity decision. Master defaults, если gate их не изменил:

```text
OBSERVATION_FOUNDATION_ENABLED=false
OBSERVATION_CLIENT_ENABLED=true
OBSERVATION_AP_ENABLED=true

OBSERVATION_SITE_IDS=
OBSERVATION_CLIENT_SSIDS=
OBSERVATION_DB_PATH=/opt/CaptivePortal/data/observations.sqlite3

OBSERVATION_CLIENT_INITIAL_DELAY_SECONDS=15
OBSERVATION_CLIENT_INTERVAL_SECONDS=60
OBSERVATION_CLIENT_PAGE_SIZE=500
OBSERVATION_CLIENT_MAX_PAGES=20
OBSERVATION_CLIENT_MAX_ROWS=10000

OBSERVATION_AP_INITIAL_DELAY_SECONDS=10
OBSERVATION_AP_INTERVAL_SECONDS=30
OBSERVATION_AP_INVENTORY_INTERVAL_SECONDS=300
OBSERVATION_AP_INVENTORY_MAX_STALE_SECONDS=900
OBSERVATION_AP_CONFIG_INTERVAL_SECONDS=21600

OBSERVATION_REQUEST_TIMEOUT_SECONDS=5
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

Feature semantics:

- master false → no repository creation required, zero Observation Omada calls, zero workers;
- master true → valid Site IDs and at least one client/AP subflag true;
- `OBSERVATION_SITE_IDS` обязателен, если включён хотя бы один из
  `OBSERVATION_CLIENT_ENABLED` / `OBSERVATION_AP_ENABLED`;
- `OBSERVATION_CLIENT_SSIDS` применяется только к Client Collector и остаётся
  optional; AP Collector не фильтруется по SSID;
- invalid enabled config → Observation runtime unavailable, CaptivPortal starts;
- `.env.example` должен получить полный итоговый Observation contract, но без
  production Site/SSID/secrets и с master `false`;
- intervals are fixed delay after previous cycle completion.

## 9. Shared provider methods

Extend existing 01B `app/controllers/omada_observations.py`; do not create another installer/provider.

Exact public method names для 01C (namespace продолжает принятый
`list_observation_clients` из 01B):

```python
list_observation_access_points(...)
get_observation_ap_overview(...)
get_observation_ap_wired_uplink(...)
get_observation_ap_lan_traffic(...)
get_observation_ap_radios(...)
get_observation_ap_general_config(...)
get_observation_ap_ip_setting(...)
get_observation_ap_radio_config(...)
get_observation_ap_ofdma(...)
get_observation_ap_available_channels(...)
get_observation_ap_safe_overrides(...)
get_observation_ap_rf_scan_state(...)
```

Each method:

- accepts `site_id`, bounded `timeout_seconds`;
- AP endpoint accepts canonical AP MAC;
- uses existing request/token lifecycle and `Result`;
- defensive copies;
- no token/header/cookie/raw secret body;
- exact `-44112` guarded single refresh/retry as 01B;
- other failure belongs to current cycle, no common retry loop.

## 10. Confirmed endpoints

Inventory:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/devices
```

Choose only `type == "ap"`. Do not use unavailable Controller 5.14.31 endpoint `GET /devices/{deviceMac}`.

Dynamic:

```text
GET /aps/{apMac}
GET /aps/{apMac}/wired-uplink
GET /aps/{apMac}/lan-traffic-info
GET /aps/{apMac}/radios
```

Slow-changing:

```text
GET /aps/{apMac}/general-config
GET /aps/{apMac}/ip-setting
GET /aps/{apMac}/radio-config
GET /aps/{apMac}/ofdma
GET /aps/{apMac}/available-channel
GET /openapi/v2/.../aps/{apMac}/override
GET /openapi/v2/.../aps/{apMac}/rf-scan-result
```

`/power-saving` regularly polling forbidden: confirmed success without useful result on EAP613 research.

## 11. AP inventory pagination

Defaults:

```text
pageSize=100
maxPages=10
maxRows=500
```

Complete only if `totalRows`/actual end consistent. Partial/failed on page/result/data/totalRows error, limits before completion, shutdown or deadline.

Duplicate canonical AP MAC:

- all rows of that MAC excluded from polling for this inventory;
- no arbitrary winner;
- `duplicate_ap_mac_count` and data-quality warning;
- other valid APs continue.

Inventory refresh is part of relevant AP cycle request/deadline budget.

## 12. Inventory cache and staleness

AP worker holds last successful **complete** inventory per Site in memory.

```text
refresh interval 300 sec
max stale 900 sec
```

On refresh failure:

- use cache only while age `<= max stale`;
- record cache age/reason;
- older cache → no AP request from it;
- dynamic/config cycle partial/failed reason `inventory_stale_expired`;
- after process restart cache empty and initial inventory mandatory.

Partial inventory never replaces last complete cache.

## 13. Bounded cycles and fairness

Dynamic boundaries:

```text
deadline 120 sec monotonic
request budget 200
request timeout 5 sec
fixed delay after completion 30 sec
```

Config boundaries:

```text
deadline 180 sec monotonic
request budget 200
fixed delay after completion 21600 sec
```

Deadline и request budget применяются к одному Site-aware storage cycle
(`ap_dynamic` или `ap_config`). Sites обрабатываются последовательно; никакой
скрытой параллельной fan-out между Site нет.

Before each request check shutdown, remaining deadline, remaining budget. After exhaustion:

- no new requests;
- valid completed sections persist;
- cycle partial;
- remaining AP count and reason telemetry;
- already-started request finishes within timeout.

AP order canonical and rotating in-memory cursor per Site after truncation, so first APs do not permanently starve later APs. Sequential requests by default; no thread per AP.

Rate-gap relation для одного Site при полном bounded dynamic cycle:

```text
worst bounded dynamic cycle 120 sec
+ fixed delay 30 sec
≤ rate max gap 180 sec
```

`OBSERVATION_RATE_MAX_GAP_SECONDS` — validation ceiling, а не обещание cadence.
Несколько Site, section failures, inventory refresh, shutdown или stale gap могут
дать `gap_too_large`; никогда не растягивать rate validity, чтобы скрыть это.

## 14. Dynamic AP observation

Best-effort independent sections:

```text
overview
wired_uplink
lan_traffic
radios
```

Successful sections persist even if another fails. AP row flags/partial and cycle result reflect section quality.

### Section timestamps

Persist source counter acquisition time separately:

```text
overview_observed_at
wired_observed_at
lan_observed_at
radio_observed_at per radio row
```

General `ap_observations.observed_at` is row formation time and must not calculate section rates.
Source timestamp фиксировать сразу после успешного получения и строгой проверки
соответствующего endpoint response. Не использовать cycle start, общий row time
или timestamp другой section. Failed/malformed section не получает фиктивный
timestamp.

### Overview fields

```text
site_id, ap_mac, name, ip, model, firmware_version,
wlan_id, cpu_util, mem_util, uptime_seconds
```

### Wired

```text
wired_rate_raw
wired_duplex_code
wired_up_bytes
wired_down_bytes
wired_up_packets
wired_down_packets
wired_activity_raw
```

No guessed duplex label. Activity unit not confirmed and not named Mbps.

### LAN

```text
lan_rx_bytes, lan_tx_bytes,
lan_rx_packets, lan_tx_packets,
lan_rx_drop_packets, lan_tx_drop_packets,
lan_rx_error_packets, lan_tx_error_packets
```

LAN and Wired are distinct counter sources.

### Radio rows

```text
site_id, ap_mac, radio_observed_at, band, radio_id,
actual_channel_raw, actual_channel, frequency_mhz, channel_width,
max_tx_rate, tx_power, wireless_mode,
tx_util, rx_util, interference_util, busy_util,
rx_bytes, tx_bytes, rx_packets, tx_packets,
rx_drop_packets, tx_drop_packets,
rx_error_packets, tx_error_packets,
rx_retry_packets, tx_retry_packets
```

`max_tx_rate` is PHY characteristic. `busy_util` is airtime utilization. Neither is current Mbps throughput.

## 15. Derived technical rates

Raw cumulative counters always persist when valid.

Wired:

```text
wired_download_mbps = ΔdownBytes * 8 / ΔT / 1_000_000
wired_upload_mbps   = ΔupBytes   * 8 / ΔT / 1_000_000
```

LAN:

```text
lan_rx_mbps
lan_tx_mbps
```

Radio aggregate interface traffic:

```text
radio_tx_mbps
radio_rx_mbps
```

Names `client_download_mbps/client_upload_mbps` forbidden for `/radios` data. These rates are aggregate AP radio-interface facts, not per-client traffic/WAN speed.

Rate uses previous stored observation of exact identity:

- wired: same `site_id+ap_mac`, wired timestamps;
- LAN: same `site_id+ap_mac`, LAN timestamps;
- radio: same `site_id+ap_mac+band`, radio timestamps.

В schema v1 `band` является persistence/rate identity; `radio_id` — только
дополнительный факт и не заменяет `band`. Если один response содержит несколько
валидных rows с одинаковым canonical `band`, все rows этого band исключить,
увеличить data-quality warning и сделать AP/cycle partial; произвольный winner
запрещён. Если endpoint невозможно безопасно привести к уникальному canonical
band без schema change — stop condition, скрытую миграцию не делать.

Independent per direction reasons:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Validity:

- previous source sample exists;
- new counter >= old counter for that direction;
- elapsed > 0;
- elapsed <= accepted `OBSERVATION_RATE_MAX_GAP_SECONDS` (default 180).

Decrease → only that direction rate NULL/reason reset. Wired reset does not null LAN/radio; one radio band does not affect another. Long gap → rate NULL/reason gap; new raw value becomes next baseline. No long-gap average.

## 16. Slow-changing AP config

Each AP config snapshot is created only when every mandatory configured section succeeds and safely normalizes:

```text
general-config
ip-setting
radio-config
ofdma
available-channel
safe override v2
rf-scan-result v2
```

Any failed/malformed/unsafe section:

- no config row for that AP;
- no hash;
- latest complete config unchanged;
- AP+section reason summary telemetry, no raw payload;
- overall cycle may be partial.

For complete normalized snapshot:

- canonical strict JSON;
- SHA-256;
- write first snapshot or changed hash only;
- unchanged hash → no new row and telemetry unchanged;
- repository uniqueness from 01A remains authoritative.

## 17. Recursive safe allowlists

Every nested object/array uses path-based child key/type allowlist:

```text
unknown nested key → DROP
unconfirmed nested schema → OMIT field/section, never raw pass-through
```

Apply to IP/radio configs, OFDMA, available channels, override and RF scan.

Minimum safe semantics:

- general: `name`, confirmed `led_setting_code`, `tag_ids`, `location` only; nested list/object filtered;
- IP: confirmed mode/address/mask/gateway/DNS/fallback scalar paths only;
- radio config: confirmed enabled/channel/width/TX power/level/mode/ranges paths;
- OFDMA: confirmed support/enabled flags per band;
- available channels: explicit item paths for confirmed band/channel/frequency/width/capability fields;
- RF scan: `time,status,status2g,status5g,status5g2,status6g`; unknown enum code raw;
- unknown/malformed required config section makes AP snapshot incomplete.

## 18. `/override` security boundary

Only v2 safe provider method `get_observation_ap_safe_overrides()`.

Allowed item fields:

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

`ssidPassword` must be stripped inside provider before returning caller data, not merely redacted later.

Raw override response forbidden in Result, logs, exception, telemetry and SQLite.

## 19. Runtime integration

Public factory contract:

```text
create_observation_foundation(settings, provider, telemetry)
```

Created only in `run.py` and receives the already-created shared provider object.
Factory всегда возвращает lifecycle object (`disabled`, working или
`unavailable`), а не бросает Observation exception наружу в portal startup.

В текущем `run.py` wiring выполняется после создания shared `controller` и Flask
`app`, чтобы передать тот же provider и `app.extensions.get("auth_telemetry")`.
Новый global lifecycle reference допустим только в `run.py`. Создание объекта не
должно запускать threads; workers стартуют явным `start()` после успешной
initialize/validate/recovery последовательности.

Workers:

```text
ClientObservationWorker   # from 01B
APObservationWorker
ObservationCleanupWorker # from 01A
```

Runtime states:

```text
disabled
starting
active
degraded
unavailable
stopping
```

Rules:

- no thread at import;
- fixed-delay, no overlap, interruptible waits;
- idempotent start/stop;
- repository initialize/validate and running→abandoned recovery before workers;
- transient cycle/source/busy → degraded, later success may return active;
- fatal config/schema/corruption → unavailable until restart/operator action;
- unavailable Observation does not abort CaptivPortal startup.

Recommended existing lifecycle order:

```text
Pending Cleaner stop
→ Observation Foundation stop
→ Public Traffic stop
→ Auth executor drain
→ Snapshot Collector drain
→ Visitor Registry stop
```

Observation stop:

- no new cycles/requests;
- interrupt waits;
- bounded active HTTP;
- finish/rollback short DB transaction;
- overall timeout default 20 sec;
- timeout/exception одного Observation worker логируется и не останавливает
  shutdown остальных компонентов;
- existing Snapshot shutdown contract unchanged.

## 20. Fail-open

Observation provider/normalization/storage/cleanup/query failure must not:

- stop portal;
- alter AuthSession/AuthWorker or authorization retry/result;
- alter CAPPORT;
- trigger reconnect;
- change Cleaner/Snapshot/Registry;
- surface in visitor browser.

Master disabled must cause zero Observation Omada calls and no required DB creation.

## 21. Operational telemetry

Use existing telemetry/logger; detailed observations remain authoritative in SQLite.

Semantic events minimum:

```text
observation.runtime_started
observation.runtime_stopped
observation.runtime_unavailable
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

Summary fields may include Site/cycle/component/state/duration/completeness/counts/failure category/http/error code. `ap_rate_reset` includes `source=wired|lan|radio`, direction and band where applicable.

No detailed RSSI/traffic/config/raw response or secrets in telemetry.

## 22. Security markers

Tests use:

```text
TEST_ACCESS_TOKEN_SHOULD_NOT_LEAK
TEST_CLIENT_SECRET_SHOULD_NOT_LEAK
TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK
```

Verify absent from Result, exception, SQLite, telemetry, stdout/stderr and config snapshots. No grep production environment.

## 23. Tests

### Provider/inventory/bounds

- `/devices` pagination complete/partial/max pages/max rows;
- AP type filter and duplicate MAC;
- malformed response/totalRows/JSON, HTTP/errorCode;
- exact `-44112` single retry;
- every dynamic/slow endpoint;
- cache fresh/stale-within-limit/stale-expired/restart empty;
- deadline/request budget stop new requests;
- rotating cursor avoids starvation;
- defensive copies/no secrets/no real Controller call.

### Normalizer/rates/config

- overview/wired/LAN/radio full/minimal/types;
- unknown enums/raw channel fallback;
- section-specific timestamps;
- first rate/no baseline, positive delta;
- independent wired/LAN/radio/direction/band reset;
- invalid elapsed/gap too large;
- aggregate radio rate names/meaning;
- partial section persistence;
- partial config no row/hash/latest;
- complete canonical hash stable;
- unchanged dedup/changed stored;
- recursive unknown nested drop;
- override password stripped before Result.

### Lifecycle/integration

- disabled zero calls/DB optional;
- invalid config unavailable but portal construction succeeds;
- same provider object identity passed;
- no provider construction inside observations;
- startup recovery before workers;
- client/AP/cleanup enable combinations;
- fixed-delay/no overlap;
- start/stop idempotent/bounded;
- no request after stopping;
- provider/storage failure fail-open;
- no thread per AP;
- shutdown ordering regression.

Preferred targeted:

```bash
python -m pytest -q \
  tests/observations/test_ap*.py \
  tests/observations/test_runtime*.py \
  tests/test_omada_observations.py --tb=short
```

## 24. Regression/full gate

Repeat current accepted Snapshot/Cleaner/shared-provider/Auth/CAPPORT regressions. At minimum:

```bash
python -m pytest -q tests/observations/test_client_*.py --tb=short
python -m pytest -q tests/visitor_registry/test_snapshot_*.py --tb=short
python -m pytest -q tests/pending_sessions --tb=short
python -m pytest -q tests/test_omada_client_lookup.py --tb=short
python -m pytest -q \
  tests/test_auth_retry.py \
  tests/test_auth_retry_frontend.py \
  tests/test_capport_*.py --tb=short
python -m pytest -q \
  tests/visitor_registry/test_snapshot_runtime.py \
  tests/test_public_traffic.py --tb=short
```

Full gate:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
git status --short
```

Сравнить с exact pre-change 01C baseline. Gates 01A/01B не заменяют current gate.

## 25. Acceptance 01C

1. exact baseline
   `578c7c83d687e04c620256c2a90f22410f801803` confirmed before changes;
2. capacity cadence/retention decision preserved;
3. shared provider/token lifecycle preserved;
4. AP inventory pagination/duplicates bounded;
5. complete inventory cache only, hard max stale;
6. dynamic/config deadline and request budgets;
7. rotating cursor fairness;
8. dynamic sections partial semantics;
9. exact section timestamps for rates;
10. wired/LAN/radio rates correctly named/calculated;
11. rate reasons independent per source/direction/band;
12. config complete-only/change-only;
13. recursive allowlists and safe override boundary;
14. runtime factory/state/start/stop fail-open;
15. master disabled = zero Observation calls;
16. same shared provider identity;
17. Snapshot/Auth/CAPPORT/Cleaner/Registry contracts unchanged;
18. no analytics/Grafana/external dependency;
19. security markers absent;
20. targeted/regression/full gates reviewed;
21. production environment/service/controller unchanged.

## 26. Stop conditions

- 01A/01B not accepted or baseline drift;
- capacity decision missing/contradicted;
- endpoint/field cannot be confirmed;
- bounded pagination/deadline impossible without unreviewed concurrency;
- canonical `band` identity conflicts with schema uniqueness;
- safe override impossible without raw secret exposure;
- structured section cannot be safely allowlisted — omit/mark incomplete, never raw;
- need Snapshot/Auth/CAPPORT/Cleaner/Visitor Registry changes;
- need external dependency/backend/schema redesign;
- full-suite new failure cannot be classified;
- production credentials/live calls/deploy required.

## 27. Repository actions

Рекомендуемая ветка: `feature/ap-observation-v1`, только от exact baseline
`578c7c83d687e04c620256c2a90f22410f801803`.

После green tests вернуть review handoff и оставить рабочее дерево без commit.
Commit, push, PR, merge и deploy — каждое только по отдельному owner разрешению.
Никаких force push/rebase принятого baseline. Production activation запрещена.

## 28. Handoff

```text
IMPLEMENTED / NOT IMPLEMENTED
BASELINE: 578c7c83d687e04c620256c2a90f22410f801803, branch, drift
FILES INSPECTED / CHANGED
CONFIG / CAPACITY DECISION USED
AP PROVIDER ENDPOINTS / ERROR HANDLING
INVENTORY PAGINATION / CACHE / FAIRNESS
DYNAMIC SECTIONS / TIMESTAMPS
RATES / RESET REASONS
CONFIG COMPLETE-ONLY / HASH / ALLOWLISTS / OVERRIDE
RUNTIME / SHUTDOWN / FAIL-OPEN
SECURITY MARKERS
TESTS / REGRESSIONS / FULL GATE
KNOWN RISKS / UNVERIFIED
REPOSITORY ACTIONS
NEXT OWNER ACTION
```

Mandatory statements:

```text
Snapshot contract changed: NO
Visitor Registry schema changed: NO
Auth/CAPPORT contract changed: NO
shared OmadaProvider preserved: YES
new token manager: NO
production activation completed: NO
```

## 29. После acceptance 01C

Отдельное production activation TASK должно определить:

- deploy exact merged SHA;
- DB parent/mode/ownership;
- approved Site IDs/cadence/retention;
- controlled restart and rollback;
- first client/AP/config/cleanup cycle verification;
- resource/DB growth observation;
- затем отдельную KB update.

Coder 01C не выполняет эти действия.
