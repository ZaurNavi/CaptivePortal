# TASK-DEVICE-TYPE-NORMALIZATION-01-FINAL

## Canonical Device Type Foundation

**Project:** CaptivPortal  
**Task:** `TASK-DEVICE-TYPE-NORMALIZATION-01`  
**Priority:** Backend / Foundation  
**Status:** `FINAL — FOR TECH LEAD / OWNER IMPLEMENTATION AUTHORIZATION`  
**Architecture review:** `PASS`  
**Baseline rebind:** `PASS`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Coder PLAN:** `NOT REQUESTED / FORBIDDEN`  
**Branch / commit / push / PR / merge:** `NOT AUTHORIZED`  
**Production:** `UNTOUCHED`  
**Prepared:** 2026-09-13

---

# 0. Final Gate

```text
TASK =
TASK-DEVICE-TYPE-NORMALIZATION-01

STATUS =
FINAL — FOR TECH LEAD / OWNER IMPLEMENTATION AUTHORIZATION

ARCHITECTURE =
PASS / FROZEN

BASELINE REBIND =
PASS

CODER =
HOLD

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

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

This document is implementation-ready but does not itself authorize implementation.

---

# 1. Authorized Baseline

```text
REPOSITORY =
ZaurNavi/CaptivePortal

HEAD =
2d87fd6d56f969492318e21c809086576b2b1ab1

TREE =
346c7f1f8ad6e91f36fbd572b7c8f6e7a22add11

MAIN DRIFT =
NO
```

Before Owner implementation authorization, Tech Lead must verify that `main` still matches this SHA/tree.

If baseline changes:

```text
CODER remains HOLD
→ Tech Lead impact rebind
→ only then implementation authorization
```

---

# 2. Final Architectural Decision

Frozen:

```text
A) READ-TIME ADDITIVE CANONICALIZATION = ACCEPTED

B) STORAGE-LEVEL CANONICALIZATION = REJECTED FOR V1

C) HYBRID = REJECTED FOR V1
```

Permanent two-field model:

```text
device_type
=
existing source/persisted evidence

device_type_key
=
derived lexical machine key
from that exact device_type
```

For Visitor Registry device summaries:

```text
last_known_device_type
=
existing source/persisted last-known evidence

last_known_device_type_key
=
derived lexical machine key
from last_known_device_type
```

No derived key becomes authoritative source evidence.

---

# 3. Canonical Semantic Owner

Add exactly:

```text
app/common/device_type.py
```

Public API:

```python
DEVICE_TYPE_KEY_MAX_UTF8_BYTES = 128

def normalize_device_type_key(
    source_value: object,
) -> str | None:
    ...
```

No other normalization owner is authorized.

No:

```text
service object
DB access
network access
external lookup
configuration
cache
runtime state
site state
device state
```

inside this helper.

---

# 4. Exact Canonicalization Algorithm

Implementation order is frozen.

```text
1. if source_value is None:
       return None

2. if source_value is not str:
       return None

3. trimmed = source_value.strip()

4. if trimmed == "":
       return None

5. if "\x00" in trimmed:
       return None

6. strict UTF-8 encode trimmed.
   If UnicodeEncodeError:
       return None

7. if len(trimmed UTF-8 bytes) > 128:
       return None

8. canonical = trimmed.casefold()

9. if canonical == "":
       return None

10. if "\x00" in canonical:
        return None

11. strict UTF-8 encode canonical.
    If UnicodeEncodeError:
        return None

12. if len(canonical UTF-8 bytes) > 128:
        return None

13. return canonical
```

Do not call:

```text
unicodedata.normalize()
lower() as a substitute for casefold()
locale-dependent transforms
regular-expression alias transforms
separator collapsing
```

---

# 5. Canonical Examples

```text
None
→ None

123
→ None

True
→ None

b"android"
→ None

""
→ None

"   "
→ None

"android"
→ "android"

"Android"
→ "android"

"ANDROID"
→ "android"

" android "
→ "android"

"\tAndroid\n"
→ "android"

"phone"
→ "phone"

"NewVendorThing"
→ "newvendorthing"

"Smart  Phone"
→ "smart  phone"

"Smart-Phone"
→ "smart-phone"

"Smart_Phone"
→ "smart_phone"
```

Unknown valid values stay lexical.

---

# 6. Unicode Policy

V1 is exactly:

```text
outer strip
+
Unicode casefold
```

V1 does NOT perform:

```text
NFC
NFD
NFKC
NFKD
```

Canonical-equivalence and compatibility-equivalence are not collapsed.

Required explicit proof examples:

```text
composed:
"É"
→ "é"

decomposed:
"E\u0301"
→ "e\u0301"

required:
outputs remain different
```

and compatibility example:

```text
full-width:
"Ａ"
→ "ａ"

ASCII:
"A"
→ "a"

required:
outputs remain different
```

This prevents accidental introduction of Unicode composition/compatibility normalization.

---

# 7. UTF-8 Byte Bound

Frozen:

```text
MAX TRIMMED SOURCE =
128 UTF-8 bytes

MAX RESULTING KEY =
128 UTF-8 bytes
```

Both bounds are required because Unicode casefold can expand encoded output.

Required expansion test:

```text
source =
"\u0130" * 64
```

The trimmed source is exactly 128 UTF-8 bytes, but casefold output expands beyond 128 UTF-8 bytes.

Required result:

```text
None
```

No truncation.

---

# 8. No Semantic Classification

Forbidden:

```text
phone → android
mobile → android
tablet → android
iphone → ios
unknown alias tables
vendor mappings
platform dictionaries
```

`device_type_key` is not a Device Classification Layer.

---

# 9. No Cross-Field Inference

The helper receives one semantic input only:

```text
device_type
```

Forbidden evidence:

```text
system_name
connect_device_type
hostname
name
MAC
OUI
vendor
SSID
AP
IP
radio
band
auth state
traffic
history
User-Agent
DHCP fingerprint
```

Example:

```text
device_type="phone"
system_name="Android"
connect_device_type="ap"
hostname="Samsung-Phone"
```

Required:

```text
device_type_key="phone"
```

---

# 10. Current State Write Path — NO CHANGE

NO-TOUCH:

```text
app/current_state/normalizer.py
app/current_state/models.py
app/current_state/repository.py
```

Existing Current State semantics stay authoritative:

```text
device_type:
nullable
string only
bounded at 128 UTF-8 bytes
empty invalid
NUL invalid
UTF-8 invalid rejected
NO trim
NO case normalization
```

Example accepted raw source:

```text
device_type=" Android "
```

may remain raw/persisted as:

```text
" Android "
```

Read output may become:

```text
device_type=" Android "
device_type_key="android"
```

No write-path normalization leakage.

---

# 11. Observations Write Path — NO CHANGE

NO-TOUCH:

```text
app/observations/normalizer.py
app/observations/models.py
app/observations/repository.py
```

Existing Observation source semantics remain.

Separate source facts remain:

```text
system_name
device_type
connect_device_type
```

Observation text normalization may already strip accepted source values before persistence.

No additional case or semantic normalization is added to storage.

---

# 12. Visitor Registry Write Path — FINAL INVENTORY

Explicit source/write owner:

```text
app/visitor_registry/registry_service.py
```

NO-TOUCH.

Current `device_type` write path passes through:

```python
_profile_string(
    normalized_client["device_type"]
)
```

Current `_profile_string()` semantics are frozen as existing behavior:

```text
None
→ None

whitespace-only string
→ None

nonblank string
→ return original string unchanged
```

Important:

```text
nonblank source is NOT trimmed

nonblank source is NOT case-normalized
```

Example:

```text
" Android "
→ " Android "
```

at this Registry profile boundary.

No implementation change to:

```text
app/visitor_registry/registry_service.py
```

is authorized.

---

# 13. Visitor Registry Other Write/Schema Files — NO CHANGE

NO-TOUCH:

```text
app/visitor_registry/snapshot_normalizer.py
app/visitor_registry/registry_repository.py
app/visitor_registry/snapshot_models.py
app/visitor_registry/registry_models.py
```

No DB schema/version change.

No snapshot rewrite.

No backfill.

---

# 14. Admin Direct Observation Gateway — NO SCOPE EXPANSION

Explicit NO-TOUCH:

```text
app/admin_web/read_gateway.py
```

Current:

```text
_CLIENT_FIELDS
```

does not expose:

```text
device_type
```

This foundation task does NOT expand that direct Admin Observation gateway.

Do not add:

```text
device_type
device_type_key
```

there merely for symmetry.

Observation normalization belongs to:

```text
ObservationReadService
```

for the approved Observation read contract in this task.

---

# 15. Home Current Client — Exact Implementation

Modify:

```text
app/admin_web/current_state_serialization.py
```

Import:

```python
from app.common.device_type import normalize_device_type_key
```

Inside:

```text
serialize_client_page()
```

each client item gains exactly:

```text
device_type
device_type_key
```

Source:

```python
raw_device_type = item.device_type
```

Public fields:

```python
"device_type": raw_device_type,
"device_type_key": normalize_device_type_key(raw_device_type),
```

No other source.

Existing fields and meanings remain unchanged.

---

# 16. Home API Version

Frozen:

```text
api_version =
admin.read.v1
```

KEEP.

No:

```text
admin.read.v2
```

for this task.

The two new nested client fields are additive.

Current browser validator accepts additive properties.

---

# 17. Home UI Boundary

NO-TOUCH:

```text
app/admin_web/static/admin.js
app/admin_web/static/admin.css
templates/**
icon assets
```

This foundation task does NOT add a Home Type column.

No current visible layout change.

Current browser Android helper remains temporarily.

---

# 18. Device List Context — Exact Source/Public Separation

Modify:

```text
app/admin_web/device_list_context_serialization.py
```

Replace the single input/output `_ITEM_KEYS` ownership with two separate contracts.

Exact source set:

```python
_SOURCE_ITEM_KEYS = {
    "device_id",
    "canonical_mac",
    "hostname",
    "device_type",
    "site_first_seen_at",
    "site_last_seen_at",
    "site_snapshot_count",
    "site_visit_count",
    "last_site_ip",
    "last_site_ssid",
    "last_site_ap_mac",
    "current_presence",
}
```

Exact public set:

```python
_PUBLIC_ITEM_KEYS = _SOURCE_ITEM_KEYS | {
    "device_type_key",
}
```

Do not mutate `_SOURCE_ITEM_KEYS` after definition.

---

# 19. Device List Context `_item()` — Exact Ownership

Frozen algorithm:

```text
1. If value is a dataclass:
   extract exactly _SOURCE_ITEM_KEYS.

2. Else if value is Mapping:
   copy the Mapping.

3. Else:
   raise existing serialization error.

4. Require exactly:
   set(source) == _SOURCE_ITEM_KEYS

5. Perform all current baseline validation
   against source fields exactly as today.

6. Validate raw:
   source["device_type"]
   with the same current source rule.

7. Build public result:
   public = dict(source)

8. Add exactly:
   public["device_type_key"] =
       normalize_device_type_key(
           source["device_type"]
       )

9. Require:
   set(public) == _PUBLIC_ITEM_KEYS

10. return public
```

No upstream key authority.

---

# 20. Device List Context Injection Rejection

A Mapping input containing:

```text
device_type_key
```

is invalid source input because its key set is not exactly `_SOURCE_ITEM_KEYS`.

Contradiction example:

```text
device_type="phone"
device_type_key="android"
```

Required:

```text
DeviceListContextSerializationError
```

It must never become a public DTO.

Serializer is the sole key owner at this boundary.

---

# 21. Device List Gateway — NO CHANGE

NO-TOUCH:

```text
app/admin_web/device_gateway.py
```

Do NOT add `device_type_key` to:

```text
AdminDeviceListContextRow
AdminDeviceRow
SQL
DB
repository DTO
gateway query projection
```

Gateway remains raw/source-only.

---

# 22. Historical Device List / Detail — Exact Implementation

Modify:

```text
app/admin_web/query_service.py
```

Import:

```python
from app.common.device_type import normalize_device_type_key
```

Current shared:

```python
_device_list_dto(item)
```

must keep:

```text
asdict(item)

remove:
latest_snapshot
```

then add:

```python
value["device_type_key"] = normalize_device_type_key(
    value.get("device_type")
)
```

Raw:

```text
value["device_type"]
```

is not rewritten.

This shared DTO path remains the one source for historical Device list and Device Detail identity.

No gateway change.

---

# 23. Device Current Context — Exact Implementation

Modify:

```text
app/admin_web/device_current_context_serialization.py
```

Import:

```python
from app.common.device_type import normalize_device_type_key
```

In existing private:

```python
_client(value)
```

preserve current raw serialization.

Preferred exact shape:

```python
raw_device_type = _text(value.device_type)
```

Then expose:

```python
"device_type": raw_device_type,
"device_type_key": normalize_device_type_key(raw_device_type),
```

Do not derive from:

```text
historical Device identity
Registry
Observation
system_name
connect_device_type
hostname
```

If current raw Device Type is `None`:

```text
device_type_key=None
```

No fallback.

---

# 24. Device Current Contract Version

Frozen:

```text
CONTRACT_VERSION =
admin.device.current.v1
```

KEEP.

No v2.

---

# 25. Visitor Registry Read Service — Exact Implementation

Modify:

```text
app/visitor_registry/registry_read_service.py
```

Import:

```python
from app.common.device_type import normalize_device_type_key
```

Add private pure read-enrichment helpers:

```python
def _device_summary_with_type_key(
    value: dict[str, Any],
) -> dict[str, Any]:
    result = dict(value)
    result["last_known_device_type_key"] = (
        normalize_device_type_key(
            result.get("last_known_device_type")
        )
    )
    return result
```

and:

```python
def _snapshot_with_type_key(
    value: dict[str, Any],
) -> dict[str, Any]:
    result = dict(value)
    result["device_type_key"] = (
        normalize_device_type_key(
            result.get("device_type")
        )
    )
    return result
```

Equivalent local private names are NOT preferred; use these exact names unless Tech Lead explicitly changes them before Owner authorization.

---

# 26. Registry Read Methods — Exact Binding

Update:

```text
get_device_by_id()
get_device_by_mac()
list_devices()
list_device_snapshots()
```

## `get_device_by_id()`

Current repository result:

```text
None
or
dict
```

Required:

```text
None
→ None

dict
→ _device_summary_with_type_key(dict)
```

## `get_device_by_mac()`

Same.

## `list_devices()`

Keep all current filter normalization unchanged.

After repository call:

```text
return a new list of enriched copies
```

using:

```text
_device_summary_with_type_key()
```

for each item.

## `list_device_snapshots()`

Keep pagination/validation unchanged.

Return enriched copies using:

```text
_snapshot_with_type_key()
```

Do not mutate repository-owned dictionaries in place.

---

# 27. Registry Read Naming

Device summary:

```text
last_known_device_type
last_known_device_type_key
```

Snapshot:

```text
device_type
device_type_key
```

No renaming of existing raw fields.

---

# 28. Registry `get_snapshot_by_auth_session()` — NO CHANGE

Current safe link DTO does not contain Device Type.

Do not add Device Type fields there.

No symmetry expansion.

---

# 29. Registry Filter Semantics — NO CHANGE

Current Registry filter:

```text
device_type
```

retains existing semantics.

Do not change filter input to:

```text
device_type_key
```

No normalized-filter redesign.

---

# 30. Registry CLI — CONSUMER ONLY

NO-TOUCH:

```text
app/visitor_registry/cli.py
```

Baseline CLI uses:

```text
VisitorRegistryReadService
```

for:

```text
list
show
snapshots
```

Therefore read-service enrichment propagates automatically.

Forbidden:

```text
normalize_device_type_key()
inside cli.py

CLI alias map

CLI-specific canonicalization

CLI-specific key reconstruction
```

CLI is a consumer, not normalization owner.

---

# 31. Observation Read Service — Exact Implementation

Modify:

```text
app/observations/read_service.py
```

Import:

```python
from app.common.device_type import normalize_device_type_key
```

Current private:

```python
_client_dto(row)
```

must become conceptually:

```python
data = dict(_data(row, _CLIENT_CORE))
data["device_type_key"] = normalize_device_type_key(
    data.get("device_type")
)

return ClientObservation(
    ...,
    data=data,
)
```

No new core column.

No model/schema change.

---

# 32. Observation Read Immutability

Existing `ClientObservation` immutable/frozen behavior remains authoritative.

The new key must be present inside the final immutable `data` mapping.

Do not attach a mutable post-construction dictionary later.

No persistence of `device_type_key`.

---

# 33. Observation Source Semantics

Example:

```text
system_name="Android"
device_type="phone"
connect_device_type="ap"
```

Required:

```text
data["device_type"]="phone"
data["device_type_key"]="phone"
```

Never:

```text
"android"
```

No cross-field fallback.

---

# 34. Analytics Model — Exact Implementation

Modify:

```text
app/analytics/models.py
```

In:

```python
@dataclass(frozen=True, slots=True)
class SafeSnapshotSummary:
```

add exactly:

```python
device_type_key: str | None
```

immediately after:

```python
device_type: str | None
```

No persistence change.

No default value is required if the centralized constructor is updated in the same change.

---

# 35. Analytics Constructor — Exact Owner

Modify:

```text
app/analytics/read_service.py
```

Production constructor is centralized in:

```python
AnalyticsReadService._snapshot()
```

No second constructor owner is introduced.

Import:

```python
from app.common.device_type import normalize_device_type_key
```

In `_snapshot(row)` retain:

```python
device_type=row["device_type"],
```

and add immediately after:

```python
device_type_key=normalize_device_type_key(
    row["device_type"]
),
```

No fallback source.

---

# 36. Analytics API Boundary

Frozen:

```text
analytics.internal.v1 =
KEEP
```

Current internal Analytics HTTP API does not expose `get_visit_context()` / `SafeSnapshotSummary` as a Device Type endpoint.

Do not add a new API route.

Do not fabricate an HTTP Device Type endpoint only to expose the new field.

Existing generic serialization continues to support dataclass serialization as currently designed.

---

# 37. Schema / Storage Decision

Frozen:

```text
DB MIGRATION = NO

BACKFILL = NO

NEW COLUMN = NO

NEW INDEX = NO

SCHEMA VERSION BUMP = NO

CURRENT STATE SCHEMA = UNCHANGED

OBSERVATIONS SCHEMA = UNCHANGED

VISITOR REGISTRY SCHEMA = UNCHANGED

ANALYTICS PERSISTENCE = UNCHANGED

TRAFFIC PROJECTION = UNCHANGED
```

Historical rows derive key at read time.

---

# 38. Feature Flag Decision

```text
FEATURE FLAG = NO
```

No dual semantics.

No config/env setting.

---

# 39. Frontend Migration Boundary

Foundation does NOT change browser implementation.

Current:

```text
isAndroidDeviceType()
```

remains until the follow-up Web task.

After foundation acceptance, recommended follow-up:

```text
TASK-WEB-DEVICE-TYPE-CONSUMERS-01
```

will move icon matching to:

```text
device_type_key == "android"
```

and may add Home Type presentation.

Not part of this FINAL.

---

# 40. Android Compatibility

Must preserve:

```text
normalize_device_type_key("android")
==
"android"
```

and:

```text
"Android"
"ANDROID"
" android "
→ "android"
```

Raw visible value is not rewritten.

No new icon.

No new display label.

---

# 41. FINAL Application File Boundary

## NEW

Exactly:

```text
app/common/device_type.py
```

## MODIFY

Exactly:

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

No other application file is authorized.

---

# 42. FINAL Test File Boundary

## NEW

Exactly:

```text
tests/test_device_type.py
```

## TEST-ONLY MODIFY

Authorized:

```text
tests/admin_web/test_home_live.py

tests/admin_web/test_device_list_context_serialization.py

tests/admin_web/test_device_current_context.py

tests/admin_web/test_query_service.py

tests/admin_web/test_admin_ui_frontend.py

tests/visitor_registry/test_device_registry.py

tests/observations/test_read_service.py

tests/analytics/test_quality_service.py

tests/analytics/test_api_routes.py
```

Regression-only execution, no modification required by default:

```text
tests/analytics/test_safety_and_performance.py
```

If implementation needs to modify another test file:

```text
STOP
→ report exact reason to Tech Lead
```

---

# 43. Explicit NO-TOUCH Application Files

At minimum:

```text
app/current_state/normalizer.py
app/current_state/models.py
app/current_state/repository.py

app/observations/normalizer.py
app/observations/models.py
app/observations/repository.py

app/visitor_registry/registry_service.py
app/visitor_registry/snapshot_normalizer.py
app/visitor_registry/registry_repository.py
app/visitor_registry/registry_models.py
app/visitor_registry/snapshot_models.py
app/visitor_registry/cli.py

app/admin_web/device_gateway.py
app/admin_web/read_gateway.py

app/admin_web/static/admin.js
app/admin_web/static/admin.css
templates/**
icon assets

schema/version owners
Omada write/control paths
Traffic
Auth
systemd
Nginx
Alloy
Loki
Grafana
```

---

# 44. Coder Stop Conditions

Coder MUST STOP and return evidence if implementation appears to require:

```text
any DB/schema migration

backfill

stored canonical column

write-path normalization

registry_service.py modification

device_gateway.py modification

read_gateway.py modification

repository modification

source normalizer modification

frontend JS/CSS/template/icon modification

new API version

new API route

feature flag

semantic alias table

cross-field inference

external lookup

new service/worker

different canonical field name

different Unicode normalization policy

different 128-byte bound

new application file outside FINAL boundary
```

No workaround.

---

# 45. Test Node IDs — Helper

Add exactly these tests to:

```text
tests/test_device_type.py
```

Exact node IDs:

```text
tests/test_device_type.py::test_normalize_device_type_key_lexical_matrix

tests/test_device_type.py::test_normalize_device_type_key_rejects_invalid_sources

tests/test_device_type.py::test_normalize_device_type_key_preserves_internal_structure

tests/test_device_type.py::test_normalize_device_type_key_enforces_utf8_byte_bounds

tests/test_device_type.py::test_normalize_device_type_key_does_not_apply_unicode_normalization
```

---

# 46. Helper Test — Lexical Matrix

`test_normalize_device_type_key_lexical_matrix` must cover:

```text
None → None

android → android

Android → android

ANDROID → android

" android " → android

phone → phone

NewVendorThing → newvendorthing
```

---

# 47. Helper Test — Invalid Sources

`test_normalize_device_type_key_rejects_invalid_sources` covers:

```text
empty string

whitespace-only

embedded NUL

non-string int

bool

bytes

dict/list

unpaired surrogate / strict UTF-8 encode failure
```

All:

```text
→ None
```

---

# 48. Helper Test — Internal Structure

`test_normalize_device_type_key_preserves_internal_structure`:

```text
"Smart  Phone"
→ "smart  phone"

"Smart-Phone"
→ "smart-phone"

"Smart_Phone"
→ "smart_phone"

"Smart.Phone/2"
→ "smart.phone/2"
```

No separator collapse.

---

# 49. Helper Test — Byte Bounds

`test_normalize_device_type_key_enforces_utf8_byte_bounds` must prove:

```text
exact 128-byte valid source/key
→ accepted

129-byte trimmed source
→ None

source "\u0130" * 64
(trimmed source == 128 UTF-8 bytes)
casefold output >128 UTF-8 bytes
→ None
```

No truncation.

---

# 50. Helper Test — Explicit No Unicode Normalization

`test_normalize_device_type_key_does_not_apply_unicode_normalization` must include both pairs.

## Canonical-equivalent pair

```python
composed = "É"
decomposed = "E\u0301"
```

Required:

```text
normalize(composed) == "é"

normalize(decomposed) == "e\u0301"

results are NOT equal
```

This proves no NFC/NFD composition step.

## Compatibility-equivalent pair

```python
full_width = "Ａ"
ascii_value = "A"
```

Required:

```text
normalize(full_width) == "ａ"

normalize(ascii_value) == "a"

results are NOT equal
```

This proves no NFKC/NFKD compatibility fold.

---

# 51. Home Current Client Tests

Modify existing strict-shape node:

```text
tests/admin_web/test_home_live.py::test_client_serializers_minimize_and_preserve_zero
```

Its exact item-key assertion must now include:

```text
device_type
device_type_key
```

Add exact new node:

```text
tests/admin_web/test_home_live.py::test_client_serializer_adds_raw_device_type_and_derived_key
```

Required cases:

```text
raw " Android "
→ raw remains " Android "
→ key "android"

raw "phone"
→ key "phone"

raw None
→ key None
```

No inference.

---

# 52. Browser Additive-Property Regression

Modify only test fixture data in:

```text
tests/admin_web/test_admin_ui_frontend.py
```

Do NOT modify JS.

Existing node:

```text
tests/admin_web/test_admin_ui_frontend.py::test_home_live_javascript_validation_freshness_and_retry_contract
```

must include on its synthetic current-client page item:

```text
device_type: " Android "
device_type_key: "android"
```

and continue to PASS.

Purpose:

```text
prove existing browser validator
accepts additive nested fields
under admin.read.v1
```

No browser consumption of `device_type_key` is introduced yet.

---

# 53. Device List Context Tests

Modify existing exact shape node:

```text
tests/admin_web/test_device_list_context_serialization.py::test_device_list_context_serialization_exact_root_overlay_and_item_keys
```

Public item key set gains exactly:

```text
device_type_key
```

Add exact node:

```text
tests/admin_web/test_device_list_context_serialization.py::test_device_list_context_serialization_derives_device_type_key_from_source_only
```

Required:

```text
AdminDeviceListContextRow device_type="Android"
→ raw "Android"
→ key "android"

phone
→ phone

None
→ None

"device_type_key"
NOT IN
AdminDeviceListContextRow.__dataclass_fields__
```

Add exact node:

```text
tests/admin_web/test_device_list_context_serialization.py::test_device_list_context_serialization_rejects_injected_device_type_key
```

Required:

```text
source Mapping with exact baseline fields
→ accepted

same Mapping + device_type_key
→ DeviceListContextSerializationError

contradiction:
device_type="phone"
device_type_key="android"
→ rejected
```

---

# 54. Device Current Context Tests

Add exact node:

```text
tests/admin_web/test_device_current_context.py::test_device_current_serializer_adds_key_from_current_raw_only
```

Required:

```text
current raw " Android "
→ raw preserved
→ key "android"

current raw None
→ key None

contract_version
=
admin.device.current.v1
```

No historical source is supplied/used to fill a missing current key.

Existing serializer/current-context regression nodes remain unchanged unless exact expected shape requires update.

---

# 55. Historical Device DTO Tests

Modify existing node:

```text
tests/admin_web/test_query_service.py::test_device_list_dto_does_not_expose_detail_snapshot
```

Add assertions:

```text
raw device_type remains "phone"

device_type_key == "phone"

latest_snapshot remains absent
```

Add exact node:

```text
tests/admin_web/test_query_service.py::test_device_list_dto_derives_key_without_rewriting_raw_type
```

Use raw:

```text
" Android "
```

Required:

```text
device_type == " Android "
device_type_key == "android"
```

This tests the shared `_device_list_dto()` contract used by historical list/detail identity.

---

# 56. Visitor Registry Read Tests

Add exact node:

```text
tests/visitor_registry/test_device_registry.py::test_registry_read_service_derives_device_type_keys_without_mutating_raw_source
```

Required coverage in one focused test:

```text
get_device_by_id()

get_device_by_mac()

list_devices()

list_device_snapshots()
```

Required semantics:

```text
device summary:
last_known_device_type unchanged
last_known_device_type_key derived

snapshot:
device_type unchanged
device_type_key derived

repository persisted raw values unchanged
```

Include raw nonblank source with visible outer whitespace where fixture path permits, proving Registry source semantics remain raw while read key strips/casefolds.

No direct call to canonical helper inside CLI tests is required.

---

# 57. Registry Write-Path Source Review Regression

No Coder code change to:

```text
app/visitor_registry/registry_service.py
```

No new Coder unit test is mandatory solely for private `_profile_string()`.

Tech Lead official source review must confirm candidate diff does not touch that file and existing semantics remain:

```text
None → None

whitespace-only → None

nonblank → original string unchanged
```

---

# 58. Observation Read Tests

Modify:

```text
tests/observations/test_read_service.py
```

Add exact node:

```text
tests/observations/test_read_service.py::test_client_device_type_key_is_read_time_enrichment_and_immutable
```

Required:

```text
persisted raw device_type="Android"

read:
data["device_type"] == "Android"
data["device_type_key"] == "android"
```

Also prove:

```text
system_name does not override key

connect_device_type does not override key
```

Use a case such as:

```text
system_name="Android"
device_type="phone"
connect_device_type="ap"
```

Required:

```text
key="phone"
```

Keep existing immutability assertion:

```text
ClientObservation.data
cannot be mutated
```

No backfill/write occurs.

---

# 59. Analytics SafeSnapshot Test

Modify:

```text
tests/analytics/test_quality_service.py
```

Add exact node:

```text
tests/analytics/test_quality_service.py::test_safe_snapshot_device_type_key_is_derived_from_raw_source_only
```

Arrange persisted Registry snapshot raw:

```text
device_type=" Android "
```

Call existing:

```text
AnalyticsReadService.get_visit_context()
```

Required:

```text
snapshot.device_type == " Android "

snapshot.device_type_key == "android"
```

Also test:

```text
None → None
```

or use a focused second fixture within the same test if practical.

No other source may influence the key.

---

# 60. Existing Analytics Safe-Snapshot Regression

Run unchanged existing node:

```text
tests/analytics/test_quality_service.py::test_safe_snapshot_contract_omits_raw_json
```

It must remain PASS.

The additive key must not expose:

```text
raw_controller_snapshot_json
client_json
auth_context_json
```

---

# 61. Analytics Read-Only Regression

Run unchanged exact node:

```text
tests/analytics/test_safety_and_performance.py::test_analytics_queries_do_not_change_source_rows_or_versions
```

This is the directly affected read-only/source-preservation regression.

Required:

```text
all source row counts unchanged

all source PRAGMA user_version values unchanged
```

after the Analytics read paths including `get_visit_context()`.

---

# 62. Analytics API/Version Regression

Modify:

```text
tests/analytics/test_api_routes.py
```

Add exact focused node:

```text
tests/analytics/test_api_routes.py::test_device_type_foundation_does_not_change_analytics_api_version
```

Use one existing safe Analytics endpoint.

Required:

```text
HTTP success

payload["api_version"]
==
"analytics.internal.v1"
```

Do NOT add a Device Type endpoint.

Do NOT assert `device_type_key` on an HTTP route that does not expose `SafeSnapshotSummary`.

---

# 63. Coder Exact Test Command 1 — Canonical Helper

Run exactly:

```bash
python -m pytest -q \
  tests/test_device_type.py::test_normalize_device_type_key_lexical_matrix \
  tests/test_device_type.py::test_normalize_device_type_key_rejects_invalid_sources \
  tests/test_device_type.py::test_normalize_device_type_key_preserves_internal_structure \
  tests/test_device_type.py::test_normalize_device_type_key_enforces_utf8_byte_bounds \
  tests/test_device_type.py::test_normalize_device_type_key_does_not_apply_unicode_normalization
```

---

# 64. Coder Exact Test Command 2 — Admin Contracts

Run exactly:

```bash
python -m pytest -q \
  tests/admin_web/test_home_live.py::test_client_serializers_minimize_and_preserve_zero \
  tests/admin_web/test_home_live.py::test_client_serializer_adds_raw_device_type_and_derived_key \
  tests/admin_web/test_device_list_context_serialization.py::test_device_list_context_serialization_exact_root_overlay_and_item_keys \
  tests/admin_web/test_device_list_context_serialization.py::test_device_list_context_serialization_derives_device_type_key_from_source_only \
  tests/admin_web/test_device_list_context_serialization.py::test_device_list_context_serialization_rejects_injected_device_type_key \
  tests/admin_web/test_device_current_context.py::test_device_current_serializer_adds_key_from_current_raw_only \
  tests/admin_web/test_query_service.py::test_device_list_dto_does_not_expose_detail_snapshot \
  tests/admin_web/test_query_service.py::test_device_list_dto_derives_key_without_rewriting_raw_type
```

---

# 65. Coder Exact Test Command 3 — Registry + Observations

Run exactly:

```bash
python -m pytest -q \
  tests/visitor_registry/test_device_registry.py::test_registry_read_service_derives_device_type_keys_without_mutating_raw_source \
  tests/observations/test_read_service.py::test_client_device_type_key_is_read_time_enrichment_and_immutable
```

No Registry CLI-specific canonicalization test is required because CLI is unchanged and consumes the enriched read service.

---

# 66. Coder Exact Test Command 4 — Analytics

Run exactly:

```bash
python -m pytest -q \
  tests/analytics/test_quality_service.py::test_safe_snapshot_device_type_key_is_derived_from_raw_source_only \
  tests/analytics/test_quality_service.py::test_safe_snapshot_contract_omits_raw_json \
  tests/analytics/test_safety_and_performance.py::test_analytics_queries_do_not_change_source_rows_or_versions \
  tests/analytics/test_api_routes.py::test_device_type_foundation_does_not_change_analytics_api_version
```

Do NOT run the entire Analytics test directory merely because Analytics models/read service are touched.

---

# 67. Coder Exact Test Command 5 — Browser Compatibility

Run exactly:

```bash
python -m pytest -q \
  tests/admin_web/test_admin_ui_frontend.py::test_home_live_javascript_validation_freshness_and_retry_contract
```

This is a compatibility regression only.

No frontend implementation file changes are authorized.

If Node is unavailable and the test is skipped, Coder reports:

```text
SKIPPED — Node unavailable
```

and does not claim browser acceptance.

Owner + Tech Lead Central Lab performs the authoritative frontend acceptance.

---

# 68. Coder Exact Static Checks

Run exactly:

```bash
python -m compileall -q \
  app/common/device_type.py \
  app/admin_web/current_state_serialization.py \
  app/admin_web/device_list_context_serialization.py \
  app/admin_web/device_current_context_serialization.py \
  app/admin_web/query_service.py \
  app/visitor_registry/registry_read_service.py \
  app/observations/read_service.py \
  app/analytics/models.py \
  app/analytics/read_service.py
```

Then:

```bash
git diff --check
```

No full repository suite under Coder responsibility.

---

# 69. Coder Forbidden Test Scope

Coder does NOT run/claim:

```text
Central Full Gate

full repository pytest

all Analytics tests

all Admin Web tests

production smoke

production deployment

browser visual acceptance

schema acceptance

production data verification

GitHub CI acceptance

TASK PASS

production ready
```

Those remain Owner + Tech Lead responsibilities.

---

# 70. Coder Implementation Order

After explicit Owner implementation authorization only:

```text
1. Verify exact authorized baseline.

2. Add app/common/device_type.py.

3. Add tests/test_device_type.py
   and pass helper narrow tests.

4. Add read/public enrichments
   only in authorized application files.

5. Update exact focused tests.

6. Run exact commands from this FINAL.

7. Run compileall.

8. Run git diff --check.

9. Return handoff.

10. Do NOT deploy.

11. Do NOT publish GitHub changes
    unless separately authorized.
```

No pre-code PLAN.

---

# 71. Coder Handoff — Required Identity

Return:

```text
TASK =
TASK-DEVICE-TYPE-NORMALIZATION-01

AUTHORIZED BASELINE HEAD =
2d87fd6d56f969492318e21c809086576b2b1ab1

AUTHORIZED BASELINE TREE =
346c7f1f8ad6e91f36fbd572b7c8f6e7a22add11

CANDIDATE HEAD =
<sha or WORKTREE-UNCOMMITTED>

CANDIDATE TREE =
<tree or N/A>
```

---

# 72. Coder Handoff — Changed Files

Return exact:

```text
NEW:
...

MODIFIED:
...

TEST-ONLY MODIFIED:
...

UNEXPECTED:
NONE
```

Any unexpected application file:

```text
STOP CONDITION
```

---

# 73. Coder Handoff — Test Results

For each command from sections 63–68:

```text
COMMAND =
<exact command>

RESULT =
PASS / FAIL / SKIPPED

TEST COUNT =
<count>
```

Also:

```text
compileall = PASS/FAIL

git diff --check = PASS/FAIL
```

No official acceptance claim.

---

# 74. Coder Handoff — Explicit Non-Claims

Must state:

```text
CENTRAL FULL GATE = NOT RUN

FULL REPOSITORY REGRESSION = NOT RUN

PRODUCTION TESTS = NOT RUN

PRODUCTION DEPLOY = NOT RUN

BROWSER VISUAL ACCEPTANCE = NOT RUN

OFFICIAL SCHEMA ACCEPTANCE = NOT CLAIMED

OFFICIAL API COMPATIBILITY ACCEPTANCE = NOT CLAIMED

TASK PASS = NOT CLAIMED
```

---

# 75. Owner + Tech Lead Official Acceptance — Source Review

After Coder handoff, independently verify:

```text
app/common/device_type.py
is the only canonical normalization owner

all approved consumers import that helper

no second alias map

no frontend normalization change

no write-path canonicalization

no DB migration/backfill

no new key stored
```

---

# 76. Owner + Tech Lead Official Acceptance — File Boundary

Verify application diff contains only:

```text
app/common/device_type.py

app/admin_web/current_state_serialization.py
app/admin_web/device_list_context_serialization.py
app/admin_web/device_current_context_serialization.py
app/admin_web/query_service.py
app/visitor_registry/registry_read_service.py
app/observations/read_service.py
app/analytics/models.py
app/analytics/read_service.py
```

plus approved test files.

Explicitly verify unchanged:

```text
app/visitor_registry/registry_service.py
app/visitor_registry/cli.py
app/admin_web/device_gateway.py
app/admin_web/read_gateway.py
all repositories
all source normalizers
admin.js
CSS/templates/icons
```

---

# 77. Owner + Tech Lead Official Acceptance — Registry Write Semantics

Source review must reconfirm unchanged:

```text
_profile_string(None)
→ None

_profile_string(whitespace-only)
→ None

_profile_string(nonblank)
→ original string unchanged
```

and:

```text
device_type
continues passing through _profile_string()
```

No trim/casefold in Registry write path.

---

# 78. Owner + Tech Lead Official Acceptance — Schema

Verify unchanged schema signatures / versions for:

```text
Current State

Observations

Visitor Registry
```

No:

```text
new column
new index
migration
backfill
```

Analytics remains read-only over existing source schema.

---

# 79. Owner + Tech Lead Official Acceptance — API Versions

Frozen versions must remain:

```text
admin.read.v1

admin.device.current.v1

analytics.internal.v1
```

No v2.

No new Analytics route.

---

# 80. Owner + Tech Lead Official Acceptance — Cross-Surface Semantics

Prove same lexical source interpretation across approved surfaces.

Example:

```text
Current State raw:
" ANDROID "

Registry raw:
"Android"

Observation raw:
"android"

Historical Admin raw:
"ANDROID"

Analytics raw:
" Android "
```

Required key on each:

```text
android
```

while raw fields remain exactly domain-correct.

---

# 81. Owner + Tech Lead Official Acceptance — No Inference

Use a deliberate contradiction fixture:

```text
device_type="phone"

system_name="Android"

connect_device_type="ap"

hostname="Samsung-Android"

vendor-like evidence present
```

Required everywhere:

```text
device_type_key="phone"
```

No inferred Android classification.

---

# 82. Owner + Tech Lead Official Acceptance — Historical No Backfill

Seed/use rows written before candidate read code.

Without DB update:

```text
Registry read
Observation read
Historical Device read
Analytics snapshot read
```

must derive keys immediately.

Prove database rows were not rewritten.

---

# 83. Owner + Tech Lead Official Acceptance — Home Browser

Run authoritative frontend test environment and confirm:

```text
admin.read.v1
current client page with additive:
device_type
device_type_key
is accepted

Home table remains visually unchanged

no Type column

no new icon

existing Android presentation still works
```

No production JS change in this task.

---

# 84. Owner + Tech Lead Official Acceptance — Device Current

Verify:

```text
raw current client.device_type unchanged

device_type_key derived only from current raw

raw None
→ key None

no historical fallback

contract_version =
admin.device.current.v1
```

---

# 85. Owner + Tech Lead Official Acceptance — Device List Context

Verify:

```text
AdminDeviceListContextRow
has no device_type_key

gateway raw/source shape unchanged

Mapping source with injected key rejected

public item contains exactly one derived key

phone/android contradiction cannot be injected
```

This is a mandatory FIX-1 regression gate.

---

# 86. Owner + Tech Lead Official Acceptance — Registry CLI

No CLI code change.

Verify structurally:

```text
list
show
snapshots
```

still use:

```text
VisitorRegistryReadService
```

and therefore receive enriched read-service output.

No duplicate helper inside CLI.

---

# 87. Owner + Tech Lead Official Acceptance — Analytics

Verify:

```text
SafeSnapshotSummary.device_type
unchanged

SafeSnapshotSummary.device_type_key
additive

only constructor owner:
AnalyticsReadService._snapshot()

source:
row["device_type"] only

get_visit_context read remains source-preserving

analytics.internal.v1 unchanged

no new Device Type HTTP endpoint
```

---

# 88. Performance

Canonical helper is:

```text
O(length of one source string)
```

with source/key bounded at 128 UTF-8 bytes.

No extra query.

No network call.

No population scan.

No new cache.

No new worker.

No capacity benchmark is required solely for this helper.

---

# 89. Security / Privacy

No additional collection.

No fingerprinting.

No external enrichment.

No secret use.

No raw payload expansion.

No change to auth/security behavior.

---

# 90. Deployment

After Owner + Tech Lead official acceptance only.

Normal artifact-coherent CaptivPortal deployment.

No data migration.

No repair.

No backfill.

No special worker lifecycle.

Application restart loads the new read-time fields.

---

# 91. Rollback

Code-only rollback.

Because persisted source data is unchanged:

```text
NO DB restore

NO reverse migration

NO key cleanup

NO backfill reversal
```

Older artifact simply stops exposing the additive derived keys.

---

# 92. Explicit Non-Goals

Not part of this task:

```text
Home Type column

frontend use of device_type_key

removal of isAndroidDeviceType()

new icons

display capitalization

semantic device class

phone→android mapping

MAC/OUI/vendor inference

hostname inference

system_name inference

connect_device_type inference

DHCP fingerprinting

User-Agent inference

confidence score

Registry normalized filtering

Admin direct Observation gateway expansion

DB canonical column

schema migration

backfill

feature flag
```

---

# 93. Follow-Up Task

After foundation PASS:

```text
TASK-WEB-DEVICE-TYPE-CONSUMERS-01
— Canonical Device Type Presentation Adoption
```

Expected future consumer semantics:

```text
device_type
→ visible source text

device_type_key
→ machine/icon matching
```

No such frontend migration is authorized by this FINAL.

---

# 94. Implementation Summary

```text
TASK =
TASK-DEVICE-TYPE-NORMALIZATION-01

ARCHITECTURE =
READ-TIME ADDITIVE

CANONICAL OWNER =
app/common/device_type.py

FUNCTION =
normalize_device_type_key(source_value)

RAW SOURCE =
PRESERVED

KEY =
device_type_key

REGISTRY SUMMARY KEY =
last_known_device_type_key

NORMALIZATION =
strip
+
Unicode casefold

UNICODE COMPOSITION/NFKC =
NO

MAX TRIMMED SOURCE =
128 UTF-8 bytes

MAX KEY =
128 UTF-8 bytes

MALFORMED / NONSTRING / NUL / INVALID UTF8 / OVERBOUND =
None

UNKNOWN VALID TYPE =
LEXICAL VALUE

ALIASES =
NO

INFERENCE =
NO

DB MIGRATION =
NO

BACKFILL =
NO

STORED KEY =
NO

FEATURE FLAG =
NO

HOME =
backend fields only
no UI Type column

DEVICE LIST CONTEXT =
source/public key sets separated

UPSTREAM KEY INJECTION =
REJECTED

DEVICE GATEWAY =
NO-TOUCH

ADMIN DIRECT OBSERVATION GATEWAY =
NO-TOUCH

REGISTRY WRITE SERVICE =
NO-TOUCH

REGISTRY CLI =
CONSUMER ONLY / NO-TOUCH

OBSERVATION WRITE PATH =
NO-TOUCH

ANALYTICS CONSTRUCTOR OWNER =
AnalyticsReadService._snapshot()

API VERSIONS =
admin.read.v1 KEEP
admin.device.current.v1 KEEP
analytics.internal.v1 KEEP

FRONTEND IMPLEMENTATION =
NO-TOUCH

CODER =
HOLD

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED
```

---

# 95. Authorization Boundary

This FINAL authorizes only:

```text
Tech Lead / Owner final review
```

It does NOT authorize:

```text
Coder implementation

branch creation

commit

push

PR

merge

deployment
```

Implementation begins only after explicit Owner instruction for this FINAL.

---

# 96. Next Workflow

```text
TASK-DEVICE-TYPE-NORMALIZATION-01-FINAL
        ↓
Tech Lead FINAL review
        ↓
Owner FINAL review
        ↓
Owner explicit implementation authorization
        ↓
Coder implements exact FINAL
        ↓
Coder narrow tests only
        ↓
Coder handoff
        ↓
Owner + Tech Lead official acceptance
        ↓
controlled normal deployment
        ↓
foundation PASS
        ↓
TASK-WEB-DEVICE-TYPE-CONSUMERS-01
```

**End of FINAL.**
