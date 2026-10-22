WEB DESIGN HANDOFF — FIX-3A

Repository:
ZaurNavi/CaptivePortal

Base candidate tree:
45c20d370270728304315454ebcc0470ec990e58

Task:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01 / FIX-3A

RESULT:
Replacement presentation-only PATCH prepared against FIX-2 candidate state.

Bad FIX-3 included:
NO

CHANGED_FILES:
- app/admin_web/static/admin.css
- app/admin_web/static/admin.js

PATCH_FILE:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01-FIX-3A.patch

PATCH_SHA256:
bd4aa253b9f50e1748e789ed719ef36a5da8c26d30b698045d99711fd4f5270e

PATCH_SIZE:
5388 bytes

DIFF_STAT:
app/admin_web/static/admin.css | 14 ++++++++++----
app/admin_web/static/admin.js  | 12 +++++++++---

2 files changed, 19 insertions(+), 7 deletions(-)

EXACT CSS SCOPE:

All new table-geometry / header / Type / SNR presentation selectors are scoped under:

`.live-section[aria-labelledby="devices-now-title"]`

Examples:

`.live-section[aria-labelledby="devices-now-title"] .live-table thead th:not(:first-child)`

`.live-section[aria-labelledby="devices-now-title"] .live-table tbody td:not(:first-child)`

`.live-section[aria-labelledby="devices-now-title"] .live-snr-value[...]`

OTHER `.live-table` TABLES AFFECTED:
NO

Traffic → Online Guests:
UNCHANGED

Traffic → Completed Sessions:
UNCHANGED

Other Home tables:
UNCHANGED

Devices page:
UNCHANGED

Device Card:
UNCHANGED

Visits:
UNCHANGED

Observations:
UNCHANGED

HEADER PRESENTATION:

Device / MAC:
left aligned, unchanged.

Centered headers:
- Type
- Auth
- IP
- AP
- Band
- RSSI
- SNR
- Uptime
- Traffic

ROW VERTICAL PRESENTATION:

Within Home → Online Devices only:

all cells after the two-line `Device / MAC` cell use:

`vertical-align: middle`

This places the one-line values on the visual middle axis of:

Device name
MAC address

rather than aligning them to either the upper or lower text line.

TYPE ↔ AUTH SPACING:

Type column now uses a compact stable width:

`width: 64px`
`min-width: 64px`

with small local horizontal padding.

Type remains immediately after Device / MAC.

Android icon:
same asset
same size
same matching contract

NULL:
same semantic

raw values such as `phone`:
same semantic

SNR PRESENTATION:

Source:
`item.snr`

Displayed numeric value:
UNCHANGED

No derived SNR value is produced.

Tone selection:

SNR >= 25
→ good
→ #10b956

SNR >= 15 and < 25
→ warning
→ #f2c20d

SNR < 15
→ danger
→ #ed3038

SNR null / unavailable:
→ existing `—`
→ no semantic color assigned

The palette exactly reuses the existing RSSI green/yellow/red tones.

SNR text remains numeric.
No Good / Warning / Poor label is added.

RSSI + SNR COMBINED SCORE:
NO

RSSI LOGIC CHANGED:
NO

SNR SOURCE CHANGED:
NO

SNR VALUE SEMANTICS CHANGED:
NO

SNR SORTING CHANGED:
NO

SNR FILTERING CHANGED:
NO

JavaScript change is limited to:

`item.snr`
→ existing numeric value
→ presentation-only `data-tone`

The shared `clientPresentationCells()` builds the SNR cell once, so both existing Home Online Devices render paths receive identical presentation.

DEVICE TYPE PREDICATE:
UNCHANGED

Still strictly:
`device_type_key === "android"`

FRONTEND DEVICE TYPE NORMALIZATION:
NO

Raw `device_type`:
UNCHANGED

`device_type_key`:
UNCHANGED

Android asset:
UNCHANGED

Backend changes:
NO

API changes:
NO

Serializers changes:
NO

Models changes:
NO

Database changes:
NO

Security changes:
NO

Data contract changes:
NO

Fetch changes:
NO

Polling/timer changes:
NO

State changes:
NO

Tests changed:
NO

Dependencies added:
NO

GitHub write operations:
NO

Commit:
NO

Push:
NO

PR:
NO

Merge:
NO

Production:
NO

SYNTHETIC FIX-2 CONTEXT APPLY CHECK:
PASS

WHITESPACE APPLY CHECK:
PASS

git diff --check:
PASS

EXACT CENTRAL LAB APPLY:
TECH LEAD PENDING

OWNER VISUAL ACCEPTANCE:
PENDING