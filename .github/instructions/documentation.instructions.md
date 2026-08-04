---
applyTo: "README*.md,docs/**/*.md,AGENTS.md,.github/**/*.md"
---

# Documentation

- Один документ — одна ответственность; детали не копируй, связывай ссылками.
- Указывай status, дату актуализации, модуль и проверенный commit для inventory.
- Исторический документ архивируй или помечай deprecated; две final-версии запрещены.
- Не копируй полный source, log или chat history.
- Secrets и реальные production values запрещены; examples используют placeholders.
- Универсальные правила не содержат названий AI-продуктов.
- Platform-specific поведение находится только в adapter.
- Изменение architecture, public contract, config, event schema, persistence, lifecycle или tests обновляет связанный документ в том же PR.
