# WEB-DESIGN IMPLEMENTATION CONTRACT

## WEB-UX-PACK-03 / R1 — Home + Traffic + Device Detail Polish

**Owner:** Zaur Navi  
**Role issuing contract:** CaptivPortal Web Design Tech Lead / UI & UX Specification Lead  
**Implementation owner:** Coder  
**Status:** READY FOR CODER IMPLEMENTATION  
**Production authorization:** NO

---

# 1. Exact baseline

Implementation is pinned to the current accepted `main`:

```text
BASE_COMMIT =
be3fe14f929b45e4a1ca3991bc6a2a3011792641

BASE_TREE =
16a16d87c7dc821e0a5c4e6fe8ad67d4962d129d
```

Before changing any file, verify both values.

If local `HEAD` or tree does not match this baseline:

```text
STOP
BASELINE_DRIFT = YES
CHANGES_MADE = NONE
```

Do not silently rebase/adapt the task to a later `main`.

---

# 2. Task intent

This is a presentation / UI consolidation pass over already existing data and APIs.

The package contains five Owner-requested changes:

```text
A. Home / Online Devices:
   enlarge and truly center Fingerprint Type icons.

B. Home:
   merge Access Points · Last 24 hours into Access Points Now;
   put the 24h timeline above the Devices bar;
   make valid-history unknown/gap segments red;
   visually promote Download / Upload / Total per-AP rates.

C. Device Detail:
   show closed Visit traffic in human-readable B/KB/MB/GB/TB units.

D. Traffic:
   move Completed Guest Session Traffic to the very end of the page.

E. Traffic:
   merge Network Traffic History and Traffic by AP into one visual card;
   Site/network chart first, AP charts after it;
   AP chart presentation sorted naturally by AP display name.
```

This task does **not** redefine source data, evidence semantics, API contracts,
feature flags, traffic formulas, Fingerprint classification, Controller identity,
or Visit traffic meaning.

---

# 3. Absolute non-goals / invariants

Do not introduce:

```text
new API endpoints
new DB/table/schema
new collector
new background worker
new classification logic
new device-type inference
new Traffic calculation
new AP history semantics
new Visit traffic semantics
new feature flag
new production configuration
new assets
```

Do not change:

```text
Home Type canonical machine mapping
Fingerprint classification states/statuses
Controller-first Platform semantics
Devices-list Type icon size
Device Card Controller/Fingerprint separation
Traffic API request/response contracts
Traffic source selection/evidence semantics
Traffic threshold logic on Home aggregate Traffic Now
AP Traffic Share product
Home AP-24H backend contract
Home AP-24H timeline bucket semantics
Visit Lifecycle persistence
reported_traffic_total_bytes storage/API value
```

No production source editing.

---

# 4. CHANGE A — Home / Online Devices / Type

## 4.1 Current baseline

The shared Fingerprint Type icon is currently 22×22 px and Home uses the shared
`.fingerprint-type-icon` inside `.live-fingerprint-type-cell`.

## 4.2 Required Home presentation

On **Home → Online Devices only**:

```text
TYPE ICON VISUAL SIZE = 44px × 44px
```

This is intentionally 2× the current size.

Do **not** enlarge the Type icon on the Devices page. Devices remains at the
current 22×22 presentation.

The Home Type column must be visually centered as one unit:

```text
header "Type" = horizontally centered
icon wrapper = horizontally centered under the header
icon = vertically centered in the table cell
```

Do not rely only on inherited `text-align`. The final computed presentation must
make the icon center align with the `Type` heading.

Recommended implementation shape:

```text
.live-fingerprint-type-header
    -> explicit centered alignment

.live-fingerprint-type-cell .fingerprint-type-icon
    -> 44×44
    -> block/flex centering or margin-inline:auto

.live-fingerprint-type-cell .fingerprint-type-icon img
    -> 44×44
```

The global `.fingerprint-type-icon` 22×22 default must remain valid for Devices.

## 4.3 Semantics / accessibility

No text is added next to the Home Type icon.

Preserve the existing authoritative icon selection:

```text
state + status + canonical_value_id
```

Preserve existing wrapper `aria-label` / `title` and decorative nested image.

No hostname, Controller type, Platform, MAC, vendor or browser inference.

---

# 5. CHANGE B — Home / merge AP 24h into Access Points Now

## 5.1 Target product structure

There must be **one** current AP card:

```text
Access Points Now
```

The standalone outer card:

```text
Access Points · Last 24 hours
```

must disappear as an independent card.

The existing AP-24H information is not deleted. It is moved into the
`Access Points Now` surface.

## 5.2 Card-level information

`Access Points Now` remains the identity / roster / pagination owner.

At the top of the card, preserve the useful AP-24H global information in a
compact integrated area:

```text
24h rolling window
AP-24H source/state message
AP-24H summary
```

Existing hooks may be retained where useful:

```text
home-ap-24h-window
home-ap-24h-state
home-ap-24h-status
home-ap-24h-message
home-ap-24h-summary
```

They must no longer create a second outer `.card`.

The AP-24H explanatory disclaimer remains available, but should be visually
secondary:

```text
Unavailable duration is controller-observed persisted evidence,
not physical downtime SLA.
```

## 5.3 One AP row, one AP identity

The unified AP row owns the AP name/MAC once.

Do not repeat AP name or MAC inside the 24h, Devices or Traffic subregions.

Required logical order inside each AP row:

```text
1. AP identity / current status / existing AP facts
2. AP MAC
3. 24-hour timeline
4. Devices count + relative bar
5. Traffic status
6. prominent Download / Upload / Total rates
7. secondary Traffic source / observed time / evidence detail
```

The timeline must be placed **above** the Devices bar.

## 5.4 AP-24H join rule

Join AP current roster and AP-24H data only by exact canonical:

```text
ap_mac
```

Never join by display name.

`Access Points Now` remains the visible roster owner.

The AP-24H endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/home/ap-24h
```

No per-AP request is allowed.

## 5.5 AP-24H pagination after consolidation

The separate visible AP-24H pagination is removed:

```text
home-ap-24h-more = no visible control
```

Only this user-facing AP pagination remains:

```text
Load more access points
live-ap-more
```

On a root AP-24H refresh:

```text
follow its cursor chain sequentially to exhaustion
build a map ap_mac -> AP-24H item
publish the completed accepted map atomically
```

Requirements:

```text
NO N+1
NO per-AP requests
NO backend pagination change
NO global page-size increase
NO duplicate rows
NO stale generation publishing over a newer refresh
```

AP-24H data for APs not yet visible in the current roster may remain cached.
When `Load more access points` reveals a cached AP, enrich that row immediately.

The current AP roster pagination and ordering are otherwise unchanged.

## 5.6 Fail-soft behavior

AP-24H failure must never break the current AP roster.

If current AP data is usable but AP-24H is unavailable:

```text
current AP identity = remains usable
Devices = remains usable if its source is usable
Traffic = remains usable if its source is usable
24h presentation = neutral unavailable / "—"
```

Do **not** paint a completely unavailable/missing AP-24H source as a fake red
24-hour outage.

A valid AP-24H item with valid timeline buckets is different: bucket colors
follow section 5.7 below.

## 5.7 Timeline colors

Existing semantic states remain unchanged.

Presentation colors must be:

```text
operational -> green
degraded    -> yellow
unavailable -> red
unknown     -> red
```

The Owner specifically wants the currently gray/colorless valid-history gap /
unknown segment to be visually red.

This is **presentation only**:

```text
bucket.ap_state remains "unknown"
title/tooltip remains "unknown"
no backend rewrite to "unavailable"
no fabricated downtime semantics
```

## 5.8 Per-AP Traffic visual hierarchy

The current per-AP rate line is too visually weak.

Do not change Traffic semantics or threshold colors. Instead, make the rates
immediately scannable.

Target presentation:

```text
Traffic · <rate_status>

Download ↓   <RATE>
Upload ↑     <RATE>
Total ↓↑     <RATE>

Source <Wired|LAN> · observed <time>
```

The rate trio must be visually dominant inside the AP row:

```text
values: approximately 1rem or slightly larger
font-weight: ~700–750
clear spacing
desktop: compact 3-column/flex row
small screens: wrap without horizontal overflow
```

Labels may be smaller/muted; numeric values must not look like ordinary
`live-detail` metadata.

Preserve:

```text
0 Mbps = valid value
null/unavailable = —
rate_status meaning unchanged
selected_source meaning unchanged
observed_at meaning unchanged
no AP-specific green/yellow/red throughput threshold
```

---

# 6. CHANGE C — Device Detail / closed Visit Traffic

## 6.1 Current baseline

Device Detail Visit rows currently expose:

```text
Traffic (bytes) = <raw integer>
```

The underlying field is:

```text
reported_traffic_total_bytes
```

## 6.2 Required presentation

Keep the raw value and backend contract unchanged.

Render it through the existing human-readable byte formatter used elsewhere by
Admin Web.

Presentation label:

```text
Traffic
```

Examples:

```text
0           -> 0 B
842         -> 842 B
1024        -> 1 KB
1048576     -> 1 MB
19608371    -> human-readable MB
2300000000  -> human-readable GB
null        -> —
```

Use binary 1024 scaling, consistent with the existing
`formatDeviceBytes()` Admin presentation.

Do not add a second raw-bytes line.

No change is requested to Visit duration formatting in this task.

---

# 7. CHANGE D — Traffic / Completed Guest Session Traffic must be last

Move the complete existing block:

```text
Completed Guest Session Traffic
traffic-completed-sessions-panel
```

to the bottom of the Traffic page.

It must be the **last enabled visual panel**, after all existing Traffic panels,
including `Traffic Evidence / Quality` when that panel is enabled.

So, when Traffic Evidence is enabled:

```text
Traffic Evidence / Quality
↓
Completed Guest Session Traffic
```

No Completed Sessions behavior changes:

```text
same API
same range controls
same pagination
same validation
same refresh behavior
same table
same evidence semantics
```

This is presentation order only.

---

# 8. CHANGE E — Traffic / combine Network Traffic History + Traffic by AP

## 8.1 One outer historical card

Visually merge these two existing cards:

```text
Network Traffic History
Traffic by AP
```

into one outer card.

Chosen title when AP Traffic is enabled:

```text
Network & AP Traffic History
```

If History is enabled but `traffic_by_ap_enabled` is false, use the existing:

```text
Network Traffic History
```

The outer identity should remain the existing History panel where practical:

```text
traffic-history-panel
```

The existing `traffic-ap-panel` may remain as an internal subsection hook, but
must no longer render as a second outer `card card-wide`.

## 8.2 Required visual order

Inside the combined card:

```text
1. main Site/network History heading/state/meta/legend
2. main Network Traffic History chart
3. AP subsection heading / AP-specific state/meta/range controls as applicable
4. AP1 chart
5. AP2 chart
6. AP3 chart
...
```

The general Network chart must always be first.

Do not move Period Statistics or Peak Load into this card.

Do not merge AP Traffic Share into this card.

## 8.3 Existing range semantics must survive

This visual merge must **not** redesign the accepted Traffic range behavior.

When:

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED = true
```

preserve:

```text
History range control = controls History
AP range control      = controls Traffic by AP
```

The AP range control can be placed in the AP subsection header.

When independent ranges are disabled, preserve the existing shared Network range
behavior.

Do not change:

```text
Traffic coordinator architecture
historical lane admission
products= request contract
request cadence
timeouts
query deadlines
validation rules
backend API
```

## 8.4 Natural AP chart presentation sorting

The server/API contract currently provides a canonical order which the frontend
validates. **Do not weaken or alter that validation.**

After validation, create a presentation copy and sort AP chart cards by:

```text
1. display_name — natural alphanumeric, case-insensitive
2. ap_mac       — ascending deterministic tie-break
```

Required natural result:

```text
AP1
AP2
AP3
...
AP9
AP10
AP11
```

Not:

```text
AP1
AP10
AP11
AP2
```

Only the `Traffic by AP` chart presentation is changed.

Do **not** silently apply this new order to AP Traffic Share or other products.

## 8.5 AP graph contents

Keep the existing AP chart semantics:

```text
Download series
Upload series
AP identity
metrics
coverage/evidence text
current snapshot/evidence information
```

Do not discard evidence just to make the card prettier.

The AP cards may stay responsive subcards inside the combined outer card.
Their DOM order must follow the natural sort above.

---

# 9. Responsive / accessibility acceptance

## Home

At desktop and mobile/table-scroll widths:

```text
44×44 Home Type icon does not clip
Type heading and icon are aligned
Online Devices remains horizontally usable
AP row does not overflow viewport
24h timeline remains legible
rate trio wraps cleanly
```

## Traffic

```text
main History chart stays full-width within the combined card
AP subcards remain responsive
natural AP order is preserved in DOM order
no nested layout causes horizontal page overflow
Completed Sessions remains last at desktop and mobile
```

## Accessibility

Preserve existing:

```text
aria-labelledby
role/status live regions
chart title/description
Fingerprint icon aria-label/title
button aria-pressed behavior
```

Do not use color as the only indication of AP-24H bucket state: existing title /
tooltip state text must remain.

---

# 10. Expected implementation area

Expected primary files:

```text
app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.css
app/admin_web/static/admin.js
```

Expected tests may include:

```text
tests/admin_web/test_web_ux_pack_02.py
tests/admin_web/test_home_ap_24h_frontend.py
tests/admin_web/test_home_ap_24h.py
tests/admin_web/test_traffic_history_frontend.py
tests/admin_web/test_admin_ui_frontend.py
```

A new focused test file such as:

```text
tests/admin_web/test_web_ux_pack_03.py
```

is allowed and preferred if it keeps this package explicit.

Minimal documentation updates are expected where current docs enumerate Traffic
panel order or claim that AP-24H is a separate Home presentation card, for
example:

```text
docs/modules/admin-web.md
docs/modules/traffic.md
```

Do not make unrelated documentation rewrites.

## Backend scope rule

No backend change is currently expected.

If implementation genuinely requires changes to:

```text
app/analytics/*
app/visit_lifecycle/*
Admin API contracts
DB/schema
collector/worker behavior
```

then:

```text
STOP
WEB DESIGN → TECH LEAD DEPENDENCY REQUIRED = YES
```

Explain the exact blocker before implementing the backend change.

---

# 11. Required tests / gates

Coder must add focused regression coverage for all of the following.

## A. Home Type

```text
Home computed/style contract = 44×44
Home Type header centered
Home Type icon centered
Devices list remains 22×22
icon machine mapping unchanged
```

## B. Unified Access Points Now

```text
no second outer AP-24H card
AP24 timeline is above Devices bar
one AP name/MAC identity
only live-ap-more visible as AP pagination
home-ap-24h-more absent from visible UI
AP24 pages are consumed without N+1
join is exact ap_mac
stale generation cannot overwrite current generation
AP24 failure does not clear AP roster
valid unknown timeline bucket is visually red
operational green / degraded yellow / unavailable red
source-unavailable-with-no-item is not fabricated as red outage
```

## C. AP rates

```text
Download / Upload / Total have promoted markup/classes
0 Mbps remains visible as 0 Mbps
unavailable remains —
source/observed metadata remains
```

## D. Device Detail Visit

```text
reported traffic uses formatDeviceBytes
raw "Traffic (bytes)" presentation removed
0 -> 0 B
MB case
GB case
null -> —
```

## E. Traffic page

```text
Completed Guest Session Traffic is last panel
History + Traffic by AP share one outer card
general History chart precedes every AP chart
Traffic by AP no longer owns a second outer card
independent range controls keep existing semantics
non-independent range semantics unchanged
API/request product contracts unchanged
```

## F. AP natural order

Test at minimum:

```text
AP1
AP2
AP10
```

and a deterministic same-name MAC tie.

The test must prove:

```text
validation still accepts/requires the canonical API order
render order is the natural display-name order after validation
```

## G. Compatibility

Run the relevant existing Home/AP24/Traffic/Admin frontend tests in addition to
the new focused tests.

Also run:

```text
python compileall for changed Python/tests if any Python changed
node --check app/admin_web/static/admin.js
git diff --check
```

No requirement to run the entire repository suite unless a changed dependency or
existing project gate makes that necessary.

---

# 12. Visual evidence required from Coder

Materialize screenshots using the actual changed templates/CSS/JS.

Minimum:

```text
1. Home desktop — Online Devices Type + unified Access Points Now visible
2. Home narrow/mobile — unified AP row without page overflow
3. Traffic desktop — combined Network & AP Traffic History visible, AP order visible
4. Traffic page lower section — proves Completed Guest Session Traffic is last
5. Device Detail — closed Visit with human-readable Traffic
```

Synthetic local QA data is acceptable for presentation screenshots.

Do not use fake production claims.

---

# 13. Coder handoff format

Return one handoff containing:

```text
TASK =
WEB-UX-PACK-03-R1

BASE_COMMIT =
be3fe14f929b45e4a1ca3991bc6a2a3011792641

BASE_TREE =
16a16d87c7dc821e0a5c4e6fe8ad67d4962d129d

LOCAL_HEAD =
...

LOCAL_TREE =
...

CHANGED_FILES =
...

DIFF_STAT =
...

TESTS_RUN =
...

TEST_RESULT =
PASS/FAIL

NODE_CHECK =
PASS/FAIL

DIFF_CHECK =
PASS/FAIL

WORKTREE_STATUS =
...

PATCH_PATH =
...

PATCH_SHA256 =
...

VISUAL_EVIDENCE =
...

BACKEND_CHANGE =
NO / YES

TECH_LEAD_DEPENDENCY =
NO / exact blocker

COMMIT =
NO

PUSH =
NO

PR =
NO

MERGE =
NO

DEPLOY =
NO

PRODUCTION =
UNTOUCHED
```

Also include a concise implementation summary and every changed file.

---

# 14. Publication / production governance

For this implementation phase:

```text
COMMIT = NO
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
PRODUCTION ACTIONS = NO
```

Coder stops after producing the exact review candidate, patch, tests and visual
evidence.

Web Design Tech Lead performs source/UI acceptance first.

Owner separately authorizes publication and production.

---

# 15. Acceptance target

The package is complete only when the Owner-visible result is:

```text
Home:
- Type icon is clearly larger and centered.
- Access Points Now owns current facts + 24h timeline + Devices + Traffic.
- 24h gap/unknown sections are visibly red.
- AP speeds are immediately readable.

Device Detail:
- closed Visit traffic reads naturally in B/KB/MB/GB/TB.

Traffic:
- Network chart and AP charts live in one History card.
- Network chart is first.
- AP charts read AP1, AP2, AP3 ... AP10 naturally.
- Completed Guest Session Traffic is the final panel on the page.
```

No product semantics are changed to achieve this presentation.
