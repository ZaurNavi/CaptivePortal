# TASK-DTI-NI-04-UNIFIED55-R7 — Coder: code only, no research

**Author / evidence owner:** TechLead22. **Date:** 2026-10-12. **Repository:** `ZaurNavi/CaptivePortal`.

**Base:** merged PR #200, exact `main@54ce5569b4799b097807399560badc2149c2502c` (the merged tree is `078ed0b107cbd4ca2fe2200add9973f35a683319`). Separate branch in Coder's Windows workspace. **No production operations.** Existing production remains on `22cdde5d4168de02d142c840028a4d66167e47f7` until one future joint deployment of both merges.

## 0. Strict boundary of Coder's job

Coder is NOT an investigator, reviewer, traffic analyst or Architect. **Coder must not:** search Google/web/GitHub for endpoints; choose Service IDs; guess DNS/IP/SNI; change a hostname; decide which source is admissible; request captures from live visitors; write a research report; assess §2.4 evidence; resolve historical Architect HOLDs; modify production, network, systemd or runtime env; analyze server load; or make security tradeoffs.

**Coder must only:** integrate exact supplied frozen TechLead artifacts/fixtures; implement the bounded necessary loader/wiring/tests in `app/network_service_recognition/` and existing Admin integration (only if justified); run local developer tests and prepare **one Dev Handoff** containing complete replacement patch, SHA-256, tree, file list and test results. Those are software delivery fields, **not research evidence**.

**Scope of original Owner goal:** 55 functioning Service recognitions, five merged + 50 additions, one correcting PR, then one combined production deployment. **TechLead finding:** with the currently approved direct-SNI-only V1 architecture, that goal is **not yet fully admissible**. This R7 does **not** rename 53 successes to 55 successes. Two blocked decisions (`service.messenger`, `service.viber`) belong solely to Tech Lead/Architect/Owner and are included here as explicit NOT-ADMITTED slots, not Coder research tickets. Coder can implement and test the deterministic 53-rule candidate now; the correcting PR and joint deployment remain blocked pending TechLead-owned final 55/55 admission. Do not silently activate experimental 55-rule prototype under `RESEARCH-ONLY-*`.

## 1. Frozen input bytes — copy, do not author

Exact files in this handoff:

- `recognition-taxonomy-v2.json`: version 2, 55 stable Service IDs, all ten allowed categories, preserves original five taxonomy semantics. SHA-256 `9dfc0a2ed699f09a4f70e32f30e2d259d96f0f70eb2e8eb06366e5198486c7ee`.
- `recognition-knowledge-manifest-v2.json`: version 2, 57 sources, 53 supportable exact-host hypotheses, SHA-256 `8f09b6cc685a103a9b4515367980ccefbaa9755a28134b9c6b184cad3e1834f3`.
- `recognition-ruleset-v2.json`: version 2, **53** active exact-SNI rules (the original five + 48 more), SHA-256 `595c6982ddf2625de1dbf0262a8da68e5e0cfcb12894a9883cf21bc63a226db8`.
- `TECHLEAD-55-HOST-DECISIONS.json` / `.csv`: authoritative ID/name/organization/category/host/evidence URL/source state and distinct-service negative hosts for all 55; these remain TechLead evidence, not a writable knowledge store.
- `TECHLEAD-55-SYNTHETIC-TEST-VECTORS.json`: **330 exact test expectations**: TLS-SNI and QUIC-SNI, host subdomain negatives, generic CDN negatives, DNS-only negatives, and same-Organization isolation.
- `TECHLEAD-RELEASE-BLOCKERS.json`: two TechLead-owned blockers; never reclassify these as active without an **additional replacement immutable bundle issued by TechLead**.
- `verify_techlead_payload_r7.py`: independent offline structural/digest oracle, a reference for checking transferred input files (not a replacement for real app tests).
- Historical original `recognition-*-v1.json` remain immutable. No modification to those bytes, the 55-row research registry SHA `70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7`, previous R3 evidence, or old tests/contract.

The *research-only 55-rule prototype* under `RESEARCH-ONLY-55-RULE-PROTOTYPE-NOT-FOR-RUNTIME/` is included as **a rejected comparison fixture**. It must never be selected by `load_local_bundle()` or installed in runtime. It demonstrably overclaims Messenger.com and Viber website.

## 2. Exact implementation instructions

1. Make a new branch from exact `main@54ce5569…`; no unrelated cherry-picks. Confirm existing R3 remains unchanged except strictly needed v2 loader selection and tests.
2. Place the three provided SHA-pinned v2 JSON files, byte for byte, in `app/network_service_recognition/knowledge/`, using their names verbatim. Do NOT generate these contents from guesses or mutable source registry.
3. Update only `load_local_bundle()` and, if necessary, minimal knowledge selection helper in `app/network_service_recognition/artifacts.py` to atomically use exactly taxonomy-v2 + knowledge-manifest-v2 + ruleset-v2. **Use existing `load_bundle()` validation.** Keep v1 files and rollback support. Do not add environment-controlled unreviewed knowledge paths, rule overrides, network fallback, runtime auto-refresh or silent subset loading. If any v2 artifact invalid or absent, NI-04 fails closed; Portal/Auth/CAPPORT/NI-03 remain unaffected.
4. Preserve one exact-SNI matcher, all fixed NI-01/NI-02B protected-readers, device/source/peer/transport provenance, 5000 facts, 25,000 scalars, 256 batch, 5-second deadline, 64 MiB incremental RSS, max 12 Recent Services, 16 KiB public envelope, no raw SNI/DNS/IP in Admin DTO, 120-second UI cadence. No second UI section, no write DB/schema/worker.
5. Match only qualifying direct retained outbound SNI with valid authoritative Site/Device binding. DNS-only, IP-only, wildcard guess, ECH without SNI and website-to-native-app inference remain forbidden. **All 55 taxonomy IDs remain stable; exactly 53 have eligible direct-SNI rules in this packet.** No silent inference of the other two.
6. Preserve `WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED=false` as default; no feature activation. Maintain existing NI-03 CSS suffix, DOM-less Node guard, protected auth and Site scoping.
7. Consume supplied `TECHLEAD-55-SYNTHETIC-TEST-VECTORS.json` as parameterized test oracle. Required 330/330 expected outcomes. `service.messenger` and `service.viber` direct-host positives are **NOT** authorized; those inputs must return unknown (unless they otherwise match a distinct, separately documented rule). In particular `www.facebook.com` cannot resolve `service.messenger`; it resolves Facebook only.
8. Test complete taxonomy set = 55 Registry55 IDs; unique exact hostname patterns for 53 active rules; 10-category closed vocabulary; byte-exact v1 frozen docs; SHA-pinned v2 raw + semantic hashes; all source refs and expiration; wrong-Site/wrong-Device/inbound/local/ECH/DNS-only fail-closed; same-Organization siblings correctly separated. Ensure loader rejects mixed-version bundles and unauthorized stale/unknown files.
9. Run focused tests, complete `tests/admin_web`, NI-03, protected reader/Portal/Auth/CAPPORT regressions, `compileall`/Node checks on Windows and native Linux *locally*. Do not test on production. Preserve recorded historical baseline-only SQLite 3.37.2 planner failures without relabeling them PASS.
10. Produce **one Dev Handoff**, not Research/QA/Architecture report. Its fields: base SHA, changed-file list, immutable input hashes, complete replacement patch path+SHA-256, candidate Git tree, test commands/results, known baseline exceptions, `SOURCE_CHANGED`, `COMMIT/PUSH/PR/PRODUCTION_ACTION=NO`. Stop for TechLead source review.

## 3. Frozen negative expectations / safety

- Same-org pairs: YouTube versus YouTube Music; Gmail versus Drive/Meet/Maps/Translate; Facebook versus Instagram/Threads/**Messenger unknown**; Teams versus OneDrive and Outlook.com; Signal `chat.signal.org` versus arbitrary `*.signal.org`; Google parent CDN not Service proof.
- `messenger.com` is a **retired web endpoint for standalone messaging** since April 2026; its presence in historical research is not an active Messenger-client proof. New Messenger web UI shares `www.facebook.com` with Facebook; encrypted HTTP path cannot be seen from V1 SNI. **No Messenger positive rule without separate TechLead replacement admission.**
- `www.viber.com` is official download/product website and `chatapi.viber.com` is a bot API, not evidence of private consumer messaging. Viber proprietary TCP cannot yield a proven direct TLS/QUIC SNI from the evidence gathered. **No Viber positive rule without separate TechLead replacement admission.**
- Bolt `mm-web.bolt.eu` is micromobility web access only, not ride-hailing or payment evidence. Signal `chat.signal.org` is an official Signal service-server URL, not proof of a message. Other exact web hosts prove web-host connections only, not the native application performing user actions.

## 4. Acceptance and deliverable definition

**Coder implementation DONE for this bounded handoff:** exact supplied 55-row taxonomy + 53 active admitted web-host identities, 330 synthetic expectations, all safe-fail and protected-reader contracts, one complete patch and standard Dev Handoff. **Coder does NOT submit missing evidence; does NOT solve recognition semantics.**

**Owner's original release goal NOT YET DONE:** 55 distinct services with actual supported active rules (including Messenger and Viber). That is a TechLead-owned blocked admission outside Coder discretion. There is NO Owner-authorized merge or production deployment for an incomplete 55/55 release. TechLead will issue replacement, fully pinned input data when and only when the two missing signal claims can be honestly supported. No work on CPU/load/other SysAdmin matters.

**One eventual code deployment:** after both PR #200 and the final corrected PR are fully accepted and merged, migrate production once from old `22cdde5d` to exact target SHA/tree. Keep flag OFF during code switch, wait up to 30 min for authentic readiness, check Portal/Auth/CAPPORT/Admin, rollback on failure; any later feature ON is separate Owner decision. No staged deployment of five alone.
