# Handoff contract

Status: current
Updated: 2026-08-26

## Обязательный итог

### Цель и результат

Что требовалось и что фактически сделано.

### Изменённые файлы

Каждый файл и краткая причина. Если изменений нет — сказать явно.

### Контракты

Изменились ли public API, config, events, persistence, lifecycle, security или architecture.

### TASK-scoped проверки исполнителя

Точные targeted/module/static команды и результат: passed, skipped, failed. Не выполненные проверки — с причиной.

Не писать, что Coder выполнил full regression, если он только передаёт Central Lab evidence.

### Central Lab / official Test Evidence

Указать одно из:

```text
not required for this handoff
pending Central Lab gate
Central Lab evidence: <artifact/date/result/reference>
```

Если официальный baseline существует, указать exact artifact и результат, но не приписывать выполнение Coder/Tech Lead.

### Linux / production-compatible evidence

Если применимо: environment, exact artifact, command/gate and result. Иначе явно `not applicable / separate release step`.

### Риски и ограничения

Известные defects, environment limits, incomplete gates и assumptions.

### Repository actions

Фактически выполненные branch, commit, push и PR; идентификаторы только если реально получены. Отдельно forbidden/not executed.

### Owner actions

Минимальные следующие действия с ответственным.

### Agent execution summary

    Agent/platform:
    Model:
    Task type:
    Execution mode:
    Files inspected:
    Files changed:
    Targeted/module tests:
    Central Lab full regression: not-run-by-agent / evidence reference / not-required
    Linux pre-production gate: separate / evidence reference / not-required
    Unexpected rework:
    Reason for additional context:
    Repository actions:

## Запрещено

Не прикладывать полную command history, многотысячные logs, secrets или неподтверждённые claims.