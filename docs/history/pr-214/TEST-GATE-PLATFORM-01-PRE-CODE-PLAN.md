# TEST-GATE-PLATFORM-01 — PRE-CODE PLAN

Статус: PLAN FOR TECH LEAD APPROVAL ONLY. Implementation/test execution не выполнены.

## 1. Замороженные границы

- NI-03 baseline: `51deead342bd821b5c46fb75a7ceef37bef63e7c`.
- NI-03 accepted candidate tree: `8ed141f0184d65e6fd8d4d3a06adadc5940497e3`.
- Полный accepted patch: `23a545ac1e915bc16fe94185c6ff0fdd1db60ed56b11cbdd60e7d59739f61b20`, 102251 bytes.
- Рабочий candidate `C:\CaptivPortal-Lab\coder-dti-ni-03` остаётся dirty/uncommitted. Все 24 изменённых пути сверены по Git blob identities с accepted tree; scope совпадает.
- Существующий `C:\CaptivPortal-Lab\lab-test-v7-strict.cmd` не изменён. SHA256: `45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77`.
- Production source, NI-03 source, service/configuration, production DB и deployment — вне scope.
- Никаких commits, fetch, push, PR, merge, gate/test runs в этом PRE-CODE round.

## 2. Основание плана: прочитанные, а не заново выполненные результаты

1. V7 log `C:\CaptivPortal-Lab\logs\lab-test-v7-strict-20261010-030525-DETACHED.log`: 187 failed, 6525 passed, 34 skipped; HEAD `57b35ee7d45d2e780230fae7de48071b9645b061`, origin/main `51deead342bd821b5c46fb75a7ceef37bef63e7c`. Tech Lead подтвердил baseline presence всех failures и отсутствие новых NI-03 P0/P1.
2. Windows diagnostic `C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-03-LEAD21-BASELINE-FULL.xml`: 2219 tests, 190 failures, 4 skips. Это отдельный запуск/набор, не V7 187. В нём есть ещё три Controller Stage-4 failures; не включать их автоматически в scope и не подменять ими V7 result.
3. Причины NI failures в Windows diagnostic: `os.pread`, `os.O_NONBLOCK`, `fcntl`, rename/unlink открытого файла. Это POSIX execution dependencies, а не повод менять production NI source или эмулировать Unix на Windows.
4. Linux full evidence `TASK-DTI-NI-03-LEAD21-LINUX-FULL.xml`: 18 failures. Повтор точных 18 node IDs на baseline и candidate (`TASK-DTI-NI-03-LINUX-BASELINE-18.xml`, `TASK-DTI-NI-03-LINUX-CANDIDATE-18.xml`) даёт одинаково 8 failures / 10 passes.
5. Эти 10 startup failures поэтому order/environment-sensitive, не доказанные постоянные baseline defects. Не превращать full Linux result в PASS по успешному отдельному повтору.
6. Windows runtime metadata прочитана без тестов: Python 3.10.11, SQLite 3.40.1. Linux SQLite identity не зафиксирована в использованных summary evidence; её необходимо отдельно зафиксировать в будущей Lab preflight.

## 3. Platform routing без потери coverage

Предлагается внешний pytest plugin и закрытый node-ID manifest. Существующий V7 runner сохраняется byte-identical. Plugin подключается только явно одобренным внешним launcher после отдельного approval; применение plugin меняет execution profile, поэтому такой результат обозначается **V7 strict / approved platform profile**, а не выдаётся за неизменённый исторический invocation.

### Правила manifest

- Каждый POSIX case имеет точный параметризованный node ID, конкретную OS-причину, обязательный Linux counterpart с тем же ID и ссылку на source/evidence. Никаких wildcard `tests/network_metadata/**`, автоматического переноса всех FAIL, exception-driven skip, `--deselect`, xfail или WARN allowlist.
- На Windows только утверждённые POSIX cases получают прозрачный статус platform transfer / skip с manifest reason. Они остаются в collected inventory, не исчезают из gate accounting.
- На Linux каждый transferred case обязан реально исполниться и PASS. Skip, missing node ID, collection error или отсутствие POSIX prerequisites блокируют composite acceptance. Windows transfer сам по себе не PASS.
- Остальные Windows-compatible тесты выполняются normally strict. Config/canonical/normalizer/schema/argument tests не переносятся лишь потому, что находятся в NI module.
- Уже существующие POSIX skips (permissions, symlinks, FIFO, Unix sockets, WAL/capacity) включаются в тот же coverage ledger и требуют Linux execution. Opt-in performance test учитывается отдельно по действующему gate contract, не получает новую waiver.
- Не подменять `pread`, `fcntl`, memory/storage checks и production methods тестовыми always-success реализациями.
- Все неожиданные skip/deselect/xfail/xpass и неучтённые изменения collection inventory являются gate defect, а не зелёным результатом.

Точный manifest составляется после approval из collection inventories и causal source review; число 186 не является постоянной invariant и не служит правилом классификации. Этот PRE-CODE round collection не выполняет.

### Первичный POSIX-review scope (read/classification only)

`tests/network_metadata/test_capacity.py`, `test_checkpoint_crash.py`, `test_health.py`, `test_privacy.py`, `test_retention.py`, `test_service.py`; POSIX-dependent node IDs в `test_repository.py`, `test_read_service.py`, `test_source.py`, `test_cli.py`; `tests/network_metadata_projection/test_projection_source.py` и уже маркированные `test_capacity_config.py`.

Для примера: `test_cli.py` содержит Windows-compatible disabled/configuration cases и POSIX writer-lock cases. Module-level blanket skip запрещён. Shared `tests/network_metadata/__init__.py` не изменять для обхода реального POSIX storage path.

## 4. Шесть V7 strict cases — непрерывная защита

Следующие IDs должны присутствовать и реально PASS на Windows, без platform exception, skip/deselect/xfail/WARN:

```
tests/analytics/test_current_traffic.py::test_sql_integrity_aggregates_reject_corrupt_rate_and_null_values[wired_download_mbps-inf-bad_rate_count]
tests/test_auth_retry_frontend.py::test_lost_retry_response_reconciles_active_run
tests/visitor_registry/test_device_registry_worker.py::test_long_full_audit_runs_in_worker_and_does_not_block_start
tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[ready]
tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[stopping]
tests/admin_web/test_home_health.py::test_unavailable_analytics_is_one_component_not_health_503
```

Plugin/aggregator проверяет protected set до исполнения и по actual outcomes. Попытка добавить protected ID в platform manifest, пропустить его или понизить FAIL → отклонение gate. Эти test files не требуют изменений.

## 5. Раздельная классификация baseline failures

| Класс | Exact files / cases | Предлагаемое действие после approval | Не разрешено |
|---|---|---|---|
| Home ordering | `tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled` | Tech Lead подтверждает accepted UI order. Текущий шаблон размещает `home-activity`, затем heading `aps-now-title`, затем внутренний `home-ap-24h`; тест ждёт другой порядок. Исправить только stale test expectation согласно подтверждённому UI contract, сохраняя строгую проверку порядка, уникальности hooks и feature gating. Если desired order не подтверждён — HOLD этого пункта. | Перестановка production DOM, удаление ordering assertion, skip/xfail. |
| CAPPORT / External Portal probe configuration | `tests/device_fingerprint_portal/test_client_hints_probe.py` (privacy canaries), `tests/test_capport_routes.py` (2 probe cases), `tests/test_proxy_headers.py` (2 probe cases) | Заменить только synthetic `C:/explicit/probe.jsonl` на абсолютный disposable path из `tmp_path` в этих пяти случаях. На Linux Windows path не абсолютный, поэтому canonical ProbeConfig отвергается до substantive assertions. Enabled config, recorder, TTL/capacity и все privacy/Auth/session/headers assertions сохранить. | Ослабление production path validator, отключение probe, изменение canaries или ожидаемых результатов. |
| SQLite EXPLAIN planner | `tests/analytics/test_historical_traffic_peak.py::test_peak_projection_reuses_one_materialized_requested_range_validation`; `tests/analytics/test_historical_traffic_statistics.py::test_combined_projection_materializes_one_expensive_validation_path` | Сначала зафиксировать SQLite version/compile options на обоих Lab. Предпочтительно квалифицировать и pin одинаковый reference SQLite в изолированных test environments, сохранив обе exact assertions. Windows 3.40.1 — исходный reference candidate, не автоматическая гарантия Linux PASS. Повторный Owner proof должен подтвердить план и результат. | Заменить `== 1` на `>= 0`, удалить materialization check, менять SQL/production dependency ради green. |

SQLite требует двух различимых claims: reference-planner contract и совместимость native production-like Linux SQLite. Pin не может скрыть failing mandatory native contract. Если freeze требует exact physical planner shape на native версии, а она его не даёт, это отдельный Tech Lead contract disposition; до него HOLD, не переписывать тест самостоятельно.

### Linux full-only startup failures

Read-only diagnostic scope: `tests/observations/test_runtime.py`, `tests/test_public_traffic.py`, `tests/visitor_registry/test_snapshot_runtime.py`, `tests/test_artifact_identity.py`, production `app/artifact_identity.py` и `run.py` только для проверки границы. Full evidence содержит `captivportal_artifact_identity_startup_failed`, отдельные baseline/candidate repeats проходят.

Будущая Owner verification должна установить imported source origin, sys.path, environment leakage, HEAD/tree/dirty state до и после full run и перед этими cases. Не мокать artifact identity globally, не ослаблять fail-closed cleanliness. Test edit в этих файлах не входит в первоначальный repair scope: только отдельное разрешение после exact root cause. Никакого production fix.

## 6. Exact proposed implementation files

### A. Новая внешняя инфраструктура, требует отдельного approval

Под `C:\CaptivPortal-Lab\test-gate-platform-01\`:

1. `platform-manifest-v1.json` — closed exact node-ID routing и protected-six inventory.
2. `pytest_platform_contract.py` — collection/outcome accounting, Windows approved transfer, Linux mandatory execution, protected-six fail-closed checks.
3. `gate-preflight-v1.py` — environment/toolchain/SQLite/plugin/import-path/repo identity snapshot; не изменяет repo и ничего не устанавливает silently.
4. `compare-gate-evidence-v1.py` — baseline/candidate same-environment differential и composite coverage ledger. Known FAIL остаётся FAIL; differential PASS хранится отдельно.
5. `test_gate_platform_contract.py` — focused self-tests инфраструктуры: unknown/protected skip rejected, missing Linux counterpart rejected, native FAIL preserved, collection drift rejected.
6. `run-platform-gates-v1.cmd` — approved Windows invocation wrapper; существующий V7 runner не перезаписывается.
7. `run-linux-platform-gates-v1.sh` — Owner launcher в dedicated WSL/Linux Lab, без production access и без unbounded destructive cleanup.
8. `gate-environment-lock-v1.json` — reviewed versions/build identities, dependency inventory и allowed sanitized test environment.

Новые launchers/plugins не будут созданы до approval. `C:\CaptivPortal-Lab\lab-test-v7-strict.cmd` — READ-ONLY.

### B. Test-only fixture repairs в отдельном infrastructure worktree

Предлагаемые существующие файлы, и только они:

```
tests/admin_web/test_home_traffic.py
tests/device_fingerprint_portal/test_client_hints_probe.py
tests/test_capport_routes.py
tests/test_proxy_headers.py
```

Home edit зависит от explicit accepted-order confirmation. Analytics planner files первоначально READ-ONLY; никакого assertion rewrite. Global repository `conftest.py`, pytest.ini и production source не требуют изменения выбранной external-plugin схемой.

Для документации нового профиля после approval: `docs/testing.md`, `docs/testing-environments.md`; только platform routing, ownership, evidence accounting и protected-six contract. Не изменять текущие документы в этом round.

## 7. Exact-artifact / reproducibility protocol

1. NI-03 worktree и accepted patch сохраняются неизменными. Не делать commit в них для test-infrastructure task.
2. Tech Lead разрешает отдельный infrastructure worktree от exact baseline и фиксирует independent test-infrastructure revision/hash. Source fixtures не накладывать скрыто на NI-03 candidate.
3. Source test corrections создают **другой full Git tree**. Нельзя утверждать, что исправленная suite прошла на прежнем exact tree `8ed141f...`. Для нового baseline/candidate pair требуется явная Tech Lead disposition: одинаковый infrastructure delta + исходный NI-03 delta, новые exact trees, unchanged production blob mapping. Пока она не выдана — исходная NI-03 publication HOLD сохраняется.
4. До source fixture corrections external platform profile может запускаться на исходных immutable baseline/candidate trees; результаты Home/probe/planner остаются FAIL и показываются отдельно. Это диагностика/coverage routing, не финальное acceptance.
5. Для каждого paired run — clean native worktrees, отдельные disposable tmp/cache/output, одинаковый interpreter/dependency/Node/SQLite profile, явный import origin из соответствующего worktree, sanitized environment. Не использовать пользовательские enabled-feature/secrets/probe переменные.
6. Retain source commit/tree, suite/manifest/plugin/runner hashes, tool versions/SQLite compile options, command/options, collected IDs, per-node outcomes/skip reasons, JUnit/log SHA256, HEAD/tree/status до/после. Old evidence immutable.
7. Не давать green gate по одинаковым двум failures: baseline/candidate differential и strict absolute results — разные поля.

## 8. Acceptance matrix — исполняет Owner / принимает Tech Lead

| Gate | Baseline | Candidate | Обязательное условие |
|---|---|---|---|
| Infrastructure self-tests | same frozen infrastructure | same | Fail/unknown-skip/protected-skip/missing-Linux negative cases реально отвергаются; no production input. |
| Windows strict compatible profile | exact approved baseline tree | exact approved candidate tree | 0 failed / 0 errors / 0 deselected / 0 unexpected skips; все шесть protected cases executed PASS. |
| Linux/POSIX mandatory lane + full compatible suite | exact approved baseline tree | exact approved candidate tree | Каждый transferred case и existing mandatory POSIX case executed PASS; real writer-lock, rotation, crash, WAL/capacity/reader-pressure/permissions checks, без emulation. |
| Five probe fixture cases | Windows + Linux | Windows + Linux | Canonical enabled config проходит; все исходные privacy/session/Header assertions PASS. |
| Home ordering | Windows + Linux | Windows + Linux | Exact approved layout order + все текущие hook/gating assertions PASS. Нет layout source change. |
| SQLite reference planner | pinned approved SQLite build | same | Две exact planner assertions и semantic assertions PASS. Версии/compile options recorded. |
| Native Linux compatibility | production-like Lab version | same | Все mandatory native assertions PASS или explicit HOLD. Reference pin не заменяет native proof. |
| Full-order startup reproducibility | clean full suite | clean full suite | 10 full-only startup cases PASS в full ordering; отдельный повтор не заменяет этот proof. |
| Baseline/candidate differential | full node outcomes | full node outcomes | 0 new failures; no unexplained collection/skip delta; every Linux transfer accounted. |
| Artifact immutability | source + suite + runner hashes before/after | same | Exact trees/production blobs/source origins unchanged; clean state; no generated evidence in repo. |

Strict PASS требует нулевых unresolved mandatory failures на обоих обязательных контурах. Если baseline ещё FAIL, допускается только status `BASELINE_BLOCKED / DIFFERENTIAL_NO_NEW_FAILURES`, не `STRICT_PASS` и не release authorization.

## 9. Риски / approval points

- Риск потерять Linux coverage при Windows skip: closed manifest + required per-node Linux PASS + protected-six guard.
- Риск скрыть production regression fixture/SQLite normalization: сохранять assertions, сначала проверить canonical config/UI authority, native and reference planner evidence раздельно.
- Риск full-order pollution/dirty artifact: отдельные worktrees/temp, source-origin checks; 10 startup failures остаются unresolved до full-run proof.
- Риск изменить accepted NI-03 tree тестовой инфраструктурой: не трогать NI worktree; новые tree identities требуют отдельного Tech Lead reconciliation.
- Перед implementation нужны approvals: exact external infrastructure file scope/platform profile; four test fixture file scope и Home ordering authority; SQLite environment strategy; new baseline/candidate test-infrastructure lineage.

## 10. Текущий handoff

```
TASK=TEST-GATE-PLATFORM-01
MODE=PRE_CODE_PLAN_ONLY
PLAN_STATUS=READY_FOR_TECH_LEAD_REVIEW
NI03_SOURCE_MODIFIED=NO
NI03_ACCEPTED_TREE_PRESERVED=YES
NI03_CANDIDATE_TREE=8ed141f0184d65e6fd8d4d3a06adadc5940497e3
LAB_RUNNER_MODIFIED=NO
TEST_INFRASTRUCTURE_IMPLEMENTED=NO
TESTS_RUN=NO
GATES_RUN=NO
COMMIT=HOLD
PUSH=HOLD
PR=HOLD
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
NEXT_ACTION=TECH_LEAD_PLAN_APPROVAL_AND_EXACT_SCOPE_AUTHORIZATION
```
