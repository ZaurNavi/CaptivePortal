# TASK-DTI-NI-04K — ARCHITECT SEMANTIC ADMISSION REVIEW R1

**Role:** CaptivPortal Architect  
**Review date:** 2026-10-12  
**Review scope:** semantic knowledge admission only; no code, Git, runtime, network, systemd or production action  
**Candidate:** `NI04K-RESEARCH-CANDIDATE-v1`  
**Normative parent:** `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md`  
**Normative R1 SHA-256:** `788879cec606f88b13bcf3a759dc19dd68eebe426e5584a727a4e6aa66d1a17e`  
**Candidate repo baseline:** `main@22cdde5d4168de02d142c840028a4d66167e47f7`  

## 1. Executive disposition

```text
rule.youtube.www_sni  = REPAIR
  semantic host→Service mapping = PASS
  taxonomy mapping = PASS
  admission fixture coverage = REPAIR (one missing mandatory same-organization/different-Service negative)

rule.whatsapp.web_sni = PASS
rule.telegram.web_sni = PASS
rule.spotify.open_sni = PASS
rule.netflix.www_sni  = PASS

WHOLE BUNDLE = REPAIR
REPAIR CLASS = BOUNDED ADMISSION-EVIDENCE REPAIR ONLY
REJECT = NO
```

The candidate is not rejected. The three runtime semantic artifacts are internally consistent and their proposed Service mappings are conservative. One R1-required per-rule evidence class is not actually instantiated for YouTube: a multi-Service/same-Organization negative. The Evidence Pack names `music.youtube.com` as a negative example, but `research-fixtures-v1.json` does not contain that vector. Because Google explicitly presents YouTube and YouTube Music as distinct products, this is an applicable R1 §2.4 fixture and must be present before semantic admission.

No taxonomy, manifest or ruleset semantic change is required to repair this finding.

## 2. Independent candidate identity / integrity check

The exact candidate artifacts reviewed are:

| Artifact | Version | Candidate semantic SHA-256 | Independent recomputation |
|---|---:|---|---|
| `captivportal.network-intelligence.recognition-taxonomy` | 1 | `7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278` | PASS |
| `captivportal.network-intelligence.recognition-knowledge` | 1 | `7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210` | PASS |
| `captivportal.network-intelligence.service-recognition` | 1 | `46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a` | PASS |

Independent SHA-256 recomputation followed R1 §3.10–§3.11: canonical JSON, UTF-8, sorted object keys, existing canonical arrays, and removal of only the artifact's own digest field. All three digests reproduce exactly.

Current GitHub `main` independently rechecked during review is still `22cdde5d4168de02d142c840028a4d66167e47f7`; the commits after the previous NI pin are the accepted Traffic Partial Coverage lane and do not alter this candidate's semantic basis.

## 3. Normative admission rules applied

This review applies the following parent/R1 constraints:

- Organization, Service and Service Category are distinct taxonomic dimensions.
- One Service maps to exactly one primary Organization and one primary Service Category.
- A direct SNI Service rule is admissible only when the hostname is sufficiently Service-specific that an authoritative exact Site+Device outbound external TLS/QUIC SNI match supports that Service identity.
- Search-result snippets, common knowledge, IP ownership, shared CDN ownership and Coder inference are not admission authority.
- Active V1 positive recognition is direct TLS/QUIC SNI only.
- Active DNS-connected rules are forbidden in V1.
- IP-only Service rules are not admitted.
- Exact rules are allowed to be deliberately narrow. False-negative coverage is not a requirement for initial admission.
- Per active Service rule, R1 requires positive evidence, near-match negative evidence, shared-infrastructure negative evidence where applicable, and multi-Service same-Organization negative evidence where applicable.
- Runtime ambiguity fixtures are required only for an actually admitted deliberate same-matcher ambiguity group; artificial ambiguity need not be manufactured when no active matcher key collides.

## 4. Rule-by-rule semantic decisions

### 4.1 `rule.youtube.www_sni` — REPAIR

**Matcher:** exact `www.youtube.com`  
**Target:** `service.youtube` → `org.google` → `category.video_streaming`

#### Semantic mapping: PASS

Current first-party evidence independently supports the mapping:

- YouTube Help, `https://support.google.com/youtube/answer/171780`, documents embedded YouTube video/player URLs under `https://www.youtube.com/...` and separately identifies `youtube-nocookie.com` for privacy-enhanced embedding.
- Google, `https://about.google/products/`, lists YouTube, YouTube Kids and YouTube Music as distinct Google products.

Therefore exact SNI `www.youtube.com` is Service-specific enough for the conservative V1 claim `service.youtube`. It is not a generic Google infrastructure hostname.

`org.google` is correct as the primary Organization. `category.video_streaming` is correct as the primary V1 category: the admitted hostname is first-party documented as the YouTube video/player host. This taxonomy assignment does not claim that every connection proves playback or that YouTube has no non-video features.

#### Admission evidence: REPAIR

R1 §2.4 requires a multi-Service/same-Organization negative where applicable. It is applicable here because the same first-party Google source explicitly lists YouTube and YouTube Music as distinct products.

The Evidence Pack itself names:

```text
music.youtube.com
```

as a negative example, but the actual `research-fixtures-v1.json` contains only:

```text
notwww.youtube.com
youtube.com
accounts.google.com
```

for the relevant YouTube near/parent/shared-Google classes. `accounts.google.com` is useful shared-Organization infrastructure evidence, but it is not the required different-Service sibling fixture.

**Required bounded repair:** add exactly one synthetic negative fixture proving that `music.youtube.com` does not match `rule.youtube.www_sni` and does not resolve `service.youtube` under this exact rule.

Recommended exact vector:

```json
{
  "case_id": "negative.same_org.youtube_music",
  "expected": "no_service_resolution",
  "expected_service_id": null,
  "observed_hostname": "music.youtube.com",
  "rule_id": null,
  "signal_family": "tls_sni",
  "source": "synthetic_no_direct_admitted_service_evidence"
}
```

One TLS vector is sufficient for this knowledge-admission negative because the matcher semantic is hostname-exact and the positive matrix already covers both TLS and QUIC. No duplicate QUIC negative is required by R1.

### 4.2 `rule.whatsapp.web_sni` — PASS

**Matcher:** exact `web.whatsapp.com`  
**Target:** `service.whatsapp` → `org.meta` → `category.messaging`

Current first-party evidence independently supports all three relations:

- WhatsApp Web itself states that WhatsApp Web is used by going to `web.whatsapp.com` from a computer browser.
- WhatsApp's current product pages describe WhatsApp as messaging/calling and explicitly identify WhatsApp Web as the browser/desktop experience.
- Meta's current first-party material lists WhatsApp, Instagram and Facebook as distinct apps/products in the Meta family; current Meta material also treats WhatsApp separately from Instagram/Facebook account/app settings.

Therefore exact `web.whatsapp.com` supports the WhatsApp Service, not Instagram, Facebook or generic Meta infrastructure. `org.meta` is the correct primary Organization for taxonomy purposes. `category.messaging` is the correct primary category.

The current fixture set includes a distinct same-Organization negative (`www.instagram.com`) and therefore satisfies the R1 multi-Service/same-Organization class for this rule.

### 4.3 `rule.telegram.web_sni` — PASS

**Matcher:** exact `web.telegram.org`  
**Target:** `service.telegram` → `org.telegram` → `category.messaging`

Current first-party Telegram evidence supports the mapping:

- `https://telegram.org/apps` lists Telegram WebA and Telegram WebK as official Telegram web applications.
- Telegram's own Web application is hosted under `web.telegram.org`; official Telegram material identifies WebA/WebK paths on that host.
- `https://telegram.org/` and the Telegram FAQ describe Telegram as a messaging application/service.

Thus exact `web.telegram.org` is directly attributable to Telegram and is not a generic hosting hostname. `org.telegram` and `category.messaging` are appropriate primary taxonomy mappings.

The exact rule intentionally does not admit sibling/alternate hostnames unless separately researched. That is valid V1 narrowing, not a defect.

### 4.4 `rule.spotify.open_sni` — PASS

**Matcher:** exact `open.spotify.com`  
**Target:** `service.spotify` → `org.spotify` → `category.audio_streaming`

Spotify's current first-party support page for the web player explicitly references `open.spotify.com` and exposes it as the Spotify Web Player destination. Its current "What is Spotify?" material describes Spotify as a digital music, podcast and video service and emphasizes music/podcast access and playback.

Therefore exact `open.spotify.com` is uniquely Spotify Service evidence rather than generic hosting.

`org.spotify` is correct. `category.audio_streaming` is accepted as the required single **primary** V1 category. This does not assert that Spotify has no video feature or that every `open.spotify.com` connection carries audio; category assignment is a Service taxonomy property, not a per-connection content classifier.

### 4.5 `rule.netflix.www_sni` — PASS

**Matcher:** exact `www.netflix.com`  
**Target:** `service.netflix` → `org.netflix` → `category.video_streaming`

Netflix Help currently instructs users to type `www.netflix.com` in the browser address bar. Netflix's current first-party service description says Netflix is a streaming service for TV shows and movies.

Therefore exact `www.netflix.com` is Service-specific enough for `service.netflix`; `org.netflix` and `category.video_streaming` are appropriate primary mappings.

## 5. Deliberately omitted domains/suffixes — PASS

The candidate intentionally admits only five exact SNI hosts and no suffix rules. This is correct for initial V1 admission.

The architecture requires trustworthy positive evidence, not exhaustive recognition. Therefore omitted official sibling domains, CDNs, apex domains, app-specific hostnames and suffixes remain `unknown` unless separately researched and admitted. Their omission creates false negatives by design but does not create false positives.

No omitted domain should be added merely to improve apparent coverage.

## 6. Synthetic fixtures — REPAIR, narrowly

The 33 supplied vectors otherwise form an appropriate NI-04K knowledge-admission matrix:

- 10 direct positive vectors: 5 exact hosts × TLS/QUIC;
- 10 near-match/parent negatives;
- 5 DNS-only negatives;
- shared Meta, shared Google, shared cloud, peer-IP-only, ECH/no-SNI, local edge, inbound edge and wrong-device negatives.

They are correctly described as **expected semantic vectors**, not production matcher integration tests. NI-04A-CODE remains responsible for executing the accepted vectors through the production artifact validator/matcher kernel.

### Missing mandatory fixture

Only one required class is missing:

```text
YouTube / Google:
explicit different-Service same-Organization negative
```

Add `music.youtube.com` as specified in §4.1.

### Ambiguity fixture

No additional ambiguity vector is mandatory for this candidate because:

```text
all five active matcher keys are distinct
ambiguity_group_id = null for every rule
no intentional same-matcher ambiguity is admitted
```

R1 requires deliberate ambiguity to be represented when it exists; it does not require fabricating an ambiguity group for coverage.

## 7. Source provenance / immutable webpage snapshots — PASS, no repair

Immutable byte-for-byte webpage snapshots are **not** a V1/R1 admission requirement for `first_party_public` knowledge sources.

The frozen schema requires:

```text
source_class
publisher_or_owner
source_locator
claim_summary
reviewed_at_utc
review_due_at_utc
```

and independent admission of provenance. `controlled_owner_trace` is an alternative source class, not a mandatory companion to `first_party_public`.

During this Architect review, the first-party claims were independently re-checked against current public publisher material. The five host→Service claims and Organization/Category semantics are still supported.

Therefore do **not** add a new snapshot/archive prerequisite to NI-04K. If a future source becomes unavailable or materially changes, the existing review/expiry/update governance is the appropriate mechanism.

## 8. Review windows / Organization naming — PASS

Candidate timestamps:

```text
reviewed_at_utc = 2026-10-11T20:04:00.000000Z
review_due_at_utc = 2027-01-09T20:04:00.000000Z
```

The 90-day window is valid and more conservative than the V1 maximum of 365 days. Exact-equality expiry and earliest-source/manifest/rule precedence remain normative.

Organization identifiers/display names are adequate:

```text
org.google   / Google
org.meta     / Meta
org.telegram / Telegram
org.spotify  / Spotify
org.netflix  / Netflix
```

No legal-entity suffix is required by `OrganizationTaxonV1`; the taxon represents the primary service operator, not a corporate-registry record.

## 9. Inherited v1 + R1 safety constraints — PASS

The candidate preserves the accepted V1/R1 safety envelope:

```text
active rules = 5
active service_sni_exact = 5
active SNI suffix = 0
active DNS-connected = 0
IP-only rules = 0
organization-only active rules = 0
ambiguity groups = 0
```

It does not infer Service from:

```text
DNS alone
DNS→IP correlation
peer IP
shared CDN/cloud
same Organization alone
ECH/no visible SNI
local/inbound/wrong-device edge context
```

No client traffic or personal SNI was used in candidate research.

## 10. Exact repair package

The next candidate should be a bounded evidence-package repair, for example:

```text
NI04K-RESEARCH-CANDIDATE-v1-R1
```

Required changes only:

1. Add `negative.same_org.youtube_music` to `research-fixtures-v1.json` with the exact semantics in §4.1.
2. Update the Evidence Pack fixture counts from 33 to 34 and negative count from 23 to 24.
3. Update `offline-validation-summary.json`, `SHA256SUMS.txt`, handoff/package identity and any fixture-file hash references affected by that added vector.
4. Re-run the existing research-only structural/offline checks.

### Runtime semantic artifacts MUST remain unchanged

Because this repair changes admission evidence only and does **not** change taxonomy, knowledge-manifest or ruleset semantics, do not manufacture a no-op runtime artifact version bump.

The corrected candidate is expected to retain exactly:

```text
Taxonomy v1
7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278

Manifest v1
7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210

Ruleset v1
46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a
```

If any of those three semantic artifacts is changed for another reason, then the R1 version/digest rules apply and a new exact artifact identity must be produced.

## 11. Final governance verdict

```text
TASK = TASK-DTI-NI-04K

ARCHITECT SEMANTIC REVIEW = COMPLETE

RULE DECISIONS:
  rule.youtube.www_sni  = REPAIR
    host/service/taxonomy semantics = PASS
    fixture evidence = REPAIR
  rule.whatsapp.web_sni = PASS
  rule.telegram.web_sni = PASS
  rule.spotify.open_sni = PASS
  rule.netflix.www_sni  = PASS

WHOLE CANDIDATE BUNDLE = REPAIR
REPAIR SCOPE = ONE MISSING YOUTUBE SAME-ORG/DIFFERENT-SERVICE NEGATIVE FIXTURE
REJECT = NO

SOURCE SNAPSHOT PREREQUISITE = NO
NEW OWNER TRACE REQUIRED = NO
NEW HOSTNAME RULE REQUIRED = NO
NEW SUFFIX RULE REQUIRED = NO
NEW DNS RULE = NO
NEW IP RULE = NO

ARCHITECT OPEN_P0 = 0
ARCHITECT OPEN_P1 = 1
ARCHITECT OPEN_P2 = 0

NI-04K = HOLD pending bounded repaired candidate
NI-04A-CODE = HOLD
MAIN NI-04 = HOLD
IMPLEMENTATION AUTHORIZATION = NO
PRODUCTION CHANGE = NO
GITHUB MUTATION AUTHORIZATION = NO
```

After the bounded evidence repair, Architect re-review may be limited to verifying the new vector, updated fixture/package hashes/counts, and confirmation that the three runtime semantic artifacts remain byte-identical. Independent Tech Lead review and explicit Owner approval of the exact accepted IDs/versions/digests remain separate mandatory gates.
