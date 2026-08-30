# Handoff contract

Status: current
Updated: 2026-08-30
Central Lab governance effective: 2026-08-27
Acceptance-before-Publication governance effective: 2026-08-30

## Обязательный итог

### Цель и результат

Что требовалось и что фактически сделано.

### Изменённые файлы

Каждый файл и краткая причина. Если изменений нет — сказать явно.

### Контракты

Изменились ли public API, config, events, persistence, lifecycle, security or architecture.

### Candidate identity

Обязательно:

```text
baseline SHA/tree:
candidate patch/commit identity:
candidate tree:
```

Если tree менялся после acceptance evidence, это новый candidate и должно быть
явно отмечено.

### TASK-scoped проверки исполнителя

Перечислить:
- new test files;
- modified existing test files;
- exact focused/minimal commands;
- passed/skipped/failed.

Если нужен cross-module proof:

```text
requested from Owner/Tech Lead/Central Lab
```

или:

```text
prepared by Coder but NOT executed
```

### Mandatory acceptance gate matrix

Для каждого gate из TASK/FINAL/release contract:

```text
gate:
required: yes/no
environment:
exact tree:
result: PASS/FAIL/PENDING/NOT-APPLICABLE
evidence reference:
```

Candidate нельзя называть accepted, пока любой mandatory gate = FAIL/PENDING.

### Central Lab / official Test Evidence

Указать одно из:

```text
not required
pending Owner/Tech Lead
Coder Lab preparation only
Central Lab evidence: <artifact/tree/date/verified-runner/result/reference>
```

Official PASS/FAIL принадлежит Owner + Tech Lead.

### Linux / production-compatible / PERF evidence

Если mandatory, это часть **pre-publication candidate acceptance**.

Указать:
- isolated environment;
- exact candidate tree;
- immutable production-size snapshot identity when used;
- read-only proof;
- result;
- unchanged snapshot/production application/service evidence where required.

### Acceptance status

```text
candidate accepted: YES/NO
all mandatory gates PASS: YES/NO
accepted candidate tree:
```

### Publication status

Publication is separate from acceptance:

```text
publication commit:
PR:
PR head tree:
merge:
merge tree:
chain-of-custody:
```

Do not describe TEST-ONLY experimental publication as accepted.

### Deployment / activation

```text
production deploy source: Git SHA/tree / not executed
production activation: executed / not executed / separate owner action
production acceptance: PASS/FAIL/PENDING/not executed
```

### Риски и ограничения

Known defects, environment limits, incomplete gates, assumptions.

### Repository actions

Only actually executed branch/commit/push/PR actions.

### Owner actions

Minimal next actions with responsible owner.

### Agent execution summary

    Agent/platform:
    Model:
    Task type:
    Execution mode:
    Files inspected:
    Files changed:
    New test files:
    Modified test files:
    Targeted/module tests:
    Cross-module/broader test:
    Central Lab full regression:
    Linux/PERF mandatory gate:
    Candidate tree:
    Candidate accepted:
    Publication commit/PR:
    Production deploy:
    Production activation:
    Unexpected rework:
    Repository actions:

## Запрещено

Не прикладывать full command history, многотысячные logs, secrets или
неподтверждённые claims.
