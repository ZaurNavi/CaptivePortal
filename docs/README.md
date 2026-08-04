# CaptivPortal knowledge base

Status: current
Updated: 2026-08-04

Это навигация, а не ещё одно описание архитектуры.

## Для новой задачи

1. Создайте TASK по docs/tasks/TASK-template.md.
2. Передайте агенту TASK, execution mode и 1–3 связанных документа.
3. Агент читает AGENTS.md, затем текущий TASK и только указанные документы.
4. Агент сверяет код, тесты и актуальную документацию до планирования изменения.
5. Результат возвращается по docs/agents/handoff.md.

## Модели истины

Current-state truth: код → тесты → актуальная документация.

Change-intent truth: утверждённый TASK → PLAN → ADR.

TASK является scope contract изменения, но не подменяет фактическое состояние. При конфликте затронутая часть останавливается, источники фиксируются и передаются Architect/Tech Lead.

## Карта знаний

| Нужно понять | Документ |
|---|---|
| Фактический снимок main | project-inventory.md |
| Архитектура и границы | architecture.md |
| Статусы и маршрутизация по модулям | module-index.md |
| Omada Open API | api/omada-open-api.md |
| Тесты | testing.md |
| Журналы и telemetry | logging.md |
| Deployment и rollback | deployment.md |
| Security | security.md |
| Процесс coding agent | agents/workflow.md |
| Контракт задачи | agents/task-contract.md |
| Repository permissions | agents/repository-actions.md |
| Формат результата | agents/handoff.md |
| Выбор класса модели | agents/model-selection.md |
| Предварительные материалы pilots | agents/pilot-results.md |
| Устойчивые решения | decisions/ |
| История | archive/ |

## Модульные документы

Текущий список и status находятся только в module-index.md. Открывайте документ модуля, если TASK затрагивает его код, контракт, persistence, events или lifecycle.

## Принцип экономии контекста

AGENTS.md содержит только стабильные инварианты. TASK выбирает минимальный набор документов. Подробности хранятся один раз и связываются ссылками. Полные журналы, исходники, история чатов и несвязанные модули в prompt не передаются.
