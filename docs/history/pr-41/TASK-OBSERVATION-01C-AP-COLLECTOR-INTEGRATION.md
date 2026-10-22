# TASK-OBSERVATION-01C — AP Observation Collector and Runtime Integration v1

**Проект:** CaptivPortal
**Родительский документ:** `TASK-OBSERVATION-FOUNDATION-01 — REV2`
**Тип:** самостоятельное execution-ТЗ / PR C
**Статус:** BLOCKED BY TASK 01A + 01B
**Старт:** только после merge/acceptance 01A и 01B и команды owner: `TASK 01C утверждено, начинать PR C`
**Production activation:** отдельный будущий TASK

## 1. Результат

Добавить bounded AP inventory/dynamic/config observation, deterministic per-source rates и полную fail-open lifecycle integration Observation Foundation в `run.py`, сохранив shared OmadaProvider и все существующие runtime contracts.

## 2. Baseline и prerequisites

Baseline — фактический merged `origin/main` с принятыми 01A+01B. Зафиксировать SHA и выполнить pre-change full Linux gate. Capacity/cadence/retention direction PR A должна быть принята. Любое расхождение schema/client/shared-provider contracts — stop и review.

## 3. Жёсткие границы

Не менять Snapshot Collector, Visitor Registry, Auth/CAPPORT, Cleaner semantics, client eligibility/storage contracts, Visit Lifecycle/Analytics, HTTP Admin API, Grafana/Alloy/systemd/production env.

Никакого второго provider/token manager, per-AP threads, unbounded concurrency/queue, raw payload journal или live-controller tests.

## 4. Configuration/cadence

Через existing pipeline использовать defaults master REV2:

```text
OBSERVATION_AP_ENABLED=true
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
```

Fixed delay начинается после завершения cycle. Deadline/request budget имеют приоритет. Перед каждым HTTP request проверить shutdown, monotonic deadline и remaining budget.

## 5. AP inventory

`GET .../sites/{siteId}/devices`; sequential bounded pagination, only `type=="ap"`. Complete только при согласованном totalRows/end data. Failure/malformed/limit/shutdown → partial/failed.

Duplicate canonical AP MAC: все rows данного MAC исключить из polling, data-quality warning/count; произвольный выбор запрещён.

Хранить последний successful complete inventory per Site in memory. Refresh 300s, max stale 900s. Failed refresh допускает cache только до max stale; expired cache запрещено опрашивать, cycle partial/failed `inventory_stale_expired`. После restart initial inventory обязателен.

При deadline/budget truncation сохранить valid observations, cycle partial, remaining count; rotating cursor по canonical AP order обеспечивает fairness.

## 6. Dynamic observations

Best-effort independent sections: overview, wired uplink, LAN traffic, radios. Section failure не уничтожает успешные sections; AP row/cycle partial.

Хранить source-specific timestamps `overview_observed_at`, `wired_observed_at`, `lan_observed_at`, `radio_observed_at`. Общий observed_at нельзя использовать для delta отдельных sources.

Нормализовать confirmed overview/wired/LAN/radio fields master REV2. Unknown enum сохранять raw без guessed labels; channel parse failure сохраняет raw; `max_tx_rate` — PHY characteristic, `busy_util` — airtime, wired activity не называть Mbps.

## 7. Derived rates

Всегда сохранять raw cumulative counters. Rates:

```text
wired_download_mbps / wired_upload_mbps
lan_rx_mbps / lan_tx_mbps
radio_rx_mbps / radio_tx_mbps
```

Radio rates — aggregate AP radio-interface traffic, не client traffic/WAN speed.

Delta только по exact same Site+AP+source identity и source timestamp. Valid если counter не уменьшился, elapsed>0 и <=180s.

Per-direction reasons отдельно: `ok|no_baseline|counter_reset|gap_too_large|invalid_elapsed|source_unavailable`. Reset wired не влияет на LAN/radio; reset одного direction/band не влияет на другие. Long-gap average запрещён; новое raw value становится baseline.

## 8. Slow config

Config snapshot конкретной AP создаётся только если все обязательные sections successful, safely normalized и complete:

```text
general-config, ip-setting, radio-config, ofdma,
available-channel, safe override v2, rf-scan-result v2
```

При любой failed/malformed/unsafe section row/hash/latest не создавать. Для complete canonical strict JSON вычислить SHA-256; писать только first/change, unchanged dedup.

Все nested objects/arrays — explicit path-based recursive allowlists; unknown child DROP, неподтверждённое поле OMIT. `/override` только через `get_ap_safe_overrides()` v2; разрешены `ssidId, ssidEntryId, ssidName, band, security, vlanEnable, vlanId, ssidEnable`. `ssidPassword` не возвращать даже redacted. Raw override запрещён в Result/log/exception/telemetry/SQLite.

## 9. Runtime integration

Factory получает `(settings, shared_provider, telemetry)` и создаётся только в `run.py`; threads at import запрещены.

Workers: Client, AP, Cleanup; fixed-delay, no overlap, interruptible and idempotent stop. States: disabled/starting/active/degraded/unavailable/stopping.

Recommended shutdown order:

```text
Pending Cleaner → Observation Foundation → Public Traffic
→ Auth executor drain → Snapshot Collector drain → Visitor Registry
```

При stopping: no new cycles/requests, interrupt waits, bounded active HTTP, finish short DB transaction, overall 20s timeout. Disabled master = zero Omada calls и DB не обязана создаваться.

Любая Observation/provider/storage/config failure не меняет portal/Auth/CAPPORT/Snapshot/Cleaner/Registry и не видна visitor browser.

## 10. Telemetry/security

Summary events для runtime/AP cycles/endpoints/rate reset/config/cleanup/storage. Rate reset event указывает source, direction и band. Не отправлять raw controller payload или detailed observation data.

Security markers обязаны отсутствовать в Result, exception, SQLite, telemetry, stdout/stderr и config snapshots. MAC хранится полностью.

## 11. Tests и acceptance

Targeted: AP pagination/duplicates/type filter; stale cache boundary; deadline/budget; rotating fairness; all endpoints/errors/token retry; normalization; source timestamps; first/positive/reset/gap rates and independence; partial sections; complete-only config/hash/dedup; recursive allowlists; safe override; no per-AP thread; lifecycle/shared-provider identity/start-stop/no request after stopping/fail-open.

Повторить Snapshot/Cleaner/CAPPORT/shared-provider regressions и full Linux gate. No real Controller calls.

Acceptance:

- all AP polling bounded; stale cache hard limit;
- radio rate semantics/names correct; reset reasons independent;
- partial config никогда не становится latest;
- shared provider object identity preserved;
- lifecycle/shutdown fail-open and bounded;
- Snapshot/Registry/Auth/CAPPORT contracts unchanged;
- defaults disabled, production/env/systemd untouched;
- no secrets and no new dependencies;
- targeted/regression/full gates имеют reviewable verdict.

## 12. Repository actions и handoff

Рекомендуемая ветка: `feature/ap-observation-v1`, только от принятого merged 01A+01B. Commit после green tests; push/PR/merge/deploy — только по отдельному owner разрешению.

Handoff: baseline, files/contracts, AP cadence/endpoints/bounds, rate/reset semantics, safe config/override proof, lifecycle/shutdown, exact test results, security verdict, risks, repository actions и отдельный next action для deploy/activation TASK.
