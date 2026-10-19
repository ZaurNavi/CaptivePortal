# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R5

## Deterministic Passive Classification Foundation Before Task-04

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-16  
**Supersedes:** `DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R4`  
**Status:** `FOR OWNER + TECHLEAD11 STRICT REVIEW`  
**Architecture Contract Final:** `NO`  
**Task-04:** `HOLD`  
**Coder:** `HOLD`  
**Code:** `NO`  
**Production change:** `NO`

---

# 1. R5 Disposition

TechLead11 strict review returned:

```text
R4 = REQUEST CHANGES

ARCHITECTURE CONTRACT FINAL = NO

TASK-04 = HOLD
CODER = HOLD
CODE = NO
PRODUCTION CHANGE = NO
```

R5 replaces R4 completely.

R4 is historical review material only.

No R4 exception, default, enum, threshold or gate remains authoritative unless reproduced explicitly in R5.

Owner policy remains:

```text
NO REVISION LIMIT.

NO KNOWN FOUNDATION DEBT
MAY BE ACCEPTED FOR THE SAKE OF
FINISHING ARCHITECTURE.
```

---

# 2. Verified Repository Baseline

R5 is prepared against:

```text
origin/main =
d37d3ec126ccd512fe835af0db21221e2f83d565

tree =
3145e904ad5027d0d584945f4814f3ade59d44ea
```

Current accepted production evidence schema families:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

Current Task-01 evidence persistence contains, among other fields:

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

Current source-health persistence contains:

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

Current persisted health state enum is exactly:

```text
available
unavailable
unsupported
```

Current Task-01 evidence API:

```text
cursor-paginated
maximum page size = 500
```

Current Task-01 timestamp contract includes:

```text
default evidence retention = 30 days

default maximum future source-clock skew =
120 seconds

default maximum delayed event age =
86400 seconds
```

Current network sensor heartbeat behavior:

```text
dhcp
tcp_syn
tls_client
quic_client

same-state heartbeat interval =
300 seconds
```

Current portal source-health remains transition/delivery-driven and does not yet provide equivalent idle periodic liveness.

---

# 3. Current 03A Status — Exact Truth

Canonical status:

```text
TASK-DEVICE-FINGERPRINT-03A
tooling / research foundation =
IMPLEMENTED / AVAILABLE
```

It provides:

```text
controlled labeled-matrix format
validation
export
sealing workflow
read-only evidence extraction
privacy boundary
```

It does NOT mean:

```text
old 12-device / 48-sample empirical matrix completed
```

Canonical:

```text
old 12-device / 48-sample campaign =
NOT REQUIRED
NOT TASK-04 BLOCKER

full historical physical matrix campaign =
NOT CLAIMED COMPLETED
```

No future roadmap text may conflate:

```text
research tooling implemented
```

with:

```text
large empirical campaign completed
```

---

# 4. Permanent Architecture Principles

Permanent R5 principles:

```text
normalized evidence
!= classification
!= identity proof

classification is advisory

classification is not authorization

classification is not a security decision

high evidence support
!= probability
!= ground truth

row count
!= vote count

same origin interpreted by multiple knowledge systems
!= multiple independent votes

raw packets are non-durable

raw User-Agent is non-durable

raw Client Hints are non-durable

no cross-MAC identity merge

unknown is valid

insufficient_evidence is valid

conflicting_evidence is valid

recognized_out_of_scope is valid

Task-01 evidence storage
!= classification storage

external artifact
!= runtime schema

runtime classification =
offline capable

runtime required Internet =
zero

pure classification core =
no I/O and no wall clock

classification meaning =
versioned policy artifact

snapshot membership =
immutable ingest watermark
+
event-time window
+
binding authority

knowledge freshness =
explicit deterministic classifier input

all classification-relevant immutable artifacts
remain retained while referenced
```

---

# 5. Required Pre-Task-04 Program

```text
TASK-01 Evidence Foundation
DONE

TASK-02 Core Sensor
DONE

TASK-03 Portal Evidence
DONE

TASK-03A Research Tooling
DONE

        ↓

PRE-TASK-04 FOUNDATION CLOSURE

OPT-01W
Task-01 Global Ingest Watermark
+
Complete Snapshot Read Boundary

OPT-SRC1
Evidence Source Binding Timeline
+
Health Clock / Evaluability Policy

OPT-02A
tcp_syn/2 Minimal Protocol Evidence
+
p0f Adapters / Conformance

OPT-03A
Bounded Client Hints Experiment
+
Portal Liveness Heartbeat

OPT-KB1
Fingerbank Static Inspection
+
Canonical DHCP Import

OPT-KB2A
p0f Conformance Oracle

OPT-KB2B
Production TCP Knowledge Corpus

OPT-KB3
IEEE Assignment Registry Import

OPT-KB4
Classification Taxonomy / Alias Layer

OPT-POL1
ClassificationPolicy
+
SnapshotResourcePolicy
+
KnowledgeFreshnessPolicy set

        ↓

MANDATORY PROOF GROUPS A–F PASS

        ↓

TECHLEAD11 TASK-04 DECOMPOSITION

        ↓

OWNER IMPLEMENTATION AUTHORIZATION
```

No Task-04 implementation task exists before this closure.

---

# PART I — TASK-01 SNAPSHOT / INGEST FOUNDATION

# 6. Why `ingested_at <= timestamp` Is Not Enough

Task-01 currently has:

```text
ingested_at
```

but no immutable monotonic commit generation shared by:

```text
device_fingerprint_evidence

device_fingerprint_source_health_events
```

Millisecond timestamps cannot be the authoritative snapshot boundary because:

```text
multiple commits may share a timestamp

wall-clock order is not commit order

clock equality is not a durable database generation

concurrent ingest can race snapshot construction
```

R5 therefore requires a real ingest-watermark domain before Task-04.

---

# 7. Canonical Global Ingest Sequence

Task-01 persistence SHALL gain an explicit:

```text
ingest_sequence
```

for BOTH:

```text
device_fingerprint_evidence

device_fingerprint_source_health_events
```

Properties:

```text
integer

positive

monotonically increasing

assigned by Task-01 storage owner

shared across both row families

never derived from UUID

never derived from SQLite rowid

never derived solely from wall clock

never reused after commit
```

This sequence is a public durable Task-01 read contract after its introduction.

---

# 8. Ingest Sequence Allocator

Canonical architecture:

```text
one Task-01 database
        ↓
one explicit durable sequence allocator
        ↓
evidence rows
+
source-health rows
```

The allocator state and row insert occur in the SAME SQLite write transaction.

Conceptually:

```text
BEGIN WRITE TRANSACTION

allocate next N ingest sequences

insert accepted evidence/health rows
with those sequences

advance durable committed watermark

COMMIT
```

Required invariant:

```text
watermark W visible to reader
→ every committed Task-01 classification row
with ingest_sequence <= W
is already committed and visible
```

An uncommitted write cannot advance the reader-visible committed watermark.

---

# 9. Batch Ingest

For a successfully committed batch containing N accepted Task-01 rows:

```text
allocate one ordered sequence range
```

Each inserted classification-relevant row receives one sequence.

The exact order inside one batch is deterministic and frozen by Task-01 write logic.

Recommended canonical allocation order:

```text
request canonical accepted-item order
```

The sequence is commit visibility identity, not fingerprint meaning.

Gaps, if implementation architecture ever permits them, MUST NOT affect snapshot semantics:

```text
membership =
sequence <= watermark
```

not:

```text
all integers must exist
```

---

# 10. Immutable Ingest Watermark

Canonical:

```text
IngestWatermark
```

contains at minimum:

```text
watermark_schema_version

database_generation_id

max_committed_ingest_sequence
```

`database_generation_id` protects against:

```text
DB replacement
restore
rebuild
sequence-domain reset
```

Therefore:

```text
watermark =
(database_generation_id, max_committed_ingest_sequence)
```

not integer alone.

---

# 11. Watermark Capture

EvidenceSnapshot construction starts by opening the Task-01 read boundary and capturing an immutable committed watermark.

Canonical:

```text
open read transaction
        ↓
capture database_generation_id
        ↓
capture max_committed_ingest_sequence
        ↓
construct snapshot against that watermark
```

The resulting snapshot records the exact watermark.

The service MUST NOT silently replace it with a newer watermark during pagination.

---

# 12. Same-Watermark Guarantee

Permanent invariant:

```text
same Task-01 database generation
+
same classification request
+
same ingest watermark
=
same eligible committed Task-01 row universe
```

subject only to source-row retention.

While required source rows still exist:

```text
replay with same watermark
→ same membership
```

Concurrent ingest with higher sequences cannot alter that snapshot.

---

# 13. Existing-Database Bootstrap

The current Task-01 schema predates ingest sequences.

R5 explicitly does NOT pretend that exact historical commit order can be reconstructed from:

```text
ingested_at
UUID
rowid
```

Migration therefore creates a new:

```text
database_generation_id
```

and a deterministic bootstrap sequence for rows already present.

Canonical migration rule:

```text
exclusive controlled migration transaction

existing rows receive deterministic bootstrap ingest_sequence values

bootstrap ordering is documented

initial post-migration watermark includes all
pre-existing committed rows
```

Important:

```text
bootstrap sequence
!= claimed historical original commit order
```

No valid immutable Task-04 watermark exists before this migration generation.

Historical rows may still participate in later snapshots because they are known to have existed before the initial post-migration watermark.

---

# 14. Watermark and Retention

Retention does not reset sequence state.

Deleting expired evidence:

```text
does not decrement watermark

does not reuse sequence values

does not create a new database generation
```

If an old retained classification requires evidence rows that have already expired:

```text
full Level-A replay may no longer be possible
```

as defined later.

---

# 15. Source Health Uses the Same Watermark

Source-health rows use the exact same:

```text
database_generation_id
+
ingest_sequence
```

domain.

Permanent:

```text
health row committed after watermark W
does not exist in snapshot W
```

even when:

```text
health.observed_at
```

describes an earlier outage.

A later snapshot with a later watermark may legitimately reconstruct that historical outage.

This is expected deterministic behavior.

---

# 16. `snapshot_as_of_utc`

R5 retains:

```text
snapshot_as_of_utc
```

only as explicit temporal/audit metadata.

It is NOT the authoritative database commit boundary.

Canonical distinction:

```text
ingest_watermark
→ exact central committed row universe

snapshot_as_of_utc
→ human/application temporal context
```

No snapshot relies solely on:

```text
ingested_at <= snapshot_as_of_utc
```

for deterministic DB membership.

---

# PART II — SOURCE AUTHORITY / BINDING TIMELINE

# 17. EvidenceSourceBindingTimeline

A single current map is insufficient.

R5 freezes:

```text
EvidenceSourceBindingTimeline
```

as a versioned deployment-side artifact.

It is NOT part of KnowledgeBundle.

It describes which producer/capture source is authoritative for which Site/source interval.

---

# 18. Binding Epoch

Minimum immutable binding epoch:

```text
binding_epoch_id

site_id

origin_group

source_kind

capture_source_id

producer_id

required

effective_from_utc

effective_to_utc
```

Interval:

```text
[effective_from_utc, effective_to_utc)
```

`effective_to_utc = null` is allowed only for the currently open epoch.

No:

```text
producer_id if required
```

exists in R5.

`producer_id` is mandatory authority identity.

---

# 19. Timeline Identity

An immutable timeline artifact records:

```text
source_binding_timeline_id

schema_version

created_at_utc

content_sha256

ordered binding epochs
```

Changing any:

```text
producer
capture source
source kind
origin mapping
Site
effective boundary
required state
```

creates new immutable timeline content/identity.

---

# 20. Multi-Epoch Snapshot Windows

R5 ALLOWS a classification window to span multiple binding epochs.

Example:

```text
window start
    ↓
sensor binding epoch A
    ↓
source replacement
    ↓
sensor binding epoch B
    ↓
window end
```

EvidenceSnapshot records all intersecting epochs.

No single-map approximation.

---

# 21. Row Authority

Evidence membership requires:

```text
row.site_id
row.source_kind
row.capture_source_id
row.producer_id
row.observed_at
```

to match an authorized binding epoch.

Canonical:

```text
row observed_at belongs to epoch E

AND

(site_id,
 origin_group,
 source_kind,
 capture_source_id,
 producer_id)

matches E
```

The same rule applies to source-health events.

---

# 22. Binding Boundary Semantics

At exact boundary:

```text
epoch A effective_to_utc = T
epoch B effective_from_utc = T
```

then:

```text
observed_at < T
→ A

observed_at >= T
→ B
```

No overlap ambiguity is allowed for the same exclusive binding slot unless the timeline explicitly models multiple concurrent authorized producers.

---

# 23. Concurrent Authorized Bindings

If architecture intentionally permits more than one authorized producer for one origin/source interval:

```text
both must appear explicitly
as separate binding epochs/records
covering the interval
```

No implicit secondary source.

No inference from arrived rows.

---

# 24. Binding-Anomaly Rows

Rows that satisfy Site/MAC/time but fail binding authority are excluded from classification.

Examples:

```text
wrong producer

wrong capture_source_id

old source after epoch end

unexpected new source

source kind emitted from unregistered producer
```

They may be counted as:

```text
snapshot_scope_anomalies
```

for engineering evidence.

They do not enter OriginAssessment.

They do not become negative evidence.

---

# 25. Health Anchor at Binding Changes

Health state does NOT automatically flow from one binding epoch into another.

For each binding epoch, reconstruction searches health events authorized within that epoch.

At a new epoch boundary:

```text
health starts unknown
```

until an event/heartbeat for that binding establishes state.

Therefore source replacement cannot inherit an old producer's `available`.

---

# PART III — EVIDENCE SNAPSHOT

# 26. EvidenceSnapshot Request

Task-04 never invents:

```text
last N minutes
latest evidence
current session window
```

Required request inputs:

```text
site_id

observed_mac

window_start_utc

window_end_utc

ingest_watermark

snapshot_as_of_utc

source_binding_timeline_id

snapshot_resource_policy_id
```

Future Task-05/caller owns:

```text
WHEN classification runs

WHICH Visit/session/current-device interval
becomes [window_start, window_end)
```

---

# 27. Evidence Membership

A row belongs only when ALL are true:

```text
site_id matches

observed_mac matches

window_start_utc <= observed_at < window_end_utc

row.ingest_sequence <= watermark.max_committed_ingest_sequence

row belongs to watermark.database_generation_id

row is authorized by applicable binding epoch
```

No other hidden recency policy.

---

# 28. Source-Health Membership

Source-health membership uses:

```text
same ingest watermark

same binding authority

same database generation
```

plus the bounded health records required to reconstruct each intersecting binding epoch.

This may include:

```text
latest eligible health event before an epoch/window segment start

+
eligible transitions/heartbeats inside the segment
```

No health event after watermark is visible.

---

# 29. Complete Pagination

Current Task-01 page limit:

```text
<= 500
```

Classification MUST consume pages deterministically until:

```text
next_cursor = none
```

for every required evidence/read family.

Forbidden:

```text
first 500 rows
→ classify
```

---

# 30. SnapshotResourcePolicy

Specific production row ceilings are NOT frozen in R5.

R5 freezes a versioned:

```text
SnapshotResourcePolicy
```

containing bounded controls such as:

```text
page_size

max_evidence_rows

max_source_health_rows

max_snapshot_bytes

max_snapshot_build_duration

memory budget
```

Exact first production values remain:

```text
REQUIRED / UNRESOLVED
```

until sizing proof.

---

# 31. Resource-Limited Behavior

If deterministic pagination cannot be completed under the accepted resource policy:

```text
snapshot_status =
resource_limited
```

Classification is not executed.

Affected origins become:

```text
not_evaluable
reason = resource_limited
```

Forbidden:

```text
partial first-N classification
```

---

# 32. Snapshot Evidence Descriptor

Canonical snapshot identity includes every classification-relevant evidence metadata field.

Minimum evidence descriptor:

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

`observed_ip` is NOT a Task-04 classification input in V1 and SHALL NOT be used by adapters/fusion.

If a future classifier proposes use of observed IP semantics:

```text
new architecture/privacy review required
```

---

# 33. Snapshot Health Descriptor

Minimum:

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

No health-semantic input is omitted from identity.

---

# 34. Snapshot Binding Descriptor

Snapshot identity also includes every intersecting authorized binding epoch:

```text
binding_epoch_id

site_id

origin_group

source_kind

capture_source_id

producer_id

required

effective_from_utc

effective_to_utc
```

plus timeline ID/digest.

---

# 35. Canonical Snapshot Ordering

Evidence rows:

```text
origin_group
source_kind
capture_source_id
producer_id
observed_at
ingest_sequence
evidence_id
```

Health rows:

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

No SQLite incidental order.

No page-boundary effect.

---

# 36. EvidenceSnapshot Identity

Canonical snapshot manifest includes:

```text
snapshot_format_version

site_id

observed_mac

window_start_utc

window_end_utc

snapshot_as_of_utc

database_generation_id

max_committed_ingest_sequence

source_binding_timeline_id

source_binding_timeline_digest

snapshot_resource_policy_id

ordered binding descriptors

ordered evidence descriptors

ordered health descriptors

scope-anomaly summary
```

Serialization:

```text
canonical UTF-8 JSON
sorted object keys
stable arrays
no insignificant whitespace
```

Identity:

```text
evidence_snapshot_digest =
SHA-256(canonical manifest)
```

Snapshot ID is immutable and tied to that manifest.

---

# PART IV — SOURCE HEALTH / CLOCK MODEL

# 37. Health Has Three Time Concepts

R5 explicitly separates:

```text
source observed_at

central ingested_at

central ingest_sequence / watermark visibility
```

Their responsibilities are different.

---

# 38. `observed_at`

`observed_at` expresses:

```text
when the producer says
the source state/heartbeat occurred
```

It defines source-state event-time placement.

It does NOT define whether central Task-01 knew about the event at a particular prior snapshot.

---

# 39. `ingested_at`

`ingested_at` expresses:

```text
central Task-01 receive/commit time metadata
```

It is retained for:

```text
delivery-delay diagnostics

clock/skew proof

audit
```

It is NOT the immutable commit generation.

---

# 40. `ingest_sequence`

`ingest_sequence` determines:

```text
whether the row existed
in the central Task-01 row universe
at snapshot watermark W
```

This is the authoritative visibility boundary.

---

# 41. Source Clock Skew

R5 does NOT invent a second fingerprint-specific clock-skew value.

Health events remain subject to the accepted Task-01 source timestamp validation contract.

Current repository default:

```text
max future source-clock skew =
120 seconds
```

ClassificationPolicy records the exact SourceHealthPolicy that references the applicable Task-01 timestamp contract.

No unbounded producer-clock assumption.

---

# 42. Delayed / Backfilled Health

A delayed health event may have:

```text
observed_at = earlier time

ingest_sequence = later commit
```

For snapshot watermark before that commit:

```text
event does not exist
```

For a later snapshot:

```text
event may reconstruct
the earlier source-state interval
```

This is deterministic and expected.

---

# 43. Heartbeat Freshness

Heartbeat freshness uses:

```text
source observed_at
```

under the bounded Task-01 skew contract.

This ensures a very late backfilled heartbeat does NOT become falsely "fresh now" merely because:

```text
ingested_at = now
```

Central visibility remains controlled separately by ingest watermark.

---

# 44. SourceHealthPolicy

Health/evaluability semantics are versioned in:

```text
SourceHealthPolicy
```

It contains, per source/binding family:

```text
expected heartbeat behavior

freshness timeout

accepted Task-01 clock-skew contract reference

accepted delivery-delay semantics

unsupported semantics

interval reconstruction rules

backfill behavior
```

Exact freshness/grace values must be justified by proof.

They are not hidden mutable config.

---

# 45. Network Sensor Heartbeat

Current network sensor contract:

```text
heartbeat interval =
300 seconds
```

for:

```text
dhcp
tcp_syn
tls_client
quic_client
```

The production SourceHealthPolicy must be proven against real scheduling/jitter before freezing its freshness timeout.

R5 therefore does NOT invent:

```text
600 seconds
```

as an automatic canonical timeout.

---

# 46. Portal Heartbeat

Before Task-04, enabled portal evidence must gain periodic source liveness independent of visitor traffic.

Target architecture:

```text
portal source-health heartbeat
≈ network source-health model
```

Initial implementation target:

```text
300-second heartbeat cadence
```

must itself be proven under OPT-03A before acceptance.

No client evidence is required to generate the heartbeat.

---

# 47. Transport-Outage Truth

Critical distinction:

## CASE A — Source Component Failure, Transport Alive

If producer can still reach Task-01:

```text
producer may send unavailable
```

and central DB can know it live.

## CASE B — Producer → Task-01 Transport Failure

The unavailable event cannot travel over the failed channel.

Therefore central semantics are:

```text
last accepted heartbeat ages out
→ health becomes unknown
```

NOT:

```text
central magically knows unavailable
```

---

# 48. Transport Recovery Backfill

If producer reliably tracked outage start/end while transport was unavailable, on recovery it MAY send bounded historical health events:

```text
unavailable at known outage start

available at known recovery point
```

A later watermark may then reconstruct the prior outage.

If the producer cannot establish reliable historical boundaries:

```text
no fabricated unavailable interval
```

Central history remains:

```text
unknown
```

for the gap.

---

# 49. Binding-Epoch Health Reconstruction

For each binding epoch segment:

```text
find latest visible eligible health state
inside the epoch at/before segment start

apply visible transitions/heartbeats

expire health according to SourceHealthPolicy

never carry state across epoch boundary
```

A source topology transition is therefore explicit.

---

# 50. SourceEvaluability

Persisted source-health remains:

```text
available
unavailable
unsupported
```

Derived classification state:

```text
evaluable
partially_evaluable
not_evaluable
unknown
```

Canonical:

### evaluable

Required classification interval for the binding is fully covered by trustworthy `available` health.

### partially_evaluable

At least one relevant interval is evaluable but another interval is:

```text
unavailable
unsupported
unknown/stale
```

### not_evaluable

No relevant interval is available and the interval is positively known to be:

```text
unavailable
or
unsupported
```

### unknown

No usable available interval exists and source health coverage itself cannot be established reliably.

---

# 51. Health Is Not Negative Evidence

Permanent:

```text
unavailable
!= no fingerprint

unsupported
!= no fingerprint

unknown health
!= no fingerprint

transport outage
!= negative classification evidence
```

Health affects evaluability only.

---

# PART V — TCP_SYN/2 MINIMAL EVIDENCE

# 52. tcp_syn/2 Principle

`tcp_syn/2` is:

```text
minimum protocol-semantic durable facts
required by admitted passive fingerprint adapters
```

It is NOT:

```text
persist every potentially interesting header value
```

Future speculative usefulness is not enough to persist a stronger correlator.

---

# 53. tcp_syn/2 Supported Initial Scope

```text
IPv4

outbound guest TCP SYN

SYN=1
ACK=0

unfragmented

complete required Ethernet/IP/TCP header bytes

current controlled RSPAN placement
```

No claim of:

```text
IPv6 parity
SYN-ACK parity
fragment reassembly parity
universal p0f parity
```

---

# 54. tcp_syn/2 Minimal Durable Fields

Conceptual V2 top-level facts:

```text
ip_version = 4

observed_ttl

ip_option_length_bytes

ip_id_zero

ip_df

ip_reserved_flag

ip_ecn_bits

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

tcp_option_records
```

Eligibility already establishes:

```text
SYN = true
ACK flag = false
```

so redundant durable eligibility flags are not required unless schema validation demonstrably needs them.

---

# 55. Exact IPv4 ID Is Not Durable

V2 initial durable fact:

```text
ip_id_zero: bool
```

NOT:

```text
exact ip_id integer
```

because admitted p0f request semantics require the zero/non-zero relationship, not the exact persistent ID.

An adapter requiring exact ID in the future must pass a new evidence-minimization/privacy gate before schema expansion.

---

# 56. TCP Timestamp Minimization

V2 persists:

```text
tcp_timestamp_present

tcp_timestamp_value_zero

tcp_timestamp_echo_nonzero
```

through the canonical option record.

It does NOT persist:

```text
exact timestamp value

exact timestamp echo value
```

because these values are not required for the admitted p0f request fingerprint semantics and create unnecessary durable correlation surface.

---

# 57. One Canonical TCP Option Representation

R5 removes the duplicate durable model:

```text
tcp_option_kind_sequence
+
tcp_option_records
```

There is exactly one durable canonical source:

```text
ordered tcp_option_records
```

Option-kind sequence is derived from record order.

No separate durable copy.

---

# 58. TCP Option Record Variants

Ordered records represent actual observed option structure.

Conceptually:

```text
kind
declared_length
available_value_length
structure_state
```

and only the minimum parsed semantics required by admitted adapters.

Examples:

### MSS

```text
kind = 2
mss
```

### Window Scale

```text
kind = 3
window_scale_raw
```

### SACK Permitted

```text
kind = 4
```

### Timestamp

```text
kind = 8
timestamp_value_zero
timestamp_echo_nonzero
```

### EOL

```text
kind = 0
eol_padding_length
eol_padding_nonzero
```

### Unknown Option

```text
kind
declared_length
available_value_length
```

No raw option bytes.

---

# 59. Derived Option Structure State

There is no independently mutable durable:

```text
global option_structure_state
```

if it can be derived from `tcp_option_records`.

The adapter/validator derives:

```text
well_formed

malformed_but_observable
```

from canonical records.

No duplicated fields capable of disagreement.

---

# 60. Malformed Options

R5 preserves the R4 semantic correction:

```text
actual packet/header incompleteness
→ reject event

malformed option syntax
inside a complete observed header
→ retain event
```

Examples retained as packet facts where bytes physically exist:

```text
invalid MSS option declared length

invalid WS option declared length

invalid timestamp option declared length

unknown option with abnormal declared length

EOL with nonzero padding

abnormal WS value

other p0f-observable malformed syntax
```

No silent disappearance merely because an external matcher would later mark:

```text
bad
```

---

# 61. Genuine Structural Rejection

Reject only when classification-required bytes are physically unavailable or base packet structure is invalid beyond observable fingerprint semantics.

Examples:

```text
captured frame shorter than declared IP packet

IPv4 fixed header incomplete

illegal IPv4 IHL

TCP fixed header incomplete

TCP data offset below legal minimum

TCP data offset points outside available declared packet

unusable fragmentation under V2 scope
```

Exact boundary is frozen by p0f conformance fixtures.

---

# 62. p0f Adapter

Transient:

```text
tcp_syn/2
→ p0f runtime representation
```

may derive:

```text
option token sequence

quirks

payload class

TTL/distance representation

window expression input
```

None of these become durable Task-02 evidence.

---

# 63. K2A vs K2B

Permanent split:

```text
K2A =
p0f semantics / conformance oracle

K2B =
production TCP knowledge corpus
```

K2A proves:

```text
CaptivPortal interprets p0f correctly
```

K2B answers:

```text
which TCP reference signatures are actually admitted
for production classification
```

The pinned p0f corpus is NOT production truth merely because p0f is the oracle.

---

# 64. tcp_syn/2 Evidence-Minimization Rule

Every proposed durable V2 field must prove:

```text
required by at least one admitted adapter/classification contract

bounded representation

no less-sensitive semantic equivalent is sufficient
```

Failure of any condition:

```text
field removed
```

Exact:

```text
TCP timestamp
TCP timestamp echo
IPv4 ID
```

must remain absent unless this gate is reopened with new evidence.

---

# PART VI — PORTAL / CLIENT HINTS

# 65. portal_headers/2 Status

```text
portal_headers/2 =
CANDIDATE
NOT FROZEN
```

Candidate high-entropy fields remain:

```text
Sec-CH-UA-Model

Sec-CH-UA-Platform-Version

Sec-CH-UA-Form-Factors
```

Each must earn inclusion independently.

---

# 66. Critical-CH

For Device Fingerprint V1:

```text
Critical-CH =
FORBIDDEN
```

No classification enrichment justifies forcing a browser retry.

Missing high-entropy hints are normal.

Fingerprint collection may not create:

```text
portal retry dependency

Authorization dependency

classification-driven navigation dependency
```

---

# 67. Accept-CH

`Accept-CH` may be used only as:

```text
bounded optional enrichment
```

Required real-flow proof includes:

```text
request hint negotiation

subsequent eligible same-origin request

normalization

end of collection lifecycle
```

---

# 68. Accept-CH Teardown

High-entropy hints must not remain requested indefinitely.

Preferred supported teardown:

```text
Clear-Site-Data: "clientHints"
```

or another proven standards-compliant bounded mechanism.

No continuous `Accept-CH` after the intended collection window.

If bounded lifecycle cannot be proven for a client class:

```text
high-entropy enrichment not admitted
for that client class
```

---

# 69. Portal Privacy

Permanent:

```text
raw UA never durable

raw Client Hints never durable

raw high-entropy CH never logged

raw high-entropy CH never placed in asynchronous queue

normalized approved P1 facts only
```

No JS fingerprint fallback.

---

# PART VII — EXTERNAL KNOWLEDGE / CANONICAL IMPORT

# 70. Runtime Vendor-Schema Prohibition

Runtime Task-04 classifier MUST NOT read:

```text
Fingerbank SQLite vendor tables

IEEE CSV layout

raw p0f.fp

other external source-specific runtime schemas
```

---

# 71. Canonical Import Pipeline

Every external source:

```text
external artifact
        ↓
quarantine / read-only inspection
        ↓
source digest
        ↓
license / provenance review
        ↓
validated source-specific importer
        ↓
CaptivPortal canonical KnowledgeBundle records
        ↓
immutable accepted bundle
        ↓
runtime
```

The original external artifact is not required for normal runtime classification after successful canonical import.

---

# 72. KnowledgeBundle Source Manifest

Each source manifest records:

```text
source_name

source_version / source metadata

retrieved_at_utc

source_digest

importer_version

license identifier/reference

redistribution status

commercial-use status

modification status

review basis

source_character

freshness_policy_id
```

---

# 73. Freshness State Model

One freshness enum only:

```text
fresh
stale
expired
```

Separate orthogonal source character:

```text
current
legacy
```

Therefore:

```text
legacy
!= stale

legacy
!= expired
```

A legacy corpus may be fresh under its accepted review policy, stale, or expired.

---

# 74. KnowledgeFreshnessPolicy

Every changing mandatory knowledge source requires an immutable versioned:

```text
KnowledgeFreshnessPolicy
```

The architecture freezes the mechanism, not guessed ages.

Policy fields may include:

```text
policy_id

policy_version

source_family

policy_basis

fresh threshold

stale threshold

expired behavior

claim-grade cap when stale

refresh/review requirement
```

Exact thresholds remain:

```text
REQUIRED / UNRESOLVED
```

until corresponding proof gate evaluates:

```text
actual source update behavior

artifact metadata

provider documentation/cadence

operational refresh capability

failure tolerance

Owner policy
```

---

# 75. No Magic Knowledge Ages

R5 intentionally removes unproven R4 values such as:

```text
Fingerbank 30 / 90

IEEE 90 / 180

legacy p0f 365
```

They have no canonical status.

A mandatory source cannot be production-admitted while its required freshness policy remains unresolved.

---

# 76. `knowledge_evaluation_at_utc`

Knowledge freshness affects classification outcome.

Therefore classification request explicitly contains:

```text
knowledge_evaluation_at_utc
```

Pure classification logic never calls:

```text
now()
system clock
datetime.utcnow()
```

to determine freshness.

---

# 77. Different Knowledge Evaluation Time

Canonical:

```text
same EvidenceSnapshot
+
same KnowledgeBundle
+
same ClassificationPolicy
+
different knowledge_evaluation_at_utc
=
different classification request
```

A later request may legitimately change:

```text
fresh
→ stale
→ expired
```

behavior.

The exact input is permanently stored.

---

# 78. Mandatory Knowledge Source Admission

A mandatory source counts toward offline bundle sufficiency only when, at admission/evaluation time, it is:

```text
legally admitted

schema-compatible

taxonomy-compatible

canonically imported

runtime-usable

not expired under accepted freshness policy
```

Physical presence of records alone is insufficient.

---

# 79. Legacy TCP Corpus

A legacy K2B source may remain admitted only when:

```text
explicit source_character = legacy

accepted freshness/review policy exists

claim grade limitations are explicit

source is not expired
```

No hard-coded legacy age exists until proven.

---

# PART VIII — TAXONOMY / IDENTITIES

# 80. classification_taxonomy_v1

Dimensions:

```text
platform_family

device_class

manufacturer_family

model_family
```

---

# 81. Platform Enum

Allowed in-scope resolved values:

```text
android
ios
windows
macos
chromeos
linux
```

No source value is squeezed into this set.

---

# 82. Device Class Enum

Phase-1:

```text
smartphone
tablet
laptop
```

No:

```text
Phone → smartphone automatically

Mobile → smartphone automatically

Desktop → laptop automatically
```

unless an admitted exact source mapping proves semantic equivalence.

---

# 83. Recognized Out-of-Scope

Known source taxon such as:

```text
TV
printer
camera
watch
wearable
desktop workstation
IoT
```

does NOT become:

```text
smartphone
tablet
laptop
```

Canonical:

```text
recognized_out_of_scope
```

with preserved source taxon reference.

---

# 84. Broad Taxon

A source value broader than target taxonomy, for example:

```text
Mobile
Computer
Desktop-form-factor
```

that does not resolve one canonical value is:

```text
broad_unresolved source information
```

It does not become recognized-out-of-scope unless the taxon is proven disjoint from the V1 in-scope set.

It contributes explainability, not a guessed value.

---

# 85. Manufacturer Identity

Canonical:

```text
manufacturer_id
display_label
source aliases
```

String equality is not identity.

---

# 86. Model Identity

Canonical:

```text
model_family_id
display_label
source aliases
```

No heuristic merge from:

```text
SM-S928B
Galaxy S24 Ultra
Samsung SM-S928B
```

without admitted mapping.

---

# 87. Alias Rules

Forbidden automatic aliasing based only on:

```text
case

punctuation

prefix stripping

substring similarity

edit distance

marketing-name similarity
```

Alias mappings are immutable KnowledgeBundle content.

---

# 88. IEEE Registry

Raw IEEE result means:

```text
mac_assignment_org
```

not:

```text
device manufacturer
```

Supported:

```text
MA-L
MA-M
MA-S
```

with longest-prefix behavior.

---

# 89. Locally Administered MAC

If U/L bit indicates locally administered address:

```text
IEEE registry lookup =
NOT ELIGIBLE
```

No cross-MAC inference.

---

# 90. IEEE Manufacturer Claim

Only an explicit accepted mapping:

```text
assignment_org_id
→ canonical manufacturer_id
```

may generate manufacturer evidence.

Without mapping:

```text
assignment organization only
```

---

# PART IX — ORIGIN PURITY

# 91. Origin Groups

Exactly:

```text
dhcp
portal
tcp
tls
quic
mac_registry
```

---

# 92. Origin Inputs

```text
dhcp
→ DHCP evidence only

portal
→ portal evidence only

tcp
→ TCP SYN evidence only

tls
→ TLS evidence only

quic
→ QUIC evidence only

mac_registry
→ current observed MAC only
```

---

# 93. Fingerbank V1 Purity

Static K1 Fingerbank:

```text
DHCP-only
```

No hidden:

```text
MAC
UA
Client Hints
TCP
TLS
QUIC
```

Fingerbank Cloud, if ever enabled as fusion input:

```text
DHCP-only
```

Multi-origin Cloud output:

```text
explainability-only
excluded from fusion
```

unless a future architecture defines attributable subclaims.

---

# 94. JA4

Permanent:

```text
JA4 observed
!= device platform

JA4 observed
!= device class

JA4 observed
!= manufacturer

JA4 observed
!= model
```

No admitted local reference:

```text
origin produces no classification claim
```

---

# PART X — PURE CLASSIFICATION CORE

# 95. Mandatory Pure-Core Boundary

Conceptual deterministic function:

```text
EvidenceSnapshot
+
SourceEvaluability
+
KnowledgeBundle
+
ClassificationPolicy
+
knowledge_evaluation_at_utc
+
ClassifierArtifactManifest
        ↓
OriginAssessments
        ↓
ClassificationResult
```

---

# 96. Pure Core Prohibitions

Pure core has:

```text
NO DB access

NO network access

NO filesystem discovery

NO current-clock reads

NO mutable global config

NO vendor-schema reads

NO environment-variable reads

NO telemetry side effects

NO classification persistence
```

Same exact inputs:

```text
→ same exact semantic result
```

---

# 97. Service Layer Ownership

Service/application layer owns:

```text
Task-01 reads

watermark capture

snapshot construction

binding-authority validation

SourceEvaluability reconstruction

bundle loading

policy loading

classifier artifact loading

persistence

telemetry

failure mapping
```

No service-layer hidden fusion rule.

---

# PART XI — CLASSIFICATION POLICY

# 98. ClassificationPolicy

Classification meaning is an immutable versioned artifact.

Minimum:

```text
classification_policy_id

policy_schema_version

content_sha256

claim-grade ordering

same-origin conflict policy

cross-origin conflict policy

support-level rules

final dimension-status rules

global-status derivation

out-of-scope precedence

SourceHealthPolicy reference

SnapshotResourcePolicy reference

KnowledgeFreshnessPolicy references
```

---

# 99. Policy Retention

Classification result records:

```text
classification_policy_id
classification_policy_digest
```

A referenced policy cannot be deleted while any retained classification points to it.

---

# 100. Claim Grades

Exactly:

```text
direct

strong_derived

supporting
```

Semantic order:

```text
direct
>
strong_derived
>
supporting
```

This ordering is explicit policy, not hidden source priority.

---

# 101. `direct`

Means:

```text
source directly declares the semantic value
at required granularity
```

It does NOT mean:

```text
ground truth
identity proof
unspoofable
security authority
```

---

# 102. `strong_derived`

Means:

```text
accepted deterministic knowledge mapping
resolves one canonical semantic value
without ambiguity
```

---

# 103. `supporting`

Means weaker/broader/legacy/stale-capped advisory support permitted by the active policy.

---

# PART XII — SAME-ORIGIN ASSESSMENT

# 104. OriginDimensionAssessment States

Internal states exactly:

```text
resolved

recognized_out_of_scope

ambiguous

conflicting

no_claim

not_evaluable
```

`ambiguous` is INTERNAL only.

It is never persisted as a final classification dimension status.

---

# 105. Same-Origin Semantic Dedup

Within one origin:

```text
identical semantic repetitions
→ one variant

packet count
→ ignored for voting

row count
→ ignored for voting
```

Counts remain explainability metadata only.

---

# 106. Candidate Ambiguity

A deterministic knowledge lookup returning multiple compatible possibilities is:

```text
ambiguous
```

Example:

```text
candidate A = Android / smartphone
candidate B = Android / tablet
```

Projection:

```text
platform =
resolved android

device_class =
ambiguous
```

This is not automatically `conflicting`.

---

# 107. Same-Origin Concrete Claim Matrix

For one dimension:

1. Determine all concrete claims and their grades after semantic dedup.
2. Select the highest claim grade present.
3. Compare distinct outcomes at that grade.

Canonical:

```text
same highest grade + same outcome
→ resolved

same highest grade + incompatible outcomes
→ conflicting
```

---

# 108. Stronger vs Weaker Same-Origin Disagreement

If one concrete outcome has higher grade than an incompatible lower-grade claim:

```text
higher-grade outcome retained

origin state = resolved

origin_contradiction = true

lower-grade contradiction preserved
```

No majority.

No row count.

---

# 109. Two Knowledge Interpreters on One Origin

Example:

```text
Fingerbank DHCP interpretation

+
another accepted DHCP interpretation
```

They remain ONE DHCP origin.

If they disagree:

```text
same-origin matrix applies
```

They do not become independent corroboration.

---

# 110. Temporal Same-Origin Conflict

Example:

```text
portal observation A → windows

portal observation B → android
```

at the same highest grade within one snapshot:

```text
portal platform OriginAssessment =
conflicting
```

No "latest wins".

---

# 111. TCP Same-Origin Variants

Distinct TCP fingerprints observed during one window remain one TCP origin.

If accepted K2B interpretation yields incompatible equal-grade concrete values:

```text
TCP OriginAssessment =
conflicting
```

No fingerprint frequency majority.

---

# 112. Broad Source Information

Broad taxon incapable of selecting one canonical target value:

```text
does not become concrete claim
```

If no concrete claim exists but broad admitted information exists:

```text
OriginDimensionAssessment =
ambiguous
```

with reason:

```text
broader_than_target_taxonomy
```

---

# PART XIII — CROSS-ORIGIN CONFLICT MATRIX

# 113. Fusion Input

Fusion receives at most:

```text
one OriginAssessment per origin group
```

No raw evidence rows.

---

# 114. Highest-Grade Concrete Outcome Rule

For one classification dimension:

```text
collect independent-origin concrete claims
that are evaluable/usable
```

Find highest grade present.

At that grade:

```text
all same semantic outcome
→ candidate selected

two or more incompatible outcomes
→ conflicting_evidence
```

No source-name priority.

---

# 115. Direct vs Direct

Different concrete values:

```text
conflicting_evidence
```

No winner.

---

# 116. Direct vs Strong-Derived

Different values:

```text
direct retained

contradiction recorded

final status may remain resolved/out-of-scope

support_level capped at medium
```

---

# 117. Direct vs Supporting

Different values:

```text
direct retained

contradiction recorded

support_level cannot exceed medium
```

---

# 118. Strong-Derived vs Strong-Derived

Different values:

```text
conflicting_evidence
```

---

# 119. Strong-Derived vs Supporting

Different values:

```text
strong_derived retained

contradiction recorded

support_level capped at medium
```

---

# 120. Supporting vs Supporting

Different values:

```text
conflicting_evidence
```

No popularity/majority tie-break.

---

# 121. In-Scope vs Out-of-Scope

`recognized_out_of_scope` is a concrete semantic outcome for conflict evaluation.

Same highest grade:

```text
in-scope
vs
recognized out-of-scope
→ conflicting_evidence
```

If one side has higher grade:

```text
higher-grade outcome retained

lower contradiction recorded

support capped according to policy
```

---

# 122. Resolved vs Broad/Unresolved Taxon

A broad taxon that could include the resolved value:

```text
does NOT contradict
```

It remains explanation only.

A taxon proven disjoint from the resolved value is an out-of-scope/incompatible concrete claim and enters the normal matrix.

---

# PART XIV — FINAL DIMENSION STATUS

# 123. Final Status Enum

Exactly:

```text
resolved

recognized_out_of_scope

unknown

insufficient_evidence

conflicting_evidence
```

No `ambiguous` final status.

---

# 124. `resolved`

Means:

```text
fusion policy selected exactly one
in-scope canonical value
```

A lower-grade contradiction may exist but must be recorded.

---

# 125. `recognized_out_of_scope`

Means:

```text
fusion selected exactly one recognized semantic taxon
that is explicitly outside this dimension's V1 target taxonomy
```

and no equal/higher incompatible claim prevents selection.

Canonical value remains:

```text
null
```

while the external/out-of-scope taxon reference is preserved.

---

# 126. `unknown`

Means:

```text
at least one relevant origin/evidence path is evaluable

evidence exists

but admitted knowledge emits no semantic claim
for this dimension
```

Example:

```text
known JA4 observed
but no admitted JA4 knowledge
```

---

# 127. `insufficient_evidence`

Means no incompatible concrete claims exist, but resolution is impossible because:

```text
no adequate evaluable evidence exists

OR

only broad/non-resolving information exists

OR

OriginAssessment is ambiguous

OR

source coverage/resource/evaluability is insufficient
for a resolving claim
```

---

# 128. `conflicting_evidence`

Means:

```text
two or more incompatible concrete semantic outcomes
exist at the decisive equal claim grade
```

or an unresolved same-origin conflict reaches the decisive fusion level.

---

# 129. Final Status Precedence

Per dimension:

```text
1. decisive equal-grade incompatible concrete claims
   → conflicting_evidence

2. one selectable concrete in-scope outcome
   → resolved

3. one selectable concrete out-of-scope outcome
   → recognized_out_of_scope

4. semantic information exists but cannot resolve
   → insufficient_evidence

5. evaluable evidence exists but knowledge emits no semantic information
   → unknown

6. no adequate evaluable evidence
   → insufficient_evidence
```

No implementation discretion.

---

# PART XV — EVIDENCE SUPPORT LEVEL

# 130. Meaning

Canonical field:

```text
support_level
```

It means:

```text
ordinal evidence corroboration/support
```

not statistical probability.

Values:

```text
none
low
medium
high
```

---

# 131. High

```text
>=2 independent origin groups

agree on selected outcome

at least two claims are direct/strong_derived

no incompatible claim of any grade
```

---

# 132. Medium

Selected outcome has:

```text
>=1 direct or strong_derived origin
```

and no equal-grade decisive conflict.

Any retained contradiction from a lower grade caps support at:

```text
medium
```

---

# 133. Low

```text
selected outcome supported only by supporting-grade origins

no incompatible supporting-grade outcome
```

---

# 134. None

Used when final dimension:

```text
unknown

insufficient_evidence

conflicting_evidence
```

For:

```text
recognized_out_of_scope
```

support may be:

```text
low
medium
high
```

using the same evidence-support rules for the out-of-scope recognition itself.

---

# PART XVI — GLOBAL CLASSIFICATION STATUS

# 135. Global Status Enum

Exactly:

```text
classified

partial

recognized_out_of_scope

unknown

insufficient_evidence

conflicting_evidence
```

---

# 136. Global Derivation

Let the four dimensions be:

```text
platform
device_class
manufacturer
model
```

Derive in this exact precedence:

### Rule 1

If ANY dimension is:

```text
conflicting_evidence
```

then:

```text
global =
conflicting_evidence
```

even if other dimensions resolved.

### Rule 2

Else if ALL four dimensions are:

```text
resolved
```

then:

```text
global =
classified
```

### Rule 3

Else if AT LEAST ONE dimension is:

```text
resolved
```

then:

```text
global =
partial
```

### Rule 4

Else if no dimension is resolved and AT LEAST ONE is:

```text
recognized_out_of_scope
```

then:

```text
global =
recognized_out_of_scope
```

### Rule 5

Else if AT LEAST ONE dimension is:

```text
insufficient_evidence
```

then:

```text
global =
insufficient_evidence
```

### Rule 6

Else:

```text
global =
unknown
```

---

# 137. Global Examples

```text
platform resolved
device_class conflict
manufacturer unknown
model unknown

→ conflicting_evidence
```

```text
platform resolved
device_class resolved
manufacturer unknown
model unknown

→ partial
```

```text
platform recognized_out_of_scope
all others unknown

→ recognized_out_of_scope
```

```text
all dimensions unknown

→ unknown
```

```text
device_class ambiguous → insufficient
all others unknown

→ insufficient_evidence
```

No UI layer may reinterpret this.

---

# PART XVII — CLASSIFIER ARTIFACT IDENTITY

# 138. ClassifierArtifactManifest

Vague:

```text
classifier_artifact_identity
```

is replaced by an exact immutable manifest.

Minimum:

```text
classifier_artifact_id

repository_commit_sha

repository_tree_sha

classification_engine_semver

pure_core_contract_version

origin_adapter_versions

K2A matcher_implementation_version

classification_result_schema_version

snapshot_contract_version

manifest_sha256
```

---

# 139. Build Identity

If runtime later uses an artifact whose bytes are not uniquely implied by repository tree:

```text
build/package digest
```

is additionally mandatory.

For current clean repository-checkout runtime:

```text
commit SHA
+
tree SHA
```

remain required base identity.

---

# 140. Classifier Artifact Retention

Classifier manifest referenced by retained classification:

```text
MUST NOT DELETE
```

No audit record may point only to:

```text
"v1"
"current"
"latest"
```

---

# PART XVIII — CLASSIFICATION REQUEST IDENTITY

# 141. ClassificationRequestManifest

A deterministic request includes:

```text
EvidenceSnapshot ID/digest

SourceEvaluability digest

KnowledgeBundle ID/digest

ClassificationPolicy ID/digest

ClassifierArtifact ID/digest

knowledge_evaluation_at_utc
```

Canonical request digest:

```text
SHA-256(canonical request manifest)
```

Same exact request manifest:

```text
→ same pure-core result
```

---

# PART XIX — AUDIT / REPRODUCIBILITY

# 142. Level A

```text
EvidenceSnapshot
→ OriginAssessments
```

reproducible while required Task-01 rows remain retained.

Requires:

```text
snapshot manifest

watermark

binding timeline/epochs

evidence descriptors

health descriptors

KnowledgeBundle

ClassificationPolicy

classifier manifest

knowledge_evaluation_at
```

---

# 143. Level B

```text
OriginAssessments
→ ClassificationResult
```

must remain reproducible for full classification-history retention.

Classification persistence stores bounded canonical OriginAssessments or equivalent exact fusion inputs.

---

# 144. After Task-01 Evidence Expiry

After evidence/source-health retention removes old rows:

```text
full evidence → OriginAssessment replay
may no longer be possible
```

R5 states this explicitly.

It does NOT claim a digest alone equals full reproduction.

Level-B fusion audit remains possible.

---

# 145. Immutable Artifact Retention Rule

While referenced by any retained classification:

```text
MUST RETAIN:
KnowledgeBundle

EvidenceSourceBindingTimeline / epochs

ClassificationPolicy

SnapshotResourcePolicy

SourceHealthPolicy

KnowledgeFreshnessPolicy artifacts

ClassifierArtifactManifest
```

No referenced artifact may be garbage-collected.

---

# PART XX — KNOWLEDGE BUNDLE

# 146. Mandatory Offline Bundle

Before Task-04 acceptance, production candidate bundle must contain usable:

```text
classification_taxonomy_v1

alias mappings

K1 DHCP knowledge

K2B TCP knowledge

K3 portal semantic rules

K4 IEEE assignment registry/mappings
```

Optional:

```text
JA4 knowledge

Cloud cache
```

---

# 147. Mandatory Source Usability

A source counts only when:

```text
legal/governance PASS

canonical import PASS

schema compatibility PASS

taxonomy compatibility PASS

freshness policy resolved

freshness state != expired

runtime matcher/adapter usable
```

---

# 148. K1 Fingerbank

Static Fingerbank V1 interpretation remains:

```text
DHCP-only
```

Returns all deterministic compatible candidates.

No:

```text
first SQL row

hidden popularity

MAC/OUI augmentation

Cloud score recreation
```

---

# 149. K2A

p0f semantics/conformance.

Owns:

```text
serialization grammar

matcher grammar

window expressions

MSS/MTU expressions

quirks

TTL/distance

fuzzy behavior

generic/specific precedence

oracle corpus
```

---

# 150. K2B

Owns actual production TCP signatures.

May be supplied by:

```text
admitted p0f corpus

admitted Fingerbank TCP content

future curated/licensed content
```

without changing tcp_syn/2 or fusion contracts.

---

# 151. K3

Portal semantic rules map only normalized portal evidence to canonical taxonomy.

No raw UA parsing in Task-04.

---

# 152. K4

IEEE canonical imported registry:

```text
MA-L
MA-M
MA-S
```

raw semantic:

```text
mac_assignment_org
```

Manufacturer mapping is separate reviewed knowledge.

---

# PART XXI — OFFLINE / CLOUD

# 153. Runtime Local-Only Path

Production synchronous classifier uses:

```text
Task-01 local read boundary

EvidenceSnapshot

SourceEvaluability

local BindingTimeline

local KnowledgeBundle

local ClassificationPolicy

local classifier code

classification DB
```

Required external network:

```text
NONE
```

---

# 154. Fingerbank Cloud

```text
optional
default OFF
background only
```

Never:

```text
Authorization dependency

startup requirement

synchronous classification requirement
```

V1 fusion-eligible lookup:

```text
DHCP-only
```

---

# PART XXII — CLASSIFICATION STORAGE

# 155. Separate Derived Storage

Task-04 classification persistence remains separate from Task-01 evidence DB.

It owns:

```text
ClassificationResult

OriginAssessments

request manifest

snapshot references

policy references

knowledge references

classifier identity

audit metadata
```

No raw packets.

No raw UA.

No raw CH.

---

# 156. Failure Isolation

Classification storage/runtime failure:

```text
must not affect:

Portal Authorization

AuthSession

AuthWorker

CAPPORT

Task-01 ingestion
```

Classification is advisory and fail-isolated.

---

# PART XXIII — REQUIRED PRE-TASK-04 PROOF MODEL

Every mandatory gate records:

```text
input

proof method

PASS condition

FAIL condition

retained evidence artifact
```

Gates are grouped A–F.

---

# GROUP A — TASK-01 SNAPSHOT / WATERMARK / SOURCE AUTHORITY

# A1 — Global Ingest Watermark

**Input**

```text
Task-01 schema/migration candidate
evidence ingest
health ingest
```

**Proof method**

Controlled concurrent inserts across both row families.

**PASS**

```text
one monotonic sequence domain

watermark sees committed rows only

post-watermark rows have greater sequence

same watermark replay produces same eligible universe
```

**FAIL**

Any timestamp/UUID/rowid dependence or cross-table ambiguity.

**Retained artifact**

```text
schema manifest
migration report
transaction proof
test fixtures/results
```

---

# A2 — Bootstrap Generation

**Input**

Existing pre-watermark Task-01 DB fixture.

**Proof method**

Migration twice from identical immutable source copy.

**PASS**

```text
same database_generation rules

same deterministic bootstrap assignment

no claim of original historical commit order
```

**FAIL**

Migration derives authoritative past order from wall-clock/UUID/rowid.

**Retained artifact**

```text
source DB digest
migration artifact
post-migration schema/digest report
```

---

# A3 — Concurrent Snapshot Determinism

**Input**

Snapshot request + concurrent delayed evidence ingest.

**Proof method**

```text
capture watermark W

begin/paginate snapshot

concurrently ingest old-observed_at eligible row

finish snapshot

replay W

then construct W2
```

**PASS**

```text
W replay:
identical membership/order/digest

new row excluded

W2:
may include new row
new snapshot identity
```

**FAIL**

Concurrent ingest changes snapshot W.

**Retained artifact**

```text
watermarks
row manifests
snapshot digests
timing trace
```

---

# A4 — Binding Authority + Epoch Transition

**Input**

Window spanning binding epoch A → B.

**Proof method**

Inject:

```text
valid A rows
valid B rows
old A row after boundary
wrong producer
wrong capture source
health from both epochs
```

**PASS**

```text
A/B explicitly represented

correct rows admitted per observed_at epoch

rogue rows excluded/anomaly-reported

health not inherited across epoch
```

**FAIL**

Single-map approximation or source leak.

**Retained artifact**

```text
timeline artifact
snapshot manifest
scope-anomaly report
```

---

# A5 — Complete Pagination

**Input**

Evidence population >500 rows plus meaningful conflicting variant after page 1.

**Proof method**

Cursor paginate to exhaustion.

**PASS**

```text
variant after first page observed

result independent of page boundaries
```

**FAIL**

Partial classification.

**Retained artifact**

```text
page trace
cursor trace
snapshot digest
```

---

# A6 — SnapshotResourcePolicy Sizing

**Input**

```text
production per-MAC cardinality measurements

worst controlled workload

memory benchmark

CPU/runtime benchmark

pagination benchmark
```

**Proof method**

Capacity test over measured distributions and controlled high cardinality.

**PASS**

First production:

```text
max rows
max bytes
deadline
memory limits
```

are justified and frozen in versioned policy.

**FAIL**

Values chosen without measurement.

**Retained artifact**

```text
measurement report
benchmark results
policy artifact/digest
```

---

# A7 — Health Clock / Watermark Reconstruction

**Input**

Fixtures with:

```text
on-time heartbeat

future-skew within Task-01 contract

delayed/backfilled outage

transport failure

recovery
```

**Proof method**

Replay with different watermarks.

**PASS**

```text
observed_at controls event-time placement

watermark controls visibility

late backfill does not exist in old snapshot

late heartbeat does not become falsely fresh by ingested_at

transport outage expires to unknown centrally
```

**FAIL**

Central system claims unseen outage or stale heartbeat becomes current.

**Retained artifact**

```text
health rows
watermarks
reconstruction timelines
policy digest
```

---

# GROUP B — TASK-02 TCP EVIDENCE / p0f

# B1 — tcp_syn/2 Privacy / Minimality

**Input**

Proposed V2 field set and admitted adapter requirements.

**Proof method**

Field-by-field evidence-value/privacy matrix.

**PASS**

Every field proves:

```text
classification need
bounded form
no less-sensitive equivalent
```

Specifically:

```text
no exact TCP timestamp

no exact timestamp echo

no exact IP ID
```

unless separately re-authorized by proof.

**FAIL**

Speculative future-use field.

**Retained artifact**

```text
field matrix
privacy review
schema candidate digest
```

---

# B2 — Malformed Option Preservation

**Input**

Pinned malformed/truncated corpus.

**Proof method**

Compare sensor parsing against supported p0f observable semantics.

**PASS**

```text
malformed-but-complete retained

physically incomplete rejected
```

**FAIL**

Fingerprintable malformed SYN disappears.

**Retained artifact**

```text
packet fixture digests
expected normalized records
test result
```

---

# B3 — p0f Runtime Adapter Conformance

**Input**

tcp_syn/2 fixtures.

**Proof method**

Generate p0f representation and compare oracle semantics.

**PASS**

Exact supported-scope equivalence.

**FAIL**

Approximate token/quirk/window behavior.

**Retained artifact**

```text
input fixtures
adapter output
oracle output
diff report
```

---

# B4 — p0f Matcher Conformance

**Input**

Pinned real-p0f corpus covering matcher grammar.

**Proof method**

CaptivPortal matcher vs real p0f.

**PASS**

Exact:

```text
match/no-match
specific/generic
fuzzy
label result
TTL/distance behavior
```

within supported scope.

**FAIL**

Any unexplained mismatch.

**Retained artifact**

```text
p0f identity/digest
corpus digest
comparison report
```

---

# B5 — TTL / RSPAN Physical Proof

**Input**

Controlled sender + actual running SPAN/RSPAN config.

**Proof method**

Correlate exact SYN sender TTL and sensor TTL.

**PASS**

Current topology's TTL assumption proven.

**FAIL**

Mismatch or incomplete topology evidence.

**Retained artifact**

```text
running config evidence
packet identifiers
sender/sensor result
```

---

# B6 — Production TCP Corpus Admission

**Input**

Candidate K2B source.

**Proof method**

Governance + import + matcher + freshness review.

**PASS**

At least one actual usable production TCP corpus exists.

**FAIL**

Only K2A oracle exists.

**Retained artifact**

```text
source manifest
canonical import digest
freshness policy
admission report
```

---

# GROUP C — TASK-03 CLIENT HINTS / PORTAL HEALTH

# C1 — Actual-Flow CH Value

**Input**

Controlled supported clients.

**Proof method**

Real CaptivPortal flow.

**PASS**

Each admitted field independently proves useful normalized classification information.

**FAIL**

Field unavailable, unstable, redundant or non-material.

**Retained artifact**

Only normalized/privacy-safe observations and browser/client test metadata.

---

# C2 — CH Privacy / Bounded Lifecycle

**Input**

Candidate Accept-CH implementation.

**Proof method**

Network/browser inspection plus application logging/storage audit.

**PASS**

```text
Critical-CH absent

no forced retry

raw CH non-durable

Accept-CH bounded

clientHints teardown proven where supported

Authorization unchanged
```

**FAIL**

Persistent high-entropy request or portal dependency.

**Retained artifact**

```text
sanitized flow trace
header lifecycle proof
storage/log audit
```

---

# C3 — Portal Idle Heartbeat

**Input**

Enabled portal evidence runtime with no visitors.

**Proof method**

Idle period exceeding multiple heartbeat cycles.

**PASS**

Periodic health appears independently of client evidence.

**FAIL**

Liveness only changes when a visitor arrives.

**Retained artifact**

```text
source-health event timeline
```

---

# C4 — Portal Transport Failure Semantics

**Input**

Controlled Task-01 delivery outage.

**Proof method**

Break transport, preserve producer runtime, restore.

**PASS**

```text
central old heartbeat expires → unknown

no impossible live unavailable claim over broken transport

bounded historical outage backfill only when producer knows boundaries

available emitted on recovery
```

**FAIL**

Central system fabricates unavailable interval.

**Retained artifact**

```text
producer timeline
central DB timeline
watermark comparison
```

---

# GROUP D — KNOWLEDGE / GOVERNANCE / FRESHNESS

# D1 — Fingerbank Static Inspection / Canonical Import

**Input**

Owner-authorized current static artifact.

**Proof method**

Read-only inspection, legal review, canonical import.

**PASS**

```text
schema understood
license status accepted
DHCP records usable
runtime no vendor-schema dependency
```

**FAIL**

Unknown legal/schema behavior.

**Retained artifact**

```text
source digest
schema inventory
license record
canonical import digest
```

---

# D2 — Fingerbank DHCP Origin Purity

**Input**

Controlled DHCP fixtures with optional MAC/other evidence present externally.

**Proof method**

Run K1 adapter.

**PASS**

Result unchanged by non-DHCP evidence.

**FAIL**

Hidden OUI/UA/TCP enrichment.

**Retained artifact**

```text
fixtures
adapter manifest
result comparison
```

---

# D3 — IEEE Import / Assignment Semantics

**Input**

Current admitted MA-L/MA-M/MA-S source.

**Proof method**

Canonical import + prefix fixtures.

**PASS**

```text
longest prefix
U/L exclusion
raw output = assignment org
manufacturer only through explicit mapping
```

**FAIL**

OUI automatically treated as manufacturer.

**Retained artifact**

```text
source/import digest
mapping fixtures
```

---

# D4 — Taxonomy / Alias Determinism

**Input**

Source taxonomy fixtures.

**Proof method**

Map aliases and broad/out-of-scope values.

**PASS**

```text
no heuristic merge
no narrowing of broad taxonomy
canonical IDs stable
out-of-scope distinct
```

**FAIL**

String similarity changes identity.

**Retained artifact**

```text
taxonomy artifact
alias artifact
fixture report
```

---

# D5 — Knowledge Freshness Policy Freeze

**Input**

For each mandatory changing source:

```text
real update behavior
source metadata
provider documentation if available
refresh operational model
Owner policy
```

**Proof method**

Determine source-specific policy and exercise boundary states.

**PASS**

Policy freezes exact:

```text
fresh
stale
expired
behavior
```

with justification.

**FAIL**

Arbitrary age threshold.

**Retained artifact**

```text
freshness research
policy artifact/digest
Owner/TechLead approval
```

---

# D6 — Mandatory Bundle Current Usability

**Input**

Candidate accepted KnowledgeBundle plus explicit `knowledge_evaluation_at_utc`.

**Proof method**

Validate every mandatory source.

**PASS**

All mandatory K1/K2B/K3/K4 sources are:

```text
legal
compatible
usable
not expired
```

**FAIL**

Bundle merely contains unusable/expired records.

**Retained artifact**

```text
bundle manifest
freshness evaluation
validation report
```

---

# GROUP E — ORIGIN / FUSION / STATUS

# E1 — Same-Origin Matrix

**Input**

Fixtures covering:

```text
duplicate rows

ambiguous CandidateSet

temporal portal changes

multiple TCP variants

two same-origin interpreters
```

**Proof method**

Pure-core OriginAssessment execution.

**PASS**

Exact R5 state:

```text
resolved
ambiguous
conflicting
no_claim
not_evaluable
recognized_out_of_scope
```

where applicable, with no row-count vote.

**FAIL**

Latest/majority/first-row behavior.

**Retained artifact**

```text
input snapshot digest
origin assessments
policy digest
```

---

# E2 — Cross-Origin Conflict Matrix

**Input**

All required grade pair combinations:

```text
direct/direct
direct/strong
direct/supporting
strong/strong
strong/supporting
supporting/supporting
in-scope/out-of-scope
resolved/broad
```

**Proof method**

Pure fusion fixtures.

**PASS**

Results exactly match R5 §§115–122.

**FAIL**

Hidden source priority or implementation discretion.

**Retained artifact**

```text
fixture matrix
classification outputs
policy digest
```

---

# E3 — Final Dimension Status

**Input**

Fixtures for every final status.

**Proof method**

Pure core.

**PASS**

Exact distinction among:

```text
resolved
recognized_out_of_scope
unknown
insufficient_evidence
conflicting_evidence
```

No final `ambiguous`.

**FAIL**

Overlapping undefined vocabulary.

**Retained artifact**

```text
fixture matrix
result digests
```

---

# E4 — Global Status Derivation

**Input**

Combinatorial dimension-status fixtures.

**Proof method**

Pure global derivation.

**PASS**

Exact R5 precedence.

**FAIL**

UI/service-dependent result.

**Retained artifact**

```text
derivation table
test result
policy digest
```

---

# E5 — Pure-Core Determinism / Knowledge Clock

**Input**

Same snapshot/bundle/policy with:

```text
same knowledge_evaluation_at

then different knowledge_evaluation_at
```

**Proof method**

Block DB/network/filesystem and mock system clock changes.

**PASS**

```text
same explicit inputs → identical result

wall-clock change alone → no effect

different explicit knowledge evaluation time
may produce freshness-driven new result
```

**FAIL**

Pure core reads current clock or environment.

**Retained artifact**

```text
request manifests
result digests
```

---

# GROUP F — AUDIT / OFFLINE / FAILURE ISOLATION

# F1 — Exact Classifier Artifact Identity

**Input**

Exact accepted candidate.

**Proof method**

Capture manifest.

**PASS**

Audit identifies:

```text
commit SHA
tree SHA
engine version
adapter versions
K2A version
schema versions
manifest digest
```

**FAIL**

Only generic version string.

**Retained artifact**

ClassifierArtifactManifest.

---

# F2 — Audit Replay / Artifact Retention

**Input**

Persisted classification and referenced artifacts.

**Proof method**

Replay Level B after removing original Task-01 evidence fixture.

**PASS**

```text
OriginAssessment → final result reproducible

all referenced immutable artifacts retrievable
```

**FAIL**

GC removes required binding/policy/bundle/classifier metadata.

**Retained artifact**

```text
audit replay report
retention inventory
```

---

# F3 — Zero Runtime Internet Dependency

**Input**

Accepted offline bundle and snapshot.

**Proof method**

Block all external network.

**PASS**

Classification completes deterministically.

**FAIL**

Any required remote lookup.

**Retained artifact**

```text
network-block proof
result digest
```

---

# F4 — Resource / Failure Isolation

**Input**

```text
resource_limited snapshot

classification DB unavailable

knowledge bundle load failure

classifier exception
```

**Proof method**

Controlled fault injection.

**PASS**

```text
no partial classification

no Task-01 corruption

no Portal/Auth/CAPPORT impact
```

**FAIL**

Authorization or evidence ingestion affected.

**Retained artifact**

```text
fault matrix
service health/result report
```

---

# F5 — Controlled Local Sanity Validation

**Input**

Only available controlled Owner devices.

No fixed 12-device campaign.

**Proof method**

Compare known device ground truth to advisory classification.

**PASS safety condition**

```text
no HIGH-support incorrect
primary classification dimension
```

Acceptable safe outputs include:

```text
unknown

insufficient_evidence

recognized_out_of_scope

low/medium support
```

when evidence does not justify stronger resolution.

**FAIL**

High-support wrong primary dimension.

**Retained artifact**

Privacy-safe controlled validation report.

---

# PART XXIV — ACCEPTANCE BEFORE TASK-04

# 157. Architecture Acceptance vs Proof Closure

Two separate states exist.

## Architecture Accepted

Requires explicit:

```text
OWNER ACCEPT

+

TECHLEAD11 ACCEPT
```

Then R5 may be promoted to:

```text
ARCHITECTURE CONTRACT FINAL
```

## Foundation Proof Closed

Requires all mandatory pre-Task-04 proof groups applicable to V1 to PASS.

Only then:

```text
TASK-04 decomposition may start
```

---

# 158. No Silent Conditional Scope

If a candidate capability is not admitted after proof, the accepted Task-04 scope is reduced explicitly.

Example:

```text
portal_headers/2 fails
→ Task-04 uses portal_headers/1
```

Not:

```text
ship half-proven portal_headers/2
```

Similarly:

```text
optional JA4 knowledge unavailable
→ JA4 produces no classification claim
```

---

# 159. Task-04 Recommended Decomposition After Closure

```text
TASK-04A
Immutable Classification Artifacts

- KnowledgeBundle
- ClassificationPolicy
- SourceBindingTimeline
- artifact stores/retention


TASK-04B
EvidenceSnapshot + SourceEvaluability

- immutable watermark reads
- binding authority
- complete pagination
- health reconstruction


TASK-04C
Origin Adapters / Assessments

- DHCP
- Portal
- TCP
- TLS
- QUIC
- MAC registry


TASK-04D
Pure Fusion Core

- same-origin matrix
- cross-origin matrix
- support levels
- dimension statuses
- global status


TASK-04E
Classification Persistence / Audit

- result schema
- OriginAssessment persistence
- request manifest
- artifact references
- replay


TASK-04F
Optional Cloud Enrichment

- default OFF
- isolated
- no core dependency


TASK-04G
Controlled Product Validation
```

This is only a future decomposition direction.

It is NOT Coder authorization.

---

# 160. Current Owner-Controlled External Actions

Potential controlled actions after architecture acceptance:

```text
O1
Fingerbank Community static artifact
download / inspection / legal review

O2
Portal Accept-CH + teardown
controlled physical experiment

O3
TTL / RSPAN
controlled sender/sensor proof

O4
Knowledge-source freshness
Owner policy decisions after measured/source research

O5
Snapshot resource policy
production cardinality/capacity measurement authorization
```

No production mutation follows automatically from R5.

---

# 161. R5 Final Review Checklist

R5 explicitly defines:

```text
real global ingest watermark

same watermark domain for evidence + health

database generation identity

concurrent ingest determinism

binding effective epochs

mandatory producer identity

binding-authorized snapshot membership

classification-relevant snapshot metadata

minimal tcp_syn/2 correlation surface

one canonical TCP option representation

explicit knowledge_evaluation_at

no invented knowledge freshness ages

orthogonal freshness/source-character model

versioned measured SnapshotResourcePolicy

pure classification core

versioned ClassificationPolicy

complete same-origin matrix

complete cross-origin grade matrix

no undefined final ambiguous state

exact final dimension statuses

exact global-status derivation

retention of all referenced immutable artifacts

exact classifier artifact manifest

real transport-outage health semantics

explicit observed/ingested/watermark clocks

Critical-CH forbidden

03A tooling vs physical campaign distinction

mandatory knowledge usability at admission

TCP evidence minimization/privacy gate

concurrent watermark proof

binding-change window proof

grouped proof gates A–F
```

---

# 162. Required R5 Status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R5

STATUS =
FOR OWNER + TECHLEAD11 STRICT REVIEW

R4 =
SUPERSEDED

ARCHITECTURE CONTRACT FINAL =
NO

TASK-04 =
HOLD

CODER =
HOLD

CODE =
NO

PRODUCTION CHANGE =
NO
```

Only explicit:

```text
OWNER ACCEPT
+
TECHLEAD11 ACCEPT
```

may promote this architecture.

Even after architectural acceptance:

```text
TASK-04 remains HOLD
```

until required pre-Task-04 foundation proof gates are closed.

---