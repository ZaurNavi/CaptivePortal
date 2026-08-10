# Testing

Status: current
Updated: 2026-08-10
Runtime baseline: main `ab776af3fc58dc090e17ecd20534abddc1f33ad3`

## Ответственность

Каждый TASK указывает ровно одно значение: `agent`, `owner`, `shared` или `not-applicable`. Нельзя автоматически перекладывать тесты на агента, если owner назначен явно.

## Порядок

1. Targeted tests для изменённого контракта.
2. Full suite.
3. Compile gate.
4. Whitespace gate.

Full gate:

    python -m pytest -q -rs
    PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
    git diff --check

`pytest.ini` задаёт единственный test root `tests/`. В current main находятся 40 файлов `test_*.py`; штатных test modules вне `tests/` нет. Явный root защищает discovery от случайных operational/research scripts.

## Stable targeted groups

    python -m pytest tests/test_auth_retry.py tests/test_portal_entry.py -q --tb=short
    python -m pytest tests/test_capport_routes.py tests/test_capport_service.py tests/test_capport_discovery_frontend.py -q --tb=short
    python -m pytest tests/test_portal_counter.py -q --tb=short
    python -m pytest tests/test_public_traffic.py tests/test_public_traffic_frontend.py -q --tb=short
    python -m pytest tests/visitor_registry -q --tb=short
    python -m pytest tests/integrations/omada -q --tb=short
    python -m pytest tests/pending_sessions -q --tb=short
    python -m pytest tests/test_omada_configuration.py -q --tb=short

TASK выбирает минимально достаточную группу; не запускает все группы как targeted.

## Pending Session Cleaner coverage

`tests/pending_sessions/` содержит 11 test files и 53 test functions. Покрываются:

- provider contracts и безопасная классификация response;
- shared token-cache concurrency/failure;
- focused race, где Cleaner recovery не инвалидирует свежий token другого thread;
- strict config и disabled/unavailable factory modes;
- pagination, incomplete inventory и duplicate MAC;
- classification, local protection и fresh preflight;
- action limits, audit-before-action, reconnect и verification;
- journal/telemetry и end-to-end fake-provider pipeline.

Это test inventory, а не утверждение о результате последнего запуска. Actual report всегда содержит точную команду и числа.

## CAPPORT/frontend coverage

Текущие tests проверяют bounded discovery contract, последовательные same-page `fetch()` requests, переход в общий AuthSession flow, строгий JSON negotiation, монотонный progress, post-`AUTHORIZED` close/revalidation и отсутствие reload-loop. Node-based frontend scenarios не заменяют live acceptance поведения Android captive WebView.

## Evidence levels

### Last known green historical baseline

Ранее зафиксировано:

    894 passed, 10 skipped, 0 failed

Этот результат относится к состоянию до PR #34–#37 и не является release verdict для current main.

### Intermediate non-green evidence

После TASK-DEBT-01 был зафиксирован прогон `924 passed, 2 failed`. Он предшествует финальным frontend PR #35–#37; два падения были связаны с frontend retry reconciliation и AF_UNIX test в ограниченной среде. Этот результат хранится как history, а не как current gate.

### Current main release gate

Для exact `main@ab776af` полный Linux `pytest` с `0 failed` на момент актуализации не подтверждён. Попытка TASK-KB-UPDATE-01 в доступной Linux/Python 3.12 среде не стартовала: модуль `pytest` отсутствует. Это environment limitation, не product failure.

Следовательно P0 release gate остаётся OPEN. До получения фактических чисел запрещено писать, что full suite на `ab776af` green.

## Reporting

Указывать точную команду, passed/skipped/failed и релевантный короткий traceback. Environment limitation отделять от product defect. Несвязанный full-suite failure не исправлять; зарегистрировать owner action.

Если environment не содержит dependencies и их установка запрещена, тест нельзя объявлять passed. Выполните доступные compile/static gates и повторите pytest в нормальном project/Linux environment.

## Production gate

Feature activation требует отдельного Linux gate на целевом Python, filesystem, permissions и service topology. Локальный green suite, Node frontend scenarios и owner-confirmed live behavior не заменяют друг друга.

Для current release остаются отдельными доказательствами:

1. полный Linux gate exact main;
2. live Android captive-window acceptance;
3. post-restart health background components.
