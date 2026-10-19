# TASK-ADMIN-SETTINGS-02 — implementation review handoff

Contract: FINAL TASK + TL-AS02-F1. Implementation candidate prepared; independent
Tech Lead acceptance/publication pending. No production access, live Controller
probe, Omada mutation, service restart or systemd action was performed.

## Identity

```text
BASE_HEAD=9ca25fd3dc9d552d446be4669f2e67247dcb7a1b
BASE_TREE=0ef5c4555fa254a8904f35e19c0570a5bbe8abe7
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-02
BRANCH=feature/admin-settings-02-controller-read-model
WORKTREE_STATE=DIRTY — exactly the implementation candidate, unstaged
CANDIDATE_TREE=ab0c754dde834a415faac0a089771a5c7ab737ca

LAB_ONLY_HEAD=83e6069b803030d2309d1a356eb9d5d7a3b1a1c6
LAB_ONLY_PARENT=9ca25fd3dc9d552d446be4669f2e67247dcb7a1b
LAB_ONLY_TREE=ab0c754dde834a415faac0a089771a5c7ab737ca
LAB_ONLY_WORKTREE=C:\CaptivPortal-Lab\verify-admin-settings-02
LAB_ONLY_WORKTREE_STATE=CLEAN
```

The detached LAB ONLY commit was created with an external index exclusively
to run the authorized startup compatibility tests without weakening the
existing clean-repository artifact identity guard. It is not an implementation
publication commit, is not pushed and is not on the feature branch.

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\admin-settings-02\TASK-ADMIN-SETTINGS-02.patch
PATCH_BYTES=67595
PATCH_SHA256=3d7fa0ef132ca0c5530b3ca0e14e730366764bb7c3094bea97420dab1bb950a6
PATCH_FORMAT=git diff --binary --full-index BASE LAB_ONLY_HEAD
REVERSE_APPLY_CHECK=PASS
WORKING_FILES_VS_CANDIDATE_INDEX=IDENTICAL
DIFF_STAT=27 files changed, 743 insertions(+), 113 deletions(-)
```

## Exact changed files

New files:

```text
app/controllers/omada_config.py
app/admin_web/controller_settings.py
app/admin_web/templates/admin/settings_controller.html
app/admin_web/static/controller_settings.js
tests/test_admin_controller_settings.py
```

Modified files:

```text
run.py
app/controllers/factory.py
app/controllers/omada.py
app/web/web.py
app/admin_web/policy.py
app/admin_web/runtime.py
app/admin_web/routes.py
app/admin_web/templates/admin/base.html
app/admin_web/static/admin.css
docs/configuration.md
docs/modules/admin-web.md
tests/test_omada_configuration.py
tests/test_proxy_headers.py
tests/test_auth_retry.py
tests/test_portal_counter.py
tests/test_auth_telemetry.py
tests/test_public_traffic.py
tests/integrations/omada/test_webhook_site_mapping.py
tests/integrations/omada/test_webhook_receiver.py
tests/visitor_registry/test_snapshot_runtime.py
tests/observations/test_runtime.py
tests/settings_control/test_run_integration.py
```

Existing test changes are limited to the changed construction boundary:
valid synthetic core configuration for startup, typed factory argument, or
explicit injection of the already-mocked Controller. Existing expected
Portal/Auth/CAPPORT/Settings outcomes are unchanged; assertions were not removed
or weakened. No SettingsStore source or registry changes.

## Requirement → implementation

| Requirement | Implementation / focused proof |
| --- | --- |
| One immutable normalized runtime config, required values and existing URL semantics | `omada_config.py`; existing 22 Omada configuration tests retained, moved onto injected config construction |
| Shared provider uses the exact adopted config; no provider settings fallback | mandatory factory/provider config argument; main shared-config composition test |
| Same startup environment-name capture for both stages | `run.py` captures once and passes the same frozen set to bootstrap and projection; identity assertion in focused test |
| Secret-free public projection, no raw settings/provider/store/environment access in read service | distinct immutable public snapshot; service accepts only its exact type |
| Client Secret non-disclosure | secret excluded from runtime repr/str; public presence/source only; sentinel absent from public serialization, responses, HTML, logs and error output |
| Source provenance | startup membership only; VERIFY_SSL remains repository constant, source repository_default |
| GLOBAL authorization | exactly one new read capability; no Site resolution; independent General/Controller navigation tests |
| Canonical read API | one GET route; exact model, UUID, scope/resource, source labels; no-store/no-cache; unknown queries fail 400 |
| Fail-closed sanitized errors | 401 / 403 / 404 / 503 / 500; no exception or configuration serialization in responses |
| Dedicated read-only UI | Controller template + GET-only same-origin script; no settings.js/admin.js, no mutation controls or probe |
| Projection isolation | startup projection/read composition failures affect Controller surface only; shared provider continues; normal Portal/Auth compatibility remains green |
| SettingsStore independence | unavailable store plus trustworthy public snapshot returns 200; twelve writable settings remain unchanged |
| TL-AS02-F1 | create_app fallback derives config from its same local mapping, exactly one factory call, zero additional settings reads; injected Controller never rebuilt |
| No systemd/production authority | no such dependency, route or operation added; none executed |

No SQLite schema, Controller overrides, generations, secret persistence,
Omada request/token behavior, Auth/CAPPORT semantics, feature flags, systemd units
or production configuration were changed. Public surface describes configuration
only, never Controller health/connectivity.

## Exact final focused verification

Environment: Windows / PowerShell, Python 3.10.11, Node v24.19.0.
All final successful test runs: 0 failed, 0 errors, 0 skipped.

### Settings / Controller focused: 107 passed

21 new Stage-2 tests, 22 existing Omada configuration tests, 64 Stage-1 tests.

```text
python -m pytest -q tests/test_admin_controller_settings.py tests/test_omada_configuration.py tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py tests/settings_control --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-focused-02 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-focused.xml
```

### Direct Admin / Omada / Portal compatibility: 268 passed

```text
python -m pytest -q tests/admin_web/test_routes.py tests/admin_web/test_api_routes.py tests/admin_web/test_runtime.py tests/admin_web/test_config.py tests/test_proxy_headers.py tests/test_auth_retry.py tests/test_capport_routes.py tests/test_omada_client_lookup.py tests/test_omada_observations.py tests/pending_sessions/test_omada_token_cache_concurrency.py --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-direct-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-direct.xml
```

### Affected application wiring: 30 passed

```text
python -m pytest -q tests/test_portal_counter.py::PortalCounterWebTests tests/test_auth_telemetry.py::AuthTelemetryWebIntegrationTests tests/test_public_traffic.py::test_api_keeps_open_counter_when_traffic_is_unavailable tests/test_public_traffic.py::test_api_returns_traffic_and_preserves_old_fields tests/test_public_traffic.py::test_corrupt_aggregate_hides_only_traffic_from_api tests/test_public_traffic.py::test_disabled_component_creates_no_database_or_worker tests/test_public_traffic.py::test_invalid_traffic_config_is_fail_safe_for_app tests/test_public_traffic.py::test_create_app_constructs_but_does_not_start_worker tests/integrations/omada/test_webhook_receiver.py::test_disabled_module_returns_404_and_creates_no_log tests/integrations/omada/test_webhook_receiver.py::test_enabled_webhook_is_isolated_from_existing_routes tests/integrations/omada/test_webhook_site_mapping.py::test_application_wiring_uses_mapping_and_invalid_config_is_fail_open tests/visitor_registry/test_snapshot_integration.py --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-wiring-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-wiring.xml
```

### Clean LAB ONLY startup compatibility: 12 + 1 passed

These commands ran in the clean detached snapshot above, not production or
official Central Lab. Artifact identity guard is unchanged.

```text
python -m pytest -q tests/visitor_registry/test_snapshot_runtime.py tests/test_public_traffic.py::test_worker_start_failure_does_not_prevent_flask_start tests/integrations/omada/test_webhook_receiver.py::test_persist_failure_leaves_portal_and_auth_routes_available --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-startup-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-startup.xml

python -m pytest -q tests/observations/test_runtime.py::test_process_wiring_passes_same_provider_and_app_telemetry --basetemp C:/CaptivPortal-Lab/tmp/admin-settings-02-observation-wiring-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/admin-settings-02-observation-wiring.xml
```

### Syntax / artifact checks

```text
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\admin-settings-02-pycache
python -m compileall -q app run.py tests                  PASS
node --check app/admin_web/static/controller_settings.js PASS
git diff --check                                        PASS
git apply --reverse --check <complete patch>             PASS
production zero-argument create_controller()/OmadaProvider() call search: NONE
```

Initial local run encountered Windows Temp permissions (47 setup errors,
no failed test assertions). Re-running with the explicit external Lab temp
directory removed that environment issue. The next run exposed three old
Stage-1 startup fixtures lacking core Controller values; their synthetic
settings now include valid Omada configuration. Final 107-test run is green.

## Limits / disposition

```text
ARCHITECTURE_AMBIGUITY=NONE
KNOWN_IMPLEMENTATION_BLOCKERS=NONE
FULL_PROJECT_TESTS=NOT RUN
CENTRAL_LAB=NOT RUN / Owner + Tech Lead responsibility
INDEPENDENT_SOURCE_REVIEW=PENDING
CANDIDATE_ACCEPTED=NO — pending independent review/acceptance
IMPLEMENTATION_PUBLICATION_COMMIT=NOT CREATED
LAB_ONLY_SNAPSHOT_COMMIT=CREATED (identity above)
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
SERVICE_RESTART=NO
LIVE_OMADA_PROBE=NO
```

Other existing worktree source files were not modified. The only additional
worktree is the detached clean candidate used for scoped startup compatibility.
Owner/Tech Lead next step: review the complete patch and exact test evidence,
determine any independent mandatory acceptance, then separately authorize
accepted-candidate publication.
