# DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION

## External Fingerprint Knowledge Baseline + Local Validation → Multi-Signal Classification Engine

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-15  
**Status:** `FOR OWNER + TECHLEAD11 ARCHITECTURE REVIEW`  
**Code:** `NO CODE YET`  
**Production changes:** `NOT AUTHORIZED`  
**New sensor collection:** `NOT REQUIRED`  
**Physical-device count blocker:** `REMOVED`  
**Task-04 implementation:** `NOT AUTHORIZED`

---

# 0. Owner Decision / Program Reset

Owner отменил прежний admission contract, при котором Task-04 зависел от:

```text
12 physical test devices
>=48 manually labeled samples
2 iPhone
2 iPad
2 macOS devices
old Gate G when its PASS depended on that matrix
```

Эти требования больше НЕ блокируют Task-04.

Новый канонический путь:

```text
TASK-01 / TASK-02 / TASK-03
NORMALIZED EVIDENCE
        ↓
EXTERNAL / CURATED FINGERPRINT KNOWLEDGE
        +
LOCAL DETERMINISTIC RULES
        +
LOCAL PRODUCTION OBSERVATIONS
        ↓
TASK-04 MULTI-SIGNAL CLASSIFICATION ENGINE
        ↓
DERIVED CLASSIFICATION
```

Local known devices остаются обязательным инструментом validation, но НЕ
становятся обязательной мировой training database и НЕ задают fixed-count
roadmap blocker.

---

# 1. Current Verified Foundation

Fresh architecture-time repository rebind:

```text
repository =
ZaurNavi/CaptivePortal

main HEAD =
d37d3ec126ccd512fe835af0db21221e2f83d565

main TREE =
3145e904ad5027d0d584945f4814f3ade59d44ea
```

Current production normalized evidence families:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

Owner production proof confirms end-to-end operation after AF_PACKET fixes:

```text
DHCP parser             PASS
DHCP scope              PASS
TCP SYN parser          PASS
TLS/JA4 path            PASS
QUIC/JA4 path           PASS
Portal evidence         PASS
Normalizer              PASS
Spool                   PASS
Delivery                PASS
Task-01 ingest          PASS
Central persistence     PASS
```

Architecture therefore treats source collection as an accepted foundation.

Task-04 MUST NOT redesign packet acquisition or portal acquisition.

---

# 2. Permanent Semantic Separation

Four semantic layers remain permanent:

```text
1. RAW ACQUISITION OBSERVATION
2. NORMALIZED EVIDENCE
3. DERIVED CLASSIFICATION
4. GROUND TRUTH
```

External knowledge introduces a fifth supporting concept:

```text
REFERENCE KNOWLEDGE
```

Reference knowledge is neither normalized evidence nor ground truth.

Examples:

```text
Fingerbank match
p0f-derived reference rule
JA4DB mapping
local curated signature rule
```

MUST NOT be stored as human ground truth.

Permanent identity rules:

```text
one fingerprint != one device
one UA != one device
one JA4 != one device
one DHCP fingerprint != one device
one MAC != permanent human identity
```

Task-04 classifies a bounded current `Site + MAC` evidence context only.

Cross-MAC identity remains Task-05 scope.

---

# 3. External Source Assessment

## 3.1 Fingerbank — Overall Verdict

Fingerbank is the strongest external candidate for DHCP-based reference
knowledge.

Recommended architecture roles:

```text
A. LOCAL_ONLY
   mandatory baseline

B. LOCAL + OPTIONAL FINGERBANK CLOUD REFRESH/ENRICHMENT
   supported
   default disabled

C. PERIODIC STATIC FINGERBANK REFERENCE IMPORT
   possible future mode
   requires separate compatibility/licensing proof

D. FINGERBANK ON-PREM PROCESSING ENGINE
   future licensed enterprise option
```

Core classification MUST work in Mode A.

Fingerbank Cloud MUST NOT become a synchronous runtime dependency.

## 3.2 Fingerbank Access / Commercial Model

Current public Fingerbank access indicates:

```text
Community Access =
free
600 requests/hour

Premium =
starts at $5,000/year
1M requests/month baseline tier

On-prem =
custom enterprise-only offering
```

Fingerbank also exposes an API-key-protected `/api/v2/download/db` SQLite
reference database, while `/api/v2/download/on-prem-db` is explicitly described
as licensing-only for the standalone Processing Engine.

Architecture MUST NOT assume that the public static database reproduces the
licensed Processing Engine scoring or matching behavior.

## 3.3 Fingerbank Cloud Privacy

Fingerbank states Cloud API device data may be retained and used to improve its
identification engine.

Fingerbank also documents that previously unknown queried combinations may be
added to its database.

Therefore:

```text
Fingerbank Cloud =
external disclosure of device evidence
```

Default V1:

```text
FINGERBANK_CLOUD_ENABLED =
false
```

Explicit Owner/Admin opt-in is required before production use.

## 3.4 p0f — Overall Verdict

Use p0f as:

```text
methodology reference
signature grammar reference
TCP normalization/matching inspiration
curated reference source where representable
```

Do NOT use its bundled database as unquestioned modern canonical truth.

The widely used p0f v3 tree identifies as 3.09b; the common public GitHub mirror
is unofficial and old relative to modern Windows/macOS/iOS/Android evolution.

## 3.5 JA4 / JA4DB — Overall Verdict

Existing JA4 and QUIC JA4 are valid supporting signals.

They MUST NOT be treated as physical-device identity.

JA4 TLS Client Fingerprinting itself is BSD 3-Clause.

Other JA4+ methods such as JA4T/JA4D are under the FoxIO License and have
commercial/OEM licensing implications.

Task-04 V1 therefore uses only existing CaptivPortal JA4 evidence.

JA4DB may become an optional periodically imported supporting reference after
license/redistribution review.

---

# 4. Current CaptivPortal Evidence Compatibility

## 4.1 DHCP → Fingerbank

Current `dhcp/1`:

```text
message_type
parameter_request_list
option_order
vendor_class
client_identifier_kind
maximum_message_size
rapid_commit_requested
capport_requested
ipv6_only_preferred_requested
hostname_present
```

Exact Fingerbank-compatible mapping:

```text
parameter_request_list
→ dhcp_fingerprint

vendor_class
→ dhcp_vendor
```

`dhcp_fingerprint` serialization rule:

```text
preserve PRL order
comma-delimited decimal option numbers
no sorting
no dedup
```

Example:

```text
[1,3,6,15,119]
→
"1,3,6,15,119"
```

`vendor_class = null` means `dhcp_vendor` is omitted.

Do NOT substitute:

```text
option_order
```

for Fingerbank DHCP fingerprint.

Other CaptivPortal DHCP fields remain local signals.

## 4.2 Portal Evidence → Fingerbank

Current `portal_headers/1` persists normalized, privacy-minimized fields:

```text
platform_family
mobile_boolean
browser_runtime_family
webview_or_captive_context
model_family
os_major
provenance/presence fields
```

It does NOT persist raw:

```text
User-Agent
sec-ch-ua
sec-ch-ua-platform
sec-ch-ua-mobile
```

Fingerbank User-Agent / Client Hints APIs expect original HTTP values.

Therefore:

```text
portal_headers/1 → Fingerbank raw UA/client_hints
EXACT COMPATIBILITY = NO
```

Forbidden:

```text
reconstruct fake User-Agent
invent sec-ch-ua
reverse-normalize platform_family into fake headers
```

Portal evidence stays local in V1.

## 4.3 TCP SYN → p0f / Fingerbank TCP

Current `tcp_syn/1`:

```text
ip_version
observed_ttl
tcp_window
mss
window_scale
sack_permitted
timestamps_present
tcp_option_order
```

p0f signature grammar requires additional semantics including:

```text
IP option length
full TCP/IP quirks
payload class
p0f-specific window/TTL semantics
```

Current durable evidence cannot losslessly construct an exact p0f signature.

Therefore:

```text
tcp_syn/1 → p0f signature
EXACT COMPATIBILITY = NO

tcp_syn/1 → Fingerbank tcp_syn_signatures
V1 = FORBIDDEN
```

Do NOT fabricate missing p0f fields.

## 4.4 Native CaptivPortal TCP Signature

Task-04 should define a native local representation:

```text
cp_tcp_syn_v1
```

using only current durable fields.

It MUST NOT be labeled as a p0f signature.

TCP remains supporting/corroborating in V1.

Exact p0f compatibility, if ever needed, requires a future Task-02 evidence
schema extension and is NOT a Task-04 V1 blocker.

## 4.5 JA4 / QUIC JA4

Existing normalized:

```text
tls_client/1
quic_client/1
```

are directly consumable by Task-04.

JA4 describes client TLS/application/library behavior and can change when
applications/libraries change.

Architecture role:

```text
supporting
```

not:

```text
unique device identity
authoritative platform
standalone high-confidence class
```

---

# 5. Proposed Knowledge Architecture

## 5.1 Offline-First Principle

Runtime dependency:

```text
Task-01 evidence READ ONLY
        +
accepted local KnowledgeBundle
        ↓
Task-04 classifier
```

Forbidden default runtime path:

```text
device event
→ Fingerbank Cloud lookup
→ wait
→ classify
```

## 5.2 Knowledge Pipeline

```text
external source / curated rules
        ↓
source-specific importer
        ↓
normalized knowledge claims/rules
        ↓
candidate bundle
        ↓
schema/license/taxonomy validation
        ↓
local validation
        ↓
Owner/TechLead acceptance
        ↓
immutable accepted bundle
        ↓
local runtime classifier
```

## 5.3 Knowledge Bundle Identity

Every accepted bundle contains:

```text
knowledge_bundle_id
knowledge_schema_version
created_at
content_sha256
taxonomy_mapping_version
compatibility_version
source_manifests
license_metadata
```

Each classification stores its:

```text
knowledge_bundle_id
```

for reproducibility.

## 5.4 Source Manifest

Per knowledge source:

```text
source_name
source_type
source_version
retrieved_at
source_digest
license_status
importer_version
enabled
notes_code
```

Allowed conceptual source types:

```text
fingerbank_cloud_cache
fingerbank_static_reference
p0f_reference
ja4db_reference
local_curated_rules
```

## 5.5 Activation / Rollback

Knowledge activation is bundle-atomic:

```text
candidate
→ validate
→ sanity test
→ accept
→ activate
```

Never hot-edit individual active rules in place.

Keep:

```text
current accepted bundle
previous accepted bundle
```

for rollback.

## 5.6 Refresh

Runtime classifier never refreshes external knowledge.

Initial V1:

```text
manual explicit refresh
```

Later optional schedule may be introduced after operational acceptance.

Refresh failure leaves the current accepted bundle unchanged.

---

# 6. Fingerbank Operating Modes

## Mode A — LOCAL_ONLY

Mandatory.

```text
Cloud = OFF
classifier = fully local
```

Task-04 acceptance MUST pass in this mode.

## Mode B — LOCAL + OPTIONAL CLOUD KNOWLEDGE REFRESH

Recommended optional mode.

Only an asynchronous/background refresh workflow may call Fingerbank.

Recommended V1 Cloud allowlist:

```text
dhcp_fingerprint
dhcp_vendor
```

Explicit denylist:

```text
MAC
IP
hostname
destination_hosts
raw User-Agent
raw Client Hints
SNI
DNS history
JA3
```

The runtime classifier does not wait for this refresh.

## Mode C — PERIODIC STATIC FINGERBANK IMPORT

Potential future mode based on `/api/v2/download/db`.

Before implementation it needs a bounded research gate for:

```text
actual SQLite schema
matching adequacy
taxonomy structure
license/terms
redistribution/storage conditions
versioning
```

Until then:

```text
DEFERRED
```

## Mode D — LICENSED ON-PREM ENGINE

Future enterprise option.

Not a Task-04 V1 dependency.

---

# 7. Proposed Multi-Signal Classifier Architecture

## 7.1 Pure Engine

```text
EvidenceSnapshot
+
KnowledgeBundle
→
ClassificationResult
```

Pure fusion logic has no DB/network access.

## 7.2 Service Layer

```text
Task-01 read-only evidence
→ build explicit EvidenceSnapshot
→ load accepted KnowledgeBundle
→ invoke pure engine
→ persist ClassificationResult
```

## 7.3 EvidenceSnapshot Boundary

Task-04 MUST NOT invent a global recency/session policy.

Input snapshot explicitly contains:

```text
site_id
observed_mac
window_start_utc
window_end_utc
normalized evidence rows
source-health context
as_of
```

Task-05 later decides:

```text
which visit/session/device window should be classified
when classification should run
```

This preserves Task-04 / Task-05 separation.

## 7.4 Evidence Origin Groups

Independent origin groups:

```text
dhcp
portal
tcp
tls
quic
```

External knowledge interprets one of these origins.

It does NOT create a new independent evidence source.

Permanent anti-double-counting rule:

```text
same DHCP evidence
interpreted by Fingerbank
+
interpreted by local DHCP rules
=
ONE dhcp origin group
```

---

# 8. Classification Taxonomy

## platform_family

V1:

```text
android
ios
windows
macos
chromeos
linux
unknown
```

For V1:

```text
iPad/iPadOS
→ platform_family = ios
→ device_class = tablet
```

A future taxonomy version may introduce separate `ipados`.

## device_class

Phase-1:

```text
smartphone
tablet
laptop
unknown
```

IoT/TV/printer/camera remain later scope.

## Optional detail

```text
manufacturer_family = string | null
model_family = string | null
```

Never force them from broad knowledge.

## classification_status

```text
classified
partial
unknown
insufficient_evidence
conflicting_evidence
```

Unknown is a valid safe result.

---

# 9. Evidence Claim Model

Each source adapter outputs normalized claims:

```text
dimension
value
origin_group
strength
source_kind
reference_id
explanation_code
```

Strength:

```text
direct
strong
supporting
weak
```

## portal_headers

```text
platform_family
→ direct

explicit model_family
→ direct

explicit os_major
→ direct

mobile_boolean
→ strong/supporting form-factor evidence

runtime/context
→ supporting
```

Portal is still client-declared/spoofable; `direct` means direct semantic
declaration, not ground truth.

## DHCP

With a sufficiently specific accepted reference match:

```text
strong
```

Raw unmatched normalized DHCP produces no forced class label.

## TCP

```text
supporting
```

It cannot alone create high confidence in V1.

## TLS / QUIC JA4

```text
supporting
```

They cannot alone create high confidence in V1.

---

# 10. Fingerbank Claim Handling

Fingerbank's own `score` is retained as:

```text
external_reference_score
```

It is NOT CaptivPortal confidence.

A deterministic external-strength adapter may use Fingerbank's documented
ranges:

```text
<=30
→ weak

31..50
→ supporting

>=51
→ strong
```

but only when the Fingerbank result actually resolves the requested taxonomy
dimension.

A broad hierarchy such as:

```text
Phone, Tablet or Wearable
```

MUST NOT be arbitrarily mapped to:

```text
smartphone
```

even at a high Fingerbank score.

Taxonomy mapping is separately versioned.

---

# 11. Deterministic Confidence / Conflict Model

V1 confidence is ordinal, not probabilistic:

```text
confidence =
0 | 1 | 2 | 3

confidence_level =
none | low | medium | high
```

Mapping:

```text
0 → none
1 → low
2 → medium
3 → high
```

No uncalibrated percentage probabilities.

## High

For one target dimension:

```text
>=2 independent origin groups
each provide agreeing direct/strong claims

AND

no direct/strong conflict
```

Example:

```text
portal → android direct
dhcp → android strong
=
high platform confidence
```

## Medium

```text
exactly one independent direct/strong origin group
no direct/strong conflict
```

Supporting agreement may corroborate, but does not become a second independent
strong origin.

## Low

```text
only supporting/weak claims agree
no stronger contradiction
```

## None

```text
no usable claim
or unresolved conflict
```

---

# 12. Conflict Resolution

## Hard direct/strong conflict

Example:

```text
portal → windows
dhcp → android
```

Result for that dimension:

```text
value = unknown
confidence = 0
confidence_level = none
classification_status = conflicting_evidence
```

Never pick a forced winner.

## Strong vs supporting conflict

```text
direct/strong = A
supporting = B
```

Result:

```text
A may be retained
conflict recorded
confidence capped at medium
```

## Supporting-only conflict

```text
value = unknown
confidence = 0
status = conflicting_evidence
```

## Within-origin conflict

If the same origin produces contradictory claims in the snapshot:

```text
origin group = conflicted
```

It is not counted as a strong independent vote.

---

# 13. Durable Classification Data Contract

Minimum output:

```text
classification_id
site_id
observed_mac
classification_status

platform_family
device_class
manufacturer_family
model_family

confidence
confidence_level

evidence_sources_used
conflicting_sources

classification_version
knowledge_bundle_id

evidence_window_start
evidence_window_end
evidence_digest

classified_at
```

Recommended additional explainability:

```text
field_confidence
explanation_codes
external_reference_ids
source_health_summary
```

No raw packet/UA/CH/SNI/DNS.

`evidence_digest` is for reproducibility/change detection only.

It MUST NOT be used to merge MAC identities.

---

# 14. Classification Storage Decision

Do NOT put classification tables into the Task-01 evidence SQLite.

Task-01 repository owns and validates its exact table/schema signature.

Architecture decision:

```text
SEPARATE CLASSIFICATION SQLITE
```

Proposed path:

```text
/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3
```

This preserves:

```text
NORMALIZED EVIDENCE
!=
DERIVED CLASSIFICATION
```

Logical history table:

```text
device_fingerprint_classification_results
```

Logical current pointer:

```text
device_fingerprint_classification_current
```

Current key:

```text
site_id + observed_mac
```

It is MAC-scoped classification, not person identity.

Recommended history retention:

```text
30 days
```

Owner may change this before Task-04 implementation FINAL.

---

# 15. Classification Read Contract

Minimum Python read service:

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

Task-04 does NOT add:

```text
Device Card
Admin UI
public classification API
```

Task-05/06 own those integrations.

---

# 16. Privacy / External Dependency Model

Permanent:

```text
classification failure
MUST NEVER
become Authorization failure
```

Fingerbank Cloud default:

```text
OFF
```

When optional Cloud mode is enabled, V1 recommends sending only:

```text
dhcp_fingerprint
dhcp_vendor
```

Do not send:

```text
MAC
IP
hostname
destination hosts
raw User-Agent
raw Client Hints
SNI
DNS
```

Current Task-03 privacy boundary remains unchanged.

No raw UA is made durable to improve external matching.

---

# 17. Failure / Degraded Behavior

## External refresh outage

```text
candidate refresh = failed
current accepted bundle = unchanged
runtime classifier = available
```

Operational state may emit:

```text
knowledge_refresh_degraded
```

## No accepted external bundle

Use:

```text
built-in/local deterministic rules
```

Result may safely be:

```text
unknown
insufficient_evidence
low/medium confidence
```

No forced Cloud query.

## Corrupt candidate bundle

```text
do not activate
keep current/previous accepted bundle
```

## Classification DB unavailable

Classification persistence becomes degraded/unavailable.

Authorization and Portal remain unaffected.

## External rate limit / 429

Refresh job obeys bounded retry/cooldown policy.

Runtime classifier remains local and unaffected.

---

# 18. Local Validation Model

Local known devices are now:

```text
sanity checks
regression checks
confidence-policy validation
external-reference validation
false-positive detection
```

They are NOT a mandatory global training corpus.

Current Owner baseline includes at least:

```text
Android smartphone
Windows laptop
```

Additional iPhone/iPad/macOS/Android devices improve validation when available
but do not block roadmap.

Procedure:

```text
1. record manual ground truth BEFORE reviewing classifier result
2. build explicit EvidenceSnapshot
3. run classifier locally
4. record result/confidence/claims/conflicts/bundle ID
5. compare against ground truth
6. high-confidence wrong platform/device class → FAIL candidate
7. unknown/low on sparse evidence may be correct
```

No automatic online learning.

No local result automatically rewrites rules.

---

# 19. 03A-R2 / Task-04 Boundary

## 03A-R2 owns

```text
external source assessment
compatibility contracts
privacy/licensing policy
knowledge-source operating modes
taxonomy mapping policy
local validation procedure
external baseline curation/import research
```

## Task-04 owns

```text
local KnowledgeBundle runtime foundation
evidence→claim adapters
deterministic multi-signal fusion
confidence/conflict semantics
classification persistence
classification read service
optional external refresh
local validation acceptance
```

## Old 03A matrix tooling

Existing merged tooling remains valid for:

```text
optional expanded research
future regression datasets
manual matrix campaigns
```

But its old:

```text
12-device / 48-sample coverage PASS
```

is no longer Task-04 admission blocker.

Do not delete the tooling.

---

# 20. Proposed Task Decomposition

## DEVICE-FINGERPRINT-03A-R2-01
**External Knowledge Compatibility & Policy**

Outputs:

```text
Fingerbank compatibility contract
Fingerbank privacy/opt-in contract
p0f representable-subset decision
JA4DB decision
taxonomy mapping specification
license/source manifest rules
```

## TASK-DEVICE-FINGERPRINT-04A
**Knowledge Bundle Foundation**

Owns:

```text
bundle schema
manifest
checksums
versioning
validation
activation
rollback
import-adapter interfaces
```

## TASK-DEVICE-FINGERPRINT-04B
**Evidence → Claim Adapters**

Owns:

```text
DHCP claim adapter
portal claim adapter
TCP supporting adapter
TLS JA4 adapter
QUIC JA4 adapter
origin-group semantics
```

## TASK-DEVICE-FINGERPRINT-04C
**Deterministic Multi-Signal Fusion Engine**

Owns:

```text
taxonomy
claim tiers
conflict handling
confidence
unknown/insufficient semantics
explainability
```

## TASK-DEVICE-FINGERPRINT-04D
**Classification Persistence + Read Service**

Owns:

```text
separate classification SQLite
immutable result history
current pointer
retention
read service
```

## TASK-DEVICE-FINGERPRINT-04E
**Optional External Knowledge Refresh**

Owns:

```text
Fingerbank opt-in refresh/cache
optional JA4DB importer
candidate bundle creation
external health/degraded semantics
```

## TASK-DEVICE-FINGERPRINT-04F
**Local Validation / Acceptance**

Uses available Owner-controlled devices without fixed-count admission.

Recommended order:

```text
04A
→ 04B
→ 04C
→ 04D
→ 04F
→ 04E
```

Core local classification must exist before optional Cloud integration.

---

# 21. Acceptance Gates

## Gate A — Fresh Source Rebind

Confirm current production schemas and no evidence-contract drift.

## Gate B — Knowledge Bundle Determinism

```text
same accepted bundle
+
same EvidenceSnapshot
→ same claims
→ same ClassificationResult
```

## Gate C — Fingerbank Privacy / Disabled Mode

Disabled:

```text
zero Fingerbank network calls
```

Enabled test payload contains only approved allowlist.

## Gate D — Offline Operation

With external network blocked:

```text
local classifier remains functional
```

No synchronous Cloud retries.

## Gate E — Hard Conflict

Fixture:

```text
portal → windows
dhcp → android
```

Expected:

```text
platform = unknown
status = conflicting_evidence
confidence = 0
```

## Gate F — No Double Counting

Same DHCP evidence interpreted by local rules and Fingerbank:

```text
one dhcp origin group
```

not two votes.

## Gate G — Safe Uncertainty

Fixtures:

```text
JA4 only
TCP only
unknown DHCP
```

must support:

```text
low
unknown
insufficient_evidence
```

## Gate H — Local Known Devices

Use currently available known devices.

No fixed-count gate.

High-confidence false positive for platform/device_class:

```text
FAIL
```

## Gate I — Persistence / Reproducibility

Persist:

```text
classification_version
knowledge_bundle_id
evidence_digest
evidence window
claims/conflicts provenance
classified_at
```

## Gate J — Failure Isolation

Prove outages of:

```text
Fingerbank
JA4DB
knowledge refresh
classification DB
candidate bundle
```

cannot break Authorization/Portal/Task-01/02/03.

## Gate K — No Identity Merge

No automatic:

```text
UA similarity merge
JA4 similarity merge
DHCP similarity merge
cross-MAC link
```

---

# 22. Required Research Gates Before Specific Importers

## Fingerbank API Adapter Research Gate

Prove with synthetic/reference values:

```text
PRL serialization order
vendor serialization
response hierarchy parsing
score handling
404
429
5xx
no MAC sent
no raw UA/CH sent
```

No production device submission is required.

## Fingerbank Static DB Gate — only if Mode C chosen

Prove:

```text
actual db schema
allowed use/license
matching attributes
offline adequacy
UA absence implications
version/digest
```

Unresolved:

```text
Mode C = deferred
```

Mode A/B can continue.

## p0f Reference Gate

Freeze:

```text
no exact p0f serialization from tcp_syn/1
```

Any imported signature subset records:

```text
source version
digest
license
conversion rule
representable fields
fixtures
```

## JA4DB Gate

Before snapshot/import:

```text
API/download format proof
license/redistribution review
verified semantics
observation_count semantics
normalization
source version/digest
staleness behavior
```

---

# 23. Risks

## External taxonomy mismatch

Mitigation:

```text
versioned mapping
unknown instead of forced conversion
```

## External reference drift

Mitigation:

```text
immutable bundle
source digest/version
candidate validation
atomic activation
rollback
```

## Cloud privacy

Mitigation:

```text
default OFF
explicit opt-in
DHCP-only allowlist
no MAC/raw UA/CH
```

## p0f age

Mitigation:

```text
methodology/supporting only
no modern-truth assumption
```

## JA4 shared application/library behavior

Mitigation:

```text
supporting only
multi-origin fusion
no identity use
```

## Confidence inflation

Mitigation:

```text
origin-group anti-double-counting
```

## Fingerprint spoofing

Mitigation:

```text
classification remains advisory
conflicts/unknown supported
never authorization truth by itself
```

---

# 24. Owner Decisions Still Required

## O1 — Fingerbank Cloud optional refresh

Architect recommendation:

```text
DEFAULT DISABLED
```

Owner decision:

```text
allow optional opt-in refresh?
YES / NO
```

If YES, V1 recommendation:

```text
DHCP fingerprint + DHCP vendor only
```

## O2 — Fingerbank static `download/db`

Architect recommendation:

```text
RESEARCH / DEFERRED
```

until schema/license/adequacy proof.

## O3 — JA4DB import

Architect recommendation:

```text
OPTIONAL SUPPORTING REFERENCE
```

with explicit license/redistribution review first.

## O4 — Commercial licensing posture

If CaptivPortal may be monetized/distributed:

```text
do not add JA4+ methods such as JA4T/JA4D
without OEM/license review
```

Existing JA4 TLS Client fingerprinting remains a separate BSD-licensed method.

## O5 — Classification history retention

Architect recommendation:

```text
30 days
```

Owner may change before Task-04 implementation FINAL.

## O6 — Automatic knowledge refresh

Architect recommendation:

```text
manual refresh first
```

Schedule later after operational acceptance.

---

# 25. Decisions Already Frozen Architecturally

These do not require another broad research loop:

```text
Task-04 is offline-first

Fingerbank is not a hard runtime dependency

raw UA remains non-durable

current tcp_syn/1 is not exact p0f

JA4 / QUIC JA4 are supporting

one-fingerprint-one-device logic is forbidden

unknown/conflict are first-class outputs

confidence is deterministic ordinal, not fake probability

same evidence interpreted by multiple knowledge sources is one origin vote

classification DB is separate from Task-01 evidence DB

Task-05 remains identity/session integration owner

old 12/48 physical matrix is not Task-04 admission blocker
```

---

# 26. New Program Sequence

```text
TASK-01
Evidence Foundation
= DONE

TASK-02
Network Evidence
= DONE

TASK-03
Portal Evidence
= DONE

TASK-03A original physical matrix
= OPTIONAL RESEARCH / VALIDATION TOOLING
  NOT TASK-04 ADMISSION BLOCKER

TASK-03A-R2
External Knowledge Baseline + Local Validation
= CURRENT BRIDGE

TASK-04
Multi-Signal Classification Engine
= NEXT AFTER ARCHITECTURE ACCEPTANCE
  + TECHLEAD11 DECOMPOSITION
  + OWNER IMPLEMENTATION AUTHORIZATION

TASK-05
Identity / Classification Integration
= HOLD

TASK-06
Device Card / Admin Presentation
= HOLD
```

---

# 27. Final Architecture Verdict

```text
EXTERNAL KNOWLEDGE =
YES

LOCAL OFFLINE CLASSIFIER =
MANDATORY

CLOUD HARD DEPENDENCY =
NO

FINGERBANK DHCP COMPATIBILITY =
YES

FINGERBANK RAW UA/CH COMPATIBILITY =
NO UNDER CURRENT PRIVACY CONTRACT

FINGERBANK p0f/TCP COMPATIBILITY =
NO WITH CURRENT tcp_syn/1

P0F METHODOLOGY =
YES / SUPPORTING

P0F BUNDLED DB AS MODERN TRUTH =
NO

PORTAL_HEADERS =
PRIMARY LOCAL SIGNAL

JA4 / QUIC JA4 =
SUPPORTING

MULTI-SIGNAL FUSION =
MANDATORY

UNKNOWN / INSUFFICIENT / CONFLICT =
FIRST-CLASS OUTPUT

PHYSICAL 12/48 MATRIX BLOCKER =
REMOVED

NEW SENSOR COLLECTION =
NOT REQUIRED

TASK-04 =
READY FOR TECHLEAD11 TECHNICAL DECOMPOSITION
AFTER OWNER ACCEPTS THIS ARCHITECTURE DECISION
```

---

# 28. External Research References

Fingerbank:

```text
https://api.fingerbank.org/api_doc/2/combinations.html
https://www.fingerbank.org/api-access/
https://www.fingerbank.org/privacy/
https://www.fingerbank.org/usage/
https://api.fingerbank.org/api_doc/2/static.html
```

p0f:

```text
https://github.com/p0f/p0f
https://github.com/p0f/p0f/blob/master/docs/README
```

JA4 / JA4DB:

```text
https://github.com/FoxIO-LLC/ja4
https://github.com/FoxIO-LLC/ja4/blob/main/License%20FAQ.md
https://docs.ja4db.com/ja4%2B-database/usage/read-the-database
```

External material remains reference/research input.

It is not production knowledge until a source-specific compatibility,
license/privacy and bundle-import gate passes.

---

# 29. Current Control Status

```text
DOCUMENT =
DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION

CURRENT GATE =
OWNER + TECHLEAD11 REVIEW

CODE =
NO

PRODUCTION CHANGE =
NO

NEW SENSOR COLLECTION =
NO

PHYSICAL DEVICE COUNT BLOCKER =
NO

TASK-04 IMPLEMENTATION =
NOT AUTHORIZED

TASK-05 =
HOLD

TASK-06 =
HOLD
```

**End of DEVICE-FINGERPRINT-03A-R2 / TASK-04 ARCHITECTURE DECISION.**
