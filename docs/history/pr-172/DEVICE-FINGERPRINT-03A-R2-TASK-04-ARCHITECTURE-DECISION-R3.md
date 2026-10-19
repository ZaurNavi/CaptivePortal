# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R3

## Strongest Practical Passive Evidence Foundation Before Task-04

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-16  
**Status:** `ARCHITECTURE CONTRACT FINAL — OPERATIONAL PROOF GATES P1–P14 PENDING`  
**Task-04 decomposition:** `HOLD`  
**Coder:** `HOLD`  
**Code:** `NO`  
**Production change:** `NO`

---

# 1. TechLead11 Review Disposition

TechLead11 strict review is ACCEPTED.

R3 replaces superseded R2 wording instead of appending exceptions.

R3 freezes these architecture principles:

```text
NO approximate p0f dialect
NO ambiguous p0f_signature evidence field
NO blind reuse of tcp_syn/1 parser rejection semantics
NO first-row / best-guess Fingerbank static matching
NO row-count confidence
NO silent source outage semantics
NO JA4 heuristic classification without accepted reference knowledge
NO placeholder local KnowledgeBundle
NO unknown-license production source
```

Accepted prior principles remain:

```text
normalized evidence != classification != ground truth

offline-first classifier

Fingerbank Cloud not hard runtime dependency

Fingerbank Cloud default OFF

raw UA / raw Client Hints remain non-durable by default

no one-fingerprint-one-device

unknown / insufficient / conflict are valid outputs

same evidence interpreted by multiple knowledge systems
does not create multiple independent votes

no cross-MAC identity merge

classification cannot affect Authorization

classification DB separate from Task-01 evidence DB

KnowledgeBundles immutable / versioned / rollbackable
```

---

# 2. Current Production Foundation

Current production evidence families:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

Production acquisition / normalization / ingest is already end-to-end proven.

R3 does NOT reopen:

```text
Catalyst RSPAN design

AF_PACKET architecture

raw dedup architecture

Suricata EVE architecture

Task-01 envelope/API/security

Authorization flow
```

except bounded parser/schema changes strictly required for stronger evidence.

---

# 3. R3 Program Sequence

```text
TASK-01
DONE

TASK-02
DONE / production proven

TASK-03
DONE / production proven

        ↓

PRE-TASK-04 SOURCE OPTIMIZATION

OPT-02A
tcp_syn/2 packet-fact contract
+
p0f compatibility proof

OPT-03A
portal_headers/2 actual-flow CH value proof

OPT-KB1
Fingerbank static DB inspection
+
deterministic ambiguity-preserving DHCP matcher

OPT-KB2
p0f matcher model + pinned reference corpus

OPT-KB3
IEEE MA-L / MA-M / MA-S local registry import

        ↓

P1–P14 PASS

        ↓

03A-R2 ARCHITECTURE FINAL
operationally closed

        ↓

TECHLEAD11 TASK-04 DECOMPOSITION

        ↓

OWNER IMPLEMENTATION AUTHORIZATION
```

Task-04 remains HOLD until P1–P14 close.

---

# 4. tcp_syn/2 — Final Evidence-Layer Decision

`tcp_syn/2` SHALL persist normalized packet-derived facts only.

It MUST NOT persist:

```text
p0f_signature
p0f_rule
p0f_label
Fingerbank TCP string
OS guess
device guess
```

Evidence pipeline:

```text
eligible TCP SYN frame
        ↓
p0f-aware packet parser
        ↓
tcp_syn/2 normalized facts
        ↓
versioned p0f runtime serializer adapter
        ↓
runtime/Fingerbank representation

tcp_syn/2 normalized facts
        ↓
versioned p0f matcher input adapter
        ↓
p0f knowledge matcher
```

`p0f.fp` remains REFERENCE KNOWLEDGE.

It is never normalized observed evidence.

---

# 5. Honest tcp_syn/2 Scope

Initial V2 scope is frozen as:

```text
IPv4 only

outbound guest TCP SYN request

SYN=1
ACK=0 eligibility inherited from Task-02 raw capture scope

unfragmented IPv4 only

current pre-router RSPAN capture point

full frame structurally available to parser
```

Architecture claim is exactly:

```text
p0f-compatible IPv4 request fingerprinting
for the eligible Task-02 captured SYN subset
```

NOT:

```text
universal p0f parity
IPv6 parity
SYN-ACK parity
fragment reassembly parity
```

---

# 6. tcp_syn/2 Packet Facts

V2 MUST preserve enough packet-derived facts to generate p0f runtime input
without guessing.

Required normalized facts:

```text
ip_version = 4

observed_ttl

ip_option_length

ip_id

df_flag

reserved_ip_flag

ecn_ip_bits

tcp_window

tcp_window_scale_raw

mss

tcp_option_layout

tcp_option_parse_status

tcp_option_trailing_nonzero

tcp_sequence_zero

tcp_ack_number_nonzero

tcp_ack_flag

tcp_urg_pointer_nonzero

tcp_urg_flag

tcp_push_flag

tcp_ecn_flags

tcp_timestamp_value_zero

tcp_timestamp_echo_nonzero

tcp_payload_length

payload_class

p0f_quirks
```

Recommended reproducibility fields:

```text
ip_header_length
tcp_header_length
```

No raw frame persistence.

---

# 7. p0f-Aware Parser Semantics

`tcp_syn/2` MUST NOT blindly reuse V1 strict rejection rules.

Parser differentiates:

## A. structurally impossible / truncated

Examples:

```text
Ethernet/IP/TCP header truncated

IPv4 IHL below legal minimum

IP total length shorter than headers

TCP data offset below legal minimum

declared TCP option bytes extend beyond captured/full IP packet

frame cannot deterministically expose required bytes
```

Result:

```text
NO tcp_syn/2 evidence
parser telemetry
```

## B. structurally observable but abnormal

Examples:

```text
window scale > 14

malformed TCP option encoding that p0f fingerprints as bad

non-zero trailing option bytes

EOL padding

ACK number set without ACK flag

URG pointer anomaly

zero sequence

non-zero timestamp echo in initial SYN
```

Result:

```text
PRESERVE

derive p0f quirks

emit tcp_syn/2
```

No fingerprintable abnormal SYN silently disappears because V1 rejected it.

---

# 8. TCP Option Layout

V2 derives canonical observed option semantics directly from option bytes:

```text
eol+n
nop
mss
ws
sok
sack
ts
?<option-id>
```

Rules:

```text
EOL =
record eol+n
where n is exact remaining padding-byte count

unknown option =
?<numeric option id>

option order =
preserved exactly

non-zero trailing bytes =
also contribute opt+ quirk

malformed structure =
bad quirk when still structurally observable
```

No inferred rule wildcard.

---

# 9. p0f Quirks

For eligible IPv4 requests, derive every applicable p0f quirk from packet facts:

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

`flow` is IPv6-only and outside V2 initial scope.

Quirk order SHALL follow the pinned p0f implementation's canonical runtime
ordering.

Do not alphabetically invent an order.

---

# 10. Payload Class

Derived exactly:

```text
tcp_payload_length =
IPv4 total length
-
IP header length
-
TCP header length
```

Then:

```text
0 bytes
→ payload_class = "0"

>0 bytes
→ payload_class = "+"
```

No wildcard `*` in observed packet facts.

---

# 11. TTL / RSPAN Semantics — Architecture Theory

Current topology indicates an outbound guest SYN is mirrored before the separate
Cisco 3845 performs L3 forwarding.

Architectural expectation:

```text
sender-emitted TTL
==
sensor observed TTL

distance =
0
```

But R3 does NOT freeze this from topology alone.

Operational Gate P4 is mandatory.

---

# 12. TTL / RSPAN Runtime Proof Contract

P4 captures one controlled SYN and records:

```text
actual Catalyst monitor/RSPAN running configuration

source VLAN/interface

SPAN/RSPAN direction

controlled sender original SYN TTL

same SYN sensor enp8s0 TTL

packet correlation discriminator
```

Required:

```text
sender TTL == sensor TTL
```

Only after P4 PASS freeze for current capture placement:

```text
ttl_distance = 0

observed_ttl =
client-emitted TTL
```

Capture topology identity becomes part of the compatibility proof.

If capture placement/config later changes:

```text
P4 proof =
INVALIDATED

p0f TTL compatibility must be re-proven
```

---

# 13. Observed p0f Runtime Serialization

Observed normalized evidence and external string serialization remain separate.

Adapter:

```text
tcp_syn/2
→ p0f_runtime_ipv4_request_v1
```

It serializes the exact observed runtime form required by the selected external
contract.

For Fingerbank this MUST be proven separately.

No adapter assumes:

```text
64
==
64+0
```

or any equivalent spelling without an acceptance proof.

---

# 14. Fingerbank tcp_syn_signatures Compatibility

Fingerbank documents:

```text
tcp_syn_signatures
must follow p0f standard
```

and gives runtime-style example:

```text
4:128+0:0:1460:8192,2:mss,nop,ws,nop,nop,sok:df,id+:0
```

Therefore P5 requires a bounded synthetic API acceptance test.

Test matrix includes:

```text
observed TTL/distance representation

zero-distance spelling

option layout

quirk list

payload class
```

No production device data is required.

Only syntax/acceptance behavior is tested.

If Fingerbank requires:

```text
128+0
```

then adapter emits exactly that.

Task-02 evidence remains external-format-neutral.

---

# 15. p0f Knowledge Rules Are Separate

`p0f.fp` rule syntax includes matching semantics not present in observed runtime
facts:

```text
ver wildcard

MSS wildcard

window:
numeric
mss*N
mtu*N
%N
*

scale wildcard

generic vs specific labels

TTL variation

fuzzy quirk behavior
```

Therefore:

```text
observed runtime serialization
!=
p0f knowledge-rule serialization
```

No string equality matcher is permitted.

---

# 16. K2 Matcher Model Decision

R3 selects:

```text
MODEL 1:
versioned p0f-compatible local matcher
```

Reason:

```text
Task-04 needs deterministic in-process/offline claims

external process dependency is unnecessary

p0f matching grammar is finite and can be conformance-tested
```

However:

```text
NO PARTIAL CLONE MAY SHIP
```

The matcher is accepted only if it passes conformance against a pinned real p0f
engine within the exact supported IPv4 request scope.

If conformance fails:

```text
K2 FAIL

Task-04 remains HOLD
```

Do NOT ship approximate fallback.

---

# 17. K2 Golden Conformance Corpus

Mandatory corpus includes:

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

p0f fuzzy quirk behavior

specific vs generic signature precedence

MSS-derived MTU matching dependency

no-match case
```

For every fixture:

```text
CaptivPortal matcher result
==
pinned p0f engine result
```

Required equivalence includes:

```text
match / no-match

specific/generic selection

label/class/name/flavor

fuzzy status where applicable

distance/TTL interpretation
```

Any mismatch:

```text
P3 FAIL
```

---

# 18. Pinned p0f Reference Governance

K2 bundle records:

```text
p0f source version/commit

p0f.fp SHA256

matcher conformance corpus version

license_identifier

license source

attribution obligations

importer/parser version
```

Known age/currentness remains explicit metadata.

Exact matching correctness does NOT mean modern taxonomy completeness.

p0f claim default strength remains:

```text
supporting
```

unless a future evidence/validation contract proves otherwise.

---

# 19. Task-03 V2 — Candidate, Not Frozen Schema

R3 does NOT freeze unused high-entropy fields into `portal_headers/2`.

Permanent privacy:

```text
raw UA =
non-durable

raw Client Hints =
non-durable
```

Candidate hints:

```text
Sec-CH-UA-Model

Sec-CH-UA-Platform-Version

Sec-CH-UA-Form-Factors
```

A field enters V2 ONLY if real portal-flow Gate P6 proves material usable value.

Mostly-null / unsupported baggage is rejected from V2.

---

# 20. Task-03 Actual Portal-Flow Proof

P6 must prove on the real CaptivPortal flow:

```text
HTTPS / secure-context eligibility

exact response that emits Accept-CH

exact subsequent request carrying requested hints

no Authorization dependency

no redirect-loop regression

no portal-flow regression

missing-hint behavior
```

Controlled clients:

```text
Android Chromium

Android WebView / captive helper

Windows Chromium
```

When available:

```text
iOS / Safari
```

Browser non-support is recorded as normal behavior.

---

# 21. Client-Hint Secure Context Contract

High-entropy Client Hints are secure-context features and are requested with
`Accept-CH`.

The client may send them only on subsequent requests and may decline them.

Therefore:

```text
missing high-entropy CH
!= source failure
!= negative evidence
```

Task-03 V2 MUST NOT make Authorization wait for hints.

No retry loop to obtain them.

No JavaScript fallback fingerprinting.

---

# 22. Candidate CH Normalization

If P6 proves value, V2 may include ONLY normalized forms.

## Model

Candidate durable semantic:

```text
model_family_ch
```

using the same strict privacy grammar as current model-family normalization.

No raw header persistence.

## Platform version

Candidate:

```text
platform_version_major_ch
```

or another explicitly proven bounded normalized major semantic.

No raw full platform string persisted.

## Form factors

Only proven standard values that materially improve Phase-1 class are admitted.

Potential normalized set:

```text
mobile
tablet
desktop
```

Do not create an enum until actual P6 values are observed on supported clients.

---

# 23. Portal V2 Admission Rule

A candidate field enters final V2 only if all are true:

```text
actual supported client emits it in real portal flow

normalization is deterministic

value materially helps:
platform
device_class
manufacturer
or model

raw value remains transient

no auth/portal regression

missing value remains normal
```

If not:

```text
field omitted from V2
```

If all candidate fields fail material-value threshold:

```text
Task-03 remains portal_headers/1
```

This is an acceptable P6 outcome.

---

# 24. Concrete Local Knowledge Sources

Accepted V1 KnowledgeBundle minimum:

```text
K1 =
deterministic DHCP/device knowledge source

K2 =
pinned p0f reference set
+
conformant p0f matcher

K3 =
local portal semantic rules

K4 =
IEEE MAC Registry
MA-L + MA-M + MA-S
```

Optional:

```text
JA4DB

Fingerbank Cloud cache
```

Task-04 cannot start with a theoretical/empty bundle.

---

# 25. K1 Fingerbank Static DB — Current Required Gate

Fingerbank Community:

```text
/api/v2/download/db
```

is CURRENT bounded research, not future/deferred.

Public documentation establishes:

```text
SQLite3 artifact

attribute tables

device records

HTTP User-Agent excluded
```

Public PacketFence/Fingerbank integration demonstrates real local combination
matching concepts.

But production architecture SHALL NOT assume current downloadable schema.

P8 must inspect the actual current artifact.

---

# 26. P8 Fingerbank Static DB Inspection

Obtain an Owner-authorized current artifact.

No production device data is submitted.

Record:

```text
retrieved_at

artifact SHA256

HTTP metadata/version metadata if exposed

SQLite user_version

table list

view list

schema definitions

indexes

row counts

device hierarchy tables

DHCP fingerprint tables

DHCP vendor tables

TCP signature tables if present

combination/relationship tables/views

source version/date

license/terms references
```

Do not infer hidden scoring.

---

# 27. K1 Ambiguity-Preserving Matching

K1 MUST return:

```text
CandidateSet
```

not one guessed device.

Input example:

```text
dhcp_fingerprint
dhcp_vendor
```

Processing:

```text
observed attributes
        ↓
all deterministic compatible records
        ↓
all linked compatible device/taxonomy candidates
        ↓
per-dimension projection
```

Never:

```text
first SQL row
best row by undocumented ordering
most popular row
arbitrary single device
```

---

# 28. K1 Dimension Projection

For every dimension:

```text
platform_family
device_class
manufacturer_family
model_family
```

Projection works independently.

Example candidate set:

```text
Candidate A:
Android / smartphone

Candidate B:
Android / tablet
```

Result:

```text
platform_family =
android / resolved

device_class =
unknown / ambiguous
```

If candidate devices agree on manufacturer but disagree on model:

```text
manufacturer may resolve

model remains ambiguous
```

No proprietary Fingerbank Cloud score is recreated.

---

# 29. K1 Matching Pass Criteria

P9 passes only if local matching:

```text
is deterministic

returns all relevant compatible candidates

preserves ambiguity

does not depend on row order

does not reproduce undocumented Fingerbank scoring

projects taxonomy independently per dimension

has explicit no-match behavior
```

If static DB lacks deterministic relationships needed:

```text
K1 FAIL
```

No reverse-engineered approximate score.

---

# 30. K1 Fail Path

If Fingerbank static DB fails P8/P9:

```text
Task-04 remains HOLD
```

until a concrete alternative K1 source is selected.

Acceptable alternative must provide:

```text
real local DHCP/device reference content

version/digest

license governance

deterministic ambiguity-preserving matcher
```

No placeholder curated rules without an identified reference source.

---

# 31. K3 Portal Semantic Rules

K3 is concrete local knowledge over normalized portal evidence.

Examples:

```text
platform_family=android
→ direct platform claim android

platform_family=windows
→ direct platform claim windows

explicit model_family
→ direct model claim

proven normalized form-factor=tablet
→ direct/strong device-class claim tablet
```

Rules are:

```text
versioned

deterministic

local

privacy-safe
```

They do not use raw UA/CH.

---

# 32. K4 — IEEE MAC Registry

Add mandatory local source:

```text
IEEE_MAC_REGISTRY
```

Official public inputs:

```text
MA-L

MA-M

MA-S
```

Runtime performs:

```text
local lookup only
```

No external runtime request.

---

# 33. K4 MAC Eligibility

First inspect MAC U/L bit.

If:

```text
U/L bit = 1
```

then:

```text
locally administered / randomized

registry lookup =
NOT PERMITTED

manufacturer claim =
NONE
```

If:

```text
U/L bit = 0
```

then longest-prefix registry lookup is permitted.

No cross-MAC identity inference.

---

# 34. K4 Longest-Prefix Matching

Use all three IEEE assignment families.

Do NOT implement 24-bit OUI-only lookup.

Importer normalizes:

```text
prefix bits
prefix length
organization
registry family
```

Runtime:

```text
eligible global MAC
→ longest matching prefix
```

Longer matching assignment wins.

K4 may resolve only:

```text
manufacturer_family
```

It MUST NOT alone resolve:

```text
platform_family

device_class

model_family
```

---

# 35. K4 Source Governance

Bundle records:

```text
source =
official IEEE Registration Authority

registry families =
MA-L
MA-M
MA-S

download date

source digest

source version/date if exposed

importer version

license_identifier

license reference

redistribution status

attribution requirement

commercial-use status

review basis
```

Unknown legal status blocks production-bundle admission.

---

# 36. JA4 — Zero Meaning Without Reference Knowledge

Permanent:

```text
JA4 observed
!= platform claim

JA4 observed
!= device-class claim

JA4 observed
!= manufacturer claim
```

If active KnowledgeBundle contains no accepted JA4 mapping:

```text
tls OriginAssessment =
NO CLASSIFICATION CLAIM

quic OriginAssessment =
NO CLASSIFICATION CLAIM
```

JA4 remains normalized evidence for later enrichment.

Forbidden heuristic labels:

```text
Apple-like JA4
Android-like JA4
frequently seen JA4
```

unless backed by accepted versioned reference knowledge.

---

# 37. EvidenceSnapshot — Mandatory Source Health

EvidenceSnapshot MUST carry source-health context per classification window.

Required source-health states:

```text
available

degraded

unavailable

unknown
```

At minimum for:

```text
dhcp

tcp

tls

quic

portal
```

MAC registry is local bundle context and has separate bundle/source health.

---

# 38. Source Health Semantics

Permanent:

```text
source unavailable
!= negative evidence

source unavailable
!= conflict

source unknown
!= negative evidence
```

Unavailable source contributes:

```text
NO CLAIM
```

Explainability distinguishes:

```text
healthy source + no evidence observed

from

source unavailable, therefore not evaluable
```

---

# 39. OriginAssessment Layer

Before multi-origin fusion, each origin group produces exactly one bounded:

```text
OriginAssessment
```

Required groups:

```text
dhcp

portal

tcp

tls

quic

mac_registry
```

No individual evidence row votes directly in cross-origin fusion.

---

# 40. OriginAssessment Contract

Each OriginAssessment contains:

```text
origin_group

source_health

evidence_count

semantic_variant_count

dimension_assessments

origin_conflict

explanation_codes

reference_ids
```

Each dimension assessment can be:

```text
claim resolved

ambiguous

conflicting

no_claim

not_evaluable
```

---

# 41. Same-Origin Dedup / Consolidation

Permanent:

```text
N DHCP records != N DHCP votes

N TCP SYNs != N TCP votes

N JA4 events != N TLS votes

N portal events != N portal votes
```

Within one origin:

```text
semantic duplicates
→ collapse

compatible claims
→ consolidate

different but non-conflicting observations
→ preserve as variant context

contradictory claims
→ origin conflict
```

No confidence based on row count.

No majority by packet count.

---

# 42. mac_registry Origin Semantics

`mac_registry` is independent as a manufacturer-reference origin only.

It derives from the current MAC context, but:

```text
must never be interpreted as physical identity confidence
```

It can contribute only to:

```text
manufacturer_family
```

and only when MAC is globally administered.

It cannot strengthen:

```text
platform
device class
model
```

---

# 43. Multi-Origin Fusion

Fusion consumes:

```text
one OriginAssessment per origin group
```

not raw evidence rows.

Independent groups:

```text
dhcp
portal
tcp
tls
quic
mac_registry
```

Knowledge sources that interpret the same evidence remain inside that origin.

Example:

```text
Fingerbank DHCP
+
local DHCP reference

→ one DHCP OriginAssessment
```

---

# 44. Per-Dimension Results

Required output dimensions:

```text
platform_family

device_class

manufacturer_family

model_family
```

Each independently has:

```text
value

status

confidence

confidence_level

origin_groups_used

conflicting_origins

not_evaluable_origins

explanation_codes

external_reference_ids
```

Status:

```text
resolved

unknown

insufficient_evidence

conflicting_evidence
```

---

# 45. Per-Dimension Confidence

Ordinal only:

```text
0 = none
1 = low
2 = medium
3 = high
```

No fake probability.

For each dimension:

## HIGH

```text
>=2 independent evaluable origins

agreeing direct/strong claims

no direct/strong conflict
```

## MEDIUM

```text
one independent direct/strong origin
no direct/strong conflict
```

Supporting origins may corroborate but do not manufacture a second strong vote.

## LOW

```text
supporting/weak claims only
without stronger contradiction
```

## NONE

```text
no usable claim
or unresolved conflict
```

Unavailable origins are excluded from claim counting.

---

# 46. Conflict Isolation

Conflict is per dimension.

Example:

```text
platform:
portal = windows
dhcp = android

device class:
portal = tablet
dhcp candidates all = tablet
```

Valid output:

```text
platform =
unknown / conflicting_evidence / none

device_class =
tablet / resolved / high or medium
according to independent origin strength
```

A conflict in one dimension MUST NOT erase unrelated dimensions.

---

# 47. Global Summary

Top-level may contain:

```text
classification_status

overall_confidence_level
```

but both are derived summaries only.

They MUST NOT replace per-dimension results.

Possible top-level status:

```text
classified

partial

unknown

insufficient_evidence

conflicting_evidence
```

---

# 48. Classification Output Contract

Minimum:

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

knowledge_bundle_id

evidence_window_start

evidence_window_end

evidence_digest

source_health_summary

classified_at
```

Each dimension result uses section 44 contract.

No raw acquisition data.

---

# 49. Classification Storage

Accepted:

```text
SEPARATE CLASSIFICATION SQLITE
```

not Task-01 evidence DB.

Reason remains:

```text
normalized evidence
!= derived classification

Task-01 repository owns its exact schema boundary
```

Task-04 storage failure never affects Authorization.

---

# 50. Actionable Knowledge Source Governance

Replace vague:

```text
license_status
```

with:

```text
license_identifier

license_source_reference

license_text_digest
if license text is bundled

redistribution_status

attribution_required

modification_status

commercial_use_status

reviewed_at

review_basis
```

Also retain:

```text
source_name

source_version

retrieved_at

source_digest

importer_version
```

Unknown legal status:

```text
SOURCE NOT ADMITTED
to accepted production KnowledgeBundle
```

---

# 51. K2 Licensing

Pinned p0f reference data must retain its actual LGPL provenance and obligations.

Bundle admission requires release-review metadata from section 50.

No stripping attribution/license provenance.

---

# 52. K1 Licensing

Fingerbank static artifact cannot enter a production KnowledgeBundle until P8
captures the actual applicable terms for:

```text
local storage

modification/import

production use

redistribution if relevant

commercial use
```

Unknown:

```text
K1 NOT ADMITTED
```

---

# 53. KnowledgeBundle Final Minimum

Before Task-04 decomposition, accepted V1 offline KnowledgeBundle must have
concrete admitted sources:

```text
K1 =
accepted deterministic DHCP/device source

K2 =
accepted p0f matcher
+
pinned request fingerprint reference set

K3 =
accepted local portal semantic rules

K4 =
accepted IEEE MA-L/MA-M/MA-S manufacturer registry
```

Optional:

```text
JA4DB

Fingerbank Cloud cache
```

No theoretical empty bundle.

---

# 54. KnowledgeBundle Immutability

Each accepted bundle:

```text
knowledge_bundle_id

schema version

created_at

content SHA256

taxonomy mapping version

source manifests

source governance metadata
```

Activation:

```text
candidate
→ validate
→ gates/local checks
→ accept
→ atomic activate
```

Keep current + previous accepted bundle.

Failed refresh never removes current bundle.

---

# 55. LOCAL_ONLY Runtime

Runtime classifier depends on:

```text
Task-01 normalized evidence read

accepted local KnowledgeBundle

Task-04 classification DB
```

It has:

```text
ZERO required external network dependency
```

Fingerbank/IEEE/p0f artifacts are imported beforehand.

IEEE runtime lookup is local.

---

# 56. Fingerbank Cloud

Still optional:

```text
default OFF
```

If later enabled:

```text
background enrichment only

never Authorization path

never synchronous classifier dependency
```

No production architectural dependence on Cloud.

---

# 57. Portal / Authorization Isolation

Task-03 V2 candidate experiment MUST NOT make:

```text
Accept-CH availability

CH return timing

hint support

normalization success
```

a dependency of:

```text
Authorization

portal rendering

CAPPORT result
```

Failure means:

```text
no enriched portal claim
```

only.

---

# 58. P1 — tcp_syn/2 Packet-Fact Completeness

PASS requires controlled fixtures prove V2 can preserve every packet fact needed
for supported IPv4 p0f request fingerprinting.

Must include fingerprintable abnormalities.

No V1-style silent reject.

---

# 59. P2 — p0f Runtime Serializer Conformance

Compare V2 → runtime serializer to the pinned p0f engine output.

PASS requires exact supported-scope agreement on:

```text
version

TTL/distance representation

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

# 60. P3 — p0f Matcher Conformance

Pinned real p0f engine is the oracle.

Golden corpus MUST include:

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

fuzzy quirk behavior

specific vs generic precedence

no-match
```

For every fixture:

```text
CaptivPortal matcher result
==
p0f result
```

Any mismatch:

```text
FAIL
```

---

# 61. P4 — Actual TTL/RSPAN Equality

Runtime proof from current environment.

Required:

```text
actual SPAN/RSPAN running config

source VLAN/interface/direction

controlled sender SYN TTL

correlated sensor enp8s0 SYN TTL
```

PASS:

```text
sender TTL == sensor TTL
```

Only after PASS:

```text
distance = 0
```

for current topology.

---

# 62. P5 — Fingerbank TCP Syntax Acceptance

Use synthetic API input.

No production device data.

Prove exact accepted representation for zero-distance TTL, including whether
Fingerbank requires runtime form such as:

```text
128+0
```

PASS only when adapter output is accepted without fabricated fields.

---

# 63. P6 — Portal CH Actual-Flow Value

Real controlled CaptivPortal flow must prove:

```text
secure HTTPS context

exact Accept-CH response

subsequent request

Android Chromium

Android WebView/captive helper

Windows Chromium

non-support behavior

no auth dependency

no redirect loop

no portal regression
```

Each candidate CH field is accepted individually only if materially useful.

---

# 64. P7 — Portal CH Privacy

PASS requires:

```text
raw CH never durable

raw CH never logged

raw CH never queued

normalized bounded values only

missing hints normal

no JS fingerprint fallback
```

---

# 65. P8 — Fingerbank Static DB

Inspect real authorized current Community DB.

PASS/fail records:

```text
schema

tables/views

device hierarchy

DHCP fingerprint content

DHCP vendor content

TCP content if any

relationship structure

artifact version/digest

actionable license governance
```

No production data submission.

---

# 66. P9 — Ambiguity-Preserving DHCP Matching

PASS requires fixtures where:

```text
one DHCP fingerprint maps to multiple candidates
```

and verifies independent projection.

Example:

```text
all candidates Android
classes differ

→ platform Android
→ device_class ambiguous
```

No first-row selection.

No hidden score recreation.

---

# 67. P10 — IEEE Registry Import

Import official:

```text
MA-L

MA-M

MA-S
```

PASS requires:

```text
all three families represented

longest-prefix match

U/L bit policy

globally administered known fixture resolves

locally administered fixture returns no manufacturer claim

source digest/governance recorded
```

No runtime Internet lookup.

---

# 68. P11 — Offline KnowledgeBundle Sufficiency

PASS requires concrete accepted:

```text
K1

K2

K3

K4
```

with:

```text
content

version/digest

importer

taxonomy mapping

actionable license governance
```

Cloud disabled.

---

# 69. P12 — Origin Dedup / Conflict

Fixtures prove:

```text
100 identical DHCP rows
!= 100 votes

many repeated JA4 rows
!= many votes

same-origin contradictory variants
→ one origin conflict

same evidence interpreted by two knowledge sources
→ one origin assessment
```

No packet-count confidence.

---

# 70. P13 — Source Health Semantics

Fixtures prove:

```text
source unavailable
→ not_evaluable
→ no negative claim
→ no conflict

healthy/no evidence
→ no evidence observed

unknown source health
→ explicitly unknown
```

Explanation distinguishes each state.

---

# 71. P14 — Zero Network Dependency

Block all external network access.

With accepted K1–K4 bundle:

```text
classification still runs deterministically

IEEE lookup local

p0f lookup local

DHCP lookup local

portal rules local
```

No Fingerbank Cloud requirement.

PASS required before Task-04 decomposition.

---

# 72. Failure Policy

Failure of P1–P14:

```text
NO SILENT FALLBACK

NO APPROXIMATE REPLACEMENT

NO RENAMED HALF-COMPATIBILITY

NO "TEMPORARY" EMPTY KNOWLEDGE SOURCE
```

Result:

```text
RETURN TO ARCHITECT + TECHLEAD11
```

Task-04 remains HOLD.

---

# 73. Revised Task Boundaries

## OPT-02A

Owns:

```text
tcp_syn/2 evidence contract

p0f-aware parser

runtime serializer adapter contract

TTL proof

p0f conformance
```

## OPT-03A

Owns:

```text
actual portal CH experiment

field-by-field value decision

portal_headers/2 only if justified

privacy proof
```

## OPT-KB1

Owns:

```text
Fingerbank static artifact inspection

ambiguity-preserving DHCP/device matcher contract

license governance
```

## OPT-KB2

Owns:

```text
p0f reference pinning

matcher grammar

conformance corpus

license governance
```

## OPT-KB3

Owns:

```text
IEEE MA-L/MA-M/MA-S importer

longest-prefix matcher

U/L semantics

license/source governance
```

No Coder implementation task for Task-04 until these source optimization
contracts and operational gates close.

---

# 74. Task-04 After P1–P14

Only after P1–P14 PASS does TechLead11 decompose:

```text
04A KnowledgeBundle Foundation

04B Evidence → OriginAssessment adapters

04C Per-dimension Fusion Engine

04D Classification Persistence + Read

04E Optional External Enrichment

04F Local Validation
```

The prior direct `Evidence → claim rows → fusion` architecture is superseded by:

```text
Evidence rows
→ OriginAssessment
→ per-dimension fusion
```

---

# 75. Local Validation

No fixed physical-device count blocker.

Use currently available controlled devices.

At minimum known examples already available can validate:

```text
Android smartphone

Windows laptop
```

High-confidence incorrect primary dimension:

```text
FAIL
```

Safe unknown/insufficient output remains acceptable.

No local validation sample auto-trains production rules.

---

# 76. Genuinely Unresolved Owner Decisions

Only decisions requiring Owner action now:

## O1 — authorize Fingerbank Community static DB bounded download/inspection

Needed for P8/P9.

No production device evidence is submitted.

## O2 — authorize bounded controlled portal Accept-CH experiment

Needed for P6/P7.

Raw CH remains non-durable.

## O3 — authorize bounded controlled TTL sender/sensor equality proof

Needed for P4.

Read/capture proof only; no production config redesign.

Other legal/source acceptance decisions are made after actual artifact terms are
available.

Classification retention can wait for Task-04 FINAL.

---

# 77. R3 Architecture Verdict

```text
ARCHITECTURE CONTRACT =
FINAL

KNOWN SEMANTIC AMBIGUITY =
NONE IN DESIGN CONTRACT

OPERATIONAL PROOF GATES =
P1–P14 PENDING

tcp_syn/2 =
PACKET FACTS ONLY

p0f observed runtime serialization =
ADAPTER

p0f knowledge rules =
KNOWLEDGE LAYER

p0f matcher =
MODEL 1
LOCAL VERSIONED MATCHER
MANDATORY REAL-p0f CONFORMANCE

TCP V2 SCOPE =
IPv4 outbound guest
unfragmented request SYN
eligible Task-02 subset

TTL =
NOT FROZEN UNTIL P4

portal_headers/2 =
CANDIDATE
FIELD-BY-FIELD ADMISSION AFTER P6/P7

Fingerbank static DB =
CURRENT REQUIRED K1 RESEARCH

Fingerbank matching =
AMBIGUITY-PRESERVING

IEEE MA-L/MA-M/MA-S =
MANDATORY K4

JA4 WITHOUT REFERENCE =
ZERO CLASSIFICATION CLAIM

OriginAssessment =
MANDATORY

SOURCE HEALTH =
MANDATORY SNAPSHOT CONTEXT

PER-DIMENSION RESULT/CONFIDENCE =
MANDATORY

OFFLINE K1+K2+K3+K4 BUNDLE =
MANDATORY BEFORE TASK-04

TASK-04 DECOMPOSITION =
HOLD

CODER =
HOLD

CODE =
NO

PRODUCTION CHANGE =
NO
```

---

# 78. Research Basis

p0f reference contract:

```text
official/current public p0f repository documentation

TCP syntax:
ver:ittl:olen:mss:wsize,scale:olayout:quirks:pclass

rule semantics include:
mss*N
mtu*N
%N
wildcards
generic/specific
fuzzy quirks
TTL variation
```

Fingerbank reference contract:

```text
tcp_syn_signatures =
p0f-standard array

documented example uses:
4:128+0:...

download/db =
SQLite attributes + devices
```

IEEE reference:

```text
official IEEE Registration Authority public:
MA-L
MA-M
MA-S
```

Client Hints reference:

```text
Model
Platform-Version
Form-Factors
are secure-context / high-entropy client hints

Accept-CH requests them for subsequent requests

support is browser-dependent
```

---

# 79. Current Control Status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R3

ARCHITECTURE CONTRACT =
FINAL

CURRENT NEXT =
OWNER / TECHLEAD11 REVIEW

THEN =
bounded P1–P14 source optimization proofs

TASK-04 TECHNICAL DECOMPOSITION =
HOLD

CODER =
HOLD

NO CODE

NO CODER TASK

NO PRODUCTION CHANGE
```

**End of DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R3.**
