# TASK-DEBT-01 — Вынос Omada OpenAPI-конфигурации из Git и очистка repository artifacts

Статус: готово к передаче Coder  
Проект: CaptivPortal  
Execution mode: `implementation`  
Исполнитель: Coder / coding agent  
Test responsibility: `agent`  
Ожидаемая ветка: `fix/openapi-credentials-repository-hygiene`

## 1. Цель

Устранить критический security debt: удалить production-значения Omada OpenAPI из отслеживаемых файлов и перевести их на существующий process-environment pipeline.

Одновременно удалить уже отслеживаемые Python cache и локальные backup-файлы, не затрагивая business logic, production, инфраструктуру и историю Git.

## 2. Подтверждённый baseline

- Перед началом выполнить `git fetch origin` и проверить актуальный `origin/main`.
- Baseline на момент выдачи TASK: `origin/main` — `76107aa826e84e4ea94a9be5421717a49daa5bcc`.
- Runtime-код после PR #32 соответствует `804b054c73d0ce02c57f05b2c29394b5b6dd87ae`; последующие три commit меняли только README.
- Последний Linux regression gate на production Python 3.10.12: `894 passed, 10 skipped, 0 failed`; `compileall` и `git diff --check` прошли.
- Если после `git fetch` `origin/main` уже другой, не считать это автоматическим конфликтом: проверить изменённые пути. Если затронуты разрешённые этой задачей файлы или требования стали неактуальны, остановиться и передать факты Tech Lead.

## 3. Текущее фактическое состояние

1. `app/config.py` содержит literal-значения:
   - `OMADA_URL`;
   - `OMADA_ID`;
   - `CLIENT_ID`;
   - `CLIENT_SECRET`.
2. Отслеживаемый `app/config.py.bak-20260727-004725` также содержит OpenAPI credentials.
3. В Git отслеживаются:
   - `app/__pycache__/*.pyc`;
   - `app/controllers/__pycache__/*.pyc`;
   - `app/config.py.bak-20260727-004725`;
   - `app/web/web.py.bak-20260727-004505`.
4. `.gitignore` уже содержит правила для `__pycache__/`, `*.py[cod]`, `.env` и `.env.*`, но ранее добавленные tracked-файлы от этого сами не исчезают.
5. Приложение не загружает `.env` автоматически. Production configuration передаётся процессу извне, например через systemd `EnvironmentFile`.
6. Старый Client Secret останется в Git history даже после удаления из текущего дерева. Переписывание истории не входит в TASK; после безопасного внедрения потребуется owner-controlled rotation.

## 4. Требуемое поведение

### 4.1. Environment contract

Использовать следующие внешние переменные:

| Environment variable | Существующий внутренний ключ `get_settings()` |
|---|---|
| `OMADA_URL` | `omada_url` |
| `OMADA_ID` | `omada_id` |
| `OMADA_CLIENT_ID` | `client_id` |
| `OMADA_CLIENT_SECRET` | `client_secret` |

Требования:

- значения читаются через существующий `app/config.py` → `app/settings.py:get_settings()` pipeline;
- public/internal keys словаря `get_settings()` не переименовываются;
- значения очищаются от случайных пробелов по краям;
- production literals и реальные fallback-значения запрещены;
- пустое или отсутствующее обязательное значение должно приводить к `ConfigurationError` при создании `OmadaProvider`, до первого HTTP-запроса;
- ошибка может перечислить только имена отсутствующих переменных/настроек, но не их значения;
- `OMADA_URL` должен быть непустым HTTP(S) URL; проверка не должна выводить URL credentials/query в error или log;
- существующий shared `OmadaProvider`, token cache и controller factory сохраняются.

### 4.2. Example configuration

Обновить `.env.example`:

- добавить четыре переменные из таблицы;
- использовать только пустые значения или явно нерабочие placeholders;
- указать, что файл не загружается приложением автоматически;
- не добавлять реальный URL, Omada ID, Client ID или Client Secret.

### 4.3. Repository hygiene

Удалить из Git current tree:

- все отслеживаемые `__pycache__/` и `*.pyc`;
- `app/config.py.bak-20260727-004725`;
- `app/web/web.py.bak-20260727-004505`.

Проверить, что `.gitignore` предотвращает повторное добавление этих классов файлов. Менять `.gitignore` только если фактическое правило недостаточно; косметический рефакторинг файла не выполнять.

Не выполнять ручное удаление runtime cache на production host. TASK изменяет только repository tree.

### 4.4. Documentation

Минимально обновить:

- `docs/deployment.md` — перечислить обязательные имена environment variables и зафиксировать, что deployment кода нельзя перезапускать до подготовки environment;
- `docs/security.md` — зафиксировать, что Omada Client Secret поступает только через process environment/approved secret mechanism и после exposure в history требует rotation.

Значения, fingerprint, длина и фрагменты секрета в документацию не добавлять.

## 5. Fail-closed / fail-open

- Core Omada configuration работает fail-closed: без полного набора обязательных настроек `OmadaProvider` не создаётся.
- Ошибка должна произойти до network request и не раскрывать secret.
- Fail-open contracts независимых operational workers не меняются.
- Portal authorization behavior при корректной configuration не меняется.

## 6. Разрешённые файлы

Изменение:

- `app/config.py`;
- `app/settings.py` — только если необходимо сохранить существующий mapping;
- `app/controllers/omada.py` — только валидация обязательной configuration при initialization;
- `.env.example`;
- `.gitignore` — только при доказанной необходимости;
- `docs/deployment.md`;
- `docs/security.md`;
- новый focused test, предпочтительно `tests/test_omada_configuration.py`;
- существующий тестовый файл Omada — только если focused coverage невозможно разместить отдельно.

Удаление:

- tracked `app/**/__pycache__/*`;
- tracked `app/**/*.pyc`;
- `app/config.py.bak-20260727-004725`;
- `app/web/web.py.bak-20260727-004505`.

Если для минимальной реализации требуется другой файл, остановить эту часть и запросить расширение scope с точным обоснованием.

## 7. Запрещённые области

Не изменять:

- `run.py`;
- `app/auth/` и `app/auth_telemetry/`;
- `app/capport/`;
- `app/pending_sessions/`;
- `app/visitor_registry/`;
- portal templates/JavaScript/CSS;
- JSONL schemas и SQLite schemas;
- `requirements*.txt`;
- `.github/workflows/`;
- `outputs/omada-webhook-normalized.alloy`;
- Alloy, Loki, Grafana, reverse proxy и production systemd;
- Omada controller applications/secrets;
- Git history.

Не выполнять общий refactor, форматирование несвязанных файлов или переименование public interfaces.

## 8. Security requirements

- Не выводить и не копировать текущие credential values в terminal transcript, test output, commit message, TASK, PLAN, PR или handoff.
- Не добавлять secret в fixtures и mocks. Использовать явно тестовые значения.
- Не логировать environment dictionary, settings dictionary или payload token endpoint целиком.
- Не добавлять temporary backup с credential values.
- Не выполнять `git filter-repo`, BFG, rebase/rewrite history или force-push.
- Не запрашивать новый production secret у владельца для реализации или тестов.
- Проверить staged diff на secrets без печати найденного значения.

## 9. Обязательные tests

Добавить focused coverage минимум для следующих cases:

1. Все четыре environment variables корректно попадают в существующие keys `get_settings()`.
2. Пробелы по краям удаляются.
3. Отсутствующий `OMADA_URL` отклоняется.
4. Отсутствующий `OMADA_ID` отклоняется.
5. Отсутствующий `OMADA_CLIENT_ID` отклоняется.
6. Отсутствующий `OMADA_CLIENT_SECRET` отклоняется.
7. Пустое/whitespace-only значение отклоняется.
8. Невалидная схема `OMADA_URL` отклоняется.
9. Ошибка не содержит test secret value.
10. При invalid configuration `requests.post/get` не вызываются.
11. При valid configuration `OmadaProvider` создаётся и сохраняет существующий mapping; сетевой запрос в этом test не выполняется.

Tests не должны зависеть от production environment. После test module environment/import state должен быть восстановлен, чтобы full suite не зависел от порядка запуска.

Предпочтительная targeted command:

```bash
python -m pytest \
  tests/test_omada_configuration.py \
  tests/test_omada_client_lookup.py \
  -q --tb=short
```

Если имя focused test отличается, указать фактическую команду в handoff.

## 10. Full gate

После targeted tests выполнить:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
```

Дополнительные repository checks:

```bash
git ls-files | rg '(^|/)(__pycache__/|.*\.py[co]$|.*\.bak-[^/]*$)'
git status --short
```

Первая команда должна завершиться без совпадений. Отсутствие совпадений является PASS, даже если `rg` возвращает exit code 1.

Frontend Node tests, CI workflow и production Linux deployment в этот TASK не входят.

## 11. Acceptance criteria

TASK считается реализованным, если одновременно выполнено всё:

- в current tree нет production Omada URL/ID/Client ID/Client Secret literals;
- `OMADA_CLIENT_SECRET` поступает только из process environment;
- отсутствующая/invalid core configuration останавливает создание provider до HTTP;
- public keys `omada_url`, `omada_id`, `client_id`, `client_secret` сохранены;
- общий provider и token lifecycle не изменены;
- `.env.example` содержит безопасный contract без реальных значений;
- tracked pycache/pyc и оба backup-файла удалены;
- документация configuration/security обновлена минимально;
- targeted tests прошли;
- full gate прошёл с точными числами passed/skipped/failed;
- `compileall` и `git diff --check` прошли;
- diff не содержит unrelated changes и новых secrets;
- production, controller secret и Git history не изменялись.

## 12. Stop conditions

Остановить затронутую часть и передать Tech Lead точные факты, если:

- актуальный main уже меняет указанный environment contract;
- существующие tests требуют реального production credential;
- безопасная fail-closed validation требует изменения файла вне allowed scope;
- найден другой tracked файл с возможным production secret;
- обнаружено, что удаляемый backup является единственным источником нужного current code;
- требуется history rewrite, force-push, controller action или production deploy;
- full suite падает по несвязанной причине.

Независимые безопасные части продолжить. Возможный secret value в handoff не приводить.

## 13. Repository actions

Разрешено:

- создать ветку `fix/openapi-credentials-repository-hygiene` от актуального `origin/main`;
- изменить только allowed files;
- удалить перечисленные tracked artifacts;
- выполнить tests/checks;
- создать один локальный commit после успешных проверок.

Рекомендуемый commit message:

```text
security: externalize Omada credentials and clean repository artifacts
```

Без отдельного разрешения владельца запрещено:

- push;
- PR;
- merge;
- force-push;
- rewrite history;
- deploy;
- restart service;
- изменение production environment;
- rotation/revocation Client Secret.

## 14. Handoff format

Вернуть:

1. Цель и фактический результат.
2. Изменённые/удалённые файлы с краткой причиной.
3. Изменения contracts: config/security; отдельно подтвердить отсутствие изменений API/events/persistence/lifecycle architecture.
4. Targeted test command и точные `passed/skipped/failed`.
5. Full gate command и точные `passed/skipped/failed`.
6. Результат `compileall`, `git diff --check` и tracked-artifact check.
7. Риски и ограничения.
8. Фактически выполненные repository actions и commit SHA, если commit создан.
9. Явное подтверждение: push/PR/merge/deploy/history rewrite/secret rotation не выполнялись.
10. Owner actions без secret values.
11. `Agent execution summary` по `docs/agents/handoff.md`.

## 15. Owner actions после принятия кода

Эти действия Coder не выполняет:

1. Tech Lead проверяет diff, tests и отсутствие credential literals.
2. Отдельным deploy TASK владелец заранее добавляет четыре обязательные переменные в production process environment без вывода значений.
3. Выполняются deployment, restart и health checks.
4. После подтверждения env-driven runtime владелец выпускает новый Omada Client Secret, безопасно обновляет production environment и повторяет restart/health checks.
5. Старый exposed Client Secret отзывается. Если Omada rotation автоматически инвалидирует старый secret, порядок операции уточняется до изменения, чтобы сократить outage.
6. Переписывание публичной Git history рассматривается только отдельным security decision; rotation обязательна независимо от решения по history.

