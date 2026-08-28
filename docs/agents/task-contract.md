# Контракт TASK

Status: current
Updated: 2026-08-28
Central Lab governance effective: 2026-08-27

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
- TASK-scoped test responsibility: agent, owner, shared или not-applicable;
- требуется ли свежий официальный Central Lab full-regression baseline для продвижения exact artifact;
- требуется ли отдельный Linux/production-compatible gate;
- текущее фактическое состояние;
- out of scope;
- 1–3 связанных документа;
- allowed и forbidden files;
- allowed, forbidden и owner-only repository actions;
- входные и выходные contracts;
- fail-open/fail-closed;
- logging, persistence, lifecycle и security;
- targeted tests;
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

## TASK-scoped test responsibility

Значения относятся только к минимальному тестированию конкретного TASK/изменяемого модуля:

- `agent`: агент создаёт/обновляет и запускает focused/minimal TASK/module tests своего изменения;
- `owner`: агент не запускает назначенные tests и описывает необходимые cases/actions;
- `shared`: TASK делит конкретные TASK-scoped cases/actions;
- `not-applicable`: TASK объясняет, почему TASK-scoped tests не требуются.

`agent` никогда не означает право запуска unrelated-module, cross-module, broader или full repository regression.

Если необходим test вне границ текущего модуля, TASK должен выбрать: `request external execution` или `agent prepares test but does not run it`.

Исторические TASK не переписываются только из-за новой governance-модели; current rule имеет приоритет для новых execution handoff.

## Official full regression

Официальный cross-module/broader/full regression / current baseline / final Test Evidence следует ownership rule из `docs/testing.md`.

TASK должен указать:

```text
fresh Central Lab baseline required: yes/no
exact artifact to validate: <SHA/patch identity when known>
cross-module test needed: yes/no
if yes: external execution OR agent prepares-without-running
Coder Lab preparation delegated: yes/no
if yes: exact prep-only scope
official Lab operator: Owner
gate direction / PASS-FAIL ownership: Tech Lead + Owner
```

TASK не назначает Coder исполнителем official Central Lab gate, broader/full regression или official acceptance.

## Linux / production-compatible gate

Linux gate — отдельная release/deploy acceptance boundary. TASK указывает необходимость и среду; он не назначается автоматически Coder или Tech Lead.

## Repository permissions

Implementation mode не означает автоматический commit или push. Publish permissions всегда перечисляются явно.