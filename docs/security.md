# Security

Status: current
Updated: 2026-08-10

## Secrets

- Secrets поступают только через production environment или утверждённый secret mechanism.
- Secrets запрещены в Git, fixtures, TASK, PLAN, ADR, PR, chat handoff и examples.
- Access Token, Client Secret, cookie, Authorization header и SSID password не логируются.
- Agent не запрашивает production secret без прямой необходимости.
- Exception и raw response очищаются до journal/telemetry.
- Omada Client Secret передаётся только через process environment или другой
  утверждённый secret mechanism; fallback-значение в repository запрещено.
- Если Omada Client Secret когда-либо попал в Git history, его необходимо
  заменить и отозвать в рамках owner-controlled rotation независимо от решения
  о переписывании history.

## Current findings на `main@ab776af`

- Production Omada credentials отсутствуют в current Git tree. `OMADA_URL`,
  `OMADA_ID`, `OMADA_CLIENT_ID` и `OMADA_CLIENT_SECRET` читаются из process
  environment и не имеют repository fallback values.
- Tracked Python cache и backup-файлы удалены; `.gitignore` блокирует их
  повторное добавление.
- Старый Omada Client Secret остаётся в Git history. Owner-controlled rotation
  и отзыв старого значения остаются OPEN независимо от решения о переписывании
  history.
- `VERIFY_SSL=false` остаётся current repository contract и открытым
  security/operations debt. Включение TLS verification требует отдельного TASK,
  выбранной доверенной certificate model и focused deployment/tests.

Secret values, fingerprints, длина и фрагменты в findings не фиксируются.

## Identifiers и network boundary

- MAC не считается secret и не маскируется в технических журналах.
- CAPPORT проверяет guest source IP по allowlist.
- Trust к reverse proxy ограничен известной topology; forwarded headers не принимаются безусловно.
- Webhook source/auth policy проверяется до persistence.

## Files и persistence

- Repository, logs и data имеют минимальные POSIX permissions.
- SQLite backup создаётся до migration.
- Raw Omada override response не сохраняется: он может содержать пароль SSID.
- Data journal выполняет redaction известных sensitive keys.

Этот документ содержит только постоянную policy. Findings конкретного снимка фиксируются в ограниченном review report и отдельном security TASK без раскрытия значений.
