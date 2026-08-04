# Workflow coding agent

Status: current
Updated: 2026-08-04

## 1. Intake

1. Прочитать AGENTS.md.
2. Прочитать текущий TASK как scope contract.
3. Определить execution mode.
4. Заявить capabilities.
5. Прочитать только документы из TASK.
6. Проверить current-state truth: код, затем тесты, затем актуальную документацию.

Если TASK отсутствует или неоднозначен, не восстанавливать задачу из chat history.

Current-state truth: код → тесты → актуальная документация. Change-intent truth: утверждённый TASK → PLAN → ADR. TASK описывает требуемое изменение, а не переписывает факты о текущем состоянии. При конфликте остановить затронутую часть, зафиксировать источники и передать Architect/Tech Lead; независимые безопасные части продолжить.

## 2. Modes

### planning-only

Разрешены чтение, проверка контрактов, короткий PLAN, список файлов и рисков. Изменения, branch, commit, push, PR и production запрещены.

### implementation

Разрешены только allowed files и проверки TASK. Repository actions назначаются отдельно.

### review

Разрешены diff, contracts, tests и verdict. Исправления только при прямом разрешении.

### publish

Разрешены только перечисленные branch/commit/push/Draft PR. Merge owner-only.

### deploy

Требует target, backup, flag, restart, health checks, rollback, owner и разрешённых production commands.

## 3. Plan

PLAN обязателен для нового модуля, нескольких подсистем, persistence, shared provider, concurrency, lifecycle, public contract или deploy. Для простой локальной правки достаточно 2–5 шагов в ответе.

## 4. Implementation

1. Изменять только allowed files.
2. Реализовать минимально достаточное поведение.
3. Не добавлять функции вне TASK.
4. Сохранять архитектурные инварианты.
5. Обновлять tests только по test responsibility.
6. Обновлять связанный knowledge document при изменении контракта.

## 5. Verification

1. Targeted tests.
2. Full pytest gate.
3. compileall.
4. git diff --check.
5. Проверка diff на secrets и unrelated changes.

Неисправимый environment limit или unrelated failure фиксируется в handoff.

## 6. Repository actions

Перед каждым write/publish action свериться с TASK и docs/agents/repository-actions.md. По умолчанию разрешено только read-only. PR по умолчанию Draft.

## 7. Handoff

Использовать docs/agents/handoff.md. Сохранять решения и факты, не transcript команд.

## 8. Session boundaries

Одна связанная сессия — один TASK. Новая сессия нужна при новом модуле, заменённом TASK, смене mode или загрязнённом/устаревшем контексте.

## 9. Token economy

- TASK содержит 1–3 knowledge links.
- rg и targeted reads предшествуют broad scan.
- В prompt передаются schema/contract, а не полный source.
- Logs ограничиваются релевантным диапазоном.
- Повторно не объясняется то, что стабильно записано в knowledge base.
- Agent execution summary позволяет техлиду выявить лишний context и rework.
