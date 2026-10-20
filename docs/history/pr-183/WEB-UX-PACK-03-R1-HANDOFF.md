# WEB-UX-PACK-03 / R1 — review candidate

Status: READY_FOR_WEB_DESIGN_REVIEW. This is an uncommitted review candidate, not publication or product acceptance.

## Identity and scope

```text
TASK=WEB-UX-PACK-03-R1
WORKTREE=C:\CaptivPortal-Lab\coder-web-ux-pack-03-r1
BASE_COMMIT=be3fe14f929b45e4a1ca3991bc6a2a3011792641
BASE_TREE=16a16d87c7dc821e0a5c4e6fe8ad67d4962d129d
LOCAL_HEAD=be3fe14f929b45e4a1ca3991bc6a2a3011792641
LOCAL_TREE=16a16d87c7dc821e0a5c4e6fe8ad67d4962d129d
WORKTREE_STATUS=DIRTY — only the 11 review-candidate files below
BASELINE_DRIFT=NO
BACKEND_CHANGE=NO
TECH_LEAD_DEPENDENCY=NO
```

LOCAL_TREE is the unchanged HEAD tree; the complete uncommitted candidate is represented by the patch below. The worktree was clean when created from the exact baseline. No implementation commit was created.

## Implementation summary

- Home-only Type icons and wrappers are 44×44, explicitly centered beneath the heading; shared Devices icons remain 22×22. Existing icon mapping/accessibility is preserved.
- Access Points Now is the single outer card and visible roster/pagination owner. AP24 root refresh consumes the existing 20-item cursor pages sequentially to exhaustion and publishes one completed canonical-MAC map. Cached history enriches later roster pages; stale generations cannot replace the current map. Source failure/timeout yields neutral unavailable history without clearing current AP/device/rate facts.
- Each AP identity appears once. Its timeline precedes Devices, and valid unknown buckets are red while retaining unknown tooltip/state semantics. Rates are prominent; zero, null, source and observed metadata remain distinct. Narrow layouts wrap rates and contain table scrolling.
- Visit Traffic uses the existing binary byte formatter; duration and stored/API values are unchanged.
- Traffic History and Traffic by AP share one outer card. Network chart comes first; AP cards use a post-validation presentation copy sorted naturally by name with MAC tie-break. API canonical-order validation, ranges/coordinator and AP Traffic Share remain unchanged. Statistics/Peak/Share remain separate panels. Completed Guest Session Traffic is last, after Evidence when enabled.
- Documentation and focused UI regression expectations were updated. No new assets, backend/API/schema/collector/production changes.

## Complete changed-file list / name-status

```text
M app/admin_web/static/admin.css
M app/admin_web/static/admin.js
M app/admin_web/templates/admin/home.html
M app/admin_web/templates/admin/traffic.html
M docs/modules/admin-web.md
M docs/modules/traffic.md
M tests/admin_web/test_home_ap_24h_frontend.py
M tests/admin_web/test_traffic_ap_frontend.py
M tests/admin_web/test_traffic_completed_sessions_frontend.py
M tests/admin_web/test_web_ux_pack_02.py
A tests/admin_web/test_web_ux_pack_03.py
```

```text
DIFF_STAT=11 files changed, 383 insertions(+), 130 deletions(-)
```

## Focused verification

Final command (from the review worktree):

```powershell
python -m pytest -q --basetemp=C:/CaptivPortal-Lab/tmp/web-ux-pack-03-focused-final tests/admin_web/test_web_ux_pack_03.py tests/admin_web/test_web_ux_pack_02.py tests/admin_web/test_home_ap_24h_frontend.py tests/admin_web/test_home_ap_24h.py tests/admin_web/test_home_traffic_frontend.py tests/admin_web/test_admin_ui_frontend.py tests/admin_web/test_traffic_history_frontend.py tests/admin_web/test_traffic_ap_frontend.py tests/admin_web/test_traffic_ap.py tests/admin_web/test_traffic_independent_ranges_frontend.py tests/admin_web/test_traffic_independent_ranges.py tests/admin_web/test_traffic_ap_share_frontend.py tests/admin_web/test_traffic_completed_sessions_frontend.py tests/admin_web/test_traffic_evidence_frontend.py
```

```text
TEST_RESULT=PASS — 151 passed in 9.27s
NODE_CHECK=PASS — node --check app/admin_web/static/admin.js
COMPILEALL=PASS — all five changed Python test files
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\web-ux-pack-03-pyc
DIFF_CHECK=PASS — git diff --check, including new file
PATCH_REVERSE_APPLY_CHECK=PASS — git apply --reverse --check
FULL_REPOSITORY_SUITE_RUN=NO
CENTRAL_LAB_RUN=NO
```

An initial run encountered the existing default Windows TEMP-directory permission error. The final run used a fresh external temporary directory; no test was skipped/deselected to bypass it.

## Complete unified review patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\web-ux-pack-03-r1\WEB-UX-PACK-03-R1.patch
PATCH_BYTES=56071
PATCH_SHA256=075f383a11089a2936d1501e5f7c812c501e27528429c2ffe7cdf324c6d951fb
PATCH_BASE=be3fe14f929b45e4a1ca3991bc6a2a3011792641
PATCH_FORMAT=git diff --binary --full-index
```

The new test file has intent-to-add only so it is included in the complete diff; nothing is committed.

## Visual evidence

Actual candidate Jinja templates/CSS and JavaScript render functions were exercised in a localhost-only synthetic presentation fixture. This is UI review evidence, not production data, backend end-to-end acceptance or an official gate. QA helpers and screenshots are external to the repository. The local preview server has been stopped.

All files below are in `C:\CaptivPortal-Lab\artifacts\web-ux-pack-03-r1\`:

| Screenshot | Evidence |
| --- | --- |
| home-desktop-type-and-ap.jpg | Desktop Type column + unified AP card |
| home-desktop-unified-ap.jpg | Complete unified AP rows, timeline before Devices, prominent rates |
| home-mobile.jpg | Narrow AP row, wrapped rates, neutral missing history |
| traffic-desktop-history.jpg | Combined History, network first, natural AP1/AP2/AP10 order |
| traffic-completed-last.jpg | Evidence precedes Completed Sessions, which is last |
| traffic-mobile.jpg | Responsive AP chart subcards |
| device-detail-traffic.jpg | Visit Traffic: 18.7 MB, 2.14 GB, 0 B and — |
| home-desktop.jpg | Additional desktop overview |

Browser observations: Home Type computed 44×44; heading/icon horizontal center difference approximately 0.008 px; shared icon default 22 px. At 390 px viewport, page content width was 375 px (scrollbar excluded), AP row width 309 px, with no horizontal page overflow. Valid unknown segment color was rgb(217,45,32). Desktop AP charts were in AP1/AP2/AP10 DOM order; mobile Completed Sessions remained last.

## DTI preservation evidence

```text
DTI_WORKTREE=C:\CaptivPortal-Lab\coder-task05-identity-session
DTI_HEAD=c8d8d620dfed06caee92a498b891bf2faa37a6a9
DTI_HEAD_TREE=be3470c378180aa215d527c6de6b686583ae0d79
DTI_EXISTING_STATUS=16 intent-to-add prototype files, unchanged
DTI_ORIGINAL_R2_1_PATCH_SHA256=3287dbf5a28adc3470a5933eeb503b55a6c5a1f5da4de84e305c9d4cc35c14fc
DTI_CURRENT_FULL_DIFF_SHA256=3287dbf5a28adc3470a5933eeb503b55a6c5a1f5da4de84e305c9d4cc35c14fc
DTI_WORKTREE_PROTOTYPE_UNCHANGED=YES
```

The DTI verification was read-only. No reset/clean/stash/rebase/checkout, file edit, test or index change was performed in the DTI worktree.

## Governance / stop

```text
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION=UNTOUCHED
PRODUCTION_ACTIONS=NO
BLOCKERS=NONE
NEXT_STEP=Web Design source/visual review; separate Owner publication authorization required
```
