# CaptivPortal knowledge base

Status: current
Updated: 2026-09-06
Current-state implementation baseline: `main@6fbc3736085be9d0538d893b6e9569ff490ef7f4`
Current implementation tree: `fc3c1ed53df32d0074036a749ee028781ec1f1b5`

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
| Current DB baseline prerequisite | `tasks/TASK-DB-BASELINE-SYNC-01.md` |
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

Current Traffic state at implementation baseline `main@6fbc3736085be9d0538d893b6e9569ff490ef7f4`:

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
```

Owner-confirmed production Traffic flags now also include:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
```

Repository default remains `WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false`.

Historical Traffic panels retain independent page-local `24h | 7d` ranges.
Online Guests Traffic is Current State-backed, near-current and range-insensitive.

Current operational prerequisite:

```text
TASK-DB-BASELINE-SYNC-01
APPROVED / READY FOR EXECUTION / NOT YET ACCEPTED
```

After `FINAL_DB_BASELINE=PASS`, the next planned product stage is **Traffic 0.8**.
This does not yet create a detailed Traffic 0.8 implementation/API contract.

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
