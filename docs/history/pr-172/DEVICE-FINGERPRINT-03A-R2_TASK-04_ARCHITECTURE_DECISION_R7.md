# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R7

## Regression-Controlled Deterministic Passive Classification Foundation

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-16  
**Status:** `FOR OWNER + TECHLEAD11 STRICT REVIEW`  
**Architecture Contract Final:** `NO`  
**Task-04:** `HOLD`  
**Task-04 Coder Task:** `NO`  
**Production change:** `NO`

---

# 1. Document disposition

This is a complete standalone architecture candidate.

It does not require R6, R5, R4, or any other superseded draft to define an implementation contract.

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R7

STATUS =
FOR OWNER + TECHLEAD11 STRICT REVIEW

R6 =
SUPERSEDED ONLY AFTER R7 ACCEPTANCE

ARCHITECTURE CONTRACT FINAL =
NO

TASK-04 =
HOLD

TASK-04 CODER TASK =
NO

PRODUCTION CHANGE =
NO
```

R7 MUST NOT self-promote.

Only:

```text
OWNER ACCEPT
+
TECHLEAD11 ACCEPT
```

may promote the architecture contract to FINAL.

After architectural acceptance, PRE-TASK foundation implementation may begin only through separate TechLead tasks and explicit Owner authorization.

Task-04 remains HOLD until Foundation Admission passes.

---

# 2. Owner quality and regression policy

R7 is governed by:

```text
NO REVISION LIMIT.

NO KNOWN CONTRADICTION.
NO KNOWN BUG.
NO UNDEFINED SEMANTIC.
NO CIRCULAR GATE.
NO HIDDEN SOURCE PRIORITY.
NO APPROXIMATE DETERMINISM.
NO UNDEFINED ARTIFACT.
NO SILENT FALLBACK.
NO SILENT REGRESSION.
```

A rewrite that fixes one defect while silently deleting an already-correct contract is REVIEW FAIL.

R7 therefore ends with an explicit architecture-preservation/regression matrix and five additional control appendices.

---

# 3. Verified repository baseline

R7 was prepared against:

```text
repository =
ZaurNavi/CaptivePortal

default branch =
main

main commit =
d37d3ec126ccd512fe835af0db21221e2f83d565

main tree =
3145e904ad5027d0d584945f4814f3ade59d44ea
```

Current accepted normalized evidence families are:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

Current Task-01 persists `payload_json` and `payload_sha256`, plus evidence/source metadata.

Current source-health persisted status enum is:

```text
available
unavailable
unsupported
```

Current Task-01 evidence read API is cursor-paginated with a maximum page size of 500.

Current Task-01 default timestamp/retention settings include:

```text
evidence retention =
30 days

maximum future source-event skew =
120 seconds

maximum delayed event age =
86400 seconds
```

Current network sensor emits bounded same-state source-health heartbeats with a 300-second cadence.

Current portal source-health does not yet provide equivalent visitor-independent periodic liveness.

Current Task-01 schema is strict schema version 1 and therefore requires an explicit v1→v2 migration contract before watermark fields can exist.

---

# 4. Exact Task-03A status

```text
TASK-DEVICE-FINGERPRINT-03A
TOOLING / RESEARCH FOUNDATION =
IMPLEMENTED / AVAILABLE
```

This does NOT mean:

```text
old 12-device / 48-sample empirical campaign completed
```

Canonical truth:

```text
old 12-device / 48-sample campaign =
NOT REQUIRED
NOT TASK-04 BLOCKER

full historical physical matrix campaign =
NOT CLAIMED COMPLETED
```

No acceptance or roadmap text may conflate tooling availability with completion of a large physical-device campaign.

---

# 5. Task boundaries

Task-04 V1 owns only:

```text
classification foundation integration

EvidenceSnapshot materialization integration

versioned EvidenceAdapters

SourceEvaluability consumption

OriginAssessment construction

pure fusion

DimensionResult / global ClassificationResult

derived classification persistence

internal read contract

audit/replay
```

Task-04 V1 DOES NOT add:

```text
Device Card UI

Admin UI presentation

public classification API

Authorization policy changes

CAPPORT admission changes

cross-MAC identity

identity/session integration

automatic learning/training
```

Identity/session integration is later work.

Presentation is later work.

Any public/API/UI scope requires a separate task/architecture decision.

---

# 6. Lifecycle — no gate cycle

Exact lifecycle:

```text
R7 architecture candidate
        ↓
Owner + TechLead11 ACCEPT
        ↓
Architecture Contract FINAL
        ↓
TechLead11 decomposes PRE-TASK foundation work
        ↓
Owner authorizes bounded foundation implementation
        ↓
Coder implements bounded PRE-TASK foundation tasks
        ↓
Foundation Admission gates PASS
        ↓
TechLead11 decomposes TASK-04
        ↓
Owner authorizes TASK-04
        ↓
Coder implements TASK-04
        ↓
TASK-04 Acceptance gates PASS
        ↓
accepted Task-04 candidate
```

No Foundation gate requires Task-04 classifier code.

No Task-04 Acceptance gate is required before Task-04 decomposition.

---

# 7. Permanent architecture principles

Permanent invariants:

```text
normalized evidence
!= classification
!= device identity proof

classification is advisory

classification never affects Authorization

classification never affects CAPPORT admission

classification is not a security identity signal

support_level
!= probability

row count
!= independent vote count

same origin interpreted by multiple knowledge systems
!= multiple independent origins

raw packets are non-durable

raw User-Agent is non-durable

raw Client Hints are non-durable

no cross-MAC identity merge

unknown is valid

insufficient_evidence is valid

conflicting_evidence is valid

recognized_out_of_scope is dimension-bounded

Task-01 evidence storage
!= Task-04 classification storage

external vendor artifact
!= runtime schema

runtime classifier requires no Internet

snapshot membership is deterministic and explicit

coverage completeness
!= validity of evidence that is actually present

knowledge freshness is explicit input

classification meaning is versioned

pure classification core performs no I/O and no wall-clock read

retained classifications retain retrievable immutable audit inputs

validation never trains production automatically
```

---

# 8. EvidenceCanonicalJsonV1 — existing Task-01 payload contract

Normalized Task-01 payload integrity uses the existing CaptivPortal evidence canonicalization contract.

`EvidenceCanonicalJsonV1` is:

```text
Python stdlib json.dumps

ensure_ascii = True
allow_nan = False
sort_keys = True
separators = (",", ":")
UTF-8 encoding for SHA-256
```

Current normalized evidence schemas are expected to validate the allowed value types before persistence.

Evidence timestamps remain exact canonical UTC:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

This contract is used when re-verifying persisted Task-01 normalized payloads during snapshot materialization.

It is distinct from the stricter artifact canonicalization below.

---

# 9. ArtifactCanonicalJsonV1

All immutable R7 architecture/runtime artifacts use one exact byte-level canonical encoder named:

```text
ArtifactCanonicalJsonV1
```

Before encoding, recursively:

```text
all object keys MUST be strings

all strings are normalized to Unicode NFC

semantic timestamps MUST already match:
YYYY-MM-DDTHH:MM:SS.mmmZ

arrays MUST already be in the exact ordering
defined by the artifact contract

floats are FORBIDDEN

Decimal objects are FORBIDDEN

NaN and Infinity are FORBIDDEN

numeric semantic values use integers where possible

non-integer semantic values, if ever needed,
use a separately specified canonical decimal string
rather than JSON float
```

Encoding is exactly:

```text
Python stdlib json.dumps

ensure_ascii = True
allow_nan = False
sort_keys = True
separators = (",", ":")
```

Additional exact rules:

```text
UTF-8 encode the resulting JSON text

JSON booleans are exactly:
true
false

JSON null is exactly:
null

integers use standard JSON decimal integer output
with no leading plus sign and no locale formatting

encoder does not pretty-print

encoder does not add trailing newline

slash is not specially escaped beyond Python stdlib behavior
```

A canonical fixture corpus SHALL pin byte outputs for:

```text
ASCII strings
non-ASCII BMP strings
non-BMP Unicode
NFC-equivalent input
booleans
null
positive/zero/negative allowed integers
nested objects
ordered arrays
timestamps
escaping of quote/backslash/control characters
```

The implementation version of `ArtifactCanonicalJsonV1` is itself part of foundation/classifier artifact identity.

Equivalent intended semantic strings normalize to the same NFC form before hashing.

---

# 10. ArtifactContent and ArtifactRegistration

Semantic identity and audit registration are separate.

## ArtifactContent

Immutable semantic object:

```text
artifact_type

artifact_schema_version

semantic_payload

content_sha256

artifact_id
```

Digest input:

```json
{
  "artifact_type": "<type>",
  "artifact_schema_version": 1,
  "semantic_payload": {}
}
```

`content_sha256`:

```text
SHA-256(
    ArtifactCanonicalJsonV1(digest_input).UTF8
)
```

`artifact_id`:

```text
<artifact_type>:v<artifact_schema_version>:sha256:<content_sha256>
```

An ArtifactContent with the same semantic bytes has the same artifact ID.

An ArtifactContent with different semantic bytes MUST have a different artifact ID.

No metadata is physically embedded inside ArtifactContent under the same identity.

## ArtifactRegistration

Separate immutable audit registration:

```text
registration_id

artifact_id

registered_at_utc

registered_by

review_registration_refs

owner_decision_ref where applicable

repository_commit_sha where applicable

repository_tree_sha where applicable

notes/reference metadata
```

`registration_id` is canonical lowercase UUIDv4.

Two registrations may point to the same ArtifactContent.

This permits:

```text
same semantic content
same artifact_id

different creation/review registrations
different registration_id
```

without identity ambiguity.

---

# 11. Artifact activation discipline

Every runtime artifact that has a mutable concept of "current/active" uses:

```text
immutable ArtifactContent
+
atomic active pointer
```

This applies at least to:

```text
KnowledgeBundle

EvidenceSourceBindingTimeline

BindingClockPolicy

SourceHealthPolicy

SnapshotContentPolicy

SnapshotExecutionPolicy

EvidenceSchemaRegistryContract

EvidenceAdapterContractSet

ClassificationPolicy
```

Rules:

```text
accepted artifact content never mutates

activation changes only the active pointer

in-flight request pins the already-selected artifact IDs/digests once

refresh cannot mutate an in-flight request

rollback atomically points to a previously accepted immutable artifact
```

`SnapshotExecutionPolicy` is operational, not a pure-classification semantic input, but its persisted version/identity is pinned in SnapshotRecord for audit.

---

# 12. Complete immutable/audit object catalog

R7 defines exact identity classes for all referenced objects.

Semantic ArtifactContent types include:

```text
ArchitectureContractReference

Task01WatermarkReadContract
Task01SchemaMigrationContract
Task01GenerationRecoveryContract
Task01HealthRetentionContract

EvidenceSourceBindingTimeline
BindingClockPolicy
SourceHealthPolicy

SnapshotContentPolicy
SnapshotExecutionPolicy

EvidenceSchemaRegistryContract
EvidenceAdapterContractSet

KnowledgeFreshnessPolicy
SourceGovernanceRecord
KnowledgeProvenanceManifest
KnowledgeBundle

ClassificationTaxonomy
AliasMapping
K3PortalRuleSet

ClassificationPolicy
ClassificationRetentionPolicy
ProductValidationPolicy

ClassifierArtifactManifest

EvidenceSnapshotContent
SourceEvaluability
OriginAssessment
ClassificationRequestManifest
ClassificationResult

GateResultManifest
FoundationAdmissionManifest
Task04AcceptanceManifest

SnapshotRecord
```

Transient, NON-retained execution object:

```text
EvidenceSnapshotMaterialization
```

Audit registration object:

```text
ArtifactRegistration
```

Gate retained evidence files are identified by SHA-256 and referenced from GateResultManifest; they need not all be ArtifactContent objects unless explicitly promoted.

Appendix C repeats the full catalog with identity/retention rules.

---

## 12.1 ArchitectureContractReference

`ArchitectureContractReference` is ArtifactContent created only after Owner + TechLead11 accept a concrete architecture Markdown file.

Semantic payload:

```text
architecture_contract_name =
DEVICE-FINGERPRINT-03A-R2 / TASK-04

architecture_revision =
R7

architecture_status =
FINAL

architecture_document_sha256 =
SHA-256 of the exact accepted Markdown file bytes
```

Its ArtifactContent ID/digest is the canonical `architecture_contract_id/digest` later recorded by FoundationAdmissionManifest.

The architecture file SHA is outside/self-independent from the Markdown body, avoiding a self-hash cycle.

# 13. Task-01 v1 → v2 migration contract

Current strict Task-01 schema v1 cannot be assumed to accept watermark columns transparently.

PRE-TASK foundation therefore requires an explicit:

```text
Task-01 schema migration
v1 → watermark-capable v2
```

Migration requirements:

```text
Task-01 writer stopped

pre-migration DB path/size/identity recorded

cryptographic digest of pre-migration backup recorded

disk/capacity headroom checked

exclusive migration boundary acquired

all existing evidence rows preserved

all existing payload_json values preserved

all evidence IDs preserved

all source-health IDs preserved

all producer/event uniqueness preserved

new database_generation_id minted

bootstrap ingest_sequence assigned deterministically

allocator initialized above highest assigned sequence

new indexes/constraints created/validated

PRAGMA user_version advanced to the accepted v2 value

PRAGMA quick_check PASS

PRAGMA integrity_check PASS for deployment migration gate

writer remains stopped until all validation PASS
```

Failure:

```text
NO partially migrated production DB becomes active
```

Migration must be atomic or cleanly recoverable from the recorded pre-migration backup.

Canonical output:

```text
Task01SchemaMigrationContract
+
GateResultManifest
```

---

# 14. Application activation and rollback after DB migration

Activation order:

```text
1. stop old Task-01 writer

2. create and verify pre-migration DB backup

3. deploy v2-capable Task-01 code without starting writer

4. execute v1→v2 migration

5. run schema/integrity/query validation

6. start v2 writer

7. verify ingest/read health
```

Rollback categories:

## v2-compatible application rollback

A rollback to another application revision explicitly proven compatible with Task-01 schema v2 may reuse the v2 DB.

## pre-v2 application rollback

Old Task-01 code is NOT assumed to accept schema v2.

Rollback to a pre-v2 binary therefore requires:

```text
stop v2 writer

restore the verified pre-migration v1 DB backup

restore compatible pre-v2 application

validate v1 DB

start pre-v2 writer
```

This emergency rollback discards Task-01 rows committed only after the migration unless a separately reviewed recovery/export path exists.

Therefore it requires explicit Owner/TechLead recovery decision acknowledging that consequence.

When later returning from restored v1 to watermark-capable v2:

```text
perform the controlled migration again
mint a new database_generation_id
rebaseline sequence state
```

No claim is made that old code can operate safely on the new schema.

---

# 15. Global ingest sequence

Both:

```text
device_fingerprint_evidence

device_fingerprint_source_health_events
```

receive one shared:

```text
ingest_sequence
```

Domain:

```text
signed 64-bit positive integer

row sequence minimum = 1

maximum = 9223372036854775807
```

Properties:

```text
monotonic within one valid database generation

assigned by Task-01 storage owner

never derived from UUID

never derived from SQLite rowid

never derived from wall clock

never reused after a successful commit in the same generation
```

Allocator exhaustion:

```text
FAIL CLOSED

no wrap

no new classification-relevant ingest
```

---

# 16. Ingest allocation transaction

Sequence allocation and row insert are one Task-01 SQLite write transaction.

Conceptually:

```text
BEGIN serialized writer transaction

validate request

resolve idempotent duplicates

reject conflicting duplicates

allocate sequence values for NEW semantic rows

insert evidence / health rows

advance durable allocator state

COMMIT
```

Rollback rolls back both row writes and allocator state from that transaction.

---

# 17. Duplicate, gap and cleanup semantics

Identical idempotent duplicate:

```text
no new semantic row

no new ingest_sequence
```

Conflicting duplicate under the same unique producer/event identity:

```text
transaction rollback

no conflicting row admitted
```

Sequence gaps are allowed and semantically meaningless.

Retention DELETE:

```text
does not advance ingest_sequence

does not reuse sequence values

does not lower allocator state
```

No "latest duplicate wins".

---

# 18. Database generation and empty watermark

`database_generation_id` format:

```text
canonical lowercase UUIDv4
xxxxxxxx-xxxx-4xxx-[89ab]xxx-xxxxxxxxxxxx
```

A watermark is:

```text
database_generation_id
max_committed_ingest_sequence
```

Canonical empty-generation watermark:

```text
valid database_generation_id

max_committed_ingest_sequence = 0
```

Row sequence domain remains:

```text
1..9223372036854775807
```

No null, negative or ambiguous empty watermark.

---

# 19. Initial sequence bootstrap

The v1→v2 migration deterministically assigns sequence values to all retained classification-relevant v1 rows.

Bootstrap order is documented by the migration contract.

Bootstrap order is NOT claimed to reconstruct historical commit order.

After migration:

```text
all retained rows belong to the newly minted generation
```

Task-04 windows are still limited by `classification_foundation_valid_from_utc`; old retained rows are not automatically made classification-authoritative.

---

# 20. Controlled restore / rollback recovery

Any controlled DB/VM/filesystem rollback that can move sequence state backward MUST execute generation recovery before v2 writer accepts new ingestion.

Recovery:

```text
writer stopped

restored DB opened exclusively

NEW database_generation_id minted

all retained classification-relevant evidence/health rows
deterministically rebaselined

new monotonic sequences assigned

allocator state set above highest assignment

indexes/constraints/integrity validated

writer allowed only after PASS
```

Old snapshot/audit artifacts continue to refer to the old generation.

They may cease to be reconstructable from the new rebaselined Task-01 DB.

---

# 21. Restore detection limitation

R7 does NOT claim automatic detection of an arbitrary external rollback that restores:

```text
DB
generation metadata
application state
all local guards
```

to an older self-consistent image.

Operational invariant:

```text
known or controlled rollback that can move sequence state backward
MUST run generation recovery before writer restart
```

Violation invalidates watermark guarantees until repaired.

---

# 22. Ingest watermark meaning

Canonical watermark:

```text
IngestWatermark {
    database_generation_id,
    max_committed_ingest_sequence
}
```

Meaning:

```text
all classification-relevant committed rows
with sequence <= W
that exist in the active SQLite read snapshot
are in the watermark-visible row universe
```

Watermark freezes insertion visibility.

SQLite read transaction freezes the concurrent database view.

Both are required.

---

# 23. One SQLite read transaction

Every live EvidenceSnapshot build uses:

```text
one read-only SQLite connection
+
one SQLite read transaction
```

for:

```text
establishing read snapshot

database generation read

watermark capture

all evidence pagination

all source-health reads

all predecessor/anchor reads

scope-authority checks requiring Task-01 rows
```

Forbidden:

```text
new DB connection per page

transaction restart during one snapshot

watermark refresh mid-build

health read from a different SQLite snapshot
```

Concurrent:

```text
ingest

retention DELETE

WAL checkpoint
```

must not alter the already-established reader view.

---

# 24. Live snapshot mode

Normal caller supplies only:

```text
site_id

observed_mac

window_start_utc

window_end_utc
```

Caller does NOT choose:

```text
database_generation_id

ingest watermark

snapshot captured time

BindingTimeline version

BindingClockPolicy version

SnapshotContentPolicy version
```

Snapshot service pins those from accepted active foundation artifacts exactly once.

---

# 25. Replay snapshot mode

Audit replay uses exact retained historical identities:

```text
EvidenceSnapshotContent ID/digest

database generation

watermark

window

BindingTimeline ID/digest

BindingClockPolicy ID/digest

FoundationAdmissionManifest ID/digest

stored snapshot manifest
```

Level-A Task-01 reconstruction is possible only while required source rows/generation remain available.

Level-B replay is based on retained derived audit objects.

---

# 26. Completed-window validity

V1 live request:

```text
window_start_utc < window_end_utc

window_start_utc >= classification_foundation_valid_from_utc

window_end_utc <= snapshot_captured_at_utc
```

No live classification of future event time.

No hidden open/current-window mode.

A future open-window use case requires an explicit new mode/architecture.

---

# 27. Snapshot semantic content vs capture metadata

Two objects:

## EvidenceSnapshotContent

Durable semantic/audit ArtifactContent.

Contains membership, descriptors, digests, bindings, watermark and exact semantic builder dependencies.

Does NOT durably duplicate normalized payload values.

## SnapshotRecord

Durable audit ArtifactContent for a successfully accepted snapshot build used by classification.

Semantic payload is exactly:

```text
EvidenceSnapshotContent ID/digest

FoundationAdmissionManifest ID/digest

snapshot_captured_at_utc

SnapshotContentPolicy ID/digest

SnapshotExecutionPolicy ID/digest

materialized_evidence_row_count

materialized_payload_bytes

total_semantic_input_bytes

scope_anomaly_count

ordered scope_anomaly_reason_counts:
    reason_code
    count

build_outcome = "success"
```

Scope-anomaly reason counts are ordered lexicographically by `reason_code`.

Failed/retryable snapshot attempts may be logged operationally, but no classification-linked successful SnapshotRecord is created for them.

`SnapshotRecord` is retained while any classification references it.

Capture time is not included in `EvidenceSnapshotContent` digest.

---

# 28. EvidenceSnapshotContent semantic dependencies

EvidenceSnapshotContent payload includes at least:

```text
snapshot_contract_version

site_id

observed_mac

window_start_utc

window_end_utc

database_generation_id

max_committed_ingest_sequence

FoundationAdmissionManifest ID/digest

EvidenceSourceBindingTimeline ID/digest

BindingClockPolicy ID/digest

EvidenceSchemaRegistryContract ID/digest

classification_foundation_valid_from_utc

ordered binding-epoch descriptors

ordered authorized evidence descriptors

ordered authorized source-health descriptors
```

No hidden "currently active" semantic builder dependency.

`SnapshotContentPolicy` is not inside semantic evidence membership identity; it is pinned in SnapshotRecord because it governs whether a build is accepted/too large rather than the meaning of each member row.

---

# 29. Evidence descriptor

Durable evidence descriptor contains:

```text
evidence_id

ingest_sequence

producer_id

source_kind

source_subtype

capture_source_id

extractor_name

extractor_version

feature_schema_version

rule_version

site_id

observed_at

ingested_at

observed_mac

privacy_class

quality_state

payload_sha256

binding_epoch_id
```

No durable copy of `payload_json` in Task-04 classification storage.

`observed_ip` is NOT Task-04 V1 classifier input.

---

# 30. Source-health descriptor

Durable health descriptor contains:

```text
source_health_id

ingest_sequence

producer_id

source_kind

capture_source_id

status

reason_code

observed_at

ingested_at

content_sha256

binding_epoch_id
```

---

# 31. EvidenceSnapshotMaterialization — transient execution object

Task-04 classification requires actual normalized evidence features.

R7 therefore defines a separate transient:

```text
EvidenceSnapshotMaterialization
```

It contains:

```text
EvidenceSnapshotContent ID/digest

ordered materialized evidence entries
```

Each materialized evidence entry contains:

```text
the corresponding durable evidence descriptor

parsed normalized payload object
```

It is built inside the SAME SQLite read transaction that constructs EvidenceSnapshotContent.

It is passed to EvidenceAdapters/pure classification execution.

It is NOT persisted into the classification DB after execution.

It is NOT retained for classification-history replay.

After Task-01 source evidence expires:

```text
Level-A replay may be unavailable
```

Level-B replay remains based on retained OriginAssessments and other derived immutable objects.

---

# 32. Materialization payload integrity

For every evidence row inside the one SQLite read transaction:

```text
read payload_json

parse JSON with duplicate-key rejection

validate JSON value is an object

validate against the exact EvidenceSchemaRegistry contract
for source_kind / feature_schema_version

re-encode using EvidenceCanonicalJsonV1

verify encoded canonical string equals the stored canonical payload_json

SHA-256(canonical payload UTF-8)
MUST equal payload_sha256
```

Any mismatch:

```text
SNAPSHOT BUILD FAIL

NO EvidenceSnapshotContent accepted

NO materialization returned

NO SourceEvaluability

NO ClassificationResult
```

No "trust the hash but ignore bytes" fallback.

No opportunistic parse of unknown future schema.

---

# 33. EvidenceSchemaRegistryContract

PRE-TASK foundation freezes an immutable:

```text
EvidenceSchemaRegistryContract
```

It identifies exact normalized-schema validators for:

```text
dhcp/1

tcp_syn/1

tcp_syn/2

tls_client/1

quic_client/1

portal_headers/1

portal_headers/2 if admitted
```

This registry is used for snapshot materialization integrity/type validation.

It is distinct from:

```text
EvidenceAdapterContractSet
```

which defines classification compatibility/interpretation.

Unknown source/schema:

```text
may remain in Task-01 storage

cannot be materialized for Task-04 semantics
without an accepted registry contract
```

---

# 34. Canonical snapshot ordering

Evidence descriptors/materialized entries:

```text
origin_group
source_kind
capture_source_id
producer_id
observed_at
ingest_sequence
evidence_id
```

Health:

```text
origin_group
source_kind
capture_source_id
producer_id
observed_at
ingest_sequence
source_health_id
```

Bindings:

```text
effective_from_utc
origin_group
source_kind
capture_source_id
producer_id
binding_epoch_id
```

Pagination boundary and SQLite incidental row order have no semantic effect.

---

# 35. Complete pagination

Current Task-01 maximum evidence page size is 500.

Snapshot build MUST paginate to exhaustion inside the one read transaction.

Forbidden:

```text
first 500 rows
→ classify
```

A meaningful contradictory/variant row after page 1 must still be observed.

---

# 36. SnapshotContentPolicy — actual input sizing

`SnapshotContentPolicy` is an immutable ArtifactContent that governs deterministic content ceilings.

It sizes the REAL classifier input, not hashes alone.

Deterministic measurement includes:

```text
authorized evidence descriptor bytes

canonical normalized payload bytes for every materialized row

authorized source-health descriptor bytes

binding descriptor bytes

required semantic dependency reference bytes
```

Canonical payload byte count:

```text
sum(
  len(
    EvidenceCanonicalJsonV1(normalized_payload).encode("utf-8")
  )
)
```

Descriptor/health/binding byte count uses ArtifactCanonicalJsonV1 over the exact ordered semantic structures.

Policy may cap:

```text
max_authorized_evidence_rows

max_authorized_health_rows

max_materialized_payload_bytes

max_total_semantic_input_bytes
```

If a deterministic content ceiling is exceeded:

```text
snapshot build result =
resource_limited

NO partial ClassificationResult
```

Exact production values are measured/frozen by Foundation gate, not guessed.

---

# 37. SnapshotExecutionPolicy

Separate operational immutable policy:

```text
maximum read-transaction wall-clock duration

SQLite busy/retry behavior

process memory guard

operational retry limits
```

Execution failure due:

```text
CPU pressure
wall-clock timeout
temporary memory pressure
SQLite busy/transient failure
```

is:

```text
retryable/non-semantic snapshot build failure

NO ClassificationResult
```

It never becomes semantic `not_evaluable`.

---

# 38. Snapshot query/WAL performance contract

The single long read transaction must be proven operationally safe.

Foundation proof measures:

```text
EXPLAIN QUERY PLAN / query plan

index use

page count

snapshot evidence row count

snapshot health row count

materialized payload bytes

total semantic input bytes

read transaction duration

WAL growth while reader is open

checkpoint progress/behavior

writer latency

retention DELETE latency

CPU and memory consumption
```

PASS requires expected product snapshots to remain inside an accepted operational envelope without materially destabilizing Task-01 ingest.

Indexes may be added only where proven query-plan evidence justifies them.

Increasing timeout blindly is NOT an accepted performance fix.

---

# 39. EvidenceSourceBindingTimeline

Immutable deployment-side ArtifactContent.

Covers Task-01 acquisition origins only:

```text
dhcp
portal
tcp
tls
quic
```

Explicitly excludes:

```text
mac_registry
```

Each epoch:

```text
binding_epoch_id

site_id

origin_group

source_kind

capture_source_id

producer_id

effective_from_utc

effective_to_utc
```

Interval:

```text
[effective_from_utc, effective_to_utc)
```

No unused `required` boolean.

Presence of binding means source expected for the interval.

---

# 40. Single authoritative binding V1

At every non-quarantined event-time point V1 permits at most one authoritative:

```text
(site_id, origin_group, source_kind)
→
producer_id + capture_source_id
```

No HA/redundant producer semantics in V1.

Any future redundancy requires explicit architecture extension.


# 41. Binding-authorized membership

A Task-01 evidence row enters EvidenceSnapshotContent only when ALL are true:

```text
site_id matches request

observed_mac matches request

source_kind maps to the expected origin

producer_id matches the authoritative binding epoch

capture_source_id matches the authoritative binding epoch

observed_at lies inside that epoch outside cutover quarantine

ingest_sequence <= captured watermark
```

Source-health rows use the same authority rule except there is no observed_mac condition.

Unauthorized rows are excluded from semantic input and may only appear in bounded SnapshotRecord scope-anomaly audit.

---

# 42. BindingClockPolicy and cutover quarantine

Binding authority uses producer event time, therefore cutovers require explicit clock semantics.

`BindingClockPolicy` payload includes:

```text
policy version

producer clock-domain identities

Task-01 central clock-domain identity

measured maximum relative clock offset

measurement method/evidence reference

cutover_guard_seconds
```

Exact guard is Foundation-proofed.

At cutover `T`:

```text
[T - guard, T + guard)
```

is quarantine unless proof permits `guard = 0`.

Rows in quarantine:

```text
not assigned silently to old/new source

not used for fusion

recorded as binding_cutover_ambiguous

coverage class = unknown
```

Task-01's general future-skew allowance is NOT accepted as proof of pairwise producer cutover accuracy.

---

# 43. Classification foundation valid-from

R7 does not invent historical source authority.

Foundation Admission freezes:

```text
classification_foundation_valid_from_utc = T
```

`T` is no earlier than:

```text
watermark-capable Task-01 v2 active

accepted BindingTimeline active

BindingClockPolicy proven

SourceHealthPolicy active

health baseline can be established

EvidenceSchemaRegistryContract active

EvidenceAdapterContractSet accepted
```

Task-04 rejects:

```text
window_start_utc < T
```

Older Task-01 evidence remains research/audit data but is not automatically classification-authoritative.

---

# 44. Source health means coverage, not evidence truth

Source-health exists to describe:

```text
source capability

acquisition availability

delivery availability

coverage/completeness uncertainty
```

It does NOT invalidate a normalized evidence row that is actually present and adapter-compatible.

It does NOT turn evidence absence into a negative device fingerprint.

---

# 45. Conservative V1 coverage classes

R7 deliberately removes `covered_delayed`.

Transport recovery/backfill does NOT prove interval completeness because current producer buffering can stale-drop, evict, capacity-block, or otherwise lose evidence.

V1 coverage classes are exactly:

```text
covered_available

acquisition_unavailable

delivery_unavailable_loss_possible

delivery_loss_confirmed

unsupported

unknown
```

Definitions:

## covered_available

Acquisition and central delivery are known healthy for the interval under accepted heartbeat/freshness semantics.

## acquisition_unavailable

The acquisition source itself could not collect the relevant evidence.

## delivery_unavailable_loss_possible

Acquisition may have continued but central delivery was impaired and completeness cannot be proven.

Actual delayed evidence that later arrives remains usable as present evidence, but absence during the interval remains uninterpretable.

## delivery_loss_confirmed

Known loss occurred.

## unsupported

Intentional capability state.

## unknown

Coverage cannot be established conservatively, including stale/missing heartbeat, unknown reason, cutover quarantine, or unproven failure semantics.

There is NO V1 transition:

```text
recovery available
→ covered_delayed
```

A future completeness-checkpoint protocol requires a separate architecture extension.

---

# 46. SourceHealthPolicy

Immutable SourceHealthPolicy contains per source/producer family:

```text
expected heartbeat contract

freshness rule

Task-01 timestamp/skew contract reference

Task-01 delayed-event contract reference

reason_code → failure-domain mapping

coverage-class mapping

backfill rules

health-retention margin requirement
```

Unknown/unrecognized `reason_code`:

```text
→ unknown
```

No Coder guess.

No producer gets a lossless-delivery guarantee unless separately proven by future architecture.

---

# 47. Transport failure truth

If source acquisition fails but producer→Task-01 transport remains healthy:

```text
producer may deliver live unavailable health
```

If producer→Task-01 transport fails:

```text
central DB cannot receive a live unavailable event over the failed transport
```

Therefore:

```text
last heartbeat ages out
→ central coverage = unknown
```

On recovery, bounded historical health may be backfilled only when:

```text
producer reliably knows the interval

AND
Task-01 delayed-event contract still permits the event
```

Even when historical health is backfilled, R7 does NOT infer completeness of missing device evidence.

---

# 48. Health backfill and delayed-event contract

Historical health backfill obeys Task-01's active delayed-event acceptance.

If the outage start/end is outside admissible delayed age:

```text
do not fabricate an inadmissible old health event

central interval remains conservatively unknown
```

Changing the Task-01 delayed-event contract requires a separate bounded foundation change/review.

---

# 49. Task-01-native health retention margin

Task-01 source-health cleanup MUST NOT parse EvidenceSourceBindingTimeline.

Instead, PRE-TASK freezes a Task-01-native:

```text
health_anchor_margin_seconds
```

derived from accepted SourceHealthPolicy.

Safety invariant:

```text
source_health_retention
>=
evidence_retention
+
health_anchor_margin
```

The margin MUST cover the maximum interval by which a predecessor health event can still be semantically relevant at the oldest retained evidence boundary, including accepted freshness/clock uncertainty required by SourceHealthPolicy.

Cleanup remains ordinary time-based Task-01 cleanup.

Foundation proof establishes the exact margin.

No equal evidence/health retention is accepted unless proof shows the margin is zero.

Canonical output:

```text
Task01HealthRetentionContract
```

---

# 50. Health state does not cross binding epoch

At a new binding epoch:

```text
old producer health state is NOT inherited
```

New epoch starts as:

```text
unknown
```

until its authorized health establishes state.

Cutover quarantine remains unknown.

---

# 51. Evidence-present vs coverage-state behavior

Present evidence and missing evidence are treated separately.

| Present compatible evidence | Coverage at event time | Evidence use | Coverage meaning |
|---|---|---|---|
| yes | covered_available | usable | normal |
| yes | acquisition_unavailable | usable | inconsistency recorded; evidence remains usable |
| yes | delivery_unavailable_loss_possible | usable | present backfill usable; absence elsewhere uninterpretable |
| yes | delivery_loss_confirmed | usable | present row usable; interval incomplete |
| yes | unsupported | usable | inconsistency recorded |
| yes | unknown | usable | health unknown recorded |
| no | covered_available | no claim | absence still NOT negative fingerprint |
| no | acquisition_unavailable | no claim | expected acquisition gap |
| no | delivery_unavailable_loss_possible | no claim | absence uninterpretable |
| no | delivery_loss_confirmed | no claim | absence uninterpretable |
| no | unsupported | no claim | intentional capability absence |
| no | unknown | no claim | absence uninterpretable |

Health primarily describes completeness/coverage.

It does not erase valid present evidence.

---

# 52. SourceEvaluability states

Aggregate states:

```text
evaluable

partially_evaluable

not_evaluable

unknown
```

## evaluable

All expected non-quarantined interval segments are `covered_available`.

## partially_evaluable

At least one segment is `covered_available` and at least one is another coverage class.

## not_evaluable

No segment is covered_available, no segment is unknown/delivery-loss-possible, and the full interval is positively known as:

```text
acquisition_unavailable
delivery_loss_confirmed
unsupported
```

## unknown

No segment is covered_available and at least one segment is:

```text
unknown
delivery_unavailable_loss_possible
binding-cutover quarantine
```

This object reports coverage only, not evidence-row schema compatibility.

---

# 53. SourceEvaluability canonical interval normal form

Each source/binding entry partitions the applicable window/binding segment into half-open intervals:

```text
[start_utc, end_utc)
```

Canonical interval normalization:

```text
sorted by start_utc

non-overlapping

clipped exactly to the applicable window ∩ binding interval

complete partition of every non-zero applicable segment

adjacent intervals with identical coverage_class
and identical reason classification are merged

zero-length intervals forbidden

end of one interval equals start of the next
for complete partitions

cutover quarantine represented explicitly as unknown
```

Explanation codes:

```text
deduplicated

sorted lexicographically
```

Reason classifications use stable enum ordering defined by SourceHealthPolicy.

Two semantically equal coverage reconstructions MUST serialize identically.

---

# 54. SourceEvaluability ArtifactContent

Payload:

```text
evidence_snapshot_content_id/digest

source_health_policy_id/digest

ordered source entries
```

Each source entry:

```text
origin_group

source_kind

binding_epoch_id

producer_id

capture_source_id

aggregate_evaluability_state

ordered normalized coverage_intervals:
    start_utc
    end_utc
    coverage_class
    reason_classification
    reason_code references where relevant

ordered explanation_codes
```

Ordering:

```text
origin_group
source_kind
binding epoch effective_from
producer_id
```

`mac_registry` has no SourceEvaluability entry.

SourceEvaluability content is retained for Level-B audit.

---

# 55. EvidenceAdapterContractSet

Each classification origin/schema has an explicit contract.

Each entry freezes:

```text
origin_group

source_kind

feature_schema_version

supported source_subtypes

extractor_name/version compatibility constraints

rule_version compatibility constraints where semantically required

quality_state handling

required normalized payload fields per dimension

legacy/current role

claim_derivation

base claim_strength ceiling

semantic projection for dedup

unsupported behavior
```

Unknown future schema is never parsed opportunistically.

---

# 56. Evidence schema vs classification adapter

Two distinct contracts:

```text
EvidenceSchemaRegistryContract
→ "is this normalized payload structurally valid for this schema?"

EvidenceAdapterContractSet
→ "is this valid evidence supported for classification and how?"
```

A structurally valid Task-01 row may be intentionally non-fusion.

No implementation conflates storage validity with classification support.

---

# 57. quality_state semantics

Current Task-01 values:

```text
valid
partial
degraded
```

V1 classification rules:

## valid

Eligible for normal adapter claim-strength rules.

## partial

Usable only if the adapter proves every normalized field required for that particular dimension is present.

Any claim generated from `partial` is capped:

```text
claim_strength = supporting
```

## degraded

No semantic classification claim in V1.

Retained for:

```text
audit
explanation
engineering diagnostics
```

No degraded row gets the same authority as valid by default.

---

# 58. V1/V2 coexistence

Explicit launch behavior:

```text
dhcp/1 =
supported by explicit adapter

tcp_syn/1 =
auditable
NOT fusion-eligible
reason:
legacy_tcp_schema_insufficient_for_exact_k2a_contract

tcp_syn/2 =
fusion-eligible after Foundation Admission

tls_client/1 =
supported structurally
semantic claims only if admitted JA4/reference knowledge exists

quic_client/1 =
supported structurally
semantic claims only if admitted JA4/reference knowledge exists

portal_headers/1 =
supported by explicit adapter

portal_headers/2 =
supported only if Client-Hints Foundation admission passes
otherwise unsupported for classification
```

No destructive rewrite required.

No `latest schema wins`.

Equivalent same-origin V1/V2 semantic projections collapse and never create duplicate votes.

---

# 59. tcp_syn/2 principle

`tcp_syn/2` persists minimum protocol-semantic facts needed for admitted passive adapters.

It does NOT persist:

```text
p0f quirks

p0f raw signature

p0f option token dialect

p0f label

Fingerbank TCP string

OS/device guess
```

Pipeline:

```text
complete eligible SYN
→ protocol-semantic tcp_syn/2
→ transient adapters
→ K2A/K2B interpretation
```

---

# 60. tcp_syn/2 initial scope

```text
IPv4 only

outbound guest request SYN

SYN=1

ACK=0 eligibility

unfragmented IPv4

complete required Ethernet/IP/TCP header bytes

current controlled pre-router RSPAN placement
```

Not claimed:

```text
IPv6 parity
SYN-ACK parity
fragment reassembly
universal p0f parity
```

---

# 61. tcp_syn/2 durable top-level facts

Exactly the initial required fact family:

```text
ip_version = 4

observed_ttl

ip_option_length_bytes

ip_id_zero

ip_df

ip_reserved_flag

ip_ecn_bits

tcp_header_length_bytes

tcp_window

tcp_sequence_zero

tcp_ack_number_nonzero

tcp_urg_pointer_nonzero

tcp_fin

tcp_rst

tcp_push

tcp_urg

tcp_ece

tcp_cwr

tcp_payload_present

ordered tcp_option_records
```

`tcp_header_length_bytes` remains because exact supported p0f MTU/window semantics require reconstructable header length.

Exact IP ID and exact TCP timestamp values are not durable.

---

# 62. tcp_option_records exact V2 contract

`tcp_option_records` is one ordered list and the ONLY durable option source of truth.

Every record has:

```text
record_type

kind

declared_length

available_value_length

structure_state
```

`record_type` enum:

```text
eol
nop
mss
window_scale
sack_permitted
timestamp
unknown
```

`kind` is integer `0..255`.

`declared_length`:

```text
null for EOL/NOP

otherwise exact observed length byte
when physically present

null when a length byte itself is unavailable
inside an otherwise bounded malformed option condition
```

`available_value_length`:

```text
integer >= 0

number of option-value bytes physically available
inside the declared TCP option area for this record
```

`structure_state` enum:

```text
well_formed

malformed_but_observable
```

Validator invariants make state deterministic from the record's structural facts and record type; no arbitrary Coder assignment.

---

# 63. EOL record

```text
record_type = "eol"
kind = 0
declared_length = null
available_value_length = 0
structure_state = "well_formed"

eol_padding_length = exact count of bytes remaining
in TCP option area after this EOL byte

eol_padding_nonzero = boolean
```

Non-zero trailing bytes after EOL are retained through `eol_padding_nonzero` and allow transient p0f `opt+` derivation.

No raw trailing bytes are durable.

No further option records are parsed after EOL.

---

# 64. NOP record

```text
record_type = "nop"
kind = 1
declared_length = null
available_value_length = 0
structure_state = "well_formed"
```

Each NOP remains a separate ordered record.

---

# 65. MSS record

```text
record_type = "mss"
kind = 2

declared_length = observed length byte when available

available_value_length = physically available value bytes

structure_state =
well_formed only when declared_length = 4
and exactly required structural bytes are available;
otherwise malformed_but_observable

mss =
unsigned 16-bit value when both MSS value bytes
are physically available;
otherwise null
```

The record survives malformed declared length when the packet/header itself is complete.

---

# 66. Window Scale record

```text
record_type = "window_scale"
kind = 3

declared_length = observed length byte when available

available_value_length = physically available value bytes

structure_state =
well_formed only when declared_length = 3
and the value byte is available;
otherwise malformed_but_observable

window_scale_raw =
unsigned 8-bit value when value byte available;
otherwise null
```

Values:

```text
>14
```

are preserved exactly as `window_scale_raw` and are NOT rejected.

Transient p0f adapter may derive `exws`.

---

# 67. SACK Permitted record

```text
record_type = "sack_permitted"
kind = 4

declared_length = observed length byte when available

available_value_length = physically available value bytes

structure_state =
well_formed only when declared_length = 2;
otherwise malformed_but_observable
```

No raw value bytes retained.

---

# 68. Timestamp record

```text
record_type = "timestamp"
kind = 8

declared_length = observed length byte when available

available_value_length = physically available value bytes

structure_state =
well_formed only when declared_length = 10
and all eight value bytes are physically available;
otherwise malformed_but_observable

timestamp_value_zero =
true/false when first four timestamp bytes available,
otherwise null

timestamp_echo_nonzero =
true/false when second four timestamp bytes available,
otherwise null
```

Exact TSval/TSecr integers are NOT durable.

---

# 69. Unknown option record

For kind values other than known EOL/NOP/MSS/WS/SACK-permitted/Timestamp:

```text
record_type = "unknown"

kind = exact observed option kind

declared_length = observed length byte if present

available_value_length =
physically available value bytes

structure_state =
well_formed when a structurally valid length >=2
fits in remaining option area;
otherwise malformed_but_observable
```

No raw value bytes.

Unknown options remain order-preserving and reconstructable enough for supported p0f option-kind / malformed semantics.

---

# 70. Malformed option traversal

For non-EOL/NOP options:

```text
missing length byte

declared length < 2

declared length extends beyond remaining option area

known option declared length mismatch
```

inside an otherwise complete TCP header are:

```text
malformed_but_observable
```

not automatic event rejection.

Parser records the maximal bounded facts physically available.

Traversal behavior for malformed length is pinned by K2A oracle fixtures so implementation cannot invent a different continuation policy.

Actual packet/header truncation remains event rejection.

---

# 71. tcp_syn/2 privacy/minimization rule

Every durable field must prove:

```text
required by admitted adapter

bounded representation

no less-sensitive equivalent
```

Fields failing this test are removed.

Exact:

```text
TCP timestamp values
timestamp echo values
IPv4 ID
```

remain forbidden without a future reviewed need.

---

# 72. K2A / K2B split

```text
K2A =
p0f semantics/conformance foundation

K2B =
production TCP knowledge corpus
```

Canonical transient adapter boundary:

```text
tcp_syn/2
→ p0f_runtime_ipv4_request_v1
```

The adapter may derive transient:

```text
p0f option layout

p0f quirks

p0f payload class

TTL/distance representation

window/MSS/MTU matcher inputs
```

None of those external-dialect values are written back into durable Task-02 evidence.

K2A owns:

```text
runtime serializer grammar

matcher grammar

MSS/MTU/window expressions

TTL/distance

option semantics

quirks

fuzzy behavior

specific/generic precedence

real-p0f oracle corpus
```

K2A proves matcher correctness.

K2B decides which reference signatures production may use.

p0f oracle does NOT automatically become modern production truth.

---

# 73. TTL/RSPAN physical proof

Current mirror topology does not self-prove hop distance.

Foundation proof records:

```text
actual running SPAN/RSPAN config

source VLAN/interface

direction

controlled SYN identity

sender TTL

sensor TTL
```

Topology/capture change invalidates the proof.

---

# 74. Portal Client Hints and Critical-CH

`portal_headers/2` remains candidate-only until Foundation proof.

Initial candidate high-entropy fields are exactly:

```text
Sec-CH-UA-Model

Sec-CH-UA-Platform-Version

Sec-CH-UA-Form-Factors
```

Each candidate is admitted independently; failure/non-support of one does not automatically admit or reject another.

Permanent:

```text
Critical-CH = FORBIDDEN
```

No fingerprint enrichment may force browser retry.

`Accept-CH` is bounded optional enrichment only.

Missing hints remain normal.

---

# 75. Accept-CH lifecycle

Controlled proof covers:

```text
eligible secure response

Accept-CH request

subsequent eligible same-origin request

normalization

end of collection lifecycle
```

Preferred teardown where supported:

```text
Clear-Site-Data: "clientHints"
```

or another accepted standards-compliant bounded mechanism.

Forbidden:

```text
continuous high-entropy hint request

raw CH persistence

raw CH logging

JS fingerprint fallback

Authorization dependency
```

If bounded lifecycle cannot be proven for a client class, high-entropy enrichment is not admitted for that class.

---

# 76. Portal idle heartbeat

Before Foundation Admission, enabled portal evidence must produce visitor-independent liveness heartbeat.

Heartbeat contains no:

```text
MAC
IP
UA
Client Hints
```

It creates no browser traffic and does not affect Authorization.

Failure semantics use SourceHealthPolicy.

---

# 77. External artifact canonical import

Runtime classifier does NOT directly read:

```text
Fingerbank SQLite schema

IEEE CSV/raw vendor layout

raw p0f.fp text

future external JA4 vendor format
```

Pipeline:

```text
external artifact

→ quarantine/read-only inspection

→ SourceGovernanceRecord

→ KnowledgeProvenanceManifest(kind=external)

→ validated source-specific importer

→ canonical knowledge records

→ immutable KnowledgeBundle

→ runtime
```

---

# 78. SourceGovernanceRecord

Every external knowledge source has immutable `SourceGovernanceRecord` containing at least:

```text
source_name

source provenance

license_identifier

license/source reference

license_text_sha256 if license text is locally retained/bundled

local_storage_status

modification_import_status

redistribution_status

attribution_requirement

commercial_use_status

review_basis

review_registration_id

unresolved_restrictions
```

Unknown material legal status:

```text
SOURCE NOT ADMITTED
```

Importer normalization does not erase source obligations.

This applies to at least:

```text
Fingerbank artifact
p0f corpus
IEEE source
future external JA4 knowledge
```

---

# 79. KnowledgeProvenanceManifest — external/internal union

Every canonical knowledge record references:

```text
knowledge_provenance_id
```

`KnowledgeProvenanceManifest.provenance_kind` is:

```text
external
internal
```

## external

Payload references:

```text
source artifact SHA256

SourceGovernanceRecord ID/digest

retrieved_at_utc

source/provider version metadata

KnowledgeFreshnessPolicy ID/digest

importer identity/version
```

## internal

Used for deterministic CaptivPortal rule sets such as K3.

Payload references:

```text
rule-set artifact ID/digest

repository commit/tree or source artifact identity

input schema compatibility

taxonomy compatibility

review registration

rule-set version
```

Internal provenance does NOT fabricate:

```text
retrieved_at aging
external license status
external freshness
```

unless an actually external component is present.

---

# 80. Knowledge reference contract

Every semantic knowledge claim references:

```text
KnowledgeBundle ID/digest

canonical_knowledge_record_id

knowledge_provenance_id/digest

rule/source record identity
```

No fake external `source_manifest_id` is required for internal K3.

---

# 81. KnowledgeFreshnessPolicy

Applies to changing EXTERNAL knowledge sources.

Freshness states:

```text
fresh
stale
expired
```

Orthogonal source character:

```text
current
legacy
```

Exact thresholds/conditions are proven per source from:

```text
actual source update behavior

artifact metadata

provider docs/cadence where available

operational refresh capability

failure tolerance

Owner policy
```

No architecture-invented age.

Internal deterministic K3 rules do not age via external freshness.

---

# 82. KnowledgeBundle

Immutable KnowledgeBundle semantic payload includes:

```text
bundle_schema_version

classification_taxonomy ID/digest

alias_mapping ID/digest

ordered KnowledgeProvenanceManifest IDs/digests

ordered SourceGovernanceRecord IDs/digests for external sources

ordered KnowledgeFreshnessPolicy IDs/digests for external sources

ordered canonical knowledge records
```

Canonical knowledge record ordering:

```text
knowledge_record_type
canonical_record_id
```

Bundle identity uses ArtifactCanonicalJsonV1.

No vendor schema at runtime.

---

# 83. KnowledgeBundle activation/pinning

Lifecycle:

```text
build immutable candidate

validate

run Foundation gates

accept

atomically switch active pointer
```

In-flight RequestAssembly pins:

```text
knowledge_bundle_id
content_sha256
```

once.

Refresh cannot mutate in-flight request.

Rollback activates a previously accepted immutable bundle.

---

# 84. Knowledge expiry runtime behavior

At explicit live/replay `knowledge_evaluation_at_utc`:

```text
expired external source
→ emits no new claims
→ explanation = knowledge_source_expired
```

Classifier continues with remaining admitted sources.

KnowledgeBundle bytes remain immutable.

Expiry is claim-admissibility behavior, not service crash.

---

# 85. Mandatory knowledge slots and symmetric failure

Foundation requires concrete usable:

```text
K1 DHCP knowledge

K2B TCP knowledge

K3 portal rules

K4 IEEE assignment knowledge
```

For ANY mandatory slot:

```text
candidate source/rule set FAIL
→ DO NOT weaken contract
→ DO NOT add empty placeholder
→ select another concrete source/rule set satisfying same contract
→ Foundation Admission remains BLOCKED until satisfied
```

No asymmetry.

JA4 knowledge is optional and excluded from this mandatory set.

---

# 86. K1 deterministic ambiguity-preserving contract

K1 consumes DHCP-origin normalized attributes only.

Pipeline:

```text
DHCP evidence

→ all deterministic compatible K1 records

→ all linked candidate taxonomy records

→ CandidateSet

→ per-dimension projection
```

Forbidden:

```text
first SQL row

best row by undocumented order

most popular device

hidden Fingerbank scoring recreation

single arbitrary candidate

MAC/OUI enrichment inside DHCP origin
```

Example:

```text
A = Android / smartphone
B = Android / tablet

platform_family =
android / resolved

device_class =
ambiguous at OriginDimensionAssessment
```

Candidate enumeration is complete and row-order independent.

No-match is an explicit empty CandidateSet.

---

# 87. K1 provenance purity

Runtime DHCP-only input is necessary but not sufficient.

Every fusion-eligible imported K1 mapping must also be attributable upstream solely to admitted DHCP attributes.

If upstream provenance:

```text
uses DHCP + MAC/OUI/other origin
OR
cannot establish DHCP-only derivation
```

then:

```text
mapping is NOT fusion-eligible as DHCP knowledge
```

It may remain research/explainability data.

---

# 88. K1 failure alternative

Fingerbank static data is one candidate, not a required brand dependency.

If Fingerbank cannot satisfy:

```text
legal admission

provenance purity

deterministic complete candidate enumeration

ambiguity preservation
```

then:

```text
Fingerbank K1 = FAIL
```

Foundation must admit another concrete K1 source satisfying the same contract.

No hand-written guesses/placeholders to make the gate green.

---

# 89. K2B legacy claim ceiling

Every K2B admission output records:

```text
source_character

freshness policy

maximum claim_strength by dimension

taxonomy limitations

known age/scope caveats
```

A source marked `legacy` does NOT automatically become `strong` because its signature match is exact.

No legacy source is fusion-admitted without an explicit claim-strength ceiling.

Absent ceiling:

```text
source not admitted
```

---

# 90. K3 internal portal semantic rules

K3 is an INTERNAL deterministic rule set inside KnowledgeBundle.

K3 consumes NORMALIZED portal evidence only.

Forbidden inside Task-04 K3:

```text
raw User-Agent parsing

raw Client Hint parsing

raw HTTP header parsing
```

Current normalized portal evidence may include:

```text
platform_family

mobile_boolean

browser_runtime_family

webview_or_captive_context

model_family

os_major

platform_source

mobile_source

runtime_source

context_source

model_source

os_major_source

presence booleans
```

K3 uses normalized provenance fields when assigning:

```text
claim_derivation
claim_strength
```

Permanent semantic guards:

```text
platform_family=android
may support Android platform claim under admitted rule

mobile_boolean=true
DOES NOT automatically mean smartphone

browser runtime
DOES NOT automatically mean device_class

webview/captive context
DOES NOT automatically mean device_class

model_family normalized value
resolves model only through an admitted canonical model rule/alias
```

---

# 91. K3 rule contract

Immutable `K3PortalRuleSet` contains:

```text
rule_set_version

ordered canonical rule IDs

supported portal schema versions

input provenance predicates

taxonomy target

claim_derivation

maximum/base claim_strength

rule explanation code

ordered test vectors
```

Rules are ordered by canonical rule ID for artifact identity.

If multiple K3 rules yield incompatible same-strength concrete claims inside portal origin, same-origin conflict semantics apply.

K3 is internal provenance and has no fabricated external freshness/license requirement.

---

# 92. K4 IEEE semantics

Imports:

```text
MA-L
MA-M
MA-S
```

uses longest-prefix match.

Locally administered MAC:

```text
IEEE assignment lookup = NOT ELIGIBLE
```

Raw semantic:

```text
mac_assignment_org
```

not device manufacturer.

Manufacturer claim requires explicit canonical mapping:

```text
assignment_org_id
→ manufacturer_id
```

with reviewed knowledge provenance.

---

# 93. JA4 safety contract

Permanent:

```text
JA4 observed
!= platform

JA4 observed
!= device_class

JA4 observed
!= manufacturer

JA4 observed
!= model
```

Default V1:

```text
no admitted JA4 reference knowledge
→ TLS OriginAssessment emits NO semantic classification claim

no admitted JA4 reference knowledge
→ QUIC OriginAssessment emits NO semantic classification claim
```

Forbidden without accepted versioned knowledge:

```text
Apple-like JA4

Android-like JA4

frequently observed JA4

local frequency heuristic
```

TLS/QUIC normalized evidence may still be collected/audited when it produces no claim.

JA4 knowledge is OPTIONAL and NOT a Foundation Admission blocker.

---

# 94. Fingerbank Cloud V1 status

```text
Fingerbank Cloud =
OUT OF TASK-04 V1 IMPLEMENTATION SCOPE

DEFAULT OFF

NO PRODUCTION CLIENT DATA SUBMISSION
```

Current Foundation research uses static/local artifacts only.

Future Cloud integration requires:

```text
separate architecture decision

Owner explicit opt-in

privacy review

origin-attribution review
```

Permanent:

```text
never Authorization dependency

never synchronous classifier dependency

never required startup dependency
```

Coder MUST NOT silently add Cloud integration to Task-04 V1.

---

# 95. classification_taxonomy_v1

Dimensions:

```text
platform_family

device_class

manufacturer_family

model_family
```

Platform in-scope values:

```text
android
ios
windows
macos
chromeos
linux
```

V1 `ios` means:

```text
Apple mobile OS family including iOS + iPadOS
```

iPhone/iPad differentiation belongs to device_class.

Device class in-scope:

```text
smartphone
tablet
laptop
```

No broad taxonomy is squeezed into a narrower class.

---

# 96. recognized_out_of_scope applicability

Final `recognized_out_of_scope` is valid only for:

```text
platform_family

device_class
```

Examples include recognized:

```text
unsupported platform family

TV

printer

camera

watch/wearable

desktop workstation

IoT class
```

Manufacturer/model do NOT use final out-of-scope status.

Unmapped manufacturer/model taxon:

```text
insufficient_evidence
+
unmapped_* explanation
```

---

# 97. Canonical manufacturer/model identity

Manufacturer:

```text
canonical manufacturer_id

display label ref

explicit aliases
```

Model:

```text
canonical model_family_id

display label ref

explicit aliases
```

String equality/similarity is not identity.

No auto alias by:

```text
case
punctuation
prefix stripping
substring
edit distance
marketing-name similarity
```

---

# 98. claim_derivation vs claim_strength

Orthogonal concepts.

`claim_derivation`:

```text
declared

deterministic_mapping

fingerprint_match

registry_mapping
```

`claim_strength`:

```text
strong

supporting
```

Fusion compares strength.

Derivation is provenance/explainability.

Client-declared claim is not automatically stronger than a deterministic mapping.

Base/capped strength is frozen by admitted rule/knowledge/policy.

---

# 99. Origin groups and purity

Origins exactly:

```text
dhcp

portal

tcp

tls

quic

mac_registry
```

Purity:

```text
dhcp → DHCP evidence only

portal → portal normalized evidence only

tcp → tcp_syn evidence only

tls → TLS normalized evidence only

quic → QUIC normalized evidence only

mac_registry → observed MAC + local registry knowledge only
```

`mac_registry` is outside Task-01 binding/source-health.

Multi-origin external answers never become an extra independent vote.

---

# 100. Semantic dedup

Same-origin semantic repetitions collapse.

```text
100 identical rows != 100 votes

V1/V2 semantically equivalent observation != 2 votes
```

EvidenceAdapterContractSet defines projection used for dedup.

Counts remain explainability only.


# 101. OriginDimensionAssessment exact contract

Each OriginAssessment contains one OriginDimensionAssessment per classification dimension.

Fields:

```text
dimension_name

internal_state

selected_canonical_value_id or null

selected_out_of_scope_taxon_ref or null

effective_claim_strength or null

ordered claim_derivations

ordered candidate_set

conflict_strength or null

ordered same_origin_contradiction_records

ordered broad_unresolved_taxon_refs

ordered knowledge_refs

ordered evidence_refs

ordered explanation_codes
```

Internal state enum exactly:

```text
resolved

recognized_out_of_scope

ambiguous

conflicting

no_claim

not_evaluable
```

`ambiguous` is internal only.

`resolved_with_contradiction` is NOT a separate state:

```text
internal_state = resolved
same_origin_contradiction_records != []
```

Candidate set entries contain:

```text
candidate_value_id or out_of_scope_taxon_ref

claim_strength

claim_derivation

knowledge_refs

evidence_refs
```

Candidate ordering is canonical by:

```text
canonical value/taxon identifier
claim_strength
claim_derivation
```

---

# 102. Same-origin conflict strength

When same-origin incompatible concrete claims exist:

```text
conflict_strength =
strong
or
supporting
```

Rules:

## incompatible strong claims

```text
internal_state = conflicting

conflict_strength = strong
```

## no strong claim, incompatible supporting claims

```text
internal_state = conflicting

conflict_strength = supporting
```

## clean strong claim + incompatible supporting claim

```text
internal_state = resolved

effective_claim_strength = strong

conflict_strength = supporting

contradiction record retained
```

No blanket "origin conflict always decisive" rule.

Cross-origin fusion consumes actual conflict strength.

---

# 103. Same-origin strength matrix

```text
strong + strong same
→ resolved strong

strong + strong incompatible
→ conflicting / conflict_strength strong

strong + supporting same
→ resolved strong

strong + supporting incompatible
→ resolved strong
→ supporting contradiction retained

supporting + supporting same
→ resolved supporting

supporting + supporting incompatible
→ conflicting / conflict_strength supporting
```

No:

```text
row majority
latest wins
source-name priority
claim_derivation priority
```

---

# 104. K1 ambiguity vs conflict

A CandidateSet containing multiple compatible candidate taxonomy rows does NOT automatically mean conflict.

If all candidates agree on one dimension:

```text
dimension may resolve
```

If candidates differ but represent alternative compatible possibilities without contradictory observed claims:

```text
internal_state = ambiguous
```

Example:

```text
Candidate A = Android / smartphone
Candidate B = Android / tablet

platform =
resolved android

device_class =
ambiguous
```

This distinction is required to preserve K1 ambiguity rather than turning database multiplicity into false conflict.

---

# 105. Cross-origin fusion with conflict strength

For each dimension fusion evaluates clean claims and conflict records by `claim_strength`.

Rules:

## any strong internal conflict

```text
final =
conflicting_evidence
```

A clean strong claim from another origin does NOT erase a strong internal conflict.

## clean strong claims from independent origins disagree

```text
conflicting_evidence
```

## clean strong outcome + only supporting incompatible clean claims

```text
strong outcome retained

contradictions recorded

support_level capped at medium
```

## clean strong outcome + supporting internal conflict in another origin

```text
strong outcome retained

supporting conflict recorded as contradiction

support_level capped at medium
```

## no strong clean outcome + supporting internal conflict

```text
conflicting_evidence
```

## supporting clean claims disagree

```text
conflicting_evidence
```

## supporting clean claims agree and no conflicts

```text
select outcome
```

No source-name or derivation-kind priority.

---

# 106. Broad/unresolved information

A broad source taxon that cannot choose one canonical value:

```text
is explanatory information
not a concrete claim
```

If broad taxon is compatible with selected value:

```text
no contradiction
```

If admitted semantics prove it disjoint from the target in-scope set:

```text
it may become recognized_out_of_scope
only for platform/device_class
```

---

# 107. Support calculation — contradiction completeness

`support_level`:

```text
none
low
medium
high
```

High requires ALL:

```text
>=2 independent origin groups agree

>=2 contributing origin claims are strong

NO incompatible claim of any strength

NO same-origin lower-strength contradiction

NO supporting internal conflict

NO cross-origin contradiction
```

Therefore HIGH is forbidden whenever any incompatible supporting claim is recorded anywhere in the evaluated dimension.

Medium:

```text
>=1 strong selected claim

no decisive strong conflict
```

Any lower-strength contradiction or supporting conflict caps at medium.

Low:

```text
selected outcome supported only by supporting claims

all selectable supporting claims agree

no supporting conflict
```

None:

```text
unknown

insufficient_evidence

conflicting_evidence
```

`recognized_out_of_scope` may be low/medium/high using same support rules.

Support is advisory corroboration, not probability or identity proof.

---

# 108. Final DimensionResult contract

Each dimension produces:

```text
dimension_name

canonical_value_id or null

display_label_ref or null

status

support_level

ordered supporting_origin_groups

ordered contradicting_origin_groups

ordered not_evaluable_origin_groups

ordered out_of_scope_taxon_refs

ordered explanation_codes

ordered knowledge_refs
```

Final status enum:

```text
resolved

recognized_out_of_scope

unknown

insufficient_evidence

conflicting_evidence
```

No final `ambiguous`.

---

# 109. Final dimension semantics and precedence

## conflicting_evidence

Decisive incompatible concrete claims/conflicts at applicable strength prevent safe selection.

## resolved

Exactly one in-scope canonical value is selectable.

Lower-strength contradiction may remain but is explicitly recorded and support capped.

## recognized_out_of_scope

Platform/device_class only.

One out-of-scope taxon is safely selectable.

## insufficient_evidence

Used when:

```text
ambiguous semantic information

unsupported classification schema without alternative resolution

only degraded/unusable evidence

unmapped manufacturer/model

broad unresolved taxon

coverage/evidence insufficiency with no resolving claim
```

## unknown

A supported/usable evidence path exists but admitted usable knowledge emits no semantic information, including when relevant knowledge is expired.

Precedence:

```text
1. decisive conflict
→ conflicting_evidence

2. selectable in-scope outcome
→ resolved

3. selectable out-of-scope outcome where allowed
→ recognized_out_of_scope

4. semantic information exists but cannot resolve
→ insufficient_evidence

5. supported evidence exists but no usable semantic knowledge claim
→ unknown

6. no adequate supported evidence path
→ insufficient_evidence
```

---

# 110. Global classification status

Global enum:

```text
classified

partial

recognized_out_of_scope

unknown

insufficient_evidence

conflicting_evidence
```

Exact derivation:

```text
1. ANY dimension conflicting_evidence
→ global conflicting_evidence

2. ALL four dimensions resolved
→ global classified

3. ANY dimension resolved
→ global partial

4. otherwise ANY platform/device_class recognized_out_of_scope
→ global recognized_out_of_scope

5. otherwise ANY dimension insufficient_evidence
→ global insufficient_evidence

6. otherwise
→ global unknown
```

No UI/service reinterpretation.

---

# 111. ClassificationPolicy — pure semantics only

`ClassificationPolicy` contains ONLY semantics used by the pure classifier.

Payload:

```text
policy_schema_version

ClassificationTaxonomy ID/digest

AliasMapping ID/digest

EvidenceAdapterContractSet ID/digest

claim_derivation enum/semantics

claim_strength enum/semantics

same-origin ambiguity/conflict rules

same-origin conflict-strength rules

cross-origin fusion matrix

support_level rules

DimensionResult rules

recognized_out_of_scope applicability

global status derivation

knowledge-expiry claim reaction semantics
```

It does NOT contain:

```text
ClassificationRetentionPolicy

ProductValidationPolicy

SnapshotExecutionPolicy

SnapshotContentPolicy

SourceHealthPolicy
```

Those belong to different layers.

`SourceEvaluability` is already an explicit classifier input.

`EvidenceSnapshotContent` already reflects accepted snapshot construction.

No cross-layer policy coupling.

---

# 112. Live knowledge evaluation time ownership

Pure core does not read wall clock.

For LIVE classification:

```text
Task-04 RequestAssembly service
captures trusted central
knowledge_evaluation_at_utc
```

Caller cannot override/backdate it.

The service captures it while pinning:

```text
KnowledgeBundle

ClassificationPolicy

ClassifierArtifactManifest
```

Validation:

For every external source used for possible claims:

```text
knowledge_evaluation_at_utc
MUST be >= source retrieved_at_utc
```

If negative source age would occur:

```text
REQUEST ASSEMBLY FAILS CLOSED

NO ClassificationResult
```

For REPLAY:

```text
use exact stored historical knowledge_evaluation_at_utc
```

---

# 113. RequestAssembly pin-once boundary

LIVE RequestAssembly proceeds once:

```text
1. obtain completed EvidenceSnapshotContent + transient Materialization

2. obtain SourceEvaluability for that snapshot

3. atomically/predictably read active accepted pointers for:
   KnowledgeBundle
   ClassificationPolicy
   ClassifierArtifactManifest

4. pin exact IDs/digests

5. capture trusted knowledge_evaluation_at_utc

6. validate source ages/policy compatibility

7. create ClassificationRequestManifest

8. invoke pure core with the pinned objects
```

After step 4:

```text
NO active pointer is re-read
for that request
```

Concurrent bundle/policy/classifier activation does not alter the in-flight request.

Replay uses retained exact IDs/digests/time.

---

# 114. Pure classification core

Pure deterministic function:

```text
EvidenceSnapshotContent
+
EvidenceSnapshotMaterialization
+
SourceEvaluability
+
KnowledgeBundle
+
ClassificationPolicy
+
knowledge_evaluation_at_utc
+
ClassifierArtifactManifest identity
→
OriginAssessments
→
DimensionResults
→
semantic ClassificationResult
```

Pure core has:

```text
NO DB access

NO network access

NO filesystem discovery

NO current-clock reads

NO mutable config reads

NO vendor-schema reads

NO telemetry side effects

NO persistence
```

Materialization integrity has already been verified against EvidenceSnapshotContent payload hashes.

---

# 115. ClassifierArtifactManifest

Immutable payload minimum:

```text
repository_commit_sha

repository_tree_sha

classification_engine_semver

ArtifactCanonicalJsonV1 implementation/version

EvidenceCanonicalJsonV1 compatibility identity

pure_core_contract_version

classification_result_schema_version

snapshot_contract_version

exact implementation identities for:
    dhcp/1 adapter
    tcp_syn/1 adapter/non-fusion handler
    tcp_syn/2 adapter
    tls_client/1 adapter
    quic_client/1 adapter
    portal_headers/1 adapter
    portal_headers/2 adapter if admitted

K2A matcher implementation version

build/package digest where repository tree alone
does not uniquely identify executed bytes
```

Changing evidence-version interpretation changes ClassifierArtifactManifest identity.

---

# 116. ClassificationRequestManifest

Immutable payload:

```text
EvidenceSnapshotContent ID/digest

SourceEvaluability ID/digest

KnowledgeBundle ID/digest

ClassificationPolicy ID/digest

ClassifierArtifactManifest ID/digest

knowledge_evaluation_at_utc
```

Its content digest is the exact:

```text
classification_request_digest
```

SnapshotContentPolicy/SourceHealthPolicy are not separately re-inserted here because their semantic outputs are already frozen into EvidenceSnapshotContent/SourceEvaluability.

No retention/product-validation policy affects request identity.

---

# 117. Semantic ClassificationResult

Immutable payload minimum:

```text
classification_request_digest

classification_policy_id/digest

knowledge_bundle_id/digest

classifier_artifact_id/digest

evidence_snapshot_content_id/digest

SourceEvaluability id/digest

platform_result

device_class_result

manufacturer_result

model_result

global classification_status

ordered OriginAssessment IDs/digests
```

No current-clock timestamp in pure result.

---

# 118. Classification persistence record

Service persistence stores separately:

```text
classification_id

site_id

observed_mac

classified_at_utc

ClassificationRequestManifest ID/digest

ClassificationResult ID/digest

SnapshotRecord ID/digest

ClassificationRetentionPolicy ID/digest
```

`SnapshotRecord` MUST remain retrievable while referenced.

No dangling audit IDs.

---

# 119. ClassificationRetentionPolicy

Separate immutable policy.

Controls:

```text
classification-history retention duration

SnapshotRecord co-retention

request/result/evaluability/origin co-retention

privacy/storage basis

expiry

reference-aware GC
```

Exact first production retention:

```text
REQUIRED / UNRESOLVED
```

until Owner freezes it before Task-04 persistence implementation.

No invented 30-day value.

Changing this policy does NOT change pure classification semantics/request digest.

---

# 120. Audit retention and replay

While a classification is retained, retain/retrieve by immutable reference:

```text
SnapshotRecord

EvidenceSnapshotContent

SourceEvaluability

OriginAssessments

ClassificationRequestManifest

ClassificationResult

KnowledgeBundle

ClassificationPolicy

EvidenceAdapterContractSet

ClassifierArtifactManifest

FoundationAdmissionManifest

relevant BindingTimeline/BindingClockPolicy

knowledge provenance/governance/freshness artifacts
```

Digest without content is not replay.

## Level A

Task-01 evidence → snapshot/materialization/evaluability/origins.

Only possible while source evidence/health/generation remains reconstructable.

## Level B

Retained:

```text
SourceEvaluability
OriginAssessments
ClassificationPolicy
KnowledgeBundle
ClassifierArtifactManifest
knowledge_evaluation_at
ClassificationRequestManifest
```

reproduces the semantic ClassificationResult for the full classification retention period.

No raw packets/UA/CH are retained to extend Level A.

---

# 121. No automatic learning / knowledge mutation

Permanent:

```text
classification output
NEVER automatically changes:

KnowledgeBundle

K3 rules

aliases

taxonomy

claim strengths

ClassificationPolicy
```

Controlled validation is:

```text
validation

regression

false-positive detection

support-policy validation
```

not training.

Any knowledge/policy correction:

```text
candidate FAIL

review correction

new immutable artifact version

re-run required gates
```

No online learning.

---

# 122. ProductValidationPolicy

Validation evaluates every dimension for which controlled ground truth is known.

Ground truth MUST be recorded BEFORE classifier result is viewed.

Validation record contains:

```text
ground_truth_recorded_at_utc

ground truth values

request digest

result digest

comparison

candidate classifier identity
```

No result-driven relabeling.

Safety:

```text
ANY incorrect resolved known-ground-truth dimension
→ FAIL

ANY false recognized_out_of_scope
for known in-scope platform/device_class
→ FAIL
```

Minimum V1 utility:

```text
Owner Android smartphone:
platform_family = android
resolved
support >= medium

Owner Windows laptop:
platform_family = windows
resolved
support >= medium

Across the two:
at least one correct device_class
resolved
support >= medium
```

Manufacturer/model may remain unresolved if evidence does not justify them.

Always-unknown engine FAILS utility.

---

# 123. GateResultManifest

Every Foundation and Task-04 acceptance gate PASS/FAIL is machine/audit-identifiable.

`GateResultManifest` semantic payload minimum:

```text
gate_id

gate_contract_version

status =
PASS | FAIL

candidate_repository_commit_sha

candidate_repository_tree_sha

ordered input_artifact_refs:
    artifact_id
    content_sha256

ordered output_artifact_refs:
    artifact_id
    content_sha256

ordered retained_evidence_refs:
    evidence_label
    file_sha256
    media_type
    optional path/reference

proof_execution_identity:
    execution_id = canonical lowercase UUIDv4
    executor_kind
    repository_commit_sha
    repository_tree_sha
    procedure_or_test_suite_id
    environment_identity
    execution_artifact_sha256 where applicable

owner_decision_registration_id or null

review_registration_ids
```

Ordering:

```text
input/output refs by artifact_id

evidence refs by evidence_label then SHA

review registrations lexicographically
```

Gate status cannot exist only in chat prose.

Human reviewer/Owner metadata is represented through ArtifactRegistration/decision registration references.

---

# 124. FoundationAdmissionManifest

Foundation Admission is a real immutable ArtifactContent.

Semantic payload minimum:

```text
foundation_manifest_version

architecture_contract_reference_id/digest

architecture_document_sha256

foundation_repository_commit_sha

foundation_repository_tree_sha

classification_foundation_valid_from_utc

Task-01 database schema contract version

Task-01 watermark/generation contract version

ordered mandatory_pre_admission_foundation_gate_ids
(excludes F-ADMIT itself)

ordered pre_admission GateResultManifest IDs/digests
(excludes the F-ADMIT GateResultManifest that outputs this manifest)

accepted EvidenceSchemaRegistryContract ID/digest

accepted EvidenceAdapterContractSet ID/digest

accepted KnowledgeBundle ID/digest

accepted EvidenceSourceBindingTimeline ID/digest

accepted BindingClockPolicy ID/digest

accepted SourceHealthPolicy ID/digest

accepted SnapshotContentPolicy ID/digest

accepted SnapshotExecutionPolicy ID/digest

accepted ClassificationPolicy ID/digest

accepted ClassificationRetentionPolicy ID/digest

accepted ProductValidationPolicy ID/digest

accepted KnowledgeFreshnessPolicy IDs/digests

accepted SourceGovernanceRecord IDs/digests

accepted KnowledgeProvenanceManifest IDs/digests

accepted K2AConformancePackage reference/digest

accepted TTL capture proof reference/digest

optional portal_headers/2 admission status/artifact
```

Task-04 decomposition binds to this exact FoundationAdmissionManifest.

No vague:

```text
foundation passed
```

state.

---

# 125. Task04AcceptanceManifest

Final Task-04 implementation acceptance produces immutable:

```text
Task04AcceptanceManifest
```

Payload minimum:

```text
FoundationAdmissionManifest ID/digest

Task-04 candidate repository commit SHA

Task-04 candidate repository tree SHA

ClassifierArtifactManifest ID/digest

ordered mandatory pre_acceptance Task-04 gate IDs
(T-01 through T-09; excludes T-ACCEPT itself)

ordered pre_acceptance Task-04 GateResultManifest IDs/digests
(excludes the T-ACCEPT GateResultManifest that outputs this manifest)

accepted ClassificationResult schema version

accepted persistence/audit contract version

accepted product-validation proof ref/digest
```

It does NOT itself authorize production deployment.

Owner deployment/activation remains a separate project decision.


# 126. Foundation gate lifecycle

Foundation gates execute only AFTER R7 becomes Architecture Contract FINAL and Owner separately authorizes the bounded PRE-TASK work.

They authorize Task-04 decomposition.

Every gate output is represented by a GateResultManifest.

---

# 127. FOUNDATION F-A1 — Task-01 v1→v2 migration / watermark schema

**INPUT**

```text
current Task-01 schema v1 DB fixture

watermark-capable schema v2 candidate

migration procedure

pre-migration backup procedure
```

**PROOF METHOD**

Execute migration on representative production-copy fixtures including retained evidence/source-health rows.

**PASS**

```text
writer stopped

pre-migration SHA recorded

headroom validated

all IDs/payloads preserved

v2 generation UUID minted

bootstrap sequences assigned

allocator initialized

constraints/indexes valid

PRAGMA user_version advanced

quick_check PASS

integrity_check PASS

writer starts only after validation
```

**FAIL**

```text
partial active migration

lost/rewritten normalized payload

lost evidence/health ID

invalid sequence/generation

old writer permitted during migration
```

**RETAINED EVIDENCE**

```text
pre/post schema dumps

pre/post row-count/identity comparison

DB file digests

migration log

PRAGMA reports
```

**CANONICAL OUTPUT ARTIFACT**

```text
Task01SchemaMigrationContract

Task01WatermarkReadContract
```

**OWNER DECISION**

Owner approves production migration/rollback risk after TechLead review.

**WHAT NEXT CONSUMES IT**

F-A2, F-A3, F-A4, FoundationAdmissionManifest.

---

# 128. FOUNDATION F-A2 — Sequence / duplicate / generation recovery

**INPUT**

```text
F-A1 candidate

duplicate fixtures

allocator-exhaustion fixture

controlled older-backup restore fixture
```

**PROOF METHOD**

Exercise:

```text
normal evidence insert

normal health insert

cross-table sequence ordering

idempotent duplicate

conflicting duplicate

sequence gap

cleanup DELETE

near-exhaustion allocator

controlled restore/rebaseline
```

**PASS**

```text
single evidence+health sequence domain

positive signed 64-bit row domain

empty watermark = 0

idempotent duplicate consumes no sequence

conflicting duplicate rolls back

DELETE does not advance sequence

gaps semantically meaningless

exhaustion fails closed

controlled restore mints new generation before writer starts
```

**FAIL**

Any reuse/wrap/UUID-rowid-clock ordering or false automatic rollback-detection claim.

**RETAINED EVIDENCE**

```text
sequence traces

old/new generation IDs

duplicate results

recovery logs

allocator-state snapshots
```

**CANONICAL OUTPUT ARTIFACT**

```text
Task01GenerationRecoveryContract
```

**OWNER DECISION**

Owner acknowledges the operational restore invariant.

**WHAT NEXT CONSUMES IT**

F-A3, production recovery procedure, FoundationAdmissionManifest.

---

# 129. FOUNDATION F-A3 — One-read-transaction concurrent consistency

**INPUT**

```text
F-A1/F-A2 candidate

multi-page evidence fixture

health anchor fixture

concurrent delayed insert

concurrent retention DELETE

WAL checkpoint activity
```

**PROOF METHOD**

```text
open read transaction

capture generation/watermark W

begin evidence pagination

concurrently:
    insert eligible old-observed_at row with seq > W
    run health/evidence retention DELETE
    trigger checkpoint where applicable

finish evidence pages

read health/anchors

construct row universe
```

**PASS**

```text
one connection/transaction used

post-W row excluded

rows visible at transaction start not skipped by concurrent delete

health uses same SQLite view

checkpoint does not alter view

repeated canonical construction from captured source view
produces identical EvidenceSnapshotContent membership/order
```

**FAIL**

Any membership shift, page skip, connection restart or mid-build watermark refresh.

**RETAINED EVIDENCE**

```text
transaction trace

watermark

page/cursor trace

concurrent writer/delete/checkpoint timeline

row-universe digest
```

**CANONICAL OUTPUT ARTIFACT**

```text
SnapshotConcurrencyProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-A4/F-A5 and Task-04 snapshot implementation.

---

# 130. FOUNDATION F-A4 — Snapshot query/WAL performance and sizing

**INPUT**

```text
watermark-capable DB

expected per-MAC production cardinality measurements

worst-case controlled cardinality

payload-size distribution

candidate query/index set
```

**PROOF METHOD**

Measure:

```text
EXPLAIN QUERY PLAN

index use

page count

evidence rows

health rows

materialized payload bytes

total semantic input bytes

read transaction duration

WAL growth

checkpoint behavior

writer latency

retention latency

CPU

memory
```

under concurrent representative ingest.

**PASS**

```text
expected product snapshots complete without destabilizing Task-01

selected indexes justified by query plan

SnapshotContentPolicy deterministic limits justified

SnapshotExecutionPolicy operational limits justified

no operational timeout masquerades as semantic resource limit
```

**FAIL**

```text
guessed ceilings

unbounded WAL growth in expected envelope

material writer/retention destabilization

deadline increase used as sole performance fix
```

**RETAINED EVIDENCE**

```text
cardinality report

query plans

benchmark report

WAL/checkpoint metrics

selected-limit rationale
```

**CANONICAL OUTPUT ARTIFACTS**

```text
SnapshotContentPolicy

SnapshotExecutionPolicy
```

**OWNER DECISION**

Owner accepts first production resource envelope.

**WHAT NEXT CONSUMES IT**

F-ADMIT, SnapshotRecord, Task-04 snapshot service.

---

# 131. FOUNDATION F-A5 — Evidence payload integrity / schema registry

**INPUT**

```text
Task-01 retained payload fixtures

current schema validators

tcp_syn/2 candidate validator

portal_headers/2 validator if admitted candidate
```

**PROOF METHOD**

For each supported schema:

```text
read payload_json

duplicate-key rejecting parse

schema validate

EvidenceCanonicalJsonV1 re-encode

stored canonical string compare

SHA-256 compare to payload_sha256
```

Inject malformed JSON, duplicate keys, wrong hash, noncanonical bytes, unknown future schema.

**PASS**

```text
all legitimate rows materialize deterministically

hash mismatch fails build

noncanonical stored payload fails build

unknown schema fails closed for Task-04 materialization

no payload copied into durable classification storage
```

**FAIL**

Any trust-without-validation or opportunistic unknown-schema parse.

**RETAINED EVIDENCE**

```text
fixture corpus

canonical byte outputs

hash comparison report

schema compatibility table
```

**CANONICAL OUTPUT ARTIFACT**

```text
EvidenceSchemaRegistryContract
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-A4 sizing, EvidenceSnapshotContent builder and T-01.

---

# 132. FOUNDATION F-B1 — Binding timeline / cutover clock / valid-from

**INPUT**

```text
actual producer/capture topology

candidate BindingTimeline

producer/central clock measurements

controlled source A→B transition
```

**PROOF METHOD**

Measure relative clocks and exercise cutover around T.

**PASS**

```text
exactly one authoritative binding outside quarantine

producer_id/capture_source_id mandatory

no HA semantics

guard derived from proof

quarantine behavior exact

mac_registry excluded

classification_foundation_valid_from_utc frozen
```

**FAIL**

Hidden historical binding, ambiguous overlap, or unmeasured exact cutover.

**RETAINED EVIDENCE**

```text
topology record

clock measurements

cutover row fixtures

timeline payload/digest
```

**CANONICAL OUTPUT ARTIFACTS**

```text
EvidenceSourceBindingTimeline

BindingClockPolicy
```

**OWNER DECISION**

Owner accepts classification_foundation_valid_from_utc.

**WHAT NEXT CONSUMES IT**

Snapshot builder, SourceEvaluability, FoundationAdmissionManifest.

---

# 133. FOUNDATION F-B2 — Source-health coverage semantics / portal heartbeat

**INPUT**

```text
network sensor health behavior

network spool loss/eviction/stale behavior

portal producer buffering/delivery behavior

status/reason codes

Task-01 delayed-event contract

portal idle-heartbeat candidate
```

**PROOF METHOD**

Controlled:

```text
acquisition failure

transport failure

network spool eviction/stale/capacity conditions

portal delivery failure

recovery/backfill

idle portal operation
```

**PASS**

```text
coverage classes map deterministically

NO covered_delayed inference

unknown reason → unknown

transport-down central state becomes stale/unknown

present backfill remains usable without claiming completeness

portal heartbeat independent of visitors

heartbeat carries no client data
```

**FAIL**

Recovery available automatically proves completeness or `unavailable` treated as one universal failure domain.

**RETAINED EVIDENCE**

```text
producer and central timelines

spool loss metrics

portal queue behavior

reason mapping

heartbeat trace
```

**CANONICAL OUTPUT ARTIFACT**

```text
SourceHealthPolicy
```

**OWNER DECISION**

None unless a future stronger delivery guarantee is proposed.

**WHAT NEXT CONSUMES IT**

F-B3, SourceEvaluability, FoundationAdmissionManifest.

---

# 134. FOUNDATION F-B3 — Task-01-native health retention margin

**INPUT**

```text
accepted SourceHealthPolicy

evidence retention

current health retention

freshness/clock influence horizon
```

**PROOF METHOD**

Derive maximum predecessor influence margin and test oldest retained evidence windows across cleanup.

**PASS**

```text
health_anchor_margin_seconds justified

source_health_retention
>= evidence_retention + margin

required predecessor remains available

Task-01 cleanup needs no BindingTimeline parsing
```

**FAIL**

Equal retention without proof or false unknown caused by predecessor cleanup.

**RETAINED EVIDENCE**

```text
margin derivation

before/after retention fixtures

health reconstruction comparison
```

**CANONICAL OUTPUT ARTIFACT**

```text
Task01HealthRetentionContract
```

**OWNER DECISION**

Owner approves any storage-retention increase if materially required.

**WHAT NEXT CONSUMES IT**

Task-01 v2 config, FoundationAdmissionManifest.

---

# 135. FOUNDATION F-C1 — tcp_syn/2 minimization and exact option schema

**INPUT**

```text
proposed tcp_syn/2 schema

p0f adapter requirements

normal + malformed packet fixtures
```

**PROOF METHOD**

Field-by-field value/privacy matrix and deterministic parser fixtures.

**PASS**

```text
tcp_header_length_bytes retained

exact IP-ID/timestamps absent

ordered exact tcp_option_records variants implemented

WS >14 preserved

EOL padding facts preserved

unknown options bounded

malformed-but-observable preserved

physical truncation rejected
```

**FAIL**

Speculative correlation field, vague option record, duplicate durable representation or missing p0f-required structure.

**RETAINED EVIDENCE**

```text
privacy/value matrix

schema digest

packet fixture digests

normalized outputs
```

**CANONICAL OUTPUT ARTIFACT**

```text
tcp_syn/2 SchemaContract
```

**OWNER DECISION**

Owner approval required for any stronger correlating field than R7 baseline.

**WHAT NEXT CONSUMES IT**

F-C2, F-F1.

---

# 136. FOUNDATION F-C2 — K2A p0f conformance

**INPUT**

```text
accepted tcp_syn/2 candidate

pinned real p0f implementation/corpus

normal/malformed supported fixtures
```

**PROOF METHOD**

Compare transient serializer/matcher behavior to oracle.

**PASS**

Exact supported-scope behavior for:

```text
header length

TTL/distance

window/MSS/MTU expressions

option layout

bad/opt+/exws and other supported quirks

payload presence

fuzzy behavior

specific/generic precedence

match/no-match
```

**FAIL**

Approximate clone or unexplained mismatch.

**RETAINED EVIDENCE**

```text
oracle artifact/digest

fixture digests

adapter output

oracle output

diff report
```

**CANONICAL OUTPUT ARTIFACT**

```text
K2AConformancePackage
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-C3, F-E2, ClassifierArtifactManifest.

---

# 137. FOUNDATION F-C3 — TTL/RSPAN physical proof

**INPUT**

```text
controlled sender

actual running Catalyst mirror/RSPAN config
```

**PROOF METHOD**

Correlate controlled SYN sender TTL with sensor-observed TTL.

**PASS**

Current capture-distance assumption physically proven.

**FAIL**

Mismatch or incomplete path/config evidence.

**RETAINED EVIDENCE**

```text
running config evidence

packet correlation

sender/sensor TTL results
```

**CANONICAL OUTPUT ARTIFACT**

```text
TTLCapturePlacementProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

p0f runtime adapter foundation and FoundationAdmissionManifest.

---

# 138. FOUNDATION F-D1 — Portal Client-Hints value/privacy/lifecycle

**INPUT**

```text
controlled Android

controlled Windows

iOS/Safari-family where available

candidate bounded Accept-CH flow
```

**PROOF METHOD**

Real CaptivPortal flow with sanitized network/storage/log inspection.

**PASS**

Each admitted field individually proves:

```text
actual client support

deterministic normalization

material classification value

raw non-durability

Critical-CH absent

no forced retry

bounded collection

teardown proven where supported

Authorization unchanged
```

**FAIL**

Persistent collection, raw durability, forced retry/auth dependency or no material value.

**RETAINED EVIDENCE**

```text
sanitized flow trace

normalized observations

storage/log audit

teardown proof
```

**CANONICAL OUTPUT ARTIFACT**

Either:

```text
portal_headers/2 SchemaContract
```

or explicit immutable admission result:

```text
portal_headers/2 NOT ADMITTED
```

**OWNER DECISION**

Owner authorizes controlled experiment.

**WHAT NEXT CONSUMES IT**

F-E3/F-F1.

---

# 139. FOUNDATION F-E1 — K1 DHCP source admission / ambiguity proof

**INPUT**

```text
candidate K1 source, beginning with Owner-authorized Fingerbank static artifact where applicable

DHCP fixtures producing:
single candidate
multiple candidates
no match
row-order permutations
```

**PROOF METHOD**

Legal/provenance inspection, canonical import and CandidateSet matching.

**PASS**

```text
source legally admitted

fusion-eligible mapping provenance DHCP-only

ALL deterministic compatible records enumerated

row order has no effect

ambiguity preserved

no-match explicit

per-dimension projection exact

no MAC/OUI enrichment

no hidden score/popularity/first-row selection
```

**FAIL**

Any requirement fails.

Then that candidate K1 source FAILS and Foundation remains blocked until another concrete K1 satisfies the same contract.

**RETAINED EVIDENCE**

```text
source SHA

SourceGovernanceRecord

provenance analysis

canonical import digest

candidate enumeration fixtures/results
```

**CANONICAL OUTPUT ARTIFACTS**

```text
K1 KnowledgeProvenanceManifest

canonical K1 knowledge record set
```

**OWNER DECISION**

Owner accepts external source governance.

**WHAT NEXT CONSUMES IT**

F-E5 KnowledgeBundle.

---

# 140. FOUNDATION F-E2 — K2B production TCP source admission

**INPUT**

```text
candidate TCP knowledge source/corpus

K2AConformancePackage

taxonomy mappings

source provenance/governance
```

**PROOF METHOD**

Canonical import, governance, K2A compatibility and scope review.

**PASS**

At least one concrete K2B source is:

```text
legally admitted

runtime-usable

taxonomy-compatible

freshness-policy resolved if external

source_character recorded

max claim_strength by dimension recorded

age/scope caveats recorded
```

**FAIL**

Only oracle exists, or source is legally/provenance/semantic unusable.

Candidate FAIL does not weaken the mandatory K2B requirement.

**RETAINED EVIDENCE**

```text
source SHA

governance/provenance

import digest

K2A compatibility

claim-strength ceiling rationale
```

**CANONICAL OUTPUT ARTIFACTS**

```text
K2B KnowledgeProvenanceManifest

canonical K2B record set
```

**OWNER DECISION**

Owner accepts external/legacy source use.

**WHAT NEXT CONSUMES IT**

F-E5 KnowledgeBundle.

---

# 141. FOUNDATION F-E3 — K3 internal portal rule admission

**INPUT**

```text
portal_headers/1 normalized schema

portal_headers/2 if admitted

classification taxonomy

candidate K3PortalRuleSet
```

**PROOF METHOD**

Run rule-set test vectors covering:

```text
platform_source provenance

mobile boolean true/false

browser runtime

webview/captive context

model mapping

broad/non-resolving values

conflicting portal observations
```

**PASS**

```text
normalized input only

no raw header/UA/CH parse

mobile true does not imply smartphone

runtime does not imply device_class

rule IDs/version exact

schema compatibility exact

taxonomy mapping exact

claim_derivation and claim_strength explicit

test vectors deterministic
```

**FAIL**

Raw parsing, implicit device class, or undefined rule strength/provenance.

Mandatory K3 slot remains blocked until another concrete internal rule set passes.

**RETAINED EVIDENCE**

```text
rule-set content/digest

test vectors/results

review registration
```

**CANONICAL OUTPUT ARTIFACTS**

```text
K3PortalRuleSet

internal KnowledgeProvenanceManifest
```

**OWNER DECISION**

Owner/TechLead accept K3 semantic rules.

**WHAT NEXT CONSUMES IT**

F-E5 KnowledgeBundle.

---

# 142. FOUNDATION F-E4 — K4 IEEE source admission

**INPUT**

```text
candidate MA-L/MA-M/MA-S source
```

**PROOF METHOD**

Governance/import + prefix/U-L/manufacturer mapping fixtures.

**PASS**

```text
longest-prefix exact

U/L exclusion exact

raw result = mac_assignment_org

manufacturer only through explicit reviewed mapping
```

**FAIL**

OUI-only simplification, unknown governance or automatic manufacturer certainty.

Candidate FAIL blocks mandatory K4 until another concrete source satisfies the contract.

**RETAINED EVIDENCE**

```text
source SHA

SourceGovernanceRecord

import report

prefix fixtures

mapping review
```

**CANONICAL OUTPUT ARTIFACTS**

```text
K4 KnowledgeProvenanceManifest

canonical K4 records
```

**OWNER DECISION**

Owner accepts external source governance.

**WHAT NEXT CONSUMES IT**

F-E5 KnowledgeBundle.

---

# 143. FOUNDATION F-E5 — External freshness/governance completion

**INPUT**

Every mandatory external K1/K2B/K4 source.

**PROOF METHOD**

For each source evaluate:

```text
license/provenance

update cadence/metadata

refresh capability

failure tolerance

source_character

claim-strength caveats
```

**PASS**

Each external source has accepted:

```text
SourceGovernanceRecord

KnowledgeFreshnessPolicy

KnowledgeProvenanceManifest
```

with no unresolved material legal restriction.

**FAIL**

Unknown material legal status or arbitrary freshness threshold.

**RETAINED EVIDENCE**

```text
license/provenance materials/digests

freshness research

Owner decisions
```

**CANONICAL OUTPUT ARTIFACTS**

Accepted governance/freshness/provenance artifacts.

**OWNER DECISION**

REQUIRED for source admission.

**WHAT NEXT CONSUMES IT**

F-E6 KnowledgeBundle.

---

# 144. FOUNDATION F-E6 — Taxonomy / aliases

**INPUT**

```text
classification taxonomy candidate

manufacturer/model alias candidates

source taxonomy mappings
```

**PROOF METHOD**

Fixtures covering:

```text
ios/iPadOS umbrella

Phone/Mobile/Desktop broad values

out-of-scope device classes

unmapped manufacturer/model

multiple source aliases
```

**PASS**

```text
no heuristic aliasing

no broad→narrow squeeze

ios umbrella exact

out-of-scope applicability exact

manufacturer/model canonical IDs deterministic
```

**FAIL**

String similarity changes identity or dimension-specific semantics drift.

**RETAINED EVIDENCE**

```text
taxonomy fixture report

alias provenance/review
```

**CANONICAL OUTPUT ARTIFACTS**

```text
ClassificationTaxonomy

AliasMapping
```

**OWNER DECISION**

Owner/TechLead accept V1 taxonomy scope.

**WHAT NEXT CONSUMES IT**

F-E7 KnowledgeBundle.

---

# 145. FOUNDATION F-E7 — KnowledgeBundle deterministic build / atomic activation

**INPUT**

```text
accepted taxonomy/aliases

K1 records/provenance

K2B records/provenance

K3 rules/provenance

K4 records/provenance

external governance/freshness policies
```

**PROOF METHOD**

Build twice from same semantic inputs; validate mandatory usability; exercise atomic activation/rollback.

**PASS**

```text
same semantic inputs → same bundle digest

mandatory K1/K2B/K3/K4 all concrete/usable

external mandatory sources not expired at admission evaluation time

no placeholder slot

runtime vendor schema absent

accepted bundle immutable

active-pointer switch atomic

in-flight pin stable

rollback to prior accepted bundle atomic
```

**FAIL**

Missing mandatory slot, mutable bundle, undefined digest, vendor runtime dependency or expired source counted as sufficient.

**RETAINED EVIDENCE**

```text
build input manifest

two build digests

validation report

activation/rollback trace
```

**CANONICAL OUTPUT ARTIFACT**

```text
KnowledgeBundle
```

**OWNER DECISION**

Owner accepts Foundation KnowledgeBundle.

**WHAT NEXT CONSUMES IT**

F-F3/F-ADMIT/Task-04 RequestAssembly.

---

# 146. FOUNDATION F-F1 — EvidenceAdapterContractSet freeze

**INPUT**

All classification-eligible schema families after Foundation work.

**PROOF METHOD**

Contract/fixture matrix covering:

```text
dhcp/1

tcp_syn/1

tcp_syn/2

tls_client/1

quic_client/1

portal_headers/1

portal_headers/2 if admitted

valid/partial/degraded

supported/unsupported subtype

extractor/rule version compatibility
```

**PASS**

```text
every schema has explicit adapter or explicit non-fusion reason

tcp_syn/1 non-fusion exact

TLS/QUIC no JA4 claim without admitted knowledge

unknown future schema fail-closed

partial claim capped supporting

degraded no claim

semantic dedup projection frozen
```

**FAIL**

Latest-schema-wins, opportunistic parse, implicit quality authority.

**RETAINED EVIDENCE**

```text
compatibility matrix

fixtures

contract payload/digest
```

**CANONICAL OUTPUT ARTIFACT**

```text
EvidenceAdapterContractSet
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-F2/F-ADMIT/Task-04 adapters.

---

# 147. FOUNDATION F-F2 — ClassificationPolicy semantic freeze

**INPUT**

```text
ClassificationTaxonomy

AliasMapping

EvidenceAdapterContractSet

R7 claim/fusion/support/status contracts

knowledge-expiry reaction semantics
```

**PROOF METHOD**

Produce immutable policy plus machine-readable canonical test-vector specification without implementing Task-04 engine.

**PASS**

Every semantic matrix/status/support cell defined and no hidden source/derivation priority.

**FAIL**

Undefined behavior or inclusion of unrelated retention/product/snapshot-execution policy.

**RETAINED EVIDENCE**

```text
policy payload/digest

test-vector spec

review report
```

**CANONICAL OUTPUT ARTIFACT**

```text
ClassificationPolicy
```

**OWNER DECISION**

Owner + TechLead accept semantic policy.

**WHAT NEXT CONSUMES IT**

F-ADMIT/Task-04 pure core.

---

# 148. FOUNDATION F-F3 — ClassificationRetentionPolicy

**INPUT**

```text
privacy
storage
audit requirements
```

**PROOF METHOD**

Bounded policy/storage review and Owner decision.

**PASS**

Exact production retention/GC semantics frozen.

**FAIL**

Task-04 persistence would start with unresolved retention.

**RETAINED EVIDENCE**

```text
privacy/storage analysis

Owner decision registration
```

**CANONICAL OUTPUT ARTIFACT**

```text
ClassificationRetentionPolicy
```

**OWNER DECISION**

REQUIRED.

**WHAT NEXT CONSUMES IT**

F-ADMIT/Task-04 persistence.

---

# 149. FOUNDATION F-F4 — ProductValidationPolicy

**INPUT**

R7 validation safety/utility requirements and available controlled devices.

**PROOF METHOD**

Freeze immutable validation policy before classifier results are viewed.

**PASS**

Policy includes:

```text
ground truth recorded before result

any wrong resolved known dimension FAIL

false out-of-scope FAIL

Android platform android >= medium

Windows platform windows >= medium

at least one correct device_class >= medium

no automatic learning
```

**FAIL**

Always-unknown engine could pass or result-driven relabeling permitted.

**RETAINED EVIDENCE**

Policy review + Owner decision registration.

**CANONICAL OUTPUT ARTIFACT**

```text
ProductValidationPolicy
```

**OWNER DECISION**

REQUIRED.

**WHAT NEXT CONSUMES IT**

F-ADMIT/T-09.

---

# 150. FOUNDATION F-F5 — Active-pointer atomicity / pinning

**INPUT**

Accepted candidates for:

```text
KnowledgeBundle

EvidenceSourceBindingTimeline

BindingClockPolicy

SourceHealthPolicy

SnapshotContentPolicy

SnapshotExecutionPolicy

EvidenceSchemaRegistryContract

EvidenceAdapterContractSet

ClassificationPolicy
```

**PROOF METHOD**

Exercise pointer activation/rollback while a synthetic in-flight build/request remains pinned.

**PASS**

```text
ArtifactContent immutable

pointer switch atomic

in-flight operation retains old pinned IDs/digests

new operation sees newly active IDs

rollback points to prior accepted artifact
```

**FAIL**

Mutable in-place policy or in-flight active-pointer reread.

**RETAINED EVIDENCE**

Activation/pinning trace.

**CANONICAL OUTPUT ARTIFACT**

```text
FoundationActivationProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-ADMIT and RequestAssembly.

---

# 151. FOUNDATION F-ADMIT — Foundation Admission

**INPUT**

All mandatory Foundation GateResultManifests and their output ArtifactContents.

**PROOF METHOD**

TechLead11 full foundation review against:

```text
R7 FINAL architecture reference

exact foundation repository candidate

all gate result manifests

artifact compatibility/dependency graph
```

**PASS**

```text
all mandatory gates PASS

mandatory K1/K2B/K3/K4 concrete and usable

classification_foundation_valid_from frozen

all required active artifacts immutable/accepted

no unresolved mandatory policy

no lifecycle contradiction

no silent fallback
```

**FAIL**

Any mandatory missing/failed artifact or unresolved contract.

**RETAINED EVIDENCE**

```text
complete foundation gate inventory

accepted artifact inventory

TechLead review registration

Owner decision registration
```

**CANONICAL OUTPUT ARTIFACT**

```text
FoundationAdmissionManifest
```

**OWNER DECISION**

EXPLICIT OWNER ACCEPT REQUIRED.

**WHAT NEXT CONSUMES IT**

```text
TechLead11 may decompose TASK-04
```

No Task-04 implementation is required to pass F-ADMIT.

---

# 152. Task-04 decomposition after Foundation Admission

Only:

```text
F-ADMIT = PASS
+
Owner Foundation acceptance
```

permits TechLead11 to decompose Task-04.

Architecture-aligned decomposition may include:

```text
TASK-04A
Snapshot materialization / SourceEvaluability integration

TASK-04B
EvidenceAdapters + OriginAssessment

TASK-04C
pure fusion + DimensionResult / global result

TASK-04D
ClassificationRequest / persistence / audit

TASK-04E
internal read contract

TASK-04F
controlled acceptance
```

No public/UI/Authorization scope is implied.

Task-04 code still requires separate Owner authorization.

---

# 153. Task-04 acceptance lifecycle

Task-04 gates execute only after:

```text
FoundationAdmissionManifest exists

TechLead11 decomposed Task-04

Owner authorized Task-04

implementation candidate exists
```

Every T-gate produces GateResultManifest.

---

# 154. TASK-04 T-01 — Snapshot materialization / payload integrity execution

**INPUT**

Implemented snapshot/materialization path + accepted foundation artifacts.

**PROOF METHOD**

Execute:

```text
multi-page valid payload set

hash mismatch

noncanonical payload bytes

duplicate-key JSON

unknown schema

content-limit exceed

operational timeout
```

**PASS**

```text
actual normalized payload reaches adapters transiently

payload integrity verified

EvidenceSnapshotContent stores only descriptor/digest

materialization not persisted

content ceiling counts real payload bytes

content-limit = semantic no-result

operational timeout = retryable no-result
```

**FAIL**

Classifier has no payload, duplicated payload retention, or timeout becomes semantic classification.

**RETAINED EVIDENCE**

Request/snapshot/materialization test report without durable raw duplicated payload.

**CANONICAL OUTPUT ARTIFACT**

```text
SnapshotMaterializationExecutionProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-02/T-03.

---

# 155. TASK-04 T-02 — SourceEvaluability execution

**INPUT**

Implemented SourceEvaluability builder.

**PROOF METHOD**

Fixtures covering every V1 coverage class, normalized intervals, cutover quarantine and present-evidence matrix.

**PASS**

```text
canonical normalized interval partition

stable digest for semantically equal coverage

no covered_delayed

present evidence remains usable

absence never becomes negative fingerprint
```

**FAIL**

Representation-dependent digest or false completeness.

**RETAINED EVIDENCE**

Input snapshot IDs and output SourceEvaluability artifacts.

**CANONICAL OUTPUT ARTIFACT**

```text
SourceEvaluabilityExecutionProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-03/T-05.

---

# 156. TASK-04 T-03 — K1/K3/adapter OriginAssessment execution

**INPUT**

Implemented adapters/OriginAssessment + accepted K1/K2B/K3/K4 and optional JA4 knowledge.

**PROOF METHOD**

Fixtures for:

```text
K1 all-candidate enumeration

row-order permutation

K1 ambiguity

no-match

K3 provenance rules

semantic dedup

quality caps

unsupported schema

expired external knowledge

JA4 without reference knowledge

same-origin strong/supporting conflicts
```

**PASS**

Exact OriginDimensionAssessment/OriginAssessment contracts and conflict_strength behavior.

**FAIL**

First-row selection, hidden scoring, raw portal parsing, JA4 heuristic, derivation priority or undefined state.

**RETAINED EVIDENCE**

Fixture matrix and resulting OriginAssessment IDs/digests.

**CANONICAL OUTPUT ARTIFACT**

```text
OriginAssessmentExecutionProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-04.

---

# 157. TASK-04 T-04 — Cross-origin fusion / support / statuses

**INPUT**

Pure fusion core + ClassificationPolicy canonical vectors.

**PROOF METHOD**

Complete vector matrix including:

```text
strong/strong agreement/conflict

strong/supporting contradiction

supporting/supporting conflict

supporting internal conflict + clean strong origin

strong internal conflict + clean strong origin

same-origin lower-strength contradiction and HIGH prohibition

out-of-scope

broad information

DimensionResult/global combinations
```

**PASS**

Exact R7 outcomes.

**FAIL**

Hidden priority, blanket origin-conflict rule, HIGH despite incompatible supporting claim, or undefined matrix cell.

**RETAINED EVIDENCE**

Vector/result table with policy digest.

**CANONICAL OUTPUT ARTIFACT**

```text
FusionExecutionProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-05/T-06.

---

# 158. TASK-04 T-05 — RequestAssembly / pure-core determinism / knowledge time

**INPUT**

Exact live and replay requests.

**PROOF METHOD**

```text
activate bundle/policy changes during an in-flight request

vary system wall clock without changing explicit inputs

attempt live caller backdating

test negative source age

advance explicit knowledge_evaluation_at

expire one knowledge source
```

with DB/network/filesystem blocked inside pure core.

**PASS**

```text
all active artifacts pinned once

caller cannot override live knowledge time

negative source age fails closed

same request digest → same result digest

wall clock alone has no effect

later explicit evaluation time may suppress expired claims

single source expiry does not crash classifier
```

**FAIL**

Pointer reread, backdating, hidden clock/I/O dependency.

**RETAINED EVIDENCE**

Request/result digests and activation timeline.

**CANONICAL OUTPUT ARTIFACT**

```text
RequestAssemblyDeterminismProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-06/T-07.

---

# 159. TASK-04 T-06 — Exact ClassifierArtifactManifest

**INPUT**

Exact Task-04 candidate.

**PROOF METHOD**

Generate and validate manifest.

**PASS**

Includes:

```text
commit SHA

tree SHA

engine semantic version

ArtifactCanonicalJsonV1 identity

all EvidenceAdapter implementation identities

K2A matcher implementation

result/snapshot contract versions

build digest where needed
```

**FAIL**

Vague `v1/current/latest` identity.

**RETAINED EVIDENCE**

Repository/build identity.

**CANONICAL OUTPUT ARTIFACT**

```text
ClassifierArtifactManifest
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-07/T-09/ClassificationRequestManifest.

---

# 160. TASK-04 T-07 — Classification persistence / audit replay / GC

**INPUT**

Implemented persistence + accepted ClassificationRetentionPolicy.

**PROOF METHOD**

Persist controlled classifications, delete Task-01 source fixture for Level-B test, replay, then expire a test classification and run reference-aware GC.

**PASS**

```text
SnapshotRecord retrievable

EvidenceSnapshotContent retrievable

SourceEvaluability retrievable

OriginAssessments retrievable

request/result/policies/bundle/classifier retrievable

Level-B result replay exact

referenced artifact cannot GC

unreferenced artifact becomes eligible only after policy permits
```

**FAIL**

Dangling SnapshotRecord ID, digest-without-content, or retention mismatch.

**RETAINED EVIDENCE**

Persistence inventory, replay report, GC report.

**CANONICAL OUTPUT ARTIFACT**

```text
ClassificationAuditPersistenceProof
```

**OWNER DECISION**

Owner verifies retention implementation.

**WHAT NEXT CONSUMES IT**

T-08/T-09/T-ACCEPT.

---

# 161. TASK-04 T-08 — Offline / failure isolation / no Cloud

**INPUT**

Accepted candidate.

**PROOF METHOD**

Block all external network and inject:

```text
classification DB failure

KnowledgeBundle load failure

snapshot execution timeout

SnapshotContentPolicy exceed

classifier exception

expired individual knowledge source
```

Also verify no production-client request path to Fingerbank Cloud.

**PASS**

```text
normal classification requires no Internet

Fingerbank Cloud absent from V1 production path

no partial classification

operational timeout retryable/no semantic result

deterministic size exceed produces no result

classification failure does not affect Task-01/Auth/CAPPORT

expired source only suppresses its claims
```

**FAIL**

Remote hard dependency, client data Cloud submission, partial result or Authorization/ingest impact.

**RETAINED EVIDENCE**

Fault/network matrix.

**CANONICAL OUTPUT ARTIFACT**

```text
OfflineFailureIsolationProof
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-09/T-ACCEPT.

---

# 162. TASK-04 T-09 — Controlled product safety / utility / anti-learning

**INPUT**

Exact accepted candidate plus Owner-controlled Android smartphone and Windows laptop.

**PROOF METHOD**

Before classifier result is visible:

```text
record controlled ground truth

seal/sign ground-truth record
```

Then execute normal product classification path.

**PASS — SAFETY**

```text
no incorrect resolved known-ground-truth dimension

no false recognized_out_of_scope
for known in-scope platform/device_class
```

**PASS — UTILITY**

```text
Android:
platform_family android
resolved
support >= medium

Windows laptop:
platform_family windows
resolved
support >= medium

at least one:
correct device_class
resolved
support >= medium
```

**PASS — ANTI-LEARNING**

```text
validation execution does NOT mutate:
KnowledgeBundle
aliases
K3 rules
ClassificationPolicy
claim strengths
```

**FAIL**

Any wrong resolved dimension, false out-of-scope, utility failure, result-driven relabeling or automatic rule mutation.

**RETAINED EVIDENCE**

Privacy-safe:

```text
pre-result ground-truth record digest

classification request digest

result digest

comparison report

candidate classifier identity
```

**CANONICAL OUTPUT ARTIFACT**

```text
Task04ProductValidationProof
```

**OWNER DECISION**

Owner verifies ground truth and acceptance result.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

---

# 163. TASK-04 T-ACCEPT — Implementation acceptance

**INPUT**

All mandatory Task-04 GateResultManifests + exact candidate + FoundationAdmissionManifest.

**PROOF METHOD**

TechLead11 full acceptance review.

**PASS**

Implementation conforms to R7 + exact FoundationAdmissionManifest with no known semantic/audit/safety/utility/fallback defect.

**FAIL**

Any mandatory gate fail or architecture divergence.

**RETAINED EVIDENCE**

Full T-gate inventory + TechLead/Owner review registrations.

**CANONICAL OUTPUT ARTIFACT**

```text
Task04AcceptanceManifest
```

**OWNER DECISION**

Owner final Task-04 acceptance decision.

**WHAT NEXT CONSUMES IT**

Normal project publication/deployment/activation flow.

---

# 164. Permanent no-silent-fallback / stop conditions

Forbidden:

```text
no watermark
→ wall-clock approximation

payload hash mismatch
→ trust payload anyway

missing payload
→ classify from descriptor only

unknown schema
→ parse nearest schema

no binding
→ infer producer from arrived rows

cutover uncertainty
→ choose old/new arbitrarily

unknown health reason
→ assume available/unavailable

transport recovery
→ infer complete delayed coverage

expired knowledge
→ retain old strength silently

mandatory K1/K2B/K3/K4 candidate fail
→ fill placeholder

K1 ambiguity
→ pick first row

K1 source fail
→ weaken deterministic matching

raw portal header
→ parse inside Task-04

JA4 without reference knowledge
→ heuristic platform/device claim

Fingerbank Cloud
→ silently call production API

tcp_syn/1
→ approximate tcp_syn/2

malformed observable TCP option
→ silently drop complete packet

content limit exceeded
→ classify first N rows

operational timeout
→ semantic not_evaluable

declared Client Hint
→ automatic reliability priority

IEEE assignment org
→ device manufacturer automatically

same-origin repeated rows
→ extra votes

supporting contradiction present
→ HIGH result

validation result
→ automatic KnowledgeBundle mutation

classification failure
→ affect Authorization/CAPPORT
```

At every stop condition:

```text
explicit typed failure/reason
NO silent approximation
```

Appendix F maps these conditions to exact actions.

---

# 165. Required R7 status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R7

STATUS =
FOR OWNER + TECHLEAD11 STRICT REVIEW

R6 =
SUPERSEDED ONLY AFTER R7 ACCEPTANCE

ARCHITECTURE CONTRACT FINAL =
NO

TASK-04 =
HOLD

TASK-04 CODER TASK =
NO

PRODUCTION CHANGE =
NO
```

R7 itself does not authorize PRE-TASK code.

If and only if:

```text
OWNER ACCEPT
+
TECHLEAD11 ACCEPT
```

R7 may become Architecture Contract FINAL.

Then:

```text
PRE-TASK foundation implementation may begin
under separate TechLead tasks + Owner authorization
```

Task-04 remains HOLD until:

```text
F-ADMIT = PASS
```

---

# APPENDIX A — ARCHITECTURE PRESERVATION / REGRESSION MATRIX (R6 → R7)

Status meanings:

```text
PRESERVED =
contract remains authoritative with the same material semantics

REVISED =
contract remains, but R7 changes/strengthens its semantics explicitly

INTENTIONALLY REMOVED =
contract no longer exists; reason and material Owner decision are required
```

R7 contains no silently omitted authoritative R6 section.

| Previous R6 contract | Status | R7 section reference | Reason |
|---|---|---|---|
| R6 §1. Document disposition | REVISED | §1, §165 | R7 status wording required; R6 supersession is conditional on R7 acceptance. |
| R6 §2. Owner quality policy | PRESERVED | §2 | Owner quality policy retained and adds no-silent-regression. |
| R6 §3. Verified repository baseline | PRESERVED | §3 | Repository baseline and current Task-01/02/03 facts retained. |
| R6 §4. Exact Task-03A status | PRESERVED | §4 | 03A tooling vs empirical campaign distinction retained. |
| R6 §5. Permanent architecture principles | REVISED | §7 | All permanent guards retained; restored JA4/Cloud/no-learning/task-scope guards added. |
| R6 §6. Lifecycle — no gate deadlock | PRESERVED | §6 | Non-circular architecture→foundation→Task-04 lifecycle retained. |
| R6 §7. PRE-TASK foundation scope | REVISED | §5-§6, §126-§151 | PRE-TASK scope retained and clarified against Task-04 boundaries. |
| R6 §8. Universal immutable artifact convention | REVISED | §9-§12 | Universal artifact convention split into ArtifactContent and ArtifactRegistration; canonical JSON fully frozen. |
| R6 §9. Task-01 global ingest sequence | PRESERVED | §15 | Global evidence+health sequence retained. |
| R6 §10. Ingest allocation transaction | PRESERVED | §16 | Transactional allocator/write invariant retained. |
| R6 §11. Duplicate semantics | PRESERVED | §17 | Idempotent/conflicting duplicate semantics retained. |
| R6 §12. Sequence gaps and cleanup | PRESERVED | §17 | Gap/cleanup semantics retained. |
| R6 §13. Database generation | REVISED | §18-§21 | Generation retained; empty watermark and exact UUIDv4 format added. |
| R6 §14. Initial watermark migration | REVISED | §13, §19 | Bootstrap migration expanded into deployable v1→v2 schema migration. |
| R6 §15. Controlled restore / rollback recovery | REVISED | §14, §20 | Controlled restore contract retained and application rollback contract added. |
| R6 §16. Restore limitation | PRESERVED | §21 | Arbitrary external rollback detection limitation remains explicit. |
| R6 §17. Immutable ingest watermark | PRESERVED | §22 | Watermark semantic retained. |
| R6 §18. One SQLite read transaction per EvidenceSnapshot | PRESERVED | §23 | Single SQLite read transaction retained. |
| R6 §19. Snapshot transaction execution failure | PRESERVED | §37 | Operational execution failures remain non-semantic no-result failures. |
| R6 §20. Live snapshot build mode | PRESERVED | §24 | Live caller cannot choose watermark/generation. |
| R6 §21. Replay mode | PRESERVED | §25 | Replay uses exact stored historical identities. |
| R6 §22. Window validity | PRESERVED | §26 | Completed-window validity retained. |
| R6 §23. Snapshot capture time vs semantic identity | REVISED | §27 | Semantic snapshot vs capture audit metadata retained; SnapshotRecord now exact artifact. |
| R6 §24. EvidenceSnapshotContent payload | REVISED | §28-§33 | Durable manifest retained but transient normalized payload materialization added. |
| R6 §25. Evidence descriptor | PRESERVED | §29 | Classification-relevant evidence metadata descriptor retained. |
| R6 §26. Source-health descriptor | PRESERVED | §30 | Health descriptor retained. |
| R6 §27. Canonical snapshot ordering | PRESERVED | §34 | Canonical ordering retained. |
| R6 §28. Complete pagination | PRESERVED | §35 | Complete pagination retained. |
| R6 §29. SnapshotContentPolicy vs SnapshotExecutionPolicy | REVISED | §36-§38 | Content/execution policy split retained; content sizing now counts actual materialized payload and WAL proof. |
| R6 §30. EvidenceSourceBindingTimeline | PRESERVED | §39 | BindingTimeline retained and mac_registry excluded. |
| R6 §31. Binding epoch | PRESERVED | §39 | Binding epoch identity/effective intervals retained. |
| R6 §32. Exactly one authoritative binding in V1 | PRESERVED | §40 | Exactly one authoritative V1 binding retained. |
| R6 §33. Binding-authorized row membership | PRESERVED | §41 | Binding-authorized membership retained. |
| R6 §34. BindingClockPolicy | PRESERVED | §42 | BindingClockPolicy/cutover quarantine retained. |
| R6 §35. Classification foundation valid-from | PRESERVED | §43 | Foundation valid-from retained. |
| R6 §36. Source-health is coverage evidence | PRESERVED | §44 | Coverage remains separate from present-evidence validity. |
| R6 §37. SourceHealthPolicy | REVISED | §46 | SourceHealthPolicy retained with conservative V1 coverage model. |
| R6 §38. Failure-domain / coverage classes | REVISED | §45 | covered_delayed intentionally removed; recovery no longer asserts completeness. |
| R6 §39. Transport failure truth | PRESERVED | §47 | Transport failure truth retained. |
| R6 §40. Health backfill delayed-event limit | PRESERVED | §48 | Health backfill remains bounded by Task-01 delayed-event contract. |
| R6 §41. Source-health predecessor anchor retention | REVISED | §49 | Predecessor protection changed to Task-01-native retention margin; no BindingTimeline cleanup coupling. |
| R6 §42. Health state does not cross binding epoch | PRESERVED | §50 | Health state does not cross binding epoch. |
| R6 §43. SourceEvaluability meaning | PRESERVED | §44, §51 | Coverage and present evidence remain separate. |
| R6 §44. SourceEvaluability states | REVISED | §52-§54 | Evaluability states retained; canonical interval normal form now exact. |
| R6 §45. Evidence-present vs health matrix | REVISED | §51 | Evidence-present/health matrix retained and adapted to conservative coverage classes. |
| R6 §46. SourceEvaluability canonical artifact | REVISED | §53-§54 | SourceEvaluability artifact retained with canonical partition/digest rules. |
| R6 §47. EvidenceAdapterContract | REVISED | §55-§56 | EvidenceAdapterContract retained and schema-registry layer made explicit. |
| R6 §48. Unsupported evidence contract | PRESERVED | §56, §58 | Unsupported future evidence remains fail-closed/non-fusion. |
| R6 §49. quality_state semantics | PRESERVED | §57 | valid/partial/degraded behavior retained. |
| R6 §50. V1/V2 coexistence | PRESERVED | §58 | Explicit V1/V2 coexistence retained; JA4 safe no-claim restored. |
| R6 §51. tcp_syn/2 principle and scope | PRESERVED | §59-§60 | tcp_syn/2 protocol-neutral scope retained. |
| R6 §52. tcp_syn/2 durable facts | REVISED | §61-§69 | Durable facts retained and option records fully specified. |
| R6 §53. IP-ID / timestamp minimization | PRESERVED | §61, §71 | Exact IP-ID/timestamps remain minimized. |
| R6 §54. One TCP option representation | REVISED | §62-§69 | Single option representation retained; exact record variants restored. |
| R6 §55. Malformed option semantics | PRESERVED | §70 | Malformed-observable vs structural truncation distinction retained. |
| R6 §56. tcp_syn/2 privacy/minimization gate | PRESERVED | §71, F-C1 | Field-by-field privacy/minimization gate retained. |
| R6 §57. p0f conformance split | PRESERVED | §72 | K2A/K2B split retained. |
| R6 §58. TTL/RSPAN proof | PRESERVED | §73 | TTL/RSPAN physical proof retained. |
| R6 §59. Portal Client Hints | PRESERVED | §74-§75 | portal_headers/2 remains bounded candidate. |
| R6 §60. Critical-CH / Accept-CH | PRESERVED | §74-§75 | Critical-CH forbidden and bounded Accept-CH retained. |
| R6 §61. Portal idle source-health | PRESERVED | §76 | Portal idle heartbeat retained. |
| R6 §62. External artifact boundary | PRESERVED | §77 | External artifact canonical import retained. |
| R6 §63. KnowledgeBundle canonical contract | REVISED | §82-§83 | KnowledgeBundle identity retained and provenance/governance schema expanded. |
| R6 §64. Knowledge source manifest | REVISED | §78-§80 | Source manifest generalized into external/internal provenance plus full governance record. |
| R6 §65. Knowledge freshness | PRESERVED | §81, §65 | Fresh/stale/expired mechanism retained without magic ages. |
| R6 §66. Knowledge expiry runtime behavior | PRESERVED | §84 | Expired source suppresses claims without classifier crash. |
| R6 §67. KnowledgeBundle activation | PRESERVED | §83 | KnowledgeBundle immutable activation/pinning/rollback retained. |
| R6 §68. Mandatory offline knowledge | REVISED | §85 | Mandatory offline knowledge retained; symmetric failure/no-placeholder rule added. |
| R6 §69. Fingerbank K1 provenance purity | REVISED | §86-§88 | DHCP provenance purity retained; complete ambiguity-preserving CandidateSet contract restored. |
| R6 §70. IEEE semantics | PRESERVED | §92 | IEEE assignment-org semantics retained. |
| R6 §71. classification_taxonomy_v1 | PRESERVED | §95 | classification_taxonomy_v1 retained; ios umbrella explicit. |
| R6 §72. recognized_out_of_scope applicability | PRESERVED | §96 | Dimension-specific out-of-scope applicability retained. |
| R6 §73. Canonical manufacturer/model identity | PRESERVED | §97 | Canonical manufacturer/model IDs and aliases retained. |
| R6 §74. Claim derivation vs claim strength | PRESERVED | §98 | Claim derivation remains orthogonal to claim strength. |
| R6 §75. Origin groups and purity | REVISED | §99 | Origin purity retained; JA4/Cloud guards restored separately. |
| R6 §76. Semantic dedup | PRESERVED | §100 | Row-count semantic dedup retained. |
| R6 §77. Same-origin strength matrix | REVISED | §102-§104 | Same-origin strength matrix retained; conflict_strength and K1 ambiguity distinction added. |
| R6 §78. Cross-origin strength matrix | REVISED | §105 | Cross-origin matrix retained and now consumes conflict strength. |
| R6 §79. OriginAssessment canonical contract | REVISED | §101-§102, §79 | OriginAssessment retained; OriginDimensionAssessment exact schema added. |
| R6 §80. OriginAssessment references | REVISED | §80, §101 | Knowledge/evidence references generalized for internal/external provenance. |
| R6 §81. ClassificationPolicy | REVISED | §111 | ClassificationPolicy narrowed to pure semantics; cross-layer policies removed. |
| R6 §82. DimensionResult | PRESERVED | §108 | DimensionResult remains canonical and service/UI-independent. |
| R6 §83. Final status semantics | PRESERVED | §109 | Final dimension status semantics/precedence retained. |
| R6 §84. support_level | REVISED | §107 | Support levels retained; HIGH explicitly forbids same-origin lower-strength contradictions. |
| R6 §85. Global classification status | PRESERVED | §110 | Global-status derivation retained. |
| R6 §86. Pure classification core | REVISED | §114 | Pure no-I/O/no-clock core retained and now receives transient materialization. |
| R6 §87. ClassifierArtifactManifest | REVISED | §115 | Exact classifier identity retained; canonicalizer and all adapter implementations explicit. |
| R6 §88. ClassificationRequestManifest | REVISED | §112-§116 | Request manifest retained; live knowledge time/service-owned RequestAssembly pinning added. |
| R6 §89. Semantic ClassificationResult | PRESERVED | §117 | Pure semantic ClassificationResult retained. |
| R6 §90. Persistence metadata | PRESERVED | §118 | Service persistence metadata remains separate. |
| R6 §91. ClassificationRetentionPolicy | PRESERVED | §119 | Separate Owner-controlled retention policy retained. |
| R6 §92. Audit retention | REVISED | §118-§120 | Audit retention retained; SnapshotRecord now mandatory retrievable object. |
| R6 §93. Audit levels | PRESERVED | §120 | Two-level audit retained. |
| R6 §94. ProductValidationPolicy | REVISED | §121-§122 | Safety/minimum utility retained; ground truth-before-result and no-learning restored. |
| R6 §95. Foundation Admission gate model | REVISED | §126-§151 | Foundation gate lifecycle retained and expanded with machine-identifiable GateResultManifests. |
| R6 §96. Foundation Admission | REVISED | §124, §151 | Foundation Admission retained; FoundationAdmissionManifest now exact schema. |
| R6 §97. Task-04 Acceptance gates | REVISED | §153-§163 | Task-04 acceptance lifecycle retained with materialization/K1/K3/conflict/pinning regressions covered. |
| R6 §98. Permanent no-silent-fallback rules | PRESERVED | §164, Appendix F | No-silent-fallback retained and expanded. |
| R6 §99. Required R6 status | REVISED | §1, §165 | Required status updated to R7 wording; no self-promotion. |



## Appendix A.2 — R6 authoritative subsections / gate preservation

| R6 subsection / gate | Status | R7 reference | Reason |
|---|---|---|---|
| Identical idempotent duplicate | PRESERVED | §17 | No-sequence duplicate-noop retained. |
| Conflicting duplicate | PRESERVED | §17 | Rollback/no conflicting row retained. |
| EvidenceSnapshotContent | REVISED | §27-§33 | Durable descriptor/digest manifest retained; transient payload materialization added. |
| SnapshotRecord | REVISED | §27, §118-§120 | Now exact retained audit ArtifactContent, preventing dangling reference. |
| SnapshotContentPolicy | REVISED | §36, F-A4 | Now counts actual normalized payload materialization bytes. |
| SnapshotExecutionPolicy | PRESERVED | §37, F-A4 | Operational/non-semantic failure separation retained. |
| covered_available | PRESERVED | §45 | Healthy coverage class retained. |
| covered_delayed | INTENTIONALLY REMOVED | §45-§47 | Current network spool/portal buffering cannot prove outage completeness; R7 chooses conservative V1. Material removal accepted only if Owner+TechLead accept R7. |
| acquisition_unavailable | PRESERVED | §45 | Acquisition failure class retained. |
| delivery_pending_lossless | INTENTIONALLY REMOVED | §45-§47 | No current producer has a proven completeness checkpoint/lossless guarantee sufficient for V1; absence remains loss-possible/unknown. |
| delivery_loss_possible | REVISED | §45 | Renamed/refined to delivery_unavailable_loss_possible; conservative semantics retained. |
| delivery_loss_confirmed | PRESERVED | §45 | Known-loss class retained. |
| unsupported | PRESERVED | §45, §52 | Intentional capability state retained. |
| unknown (coverage) | PRESERVED | §45, §52 | Conservative unknown coverage retained. |
| evaluable | PRESERVED | §52 | Coverage state retained under conservative classes. |
| partially_evaluable | PRESERVED | §52 | Coverage state retained. |
| not_evaluable | PRESERVED | §52 | Coverage state retained. |
| unknown (SourceEvaluability) | PRESERVED | §52 | Coverage uncertainty retained. |
| valid quality_state | PRESERVED | §57 | Normal adapter claim handling retained. |
| partial quality_state | PRESERVED | §57 | Dimension-specific usability + supporting cap retained. |
| degraded quality_state | PRESERVED | §57 | Excluded from semantic claims in V1. |
| F-A1 — Watermark + one-transaction snapshot foundation | REVISED | F-A1/F-A3 | Split into deployable migration/watermark and concurrency proofs; semantics preserved. |
| F-A2 — Concurrent ingest + retention determinism | REVISED | F-A3 | Concurrent ingest/delete/checkpoint proof strengthened. |
| F-A3 — Generation migration/recovery | REVISED | F-A1/F-A2, §13-§21 | Schema migration and application rollback made explicit. |
| F-A4 — Source-health predecessor anchor retention | REVISED | F-B3, §49 | Binding-dependent cleanup removed; Task-01-native retention margin used. |
| F-B1 — Binding timeline / clock / valid-from | PRESERVED | F-B1 | Single-authority/cutover/valid-from gate retained. |
| F-B2 — Health failure-domain / coverage policy | REVISED | F-B2 | covered_delayed/lossless assumptions removed; current producer loss behavior included. |
| F-B3 — Portal idle heartbeat | REVISED | F-B2 | Heartbeat incorporated into health-coverage proof; core guard retained. |
| F-C1 — tcp_syn/2 minimization/schema | REVISED | F-C1 | Exact tcp_option_records variants restored. |
| F-C2 — p0f adapter/matcher conformance | PRESERVED | F-C2 | Exact K2A oracle conformance retained. |
| F-C3 — TTL/RSPAN physical proof | PRESERVED | F-C3 | Physical topology proof retained. |
| F-D1 — Client Hints actual-flow + teardown | PRESERVED | F-D1 | Critical-CH prohibition and bounded teardown retained. |
| F-E1 — Fingerbank static import/provenance purity | REVISED | F-E1 | Complete ambiguity-preserving K1 matching and alternative-source path restored. |
| F-E2 — IEEE import | REVISED | F-E4 | IEEE admission retained; gate renamed/ordered within knowledge group. |
| F-E3 — Production TCP knowledge admission | REVISED | F-E2 | K2B admission retained with explicit legacy claim-strength ceiling. |
| F-E4 — Taxonomy/alias determinism | REVISED | F-E6 | Taxonomy/alias gate retained with dimension-specific out-of-scope semantics. |
| F-E5 — Knowledge freshness policies | REVISED | F-E5 | External-only freshness/governance separation added. |
| F-F1 — KnowledgeBundle build/activation | REVISED | F-E7 | Bundle deterministic build/activation retained and provenance model expanded. |
| F-F2 — Snapshot sizing | REVISED | F-A4 | Moved earlier; now includes real payload bytes and WAL/query performance. |
| F-F3 — EvidenceAdapterContractSet freeze | REVISED | F-F1 | Adapter contract retained; EvidenceSchemaRegistry split separately. |
| F-F4 — ClassificationPolicy freeze | REVISED | F-F2 | Policy narrowed to pure classification semantics. |
| F-F5 — ClassificationRetentionPolicy freeze | REVISED | F-F3 | Separate retention policy retained. |
| F-F6 — ProductValidationPolicy freeze | REVISED | F-F4 | Ground-truth-before-result/no-learning added. |
| T-01 — EvidenceAdapter execution/coexistence | REVISED | T-01/T-03 | Materialization integrity split into T-01; adapter/origin behavior covered T-03. |
| T-02 — SourceEvaluability execution | REVISED | T-02 | Canonical interval normal form and conservative coverage added. |
| T-03 — OriginAssessment execution | REVISED | T-03 | K1/K3/JA4/conflict_strength regression cases added. |
| T-04 — Fusion/Dimension/global execution | REVISED | T-04 | Same-origin conflict strength and HIGH contradiction completeness added. |
| T-05 — Pure-core determinism / explicit knowledge time | REVISED | T-05 | Live RequestAssembly owns/pins knowledge time and artifacts. |
| T-06 — Exact ClassifierArtifactManifest | PRESERVED | T-06 | Exact identity retained and canonicalizer/adapter identities explicit. |
| T-07 — Persistence/retention/audit replay | REVISED | T-07 | SnapshotRecord/retrievable input objects explicitly required. |
| T-08 — Offline/failure isolation | REVISED | T-08 | Cloud out-of-scope and source-expiry degradation explicitly tested. |
| T-09 — Controlled product safety + utility | REVISED | T-09 | Ground truth pre-seal and no-learning enforced. |
| T-ACCEPT — Task-04 acceptance | PRESERVED | T-ACCEPT | Post-implementation acceptance boundary retained. |

# APPENDIX B — Restored prior permanent guards

The following guards existed in earlier architecture/review history and are explicitly restored so that R7 does not regress while correcting R6.

| Restored guard | R7 reference | Status / reason |
|---|---|---|
| K1 returns ALL deterministic compatible candidates, not first/best row | §86, F-E1 | RESTORED; required for ambiguity-preserving DHCP interpretation |
| K1 CandidateSet projects independently per dimension | §86, §104, F-E1 | RESTORED |
| K1 row order does not affect result | §86, F-E1 | RESTORED |
| K1 no-match is explicit | §86, F-E1 | RESTORED |
| K1 may not use MAC/OUI inside DHCP origin | §86-§88 | RESTORED |
| Failed Fingerbank K1 cannot weaken requirements; another concrete K1 is required | §88, §85, F-E1 | RESTORED |
| K3 consumes normalized portal evidence only | §90-§91, F-E3 | RESTORED |
| K3 never parses raw UA / raw Client Hints / raw headers | §90, F-E3 | RESTORED |
| `mobile_boolean=true` does not imply smartphone | §90-§91 | RESTORED |
| Browser runtime/WebView context does not automatically imply device class | §90-§91 | RESTORED |
| K3 is internal deterministic knowledge, not fake external freshness source | §79, §90-§91 | RESTORED |
| Knowledge references support both internal and external provenance | §79-§80 | RESTORED |
| JA4 observed alone produces no platform/device/manufacturer/model claim | §93, F-F1, T-03 | RESTORED |
| Local JA4 frequency heuristics are forbidden without admitted knowledge | §93 | RESTORED |
| JA4 knowledge is optional and not Foundation blocker | §93 | RESTORED |
| Fingerbank Cloud is out of Task-04 V1 scope, default OFF, no production client submission | §94, T-08 | RESTORED |
| Future Cloud requires separate architecture + Owner opt-in + privacy/origin review | §94 | RESTORED |
| Classification/validation never automatically trains or mutates production knowledge/policy | §121-§122, T-09 | RESTORED |
| TCP option record variants are exact, including EOL/NOP/MSS/WS/SACK/TS/unknown | §62-§70, F-C1 | RESTORED |
| WS values >14 remain observable and are not parser-rejected | §66 | RESTORED |
| Malformed-but-observable option syntax survives for p0f `bad/opt+/exws` reconstruction | §62-§70 | RESTORED |
| OriginDimensionAssessment has exact candidate/claim/contradiction references | §101 | RESTORED |
| Same-origin conflict carries actual `conflict_strength` | §102-§105 | RESTORED |
| Supporting internal conflict can be overridden by clean strong claim only with contradiction + support cap | §105 | RESTORED |
| Strong internal conflict remains decisive | §105 | RESTORED |
| HIGH support forbids any incompatible supporting claim, including same-origin | §107, T-04 | RESTORED |
| Recovery does not imply delayed interval completeness | §45-§47, F-B2 | RESTORED conservatively; `covered_delayed` removed |
| Source-health cleanup does not parse BindingTimeline | §49, F-B3 | RESTORED as Task-01-native margin contract |
| Task-01 v1→v2 migration is explicit deployment work | §13-§14, F-A1 | RESTORED |
| Old binary rollback after schema migration is explicit and may require old DB restore | §14 | RESTORED |
| Single long read transaction requires WAL/query-plan performance proof | §38, F-A4 | RESTORED |
| Empty watermark is generation + sequence 0 | §18, F-A2 | RESTORED |
| SourceEvaluability interval arrays have canonical normal form | §53-§54, T-02 | RESTORED |
| Controlled ground truth is recorded before viewing result | §122, T-09 | RESTORED |
| Validation failure creates new reviewed artifacts; no result-driven mutation | §121-§122 | RESTORED |
| Task-04 excludes UI/public API/Auth/cross-MAC identity | §5 | RESTORED |
| External source governance preserves full license/provenance obligations | §78, F-E1/F-E2/F-E4/F-E5 | RESTORED |
| Legacy K2B has explicit claim-strength ceiling and caveats | §89, F-E2 | RESTORED |
| Mandatory K1/K2B/K3/K4 failure paths are symmetric; no placeholders | §85, F-E1-§F-E4 | RESTORED |
| SnapshotRecord is retained while referenced | §27, §118-§120, T-07 | RESTORED |
| Active artifact pointers switch atomically; in-flight operations remain pinned | §11, §83, §113, F-F5 | RESTORED |

No restored guard above may be removed in a later rewrite without:

```text
explicit preservation-matrix entry

material reason

TechLead11 review

Owner decision where material
```

---

# APPENDIX C — All immutable artifact types + identity rules

Unless explicitly marked otherwise, every semantic/audit artifact below uses:

```text
ArtifactContent
+
ArtifactCanonicalJsonV1
+
SHA-256 content identity
+
separate ArtifactRegistration
```

| Artifact type | Identity / canonical payload source | Retention / activation rule |
|---|---|---|
| ArchitectureContractReference | architecture contract identifier + accepted Markdown file SHA-256 | Retain while any FoundationAdmissionManifest references it |
| Task01SchemaMigrationContract | accepted migration semantic contract | Retain as foundation governance/audit |
| Task01WatermarkReadContract | watermark/read-transaction semantic contract | Retain while foundation/classifications depend on it |
| Task01GenerationRecoveryContract | generation/recovery semantic contract | Retain as operational foundation contract |
| Task01HealthRetentionContract | evidence retention + derived health-anchor margin contract | Retain while active Task-01 foundation uses it |
| EvidenceSourceBindingTimeline | ordered binding epochs | Immutable; atomic active pointer; retain while referenced |
| BindingClockPolicy | clock domains + measured guard contract | Immutable; active pointer; retain while referenced |
| SourceHealthPolicy | heartbeat/reason/coverage/backfill/retention-margin semantics | Immutable; active pointer; retain while referenced |
| SnapshotContentPolicy | deterministic row/materialized-byte ceilings | Immutable; active pointer; SnapshotRecord pins accepted identity |
| SnapshotExecutionPolicy | operational timeout/busy/memory/retry contract | Immutable operational artifact; SnapshotRecord pins version/ID; changing it does not change pure classification result semantics |
| EvidenceSchemaRegistryContract | exact normalized schema validators/version registry | Immutable; active foundation artifact; EvidenceSnapshotContent pins it |
| EvidenceAdapterContractSet | exact classification compatibility/adapters/quality/dedup contracts | Immutable; atomic active pointer; request/classifier identity references it |
| ClassificationTaxonomy | platform/device/manufacturer/model canonical taxonomy | Immutable; KnowledgeBundle/ClassificationPolicy reference it |
| AliasMapping | explicit canonical manufacturer/model/source aliases | Immutable; KnowledgeBundle references it |
| K3PortalRuleSet | internal normalized-portal rule set and test vectors | Immutable; KnowledgeBundle references it |
| KnowledgeFreshnessPolicy | external source fresh/stale/expired contract | Immutable; retain while bundle/classification references it |
| SourceGovernanceRecord | full external license/provenance/governance contract | Immutable; retain while any bundle/source provenance references it |
| KnowledgeProvenanceManifest | external/internal provenance union | Immutable; every canonical knowledge claim references it through bundle |
| KnowledgeBundle | taxonomy/aliases/provenance/governance/freshness/canonical knowledge record set | Immutable; atomic active pointer; retain while referenced |
| ClassificationPolicy | pure fusion/claim/support/status semantics only | Immutable; atomic active pointer; request pins once |
| ClassificationRetentionPolicy | classification history/privacy/GC semantics | Immutable; persistence record references it; not pure classifier input |
| ProductValidationPolicy | controlled safety/utility/ground-truth-before-result rules | Immutable; gate acceptance reference; not pure classifier input |
| ClassifierArtifactManifest | exact code/tree/adapter/K2A/canonicalizer/build identity | Immutable; request pins once; retain while referenced |
| EvidenceSnapshotContent | watermark/bindings/metadata/payload digests/health descriptors/dependency refs | Durable; retain while classification references it |
| SnapshotRecord | capture timestamp + snapshot/policy refs + bounded build audit | Durable ArtifactContent; retain while classification references it |
| SourceEvaluability | canonical normalized coverage partitions | Durable; retain for Level-B audit |
| OriginAssessment | canonical per-origin dimension/candidate/conflict/provenance assessment | Durable; retain for Level-B audit |
| ClassificationRequestManifest | exact pure input artifact refs + knowledge evaluation time | Durable; retain with classification |
| ClassificationResult | pure semantic dimension/global result + OriginAssessment refs | Durable; retain with classification |
| GateResultManifest | machine-identifiable gate status/input/output/evidence/proof refs | Retain as Foundation/Task-04 acceptance evidence |
| FoundationAdmissionManifest | exact architecture/foundation/gate/runtime artifact set | Retain permanently for every classification lineage that references it |
| Task04AcceptanceManifest | exact Foundation manifest + classifier candidate + Task-04 gate set | Retain for accepted Task-04 lineage |
| K2AConformancePackage | pinned p0f oracle/corpus/adapter comparison semantic manifest | Immutable proof artifact; FoundationAdmissionManifest references accepted version |
| TTLCapturePlacementProof | exact capture topology + controlled TTL proof manifest | Immutable proof artifact; invalidate/replace when capture topology changes |
| SnapshotConcurrencyProof | concurrent insert/delete/checkpoint proof manifest | Immutable Foundation proof artifact |
| FoundationActivationProof | active-pointer/pinning/rollback proof manifest | Immutable Foundation proof artifact |
| Task04 execution proof artifacts (`*ExecutionProof`, `*DeterminismProof`, `*ValidationProof`, etc.) | canonical proof summary + retained evidence SHA refs | GateResultManifest references them |
| ArtifactRegistration | separate audit registration identified by canonical lowercase UUIDv4 | May differ for identical ArtifactContent; registration data never changes semantic artifact ID |
| EvidenceSnapshotMaterialization | **NOT ArtifactContent; transient only** | Never retained in classification history; disposed after request execution |
| Retained evidence files | raw/sanitized proof files identified by SHA-256 in GateResultManifest | Retention follows gate/audit policy; not automatically runtime ArtifactContent |

Universal rule:

```text
same semantic ArtifactContent bytes
→ same artifact_id

different semantic ArtifactContent bytes
→ different artifact_id

review/created_at/created_by differences
→ different ArtifactRegistration
NOT different semantic ArtifactContent
```

---

# APPENDIX D — Foundation gate → output artifact dependency graph

```text
R7 FINAL ArchitectureContractReference
    |
    +--> F-A1
    |     ├─ Task01SchemaMigrationContract
    |     └─ Task01WatermarkReadContract
    |            |
    |            +--> F-A2
    |            |     └─ Task01GenerationRecoveryContract
    |            |
    |            +--> F-A3
    |                  └─ SnapshotConcurrencyProof
    |
    +--> F-A5
    |     └─ EvidenceSchemaRegistryContract
    |            |
    |            +-------------------+
    |                                |
    +--> F-A3 ----------------> F-A4 |
    |                         + F-A5 |
    |                                v
    |                         SnapshotContentPolicy
    |                         SnapshotExecutionPolicy
    |
    +--> F-B1
    |     ├─ EvidenceSourceBindingTimeline
    |     └─ BindingClockPolicy
    |
    +--> F-B2
    |     └─ SourceHealthPolicy
    |            |
    |            +--> F-B3
    |                  └─ Task01HealthRetentionContract
    |
    +--> F-C1
    |     └─ tcp_syn/2 SchemaContract
    |            |
    |            +--> F-C2
    |            |     └─ K2AConformancePackage
    |            |            |
    |            |            +--> F-E2 K2B admission
    |            |
    |            +--> F-C3
    |                  └─ TTLCapturePlacementProof
    |
    +--> F-D1
    |     └─ portal_headers/2 SchemaContract
    |        OR explicit NOT-ADMITTED result
    |
    +--> F-E1
    |     └─ K1 provenance + canonical K1 records
    |
    +--> F-E2
    |     └─ K2B provenance + canonical TCP records
    |
    +--> F-E3
    |     ├─ K3PortalRuleSet
    |     └─ internal KnowledgeProvenanceManifest
    |
    +--> F-E4
    |     └─ K4 provenance + canonical IEEE records
    |
    +--> F-E5
    |     ├─ SourceGovernanceRecords
    |     └─ KnowledgeFreshnessPolicies
    |
    +--> F-E6
    |     ├─ ClassificationTaxonomy
    |     └─ AliasMapping
    |
    +--> F-E1/F-E2/F-E3/F-E4/F-E5/F-E6
    |           |
    |           v
    |         F-E7
    |           └─ KnowledgeBundle
    |
    +--> F-C1 + F-D1 + F-A5 + existing evidence schemas
    |           |
    |           v
    |         F-F1
    |           └─ EvidenceAdapterContractSet
    |
    +--> ClassificationTaxonomy
    |    + EvidenceAdapterContractSet
    |    + R7 fusion contracts
    |           |
    |           v
    |         F-F2
    |           └─ ClassificationPolicy
    |
    +--> F-F3
    |     └─ ClassificationRetentionPolicy
    |
    +--> F-F4
    |     └─ ProductValidationPolicy
    |
    +--> accepted active artifacts
          |
          v
        F-F5
          └─ FoundationActivationProof

ALL mandatory GateResultManifests
+ exact foundation commit/tree
+ all accepted artifacts above
        |
        v
      F-ADMIT
        |
        └─ FoundationAdmissionManifest
              |
              v
      TechLead11 may decompose Task-04
```

Dependency note:

```text
F-A4 sizing MUST consume F-A5's exact payload/schema materialization rules
so actual normalized payload bytes are included in capacity measurement.
```

No Foundation edge points to a Task-04 implementation output.

---

# APPENDIX E — Task-04 acceptance gate → output artifact dependency graph

```text
FoundationAdmissionManifest
        |
        +--> implemented snapshot/materialization
        |       |
        |       v
        |      T-01
        |       └─ SnapshotMaterializationExecutionProof
        |
        +--> SourceHealthPolicy + snapshot
        |       |
        |       v
        |      T-02
        |       ├─ SourceEvaluability artifacts
        |       └─ SourceEvaluabilityExecutionProof
        |
        +--> T-01 + T-02
        |    + KnowledgeBundle
        |    + EvidenceAdapterContractSet
        |       |
        |       v
        |      T-03
        |       ├─ OriginAssessment artifacts
        |       └─ OriginAssessmentExecutionProof
        |
        +--> T-03 + ClassificationPolicy
        |       |
        |       v
        |      T-04
        |       └─ FusionExecutionProof
        |
        +--> pinned request assembly
        |    + T-04
        |       |
        |       v
        |      T-05
        |       └─ RequestAssemblyDeterminismProof
        |
        +--> exact implementation candidate
        |       |
        |       v
        |      T-06
        |       └─ ClassifierArtifactManifest
        |
        +--> T-01..T-06
        |    + ClassificationRetentionPolicy
        |       |
        |       v
        |      T-07
        |       └─ ClassificationAuditPersistenceProof
        |
        +--> exact accepted candidate
        |       |
        |       v
        |      T-08
        |       └─ OfflineFailureIsolationProof
        |
        +--> T-06 + T-07 + T-08
        |    + ProductValidationPolicy
        |       |
        |       v
        |      T-09
        |       └─ Task04ProductValidationProof
        |
        +--> all mandatory T GateResultManifests
                |
                v
             T-ACCEPT
                |
                └─ Task04AcceptanceManifest
```

Task-04 code exists before T-gates execute.

No T-gate is a prerequisite for Task-04 decomposition.

---

# APPENDIX F — No-silent-fallback / stop-condition matrix

| Condition | Required action | Forbidden fallback | Result class |
|---|---|---|---|
| Architecture not Owner+TechLead accepted | Keep PRE-TASK implementation unauthorized | Treat draft as FINAL | Architecture HOLD |
| Foundation mandatory gate FAIL | Foundation Admission blocked | Skip gate / prose-only PASS | Foundation HOLD |
| Mandatory K1 source FAIL | Find another concrete compliant K1 | First row / hand-written guesses / weaker contract | Foundation HOLD |
| Mandatory K2B source FAIL | Find another concrete compliant K2B | Use oracle as production truth automatically | Foundation HOLD |
| Mandatory K3 rules FAIL | Correct/new internal rule set | Raw UA parsing / empty placeholder | Foundation HOLD |
| Mandatory K4 source FAIL | Find another concrete compliant K4 | OUI-only automatic manufacturer guess | Foundation HOLD |
| Unknown material external license restriction | Source not admitted | Assume permitted | Knowledge admission FAIL |
| External freshness policy unresolved | Source not admitted as mandatory runtime source | Invent age threshold | Knowledge admission FAIL |
| Task-01 migration validation FAIL | Keep writer stopped; restore/repair | Activate partially migrated DB | Migration FAIL |
| Pre-v2 app rollback requested after v2 migration | Restore compatible pre-migration DB under explicit recovery decision | Run strict old code on unproven v2 schema | Controlled rollback |
| Sequence allocator exhausted | Stop new classification-relevant ingest | Wrap/reuse/negative sequence | Fatal storage condition |
| Arbitrary rollback not detectable | Require operational generation recovery when rollback known | Claim automatic detection | Recovery contract |
| Snapshot opens second DB transaction/page connection | Fail implementation/gate | Continue with approximate consistency | Snapshot FAIL |
| Concurrent retention changes active-reader membership | Gate FAIL | Accept skipped page rows | Snapshot consistency FAIL |
| payload_json parse fails | Snapshot build fail | Ignore row and classify remainder silently | No ClassificationResult |
| Duplicate JSON key found | Snapshot build fail | Last-key-wins parse | No ClassificationResult |
| Canonical payload bytes differ from stored payload_json | Snapshot build fail | Recanonicalize silently and continue | No ClassificationResult |
| Payload SHA mismatch | Snapshot build fail | Trust either bytes or hash | No ClassificationResult |
| Unknown evidence schema | No semantic materialization/claim; explicit unsupported contract | Parse nearest known schema | Safe no-claim / insufficient |
| Deterministic content ceiling exceeded | No ClassificationResult | Classify first N rows | `resource_limited` build result |
| Operational timeout / CPU / memory / SQLite transient | Retryable/non-semantic build failure | Convert to device `unknown/not_evaluable` | No ClassificationResult |
| No authoritative binding | Reject/classification window invalid or unknown per explicit boundary | Infer producer from rows | Snapshot/binding failure |
| Binding cutover quarantine | Exclude ambiguous rows; coverage unknown | Assign to nearest epoch | Explicit cutover ambiguity |
| Source health reason unknown | Coverage unknown | Assume available/unavailable | SourceEvaluability unknown |
| Transport recovers | Use actual backfilled rows only; completeness remains unproven | Mark interval covered_delayed | Conservative coverage |
| Health backfill older than Task-01 delayed limit | Do not fabricate old health row | Bypass Task-01 age validation | Coverage remains unknown |
| Present valid evidence + health unavailable/unknown | Evidence may still be used; inconsistency/coverage recorded | Discard valid present evidence | Claim + coverage explanation |
| Missing evidence + source outage | No claim | Treat as negative device signal | No negative evidence |
| tcp_syn/1 encountered | Audit/non-fusion | Approximate tcp_syn/2 | No TCP V1 claim |
| Malformed-but-observable TCP option | Preserve bounded facts | Drop complete packet | tcp_syn/2 evidence |
| Physical packet/header truncation | No tcp_syn/2 event | Fabricate missing bytes | Parser reject |
| JA4 observed without admitted reference knowledge | TLS/QUIC no semantic claim | Apple-like/Android-like/frequency heuristic | No claim |
| Fingerbank Cloud path attempted in V1 | Block/FAIL scope check | Submit production client data | Scope violation |
| K1 returns multiple candidates | Preserve CandidateSet/project per dimension | Pick first/best/popular | Ambiguous/resolved by dimension |
| K1 upstream mapping provenance multi-origin/unknown | Exclude from DHCP fusion | Treat as DHCP-only | Knowledge non-admission |
| Client Hint says mobile | Preserve normalized fact only | Smartphone claim automatically | No device-class shortcut |
| Declared claim conflicts with deterministic mapping | Compare claim_strength only | Declared always wins | Strength matrix |
| Strong internal conflict | Final decisive conflict | Let other clean strong origin erase it | `conflicting_evidence` |
| Supporting internal conflict + clean strong claim | Strong may resolve; contradiction retained; cap medium | Blanket global conflict OR ignore contradiction | Resolved with cap |
| Any incompatible supporting claim exists | HIGH forbidden | HIGH despite contradiction | Max medium |
| Expired external knowledge source | Suppress that source claims | Keep old strength OR crash classifier | Degraded knowledge availability |
| Live caller supplies/backdates knowledge time | Ignore/reject; service owns trusted time | Caller-selected freshness | Request assembly FAIL |
| Negative knowledge source age | Fail request assembly | Treat source as fresh | No ClassificationResult |
| Active pointer changes mid-request | Continue with pinned IDs | Re-read and mix versions | Stable request |
| Snapshot materialization completed | Dispose transient payload copy after use | Retain payload in classification DB | Privacy boundary |
| Classification persistence loses referenced SnapshotRecord | Gate/runtime FAIL | Keep dangling ID | Audit failure |
| Validation ground truth not pre-recorded | Validation run invalid | Label after seeing result | Product gate FAIL |
| Validation finds wrong resolved result | Candidate FAIL, correct artifacts, rerun | Auto-train/mutate live knowledge | Product gate FAIL |
| Always-unknown classifier | Utility gate FAIL | Treat as safe PASS | Product gate FAIL |
| Classification subsystem fails | Isolate from Auth/CAPPORT/Task-01 | Block Authorization | Failure isolation |
| Public/UI feature proposed inside Task-04 | Separate task/architecture | Scope creep | Out of scope |

---

# End of R7

R7 is intentionally a review candidate, not FINAL.

All future rewrite/revision work MUST update:

```text
Appendix A preservation/regression matrix
+
Appendix B restored-guard matrix
```

so that no accepted guard disappears silently.
