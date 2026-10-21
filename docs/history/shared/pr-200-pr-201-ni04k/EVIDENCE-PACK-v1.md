# CaptivPortal · TASK-DTI-NI-04K
## Initial recognition knowledge — RESEARCH CANDIDATE v1

**Prepared:** 2026-10-11 UTC / 2026-10-12 Asia/Baku  
**Governance:** Research/admission only, NOT an Architect/Tech Lead/Owner-admitted production bundle  
**Normative contracts:** original `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md`; `v1-R1` addendum, SHA-256 `788879cec606f88b13bcf3a759dc19dd68eebe426e5584a727a4e6aa66d1a17e`  
**Repo baseline inspected:** `main@22cdde5d4168de02d142c840028a4d66167e47f7` (Traffic-only delta from Architect pin `e8061de9`)

## 1. Admission policy

This candidate supplies **exact SNI hostnames only**. `service_sni_exact` is used rather than any domain-wide suffix. The only permitted positive evidence is an independently established authoritative `Site+Device+event_time` outbound external NI-02B edge with NI-01 `tls_sni`/`quic_sni` in `observed_retained` state, and a valid active, unexpired rule. There are no host patterns for generic infrastructure, no DNS-connected positive rules, and no IP-only inferences.

A match supports a conservative product claim: **a qualifying network connection displayed the admitted service-specific TLS/QUIC SNI hostname**. It does **not** prove a video was watched, a message was exchanged, a user deliberately opened the app, or that *all* activity of that service is observable. Requests can be background/automated, and HTTPS ECH, QUIC variants and SNI omissions may hide evidence.

## 2. Sources indexed in InitialRecognitionKnowledgeManifestV1

| Knowledge ref | Source class / first-party publisher | Exact original URL and supported claim |
|---|---|---|
| `knowledge.google.youtube.host` | first_party_public / Google YouTube Help | https://support.google.com/youtube/answer/171780?hl=en — Google documents `https://www.youtube.com` as a YouTube player-host URL and distinguishes `youtube-nocookie.com`. |
| `knowledge.google.youtube.operator` | first_party_public / Google | https://about.google/products/ — Google lists YouTube, YouTube Kids and YouTube Music as separate Google products. |
| `knowledge.meta.whatsapp.host` | first_party_public / WhatsApp Help Center | https://faq.whatsapp.com/668538004658079/?cms_platform=windows-desktop&locale=ja_JP — WhatsApp directs browser users to `web.whatsapp.com`. |
| `knowledge.meta.whatsapp.operator` | first_party_public / Meta Newsroom | https://about.fb.com/news/2026/09/introducing-meta-one-subscription-service-more-features-ai/ — Meta identifies WhatsApp, Instagram, Facebook as distinct Meta app/products. |
| `knowledge.telegram.web.host` | first_party_public / Telegram Web | https://web.telegram.org/?lang=ru — official Telegram Web login is located on `web.telegram.org`. |
| `knowledge.telegram.apps.operator` | first_party_public / Telegram | https://telegram.org/apps — Telegram explicitly identifies its official WebA/WebK applications. |
| `knowledge.spotify.web.host` | first_party_public / Spotify Support | https://support.spotify.com/us/article/web-player-help/ — Spotify support explicitly documents `open.spotify.com` as the Spotify Web Player hostname. |
| `knowledge.spotify.service` | first_party_public / Spotify Support | https://support.spotify.com/az-az/article/what-is-spotify/ — Spotify describes the Service, including music and podcasts; this supports the taxonomy description. |
| `knowledge.netflix.web.host` | first_party_public / Netflix Help Center | https://help.netflix.com/en/node/133134 — Netflix tells users to navigate to `www.netflix.com` in their browser. |

**Methodology:** each original publisher page was examined via public search/opened retrieved content on 2026-10-11 UTC. Search-result snippets alone were not used as admission authority. This archive records URLs and relevant semantic claims, **not** byte-for-byte independently archived HTTP response bodies. Content and identity are therefore subject to Architect review and source re-check at admission. No real device traffic, personal identifiers, client DNS logs or SNI were collected for this research.

**Review window:** `reviewed_at_utc=2026-10-11T20:04:00.000000Z` and `review_due_at_utc=2027-01-09T20:04:00.000000Z` (90 days) are candidate metadata; Architect/Owner can reject the times before admission. Earliest source, manifest, or rule expiry wins, with no grace period.

## 3. Proposed real Service rules

| Rule ID | Hostname / kind | Target and taxonomy | Positive rationale | Key negative examples |
|---|---|---|---|---|
| `rule.youtube.www_sni` | `www.youtube.com`, `service_sni_exact` | `service.youtube` → `org.google` → `category.video_streaming` | Official YouTube Help uses exact `www.youtube.com` YouTube player hostname, separate from other Google services. | `accounts.google.com`, `music.youtube.com`, `notwww.youtube.com`, any generic Google CDN/IP must NOT mean YouTube. |
| `rule.whatsapp.web_sni` | `web.whatsapp.com`, `service_sni_exact` | `service.whatsapp` → `org.meta` → `category.messaging` | WhatsApp first-party help identifies exact WhatsApp Web entry hostname; Meta confirms distinct product identity. | `www.instagram.com`, `facebook.com`, `notweb.whatsapp.com`, `.whatsapp.net`/other unrelated Meta hostnames must NOT mean WhatsApp. |
| `rule.telegram.web_sni` | `web.telegram.org`, `service_sni_exact` | `service.telegram` → `org.telegram` → `category.messaging` | Official Telegram Web login and Telegram first-party apps page confirm Telegram web client identity. | `notweb.telegram.org`, `telegram.org`, `webk.telegram.org` do not match this **exact** rule. |
| `rule.spotify.open_sni` | `open.spotify.com`, `service_sni_exact` | `service.spotify` → `org.spotify` → `category.audio_streaming` | Spotify support instructs users to use `open.spotify.com` for Web Player. | `notopen.spotify.com`, `spotify.com`, generic CDN/hosting IP do not match this rule. |
| `rule.netflix.www_sni` | `www.netflix.com`, `service_sni_exact` | `service.netflix` → `org.netflix` → `category.video_streaming` | Netflix official help instructs users to enter `www.netflix.com`. | `notwww.netflix.com`, `netflix.com` apex, CDN IP alone do not match this exact rule. |

The listed alternate official service domains are excluded **intentionally**, not classified as another Service: an exact-match-only admission favours avoiding false positives over maximizing apparent coverage. Different hostname rules could be researched and separately admitted later.

## 4. Evidence fixtures and semantics

`research-fixtures-v1.json` contains **33 synthetic fixtures**:
- **10 positive**: five exact hostnames × TLS and QUIC synthetic qualifying authoritative outbound/external edge context. These are *expected* outputs, not actual production captures.
- **10 near-match / parent-host negatives**: the parent-only hostname and a `not` prefixed hostname for each Service. These intentionally do not match exact rules.
- **5 DNS-only negatives**: correct-looking DNS query plus unspecified answers without direct admitted SNI cannot resolve Service.
- **8 additional negatives**: shared Meta, shared Google, shared CDN, peer-IP-only, ECH/SNI absent, local edge, inbound edge, and incorrect Site/Device attribution.

**Critical limitations:** the research fixture file does not instantiate the NI-02B/NI-01 actual reader and does not execute the future production matcher. Such technical integration is expressly reserved for `NI-04A-CODE`; no separate production-equivalent matcher is introduced during this research stage.

**Ambiguity:** no active rules share an exact matcher-key; therefore there is *no admitted runtime ambiguity group in this first candidate*. The R1 rule for explicit deliberate ambiguity remains normative for future bundles. Admitting intentionally ambiguous rule pairs as artificial "coverage" is not required.

## 5. Bundle integrity outcomes

Offline checks (research-only generator, not product runtime):

- R1 §3.14 **all 3 synthetic reference SHA-256** reproduced independently: PASS.
- Candidate taxonomy, manifest, ruleset: canonical JSON with sorted arrays and object keys, exact bytes: PASS.
- Bundle ID/version/digest references: PASS against this local candidate.
- 5 Service IDs, 5 matching Service rules, 9 first-party knowledge sources: structural checks PASS.
- Rule/source/manifest timestamps and due-time precedence: candidate checked, strict exact due-time rejection probed.
- 19 **bounded invalid-artifact probes**: research harness rejected each expected-invalid mutation. These probes are a subset of the complete mandatory NI-04A validation matrix, NOT a claim that production artifact validation is implemented or tested.

Refer to `offline-validation-summary.json`, `SHA256SUMS.txt` and the actual three `.json` artifact files for exact digests.

## 6. Open research / governance gates

1. **Architect semantic admission = PENDING** (independent examination of hostname specificity, taxon owner, negative evidence, source provenance and exact research bundle; may narrow/reject individual proposals).
2. **Independent Tech Lead NI-04K bundle review = PENDING**. The assistant prepared this researcher candidate and cannot credibly claim its own self-review is independent.
3. **Owner exact bundle approval = PENDING**. General permission to start this research is **not** permission to admit these exact rules for implementation.
4. Original external content preservation has URL+claim+UTC review time but no immutable primary webpage snapshot. An independent source verification/review is required before admitted production use.
5. The bundle has not been tested on actual Suricata/NI-01/NI-02B client edges. No claim of real traffic coverage or playback/message detection is made.

**NI-04K = RESEARCH CANDIDATE PREPARED / ADMISSION HOLD. NI-04A-CODE = HOLD. Main NI-04 = HOLD. Production mutations = NONE. GitHub mutations = NONE.**
