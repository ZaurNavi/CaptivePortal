---
applyTo: "tests/**/*.py"
---

# Tests

- Test responsibility берётся только из TASK: agent, owner, shared или not-applicable.
- Сначала запускай минимальную связанную группу, затем full gate.
- Не удаляй тесты, не ослабляй assertions и не исправляй несвязанные failures.
- Для внешних API используй deterministic fakes/fixtures; production network запрещён без отдельного TASK.
- Отчёт содержит точную команду и числа passed, skipped, failed.
- Environment failure отделяй от product failure.
