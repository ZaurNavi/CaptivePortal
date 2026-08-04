---
applyTo: "app/pending_sessions/**/*.py,app/controllers/omada_pending_sessions.py,tests/pending_sessions/**/*.py"
---

# Pending Client Session Cleaner

- Read `docs/modules/pending-session-cleaner.md`, `docs/api/omada-open-api.md` and the current TASK.
- Preserve the single shared `OmadaProvider` and its thread-safe token cache; no second provider, OAuth client, cache or token manager.
- Mutation is `reconnect` only. Incomplete inventory, local protection, failed/stale preflight, unavailable audit, exhausted guard/budget or shutdown must block POST.
- Preserve two local-protection checks, audit-before-action and bounded verification. Do not add blind POST retry.
- Cleaner stays fail-open relative to portal authorization and never reads Visitor Registry SQLite.
- JSONL schema changes require tests and `docs/modules/pending-session-cleaner.md`; keep full MAC and exclude tokens, headers, cookies, secrets and raw responses.
- Default feature state remains disabled. Multi-process activation requires an ADR for leader election or inter-process locking.
- Run `python -m pytest tests/pending_sessions -q --tb=short`, then the full gate from `docs/testing.md`.
