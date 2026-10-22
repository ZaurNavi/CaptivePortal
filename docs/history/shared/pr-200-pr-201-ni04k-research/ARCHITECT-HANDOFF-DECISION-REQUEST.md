# CaptivPortal / TASK-DTI-NI-04K — ARCHITECT HANDOFF, 2026-10-12

## Owner directive

Research the full approved 50-service *priority candidate list* in one package, rather than introducing Services one by one. This is **research authorization only** and cannot authorize Coder/production actions.

## Inputs and precedence

1. `NI04K-SERVICE-DISCOVERY-TOP50-v1.md` — 50 priority names and AZ guest-Wi-Fi rationale; order is not observed popularity.
2. `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md` + normative `v1-R1` addendum; `v1-R1` contract SHA-256: `788879cec606f88b13bcf3a759dc19dd68eebe426e5584a727a4e6aa66d1a17e`.
3. `TASK-DTI-NI-04K-ARCHITECT-SEMANTIC-REVIEW-R1` on 5-rule v1 — one specific missing YouTube Music negative fixture; no rejection of semantic rule identity.
4. `NI04K-RESEARCH-CANDIDATE-v2` is separately prepared TikTok expansion, not covered by original review.

## Delivered, separate lanes

**Lane A — BOUNDED REPAIR of original v1 (5 services):** `NI04K-v1-R1-EVIDENCE-REPAIR/`. Adds the one missing negative fixture `music.youtube.com`, updates the evidence count 33→34 and re-hashes mutable evidence files. The original three recognition runtime artifacts are byte-identical. This is the direct response to Architect R1 and is ready for **bounded re-review** (not for Coder). It does not add TikTok or a sixth Service.

**Lane B — complete TOP-50 research screen:** `ARCHITECT-RESEARCH-REPORT-TOP50-R2.md` + `SERVICE-EVIDENCE-MATRIX-v1.{csv,json}` + `PROPOSED-NEGATIVE-FIXTURES-RESEARCH-v1.json`. Every service has at least a first-party evidence locator or an explicit evidence gap, category/organization proposal, SNI hostname candidate (or NONE), limitations and independent review state. No new semantic runtime taxonomy/manifest/ruleset has been fabricated or admitted. The 189 fixtures are **research proposals**, not executable production matching tests.

## Decisions requested from Architect

1. **Bounded R1:** return PASS / REPAIR / REJECT for the five-rule **v1-R1 evidence-only repair**; verify all three original hashes remain the same. Do not confuse with v2 or TOP50.
2. **TOP50:** for each row return host→Service specificity verdict; Organization and Category acceptance; exact host(s) allowed; semantic need for a same-Org different-Service negative; whether first-party site alone suffices to allow that exact web host (NOT native app). For unresolved 9, return HOLD / precise missing evidence.
3. **Taxonomy question:** one primary category for TikTok, AI assistants, Steam, marketplaces, local news, Bolt/Wolt, without silently inventing categories; decide whether a new architecture version is needed.
4. **Packaging:** specify subset for the next immutable *versioned* production knowledge proposal; do not request a 50-rule activation unless EVERY accepted rule satisfies NI-04K §2.4 with provenance and signed-off evidence. Support incremental batches under immutable versioning.
5. **Privacy:** forbid exact Service from IP, DNS-only, generic CDN, no-SNI/ECH, shared parent organization; forbid marketing website equivalence to mobile in-app usage.

## Formal status

```
TOP50_PUBLIC_WEB_IDENTITY_RESEARCH = COMPLETE (50/50 REVIEWED)
TOP50_D=23; TOP50_S=18; TOP50_H=9
TOP50_ARCHITECT_REVIEW_CANDIDATES=41 (NOT ADMITTED)
TOP50_RESEARCH_HOLD=9
TOP50_NEW_ACTIVE_RUNTIME_BUNDLE=NONE
V1_R1_MISSING_FIXTURE=REPAIRED_FOR_BOUNDED_RE-REVIEW
V1_R1_ARCHITECT_RE-REVIEW=PENDING
TOP50_ARCHITECT_SEMANTIC_ADMISSION=PENDING
INDEPENDENT_TECHLEAD_ADMISSION=PENDING
OWNER_EXACT_BUNDLE_APPROVAL=PENDING
NI04A_CODER=HOLD
MAIN_NI04_CODER=HOLD
PRODUCTION_AND_GIT_MUTATIONS=NONE
```
