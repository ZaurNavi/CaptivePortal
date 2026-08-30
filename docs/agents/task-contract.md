# Контракт TASK

Status: current
Updated: 2026-08-30
Central Lab governance effective: 2026-08-27
Acceptance-before-Publication governance effective: 2026-08-30

TASK — высший источник change intent конкретной задачи и её scope contract.
Он не является источником фактов о текущей реализации и не может молча отменить
security, acceptance-before-publication или owner-only ограничения.

## Две модели истины

Current-state truth:

1. код;
2. тесты;
3. актуальная документация.

Change-intent truth:

1. утверждённый TASK;
2. PLAN;
3. ADR.

TASK определяет требуемое изменение относительно подтверждённого current state.
PLAN описывает способ выполнения TASK. ADR фиксирует устойчивое архитектурное
решение, но не подменяет фактическую проверку кода и тестов.

## Обязательные поля

- цель и требуемое поведение;
- execution mode;
- исполнитель/platform;
- capability assumptions;
- TASK-scoped test responsibility;
- **полный список mandatory acceptance gates**;
- требуется ли fresh Central Lab full gate;
- требуется ли Linux/production-compatible gate;
- требуется ли production-size PERF/capacity/migration/security/browser gate;
- exact candidate identity/tree rule;
- текущее фактическое состояние;
- out of scope;
- 1–3 связанных документа;
- allowed/forbidden files;
- allowed/forbidden/owner-only repository actions;
- contracts, fail-open/fail-closed, logging, persistence, lifecycle, security;
- targeted tests;
- acceptance and stop conditions;
- publication authorization condition;
- deploy/activation separation;
- handoff and PR requirements.

## Scope rule

Файл не становится разрешённым только потому, что его удобно отрефакторить.
Если необходимый файл отсутствует в allowed list, исполнитель останавливает
затронутую часть и объясняет минимальное расширение.

## TASK-scoped test responsibility

Значения относятся только к минимальному тестированию текущего TASK/модуля:

- `agent`: focused/minimal TASK/module tests;
- `owner`: agent не запускает назначенные tests;
- `shared`: TASK делит конкретные TASK-scoped cases/actions;
- `not-applicable`: TASK объясняет отсутствие TASK-scoped tests.

`agent` никогда не означает право запуска unrelated-module, cross-module,
broader/full repository regression или official acceptance.

Если proof требует test вне module boundary, TASK выбирает:
`request external execution` или `agent prepares test but does not run it`.

## Mandatory acceptance gates

TASK обязан перечислить все обязательные до publication gates.

Canonical rule:

```text
candidate accepted
=
all mandatory gates for exact candidate tree PASS
```

Например, если FINAL требует PERF:

```text
targeted PASS
V6 PASS
PERF FAIL
→ candidate REJECTED
→ publication NOT AUTHORIZED
```

После remediation новый tree — новый candidate. Tech Lead определяет, какие gates
должны быть повторены; TASK/FINAL может требовать повтор всей официальной матрицы.

## Official full regression

Cross-module/broader/full regression follows `docs/testing.md`.

TASK указывает:

```text
fresh Central Lab baseline required: yes/no
exact artifact/tree:
cross-module test needed: yes/no
if yes: external execution OR agent prepares-without-running
Coder Lab preparation delegated: yes/no
official Lab operator: Owner
gate direction / PASS-FAIL ownership: Tech Lead + Owner
```

Coder не назначается operator official Central Lab gate.

## Linux / production-compatible acceptance

If mandatory, Linux/production-compatible/PERF acceptance is part of
**pre-publication candidate acceptance**, not post-publication testing.

Preferred controlled environment is Linux Central Lab or another isolated
production-compatible acceptance environment.

Mandatory acceptance must not require normal GitHub publication merely as
transport.

Candidate may be transported as:

```text
patch
local bundle
controlled worktree materialization
other controlled lab artifact
```

with exact tree verification.

Production-size data may be supplied as a consistent immutable read-only
snapshot with identity/hash and unchanged-after-test proof.

## Acceptance before Publication

Permanent sequence:

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

Normal publication commit/branch/PR is not an acceptance prerequisite.

A TEST-ONLY / EXPERIMENTAL publication exception requires explicit Owner +
Tech Lead authorization and is not accepted/mergeable/deployable.

## Repository permissions

Implementation mode does not imply commit/push.

Publication permissions are separate and become actionable only after acceptance
unless a specifically authorized TEST-ONLY exception applies.

Merge remains Owner-controlled.

## Production boundary

Normal production application deployment is Git-based and uses explicit verified
SHA/tree identity. Direct patch/source copying to production is not a standard
TASK path.

Emergency exception requires Owner + Tech Lead and later repository reconciliation.

## Historical TASK rule

Historical FINAL TASKs are not rewritten merely because governance evolves.
Current governance controls future execution and interpretation when an old TASK
contains weaker process wording.
