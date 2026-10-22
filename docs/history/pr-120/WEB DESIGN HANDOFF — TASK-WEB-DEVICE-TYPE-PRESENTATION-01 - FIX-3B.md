WEB DESIGN HANDOFF — FIX-3B

Repository:
ZaurNavi/CaptivePortal

Base exact tree:
3a3fadfafc827b0db24622a060e4343aa1e35653

Task:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01 / FIX-3B

RESULT:
Header-only optical centering correction for Home → Online Devices.

CHANGED_FILES:
- app/admin_web/static/admin.css

PATCH_FILE:
TASK-WEB-DEVICE-TYPE-PRESENTATION-01-FIX-3B.patch

PATCH_SHA256:
14d575ef602424f8f0b510eb7ba9c789d89e7c924266f2c97f9abad3b7444242

PATCH_SIZE:
1828 bytes

DIFF_STAT:
app/admin_web/static/admin.css | 3 ++-

1 file changed, 2 insertions(+), 1 deletion(-)

SCOPE:
Only:

.live-section[aria-labelledby="devices-now-title"]

Only Home → Current scoped online devices / Online Devices.

BODY CELLS CHANGED:
NO

BODY TEXT ALIGNMENT CHANGED:
NO

ROW GEOMETRY CHANGED:
NO

VERTICAL ALIGNMENT CHANGED:
NO

COLUMN WIDTHS CHANGED:
NO

TYPE SPACING CHANGED:
NO

ANDROID ICON CHANGED:
NO

SNR PRESENTATION CHANGED:
NO

RSSI PRESENTATION CHANGED:
NO

WHY THE HEADER LOOKED SHIFTED:

The table can distribute spare horizontal width across its columns.

Body values remain left-anchored inside their cells.

The previous:

text-align: center

centered each header label within the complete expanded header cell.

That geometric cell center therefore appeared visually too far right relative to the already accepted left-anchored content underneath.

FIX-3B corrects only the header's optical center.

For normal data headers the existing total horizontal header padding is preserved:

before:
left .55rem
right .55rem
total 1.10rem

after:
left .275rem
right .825rem
total 1.10rem

Because the total padding is unchanged:
- column sizing does not expand;
- body geometry does not move;
- table width does not change.

The header label alone moves approximately .275rem to the left.

TYPE HEADER:

Type has its existing compact 64px column and its existing total .8rem horizontal header padding preserved.

before:
left .4rem
right .4rem

after:
left .2rem
right .6rem

total remains:
.8rem

So Type receives the same optical correction without changing its column width or the Type ↔ Auth body spacing.

TARGET HEADERS:
- Type
- Auth
- IP
- AP
- Band
- RSSI
- SNR
- Uptime
- Traffic

Device / MAC:
UNCHANGED / LEFT ALIGNED

OTHER `.live-table`:
UNCHANGED

Traffic tables:
UNCHANGED

Devices page:
UNCHANGED

Device Card:
UNCHANGED

Backend:
NO CHANGES

API:
NO CHANGES

Data/source semantics:
NO CHANGES

Device Type normalization:
NO CHANGES

Tests:
NO CHANGES

JavaScript:
NO CHANGES

Dependencies:
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

SYNTHETIC CURRENT-CONTEXT APPLY CHECK:
PASS

WHITESPACE CHECK:
PASS

CENTRAL LAB EXACT APPLY:
TECH LEAD PENDING

OWNER VISUAL ACCEPTANCE:
PENDING