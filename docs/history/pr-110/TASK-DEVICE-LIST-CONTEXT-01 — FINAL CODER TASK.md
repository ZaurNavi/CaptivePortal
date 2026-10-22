# TASK-DEVICE-LIST-CONTEXT-01 — FINAL CODER TASK

**Project:** CaptivPortal  
**Area:** Admin Console → Devices list  
**Architecture:** `TASK-DEVICE-LIST-CONTEXT-01 — FINAL-R2`  
**Architect implementation draft:** reconciled by Tech Lead  
**Tech Lead repository rebind:** COMPLETE  
**Prepared:** 2026-09-09

---

# 0. WORKFLOW CONTRACT

```text
ARCHITECT + TECH LEAD DESIGN
CODER WRITES CODE
OWNER + TECH LEAD ACCEPT
```

Coder:

```text
DOES NOT PLAN
DOES NOT DESIGN
DOES NOT PROPOSE ALTERNATIVES
DOES NOT PROTOTYPE
DOES NOT PREVIEW
DOES NOT CHANGE SCOPE
```

Coder receives this specification and writes the implementation exactly to it.

Coder may run only the narrowly targeted tests explicitly listed in this TASK.

No broad regression, Central Gate, benchmark acceptance, browser acceptance, production smoke, deployment, merge or publication.

---

# 1. AUTHORIZATION STATE

```text
IMPLEMENTATION_READY=YES

OWNER_IMPLEMENTATION_AUTHORIZATION=NOT_YET_GRANTED

CODER=HOLD
```

Do not modify the repository until Owner explicitly gives implementation authorization for this TASK.

After Owner authorization there is:

```text
NO CODER PLAN STAGE
NO PLAN REVIEW STAGE
```

Coder starts implementation immediately.

---

# 2. EXACT BASELINE

Authorized baseline:

```text
repository:
ZaurNavi/CaptivePortal

branch:
main

SHA:
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

TREE:
edb5bab5479a4417d545429eeacf2b29a640e441
```

Before editing, Coder must verify:

```text
git rev-parse HEAD
git show -s --format=%T HEAD
git status --short
```

Required:

```text
HEAD=
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

TREE=
edb5bab5479a4417d545429eeacf2b29a640e441

WORKTREE=
clean
```

If any differs:

```text
STOP
RETURN EXACT EVIDENCE
DO NOT REBASE
DO NOT MERGE
DO NOT RESET
DO NOT DESIGN A WORKAROUND
```

---

# 3. PRODUCT RESULT

Existing endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/devices
```

Capability remains:

```text
admin.read.devices
```

Query parameters remain exactly:

```text
limit
cursor
mac
```

No second endpoint.

## Feature OFF

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
```

must preserve exactly:

```text
existing historical list path
existing DTO
existing ordering
existing generic devices cursor
zero Current State list reads
Device Detail identity unchanged
```

## Feature ON

Adds to Devices list:

```text
hostname
current_presence
current_state_overlay
server-side Online-first ordering
dedicated authenticated context cursor
```

---

# 4. PERMANENT SEMANTICS

Devices membership remains:

```text
historical Site Snapshot evidence
OR
historical Site Visit evidence
```

Current State:

```text
overlay only
```

A Current client with no historical Device membership:

```text
MUST NOT create a Device row
```

Presence:

```text
online
offline
unknown
```

Rules:

```text
fresh + complete + trusted + MAC present
→ online

fresh + complete + trusted + MAC absent
→ offline

stale
unavailable
invalid timestamp
untrusted scope
→ unknown
```

Permanent:

```text
stale != offline
unavailable != offline
invalid timestamp != offline
```

Historical Snapshot/Observation/Visit facts MUST NOT infer current Presence.

---

# 5. HOSTNAME CONTRACT

Public Feature ON field:

```text
hostname: string | null
```

Source:

```text
latest Snapshot for requested Site
→ hostname
```

Forbidden fallback:

```text
name
system_name
MAC
```

If no hostname:

```text
hostname=null
```

`device_type` remains separate.

---

# 6. FILE SCOPE — MUST MODIFY

Modify exactly:

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

# 7. FILE SCOPE — CREATE

Create exactly:

```text
app/admin_web/device_list_context_config.py
app/admin_web/device_list_context_cursor.py
app/admin_web/device_list_context_serialization.py

tests/admin_web/test_device_list_context_cursor.py
tests/admin_web/test_device_list_context_serialization.py
```

---

# 8. MUST NOT MODIFY

Do not modify:

```text
app/admin_web/cursors.py
app/admin_web/routes.py

app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/devices.html
app/admin_web/templates/admin/device.html

app/current_state/models.py
app/current_state/repository.py
app/current_state/config.py
app/current_state/normalizer.py
Current State workers/collectors

app/analytics/current_guest_traffic.py
other Traffic modules

Visitor Registry writer/schema
Visit Lifecycle
Observation acquisition/schema

OmadaProvider
CAPPORT/Auth

run.py
requirements*

Grafana
Loki
Alloy
systemd
Nginx
```

If implementation appears to require any MUST-NOT-MODIFY file:

```text
STOP
RETURN EXACT EVIDENCE
```

---

# 9. CONFIG — app/config.py

Immediately after the existing Device settings add:

```python
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED = os.getenv(
    "WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED", "false"
)
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET = os.getenv(
    "WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET", ""
)
```

Keep:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
```

unchanged.

---

# 10. SETTINGS — app/settings.py

Import both new constants from `app.config`.

Add exact settings mappings:

```python
"web_admin_device_list_context_enabled": (
    WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED
),
"web_admin_device_list_context_cursor_secret": (
    WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
),
```

Place them adjacent to the existing Device Admin settings.

---

# 11. .env.example

Add exactly:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED=false
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET=
```

adjacent to:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
```

---

# 12. AdminWebConfig

Modify:

```text
app/admin_web/config.py
```

Add field immediately after `device_page_size`:

```python
device_list_context_enabled: bool
```

Keep:

```python
device_current_context_enabled
```

as a separate field.

Parse exactly:

```python
device_list_context_enabled = _exact_bool(
    settings.get("web_admin_device_list_context_enabled", "false"),
    "WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED",
)
```

Validation:

```python
if device_list_context_enabled and not enabled:
    raise AdminWebConfigError(
        "WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED requires WEB_ADMIN_ENABLED=true"
    )
```

Include:

```python
device_list_context_enabled=device_list_context_enabled
```

in `AdminWebConfig(...)`.

Do NOT add cursor secret to `AdminWebConfig`.

---

# 13. Dedicated context configuration

Create:

```text
app/admin_web/device_list_context_config.py
```

Exact public types:

```python
class DeviceListContextConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class DeviceListContextConfig:
    enabled: bool
    cursor_secret: bytes
```

Implement:

```python
def device_list_context_config_from_settings(
    settings,
    *,
    admin_config,
) -> DeviceListContextConfig:
```

Behavior:

## Feature OFF

If:

```python
admin_config.device_list_context_enabled is False
```

return:

```python
DeviceListContextConfig(
    enabled=False,
    cursor_secret=b"",
)
```

Do not validate the secret.

## Feature ON

Read:

```text
web_admin_device_list_context_cursor_secret
```

It must be a string matching exactly:

```text
[0-9a-f]{64}
```

Then:

```python
bytes.fromhex(value)
```

must produce exactly 32 bytes.

Otherwise raise:

```python
DeviceListContextConfigError
```

No normalization.

No uppercase.

No autogenerated secret.

No reuse of:

```text
Admin password hash
session token
CSRF token
other application secret
```

`repr()` must not expose secret material.

---

# 14. CURSOR CRYPTOGRAPHY

Create:

```text
app/admin_web/device_list_context_cursor.py
```

Use exactly:

```text
HMAC-SHA-256
```

Signing:

```python
hmac.new(
    secret_key,
    canonical_payload_bytes,
    hashlib.sha256,
).digest()
```

Verification:

```python
hmac.compare_digest(...)
```

Digest:

```text
32 bytes
no truncation
```

Import from existing:

```python
app.admin_web.cursors.filter_fingerprint
```

Do NOT modify generic cursor code.

---

# 15. CURSOR WIRE FORMAT

Exact format:

```text
<base64url-no-padding(payload)>.<base64url-no-padding(signature)>
```

Exactly one `.` separator.

Canonical payload encoding:

```python
json.dumps(
    payload,
    ensure_ascii=True,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("ascii")
```

Complete token maximum:

```python
AdminWebConfig.max_cursor_chars
```

No separate max-length setting.

---

# 16. CURSOR TYPES

Create exactly:

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

Codec:

```python
class DeviceListContextCursorCodec:
    def __init__(
        self,
        *,
        secret_key: bytes,
        maximum_length: int,
    ): ...

    def encode(
        self,
        value: DeviceListContextCursor,
    ) -> str: ...

    def decode(
        self,
        value,
        *,
        site_id,
        filters,
    ) -> DeviceListContextCursor | None: ...
```

---

# 17. CURSOR CONSTANTS

Exact:

```text
version=1
kind=devices_context
ordering_contract_version=1
```

Enums:

```text
overlay_mode:
trusted | unknown

source_execution_status:
available | unavailable

last_online_rank:
0 | 1
```

---

# 18. CURSOR EXACT FIELD SET

Signed JSON contains exactly:

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

No extra keys.

---

# 19. CURSOR CANONICAL IDENTITY VALIDATION

Validate:

```text
site_id
→ exactly 24 lowercase hex

filter_fingerprint
→ exactly 64 lowercase hex

evaluated_at_utc
→ YYYY-MM-DDTHH:MM:SS.mmmZ
→ valid datetime

last_site_last_seen_at
→ same canonical UTC format

last_device_id
→ canonical lowercase UUID string

current_cycle_id
→ trusted: non-empty string, <=128
→ unknown: null

source_scope_hash
→ trusted: exactly 64 lowercase hex
→ unknown: null
```

---

# 20. SIGNED SCOPE CONTRACT

`scope`:

```text
dict | null
```

When non-null exact keys:

```text
scope_type
site_id
ssids
```

Exact machine value:

```text
scope_type=client_ssid_allowlist
```

`scope.site_id` must equal cursor `site_id`.

`ssids` must be:

```text
non-empty list[str]
sorted
unique
```

The canonical scope is NOT raw config order.

It must match existing Current State canonicalization:

```python
{
    "scope_type": "client_ssid_allowlist",
    "site_id": site_id,
    "ssids": sorted(set(ssids)),
}
```

Recompute using existing:

```python
canonical_scope(
    "client",
    site_id,
    tuple(ssids),
)
```

The decoded canonical JSON object must exactly equal signed `scope`.

For trusted cursor:

```text
signed source_scope_hash
==
hash returned by canonical_scope()
```

---

# 21. SIGNED SNAPSHOT CONTRACT

`snapshot`:

```text
dict | null
```

When present exact keys:

```text
observed_at
capture_finished_at
age_seconds
freshness_status
freshness_reason
complete
```

Allowed freshness:

```text
fresh
stale
unavailable
```

Allowed reasons exactly:

```text
within_freshness_window
older_than_freshness_window
older_than_unavailable_threshold
no_complete_snapshot
clock_anomaly
invalid_timestamp
invalid_source_scope
```

`age_seconds`:

```text
finite non-negative number | null
```

`complete`:

```text
bool
```

No cycle ID in snapshot.

No scope hash in snapshot.

---

# 22. CURSOR CROSS-FIELD INVARIANTS

## trusted

Must satisfy:

```text
overlay_mode=trusted
source_execution_status=available

scope != null
snapshot != null

snapshot.freshness_status=fresh
snapshot.freshness_reason=within_freshness_window
snapshot.complete=true

current_cycle_id != null
source_scope_hash != null

last_online_rank=0 or 1
```

## unknown + semantic evidence

Must satisfy:

```text
overlay_mode=unknown
source_execution_status=available

scope != null
snapshot != null

snapshot.freshness_status != fresh

current_cycle_id=null
source_scope_hash=null
last_online_rank=1
```

## unknown + execution unavailable

Must satisfy:

```text
overlay_mode=unknown
source_execution_status=unavailable

snapshot=null

current_cycle_id=null
source_scope_hash=null
last_online_rank=1
```

`scope` may be canonical non-null when config was safely available; otherwise null.

---

# 23. CURSOR ENCODE

`encode()` MUST:

```text
validate the full dataclass
validate every format
validate all cross-field invariants
validate canonical scope/hash
serialize canonically
sign
build token
require total length <= maximum_length
```

Do not sign an invalid cursor object.

If generated token exceeds maximum:

```python
raise DeviceListContextCursorError
```

---

# 24. CURSOR DECODE ORDER

Perform exactly:

```text
1. value is None → return None.

2. Require non-empty str and
   len(value) <= maximum_length.

3. Require exactly one "." and two non-empty segments.

4. Strict base64url decode both segments.

5. Require signature length exactly 32 bytes.

6. Calculate HMAC over RAW payload bytes.

7. hmac.compare_digest.

8. If signature mismatch:
   DeviceListContextCursorError.

9. ASCII-decode JSON payload.

10. Require dict and exact field set.

11. Validate types, formats, enums,
    canonical scope and cross-field invariants.

12. Require:
    version=1
    kind=devices_context
    site_id=requested site
    filter_fingerprint=filter_fingerprint(filters)
    ordering_contract_version=1

13. Canonically reserialize parsed payload.

14. Require canonical payload bytes == raw payload bytes.

15. Canonically re-encode payload/signature without padding.

16. Require reconstructed token == supplied token.

17. Return DeviceListContextCursor.
```

No Current State semantic read before successful completion.

---

# 25. CURSOR ERROR MAPPING

Caller cursor problem:

```text
malformed
non-canonical
tampered
wrong HMAC
wrong Site
wrong filter
wrong kind
wrong version
wrong ordering version
oversize
invalid field
invalid invariant
```

raises:

```text
DeviceListContextCursorError
```

and QueryService maps to:

```text
AdminQueryValidationError
→ 400 invalid_request
```

Server-side cursor encode failure maps to:

```text
AdminQueryUnavailable
→ 503 source_unavailable
```

Never silently omit `next_cursor` when:

```text
has_more=true
```

---

# 26. CURRENT STATE INVENTORY MODEL

Modify:

```text
app/current_state/read_service.py
```

Add exactly:

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

Add:

```python
class CurrentClientInventoryContextExpired(
    CurrentStateValidationError
):
    pass
```

---

# 27. CURRENT INVENTORY METHOD

Add exactly:

```python
def get_current_client_inventory_context(
    self,
    site_id: str,
    *,
    evaluated_at_utc: datetime | str | None = None,
    current_cycle_id: str | None = None,
    expected_source_scope_hash: str | None = None,
) -> CurrentClientInventoryContext:
```

No Device rows returned.

No population materialization.

No Omada call.

No writes.

---

# 28. CURRENT INVENTORY ARGUMENT RULE

These two arguments must be:

```text
both null
OR
both non-null
```

```text
current_cycle_id
expected_source_scope_hash
```

Partial pair:

```python
raise CurrentStateValidationError
```

If provided:

```text
current_cycle_id
```

must pass existing:

```python
require_cycle_id()
```

Expected hash must match:

```text
[0-9a-f]{64}
```

Malformed internal argument:

```python
raise CurrentStateValidationError
```

---

# 29. CURRENT INITIAL MODE

When pinned arguments are null:

1. Validate Site with existing `require_site_id`.
2. Require Site belongs to `self.config.site_ids`.
3. Resolve:

```python
scope_json, scope_hash = canonical_scope(
    "client",
    site,
    self.config.client_ssids,
)
```

4. Resolve evaluated T through existing `_evaluated()`.
5. In one existing repository read transaction use:

```python
_cycle_selection(
    connection,
    site,
    "client",
    source_scope_hash=scope_hash,
)
```

6. Use `latest_complete` as selected cycle.
7. Build metadata with existing:

```python
self._meta(...)
```

8. Trusted scope test must be identical to existing `get_current_client()`:

```python
snapshot.source_scope == json.loads(scope_json)
and snapshot.source_scope_hash == scope_hash
and snapshot.source_scope_version == 1
```

If snapshot is fresh but scope trust fails, convert metadata to:

```text
freshness_status=unavailable
freshness_reason=invalid_source_scope
```

using the same `_meta_from_row()` behavior already used by `get_current_client()`.

Return trusted only when:

```text
selected exists
snapshot.complete is True
snapshot.freshness_status == "fresh"
trusted_scope is True
```

Trusted return:

```text
overlay_mode="trusted"
current_cycle_id=str(selected["cycle_id"])
source_scope_hash=scope_hash
```

All other safe semantic states return:

```text
overlay_mode="unknown"
current_cycle_id=None
source_scope_hash=None
```

Do not convert stale/unavailable/no-complete into an exception.

---

# 30. CURRENT TRUSTED CONTINUATION MODE

For pinned arguments:

1. Resolve current canonical configured scope/hash.
2. If valid signed `expected_source_scope_hash` differs from currently configured canonical hash:

```python
raise CurrentClientInventoryContextExpired
```

3. Select exactly:

```sql
SELECT *
FROM current_state_cycles
WHERE cycle_id=?
  AND site_id=?
  AND kind='client'
  AND result='success'
  AND complete=1
  AND source_scope_hash=?
```

4. Missing row:

```python
raise CurrentClientInventoryContextExpired
```

5. Build `CurrentSnapshotMeta` at the signed/pinned `evaluated_at_utc`.

6. Revalidate exact source scope JSON/hash/version.

7. Require:

```text
snapshot.complete=true
snapshot.freshness_status=fresh
scope trusted
```

Any semantic incompatibility of the server-issued pinned context:

```python
raise CurrentClientInventoryContextExpired
```

Success returns the exact same:

```text
T
cycle ID
scope hash
overlay_mode=trusted
```

Do not choose a newer cycle.

Storage/schema/I/O failures remain normal Current State source exceptions.

---

# 31. GATEWAY MODELS

Modify:

```text
app/admin_web/device_gateway.py
```

Add:

```python
class AdminDeviceContextExpired(AdminDeviceSourceError):
    pass
```

Add exactly:

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

Add:

```python
@dataclass(frozen=True, slots=True)
class AdminDeviceListContextPage:
    items: tuple[AdminDeviceListContextRow, ...]
    has_more: bool
```

---

# 32. GATEWAY CONSTRUCTOR

Change only signature/storage:

```python
def __init__(
    self,
    registry_db_path,
    visit_db_path,
    current_state_db_path=None,
):
```

Store:

```python
self._registry_path = Path(registry_db_path)
self._visit_path = Path(visit_db_path)
self._current_state_path = (
    None
    if current_state_db_path is None
    else Path(current_state_db_path)
)
```

Do not alter behavior of existing:

```text
list_devices()
get_device()
_open()
_DEVICE_PAGE_SQL
```

---

# 33. NEW GATEWAY METHOD

Add exactly:

```python
def list_devices_context(
    self,
    *,
    site_id: str,
    limit: int,
    deadline: QueryDeadline,
    overlay_mode: str,
    current_cycle_id: str | None,
    source_scope_hash: str | None,
    cursor: tuple[int, str, str] | None = None,
    canonical_mac: str | None = None,
) -> AdminDeviceListContextPage:
```

Accepted modes only:

```text
trusted
unknown
```

Trusted requires:

```text
cycle non-null
hash non-null
Current DB path non-null
```

Unknown requires:

```text
cycle null
hash null
```

---

# 34. UNKNOWN GATEWAY PATH — REUSE OLD PATH

Do NOT create a second historical SQL query for unknown mode.

For:

```text
overlay_mode=unknown
```

call existing:

```python
self.list_devices(...)
```

exactly.

Convert context cursor:

```text
None
→ historical cursor None

(rank, at, device_id)
→ require rank == 1
→ historical cursor (at, device_id)
```

Map every existing `AdminDeviceRow` to context row:

```text
hostname =
row.latest_snapshot["hostname"]
when latest_snapshot exists
else null

current_presence="unknown"
online_rank=1
```

Keep every other public historical field exactly from `AdminDeviceRow`.

This path MUST NOT attach/read Current State DB.

---

# 35. TRUSTED GATEWAY CONNECTION

Add:

```text
_CURRENT_ALIAS = "current_state_db"
```

Add private `_open_context(deadline)`.

Use same in-memory URI connection pattern as existing `_open()`:

```text
isolation_level=None
timeout=0.0
row_factory=sqlite3.Row
```

Attach read-only:

```text
registry DB
visit DB
Current State DB
```

Then:

```text
PRAGMA query_only=ON
BEGIN
```

Require user versions:

```text
registry=1
visit=2
current_state=1
```

Use the same:

```text
_PROGRESS_OPCODE_INTERVAL
QueryDeadline progress handler
```

Schema/open failures:

```python
AdminDeviceSourceError("device source unavailable")
```

---

# 36. SAME-TRANSACTION CURRENT CYCLE GUARD

Inside the same trusted context transaction used for list composition, before interpreting client membership, execute exactly:

```sql
SELECT 1
FROM current_state_db.current_state_cycles
WHERE cycle_id=?
  AND site_id=?
  AND kind='client'
  AND result='success'
  AND complete=1
  AND source_scope_hash=?
LIMIT 1
```

Parameters:

```text
current_cycle_id
site_id
source_scope_hash
```

No row:

```python
raise AdminDeviceContextExpired(
    "device current context expired"
)
```

This exception must not be swallowed into generic source unavailable inside the gateway.

---

# 37. TRUSTED CONTEXT SQL

Create:

```text
_DEVICE_CONTEXT_PAGE_SQL
```

Keep the existing historical CTE definitions from `_DEVICE_PAGE_SQL` through the completed:

```text
devices
```

projection with the same historical membership, identity-conflict and latest requested-Site Snapshot semantics.

After `devices`, add context composition equivalent exactly to:

```sql
context_devices AS (
    SELECT
        devices.*,
        CASE
            WHEN current_client.client_mac IS NOT NULL
            THEN 'online'
            ELSE 'offline'
        END AS current_presence,
        CASE
            WHEN current_client.client_mac IS NOT NULL
            THEN 0
            ELSE 1
        END AS online_rank
    FROM devices
    LEFT JOIN current_state_db.current_client_state AS current_client
      ON current_client.cycle_id = :current_cycle_id
     AND current_client.site_id = :site_id
     AND current_client.client_mac = devices.canonical_mac
    WHERE (
        :canonical_mac IS NULL
        OR devices.canonical_mac = :canonical_mac
    )
),
page AS (
    SELECT *
    FROM context_devices
    WHERE (
        :cursor_rank IS NULL
        OR online_rank > :cursor_rank
        OR (
            online_rank = :cursor_rank
            AND site_last_seen_at < :cursor_at
        )
        OR (
            online_rank = :cursor_rank
            AND site_last_seen_at = :cursor_at
            AND device_id < :cursor_device_id
        )
    )
    ORDER BY
        online_rank ASC,
        site_last_seen_at DESC,
        device_id DESC
    LIMIT :row_limit
)
```

Final projection must include only fields needed for:

```text
AdminDeviceListContextRow
identity_conflict
```

including:

```text
snapshot_hostname
current_presence
online_rank
```

Final order:

```sql
ORDER BY
    online_rank ASC,
    site_last_seen_at DESC,
    device_id DESC
```

No OFFSET.

No Python global sorting.

No Current page loop.

---

# 38. TRUSTED PRESENCE

After cycle guard succeeded in the same transaction:

```text
matching current_client_state row
→ current_presence=online
→ online_rank=0

no matching row
→ current_presence=offline
→ online_rank=1
```

Current-only rows cannot appear because the query starts from historical `devices`.

---

# 39. TRUSTED CURSOR PREDICATE

For signed last key:

```text
rank
site_last_seen_at
device_id
```

strictly-after semantics are:

```text
online_rank > rank

OR

online_rank = rank
AND site_last_seen_at < cursor_at

OR

online_rank = rank
AND site_last_seen_at = cursor_at
AND device_id < cursor_device_id
```

Canonical ordering:

```text
online_rank ASC
site_last_seen_at DESC
device_id DESC
```

---

# 40. STRICT CONTEXT ROW MAPPING

Add a dedicated row mapper for trusted SQL.

Validate:

```text
canonical MAC
online_rank exactly 0 or 1
current_presence exactly online or offline
online → rank 0
offline → rank 1
identity conflict absent
```

Hostname is:

```text
snapshot_hostname
```

with no fallback.

---

# 41. SERIALIZER MODULE

Create:

```text
app/admin_web/device_list_context_serialization.py
```

Add:

```python
class DeviceListContextSerializationError(ValueError):
    pass
```

Provide exactly two public functions.

### Function 1

```python
def serialize_device_list_context_overlay(
    *,
    site_id: str,
    overlay_mode: str,
    source_execution_status: str,
    evaluated_at_utc: str,
    scope,
    snapshot: CurrentSnapshotMeta | None,
) -> dict:
```

Purpose:

```text
construct and sanitize initial page overlay metadata
```

### Function 2

```python
def serialize_device_list_context(
    *,
    site_id: str,
    items,
    overlay,
) -> dict:
```

Purpose:

```text
strictly validate public context list result
```

No data source reads.

No cursor work.

---

# 42. OVERLAY SERIALIZATION

Exact public root overlay keys:

```text
overlay_mode
ordering_applied
source_execution_status
evaluated_at_utc
scope
snapshot
```

## trusted

Require:

```text
overlay_mode=trusted
source_execution_status=available
scope canonical and for requested site
snapshot != null
snapshot.kind=client
snapshot.site_id=requested site
snapshot.evaluated_at=evaluated_at_utc
snapshot.freshness_status=fresh
snapshot.freshness_reason=within_freshness_window
snapshot.complete=true
```

Emit:

```text
ordering_applied=true
```

## unknown semantic

Require:

```text
overlay_mode=unknown
source_execution_status=available
scope canonical
snapshot != null
snapshot is NOT fresh trusted evidence
```

Emit:

```text
ordering_applied=false
```

## unknown execution failure

Require:

```text
overlay_mode=unknown
source_execution_status=unavailable
snapshot=null
```

`scope`:

```text
canonical object or null
```

Emit:

```text
ordering_applied=false
```

---

# 43. SAFE SNAPSHOT PUBLIC SHAPE

Public snapshot exact keys:

```text
observed_at
capture_finished_at
age_seconds
freshness_status
freshness_reason
complete
```

Use the same freshness/reason and timestamp-sanitization rules already accepted by Device Current Context.

For:

```text
invalid_timestamp
invalid_source_scope
```

unsafe timestamps are emitted:

```text
observed_at=null
capture_finished_at=null
age_seconds=null
```

Do not expose:

```text
cycle_id
source_scope_hash
source_scope_version
latest attempt internals
```

---

# 44. FEATURE ON ITEM DTO

Each item exact keys:

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

Do not emit:

```text
latest_snapshot
online_rank
current_cycle_id
source_scope_hash
```

Strictly validate:

```text
device_id canonical UUID
canonical_mac canonical uppercase-colon MAC
hostname str|null
device_type str|null
timestamps canonical UTC
counts type int >=0
last_* types
last_site_ap_mac canonical MAC|null
current_presence online|offline|unknown
```

Explicit `site_id` passed to serializer is authority for validating overlay `scope.site_id`.

---

# 45. QUERY SERVICE CONSTRUCTOR

Modify `AdminQueryService.__init__` by adding optional arguments:

```python
device_list_context_state: str = "disabled",
device_list_context_cursor_codec: Any | None = None,
```

Store:

```python
self._device_list_context_state
self._device_list_context_cursor_codec
```

Defaults are mandatory so existing direct constructor tests/callers remain valid.

---

# 46. QueryService list_devices — BRANCH BEFORE OLD CURSOR DECODER

Keep common beginning:

```text
authorize
selected_limit
selected_mac
filters
```

Then branch:

```python
if not self._config.device_list_context_enabled:
    ...
else:
    ...
```

This branch MUST occur before the existing:

```python
decode_cursor(... kind="devices" ...)
```

Feature ON context cursor MUST NEVER be passed to generic Admin cursor decoder.

---

# 47. FEATURE OFF QueryService FLOW

Inside false branch preserve the existing implementation path:

```text
generic decode_cursor kind=devices
_run(query)
AdminDeviceReadGateway.list_devices()
_device_list_dto()
generic encode_cursor kind=devices
AdminQueryResponse
```

Do not invoke:

```text
Current State
context cursor codec
context serializer
list_devices_context()
```

Do not alter `_device_list_dto()`.

Device Detail continues to use it unchanged.

---

# 48. FEATURE ON PRECONDITION

If:

```text
device_list_context_state != active
```

or codec is `None`:

```python
raise AdminQueryUnavailable
```

before source execution.

Decode context cursor with:

```python
codec.decode(
    cursor,
    site_id=site_id,
    filters=filters,
)
```

Catch:

```python
DeviceListContextCursorError
```

and raise:

```python
AdminQueryValidationError
```

Decode occurs before `_run(query)` and before any Current semantic call.

---

# 49. FEATURE ON INITIAL REQUEST

When decoded cursor is `None`:

Inside one existing `_run(query)`:

1. Set:

```python
evaluated_at_utc = format_utc(
    datetime.now(timezone.utc)
)
```

2. Build canonical safe scope, if possible, from:

```text
self._current_state.config.client_ssids
```

using existing `canonical_scope()`.

This is a local config read only.

If Current source/config is absent or malformed:

```text
safe scope=null
```

3. If `self._current_state` is absent or required method is absent:

```text
treat as initial Current execution unavailable
```

Do NOT fail the historical list.

4. Otherwise call once:

```python
get_current_client_inventory_context(
    site_id,
    evaluated_at_utc=evaluated_at_utc,
)
```

with deadline checks immediately before and after.

---

# 50. INITIAL TRUSTED FLOW

For trusted descriptor:

1. Create safe root overlay using:

```python
serialize_device_list_context_overlay(...)
```

from:

```text
requested site
descriptor snapshot
descriptor evaluation
canonical scope
```

2. Call:

```python
self._devices.list_devices_context(
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

3. If it succeeds:
   - strict serialize items/root;
   - if has_more, sign cursor using the **already sanitized public overlay metadata** plus last row key.

---

# 51. INITIAL SEMANTIC UNKNOWN FLOW

For:

```text
context.overlay_mode=unknown
```

Create canonical public overlay:

```text
overlay_mode=unknown
ordering_applied=false
source_execution_status=available
evaluated_at=T
canonical scope
sanitized descriptor snapshot
```

Then call:

```python
list_devices_context(
    ...,
    overlay_mode="unknown",
    current_cycle_id=None,
    source_scope_hash=None,
    cursor=None,
)
```

All rows:

```text
current_presence=unknown
```

If has_more, issue signed unknown cursor from sanitized chain metadata.

---

# 52. INITIAL CURRENT EXECUTION FAILURE

Treat these as initial Current source execution failure:

```text
Current source missing
required Current method missing
CurrentStateStorageError
CurrentStateSchemaError
CurrentStateValidationError
sqlite3.Error
OSError
```

except `CurrentClientInventoryContextExpired`, which is not a valid initial-mode outcome.

If deadline remains:

```text
fallback to unknown context path
```

Use root:

```text
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
evaluated_at=T
scope=canonical scope if safely known else null
snapshot=null
```

Then historical unknown list.

If historical path fails:

```python
AdminQueryUnavailable
```

If deadline expires:

```python
AdminQueryDeadline
```

---

# 53. INITIAL SELECTOR→GATEWAY RETENTION RACE

If initial trusted gateway raises:

```python
AdminDeviceContextExpired
```

do not propagate cursor-expired.

If deadline remains:

```text
rerun list_devices_context in unknown mode
```

Root becomes exactly:

```text
overlay_mode=unknown
ordering_applied=false
source_execution_status=unavailable
evaluated_at=same T
scope=canonical safe scope if available
snapshot=null
```

All rows unknown.

Historical ordering.

No trusted cursor.

If has_more, issue a new signed unknown cursor.

---

# 54. UNKNOWN CONTINUATION

For signed:

```text
overlay_mode=unknown
```

Do NOT call any Current State read method.

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

Public root overlay is reconstructed strictly from signed chain fields.

Do not inspect newly published Current evidence.

If has_more:

```text
copy all chain metadata unchanged
update only last_* position fields
sign next cursor
```

---

# 55. TRUSTED CONTINUATION

For signed trusted cursor:

1. Require Current source and method present.

If absent:

```python
raise AdminQueryUnavailable
```

2. Deadline check.

3. Call:

```python
get_current_client_inventory_context(
    site_id,
    evaluated_at_utc=decoded.evaluated_at_utc,
    current_cycle_id=decoded.current_cycle_id,
    expected_source_scope_hash=decoded.source_scope_hash,
)
```

4. Map:

```text
CurrentClientInventoryContextExpired
→ AdminQueryCursorExpired

Current State storage/schema/I/O failure
→ AdminQueryUnavailable
```

5. Deadline check.

6. Require returned context:

```text
overlay_mode=trusted
same site
same evaluated_at
same cycle
same scope hash
```

Contradiction:

```python
AdminQueryIntegrityUnavailable
```

7. Call trusted `list_devices_context()` with signed keyset position.

8. Map:

```text
AdminDeviceContextExpired
→ AdminQueryCursorExpired

AdminDeviceSourceError
→ existing unavailable path
```

9. Public overlay metadata for continuation comes from the signed cursor chain, NOT from newly revalidated metadata.

Current revalidation is trust evidence only.

10. If has_more, update only last position and issue next signed cursor.

No cycle switch.

No trusted→unknown fallback.

---

# 56. ERROR TAXONOMY

Exact:

```text
bad/tampered context cursor
→ AdminQueryValidationError
→ 400 invalid_request

pinned trusted semantic context expired
→ AdminQueryCursorExpired
→ 400 cursor_expired

trusted gateway pinned-cycle guard missing
on continuation
→ AdminQueryCursorExpired
→ 400 cursor_expired

temporary Current source failure on continuation
→ AdminQueryUnavailable
→ 503 source_unavailable

temporary gateway/source failure
→ AdminQueryUnavailable
→ 503 source_unavailable

deadline exhaustion
→ AdminQueryDeadline
→ 503 query_deadline

serializer contradiction
→ AdminQueryIntegrityUnavailable
→ 503 source_unavailable

Feature ON but context config/codec unavailable
→ AdminQueryUnavailable
→ 503 source_unavailable
```

Do not modify routes.py; existing route error mapping already implements these public codes/statuses.

---

# 57. RUNTIME FIELDS

Add to `AdminWebRuntime`:

```python
device_list_context_config: DeviceListContextConfig | None = None
device_list_context_state: str = "disabled"
device_list_context_cursor_codec: Any | None = None
```

Allowed state:

```text
disabled
active
unavailable
```

---

# 58. RUNTIME CONTEXT CONFIGURATION

After base `AdminWebConfig` is successfully parsed:

Call:

```python
device_list_context_config_from_settings(
    settings,
    admin_config=config,
)
```

## Flag false

```text
state=disabled
codec=None
```

## Flag true + valid 64-char secret

Construct:

```python
DeviceListContextCursorCodec(
    secret_key=context_config.cursor_secret,
    maximum_length=config.max_cursor_chars,
)
```

Set:

```text
state=active
```

## Flag true + invalid secret

Catch only context config error.

Set:

```text
context_config=None
context_state=unavailable
codec=None
```

Log a sanitized context-configuration failure event.

Do not log the secret.

Do not make base Admin runtime unavailable.

---

# 59. RUNTIME CURRENT DB PATH EXTRACTION

Do NOT unconditionally access:

```text
current_state_read_service.repository
```

Existing tests/products legitimately use minimal Current State stubs.

Only when:

```python
config.device_list_context_enabled
```

resolve optional path safely.

Exact resolution order:

```python
current_state_db_path = None

if config.device_list_context_enabled:
    current_repository = getattr(
        current_state_read_service,
        "repository",
        None,
    )
    current_state_db_path = getattr(
        current_repository,
        "db_path",
        None,
    )

    if current_state_db_path is None:
        current_config = getattr(
            current_state_read_service,
            "config",
            None,
        )
        current_state_db_path = getattr(
            current_config,
            "db_path",
            None,
        )
```

Do not access it when Feature OFF.

A missing path does NOT invalidate base Admin runtime.

It simply means trusted gateway composition is unavailable; initial list can still fail-open unknown.

---

# 60. RUNTIME `_query_service(...)`

Extend internal `_query_service(...)` arguments with:

```text
device_list_context_state
device_list_context_cursor_codec
```

Pass optional Current path to:

```python
AdminDeviceReadGateway(
    registry_repository.config.db_path,
    visit_repository.db_path,
    current_state_db_path,
)
```

Pass to `AdminQueryService`:

```python
device_list_context_state=device_list_context_state,
device_list_context_cursor_codec=device_list_context_cursor_codec,
```

No `run.py` change.

---

# 61. PUBLIC RESULT SHAPE

Feature ON `AdminQueryResponse.result`:

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

Existing page envelope remains:

```python
{
    "limit": selected_limit,
    "next_cursor": next_cursor,
}
```

No additional page keys.

---

# 62. FOCUSED TESTING — CODER ONLY

Coder may run ONLY the tests listed below.

New modules may be run completely:

```bat
python -m pytest -q tests/admin_web/test_device_list_context_cursor.py

python -m pytest -q tests/admin_web/test_device_list_context_serialization.py
```

Existing larger modules must be restricted with `-k`:

```bat
python -m pytest -q tests/current_state/test_read_service.py -k "inventory_context"

python -m pytest -q tests/admin_web/test_device_gateway.py -k "device_list_context"

python -m pytest -q tests/admin_web/test_query_service.py -k "device_list_context"

python -m pytest -q tests/admin_web/test_runtime.py -k "device_list_context"

python -m pytest -q tests/admin_web/test_config.py -k "device_list_context"
```

Coder MUST NOT run the entire existing modules without `-k`.

---

# 63. REQUIRED CURSOR FOCUSED TESTS

New cursor tests must cover:

```text
trusted round-trip
unknown semantic round-trip
unknown source-unavailable round-trip

wrong secret
payload tamper
signature tamper

tamper:
overlay_mode
evaluated_at
cycle id
scope hash
online rank
device id
site
filter fingerprint

malformed separator
empty segment
invalid strict base64
wrong signature length
non-canonical JSON
extra field
missing field

wrong Site
wrong filter
wrong kind
wrong version
wrong ordering version

oversize input
server encode overflow

trusted invariants
unknown semantic invariants
unknown unavailable invariants

canonical sorted/deduplicated scope enforcement
trusted scope-hash coherence

encode rejects invalid dataclass before signing
```

All tests in this new file are permitted.

---

# 64. REQUIRED SERIALIZER FOCUSED TESTS

New serializer tests:

```text
exact item key set
exact root key set
exact overlay key set

trusted overlay
semantic unknown overlay
execution-unavailable overlay

explicit requested-Site validation
scope Site mismatch rejection
canonical scope rejection

hostname null preserved

online/offline/unknown validation
online_rank never exposed

counts/types

no latest_snapshot
no cycle id
no source scope hash

invalid timestamp sanitization
invalid source-scope timestamp sanitization

contradictory trusted overlay rejection
contradictory unknown overlay rejection
```

---

# 65. REQUIRED CURRENT READ-SERVICE FOCUSED TESTS

Names must contain:

```text
inventory_context
```

Cover only new method:

```text
initial fresh complete trusted
empty-client fresh complete still trusted
stale → unknown
unavailable → unknown
no complete → unknown
clock anomaly → unknown
invalid timestamp → unknown
invalid/untrusted scope → unknown

pinned same T/A/H → trusted
pinned missing → expired
configured scope changed → expired
pinned wrong Site/result/complete/scope → expired

partial pinned arguments → validation error
malformed pinned cycle/hash → validation error

storage/schema errors remain source errors
```

---

# 66. REQUIRED GATEWAY FOCUSED TESTS

Names must contain:

```text
device_list_context
```

Cover:

```text
unknown uses historical path/order
unknown requires no Current DB
hostname exact latest-Site raw hostname
hostname null remains null

trusted MAC present → online/rank0
trusted MAC absent → offline/rank1

global Online-first before limit

rank secondary ordering
trusted keyset predicate

exact MAC filter

Current-only MAC never inserted

same-transaction guard missing
→ AdminDeviceContextExpired

retention-race simulation
→ no false offline

temporary SQLite failure
→ AdminDeviceSourceError

old list_devices behavior unchanged
get_device semantics unchanged
```

No performance benchmark.

---

# 67. REQUIRED QUERY SERVICE FOCUSED TESTS

Names must contain:

```text
device_list_context
```

Cover:

```text
Feature OFF:
old decoder/path/DTO
no context codec
no Current descriptor

Feature ON unavailable state
→ AdminQueryUnavailable

context cursor decoded before Current read

initial trusted:
one descriptor call
one context gateway call
signed cursor

initial semantic unknown
→ unknown gateway
→ signed unknown cursor

initial Current source absent
→ unknown fail-open

initial Current source exception
→ unknown fail-open

initial AdminDeviceContextExpired
→ unknown fail-open
→ no trusted cursor

unknown continuation
→ zero Current calls
→ signed chain metadata preserved

trusted continuation
→ same signed T/A/H
→ semantic revalidation
→ gateway same A/H

new Current metadata on trusted continuation
does not replace signed public chain metadata

CurrentClientInventoryContextExpired
→ AdminQueryCursorExpired

AdminDeviceContextExpired continuation
→ AdminQueryCursorExpired

temporary Current source failure
→ AdminQueryUnavailable

cursor tamper
→ AdminQueryValidationError

serializer failure
→ AdminQueryIntegrityUnavailable

context encode overflow
→ AdminQueryUnavailable

deadline
→ AdminQueryDeadline
```

---

# 68. REQUIRED CONFIG/RUNTIME FOCUSED TESTS

Test names contain:

```text
device_list_context
```

Cover:

```text
Admin flag default=false

flag=true requires WEB_ADMIN_ENABLED=true

settings surface contains:
web_admin_device_list_context_enabled
web_admin_device_list_context_cursor_secret

feature off accepts empty secret

feature on accepts exactly 64 lowercase hex

reject:
empty
63 chars
65 chars
uppercase
non-hex

secret never appears in repr

runtime disabled:
state=disabled
codec=None

runtime active:
state=active
codec constructed

invalid secret:
context state unavailable
base Admin runtime active

Feature OFF:
does not inspect Current repository path

Feature ON:
Current repository db_path injected when available

Feature ON:
minimal/absent Current source does not crash base runtime
```

---

# 69. CODER SYNTAX CHECKS

Coder may run compile/syntax checks only for touched Python implementation files.

Use:

```bat
python -m py_compile app\admin_web\device_list_context_config.py
python -m py_compile app\admin_web\device_list_context_cursor.py
python -m py_compile app\admin_web\device_list_context_serialization.py
python -m py_compile app\admin_web\config.py
python -m py_compile app\admin_web\runtime.py
python -m py_compile app\admin_web\query_service.py
python -m py_compile app\admin_web\device_gateway.py
python -m py_compile app\current_state\read_service.py
```

Then:

```bat
git diff --check
```

---

# 70. CODER MUST NOT RUN

Coder must NOT run:

```text
Central Full Gate
lab-test-v6-fixed.cmd

entire repository pytest
entire existing large test modules

benchmark_device_gateway.py
any capacity benchmark

EXPLAIN QUERY PLAN acceptance

performance tests
cross-surface official regression

browser tests
visual tests

production smoke
production commands

deployment
```

Coder must NOT claim:

```text
TASK PASS
performance PASS
security acceptance PASS
merge ready
deploy ready
production ready
```

---

# 71. NO GIT PUBLICATION

Coder must NOT:

```text
commit
push
create PR
merge
rebase
deploy
```

Implementation remains a local working-tree candidate.

---

# 72. CODER HANDOFF

After implementation and narrow tests, provide exactly:

```text
TASK-DEVICE-LIST-CONTEXT-01
IMPLEMENTATION HANDOFF

BASELINE_SHA=
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

BASELINE_TREE=
edb5bab5479a4417d545429eeacf2b29a640e441

CHANGED_FILES=
<exact list>

NEW_FILES=
<exact list>

git diff --stat:
<output>

NARROW_TESTS:
<each exact command + result>

PY_COMPILE=
PASS/FAIL

git diff --check=
PASS/FAIL

CODER_ACCEPTANCE_CLAIM=
NONE

COMMIT=
NO

PUSH=
NO

PR=
NO

DEPLOY=
NO
```

Create patch:

```bat
git diff > TASK-DEVICE-LIST-CONTEXT-01-coder.patch
```

Return the patch with the handoff.

---

# 73. CODER STOP CONDITIONS

Immediately STOP and return exact evidence if:

```text
baseline SHA/tree differs
worktree is dirty before implementation

specified source object does not exist
actual source contract materially contradicts this TASK

implementation requires:
routes.py change
generic cursor v1 change
Current State model/schema/repository change
new index
new DB/cache
new collector/poller
run.py change
Traffic change
Device Current semantic change
frontend change
query-time Omada

Online-first cannot be achieved without schema/index change

same-transaction pinned-cycle proof cannot be achieved
inside authorized gateway boundary

HMAC contract cannot be implemented
without changing a forbidden security boundary

DTO/error contract conflicts with existing Admin infrastructure
```

On STOP:

```text
RETURN:
file
line/function
actual behavior
exact contradiction

DO NOT:
design workaround
expand scope
choose alternative
```

---

# 74. EXPLICITLY FORBIDDEN IMPLEMENTATIONS

Do not implement:

```text
list_current_clients() as Presence authority

N × get_current_client()

N × /devices/<id>/current

browser Online sorting
page-local Online sorting

Current-only Device insertion

historical Last Seen → Online/Offline
historical active → Online

stale/unavailable → Offline

Current Guest Traffic in list

new DB
new cache
new schema
new index

server-side cursor state cache

different signing algorithm
different secret source

unsigned context cursor

generic cursor modification

new endpoint

frontend polling
```

---

# 75. OWNER + TECH LEAD ACCEPTANCE — NOT CODER WORK

After handoff Owner + Tech Lead will separately perform:

```text
candidate identity verification

source review
Feature OFF differential

cross-surface regression

query-plan inspection
capacity/performance gate

large historical inventory
Current population bound

global Online-first acceptance
pagination race acceptance
retention race acceptance

cursor tamper/security acceptance

browser data acceptance

official PASS / FAIL / FIX
```

Coder does none of these under this TASK.

---

# 76. FINAL IMPLEMENTATION CONTRACT

```text
TASK=
TASK-DEVICE-LIST-CONTEXT-01

IMPLEMENTATION_READY=
YES

ARCHITECTURE=
FINAL-R2 ACCEPTED

BASELINE=
fd12f16c1f64900ce4096b3509a3b52d6bfe1b46

TREE=
edb5bab5479a4417d545429eeacf2b29a640e441

FEATURE_FLAG=
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED

SAFE_DEFAULT=
false

CURSOR_SECRET=
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET

CURSOR=
dedicated devices_context v1
HMAC-SHA-256
32-byte key
mandatory integrity

GENERIC CURSOR=
NO TOUCH

MEMBERSHIP=
historical Registry/Visit only

HOSTNAME=
latest requested-Site snapshot hostname
no fallback

PRESENCE=
online | offline | unknown

ONLINE-FIRST=
server-side before LIMIT

ORDER=
online_rank ASC
site_last_seen_at DESC
device_id DESC

CURRENT SELECTOR=
get_current_client_inventory_context

Current list_current_clients=
FORBIDDEN

TOCTOU=
same-transaction pinned-cycle structural proof

FEATURE OFF=
direct old path

INITIAL CURRENT FAILURE=
fail-open unknown where deadline permits

TRUSTED CONTINUATION FAILURE=
no silent downgrade

CODER PLAN=
FORBIDDEN

CODER TESTING=
NARROW ONLY

CODER GIT PUBLICATION=
FORBIDDEN

OWNER AUTHORIZATION=
REQUIRED BEFORE EDITING
```