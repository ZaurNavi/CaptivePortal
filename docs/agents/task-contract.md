# Контракт TASK

Status: current
Updated: 2026-08-04

TASK — высший источник change intent конкретной задачи и её scope contract. Он не является источником фактов о текущей реализации и не может молча отменить security или необратимые owner-only ограничения.

## Две модели истины

Current-state truth:

1. код;
2. тесты;
3. актуальная документация.

Change-intent truth:

1. утверждённый TASK;
2. PLAN;
3. ADR.

TASK определяет требуемое изменение относительно подтверждённого current state. PLAN описывает способ выполнения TASK. ADR фиксирует устойчивое архитектурное решение, но не подменяет фактическую проверку кода и тестов.

## Обязательные поля

- цель и требуемое поведение;
- execution mode;
- исполнитель/platform;
- capability assumptions;
- test responsibility: agent, owner, shared или not-applicable;
- текущее фактическое состояние;
- out of scope;
- 1–3 связанных документа;
- allowed и forbidden files;
- allowed, forbidden и owner-only repository actions;
- входные и выходные contracts;
- fail-open/fail-closed;
- logging, persistence, lifecycle и security;
- targeted tests и full gate;
- acceptance и stop conditions;
- handoff и PR requirements.

## Scope rule

Файл не становится разрешённым только потому, что его удобно отрефакторить. Если необходимый файл отсутствует в allowed list, агент останавливает эту часть и объясняет минимальное расширение.

## Conflicts

При противоречии внутри current-state truth, внутри change-intent truth или между ними агент:

1. приводит точные факты;
2. не выбирает молча одну сторону;
3. продолжает независимые безопасные части;
4. передаёт конфликт Architect/Tech Lead.

## Test responsibility

- agent: агент создаёт/обновляет и запускает назначенные tests.
- owner: агент не добавляет tests, но описывает необходимые cases.
- shared: TASK делит конкретные cases/actions.
- not-applicable: TASK объясняет почему.

## Repository permissions

Implementation mode не означает автоматический commit или push. Publish permissions всегда перечисляются явно.
