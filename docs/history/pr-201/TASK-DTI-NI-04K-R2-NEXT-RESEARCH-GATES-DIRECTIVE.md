# CaptivPortal — TASK-DTI-NI-04K / Research gates following Architect R2

**Role:** TechLead22 / governance and research direction  
**Date:** 2026-10-12 (Asia/Baku)  
**Source:** `TASK-DTI-NI-04K-ARCHITECT-HANDOFF-DECISION-R2(1).md`  
**No implementation, Git, production, SPAN, controller, network, service or deployment change.**

## Gate 0 — Complete Lane A before expansion

- Input: `NI04K-LANE-A-BOUNDED-REPAIR-FOR-ARCHITECT-R3.zip` (contains bytes for Architect R2's `HOLD_INPUT_NOT_SUPPLIED`).
- Architect independently verify: only one synthetic fixture added (`negative.same_org.youtube_music`), 34 total; identical original Taxonomy/Knowledge Manifest/Ruleset bytes and digest identities; evidence and checksum consistency; Netflix source locator restored to original manifest URL.
- Required output: explicit Lane A bounded **PASS/REPAIR/REJECT** and exact package hash identity.
- If PASS: separate independent Tech Lead knowledge admission, then Owner authorization of the **exact** artifact IDs/versions/digests. No inherited implementation authorization.

## Gate 1 — Prepare next immutable expansion candidate, research/admission only

**Blocker:** do not allocate/finalize an expansion runtime package before Lane A admission process is complete.

Once eligible, make one **new** candidate containing the accepted Lane A services and exactly five extra rules from Architect R2:

| Service | exact host | approved primary category | mandatory consideration |
|---|---|---|---|
| TikTok | `www.tiktok.com` | `category.social` | same-org different-service negative `shop.tiktok.com` |
| Pinterest | `pinterest.com` | `category.social` | canonical apex and near-match; no blanket CDN/suffix |
| Snapchat | `web.snapchat.com` | `category.social` | possible web redirect; only actually observed SNI counts |
| Discord | `discord.com` | `category.messaging` | no claim of native voice/call/media traffic |
| Zoom | `join.zoom.us` | `category.productivity_collaboration` | joining portal only, not meeting media |

For **every** rule, require first-party/approved provenance, exact hostname claim, positive TLS/QUIC synthetic vectors, near-match negatives, CDN/shared infrastructure negatives where applicable, same-Organization other-Service negatives where applicable, rule/source review and expiry, taxonomy Organization/Service/Category correctness, canonical manifest, exact SHA256 and acceptance matrix under parent v1 + R1 §2.4.

- Production artifacts: `RecognitionTaxonomyContractV1`, `InitialRecognitionKnowledgeManifestV1`, `RecognitionRuleSetV1`; include all applicable **new** identity/version/digest triplets.
- Do **not** reuse `NI04K-RESEARCH-CANDIDATE-v2`'s unadmitted semantic version/identity or its `category.video_streaming` TikTok taxonomy. Exact future version allocation must be reviewed against admitted artifact registry/history.
- Do not infer native-app usage from exact browser host or DNS/IP/CDN/missing SNI.
- Production matcher, Admin UI and other code are not in this research task.

## Gate 2 — Parallel TOP-50 research disposition, no activation

- **ChatGPT:** narrow correction of primary category only -> `category.other_supported`; existing exact host `chatgpt.com` and Organization `OpenAI` accepted semantically in Architect R2. Refresh evidence candidate metadata only; do not silently mutate old immutable runtime artifacts.
- **Nine research HOLD rows:** Instagram (official exact web host + Meta-sibling negative), X (X Help first-party exact `x.com`), VK (verified first-party web endpoint/operator), Signal (real service-use client SNI rather than marketing), Viber (real messaging endpoint rather than marketing), OneDrive (Microsoft `onedrive.live.com` proof + sibling negative), AliExpress (official exact host), Bolt (specific product scope and endpoint), Wolt (explicit broad platform scope + exact consumer endpoint).
- Any row not meeting its proof remains HOLD. A completed TOP-50 screening is **not** completed runtime knowledge admission.

## Exit gates

```text
TOP50_ARCHITECT_SEMANTIC_APPROVED_HOSTS=40
TOP50_RESEARCH_REPAIR=1
TOP50_RESEARCH_HOLD=9
TOP50_NEW_RUNTIME_RULES_ADMITTED=0
LANE_A_ARCHITECT_BOUNDED_REVIEW=PENDING
NI04K_INDEPENDENT_TECHLEAD_KNOWLEDGE_ADMISSION=PENDING
OWNER_EXACT_BUNDLE_APPROVAL=PENDING
NI04A_CODER=HOLD
MAIN_NI04_CODER=HOLD
PRODUCTION_OR_GIT_CHANGE=NO
```
