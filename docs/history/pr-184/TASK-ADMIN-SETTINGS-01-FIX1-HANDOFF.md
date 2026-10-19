# TASK-ADMIN-SETTINGS-01 — bounded FIX ROUND 1

STATUS = FIXES IMPLEMENTED / READY FOR TECH LEAD SOURCE REVIEW

Authority: Tech Lead source/diff review of R1 + TL-F1..TL-F5. Only TL-SR-P1-01, TL-SR-P1-02 and TL-SR-P1-03 repaired. No architecture redesign or production action.

## Baseline / actual implementation worktree

```text
BASE_HEAD=9af1cb158bfcfcb31d441caf71061c9aa2888b85
BASE_TREE=4850e322a4286880a32dbd995121a85bc85c9e99
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-01-r1
WORKTREE_STATE=DIRTY — uncommitted review candidate
ACTUAL_IMPLEMENTATION_HEAD=9af1cb158bfcfcb31d441caf71061c9aa2888b85
ACTUAL_IMPLEMENTATION_HEAD_TREE=4850e322a4286880a32dbd995121a85bc85c9e99
STAGED_CONTENT=NONE
IMPLEMENTATION_COMMIT=NONE
```

Original reviewed patch remains unchanged:
5589b4d51c623ebea4b74821da107842c42ea1d74f0afe313ab8b9e229067519.

## Replacement full patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\admin-settings-01-r1\TASK-ADMIN-SETTINGS-01-FIX1.patch
PATCH_BYTES=115592
PATCH_SHA256=4b79c89da9fe5beb7d9579719f2baab005da09952ff50a02dede278199ac235f
PATCH_BASE=9af1cb158bfcfcb31d441caf71061c9aa2888b85
PATCH_FORMAT=git diff --binary --full-index BASE
PATCH_REVERSE_APPLY=PASS
FULL_SCOPE=36 files / 1735 insertions / 22 deletions
```

This is the complete BASE-to-FIX1 candidate, not a fix-only delta. New-file intent-to-add entries are unchanged; no implementation content was staged or committed.

## Exact FIX-round files — 10 existing candidate files changed

```text
app/settings_control/repository.py
app/settings_control/services.py
app/settings_control/models.py
app/settings_control/definitions.py
app/admin_web/static/settings.js
tests/settings_control/test_repository.py
tests/settings_control/test_services.py
tests/settings_control/test_definitions.py
tests/admin_web/test_settings_routes.py
tests/admin_web/test_settings_ui.py
```

No new paths were introduced during the FIX round. No additional baseline-existing test file was modified. The already authorized TL-F4 injection adjustment is unchanged.

## P1-01 — repository SQLite ownership

All SettingsStore SQL and SQLite connection operations are in repository.py. services.py has no execute/executemany/executescript/connect or table SQL.

| Operation formerly in services.py | SettingsRepository API |
| --- | --- |
| Latest configured-generation activation event | latest_activation_result(transaction, generation) |
| Latest actual setting-change audit | latest_setting_audit(transaction, key, generation) |
| Allocate/insert generation + complete sorted override set | create_generation(transaction, named metadata/overrides) |
| Persist each actually changed setting's audit | append_mutation_audit(transaction, named domain facts) |
| Read-side idempotency lookup | lookup_idempotency(principal, key) |

Services orchestrate resolution, validation, change/no-op semantics and result projection through repository APIs. Existing repository ownership of BEGIN IMMEDIATE, current head/override/effective state, activation and success-idempotency persistence remains unchanged. Generation/full overrides/audit/idempotency still commit in one writer transaction. No second persistence layer or Admin-route SQL was introduced.

Focused source-boundary test checks every production settings_control module other than repository.py for SQLite imports and direct connection/SQL execution calls.

## P1-02 — exact two-stage idempotency

1. Existing route authentication → global authorization → CSRF/header/body/strict JSON validation remains unchanged.
2. Service canonicalizes structurally valid changes and hashes the deterministic payload.
3. Repository lookup_idempotency uses an ordinary read transaction.
4. Existing same hash returns original stored status/full successful response immediately; different hash returns 409. Neither needs writer ownership or head CAS.
5. Only a read-side miss enters BEGIN IMMEDIATE.
6. Idempotency is rechecked inside that writer transaction before ordinary stale-generation rejection; then existing CAS/validation/mutation/no-op/audit/persistence flow proceeds.

New proof holds a real competing SQLite BEGIN IMMEDIATE after an accepted mutation/head advance and asserts that both replay and idempotency conflict avoid any write transaction. Original success is returned despite stale If-Match. Another proof simulates an initial miss and confirms writer-side recheck returns a concurrently available original success before CAS. Existing busy-writer test still verifies that genuinely new mutations fail boundedly with settings_store_unavailable, no success record or partial generation.

## P1-03 — canonical read/API metadata

Each integer SettingReadModelV1 validation object is exactly:

```json
{"type":"integer","min":1,"max":500}
```

Bounds vary by the frozen registry; no extra metadata keys. Model typing is Mapping[str, int | str]. Canonical groups are pagination for the first six settings and refresh for the remaining six. GET and full mutation success projections assert these exact shapes; replay remains original stored response.

settings.js takes input bounds from validation.min / validation.max. API group identifiers remain machine values; UI-only text maps pagination → Pagination / Presentation and refresh → Refresh Cadence. No frontend bounds/default/precedence table was added; admin.js remains unchanged.

## Focused Settings tests

Windows PowerShell; Python 3.10.11 at C:\Users\Zaur Navi\AppData\Local\Programs\Python\Python310\python.exe; Node v24.19.0.

```text
python -m pytest -q --basetemp=C:/CaptivPortal-Lab/tmp/admin-settings-fix1-focused tests/settings_control tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py
RESULT=64 passed / 0 failed / 0 errors / 0 skipped
```

## Directly affected compatibility

```text
python -m pytest -q --basetemp=C:/CaptivPortal-Lab/tmp/admin-settings-fix1-direct --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-01-r1/fix1-direct-results.xml tests/admin_web/test_config.py tests/admin_web/test_runtime.py tests/admin_web/test_routes.py tests/admin_web/test_admin_ui_frontend.py tests/admin_web/test_api_routes.py tests/admin_web/test_admin_ui.py tests/admin_web/test_home_activity_frontend.py tests/admin_web/test_home_health_frontend.py tests/admin_web/test_home_ap_24h_frontend.py tests/admin_web/test_home_traffic_frontend.py tests/test_proxy_headers.py
RESULT=148 passed / 0 failed / 0 errors / 0 skipped
```

The startup file was verified separately using the expressly authorized clean procedure below, not bypassed or deselected from its required verification scope.

## Authorized clean verification exception

A new detached disposable worktree was created at the exact accepted baseline:
C:\CaptivPortal-Lab\verify-admin-settings-01-fix1.
The replacement patch was applied with --index. Its rebuilt staged binary/full-index patch had the exact same SHA256 as the replacement above. One temporary local LAB ONLY commit was created; it was never pushed and is not a publication identity.

```text
VERIFY_HEAD=c053829ef8c9672c58f2641806fe2a9e935b55f2
VERIFY_PARENT=9af1cb158bfcfcb31d441caf71061c9aa2888b85
VERIFY_TREE=0ef5c4555fa254a8904f35e19c0570a5bbe8abe7
VERIFY_WORKTREE_STATE=CLEAN — before and after verification
VERIFY_PATCH_IDENTITY=EXACT MATCH
```

Exact command, executed from that disposable worktree:

```text
python -m pytest -q --tb=short --basetemp=C:/CaptivPortal-Lab/tmp/admin-settings-fix1-clean --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-01-r1/fix1-clean-verification-results.xml tests/visitor_registry/test_snapshot_runtime.py tests/test_artifact_identity.py
RESULT=25 passed / 0 failed / 0 errors / 0 skipped
SNAPSHOT_RUNTIME_RESULT=10 passed
ARTIFACT_IDENTITY_RESULT=15 passed
```

The eight prior startup failures do not reproduce in this clean candidate. Production artifact-identity guard was not modified. The old tests were not changed beyond the previously reviewed TL-F4 injection adjustment.

After evidence capture and exact path/HEAD/clean-status checks, git worktree remove deleted only that explicitly named disposable verification checkout and its detached worktree HEAD registration. No branch ref was created. Patch and XML evidence remain in the external artifacts directory. No forced removal/reset/clean/stash or change to the actual implementation worktree was performed.

```text
DISPOSABLE_VERIFY_WORKTREE_REMOVED=YES
DISPOSABLE_VERIFY_REF_REMOVED=YES
TEMPORARY_VERIFY_COMMITS_CREATED=1
TEMPORARY_VERIFY_COMMIT_PUSHED=NO
ACTUAL_IMPLEMENTATION_COMMIT_CREATED=NO
```

## Syntax / diff / patch checks

External PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\admin-settings-fix1-pycache:

```text
python -m compileall -q app/settings_control tests/settings_control app/config.py app/settings.py app/web/web.py app/admin_web/policy.py app/admin_web/runtime.py app/admin_web/routes.py run.py tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py tests/visitor_registry/test_snapshot_runtime.py
COMPILEALL=PASS
node --check app/admin_web/static/settings.js
NODE_CHECK=PASS
git diff --check
DIFF_CHECK=PASS
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/admin-settings-01-r1/TASK-ADMIN-SETTINGS-01-FIX1.patch
PATCH_REVERSE_APPLY=PASS
```

## Exact full new-file inventory — 23

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

## Exact full modified-file inventory — 13

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

No additional baseline-existing test source modifications, runtime identity bypass, unrelated refactor or schema change. Other worktrees/prototypes were not edited.

```text
ARCHITECTURE_AMBIGUITY=NONE
KNOWN_BLOCKERS=NONE OBSERVED IN AUTHORIZED VERIFICATION
TECH_LEAD_ACCEPTANCE=PENDING SOURCE REVIEW
FULL_PROJECT_TESTS=NOT RUN
CENTRAL_LAB=NOT RUN
COMMIT=NO — actual implementation worktree
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_TEST=NO
SERVICE_RESTART=NO
PRODUCTION_ACTION=NO
```

STOP / HOLD FOR TECH LEAD REVIEW.
