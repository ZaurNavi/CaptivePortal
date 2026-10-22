# TASK-OBSERVATION-01B — Client Observation Collector v1

**Проект:** CaptivPortal
**Родительский документ:** `TASK-OBSERVATION-FOUNDATION-01 — REV2`
**Тип:** самостоятельное execution-ТЗ / PR B
**Статус:** BLOCKED BY TASK 01A
**Старт:** только после merge/acceptance 01A и команды owner: `TASK 01B утверждено, начинать PR B`
**Следующий этап:** TASK 01C запрещено начинать до merge и приёмки 01B

## 1. Результат

Добавить periodic Client Observation Collector, который через существующий shared `OmadaProvider` получает bounded inventory авторизованных wireless clients, безопасно нормализует и пишет rows/cycle metadata в принятую schema PR A.

## 2. Baseline и prerequisites

Baseline — фактический merged `origin/main`, содержащий принятую 01A. Зафиксировать exact SHA. Убедиться, что capacity gate, retention/cadence и schema 01A приняты.

До изменений выполнить full Linux gate и сохранить passed/skipped/failed, compileall, diff-check. Если 01A не принята либо schema/query contracts расходятся с TASK — stop.

## 3. Жёсткие границы

Не менять AuthorizedClientSnapshotCollector, request/model/schema/log/retry; Visitor Registry; Auth/CAPPORT; Cleaner; AP collector; Visit Lifecycle/Analytics; Grafana/Alloy/systemd/production env.

Snapshot failure не подавляет будущие observations. Observation failure не влияет на авторизацию/portal/browser.

Использовать тот же provider object из `run.py`; не создавать provider/token cache/client внутри observations.

## 4. Configuration

Через existing config pipeline:

```text
OBSERVATION_FOUNDATION_ENABLED=false
OBSERVATION_CLIENT_ENABLED=true
OBSERVATION_SITE_IDS=
OBSERVATION_CLIENT_SSIDS=
OBSERVATION_CLIENT_INITIAL_DELAY_SECONDS=15
OBSERVATION_CLIENT_INTERVAL_SECONDS=60
OBSERVATION_REQUEST_TIMEOUT_SECONDS=5
OBSERVATION_CLIENT_PAGE_SIZE=500
OBSERVATION_CLIENT_MAX_PAGES=20
OBSERVATION_CLIENT_MAX_ROWS=10000
```

Site IDs required при enabled, CSV trim/dedupe preserving order, empty element invalid. SSID allowlist optional, exact case-sensitive; empty = all SSIDs configured Sites. Fixed delay считается после завершения cycle.

## 5. Provider и bounded pagination

Использовать подтверждённый clients endpoint через shared provider. Pagination sequential и bounded: pageSize 500, max 20 pages, max 10000 rows; без concurrent GET и без N+1 detail calls.

Cycle complete только при согласованном inventory. Page failure, malformed/inconsistent totalRows, ранний limit или shutdown → partial/failed. Валидные rows partial inventory можно сохранить только с `source_inventory_complete=false`, cycle `complete=false`.

HTTP 200 не равен success: нужен success envelope. Для `errorCode=-44112` invalidate только использованный token, один fresh shared token и максимум один guarded retry. Остальные transient failures завершает текущий cycle; unknown errorCode не получает выдуманный retry/label.

## 6. Eligibility и duplicates

Detailed row сохраняется только при:

```text
valid canonical MAC
wireless is True
active is True
authStatus == 2
SSID проходит optional allowlist
```

`authStatus==1` и unknown status detailed row не создают. Duplicate canonical MAC в одном cycle: не выбирать произвольно, rows этого MAC не сохранять, увеличить duplicate count.

## 7. Independent normalizer

Создать Observation normalizer; snapshot normalizer не менять.

Safe allowlist включает identity/context, radio/session и traffic fields из master REV2: MAC/controller id/name/hostname/system/device type/IP/IPv6/SSID/AP; connect/signal/wifi/radio/band/channel/rates/RSSI/SNR/VID/uptime/last seen/auth/activity/flags; cumulative traffic and packet counters.

Type rules:

- bool не int; exact int; finite float only;
- invalid optional → NULL, required identity invalid → skip;
- numeric string не coercion;
- MAC uppercase colon canonical, IP canonical;
- unknown enum хранить raw code без invented label;
- radio_id 0→2.4GHz, 1→5GHz, other band NULL, raw id сохранять.

Structured sources `ipSetting`, `rateLimit`, `clientLockToApSetting`, `multiLink` разрешены только при explicit path-based recursive allowlist подтверждённых child keys/types. Unknown nested key → DROP. Неподтверждённый object целиком OMIT. Raw controller row не хранить.

Никогда не сохранять/логировать tokens, Client Secret, Authorization/cookies, credentials/password, dot1x identity, raw secret-bearing fields.

## 8. Worker/cycle behavior

Один fixed-delay worker, no overlap, interruptible wait, no per-client threads/unbounded queue. Для каждого Site создать provisional `client` cycle `running` до polling, завершить `completed` с success/partial/failed/shutdown и counters.

Writes — bounded short batches через repository 01A, network вне transaction. Runtime disabled = zero Omada calls. Storage/provider failure → degraded, следующий successful cycle может вернуть active.

Operational telemetry только summary; detailed RSSI/traffic payload туда не отправлять.

## 9. Tests и acceptance

Targeted: config; provider pagination/envelopes/token retry; malformed/HTTP/network; full/minimal normalization; invalid MAC/IP/types/NaN; eligibility/SSID; duplicate MAC; partial inventory flag; structured unknown nested drop; shutdown/no overlap; storage/provider fail-open; shared provider identity; security markers.

Regression минимум:

```bash
python -m pytest -q tests/visitor_registry/test_snapshot_*.py --tb=short
python -m pytest -q tests/pending_sessions --tb=short
python -m pytest -q tests/test_omada_client_lookup.py --tb=short
```

Плюс current CAPPORT/shared-provider tests и full Linux gate (`pytest -q -rs`, compileall, diff-check).

Acceptance:

- schema 01A не ломается и не расширяется без review;
- Snapshot runtime/schema changes = 0;
- AP collector отсутствует;
- Site-aware/idempotent rows и cycle quality корректны;
- secrets absent from Results/exceptions/SQLite/telemetry/stdout;
- production остаётся disabled и не меняется;
- новых failures относительно baseline нет либо классификация доказана.

## 10. Repository actions и handoff

Рекомендуемая ветка: `feature/client-observation-v1`, только от принятого merged 01A. Commit после green tests; push/PR/merge — только по отдельному owner разрешению.

Handoff: baseline, changed files, provider identity, eligibility/pagination/partial semantics, fields/allowlists, cycle behavior, exact tests/results, security verdict, risks и repository actions.
