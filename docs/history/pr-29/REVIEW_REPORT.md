# CaptivPortal knowledge base — пакет на согласование

Status: ready for Architect and Tech Lead review  
Prepared: 2026-08-03  
Repository snapshot: main a44b3128d72a5ce17529db0842580571023242ee

## Результат

Подготовлен полный макет базы знаний и инструкций для coding agents вне рабочего репозитория. Рабочая копия CaptivePortal остаётся clean; branch, commit, push и PR не создавались.

Пакет решает две задачи:

1. хранит актуальную архитектурную и эксплуатационную истину;
2. сокращает AI context через короткую точку входа, TASK-driven reading и path-specific instructions.

## Что входит

- universal AGENTS.md, 118 строк;
- GitHub Copilot adapter и 7 path-specific instruction files;
- architecture, inventory, module index, tests, logging, deployment, security и Omada API;
- 11 module contracts по фактической структуре main;
- agent workflow, TASK contract, handoff, repository permissions и model selection;
- TASK, PLAN и ADR templates;
- PR template;
- archive/migration plan без удаления исторических материалов;
- один check script и proposed pytest discovery config;
- два pilot reports и explicit cross-agent limitation;
- точечное предложение для README.md и README_RU.md.

## Источник фактов

Инвентаризация сделана по коду commit a44b3128, существующим README/docs, тестам и переданным live research reports. Chat history использовалась только для внешнего статуса работ и не подменяет main.

## Архитектурная истина

- Единый flow: Omada External Portal или CAPPORT login → PortalClientContext → AuthSessionManager → AuthWorker → shared OmadaProvider.
- CAPPORT не имеет отдельного authorization mechanism.
- run.py — process lifecycle/composition root; create_app() — Flask composition factory.
- Один OmadaProvider на process; current token lifecycle — token per request.
- Auth sessions/workers in-memory; topology single-process.
- Visitor Registry не обращается к Omada.
- Cleaner не читает Visitor Registry database.
- Background operational modules fail-open.
- Application code/events отделены от Alloy, Loki, Grafana, systemd и deployment.

## Статусы модулей в снимке

| Модуль | Статус |
|---|---|
| Authorization, portal entry, CAPPORT | active |
| Auth telemetry, portal counter, public traffic | active |
| Authorized snapshot collector | implemented-disabled |
| Visitor Device Registry | implemented-disabled |
| Webhook receiver/normalizer | implemented-disabled |
| Pending Client Session Cleaner | development; final code отсутствует в этом main |

После merge работы кодера main будет заново инвентаризирован. Cleaner не будет повышен в status по обещанию или branch context — только по merged code, tests, flag и lifecycle.

## Temporary cleanup artifacts

По указанию owner следующие файлы не удаляются, не переименовываются и не архивируются:

- omada_pending_cleanup_test.py;
- tools/omada_pending_cleanup_test.py;
- tools/pending_session_probe.py;
- tools/pending_session_probe_README.md.

Они отмечены как temporary research artifacts и не являются final Cleaner contract.

## Решения, требующие подтверждения

### 1. Test discovery

Рекомендация: добавить pytest.ini с testpaths = tests. Это не меняет временные scripts, но исключает их из штатного discovery. Альтернатива — документировать full gate как python -m pytest tests -q -rs и отказаться от exact команды ТЗ.

### 2. Дополнительные module docs

Кроме минимального списка ТЗ добавлены portal-entry, auth-telemetry, public-traffic-counter и webhook-receiver. Иначе module index не описывал бы фактический main и агенты снова искали бы архитектуру в source.

### 3. Язык

Внутренняя база и universal rules — на русском с неизменёнными code identifiers. Platform adapter изолирован в .github. Это минимизирует двуязычное дублирование.

### 4. Existing docs

Предлагается перенести устойчивые контракты в docs/modules/, а текущие подробные документы архивировать с superseded header. Никакого удаления в этом PR.

### 5. Public README

README остаётся public overview. Добавляется короткая навигация в knowledge base; stale Repository Structure сокращается до ссылки на inventory.

### 6. Security finding

В app/config.py присутствуют похожие на реальные credentials. Значения не воспроизведены. Нужен отдельный срочный security TASK: rotation, environment-based config и согласованная очистка history. Knowledge-base PR business code не меняет.

## Baseline verification

| Проверка | Факт |
|---|---|
| Working repository status | clean |
| python -m pytest -q -rs | collection error: два временных файла с одним basename |
| python -m pytest tests -q -rs | 798 passed, 1 sandbox-only AF_UNIX PermissionError |
| compileall app | passed, pycache направлен в /tmp |
| git diff --check | passed |
| Secret-like literals в review package | не найдены |
| AGENTS.md limit | 118 из 250 строк |
| Copilot adapter limit | 21 из 200 строк |

Full suite должен быть повторён в normal Linux environment после approved changes и merge Cleaner.

## Pilot status

- Simple documentation implementation: выполнен на review package, repo writes запрещены.
- Complex Cleaner planning-only: выполнен; shared provider, reconnect-only, protections, audit, fail-open и infrastructure boundary распознаны.
- Cross-agent universality: проверен один тип исполнителя, ChatGPT/Codex. GitHub Copilot не запускался до утверждения и появления instructions в repository. Ограничение явно документировано; final rerun обязателен.

## Что произойдёт только после approval

1. Refresh origin/main после merge кодера.
2. Повторная инвентаризация и diff статусов, особенно Cleaner.
3. Корректировка предложенных файлов.
4. Создание отдельной feature branch.
5. Добавление только утверждённых docs/instructions/tooling.
6. Targeted/full checks в нормальном окружении.
7. Два пилота и cross-agent verification.
8. Draft PR с фактическими результатами.
9. Tech Lead review и Architect confirmation.

Merge и production deployment в эту задачу не входят без отдельного разрешения.

## Approval checklist

- [ ] Architect подтверждает architecture.md и границы модулей.
- [ ] Tech Lead подтверждает AGENTS/workflow/TASK/handoff.
- [ ] Tech Lead выбирает pytest.ini либо явный tests/ command.
- [ ] Owner подтверждает archive migration и README changes.
- [ ] Owner подтверждает, что temporary cleanup artifacts остаются без изменений.
- [ ] После merge Cleaner разрешён refresh main.
- [ ] После финального review разрешены branch и Draft PR.

Подробное состояние 58 критериев: ACCEPTANCE_MATRIX.md.

