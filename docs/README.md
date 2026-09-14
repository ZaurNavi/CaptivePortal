# CaptivPortal knowledge base

Status: current
Updated: 2026-09-13
Current-state implementation baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`
Current implementation tree: `8312658be3ba272998f46212d9bad76950e3867e`

Эта страница — навигация. Она не дублирует архитектуру.

- [Device Fingerprint Evidence](modules/device-fingerprint.md) — current,
  default disabled passive evidence foundation and isolated auxiliary service.

## Модели истины

**Current-state truth:** current code → current tests → current docs.

**Change-intent truth:** approved FINAL TASK → PLAN → ADR.

Historical reports, production acceptance и research сохраняют доказательную
ценность, но не заменяют current code при описании того, как система работает
сейчас.

## Рекомендуемый порядок чтения

1. `../AGENTS.md`
2. `project-inventory.md`
3. `architecture.md`
4. `module-index.md`
5. `configuration.md`
6. соответствующий `modules/*.md`
7. `testing-environments.md` перед любым Windows/Linux/production gate
8. `testing.md`, `security.md`, `deployment.md` по задаче

## Карта знаний

| Нужно понять | Источник |
|---|---|
| Exact current snapshot | `project-inventory.md` |
| Dependency/lifecycle architecture | `architecture.md` |
| Module status and routing | `module-index.md` |
| Configuration groups/defaults | `configuration.md` |
| Traffic current semantics/roadmap | `modules/traffic.md` |
| Omada OpenAPI evidence | `api/omada-open-api.md` |
| Testing responsibility/gates | `testing.md` |
| Test environment routing / production-not-test-host invariant | `testing-environments.md` |
| Practical command/harness lessons | `operations-command-lessons-learned.md` |
| Completed DB baseline gate | `tasks/TASK-DB-BASELINE-SYNC-01.md` |
| TRAFFIC-08 final production closure | `tasks/TASK-TRAFFIC-08-FINAL.md` |
| TRAFFIC-09 final production closure | `tasks/TASK-TRAFFIC-09-FINAL.md` |
| DEVICE-CARD-01 final production closure | `tasks/TASK-DEVICE-CARD-01-FINAL.md` |
| WEB-ASSET-LIBRARY-01 final production closure | `tasks/TASK-WEB-ASSET-LIBRARY-01-FINAL.md` |
| WEB-ASSET-LIBRARY-01 Android FIX closure | `tasks/TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION-FINAL.md` |
| Home Online Devices presentation closure | `tasks/TASK-WEB-HOME-ONLINE-DEVICE-PRESENTATION-01-FINAL.md` |
| Canonical Device Type foundation closure | `tasks/TASK-DEVICE-TYPE-NORMALIZATION-01-FINAL.md` |
| Device Type + SNR presentation closure | `tasks/TASK-WEB-DEVICE-TYPE-PRESENTATION-01-FINAL.md` |
| Windows compatibility baseline cleanup | `tasks/TASK-TEST-BASELINE-CLEANUP-01-FINAL.md` |
| Web Designer canonical role | `agents/web-designer-role.md` |
| Projection lifecycle P0 closure | `tasks/TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01-IMPLEMENTATION-READY-FINAL-R5.md` |
| Deferred Projection maintenance request | `deferred/TRAFFIC-PROJECTION-MAINTENANCE-REINDEX.md` |
| Acceptance/publication workflow | `agents/workflow.md` |
| Git/production deployment boundary | `deployment.md` |
| Repository actions | `agents/repository-actions.md` |
| Logging/journals | `logging.md` |
| Security boundaries | `security.md` |
| TASK contract | `agents/task-contract.md` |
| Handoff format | `agents/handoff.md` |
| Home Activity postmortem | `postmortems/TASK-HOME-ACTIVITY-01-2026-08-26.md` |
| Historical/superseded material | `archive/` |

## Current module contracts

- `modules/authorization.md`
- `modules/portal-entry.md`
- `modules/capport.md`
- `modules/auth-telemetry.md`
- `modules/public-authorization-counter.md`
- `modules/public-traffic-counter.md`
- `modules/authorized-client-snapshot.md`
- `modules/visitor-registry.md`
- `modules/omada-webhook-receiver.md`
- `modules/omada-webhook-normalizer.md`
- `modules/pending-session-cleaner.md`
- `modules/visit-lifecycle.md`
- `modules/observations.md`
- `modules/current-state.md`
- `modules/analytics.md`
- `modules/admin-web.md`
- `modules/home-activity.md`
- `modules/traffic.md`

## Current vs planned

Current Traffic state at implementation baseline `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`:

```text
TRAFFIC-00         DONE
TRAFFIC-01         DONE / PRODUCTION ACTIVE
TRAFFIC-02-READ    DONE
TRAFFIC-02         DONE / PRODUCTION ACTIVE
TRAFFIC-02-PERF-01 DONE
TRAFFIC-03         DONE / PRODUCTION ACTIVE
TRAFFIC-04         DONE / PRODUCTION ACTIVE
TRAFFIC-05         DONE / PRODUCTION ACTIVE
TRAFFIC-RANGE-01   DONE / PRODUCTION ACTIVE / PRODUCTION ACCEPTANCE PASS
TRAFFIC-06         DONE / PRODUCTION ACTIVE
TRAFFIC-07-READ    DONE / READ FOUNDATION IMPLEMENTED
TRAFFIC-07         COMPLETE / PRODUCTION ACTIVE
TRAFFIC-08         CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
TRAFFIC-09         COMPLETED / PRODUCTION ACTIVE
```

Owner-confirmed production Traffic flags now also include:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Repository default remains `WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false`.

Historical Traffic panels retain independent page-local `24h | 7d` ranges.
Online Guests Traffic is Current State-backed, near-current and range-insensitive.

Closed prerequisite and current closure:

```text
TASK-DB-BASELINE-SYNC-01 = CLOSED / PASS
FINAL_DB_BASELINE = PASS
TASK-TRAFFIC-08 = CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
TASK-TRAFFIC-09 = COMPLETED / PRODUCTION ACTIVE
TASK_TRAFFIC_09_PRODUCTION = ACTIVE
```

No next Traffic TASK is currently assigned. A successor becomes canonical only
after separate Owner / Tech Lead approval.

`modules/traffic.md` is the current Traffic product/semantic contract.
Historical FINAL TASKs and acceptance evidence remain traceability evidence and
do not override current implementation state.

## Current Device Card state

```text
TASK-DEVICE-CARD-01 = COMPLETE
IMPLEMENTATION = PASS
OWNER + TECH LEAD ACCEPTANCE = PASS
MERGE = COMPLETE
PRODUCTION DEPLOY = PASS
PRODUCTION ACTIVATION = PASS
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED = true
```

Current implementation / production checkpoint:

```text
main = 3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
tree = 8312658be3ba272998f46212d9bad76950e3867e
```

Device Detail now exposes a separate read-only `Current Device Context` over
persisted Current State + the accepted exact-client Current Guest Traffic
projection.

Permanent semantic boundary:

```text
Historical Device Context != Current Device Context
stale != offline
unavailable != offline
numeric 0 != missing/unavailable
```

Follow-on UI work:

```text
TASK-WEB-DEVICE-UI-01 = CLOSED / PRODUCTION ACTIVE
PR #110 = MERGED / PRODUCTION VERIFIED
```

## Admin Web local asset library — current production

```text
TASK-WEB-ASSET-LIBRARY-01=CLOSED / PRODUCTION PASS
TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION=CLOSED / PRODUCTION PASS
PR #113=MERGED
PR #114=MERGED / PRODUCTION VERIFIED
current production HEAD=3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
current production tree=8312658be3ba272998f46212d9bad76950e3867e
```

The repository-local Android asset remains:

```text
app/admin_web/static/icons/platforms/android.svg
SHA256=2f2411f1f05522e90049f8cbb06105fb553057efeadf772cdcc3ae24bbc8a6cc
```

The Asset Library tasks remain valid provenance/history for introducing and
fixing that asset. Their former raw browser predicate is historical acceptance
evidence only.

Current machine decision after PR #119/#120:

```javascript
device_type_key === "android"
```

Raw `device_type` remains source/display evidence. Current Admin Web does not
trim/lower/casefold/Unicode-normalize or infer Device Type in the browser.

## Canonical Device Type contract — current production

```text
TASK-DEVICE-TYPE-NORMALIZATION-01=CLOSED / MERGED / DEPLOYED / PRODUCTION ACTIVE
TASK-WEB-DEVICE-TYPE-PRESENTATION-01=CLOSED / MERGED / DEPLOYED / PRODUCTION ACCEPTANCE PASS
PR #119=MERGED
PR #120=MERGED
current production HEAD=3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
current production tree=8312658be3ba272998f46212d9bad76950e3867e
```

Canonical ownership:

```text
raw/source/display value = device_type
machine/presentation key = device_type_key
normalization owner       = app/common/device_type.py
```

`device_type_key` is a bounded lexical key derived with `strip()` + `casefold()`
and strict UTF-8 validation. It does not perform Unicode normalization, semantic
mapping, inference, separator collapsing or truncation.

The browser consumes the server-provided key. It must not derive a Device Type
key from raw `device_type`.

Android presentation is therefore strictly:

```javascript
device_type_key === "android"
```

The earlier browser-owned `trim().toLowerCase()` Android predicate remains
historical evidence of TASK-WEB-ASSET-LIBRARY-01/FIX and is **superseded as a
current contract** by PR #119/#120.

The Android SVG remains repository-local:

```text
app/admin_web/static/icons/platforms/android.svg
SHA256=2f2411f1f05522e90049f8cbb06105fb553057efeadf772cdcc3ae24bbc8a6cc
```


## Home Online Devices — current presentation

The current production Home table presents:

```text
Device / MAC
Type
Auth
IP
AP
Band
RSSI
SNR
Uptime
Traffic
```

The `Type` column is immediately after `Device / MAC`.

Type presentation:

```text
device_type_key == "android" -> Android SVG cue
device_type_key == null AND device_type == null -> NULL
otherwise -> raw device_type
```

No Device Type inference is performed from hostname, system name, MAC, vendor,
SSID, AP, IP or history.

SNR is presentation-only:

```text
>=25      good    #10b956
15..24    warning #f2c20d
<15       danger  #ed3038
null      neutral / —
```

RSSI and SNR are independent. No combined score or backend quality
classification exists.

Home-specific geometry and tones are scoped to:

```css
.live-section[aria-labelledby="devices-now-title"]
```

and do not redefine unrelated `.live-table` surfaces.


## Device Card Device Type — current presentation

Device Card keeps raw and canonical roles separate:

```text
device_type     -> source/display text
device_type_key -> machine/presentation decision
```

The frontend does not trim, lowercase, casefold, Unicode-normalize or infer
Device Type.

A detail object that contains its own `device_type_key` owns that presentation
decision. `Latest Site snapshot` may use `identity.device_type_key` when the
snapshot raw type and identity raw type belong to the same Device record.

`device_type_key` itself is not rendered as a separate user-facing field.

## Home operational read models — current repository contracts

Two implemented Home subsystems were underrepresented in the previous current KB
inventory and are explicitly restored here.

### Home System Health

```text
TASK-HOME-HEALTH-01 implementation=MERGED
PR #74 merge=f458df3b360bba89e9965a1edfdcc0d3af2f201c
repository default WEB_ADMIN_HOME_HEALTH_ENABLED=false
```

Home System Health is a read-only Admin composition over existing bounded
runtime/read evidence. It has no request-time Omada probe, Health DB, repair
worker or log scan. Its top-level product states are `operational`, `degraded`,
`unavailable`, `unknown`; `initializing`/`stale` are reason semantics.

This KB sync does **not** infer the current production value of
`WEB_ADMIN_HOME_HEALTH_ENABLED`; production enabled-state remains host-verified
unless separately evidenced.

### Home AP-24H

```text
TASK-HOME-AP-24H-01 implementation=MERGED
PR #78 merge=042f8e4c5f3c6205cec1823322688e1bf3805a57
PR #79 duration-partition fix=MERGED
PR #80 frontend dataset activation fix=MERGED
TASK-HOME-AP-24H-TELEMETRY-01 / PR #81=MERGED
repository default WEB_ADMIN_HOME_AP_24H_ENABLED=false
repository default WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED=false
```

Home AP-24H is a Site-scoped rolling 24-hour read model over persisted Current
State + Observation evidence: 96 x 15-minute buckets, no query-time Omada and no
new persistence owner. Operational telemetry reuses the existing Authorization
Telemetry sink and is separately feature-gated/fail-open.

Historical PR evidence shows production-acceptance work occurred during AP-24H
fixes, but this KB sync does not invent a current host flag value. Current
production enablement must be asserted only from host/Owner evidence.

## Current Windows full-regression contract

```text
current runner=C:\CaptivPortal-Lab\lab-test-v7-strict.cmd
runner SHA256=45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77
V6 fixed=historical / audit only
former six compatibility exclusions=ordinary strict regressions
compatibility allowlist for former six=EMPTY
WARN escape for former six=REMOVED
```

Canonical closure:
`tasks/TASK-TEST-BASELINE-CLEANUP-01-FINAL.md`.

## Traffic Projection lifecycle P0 closure

Canonical task / incident record:

`tasks/TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01-IMPLEMENTATION-READY-FINAL-R5.md`

Current truth:

```text
FINAL-R5 + FIX-1=accepted
PR #111=merged
production=7472d67274ea5aaea2a20df6b613b78d5bb70f42
tree=3950df6d400049ed16a823032c6740396cd61137
recovery=PASS
Projection health=healthy
Historical Traffic=restored
worker=active + enabled
P0 incident=closed
```

The task record preserves the earlier HOLD/containment state as chronology and
does not treat it as current status.

## Permanent promotion boundary

Canonical workflow remains:

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

## Контекстная экономия

Подробный факт хранится в одном нормативном документе и связывается ссылкой.
Не копируйте целые TASK/research reports в current architecture. Не передавайте
агенту весь repository KB, если TASK требует 1–3 связанных contracts.

## Device Fingerprint sensor

Текущее устройство passive network evidence описано в
`docs/modules/device-fingerprint.md`; deployment boundary — в
`docs/deployment.md`, sensor-only configuration — в `docs/configuration.md`.
