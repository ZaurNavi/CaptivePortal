# TASK-DEVICE-LIST-CONTEXT-01 — IMPLEMENTATION SPEC DRAFT

**Project:** CaptivPortal  
**Architecture source:** `TASK-DEVICE-LIST-CONTEXT-01 — FINAL-R2`  
**Architecture status:** `FINAL / TECH LEAD FINAL ACCEPTANCE=PASS`  
**Deliverable type:** Architect implementation-spec draft for Tech Lead repository rebind and FINAL CODER TASK  
**Status:** `IMPLEMENTATION SPEC DRAFT — FOR TECH LEAD REBIND / HARDENING`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Coder PLAN:** `FORBIDDEN / NOT REQUIRED`  
**Coder design/proposal/spike:** `FORBIDDEN`  
**GitHub write:** `HOLD`  
**Production:** `UNTOUCHED`  
**TASK-WEB-DEVICE-UI-01:** `FROZEN`  
**Prepared:** 2026-09-09

---

# 0. Owner workflow rule — mandatory from this TASK forward

Permanent project model:

```text
ARCHITECT + TECH LEAD DESIGN
CODER WRITES CODE
OWNER + TECH LEAD ACCEPT
```

Coder is not:

```text
Architect
Tech Lead
Solution Designer
Task Planner
Architecture Reviewer
Acceptance Engineer
Performance Engineer
Browser Tester
```

There is no Coder PLAN stage.

After separate Owner implementation authorization:

```text
Coder receives exact FINAL CODER TASK
→ writes code
→ runs only narrowly targeted implementation tests
→ returns handoff
```

If the exact TASK contradicts the repository, Coder:

```text
STOP
→ return exact contradiction evidence only
```

Coder does not design a workaround.

---

# 1. Baseline for this Architect draft

This implementation-spec draft is prepared against the accepted architecture baseline:

```text
repository main =
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

tree =
edb5bab5479a4417d545429eeacf2b29a640e441
```

Current deployed application baseline remains:

```text
SHA =
7df71a8e807efd74b123117e78cb8d992c190fa1

CODE TREE =
8f1342f0a0f1e8242642161e02b2f3276e6ddf51
```

PR #109 is docs-only.

Tech Lead must perform a fresh repository rebind before producing the FINAL CODER TASK.

This draft itself does not authorize code.

---

# 2. Exact product change

Existing endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/devices
```

Existing query parameters remain:

```text
limit
cursor
mac
```

Existing capability remains:

```text
admin.read.devices
```

Feature OFF:

```text
exact existing historical Devices behavior
```

Feature ON adds:

```text
hostname
current_presence
current_state_overlay

server-side Online-first ordering
dedicated integrity-protected context cursor
```

No new public endpoint.

---

# 3. Component responsibility matrix

The implementation is divided exactly as follows.

## `CurrentStateReadService`

Owns:

```text
Current client inventory semantic context selection
freshness evaluation
scope validation
trusted vs unknown decision
trusted pinned-cycle revalidation
```

Does NOT own:

```text
Devices membership
Devices SQL ordering
Devices pagination
cursor signing
Admin DTO
```

## `AdminDeviceReadGateway`

Owns:

```text
historical Device membership projection
requested-Site latest Snapshot hostname
set-based Current membership composition
same-transaction pinned-cycle structural proof
current_presence assignment from supplied overlay mode
Online-first SQL ordering
keyset continuation
```

Does NOT own:

```text
latest Current cycle selection
freshness policy
scope trust policy
trusted/unknown semantic decision
cursor cryptography
```

## `AdminQueryService`

Owns:

```text
admin.read.devices authorization
Feature OFF / Feature ON branch
one evaluated_at on initial request
cursor decode/validation
CurrentStateReadService calls
initial Current fail-open orchestration
continuation error mapping
gateway call orchestration
root overlay chain metadata selection
next cursor creation
AdminQueryResponse
```

## Admin runtime

Owns:

```text
feature config composition
cursor secret validation/config state
cursor codec construction
Current State DB path injection into AdminDeviceReadGateway
context feature active/disabled/unavailable state
```

## Dedicated Device List Context serializer

Owns:

```text
strict enriched item DTO
strict current_state_overlay DTO
enum/null/type validation
no source internals leakage
```

Does NOT query or calculate semantics.

## Dedicated Device List Context cursor codec

Owns:

```text
canonical payload
HMAC authentication
encode
decode
canonicality
length
integrity verification
transport validation
```

Does NOT decide Current semantic trust.

---

# 4. Exact new Current State model

Add in:

```text
app/current_state/read_service.py
```

the frozen dataclass:

```python
@dataclass(frozen=True, slots=True)
class CurrentClientInventoryContext:
    site_id: str
    evaluated_at_utc: str
    overlay_mode: str
    snapshot: CurrentSnapshotMeta
    current_cycle_id: str | None
    source_scope_hash: str | None
```

Allowed `overlay_mode`:

```text
trusted
unknown
```

Invariant:

```text
overlay_mode=trusted
→ current_cycle_id != null
→ source_scope_hash != null
→ snapshot.complete=true
→ snapshot.freshness_status=fresh

overlay_mode=unknown
→ current_cycle_id=null
→ source_scope_hash=null
```

No Device rows are stored in this model.

---

# 5. Exact pinned-context expiration exception

Add in:

```text
app/current_state/read_service.py
```

the frozen exception:

```python
class CurrentClientInventoryContextExpired(CurrentStateValidationError):
    pass
```

Meaning:

```text
a server-issued trusted inventory context
can no longer be safely resolved against the current configured scope/storage
```

It is used only for trusted pinned continuation validation.

It is not used for initial semantic stale/unavailable state.

---

# 6. Exact new Current State method

Add exactly:

```python
CurrentStateReadService.get_current_client_inventory_context(
    site_id,
    *,
    evaluated_at_utc=None,
    current_cycle_id=None,
    expected_source_scope_hash=None,
) -> CurrentClientInventoryContext
```

No alternate public method is part of this TASK.

---

# 7. Current inventory-context call modes

The method has exactly two call modes.

## Initial mode

Input:

```text
current_cycle_id=None
expected_source_scope_hash=None
```

Behavior:

```text
resolve requested Site
resolve canonical configured client scope
select accepted latest complete-success client cycle
construct CurrentSnapshotMeta at evaluated_at_utc
validate scope json/hash/version
evaluate freshness
```

Return:

### trusted

Only if:

```text
selected cycle exists
result=success
complete=true
freshness_status=fresh
scope_type=client_ssid_allowlist
scope Site matches
source_scope_hash matches configured canonical scope
source_scope_json matches configured canonical scope
source_scope_version=1
```

Return:

```text
overlay_mode=trusted
current_cycle_id=selected cycle
source_scope_hash=configured hash
```

### unknown

For safe semantic states:

```text
no complete snapshot
stale
unavailable
clock anomaly
invalid timestamp
untrusted scope
invalid source scope safely represented
```

Return:

```text
overlay_mode=unknown
current_cycle_id=null
source_scope_hash=null
```

No exception solely because evidence is stale/unavailable.

---

# 8. Trusted continuation mode

Input is mandatory:

```text
current_cycle_id=<server-issued pinned cycle>
expected_source_scope_hash=<server-issued pinned hash>
evaluated_at_utc=<server-issued pinned T>
```

Rules:

```text
current_cycle_id and expected_source_scope_hash
must either both be provided or both be null
```

For trusted continuation both are provided.

The method must:

```text
resolve current configured canonical client scope
require configured scope hash == expected_source_scope_hash

select exact:
cycle_id=current_cycle_id
site_id=requested site
kind=client
result=success
complete=1
source_scope_hash=expected_source_scope_hash

construct CurrentSnapshotMeta at the pinned evaluated_at_utc
validate scope json/version
require snapshot freshness_status=fresh at pinned T
```

Success:

```text
overlay_mode=trusted
same current_cycle_id
same source_scope_hash
```

Failure because the pinned semantic context no longer exists or is incompatible:

```text
raise CurrentClientInventoryContextExpired
```

Examples:

```text
cycle retention-deleted
cycle missing
configured scope hash changed
scope json/version incompatible
cycle structurally no longer matches
```

Storage/schema execution errors remain their existing Current State exceptions and are not converted to expiration.

---

# 9. Unknown continuation does NOT call CurrentStateReadService

For a validated server-issued cursor whose:

```text
overlay_mode=unknown
```

`AdminQueryService.list_devices()` MUST NOT call:

```text
get_current_client_inventory_context()
list_current_clients()
get_current_client()
```

on continuation.

It reuses the integrity-protected chain metadata from page 1.

Reason:

```text
unknown cursor chain is pinned to historical ordering
new Current evidence is not allowed to become ordering authority mid-chain
```

---

# 10. `list_current_clients()` is forbidden for list Presence

Permanent implementation rule:

```text
CurrentStateReadService.list_current_clients(...)
MUST NOT be used
to decide TASK-DEVICE-LIST-CONTEXT-01 Presence
```

Also forbidden:

```text
N × get_current_client()
```

The new narrow inventory-context descriptor is the semantic boundary.

---

# 11. Exact gateway constructor extension

Change:

```python
AdminDeviceReadGateway(
    registry_db_path,
    visit_db_path,
)
```

to accept one optional third source path:

```python
AdminDeviceReadGateway(
    registry_db_path,
    visit_db_path,
    current_state_db_path=None,
)
```

Store:

```text
_registry_path
_visit_path
_current_state_path
```

Existing:

```text
list_devices()
get_device()
```

must not attach/read `_current_state_path`.

---

# 12. Existing gateway path must remain direct

Existing:

```python
AdminDeviceReadGateway.list_devices(...)
```

remains the Feature OFF historical path.

Its contract remains:

```text
historical membership
historical ordering:
site_last_seen_at DESC
device_id DESC

existing AdminDeviceRow
existing AdminDevicePage
```

No Current composition.

Existing `get_device()` remains unchanged semantically.

---

# 13. Exact new gateway models

Add in:

```text
app/admin_web/device_gateway.py
```

the frozen models:

```python
@dataclass(frozen=True, slots=True)
class AdminDeviceListContextRow:
    device_id: str
    canonical_mac: str
    hostname: str | None
    device_type: str | None
    site_first_seen_at: str
    site_last_seen_at: str
    site_snapshot_count: int
    site_visit_count: int
    last_site_ip: str | None
    last_site_ssid: str | None
    last_site_ap_mac: str | None
    current_presence: str
    online_rank: int
```

Allowed `current_presence`:

```text
online
offline
unknown
```

Allowed `online_rank`:

```text
0
1
```

`online_rank` is internal pagination state and is not emitted in the public item DTO.

Also add:

```python
@dataclass(frozen=True, slots=True)
class AdminDeviceListContextPage:
    items: tuple[AdminDeviceListContextRow, ...]
    has_more: bool
```

---

# 14. Exact gateway context-expired exception

Add:

```python
class AdminDeviceContextExpired(AdminDeviceSourceError):
    pass
```

Meaning:

```text
the already-selected trusted pinned cycle
cannot be structurally proven in the exact Current DB read snapshot
used for membership composition
```

It is not a general SQLite/source error.

---

# 15. Exact new gateway method

Add exactly:

```python
AdminDeviceReadGateway.list_devices_context(
    *,
    site_id,
    limit,
    deadline,
    overlay_mode,
    current_cycle_id,
    source_scope_hash,
    cursor,
    canonical_mac=None,
) -> AdminDeviceListContextPage
```

`cursor` exact internal value:

```text
None
or
tuple[int, str, str]
=
(online_rank, site_last_seen_at, device_id)
```

Rules:

```text
trusted
→ current_cycle_id required
→ source_scope_hash required
→ current_state_db_path required

unknown
→ current_cycle_id must be null
→ source_scope_hash must be null
```

---

# 16. Unknown gateway path

For:

```text
overlay_mode=unknown
```

`list_devices_context()` must not attach/read Current State DB.

It must use the existing historical query behavior and ordering:

```text
site_last_seen_at DESC
device_id DESC
```

Each returned row becomes:

```text
hostname =
latest requested-Site snapshot hostname
or null

current_presence=unknown
online_rank=1
```

Context cursor position:

```text
(1, site_last_seen_at, device_id)
```

No Current lookup.

---

# 17. Trusted gateway DB transaction

For:

```text
overlay_mode=trusted
```

open one read-only SQLite connection/transaction containing:

```text
Registry DB
Visit DB
Current State DB
```

The transaction must:

```text
BEGIN
verify expected schema versions
set query_only
use existing QueryDeadline progress handler
```

All Current cycle structural proof and MAC membership composition occur inside this same transaction/snapshot.

---

# 18. Same-transaction pinned-cycle structural proof

Before interpreting MAC absence, the trusted gateway path must query in the same transaction:

```text
current_state_cycles
```

for exactly:

```text
cycle_id = current_cycle_id
site_id = site_id
kind = 'client'
result = 'success'
complete = 1
source_scope_hash = source_scope_hash
```

If no exact row:

```text
raise AdminDeviceContextExpired
```

Only after this guard succeeds may a missing:

```text
current_client_state
```

row mean `offline`.

This is mandatory TOCTOU protection.

---

# 19. Trusted set-based Device composition

After the structural guard succeeds, compose the historical Device inventory with:

```text
current_client_state
```

using:

```text
pinned current_cycle_id
requested site_id
historical canonical_mac = current client_mac
```

Do not select a Current cycle inside the gateway.

Do not calculate freshness inside the gateway.

Presence assignment:

```text
matching current_client_state row
→ current_presence=online
→ online_rank=0

no matching row
→ current_presence=offline
→ online_rank=1
```

because exact pinned cycle existence/coherence was already proven in the same transaction.

---

# 20. Trusted ordering

Exact ordering:

```text
online_rank ASC
site_last_seen_at DESC
device_id DESC
```

Apply:

```text
MAC filter
keyset continuation predicate
ORDER BY
LIMIT limit+1
```

inside the set-based SQL before constructing Python rows.

No full historical Python materialization.

No page-local re-sort.

---

# 21. Trusted keyset continuation predicate

For a non-null cursor:

```text
(cursor_rank, cursor_at, cursor_device_id)
```

return rows strictly after that key in:

```text
online_rank ASC
site_last_seen_at DESC
device_id DESC
```

Exact logical predicate:

```text
online_rank > cursor_rank

OR

(
  online_rank = cursor_rank
  AND site_last_seen_at < cursor_at
)

OR

(
  online_rank = cursor_rank
  AND site_last_seen_at = cursor_at
  AND device_id < cursor_device_id
)
```

No OFFSET.

---

# 22. Hostname source

For both trusted and unknown context paths:

```text
hostname =
latest requested-Site Snapshot hostname
```

No fallback:

```text
name
system_name
MAC
```

If absent:

```text
hostname=null
```

No new source.

---

# 23. Initial selector→gateway race behavior

Initial request may do:

```text
CurrentStateReadService
→ trusted A

then retention removes A

then gateway starts
```

If gateway raises:

```text
AdminDeviceContextExpired
```

`AdminQueryService` must:

```text
require remaining deadline
rerun historical/context unknown path
return HTTP 200
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
current_presence=unknown
```

No trusted cursor is emitted.

No false Offline.

---

# 24. Initial context-source execution failure

If initial Current selector or trusted context gateway fails with a Current/source execution error, while the Admin deadline still permits historical list work:

```text
fallback to unknown/historical context list
```

Root:

```text
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
snapshot=null if no safe semantic snapshot exists
all current_presence=unknown
```

If historical fallback also fails:

```text
AdminQueryUnavailable
```

If Admin deadline is exhausted:

```text
AdminQueryDeadline
```

---

# 25. Dedicated configuration module

Create:

```text
app/admin_web/device_list_context_config.py
```

with:

```python
class DeviceListContextConfigError(ValueError):
    pass
```

and:

```python
@dataclass(frozen=True, slots=True, repr=False)
class DeviceListContextConfig:
    enabled: bool
    cursor_secret: bytes
```

`__repr__` must never expose the secret.

Add exact parser:

```python
device_list_context_config_from_settings(
    settings,
    *,
    admin_config,
) -> DeviceListContextConfig
```

---

# 26. Exact feature flag configuration

Add:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED
```

Repository default:

```text
false
```

`app/config.py`:

```text
os.getenv("WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED", "false")
```

`app/settings.py` mapping:

```text
web_admin_device_list_context_enabled
```

`AdminWebConfig` field:

```text
device_list_context_enabled: bool
```

Validation:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
```

No dependency on:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
WEB_ADMIN_TRAFFIC_ENABLED
```

---

# 27. Exact cursor secret configuration

Add server-only environment variable:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
```

Repository default:

```text
empty string
```

`app/settings.py` mapping:

```text
web_admin_device_list_context_cursor_secret
```

`.env.example`:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET=
```

The secret is not logged and not exposed in repr/API/UI.

---

# 28. Exact cursor secret format

When feature is enabled:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
```

must be exactly:

```text
64 lowercase hexadecimal characters
```

Regex:

```text
[0-9a-f]{64}
```

Decode with:

```text
bytes.fromhex(...)
```

Result:

```text
exactly 32 secret bytes
```

No uppercase normalization.

No autogenerated secret.

No password-hash reuse.

No session-token reuse.

No fallback secret.

Changing the secret invalidates all outstanding context cursors.

No multi-key rotation support in v1.

---

# 29. Invalid/missing cursor secret behavior

When:

```text
feature=false
```

secret may be empty and is not validated.

When:

```text
feature=true
```

missing/invalid secret:

```text
DeviceListContextConfigError
```

Runtime behavior:

```text
base Admin runtime remains active
existing Device Detail remains active
device_list_context_state=unavailable
no cursor codec
```

A `GET /devices` request while the feature flag is ON but context runtime state is unavailable returns:

```text
503
source_unavailable
```

It must not silently return a Feature ON response without integrity protection.

Feature OFF remains unaffected.

---

# 30. Dedicated cursor module

Create:

```text
app/admin_web/device_list_context_cursor.py
```

Imports from existing cursor module only for:

```text
filter_fingerprint
```

Do NOT modify:

```text
app/admin_web/cursors.py
```

---

# 31. Exact cursor cryptographic contract

Use:

```text
HMAC-SHA-256
```

Primitive:

```python
hmac.new(secret_key, canonical_payload_bytes, hashlib.sha256).digest()
```

Verification:

```python
hmac.compare_digest(expected_digest, supplied_digest)
```

Digest size:

```text
32 bytes
```

No truncation.

---

# 32. Exact cursor wire format

Token format:

```text
<base64url-no-padding(canonical JSON payload bytes)>
.
<base64url-no-padding(32-byte HMAC-SHA256 digest)>
```

Exactly one ASCII period separator.

No `=` padding in emitted token.

Payload serialization:

```python
json.dumps(
    payload,
    ensure_ascii=True,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("ascii")
```

Maximum complete token length:

```text
AdminWebConfig.max_cursor_chars
```

Existing repository default:

```text
4096
```

No new cursor-length setting.

---

# 33. Exact cursor payload — field set

Payload must have exactly these keys:

```text
version
kind
site_id
filter_fingerprint
ordering_contract_version

overlay_mode
evaluated_at_utc

source_execution_status
scope
snapshot

current_cycle_id
source_scope_hash

last_online_rank
last_site_last_seen_at
last_device_id
```

No additional keys.

---

# 34. Exact cursor payload — constants

```text
version = 1
kind = "devices_context"
ordering_contract_version = 1
```

`overlay_mode`:

```text
trusted
unknown
```

`source_execution_status`:

```text
available
unavailable
```

`last_online_rank`:

```text
0
1
```

---

# 35. Exact cursor payload — identity/position fields

```text
site_id:
canonical 24 lowercase hex Site ID

filter_fingerprint:
64 lowercase hex SHA-256
of current list filters
using existing filter_fingerprint()

evaluated_at_utc:
canonical UTC timestamp
YYYY-MM-DDTHH:MM:SS.mmmZ

last_site_last_seen_at:
canonical UTC timestamp
YYYY-MM-DDTHH:MM:SS.mmmZ

last_device_id:
canonical lowercase UUID string
```

`current_cycle_id`:

```text
trusted → non-empty string length <=128
unknown → null
```

`source_scope_hash`:

```text
trusted → exactly 64 lowercase hex
unknown → null
```

---

# 36. Exact cursor `scope` field

`scope` is:

```text
object | null
```

When available:

```json
{
  "scope_type": "client_ssid_allowlist",
  "site_id": "<canonical site_id>",
  "ssids": ["<configured SSID>", "..."]
}
```

Exact keys:

```text
scope_type
site_id
ssids
```

`ssids` preserves the page-1 canonical Current State scope order/value.

If Current service/config is unavailable before page-1 semantic context can be constructed:

```text
scope=null
```

---

# 37. Exact cursor `snapshot` field

`snapshot` is:

```text
object | null
```

When present, exact keys:

```text
observed_at
capture_finished_at
age_seconds
freshness_status
freshness_reason
complete
```

Types:

```text
observed_at: canonical UTC string | null
capture_finished_at: canonical UTC string | null
age_seconds: finite non-negative number | null
freshness_status: fresh | stale | unavailable
freshness_reason: existing Current State reason string
complete: boolean
```

No cycle ID in public snapshot metadata.

No source_scope_hash in public snapshot metadata.

For initial Current execution failure without safe semantic snapshot:

```text
snapshot=null
```

---

# 38. Trusted cursor field invariants

For:

```text
overlay_mode=trusted
```

required:

```text
source_execution_status=available
scope != null
snapshot != null
snapshot.freshness_status=fresh
snapshot.complete=true
current_cycle_id != null
source_scope_hash != null
```

`last_online_rank` may be:

```text
0 or 1
```

depending on page position.

---

# 39. Unknown cursor field invariants

For:

```text
overlay_mode=unknown
```

required:

```text
current_cycle_id=null
source_scope_hash=null
last_online_rank=1
```

If semantic Current evidence was safely read:

```text
source_execution_status=available
snapshot may be stale/unavailable/etc.
```

If Current source execution failed:

```text
source_execution_status=unavailable
snapshot=null unless a safe page-1 semantic snapshot had already been constructed
```

Unknown chain does not become trusted on continuation.

---

# 40. Cursor codec classes

Add exactly:

```python
class DeviceListContextCursorError(ValueError):
    pass
```

and:

```python
@dataclass(frozen=True, slots=True)
class DeviceListContextCursor:
    version: int
    kind: str
    site_id: str
    filter_fingerprint: str
    ordering_contract_version: int
    overlay_mode: str
    evaluated_at_utc: str
    source_execution_status: str
    scope: dict | None
    snapshot: dict | None
    current_cycle_id: str | None
    source_scope_hash: str | None
    last_online_rank: int
    last_site_last_seen_at: str
    last_device_id: str
```

Add:

```python
class DeviceListContextCursorCodec:
    def __init__(self, *, secret_key: bytes, maximum_length: int): ...
    def encode(self, value: DeviceListContextCursor) -> str: ...
    def decode(
        self,
        value,
        *,
        site_id,
        filters,
    ) -> DeviceListContextCursor | None: ...
```

---

# 41. Cursor decode validation order

`decode()` must perform validation in this order:

```text
1. None → return None.

2. Require str, non-empty,
   len <= maximum_length.

3. Require exactly one "." separator
   and two non-empty segments.

4. Base64url-decode both segments
   with strict alphabet validation.

5. Require supplied signature length = 32 bytes.

6. Compute HMAC-SHA256 over raw payload bytes.

7. hmac.compare_digest().
   If mismatch → DeviceListContextCursorError.

8. Decode payload bytes as ASCII JSON.

9. Require dict with exact field set.

10. Validate all field types/enums/formats/invariants.

11. Require:
    version=1
    kind=devices_context
    site_id=requested site
    filter_fingerprint=existing filter_fingerprint(filters)
    ordering_contract_version=1

12. Re-serialize the parsed payload canonically,
    require raw payload bytes exactly equal canonical bytes.

13. Re-encode both canonical payload and signature
    with no padding and require exact token equality.

14. Return DeviceListContextCursor.
```

No semantic Current read occurs before steps 1–13 succeed.

---

# 42. Cursor decode error mapping

Any:

```text
malformed
non-canonical
integrity-invalid
wrong Site
wrong filter fingerprint
wrong kind
wrong version
wrong ordering contract
bad field type
bad field invariant
oversize cursor
```

raises:

```text
DeviceListContextCursorError
```

`AdminQueryService` maps it to:

```text
AdminQueryValidationError
→ HTTP 400
→ invalid_request
```

Never:

```text
cursor_expired
source_unavailable
```

---

# 43. Server-generated cursor overflow

If `encode()` would produce a token longer than:

```text
maximum_length
```

raise:

```text
DeviceListContextCursorError
```

`AdminQueryService` MUST map server-side encode failure to:

```text
AdminQueryUnavailable
→ HTTP 503 source_unavailable
```

It must not return a page with a missing/truncated continuation cursor when `has_more=true`.

---

# 44. Exact filter fingerprint input

Existing list filter state for context cursor:

```python
filters = {} if selected_mac is None else {"mac": selected_mac}
```

Use existing:

```text
filter_fingerprint(filters)
```

No `limit` in filter fingerprint.

No feature flag in filter fingerprint.

Site is a separate signed field.

---

# 45. Dedicated serializer module

Create:

```text
app/admin_web/device_list_context_serialization.py
```

Add exact exception:

```python
class DeviceListContextSerializationError(ValueError):
    pass
```

Add exact function:

```python
serialize_device_list_context(
    *,
    items,
    overlay,
) -> dict
```

No source reads.

No cursor encoding.

---

# 46. Exact Feature ON item DTO

Each public item has exactly:

```text
device_id
canonical_mac
hostname
device_type
site_first_seen_at
site_last_seen_at
site_snapshot_count
site_visit_count
last_site_ip
last_site_ssid
last_site_ap_mac
current_presence
```

Types:

```text
device_id: canonical UUID string
canonical_mac: canonical colon MAC
hostname: string | null
device_type: string | null

site_first_seen_at: canonical timestamp string
site_last_seen_at: canonical timestamp string

site_snapshot_count: integer >=0
site_visit_count: integer >=0

last_site_ip: string | null
last_site_ssid: string | null
last_site_ap_mac: canonical MAC | null

current_presence:
online | offline | unknown
```

No:

```text
latest_snapshot
online_rank
current_cycle_id
source_scope_hash
```

in item DTO.

---

# 47. Exact root overlay DTO

Feature ON result exact shape:

```json
{
  "items": [],
  "current_state_overlay": {
    "overlay_mode": "trusted",
    "ordering_applied": true,
    "source_execution_status": "available",
    "evaluated_at_utc": "2026-09-09T12:00:00.000Z",
    "scope": {
      "scope_type": "client_ssid_allowlist",
      "site_id": "0123456789abcdef01234567",
      "ssids": ["Zefer_Parki"]
    },
    "snapshot": {
      "observed_at": "2026-09-09T11:59:50.000Z",
      "capture_finished_at": "2026-09-09T11:59:55.000Z",
      "age_seconds": 10.0,
      "freshness_status": "fresh",
      "freshness_reason": "within_freshness_window",
      "complete": true
    }
  }
}
```

Exact root keys:

```text
items
current_state_overlay
```

Exact overlay keys:

```text
overlay_mode
ordering_applied
source_execution_status
evaluated_at_utc
scope
snapshot
```

---

# 48. Root overlay invariants

```text
overlay_mode=trusted
→ ordering_applied=true
→ source_execution_status=available
→ scope != null
→ snapshot != null
→ snapshot.freshness_status=fresh
→ snapshot.complete=true
```

```text
overlay_mode=unknown
→ ordering_applied=false
```

For initial semantic unknown:

```text
source_execution_status=available
```

For initial execution failure:

```text
source_execution_status=unavailable
```

No public:

```text
current_cycle_id
source_scope_hash
```

---

# 49. Existing page envelope

Continue returning existing Admin page metadata:

```json
{
  "limit": 100,
  "next_cursor": "<string-or-null>"
}
```

Feature OFF uses old generic cursor.

Feature ON uses the new context cursor.

No extra page fields.

---

# 50. Feature OFF DTO — exact preservation

When:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
```

`AdminQueryService.list_devices()` must execute the existing code path:

```text
decode existing generic kind=devices cursor
AdminDeviceReadGateway.list_devices()
_device_list_dto()
encode existing generic kind=devices cursor
```

No call to:

```text
CurrentStateReadService
DeviceListContextCursorCodec
list_devices_context()
context serializer
Current State DB
```

Device Detail `identity` continues using existing `_device_list_dto()` unchanged.

---

# 51. Feature ON initial query flow

`AdminQueryService.list_devices()` exact sequence:

```text
1. authorize admin.read.devices.

2. parse selected_limit and optional canonical MAC
   with existing validators.

3. filters =
   {} or {"mac": selected_mac}.

4. Confirm:
   device_list_context_state=active
   cursor codec exists.
   Else AdminQueryUnavailable.

5. No cursor:
   initial request.

6. Capture one:
   evaluated_at_utc = server UTC now
   in existing canonical format.

7. deadline.require_remaining().

8. Call:
   CurrentStateReadService.get_current_client_inventory_context(
       site_id,
       evaluated_at_utc=evaluated_at_utc,
   )

9. deadline.require_remaining().

10. Branch trusted / unknown / source failure
    exactly as below.

11. Call one gateway context page path.

12. Strict serialize.

13. If has_more:
    create signed context cursor from:
    chain overlay metadata
    + last row ordering key.

14. Return AdminQueryResponse(result, page).
```

All inside existing `_run(query)`:

```text
one concurrency slot
one QueryDeadline
```

---

# 52. Feature ON initial trusted flow

If Current descriptor:

```text
overlay_mode=trusted
```

call:

```python
AdminDeviceReadGateway.list_devices_context(
    site_id=site_id,
    limit=selected_limit,
    deadline=deadline,
    overlay_mode="trusted",
    current_cycle_id=context.current_cycle_id,
    source_scope_hash=context.source_scope_hash,
    cursor=None,
    canonical_mac=selected_mac,
)
```

If success:

```text
root trusted metadata
items online/offline
Online-first
signed trusted cursor if has_more
```

---

# 53. Feature ON initial semantic-unknown flow

If descriptor:

```text
overlay_mode=unknown
```

call:

```python
list_devices_context(
    ...,
    overlay_mode="unknown",
    current_cycle_id=None,
    source_scope_hash=None,
    cursor=None,
)
```

Result:

```text
HTTP 200
all current_presence=unknown
historical order
root:
overlay_mode=unknown
ordering_applied=false
source_execution_status=available
```

Signed unknown cursor if `has_more`.

---

# 54. Feature ON initial Current execution-failure flow

Catch from Current selector:

```text
CurrentStateStorageError
CurrentStateSchemaError
CurrentStateValidationError
```

except:

```text
CurrentClientInventoryContextExpired
```

which is not expected in initial mode.

If deadline still valid:

```text
call unknown gateway path
```

Root:

```text
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
scope =
canonical configured scope if safely available
else null
snapshot=null
```

If historical unknown gateway succeeds:

```text
HTTP 200
```

If it fails:

```text
AdminQueryUnavailable
```

If deadline expires:

```text
AdminQueryDeadline
```

---

# 55. Initial trusted selector→gateway race flow

If selector returned trusted but gateway raises:

```text
AdminDeviceContextExpired
```

this is the initial retention/TOCTOU race.

If deadline permits:

```text
rerun gateway with overlay_mode=unknown
```

Root:

```text
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
snapshot=null
```

All rows:

```text
current_presence=unknown
```

No trusted cursor emitted.

---

# 56. Feature ON continuation decode flow

If `cursor` is present:

```text
1. Decode with DeviceListContextCursorCodec
   before any semantic Current processing.

2. DeviceListContextCursorError
   → AdminQueryValidationError.

3. Cursor Site/filter/order/version
   already verified by codec.

4. Branch by signed overlay_mode.
```

---

# 57. Unknown continuation flow

For signed:

```text
overlay_mode=unknown
```

DO NOT read Current State.

Call:

```python
list_devices_context(
    site_id=site_id,
    limit=selected_limit,
    deadline=deadline,
    overlay_mode="unknown",
    current_cycle_id=None,
    source_scope_hash=None,
    cursor=(
        decoded.last_online_rank,
        decoded.last_site_last_seen_at,
        decoded.last_device_id,
    ),
    canonical_mac=selected_mac,
)
```

Use decoded signed chain metadata as root overlay metadata.

Do NOT substitute newly observed Current evidence.

If has_more, next cursor repeats the same chain metadata and updates only:

```text
last_online_rank
last_site_last_seen_at
last_device_id
```

---

# 58. Trusted continuation flow

For signed:

```text
overlay_mode=trusted
```

sequence:

```text
1. deadline.require_remaining().

2. CurrentStateReadService.get_current_client_inventory_context(
       site_id,
       evaluated_at_utc=decoded.evaluated_at_utc,
       current_cycle_id=decoded.current_cycle_id,
       expected_source_scope_hash=decoded.source_scope_hash,
   )

3. CurrentClientInventoryContextExpired
   → AdminQueryCursorExpired.

4. Current State storage/schema execution failure
   → AdminQueryUnavailable.

5. deadline.require_remaining().

6. Require returned context:
   overlay_mode=trusted
   same cycle
   same hash.

7. Gateway list_devices_context(
       trusted,
       same cycle/hash,
       decoded last key,
   ).

8. AdminDeviceContextExpired
   → AdminQueryCursorExpired.

9. AdminDeviceSourceError
   → AdminQueryUnavailable.

10. AnalyticsQueryDeadlineExceeded
    → AdminQueryDeadline.

11. Serialize using chain T/context.

12. Encode next signed trusted cursor if has_more.
```

No switch to a newer Current cycle.

No fallback to unknown within a trusted continuation.

---

# 59. Exact internal/public error table

| Condition | Internal exception/result | Public behavior |
|---|---|---|
| malformed context cursor | `DeviceListContextCursorError` | `400 invalid_request` |
| non-canonical cursor | `DeviceListContextCursorError` | `400 invalid_request` |
| HMAC mismatch/tamper | `DeviceListContextCursorError` | `400 invalid_request` |
| wrong signed Site/filter/kind/version/order | `DeviceListContextCursorError` | `400 invalid_request` |
| context cursor encode overflow | `DeviceListContextCursorError` during server encode | `503 source_unavailable` |
| trusted pinned semantic cycle missing/incompatible | `CurrentClientInventoryContextExpired` | `400 cursor_expired` |
| trusted gateway same-transaction cycle guard missing | `AdminDeviceContextExpired` | initial: fail-open unknown; continuation: `400 cursor_expired` |
| Current semantic stale/unavailable | `CurrentClientInventoryContext(overlay_mode="unknown")` | `200`, unknown presence |
| initial Current storage/schema/validation execution failure | existing Current State exception | fail-open historical unknown where deadline permits |
| trusted continuation temporary Current source failure | existing Current State/source exception | `503 source_unavailable` |
| trusted continuation temporary gateway/current DB failure | `AdminDeviceSourceError` | `503 source_unavailable` |
| Admin deadline exhausted | `AnalyticsQueryDeadlineExceeded` / `AdminQueryDeadline` | `503 query_deadline` |
| Feature ON context config/codec unavailable | `AdminQueryUnavailable` | `503 source_unavailable` |
| historical Registry/Visit source unavailable | existing gateway source error | `503 source_unavailable` |
| historical identity conflict | existing integrity path | existing safe Admin integrity behavior |

No other public error code is added by this TASK.

---

# 60. Runtime exact composition

Add to `AdminWebRuntime`:

```text
device_list_context_state:
disabled | active | unavailable

device_list_context_config:
DeviceListContextConfig | None
```

Runtime flow after `AdminWebConfig` is parsed:

```text
1. parse DeviceListContextConfig.

2. feature false
   → state=disabled
   → no codec.

3. feature true + valid secret
   → state=active
   → create DeviceListContextCursorCodec(
         secret_key=config.cursor_secret,
         maximum_length=admin_config.max_cursor_chars,
      )

4. feature true + invalid secret/config
   → state=unavailable
   → log sanitized configuration error
   → base Admin remains available.
```

No secret values in logs.

---

# 61. Runtime gateway construction

When constructing `AdminDeviceReadGateway`:

```text
registry path =
existing Registry repository path

visit path =
existing Visit repository path

current_state_db_path =
current_state_read_service.repository.config.db_path
if current_state_read_service exists
else None
```

Passing the path does not itself attach/read Current DB.

Only:

```text
list_devices_context(overlay_mode="trusted")
```

may attach it.

Feature OFF still uses old gateway method with zero Current DB list workload.

---

# 62. Query service constructor dependencies

Tech Lead FINAL CODER TASK must bind `AdminQueryService` to exactly:

```text
existing AdminWebConfig
existing CurrentStateReadService
existing AdminDeviceReadGateway

device_list_context_state
DeviceListContextCursorCodec | None
```

No HTTP call to another Admin endpoint.

No new service process.

No cache.

---

# 63. Dedicated feature configuration failure isolation

Invalid context cursor secret/config must NOT make these fail:

```text
Admin login
Device Detail
Device Current
Visits
Traffic
Home
```

Only context-enabled Devices list product is unavailable while flag is true.

Feature false preserves existing Devices list.

---

# 64. File scope — MUST MODIFY

Tech Lead should verify these exact paths at fresh rebind; absent contradiction, FINAL CODER TASK must authorize modification of:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/device_gateway.py

app/current_state/read_service.py

tests/admin_web/test_config.py
tests/admin_web/test_runtime.py
tests/admin_web/test_query_service.py
tests/admin_web/test_device_gateway.py
tests/current_state/test_read_service.py
```

---

# 65. File scope — NEW FILES

Create exactly:

```text
app/admin_web/device_list_context_config.py
app/admin_web/device_list_context_cursor.py
app/admin_web/device_list_context_serialization.py

tests/admin_web/test_device_list_context_cursor.py
tests/admin_web/test_device_list_context_serialization.py
```

No alternative module names in the FINAL CODER TASK unless Tech Lead rebind finds a factual naming/path conflict before authorization.

---

# 66. File scope — MUST NOT MODIFY

By default, this TASK must not modify:

```text
app/admin_web/cursors.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/devices.html
app/admin_web/templates/admin/device.html

app/current_state/models.py
app/current_state/repository.py
app/current_state/schema.py
Current State collector/worker files

app/analytics/current_guest_traffic.py
Traffic modules

Visitor Registry writer/schema
Visit Lifecycle
Observation acquisition/schema

OmadaProvider
CAPPORT/Auth

run.py
requirements*
Grafana/Loki/Alloy
systemd/Nginx
```

`TASK-WEB-DEVICE-UI-01` remains separate and frozen.

If Tech Lead rebind proves one of these files is objectively required, that must be resolved before the FINAL CODER TASK; Coder does not expand scope himself.

---

# 67. Coder focused tests — exact allowed set

Coder is required to create/update and run only the following narrowly targeted test modules:

```text
tests/admin_web/test_device_list_context_cursor.py
tests/admin_web/test_device_list_context_serialization.py
tests/current_state/test_read_service.py
tests/admin_web/test_device_gateway.py
tests/admin_web/test_query_service.py
tests/admin_web/test_runtime.py
tests/admin_web/test_config.py
```

Coder may run syntax/compile checks for touched implementation files and:

```text
git diff --check
```

Coder must not run official acceptance suites/gates unless Owner + Tech Lead later give a separate instruction.

---

# 68. Focused cursor tests required from Coder

`tests/admin_web/test_device_list_context_cursor.py` must narrowly cover:

```text
trusted encode/decode round-trip

unknown semantic-chain round-trip

unknown execution-unavailable round-trip

wrong secret → DeviceListContextCursorError

single-field tamper:
evaluated_at_utc
current_cycle_id
source_scope_hash
overlay_mode
last_online_rank
last_device_id

malformed token
missing/extra separator
bad base64
wrong signature length
non-canonical JSON/token
extra payload field
missing payload field
wrong site
wrong filter
wrong kind/version/order version
oversize input

trusted nullability invariants
unknown nullability invariants

encode over maximum length
→ error
```

Do not benchmark HMAC.

---

# 69. Focused Current inventory-context tests required from Coder

Extend:

```text
tests/current_state/test_read_service.py
```

only for the new method:

```text
initial fresh complete trusted
→ trusted + cycle/hash

initial fresh complete trusted with no clients
→ trusted descriptor still valid

stale
→ unknown

unavailable
→ unknown

no complete
→ unknown

clock anomaly/invalid timestamp
→ unknown

untrusted scope
→ unknown

trusted pinned continuation same T/A/H
→ trusted

pinned cycle missing
→ CurrentClientInventoryContextExpired

configured scope hash mismatch
→ CurrentClientInventoryContextExpired

pinned cycle wrong Site/kind/result/complete
→ CurrentClientInventoryContextExpired

storage error remains storage error
```

Do not retest all Current State products.

---

# 70. Focused gateway tests required from Coder

Extend:

```text
tests/admin_web/test_device_gateway.py
```

for:

```text
old list_devices path remains historical
old get_device semantics unchanged

unknown context:
hostname exact raw value
hostname null remains null
presence unknown
historical order
no Current DB read requirement

trusted context:
MAC present → online/rank 0
MAC absent → offline/rank 1

global Online-first before limit
secondary historical ordering

trusted context cursor predicate

exact MAC filter

Current-only MAC absent from historical inventory
→ no row

same-transaction cycle guard missing
→ AdminDeviceContextExpired

selector/composition race simulation:
delete pinned cycle before gateway transaction
→ no false offline

temporary SQLite/source error
→ AdminDeviceSourceError
```

No capacity benchmark by Coder.

---

# 71. Focused serializer tests required from Coder

`tests/admin_web/test_device_list_context_serialization.py`:

```text
exact item key set
exact overlay key set
trusted shape
unknown semantic shape
unknown execution-unavailable shape

hostname null preserved
presence enum validation
counts/types validation
scope machine type
snapshot freshness enum
no online_rank leakage
no current_cycle_id leakage
no source_scope_hash leakage
no latest_snapshot leakage

contradictory trusted/unknown shapes
→ DeviceListContextSerializationError
```

---

# 72. Focused QueryService tests required from Coder

Extend:

```text
tests/admin_web/test_query_service.py
```

only around list context orchestration:

```text
Feature OFF:
old gateway method used
old cursor codec used
no Current descriptor call
no context serializer/codec

Feature ON config unavailable
→ AdminQueryUnavailable

initial trusted
→ descriptor once
→ context gateway once
→ signed context cursor

initial semantic unknown
→ unknown gateway
→ signed unknown cursor

initial Current execution failure
→ historical/unknown fail-open

initial selector→gateway AdminDeviceContextExpired
→ unknown fail-open
→ no trusted cursor

unknown continuation
→ no CurrentStateReadService call
→ chain metadata preserved

trusted continuation:
integrity decode before Current call
pinned descriptor revalidation
same cycle/hash gateway call

CurrentClientInventoryContextExpired
→ AdminQueryCursorExpired

AdminDeviceContextExpired continuation
→ AdminQueryCursorExpired

temporary Current source failure
→ AdminQueryUnavailable

deadline
→ AdminQueryDeadline

cursor tamper
→ AdminQueryValidationError
```

No full Admin regression by Coder.

---

# 73. Focused runtime/config tests required from Coder

Extend:

```text
tests/admin_web/test_config.py
tests/admin_web/test_runtime.py
```

only for:

```text
feature default false

feature true requires WEB_ADMIN_ENABLED=true

feature false accepts empty cursor secret

feature true accepts exactly 64 lowercase hex secret

feature true rejects:
empty
short
long
uppercase
non-hex

runtime disabled state

runtime active state
→ codec constructed
→ current DB path injected

invalid context secret
→ device_list_context_state=unavailable
→ base Admin runtime remains active

secret absent from repr/log-safe object
```

---

# 74. Coder explicitly does NOT run

Coder must not run/claim:

```text
Central Full Gate
full repository regression
cross-surface official regression
benchmark_device_gateway acceptance
EXPLAIN QUERY PLAN acceptance
capacity gate
performance PASS
browser acceptance
visual acceptance
production smoke
deployment
production verification
official security acceptance
official PASS/FAIL
Merge ready
Deploy ready
Production ready
```

Those belong to Owner + Tech Lead.

---

# 75. Owner + Tech Lead post-handoff gates — not Coder work

After Coder handoff, Owner + Tech Lead will separately perform:

```text
fresh candidate identity verification
targeted cross-surface regression
EXPLAIN QUERY PLAN
representative capacity
large historical inventory
configured Current population bound
page 1 + continuation
MAC filter
cursor tamper/security acceptance
retention race acceptance
browser data acceptance
Feature OFF differential
official PASS/FAIL
```

This section is informational for workflow only.

Coder does not execute these gates under the implementation TASK.

---

# 76. Coder STOP conditions

Coder may STOP only for an objective contradiction such as:

```text
supplied baseline differs from authorized baseline

specified file/method does not exist as stated

specified existing contract is materially different

exact cursor secret/config path cannot be implemented
without touching a forbidden global security boundary

same-transaction Current structural proof cannot be achieved
within authorized gateway/source boundaries

required Online-first query requires a schema/index change

specified DTO/error contract contradicts current accepted API infrastructure

implementation requires modifying a MUST NOT MODIFY file

specified invariant is technically impossible in authorized scope
```

Coder response:

```text
STOP
→ exact file/line/runtime evidence
→ no workaround
→ no alternative design
```

Return to:

```text
Architect + Tech Lead
```

---

# 77. Coder forbidden decisions

Coder must not:

```text
choose another HMAC algorithm
choose another secret source
reuse password hash
create server-side cursor cache
choose another cursor payload
change payload field names
change error taxonomy
change feature failure behavior

choose list_current_clients
choose per-row get_current_client
choose browser sorting
choose page-local sorting
choose Current-only insertion

add an index
add a schema
add a DB/cache
increase deadline/concurrency

change Device Current semantics
add Traffic
change hostname fallback
add polling
expand UI scope
```

Any such need is a STOP.

---

# 78. Tech Lead repository rebind checklist

Before converting this draft into the FINAL CODER TASK, Tech Lead must verify exact current source for:

```text
origin/main SHA/tree

AdminWebConfig field/constructor order
app/settings.py import/mapping locations
runtime _query_service construction
AdminQueryService constructor and list_devices body
existing Admin exception mappings
AdminDeviceReadGateway constructor/open/query helpers
Current State repository db_path field
Current State schema version
current_state_cycles exact columns
current_client_state exact columns/key
CurrentSnapshotMeta exact fields
existing Current State helper functions
existing cursor max length
existing timestamp canonical format
test module actual names
```

Tech Lead should correct factual repository-binding details in the FINAL CODER TASK without changing the accepted architecture.

If rebind reveals a material architecture contradiction:

```text
return to Architect
```

Do not pass ambiguity to Coder.

---

# 79. Required FINAL CODER TASK quality

After Tech Lead rebind, the FINAL CODER TASK must contain no phrases such as:

```text
or equivalent
conceptually
choose
decide
consider
as appropriate
repository-consistent approach
propose
investigate
plan
spike
prototype
```

All implementation choices must be fixed before Owner authorization.

---

# 80. Implementation authorization boundary

This Architect implementation-spec draft:

```text
DOES NOT AUTHORIZE IMPLEMENTATION
```

Current state:

```text
ARCHITECTURE=FINAL / ACCEPTED

ARCHITECT IMPLEMENTATION SPEC DRAFT=
COMPLETE

TECH LEAD NEXT=
FRESH REPOSITORY REBIND
+
SOURCE VERIFICATION
+
FINAL CODER TASK

CODER=
HOLD

CODER PLAN=
FORBIDDEN / NOT REQUIRED

IMPLEMENTATION AUTHORIZATION=
NOT GRANTED

GITHUB WRITE=
HOLD

PRODUCTION=
UNTOUCHED

TASK-WEB-DEVICE-UI-01=
FROZEN
```

Next workflow:

```text
Architect implementation-spec draft
        ↓
Tech Lead repository rebind / exact source verification
        ↓
Architect + Tech Lead exact FINAL CODER TASK
        ↓
Owner implementation authorization
        ↓
Coder writes code immediately
        ↓
narrow focused tests only
        ↓
Coder handoff
        ↓
Owner + Tech Lead official acceptance
```
