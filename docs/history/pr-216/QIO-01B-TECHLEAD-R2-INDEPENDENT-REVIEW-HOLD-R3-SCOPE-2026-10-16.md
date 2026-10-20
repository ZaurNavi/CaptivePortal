# CaptivPortal — QIO-01B R2 — Tech Lead Independent Review / HOLD / R3 scope

**Date:** 2026-10-16, Asia/Baku. **Owner governance:** No commit/push/PR/merge/deploy; production unmodified.

## Exact candidate and evidence

- BASE HEAD `59aaac88e24ece85f448fab9bbef43cf9ff34de4`; BASE TREE `fa41c12252b7de664b2d2ba0a3e9db8c8b99721d`.
- Supplied R2 replacement patch 88,156 bytes SHA256 `1bded1b164750fe2856a2c57d5875fd4f063b3bb6e9a69e731e326061cbda86d`: independently verified.
- Independently reconstructed full R2 tree `6fa625eb263756024bef472fe1bb1cb5677a94bd` from baseline + patch. 22 changed files. Full submitted source SHA inventory matches local Coder worktree. R1's original 18 source files, including all seven production files, unchanged.
- R2 only changes four Settings Control test/helper files. Coder's evidence 896 unique PASS Linux / 780 PASS + 116 platform SKIP Windows is focused evidence only, not a full gate.

## Independently executed results

1. Linux complete `tests/settings_control`: **443 passed, zero failed**. Independent Windows original-codepage single-case reproduction: `tests/test_omada_strict_tls.py::test_inventory_covers_all_twelve_sites_without_global_trust_changes` **FAIL** UnicodeDecodeError with CP1251 when `Path.read_text()` omits encoding. `-X utf8` is not accepted as substitute for original Windows gate.
2. To conserve time, Tech Lead reconstructed a separate **LAB ONLY** one-line encoding-repair trial (the original Coder R2 worktree is not changed), adding `encoding="utf-8"` to that test source read. Independent exact LAB trial tree `0b0f1c698e9220a8ee9d9610976f64c66188b0aa` on Linux and Windows, clean QA worktrees. Single Windows case on that LAB trial: **PASS without UTF-8 interpreter switch**. Linux root-owned TLS fixture test file: **117 passed**.
3. **Important further independent scope discovery:** Five previously untested legacy suites (`tests/test_admin_controller_settings.py`, `tests/test_public_traffic.py`, `tests/observations/test_runtime.py`, `tests/pending_sessions/test_omada_reconnect_completion.py`, `tests/visitor_registry/test_snapshot_runtime.py`) give **100 passed / 33 failed** on the LAB trial. Fail breakdown: admin_controller 21, public_traffic 1, observations runtime 1, reconnect completion 2, visitor snapshot runtime 8. Most legacy positive fixtures contain forbidden `https://controller.invalid` / `verify_ssl=False`; reconnect two bare synthetic Provider mocks have no `_request` seam. The narrow reasons must each be verified and fixed without weakening behavioral assertions.
4. Because a full gate could no longer be all green, our QA Linux and Windows full runs were intentionally interrupted **before completion** to avoid monopolizing a shared lab concurrently running SSR tests. Both are **ABORTED/INCOMPLETE**, not PASS. Linux log `/home/zaur_navi/captivportal-lab/qio01b-techlead-linux-full-r3qa.log`. Windows lab log `C:\CaptivPortal-Lab\logs\lab-test-v9-qio01b-path-admission-20261016-113435-DETACHED.log`.
5. **Runner incident:** After its pytest subprocess was forcibly stopped at roughly 19% collection progress, the versioned Windows runner wrote `RESULT: PASS` without a full pytest summary or complete expected stage markers. This is false-positive truncated-gate evidence and must be treated as invalid; separately investigate robust detection of interrupted pytest in official runner management, but **do not fix runner as part of QIO-01B**. Original v7/v8 runners were not edited. The separate versioned v9 LAB runner changed only version text and allowed lab path.

## R3 authorized test-only scope

- Prior one-line-only instruction is superseded. **No new production code changes.** Coder may minimally adjust exactly these six additional existing test modules, subject to preserving all original correctness assertions and negative guards:
  - `tests/test_omada_strict_tls.py`: explicit UTF-8 text encoding for source inventory test.
  - `tests/test_admin_controller_settings.py`: admitted canonical Omada origin, true TLS and synthetic anchor/digest for positive composition/projection tests; preserve public projection assertions/provenance and explicit invalid test coverage.
  - `tests/test_public_traffic.py`: admitted positive startup mock configuration.
  - `tests/observations/test_runtime.py`: admitted positive startup mock configuration.
  - `tests/pending_sessions/test_omada_reconnect_completion.py`: local synthetic `_request` transport seam for two tests without bypassing the existing parser, mutation payload and token-cache assertions.
  - `tests/visitor_registry/test_snapshot_runtime.py`: admitted positive startup mock configuration and local composition fakes. No production change.
- All changes beyond those six (and four already approved R2 tests) require separate scope request.
- Must not change skips/xfails, runtime restrictions, assertions, service activation, transport or system trust. Coder must provide a new full replacement patch/hash/tree and focused Linux/Windows tests covering those six plus Settings and original Omada/CAPPORT targeted tests.
- The one-line LAB-only tree `0b0f1c69...` is **not** the expected final R3 tree once the six-file compatibility repair is included. The Coder R3 tree is to be freshly independently verified.

## Production preflight: RV-1 / RV-2 / RV-3

- Production VM `192.168.0.202` is still running previously accepted `main@59aaac88`. Read-only inspection confirmed `/etc/default/captive-portal` specifies `OMADA_URL=https://192.168.0.222:8043`, no `OMADA_TLS_TRUST_ANCHOR_PATH` or `OMADA_TLS_TRUST_ANCHOR_SHA256`. Read-only Settings SQLite has **no persisted `OMADA_URL` override**. No production config was changed.
- `Omada` name has no working resolution yet on Ubuntu. Controlled hosts/DNS and trust-file setup require separate Owner/SysAdmin GO before deployment.
- RV-1 independent Omada-side certificate export/provenance and Owner approval of trusted fingerprint remain pending. Network TLS presentation alone is insufficient trust.
- RV-3 focused Settings reconciliation PASS, but full legacy cross-module regression is **HOLD** until new R3 test-only fixes.

## Verdict

`R2_ACCEPTANCE=HOLD`

`R3_AUTHORIZED=TEST_COMPAT_REPAIR_ONLY`

`INDEPENDENT_LINUX_SETTINGS=443_PASS`

`INDEPENDENT_LINUX_ROOT_TLS=117_PASS`

`INDEPENDENT_LEGACY_CROSS_MODULE=100_PASS_33_FAIL`

`LINUX_FULL=ABORTED_INCOMPLETE`

`WINDOWS_FULL=ABORTED_INCOMPLETE_FALSE_PASS_LOG_INVALID`

`RV1=HOLD; RV2=HOLD; RV3=HOLD_BEYOND_SETTINGS`

`COMMIT_PUSH_PR=NO; PRODUCTION_ACTION=NO`
