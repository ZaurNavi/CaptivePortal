# TASK-DTI-NI-02B
## DEVICE-RELATIVE NETWORK METADATA PROJECTION
## + EXISTING VISITOR REGISTRY LATE `device_id` BINDING
### ARCHITECTURE CONTRACT v1
### IMPLEMENTATION-READY / FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Repository / production baseline:** `main@e32c695e53ffb2b173178189581751728c2ee0c2`  
**TREE:** `6348fe5fddb22f597ba8a6e40cf5f96a4d9d73ac`  
**Parent stage:** `TASK-DTI-NI-02A = PRODUCTION ACCEPTED / CLOSED`  
**Status:** `ARCHITECTURE CONTRACT v1 — READY FOR TECH LEAD REVIEW`  
**Coder:** `HOLD`  
**Implementation authorization:** `NO — until Tech Lead accepts this contract and issues implementation TASK`  
**Production activation:** `NO`

---

# 0. ARCHITECTURE RESULT

NI-02B V1 uses:

```text
MODEL A:
MATERIALIZED DEVICE NETWORK PROJECTION STORE
```

with a new independent auxiliary runtime:

```text
network-metadata-projection.service
```

and a new independent SQLite database:

```text
/opt/CaptivePortal/data/network_metadata_projection.sqlite3
```

NI-02B does **not** modify the NI-01 schema.

NI-02B does **not** modify the NI-02A authority schema.

NI-02B does **not** write Visitor Registry.

Canonical pipeline:

```text
NI-01 retained observation
        ↓
NI-01 internal projection-source read boundary
        ↓
exact observation Site + event_at + endpoints + capture/network scope
        ↓
NI-02A resolve_ipv4(site_id, endpoint_ipv4, event_at)
        ↓
0 / 1 / 2 independently resolved Site+MAC endpoint identities
        ↓
materialized DeviceNetworkMetadataEdgeV1
        ↓
Site+MAC current Registry-binding relation
        ↓
existing Visitor Registry device_id where authoritative
        ↓
DeviceNetworkMetadataReadService
        ↓
future NI-03
```

Primary permanent identity remains:

```text
site_id + client_mac
```

`device_id` remains a late authoritative attachment only.

---

# 1. FROZEN AUTHORITATIVE INPUTS

NI-02B V1 has exactly three authoritative input boundaries.

## 1.1 NI-01 observation authority

Authoritative for:

```text
observation_id
source_event_identity
source_event_family
source_generation_id
record_start_byte_offset

site_id
capture_source_id
network_scope_id
network_scope_state
capture_scope_binding_digest
capture-scope IPv4 CIDRs

event_at
ingested_at

src_ip
dst_ip
src_port
dst_port
transport_protocol
```

NI-02B does not parse raw EVE.

NI-02B does not read the Suricata source file.

NI-02B does not reconstruct NI-01 observations.

## 1.2 NI-02A temporal authority

Authoritative only for:

```text
site_id + IPv4 + event_at
→ Site + MAC
```

via:

```text
NetworkAttributionReadService.resolve_ipv4(...)
```

Accepted authority remains:

```text
trusted DHCPv4 ACK
finite temporal binding intervals
```

No alternative IP→MAC authority is admitted.

## 1.3 Visitor Registry identity authority

Authoritative only for:

```text
canonical MAC
→ existing Registry device_id
```

through the existing:

```text
VisitorRegistryReadService.get_device_by_mac(mac)
```

NI-02B does not generate `device_id`.

NI-02B does not call `build_device_id()`.

NI-02B does not use Registry `last_ip` or `last_site_id` as temporal evidence.

---

# 2. PHYSICAL TOPOLOGY — FROZEN

```text
Fingerprint Sensor process
    └─ existing NI-02A single writer
       → network_attribution.sqlite3

network-metadata.service
    └─ existing NI-01 single writer
       → network_metadata.sqlite3

captive-portal.service
    └─ existing Visitor Registry writer
       → visitor_registry.sqlite3

network-metadata-projection.service
    ├─ READ-ONLY NI-01
    ├─ READ-ONLY NI-02A
    ├─ READ-ONLY Visitor Registry
    └─ SINGLE WRITER
       → network_metadata_projection.sqlite3
```

No `ATTACH DATABASE` cross-store transaction.

No distributed transaction.

No upstream writer lock is acquired by NI-02B.

---

# 3. PROCESS OWNERSHIP — FROZEN

Writer owner:

```text
network-metadata-projection.service
```

Reader owner:

```text
DeviceNetworkMetadataReadService
```

may be instantiated by future NI-03 or other explicitly admitted internal consumers.

Single-writer invariant:

```text
exactly one process may own projection DB write lock
```

Writer lock path:

```text
<NETWORK_METADATA_PROJECTION_DB_PATH>.writer.lock
```

Default:

```text
/opt/CaptivePortal/data/network_metadata_projection.sqlite3.writer.lock
```

---

# 4. STARTUP / SHUTDOWN ORDERING — FROZEN

NI-02B is failure-isolated.

Systemd must NOT use:

```text
Requires=
BindsTo=
PartOf=
```

against:

```text
network-metadata.service
captive-portal.service
Fingerprint Sensor
```

Optional ordering-only `After=` is permitted, but upstream absence must not prevent NI-02B from reaching a bounded degraded state.

Startup sequence:

```text
1. parse NI-02B config;
2. if disabled → zero projection DB/write side effects;
3. acquire projection writer lock;
4. open/create exact projection schema V1;
5. quick_check / FK / exact schema validation;
6. create read-only upstream adapters;
7. establish or resume projection checkpoints;
8. perform bounded eligible backfill;
9. enter incremental poll/retry/reconciliation loop.
```

Shutdown:

```text
1. stop accepting new poll work;
2. finish or roll back current projection transaction;
3. leave committed checkpoint unchanged if transaction failed;
4. close projection DB;
5. release writer lock;
6. do not signal or stop any upstream component.
```

---

# 5. WHY A NEW STORE — FROZEN

The new store is required because:

```text
NI-01 schema V1 is frozen;
NI-01 writer must not synchronously depend on NI-02A/Registry;
NI-02B needs independent failure/rollback/capacity lifecycle;
NI-02B has different retention and late-binding semantics.
```

Therefore NI-02B MUST NOT add tables to:

```text
network_metadata.sqlite3
```

and MUST NOT add writes to:

```text
network_attribution.sqlite3
visitor_registry.sqlite3
```

---

# 6. NI-01 INTERNAL PROJECTION-SOURCE READ BOUNDARY — FROZEN

NI-02B MUST NOT perform arbitrary direct SQL against NI-01 from projection-domain code.

Introduce a read-only NI-01-owned internal boundary:

```text
NetworkMetadataProjectionSourceReadService
```

It is allowed to read sensitive endpoint rows strictly for NI-02B.

The existing:

```text
NetworkMetadataReadService
```

remains non-sensitive and unchanged as its public/read contract.

Required projection-source methods:

```text
list_source_generations()

read_projection_batch(
    source_generation_id,
    after_record_start_byte_offset,
    limit
)

get_projection_source_record(
    observation_id
)

get_source_progress(
    source_generation_id
)
```

Every SQLite connection from this boundary is:

```text
mode=ro
PRAGMA query_only=ON
foreign_keys=ON
bounded busy timeout
```

No NI-01 writes.

---

# 7. NetworkMetadataProjectionSourceRecordV1 — FROZEN

Exact internal source record:

```text
observation_id: str, non-null
source_event_identity: str, non-null
source_event_family: dns | tls | quic

source_generation_id: str, non-null
record_start_byte_offset: int >= 0

site_id: str, non-null
capture_source_id: str, non-null
network_scope_id: str, non-null
network_scope_state: within_intended_scope
capture_scope_binding_digest: str, non-null
capture_scope_ipv4_cidrs: tuple[str, ...], non-empty

event_at: canonical UTC timestamp
ingested_at: canonical UTC timestamp

sensitive_endpoint_presence_state:
    observed_retained
    not_observed
    expired

src_ip: canonical IP string | null
dst_ip: canonical IP string | null
src_port: int 0..65535 | null
dst_port: int 0..65535 | null
transport_protocol: TCP | UDP | null
```

If the NI-01 exact schema, FK, referenced capture binding, or source identity cannot be trusted:

```text
source read = unavailable
```

No best-effort projection.

---

# 8. NI-02A HORIZON READ EXTENSION — FROZEN

NI-02B may add one read-only method to the existing NI-02A read service:

```text
NetworkAttributionReadService.get_authority_horizon(site_id)
```

Exact result:

```text
NetworkAttributionHorizonV1

state:
    available
    unavailable

site_id: str

first_usable_at: timestamp | null
retained_from: timestamp | null

reason: str | null
```

No NI-02A schema change.

No NI-02A write.

This method exists only to bound backfill/rebuild eligibility.

Temporal endpoint identity still comes exclusively from:

```text
resolve_ipv4(...)
```

---

# 9. EXACT TEMPORAL ATTRIBUTION ENUM — FROZEN

NI-02B endpoint-level state:

```text
resolved
ambiguous
unattributed
unavailable
outside_historical_horizon
invalid
unsupported_address_family
endpoint_absent
```

Mapping:

```text
NI-02A resolved
→ resolved

NI-02A ambiguous
→ ambiguous

NI-02A unattributed
→ unattributed

NI-02A unavailable
→ unavailable

NI-02A outside_historical_horizon
→ outside_historical_horizon

NI-02A invalid
→ invalid

IPv6 endpoint
→ unsupported_address_family

missing endpoint
→ endpoint_absent
```

No additional attribution state is allowed in V1.

---

# 10. IPV6 — FROZEN

NI-02B V1:

```text
IPv6 temporal attribution = OUT OF SCOPE
```

For an IPv6 endpoint:

```text
temporal_attribution_state =
unsupported_address_family
```

NI-02A is not called.

No IPv4 identity is borrowed.

No IPv6 address may generate a Device edge.

IPv6 peer endpoint may still be represented as a peer endpoint on an edge whose device endpoint was independently resolved through IPv4.

---

# 11. ENDPOINT ATTRIBUTION ALGORITHM — FROZEN

For each retained NI-01 observation:

```text
src
and
dst
```

are evaluated independently.

For each endpoint:

```text
if IP is null:
    endpoint_absent

elif IP version == 6:
    unsupported_address_family

elif IP version == 4:
    call:
    resolve_ipv4(
        observation.site_id,
        endpoint_ipv4,
        observation.event_at
    )
```

`event_at` is always the NI-01 observation event time.

Never use:

```text
ingested_at
projected_at
current clock
nearest binding
newest binding
Registry last_ip
```

as temporal identity time.

---

# 12. SCOPE/AUTHORITY CONSISTENCY — FROZEN

If NI-02A returns:

```text
resolved
```

for an endpoint whose IPv4 is not inside the exact NI-01 observation:

```text
capture_scope_ipv4_cidrs
```

then this is not silently accepted.

It is:

```text
projection conflict =
resolved_endpoint_outside_capture_scope
```

Reason:

```text
the NI-01 observation Site/network-scope authority
and the NI-02A Device population authority disagree.
```

No edge is emitted for that observation.

Checkpoint does not advance beyond that conflicting observation.

---

# 13. `invalid` ATTRIBUTION RESULT — FROZEN

For canonical NI-01 input, an NI-02A result:

```text
invalid
```

is a contract inconsistency.

Disposition:

```text
projection conflict =
attribution_query_contract_invalid
```

No edge.

No checkpoint advance beyond the record.

Do not downgrade it to ordinary unattributed.

---

# 14. 0 / 1 / 2 EDGE RULE — FROZEN

Edge emission is per independently resolved endpoint.

```text
0 resolved endpoints
→ 0 edges

1 resolved endpoint
→ 1 edge

2 resolved endpoints
→ 2 edges
```

A non-resolved peer does NOT block an independently resolved device endpoint, except where the peer produces a structural conflict state `invalid`.

Specifically:

```text
peer ambiguous
peer unattributed
peer outside_historical_horizon
peer unsupported_address_family
peer endpoint_absent
→ resolved device edge is still emitted

peer unavailable
→ resolved device edge is emitted immediately
→ unavailable peer role enters retry queue
```

No heuristic dedup.

---

# 15. LOCAL DEVICE↔DEVICE — FROZEN

If both endpoints resolve:

```text
src → Site+MAC A
dst → Site+MAC B
```

then exactly two edges are emitted:

```text
edge A:
device_endpoint_role=src

edge B:
device_endpoint_role=dst
```

This remains true if:

```text
MAC A == MAC B
```

because roles are distinct.

No cross-MAC merge occurs.

---

# 16. ENDPOINT REPRESENTATION — FROZEN

`device_endpoint` exact shape:

```text
ip: canonical IPv4 string, non-null
port: int 0..65535 | null
transport_protocol: TCP | UDP | null
```

`peer_endpoint` exact shape:

```text
ip: canonical IPv4/IPv6 string | null
port: int 0..65535 | null
transport_protocol: TCP | UDP | null
```

Constraint:

```text
peer_endpoint.ip == null
→ peer_endpoint.port must be null
```

Transport protocol is copied from the same NI-01 observation.

No DNS name.

No SNI.

No organization name.

No service label.

---

# 17. PEER SCOPE — FROZEN

`peer_scope` enum:

```text
local
external
unknown
```

Authoritative input is the exact NI-01:

```text
CaptureScopeBindingV1.ipv4_cidrs
```

for that observation.

Exact algorithm:

```text
peer IPv4 inside any admitted capture-scope CIDR
→ local

peer IPv4 outside all admitted capture-scope CIDRs
→ external

peer IPv6
or peer IP absent
→ unknown
```

Do NOT use:

```text
RFC1918
public/private address heuristic
default gateway guessing
DNS resolver guessing
routing table guessing
Internet reachability
```

`external` means:

```text
outside the admitted capture/network scope
```

It MUST NOT be re-labelled as:

```text
Internet
WAN
public Internet
```

without a later authority.

---

# 18. DIRECTION — FROZEN

`direction` enum:

```text
outbound
inbound
local
unknown
```

Exact algorithm:

```text
peer_scope=local
→ direction=local

peer_scope=external
AND device_endpoint_role=src
→ outbound

peer_scope=external
AND device_endpoint_role=dst
→ inbound

peer_scope=unknown
→ unknown
```

Direction means relative to the admitted capture/network scope.

It is not a WAN-routing claim.

---

# 19. REQUIRED CASES — FROZEN

## Guest Device → external endpoint

```text
device role=src
peer_scope=external
direction=outbound
```

## External endpoint → guest Device

```text
device role=dst
peer_scope=external
direction=inbound
```

## Guest Device A → Guest Device B

Both addresses belong admitted capture scope and both resolve:

```text
2 edges
peer_scope=local
direction=local
```

for both.

## Guest Device → gateway/resolver/local infrastructure

If infrastructure IPv4 is inside admitted capture-scope CIDRs:

```text
peer_scope=local
direction=local
```

If outside those CIDRs:

```text
peer_scope=external
```

which means only `outside admitted scope`, not Internet.

## Only one endpoint resolves

Exactly one Device edge.

## Neither resolves

Zero edges.

---

# 20. DeviceNetworkMetadataEdgeV1 — EXACT LOGICAL CONTRACT

```text
edge_id: 64-char lowercase SHA-256 hex
schema_version: 1

site_id: str

device_id: canonical existing Registry UUID | null
client_mac: canonical MAC

identity_binding_state:
    authoritative
    not_yet_registry_resolved
    registry_unavailable

identity_binding_evaluated_at: timestamp
device_id_bound_at: timestamp | null

event_at: timestamp
projected_at: timestamp

device_endpoint:
    ip: IPv4 string
    port: int | null
    transport_protocol: TCP | UDP | null

peer_endpoint:
    ip: IPv4/IPv6 string | null
    port: int | null
    transport_protocol: TCP | UDP | null

device_endpoint_role:
    src
    dst

peer_scope:
    local
    external
    unknown

direction:
    outbound
    inbound
    local
    unknown

source_observation_ref: observation_id
source_event_identity: str
source_event_family:
    dns
    tls
    quic

source_generation_id: str
capture_source_id: str

network_scope_id: str
network_scope_state:
    within_intended_scope

capture_scope_binding_digest: str

attribution_state:
    resolved

attribution_source:
    trusted_dhcp_v4

attribution_binding_id: str
attribution_valid_from: timestamp
attribution_valid_until: timestamp

peer_attribution_state:
    resolved
    ambiguous
    unattributed
    unavailable
    outside_historical_horizon
    invalid
    unsupported_address_family
    endpoint_absent

peer_attribution_binding_id: str | null

projection_contract_version: 1
projection_algorithm_version:
    dti-ni-02b-projection-v1

projection_run_id: str
```

For every V1 edge:

```text
attribution_state MUST equal resolved
```

Non-resolved endpoint states do not create Device edges.

---

# 21. EDGE IDENTITY — FROZEN

`edge_id` does not include Registry `device_id`.

Exact bytes:

```text
UTF-8(
    "device-network-metadata-edge-v1"
    + "\0"
    + observation_id
    + "\0"
    + device_endpoint_role
)
```

Then:

```text
edge_id =
lowercase SHA-256 hex of those exact bytes
```

Consequences:

```text
same observation + src
→ same edge_id

same observation + dst
→ different edge_id

Registry late binding
→ does not change edge_id

replay
→ does not create another edge
```

---

# 22. EDGE SEMANTIC DIGEST — FROZEN

Projection store persists:

```text
edge_semantic_digest
```

SHA-256 over canonical JSON of all immutable edge fields except:

```text
device_id
identity_binding_state
identity_binding_evaluated_at
device_id_bound_at
projected_at
projection_run_id
edge_semantic_digest
```

Registry binding is intentionally excluded because it is late-bound through a separate relation.

---

# 23. IDEMPOTENCY — FROZEN

On replay:

```text
edge_id absent
→ insert edge

edge_id present
AND semantic digest identical
→ idempotent no-op

edge_id present
AND semantic digest differs
→ projection_semantic_conflict
```

No second edge version is silently inserted.

No old edge is silently overwritten.

---

# 24. PROJECTION CONFLICT ENUM — FROZEN

Exact conflict reasons:

```text
source_observation_identity_conflict
resolved_endpoint_outside_capture_scope
attribution_query_contract_invalid
edge_semantic_conflict
registry_identity_conflict
checkpoint_source_conflict
```

Conflict behavior:

```text
projection runtime state = blocked_conflict
offending source-generation checkpoint does not advance
existing committed edges remain readable
upstream services continue unchanged
```

No heuristic conflict repair.

---

# 25. PROJECTION CONTRACT / ALGORITHM VERSIONING — FROZEN

Projection contract:

```text
projection_contract_version = 1
```

Algorithm:

```text
projection_algorithm_version =
dti-ni-02b-projection-v1
```

Projection DB schema:

```text
user_version = 1
```

A store created under another algorithm/version is not silently mixed.

Future algorithm change requires:

```text
separate architecture decision
and either explicit migration
or controlled derived-store rebuild
```

No mixed algorithm versions in one V1 active projection store.

---

# 26. VISITOR REGISTRY AUTHORITY RULE — FROZEN

Exact canonical lookup:

```text
VisitorRegistryReadService.get_device_by_mac(
    canonical client_mac
)
```

is sufficient Registry identity authority.

Site membership is NOT re-proven from Registry.

Reason:

```text
Site membership at event time is already established
by Site-scoped NI-02A temporal attribution.
```

Forbidden as Site authority:

```text
Visitor Registry last_site_id
Visitor Registry last_ip
latest Registry snapshot Site
```

---

# 27. SAME DEVICE ACROSS MULTIPLE SITES — FROZEN

One existing Registry `device_id` MAY legitimately appear on Device edges from multiple Sites only when:

```text
the exact same canonical MAC
has an independently resolved NI-02A Site+MAC binding
for each observation/Site.
```

This is not a cross-MAC merge.

Every edge remains Site-scoped.

---

# 28. REGISTRY BINDING STATES — FROZEN

Exact enum:

```text
authoritative
not_yet_registry_resolved
registry_unavailable
```

## authoritative

Only when:

```text
Registry read boundary is readable
AND exact canonical MAC lookup returns a row
AND row.mac equals requested canonical MAC
AND returned device_id is a valid existing Registry device_id
```

## not_yet_registry_resolved

When:

```text
Registry read boundary is readable
AND exact canonical MAC lookup returns no row
```

This does not mean the Device will never exist.

## registry_unavailable

When:

```text
Registry read boundary cannot be trusted/read
or exact Registry schema/read operation fails
```

It is not temporal `unattributed`.

---

# 29. PRE-REGISTRY STATE — FROZEN

Accepted conceptual state is frozen:

```text
not_yet_registry_resolved
```

When temporal attribution resolves:

```text
Site + MAC
```

but Registry has no Device row:

```text
edge is stored immediately

client_mac = authoritative MAC

device_id = null

identity_binding_state =
not_yet_registry_resolved
```

Durable pre-Registry identity:

```text
site_id + client_mac
```

No observation is dropped.

No Device is invented.

---

# 30. PHYSICAL LATE-BINDING NORMALIZATION — FROZEN

`device_network_metadata_edges` does NOT store mutable `device_id`.

Physical late binding is normalized into:

```text
projection_registry_identities

projection_site_mac_bindings

projection_registry_binding_events
```

Logical `DeviceNetworkMetadataEdgeV1.device_id` and `identity_binding_state` are produced by read-time join inside the projection store only.

This is not query-time Registry reconstruction.

---

# 31. STRUCTURAL NO-CROSS-MAC MERGE — FROZEN

`projection_registry_identities` has:

```text
device_id PRIMARY KEY
client_mac UNIQUE NOT NULL
```

Therefore one projection-local authoritative Registry identity cannot map:

```text
one device_id → two MACs
or
one MAC → two device_ids
```

`projection_site_mac_bindings` has:

```text
PRIMARY KEY(site_id, client_mac)
```

and authoritative rows reference:

```text
projection_registry_identities(device_id)
```

Multiple Sites may reference the same identity only with the same canonical MAC.

---

# 32. LATE BINDING MECHANISM — FROZEN

Mechanism:

```text
immediate lookup on first retained Site+MAC edge
+
periodic bounded reconciliation
```

No Registry-triggered writes.

No on-read Registry lookup.

No Device Card reconstruction.

---

# 33. REGISTRY RECONCILIATION — FROZEN

Every:

```text
60 seconds
```

the projection writer reconciles at most:

```text
500 Site+MAC binding rows
```

ordered by:

```text
last_evaluated_at ASC,
site_id ASC,
client_mac ASC
```

This includes unresolved rows first.

Authoritative rows may be revisited in bounded rotation for conflict detection but their established binding is monotonic.

---

# 34. LATE AUTHORITATIVE BINDING — FROZEN

When a previously unresolved Site+MAC later returns a valid Registry row:

one projection-store transaction:

```text
1. verify global device_id↔MAC structural consistency;

2. insert/reuse projection_registry_identities;

3. update projection_site_mac_bindings:
   binding_state=authoritative
   device_id=<existing Registry device_id>
   authoritative_bound_at=<now>
   last_evaluated_at=<now>;

4. append immutable registry-binding event.
```

No edge row is rewritten.

No NI-01 row is rewritten.

No NI-02A row is rewritten.

---

# 35. REGISTRY RECORD DISAPPEARS LATER — FROZEN

Once:

```text
device_id + MAC
```

has been authoritatively established for a retained projection identity, the binding is monotonic during the retained projection horizon.

If later Registry lookup:

```text
returns no row
or Registry is temporarily unavailable
```

NI-02B:

```text
does NOT delete the established device_id
does NOT downgrade the historical authoritative binding
does NOT invent another identity
records Registry health degradation / missing-current-evidence telemetry
```

Reason:

```text
Visitor Registry V1 has no authoritative identity-revocation/tombstone contract.
```

A different device_id for the same MAC or the same device_id for a different MAC is:

```text
registry_identity_conflict
```

and blocks projection writes fail-closed.

---

# 36. REGISTRY PROVENANCE — FROZEN

Authoritative binding records retain:

```text
registry_schema_version = 1
registry_device_id
registry_client_mac
registry_record_updated_at if present
binding_evaluated_at
authoritative_bound_at
projection_run_id
```

No Registry raw JSON.

No snapshot body duplication.

---

# 37. TEMPORAL ATTRIBUTION VS REGISTRY IDENTITY — FROZEN

The two dimensions are permanently separate.

Example:

```text
temporal attribution = resolved
registry binding = not_yet_registry_resolved
```

is fully valid.

Example:

```text
temporal attribution = resolved
registry binding = registry_unavailable
```

is fully valid.

Neither may be represented as:

```text
unattributed
```

---

# 38. TRANSIENT PROJECTION RESULT — FROZEN

For processing/QA, NI-02B defines:

```text
NetworkMetadataProjectionResultV1
```

with:

```text
observation_id

src_attribution_state
dst_attribution_state

emitted_edge_count: 0 | 1 | 2

projection_state:
    complete
    pending
    partial_pending
    terminal_no_edge
    expired_unresolved
    conflict

safe_reason: str | null
```

This is an internal result/telemetry contract.

It is not a Device edge.

---

# 39. PROJECTION STATE PRECEDENCE — FROZEN

```text
structural conflict
→ conflict

otherwise
any endpoint unavailable
AND emitted_edge_count=0
→ pending

otherwise
any endpoint unavailable
AND emitted_edge_count>0
→ partial_pending

otherwise
emitted_edge_count>0
→ complete

otherwise
→ terminal_no_edge
```

If a pending retry can no longer be evaluated because the mandatory sensitive source dependency expired:

```text
expired_unresolved
```

Previously emitted edge remains until its own retention cutoff.

---

# 40. UNAVAILABLE ATTRIBUTION RETRY — FROZEN

Only endpoint state:

```text
unavailable
```

is retryable in V1.

Not retried as an attribution outcome:

```text
ambiguous
unattributed
outside_historical_horizon
unsupported_address_family
endpoint_absent
```

`invalid` is conflict, not retry.

Pending rows store no raw endpoint IP.

They store only enough identity to re-read the original NI-01 observation:

```text
observation_id
site_id
source_generation_id
record_start_byte_offset
pending endpoint roles
first_pending_at
last_attempt_at
next_retry_at
```

---

# 41. ATTRIBUTION RETRY CADENCE — FROZEN

Retry interval:

```text
30 seconds
```

Maximum pending observations per retry pass:

```text
500
```

On retry, endpoint data is re-read from NI-01 through:

```text
get_projection_source_record(observation_id)
```

No raw endpoint copy is retained in the pending queue.

---

# 42. MATERIALIZED STORE SCHEMA V1 — FROZEN

Exact logical tables:

```text
network_metadata_projection_schema

projection_runs

device_network_metadata_edges

projection_registry_identities

projection_site_mac_bindings

projection_registry_binding_events

projection_source_checkpoints

projection_pending_attribution

projection_runtime_state
```

No other persistent table is required by V1.

---

# 43. `network_metadata_projection_schema` — FROZEN

Exactly one singleton row:

```text
singleton_id = 1

schema_version = 1

projection_contract_version = 1

projection_algorithm_version =
dti-ni-02b-projection-v1

created_at_utc
```

`PRAGMA user_version=1`.

---

# 44. `projection_runs` — FROZEN

Fields:

```text
projection_run_id TEXT PRIMARY KEY

started_at_utc TEXT NOT NULL

repository_head TEXT NOT NULL
repository_tree TEXT NOT NULL

projection_contract_version INTEGER NOT NULL CHECK(...=1)

projection_algorithm_version TEXT NOT NULL
CHECK(...='dti-ni-02b-projection-v1')

configuration_digest TEXT NOT NULL
```

No raw endpoint data.

---

# 45. `device_network_metadata_edges` — FROZEN

Physical immutable fields:

```text
edge_id TEXT PRIMARY KEY

schema_version INTEGER NOT NULL CHECK(schema_version=1)

site_id TEXT NOT NULL
client_mac TEXT NOT NULL

event_at TEXT NOT NULL
source_ingested_at TEXT NOT NULL
projected_at TEXT NOT NULL

device_endpoint_role TEXT NOT NULL
CHECK(device_endpoint_role IN ('src','dst'))

device_ip TEXT NOT NULL
device_port INTEGER NULL
CHECK(device_port IS NULL OR device_port BETWEEN 0 AND 65535)

peer_ip TEXT NULL
peer_port INTEGER NULL
CHECK(peer_port IS NULL OR peer_port BETWEEN 0 AND 65535)
CHECK(peer_ip IS NOT NULL OR peer_port IS NULL)

transport_protocol TEXT NULL
CHECK(transport_protocol IS NULL OR transport_protocol IN ('TCP','UDP'))

peer_scope TEXT NOT NULL
CHECK(peer_scope IN ('local','external','unknown'))

direction TEXT NOT NULL
CHECK(direction IN ('outbound','inbound','local','unknown'))

source_observation_ref TEXT NOT NULL
source_event_identity TEXT NOT NULL
source_event_family TEXT NOT NULL
CHECK(source_event_family IN ('dns','tls','quic'))

source_generation_id TEXT NOT NULL
record_start_byte_offset INTEGER NOT NULL CHECK(...>=0)

capture_source_id TEXT NOT NULL
network_scope_id TEXT NOT NULL

network_scope_state TEXT NOT NULL
CHECK(network_scope_state='within_intended_scope')

capture_scope_binding_digest TEXT NOT NULL

attribution_state TEXT NOT NULL
CHECK(attribution_state='resolved')

attribution_source TEXT NOT NULL
CHECK(attribution_source='trusted_dhcp_v4')

attribution_binding_id TEXT NOT NULL
attribution_valid_from TEXT NOT NULL
attribution_valid_until TEXT NOT NULL

peer_attribution_state TEXT NOT NULL
peer_attribution_binding_id TEXT NULL

projection_contract_version INTEGER NOT NULL CHECK(...=1)

projection_algorithm_version TEXT NOT NULL
CHECK(...='dti-ni-02b-projection-v1')

projection_run_id TEXT NOT NULL
REFERENCES projection_runs(projection_run_id)

edge_semantic_digest TEXT NOT NULL
```

Unique constraint:

```text
UNIQUE(source_observation_ref, device_endpoint_role)
```

This guarantees maximum two edges per observation.

---

# 46. EDGE IMMUTABILITY — FROZEN

`device_network_metadata_edges` has triggers:

```text
BEFORE UPDATE
→ abort immutable projection edge

BEFORE DELETE
→ permitted only through controlled retention owner
```

V1 implementation may use an explicit retention-authorized repository delete path.

Application/business code must not update an edge.

Registry late binding never updates this table.

---

# 47. `projection_registry_identities` — FROZEN

Fields:

```text
device_id TEXT PRIMARY KEY
client_mac TEXT NOT NULL UNIQUE

registry_schema_version INTEGER NOT NULL CHECK(...=1)

first_bound_at TEXT NOT NULL
last_verified_at TEXT NOT NULL

registry_record_updated_at TEXT NULL
```

No Site field here because Registry identity is global-by-MAC.

---

# 48. `projection_site_mac_bindings` — FROZEN

Fields:

```text
site_id TEXT NOT NULL
client_mac TEXT NOT NULL

binding_state TEXT NOT NULL
CHECK(binding_state IN (
    'authoritative',
    'not_yet_registry_resolved',
    'registry_unavailable'
))

device_id TEXT NULL
REFERENCES projection_registry_identities(device_id)

first_edge_at TEXT NOT NULL
last_edge_at TEXT NOT NULL

last_evaluated_at TEXT NOT NULL
authoritative_bound_at TEXT NULL

last_safe_reason TEXT NULL

PRIMARY KEY(site_id, client_mac)

CHECK(
    (binding_state='authoritative'
     AND device_id IS NOT NULL
     AND authoritative_bound_at IS NOT NULL)
    OR
    (binding_state IN (
        'not_yet_registry_resolved',
        'registry_unavailable'
     )
     AND device_id IS NULL
     AND authoritative_bound_at IS NULL)
)
```

Once authoritative, V1 does not downgrade it.

---

# 49. `projection_registry_binding_events` — FROZEN

Append-only transition/provenance table:

```text
binding_event_id INTEGER PRIMARY KEY

site_id TEXT NOT NULL
client_mac TEXT NOT NULL

previous_state TEXT NULL
new_state TEXT NOT NULL

device_id TEXT NULL

evaluated_at TEXT NOT NULL

registry_schema_version INTEGER NULL
registry_record_updated_at TEXT NULL

safe_reason TEXT NULL

projection_run_id TEXT NOT NULL
```

No raw Registry JSON.

No IP.

---

# 50. `projection_source_checkpoints` — FROZEN

One row per NI-01 source generation:

```text
source_generation_id TEXT PRIMARY KEY

last_record_start_byte_offset INTEGER NOT NULL
CHECK(...>=0)

last_observation_id TEXT NULL

last_source_ingested_at TEXT NULL

updated_at_utc TEXT NOT NULL
```

Checkpoint identity:

```text
source_generation_id
+
record_start_byte_offset
```

No event-time checkpoint.

No heuristic event identity.

---

# 51. `projection_pending_attribution` — FROZEN

Fields:

```text
observation_id TEXT PRIMARY KEY

site_id TEXT NOT NULL

source_generation_id TEXT NOT NULL
record_start_byte_offset INTEGER NOT NULL

event_at TEXT NOT NULL
source_ingested_at TEXT NOT NULL

pending_src INTEGER NOT NULL CHECK(IN (0,1))
pending_dst INTEGER NOT NULL CHECK(IN (0,1))

first_pending_at TEXT NOT NULL
last_attempt_at TEXT NOT NULL
next_retry_at TEXT NOT NULL

CHECK(pending_src=1 OR pending_dst=1)
```

No endpoint IP/port.

No DNS/SNI.

---

# 52. `projection_runtime_state` — FROZEN

Singleton current operational state:

```text
singleton_id = 1

runtime_state:
    initializing
    usable
    degraded
    source_unavailable
    attribution_unavailable
    registry_degraded
    capacity_halted
    blocked_conflict
    stopping

safe_reason TEXT NULL

last_source_poll_at TEXT NULL
last_projection_commit_at TEXT NULL
last_registry_reconcile_at TEXT NULL
last_retention_at TEXT NULL

pending_attribution_count INTEGER NOT NULL

blocked_observation_id TEXT NULL

updated_at_utc TEXT NOT NULL
```

This is operational state, not Device identity authority.

---

# 53. REQUIRED INDEXES — FROZEN

At minimum:

```text
device_network_metadata_edges
(site_id,event_at,edge_id)

device_network_metadata_edges
(site_id,client_mac,event_at,edge_id)

device_network_metadata_edges
(source_observation_ref,device_endpoint_role)

projection_site_mac_bindings
(binding_state,last_evaluated_at,site_id,client_mac)

projection_registry_identities
(client_mac)

projection_registry_binding_events
(site_id,client_mac,evaluated_at,binding_event_id)

projection_pending_attribution
(next_retry_at,observation_id)

projection_source_checkpoints
(updated_at_utc,source_generation_id)
```

No index containing DNS/SNI because NI-02B does not store them.

---

# 54. PROJECTION TRANSACTION BOUNDARY — FROZEN

For one incremental source batch, a single projection DB transaction contains:

```text
new idempotent edges

new/update Site+MAC binding rows

new Registry binding events where applicable

pending-attribution upserts/deletes

source checkpoint advancement

runtime-state update needed for successful commit
```

Checkpoint advances only with the corresponding projection disposition.

Crash before commit:

```text
no checkpoint advance
replay source batch
```

Crash after commit:

```text
checkpoint and edges are already durable
replay is idempotent
```

---

# 55. SOURCE ORDERING — FROZEN

Source generation discovery order:

```text
NI-01 generation opened_at_utc ASC
source_generation_id ASC
```

Within one generation:

```text
record_start_byte_offset ASC
```

Projection identity never uses current SQLite `rowid`.

---

# 56. SOURCE GENERATION HANDLING — FROZEN

Each NI-01 source generation has an independent projection checkpoint.

Closed source generation:

```text
continues processing until all retained source records
past its checkpoint are consumed
```

New source generation:

```text
gets its own checkpoint row
```

Rotation does not reset previously processed generations.

---

# 57. LATE NI-01 EVENT HANDLING — FROZEN

A source event delivered after NI-02B activation is discovered by its NI-01:

```text
source_generation_id
record_start_byte_offset
```

regardless of `event_at`.

Temporal attribution always uses:

```text
event_at
```

Therefore a late-delivered old observation may resolve to:

```text
resolved
outside_historical_horizon
unavailable
...
```

according to NI-02A authority at that exact event time.

No attribution is fabricated from delivery time.

---

# 58. INITIAL BACKFILL — FROZEN

NI-02B V1 performs bounded backfill.

Backfill does not modify NI-01 or NI-02A.

Per Site, an observation is edge-materialization eligible only when:

```text
sensitive_endpoint_presence_state =
observed_retained

AND

event_at >= NI-02A first_usable_at

AND

event_at >= NI-02A retained_from

AND

the NI-01 sensitive endpoint row is still retained
```

Because NI-01 sensitive retention is 14 days and NI-02A is 30 days, the practical maximum edge rebuild horizon is bounded by the 14-day sensitive dependency.

---

# 59. BEFORE NI-02A FIRST USABLE — FROZEN

Observation with:

```text
event_at < first_usable_at
```

receives no historical Device edge.

No historical IP→MAC inference.

During initial backfill it may be skipped after checkpoint accounting.

If encountered as a late incremental observation:

```text
endpoint state =
outside_historical_horizon
```

or the exact NI-02A returned state.

---

# 60. INSIDE AUTHORITY HORIZON — FROZEN

For an eligible observation:

```text
call NI-02A independently for each IPv4 endpoint
```

and apply the exact 0/1/2-edge algorithm.

---

# 61. COVERAGE GAP — FROZEN

If NI-02A returns:

```text
unavailable
```

because source coverage is not authoritative for the endpoint/event time:

```text
do not emit an edge for that endpoint
do not convert it to unattributed
persist pending retry
```

An independently resolved opposite endpoint still emits its edge.

---

# 62. PENDING RETRY EXPIRY — FROZEN

A retry remains eligible only while the original NI-01 sensitive endpoint dependency is still available.

When NI-01 endpoint data expires under its 14-day policy before attribution becomes authoritative:

```text
pending row is removed

projection result state =
expired_unresolved

no Device edge is invented
```

No retry stores a private copy of the expired peer IP.

---

# 63. REBUILD HORIZON — FROZEN

A Device edge is deterministically rebuildable only while all mandatory facts remain available:

```text
NI-01 core observation
NI-01 sensitive endpoint
NI-01 capture-scope binding
NI-02A temporal binding/coverage authority
projection algorithm v1
```

Registry is not mandatory to rebuild the Site+MAC edge because pre-Registry edge is valid.

Therefore:

```text
maximum raw-edge rebuild horizon =
intersection of dependencies

and never exceeds
NI-01 sensitive retention = 14 days
```

No edge claims rebuildability after a mandatory dependency expired.

---

# 64. SENSITIVE RETENTION — FROZEN

`DeviceNetworkMetadataEdgeV1` contains remote endpoint IP/port and is:

```text
SensitiveNetworkMetadata
```

Edge retention MUST NOT exceed NI-01 sensitive endpoint retention.

Exact edge expiry condition mirrors NI-01:

```text
if event_at < now-14d
OR source_ingested_at < now-14d
→ edge eligible for deletion
```

`projected_at` never extends retention.

Late Registry binding never extends retention.

---

# 65. OTHER PROJECTION RETENTION — FROZEN

```text
edges:
14 days max

pending attribution:
no later than source sensitive endpoint availability;
hard max 14 days by source event/ingest age

Registry binding events:
30 days max

Site+MAC binding rows:
retain only while referenced by at least one retained edge
or pending attribution relation requiring that identity;
otherwise eligible for cleanup

projection registry identities:
retain only while referenced by retained Site+MAC bindings

projection runs:
90 days max when no retained row references the run

source checkpoints:
retain while corresponding NI-01 generation is still visible
or within NI-01 lineage horizon;
or until safe cleanup proves no retained source row can reappear
```

No derived raw peer endpoint survives beyond 14 days.

---

# 66. RETENTION CLEANUP — FROZEN

Cleanup cadence:

```text
3600 seconds
```

Batch size:

```text
5000 rows
```

Maximum batches per cleanup pass:

```text
20
```

Cleanup ordering:

```text
1. expired edges
2. expired pending rows
3. orphan Site+MAC binding rows
4. orphan Registry identity rows
5. old binding events
6. unreferenced old projection runs
7. safely obsolete checkpoints
```

Cleanup cannot override a capacity halt by deleting identity evidence needed to explain committed live edges.

---

# 67. READ BOUNDARY FOR NI-03 — FROZEN

Introduce:

```text
DeviceNetworkMetadataReadService
```

It reads only:

```text
network_metadata_projection.sqlite3
```

It does NOT call:

```text
NI-02A
Visitor Registry
raw EVE
NI-01 sensitive table directly
```

Late-binding reconstruction is already materialized in projection-local binding tables.

---

# 68. READ METHOD — BY DEVICE_ID — FROZEN

```text
list_edges_by_device(
    site_id,
    device_id,
    from_utc,
    to_utc,
    *,
    limit,
    cursor
)
```

Constraints:

```text
Site required
device_id required
window >0 and <=14 days
limit 1..500
order by event_at, edge_id
keyset cursor=(event_at,edge_id)
```

Only edges whose current projection-local binding is:

```text
authoritative
AND device_id matches
```

are returned.

---

# 69. READ METHOD — BY PRE-REGISTRY MAC — FROZEN

```text
list_edges_by_mac(
    site_id,
    client_mac,
    from_utc,
    to_utc,
    *,
    limit,
    cursor
)
```

Same bounded window/pagination.

This is the canonical infrastructure read for:

```text
pre-Registry Site+MAC identity
```

It remains usable after later binding; returned logical rows then include the authoritative `device_id`.

---

# 70. READ METHOD — BY SOURCE OBSERVATION — FROZEN

```text
list_edges_by_observation(
    site_id,
    observation_id
)
```

Returns:

```text
0, 1 or 2 edges
```

ordered:

```text
src
then dst
```

No missing-edge interpretation is permitted without projection health/context.

---

# 71. READ SERVICE STATUS — FROZEN

```text
get_status()
```

returns safe operational status only:

```text
enabled
store_state
runtime_state
safe_reason

schema_version
projection_contract_version
projection_algorithm_version

last_projection_commit_at
last_registry_reconcile_at

pending_attribution_count

checkpoint_count

db_bytes
capacity_limit_bytes
```

No raw IP/MAC/DNS/SNI.

---

# 72. QUERY SAFETY — FROZEN

All read queries are:

```text
Site-scoped
bounded
set-based
read-only
keyset-paginated
```

No offset pagination for Device edge history.

No query window beyond 14 days.

No cross-Site `device_id` query without explicit Site.

---

# 73. FUTURE NI-03 SOURCE PAYLOAD — FROZEN BOUNDARY

NI-02B stores:

```text
source_observation_ref
source_event_family
```

but does not duplicate:

```text
DNS names
DNS answers
SNI
ALPN payloads
```

Future NI-03 may use the source reference through an explicitly admitted NI-01 read boundary.

NI-03 MUST NOT read raw EVE.

---

# 74. FUTURE DEVICE CARD PRIVACY — FROZEN

NI-02B does not create any Admin/UI endpoint.

Future Device Card must not expose raw:

```text
remote IP history
remote ports
DNS names
SNI
```

merely because NI-02B can associate them with a Device.

Any Device Card presentation requires a separate NI-03/UI privacy contract.

---

# 75. NI-01 UNAVAILABLE — FROZEN

If NI-01 read boundary is unavailable:

```text
no checkpoint advancement
no fabricated empty projection
runtime state = source_unavailable
existing projection edges remain readable
```

NI-01 writer is not affected.

---

# 76. NI-02A UNAVAILABLE — FROZEN

If NI-02A is unavailable:

For new IPv4 endpoint attribution:

```text
state=unavailable
pending retry
```

An independently resolved endpoint from the same observation may still commit if already resolved in the same evaluation before the unavailable peer result.

No "unattributed" substitution.

NI-02A writer/sensor is not affected.

---

# 77. REGISTRY UNAVAILABLE — FROZEN

Registry outage:

```text
does NOT stop edge materialization
does NOT block checkpoint
```

New Site+MAC edges receive:

```text
identity_binding_state =
registry_unavailable

device_id =
null
```

Periodic reconciliation resumes automatically.

---

# 78. PROJECTION STORE UNAVAILABLE — FROZEN

If projection DB cannot be trusted/written:

```text
projection service becomes unavailable
no source checkpoint advances
no upstream write/change
```

NI-01, NI-02A, Registry, Fingerprint, CAPPORT and Authorization continue.

---

# 79. CAPACITY HALT — FROZEN

Projection capacity is fail-closed for projection writes.

When safe headroom cannot be guaranteed:

```text
runtime_state=capacity_halted

failed batch checkpoint advance=0

existing committed reads remain available where DB itself is readable

upstream acquisition continues
```

No silent edge drop.

---

# 80. CONFLICT BLOCK — FROZEN

On any projection conflict:

```text
runtime_state=blocked_conflict

offending source-generation checkpoint does not advance

no later record from that blocked generation is treated as projected

existing committed projection stays readable

upstream acquisition continues
```

No auto-skip.

No auto-repair.

---

# 81. NO-EDGE DOES NOT MEAN NO ACTIVITY — FROZEN

Consumers MUST NOT infer:

```text
zero edges
=
no protocols
no services
no Device traffic
no network activity
```

because zero edges may result from:

```text
ambiguous temporal identity
unattributed identity
authority unavailable
outside horizon
IPv6 unsupported
projection outage
retention expiry
```

NI-03 must consume projection availability/status semantics.

---

# 82. MULTI-SITE — FROZEN

Every edge contains:

```text
site_id
```

Every identity binding is keyed:

```text
site_id + client_mac
```

Every Device query requires Site.

No Site fallback.

No default Site.

No cross-Site IP attribution.

No cross-Site MAC merge.

The same authoritative Registry device_id may be referenced from multiple Site rows only for the same MAC and separately proven Site+MAC attribution.

---

# 83. CONFIGURATION — FROZEN

Default OFF:

```text
NETWORK_METADATA_PROJECTION_ENABLED=false
```

DB:

```text
NETWORK_METADATA_PROJECTION_DB_PATH=
/opt/CaptivePortal/data/network_metadata_projection.sqlite3
```

Capacity:

```text
NETWORK_METADATA_PROJECTION_MAX_DB_BYTES=
17179869184
```

Default:

```text
16 GiB
```

Architecture hard maximum:

```text
64 GiB
```

Minimum:

```text
64 MiB
```

---

# 84. PROCESSING CONFIGURATION — FROZEN

```text
NETWORK_METADATA_PROJECTION_BATCH_MAX_OBSERVATIONS=256

NETWORK_METADATA_PROJECTION_POLL_INTERVAL_SECONDS=1

NETWORK_METADATA_PROJECTION_ATTRIBUTION_RETRY_INTERVAL_SECONDS=30

NETWORK_METADATA_PROJECTION_ATTRIBUTION_RETRY_BATCH_SIZE=500

NETWORK_METADATA_PROJECTION_REGISTRY_RECONCILE_INTERVAL_SECONDS=60

NETWORK_METADATA_PROJECTION_REGISTRY_RECONCILE_BATCH_SIZE=500

NETWORK_METADATA_PROJECTION_RETENTION_INTERVAL_SECONDS=3600

NETWORK_METADATA_PROJECTION_RETENTION_BATCH_SIZE=5000

NETWORK_METADATA_PROJECTION_RETENTION_MAX_BATCHES_PER_PASS=20

NETWORK_METADATA_PROJECTION_SHUTDOWN_TIMEOUT_SECONDS=20
```

No configuration key may increase retention beyond the frozen privacy periods.

---

# 85. UPSTREAM CONFIGURATION REUSE — FROZEN

NI-02B reuses existing authoritative paths/settings:

```text
NETWORK_METADATA_DB_PATH

NETWORK_ATTRIBUTION_ENABLED
NETWORK_ATTRIBUTION_DB_PATH
NETWORK_ATTRIBUTION_MAX_DB_BYTES

VISITOR_REGISTRY_DB_PATH
```

It MUST NOT introduce duplicated aliases such as:

```text
PROJECTION_SOURCE_NETWORK_METADATA_DB
PROJECTION_ATTRIBUTION_DB
PROJECTION_REGISTRY_DB
```

---

# 86. DEFAULT-OFF SEMANTICS — FROZEN

If:

```text
NETWORK_METADATA_PROJECTION_ENABLED=false
```

then:

```text
no projection DB create
no writer lock
no NI-01 read
no NI-02A read
no Registry read
no background thread
```

Read service may report:

```text
disabled
```

without opening the store.

---

# 87. CAPACITY PRODUCTION ADMISSION — FROZEN

Architecture does not pre-authorize permanent production activation merely because implementation passes.

Before permanent enablement, production acceptance MUST measure:

```text
bytes per retained edge
0/1/2-edge distribution
registry-binding overhead
index overhead
WAL/headroom
projected 14-day steady-state
```

Permanent activation gate:

```text
projected steady-state
+
operational WAL/headroom
<= 80% of configured projection capacity
```

and filesystem free-space gate must pass.

Architecture hard maximum remains 64 GiB.

---

# 88. PROJECTION DB SQLITE POLICY — FROZEN

```text
schema version = 1
journal_mode = WAL
foreign_keys = ON
synchronous = FULL
busy_timeout = bounded
single writer lock = mandatory
quick_check = ok at startup
foreign_key_check = zero rows at startup
exact schema signature = mandatory
```

Unknown/future schema:

```text
fail closed
```

No automatic destructive recreation.

---

# 89. PROJECTION STORE PRIVACY — FROZEN

NI-02B projection DB may retain only:

```text
the exact endpoint IP/port fields required by DeviceNetworkMetadataEdgeV1
for <=14 days
```

It MUST NOT duplicate:

```text
DNS query names
DNS answer values
TLS SNI
QUIC SNI
ALPN arrays
raw EVE
Registry raw JSON
DHCP raw frames
```

---

# 90. OBSERVABILITY — FROZEN

Safe counters/gauges include:

```text
source_observations_scanned
source_observations_checkpointed

edges_emitted_0
edges_emitted_1
edges_emitted_2

src_resolved
src_ambiguous
src_unattributed
src_unavailable
src_outside_horizon
src_ipv6_unsupported

dst_resolved
dst_ambiguous
dst_unattributed
dst_unavailable
dst_outside_horizon
dst_ipv6_unsupported

pending_attribution_count

registry_authoritative_count
registry_not_yet_resolved_count
registry_unavailable_count
late_bind_success_count

projection_conflict_count

projection_db_bytes
projection_capacity_limit_bytes

retention_edges_deleted
retention_pending_deleted

checkpoint_lag_records
last_projection_commit_age_seconds
```

---

# 91. OBSERVABILITY PRIVACY — FROZEN

Logs/telemetry MUST NOT contain raw:

```text
src_ip
dst_ip
port
MAC
device_id
DNS name
SNI
raw Registry row
raw DHCP packet
```

Safe identifiers allowed for bounded diagnostics:

```text
observation_id
edge_id
source_generation_id
safe reason code
Site ID where already operationally admitted
```

No sensitive endpoint dump on exception.

---

# 92. ROLLBACK / DEACTIVATION — FROZEN

Safe deactivation:

```text
1. stop/disable network-metadata-projection.service;
2. set NETWORK_METADATA_PROJECTION_ENABLED=false;
3. leave NI-01 unchanged;
4. leave NI-02A unchanged;
5. leave Registry unchanged;
6. retain projection DB for evidence/rollback unless owner separately authorizes removal.
```

No upstream rollback is required because NI-02B changes no upstream schema.

---

# 93. CODE ROLLBACK — FROZEN

Rollback to pre-NI-02B application code:

```text
network-metadata-projection.service must remain stopped/disabled
projection DB is ignored
```

No NI-01 DB restore.

No NI-02A DB restore.

No Registry DB restore.

This is a required benefit of the separate projection store.

---

# 94. REBUILD — FROZEN

V1 supports controlled derived-store rebuild only from retained authoritative dependencies.

Rebuild is allowed only while:

```text
NI-01 sensitive endpoint retained
AND
NI-02A authority can evaluate event_at
```

Rebuild must use the same:

```text
edge_id
projection_contract_version
projection_algorithm_version
```

and reproduce the same semantic digest.

If not:

```text
projection_semantic_conflict
```

A future algorithm change is not a V1 rebuild; it requires separate admission.

---

# 95. NO QUERY-TIME PROJECTION — FROZEN

Future NI-03/Device Card MUST NOT implement:

```text
NI-01 observation
→ query-time NI-02A
→ query-time Registry
```

Device-relative projection and late binding are NI-02B writer responsibilities.

Readers consume materialized projection only.

---

# 96. NO REGISTRY WRITE — FROZEN

NI-02B may never:

```text
insert Visitor Device
update Visitor Device
create snapshot
change Registry Site
change Registry last_ip
```

No alternate Registry.

No Registry callback requirement.

---

# 97. NO VISIT OWNERSHIP — FROZEN

NI-02B does not read/write Visit identity as an attribution authority.

No Visit record may create or merge Device identity.

No Visit schema change.

---

# 98. NO FINGERPRINT IDENTITY FUSION — FROZEN

Device Fingerprint evidence/classification may not be used for:

```text
IP→MAC
MAC→device_id
cross-MAC merge
```

Fingerprint Sensor remains failure-isolated.

NI-02B needs no modification of fingerprint classification identity semantics.

---

# 99. NON-GOALS — FROZEN OUT OF SCOPE

```text
IPv6 attribution

new DHCP authority

Cisco polling

Omada temporal IP polling

Protocol Intelligence

Service Recognition

Organization Recognition

Transport Health

Device Card UI

Admin UI

traffic byte/rate accounting

SPAN accounting redesign

Registry writes

Visit writes

new Device creation

cross-MAC identity

secret management

Settings UI
```

---

# 100. CODER OWNERSHIP BOUNDARIES — ALLOWED

Implementation may add:

```text
app/network_metadata_projection/**
```

including:

```text
models
config
schema
repository
service
read_service
cli
telemetry
validation
```

Bounded read-only additions are allowed to:

```text
app/network_metadata/
```

only for:

```text
NetworkMetadataProjectionSourceReadService
```

Bounded read-only additions are allowed to:

```text
app/network_attribution/read_service.py
app/network_attribution/models.py
```

only for:

```text
NetworkAttributionHorizonV1
get_authority_horizon(site_id)
```

Tests/docs/config example/unit packaging may be added as required.

---

# 101. CODER FORBIDDEN OWNERSHIP

Coder MUST NOT modify architecture/semantics of:

```text
NI-01 normalizer
NI-01 observation schema V1
NI-01 writer/checkpoint
NI-01 retention durations

NI-02A DHCP authority
NI-02A interval rules
NI-02A schema V1
NI-02A retention

Visitor Registry schema
Visitor Registry writer
Visitor device_id algorithm
Visitor Registry MAC uniqueness

Visit Lifecycle

Device Fingerprint identity/fusion

CAPPORT
Authorization
Portal

existing Device Card/Admin UI
```

Any need to cross one of these boundaries returns to Architect.

---

# 102. ACCEPTANCE — SOURCE BOUNDARY

Must prove:

```text
projection service reads NI-01 through the bounded internal read service

projection service does not parse raw EVE

projection service does not write NI-01

projection source reader can return exact retained endpoint + scope facts

expired sensitive endpoint is not reconstructed
```

---

# 103. ACCEPTANCE — NI-02A

Deterministic cases:

```text
current IPv4 binding
→ resolved edge

IP reassignment:
event before boundary
→ old MAC

event after boundary
→ new MAC

exact NI-02A boundary
→ current accepted NI-02A [valid_from,valid_until) semantics

ambiguous
→ no edge for that endpoint

unattributed
→ no edge for that endpoint

unavailable
→ pending retry

outside_historical_horizon
→ no fabricated edge

invalid
→ projection conflict

nearest/newest binding
→ never used
```

---

# 104. ACCEPTANCE — EDGE COUNT

Required:

```text
neither endpoint resolved
→ 0

src resolved only
→ 1 src edge

dst resolved only
→ 1 dst edge

both resolved
→ 2 edges

peer unavailable
→ resolved opposite edge still commits
→ unavailable role pending

same observation replay
→ no duplicate edge
```

---

# 105. ACCEPTANCE — EDGE ID

Required:

```text
same observation + src
→ same edge_id

same observation + dst
→ same dst edge_id

src edge_id != dst edge_id

Registry late binding
→ edge_id unchanged

semantic mismatch for existing edge_id
→ blocked conflict
```

---

# 106. ACCEPTANCE — NETWORK SCOPE / DIRECTION

Required:

```text
inside capture-scope peer
→ local/local

outside capture-scope peer + device src
→ external/outbound

outside capture-scope peer + device dst
→ external/inbound

IPv6/absent peer
→ unknown/unknown

RFC1918 outside admitted scope
→ not auto-local

both guest endpoints inside admitted scope
→ 2 local edges

gateway inside admitted scope
→ local

resolved device endpoint outside admitted capture scope
→ conflict
```

---

# 107. ACCEPTANCE — REGISTRY AUTHORITY

Required:

```text
exact MAC row found
→ authoritative + existing device_id

no MAC row
→ not_yet_registry_resolved + device_id null

Registry unavailable
→ registry_unavailable + device_id null

Registry last_ip ignored

Registry last_site_id ignored

same MAC / multiple Sites with separate temporal proof
→ same existing device_id allowed

different MAC for existing bound device_id
→ registry_identity_conflict
```

---

# 108. ACCEPTANCE — PRE-REGISTRY / LATE BINDING

Required:

```text
resolved Site+MAC + no Registry row
→ edge persists immediately

later Registry row appears
→ periodic reconcile binds existing device_id

edge row unchanged

edge_id unchanged

source observation unchanged

NI-02A binding unchanged

read by MAC before bind works

read by device_id after bind works

same retained edge becomes device_id-visible
without edge rewrite
```

---

# 109. ACCEPTANCE — REGISTRY OUTAGE

Required:

```text
Registry down during projection
→ edge still materialized

binding state registry_unavailable

checkpoint can advance

Registry recovers
→ reconciliation resumes

previously authoritative binding
+ temporary later Registry outage
→ binding not erased
```

---

# 110. ACCEPTANCE — BACKFILL

Required:

```text
observation before first_usable_at
→ no historical fabrication

eligible retained observation inside horizon
→ projected

coverage gap
→ pending/unavailable

late observation after NI-02B activation
→ event_at-based attribution

backfill restart
→ checkpoint resumes

backfill replay
→ no duplicate edges
```

---

# 111. ACCEPTANCE — RETENTION

Required:

```text
edge cannot survive NI-01 sensitive 14-day boundary

projected_at does not extend retention

late device_id binding does not extend retention

pending row removed when sensitive source expires

DNS/SNI not duplicated in projection store

30-day Registry binding event retention bounded

controlled cleanup batching
```

---

# 112. ACCEPTANCE — CHECKPOINT / CRASH

Required:

```text
edge/pending write + checkpoint same projection transaction

crash before commit
→ checkpoint unchanged

restart
→ source batch replay

replay
→ deterministic no duplicate

capacity failure
→ failed batch checkpoint advance=0

conflict
→ offending generation checkpoint not advanced
```

---

# 113. ACCEPTANCE — MULTI-SITE / NO MERGE

Required:

```text
all edge reads require Site

same MAC may bind same Registry device_id across Sites
only with separate Site+MAC temporal authority

one device_id cannot bind different MACs
inside projection store

no cross-MAC identity inference

no cross-Site IP attribution
```

---

# 114. ACCEPTANCE — FAILURE ISOLATION

Inject failures independently:

```text
NI-01 unavailable
NI-02A unavailable
Registry unavailable
projection DB unavailable
projection capacity halt
projection semantic conflict
```

Must prove no regression to:

```text
Fingerprint Sensor acquisition
NI-02A writer
NI-01 writer
Visitor Registry writer
Authorization
CAPPORT
Captive Portal
```

---

# 115. ACCEPTANCE — READ SERVICE

Must prove:

```text
site_id + device_id + bounded window

site_id + MAC + bounded window

site_id + observation_id → 0/1/2 edges

max window=14d

limit<=500

keyset pagination

query-only SQLite

no NI-02A call on read

no Registry call on read

no raw EVE access on read
```

---

# 116. ACCEPTANCE — PRIVACY

Must prove:

```text
no DNS/SNI duplication

no raw endpoint values in logs

no raw Registry JSON

no raw DHCP frames

edge retention <=14d

future Admin/Device Card route not introduced
```

---

# 117. ACCEPTANCE — DEFAULT OFF

With:

```text
NETWORK_METADATA_PROJECTION_ENABLED=false
```

prove:

```text
no DB create
no lock create
no upstream DB open
no worker
no mutation
```

---

# 118. ACCEPTANCE — SQLITE / CAPACITY

Must prove:

```text
schema V1 exact

WAL
foreign_keys ON
synchronous FULL
quick_check ok
FK check clean

second writer rejected

configured hard cap honored

capacity_halted=true on bounded cap test

failed capacity batch checkpoint advance=0

page reuse / retention does not silently exceed hard cap
```

Before permanent production enablement:

```text
measured steady-state capacity gate PASS
```

is mandatory.

---

# 119. OBSERVATION EXACTNESS INVARIANTS

```text
NI02B-I01
NI-01 observation_id is never rewritten.

NI02B-I02
NI-01 source_event_identity is never rewritten.

NI02B-I03
NI-02A fact/binding identity is never rewritten.

NI02B-I04
Registry device_id is never generated by DTI.

NI02B-I05
Site+MAC remains the durable pre-Registry identity.

NI02B-I06
One source observation emits at most two edges.

NI02B-I07
One endpoint role emits at most one edge.

NI02B-I08
A resolved edge always references one exact NI-02A binding_id.

NI02B-I09
Peer attribution failure does not invent peer identity.

NI02B-I10
No raw-IP-only permanent Device identity exists.
```

---

# 120. LATE-BINDING INVARIANTS

```text
NI02B-I11
Registry binding is a separate dimension from temporal attribution.

NI02B-I12
not_yet_registry_resolved is a valid retained state.

NI02B-I13
Registry outage is not temporal unattributed.

NI02B-I14
Late Registry binding does not rewrite edge identity.

NI02B-I15
Late Registry binding does not rewrite source observation.

NI02B-I16
Late Registry binding does not rewrite DHCP authority.

NI02B-I17
No Registry last_ip/last_site temporal authority.

NI02B-I18
No cross-MAC device_id binding.
```

---

# 121. PRIVACY / RETENTION INVARIANTS

```text
NI02B-I19
Raw peer endpoint retention never exceeds 14 days.

NI02B-I20
projected_at never refreshes sensitive retention age.

NI02B-I21
device_id late binding never refreshes sensitive retention age.

NI02B-I22
DNS/SNI are not duplicated into projection DB.

NI02B-I23
Projection cannot claim deterministic rebuildability
after required source facts expire.
```

---

# 122. FAILURE INVARIANTS

```text
NI02B-I24
Projection failure never stops NI-01 acquisition.

NI02B-I25
Projection failure never stops NI-02A acquisition.

NI02B-I26
Projection failure never stops Fingerprint Sensor.

NI02B-I27
Projection failure never writes Visitor Registry.

NI02B-I28
Projection failure never affects CAPPORT/Auth.

NI02B-I29
Missing projection cannot be interpreted as no Device activity.

NI02B-I30
Conflicts fail closed and do not advance the offending checkpoint.
```

---

# 123. DEFERRED / OUT OF SCOPE

```text
IPv6 attribution

cross-Site identity beyond exact same-MAC Registry identity

new IP→MAC authorities

Registry tombstone/revocation semantics

projection algorithm v2

projection schema migration beyond v1

NI-03 Protocol Intelligence

Service/Organization recognition

Transport Health

Device Card aggregation/presentation

long-lived remote endpoint history

Admin Settings controls for NI-02B

automatic systemd control from Admin
```

---

# 124. ARCHITECTURE BLOCKERS

```text
ARCHITECTURE BLOCKER = NONE
```

No new live-network research is required to define NI-02B V1.

The already accepted NI-02A temporal authority is sufficient.

Production capacity measurement is an activation/acceptance gate, not an architecture blocker.

---

# 125. FINAL DISPOSITION

```text
TASK =
TASK-DTI-NI-02B

ARCHITECTURE CONTRACT =
v1

PHYSICAL MODEL =
MATERIALIZED PROJECTION STORE

WRITER =
network-metadata-projection.service

STORE =
/opt/CaptivePortal/data/network_metadata_projection.sqlite3

STORE SCHEMA =
V1

NI-01 SCHEMA CHANGE =
NO

NI-02A SCHEMA CHANGE =
NO

REGISTRY SCHEMA CHANGE =
NO

REGISTRY WRITE =
NO

VISIT WRITE =
NO

EDGE IDENTITY =
SHA-256(observation_id + endpoint role contract)

MAX EDGES PER OBSERVATION =
2

PRIMARY PRE-REGISTRY IDENTITY =
site_id + client_mac

DEVICE_ID =
EXISTING REGISTRY ONLY / LATE-BOUND

LATE BINDING =
IMMEDIATE LOOKUP + 60s BOUNDED RECONCILIATION

RAW EDGE RETENTION =
14 DAYS MAX

ATTRIBUTION AUTHORITY =
NI-02A TRUSTED DHCPv4 ONLY

IPV6 ATTRIBUTION =
OUT OF SCOPE

QUERY-TIME ATTRIBUTION =
FORBIDDEN

CROSS-MAC MERGE =
FORBIDDEN

FAILURE ISOLATION =
REQUIRED

DEFAULT ACTIVATION =
OFF

ARCHITECTURE BLOCKER =
NONE

OPEN P0 =
0

OPEN P1 =
0

READY FOR TECH LEAD IMPLEMENTATION CONTRACT =
YES

CODER =
HOLD

PRODUCTION ACTIVATION =
NO
```

---

# 126. NEXT GOVERNANCE STEP

```text
Architect
→ this Architecture Contract v1

then

Tech Lead
→ architecture review

if PASS:

Tech Lead
→ exact implementation TASK / file-level implementation contract

then and only then:

Coder
→ implementation

after code/lab acceptance:

separate production activation/capacity admission
```
