# TASK-DTI-NI-04K — ARCHITECT HANDOFF DECISION R2
## TOP-50 exact-web-host semantic admission + bounded v1-R1 disposition

**Project:** CaptivPortal  
**Role:** Architect  
**Date:** 2026-10-12 (Asia/Baku)  
**Current repository baseline re-pinned:** `main@22cdde5d4168de02d142c840028a4d66167e47f7`  
**Architecture authority:** `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md` + normative `v1-R1` SHA-256 `788879cec606f88b13bcf3a759dc19dd68eebe426e5584a727a4e6aa66d1a17e`  
**Implementation authorization:** NO  
**Production/Git/network mutation:** NO

---

## 1. Executive decision

This decision keeps the original V1 recognition boundary: a positive Service result may be supported only by an admitted direct TLS/QUIC SNI rule over authoritative Site+Device-relative outbound/external evidence. Organization, Service and Service Category remain separate. DNS-only, IP-only, generic CDN/cloud, ECH/no-visible-SNI and parent-organization ownership never resolve an exact Service.

TOP-50 row disposition:

```text
ACCEPTED_HOST_AND_TAXONOMY = 40
RESEARCH_REPAIR             = 1   # ChatGPT category only
HOLD                        = 9   # current research candidate remains insufficient
ACTIVE_RUNTIME_RULES_ADDED  = 0
```

The 40 accepted rows are **semantic host/taxonomy approvals only**. They are not yet NI-04K production knowledge rules because the TOP-50 dossier is not an immutable `RecognitionTaxonomyContractV1 + InitialRecognitionKnowledgeManifestV1 + RecognitionRuleSetV1` bundle with complete per-rule §2.4 evidence.

---

## 2. Bounded Lane A — original five-service v1-R1 repair

### 2.1 Semantic disposition

The bounded repair requested by `TASK-DTI-NI-04K-ARCHITECT-SEMANTIC-REVIEW-R1` is semantically sufficient: the missing YouTube same-Organization/different-Service negative must be `music.youtube.com`; adding that evidence vector does not require changing the runtime taxonomy, knowledge manifest or ruleset semantics.

From the previously supplied original v1 ZIP, Architect independently recomputed the three self-field-excluded semantic digests and confirmed:

```text
Taxonomy v1 = 7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278
Manifest v1 = 7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210
Ruleset v1  = 46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a
```

### 2.2 Integrity limitation of this handoff

The actual `NI04K-v1-R1-EVIDENCE-REPAIR/` bytes were **not included in the files handed to Architect in this turn**. Therefore Architect does not fabricate a byte-level comparison of the repaired fixture/package hashes.

Exact bounded disposition:

```text
V1_R1_REPAIR_SEMANTICS = PASS
ORIGINAL_RUNTIME_SEMANTIC_DIGESTS = VERIFIED
REPAIRED_PACKAGE_BYTE_IDENTITY = NOT_INDEPENDENTLY_VERIFIED_IN_THIS_HANDOFF
V1_R1_WHOLE_BUNDLE_FINAL_ADMISSION = HOLD until repaired package bytes are independently checked
```

This is not a new semantic REPAIR. It is an evidence/integrity input gate only. If the repaired package contains exactly the one added negative vector, updated evidence counts/hashes, and the three runtime semantic artifacts are byte-identical, the bounded Architect result becomes PASS without reopening the five rule semantics.

---

## 3. Frozen policy: what an exact web-host rule means

A first-party branded site can be sufficient for an exact `service_sni_exact` rule **only** when the exact hostname itself is a user-facing Service endpoint and the rule claim is limited to:

> a qualifying authoritative outbound TLS/QUIC connection exposed this admitted Service-specific web hostname.

It does **not** mean:

- the native mobile/desktop app was used;
- media was played;
- a message/call/order/search actually occurred;
- all traffic for that Service is observable;
- a marketing/download/corporate site is equivalent to in-app Service activity.

Therefore an `S`-grade first-party site can be semantically sufficient for a **web-host-only** rule when it is interactive and uniquely Service-specific. A marketing-only/download-only/multi-product corporate host is not sufficient merely because the brand owns it.

---

## 4. Taxonomy decisions

V1 already has a closed category set sufficient for this research. No new Architecture Contract version is required.

```text
TikTok                    -> category.social
ChatGPT                    -> category.other_supported
Google Gemini              -> category.other_supported
Claude                     -> category.other_supported
DeepSeek                   -> category.other_supported
Steam                      -> category.software_distribution
Epic Games Store           -> category.software_distribution
Birmarket / Tap.az /
Turbo.az / Lalafo.az /
Temu / Trendyol /
AliExpress                 -> category.other_supported
Oxu.az                     -> category.other_supported
Bolt / Wolt                -> category.other_supported
```

`category.other_supported` is used only for a specifically admitted known Service that does not fit another V1 category; it is never an unknown catch-all.

Adding new Services/Organizations to a concrete runtime taxonomy is still a semantic artifact content change and therefore requires a new `taxonomy_version` and digest. That is an artifact-version increment, **not** a new architecture-contract version. A future new category such as `category.ai_assistant` or `category.marketplace` would require taxonomy-version increment plus architecture/Tech Lead compatibility review; it is not needed for V1.

---

## 5. TOP-50 row-by-row semantic decisions

| # | Service | Decision | Host specificity | Exact host(s) allowed | Organization | Category | Same-Org negative | First-party site alone? | Architect note / required repair |
|---|---|---|---|---|---|---|---|---|---|
| 1 | YouTube | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.youtube.com | ACCEPT: Google | ACCEPT: category.video_streaming | YES — music.youtube.com | YES — for exact web-host identity only; never native-app/activity equivalence | Same-org negative music.youtube.com; web host not playback volume |
| 2 | TikTok | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.tiktok.com | ACCEPT: TikTok | ACCEPT: category.social | YES — shop.tiktok.com | YES — for exact web-host identity only; never native-app/activity equivalence | Category social vs video_streaming Architect choice; not native media CDN |
| 3 | WhatsApp | ACCEPTED_HOST_AND_TAXONOMY | PASS | web.whatsapp.com | ACCEPT: Meta | ACCEPT: category.messaging | YES — Meta sibling (e.g. www.facebook.com) | YES — for exact web-host identity only; never native-app/activity equivalence | WhatsApp mobile traffic / calls not inferred |
| 4 | Instagram | HOLD | HOLD | NONE | ACCEPT: Meta | ACCEPT: category.social | YES — Meta sibling required after host proof | NO — current candidate does not meet the web-endpoint proof rule | HOLD — no independently admitted first-party source in this candidate proving exact www.instagram.com as the Service web endpoint. Need an updated first-party hostname-specific source and Meta sibling negative; marketing/ownership evidence alone is insufficient. |
| 5 | Telegram | ACCEPTED_HOST_AND_TAXONOMY | PASS | web.telegram.org | ACCEPT: Telegram | ACCEPT: category.messaging | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Native MTProto traffic not inferable from web |
| 6 | Facebook | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.facebook.com | ACCEPT: Meta | ACCEPT: category.social | YES — messenger.com | YES — for exact web-host identity only; never native-app/activity equivalence | Messenger and Instagram negative; login does not prove social activity |
| 7 | ChatGPT | RESEARCH_REPAIR | PASS | chatgpt.com | ACCEPT: OpenAI | REPAIR → category.other_supported: category.other_supported | YES — platform.openai.com (different OpenAI service surface) | YES — for exact web-host identity only; never native-app/activity equivalence | RESEARCH_REPAIR — host→Service and Organization PASS, but primary category MUST be category.other_supported for V1 consistency with Gemini/Claude/DeepSeek. No new category is needed. |
| 8 | Spotify | ACCEPTED_HOST_AND_TAXONOMY | PASS | open.spotify.com | ACCEPT: Spotify | ACCEPT: category.audio_streaming | NO | YES — for exact web-host identity only; never native-app/activity equivalence | No assertion that audio bytes used this host |
| 9 | Netflix | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.netflix.com | ACCEPT: Netflix | ACCEPT: category.video_streaming | NO | YES — for exact web-host identity only; never native-app/activity equivalence | CDN/media hostnames distinct |
| 10 | Pinterest | ACCEPTED_HOST_AND_TAXONOMY | PASS | pinterest.com | ACCEPT: Pinterest | ACCEPT: category.social | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Marketing and pin-CDNs excluded |
| 11 | Roblox | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.roblox.com | ACCEPT: Roblox | ACCEPT: category.gaming | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Game servers, games and platform sessions are not proven |
| 12 | Snapchat | ACCEPTED_HOST_AND_TAXONOMY | PASS | web.snapchat.com | ACCEPT: Snap | ACCEPT: category.social | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Currently redirects to www.snapchat.com/web; runtime SNI only if actually observed |
| 13 | Facebook Messenger | ACCEPTED_HOST_AND_TAXONOMY | PASS | messenger.com | ACCEPT: Meta | ACCEPT: category.messaging | YES — www.facebook.com | YES — for exact web-host identity only; never native-app/activity equivalence | Facebook messages also exist on facebook.com; no all-Messenger-traffic claim |
| 14 | Discord | ACCEPTED_HOST_AND_TAXONOMY | PASS | discord.com | ACCEPT: Discord | ACCEPT: category.messaging | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Does not prove calls/voice app network flow |
| 15 | Twitch | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.twitch.tv | ACCEPT: Twitch | ACCEPT: category.video_streaming | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Exact www host not explicitly required by browser-help; CDN video separate |
| 16 | X | HOLD | HOLD | NONE | ACCEPT: X | ACCEPT: category.social | NO | NO — current candidate does not meet the web-endpoint proof rule | HOLD — current candidate grade H. Architect web re-check found X Help explicitly naming x.com, so repair is narrow: update evidence source/claim to that first-party material, regenerate evidence identity, then re-review exact x.com. |
| 17 | Google Drive | ACCEPTED_HOST_AND_TAXONOMY | PASS | drive.google.com | ACCEPT: Google | ACCEPT: category.cloud_storage | YES — docs.google.com | YES — for exact web-host identity only; never native-app/activity equivalence | Drive vs Google Docs/Meet/Google auth sibling negatives |
| 18 | Microsoft Teams | ACCEPTED_HOST_AND_TAXONOMY | PASS | teams.microsoft.com | ACCEPT: Microsoft | ACCEPT: category.productivity_collaboration | YES — Microsoft sibling required (OneDrive is suitable after its evidence repair) | YES — for exact web-host identity only; never native-app/activity equivalence | Meeting media/microsoft telemetry excluded |
| 19 | Zoom | ACCEPTED_HOST_AND_TAXONOMY | PASS | join.zoom.us | ACCEPT: Zoom | ACCEPT: category.productivity_collaboration | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Only join portal, not media transfer or full Zoom app |
| 20 | LinkedIn | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.linkedin.com | ACCEPT: LinkedIn | ACCEPT: category.social | NO — primary Organization is LinkedIn, not Microsoft parent | YES — for exact web-host identity only; never native-app/activity equivalence | LinkedIn authentication and ads separate |
| 21 | Threads | ACCEPTED_HOST_AND_TAXONOMY | PASS | threads.com | ACCEPT: Meta | ACCEPT: category.social | YES — www.facebook.com or another admitted Meta sibling | YES — for exact web-host identity only; never native-app/activity equivalence | Do not silently admit old threads.net |
| 22 | Reddit | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.reddit.com | ACCEPT: Reddit | ACCEPT: category.social | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Media/CDN and third-party embeds not inferred |
| 23 | VK | HOLD | HOLD | NONE | HOLD — operator provenance required: VK | ACCEPT: category.social | NO on current org model; HOLD for operator proof | NO — current candidate does not meet the web-endpoint proof rule | HOLD — exact vk.com and primary service-operator provenance were not independently established from an accessible first-party source in this candidate. Need first-party service-host proof plus operator identity. |
| 24 | Signal | HOLD | HOLD | NONE | ACCEPT: Signal | ACCEPT: category.messaging | NO | NO — current candidate does not meet the web-endpoint proof rule | HOLD — signal.org is a marketing/download site, not a browser messaging endpoint. Need a first-party-proven direct SNI hostname used by the Signal messaging service, or a future separately admitted non-SNI signal. |
| 25 | Viber | HOLD | HOLD | NONE | ACCEPT: Rakuten Viber | ACCEPT: category.messaging | NO — primary Organization is Rakuten Viber | NO — current candidate does not meet the web-endpoint proof rule | HOLD — www.viber.com is product/marketing/download content, not a Viber web-messaging endpoint. Need a first-party-proven service-use hostname from the actual Viber client path; do not map marketing visits to messaging use. |
| 26 | Microsoft OneDrive | HOLD | HOLD | NONE | ACCEPT: Microsoft | ACCEPT: category.cloud_storage | YES — teams.microsoft.com | NO — current candidate does not meet the web-endpoint proof rule | HOLD — candidate has no exact host. Architect web re-check found Microsoft first-party evidence for OneDrive.com and OneDrive endpoint documentation including onedrive.live.com. Next candidate should choose one exact service-use host (recommended onedrive.live.com), update evidence, and add Microsoft sibling negative. |
| 27 | Dropbox | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.dropbox.com | ACCEPT: Dropbox | ACCEPT: category.cloud_storage | YES — Dropbox sibling product/infrastructure negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Dropbox has multiple documented domains; only this exact host proposed |
| 28 | Google Meet | ACCEPTED_HOST_AND_TAXONOMY | PASS | meet.google.com | ACCEPT: Google | ACCEPT: category.productivity_collaboration | YES — drive.google.com | YES — for exact web-host identity only; never native-app/activity equivalence | Video/voice transport domains excluded |
| 29 | Google Docs | ACCEPTED_HOST_AND_TAXONOMY | PASS | docs.google.com | ACCEPT: Google | ACCEPT: category.productivity_collaboration | YES — drive.google.com | YES — for exact web-host identity only; never native-app/activity equivalence | Docs and Drive remain distinct services despite shared storage |
| 30 | Google Gemini | ACCEPTED_HOST_AND_TAXONOMY | PASS | gemini.google.com | ACCEPT: Google | ACCEPT: category.other_supported | YES — docs.google.com | YES — for exact web-host identity only; never native-app/activity equivalence | Provisional other_supported category needs Architect admission |
| 31 | Claude | ACCEPTED_HOST_AND_TAXONOMY | PASS | claude.ai | ACCEPT: Anthropic | ACCEPT: category.other_supported | YES — Anthropic developer-platform sibling negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Other_supported category requires Architect admission; API excluded |
| 32 | DeepSeek | ACCEPTED_HOST_AND_TAXONOMY | PASS | chat.deepseek.com | ACCEPT: DeepSeek | ACCEPT: category.other_supported | YES — platform.deepseek.com | YES — for exact web-host identity only; never native-app/activity equivalence | AI product taxonomy decision; API excluded |
| 33 | Apple Music | ACCEPTED_HOST_AND_TAXONOMY | PASS | music.apple.com | ACCEPT: Apple | ACCEPT: category.audio_streaming | YES — Apple sibling Service negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Do not extrapolate native Apple Music/CDN media |
| 34 | SoundCloud | ACCEPTED_HOST_AND_TAXONOMY | PASS | soundcloud.com | ACCEPT: SoundCloud | ACCEPT: category.audio_streaming | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Domain choice bare vs www redirect confirmed only for landing |
| 35 | YouTube Music | ACCEPTED_HOST_AND_TAXONOMY | PASS | music.youtube.com | ACCEPT: Google | ACCEPT: category.audio_streaming | YES — www.youtube.com | YES — for exact web-host identity only; never native-app/activity equivalence | Mandatory negative for normal YouTube; sibling Google service |
| 36 | Prime Video | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.primevideo.com | ACCEPT: Amazon | ACCEPT: category.video_streaming | YES — Amazon sibling Service negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Amazon/AWS/CDN not inferred; region-dependent domains |
| 37 | Disney+ | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.disneyplus.com | ACCEPT: Disney | ACCEPT: category.video_streaming | YES — Disney sibling Service negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Streaming content may be elsewhere; web host only |
| 38 | Steam | ACCEPTED_HOST_AND_TAXONOMY | PASS | store.steampowered.com | ACCEPT: Valve | ACCEPT: category.software_distribution | NO under current org/service scope | YES — for exact web-host identity only; never native-app/activity equivalence | Steam client/games traffic not inferred; category vs gaming Architect choice |
| 39 | Epic Games Store | ACCEPTED_HOST_AND_TAXONOMY | PASS | store.epicgames.com | ACCEPT: Epic Games | ACCEPT: category.software_distribution | YES — Epic sibling Service negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Fortnite/Unreal/Epic login distinct services |
| 40 | Birmarket | ACCEPTED_HOST_AND_TAXONOMY | PASS | birmarket.az | ACCEPT: Birmarket | ACCEPT: category.other_supported | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Marketplace taxonomy vs other_supported Architect decision |
| 41 | Tap.az | ACCEPTED_HOST_AND_TAXONOMY | PASS | tap.az | ACCEPT: Tap.az | ACCEPT: category.other_supported | NO under proposed separate Organization taxon | YES — for exact web-host identity only; never native-app/activity equivalence | Same link family Turbo.az should not be conflated |
| 42 | Turbo.az | ACCEPTED_HOST_AND_TAXONOMY | PASS | turbo.az | ACCEPT: Turbo.az | ACCEPT: category.other_supported | NO under proposed separate Organization taxon | YES — for exact web-host identity only; never native-app/activity equivalence | Related Tap.az links do not prove same Service |
| 43 | Lalafo.az | ACCEPTED_HOST_AND_TAXONOMY | PASS | lalafo.az | ACCEPT: Lalafo | ACCEPT: category.other_supported | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Other_supported category requires Architect decision |
| 44 | Oxu.az | ACCEPTED_HOST_AND_TAXONOMY | PASS | oxu.az | ACCEPT: Oxu.az | ACCEPT: category.other_supported | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Other_supported category decision and editorial content not inferred |
| 45 | Yandex Search | ACCEPTED_HOST_AND_TAXONOMY | PASS | yandex.com | ACCEPT: Yandex | ACCEPT: category.web_search | YES — Yandex sibling Service negative required | YES — for exact web-host identity only; never native-app/activity equivalence | Other Yandex services and region hosts not inferred |
| 46 | Temu | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.temu.com | ACCEPT: Temu | ACCEPT: category.other_supported | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Other_supported commerce category decision; payment/CDN separate |
| 47 | Trendyol | ACCEPTED_HOST_AND_TAXONOMY | PASS | www.trendyol.com | ACCEPT: Trendyol | ACCEPT: category.other_supported | NO | YES — for exact web-host identity only; never native-app/activity equivalence | Marketplace taxonomy decision and region/redirect handling |
| 48 | AliExpress | HOLD | HOLD | NONE | ACCEPT: AliExpress | ACCEPT: category.other_supported | NO — primary Organization is AliExpress in this proposal | NO — current candidate does not meet the web-endpoint proof rule | HOLD — www.aliexpress.com could not be independently verified from an accessible first-party source in the candidate/review path. Need first-party exact-host evidence (official help/terms/security page is sufficient) before admission. |
| 49 | Bolt | HOLD | HOLD | NONE | ACCEPT: Bolt | ACCEPT: category.other_supported | YES — Bolt is explicitly multi-service | NO — current candidate does not meet the web-endpoint proof rule | HOLD — bolt.eu is a multi-product Bolt super-app/corporate surface (rides, food, drive, market, micromobility, business). Need a precise Service scope and a service-specific user endpoint; generic bolt.eu must not mean 'ride used'. |
| 50 | Wolt | HOLD | HOLD | NONE | ACCEPT: Wolt | ACCEPT: category.other_supported | YES if future Service scope splits Wolt sub-services; otherwise define service.wolt as broad platform | NO — current candidate does not meet the web-endpoint proof rule | HOLD — candidate did not freeze an exact host or Service scope. wolt.com is an interactive consumer ordering platform, but the next candidate must explicitly define service.wolt as the broad Wolt consumer platform (not 'food delivery only') and bind exact wolt.com before admission. |

---

## 6. Nine HOLD rows — exact repair requirements

### 04. Instagram

HOLD — no independently admitted first-party source in this candidate proving exact www.instagram.com as the Service web endpoint. Need an updated first-party hostname-specific source and Meta sibling negative; marketing/ownership evidence alone is insufficient.

### 16. X

HOLD — current candidate grade H. Architect web re-check found X Help explicitly naming x.com, so repair is narrow: update evidence source/claim to that first-party material, regenerate evidence identity, then re-review exact x.com.

Current independent Architect re-check found first-party X Help material explicitly instructing use of `x.com`/`x.com/login`. This is suitable repair evidence, but the current immutable research candidate must be regenerated rather than silently upgraded in place.

### 23. VK

HOLD — exact vk.com and primary service-operator provenance were not independently established from an accessible first-party source in this candidate. Need first-party service-host proof plus operator identity.

### 24. Signal

HOLD — signal.org is a marketing/download site, not a browser messaging endpoint. Need a first-party-proven direct SNI hostname used by the Signal messaging service, or a future separately admitted non-SNI signal.

### 25. Viber

HOLD — www.viber.com is product/marketing/download content, not a Viber web-messaging endpoint. Need a first-party-proven service-use hostname from the actual Viber client path; do not map marketing visits to messaging use.

### 26. Microsoft OneDrive

HOLD — candidate has no exact host. Architect web re-check found Microsoft first-party evidence for OneDrive.com and OneDrive endpoint documentation including onedrive.live.com. Next candidate should choose one exact service-use host (recommended onedrive.live.com), update evidence, and add Microsoft sibling negative.

Current independent Architect re-check found Microsoft first-party material that identifies OneDrive.com and an official OneDrive endpoint list containing `onedrive.live.com`. Prefer `onedrive.live.com` for a future direct Service-use exact rule; do not equate generic Microsoft identity hosts with OneDrive.

### 48. AliExpress

HOLD — www.aliexpress.com could not be independently verified from an accessible first-party source in the candidate/review path. Need first-party exact-host evidence (official help/terms/security page is sufficient) before admission.

### 49. Bolt

HOLD — bolt.eu is a multi-product Bolt super-app/corporate surface (rides, food, drive, market, micromobility, business). Need a precise Service scope and a service-specific user endpoint; generic bolt.eu must not mean 'ride used'.

### 50. Wolt

HOLD — candidate did not freeze an exact host or Service scope. wolt.com is an interactive consumer ordering platform, but the next candidate must explicitly define service.wolt as the broad Wolt consumer platform (not 'food delivery only') and bind exact wolt.com before admission.

Current independent Architect re-check confirms `wolt.com` is an interactive consumer ordering surface. A future repaired candidate may use exact `wolt.com` only if `service.wolt` is explicitly defined as the broad Wolt consumer platform; it must not be presented as proof of a specific food-delivery/mobile-app action.

---

## 7. Packaging / immutable bundle sequencing

### 7.1 Immediate next production-knowledge proposal

The immediate next immutable production-knowledge proposal remains the **repaired original five-service v1** only:

```text
YouTube
WhatsApp
Telegram
Spotify
Netflix
```

Reason: these are the only Services for which a complete per-rule evidence package and exact runtime artifact tuple already exist, subject only to the bounded repaired-package byte verification above.

### 7.2 Recommended first TOP-50 expansion batch

After Lane A is independently closed, prepare one new immutable candidate adding the following five low-ambiguity, documentary-evidence Services:

```text
TikTok      -> www.tiktok.com        -> category.social
Pinterest   -> pinterest.com          -> category.social
Snapchat    -> web.snapchat.com       -> category.social
Discord     -> discord.com            -> category.messaging
Zoom        -> join.zoom.us           -> category.productivity_collaboration
```

This is a **research/admission packaging recommendation**, not activation authorization. Every added rule must receive its own positive evidence refs, near-match negative, shared-infrastructure negative where applicable, same-Organization/different-Service negative where applicable, review dates, canonical manifest refs and regenerated artifact digests.

Do not reuse an already-issued immutable candidate identity/version from the separately prepared unadmitted `NI04K-RESEARCH-CANDIDATE-v2`. The researcher must allocate the next unused artifact versions and return the exact ID/version/digest tuple for review.

The remaining semantically accepted TOP-50 rows should follow in later immutable batches; there is no architectural benefit in manufacturing one 40-rule runtime bundle before each rule has a complete §2.4 evidence pack.

---

## 8. Privacy and false-positive boundary — mandatory

The following can never by themselves resolve an exact Service in V1:

```text
peer IP / IP ownership
ASN / cloud / CDN ownership
DNS-only name
DNS→IP correlation
shared parent Organization
generic authentication/login infrastructure
ECH / no visible SNI
local/inbound/wrong-device edge
marketing/download site when the claim is native-app Service use
```

A recognized web hostname is evidence only for that exact observed web endpoint. Native app coverage remains unknown unless separately admitted direct evidence exists.

---

## 9. Governance verdict

```text
TASK = TASK-DTI-NI-04K

CURRENT_BASELINE = main@22cdde5d4168de02d142c840028a4d66167e47f7

LANE_A_V1_R1_SEMANTIC_REPAIR = PASS
LANE_A_REPAIRED_PACKAGE_BYTE_VERIFICATION = HOLD_INPUT_NOT_SUPPLIED

TOP50_HOST_TAXONOMY_SEMANTIC_ACCEPT = 40
TOP50_RESEARCH_REPAIR = 1
TOP50_HOLD = 9
TOP50_ACTIVE_RUNTIME_RULES_ADDED = 0

ARCHITECTURE_CONTRACT_VERSION_CHANGE = NO
FUTURE_RUNTIME_TAXONOMY_VERSION_INCREMENT = YES when bundle content changes

OPEN_ARCH_P0 = 0
OPEN_ARCH_P1 = 0
OPEN_ARCH_P2 = 0

INDEPENDENT_TECHLEAD_ADMISSION = REQUIRED
OWNER_EXACT_BUNDLE_APPROVAL = REQUIRED
NI04A_CODER = HOLD
MAIN_NI04_CODER = HOLD
IMPLEMENTATION_AUTHORIZATION = NO
PRODUCTION_CHANGE = NO
GIT_MUTATION_AUTHORIZATION = NO
```

Architect semantic review of the TOP-50 research dossier is complete. No TOP-50 runtime artifact is admitted merely by this decision.
