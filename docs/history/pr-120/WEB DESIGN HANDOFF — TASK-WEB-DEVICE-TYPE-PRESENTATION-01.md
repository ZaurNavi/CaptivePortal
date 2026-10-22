WEB DESIGN HANDOFF

Repository:
ZaurNavi/CaptivePortal

Baseline HEAD:
144c8a922b4431293fdc1d4bb57bed29a8402f6b

Baseline TREE:
2349838d7e524efd3fb2e0433a7111553f195e71

Task:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01

RESULT:
Presentation-only candidate prepared against the canonical Device Type baseline.

CHANGED_FILES:
- app/admin_web/static/admin.js
- app/admin_web/static/admin.css

home.html changed:
NO

NEW_ASSETS:
NO

Existing asset reused:
`/admin/static/icons/platforms/android.svg`

PATCH_FILE:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01.patch

PATCH_SHA256:
aa071c2ff1b936276f8092d30522e69931a84c3ae979b046369aac8226043db7

PATCH_SIZE:
9744 bytes

DIFF_STAT:
app/admin_web/static/admin.css | 4 ++
app/admin_web/static/admin.js  | 84 ++++++++++++++++++++++++++++++++----------
2 files changed, 69 insertions(+), 19 deletions(-)

HOME DEVICE TYPE INDICATOR:

A new narrow indicator column is inserted immediately after `Device / MAC`.

Header:
- no visible text;
- accessible `aria-label="Device type"`;
- narrow presentation width;
- centered vertically and horizontally.

Android:
`device_type_key === "android"`
→ existing Android SVG only;
→ no permanent Type text beside the icon;
→ raw `device_type` is used as tooltip/accessibility label when available.

Missing:
`device_type_key === null`
AND
`device_type === null`
→ `NULL`

Other/raw type:
example:
`device_type = "phone"`
`device_type_key = "phone"`
→ `phone`

No icon is invented for unsupported keys.

Contradictory unrelated fields:
hostname / system_name / vendor / MAC / SSID / etc.
→ ignored for Device Type decision.

Both existing Home Online Devices render paths use the same `clientPresentationCells()` result, so the Device Type indicator is present consistently in standalone and coordinator rendering.

DEVICE CARD TRANSITION:

Old Android predicate:
raw value
→ trim()
→ toLowerCase()
→ compare with "android"

REMOVED.

New predicate:
`deviceTypeKey === "android"`

`isAndroidDeviceType()` now accepts a canonical machine key only and performs strict equality.

Raw `device_type` remains the displayed evidence text.

`device_type_key` is used only as the presentation decision source and is not displayed as an additional user-facing Device Card field.

Device Identity Type:
- raw text remains unchanged;
- Android icon decision uses `identity.device_type_key`.

Device detail/snapshot Type:
- raw `device_type` remains displayed;
- matching `device_type_key` supplies icon decision;
- machine-key field itself is filtered from visible detail rows.

Existing Devices list presentation also passes `item.device_type_key` into the same shared Device Type renderer. This is required to preserve the existing Android icon after removal of raw frontend normalization.

DEVICE TYPE NORMALIZATION IN FRONTEND:
NO

Frontend does NOT perform Device Type:
- trim
- lowercase
- uppercase
- casefold
- Unicode normalization
- alias mapping
- semantic inference

ANDROID ICON DECISION SOURCE:
device_type_key

Canonical predicate:
`device_type_key === "android"`

BACKEND CHANGED:
NO

API CHANGED:
NO

DATABASE/SCHEMA CHANGED:
NO

SOURCE NORMALIZATION CHANGED:
NO

CURRENT STATE BACKEND CHANGED:
NO

OBSERVATIONS BACKEND CHANGED:
NO

ANALYTICS BACKEND CHANGED:
NO

ROUTES CHANGED:
NO

FETCH/REQUEST LOGIC CHANGED:
NO

SORTING CHANGED:
NO

FILTERS CHANGED:
NO

PAGINATION / LOAD MORE CHANGED:
NO

REFRESH / TIMERS CHANGED:
NO

SECURITY/AUTH CHANGED:
NO

FEATURE FLAGS CHANGED:
NO

TESTS CHANGED:
NO

DOCS CHANGED:
NO

DEPENDENCIES ADDED:
NO

GITHUB WRITE OPERATIONS:
NO

COMMIT:
NO

PUSH:
NO

PR:
NO

MERGE:
NO

DEPLOY:
NO

PRODUCTION TOUCHED:
NO

SELF-REVIEW:

Changed path scan:
PASS

Device Type frontend normalization scan:
PASS

Strict canonical key decision found:
- `return deviceTypeKey === "android";`
- `item.device_type_key === "android"`

Existing Android asset reused:
PASS

New asset creation:
NONE

Focused presentation semantic probe:
PASS

Verified cases:
- `android` key → Android
- `Android` key → not Android
- ` ANDROID ` key → not Android
- `phone` key → not Android
- null key → not Android
- raw `" Android "` + key `"android"` → icon decision from key, raw preserved
- null/null → Home `NULL`
- raw `phone` + key `phone` + Android-looking hostname/system metadata → raw `phone`, no Android icon

Patch structural check:
PASS

Synthetic exact-context:
`git apply --check` = PASS
`git apply --check --whitespace=error-all` = PASS
`git diff --check` = PASS

Exact repository worktree:
GIT_APPLY_CHECK=TECH LEAD / OWNER PENDING
GIT_DIFF_CHECK=TECH LEAD / OWNER PENDING

KNOWN STALE TEST CONTRACT — TECH LEAD/CODER FOLLOW-UP

`tests/admin_web/test_admin_ui_frontend.py` was intentionally NOT modified.

The old assertions expecting:
- `"Android"` → true
- `" ANDROID "` → true

conflict with the newly approved canonical-key contract.

Expected new technical contract for later test update:
- `"android"` → true
- `"Android"` → false
- `" ANDROID "` → false
- `"phone"` → false
- `null` → false

Per Tech Lead decision OPTION A, Web Designer does not preserve obsolete raw normalization merely to satisfy those stale assertions.

OWNER_VISUAL_ACCEPTANCE:
PENDING

PRODUCTION:
NO