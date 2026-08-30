# CaptivPortal knowledge base

Status: current
Updated: 2026-08-31
Current-state baseline: `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`

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
7. `testing.md`, `security.md`, `deployment.md` по задаче

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

Current Traffic sequence at `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`:

```text
TRAFFIC-00         DONE
TRAFFIC-01         DONE
TRAFFIC-02-READ    DONE
TRAFFIC-02         DONE
TRAFFIC-02-PERF-01 DONE
TRAFFIC-03         DONE / PRODUCTION ACTIVE
TRAFFIC-04         CLOSED / PRODUCTION PASS / ACTIVE
TRAFFIC-05         NEXT / NOT IMPLEMENTED
```

Owner-confirmed production Traffic flags:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
```

`modules/traffic.md` is the current Traffic product/semantic contract.
Historical FINAL TASKs and superseded/amended acceptance evidence remain
traceability evidence and do not replace current implementation state.

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
