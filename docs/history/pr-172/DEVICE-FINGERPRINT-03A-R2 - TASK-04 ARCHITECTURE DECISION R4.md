# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R4

## Strongest Practical Passive Evidence Foundation Before Task-04

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-16  
**Supersedes:** `DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R3`  
**Status:** `FOR OWNER + TECHLEAD11 STRICT REVIEW`  
**Task-04 decomposition:** `HOLD`  
**Coder:** `HOLD`  
**Code:** `NO`  
**Production change:** `NO`

---

# 1. R4 Disposition

TechLead11 strict review of R3 returned:

```text
R3 = REQUEST CHANGES

ARCHITECTURE CONTRACT FINAL = REVOKED
```

R4 replaces R3 in full.

R4 does NOT append exceptions to R3.

Any R3 wording inconsistent with R4 is superseded.

Owner policy remains:

```text
REVISION COUNT DOES NOT MATTER.

THE FOUNDATION MUST BE:

clean
internally consistent
deterministic
free of known architectural debt

BEFORE TASK-04 STARTS.
```

R4 therefore does not optimize for closing review.

It optimizes for the strongest clean foundation that can be practically proven.

---

# 2. Verified Repository Baseline

Architecture review was rebound to current repository state:

```text
origin/main =
d37d3ec126ccd512fe835af0db21221e2f83d565

tree =
3145e904ad5027d0d584945f4814f3ade59d44ea
```

Current accepted evidence families are:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

Current Task-01 evidence rows already contain:

```text
observed_at
ingested_at
evidence_id
payload_sha256
site_id
observed_mac
capture_source_id
source_kind
```

Current persisted source-health states are exactly:

```text
available
unavailable
unsupported
```

There is no persisted:

```text
degraded
unknown
```

source-health state.

Current Task-01 evidence read API is cursor-paginated and allows:

```text
1..500 rows per page
```

Current network sensor source-health heartbeat contract is:

```text
300 seconds
```

for:

```text
dhcp
tcp_syn
tls_client
quic_client
```

Current portal producer emits source-health transitions from delivery activity but does not provide an equivalent periodic liveness heartbeat.

That asymmetry is explicitly addressed by R4.

---

# 3. Permanent Architecture Principles

The following remain permanent:

```text
normalized evidence
!= classification
!= ground truth

passive evidence
!= device identity proof

classification
!= Authorization input

classification
!= security decision

offline-first classification

runtime classification has no required Internet dependency

Fingerbank Cloud default OFF

raw packets are non-durable

raw User-Agent is non-durable

raw Client Hints are non-durable

no one-fingerprint-one-device assumption

no cross-MAC identity merge

row count does not create confidence

same evidence interpreted by multiple knowledge systems
does not create independent votes

unknown is valid

insufficient evidence is valid

conflict is valid

recognized-out-of-scope is valid

classification storage is separate from Task-01 evidence storage

KnowledgeBundles are immutable/versioned

external vendor artifacts are import inputs
not runtime schemas
```

New R4 permanent principles:

```text
tcp_syn/2 is protocol-semantic
not p0f-semantic

p0f conformance
!= p0f production knowledge content

source taxonomy
must not be squeezed into CaptivPortal taxonomy

IEEE assignment holder
!= automatically device manufacturer

OriginAssessment is origin-pure

classification windows are caller-owned

snapshot completeness requires observed-time
+
ingestion cutoff

source health is interval semantics
not latest-row semantics

knowledge freshness is part of claim admissibility

confidence means evidence support
not probability
```

---

# 4. Boundaries R4 Does Not Reopen

R4 does not reopen:

```text
Catalyst RSPAN architecture

AF_PACKET process architecture

raw packet dedup architecture

Suricata EVE architecture

Task-01 security/API envelope

Task-01 normalized evidence DB ownership

Portal Authorization flow

AuthSession/AuthWorker semantics

CAPPORT behavior

no cross-MAC identity rule
```

except bounded changes explicitly required for:

```text
tcp_syn/2

portal_headers/2 candidate work

source-health liveness

complete deterministic evidence reads
```

---

# 5. Revised Program Sequence

```text
TASK-01
Evidence Foundation
DONE

TASK-02
Core Packet Sensor
DONE

TASK-03
Portal Evidence
DONE

TASK-03A
Labeled Evidence Matrix
DONE / research foundation

        ↓

PRE-TASK-04 FOUNDATION CLOSURE

OPT-01R
EvidenceSnapshot complete/as-of read contract

OPT-02A
tcp_syn/2 protocol-semantic evidence
+
p0f adapters
+
p0f conformance

OPT-03A
portal_headers/2 bounded CH experiment
+
Accept-CH lifecycle teardown
+
portal source-health heartbeat

OPT-SRC1
EvidenceSourceRegistry / SourceBindingMap
+
source-health interval reconstruction

OPT-KB1
Fingerbank static artifact inspection
+
canonical import
+
DHCP-only deterministic matcher

OPT-KB2A
p0f semantics/conformance model

OPT-KB2B
admitted production TCP knowledge corpus

OPT-KB3
IEEE MA-L / MA-M / MA-S canonical import

OPT-KB4
classification_taxonomy_v1
+
manufacturer/model aliases
+
out-of-scope semantics

        ↓

R4 REQUIRED PROOF GATES PASS

        ↓

TECHLEAD11 TASK-04 DECOMPOSITION

        ↓

OWNER IMPLEMENTATION AUTHORIZATION
```

Architectural acceptance of R4 may occur while proof gates remain pending.

However:

```text
TASK-04 DECOMPOSITION
=
HOLD
```

until all gates designated mandatory pre-Task-04 are closed.

---

# 6. tcp_syn/2 — Evidence-Layer Decision

`tcp_syn/2` is a normalized protocol-semantic packet-fact schema.

It is NOT:

```text
a p0f fingerprint schema

a Fingerbank schema

an OS classification schema
```

Canonical pipeline:

```text
eligible complete TCP SYN frame
        ↓
protocol-semantic parser
        ↓
tcp_syn/2 normalized packet facts
        ↓
adapter
        ├── p0f runtime representation
        ├── p0f matcher representation
        ├── Fingerbank TCP representation if admitted
        └── future fingerprint representations
```

Task-02 evidence therefore remains useful if:

```text
p0f is replaced
Fingerbank is replaced
a second TCP knowledge engine is added
```

---

# 7. tcp_syn/2 — Forbidden Durable Fields

`tcp_syn/2` MUST NOT persist:

```text
p0f_quirks

p0f_signature

p0f raw_sig

p0f_rule

p0f_label

p0f payload-class token

p0f option-layout token dialect

Fingerbank TCP string

OS guess

platform guess

device guess
```

All of those are adapter or knowledge-layer semantics.

---

# 8. tcp_syn/2 Initial Scope

Initial V2 scope remains:

```text
IPv4 only

outbound guest request SYN

SYN = 1

ACK = 0 eligibility

unfragmented IPv4

current pre-router RSPAN capture placement

complete Ethernet/IP/TCP bytes available
for the declared captured IP packet
```

Architecture claim:

```text
protocol-semantic normalized TCP SYN facts
sufficient for exact supported-scope
p0f request reconstruction
```

Not:

```text
universal p0f parity

IPv6 parity

SYN-ACK parity

fragment reassembly parity
```

---

# 9. tcp_syn/2 Canonical Protocol Facts

The durable schema SHALL preserve bounded packet-derived facts only.

Required V2 conceptual fields:

```text
ip_version = 4

observed_ttl

ip_header_length_bytes
ip_total_length_bytes
ip_option_length_bytes

ip_id
ip_df_flag
ip_reserved_flag
ip_ecn_bits

tcp_header_length_bytes
tcp_window

tcp_window_scale_raw
mss

tcp_syn_flag
tcp_ack_flag
tcp_fin_flag
tcp_rst_flag
tcp_push_flag
tcp_urg_flag
tcp_ece_flag
tcp_cwr_flag

tcp_sequence_zero
tcp_ack_number_nonzero
tcp_urg_pointer_nonzero

tcp_timestamp_present
tcp_timestamp_value
tcp_timestamp_echo_reply

tcp_option_kind_sequence

tcp_option_records

tcp_option_structure_status

tcp_eol_padding_length
tcp_eol_padding_nonzero

tcp_payload_length_bytes
```

Timestamp numeric values are bounded unsigned protocol facts.

Raw option bytes are not persisted.

Raw TCP payload is not persisted.

Raw sequence/ACK numbers are not required; only the semantic facts needed for supported fingerprint reconstruction are retained.

---

# 10. TCP Option Record Contract

`tcp_option_records` exists to preserve observable TCP option structure without adopting p0f vocabulary.

Each bounded record may contain:

```text
kind

declared_length

available_value_length

structure_state
```

Where applicable, parsed semantic values remain in dedicated fields such as:

```text
mss

tcp_window_scale_raw

tcp_timestamp_value

tcp_timestamp_echo_reply
```

For unknown options:

```text
kind
declared_length
available_value_length
```

remain observable packet facts.

No unknown option receives a guessed semantic name.

---

# 11. TCP Option Structural States

Canonical V2 distinction:

```text
well_formed

malformed_but_observable
```

An eligible complete TCP header is NOT discarded merely because its internal option encoding is abnormal.

Examples that MUST be preserved when the relevant header bytes are physically present:

```text
window scale beyond normal RFC range

known option with abnormal declared length

unknown option

internal option length inconsistent
with remaining option area

non-zero bytes after EOL

abnormal EOL padding

ACK number present without ACK flag

URG pointer anomaly

zero sequence number

timestamp anomalies
```

The event records packet facts plus structural anomaly state.

The adapter later determines whether that state maps to:

```text
p0f bad

p0f opt+

p0f exws

or another external semantic
```

Task-02 does not persist that mapping.

---

# 12. Genuine Structural Incompleteness

An event may be omitted only for packet conditions proven equivalent to genuine structural incompleteness/non-fingerprintability within the pinned supported parser contract.

Examples include:

```text
captured frame shorter than declared IPv4 packet

IPv4 header itself incomplete

IPv4 IHL below legal minimum

IPv4 total length shorter than required headers

TCP fixed header incomplete

TCP data offset below legal minimum

TCP data offset requiring bytes outside
the complete declared IPv4 packet

required bytes physically unavailable
```

A malformed option whose length field is wrong inside an otherwise fully captured TCP header does NOT automatically qualify as packet truncation.

The exact boundary SHALL be conformance-tested against the pinned real p0f implementation.

No V1-style silent loss of fingerprintable abnormal SYNs is permitted.

---

# 13. TCP Payload Semantics

Durable packet fact:

```text
tcp_payload_length_bytes
```

derived from:

```text
IPv4 total length
-
IP header length
-
TCP header length
```

External adapters may derive:

```text
p0f payload class 0
p0f payload class +
```

Task-02 SHALL NOT persist those tokens.

---

# 14. p0f Adapter Boundary

Transient adapter:

```text
tcp_syn/2
→ p0f_runtime_ipv4_request_v1
```

may derive:

```text
p0f option layout

p0f quirks

p0f payload class

TTL/distance representation
```

Those are external-dialect outputs.

They never become durable Task-02 evidence.

---

# 15. p0f Quirks Are Adapter Semantics

For supported IPv4 request processing, the adapter may derive semantics equivalent to:

```text
df
id+
id-
ecn
0+
seq-
ack+
ack-
uptr+
urgf+
pushf+
ts1-
ts2+
opt+
exws
bad
```

Their exact derivation and ordering MUST match the pinned p0f oracle.

No alphabetic or locally invented order.

`flow` remains outside initial IPv4 scope.

---

# 16. TTL / RSPAN Contract

Topology suggests:

```text
client-emitted TTL
==
sensor-observed TTL
```

because capture is expected before L3 forwarding.

R4 still refuses to freeze this from topology theory alone.

Mandatory controlled proof records:

```text
actual Catalyst monitor/RSPAN running config

source VLAN/interface

direction

controlled sender SYN identity

sender original TTL

correlated sensor enp8s0 TTL
```

Only after PASS:

```text
current capture placement TTL distance = 0
```

If capture placement or monitor configuration changes:

```text
TTL compatibility proof invalidated
```

and must be repeated.

---

# 17. K2A — p0f Semantics / Conformance

K2 is split.

K2A owns:

```text
p0f runtime serialization semantics

p0f knowledge-rule grammar

window expressions

MSS/MTU expressions

wildcards

TTL variation

fuzzy matching behavior

quirk semantics

generic/specific precedence

real-p0f oracle corpus
```

Purpose:

```text
prove that CaptivPortal interprets p0f correctly
```

K2A does NOT define which TCP signatures production should trust.

---

# 18. K2A Matcher Model

Selected model remains:

```text
versioned local p0f-compatible matcher
```

No partial clone may ship.

Supported-scope result must conform to a pinned real p0f engine for:

```text
match / no-match

specific/generic selection

label/class/name/flavor where applicable

fuzzy state

TTL/distance interpretation
```

Any mismatch in the accepted conformance corpus:

```text
K2A FAIL
```

No approximate fallback.

---

# 19. K2B — Production TCP Knowledge Corpus

K2B is separate from K2A.

K2B owns actual TCP reference signatures admitted for production classification.

Possible sources include:

```text
pinned p0f.fp

Fingerbank TCP signatures
if present and legally usable

future curated/licensed modern corpus
```

Permanent:

```text
p0f oracle
!= mandatory production truth
```

The old p0f corpus does not become production authority merely because p0f is used for conformance.

Changing the accepted K2B corpus MUST NOT require changing:

```text
tcp_syn/2

EvidenceSnapshot

OriginAssessment contract

fusion engine
```

---

# 20. K2B Canonical Import

Raw source formats such as:

```text
p0f.fp

Fingerbank SQLite rows

other external rule files
```

are import inputs only.

Canonical path:

```text
external TCP artifact
        ↓
quarantine
        ↓
validated source-specific importer
        ↓
CaptivPortal canonical TCP knowledge records
        ↓
accepted KnowledgeBundle
        ↓
runtime matcher
```

Runtime never parses raw `p0f.fp`.

Runtime never opens Fingerbank vendor tables directly.

---

# 21. Fingerbank TCP Compatibility

Fingerbank documents TCP signatures as p0f-standard representations.

A bounded synthetic compatibility proof remains required before any Fingerbank TCP adapter is admitted.

It proves exact accepted representation of:

```text
TTL/distance

zero-distance spelling

option layout

quirks

payload class
```

No production client fingerprint is needed.

A Fingerbank-specific representation remains transient adapter output.

---

# 22. Task-03 / portal_headers/2 Status

`portal_headers/2` remains:

```text
CANDIDATE
NOT FROZEN
```

Permanent privacy:

```text
raw UA = non-durable

raw Client Hints = non-durable
```

Candidate high-entropy hints remain:

```text
Sec-CH-UA-Model

Sec-CH-UA-Platform-Version

Sec-CH-UA-Form-Factors
```

A field enters V2 only after actual-flow proof demonstrates material value.

---

# 23. Portal Hint Admission Rule

Each candidate field is admitted independently only if:

```text
real supported client emits it

normalization is deterministic

semantic granularity is understood

it materially improves an allowed classification dimension

raw value remains transient

no Authorization dependency exists

no redirect/portal regression exists

collection lifetime is bounded

missing value remains normal
```

If none pass:

```text
portal_headers/1 remains canonical
```

That is an acceptable result.

---

# 24. Accept-CH Collection Lifecycle

High-entropy Client Hints SHALL NOT remain requested indefinitely.

Candidate V2 flow:

```text
controlled eligible portal response
        ↓
bounded Accept-CH request
        ↓
one subsequent eligible same-origin request
        ↓
normalize accepted values
        ↓
stop requesting high-entropy hints
        ↓
clear persisted client-hint preference
where the client supports the standards mechanism
```

Preferred teardown contract:

```text
Clear-Site-Data: "clientHints"
```

after the bounded collection hop where supported.

The application MUST NOT continuously emit the high-entropy `Accept-CH` request after collection is complete.

P6 must test both acquisition and teardown.

If a supported browser class cannot demonstrate a bounded standards-compliant lifecycle:

```text
high-entropy CH collection is not admitted
for that client class
```

No JavaScript fingerprint fallback.

No Authorization wait/retry loop.

---

# 25. Portal Source-Health Heartbeat

Current portal source-health is transition/event-driven and does not prove liveness while no portal evidence is flowing.

Before Task-04, this asymmetry must be closed.

When portal evidence production is enabled, `portal_headers` SHALL emit a bounded liveness/source-health heartbeat independent of whether a client happens to visit the portal.

V1 target heartbeat interval:

```text
300 seconds
```

This heartbeat exists only to prove the source/delivery path.

It MUST NOT:

```text
affect Authorization

block portal requests

create browser traffic

contain client evidence

contain MAC/IP/UA/CH
```

Portal and network source-health can then use one reconstruction model.

---

# 26. classification_taxonomy_v1

R4 freezes a canonical V1 taxonomy.

Classification dimensions:

```text
platform_family

device_class

manufacturer_family

model_family
```

Source-specific values are NEVER copied directly into these dimensions without an admitted deterministic mapping.

---

# 27. platform_family v1

Canonical resolved values:

```text
android
ios
windows
macos
chromeos
linux
```

`ios` is the V1 Apple mobile OS family and may include an explicitly mapped iPadOS source taxon when the alias mapping proves family equivalence.

No source value outside this set is guessed into the closest value.

If a source recognizes another platform but the V1 taxonomy does not contain it:

```text
result status =
recognized_out_of_scope

value =
null

recognized_taxon_reference =
preserved for explanation
```

Unknown and recognized-out-of-scope are different states.

---

# 28. device_class v1

Phase-1 canonical values are exactly:

```text
smartphone
tablet
laptop
```

No other class is silently mapped into these.

Examples:

```text
external Phone
→ NOT automatically smartphone

external Mobile
→ NOT automatically smartphone

Client Hint form-factor Desktop
→ NOT automatically laptop

Wearable
→ NOT smartphone

TV
→ NOT tablet

Desktop workstation
→ NOT laptop
```

When an accepted source specifically recognizes:

```text
TV
printer
camera
watch/wearable
desktop workstation
IoT class
or another non-Phase-1 device
```

the canonical result is:

```text
status =
recognized_out_of_scope

device_class =
null
```

The source taxonomy reference remains available for explainability.

No out-of-scope class is squeezed into the Phase-1 enum.

---

# 29. manufacturer_family v1

`manufacturer_family` is NOT an arbitrary source string.

Resolved value is:

```text
canonical manufacturer ID
```

The ID:

```text
exists in the active KnowledgeBundle taxonomy

is versioned

has a separate display label

has source-specific aliases separately
```

Conceptual example:

```text
manufacturer_id = samsung

display_label = Samsung

aliases may include explicitly reviewed source forms
```

No alias is accepted merely because strings look similar.

---

# 30. model_family v1

`model_family` is similarly represented by:

```text
canonical model-family ID
```

plus a separate display label.

A model family is resolved only when a source-specific value has an admitted mapping.

Examples such as:

```text
SM-S928B
Galaxy S24 Ultra
Samsung SM-S928B
```

are not considered equal by string heuristics.

They become equivalent only through an accepted versioned alias mapping.

---

# 31. Canonical Alias Layer

KnowledgeBundle owns:

```text
taxonomy_version

manufacturer records

model-family records

source-taxonomy mappings

source aliases

canonical display labels
```

Permanent rules:

```text
unproven aliases are not merged

case-insensitive similarity alone is insufficient

punctuation normalization alone is insufficient

vendor-prefix stripping alone is insufficient

different source labels
do not automatically mean conflict

one-to-many alias mapping
does not resolve the dimension
```

If a source taxon is broader than the CaptivPortal dimension:

```text
dimension remains unresolved
```

---

# 32. Taxonomy Mapping Safety

Permitted:

```text
source exact semantic
→ equal/broader canonical family
when explicitly reviewed
```

Forbidden:

```text
broad source semantic
→ narrower CaptivPortal semantic
without proof
```

Examples:

```text
source = Android
→ platform_family android

source = Tablet
→ device_class tablet
if source taxonomy explicitly means device class

source = Mobile
→ no smartphone claim

source = Desktop form-factor
→ no laptop claim
```

---

# 33. IEEE Registry Meaning

IEEE MA-L / MA-M / MA-S identifies an address assignment holder.

Canonical raw result:

```text
mac_assignment_org
```

It does NOT automatically mean:

```text
device manufacturer
```

The assignment organization may be:

```text
device vendor

NIC vendor

chip vendor

ODM

parent organization

subsidiary

other assignment owner
```

---

# 34. IEEE MAC Eligibility

U/L-bit rule remains mandatory.

If:

```text
U/L bit = 1
```

then:

```text
MAC is locally administered/randomized for this purpose

IEEE assignment lookup =
NOT ELIGIBLE

mac_assignment_org =
none
```

If:

```text
U/L bit = 0
```

longest-prefix registry lookup may proceed.

No cross-MAC inference.

---

# 35. IEEE Longest-Prefix Lookup

Canonical importer supports:

```text
MA-L
MA-M
MA-S
```

Canonical imported record:

```text
prefix_bits

prefix_length

assignment_org_id

assignment_org_label

registry_family

source_record_reference
```

Runtime chooses the longest matching eligible prefix.

Do not reduce IEEE support to 24-bit OUI lookup.

---

# 36. IEEE → Manufacturer Mapping

Raw IEEE evidence contributes:

```text
mac_assignment_org
```

only.

A `manufacturer_family` claim may be emitted only if the active KnowledgeBundle contains an explicit reviewed mapping:

```text
mac_assignment_org_id
→ canonical manufacturer_id
```

That mapping has:

```text
mapping_version

review_basis

claim_grade
```

Default with no accepted mapping:

```text
manufacturer claim =
NONE
```

Therefore:

```text
IEEE match
!= manufacturer certainty
```

---

# 37. Origin Groups

Cross-origin fusion recognizes exactly these V1 origin groups:

```text
dhcp

portal

tcp

tls

quic

mac_registry
```

An individual evidence row never votes directly in final fusion.

---

# 38. Origin Purity

Each `OriginAssessment` consumes only evidence belonging to its origin.

Canonical V1:

```text
dhcp
→ dhcp evidence only

portal
→ portal_headers evidence only

tcp
→ tcp_syn evidence only

tls
→ tls_client evidence only

quic
→ quic_client evidence only

mac_registry
→ current observed MAC only
```

Knowledge sources may interpret an origin's evidence, but may not inject facts from another origin.

---

# 39. Fingerbank Origin Purity

K1 static Fingerbank DHCP interpretation MUST use only admitted DHCP-derived attributes.

It MUST NOT secretly add:

```text
MAC/OUI

portal UA

Client Hints

TCP

TLS

QUIC
```

to obtain a stronger result.

If Fingerbank Cloud is ever enabled in V1:

```text
fusion-eligible Cloud lookup =
DHCP-only
```

A multi-origin Fingerbank result may exist only as:

```text
explainability-only enrichment
```

and is excluded from support/confidence fusion.

No multi-origin external result becomes an extra independent vote.

---

# 40. JA4 Semantics

Permanent:

```text
JA4 observed
!= platform

JA4 observed
!= device class

JA4 observed
!= manufacturer

JA4 observed
!= model
```

If no admitted local JA4 reference knowledge exists:

```text
tls OriginAssessment =
no classification claim

quic OriginAssessment =
no classification claim
```

No frequency heuristic.

No “Apple-like”, “Android-like” or similar locally invented labels.

---

# 41. External Artifact Boundary

Runtime classification MUST NOT depend directly on:

```text
Fingerbank SQLite schema

IEEE CSV schema

raw p0f.fp grammar/file layout

vendor-specific tables/views
```

Every external artifact follows:

```text
external artifact
        ↓
quarantine / read-only inspection
        ↓
source digest
        ↓
license/provenance review
        ↓
source-specific validated importer
        ↓
CaptivPortal canonical KnowledgeBundle schema
        ↓
bundle validation
        ↓
immutable accepted bundle
        ↓
runtime classifier
```

Runtime reads only CaptivPortal canonical records.

---

# 42. Canonical KnowledgeBundle Schema Families

Conceptual internal record families include:

```text
SourceManifest

TaxonomyManufacturer

TaxonomyModelFamily

SourceAliasMapping

DhcpKnowledgeRecord

TcpKnowledgeRecord

MacAssignmentRecord

MacAssignmentManufacturerMapping

PortalSemanticRule

optional Ja4KnowledgeRecord
```

Exact SQLite/table implementation belongs to Task-04 decomposition.

The architecture invariant is:

```text
runtime internal schema
!= upstream vendor schema
```

---

# 43. Knowledge Source Governance

Every imported source records:

```text
source_name

source_version

retrieved_at

source_digest

importer_version

license_identifier

license_source_reference

license_text_digest
if bundled

redistribution_status

attribution_required

modification_status

commercial_use_status

reviewed_at

review_basis

freshness_policy_id
```

Unknown material legal status:

```text
SOURCE NOT ADMITTED
```

No production bundle silently accepts unknown terms.

---

# 44. Knowledge Freshness Is First-Class

Each changing external source has a frozen source-specific freshness contract.

Runtime derives:

```text
fresh

stale

expired
```

for the classification's recorded:

```text
knowledge_as_of_utc
```

Knowledge freshness is part of claim admissibility.

It is not just dashboard metadata.

---

# 45. Fingerbank Static Freshness Policy

Initial V1 policy:

```text
policy_id =
fingerbank_static_v1

fresh:
retrieved age <= 30 days

stale:
>30 and <=90 days

expired:
>90 days
```

Behavior:

```text
fresh
→ normal admitted claim grade

stale
→ claim grade capped at supporting
→ explicit stale warning

expired
→ no classification claim
→ refresh required
```

This applies only if actual Fingerbank terms allow the artifact to be admitted.

---

# 46. IEEE Registry Freshness Policy

Initial V1:

```text
policy_id =
ieee_registry_v1

fresh:
retrieved age <= 90 days

stale:
>90 and <=180 days

expired:
>180 days
```

Behavior:

```text
fresh
→ normal assignment-org use

stale
→ assignment-org remains explainable
→ manufacturer mapping claim capped at supporting

expired
→ no classification manufacturer claim
→ registry refresh required
```

---

# 47. Legacy p0f Corpus Freshness

K2A conformance oracle and K2B production knowledge remain separate.

Pinned p0f code/corpus may remain valid as:

```text
conformance oracle
```

without being modern production taxonomy.

If legacy `p0f.fp` is admitted as K2B:

```text
knowledge freshness state =
stale_legacy
```

from initial admission.

Its classification claim grade is capped at:

```text
supporting
```

It requires explicit re-review at least every:

```text
365 days
```

If review age exceeds 365 days:

```text
classification claim =
expired / not admitted until re-review
```

A newer admitted K2B source may replace it without changing Task-02 evidence or fusion architecture.

---

# 48. Portal Rules Freshness

K3 portal rules are internal deterministic bundle content.

They are not time-aged like an external registry.

Their admission depends on exact compatibility with:

```text
portal evidence schema version

normalizer version

classification_taxonomy_v1
```

A schema/rule incompatibility:

```text
bundle validation FAIL
```

not silent stale behavior.

---

# 49. EvidenceSourceRegistry / SourceBindingMap

Task-04 may not infer expected sources from rows that happened to arrive.

A versioned deployment-side SourceBindingMap is mandatory.

It is separate from:

```text
KnowledgeBundle

fingerprint evidence

classification taxonomy
```

Conceptual V1 entry:

```text
binding_id

site_id

origin_group

source_kind

capture_source_id

producer_id if required for validation

required

active_from_utc
```

Current site-specific values live in deployment configuration/artifacts.

They are not hard-coded in the classifier.

---

# 50. SourceBindingMap Identity

Every immutable map has:

```text
source_binding_map_id

schema_version

created_at

content_sha256
```

EvidenceSnapshot records:

```text
source_binding_map_id
content_sha256
```

Changing:

```text
capture source

producer

site

source topology
```

creates a new SourceBindingMap version.

Historical classifications continue to reference the old version.

---

# 51. EvidenceSnapshot Ownership

Task-04 MUST NOT invent hidden lifecycle policy such as:

```text
last 5 minutes

last 30 minutes

latest evidence

most recent device state
```

Task-04 receives an explicit classification window.

Required snapshot request:

```text
site_id

observed_mac

window_start_utc

window_end_utc

snapshot_as_of_utc

source_binding_map_id
```

Task-05 or another future caller owns:

```text
WHEN to classify

WHICH visit/session/current-device interval
becomes the evidence window
```

Task-04 owns only deterministic interpretation of the supplied window.

---

# 52. EvidenceSnapshot Time Semantics

Evidence membership:

```text
observed_at >= window_start_utc

observed_at < window_end_utc

ingested_at <= snapshot_as_of_utc
```

Therefore:

```text
same observed window
+
different snapshot_as_of
=
different snapshot
```

Late-arriving evidence may legitimately appear in a later reclassification.

That produces a new snapshot identity.

No race-dependent hidden inclusion.

---

# 53. EvidenceSnapshot Canonical Ordering

Evidence rows are canonically ordered by:

```text
source_kind

capture_source_id

observed_at

evidence_id
```

Source-health events are canonically ordered by:

```text
source_kind

capture_source_id

observed_at

source_health_id
```

Ordering is independent of:

```text
SQLite incidental row order

pagination boundaries

query plan
```

---

# 54. EvidenceSnapshot Canonical Identity

Snapshot identity/digest includes at minimum:

```text
snapshot_format_version

site_id

observed_mac

window_start_utc

window_end_utc

snapshot_as_of_utc

source_binding_map_id

source_binding_map_digest
```

plus ordered evidence descriptors:

```text
evidence_id

source_kind

capture_source_id

observed_at

ingested_at

feature_schema_version

payload_sha256
```

and ordered source-health descriptors:

```text
source_health_id

source_kind

capture_source_id

status

reason_code

observed_at

ingested_at

content_sha256
```

Canonical serialization:

```text
UTF-8 canonical JSON
stable key order
no insignificant whitespace
```

Digest:

```text
SHA-256
```

---

# 55. Complete Pagination Contract

Current Task-01 evidence reads are paginated.

Task-04 MUST:

```text
paginate deterministically to exhaustion
```

or use an equivalent reviewed complete-read boundary.

Forbidden:

```text
read first 500 rows

classify

ignore next_cursor
```

because unseen later rows may contain:

```text
new semantic variant

contradiction

different source

late-arrived evidence
```

---

# 56. Snapshot Resource Ceiling

V1 complete-read policy is bounded and fail-closed.

Initial architecture bounds:

```text
read page size =
500

MAX_SNAPSHOT_EVIDENCE_ROWS =
10000

MAX_SNAPSHOT_SOURCE_HEALTH_ROWS =
2000
```

These are resource bounds, not classification-window policy.

If complete exhaustion cannot be achieved before a bound:

```text
snapshot status =
resource_limited

classification =
NOT PERFORMED
```

Affected origins:

```text
not_evaluable / resource_limited
```

Forbidden:

```text
classify partial first N rows
```

Changing these bounds requires an explicit versioned resource-policy change.

---

# 57. SourceHealthEvent vs SourceEvaluability

Persisted Task-01 source health remains exactly:

```text
available

unavailable

unsupported
```

R4 introduces no fake persisted `degraded`.

Classification derives a separate:

```text
SourceEvaluability
```

Allowed values:

```text
evaluable

partially_evaluable

not_evaluable

unknown
```

---

# 58. Source-Health Freshness SLA

Network sensor expected heartbeat:

```text
300 seconds
```

R4 v1 freshness maximum:

```text
600 seconds
```

Portal heartbeat after OPT-03A:

```text
300 seconds
```

Portal freshness maximum:

```text
600 seconds
```

The 600-second limit intentionally tolerates one missed/delayed heartbeat but does not allow an ancient `available` event to mean healthy forever.

Same-state heartbeats continue to refresh liveness.

---

# 59. Health Interval Reconstruction

For every expected SourceBinding:

1. select only health events with:

```text
ingested_at <= snapshot_as_of_utc
```

2. obtain the latest event at/before `window_start_utc` as a possible anchor;

3. include transitions/heartbeats through the classification window;

4. each event state is valid only until:

```text
next health event

or

event observed_at + 600 seconds

whichever occurs first
```

5. after freshness expiry with no newer event:

```text
state =
unknown
```

until another health event establishes state.

No historic `available` survives indefinitely.

---

# 60. Health State Across a Window

Classification health uses the entire interval, not the last event.

Example:

```text
first half unavailable
second half available
```

does NOT become:

```text
available
```

for the whole window.

Derived semantics:

```text
evaluable
=
the complete expected interval is covered by available state

partially_evaluable
=
at least one interval is available
and another interval is unavailable,
unsupported or freshness-unknown

not_evaluable
=
no interval is available
and the interval is completely known as
unavailable/unsupported

unknown
=
no usable available interval
and health coverage itself is incomplete/expired/missing
```

`unsupported` is an intentional capability state.

It is not mislabeled as an outage.

Explanation must preserve:

```text
unsupported_capability

source_unavailable

health_stale

health_missing
```

separately.

---

# 61. Health and Evidence Semantics

Permanent:

```text
source unavailable
!= negative evidence

source unsupported
!= negative evidence

source health unknown
!= negative evidence

source unavailable
!= classification conflict
```

Evidence from a proven available subinterval may be evaluated when origin evaluability is `partially_evaluable`.

Missing evidence during unavailable/unknown intervals cannot be interpreted negatively.

---

# 62. OriginAssessment Contract

Each origin produces exactly one bounded `OriginAssessment`.

Minimum:

```text
origin_group

source_evaluability

health_coverage

evidence_count

semantic_variant_count

dimension_assessments

origin_conflict

explanation_codes

evidence_reference_ids

knowledge_reference_ids

origin_assessment_digest
```

`evidence_count` is explainability only.

It never increases support level.

---

# 63. Same-Origin Consolidation

Permanent:

```text
100 identical DHCP records
!= 100 votes

100 identical TCP SYNs
!= 100 votes

100 repeated JA4 rows
!= 100 votes

100 repeated portal rows
!= 100 votes
```

Within one origin:

```text
semantic duplicates
→ collapse

compatible variants
→ consolidate

distinct non-conflicting variants
→ preserve context

contradictory semantic claims
→ origin conflict
```

No majority by packet count.

No majority by row count.

---

# 64. Claim Grades

Each deterministic knowledge interpretation may emit one of:

```text
direct

strong_derived

supporting
```

`direct` means only:

```text
the source directly declares
the semantic value at the required granularity
```

It does NOT mean:

```text
ground truth

unspoofable

authoritative identity

security proof
```

Examples of client-declared/fingerprintable sources remain spoofable:

```text
User-Agent

Client Hints

DHCP

TCP

TLS/QUIC fingerprint
```

`strong_derived` means an accepted deterministic knowledge mapping resolves the value without ambiguity.

`supporting` means weaker, broader, stale/legacy or otherwise advisory evidence.

---

# 65. Multi-Origin Fusion

Fusion consumes:

```text
one OriginAssessment per origin
```

not raw evidence rows.

Origins:

```text
dhcp
portal
tcp
tls
quic
mac_registry
```

A knowledge engine that interprets one origin stays inside that origin.

Example:

```text
Fingerbank DHCP matcher
+
another local DHCP mapping

→ one DHCP OriginAssessment
```

not two votes.

---

# 66. Per-Dimension Result Status

Each classification dimension has:

```text
value

status

support_level

origin_groups_used

conflicting_origins

not_evaluable_origins

recognized_taxon_references

explanation_codes

knowledge_reference_ids
```

Allowed status:

```text
resolved

recognized_out_of_scope

unknown

insufficient_evidence

conflicting_evidence
```

---

# 67. Evidence Support Level

The ordinal previously called confidence is explicitly:

```text
evidence support / corroboration level
```

It is NOT:

```text
probability that the classification is correct
```

Canonical field name:

```text
support_level
```

Values:

```text
none

low

medium

high
```

If a later UI uses the word `confidence`, it MUST explain that it is an ordinal evidence-support level, not statistical probability.

---

# 68. Support-Level Rules

## HIGH

```text
>=2 independent evaluable origin groups

agree on the dimension

at least two usable direct/strong-derived claims

no direct/strong-derived conflict
```

## MEDIUM

```text
one independent direct/strong-derived origin

no direct/strong-derived conflict
```

## LOW

```text
supporting claims only

no stronger contradiction
```

## NONE

```text
no usable claim

or unresolved conflict

or recognized-out-of-scope with no in-scope value
```

Repeated rows do not alter the level.

Two knowledge systems interpreting the same origin do not create HIGH.

---

# 69. Conflict Isolation

Conflict remains dimension-local.

Example:

```text
platform:

portal = windows

dhcp = android
```

while:

```text
device_class:

portal = tablet

dhcp candidate projection = tablet
```

may produce:

```text
platform:
status = conflicting_evidence
value = null
support = none

device_class:
status = resolved
value = tablet
support = high or medium
according to independent origin grades
```

A conflict in one dimension does not erase unrelated dimensions.

---

# 70. Global Classification Status

Top-level status is derived only.

Allowed:

```text
classified

partial

recognized_out_of_scope

unknown

insufficient_evidence

conflicting_evidence
```

It never replaces the four per-dimension results.

No single global support score may hide dimension-specific conflicts.

---

# 71. KnowledgeBundle Minimum

Before Task-04 decomposition, an accepted offline bundle must contain:

```text
classification_taxonomy_v1

canonical alias mappings

K1:
accepted deterministic DHCP/device knowledge

K2B:
accepted TCP knowledge corpus

K3:
accepted local portal semantic rules

K4:
IEEE MA-L / MA-M / MA-S assignment registry
```

K2A conformance assets are separately pinned to the classifier implementation.

Optional:

```text
JA4 knowledge

Fingerbank Cloud cache
```

No theoretical empty source.

No placeholder knowledge.

---

# 72. Fingerbank Static K1

Current bounded research target remains Fingerbank Community static DB.

Inspection MUST capture:

```text
retrieved_at

artifact SHA256

artifact metadata/version if exposed

SQLite user_version

tables

views

schema

indexes

row counts

device hierarchy

DHCP fingerprint records

DHCP vendor records

TCP records if present

relationships

license/terms
```

Do not assume the downloadable schema before inspection.

---

# 73. K1 Deterministic Matching

K1 input is DHCP-only.

It returns:

```text
CandidateSet
```

not a guessed single device.

Canonical:

```text
DHCP normalized attributes
        ↓
all deterministic compatible K1 records
        ↓
all linked candidate taxonomy records
        ↓
independent projection per dimension
```

Forbidden:

```text
first SQL row

undocumented ordering

popularity guess

hidden score recreation

MAC/OUI enrichment inside K1
```

---

# 74. K1 Ambiguity

Example:

```text
Candidate A:
Android / smartphone

Candidate B:
Android / tablet
```

Projection:

```text
platform_family =
android / resolved

device_class =
null / insufficient or ambiguous
```

If candidate records agree on manufacturer but disagree on model:

```text
manufacturer may resolve

model remains unresolved
```

No first-row collapse.

---

# 75. KnowledgeBundle Immutability

Accepted bundle records:

```text
knowledge_bundle_id

schema_version

created_at

content_sha256

taxonomy_version

alias_mapping_version

source manifests

source governance

freshness policies

importer versions
```

Activation:

```text
candidate

validate

proof gates

accept

atomic activate
```

Failed refresh never destroys the active accepted bundle.

---

# 76. KnowledgeBundle Retention

R3's simple:

```text
keep current + previous
```

is strengthened.

R4 requires:

```text
current bundle

previous accepted bundle

PLUS

every bundle still referenced
by a retained classification record
```

A KnowledgeBundle required for classification audit must not be garbage-collected while the corresponding classification history remains retained.

---

# 77. LOCAL_ONLY Runtime

Production classification path depends on:

```text
Task-01 normalized read boundary

explicit EvidenceSnapshot

SourceBindingMap

accepted local KnowledgeBundle

Task-04 classification storage
```

Required external network dependency:

```text
NONE
```

External knowledge refresh/import occurs outside the synchronous classification path.

---

# 78. Fingerbank Cloud

Fingerbank Cloud remains:

```text
optional

default OFF

background enrichment only
```

Never:

```text
Authorization dependency

synchronous classification dependency

required startup dependency
```

V1 fusion-eligible Cloud use, if later enabled:

```text
DHCP-only
```

Multi-origin Cloud answers are explainability-only unless a future architecture revision defines a safe origin attribution model.

---

# 79. Classification Output Contract

Minimum R4 result:

```text
classification_id

site_id

observed_mac

classification_status

platform_result

device_class_result

manufacturer_result

model_result

classification_version

classifier_artifact_identity

knowledge_bundle_id

knowledge_as_of_utc

evidence_snapshot_id

evidence_snapshot_digest

window_start_utc

window_end_utc

snapshot_as_of_utc

source_binding_map_id

source_binding_map_digest

source_evaluability_summary

origin_assessment_digests

classified_at_utc
```

No raw packet.

No raw UA.

No raw Client Hint.

---

# 80. Classification Storage

Accepted:

```text
separate classification SQLite
```

Task-01 evidence DB remains authoritative only for normalized evidence.

Classification DB owns:

```text
derived classification

bounded OriginAssessment provenance

fusion inputs

classification result

audit metadata
```

Classification DB failure:

```text
must not affect Authorization
```

---

# 81. Reproducibility — Level A

Level A:

```text
EvidenceSnapshot
→ OriginAssessment
```

is reproducible while required Task-01 evidence/source-health rows still exist.

Required identity includes:

```text
snapshot manifest

ordered evidence IDs/digests

ordered source-health IDs/digests

source-binding version

snapshot_as_of

KnowledgeBundle ID

classifier version
```

No vague `evidence_digest` alone is sufficient.

---

# 82. Reproducibility — Level B

Level B:

```text
OriginAssessment
→ final classification
```

must remain reproducible for the full retained classification-history period.

Therefore classification storage persists bounded canonical OriginAssessments or equivalent deterministic fusion inputs.

After Task-01 evidence retention expires:

```text
full evidence → OriginAssessment reproduction
may no longer be possible
```

This limitation is explicit.

However:

```text
stored OriginAssessment
→ final fusion result
```

remains auditable while classification history, referenced KnowledgeBundle and classifier identity are retained.

R4 does NOT falsely call a single digest full historical reproducibility.

---

# 83. Source Evidence Expiry Contract

After Task-01 evidence rows expire:

```text
raw/normalized evidence-level replay
=
not guaranteed
```

unless future retention policy explicitly changes.

No raw acquisition content is copied into classification storage merely to extend replay.

Privacy and bounded retention remain primary.

---

# 84. Local Validation Principle

No fixed large physical-device fleet is a prerequisite.

Use available controlled devices.

At minimum current known controlled categories may include:

```text
Android smartphone

Windows laptop
```

Required safety criterion:

```text
high-support incorrect primary dimension
=
FAIL
```

Safe results such as:

```text
unknown

insufficient

recognized_out_of_scope

low support
```

remain acceptable when evidence does not justify stronger classification.

Local validation never auto-trains production rules.

---

# 85. Required Proof Gates

R4 replaces P1–P14 with a clean P1–P25 set.

All semantics are defined here before implementation/proof work begins.

---

# 86. P1 — tcp_syn/2 Protocol Neutrality

PASS requires:

```text
durable V2 contains protocol-semantic facts only

no p0f quirk/token fields

no Fingerbank string

no OS/device result

future adapter can reconstruct required supported inputs
without raw frame persistence
```

---

# 87. P2 — Malformed TCP Option Preservation

Pinned p0f oracle fixtures prove the parser distinguishes:

```text
real packet/header truncation
from
malformed-but-observable option syntax
```

Fingerprintable malformed SYNs survive.

No silent V1-style loss.

---

# 88. P3 — p0f Runtime Serializer Conformance

For supported scope:

```text
tcp_syn/2
→ adapter
```

must exactly reproduce p0f runtime semantics for:

```text
version

TTL/distance

IP option length

MSS

window

scale

option layout

quirks

payload class
```

No approximate spelling.

---

# 89. P4 — K2A Matcher Conformance

Pinned real p0f engine is oracle.

Corpus includes:

```text
numeric window

mss*N

mtu*N

%N

wildcard MSS

wildcard window

wildcard scale

EOL padding

unknown option

exws

bad

ECN

TTL/distance

fuzzy behavior

specific/generic precedence

no-match
```

CaptivPortal result must equal oracle result within supported scope.

---

# 90. P5 — Actual TTL/RSPAN Equality

Controlled sender/sensor proof.

Required:

```text
running SPAN/RSPAN config

source/direction

sender SYN identity

sender TTL

sensor TTL
```

PASS:

```text
sender TTL == sensor TTL
```

Otherwise current zero-distance assumption is rejected.

---

# 91. P6 — Fingerbank TCP Syntax Compatibility

Synthetic-only API acceptance proves exact external runtime representation.

No production client data.

This gate proves compatibility only.

It does not make Fingerbank TCP the production K2B corpus.

---

# 92. P7 — Portal CH Actual-Flow Value

Controlled real CaptivPortal flow proves:

```text
HTTPS secure context

Accept-CH response

subsequent request behavior

Android Chromium

Android captive/WebView helper

Windows Chromium

iOS/Safari when available

missing/non-support behavior

no Authorization dependency

no redirect loop
```

Each candidate field judged independently.

---

# 93. P8 — Portal Privacy + Accept-CH Teardown

PASS requires:

```text
raw UA never durable

raw CH never durable

raw CH never logged

raw CH never queued

only normalized admitted values leave request scope

no JS fingerprint fallback

Accept-CH request is bounded

high-entropy request stops after collection

clientHints teardown is proven where supported
```

Failure to prove bounded teardown blocks high-entropy CH admission for that client class.

---

# 94. P9 — Portal Source-Health Liveness

PASS requires enabled portal producer to emit source-health liveness independently of visitor activity.

Proof:

```text
heartbeat around 300s

no client data in heartbeat

delivery failure becomes unavailable

recovery becomes available

idle portal can remain provably alive
```

---

# 95. P10 — Fingerbank Static Artifact Inspection

Owner-authorized current artifact inspection records:

```text
schema

content

relationships

digest

version

license/governance

freshness metadata
```

No production client evidence submitted.

---

# 96. P11 — External Artifact Canonical Import

For every mandatory external source:

```text
raw artifact
→ validated canonical importer
→ CaptivPortal bundle records
```

Runtime tests must succeed without the original vendor artifact being present.

PASS proves:

```text
no Fingerbank-schema runtime dependency

no IEEE-CSV runtime dependency

no raw-p0f-file runtime dependency
```

---

# 97. P12 — DHCP Matching + Origin Purity

Fixtures prove:

```text
all deterministic candidates returned

ambiguity preserved

no first-row choice

no row-order dependency

K1 receives DHCP only

K1 does not use MAC/OUI

no hidden multi-origin enrichment
```

---

# 98. P13 — K2B TCP Corpus Admission

At least one concrete production TCP knowledge source is:

```text
identified

legally/governance admitted

canonically imported

freshness policy assigned

claim grade defined
```

p0f oracle alone does not satisfy P13.

---

# 99. P14 — Taxonomy / Alias Determinism

Fixtures prove:

```text
exact v1 platform enum

exact v1 device-class enum

manufacturer IDs

model-family IDs

explicit aliases

no string heuristic merge

broad source taxonomy does not narrow itself

different labels do not automatically conflict
```

---

# 100. P15 — Out-of-Scope Behavior

Fixtures include recognized:

```text
TV

printer

camera

wearable/watch

desktop workstation

other non-Phase-1 class
```

PASS:

```text
no result is squeezed into
smartphone/tablet/laptop

recognized_out_of_scope
is distinct from unknown
```

---

# 101. P16 — IEEE Assignment-Organization Semantics

PASS proves:

```text
MA-L
MA-M
MA-S

longest-prefix lookup

U/L rule

raw result = mac_assignment_org

no automatic manufacturer claim

manufacturer claim only through accepted mapping
```

---

# 102. P17 — SourceBindingMap

PASS requires:

```text
versioned explicit expected bindings

site/source_kind/capture_source_id known
even when zero evidence arrives

no classifier hard-code of Zefer source IDs

snapshot records binding-map identity
```

---

# 103. P18 — EvidenceSnapshot as-of Determinism

Fixtures create late-arriving evidence.

Required:

```text
same window
same snapshot_as_of
→ identical snapshot digest

later snapshot_as_of
→ new snapshot may include late evidence
→ new snapshot identity
```

No race-dependent result.

---

# 104. P19 — Complete Pagination / Resource Fail-Closed

Fixtures exceed one 500-row page.

PASS:

```text
all pages consumed

canonical result independent of page boundary
```

Resource-limit fixture:

```text
limit reached before exhaustion
→ resource_limited
→ no partial classification
```

---

# 105. P20 — Source-Health Interval/Freshness Semantics

Fixtures prove:

```text
available heartbeat fresh
→ evaluable

historic available beyond 600s
→ health unknown

unavailable
→ no negative classification claim

unsupported
→ intentional not-evaluable capability

unavailable then available
→ interval remains partial

missing initial anchor
→ unknown interval until state established
```

---

# 106. P21 — Origin Dedup / Conflict / Purity

Fixtures prove:

```text
100 identical rows != 100 votes

multiple knowledge sources on one origin
!= multiple origins

contradictory same-origin variants
→ one origin conflict

multi-origin external result
→ excluded from fusion unless origin-isolated
```

---

# 107. P22 — Knowledge Freshness

Fixtures exercise:

```text
fresh

stale

expired

stale_legacy
```

for admitted source policies.

PASS requires exact claim-grade behavior.

Expired source cannot silently retain prior strength.

---

# 108. P23 — Audit / Reproducibility

PASS proves:

```text
canonical EvidenceSnapshot identity

stable ordering

evidence/health reference digests

source-binding identity

snapshot_as_of identity

KnowledgeBundle identity

classifier identity

OriginAssessment digest stability

fusion replay from retained OriginAssessments
```

Also explicitly proves that evidence-level replay is no longer guaranteed after Task-01 evidence expiry.

---

# 109. P24 — Offline KnowledgeBundle Sufficiency

With Cloud disabled, accepted bundle contains concrete usable:

```text
taxonomy/aliases

K1

K2B

K3

K4
```

with:

```text
canonical imported content

versions/digests

governance

freshness policies
```

No placeholder source.

---

# 110. P25 — Zero Runtime Network Dependency

Block all external network access.

Classification over an explicit EvidenceSnapshot must still execute deterministically using:

```text
local Task-01 evidence

local source bindings

local KnowledgeBundle

local classification storage
```

No Fingerbank Cloud requirement.

No IEEE Internet lookup.

No remote p0f service.

---

# 111. Failure Policy

Failure of a mandatory proof gate means:

```text
NO SILENT FALLBACK

NO APPROXIMATE REPLACEMENT

NO PARTIAL FIRST-PAGE CLASSIFICATION

NO EMPTY PLACEHOLDER KNOWLEDGE

NO "TEMPORARY" STRING ALIASES

NO STALE SOURCE AT NORMAL STRENGTH

NO ASSUMED SOURCE HEALTH

NO ASSUMED MANUFACTURER FROM OUI

NO TASK-04 DECOMPOSITION
```

Return to:

```text
Architect2
+
TechLead11
+
Owner where required
```

---

# 112. Revised Pre-Task Workstream Boundaries

## OPT-01R

Owns:

```text
complete read semantics

ingested_at / snapshot_as_of filtering

deterministic pagination

source-health interval reads

snapshot resource bounds
```

No evidence schema ownership change except if a proven read index is separately required and authorized.

## OPT-02A

Owns:

```text
tcp_syn/2 protocol-neutral schema

malformed-option preservation

p0f adapter

p0f conformance

TTL proof
```

## OPT-03A

Owns:

```text
actual CH experiment

field-by-field V2 admission

bounded Accept-CH lifecycle

clientHints teardown

portal source-health heartbeat

privacy proof
```

## OPT-SRC1

Owns:

```text
SourceBindingMap schema

source-health reconstruction policy

600s freshness semantics

expected-source topology
```

## OPT-KB1

Owns:

```text
Fingerbank static inspection

license/governance

freshness

canonical importer

DHCP-only CandidateSet semantics
```

## OPT-KB2A

Owns:

```text
p0f runtime/matcher conformance

oracle corpus

p0f grammar semantics
```

## OPT-KB2B

Owns:

```text
production TCP knowledge source selection

canonical import

freshness

claim grade
```

## OPT-KB3

Owns:

```text
IEEE MA-L/MA-M/MA-S import

assignment-org semantics

longest-prefix

U/L behavior

manufacturer mapping boundary

freshness/governance
```

## OPT-KB4

Owns:

```text
classification_taxonomy_v1

manufacturer IDs

model-family IDs

source aliases

out-of-scope semantics
```

---

# 113. Task-04 Decomposition After Foundation Closure

Only after:

```text
R4 architecture accepted

AND

mandatory pre-Task-04 proof gates PASS
```

TechLead11 may decompose Task-04.

Recommended decomposition:

```text
04A
Canonical KnowledgeBundle Foundation
+
importers
+
taxonomy
+
freshness

04B
EvidenceSnapshot
+
SourceBindingMap
+
source evaluability

04C
OriginAssessment adapters
+
origin purity
+
dedup/conflict

04D
Per-dimension Fusion Engine
+
support levels
+
out-of-scope handling

04E
Classification Persistence
+
read contract
+
audit provenance

04F
Optional external enrichment
default OFF

04G
Controlled local validation
```

Coder receives no Task-04 implementation work before that point.

---

# 114. Owner Actions Currently Required

Current bounded Owner-controlled proofs remain:

```text
O1

Authorize Fingerbank Community static DB
bounded download/inspection.

No production device evidence is submitted.


O2

Authorize controlled portal Accept-CH
acquisition + teardown experiment.

Raw hints remain non-durable.


O3

Authorize controlled sender/sensor TTL proof.

No production topology redesign.
```

Additional external source/legal acceptance is made only after actual artifact terms are inspected.

---

# 115. R4 Architecture Verdict

```text
DOCUMENT STATUS =
FOR OWNER + TECHLEAD11 STRICT REVIEW

ARCHITECTURE CONTRACT FINAL =
NO

R3 =
SUPERSEDED

TASK-04 =
HOLD

CODER =
HOLD

CODE =
NO

PRODUCTION CHANGE =
NO


tcp_syn/2 =
PROTOCOL-SEMANTIC FACTS ONLY

p0f semantics =
ADAPTER + K2A CONFORMANCE

production TCP knowledge =
K2B SEPARATE

p0f corpus =
NOT AUTOMATIC PRODUCTION TRUTH


classification_taxonomy_v1 =
FROZEN IN R4

Phase-1 device_class =
smartphone
tablet
laptop

recognized out-of-scope =
FIRST-CLASS SAFE STATE


manufacturer/model =
CANONICAL VERSIONED IDS

string equality =
NOT A FUSION CONTRACT


IEEE result =
MAC ASSIGNMENT ORGANIZATION

IEEE manufacturer claim =
ONLY THROUGH ACCEPTED MAPPING


OriginAssessment =
MANDATORY

origin purity =
MANDATORY

Fingerbank V1 fusion use =
DHCP-ONLY


external artifact =
IMPORT INPUT ONLY

runtime vendor-schema dependency =
FORBIDDEN


EvidenceSnapshot =
EXPLICIT WINDOW
+
EXPLICIT AS-OF
+
EXPLICIT SOURCE BINDING

hidden "latest N minutes" =
FORBIDDEN


pagination =
TO EXHAUSTION

partial first-page classification =
FORBIDDEN


persisted source health =
available
unavailable
unsupported

derived evaluability =
evaluable
partially_evaluable
not_evaluable
unknown


network health heartbeat =
300s

portal target heartbeat =
300s

source-health freshness maximum =
600s


knowledge freshness =
FIRST-CLASS

stale knowledge =
CAPPED / SOURCE-SPECIFIC

expired knowledge =
NO CLAIM


confidence semantic =
EVIDENCE SUPPORT / CORROBORATION

probability claim =
NO


Accept-CH =
BOUNDED LIFECYCLE

continuous high-entropy request =
NO


audit =
TWO LEVEL

EvidenceSnapshot → OriginAssessment
while Task-01 evidence survives

OriginAssessment → final classification
for classification-history retention


raw packets =
NO

raw UA =
NO

raw Client Hints =
NO


runtime required Internet =
ZERO
```

R4 becomes:

```text
ARCHITECTURE CONTRACT FINAL
```

only after explicit:

```text
OWNER ACCEPT
+
TECHLEAD11 ACCEPT
```

Operational proof gates may remain pending after architectural acceptance, but no gate semantics may remain undefined.

---