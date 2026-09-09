# CaptivPortal knowledge base

Status: current
Updated: 2026-09-09
Current-state implementation baseline: `main@7df71a8e807efd74b123117e78cb8d992c190fa1`
Current implementation tree: `8f1342f0a0f1e8242642161e02b2f3276e6ddf51`

Эта страница — навигация. Она не дублирует архитектуру.

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

Current Traffic state at implementation baseline `main@e32ade378bdbfc9f8458db9c18221958f4552718`:

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

Current implementation / production baseline:

```text
main = 7df71a8e807efd74b123117e78cb8d992c190fa1
tree = 8f1342f0a0f1e8242642161e02b2f3276e6ddf51
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
TASK-WEB-DEVICE-UI-01 = IN PROGRESS / LAB REVIEW PENDING
MERGED = NO
DEPLOYED = NO
CURRENT PRODUCTION BEHAVIOR = NO
```

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
