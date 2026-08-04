---
applyTo: "app/**/*worker.py,app/**/*collector.py,run.py"
---

# Background workers

- Создание и startup — только в composition root; никаких side effects при import.
- Один worker на process, если ADR не говорит иначе.
- Fixed-delay; overlapping scan запрещён.
- stop() идемпотентен, ожидание interruptible, shutdown bounded.
- После stop_accepting() новые mutation не начинаются.
- HTTP timeout, retries и verification ограничены.
- Ошибка worker не останавливает Flask; модуль переходит в unavailable/disabled с telemetry.
- Flask current_app из thread запрещён.
- Feature по умолчанию выключен, если это контракт модуля.
- Rollback в production: feature disable + service restart.
- Lifecycle change требует PLAN.
