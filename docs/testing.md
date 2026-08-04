# Testing

Status: current
Updated: 2026-08-04

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

`pytest.ini` задаёт единственный test root `tests/`. В current main штатных test modules вне `tests/` нет; временные pending-session probe scripts удалены PR #28. Явный root защищает discovery от случайных operational/research scripts в будущем.

## Stable targeted groups

    python -m pytest tests/test_auth_retry.py tests/test_portal_entry.py -q --tb=short
    python -m pytest tests/test_capport_routes.py tests/test_capport_service.py -q --tb=short
    python -m pytest tests/test_portal_counter.py -q --tb=short
    python -m pytest tests/test_public_traffic.py tests/test_public_traffic_frontend.py -q --tb=short
    python -m pytest tests/visitor_registry -q --tb=short
    python -m pytest tests/integrations/omada -q --tb=short
    python -m pytest tests/pending_sessions -q --tb=short

TASK выбирает минимально достаточную группу; не запускает все группы как targeted.

## Pending Session Cleaner coverage

`tests/pending_sessions/` содержит 11 test files и 52 test functions. Покрываются:

- provider contracts и безопасная классификация response;
- shared token-cache concurrency/failure;
- strict config и disabled/unavailable factory modes;
- pagination, incomplete inventory и duplicate MAC;
- classification, local protection и fresh preflight;
- action limits, audit-before-action, reconnect и verification;
- journal/telemetry и end-to-end fake-provider pipeline.

Known gap baseline `227ebe9`: нет focused test, где AuthWorker публикует свежий token между compare-and-invalidate reconnect adapter и повторной no-argument invalidation Cleaner recovery.

Это test inventory, а не утверждение о результате последнего запуска. Actual report всегда содержит точную команду и числа.

## Reporting

Указывать точную команду, passed/skipped/failed и релевантный короткий traceback. Environment limitation отделять от product defect. Несвязанный full-suite failure не исправлять; зарегистрировать owner action.

Если environment не содержит dependencies и их установка запрещена, тест нельзя объявлять passed. Выполните доступные compile/static gates и повторите pytest в нормальном project/Linux environment.

## Production gate

Feature activation требует отдельного Linux gate на целевом Python, filesystem, permissions и service topology. Локальный green suite или owner-confirmed live behavior не заменяют друг друга: нужны оба доказательства.

## Integration evidence 2026-08-04

- runtime baseline: main `227ebe9`;
- temporary probe artifacts отсутствуют;
- `PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app`: passed;
- `git diff --check`: passed before knowledge-base integration;
- isolated integration Python: pytest/runtime packages unavailable, network install blocked; normal project-environment pytest rerun pending;
- GitHub: для merged Cleaner commits не обнаружены attached Actions workflow runs/status checks.
