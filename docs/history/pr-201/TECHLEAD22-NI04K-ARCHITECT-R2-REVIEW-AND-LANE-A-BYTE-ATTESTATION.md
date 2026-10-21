# CaptivPortal — TechLead22 / NI-04K Architect R2 review and Lane A byte attestation

Date: 2026-10-12 (Asia/Baku)  
Architect input: `TASK-DTI-NI-04K-ARCHITECT-HANDOFF-DECISION-R2(1).md`  
Repository baseline from Architect: `main@22cdde5d4168de02d142c840028a4d66167e47f7` (not repinned live as part of this offline review).

## 1. R2 disposition: ACCEPTED AS GOVERNANCE INPUT

- TOP-50 host/taxonomy **semantic acceptance 40**, **Research Repair 1** (ChatGPT primary V1 category -> `category.other_supported`), **Research HOLD 9** (Instagram, X, VK, Signal, Viber, OneDrive, AliExpress, Bolt, Wolt).
- All 40 accepted are **web-host/taxonomy semantics only**, not admitted runtime rules.
- Original Lane A five-rule evidence repair must be admitted first; new expansion batch afterward: TikTok, Pinterest, Snapchat, Discord, Zoom.
- For TikTok the Architect category is **`category.social`**, overriding the unadmitted prior TikTok v2 candidate's `video_streaming` taxonomy. Reusing old v2 artifact version/digest is forbidden.
- No semantic rule may claim native app use, streaming/media transfer, actual messaging, or full Service coverage from exact SNI web host alone.

## 2. Lane A — actual repaired package byte inspection (LOCAL INDEPENDENT RECOMPUTATION)

Compared the original `NI04K-RESEARCH-CANDIDATE-v1` to research-provided `NI04K-v1-R1-EVIDENCE-REPAIR` and to **new, provenance-aligned copy** `NI04K-LANE-A-BOUNDED-REPAIR-FOR-ARCHITECT-R3`.

**PASS / observed:**
- Three runtime semantic JSON artifacts are **byte-identical across all three**. No version increments and no new rule.
- Recomputed self-field-excluded canonical SHA-256 identities independently, 3/3 PASS:
  - taxonomy v1: `7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278`
  - knowledge manifest v1: `7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210`
  - ruleset v1: `46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a`
- `research-fixtures-v1.json`: 33 -> 34 vectors, ten positive and 24 negative. All original 33 vectors, schema note and 19 invalid-artifact probe declarations are **identical**, with **exactly one** added vector: `negative.same_org.youtube_music` (TLS SNI `music.youtube.com`, expected `no_service_resolution`). This is fixture-set comparison, not execution of the future production matcher.
- Prior repaired package itself: all ten entries in its SHA256SUMS.txt match their actual local files.

**One package documentation inconsistency was identified and corrected in a NEW copy:** the researcher-modified Evidence Pack had changed the Netflix source URL from `https://help.netflix.com/en/node/133134` (exact URL in unchanged manifest and original Evidence Pack) to `/134134`. The latter was not verified via public browse; `/133134` is an accessible first-party Netflix help page that explicitly names `www.netflix.com`. The new R3 handoff copy restores `/133134` **in the Evidence Pack only** and regenerates its file checksum. There is no semantic artifact change.

**Independent final Architect admission is not self-declared.** Architect R2 explicitly held the missing byte evidence. This package supplies that evidence for bounded Architect re-review. After independent Architect PASS, the separate independent Tech Lead **knowledge-admission** gate and Owner authorization for exact ID/version/digest are still required. Technical byte attestation != production admission.

## 3. Gate decisions

```text
ARCHITECT_R2_DISPOSITION = RECEIVED / ACCEPTED AS INPUT
LANE_A_REPAIRED_BYTES = VERIFIED IN THIS OFFLINE REVIEW
LANE_A_RUNTIME_JSON_BYTE_IDENTITY = PASS
LANE_A_CANONICAL_SEMANTIC_DIGESTS = 3/3 PASS
LANE_A_ONLY_NEW_FIXTURE = negative.same_org.youtube_music
LANE_A_RESEARCH_PACKAGE_NETFLIX_LOCATOR_MISMATCH = CORRECTED IN NEW COPY
LANE_A_ARCHITECT_FINAL_BOUNDED_ACCEPTANCE = PENDING RE-REVIEW
NI04K_COMPLETE_KNOWLEDGE_ADMISSION = HOLD
TOP50_40_SEMANTICS = ACCEPTED_BY_ARCHITECT_NOT_RUNTIME_ADMITTED
TOP50_NEXT_BATCH = TIKTOK/PINTEREST/SNAPCHAT/DISCORD/ZOOM, RESEARCH ONLY
NI04A_CODER = HOLD
MAIN_NI04_CODER = HOLD
PRODUCTION_GIT_NETWORK_MUTATIONS = NONE
```

## 4. Requested Architect action

Independently inspect `NI04K-LANE-A-BOUNDED-REPAIR-FOR-ARCHITECT-R3.zip` (all source bytes enclosed); compare exact 34th YouTube Music negative against previous 33, confirm all three JSON byte hashes and semantic digests unchanged, and return precise bounded **PASS/REPAIR/REJECT** for Lane A. Do not conflate this with the unadmitted TOP-50 expansion. No Coder task or production deployment.
