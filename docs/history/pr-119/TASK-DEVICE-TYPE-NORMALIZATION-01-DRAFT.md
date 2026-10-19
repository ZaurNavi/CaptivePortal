# TASK-DEVICE-TYPE-NORMALIZATION-01-DRAFT

## Canonical Device Type Foundation

**Project:** CaptivPortal  
**Task:** `TASK-DEVICE-TYPE-NORMALIZATION-01`  
**Priority:** Backend / Foundation  
**Status:** `DRAFT — FOR TECH LEAD REVIEW`  
**Architecture stage:** DRAFT  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**GitHub write / branch / commit / push / PR:** `NOT AUTHORIZED`  
**Production:** `UNTOUCHED`  
**Prepared:** 2026-09-12

---

# 0. ARCHITECT RECOMMENDATION

```text
ARCHITECT RECOMMENDATION:

A) read-time additive canonicalization = RECOMMENDED

B) storage-level canonicalization = REJECTED FOR V1

C) hybrid = REJECTED FOR V1
```

The existing `device_type` field is already established source/persisted evidence across Current State, Observations, Visitor Registry, Admin Device reads and Analytics. V1 must not redefine it.

The foundation keeps:

```text
device_type
=
existing source/sanitized value
```

and adds:

```text
device_type_key
=
pure deterministic lexical canonicalization
of that exact source value
```

The key is derived at read/public-contract boundaries. That means historical rows gain the same canonical interpretation immediately, without DB migration, backfill, destructive rewrite, or coexistence of old raw/new canonical storage.

The canonical key is derived data, not authoritative evidence.

---

# 1. Goal

Create one backend-owned Device Type lexical-normalization contract for CaptivPortal so that all approved read surfaces and future UI consumers use one machine key rather than local dictionaries or guesses.

The foundation must provide consistent semantics to:

```text
Admin Home Current Clients
Devices list
Device Detail
Device Current Context
Visitor Registry derived reads
Observations reads
Analytics snapshot/evidence reads
future backend/read consumers
```

while preserving all existing raw source semantics.

---

# 2. Problem Statement

Today the same source fact appears on multiple persistence/read surfaces but upstream normalization differs:

```text
Current State:
source string preserved after bounded validation

Observations:
accepted string is stripped

Visitor Snapshot / Registry:
strict source string retained

Admin / Analytics:
read persisted source text

Frontend:
local trim+lowercase Android interpretation
```

That creates a risk that every UI/read surface invents its own semantics.

The task must establish:

```text
ONE normalization owner
ONE canonical field name
ONE lexical algorithm
ONE source-vs-derived contract
```

before Device Type is expanded into more UI consumers.

---

# 3. Exact Baseline

```text
REPOSITORY =
ZaurNavi/CaptivePortal

HEAD =
2d87fd6d56f969492318e21c809086576b2b1ab1

TREE =
346c7f1f8ad6e91f36fbd572b7c8f6e7a22add11

PR #118 =
MERGED

PRODUCTION ARTIFACT =
ACCEPTED
```

Tech Lead must fresh-rebind this SHA/tree before FINAL. If `main` moves, the DRAFT remains architectural input but exact FINAL file/symbol binding must be repeated.

Coder receives nothing at DRAFT stage.

---

# 4. Current State / Source Inventory

## 4.1 Current State

Files:

```text
app/current_state/normalizer.py
app/current_state/models.py
app/current_state/repository.py
```

Omada aliases:

```text
deviceType
device_type
```

write to:

```text
device_type
```

Current normalization semantics:

```text
nullable
string only
maximum 128 UTF-8 bytes
empty invalid
NUL invalid
UTF-8 encode failure invalid
overlong invalid
NO trim
NO case normalization
NO semantic classification
```

Model/storage already contain:

```text
CurrentClientState.device_type: str | None
current_client_state.device_type TEXT
```

These semantics remain unchanged.

## 4.2 Observations

Files:

```text
app/observations/normalizer.py
app/observations/models.py
app/observations/repository.py
app/observations/read_service.py
```

Separate source facts:

```text
system_name
device_type
connect_device_type
```

Aliases:

```text
device_type:
deviceType
device_type

connect_device_type:
connectDevType
connectDeviceType
connect_device_type
```

Accepted text is already `.strip()` before persistence. There is no casefold or classification.

Storage remains:

```text
client_observations.device_type TEXT
client_observations.connect_device_type TEXT
```

`ClientObservation` exposes non-core columns through `data`.

Permanent invariant:

```text
system_name
device_type
connect_device_type
ARE INDEPENDENT SOURCE FACTS
```

## 4.3 Visitor Snapshot / Registry

Files:

```text
app/visitor_registry/snapshot_normalizer.py
app/visitor_registry/registry_repository.py
app/visitor_registry/registry_read_service.py
```

Mappings include:

```text
deviceType → device_type
connectDevType → connect_device_type
```

Registry persists:

```text
device_snapshots.device_type TEXT
visitor_devices.last_known_device_type TEXT
```

Existing filtering may use `COLLATE NOCASE`, but storage values are not canonicalized.

Registry persistence remains unchanged; only read results are candidates for additive canonical keys.

## 4.4 Admin Historical Device

Files:

```text
app/admin_web/device_gateway.py
app/admin_web/query_service.py
```

Existing DTOs include:

```text
AdminDeviceRow.device_type
AdminDeviceListContextRow.device_type
```

Historical type comes from the latest relevant Site Registry snapshot.

The gateway is historical/source evidence and must not become normalization owner.

## 4.5 Device List Context

File:

```text
app/admin_web/device_list_context_serialization.py
```

Public item already has:

```text
device_type
```

No semantic normalization exists.

The foundation adds sibling:

```text
device_type_key
```

without changing raw `device_type`.

## 4.6 Device Current Context

File:

```text
app/admin_web/device_current_context_serialization.py
```

Contract:

```text
admin.device.current.v1
```

Current client already exposes raw `device_type`.

Foundation adds a sibling key derived from that current raw value only.

## 4.7 Home Current Client

File:

```text
app/admin_web/current_state_serialization.py
```

Critical gap:

```text
CurrentClientState contains device_type
BUT
serialize_client_page() does not publish it
```

Foundation should close this backend contract gap by adding:

```text
device_type
device_type_key
```

to each current client item.

No Home UI Type column is added in this task.

## 4.8 Analytics / Evidence

Files:

```text
app/analytics/models.py
app/analytics/read_service.py
```

`SafeSnapshotSummary` already contains:

```text
device_type: str | None
```

Foundation adds:

```text
device_type_key: str | None
```

computed from the same Registry snapshot raw value.

## 4.9 Frontend

File:

```text
app/admin_web/static/admin.js
```

Current helper:

```text
isAndroidDeviceType(value)
```

does browser-side trim/lowercase exact Android matching.

This foundation task leaves it untouched. A follow-up Web task will replace browser normalization with backend `device_type_key`.

---

# 5. Confirmed Evidence and Semantic Boundary

Confirmed real source includes:

```text
device_type="android"
```

Synthetic source evidence also includes independent values:

```text
system_name="Android"
device_type="phone"
connect_device_type="ap"
```

Therefore V1 explicitly forbids:

```text
phone → android

system_name=Android
→ device_type_key=android

connect_device_type=ap
→ any device_type classification
```

No semantic alias map is authorized.

---

# 6. Architectural Decision

Canonical flow:

```text
persist existing source evidence
        ↓
existing read boundary
        ↓
shared lexical helper
        ↓
additive machine key
        ↓
backend/public DTO
        ↓
future UI consumer
```

Write paths remain unchanged.

The helper receives exactly one semantic input:

```text
device_type
```

No other device attribute may participate.

---

# 7. Canonical Field Name

Chosen:

```text
device_type_key
```

Reason:

- `key` clearly means machine comparison/matching;
- it does not imply source replacement;
- it does not imply semantic device classification;
- it is suitable for icon/presentation lookup;
- it keeps raw `device_type` conceptually primary as evidence/display text.

Example:

```json
{
  "device_type": " Android ",
  "device_type_key": "android"
}
```

For Registry device-summary rows whose raw field is `last_known_device_type`, the matching additive field is:

```text
last_known_device_type_key
```

---

# 8. Canonical Owner

New module:

```text
app/common/device_type.py
```

Exact architecture-level API:

```python
DEVICE_TYPE_KEY_MAX_UTF8_BYTES = 128

def normalize_device_type_key(
    source_value: object,
) -> str | None:
    ...
```

No service object, I/O, config, DB, network, cache, or external lookup.

`app/common` is the correct owner because the contract crosses Current State, Registry, Observations, Analytics and Admin Web.

---

# 9. Canonical Data Contract

## 9.1 Accepted input types

```text
None → None

str → validate/canonicalize

anything else → None
```

No implicit `str(value)` conversion.

## 9.2 Outer whitespace

Use:

```python
trimmed = source_value.strip()
```

Leading/trailing Unicode whitespace is removed for key derivation only.

Whitespace-only:

```text
→ None
```

Raw source field is never rewritten.

## 9.3 Case

Use:

```python
canonical = trimmed.casefold()
```

Unicode casefold is locale-independent.

Examples:

```text
"android" → "android"
"Android" → "android"
"ANDROID" → "android"
" android " → "android"
"phone" → "phone"
```

Contract wording is `casefolded`, not “ASCII lowercase for every Unicode string”.

## 9.4 Unicode normalization

Do NOT apply:

```text
NFC
NFD
NFKC
NFKD
```

V1 is lexical trim+casefold, not compatibility normalization.

## 9.5 NUL

If `"\x00"` appears anywhere:

```text
→ None
```

No truncation/removal/replacement.

## 9.6 UTF-8 validity

Trimmed source must strict-encode to UTF-8.

Encoding failure, including malformed surrogate content:

```text
→ None
```

## 9.7 Length

Bound V1 canonical domain to:

```text
128 UTF-8 bytes
```

Require both:

```text
trimmed source UTF-8 <= 128 bytes
canonical casefolded output UTF-8 <= 128 bytes
```

Casefold may expand characters, so both checks are required.

## 9.8 Internal structure

Preserve internal:

```text
spaces
multiple spaces
hyphens
underscores
periods
slashes
punctuation
digits
```

except ordinary casefold effects.

Examples:

```text
"Smart  Phone" → "smart  phone"
"Smart-Phone" → "smart-phone"
"Smart_Phone" → "smart_phone"
```

No separator normalization.

## 9.9 Unknown values

Unknown but valid values remain lexical keys:

```text
"phone" → "phone"
"NewVendorThing" → "newvendorthing"
```

No known-category allowlist.

## 9.10 Determinism

Same input must always produce the same output independently of:

```text
Site
MAC
hostname
vendor
SSID
AP
IP
history
time
locale
DB
network
controller state
```

## 9.11 Fail-closed

If canonicalization cannot safely produce a bounded valid key:

```text
device_type_key = None
```

Do not guess, use another source field, return `"unknown"`, or make the read fail for ordinary malformed Device Type input.

---

# 10. Source-vs-Normalized Semantics

Permanent two-field model:

```text
device_type
=
existing source/persisted evidence
according to the existing domain's rules

device_type_key
=
derived lexical machine key
from that exact device_type
```

Invariant:

```text
device_type_key MUST NEVER replace device_type
```

If a surface already publishes raw `device_type`, it keeps doing so unchanged.

---

# 11. No Cross-Field Inference

Forbidden inputs to the canonical key:

```text
system_name
connect_device_type
hostname
name
MAC/OUI
vendor
SSID
AP
IP
radio/band
auth
traffic
history
User-Agent
DHCP fingerprint
```

No fallback chain exists.

---

# 12. Read-Time vs Storage Decision

V1 explicitly chooses:

```text
READ-TIME CANONICALIZATION
```

Storage-level canonicalization is unnecessary because persisted raw text is sufficient to deterministically derive the key.

Hybrid is also rejected because it would create two mechanisms:

```text
old rows derive
new rows persist
```

and create future drift risk.

If a future multi-source classification becomes expensive and needs materialization, that is a separate architecture.

---

# 13. Current State Write Path

NO CHANGE:

```text
app/current_state/normalizer.py
app/current_state/models.py
app/current_state/repository.py
```

Example:

```text
persisted:
device_type=" Android "

public:
device_type=" Android "
device_type_key="android"
```

No canonicalization leaks into Current State storage.

---

# 14. Observations Write Path

NO CHANGE:

```text
app/observations/normalizer.py
app/observations/models.py
app/observations/repository.py
```

Existing trim semantics remain.

Example source:

```text
" Android "
```

may persist as:

```text
"Android"
```

Read output:

```text
device_type="Android"
device_type_key="android"
```

---

# 15. Visitor Registry Write Path

NO CHANGE:

```text
app/visitor_registry/snapshot_normalizer.py
app/visitor_registry/registry_repository.py
```

Historical source text remains untouched.

Example:

```text
device_type=" Android "
device_type_key="android"
```

at read time.

No backfill.

---

# 16. Home Current Client Public Contract

Modify:

```text
app/admin_web/current_state_serialization.py
```

Function:

```text
serialize_client_page()
```

Add to each item:

```text
device_type =
item.device_type

device_type_key =
normalize_device_type_key(item.device_type)
```

No alternative source.

No UI column in this task.

---

# 17. Home Current Client API Version

Architect recommendation:

```text
keep api_version = admin.read.v1
```

because fields are additive and nullable:

```text
no existing key removed
no existing key renamed
no existing type changed
no existing semantics changed
```

Tech Lead must verify exact repository v1 governance before FINAL.

If v1 exact-field immutability forbids this:

```text
return FIX-1 to Architect
```

Coder never chooses the version.

---

# 18. Device List Context Public Contract

Modify:

```text
app/admin_web/device_list_context_serialization.py
```

Existing item:

```text
device_type
```

remains unchanged.

Add:

```text
device_type_key
```

derived from that same raw field.

No SQL/gateway normalization.

---

# 19. Historical Device Gateway

NO CHANGE:

```text
app/admin_web/device_gateway.py
```

Gateway continues owning historical source selection.

It returns raw `device_type`.

Derived public key belongs after the gateway.

---

# 20. Historical Device List / Device Detail DTO

Modify:

```text
app/admin_web/query_service.py
```

Existing shared:

```text
_device_list_dto()
```

keeps its current `asdict()` and `latest_snapshot` removal behavior, then adds:

```text
device_type_key =
normalize_device_type_key(
    value.get("device_type")
)
```

This covers both historical list and the shared Device Detail identity projection without changing gateway DTOs.

No new source lookup.

---

# 21. Device Current Context

Modify:

```text
app/admin_web/device_current_context_serialization.py
```

Inside current-state client:

```text
device_type
→ unchanged

device_type_key
→ normalize_device_type_key(current device_type)
```

Forbidden fallback:

```text
historical identity
latest snapshot
Observation
system_name
connect_device_type
```

If current client is absent, no current type/key is fabricated.

---

# 22. Device Current Contract Version

Architect recommendation:

```text
keep contract_version =
admin.device.current.v1
```

The new sibling is additive/nullable and does not alter existing values.

Tech Lead must validate frozen DTO governance. If v1 exact-field rules forbid this, return to Architect before FINAL.

---

# 23. Visitor Registry Device Summary Reads

Modify:

```text
app/visitor_registry/registry_read_service.py
```

For:

```text
get_device_by_id()
get_device_by_mac()
list_devices()
```

keep:

```text
last_known_device_type
```

and add:

```text
last_known_device_type_key
```

from that exact raw value.

Return enriched copies rather than mutating repository-owned objects in place.

---

# 24. Visitor Registry Snapshot Reads

For:

```text
list_device_snapshots()
```

keep:

```text
device_type
```

and add:

```text
device_type_key
```

from each snapshot's raw `device_type`.

`get_snapshot_by_auth_session()` currently returns link/identity metadata without Device Type and remains unchanged.

---

# 25. Registry Filter Semantics

Existing `device_type` filtering remains unchanged, including existing case-insensitive comparison where used.

This task does NOT redefine filter input as `device_type_key`.

Normalized filtering can be a separate task if ever required.

---

# 26. Observation Read Contract

Modify:

```text
app/observations/read_service.py
```

In `_client_dto()`:

1. produce existing `data = _data(...)`;
2. add:
   ```text
   data["device_type_key"] =
   normalize_device_type_key(
       data.get("device_type")
   )
   ```
3. construct `ClientObservation`.

Existing raw `data["device_type"]` remains unchanged.

---

# 27. Observation Model Decision

NO CHANGE:

```text
app/observations/models.py
```

`device_type_key` is derived read data inside:

```text
ClientObservation.data
```

not a stored/core schema field.

No Observation schema version bump.

---

# 28. Observation No-Inference Example

Input row:

```text
system_name="Android"
device_type="phone"
connect_device_type="ap"
```

Required:

```text
device_type="phone"
device_type_key="phone"
system_name="Android"
connect_device_type="ap"
```

Forbidden:

```text
device_type_key="android"
```

---

# 29. Analytics SafeSnapshotSummary

Modify:

```text
app/analytics/models.py
```

Add sibling:

```python
device_type_key: str | None
```

next to existing:

```python
device_type: str | None
```

This is a read DTO only.

No Analytics persistence change.

---

# 30. Analytics Snapshot Construction

Modify:

```text
app/analytics/read_service.py
```

In existing `_snapshot(row)`:

```text
device_type =
row["device_type"]

device_type_key =
normalize_device_type_key(
    row["device_type"]
)
```

No fallback to hostname/system/connect type.

---

# 31. Analytics API Compatibility

Recommendation:

```text
existing Analytics read contract version remains
```

because the field is additive and raw semantics are unchanged.

Tech Lead must rebind all exact constructor/serializer consumers before FINAL.

If an exact immutable field-set contract requires versioning, return FIX to Architect.

---

# 32. Current Frontend Compatibility

Foundation does NOT modify:

```text
app/admin_web/static/admin.js
```

Current production `isAndroidDeviceType()` remains temporarily.

This guarantees no visual change while backend contract is introduced.

After foundation acceptance, a dedicated Web task will switch icon selection to:

```text
device_type_key === "android"
```

and remove browser-owned normalization.

---

# 33. Android Compatibility Invariant

Backend foundation must prove:

```text
device_type="android"
→ device_type_key="android"
```

and:

```text
"Android"
"ANDROID"
" android "
→ "android"
```

Visible raw source text remains raw.

No automatic display rewrite to:

```text
Android
Phone
Android Phone
```

---

# 34. Public Contract Summary

For normal raw fields:

```json
{
  "device_type": "<existing source value or null>",
  "device_type_key": "<derived key or null>"
}
```

For Registry device summaries:

```json
{
  "last_known_device_type": "<existing value or null>",
  "last_known_device_type_key": "<derived key or null>"
}
```

The key is never authoritative source evidence.

---

# 35. Cross-Surface Invariant

Equal lexical source input must produce equal key across:

```text
Current State
Registry snapshot
Observation
Admin Device
Analytics
```

Example:

```text
"ANDROID"
→ "android"
```

Different domains may preserve raw text differently while producing the same key.

---

# 36. Schema Impact

```text
DB SCHEMA MIGRATION = NO

BACKFILL = NO

Current State schema v1 = NO CHANGE

Observations schema v1 = NO CHANGE

Visitor Registry schema v1 = NO CHANGE

Analytics persisted schema = NO CHANGE

Traffic Projection schema = NO CHANGE

NEW COLUMN = NO

NEW INDEX = NO
```

---

# 37. Historical Data Behavior

Existing historical rows immediately gain a key when read by changed code.

No age cutoff and no distinction between pre-task/post-task persisted rows.

Historical source text is never rewritten.

---

# 38. Backward Compatibility

Existing `device_type` retains:

```text
same name
same source
same nullability
same raw value
same persistence semantics
```

All changes are additive derived read fields.

Existing consumers may ignore them.

---

# 39. Failure Semantics

The canonical helper is non-throwing for ordinary untrusted source values.

Malformed Device Type:

```text
raw field =
whatever existing safe read contract exposes

device_type_key =
null
```

The new derived key must not make an otherwise valid read unavailable.

Programming errors outside the helper's malformed-input domain remain normal implementation failures; do not broadly swallow unrelated exceptions.

---

# 40. Security / Privacy Boundary

No new data collection.

No external lookup.

No vendor/OUI query.

No fingerprinting.

No controller write.

No new raw payload retention.

Only an already existing source value is transformed into a bounded lexical key.

---

# 41. Device Classification Boundary

This is NOT a Device Classification Layer.

Future classification, if approved, must be separate and may need fields such as:

```text
device_class
classification_source
classification_confidence
classification_reason
```

That future layer must not overload `device_type_key`.

---

# 42. Feature Flag Decision

```text
FEATURE FLAG = NO
```

Reasons:

```text
pure deterministic helper
additive read fields
no migration
no background worker
no external dependency
simple code rollback
```

Two competing canonicalization regimes should not coexist behind a flag.

---

# 43. Runtime / Activation

No new service, worker, scheduled job, environment setting or migration command.

Normal artifact deployment/restart loads the read-time contract.

No DB rebuild or source rescan.

---

# 44. Rollback

Code-only rollback.

Persisted raw data is untouched, so rollback requires:

```text
NO DB restore
NO reverse migration
NO backfill reversal
NO repair
```

The additive derived fields simply disappear with the older artifact.

---

# 45. Exact NEW Files — DRAFT

```text
app/common/device_type.py

tests/test_device_type.py
```

Consumers import explicitly:

```python
from app.common.device_type import normalize_device_type_key
```

`app/common/__init__.py` does not need modification by default.

---

# 46. Exact MODIFY Files — DRAFT

```text
app/admin_web/current_state_serialization.py

app/admin_web/device_list_context_serialization.py

app/admin_web/device_current_context_serialization.py

app/admin_web/query_service.py

app/visitor_registry/registry_read_service.py

app/observations/read_service.py

app/analytics/models.py

app/analytics/read_service.py
```

Tech Lead must source-rebind exact symbols before FINAL.

---

# 47. Explicit NO-TOUCH Write/Schema Files

```text
app/current_state/normalizer.py
app/current_state/models.py
app/current_state/repository.py

app/observations/normalizer.py
app/observations/models.py
app/observations/repository.py

app/visitor_registry/snapshot_normalizer.py
app/visitor_registry/registry_repository.py
app/visitor_registry/snapshot_models.py

app/admin_web/device_gateway.py
```

If FINAL implementation objectively needs a NO-TOUCH file, return to Architect first.

---

# 48. Explicit NO-TOUCH Frontend

```text
app/admin_web/static/admin.js
app/admin_web/static/admin.css
templates/**
icon assets
```

No visual redesign, new Type column, new icon, or browser-normalization migration in this foundation task.

---

# 49. Explicit Non-Goals

OUT OF SCOPE:

```text
DHCP fingerprinting
MAC/OUI inference
vendor inference
hostname inference
system_name inference
connect_device_type inference
User-Agent inference
SSID/AP/IP inference
history inference
ML classification
confidence score
semantic alias map
phone → android
mobile → android
new Device Type icons
Home Type column
Devices redesign
Device Detail redesign
Omada writes/control
external lookups
Registry filter redesign
stored canonical column
schema migration
backfill
```

---

# 50. Coder Narrow Semantic Tests — Future FINAL

`tests/test_device_type.py` must cover:

```text
None → None

"android" → "android"

"Android" → "android"

"ANDROID" → "android"

" android " → "android"

whitespace-only → None

empty → None

non-string → None

embedded NUL → None

unpaired surrogate / UTF-8 invalid → None

"phone" → "phone"

"Smart  Phone" → "smart  phone"

"Smart-Phone" → "smart-phone"

"Smart_Phone" → "smart_phone"

128-byte valid boundary → accepted

129-byte trimmed source → None

casefold expansion over 128 bytes → None
```

Also prove application code does not perform NFC/NFKC normalization.

---

# 51. No-Inference Regression

Tests must include a case where:

```text
device_type="phone"
system_name="Android"
connect_device_type="ap"
hostname looks Android-related
MAC/vendor-like fixture exists
```

Required:

```text
device_type_key="phone"
```

Only raw `device_type` is passed to helper.

---

# 52. Home Current Client Tests

Update exact existing Home/current-client tests after Tech Lead rebind.

Required:

```text
raw device_type now present
device_type_key present
raw unchanged
key canonical
null raw → null key
phone → phone
api_version remains admin.read.v1
if additive-in-v1 rule is accepted
```

No UI Type column test in this task.

---

# 53. Device List Context Tests

Existing target:

```text
tests/admin_web/test_device_list_context_serialization.py
```

Required:

```text
raw preserved
key additive
android variants → android
phone → phone
null → null
no classification metadata
```

---

# 54. Device Current Context Tests

Existing target:

```text
tests/admin_web/test_device_current_context.py
```

Required:

```text
current raw type preserved
key derived from current raw only
no historical fallback
no system_name fallback
contract_version stays admin.device.current.v1
if Tech Lead accepts v1 additive rule
```

Frontend contract fixtures are changed only if exact-key validation requires them; no browser behavior changes.

---

# 55. Historical Device Query Tests

Existing target:

```text
tests/admin_web/test_query_service.py
```

Required:

```text
historical list raw type preserved
historical list key derived
Device Detail identity raw preserved
Device Detail identity key derived
latest_snapshot still not leaked
gateway semantics unchanged
```

---

# 56. Visitor Registry Read Tests

Primary existing test module:

```text
tests/visitor_registry/test_device_registry.py
```

Required:

```text
get_device_by_id:
raw last_known_device_type unchanged
last_known_device_type_key derived

get_device_by_mac:
same

list_devices:
same

list_device_snapshots:
raw device_type unchanged
device_type_key derived

get_snapshot_by_auth_session:
unchanged output contract
```

No Registry write/schema changes merely to support key tests.

---

# 57. Observation Read Tests

Tech Lead must bind the exact existing read-service test module/function under:

```text
tests/observations/
```

Required:

```text
ClientObservation.data["device_type"] unchanged

ClientObservation.data["device_type_key"] derived

system_name ignored

connect_device_type ignored

historical persisted row gains key without rewrite
```

Observation normalizer tests remain regression-only because write semantics do not change.

---

# 58. Analytics Read Tests

Tech Lead must bind exact tests under:

```text
tests/analytics/
```

Required:

```text
SafeSnapshotSummary.device_type unchanged

SafeSnapshotSummary.device_type_key derived

null propagation

unknown valid type preserved lexically

no hostname/system inference

all exact dataclass constructor fixtures updated additively
```

---

# 59. Cross-Surface Contract Test

One focused acceptance test must compare approved read surfaces.

Example:

```text
Current State raw = " ANDROID "
Registry raw = "Android"
Observation raw = "android"
```

Required:

```text
device_type_key == "android"
```

on every changed read surface.

At the same time, each raw field must remain exactly consistent with its domain's existing source semantics.

---

# 60. Historical No-Backfill Test

Seed/retain historical rows first.

Without rewriting DB rows, read through:

```text
Registry
Observation
historical Device
```

Required:

```text
key appears immediately
raw persisted data remains unchanged
```

---

# 61. Source/Canonical Preservation Test

At least one surface whose raw contract preserves source case/whitespace must explicitly prove:

```text
device_type=" Android "
device_type_key="android"
```

and verify raw was not rewritten to `"android"`.

---

# 62. Android Icon Compatibility

Foundation test responsibility:

```text
normalize_device_type_key("android") == "android"
```

Actual browser migration remains follow-up.

Current `isAndroidDeviceType()` must continue to work because this task does not modify frontend.

---

# 63. Coder Narrow-Test Scope — DRAFT

Expected core modules for FINAL:

```text
tests/test_device_type.py

tests/admin_web/test_home_live.py

tests/admin_web/test_device_list_context_serialization.py

tests/admin_web/test_device_current_context.py

tests/admin_web/test_query_service.py

tests/visitor_registry/test_device_registry.py

exact Observation read-service test
→ Tech Lead rebind

exact Analytics snapshot/read tests
→ Tech Lead rebind
```

Plus compile/syntax of touched files and `git diff --check`.

Exact commands belong in FINAL, not DRAFT.

---

# 64. Testing Governance

Coder later proves narrow implementation correctness only.

Coder does NOT run/claim:

```text
Central Full Gate
full repository regression
production deployment
production smoke
browser visual acceptance
official schema acceptance
official API compatibility acceptance
TASK PASS
merge ready
production ready
```

Owner + Tech Lead perform official acceptance.

---

# 65. Tech Lead / Central Lab Acceptance Scope

Official acceptance must include:

```text
fresh candidate SHA/tree

source review against FINAL scope

helper semantic matrix

cross-surface same-key proof

raw evidence preservation

no-inference proof

DB schema signatures unchanged

no migration/backfill

Admin API compatibility

Device Current DTO compatibility

Registry read compatibility

Observation read compatibility

Analytics read compatibility

Home Current Client backend fields present

Home visual UI unchanged

existing Android icon still works

historical rows derive key without rewrite

no new browser canonicalization in foundation
```

---

# 66. Schema Signature Acceptance

Prove unchanged:

```text
Current State schema/version

Observations schema/version

Visitor Registry schema/version
```

No new columns/indexes.

No migration side effects.

---

# 67. API Compatibility Acceptance

Existing pre-task fields must retain exact:

```text
names
types
nullability
semantics
```

Only explicitly approved additive key fields may appear.

Verify:

```text
admin.read.v1
admin.device.current.v1
Analytics contract version
```

according to Tech Lead's version-governance review.

---

# 68. Visual Non-Regression

Home Current Client API becomes richer, but foundation must not change:

```text
Home table columns
layout
colors
RSSI presentation
Auth/Band styling
Uptime
Traffic
```

Devices/Device Detail visible source type text is not rewritten.

---

# 69. Performance

Helper complexity:

```text
O(source string length)
```

No DB query, network request, collection, population scan, or external lookup.

No dedicated capacity benchmark is architecturally required solely for the helper. Tech Lead may run existing page/capacity gates if testing governance requires them.

---

# 70. Rollout

```text
1. Tech Lead reviews this DRAFT.

2. Architect incorporates exact FIXes if any.

3. Prepare implementation-ready FINAL.

4. Owner authorizes Coder.

5. Coder implements + narrow tests.

6. Owner + Tech Lead official acceptance.

7. Normal artifact-coherent deployment.

8. Verify additive backend fields.

9. Verify raw source preservation.

10. Verify current UI unchanged.

11. Foundation accepted.

12. Start Web consumer migration.
```

---

# 71. Deployment

No special migration sequence.

Normal application artifact deployment/restart only.

No Current State reset.

No Observation reset.

No Registry rebuild.

No Analytics rebuild.

No Traffic Projection repair.

---

# 72. Proposed Follow-Up Task

Recommended:

```text
TASK-WEB-DEVICE-TYPE-CONSUMERS-01
— Canonical Device Type Presentation Adoption
```

Minimum scope:

```text
Home Online Devices:
add Type presentation using raw device_type

existing Android icon consumers:
use device_type_key == "android"

remove browser-owned isAndroidDeviceType() normalization

preserve raw visible type text

no new semantic categories

no new icons unless separately authorized
```

This task starts only after backend foundation PASS.

---

# 73. Follow-Up Presentation Contract

Future UI uses:

```text
device_type
→ visible source text

device_type_key
→ machine/icon matching
```

Example:

```text
raw = "android"
key = "android"

visible = android
icon = existing Android icon
```

Not:

```text
Android Phone
Phone
```

unless Owner separately authorizes display semantics.

---

# 74. Acceptance Criteria

Architecture/implementation passes only if all are true:

```text
one canonical owner exists

device_type raw semantics unchanged

device_type_key additive

read-time architecture used

no migration

no backfill

no inference

all approved read surfaces use same helper

Home backend gap closed

same source lexical value gives same key

raw evidence remains domain-correct

invalid canonical source gives null key

unknown valid source remains lexical value

current UI unchanged

Android production compatibility retained
```

---

# 75. Risk / Open Question 1 — API Versioning

Architect recommendation:

```text
admin.read.v1 remains
admin.device.current.v1 remains
```

Tech Lead must answer:

```text
Does repository governance forbid additive nullable fields
inside these existing v1 DTOs?
```

If YES:

```text
return exact FIX-1
with affected contract/version rule
```

No Coder discretion.

---

# 76. Risk / Open Question 2 — Registry Naming

Architect recommendation:

```text
device summary:
last_known_device_type_key

snapshot:
device_type_key
```

Tech Lead must verify exact result dictionaries and whether any additional Registry read/CLI surface carries type and needs the key.

---

# 77. Risk / Open Question 3 — Analytics Frozen DTO Consumers

Adding `SafeSnapshotSummary.device_type_key` can require fixture/constructor updates.

Tech Lead must identify every exact constructor and serializer consumer before FINAL.

This does not justify storage-level canonicalization.

---

# 78. Risk / Open Question 4 — 128-byte Bound

Current State already uses a 128-byte source bound.

Registry/Observation historical data may theoretically contain longer source strings.

V1 recommendation:

```text
raw remains visible

canonical key for >128-byte trimmed source
→ null
```

Tech Lead should check fixtures/known evidence for accepted longer values before FINAL.

---

# 79. Risk / Open Question 5 — Unicode Policy

`casefold()` is intentionally stronger than simple ASCII lowercase for some Unicode characters.

No NFC/NFKC is applied.

Tech Lead should validate this as the stable lexical policy.

Future semantic aliases/classification remain separate.

---

# 80. Risk / Open Question 6 — Exact Observation Tests

Architecture surface is fixed:

```text
ObservationReadService._client_dto()
ClientObservation.data
```

Tech Lead must bind exact existing test file/functions for FINAL.

No write-path change.

---

# 81. Risk / Open Question 7 — Browser Helper Removal Timing

Architecture recommendation:

```text
do NOT remove isAndroidDeviceType()
inside backend foundation
```

Remove it only after backend acceptance in the follow-up Web task.

This keeps backend contract acceptance separate from visual migration.

---

# 82. DRAFT File Matrix

```text
NEW:

app/common/device_type.py
tests/test_device_type.py
```

```text
MODIFY:

app/admin_web/current_state_serialization.py
app/admin_web/device_list_context_serialization.py
app/admin_web/device_current_context_serialization.py
app/admin_web/query_service.py

app/visitor_registry/registry_read_service.py

app/observations/read_service.py

app/analytics/models.py
app/analytics/read_service.py
```

```text
NO-TOUCH:

app/current_state/normalizer.py
app/current_state/models.py
app/current_state/repository.py

app/observations/normalizer.py
app/observations/models.py
app/observations/repository.py

app/visitor_registry/snapshot_normalizer.py
app/visitor_registry/registry_repository.py
app/visitor_registry/snapshot_models.py

app/admin_web/device_gateway.py

app/admin_web/static/admin.js
app/admin_web/static/admin.css
templates/**
icon assets

DB schema/version owners
Omada writes/control
Traffic
Auth
systemd
Nginx
Grafana/Loki/Alloy
```

---

# 83. DRAFT Test Matrix

```text
NEW:

tests/test_device_type.py
```

Expected existing test targets:

```text
tests/admin_web/test_home_live.py

tests/admin_web/test_device_list_context_serialization.py

tests/admin_web/test_device_current_context.py

tests/admin_web/test_query_service.py

tests/visitor_registry/test_device_registry.py

exact tests/observations read-service module
→ Tech Lead bind

exact tests/analytics snapshot/read module(s)
→ Tech Lead bind
```

No full-suite command assigned at DRAFT stage.

---

# 84. Architect Decision Summary

```text
TASK =
TASK-DEVICE-TYPE-NORMALIZATION-01

ARCHITECT RECOMMENDATION =
A) READ-TIME ADDITIVE CANONICALIZATION

CANONICAL OWNER =
app/common/device_type.py

CANONICAL FIELD =
device_type_key

RAW FIELD =
device_type
UNCHANGED

HELPER =
normalize_device_type_key(source_value)

NORMALIZATION =
outer strip
+
Unicode casefold

UNICODE NFC/NFKC =
NO

INTERNAL SPACES =
PRESERVED

HYPHENS/UNDERSCORES =
PRESERVED

NUL =
INVALID → null

NON-STRING =
null

WHITESPACE-ONLY =
null

UTF-8 INVALID =
null

MAX TRIMMED SOURCE =
128 UTF-8 bytes

MAX KEY =
128 UTF-8 bytes

UNKNOWN VALID SOURCE =
PRESERVED LEXICALLY

SEMANTIC ALIASES =
NO

INFERENCE =
NO

DB MIGRATION =
NO

BACKFILL =
NO

CURRENT STATE SCHEMA =
UNCHANGED

OBSERVATIONS SCHEMA =
UNCHANGED

VISITOR REGISTRY SCHEMA =
UNCHANGED

ANALYTICS PERSISTENCE =
UNCHANGED

HOME CURRENT CLIENT API =
ADD device_type
+
device_type_key

HOME UI TYPE COLUMN =
OUT OF SCOPE

DEVICE LIST =
ADD device_type_key

DEVICE DETAIL =
ADD device_type_key

DEVICE CURRENT =
ADD device_type_key

REGISTRY READS =
ADD derived sibling keys

OBSERVATION READS =
ADD device_type_key to ClientObservation.data

ANALYTICS =
ADD SafeSnapshotSummary.device_type_key

API VERSION RECOMMENDATION =
KEEP existing v1 versions
subject to Tech Lead governance confirmation

FEATURE FLAG =
NO

FRONTEND HELPER REMOVAL =
FOLLOW-UP WEB TASK

CODER =
HOLD

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED
```

---

# 85. Required Tech Lead Review

Tech Lead must verify at exact baseline:

```text
HEAD/tree

all device_type source/write/read occurrences

shared DTO use in query_service

strict serializer key sets

admin.read.v1 additive-field governance

admin.device.current.v1 additive-field governance

Registry read result shapes

exact Observation read tests

Analytics exact constructor/serializer consumers

any additional public read surface exposing device_type

128-byte bound against accepted fixtures/data
```

Then return:

```text
PASS
```

or:

```text
FIX-1 / FIX-N
with exact source evidence
```

---

# 86. DRAFT Gate

```text
STATUS =
DRAFT — FOR TECH LEAD REVIEW

ARCHITECTURE DIRECTION =
READ-TIME ADDITIVE

IMPLEMENTATION-READY =
NO

CODER =
HOLD

CODER PLAN =
NOT REQUESTED / FORBIDDEN

BRANCH =
NOT AUTHORIZED

COMMIT =
NOT AUTHORIZED

PUSH =
NOT AUTHORIZED

PR =
NOT AUTHORIZED

PRODUCTION =
UNTOUCHED
```

---

# 87. Next Workflow

```text
TASK-DEVICE-TYPE-NORMALIZATION-01-DRAFT
        ↓
Tech Lead source/architecture review
        ↓
if corrections:
Architect corrected DRAFT
        ↓
Tech Lead PASS
        ↓
Architect + Tech Lead implementation-ready FINAL
        ↓
Owner review
        ↓
Owner explicit implementation authorization
        ↓
Coder
        ↓
narrow tests only
        ↓
Coder handoff
        ↓
Owner + Tech Lead official acceptance
        ↓
controlled deployment
        ↓
TASK-WEB-DEVICE-TYPE-CONSUMERS-01
```

This DRAFT does not authorize implementation.
