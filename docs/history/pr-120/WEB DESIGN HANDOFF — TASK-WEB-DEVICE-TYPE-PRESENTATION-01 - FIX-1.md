WEB DESIGN HANDOFF — FIX-1

Repository:
ZaurNavi/CaptivePortal

Baseline:
144c8a922b4431293fdc1d4bb57bed29a8402f6b

Baseline tree:
2349838d7e524efd3fb2e0433a7111553f195e71

Task:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01 / FIX-1

RESULT:
Bounded Device Card presentation regression fixed.
Previous accepted Home / Devices list / Identity presentation retained.

CHANGED_FILES:
- app/admin_web/static/admin.js
- app/admin_web/static/admin.css

PATCH_FILE:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01-FIX-1.patch

NEW_PATCH_SHA256:
32b4cb19f2b9e33665db87037032aac7c7a3a20bee14a5625eb9b246776b3a58

NEW_PATCH_SIZE:
10653 bytes

DIFF_STAT:
app/admin_web/static/admin.css | 4 ++
app/admin_web/static/admin.js  | 90 ++++++++++++++++++++++++++++++++----------
2 files changed, 73 insertions(+), 21 deletions(-)

FIX-1 IMPLEMENTATION:

`deviceDetailEntries()` now accepts an optional explicit canonical Device Type key.

Decision rule:

1. If the detail object itself contains `device_type_key`,
   that exact canonical key is used.

2. Otherwise an explicitly supplied corresponding canonical key may be used.

3. No key is derived from raw `device_type`.

For Device Card → Latest Site snapshot:

raw text:
`result.latest_snapshot.device_type`

remains displayed unchanged.

Android decision key:
`identity.device_type_key`

is explicitly passed by the Device Card renderer:

`deviceDetailEntries(result.latest_snapshot, identity.device_type_key)`

This does NOT copy or rewrite raw evidence.

IDENTITY ANDROID DECISION:
canonical `identity.device_type_key`

LATEST SITE SNAPSHOT ANDROID DECISION:
canonical `identity.device_type_key`

HOME ANDROID DECISION:
canonical `item.device_type_key`

DEVICES LIST ANDROID DECISION:
canonical `item.device_type_key`

FRONTEND RAW DEVICE TYPE NORMALIZATION:
NO

No:
- trim()
- toLowerCase()
- toUpperCase()
- casefold
- alias mapping
- inference from hostname/system/vendor/MAC/etc.

Required cases verified by focused semantic probe:

Identity:
raw `" Android "`
key `"android"`
→ raw preserved + Android decision true

Latest Site snapshot:
raw `" Android "`
explicit identity key `"android"`
→ raw preserved + Android decision true

Unknown:
raw `"phone"`
key `"phone"`
→ Android decision false

Missing:
raw null
key null
→ Android decision false

Contradiction:
raw `"phone"`
canonical key `"phone"`
Android-looking unrelated metadata
→ Android decision remains false

Detail object own-key precedence:
If a detail object explicitly contains its own `device_type_key`,
that exact key takes precedence over an externally supplied key.

This prevents unrelated canonical metadata from overriding an object's explicit machine key.

HOME IMPLEMENTATION CHANGED BY FIX-1:
NO

HOME VISUAL DESIGN CHANGED:
NO

CSS CHANGED FROM PREVIOUS CANDIDATE:
NO

NEW ASSETS:
NO

BACKEND CHANGED:
NO

API CHANGED:
NO

DATABASE/SCHEMA CHANGED:
NO

SOURCE NORMALIZATION CHANGED:
NO

TESTS CHANGED:
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

PATCH STRUCTURAL CHECK:
PASS

SYNTHETIC EXACT-CONTEXT:
git apply --check = PASS
git apply --check --whitespace=error-all = PASS
git diff --check = PASS

FOCUSED DEVICE TYPE SEMANTIC PROBE:
PASS

DEVICE TYPE FRONTEND NORMALIZATION SCAN:
PASS

KNOWN STALE TEST CONTRACT — TECH LEAD/CODER FOLLOW-UP

`tests/admin_web/test_admin_ui_frontend.py`
was intentionally NOT modified.

Known old assertions for `"Android"` and `" ANDROID "` remain stale under the canonical-key contract, per previous Tech Lead OPTION A decision.

Exact repository worktree:
GIT_APPLY_CHECK=TECH LEAD / OWNER PENDING
GIT_DIFF_CHECK=TECH LEAD / OWNER PENDING

OWNER_VISUAL_ACCEPTANCE:
PENDING

PRODUCTION:
NO