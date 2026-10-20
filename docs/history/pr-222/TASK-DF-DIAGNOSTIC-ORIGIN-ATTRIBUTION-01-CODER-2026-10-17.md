# TASK-DF-DIAGNOSTIC-ORIGIN-ATTRIBUTION-01 — Coder implementation contract

**Project:** CaptivPortal / Device Fingerprint / Admin Web
**Date:** 2026-10-17 (Asia/Baku)
**Status:** TECH LEAD TASK / IMPLEMENTATION CANDIDATE — Coder may prepare isolated PR; production/deployment HOLD.
**Source baseline observed:** `/opt/CaptivePortal` on production HEAD `cd83c3e04233593126d247b0c96c1135f4233072`, clean worktree at 20:27 Baku. Re-pin `origin/main` before implementation. No hard-coded previous HEAD in production behavior.
**Priority:** P2 diagnostic accuracy. Not a correctness failure of authoritative classification claims.

## Verified defect

Current `app/device_fingerprint/origin_assessment.py`:
- In `DeviceFingerprintOriginAssessmentBuilder.build`, `mac_registry` reads K4 freshness for `manufacturer_family` and appends `knowledge_source_expired` to the **origin-wide** `explanations` array when expired.
- The same array is passed to `_reduce_claims` **for all four** dimensions (`platform_family`, `device_class`, `manufacturer_family`, `model_family`).
- `app/device_fingerprint/fusion.py:DeviceFingerprintFusionCore._dimension` further unions `explanation_codes` across all six origins, including non-supporting ones.
- `app/admin_web/device_fingerprint_presentation.py` passes flat `explanation_codes` unchanged; `app/admin_web/static/admin.js:fingerprintDetailEntries` displays the code next to a `resolved` value without identifying its origin.

Real production provenance: Satori K1 retrieved `2026-10-01T06:34:49.000Z`, K4 IEEE retrieved `2026-10-01T09:50:30.800Z`. Evaluating on 2026-10-16: Satori K1 is fresh (365-day fresh / 730-day expiry windows in admitted `satori_dhcp` policy), whereas K4 is expired (2-day fresh / 7-day expiry policy). The displayed `device_class=smartphone`, `platform=android` with DHCP support AND `knowledge_source_expired` is consistent with a **K4 warning propagated to other dimensions**, not an expired K1 claim. This is a diagnostic attribution defect/misleading UI. DO NOT remove K4 expiry or downgrade a supported K1 result.

## Scope and requirements

1. Preserve byte-for-byte semantics of frozen R14 `ClassificationResult`, all `DimensionResult` statuses, support levels, claims, exact `explanation_codes`, `knowledge_references`, selection matrices, source freshness/admission and persisted artifacts. This task must **not** change `origin_assessment.py`, `fusion.py`, admissible knowledge/policy, existing database schema, or classification algorithm.
2. Improve **Device Card → Fingerprint details** such that explanation codes visibly distinguish **why the selected value is supported** from **diagnostic information about other origins**. A global `knowledge_source_expired` must NOT be presented as proof that the selected DHCP claim used expired source knowledge.
3. Prefer per-origin diagnostic attribution from the retained *immutable* `OriginAssessment` artifacts referenced by the authoritative persisted `ClassificationResult` (six origins). If an additive Device Card read-model is necessary, use a bounded Site/MAC-scoped, read-only artifact lookup, validate IDs/digests/references, and avoid N+1 on lists. Never re-run classification/freshness or scan raw evidence at render time. If per-origin lookup is not practical without changing frozen read contracts, use a clearly worded diagnostic disclaimer and report the unresolved attribution gap to Tech Lead rather than inventing provenance.
4. Keep canonical value, status, support_level, supporting/contradicting/not-evaluable groups and full engineering `knowledge_references` accessible. Preserve exact IDs/digests; never count seven K1 matching record references from one Satori provenance as seven independent knowledge sources.
5. Clearly identify that `classified_at_utc` represents last retained classification, **not a live assessment**. Do not invent a stale threshold or live producer health in this task.
6. No effect on Home/Online Devices selection precedence, current device read contracts except explicitly additive optional diagnostic data, Guest Auth, CAPPORT, Omada, background classification, Sensor, Evidence, or systemd.
7. Safe failure: malformed/missing diagnostic artifact must not turn into guessed values, must not break the core Device Card, and must not leak data across Sites. Report diagnostic-unavailable explicitly.

## Required reproducible tests

- Fixture A: fresh Satori K1 DHCP yields `android`/`smartphone`; expired K4 yields `knowledge_source_expired` in non-supporting MAC origin. Card indicates `resolved` with truthful DHCP support and **separately labeled K4 expired diagnostic**; no claim downgrade.
- Fixture B: actually expired K1 DHCP yields no K1 claim, appropriate unresolved/other-origin outcome and K1 expired diagnostic; do not mask genuine expiry.
- Fixture C: seven K1 records sharing one provenance are not displayed or counted as seven independent sources.
- Fixture D: absent/corrupt OriginAssessment, Site/MAC mismatch, unknown classification, unsupported case: bounded failure, no guessing/no cross-Site leak.
- Fixture E: `Home` compact table and existing API consumers remain unchanged; no N+1/raw-evidence read.
- Focused Python + JS tests; independent full regression gates requested after isolated PR. No production mutation.

## Coder handoff format

Submit one isolated PR with exact changed-file inventory, targeted RED→GREEN tests, source pin/HEAD/TREE, performance/read-count evidence, screenshots or DOM test demonstrating source attribution, security/isolation review and rollback plan. No automatic merge or deploy. If solving properly requires changing frozen R14 claim/explanation semantics, STOP and request a formal frozen-contract change decision (Owner + Architect + Tech Lead); do not perform it in this PR.
