---
applyTo: "app/**/*repository.py,app/visitor_registry/**/*.py,app/public_traffic/**/*.py,app/portal_counter/**/*.py"
---

# Storage

- SQLite schema меняется только с migration plan, backup и rollback.
- Repository не зависит от Flask route или current_app.
- Транзакции ограничены; partial state не публикуется как success.
- Пути проходят существующую config pipeline и валидируются до worker start.
- Учитывай rotation, inode replacement, partial JSONL line и restart checkpoints.
- Visitor Registry не обращается к Omada.
- Pending Session Cleaner не читает visitor_registry.sqlite3.
- Не удаляй production data и не выполняй migration без deploy TASK.
