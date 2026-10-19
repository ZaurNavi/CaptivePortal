# WEB-DESIGN IMPLEMENTATION CONTRACT

## TASK

**Task ID:** `HOME-UX-REFINEMENT-01`  
**Project:** CaptivPortal  
**Repository:** `ZaurNavi/CaptivePortal`

### Exact baseline

```text
BASE_COMMIT =
c2635b467dc83e3f574ed204184a2e982f925a9a

BASE_TREE =
bb1d5f7951d77e8a65a6af4856b07d80fc9122f0
```

Coder must verify the baseline before changing files.

---

# 1. OWNER INTENT

Refine the Home page as one coherent implementation package rather than a series of micro-patches.

Goals:

1. Make the top Current Network summary cards more compact vertically.
2. Align their primary metric values on one visual horizontal axis.
3. Move **Online Devices** above **Traffic Now**.
4. Improve **Traffic Now** with direction arrows and severity colors.
5. Improve Home **Platform** presentation:
   - Controller remains primary.
   - Authoritative PRODUCTION Fingerprint platform becomes fallback only when Controller Platform is unresolved.
6. Preserve all existing source semantics, Current State behavior, Traffic semantics, Device Type normalization rules, and Device Card source separation.

---

# 2. CURRENT STATE

Home currently contains five top summary cards:

```text
Online Now
Authorized
Waiting Authorization
Other / Unknown
AP Online / Total
```

Current page ordering places `Traffic Now` before `Online Devices`.

Home Online Devices currently distinguishes:

```text
Type
=
Fingerprint device_class

Platform
=
Controller / Omada device_type
```

The Fingerprint presentation layer already contains authoritative `platform_result`, but Home currently receives only the compact Fingerprint `Type` projection.

---

# 3. TARGET HOME ORDER

Required page order:

```text
Current Network summary cards

existing Current-State warning panels, when applicable

Online Devices

Traffic Now
  ├─ Download / Upload / Total / Traffic evidence
  └─ Traffic by AP

then all remaining existing Home sections
in their existing relative order
```

Frozen requirement:

```text
Online Devices
MUST appear before
Traffic Now
```

`Traffic by AP` remains part of the Traffic Now section.

Do not reorder unrelated Home sections beyond what is required to place Online Devices before Traffic Now.

---

# 4. CURRENT NETWORK SUMMARY — DESIGN CONTRACT

## 4.1 Composition

Keep the same five cards and existing data:

```text
Online Now
Authorized
Waiting Authorization
Other / Unknown
AP Online / Total
```

No metric may be removed or renamed.

## 4.2 Vertical density

Make the cards visibly more compact vertically.

Reduce, where appropriate:

```text
top/bottom internal whitespace
heading → metric spacing
metric → secondary detail spacing
```

Do not significantly reduce card width.

Do not reduce readability.

Primary metric values remain the dominant visual element.

## 4.3 Primary metric alignment

On desktop, all five primary metric values must sit on one common horizontal visual axis despite different heading lengths.

Longer headings must not push the primary metric lower than neighboring cards.

Secondary freshness/detail rows may occupy different amounts of space below the primary metric line.

## 4.4 Scope

Do not globally change `.card` geometry.

Compact styling must be scoped to Home summary `.live-metrics` cards only.

Do not unintentionally change:

- Traffic cards
- Health cards
- Activity cards
- other Admin pages

---

# 5. ONLINE DEVICES — PLACEMENT CONTRACT

Move the existing **Online Devices** panel as one unit.

Move together:

```text
title
filters
state
table
pagination / Load More
```

Do not rebuild the table from scratch.

Preserve existing:

```text
filter semantics
sort semantics
pagination
Load More
refresh behavior
Current State source
RSSI presentation
SNR presentation
Auth presentation
Band presentation
Type semantics
column ordering
horizontal table scrolling
```

except for the approved Home Platform behavior in this contract.

---

# 6. TRAFFIC NOW — VISUAL CONTRACT

## 6.1 Existing labels

Preserve:

```text
Download Now
Upload Now
Total Traffic Now
Traffic evidence
```

## 6.2 Direction indicators

Render these exact visible symbols before the numeric value:

```text
Download:
↓ 42.13 Mbps

Upload:
↑ 8.20 Mbps

Total:
↓↑ 50.33 Mbps
```

Frozen symbols:

```text
Download = ↓
Upload   = ↑
Total    = ↓↑
```

Do not replace Total with `↕`.

No external icon library is required.

Unicode arrows are sufficient.

## 6.3 Traffic severity thresholds

Each visible Traffic Now numeric metric is classified independently by its own existing numeric Mbps value.

Frozen boundaries:

```text
value <= 50 Mbps
→ GOOD / GREEN

value > 50 Mbps
AND
value <= 70 Mbps
→ WARNING / YELLOW

value > 70 Mbps
→ DANGER / RED
```

Boundary examples:

```text
0       → green
49.99   → green
50.00   → green

50.01   → yellow
60.00   → yellow
70.00   → yellow

70.01   → red
100.00  → red
```

Therefore:

```text
50 = GREEN
70 = YELLOW
```

## 6.4 Color scope

Color the visible metric value line.

The arrow may inherit the same tone.

Do not recolor the entire card background.

Do not turn these cards into alert panels.

## 6.5 Unavailable state

If existing Traffic freshness/availability semantics render:

```text
—
```

then no traffic severity color is assigned.

Unavailable remains neutral.

Do not parse the formatted text back into a number.

Tone must be derived from the existing validated numeric traffic value already used by the renderer.

## 6.6 Existing Traffic semantics

Do not change:

```text
Current Traffic source
freshness
coverage
selected source
source mixing rules
AP traffic calculation
traffic API
traffic aggregation
zero semantics
```

This is a presentation cue only.

---

# 7. HOME PLATFORM — TECH LEAD DECISION

The required technical dependency has been resolved.

Approved direction:

```text
DEPENDENCY REQUEST = ACCEPTED
ARCHITECT REVIEW    = NOT REQUIRED
BACKEND EXTENSION   = APPROVED / BOUNDED
CLASSIFIER CHANGE   = NO
FINGERPRINT SEMANTICS CHANGE = NO
DEVICE CARD CHANGE  = NO
AUTH/CAPPORT CHANGE = NO
```

This task may extend the bounded Home read/presentation contract as defined below.

---

# 8. HOME TYPE — FROZEN

Home `Type` remains:

```text
Type
=
Fingerprint device_class
```

Controller must never backfill `Type`.

Existing Type states remain:

```text
resolved             → value
completed unresolved → Unknown
no result            → —
unavailable          → —
```

Do not change this semantic.

---

# 9. HOME PLATFORM — PRECEDENCE CONTRACT

Home `Platform` becomes a Controller-first effective presentation.

Exact precedence:

```text
IF Controller Platform is usable:
    use Controller Platform

ELSE IF authoritative PRODUCTION Fingerprint Platform is resolved:
    use Fingerprint Platform

ELSE:
    use honest unresolved presentation
```

This applies to Home only.

It does not create general reconciliation between Controller and Fingerprint.

---

# 10. CONTROLLER PLATFORM ELIGIBILITY

Controller Platform is usable when:

```text
device_type_key != null
AND
device_type_key != "unknown"
```

For fallback eligibility:

```text
device_type_key == null
→ Controller unresolved

device_type_key == "unknown"
→ Controller unresolved
```

Do not create a heuristic list of other values.

Do not independently reinterpret these as unresolved:

```text
other
generic
n/a
unavailable
undefined
phone
mobile
```

unless an existing contract already defines such semantics.

No browser normalization of raw `device_type` is allowed.

---

# 11. AUTHORITATIVE FINGERPRINT PLATFORM PROJECTION

Add a compact authoritative Fingerprint Platform presentation to the Home enrichment/read path.

Approved conceptual projection:

```text
fingerprint_platform = {
    state,
    status,
    canonical_value_id,
    value
}
```

Preferred source path:

```text
DeviceFingerprintPresentationService
→ existing get_many(...)
→ same PRODUCTION-only batch read
→ compact_platform()
```

Requirements:

```text
NO second fingerprint query
NO query-per-device
NO N+1
KEEP Site scope
KEEP one bounded batch
KEEP PRODUCTION-only authority
```

Existing:

```text
fingerprint_type
```

remains unchanged.

---

# 12. FINGERPRINT PLATFORM STATE MATRIX

## 12.1 No authoritative production result

```text
state = no_result
status = null
canonical_value_id = null
value = —
```

## 12.2 Fingerprint read/persistence unavailable

```text
state = unavailable
status = null
canonical_value_id = null
value = —
```

## 12.3 Resolved platform

Example:

```text
state = classified
status = resolved
canonical_value_id = android
value = Android
```

## 12.4 Completed but unresolved

For any of:

```text
unknown
insufficient_evidence
conflicting_evidence
recognized_out_of_scope
```

return:

```text
state = classified
status = <exact existing status>
canonical_value_id = null
value = Unknown
```

Only:

```text
status == resolved
AND
canonical_value_id != null
```

makes Fingerprint eligible as Home Platform fallback.

---

# 13. AUTHORITATIVE EFFECTIVE HOME PLATFORM

Tech Lead decision:

Do not duplicate Controller/Fingerprint precedence in browser JavaScript.

Build an authoritative Home presentation object in the Admin presentation/query layer after Controller current-client serialization and Fingerprint batch presentation are both available.

Required conceptual response object:

```text
platform_presentation = {
    source,
    value,
    key
}
```

Where:

```text
source =
controller | fingerprint | none

value =
exact value to render in Home Platform

key =
canonical effective machine key used for presentation decisions
```

Browser behavior should remain intentionally simple:

```text
render platform_presentation.value

if platform_presentation.key === "android":
    render existing Android icon
```

Appropriate composition boundary:

```text
AdminQueryService
or
small Admin Home presentation helper
```

Do not place Controller precedence logic inside:

```text
Fingerprint classifier
ClassificationResult
classification DB
classification read service
fusion
knowledge
```

---

# 14. PLATFORM UNRESOLVED DISPLAY

Exact unresolved branch:

```text
Controller explicitly Unknown
→ display Unknown

Controller unresolved
+
completed Fingerprint platform exists but is unresolved
→ display Unknown

Controller absent
+
Fingerprint no_result
→ display —

Controller absent
+
Fingerprint unavailable
→ display —
```

Examples:

```text
Controller Android
Fingerprint ChromeOS resolved
→ Android
→ source controller

Controller Unknown
Fingerprint Android resolved
→ Android
→ source fingerprint

Controller null
Fingerprint Android resolved
→ Android
→ source fingerprint

Controller Windows
Fingerprint Android resolved
→ Windows
→ source controller

Controller Unknown
Fingerprint conflicting
→ Unknown

Controller null
Fingerprint unknown
→ Unknown

Controller null
Fingerprint no_result
→ —

Controller null
Fingerprint unavailable
→ —
```

No source may manufacture a resolved value from unresolved evidence.

---

# 15. ANDROID ICON CONTRACT

Use the existing Android asset.

Android machine decision:

```text
platform_presentation.key === "android"
```

Then render the existing Android icon.

The canonical effective key may originate from:

```text
Controller device_type_key
```

or:

```text
Fingerprint platform canonical_value_id
```

depending on precedence.

Forbidden:

```text
trim(raw string)
lowercase(raw string)
casefold(raw string)
regex(raw string)
contains("android")
hostname inference
vendor inference
system_name inference
```

Do not introduce new raw-string Device Type normalization.

---

# 16. PLATFORM PROVENANCE

Visible Home provenance badge:

```text
NO
```

Do not render:

```text
Android (Fingerprint)
```

Do not add a new Source column.

Technical provenance is required via:

```text
platform_presentation.source
```

Values:

```text
controller
fingerprint
none
```

---

# 17. FAIL-SOFT CONTRACT

Fingerprint remains advisory and optional.

If Fingerprint read fails and Controller Platform is usable:

```text
Platform = Controller
```

If Fingerprint read fails and Controller Platform is unresolved:

```text
Platform = existing honest unresolved presentation
```

Fingerprint failure must not:

```text
fail Home
cause full-page 503
suppress Controller data
substitute into Type
```

---

# 18. DEVICE CARD — EXPLICITLY OUT OF SCOPE

Do not change Device Card reconciliation semantics.

Device Card continues to display:

```text
Controller Platform
Fingerprint Platform
```

as separate values.

They may disagree.

Home fallback must not become a general product-wide reconciliation rule.

---

# 19. RESPONSIVE CONTRACT

## Desktop

- Existing five-column summary layout remains when viewport permits.
- Primary summary values align horizontally.
- Online Devices retains current table density and horizontal-overflow behavior.
- Traffic layout retains current desktop geometry.

## Tablet / narrow desktop

- Existing responsive grid behavior remains.
- Summary cards may wrap according to existing breakpoints.
- Cards within the same rendered row should keep visually consistent internal metric alignment.

## Mobile

- Do not force five summary cards into one row.
- Do not remove information just to fit.
- Online Devices keeps existing horizontal table-scroll behavior unless an existing project contract already specifies otherwise.
- Traffic arrows and traffic severity colors remain visible.
- No new mobile-specific interaction is required.

---

# 20. INTERACTION CONTRACT

No new interaction is introduced.

Preserve:

```text
Home Current refresh lifecycle
Online Devices filters
Online Devices sorting
Load More
Traffic state handling
Traffic by AP Load More
existing aria/live regions
```

Moving Online Devices changes placement only.

No new button.

No dropdown.

No hover-only required information.

---

# 21. LIKELY IMPLEMENTATION MAP

Likely affected production areas:

```text
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.css
app/admin_web/static/admin.js
app/admin_web/device_fingerprint_presentation.py
app/admin_web/query_service.py
```

plus the exact existing Home serialization/presentation boundary needed to carry the approved objects.

This list is an implementation map only.

It is not permission for unrelated changes.

---

# 22. DOCUMENTATION UPDATES

Because this task changes current Home Platform product truth, inspect and update current documentation where applicable.

At minimum:

```text
README.md
README_RU.md
docs/README.md
docs/modules/admin-web.md
docs/modules/device-fingerprint.md
```

New documentation must accurately state:

```text
Home Type =
Fingerprint device_class

Home Platform =
Controller-first effective presentation;
resolved Fingerprint platform is fallback only
when Controller Platform is unresolved.

Device Card =
Controller Platform and Fingerprint Platform remain separate.
```

Do not rewrite historical task evidence as if the previous contract never existed.

---

# 23. EXISTING CONTRACTS TO PRESERVE

Preserve:

```text
same-origin Admin API boundary
Site authorization
Current State semantics
Traffic semantic ownership
Fingerprint PRODUCTION-only authority
one bounded Fingerprint batch
Fingerprint fail-soft behavior
Type = Fingerprint device_class
Device Card source separation
raw device_type evidence
canonical device_type_key
no frontend Device Type normalization
Android canonical-key matching
RSSI presentation
SNR presentation
Auth presentation
Band presentation
pagination
sorting
filters
security
authentication
CAPPORT behavior
```

---

# 24. OUT OF SCOPE / FORBIDDEN

```text
NO classifier redesign
NO Fingerprint fusion change
NO new evidence interpretation
NO new taxonomy
NO new scoring
NO Traffic calculation change
NO Current State semantic change
NO RSSI redesign
NO SNR redesign
NO Device Card redesign
NO Devices page redesign
NO Visits change
NO Observations change
NO Traffic page change
NO Auth/CAPPORT change
NO unrelated Home redesign
NO unrelated refactor
NO "cleanup while here"
NO new dependency/CDN/icon library
NO production work
```

A DB/schema change is not authorized by this Web Design contract.

If Coder discovers a technical requirement outside this approved boundary, stop and return:

```text
CODER BLOCKER
```

Do not broaden scope silently.

---

# 25. ACCEPTANCE CRITERIA

## Summary cards

```text
AC-01
Five top Home summary cards are visibly shorter vertically than baseline.

AC-02
Their width/layout remains consistent with the current Home structure.

AC-03
Primary values of all five cards align on one horizontal visual axis on desktop.

AC-04
Secondary detail/freshness text remains visible.
```

## Page ordering

```text
AC-05
Online Devices appears before Traffic Now.

AC-06
Online Devices existing filters/sort/pagination behavior is unchanged.
```

## Traffic Now

```text
AC-07
Download displays ↓ before the value.

AC-08
Upload displays ↑ before the value.

AC-09
Total displays ↓↑ before the value.

AC-10
Traffic numeric value <= 50 Mbps is green.

AC-11
Traffic numeric value > 50 and <= 70 Mbps is yellow.

AC-12
Traffic numeric value > 70 Mbps is red.

AC-13
50.00 Mbps is green.

AC-14
70.00 Mbps is yellow.

AC-15
Unavailable Traffic remains neutral.

AC-16
Traffic numeric/source semantics are unchanged.
```

## Platform

```text
AC-17
Home Type behavior is unchanged.

AC-18
Usable Controller Platform always wins over Fingerprint.

AC-19
Controller Unknown + resolved Fingerprint Platform uses Fingerprint.

AC-20
Controller missing/null + resolved Fingerprint Platform uses Fingerprint.

AC-21
Unresolved Fingerprint never manufactures a resolved Platform.

AC-22
Fingerprint unavailable does not break Home.

AC-23
Effective Controller Android shows Android icon.

AC-24
Effective Fingerprint-fallback Android shows Android icon.

AC-25
Android decision uses canonical effective key only.

AC-26
No raw-string Device Type normalization is introduced.

AC-27
Home Fingerprint read remains one bounded PRODUCTION-only batch.

AC-28
Device Card behavior remains unchanged.

AC-29
Other Admin pages receive no visual regression from Home-specific CSS changes.

AC-30
Current project documentation reflects the new Home-only Platform fallback.
```

---

# 26. REQUIRED PLATFORM REGRESSION MATRIX

Focused tests must prove at least:

```text
1.
Controller Android
Fingerprint ChromeOS resolved
→ Platform Android
→ source controller
→ Android icon

2.
Controller Unknown
Fingerprint Android resolved
→ Platform Android
→ source fingerprint
→ Android icon

3.
Controller null
Fingerprint Android resolved
→ Platform Android
→ source fingerprint
→ Android icon

4.
Controller Windows
Fingerprint Android resolved
→ Platform Windows
→ source controller
→ NO Android icon

5.
Controller Unknown
Fingerprint unknown
→ Platform Unknown
→ key null
→ no Android icon

6.
Controller null
Fingerprint conflicting_evidence
→ Platform Unknown
→ key null

7.
Controller null
Fingerprint insufficient_evidence
→ Platform Unknown

8.
Controller null
Fingerprint recognized_out_of_scope
→ Platform Unknown

9.
Controller null
Fingerprint no_result
→ Platform —

10.
Controller null
Fingerprint unavailable
→ Platform —
→ Home remains usable

11.
Fingerprint canonical_value_id = android
→ icon decision uses canonical ID

12.
No raw-string Android normalization is introduced.

13.
Home still performs ONE bounded Fingerprint batch read.

14.
PRE_ACCEPTANCE_CANDIDATE cannot enter Home fallback.

15.
Site mismatch / Fingerprint read failure remains fail-soft.

16.
Home Type semantics remain unchanged.

17.
Device Card remains separate Controller Platform / Fingerprint Platform.
```

---

# 27. REQUIRED TRAFFIC FOCUSED TESTS

Focused tests must prove:

```text
49.99 → green
50.00 → green
50.01 → yellow
70.00 → yellow
70.01 → red

null/unavailable → neutral

Download → ↓
Upload → ↑
Total → ↓↑

0.00 Mbps remains a valid numeric zero
```

Do not weaken/remove existing traffic freshness or unavailable behavior tests.

---

# 28. REQUIRED LAYOUT / TEMPLATE TEST EXPECTATIONS

Where practical within existing frontend/template tests, prove:

```text
Online Devices section precedes home-traffic

all five summary metrics remain present

existing Online Devices IDs/hooks remain present

existing Traffic IDs/hooks remain present
```

Do not introduce brittle pixel-perfect automated tests.

Final visual acceptance is performed by Owner / Web Design Tech Lead.

---

# 29. CODER TEST EXECUTION BOUNDARY

Before handoff, Coder must run only the minimum focused tests relevant to the changed code.

Run focused tests covering the touched areas:

```text
Admin Web frontend:
- Home layout
- Online Devices presentation
- Traffic Now presentation

Fingerprint/Admin presentation:
- compact_platform
- platform_presentation
- Home fingerprint batch enrichment

Serializer/query tests:
- only exact contracts touched by implementation
```

Do not run broad Central/Full suites unless Project Tech Lead separately requests them.

Coder must report:

```text
exact commands
PASS / FAIL
test counts
skipped tests, if any
```

Any unexpected failure must be reported.

Do not hide it.

---

# 30. CODER IMPLEMENTATION BOUNDARY

Coder implements only this contract.

Coder may choose reasonable internal implementation details where this contract does not freeze them.

Coder does not have design discretion to change:

```text
labels
Traffic thresholds
arrow symbols
Platform precedence
unresolved-state rules
Type semantics
Device Card source separation
visible provenance policy
scope
```

If a frozen requirement cannot be implemented safely within the approved architecture:

```text
CODER BLOCKER
```

Return the blocker before implementing a compromise.

---

# 31. PHASE 1 HANDOFF — STOP BEFORE COMMIT

After implementation and focused tests:

**STOP. DO NOT COMMIT.**

Return:

```text
CODER IMPLEMENTATION HANDOFF

TASK=
HOME-UX-REFINEMENT-01

BASE_COMMIT=
c2635b467dc83e3f574ed204184a2e982f925a9a

BASE_TREE=
bb1d5f7951d77e8a65a6af4856b07d80fc9122f0

CHANGED_FILES=
...

DIFF_STAT=
...

IMPLEMENTATION_SUMMARY=
...

TESTS_RUN=
...

TEST_RESULT=
...

KNOWN_LIMITATIONS=
...

GIT_DIFF_CHECK=
...

UNIFIED_PATCH=
<patch artifact / exact patch>

COMMIT=
NO

PUSH=
NO

PR=
NO

MERGE=
NO

PRODUCTION=
NO
```

Required review artifacts:

```text
git diff
git diff --stat
git diff --check
unified patch
```

No commit is allowed in Phase 1.

---

# 32. REVIEW FLOW

```text
Coder implementation
        ↓
Coder focused tests
        ↓
diff + unified patch
        ↓
Project Tech Lead source review
        ↓
Owner / Web Design Tech Lead visual + UX review
        ↓
correction if required
        ↓
explicit APPROVAL TO COMMIT
```

Only after explicit approval may Coder proceed to commit/PR stage.

---

# 33. COMMIT / PR STAGE

After separate explicit Owner / Tech Lead GO:

Coder may:

```text
commit the exact approved candidate
push approved branch
open PR
```

Return:

```text
commit SHA
tree SHA
PR number
changed files
test result
```

No additional code/design change is allowed between approved diff and commit without another review.

---

# 34. MERGE OWNERSHIP

```text
MERGE = OWNER ONLY
```

Coder:

```text
MUST NOT MERGE
```

PR creation is not merge authorization.

Production deploy is not authorized by this task.

---

# 35. DEFINITION OF DONE — CODER PHASE 1

Phase 1 is complete only when:

```text
implementation complete
focused tests PASS
diff reviewed locally
git diff --check PASS
unified patch produced
scope remains within approved contract
no commit exists
no push exists
no PR exists
Owner / Project Tech Lead have all review artifacts
```

---

# 36. FINAL IMPLEMENTATION RULE

```text
NO UNRELATED REFACTOR
NO "CLEANUP WHILE HERE"
NO DESIGN DEVIATION
NO BACKEND CHANGE OUTSIDE THE APPROVED HOME READ-CONTRACT EXTENSION
NO COMMIT BEFORE REVIEW
NO PR BEFORE REVIEW
NO MERGE
NO PRODUCTION
```
