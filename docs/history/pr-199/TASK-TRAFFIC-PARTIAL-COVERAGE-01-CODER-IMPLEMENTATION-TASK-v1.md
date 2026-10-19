# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — CODER IMPLEMENTATION TASK v1

**Project:** CaptivPortal / `ZaurNavi/CaptivePortal`  
**Issued by:** Technical Lead  
**Date:** 2026-10-11  
**Type:** Production-code implementation, tests and local evidence; **not** a deployment order  
**Architecture:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1(1).md` — **TECH LEAD ACCEPTED**  
**Status:** TASK PREPARED; **CODER START REQUIRES EXPLICIT OWNER AUTHORIZATION**  
**Merge / production / activation:** NOT AUTHORIZED

## 0. First read — objective

Fix the demonstrated AP-4 failure mode. When one AP loses power/cable and its traffic endpoints return `source_unavailable`, the other APs' valid traffic must remain visible on **Home → Traffic Now** and **Traffic → Current/History**. Show a complete **confirmed-online-population** total only when Current State independently proves a temporally aligned Offline AP and all confirmed-Online APs have valid comparable measurements. Otherwise show an explicitly **partial measured subtotal**. Never change missing rates into numeric zero, never call a partial subtotal a complete Site total, and never merge strict/partial historical samples into one full-coverage series.

**Concrete example:** 4 installed AP; AP-4 confirmed Offline, other 3 measured at 18 Mbps download + 3 Mbps upload => live `complete_online_population`, 21 Mbps, `3 Online / 4 total · 1 Offline excluded`; historical representation of that partial source cycle => **21 Mbps measured partial coverage**, **not** a retroactively complete four-AP total.

This is a **read/query/serialization/UI correction**, not a change to how measurements are collected or stored.

## 1. Authority, prerequisite and baseline gate

1. Read the complete authoritative **v1-R1** architecture contract before touching code, especially §§4–25, 30–40 and fixtures T01–T25. Its enums, numeric rules, JSON shapes, UI messages, hard caps and forbidden operations are normative. This TASK defines *what to implement*, not an alternative architecture. On inconsistency, STOP and ask Technical Lead; never silently choose semantics.
2. Exact reviewed baseline at task creation:
   - `main`: `e8061de9fbd6da8be5cd269779070a4db4d59d64`
   - tree: `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`
3. Begin only after Owner expressly authorizes Coder to work. Verify Git branch, HEAD, tree and clean worktree. If `main` moved because another task was merged (including NI-04A), STOP for a Technical Lead baseline/overlap recheck. Do not blindly rebase or change another task.
4. Implement in isolated feature branch/worktree, not production. No push, PR, merge, production action or service restart without separate authorization.
5. No new architecture/design choice: only bounded private helpers, code organization and test organization are at Coder discretion.

## 2. Non-negotiable rules

- `missing != 0`; `unknown != offline`; stale AP status is not Offline; `source_unavailable != ok`.
- An excluded confirmed-Offline AP is **absent from the live expected population**, **never** a written/synthesized `0.0 Mbps` observation. Real zero is allowed only with numeric `0.0` and reason `ok`.
- AP status source of truth is **Current State**, not missing traffic, ping, IP, name, historical data or network inference. Join **only Site + canonical AP MAC**; prevent cross-Site joins.
- A Site traffic aggregate chooses **one** source family, **Wired OR LAN**, by the exact architecture priority. No per-AP Wired/LAN mixing, no sum over mismatched timestamps, no DTI/NI/NetFlow alternative/fallback.
- Existing API behavior without `coverage_mode` stays **unchanged**. Existing strict current and strict historical semantic methods remain independently available. Historical strict Average/Peak/AP-share formulas are not modified.
- No new collector, Omada requests, database, schema, migration, writer, durable observation, backfill, background job, new port or changes to retention/cadence. **No DB writes in the new evidence read paths.**
- No effect on Portal/Auth/CAPPORT, Guest/Session/Public Traffic, NI-01/02B/03/04, Fingerprint, Current State collection, Traffic Projection writer, Omada Controller.
- Fail closed for malformed data; never hide a newer structurally corrupt candidate by presenting an old numeric result as current.

## 3. Implementation steps (all mandatory)

### A. Add authoritative time-aligned AP status read boundary

Owners: `app/current_state/read_service.py`, `app/current_state/models.py` only.

Implement internal bounded read-only method exactly:

`CurrentStateReadService.read_ap_status_evidence_at(site_id, traffic_finished_at) -> CurrentApStatusEvidenceV1`.

- Select **latest successful complete AP inventory** for the Site whose `capture_finished_at <= traffic_finished_at`.
- Status evidence is `aligned_fresh` only when age at traffic time lies in `[0, CurrentStateConfig.ap_fresh_max_age_seconds]` (default 90s); else `stale` or `unavailable`. Never use a **future** AP status snapshot to reclassify earlier traffic.
- Validate complete inventory, same Site, canonical unique MAC, status classification `online|offline|other|unknown`, and scope metadata; preserve source cycle ID, capture times, age and scope hash.
- Expose the bounded complete-status set to the **internal** current traffic service only; never expose a raw Current State DB read via Admin routes/browser. Read-only existing repository access, no migrations, no new polling.

### B. New current traffic read path — leave strict method unchanged

Owners: `app/analytics/source_gateway.py`, `app/analytics/current_traffic.py`, `app/analytics/models.py`.

Implement:

`AnalyticsSourceGateway.read_current_partial_traffic_evidence(...)`

`CurrentTrafficReadService.get_current_site_traffic_partial_coverage(...)`.

- Read newest completed `success|partial` AP-dynamic candidate and latest-attempt metadata in the existing bounded query path. Source cycle must satisfy §8 lifecycle/structural integrity gate. Accept source `partial` with endpoint errors only where identity/rate/timestamp integrity remains valid. Do not relax strict `get_current_site_traffic()` predicates.
- Structural checks: source rows reported=seen=stored=actual; skipped=0; warnings=0; same Site/cycle; unique canonical MAC; rate reasons/value shape; valid timestamps and finite nonnegative numbers. Overall `partial` and `error_count>0` are allowed. A broken overview/radio endpoint is **not** independently grounds to reject valid traffic rates. Any corrupted newest eligible cycle => safe `unavailable`, not an earlier apparently-fresh numeric result.
- Compute Observation set `R`, Current State installed set `I`, `O` online, `F` offline and `X` other/unknown; report match/mismatch and counts. Only a fresh temporally aligned complete Current State snapshot may exclude known Offline APs.
- Source choice **in order** (§7.2): Wired covering all `R`; LAN covering all `R`; Wired covering all confirmed `O`; LAN covering all confirmed `O`; LAN higher pair count; otherwise Wired. One source family per Site result. Respect the exact closed `selection_reason` names.
- Measurement states **in order** (§4.3 / §9.2): `complete_installed` on proven fully covered installed population (legacy complete success OR aligned matching Current State); `complete_online_population` only when `R=I`, `X=empty`, all Online pairs valid and all Offline selected-source directions are exactly `source_unavailable/NULL`; `partial_measured` if at least one safe selected-source direction exists; else `unavailable`.
- Explicit R1 precedence: a globally `partial` source cycle with all *observed* APs measured but **no installed-population proof** stays `partial_measured`, never `complete_installed`.
- For Online-but-missing, unknown/other, stale status or population mismatch, still return safe measured subtotal as **partial**, not zero or false complete. `status_measurement_conflict` is required for confirmed Offline with incompatible selected-source reasons/rates (§11.1, T15).
- Download = sum only real valid selected-source Download values, or `NULL` if none. Upload independently likewise. Current Total = Download+Upload only if **both** exist. Never create traffic zero from absence. Enforce max AP timestamp skew 60s by default (otherwise Site numbers `NULL`, reason `temporal_skew`), existing current fresh/stale 90/180-second policy, future-time rejection, and no stale reuse after AP comes Online.
- Return the exact `CoverageAwareCurrentSiteTrafficV1` model (§11): metric version, measurement/population states, snapshot/latest-attempt/freshness, coverage identity and counts, source selection, status evidence metadata, closed reasons. For `unavailable` all Site numeric traffic fields `NULL`.
- Current AP page under `partial_v1` uses the **same selected cycle, selected source, Site and status evidence** as the summary; retain existing deterministic bounded cursor paging, ACL and validation. Add only the §12 derived `coverage_role` and status context. Do not fabricate rows missing from an Observation cycle.

### C. Historical partial-read overlay — keep projection statistics unchanged

Owners: `app/analytics/historical_traffic.py`, `app/analytics/models.py`, bounded shared analytic helpers in the allowed files, and **read-only** `app/traffic_projection/read_service.py`.

Implement:

`PartialTrafficEvidenceReadBoundaryV1.read_partial_ap_traffic_evidence(...)`

`HistoricalTrafficReadService.get_site_history_partial_coverage(...)`.

- First obtain the existing strict projected Historical result through the unchanged canonical method. Independently read **persisted completed `result=partial, complete=0` Observation AP-dynamic cycles** by Site and `[from_utc,to_utc)` via existing configured Observation path, SQLite `mode=ro`, `PRAGMA query_only=ON`, bounded indexed read, existing deadline/busy constraints. No second DB path alias and no projection writer modification.
- Structural partial-cycle admission is the same as step B. Reject malformed identity/rates; count integrity rejections as frozen. Do not treat rejected cycles as zero or as valid numeric overlay.
- Source selection is **once per product bucket** (not per AP/cycle): frozen §14.1 priority, including R1 directional-opportunity tie-break; no Wired/LAN mixing. Use only 24h/7d existing ranges and bucket alignment.
- For each admitted cycle and selected source: `D_c` real valid Download APs, `U_c` valid Upload APs, `P_c=D_c∩U_c`. A coherent cycle Total exists **only when `D_c=U_c=P_c` and nonempty**. Download-only and Upload-only evidence remain individually visible, but cannot invent a Total from unlike AP populations.
- Per bucket, directional arithmetic means are separately computed over cycles with that direction: `C_D`, `C_U`; Total mean only over coherent-total cycles `C_T`, **never** `mean Download + mean Upload` when sample sets differ. `download_sample_count=|C_D|`, `upload_sample_count=|C_U|`, `measured_sample_count=|C_T|`.
- States: `partial_measured` if ≥1 coherent Total sample; `partial_directional` if some directional value but no Total sample; `partial_unmeasured` if no valid directions. Evidence-only `partial_unmeasured` bucket has **all three traffic numbers NULL**, no zero point.
- `coverage_ratio = Σ|P_c| / Σ|R_c|` for positive denominator; zero here is a *coverage ratio*, not a traffic measurement. Include exact opportunity counts, min/max AP counts, selected source, closed reasons, and sparse §15 DTO (max one overlay entry per product bucket). No AP-status-based historical Offline promotion.
- Preserve original strict time-series and strict period Average, Peak, AP series and AP share metrics. Do **not** average strict complete and partial subtotals. When partial overlay exists, qualify Average/Peak as complete-coverage-only and suppress full-period percentage comparisons and AP share fractions. Apply exact §16 / §25 reasons and copy. On overlay failure or unknown coverage, keep independently valid strict values but **never** claim full-period correctness.
- Overlay envelope `network_traffic_partial_coverage_overlay.v1`: §17 exact types/status/reason/counts/buckets. `has_partial_measurements` and `source_coverage_insufficient` are `boolean|null`; **unknown = JSON null**, never false. On `unavailable`, `capacity_limited`, `source_coverage_insufficient`, all overlay buckets `[]`, bucket_count `0`, examined/admitted/rejected/row counts `null`, comparison/AP-share not allowed. `source_coverage_insufficient=true` only for known incomplete raw range, `null` for unknown source/capacity failures. On `ok` with no partial cycles and *proven* raw range coverage, `has_partial_measurements=false` and strict eligibility can govern comparisons/share.
- Constraints: max 10,080 partial cycles/request; 150,000 AP rows/request; streaming batches ≤2,000 rows; ≤5s **local overlay** processing budget; ≤720 returned product buckets; existing total Admin query deadline and concurrency. No `OFFSET` pagination or unbounded group aggregation. Any cap exceeded: `capacity_limited`, no partial/truncated numeric buckets. Source DB unavailable => overlay `unavailable`; insufficient retained raw range => `source_coverage_insufficient`. **Do not infer “no partials” from empty query results without reliable source-range coverage proof.**

### D. Add opt-in mode, flag and safe serialization

Owners: `app/admin_web/current_traffic_serialization.py`, `historical_traffic_serialization.py`, `query_service.py`, `routes.py`, `config.py`, `app/config.py`, `app/settings.py`.

- Add exactly **one** repository-default-OFF flag: `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false`. Use process env → `app/config.py` → `app/settings.py:get_settings()` → `AdminWebConfig`, with strict validation and no extra hidden feature flag. Do not turn ON in production.
- Add strict opt-in `coverage_mode=partial_v1` to:
  - `GET /admin/api/v1/sites/<site_id>/current-traffic/summary` (`admin.read.overview`);
  - `GET /admin/api/v1/sites/<site_id>/traffic/current` (`admin.read.context`);
  - `GET /admin/api/v1/sites/<site_id>/current-traffic/aps` (`admin.read.observations`, existing bounded `cycle_id/limit/cursor`);
  - `GET /admin/api/v1/sites/<site_id>/traffic/history` (existing authorization and product include selection).
- Missing parameter => strict legacy byte/semantic response unchanged (except existing nonsemantic runtime metadata). Any other value, duplicate or invalid parameter => `400 invalid_request`. New mode with feature disabled => `404 not_found`. Preserve Site isolation, admin capabilities and request limits. No new public read endpoint for source databases or status evidence.
- New serializers validate exact §11/12 current and §15/17 historical DTOs. Fail closed on unknown enum, non-finite/negative number, inconsistent count, bad Site/timestamp/source, malformed source selection and invalid null/value relation. Ensure strict serializers and strict methods are still independently exercised by tests.
- Keep Current Traffic mode distinct from Current Guest Traffic, Traffic Evidence and other products. Preserve existing admin history `range`, include/products, response-size constraints and provenance.

### E. Home and Traffic UI consumption

Owners: `app/admin_web/templates/admin/home.html`, `traffic.html`, `app/admin_web/static/admin.js` only (reuse existing CSS patterns; new stylesheet edits are not authorized by this TASK).

- Feature flag OFF: preserve current requests, markup behavior and all strict labels. Feature ON: Home and Traffic use `coverage_mode=partial_v1`, consuming the **server-supplied** coverage state; browser must not decide AP offline/completeness from raw data.
- Home and Traffic Current: exact four states and English copy from §§22–23. Example: `Total traffic: 21 Mbps` + `3 Online / 4 total · 1 Offline excluded`; partial => `Measured traffic: 21 Mbps` + `Partial data · 3 of 4 APs measured`; unavailable => `No reliable traffic data`, numeric `—`; stale => `Traffic is stale`. Per-AP roster identifies Offline excluded vs Online-with-missing vs unknown/other. Real zero remains numeric zero.
- History: preserve strict chart series, add visually **distinct** sparse overlay for `partial_measured` Total; distinguish directional-only evidence without synthesizing a Total; for `partial_unmeasured`, show only nonnumeric marker/annotation, never a zero line. Mixed complete/partial evidence in the same bucket remains two distinct observations with §24 exact tooltip. No interpolating across missing data.
- Period Average, Peak, comparison and AP share must follow exact status-specific copy/masking §§16, 25, including failure states and tri-state unknown. No browser-side reconstruction of averages, source choice or period completeness.
- Reuse existing request timeout, refresh timer, state/failure handling and accessible UI practices. No new independent polling loop or source fan-out, no modification to NI-03 interface.

## 4. Approved files / protected files

**Allow changes only within architecture §30:**

```text
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/historical_traffic.py
app/traffic_projection/read_service.py              # read-only addition
app/current_state/read_service.py                    # read-only addition
app/current_state/models.py                          # read-only DTO
app/admin_web/current_traffic_serialization.py
app/admin_web/historical_traffic_serialization.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/config.py
app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/config.py
app/settings.py
tests/**                                           # relevant focused tests
```

No broad refactoring. **Do not alter**: Observation collector, repository/schema/writer, OmadaProvider, Current State collector/repository/schema/status classifier, Traffic Projection writer/repository/schema/projector, Portal/Auth/CAPPORT, Registry/Visit Lifecycle, Guest/Session/Public Traffic, Fingerprint, NI, Suricata, systemd files, production env, SQLite databases, Grafana stack. If another file or a protected contract is truly necessary, **STOP; obtain Technical Lead authorization first**.

## 5. Test and independent acceptance plan

Implement deterministic **real production-code-path** tests of every architecture test **T01–T25**, not a parallel test-only arithmetic simulation. Cover both typed service layer and serialized HTTP/API where appropriate; assert displayed state, numbers, source family, reasons, nulls, Site isolation, privacy and feature-gate behavior.

**Primary numerical canaries** (§35): synthetic Site `aaaaaaaaaaaaaaaaaaaaaaaa`, AP-1..4 MAC suffix `01..04`; rates AP1=10/1, AP2=5/1, AP3=3/1, AP4=2/1 Mbps. All four valid => Download=20, Upload=4, Total=24. AP4 excluded/absent, remaining 3 valid => Download=18, Upload=3, Total=21. T02 Current must be `complete_online_population`, T02 History `partial_measured`. No fake `AP4=0` fact.

**Mandatory full matrix** (exact cases/expected wire fields in v1-R1 §§36–38):

```text
T01 full 4-of-4 current measurement
T02 confirmed Offline AP4 / 3-of-4 measured / historic partial
T03 Online AP4 with missing measurement
T04 AP status unknown, other or stale
T05 no valid AP directions; historical partial_unmeasured + nulls
T06 actual measured zero
T07 online recovery no_baseline/counter_reset -> full
T08 Site inventory mismatch, wrong Site, cross-Site MAC
T09 timestamp skew, aged-out and stale
T10 Wired/LAN deterministic selection; no mixing
T11 historical 4 -> 3 -> 4, statistics masking
T12 corruption: duplicate/bad MAC, row count, reason/value/time
T13 feature OFF + missing coverage_mode backward compatibility
T14 automatic AP recovery without data mutation
T15 Offline with incompatible counter_reset => status_measurement_conflict
T16 future status snapshot cannot relabel past traffic
T17 overlay capacity/time budget => exact capacity_limited JSON + UI
T18 overlay source failure => exact unavailable JSON + UI
T19 full-covered strict-only interval =>
    status=ok, reason=no_partial_measurements,
    has_partial_measurements=false, source_coverage_insufficient=false
T20 strict and partial sample coexist inside one graph bucket
T21 raw range coverage insufficient => exact failure JSON + UI
T22 all historical directions non-ok => evidence-only partial_unmeasured
T23 historical Download-only => partial_directional, Total=null
T24 historical Upload-only and disjoint directional cycles => Total=null
T25 varying AP counts => opportunity ratio 7/9 (not mean of ratios)
```

Additional negative gates: invalid/multiple `coverage_mode`, feature OFF 404, unauthorized 401/403 and wrong Site, oversized response, concurrent deadlines, invalid enum/malformed DTO, no silent inference of `has_partial_measurements=false` on coverage gap, non-finite numeric rejection, no mixed-source sum, no new AP-only status reads in browser, no new Omada calls, no protected writer activity, no source DB mutations.

**Real-incident replay**: deterministic synthetic fixture shaped like Oct 10 AP-4 cable incident: `partial` cycle with 4 AP rows, 2 endpoint errors, AP1–3 Wired/LAN valid, AP4 both unavailable, preceding aligned confirmed Offline Current State snapshot. Prove 21 Mbps live `complete_online_population` and 21 Mbps historical `partial_measured`; prove automatic recovery sequence Offline -> Online no_baseline -> fully measured. Do not copy raw production DB, real MACs/IPs or secrets into test fixtures/artifacts.

Run targeted suites for `tests/analytics/**`, `tests/current_state/**`, `tests/admin_web/**`, `tests/traffic_projection/**`, `tests/observations/**`; JS syntax/DOM tests as applicable; full repository gate:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
git status --short
```

Tests must finish with counts PASS/FAIL/SKIP and reasons. Do not claim PASS for tests not run. If environment prevents the full suite, report `BLOCKED` with evidence; do not substitute partial tests for full PASS. Preserve CI/test-gate requirements for external independence.

## 6. Handoff deliverables and stop rules

Provide **one reviewable change set** (or ask Tech Lead if phase splitting is needed), committed on isolated branch, with:

1. `BASELINE_SHA`, `BASELINE_TREE`, `IMPLEMENTATION_SHA`, `IMPLEMENTATION_TREE`, `BRANCH`, `WORKTREE_CLEAN`.
2. Exact modified-file list/diffstat and rationale for each file; proof no protected files or writer/schema changes.
3. New feature flag and **repository default OFF**, with strict absent-param legacy response comparisons.
4. Mapping of implementation components to Architecture §§5, 7–25; current and historical final DTO samples with synthetic safe data.
5. Evidence for **each T01–T25** and the real AP-4 replay; full regression counts (PASS/FAIL/SKIP), JS syntax, compile, diff check, concurrency/deadline/cap evidence.
6. Security/Site authorization and privacy evidence, raw SQLite read-only proof, no synthetic zero and no new Omada calls.
7. Description of UI states, tooltip/legend/quality wording and screenshots or browser DOM evidence at normal/mobile width if locally available.
8. Proposed roll-out and roll-back documentation (for review only). Do **not** run production deployment.
9. Explicit unresolved issues, if any, with severity. **No “all PASS” handoff** while critical tasks remain unverified.

**STOP and return to Tech Lead** if baseline moved, protected file/contract change required, selected-source mixing seems unavoidable, exact API semantics cannot be implemented, historical 5s/row caps cannot be upheld, reliable raw source-range coverage cannot be established, or any planned step would require a new DB, migration, Omada request or Portal/Auth/CAPPORT change. Never mask such blockers with fallback guesses.

## 7. Release boundaries: NOT PART OF CODER TASK

Architecture v1-R1 §§33–34 governs rollout: review and test with flag OFF; separate Owner authorization for merge; deploy flag OFF; separate Owner authorization for any **CaptivPortal service restart** and later activation (flag ON), live smoke, and rollback. Other pipeline services must not be restarted. If activated and a regression occurs, semantic rollback is flag OFF + Owner-approved portal restart; do not delete/rebuild any DB. **No permission in this TASK to merge, push, deploy, activate, restart, or change production.**

## 8. Final expected Coder report

```text
TASK=TASK-TRAFFIC-PARTIAL-COVERAGE-01
ARCHITECTURE=TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1
CODER_EXECUTION_AUTHORIZED_BY_OWNER=<recorded explicit approval>
BASELINE_SHA=<...>
BASELINE_TREE=<...>
IMPLEMENTATION_SHA=<...>
IMPLEMENTATION_TREE=<...>
CHANGED_FILES=<...>
FEATURE_DEFAULT=false
COVERAGE_MODE=partial_v1 (opt-in only)
T01_T25=<25 detailed results>
AP4_REPLAY=<PASS/FAIL>
FULL_PYTEST=<PASS/FAIL/BLOCKED, total/failed/skipped>
JS_SYNTAX=<...>
COMPILEALL=<...>
DIFF_CHECK=<...>
WORKTREE_CLEAN=<...>
PROTECTED_CHANGES=NO
DB_WRITES=NO
SCHEMA_CHANGE=NO
NEW_OMADA_CALLS=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTIONS=NO
OPEN_P0=<...>
OPEN_P1=<...>
OPEN_P2=<...>
TECH_LEAD_REVIEW=REQUESTED
```

**Definition of Done:** exact v1-R1 semantics implemented, tests and AP-4 replay proven, strict legacy safe, no protected system modified, candidate ready for **independent Tech Lead review** — not merged or deployed.
