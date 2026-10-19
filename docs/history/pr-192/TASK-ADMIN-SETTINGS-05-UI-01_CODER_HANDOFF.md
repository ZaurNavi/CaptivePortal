# TASK-ADMIN-SETTINGS-05-UI-01 — first source/diff handoff

Date: 2026-10-09 (Asia/Baku).

## Required result

```ini
TASK=TASK-ADMIN-SETTINGS-05-UI-01
BASE_HEAD=42cc9b86f6760663ce20d3a9dc47b679849f2fa0
BASE_TREE=2b176bda9d00e4e5699c8fc36be97e3f9da45d3d
HEAD=UNCOMMITTED
ACTUAL_REPOSITORY_HEAD=42cc9b86f6760663ce20d3a9dc47b679849f2fa0
WORKTREE_PATH=C:\CaptivPortal-Lab\coder-admin-settings-05-ui-01
BRANCH=fix/admin-settings-05-portal-ui
WORKTREE=DIRTY / exactly six authorized modified files / no untracked files
PRODUCTION_FILES_CHANGED=exactly three authorized UI files / NO others
BACKEND_CHANGED=NO
API_CHANGED=NO
SCHEMA_CHANGED=NO
AUTHORIZATION_CHANGED=NO
SETTINGS_SEMANTICS_CHANGED=NO
TARGETED_TESTS=38 passed / 0 failed / 0 skipped
NODE_CHECK=PASS
DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
OPEN_P0=0 observed
OPEN_P1=0 observed
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

The fetched remote main, new worktree HEAD/tree and clean status were checked before any source changes. Original Settings-05 publication worktree was preserved. No accepted code/history was rewritten.

## Exact modified files

Production UI only:

- `app/admin_web/templates/admin/settings_portal.html`: dot/title/message/generation state structure, one page-level external adoption note, Refresh wording and action-bar hook.
- `app/admin_web/static/portal_settings.js`: metadata-derived hints, source labels, safe structured card rendering, multiline/pending facts, deterministic action/busy state, readonly/error/conflict handling.
- `app/admin_web/static/admin.css`: light-surface Settings tabs and Portal-scoped responsive grids/cards/muted facts/textarea/focus/disabled/warning/sticky actions.

Existing task tests only:

- `tests/admin_web/portal_settings_stage5_ui.cjs`: existing disposable actual-controller scenarios retained/extended to cover all required UI behavior; no network.
- `tests/admin_web/test_portal_settings_stage5_frontend.py`: 13 Node scenarios, preserved safety/source guards, scoped CSS contract checks.
- `tests/admin_web/test_portal_settings_stage5.py`: rendered Portal shell state/action/tab hooks; all existing API/security assertions preserved.

New repository files: NONE.

```text
M app/admin_web/static/admin.css
M app/admin_web/static/portal_settings.js
M app/admin_web/templates/admin/settings_portal.html
M tests/admin_web/portal_settings_stage5_ui.cjs
M tests/admin_web/test_portal_settings_stage5.py
M tests/admin_web/test_portal_settings_stage5_frontend.py

app/admin_web/static/admin.css                     | 40
app/admin_web/static/portal_settings.js            | 113
app/admin_web/templates/admin/settings_portal.html | 14
tests/admin_web/portal_settings_stage5_ui.cjs      | 121
tests/admin_web/test_portal_settings_stage5.py     | 9
tests/admin_web/test_portal_settings_stage5_frontend.py | 48
6 files changed, 302 insertions(+), 43 deletions(-)
```

## Exact focused verification

PowerShell command, using existing WSL Ubuntu-22.04 / Python 3.10.12 and existing dependencies only:

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivPortal-Lab/coder-admin-settings-05-ui-01 --exec env 'PYTHONPATH=/mnt/c/Users/Zaur Navi/AppData/Local/Programs/Python/Python310/Lib/site-packages' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPYCACHEPREFIX=/tmp/as05-ui01-pycache python3 -m pytest -q tests/admin_web/test_portal_settings_stage5.py tests/admin_web/test_portal_settings_stage5_frontend.py --basetemp /tmp/as05-ui01-focused-r2
```

Final: **38 passed in 8.23s**, exit 0; no skips/failures. This includes the disposable Node controller scenarios; no second frontend regression suite was run.

```powershell
node --check app/admin_web/static/portal_settings.js
git diff --check
git apply --reverse --check C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-05-UI-01_BASE-to-CANDIDATE.patch
```

All PASS, exit 0. Node syntax check used existing Windows Node 24.19.0. The focused subprocess scenarios used existing WSL Node 24.20.0.

Implementation iteration: first focused run had 37 passed / 1 failed in the new CSS helper, which considered only the first matching focus declaration. The helper now considers all matching declarations without removing the outline requirement. Final focused run above passes.

Forbidden backend/config/guest/CAPPORT/Settings source paths were explicitly checked unchanged with `git diff --quiet`. Exact six-file scope and no untracked repository files verified.

Full repository/cross-module/Central Lab/production tests: NOT RUN, per contract. No production login/access, no guest portal preview, no restart, no dependencies installed.

## UI defect mapping

| Defect | Implementation |
| --- | --- |
| UI-01 | `validationHint(item.validation)` reads required/content/format/length/line/host/query metadata and builds plain operator text; raw validation serialization removed. |
| UI-02 | Configured/Effective/Pending retain exact strings; `.portal-setting-value` uses `white-space: pre-wrap` and wrapping without data normalization. |
| UI-03 | `textarea.portal-setting-input` receives inherited font, full bounded width, border/padding, useful minimum height, vertical resize, visible focus and disabled styling. |
| UI-04 | `.muted` is implemented only inside `#portal-settings-page`; unrelated global metadata styles unchanged. |
| UI-05 | source presentation maps Repository default / Saved override / Deployment environment; authoritative enum values unchanged. |
| UI-06 | repeated per-field apply facts removed; one page-level external restart note consumes existing apply metadata; no restart control. |
| UI-07 | scoped `.settings-tabs .nav-link` styles override dark sidebar presentation, with readable inactive, hover/focus and `aria-current` active states; base.html untouched. |
| UI-08 | state dot/title/message plus subordinate generation line; loading, active, pending, save success/rejection, concurrent change and unavailable presentation use existing tones. |
| UI-09 | `updateActions()` requires writable current model/ETag, selected mutation and not busy; resets after refresh/success/conflict, retains selections after safe validation rejection; zero-change submit never posts. |
| UI-10 | labels Change / No change / Use custom value / Refresh / New value; unchanged/set/clear_override operations and reset label preserved. |
| UI-11 | technical keys remain in DOM as small `.mono.muted.portal-setting-key` metadata. |
| UI-12 | existing API iteration/order unchanged; Branding 3 and Support 2 columns at wide desktop; default single-column grids and wrapping tabs at narrow widths. |
| UI-13 | card hierarchy separates title/description/key, Configured/Effective/Source/Pending facts, editor and associated human hint. |
| UI-14 | exact public guest/privacy warning once at Support contacts top with scoped visible warning-callout styling. |

## Preserved behavior

- Fourteen inputs, three TEXTAREA descriptions and original model order.
- Human hint content demonstrably changes with synthetic server metadata (73-character title limit, 6-line description, synthetic allowed host), not a local business rule table.
- No unsafe HTML APIs, storage, trimming, restart execution or parallel validation authority.
- Each hint is linked by aria-describedby; controls use real wrapping labels.
- Configured/Effective display only their respective authoritative values. Pending is explicitly labelled and highlighted, not color alone; matching values do not imply pending work.
- Readonly retains every current-state fact; controls/Save unavailable and no POST.
- Set strings, clear_override payload, CSRF, If-Match, Idempotency-Key, same-origin and no-store unchanged.
- In-flight Save/Refresh and edit controls disabled; duplicate submit suppressed.
- 400/422 rejection, 412 reload/conflict, 503 unavailable, initial load outage, successful save/reload and backend no-op response remain covered.
- No new API field/endpoint, no change to allowlist/defaults, audit/schema/generation/adoption/C1/Stage-4 secrets.

## Local rendered/visual evidence

Computer-use browser preview served actual candidate Jinja template / CSS / JS on loopback using disposable shaped settings data. Preview helper is outside Git at `C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-05-UI-01-preview\server.py`; it has GET-only model/static routes, no DB/provider or mutation route. No Save button was submitted. Server stopped and viewport override reset after review.

Observed:

- 1440×1000: Branding widths 353.062 / 353.062 / 353.075 px; Support 537.6 / 537.6 px; readable light tabs with Portal active; Active adopted message; Save disabled without a selected change.
- Pending fixture: exact pending restart text, separate configured/effective generations; LF strings displayed on distinct lines; Saved override source and visible labelled Pending fact.
- Dirty description: selecting `set` enables textarea and Save; all original description text retained. Sticky actions remain visible while scrolling.
- Support warning appears once above two-column contacts.
- 390×844: single-column Branding/Support, clientWidth=scrollWidth=375; no horizontal overflow. Readonly keeps facts, all inputs/selects/textarea and Save disabled.
- 320×740: single-column Branding, clientWidth=scrollWidth=305; wrapping tabs.
- 390×844 pending edit: keyboard Tab from Change focuses TEXTAREA with solid focus outline; Save enabled; clientWidth=scrollWidth=375.

Screenshots (complete viewport files):

- [Desktop active](TASK-ADMIN-SETTINGS-05-UI-01-preview/desktop-active.jpg)
- [Desktop pending](TASK-ADMIN-SETTINGS-05-UI-01-preview/desktop-pending.jpg)
- [Desktop multiline/pending/dirty editor](TASK-ADMIN-SETTINGS-05-UI-01-preview/desktop-description-detail.jpg)
- [Desktop support warning](TASK-ADMIN-SETTINGS-05-UI-01-preview/desktop-support-warning.jpg)
- [Mobile readonly](TASK-ADMIN-SETTINGS-05-UI-01-preview/mobile-readonly.jpg)
- [Mobile pending textarea keyboard focus](TASK-ADMIN-SETTINGS-05-UI-01-preview/mobile-pending-textarea-focus.jpg)

## Patch

```ini
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-05-UI-01_BASE-to-CANDIDATE.patch
PATCH_BYTES=40366
SHA256=9e377a714a10144b25948852976fc6f93f17983286d17c74e4675096827abddd
PATCH_BASE=42cc9b86f6760663ce20d3a9dc47b679849f2fa0
```

Binary-capable full-index unified diff from exact baseline to current working candidate. Reverse applicability PASS, no mutation during applicability check.

## Limitations and review status

KNOWN_LIMITATIONS=Local visual evidence is synthetic/disposable, not production/adoption evidence; full-page browser capture unavailable, viewport captures supplied instead. No known implementation blocker observed. Tech Lead/UI acceptance remains pending.

Candidate accepted: NO — this is first source/diff handoff.
No commit created; real HEAD remains exact accepted baseline; six-file dirty candidate preserved for review.
Repository actions: fetched origin and created isolated worktree/branch only.

HOLD FOR TECH LEAD / UI REVIEW.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
