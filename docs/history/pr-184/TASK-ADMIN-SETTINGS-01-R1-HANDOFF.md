# TASK-ADMIN-SETTINGS-01 — first implementation handoff

STATUS = IMPLEMENTED / HOLD FOR TECH LEAD REVIEW AND STARTUP-TEST DISPOSITION

Contract: accepted R1 + binding TL-F1..TL-F5. No acceptance or publication is declared by Coder.

## Identity and isolation

```text
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-01-r1
BASE_HEAD=9af1cb158bfcfcb31d441caf71061c9aa2888b85
BASE_TREE=4850e322a4286880a32dbd995121a85bc85c9e99
HEAD_AFTER_IMPLEMENTATION=9af1cb158bfcfcb31d441caf71061c9aa2888b85
HEAD_TREE_AFTER_IMPLEMENTATION=4850e322a4286880a32dbd995121a85bc85c9e99
INITIAL_WORKTREE_STATE=CLEAN
WORKTREE_STATE=DIRTY — intentional uncommitted review candidate
STAGED_CONTENT=NONE
```

The fresh isolated worktree was created directly from the exact accepted baseline. Both HEAD/TREE gates passed before source modification. New files have intent-to-add entries solely to include them in the unified patch; no implementation content is staged for a commit.

The previous UX worktree remains clean at cc456f944125956b19a87d0f8dae90dc33a68aa6 / tree 4850e322a4286880a32dbd995121a85bc85c9e99.

DTI worktree/prototype was not modified. Read-only preservation check: HEAD c8d8d620dfed06caee92a498b891bf2faa37a6a9; tree be3470c378180aa215d527c6de6b686583ae0d79; retained DTI diff SHA256 3287dbf5a28adc3470a5933eeb503b55a6c5a1f5da4de84e305c9d4cc35c14fc.

## Exact new files — 23

```text
app/admin_web/static/settings.js
app/admin_web/templates/admin/settings.html
app/settings_control/__init__.py
app/settings_control/activation.py
app/settings_control/bootstrap.py
app/settings_control/definitions.py
app/settings_control/models.py
app/settings_control/repository.py
app/settings_control/resolver.py
app/settings_control/services.py
app/settings_control/validation.py
tests/admin_web/test_settings_routes.py
tests/admin_web/test_settings_ui.py
tests/settings_control/__init__.py
tests/settings_control/test_activation.py
tests/settings_control/test_bootstrap.py
tests/settings_control/test_definitions.py
tests/settings_control/test_repository.py
tests/settings_control/test_resolver.py
tests/settings_control/test_run_integration.py
tests/settings_control/test_services.py
tests/settings_control/test_validation.py
tests/settings_control/test_web_settings_injection.py
```

## Exact modified files — 13

```text
.env.example
app/admin_web/policy.py
app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/static/admin.css
app/admin_web/templates/admin/base.html
app/config.py
app/settings.py
app/web/web.py
docs/configuration.md
docs/modules/admin-web.md
run.py
tests/visitor_registry/test_snapshot_runtime.py
```

The only existing test-file modification is TL-F4's permitted `settings=settings` factory injection signature/assertion. No other existing test file or `admin.js` was changed.

Aggregate diff: **36 files, 1615 insertions, 22 deletions**.

## Focused verification

Final command (disposable external temp directory):

```text
python -m pytest -q --basetemp=C:/CaptivPortal-Lab/tmp/admin-settings-01-focused-final tests/settings_control tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py
61 passed / 0 failed / 0 skipped
```

## Directly affected existing verification

Final command:

```text
python -m pytest -q --tb=line --basetemp=C:/CaptivPortal-Lab/tmp/admin-settings-01-direct-grouped --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-01-r1/direct-grouped-results.xml tests/admin_web/test_config.py tests/admin_web/test_runtime.py tests/admin_web/test_routes.py tests/admin_web/test_admin_ui_frontend.py tests/admin_web/test_api_routes.py tests/admin_web/test_admin_ui.py tests/admin_web/test_home_activity_frontend.py tests/admin_web/test_home_health_frontend.py tests/admin_web/test_home_ap_24h_frontend.py tests/admin_web/test_home_traffic_frontend.py tests/visitor_registry/test_snapshot_runtime.py tests/test_proxy_headers.py
150 passed / 8 failed / 0 errors / 0 skipped
```

| Existing file | Passed | Failed |
| --- | ---: | ---: |
| tests/admin_web/test_config.py | 47 | 0 |
| tests/admin_web/test_runtime.py | 19 | 0 |
| tests/admin_web/test_routes.py | 28 | 0 |
| tests/admin_web/test_admin_ui_frontend.py | 2 | 0 |
| tests/admin_web/test_api_routes.py | 19 | 0 |
| tests/admin_web/test_admin_ui.py | 10 | 0 |
| tests/admin_web/test_home_activity_frontend.py | 3 | 0 |
| tests/admin_web/test_home_health_frontend.py | 3 | 0 |
| tests/admin_web/test_home_ap_24h_frontend.py | 3 | 0 |
| tests/admin_web/test_home_traffic_frontend.py | 2 | 0 |
| tests/visitor_registry/test_snapshot_runtime.py | 2 | 8 |
| tests/test_proxy_headers.py | 12 | 0 |

All eight failures occur at `run.main()`'s existing artifact-identity guard before Settings bootstrap/composition. `capture_loaded_artifact_identity()` rejects a non-empty Git porcelain status; `run.py` exits with SystemExit(1). First-round COMMIT=NO means this implementation checkout must remain dirty. Neither the production guard nor existing startup assertions were weakened.

Exact failing tests in tests/visitor_registry/test_snapshot_runtime.py:

```text
test_main_wires_one_provider_and_starts_collector_before_app
test_disabled_unavailable_or_raising_collector_does_not_stop_app[False-None]
test_disabled_unavailable_or_raising_collector_does_not_stop_app[False-start_error1]
test_disabled_unavailable_or_raising_registry_does_not_stop_app[False-None]
test_disabled_unavailable_or_raising_registry_does_not_stop_app[False-start_error1]
test_unexpected_registry_factory_failure_remains_fail_open[factory_error0]
test_unexpected_registry_factory_failure_remains_fail_open[factory_error1]
test_background_registry_audit_does_not_delay_app_run
```

Bounded Tech Lead disposition requested: how to verify these existing startup tests on a clean immutable candidate while first-round commit remains forbidden. No change beyond TL-F4 was made to that test file. The new Settings startup tests isolate artifact-identity capture with an explicitly synthetic test stub and exercise actual durable Settings adoption/failure; this does not attest production artifact identity.

Earlier separate direct invocations yielded 110 passed / 8 failed and 40 passed. An interleaved-directory combined invocation yielded 122 passed / 8 failed / 28 setup errors (`admin_app` fixture not found). Grouping all Admin test paths contiguously, without modifying tests or deselecting cases, produced the final 150 passed / 8 failed / 0 errors above. The earlier XML is retained separately as direct-existing-results.xml; no errors were silently discarded.

## Syntax, whitespace and patch integrity

```text
COMPILEALL=PASS
NODE_SYNTAX_CHECK=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
FULL_PROJECT_TESTS=NOT RUN
CENTRAL_LAB=NOT RUN
```

Compile command: external `PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\admin-settings-01-pycache`, then `python -m compileall -q app/settings_control tests/settings_control app/config.py app/settings.py app/web/web.py app/admin_web/policy.py app/admin_web/runtime.py app/admin_web/routes.py run.py tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py tests/visitor_registry/test_snapshot_runtime.py`.

JavaScript: `node --check app/admin_web/static/settings.js`.

## Architecture requirement → implementation mapping

| Requirement | Implementation / evidence |
| --- | --- |
| One exact ordered 12-key writable registry, shared defaults | definitions.py + config.py; test_definitions.py |
| Zero SettingsStore I/O when disabled | bootstrap.py; disabled bootstrap spy/test |
| Explicit environment-origin tracking; override > environment > default | resolver.py; test_resolver.py |
| All-or-nothing primitive and existing semantic validation | validation.py + services.py; test_validation.py/test_services.py |
| Immutable generation history; physical generation 0 | repository.py; test_repository.py |
| BEGIN IMMEDIATE, full overrides, audit, idempotency, CAS | repository.py + services.py; concurrency/rollback/replay tests |
| TL-F1 system/settings_bootstrap | generation-0 initialization and exact physical assertions |
| TL-F2 GLOBAL page, no Site resolution/context/API base | policy.py/routes.py/base.html/settings.html; resolver-forbidden route test |
| TL-F3 dedicated settings.js, admin.js untouched | conditional script loading + UI isolation tests |
| TL-F4 only permitted existing-test injection adjustment | exact two-line diff in test_snapshot_runtime.py |
| TL-F5 strict JSON and full original 12-item replay model | strict pairs/constant parser; route rejection and replay-after-effective-advance tests |
| One immutable startup snapshot; no head reread at adoption | bootstrap.py/run.py/activation.py; exact-G tests |
| Durable adoption precedes serving; write/config failure aborts | activation.py; test_run_integration.py |
| Adoption independent of AdminQueryService/source health | real query-unavailable Settings route fixture still adopts and reads |
| Admin receives no activation capability | SettingsAdminContext + mutation/read services only; capability test |
| No restart/systemd/hot reload authority | read/write Settings API and UI only; no activation endpoint or service-control code |

## SQLite schema summary

Schema identity: `PRAGMA user_version=1`; foreign_keys=ON; busy_timeout=1000 ms. Initialization is transactional; unknown/newer/corrupt/incompatible databases are not dropped, rewritten or migrated. No parent-directory creation.

Six tables:

1. settings_generations: allocated INTEGER PRIMARY KEY, parent FK, global scope, UTC creation/principal/request metadata; immutable.
2. settings_overrides: complete per-generation integer override set, composite primary key, generation FK; immutable.
3. settings_target_state: target key, nullable effective-generation FK, nullable update timestamp; mutable only via activation lifecycle.
4. settings_activation_events: adopted/failed event, generation/target/time/effective-after/error metadata; append-only.
5. settings_mutation_audit: actual changed override/configured values, principal/IP/request/idempotency, generation linkage, global scope and apply target; immutable.
6. settings_idempotency: unique principal-type/name/global/key, canonical payload hash, original successful status/full response, generation/changed/time; immutable; response ≤65536 UTF-8 bytes.

Generation 0 is physically persisted with parent NULL, scope global, canonical UTC creation, **system / settings_bootstrap**, request_id NULL. Overrides, mutation audit, idempotency and activation-event tables are initially empty. `captive-portal.service` target initially has effective_generation=NULL and updated_at_utc=NULL.

## Explicit confirmations

- Resolver precedence: GLOBAL override > explicit environment > shared repository default; base-source classification uses captured environment-name presence. Clear Override removes persistence rather than storing a copied base value. Invalid base values are not silently defaulted.
- Exactly 12 writable, non-secret, GLOBAL integer settings; bootstrap/security/feature/credentials/Site settings are not writable. Canonical defaults/bounds/consumer-validator ownership match R1.
- GLOBAL authorization requires AdminPrincipal/platform_operator and the exact global capability; Site authorization remains unchanged.
- Strict JSON rejects duplicate members at all object levels and NaN/Infinity/-Infinity; exact structure/types; no request.form; independent 32768-byte body / 64-change structural bounds.
- Changed=201, no-op=200; both persist original successful idempotency response. Equivalent input ordering has identical payload hash; conflicts precede stale CAS; replay preserves original full ordered 12-item representation after configured/effective advance.
- One frozen startup G is injected into create_app and runtime composition. Only main lifecycle adopts exact G. Adoption event/target update commit before app.run. Positive configuration failure records failed without effective advance and aborts. Absence of runtime alone is not fabricated positive failure.
- Read model separates configured/effective/pending. Disabled consumers have effective_value=null. No trustworthy adopted snapshot yields runtime_unavailable. Missing liveness is not activation_failed.
- Settings Admin UI has no systemd/restart/sudo/reload authority and no hot activation. No production service actions occurred.

## Known limitations / blockers

1. Existing startup compatibility is not green: the eight clean-worktree artifact-identity failures above require Tech Lead's bounded verification disposition. No source repair or broader test rewrite was attempted.
2. No browser visual acceptance or production activation was performed; template/security/source checks and focused tests are not represented as Owner visual acceptance.
3. No full-project or official Central Lab gate was run by Coder.

Architecture ambiguity = NONE. Verification-authority conflict = clean startup identity gate versus first-round COMMIT=NO; returned explicitly, not bypassed.

## Complete replacement patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\admin-settings-01-r1\TASK-ADMIN-SETTINGS-01-R1.patch
PATCH_BASE=9af1cb158bfcfcb31d441caf71061c9aa2888b85
PATCH_BYTES=109500
PATCH_SHA256=5589b4d51c623ebea4b74821da107842c42ea1d74f0afe313ab8b9e229067519
PATCH_FORMAT=git diff --binary --full-index BASE
PATCH_REVERSE_APPLY_CHECK=PASS
```

STOP / HOLD FOR TECH LEAD REVIEW.

```text
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_TEST=NO
SERVICE_RESTART=NO
PRODUCTION_ACTION=NO
```
