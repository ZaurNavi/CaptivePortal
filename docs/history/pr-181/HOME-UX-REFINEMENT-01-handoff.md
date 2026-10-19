# CODER IMPLEMENTATION HANDOFF

```text
TASK=HOME-UX-REFINEMENT-01
BASE_COMMIT=c2635b467dc83e3f574ed204184a2e982f925a9a
BASE_TREE=bb1d5f7951d77e8a65a6af4856b07d80fc9122f0
LOCAL_HEAD=c2635b467dc83e3f574ed204184a2e982f925a9a
LOCAL_HEAD_TREE=bb1d5f7951d77e8a65a6af4856b07d80fc9122f0
CHANGED_FILES=14
DIFF_STAT=14 files changed, 366 insertions(+), 74 deletions(-)
TEST_RESULT=PASS; 120 unique focused test cases; 0 failed; 0 errors; 0 skipped
PY_COMPILE=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
WORKTREE=DIRTY (exact Phase 1 implementation below; no staged changes)
UNIFIED_PATCH=C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01.patch
PATCH_BYTES=54532
PATCH_SHA256=e62b155cc311890d0e25cf50ea8b079971e32525ae403dab880aecbe7c5e455c
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
PRODUCTION=NO
FULL_TESTS_RUN=NO
CENTRAL_LAB_RUN=NO
```

## IMPLEMENTATION_SUMMARY

- Five existing Current Network metrics keep their labels/data, width/grid and responsive breakpoints. Only `.live-metrics > .live-metric` cards receive compact vertical spacing, a shared heading allowance and dominant metric line. Details remain visible; global `.card` is unchanged.
- Online Devices is moved as one unchanged template block after Current-State warnings and before Traffic Now. Filters, sort, pagination, scroll/accessibility hooks remain. Traffic by AP stays nested inside Traffic Now; all other panels retain relative order.
- Home Traffic Now renders exact `↓`, `↑`, `↓↑` arrows. Each numeric value independently selects green at <=50, yellow at >50 through 70, red above 70. Null/unavailable remains neutral and clears previously applied tone. Tone uses validated numeric data, never formatted text. AP rows and Traffic page/calculation/freshness/coverage/source semantics are unchanged.
- `compact_platform()` preserves exact classified dimension status/canonical value, and no-result/unavailable neutral states. The existing single Site-scoped PRODUCTION batch supplies both Type and Platform.
- The server composes `platform_presentation={source,value,key}`. Controller wins iff its existing key is neither null nor `unknown`; only a resolved Fingerprint platform can fall back. No heuristic key exclusions, browser normalization, visible provenance badges or Type fallback are introduced.
- Home Android rendering uses only the exact effective `android` key. Device Card continues exposing Controller/Fingerprint separately. Candidate/Site mismatch/storage failure are fail-soft.
- Current statements and diagrams in the five required documentation files reflect this Home-only behavior without asserting production deployment; historical provenance and Device Card separation remain.

## CHANGED_FILES / git diff --name-status

```text
M README.md
M README_RU.md
M app/admin_web/device_fingerprint_presentation.py
M app/admin_web/query_service.py
M app/admin_web/static/admin.css
M app/admin_web/static/admin.js
M app/admin_web/templates/admin/home.html
M docs/README.md
M docs/modules/admin-web.md
M docs/modules/device-fingerprint.md
M tests/admin_web/test_admin_ui_frontend.py
M tests/admin_web/test_device_fingerprint_presentation.py
M tests/admin_web/test_home_traffic.py
M tests/admin_web/test_home_traffic_frontend.py
```

## DIFF_STAT

```text
 README.md                                          | 38 ++++++++++--
 README_RU.md                                       | 38 ++++++++++--
 app/admin_web/device_fingerprint_presentation.py   | 23 ++++++++
 app/admin_web/query_service.py                     | 11 +++-
 app/admin_web/static/admin.css                     |  7 +++
 app/admin_web/static/admin.js                      | 45 ++++++++------
 app/admin_web/templates/admin/home.html            | 28 ++++-----
 docs/README.md                                     | 36 +++++++++--
 docs/modules/admin-web.md                          | 47 ++++++++++++---
 docs/modules/device-fingerprint.md                 | 24 ++++++--
 tests/admin_web/test_admin_ui_frontend.py          | 26 ++++++--
 .../test_device_fingerprint_presentation.py        | 69 +++++++++++++++++++++-
 tests/admin_web/test_home_traffic.py               | 22 +++++++
 tests/admin_web/test_home_traffic_frontend.py      | 26 +++++++-
 14 files changed, 366 insertions(+), 74 deletions(-)
```

## TESTS_RUN

Working directory for all commands: `C:\CaptivPortal-Lab\coder-task05-identity-session`.

External Python cache for all Python commands:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\home-ux-refinement-01-pyc'
```

### Focused Home/Fingerprint/frontend/template and direct Device Card preservation

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q -rs tests/admin_web/test_device_fingerprint_presentation.py tests/admin_web/test_admin_ui_frontend.py tests/admin_web/test_home_traffic_frontend.py tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled tests/admin_web/test_device_fingerprint_frontend.py --basetemp='C:\CaptivPortal-Lab\tmp\home-ux-refinement-01-focused-01' --junitxml='C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01-focused.xml'
```

PASS: 62 passed, 0 failed, 0 errors, 0 skipped (retained JUnit evidence).

- Fingerprint presentation: 53.
- Admin/Home frontend: 2.
- Home Traffic frontend: 2.
- Enabled/disabled Home template: 1.
- Direct Device Card frontend separation/fail-soft compatibility: 4.

### Existing Home Current-State query/serializer/routes/refresh compatibility

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q -rs tests/admin_web/test_home_live.py --basetemp='C:\CaptivPortal-Lab\tmp\home-ux-refinement-01-home-live-01' --junitxml='C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01-home-live.xml'
```

PASS: 58 passed, 0 failed, 0 errors, 0 skipped.

### Final layout recheck after summary heading allowance adjustment

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q -rs tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled --basetemp='C:\CaptivPortal-Lab\tmp\home-ux-refinement-01-final-layout-01' --junitxml='C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01-final-layout.xml'
```

PASS: 1 passed, 0 failed, 0 errors, 0 skipped. This is a repeated case, not an additional unique test: 120 unique cases / 121 executions overall.

### Changed Python syntax and diff checks

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m py_compile app/admin_web/device_fingerprint_presentation.py app/admin_web/query_service.py tests/admin_web/test_admin_ui_frontend.py tests/admin_web/test_device_fingerprint_presentation.py tests/admin_web/test_home_traffic.py tests/admin_web/test_home_traffic_frontend.py
git diff --check
```

Both PASS. Existing frontend tests also verify JavaScript syntax and exercise real Node rendering/state logic.

## Review artifacts

The patch is the complete binary-capable, full-index BASE-to-worktree diff, not a commit-to-commit fragment:

```powershell
git diff --binary --full-index --output=C:/CaptivPortal-Lab/artifacts/HOME-UX-REFINEMENT-01.patch c2635b467dc83e3f574ed204184a2e982f925a9a
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/HOME-UX-REFINEMENT-01.patch
```

External retained files:

- `C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01.patch`
- `C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01-diff-stat.txt`
- `C:\CaptivPortal-Lab\artifacts\HOME-UX-REFINEMENT-01-name-status.txt`
- the three JUnit XML files listed in test commands above.

## KNOWN_LIMITATIONS

No functional blocker found in the focused verification. Actual visual/UX acceptance at desktop/tablet/mobile remains Owner / Web Design Tech Lead responsibility; no browser screenshot or pixel-perfect acceptance is claimed. Full/Central suites were intentionally not run. No production, schema, classifier, fusion, Auth, CAPPORT, Device Card reconciliation or Traffic calculation changes were performed.

Phase 1 stopped before commit. Await exact diff source review and separate explicit approval to commit/push/PR.
