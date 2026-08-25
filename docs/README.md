# CaptivPortal knowledge base

Status: current
Updated: 2026-08-25
Current-state baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

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

## Current vs planned

Home Live and Home Traffic находятся в current `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`.

Home Activity не находится в коде этого baseline и не должен описываться как current implementation. Если approved TASK для него передан вне repository, он остаётся change-intent до merge соответствующего runtime change.

## Контекстная экономия

Подробный факт хранится в одном нормативном документе и связывается ссылкой. Не копируйте целые TASK/research reports в current architecture. Не передавайте агенту весь repository KB, если TASK требует 1–3 связанных contracts.
