# DEPLOY-CONFIG-02 — R3 W01 test portability correction

STATUS=READY_FOR_TECHLEADJR_INDEPENDENT_QA

## Exact identity

```ini
TASK=TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/captivprod-deploy-config-02
BRANCH=task/captivprod-deploy-config-02
HEAD=84b80376b13002d435be28eec98b91b9cbf71c63
BASE_TREE=fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8
PREVIOUS_R2_TREE=a787a5ad842aa72189423e0d0940567b31b1b953
R3_CANDIDATE_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
WORKTREE_STATE=DIRTY_UNCOMMITTED
PATCH_BYTES=69329
PATCH_SHA256=51c39c08c15663c0d4f9a8964c378257dae34be90edcbc7f6415805e11da7d55
```

Full replacement patch:
`C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-r3-20261015\TASK-CAPTIVPROD-DEPLOY-CONFIG-02-R3.patch`

Serialized against unchanged base HEAD with `git diff --binary --full-index --output=<patch>`. All four intent-to-add test files are included. The patch is a full replacement, not only the one-line repair. Fresh external-index reconstruction from exact base reproduces the R3 tree above. Reverse-apply check also PASS. No commit created; no candidate staging in the real Git index. Historical R2 artifacts/logs remain untouched.

## Authorized correction — exact one-line delta

Only this file differs from R2:
`tests/device_fingerprint_portal/test_deploy_isolation.py`

Only change:

```diff
-        assert str(path) == config.credential_path
+        assert path.as_posix() == config.credential_path
```

The assertion still checks the exact configured credential path, expressed lexically with POSIX separators on both platforms. No path fallback, partial match, basename-only comparison or normalization of expected identity was added. Bearer, CA/TLS, HTTP 200/401/403, exact producer/Site/source tuple, single transport call and no-identity-fallback assertions are unchanged.

`R2-to-R3.diff` retains the complete incremental diff. Byte checks prove the corrected file equals the R2 blob after exactly this single literal replacement. All **other 14 candidate files** are byte-identical to R2, including all three production files, T05 guard and T05 tests. No extra repo paths or untracked files exist.

## Complete BASE-to-R3 changed-file inventory

15 files, 888 insertions(+), 51 deletions(-):

```text
.env.example
app/device_fingerprint_portal/config.py
app/device_fingerprint_sensor/capture.py
app/device_fingerprint_sensor/config.py
docs/configuration.md
docs/modules/device-fingerprint-portal.md
docs/modules/device-fingerprint.md
tests/device_fingerprint_portal/test_deploy_config.py
tests/device_fingerprint_portal/test_deploy_isolation.py
tests/device_fingerprint_sensor/test_cli.py
tests/device_fingerprint_sensor/test_config.py
tests/device_fingerprint_sensor/test_deploy_config.py
tests/device_fingerprint_sensor/test_deploy_preflight.py
tests/device_fingerprint_sensor/test_producer.py
tests/device_fingerprint_sensor/test_runtime.py
```

Exactly three authorized production files relative to base; **zero production changes in this R3 repair**. No new test file was introduced by R3. Full source byte counts and current/R2 SHA256 pairs are in `verification.json`. `git-status.txt` and `diff-stat.txt` retain the observed dirty state and complete diff stat.

## Required focused results

| Execution | Passed | Failed/errors | Skipped |
| --- | ---: | ---: | ---: |
| Windows original three W01 cases: 200, 401, 403 | 3 | 0 | 0 |
| Windows complete 11-file Sensor/Portal suite | 271 | 0 | 0 |
| Linux complete identical 11-file suite | 271 | 0 | 0 |
| Linux T05 complete selected file | 33 | 0 | 0 |

Durations reported by pytest: Windows three 3.09s; Windows focused 10.90s; Linux focused 2.21s; Linux T05 0.45s. No skips/xfails added or assertions weakened. XML verification confirms the **same 271 exact test IDs** ran and passed on both platforms. The three formerly failing Windows cases are an exact subset; all 33 T05 IDs are an exact subset of the focused suites. These run counts overlap and are not summed as distinct tests.

### Environments

- Linux: WSL Ubuntu-22.04, Python 3.10.12, pytest 9.1.1, SQLite 3.37.2. Interpreter `/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`; SHA256 `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`.
- Windows: Python 3.10.11, pytest 9.1.1, SQLite 3.40.1. Interpreter `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`; SHA256 `b2c836c52cdf063180b9ee76f67ac42946101b79ac457f3494035a67c090d961`.
- Windows execution cwd was the **same Coder worktree via UNC**, not the main checkout: `\\wsl.localhost\Ubuntu-22.04\home\zaur_navi\captivportal-lab\worktrees\captivprod-deploy-config-02`. Existing QA worktrees were not edited. No synthetic commit or new Windows repo materialization was required.
- Bytecode and pytest temporary output were external to Git. No package/environment installation or production access occurred.

### Exact focused commands

Common explicit 11-file set (no directory-wide/full collection):

```text
tests/device_fingerprint_sensor/test_config.py
tests/device_fingerprint_sensor/test_runtime.py
tests/device_fingerprint_sensor/test_cli.py
tests/device_fingerprint_sensor/test_producer.py
tests/device_fingerprint_sensor/test_deploy_config.py
tests/device_fingerprint_sensor/test_deploy_preflight.py
tests/device_fingerprint_portal/test_config.py
tests/device_fingerprint_portal/test_privacy.py
tests/device_fingerprint_portal/test_producer.py
tests/device_fingerprint_portal/test_deploy_config.py
tests/device_fingerprint_portal/test_deploy_isolation.py
```

Windows PowerShell, from the UNC Coder worktree:

```powershell
$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\deploy-config-02-r3-pycache'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider 'tests/device_fingerprint_portal/test_deploy_isolation.py::test_T07_T08_T09_portal_exact_transport_tuple_and_verified_ca_injection' --basetemp=C:\CaptivPortal-Lab\tmp\deploy-config-02-r3-windows-three --junitxml=C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-r3-20261015\windows-three.xml
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider tests/device_fingerprint_sensor/test_config.py tests/device_fingerprint_sensor/test_runtime.py tests/device_fingerprint_sensor/test_cli.py tests/device_fingerprint_sensor/test_producer.py tests/device_fingerprint_sensor/test_deploy_config.py tests/device_fingerprint_sensor/test_deploy_preflight.py tests/device_fingerprint_portal/test_config.py tests/device_fingerprint_portal/test_privacy.py tests/device_fingerprint_portal/test_producer.py tests/device_fingerprint_portal/test_deploy_config.py tests/device_fingerprint_portal/test_deploy_isolation.py --basetemp=C:\CaptivPortal-Lab\tmp\deploy-config-02-r3-windows-focused --junitxml=C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-r3-20261015\windows-focused.xml
```

Linux native shell, from the Coder worktree:

```bash
export PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/captivprod-deploy-config-02-pycache
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pytest -q -p no:cacheprovider tests/device_fingerprint_sensor/test_config.py tests/device_fingerprint_sensor/test_runtime.py tests/device_fingerprint_sensor/test_cli.py tests/device_fingerprint_sensor/test_producer.py tests/device_fingerprint_sensor/test_deploy_config.py tests/device_fingerprint_sensor/test_deploy_preflight.py tests/device_fingerprint_portal/test_config.py tests/device_fingerprint_portal/test_privacy.py tests/device_fingerprint_portal/test_producer.py tests/device_fingerprint_portal/test_deploy_config.py tests/device_fingerprint_portal/test_deploy_isolation.py --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/captivprod-deploy-config-02-r3-20261015/linux-focused.xml
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pytest -q -p no:cacheprovider tests/device_fingerprint_sensor/test_deploy_preflight.py --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/captivprod-deploy-config-02-r3-20261015/linux-t05.xml
```

Each invocation retained full output in the matching `.log` beside `.xml`; all exit codes were 0. Windows logs use PowerShell output encoding; JUnit files remain machine-readable XML.

## Static / integrity checks

- `compileall -q` on all 11 changed Python source/test files: PASS on Windows and Linux, exit 0. Exact file set: the three production files plus all eight tests in the inventory. Respective interpreter and external bytecode prefix as above; both `*-compileall.log` files are empty (no diagnostics).
- `git diff --check`: PASS, no whitespace exceptions.
- Exact changed-file allowlist: PASS (15 files; 3 production).
- No source/test/doc change beyond the one approved assertion relative to R2: PASS.
- All production Git blobs unchanged from R2: PASS; T05 fix and tests byte-identical: PASS.
- Other 14 changed-candidate files compared byte-for-byte and by SHA256 to their R2 tree blobs: PASS.
- Full replacement patch reverse check and fresh external-index reconstruction: PASS.
- No new credential material or secret/payload-bearing data: exact one-line lexical assertion replacement only. No real keys/certificates/tokens introduced or logged.

Machine-verifiable proof: `verify_r3_handoff.py`, `verification.log`, `verification.json`. The verifier and external temporary Git indexes are handoff-only and outside the repository. The complete original R2 native Linux real-symlink proof remains historical evidence; R3 does not claim it was rerun. T05 source and tests are unchanged and the explicitly required 33-case Linux T05 execution was rerun successfully.

## Remaining independent acceptance

This is Coder focused verification, **not official release acceptance**. Official Windows V7, complete Linux release gate, actual disposable TLS receiver and admission/provenance matrices remain TechLeadJR/Owner responsibilities. No full/Central suite was run. The previously interrupted Linux full run is not a PASS and is not presented as current full evidence. DEPLOY-CONFIG-01 exception does not transfer to this task.

```ini
W01=FIXED_TARGETED_PASS
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
SERVICE_RESTART=NO
PRODUCTION_ACTION=NO
CODER_HOLD=YES
NEXT_ACTION=TECHLEADJR_R3_INDEPENDENT_QA
```
