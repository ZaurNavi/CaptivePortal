# TASK-ADMIN-SETTINGS-04 — local candidate handoff (Scope Extension 01)

Status: READY_FOR_TECH_LEAD_SOURCE_REVIEW. This is a local implementation candidate, not a production acceptance or publication verdict.

## Exact identity

```ini
TASK=TASK-ADMIN-SETTINGS-04
BASE_HEAD=430acb4f235a606f05acc78e7f983824e4448644
BASE_TREE=06e0edf54f37e4b9a3d4c3b8f3a1f37b181c3b3b
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-04
BRANCH=feature/admin-settings-04-controller-secret-management
CANDIDATE_COMMIT=698ba5b03887c90181cf78d63e156a7a965fe802
CANDIDATE_PARENT=430acb4f235a606f05acc78e7f983824e4448644
CANDIDATE_TREE=6933ebad3cf83ea9529744f0ad73f1c4697dbedc
SUBJECT=ADMIN-SETTINGS-04: add write-only Omada client secret management
LOCAL_CANDIDATE_COMMITS=1
WORKTREE_STATE=CLEAN
GIT_STATUS_PORCELAIN=<empty>
CHANGED_FILES=40
ADDITIONS=1730
DELETIONS=96

FULL_BASE_TO_CANDIDATE_PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-04-SCOPE01_BASE-to-CANDIDATE.patch
FULL_PATCH_BYTES=159300
FULL_PATCH_SHA256=1594fe05a834692755a0b9565d3b679b915e4c4f10ecabd3dcc6caec7f210281
PATCH_FORMAT=git diff --binary --full-index BASE CANDIDATE
PATCH_REVERSE_APPLY_CHECK=PASS
GIT_DIFF_CHECK=PASS
```

The complete patch is against the newly authorized exact baseline, not the superseded pre-NI baseline and not merely the final validation-boundary edit. Patch reverse-check did not apply or mutate files.

## Scope Extension 01

The preserved dirty implementation was continued without reset, clean, checkout, stash, rebase, or discard. `app/settings_control/validation.py` is the only newly scope-authorized production file.

`SettingsValidationService.validate(snapshot, *, secret_resolution=None)` passes the original mapping and a separate `OmadaClientSecretResolution` into `build_omada_runtime_config(snapshot.values, secret_resolution=secret_resolution)`. Missing or incorrectly typed resolution safely fails as `422 validation_failed / controller_prerequisite_invalid`, even if a disposable legacy test snapshot contains a raw secret. No validator fallback reads that field.

Both enabled production callers explicitly provide the resolution: bootstrap and ordinary General/Controller mutation. The temporary replacement snapshot/raw-secret insertion is removed. The validator retains neither resolution nor raw secret. Deployment fallback validation on managed-secret clear also uses a separate resolution instead of inserting a raw secret into a copied ordinary mapping.

Primitive, existing Admin/Home/Current-State semantic validation and canonical Controller prerequisite validation remain active. Synthetic tests prove original mapping identity, keyword-only resolution, no ordinary snapshot contamination, safe missing-resolution failure, and no durable generation after that failure.

## Implementation / architecture mapping

| Requirement | Implementation / local evidence |
|---|---|
| Exactly one write-only secret, no ordinary definition/override | `controller_secret.py`, ordinary registry unchanged; snapshot and ordinary projection sentinel tests |
| v2 to v3 in the same SettingsStore | `repository.py`: typed idempotency, live encrypted versions, immutable bindings, safe secret audit; migration tests preserve both General and Controller audit and exact old receipts |
| Generation 0 system identity | Existing `system / settings_bootstrap` invariant retained; generation 0 has no secret binding |
| Managed > deployment/environment > repository default | One startup resolution, separate from ordinary snapshot; managed failure cannot fall back |
| AES-256-GCM / fixed encrypted frame | 4100-byte frame, 4116-byte ciphertext/tag, 12-byte random nonce, UUIDv4 AAD, random padding, HKDF-SHA256 separated encryption/idempotency keys |
| Exact file-security boundaries | No-follow opened-object checks and metadata policy; no chmod/chown/chgrp repair authority; disposable Linux/fake-metadata tests |
| Logical live-secret retention | Configured/effective versions only; failed adoption retains effective version, successful adoption removes superseded live rows; historical bindings can outlive ciphertext |
| HMAC idempotency | Domain/principal/operation/key-bound fingerprint, read-only replay/conflict before writer, writer recheck, shared generation CAS, exact safe receipt replay at HTTP 200 |
| Existing ordinary Settings semantics | General still returns ordered twelve integer settings; Controller still has exactly three writable non-secret strings; binding copied on ordinary changed generations |
| Independent GLOBAL authorization | Code-owned recognized capabilities; strict startup parser; immutable session grant; default four capabilities exclude secret write; no Site authority |
| Write-only Controller v3 | Safe presence/source/ownership/pending/store-state fields only; ordinary and secret mutation availability independent; effective-only safe read on ordinary Store outage |
| Exact secret endpoint | Session/read+secret capability, CSRF, quoted ETag, UUIDv4, bounded body, strict JSON, safe closed public errors; internal secret dependency categories map to secret-store-unavailable on HTTP mutation |
| Safe UI | Two empty password inputs, new-password autocomplete, paste allowed, no secret confirmation/read-back/storage, finally clears values and drops payload/body references, only retry key retained on network uncertainty, GET after receipt |
| Startup/adoption ordering | Existing prepare-read-boundary -> Analytics/Admin composition -> durable adoption -> provider-capable starts -> HTTP serve retained; local synthetic ordering tests prohibit pre-adoption provider calls |
| Recovery | Local stopped-service CLI, secure existing schema-v3 DB, expected-generation CAS, no decrypt/key read, safe local-operator audit, normal generation without secret binding |
| No systemd/activation authority in Admin | No restart/connection-test/hot-reconnect handler; only external operator restart/adoption, documented backup/downgrade/security boundary |
| Validation scope extension | Separate explicit resolution into the canonical builder; no replacement `ResolvedSettingsSnapshot` with raw secret |

## SQLite and security results

```ini
SCHEMA_VERSION=3
MIGRATION_V2_TO_V3=PASS
MIGRATION_V1_UPGRADE_COMPATIBILITY=PASS
MIGRATION_HISTORY_PRESERVATION=PASS
GENERATION_0_IDENTITY=system / settings_bootstrap
GENERATION_0_SECRET_BINDING=ABSENT
SCHEMA_NEW_TABLES=controller_secret_versions,settings_secret_bindings,settings_secret_mutation_audit
IDEMPOTENCY_FINGERPRINT_KINDS=sha256_canonical_json_v1,hmac_sha256_controller_secret_v1
IDEMPOTENCY_DOMAINS=general,controller,controller_secret
CRYPTOGRAPHY_VERSION=3.4.8
AESGCM_IMPORT=PASS
HKDF_IMPORT=PASS
SHA256_IMPORT=PASS
CRYPTO_TARGETED_TESTS=PASS (included in focused result)
PACKAGE_INSTALL=NO

GLOBAL_CAPABILITY_DEFAULT=admin.read.settings.global,admin.write.settings.global,admin.read.settings.controller,admin.write.settings.controller
SECRET_CAPABILITY=admin.write.settings.controller.secret
SECRET_CAPABILITY_DEFAULT_GRANTED=NO
SECRET_STORE_DB_SECURITY=PASS (disposable/fake metadata + Linux no-follow focused checks)
MASTER_KEY_SECURITY=PASS (disposable/fake metadata + Linux no-follow focused checks)
SECRET_STORE_STATE_TESTS=PASS

RAW_SECRET_IN_SETTINGS_OVERRIDES=NO
RAW_SECRET_IN_PUBLIC_API=NO
RAW_SECRET_IN_AUDIT=NO
RAW_SECRET_IN_IDEMPOTENCY_RESPONSE=NO
RAW_SECRET_IN_DB_FILE_SENTINEL_SCAN=NO
RAW_SECRET_IN_LOG_SENTINEL_SCAN=NO
PRE_ADOPTION_PROVIDER_CALLS=0 (synthetic targeted ordering evidence)
CONTROLLER_READ_MODEL_VERSION=admin.settings.controller.v3
SECRET_MUTATION_API=POST /admin/api/v1/settings/controller/client-secret/generations
BREAK_GLASS_COMMAND=python3 -m app.settings_control.secret_recovery clear-omada-client-secret --expected-generation <N>
```

Sentinel checks refer to disposable test secrets, database files, responses, rendered HTML, model repr and captured local application logs, not production inspection. Crypto test vector pins both HKDF outputs for a disposable 32-byte master, with AESGCM round-trip/authentication/fixed-frame tests on cryptography 3.4.8.

Managed missing-version validation fails before a usable repository is constructed; no successful adoption or fabricated failure event is written in that case. Other managed dependency failures are durably attested when the usable Settings repository permits it. No-managed startup is tested with unavailable master key and with failed secret DB-security checks; valid deployment secret remains usable while secret management is unavailable.

Logical secret GC is not a guarantee of forensic erasure of historical DB/WAL/backups/storage. Production provisioning, real key/DB permissions, deployment, browser acceptance, and independent full regression remain Owner/Tech Lead actions.

## Exact verification

Environment: existing local WSL `Ubuntu-22.04`, Python 3.10.12, system cryptography 3.4.8, existing pytest 9.1.1 dependencies, plugin autoload disabled. No installation/upgrade/downgrade. Bytecode was directed outside the repository to `/tmp/as04-pycache`. Node v24.19.0 was used only for the required syntax check.

The two executed targeted commands share this PowerShell prefix:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-04 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as04-pycache python3 -m pytest -q <explicit file list below>
```

Focused Stage-4 + directly affected validator file list:

```text
tests/settings_control/test_controller_secret_crypto.py
tests/settings_control/test_controller_secret_repository.py
tests/settings_control/test_controller_secret_service.py
tests/settings_control/test_controller_secret_startup.py
tests/settings_control/test_secret_recovery.py
tests/admin_web/test_controller_settings_stage4.py
tests/admin_web/test_global_capabilities_stage4.py
tests/settings_control/test_validation.py
```

Final result: **126 passed, 0 failed, 0 skipped (5.77s)**.

Directly affected Settings/Admin compatibility file list:

```text
tests/settings_control/test_repository.py
tests/settings_control/test_services.py
tests/settings_control/test_bootstrap.py
tests/settings_control/test_run_integration.py
tests/settings_control/test_controller_stage3.py
tests/admin_web/test_config.py
tests/admin_web/test_settings_routes.py
tests/admin_web/test_controller_settings_stage3.py
tests/test_admin_controller_settings.py
tests/test_omada_configuration.py
```

Final result: **214 passed, 0 failed, 0 skipped (16.75s)**. Total final targeted checks: **340 PASS**. No full repository suite, unrelated module suite or Central Lab runner was executed. Existing run-integration fixtures are the explicitly authorized directly affected startup boundary, not an official integration gate.

Required static checks:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-04 --exec env PYTHONPYCACHEPREFIX=/tmp/as04-pycache python3 -m compileall -q app run.py
node --check app/admin_web/static/controller_settings.js
git diff --check
git diff --check HEAD^ HEAD
git apply --reverse --check C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-04-SCOPE01_BASE-to-CANDIDATE.patch
```

All returned exit status 0. Worktree remained clean after the commit and patch check. Tests ran against the final source content before the single local commit; staged tree and committed tree were verified equal. No source changed after those final tests.

```ini
TARGETED_TEST_RESULT=126 PASS / 214 PASS; failed=0; skipped=0
COMPILEALL=PASS
NODE_CHECK=PASS
GIT_DIFF_CHECK=PASS
FULL_REPOSITORY_PYTEST=NOT_RUN_BY_CODER_PER_TASK
CENTRAL_LAB=NOT_RUN; pending Owner/Tech Lead
ARCHITECTURE_AMBIGUITY=NONE
OPEN_P0=0 known to Coder; independent source review pending
OPEN_P1=0 known to Coder; independent source review pending
CANDIDATE_ACCEPTED=NO (awaiting Tech Lead review / required independent gates)
```

An intermediate new HTTP test used an empty `CONTENT_LENGTH` string, which represents zero rather than a missing length in the test stack. The fixture was corrected to an absent (`None`) value; the production 411 rule was not weakened. Final tests are green. UI verification here is rendered/static source-contract testing, not an interactive browser acceptance claim.

## Exact changed-file list (Git name-status)

Paths below are relative to `C:\CaptivPortal-Lab\coder-admin-settings-04`. New test files are the `A tests/.../test_*.py` rows; the new `stage4_helpers.py` is disposable test support only. No generated corpora, databases, keys, production secrets, bytecode, logs, or unrelated Lab artifacts are committed.

```text
M .env.example
A app/admin_web/capabilities.py
M app/admin_web/config.py
M app/admin_web/controller_settings.py
M app/admin_web/models.py
M app/admin_web/policy.py
M app/admin_web/routes.py
M app/admin_web/runtime.py
M app/admin_web/static/controller_settings.js
M app/admin_web/templates/admin/settings_controller.html
M app/config.py
M app/controllers/omada_config.py
M app/settings.py
M app/settings_control/activation.py
M app/settings_control/bootstrap.py
A app/settings_control/controller_secret.py
M app/settings_control/models.py
M app/settings_control/repository.py
A app/settings_control/secret_recovery.py
M app/settings_control/services.py
M app/settings_control/validation.py
M docs/configuration.md
M docs/deployment.md
M docs/modules/admin-web.md
M requirements.txt
M run.py
M tests/admin_web/test_controller_settings_stage3.py
A tests/admin_web/test_controller_settings_stage4.py
A tests/admin_web/test_global_capabilities_stage4.py
M tests/admin_web/test_settings_routes.py
A tests/settings_control/stage4_helpers.py
A tests/settings_control/test_controller_secret_crypto.py
A tests/settings_control/test_controller_secret_repository.py
A tests/settings_control/test_controller_secret_service.py
A tests/settings_control/test_controller_secret_startup.py
M tests/settings_control/test_controller_stage3.py
M tests/settings_control/test_repository.py
A tests/settings_control/test_secret_recovery.py
M tests/settings_control/test_validation.py
M tests/test_admin_controller_settings.py
```

`git diff --stat BASE CANDIDATE`: **40 files changed, 1730 insertions(+), 96 deletions(-)**. Production/source/config/document files implement only authorized Stage-4 boundaries (plus approved `validation.py` extension); modified existing tests are direct compatibility/schema/read-model/helper adjustments. The complete per-file diff is in the attached binary-capable patch.

## Preserved NI worktree and actions

Read-only verification of `C:\CaptivPortal-Lab\coder-dti-ni-01`:

```ini
NI_HEAD=f3a69e90fd48381889bcd32d5158fbbb359f446d
NI_TREE=0a0ec87cd26d63b321ce62446178f4d8ab46cc02
NI_STATUS_PORCELAIN=<empty>
NI_WORKTREE_UNCHANGED=YES
```

Agent execution summary: Codex desktop / implementation mode; preserved isolated Settings04 worktree; implemented only approved scope; completed targeted local checks; created exactly one local candidate commit and exported full patch. No subagents, package installation, remote publication, official gate, production access, service restart or deployment. Scope Extension 01 resolved the reported validation-boundary blocker. Review/acceptance remains Tech Lead/Owner-controlled.

```ini
COMMIT=ONE_LOCAL_CANDIDATE
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_TEST=NO
SERVICE_RESTART=NO
SYSTEMD_ACTION=NO
PRODUCTION_ACTION=NO
```

HOLD for Tech Lead source review. No further implementation/publication action is taken in this handoff.
