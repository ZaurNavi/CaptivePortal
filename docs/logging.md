# Logging, telemetry и data journals

Status: current
Updated: 2026-08-04

## Разделение

Operational telemetry отвечает на вопрос «в каком состоянии компонент и почему он отказал». Data journal хранит устойчивые структурированные факты для последующего чтения и аналитики. Один event contract не подменяет другой.

## Общий контракт

- JSONL, UTF-8, strict JSON, одна запись на строку.
- UTC timestamp и явная schema version.
- JSON serialization с allow_nan=false.
- Полный нормализованный MAC; MAC не считается secret.
- Access Token, Client Secret, cookies, Authorization header и SSID password запрещены.
- Полный Omada override response запрещён.
- Rotation и file permissions учитываются writer и deployment.
- Event name или schema меняются вместе с tests и связанной документацией.

## Current journals

| Файл | Роль | Owner |
|---|---|---|
| auth_telemetry.log | operational authorization telemetry | app/auth_telemetry |
| visitor_snapshots.log | authorized client data journal | snapshot collector |
| omada_webhook.log | raw redacted webhook journal | webhook receiver |
| omada_webhook_normalized.log | normalized data journal | webhook normalizer |
| pending_session_cleaner.log | Cleaner scan/action audit; rotating JSONL, mode 0640 | app/pending_sessions/journal.py |

SQLite files не являются logs.

## Pending Session Cleaner

Cleaner реализует три schema-versioned data events:

- `pending_session.scan.completed`;
- `pending_session.action.planned`;
- `pending_session.action.completed`.

`action.planned` должен быть успешно записан и flush-нут до POST; ошибка блокирует reconnect. `action.completed` фиксирует выполненное действие или deterministic skip первоначального кандидата. MAC сохраняется полностью; token, Authorization header, cookie, Client Secret и raw controller response не записываются.

Operational events `pending_session_cleaner_*` передаются отдельно через AuthorizationTelemetry adapter и не заменяют audit journal.

## Coder boundary

Coder реализует корректную запись предусмотренных events и tests. Он не настраивает Grafana, не изменяет Alloy и не изменяет Loki без отдельного infrastructure TASK.

## Передача логов агенту

Передавайте временной диапазон, component, event, correlation id, MAC и ограниченное окружение ошибки. Используйте tail/journalctl с лимитом; не передавайте rotated journals или многодневный verbose output целиком.
