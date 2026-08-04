---
applyTo: "app/**/*.py,run.py"
---

# Python

- Сохраняй существующие слои и public signatures.
- Используй app/config.py → app/settings.py:get_settings().
- Не создавай объект с network, file или thread side effects при import.
- run.py остаётся единственным process entrypoint.
- Используй типы и dataclasses в стиле соседнего кода; не добавляй dependency ради удобства.
- Все network calls имеют bounded timeout; retries ограничены.
- Не перехватывай Exception без telemetry и безопасного результата.
- Не используй print() в production code.
- Не меняй business logic вне TASK.
