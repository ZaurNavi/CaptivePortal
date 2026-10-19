# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R2

## Pre-Task-04 Source Optimization + Concrete Offline Knowledge Baseline

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-15  
**Status:** `FOR OWNER + TECHLEAD11 REVIEW`  
**Code:** `NO`  
**Coder task:** `NO`  
**Production change:** `NO`  
**Task-04 decomposition:** `HOLD UNTIL PRE-TASK-04 SOURCE OPTIMIZATION IS CLOSED`

---

# 1. TechLead11 Review Disposition

TechLead11 review is accepted.

R1 conclusions that are REVISED:

```text
OLD:
tcp_syn/1 is not exact p0f
→ keep permanent reduced local dialect

R2:
reopen Task-02 TCP evidence
→ prefer bounded tcp_syn/2 if exact p0f compatibility is technically valid
```

```text
OLD:
Task-03 low-entropy evidence is frozen

R2:
reopen only bounded normalized Client-Hints enrichment
where classifier value is materially better
without durable raw headers
```

```text
OLD:
LOCAL_ONLY is mandatory
while concrete offline knowledge content is still deferred

R2:
concrete offline KnowledgeBundle sources
must be proven BEFORE Task-04 decomposition
```

```text
OLD:
one global result confidence can summarize the classification

R2:
confidence/result/conflict is first-class PER DIMENSION
```

Accepted principles retained:

```text
normalized evidence != classification != ground truth

offline-first

Fingerbank Cloud not a hard runtime dependency

Fingerbank Cloud default OFF

raw UA / raw Client Hints non-durable by default

no one-fingerprint-one-device assumption

JA4 / QUIC JA4 supporting only

unknown / insufficient / conflict valid

same evidence interpreted by multiple knowledge systems
!= multiple independent votes

no cross-MAC identity merge

classification failure cannot affect Authorization

classification DB separate from Task-01 evidence DB

knowledge bundles immutable/versioned/rollbackable
```

---

# 2. Current Source Baseline

Fresh architecture-time repository baseline:

```text
main HEAD =
d37d3ec126ccd512fe835af0db21221e2f83d565

main TREE =
3145e904ad5027d0d584945f4814f3ade59d44ea
```

Current production schemas:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

Current source acquisition layer is production-proven and remains the base.

Pre-Task-04 optimization MUST remain bounded to evidence fields that materially
improve classification.

No RSPAN redesign.

No AF_PACKET redesign.

No Task-01 envelope redesign.

No Suricata architecture redesign.

---

# 3. tcp_syn/2 Decision

## 3.1 Decision

R2 chooses:

```text
tcp_syn/2 =
RECOMMENDED PRE-TASK-04 SOURCE UPGRADE
```

provided the bounded implementation proof confirms exact deterministic
p0f-request signature serialization from the already observed full SYN frame.

Historical:

```text
tcp_syn/1
```

remains valid and readable.

No destructive migration.

New rows after explicit upgrade may use:

```text
tcp_syn/2
```

Task-04 should prefer v2 when available and degrade to v1 supporting semantics
for historical rows.

---

# 4. Exact p0f SYN Signature Contract

p0f v3 canonical TCP request signature syntax:

```text
ver:ittl:olen:mss:wsize,scale:olayout:quirks:pclass
```

A true `tcp_syn/2` MUST preserve enough normalized facts to serialize this
without guessing.

Required V2 normalized fields:

```text
ip_version

initial_ttl

ip_option_length

mss

tcp_window

window_scale

tcp_option_layout

quirks

payload_class

p0f_signature
```

Recommended additional reproducibility fields:

```text
observed_ttl

ttl_distance

tcp_header_length

tcp_payload_length
```

`p0f_signature` is canonical derived normalized evidence.

No raw frame persistence.

---

# 5. p0f Option Layout

V2 MUST preserve p0f-compatible option layout semantics, not only numeric option
IDs.

Required canonical tokens include:

```text
eol+n
nop
mss
ws
sok
sack
ts
?<unknown-option-id>
```

Current `tcp_option_order` from v1 is insufficient because p0f distinguishes
padding after EOL and semantic option names.

V2 parser therefore must derive:

```text
tcp_option_layout
```

directly from the already visible TCP options bytes.

No new capture source is required.

---

# 6. p0f Quirks Required

V2 parser MUST deterministically derive all p0f request quirks that are
representable from the current full IPv4 SYN frame:

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

IPv6 `flow` is outside initial V2 if Task-02 remains IPv4-only.

If IPv6 is not added, exact V2 contract is:

```text
p0f-compatible IPv4 SYN request signature
```

not a false claim of IPv6 parity.

---

# 7. p0f Payload Class

Current raw parser receives full packet bytes and IPv4 total length.

V2 MUST compute:

```text
tcp_payload_length =
ip_total_length - ip_header_length - tcp_header_length
```

Then:

```text
payload_class =
"0" if zero
"+" if non-zero
```

No wildcard is used for observed evidence.

---

# 8. IP Option Length

For IPv4:

```text
ip_option_length =
IHL_bytes - 20
```

This is directly observable from the SYN packet.

No new acquisition path is needed.

---

# 9. TTL / RSPAN Semantics Proof

This is now architecturally proven for the current production topology.

Current path:

```text
client on VLAN20
        ↓
Catalyst source VLAN20
        ↓
RSPAN copy
        ↓
sensor enp8s0
```

L3 gateway/router is the separate Cisco 3845.

Cisco SPAN documentation states ingress/source-VLAN traffic is copied before
device modification/processing.

IPv4 TTL is decremented by a router when forwarding.

Therefore the outbound guest SYN is copied on VLAN20 before it reaches the
separate L3 router that would decrement TTL.

Freeze for current topology:

```text
observed_ttl =
client-emitted initial TTL

ttl_distance =
0

initial_ttl =
observed_ttl
```

This rule is valid only for the current RSPAN capture placement.

If future capture placement moves downstream of an L3 hop:

```text
this TTL rule MUST be re-evaluated
```

---

# 10. p0f Signature Serialization Rule

For current IPv4 pre-router capture:

```text
ittl =
str(initial_ttl)
```

Do NOT serialize:

```text
observed+distance
```

when distance is known zero.

Example conceptual output:

```text
4:64:0:1460:64240,7:mss,sok,ts,nop,ws:df,id+:0
```

The exact signature content comes only from packet facts.

No wildcard normalization such as:

```text
mss=*
wsize=mss*X
```

belongs in raw observed evidence unless separately derived by an explicit
knowledge-rule layer.

V2 stores the exact observed p0f-compatible raw signature form.

---

# 11. Fingerbank TCP Compatibility Decision

Fingerbank accepts:

```text
tcp_syn_signatures
```

in p0f-standard form.

If `tcp_syn/2` passes fixture comparison against p0f canonical output:

```text
CaptivPortal tcp_syn/2.p0f_signature
→ Fingerbank tcp_syn_signatures
COMPATIBILITY = YES
```

This is preferred over maintaining a permanent reduced `cp_tcp_syn_v1`
dialect.

`tcp_syn/1` remains:

```text
historical supporting fallback
```

---

# 12. Required tcp_syn/2 Calibration Gate

Before implementation FINAL:

Use bounded controlled SYN fixtures captured through the real RSPAN path.

For each fixture compare:

```text
CaptivPortal proposed serializer
vs
p0f canonical raw_sig
```

Required exact agreement on:

```text
ver
ittl
olen
mss
wsize
scale
olayout
quirks
pclass
```

At minimum include:

```text
normal Linux/Android-style SYN
Windows-style SYN
EOL/padding case
unknown TCP option case if fixture available
ECN case
timestamp case
non-zero payload synthetic unit fixture
```

If exact agreement cannot be reached from current packet bytes:

```text
STOP
→ TechLead11 / Architect review
```

Do not silently revert to approximate p0f labeling.

---

# 13. Task-03 Reassessment

R2 keeps:

```text
durable raw User-Agent = NO
durable raw Client Hints = NO
```

but accepts a bounded normalized enrichment assessment.

Client Hint entropy matters:

Low-entropy current defaults:

```text
Sec-CH-UA
Sec-CH-UA-Mobile
Sec-CH-UA-Platform
```

Higher-entropy hints generally require:

```text
Accept-CH
```

and browser support is not universal.

---

# 14. Task-03 Enrichment Decision

R2 recommends a new:

```text
portal_headers/2
```

with normalized-only optional enrichment for exactly:

```text
Sec-CH-UA-Model

Sec-CH-UA-Platform-Version

Sec-CH-UA-Form-Factors
```

Do NOT add by default:

```text
Sec-CH-UA-Arch

Sec-CH-UA-Bitness

Sec-CH-UA-Full-Version-List

Sec-CH-UA-WoW64
```

Rationale:

```text
Model
→ materially useful for model/manufacturer-family resolution

Platform-Version
→ useful OS-version family corroboration
when reduced UA is weak

Form-Factors
→ directly relevant to smartphone/tablet/laptop class

Arch / Bitness
→ comparatively low Phase-1 classification value

Full-Version
→ high detail / low device-class value
```

---

# 15. Portal V2 Privacy Contract

Raw new headers remain:

```text
request-lifetime only

not queued

not logged

not persisted

not hashed as a durable correlator
```

V2 stores only bounded normalized values.

Proposed additional durable fields:

```text
client_hint_model_family

client_hint_platform_version_major

client_hint_form_factors

client_hint_model_present

client_hint_platform_version_present

client_hint_form_factors_present
```

Exact names remain TechLead implementation-contract detail.

No raw strings outside normalization.

---

# 16. Model Normalization

`Sec-CH-UA-Model` may contain a device model string.

V2 should reuse the existing `model_family` privacy grammar:

```text
bounded
printable
no MAC-like
no UUID-like
no Build ID
no raw fragment
```

If both:

```text
UA-derived model_family
and
CH-derived model
```

exist:

```text
preserve provenance
do not silently overwrite conflict
```

Task-04 can detect agreement/conflict.

---

# 17. Platform-Version Normalization

Do NOT store full raw platform-version string.

Recommended V2 durable value:

```text
platform_version_major =
integer | null
```

or, if a specific platform requires a bounded semantic token:

```text
normalized major only
```

This is enough for Phase-1 OS-family/version corroboration.

Do NOT create a universal OS marketing-version conversion unless separately
proven.

---

# 18. Form-Factor Normalization

`Sec-CH-UA-Form-Factors` can explicitly include values such as:

```text
Mobile
Tablet
Desktop
```

V2 maps only known relevant Phase-1 tokens:

```text
mobile
tablet
desktop
```

Other standardized form factors may be retained as:

```text
other_known
```

only if the schema explicitly needs them; otherwise ignored for V1.

This signal can materially improve:

```text
smartphone vs tablet vs laptop
```

but remains client-declared evidence, not ground truth.

---

# 19. Accept-CH Operational Boundary

High-entropy hint collection changes response behavior.

Therefore Task-03 V2 MUST explicitly define:

```text
which portal response(s) emit Accept-CH
```

and MUST NOT globally emit it on arbitrary routes.

Recommended scope:

```text
eligible portal-entry origin only
```

The browser may provide hints only on subsequent requests.

Therefore V2 collection must tolerate:

```text
first request =
no high-entropy hints

later eligible request =
hints present
```

Missing hints are normal, not source failure.

---

# 20. Task-03 V2 Research Gate

Before implementation FINAL, use controlled:

```text
Android Chromium/WebView
Windows Chromium
```

and, when available:

```text
iOS/Safari
```

to determine actual support.

Measure:

```text
which hints are returned
which portal request carries them
WebView vs normal-browser difference
model usefulness
platform-version usefulness
form-factor usefulness
```

If a recommended hint is not reliably available on a target browser family:

```text
keep it optional
```

Do not block Task-04 on universal CH support.

---

# 21. Concrete Offline KnowledgeBundle Requirement

R2 accepts TechLead11's criticism:

```text
LOCAL_ONLY mandatory
+
no concrete local knowledge
=
incomplete architecture
```

Therefore Task-04 decomposition remains HOLD until at least one real local
knowledge baseline is technically proven.

---

# 22. Concrete V1 Offline Knowledge Sources

R2 proposes a multi-source local bundle:

## Source K1 — Fingerbank Community Static DB

Primary DHCP/device taxonomy candidate:

```text
/api/v2/download/db
```

Public documentation confirms:

```text
SQLite3
attribute tables
device tables
HTTP User-Agent excluded
```

PacketFence public Fingerbank integration demonstrates real local DB matching
using:

```text
DHCP_Fingerprint
DHCP_Vendor
User_Agent
MAC_Vendor
DHCP6_Fingerprint
DHCP6_Enterprise
```

through combination/device tables and local exact/fuzzy matching views.

K1 is the preferred V1 DHCP knowledge source IF the current downloaded DB
inspection gate passes.

## Source K2 — p0f `p0f.fp`

Concrete local TCP reference source.

License in current p0f fingerprint file:

```text
GNU LGPL
```

Use only:

```text
[tcp:request]
```

signatures that can be exactly matched from `tcp_syn/2`.

Treat age/currentness as metadata.

Do not make p0f alone authoritative.

## Source K3 — Local Portal Deterministic Rules

Concrete built-in rules over `portal_headers/1` and optional `/2`.

Examples:

```text
platform_family=android
→ platform android direct claim

form_factor=tablet
→ device_class tablet direct/strong client claim
```

These are local deterministic semantic mappings, not learned world knowledge.

## Source K4 — Optional JA4DB Snapshot

Supporting only.

Not required for initial V1 bundle if licensing/download gate is unresolved.

---

# 23. Fingerbank Static DB Research Disposition

Status:

```text
CURRENT REQUIRED RESEARCH GATE
NOT DEFERRED
```

What public evidence proves now:

```text
download/db exists

returns SQLite3

contains attributes + devices

excludes HTTP User-Agent

PacketFence local Fingerbank source performs local combination matching
against upstream/local SQLite schemas

device hierarchy/score information is used by PacketFence
```

What cannot be certified from public documentation alone:

```text
exact current downloadable table list

exact current column layout

whether tcp_syn_signatures are included in community download/db

exact current combination-match views/indexes

exact redistribution/storage terms for this current downloadable artifact

whether community DB contains enough current device rows
for our Phase-1 taxonomy
```

Therefore R2 does NOT pretend these are known.

---

# 24. Fingerbank Static DB Mandatory Inspection Gate

Before Task-04 TechLead decomposition, obtain one authorized current Community
`download/db` artifact.

Required inspection is read-only/offline.

Record:

```text
retrieved_at

HTTP metadata if provided

file SHA256

SQLite user_version

SQLite table names

view names

CREATE TABLE / CREATE VIEW schemas

row counts

attribute table families

device table hierarchy

DHCP fingerprint rows

DHCP vendor rows

TCP signature rows if present

combination relation structure

version metadata

license/terms reference
```

No production evidence is submitted.

If an API key/terms acceptance is needed:

```text
Owner must authorize that bounded external download
```

---

# 25. Fingerbank Static DB Pass Criteria

K1 PASS requires:

```text
DHCP fingerprint knowledge exists

DHCP vendor knowledge exists

device hierarchy/taxonomy exists

matching relation between attributes and devices is reconstructable
without reverse-engineering a proprietary black-box score

local exact matching can be implemented deterministically

license/storage use is acceptable

bundle refresh/version can be identified
```

TCP presence is desirable after `tcp_syn/2` but NOT required for K1 PASS because
K2 provides TCP reference knowledge.

If K1 PASS:

```text
Fingerbank static DB
becomes primary offline DHCP/device taxonomy source
```

---

# 26. Fingerbank Static DB Fail Path

If current Community DB lacks adequate DHCP/device matching content or legal use
cannot be established:

```text
K1 = REJECTED
```

Concrete fallback V1 bundle remains:

```text
K2 p0f TCP reference
+
K3 portal deterministic rules
+
local curated DHCP rule pack
derived from explicitly licensed/public DHCP references
```

However:

```text
Task-04 decomposition remains HOLD
until that curated DHCP reference source is concretely selected,
versioned and license-reviewed
```

The architecture will not declare an empty offline knowledge bundle sufficient.

---

# 27. Fingerbank Cloud Role After Static DB Research

Cloud remains optional regardless of K1 result.

Default:

```text
OFF
```

Possible later use:

```text
knowledge refresh/enrichment
unknown signature investigation
```

Runtime classifier MUST never require it.

---

# 28. KnowledgeBundle V1 Content

An accepted V1 bundle contains at least:

```text
taxonomy_mapping

portal semantic rules

p0f TCP request signatures

one concrete DHCP/device reference source
```

Optional:

```text
JA4DB supporting mappings
cached Fingerbank Cloud enrichment
```

Every source entry records:

```text
source_name
source_version
retrieved_at
source_digest
license_status
importer_version
enabled
```

Bundle itself records:

```text
knowledge_bundle_id
knowledge_schema_version
content_sha256
taxonomy_mapping_version
compatibility_version
created_at
```

---

# 29. Per-Dimension Result Model

Task-04 output MUST represent each target dimension independently.

Required dimensions:

```text
platform_family
device_class
manufacturer_family
model_family
```

Each dimension has:

```text
value

status

confidence

confidence_level

evidence_sources_used

conflicting_sources

explanation_codes
```

Dimension status:

```text
resolved
unknown
insufficient_evidence
conflicting_evidence
```

---

# 30. Per-Dimension Confidence

Each dimension independently uses:

```text
confidence =
0 | 1 | 2 | 3

confidence_level =
none | low | medium | high
```

Example valid result:

```text
platform_family:
  value = ios
  status = resolved
  confidence = 3
  confidence_level = high

device_class:
  value = unknown
  status = insufficient_evidence
  confidence = 0

manufacturer_family:
  value = apple
  status = resolved
  confidence = 2

model_family:
  value = null
  status = unknown
  confidence = 0
```

No global confidence may overwrite these.

---

# 31. Dimension-Specific Conflict Isolation

Conflict is resolved per dimension.

Example:

```text
portal platform = windows
DHCP platform = android

but

portal form-factor = tablet
DHCP device class = tablet
```

Result MAY be:

```text
platform_family =
unknown / conflicting_evidence

device_class =
tablet / resolved
```

provided device-class claims do not semantically depend on the disputed platform.

A conflict in one dimension MUST NOT erase an independently supported dimension.

---

# 32. Global Classification Summary

A global summary may exist for UI/service convenience:

```text
classification_status
overall_confidence_level
```

but it is derived from per-dimension state.

It MUST NOT replace per-dimension contracts.

Recommended global statuses:

```text
classified
partial
unknown
insufficient_evidence
conflicting_evidence
```

Example:

```text
platform high
device_class unknown

→ global = partial
```

---

# 33. Evidence-Origin Independence

Independent origin groups remain:

```text
dhcp
portal
tcp
tls
quic
```

Knowledge source is NOT an origin.

Same DHCP evidence interpreted by:

```text
Fingerbank static DB
Fingerbank Cloud cache
local DHCP rule
```

still counts as:

```text
ONE dhcp origin group
```

No confidence inflation.

---

# 34. Claim Strength

Per-dimension claims retain:

```text
direct
strong
supporting
weak
```

Recommended defaults:

```text
portal explicit normalized field
→ direct for that semantic dimension

specific DHCP reference
→ strong

tcp_syn/2 p0f match
→ supporting by default

TLS/QUIC JA4 match
→ supporting

broad/generic stale reference
→ weak
```

p0f exact signature compatibility does NOT automatically mean modern
platform certainty.

---

# 35. Per-Dimension Confidence Policy

For each dimension independently:

## HIGH

```text
>=2 independent origin groups
with agreeing direct/strong claims

and
no direct/strong conflict
```

## MEDIUM

```text
one independent direct/strong origin group
with no direct/strong conflict
```

Supporting agreement may corroborate but not count as a second strong origin.

## LOW

```text
supporting/weak only
with no stronger contradiction
```

## NONE

```text
no usable claim
or unresolved dimension conflict
```

No arbitrary numeric source weights in V1.

---

# 36. Conflict Policy

## direct/strong vs direct/strong

For the affected dimension:

```text
value = unknown
status = conflicting_evidence
confidence = 0
```

## direct/strong vs supporting

Keep stronger value if semantically safe.

Record conflict.

Cap affected dimension confidence at:

```text
medium
```

## supporting vs supporting conflict

Affected dimension becomes:

```text
unknown / conflicting_evidence / none
```

Other dimensions remain independently evaluable.

---

# 37. Durable Classification Contract — Revised

Minimum top-level output:

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

classified_at
```

Each `*_result` is structured as:

```text
value
status
confidence
confidence_level
evidence_sources_used
conflicting_sources
explanation_codes
external_reference_ids
```

This is preferred over one flat confidence value.

---

# 38. Classification Storage Boundary

R1 decision remains accepted:

```text
SEPARATE CLASSIFICATION SQLITE
```

Do not add classification tables into Task-01 evidence DB.

Proposed:

```text
/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3
```

Reason:

```text
Task-01 exact repository ownership
+
normalized evidence != derived classification
```

No Task-01 migration is required for classification itself.

---

# 39. Pre-Task-04 Source Optimization Tasks

Before TechLead11 decomposes Task-04:

## OPT-02A — TCP Evidence V2 Feasibility / Contract

Deliver:

```text
tcp_syn/2 exact schema
p0f canonical serializer
TTL/RSPAN proof
real fixture comparison
Fingerbank tcp_syn_signatures compatibility proof
```

No broad acquisition redesign.

## OPT-03A — Portal CH Enrichment Feasibility / Contract

Deliver:

```text
portal_headers/2 decision
Accept-CH scope
Model normalization
Platform-Version normalization
Form-Factors normalization
browser support evidence
privacy proof
```

## OPT-KB1 — Fingerbank Static DB Inspection

Deliver:

```text
actual current SQLite schema
attribute families
device hierarchy
DHCP content
TCP content if any
matching feasibility
license/storage decision
version/refresh mechanism
```

These three are bounded PRE-TASK-04 tasks.

---

# 40. Revised Program Sequence

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
tcp_syn/2 / exact p0f compatibility

OPT-03A
portal_headers/2 normalized CH enrichment

OPT-KB1
concrete offline Fingerbank static DB inspection

        ↓

03A-R2 ARCHITECTURE FINAL

        ↓

TECHLEAD11 TASK-04 TECHNICAL DECOMPOSITION

        ↓

OWNER IMPLEMENTATION AUTHORIZATION

        ↓

TASK-04 IMPLEMENTATION
```

Task-04 is NOT yet ready for decomposition.

---

# 41. What Does NOT Reopen

Pre-Task-04 optimization MUST NOT redesign:

```text
Catalyst RSPAN topology

enp8s0 sensor placement

AF_PACKET architecture

raw dedup architecture

Suricata EVE architecture

Task-01 envelope/API/security

portal Authorization flow

classification/Authorization separation
```

unless one of the exact new evidence fields proves impossible without a specific
bounded change.

---

# 42. Local Validation

Old fixed 12/48 blocker remains removed.

Minimum currently available validation may use:

```text
Owner Android smartphone
Owner Windows laptop
```

Later:

```text
iPhone
iPad
macOS
other Android
```

extend validation.

No fixed count blocks Task-04.

High-confidence incorrect result on a known controlled device remains:

```text
FAIL
```

Unknown/low-confidence on sparse evidence can be correct.

---

# 43. Acceptance Gates — PRE-TASK-04

## Gate P1 — tcp_syn/2 exactness

PASS only if proposed V2 serializer matches canonical p0f raw signature on
controlled fixtures field-for-field.

## Gate P2 — TTL placement

PASS requires topology proof remains valid and controlled capture confirms
pre-router TTL behavior.

## Gate P3 — Fingerbank TCP

PASS if one `tcp_syn/2.p0f_signature` can be accepted as Fingerbank-standard
`tcp_syn_signatures` without fabricated fields.

## Gate P4 — Portal V2 privacy

PASS requires:

```text
no raw new CH persisted
no raw new CH logged
bounded normalized schema only
```

## Gate P5 — Portal V2 value

At least one of the proposed high-value hints must materially improve:

```text
model
OS version
or
device class
```

on supported controlled clients.

If none do:

```text
keep Task-03 V1
```

and document evidence.

## Gate P6 — Fingerbank Static DB

PASS requires actual downloaded DB inspection and concrete local matching path.

## Gate P7 — Offline Knowledge Sufficiency

PASS requires accepted local KnowledgeBundle content includes:

```text
portal rules
TCP reference
DHCP/device reference
```

No Cloud dependency.

Only P1-P7 closure allows:

```text
03A-R2 ARCHITECTURE FINAL
```

---

# 44. Fingerbank Static DB Refresh / Versioning

If K1 passes:

Each imported artifact records:

```text
downloaded_at
SHA256
SQLite schema digest
row counts
Fingerbank version metadata if available
license reference
importer version
taxonomy mapping version
```

Refresh:

```text
download candidate
→ inspect/validate
→ build candidate KnowledgeBundle
→ local validation
→ atomic bundle activation
```

Failed refresh:

```text
current bundle remains active
```

No runtime outage.

---

# 45. Cloud Failure Behavior

Accepted R1 principle remains:

```text
Fingerbank unavailable
→ classifier stays local
```

Fingerbank Cloud is optional enrichment only.

Default:

```text
OFF
```

If enabled later:

```text
no synchronous auth/classification dependency
```

---

# 46. JA4 Role

No change:

```text
tls_client JA4
quic_client JA4
=
supporting/corroborating
```

JA4 alone MUST NOT resolve high-confidence physical device class/platform.

Optional JA4DB remains non-blocking.

Concrete V1 KnowledgeBundle does NOT depend on JA4DB.

---

# 47. Genuine Owner Decisions Still Required

Only these remain.

## O1 — Authorize bounded Fingerbank Community `download/db` inspection

Required because actual current downloadable SQLite schema cannot be certified
from public documentation without obtaining the API-key-protected artifact.

Decision:

```text
AUTHORIZE / DO NOT AUTHORIZE
```

This is research only.

No production device evidence is submitted.

## O2 — Authorize bounded Task-03 Accept-CH experiment

Needed to test:

```text
Sec-CH-UA-Model
Sec-CH-UA-Platform-Version
Sec-CH-UA-Form-Factors
```

on controlled Owner devices.

Decision:

```text
AUTHORIZE / DO NOT AUTHORIZE
```

No raw durable retention.

## O3 — Classification history retention

Architect still recommends:

```text
30 days
```

This can wait until Task-04 FINAL and does NOT block source optimization.

No other broad Owner decision is required now.

---

# 48. R2 Architecture Verdict

```text
TECHLEAD11 REVIEW =
INCORPORATED

tcp_syn/2 =
RECOMMENDED / PRE-TASK-04 REQUIRED DECISION

EXACT p0f COMPATIBILITY =
TECHNICALLY ACHIEVABLE IN PRINCIPLE
WITH CURRENT FULL IPv4 SYN FRAME
PENDING FIELD-BY-FIELD FIXTURE PROOF

TTL / RSPAN SEMANTICS =
PRE-ROUTER
DISTANCE 0
observed_ttl = initial_ttl
FOR CURRENT TOPOLOGY

Task-03 ENRICHMENT =
portal_headers/2 RECOMMENDED
WITH MODEL + PLATFORM-VERSION + FORM-FACTORS
NORMALIZED ONLY
PENDING CONTROLLED VALUE/PRIVACY PROOF

LOCAL KNOWLEDGE =
MUST BE CONCRETE BEFORE TASK-04

PRIMARY DHCP CANDIDATE =
Fingerbank Community static /download/db
CURRENT REQUIRED INSPECTION GATE

TCP LOCAL REFERENCE =
p0f [tcp:request] signatures

PORTAL LOCAL REFERENCE =
deterministic normalized semantic rules

JA4 =
supporting / optional external mapping

PER-DIMENSION RESULTS =
MANDATORY

PER-DIMENSION CONFIDENCE =
MANDATORY

PHYSICAL 12/48 BLOCKER =
REMOVED

TASK-04 TECHNICAL DECOMPOSITION =
HOLD

CODE =
NO

PRODUCTION CHANGE =
NO
```

---

# 49. Research References

Fingerbank:

```text
https://api.fingerbank.org/api_doc/2/static.html
https://api.fingerbank.org/api_doc/2/combinations.html
https://www.fingerbank.org/privacy/
```

PacketFence / Fingerbank local integration:

```text
inverse-inc/packetfence
fingerbank::Source::LocalDB
fingerbank::Constant
Fingerbank integration documentation
```

p0f:

```text
https://github.com/p0f/p0f/blob/master/docs/README
https://github.com/p0f/p0f/blob/master/p0f.fp
```

Cisco / TTL:

```text
Cisco SPAN documentation
RFC 1812
```

Client Hints:

```text
WICG User-Agent Client Hints
MDN Sec-CH-UA-Model
MDN Sec-CH-UA-Platform-Version
MDN Sec-CH-UA-Form-Factors
```

---

# 50. Current Control Status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04
ARCHITECTURE DECISION R2

CURRENT GATE =
OWNER + TECHLEAD11 REVIEW

NEXT IF ACCEPTED =
bounded PRE-TASK-04 SOURCE OPTIMIZATION

TASK-04 TECHLEAD DECOMPOSITION =
HOLD

CODER =
HOLD

NO CODE

NO CODER TASK

NO PRODUCTION CHANGE
```

**End of DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION R2.**
