# TASK-ADMIN-SETTINGS-03 — Coder implementation handoff

Status: local review candidate only. Tech Lead acceptance and publication remain pending.

## Exact identity

```text
TASK=TASK-ADMIN-SETTINGS-03
BASE_HEAD=c1167180daec9ca17d13ab44326f143122db8d5e
BASE_TREE=278df41bfa3134b22963b41006585da35de08074
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-03
BRANCH=feature/admin-settings-03-controller-writable-nonsecret
CANDIDATE_COMMIT=913b500076d9b831fb0cdc0e3fae142b7742a1a3
CANDIDATE_PARENT=c1167180daec9ca17d13ab44326f143122db8d5e
CANDIDATE_TREE=7a2782876f1060fb7297014ce1c6c95dec8df9c3
GIT_STATUS_PORCELAIN=<empty>
WORKTREE_STATE=CLEAN
CHANGED_FILES_COUNT=33
ADDITIONS=1180
DELETIONS=205
FULL_BASE_TO_CANDIDATE_PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-03_BASE-to-CANDIDATE.patch
FULL_PATCH_BYTES=134355
FULL_PATCH_SHA256=5ecdaaef0132dfe71eee267814a85b5de53437d3750983ab137f343189397ae3
PATCH_REVERSE_APPLY_CHECK=PASS
SCHEMA_VERSION=2
SCHEMA_MIGRATION_TEST_COUNT/PASS=3/3 PASS
FOCUSED_TESTS=186 passed / 0 failed
AFFECTED_RUNTIME_TESTS=2402 passed / 29 skipped / 1 failed (independently reproduced on baseline)
FULL_PYTEST=5494 passed / 30 skipped / 1 failed / 0 errors / 0 deselected (independently reproduced baseline failure)
COMPILEALL=PASS
NODE_CHECK=PASS
GIT_DIFF_CHECK=PASS
OPEN_P0=0 identified by Coder in implementation
OPEN_P1=0 identified by Coder in implementation
KNOWN_BASELINE_TEST_BLOCKER=tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled
ARCHITECTURE_AMBIGUITY=NONE
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
SYSTEMD_ACTION=NO
SERVICE_RESTART=NO
LIVE_OMADA_TEST=NO
```

The commit is a local review/Lab candidate, not a publication or production activation. No existing worktree was reset, cleaned, stashed or overwritten. A separate untouched-baseline verification worktree was created at `C:\CaptivPortal-Lab\as03-baseline-verification`.

## Exact changed-file list

```text
M app/admin_web/controller_settings.py
M app/admin_web/policy.py
M app/admin_web/routes.py
M app/admin_web/runtime.py
M app/admin_web/static/controller_settings.js
M app/admin_web/templates/admin/base.html
M app/admin_web/templates/admin/settings_controller.html
M app/controllers/omada_config.py
M app/settings_control/activation.py
M app/settings_control/bootstrap.py
M app/settings_control/definitions.py
M app/settings_control/models.py
M app/settings_control/repository.py
M app/settings_control/resolver.py
M app/settings_control/services.py
M app/settings_control/validation.py
M docs/configuration.md
M docs/modules/admin-web.md
M run.py
A tests/admin_web/controller_settings_stage3_ui.cjs
A tests/admin_web/test_controller_settings_stage3.py
A tests/admin_web/test_controller_settings_stage3_frontend.py
M tests/admin_web/test_settings_routes.py
M tests/settings_control/__init__.py
M tests/settings_control/test_bootstrap.py
A tests/settings_control/test_controller_stage3.py
M tests/settings_control/test_definitions.py
M tests/settings_control/test_repository.py
M tests/settings_control/test_resolver.py
M tests/settings_control/test_run_integration.py
M tests/settings_control/test_validation.py
M tests/test_admin_controller_settings.py
M tests/visitor_registry/test_snapshot_runtime.py
```

19 production/documentation files, all within the authorized surface; 14 test/fixture files. `app/admin_web/static/admin.js`, Omada operational methods, secrets/TLS configuration and deployment files are unchanged.

## Verification commands and results

All commands ran locally against disposable inputs; no test required a live Omada Controller.

Focused, on the clean candidate:

```text
python -m pytest -q tests/settings_control tests/test_admin_controller_settings.py tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py tests/admin_web/test_controller_settings_stage3.py tests/admin_web/test_controller_settings_stage3_frontend.py tests/test_omada_configuration.py --basetemp C:/CaptivPortal-Lab/tmp/as03-focused-final --tb=short
186 passed in 12.52s
```

Affected runtime, on the clean candidate:

```text
python -m pytest -q -rs tests/visitor_registry tests/observations tests/current_state tests/pending_sessions tests/visit_lifecycle tests/admin_web tests/integrations/omada tests/test_proxy_headers.py tests/test_auth_retry.py tests/test_auth_telemetry.py tests/test_portal_counter.py tests/test_public_traffic.py tests/test_omada_observations.py tests/test_omada_client_lookup.py --basetemp C:/CaptivPortal-Lab/tmp/as03-compat-final --tb=short
1 failed, 2402 passed, 29 skipped in 116.15s
```

The skips are existing Windows/POSIX filesystem-mode, symlink, FIFO and socket cases. The one failure is detailed below and not waived.

Dedicated migration/rollback checks:

```text
python -m pytest -q tests/settings_control/test_controller_stage3.py -k migration --basetemp C:/CaptivPortal-Lab/tmp/as03-migration-final
3 passed, 37 deselected in 1.76s
```

This is a narrow supplementary selection, not the full gate; the complete focused and full commands contain no deselection filter.

Static checks:

```text
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\as03-compile-cache
python -m compileall -q app run.py
PASS
node --check app/admin_web/static/controller_settings.js
PASS
git diff --check HEAD^ HEAD
PASS
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-03_BASE-to-CANDIDATE.patch
PASS
```

Full repository:

```text
python -m pytest -q -rs --basetemp C:/CaptivPortal-Lab/tmp/as03-full-01 --tb=short
1 failed, 5494 passed, 30 skipped in 700.05s (0:11:40)
0 errors
0 deselected
```

Full repository exit status: 1. Its only failure is exactly the baseline Home
assertion below. The 30 skips are the existing opt-in Analytics performance
benchmark and Windows/POSIX platform cases. No full-suite PASS is claimed and no
test is skipped/deselected as a workaround by this implementation.

## Unrelated baseline failure — not silently waived

Exact failing test:

```text
tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled
tests/admin_web/test_home_traffic.py:629
assert [template.index(f'id="{hook}"') for hook in remaining] == sorted(...)
actual:   [6850, 10547, 10471]
expected: [6850, 10471, 10547]
remaining = ["home-activity", "home-ap-24h", "aps-now-title"]
```

Independent reproduction on a separate clean, untouched accepted baseline:

```text
WORKTREE=C:\CaptivPortal-Lab\as03-baseline-verification
HEAD=c1167180daec9ca17d13ab44326f143122db8d5e
TREE=278df41bfa3134b22963b41006585da35de08074
git status --porcelain=<empty>
python -m pytest -q tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled --basetemp C:/CaptivPortal-Lab/tmp/as03-baseline-home --tb=short
1 failed in 0.46s
same assertion and actual/expected values
```

Neither that test nor `app/admin_web/templates/admin/home.html` is changed. Acceptance remains with Tech Lead; a full-suite PASS is not claimed.

## Source notes / architecture mapping

1. **One Store; migration v1→v2.** `repository.py` retains the exact baseline `_V1_DDL` (independent text comparison with the baseline Git object returned `BASELINE_V1_DDL_EXACT_MATCH=True`). Initialization validates the old schema/history and performs the migration within its existing single `BEGIN IMMEDIATE` transaction. Only overrides, mutation audit and idempotency leaf tables are replaced; their rows and identities are copied, typed/domain metadata is added, and immutable triggers are recreated. Parent generations, target state and activation events are untouched. General response JSON is copied without parsing or rewriting. Rollback restores exact input DB bytes in the failure fixture. New DBs initialize directly at v2 with canonical generation 0 `system / settings_bootstrap`, no overrides/audit/idempotency.

2. **Exactly 15 definitions / two domains.** The original ordered 12 General integers retain bounds and consumer metadata. Exactly `OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID` are added as GLOBAL, normal, required strings, explicitly mapped to `omada_url`, `omada_id`, `client_id`. No secret or writable TLS definition exists. The single resolver uses persisted override > explicit startup environment > repository default and validates the selected Controller value; a valid override may shadow an invalid lower base, while invalid clear fails atomically.

3. **Canonical validation / common mutation.** `normalize_controller_setting()` in the existing Omada configuration owner is shared with runtime composition. IDs trim without new charset/case/length rules; existing URL semantics are preserved. Complete-generation validation retains General validators and the required non-writable secret prerequisite without echoing rejected input. The new exact Controller POST uses its own GLOBAL write capability, CSRF, strict JSON, 32768-byte body, three unique changes and common generation CAS. General/Controller idempotency is domain-separated and replay precedes current CAS/full-candidate validation. Changed/no-op semantics compare override ownership, not merely scalar equality. The bounded receipt contains keys/generation/state, no Controller scalar values. Receipt persistence overflow returns a safe 500 and rolls back generation/overrides/audit/idempotency together. General projections/receipts remain ordered 12-item V1.

4. **Safe configured read + exact effective snapshot.** The Admin read model obtains only a three-key configured projection from the common Settings service; it neither opens SQLite nor reads the full settings mapping, environment or provider private fields. The immutable public snapshot carries exact startup generation and writable provenance, including `persisted_override`. V2 pending fields compare both canonical scalar and source; a General-only pending generation gives Controller pending count 0. After adoption, Store outage nulls configured/override/pending fields rather than using cached truth; effective-only read remains 200 and mutation fails 503. Public projection failure remains non-core.

5. **Startup classification.** Omada provider construction only assigns immutable configuration and initializes local synchronization; no OAuth/request is made. Before durable adoption, Visitor Registry scans local JSONL/SQLite; Visit Lifecycle reads normalized local webhook journals and reconciles against the local Registry; Analytics/Admin are read-boundary composition; AP-24H telemetry reads persisted Current State/Observation and emits local telemetry. `create_app` can start the existing Portal evidence producer, which talks to the separate evidence service, not Omada/OAuth. The Auth thread pool is lazy and HTTP is not serving. These unchanged paths have no shared Controller operation. Pending-session cleaner, Observation, Current State and visitor snapshot collector are composed but now start only after successful durable adoption; HTTP and the Public Traffic worker also follow adoption. Instrumented tests cover all four Controller-capable starts, provider/projection failure, durable-write failure, enabled Store/configuration failure, and post-adoption worker failure without effective-generation rollback or fabricated activation failure.

   Fingerprint integration composition is enqueue-only over local SQLite; it starts no classifier/Controller worker. Its separately owned CLI worker is not executed by the main Portal process. Visit-start submission also has no shared Controller dependency.

6. **Secret boundary.** Only the existing private runtime configuration carries the secret (repr excluded). New Controller definitions, override rows, audit values, idempotency receipts, safe configured projection, public effective objects, HTML/JS data and errors retain no raw secret. Sentinel tests cover HTTP success/errors/page/logs, persistence tables and public repr. TLS is visible/read-only; no override or mutation path is admitted. No network probe, restart button, subprocess/sudo/systemd authority or request-time environment reread was added.

7. **UI / documentation.** Dedicated `controller_settings.js` edits exactly the three non-secret fields, offers Clear Override and confirms selected keys with restart/no-connection-test wording. Every 200/201, including replay, re-GETs authoritative V2 state; 412 reloads and shows conflict without automatic resubmit, and a later manual submit uses a new UUID. The real script is exercised through a disposable DOM/fetch boundary for success, no-op, conflict, clear, cancel, Store outage and read-only authorization. Operator docs describe automatic v2 migration, enabled-startup fail-closed behavior, configured vs effective truth and externally performed activation.

## Governance

```text
COMMIT=LOCAL REVIEW CANDIDATE ONLY
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
PRODUCTION_TEST=NO
SERVICE_RESTART=NO
SYSTEMD_ACTION=NO
```

Stop for Tech Lead source/diff review. No publication authorization is inferred.
