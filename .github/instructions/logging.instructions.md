---
applyTo: "app/**/*.py,tools/**/*.py"
---

# Logging and journals

Operational telemetry диагностирует приложение; data journal хранит устойчивые события. Не смешивай их контракты.

- JSONL: UTF-8, strict JSON, одна запись на строку, UTC timestamp, allow_nan=false.
- MAC сохраняется полностью.
- Tokens, passwords, cookies, Authorization headers и SSID password запрещены.
- Полный Omada override response запрещён.
- Schema event меняется вместе с документацией и тестами.
- Не используй print() в production.
- Coder заканчивает работу после корректной записи events.
- Grafana, Alloy и Loki меняются только отдельным infrastructure TASK.
