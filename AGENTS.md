# CaptivPortal: правила для coding agents

Status: current
Updated: 2026-08-29
Central Lab governance effective: 2026-08-27

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
- Coder/исполнитель выполняет минимальные automated tests непосредственно в пределах текущего TASK / изменяемого модуля: focused tests, новые regression cases этого изменения и релевантные static/syntax checks; эти targeted-прогоны можно повторять в процессе разработки.
- Coder может создавать/изменять automated tests только в пределах реализуемого изменения и не расширяет execution на unrelated modules, cross-module regression, broader regression или full repository suite.
- Если proof требует test вне TASK/module boundary, Coder либо сообщает Owner/Tech Lead точный дополнительный test/gate для внешнего запуска, либо подготавливает/реализует такой test, но не запускает его.
- `C:\CaptivPortal-Lab` и официальный Central Lab full repository regression cycle контролируются Owner / Tech Lead: Tech Lead определяет exact artifact, commands/gate procedure и acceptance criteria; Owner физически управляет Lab и запускает официальный regression; Owner + Tech Lead анализируют evidence и выдают PASS / FAIL / return-to-coder.
- Coder не запускает официальный Central Lab gate, не выдаёт официальный PASS/FAIL и не считает собственные tests repository regression gate. По явному поручению Owner/Tech Lead Coder может только подготовить candidate/artifacts или пропатчить указанную Lab working directory; после подготовки цикл возвращается Owner/Tech Lead до запуска gate.
- Windows Local Gate не заменяет отдельный Linux/production-compatible gate, когда такой gate требуется release/deploy contract.
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

Targeted commands для Coder/исполнителя определяет TASK. Они ограничены изменяемым модулем/TASK scope и проверяют непосредственные контракты, новые regression-сценарии этого изменения и необходимые static/syntax checks.

Coder обязан в handoff перечислить:
- новые test files;
- изменённые существующие test files;
- exact focused/minimal command;
- фактический результат разрешённого focused запуска.

Cross-module/broader/full execution не относится к Coder local self-check. Если такой test нужен, Coder передаёт точную необходимость Owner/Tech Lead либо подготавливает test без запуска.

После каждого принятого нового TASK / panel / module / API / read-service Tech Lead обязан заново пересмотреть relevant targeted Central Lab regression block и текущий repository test set. Старый targeted command не становится canonical автоматически только потому, что раньше был корректен.

Full Central Lab runner меняется только при изменении самого gate/compatibility/environment contract. Обычный новый pytest file, который автоматически попадает в full discovery, не требует механической правки runner.

Официальный Central Lab cycle для exact artifact направляет Tech Lead, физически запускает Owner, а PASS/FAIL принимает Owner + Tech Lead.

### Windows Central Lab current environment

Detailed source of truth: `docs/testing.md`.

Current verified 2026-08-29:
- repository: `C:\CaptivPortal-UI-Preview`;
- support directory: `C:\CaptivPortal-Lab`;
- manual pytest interpreter: `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`;
- manual pytest uses explicit cleaned `C:\CaptivPortal-Lab\tmp\<run>` via `--basetemp`;
- current verified full runner: `C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd`.

Permanent anti-drift rule:

```text
documented gate version
!=
automatically current gate version
```

Before every official full gate Owner / Tech Lead verifies the actual approved runner against:
- exact candidate;
- exact baseline;
- known compatibility baseline;
- current test set;
- TASK-specific/cross-surface acceptance invariants.

Infrastructure failure before test logic (wrong interpreter, missing pytest, inaccessible temp directory, malformed Lab environment, dirty-candidate refusal) is not automatically an implementation regression. Restore the canonical Lab environment and repeat the same scope before classifying product failure.

Official full gate requires a clean immutable candidate. A local detached `LAB ONLY` candidate commit is permitted for Central Lab acceptance; it is not pushed, PR'd, merged or deployed.

Если перед production требуется Linux/full production-compatible gate, он выполняется отдельно по deploy/release contract. Windows gate его не заменяет.

## Повторное использование результатов тестирования

Reviewer / Tech Lead не должен повторно запускать идентичные targeted tests только для формального подтверждения результата исполнителя.

Результаты исполнителя принимаются как targeted test evidence, если handoff содержит:

- exact baseline;
- exact patch SHA256 или commit SHA;
- точную команду;
- Python/Node и операционную среду;
- passed/skipped/failed;
- классификацию известных падений;
- подтверждение применимости exact patch.

Перед повторным targeted-прогоном reviewer обязан определить, какую новую информацию даст этот запуск.

Повторный targeted-прогон разрешён только когда он:

1. проверяет новый риск или сценарий, не проверенный исполнителем;
2. запускает пропущенные platform-specific тесты в другой среде;
3. подтверждает exact-artifact integration или обязательный independent gate;
4. расследует неполный, противоречивый или сомнительный результат;
5. прямо требуется утверждённым TASK, deploy/production gate или отдельной owner-командой.

Cross-module/broader/full repository suite и официальный acceptance выполняются Owner/Tech Lead/Central Lab, а не Coder. После успешного gate на неизменённом exact artifact его не повторяют без новой причины. Отдельный Linux production-compatible gate не считается дублированием, когда он требуется как platform-specific release acceptance.

Reviewer не должен утверждать, что лично выполнил targeted tests, если он использует результаты исполнителя.

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

Верни: цель и результат; изменённые файлы; TASK-scoped targeted checks с числами passed, skipped и failed; Central Lab/full evidence reference или pending/not-required; отдельный Linux gate evidence если применимо; не выполненные проверки; риски; repository actions, выполненные фактически; owner actions; Agent execution summary.
