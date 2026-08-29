# CaptivPortal knowledge base

Status: current
Updated: 2026-08-29
Current-state baseline: `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`

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
- `modules/traffic.md`

## Current vs planned

Home Live, Home Traffic, Home Activity, Traffic Section Foundation and Current Network Throughput are current at `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`.

Production on 2026-08-29 is reported at the same HEAD/tree with both:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
```

The flags remain independent feature boundaries.

Traffic sequence:

```text
TRAFFIC-00      DONE / MERGED / PRODUCTION / ACTIVE
TRAFFIC-01      DONE / MERGED / PRODUCTION / ACTIVE
TRAFFIC-02-READ NEXT / DRAFT REVIEW / IMPLEMENTATION NOT STARTED
TRAFFIC-02+     NOT STARTED
```

`modules/traffic.md` is the current Traffic product/semantic contract. Historical FINAL TASKs retain traceability but do not describe current implementation state.

## Контекстная экономия

Подробный факт хранится в одном нормативном документе и связывается ссылкой. Не копируйте целые TASK/research reports в current architecture. Не передавайте агенту весь repository KB, если TASK требует 1–3 связанных contracts.
