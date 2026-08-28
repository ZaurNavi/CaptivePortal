---
applyTo: "tests/**/*.py"
---

# Tests

- TASK-scoped test responsibility берётся из TASK: agent, owner, shared или not-applicable.
- Coder/agent запускает только focused/minimal TASK/module группу и новые regression cases своего изменения; повторные локальные прогоны этой же группы разрешены.
- Coder/agent может создавать/изменять automated tests своего implementation scope.
- Не запускай unrelated-module, cross-module, broader или full CaptivPortal regression. Если такой proof нужен, запроси Owner/Tech Lead/Central Lab execution или подготовь test без запуска.
- `C:\CaptivPortal-Lab` не запускается Coder/agent как официальный gate. Prep-only изменение Lab directory допустимо только по явному Owner/Tech Lead поручению и заканчивается до official execution.
- Не удаляй тесты, не ослабляй assertions и не исправляй несвязанные failures ради green result.
- Для внешних API используй deterministic fakes/fixtures; production network запрещён без отдельного TASK.
- Handoff содержит точную focused/minimal команду и числа passed, skipped, failed; cross-module/broader evidence и Central Lab evidence указываются отдельно и не приписываются agent.
- Environment failure отделяй от product failure.
