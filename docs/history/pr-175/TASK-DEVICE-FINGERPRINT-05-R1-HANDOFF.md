# TASK-DEVICE-FINGERPRINT-05-R1

```text
TASK = TASK-DEVICE-FINGERPRINT-05-R1
STATUS = IMPLEMENTED
BASE = 1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22
BASE_TREE = 8183bf48abfc71c1b488c0667efc0f1ae717003e
BRANCH = fix/device-fingerprint-05-r1-executable-identity
COMMIT = 1bb7f73d9977c457da05af26bf28b30c3c7e06d8
TREE = 545a48caf86adc247083db611e87a8d36820f353

FILES_CHANGED =
app/device_fingerprint_integration/compatibility.py
tests/device_fingerprint_integration/test_executor_persistence.py

ROOT_CAUSE = The full admitted identity tail, including its slash discriminator, was incorrectly traversed as a Python dotted attribute path.
REPAIR = Separate the symbol at the first slash; validate non-empty dotted Python identifiers; retain the full identity and unchanged path/origin/full-file digest checks.

TARGETED_TESTS = 32 passed / 0 skipped / 0 failed / 0 errors (25.76s)
PRODUCTION_SHAPED_IDENTITY_REGRESSION = PASS
NO_SUFFIX_IDENTITY_REGRESSION = PASS
BAD_SYMBOL_FAIL_CLOSED = PASS
EMPTY_SYMBOL_FAIL_CLOSED = PASS
MALFORMED_DOTTED_SYMBOL_FAIL_CLOSED = PASS
BAD_DIGEST_FAIL_CLOSED = PASS
PATH_ESCAPE_FAIL_CLOSED = PASS
MISSING_IDENTITY_LIST_FAIL_CLOSED = PASS
SOURCE_ORIGIN_MISMATCH_FAIL_CLOSED = PASS
EVIDENCE_CANONICAL_IDENTITY = PASS
CORRUPTED_EVIDENCE_CANONICAL_DIGEST_FAIL_CLOSED = PASS
PY_COMPILE = PASS
DIFF_CHECK = PASS
WORKING_TREE = CLEAN

UNRELATED_CHANGES = NONE
PRODUCTION_ACTIONS = NONE
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
FULL_TESTS_RUN = NO
CENTRAL_LAB_RUN = NO
CANDIDATE_ACCEPTED = PENDING_TECH_LEAD_REVIEW

PATCH_PATH = C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-R1_BASE-to-R1.patch
PATCH_BYTES = 6609
PATCH_SHA256 = a0e6921809ed8fbea3ca8ce605541180d7a1578ac9d2560d2a993b7cd3e34d37
REVERSE_APPLY_CHECK = PASS
```

## Exact focused execution

Environment: Windows, Python 3.10.11, local disposable fixtures only. Workdir: `C:\CaptivPortal-Lab\coder-task05-identity-session`.

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\task05-r1-pyc'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q tests/device_fingerprint_integration/test_executor_persistence.py --basetemp=C:\CaptivPortal-Lab\tmp\task05-r1-focused-20261004-01 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-R1-focused.xml
# 32 passed in 25.76s

& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m py_compile app/device_fingerprint_integration/compatibility.py
# PASS

git diff --stat 1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22...HEAD
git diff --check 1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22...HEAD
# PASS
```

## Diff evidence

```text
git diff --name-status 1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22...HEAD
M app/device_fingerprint_integration/compatibility.py
M tests/device_fingerprint_integration/test_executor_persistence.py

git diff --stat 1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22...HEAD
 .../compatibility.py                               |  5 +-
 .../test_executor_persistence.py                   | 67 +++++++++++++++++++++-
 2 files changed, 70 insertions(+), 2 deletions(-)

git status --short
<empty>
```

The binary-capable full-index BASE-to-R1 patch was exported from the exact local commit. Its reverse applicability was checked without applying or changing repository files. Patch and test evidence remain outside Git.

## Regression coverage and boundaries

The normal `prepared_production()` fixture now uses `DeviceFingerprintOriginAssessmentBuilder.build/dhcp/1/FUSION`, so existing normal Task-05 preflight, executor and persistence tests exercise the real admitted identity syntax.

Additional focused cases cover mac_registry/FUSION, dhcp/1/FUSION, portal_headers/2/OPTIONAL_IF_ADMITTED, tcp_syn/1/NON_FUSION_HANDLER, the legacy no-suffix identity, missing/empty/malformed Python symbols, canonical JSON digest verification and source-origin mismatch. Existing bad-adapter-digest, path-escape and empty-identity-list tests remain intact.

The repair neither rewrites full identity/digest values nor interprets discriminator components. No source-kind/schema/mode semantics, Task-04 artifacts, public reason codes, terminal job/retry/lease/persistence semantics, production data, profiles, activation state, configuration or services were changed. Test-created synthetic contents are disposable local fixtures only.

No new test file was added. The only modified existing test file is the authorized integration executor/persistence file. No cross-module, full or official Central Lab execution was performed. Tech Lead review and broader acceptance gates remain pending; production acceptance is not claimed.
