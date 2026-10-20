# CaptivPortal — QIO-01B Option B — Tech Lead independent R1 source review

**Date:** 2026-10-16 (Asia/Baku)  
**Status:** `SOURCE_REVIEW=CONDITIONAL_PASS`, `RV3_TEST_GATE=FAIL`, `FINAL_ACCEPTANCE=HOLD`, `CODER_R2=GO_TEST_COMPAT_ONLY`, `GITHUB=NO`, `PRODUCTION=NO`.

## Immutable candidate being reviewed

- Base HEAD `59aaac88e24ece85f448fab9bbef43cf9ff34de4`, base tree `fa41c12252b7de664b2d2ba0a3e9db8c8b99721d`.
- R1 candidate tree as declared by Coder: `607f97855d7895a5a0181f233e2dd7c5d2686e0e` (not an independently accepted final tree).
- Attached patch SHA-256 verified by Tech Lead: `6db46e2dc85d793e82a6f73ff11e77fc9820713e2249c53167a785a8364993d8` (75,782 bytes).
- 18 changed files per evidence: 7 authorized production, 2 docs, 9 tests/test-support. No source commit, push, PR or deployment authorized.

## Source-level result

1. One Option B only. `OmadaProvider._request` delegates to `_OmadaVerifiedTransport`, with 12 inventoried HTTP call sites: 7 provider, 3 pending sessions, 2 observations. Source has a per-provider strict `SSLContext` and Sessions with `trust_env=False`, `allow_redirects=False`; checks prevent unexpected origin/proxy/Host overrides. There is no approved `verify=False` fallback or blanket warning suppression.
2. `get_sites()` now raises `ControllerError` on unavailable authority instead of silently converting such failure to `[]`. This is a deliberate contract change and needs regression coverage.
3. The strict policy requires independently approved root-owned PEM, SHA-256, `Omada` hostname and DNS/hosts mapping; no production deployment is possible before RV-1 and RV-2. The actual controller's certificate has SAN `DNS:Omada` and is not currently a trusted Owner-certified anchor.
4. Settings compatibility is **not resolved**. Shared test fixtures and some behavior tests still use `https://controller.invalid` and `verify_ssl=False`, which the new policy intentionally rejects.
5. The source review does not constitute live Omada/OpenAPI acceptance, complete Windows/Linux regression, proof of token/auth/unauth behavior against actual controller, nor any physical HDD I/O improvement.

## Verification of supplied Coder focused evidence

Tech Lead independently parsed the five supplied JUnit XML files in the ZIP: **282 test executions, 262 distinct testcase IDs, 0 fail/error/skip**. This verifies the consistency of the Coder-supplied records, not an independent rerun of these 262 focused tests.

## Independent targeted gate (not a Coder claim)

Executed read-only on Central Lab WSL Ubuntu, unchanged R1 worktree based on `59aaac88`, using isolated external pytest `--basetemp`:

`python -m pytest -q -p no:cacheprovider --basetemp=/tmp/qio01b-techlead-settings-r1 tests/settings_control`

**Observed: `272 PASSED / 154 FAILED`**, exit code 1, elapsed approximately 9.02 seconds. Out of 154 failures, 148 ended in `SettingsError: validation_failed`; six ended with assertion mismatch. A representative trace shows `tests/settings_control/__init__.py:8-9` defines `CONTROLLER_BASE` with `omada_url=https://controller.invalid`, `verify_ssl=False`. The new `normalize_controller_setting('OMADA_URL', ...)` rejects this input through `app/settings_control/value_validation.py`. Broad full gates intentionally not started because this independently established blocker must be repaired first.

Failing modules (number of cases):

- `test_features_stage6.py` 67
- `test_controller_stage3.py` 12
- `test_validation.py` 11
- `test_controller_secret_startup.py` 10
- `test_run_integration.py` 10
- `test_portal_stage5.py` 9
- `test_services.py` 7
- `test_controller_secret_repository.py` 6
- `test_controller_secret_service.py` 6
- `test_activation.py` 5
- `test_controller_secret_crypto.py` 3
- `test_secret_recovery.py` 3
- `test_repository.py` 2
- `test_secret_recovery_v4.py` 2
- `test_resolver.py` 1

## Tech Lead narrow authorization: R2 test-contract reconciliation

**GO for changing ONLY `tests/settings_control/__init__.py` and the 15 above-named failing test modules, to the extent necessary for the strict TLS contract.** No additional production/source files are approved. Preserve the Option B implementation and 12 request sites unchanged unless a specific code defect is independently demonstrated; request a separate scope decision then.

Coder must:

1. Update **positive** Controller test fixtures to valid strict `https://Omada:8043`, `verify_ssl=True`, a synthetic absolute approved trust path and 64-char SHA-256 for pure settings validation. For tests that really instantiate a provider, isolate certificate admission with a local/test-only fixture or explicit mock at the correct boundary; do not disable real transport verification or require a production secret.
2. Preserve explicit **negative** tests for invalid URL/IP/hostname, missing bundle/digest, `verify_ssl=False`, invalid persisted overrides and unavailable authority. A configured invalid URL must fail validation, not be silently rewritten by code.
3. Retain prior assertions and scenarios for Settings CAS, audit, history, idempotency, atomic mutations, rollback, adoption generation, fail-closed, secret write-only, recovery, feature gates and run composition. No `skip`, `xfail`, blanket deselection, broad monkeypatching, or weakened assertions.
4. Distinguish the six independent assertion failures from the 148 fixture-validation failures. Explain and repair each without changing unrelated product expectations.
5. Run the complete `tests/settings_control` focused suite and directly affected Admin/Controller/Omada suites on Linux, and the available relevant Windows focused suite. The latter may require test-only POSIX fixture routing for actual root-owned cert admission, but never skip generic cross-platform Settings behavior. Supply exact ID inventory, source diff, patch hash and candidate tree.
6. Ensure source tests exercise real `get_sites` success and failure; all 12 sites remain in the one verified transport.
7. Handoff only: `COMMIT=PUSH=PR=DEPLOY=NO`. Tech Lead will repeat independent targeted gates, then complete strict Windows and full Linux gates, certificate provenance/actual request validation and required performance evidence.

## Operational holds independent of test fixes

- **RV-1:** Owner/SysAdmin independently export and approve the actual Omada public certificate; confirm SHA and root-owned trust file. TLS handshake alone is not provenance.
- **RV-2:** Owner/SysAdmin-authorized local `Omada → 192.168.0.222` address mapping and strict DNS/SNI/Host validation, with proxy bypass audit.
- **RV-3:** Settings test contract and effective persisted Controller settings must be reconciled. Existing persisted `OMADA_URL` overrides might have priority over environment and must be reviewed; production cannot be switched blindly.
- Deploy requires a separate Owner GO and a night maintenance window because this change affects the **main `captive-portal.service` runtime**, unlike QIO-01A worker-only restart.

**Disposition: `R1=HOLD`, `R2_CODER_TEST_ONLY=GO`, `FULL_GATES=TECHLEAD_AFTER_R2`, `PRODUCTION=NO`.**
