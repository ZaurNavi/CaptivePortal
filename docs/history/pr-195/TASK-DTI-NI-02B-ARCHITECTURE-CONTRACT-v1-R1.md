# TASK-DTI-NI-02B
## DEVICE-RELATIVE NETWORK METADATA PROJECTION
## + EXISTING VISITOR REGISTRY LATE `device_id` BINDING
### ARCHITECTURE CONTRACT v1-R1
### BOUNDED CONSISTENCY / IMPLEMENTATION-EXACTNESS REPAIR
### FOR TECH LEAD RE-REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Baseline:** `main@e32c695e53ffb2b173178189581751728c2ee0c2`  
**TREE:** `6348fe5fddb22f597ba8a6e40cf5f96a4d9d73ac`  
**Parent contract:** `TASK-DTI-NI-02B — ARCHITECTURE CONTRACT v1`  
**R1 scope:** `P1-01 / P1-02 / P1-03 / P2-01 only`  
**Status:** `DRAFT FOR TECH LEAD RE-REVIEW`  
**Coder:** `HOLD`  
**Production change:** `NO`

---

# 0. PRECEDENCE / NON-REOPEN RULE

Этот документ является точечным нормативным patch к `ARCHITECTURE CONTRACT v1`.

При конфликте:

```text
v1-R1
>
v1
```

Все решения v1, не изменённые ниже, остаются без изменений.

R1 НЕ переоткрывает:

```text
NI-02A authority
DHCP admission
NI-01 architecture
Visitor Registry architecture
IPv6 admission
Network Intelligence roadmap
materialized projection-store model
separate projection service
Site+MAC identity
14-day sensitive retention
0/1/2 edge model
```

---

# 1. P1-01 — PARTIAL EDGE + ATTRIBUTION RETRY + IMMUTABLE EDGE

## 1.1 Selected repair model

Выбран точный механизм:

```text
PERSISTED COUNTERPART ATTRIBUTION SNAPSHOT
IN THE PENDING-ATTRIBUTION ROW
```

Это вариант семейства:

```text
A
```

из Tech Lead review.

NI-02B НЕ делает mutable peer-attribution fields в edge.

`device_network_metadata_edges` остаётся immutable.

Уже materialized edge никогда не переписывается из-за более позднего результата другой endpoint-role.

---

# 2. PEER ATTRIBUTION FIELD SEMANTICS — REDEFINED EXACTLY

Для immutable edge:

```text
peer_attribution_state
peer_attribution_binding_id
```

означают:

```text
COUNTERPART TEMPORAL-ATTRIBUTION SNAPSHOT
USED AT THE EXACT ATTEMPT THAT MATERIALIZED THIS EDGE
```

Они НЕ означают:

```text
latest peer attribution
final peer attribution
eventual observation-wide attribution
current NI-02A state
```

Следовательно две edges одного observation MAY legitimately contain
different peer-attribution snapshots when they were materialized in
different retry attempts.

Это не inconsistency.

Это точная lineage семантика.

---

# 3. ROLE SNAPSHOT CONTRACT

Для каждой endpoint-role:

```text
src
dst
```

pending state сохраняет:

```text
<role>_snapshot_state

<role>_snapshot_binding_id
```

Allowed snapshot states:

```text
resolved
ambiguous
unattributed
unavailable
outside_historical_horizon
unsupported_address_family
endpoint_absent
```

`invalid` в pending row запрещён, потому что:

```text
invalid
→ attribution_query_contract_invalid
→ projection conflict
→ no pending commit
```

Constraint:

```text
snapshot_state = resolved
→ snapshot_binding_id MUST be non-null

snapshot_state != resolved
→ snapshot_binding_id MUST be null
```

---

# 4. PENDING FLAG / SNAPSHOT INVARIANT

Exact invariant:

```text
pending_src = 1
IFF
src_snapshot_state = unavailable
```

and:

```text
pending_dst = 1
IFF
dst_snapshot_state = unavailable
```

Pending row exists only while:

```text
pending_src = 1
OR
pending_dst = 1
```

Therefore any non-pending counterpart has a durable non-sensitive
attribution-state snapshot available for later edge construction.

No raw endpoint IP is added for retry convenience.

---

# 5. UPDATED `projection_pending_attribution` LOGICAL SCHEMA

v1 §51 is replaced for the affected columns by:

```text
observation_id TEXT PRIMARY KEY

site_id TEXT NOT NULL

source_generation_id TEXT NOT NULL
record_start_byte_offset INTEGER NOT NULL

event_at TEXT NOT NULL
source_ingested_at TEXT NOT NULL

pending_src INTEGER NOT NULL CHECK(pending_src IN (0,1))
pending_dst INTEGER NOT NULL CHECK(pending_dst IN (0,1))

src_snapshot_state TEXT NOT NULL
src_snapshot_binding_id TEXT NULL

dst_snapshot_state TEXT NOT NULL
dst_snapshot_binding_id TEXT NULL

first_pending_at TEXT NOT NULL
last_attempt_at TEXT NOT NULL
next_retry_at TEXT NOT NULL

CHECK(pending_src=1 OR pending_dst=1)

CHECK(
    (pending_src=1 AND src_snapshot_state='unavailable')
    OR
    (pending_src=0 AND src_snapshot_state!='unavailable')
)

CHECK(
    (pending_dst=1 AND dst_snapshot_state='unavailable')
    OR
    (pending_dst=0 AND dst_snapshot_state!='unavailable')
)

CHECK(
    (src_snapshot_state='resolved' AND src_snapshot_binding_id IS NOT NULL)
    OR
    (src_snapshot_state!='resolved' AND src_snapshot_binding_id IS NULL)
)

CHECK(
    (dst_snapshot_state='resolved' AND dst_snapshot_binding_id IS NOT NULL)
    OR
    (dst_snapshot_state!='resolved' AND dst_snapshot_binding_id IS NULL)
)
```

Allowed state CHECK must contain exactly the enum frozen above.

Still forbidden:

```text
src_ip
dst_ip
src_port
dst_port
MAC copy solely for retry
DNS
SNI
```

---

# 6. INITIAL ATTRIBUTION ATTEMPT — EXACT TWO-PHASE RULE

For a new NI-01 observation:

```text
PHASE 1
evaluate BOTH endpoint roles independently

PHASE 2
freeze one in-memory observation attribution snapshot:
    src state/binding
    dst state/binding

PHASE 3
materialize every newly resolved role edge
using the counterpart snapshot from that SAME attempt

PHASE 4
if any role state=unavailable:
    persist pending row with BOTH role snapshots
else:
    no pending row
```

Edge emission happens only after both role evaluations for that attempt
are known.

Therefore if both resolve in one attempt:

```text
src edge.peer_attribution_state = resolved
src edge.peer_attribution_binding_id = dst binding

dst edge.peer_attribution_state = resolved
dst edge.peer_attribution_binding_id = src binding
```

---

# 7. RETRY — EXACT ROLE SELECTION

On retry:

```text
ONLY roles whose pending flag = 1
are re-evaluated through NI-02A.
```

A role whose pending flag is already:

```text
0
```

MUST NOT be re-queried.

Its stored snapshot is authoritative for:

```text
counterpart lineage
during this pending observation lifecycle.
```

No retry is allowed to "refresh" a non-pending role.

---

# 8. RETRY — EXACT ATTEMPT ALGORITHM

For one pending observation:

```text
1. re-read the NI-01 source observation
   through get_projection_source_record(observation_id);

2. verify exact source identity;

3. load persisted src/dst snapshots;

4. re-evaluate ONLY role(s) with pending flag=1;

5. replace only those pending-role in-memory snapshots
   with the newly returned NI-02A result;

6. after all pending roles for this retry attempt have been evaluated,
   materialize edge(s) for role(s) that became resolved;

7. every newly created edge takes its peer attribution fields
   from the counterpart snapshot now present in that same
   observation attribution snapshot;

8. role that returns unavailable remains pending;

9. role that returns a non-retryable non-resolved state:
   ambiguous
   unattributed
   outside_historical_horizon
   unsupported_address_family
   endpoint_absent
   becomes non-pending and its snapshot is frozen to that state;

10. if no pending roles remain:
    delete projection_pending_attribution row;

11. commit new edges / pending-row change /
    projection result disposition atomically.
```

---

# 9. NON-PENDING ROLE RE-EVALUATION — FORBIDDEN

Retry MUST NOT call temporal attribution for a non-pending role.

Therefore the retry state machine cannot discover a later changed result
for that already frozen role.

If an implementation performs such a lookup anyway:

```text
its result has NO authority
to alter an existing edge
or the frozen counterpart snapshot
```

Such a lookup is architecturally unnecessary and MUST NOT be part of
the implementation path.

A controlled full derived-store rebuild is a separate operation.
If that rebuild produces different immutable edge semantics for the same
`edge_id`, existing rule remains:

```text
edge_semantic_conflict
```

---

# 10. EXISTING EDGE REWRITE — ABSOLUTELY FORBIDDEN

For an already committed edge, retry MUST NOT change:

```text
peer_attribution_state
peer_attribution_binding_id
edge_semantic_digest
attribution_binding_id
client_mac
device_endpoint
peer_endpoint
direction
peer_scope
```

Retry MUST NOT recalculate or replace the existing edge semantic digest.

The existing edge remains byte/semantic-lineage stable.

---

# 11. NEW EDGE DIGEST ON RETRY

A newly created opposite-role edge computes its semantic digest once,
using:

```text
its own newly resolved temporal attribution

AND

the frozen counterpart snapshot available in the pending row /
current retry attempt
```

That digest is thereafter immutable.

Registry binding remains excluded from the immutable edge digest exactly
as in parent v1.

---

# 12. CASE A — FROZEN

Initial:

```text
src = resolved / MAC-A / binding-A
dst = unavailable
```

Initial commit:

```text
src edge created

src edge:
    attribution_binding_id = binding-A

    peer_attribution_state = unavailable
    peer_attribution_binding_id = null

pending row:
    pending_src = 0
    src_snapshot_state = resolved
    src_snapshot_binding_id = binding-A

    pending_dst = 1
    dst_snapshot_state = unavailable
    dst_snapshot_binding_id = null
```

Retry:

```text
ONLY dst is queried
```

If:

```text
dst = resolved / MAC-B / binding-B
```

then:

```text
dst edge is created

dst edge:
    attribution_binding_id = binding-B

    peer_attribution_state = resolved
    peer_attribution_binding_id = binding-A
```

Existing src edge:

```text
UNCHANGED

peer_attribution_state remains unavailable
peer_attribution_binding_id remains null
semantic digest unchanged
```

Pending row:

```text
deleted
```

Final:

```text
edge count = 2
projection_state = complete
```

No src re-query.

---

# 13. CASE B — FROZEN

Initial:

```text
src = unattributed
dst = unavailable
```

Initial commit:

```text
edges = 0

pending row:
    pending_src = 0
    src_snapshot_state = unattributed
    src_snapshot_binding_id = null

    pending_dst = 1
    dst_snapshot_state = unavailable
    dst_snapshot_binding_id = null
```

Retry queries:

```text
dst only
```

If:

```text
dst = resolved / MAC-B / binding-B
```

then create exactly one dst edge:

```text
dst edge:
    attribution_binding_id = binding-B

    peer_attribution_state = unattributed
    peer_attribution_binding_id = null
```

No src edge.

Pending row deleted.

Final:

```text
edge count = 1
projection_state = complete
```

---

# 14. CASE C — FROZEN

Initial:

```text
src = unavailable
dst = unavailable
```

Initial:

```text
edges = 0

pending row:
    pending_src = 1
    src_snapshot_state = unavailable

    pending_dst = 1
    dst_snapshot_state = unavailable

projection_state = pending
```

Retry 1 evaluates both pending roles.

Result:

```text
src = resolved / MAC-A / binding-A
dst = unavailable
```

Commit:

```text
src edge created

src edge:
    peer_attribution_state = unavailable
    peer_attribution_binding_id = null

pending row becomes:
    pending_src = 0
    src_snapshot_state = resolved
    src_snapshot_binding_id = binding-A

    pending_dst = 1
    dst_snapshot_state = unavailable

projection_state = partial_pending
```

Retry 2 evaluates:

```text
dst only
```

Result:

```text
dst = resolved / MAC-B / binding-B
```

Commit:

```text
dst edge created

dst edge:
    peer_attribution_state = resolved
    peer_attribution_binding_id = binding-A

existing src edge:
    unchanged
    old digest unchanged

pending row:
    deleted

final edge count = 2

projection_state = complete
```

This asymmetry is intentional exact-at-materialization lineage.

---

# 15. BOTH PENDING RESOLVE IN SAME RETRY — FROZEN

If a retry begins:

```text
src unavailable
dst unavailable
```

and in the same retry attempt:

```text
src → resolved / binding-A
dst → resolved / binding-B
```

then both role results are collected before edge creation.

Create:

```text
src edge:
    peer state = resolved
    peer binding = binding-B

dst edge:
    peer state = resolved
    peer binding = binding-A
```

Pending row deleted.

Final:

```text
2 edges
complete
```

---

# 16. RETRY RETURNS TERMINAL NON-RESOLVED STATE — FROZEN

Example:

```text
src already resolved
dst pending unavailable
```

Retry returns:

```text
dst = unattributed
```

Then:

```text
no dst edge

dst pending flag → 0

dst snapshot → unattributed

existing src edge remains unchanged
with peer_attribution_state=unavailable

pending row deleted

projection_state=complete
because at least one edge exists
and no retryable uncertainty remains
```

For zero emitted edges and no pending roles:

```text
projection_state=terminal_no_edge
```

---

# 17. P1-01 INVARIANTS

```text
R1-P1-01-I01
resolved side is not withheld because peer is unavailable.

R1-P1-01-I02
existing edge_id never changes.

R1-P1-01-I03
already committed edge is never rewritten.

R1-P1-01-I04
existing edge semantic digest is never recalculated by retry.

R1-P1-01-I05
retry calls NI-02A only for pending roles.

R1-P1-01-I06
non-pending counterpart attribution snapshot is durably retained
only while another role remains pending.

R1-P1-01-I07
pending retry stores no raw endpoint copy.

R1-P1-01-I08
max 2 edges per observation remains unchanged.

R1-P1-01-I09
late Registry binding remains independent.

R1-P1-01-I10
only NI-02A remains temporal authority.
```

---

# 18. P1-01 ACCEPTANCE ADDITIONS

Mandatory deterministic tests:

```text
CASE A exact sequence
→ PASS

CASE B exact sequence
→ PASS

CASE C exact sequence
→ PASS

both unavailable → both resolve same retry
→ 2 mutually-resolved peer snapshots

resolved opposite + pending role later unattributed
→ old edge unchanged

non-pending role NI-02A mock must not be called on retry

existing edge semantic digest unchanged across retry

new opposite edge uses frozen counterpart snapshot

pending row contains no IP/port/MAC copy

pending row deleted only when no pending roles remain

retry crash before commit
→ old edge/pending state remains
→ deterministic retry

retry crash after commit
→ new edge/pending transition already durable
→ no duplicate
```

---

# 19. P1-01 DISPOSITION

```text
P1-01 = RESOLVED
```

---

# 20. P1-02 — SOURCE CHECKPOINT BOOTSTRAP / FIRST RECORD

## 20.1 Exact representation of "nothing committed"

The exact representation is:

```text
NO ROW
in projection_source_checkpoints
for that source_generation_id
```

No numeric sentinel is used.

No fake offset is used.

---

# 21. CHECKPOINT ROW SEMANTICS

If a checkpoint row exists:

```text
last_record_start_byte_offset
```

means exactly:

```text
the greatest source record byte offset
whose projection disposition was successfully committed
for that source generation.
```

Therefore:

```text
offset=0
```

is a legitimate committed checkpoint.

It never means "not started".

---

# 22. SOURCE READ API — R1 EXACT SIGNATURE

Parent conceptual API is amended to:

```text
read_projection_batch(
    source_generation_id,
    after_record_start_byte_offset: int | null,
    limit
)
```

Exact semantics:

```text
after_record_start_byte_offset = null
→ no lower offset predicate

after_record_start_byte_offset = N
→ return only records with
   record_start_byte_offset > N
```

---

# 23. FIRST-BATCH SQL SEMANTICS

Conceptually exact query rule:

```text
if after_record_start_byte_offset IS NULL:

    WHERE source_generation_id = :generation

    ORDER BY record_start_byte_offset ASC
    LIMIT :limit
```

No:

```text
offset > 0
offset >= 0 sentinel comparison
```

is added.

If checkpoint exists with offset N:

```text
WHERE source_generation_id = :generation
AND record_start_byte_offset > :N

ORDER BY record_start_byte_offset ASC
LIMIT :limit
```

---

# 24. FIRST CHECKPOINT ROW CREATION — FROZEN

A checkpoint row is NOT created merely because a source generation is discovered.

The first checkpoint row is created only inside the same successful
projection-store transaction that commits the first source record's
projection disposition.

A record disposition may be:

```text
0-edge terminal disposition
1-edge commit
2-edge commit
pending attribution state
partial-pending state
```

provided it is a successful non-conflict, non-capacity-failed
projection disposition.

---

# 25. FIRST RECORD OFFSET = 0 — FROZEN

Generation:

```text
first retained record offset = 0
```

Initial state:

```text
no checkpoint row
```

Read:

```text
after = null
```

Therefore offset 0 is returned and processed.

After successful transaction:

```text
checkpoint row created
last_record_start_byte_offset = 0
```

Next read:

```text
offset > 0
```

Thus first record is not silently skipped.

---

# 26. FIRST RECORD OFFSET > 0 — FROZEN

Generation may legitimately have:

```text
first retained record offset = K
K > 0
```

for example because earlier source records are not retained/eligible in
the NI-01 projection-source view.

Initial state:

```text
no checkpoint row
```

Read with:

```text
after = null
```

returns the actual first retained record:

```text
offset = K
```

After successful commit:

```text
checkpoint = K
```

No synthetic assumption about generation start offset is made.

---

# 27. CRASH / REPLAY — FIRST RECORD

Crash before first projection transaction commit:

```text
no checkpoint row
```

Restart:

```text
after = null
first retained source record is re-read
```

No committed projection fact exists from that failed transaction.

Crash after transaction commit:

```text
first edge/pending/terminal disposition
AND
checkpoint row
are already durable together
```

Restart:

```text
after = committed offset
```

Normal execution processes the first retained record exactly once.

Crash/replay may re-read only when prior transaction did not commit.

---

# 28. CHECKPOINT ADVANCEMENT RULE — UNCHANGED BUT EXPLICIT

Checkpoint MUST NOT be created/advanced when the current source record
results in:

```text
projection conflict

pre-write capacity rejection

projection-store transaction rollback

untrusted source identity
```

A successfully committed pending-attribution disposition DOES advance
the source checkpoint because retry ownership has moved to the durable
pending table.

---

# 29. P1-02 ACCEPTANCE ADDITIONS

Mandatory:

```text
generation first record offset=0
→ processed

generation first record offset>0
→ processed

no checkpoint row
→ read after=null

existing checkpoint=0
→ next read uses >0

checkpoint row is not created at generation discovery

first terminal 0-edge observation
→ checkpoint row created only with committed disposition

first pending observation
→ pending + checkpoint atomic

crash before first commit
→ no checkpoint row

crash after first commit
→ no duplicate projection

no negative/synthetic sentinel anywhere
```

---

# 30. P1-02 DISPOSITION

```text
P1-02 = RESOLVED
```

---

# 31. P1-03 — EXACT SQLITE CAPACITY FOOTPRINT / WAL PRESSURE

## 31.1 Exact configured-cap footprint

`NETWORK_METADATA_PROJECTION_MAX_DB_BYTES` bounds the complete writable
SQLite footprint:

```text
projection_sqlite_footprint_bytes
=
size(network_metadata_projection.sqlite3)
+
size(network_metadata_projection.sqlite3-wal)
+
size(network_metadata_projection.sqlite3-shm)
+
size(network_metadata_projection.sqlite3-journal, if present)
```

Missing files contribute:

```text
0
```

This is the only authoritative capacity footprint.

Forbidden capacity accounting:

```text
main DB only

PRAGMA page_count * page_size only

WAL excluded

SHM excluded
```

Writer lock file is operational lock metadata and is outside this
SQLite-footprint cap.

---

# 32. HARD CAP

Configured cap:

```text
NETWORK_METADATA_PROJECTION_MAX_DB_BYTES
```

remains:

```text
minimum = 64 MiB
default = 16 GiB
architecture maximum = 64 GiB
```

No implementation may silently expand it.

---

# 33. TRANSACTION HEADROOM — FROZEN

Architecture freezes:

```text
PROJECTION_TRANSACTION_HEADROOM_BYTES
=
16777216
=
16 MiB
```

This is a code-owned safety constant in V1.

It is not operator-expandable.

Before implementation acceptance, lab proof MUST demonstrate:

```text
one maximum admitted 256-observation projection transaction
cannot increase the complete writable SQLite footprint
by more than 16 MiB
under the exact V1 schema/index set.
```

If this proof fails:

```text
STOP
→ Architect return
```

Coder may not increase the constant or batch semantics independently.

---

# 34. PRE-WRITE CAPACITY GATE — EXACT

Before starting every projection write transaction:

```text
F = current complete SQLite footprint
H = 16 MiB
C = configured capacity
```

If:

```text
F + H <= C
```

the transaction may start.

If:

```text
F + H > C
```

the writer MUST NOT start the projection transaction yet.

It enters capacity-maintenance logic first.

Therefore a batch denied by the pre-write gate has:

```text
edge commit = 0
pending-state commit = 0
checkpoint advance = 0
```

---

# 35. NORMAL WAL MAINTENANCE — FROZEN

Outside any active write transaction:

```text
PRAGMA wal_checkpoint(PASSIVE)
```

is executed:

```text
after each successful projection write transaction
```

PASSIVE checkpoint result:

```text
busy / incomplete because of a legitimate reader
```

is NOT:

```text
corruption
semantic conflict
permanent writer fault
```

If capacity headroom remains sufficient:

```text
F + H <= C
```

ordinary reader contention does not stop subsequent projection batches.

---

# 36. TRUNCATE POLICY — FROZEN

`PRAGMA wal_checkpoint(TRUNCATE)` is NOT the normal after-every-batch path.

It is attempted only:

```text
A. when pre-write capacity gate lacks required headroom
   after PASSIVE maintenance;

or

B. after bounded retention cleanup when capacity pressure remains.
```

TRUNCATE runs:

```text
outside a write transaction
```

and may legitimately return busy/locked due to an old reader snapshot.

---

# 37. READER-BLOCKED CAPACITY MAINTENANCE — NEW EXACT STATE

Add runtime state:

```text
capacity_waiting_reader
```

to `projection_runtime_state.runtime_state`.

Exact meaning:

```text
complete footprint is still <= configured hard cap

BUT

required 16 MiB pre-write headroom cannot currently be restored

AND

WAL checkpoint/TRUNCATE is blocked by a legitimate reader.
```

Behavior:

```text
do not start a new projection write transaction

do not advance source checkpoint

do not delete committed live evidence

keep existing committed projection readable

retry PASSIVE/TRUNCATE on later poll cycles

automatically return to usable/degraded processing
once:
    footprint + headroom <= cap
```

This state is not a permanent writer fault.

---

# 38. TRUE CAPACITY HALT — EXACT

`capacity_halted` is used when any of the following is true:

```text
1. main/live committed SQLite footprint itself cannot satisfy
   F + H <= C after non-blocked maintenance;

2. complete footprint is > configured cap;

3. non-reader-blocked SQLite maintenance cannot restore
   bounded capacity headroom;

4. post-commit check detects that the configured cap has been exceeded.
```

`capacity_halted` means:

```text
no new projection write transaction
no new checkpoint advancement
committed reads remain available if DB itself is readable
no silent evidence deletion
```

Recovery is allowed only after a later exact remeasurement shows:

```text
F + H <= C
```

and normal SQLite integrity checks remain trustworthy.

No process restart is required solely to clear a recovered capacity halt.

---

# 39. POST-WRITE CAPACITY CHECK — EXACT

After a projection transaction commits durably:

```text
1. that transaction is already a valid committed projection fact;

2. its source checkpoint, if part of that transaction,
   remains committed;

3. run PASSIVE WAL maintenance;

4. remeasure the complete SQLite footprint.
```

If:

```text
F <= C
```

the committed transaction remains valid.

If:

```text
F + H > C
```

future writes are paused and capacity-maintenance logic runs before any
next transaction.

If:

```text
F > C
```

transition immediately to:

```text
capacity_halted
```

The just-committed projection transaction is NOT rolled back
retrospectively.

Its checkpoint is NOT rewound.

Its edge/pending/binding facts are NOT deleted to fake compliance.

---

# 40. POST-COMMIT CAP BREACH SEMANTICS

A post-commit breach means:

```text
the pre-write headroom proof was insufficient
or an unexpected SQLite footprint expansion occurred.
```

The committed facts remain authoritative because the transaction already
committed atomically.

Operational result:

```text
capacity_halted
no further writes
checkpoint remains at the committed record
capacity fault is surfaced
```

Implementation acceptance MUST fail if the lab can reproduce such a cap
breach under the admitted max-batch contract.

This prevents architecture from treating ordinary over-cap commits as an
acceptable steady-state mode.

---

# 41. RETENTION VS CAPACITY

Retention cleanup may delete only evidence that is already eligible under
the frozen retention contract.

It MUST NOT:

```text
delete still-live edges
delete still-required identity lineage
delete active checkpoint state
shorten the 14-day edge retention
```

solely to satisfy capacity.

After legitimate retention cleanup:

```text
PASSIVE
then if needed TRUNCATE
then remeasure
```

may restore headroom.

---

# 42. WAL READER CONTENTION — REQUIRED DISTINCTION

Exact distinction:

```text
reader blocks checkpoint/TRUNCATE
AND footprint <= cap
→ capacity_waiting_reader
  when write headroom is insufficient

reader blocks checkpoint/TRUNCATE
BUT headroom remains sufficient
→ continue normal writes

committed footprint > cap
→ capacity_halted

main/live data too large for cap+headroom
→ capacity_halted
```

Normal reader contention alone is never:

```text
storage corruption
projection_semantic_conflict
permanent writer failure
```

---

# 43. CAPACITY CHECKPOINT SEMANTICS

The phrase:

```text
failed capacity batch checkpoint advance = 0
```

means exactly:

```text
a batch rejected BEFORE its projection transaction begins
because bounded capacity cannot be guaranteed
does not advance the source checkpoint.
```

It does NOT mean:

```text
rewind checkpoint after a transaction already committed.
```

Committed transaction checkpoint identity is immutable.

---

# 44. UPDATED RUNTIME STATE ENUM

Parent v1 runtime-state enum is amended to:

```text
initializing
usable
degraded
source_unavailable
attribution_unavailable
registry_degraded
capacity_waiting_reader
capacity_halted
blocked_conflict
stopping
```

No other new state is added by R1.

---

# 45. P1-03 ACCEPTANCE ADDITIONS

Mandatory tests:

```text
footprint =
main + WAL + SHM + unexpected journal

main-only accounting test
→ must fail implementation if used

max 256-observation transaction growth
<=16 MiB proven

pre-write F+H<=C
→ allowed

pre-write F+H>C
→ no transaction
→ no checkpoint advance

PASSIVE blocked by reader
+ sufficient headroom
→ continue

TRUNCATE blocked by reader
+ insufficient headroom
+ footprint<=cap
→ capacity_waiting_reader
→ no new write
→ no checkpoint advance
→ recover automatically after reader release

live/main data cannot fit with headroom
→ capacity_halted

post-commit F<=C but headroom low
→ committed checkpoint retained
→ next write waits for maintenance

post-commit F>C
→ committed transaction remains valid
→ checkpoint not rewound
→ capacity_halted

retention does not delete unexpired live evidence

capacity recovery
→ only after exact footprint + headroom gate passes
```

---

# 46. P1-03 DISPOSITION

```text
P1-03 = RESOLVED
```

---

# 47. P2-01 — REGISTRY RECONCILIATION ORDER

## 47.1 Intent

R1 freezes both:

```text
unresolved identities receive priority
```

and:

```text
authoritative identities still receive bounded fair re-verification
```

Therefore one simple global `last_evaluated_at` order is NOT sufficient.

---

# 48. RECONCILIATION BATCH SIZE — UNCHANGED

Every reconciliation pass remains:

```text
interval = 60 seconds
maximum selected rows = 500
```

---

# 49. TWO-LANE SELECTION — FROZEN

Each pass has two logical lanes:

```text
UNRESOLVED lane
target quota = 400 rows

AUTHORITATIVE lane
target quota = 100 rows
```

This is a selection policy, not two transactions.

The selected rows may be processed within the same bounded reconciliation
transaction/batch strategy.

---

# 50. UNRESOLVED LANE — EXACT STATE PRIORITY

Unresolved lane includes:

```text
not_yet_registry_resolved
registry_unavailable
```

Exact state priority:

```text
priority 0 =
not_yet_registry_resolved

priority 1 =
registry_unavailable
```

Within state priority:

```text
last_evaluated_at ASC
site_id ASC
client_mac ASC
```

Conceptually:

```text
ORDER BY
    CASE binding_state
        WHEN 'not_yet_registry_resolved' THEN 0
        WHEN 'registry_unavailable' THEN 1
    END ASC,
    last_evaluated_at ASC,
    site_id ASC,
    client_mac ASC
```

up to the unresolved lane quota.

---

# 51. AUTHORITATIVE LANE — EXACT ORDER

Authoritative lane includes only:

```text
binding_state='authoritative'
```

Order:

```text
last_evaluated_at ASC
site_id ASC
client_mac ASC
```

up to:

```text
100
```

rows per normal pass.

This guarantees bounded conflict/reverification coverage even if unresolved
rows are continuously present.

---

# 52. QUOTA SPILLOVER — FROZEN

If unresolved lane contains fewer than 400 rows:

```text
unused unresolved slots are offered to authoritative lane
using authoritative ordering.
```

If authoritative lane contains fewer than 100 rows:

```text
unused authoritative slots are offered to unresolved lane
using unresolved ordering.
```

Total selected rows MUST NOT exceed:

```text
500
```

---

# 53. NO DUPLICATE SELECTION

A `(site_id, client_mac)` row may appear at most once in a reconciliation
pass.

State change during the pass does not cause the same row to be selected
again until a later pass.

---

# 54. RECONCILIATION STATE TRANSITIONS — UNCHANGED

R1 changes selection ordering only.

Existing semantics remain:

```text
not_yet_registry_resolved
→ may become authoritative

registry_unavailable
→ may become authoritative
or not_yet_registry_resolved
according to trustworthy Registry result

authoritative
→ monotonic authoritative binding
→ no downgrade on transient absence/outage

identity mismatch
→ registry_identity_conflict
```

---

# 55. P2-01 ACCEPTANCE ADDITIONS

Mandatory:

```text
>400 not_yet rows + authoritative rows
→ first unresolved lane deterministically selects oldest not_yet
→ authoritative still receives up to 100 reserved slots

not_yet + registry_unavailable
→ not_yet priority first
→ then registry_unavailable

<400 unresolved
→ spare slots flow to authoritative

<100 authoritative
→ spare slots flow to unresolved

same timestamp ties
→ site_id then client_mac deterministic

no row selected twice in one pass

authoritative rows are not starved indefinitely
```

---

# 56. P2-01 DISPOSITION

```text
P2-01 = RESOLVED
```

---

# 57. R1 REPLACEMENT SUMMARY

The following parent-v1 clauses are normatively amended:

```text
peer_attribution_state semantics
peer_attribution_binding_id semantics

projection_pending_attribution schema

retry algorithm

projection state behavior across partial retries

projection_source_checkpoints bootstrap semantics

read_projection_batch after-offset parameter

SQLite capacity footprint definition

WAL checkpoint/truncate policy

runtime capacity state enum

Registry reconciliation ordering
```

All other v1 clauses remain unchanged.

---

# 58. R1 CONSOLIDATED INVARIANTS

```text
R1-I01
Committed edge is immutable across later attribution retry.

R1-I02
Peer attribution on an edge is exact-at-materialization snapshot,
not eventual truth.

R1-I03
Retry re-evaluates only currently pending roles.

R1-I04
Pending row stores non-sensitive counterpart attribution snapshot.

R1-I05
No raw endpoint copy is introduced for retry.

R1-I06
Existing edge digest is never recomputed by retry.

R1-I07
New opposite edge uses frozen counterpart snapshot.

R1-I08
No checkpoint row means no source record has yet been committed.

R1-I09
Offset zero is always a valid source-record offset.

R1-I10
Initial source read uses after=null, never a numeric sentinel.

R1-I11
First checkpoint row is created atomically with first committed disposition.

R1-I12
Projection capacity counts main DB + WAL + SHM + unexpected journal.

R1-I13
Pre-write capacity requires fixed 16 MiB transaction headroom.

R1-I14
Legitimate reader blocking WAL truncation is not corruption
or permanent writer failure.

R1-I15
A batch denied before write does not advance checkpoint.

R1-I16
A transaction already committed remains valid;
its checkpoint is never rewound by post-commit capacity detection.

R1-I17
No live evidence is silently deleted to fake cap compliance.

R1-I18
Registry reconciliation is unresolved-priority
with bounded authoritative fairness.
```

---

# 59. REQUIRED R1 DISPOSITION

```text
TASK =
TASK-DTI-NI-02B

ARCHITECTURE CONTRACT =
v1-R1

P1-01 =
RESOLVED

P1-02 =
RESOLVED

P1-03 =
RESOLVED

P2-01 =
RESOLVED

OPEN_P0 =
0

OPEN_P1 =
0

OPEN_P2 =
0

ARCHITECTURE =
DRAFT FOR TECH LEAD RE-REVIEW

CODER =
HOLD

PRODUCTION CHANGE =
NO
```

---

# 60. NEXT GOVERNANCE STEP

```text
Architect
→ v1-R1 bounded architecture repair

Tech Lead
→ re-review

if PASS:

Tech Lead
→ immediately issue exact Coder implementation TASK

until PASS:

CODER = HOLD
PRODUCTION CHANGE = NO
```
