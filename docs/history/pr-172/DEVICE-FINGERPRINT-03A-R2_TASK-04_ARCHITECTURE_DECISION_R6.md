# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R6

## Deterministic Passive Classification Foundation and Task-04 Lifecycle Contract

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-16  
**Status:** `FOR OWNER + TECHLEAD11 STRICT REVIEW`  
**Architecture Contract Final:** `NO`  
**Task-04:** `HOLD`  
**Task-04 Coder Task:** `NO`  
**Production change from this document alone:** `NO`

---

# 1. Document disposition

This document is the complete authoritative R6 architecture candidate for the Device Fingerprint pre-Task-04 foundation and Task-04 classification architecture.

It is standalone. No earlier revision is required to interpret or implement any R6 contract.

```text
R5 = SUPERSEDED

R6 = FOR OWNER + TECHLEAD11 STRICT REVIEW

ARCHITECTURE CONTRACT FINAL = NO

TASK-04 = HOLD

NO TASK-04 CODER TASK

NO PRODUCTION CHANGE FROM THIS DOCUMENT ALONE
```

Only explicit:

```text
OWNER ACCEPT
+
TECHLEAD11 ACCEPT
```

may promote this architecture contract to `FINAL`.

After architectural acceptance, bounded PRE-TASK foundation implementation may begin only through separate TechLead tasks and Owner authorization.

Task-04 itself remains HOLD until Foundation Admission gates defined in this document pass.

---

# 2. Owner quality policy

R6 is governed by the following quality policy:

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
```

The objective is not to finish architecture review quickly.

The objective is to close the foundation cleanly enough that later Task-04 implementation does not inherit known architectural debt.

---

# 3. Verified repository baseline

R6 was prepared against the verified repository state:

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

Current Task-01 evidence rows contain classification-relevant metadata including:

```text
evidence_id
producer_id
source_event_id
source_kind
source_subtype
extractor_name
extractor_version
feature_schema_version
rule_version
site_id
capture_source_id
observed_at
observed_mac
observed_ip
privacy_class
quality_state
payload_sha256
ingested_at
```

Current Task-01 source-health rows contain:

```text
source_health_id
producer_id
source_health_event_id
site_id
capture_source_id
source_kind
status
reason_code
observed_at
content_sha256
ingested_at
```

Current persisted source-health status values are exactly:

```text
available
unavailable
unsupported
```

Current Task-01 read API is cursor-paginated with maximum page size 500.

Current Task-01 configuration has, by default:

```text
evidence retention =
30 days

maximum future event clock skew =
120 seconds

maximum delayed event age =
86400 seconds
```

Current network fingerprint sensor source-health heartbeat cadence is 300 seconds for:

```text
dhcp
tcp_syn
tls_client
quic_client
```

Current portal producer does not yet provide an equivalent idle periodic liveness heartbeat.

---

# 4. Exact Task-03A status

Canonical truth:

```text
TASK-DEVICE-FINGERPRINT-03A
TOOLING / RESEARCH FOUNDATION =
IMPLEMENTED / AVAILABLE
```

This means the repository contains the controlled labeled-evidence matrix tooling and research foundation.

It does NOT mean:

```text
old 12-device / 48-sample empirical campaign completed
```

Canonical:

```text
old 12-device / 48-sample matrix campaign =
NOT REQUIRED
NOT TASK-04 BLOCKER

full historical physical matrix campaign =
NOT CLAIMED COMPLETED
```

No roadmap or acceptance statement may conflate research tooling availability with completion of a large physical-device campaign.

---

# 5. Permanent architecture principles

The following are permanent R6 invariants:

```text
normalized evidence
!= classification
!= device identity proof

classification is advisory

classification does not affect Authorization

classification does not affect CAPPORT admission

classification does not become a security identity signal

support level
!= statistical probability

row count
!= independent corroboration

same origin interpreted by multiple knowledge systems
!= multiple independent origins

raw packets are non-durable

raw User-Agent is non-durable

raw Client Hints are non-durable

no cross-MAC identity merge

unknown is valid

insufficient_evidence is valid

conflicting_evidence is valid

recognized_out_of_scope is valid where dimensionally defined

Task-01 evidence storage
!= Task-04 classification storage

external vendor artifact
!= runtime schema

runtime classifier requires no Internet

snapshot membership is explicit and deterministic

source coverage
!= validity of an already-present normalized evidence row

knowledge freshness is an explicit classifier input

classification meaning is versioned

pure classification core performs no I/O and reads no wall clock

every retained classification keeps retrievable immutable inputs required for audit
```

---

# 6. Lifecycle — no gate deadlock

R6 separates architecture review, PRE-TASK foundation admission, and Task-04 implementation acceptance.

The exact lifecycle is:

```text
R6 architecture candidate
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

Therefore:

```text
architecture-review Coder HOLD
```

does NOT mean:

```text
foundation implementation Coder HOLD forever
```

Before architecture acceptance:

```text
CODER = HOLD
```

After architecture acceptance:

```text
PRE-TASK Coder work =
allowed only under separate TechLead tasks + Owner authorization
```

Task-04 remains HOLD until Foundation Admission.

---

# 7. PRE-TASK foundation scope

PRE-TASK foundation work may implement only architecture required before a classifier can be decomposed safely:

```text
Task-01 immutable ingest watermark
Task-01 complete snapshot read transaction
Task-01 health-anchor retention
database generation / recovery contract

EvidenceSourceBindingTimeline
BindingClockPolicy
classification_foundation_valid_from_utc

SourceHealthPolicy
portal heartbeat/liveness
coverage semantics

tcp_syn/2
p0f runtime/conformance foundation
TTL/RSPAN proof

bounded portal Client Hints experiment

external knowledge inspection/importers
KnowledgeBundle construction/activation
taxonomy/aliases
knowledge freshness policies

EvidenceAdapterContract artifacts

SnapshotContentPolicy
SnapshotExecutionPolicy

ClassificationPolicy contract
ClassificationRetentionPolicy
ProductValidationPolicy
```

PRE-TASK work does NOT implement:

```text
Task-04 OriginAssessment engine
Task-04 fusion engine
Task-04 ClassificationResult engine
Task-04 classification persistence service
Task-04 product classification API
```

Those belong to Task-04 after Foundation Admission.

---

# 8. Universal immutable artifact convention

R6 defines one canonical immutable artifact convention.

Every immutable artifact covered by this convention is stored as:

```text
artifact_type
artifact_schema_version
artifact_id
artifact_metadata
payload
content_sha256
```

Canonical digest input is the UTF-8 JSON object:

```json
{
  "artifact_type": "...",
  "artifact_schema_version": 1,
  "payload": {}
}
```

Digest:

```text
content_sha256 =
SHA-256(canonical UTF-8 JSON digest input)
```

Canonical JSON rules:

```text
UTF-8

object keys sorted lexicographically

arrays ordered exactly as required by that artifact contract

no insignificant whitespace

no NaN / Infinity

all timestamps canonical UTC

content_sha256 excluded from its own digest

artifact_id excluded from its own digest

artifact_metadata excluded from semantic content digest
```

`artifact_metadata` may contain non-semantic audit information such as:

```text
created_at_utc
created_by
review reference
```

Changing only artifact metadata does not change semantic content identity.

Canonical artifact ID:

```text
<artifact_type>:v<artifact_schema_version>:sha256:<content_sha256>
```

An immutable artifact is never edited in place.

A semantic change creates a new payload, digest and artifact ID.

This convention applies to at least:

```text
KnowledgeBundle

ClassificationPolicy

SourceHealthPolicy

SnapshotContentPolicy

EvidenceSourceBindingTimeline

BindingClockPolicy

EvidenceAdapterContractSet

ClassifierArtifactManifest

SourceEvaluability

OriginAssessment

ClassificationRequestManifest

semantic ClassificationResult
```

A documented artifact-specific exception requires a future architecture revision.

---

# 9. Task-01 global ingest sequence

Task-01 SHALL gain one explicit classification-relevant ingestion order shared by:

```text
device_fingerprint_evidence

device_fingerprint_source_health_events
```

Each successfully inserted classification-relevant row receives:

```text
ingest_sequence
```

Domain:

```text
signed 64-bit positive integer

minimum = 1

maximum = 9223372036854775807
```

Properties:

```text
monotonic within one valid database generation

assigned by Task-01 storage owner

never derived from UUID

never derived from SQLite rowid

never derived from wall clock

never reused after successful commit in the same valid generation
```

Allocator exhaustion:

```text
FAIL CLOSED

no wrap

no new classification-relevant ingest

explicit fatal storage/ingest condition
```

---

# 10. Ingest allocation transaction

Sequence allocation and row insertion occur in the SAME SQLite write transaction.

Conceptually:

```text
BEGIN IMMEDIATE / equivalent serialized writer transaction

validate request

resolve idempotent duplicates

reject conflicting duplicates

allocate sequence values for new semantic rows

insert evidence and/or source-health rows

advance committed allocator state

COMMIT
```

Required invariant:

```text
reader-visible committed watermark W
means no uncommitted classification-relevant row
with sequence <= W remains hidden
```

A rollback rolls back both inserted rows and sequence-state changes made by that transaction.

---

# 11. Duplicate semantics

Task-01 duplicate behavior is part of the ingest-sequence contract.

## Identical idempotent duplicate

If the producer/event identity already exists and the new request is semantically identical under the Task-01 duplicate contract:

```text
no new semantic row

no new ingest_sequence

idempotent success / duplicate-noop
```

## Conflicting duplicate

If the same unique producer/event identity attempts to submit semantically different content:

```text
transaction = ROLLBACK

no conflicting row admitted

no successful sequence advancement from the rolled-back transaction
```

No "latest duplicate wins".

---

# 12. Sequence gaps and cleanup

R6 does not require sequence values to be contiguous.

If an implementation legitimately produces a gap:

```text
gap has no semantic meaning
```

Watermark logic never assumes every integer exists.

Retention DELETE:

```text
does not advance ingest_sequence

does not reuse old sequence values

does not lower committed sequence state
```

---

# 13. Database generation

A Task-01 classification-capable database has one active:

```text
database_generation_id
```

The generation identifies the current sequence namespace/rebaseline.

A watermark is:

```text
database_generation_id
+
max_committed_ingest_sequence
```

The generation is not claimed to be an automatic detector of arbitrary filesystem rollback.

---

# 14. Initial watermark migration

The current database predates `ingest_sequence`.

PRE-TASK migration therefore runs under an exclusive controlled migration boundary.

It SHALL:

```text
mint a new database_generation_id

assign deterministic bootstrap ingest_sequence values
to all retained classification-relevant evidence and health rows

initialize allocator state above the highest assigned value

prevent writer ingestion until migration commits completely
```

Bootstrap order is deterministic and documented.

Bootstrap order is NOT claimed to reconstruct original historical commit order.

After migration:

```text
all retained rows belong to the new active generation
```

No Task-04 live classification is valid before the resulting foundation activation boundary defined later.

---

# 15. Controlled restore / rollback recovery

Any controlled operation capable of moving Task-01 sequence state backward, including:

```text
database backup restore

VM snapshot rollback

filesystem rollback

database rebuild from older material
```

MUST trigger a generation recovery procedure BEFORE the writer accepts new ingestion.

The recovery procedure SHALL:

```text
stop the Task-01 writer

open the restored/rebuilt DB exclusively

mint a NEW database_generation_id

deterministically rebaseline ALL retained classification-relevant evidence
and source-health rows into the new generation

assign fresh monotonic ingest_sequence values

set allocator state above the highest assigned value

validate uniqueness and indexes

commit

only then permit writer startup
```

Evidence IDs, health IDs and payload/content digests remain unchanged where the underlying rows are unchanged.

The rebaseline does NOT claim historical commit order.

Old snapshot manifests continue to identify the old generation and remain valid audit artifacts.

They may no longer be reconstructable from the newly rebaselined Task-01 DB after restore.

---

# 16. Restore limitation

An arbitrary external rollback that restores:

```text
database
+
generation state
+
all local guards
```

to an older image may be indistinguishable to the application from a legitimate older machine state.

R6 does NOT claim impossible automatic detection.

Operational invariant:

```text
any known or controlled rollback that may move sequence state backward
MUST execute the generation recovery procedure before writer restart
```

Violation is an infrastructure/recovery contract violation and invalidates subsequent ingest-watermark guarantees until repaired.

---

# 17. Immutable ingest watermark

Canonical watermark:

```text
IngestWatermark {
    database_generation_id
    max_committed_ingest_sequence
}
```

Meaning:

```text
all classification-relevant committed rows
with ingest_sequence <= W
that exist in the active SQLite read snapshot
belong to the watermark-visible row universe
```

Watermark freezes insertion visibility.

SQLite read transaction freezes concurrent mutation visibility during one snapshot build.

Both are required.

---

# 18. One SQLite read transaction per EvidenceSnapshot

Canonical live snapshot construction uses exactly one read-only SQLite connection and one SQLite read transaction for the entire Task-01 row-universe build.

Conceptually:

```text
open read-only Task-01 connection

BEGIN READ TRANSACTION

establish SQLite read snapshot

read database_generation_id

read committed ingest watermark

read required evidence pages using the SAME connection

read required source-health pages using the SAME connection

read all predecessor/anchor health rows using the SAME connection

complete authorized row universe

COMMIT / ROLLBACK READ TRANSACTION
```

Forbidden:

```text
new connection per page

transaction restart between pages

watermark refresh during pagination

health read from a different SQLite snapshot
```

Concurrent:

```text
ingest

retention DELETE

WAL checkpoint
```

must not change the active reader's visible SQLite snapshot.

---

# 19. Snapshot transaction execution failure

The read transaction may have an operational maximum duration to protect the database.

If an operational timeout, SQLite busy/transient error, memory pressure, or equivalent execution failure occurs:

```text
snapshot build fails

transaction is closed

NO semantic EvidenceSnapshotContent is emitted

NO SourceEvaluability is emitted

NO ClassificationResult is emitted
```

This is a retryable/non-semantic service failure where appropriate.

It is NOT:

```text
resource_limited classification

not_evaluable origin

unknown device
```

for the same semantic input.

---

# 20. Live snapshot build mode

Normal lifecycle callers do NOT supply database watermark/generation.

Caller supplies only:

```text
site_id

observed_mac

window_start_utc

window_end_utc
```

The Snapshot Service itself:

```text
validates the completed window

pins the currently accepted EvidenceSourceBindingTimeline

pins the accepted SnapshotContentPolicy

opens the single SQLite read transaction

captures database generation

captures committed ingest watermark

captures central snapshot_captured_at_utc

builds authorized snapshot content
```

Ordinary callers cannot choose an older or future database generation boundary.

---

# 21. Replay mode

Replay/audit is separate.

Replay uses the exact stored:

```text
EvidenceSnapshotContent artifact/digest

database_generation_id

ingest watermark

window

binding timeline artifact/digest

SnapshotContentPolicy reference

stored request inputs
```

If Task-01 still contains all required source rows in the same database generation, Level-A reconstruction may be attempted using one read transaction and the exact watermark.

If those source rows have expired or a controlled restore rebaselined the database:

```text
DB reconstruction may be unavailable
```

The retained EvidenceSnapshotContent and downstream audit objects remain authoritative for Level-B replay.

---

# 22. Window validity

For V1 normal live completed-window classification:

```text
window_start_utc < window_end_utc

window_start_utc >= classification_foundation_valid_from_utc

window_end_utc <= snapshot_captured_at_utc
```

No live request may classify future event time.

No hidden "open current window" mode exists.

If a future lifecycle requires an explicitly open/current window:

```text
new explicit request mode
+
new semantics
+
architecture review
```

are required.

---

# 23. Snapshot capture time vs semantic identity

R6 separates:

```text
EvidenceSnapshotContent
```

from:

```text
SnapshotRecord
```

## EvidenceSnapshotContent

Contains only classification-semantic snapshot inputs.

Its digest does NOT include:

```text
snapshot_captured_at_utc
build duration
CPU timing
connection ID
retry counters
```

## SnapshotRecord

Service/audit record contains:

```text
snapshot_record_id
evidence_snapshot_content_id
evidence_snapshot_content_digest
snapshot_captured_at_utc
build/audit metadata
SnapshotExecutionPolicy reference
scope-anomaly summary
```

Two live builds that obtain identical semantic content under the same watermark/bindings may have different SnapshotRecord metadata but the same EvidenceSnapshotContent digest.

---

# 24. EvidenceSnapshotContent payload

Canonical semantic payload includes:

```text
snapshot_contract_version

site_id

observed_mac

window_start_utc

window_end_utc

database_generation_id

max_committed_ingest_sequence

source_binding_timeline_id
source_binding_timeline_digest

classification_foundation_valid_from_utc

ordered binding-epoch descriptors

ordered authorized evidence descriptors

ordered authorized source-health descriptors
```

It does NOT include unauthorized/rogue rows.

Scope anomalies are SnapshotRecord audit metadata and do not enter classification semantics.

---

# 25. Evidence descriptor

Every authorized evidence descriptor contains all metadata capable of affecting adapter eligibility/semantics:

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

`observed_ip` is NOT a Task-04 V1 classifier input.

A future proposal to classify from IP semantics requires separate architecture/privacy review.

---

# 26. Source-health descriptor

Every authorized health descriptor contains:

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

No classification-relevant health-semantic field is omitted from snapshot identity.

---

# 27. Canonical snapshot ordering

Evidence descriptors:

```text
origin_group
source_kind
capture_source_id
producer_id
observed_at
ingest_sequence
evidence_id
```

Source-health descriptors:

```text
origin_group
source_kind
capture_source_id
producer_id
observed_at
ingest_sequence
source_health_id
```

Binding epochs:

```text
effective_from_utc
origin_group
source_kind
capture_source_id
producer_id
binding_epoch_id
```

Pagination boundaries and SQLite incidental order cannot alter semantic ordering.

---

# 28. Complete pagination

Snapshot builder paginates each required Task-01 read deterministically to exhaustion.

Current Task-01 page-size ceiling is 500.

Forbidden:

```text
read first 500 rows
classify
ignore next_cursor
```

The one SQLite read transaction remains open across every page.

---

# 29. SnapshotContentPolicy vs SnapshotExecutionPolicy

R6 separates deterministic content ceilings from operational execution limits.

## SnapshotContentPolicy

Immutable semantic policy.

May contain:

```text
max_authorized_evidence_rows
max_authorized_health_rows
max_canonical_snapshot_input_bytes
other deterministic content-size ceilings
```

These depend only on snapshot content.

If exceeded:

```text
snapshot content status =
resource_limited

NO ClassificationResult
```

No partial input is classified.

Exact first production values are NOT guessed in architecture.

They are frozen by Foundation sizing proof.

## SnapshotExecutionPolicy

Operational service policy.

May contain:

```text
maximum read-transaction wall-clock duration

SQLite busy/retry policy

process memory guard

operational retry count
```

These are NOT semantic classifier inputs.

Execution-policy failure:

```text
retryable/non-semantic snapshot build failure

NO ClassificationResult
```

The same exact content may succeed on retry.

---

# 30. EvidenceSourceBindingTimeline

R6 defines one immutable deployment-side:

```text
EvidenceSourceBindingTimeline
```

It is NOT KnowledgeBundle content.

It covers Task-01 acquisition origins only:

```text
dhcp
portal
tcp
tls
quic
```

It explicitly EXCLUDES:

```text
mac_registry
```

because `mac_registry` uses the already-observed MAC plus local KnowledgeBundle and has no Task-01 producer, capture source or source-health heartbeat.

---

# 31. Binding epoch

Each V1 binding epoch contains:

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

Interval semantics:

```text
[effective_from_utc, effective_to_utc)
```

`effective_to_utc = null` is allowed only for the currently open epoch.

There is NO V1 `required` boolean.

Presence of an active binding means:

```text
this Task-01 source is expected for that interval
```

---

# 32. Exactly one authoritative binding in V1

For V1, at every non-quarantined event-time point there may be at most one authoritative binding for:

```text
(site_id, origin_group, source_kind)
```

Concurrent HA/redundant producers are NOT defined in V1.

No:

```text
all-of
any-of
active/passive
duplicate capture
health quorum
```

semantics exist.

If HA/redundant source capture is required later:

```text
new explicit architecture extension
```

is mandatory.

---

# 33. Binding-authorized row membership

A Task-01 row enters EvidenceSnapshotContent only when:

```text
site_id matches request

observed_mac matches request for evidence rows

source_kind maps to the expected origin

producer_id matches the applicable binding epoch

capture_source_id matches the applicable binding epoch

observed_at lies inside the epoch's accepted event-time interval

ingest_sequence <= captured watermark
```

Same rule applies to health rows except there is no observed_mac condition.

Rows from:

```text
wrong producer

wrong capture source

expired old binding

unexpected new binding
```

are excluded from semantic snapshot input.

They are recorded only as bounded scope anomalies in SnapshotRecord/telemetry.

---

# 34. BindingClockPolicy

Binding authority uses producer event time, therefore binding cutovers require a clock-domain contract.

R6 defines immutable:

```text
BindingClockPolicy
```

with at least:

```text
policy ID/digest

producer clock-domain identities

Task-01 clock-domain identity

measured/proven maximum relevant clock offset

cutover_guard_seconds

proof basis
```

Exact `cutover_guard_seconds` is Foundation-proofed, not guessed.

At a binding transition at `T`:

```text
[T - guard, T + guard)
```

is the cutover quarantine interval unless Foundation proof allows guard = 0.

Rows whose `observed_at` lies inside this cutover quarantine:

```text
are not silently assigned to old or new producer

are excluded from fusion

are recorded as binding_cutover_ambiguous

produce unknown coverage for that interval
```

No Task-01 future-skew setting is treated as proof of pairwise producer cutover accuracy.

---

# 35. Classification foundation valid-from

R6 chooses a clean V1 historical boundary instead of inventing retroactive source authority.

Foundation Admission SHALL freeze:

```text
classification_foundation_valid_from_utc = T
```

`T` is no earlier than the point where:

```text
watermark-capable Task-01 generation is active

accepted BindingTimeline is active

BindingClockPolicy is proven

required source-health baseline/heartbeat state can begin

accepted EvidenceAdapter contracts are known
```

Task-04 refuses:

```text
window_start_utc < T
```

Older retained Task-01 evidence remains valid repository data/research evidence but is not implicitly granted Task-04 source authority.

---

# 36. Source-health is coverage evidence

Task-01 source-health does NOT directly mean device evidence exists or does not exist.

Health describes:

```text
source capability
acquisition state
delivery state
coverage/completeness confidence
```

It must never transform absence into a negative fingerprint claim.

---

# 37. SourceHealthPolicy

Each Task-01 source family uses immutable:

```text
SourceHealthPolicy
```

It contains, per producer/source contract:

```text
expected heartbeat behavior

freshness rule

Task-01 timestamp/skew contract reference

delayed-event contract reference

reason_code mapping

delivery guarantee classification

coverage reconstruction rules

backfill rules

health-anchor retention requirement
```

Exact freshness/grace values are proven from actual producer behavior.

No unproven fixed freshness multiplier is canonical.

---

# 38. Failure-domain / coverage classes

SourceHealthPolicy maps:

```text
producer/source identity
+
persisted status
+
reason_code
+
proven producer delivery guarantees
```

to one of these V1 coverage classes:

```text
covered_available

covered_delayed

acquisition_unavailable

delivery_pending_lossless

delivery_loss_possible

delivery_loss_confirmed

unsupported

unknown
```

Definitions:

## covered_available

Source acquisition and central delivery are known healthy for the interval.

## covered_delayed

A previously impaired delivery interval is now known complete because:

```text
producer contract is proven lossless for the bounded outage
AND
backlog drain completed
AND
recovery health semantics prove completion
```

## acquisition_unavailable

Source could not acquire the target evidence during the interval.

## delivery_pending_lossless

Acquisition may continue and producer guarantees bounded lossless spool, but at this snapshot watermark all delayed rows are not yet proven centrally complete.

## delivery_loss_possible

Delivery path failed and the producer contract cannot prove all evidence was preserved.

## delivery_loss_confirmed

Known evidence loss occurred.

## unsupported

Intentional source capability state.

## unknown

Coverage cannot be established conservatively.

Unknown `reason_code` or unproven producer guarantee maps to:

```text
unknown
```

not a guessed stronger state.

---

# 39. Transport failure truth

If acquisition component fails while Task-01 transport remains functional:

```text
producer may deliver live unavailable health
```

If producer→Task-01 transport itself fails:

```text
central Task-01 cannot receive a live unavailable event over that failed path
```

Therefore:

```text
last heartbeat eventually loses freshness
→ central coverage becomes unknown
```

On recovery, bounded historical health may be backfilled only when the producer reliably knows the historical interval and Task-01 delayed-event rules still permit ingestion.

---

# 40. Health backfill delayed-event limit

Historical source-health backfill is subject to the active Task-01 delayed-event contract.

If an outage start lies outside the admissible delayed-event horizon:

```text
do not fabricate a deliverable old source-health event

central historical interval remains conservatively unknown
```

No bypass exists solely for classification convenience.

---

# 41. Source-health predecessor anchor retention

Health reconstruction may require the latest eligible health event before a classification window or binding segment.

Therefore health cleanup SHALL preserve a predecessor anchor required by retained classification-eligible evidence.

Canonical cleanup invariant:

For every binding epoch intersecting the current classification-eligible evidence-retention horizon:

```text
preserve the latest authorized source-health event
at or before the earliest still-classification-eligible point
for that epoch
```

even if that one anchor is older than the normal health-event cleanup horizon.

Also preserve health transitions/heartbeats required inside retained classification windows.

The anchor remains until no retained classification-eligible evidence window can require it.

This avoids:

```text
evidence still retained
but health predecessor deleted
→ false unknown at window start
```

---

# 42. Health state does not cross binding epoch

At a new binding epoch:

```text
old producer health state is not inherited
```

The new epoch begins coverage as:

```text
unknown
```

until an authorized health event establishes its state.

Binding cutover quarantine remains unknown.

---

# 43. SourceEvaluability meaning

`SourceEvaluability` measures coverage/completeness of expected Task-01 acquisition sources.

It does NOT decide whether an already-present authorized normalized evidence row is syntactically/classification-compatible.

Existing-row compatibility is owned by EvidenceAdapterContract and OriginAssessment.

Therefore it is possible, by design, to have:

```text
SourceEvaluability = unknown/partial
+
present compatible evidence
→ usable evidence claim
```

because health coverage cannot erase evidence that is actually present.

---

# 44. SourceEvaluability states

Aggregate V1 states:

```text
evaluable

partially_evaluable

not_evaluable

unknown
```

## evaluable

All expected interval segments are:

```text
covered_available
or
covered_delayed
```

## partially_evaluable

At least one interval segment is covered and at least one is not fully covered.

## not_evaluable

No segment is covered and the full interval is positively known as intentional/known non-coverage such as:

```text
acquisition_unavailable
delivery_loss_confirmed
unsupported
```

with no unknown/pending segment.

## unknown

No segment is covered and at least one relevant interval is:

```text
unknown
delivery_pending_lossless
delivery_loss_possible
binding-cutover ambiguous
```

`SourceEvaluability` is a coverage assessment, not a row-validity verdict.

---

# 45. Evidence-present vs health matrix

R6 freezes the following V1 behavior.

| Present adapter-compatible evidence | Coverage state at its event time | Evidence-row use | Coverage interpretation |
|---|---|---|---|
| yes | covered_available | usable | normal |
| yes | covered_delayed | usable | normal after proven completion |
| yes | unknown | usable | `health_unknown_with_present_evidence` |
| yes | acquisition_unavailable | usable | `health_evidence_inconsistency`; coverage remains incomplete |
| yes | delivery_pending_lossless | usable | current absence elsewhere not interpretable |
| yes | delivery_loss_possible | usable | coverage incomplete |
| yes | delivery_loss_confirmed | usable | coverage incomplete |
| yes | unsupported | usable | `unsupported_but_evidence_present` inconsistency |
| no | covered_available | no claim | absence is still NOT a negative device fingerprint |
| no | unknown | no claim | absence uninterpretable |
| no | acquisition_unavailable | no claim | expected acquisition gap |
| no | delivery_pending_lossless | no claim | may arrive at later watermark |
| no | delivery_loss_possible | no claim | missing evidence uninterpretable |
| no | delivery_loss_confirmed | no claim | missing evidence uninterpretable |
| no | unsupported | no claim | intentional capability absence |

Health never creates a device-class/platform/manufacturer/model negative claim.

---

# 46. SourceEvaluability canonical artifact

`SourceEvaluability` uses the universal immutable artifact convention.

Its payload contains:

```text
evidence_snapshot_content_id
evidence_snapshot_content_digest

source_health_policy_id
source_health_policy_digest

ordered source entries
```

Each source entry contains:

```text
origin_group

source_kind

binding_epoch_id

producer_id

capture_source_id

aggregate_evaluability_state

covered_available_intervals

covered_delayed_intervals

acquisition_unavailable_intervals

delivery_pending_lossless_intervals

delivery_loss_possible_intervals

delivery_loss_confirmed_intervals

unsupported_intervals

unknown_intervals

health_reason_classifications

explanation_codes
```

Intervals are canonical half-open UTC:

```text
[start_utc, end_utc)
```

Canonical ordering:

```text
origin_group
source_kind
binding_epoch effective_from
producer_id
```

`mac_registry` has no SourceEvaluability entry.

The SourceEvaluability object/digest is retained for Level-B audit.

---

# 47. EvidenceAdapterContract

Every origin has explicit versioned EvidenceAdapterContract entries.

The canonical `EvidenceAdapterContractSet` is immutable and referenced by ClassificationPolicy and ClassifierArtifactManifest.

Each contract freezes:

```text
origin_group

source_kind

feature_schema_version

supported source_subtypes

compatible extractor_name/version constraints

compatible rule_version constraints where semantic

quality-state handling

required normalized payload fields per dimension

legacy/current schema role

claim derivation type

base claim-strength ceiling rules

semantic dedup projection
```

Unknown future schema is never parsed opportunistically.

---

# 48. Unsupported evidence contract

If a row is authorized by binding/time/watermark but its:

```text
source_kind
feature_schema_version
source_subtype
extractor/rule contract
```

is unsupported:

```text
row remains in EvidenceSnapshotContent/audit

row does not generate semantic classification claim

OriginAssessment records unsupported_evidence_contract
```

If no other compatible evidence resolves the dimension, this contributes to:

```text
insufficient_evidence
```

not a guessed classification.

---

# 49. quality_state semantics

Task-01 persists:

```text
valid
partial
degraded
```

R6 V1 default semantics:

## valid

Eligible for the adapter's normal base claim-strength rules.

## partial

May be interpreted only when the EvidenceAdapterContract proves that all normalized fields required for that specific dimension are present.

Any claim generated from `partial` evidence is capped at:

```text
supporting
```

in V1.

## degraded

Excluded from semantic claim generation in V1.

Retained for:

```text
audit
explanation
engineering diagnostics
```

A future proposal to use degraded evidence requires explicit architecture and validation.

---

# 50. V1/V2 coexistence

Task-04 launch may encounter multiple historical schema versions.

R6 freezes:

```text
dhcp/1 =
supported by explicit DHCP v1 adapter

tcp_syn/1 =
retained/auditable
NOT fusion-eligible for Task-04 V1
reason = legacy_tcp_schema_insufficient_for_exact_k2a_contract

tcp_syn/2 =
supported after Foundation Admission

tls_client/1 =
supported by explicit TLS v1 adapter

quic_client/1 =
supported by explicit QUIC v1 adapter

portal_headers/1 =
supported by explicit Portal v1 adapter

portal_headers/2 =
supported ONLY if Foundation Client-Hints admission passes
otherwise unsupported evidence contract
```

No destructive rewrite of old rows is required.

No generic:

```text
latest schema wins
```

rule exists.

If V1/V2 observations project to semantically identical same-origin claims:

```text
same-origin semantic dedup collapses them
```

They never become independent votes.

---

# 51. tcp_syn/2 principle and scope

`tcp_syn/2` persists the minimum protocol-semantic packet facts needed by admitted passive fingerprint adapters.

Initial scope:

```text
IPv4 only

outbound guest request SYN

SYN=1

ACK=0 eligibility

unfragmented IPv4

complete required Ethernet/IP/TCP header bytes

current controlled pre-router RSPAN placement
```

It does NOT persist:

```text
p0f quirks

p0f raw signature

p0f tokenized option dialect

p0f label

Fingerbank TCP string

OS guess

device guess
```

---

# 52. tcp_syn/2 durable facts

Initial V2 durable facts are limited to:

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

`tcp_header_length_bytes` is retained because exact supported p0f matching requires reconstructable total header length for MTU/window semantics, including malformed-but-observable option layouts.

Supported total header length:

```text
20
+
ip_option_length_bytes
+
tcp_header_length_bytes
```

---

# 53. IP-ID / timestamp minimization

Durable V2 stores:

```text
ip_id_zero
```

NOT exact IPv4 ID.

Timestamp option stores only:

```text
timestamp option present

timestamp_value_zero

timestamp_echo_nonzero
```

It does NOT store exact TCP timestamp or timestamp echo values.

No speculative future use justifies a stronger persistent correlator.

---

# 54. One TCP option representation

There is exactly one durable option source of truth:

```text
ordered tcp_option_records
```

No separately persisted option-kind sequence.

Each record contains only bounded required structure and minimum admitted semantics.

Raw option bytes are not durable.

A global malformed/well-formed state is derived deterministically from ordered records and is not separately persisted if it can disagree with them.

---

# 55. Malformed option semantics

Distinction:

```text
actual packet/header structural incompleteness
→ reject event

malformed option syntax inside a complete observable TCP header
→ preserve normalized packet facts
```

No silent loss of fingerprintable abnormal SYNs.

Exact supported boundary is proven against pinned p0f behavior.

---

# 56. tcp_syn/2 privacy/minimization gate

Before schema freeze, every durable field must prove:

```text
required by an admitted adapter/classification contract

bounded representation

no less-sensitive equivalent can satisfy the admitted requirement
```

A field that fails any condition is removed.

Exact timestamp/IP-ID numeric values remain excluded unless a future reviewed adapter proves otherwise.

---

# 57. p0f conformance split

R6 separates:

```text
K2A =
p0f semantics/conformance foundation

K2B =
production TCP knowledge corpus
```

K2A owns runtime serialization, matcher grammar, window/MSS/MTU expressions, option semantics, quirks, TTL/distance, fuzzy behavior, specific/generic precedence and real-p0f oracle corpus.

K2A proves CaptivPortal understands p0f.

K2B owns actual admitted production TCP reference signatures.

---

# 58. TTL/RSPAN proof

R6 does not freeze hop distance from topology theory.

Foundation proof must record actual SPAN/RSPAN config, source/direction, controlled sender SYN identity, sender TTL and sensor TTL.

Capture-topology change invalidates this proof.

---

# 59. Portal Client Hints

`portal_headers/2` remains:

```text
CANDIDATE
NOT FROZEN
```

Candidate high-entropy hints may include Model, Platform-Version and Form-Factors.

Each field is admitted independently only after controlled actual-flow value/privacy proof.

If none passes:

```text
portal_headers/1 remains canonical
```

---

# 60. Critical-CH / Accept-CH

For V1:

```text
Critical-CH = FORBIDDEN
```

No forced browser retry.

`Accept-CH` is bounded optional enrichment only.

Controlled proof must demonstrate:

```text
negotiation

subsequent eligible same-origin request

normalization

collection teardown
```

Preferred teardown where supported:

```text
Clear-Site-Data: "clientHints"
```

No continuous high-entropy request, raw durability, JS fingerprint fallback or Authorization dependency.

---

# 61. Portal idle source-health

Before Foundation Admission, enabled portal evidence must gain idle periodic source liveness independent of visitor traffic.

Heartbeat contains no client evidence and follows the failure-domain/coverage semantics frozen by SourceHealthPolicy.

---

# 62. External artifact boundary

Runtime Task-04 classifier never reads vendor schemas directly.

Required pipeline:

```text
external artifact
→ quarantine/read-only inspection
→ legal/provenance review
→ validated importer
→ CaptivPortal canonical knowledge records
→ immutable KnowledgeBundle
→ runtime
```

---

# 63. KnowledgeBundle canonical contract

`KnowledgeBundle` is immutable under the universal artifact convention.

Semantic payload minimum:

```text
bundle_schema_version

classification_taxonomy_version

alias_mapping_version

ordered canonical source manifests

ordered canonical imported knowledge records

ordered freshness-policy references

ordered source-governance references
```

`created_at_utc` is artifact metadata and does not alter semantic content digest.

Source manifests are ordered by `source_manifest_id`.

Knowledge records are ordered by:

```text
knowledge_record_type
canonical_record_id
```

Policy/governance references are ordered by artifact ID.

---

# 64. Knowledge source manifest

Each external source manifest contains at least:

```text
source_manifest_id

source_name

source_version/provider metadata

retrieved_at_utc

source_artifact_sha256

importer identity/version

license/provenance reference

redistribution/commercial/modification status where applicable

source_character

freshness_policy_id/digest

canonical imported-record-set digest
```

`source_character`:

```text
current
legacy
```

Freshness state remains separately:

```text
fresh
stale
expired
```

---

# 65. Knowledge freshness

Each changing external source requires immutable `KnowledgeFreshnessPolicy`.

Exact thresholds are proven from real source behavior, metadata/provider cadence, operational refresh capability, failure tolerance and Owner policy.

No magic ages are frozen by architecture.

Classification request explicitly contains:

```text
knowledge_evaluation_at_utc
```

Pure core does not read current time.

---

# 66. Knowledge expiry runtime behavior

If one source is expired at explicit knowledge evaluation time:

```text
source emits no new classification claims

knowledge_source_expired explanation recorded

classifier continues with remaining admitted sources
```

KnowledgeBundle bytes do not mutate.

A source expiry is not a classifier crash.

---

# 67. KnowledgeBundle activation

Lifecycle:

```text
build candidate
validate
Foundation checks
accept
atomic active-pointer switch
```

In-flight request pins bundle ID/digest.

Refresh does not mutate accepted bundle.

Rollback atomically activates a previously accepted bundle.

---

# 68. Mandatory offline knowledge

At Foundation Admission, accepted bundle contains currently usable:

```text
taxonomy/aliases
K1 DHCP knowledge
K2B TCP knowledge
K3 portal rules
K4 IEEE registry/mappings
```

A source counts only if legally admitted, canonically imported, schema/taxonomy compatible, freshness-resolved, not expired and runtime usable.

---

# 69. Fingerbank K1 provenance purity

K1 runtime input is DHCP-only.

Additionally, every fusion-eligible imported K1 mapping must be provably attributable solely to admitted DHCP attributes upstream.

Unknown or multi-origin upstream provenance:

```text
NOT fusion-eligible as DHCP knowledge
```

It may remain research/explainability data.

---

# 70. IEEE semantics

MA-L/MA-M/MA-S longest-prefix import.

Locally administered MAC:

```text
IEEE lookup = NOT ELIGIBLE
```

Raw result:

```text
mac_assignment_org
```

Manufacturer claim requires explicit canonical mapping from assignment org to manufacturer.

---

# 71. classification_taxonomy_v1

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

R6 freezes:

```text
ios =
Apple mobile OS family including iOS + iPadOS for V1
```

Device class in-scope values:

```text
smartphone
tablet
laptop
```

---

# 72. recognized_out_of_scope applicability

Allowed final status only for:

```text
platform_family
device_class
```

Not allowed for:

```text
manufacturer_family
model_family
```

Unmapped manufacturer/model taxon becomes `insufficient_evidence` with explicit unmapped explanation.

---

# 73. Canonical manufacturer/model identity

Manufacturer:

```text
manufacturer_id
display label reference
explicit source aliases
```

Model:

```text
model_family_id
display label reference
explicit source aliases
```

No heuristic identity from case, punctuation, prefix stripping, substring, edit distance or marketing similarity.

---

# 74. Claim derivation vs claim strength

Orthogonal V1 concepts:

```text
claim_derivation =
declared
deterministic_mapping
fingerprint_match
registry_mapping
```

and:

```text
claim_strength =
strong
supporting
```

Fusion compares strength only.

Derivation is provenance/explainability.

No "declared always wins".

---

# 75. Origin groups and purity

Origins:

```text
dhcp
portal
tcp
tls
quic
mac_registry
```

Inputs remain origin-isolated.

`mac_registry` consumes observed MAC + local knowledge only and is outside Task-01 binding/health.

Multi-origin external answers do not become independent votes.

---

# 76. Semantic dedup

Repeated same-origin rows do not multiply support.

Equivalent V1/V2 semantic projections collapse within the origin.

Counts remain explainability only.

---

# 77. Same-origin strength matrix

```text
strong + strong same
→ resolved

strong + strong incompatible
→ conflicting

strong + supporting same
→ resolved

strong + supporting incompatible
→ strong retained
→ contradiction recorded

supporting + supporting same
→ resolved

supporting + supporting incompatible
→ conflicting
```

No row majority, latest wins, source-name or derivation priority.

`ambiguous` remains internal only and maps to final `insufficient_evidence` unless another origin safely resolves the dimension.

---

# 78. Cross-origin strength matrix

```text
strong vs strong incompatible
→ conflicting_evidence

strong vs supporting incompatible
→ strong retained
→ contradiction recorded
→ support capped medium

supporting vs supporting incompatible
→ conflicting_evidence
```

Same-outcome claims corroborate according to support rules.

No hidden source priority.

---

# 79. OriginAssessment canonical contract

Immutable payload minimum:

```text
origin_group

evidence_compatibility_status

SourceEvaluability ref/digest
or null for mac_registry

semantic_variant_count

ordered dimension_assessments

ordered same-origin contradictions

ordered broad/unresolved information

ordered out-of-scope references

ordered evidence references

ordered knowledge references

ordered explanation codes
```

Compatibility enum:

```text
compatible
partially_compatible
unsupported_evidence_contract
no_evidence
not_applicable
```

Dimension internal state enum:

```text
resolved
recognized_out_of_scope
ambiguous
conflicting
no_claim
not_evaluable
```

Contradiction is a separate flag/list, not an extra enum state.

---

# 80. OriginAssessment references

Evidence reference minimum:

```text
evidence_id
payload_sha256
feature_schema_version
adapter_contract_id/digest
```

Knowledge reference minimum:

```text
knowledge_bundle_id/digest
source_manifest_id
canonical_knowledge_record_id
```

No raw packet/UA/CH copied.

---

# 81. ClassificationPolicy

Immutable payload minimum:

```text
taxonomy reference

EvidenceAdapterContractSet reference

claim enums

same-origin matrix

cross-origin matrix

support rules

DimensionResult status rules

out-of-scope applicability

global-status derivation

SourceHealthPolicy reference

SnapshotContentPolicy reference

KnowledgeFreshnessPolicy references

ClassificationRetentionPolicy reference

ProductValidationPolicy reference
```

Mutable config cannot alter classification meaning.

---

# 82. DimensionResult

For each dimension:

```text
dimension_name

canonical_value_id or null

display_label_ref or null

status

support_level

supporting_origin_groups

contradicting_origin_groups

not_evaluable_origin_groups

out_of_scope_taxon_references

explanation_codes

knowledge_references
```

Final status enum:

```text
resolved
recognized_out_of_scope
unknown
insufficient_evidence
conflicting_evidence
```

---

# 83. Final status semantics

`conflicting_evidence`:
decisive incompatible concrete claims.

`resolved`:
one safe in-scope canonical value selected.

`recognized_out_of_scope`:
platform/device-class only; one safe external taxon proven outside V1 scope.

`insufficient_evidence`:
semantic information exists but is ambiguous/broad/unsupported/unmapped/otherwise insufficient, or no adequate supported evidence path exists.

`unknown`:
supported evidence exists but usable admitted knowledge emits no semantic information, including relevant knowledge suppressed by expiry.

---

# 84. support_level

```text
none
low
medium
high
```

High:

```text
>=2 independent origins agree
>=2 contributing claims strong
no incompatible claim of any strength
```

Medium:

```text
>=1 strong claim
no decisive strong conflict
```

Any lower-strength contradiction caps medium.

Low:

```text
supporting claims only
all selectable supporting claims agree
```

None for unknown/insufficient/conflicting.

Out-of-scope recognition may have low/medium/high.

---

# 85. Global classification status

Exact precedence:

```text
1. any dimension conflicting
→ conflicting_evidence

2. all four resolved
→ classified

3. any resolved
→ partial

4. otherwise any platform/device_class recognized_out_of_scope
→ recognized_out_of_scope

5. otherwise any insufficient_evidence
→ insufficient_evidence

6. otherwise
→ unknown
```

Global enum:

```text
classified
partial
recognized_out_of_scope
unknown
insufficient_evidence
conflicting_evidence
```

---

# 86. Pure classification core

Deterministic function:

```text
EvidenceSnapshotContent
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

Pure core has no DB, network, filesystem discovery, clock reads, mutable config, vendor schema, telemetry or persistence.

---

# 87. ClassifierArtifactManifest

Immutable payload minimum:

```text
repository_commit_sha
repository_tree_sha
classification_engine_semver
pure_core_contract_version
classification_result_schema_version
snapshot_contract_version

exact adapter implementation identities for:
dhcp/1
tcp_syn/1
tcp_syn/2
tls_client/1
quic_client/1
portal_headers/1
portal_headers/2 when admitted

K2A matcher implementation version

build/package digest where required
```

Changing schema-version interpretation changes classifier identity.

---

# 88. ClassificationRequestManifest

Immutable payload:

```text
EvidenceSnapshotContent ID/digest
SourceEvaluability ID/digest
KnowledgeBundle ID/digest
ClassificationPolicy ID/digest
ClassifierArtifactManifest ID/digest
knowledge_evaluation_at_utc
```

Its digest is `classification_request_digest`.

---

# 89. Semantic ClassificationResult

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

No `classified_at_utc` in pure semantic result.

---

# 90. Persistence metadata

Service persistence separately stores:

```text
classification_id
site_id
observed_mac
classified_at_utc
ClassificationRequestManifest ID/digest
semantic ClassificationResult ID/digest
SnapshotRecord ID
retention-policy ID/digest
```

---

# 91. ClassificationRetentionPolicy

Classification storage contains privacy-relevant durable data including MAC and derived device information.

Therefore immutable `ClassificationRetentionPolicy` is mandatory.

Exact duration:

```text
REQUIRED / UNRESOLVED
```

R6 does not invent 30 days.

Foundation Admission requires Owner to freeze first production retention before Task-04 decomposition.

Artifact/content retention follows references from retained classifications.

---

# 92. Audit retention

While a classification remains retained, retain retrievable:

```text
EvidenceSnapshotContent
SnapshotRecord reference
SourceEvaluability
OriginAssessments
ClassificationRequestManifest
semantic ClassificationResult
KnowledgeBundle
ClassificationPolicy
EvidenceAdapterContractSet
SourceHealthPolicy
SnapshotContentPolicy
EvidenceSourceBindingTimeline
BindingClockPolicy
KnowledgeFreshnessPolicies
ClassifierArtifactManifest
ProductValidationPolicy
```

Digest without retrievable content is not replay.

After classification expiry, an artifact is GC-eligible only if no other retained classification references it.

---

# 93. Audit levels

Level A:

```text
Task-01 source rows
→ snapshot/evaluability/origin
```

available only while required Task-01 rows and compatible generation remain.

Level B:

```text
retained SourceEvaluability
+
retained OriginAssessments
+
retained policy/bundle/classifier/request
→ semantic ClassificationResult
```

must remain possible for full classification-history retention.

No raw acquisition data is extended merely for replay.

---

# 94. ProductValidationPolicy

No undefined "primary dimension".

Safety:

```text
ANY incorrect resolved known-ground-truth dimension
→ FAIL

ANY false recognized_out_of_scope
on known in-scope platform/device_class
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

Across those two:
at least one correct device_class
resolved
support >= medium
```

Manufacturer/model may remain unresolved if evidence does not justify them.

Always-unknown classifier cannot pass.

---

# 95. Foundation Admission gate model

Foundation gates run only after architecture acceptance and separate Owner authorization of bounded foundation work.

Every gate MUST produce:

```text
INPUT
PROOF METHOD
PASS
FAIL
RETAINED EVIDENCE
CANONICAL OUTPUT ARTIFACT
OWNER DECISION IF ANY
NEXT CONSUMER
```

## F-A1 — Watermark + one-transaction snapshot foundation

**INPUT:** watermark-capable Task-01 schema, sequence allocator, snapshot read boundary.  
**PROOF:** controlled evidence+health ingest and complete multi-page read using one SQLite transaction.  
**PASS:** one sequence namespace; committed watermark exact; same connection/transaction for all pages/health/anchors.  
**FAIL:** timestamp/UUID/rowid commit order, connection per page, watermark refresh.  
**RETAINED:** schema manifest, transaction trace, test report.  
**OUTPUT:** `Task01WatermarkReadContract`.  
**OWNER:** none unless scope exception.  
**NEXT:** F-A2/F-A3/Snapshot Service.

## F-A2 — Concurrent ingest + retention determinism

**INPUT:** F-A1 candidate, multi-page fixture, concurrent delayed insert, concurrent retention DELETE.  
**PROOF:** start reader; capture W; paginate while insert/delete/checkpoint occurs.  
**PASS:** immutable reader view; post-W insert excluded; rows visible at reader start not skipped by concurrent delete; stable content digest.  
**FAIL:** mid-snapshot membership/order change.  
**RETAINED:** W, row manifests, transaction/retention trace, digests.  
**OUTPUT:** `SnapshotConcurrencyProof`.  
**OWNER:** none.  
**NEXT:** Foundation Admission.

## F-A3 — Generation migration/recovery

**INPUT:** pre-watermark DB, migration, older-backup restore fixture.  
**PROOF:** initial rebaseline + controlled restore rebaseline.  
**PASS:** new generation, deterministic retained-row rebaseline, writer blocked until completion, no sequence reuse/wrap, exact duplicate semantics.  
**FAIL:** sequence reuse or impossible automatic rollback-detection claim.  
**RETAINED:** old/new DB/generation/allocator evidence.  
**OUTPUT:** `Task01GenerationRecoveryContract`.  
**OWNER:** acknowledge recovery operational invariant.  
**NEXT:** production recovery + snapshot/audit.

## F-A4 — Source-health predecessor anchor retention

**INPUT:** evidence retention, health cleanup, binding epochs, retention-boundary windows.  
**PROOF:** cleanup plus health reconstruction.  
**PASS:** required predecessor survives for every retained eligible binding segment.  
**FAIL:** retained evidence becomes falsely unknown due deleted predecessor.  
**RETAINED:** before/after inventory and reconstruction.  
**OUTPUT:** `SourceHealthRetentionContract`.  
**OWNER:** none.  
**NEXT:** SourceEvaluability.

## F-B1 — Binding timeline / clock / valid-from

**INPUT:** actual topology, timeline candidate, clock measurements, A→B cutover.  
**PROOF:** measure clock domains and execute cutover.  
**PASS:** one authoritative binding outside quarantine; mandatory producer/capture identity; no HA; guard frozen; valid-from frozen; mac_registry excluded.  
**FAIL:** hidden historical authority or undefined overlap/cutover.  
**RETAINED:** topology, clock, cutover, timeline digest.  
**OUTPUT:** `EvidenceSourceBindingTimeline`, `BindingClockPolicy`.  
**OWNER:** accept `classification_foundation_valid_from_utc`.  
**NEXT:** Snapshot/health/Task-04.

## F-B2 — Health failure-domain / coverage policy

**INPUT:** network+portal producer behavior, status/reasons, spool/queue guarantees, delayed-event contract.  
**PROOF:** acquisition failure, transport failure, recovery, backfill.  
**PASS:** deterministic coverage mapping; unknown reason→unknown; transport outage→central unknown; delayed contract respected.  
**FAIL:** one generic unavailable semantics or fabricated central outage.  
**RETAINED:** producer/central timelines and mapping.  
**OUTPUT:** `SourceHealthPolicy`.  
**OWNER:** only if risk acceptance needed.  
**NEXT:** SourceEvaluability/ClassificationPolicy.

## F-B3 — Portal idle heartbeat

**INPUT:** enabled portal producer idle + transport-failure scenario.  
**PROOF:** multiple heartbeat cycles, outage/recovery.  
**PASS:** client-independent heartbeat, no client data/auth effect, accepted cadence/freshness frozen.  
**FAIL:** visitor-dependent liveness or impossible live outage report over failed path.  
**RETAINED:** health timeline.  
**OUTPUT:** updated accepted `SourceHealthPolicy`.  
**OWNER:** none.  
**NEXT:** Foundation Admission.

## F-C1 — tcp_syn/2 minimization/schema

**INPUT:** proposed schema + admitted p0f requirements.  
**PROOF:** field-by-field privacy/value matrix + packet fixtures.  
**PASS:** minimum facts; header length sufficient; no exact IP-ID/timestamps; one option representation; malformed observable preserved.  
**FAIL:** speculative correlator/duplicate representation/missing required structure.  
**RETAINED:** field matrix, privacy review, schema/fixture report.  
**OUTPUT:** `tcp_syn/2 schema contract`.  
**OWNER:** required for any stronger correlating field.  
**NEXT:** F-C2/adapter contracts.

## F-C2 — p0f adapter/matcher conformance

**INPUT:** tcp_syn/2 + pinned real p0f/corpus.  
**PROOF:** oracle comparison for normal/malformed supported fixtures.  
**PASS:** exact supported serialization/matching semantics.  
**FAIL:** approximate clone/unexplained mismatch.  
**RETAINED:** oracle/corpus identity and diff report.  
**OUTPUT:** `K2AConformancePackage`.  
**OWNER:** none.  
**NEXT:** K2B/classifier identity.

## F-C3 — TTL/RSPAN physical proof

**INPUT:** controlled sender + running mirror config.  
**PROOF:** correlated SYN sender/sensor TTL.  
**PASS:** current distance assumption proven.  
**FAIL:** mismatch/incomplete path evidence.  
**RETAINED:** config + packet correlation.  
**OUTPUT:** `TTLCapturePlacementProof`.  
**OWNER:** none.  
**NEXT:** p0f runtime contract.

## F-D1 — Client Hints actual-flow + teardown

**INPUT:** controlled clients + candidate Accept-CH.  
**PROOF:** real portal flow, sanitized network/storage audit.  
**PASS:** material deterministic normalized value; no Critical-CH/retry/raw durability/auth effect; bounded teardown.  
**FAIL:** persistent collection, raw durability or no value.  
**RETAINED:** sanitized flow/teardown/storage proof.  
**OUTPUT:** `portal_headers/2 contract` OR explicit `NOT ADMITTED`.  
**OWNER:** authorize controlled experiment.  
**NEXT:** adapter contracts/K3.

## F-E1 — Fingerbank static import/provenance purity

**INPUT:** Owner-authorized current static artifact.  
**PROOF:** read-only schema/legal/provenance inspection + canonical import.  
**PASS:** vendor runtime coupling removed; fusion-eligible DHCP mapping proven DHCP-only upstream.  
**FAIL:** hidden multi-origin mapping/unknown legal basis/runtime vendor dependency.  
**RETAINED:** SHA/schema/license/provenance/import report.  
**OUTPUT:** Fingerbank source manifest + canonical K1 records.  
**OWNER:** source governance acceptance.  
**NEXT:** KnowledgeBundle.

## F-E2 — IEEE import

**INPUT:** MA-L/MA-M/MA-S candidate.  
**PROOF:** canonical import/prefix fixtures.  
**PASS:** longest prefix, U/L exclusion, assignment-org semantics, explicit manufacturer mapping only.  
**FAIL:** OUI-only or automatic manufacturer certainty.  
**RETAINED:** source/import/mapping report.  
**OUTPUT:** IEEE source manifest + K4 records.  
**OWNER:** governance acceptance where needed.  
**NEXT:** KnowledgeBundle.

## F-E3 — Production TCP knowledge admission

**INPUT:** K2B candidate.  
**PROOF:** governance/provenance/import/K2A compatibility/taxonomy review.  
**PASS:** actual usable TCP corpus exists separately from oracle.  
**FAIL:** oracle-only or unusable source.  
**RETAINED:** source manifest/import/conformance report.  
**OUTPUT:** K2B manifest + canonical TCP records.  
**OWNER:** source governance/legacy acceptance.  
**NEXT:** KnowledgeBundle.

## F-E4 — Taxonomy/alias determinism

**INPUT:** taxonomy + mappings.  
**PROOF:** fixtures for iOS/iPadOS, broad values, out-of-scope, aliases, unmapped manufacturer/model.  
**PASS:** exact R6 semantics, no heuristic aliasing/narrowing.  
**FAIL:** string similarity changes identity.  
**RETAINED:** taxonomy/alias fixture report.  
**OUTPUT:** `classification_taxonomy_v1`, `alias_mapping_v1`.  
**OWNER:** accept V1 scope.  
**NEXT:** KnowledgeBundle/Policy.

## F-E5 — Knowledge freshness policies

**INPUT:** source update behavior/docs/metadata/refresh operations/failure tolerance.  
**PROOF:** source-specific analysis and boundary fixtures.  
**PASS:** justified fresh/stale/expired policy and stale strength behavior.  
**FAIL:** arbitrary age.  
**RETAINED:** research/rationale.  
**OUTPUT:** immutable `KnowledgeFreshnessPolicy` per source.  
**OWNER:** accept freshness policy.  
**NEXT:** bundle admission/policy.

## F-F1 — KnowledgeBundle build/activation

**INPUT:** taxonomy, K1/K2B/K3/K4, manifests, policies.  
**PROOF:** deterministic build twice + validation + atomic activation/rollback.  
**PASS:** same semantic digest; mandatory sources usable; immutable pin; atomic switch/rollback.  
**FAIL:** undefined digest/mutable bundle/vendor dependency/expired source counted.  
**RETAINED:** bundle digests/validation/activation trace.  
**OUTPUT:** accepted `KnowledgeBundle`.  
**OWNER:** accept bundle.  
**NEXT:** Task-04.

## F-F2 — Snapshot sizing

**INPUT:** production per-MAC cardinality, worst-case controlled workload, bytes/pagination/memory/CPU benchmarks.  
**PROOF:** measured capacity study.  
**PASS:** separate deterministic content ceilings and operational execution limits frozen.  
**FAIL:** guessed ceilings or CPU pressure mapped to semantic resource state.  
**RETAINED:** measurement/benchmark report.  
**OUTPUT:** `SnapshotContentPolicy`, `SnapshotExecutionPolicy`.  
**OWNER:** accept resource envelope.  
**NEXT:** Snapshot Service/Policy.

## F-F3 — EvidenceAdapterContractSet freeze

**INPUT:** all eligible schema families and quality states.  
**PROOF:** compatibility fixtures.  
**PASS:** explicit adapter/non-fusion reason for every schema; unknown future fail-closed; partial supporting cap; degraded excluded; dedup frozen.  
**FAIL:** latest-wins/opportunistic parse/Coder quality discretion.  
**RETAINED:** adapter matrix/fixtures.  
**OUTPUT:** `EvidenceAdapterContractSet`.  
**OWNER:** none.  
**NEXT:** ClassificationPolicy/Task-04.

## F-F4 — ClassificationPolicy freeze

**INPUT:** taxonomy, adapters, health/content/freshness policies and R6 matrices.  
**PROOF:** immutable policy + machine-readable canonical test-vector specification, without implementing Task-04 engine.  
**PASS:** every matrix/status/support rule defined; no hidden source/derivation priority.  
**FAIL:** undefined cell/mutable config dependency.  
**RETAINED:** policy digest/test-vector spec/review.  
**OUTPUT:** `ClassificationPolicy`.  
**OWNER:** Owner + TechLead semantic acceptance.  
**NEXT:** Task-04 pure core.

## F-F5 — ClassificationRetentionPolicy freeze

**INPUT:** privacy/storage/audit requirements.  
**PROOF:** Owner decision + bounded review.  
**PASS:** exact retention/GC semantics frozen.  
**FAIL:** unresolved persistence retention.  
**RETAINED:** decision + analysis.  
**OUTPUT:** `ClassificationRetentionPolicy`.  
**OWNER:** REQUIRED.  
**NEXT:** Task-04 persistence.

## F-F6 — ProductValidationPolicy freeze

**INPUT:** controlled Android smartphone + Windows laptop and R6 safety/utility floor.  
**PROOF:** immutable acceptance policy artifact.  
**PASS:** exact no-wrong-resolution/no-false-out-of-scope plus minimum utility requirements frozen.  
**FAIL:** always-unknown could pass.  
**RETAINED:** policy review.  
**OUTPUT:** `ProductValidationPolicy`.  
**OWNER:** REQUIRED.  
**NEXT:** Task-04 product acceptance.

---

# 96. Foundation Admission

`F-ADMIT` consumes all mandatory Foundation outputs.

Optional `portal_headers/2` may close as explicit `NOT ADMITTED`.

**PASS** requires a complete internally consistent Foundation Artifact Set and exact repository candidate identity for implemented foundation pieces.

Canonical output:

```text
FoundationAdmissionManifest
```

containing exact accepted artifact IDs/digests and foundation repository commit/tree identities.

Only after explicit TechLead11 review + Owner acceptance of `F-ADMIT`:

```text
TechLead11 may decompose TASK-04
```

No Task-04 code is required to pass Foundation Admission.

---

# 97. Task-04 Acceptance gates

These gates run only after:

```text
F-ADMIT PASS
TechLead11 decomposition
Owner Task-04 authorization
Task-04 implementation candidate exists
```

## T-01 — EvidenceAdapter execution/coexistence

**INPUT:** implementation + accepted adapter contracts.  
**PROOF:** execute every supported/unsupported schema and quality fixture.  
**PASS:** exact V1/V2/quality/dedup behavior.  
**FAIL:** opportunistic parse/duplicate vote/quality discretion.  
**RETAINED:** test report + candidate identity.  
**OUTPUT:** `EvidenceAdapterExecutionProof`.  
**OWNER:** none.  
**NEXT:** T-02/T-03.

## T-02 — SourceEvaluability execution

**INPUT:** implementation + accepted health policy/snapshot fixtures.  
**PROOF:** interval matrix including available/delayed/acquisition failure/loss/unsupported/unknown/cutover/present-evidence inconsistency.  
**PASS:** canonical SourceEvaluability exact.  
**FAIL:** health discards present evidence or absence becomes negative fingerprint.  
**RETAINED:** input/output artifact digests.  
**OUTPUT:** `SourceEvaluabilityExecutionProof`.  
**OWNER:** none.  
**NEXT:** T-03/T-05.

## T-03 — OriginAssessment execution

**INPUT:** implemented origin logic + accepted knowledge/policy.  
**PROOF:** dedup, ambiguity, strength conflicts, broad taxon, out-of-scope, unsupported contract, expired knowledge.  
**PASS:** canonical OriginAssessment exact.  
**FAIL:** row majority/latest-wins/derivation priority/undefined state.  
**RETAINED:** fixture matrix + OriginAssessments.  
**OUTPUT:** `OriginAssessmentExecutionProof`.  
**OWNER:** none.  
**NEXT:** T-04.

## T-04 — Fusion/Dimension/global execution

**INPUT:** pure fusion core + accepted policy vectors.  
**PROOF:** full same/cross-origin matrix/status combinations.  
**PASS:** exact strength conflict, support, dimension/global semantics.  
**FAIL:** hidden priority/undefined cell.  
**RETAINED:** vector/result table.  
**OUTPUT:** `FusionExecutionProof`.  
**OWNER:** none.  
**NEXT:** T-05/T-06.

## T-05 — Pure-core determinism / explicit knowledge time

**INPUT:** exact immutable requests under controlled environment/time changes.  
**PROOF:** block DB/network/filesystem; vary system clock; then vary only explicit knowledge evaluation time.  
**PASS:** same request digest→same result; wall clock alone no effect; expired individual source suppresses claims without service crash.  
**FAIL:** hidden I/O/clock/config dependency.  
**RETAINED:** request/result digests and blocked-I/O proof.  
**OUTPUT:** `PureCoreDeterminismProof`.  
**OWNER:** none.  
**NEXT:** T-06/T-08.

## T-06 — Exact ClassifierArtifactManifest

**INPUT:** exact candidate.  
**PROOF:** generate manifest.  
**PASS:** commit/tree/engine/contracts/all adapter implementation identities/K2A/build digest where needed.  
**FAIL:** vague current/v1 identity.  
**RETAINED:** build/repository identity.  
**OUTPUT:** accepted `ClassifierArtifactManifest`.  
**OWNER:** none.  
**NEXT:** T-07/T-09.

## T-07 — Persistence/retention/audit replay

**INPUT:** persistence + accepted retention + immutable request objects.  
**PROOF:** persist, Level-B replay, reference-aware test GC.  
**PASS:** all replay objects retrievable; exact replay; referenced artifacts retained; GC only when unreferenced after classification expiry.  
**FAIL:** digest-only audit or lost artifact/privacy mismatch.  
**RETAINED:** persistence/replay/GC report.  
**OUTPUT:** `ClassificationAuditPersistenceProof`.  
**OWNER:** verify retention implementation.  
**NEXT:** T-08/T-09.

## T-08 — Offline/failure isolation

**INPUT:** candidate.  
**PROOF:** block Internet; inject classification DB failure, bundle load failure, operational snapshot timeout, deterministic content-limit excess, classifier exception and source expiry.  
**PASS:** no Internet hard dependency; no partial classification; operational timeout is retryable build failure; classification failure does not affect Task-01/Auth/CAPPORT; expired source degrades claims only.  
**FAIL:** remote hard dependency, auth impact, ingest impact or partial result.  
**RETAINED:** fault matrix/service report.  
**OUTPUT:** `OfflineFailureIsolationProof`.  
**OWNER:** none.  
**NEXT:** T-09.

## T-09 — Controlled product safety + utility

**INPUT:** accepted candidate + Owner Android smartphone + Owner Windows laptop.  
**PROOF:** normal product path with known ground truth.  
**PASS SAFETY:** no incorrect resolved known-ground-truth dimension; no false out-of-scope on known in-scope platform/device class.  
**PASS UTILITY:** Android platform `android` resolved support >= medium; Windows laptop platform `windows` resolved support >= medium; at least one correct device_class resolved support >= medium.  
**FAIL:** any wrong resolved dimension, false out-of-scope or minimum utility failure.  
**RETAINED:** privacy-safe validation report + request/result digests.  
**OUTPUT:** `Task04ProductValidationProof`.  
**OWNER:** validate ground truth and accept controlled result.  
**NEXT:** T-ACCEPT.

## T-ACCEPT — Task-04 acceptance

**INPUT:** all mandatory T-gate PASS artifacts + exact candidate identity.  
**PROOF:** TechLead11 full acceptance review.  
**PASS:** implementation conforms to R6 + FoundationAdmissionManifest.  
**FAIL:** any known semantic/audit/safety/utility/fallback defect.  
**RETAINED:** acceptance report + exact artifact inventory.  
**OUTPUT:** `Task04AcceptanceManifest`.  
**OWNER:** final Task-04 acceptance/deployment decision remains separate.  
**NEXT:** normal project publication/deployment/activation process.

---

# 98. Permanent no-silent-fallback rules

Forbidden:

```text
no watermark
→ wall-clock approximation

no binding
→ infer producer from arrived rows

cutover uncertainty
→ pick nearest producer

unknown health reason
→ assume available/unavailable

expired knowledge
→ silently keep strength

unsupported schema
→ parse nearest schema

tcp_syn/1
→ approximate tcp_syn/2

malformed p0f semantics
→ silently discard complete observable packet

content limit exceeded
→ classify first N rows

operational timeout
→ semantic not_evaluable

ambiguous knowledge
→ first row

same-origin repeats
→ extra votes

declared Client Hint
→ automatic reliability priority

IEEE assignment org
→ automatic manufacturer

out-of-scope device
→ squeeze into smartphone/tablet/laptop

classification failure
→ affect Authorization
```

At the relevant boundary:

```text
fail closed with explicit typed reason
```

instead of hidden approximation.

---

# 99. Required R6 status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R6

STATUS =
FOR OWNER + TECHLEAD11 STRICT REVIEW

R5 =
SUPERSEDED

ARCHITECTURE CONTRACT FINAL =
NO

TASK-04 =
HOLD

NO TASK-04 CODER TASK

NO PRODUCTION CHANGE FROM THIS DOCUMENT ALONE
```

Only:

```text
OWNER ACCEPT
+
TECHLEAD11 ACCEPT
```

may promote the architecture contract.

After architectural acceptance:

```text
PRE-TASK FOUNDATION implementation may begin
under separate TechLead tasks + Owner authorization
```

Task-04 remains HOLD until:

```text
Foundation Admission F-ADMIT = PASS
```

Only then may TechLead11 decompose Task-04.

---
