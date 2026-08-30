# TASK-XXX — Название

Status: draft

## 1. Цель

## 2. Execution mode

planning-only / implementation / review / publish / deploy

## 3. Исполнитель и agent platform

## 4. Agent capability assumptions

## 5. TASK-scoped test responsibility

agent / owner / shared / not-applicable

> `agent` означает только focused/minimal automated tests текущего TASK/модуля.
> Cross-module/broader/full execution и official acceptance принадлежат
> Owner/Tech Lead/Central Lab.

## 6. Текущее состояние

## 7. Требуемое поведение

## 8. Не входит в задачу

## 9. Связанные документы

Указать 1–3 current contracts.

## 10. Разрешённые файлы

## 11. Запрещённые файлы и области

## 12. Разрешённые repository actions

## 13. Запрещённые и owner-only repository actions

## 14. Архитектурные ограничения

## 15. Входные контракты

## 16. Выходные контракты

## 17. Error handling

## 18. Fail-open / fail-closed

## 19. Logging и events

## 20. Persistence

## 21. Lifecycle и shutdown

## 22. Security

## 23. Targeted/module tests

Указать expected new/changed test files и exact focused/minimal command.
После implementation handoff Tech Lead пересматривает current targeted set.

## 24. Cross-module / broader / full regression

```text
cross-module test needed: yes/no
fresh Central Lab baseline required: yes/no
exact candidate tree:
official Lab operator: Owner
gate direction / PASS-FAIL: Tech Lead + Owner
```

## 25. Other mandatory acceptance gates

Explicitly list:

```text
Linux/production-compatible:
PERF/capacity:
migration/schema:
security:
browser:
other:
```

Required gates are pre-publication acceptance.

## 26. Acceptance-before-Publication

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

Define exact conditions for `candidate accepted`.

## 27. Publication / chain-of-custody

```text
normal publication before full acceptance: NO
accepted candidate tree:
publication commit/tree:
PR head tree:
merge tree:
```

TEST-ONLY experimental publication requires Owner + Tech Lead and must be marked
NOT ACCEPTED / NOT MERGEABLE / NOT DEPLOYABLE.

## 28. Production delivery / activation

Normal application code deploy:

```text
FROM GIT
verified SHA/tree
```

Activation is separate Owner-controlled action.

## 29. Acceptance criteria

## 30. Stop conditions

## 31. Handoff format

## 32. PR requirements
