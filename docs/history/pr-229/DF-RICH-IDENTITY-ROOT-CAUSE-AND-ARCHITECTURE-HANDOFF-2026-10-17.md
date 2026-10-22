# Device Fingerprint rich identity — root cause and architecture handoff

**Status:** Investigation completed; architectural extension required for richer canonical classification. **No authorization to modify frozen R14 classification semantics or production.**
**Date:** 2026-10-17 (Asia/Baku).

## Actual production findings (read-only)

- Production checkout HEAD `cd83c3e04233593126d247b0c96c1135f4233072`, classification SQLite `/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3`: 2,000 retained PRODUCTION classifications; newest at `2026-10-16T18:46:33.892Z` (22:46 Baku). Not evidence of real-time classification on 2026-10-17.
- At 20:27 Baku: `fingerprint-sensor.service`, `fingerprint-evidence.service`, `fingerprint-classification.service` inactive and disabled; `fingerprint-suricata.service` failed after TERM during shutdown at 15:06 and disabled. Establish whether this is an operator safety hold; do not re-enable without explicit production GO.
- Production Evidence DB `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3`: last 500 ingress rows comprise tcp_syn=269, tls_client=157, quic_client=59, dhcp=15; last observed through 2026-10-16T18:49Z.
- From the **200 newest** `source_kind='portal_headers'` rows in Site `6a64f17630da7c70d232187a`, **all 200 are schema v1**; **119** have a non-null normalized `model_family` and **198** have a non-null `os_major`. This is *observed feature availability in a bounded sample*, not proof of model accuracy/coverage across all devices. No guest identifiers were exported.
- Repo `tests/device_fingerprint/test_portal_schema.py:payload_v2()` contains valid normalized proof fixture `model_family='Nokia G21'`, `os_major=13`, model source `sec_ch_ua_model`, OS source `sec_ch_ua_platform_version`; `test_payload_integrity.py` confirms byte integrity/materialization. This proves schema support, **NOT** Fusion's willingness to make semantic model/OS-version claims.

## Existing capability ceilings (code-verified)

- `app/device_fingerprint/k1_satori_import.py`: K1 Satori maps Android/iOS/Windows/macOS/ChromeOS/Linux and smartphone/tablet/laptop only; model/brand is not automatically projected.
- `app/device_fingerprint/k2b_p0f_import.py`: K2B p0f semantic claims are `platform_family` only; a non-match cannot identify manufacturer or model.
- `app/device_fingerprint/k3_portal_rules.py:build_k3_portal_rule_set_v1`: 13 conservative K3 rules (12 platform-family rules, one tablet form-factor rule). It intentionally has synthetic `unknown_model_ua.no_claim` and `unknown_model_ch.no_claim` vectors. It does not claim `model_family` from normalized `model_family` nor emit `os_major`/Android-version identity.
- `app/device_fingerprint/k4_ieee_import.py`: initial `manufacturer_mapping` is null by contract; MAC assignment organization is NOT device manufacturer; randomized MAC introduces additional limits.
- `tls_client`, `quic_client`/JA4: V1 structurally evaluable, not semantic platform/brand/model classifiers under R14.
- R14 classifier's four authoritative dimensions are platform_family, device_class, manufacturer_family, model_family. Android **major version** is not currently an authoritative dimension. These are approved conservative choices, not a missing SQL field or broken display.

## Provenance/explanation finding

The `knowledge_source_expired` displayed next to resolved DHCP results originates from the expired independent K4 IEEE provenance (retrieved 2026-10-01, 7-day expiry), while K1 Satori (retrieved 2026-10-01, 730-day expiry) is fresh. `origin_assessment.py` shares an origin-wide explanation array into all four dimensions, then `fusion.py` unions all origins; Card shows flat `explanation_codes`. The source-specific attribution/UI correction is covered by separate implementation task `TASK-DF-DIAGNOSTIC-ORIGIN-ATTRIBUTION-01`.

## Architecture decisions required for richer fingerprints (NO CODER FEATURE IMPLEMENTATION YET)

A. **Two separate product surfaces:** (1) canonical **verified** Classifier result (remains R14 authoritative), (2) *Observed Device Hints* with explicit `source`, `evidence_schema`, `observed_at`, `capture_quality`, `trust/certainty` and non-authoritative meaning. Do not silently upcast untrusted UA/Client Hints `model_family` into verified manufacturer/model.

B. Decide whether to introduce **explicit OS-major observation** (e.g., Android 13, iOS major) in the read model, separately from canonical `platform_family`, including evidence strength, spoofing/privacy, conflict and retention rules. Existing model/`os_major` normalized fields allow an MVP based on already retained data if the architecture accepts the distinction, without new packet capture.

C. For new canonical manufacturer/model classification: define curated/versioned alias/taxonomy mapping from admissible model hints, confidence thresholds, conflict resolution across portal/DHCP/MAC/K2, provenance, rejection for unknown ambiguous strings, pinned test vectors, admission rules and rollback. Do not infer manufacturer directly from MAC assignment organization and do not treat seven Satori rules as independent votes.

D. Explicitly address whether `portal_headers/2` production producer/admission should be enabled: last 200 sample rows were all v1, while test v2 fixture supports detailed CH. This is a separate telemetry-producer/admission and compatibility decision; do not turn it on blindly.

E. Owner-device live acceptance: after separate authorization, use only user's own Nokia phone with stable MAC; randomized MAC series separately; capture/compare available v1/v2 normalized hints and persisted claim lineage; demonstrate correct source attribution. No random visitors/staff for destructive or privacy-sensitive tests.

F. Preserve no-guessing, privacy, Site boundary, immutable evidence/provenance and full R14 frozen-contract change control. Architect + Tech Lead + Owner approval needed before adding/modifying classifier rules or persisted semantics; then prepare a separate implementation TASK for Coder, comprehensive RED/GREEN tests and a nonproduction gate.

## Disposition

1. **P2 presentation/diagnostic bug:** Coder implementation candidate, separately documented.
2. **P1 operational missing live fingerprint pipeline:** Not a classification-code regression proven by this investigation; services currently disabled/stopped. Requires operator policy/health diagnosis and explicit production GO before reactivation.
3. **Product capability gap:** Rich data are captured (at least in a recent bounded v1 sample), but current approved classifier intentionally declines model/OS-major semantics. Architecture extension, then Coder implementation; do not mislabel this as a hotfix or invent detail.
