# Handoff contract

Status: current
Updated: 2026-08-28
Central Lab governance effective: 2026-08-27

## Обязательный итог

### Цель и результат

Что требовалось и что фактически сделано.

### Изменённые файлы

Каждый файл и краткая причина. Если изменений нет — сказать явно.

### Контракты

Изменились ли public API, config, events, persistence, lifecycle, security или architecture.

### TASK-scoped проверки исполнителя

Точные focused/minimal TASK/module/static команды и результат: passed, skipped, failed. Не выполненные проверки — с причиной.

Если для доказательства нужен test вне module/TASK boundary, указать отдельно одно из:

```text
cross-module test requested from Owner/Tech Lead/Central Lab
```

```text
cross-module test prepared by Coder but NOT executed
```

Не писать, что Coder выполнил broader/full regression или official gate.

### Central Lab / official Test Evidence

Указать одно из:

```text
not required for this handoff
pending Owner/Tech Lead Central Lab gate
Coder Lab preparation only: <explicit delegated action>
Central Lab evidence: <artifact/date/result/reference>
```

Coder не заявляет official Central Lab execution или PASS/FAIL. Если Coder получил prep-only доступ к `C:\CaptivPortal-Lab`, handoff перечисляет только подготовительные действия и явно возвращает gate Owner/Tech Lead.

Для official evidence указывать exact artifact, Owner physical execution и Owner + Tech Lead PASS/FAIL.

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
    Cross-module/broader test: requested / prepared-not-run / not-required
    Central Lab preparation: none / explicitly delegated prep-only action
    Central Lab full regression: not-run-by-agent / Owner+Tech Lead evidence reference / not-required
    Linux pre-production gate: separate / evidence reference / not-required
    Unexpected rework:
    Reason for additional context:
    Repository actions:

## Запрещено

Не прикладывать полную command history, многотысячные logs, secrets или неподтверждённые claims.