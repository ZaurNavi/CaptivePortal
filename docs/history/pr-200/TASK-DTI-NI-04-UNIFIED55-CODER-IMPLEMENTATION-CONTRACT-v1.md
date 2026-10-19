# TASK-DTI-NI-04-UNIFIED55-IMPLEMENTATION — Coder Contract v1
## One Coder TASK · One implementation branch/PR target · 55 distinct Service IDs · default OFF

**Issuing role:** CaptivPortal Technical Lead 22  
**Owner instruction:** combine original five and TOP-50 into one deliverable; waive an additional separate admission reviewer  
**Date:** 2026-10-12 (Asia/Baku)  
**Repository baseline:** `main@22cdde5d4168de02d142c840028a4d66167e47f7`, TREE `a783d1cb3b2f33107ba64878ae5d3d8b80463f38`  
**Mandatory repository governance:** `AGENTS.md`, `docs/agents/workflow.md`, `docs/agents/handoff.md` at the pinned commit  
**Architecture authority:** `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md` plus normative `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1-R1`, except Owner's explicitly documented consolidation of the execution/handoff into one Coder TASK.  
**Production mutations:** FORBIDDEN. **Feature flag default:** OFF. **Automatic merge/deploy:** NO.

# 0. Hard interpretation of 55 (MUST READ)

The five previously researched services are already in the original TOP-50. Duplicate Service IDs and duplicate `(matcher_key,target_key)` rules are forbidden by R1; **do not copy the five twice**. 55 UNIQUE Services = original TOP-50 + these five additional, independently named candidates: `Gmail`, `Google Maps`, `Google Translate`, `Outlook.com (consumer web)`, `Booking.com`. Exact unique IDs and first-party source locators are in `NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json`. Coder must NOT change these semantic choices.

The 55 registry entries are **catalog scope**, not 55 admitted Service rules. At handoff: original Lane A has five admitted-to-Owner reference rules, Architect R2 accepted host/taxonomy semantics for 40 of the original 50 (including the Lane A five), ChatGPT category repair is `category.other_supported`, 9 names are Architect HOLD, and the five extra names are research-only candidates. Coder must never silently mark them all recognized. One implementation/release target does NOT remove per-rule evidence requirements: `active` only for fully admitted direct-SNI rules. Unsupported rules are **not activated**; do not stuff never-admitted rules into runtime as `retired` simply to manufacture 55 runtime rules.

**Acceptance target for the single TASK:** finished end-to-end NI-04A infrastructure + NI-04 read-only Device Service Intelligence, with data-driven local immutable bundle support for up to 55 scoped Service identities. A `55/55 positively recognizable` claim or feature activation against incomplete/invalid bundle is forbidden. A truthful launch report must separate catalog targets / admitted rules / actually observed supported recognitions. No second Coder TASK for another batch.

# 1. Input/source inventory, ownership and immutable data

MUST consume:
- `LANE-A-VERIFIED-REFERENCE/{recognition-taxonomy-v1.json,recognition-knowledge-manifest-v1.json,recognition-ruleset-v1.json,research-fixtures-v1.json,EVIDENCE-PACK-v1.md}`; initial exact semantic digests recorded in Owner decision.
- `NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json`: immutable research-source catalog **not a runtime ruleset**; 55 unique IDs; `admission_decision` controls research gate only, NEVER an API field exposed to users.
- Architect R2 decision for 40 ACCEPTED / 1 REPAIR / 9 HOLD and Architect R3 Lane A PASS.
- Original NI-04 v1 + R1 control every normalization, matching, cross-store provenance, time windows, cardinality, query caps, errors and security settings.

**Knowledge authority:** Coder may write deterministic artifact loader, schema validators and matcher, but CANNOT choose new hostname↔Service rules, Organization, Category or Rule Lifecycle from incomplete evidence. Any actual proposed expanded `RecognitionTaxonomyContractV1 + InitialRecognitionKnowledgeManifestV1 + RecognitionRuleSetV1` must first have complete independent source references and fixtures per active rule, exact IDs/version/SHA-256, collision and expiry checks, and Owner-adopted knowledge admission. If the exact full artifact tuple is not provided, leave those candidate rows inactive and feature OFF. **Do not infer identity from marketed ownership or service naming.**

# 2. Delivery model: ONE Coder TASK / ONE PR / ONE target release

One branch and one reviewable PR may contain technically separate modules, but neither should duplicate the other's semantics. Internal logical dependency: protected read bridges + immutable validator/matcher MUST pass focused checks before product orchestration/UI is treated as acceptable. This is a test/checkpoint **within the same TASK**, not a second Owner/Coder handoff. Coder provides one end-to-end change set, one final test/evidence report and rollback notes. If strict staged acceptance requires an additional architecture revision, stop before merging and report the precise conflict; do not silently claim original R1 was changed by an implementation detail.

# 3. Exact allowed module boundaries

### 3.1 NI-01 protected evidence read (additive only)
- New `app/network_metadata/recognition_read_service.py`.
- Read source observations by **exact bounded `source_observation_ref` set** from the existing NI-01 SQLite store; `mode=ro`, `PRAGMA query_only=ON`, bounded 256 refs/batch and common deadline; verify source row provenance/retention; internal `RecognitionSourceEvidenceV1`.
- Keep DNS DTO truthful about absent per-answer query ownership; **DNS is not a positive recognition signal in V1**.
- Raw SNI and sensitive DNS stay within the protected process and request, never escape through current public NI-01 `list_observations`, Admin API or logs.

### 3.2 NI-02B protected Device-relative snapshot (additive only)
- New `app/network_metadata_projection/recognition_read_service.py`.
- One read transaction: runtime state + exact Site/MAC/Device authoritative binding + event-time bounded outbound/external edge facts + source refs and provenance.
- Existing NI-03 `read_protocol_evidence_snapshot()` is untouched. No query-time reattribution by IP. Use `mode=ro`, `query_only=ON`, SQLite schema validation, 5-second total deadline. Do not alter NI-02B tables/writers or retention.

### 3.3 Immutable knowledge artifact loader / canonicalizer / matcher
- New package `app/network_service_recognition/` with `artifacts.py`, `canonical.py`, `matcher.py`.
- Use `CaptivPortalRecognitionCanonicalJsonV1`: strict duplicate JSON key rejection; NFC, canonical UTF-8 object key/order & array order, no insignificant whitespace, no float; SHA-256 of canonical bytes **excluding only artifact's own digest key**; cross-referenced taxonomy/manifest hashes remain inside ruleset hash input.
- Enforce exact schema, regex IDs, source/ref uniqueness, rule review & effective earliest expiry (rule, manifest, all referenced sources), canonical hostname boundary, `rule_kind` active eligibility, static invalid duplicates and only explicitly declared `ambiguity_group_id` runtime ambiguity. Reuse one immutable active local bundle; no partial/truncated/nearest-version activation, no runtime network lookups.
- `matcher.py` one production pure `match_direct_sni_v1(hostname,signal_family,evaluated_at_utc,taxonomy,manifest,ruleset)->RecognitionMatchOutcomeV1`. Inputs `tls_sni|quic_sni`, `observed_retained`, valid Device-relative outbound external edge.
- Exact > suffix; longer suffix > shorter; service > organization; explicit ambiguity returns `ambiguous` with `service_id=null`; no rule ID or lexical tie-break winner.
- **Active DNS-connected rules prohibited** by R1; IP-only, port-only, ASN, CDN, JA4, ML, live LLM, packet payload classifiers prohibited. DNS-only evidence can describe limited coverage but never resolve a Service.

### 3.4 Main NI-04 read-only orchestrator (reuse NI-04A kernel)
- New `app/network_service_recognition/read_service.py` (`DeviceServiceRecognitionReadService`) and product-safe DTO/serializer as allowed by architecture.
- `get_device_service_summary(site_id,device_id,client_mac,*,evaluated_at_utc,deadline)`; source of `client_mac` is the existing Admin Device gateway, not browser.
- Verify authoritative exact Site+Device/MAC identity and every cross-store provenance join; any mismatch/untrusted/missing evidence returns safe state, no guessed Service and no fallback to public NI-03 protocol labels.
- Windows: exact trailing 24h summary `[evaluated_at-86400,evaluated_at)` and recent 60m `[evaluated_at-3600,evaluated_at)`; no browser-defined time range. Dedupe Recent Services by `service_id`, last event time; ≤12 Recent Services; up to 10 categories; Last Service Observation; separate source, attribution and recognition coverage; freshness/identity pending; no source write, cache of raw evidence, or new history DB.
- Implement `RecognitionMatchOutcomeV1`, `ServiceObservationV1`, `DeviceServiceSummaryV1` and related public DTOs exactly per v1+R1 (R1 overrides all positive DNS-correlation portions). Do not simplify failure/unknown/ambiguous states into zeros.

### 3.5 Admin REST + Device Card (additive only)
- `GET /admin/api/v1/sites/<site_id>/devices/<device_id>/service-intelligence` only. Uses current session, same Site scope and `admin.read.device` capability, auth BEFORE evidence read; no body/query; no POST/PUT/PATCH/DELETE. API version `admin.device.service-intelligence.v1`.
- Safe `{api_version,request_id,site_id,result,page:null}` envelope. `Cache-Control: no-store`, `Pragma: no-cache`, same-origin; response ≤16,384 bytes; no raw SNI, DNS, IP/port, MAC newly added, edge/source IDs, rule IDs, source URLs, raw hostnames.
- Exact normalized errors per v1: 400 invalid_request, 401 authentication_required, 403 site_forbidden, 404 feature-off/Device absent, 429 concurrency_limit (`Retry-After: 1`), 503 query_deadline/source_unavailable/recognition_unavailable/response_too_large, 500 internal_error. Internal diagnostics may expose only safe bounded codes.
- Add a separate **Service Intelligence** section on existing `app/admin_web/templates/admin/device.html`; do not rename/replace **Network / Protocol Intelligence**. Recent Services, categories, last observed, freshness, source/attribution/recognition coverage, manual Refresh. UI labels must say `recognized Service-specific web hostname`, NOT `app opened`, `media streamed` or `message sent`.
- JS: first request when section visible, 120s refresh, max one in-flight request per Device Card, manual coalescing, 10s browser timeout, failure backoff 120/300/600s, suspend hidden/pagehide/401/403/404, stale last-good max 900s. No localStorage/sessionStorage for sensitive data, no raw network metadata in HTML attributes.

### 3.6 Deployment-owned config (not a Settings mutation)
- New flag `WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED` default false through `app/config.py`, `app/settings.py`, `app/admin_web/config.py` and existing `run.py`/Admin runtime composition. Add optional source readers only when feature enabled; invalid source/artifact must disable NI-04 **only**, not Portal/Auth/CAPPORT/NI-03.
- Source of NI-01 settings `/etc/captive-portal/network-metadata.env` via existing `network_metadata_config_from_env()`; NI-02B `/etc/captive-portal/network-metadata-projection.env` via existing `projection_config_from_env()`. Coder may supply a reviewable deployment handoff for the main-process NI-01 environment, but MUST NOT mutate production systemd or leak env secrets. Restart is a separate Owner-only deployment decision.

# 4. Performance/concurrency/resource hard gates

| Limit | Required |
|---|---:|
| NI-04 extra process-local concurrency gate | 1 active read |
| Server deadline | min(shared deadline, 5s) |
| Projection edge facts | 5000 max |
| Unique source observation refs | 5000 max |
| NI-01 exact-ref batch | 256 max |
| Hostname/SNI/DNS scalar values examined | 25,000 max |
| Ephemeral ServiceObservationV1 | 5000 max |
| Recent Services response | 12 max |
| Public Service Categories | 10 max |
| API response | 16 KiB max |
| Peak incremental process RSS at max synthetic case | ≤64 MiB |
| Knowledge taxonomy Services | ≤512 |
| Organizations | ≤256 |
| Recognition rules & hostname patterns | ≤2048 each |
| Knowledge sources | ≤4096 |

Hard source/signal overflow: no partial Service set; safe `503 source_unavailable`. Only the ≤12 Recent Services presentation bound may return evaluated subset with recognition_state `limited`. No SQLite write transaction by NI-04. NI-01/NI-02B writers must continue; no checkpoint corruption, false capacity halt, unbounded RSS, long-lived read transactions or Portal/Auth/CAPPORT regression.

# 5. Allowed file paths / no-go areas

**Allowed add:**
- `app/network_metadata/recognition_read_service.py`
- `app/network_metadata_projection/recognition_read_service.py`
- `app/network_service_recognition/{__init__.py,artifacts.py,canonical.py,matcher.py,models.py,read_service.py,serialization.py,knowledge/*.json}` as justified
- focused `tests/network_metadata/`, `tests/network_metadata_projection/`, `tests/network_service_recognition/`, `tests/admin_web/` and documentation for this feature.

**Allowed modify (additive diff only):**
- `app/admin_web/{config.py,query_service.py,routes.py,static/admin.js,static/admin.css,templates/admin/device.html}` and existing Admin composition helper(s) as proven necessary (identify exact actual paths in PR)
- `app/{config.py,settings.py}`, `run.py` and corresponding focused config tests.

**Forbidden edits** without separate Owner/Architect directive: `app/network_metadata/schema.py`, ingestion/normalizer/retention/writer, `app/network_metadata_projection/schema.py`, attribution/Registry writers, NI-03 existing read DTO/route semantics, Portal/Authorization/CAPPORT, Omada provider, Visitor/Visit Lifecycle, Current State/Traffic Projection, Device Fingerprint/Sensor/Suricata, Settings control plane, Nginx, SPAN topology, production service unit/env, any new raw-history DB, user-facing network evidence download.

# 6. Evidence, security and recognition test matrix (Coder MUST implement)

**Knowledge validator**
1. Recompute all three Lane A v1 semantic SHA-256 values from raw verified references; 34 research vectors preserved including `negative.same_org.youtube_music`; no v1 semantic version bump if unchanged.
2. Synthetic canonical fixture digests from Architect R1 v1: taxonomy `63c37fdcf6d276a6ab7521e2e7cd6c9d5baad2c821a6c76ea8e87d294a836700`, manifest `8529f4bc8b29d7bbe64d1d8394ba6d33021b2c59cd70ad5ccc5b0ce4e01e0ed1`, ruleset `61097d804e91e5bad70b8f6d1e883718e84d631effcec0fe3240e8a806a426bd`.
3. Reject missing/duplicate knowledge refs, duplicate JSON names, invalid sorting/normalization/digests, dangling taxonomy targets, bad cross-artifact IDs/version/digests, illegal DNS-connected active kinds, expiry/review-inversion, duplicate matcher+target, undeclared ambiguity, orphan groups, wrong canonical byte input. Never repair a bad artifact silently.
4. Exact runtime artifact expansion MUST use new ID/version/digest tuple appropriate to content change, linked sources and per-rule negative fixtures. A static candidate catalog or current Top-50 research CSV is not valid production bundle input.

**Matcher**
5. Production `matcher.py` used by all tests, no test-only matcher. Positive both TLS and QUIC SNI and no false resolution for e.g. `music.youtube.com` as `service.youtube`, `notwww.youtube.com`, apex/suffix boundary, unrelated Google/Meta sibling, cloud/CDN IP, DNS-only, ECH/no SNI, wrong Site/Device, inbound/local, stale/expired, ambiguous deliberate equal key. Zero false positives in negative fixture matrix.
6. Catalog 55 unique Service IDs, no duplicate host rule, no automatic lifecycle promotion of 9 HOLD/1 category-repair/5 new proposed rules; unsupported remain unknown/limited not 'no internet'. `ChatGPT -> category.other_supported` whenever a new admitted artifact includes ChatGPT.

**Cross-store, UI and security**
7. NI-02B authoritative event-time identity, one snapshot, exact source refs, provenance mismatch fail closed; disabled/upstream missing; source retention; boundary case evaluated_at; 5000/5001 edges, 256/257 batches; 25k cap; concurrency/deadline; no writes.
8. Positive same exact Device via Admin `admin.read.device`; 400/401/403/404/429/503 mappings; Site A cannot access Site B; unauthenticated API never opens evidence reader; response ≤16 KiB; no cache; no raw SNI/DNS/MAC/IP etc anywhere in public response, logs, JS, DOM.
9. Device Card NI-03 unaffected/green; NI-04 independently OFF/ON/unavailable; new section not visible when OFF; 120s polling/timeout/backoff/manual coalescing, stale/identity-pending/no-absence semantics, mobile/desktop accessibility; no 55-application-usage claim.
10. Linux-native full focused regression per repo accepted SQLite baseline; no production performance experiments; synthetic lab writer/read coexistence; RSS ≤64 MiB; collect p50/p95/max; no increased non-feature portal/authorization latency.

# 7. Exact deliverables

One PR with:
- protected internal NI-01/NI-02B readers and tests, immutable loader/canonicalizer/matcher and tests, NI-04 orchestrator/DTO, Admin route/UI/JS, default-OFF config and additive main-process handoff;
- accepted local knowledge bundle(s) with exact manifest/taxonomy/ruleset ID-version-digest and evidence pack for **every activated rule**;
- explicit machine-readable 55-item research/scope registry tracked **separately from runtime loader**, and one report per row: `catalog_target`, `host_candidate`, `host_semantic_accepted`, `rule_bundle_admitted`, `direct_SNI_supported`, `reason_if_not_admitted`;
- tests for every admitted rule's positive, near-match, same-org, shared-infra as applicable; security, performance, failure isolation, API/UI;
- `BASELINE/SHA/TREE`, changed-file list, test commands/results, SQLite version, negative evidence results, hash attestation, no secrets, rollback with feature OFF and exact commit reversion instructions;
- no merge or deployment without Owner's separate approval.

**One final PR; no subsequent Coder TASK needed to make the same engine support the rest of the registry.** New actual service-rule admissions after that PR remain immutable data revision and review (not a reason to copy/paste another matcher or add another API).

# 8. STOP / NOT ACCEPTED

Immediate STOP and report to Tech Lead if:
- Coder is asked to invent admitted hostname, Organizational identity, Service Category or positive rule evidence, to silently upgrade any of the nine HOLD rows, or to equate branded login/CDN/marketing with native app usage;
- an expanded bundle of 55 is demanded as active despite missing evidence, or either protected reader must expose raw evidence to browser;
- missing source data is represented as zero activity, source/runtime failure masks the Portal, a schema/writer change is necessary, or a hard limit/test gate fails;
- runtime artifacts are invalid, sources disagree, fatal source provenance not verified, or a production flag/restart/deploy would be needed to 'prove' changes;
- original architectural separation (`NI04A before main NI04`) is materially contradicted by code acceptance sequencing. This consolidated TASK requires internal proof of the kernel before acceptance of product layer, not a second external Coder TASK.

# 9. Acceptance statement

This is a **single executable Coder handoff for all 55 UNIQUE Service identities and one NI-04 product implementation**, authorized in scope by Owner. It is **NOT a factual claim that all 55 can be positively recognized by existing retained SNI**. Knowledge activation remains limited to actually validated per-rule immutable evidence. The release stays flag-OFF until tested and separately approved by Owner. Traffic 24h observation HOLD is unrelated and MUST NOT be modified.
