---
applyTo: "tests/**/*.py"
---

# Tests

- TASK-scoped test responsibility берётся из TASK: agent, owner, shared или not-applicable.
- Coder/agent запускает минимальную связанную targeted/module группу и новые regression cases текущего TASK; повторные локальные targeted-прогоны во время разработки разрешены.
- Не запускай full CaptivPortal suite по умолчанию только потому, что изменён test-файл; официальный full regression принадлежит Central Lab согласно `AGENTS.md` и `docs/testing.md`.
- Exceptional broader/full run в agent workflow требует отдельной прямой причины/owner requirement.
- Не удаляй тесты, не ослабляй assertions и не исправляй несвязанные failures ради green result.
- Для внешних API используй deterministic fakes/fixtures; production network запрещён без отдельного TASK.
- Handoff содержит точную targeted-команду и числа passed, skipped, failed; Central Lab evidence указывается отдельно и не приписывается agent.
- Environment failure отделяй от product failure.