# CaptivPortal knowledge base

Status: current
Updated: 2026-09-06
Current-state implementation baseline: `main@df91355a99d2561abc9c4d6d4bb6f5a968d327b3`
Current implementation tree: `1161739c6b4fe90fa08928556746a5a4ea6af4cd`

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

Current Traffic state at implementation baseline `main@df91355a99d2561abc9c4d6d4bb6f5a968d327b3`:

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
```

Owner-confirmed production Traffic flags now also include:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

Repository default remains `WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false`.

Historical Traffic panels retain independent page-local `24h | 7d` ranges.
Online Guests Traffic is Current State-backed, near-current and range-insensitive.

Closed prerequisite and current closure:

```text
TASK-DB-BASELINE-SYNC-01 = CLOSED / PASS
FINAL_DB_BASELINE = PASS
TASK-TRAFFIC-08 = CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
```

No next Traffic TASK is currently assigned. A successor becomes canonical only
after separate Owner / Tech Lead approval.

`modules/traffic.md` is the current Traffic product/semantic contract.
Historical FINAL TASKs and acceptance evidence remain traceability evidence and
do not override current implementation state.

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
