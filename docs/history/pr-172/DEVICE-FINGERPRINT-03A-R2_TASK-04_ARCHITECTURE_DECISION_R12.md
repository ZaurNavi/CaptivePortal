# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R12

## Regression-Controlled Deterministic Passive Classification Foundation — Control-Plane / Schema Closure

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-16  
**Status:** `FINAL CANDIDATE — CONTROL-PLANE/SCHEMA CLOSED — FOR OWNER + TECHLEAD11 FINAL REVIEW`  
**Architecture Contract Final:** `NO`  
**Task-04:** `HOLD`  
**Task-04 Coder Task:** `NO`  
**Production change:** `NO`

---

# 1. Document disposition

This is a complete standalone R12 FINAL-CANDIDATE architecture document.

R11 is the frozen semantic predecessor except for the exact corrections authorized by the TechLead11 R12 final control-plane/schema review. R12 changes only R12-01 through R12-12 plus mechanically affected Appendix C/D/E/F/G, preservation matrix, cross-references and status/revision references.

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R12

STATUS =
FINAL CANDIDATE — CONTROL-PLANE/SCHEMA CLOSED
FOR OWNER + TECHLEAD11 FINAL REVIEW

R11 =
FROZEN PREDECESSOR
except explicitly authorized R12 corrections

ARCHITECTURE CONTRACT FINAL =
NO

TASK-04 =
HOLD

TASK-04 CODER TASK =
NO

PRODUCTION CHANGE =
NO
```

R12 does not self-promote to FINAL. Only explicit:

```text
OWNER ACCEPT
+
TECHLEAD11 FINAL ACCEPT
```

may promote the architecture contract.

Until then:

```text
TASK-04 = HOLD
TASK-04 CODER TASK = NO
PRODUCTION CHANGE = NO
```

# 2. Owner quality and regression policy

R12 is governed by:

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

## 2.1 Frozen-contract change control

Effective for R8 and all later revisions:

```text
ANY R7 CONTRACT
NOT EXPLICITLY AUTHORIZED FOR CHANGE
BY THE R8 REVIEW
=
FROZEN
```

Frozen content SHALL be carried forward unchanged in semantic meaning and, where practical, verbatim.

Forbidden without a separately approved exception:

```text
rename frozen enums
change frozen defaults
change precedence
change gate meaning
move ownership
remove a safeguard because it appears redundant
simplify wording in a way that narrows or broadens scope
```

If a future Architect believes a frozen contract must change, work on that change stops and a separate:

```text
FROZEN-CONTRACT CHANGE REQUEST
```

must contain:

```text
exact frozen contract
reason change is required
what breaks if unchanged
proposed replacement
regression impact
Owner decision required
```

Until TechLead11 + Owner approve the exception, the frozen contract remains unchanged.

A preservation-matrix explanation after an unauthorized semantic change is not sufficient.

Appendix A records the current R11→R12 disposition and retains prior regression history as documentary lineage.

Appendix B is the permanent Frozen Contract Register and MUST be carried forward by future revisions.

## 2.2 R12 final control-plane/schema change authorization

For R12 specifically:

```text
EVERY R11 CONTRACT
NOT EXPLICITLY AUTHORIZED FOR CHANGE
BY THE TECHLEAD11 R12 FINAL CONTROL-PLANE / SCHEMA REVIEW
=
FROZEN
```

Authorized semantic changes are limited to R12-01 through R12-12 plus mechanically affected:

```text
Appendix C
Appendix D
Appendix E
Appendix F
Appendix G
preservation matrix
cross-references
status/revision references
```

Everything else is copied forward without semantic redesign, cleanup, enum renaming, precedence changes, policy redesign or gate scope expansion.

If preparation of R12 reveals a separate frozen defect outside that authorization, it requires a separate `FROZEN-CONTRACT CHANGE REQUEST`; it is not silently repaired in R12.

---

---

# 3. Verified repository baseline

---

---

# 3. Verified repository baseline

R12 was verified against:

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

Existing merged 03A tooling remains valid for:

```text
optional controlled research
future regression datasets
manual expanded validation
```

PRE-TASK / Task-04 work MUST NOT silently delete, repurpose, or redefine that tooling.

Removal or repurposing requires a separate explicit task and review.

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

## 5.1 Acquisition/infrastructure boundaries

PRE-TASK / Task-04 MUST NOT broadly redesign:

```text
Catalyst RSPAN topology

sensor interface placement

AF_PACKET architecture

raw exact-frame dedup architecture

Suricata EVE architecture

existing Task-01 ingest security boundary

existing Task-01 API/envelope semantics
except the exact bounded v2 changes
explicitly authorized by this architecture

Portal Authorization flow

classification/Authorization isolation
```

An exception requires ALL:

```text
a specific required evidence/foundation field
is proven impossible under the current design

separate bounded change proposal

TechLead11 review

Owner authorization
```

No opportunistic infrastructure cleanup is part of this program.

## 5.2 Classification storage boundary

Frozen V1 architecture:

```text
Task-01 normalized evidence SQLite
!=
Task-04 classification SQLite
```

Task-04 classification result/history/current-state tables MUST NOT be added to the Task-01 evidence DB.

Task-04 owns a dedicated Classification SQLite.

Its exact production path is frozen by the later Task-04 implementation contract; database separation itself is frozen here.

## 5.3 Internal classification read contract

Task-04 owns a typed internal read surface equivalent to:

```text
get_current(
    site_id,
    observed_mac
)

list_history(
    site_id,
    observed_mac,
    from_utc,
    to_utc,
    limit,
    cursor
)
```

The implementation may use different method/type names only if the same typed semantics are preserved.

This is an internal product read contract, not a public API.

## 5.4 Later ownership

```text
Task-05 = identity/session integration

Task-06 = presentation integration
```

Task-04 adds:

```text
NO public classification API
NO Device Card UI
NO Admin UI presentation
```

Identity/session and presentation do not migrate into Task-04 merely because classification storage exists.

---

# 6. Lifecycle — no gate cycle

Exact lifecycle:

```text
R12 architecture candidate
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
T-ACCEPT creates implementation/admission lineage
        ↓
accepted/admitted Task-04 candidate
        ↓
SEPARATE explicit Owner-authorized production activation action
        ↓
crash-atomic production ClassificationRuntimeProfile activation
```

T-ACCEPT means implementation acceptance / production eligibility. It does NOT change the production ClassificationRuntimeProfile pointer.

Foundation F-ADMIT MAY activate the initial FoundationRuntimeProfile because that does not activate Task-04 production classification; that Foundation activation uses the same crash-atomic activation primitive frozen in §11.5.

No Foundation gate requires Task-04 classifier code.

No Task-04 Acceptance gate is required before Task-04 decomposition.

Task-04 acceptance itself is not a production change.

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

All immutable R12 architecture/runtime ArtifactContent uses one exact byte-level encoder:

```text
ArtifactCanonicalJsonV1
```

Before encoding, recursively:

```text
all object keys MUST be strings

all strings are normalized to Unicode NFC

semantic timestamps MUST already match exactly:
YYYY-MM-DDTHH:MM:SS.mmmZ

floats are FORBIDDEN

Decimal objects are FORBIDDEN

NaN and Infinity are FORBIDDEN

numeric semantic values use integers where possible

non-integer semantic values, if ever required,
use a separately specified canonical decimal string
rather than JSON float
```

## 9.1 Duplicate-key and NFC-key collision rejection

When ArtifactContent JSON is decoded/imported:

```text
duplicate object keys in the source JSON = VALIDATION FAIL
```

Before encoding, after NFC normalization of object keys:

```text
if two originally distinct keys normalize to the same key
→ ARTIFACT VALIDATION FAIL
```

Forbidden:

```text
first-key-wins
last-key-wins
silent merge
```

The collision check occurs before hashing.

## 9.2 Exact encoder

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

JSON booleans exactly:
true
false

JSON null exactly:
null

integers use standard decimal JSON integer output
with no leading plus sign and no locale formatting

no pretty printing

no trailing newline

slash is not specially escaped beyond Python stdlib behavior
```

## 9.3 ArtifactCanonicalOrderingV1

Every semantic collection declares one of exactly three ordering classes:

```text
SEQUENCE
SET
MAP
```

### SEQUENCE

Order carries semantic meaning.

The producer MUST preserve the explicitly defined semantic order.

Examples include:

```text
TCP option records
coverage interval sequence
ordered candidate precedence only where the contract explicitly says order is semantic
```

### SET

Order carries no semantic meaning.

Every SET-like array MUST declare an explicit primary canonical sort key.

Canonical total-order rule is exactly:

```text
1. sort by the declared primary canonical key

2. when two elements have an equal primary key,
   compare ArtifactCanonicalJsonV1(element) UTF-8 byte sequences
   lexicographically and use that as the tie-break

3. if the canonical byte sequences are identical,
   the entries are duplicate SET elements
   → ARTIFACT VALIDATION FAIL
```

For primitive SET elements whose value itself is the canonical identity, the primary key is that primitive canonical value.

If an artifact contract defines no more specific key for an artifact/value-reference SET:

```text
primary key = canonical artifact/value ID
```

No implementation may use an undefined phrase such as:

```text
canonical matrix key
canonical conflict key
canonical source key
```

without the owning artifact contract declaring the exact primary field tuple. The universal canonical-byte tie-break still applies after that tuple.

### MAP

Object-member order is handled by ArtifactCanonicalJsonV1 lexicographic key sorting after duplicate-key and NFC-collision validation.

Every ArtifactContent array field MUST explicitly declare its class and, for SET, its primary sort key.

At minimum the following are SET-like unless their owning contract explicitly marks them SEQUENCE:

```text
OriginDimensionAssessment.claim_derivations
candidate knowledge_refs
candidate evidence_refs
same-origin contradiction records
broad/unresolved refs
OriginAssessment knowledge/evidence/explanation refs
DimensionResult supporting/contradicting/not-evaluable origin lists
DimensionResult knowledge/out-of-scope/explanation refs
Foundation gate ID lists
GateResult artifact/evidence/decision reference lists
Task-04 gate ID lists
policy enum vectors
policy matrix rows
provenance/governance reference arrays
```

Exact per-field primary keys are repeated in the relevant artifact contracts and Appendix C.

---

## 9.4 Canonical fixture corpus

A fixture corpus SHALL pin exact encoded bytes for:

```text
ASCII strings
non-ASCII BMP strings
non-BMP Unicode
NFC-equivalent values
NFC key-collision rejection
duplicate-key decode rejection
booleans
null
positive/zero/negative allowed integers
nested maps
SEQUENCE arrays
SET arrays
canonical timestamps
quote/backslash/control escaping
```

The implementation identity/version of `ArtifactCanonicalJsonV1` and `ArtifactCanonicalOrderingV1` is part of foundation/classifier identity where applicable.

---

# 10. ArtifactContent, ArtifactRegistration and DecisionRecord

Semantic identity and audit registration are separate.

## 10.1 ArtifactContent

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

Different semantic bytes MUST have a different artifact ID.

Audit metadata is never embedded inside ArtifactContent under the same semantic identity.

ArtifactContent schemas are CLOSED-WORLD per `artifact_schema_version`.

For every ArtifactContent:

```text
artifact_schema_version
→ defines the EXACT allowed semantic_payload fields
   and the EXACT allowed fields of every nested semantic object

undeclared top-level semantic field
→ VALIDATION FAIL

undeclared nested semantic field
→ VALIDATION FAIL

optional field
→ allowed only when that optional field is explicitly declared
   by the frozen schema version

new semantic field
→ requires a new artifact_schema_version
   unless the existing version explicitly declared that field optional
```

Coder/implementation code may not add implementation-defined semantic extensions under an existing artifact schema version.

### 10.1.1 Universal duplicate direct/transitive reference invariant

Whenever one ArtifactContent represents the same dependency both directly and transitively:

```text
direct ID/digest MUST equal the value reachable through the transitive reference
```

No direct/transitive occurrence is allowed to compete as a second source of truth. Missing or unequal duplicates fail ArtifactContent construction.

This universal rule includes the explicit R12 checks for SnapshotRecord, classification persistence, KnowledgeBundle inventories, EvidenceSnapshotContent OriginRuntimeAdmission, ClassificationRequestManifest vs ClassificationRuntimeProfile, and any future duplicate declared under the same artifact schema version.

## 10.2 ArtifactRegistration

Separate immutable audit registration.

Audit schema version 1 fields are:

```text
registration_schema_version = 1
registration_id
artifact_id
registered_at_utc
registered_by_role
repository_commit_sha or null
repository_tree_sha or null
ordered decision_record_refs
notes/reference metadata
```

`registration_id` is canonical lowercase UUIDv4.

`decision_record_refs` are SET-like, primary key = `decision_record_id`, with the universal canonical-byte tie-break from §9.3.

Two registrations may point to the same ArtifactContent.

ArtifactRegistration is audit metadata, not semantic ArtifactContent. Later audit-only extensibility requires a new versioned ArtifactRegistration audit schema and does not alter the referenced ArtifactContent identity.

---

## 10.3 DecisionRecord

All Owner/reviewer decision references use one exact immutable audit-record contract:

```text
decision_record_id = canonical lowercase UUIDv4

decision_subject_type

decision_subject_id

decision =
    ACCEPT
  | REJECT
  | APPROVE_EXCEPTION
  | ACKNOWLEDGE_RISK

decided_at_utc = YYYY-MM-DDTHH:MM:SS.mmmZ

actor_role = OWNER | TECHLEAD11 | OTHER_EXPLICIT_ROLE

ordered referenced_artifact_ids
ordered referenced_gate_ids

reason/reference text

record_sha256
```

`record_sha256` is SHA-256 over ArtifactCanonicalJsonV1 of all fields except `record_sha256`; referenced arrays are SET-like and sorted lexicographically.

A random registration UUID is never inserted into semantic KnowledgeBundle content merely to represent approval.

Where approval is semantically required, the semantic artifact records the actual admitted semantic state; DecisionRecord/ArtifactRegistration records who approved it and when.

---

# 11. Artifact activation discipline

Accepted ArtifactContent is immutable.

Runtime execution-set content and governance/admission lineage are separate.

Mutable "current" selection exists only through atomic runtime-profile pointers.

## 11.1 FoundationRuntimeProfile

Immutable `FoundationRuntimeProfile` is the atomic compatibility unit for snapshot/source foundation runtime.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
foundation_profile_contract_version

EvidenceSourceBindingTimeline ID/digest
BindingClockPolicy ID/digest
SourceHealthPolicy ID/digest
SnapshotContentPolicy ID/digest
SnapshotExecutionPolicy ID/digest
EvidenceSchemaRegistryContract ID/digest
Task01HealthRetentionContract ID/digest
OriginRuntimeAdmission ID/digest
classification_foundation_valid_from_utc

ordered SourceHealthEmitterContract IDs/digests

TTLCapturePlacementProof ID/digest or null

snapshot_contract_version
```

The FoundationAdmissionManifest lineage root is NOT part of FoundationRuntimeProfile semantic content.

`SourceHealthEmitterContract` refs are a SET with primary key = artifact ID and the universal canonical-byte tie-break.

When `OriginRuntimeAdmission.tcp_state = ENABLED`:

```text
TTLCapturePlacementProof ID/digest MUST be non-null
and MUST equal the proof referenced by OriginRuntimeAdmission
```

When TCP is disabled:

```text
TTLCapturePlacementProof ID/digest = null
```

One active pointer selects the ENTIRE FoundationRuntimeProfile for standalone/research foundation operations.

Forbidden:

```text
read current BindingTimeline
then current ClockPolicy
then current HealthPolicy
then current SchemaRegistry independently
```

A production classification request does NOT read the active FoundationRuntimeProfile pointer independently; it obtains its exact FoundationRuntimeProfile from the already pinned ClassificationRuntimeProfile as frozen in §113.

## 11.2 ClassificationRuntimeProfile

Immutable `ClassificationRuntimeProfile` is the atomic compatibility unit for classification execution.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
classification_runtime_profile_contract_version

FoundationRuntimeProfile ID/digest
KnowledgeBundle ID/digest
ClassificationPolicy ID/digest
EvidenceAdapterContractSet ID/digest
ClassifierArtifactManifest ID/digest
```

Task04AcceptanceManifest is NOT part of ClassificationRuntimeProfile semantic content.

Therefore a candidate ClassificationRuntimeProfile can be constructed and hashed BEFORE T-ACCEPT.

One active pointer selects the ENTIRE ClassificationRuntimeProfile for production classification traffic.

LIVE RequestAssembly reads that pointer once, pins one exact profile ID/digest, and loads exactly the artifacts referenced by that profile.

It never independently chooses currently active Bundle/Policy/Classifier/Foundation versions.

## 11.3 Runtime profile compatibility

A ClassificationRuntimeProfile candidate MUST validate all of the following:

```text
KnowledgeBundle taxonomy ID
==
ClassificationPolicy taxonomy ID

KnowledgeBundle alias mapping
compatible with policy/classifier expectation

ClassificationPolicy EvidenceAdapterContractSet ID
==
profile EvidenceAdapterContractSet ID

ClassifierArtifactManifest adapter implementations
implement exactly the admitted EvidenceAdapterContractSet

classifier snapshot contract version
compatible with FoundationRuntimeProfile snapshot contract

FoundationRuntimeProfile EvidenceSchemaRegistryContract
compatible with EvidenceAdapterContractSet

ClassifierArtifactManifest K2A implementation
compatible with admitted K2B representation

FoundationRuntimeProfile contract versions
compatible with classifier/request contract versions

FoundationRuntimeProfile OriginRuntimeAdmission contract
compatible with classifier TCP-origin disable/enable semantics
```

Mismatch:

```text
PROFILE CANDIDATE = REJECTED
NO ACTIVATION
```

No best-effort compatibility.

## 11.4 RuntimeProfileAdmissionManifest

Every runtime-profile admission is justified by immutable `RuntimeProfileAdmissionManifest`.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
runtime_profile_admission_contract_version

profile_kind = foundation | classification
candidate_profile_id/digest
previous_active_profile_id/digest or null
update_class

ordered prerequisite GateResultManifest IDs/digests

compatibility_validation_result = PASS

candidate_repository_commit_sha
candidate_repository_tree_sha

FoundationAdmissionManifest ID/digest
Task04AcceptanceManifest ID/digest or null
foundation_runtime_profile_admission_manifest ID/digest or null
```

`update_class` is a CLOSED V1 enum exactly:

```text
INITIAL_FOUNDATION
INITIAL_CLASSIFICATION
KNOWLEDGE_BUNDLE_REFRESH
KNOWLEDGE_FRESHNESS_POLICY_CHANGE
BINDING_TIMELINE_CHANGE
CAPTURE_TOPOLOGY_CHANGE
SOURCE_HEALTH_EMITTER_CHANGE
SOURCE_HEALTH_POLICY_CHANGE
SNAPSHOT_CONTENT_POLICY_CHANGE
SNAPSHOT_EXECUTION_POLICY_CHANGE
EVIDENCE_SCHEMA_CHANGE
EVIDENCE_ADAPTER_CHANGE
EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE
CLASSIFICATION_POLICY_CHANGE
CLASSIFIER_ARTIFACT_CHANGE
FOUNDATION_VALID_FROM_LATER
ROLLBACK_REACTIVATION
```

Any other value is validation failure for schema version 1.

Rules:

```text
profile_kind = foundation
→ Task04AcceptanceManifest ID/digest = null
→ foundation_runtime_profile_admission_manifest ID/digest = null

profile_kind = classification
→ Task04AcceptanceManifest ID/digest is required
→ foundation_runtime_profile_admission_manifest ID/digest is required
```

For `profile_kind = classification`, the referenced foundation RuntimeProfileAdmissionManifest MUST:

```text
already exist and be admitted
have profile_kind = foundation
have candidate_profile_id/digest
==
candidate ClassificationRuntimeProfile.FoundationRuntimeProfile ID/digest
```

This is exact FoundationRuntimeProfile admission-proof lineage; the root FoundationAdmissionManifest alone is insufficient for later FoundationRuntimeProfile versions.

For a classification admission, the required Task04AcceptanceManifest is either:

```text
a NEW manifest when the update class requires semantic Task-04 reacceptance

or

the previously accepted manifest explicitly permitted for reuse by Appendix G
```

No implicit acceptance-manifest reuse exists.

Appendix G freezes, for EVERY `update_class`:

```text
allowed profile_kind
allowed FoundationRuntimeProfile field deltas
allowed ClassificationRuntimeProfile field deltas
required prerequisite gates/proofs
whether an existing Task04AcceptanceManifest may be reused
whether a NEW Task04AcceptanceManifest is mandatory
```

A candidate whose actual field delta exceeds its update-class allowance is rejected.

One RuntimeProfileAdmissionManifest has exactly ONE `profile_kind`. Appendix-G wording such as `foundation, then classification` always means TWO ordered admission manifests/actions: first one `profile_kind=foundation`, then a distinct one `profile_kind=classification` after the foundation admission exists.

### 11.4.1 Single update_class composition rule

A RuntimeProfileAdmissionManifest contains exactly ONE `update_class`.

V1 rule:

```text
independent update classes MUST NOT be bundled
unless one Appendix-G row explicitly permits every dependent field delta
```

If a requested change spans two independent update classes and no single Appendix-G row explicitly permits the composition:

```text
perform sequential admissions
through safe compatible intermediate immutable profiles
```

Coder/runtime MUST NOT choose a dominant class or collapse independent classes heuristically.

For `EVIDENCE_SCHEMA_CHANGE`, reuse of an existing Task04AcceptanceManifest is permitted ONLY when ALL are true:

```text
EvidenceAdapterContractSet ID/digest unchanged
ClassificationPolicy ID/digest unchanged
ClassifierArtifactManifest ID/digest unchanged
new schema change produces no new classifier semantic behavior
profile compatibility/regression PASS
```

If a new evidence schema creates classifier-visible adapter semantics, the Foundation schema/registry admission occurs first without changing active production ClassificationRuntimeProfile; the companion classification admission then uses `EVIDENCE_ADAPTER_CHANGE` or `EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE` as applicable.

For `EVIDENCE_ADAPTER_CHANGE`, the dependent policy rebind is explicitly permitted and required:

```text
new EvidenceAdapterContractSet
+
new ClassificationPolicy ArtifactContent
whose ONLY policy delta is:
    EvidenceAdapterContractSet ref old → new
+
new ClassifierArtifactManifest where implementation compatibility requires
+
new ClassificationRuntimeProfile
+
NEW Task04AcceptanceManifest
```

That dependent reference rebind is part of `EVIDENCE_ADAPTER_CHANGE`; it is NOT an independent policy-rule semantic change.

If ClassificationPolicy RULE SEMANTICS also change in the same release, use exactly:

```text
EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE
```

with full Task-04 semantic reacceptance. This is the only V1 composite class for a genuine simultaneous EvidenceAdapter semantic change + ClassificationPolicy semantic-rule change.

For `ROLLBACK_REACTIVATION`:

```text
NO semantic delta
means the candidate profile bytes/digest are EXACTLY equal
to a previously admitted immutable profile
```

It does NOT mean equality to the currently active profile. Differences between current-active and rollback-target are expected.

`ordered prerequisite GateResultManifest IDs/digests` means PREREQUISITE results only.

It MUST explicitly exclude:

```text
the F-ADMIT GateResultManifest that outputs this manifest

the T-ACCEPT GateResultManifest that outputs this manifest

any runtime-profile-admission GateResultManifest that outputs this manifest
```

The completed final GateResultManifest may reference RuntimeProfileAdmissionManifest as its output.

Dependency direction is strictly:

```text
prerequisite GateResultManifests
        ↓
lineage-root artifact(s) + already-existing candidate runtime profile
        ↓
RuntimeProfileAdmissionManifest
        ↓
final GateResultManifest output reference
```

No ArtifactContent output semantically references the GateResultManifest that lists that artifact as an output.

Human acceptance/activation time remains in DecisionRecord/ArtifactRegistration/activation records, not in runtime-profile semantic identity.

---

## 11.5 Atomic pointer behavior

Rules:

```text
ArtifactContent never mutates

runtime-profile activation is one crash-atomic control-plane transaction

active pointer tuple is externally visible
IFF
the exact RuntimeProfileActivationRecord
AND
its initial ACTIVE RuntimeProfileValidityRecord
AND
the canonical validity-head entry
are durably retrievable

old in-flight operation remains entirely on old pinned profile

new operation sees entirely new profile
```

Preferred and REQUIRED V1 transaction model:

```text
precompute immutable RuntimeProfileActivationRecord content
precompute immutable initial ACTIVE RuntimeProfileValidityRecord content

BEGIN one durable control-plane transaction

insert RuntimeProfileActivationRecord ArtifactContent
insert initial ACTIVE RuntimeProfileValidityRecord ArtifactContent
insert canonical validity head:
    activation_record_id -> initial validity_record_id

if replacing a currently ACTIVE prior activation safely:
    construct its INACTIVE/SUPERSEDED_SAFE successor
    CAS its validity head to that successor in the same transaction

write active pointer tuple referencing:
    profile_kind
    runtime_profile_id/digest
    activation_record_id
    activation_generation_id

COMMIT
```

Crash semantics:

```text
crash before COMMIT
→ old complete control-plane state remains

crash during transaction
→ transaction rollback/recovery exposes old complete state

crash after durable COMMIT
→ new complete pointer + activation + initial validity head are all visible
```

Forbidden observable successful-activation state:

```text
pointer → missing RuntimeProfileActivationRecord
pointer → missing initial RuntimeProfileValidityRecord
pointer → missing canonical validity head
```

`activation_lineage_unavailable` remains only corruption/storage-failure protection. It is NOT a normal successful activation transition.

A mixed set such as:

```text
new KnowledgeBundle
+
old ClassificationPolicy
+
old ClassifierArtifact
```

is forbidden unless that exact set is a separately admitted immutable ClassificationRuntimeProfile.

Activating a new FoundationRuntimeProfile does NOT automatically change production classification traffic.

Production classification continues to use the FoundationRuntimeProfile referenced by its active ClassificationRuntimeProfile until a compatible new ClassificationRuntimeProfile is admitted and separately activated for production.

If an old classification profile becomes unsafe before the safe replacement profile is active, the unsafe classification path is suspended according to the applicable stop condition rather than mixing generations.

### 11.5.1 Auditable rollback reactivation

Rollback never mutates or rebuilds the previously admitted profile.

Every rollback admission creates a NEW RuntimeProfileAdmissionManifest with:

```text
update_class = ROLLBACK_REACTIVATION

candidate_profile_id/digest =
previously admitted immutable profile being restored

previous_active_profile_id/digest =
profile being rolled back from

proof that candidate_profile_id/digest
was previously admitted for the same profile_kind/lineage

required current safety/compatibility recheck = PASS
```

For classification rollback, the RuntimeProfileAdmissionManifest references the Task04AcceptanceManifest lineage that previously admitted the exact candidate profile unless a new semantic reacceptance is independently required.

A DecisionRecord is required wherever Appendix G/Owner policy requires it.

After rollback admission and current-safety PASS, the rollback activation uses the SAME crash-atomic transaction primitive from §11.5 and creates a NEW activation record + initial ACTIVE validity head even though the profile bytes/digest are old.

Forbidden:

```text
unaudited pointer rewind
rebuild old profile content under a new digest
reactivate a profile whose current safety prerequisites are invalid
```

`artifact/profile activated_at` is audit metadata and is NOT knowledge freshness time.

### 11.5.2 RuntimeProfileActivationRecord — exact successful activation lineage

Every successful runtime-profile pointer activation has one immutable `RuntimeProfileActivationRecord`.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
activation_contract_version
activation_record_id
profile_kind = foundation | classification
runtime_profile_id
runtime_profile_digest
runtime_profile_admission_manifest_id
runtime_profile_admission_manifest_digest
previous_activation_record_id or null
previous_active_profile_id or null
previous_active_profile_digest or null
activated_at_utc
activation_reason_update_class
activation_result = ACTIVE
activation_generation_id
```

R12 V1 chooses separate canonical lowercase UUIDv4 record identities for `activation_record_id`, `activation_generation_id`, and predecessor activation-record references. These are NOT ArtifactId values.

The RuntimeProfileActivationRecord content is precomputed before the crash-atomic transaction, but it becomes durably visible only as part of the successful §11.5 transaction that also publishes its initial ACTIVE validity record/head and active pointer tuple.

If the control-plane transaction does not commit:

```text
NO ACTIVE activation record/pointer tuple from that attempted activation is externally visible
```

Rollback to the same immutable profile creates a NEW RuntimeProfileActivationRecord.

DecisionRecord / ArtifactRegistration linkage is audit association and is not embedded in runtime-profile semantic content.

### 11.5.3 RuntimeProfileValidityRecord — canonical current admissibility head

Every admitted runtime-profile activation has an immutable validity-state chain with exactly ONE canonical current head.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
runtime_profile_validity_contract_version
validity_record_id
profile_kind = foundation | classification
runtime_profile_id
runtime_profile_digest
activation_record_id
state = ACTIVE | INACTIVE | SUSPENDED_INVALIDATED
reason_code
effective_at_utc
inflight_commit_rule = ALLOW_PINNED_INFLIGHT | REJECT_PINNED_INFLIGHT
previous_validity_record_id or null
```

R12 V1 chooses canonical lowercase UUIDv4 separate record identities for `validity_record_id` and `previous_validity_record_id`; they are NOT ArtifactId values.

V1 `reason_code` enum is exactly:

```text
ACTIVATED
SUPERSEDED_SAFE
ROLLBACK_REACTIVATED
TTL_CAPTURE_PROOF_INVALIDATED
EXPLICIT_POLICY_SUSPEND
PROFILE_COMPATIBILITY_INVALIDATED
```

Cross-field rules:

```text
state = ACTIVE
→ reason_code = ACTIVATED | ROLLBACK_REACTIVATED
→ inflight_commit_rule = ALLOW_PINNED_INFLIGHT

state = INACTIVE
→ reason_code = SUPERSEDED_SAFE
→ inflight_commit_rule = ALLOW_PINNED_INFLIGHT

state = SUSPENDED_INVALIDATED
→ reason_code = TTL_CAPTURE_PROOF_INVALIDATED | EXPLICIT_POLICY_SUSPEND | PROFILE_COMPATIBILITY_INVALIDATED
→ inflight_commit_rule = REJECT_PINNED_INFLIGHT
```

Canonical head control-plane invariant:

```text
activation_record_id
→ exactly one current validity_record_id head
```

A post-activation validity transition is exactly:

```text
expected_head = atomically read canonical validity head

construct new immutable RuntimeProfileValidityRecord:
    activation_record_id = same activation
    previous_validity_record_id = expected_head

BEGIN durable control-plane transaction
insert new validity ArtifactContent
CAS validity_head:
    expected_head -> new validity_record_id
COMMIT
```

If CAS affects zero rows because the head changed:

```text
transaction ROLLBACK
transition FAIL/retry from newly observed canonical head
no orphan successor is canonical
```

No two validity records can both become canonical successors of one head.

Ordering authority is ONLY the CAS-protected canonical head chain. Forbidden ordering authorities:

```text
max timestamp
latest inserted row
largest UUID
filesystem order
arbitrary SQL row order
```

`effective_at_utc` is audit time, not ordering authority.

Restart/recovery opens the durable control-plane store, validates every active pointer's activation record and validity-head mapping, and accepts the state only when the pointer→activation→head chain is complete and internally consistent. Missing/corrupt linkage is fail-closed corruption, not a normal activation state.

Normal safe profile replacement creates an `INACTIVE/SUPERSEDED_SAFE` successor for the previous ACTIVE activation as part of the same crash-atomic replacement transaction where applicable. Requests already pinned to that previous activation MAY finish and commit under their pinned activation lineage.

Unsafe semantic-proof invalidation, including TTL/capture-proof invalidation, performs a CAS head transition to `SUSPENDED_INVALIDATED` and is fail-closed:

```text
requests pinned before invalidation
MUST NOT production-commit after the invalidation head becomes canonical
```

The production commit guard re-resolves the canonical validity head for the exact pinned activation. `SUSPENDED_INVALIDATED` or `REJECT_PINNED_INFLIGHT` rejects commit with typed reason `runtime_profile_invalidated`.

A safe replacement does not rewrite the invalidated record; it creates/adopts a new admitted profile/activation and its own ACTIVE validity head.

Rollback safety recheck MUST reject a rollback candidate whose previous admission exists but whose current prerequisites remain invalid. Successful rollback creates a NEW activation record and validity chain/head.

---

## 11.6 Acyclic ArtifactContent dependency rule

The semantic ArtifactContent dependency graph MUST be acyclic.

Forbidden cycles include:

```text
Artifact A digest depends on Artifact B
while Artifact B digest depends on Artifact A

GateResultManifest ↔ output ArtifactContent

RuntimeProfile ↔ acceptance/admission lineage root

CapabilityDisposition ↔ producing GateResultManifest
```

For every concrete Foundation/Task-04 artifact build graph:

```text
a topological ordering MUST exist
```

RuntimeProfileActivationRecord.previous_activation_record_id and RuntimeProfileValidityRecord.previous_validity_record_id are history-predecessor references only. They MUST reference an already-existing older record, MUST NOT self-reference, and MUST NOT reference a future record. Concrete activation/validity instance graphs therefore remain acyclic despite recursive schema type references.

Failure is non-retryable for the same candidate graph and blocks admission/activation.

---

# 12. Complete immutable/audit object catalog

R12 defines identity classes for every referenced object.

Semantic ArtifactContent types include:

```text
ArchitectureContractReference

Task01WatermarkReadContract
Task01SchemaMigrationContract
Task01GenerationRecoveryContract
Task01HealthRetentionContract

TcpSynV2SchemaContract
PortalHeadersV2SchemaContract
CapabilityDisposition
EvidenceSchemaRegistryContract
EvidenceAdapterContractSet

SourceHealthEmitterContract
EvidenceSourceBindingTimeline
BindingClockPolicy
SourceHealthPolicy
OriginRuntimeAdmission

SnapshotContentPolicy
SnapshotExecutionPolicy

ClassificationTaxonomy
AliasMapping
K3PortalRuleSet

KnowledgeFreshnessPolicy
SourceGovernanceRecord
KnowledgeProvenanceManifest
CanonicalKnowledgeRecordSet
KnowledgeBundle

ClassificationPolicy
ClassificationRetentionPolicy
ProductValidationPolicy

FoundationAdmissionManifest
FoundationRuntimeProfile
Task04AcceptanceManifest
ClassificationRuntimeProfile
RuntimeProfileAdmissionManifest
RuntimeProfileActivationRecord
RuntimeProfileValidityRecord

ClassifierArtifactManifest

EvidenceSnapshotContent
SnapshotRecord
SourceEvaluability
OriginAssessment
ClassificationRequestManifest
ClassificationResult

ControlledValidationGroundTruthRecord
ProductValidationComparisonRecord

GateResultManifest
GateProofArtifact
K2AConformancePackage
TTLCapturePlacementProof
```
Transient NON-retained execution object:

```text
EvidenceSnapshotMaterialization
```

Immutable audit records:

```text
ArtifactRegistration
DecisionRecord
```

Retained evidence files referenced by gates are identified by SHA-256 from GateResultManifest; they need not become ArtifactContent unless the relevant contract promotes them.

Appendix C defines identity, ordering and retention for every type.

## 12.1 ArchitectureContractReference

Created only after Owner + TechLead11 accept the exact architecture Markdown file.

Semantic payload:

```text
architecture_contract_name =
DEVICE-FINGERPRINT-03A-R2 / TASK-04

architecture_revision =
R12

architecture_status =
FINAL

architecture_document_sha256 =
SHA-256 of the exact accepted Markdown file bytes
```

The architecture file SHA is independent from the file body, avoiding a self-hash cycle.

## 12.2 CapabilityDisposition

Immutable semantic result for optional capability admission.

For `artifact_schema_version = 1`, fields are exactly:

```text
capability_id
status = ADMITTED | NOT_ADMITTED
ordered reason_codes
fallback_source_kind or null
fallback_feature_schema_version or null
```

`reason_codes` are SET-like with primary key = reason-code string and the universal canonical-byte tie-break.

CapabilityDisposition does NOT reference the GateResultManifest that produces it.

For `portal_headers/2`:

```text
status = ADMITTED
→ fallback_source_kind = null
→ fallback_feature_schema_version = null

status = NOT_ADMITTED
→ fallback_source_kind = portal_headers
→ fallback_feature_schema_version = 1
```

F-A5 MUST prove that this declared fallback exists in the FINAL EvidenceSchemaRegistryContract.

No dangling future registry/artifact reference is placed inside the disposition.

The Foundation gate may PASS with safe optional rejection when this CapabilityDisposition is the declared semantic output.

---

## 12.3 CanonicalKnowledgeRecordSet

K1, K2B and K4 importers each output an immutable set rather than an unnamed bag.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
knowledge_slot = K1 | K2B | K4
knowledge_record_schema_version
knowledge_provenance_id/digest
ordered records
```

`records` are SET-like sorted by:

```text
record_type
canonical_record_id
```

Duplicate canonical record IDs within the same `record_type` are forbidden.

CanonicalKnowledgeRecordSet uses the normal universal ArtifactContent identity from §10.1 and ArtifactCanonicalJsonV1.

There is NO second `record_set_sha256`-derived artifact identity and no self-hash field inside semantic payload.

## 12.4 ControlledValidationGroundTruthRecord

Immutable pre-result validation truth:

```text
validation_run_id
site_id
controlled_device_lab_label
observed_mac
window_start_utc
window_end_utc
platform_family ground truth
optional device_class ground truth
optional manufacturer_id ground truth only if independently verified
optional model_family_id ground truth only if independently verified
ground_truth_method
recorded_at_utc
```

It contains no unnecessary personal/user data.

The ArtifactRegistration/DecisionRecord attests operator/Owner acceptance.

It MUST exist before result visibility.

## 12.5 ProductValidationComparisonRecord

Immutable comparison artifact:

```text
ControlledValidationGroundTruthRecord ID/digest
ClassificationRequestManifest ID/digest
ClassificationResult ID/digest
ordered per-dimension comparison outcomes
overall validation outcome
```

Per-dimension comparisons are SET-like sorted by dimension name.


## 12.6 TcpSynV2SchemaContract

Immutable exact schema contract payload:

```text
schema_family = tcp_syn
feature_schema_version = 2
source_kind = tcp_syn
supported_scope identity
ordered top_level_field_contracts
ordered tcp_option_record_variant_contracts
privacy_minimization_contract_version
malformed_observable_contract_version
EvidenceCanonicalJsonV1 identity
```

Top-level field contracts are SET-like sorted by field name.

TCP option variant contracts are SET-like sorted by option variant canonical ID; semantic packet option order is represented by evidence records, not by schema-contract array position.

## 12.7 PortalHeadersV2SchemaContract

When admitted, immutable exact schema contract payload:

```text
schema_family = portal_headers
feature_schema_version = 2
source_kind = portal_headers
ordered normalized field contracts
normalized provenance contracts
privacy/non-durability contract version
Accept-CH bounded-lifecycle contract version
EvidenceCanonicalJsonV1 identity
```

Field/provenance contracts are SET-like sorted by canonical field ID.

## 12.8 K2AConformancePackage

Immutable compatibility package payload:

```text
p0f implementation identity/digest
p0f reference-corpus identity/digest
supported request scope
p0f runtime serializer contract version
matcher implementation contract version
ordered conformance fixture-set IDs/digests
conformance_status = PASS
```

Fixture refs are SET-like sorted by artifact/value ID.

## 12.9 TTLCapturePlacementProof

Immutable topology-specific proof payload:

```text
capture_topology_identity
running_config_evidence_sha256
source interface/VLAN identity
direction
ordered controlled packet proof records:
    packet proof ID
    sender original TTL
    sensor observed TTL
    correlated packet identity/digest
proven_distance_semantics
proof_valid_for_topology_identity
```

Packet proof records are SET-like sorted by packet proof ID.

A topology identity change invalidates this proof for the new topology.

## 12.10 GateProofArtifact

Generic immutable proof output for a gate when no domain-specific semantic artifact is required.

Payload:

```text
proof_kind
source_gate_id
candidate_repository_commit_sha
candidate_repository_tree_sha
ordered input_artifact_refs
procedure_or_test_suite_id
proof_execution_identity
canonical_result_summary
ordered retained_evidence_refs
```

Input/evidence refs are SET-like sorted using §9.3.

Canonical `proof_kind` values used by R12 include:

```text
SNAPSHOT_CONCURRENCY
SNAPSHOT_PERFORMANCE
RUNTIME_PROFILE_ATOMICITY
SNAPSHOT_MATERIALIZATION_EXECUTION
SOURCE_EVALUABILITY_EXECUTION
ORIGIN_ASSESSMENT_EXECUTION
FUSION_EXECUTION
REQUEST_ASSEMBLY_DETERMINISM
CLASSIFICATION_AUDIT_PERSISTENCE
OFFLINE_FAILURE_ISOLATION
TASK04_PRODUCT_VALIDATION
ARTIFACT_GRAPH_ACYCLICITY
CLASSIFICATION_PROFILE_COMPATIBILITY
```


## 12.11 OriginRuntimeAdmission

Immutable semantic admission artifact for classification-origin runtime enable/disable state.

For `artifact_schema_version = 1`, fields are exactly:

```text
origin_runtime_admission_contract_version

tcp_state = ENABLED | DISABLED

tcp_reason_code =
    TTL_PROOF_VALID
  | TTL_PROOF_INVALID
  | PROFILE_POLICY_DISABLED

TTLCapturePlacementProof ID/digest or null
```

Rules:

```text
tcp_state = ENABLED
→ tcp_reason_code = TTL_PROOF_VALID
→ TTLCapturePlacementProof ID/digest required

tcp_state = DISABLED
→ tcp_reason_code = TTL_PROOF_INVALID | PROFILE_POLICY_DISABLED
→ TTLCapturePlacementProof ID/digest = null
```

EvidenceSnapshotContent pins this semantic state/artifact as frozen in §28.

When TCP is disabled:

```text
tcp_syn rows remain audit-visible
TCP semantic adapter/p0f/K2B claim generation is prohibited
TCP OriginAssessment = no_claim
explanation = origin_runtime_disabled
```

This artifact is not source-health coverage and does not change SourceEvaluability semantics.

---

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

R12 does NOT claim automatic detection of an arbitrary external rollback that restores:

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

Two service-owned live paths exist.

## Production classification

RequestAssembly FIRST pins one ClassificationRuntimeProfile.

Snapshot Service then receives and uses the exact FoundationRuntimeProfile referenced by that already pinned ClassificationRuntimeProfile.

It does NOT read the active FoundationRuntimeProfile pointer separately.

## Standalone/research snapshot operation

A non-classification snapshot/research operation MAY pin the one active FoundationRuntimeProfile pointer directly.

In both cases, the ordinary caller never selects database generation, watermark or foundation artifact versions.

---

# 25. Replay snapshot mode

Audit replay uses exact retained historical identities:

```text
EvidenceSnapshotContent ID/digest
database generation
watermark
window
SnapshotRecord ID/digest
FoundationRuntimeProfile ID/digest from SnapshotRecord audit lineage
BindingTimeline ID/digest
BindingClockPolicy ID/digest
OriginRuntimeAdmission ID/digest
stored snapshot manifest
```

The FoundationRuntimeProfile is audit/execution lineage, not part of EvidenceSnapshotContent semantic identity.

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

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
EvidenceSnapshotContent ID/digest
FoundationRuntimeProfile ID/digest
snapshot_captured_at_utc
SnapshotContentPolicy ID/digest
SnapshotExecutionPolicy ID/digest
verified_evidence_row_count
verified_payload_bytes
materialized_evidence_row_count
materialized_payload_bytes
total_semantic_input_bytes
scope_anomaly_count
ordered scope_anomaly_reason_counts:
    reason_code
    count
build_outcome = "success"
```

`scope_anomaly_reason_counts` is SET-like with primary key = `reason_code` and the universal canonical-byte tie-break; duplicate reason codes are forbidden.

`verified_payload_bytes` counts canonical payload bytes for ALL authorized evidence rows whose generic JSON/hash integrity was checked, including intact unsupported future schemas.

`materialized_payload_bytes` counts only the subset semantically materialized for admitted schema adapters.

Failed/retryable snapshot attempts may be logged operationally, but no classification-linked successful SnapshotRecord is created for them.

`SnapshotRecord` is retained while any classification references it.

Duplicate-reference invariants are exact:

```text
SnapshotRecord.FoundationRuntimeProfile ID/digest
MUST equal the exact FoundationRuntimeProfile used to build the snapshot

SnapshotRecord.SnapshotContentPolicy ID/digest
MUST equal FoundationRuntimeProfile.SnapshotContentPolicy ID/digest

SnapshotRecord.SnapshotExecutionPolicy ID/digest
MUST equal FoundationRuntimeProfile.SnapshotExecutionPolicy ID/digest
```

Any mismatch:

```text
SnapshotRecord construction FAIL
```

Capture time, runtime-profile identity and execution-policy identity are not included in `EvidenceSnapshotContent` digest.

---

# 28. EvidenceSnapshotContent semantic dependencies

For `artifact_schema_version = 1`, EvidenceSnapshotContent semantic payload fields are exactly:

```text
snapshot_contract_version
site_id
observed_mac
window_start_utc
window_end_utc
database_generation_id
max_committed_ingest_sequence
EvidenceSourceBindingTimeline ID/digest
BindingClockPolicy ID/digest
EvidenceSchemaRegistryContract ID/digest
OriginRuntimeAdmission:
    artifact_id
    content_sha256
    tcp_state
    tcp_reason_code
    TTLCapturePlacementProof ID/digest or null
classification_foundation_valid_from_utc
ordered binding-epoch descriptors
ordered authorized evidence descriptors
ordered authorized source-health descriptors
```

The inline `OriginRuntimeAdmission` descriptor MUST exactly equal the referenced OriginRuntimeAdmission ArtifactContent payload relevant to V1 TCP admission.

Mismatch:

```text
SNAPSHOT BUILD FAIL
runtime_profile_incompatible
```

EvidenceSnapshotContent intentionally does NOT include:

```text
FoundationRuntimeProfile ID/digest
SnapshotExecutionPolicy ID/digest
runtime-profile admission lineage
activation timestamp
review/decision lineage
```

Therefore:

```text
same evidence membership
same watermark
same binding/clock/schema authority
same OriginRuntimeAdmission semantic state
same window
→ same EvidenceSnapshotContent digest
```

regardless of timeout/retry/memory execution policy or runtime-profile governance history.

FoundationRuntimeProfile and SnapshotExecutionPolicy remain pinned in SnapshotRecord for execution/audit lineage.

No hidden currently-active semantic builder dependency is permitted.

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

R12 therefore defines a separate transient:

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

# 32. Materialization payload integrity and unsupported-schema behavior

For every authorized evidence row inside the one SQLite read transaction:

```text
read payload_json raw text

parse JSON with duplicate-key rejection

require JSON top-level object

re-encode generic parsed object using EvidenceCanonicalJsonV1

verify canonical encoded string equals stored canonical payload_json

SHA-256(canonical payload UTF-8)
MUST equal payload_sha256
```

If generic integrity/canonical/hash verification fails:

```text
SNAPSHOT BUILD FAIL
corrupt_payload or payload_hash_mismatch

NO accepted EvidenceSnapshotContent
NO materialization
NO SourceEvaluability
NO ClassificationResult
```

Then branch on schema support:

## Known schema in EvidenceSchemaRegistryContract

```text
run the exact registered schema validator

if schema validation fails:
    SNAPSHOT BUILD FAIL
    corrupt_payload/schema_validation_failure

if validation passes:
    produce transient parsed normalized payload
    include in EvidenceSnapshotMaterialization
```

## Unknown/unsupported future schema

```text
keep durable evidence descriptor in EvidenceSnapshotContent

DO NOT semantically materialize payload for adapters

DO NOT drop the row from audit membership

EvidenceAdapter/Origin path records:
unsupported_evidence_contract

NO semantic claim from that row
```

Unknown schema therefore does NOT crash an otherwise valid snapshot merely because Task-04 has not admitted that schema.

Unknown schema also does NOT get parsed as the nearest known schema.

Corrupt bytes/hash remain hard snapshot failure regardless of schema support.

---

# 33. EvidenceSchemaRegistryContract

PRE-TASK Foundation freezes an immutable FINAL:

```text
EvidenceSchemaRegistryContract
```

The FINAL Foundation registry consumes the final schema dispositions from:

```text
F-C1 tcp_syn/2 SchemaContract

F-D1 portal_headers/2 SchemaContract
OR
CapabilityDisposition(status=NOT_ADMITTED)
```

It also includes exact existing schema validators for:

```text
dhcp/1
tcp_syn/1
tls_client/1
quic_client/1
portal_headers/1
```

The registry identifies exact normalized-schema validators and schema contract IDs/digests.

It is used only after generic payload JSON/hash integrity succeeds.

It is distinct from:

```text
EvidenceAdapterContractSet
```

which defines classification compatibility/interpretation.

Unknown source/schema:

```text
remains durably represented by its snapshot descriptor
is not semantically materialized
produces unsupported_evidence_contract
produces NO claim
```

No FINAL registry may claim support for an unaccepted candidate schema.

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

It sizes the REAL snapshot verification/materialization input, not hashes alone.

Deterministic measurement includes:

```text
authorized evidence descriptor bytes
verified_payload_bytes for ALL authorized rows whose JSON/canonical/hash integrity is checked
materialized_payload_bytes for the admitted semantic subset
authorized source-health descriptor bytes
binding descriptor bytes
required semantic dependency reference bytes
```

For each authorized evidence row whose payload integrity is checked:

```text
verified row payload bytes =
len(EvidenceCanonicalJsonV1(parsed_payload).encode("utf-8"))
```

Then:

```text
verified_payload_bytes =
sum(verified row payload bytes for ALL authorized verified rows)

materialized_payload_bytes =
sum(verified row payload bytes only for rows admitted to semantic materialization)
```

Thus an intact unknown future schema does NOT bypass deterministic sizing merely because it is later excluded from semantic adapters.

Descriptor/health/binding byte count uses ArtifactCanonicalJsonV1 over the exact canonical semantic structures.

For `artifact_schema_version = 1`, SnapshotContentPolicy semantic payload fields are exactly:

```text
snapshot_content_policy_version
max_authorized_evidence_rows
max_authorized_health_rows
max_verified_payload_bytes
max_materialized_payload_bytes
max_total_semantic_input_bytes
```

If a deterministic content ceiling is exceeded:

```text
snapshot build result = resource_limited
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

SourceHealthEmitterContract ID/digest

effective_from_utc

effective_to_utc
```

Interval:

```text
[effective_from_utc, effective_to_utc)
```

No unused `required` boolean.

Presence of binding means source expected for the interval.

If source-health semantics change under the same physical producer/service identity:

```text
new SourceHealthEmitterContract
+
new binding/contract epoch
```

Historical health is never reinterpreted under a newer emitter contract.

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

R12 does not invent historical source authority.

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

## 43.1 Runtime-profile valid-from monotonicity

For every later FoundationRuntimeProfile under the same FoundationAdmissionManifest lineage:

```text
new classification_foundation_valid_from_utc
>=
initial FoundationAdmissionManifest.classification_foundation_valid_from_utc
```

A later profile may move valid-from later when new authority/cutover semantics require it.

It MUST NOT move valid-from earlier and thereby authorize previously unproven history.

Intentional historical authority expansion requires a separate explicit architecture/re-admission proof and is not achieved by profile edit.

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

R12 deliberately removes `covered_delayed`.

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

# 46. SourceHealthEmitterContract and SourceHealthPolicy

## 46.1 SourceHealthEmitterContract

Every binding epoch references immutable `SourceHealthEmitterContract`.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
emitter_contract_version
producer_service_implementation_identity
ordered source_kinds
heartbeat_behavior_cadence_semantics
persisted_status_emission_semantics
ordered reason_code_definitions
delivery_spool_loss_behavior_relevant_to_coverage
Task-01_delayed_event_interaction
source_health_event_compatibility_version
```

`source_kinds` is SET-like with primary key = source-kind string and canonical-byte tie-break.

Each `reason_code_definition` fields are exactly:

```text
reason_code
exact_meaning
status_compatibility
failure_domain_semantics
```

Reason-code definitions are SET-like with primary key = `reason_code`; ties use canonical bytes.

Historical reason codes are interpreted only through the emitter contract referenced by their binding epoch.

---

## 46.2 SourceHealthPolicy

For `artifact_schema_version = 1`, SourceHealthPolicy semantic payload fields are exactly:

```text
source_health_policy_version
ordered accepted SourceHealthEmitterContract IDs/digests
ordered emitter_source_family_rules
Task-01 timestamp/skew contract reference
Task-01 delayed-event contract reference
health_anchor_margin_seconds requirement
```

Each `emitter_source_family_rule` fields are exactly:

```text
SourceHealthEmitterContract ID/digest
source_kind
expected heartbeat contract
freshness rule
ordered status_reason_failure_domain_mappings
coverage-class mapping
backfill rules
```

Accepted emitter refs are SET-like with primary key = artifact ID.
Family rules are SET-like with primary key `(SourceHealthEmitterContract artifact_id, source_kind)`.
Status/reason mappings are SET-like with primary key `(status, reason_code)`.
All ties use the universal canonical-byte tie-break.

Unknown/unrecognized status/reason under the bound emitter contract:

```text
→ unknown
```

No Coder guess.

No producer gets a lossless-delivery guarantee in V1.

SourceHealthPolicy activation requires health-retention compatibility defined in §49.

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

Even when historical health is backfilled, R12 does NOT infer completeness of missing device evidence.

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

Instead PRE-TASK freezes Task-01-native:

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

The margin covers the maximum interval by which a predecessor health event can still be semantically relevant at the oldest retained evidence boundary, including accepted freshness/clock uncertainty required by SourceHealthPolicy.

Cleanup remains ordinary time-based Task-01 cleanup.

Foundation proof establishes the exact margin.

No equal evidence/health retention is accepted unless proof shows margin=0.

Canonical output:

```text
Task01HealthRetentionContract
```

## 49.1 Later SourceHealthPolicy activation compatibility

A later SourceHealthPolicy candidate MUST compute its required health-retention margin before activation.

Required proof:

```text
new required health_anchor_margin_seconds
<=
Task-01 health history currently guaranteed/preserved
```

If the new policy requires older predecessor history than Task-01 has preserved:

```text
POLICY ACTIVATION BLOCKED
```

The system must first update Task-01 retention safely and accumulate sufficient history before the policy can become active.

No policy may retroactively demand health history already deleted.

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

For `artifact_schema_version = 1`, every external knowledge source has immutable `SourceGovernanceRecord` with exactly these semantic payload fields:

```text
source_name

source_provenance

license_identifier

license_source_reference

license_text_sha256 if license text is locally retained/bundled

local_storage_status

modification_import_status

redistribution_status

attribution_requirement

commercial_use_status

review_basis_semantics

unresolved_restrictions
```

Human reviewer identity/timestamp/decision registration is NOT part of semantic SourceGovernanceRecord identity.

It is captured by ArtifactRegistration + DecisionRecord/GateResultManifest.

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
knowledge_provenance_id/digest
```

`provenance_kind`:

```text
external
internal
```

## external

Semantic payload references:

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

Semantic payload references:

```text
rule-set ArtifactContent ID/digest

repository commit/tree or source artifact identity

input schema compatibility

taxonomy compatibility

rule-set version
```

Internal provenance has no fabricated external:

```text
retrieved_at aging
license status
KnowledgeFreshnessPolicy
```

Human review registration/decision identity stays in ArtifactRegistration/GateResult/DecisionRecord and is not hidden semantic knowledge input.

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

Freshness states remain exactly:

```text
fresh
stale
expired
```

Orthogonal source character remains:

```text
current
legacy
```

Threshold VALUES are proven per source from:

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

For `artifact_schema_version = 1`, KnowledgeFreshnessPolicy semantic payload fields are exactly:

```text
knowledge_freshness_policy_version
source_family_id
fresh_max_age_ms
stale_max_age_ms
ordered freshness_state_rules
```

`source_family_id` is a canonical stable lower-case ASCII source-family identifier matching:

```text
^[a-z0-9][a-z0-9._-]{0,63}$
```

It is NOT a KnowledgeProvenanceManifest ID/digest and creates no provenance↔freshness dependency cycle.

Threshold invariant:

```text
0 <= fresh_max_age_ms <= stale_max_age_ms
```

For external provenance, state evaluation uses exact canonical UTC millisecond timestamps:

```text
age_ms =
knowledge_evaluation_at_utc
-
retrieved_at_utc
```

Both timestamps use the frozen `YYYY-MM-DDTHH:MM:SS.mmmZ` representation and are converted to integer Unix/UTC milliseconds before subtraction.

State derivation is exactly:

```text
age_ms < 0
→ negative_knowledge_age
→ request/admission evaluation FAILS CLOSED

age_ms <= fresh_max_age_ms
→ fresh

fresh_max_age_ms < age_ms <= stale_max_age_ms
→ stale

age_ms > stale_max_age_ms
→ expired
```

No prose freshness expression is executed by Coder/runtime in V1.

A future source requiring a different freshness basis requires a new KnowledgeFreshnessPolicy schema version.

`freshness_state_rules` is SET-like with primary key = `freshness_state`; ties use ArtifactCanonicalJsonV1 bytes. The canonical enum order used for display/test vectors is `fresh`, `stale`, `expired`.

Each freshness-state rule fields are exactly:

```text
freshness_state = fresh | stale | expired
claim_eligible = true | false
claim_strength_cap = NO_ADDITIONAL_CAP | strong | supporting | NONE
required_explanation_code or null
ordered dimension_overrides
```

Each dimension override fields are exactly:

```text
dimension_name
claim_eligible
claim_strength_cap
required_explanation_code or null
```

Dimension overrides are SET-like with primary key = `dimension_name`, then canonical-byte tie-break.

Consistency:

```text
claim_eligible = false
→ claim_strength_cap = NONE

claim_eligible = true
→ claim_strength_cap != NONE
```

Required expired behavior remains:

```text
expired
→ claim_eligible = false
→ claim_strength_cap = NONE
→ required explanation identifies knowledge_source_expired
```

`fresh` and `stale` behavior is source-specific and MUST be explicit in the admitted policy.

A proven policy MAY define, for example:

```text
stale → claim eligible, supporting ceiling
```

or another reviewed source/dimension-specific rule.

There is NO universal invented stale downgrade.

### 81.1 Claim-strength cap precedence

Freshness can only preserve or REDUCE admitted claim authority.

For an eligible claim, effective strength is exactly:

```text
effective_strength =
minimum_authority(
    admitted base claim strength,
    applicable KnowledgeFreshnessPolicy cap,
    every other already-admitted claim-strength ceiling
)
```

Authority ordering for strength values is:

```text
strong > supporting
```

`NO_ADDITIONAL_CAP` means the freshness rule contributes no additional ceiling.

`NONE` means no claim may be emitted and is valid only with `claim_eligible = false`.

Examples:

```text
base supporting
+
freshness cap strong
→ supporting

base strong
+
freshness cap supporting
→ supporting

NO_ADDITIONAL_CAP
→ base strength unchanged subject to other admitted ceilings

NONE
→ no claim
```

If a matching dimension override exists:

```text
the matching dimension override REPLACES
the general freshness-state rule
FOR THAT DIMENSION ONLY
```

All other dimensions use the general state rule.

`claim_eligible = false` always suppresses claim creation regardless of any strength field.

The required explanation code emitted is exactly the code from the chosen applicable rule: dimension override when matched, otherwise general state rule.

ClassificationPolicy executes this admitted behavior. Coder does not invent stale state, cap precedence or override precedence.

# 82. KnowledgeBundle

For `artifact_schema_version = 1`, immutable KnowledgeBundle semantic payload fields are exactly:

```text
bundle_schema_version

ClassificationTaxonomy ID/digest

AliasMapping ID/digest

ordered KnowledgeProvenanceManifest IDs/digests

ordered SourceGovernanceRecord IDs/digests for external sources only

ordered KnowledgeFreshnessPolicy IDs/digests for changing external sources only

K1 CanonicalKnowledgeRecordSet ID/digest

K2B CanonicalKnowledgeRecordSet ID/digest

K3PortalRuleSet ID/digest

K4 CanonicalKnowledgeRecordSet ID/digest
```

All reference arrays are SET-like and sorted lexicographically by artifact ID.

Duplicate direct/transitive inventory invariants are exact:

```text
ordered SourceGovernanceRecord refs
= EXACT deduplicated transitive external governance refs
  reachable from the bundle's external KnowledgeProvenanceManifests

ordered KnowledgeFreshnessPolicy refs
= EXACT deduplicated transitive changing-external freshness-policy refs
  reachable from the bundle's external KnowledgeProvenanceManifests
```

No extra refs and no missing refs are allowed.

Additionally:

```text
every K1/K2B/K4 CanonicalKnowledgeRecordSet.knowledge_provenance ref
MUST be present in the bundle KnowledgeProvenanceManifest refs

K3PortalRuleSet internal KnowledgeProvenanceManifest
MUST be present
```

JA4 normalized evidence remains supported/auditable under the frozen §93 safety contract, but KnowledgeBundle schema V1 contains NO JA4 CanonicalKnowledgeRecordSet because CanonicalKnowledgeRecordSet schema V1 has only K1/K2B/K4 record variants.

Without a separately versioned future JA4 knowledge schema:

```text
TLS/QUIC JA4 evidence
→ NO semantic JA4 classification claim
```

Future JA4 classification knowledge requires:

```text
new CanonicalKnowledgeRecordSet schema/version
+
new KnowledgeBundle schema/version
+
separate architecture/admission review
```

No raw vendor schema is part of runtime.

No external audit registration UUID is inserted into semantic bundle content.

---

# 83. KnowledgeBundle activation/pinning

KnowledgeBundle ArtifactContent is immutable.

A bundle refresh never mutates the active bundle in place.

Post-F-ADMIT runtime activation occurs only through a newly admitted ClassificationRuntimeProfile that references the new KnowledgeBundle.

For a KnowledgeBundle-only refresh, dependency order is exactly:

```text
1. validate/import refreshed knowledge

2. construct new immutable KnowledgeBundle

3. construct candidate ClassificationRuntimeProfile
   referencing that already-existing KnowledgeBundle

4. run exact §11.3 profile compatibility checks

5. run the bounded prerequisite knowledge/governance/freshness/bundle
   admission/regression gates required by update_class=KNOWLEDGE_BUNDLE_REFRESH

6. construct RuntimeProfileAdmissionManifest(
       update_class=KNOWLEDGE_BUNDLE_REFRESH
   )
   referencing the already-existing candidate ClassificationRuntimeProfile
   and only prerequisite GateResults

7. create DecisionRecord where Appendix G/Owner policy requires it

8. perform the separate crash-atomic §11.5 classification activation action:
       precompute RuntimeProfileActivationRecord + initial ACTIVE RuntimeProfileValidityRecord
       insert both records + initialize validity head + switch CRP pointer in one durable transaction
```

No RuntimeProfileAdmissionManifest may be constructed before its candidate ClassificationRuntimeProfile exists.

No full Task-04 implementation reacceptance is required when:

```text
classifier implementation unchanged
ClassificationPolicy unchanged
EvidenceAdapterContractSet unchanged
foundation profile unchanged
all compatibility checks PASS
update_class field-delta rules PASS
```

In that bounded case, RuntimeProfileAdmissionManifest reuses the explicitly permitted prior Task04AcceptanceManifest lineage under Appendix G.

In-flight request stays on its already pinned old ClassificationRuntimeProfile.

Rollback follows `ROLLBACK_REACTIVATION` §11.5.1; bundle/profile bytes never mutate.

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

For OriginDimensionAssessment contract version 1, fields are exactly:

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

### CandidateEntry exact schema

Each `candidate_set` element fields are exactly:

```text
candidate_kind = CANONICAL_VALUE | OUT_OF_SCOPE_TAXON
candidate_value_id or null
out_of_scope_taxon_ref or null
claim_strength = strong | supporting
claim_derivation = declared | deterministic_mapping | fingerprint_match | registry_mapping
ordered knowledge_refs
ordered evidence_refs
```

Exactly one of `candidate_value_id` / `out_of_scope_taxon_ref` is non-null according to `candidate_kind`.

Candidate SET primary sort key is exactly:

```text
(candidate_kind,
 candidate_value_id-or-empty,
 out_of_scope_taxon_ref-or-empty,
 claim_strength,
 claim_derivation)
```

Equal primary keys use ArtifactCanonicalJsonV1(element) UTF-8 bytes as the total tie-break.

### EvidenceRef exact schema

Fields are exactly:

```text
evidence_id
payload_sha256
feature_schema_version
adapter_contract_id
adapter_contract_digest
```

Evidence-ref SET primary key = `evidence_id`; ties use canonical bytes.

### KnowledgeRef exact schema

Fields are exactly:

```text
knowledge_bundle_id
knowledge_bundle_digest
canonical_knowledge_record_id
knowledge_provenance_id
knowledge_provenance_digest
rule_or_source_record_identity
```

Knowledge-ref SET primary sort key is exactly:

```text
(knowledge_provenance_id,
 canonical_knowledge_record_id,
 rule_or_source_record_identity)
```

then canonical-byte tie-break.

### SameOriginContradictionRecord exact schema

Fields are exactly:

```text
dimension_name
conflict_strength = strong | supporting
retained_candidate_key or null
ordered incompatible_candidate_keys
ordered evidence_refs
ordered knowledge_refs
explanation_code
```

`incompatible_candidate_keys` is SET-like with primary key = candidate-key string, then canonical-byte tie-break.

Contradiction-record SET primary sort key is exactly:

```text
(dimension_name,
 conflict_strength,
 retained_candidate_key-or-empty)
```

then canonical-byte tie-break.

### BroadUnresolvedRef exact schema

Fields are exactly:

```text
reference_kind = BROAD_TAXON | UNMAPPED_TAXON
canonical_taxon_or_source_ref
ordered evidence_refs
ordered knowledge_refs
explanation_code
```

Broad/unresolved SET primary sort key is exactly:

```text
(reference_kind, canonical_taxon_or_source_ref)
```

then canonical-byte tie-break.

`claim_derivations` and `explanation_codes` are SET-like strings sorted lexicographically, with canonical-byte tie-break.

## 101.1 OriginAssessment exact top-level ArtifactContent

For `artifact_schema_version = 1`, OriginAssessment semantic payload fields are exactly:

```text
origin_assessment_contract_version
EvidenceSnapshotContent ID/digest
SourceEvaluability ID/digest
origin_group
ordered OriginDimensionAssessment objects
ordered evidence_refs
ordered knowledge_refs
ordered explanation_codes
```

OriginDimensionAssessment objects are SET-like with primary key = `dimension_name`, then canonical-byte tie-break.

Top-level evidence/knowledge refs use the exact schemas and sort keys defined above.

Top-level explanation codes are SET-like sorted lexicographically, then canonical-byte tie-break.

`mac_registry` references the overall SourceEvaluability ArtifactContent ID/digest even though SourceEvaluability has no `mac_registry` source entry.

No Coder-defined OriginAssessment semantic/audit fields are allowed under artifact schema version 1.

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

For `artifact_schema_version = 1`, semantic payload fields are exactly:

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
knowledge-freshness policy execution semantics
```

The freshness execution semantic is exactly:

```text
for an external-knowledge claim:
    resolve the KnowledgeFreshnessPolicy referenced by its admitted provenance
    evaluate it at explicit knowledge_evaluation_at_utc
    apply fresh/stale/expired claim_eligible
    apply claim_strength_cap
    apply dimension override when present
    emit the required explanation code
```

ClassificationPolicy does NOT invent source-specific freshness thresholds or stale caps.

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

`EvidenceSnapshotContent` already reflects accepted snapshot construction and OriginRuntimeAdmission semantics.

No cross-layer policy coupling.

The executable V1 machine representation of these already-frozen semantics is the closed typed schema in Appendix C.3.23. Implementations MUST execute that representation directly; arbitrary condition/outcome string parsers are forbidden. C.3.23 changes representation closure only and does not alter §§101–110 semantics.

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

The service captures it only after pinning one ClassificationRuntimeProfile and loading exactly that profile's referenced KnowledgeBundle, ClassificationPolicy, EvidenceAdapterContractSet and ClassifierArtifactManifest.

Validation:

For every external source used for possible claims:

```text
knowledge_evaluation_at_utc
MUST be >= source retrieved_at_utc
```

If negative source age would occur:

```text
REQUEST ASSEMBLY FAILS CLOSED
negative_knowledge_age
NO ClassificationResult
```

For REPLAY:

```text
use exact stored historical knowledge_evaluation_at_utc
```

`profile activated_at` is never used as source freshness time.

---

# 113. RequestAssembly pin-once boundary

LIVE PRODUCTION classification proceeds exactly once:

```text
1. atomically read ONE active classification pointer tuple:
       ClassificationRuntimeProfile ID/digest
       RuntimeProfileActivationRecord ID
       activation_generation_id

2. resolve and pin the exact RuntimeProfileActivationRecord;
   validate that its profile ID/digest equals the pointer tuple;
   resolve the exact CAS-protected canonical RuntimeProfileValidityRecord head
   for that activation and require it permits new execution

3. pin exact ClassificationRuntimeProfile ID/digest

4. load the exact FoundationRuntimeProfile referenced by that profile

5. build EvidenceSnapshotContent + transient EvidenceSnapshotMaterialization
   using THAT FoundationRuntimeProfile

6. build SourceEvaluability using the SourceHealthPolicy/emitter/binding contracts
   from the already pinned FoundationRuntimeProfile

7. load exactly the KnowledgeBundle,
   ClassificationPolicy,
   EvidenceAdapterContractSet,
   ClassifierArtifactManifest
   referenced by the already pinned ClassificationRuntimeProfile

8. validate all profile compatibility invariants

9. capture trusted central knowledge_evaluation_at_utc

10. validate non-negative external knowledge ages

11. create semantic ClassificationRequestManifest

12. invoke pure core with the pinned semantic input objects
```

After step 1:

```text
NO active runtime-profile pointer is re-read for semantic input selection
```

The exact production execution lineage is the pinned successful RuntimeProfileActivationRecord plus its canonical validity-head chain.

Concurrent safe FoundationRuntimeProfile or ClassificationRuntimeProfile activation does not alter the in-flight request.

A newly active FoundationRuntimeProfile does not automatically affect production classification. Only a ClassificationRuntimeProfile that explicitly references it can do so.

The exact classification activation lineage is execution/audit context and is NOT part of the pure ClassificationRequestManifest digest.

Standalone/research snapshot operations may use the active FoundationRuntimeProfile pointer directly under §24.

Task-04 acceptance may exercise the same RequestAssembly implementation against an exact non-production candidate ClassificationRuntimeProfile supplied by the acceptance harness. For that mode:

```text
execution_context = PRE_ACCEPTANCE_CANDIDATE
RuntimeProfileActivationRecord = null
```

Product callers still cannot select profiles.

Replay uses retained exact semantic request inputs, retained exact activation/profile audit lineage and historical knowledge time.

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

OriginRuntimeAdmission semantics are pinned inside EvidenceSnapshotContent.

When:

```text
EvidenceSnapshotContent.OriginRuntimeAdmission.tcp_state = DISABLED
```

pure execution MUST enforce:

```text
tcp_syn evidence remains audit-visible where otherwise retained
TCP semantic claim generation = prohibited
p0f/K2B claim path = prohibited
TCP OriginAssessment internal_state = no_claim
explanation_codes include origin_runtime_disabled
```

No FoundationRuntimeProfile object is read by pure core.

---

# 115. ClassifierArtifactManifest

For `artifact_schema_version = 1`, semantic payload fields are exactly:

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

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
EvidenceSnapshotContent ID/digest
SourceEvaluability ID/digest
KnowledgeBundle ID/digest
ClassificationPolicy ID/digest
EvidenceAdapterContractSet ID/digest
ClassifierArtifactManifest ID/digest
knowledge_evaluation_at_utc
```

Its content digest is the exact:

```text
classification_request_digest
```

ClassificationRequestManifest intentionally does NOT include:

```text
ClassificationRuntimeProfile ID/digest
FoundationRuntimeProfile ID/digest
SnapshotExecutionPolicy ID/digest
runtime-profile admission lineage
activation/review/decision identity
```

Therefore a change only to timeout/retry/memory guard or governance/admission lineage does NOT change the semantic request digest when all pure semantic inputs are unchanged.

RequestAssembly validates that the individual semantic ArtifactContent IDs loaded from the pinned ClassificationRuntimeProfile exactly equal the IDs referenced in this manifest.

Runtime-profile IDs remain persisted separately as execution/audit lineage under §118.

No retention/product-validation policy affects request identity.

---

# 117. Semantic ClassificationResult

For `artifact_schema_version = 1`, semantic payload fields are exactly:

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

Task-04 uses a dedicated Classification SQLite separate from Task-01 evidence SQLite.

The per-classification persistence CORE contains only information available at classification execution time:

```text
classification_id
site_id
observed_mac
classified_at_utc
execution_context = PRODUCTION | PRE_ACCEPTANCE_CANDIDATE
ClassificationRuntimeProfile ID/digest
FoundationRuntimeProfile ID/digest
classification RuntimeProfileActivationRecord ID or null
ClassificationRequestManifest ID/digest
ClassificationResult ID/digest
SnapshotRecord ID/digest
ClassificationRetentionPolicy ID/digest
```

Cross-field rules:

```text
execution_context = PRODUCTION
→ RuntimeProfileActivationRecord ID REQUIRED

execution_context = PRE_ACCEPTANCE_CANDIDATE
→ RuntimeProfileActivationRecord ID = null
```

The per-classification core row does NOT require:

```text
Task04AcceptanceManifest
Classification RuntimeProfileAdmissionManifest
Foundation RuntimeProfileAdmissionManifest
```

Those are profile/admission governance lineage, not semantic classification execution data.

For production rows, the exact RuntimeProfileActivationRecord resolves unambiguously:

```text
classification activation
→ ClassificationRuntimeProfile
→ RuntimeProfileAdmissionManifest
→ Task04AcceptanceManifest / permitted reused lineage
→ Decision/admission lineage
```

No fake/null future acceptance identifiers are inserted into production rows.

Duplicate-reference invariant:

```text
persisted FoundationRuntimeProfile ID/digest
MUST equal
persisted ClassificationRuntimeProfile.FoundationRuntimeProfile ID/digest
```

Mismatch:

```text
persistence FAIL
```

## 118.1 Production commit admission invariant

A PRODUCTION classification may be committed only when the exact pinned classification RuntimeProfileActivationRecord:

```text
exists
resolves to the persisted ClassificationRuntimeProfile ID/digest
resolves to an admitted RuntimeProfileAdmissionManifest/Task04Acceptance lineage
and remains valid for production commit under the CAS-protected canonical RuntimeProfileValidityRecord head
```

The service re-resolves the CAS-protected canonical validity head for the exact pinned activation immediately before commit. Timestamp/UUID/insertion ordering is never used to select validity.

Rules:

```text
ACTIVE
→ commit allowed

INACTIVE + ALLOW_PINNED_INFLIGHT
→ commit allowed only for a request proven pinned before that deactivation

SUSPENDED_INVALIDATED
or REJECT_PINNED_INFLIGHT
→ production commit rejected
→ reason = runtime_profile_invalidated
```

For TTL/capture-proof invalidation specifically, a request pinned before invalidation is NOT grandfathered; production commit is rejected after invalidation takes effect.

Admission/validity verification is an execution/persistence guard and is NOT part of the pure ClassificationRequest digest.

## 118.2 Acceptance-harness persistence

T-07/T-09 may persist the exact pre-acceptance candidate profile into an isolated acceptance Classification SQLite.

Acceptance-only rows:

```text
use the same persistence CORE schema
execution_context = PRE_ACCEPTANCE_CANDIDATE
use the exact T-06A candidate profile ID/digest
RuntimeProfileActivationRecord ID = null
do not require future T-ACCEPT artifacts
do not represent production admission
```

No classification row mutation is required after T-ACCEPT.

Production admission lineage is established at the profile activation level after acceptance.

SnapshotRecord and every referenced replay artifact MUST remain retrievable while the classification is retained.

No dangling audit IDs.

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

While a classification is retained, retain retrievable:

```text
EvidenceSnapshotContent
SnapshotRecord
SourceEvaluability
OriginAssessments
ClassificationRequestManifest
ClassificationResult
FoundationAdmissionManifest lineage root
FoundationRuntimeProfile
ClassificationRuntimeProfile
Foundation RuntimeProfileAdmissionManifest(s) required by retained profile lineage
Classification RuntimeProfileAdmissionManifest(s) required by retained profile lineage
RuntimeProfileActivationRecord referenced by every retained production classification
RuntimeProfileValidityRecord chain required to explain that activation's admissibility/invalidation history
Task04AcceptanceManifest for the referenced classifier/profile lineage
KnowledgeBundle
ClassificationPolicy
EvidenceAdapterContractSet
EvidenceSchemaRegistryContract
SourceHealthPolicy
SourceHealthEmitterContract(s)
SnapshotContentPolicy
EvidenceSourceBindingTimeline
BindingClockPolicy
KnowledgeFreshnessPolicies
ClassifierArtifactManifest
ProductValidationPolicy where referenced
```

Digest without retrievable content is not replay.

Production classification admission lineage is resolved first through the exact retained RuntimeProfileActivationRecord stored in the classification persistence CORE, then through its RuntimeProfileAdmissionManifest and acceptance/decision lineage. Profile ID alone is never used as a one-to-one activation-lineage key because the same immutable profile may be activated multiple times.

After classification expiry, an artifact is GC-eligible only when no other retained classification/reference requires it.

## Level A

```text
Task-01 source evidence/health rows
→ EvidenceSnapshotContent/Materialization
→ SourceEvaluability
→ OriginAssessment
```

Only while required Task-01 rows and compatible generation remain available.

## Level B

```text
retained SourceEvaluability
+
retained OriginAssessments
+
retained runtime profiles/policies/bundle/classifier/request
→ ClassificationResult
```

must remain possible for the full classification-history retention period.

Transient normalized payload materialization is NOT retained in classification storage merely to extend Level-A replay.

---

# 121. No automatic learning / knowledge mutation

Controlled validation is:

```text
validation
regression
false-positive detection
support-policy validation
```

It is NOT:

```text
online training
automatic rule generation
automatic alias creation
automatic KnowledgeBundle mutation
automatic claim-strength tuning
```

Permanent:

```text
ClassificationResult
NEVER automatically rewrites
rules / aliases / knowledge records / strengths
```

If validation discovers an error:

```text
candidate FAIL
→ reviewed architecture/knowledge/policy/code correction
→ new immutable versioned artifact
→ rerun applicable gates
```

No result-driven production learning.

## 121.1 Post-F-ADMIT runtime artifact update / re-admission rules

Every active runtime profile has an auditable admission path.

A FoundationRuntimeProfile activation by itself NEVER changes production classification traffic.

For every FoundationRuntimeProfile update intended to affect live classification:

```text
construct/admit new FoundationRuntimeProfile
construct a compatible new ClassificationRuntimeProfile
using already accepted classifier/policy/bundle where allowed
admit that ClassificationRuntimeProfile
atomically switch the ClassificationRuntimeProfile pointer
```

Until that ClassificationRuntimeProfile switch occurs:

```text
production classification remains entirely on the old ClassificationRuntimeProfile
and the old FoundationRuntimeProfile referenced by it
```

Because production classification pins ClassificationRuntimeProfile first, an independently newer active FoundationRuntimeProfile MUST NOT make normal classification fail with a torn-profile mismatch.

If the old classification generation becomes unsafe, classification is suspended at the unsafe path until a safe compatible ClassificationRuntimeProfile is active; it is not allowed to mix new Foundation state into the old ClassificationRuntimeProfile.

### KnowledgeBundle-only refresh

Requires the exact build/admission order in §83:

```text
new KnowledgeBundle
→ candidate ClassificationRuntimeProfile
→ compatibility
→ bounded prerequisite gates
→ RuntimeProfileAdmissionManifest(update_class=KNOWLEDGE_BUNDLE_REFRESH)
→ DecisionRecord where required
→ atomic ClassificationRuntimeProfile switch
```

Existing Task04AcceptanceManifest lineage MAY be reused only because classifier/policy/adapters/foundation semantics are unchanged and Appendix G explicitly permits reuse.

### KnowledgeFreshnessPolicy semantic change

Because external KnowledgeProvenanceManifest and KnowledgeBundle reference KnowledgeFreshnessPolicy identity, change requires:

```text
new KnowledgeFreshnessPolicy
+
new affected KnowledgeProvenanceManifest
+
new KnowledgeBundle
+
new compatible ClassificationRuntimeProfile
+
normal admission/compatibility proof
```

A freshness-policy-only active runtime state is forbidden.

Existing Task04AcceptanceManifest MAY be reused only when the accepted classifier already implements the unchanged generic KnowledgeFreshnessPolicy execution contract and no ClassificationPolicy/EvidenceAdapter/Classifier semantic artifact changes.

### BindingTimeline / capture topology change

Requires:

```text
binding/clock/source-authority proof
new EvidenceSourceBindingTimeline/BindingClockPolicy as applicable
new OriginRuntimeAdmission
new TTL/RSPAN proof if TCP semantics are affected
OR OriginRuntimeAdmission with TCP disabled for a post-admission safety transition
new FoundationRuntimeProfile
RuntimeProfileAdmissionManifest
```

If intended to affect production classification, also construct/admit and atomically activate a compatible new ClassificationRuntimeProfile that references the new FoundationRuntimeProfile.

### SourceHealthEmitterContract or SourceHealthPolicy change

Requires:

```text
emitter semantics proof where applicable
health semantics proof
health-retention-margin compatibility proof
new binding/contract epoch when emitter semantics change
new FoundationRuntimeProfile
RuntimeProfileAdmissionManifest
```

If intended for production classification, also admit/activate a compatible new ClassificationRuntimeProfile.

A SourceHealthPolicy whose required retention margin exceeds already-preserved Task-01 health history cannot activate until sufficient history has accumulated.

### SnapshotContentPolicy change

Requires new sizing/query/WAL proof, new FoundationRuntimeProfile and admission manifest.

If intended for production classification, also admit/activate a compatible new ClassificationRuntimeProfile.

### SnapshotExecutionPolicy-only operational change

Requires bounded operational safety proof and a new FoundationRuntimeProfile because SnapshotRecord/audit pins the execution policy.

It does NOT change EvidenceSnapshotContent or ClassificationRequest semantic digest by itself.

If intended for production classification, a compatible new ClassificationRuntimeProfile references the new FoundationRuntimeProfile; no pure semantic reacceptance is required when pure semantic artifacts are unchanged.

### Evidence schema / EvidenceSchemaRegistry change

Requires:

```text
foundation schema/registry admission
+
EvidenceAdapter/classifier compatibility regression
+
new FoundationRuntimeProfile when registry changes
+
new ClassificationRuntimeProfile
```

If the change modifies classifier semantic behavior, it requires NEW Task04AcceptanceManifest under §125/Appendix G.

### EvidenceAdapterContractSet semantic change

Requires:

```text
foundation adapter admission
+
applicable Task-04 semantic/regression/product gates
+
new compatible classifier implementation identity where required
+
new ClassificationRuntimeProfile
+
NEW Task04AcceptanceManifest
```

Old Task04AcceptanceManifest does not bless a new adapter semantic contract.

### ClassificationPolicy semantic change

Requires:

```text
Task-04 semantic/regression/product acceptance
+
new ClassificationRuntimeProfile
+
NEW Task04AcceptanceManifest
```

### ClassifierArtifact semantic/code change

Requires:

```text
applicable Task-04 acceptance gates
+
new ClassifierArtifactManifest
+
new ClassificationRuntimeProfile
+
NEW Task04AcceptanceManifest
```

### Foundation valid-from later

A later admitted FoundationRuntimeProfile may move `classification_foundation_valid_from_utc` later only under §43.1 proof/admission.

A compatible ClassificationRuntimeProfile is required before that later valid-from affects production classification.

### Rollback reactivation

Uses exactly:

```text
update_class = ROLLBACK_REACTIVATION
```

and §11.5.1 / Appendix G.

No accepted artifact is placed behind an active pointer merely because it exists.

Any update class requiring Task-04 semantic reacceptance MUST produce a NEW Task04AcceptanceManifest referencing the exact newly tested candidate ClassificationRuntimeProfile before activation.

Reuse of an existing Task04AcceptanceManifest is permitted only for update classes explicitly marked REUSE in Appendix G.

## 121.2 TTL/RSPAN proof invalidation stop action

If capture topology/config relevant to TTL semantics changes:

```text
current TTLCapturePlacementProof = INVALID FOR NEW TOPOLOGY
```

The currently active ClassificationRuntimeProfile that would keep using that proof is unsafe for new classification traffic.

Until a safe replacement ClassificationRuntimeProfile activates:

```text
classification traffic using the unsafe profile MUST be suspended
```

Safe replacement uses either:

```text
new valid TTLCapturePlacementProof
→ OriginRuntimeAdmission(tcp=ENABLED)
```

or:

```text
OriginRuntimeAdmission(tcp=DISABLED)
```

followed by:

```text
new FoundationRuntimeProfile
+
compatible new ClassificationRuntimeProfile
+
required admission manifests
+
atomic ClassificationRuntimeProfile activation
```

After safe activation:

```text
TCP enabled profile
→ TCP/p0f may resume

TCP disabled profile
→ other origins may classify safely
→ TCP OriginAssessment = no_claim / origin_runtime_disabled
```

For a planned topology change, safe replacement profiles SHOULD be admitted before cutover.

Receiving packets is not evidence that the old TTL proof remains valid.

---

# 122. ProductValidationPolicy

No undefined "primary dimension".

Validation evaluates every dimension for which controlled ground truth is actually known.

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
support_level >= medium

Owner Windows laptop:
platform_family = windows
resolved
support_level >= medium

Across those two controlled devices:
at least one correct device_class
resolved
support_level >= medium
```

Manufacturer/model may remain unresolved where independently verified ground truth/evidence does not justify them.

Always-unknown classifier cannot pass.

## 122.1 Pre-result ground truth

For every controlled validation request:

```text
ControlledValidationGroundTruthRecord
MUST be committed/registered
BEFORE ClassificationResult is visible to the evaluator
```

It binds the known controlled physical device to:

```text
validation_run_id
site_id
observed_mac
window_start_utc
window_end_utc
known ground-truth dimensions
ground_truth_method
recorded_at_utc
```

Ground truth is never inferred from fingerprints.

No result-driven relabeling.

## 122.2 Comparison record

After classifier execution, create:

```text
ProductValidationComparisonRecord
```

referencing:

```text
GroundTruthRecord ID/digest
ClassificationRequestManifest ID/digest
ClassificationResult ID/digest
comparison outcome
```

Validation result never mutates production artifacts automatically.

---

# 123. GateResultManifest

Every Foundation and Task-04 gate PASS/FAIL is machine/audit-identifiable.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
gate_id
gate_contract_version
status = PASS | FAIL
candidate_repository_commit_sha or null
candidate_repository_tree_sha or null
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
    path_or_reference or null
proof_execution_identity:
    execution_id = canonical lowercase UUIDv4
    executor_kind
    repository_commit_sha or null
    repository_tree_sha or null
    procedure_or_test_suite_id
    environment_identity
    execution_artifact_sha256 or null
trusted_time_inputs:
    foundation_knowledge_evaluation_at_utc or null
    foundation_admission_evaluation_at_utc or null
    knowledge_evaluation_at_utc or null
ordered decision_record_refs
```

Canonical ordering:

```text
input/output artifact refs = SET primary key artifact_id
retained evidence refs = SET primary key (evidence_label, file_sha256)
decision_record_refs = SET primary key decision_record_id
```

All ties use §9.3 canonical-byte tie-break.

No undefined ReviewRecord/review-registration reference exists. Material Owner/TechLead review decisions use DecisionRecord.

A GateResultManifest MUST NOT be a semantic dependency of an ArtifactContent that the same GateResultManifest lists as its output.

Gate status cannot exist only in chat prose.

---

# 124. FoundationAdmissionManifest — immutable initial lineage root

FoundationAdmissionManifest records the exact Foundation set that passed INITIAL Foundation Admission.

It is NOT a forever-current runtime artifact set.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
foundation_manifest_version
ArchitectureContractReference ID/digest
architecture_document_sha256
foundation_repository_commit_sha
foundation_repository_tree_sha
foundation_knowledge_evaluation_at_utc
foundation_admission_evaluation_at_utc
classification_foundation_valid_from_utc
Task-01 database schema/generation contract version
Task-01 watermark/generation contract version
ordered mandatory pre-admission Foundation gate IDs
ordered pre-admission GateResultManifest IDs/digests
initial accepted EvidenceSchemaRegistryContract ID/digest
initial accepted EvidenceAdapterContractSet ID/digest
initial accepted KnowledgeBundle ID/digest
initial accepted EvidenceSourceBindingTimeline ID/digest
initial accepted BindingClockPolicy ID/digest
initial accepted SourceHealthPolicy ID/digest
initial accepted SourceHealthEmitterContract IDs/digests
initial accepted SnapshotContentPolicy ID/digest
initial accepted SnapshotExecutionPolicy ID/digest
initial accepted ClassificationPolicy ID/digest
initial accepted ClassificationRetentionPolicy ID/digest
initial accepted ProductValidationPolicy ID/digest
initial accepted KnowledgeFreshnessPolicy IDs/digests
initial accepted SourceGovernanceRecord IDs/digests
initial accepted KnowledgeProvenanceManifest IDs/digests
initial accepted K2AConformancePackage ID/digest
initial accepted TTLCapturePlacementProof ID/digest
initial accepted OriginRuntimeAdmission ID/digest
portal_headers/2 CapabilityDisposition ID/digest
```

`mandatory pre-admission Foundation gate IDs` and `pre-admission GateResultManifest` refs EXCLUDE F-ADMIT itself and the F-ADMIT GateResultManifest that outputs this lineage root.

All SET-like gate/artifact reference arrays use artifact/gate ID primary keys plus §9.3 tie-break.

`foundation_knowledge_evaluation_at_utc` is the trusted source-policy/governance proof time captured at F-E5.

`foundation_admission_evaluation_at_utc` is separately captured by F-ADMIT immediately for FINAL Foundation admission freshness re-evaluation.

Both are tool/service-owned trusted central times and are not user-backdated.

Mandatory external-source freshness PASS at F-ADMIT is evaluated against `foundation_admission_evaluation_at_utc`, not merely the older F-E5 proof time.

Initial V1 FoundationAdmissionManifest MUST record:

```text
initial accepted TTLCapturePlacementProof = non-null PASS proof

initial accepted OriginRuntimeAdmission.tcp_state = ENABLED
initial accepted OriginRuntimeAdmission.tcp_reason_code = TTL_PROOF_VALID
```

Initial Foundation Admission cannot use TCP-disabled admission as a substitute for F-C3 PASS.

FoundationAdmissionManifest never changes when later runtime artifacts refresh.

Later runtime semantic sets are represented by FoundationRuntimeProfile versions and their RuntimeProfileAdmissionManifests.

Task-04 lineage remains anchored to this root.

---

# 125. Task04AcceptanceManifest — implementation lineage root

Task04AcceptanceManifest records one accepted Task-04 implementation lineage.

For `artifact_schema_version = 1`, semantic payload fields are exactly:

```text
FoundationAdmissionManifest ID/digest
Task-04 candidate repository commit SHA
Task-04 candidate repository tree SHA
ClassifierArtifactManifest ID/digest
tested ClassificationRuntimeProfile ID/digest
ordered mandatory pre-acceptance Task-04 gate IDs
ordered pre-acceptance Task-04 GateResultManifest IDs/digests
accepted ClassificationResult schema version
accepted persistence/audit contract version
ordered accepted ProductValidationComparisonRecord IDs/digests
```

Mandatory gate IDs include all required T-gates for the candidate, including the candidate-profile compatibility gate, and EXCLUDE T-ACCEPT itself.

Pre-acceptance GateResult refs EXCLUDE the T-ACCEPT GateResultManifest that outputs this lineage root.

The `tested ClassificationRuntimeProfile ID/digest` MUST be the exact candidate profile digest exercised by T-05 and T-09. T-ACCEPT accepts that exact profile but does NOT activate production; any later production activation uses the same already-tested digest under §163.1.

Task04AcceptanceManifest does NOT appear inside ClassificationRuntimeProfile semantic content.

It does NOT itself authorize production deployment.

After T-ACCEPT, RuntimeProfileAdmissionManifest links this Task04AcceptanceManifest to the exact already-tested ClassificationRuntimeProfile before production pointer activation.

A later classifier implementation change requires a new Task04AcceptanceManifest lineage.

Additionally, ANY update class that Appendix G marks as requiring Task-04 semantic reacceptance MUST create a NEW Task04AcceptanceManifest referencing the exact newly tested candidate ClassificationRuntimeProfile.

At minimum this includes semantic changes to:

```text
ClassificationPolicy
EvidenceAdapterContractSet
ClassifierArtifact
Evidence/schema behavior that changes classifier semantics
```

An old Task04AcceptanceManifest may be reused only for explicitly bounded non-code/non-semantic update classes marked `REUSE` in Appendix G.

---

# 126. Foundation gate lifecycle and typed runtime error taxonomy

Foundation gates execute only after architecture acceptance and bounded PRE-TASK authorization.

They do not require Task-04 implementation code.

Every gate emits GateResultManifest.

## 126.1 Runtime/build typed error families

Operational/build errors are distinct from device semantic statuses.

Families:

```text
SnapshotBuildError
SourceEvaluabilityError
EvidenceCompatibilityCondition
RuntimeProfileError
RequestAssemblyError
ClassificationExecutionError
ClassificationPersistenceError
ArtifactDependencyError
```

Minimum typed reasons and handling:

| Typed reason | Family | Retry class | Result behavior |
|---|---|---|---|
| `corrupt_payload` | SnapshotBuildError | non-retryable for same stored row | no snapshot/result |
| `payload_hash_mismatch` | SnapshotBuildError | non-retryable for same stored row | no snapshot/result |
| `schema_validation_failure` | SnapshotBuildError | non-retryable for same stored row | no snapshot/result |
| `unsupported_schema` | EvidenceCompatibilityCondition | safe-no-claim | descriptor retained; no claim; SourceEvaluability unchanged |
| `resource_limited` | SnapshotBuildError | non-retryable for same content/policy | no ClassificationResult |
| `binding_unavailable` | SnapshotBuildError | non-retryable until profile/binding changes | no result/window invalid |
| `binding_cutover_ambiguous` | SourceEvaluability safe condition | safe-no-claim | coverage unknown for interval |
| `runtime_profile_incompatible` | RuntimeProfileError | non-retryable until admitted profile fixed | no activation/request |
| `artifact_dependency_cycle` | ArtifactDependencyError | non-retryable for same graph | no admission/activation |
| `negative_knowledge_age` | RequestAssemblyError | non-retryable for same request inputs | no result |
| `knowledge_bundle_unavailable` | RequestAssemblyError | retryable only if transient load issue | no result |
| `retryable_sqlite_busy` | SnapshotBuildError | retryable | no result |
| `snapshot_timeout` | SnapshotBuildError | retryable/operational | no semantic result |
| `persistence_unavailable` | ClassificationPersistenceError | retryable according to service policy | semantic result not committed |
| `production_profile_not_admitted` | ClassificationPersistenceError | non-retryable until profile admission/active state changes | production result not committed |
| `activation_lineage_unavailable` | RuntimeProfileError | retryable only while successful pointer activation is awaiting immutable activation-record finalization | no production request/result |
| `runtime_profile_invalidated` | ClassificationPersistenceError | non-retryable for the pinned activation | production result not committed |
| `classifier_internal_error` | ClassificationExecutionError | non-retryable until code/input defect corrected unless proven transient | no result |

Operational failures MUST NOT map into:

```text
unknown
insufficient_evidence
not_evaluable
```

unless the condition is explicitly a safe semantic no-claim/evaluability state above.

`unsupported_schema` belongs only to evidence compatibility/adapter claim eligibility. It does NOT change source coverage/completeness and is not a SourceEvaluability error.

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

F-A2, F-A3, F-A4, F-ADMIT and FoundationAdmissionManifest construction.

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

F-A3, F-ADMIT and production recovery procedure.

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
GateProofArtifact(proof_kind=SNAPSHOT_CONCURRENCY)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-ADMIT and Task-04 snapshot implementation.

---

# 130. FOUNDATION F-A4 — Snapshot query/WAL performance and sizing

**INPUT**

```text
PASS F-A5 FINAL EvidenceSchemaRegistryContract

Task-01 v2 candidate

exact snapshot queries/indexes

actual normalized payload materialization behavior

production per-MAC cardinality measurements

controlled high-cardinality workload
```

**PROOF METHOD**

Measure:

```text
EXPLAIN QUERY PLAN / index use
page count
snapshot evidence rows
snapshot health rows
verified payload bytes for all integrity-checked authorized rows
materialized payload bytes for admitted rows
descriptor bytes
binding/health bytes
total semantic input bytes
read-transaction duration
WAL growth during reader
checkpoint behavior
writer latency
retention latency
CPU/memory
```

**PASS**

```text
expected product snapshots fit accepted envelope
Task-01 ingest remains operationally safe
no arbitrary timeout increase used as fix
indexes added only when query-plan evidence justifies them
SnapshotContentPolicy exact deterministic limits frozen, including max_verified_payload_bytes and max_materialized_payload_bytes
SnapshotExecutionPolicy exact operational limits frozen
```

**FAIL**

Unmeasured limits, verified/materialized payload bytes omitted, or long reader materially destabilizes writer/retention without a proven bounded correction.

**RETAINED EVIDENCE**

```text
query plans
benchmark/cardinality report
WAL/checkpoint/writer latency report
selected-policy rationale
```

**CANONICAL OUTPUT ARTIFACTS**

```text
SnapshotContentPolicy
SnapshotExecutionPolicy
GateProofArtifact(proof_kind=SNAPSHOT_PERFORMANCE)
```

**OWNER DECISION**

Owner accepts first production resource envelope.

**WHAT NEXT CONSUMES IT**

F-ADMIT, FoundationRuntimeProfile and snapshot service.

---

# 131. FOUNDATION F-A5 — FINAL EvidenceSchemaRegistryContract / payload integrity

**DEPENDENCY ORDER**

```text
F-C1 tcp_syn/2 final SchemaContract
        \
         \
F-D1 portal_headers/2 admitted SchemaContract
OR CapabilityDisposition(NOT_ADMITTED)
          \
           ↓
F-A5 FINAL EvidenceSchemaRegistryContract
           ↓
F-A4 sizing/performance
```

**INPUT**

```text
existing accepted schema validators:
    dhcp/1
    tcp_syn/1
    tls_client/1
    quic_client/1
    portal_headers/1

PASS F-C1 TcpSynV2SchemaContract

PASS F-D1 PortalHeadersV2SchemaContract
OR CapabilityDisposition(NOT_ADMITTED)
```

**PROOF METHOD**

Execute fixtures for:

```text
known schema valid payload
known schema invalid payload
unknown structurally intact future schema
invalid JSON
duplicate JSON key
canonical-string mismatch
payload SHA mismatch
```

**PASS**

```text
generic integrity/hash failures hard-fail snapshot
known schema validates/materializes
unknown schema descriptor retained
unknown schema not semantically materialized
unknown schema → unsupported_evidence_contract / no claim
FINAL registry lists no unaccepted candidate schema
CapabilityDisposition(NOT_ADMITTED portal_headers/2) proves fallback_source_kind=portal_headers / feature_schema_version=1 exists in FINAL registry
```

**FAIL**

Unknown schema crashes valid snapshot, silently disappears, or is opportunistically parsed; or corrupt payload is tolerated.

**RETAINED EVIDENCE**

```text
schema fixture corpus
payload canonical/hash results
registry payload/digest
```

**CANONICAL OUTPUT ARTIFACT**

```text
EvidenceSchemaRegistryContract
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-A4 sizing, F-E3 K3 rule admission, F-F1 EvidenceAdapterContractSet and F-ADMIT.

---

# 132. FOUNDATION F-B0 — SourceHealthEmitterContract admission

**INPUT**

Current network-sensor and portal source-health implementations, reason codes, heartbeat behavior, spool/delivery behavior and Task-01 delayed-event interaction.

**PROOF METHOD**

Inspect exact implementation identities and execute status/reason/heartbeat/delivery fixtures.

**PASS**

Every Task-01 source-health producer used by the Foundation has an immutable SourceHealthEmitterContract with exact reason-code and failure-domain semantics.

**FAIL**

Reason semantics depend only on producer_id or undocumented software behavior.

**RETAINED EVIDENCE**

Implementation identity, reason-code matrix, heartbeat/spool/delivery test evidence.

**CANONICAL OUTPUT ARTIFACTS**

One `SourceHealthEmitterContract` per admitted emitter semantic version.

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-B1 BindingTimeline and F-B2 SourceHealthPolicy.

---

# 132.1 FOUNDATION F-B1 — Binding timeline / cutover clock / valid-from

**INPUT**

```text
PASS F-B0 SourceHealthEmitterContracts

actual producer/capture topology
candidate EvidenceSourceBindingTimeline
producer/Task-01 clock measurements
controlled A→B cutover fixture
```

**PROOF METHOD**

Measure clock relationship and execute controlled binding/emitter cutover.

**PASS**

```text
exactly one authoritative V1 binding outside cutover quarantine
producer_id mandatory
capture_source_id mandatory
SourceHealthEmitterContract ID/digest mandatory per epoch
no concurrent HA semantics
cutover guard frozen from proof
rows inside guard quarantined
classification_foundation_valid_from_utc frozen
mac_registry absent from timeline
new emitter semantics create new epoch
```

**FAIL**

Hidden historical authority, overlapping undefined binding, unmeasured exact cutover, or health semantics without epoch-owned emitter contract.

**RETAINED EVIDENCE**

Topology, clock measurement, cutover trace, emitter contract refs, timeline payload/digest.

**CANONICAL OUTPUT ARTIFACTS**

```text
EvidenceSourceBindingTimeline
BindingClockPolicy
```

**OWNER DECISION**

Owner accepts `classification_foundation_valid_from_utc`.

**WHAT NEXT CONSUMES IT**

F-B2, F-ADMIT, FoundationRuntimeProfile, snapshot builder.

---

# 133. FOUNDATION F-B2 — Source-health coverage semantics / portal heartbeat

**INPUT**

```text
PASS F-B0 SourceHealthEmitterContracts
PASS F-B1 BindingTimeline/Clock
network sensor behavior
portal producer behavior
Task-01 timestamp/delayed contract
```

**PROOF METHOD**

Controlled:

```text
healthy heartbeat
acquisition failure
transport failure
spool stale-drop/eviction/capacity behavior
recovery/backfill
portal idle period
portal transport failure/recovery
unknown reason code
```

**PASS**

```text
SourceHealthPolicy interprets:
binding epoch emitter contract + status + reason_code

coverage classes exactly R12 conservative V1

NO covered_delayed

transport recovery does not prove completeness

actual backfilled evidence remains usable

unknown reason/emitter mismatch → unknown

portal idle heartbeat independent of visitors

backfill obeys Task-01 delayed-event limit
```

**FAIL**

Generic unavailable semantics, available-after-recovery→complete, visitor-dependent portal liveness, or historical health reinterpretation under a newer emitter contract.

**RETAINED EVIDENCE**

Producer/central timelines, spool-loss fixtures, portal heartbeat trace, reason/coverage matrix.

**CANONICAL OUTPUT ARTIFACT**

```text
SourceHealthPolicy
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-B3 health retention, F-ADMIT, FoundationRuntimeProfile and SourceEvaluability.

---

# 134. FOUNDATION F-B3 — Task-01-native health retention margin

**INPUT**

```text
PASS F-B2 SourceHealthPolicy
current evidence retention
current health retention capability
```

**PROOF METHOD**

Derive exact health_anchor_margin_seconds from SourceHealthPolicy and test predecessor preservation at oldest retained evidence boundary using ordinary time-based Task-01 cleanup.

**PASS**

```text
source_health_retention
>= evidence_retention + margin

Task-01 cleanup does not parse BindingTimeline
required predecessor can still exist for oldest retained eligible evidence
```

Also prove the activation-compatibility rule:

```text
future SourceHealthPolicy required margin
must be <= already preserved history capability
or activation is blocked until sufficient history accumulates
```

**FAIL**

Equal retention without proof, topology-coupled cleanup, or policy activation requiring already deleted predecessor history.

**RETAINED EVIDENCE**

Margin derivation, boundary fixtures, before/after retention inventory.

**CANONICAL OUTPUT ARTIFACT**

```text
Task01HealthRetentionContract
```

**OWNER DECISION**

Owner accepts resulting Task-01 retention configuration when production settings change.

**WHAT NEXT CONSUMES IT**

F-ADMIT, FoundationRuntimeProfile and future SourceHealthPolicy re-admission.

---

# 135. FOUNDATION F-C1 — tcp_syn/2 minimization and exact option schema

**INPUT**

R12 frozen tcp_syn/2 field/option-record contract and admitted p0f reconstruction requirements.

**PROOF METHOD**

Field-by-field privacy/value matrix plus normal/malformed packet fixtures.

**PASS**

```text
protocol-neutral durable fields only
exact frozen top-level fields
exact EOL/NOP/MSS/WS/SACK/Timestamp/unknown variants
tcp_header_length_bytes sufficient
no exact TCP timestamps
timestamp echo numeric values absent
exact IPv4 ID absent
malformed-but-observable preserved
raw option bytes absent
```

**FAIL**

Speculative correlator, underdefined option record, duplicated representation, or missing fact required for exact supported p0f behavior.

**RETAINED EVIDENCE**

Field matrix, privacy review, schema fixture report.

**CANONICAL OUTPUT ARTIFACT**

```text
TcpSynV2SchemaContract
```

**OWNER DECISION**

Owner approval required for any stronger correlating field than frozen baseline.

**WHAT NEXT CONSUMES IT**

F-C2 and F-A5 FINAL EvidenceSchemaRegistryContract.

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

F-E2, F-F1 and ClassifierArtifactManifest construction.

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

F-ADMIT / initial OriginRuntimeAdmission / FoundationAdmissionManifest.

---

# 138. FOUNDATION F-D1 — Portal Client-Hints value/privacy/lifecycle

**INPUT**

Controlled supported clients + candidate bounded Accept-CH flow.

**PROOF METHOD**

Real CaptivPortal flow with sanitized network/browser/storage inspection.

**PASS — ADMITTED PATH**

For every admitted field:

```text
actual client emits it
normalization deterministic
material classification value
raw value non-durable
Critical-CH absent
no forced retry
bounded Accept-CH lifecycle
teardown proven where supported
Authorization unchanged
```

Outputs:

```text
PortalHeadersV2SchemaContract
CapabilityDisposition(
    capability_id=portal_headers/2,
    status=ADMITTED
)
```

**PASS — SAFE NOT_ADMITTED PATH**

If value/privacy/lifecycle proof does not justify V2 but existing portal_headers/1 remains safe:

```text
CapabilityDisposition(
    capability_id=portal_headers/2,
    status=NOT_ADMITTED,
    fallback=portal_headers/1 supported contract
)
```

This safe optional rejection is a gate PASS, not Foundation failure.

**FAIL**

Raw durability, forced retry/Authorization dependency, unsafe partial behavior, or no valid fallback disposition.

**RETAINED EVIDENCE**

Sanitized flows, normalized observations, storage/log audit, teardown proof.

**CANONICAL OUTPUT ARTIFACTS**

`CapabilityDisposition` plus `PortalHeadersV2SchemaContract` only when ADMITTED.

**OWNER DECISION**

Owner authorizes controlled experiment.

**WHAT NEXT CONSUMES IT**

F-A5 FINAL EvidenceSchemaRegistryContract and F-F1 EvidenceAdapterContractSet.

---

# 139. FOUNDATION F-E1 — K1 DHCP source admission / ambiguity proof

**INPUT**

Owner-authorized Fingerbank static candidate OR another concrete K1 candidate.

**PROOF METHOD**

Governance/provenance inspection, canonical import, and deterministic matcher fixtures covering:

```text
row-order permutations
multiple compatible candidates
no-match
per-dimension agreement/disagreement
upstream provenance purity
non-DHCP attributes present externally but hidden from K1
```

**PASS**

```text
all deterministic compatible K1 records enumerated
all linked candidate taxonomy rows preserved
CandidateSet complete and row-order independent
no first/best/popular/scoring shortcut
per-dimension projection exact
A=Android/smartphone + B=Android/tablet
→ platform android resolved
→ device_class ambiguous
no-match = explicit empty CandidateSet
runtime input DHCP-only
fusion-eligible mappings provenance-pure DHCP-only
```

**FAIL**

Candidate source fails legal/provenance/determinism/ambiguity requirements.

On FAIL:

```text
DO NOT weaken K1 contract
select another concrete K1 source
Foundation Admission remains blocked
```

No placeholder/manual guesses.

**RETAINED EVIDENCE**

Source SHA, governance/provenance review, canonical import, CandidateSet fixture matrix.

**CANONICAL OUTPUT ARTIFACTS**

```text
KnowledgeProvenanceManifest(K1)
CanonicalKnowledgeRecordSet(knowledge_slot=K1)
```

plus SourceGovernanceRecord/KnowledgeFreshnessPolicy for external sources.

**OWNER DECISION**

Owner accepts external source governance where applicable.

**WHAT NEXT CONSUMES IT**

F-E5, F-E7 KnowledgeBundle and F-F1 EvidenceAdapterContractSet.

---

# 140. FOUNDATION F-E2 — K2B production TCP source admission

**INPUT**

Concrete K2B TCP source candidate + PASS K2A conformance package.

**PROOF METHOD**

Governance/provenance inspection, canonical import, K2A representation compatibility and taxonomy/claim-strength review.

**PASS**

At least one real production TCP corpus exists separately from K2A oracle and its admission explicitly freezes:

```text
source_character = current | legacy
freshness policy
maximum claim_strength per dimension
taxonomy limitations
known age/scope caveats
```

Legacy exact match does NOT automatically become strong.

**FAIL**

Oracle-only source, unknown legal status, incompatible representation, missing strength ceiling, or unusable taxonomy.

On FAIL:

```text
do not weaken requirements
select another concrete K2B source
Foundation Admission remains blocked
```

**RETAINED EVIDENCE**

Source/governance/provenance/import/K2A compatibility/strength review.

**CANONICAL OUTPUT ARTIFACTS**

```text
KnowledgeProvenanceManifest(K2B)
CanonicalKnowledgeRecordSet(knowledge_slot=K2B)
```

plus external SourceGovernanceRecord/KnowledgeFreshnessPolicy where applicable.

**OWNER DECISION**

Owner accepts source governance/legacy policy.

**WHAT NEXT CONSUMES IT**

F-E5 and F-E7 KnowledgeBundle.

---

# 141. FOUNDATION F-E3 — K3 internal portal rule admission

**INPUT**

```text
normalized portal schema(s) accepted by F-A5
ClassificationTaxonomy candidate
K3PortalRuleSet candidate
```

**PROOF METHOD**

Execute rule test vectors covering normalized provenance fields, mobile boolean, browser runtime/context, model family and conflicting portal observations.

**PASS**

```text
normalized input only
no raw header/UA/CH parsing
mobile true does not imply smartphone
runtime/context does not imply device_class
model resolution only through admitted canonical model rule/alias
rule IDs/version exact
schema compatibility exact
taxonomy mapping exact
claim_derivation and claim_strength explicit
test vectors deterministic
```

**FAIL**

Raw parsing, implicit device-class shortcut, undefined strength/provenance or placeholder rule set.

On FAIL:

```text
do not weaken K3 requirements
create/review another concrete internal rule set
Foundation Admission remains blocked
```

**RETAINED EVIDENCE**

Rule-set artifact, vectors/results, review/decision audit records.

**CANONICAL OUTPUT ARTIFACTS**

```text
K3PortalRuleSet
KnowledgeProvenanceManifest(provenance_kind=internal)
```

**OWNER DECISION**

Owner/TechLead accept K3 semantic rules.

**WHAT NEXT CONSUMES IT**

F-E7 KnowledgeBundle and F-F1 EvidenceAdapterContractSet.

---

# 142. FOUNDATION F-E4 — K4 IEEE source admission

**INPUT**

Concrete MA-L/MA-M/MA-S source candidate.

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

On FAIL:

```text
do not weaken K4 requirements
select another concrete K4 source
Foundation Admission remains blocked
```

**RETAINED EVIDENCE**

Source SHA, governance/provenance, import report, prefix/mapping fixtures.

**CANONICAL OUTPUT ARTIFACTS**

```text
KnowledgeProvenanceManifest(K4)
CanonicalKnowledgeRecordSet(knowledge_slot=K4)
```

plus external SourceGovernanceRecord/KnowledgeFreshnessPolicy.

**OWNER DECISION**

Owner accepts external governance.

**WHAT NEXT CONSUMES IT**

F-E5 and F-E7 KnowledgeBundle.

---

# 143. FOUNDATION F-E5 — External freshness/governance completion

**INPUT**

Every mandatory external K1/K2B/K4 source plus trusted central gate clock.

**PROOF METHOD**

For each source evaluate license/provenance/update cadence/refresh capability/failure tolerance/source_character/claim caveats and justify exact V1 integer-age thresholds.

The gate tool captures the source-policy/governance proof time:

```text
foundation_knowledge_evaluation_at_utc
```

itself. It is not user-supplied/backdated.

For every changing external source the candidate KnowledgeFreshnessPolicy MUST freeze:

```text
source_family_id
fresh_max_age_ms
stale_max_age_ms
fresh/stale/expired state rules
claim eligibility
claim-strength ceilings
required explanation codes
```

with:

```text
0 <= fresh_max_age_ms <= stale_max_age_ms
```

and exact §81 machine-deterministic age evaluation.

**PASS**

Each external source has accepted:

```text
SourceGovernanceRecord
KnowledgeFreshnessPolicy
KnowledgeProvenanceManifest
```

with no unresolved material legal restriction, no provenance↔freshness ArtifactContent dependency cycle, non-negative source age, and source state usable under its exact policy at the captured `foundation_knowledge_evaluation_at_utc`.

Threshold values are justified by retained source-specific evidence; no prose runtime condition remains.

**FAIL**

Unknown material legal status, arbitrary freshness threshold, free-form runtime freshness condition, negative source age, provenance↔freshness cycle, or time-dependent PASS without recorded trusted evaluation time.

**RETAINED EVIDENCE**

License/provenance materials/digests, freshness research, threshold rationale and exact trusted evaluation time.

**CANONICAL OUTPUT ARTIFACTS**

Accepted governance/freshness/provenance artifacts.

**OWNER DECISION**

REQUIRED for external source admission.

**WHAT NEXT CONSUMES IT**

F-E7 KnowledgeBundle and F-ADMIT final freshness re-evaluation.

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

F-E3 K3 rule admission, F-E7 KnowledgeBundle and F-F2 ClassificationPolicy.

---

# 145. FOUNDATION F-E7 — KnowledgeBundle deterministic build

**INPUT**

```text
accepted ClassificationTaxonomy / AliasMapping
CanonicalKnowledgeRecordSet(K1)
CanonicalKnowledgeRecordSet(K2B)
K3PortalRuleSet
CanonicalKnowledgeRecordSet(K4)
KnowledgeProvenanceManifests
external SourceGovernanceRecords
external KnowledgeFreshnessPolicies
foundation_knowledge_evaluation_at_utc from F-E5
```

**PROOF METHOD**

Build twice from identical semantic inputs and validate mandatory runtime usability at the trusted Foundation evaluation time.

**PASS**

```text
same semantic inputs → same KnowledgeBundle digest
mandatory K1/K2B/K3/K4 concrete/usable
external mandatory sources not expired at exact F-E5 trusted proof time
no placeholder slot
runtime vendor schema absent
accepted KnowledgeBundle immutable
```

Bundle activation itself is no longer an independent pointer; activation occurs through Foundation/ClassificationRuntimeProfile admission.

**FAIL**

Missing mandatory slot, undefined digest, vendor runtime dependency or expired source counted as sufficient.

**RETAINED EVIDENCE**

Build input manifest, two build digests, validation report, trusted evaluation time.

**CANONICAL OUTPUT ARTIFACT**

```text
KnowledgeBundle
```

**OWNER DECISION**

Owner accepts initial Foundation KnowledgeBundle.

**WHAT NEXT CONSUMES IT**

F-ADMIT final freshness re-evaluation/profile admission and Task-04.

---

# 146. FOUNDATION F-F1 — EvidenceAdapterContractSet freeze

**INPUT**

```text
PASS F-A5 FINAL EvidenceSchemaRegistryContract
CapabilityDisposition(portal_headers/2)
all classification-eligible schema families
K2A/K1/K3/JA4 safety contracts
```

**PROOF METHOD**

Compatibility matrix covering:

```text
dhcp/1
tcp_syn/1
tcp_syn/2
tls_client/1
quic_client/1
portal_headers/1
portal_headers/2 if ADMITTED
valid/partial/degraded
supported/unsupported subtype
extractor/rule version compatibility
```

**PASS**

```text
every schema has explicit adapter or explicit non-fusion reason
tcp_syn/1 non-fusion exact
TLS/QUIC no JA4 claim without admitted knowledge
unknown future schema safe unsupported no-claim
partial claim capped supporting
degraded no claim
semantic dedup projection frozen
registry/adapter compatibility exact
```

**FAIL**

Latest-schema-wins, opportunistic parse, implicit quality authority or adapter contract claims schema not admitted by final registry.

**RETAINED EVIDENCE**

Compatibility matrix, fixtures, contract payload/digest.

**CANONICAL OUTPUT ARTIFACT**

```text
EvidenceAdapterContractSet
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-F2, F-ADMIT, ClassificationRuntimeProfile compatibility and Task-04.

---

# 147. FOUNDATION F-F2 — ClassificationPolicy semantic freeze

**INPUT**

```text
ClassificationTaxonomy

AliasMapping

EvidenceAdapterContractSet

R12 claim/fusion/support/status contracts

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

F-ADMIT and Task-04 pure core.

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

F-ADMIT and Task-04 persistence.

---

# 149. FOUNDATION F-F4 — ProductValidationPolicy

**INPUT**

R12 validation safety/utility requirements and available controlled devices.

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

F-ADMIT and T-09.

---

# 150. FOUNDATION F-F5 — Runtime-profile atomicity / pinning mechanism proof

**INPUT**

Synthetic/accepted-compatible fixture FoundationRuntimeProfiles and pre-acceptance candidate ClassificationRuntimeProfiles constructed from immutable fixture artifacts without embedding admission/acceptance lineage in profile semantic content; control-plane transaction store capable of pointer + activation + validity-head mutation.

**PROOF METHOD**

Exercise crash-atomic active-profile activation, rollback activation and CAS-protected validity transitions while in-flight snapshot/request execution remains pinned.

Crash points MUST include:

```text
before activation transaction
inside activation transaction before COMMIT
after durable COMMIT
during rollback activation
```

Validity concurrency MUST include two attempted successors from the same expected head.

**PASS**

```text
only complete runtime profiles are selected
profile ArtifactContent immutable
active pointer visible IFF activation + initial ACTIVE validity head are durably retrievable
crash before/during COMMIT exposes old complete state only
crash after durable COMMIT exposes new complete state only
no normal activation_lineage_unavailable window
old in-flight operation remains entirely on old profile
new operation sees entirely new profile
rollback points to prior admitted profile via a NEW activation record
no independent Bundle/Policy/Classifier/Foundation artifact pointer reads
ClassificationRuntimeProfile can exist/test before Task04AcceptanceManifest
FoundationRuntimeProfile can exist independently of FoundationAdmissionManifest semantic identity
exactly one canonical validity head exists per activation
validity CAS permits at most one canonical successor per expected head
restart/recovery reconstructs pointer→activation→validity-head deterministically
```

**FAIL**

Torn artifact set, pointer without activation/initial validity head, mutable in-place policy, in-flight pointer reread, timestamp/UUID validity ordering, dual canonical validity successor, or rollback activation without complete audit lineage.

**RETAINED EVIDENCE**

Profile-switch/pinning trace, transaction crash-point trace, rollback trace, CAS race trace, restart/recovery trace and compatibility test fixtures.

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=RUNTIME_PROFILE_ATOMICITY)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-ADMIT and post-T-ACCEPT production activation action.

---

# 150.1 FOUNDATION F-F6 — Immutable ArtifactContent dependency graph acyclicity

**INPUT**

```text
all mandatory Foundation ArtifactContent schema contracts
all candidate Foundation ArtifactContent dependencies
RuntimeProfileAdmissionManifest dependency rules
GateResultManifest output-reference rules
Task-04 artifact dependency schema templates
```

**PROOF METHOD**

Build the directed semantic dependency graph where:

```text
A → B
means ArtifactContent A semantic digest includes ArtifactContent B ID/digest
```

Run cycle detection and produce one deterministic topological ordering for every concrete Foundation candidate graph and the frozen Task-04 artifact graph templates.

Explicitly exercise regressions for:

```text
GateResultManifest ↔ output artifact cycle
RuntimeProfile ↔ acceptance/admission lineage cycle
CapabilityDisposition ↔ producing GateResult cycle
KnowledgeFreshnessPolicy ↔ KnowledgeProvenanceManifest cycle
mutual ArtifactContent dependency cycle
```

**PASS**

```text
topological ordering exists
no output artifact references its producing GateResultManifest
RuntimeProfileAdmissionManifest references prerequisite GateResults only
CapabilityDisposition has no producing-gate back-reference
KnowledgeFreshnessPolicy depends only on stable source_family_id, not KnowledgeProvenanceManifest identity
runtime profiles contain execution-set semantics, not acceptance-lineage back-references
```

**FAIL**

Any semantic ArtifactContent cycle or un-topologizable build graph.

**RETAINED EVIDENCE**

```text
dependency graph
cycle-test fixtures
topological ordering
```

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=ARTIFACT_GRAPH_ACYCLICITY)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

F-ADMIT.

---

# 151. FOUNDATION F-ADMIT — Foundation Admission + initial FoundationRuntimeProfile

**INPUT**

All mandatory Foundation GateResultManifests/output artifacts, PASS F-F5 crash-atomic profile mechanism proof, PASS F-F6 acyclicity proof, PASS F-C3 TTLCapturePlacementProof, exact foundation repository candidate, and F-E5 external-source freshness/governance artifacts.

**PROOF METHOD**

TechLead11 full Foundation review against accepted R12 ArchitectureContractReference and dependency graph.

F-ADMIT constructs/adopts artifacts in this EXACT acyclic order:

```text
1. capture trusted central
   foundation_admission_evaluation_at_utc

2. re-evaluate every mandatory external knowledge source
   at THAT exact time using the admitted KnowledgeFreshnessPolicy:
       age_ms exact
       no negative age
       fresh/stale/expired exact
       mandatory runtime knowledge must remain usable/claim-eligible
       under its admitted state rule

3. construct OriginRuntimeAdmission:
       tcp_state = ENABLED
       tcp_reason_code = TTL_PROOF_VALID
       TTLCapturePlacementProof ID/digest = PASS F-C3 proof

4. construct FoundationAdmissionManifest
   referencing the already-existing OriginRuntimeAdmission,
   prerequisite GateResults only,
   PASS F-C3 proof,
   and exact foundation_admission_evaluation_at_utc

5. construct FoundationRuntimeProfile
   containing the exact compatible foundation execution set
   and NO FoundationAdmissionManifest semantic back-reference

6. construct RuntimeProfileAdmissionManifest(
       profile_kind=foundation,
       update_class=INITIAL_FOUNDATION
   )
   referencing the already-existing FoundationRuntimeProfile,
   FoundationAdmissionManifest lineage root,
   prerequisite GateResults only

7. create required Owner DecisionRecord authorizing Foundation admission/activation

8. precompute Foundation RuntimeProfileActivationRecord + initial ACTIVE RuntimeProfileValidityRecord

9. perform ONE crash-atomic §11.5 control-plane transaction:
       insert ActivationRecord
       insert initial ACTIVE ValidityRecord
       initialize canonical validity head
       atomically switch FoundationRuntimeProfile pointer
       COMMIT

10. create final F-ADMIT GateResultManifest
    referencing all completed output artifacts
```

No object is constructed before a semantic dependency it references.

Initial V1 admission rule is unambiguous:

```text
F-C3 = MANDATORY PASS
TTLCapturePlacementProof = REQUIRED
OriginRuntimeAdmission.tcp_state = ENABLED
OriginRuntimeAdmission.tcp_reason_code = TTL_PROOF_VALID
```

Initial F-ADMIT cannot substitute `TCP DISABLED` for a failed/missing physical TTL proof.

TCP-disabled OriginRuntimeAdmission remains available only for post-admission safety transitions already frozen by §121.2/Appendix G.

**PASS**

```text
all mandatory prerequisite gates PASS
F-C3 PASS
mandatory K1/K2B/K3/K4 concrete/usable
mandatory external knowledge usable at foundation_admission_evaluation_at_utc
no negative external source age
classification_foundation_valid_from frozen
final registry/adapters compatible
health emitter/policy/retention compatible
profile compatibility PASS
OriginRuntimeAdmission tcp=ENABLED / TTL_PROOF_VALID
all required artifacts immutable/accepted
artifact dependency graph acyclic
crash-atomic Foundation activation PASS
active pointer resolves exact ActivationRecord + initial canonical ACTIVE validity head
no unresolved mandatory policy
no lifecycle contradiction
```

**FAIL**

Any missing/failed artifact, F-C3 failure, invalid/missing TTL proof, mandatory external source unusable at final admission time, negative source age, incompatible profile, unresolved contract, artifact cycle, non-atomic activation or silent fallback.

**RETAINED EVIDENCE**

Complete foundation gate/artifact inventory, exact `foundation_admission_evaluation_at_utc`, final freshness re-evaluation, F-C3 proof, activation transaction trace, exact ActivationRecord/ValidityRecord identities, final pointer/head state and Owner DecisionRecord.

**CANONICAL OUTPUT ARTIFACTS**

```text
FoundationAdmissionManifest
OriginRuntimeAdmission
FoundationRuntimeProfile
RuntimeProfileAdmissionManifest(profile_kind=foundation, update_class=INITIAL_FOUNDATION)
RuntimeProfileActivationRecord(profile_kind=foundation)
RuntimeProfileValidityRecord(state=ACTIVE)
```

FoundationRuntimeProfile is activated as part of F-ADMIT through the crash-atomic primitive.

**OWNER DECISION**

EXPLICIT OWNER ACCEPT REQUIRED.

**WHAT NEXT CONSUMES IT**

Standalone/research Snapshot Service may use the active FoundationRuntimeProfile.

Task-04 candidate ClassificationRuntimeProfile construction uses the admitted FoundationRuntimeProfile together with its exact foundation RuntimeProfileAdmissionManifest lineage.

After PASS/activation:

```text
TechLead11 may decompose Task-04
```

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

Implemented Snapshot Service + accepted FoundationRuntimeProfile / final EvidenceSchemaRegistryContract.

**PROOF METHOD**

Execute known-valid, known-invalid, unknown-schema, duplicate-key, canonical mismatch and hash mismatch rows inside one SQLite snapshot transaction.

**PASS**

```text
known valid schema materializes normalized payload
known invalid schema hard-fails snapshot
corrupt JSON/hash/canonical mismatch hard-fails snapshot
unknown structurally intact schema descriptor remains in EvidenceSnapshotContent
unknown schema NOT semantically materialized
unknown schema → unsupported_evidence_contract/no claim
transient normalized payload not persisted in Classification DB
SnapshotContentPolicy counts verified payload bytes for ALL integrity-checked authorized rows, including unknown schemas, and separately counts materialized payload bytes
```

**FAIL**

Unknown schema crashes otherwise valid snapshot, disappears, or is opportunistically parsed; or corrupt payload is tolerated.

**RETAINED EVIDENCE**

Fixture/input/output digests and execution trace.

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=SNAPSHOT_MATERIALIZATION_EXECUTION)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

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
GateProofArtifact(proof_kind=SOURCE_EVALUABILITY_EXECUTION)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

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
GateProofArtifact(proof_kind=ORIGIN_ASSESSMENT_EXECUTION)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

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
OriginRuntimeAdmission tcp=DISABLED with audit-visible tcp_syn rows
```

**PASS**

Exact frozen fusion outcomes.

When OriginRuntimeAdmission.tcp_state=DISABLED: TCP produces `no_claim / origin_runtime_disabled`; no p0f/K2B claim enters fusion.

**FAIL**

Hidden priority, blanket origin-conflict rule, HIGH despite incompatible supporting claim, or undefined matrix cell.

**RETAINED EVIDENCE**

Vector/result table with policy digest.

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=FUSION_EXECUTION)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

---

# 158. TASK-04 T-05 — RequestAssembly / runtime-profile pinning / pure-core determinism

**INPUT**

Implemented RequestAssembly/pure core + PASS T-06A exact candidate ClassificationRuntimeProfile ID/digest.

**PROOF METHOD**

Run the normal RequestAssembly implementation against the exact candidate profile in a non-production acceptance harness, with DB/network/filesystem access blocked inside pure core, while performing a concurrent atomic ClassificationRuntimeProfile pointer switch in the harness.

**PASS**

```text
production LIVE ordering pins ClassificationRuntimeProfile first
candidate execution uses the exact T-06A profile digest
FoundationRuntimeProfile is loaded only from that candidate profile
no independent active Foundation pointer read
old in-flight request remains entirely old profile
new request sees entirely new profile
no mixed Bundle/Policy/Classifier/Foundation set
semantic ClassificationRequestManifest contains no runtime-profile/governance/operational identity
same pure semantic request digest → same result digest
system wall-clock change alone → no effect
trusted service-owned knowledge_evaluation_at used
negative knowledge age fails request
fresh/stale/expired behavior follows exact KnowledgeFreshnessPolicy
expired individual source suppresses its claims but does not crash classifier
```

**FAIL**

Independent active-pointer reads, torn set, semantic request digest changed only by operational/profile lineage, caller-backdated time, hidden I/O/clock/config dependency or knowledge-source expiry crash.

**RETAINED EVIDENCE**

Candidate profile digest, semantic request/result digests, pointer-switch trace and blocked-I/O proof.

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=REQUEST_ASSEMBLY_DETERMINISM)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-ACCEPT and production RequestAssembly.

---

# 159. TASK-04 T-06 — Exact ClassifierArtifactManifest

**INPUT**

Exact Task-04 implementation candidate.

**PROOF METHOD**

Generate immutable manifest from exact build/repository state.

**PASS**

Manifest identifies exact:

```text
commit SHA
tree SHA
engine version
ArtifactCanonicalJsonV1/Ordering implementation identity
EvidenceCanonicalJsonV1 compatibility
all adapter implementation identities for every admitted/explicitly non-fusion schema
K2A matcher implementation
snapshot/result/pure-core contract versions
build/package digest where required
```

Classifier implementation version cannot change underneath an active ClassificationRuntimeProfile.

**FAIL**

Vague current/v1 identity or missing adapter semantic implementation identity.

**RETAINED EVIDENCE**

Build/repository identity evidence.

**CANONICAL OUTPUT ARTIFACT**

```text
ClassifierArtifactManifest
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-06A and T-ACCEPT.

---

# 159.1 TASK-04 T-06A — Candidate ClassificationRuntimeProfile assembly / compatibility

**INPUT**

```text
PASS T-06 ClassifierArtifactManifest
admitted FoundationRuntimeProfile
accepted KnowledgeBundle
accepted ClassificationPolicy
accepted EvidenceAdapterContractSet
```

**PROOF METHOD**

Construct the immutable pre-acceptance candidate ClassificationRuntimeProfile with NO Task04AcceptanceManifest semantic dependency and execute all §11.3 compatibility checks plus concrete artifact dependency-cycle validation.

**PASS**

```text
candidate ClassificationRuntimeProfile exists before T-05/T-09
profile semantic payload contains only execution-set content
profile compatibility PASS
artifact dependency graph acyclic
candidate profile digest frozen for subsequent T-05/T-09/T-ACCEPT
```

**FAIL**

Any profile mismatch, acceptance-lineage back-reference, dependency cycle or inability to produce a stable candidate digest before product validation.

**RETAINED EVIDENCE**

Profile payload/digest, compatibility report and concrete topological dependency ordering.

**CANONICAL OUTPUT ARTIFACTS**

```text
ClassificationRuntimeProfile
GateProofArtifact(proof_kind=CLASSIFICATION_PROFILE_COMPATIBILITY)
```

**OWNER DECISION**

None. This is a candidate profile, not production activation.

**WHAT NEXT CONSUMES IT**

T-05, T-07, T-08, T-09 and T-ACCEPT.

---

# 160. TASK-04 T-07 — Classification persistence / audit replay / GC

**INPUT**

```text
implemented persistence
accepted ClassificationRetentionPolicy
exact PASS T-06A candidate ClassificationRuntimeProfile P ID/digest
```

**PROOF METHOD**

Use an isolated acceptance Classification SQLite.

Persist controlled classifications produced with the exact candidate profile `P` using the §118 persistence CORE, with NO fake/null future:

```text
Task04AcceptanceManifest
Classification RuntimeProfileAdmissionManifest
Foundation RuntimeProfileAdmissionManifest
```

Acceptance-only rows do not represent production admission.

Then delete the Task-01 source fixture for Level-B test, replay, expire a test classification and run reference-aware GC.

Separately verify the production persistence guard rejects production commit when the pinned ClassificationRuntimeProfile is not currently admitted for production use.

**PASS**

```text
exact T-06A candidate profile P persisted in acceptance DB via same core schema
no future acceptance/admission placeholders required
SnapshotRecord retrievable
EvidenceSnapshotContent retrievable
SourceEvaluability retrievable
OriginAssessments retrievable
request/result/policies/bundle/classifier retrievable
Level-B result replay exact
referenced artifact cannot GC
unreferenced artifact becomes eligible only after policy permits
production commit requires currently admitted ClassificationRuntimeProfile
no classification-row mutation required after later T-ACCEPT
```

**FAIL**

Dangling SnapshotRecord ID, digest-without-content, retention mismatch, fake future acceptance IDs, inability to persist pre-acceptance candidate P in isolated acceptance storage, or production commit allowed for an unadmitted profile.

**RETAINED EVIDENCE**

Candidate profile P digest, isolated acceptance DB inventory, replay report, GC report and production-admission guard proof.

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=CLASSIFICATION_AUDIT_PERSISTENCE)
```

**OWNER DECISION**

Owner verifies retention implementation.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

# 161. TASK-04 T-08 — Offline / failure isolation / no Cloud

**INPUT**

```text
exact Task-04 implementation candidate
+
exact PASS T-06A candidate ClassificationRuntimeProfile P ID/digest
```

The candidate is NOT accepted yet.

**PROOF METHOD**

Run against exact candidate profile `P`, block all external network and inject:

```text
classification DB failure

KnowledgeBundle load failure

snapshot execution timeout

SnapshotContentPolicy exceed

classifier exception

expired individual knowledge source
OriginRuntimeAdmission with TCP disabled while tcp_syn evidence exists
```

Also verify no production-client request path to Fingerbank Cloud.

**PASS**

```text
exact candidate profile P used
normal classification requires no Internet
Fingerbank Cloud absent from V1 production path
no partial classification
operational timeout retryable/no semantic result
deterministic size exceed produces no result
classification failure does not affect Task-01/Auth/CAPPORT
expired source only suppresses its claims
TCP disabled state produces no TCP/p0f/K2B claim while other safe origins continue
```

**FAIL**

Remote hard dependency, candidate-profile mismatch, client data Cloud submission, partial result or Authorization/ingest impact.

**RETAINED EVIDENCE**

Candidate profile P digest and fault/network matrix.

**CANONICAL OUTPUT ARTIFACT**

```text
GateProofArtifact(proof_kind=OFFLINE_FAILURE_ISOLATION)
```

**OWNER DECISION**

None.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

# 162. TASK-04 T-09 — Controlled product safety / utility / anti-learning

**INPUT**

Exact PASS T-06A candidate ClassificationRuntimeProfile ID/digest + ProductValidationPolicy + controlled Owner Android smartphone + Owner Windows laptop.

**PROOF METHOD**

For each device:

```text
1. create/register ControlledValidationGroundTruthRecord
   BEFORE result visibility

2. execute the normal product RequestAssembly/classification path against the exact T-06A candidate ClassificationRuntimeProfile through the non-production acceptance harness

3. persist ClassificationRequestManifest + ClassificationResult

4. create ProductValidationComparisonRecord

5. compare every ground-truth dimension
```

**PASS — SAFETY**

```text
NO incorrect resolved known-ground-truth dimension
NO false recognized_out_of_scope for known in-scope platform/device_class
```

**PASS — MINIMUM UTILITY**

```text
Android platform = android, resolved, support >= medium
Windows laptop platform = windows, resolved, support >= medium
at least one device has correct device_class, resolved, support >= medium
```

**FAIL**

Any wrong resolved known dimension, false out-of-scope, result-driven ground-truth change, or minimum utility failure.

`always unknown` FAILS.

**RETAINED EVIDENCE**

Privacy-safe validation report plus GroundTruth/Request/Result/Comparison artifact IDs/digests and exact tested candidate ClassificationRuntimeProfile ID/digest.

**CANONICAL OUTPUT ARTIFACTS**

```text
ControlledValidationGroundTruthRecord(s)
ProductValidationComparisonRecord(s)
GateProofArtifact(proof_kind=TASK04_PRODUCT_VALIDATION)
```

**OWNER DECISION**

Owner validates ground truth and acceptance comparison.

**WHAT NEXT CONSUMES IT**

T-ACCEPT.

---

# 163. TASK-04 T-ACCEPT — Implementation acceptance / production eligibility of the exact tested ClassificationRuntimeProfile

**INPUT**

PASS all mandatory applicable Task-04 gates including T-06A, T-05, T-07, T-08 and T-09; exact implementation candidate; exact T-06A candidate ClassificationRuntimeProfile `P` ID/digest; accepted FoundationAdmissionManifest lineage; exact already-admitted foundation RuntimeProfileAdmissionManifest for `P.FoundationRuntimeProfile`; foundation/classification artifacts.

**PROOF METHOD**

TechLead11 full Task-04 acceptance review.

For INITIAL classification acceptance or any update class requiring Task-04 semantic reacceptance, the gate performs acyclic admission in this order:

```text
1. verify the ClassificationRuntimeProfile digest used by all applicable
   pre-acceptance gates equals exact T-06A candidate digest P

2. verify P has NOT been rebuilt or semantically changed after T-09

3. construct NEW Task04AcceptanceManifest
   referencing exact tested candidate P
   and prerequisite T-gate results only

4. re-run concrete runtime-profile compatibility and ArtifactContent graph acyclicity

5. construct RuntimeProfileAdmissionManifest with the applicable closed update_class
   linking:
       exact tested candidate P
       FoundationAdmissionManifest lineage root
       exact already-admitted foundation RuntimeProfileAdmissionManifest
       new Task04AcceptanceManifest
       prerequisite GateResults only

6. create required Owner acceptance DecisionRecord

7. create final T-ACCEPT GateResultManifest
   referencing Task04AcceptanceManifest and RuntimeProfileAdmissionManifest outputs
```

T-ACCEPT MUST NOT change the production ClassificationRuntimeProfile pointer and produces NO RuntimeProfileActivationRecord/RuntimeProfileValidityRecord.

No semantic ClassificationRuntimeProfile rebuild occurs after product validation.

A previously accepted Task04AcceptanceManifest may be reused only for update classes explicitly marked `REUSE` in Appendix G; those bounded profile admissions do not fabricate a new T-ACCEPT semantic lineage.

**PASS**

```text
all mandatory applicable Task-04 gates PASS
exact tested profile digest preserved
profile compatibility PASS
artifact dependency graph acyclic
new Task04AcceptanceManifest created whenever semantic reacceptance is required
exact foundation RuntimeProfileAdmissionManifest lineage pinned
exact classifier version pinned
all audit/profile lineage retrievable
candidate P is ACCEPTED/ADMITTED for production eligibility
production pointer remains unchanged
```

**FAIL**

Any semantic/audit/safety/utility defect, candidate-profile digest mismatch, missing required new Task04AcceptanceManifest, unauthorized old-manifest reuse, missing/mismatched foundation RuntimeProfileAdmissionManifest, profile incompatibility, artifact cycle or hidden fallback.

**RETAINED EVIDENCE**

Acceptance report, exact commit/tree/build identity, exact tested profile digest, all prerequisite T GateResultManifests, compatibility/acyclicity trace and Owner acceptance DecisionRecord.

**CANONICAL OUTPUT ARTIFACTS**

For a semantic reacceptance path:

```text
Task04AcceptanceManifest
RuntimeProfileAdmissionManifest(profile_kind=classification)
```

The ClassificationRuntimeProfile is a prerequisite tested artifact, not a newly rebuilt T-ACCEPT output.

**OWNER DECISION**

Owner final Task-04 acceptance required.

Production deployment/activation remains a separate explicit Owner-authorized project action after acceptance.

**WHAT NEXT CONSUMES IT**

Post-T-ACCEPT production activation action or later bounded runtime-profile admission/update path.

---

# 163.1 POST-T-ACCEPT PRODUCTION ACTIVATION ACTION — explicit Owner-authorized deployment action

This action is NOT T-ACCEPT and is NOT an additional semantic acceptance gate.

**PRECONDITIONS**

```text
exact ClassificationRuntimeProfile P already accepted/admitted
exact classification RuntimeProfileAdmissionManifest exists for P
exact required Task04AcceptanceManifest lineage exists
exact foundation RuntimeProfileAdmissionManifest referenced by classification RPM remains valid
current safety/compatibility recheck = PASS
explicit Owner production-activation DecisionRecord exists
```

**ACTION**

No rebuild of P occurs.

Precompute:

```text
RuntimeProfileActivationRecord(profile_kind=classification,
                               runtime_profile=P,
                               runtime_profile_admission_manifest=accepted RPM)

initial RuntimeProfileValidityRecord(state=ACTIVE,
                                     reason=ACTIVATED or ROLLBACK_REACTIVATED)
```

Then execute ONE crash-atomic §11.5 control-plane transaction that inserts the activation record, inserts initial ACTIVE validity record, initializes the canonical validity head, safely deactivates the previous activation when applicable, and switches the production ClassificationRuntimeProfile pointer.

**SUCCESS OUTPUTS**

```text
RuntimeProfileActivationRecord
RuntimeProfileValidityRecord(state=ACTIVE)
updated production active-pointer tuple / canonical validity-head state
Owner deployment DecisionRecord linkage
```

A failed pointer transaction produces no ACTIVE activation record and leaves the prior complete production state visible.

No new Task04AcceptanceManifest is created merely because deployment occurs later than acceptance.

---

# 164. Permanent no-silent-fallback / stop conditions

Permanent prohibitions:

```text
no watermark
→ wall-clock approximation FORBIDDEN

no authoritative binding
→ infer producer from arrived rows FORBIDDEN

cutover uncertainty
→ nearest producer FORBIDDEN

unknown health emitter/reason semantics
→ assume meaning FORBIDDEN

stale external knowledge without explicit admitted stale rule
→ Coder-chosen claim behavior FORBIDDEN

expired knowledge
→ silently retain old strength FORBIDDEN

KnowledgeFreshnessPolicy semantic change
→ activate without new affected provenance + KnowledgeBundle FORBIDDEN

unsupported future evidence schema
→ parse nearest schema FORBIDDEN

unsupported future evidence schema
→ drop from audit membership FORBIDDEN

unsupported future evidence schema payload bytes
→ omit from verified deterministic resource sizing FORBIDDEN

tcp_syn/1
→ approximate tcp_syn/2 FORBIDDEN

malformed observable packet
→ silently discard complete fingerprintable packet FORBIDDEN

content ceiling exceeded
→ classify first N rows FORBIDDEN

operational timeout
→ device semantic not_evaluable/unknown FORBIDDEN

ambiguous K1
→ first/best/popular row FORBIDDEN

same-origin repetitions
→ extra votes FORBIDDEN

declared Client Hint
→ automatic reliability priority FORBIDDEN

IEEE assignment org
→ automatic device manufacturer FORBIDDEN

JA4 without admitted reference knowledge
→ platform/device heuristic FORBIDDEN

Fingerbank Cloud in Task-04 V1
→ production client submission FORBIDDEN

validation result
→ automatic knowledge/policy mutation FORBIDDEN

classification failure
→ Authorization/CAPPORT impact FORBIDDEN

independent active artifact pointers
→ torn runtime set FORBIDDEN

production classification
→ read active FoundationRuntimeProfile independently after pinning ClassificationRuntimeProfile FORBIDDEN

runtime profile or acceptance lineage
→ alter pure ClassificationRequest digest when pure semantic inputs are unchanged FORBIDDEN

Task04AcceptanceManifest
→ embedded inside candidate ClassificationRuntimeProfile semantic content FORBIDDEN

candidate ClassificationRuntimeProfile validated by T-09
→ rebuild with different semantic digest before activation FORBIDDEN

RuntimeProfileAdmissionManifest
→ reference the GateResultManifest that outputs it FORBIDDEN

CapabilityDisposition
→ reference its producing GateResultManifest FORBIDDEN

any ArtifactContent dependency cycle
→ admission/activation FORBIDDEN

invalidated TTL proof
→ continue TCP/p0f claims FORBIDDEN

unsafe old ClassificationRuntimeProfile after TTL topology invalidation
→ continue new classification traffic FORBIDDEN

SourceHealthPolicy requiring deleted predecessor history
→ activate anyway FORBIDDEN

later FoundationRuntimeProfile valid-from
→ move earlier than initial FoundationAdmissionManifest valid-from FORBIDDEN
```

At the relevant boundary:

```text
fail closed with the typed reason from §126.1
or safe no-claim where R12 explicitly defines one
```

Appendix F is the exhaustive stop-condition/error matrix.

---

# 165. R12 FINAL-CANDIDATE control-plane/schema acceptance checklist record

Before returning R12, Architect independently verified:

```text
1. R11 → R12 unauthorized frozen semantic changes = 0

2. Frozen semantic-field coverage = PASS
   FrozenSemanticFields(type) SUBSET OF C3SemanticFields(type)

3. §12 ArtifactContentTypes == Appendix C ArtifactContentTypes == C.3 RegistryTypes

4. all C.3 types/nested semantic shapes resolved; no undefined semantic type tokens

5. ArtifactContent dependency graph acyclic

6. activation transaction crash-atomic:
   externally visible pointer IFF ActivationRecord + initial ACTIVE ValidityRecord + canonical head durable

7. validity head unique and CAS-protected; no timestamp/UUID/latest-row ordering

8. T-ACCEPT performs no production activation

9. production classification activation requires explicit Owner authorization

10. classification RuntimeProfileAdmissionManifest pins exact foundation RuntimeProfileAdmissionManifest

11. every update_class transition has constructible compatible intermediate state or exact permitted composite class

12. JA4 V1 schema contradiction absent

13. Foundation INPUT / WHAT NEXT / Appendix D exact

14. Task-04 INPUT / WHAT NEXT / Appendix E exact

15. 0 stale current-revision labels

16. 0 TODO/TBD/undefined semantic SHAPE
```

Measured/configuration VALUES owned by future gates may remain unresolved only where the frozen architecture explicitly delegates the value. Semantic shape/type/transition/precedence does not remain unresolved.

---

# 166. Required R12 status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R12

STATUS =
FINAL CANDIDATE — CONTROL-PLANE/SCHEMA CLOSED
FOR OWNER + TECHLEAD11 FINAL REVIEW

R11 =
FROZEN PREDECESSOR
except explicitly authorized R12 corrections above

ARCHITECTURE CONTRACT FINAL =
NO

TASK-04 =
HOLD

TASK-04 CODER TASK =
NO

PRODUCTION CHANGE =
NO
```

R12 MUST NOT self-promote to FINAL.

Only:

```text
OWNER ACCEPT
+
TECHLEAD11 FINAL ACCEPT
```

may promote it.

---

# APPENDIX A — R11 → R12 Preservation Matrix

R11 is the frozen semantic baseline. R12 changes only the exact TechLead11-authorized control-plane/schema corrections.

| R11 contract / zone | R12 disposition | Authority / reason |
|---|---|---|
| §§1–3 revision/status/baseline wording | REVISED — MECHANICAL / AUTHORIZED | R12 status and current-baseline wording |
| §6 lifecycle acceptance vs production activation | REVISED — EXPLICIT FROZEN-CONTRACT EXCEPTION | R12-05 |
| §§4–5,7–10 frozen architecture semantics | FROZEN / PRESERVED | R12-00 |
| §11.4 RuntimeProfileAdmissionManifest lineage/update composition | REVISED — AUTHORIZED | R12-07, R12-09 |
| §11.5 activation/validity control plane | REVISED — AUTHORIZED | R12-03, R12-04, R12-05, R12-06 |
| §11.6 acyclicity principle | FROZEN / PRESERVED | R12-00 |
| §12 catalog | REVISED — SCHEMA CATALOG CONSISTENCY ONLY | R12-02 |
| §§13–77 | FROZEN / PRESERVED | R12-00 |
| §78 SourceGovernanceRecord semantics | FROZEN / PRESERVED; C.3 typed representation corrected | R12-01 |
| §79 KnowledgeProvenanceManifest semantics | FROZEN / PRESERVED; C.3 typed union corrected | R12-01 |
| §§80–81 | FROZEN / PRESERVED | R12-00 |
| §82 KnowledgeBundle optional JA4 field | REVISED — EXPLICIT FROZEN-CONTRACT EXCEPTION | R12-08 |
| §§83–110 | FROZEN / PRESERVED except mechanical activation cross-reference | R12-00 / R12-05 |
| §111 ClassificationPolicy semantic meaning | FROZEN / PRESERVED; executable typed representation added | R12-11 |
| §§112,114–117,119–149 | FROZEN / PRESERVED | R12-00 |
| §113 RequestAssembly activation-head lookup | REVISED — AUTHORIZED control-plane closure | R12-04, R12-05 |
| §118 production commit validity lookup | REVISED — AUTHORIZED control-plane closure | R12-04, R12-05 |
| §150 F-F5 crash-atomic/CAS proof | REVISED — NARROW AUTHORIZED EXTENSION | R12-03, R12-04 |
| §150.1 F-F6 | FROZEN / PRESERVED | R12-00 |
| §151 F-ADMIT activation transaction/output prose | REVISED — AUTHORIZED | R12-03, R12-06 |
| §§152–162 | FROZEN / PRESERVED except mechanical dependency wording where Appendix D/E requires exactness | R12-08 review instruction |
| §163 T-ACCEPT | REVISED — EXPLICIT FROZEN-CONTRACT EXCEPTION | R12-05, R12-06, R12-09 |
| §163.1 production activation action | ADDED — AUTHORIZED | R12-05, R12-06 |
| §§164–165 | FROZEN / PRESERVED except R12 checklist/status mechanics | R12-00, R12-12 |
| Appendix B | FROZEN / PRESERVED | R12-00 |
| Appendix C / C.3 | REVISED — SCHEMA CLOSURE ONLY | R12-01,02,08,10,11 |
| Appendix D/E | REVISED — DEPENDENCY PROSE/GRAPH CONSISTENCY ONLY | R12-08 |
| Appendix F | REVISED — ACTIVATION ERROR/STOP CONSISTENCY ONLY | R12-03..06 |
| Appendix G | REVISED — UPDATE/ADMISSION COMPOSITION ONLY | R12-05,07,09 |

Frozen semantic-field coverage rule for all pre-R11 ArtifactContent:

```text
FrozenSemanticFields(type)
SUBSET OF
C3SemanticFields(type)
```

R12 final validation records this as PASS. No frozen semantic field is removed merely because another artifact contains similar information.

---

# APPENDIX B — Permanent Frozen Contract Register

Future revisions MUST carry this register forward.

| Frozen contract | Canonical R10 location |
|---|---|
| Old 12-device/48-sample campaign is not Task-04 blocker | §4 |
| Existing 03A tooling preserved for optional research/regression | §4 |
| Architecture→PRE-TASK→Foundation Admission→Task-04 lifecycle | §6, §126-§153 |
| No broad RSPAN topology redesign | §5.1 |
| No broad sensor-interface/AF_PACKET redesign | §5.1 |
| No raw exact-frame dedup redesign | §5.1 |
| No Suricata EVE redesign | §5.1 |
| Existing Task-01 ingest security/API-envelope boundary preserved except authorized bounded v2 changes | §5.1 |
| Portal Authorization/classification isolation | §5.1, §7 |
| Classification DB separate from Task-01 evidence DB | §5.2, §118 |
| Internal `get_current` / `list_history` equivalent read contract | §5.3 |
| Task-05 owns identity/session integration | §5.4 |
| Task-06 owns presentation integration | §5.4 |
| Global evidence+health ingest sequence | §15-§22 |
| Database generation and controlled restore rebaseline | §18-§21 |
| Empty watermark sequence = 0; row domain starts at 1 | §18 |
| One SQLite read transaction per snapshot | §23 |
| Live vs replay split | §24-§25 |
| Completed-window contract | §26 |
| Payload non-duplication / transient materialization | §27, §31-§32 |
| SnapshotContentPolicy vs SnapshotExecutionPolicy | §36-§37 |
| Single authoritative V1 binding | §39-§41 |
| BindingClockPolicy / cutover quarantine | §42 |
| classification_foundation_valid_from | §43 |
| Coverage != present evidence validity | §44, §51 |
| `covered_delayed` removed conservatively | §45 |
| Task-01-native health retention margin | §49 |
| quality_state valid/partial/degraded semantics | §57 |
| tcp_syn/1 non-fusion | §58 |
| tcp_syn/2 protocol-neutral boundary | §59-§71 |
| tcp_syn/2 frozen durable top-level fields | §61 |
| exact tcp_option_records variants | §62-§70 |
| TCP privacy minimization | §71 |
| K2A/K2B split | §72 |
| Physical TTL/RSPAN proof | §73, §121.2 |
| Critical-CH forbidden | §74 |
| Bounded Accept-CH lifecycle | §75 |
| Portal idle heartbeat | §76 |
| Vendor artifact != runtime schema | §77 |
| K1 all-candidate ambiguity preservation | §86, F-E1 |
| K1 DHCP-origin purity | §87 |
| K1 no first-row/best/popularity scoring | §86 |
| K1 failure does not weaken requirements | §88, F-E1 |
| K2B legacy claim-strength ceiling | §89, F-E2 |
| K3 normalized portal input only | §90-§91 |
| K3 no raw UA/CH/header parsing | §90-§91 |
| K4 IEEE assignment-org semantics | §92 |
| JA4 no-reference = no claim | §93 |
| Fingerbank Cloud V1 out of scope/default OFF/no production submission | §94 |
| classification_taxonomy_v1 | §95 |
| ios includes iPadOS family in V1 | §95 |
| recognized_out_of_scope only platform/device_class | §96 |
| canonical manufacturer/model IDs | §97 |
| claim_derivation != claim_strength | §98 |
| origin purity | §99 |
| row count != votes / semantic dedup | §100 |
| OriginDimensionAssessment candidate semantics | §101, §104 |
| same-origin conflict_strength | §102 |
| cross-origin strength rules | §105 |
| HIGH forbidden with any incompatible claim including same-origin lower strength | §107 |
| DimensionResult semantics | §108-§109 |
| global-status precedence | §110 |
| ClassificationPolicy pure semantics only | §111 |
| pure core no I/O / no clock | §114 |
| exact classifier artifact identity | §115 |
| ClassificationRetentionPolicy separated | §119 |
| two-level audit | §120 |
| no automatic learning | §121 |
| controlled validation safety + utility | §122, T-09 |
| Foundation gates before Task-04 | §126-§151 |
| Task-04 acceptance gates after implementation | §153-§163 |
| all no-silent-fallback rules | §164, Appendix F |

No future revision may silently drop a register entry because it predates the immediately previous revision.

---

Additional predecessor contracts frozen in R9 and preserved by R10:

| Frozen R9 contract | Canonical R10 location |
|---|---|
| Runtime execution-set content is separate from acceptance/governance lineage | §11.1-§11.4 |
| Candidate ClassificationRuntimeProfile exists and is tested before Task04AcceptanceManifest | §11.2, T-06A, T-05, T-09 |
| T-ACCEPT accepts the exact profile digest tested by T-05/T-09; production activation is a separate Owner-authorized action | §125, §163, §163.1 |
| Production live classification pins ClassificationRuntimeProfile before snapshot build | §24, §113 |
| FoundationRuntimeProfile activation alone does not alter production classification | §11.5, §121.1 |
| EvidenceSnapshotContent semantic digest excludes operational/runtime-profile lineage | §27-§28 |
| ClassificationRequest digest excludes runtime-profile/governance/operational identity | §116 |
| OriginRuntimeAdmission makes TCP enable/disable executable in pure semantics | §12.11, §28, §114 |
| Stale knowledge behavior is explicit per KnowledgeFreshnessPolicy | §81, §111 |
| Unknown-schema compatibility is not SourceEvaluability | §32, §126.1 |
| All integrity-checked unknown-schema payload bytes count toward deterministic sizing | §36, F-A4, T-01 |
| KnowledgeFreshnessPolicy semantic update requires new provenance + KnowledgeBundle | §121.1, Appendix G |
| Artifact SET ordering has canonical-byte total tie-break | §9.3 |
| ArtifactContent schemas are closed-world per schema version | §10.1 |
| OriginAssessment top-level/nested schemas are exact | §101-§101.1 |
| Immutable ArtifactContent dependency graph must be acyclic | §11.6, F-F6 |
| classification_foundation_valid_from never moves earlier within lineage | §43.1 |


---


## B.1 R10 surgical contracts that become frozen if R10 is accepted

| R10 contract | Canonical R10 location |
|---|---|
| Per-classification persistence CORE excludes future acceptance/admission IDs; production commit requires admitted profile | §118, T-07 |
| F-ADMIT exact dependency order builds OriginRuntimeAdmission before FoundationAdmissionManifest | F-ADMIT |
| Initial V1 Foundation Admission requires F-C3 PASS, TTL proof and TCP ENABLED | §124, F-ADMIT |
| KnowledgeFreshnessPolicy depends on stable source_family_id and exact integer millisecond age thresholds | §81, F-E5 |
| Freshness cap can only preserve/reduce claim authority and has exact dimension-override precedence | §81.1 |
| KnowledgeBundle refresh creates candidate CRP before its admission manifest | §83 |
| RuntimeProfileAdmissionManifest update_class is a closed V1 enum | §11.4 |
| Semantic Task-04 changes require a new Task04AcceptanceManifest; bounded non-semantic classes may explicitly reuse prior lineage | §121.1, §125, Appendix G |
| Rollback reactivation is a new audited activation event with ROLLBACK_REACTIVATION | §11.5.1, Appendix G |
| T-06A candidate profile P is used by T-05/T-07/T-08/T-09/T-ACCEPT | T-06A through T-ACCEPT, Appendix E |


## B.R11 Schema/lineage closure contracts becoming frozen upon R11 acceptance

```text
Artifact Schema Registry V1 closed-world completeness
CanonicalKnowledgeRecordSet single universal identity
RuntimeProfileActivationRecord exact activation lineage
RuntimeProfileValidityRecord deterministic admissibility/invalidation
production classification exact activation pin
TTL invalidation fail-closed production commit rejection
direct/transitive reference equality invariants
single update_class composition rule
gate INPUT / WHAT NEXT / Appendix D/E exact consistency
```

# APPENDIX C — Immutable Artifact Catalog

All semantic ArtifactContent uses §9-§10 identity and CLOSED-WORLD schema rules.

Universal collection rule:

```text
SEQUENCE → preserve declared semantic order
SET → primary key declared by owning contract; equal primary keys use ArtifactCanonicalJsonV1(element) UTF-8 bytes as total tie-break; byte-identical duplicates FAIL
MAP → canonical object-key order after duplicate/NFC collision validation
```

No duplicate artifact type entry exists in this catalog.

| ArtifactContent type | Exact semantic contract / ordering authority | Retention / activation role |
|---|---|---|
| ArchitectureContractReference | §12.1 | Permanent architecture lineage |
| Task01WatermarkReadContract | F-A1 output contract | Foundation/replay lineage |
| Task01SchemaMigrationContract | §13-§14 / F-A1 | Migration/recovery lineage |
| Task01GenerationRecoveryContract | §18-§21 / F-A2 | Recovery lineage |
| Task01HealthRetentionContract | §49 / F-B3 | FoundationRuntimeProfile dependency |
| TcpSynV2SchemaContract | §12.6, §59-§71 / F-C1 | EvidenceSchemaRegistry/Foundation lineage |
| PortalHeadersV2SchemaContract | §12.7 / F-D1 when ADMITTED | EvidenceSchemaRegistry/Foundation lineage |
| CapabilityDisposition | §12.2 | Optional capability ADMITTED/NOT_ADMITTED disposition |
| EvidenceSchemaRegistryContract | §33 / F-A5 | FoundationRuntimeProfile semantic builder dependency |
| EvidenceAdapterContractSet | §55 / F-F1 | ClassificationRuntimeProfile + classifier compatibility |
| SourceHealthEmitterContract | §46.1 / F-B0 | Binding epochs / health semantics |
| EvidenceSourceBindingTimeline | §39-§41 / F-B1 | FoundationRuntimeProfile authority |
| BindingClockPolicy | §42 / F-B1 | FoundationRuntimeProfile authority |
| SourceHealthPolicy | §46.2 / F-B2 | SourceEvaluability construction |
| OriginRuntimeAdmission | §12.11 | FoundationRuntimeProfile; inline semantic pin in EvidenceSnapshotContent |
| SnapshotContentPolicy | §36 / F-A4 | Deterministic snapshot build ceiling; not pure request identity |
| SnapshotExecutionPolicy | §37 / F-A4 | Operational runtime profile/SnapshotRecord only |
| ClassificationTaxonomy | §95 / F-E6 | KnowledgeBundle/ClassificationPolicy |
| AliasMapping | §97 / F-E6 | KnowledgeBundle |
| K3PortalRuleSet | §90-§91 / F-E3 | Internal K3 knowledge |
| KnowledgeFreshnessPolicy | §81 / F-E5 | Stable source_family_id + exact integer-age external claim admissibility |
| SourceGovernanceRecord | §78 / F-E5 | External legal/governance semantics |
| KnowledgeProvenanceManifest | §79 / F-E1/E2/E3/E4 | Internal/external provenance |
| CanonicalKnowledgeRecordSet | §12.3 / F-E1/E2/E4 | Concrete K1/K2B/K4 set |
| KnowledgeBundle | §82-§83 / F-E7 | ClassificationRuntimeProfile |
| ClassificationPolicy | §111 / F-F2 | Pure classifier semantics |
| ClassificationRetentionPolicy | §119 / F-F3 | Persistence/GC only |
| ProductValidationPolicy | §122 / F-F4 | T-09 acceptance only |
| FoundationAdmissionManifest | §124 | Immutable initial Foundation lineage root; never current-runtime pointer |
| FoundationRuntimeProfile | §11.1 | Atomic foundation execution set; standalone active pointer |
| Task04AcceptanceManifest | §125 | Accepted implementation lineage; NEW for semantic reacceptance, references exact tested candidate profile |
| ClassificationRuntimeProfile | §11.2 | Atomic production classification execution set; one active classification pointer |
| RuntimeProfileAdmissionManifest | §11.4 / Appendix G | Closed update_class enum; governance link from already-existing profile to lineage roots/prerequisite gates |
| RuntimeProfileActivationRecord | §11.5.2 | Exact successful activation event; same profile may have many activation records |
| RuntimeProfileValidityRecord | §11.5.3 | Auditable ACTIVE/INACTIVE/SUSPENDED_INVALIDATED admissibility chain |
| ClassifierArtifactManifest | §115 | Exact classifier/adapters/K2A/build identity |
| EvidenceSnapshotContent | §27-§35 | Durable semantic snapshot manifest; no duplicated normalized payload |
| SnapshotRecord | §27 | Runtime/execution audit lineage; retained while referenced |
| SourceEvaluability | §53-§54 | Coverage-only semantic input; retained Level-B |
| OriginAssessment | §101-§101.1 | Exact origin semantic assessment; retained Level-B |
| ClassificationRequestManifest | §116 | Pure semantic request identity only |
| ClassificationResult | §117 | Pure semantic classification result |
| ControlledValidationGroundTruthRecord | §12.4, §122.1 | Pre-result validation truth |
| ProductValidationComparisonRecord | §12.5, §122.2 | Validation truth/request/result comparison |
| GateResultManifest | §123 | Machine/audit gate result; never a back-reference from its outputs |
| GateProofArtifact | §12.10 | Reusable proof result by exact proof_kind |
| K2AConformancePackage | §12.8 / F-C2 | p0f oracle/conformance package |
| TTLCapturePlacementProof | §12.9 / F-C3 | Topology-specific TTL proof |

Transient NON-retained semantic execution object:

```text
EvidenceSnapshotMaterialization — §31-§32
```

Immutable audit records, not semantic ArtifactContent:

```text
ArtifactRegistration — §10.2
DecisionRecord — §10.3
```

No ReviewRecord/review-registration reference type exists in R12.

## C.1 Exact SET primary keys / total tie-break

```text
OriginDimensionAssessment.claim_derivations
→ primary key = derivation string

CandidateEntry set
→ primary tuple defined in §101

EvidenceRef set
→ primary key = evidence_id

KnowledgeRef set
→ primary tuple defined in §101

SameOriginContradictionRecord set
→ primary tuple defined in §101

BroadUnresolvedRef set
→ primary tuple defined in §101

OriginAssessment dimension assessments
→ primary key = dimension_name

DimensionResult supporting/contradicting/not-evaluable origins
→ primary key = canonical origin enum value

DimensionResult knowledge refs
→ primary key = canonical KnowledgeRef tuple

DimensionResult out-of-scope refs
→ primary key = canonical taxon ID

Gate IDs
→ primary key = gate_id

GateResult input/output artifact refs
→ primary key = artifact_id

GateResult retained evidence refs
→ primary tuple = (evidence_label, file_sha256)

DecisionRecord refs
→ primary key = decision_record_id

Artifact/provenance/governance reference sets
→ primary key = artifact_id
```

For EVERY SET above and every other SET-like ArtifactContent collection, equal primary keys use the universal canonical-byte tie-break from §9.3. Byte-identical duplicate SET elements are invalid.

## C.2 Closed-world schema invariant

For every ArtifactContent in this catalog:

```text
artifact_schema_version fixes EXACT allowed top-level and nested semantic fields
undeclared semantic field = VALIDATION FAIL
new semantic field = schema-version change unless already explicitly optional
```

## C.3 Artifact Schema Registry V1

This appendix is NORMATIVE and closes the R12 closed-world ArtifactContent contract.

For every ArtifactContent below:

```text
artifact_type exact string = table key below
artifact_schema_version = 1 unless the owning section explicitly freezes another integer
semantic payload MUST contain exactly the fields declared by this registry or the exact normative section reference
undeclared top-level or nested semantic field = VALIDATION FAIL
new semantic field = new artifact_schema_version unless already declared optional here
```

### C.3.1 Common V1 scalar/reference types

```text
Sha256 = lowercase ASCII hex string matching ^[0-9a-f]{64}$
GitSha = lowercase ASCII hex string matching ^[0-9a-f]{40}$
UuidV4 = canonical lowercase UUID version-4 string matching RFC-4122 textual 8-4-4-4-12 form
UtcMs = exact ASCII timestamp YYYY-MM-DDTHH:MM:SS.mmmZ validated by current Task-01 UTC contract
Mac48 = canonical lowercase colon MAC aa:bb:cc:dd:ee:ff
SiteId = lowercase ASCII 24-hex Site identifier matching ^[0-9a-f]{24}$
ArtifactId = universal §10.1 artifact ID string whose artifact_type exists in Artifact Schema Registry V1
ReasonCode = non-empty NFC string from the exact owning closed enum/domain; never free implementation text
NonEmptyString = NFC-normalized UTF-8 string with Unicode scalar length >=1
PrintableAscii1To128 = string length 1..128 whose every code point is U+0020..U+007E inclusive
PositiveInt64 = integer 1..9223372036854775807
NonNegativeInt64 = integer 0..9223372036854775807
Int32Positive = integer 1..2147483647
Nullable<T> = null OR exact T
DimensionName = enum{platform_family,device_class,manufacturer_family,model_family}
OriginGroup = enum{dhcp,portal,tcp,tls,quic,mac_registry}
ClaimStrength = enum{strong,supporting}
ClaimDerivation = enum{declared,deterministic_mapping,fingerprint_match,registry_mapping}
ArtifactRef<T> = object exactly {artifact_id: ArtifactId, content_sha256: Sha256}, whose ArtifactId artifact_type MUST equal T
AnyArtifactRef = object exactly {artifact_id: ArtifactId, content_sha256: Sha256}, whose ArtifactId artifact_type MUST be a member of the C.3 RegistryTypes set
```

All semantic objects are closed-world. All strings are NFC-normalized before validation/hash under §9. Duplicate JSON keys and NFC key collisions fail before schema validation.

The snake_case field identifiers in Appendix C.3 are the canonical ArtifactContent JSON keys. Earlier prose labels such as `KnowledgeBundle ID/digest` are normative human-readable aliases for the corresponding C.3 `ArtifactRef` field and do not create an additional field.

No undefined alias, unbounded placeholder type, untyped sequence, prose-only nullable grammar, or untyped reference target is valid in C.3.

---

### C.3.2 Common nested objects

#### ArtifactRef

Exactly:

```text
artifact_id: ArtifactId
content_sha256: Sha256
```

#### EvidenceRef

Exactly §101:

```text
evidence_id: UuidV4
payload_sha256: Sha256
feature_schema_version: int[1..2147483647]
adapter_contract_id: ArtifactId
adapter_contract_digest: Sha256
```

#### KnowledgeRef

Exactly §101:

```text
knowledge_bundle_id: ArtifactId
knowledge_bundle_digest: Sha256
canonical_knowledge_record_id: NonEmptyString
knowledge_provenance_id: ArtifactId
knowledge_provenance_digest: Sha256
rule_or_source_record_identity: NonEmptyString
```

#### ProofExecutionIdentity

Exactly:

```text
execution_id: UuidV4
executor_kind: NonEmptyString
repository_commit_sha: Nullable<GitSha>
repository_tree_sha: Nullable<GitSha>
procedure_or_test_suite_id: NonEmptyString
environment_identity: NonEmptyString
execution_artifact_sha256: Nullable<Sha256>
```

#### RetainedEvidenceRef

Exactly:

```text
evidence_label: NonEmptyString
file_sha256: Sha256
media_type: NonEmptyString
path_or_reference: Nullable<NonEmptyString>
```

#### RuntimeProfileRef

Exactly `ArtifactRef<FoundationRuntimeProfile>` or `ArtifactRef<ClassificationRuntimeProfile>` according to the owning field.

### C.3.3 Registry — exact schema authority for every ArtifactContent

| artifact_type | schema authority |
|---|---|
| `ArchitectureContractReference` | EXACT §12.1 fields; no additional fields |
| `Task01WatermarkReadContract` | INLINE C.3.4 |
| `Task01SchemaMigrationContract` | INLINE C.3.5 |
| `Task01GenerationRecoveryContract` | INLINE C.3.6 |
| `Task01HealthRetentionContract` | INLINE C.3.7 |
| `TcpSynV2SchemaContract` | INLINE C.3.8 |
| `PortalHeadersV2SchemaContract` | INLINE C.3.9 |
| `CapabilityDisposition` | EXACT §12.2 fields/invariants |
| `EvidenceSchemaRegistryContract` | INLINE C.3.10 |
| `EvidenceAdapterContractSet` | INLINE C.3.11 |
| `SourceHealthEmitterContract` | EXACT §46.1 plus nested schema C.3.12 |
| `EvidenceSourceBindingTimeline` | INLINE C.3.13 |
| `BindingClockPolicy` | INLINE C.3.14 |
| `SourceHealthPolicy` | EXACT §46.2 plus nested schema C.3.15 |
| `OriginRuntimeAdmission` | EXACT §12.11 fields/invariants |
| `SnapshotContentPolicy` | EXACT §36 fields/invariants |
| `SnapshotExecutionPolicy` | INLINE C.3.16 |
| `ClassificationTaxonomy` | INLINE C.3.17 |
| `AliasMapping` | INLINE C.3.18 |
| `K3PortalRuleSet` | INLINE C.3.19 |
| `KnowledgeFreshnessPolicy` | EXACT §81 fields/invariants plus nested state/override schema there |
| `SourceGovernanceRecord` | INLINE C.3.20 |
| `KnowledgeProvenanceManifest` | INLINE C.3.21 |
| `CanonicalKnowledgeRecordSet` | INLINE C.3.22 |
| `KnowledgeBundle` | EXACT §82 fields + R12 equality invariants; no additional fields |
| `ClassificationPolicy` | INLINE C.3.23 |
| `ClassificationRetentionPolicy` | INLINE C.3.24 |
| `ProductValidationPolicy` | INLINE C.3.25 |
| `FoundationAdmissionManifest` | EXACT §124 field list/invariants |
| `FoundationRuntimeProfile` | EXACT §11.1 fields/invariants |
| `Task04AcceptanceManifest` | EXACT §125 fields/invariants |
| `ClassificationRuntimeProfile` | EXACT §11.2 fields/invariants |
| `RuntimeProfileAdmissionManifest` | EXACT §11.4 fields/invariants + §11.4.1 composition rule |
| `RuntimeProfileActivationRecord` | EXACT §11.5.2 fields/invariants |
| `RuntimeProfileValidityRecord` | EXACT §11.5.3 fields/invariants |
| `ClassifierArtifactManifest` | INLINE C.3.26 |
| `EvidenceSnapshotContent` | INLINE C.3.27 |
| `SnapshotRecord` | INLINE C.3.28 |
| `SourceEvaluability` | INLINE C.3.29 |
| `OriginAssessment` | INLINE C.3.30 |
| `ClassificationRequestManifest` | EXACT §116 fields/invariants |
| `ClassificationResult` | INLINE C.3.31 |
| `ControlledValidationGroundTruthRecord` | INLINE C.3.32 |
| `ProductValidationComparisonRecord` | INLINE C.3.33 |
| `GateResultManifest` | INLINE C.3.34 |
| `GateProofArtifact` | INLINE C.3.35 |
| `K2AConformancePackage` | INLINE C.3.36 |
| `TTLCapturePlacementProof` | INLINE C.3.37 |

### C.3.4 Task01WatermarkReadContract

Exact payload:

```text
contract_version: Int32Positive
database_generation_field_name: "database_generation_id"
ingest_sequence_field_name: "ingest_sequence"
ingest_sequence_min: 1
ingest_sequence_max: 9223372036854775807
shared_row_families: SET<enum{device_fingerprint_evidence,device_fingerprint_source_health_events}>
watermark_object_fields: SEQUENCE<string> exactly [database_generation_id,max_committed_ingest_sequence]
snapshot_read_transaction_required: true
same_connection_all_pages_required: true
post_watermark_rows_excluded: true
```

`shared_row_families` primary key = enum string.

### C.3.5 Task01SchemaMigrationContract

Exact payload:

```text
contract_version: Int32Positive
from_schema_version: Int32Positive
to_schema_version: int[2..2147483647]
exclusive_migration_required: true
writer_blocked_until_commit: true
new_database_generation_required: true
bootstrap_sequence_assignment_rule_id: NonEmptyString
bootstrap_claims_historical_commit_order: false
ordered migration_steps: SEQUENCE<MigrationStep>
rollback_mode: enum{V2_COMPATIBLE_APP_ROLLBACK,PRE_V2_APP_ROLLBACK_REQUIRES_DB_RESTORE_RECOVERY}
```

`MigrationStep` exactly `{step_index:Int32Positive, step_id:NonEmptyString, operation:NonEmptyString}`; `step_index` strictly increasing from 1 without duplicates.

### C.3.6 Task01GenerationRecoveryContract

Exact payload:

```text
contract_version: Int32Positive
trigger_classes: SET<enum{DATABASE_BACKUP_RESTORE,VM_SNAPSHOT_ROLLBACK,FILESYSTEM_ROLLBACK,DATABASE_REBUILD_FROM_OLDER_MATERIAL}>
writer_stop_required: true
new_generation_required: true
rebaseline_all_retained_rows_required: true
sequence_reuse_forbidden: true
sequence_wrap_forbidden: true
allocator_exhaustion_behavior: "FAIL_CLOSED"
idempotent_duplicate_consumes_sequence: false
conflicting_duplicate_behavior: "ROLLBACK"
cleanup_advances_sequence: false
```

### C.3.7 Task01HealthRetentionContract

Exact payload:

```text
contract_version: Int32Positive
source_health_policy: ArtifactRef<SourceHealthPolicy>
required_health_anchor_margin_seconds: NonNegativeInt64
preserve_predecessor_anchor: true
retained_evidence_horizon_seconds: NonNegativeInt64
retained_health_horizon_seconds: NonNegativeInt64
retention_compatibility_status: "PASS"
```

Invariant: retained health capability MUST satisfy §49/§49.1 required margin before policy/profile activation.

### C.3.8 TcpSynV2SchemaContract

Top-level exact payload fields are §12.6. Nested types are exactly:

`TopLevelFieldContract`:

```text
field_name: NonEmptyString
field_type: enum{INT,BOOL,ENUM,ARRAY}
nullable: bool
minimum_int: Nullable<int[-9223372036854775808..9223372036854775807]>
maximum_int: Nullable<int[-9223372036854775808..9223372036854775807]>
enum_values: SET<string>
privacy_role: NonEmptyString
```

Cross-field: non-INT => minimum_int/maximum_int null; non-ENUM => enum_values empty.

`TcpOptionVariantContract`:

```text
variant_id: enum{EOL,NOP,MSS,WINDOW_SCALE,SACK_PERMITTED,TIMESTAMP,UNKNOWN}
kind_value: int[0..255]
exact_fields: SET<string>
malformed_observable_supported: bool
```

`top_level_field_contracts` SET primary key=`field_name`; option variants SET primary key=`variant_id`. Actual allowed V2 evidence fields/variant semantics remain exactly §61-§70.

### C.3.9 PortalHeadersV2SchemaContract

Top-level exact payload fields are §12.7. Nested `NormalizedFieldContract` exactly:

```text
field_id: NonEmptyString
value_type: enum{STRING,INTEGER,BOOLEAN,ENUM}
nullable: bool
enum_values: SET<string>
normalization_rule_id: NonEmptyString
source_header_id: NonEmptyString
```

`ProvenanceContract` exactly `{normalized_field_id:NonEmptyString, provenance_field_id:NonEmptyString, allowed_source_values:SET<string>}`.

Both collections are SET-like; primary keys are `field_id` and `normalized_field_id` respectively. Only fields admitted by F-D1 may appear.

### C.3.10 EvidenceSchemaRegistryContract

Exact payload:

```text
registry_contract_version: Int32Positive
evidence_canonical_json_version: NonEmptyString
schema_entries: SET<EvidenceSchemaEntry>
portal_headers_v2_disposition: ArtifactRef<CapabilityDisposition>
```

`EvidenceSchemaEntry` exactly:

```text
source_kind: NonEmptyString
feature_schema_version: int[1..2147483647]
schema_status: enum{SUPPORTED,KNOWN_NON_FUSION}
validator_contract_id: NonEmptyString
schema_contract_ref: Nullable<ArtifactRef<TcpSynV2SchemaContract|PortalHeadersV2SchemaContract>>
```

Primary key `(source_kind,feature_schema_version)`. Current mandatory entries exactly cover `dhcp/1,tcp_syn/1,tls_client/1,quic_client/1,portal_headers/1` plus `tcp_syn/2` and `portal_headers/2` only according to final admitted disposition. Unknown future schemas are not registry entries.

### C.3.11 EvidenceAdapterContractSet

Exact payload:

```text
adapter_contract_set_version: Int32Positive
evidence_schema_registry: ArtifactRef<EvidenceSchemaRegistryContract>
adapter_entries: SET<EvidenceAdapterEntry>
```

`EvidenceAdapterEntry` exactly:

```text
adapter_contract_id: NonEmptyString
origin_group: enum{dhcp,portal,tcp,tls,quic,mac_registry}
source_kind: NonEmptyString
feature_schema_version: int[1..2147483647]
supported_source_subtypes: SET<string>
extractor_name_constraints: SET<string>
extractor_version_constraints: SET<string>
rule_version_constraints: SET<string>
quality_valid_behavior: NonEmptyString
quality_partial_behavior: "SUPPORTING_CAP_IF_REQUIRED_FIELDS_PRESENT"
quality_degraded_behavior: "NO_CLAIM"
required_fields_by_dimension: MAP<DimensionName,SET<NonEmptyString>>
legacy_current_role: enum{CURRENT,LEGACY_NON_FUSION,LEGACY_SUPPORTED}
claim_derivation: enum{declared,deterministic_mapping,fingerprint_match,registry_mapping}
base_claim_strength_ceiling: enum{strong,supporting}
semantic_projection_id: NonEmptyString
unsupported_behavior: "UNSUPPORTED_EVIDENCE_CONTRACT_NO_CLAIM"
```

Primary key `adapter_contract_id`; MAP dimension keys limited to the four V1 dimensions.

### C.3.12 SourceHealthEmitterContract

Exact top-level payload:

```text
emitter_contract_version: Int32Positive
producer_service_implementation_identity: NonEmptyString
source_kinds: SET<NonEmptyString>
heartbeat_behavior_cadence_semantics: HeartbeatBehaviorContract
persisted_status_emission_semantics: StatusEmissionContract
reason_code_definitions: SET<ReasonCodeDefinition>
delivery_spool_loss_behavior_relevant_to_coverage: DeliveryCoverageContract
task01_delayed_event_interaction: DelayedEventInteractionContract
source_health_event_compatibility_version: Int32Positive
```

`HeartbeatBehaviorContract` exactly:

```text
mode: enum{PERIODIC,EVENT_DRIVEN,NONE}
nominal_interval_ms: Nullable<PositiveInt64>
same_state_heartbeat_required: bool
```

Cross-field: `mode=PERIODIC` requires non-null `nominal_interval_ms`; other modes require null.

`StatusEmissionContract` exactly:

```text
allowed_statuses: SET<enum{available,unavailable,unsupported}>
status_transition_delivery_required_when_transport_available: bool
```

`ReasonCodeDefinition` exactly:

```text
reason_code: NonEmptyString
exact_meaning: NonEmptyString
status_compatibility: SET<enum{available,unavailable,unsupported}>
failure_domain_semantics: enum{ACQUISITION,DELIVERY,CAPABILITY,RECOVERY,OTHER}
```

`DeliveryCoverageContract` exactly:

```text
producer_spool_mode: enum{NONE,BOUNDED_LOSSY,BOUNDED_NONLOSSY}
lossless_interval_completion_claim_permitted: false
evidence_eviction_possible: bool
capacity_block_possible: bool
```

For V1, `lossless_interval_completion_claim_permitted` MUST be `false`; this preserves removal of `covered_delayed`.

`DelayedEventInteractionContract` exactly:

```text
must_obey_task01_delayed_event_contract: true
historical_health_backfill_permitted_when_within_task01_limit: bool
recovery_never_proves_missing_interval_complete: true
```

`source_kinds` primary key = source-kind string. `reason_code_definitions` primary key = `reason_code`; universal SET tie-break applies.

### C.3.13 EvidenceSourceBindingTimeline

Exact payload:

```text
binding_timeline_contract_version: Int32Positive
binding_epochs: SET<BindingEpoch>
```

`BindingEpoch` exactly:

```text
binding_epoch_id: NonEmptyString
site_id: SiteId
origin_group: enum{dhcp,portal,tcp,tls,quic}
source_kind: NonEmptyString
capture_source_id: NonEmptyString
producer_id: NonEmptyString
source_health_emitter_contract: ArtifactRef<SourceHealthEmitterContract>
effective_from_utc: UtcMs
effective_to_utc: Nullable<UtcMs>
```

Primary key `binding_epoch_id`. Cross-field/overlap rules remain exactly §39-§42; `mac_registry` forbidden.

### C.3.14 BindingClockPolicy

Exact payload:

```text
binding_clock_policy_version: Int32Positive
producer_clock_domains: SET<ClockDomain>
task01_clock_domain_id: NonEmptyString
measured_max_relative_clock_offset_ms: NonNegativeInt64
measurement_method_id: NonEmptyString
measurement_evidence_ref: NonEmptyString
cutover_guard_seconds: NonNegativeInt64
```

`ClockDomain` exactly `{clock_domain_id:NonEmptyString, producer_id:NonEmptyString}`; SET primary key=`clock_domain_id`.

### C.3.15 SourceHealthPolicy

Exact top-level payload:

```text
source_health_policy_version: Int32Positive
accepted_source_health_emitter_contracts: SET<ArtifactRef<SourceHealthEmitterContract>>
emitter_source_family_rules: SET<EmitterSourceFamilyRule>
task01_timestamp_skew_contract_ref: NonEmptyString
task01_delayed_event_contract_ref: NonEmptyString
health_anchor_margin_seconds: NonNegativeInt64
```

`EmitterSourceFamilyRule` exactly:

```text
source_health_emitter_contract: ArtifactRef<SourceHealthEmitterContract>
source_kind: NonEmptyString
expected_heartbeat: ExpectedHeartbeatRule
freshness: HealthFreshnessRule
status_reason_failure_domain_mappings: SET<StatusReasonMapping>
coverage_class_mapping: SET<CoverageMapping>
backfill: HealthBackfillRule
```

`ExpectedHeartbeatRule` exactly:

```text
mode: enum{PERIODIC,EVENT_DRIVEN,NONE}
nominal_interval_ms: Nullable<PositiveInt64>
```

Cross-field: `PERIODIC` requires non-null interval; other modes require null.

`HealthFreshnessRule` exactly:

```text
freshness_timeout_ms: NonNegativeInt64
when_timeout_exceeded: "unknown"
```

`StatusReasonMapping` exactly:

```text
status: enum{available,unavailable,unsupported}
reason_code: Nullable<NonEmptyString>
failure_domain: enum{ACQUISITION,DELIVERY,CAPABILITY,RECOVERY,OTHER}
coverage_class: enum{covered_available,acquisition_unavailable,delivery_unavailable_loss_possible,delivery_loss_confirmed,unsupported,unknown}
```

`CoverageMapping` exactly `{failure_domain:enum{ACQUISITION,DELIVERY,CAPABILITY,RECOVERY,OTHER}, coverage_class:enum{covered_available,acquisition_unavailable,delivery_unavailable_loss_possible,delivery_loss_confirmed,unsupported,unknown}}`.

`HealthBackfillRule` exactly:

```text
must_obey_task01_delayed_event_contract: true
arrived_backfill_present_evidence_usable: true
recovery_never_upgrades_interval_to_complete: true
```

Accepted emitter refs primary key = artifact ID. Family rules primary tuple `(source_health_emitter_contract.artifact_id,source_kind)`. Status/reason mappings primary tuple `(status,reason_code)`. Coverage mappings primary key=`failure_domain`. Universal SET tie-break applies. Unknown/unrecognized status/reason maps to `unknown`. No V1 rule may create `covered_delayed`.

### C.3.16 SnapshotExecutionPolicy

Exact payload:

```text
snapshot_execution_policy_version: Int32Positive
max_read_transaction_duration_ms: PositiveInt64
sqlite_busy_timeout_ms: NonNegativeInt64
max_retry_count: NonNegativeInt64
process_memory_guard_bytes: PositiveInt64
```

These fields are operational only and MUST NOT enter EvidenceSnapshotContent or pure request identity.

### C.3.17 ClassificationTaxonomy

Exact payload:

```text
taxonomy_version: NonEmptyString
platform_family_values: SET<enum{android,ios,windows,macos,chromeos,linux}>
device_class_values: SET<enum{smartphone,tablet,laptop}>
manufacturer_records: SET<ManufacturerRecord>
model_family_records: SET<ModelFamilyRecord>
recognized_out_of_scope_dimensions: SET<enum{platform_family,device_class}>
```

`ManufacturerRecord` exactly `{manufacturer_id:NonEmptyString, display_label:NonEmptyString}` primary key=`manufacturer_id`.
`ModelFamilyRecord` exactly `{model_family_id:NonEmptyString, manufacturer_id:Nullable<NonEmptyString>, display_label:NonEmptyString}` primary key=`model_family_id`.
Exact taxonomy semantics remain §95-§97; `ios` includes iPadOS family in V1.

### C.3.18 AliasMapping

Exact payload:

```text
alias_mapping_version: NonEmptyString
manufacturer_aliases: SET<ManufacturerAlias>
model_aliases: SET<ModelAlias>
source_taxonomy_mappings: SET<SourceTaxonomyMapping>
```

`ManufacturerAlias` exactly `{source_id:NonEmptyString, source_value:NonEmptyString, manufacturer_id:NonEmptyString}` primary tuple `(source_id,source_value)`.
`ModelAlias` exactly `{source_id:NonEmptyString, source_value:NonEmptyString, model_family_id:NonEmptyString}` primary tuple `(source_id,source_value)`.
`SourceTaxonomyMapping` exactly `{source_id:NonEmptyString, dimension_name:enum{platform_family,device_class,manufacturer_family,model_family}, source_taxon:NonEmptyString, mapping_kind:enum{CANONICAL_VALUE,BROAD_UNRESOLVED,RECOGNIZED_OUT_OF_SCOPE,UNMAPPED}, target_id_or_ref:Nullable<NonEmptyString>}` primary tuple `(source_id,dimension_name,source_taxon)`.

### C.3.19 K3PortalRuleSet

Exact payload:

```text
k3_rule_set_version: NonEmptyString
portal_schema_family: "portal_headers"
admitted_feature_schema_versions: SET<int[1..2147483647]>
rules: SET<K3Rule>
test_vectors: SET<K3TestVector>
```

`K3Rule` exactly:

```text
rule_id: NonEmptyString
dimension_name: enum{platform_family,device_class,manufacturer_family,model_family}
input_predicates: SET<K3Predicate>
outcome_kind: enum{CANONICAL_VALUE,BROAD_UNRESOLVED,RECOGNIZED_OUT_OF_SCOPE,NO_CLAIM}
outcome_id_or_ref: Nullable<NonEmptyString>
claim_derivation: enum{declared,deterministic_mapping}
base_claim_strength: enum{strong,supporting}
explanation_code: NonEmptyString
```

`K3PredicateScalar` exactly `string | int[-9223372036854775808..9223372036854775807] | bool`.

`K3Predicate` exactly `{field_name:NonEmptyString, operator:enum{EQ,IS_TRUE,IS_FALSE,IS_NULL,IS_NOT_NULL,IN}, value:Nullable<K3PredicateScalar>, values:SET<K3PredicateScalar>}` with `value` used only for EQ and `values` only for IN.

`K3NormalizedScalar` exactly `string | int[-9223372036854775808..9223372036854775807] | bool | null`.

`K3NormalizedValue` exactly `K3NormalizedScalar | SEQUENCE<K3NormalizedScalar>`; nested arrays/objects are forbidden in schema version 1.

`K3TestVector` exactly `{test_vector_id:NonEmptyString, feature_schema_version:Int32Positive, normalized_input:MAP<NonEmptyString,K3NormalizedValue>, expected_rule_ids:SET<NonEmptyString>, expected_dimension_outcomes:MAP<DimensionName,Nullable<NonEmptyString>>}`.

No raw UA/CH/header field exists in this schema.

### C.3.20 SourceGovernanceRecord

Exact payload preserves every frozen §78 semantic field and adds only the schema-only contract version:

```text
governance_contract_version: Int32Positive
source_name: NonEmptyString
source_provenance: NonEmptyString
license_identifier: NonEmptyString
license_source_reference: NonEmptyString
license_text_sha256: Nullable<Sha256>
local_storage_status: enum{NOT_STORED,STORED_LOCAL,STORED_BUNDLED}
modification_import_status: enum{UNMODIFIED_SOURCE,IMPORTED_NORMALIZED,MODIFIED_WITH_PERMISSION,NOT_ADMITTED}
redistribution_status: enum{ALLOWED,RESTRICTED,PROHIBITED,NOT_APPLICABLE,UNKNOWN_NOT_ADMITTED}
attribution_requirement: enum{REQUIRED,NOT_REQUIRED,UNKNOWN_NOT_ADMITTED}
commercial_use_status: enum{ALLOWED,RESTRICTED,PROHIBITED,NOT_APPLICABLE,UNKNOWN_NOT_ADMITTED}
review_basis_semantics: NonEmptyString
unresolved_restrictions: SET<NonEmptyString>
```

`unresolved_restrictions` is a SET with primary key = normalized string and §9.3 tie-break; byte-identical duplicates fail.

Cross-field invariants:

```text
license_text_sha256 = non-null
IFF locally retained/bundled license text exists for this governance record

each material UNKNOWN_NOT_ADMITTED or unresolved restriction that prevents legal/governance admission
→ source is NOT ADMITTED
```

Reviewer/decision IDs are audit lineage and are NOT semantic fields.

This C.3 schema does not replace or weaken a §78 semantic field.

---

### C.3.21 KnowledgeProvenanceManifest

Exact tagged-union payload preserves the complete frozen §79 union.

Common fields:

```text
provenance_contract_version: Int32Positive
provenance_kind: enum{external,internal}
```

If `provenance_kind = external`, additional fields are EXACTLY:

```text
source_artifact_sha256: Sha256
source_governance_record: ArtifactRef<SourceGovernanceRecord>
retrieved_at_utc: UtcMs
source_provider_version_metadata: NonEmptyString
knowledge_freshness_policy: ArtifactRef<KnowledgeFreshnessPolicy>
importer_identity: NonEmptyString
importer_version: NonEmptyString
```

If `provenance_kind = internal`, additional fields are EXACTLY:

```text
rule_set_artifact: AnyArtifactRef
repository_commit_sha: Nullable<GitSha>
repository_tree_sha: Nullable<GitSha>
source_artifact_identity: Nullable<Sha256>
input_schema_compatibility: SET<SchemaCompatibilityRef>
taxonomy_compatibility: ArtifactRef<ClassificationTaxonomy>
rule_set_version: NonEmptyString
```

`SchemaCompatibilityRef` exactly:

```text
source_kind: NonEmptyString
feature_schema_version: Int32Positive
```

`input_schema_compatibility` is a SET primary tuple `(source_kind,feature_schema_version)` plus §9.3 tie-break.

Internal provenance XOR invariant:

```text
(repository_commit_sha != null AND repository_tree_sha != null)
XOR
(source_artifact_identity != null)
```

External-only fields are forbidden for internal and internal-only fields are forbidden for external.

Internal provenance has no fabricated external `retrieved_at_utc`, license fields or KnowledgeFreshnessPolicy.

Human review/decision identities remain audit lineage, not semantic provenance fields.

---

### C.3.22 CanonicalKnowledgeRecordSet

Exact top-level payload is §12.3. There is ONE universal ArtifactContent identity only.

`records` element is a tagged union by `knowledge_slot`:

#### K1 record

```text
record_type: "K1_DHCP"
canonical_record_id: NonEmptyString
dhcp_match_attributes: DhcpV1MatchAttributes
candidate_taxonomy_refs: SET<K1CandidateTaxonRef>
source_record_identity: NonEmptyString
```

`DhcpV1MatchAttributes` exactly:

```text
message_type: enum{discover,request,inform,decline,release}
parameter_request_list: SEQUENCE<int[0..255]> length 0..64
option_order: SEQUENCE<int[0..255]> length 0..64
vendor_class: Nullable<PrintableAscii1To128>
client_identifier_kind: enum{absent,mac,opaque}
maximum_message_size: Nullable<int[576..65535]>
rapid_commit_requested: bool
capport_requested: bool
ipv6_only_preferred_requested: bool
hostname_present: bool
```

`parameter_request_list` and `option_order` are SEQUENCE because order carries source semantics. This is the exact current `dhcp/1` normalized payload shape.

`K1CandidateTaxonRef` exactly `{dimension_name:enum{platform_family,device_class,manufacturer_family,model_family}, outcome_kind:enum{CANONICAL_VALUE,BROAD_UNRESOLVED,RECOGNIZED_OUT_OF_SCOPE,UNMAPPED}, value_or_ref:Nullable<NonEmptyString>, base_claim_strength:enum{strong,supporting}}`.

No MAC/OUI/UA/TCP/TLS/QUIC attribute is permitted in `dhcp_match_attributes`.

#### K2B record

```text
record_type: "K2B_TCP"
canonical_record_id: NonEmptyString
p0f_compatible_rule_identity: NonEmptyString
canonical_match_rule: NonEmptyString
dimension_claims: SET<K2BClaim>
source_character: enum{current,legacy}
source_record_identity: NonEmptyString
```

`K2BClaim` exactly `{dimension_name:enum{platform_family,device_class,manufacturer_family,model_family}, outcome_kind:enum{CANONICAL_VALUE,BROAD_UNRESOLVED,RECOGNIZED_OUT_OF_SCOPE,UNMAPPED}, value_or_ref:Nullable<NonEmptyString>, base_claim_strength:enum{strong,supporting}}`. Legacy record claims remain capped by §89.

#### K4 record

```text
record_type: "K4_IEEE_ASSIGNMENT"
canonical_record_id: NonEmptyString
prefix_hex: NonEmptyString
prefix_length_bits: enum{24,28,36}
assignment_org_id: NonEmptyString
assignment_org_label: NonEmptyString
registry_family: enum{MA-L,MA-M,MA-S}
source_record_identity: NonEmptyString
manufacturer_mapping: Nullable<K4ManufacturerMapping>
```

`K4ManufacturerMapping` exactly `{manufacturer_id:NonEmptyString, mapping_version:NonEmptyString, review_basis:NonEmptyString, base_claim_strength:enum{strong,supporting}}`.

Record SET primary tuple `(record_type,canonical_record_id)`. A set may contain only the record variant matching its `knowledge_slot`.

### C.3.23 ClassificationPolicy

Exact top-level semantic payload preserves §111 fields but encodes §§101–110 as closed machine data with no free condition/outcome parser:

```text
policy_schema_version: Int32Positive
classification_taxonomy: ArtifactRef<ClassificationTaxonomy>
alias_mapping: ArtifactRef<AliasMapping>
evidence_adapter_contract_set: ArtifactRef<EvidenceAdapterContractSet>
claim_derivation_semantics: MAP<ClaimDerivation,literal "PROVENANCE_ONLY_NO_AUTHORITY_ORDER">
claim_strength_semantics: MAP<ClaimStrength,int[1..2]>
same_origin_ambiguity_conflict_rules: SET<SameOriginAmbiguityRule>
same_origin_conflict_strength_rules: SET<SameOriginConflictRule>
cross_origin_fusion_matrix: SET<CrossOriginFusionCell>
support_level_rules: SEQUENCE<SupportLevelRule>
dimension_result_rules: SEQUENCE<DimensionStatusRule>
recognized_out_of_scope_applicability: SET<DimensionName>
global_status_derivation: SEQUENCE<GlobalStatusRule>
knowledge_freshness_policy_execution_semantics: FreshnessExecutionSemantics
```

Exact fixed maps:

```text
claim_derivation_semantics keys =
{declared,deterministic_mapping,fingerprint_match,registry_mapping}

Every claim_derivation_semantics key maps exactly to literal `PROVENANCE_ONLY_NO_AUTHORITY_ORDER`; derivation carries no authority ordering.

claim_strength_semantics =
{supporting:1, strong:2}
```

`SameOriginAmbiguityRule` exact schema:

```text
rule: enum{COMPATIBLE_CANDIDATE_VARIATION}
projection_mode: enum{PER_DIMENSION}
compatible_multi_candidate_outcome: enum{AMBIGUOUS_NOT_CONFLICT}
```

Schema V1 requires exactly one such row.

`SameOriginConflictRule` exact schema:

```text
left_strength: ClaimStrength
right_strength: ClaimStrength
compatibility: enum{SAME,INCOMPATIBLE}
outcome: enum{
  RESOLVED_STRONG,
  RESOLVED_SUPPORTING,
  CONFLICT_STRONG,
  CONFLICT_SUPPORTING,
  RESOLVED_STRONG_WITH_SUPPORTING_CONTRADICTION
}
```

SET primary tuple `(left_strength,right_strength,compatibility)`; symmetric pair semantics are canonicalized by strength rank so `(strong,supporting)` is stored, never duplicate `(supporting,strong)`.

Required cells encode §103 exactly:

```text
strong,strong,SAME -> RESOLVED_STRONG
strong,strong,INCOMPATIBLE -> CONFLICT_STRONG
strong,supporting,SAME -> RESOLVED_STRONG
strong,supporting,INCOMPATIBLE -> RESOLVED_STRONG_WITH_SUPPORTING_CONTRADICTION
supporting,supporting,SAME -> RESOLVED_SUPPORTING
supporting,supporting,INCOMPATIBLE -> CONFLICT_SUPPORTING
```

`CrossOriginFusionCell` exact schema:

```text
strong_clean_present: bool
strong_clean_disagree: bool
strong_internal_conflict_present: bool
supporting_clean_present: bool
supporting_clean_disagree: bool
supporting_internal_conflict_present: bool
outcome: enum{
  SELECT_STRONG,
  SELECT_SUPPORTING,
  CONFLICTING_EVIDENCE,
  NO_CONCRETE_SELECTION
}
record_supporting_contradiction: bool
support_cap: enum{NONE,MEDIUM}
```

The complete SET is the truth table for §105; missing or duplicate input tuple is validation failure.

`SupportLevelRule` exact schema:

```text
rule_order: int[1..4]
condition: enum{
  HIGH_ALL_REQUIREMENTS,
  MEDIUM_STRONG_NO_DECISIVE_CONFLICT,
  LOW_SUPPORTING_ONLY_ALL_AGREE,
  NONE_UNRESOLVED
}
result: enum{high,medium,low,none}
```

Required SEQUENCE order is exactly the §107 precedence above. `HIGH_ALL_REQUIREMENTS` includes the frozen prohibition on ANY incompatible claim, same-origin lower-strength contradiction, supporting internal conflict or cross-origin contradiction.

`DimensionStatusRule` exact schema:

```text
precedence: int[1..6]
condition: enum{
  DECISIVE_CONFLICT,
  SELECTABLE_IN_SCOPE,
  SELECTABLE_OUT_OF_SCOPE_WHERE_ALLOWED,
  SEMANTIC_INFO_UNRESOLVED,
  SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE,
  NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH
}
result: enum{resolved,recognized_out_of_scope,unknown,insufficient_evidence,conflicting_evidence}
```

Required mappings are exactly §109:

```text
1 DECISIVE_CONFLICT -> conflicting_evidence
2 SELECTABLE_IN_SCOPE -> resolved
3 SELECTABLE_OUT_OF_SCOPE_WHERE_ALLOWED -> recognized_out_of_scope
4 SEMANTIC_INFO_UNRESOLVED -> insufficient_evidence
5 SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE -> unknown
6 NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH -> insufficient_evidence
```

`recognized_out_of_scope_applicability` MUST equal exactly `{platform_family,device_class}`.

`GlobalStatusRule` exact schema:

```text
precedence: int[1..6]
condition: enum{
  ANY_DIMENSION_CONFLICTING,
  ALL_FOUR_DIMENSIONS_RESOLVED,
  ANY_DIMENSION_RESOLVED,
  ANY_PLATFORM_OR_DEVICE_CLASS_OUT_OF_SCOPE,
  ANY_DIMENSION_INSUFFICIENT,
  OTHERWISE
}
result: enum{classified,partial,recognized_out_of_scope,unknown,insufficient_evidence,conflicting_evidence}
```

Required mappings are exactly §110:

```text
1 ANY_DIMENSION_CONFLICTING -> conflicting_evidence
2 ALL_FOUR_DIMENSIONS_RESOLVED -> classified
3 ANY_DIMENSION_RESOLVED -> partial
4 ANY_PLATFORM_OR_DEVICE_CLASS_OUT_OF_SCOPE -> recognized_out_of_scope
5 ANY_DIMENSION_INSUFFICIENT -> insufficient_evidence
6 OTHERWISE -> unknown
```

`FreshnessExecutionSemantics` exact schema:

```text
evaluation_time_source: enum{CLASSIFICATION_REQUEST_KNOWLEDGE_EVALUATION_AT_UTC}
negative_age_behavior: enum{REQUEST_FAIL}
policy_source: enum{KNOWLEDGE_PROVENANCE_REFERENCED_POLICY}
dimension_override_precedence: enum{MATCHING_DIMENSION_OVERRIDE_REPLACES_GENERAL_STATE_RULE}
strength_cap_mode: enum{MINIMUM_AUTHORITY}
expired_behavior: enum{NO_NEW_CLAIM}
```

No implementation-defined `condition_id`, `outcome_id`, DSL or prose parser exists in schema version 1. Two implementations consuming identical ClassificationPolicy ArtifactContent MUST derive identical policy behavior using only this closed typed representation plus the explicitly referenced KnowledgeFreshnessPolicy artifacts.

---

### C.3.24 ClassificationRetentionPolicy

Exact payload:

```text
retention_policy_version: Int32Positive
classification_history_retention_seconds: PositiveInt64
co_retain_snapshot_record: true
co_retain_request_result_evaluability_origin: true
privacy_storage_basis: NonEmptyString
expiry_behavior: "DELETE_CLASSIFICATION_WHEN_ELIGIBLE"
reference_aware_gc: true
```

The first production `classification_history_retention_seconds` value remains Owner-gated by F-F3; the schema/shape is fixed here.

### C.3.25 ProductValidationPolicy

Exact payload:

```text
product_validation_policy_version: Int32Positive
known_dimension_wrong_resolved_behavior: "FAIL"
false_out_of_scope_behavior: "FAIL"
android_required_platform: "android"
android_min_support: "medium"
windows_required_platform: "windows"
windows_min_support: "medium"
minimum_correct_device_class_count_across_controlled_devices: 1
device_class_min_support: "medium"
ground_truth_must_preexist_result: true
automatic_learning_forbidden: true
```

### C.3.26 ClassifierArtifactManifest

Exact payload:

```text
repository_commit_sha: GitSha
repository_tree_sha: GitSha
classification_engine_semver: NonEmptyString
artifact_canonical_json_version: NonEmptyString
evidence_canonical_json_compatibility_identity: NonEmptyString
pure_core_contract_version: NonEmptyString
classification_result_schema_version: Int32Positive
snapshot_contract_version: Int32Positive
adapter_implementation_identities: SET<AdapterImplementationIdentity>
k2a_matcher_implementation_version: NonEmptyString
build_package_digest: Nullable<Sha256>
```

`AdapterImplementationIdentity` exactly `{source_kind:NonEmptyString, feature_schema_version:Int32Positive, implementation_id:NonEmptyString, implementation_digest:Nullable<Sha256>, mode:enum{FUSION,NON_FUSION_HANDLER,OPTIONAL_IF_ADMITTED}}` primary tuple `(source_kind,feature_schema_version)`.
Mandatory entries exactly cover the adapters/non-fusion handlers enumerated in §115; portal_headers/2 entry appears only if admitted.

### C.3.27 EvidenceSnapshotContent

Exact payload:

```text
snapshot_contract_version: Int32Positive
site_id: SiteId
observed_mac: Mac48
window_start_utc: UtcMs
window_end_utc: UtcMs
database_generation_id: NonEmptyString
max_committed_ingest_sequence: int[0..9223372036854775807]
evidence_source_binding_timeline: ArtifactRef<EvidenceSourceBindingTimeline>
binding_clock_policy: ArtifactRef<BindingClockPolicy>
evidence_schema_registry_contract: ArtifactRef<EvidenceSchemaRegistryContract>
origin_runtime_admission: OriginRuntimeAdmissionDescriptor
classification_foundation_valid_from_utc: UtcMs
binding_epoch_descriptors: SET<BindingEpochDescriptor>
evidence_descriptors: SEQUENCE<EvidenceDescriptor>
source_health_descriptors: SEQUENCE<SourceHealthDescriptor>
```

`OriginRuntimeAdmissionDescriptor` exactly `{artifact_id:ArtifactId, content_sha256:Sha256, tcp_state:enum{ENABLED,DISABLED}, tcp_reason_code:enum{TTL_PROOF_VALID,TTL_PROOF_INVALID,PROFILE_POLICY_DISABLED}, ttl_capture_placement_proof:Nullable<ArtifactRef<TTLCapturePlacementProof>>}` and MUST exactly equal the referenced OriginRuntimeAdmission semantics.
`BindingEpochDescriptor` exactly mirrors the authorized §39 BindingEpoch fields plus bound emitter ArtifactRef.
`EvidenceDescriptor` exact fields are §29.
`SourceHealthDescriptor` exact fields are §30.
Ordering is exactly §34. `SnapshotExecutionPolicy` and FoundationRuntimeProfile ID are NOT semantic payload fields.

### C.3.28 SnapshotRecord

Exact payload:

```text
evidence_snapshot_content: ArtifactRef<EvidenceSnapshotContent>
foundation_runtime_profile: ArtifactRef<FoundationRuntimeProfile>
snapshot_captured_at_utc: UtcMs
snapshot_content_policy: ArtifactRef<SnapshotContentPolicy>
snapshot_execution_policy: ArtifactRef<SnapshotExecutionPolicy>
verified_evidence_row_count: NonNegativeInt64
verified_payload_bytes: NonNegativeInt64
materialized_evidence_row_count: NonNegativeInt64
materialized_payload_bytes: NonNegativeInt64
total_semantic_input_bytes: NonNegativeInt64
scope_anomaly_count: NonNegativeInt64
scope_anomaly_reason_counts: SET<ScopeAnomalyReasonCount>
build_outcome: "success"
```

`ScopeAnomalyReasonCount` exactly `{reason_code:NonEmptyString, count:PositiveInt64}` primary key=`reason_code`. `scope_anomaly_count` MUST equal the sum of all reason-count values.
Equality invariants with FoundationRuntimeProfile policies are §27 and the R12 duplicate-reference invariant.

### C.3.29 SourceEvaluability

Top-level exact fields are §54. `source_entries` element exactly:

```text
origin_group: enum{dhcp,portal,tcp,tls,quic}
source_kind: NonEmptyString
binding_epoch_id: NonEmptyString
producer_id: NonEmptyString
capture_source_id: NonEmptyString
aggregate_evaluability_state: enum{evaluable,partially_evaluable,not_evaluable,unknown}
coverage_intervals: SEQUENCE<CoverageInterval>
explanation_codes: SET<NonEmptyString>
```

`CoverageInterval` exactly `{start_utc:UtcMs,end_utc:UtcMs,coverage_class:enum{covered_available,acquisition_unavailable,delivery_unavailable_loss_possible,delivery_loss_confirmed,unsupported,unknown},reason_classification:NonEmptyString,reason_code_refs:SET<NonEmptyString>}`. Intervals are normalized, non-overlapping, half-open and ordered exactly by §53; adjacent equal intervals merge.

### C.3.30 OriginAssessment

Top-level exact payload:

```text
origin_assessment_contract_version: Int32Positive
evidence_snapshot_content: ArtifactRef<EvidenceSnapshotContent>
source_evaluability: ArtifactRef<SourceEvaluability>
origin_group: enum{dhcp,portal,tcp,tls,quic,mac_registry}
dimension_assessments: SET<OriginDimensionAssessment>
evidence_refs: SET<EvidenceRef>
knowledge_refs: SET<KnowledgeRef>
explanation_codes: SET<NonEmptyString>
```

For `mac_registry`, the overall SourceEvaluability artifact ref remains required even though no mac_registry source entry exists, exactly as frozen in §101.1.

`OriginDimensionAssessment`, `CandidateEntry`, `SameOriginContradictionRecord`, `EvidenceRef`, `KnowledgeRef`, `BroadUnresolvedRef` are EXACT §101 closed schemas. Dimension-assessment SET primary key=`dimension_name`; other SET keys are §101/C.1.

### C.3.31 ClassificationResult

Exact payload fields are §117 with nested `DimensionResult` EXACT §108 and `OriginAssessment` refs SET primary key=`artifact_id`.

### C.3.32 ControlledValidationGroundTruthRecord

Exact payload:

```text
validation_run_id: UuidV4
site_id: SiteId
controlled_device_lab_label: NonEmptyString
observed_mac: Mac48
window_start_utc: UtcMs
window_end_utc: UtcMs
platform_family_ground_truth: enum{android,ios,windows,macos,chromeos,linux}|NonEmptyString
device_class_ground_truth: Nullable<enum{smartphone,tablet,laptop}|NonEmptyString>
manufacturer_id_ground_truth: Nullable<NonEmptyString>
model_family_id_ground_truth: Nullable<NonEmptyString>
ground_truth_method: enum{OWNER_CONTROLLED_DEVICE,PHYSICAL_DEVICE_INSPECTION,OS_DEVICE_SETTINGS,INDEPENDENT_ASSET_RECORD}
recorded_at_utc: UtcMs
```

`recorded_at_utc` MUST precede result visibility. Manufacturer/model fields may be non-null only when independently verified by the declared method. No personal identity field exists.

### C.3.33 ProductValidationComparisonRecord

Exact payload:

```text
validation_run_id: UuidV4
ground_truth_record: ArtifactRef<ControlledValidationGroundTruthRecord>
classification_request: ArtifactRef<ClassificationRequestManifest>
classification_result: ArtifactRef<ClassificationResult>
per_dimension_outcomes: SET<ValidationDimensionOutcome>
overall_validation_outcome: enum{PASS,FAIL}
```

`ValidationDimensionOutcome` exactly `{dimension_name:enum{platform_family,device_class,manufacturer_family,model_family}, ground_truth_known:bool, expected_value_or_ref:Nullable<NonEmptyString>, actual_status:enum{resolved,recognized_out_of_scope,unknown,insufficient_evidence,conflicting_evidence}, actual_value_or_ref:Nullable<NonEmptyString>, support_level:enum{none,low,medium,high}, comparison_outcome:enum{PASS,FAIL,NOT_APPLICABLE}}` primary key=`dimension_name`.

### C.3.34 GateResultManifest

Exact top-level/nested schema is §123. `input_artifact_refs` and `output_artifact_refs` use exact `ArtifactRef`; `retained_evidence_refs` use C.3.2 `RetainedEvidenceRef`; `proof_execution_identity` uses C.3.2 `ProofExecutionIdentity`; `decision_record_refs` is SET<DecisionRecord ID string>. No other nested fields are allowed.

### C.3.35 GateProofArtifact

Exact payload:

```text
proof_kind: enum{SNAPSHOT_CONCURRENCY,SNAPSHOT_PERFORMANCE,RUNTIME_PROFILE_ATOMICITY,SNAPSHOT_MATERIALIZATION_EXECUTION,SOURCE_EVALUABILITY_EXECUTION,ORIGIN_ASSESSMENT_EXECUTION,FUSION_EXECUTION,REQUEST_ASSEMBLY_DETERMINISM,CLASSIFICATION_AUDIT_PERSISTENCE,OFFLINE_FAILURE_ISOLATION,TASK04_PRODUCT_VALIDATION,ARTIFACT_GRAPH_ACYCLICITY,CLASSIFICATION_PROFILE_COMPATIBILITY}
source_gate_id: NonEmptyString
candidate_repository_commit_sha: Nullable<GitSha>
candidate_repository_tree_sha: Nullable<GitSha>
input_artifact_refs: SET<AnyArtifactRef>
procedure_or_test_suite_id: NonEmptyString
proof_execution_identity: ProofExecutionIdentity
canonical_result_summary: NonEmptyString
retained_evidence_refs: SET<RetainedEvidenceRef>
```

No implementation-defined `proof_kind` in schema version 1.

### C.3.36 K2AConformancePackage

Exact payload:

```text
p0f_implementation_identity: NonEmptyString
p0f_implementation_digest: Sha256
p0f_reference_corpus_identity: NonEmptyString
p0f_reference_corpus_digest: Sha256
supported_request_scope: NonEmptyString
p0f_runtime_serializer_contract_version: NonEmptyString
matcher_implementation_contract_version: NonEmptyString
conformance_fixture_refs: SET<ConformanceFixtureRef>
conformance_status: "PASS"
```

`ConformanceFixtureRef` exactly `{fixture_set_id:NonEmptyString, fixture_set_digest:Sha256}` primary key=`fixture_set_id`.

### C.3.37 TTLCapturePlacementProof

Exact payload:

```text
capture_topology_identity: NonEmptyString
running_config_evidence_sha256: Sha256
source_interface_vlan_identity: NonEmptyString
direction: enum{INGRESS,EGRESS,BOTH,EXACT_MIRROR_CONTRACT}
controlled_packet_proof_records: SET<TTLPacketProof>
proven_distance_semantics: NonEmptyString
proof_valid_for_topology_identity: NonEmptyString
```

`TTLPacketProof` exactly:

```text
packet_proof_id: NonEmptyString
sender_original_ttl: int[0..255]
sensor_observed_ttl: int[0..255]
correlated_packet_identity: NonEmptyString
correlated_packet_digest: Sha256
```

Primary key=`packet_proof_id`. `proof_valid_for_topology_identity` MUST equal `capture_topology_identity`.

### C.3.38 RuntimeProfileActivationRecord

Exact payload:

```text
activation_contract_version: Int32Positive
activation_record_id: UuidV4
profile_kind: enum{foundation,classification}
runtime_profile_id: ArtifactId
runtime_profile_digest: Sha256
runtime_profile_admission_manifest_id: ArtifactId
runtime_profile_admission_manifest_digest: Sha256
previous_activation_record_id: Nullable<UuidV4>
previous_active_profile_id: Nullable<ArtifactId>
previous_active_profile_digest: Nullable<Sha256>
activated_at_utc: UtcMs
activation_reason_update_class: enum{
  INITIAL_FOUNDATION,
  INITIAL_CLASSIFICATION,
  KNOWLEDGE_BUNDLE_REFRESH,
  KNOWLEDGE_FRESHNESS_POLICY_CHANGE,
  BINDING_TIMELINE_CHANGE,
  CAPTURE_TOPOLOGY_CHANGE,
  SOURCE_HEALTH_EMITTER_CHANGE,
  SOURCE_HEALTH_POLICY_CHANGE,
  SNAPSHOT_CONTENT_POLICY_CHANGE,
  SNAPSHOT_EXECUTION_POLICY_CHANGE,
  EVIDENCE_SCHEMA_CHANGE,
  EVIDENCE_ADAPTER_CHANGE,
  EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE,
  CLASSIFICATION_POLICY_CHANGE,
  CLASSIFIER_ARTIFACT_CHANGE,
  FOUNDATION_VALID_FROM_LATER,
  ROLLBACK_REACTIVATION
}
activation_result: literal "ACTIVE"
activation_generation_id: UuidV4
```

Reference invariants:

```text
runtime_profile_id artifact_type matches profile_kind
runtime_profile_admission_manifest_id artifact_type = RuntimeProfileAdmissionManifest
runtime_profile_admission_manifest.candidate_profile_id/digest == runtime_profile_id/digest
previous_active_profile_id null IFF previous_active_profile_digest null
previous_activation_record_id refers to an already-existing older activation-record UUID when non-null
```

`activation_record_id`, `activation_generation_id`, and `previous_activation_record_id` are separate UUID record identities, never ArtifactId aliases.

---

### C.3.39 RuntimeProfileValidityRecord

Exact payload:

```text
runtime_profile_validity_contract_version: Int32Positive
validity_record_id: UuidV4
profile_kind: enum{foundation,classification}
runtime_profile_id: ArtifactId
runtime_profile_digest: Sha256
activation_record_id: UuidV4
state: enum{ACTIVE,INACTIVE,SUSPENDED_INVALIDATED}
reason_code: enum{
  ACTIVATED,
  SUPERSEDED_SAFE,
  ROLLBACK_REACTIVATED,
  TTL_CAPTURE_PROOF_INVALIDATED,
  EXPLICIT_POLICY_SUSPEND,
  PROFILE_COMPATIBILITY_INVALIDATED
}
effective_at_utc: UtcMs
inflight_commit_rule: enum{ALLOW_PINNED_INFLIGHT,REJECT_PINNED_INFLIGHT}
previous_validity_record_id: Nullable<UuidV4>
```

Cross-field state/reason/inflight invariants are exactly §11.5.3.

`validity_record_id` and `previous_validity_record_id` are separate UUID record identities, not ArtifactId values.

`activation_record_id` MUST resolve an existing RuntimeProfileActivationRecord with matching `profile_kind` and `runtime_profile_id/digest`.

The canonical current validity state is selected ONLY through the CAS-protected control-plane validity-head mapping for `activation_record_id`; timestamp/UUID/storage order is never selection authority.

---

### C.3.40 Closed-world registry completeness invariant

The following three sets MUST be exactly equal, with no duplicate type:

```text
§12 Semantic ArtifactContentTypes
==
Appendix C ArtifactContentTypes
==
C.3 RegistryTypes
```

For every registry type, the owning C.3 entry MUST provide either:

```text
an executable closed-world schema inline
```

or:

```text
an exact normative section reference whose field set, nested types, enums, nullability,
collection class/order and cross-field invariants are complete and closed-world
```

A catalog type with no C.3 entry/reference, a C.3 type absent from either catalog, duplicate type entry, undefined nested semantic type, or undeclared semantic field is architecture validation failure.

`ArtifactRef<T>` target T MUST exist in this same registry. `AnyArtifactRef` target artifact_type MUST be a member of this same registry.

Schema-token validation for R12 requires:

```text
0 undefined type aliases
0 unbounded placeholder type tokens
0 untyped sequence tokens
0 prose-only nullable grammar
0 untyped reference target
0 undefined nested object
```

Frozen semantic field coverage validation requires, for every pre-R11 ArtifactContent:

```text
FrozenSemanticFields(type) SUBSET OF C3SemanticFields(type)
```

Loss of a frozen semantic field is validation failure.

---

# APPENDIX D — Foundation gate dependency graph

# APPENDIX D — Foundation gate dependency graph

Gate INPUT dependencies and ArtifactContent construction dependencies are distinct; both MUST be acyclic.

Normative consistency rule:

```text
Every gate INPUT dependency MUST appear as an Appendix-D edge.
Every Appendix-D edge MUST be justified by a gate INPUT/contract dependency.
Every WHAT NEXT claim MUST be the reverse statement of a real downstream INPUT/contract dependency.
0 invented edges. 0 missing edges. 0 contradictory dependency statements.
```

```text
ArchitectureContractReference(R12 FINAL)
        |
        +--> F-A1 Task-01 v1→v2 migration/watermark
        |       +--> F-A2 sequence/duplicate/generation recovery
        |       +--> F-A3 one-read-transaction concurrency
        |       +--> F-A4 (Task-01 v2 input)
        |
        +--> F-C1 tcp_syn/2 final TcpSynV2SchemaContract
        |       +--> F-C2 K2AConformancePackage
        |       |       +--> F-E2 K2B source admission
        |       +--> F-A5 FINAL EvidenceSchemaRegistryContract
        |
        +--> F-D1 PortalHeadersV2SchemaContract
        |       OR CapabilityDisposition(NOT_ADMITTED,
        |            fallback_source_kind=portal_headers,
        |            fallback_feature_schema_version=1)
        |       +--> F-A5 FINAL EvidenceSchemaRegistryContract
        |
        +--> F-E6 ClassificationTaxonomy + AliasMapping
        |       +--> F-E3 K3 rule admission
        |       +--> F-E7 KnowledgeBundle
        |       +--> F-F2 ClassificationPolicy
        |
        +--> F-A5 FINAL EvidenceSchemaRegistryContract
        |       +--> F-A4 sizing/query/WAL/materialization
        |       |       +--> SnapshotContentPolicy
        |       |       +--> SnapshotExecutionPolicy
        |       +--> F-E3 K3 internal portal rule admission
        |       +--> F-F1 EvidenceAdapterContractSet
        |
        +--> F-B0 SourceHealthEmitterContracts
        |       +--> F-B1 BindingTimeline + BindingClockPolicy + valid-from
        |               +--> F-B2 SourceHealthPolicy + portal idle heartbeat
        |                       +--> F-B3 Task01HealthRetentionContract
        |
        +--> F-E1 K1 CanonicalKnowledgeRecordSet + provenance
        |       +--> F-E5 external governance/freshness
        |       +--> F-E7 KnowledgeBundle
        |       +--> F-F1 EvidenceAdapterContractSet
        |
        +--> F-E2 K2B CanonicalKnowledgeRecordSet + provenance
        |       +--> F-E5 external governance/freshness
        |       +--> F-E7 KnowledgeBundle
        |
        +--> F-E3 K3PortalRuleSet + internal provenance
        |       +--> F-E7 KnowledgeBundle
        |       +--> F-F1 EvidenceAdapterContractSet
        |
        +--> F-E4 K4 CanonicalKnowledgeRecordSet + provenance
        |       +--> F-E5 external governance/freshness
        |       +--> F-E7 KnowledgeBundle
        |
        +--> F-E5 SourceGovernanceRecord + KnowledgeFreshnessPolicy
        |       + KnowledgeProvenanceManifest completion
        |       +--> F-E7 KnowledgeBundle
        |       +--> F-ADMIT final freshness re-evaluation
        |
        +--> [F-A5 + F-C2 + F-E1 + F-E3 + CapabilityDisposition]
        |       +--> F-F1 EvidenceAdapterContractSet
        |               +--> F-F2 ClassificationPolicy
        |
        +--> F-F3 ClassificationRetentionPolicy
        +--> F-F4 ProductValidationPolicy
        +--> F-F5 crash-atomic runtime-profile/validity-head mechanism proof
        |
        +--> ALL Foundation ArtifactContent candidates/templates
                +--> F-F6 ArtifactContent dependency-graph acyclicity

MANDATORY INITIAL F-ADMIT additionally consumes:
F-C3 TTLCapturePlacementProof PASS
F-A1/F-A2/F-A3/F-A4/F-A5
F-B0/F-B1/F-B2/F-B3
F-C1/F-C2/F-C3
F-D1 disposition
F-E1/F-E2/F-E3/F-E4/F-E5/F-E6/F-E7
F-F1/F-F2/F-F3/F-F4/F-F5/F-F6
        |
        v
F-ADMIT exact order:
1 foundation_admission_evaluation_at_utc
2 final mandatory external freshness re-evaluation
3 OriginRuntimeAdmission(tcp=ENABLED, TTL_PROOF_VALID)
4 FoundationAdmissionManifest
5 FoundationRuntimeProfile
6 Foundation RuntimeProfileAdmissionManifest(INITIAL_FOUNDATION)
7 Owner DecisionRecord
8 precompute Foundation ActivationRecord + initial ACTIVE ValidityRecord
9 ONE crash-atomic control-plane transaction publishes activation/head/pointer
10 final F-ADMIT GateResultManifest
        |
        v
TechLead11 may decompose Task-04
```

Exact normative INPUT edges:

```text
F-A2 <- F-A1
F-A3 <- F-A1 + F-A2
F-A5 <- F-C1 + F-D1 disposition
F-A4 <- F-A5 + F-A1 Task-01-v2 output
F-B1 <- F-B0
F-B2 <- F-B0 + F-B1
F-B3 <- F-B2
F-E2 <- F-C2
F-E3 <- F-A5 + F-E6
F-E5 <- F-E1 + F-E2 + F-E4 external source outputs
F-E7 <- F-E1 + F-E2 + F-E3 + F-E4 + F-E5 + F-E6
F-F1 <- F-A5 + F-C2 + F-E1 + F-E3 + F-D1 disposition
F-F2 <- F-E6 + F-F1
F-F5 <- runtime-profile fixture artifacts/control-plane mechanism
F-F6 <- all concrete ArtifactContent candidate/template dependency graphs
F-ADMIT <- all mandatory Foundation PASS artifacts listed above
```

WHAT-NEXT corrections are exact:

```text
F-A3 -> F-ADMIT + Task-04 snapshot implementation only; NOT F-A5
F-C2 -> F-E2 + F-F1 + ClassifierArtifactManifest construction; NOT F-C3
F-E7 -> F-ADMIT + Task-04 runtime knowledge input; NOT F-F2
```

Construction invariants:

```text
KnowledgeFreshnessPolicy -> no KnowledgeProvenanceManifest dependency
KnowledgeProvenanceManifest(external) -> KnowledgeFreshnessPolicy
OriginRuntimeAdmission exists before FoundationAdmissionManifest
FoundationAdmissionManifest exists before foundation RuntimeProfileAdmissionManifest
FoundationRuntimeProfile does not semantically reference FoundationAdmissionManifest
RuntimeProfileAdmissionManifest references prerequisite GateResults only
F-ADMIT GateResult references completed outputs; outputs do not reference F-ADMIT GateResult
```

No Foundation edge depends on Task-04 implementation output.

---

# APPENDIX E — Task-04 acceptance dependency graph

Normative consistency rule:

```text
Every T-gate INPUT dependency MUST appear as an Appendix-E edge.
Every Appendix-E edge MUST be justified by a T-gate INPUT/contract dependency.
Every WHAT NEXT claim MUST be the reverse statement of a real downstream INPUT/contract dependency.
0 invented edges. 0 missing edges. 0 contradictory dependency statements.
```

```text
FoundationAdmissionManifest
+
admitted FoundationRuntimeProfile
+
exact admitted foundation RuntimeProfileAdmissionManifest
+
accepted KnowledgeBundle / ClassificationPolicy / EvidenceAdapterContractSet
        |
        +--> T-01 snapshot/materialization execution
        +--> T-02 SourceEvaluability execution
        +--> T-03 OriginAssessment execution
        +--> T-04 fusion/status/support + TCP-disabled semantic vector
        |
        +--> T-06 exact ClassifierArtifactManifest
                |
                v
              T-06A construct/validate candidate ClassificationRuntimeProfile P
                |
                +--> T-05 RequestAssembly/pure determinism using EXACT P
                +--> T-07 isolated acceptance persistence/replay/GC using EXACT P
                +--> T-08 offline/failure isolation using exact implementation candidate + EXACT P
                +--> T-09 controlled product validation using EXACT P
                +--> T-ACCEPT exact-profile identity/admission check

T-01 PASS ----\
T-02 PASS -----\
T-03 PASS ------\
T-04 PASS -------\
T-05 PASS --------\
T-06 PASS ---------+--> T-ACCEPT
T-06A PASS --------/
T-07 PASS --------/
T-08 PASS -------/
T-09 PASS ------/
                         |
                         +--> verify every applicable tested profile digest == P
                         +--> NEW Task04AcceptanceManifest when semantic reacceptance required
                         +--> classification RuntimeProfileAdmissionManifest(applicable closed update_class,
                              exact foundation RPM lineage)
                         +--> Owner acceptance DecisionRecord
                         +--> final T-ACCEPT GateResultManifest
                         |
                         v
                 ACCEPTED / PRODUCTION-ELIGIBLE P
                         |
                         v
SEPARATE Owner-authorized production activation action
                         |
                         +--> current safety/compatibility recheck
                         +--> crash-atomic ActivationRecord + initial ACTIVE ValidityRecord + pointer transaction
```

For INITIAL Task-04 acceptance:

```text
update_class = INITIAL_CLASSIFICATION
NEW Task04AcceptanceManifest = REQUIRED
```

No bootstrap cycle exists:

```text
candidate ClassificationRuntimeProfile P exists before T-05/T-07/T-08/T-09
T-07 acceptance persistence CORE does not require future T-ACCEPT artifacts
Task04AcceptanceManifest exists only after prerequisite tests
P does NOT reference Task04AcceptanceManifest
RuntimeProfileAdmissionManifest is constructed only after P, required acceptance lineage,
and exact admitted foundation RuntimeProfileAdmissionManifest exist
T-ACCEPT does NOT activate production
```

Exact WHAT-NEXT correction:

```text
T-04 -> T-ACCEPT semantic evidence only; it does NOT feed T-06 as an INPUT
T-06 -> T-06A + T-ACCEPT identity evidence
T-06A -> T-05 + T-07 + T-08 + T-09 + T-ACCEPT
```

No pre-T-ACCEPT gate requires a T-ACCEPT output.

No T-gate is required before Task-04 decomposition.

T-ACCEPT concrete ArtifactContent graph MUST again be acyclic.

---

# APPENDIX F — No-silent-fallback / typed error matrix

| Condition | Required typed action | Forbidden fallback | Result class |
|---|---|---|---|
| Architecture not accepted | Keep PRE-TASK unauthorized | Treat draft as FINAL | Architecture HOLD |
| Foundation mandatory gate FAIL | Block F-ADMIT | Skip/prose-only PASS | Foundation HOLD |
| Artifact dependency cycle | `artifact_dependency_cycle`; reject candidate graph | Hash/build cyclic objects anyway | Admission FAIL |
| Gate output points to producing GateResult | Reject graph | Circular hash workaround | Admission FAIL |
| CapabilityDisposition points to producer gate | Reject artifact | Circular reference | Foundation FAIL |
| Mandatory K1/K2B/K3/K4 candidate fails | Select another concrete compliant source/rule set | Weaken requirements / placeholder | Foundation HOLD |
| Unknown material legal status | Source not admitted | Assume permitted | Knowledge admission FAIL |
| F-E5 trusted proof time absent/backdated | Gate FAIL | User/local arbitrary time | Knowledge policy proof FAIL |
| Mandatory source becomes unusable before F-ADMIT | Fail final admission freshness recheck | Reuse older F-E5 PASS | Foundation HOLD |
| `stale` policy behavior undefined | Source/policy not admitted | Coder chooses downgrade/eligibility | Knowledge admission FAIL |
| KnowledgeFreshnessPolicy changed without new provenance+bundle | Reject activation/profile | Policy-only runtime state | Profile admission FAIL |
| Task-01 migration validation FAIL | Writer stays stopped; repair/restore | Partial migration activation | Migration FAIL |
| Sequence exhausted | Stop ingest | Wrap/reuse | Fatal storage condition |
| Snapshot second connection/transaction | `SnapshotBuildError` | Approximate consistency | No result |
| Concurrent retention changes reader view | Gate FAIL | Continue | Snapshot consistency FAIL |
| Invalid/duplicate-key/canonical payload | `corrupt_payload` | Drop row/continue | No result |
| Payload hash mismatch | `payload_hash_mismatch` | Trust bytes/hash selectively | No result |
| Known-schema validation fail | `schema_validation_failure` | Treat as unsupported future schema | No result |
| Unknown intact schema | descriptor retained; EvidenceCompatibility `unsupported_schema`; no claim | Crash/drop/nearest parse | Safe no-claim; SourceEvaluability unchanged |
| Unknown-schema payload exceeds verified byte ceiling | `resource_limited` | Ignore bytes because unmaterialized | No result |
| Deterministic content ceiling | `resource_limited` | first-N classification | No result |
| SQLite busy | `retryable_sqlite_busy` | device unknown | Retryable no-result |
| Snapshot wall timeout | `snapshot_timeout` | semantic not_evaluable | Retryable no-result |
| Missing binding | `binding_unavailable` | infer source from rows | No result/window invalid |
| Cutover quarantine | `binding_cutover_ambiguous`; exclude row; coverage unknown | nearest epoch | Safe no-claim interval |
| Runtime profile mismatch | `runtime_profile_incompatible`; reject candidate/request | best effort set | No activation/result |
| Production commit with unadmitted ClassificationRuntimeProfile | `production_profile_not_admitted`; reject production commit | persist then invent acceptance IDs | No committed production result |
| T-07 pre-acceptance candidate profile | persist CORE in isolated acceptance DB; no future admission IDs | fake/null Task04Acceptance/RPM IDs | Acceptance proof only |
| Production classification reads Foundation active pointer after CRP pin | reject implementation | torn generation | RequestAssembly/Profile FAIL |
| New Foundation profile active while old Classification profile remains safe | production classification stays entirely on old CRP/old referenced FRP | mix new FRP into old CRP | Stable old generation |
| Old Classification profile becomes unsafe after TTL topology change | suspend unsafe classification until safe replacement CRP activates | keep old TCP proof | No unsafe result |
| Candidate profile digest changes after T-09 | T-ACCEPT FAIL | rebuild/activate different profile | Acceptance FAIL |
| Admission manifest constructed before candidate profile dependency exists | `artifact_dependency_cycle` / construction-order FAIL | forward/dangling candidate reference | Admission FAIL |
| Semantic Task-04 update reuses old Task04AcceptanceManifest | reject update class admission | implicit lineage reuse | Reacceptance FAIL |
| Rollback pointer rewound without ROLLBACK_REACTIVATION manifest | reject activation | unaudited pointer rewind | Activation FAIL |
| Operational profile/lineage only changes | semantic snapshot/request digest unchanged | contaminate pure digest | Determinism FAIL |
| Negative knowledge age | `negative_knowledge_age` | mark fresh | No result |
| KnowledgeBundle transient load fail | `knowledge_bundle_unavailable` | old unpinned bundle | Retryable no-result if proven transient |
| Classification DB unavailable | `persistence_unavailable` | claim committed result | No committed result |
| Classifier internal defect | `classifier_internal_error` | partial result | No result |
| Unknown health emitter/reason | coverage unknown | assume semantics | SourceEvaluability unknown |
| Transport recovers | actual backfilled rows usable; absence incomplete | infer covered_delayed | Conservative coverage |
| Present evidence + health unknown/outage | use compatible present row; record coverage | discard row | Claim + explanation |
| Missing evidence + outage | no claim | negative device claim | No negative evidence |
| `tcp_syn/1` | audit/non-fusion | approximate v2 | No TCP v1 claim |
| OriginRuntimeAdmission TCP disabled | audit tcp_syn rows; TCP no_claim/origin_runtime_disabled | p0f/K2B claim anyway | Other origins may continue |
| Initial F-ADMIT missing/failed F-C3 TTL proof | Foundation HOLD; TCP-disabled shortcut forbidden | initial admission with TCP disabled | No Foundation Admission |
| Invalid TTL proof/topology changed post-admission | suspend unsafe traffic; re-prove or admit disabled TCP profile/CRP | old proof reuse | TCP/classification stop until safe profile |
| JA4 without admitted reference | no TLS/QUIC semantic claim | local heuristic | No claim |
| Fingerbank Cloud attempted | block V1 scope path | submit production client data | Scope violation |
| K1 multiple candidates | preserve complete CandidateSet | first/best/popular | Per-dimension ambiguity/resolution |
| K1 provenance impure | exclude mapping | treat as DHCP-only | Knowledge non-admission |
| Strong internal conflict | decisive conflict | erase with other origin | conflicting_evidence |
| Supporting internal conflict + clean strong | strong may resolve, contradiction, cap medium | blanket conflict/ignore contradiction | Resolved capped |
| Any incompatible claim of any strength | HIGH forbidden | HIGH anyway | max medium/conflict |
| Expired knowledge source | suppress that source claims | old strength/service crash | degraded knowledge availability |
| Stale knowledge source | exact age_ms state + applicable policy eligibility/cap/explanation; cap can only preserve/reduce authority | implementation-chosen behavior / strength upgrade | Policy-defined claim/no-claim |
| Knowledge freshness age < 0 | `negative_knowledge_age`; fail request/admission evaluation | treat as fresh | No result/PASS |
| KnowledgeFreshnessPolicy↔Provenance dependency cycle | `artifact_dependency_cycle`; reject | mutual IDs | Admission FAIL |
| Live caller supplies knowledge time | reject/ignore; service captures | caller freshness control | RequestAssemblyError |
| Active CRP changes mid-request | stay on pinned old CRP and its FRP | reread/mix | Stable request |
| SourceHealthPolicy needs unavailable old history | block activation | reinterpret missing history | Profile admission FAIL |
| Later foundation valid-from earlier than lineage root | reject profile admission | retroactive authority | Profile admission FAIL |
| Snapshot materialization complete | dispose transient payload | persist copy in Classification DB | Privacy boundary |
| SnapshotRecord/profile/admission lineage not retrievable | persistence/audit FAIL | dangling ID | Audit failure |
| Validation truth not pre-recorded | validation run invalid | label after result | Product gate FAIL |
| Validation wrong resolved result | candidate FAIL; reviewed new artifact/version | auto-learn | Product gate FAIL |
| Always-unknown classifier | utility FAIL | safe PASS | Product gate FAIL |
| Classification subsystem failure | isolate from Task-01/Auth/CAPPORT | block Authorization | Failure isolation |
| Public/UI feature proposed | separate later task | scope creep | Out of scope |


---


## F.1 R12 control-plane stop/error additions

| Condition | Layer | Exact outcome | Retry class | Semantic device status? |
|---|---|---|---|---|
| activation transaction aborts before COMMIT | control plane | old complete pointer/activation/head remains | retryable when storage condition clears | NO |
| pointer/activation/head durable set inconsistent on recovery | control plane | `activation_lineage_unavailable`; production start/commit FAIL CLOSED | non-retryable until repaired | NO |
| validity CAS expected-head mismatch | control plane | transition transaction rolls back; reread head and retry | retryable | NO |
| pinned activation canonical head = SUSPENDED_INVALIDATED | production commit | reject with `runtime_profile_invalidated` | non-retryable for that pinned request | NO |
| T-ACCEPT PASS | acceptance | candidate admitted/eligible only; production pointer unchanged | N/A | NO |
| production activation lacks explicit Owner deployment decision | control plane | activation forbidden | non-retryable until decision exists | NO |

# APPENDIX G — Runtime artifact update / re-admission matrix

Every RuntimeProfileAdmissionManifest has exactly one `profile_kind` and exactly one closed `update_class`.

If one operational change requires both foundation and classification profile changes, Appendix G means TWO ordered admissions/actions: first foundation admission, then classification admission after the exact foundation RuntimeProfileAdmissionManifest exists.

| update_class | profile_kind / ordered action | Allowed FRP delta | Allowed CRP delta | Required proof | Task04AcceptanceManifest | Activation rule |
|---|---|---|---|---|---|---|
| `INITIAL_FOUNDATION` | foundation | Initial complete FRP | N/A | all initial Foundation gates + F-ADMIT | null | F-ADMIT crash-atomically activates initial FRP |
| `INITIAL_CLASSIFICATION` | classification | referenced admitted FRP unchanged | Initial complete CRP | T-06/T-06A + applicable T-01..T-09 + T-ACCEPT | **NEW REQUIRED** | T-ACCEPT does NOT activate; separate Owner production action activates exact P |
| `KNOWLEDGE_BUNDLE_REFRESH` | classification | unchanged | ONLY KnowledgeBundle ref changes | import/governance/freshness/bundle validation + profile compatibility | REUSE permitted if policy/adapters/classifier/foundation unchanged | Candidate CRP → RPM → required Decision → separate crash-atomic CRP activation |
| `KNOWLEDGE_FRESHNESS_POLICY_CHANGE` | classification | unchanged | KnowledgeBundle ref changes because new policy→new provenance→new bundle; all other CRP refs unchanged | new KFP + affected provenance + bundle validation + compatibility | REUSE only if generic classifier/policy/adapter semantics unchanged | no policy-only state; activate admitted CRP separately |
| `BINDING_TIMELINE_CHANGE` | foundation THEN classification | Foundation RPM: BindingTimeline; BindingClockPolicy/valid-from/emitter/ORA only when proof requires | Classification RPM: ONLY FRP ref changes | binding/source-authority/clock proof + compatibility | REUSE if classifier/policy/adapters unchanged | two RPMs/actions; live classification changes only after companion CRP activation |
| `CAPTURE_TOPOLOGY_CHANGE` | foundation THEN classification | Binding/Clock as applicable; TTLCapturePlacementProof; OriginRuntimeAdmission; valid-from may move later | companion CRP: ONLY FRP ref changes | topology/binding/clock proof + new TTL proof OR later TCP-disabled safety profile | REUSE if classifier semantics unchanged | unsafe old path suspended until safe companion CRP separately activates |
| `SOURCE_HEALTH_EMITTER_CHANGE` | foundation THEN classification | emitter refs; affected BindingTimeline epoch; SourceHealthPolicy/retention only as proven | companion CRP: ONLY FRP ref changes | emitter/epoch/health/retention compatibility proof | REUSE if classifier semantics unchanged | two admissions/actions |
| `SOURCE_HEALTH_POLICY_CHANGE` | foundation THEN classification | SourceHealthPolicy; Task01HealthRetentionContract only if safely compatible | companion CRP: ONLY FRP ref changes | health semantics + retention-margin proof | REUSE if classifier semantic contract unchanged | block until sufficient history; then two admissions/actions |
| `SNAPSHOT_CONTENT_POLICY_CHANGE` | foundation THEN classification | SnapshotContentPolicy only | companion CRP: ONLY FRP ref changes | sizing/query/WAL/materialization proof | REUSE | two admissions/actions |
| `SNAPSHOT_EXECUTION_POLICY_CHANGE` | foundation THEN classification | SnapshotExecutionPolicy only | companion CRP: ONLY FRP ref changes | operational safety proof | REUSE | pure semantic digests unchanged; two admissions/actions if production classification should use new FRP |
| `EVIDENCE_SCHEMA_CHANGE` | foundation; classification companion only if needed | EvidenceSchemaRegistryContract + directly required compatible foundation refs | REUSE path: only FRP ref changes and adapter/policy/classifier IDs unchanged | final schema/registry admission + compatibility/regression | REUSE ONLY when adapter/policy/classifier unchanged and no new classifier semantic behavior; otherwise companion uses `EVIDENCE_ADAPTER_CHANGE` or composite class and NEW manifest | Foundation registry may admit first without active CRP change; no impossible intermediate CRP |
| `EVIDENCE_ADAPTER_CHANGE` | classification (after any required foundation schema admission) | unchanged admitted FRP ref for this classification admission | new EvidenceAdapterContractSet + dependent ClassificationPolicy rebind ONLY + ClassifierArtifactManifest as required | adapter admission + full applicable semantic/regression/product gates | **NEW REQUIRED** | dependent policy rebind is part of this class, not independent policy-rule change |
| `EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE` | classification | unchanged admitted FRP ref unless separately admitted foundation change already exists | new EvidenceAdapterContractSet + genuine ClassificationPolicy rule semantics + ClassifierArtifactManifest as required | full Task-04 semantic/regression/product reacceptance | **NEW REQUIRED** | exact tested CRP only after T-ACCEPT; separate production activation |
| `CLASSIFICATION_POLICY_CHANGE` | classification | unchanged | ClassificationPolicy rule semantics only; ClassifierArtifact only if implementation change follows its applicable acceptance | full applicable semantic vector/regression/product gates | **NEW REQUIRED** | exact tested CRP only after T-ACCEPT; separate production activation |
| `CLASSIFIER_ARTIFACT_CHANGE` | classification | unchanged unless separately admitted foundation change already exists | ClassifierArtifactManifest only; other semantic refs unchanged | T-06/T-06A + applicable T-gates including product validation | **NEW REQUIRED** | exact tested CRP only after T-ACCEPT; separate production activation |
| `FOUNDATION_VALID_FROM_LATER` | foundation THEN classification | valid-from may ONLY move later; related authority refs only if proof requires | companion CRP: ONLY FRP ref changes | authority/monotonicity proof | REUSE if classifier semantics unchanged | two admissions/actions |
| `ROLLBACK_REACTIVATION` | foundation OR classification | candidate bytes/digest EXACTLY equal a previously admitted FRP | candidate bytes/digest EXACTLY equal a previously admitted CRP | previous admission proof + current safety/compatibility recheck + DecisionRecord where required | classification rollback REUSES lineage that admitted exact profile unless new semantic reacceptance independently required | NEW RPM + NEW crash-atomic activation/validity record/head; no unaudited pointer rewind |

## G.1 Semantic reacceptance rule

ANY update requiring full/applicable Task-04 semantic reacceptance MUST produce a NEW Task04AcceptanceManifest referencing the exact newly tested candidate ClassificationRuntimeProfile.

At minimum:

```text
EVIDENCE_ADAPTER_CHANGE
EVIDENCE_ADAPTER_AND_CLASSIFICATION_POLICY_CHANGE
CLASSIFICATION_POLICY_CHANGE
CLASSIFIER_ARTIFACT_CHANGE
EVIDENCE_SCHEMA_CHANGE when classifier semantic behavior changes via its required companion classification class
```

Old Task04AcceptanceManifest MUST NOT bless a changed semantic classifier contract.

## G.2 Bounded acceptance-lineage reuse

Reuse is permitted only where the table explicitly says `REUSE` and exact field-delta/compatibility checks PASS.

No implicit reuse.

## G.3 KnowledgeFreshnessPolicy semantic update order

```text
new KnowledgeFreshnessPolicy
→ new affected external KnowledgeProvenanceManifest
→ new KnowledgeBundle
→ candidate ClassificationRuntimeProfile
→ compatibility + bounded admission proofs
→ RuntimeProfileAdmissionManifest(KNOWLEDGE_FRESHNESS_POLICY_CHANGE,
     exact foundation RuntimeProfileAdmissionManifest)
→ DecisionRecord where required
→ separate crash-atomic CRP activation
```

A policy-only active state is impossible.

## G.4 Foundation profile change intended for production classification

```text
admit new FRP with ONE foundation RPM
→ construct compatible companion CRP
→ admit companion CRP with a DISTINCT classification RPM
   that pins the exact foundation RPM
→ separately crash-atomically activate the companion CRP
```

Until companion CRP activation, existing production requests remain on the old CRP/old referenced FRP. If old generation is unsafe, affected classification is suspended rather than mixed.

## G.5 Rollback exact meaning

For `ROLLBACK_REACTIVATION`:

```text
NO semantic delta
=
candidate profile bytes/digest EXACTLY equal a previously admitted immutable profile
```

It does NOT mean equality to the currently active profile. Current-active and rollback-target differences are expected.

Rollback activation still creates a NEW RuntimeProfileAdmissionManifest, NEW RuntimeProfileActivationRecord and NEW initial ACTIVE RuntimeProfileValidityRecord/head through the crash-atomic primitive.

## G.6 Non-runtime policies

ProductValidationPolicy and ClassificationRetentionPolicy changes do not use RuntimeProfileAdmissionManifest unless combined with an actual runtime-profile change covered by one closed update_class.

No ArtifactContent becomes active merely because it exists on disk.

---

# End of R12
