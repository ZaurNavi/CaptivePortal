# CaptivPortal knowledge base

Status: current
Updated: 2026-08-26
Current-state baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`

Эта страница — навигация. Она не дублирует архитектуру.

## Модели истины

**Current-state truth:** current code → current tests → current docs.

**Change-intent truth:** approved FINAL TASK → PLAN → ADR.

Historical reports, production acceptance и research сохраняют доказательную ценность, но не заменяют current code при описании того, как система работает сейчас.

## Рекомендуемый порядок чтения

1. `../AGENTS.md`
2. `project-inventory.md`
3. `architecture.md`
4. `module-index.md`
5. `configuration.md`
6. соответствующий `modules/*.md`
7. `testing.md`, `security.md`, `deployment.md` по задаче

## Карта знаний

| Нужно понять | Источник |
|---|---|
| Exact current snapshot | `project-inventory.md` |
| Dependency/lifecycle architecture | `architecture.md` |
| Module status and routing | `module-index.md` |
| Configuration groups/defaults | `configuration.md` |
| Omada OpenAPI evidence | `api/omada-open-api.md` |
| Testing responsibility/gates | `testing.md` |
| Logging/journals | `logging.md` |
| Security boundaries | `security.md` |
| Deployment/activation | `deployment.md` |
| Agent workflow | `agents/workflow.md` |
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

## Current vs planned

Home Live, Home Traffic и Home Activity находятся в current `main@53f617b3ac0155d0d647e58e98309927f9a4d318`.

`TASK-HOME-ACTIVITY-01` имеет состояние: Implemented → Merged → Central Lab PASS → Production deployed → Core production acceptance PASS.

Текущий incident/postmortem: `postmortems/TASK-HOME-ACTIVITY-01-2026-08-26.md`.

## Контекстная экономия

Подробный факт хранится в одном нормативном документе и связывается ссылкой. Не копируйте целые TASK/research reports в current architecture. Не передавайте агенту весь repository KB, если TASK требует 1–3 связанных contracts.
