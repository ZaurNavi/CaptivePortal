# Матрица 58 критериев ТЗ

Status values:

- Ready in proposal — файл/правило подготовлено вне repository.
- Pending integration — проверяется после approval и refresh main.
- Pending review — требуется Architect/Tech Lead.
- Blocked baseline — текущий main/environment не проходит gate.

| № | Критерий | Статус | Комментарий |
|---:|---|---|---|
| 1 | AGENTS.md | Ready in proposal | 118 строк |
| 2 | Copilot instructions | Ready in proposal | platform adapter |
| 3 | Path-specific instructions | Ready in proposal | 7 файлов |
| 4 | Проверено применение instructions | Pending integration | activation только в repo |
| 5 | Project inventory | Ready in proposal | main a44b3128 |
| 6 | Architecture | Ready in proposal | со схемами |
| 7 | Module index | Ready in proposal | 11 фактических модулей |
| 8 | Testing | Ready in proposal | commands и baseline |
| 9 | Logging | Ready in proposal | telemetry/journal split |
| 10 | Deployment | Ready in proposal | production unverified noted |
| 11 | Security | Ready in proposal | critical finding redacted |
| 12 | Omada API | Ready in proposal | только confirmed endpoints |
| 13 | Module documents | Ready in proposal | 11 contracts |
| 14 | Agent workflow | Ready in proposal | modes и economy |
| 15 | Task contract | Ready in proposal | scope/permissions |
| 16 | Handoff | Ready in proposal | factual report |
| 17 | Repository actions | Ready in proposal | protected operations |
| 18 | Model selection | Ready in proposal | vendor-neutral |
| 19 | TASK template | Ready in proposal | 28 sections |
| 20 | PLAN template | Ready in proposal | risk/rollback |
| 21 | ADR template | Ready in proposal | durable decisions |
| 22 | Source of truth per module | Ready in proposal | index + contracts |
| 23 | Stale docs marked/archived | Pending integration | migration plan ready; no deletion |
| 24 | No secrets in instructions | Ready in proposal | pattern scan clean |
| 25 | No temporary tasks in universal rules | Ready in proposal | Cleaner specifics modular |
| 26 | Universal, vendor-neutral rules | Ready in proposal | platform isolated |
| 27 | Copilot rules only in .github | Ready in proposal | yes |
| 28 | MAC not masked | Ready in proposal | repeated invariant |
| 29 | Coder/Grafana boundary | Ready in proposal | explicit |
| 30 | App/infrastructure boundary | Ready in proposal | explicit |
| 31 | Shared OmadaProvider | Ready in proposal | explicit |
| 32 | Existing token lifecycle | Ready in proposal | token per request |
| 33 | New token cache forbidden | Ready in proposal | ADR/TASK required |
| 34 | Single authorization flow | Ready in proposal | explicit diagram |
| 35 | Fail-open components | Ready in proposal | inventory + modules |
| 36 | Single-process limitations | Ready in proposal | sessions/workers |
| 37 | Configuration pipeline | Ready in proposal | config → settings |
| 38 | Execution modes | Ready in proposal | 5 modes |
| 39 | Repository permissions | Ready in proposal | granular |
| 40 | Capability declaration | Ready in proposal | mandatory |
| 41 | Handoff format | Ready in proposal | mandatory |
| 42 | Test responsibility | Ready in proposal | 4 values |
| 43 | Targeted/full tests | Ready in proposal | stable groups |
| 44 | No dependencies added | Ready in proposal | proposal adds none |
| 45 | Business logic unchanged | Ready in proposal | repo untouched |
| 46 | API contracts unchanged | Ready in proposal | repo untouched |
| 47 | JSONL schemas unchanged | Ready in proposal | repo untouched |
| 48 | SQLite schemas unchanged | Ready in proposal | repo untouched |
| 49 | Alloy/Loki/Grafana unchanged | Ready in proposal | repo untouched |
| 50 | Production systemd unchanged | Ready in proposal | repo untouched |
| 51 | Simple pilot | Pending integration | preliminary package pilot done |
| 52 | Planning-only pilot | Pending integration | preliminary Cleaner pilot done |
| 53 | Two agents or limitation | Ready in proposal | one agent; limitation documented |
| 54 | Full pytest passes | Blocked baseline | duplicate probe discovery; one sandbox failure in tests/ |
| 55 | compileall passes | Ready in proposal | baseline passed; rerun needed |
| 56 | git diff --check passes | Ready in proposal | baseline passed; rerun needed |
| 57 | Tech Lead review | Pending review | not claimed |
| 58 | Architect confirmation | Pending review | not claimed |

Задача не объявляется завершённой в repository, пока пункты 4, 23, 51, 52, 54, 57 и 58 не закрыты после approval.

