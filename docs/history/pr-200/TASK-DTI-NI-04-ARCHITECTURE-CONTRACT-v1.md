# TASK-DTI-NI-04 — SERVICE RECOGNITION
## ARCHITECTURE CONTRACT v1
### Recognition of Internet Services / Распознавание интернет-сервисов

**Project:** CaptivPortal  
**Program:** Device Traffic Intelligence / Network Intelligence  
**Task:** `TASK-DTI-NI-04`  
**Role:** Architect  
**Document:** `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md`  
**Prepared:** 2026-10-10  
**Architecture type:** final semantic/component/security/read-model contract  
**Implementation authorization:** `NO`  
**Coder:** `HOLD`  
**Production change:** `NO`  

---

# 0. DOCUMENT DISPOSITION

This document answers the Technical Lead architecture request for:

```text
TASK-DTI-NI-04 — Service Recognition
```

It is intentionally not:

```text
Coder TASK
production implementation
deployment authorization
production activation authorization
rule-catalog approval by itself
```

The contract freezes the architecture that a later Technical Lead implementation TASK must preserve.

Final disposition is:

```text
ARCHITECTURE SEMANTICS =
PASS / COMPLETE

MAIN NI-04 PRODUCT IMPLEMENTATION =
HOLD

MANDATORY PREREQUISITE =
TASK-DTI-NI-04A
RECOGNITION EVIDENCE BRIDGE + INITIAL KNOWLEDGE ADMISSION

READY FOR TECH LEAD IMPLEMENTATION TASK =
YES, FOR NI-04A ONLY

FINAL REQUEST STATUS =
ARCHITECTURE HOLD / PREREQUISITE REQUIRED
```

The HOLD is not caused by an unresolved architectural choice.

The HOLD exists because the current production code intentionally does not expose
the sensitive DNS/SNI fields through a consumer-safe recognition read boundary,
and because no accepted initial concrete service-recognition knowledge/rule bundle
has yet been admitted.

Both prerequisite outputs are specified exactly below.

---

# 1. AUTHORITATIVE INPUTS / PRECEDENCE

This contract is subordinate to and must preserve the accepted semantics of:

```text
DTI-NETWORK-INTELLIGENCE-PRIORITY-ADDENDUM-v0.2-FINAL-TECHLEAD-ACCEPTED.md

DEVICE-TRAFFIC-ENRICHMENT-ARCHITECTURE-v0.3_FINAL_TECHLEAD_ACCEPTED.md

accepted NI-01 contracts

accepted NI-02A temporal attribution contracts

accepted NI-02B device-relative projection contracts

accepted NI-03 Protocol Intelligence contracts
including the NI-03 R1 corrections

current Admin Web security / Site / query-control contracts
```

If a later implementation discovers that one of the decisions below cannot be
implemented without changing a frozen parent semantic contract:

```text
STOP
→ Architect return
```

Coder must not reinterpret the parent.

---

# 2. VERIFIED CURRENT BASELINE

## 2.1 Repository baseline

The Architecture Request stated:

```text
Repository =
ZaurNavi/CaptivePortal

HEAD =
e8061de9fbd6da8be5cd269779070a4db4d59d64

TREE =
d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
```

The Architect re-pinned current GitHub `main` and confirmed the same values.

The current HEAD is the merge of:

```text
PR #198
WEB-FIX-NI03-01:
refine Network / Protocol Intelligence presentation
```

Therefore:

```text
BASELINE_MOVED =
NO

ARCHITECTURE REQUEST BASELINE =
CURRENT
```

## 2.2 Production read-only confirmation

Read-only production inspection also confirmed:

```text
/opt/CaptivePortal HEAD =
e8061de9fbd6da8be5cd269779070a4db4d59d64

/opt/CaptivePortal TREE =
d5503fe1f2b5774bbe55cb2d34dba63246f56f6f

captive-portal.service =
active

network-metadata.service =
active

network-metadata-projection.service =
active
```

No production mutation was performed during architecture preparation.

## 2.3 Current configuration ownership observed

Current production service ownership is:

```text
network-metadata.service
→ EnvironmentFile=/etc/captive-portal/network-metadata.env
→ app.network_metadata.config.network_metadata_config_from_env()

network-metadata-projection.service
→ EnvironmentFile=-/etc/captive-portal/network-metadata-projection.env
→ app.network_metadata_projection.config.projection_config_from_env()

captive-portal.service
→ EnvironmentFile=/etc/default/captive-portal
→ EnvironmentFile=-/etc/captive-portal/network-metadata-projection.env
```

Current main Admin process therefore already receives NI-02B projection
configuration, but does not currently receive the NI-01 environment file.

NI-04 must close that handoff explicitly.

---

# 3. VERIFIED CURRENT CODE FACTS

At the reviewed baseline:

## 3.1 NI-01 stores the source material needed for recognition

NI-01 persists normalized:

```text
DNS query names

DNS answer values:
A
AAAA
CNAME

TLS SNI

QUIC SNI

endpoint metadata:
src/dst IP
src/dst port
transport protocol

source/event/provenance identity
```

Current retention constants include:

```text
Sensitive network metadata =
14 days

Core normalized metadata =
30 days
```

No packet payload is required for NI-04 V1.

## 3.2 Current NI-01 normal consumer read boundary is intentionally non-sensitive

Current:

```text
NetworkMetadataReadService
```

is explicitly a:

```text
typed, strictly non-sensitive read-only projection
```

It exposes presence/truncation state and safe protocol metadata but intentionally
does not return:

```text
raw DNS query names
raw DNS answer values
TLS SNI value
QUIC SNI value
raw sensitive endpoint history
```

Therefore NI-04 MUST NOT misuse the existing ordinary NI-01 read API.

## 3.3 NI-02B is the device-relative identity authority

Current:

```text
DeviceNetworkMetadataEdgeV1
```

already binds an NI-01 observation to an attributed:

```text
Site
client MAC
event time
device endpoint role
peer endpoint
direction
source observation ref
source event family
attribution provenance
```

and current Registry late binding can make retained Site+MAC edges visible to
an authoritative existing `device_id`.

NI-04 MUST consume that authority.

It MUST NOT re-run:

```text
IP → MAC
MAC → device_id
Registry identity
```

on its own.

## 3.4 Current NI-03 is deliberately lossy for service recognition

Current NI-03 reads a narrow NI-02B snapshot containing only:

```text
edge_id
event_at
source_event_family
```

for product protocol aggregation.

It intentionally excludes:

```text
DNS names
SNI
peer IP
raw endpoint data
```

Therefore:

```text
DeviceProtocolSummaryV1
```

is NOT an NI-04 recognition authority.

NI-04 must not attempt:

```text
DNS + TLS + QUIC
→ guess service
```

from the NI-03 public summary.

---

# 4. ARCHITECTURE DECISION — DATA SUFFICIENCY

The answer to the Technical Lead critical question is:

```text
CURRENT ACQUISITION SOURCES =
SUFFICIENT FOR A CONSERVATIVE NI-04 V1

CURRENT CONSUMER READ CONTRACTS =
NOT SUFFICIENT

NEW SURICATA EVENT FAMILY =
NOT REQUIRED FOR NI-04 V1

FLOW EVENT FAMILY =
NOT REQUIRED

PERIODIC TRAFFIC METER =
NOT REQUIRED

EXTERNAL ONLINE LOOKUP =
NOT REQUIRED

NI-01 SCHEMA CHANGE =
NOT REQUIRED

NI-02B STORAGE SCHEMA CHANGE =
NOT REQUIRED

NI-03 CONTRACT CHANGE =
FORBIDDEN / NOT REQUIRED
```

The missing architecture boundary is a protected in-process recognition evidence
bridge that combines:

```text
authoritative device-relative identity from NI-02B
+
sensitive recognition-only fields from NI-01
```

using immutable source observation identity.

---

# 5. CANONICAL NI-04 COMPONENT FLOW

Target V1 flow:

```text
                           accepted Suricata metadata
                                      ↓
                               NI-01 normalized store
                                      │
                     protected recognition-only read
                                      │
                                      │ source_observation_ref
                                      │
NI-02A authority → NI-02B projection ─┘
        ↓
authoritative Device-relative edges
        ↓
RecognitionProjectionSnapshotV1
        ↓
RecognitionSourceEvidenceV1
        ↓
RecognitionTaxonomyContractV1
+
RecognitionRuleSetV1
        ↓
DeviceServiceRecognitionReadService
        ↓
ephemeral ServiceObservationV1
        ↓
ephemeral DeviceServiceSummaryV1
        ↓
AdminQueryService
        ↓
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/service-intelligence
        ↓
Device Card → Service Intelligence
```

Permanent forbidden paths:

```text
Browser → NI-01 SQLite

Browser → NI-02B SQLite

Browser → raw EVE

NI-04 → raw PCAP

NI-04 → Suricata socket

NI-04 → query-time IP attribution

NI-04 → direct Registry identity construction

NI-04 → NI-03 DeviceProtocolSummaryV1 as recognition evidence

NI-04 → external cloud/API lookup during a Device Card request
```

---

# 6. ARCHITECTURE DECISION — NO NEW NI-04 USER-TRAFFIC STORE IN V1

NI-04 V1 creates:

```text
NO new user-traffic SQLite database
NO new ServiceObservation history database
NO new summary database
NO background recognition writer
NO recognition checkpoint
NO durable per-Device recognition cache
NO recognition retention worker
```

Exact model:

```text
ServiceObservationV1 =
ephemeral deterministic derived object

DeviceServiceSummaryV1 =
ephemeral deterministic read model
```

This is deliberate.

Reasons:

```text
1. NI-02B already owns temporal Device identity.

2. NI-01 already owns sensitive metadata retention.

3. The product window is only 24h, far inside the accepted 14-day
   sensitive metadata retention.

4. A new writer would require a second late-binding/retry/change-feed
   contract which does not currently exist.

5. Read-time derivation automatically sees:
   - later NI-02B attribution retry;
   - later Registry authoritative binding;
   - current accepted rule bundle;
   without replaying a second persistence pipeline.

6. V1 does not need historical service analytics.

7. Avoiding a product history store avoids silently extending DNS/SNI-derived
   browsing history retention.
```

Future durable service history requires a separate architecture revision.

---

# 7. PREREQUISITE — TASK-DTI-NI-04A

Before the main NI-04 product/UI implementation may start, Technical Lead must
prepare and accept a separate prerequisite implementation/admission task:

```text
TASK-DTI-NI-04A
RECOGNITION EVIDENCE BRIDGE + INITIAL KNOWLEDGE ADMISSION
```

NI-04A has exactly two purposes:

```text
A. expose the minimum sensitive evidence through protected internal read
   contracts without changing source ownership;

B. admit the first concrete local taxonomy/rules/knowledge bundle.
```

NI-04A MUST NOT implement:

```text
Admin Service Intelligence endpoint
Device Card Service Intelligence section
service polling
customer-visible service result
background recognition worker
new user-traffic database
```

Main:

```text
TASK-DTI-NI-04
```

remains:

```text
CODER HOLD
```

until NI-04A acceptance.

---

# 8. NI-04A — NI-02B PROTECTED RECOGNITION SNAPSHOT

The existing NI-02B store remains unchanged.

Add an internal read-owner method conceptually equivalent to:

```text
read_service_recognition_snapshot(
    site_id,
    device_id,
    client_mac,
    from_utc,
    to_utc,
    *,
    max_rows,
    deadline
) -> RecognitionProjectionSnapshotV1
```

The method belongs to:

```text
DeviceNetworkMetadataReadService
```

or an equivalent NI-02B-owned read-service boundary.

It is NOT an Admin API.

It is NOT public.

It MUST use the same NI-02B DB and the same strict schema validation.

## 8.1 Same-snapshot content

Within one NI-02B read-only SQLite snapshot it must read:

```text
projection runtime state

Site+MAC Registry binding state

bound device_id

eligible edge facts
```

## 8.2 RecognitionProjectionEdgeFactV1

Exact internal fields:

```text
edge_id: string

event_at: canonical UTC timestamp

source_observation_ref: canonical NI-01 observation UUID

source_event_family:
    dns
    tls
    quic

source_generation_id: canonical UUID

capture_source_id: canonical capture-source ID

network_scope_id: string

capture_scope_binding_digest: sha256 hex

device_endpoint_role:
    src
    dst

peer_ip: IPv4 | IPv6 | null

peer_port: integer 0..65535 | null

transport_protocol:
    TCP
    UDP
    null

peer_scope:
    local
    external
    unknown

direction:
    outbound
    inbound
    local
    unknown
```

These values remain internal to the recognition process.

They are forbidden from the product DTO except where separately transformed
into a safe derived field.

## 8.3 RecognitionProjectionSnapshotV1

Exact fields:

```text
schema_version = 1

site_id

device_id

identity_binding_state:
    authoritative
    not_yet_registry_resolved
    registry_unavailable
    absent

projection_runtime_state:
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

bound_device_id: UUID | null

facts: tuple[RecognitionProjectionEdgeFactV1, ...]

historical_window_completeness_claimed = false
```

## 8.4 Identity gate

Exactly as NI-03:

```text
authoritative binding
AND bound_device_id == requested device_id
→ edge facts may be returned
```

Any other identity state:

```text
facts = empty

NO MAC fallback
NO raw edge scan presented as Device evidence
```

Authoritative binding to a different device ID:

```text
integrity unavailable
```

## 8.5 Window

V1 accepts only:

```text
to_utc - from_utc = 86400 seconds
```

with half-open semantics:

```text
[from_utc, to_utc)
```

No caller-defined arbitrary history window.

## 8.6 Row cap

Exact:

```text
SERVICE_RECOGNITION_MAX_EDGE_ROWS =
5000
```

The reader may fetch at most:

```text
5001
```

rows to detect overflow.

If row 5001 exists:

```text
NO truncated recognition
NO newest-only recognition
→ recognition source unavailable for that request
```

## 8.7 Reader protections

Exact:

```text
SQLite mode=ro

PRAGMA query_only=ON

PRAGMA foreign_keys=ON

busy_timeout=500ms

same-snapshot runtime/binding/facts

no WAL checkpoint

no VACUUM

no writer lock

no NI-02B state mutation
```

---

# 9. NI-04A — NI-01 PROTECTED RECOGNITION EVIDENCE READ

NI-01 must remain the owner of its sensitive metadata.

NI-04 MUST NOT execute direct SQL against NI-01 tables.

Add a separate protected, internal, recognition-only method under NI-01 read
ownership conceptually equivalent to:

```text
read_recognition_evidence(
    site_id,
    observation_refs,
    *,
    deadline
) -> tuple[RecognitionSourceEvidenceV1, ...]
```

## 9.1 Caller restriction

This method is for in-process trusted consumers only.

The intended V1 caller is:

```text
DeviceServiceRecognitionReadService
```

It MUST NOT be wired directly to:

```text
Flask route
template
JavaScript
external API
Grafana
Loki
```

## 9.2 Batch bound

One NI-01 evidence fetch accepts at most:

```text
256 unique observation refs
```

Larger Device windows are fetched in sequential bounded batches.

No batch may contain:

```text
duplicate observation refs
mixed Site identity
invalid observation identity
```

## 9.3 RecognitionSourceEvidenceV1

Exact internal DTO:

```text
schema_version = 1

site_id

observation_id

event_at

source_event_family:
    dns
    tls
    quic

source_generation_id

source_event_identity

capture_source_id

network_scope_id

capture_scope_binding_digest

sensitive_endpoint_presence_state:
    observed_retained
    not_observed
    expired

src_ip: IPv4 | IPv6 | null
dst_ip: IPv4 | IPv6 | null
src_port: integer | null
dst_port: integer | null
transport_protocol: TCP | UDP | null

flow_id_decimal: decimal string | null
transaction_id_decimal: decimal string | null

dns:
    null
    or
    query_names_presence_state
    answer_values_presence_state
    queries_truncated
    answers_truncated
    queries:
        tuple[RecognitionDnsQueryV1, ...]
    answers:
        tuple[RecognitionDnsAnswerV1, ...]

tls:
    null
    or
    sni: string | null
    sni_presence_state

quic:
    null
    or
    sni: string | null
    sni_presence_state
```

Exact DNS child DTOs:

```text
RecognitionDnsQueryV1:
    ordinal: 0..7
    query_name: sensitive string
    query_type: source-preserved string

RecognitionDnsAnswerV1:
    ordinal: 0..31
    answer_type:
        A
        AAAA
        CNAME
    answer_value: sensitive string
```

## 9.4 Forbidden fields

Recognition read does NOT need and MUST NOT expose:

```text
raw Suricata JSON
raw source record body
packet payload
HTTP body
certificate content
credentials
cookies
Authorization headers
full PCAP
```

## 9.5 Missing/expired sensitive values

If sensitive values have expired or were not retained:

```text
do not fabricate them
do not read rotated raw EVE
do not reconstruct from logs
```

Return only the trustworthy presence/expired state.

---

# 10. EXACT CROSS-STORE LINKAGE CONTRACT

NI-04 does not perform a heuristic cross-store join.

Every source evidence item is eligible only if all required provenance checks
match the NI-02B edge:

```text
edge.site_id
==
source.site_id

edge.source_observation_ref
==
source.observation_id

edge.event_at
==
source.event_at

edge.source_event_family
==
source.source_event_family

edge.source_generation_id
==
source.source_generation_id

edge.capture_source_id
==
source.capture_source_id

edge.network_scope_id
==
source.network_scope_id

edge.capture_scope_binding_digest
==
source.capture_scope_binding_digest
```

Any mismatch:

```text
recognition integrity unavailable
```

No partial use of mismatched evidence.

This is the canonical bridge between:

```text
Device-relative authority
and
sensitive recognition evidence
```

---

# 11. CROSS-DATABASE CONSISTENCY MODEL

NI-04 V1 does NOT claim one atomic transaction across the NI-02B and NI-01
SQLite databases.

Exact safe sequence:

```text
1. open one bounded NI-02B snapshot;

2. read runtime + authoritative identity + edge facts;

3. close NI-02B snapshot;

4. read immutable/retained NI-01 observations by exact observation refs
   in bounded batches;

5. validate full provenance equality;

6. evaluate recognition.
```

This is accepted because:

```text
NI-02B edge facts are immutable while retained;

NI-01 observation identity is immutable;

the 24h product window is safely inside the 14-day sensitive retention;

provenance mismatch fails closed.
```

No cross-database "almost same timestamp" join is allowed.

---

# 12. NI-01 CONFIGURATION HANDOFF TO MAIN ADMIN RUNTIME

NI-04 must not freeze a second literal NI-01 database path.

The authoritative NI-01 deployment file remains:

```text
/etc/captive-portal/network-metadata.env
```

The canonical parser remains:

```text
network_metadata_config_from_env()
```

To permit the main `captive-portal.service` to construct an NI-01 read-only
consumer, install a deployment-owned drop-in:

```text
/etc/systemd/system/captive-portal.service.d/
15-network-metadata-read.conf
```

with:

```ini
[Service]
EnvironmentFile=-/etc/captive-portal/network-metadata.env
```

The leading `-` is intentional.

Absence of this optional file MUST NOT prevent the core portal process from
starting.

The existing:

```text
20-network-metadata-projection-read.conf
```

remains unchanged.

## 12.1 No aliases

Forbidden:

```text
SERVICE_RECOGNITION_NETWORK_METADATA_DB_PATH

SERVICE_RECOGNITION_NI01_DB_PATH

WEB_ADMIN_NI01_DB_PATH
```

or equivalent second authorities.

## 12.2 Enabled authority

NI-01 is considered deployment-enabled for recognition only when canonical:

```text
NetworkMetadataConfig.enabled == true
```

If disabled:

```text
NI-04 must not open an old NI-01 DB as fallback
```

## 12.3 Collision gate

Before production activation:

```text
NETWORK_METADATA_*
```

must not be independently duplicated with conflicting values in:

```text
/etc/default/captive-portal
```

Any duplicate key across loaded EnvironmentFiles with differing semantics:

```text
ACTIVATION HOLD
```

No general environment dump is required or allowed.

Only exact non-secret keys are inspected.

---

# 13. RECOGNITION TAXONOMY CONTRACT V1

Freeze:

```text
RecognitionTaxonomyContractV1
```

Taxonomy is a local immutable runtime artifact.

It separates three independent dimensions:

```text
Organization / Infrastructure

Service

Service Category
```

Permanent:

```text
organization != service != category
```

Examples of forbidden inference:

```text
Google infrastructure
!=
Google Search

Meta infrastructure
!=
WhatsApp

Cloudflare infrastructure
!=
the application using Cloudflare
```

---

# 14. TAXONOMY IDENTIFIER FORMAT

All taxonomy IDs are stable, lowercase ASCII identifiers.

## Organization ID

Pattern:

```text
^org\.[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$
```

Example shape:

```text
org.example
```

## Service ID

Pattern:

```text
^service\.[a-z0-9][a-z0-9._-]{1,58}[a-z0-9]$
```

Example shape:

```text
service.example
```

## Category ID

V1 category IDs are closed and exact:

```text
category.video_streaming

category.audio_streaming

category.messaging

category.social

category.cloud_storage

category.productivity_collaboration

category.gaming

category.software_distribution

category.web_search

category.other_supported
```

Unknown/unrecognized traffic MUST NOT be assigned:

```text
category.other_supported
```

merely to avoid an unknown result.

`category.other_supported` is only for an explicitly admitted known service
which does not fit another V1 category.

Adding another category:

```text
requires taxonomy version increment
and architecture/Tech Lead compatibility review
```

---

# 15. TAXONOMY RECORDS

## 15.1 OrganizationTaxonV1

Exact fields:

```text
organization_id

display_name

organization_kind:
    service_operator
    infrastructure_provider
    mixed
```

`display_name`:

```text
UTF-8
1..64 visible characters
no control characters
no leading/trailing whitespace
```

## 15.2 ServiceCategoryTaxonV1

Exact fields:

```text
service_category_id

display_name
```

The ID must be one of the closed V1 category IDs.

## 15.3 ServiceTaxonV1

Exact fields:

```text
service_id

display_name

organization_id

service_category_id

lifecycle_state:
    active
    retired
```

V1 relationship:

```text
one Service
→ exactly one primary Organization
→ exactly one primary Service Category
```

No multi-category weighting.

No confidence percentage.

No multiple "probable owners".

---

# 16. TAXONOMY VERSIONING

Exact top-level artifact:

```text
RecognitionTaxonomyContractV1:
    schema_version = 1

    taxonomy_id =
      "captivportal.network-intelligence.recognition-taxonomy"

    taxonomy_version:
      positive integer

    taxonomy_digest_sha256:
      canonical-content SHA-256

    organizations:
      tuple[OrganizationTaxonV1, ...]

    service_categories:
      tuple[ServiceCategoryTaxonV1, ...]

    services:
      tuple[ServiceTaxonV1, ...]
```

Any semantic taxonomy content change increments:

```text
taxonomy_version
```

IDs are immutable after admission.

A renamed display label does not change the stable ID but still increments the
taxonomy version.

Deleted IDs are not silently reused.

---

# 17. INITIAL TAXONOMY CONTENT IS NOT INFERRED FROM THE REQUEST EXAMPLES

The Technical Lead request listed:

```text
YouTube
WhatsApp
Telegram
Netflix
Spotify
```

as examples of the target result class, not as an approved recognition list.

Therefore this architecture does NOT silently promote those examples into
admitted V1 rules.

NI-04A must produce an exact:

```text
InitialRecognitionKnowledgeManifestV1
```

and an exact first taxonomy/rules bundle.

Production Service Recognition requires:

```text
at least one active admitted Service
+
at least one active admitted Service rule
```

An empty or demonstration-only rule bundle does not satisfy NI-04 product
acceptance.

---

# 18. KNOWLEDGE SOURCE GOVERNANCE

Recognition knowledge is local at runtime but must have provenance.

No runtime call to an external service is required or allowed.

Each admitted rule must reference one or more:

```text
RecognitionKnowledgeSourceV1
```

with exact fields:

```text
knowledge_ref

source_class:
    first_party_public
    controlled_owner_trace
    authoritative_registry
    reviewed_internal_research

publisher_or_owner

source_locator

claim_summary

reviewed_at_utc

review_due_at_utc
```

Forbidden knowledge admission:

```text
anonymous list with no provenance

LLM-only assertion

community guess without corroboration

"everyone knows this domain"

shared CDN IP ownership alone as exact service proof
```

Maximum accepted review interval in V1:

```text
365 days
```

Thus:

```text
review_due_at_utc - reviewed_at_utc
<= 365 days
```

An expired knowledge rule is not executed as service evidence.

It becomes inactive and contributes:

```text
recognition coverage = limited
```

until a reviewed bundle replaces it.

---

# 19. RECOGNITION RULESET V1

Freeze:

```text
RecognitionRuleSetV1
```

Exact top-level fields:

```text
schema_version = 1

ruleset_id =
  "captivportal.network-intelligence.service-recognition"

ruleset_version:
  positive integer

ruleset_digest_sha256

taxonomy_id

taxonomy_version

taxonomy_digest_sha256

knowledge_manifest_id

knowledge_manifest_version

rules:
  tuple[RecognitionRuleV1, ...]
```

The ruleset may reference only taxonomy records in the exact bundled taxonomy
version/digest.

---

# 20. RECOGNITION RULE V1

Exact fields:

```text
rule_id

rule_kind

target_type:
    service
    organization

target_id

hostname_pattern

knowledge_refs:
    non-empty tuple

reviewed_at_utc

review_due_at_utc

lifecycle_state:
    active
    retired
```

Rule ID pattern:

```text
^rule\.[a-z0-9][a-z0-9._-]{1,94}[a-z0-9]$
```

No regex rule language is admitted in V1.

No arbitrary expression language.

No user-entered rule execution.

---

# 21. ADMITTED RULE KINDS

V1 admits exactly:

```text
service_sni_exact

service_sni_suffix

service_dns_connected_exact

service_dns_connected_suffix

organization_sni_exact

organization_sni_suffix

organization_dns_connected_exact

organization_dns_connected_suffix
```

Explicitly NOT admitted in V1:

```text
service_ip_exact

service_ip_cidr

ASN-only service rule

port-only service rule

JA4-only service rule

user-agent service rule

payload rule

arbitrary regex rule

machine-learning classification rule
```

The parent architecture permits a future deterministic IP-only rule only after
separate admission.

This V1 admits none.

---

# 22. HOSTNAME CANONICALIZATION

Before matching a DNS query name or SNI:

```text
1. value must be a string;

2. length before normalization <= 253 bytes;

3. strip exactly one terminal "." if present;

4. lowercase ASCII;

5. reject non-ASCII input in V1;

6. each label length = 1..63;

7. each label must match:
   [a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?

8. total normalized name must be non-empty.
```

No Unicode/IDN conversion is attempted in V1.

Punycode already represented as ASCII is treated as ordinary ASCII hostname
syntax.

Invalid hostname:

```text
not a rule match
+
recognition coverage may become limited
```

No silent repair.

---

# 23. EXACT HOSTNAME RULE MATCHING

## Exact

```text
observed_host == rule.hostname_pattern
```

## Suffix

A suffix rule for:

```text
example.com
```

matches only:

```text
example.com
*.example.com
```

implemented semantically as:

```text
host == suffix
OR
host ends with "." + suffix
```

It MUST NOT match:

```text
notexample.com
```

Wildcard strings are not stored in `hostname_pattern`.

Within one rule kind:

```text
exact match
>
longer suffix
>
shorter suffix
```

---

# 24. ALLOWED INPUT SIGNAL TYPES

Closed V1 signal enum:

```text
tls_sni

quic_sni

dns_query_name

dns_answer_address

peer_address_correlation
```

Additional fields may be used only to validate context:

```text
event_at

Site

Device identity

direction

peer_scope

transport protocol
```

They are not service identifiers by themselves.

Not admitted as service evidence in V1:

```text
IP alone

port alone

TCP/UDP alone

organization ownership alone

generic cloud/CDN ownership alone

absence of a hostname

NI-03 protocol label alone
```

---

# 25. EVIDENCE STRENGTH CLASS

Closed enum:

```text
strong

correlated

weak_context
```

Exact meaning:

## strong

A unique admitted same-connection hostname rule:

```text
TLS SNI
or
QUIC SNI
```

directly identifies one service or organization.

## correlated

A service-specific DNS hostname plus a returned A/AAAA address plus a later
same-Device connection to that exact address inside the allowed correlation
window.

## weak_context

Organization/infrastructure context that does not establish a specific service.

Weak context alone can never resolve a Service.

---

# 26. DNS CONNECTION CORRELATION

Exact maximum correlation interval:

```text
DNS_CONNECTION_CORRELATION_SECONDS =
300
```

A DNS-correlated service result requires ALL:

```text
same Site

same authoritative Device

DNS query hostname matches one admitted service DNS rule

same DNS observation contains at least one A or AAAA answer

later eligible Device connection edge has peer_ip equal to one of those
A/AAAA answer values

connection event_at is within:
[dns_event_at, dns_event_at + 300 seconds]

connection is:
direction=outbound

connection peer_scope=external

no stronger contradictory service signal exists
```

DNS CNAME is not sufficient for V1 connection correlation because current
normalized answer representation does not retain enough owner-name linkage to
reconstruct a complete DNS CNAME chain safely.

CNAME values may be retained by NI-01 but are not a V1 service resolution
primitive.

---

# 27. DNS QUERY ALONE

Exact rule:

```text
DNS query name
without a qualifying subsequent connection
=
INSUFFICIENT
```

It may contribute to internal recognition coverage diagnostics.

It MUST NOT produce:

```text
service_resolved
```

Reason:

```text
prefetch
background resolver activity
cached behavior
application probes
DNS-only lookups
```

must not be presented as proven service use.

---

# 28. DIRECT SNI RECOGNITION

A TLS/QUIC SNI service result is allowed only when ALL:

```text
edge belongs to authoritative exact Site+Device

edge direction = outbound

edge peer_scope = external

SNI presence state = observed_retained

SNI canonicalization passes

exactly one highest-precedence active service rule resolves the hostname

rule knowledge is not expired
```

Then:

```text
evidence_strength_class = strong

support_state = directly_supported

resolution_state = service_resolved
```

No IP ownership is required.

---

# 29. RULE PRIORITY

Rule-class priority is fixed.

Lower number is stronger:

```text
10 service_sni_exact

20 service_sni_suffix

30 service_dns_connected_exact

40 service_dns_connected_suffix

50 organization_sni_exact

60 organization_sni_suffix

70 organization_dns_connected_exact

80 organization_dns_connected_suffix
```

Within equal rule kind:

```text
exact hostname uniqueness
or
longest suffix specificity
```

is applied before `rule_id` tie handling.

`rule_id` is never a semantic winner.

If two different Service IDs remain at the same effective highest Service
priority/specificity:

```text
resolution_state = ambiguous

NO service result
```

---

# 30. CONFLICT SEMANTICS

The engine never averages conflicting evidence.

No confidence percentage.

Exact behavior:

```text
unique stronger Service result
+
weaker different organization/infrastructure context
→ keep Service result
→ do not reinterpret infrastructure provider as service owner

two equally strong different Service results
→ ambiguous
→ no Service result

direct SNI Service A
+
weaker stale/correlated DNS Service B
→ Service A wins

two direct SNI rules matching different services at equal effective specificity
→ ambiguous
→ no Service result

only organization rules match
→ organization_resolved
→ service_id null

no eligible rule match
→ unknown
```

---

# 31. SERVICE OWNERSHIP VS INFRASTRUCTURE ORGANIZATION

When a Service is resolved:

```text
ServiceObservationV1.organization_id
=
the Service's primary organization_id from taxonomy
```

It does NOT become:

```text
owner of peer IP
CDN provider
cloud provider
DNS resolver operator
```

An observed infrastructure organization can be represented only as a separate
organization-only recognition observation.

NI-04 public Service Intelligence V1 does not publish a "Recent Organizations"
list.

Future NI-05 consumes the NI-04 recognition owner, not a second classifier.

---

# 32. SERVICE OBSERVATION V1

Freeze:

```text
ServiceObservationV1
```

It is an internal, ephemeral, deterministic record.

Exact fields:

```text
schema_version = 1

service_observation_id:
    64-char lowercase SHA-256 hex

site_id

device_id

observed_at:
    canonical UTC timestamp

organization_id:
    string | null

service_id:
    string | null

service_category_id:
    string | null

evidence_strength_class:
    strong
    correlated
    weak_context

support_state:
    directly_supported
    multi_signal_supported
    contextual_only
    insufficient
    conflicting
    unavailable

supporting_signal_types:
    sorted unique tuple from the V1 signal enum

evidence_refs:
    sorted unique tuple[RecognitionEvidenceRefV1, ...]

recognition_ruleset_id

recognition_ruleset_version

recognition_ruleset_digest_sha256

taxonomy_id

taxonomy_version

taxonomy_digest_sha256

resolution_state:
    service_resolved
    organization_resolved
    ambiguous
    unknown
    unavailable
```

---

# 33. RECOGNITION EVIDENCE REF V1

Exact internal DTO:

```text
RecognitionEvidenceRefV1

edge_id

source_observation_ref

signal_type

event_at
```

It does NOT contain:

```text
DNS name
SNI
IP
port
raw payload
```

Evidence refs are internal only.

They are not serialized to Admin API.

---

# 34. SERVICE OBSERVATION ID

`service_observation_id` is deterministic:

```text
SHA-256(
  canonical JSON of:
    schema_version
    site_id
    device_id
    observed_at
    organization_id
    service_id
    service_category_id
    evidence_strength_class
    support_state
    supporting_signal_types sorted
    evidence_refs sorted
    recognition_ruleset_id
    recognition_ruleset_version
    recognition_ruleset_digest_sha256
    taxonomy_id
    taxonomy_version
    taxonomy_digest_sha256
)
```

No random UUID.

Same source facts + same rule/taxonomy versions + same evaluated semantics produce
the same observation identity.

---

# 35. SERVICE OBSERVATION FIELD INVARIANTS

## service_resolved

Requires:

```text
organization_id != null

service_id != null

service_category_id != null

support_state in:
    directly_supported
    multi_signal_supported

evidence_strength_class in:
    strong
    correlated
```

Taxonomy relationship must match exactly.

## organization_resolved

Requires:

```text
organization_id != null

service_id = null

service_category_id = null

support_state in:
    directly_supported
    multi_signal_supported
    contextual_only
```

## ambiguous

Requires:

```text
service_id = null
service_category_id = null
support_state = conflicting
```

`organization_id` may be present only if all highest-strength conflicting
Service candidates share the exact same taxonomy organization.

## unknown

Requires:

```text
service_id = null
service_category_id = null
support_state = insufficient
```

## unavailable

Requires:

```text
organization_id = null
service_id = null
service_category_id = null
support_state = unavailable
```

---

# 36. OBSERVED_AT SEMANTICS

For direct SNI:

```text
observed_at =
SNI connection event_at
```

For DNS-correlated recognition:

```text
observed_at =
qualifying subsequent connection event_at
```

NOT:

```text
DNS query time
```

This means "service use was supported at the connection event".

For organization-only direct SNI:

```text
observed_at =
SNI event_at
```

---

# 37. DEVICE SERVICE SUMMARY V1

Freeze:

```text
DeviceServiceSummaryV1
```

Exact fields:

```text
schema_version = 1

site_id

device_id

evaluated_at_utc

window:
    from_utc
    to_utc
    duration_seconds = 86400
    recent_from_utc
    recent_duration_seconds = 3600

availability_state:
    usable
    degraded

evidence_state:
    supported_results_present
    no_supported_result_observed_with_sufficient_coverage
    insufficient_source_coverage
    insufficient_attribution
    recognition_limited
    identity_pending

identity_binding_state:
    authoritative
    pending
    unavailable
    absent

recent_services:
    tuple[RecentServiceV1, ...]

service_categories:
    tuple[RecentServiceCategoryV1, ...]

last_service_observation:
    LastServiceObservationV1 | null

freshness_state:
    fresh
    recent
    stale
    unavailable

coverage:
    ServiceRecognitionCoverageV1

recognition_ruleset_id

recognition_ruleset_version

recognition_ruleset_digest_sha256

taxonomy_id

taxonomy_version

taxonomy_digest_sha256
```

No raw recognition evidence.

---

# 38. SERVICE SUMMARY WINDOW

NI-04 inherits the NI-03 time policy exactly.

Summary window:

```text
24h
86400 seconds
```

Recent Services window:

```text
60m
3600 seconds
```

For evaluation time `evaluated_at_utc`:

```text
summary_from =
evaluated_at - 24h

recent_from =
evaluated_at - 60m
```

Half-open intervals:

```text
summary:
[summary_from, evaluated_at)

recent:
[recent_from, evaluated_at)
```

Browser cannot supply custom time bounds.

Server owns evaluation time.

---

# 39. RECENT SERVICE V1

Exact public DTO:

```text
RecentServiceV1

service_id

display_name

organization_id

organization_display_name

service_category_id

service_category_display_name

last_observed_at

support_state:
    directly_supported
    multi_signal_supported
```

No raw evidence.

No confidence percentage.

No IP/domain/SNI.

Maximum:

```text
12 Recent Services
```

If more than 12 distinct supported services occur inside 60m:

```text
sort first
take first 12
set public summary recognition coverage = limited
```

This is the only admitted result-cardinality truncation.

It is visible through coverage.

It is not silent.

---

# 40. RECENT SERVICES DEDUPLICATION

Group successful service observations inside the Recent window by:

```text
service_id
```

For each service retain:

```text
max(observed_at)
```

If the same service has both:

```text
directly_supported
and
multi_signal_supported
```

at the exact same latest timestamp, prefer:

```text
directly_supported
```

for display support state.

Multiple DNS/TLS/QUIC evidence events therefore do not create duplicate Service
rows.

---

# 41. RECENT SERVICE SORT

Sort:

```text
last_observed_at DESC
```

Tie:

```text
service_id ASC
```

No event count.

No traffic volume.

No popularity score.

---

# 42. SERVICE CATEGORY SUMMARY

Exact DTO:

```text
RecentServiceCategoryV1

service_category_id

display_name

last_observed_at
```

The list includes only categories represented by:

```text
Recent Services
```

Deduplicate by category ID.

`last_observed_at`:

```text
max(last_observed_at of Recent Services in category)
```

Sort:

```text
last_observed_at DESC

then service_category_id ASC
```

Maximum:

```text
10
```

because V1 category vocabulary is closed to 10 categories.

No counts or percentages.

---

# 43. LAST SERVICE OBSERVATION

Exact DTO:

```text
LastServiceObservationV1

service_id

display_name

organization_id

organization_display_name

service_category_id

service_category_display_name

observed_at

support_state:
    directly_supported
    multi_signal_supported
```

Choose from all `service_resolved` observations inside 24h:

```text
observed_at DESC

then service_id ASC

then service_observation_id ASC
```

No organization-only event may become Last Service Observation.

---

# 44. COVERAGE V1

Exact public DTO:

```text
ServiceRecognitionCoverageV1

scope =
    current_pipeline

source_state:
    usable
    degraded
    unavailable
    unknown

attribution_state:
    usable
    degraded
    unavailable
    unknown

projection_state:
    usable
    degraded

recognition_state:
    usable
    limited

historical_window_completeness_claimed =
    false
```

If rule/taxonomy/evidence infrastructure is globally unavailable such that a
summary cannot be evaluated safely:

```text
no summary DTO
→ HTTP 503 recognition_unavailable or source_unavailable
```

Thus public successful DTO does not use:

```text
recognition_state=unavailable
```

---

# 45. SOURCE / ATTRIBUTION COVERAGE MAPPING

NI-04 inherits NI-03's frozen mapping from current NI-02B runtime state.

## usable

```text
projection_state  = usable
source_state      = usable
attribution_state = usable
```

## registry_degraded

```text
projection_state  = degraded
source_state      = usable
attribution_state = usable
```

## attribution_unavailable

```text
projection_state  = degraded
source_state      = usable
attribution_state = degraded
```

## source_unavailable

```text
projection_state  = degraded
source_state      = unavailable
attribution_state = unknown
```

## capacity_waiting_reader / capacity_halted / blocked_conflict / degraded

```text
projection_state  = degraded
source_state      = degraded
attribution_state = degraded
```

## initializing / stopping

```text
projection_state  = degraded
source_state      = unknown
attribution_state = unknown
```

Unknown runtime enum:

```text
integrity unavailable
→ HTTP 503
```

NI-04 does not invent a second mapping.

---

# 46. RECOGNITION COVERAGE STATE

`recognition_state=usable` requires ALL:

```text
taxonomy valid

ruleset valid

knowledge references valid and not expired for all rules actually needed
during evaluation

all selected source observation refs were safely read or had an explicitly
trustworthy non-sensitive absence state

no row/signal cap exceeded

no ambiguous highest-strength candidate affecting the absence claim

no truncation/missing sensitive fields that could hide a supported rule match
for the observed candidate set
```

`recognition_state=limited` if evaluation completed but any applies:

```text
SNI not observed for otherwise eligible TLS/QUIC event

sensitive value marked expired/unavailable

DNS names/answers truncated

invalid hostname that cannot be safely normalized

DNS-only service candidate lacked qualifying connection

highest-strength service conflict produced ambiguous result

knowledge rule relevant to an observed candidate is expired

Recent Service cardinality exceeded 12
```

Limited does NOT erase already supported valid Service results.

---

# 47. EVIDENCE STATE PRECEDENCE

Exact order:

```text
1. identity not authoritative
→ identity_pending

2. at least one service_resolved observation in 24h
→ supported_results_present

3. source_state != usable
→ insufficient_source_coverage

4. attribution_state != usable
→ insufficient_attribution

5. recognition_state != usable
→ recognition_limited

6. otherwise
→ no_supported_result_observed_with_sufficient_coverage
```

This order is normative.

---

# 48. SAFE EMPTY MEANING

If:

```text
evidence_state =
no_supported_result_observed_with_sufficient_coverage
```

safe product wording is:

```text
No supported services recognized in the last 24 hours.
```

Mandatory qualification:

```text
This does not prove that the Device used no Internet services or had no
network activity.
```

Forbidden:

```text
No services used

No Internet usage

No applications used

Device was inactive
```

---

# 49. FRESHNESS V1

Exact public enum:

```text
fresh

recent

stale

unavailable
```

Base temporal freshness from Last Service Observation:

```text
no Last Service Observation
→ unavailable

0 <= age <= 300 seconds
→ fresh

300 < age <= 3600 seconds
→ recent

3600 < age <= 86400 seconds
→ stale
```

No service evidence older than 24h participates.

---

# 50. COVERAGE CAP ON FRESHNESS

Apply after base temporal freshness.

If:

```text
source_state in {unavailable, unknown}
```

and evidence exists:

```text
freshness = stale
```

If:

```text
source_state=degraded
```

then:

```text
fresh → recent
recent → recent
stale → stale
```

If:

```text
attribution_state in {degraded, unavailable, unknown}
```

then:

```text
fresh → recent
recent → recent
stale → stale
```

If:

```text
recognition_state=limited
```

then:

```text
fresh → recent
recent → recent
stale → stale
```

If source + attribution + recognition are usable:

```text
use base freshness unchanged
```

---

# 51. CURRENT DEGRADED PRODUCTION SEMANTICS

Current observed production can enter:

```text
attribution_unavailable
```

while already committed Device edges remain readable.

NI-04 MUST preserve useful committed facts.

Exact:

```text
runtime=attribution_unavailable
+
authoritative Device binding
+
supported service observations from already committed edges
→ HTTP 200
→ show supported services
→ availability=degraded
→ source=usable
→ attribution=degraded
→ base fresh capped to recent
```

The newest pending/unattributed tail is not silently treated as absence.

No separate "must always be usable" health gate is required before implementation.

Production activation must nevertheless test the accepted degraded-state
behavior.

---

# 52. AVAILABILITY STATE

Successful DTO:

```text
availability_state=usable
```

only when:

```text
projection_state=usable
AND
identity_binding_state=authoritative
AND
recognition_state=usable
```

Otherwise a safely evaluable result is:

```text
availability_state=degraded
```

Readable degraded state is not automatically HTTP 503.

---

# 53. COMMON CDN / CLOUD ADDRESS CASE

Case:

```text
peer IP belongs to shared CDN/cloud
```

V1:

```text
IP alone
→ no Service

generic cloud ownership
→ no Service

organization-only hostname rule
→ may resolve Organization

specific admitted Service SNI
→ may resolve Service

specific admitted DNS + exact answer + subsequent peer match
→ may resolve Service
```

No IP-owner-to-service shortcut.

---

# 54. MULTIPLE SERVICES OF ONE ORGANIZATION

One organization may own multiple Services.

Therefore:

```text
organization_id match
```

does not select among those Services.

A Service result requires a Service-specific rule.

If evidence supports only the organization:

```text
organization_resolved
service_id = null
```

---

# 55. DNS CACHE

If the Device connects using a cached DNS answer and no qualifying DNS event
exists inside the 300-second correlation interval:

```text
DNS-correlated recognition =
NO
```

If a direct admitted SNI rule exists:

```text
SNI recognition may still succeed
```

If no direct signal exists:

```text
no Service result
recognition may be limited
```

No historical DNS archaeology beyond the fixed window.

---

# 56. DNS QUERY WITHOUT CONNECTION

Exact:

```text
query only
→ no Service result
```

even if the query hostname is an admitted Service domain.

This is mandatory false-positive protection.

---

# 57. MISSING SNI

If:

```text
TLS/QUIC event exists
SNI absent/not_observed
```

then:

```text
no SNI rule evaluation
```

Other valid correlated evidence may still resolve a Service.

If not:

```text
no Service result
recognition_state may be limited
```

---

# 58. ECH / ENCRYPTED HOSTNAME CASE

Current source contracts do not provide an authoritative positive:

```text
ECH detected
```

product fact.

Therefore NI-04 V1 MUST NOT label:

```text
ECH
encrypted SNI
```

merely because SNI is absent.

Exact behavior:

```text
SNI unavailable
→ no direct SNI evidence

use other admitted evidence if available

otherwise no Service result
+
limited recognition where appropriate
```

---

# 59. VPN / TUNNEL CASE

V1 does not attempt to infer inner services behind a VPN/tunnel.

Permanent:

```text
outer endpoint evidence
!=
inner application evidence
```

A directly admitted hostname may identify an outer VPN provider/service only if
a future/initial ruleset explicitly contains such a Service.

It does not authorize inference of traffic carried inside the tunnel.

No "Telegram through VPN" claim from VPN endpoint ownership.

---

# 60. LOCAL DNS RESOLVER

A Device DNS query to a local resolver may participate in correlation when:

```text
the DNS observation is authoritatively Device-relative

the query hostname is available

A/AAAA answer values are available

a subsequent same-Device external connection matches an answer value
within 300 seconds
```

The resolver itself is not the Service.

---

# 61. PUBLIC DNS RESOLVER

Same rule as local resolver.

Public resolver organization/IP does not become the queried Service.

No:

```text
Google DNS
→ Google service
```

inference.

---

# 62. DEVICE IP REASSIGNMENT

NI-04 never binds service evidence through the current Device IP.

Authority is:

```text
NI-02A event-time attribution
→ NI-02B immutable Device-relative edge
```

Therefore later IP reassignment does not migrate prior service evidence to
another Device.

No cross-MAC merge.

No IP-only permanent identity.

---

# 63. EVENT BEFORE REGISTRY DEVICE CREATION

If NI-02B has retained Site+MAC edges but current binding is not authoritative:

```text
NI-04 returns identity_pending
```

No MAC fallback.

When NI-02B later establishes authoritative binding to the existing Device:

```text
the next NI-04 read may evaluate still-retained pre-binding edges
inside the 24h window
```

No NI-04 replay writer is needed.

---

# 64. LATE ATTRIBUTION / LATE EDGE

If NI-02B later materializes an edge for an older source event due to accepted
attribution retry:

```text
the next NI-04 read sees it naturally
if event_at remains inside the 24h window
```

No NI-04 cursor/change-feed is needed.

This is a major reason V1 is read-time rather than a new writer pipeline.

---

# 65. LATE SOURCE EVENT

NI-04 uses authoritative:

```text
event_at
```

for product timing.

`ingested_at` or `projected_at` do not become service-use time.

A late source event is eligible only if:

```text
summary_from <= event_at < evaluated_at
```

and all source/provenance/retention checks pass.

If outside the 24h window:

```text
not shown
```

No window rewriting.

---

# 66. RULE UPDATE / RE-EVALUATION

Because NI-04 V1 does not persist Service results:

```text
new accepted ruleset
→ future reads evaluate retained 24h evidence under the new ruleset
```

No historical Service row rewrite exists.

Every public result carries exact:

```text
ruleset ID/version/digest
taxonomy ID/version/digest
```

Therefore the semantic version that produced the current result is explicit.

Historical reproduction after underlying NI-01 sensitive evidence expires is
not promised by V1.

This limitation is intentional and must be documented.

---

# 67. RULESET UPDATE AND ROLLBACK

V1 rule/taxonomy artifacts are repository-owned immutable files.

Preferred package ownership:

```text
app/network_service_recognition/
    taxonomy-v1.json
    ruleset-v1.json
    knowledge-manifest-v1.json
```

or semantically equivalent paths under the same module.

Runtime network download is forbidden.

Update requires:

```text
reviewed repository change
→ tests
→ accepted commit
→ deploy
→ captive-portal.service restart
```

Rollback:

```text
feature OFF
or
rollback to previous accepted application commit/artifact bundle
→ restart captive-portal.service
```

No rule hot-edit UI.

No Admin Settings rule editor.

No remote rule feed.

---

# 68. STARTUP ARTIFACT VALIDATION

When NI-04 feature is enabled, startup composition validates:

```text
taxonomy schema
taxonomy IDs
category enum
referential integrity
taxonomy digest

knowledge manifest schema
knowledge refs
review dates

ruleset schema
ruleset ID/version/digest
ruleset → exact taxonomy reference
rule IDs
rule kinds
target type/ID
hostname canonical form
knowledge refs
review due dates
duplicate/conflicting impossible static definitions
hard cardinality caps
```

Invalid artifacts:

```text
NI-04 dependency state = recognition_configuration_unavailable
```

Core portal/Admin still starts.

NI-03 still works.

NI-04 endpoint:

```text
503 recognition_unavailable
```

No private parse error is exposed.

---

# 69. ARTIFACT CARDINALITY CAPS

V1 hard caps:

```text
organizations <= 256

services <= 512

service categories = 10 exact IDs

rules <= 2048

knowledge sources <= 4096

hostname patterns <= 2048
```

Exceeding a cap:

```text
artifact invalid
→ NI-04 unavailable
```

No silent truncation.

---

# 70. RULE EVALUATION DETERMINISM

V1 recognition engine is:

```text
pure deterministic evaluation
```

given:

```text
RecognitionProjectionSnapshotV1

RecognitionSourceEvidenceV1 set

RecognitionTaxonomyContractV1

RecognitionRuleSetV1

evaluated_at_utc
```

Forbidden:

```text
random score

probability threshold

LLM call

online reputation API

time-dependent external lookup

unordered map iteration as tie-break

"best effort" hidden fallback
```

---

# 71. DEVICE SERVICE RECOGNITION READ SERVICE

New semantic owner:

```text
DeviceServiceRecognitionReadService
```

Preferred module:

```text
app/network_service_recognition/
```

Canonical method:

```text
get_device_service_summary(
    site_id,
    device_id,
    client_mac,
    *,
    evaluated_at_utc,
    deadline
) -> DeviceServiceSummaryV1
```

All inputs are server-side/internal.

Browser never supplies:

```text
client_mac
from_utc
to_utc
ruleset
taxonomy version
raw hostname
```

---

# 72. READ ALGORITHM — EXACT ORDER

For one request:

```text
1. validate Site/device/MAC/internal evaluated_at;

2. acquire NI-04 concurrency slot;

3. derive:
   summary_from = evaluated_at - 24h
   recent_from  = evaluated_at - 60m;

4. read one NI-02B recognition snapshot;

5. if identity not authoritative:
   return safe identity_pending summary without NI-01 sensitive read;

6. enforce max 5000 edge facts;

7. collect unique source_observation_ref values;

8. read NI-01 recognition evidence in <=256-ref batches;

9. verify complete cross-store provenance;

10. canonicalize only the needed sensitive values in memory;

11. evaluate direct SNI rules;

12. build bounded DNS→answer→connection correlation candidates;

13. evaluate correlated rules;

14. resolve conflicts deterministically;

15. create ephemeral ServiceObservationV1 records;

16. aggregate DeviceServiceSummaryV1;

17. validate public DTO cross-field invariants;

18. serialize safe result;

19. release request-local sensitive data;
```

No source data is written.

---

# 73. IN-MEMORY SENSITIVE DATA LIFETIME

Raw:

```text
DNS names
SNI
peer addresses
```

used by NI-04 exist only:

```text
inside the bounded request evaluation
```

They MUST NOT be:

```text
stored in NI-04 DB
cached across requests
placed in global module state
placed in browser payload
placed in template attributes
logged
emitted to metrics labels
persisted in localStorage/sessionStorage
```

Normal Python/process memory reclamation is sufficient; no claim of secure memory
zeroization is made.

---

# 74. RECOGNITION SIGNAL PROCESSING CAPS

Per NI-04 request:

```text
max projection edge facts =
5000

max unique source observation refs =
5000

NI-01 read batch =
256 refs

max total hostname/SNI/DNS answer scalar values examined =
25000

max ServiceObservationV1 internal records =
5000

max Recent Services public =
12

max public categories =
10
```

If an internal hard source/signal cap would be exceeded:

```text
NO partial Service set
→ HTTP 503 source_unavailable
```

Except the explicitly defined `Recent Services > 12` presentation bound, which
returns the first 12 with:

```text
recognition_state=limited
```

because the full underlying supported set was evaluated safely.

---

# 75. ADMIN AUTHORIZATION

NI-04 Device Card reuses the existing capability:

```text
admin.read.device
```

No new write capability.

No new role.

No new Site authority.

Reason:

```text
Service Intelligence is a read-only derived view of the same exact Device.
```

Future separate access control for sensitive raw evidence is irrelevant because
raw evidence is not exposed through Admin.

---

# 76. ADMIN API ENDPOINT

Exact:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/service-intelligence
```

No:

```text
POST
PUT
PATCH
DELETE
```

No query parameters.

No request body.

API version:

```text
admin.device.service-intelligence.v1
```

---

# 77. ADMIN API SUCCESS ENVELOPE

Exact top-level shape:

```json
{
  "api_version": "admin.device.service-intelligence.v1",
  "request_id": "<uuid>",
  "site_id": "<site_id>",
  "result": {
    "...": "DeviceServiceSummaryV1"
  },
  "page": null
}
```

No pagination.

Response maximum:

```text
16384 bytes
```

If exceeded:

```text
503 response_too_large
```

No truncation.

---

# 78. API CACHE CONTRACT

Exact headers:

```text
Cache-Control: no-store

Pragma: no-cache
```

No ETag.

No CORS expansion.

No browser cache reuse.

Same-origin Admin policy remains.

---

# 79. API ERROR MAPPING

Exact safe mapping:

```text
400 invalid_request
→ invalid Site/device syntax
→ any query parameter
```

```text
401 authentication_required
→ no valid Admin session
```

```text
403 site_forbidden
→ Site denied
→ admin.read.device denied
```

```text
404 not_found
→ Device absent in exact Site
→ NI-04 feature disabled
```

```text
429 concurrency_limit
Retry-After: 1
→ NI-04 or shared Admin read gate unavailable
```

```text
503 query_deadline
→ bounded deadline expired
```

```text
503 source_unavailable
→ NI-01 disabled
→ NI-02B disabled
→ required DB unavailable
→ schema untrusted
→ provenance mismatch
→ hard edge/signal cap exceeded
```

```text
503 recognition_unavailable
→ taxonomy/rules/knowledge artifact unavailable or invalid
```

```text
503 response_too_large
→ 16 KiB cap exceeded
```

```text
500 internal_error
→ unexpected application failure
```

No exception text.

No raw hostname.

No DB path.

No rule file path.

---

# 80. FEATURE GATE

Introduce:

```text
WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED
```

Repository default:

```text
false
```

Exact values:

```text
true
false
```

It is deployment-owned.

It is NOT a writable Admin Settings Stage-1 key.

Activation target:

```text
captive-portal.service restart
```

No hot enable.

No systemd control button.

---

# 81. FEATURE OFF

If:

```text
WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED=false
```

then:

```text
no NI-04 service-composition requirement

no NI-01 recognition reader opened by Admin

no NI-04 Device Card section

NI-04 API = 404 feature absent
```

NI-03 behavior unchanged.

---

# 82. OPTIONAL DEPENDENCY FAILURE

If feature is true but:

```text
NI-01 env missing

NI-01 config invalid

NI-01 disabled

NI-01 DB unavailable

NI-02B config unavailable

NI-02B DB unavailable

recognition artifacts invalid
```

then:

```text
captive-portal.service still starts

Guest Portal still starts

CAPPORT still starts

Authorization still starts

existing Admin still starts

NI-03 remains independently available according to its own contract
```

NI-04 alone becomes unavailable.

---

# 83. DEVICE CARD SECTION

NI-04 adds a separate section:

```text
Service Intelligence
```

It MUST NOT rename or replace the existing:

```text
Network / Protocol Intelligence
```

section.

NI-03 remains the authority for protocol-family presentation.

NI-04 remains the authority for service recognition.

---

# 84. DEVICE CARD DEFAULT FIELDS

The Service Intelligence section shows:

```text
Recent Services

Service Categories

Last Service Observation

Freshness

Recognition coverage

Source coverage

Attribution coverage

Last evaluated

manual Refresh
```

No raw:

```text
DNS
SNI
IP
port
rule ID
knowledge URL
evidence ref
```

by default.

No hidden expandable raw browsing history in V1.

---

# 85. SERVICE ITEM PRESENTATION

A recognized service item shows conceptually:

```text
<Service Display Name>
<Service Category Display Name>
<Last observed timestamp>
```

Organization display name MAY be shown as secondary text because it is a safe
taxonomy fact attached to an already resolved Service.

It MUST NOT show:

```text
confidence %
domain
SNI
remote IP
DNS query
```

---

# 86. EMPTY UI — SUFFICIENT COVERAGE

When:

```text
evidence_state =
no_supported_result_observed_with_sufficient_coverage
```

title:

```text
No supported services recognized
```

message:

```text
No supported service was recognized in the last 24 hours.
This does not prove that no Internet service or network activity occurred.
```

---

# 87. EMPTY UI — INSUFFICIENT SOURCE

When:

```text
evidence_state=insufficient_source_coverage
```

show:

```text
Service recognition has insufficient source coverage.
```

Do not show:

```text
No services
```

---

# 88. EMPTY UI — INSUFFICIENT ATTRIBUTION

When:

```text
evidence_state=insufficient_attribution
```

show:

```text
Service recognition has incomplete Device attribution coverage.
```

No absence claim.

---

# 89. EMPTY UI — RECOGNITION LIMITED

When:

```text
evidence_state=recognition_limited
```

show:

```text
Service recognition is limited by the currently observable or admitted evidence.
```

No guessed result.

---

# 90. IDENTITY PENDING UI

When:

```text
identity_binding_state in:
pending
unavailable
absent
```

show:

```text
Device network identity binding pending
```

No MAC fallback.

No raw MAC display added by NI-04.

---

# 91. STALE SERVICE EVIDENCE

If:

```text
freshness_state=stale
```

a previously supported Service result remains visible with:

```text
Stale evidence
```

It is not cleared solely because current source coverage degraded.

---

# 92. CLIENT AUTO REFRESH

NI-04 is heavier than NI-03 and therefore uses its own bounded cadence.

Exact normal automatic interval:

```text
120 seconds
```

Initial request:

```text
immediate when section becomes active/visible
```

Do not start polling when:

```text
section absent
document hidden
page stopping
session terminally failed
```

Stop on:

```text
pagehide

401

403

404 for Device/feature
```

On visibility return:

```text
refresh immediately if 120s has elapsed
otherwise schedule remaining interval
```

No 1-second or 10-second polling.

---

# 93. CLIENT REQUEST CONCURRENCY

Per Device Card:

```text
maximum in-flight NI-04 request =
1
```

Manual refresh during in-flight request:

```text
do not start another request

coalesce to exactly one follow-up
```

The page-level Refresh may use the same NI-04 coordinator.

No second independent NI-04 loop.

NI-03 polling remains independent and unchanged.

---

# 94. CLIENT TIMEOUT / BACKOFF

Browser timeout:

```text
10 seconds
```

using AbortController or equivalent current project pattern.

Automatic retry schedule after consecutive failure:

```text
1st failure → 120s

2nd failure → 300s

3rd+ → 600s

success → reset to 120s
```

Manual refresh bypasses wait time but not concurrency.

Maximum last-good Service Intelligence render after request failures:

```text
900 seconds
15 minutes
```

After 15m from the last successful:

```text
evaluated_at_utc
```

clear active current service data and show unavailable.

This is separate from service evidence freshness.

---

# 95. SERVER CONCURRENCY

NI-04 uses:

```text
existing shared AdminQueryExecutionControls
```

plus an NI-04-specific process-local gate:

```text
maximum concurrent NI-04 recognition reads =
1
```

If occupied:

```text
429 concurrency_limit
Retry-After: 1
```

This intentionally protects two upstream SQLite stores.

---

# 96. SERVER DEADLINE

Exact NI-04 hard request evaluation ceiling:

```text
5 seconds
```

Effective deadline:

```text
min(
    remaining shared Admin query deadline,
    5 seconds
)
```

No read transaction is allowed to remain intentionally open past the deadline.

NI-01 read batches and rule evaluation share the same total deadline.

---

# 97. PERFORMANCE ACCEPTANCE

Correctness hard ceilings:

```text
5000 projection edges

5000 source refs

25000 scalar recognition values

2048 rules

5s server deadline

1 concurrent recognition evaluation

16 KiB response
```

Mandatory lab acceptance must prove:

```text
NI-02B normal writer continues;

NI-01 normal writer continues;

no false capacity_halted;

no checkpoint corruption;

no writer lock acquisition by NI-04;

no Portal/Auth/CAPPORT latency regression attributable to NI-04
outside accepted measurement noise;

no unbounded RSS growth across repeated Device Card refresh;

no request retains a SQLite snapshot indefinitely.
```

At the maximum admitted synthetic fixture, peak incremental process RSS caused by
one NI-04 evaluation must remain:

```text
<= 64 MiB
```

If this gate fails:

```text
STOP
→ Architect/Tech Lead review
```

Coder must not silently raise caps.

---

# 98. PRODUCT LATENCY EXPECTATION

The architectural hard correctness limit is:

```text
5s
```

Production acceptance additionally records observed:

```text
p50
p95
max
```

for NI-04 endpoint under the accepted bounded test set.

No new product SLA is claimed by architecture beyond the 5s hard ceiling.

If normal production requests repeatedly approach the hard ceiling:

```text
production activation = HOLD
```

until reviewed.

---

# 99. PRIVACY

Permanent V1 rule:

```text
METADATA OVER PAYLOAD
+
DERIVED SUMMARY OVER RAW METADATA
```

Raw sensitive recognition values are permitted only inside the protected
recognition process.

Admin API/HTML/JS MUST NOT expose:

```text
DNS query names

DNS answers

SNI

remote IP

remote port

edge_id

source_observation_ref

attribution binding ID

client MAC introduced by NI-04

knowledge source locator

raw rule pattern
```

Default Device Card receives only derived product-safe results.

---

# 100. APPLICATION LOGGING

NI-04 application logs/metrics/telemetry MUST NOT contain:

```text
device_id as a metric/log field

MAC

DNS name

SNI

remote IP

port

edge_id

source_observation_ref

raw rule match value

Service history list for one Device
```

Allowed bounded application diagnostics:

```text
request_id

Site ID

safe failure category

duration bucket

edge-row-count bucket

source-ref-count bucket

result-count bucket

ruleset version

taxonomy version

HTTP status class
```

Do not log full request path from NI-04 application code.

Existing reverse-proxy URI logging follows the already accepted NI-03/Admin
infrastructure boundary and is not redefined here.

---

# 101. NO NEW REVERSE-PROXY LOGGING

NI-04 MUST NOT add:

```text
$request_uri logging

query-string logging

request-body logging

response-body logging

Authorization header logging

Cookie logging
```

No Nginx configuration change is required merely for NI-04.

---

# 102. MULTI-SITE

Every NI-04 operation is Site-scoped.

Permanent:

```text
same device_id on Site A
does not authorize Site B evidence

same hostname observed on different Sites
produces independent Device summaries

DNS correlation never crosses Site

Device correlation never crosses Site

no default-Site fallback

no cross-Site service aggregation in V1
```

Taxonomy/rules are platform-global knowledge artifacts.

User traffic/evidence remains Site-scoped.

---

# 103. FAILURE ISOLATION

Failure of NI-04 MUST NOT:

```text
stop Portal

stop CAPPORT

change guest Authorization

query or mutate Omada

mutate Visitor Registry

mutate NI-01

mutate NI-02A

mutate NI-02B

change NI-03 output

change Device Fingerprint

restart Fingerprint Sensor

restart Suricata

modify RSPAN/SPAN

modify Cisco

modify Omada Controller
```

NI-04 has no authority over those domains.

---

# 104. PROTECTED COMPONENTS

NI-04 architecture explicitly protects:

```text
Guest Portal routes and semantics

CAPPORT

AuthSession / AuthWorker

Omada provider/control

Visitor Registry identity

Visit Lifecycle

Observation Foundation

Current State

existing Traffic products

Device Fingerprint

fingerprint-sensor.service

fingerprint-suricata.service

Suricata production capture config

NI-01 writer/schema/retention semantics

NI-02A attribution semantics

NI-02B writer/schema/edge semantics

NI-03 Protocol Intelligence semantics/API/UI

Admin authentication/session/security
```

Read-only additive interfaces do not authorize modification of these semantics.

---

# 105. ALLOWED CONCEPTUAL IMPLEMENTATION BOUNDARIES

After the relevant Tech Lead/Owner authorizations, NI-04 work may conceptually
touch:

```text
app/network_metadata/
    read-only protected recognition read boundary only

app/network_metadata_projection/
    read-only protected recognition snapshot only

app/network_service_recognition/
    new recognition semantics, DTOs, rule/taxonomy loader, read service

app/admin_web/
    additive query-service composition
    additive read-only API route
    additive Device Card section
    additive dedicated static JS/CSS hooks as required

app/config.py / app/settings.py
    NI-04 feature flag via existing Admin config pipeline only

deployment/systemd artifacts
    main-process read-only NI-01 configuration handoff

tests/
docs/
```

No exact file allowlist is granted here.

Tech Lead owns the implementation-task file allowlist after source review.

---

# 106. NO RAW SOURCE FALLBACK

If the protected NI-01 recognition read fails:

```text
do not read raw EVE

do not read rotated EVE

do not parse Loki

do not query Grafana

do not inspect packet capture

do not use Suricata socket
```

Return safe unavailable semantics.

---

# 107. NO NI-03 FALLBACK

If sensitive recognition evidence is unavailable:

```text
DNS/TLS/QUIC labels from NI-03
```

must NOT be transformed into guessed services.

NI-03 remains visible independently.

---

# 108. NO EXTERNAL ONLINE DEPENDENCY

NI-04 V1 MUST NOT require at request time:

```text
ASN API

WHOIS API

GeoIP cloud API

vendor recognition API

public DNS API

search engine

LLM

third-party service catalog
```

Static reviewed provenance may refer to external public sources in the admitted
knowledge manifest, but execution is offline/local.

---

# 109. ACCEPTANCE — RECOGNITION DIRECT SNI

PASS requires deterministic fixtures proving:

```text
unique active TLS SNI exact Service rule
→ service_resolved

unique active TLS SNI suffix Service rule
→ service_resolved

unique active QUIC SNI Service rule
→ service_resolved

unrelated hostname
→ no Service result

suffix boundary notexample.com vs example.com
→ no false match

expired rule
→ no Service result
→ recognition limited
```

FAIL if any service is guessed from IP/port/protocol alone.

---

# 110. ACCEPTANCE — MULTI-SIGNAL DNS

PASS requires:

```text
service-specific DNS query
+
A/AAAA answer
+
same Site+Device
+
subsequent outbound external peer-IP match <=300s
→ multi_signal_supported Service

same evidence at exactly +300s
→ included

same peer match >300s
→ not correlated

DNS query only
→ no Service

DNS query + answer but no peer connection
→ no Service

peer IP match but DNS query belongs to other Device
→ no Service

peer IP match on other Site
→ no Service
```

---

# 111. ACCEPTANCE — SHARED CDN / CLOUD

Required:

```text
shared IP only
→ no Service

organization-only shared hostname
→ organization_resolved only

shared cloud organization
→ no arbitrary child Service

specific direct Service SNI on same connection
→ Service may resolve
```

Any:

```text
Cloudflare IP → specific website
```

style inference is FAIL.

---

# 112. ACCEPTANCE — MULTIPLE SERVICES SAME ORGANIZATION

Fixture:

```text
Service A
Service B
same organization
```

Required:

```text
organization evidence only
→ no Service

Service A-specific rule
→ Service A

Service B-specific rule
→ Service B

equal-strength conflicting A+B rules
→ ambiguous
→ no Service
```

---

# 113. ACCEPTANCE — NO SNI / ECH-LIKE LIMITATION

Required:

```text
TLS/QUIC with sni_presence_state not observed
→ no direct Service

no other evidence
→ no guessed Service
→ recognition limited where appropriate
```

The UI/API must not claim:

```text
ECH detected
```

unless a future source contract explicitly admits it.

---

# 114. ACCEPTANCE — DNS CACHE

Required:

```text
no DNS event in bounded correlation interval
+
no direct SNI
→ no Service
```

No search of old DNS history solely to force a match.

---

# 115. ACCEPTANCE — VPN

Required:

```text
outer VPN/tunnel-like endpoint evidence
→ no inference of inner Service

IP ownership of VPN endpoint
→ no inner Service
```

If a directly admitted outer service hostname exists, only that exact outer
service may be resolved.

---

# 116. ACCEPTANCE — LOCAL/PUBLIC DNS RESOLVER

Required:

```text
local resolver query
+
valid answer
+
same-Device external connection match
→ eligible correlation

public resolver query
+
valid answer
+
same-Device external connection match
→ eligible correlation

resolver IP/provider alone
→ no queried Service
```

---

# 117. ACCEPTANCE — IP REASSIGNMENT

Required controlled fixtures:

```text
IP X belongs to Device A at event time
then later Device B
```

NI-04 must use the NI-02B Device-relative edge and show historical Service
evidence only for Device A.

No current-IP join.

No cross-MAC merge.

---

# 118. ACCEPTANCE — PRE-REGISTRY / LATE BINDING

Required:

```text
retained NI-02B Site+MAC edge
+
binding not_yet_registry_resolved
→ identity_pending
→ no Service evidence

later authoritative binding to Device
→ same still-retained edge becomes evaluable on next read
```

No NI-04 write/replay required.

---

# 119. ACCEPTANCE — LATE ATTRIBUTION

Required:

```text
source observation initially has no Device edge
because NI-02B attribution pending

later NI-02B retry materializes valid edge

event_at still inside 24h
→ next NI-04 read can recognize it
```

No event is recognized before NI-02B authority exists.

---

# 120. ACCEPTANCE — DEGRADED / AVAILABLE

Required state matrix:

```text
runtime=usable
+ recognized Service
→ 200 / availability usable

runtime=attribution_unavailable
+ committed recognized Service
→ 200 / availability degraded
→ source usable
→ attribution degraded
→ fresh capped to recent

runtime=source_unavailable
+ committed recognized Service
+ stores readable
→ 200 / availability degraded
→ source unavailable
→ freshness stale

runtime=capacity_halted
+ committed recognized Service
→ 200 / degraded

runtime=blocked_conflict
+ committed recognized Service
→ 200 / degraded

projection DB unreadable
→ 503 source_unavailable

NI-01 DB unreadable
→ 503 source_unavailable

ruleset invalid
→ 503 recognition_unavailable
```

---

# 121. ACCEPTANCE — EMPTY RESULTS

Required:

```text
authoritative identity
+ source usable
+ attribution usable
+ recognition usable
+ no supported Service
→ no_supported_result_observed_with_sufficient_coverage
```

UI wording must include:

```text
No supported services recognized
```

and must not imply no activity.

If source degraded/unavailable:

```text
insufficient_source_coverage
```

If attribution degraded:

```text
insufficient_attribution
```

If recognition limited:

```text
recognition_limited
```

---

# 122. ACCEPTANCE — RULE CONFLICT

Required:

```text
two same-strength/specificity different Service matches
→ ambiguous
→ no Service row

direct SNI Service A
+
weaker DNS-correlated Service B
→ Service A

service match
+
unrelated weaker infrastructure organization context
→ Service remains
```

No confidence weighting.

---

# 123. ACCEPTANCE — MISSING RULESET

Required:

```text
feature true
+
taxonomy/ruleset/knowledge artifact missing
→ main application starts
→ NI-03 works
→ NI-04 = 503 recognition_unavailable
```

No empty "No services" response.

---

# 124. ACCEPTANCE — SOURCE PROVENANCE MISMATCH

Any mismatch between NI-02B edge provenance and NI-01 source evidence:

```text
site
observation ID
event time
family
generation
capture source
network scope
binding digest
```

must produce:

```text
503 source_unavailable
```

for that request.

No partial service output.

---

# 125. ACCEPTANCE — MULTI-SITE

Required:

```text
Site A Device request
→ only Site A edges/source records

same device_id on Site B
→ not merged

wrong Site
→ existing Admin Device semantics:
   403 or 404 as appropriate

DNS correlation across Sites
→ impossible / rejected
```

---

# 126. ACCEPTANCE — API

Required:

```text
GET exact endpoint
→ 200 versioned DTO

any query parameter
→ 400

invalid Site/device
→ 400

unauthenticated
→ 401

Site/capability denied
→ 403

Device absent
→ 404

feature off
→ 404

concurrency occupied
→ 429 + Retry-After:1

deadline
→ 503 query_deadline

source store/config unavailable
→ 503 source_unavailable

recognition artifacts unavailable
→ 503 recognition_unavailable

response >16KiB
→ 503 response_too_large

Cache-Control=no-store
Pragma=no-cache
```

---

# 127. ACCEPTANCE — UI

Required:

```text
NI-03 section unchanged

Service Intelligence absent when feature OFF

Service Intelligence present when feature ON + authorized

Recent Services rendered

Service Categories rendered

Last Service Observation rendered

Freshness rendered

Recognition coverage rendered

Source coverage rendered

Attribution coverage rendered

Last evaluated rendered

manual refresh works

120s bounded automatic refresh works

hidden tab stops NI-04 polling

no overlapping NI-04 requests

manual clicks coalesce

NI-03 failure does not automatically fail NI-04 request

NI-04 failure does not stop NI-03
```

---

# 128. ACCEPTANCE — PRIVACY

Prove NI-04 public API, HTML, JS, application logs and metrics do NOT expose:

```text
DNS name

DNS answer

SNI

remote IP

remote port

MAC introduced by NI-04

edge_id

source_observation_ref

attribution binding

raw rule hostname pattern

raw knowledge locator
```

Prove no:

```text
localStorage
sessionStorage
browser raw metadata cache
```

for recognition evidence.

---

# 129. ACCEPTANCE — PERFORMANCE / WRITER COEXISTENCE

Required lab gate with active writers:

```text
1 NI-04 read
+
normal NI-01 writer
+
normal NI-02B writer
```

must not cause:

```text
writer failure

checkpoint corruption

false capacity halt

unbounded WAL growth attributable to held NI-04 reader

Portal/Auth/CAPPORT failure
```

Two simultaneous NI-04 evaluations must never occur because the process-local
gate is 1.

---

# 130. ACCEPTANCE — HARD CAPS

Required:

```text
5000 matching edge facts
→ evaluable if all other caps pass

5001
→ no partial output
→ 503 source_unavailable

256 refs in one NI-01 batch
→ allowed

257 refs passed to one NI-01 batch method
→ validation failure

25000 scalar recognition values
→ allowed

25001
→ no partial output
→ 503 source_unavailable

2048 rules
→ allowed

2049
→ artifact invalid
→ NI-04 unavailable
```

---

# 131. ACCEPTANCE — RESTART / CONFIGURATION HANDOFF

NI-04A/production integration must prove:

```text
captive-portal.service obtains NI-01 config through
/etc/captive-portal/network-metadata.env

existing network_metadata_config_from_env() remains canonical

no second NI-01 DB-path alias exists

NI-01 disabled + old DB exists
→ old DB not opened by NI-04

missing optional NI-01 env
→ core portal starts
→ NI-04 unavailable

invalid NI-01 config
→ core portal starts
→ NI-04 unavailable

NI-02B existing config handoff remains unchanged

no request-time getenv

no request-time EnvironmentFile parse

no request-time systemctl
```

---

# 132. ACCEPTANCE — FAILURE ISOLATION

Inject failures in:

```text
NI-01 read
NI-02B read
taxonomy loader
rules loader
knowledge manifest
recognition evaluation
row cap
deadline
browser timeout
```

Prove no regression to:

```text
Portal
CAPPORT
Authorization
Visitor Registry
NI-01 writer
NI-02A
NI-02B writer
NI-03 API/UI
Device Fingerprint
Fingerprint Sensor
Suricata
Omada
```

---

# 133. INITIAL KNOWLEDGE ADMISSION GATE — EXACT

NI-04A cannot be accepted with merely a schema.

It must deliver an exact first bundle containing:

```text
RecognitionTaxonomyContractV1

InitialRecognitionKnowledgeManifestV1

RecognitionRuleSetV1
```

For each active service rule, acceptance evidence must establish:

```text
target Service identity

target Organization

target Category

exact hostname rule

why hostname is Service-specific enough for the selected rule kind

knowledge provenance

review date/due date

positive fixture

negative near-match fixture

shared-infrastructure false-positive fixture where applicable
```

The request examples are candidates only.

Any candidate without sufficient proof:

```text
NOT ADMITTED
```

This is safe and expected.

---

# 134. NI-04A PASS GATE

`TASK-DTI-NI-04A` is PASS only if ALL:

```text
1. NI-02B protected recognition snapshot exists and is read-only.

2. NI-01 protected recognition evidence read exists and is read-only.

3. No NI-01 or NI-02B writer/schema semantic change was introduced.

4. Exact cross-store provenance checks pass.

5. Sensitive fields never appear in ordinary NI-01 read API.

6. Sensitive fields never appear in Admin API/UI/logs.

7. Main runtime canonical NI-01 configuration handoff is frozen and tested.

8. At least one real Service is admitted through a reviewed local knowledge
   bundle.

9. Rule conflicts/near-match negatives are tested.

10. Hard read/cardinality bounds are proven.

11. NI-03 remains unchanged.

12. Protected-core regressions = 0.
```

Only after this gate:

```text
MAIN NI-04 CODER HOLD
→ may be lifted by Owner/Tech Lead
```

for the product/read-model/UI implementation task.

---

# 135. PRODUCTION ACTIVATION SEQUENCE — FUTURE

This architecture does not authorize activation.

The later production TASK should stage:

```text
1. re-pin accepted HEAD/TREE and production baseline;

2. verify protected services and current resource baseline;

3. install source with NI-04 feature OFF;

4. install NI-01 read EnvironmentFile drop-in while feature remains OFF;

5. daemon-reload;

6. restart captive-portal.service only if authorized;

7. prove Portal/CAPPORT/Admin/NI-03 baseline;

8. prove canonical NI-01/NI-02B read configuration without dumping secrets;

9. enable WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED=true;

10. restart captive-portal.service;

11. verify API/UI positive recognition on an Owner-controlled test case;

12. verify conservative negative/shared-CDN/no-SNI cases;

13. verify degraded attribution case;

14. verify CPU/RAM/SQLite writer coexistence;

15. verify application/privacy logs;

16. verify external HTTPS Device Card;

17. record PASS.
```

Do not restart:

```text
network-metadata.service

network-metadata-projection.service

fingerprint-sensor.service

fingerprint-suricata.service
```

unless a separately authorized test explicitly requires it.

---

# 136. FAST PRODUCT ROLLBACK

Exact primary rollback:

```text
WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED=false

restart captive-portal.service

verify:
Portal
CAPPORT
Admin
NI-03
```

No NI-01 DB restore.

No NI-02B DB restore.

No traffic data deletion.

No Suricata rollback.

If full deployment handoff rollback is required:

```text
feature OFF

remove only:
15-network-metadata-read.conf

daemon-reload

restart captive-portal.service

verify baseline

leave NI-01 and NI-02B auxiliary services/stores untouched
```

---

# 137. REPRODUCIBILITY CONTRACT

Within retained evidence availability, an NI-04 result is reproducible from:

```text
exact evaluated_at_utc

exact Site+Device identity

exact NI-02B edge facts/provenance

exact NI-01 source evidence

exact taxonomy ID/version/digest

exact ruleset ID/version/digest

exact knowledge manifest version
```

V1 does NOT promise reconstruction after:

```text
NI-01 sensitive retention expiry
```

because it deliberately stores no separate Service history.

This limitation must be visible in technical documentation, not hidden.

---

# 138. FUTURE NI-05 BOUNDARY

NI-05 MUST NOT create:

```text
second hostname classifier

second DNS/SNI ruleset

second service→organization mapping
```

NI-05 may consume NI-04's internal organization-resolution output using the same:

```text
RecognitionTaxonomyContractV1
RecognitionRuleSetV1
ServiceObservationV1 semantics
```

It may add organization aggregation/presentation under a future contract.

NI-04 remains the single recognition semantic owner.

---

# 139. FUTURE PERSISTENCE BOUNDARY

If future requirements need:

```text
7-day/30-day service history
historical service timeline
rule-version audit after NI-01 sensitive expiry
analytics across service history
```

that is NOT silently added to NI-04 V1.

Required separate architecture must define:

```text
derived-store owner

schema

immutable/recomputed semantics

rule-version lineage

rebuild dependency closure

retention

privacy

capacity

migration

late-binding/replay

deletion
```

---

# 140. EXPLICIT NON-GOALS

NI-04 V1 does NOT implement:

```text
traffic bytes by service

traffic percentage by service

dominant service

time spent in application

application foreground/background state

website browsing history

DNS history UI

SNI history UI

remote-IP history UI

ASN product view

GeoIP

behavior profile

anomaly detection

security scoring

automatic blocking

Omada policy action

authorization decision

CAPPORT admission

Device Fingerprint changes

cross-MAC identity

IPv6 Device identity redesign

persistent service history

customer-facing reports
```

---

# 141. ARCHITECTURAL ANSWERS TO THE TECH LEAD'S CRITICAL QUESTIONS

## 1. Where does NI-04 obtain recognition features?

```text
Device identity / event authority:
NI-02B

DNS/SNI sensitive feature values:
NI-01 protected recognition-only read
```

## 2. How are DNS/SNI facts linked to a Device-relative event?

Exactly through:

```text
NI-02B.source_observation_ref
==
NI-01.observation_id
```

plus full provenance equality.

## 3. Is a separate protected NI-01 read boundary needed?

```text
YES
MANDATORY
```

## 4. Expand existing projection or create another?

```text
NO NI-02B storage/schema expansion

ADD read-only recognition snapshot only

NO second projection DB

NO NI-04 traffic-data DB in V1
```

## 5. How are NI-02B and NI-03 preserved?

```text
No writer/schema semantic change
No NI-03 DTO/API/UI semantic change
Read-only additive boundaries only
Failure isolated
```

## 6. Can full NI-04 V1 be delivered on current sources?

```text
YES at acquisition/schema level

NO on current consumer contract alone

MANDATORY NI-04A protected bridge + knowledge admission first
```

---

# 142. DECISION MATRIX — REQUESTED SPECIAL CASES

| Case | Service recognition allowed? | Required evidence | Insufficient-evidence result |
|---|---|---|---|
| Common CDN/cloud IP | No, by IP alone | Service-specific SNI or admitted DNS+connection rule | no Service / possible org context |
| Multiple Services same org | Not by org alone | Service-specific rule | organization only / unknown |
| DNS cache | Only if direct SNI or qualifying recent DNS correlation exists | direct SNI or DNS within 300s + answer + peer match | no Service |
| DNS query without connection | No | later qualifying connection required | insufficient |
| Missing SNI | Maybe via DNS correlation | qualifying DNS+connection | limited/unknown |
| ECH-like unobservable hostname | No positive ECH claim | other admitted evidence only | limited/unknown |
| VPN/tunnel | No inner-service inference | direct outer-service evidence only | unknown |
| Local DNS resolver | Yes, correlation possible | query+answer+later external peer match | insufficient |
| Public DNS resolver | Yes, correlation possible | query+answer+later external peer match | insufficient |
| Device IP changed | Yes | NI-02B event-time Device edge | no current-IP inference |
| Event before Registry binding | Not until authoritative binding | later NI-02B authoritative binding | identity_pending |
| Late event / retry | Yes if still in 24h | later valid NI-02B edge + retained NI-01 evidence | otherwise absent/limited |

---

# 143. FROZEN CONSTANT REGISTER

```text
SUMMARY_WINDOW_SECONDS =
86400

RECENT_WINDOW_SECONDS =
3600

FRESH_SECONDS =
300

DNS_CONNECTION_CORRELATION_SECONDS =
300

SERVICE_RECOGNITION_MAX_EDGE_ROWS =
5000

NI01_RECOGNITION_BATCH_REFS =
256

SERVICE_RECOGNITION_MAX_SIGNAL_VALUES =
25000

SERVICE_RECOGNITION_MAX_INTERNAL_OBSERVATIONS =
5000

MAX_RECENT_SERVICES =
12

MAX_SERVICE_CATEGORIES =
10

MAX_ORGANIZATIONS =
256

MAX_SERVICES =
512

MAX_RULES =
2048

MAX_KNOWLEDGE_SOURCES =
4096

MAX_RULE_HOSTNAME_PATTERNS =
2048

SERVER_DEADLINE_SECONDS =
5

SQLITE_BUSY_TIMEOUT_MS =
500

NI04_MAX_CONCURRENT_READS =
1

CLIENT_TIMEOUT_SECONDS =
10

CLIENT_REFRESH_SECONDS =
120

CLIENT_BACKOFF_SECONDS =
120 / 300 / 600

CLIENT_LAST_GOOD_MAX_SECONDS =
900

MAX_API_RESPONSE_BYTES =
16384

KNOWLEDGE_MAX_REVIEW_AGE_DAYS =
365
```

Coder may not change these values without architecture return.

---

# 144. FINAL INVARIANTS

```text
NI04-I01
NI-04 never redoes Device attribution.

NI04-I02
NI-04 never recognizes a Service from NI-03 protocol labels alone.

NI04-I03
NI-02B source_observation_ref is the bridge to NI-01 evidence.

NI04-I04
Raw DNS/SNI stays behind a protected in-process boundary.

NI04-I05
No raw DNS/SNI enters Admin API/UI/logs.

NI04-I06
No Service is inferred from IP alone in V1.

NI04-I07
Organization != Service != Category.

NI04-I08
DNS query alone is insufficient.

NI04-I09
DNS service correlation requires answer + same-Device connection within 300s.

NI04-I10
Direct unique Service SNI is stronger than DNS correlation.

NI04-I11
Equal-strength Service conflict is ambiguous, never averaged.

NI04-I12
No arbitrary confidence percentage exists.

NI04-I13
Current degraded attribution does not invalidate already committed
authoritative evidence.

NI04-I14
Missing/incomplete coverage never becomes "No services used."

NI04-I15
Service results are ephemeral in V1; no new user-traffic history store.

NI04-I16
Rule/taxonomy provenance is versioned and local at runtime.

NI04-I17
NI-05 consumes NI-04 recognition ownership; it does not reclassify.

NI04-I18
Feature failure is isolated from Portal/Auth/CAPPORT/NI-03.

NI04-I19
Site is mandatory on every evidence and product boundary.

NI04-I20
Traffic-accounting lane remains parked and is not a dependency.
```

---

# 145. MANDATORY PREREQUISITE REGISTER

Before main NI-04 implementation:

```text
PREREQUISITE =
TASK-DTI-NI-04A
RECOGNITION EVIDENCE BRIDGE + INITIAL KNOWLEDGE ADMISSION

REQUIRED OUTPUTS =
1. NI-02B RecognitionProjectionSnapshotV1 read boundary
2. NI-01 RecognitionSourceEvidenceV1 protected read boundary
3. main-process NI-01 canonical configuration handoff
4. InitialRecognitionKnowledgeManifestV1
5. RecognitionTaxonomyContractV1 concrete v1 bundle
6. RecognitionRuleSetV1 concrete first bundle
7. positive + negative + ambiguity evidence
8. privacy proof
9. bounded reader/writer coexistence proof
10. no NI-03 semantic regression

MAIN NI-04 CODER =
HOLD UNTIL NI-04A PASS
```

No additional source acquisition research is required to establish that the
current NI-01 store contains the necessary signal classes.

Concrete Service-domain knowledge admission is still required.

---

# 146. FINAL ARCHITECTURE VERDICT

```text
TASK =
TASK-DTI-NI-04

ARCHITECTURE CONTRACT =
v1

REPOSITORY BASELINE =
e8061de9fbd6da8be5cd269779070a4db4d59d64

TREE =
d5503fe1f2b5774bbe55cb2d34dba63246f56f6f

CURRENT SOURCE DATA SUFFICIENT =
YES

CURRENT SAFE READ CONTRACT SUFFICIENT =
NO

NEW ACQUISITION SOURCE REQUIRED =
NO

NI-01 SCHEMA CHANGE REQUIRED =
NO

NI-02B STORAGE SCHEMA CHANGE REQUIRED =
NO

NI-03 SEMANTIC CHANGE REQUIRED =
NO

NEW NI-04 USER-TRAFFIC DB =
NO

SERVICE IP-ONLY INFERENCE =
FORBIDDEN IN V1

TRAFFIC METER DEPENDENCY =
NO / PARKED

EXTERNAL RUNTIME LOOKUP =
NO

OPEN ARCHITECTURE P0 =
0

OPEN ARCHITECTURE P1 =
0

ARCHITECTURE SEMANTICS =
PASS / COMPLETE

MANDATORY PREREQUISITE =
TASK-DTI-NI-04A

MAIN NI-04 CODER =
HOLD

IMPLEMENTATION AUTHORIZATION =
NO

PRODUCTION CHANGE =
NO

READY FOR TECH LEAD IMPLEMENTATION TASK =
YES — NI-04A ONLY

FINAL REQUEST STATUS =
ARCHITECTURE HOLD / PREREQUISITE REQUIRED
```

---

# 147. NEXT GOVERNANCE STEP

```text
Architect
→ this complete NI-04 v1 contract

Technical Lead
→ independent architecture review

if architecture review PASS:
Technical Lead
→ exact TASK-DTI-NI-04A implementation/admission contract

Owner
→ explicit authorization before Coder action

NI-04A
→ implementation + review + lab/privacy/admission acceptance

only after NI-04A PASS:
Technical Lead
→ exact main TASK-DTI-NI-04 implementation contract

Owner
→ explicit Coder authorization

merge
→ separate decision

production activation
→ separate decision
```

No implementation work is authorized by this architecture document itself.
