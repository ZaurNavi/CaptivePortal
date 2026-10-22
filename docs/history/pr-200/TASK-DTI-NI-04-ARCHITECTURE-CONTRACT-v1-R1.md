# TASK-DTI-NI-04 — SERVICE RECOGNITION
## ARCHITECTURE CONTRACT v1-R1
### TECH LEAD R1 — BOUNDED REPAIR ADDENDUM
### FOR TECH LEAD RE-REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Parent artifact:** `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md`  
**Tech Lead return:** `TASK-DTI-NI-04-TECHLEAD-ARCH-REVIEW-R1`  
**Pinned baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Pinned TREE:** `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`  
**R1 scope:** `P1-01 .. P1-05 only`  
**Implementation authorization:** `NO`  
**Coder:** `HOLD`  
**Production change:** `NO`

---

# 0. PRECEDENCE / NON-REOPEN RULE

Этот документ является нормативным addendum к:

```text
TASK-DTI-NI-04
ARCHITECTURE CONTRACT v1
```

При конфликте:

```text
v1-R1
>
v1
```

R1 изменяет только bounded clauses, необходимые для закрытия Tech Lead P1-01..P1-05.
Все остальные решения v1 сохраняются без redesign.

Сохраняются, в частности:

```text
NI-04A before main NI-04

NI-01 = source owner for DNS/TLS/QUIC normalized metadata

NI-02B = authoritative Device-relative/event-time projection owner

NI-03 API/DTO/UI semantics unchanged

no new traffic meter
no new packet parser family
no new external runtime lookup
no Admin/browser direct SQLite access
no payload/PCAP product storage
no IP-only exact Service inference
Organization != Service != Service Category
Site mandatory
metadata over payload
failure isolation
no new NI-04 user-traffic history DB in V1
main NI-04 product Coder HOLD until prerequisite acceptance
```

R1 does NOT authorize:

```text
source edit
commit
push
PR
merge
deploy
systemd mutation
production action
```

---

# 1. TECH LEAD R1 DISPOSITION SUMMARY

Tech Lead accepted the semantic direction and returned five bounded P1 issues:

```text
P1-01  missing approved initial service-rule knowledge / admission owner
P1-02  incomplete manifest + canonical version/digest contract
P1-03  DNS→connection proof too weak for current NI-01 schema
P1-04  static bundle collision vs runtime ambiguity boundary undefined
P1-05  NI-04A code/validation boundary vs main NI-04 ownership undefined
```

R1 resolves them as follows:

```text
P1-01 = PASS AS ARCHITECTURE REPAIR
        separate non-Coder knowledge-admission prerequisite created

P1-02 = PASS
        complete manifest schema + canonical bytes + digest rules frozen

P1-03 = PASS
        DNS-connected recognition remains RESERVED / NOT ACTIVE IN V1
        direct SNI is the only positive Service/Organization recognition signal in V1

P1-04 = PASS
        exact invalid static collision set + explicit runtime ambiguity group frozen

P1-05 = PASS
        exact NI-04K / NI-04A-CODE / main NI-04 ownership sequence frozen
        one reusable production matcher kernel, no test-only duplicate engine
```

Architectural open findings after this R1:

```text
OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0
```

Execution remains held because real recognition knowledge must be independently admitted before bundle-dependent code work.

---

# 2. R1-01 — INITIAL RECOGNITION KNOWLEDGE ADMISSION
## Supersedes v1 §§17–18, 133–134, 145–147 where they imply that NI-04A code and knowledge admission may be one undifferentiated task

## 2.1 Selected repair

R1 selects Tech Lead option **B**.

No real hostname/service rule is fabricated by Architect.

A separate mandatory non-Coder gate is inserted before bundle-dependent NI-04A implementation:

```text
TASK-DTI-NI-04K
INITIAL RECOGNITION KNOWLEDGE ADMISSION
```

This is a research/admission task, not a production implementation task.

Exact sequence becomes:

```text
Architect R1 accepted
        ↓
TASK-DTI-NI-04K
Initial Recognition Knowledge Admission
        ↓
Tech Lead independent admission review
        ↓
Owner acceptance of admitted bundle use
        ↓
TASK-DTI-NI-04A-CODE
Evidence Bridge + Artifact Runtime + Pure Matcher Kernel
        ↓
NI-04A technical acceptance
        ↓
MAIN TASK-DTI-NI-04
Read-time orchestration + safe product API/UI
```

No Coder may skip NI-04K.

---

## 2.2 Roles and admission authority

Evidence collection may be performed by:

```text
Research & QA
or
an explicitly designated Technical Researcher
```

Evidence collector may:

```text
locate first-party public documentation
capture Owner-controlled traces
prepare source references
prepare positive/negative fixtures
report ambiguity
```

Evidence collector may NOT unilaterally admit a production Service rule.

Semantic admission authority is:

```text
Architect
→ evaluates whether the evidence satisfies the frozen recognition semantics

Tech Lead
→ independently verifies provenance, false-positive controls and bundle integrity

Owner
→ authorizes the accepted knowledge bundle for implementation/product use
```

Coder authority is exactly:

```text
NO authority to choose initial Service
NO authority to choose Organization
NO authority to choose Category
NO authority to choose hostname pattern
NO authority to decide whether a hostname is service-specific
NO authority to weaken negative fixtures
NO authority to invent provenance
```

Coder consumes only an already admitted exact bundle.

---

## 2.3 TASK-DTI-NI-04K mandatory outputs

NI-04K MUST produce one immutable candidate bundle containing:

```text
RecognitionTaxonomyContractV1
InitialRecognitionKnowledgeManifestV1
RecognitionRuleSetV1
```

and an evidence pack for every active Service rule.

Minimum accepted production knowledge:

```text
>= 1 real Service
>= 1 real active direct-SNI Service rule
```

Because R1-03 disables DNS-connected positive recognition in V1, NI-04K acceptance MUST include at least one:

```text
service_sni_exact
or
service_sni_suffix
```

rule whose hostname specificity is independently proven.

The examples from the original request remain candidates only:

```text
YouTube
WhatsApp
Telegram
Netflix
Spotify
```

None is admitted merely because it was named in the request.

---

## 2.4 Per-rule evidence pack

For every active Service rule NI-04K MUST provide:

```text
rule_id
service_id
organization_id
service_category_id
canonical display names
rule_kind
canonical hostname_pattern
knowledge_refs

positive evidence reference(s)
negative near-match fixture(s)
shared-CDN/cloud negative fixture where applicable
multi-service same-organization negative fixture where applicable

reviewed_at_utc
review_due_at_utc
```

Evidence must establish the exact claim appropriate to the rule kind.

For a direct SNI Service rule the admission claim is:

```text
this hostname pattern is sufficiently Service-specific
that an authoritative Device-relative outbound TLS/QUIC SNI match
supports this exact Service identity
```

Forbidden admission evidence:

```text
LLM assertion alone
search-result snippet alone
unattributed domain list
shared hosting ownership alone
IP ownership alone
"commonly known" domain claim
Coder guess
```

---

## 2.5 NI-04K PASS

NI-04K PASS requires ALL:

```text
1. >=1 real active Service exists.
2. >=1 active direct-SNI Service rule exists.
3. Every active rule has non-dangling knowledge_refs.
4. Every referenced source has accepted provenance.
5. Positive fixture matches exactly as intended.
6. Near-match fixture does not resolve the Service.
7. Shared infrastructure negative fixture does not resolve the Service.
8. Taxonomy Organization/Service/Category relation is exact.
9. Artifact canonicalization and digests pass R1-02.
10. Static collision admission passes R1-04.
11. No active DNS-connected rule exists in V1.
12. Tech Lead independent review = PASS.
13. Owner permits the admitted bundle to be consumed by implementation.
```

Any one failure:

```text
TASK-DTI-NI-04K = HOLD
TASK-DTI-NI-04A-CODE = HOLD
MAIN NI-04 = HOLD
```

No production code is written to compensate for missing knowledge admission.

---

## 2.6 P1-01 disposition

```text
P1-01 = PASS

REAL INITIAL BUNDLE =
NOT FABRICATED BY ARCHITECT

MANDATORY PRE-CODER GATE =
TASK-DTI-NI-04K

READY_FOR_NI04K_RESEARCH_ADMISSION_TASK = YES

READY_FOR_NI04A_CODER_TASK = NO
until NI-04K PASS + explicit Owner authorization
```

---

# 3. R1-02 — COMPLETE MANIFEST / VERSION / DIGEST CONTRACT
## Supersedes v1 §§16, 18–20, 34, 67–69, 133 wherever canonical identity was incomplete

## 3.1 Artifact set

The recognition knowledge bundle consists of exactly three independently hashed artifacts:

```text
RecognitionTaxonomyContractV1
InitialRecognitionKnowledgeManifestV1
RecognitionRuleSetV1
```

Each artifact has:

```text
one stable artifact ID
one positive integer version
one SHA-256 digest over exact canonical bytes
```

No mutable sidecar metadata may alter runtime semantics without changing the appropriate artifact version/digest.

---

## 3.2 InitialRecognitionKnowledgeManifestV1 — exact top-level schema

Exact fields:

```text
schema_version:
    integer = 1

knowledge_manifest_id:
    exact string =
    "captivportal.network-intelligence.recognition-knowledge"

knowledge_manifest_version:
    positive integer

knowledge_manifest_digest_sha256:
    lowercase ASCII hex, exactly 64 chars

reviewed_at_utc:
    canonical UTC timestamp

review_due_at_utc:
    canonical UTC timestamp

sources:
    tuple[RecognitionKnowledgeSourceV1, ...]
```

No other top-level fields are admitted in V1.

Hard cardinality:

```text
1 <= len(sources) <= 4096
```

Manifest review interval:

```text
reviewed_at_utc < review_due_at_utc
review_due_at_utc - reviewed_at_utc <= 365 days
```

---

## 3.3 RecognitionKnowledgeSourceV1 — exact schema and validation

Exact fields remain:

```text
knowledge_ref
source_class
publisher_or_owner
source_locator
claim_summary
reviewed_at_utc
review_due_at_utc
```

`knowledge_ref` exact syntax:

```text
^knowledge\.[a-z0-9][a-z0-9._-]{1,94}[a-z0-9]$
```

`source_class` closed enum:

```text
first_party_public
controlled_owner_trace
authoritative_registry
reviewed_internal_research
```

Text bounds:

```text
publisher_or_owner: 1..128 visible characters
source_locator:      1..2048 characters
claim_summary:       1..512 visible characters
```

For all three:

```text
no leading/trailing whitespace
no U+0000..U+001F control characters
no U+007F
Unicode NFC required
```

Source review window:

```text
source.reviewed_at_utc < source.review_due_at_utc
source.review_due_at_utc - source.reviewed_at_utc <= 365 days
```

At manifest admission time:

```text
source.reviewed_at_utc <= manifest.reviewed_at_utc
manifest.reviewed_at_utc < source.review_due_at_utc
```

A source already expired when the manifest is admitted makes the manifest invalid.

---

## 3.4 Source ordering and uniqueness

`sources` is semantically a set but canonically represented as an array sorted by:

```text
knowledge_ref ASC
```

Exact rules:

```text
duplicate knowledge_ref
→ whole manifest invalid

same knowledge_ref with different content
→ whole manifest invalid

unsorted source array in stored artifact
→ artifact invalid
```

Runtime does not reorder and silently accept a malformed stored artifact.

Admission tooling MAY construct canonical order before final artifact creation, but the accepted artifact itself must already be canonical.

---

## 3.5 Taxonomy canonical ordering

Within `RecognitionTaxonomyContractV1`:

```text
organizations
→ organization_id ASC

service_categories
→ service_category_id ASC

services
→ service_id ASC
```

Duplicate IDs are invalid.

Every Service must reference exactly one existing Organization and one existing Service Category in the same artifact.

---

## 3.6 Ruleset schema amendments

`RecognitionRuleSetV1` exact top-level fields are amended to:

```text
schema_version = 1

ruleset_id =
  "captivportal.network-intelligence.service-recognition"

ruleset_version:
  positive integer

ruleset_digest_sha256:
  lowercase ASCII hex, exactly 64 chars

taxonomy_id

taxonomy_version

taxonomy_digest_sha256

knowledge_manifest_id

knowledge_manifest_version

knowledge_manifest_digest_sha256

rules:
  tuple[RecognitionRuleV1, ...]
```

The new mandatory field is:

```text
knowledge_manifest_digest_sha256
```

Thus the ruleset binds the exact knowledge bytes, not only manifest ID/version.

Rules are canonically sorted by:

```text
rule_id ASC
```

`knowledge_refs` inside each rule are canonically sorted:

```text
knowledge_ref ASC
```

No duplicate knowledge_ref is allowed in one rule.

---

## 3.7 RecognitionRuleV1 R1 schema amendment

Exact fields become:

```text
rule_id
rule_kind
target_type
target_id
hostname_pattern
knowledge_refs
reviewed_at_utc
review_due_at_utc
lifecycle_state
ambiguity_group_id
```

`ambiguity_group_id` is:

```text
null
or
ASCII string matching:
^ambiguity\.[a-z0-9][a-z0-9._-]{1,94}[a-z0-9]$
```

Its semantics are frozen by R1-04.

Rule review interval:

```text
rule.reviewed_at_utc < rule.review_due_at_utc
rule.review_due_at_utc - rule.reviewed_at_utc <= 365 days
```

Every rule must reference at least one knowledge source.

Every referenced `knowledge_ref` must exist exactly once in the exact referenced manifest.

Dangling reference:

```text
whole ruleset invalid
```

---

## 3.8 Knowledge / rule expiry precedence

For one active rule `R`, define:

```text
referenced_sources(R) =
all RecognitionKnowledgeSourceV1 entries named by R.knowledge_refs
```

Exact effective due time:

```text
rule_effective_due_at =
MIN(
    R.review_due_at_utc,
    knowledge_manifest.review_due_at_utc,
    every referenced source.review_due_at_utc
)
```

A rule is eligible at `evaluated_at_utc` only when:

```text
R.lifecycle_state = active
AND
evaluated_at_utc < rule_effective_due_at
```

At exact equality:

```text
evaluated_at_utc == rule_effective_due_at
→ expired / not eligible
```

No grace period.

No rule-level later date may extend an earlier manifest/source expiry.

No manifest-level later date may extend an earlier source/rule expiry.

If an expired rule would otherwise be needed for a candidate result:

```text
no positive result from that rule
recognition coverage may become limited
```

It never becomes an automatic `unknown = no service` claim.

---

## 3.9 Review-order invariants

For each active rule:

```text
rule.reviewed_at_utc >= manifest.reviewed_at_utc
```

and for every referenced source:

```text
rule.reviewed_at_utc >= source.reviewed_at_utc
```

This means a production rule cannot claim to have been reviewed before the exact knowledge it relies on.

Violation:

```text
ruleset invalid
```

---

## 3.10 Canonical JSON / byte serialization — exact

All three artifacts use the same canonical serializer:

```text
CaptivPortalRecognitionCanonicalJsonV1
```

Input must already satisfy the artifact schema and canonical array ordering.

Exact byte recipe:

```text
1. Unicode strings MUST be NFC-normalized before serialization.

2. JSON object member names are sorted ascending by their UTF-8 byte sequence.
   All schema member names are ASCII, so this is equivalent to ASCII lexicographic order.

3. Arrays preserve the already-required canonical semantic ordering defined by this contract.

4. No insignificant whitespace is emitted.
   Separators are exactly:
       ',' between array/object items
       ':' between member name and value

5. UTF-8 is used directly.
   No BOM.
   No trailing newline.

6. String escaping is exact:
   '"'  → \" 
   '\\' → \\
   U+0008 → \b
   U+0009 → \t
   U+000A → \n
   U+000C → \f
   U+000D → \r
   other U+0000..U+001F → lowercase \u00xx
   '/' is never escaped
   all other NFC Unicode characters are emitted as UTF-8 bytes.

7. Integers use base-10 ASCII with no leading plus and no leading zero
   except integer zero itself.

8. Boolean tokens are exactly:
       true
       false

9. null token is exactly:
       null

10. Floating-point values are forbidden in these artifacts.

11. Duplicate object member names are forbidden before canonicalization.
```

Two independent implementations following this recipe MUST produce byte-identical results.

---

## 3.11 Digest computation — exact self-field exclusion

For each artifact, compute SHA-256 over the canonical JSON of the artifact after removing ONLY its own digest field.

Exact rules:

```text
Taxonomy digest input:
RecognitionTaxonomyContractV1
minus taxonomy_digest_sha256

Knowledge manifest digest input:
InitialRecognitionKnowledgeManifestV1
minus knowledge_manifest_digest_sha256

Ruleset digest input:
RecognitionRuleSetV1
minus ruleset_digest_sha256
```

Referenced child digests remain present.

Therefore ruleset digest input includes:

```text
taxonomy_digest_sha256
knowledge_manifest_digest_sha256
```

Digest encoding:

```text
SHA-256(raw canonical UTF-8 bytes)
→ lowercase hex
→ exactly 64 ASCII chars
```

No digest field is replaced by zeroes for hashing.
It is absent from the hash-input object.

---

## 3.12 Artifact equality / version rules

For one artifact ID:

```text
same version + same digest
→ same artifact identity

same version + different digest
→ integrity conflict / reject

different version + same digest
→ invalid no-op version bump / reject during admission

semantic content change
→ version MUST increment
→ digest MUST change
```

Rollback may reactivate an older previously accepted:

```text
ID + version + digest
```

without rewriting that artifact.

Runtime artifacts are immutable.

Review date change, due date change, display-name change, rule lifecycle change, pattern change, knowledge-source change and ambiguity-group change are all semantic content changes for digest/version purposes.

Stable taxonomy IDs and previously admitted rule IDs are not silently reused for unrelated semantics.

---

## 3.13 Cross-artifact exact-reference validation

Ruleset must reference exact taxonomy:

```text
ruleset.taxonomy_id == taxonomy.taxonomy_id
ruleset.taxonomy_version == taxonomy.taxonomy_version
ruleset.taxonomy_digest_sha256 == taxonomy.taxonomy_digest_sha256
```

Ruleset must reference exact manifest:

```text
ruleset.knowledge_manifest_id == manifest.knowledge_manifest_id
ruleset.knowledge_manifest_version == manifest.knowledge_manifest_version
ruleset.knowledge_manifest_digest_sha256 == manifest.knowledge_manifest_digest_sha256
```

Any mismatch:

```text
whole recognition bundle invalid
NI-04 dependency state = recognition_configuration_unavailable
```

No nearest-version selection.
No fallback manifest.
No partial ruleset activation.

---

## 3.14 Synthetic canonical positive example

This example is **synthetic only** and is NOT admitted production recognition knowledge.
It exists solely to make canonicalization testable.

### Taxonomy

```json
{"organizations":[{"display_name":"Example Lab","organization_id":"org.example_lab","organization_kind":"service_operator"}],"schema_version":1,"service_categories":[{"display_name":"Video Streaming","service_category_id":"category.video_streaming"}],"services":[{"display_name":"Example Video","lifecycle_state":"active","organization_id":"org.example_lab","service_category_id":"category.video_streaming","service_id":"service.example_video"}],"taxonomy_digest_sha256":"63c37fdcf6d276a6ab7521e2e7cd6c9d5baad2c821a6c76ea8e87d294a836700","taxonomy_id":"captivportal.network-intelligence.recognition-taxonomy","taxonomy_version":1}
```

Expected taxonomy digest:

```text
63c37fdcf6d276a6ab7521e2e7cd6c9d5baad2c821a6c76ea8e87d294a836700
```

### Knowledge manifest

```json
{"knowledge_manifest_digest_sha256":"8529f4bc8b29d7bbe64d1d8394ba6d33021b2c59cd70ad5ccc5b0ce4e01e0ed1","knowledge_manifest_id":"captivportal.network-intelligence.recognition-knowledge","knowledge_manifest_version":1,"review_due_at_utc":"2026-12-31T00:00:00.000000Z","reviewed_at_utc":"2026-10-10T00:00:00.000000Z","schema_version":1,"sources":[{"claim_summary":"Synthetic fixture only; not production recognition knowledge.","knowledge_ref":"knowledge.synthetic.example_video","publisher_or_owner":"CaptivPortal synthetic fixture","review_due_at_utc":"2026-12-31T00:00:00.000000Z","reviewed_at_utc":"2026-10-10T00:00:00.000000Z","source_class":"reviewed_internal_research","source_locator":"fixture://synthetic/example-video"}]}
```

Expected manifest digest:

```text
8529f4bc8b29d7bbe64d1d8394ba6d33021b2c59cd70ad5ccc5b0ce4e01e0ed1
```

### Ruleset

```json
{"knowledge_manifest_digest_sha256":"8529f4bc8b29d7bbe64d1d8394ba6d33021b2c59cd70ad5ccc5b0ce4e01e0ed1","knowledge_manifest_id":"captivportal.network-intelligence.recognition-knowledge","knowledge_manifest_version":1,"rules":[{"ambiguity_group_id":null,"hostname_pattern":"video.example.invalid","knowledge_refs":["knowledge.synthetic.example_video"],"lifecycle_state":"active","review_due_at_utc":"2026-12-31T00:00:00.000000Z","reviewed_at_utc":"2026-10-10T00:00:00.000000Z","rule_id":"rule.synthetic.example_video.sni","rule_kind":"service_sni_exact","target_id":"service.example_video","target_type":"service"}],"ruleset_digest_sha256":"61097d804e91e5bad70b8f6d1e883718e84d631effcec0fe3240e8a806a426bd","ruleset_id":"captivportal.network-intelligence.service-recognition","ruleset_version":1,"schema_version":1,"taxonomy_digest_sha256":"63c37fdcf6d276a6ab7521e2e7cd6c9d5baad2c821a6c76ea8e87d294a836700","taxonomy_id":"captivportal.network-intelligence.recognition-taxonomy","taxonomy_version":1}
```

Expected ruleset digest:

```text
61097d804e91e5bad70b8f6d1e883718e84d631effcec0fe3240e8a806a426bd
```

Again:

```text
example.invalid
Example Video
Example Lab
```

are synthetic fixtures and MUST NOT appear as active production knowledge.

---

## 3.15 Digest-invalid rejection example

Take the exact manifest above but replace:

```text
knowledge_manifest_digest_sha256
```

with:

```text
0000000000000000000000000000000000000000000000000000000000000000
```

Validator recomputation remains:

```text
8529f4bc8b29d7bbe64d1d8394ba6d33021b2c59cd70ad5ccc5b0ce4e01e0ed1
```

Required result:

```text
REJECT WHOLE BUNDLE
reason = knowledge_manifest_digest_mismatch
NO rule execution
NO partial activation
```

No implementation may overwrite the bad digest and continue silently.

---

## 3.16 P1-02 disposition

```text
P1-02 = PASS

MANIFEST SCHEMA = FROZEN
CANONICAL BYTES = FROZEN
DIGEST EXCLUSION = FROZEN
ORDERING = FROZEN
REF UNIQUENESS = FROZEN
EXPIRY PRECEDENCE = FROZEN
VERSION/EQUALITY = FROZEN
```

---

# 4. R1-03 — DNS CORRELATION V1 SAFETY REPAIR
## Supersedes v1 §§21, 25–27, 36 where DNS-correlated observed_at was defined, 53, 55–61, 66, 72 step 12, 110–111, 114, 116, 142–144 wherever DNS-connected positive resolution was active

## 4.1 Selected safe policy

R1 selects Tech Lead option **B**.

Current NI-01 DNS schema does NOT preserve enough answer-owner linkage to prove that every A/AAAA value in a multi-question/multi-answer DNS observation belongs to a specific matched query.

Therefore V1 MUST NOT produce a positive Service or Organization result from DNS→connection correlation.

Exact V1 positive recognition signals are now:

```text
TLS SNI
QUIC SNI
```

only.

DNS remains protected network metadata and may be returned by the protected recognition read boundary, but it is NOT a positive recognition primitive in NI-04 V1.

No NI-01 schema change is authorized by this repair.

---

## 4.2 Rule-kind admission status

The V1 rule-kind vocabulary remains structurally known:

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

But active production admission is frozen to:

```text
ACTIVE-ELIGIBLE V1:
service_sni_exact
service_sni_suffix
organization_sni_exact
organization_sni_suffix

RESERVED / NOT ACTIVE IN V1:
service_dns_connected_exact
service_dns_connected_suffix
organization_dns_connected_exact
organization_dns_connected_suffix
```

Admission validator rule:

```text
if rule_kind is *_dns_connected_*
AND lifecycle_state = active
→ whole ruleset invalid
```

A reserved DNS-connected rule may exist only as:

```text
lifecycle_state = retired
```

for schema/history fixtures.

The initial production bundle SHOULD omit reserved DNS-connected rules entirely.

Runtime matcher does not evaluate retired rules.

---

## 4.3 RecognitionSourceEvidenceV1 DNS DTO amendment

The protected NI-01 recognition DTO for a DNS source observation is amended to contain the fields necessary to represent the current source faithfully, without claiming unsupported ownership linkage.

Exact DNS family payload:

```text
family = dns

dns_event_kind
rcode
query_count_observed
answer_count_observed
queries_truncated
answers_truncated
query_names_presence_state
answer_values_presence_state

queries:
    tuple[RecognitionDnsQueryV1, ...]

answers:
    tuple[RecognitionDnsAnswerV1, ...]
```

`RecognitionDnsQueryV1`:

```text
ordinal
query_name
query_type
```

`RecognitionDnsAnswerV1`:

```text
ordinal
answer_type
answer_value
```

No field is invented for:

```text
answer_owner_name
answer_query_ordinal
answer_question_binding
```

because current NI-01 schema does not store those semantics.

The DTO MUST NOT infer such linkage.

---

## 4.4 DNS evidence runtime meaning

In NI-04 V1:

```text
DNS query observed
→ MAY contribute to internal recognition-limitation diagnostics
→ MUST NOT resolve Service
→ MUST NOT resolve Organization

DNS A/AAAA answer observed
→ MUST NOT resolve Service
→ MUST NOT resolve Organization

DNS query + A/AAAA answer + later peer IP match
→ MUST NOT resolve Service in V1
→ MUST NOT resolve Organization in V1
```

This remains true even when:

```text
same Site
same Device
same observation
time distance <= 300s
outbound external edge exists
```

because exact query→answer ownership is not guaranteed by current retained schema.

---

## 4.5 DNS_CONNECTION_CORRELATION_SECONDS status

Parent v1 active constant:

```text
DNS_CONNECTION_CORRELATION_SECONDS = 300
```

is superseded for NI-04 V1 runtime by:

```text
DNS_CONNECTION_CORRELATION_SECONDS = NOT_ACTIVE_IN_V1
```

No production matcher/correlator may use a numeric DNS connection window to produce a Service result under this contract.

A future architecture amendment may re-admit DNS correlation only after one of these is proven:

```text
A. source schema preserves trustworthy query↔answer association;

or

B. an independently admitted deterministic DNS correlation contract proves equivalent ownership without unsafe inference.
```

That future change is not delegated to Coder.

---

## 4.6 Direct SNI remains enabled

Direct Service recognition remains exactly:

```text
TLS/QUIC edge belongs to authoritative exact Site+Device
AND
edge direction = outbound
AND
peer_scope = external
AND
SNI presence_state = observed_retained
AND
SNI canonicalization passes
AND
active unexpired ruleset contains a deterministic highest-precedence SNI match
```

Then the matcher may return:

```text
service_resolved
organization_resolved
ambiguous
unknown
```

according to R1-04 collision semantics.

Evidence strength for resolved direct SNI:

```text
strong
```

Support state:

```text
directly_supported
```

No IP ownership is needed.

---

## 4.7 Missing SNI / ECH / DNS cache / resolver cases — amended exact outcomes

### Missing SNI

```text
no active direct SNI signal
→ no positive Service result
→ recognition may be limited
```

### ECH / encrypted hostname

```text
no visible admitted SNI
→ no Service inference from ECH itself
→ no DNS fallback in V1
→ recognition_limited or unknown according to coverage
```

### DNS cache

```text
connection occurs without qualifying direct SNI
→ no Service result
```

No old DNS archaeology is attempted.

### Local DNS resolver

```text
DNS event may be represented internally
→ resolver event does not resolve downstream Service
```

### Public DNS resolver

```text
DNS event may be represented internally
→ resolver event does not resolve downstream Service
```

Public resolver organization is not inferred as the requested Service.

### Shared CDN / cloud IP

```text
peer IP alone
→ never exact Service
```

This remains permanent V1 behavior.

---

## 4.8 Device IP reassignment / late binding unaffected

R1-03 does NOT change identity authority.

Direct SNI is considered only after NI-02B has produced the authoritative exact:

```text
Site + Device + event-time edge
```

Therefore:

```text
current IP change
old DHCP binding
later Registry binding
```

never trigger query-time IP identity reconstruction in NI-04.

---

## 4.9 Read algorithm amendment

Parent v1 `READ ALGORITHM — EXACT ORDER` is amended.

Remove:

```text
build bounded DNS→answer→connection correlation candidates

evaluate correlated DNS rules
```

New exact core evaluation order after evidence/provenance validation is:

```text
1. canonicalize eligible retained TLS/QUIC SNI in request-local memory;

2. evaluate active direct SNI rules through the production pure matcher kernel;

3. resolve exact/static-overlap conflicts using R1-04;

4. create ephemeral ServiceObservationV1 from resolved/ambiguous/unknown matcher outcomes;

5. aggregate DeviceServiceSummaryV1.
```

DNS payload, if present in the protected evidence set, is not fed into positive rule matching.

---

## 4.10 Required negative acceptance

All MUST produce **no Service resolution**:

```text
1. one DNS observation contains matched query + unrelated additional A/AAAA

2. DNS query + answer + later DNS-to-resolver edge only

3. DNS query + answer + later TLS/QUIC peer-IP match but no direct admitted SNI

4. two candidate Services share the same answer/peer IP

5. DNS cache with no new DNS and no direct admitted SNI

6. local resolver response only

7. public resolver response only
```

Expected product meaning:

```text
unknown
or
recognition_limited
```

according to source/attribution/rule visibility.

Never:

```text
service_resolved
```

---

## 4.11 Positive acceptance

Positive V1 recognition must be reproducible from admitted direct SNI fields.

Required:

```text
active admitted service_sni_exact or service_sni_suffix rule
+
authoritative Site+Device TLS/QUIC edge
+
observed_retained SNI
+
valid provenance
+
unexpired knowledge/rule
→ deterministic service_resolved
```

Near-match hostname:

```text
→ no Service resolution
```

---

## 4.12 P1-03 disposition

```text
P1-03 = PASS

DNS-CONNECTED POSITIVE RECOGNITION =
NOT ACTIVE IN V1

DIRECT TLS/QUIC SNI RECOGNITION =
ACTIVE-ELIGIBLE

PARENT SCHEMA CHANGE =
NO

FALSE DNS OWNERSHIP INFERENCE =
FORBIDDEN
```

---

# 5. R1-04 — STATIC COLLISION VS RUNTIME AMBIGUITY
## Supersedes v1 §§20, 23, 29–30, 68, 70, 109, 122 where collision classes were not separated

## 5.1 Definitions

For one `RecognitionRuleV1`, define:

```text
matcher_key =
(rule_kind, canonical hostname_pattern)
```

Define target key:

```text
target_key =
(target_type, target_id)
```

Only active rules participate in runtime matching.
Retired rules still participate in artifact uniqueness/integrity checks.

---

## 5.2 Static invalid duplicates — whole bundle rejected

The following are always invalid at artifact admission/startup:

```text
A. duplicate rule_id

B. same rule_id with non-identical content

C. two rules with same matcher_key + same target_key
   even if rule_id differs

D. semantically identical rule copied under another rule_id

E. one rule contains duplicate knowledge_ref

F. same matcher_key targets different Services
   but ambiguity_group_id is null

G. same matcher_key targets different Services
   and ambiguity_group_id values differ

H. an ambiguity_group_id contains rules with different matcher_key

I. ambiguity_group_id is present on a rule that has no same-matcher-key
   different-Service partner in the same ruleset

J. same matcher_key collision mixes active and retired rules while an active rule
   declares an ambiguity_group_id whose full intended group is not active
```

Result:

```text
whole ruleset invalid
NI-04 dependency state = recognition_configuration_unavailable
```

No runtime ambiguity is produced from an invalid bundle.

---

## 5.3 Explicit valid runtime ambiguity group

Identical match patterns targeting different Services MAY be admitted only as a deliberate known-shared semantic case.

Exact admission shape:

```text
same matcher_key

different target_id values

target_type = service for every member

same non-null ambiguity_group_id for every colliding member

>= 2 members

all members active

all members independently satisfy provenance/review requirements
```

Such a group means:

```text
this hostname is known to be insufficient to distinguish these Services
```

Runtime behavior when that matcher_key is the strongest matching key:

```text
resolution_state = ambiguous
service_id = null
NO rule_id ordering winner
NO lexical target winner
NO confidence score
```

The ambiguity group is therefore an explicit knowledge fact, not an accidental loader collision.

---

## 5.4 Valid deterministic overlaps that are NOT ambiguity

These overlaps are valid:

### Exact vs suffix

```text
service_sni_exact for host X
+
service_sni_suffix for parent suffix Y
```

when X matches Y.

Exact rule has stronger frozen priority and wins.

### Longer suffix vs shorter suffix

Two different suffix patterns may overlap.

Example shape:

```text
video.example.invalid
example.invalid
```

Longest matching suffix wins within the same rule kind.

### Service vs organization rule

A Service SNI rule and Organization SNI rule may both match.

Service result remains primary.

Organization output for a resolved Service comes from:

```text
ServiceTaxonV1.organization_id
```

A weaker matching infrastructure Organization rule does not override the Service's taxonomy Organization.

These deterministic overlaps do not require `ambiguity_group_id`.

---

## 5.5 Invalid static test pair

Synthetic bundle:

```text
rule.a:
  rule_kind = service_sni_exact
  hostname_pattern = shared.example.invalid
  target_id = service.alpha
  ambiguity_group_id = null

rule.b:
  rule_kind = service_sni_exact
  hostname_pattern = shared.example.invalid
  target_id = service.beta
  ambiguity_group_id = null
```

Required:

```text
ARTIFACT REJECT
reason = undeclared_service_matcher_collision
```

Runtime is never reached.

---

## 5.6 Valid runtime ambiguity test pair

Synthetic bundle:

```text
rule.a:
  rule_kind = service_sni_exact
  hostname_pattern = shared.example.invalid
  target_id = service.alpha
  ambiguity_group_id = ambiguity.shared_example

rule.b:
  rule_kind = service_sni_exact
  hostname_pattern = shared.example.invalid
  target_id = service.beta
  ambiguity_group_id = ambiguity.shared_example
```

Both rules otherwise independently pass provenance/review validation.

Request evidence:

```text
SNI = shared.example.invalid
```

Required runtime result:

```text
resolution_state = ambiguous
service_id = null
```

Forbidden:

```text
rule.a wins because rule_id sorts first
rule.b wins because target_id sorts first
```

---

## 5.7 Same-target duplicate rejection test pair

Synthetic bundle:

```text
rule.a:
  service_sni_exact
  video.example.invalid
  → service.alpha

rule.b:
  service_sni_exact
  video.example.invalid
  → service.alpha
```

Required:

```text
ARTIFACT REJECT
reason = duplicate_matcher_target_rule
```

No reason exists to carry redundant semantically equivalent rules.

---

## 5.8 Runtime ambiguity scope in current SNI-only V1

With DNS-connected rules inactive, V1 runtime ambiguity can arise only from an explicitly admitted:

```text
ambiguity_group_id
```

for the strongest matching direct SNI matcher key.

No other hidden collision path is permitted.

Future DNS or other signal admission must separately define whether it can create additional runtime ambiguity classes.

---

## 5.9 P1-04 disposition

```text
P1-04 = PASS

STATIC DUPLICATES = CLOSED INVALID SET

UNDECLARED SAME-MATCHER DIFFERENT-SERVICE COLLISION = INVALID

DECLARED SAME-MATCHER DIFFERENT-SERVICE AMBIGUITY GROUP = VALID

RULE ID AS WINNER = FORBIDDEN
```

---

# 6. R1-05 — NI-04A CODE / VALIDATION BOUNDARY
## Supersedes v1 §§7, 17–21, 68–72, 105, 133–134, 145–147 where prerequisite code ownership was not explicit

## 6.1 Stage split — exact

R1 freezes three distinct stages:

```text
TASK-DTI-NI-04K
= research / semantic knowledge admission
= NO production code

TASK-DTI-NI-04A-CODE
= protected evidence bridges
+ artifact runtime validation
+ canonical digests
+ reusable pure direct-SNI matcher kernel
= NO Admin Service API/UI
= NO DeviceServiceSummary product orchestration

TASK-DTI-NI-04
= request-time cross-store orchestration
+ ServiceObservationV1 construction
+ DeviceServiceSummaryV1 aggregation
+ Admin API/UI
```

No stage may silently absorb the next one.

---

## 6.2 NI-04K ownership

NI-04K owns only:

```text
real knowledge provenance research
semantic taxonomy candidate preparation
real rule candidate preparation
positive/negative fixtures
Architect/Tech Lead admission evidence
```

NI-04K creates no runtime Python code and no production feature activation.

---

## 6.3 NI-04A-CODE exact module boundaries

After NI-04K PASS and a separate exact Tech Lead implementation TASK, NI-04A-CODE may implement only these semantic boundaries.

### A. NI-01 protected recognition reader

Required owner/module:

```text
app/network_metadata/recognition_read_service.py
```

Purpose:

```text
read exact observation refs from NI-01 store
through mode=ro / query_only=ON
return protected RecognitionSourceEvidenceV1
```

It is NI-01-owned internal infrastructure.

It MUST NOT be added to the ordinary non-sensitive public `NetworkMetadataReadService.list_observations()` payload.

It MUST NOT be exposed directly to:

```text
Admin API
browser
template
analytics public/internal HTTP route
```

### B. NI-02B protected recognition snapshot reader

Required owner/module:

```text
app/network_metadata_projection/recognition_read_service.py
```

Purpose:

```text
same-snapshot runtime state
+ authoritative Site/MAC/device binding
+ bounded Device-relative edge facts
+ source_observation_ref/provenance needed for recognition
```

It reads existing NI-02B schema only.

No writer/schema mutation.

Current NI-03:

```text
app/network_metadata_projection/read_service.py
read_protocol_evidence_snapshot(...)
```

remains semantically unchanged.

### C. Artifact schema/canonicalization owner

Required owner/module:

```text
app/network_service_recognition/artifacts.py
app/network_service_recognition/canonical.py
```

Owns exactly:

```text
RecognitionTaxonomyContractV1 validation
InitialRecognitionKnowledgeManifestV1 validation
RecognitionRuleSetV1 validation
RecognitionRuleV1 validation
cross-artifact reference validation
CaptivPortalRecognitionCanonicalJsonV1
SHA-256 identity validation
review/expiry validation
static collision admission
```

### D. Reusable production matcher semantic owner

Required owner/module:

```text
app/network_service_recognition/matcher.py
```

NI-04A-CODE MUST implement the real production pure matcher kernel now.

It is not test-only.

Exact conceptual signature:

```text
match_direct_sni_v1(
    *,
    hostname,
    signal_family,
    evaluated_at_utc,
    taxonomy,
    manifest,
    ruleset
) -> RecognitionMatchOutcomeV1
```

`signal_family` exact V1 enum:

```text
tls_sni
quic_sni
```

The matcher owns:

```text
hostname canonicalization
active/unexpired rule eligibility
rule-kind priority
exact/suffix specificity
R1-04 static-admitted ambiguity semantics
resolved Service/Organization target selection
unknown outcome
```

It does NOT own:

```text
SQLite
Device attribution
Registry
cross-store reads
DNS correlation
24h Device aggregation
Recent Services list
freshness/coverage mapping
Admin authorization
HTTP
UI
```

### E. Accepted local artifacts

Required conceptual location:

```text
app/network_service_recognition/knowledge/
    recognition-taxonomy-v1.json
    recognition-knowledge-manifest-v1.json
    recognition-ruleset-v1.json
```

Exact filenames may be changed by Tech Lead only if repository convention requires an equivalent fixed path, but semantic ownership must remain in this package and there must be one active bundle, not duplicated constants.

The exact accepted bundle is the NI-04K output.

---

## 6.4 NI-04A-CODE explicitly deferred components

NI-04A-CODE MUST NOT implement:

```text
DeviceServiceRecognitionReadService product orchestration

ServiceObservationV1 aggregation from a Device window

DeviceServiceSummaryV1 aggregation

Recent Services product list

Service Categories product list

Last Service Observation product selection

product freshness/coverage serialization

AdminQueryService service-intelligence method

/admin/api/v1/.../service-intelligence

Device Card Service Intelligence section

browser polling

customer-visible Service result

new user-data writer

new recognition-result DB

DNS correlation engine
```

These remain main NI-04 scope, except DNS correlation which is not active in V1 at all.

---

## 6.5 NI-04A tests must use production semantic kernel

Forbidden:

```text
test-only matcher
fixture-only fake specificity algorithm
separate Python implementation in tests
expected-result generator that reimplements matching semantics
```

Required:

```text
artifact tests
→ load production artifact validator/canonicalizer

matcher tests
→ invoke app/network_service_recognition/matcher.py

integration tests
→ NI-02B protected snapshot + NI-01 protected evidence
→ feed eligible SNI into the same production matcher kernel
```

Expected values may be static fixtures, but the semantic engine under test must be the production matcher.

---

## 6.6 NI-04A integration proof without main product orchestration

NI-04A-CODE must prove one bounded integration path:

```text
NI-02B recognition snapshot
→ exact source_observation_ref
→ NI-01 protected evidence
→ provenance equality
→ eligible retained TLS/QUIC SNI
→ production match_direct_sni_v1()
→ internal RecognitionMatchOutcomeV1
```

This integration proof is not an Admin API.

It may exist as:

```text
integration test fixture/harness
```

provided the only matcher used is the production matcher module.

No `DeviceServiceSummaryV1` is required in NI-04A-CODE.

---

## 6.7 RecognitionMatchOutcomeV1 — internal matcher DTO

Freeze the pure matcher return DTO so main NI-04 does not redesign it.

Exact fields:

```text
schema_version = 1

resolution_state:
    service_resolved
    organization_resolved
    ambiguous
    unknown

service_id:
    Service ID | null

organization_id:
    Organization ID | null

service_category_id:
    Service Category ID | null

evidence_strength_class:
    strong | null

support_state:
    directly_supported | ambiguous | unsupported

matched_rule_ids:
    tuple[str, ...]

ambiguity_group_id:
    string | null

ruleset_id
ruleset_version
ruleset_digest_sha256

taxonomy_id
taxonomy_version
taxonomy_digest_sha256

knowledge_manifest_id
knowledge_manifest_version
knowledge_manifest_digest_sha256
```

Exact invariants:

### service_resolved

```text
service_id != null
organization_id = taxonomy service.organization_id
service_category_id = taxonomy service.service_category_id
matched_rule_ids = exactly one winning Service rule_id
evidence_strength_class = strong
support_state = directly_supported
ambiguity_group_id = null
```

### organization_resolved

```text
service_id = null
organization_id != null
service_category_id = null
matched_rule_ids = exactly one winning Organization rule_id
evidence_strength_class = strong
support_state = directly_supported
ambiguity_group_id = null
```

### ambiguous

```text
service_id = null
service_category_id = null
organization_id = null
matched_rule_ids = all strongest ambiguity-group Service rule_ids sorted ASC
len(matched_rule_ids) >= 2
evidence_strength_class = null
support_state = ambiguous
ambiguity_group_id != null
```

### unknown

```text
service_id = null
organization_id = null
service_category_id = null
matched_rule_ids = empty tuple
evidence_strength_class = null
support_state = unsupported
ambiguity_group_id = null
```

No confidence number.

No hostname is stored in this DTO.

---

## 6.8 Main NI-04 exact ownership after NI-04A PASS

Main NI-04 later owns:

```text
app/network_service_recognition/read_service.py
```

and the safe product DTO/aggregation layer.

It MUST reuse without semantic duplication:

```text
artifacts.py
canonical.py
matcher.py
NI-01 protected reader
NI-02B protected reader
```

Main NI-04 orchestration sequence becomes:

```text
Device identity from existing Admin Device gateway
→ NI-02B protected recognition snapshot
→ NI-01 protected source evidence by exact refs
→ provenance verification
→ direct TLS/QUIC SNI signals only
→ matcher.py
→ ServiceObservationV1
→ DeviceServiceSummaryV1
→ AdminQueryService
→ versioned Admin API
→ Device Card Service Intelligence
```

No second recognition engine.

---

## 6.9 P1-05 disposition

```text
P1-05 = PASS

PURE PRODUCTION MATCHER IN NI-04A-CODE = REQUIRED

TEST-ONLY MATCHER = FORBIDDEN

DNS CORRELATOR IN NI-04A = NO

ADMIN SERVICE API/UI IN NI-04A = NO

DEVICE SUMMARY AGGREGATION IN NI-04A = NO

MAIN NI-04 MUST REUSE NI-04A MATCHER = YES
```

---

# 7. R1 AMENDED STARTUP VALIDATION

Parent v1 startup artifact validation is amended to the following exact order:

```text
1. load exact taxonomy bytes;
2. parse strict JSON with duplicate-member rejection;
3. validate taxonomy schema/cardinality/order;
4. recompute taxonomy digest;
5. compare exact taxonomy digest;

6. load exact knowledge-manifest bytes;
7. parse strict JSON with duplicate-member rejection;
8. validate manifest schema/source ordering/uniqueness/review windows;
9. recompute manifest digest;
10. compare exact manifest digest;

11. load exact ruleset bytes;
12. parse strict JSON with duplicate-member rejection;
13. validate ruleset schema/rule order/ref uniqueness;
14. validate exact taxonomy ID/version/digest reference;
15. validate exact manifest ID/version/digest reference;
16. validate every rule target and knowledge ref;
17. validate review-order/effective-expiry semantics;
18. validate active rule kinds — DNS-connected active is forbidden;
19. validate R1-04 static collision rules;
20. recompute ruleset digest;
21. compare exact ruleset digest;
22. activate bundle atomically as one in-memory immutable set.
```

Any failure:

```text
no partial bundle
no prior-file mixing
no nearest version
no rule subset activation
NI-04 recognition dependency unavailable
NI-03 unaffected
Portal/Auth/CAPPORT unaffected
```

---

# 8. R1 AMENDED RECOGNITION COVERAGE

R1 does not redefine source/attribution coverage from v1.

Recognition coverage gains one exact limitation:

```text
DNS evidence exists
but no eligible direct SNI exists
→ DNS cannot rescue recognition in V1
```

Therefore recognition state may be:

```text
usable
limited
unavailable
```

Conceptual safe mapping:

```text
bundle valid + at least one active unexpired rule + eligible direct SNI evaluation possible
→ recognition_state = usable

bundle valid
BUT direct SNI absent/unobservable for candidate traffic
OR only reserved DNS evidence exists
OR required active rule expired
→ recognition_state = limited

bundle invalid/missing/digest mismatch
→ recognition_state = unavailable
```

This is independent of:

```text
source_state
attribution_state
```

No dimension may mask another.

---

# 9. R1 AMENDED SPECIAL-CASE MATRIX

| Case | Positive Service V1? | Required positive evidence | Safe insufficient result |
|---|---|---|---|
| Direct unique TLS SNI | YES | admitted active Service SNI rule | resolved / conflict handling |
| Direct unique QUIC SNI | YES | admitted active Service SNI rule | resolved / conflict handling |
| Shared CDN/cloud IP only | NO | none admitted | unknown/limited |
| DNS query only | NO | DNS not positive in V1 | unknown/limited |
| DNS query + A/AAAA | NO | DNS not positive in V1 | unknown/limited |
| DNS + later peer-IP match | NO | DNS-connected not active in V1 | unknown/limited |
| DNS cache + no SNI | NO | no admitted positive signal | unknown/limited |
| Missing SNI | NO unless another direct admitted SNI exists | direct SNI required | limited/unknown |
| ECH hides hostname | NO | no ECH inference | limited/unknown |
| VPN/tunnel inner services | NO | only outer direct SNI if itself admitted | unknown/limited |
| Local DNS resolver | NO downstream Service from resolver event | direct SNI later | unknown/limited |
| Public DNS resolver | NO downstream Service from resolver event | direct SNI later | unknown/limited |
| IP reassignment | MAYBE | authoritative NI-02B event-time edge + direct SNI | no current-IP guess |
| Event pre-Registry | NO until NI-02B authoritative binding | later authoritative binding | identity_pending |
| Current attribution degraded but old committed direct-SNI edge valid | YES, with degraded coverage | already committed authoritative edge + retained SNI | degraded result allowed |
| Bundle expired | NO from expired rules | replacement admitted bundle | recognition_limited |
| Bundle digest invalid | NO | valid exact bundle required | recognition_unavailable |

---

# 10. R1 ACCEPTANCE MATRIX

## 10.1 R1-01 knowledge admission

```text
No real approved Service/rule bundle exists
→ NI-04K HOLD
→ NI-04A-CODE HOLD

Coder proposes a hostname/service choice
→ FAIL

Architect/Tech Lead accepted NI-04K bundle with >=1 real active direct-SNI Service rule
→ knowledge prerequisite PASS candidate
```

## 10.2 R1-02 digest determinism

Two independent canonical serializers given the same valid synthetic artifact MUST produce the exact hashes frozen in §3.14.

Any difference:

```text
FAIL
```

Required invalid cases:

```text
wrong digest
unsorted sources
unsorted rules
unsorted knowledge_refs
duplicate knowledge_ref
dangling knowledge_ref
same ID/version + different digest
different version + same digest
expired source at manifest review time
rule reviewed before referenced source
ruleset taxonomy digest mismatch
ruleset manifest digest mismatch
```

Every case:

```text
whole bundle rejected
```

## 10.3 R1-03 DNS false-positive protection

Required:

```text
ambiguous multi-answer DNS response
→ no Service

unrelated additional A/AAAA
→ no Service

DNS-to-resolver-only edge
→ no Service

two candidate services share peer IP
→ no Service

DNS + later TLS peer match with no admitted direct SNI
→ no Service

active *_dns_connected_* rule in artifact
→ artifact reject
```

Positive direct SNI fixture:

```text
→ deterministic Service result
```

## 10.4 R1-04 collision loader/runtime

Required invalid static cases:

```text
duplicate rule_id
same matcher+same target duplicate
same matcher+different Service with no ambiguity group
same matcher+different Service with different ambiguity groups
orphan ambiguity_group_id
```

All:

```text
artifact reject
```

Required valid overlap cases:

```text
exact vs suffix
→ exact wins

longer suffix vs shorter suffix
→ longer suffix wins

explicit same matcher + same ambiguity_group + different Services
→ runtime ambiguous
→ no Service ID
```

Rule ID order never chooses winner.

## 10.5 R1-05 semantic-owner proof

Repository/source review must prove:

```text
one artifact canonicalizer owner
one artifact validator owner
one matcher semantic owner
no test-only duplicate matcher
no Admin Service API/UI in NI-04A-CODE
no DeviceServiceSummary orchestration in NI-04A-CODE
no DNS correlator
no NI-01/NI-02B schema/writer change
NI-03 tests unchanged/green
```

Integration test must use:

```text
protected NI-02B reader
+
protected NI-01 reader
+
production matcher.py
```

not a test-only recognition engine.

---

# 11. R1 PROTECTED COMPONENTS — UNCHANGED

R1 does not authorize mutation of semantic ownership in:

```text
Portal
Authorization
CAPPORT
Omada Provider / Controller
Visitor Registry
Visit Lifecycle
Observation
Current State
Traffic Projection
Device Fingerprint
Fingerprint Sensor
Suricata
NI-01 writer/schema
NI-02A authority
NI-02B writer/schema
NI-03 public DTO/API/UI semantics
Admin security/session boundary
Settings control plane
Nginx routing/logging
SPAN/RSPAN/network topology
```

The only future additive read/code boundaries admitted by R1 are those enumerated in §6 after their governance gates are passed.

---

# 12. R1 CONFIGURATION / DEPLOYMENT STATUS

The v1 canonical configuration handoff decision remains unchanged:

```text
NI-01 config authority:
/etc/captive-portal/network-metadata.env
→ network_metadata_config_from_env()

NI-02B config authority:
/etc/captive-portal/network-metadata-projection.env
→ projection_config_from_env()
```

NI-04A-CODE may later require the already-designed main-process NI-01 EnvironmentFile handoff, but this R1 itself authorizes no systemd action.

Exact status now:

```text
SYSTEMD CHANGE = NO
PRODUCTION CHANGE = NO
SERVICE RESTART = NO
```

---

# 13. R1 REPRODUCIBILITY AMENDMENT

Within retained evidence availability, a future main NI-04 result is reproducible from:

```text
exact evaluated_at_utc
exact Site+Device identity
exact NI-02B edge facts/provenance
exact NI-01 retained TLS/QUIC SNI evidence
exact taxonomy ID/version/digest
exact knowledge-manifest ID/version/digest
exact ruleset ID/version/digest
exact matcher contract version
```

DNS evidence is NOT a dependency of a positive V1 Service result after R1-03.

Reproduction after NI-01 sensitive retention expiry remains not promised because V1 stores no separate Service history.

---

# 14. R1 FROZEN CONSTANT REGISTER — DELTA

All v1 constants remain unchanged except:

```text
DNS_CONNECTION_CORRELATION_SECONDS
```

which is no longer an active runtime constant.

Exact R1 status:

```text
DNS_CONNECTION_CORRELATION_SECONDS = NOT_ACTIVE_IN_V1
```

No numeric DNS correlation interval participates in Service resolution.

New artifact constants:

```text
KNOWLEDGE_MANIFEST_ID =
"captivportal.network-intelligence.recognition-knowledge"

TAXONOMY_ID =
"captivportal.network-intelligence.recognition-taxonomy"

RULESET_ID =
"captivportal.network-intelligence.service-recognition"

ARTIFACT_CANONICALIZATION =
CaptivPortalRecognitionCanonicalJsonV1

ARTIFACT_DIGEST =
SHA-256 lowercase hex
```

---

# 15. R1 CONSOLIDATED INVARIANTS

```text
NI04-R1-I01
Coder never selects real Services, hostnames, Organizations or Categories.

NI04-R1-I02
Real initial recognition knowledge is admitted by TASK-DTI-NI-04K before bundle-dependent code.

NI04-R1-I03
Every production recognition artifact has exact ID + version + SHA-256 digest.

NI04-R1-I04
Canonical bytes are independently reproducible.

NI04-R1-I05
Ruleset binds exact taxonomy digest and exact knowledge-manifest digest.

NI04-R1-I06
Dangling or duplicate knowledge refs invalidate the whole bundle.

NI04-R1-I07
Earliest rule/manifest/source expiry wins; later dates never extend it.

NI04-R1-I08
Current NI-01 DNS schema is not treated as proof of query→answer ownership.

NI04-R1-I09
DNS-connected Service/Organization recognition is not active in V1.

NI04-R1-I10
Positive V1 recognition uses admitted direct TLS/QUIC SNI only.

NI04-R1-I11
IP-only exact Service inference remains forbidden.

NI04-R1-I12
Static undeclared same-matcher Service collision invalidates the bundle.

NI04-R1-I13
Deliberate runtime ambiguity requires explicit common ambiguity_group_id.

NI04-R1-I14
Rule ID ordering never chooses semantic winner.

NI04-R1-I15
NI-04A-CODE implements the one reusable production matcher kernel.

NI04-R1-I16
Tests invoke the production matcher; no divergent test-only rule engine exists.

NI04-R1-I17
NI-04A-CODE has no Admin Service API/UI and no Device summary aggregation.

NI04-R1-I18
Main NI-04 must reuse NI-04A artifact/matcher semantics unchanged.

NI04-R1-I19
NI-01/NI-02B schemas and NI-03 semantics remain unchanged.

NI04-R1-I20
Failure of any NI-04 artifact/reader/matcher remains isolated from Portal/Auth/CAPPORT/NI-03.
```

---

# 16. R1 P1 CLOSURE REGISTER

```text
P1-01
STATUS = PASS
REPAIR = explicit non-Coder TASK-DTI-NI-04K before bundle-dependent implementation

P1-02
STATUS = PASS
REPAIR = full manifest schema + exact canonical serialization/digests/version/expiry/ref rules

P1-03
STATUS = PASS
REPAIR = DNS-connected recognition reserved/not active; direct SNI only for positive V1

P1-04
STATUS = PASS
REPAIR = exact static reject set + explicit ambiguity_group_id runtime ambiguity

P1-05
STATUS = PASS
REPAIR = exact stage/module ownership + required reusable production matcher kernel
```

Open findings:

```text
OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0
```

---

# 17. REQUIRED GOVERNANCE AFTER TECH LEAD R1 REVIEW

If Tech Lead accepts this v1-R1:

```text
STEP 1
Tech Lead / Owner
→ authorize TASK-DTI-NI-04K research/admission only

STEP 2
Research/QA or designated Technical Researcher
→ collect evidence and candidate bundle

STEP 3
Architect
→ semantic admission decision against this contract

STEP 4
Tech Lead
→ independent NI-04K acceptance

STEP 5
Owner
→ authorize exact admitted bundle for implementation use

STEP 6
Tech Lead
→ issue exact TASK-DTI-NI-04A-CODE implementation contract

STEP 7
Owner
→ explicit Coder authorization

STEP 8
Coder
→ NI-04A-CODE only

STEP 9
Tech Lead
→ independent implementation/admission review

STEP 10
only after NI-04A PASS
→ exact main NI-04 product implementation TASK
```

No authorization is inherited across steps.

---

# 18. FINAL R1 STATUS

```text
TASK =
TASK-DTI-NI-04

ARCHITECTURE CONTRACT =
v1-R1

BASELINE HEAD =
e8061de9fbd6da8be5cd269779070a4db4d59d64

BASELINE TREE =
d5503fe1f2b5774bbe55cb2d34dba63246f56f6f

TECH LEAD R1 P1 REPAIRS =
5 / 5 CLOSED BY ARCHITECTURE

OPEN_P0 =
0

OPEN_P1 =
0

OPEN_P2 =
0

ARCHITECTURE_STATUS =
READY FOR TECH LEAD RE-REVIEW

SEMANTIC DESIGN =
PASS / COMPLETE

MANDATORY PRE-CODER RESEARCH/ADMISSION =
TASK-DTI-NI-04K

READY_FOR_TECH_LEAD_NI04K_TASK =
YES

READY_FOR_NI04A_IMPLEMENTATION_TASK =
NO — UNTIL NI-04K PASS + OWNER AUTHORIZATION

NI-04A CODER =
HOLD

MAIN NI-04 CODER =
HOLD

IMPLEMENTATION_AUTHORIZATION =
NO

PRODUCTION_CHANGE =
NO

FINAL EXECUTION STATUS =
ARCHITECTURE HOLD / PREREQUISITE REQUIRED
```

The HOLD is no longer caused by an unresolved architecture choice.
It is caused by the deliberately separate factual knowledge-admission prerequisite that prevents Coder from inventing production Service identity rules.

