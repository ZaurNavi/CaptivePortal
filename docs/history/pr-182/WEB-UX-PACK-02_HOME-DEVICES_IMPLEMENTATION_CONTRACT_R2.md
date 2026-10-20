# WEB-DESIGN IMPLEMENTATION CONTRACT

## WEB-UX-PACK-02 — Home + Devices Presentation Refinement

**Status:** FINAL / READY FOR CODER — REVISION 2  
**Owner design decisions:** FROZEN  
**Open product questions:** NONE  
**Repository:** `ZaurNavi/CaptivePortal`  
**Required baseline:** `main@c8d8d620dfed06caee92a498b891bf2faa37a6a9`  
**Required baseline tree:** `be3470c378180aa215d527c6de6b686583ae0d79`

This contract is implementation-authoritative for this package.

**REVISION 2 supersedes the previously generated WEB-UX-PACK-02 contract.**
The R2 change additionally folds the Home `Traffic by AP` card into the same
`Access Points Now` card that already absorbs `Devices by AP — Now`.
Do not implement from the earlier contract.

The Coder MUST NOT make independent product, UX, semantic, taxonomy, fallback,
icon, timezone, data-population, or API-shape decisions.

If repository `main` is not exactly the required baseline when work begins,
STOP and report baseline drift before implementation. Do not silently rebase this
contract onto a later tree.

---

# 1. Required companion artifact

The Owner must provide the Coder with this contract **and**:

```text
CaptivPortal_Device_Type_Icons_v2.zip
SHA256=2baa2f1dd80a431657d3581ad37011acc0ae82b786aa4ba8b68828d8548eccf1
```

The earlier `CaptivPortal_Home_Device_Type_Icon_Pack_v1.zip` is **SUPERSEDED**.
Do not use any v1 assets.

The v2 archive mirrors the target repository path:

```text
app/admin_web/static/icons/device-types/
```

Only the six SVGs in that directory are production assets.
The archive `_preview/` directory is review-only and MUST NOT be copied into
production static assets.

Existing Android Platform asset remains unchanged:

```text
app/admin_web/static/icons/platforms/android.svg
```

Do not move, duplicate, redraw, or replace the Android asset in this task.

---

# 2. Package scope

This package has four user-facing changes:

1. Home → Online Devices:
   convert Fingerprint `Type` from visible text to authoritative icon-only
   presentation.

2. Devices page:
   - rename the current Controller-type presentation from `Type` to `Platform`;
   - add a new Fingerprint `Type` field before Platform;
   - make Devices Platform use the same effective Controller-first presentation
     semantics as Home;
   - add a small Site-scoped Device Inventory summary:
     `Total Devices` and `New Today`.

3. Home:
   consolidate all current per-AP presentation from:
   - `Access Points Now`;
   - `Devices by AP — Now`;
   - `Traffic by AP`;
   into ONE `Access Points Now` card, with one AP identity row and no duplicated
   AP name/MAC/count information. Remove the two standalone per-AP cards
   `Devices by AP — Now` and `Traffic by AP`.

4. Add the supplied local Device Type SVG asset directory and use it on both
   Home and Devices.

Everything else is unchanged unless explicitly named below.

---

# 3. Explicit non-goals

The following are OUT OF SCOPE and MUST NOT be changed:

- Device Detail / Device Card information architecture.
- Device Card's separate `Controller Platform` and `Fingerprint Information`.
- Fingerprint classification logic, rules, evidence, production activation, or
  knowledge bundles.
- Authorization, CAPPORT, guest authorization, session lifecycle, or identity
  semantics.
- Omada collection logic.
- Current State collection logic.
- New database, new table, new materialized counter, new collection, new
  ingestion, new device identity logic, or new classification logic.
- Traffic page semantics.
- Home `Traffic Now` aggregate metrics, evidence, thresholds, arrows, and
  traffic semantics from the previous task. Only the per-AP `Traffic by AP`
  subcard is moved into `Access Points Now` by this revision.
- Home Online Devices ordering/filtering/pagination other than the Type cell
  presentation.
- New iOS/Apple iconography. iOS remains text when it is the effective Platform.
- Third-party runtime icon/CDN dependencies.
- New feature flags for this package.
- New timezone setting.

---

# 4. Existing architecture that MUST be preserved

Browser data boundary remains:

```text
browser
→ same-origin /admin/api/v1
→ AdminQueryService
→ Site-safe read gateways / persisted read services
```

The browser MUST NOT query SQLite, Omada, Fingerprint persistence, Loki, Grafana,
or internal Analytics services directly.

Fingerprint remains advisory and fail-soft.

Current Home terminology is authoritative and is extended to Devices:

```text
Type     = authoritative PRODUCTION Fingerprint device_class
Platform = Controller-first; resolved PRODUCTION Fingerprint fallback only

Type != Platform
Controller Platform NEVER backfills Fingerprint Type
```

---

# 5. Authoritative Device Type machine contract

## 5.1 Resolved enum

The complete resolved `device_class` enum for this presentation is:

```text
smartphone
tablet
laptop
```

No other resolved canonical value may be guessed, normalized, aliased, or mapped
by the frontend.

## 5.2 Completed unresolved states

For:

```text
state = classified

status ∈ {
  unknown,
  insufficient_evidence,
  conflicting_evidence,
  recognized_out_of_scope
}
```

use one common unresolved presentation.

## 5.3 No-result and source-unavailable are distinct

```text
state = no_result
```

and:

```text
state = unavailable
```

are different machine states and MUST have different icons.

`no_result` means **no authoritative Type result is currently available**.
The UI MUST NOT claim that classification is actively running.

`unavailable` means the authoritative Fingerprint read source is unavailable.

## 5.4 Required compact Type projection

Change the shared compact Type projection to the exact shape:

```json
{
  "state": "classified | no_result | unavailable",
  "status": "resolved | unknown | insufficient_evidence | conflicting_evidence | recognized_out_of_scope | null",
  "canonical_value_id": "smartphone | tablet | laptop | null",
  "value": "Smartphone | Tablet | Laptop | Unknown | —"
}
```

Required invariants:

### Resolved

```text
state=classified
status=resolved
canonical_value_id ∈ {smartphone, tablet, laptop}
value is the canonical presentation label
```

### Completed unresolved

```text
state=classified
status ∈ {
  unknown,
  insufficient_evidence,
  conflicting_evidence,
  recognized_out_of_scope
}
canonical_value_id=null
value=Unknown
```

### No result

```text
state=no_result
status=null
canonical_value_id=null
value=—
```

### Unavailable

```text
state=unavailable
status=null
canonical_value_id=null
value=—
```

A resolved `device_class` with a canonical ID outside the authoritative enum is
not a new UI type. It is invalid presentation input. It MUST follow the existing
Fingerprint fail-soft boundary and be exposed to the consuming page as
`state=unavailable`, not as a generic/guessed icon.

The browser MUST NOT derive icon selection from `value`.

---

# 6. Final Device Type icon asset contract

Create/use:

```text
app/admin_web/static/icons/device-types/
```

Exact production files and SHA256:

```text
type-smartphone.svg
40fc00b7aa66ec1d548956798379cf84fb99312ff0ec4c27bb25fab275480000

type-tablet.svg
6ebc93d6779dfc10271e8182c858d4969c37c84b2c7c8146bce57ee88df6abb6

type-laptop.svg
77531c51c7e76ebe29e7e034bb230ab9490c66145ec972c4748543d4917206fb

type-unresolved.svg
b81ad849966c7aefe19c74ee6f616b0b24f7b2e5d28bef70087b9135cfd05d82

type-no-result.svg
47c7bd944686d7f70cf8d8332fbcfd7e08398e95890e92c755a6bd9d35f14b6f

type-unavailable.svg
18e76d5e11bb354d85fa72e2906ddce9223aa6872587c9040230fd34a9fc28b7
```

Exact mapping:

```text
classified + resolved + smartphone
→ type-smartphone.svg

classified + resolved + tablet
→ type-tablet.svg

classified + resolved + laptop
→ type-laptop.svg

classified + {
  unknown,
  insufficient_evidence,
  conflicting_evidence,
  recognized_out_of_scope
}
→ type-unresolved.svg

no_result
→ type-no-result.svg

unavailable
→ type-unavailable.svg
```

There is NO generic fallback icon.

Malformed/unrecognized machine projection must follow the page's controlled
invalid/unavailable path; it must not be silently converted to another icon.

---

# 7. Type icon visual/accessibility contract

On both Home → Online Devices and Devices list:

```text
CSS display width  = 22px
CSS display height = 22px
```

This is exact. The SVG's intrinsic `96×96` preview/viewBox size is not the UI
size.

Requirements:

- icon-only value presentation;
- no visible `Smartphone`, `Tablet`, `Laptop`, `Unknown`, `—`, or state text in
  the Type value area;
- existing `Type` header/field label remains visible;
- icon must be vertically and horizontally centered in its value area;
- icon MUST NOT increase the normal row height;
- no large background/card treatment around the icon;
- all six states use the same 22×22 display box.

Exact accessible labels:

```text
smartphone  → Smartphone
tablet      → Tablet
laptop      → Laptop
unresolved  → Device type unresolved
no_result   → No device type result
unavailable → Device type source unavailable
```

Required DOM accessibility pattern:

- semantic wrapper owns exact `aria-label`;
- wrapper owns matching `title`;
- nested `<img>` is decorative:
  - `alt=""`
  - `aria-hidden="true"`
- width/height is controlled by the common Type icon CSS class.

Do not expose the machine key as visible UI text.

---

# 8. Frontend Type mapping is machine-only

Icon selection MUST use only:

```text
state + status + canonical_value_id
```

Forbidden in browser code:

- comparing `value` to `"Smartphone"` / `"Unknown"` / etc.;
- `.trim()` for Type decisions;
- `.toLowerCase()` / `.toUpperCase()` for Type decisions;
- `casefold`-equivalent inference;
- substring/regex classification;
- mapping from Controller `device_type`;
- mapping from hostname, MAC, vendor, platform, user agent, or any other field.

The browser is a presentation consumer, not a classifier.

---

# 9. Home → Online Devices changes

## 9.1 Type

Keep the existing Home column order:

```text
Device / MAC
Type
Platform
Auth
IP
AP
Band
RSSI
SNR
Uptime
Traffic
```

Only the Type cell presentation changes from visible text to the exact icon-only
contract in Sections 5–8.

The Home API item must provide the expanded compact Type projection from
Section 5.

## 9.2 Platform

Do NOT redesign or alter the accepted Platform semantics from
`HOME-UX-REFINEMENT-01`.

Effective Platform remains:

1. usable Controller Platform wins;
2. if Controller is unresolved, a resolved authoritative PRODUCTION Fingerprint
   Platform may be the fallback;
3. otherwise present honest `Unknown` or `—`.

Current server-composed Platform shape remains:

```json
{
  "source": "controller | fingerprint | none",
  "value": "presentation value",
  "key": "canonical effective key or null"
}
```

Android icon decision remains exact:

```text
platform_presentation.key == "android"
```

No browser normalization.

---

# 10. Shared effective Platform helper

Because the same effective Platform semantics are now required by Home and
Devices, the current helper name `home_platform_presentation` becomes
surface-specific and MUST be generalized.

Rename it to:

```text
effective_platform_presentation
```

and update all internal imports/references/tests.

This is a name/generalization only. Its accepted semantics MUST NOT change.

Exact precedence remains:

```text
IF controller_key != null AND controller_key != "unknown":
    source=controller
    value=controller_value
    key=controller_key

ELSE IF fingerprint platform:
    state=classified
    status=resolved
    canonical_value_id != null:
        source=fingerprint
        value=fingerprint value
        key=canonical_value_id

ELSE:
    source=none
    key=null

    IF controller_key == "unknown"
       OR fingerprint platform state == classified:
        value=Unknown
    ELSE:
        value=—
```

No visible source/provenance badge is added.

---

# 11. Devices page — Type / Platform redesign

## 11.1 Current field correction

The existing Devices row field currently labeled:

```text
Type
```

and driven by Controller `device_type` / `device_type_key` is conceptually
Platform.

Rename that visible field label to:

```text
Platform
```

Do not remove the raw/controller evidence from the API.

## 11.2 New Type field

Insert a new visible field immediately BEFORE Platform:

```text
Type
```

Its value uses the exact same Fingerprint Type icon contract as Home.

Target conceptual order:

```text
Status
Device identity
Type
Platform
Last seen
Network
Visits / Snapshots
Chevron
```

## 11.3 Exact desktop grid

Use this desktop grid:

```css
grid-template-columns:
  104px
  minmax(220px, 1.1fr)
  72px
  minmax(105px, .5fr)
  minmax(180px, .9fr)
  minmax(145px, .62fr)
  minmax(140px, .72fr)
  auto;
```

Column ownership:

```text
1 Status
2 Main identity
3 Type
4 Platform
5 Activity / Last seen
6 Network
7 Stats
8 Chevron
```

The 72px Type column contains the centered 22×22 icon.

## 11.4 Mobile layout

Preserve the existing compact three-column mobile row shell.

On mobile:

- Status remains first-column status.
- Device identity remains the primary row content.
- Chevron remains at the current right position.
- Network remains hidden exactly as today.
- Full-width detail lane is `grid-column: 2 / 4`.
- Detail order within that lane is exactly:

```text
Type
Platform
Last seen / Activity
Visits / Snapshots
```

Type remains icon-only.
Platform remains its normal visible value presentation.

No horizontal overflow may be introduced.

---

# 12. Devices page — required per-item server projections

The Devices list endpoint must enrich every returned item with:

```text
fingerprint_type
fingerprint_platform
platform_presentation
```

These are additional fields. Existing fields remain.

## 12.1 Fingerprint read behavior

For every returned Devices page:

- collect returned canonical MACs;
- perform exactly ONE bounded
  `DeviceFingerprintPresentationService.get_many(site_id, macs)` call;
- never perform per-row Fingerprint reads;
- enrich only the rows in the returned page;
- remain Site-scoped;
- retain current Fingerprint fail-soft behavior.

This enrichment is required for BOTH:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=true
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
```

The browser contract MUST NOT change depending on that feature flag.

## 12.2 Devices `fingerprint_type`

Exact shape = Section 5 compact Type projection.

## 12.3 Devices `fingerprint_platform`

Use the current compact Fingerprint Platform projection.

## 12.4 Devices `platform_presentation`

Compose with `effective_platform_presentation()` using the row's existing:

```text
device_type
device_type_key
```

plus its Fingerprint Platform projection.

The Devices effective Platform precedence must be byte-for-byte semantically
equivalent to Home.

---

# 13. Devices page — Platform visual contract

The Devices Platform field keeps the existing Devices-row visual style.

### Effective Android

If:

```text
platform_presentation.key == "android"
```

render:

- existing repository Android icon:
  `app/admin_web/static/icons/platforms/android.svg`;
- visible `platform_presentation.value` text next to it;
- no browser string inference.

### Other resolved Platform

For iOS, macOS, Windows, ChromeOS, or any other effective non-Android value:

- render the exact server-provided `platform_presentation.value` as visible text;
- do not create or use a new platform icon in this package.

The Owner explicitly canceled the proposed custom iOS icon.

### Unresolved / missing

Render exact server value:

```text
Unknown
```

or:

```text
—
```

as applicable.

Never substitute Type iconography into Platform.

---

# 14. Devices page — Device Inventory summary card

## 14.1 Placement

Add one compact card to the Devices page:

```text
after the Exact MAC search controls
before the existing page state / device list
```

Do this locally in `devices.html`; do not redesign `base.html`.

Exact title:

```text
Device Inventory
```

Exact metric labels:

```text
Total Devices
New Today
```

Initial metric values:

```text
—
```

## 14.2 Layout

Desktop:

```text
┌──────────────────────────────────┐
│ Device Inventory                 │
│ Total Devices       New Today    │
│ 1,248               17           │
└──────────────────────────────────┘
```

Use the existing Admin card language; keep the card visually small/compact.

The two metric cells are equal-width side by side.

Narrow/mobile:
- stack metrics one per row;
- no horizontal scrolling;
- no oversized number treatment that dominates the page.

## 14.3 Loading / failure

The card is independent from the list.

On initial page load:
- show `—` / `—`;
- request the inventory summary.

On success:
- replace with integer values.

On summary request failure:
- keep both metric values as `—`;
- show small text exactly:

```text
Unavailable
```

inside the card;
- do NOT fail, hide, or clear the device list;
- do NOT raise the page-global error state solely because the inventory summary
  failed.

The existing top-level manual `Refresh` button refreshes both:
- the Devices list root load;
- the inventory summary.

The following MUST NOT refetch or alter the inventory summary:

- Exact MAC Search;
- Clear Search;
- Load More / pagination.

There is no automatic polling.

## 14.4 Search independence

The summary always describes the selected Site's complete Site-safe device
population.

An Exact MAC filter MUST NOT affect either counter.

---

# 15. Device Inventory backend read contract

Tech Lead dependency is resolved:

```text
DATA EXISTS = YES

READY UI COUNTER / API = NO

BACKEND WORK NEEDED =
small Site-safe read projection:
- total_devices
- new_devices_today

NO NEW DB
NO NEW TABLE
NO NEW COLLECTION
NO NEW DEVICE LOGIC
```

Implement only that bounded read projection.

---

# 16. Device Inventory API contract

Add exact endpoint:

```text
GET /admin/api/v1/sites/<site_id>/devices/inventory-summary
```

Allowed query parameters:

```text
none
```

If any query parameter is present:
- use the existing controlled `400 invalid_request` path.

Required capability:

```text
admin.read.devices
```

Do not introduce a new capability.

Required `AdminQueryService` method name:

```text
device_inventory_summary
```

Required gateway value type:

```python
@dataclass(frozen=True, slots=True)
class AdminDeviceInventorySummary:
    total_devices: int
    new_devices_today: int
```

Required gateway method:

```text
device_inventory_summary(
    *,
    site_id,
    today_start_utc,
    evaluated_at_utc,
    deadline
)
```

Use the existing Admin concurrency/deadline gate.

Do not collide with the existing historical Analytics method
`device_summary(...)`.

---

# 17. Device Inventory public result shape

Keep the normal outer Admin API envelope unchanged.

The endpoint's `result` object is EXACTLY:

```json
{
  "total_devices": 0,
  "new_devices_today": 0,
  "timezone": "IANA/Timezone",
  "evaluated_at_utc": "YYYY-MM-DDTHH:MM:SS.mmmZ"
}
```

Validation:

```text
total_devices is int >= 0
new_devices_today is int >= 0
new_devices_today <= total_devices
timezone is the authoritative validated existing IANA timezone
evaluated_at_utc is canonical UTC
```

No additional result fields.

---

# 18. Device Inventory population semantics

`total_devices` is NOT a count of all global rows in `visitor_devices`.

It MUST use exactly the same Site-scoped population semantics as the existing
Devices list:

```text
Site device_snapshots
UNION
Site visits with device_id
GROUPED by device_id
```

In other words, count distinct device identities that have evidence for the
selected Site according to the existing Device list population.

A globally-known registry device with no evidence for this Site MUST NOT be
counted.

`new_devices_today` is the subset of that SAME Site population whose derived:

```text
site_first_seen_at
```

falls in:

```text
today_start_utc <= site_first_seen_at <= evaluated_at_utc
```

Do not introduce another "registration time" definition.

Prefer extracting/reusing the existing Device population CTE so the list and
inventory summary cannot drift into two different identity/population rules.

Identity-conflict/integrity handling remains strict. If the population cannot be
trusted, use the existing controlled integrity/unavailable path; never return
fabricated counts.

---

# 19. Device Inventory calendar / timezone contract

"Today" is server-authoritative.

Use the existing validated Visitor Registry timezone source:

```text
PORTAL_COUNTER_TIMEZONE
```

Use the existing registry timezone configuration/validation path.

Do NOT use:

- browser timezone;
- browser clock;
- host-local implicit timezone;
- a new environment variable;
- optional Home Activity configuration as a dependency.

Query Service computes one:

```text
evaluated_at_utc = server UTC now
```

Then, using the existing authoritative IANA timezone:

1. convert `evaluated_at_utc` to that timezone;
2. resolve that local calendar date's midnight;
3. convert midnight back to UTC;
4. pass `today_start_utc` and the SAME `evaluated_at_utc` to the gateway.

This must be IANA/DST-safe.

No fixed UTC offset arithmetic.

The endpoint returns the timezone name used so the read is auditable.

---

# 20. Home — consolidate all current per-AP data into Access Points Now

The Owner's final requirement is ONE current-AP card on Home.

Three current presentations exist at the baseline:

```text
Access Points Now
Devices by AP — Now
Traffic by AP
```

After this task, their unique information is consolidated into:

```text
Access Points Now
```

There must be no duplicate AP identity or duplicate current client count.

## 20.1 Remove both standalone per-AP cards

Delete the standalone Home section titled:

```text
Devices by AP — Now
```

Delete the standalone Home section titled:

```text
Traffic by AP
```

The following user-facing regions/controls no longer exist:

```text
live-devices-by-ap
traffic-ap-title
traffic-ap-state
traffic-ap-rows
traffic-ap-more
```

Do not leave hidden duplicate render regions.

The top-level `Traffic Now` section remains. Its aggregate:
- Download Now;
- Upload Now;
- Total Traffic Now;
- Traffic evidence / coverage;
- existing state/freshness behavior

remain unchanged.

Only its separate per-AP `Traffic by AP` card is removed.

## 20.2 Access Points Now is the single AP identity owner

The existing `Access Points Now` card remains the identity/roster owner.

It retains:

- title `Access Points Now`;
- `live-ap-count`;
- `live-ap-state`;
- AP pagination / `Load more access points`;
- current AP name;
- canonical AP MAC;
- AP product/status badge (`product_status_classification`);
- all other currently rendered AP facts that are not duplicates of the merged
  Devices/Traffic information;
- existing AP freshness/warning behavior.

An AP name and AP MAC are rendered ONCE per AP row.

`Devices by AP` and traffic data MUST NOT create a second AP identity row.

All enrichment joins use exact canonical:

```text
ap_mac
```

Never join by AP display name.

A traffic record whose `ap_mac` has not yet appeared in the loaded Access Points
roster is retained only in the internal traffic map. It becomes visible if/when
that AP is loaded through the normal Access Points pagination. It does not create
a traffic-only duplicate AP row.

## 20.3 Exact unified AP row information

Each visible AP row contains these logical regions, in this order:

```text
AP identity / AP status
AP MAC
Devices
Traffic
Traffic evidence detail
```

Conceptual example:

```text
AP-01                                      [online]
AA:BB:CC:DD:EE:FF

Devices · 18
████████████████████

Traffic                                    [valid]
Download 12.30 Mbps · Upload 2.10 Mbps · Total 14.40 Mbps
Source Wired · observed 2026-10-06T...
```

This example is structural, not fake production data.

Rules:

- AP name appears once.
- AP MAC appears once.
- AP status badge and Traffic rate-status badge are different facts and may both
  be shown.
- current client count appears once.
- do NOT retain the old `Current scoped clients: N` text in addition to the new
  Devices bar; the bar/count replaces it.
- do NOT repeat traffic item `name` or `ap_mac`, because Access Points Now already
  owns identity.
- no additional AP title is nested inside the Traffic subregion.

## 20.4 Traffic subregion preserves the current unique Traffic by AP facts

For a matched current traffic item, preserve these current facts exactly:

```text
rate_status
download_mbps
upload_mbps
total_mbps
selected_source
observed_at
```

Visible presentation:

```text
Traffic [rate_status badge]
Download <formatted Mbps> · Upload <formatted Mbps> · Total <formatted Mbps>
Source <LAN|Wired> · observed <observed_at|—>
```

Use the existing Mbps formatter and current source labeling:

```text
selected_source == "lan" → LAN
otherwise current supported source → Wired
```

Do not introduce traffic color thresholds into the per-AP rows.
The numeric traffic-tone thresholds from the aggregate `Traffic Now` metrics
remain scoped to the aggregate metrics.

`0 Mbps` is a valid value and MUST render as zero, not as unavailable.

## 20.5 Traffic feature-gate / unavailable behavior

If Home current traffic is feature-disabled:

- do not issue per-AP traffic requests;
- omit the Traffic subregion from Access Points rows;
- Access Points Now and Devices bars continue normally.

If Home current traffic is enabled but the current Traffic snapshot/read is
unavailable:

```text
Traffic · —
```

is shown as a neutral unavailable Traffic value for each visible AP row.

Do not fabricate:

```text
0 Mbps
```

for unavailable traffic.

Do not delete or fail the AP row merely because Traffic is unavailable.

The existing top-level `Traffic Now` state/evidence remains the page-level source
of Traffic availability/freshness messaging. Do NOT add a second card-level
Traffic warning banner inside Access Points Now.

---

# 21. AP client-count / Devices bar semantics

Use the existing current client summary:

```text
result.devices_by_ap[]
```

with:

```text
ap_mac
client_count
```

No new endpoint, DB query, collector, or metric is permitted for the Devices bar.

## 21.1 Scale

Preserve the current relative scale exactly:

```text
max_count = max(1, every client_count in the full devices_by_ap summary)

fill_percent = min(100, client_count / max_count * 100)
```

Important:

- scale is based on the complete available `devices_by_ap` summary;
- it is NOT recomputed from only currently visible/paginated AP rows.

## 21.2 AP with zero clients

If the client summary is available and a known AP row has no matching
`devices_by_ap` bucket:

```text
Devices · 0
fill = 0%
```

This is a real zero.

## 21.3 Client summary unavailable

If current client summary is unavailable:

```text
Devices · —
```

and render the track in a neutral empty state.

Do NOT convert unavailable to zero.

The Access Points card itself remains usable if the AP page is available.

## 21.4 Unknown AP clients

The existing unknown AP population signal must remain visible inside the merged
Access Points Now card:

```text
AP Unknown · N
```

when:

```text
counts.ap_unknown > 0
```

Place it once as a footer below the AP rows/current visible row group and above
the sole Access Points pagination control.

Unknown AP clients cannot be attached to a known AP row.

---

# 22. Traffic-by-AP data ownership, pagination, and render lifecycle

## 22.1 Existing traffic source remains authoritative

Use the existing current per-AP Traffic API/read path.

No new Traffic database, query model, collector, calculation, or per-device
traffic logic is created.

The merged UI consumes the same current Traffic item fields that the baseline
`Traffic by AP` card consumes.

## 22.2 No user-facing Traffic pagination

Remove the user-facing:

```text
Load more traffic rows
```

control.

`Load more access points` becomes the ONLY visible pagination control for the
unified current AP card.

Do not couple Access Points cursor semantics to the Traffic cursor.

## 22.3 Internal Traffic pagination

When Home current Traffic is enabled and a usable current Traffic cycle/snapshot
is available:

- follow the existing current per-AP Traffic cursor chain sequentially to
  exhaustion for that accepted root refresh;
- build one in-memory map:

```text
ap_mac → current traffic item
```

- do not issue one Traffic request per AP;
- do not create a new browser-side traffic classifier;
- do not alter backend page-size or cursor contracts merely for this UI merge.

If a newer root refresh supersedes the in-progress traffic cursor chain, abort or
discard the superseded chain using the existing Home request-generation rules.
Old traffic rows MUST NOT overwrite a newer accepted refresh.

## 22.4 One render owner

After this package there is no independent:

```text
Devices by AP renderer
Traffic by AP renderer
```

The `Access Points Now` renderer is the single presentation owner of:

- AP identity/status rows;
- per-AP Devices bar/count;
- per-AP current Traffic subregion;
- `AP Unknown · N` footer;
- sole AP pagination control.

It retains the latest accepted:

```text
current AP page/list state
current client summary state
current per-AP Traffic map/state
```

and composes those states by `ap_mac`.

## 22.5 Idempotent updates

Whenever any accepted source changes:

```text
current AP page/list
current client summary
current per-AP Traffic map/state
```

update the existing AP row enrichment idempotently.

Requirements:

- no duplicate AP row;
- no duplicate AP name;
- no duplicate AP MAC;
- no duplicate Devices bar;
- no duplicate Devices count;
- no duplicate Traffic subregion;
- no duplicate Traffic rate-status badge;
- no duplicate unknown footer;
- no stale client count after newer client summary;
- no stale Traffic values after newer accepted Traffic refresh;
- Load More AP rows immediately receive the latest accepted Devices bar state and
  Traffic map state;
- client-summary failure changes Devices to `—` without deleting AP rows;
- Traffic failure changes Traffic to `—` without deleting AP rows;
- later successful client/Traffic reads restore their respective enrichment.

Keep the existing Home global/current warning and freshness systems.
Do not invent a fourth AP/Traffic warning surface.

---

# 23. Expected source files

The Coder should expect to touch the smallest correct subset of these files:

```text
app/admin_web/device_fingerprint_presentation.py
app/admin_web/query_service.py
app/admin_web/device_gateway.py
app/admin_web/routes.py

app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/devices.html

app/admin_web/static/admin.js
app/admin_web/static/admin.css

app/admin_web/static/icons/device-types/type-smartphone.svg
app/admin_web/static/icons/device-types/type-tablet.svg
app/admin_web/static/icons/device-types/type-laptop.svg
app/admin_web/static/icons/device-types/type-unresolved.svg
app/admin_web/static/icons/device-types/type-no-result.svg
app/admin_web/static/icons/device-types/type-unavailable.svg
```

Tests and current docs must be updated as required.

Likely focused test surfaces include:

```text
tests/admin_web/test_device_fingerprint_presentation.py
tests/admin_web/test_query_service.py
tests/admin_web/test_device_gateway.py
tests/admin_web/test_device_list_context_serialization.py   # only if public serializer shape changes there
tests/admin_web/test_admin_ui_frontend.py
route/API tests covering Admin Web devices endpoints
```

Update current documentation that states Home/Devices presentation or endpoint
contracts, including at minimum:

```text
docs/modules/admin-web.md
```

Do not mechanically edit unrelated historical task records.

---

# 24. Required backend tests

## 24.1 Fingerprint compact Type

Test exact compact projection for:

```text
smartphone
tablet
laptop
```

Test every completed unresolved status:

```text
unknown
insufficient_evidence
conflicting_evidence
recognized_out_of_scope
```

Assertions:
- status retained;
- `canonical_value_id is null`;
- value is `Unknown`.

Test separately:

```text
no_result
unavailable
```

and prove their machine states remain distinct.

Test an unsupported resolved canonical device class:
- no guessed mapping;
- fail-soft consumer result becomes `unavailable`.

## 24.2 Devices page Fingerprint enrichment

For both Device List Context feature states:

```text
enabled
disabled
```

prove:
- exactly one bounded Fingerprint batch for a returned page;
- no per-row Fingerprint read;
- each item receives:
  - `fingerprint_type`
  - `fingerprint_platform`
  - `platform_presentation`;
- Site and canonical-MAC scope preserved;
- pagination contract preserved;
- exact MAC filter preserved;
- current presence/order behavior preserved.

## 24.3 Platform precedence matrix

Test Devices and Home against the SAME expected matrix:

1. usable Controller wins over resolved Fingerprint;
2. Controller null + resolved Fingerprint → Fingerprint;
3. Controller `unknown` + resolved Fingerprint → Fingerprint;
4. Controller `unknown` + classified unresolved Fingerprint → `Unknown`;
5. Controller null + classified unresolved Fingerprint → `Unknown`;
6. Controller null + no_result → `—`;
7. Controller null + unavailable → `—`.

Prove Type never falls back to Controller.

---

# 25. Required Device Inventory tests

Backend/gateway/API tests must prove:

1. empty Site:
   ```text
   total_devices=0
   new_devices_today=0
   ```

2. non-empty Site counts.

3. Site isolation:
   evidence belonging only to another Site is not counted.

4. population parity with Devices list:
   - snapshot-only device;
   - visit-only device with `device_id`;
   - device represented in both counts once.

5. exact `site_first_seen_at` semantics:
   earliest Site evidence drives New Today.

6. local calendar boundary:
   item immediately before local midnight is not New Today;
   item at/after local midnight is New Today.

7. IANA/DST-safe conversion with a DST-observing test timezone.

8. invariant:
   ```text
   0 <= new_devices_today <= total_devices
   ```

9. endpoint rejects any query parameter with controlled 400.

10. endpoint requires `admin.read.devices`.

11. endpoint uses existing Admin execution deadline/concurrency controls.

12. source/integrity failure does not return fabricated values.

13. Exact MAC list search does not influence inventory counts.

---

# 26. Required frontend tests — Home Type

Prove all six final Type presentation outcomes:

```text
smartphone
tablet
laptop
unresolved
no_result
unavailable
```

For each:
- correct SVG path;
- exact accessible title/aria label;
- no visible Type value text;
- icon class enforces 22×22;
- malformed machine projection is not guessed.

Also prove Home Platform behavior remains unchanged from the accepted
`HOME-UX-REFINEMENT-01`.

---

# 27. Required frontend tests — Devices Type / Platform

Prove:

- previous visible field label `Type` is now `Platform`;
- new `Type` exists immediately before Platform;
- Type is icon-only;
- Type uses exact six-state mapping;
- Type icons are 22×22;
- Android effective Platform uses existing Android asset AND visible server value;
- iOS/non-Android Platform is text only;
- no new iOS icon is referenced;
- Platform consumes `platform_presentation`;
- no frontend raw-string inference;
- existing status, identity, last-seen, network, visits/snapshots, chevron remain;
- responsive mobile Type → Platform → Activity → Stats order;
- no horizontal overflow from new Type column.

---

# 28. Required frontend tests — Device Inventory card

Prove:

- card title is `Device Inventory`;
- labels are exactly `Total Devices` and `New Today`;
- initial values are `—`;
- success renders integer values;
- summary failure shows exact `Unavailable` and does not fail/remove list;
- Search/Clear/Load More do not refetch summary;
- top-level manual Refresh does refetch summary;
- mobile stacking works without overflow.

---

# 29. Required frontend tests — unified Access Points Now

Prove:

- no standalone `Devices by AP — Now` section remains;
- no standalone `Traffic by AP` section remains;
- obsolete presentation hooks are gone:
  - `live-devices-by-ap`;
  - `traffic-ap-title`;
  - `traffic-ap-state`;
  - `traffic-ap-rows`;
  - `traffic-ap-more`;
- `Traffic Now` aggregate metrics/evidence remain;
- `Access Points Now` remains and is the sole current per-AP card;
- each AP identity/name/MAC is rendered once;
- each AP row can receive one and only one Devices bar;
- old `Current scoped clients: N` is not duplicated beside the Devices bar;
- Devices join is exact by `ap_mac`;
- full-summary Devices max scaling is preserved;
- matching bucket renders exact count;
- available client summary + missing AP bucket renders `Devices · 0`;
- unavailable client summary renders `Devices · —`, not zero;
- `AP Unknown · N` footer is preserved exactly once;
- each AP row can receive one and only one Traffic subregion;
- Traffic join is exact by `ap_mac`;
- matched Traffic preserves:
  - `rate_status`;
  - Download;
  - Upload;
  - Total;
  - Source;
  - observed timestamp;
- Traffic does not repeat AP name or AP MAC;
- valid `0 Mbps` remains zero;
- unavailable Traffic renders `Traffic · —`, not fake zero;
- Home Traffic feature-disabled state emits no per-AP traffic request and omits
  Traffic subregions;
- user-facing `Load more traffic rows` no longer exists;
- `Load more access points` remains functional and is the sole AP-card pagination;
- existing Traffic cursor chain can be consumed internally to exhaustion without
  creating per-AP requests;
- a traffic record for an AP not yet loaded does not create a duplicate
  traffic-only AP row;
- newly loaded AP rows use current accepted Devices and Traffic enrichment;
- later client-summary updates change existing bars without duplicates;
- later Traffic updates change existing Traffic subregions without duplicates;
- client-summary failure does not delete AP rows;
- Traffic failure does not delete AP rows.

---

# 30. Static / syntax verification

At minimum:

- Python compile/import checks for changed Python modules;
- JavaScript syntax/available frontend test harness;
- template rendering tests for changed templates;
- CSS/DOM selectors used by tests must match production markup;
- supplied SVG files byte/hash verification against Section 6.

No external network runtime dependency may be introduced.

---

# 31. UX acceptance checklist

Implementation is not ready for Owner/Web Design acceptance until all of the
following are true:

### Home Online Devices

- Type values are icons only.
- Icons are visibly compact and aligned to row height.
- No icon looks like the 96px preview.
- Platform behavior is unchanged.
- Online Devices table did not widen unnecessarily.

### Devices

- `Type` visually means Fingerprint device class.
- `Platform` visually means effective Platform.
- Type appears before Platform.
- Android Platform still looks familiar.
- iOS remains ordinary text.
- Device rows remain readable desktop and mobile.
- Device Inventory card is small, not a dominant dashboard section.

### Access Points Now

- Only one current per-AP card remains.
- AP name/MAC are not duplicated.
- AP rows show their own Devices count/bar.
- AP rows show their current Traffic rate/status/source/observed facts when
  Traffic is enabled and available.
- Existing AP status/facts remain readable.
- Unknown AP population signal is not lost.
- No standalone Devices by AP card remains.
- No standalone Traffic by AP card remains.
- No separate user-facing Traffic pagination remains.

---

# 32. Documentation contract

Update current-state documentation so future agents/coders see the new truth:

```text
Home Type = icon-only Fingerprint device_class presentation
Devices Type = same Fingerprint device_class presentation
Devices Platform = effective Controller-first Platform presentation
Device Card remains separate Controller/Fingerprint sources
Devices inventory summary = Site-safe existing population read
Devices by AP standalone card = removed; Devices bars live in Access Points Now
Traffic by AP standalone card = removed; Traffic facts live in Access Points Now
Access Points Now = single current per-AP identity/presentation owner
```

Document the new endpoint:

```text
GET /admin/api/v1/sites/<site_id>/devices/inventory-summary
capability=admin.read.devices
query parameters=none
```

Document local Type assets and authoritative mapping.

Do not claim production deployment before Owner actually deploys and verifies it.

---

# 33. Forbidden implementation shortcuts

The following are automatic HOLD conditions:

- frontend maps icon from `fingerprint_type.value`;
- frontend maps icon from Controller type;
- frontend lowercases/trims/normalizes Type to guess an icon;
- generic fallback Type icon;
- one Fingerprint query per device row;
- Platform semantics differ between Home and Devices;
- new iOS icon;
- Apple logo or Apple-owned icon asset;
- Type icon larger than 22×22 in normal UI;
- Device Card semantics changed;
- Devices counters use global Registry population instead of Site list population;
- `New Today` uses browser timezone;
- `New Today` uses a new registration definition instead of `site_first_seen_at`;
- new DB/table/collector/cache/materialized counter;
- MAC search changes summary counters;
- AP bars joined by AP name;
- unavailable AP client summary shown as zero;
- AP bar scale based only on visible paginated APs;
- standalone Devices-by-AP card remains;
- standalone Traffic-by-AP card remains;
- user-facing `Load more traffic rows` remains;
- merged Traffic repeats AP name or AP MAC already owned by Access Points Now;
- Traffic is joined to AP by display name instead of canonical `ap_mac`;
- one per-AP Traffic request is introduced;
- unavailable Traffic is rendered as `0 Mbps`;
- merge/deploy performed without separate Owner authorization.

---

# 34. Coder handoff requirements

Coder must return one implementation handoff containing:

```text
BASE_COMMIT
BASE_TREE
HEAD_COMMIT / candidate commit if committed
HEAD_TREE
changed-file list
insertions/deletions
focused test commands
focused test results
syntax/static check results
asset SHA256 verification
```

Also provide materialized visual evidence/screenshots for:

1. Home Online Devices with at least:
   - one resolved Type icon;
   - one unresolved/no-result state where available;
   - existing Platform.

2. Devices desktop:
   - Device Inventory card;
   - Type;
   - Platform;
   - normal row information.

3. Devices narrow/mobile layout.

4. Home Access Points Now:
   - merged per-AP Devices bars;
   - merged per-AP Traffic facts;
   - AP name/MAC shown once per AP;
   - no standalone Devices by AP card;
   - no standalone Traffic by AP card;
   - no user-facing Traffic pagination.

If test data cannot naturally exhibit every runtime state, state that honestly;
do not fabricate production data. Unit/DOM tests must still cover every mapping.

The Coder must NOT:
- merge;
- deploy;
- alter production flags;
- activate anything in production.

Owner authorization is required after Web Design implementation review.

---

# 35. Acceptance authority

After the Coder returns the implementation handoff:

1. Web Design Tech Lead reviews implementation against this contract.
2. Web Design Tech Lead reviews the materialized UI evidence.
3. Result is:
   ```text
   WEB DESIGN IMPLEMENTATION REVIEW = PASS
   ```
   or:
   ```text
   WEB DESIGN IMPLEMENTATION REVIEW = HOLD
   ```
4. Only after PASS may the candidate be handed back to Owner for merge/deploy
   authorization.

---

# 36. Final frozen summary

```text
HOME / ONLINE DEVICES
Type     = Fingerprint device_class icon-only
Platform = accepted effective Controller-first Platform

DEVICES
Type     = same Fingerprint device_class icon-only
Platform = renamed old Type field + same effective Platform semantics
Summary  = Site-safe Total Devices + New Today

HOME / ACCESS POINTS
Access Points Now              = ONLY current per-AP card
Devices by AP standalone card = REMOVED
Traffic by AP standalone card = REMOVED
Devices count/bar             = MERGED into each AP row
Traffic facts                 = MERGED into each AP row
AP name/MAC                   = rendered ONCE
Visible AP pagination         = Load more access points ONLY

TYPE ASSETS
local only
22×22 display
six final SVGs
machine mapping only
no frontend inference
```

**Implementation contract complete. No product decisions are intentionally left
to the Coder.**
