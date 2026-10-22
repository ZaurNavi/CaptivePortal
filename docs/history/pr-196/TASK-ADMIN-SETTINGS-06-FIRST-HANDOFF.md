# TASK-ADMIN-SETTINGS-06 — first implementation handoff

Implementation contract: original TASK + authoritative baseline amendment A1 + shared-fixture scope amendment A2. Candidate is uncommitted and awaits Tech Lead review. No acceptance or publication is declared.

## Required result block

```ini
TASK=TASK-ADMIN-SETTINGS-06
BASE_HEAD=3467da8abd4ad4bb5b381a13e374e2e8faf4685e
BASE_TREE=2e3cb2b345af370275cb9b8fe35729f6f5218d35
BRANCH=feature/admin-settings-06-feature-controls
WORKTREE_PATH=C:\CaptivPortal-Lab\coder-admin-settings-06
HEAD=UNCOMMITTED
LOCAL_HEAD=3467da8abd4ad4bb5b381a13e374e2e8faf4685e
WORKTREE=DIRTY
CANDIDATE_TREE=2e5f224217f38c5545b413295d9f2effdd8c8d74
CHANGED_FILES=63
PRODUCTION_FILES=21
TEST_FILES=42
ADDITIONS=1941
DELETIONS=307
REGISTRY_COUNT=General:12 / Controller:3 / Portal:14 / Features:17 / Total:46
TARGET_SCHEMA=5
FEATURE_PLAN=one resolved startup snapshot / one immutable startup plan; supplied exact-object identity retained
AP24_ADMITTED=NO
PROJECTION_READ_ADMITTED=YES
SECRET_ISOLATION=PASS
V4_TO_V5=PASS
V5_RECOVERY=PASS
R1_1_MATRIX=PASS
ROUTE_GATING=PASS
TARGETED_TESTS=741 PASS / 1 pre-existing Home-ordering assertion FAIL / 0 ERROR / 0 SKIP
NEW_STAGE6_TESTS=163 PASS / 0 FAIL
DIRECT_EXISTING_COMPATIBILITY=578 PASS / 1 pre-existing Home-ordering assertion FAIL
NODE_CHECK=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
NORMAL_INDEX_STAGED_FILES=0
ARCHITECTURE_AMBIGUITY=NONE
OPEN_P0=0 (known new Stage-6 findings)
OPEN_P1=0 (known new Stage-6 findings)
TEST_GATE_ALL_GREEN=NO
HOLD_REASON=Tech Lead review plus disposition of unchanged baseline Home-ordering assertion
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

## Exact file inventory

Names below are relative to the isolated worktree above. A=new; M=modified.

CHANGED_PRODUCTION_FILES:

```text
M	app/admin_web/capabilities.py
M	app/admin_web/config.py
M	app/admin_web/routes.py
M	app/admin_web/runtime.py
M	app/admin_web/static/admin.css
A	app/admin_web/static/features_settings.js
M	app/admin_web/templates/admin/base.html
A	app/admin_web/templates/admin/settings_features.html
M	app/analytics/runtime.py
M	app/settings_control/activation.py
M	app/settings_control/bootstrap.py
M	app/settings_control/definitions.py
A	app/settings_control/features.py
M	app/settings_control/models.py
M	app/settings_control/repository.py
M	app/settings_control/resolver.py
M	app/settings_control/services.py
M	app/settings_control/validation.py
M	app/settings_control/value_validation.py
M	app/traffic_projection/config.py
M	run.py
```

CHANGED_TEST_FILES:

```text
M	tests/admin_web/conftest.py
A	tests/admin_web/feature_settings_stage6_ui.cjs
M	tests/admin_web/test_config.py
M	tests/admin_web/test_device_current_context.py
A	tests/admin_web/test_feature_settings_stage6.py
A	tests/admin_web/test_feature_settings_stage6_frontend.py
M	tests/admin_web/test_home_activity.py
M	tests/admin_web/test_home_health.py
M	tests/admin_web/test_home_live.py
M	tests/admin_web/test_home_traffic.py
M	tests/admin_web/test_routes.py
M	tests/admin_web/test_runtime.py
M	tests/admin_web/test_settings_routes.py
M	tests/admin_web/test_traffic_ap.py
M	tests/admin_web/test_traffic_ap_share.py
M	tests/admin_web/test_traffic_completed_sessions.py
M	tests/admin_web/test_traffic_current.py
M	tests/admin_web/test_traffic_evidence.py
M	tests/admin_web/test_traffic_foundation.py
M	tests/admin_web/test_traffic_history.py
M	tests/admin_web/test_traffic_independent_ranges.py
M	tests/admin_web/test_traffic_online_guests.py
M	tests/admin_web/test_traffic_peak.py
M	tests/admin_web/test_traffic_statistics.py
A	tests/analytics/test_feature_plan_stage6.py
M	tests/analytics/test_runtime.py
M	tests/settings_control/__init__.py
M	tests/settings_control/test_activation.py
M	tests/settings_control/test_controller_secret_repository.py
M	tests/settings_control/test_controller_secret_service.py
M	tests/settings_control/test_controller_secret_startup.py
M	tests/settings_control/test_controller_stage3.py
M	tests/settings_control/test_definitions.py
A	tests/settings_control/test_features_stage6.py
M	tests/settings_control/test_portal_stage5.py
M	tests/settings_control/test_repository.py
M	tests/settings_control/test_run_integration.py
M	tests/settings_control/test_schema_v4_portal.py
A	tests/settings_control/test_schema_v5_features.py
A	tests/settings_control/test_secret_recovery_v5.py
M	tests/settings_control/test_services.py
M	tests/settings_control/test_validation.py
```

NEW_FILES:

```text
app/admin_web/static/features_settings.js
app/admin_web/templates/admin/settings_features.html
app/settings_control/features.py
tests/admin_web/feature_settings_stage6_ui.cjs
tests/admin_web/test_feature_settings_stage6.py
tests/admin_web/test_feature_settings_stage6_frontend.py
tests/analytics/test_feature_plan_stage6.py
tests/settings_control/test_features_stage6.py
tests/settings_control/test_schema_v5_features.py
tests/settings_control/test_secret_recovery_v5.py
```

Only A2 adds the shared fixture authorization: tests/admin_web/conftest.py. No other shared fixture/benchmark file was changed. Existing test changes adapt explicit real feature-plan injection and accepted Stage-6 expectations; the unrelated failing Home-ordering assertion is unchanged.

Forbidden paths remain unchanged, including .env.example, app/config.py, app/settings.py, NI attribution/metadata/projection code and deployment files. No parallel worktree was edited.

## FEATURE_ALLOWLIST — exact registry order

```text
WEB_ADMIN_HOME_LIVE_ENABLED
WEB_ADMIN_HOME_TRAFFIC_ENABLED
WEB_ADMIN_HOME_ACTIVITY_ENABLED
WEB_ADMIN_HOME_HEALTH_ENABLED
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
```

All 17 preferences are GLOBAL ordinary editable settings, canonical durable strings true/false with public boolean representation, repository default false, main-service restart adoption. WEB_ADMIN_ENABLED remains the independent outer composition gate, not a graph parent. AP24 is not added to this allowlist.

## Architecture requirement → implementation mapping

| Requirement | Implementation and evidence |
|---|---|
| One registry-owned feature graph | definitions.py declares exact keys, feature IDs, control kinds and parents; features.py derives immutable configured values, states and ordered blocking ancestors. |
| Parent=false, child=true is valid | Child preference persists unchanged; effective state is dormant_parent_disabled. No cascade writes or manufactured child audit changes. Parent/ancestor tests pass. |
| One startup snapshot / one startup plan | bootstrap.py creates plan once before validation; validation receives that exact plan. run.py supplies it to Analytics/Admin/activation. Both enabled and disabled Settings startup paths assert exactly one build. |
| Mandatory runtime plan | Admin/Analytics runtime factories require feature_plan; production does not accept a None fallback or reread environment. Activation verifies submitted/runtime object and generation identities. |
| A2 shared fixture | admin_app uses the same settings mapping for its synthetic ResolvedSettingsSnapshot and create_admin_web_runtime; constructs real AdminFeaturePlanV1.from_snapshot; asserts runtime.feature_plan is feature_plan. No Store/SQLite or mock plan added for this purpose. |
| General consumer behavior | Read model uses outer Admin gate and selected plan for affected General consumers; dormant/disabled returns effective_value=null with consumer_disabled. Existing AP24 consumer behavior stays separate. |
| Conditional prerequisite validation | General primitives always checked. Enabled graph plus outer Admin selects authoritative Admin/Activity/Health/ListContext/Projection read prerequisites; dormant flags do not trigger irrelevant prerequisites. A–G and retained-invalid-then-enable H cases cover startup and all mutation domains. |
| Read-only projection selection | traffic_projection/config.py has read-boundary-only configuration; Analytics opens it only when selected. No producer/worker flag mutation, writer lock requirement or raw fallback on selected-source failure. |
| Structural startup adoption | activation.py checks graph-selected configuration/codec/historical-mode and exact plan identities. It does not poll optional source health. Existing AP24 adoption condition and its failure category remain separately preserved. |
| Secret isolation | Features and Portal mutation use non-secret validation and inherit managed-secret ownership; no secret resolution/decrypt/master-key load. General/Controller use the canonical Controller builder with separate secret resolution. Managed opaque-secret test forbids resolve/keys/key load/decrypt and verifies exact binding carry-forward. |
| SQLite schema v5 | repository.py expands only audit/idempotency allowed-key/domain constraints and preserves ordinary override representation. Migration validates closed schema, history, foreign keys and secret history before/after transactional row-preserving copy. |
| Recovery compatibility | v5 recovery preserves Features and all ordinary state/history/receipts/effective head while replacing only secret ownership. No decrypt/master-key load; existing recovery uses current repository schema version without a production recovery-module edit. |
| GLOBAL HTTP boundary | New Features page/read/generation routes use separate read/write capabilities; write requires both. Strict JSON/boolean shapes, CSRF, canonical UUIDv4, common CAS/ETag and separate idempotency domain remain fail-closed. |
| Runtime route gating | Disabled/dormant products return before source access; startup plan is not hot-replaced by a configured-generation write. Base Devices list/card functionality remains. |
| Dedicated UI | features_settings.js owns page behavior; registry graph is server-owned. Safe textContent, grouped controls, explicit dirty sets/resets, no parent cascade, no restart/polling authority. General→Features→Controller→Portal navigation and Store-unavailable/read-only presentation are covered. |

## SQLite / startup / mutation confirmations

- Schema target 5; empty stores initialize at 5, supported earlier versions migrate through existing paths.
- v4→v5 preserves generation IDs, parent chain, overrides, audit IDs, idempotency receipt bytes, activation/effective state, opaque secret frames and secret-binding history.
- No migration-created Features overrides, generations, audit entries or receipts.
- Exact transactional BEGIN/COMMIT and rollback-on-failure checks pass; malformed/future schema and invalid key representation fail closed.
- Generation 0 continues using existing system / settings_bootstrap identity; no Stage-6 alternate bootstrap actor.
- Resolver retains existing base/override precedence and validates invalid base feature scalars even if an override would shadow them.
- Changed/no-op/replay uses common generation CAS with a separate Features idempotency domain; replay checked before CAS. No-op stores receipt without new generation or audit.
- Configured feature readback may derive a prospective plan; it cannot replace the immutable process startup plan.
- Settings/API has no systemd or restart authority. Adoption remains restart-based; no restart was performed.
- No secret is copied into ordinary ResolvedSettingsSnapshot for validation.

## Verification executed

Environment: Windows, Python 3.10.11 from C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe, Node v24.19.0. PYTHONPYCACHEPREFIX was external to the repository: C:\CaptivPortal-Lab\tmp\settings06-pycache.

The final focused command below ran the mandatory TASK list plus the narrow Settings-route/UI/v4-schema direct compatibility files. No full repository suite or Central Lab was run.

```text
python -m pytest -q
  tests/settings_control/test_features_stage6.py
  tests/settings_control/test_schema_v5_features.py
  tests/settings_control/test_secret_recovery_v5.py
  tests/settings_control/test_definitions.py
  tests/settings_control/test_resolver.py
  tests/settings_control/test_validation.py
  tests/settings_control/test_services.py
  tests/settings_control/test_repository.py
  tests/settings_control/test_bootstrap.py
  tests/settings_control/test_activation.py
  tests/settings_control/test_run_integration.py
  tests/admin_web/test_feature_settings_stage6.py
  tests/admin_web/test_feature_settings_stage6_frontend.py
  tests/admin_web/test_config.py
  tests/admin_web/test_runtime.py
  tests/admin_web/test_routes.py
  tests/admin_web/test_home_live.py
  tests/admin_web/test_home_traffic.py
  tests/admin_web/test_home_activity.py
  tests/admin_web/test_home_health.py
  tests/admin_web/test_device_current_context.py
  tests/admin_web/test_traffic_foundation.py
  tests/admin_web/test_traffic_history.py
  tests/admin_web/test_traffic_statistics.py
  tests/admin_web/test_traffic_peak.py
  tests/admin_web/test_traffic_ap.py
  tests/admin_web/test_traffic_independent_ranges.py
  tests/admin_web/test_traffic_ap_share.py
  tests/admin_web/test_traffic_online_guests.py
  tests/admin_web/test_traffic_completed_sessions.py
  tests/admin_web/test_traffic_evidence.py
  tests/analytics/test_feature_plan_stage6.py
  tests/analytics/test_runtime.py
  tests/traffic_projection/test_projected_read.py
  tests/admin_web/test_settings_routes.py
  tests/admin_web/test_settings_ui.py
  tests/settings_control/test_schema_v4_portal.py
  --basetemp=C:\CaptivPortal-Lab\tmp\settings06-frozen-focused
  --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-focused-final.xml
  --tb=short
```

Final result: 742 collected/executed; 741 passed, 1 failed, 0 errors, 0 skipped. JUnit duration 57.831 seconds.

New Stage-6 results:

| File | Passed | Failed |
|---|---:|---:|
| tests/settings_control/test_features_stage6.py | 89 | 0 |
| tests/settings_control/test_schema_v5_features.py | 11 | 0 |
| tests/settings_control/test_secret_recovery_v5.py | 2 | 0 |
| tests/admin_web/test_feature_settings_stage6.py | 40 | 0 |
| tests/admin_web/test_feature_settings_stage6_frontend.py | 11 | 0 |
| tests/analytics/test_feature_plan_stage6.py | 10 | 0 |
| Total | 163 | 0 |

The frontend group includes ten executions of the actual dedicated Node harness, plus a static ownership/safe-DOM assertion. No browser/product visual acceptance is claimed.

Syntax and patch checks:

```text
node --check app/admin_web/static/features_settings.js                         PASS
node --check tests/admin_web/feature_settings_stage6_ui.cjs                    PASS
python -m compileall -q run.py app/settings_control app/admin_web
  app/analytics/runtime.py app/traffic_projection/config.py
  tests/settings_control/test_features_stage6.py
  tests/settings_control/test_schema_v5_features.py
  tests/settings_control/test_secret_recovery_v5.py
  tests/admin_web/test_feature_settings_stage6.py
  tests/admin_web/test_feature_settings_stage6_frontend.py
  tests/analytics/test_feature_plan_stage6.py                                  PASS
git diff --check                                                             PASS
complete candidate diff --check using external temporary Git index            PASS
git apply --reverse --check exported complete patch                           PASS
git diff --cached --name-only                                                 empty
```

## One unchanged baseline assertion — exact evidence for Tech Lead

```text
FAILED=tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled
Assertion: offsets of ["home-activity", "home-ap-24h", "aps-now-title"] must be sorted.
Actual offsets: [6850, 10547, 10471]
Sorted offsets: [6850, 10471, 10547]
Exact BASE template offsets: [6850, 10547, 10471]
Candidate template offsets: [6850, 10547, 10471]
TemplateMatchesBaseline=True
```

app/admin_web/templates/admin/home.html has no diff against BASE_HEAD. The failing ordering assertion is unchanged. Existing test-file edits supply the real plan; they do not change this ordering expectation. This is a read-only baseline source comparison, NOT a claim that a separate baseline pytest run was executed.

No fix, skip, xfail, deselection, timing workaround or Home product change was introduced. Tech Lead disposition is required before an all-green acceptance/publication gate can be claimed.

## Known limits / pending review

- One baseline Home-ordering assertion fails; full focused gate is not entirely green.
- No known new Stage-6 P0/P1 finding; this is a Coder assessment, not independent acceptance.
- Broader repository/Linux/cross-module regression and product/source acceptance belong to Tech Lead; not executed.
- The available Windows interpreter lacks cryptography. The required new secret-isolation/recovery fixtures use retained opaque synthetic encrypted frames with all decrypt/key-loading boundaries forbidden. No broader AES cryptography gate is claimed.
- Some authorized existing Stage-4 compatibility files were adapted for mandatory plan injection but are outside the mandatory focused run; broader regression remains pending.
- No repository/production environment or dependency installation was performed.
- No architecture ambiguity or additional unauthorized production/shared-fixture requirement is currently known.

## Complete BASE→candidate patch and diff

```ini
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-06-FIRST-CANDIDATE.patch
PATCH_BYTES=215635
PATCH_SHA256=7074bb9189f296d94dafd8d4487bd49b63edabd69fc28187cab4230e1ddd198c
CANDIDATE_TREE=2e5f224217f38c5545b413295d9f2effdd8c8d74
REVERSE_APPLY=PASS
```

Export used a separate external temporary index so new files are included without staging anything in the normal worktree index. No implementation commit exists.

```text
 app/admin_web/capabilities.py                      |   3 +-
 app/admin_web/config.py                            | 117 ++-----
 app/admin_web/routes.py                            |  56 +++-
 app/admin_web/runtime.py                           |  17 +-
 app/admin_web/static/admin.css                     |   7 +
 app/admin_web/static/features_settings.js          | 119 +++++++
 app/admin_web/templates/admin/base.html            |   9 +-
 .../templates/admin/settings_features.html         |  12 +
 app/analytics/runtime.py                           |  25 +-
 app/settings_control/activation.py                 |  38 ++-
 app/settings_control/bootstrap.py                  |  10 +-
 app/settings_control/definitions.py                |  35 ++
 app/settings_control/features.py                   |  61 ++++
 app/settings_control/models.py                     |   1 +
 app/settings_control/repository.py                 |  43 ++-
 app/settings_control/resolver.py                   |   2 +
 app/settings_control/services.py                   |  80 ++++-
 app/settings_control/validation.py                 |  44 ++-
 app/settings_control/value_validation.py           |   4 +
 app/traffic_projection/config.py                   |  24 ++
 run.py                                             |  13 +-
 tests/admin_web/conftest.py                        |   9 +-
 tests/admin_web/feature_settings_stage6_ui.cjs     | 128 +++++++
 tests/admin_web/test_config.py                     |  11 +-
 tests/admin_web/test_device_current_context.py     |  23 +-
 tests/admin_web/test_feature_settings_stage6.py    | 203 ++++++++++++
 .../test_feature_settings_stage6_frontend.py       |  42 +++
 tests/admin_web/test_home_activity.py              |  12 +-
 tests/admin_web/test_home_health.py                |  12 +-
 tests/admin_web/test_home_live.py                  |  22 +-
 tests/admin_web/test_home_traffic.py               |  22 +-
 tests/admin_web/test_routes.py                     |  12 +-
 tests/admin_web/test_runtime.py                    |  26 +-
 tests/admin_web/test_settings_routes.py            |  18 +-
 tests/admin_web/test_traffic_ap.py                 |  25 +-
 tests/admin_web/test_traffic_ap_share.py           |  27 +-
 tests/admin_web/test_traffic_completed_sessions.py |  23 +-
 tests/admin_web/test_traffic_current.py            |  12 +-
 tests/admin_web/test_traffic_evidence.py           |  21 +-
 tests/admin_web/test_traffic_foundation.py         |  23 +-
 tests/admin_web/test_traffic_history.py            |  26 +-
 tests/admin_web/test_traffic_independent_ranges.py |  25 +-
 tests/admin_web/test_traffic_online_guests.py      |  23 +-
 tests/admin_web/test_traffic_peak.py               |  27 +-
 tests/admin_web/test_traffic_statistics.py         |   5 +-
 tests/analytics/test_feature_plan_stage6.py        |  80 +++++
 tests/analytics/test_runtime.py                    |  20 +-
 tests/settings_control/__init__.py                 |   8 +
 tests/settings_control/test_activation.py          |  15 +-
 .../test_controller_secret_repository.py           |   5 +-
 .../test_controller_secret_service.py              |   5 +-
 .../test_controller_secret_startup.py              |  11 +-
 tests/settings_control/test_controller_stage3.py   |   7 +-
 tests/settings_control/test_definitions.py         |   2 +-
 tests/settings_control/test_features_stage6.py     | 367 +++++++++++++++++++++
 tests/settings_control/test_portal_stage5.py       |   5 +-
 tests/settings_control/test_repository.py          |   4 +-
 tests/settings_control/test_run_integration.py     |  17 +-
 tests/settings_control/test_schema_v4_portal.py    |   4 +-
 tests/settings_control/test_schema_v5_features.py  | 119 +++++++
 tests/settings_control/test_secret_recovery_v5.py  |  73 ++++
 tests/settings_control/test_services.py            |   7 +-
 tests/settings_control/test_validation.py          |   2 +-
 63 files changed, 1941 insertions(+), 307 deletions(-)
```

HOLD FOR TECH LEAD REVIEW.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO

