# TASK-ADMIN-SETTINGS-02 — FIX1 handoff

Authority: original TASK + TL-AS02-F1 + Tech Lead Source Review R1.
Disposition: FIX1 implementation complete; independent re-review pending.

## Candidate / complete replacement patch

```text
BASE_HEAD=9ca25fd3dc9d552d446be4669f2e67247dcb7a1b
BASE_TREE=0ef5c4555fa254a8904f35e19c0570a5bbe8abe7
R1_TREE=ab0c754dde834a415faac0a089771a5c7ab737ca
FIX1_CANDIDATE_TREE=278df41bfa3134b22963b41006585da35de08074

PATCH_PATH=C:\CaptivPortal-Lab\artifacts\admin-settings-02\TASK-ADMIN-SETTINGS-02-FIX1.patch
PATCH_BYTES=69753
PATCH_SHA256=ddefab36af467a0bfa7e0915032df8d3645efeb24b3d1365279f7cf665f593ea
PATCH_FORMAT=complete BASE-to-FIX1 git diff --binary --full-index
COMPLETE_SCOPE=27 files changed, 783 insertions(+), 113 deletions(-)
REVERSE_APPLY_CHECK=PASS
WORKING_FILES_MATCH_CANDIDATE_INDEX=YES
```

The original R1 patch, handoff and clean LAB ONLY worktree were preserved.
FIX1 tree and patch were generated through a separate external candidate index;
no new commit was created and the implementation worktree's normal index was
not staged/changed.

## Exact changes since R1

```text
M app/admin_web/routes.py
M app/admin_web/static/controller_settings.js
M app/admin_web/templates/admin/settings_controller.html
M tests/test_admin_controller_settings.py

4 files changed, 46 insertions(+), 6 deletions(-)
```

P1-01: Controller API GET rejects a positive request-body length or any body
byte with `400 invalid_request`, before reading Controller configuration.
Unknown-length streams are inspected for at most one byte. No schema parsing,
body retention/logging, route-method widening or shared boundary change.
Existing no-store/no-cache headers remain. Three regressions cover octet-stream,
malformed JSON and a sentinel-secret text body; each asserts rejection without
configuration read and unchanged 200 behavior for a subsequent body-free GET.

P1-02: heading is exactly `Controller`; visible provider identity is
`Omada Controller`. JS success is `Read-only effective startup configuration.`
Both initial-template and JS failure wording is
`Controller configuration is unavailable.` Existing canonical loading wording
is preserved. Deployment/no-connection-test explanation remains separate.
One narrow UI regression asserts heading, provider and all canonical statuses.

No other R1 production/configuration/provider/fallback/authorization/Store
semantics or files changed during FIX1.

## Focused verification

Environment: Windows/PowerShell, Python 3.10.11, Node v24.19.0.
All final runs: 0 failures, 0 errors, 0 skipped.

### Existing Stage-2 focused gate: 111 PASS

25 Stage-2 tests, 22 Omada configuration tests and 64 Stage-1 tests.

```text
python -m pytest -q tests/test_admin_controller_settings.py tests/test_omada_configuration.py tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py tests/settings_control --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-fix1-focused-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-fix1-focused.xml
```

### Existing direct compatibility group: 268 PASS

Re-run because shared routes are touched. No broad/full repository execution.

```text
python -m pytest -q tests/admin_web/test_routes.py tests/admin_web/test_api_routes.py tests/admin_web/test_runtime.py tests/admin_web/test_config.py tests/test_proxy_headers.py tests/test_auth_retry.py tests/test_capport_routes.py tests/test_omada_client_lookup.py tests/test_omada_observations.py tests/pending_sessions/test_omada_token_cache_concurrency.py --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-fix1-direct-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-fix1-direct.xml
```

### Static / patch checks

```text
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\admin-settings-02-fix1-pycache
python -m compileall -q app run.py tests                  PASS
node --check app/admin_web/static/controller_settings.js PASS
git diff --check                                        PASS
git diff --cached --check (external FIX1 index)           PASS
git apply --reverse --check <full FIX1 patch>             PASS
```

R1 application/startup wiring evidence accepted by Tech Lead remains historical
R1 evidence, not claimed as a fresh FIX1 rerun. Those unchanged paths were not
rerun unnecessarily; only required focused/direct checks above ran for FIX1.

## State / hold

```text
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-02
BRANCH=feature/admin-settings-02-controller-read-model
LOCAL_HEAD=9ca25fd3dc9d552d446be4669f2e67247dcb7a1b
WORKTREE_STATE=DIRTY — full reviewed implementation candidate, unstaged
KNOWN_FIX1_BLOCKERS=NONE
INDEPENDENT_RE_REVIEW=PENDING
NEW_COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
FULL_TESTS=NO
CENTRAL_LAB=NO
PRODUCTION_ACTION=NO
```

Return control to Tech Lead for FIX1 source/diff re-review. No publication is
performed under this implementation repair authority.
