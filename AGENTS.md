# CaptivPortal: правила для coding agents

Status: current
Updated: 2026-08-04

## Project

CaptivPortal — Python-платформа внешнего Captive Portal и связанных operational-функций для Omada Controller.

## Модели истины

Current-state truth описывает то, что существует сейчас:

1. Код текущей ветки.
2. Тесты текущей ветки.
3. Актуальная документация в docs/.

Change-intent truth описывает утверждённое изменение:

1. Утверждённый TASK.
2. Связанный PLAN.
3. Связанный ADR.

TASK задаёт scope и намерение изменения, но не стоит выше фактического кода и тестов при описании текущего состояния. Repository history и chat history не используются для восстановления архитектуры, если актуальные документы существуют.

При противоречии внутри одной модели или между current state и change intent останови затронутую часть, укажи точные источники и передай конфликт Architect/Tech Lead. Независимые безопасные части можно продолжить.

## Минимальное чтение

1. Прочитай TASK.
2. Определи execution mode, test responsibility и repository actions.
3. Прочитай только документы, указанные в TASK.
4. Проверь связанные файлы, сигнатуры и тесты.
5. Не сканируй весь репозиторий без причины.

Карта знаний: docs/README.md.
Процесс: docs/agents/workflow.md.
Контракт TASK: docs/agents/task-contract.md.
Формат результата: docs/agents/handoff.md.

## Capabilities

До работы явно определи доступность:

- repository read и write;
- shell и test execution;
- branch, commit, push и pull request;
- external network;
- production access.

Не имитируй недоступное действие. Выполни доступную часть и оставь owner action.

## Execution modes

- planning-only: чтение, проверка контрактов и план; без изменений.
- implementation: изменения только в разрешённых файлах.
- review: анализ diff и verdict; исправления только при отдельном разрешении.
- publish: только явно разрешённые branch, commit, push или Draft PR.
- deploy: только отдельный deploy TASK с backup, health checks и rollback.

## Обязательные правила

- Не менять несвязанные файлы и не выполнять общий рефакторинг.
- Не менять public contracts, JSONL schema или SQLite schema без требования.
- Не удалять тесты, не ослаблять assertions и не менять ожидаемый результат ради green suite.
- Не добавлять зависимости без необходимости.
- Не хранить secrets в Git, fixtures, TASK, PLAN, PR или handoff.
- Не логировать Access Token, Client Secret, cookie, Authorization header и пароль SSID.
- MAC в технических журналах не маскировать.
- Проверять HTTP status и Omada JSON errorCode раздельно.
- Использовать существующие app/config.py → app/settings.py:get_settings().
- Использовать общий OmadaProvider и не создавать второй provider, token manager или механизм авторизации без утверждённого change intent.
- CAPPORT обязан входить в общий PortalClientContext → AuthSessionManager → AuthWorker flow.
- Независимый background component работает fail-open.
- Не использовать Flask current_app из фонового thread.
- Worker создаётся в composition root, не при import.
- Не менять Alloy, Loki, Grafana, production systemd или reverse proxy без отдельного TASK.
- Сначала targeted tests, затем full gate.
- Не исправлять несвязанные падения full suite.
- Не утверждать, что test, commit, push, PR или deploy выполнен, если это не так.
- Merge, force push и production deploy — owner-only без прямого разрешения.

## Архитектурные инварианты

- run.py — process entrypoint и верхнеуровневый lifecycle/composition root.
- app/web/web.py:create_app() — Flask composition factory.
- Один OmadaProvider передаётся в web/auth и зависимые компоненты процесса.
- AuthSessionManager и auth executor находятся в памяти процесса; production предполагает один WSGI process.
- Visitor Registry читает visitor snapshot journal и не обращается к Omada.
- Ошибка независимого operational component не должна ломать основной portal authorization flow.

## Проверки

Targeted command определяет TASK. Полный gate:

    python -m pytest -q -rs
    PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
    git diff --check

Если environment запрещает проверку, укажи команду, причину и owner action.

## Stop conditions

Останови затронутую часть, если:

- TASK противоречит архитектуре или фактическому контракту;
- endpoint не подтверждён;
- нужен secret или запрещённый файл;
- требуется инфраструктура вне scope;
- безопасное поведение не определено;
- нужен отсутствующий ADR;
- требуется необратимое repository action без разрешения;
- production operation запрошена без deploy TASK.

Независимые безопасные части продолжай.

## Handoff

Верни: цель и результат; изменённые файлы; targeted/full checks с числами passed, skipped и failed; не выполненные проверки; риски; repository actions, выполненные фактически; owner actions; Agent execution summary.
