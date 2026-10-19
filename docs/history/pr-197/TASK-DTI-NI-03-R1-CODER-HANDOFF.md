# TASK-DTI-NI-03 — R1 REVIEW CANDIDATE

BASE_HEAD=51deead342bd821b5c46fb75a7ceef37bef63e7c
BASE_TREE=7b6cfa20c23c097e87059ca12a593f697f0a36a2
HEAD_REMAINS=51deead342bd821b5c46fb75a7ceef37bef63e7c
WORKTREE=C:\CaptivPortal-Lab\coder-dti-ni-03
BRANCH=feature/dti-ni-03-protocol-intelligence
WORKTREE_STATE=DIRTY / UNCOMMITTED

## Repairs

- P1-01: availability is usable exactly when projection is usable and identity is authoritative; otherwise degraded. Semantic construction, server publication validation and browser validation use this rule. Coverage and freshness mappings remain unchanged.
- P1-02: authenticated session, exact Site, device capability, forbidden inputs and canonical Device ID precede the feature-OFF gate. The existing canonical_device_id helper is reused. Feature OFF never calls Device lookup or semantic/projection reads.

FILES_CHANGED_SINCE_PREVIOUS_CANDIDATE (exactly seven):

```
app/admin_web/routes.py
app/admin_web/static/device_protocol_intelligence.js
app/network_protocol_intelligence/models.py
app/network_protocol_intelligence/read_service.py
tests/admin_web/device_protocol_intelligence.cjs
tests/admin_web/test_device_protocol_intelligence.py
tests/network_protocol_intelligence/test_read_service.py
```

The previous tree is ece007c668c22471f802251ac8369369ad7e278d. Tree-to-tree scope comparison verifies no other file changed during R1, including all explicitly protected files.

## Authorized verification

Environment: Windows PowerShell, Python 3.10.11, Node v24.19.0.

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\ni03-pycache'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q tests/network_protocol_intelligence/test_read_service.py tests/admin_web/test_device_protocol_intelligence.py tests/admin_web/test_device_protocol_intelligence_frontend.py tests/admin_web/test_routes.py --basetemp 'C:\CaptivPortal-Lab\tmp\ni03-r1-20261010-02' --junitxml='C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-03-R1-final-focused.xml'
```

FINAL_RESULT=121 passed / 0 failed / 0 skipped

- Semantic service / serializer: 50 passed.
- API / routing: 41 passed.
- Frontend (including real Node harness): 2 passed.
- Direct existing route regression: 28 passed.

New regressions cover all four identity states with usable/degraded projection, rejection of contradictory availability, public DTO semantics for pending/unavailable/absent binding, and feature-OFF authentication/Site/capability/input/UUID precedence without reads. Existing enabled-path failure mapping remains green.

First local run: 120 passed / 1 failed because the newly written unauthenticated fixture expected `unauthenticated` instead of the existing `authentication_required` error code. Only the new test expectation was corrected to the existing contract; production authentication behavior was not changed. Final run above is fully green.

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m compileall -q app/network_protocol_intelligence app/admin_web/routes.py tests/network_protocol_intelligence/test_read_service.py tests/admin_web/test_device_protocol_intelligence.py tests/admin_web/test_device_protocol_intelligence_frontend.py
& 'C:\Program Files\nodejs\node.exe' --check app/admin_web/static/device_protocol_intelligence.js
git diff --check
```

COMPILEALL=PASS
NODE_CHECK=PASS
DIFF_CHECK=PASS

## Complete replacement artifact

NEW_CANDIDATE_TREE=8ed141f0184d65e6fd8d4d3a06adadc5940497e3
NEW_PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-03-R1-CANDIDATE.patch
NEW_PATCH_BYTES=102251
NEW_PATCH_SHA256=23a545ac1e915bc16fe94185c6ff0fdd1db60ed56b11cbdd60e7d59739f61b20

Full baseline-to-candidate binary/full-index patch, including new files. Exported using an external temporary Git index; no commit created. Applying to a separate index initialized at BASE_HEAD reproduces the exact candidate tree. Reverse-apply check against the current worktree passes.

FULL_CANDIDATE_STAT=24 files changed, 1494 insertions(+), 4 deletions(-)
PATCH_RECONSTRUCTION=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
INDEX_STAGED_FILES=NONE

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO
FULL_REPOSITORY_TESTS=NO
CENTRAL_LAB_RUN=NO
LINUX_WAL_RERUN=NO / not required; protected read service unchanged since reviewed candidate

NEXT_ACTION=TECH LEAD R1 SOURCE REVIEW
