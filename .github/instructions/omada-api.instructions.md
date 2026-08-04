---
applyTo: "app/controllers/omada.py,app/controllers/omada_pending_sessions.py,app/integrations/omada/**/*.py,tests/**/*omada*.py"
---

# Omada Open API

- Используй общий OmadaProvider и сначала проверь фактический token lifecycle в текущем коде и тестах.
- Не создавай второй provider или token manager. Изменение cache/lifecycle требует явного TASK, concurrency tests и при устойчивом решении ADR.
- При конфликте current state и change intent останови затронутую часть и передай точные источники Architect/Tech Lead.
- Проверяй HTTP status и JSON errorCode отдельно.
- errorCode -44112 означает истёкший token; recovery должен быть bounded и endpoint-specific.
- Authorization header имеет форму AccessToken=<token>; значение не логируется.
- MAC в URL форматируй через app/common/mac.py по контракту endpoint.
- Используй только endpoints, подтверждённые docs/api/omada-open-api.md.
- Не сохраняй полный override response: он может содержать пароль SSID.
- Mutation endpoint требует отдельного TASK, guard, audit и verification.
