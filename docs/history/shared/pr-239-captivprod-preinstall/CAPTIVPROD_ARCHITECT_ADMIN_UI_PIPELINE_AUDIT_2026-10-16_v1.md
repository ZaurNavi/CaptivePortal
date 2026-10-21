# CAPTIVPROD — Admin UI Functional Recovery / Data Pipeline Audit

**Document:** `CAPTIVPROD-ADMIN-UI-PIPELINE-AUDIT-20261016`  
**Version:** `v1.0`  
**Priority:** `P1`  
**Host:** `captiv-prod`, `192.168.0.99`  
**Deployed Git baseline:** `b6152459421b48514ddc8af114bcc96e30351cf7` (verified by read-only `git rev-parse HEAD`)  
**Inspection:** 2026-10-16, approximately 17:57–18:12 UTC (21:57–22:12 Asia/Baku)  
**Stage:** `A — READ-ONLY DIAGNOSTICS`; `B — PROPOSAL ONLY`  
**Authority:** Architect diagnostics approved; **mutations HOLD**.  
**Disposition:** `ADMIN_UI_FUNCTIONAL_ACCEPTANCE=HOLD`.

## 1. Executive assessment

**The pilot is collecting real traffic; the default Admin Traffic pipeline is selecting no usable snapshot.** The latest `ap_dynamic` collection remained `partial` because Omada inventory included APs whose detailed Wired/LAN data were unavailable. In the examined database **there was not a single `ap_dynamic` cycle with `complete=1 AND result='success'`**. The default Analytics Source Gateway intentionally requires such a strict cycle, so its Current Traffic result is `no_complete_snapshot`, with all Mbps values `null`, despite good rates for online APs in `ap_observations`.

The repository already contains an opt-in **partial-coverage** implementation for Current Traffic and historical evidence, but `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED` is **absent from production env**, no Settings overrides exist, and code defaults to `false`. Moreover, `CurrentStateReadService.read_ap_status_evidence_at()` currently declines to attest otherwise complete AP inventory cycles when `data_quality_warning_count != 0`: the last observed Current State AP cycle was `success/complete` with **2 warnings**. Thus merely enabling the feature cannot honestly assert `complete_online_population`; the present backend gives `partial_measured/measured_only` until that quality boundary is resolved.

Other independent matters: the Owner phone's controller/registry `device_type` is **`unknown`** and fingerprint integration is disabled; that is a source limitation, not evidence of an identity mismatch. Omada webhook receiving is disabled, with no normalized offline events, so the one Visit remains open. AP Configuration Observation has two failed pre-Adoption attempts and no post-Adoption scheduled config cycle yet.

**No production files/configuration/services, databases, APs, Omada settings, Cisco, firewall, NPM, Git branches or collectors were changed.** Queries were performed with SQLite `mode=ro`/`query_only`, source inspection, SSH, and unauthenticated HTTP status checks. No synthetic events or forced cycles were created.

## 2. Time-scoped evidence — do not assume AP population is static

Observed AP population changed **during this read-only audit**; the operator may have been working independently. We did not adopt, configure, or transfer APs.

| Evidence time (UTC) | Current State AP inventory | Latest `ap_dynamic` | Meaning |
|---|---|---|---|
| ~18:00:04 | **1 online** (`AP-4`, suffix `FB:8D`), **3 offline** | `partial`, 4 rows, `error_count=6` | AP-4 alone had valid Wired/LAN rates; three APs had `source_unavailable` |
| 18:10:42 (backend read at 18:10:52) | Two measured APs | `partial`; two measured APs, others unavailable | Pure source-level partial projection yielded nonzero traffic |
| 18:12:04–18:12:05 | **2 online** (suffix `FB:8D`, `5C:38`); **2 offline** (`4A:68`, `6F:F8`) | `partial`, `error_count=4`, 4 rows | Two online APs now have valid rates; strict source still cannot accept the whole cycle |

The second online AP is reported as **observed**, not as an authorized migration by SysAdmin. Before using a future AP-count-dependent acceptance criterion, capture a fresh population snapshot and record which devices the Owner has deliberately transferred.

### 2.1 Source databases — live SELECT evidence

| Database / source | State |
|---|---|
| `observations.sqlite3` | 595 `ap_dynamic` partial cycles by ~18:07 UTC; **0 strict complete-success** cycles. Earlier source snapshot: 294 complete-success client cycles; count continues growing |
| `ap_observations` | AP-4 valid rates, plus a second AP with valid rates later in audit; offline APs have null rates and `source_unavailable` |
| `current_state.sqlite3` | AP and client cycles `complete=1/result=success` (294 of each by ~18:00); latest AP cycle still had nonzero `data_quality_warning_count` |
| `client_observations` | One authorized SSID `Zefer_Parki` guest repeatedly observed; cumulative controller traffic grew from 144,821 to **232,876,092 bytes** over the earlier observed period |
| `visitor_registry.sqlite3` | 1 device; Registry-to-Current-State MAC identity match count **1**; `device_type=unknown` |
| `visits.sqlite3` | 1 Visit `open`; `visit_source_events=0`; authorization linked to a device and initial snapshot; start AP absent in Visit row |
| `ap_config_snapshots` | **0** rows |

**Units:** `controller_traffic_total`, `traffic_down/up`, and Visit reported traffic are **cumulative bytes**, not Mbps. AP instantaneous rates are computed from successive cumulative AP counters and elapsed time; they require valid baseline and direction evidence. No 230–250 MB cumulative figure is an assertion of current link rate.

### 2.2 AP rate-baseline evidence

At 18:07 UTC the last two AP-4 samples had valid Wired rates, approximately 30 seconds apart:

- `18:06:39.164Z`: `wired_download_mbps=0.0086748`, `wired_upload_mbps=0.0041942`, both reasons `ok`.
- `18:07:09.489Z`: `wired_download_mbps=0.0098858`, `wired_upload_mbps=0.0006708`, both reasons `ok`.
- `wired_up_bytes` moved `16,057,649 → 16,060,192`; `wired_down_bytes` moved `223,784,603 → 223,822,079`. These provide distinct, non-reset baselines for AP-4.

At ~18:12 the next data included valid Wired Mbps for **two** APs. Offline APs had `source_unavailable`, not `counter_reset` or `gap_too_large` in that live cycle. Over historical rows, `counter_reset` and `no_baseline` each occurred once in earlier measurements; neither explains the persistent current `partial` result. The source supports **Wired** and **LAN** rate pairs for the measured APs, without mixing directions or inventing missing rates.

## 3. Exact pipeline from Omada to Admin UI

### 3.1 Omada OpenAPI → Observation facts

`observation_cycles` demonstrates successful client polling and four-row AP inventory collection. The AP worker attempts detail sections per AP. Its live outcomes are `ap_dynamic/partial` because some returned APs do not have required rate sources (`wired_uplink_ok=0`, `lan_traffic_ok=0`); `error_count=6` when three APs were offline, subsequently `4` when two remained offline. This is **not** a global Omada TLS failure: online APs return valid counters.

### 3.2 SQLite → Analytics Source Gateway (primary root cause)

In `app/analytics/source_gateway.py::AnalyticsSourceGateway.current_traffic_data`, the default Current Traffic cycle selector explicitly requires:

```sql
WHERE site_id=? AND kind='ap_dynamic'
  AND state='completed' AND complete=1 AND result='success'
```

The live query found **zero** such cycles. The method therefore returns `cycle=None` even though it separately sees a newer `partial` attempt. Current Traffic serializes this intentionally as unavailable. This is source-selection behavior, **not proof that traffic counters are zero**.

### 3.3 Reproduced backend JSON — **source-level**, not HTTP endpoint JSON

To verify behavior without stealing an Admin session or bypassing authorization, we called the deployed **read-only `CurrentTrafficReadService` and its production serializer** against the live databases, with a read-only connection facade and identical policy thresholds (fresh 90s, stale 180s, AP skew 60s). At `2026-10-16T18:10:52.168Z`:

**Strict/current (the normal default):**

```json
{
  "snapshot": {
    "cycle_id": null,
    "freshness_status": "unavailable",
    "freshness_reason": "no_complete_snapshot",
    "latest_attempt_result": "partial",
    "selection_reason": "no_complete_snapshot"
  },
  "traffic": {
    "download_mbps": null,
    "upload_mbps": null,
    "total_mbps": null,
    "unit": "Mbps"
  },
  "coverage": {
    "coverage_status": "none",
    "coverage_reasons": ["no_valid_rate"]
  }
}
```

**Partial-coverage backend projection (not activated in Admin configuration):**

```json
{
  "metric_version": "network_traffic_current_partial_coverage.v1",
  "measurement_state": "partial_measured",
  "population_scope": "measured_only",
  "snapshot": {
    "source_result": "partial",
    "source_complete": false,
    "freshness_status": "fresh",
    "age_seconds": 10.2
  },
  "traffic": {
    "download_mbps": 0.3541882542885725,
    "upload_mbps": 0.07663210527399134,
    "total_mbps": 0.4308203595625638,
    "unit": "Mbps"
  },
  "source_selection": {
    "selected_source": "wired",
    "wired_pair_valid_ap_count": 2,
    "lan_pair_valid_ap_count": 2
  },
  "coverage": {
    "observation_ap_count": 4,
    "measured_pair_ap_count": 2,
    "population_match_state": "status_unavailable",
    "coverage_reasons": [
      "source_cycle_partial",
      "source_unavailable",
      "status_evidence_unavailable"
    ]
  },
  "status_evidence": {"state": "unavailable"}
}
```

The same output occurred with and without asking the partial read service to consult Current State AP status. **It is wrong to display these rates as complete installed or complete online coverage.** This result proves that meaningful rates are available to the backend; it does **not** claim an authenticated Admin HTTP 200, nor does it claim browser E2E PASS.

### 3.4 Current State AP status-evidence veto — secondary root cause

`CurrentStateReadService.read_ap_status_evidence_at()` requires a complete successful inventory cycle **and zero** `items_skipped`, `unidentified_count`, `duplicate_identity_count`, `error_count`, **`data_quality_warning_count`**. The source cycle at 18:12:04Z was `success, complete=1, items_stored=4`, but `data_quality_warning_count=2`; therefore the status reader returns `state=unavailable`. In an earlier state with three offline APs, it returned one warning. The **specific reasons generating warnings have not been proven**; do not weaken the integrity check solely on an assumption that every warning means an offline AP.

Consequently, the existing partial-coverage algorithm cannot yet certify offline exclusions as `complete_online_population`. With status unavailable it correctly yields `partial_measured` and `measured_only`.

### 3.5 Admin Query → HTTP JSON → browser

- **Home current throughput**: default `/admin/api/v1/sites/<site_id>/current-traffic/summary` and `/current-traffic/aps` use strict service unless an explicitly permitted `coverage_mode=partial_v1` is supplied.
- **Traffic current and AP list**: `/admin/api/v1/sites/<site_id>/traffic/current`, `/traffic/summary`, and associated AP page follow strict selection by default. A partial-mode branch exists in Admin Query Service and in `admin.js` but is gated by `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false` (env value absent, empty Settings overrides, code default false).
- **History, Statistics, Peak, AP Traffic and AP Share**: read historical/aggregated source facts and enforce quality/coverage; with no strict accepted AP cycles the ordinary output cannot be used as evidence of a complete historic series. A historical partial overlay exists in source code, but it also requires controlled activation and correct UI labeling.
- **Online Guests**: a distinct current client-rate path exists; successful Current State cycles give it source evidence independent of AP strict-complete selection. Its complete authenticated API payload was not captured.
- **Completed Sessions**: the only Visit is still `open`, so the completed-visit population is empty. This is not equal to a zero-byte completed session.

At the browser boundary, `app/admin_web/static/admin.js` validates returned schemas and renders **`null` metrics as `—`**/unavailable. In partial mode it uses `CaptivPortalCurrentPartialCoverage.summary()` and `.page()` with coverage labels; for example 0.430820 Mbps would display approximately `0.43 Mbps`. Very small **valid** Mbps may round to `0.00 Mbps`; do not confuse rounding with missing data.

**HTTP access limitation:** a live unauthenticated GET of `/admin/api/v1/sites/<site_id>/traffic/current` through NPM gave **HTTP 401** as expected. No Owner Admin session or credential was available in the read-only audit. Therefore *authenticated response JSON and a live browser render were not independently captured*. The JSON above is reproduced from **the actual backend read/serializer** and labeled accordingly. To close full acceptance, capture sanitized authenticated Admin JSON/browser evidence using an approved Owner session, **without lowering authentication**.

## 4. Home / System Health: component-level diagnosis

`app/admin_web/home_health.py::_network_history` evaluates both `client` and `ap_dynamic`. For each it obtains the newest completed cycle **and the newest complete-success cycle** via `ObservationRepository.get_home_health_cycles`.

- Client has fresh complete-success cycles (e.g. `18:07:04.427Z`).
- AP dynamic has fresh `partial` attempts (e.g. `18:07:09.707Z`, then newer), but **last complete-success AP cycle = NULL**.
- The current implementation returns `status=unknown`, `reason_code=initializing` if a required stream has never produced any complete success; its partial error counts are not presented as a successful history. This is a **deterministic code/source inference** assuming the worker is running, not a captured authenticated Health JSON.
- `evidence_at` (if evaluated normally) comes from the earliest of collected last-attempt timestamps before this early return; `last_success_at` is omitted for that branch. The most recent AP attempt is **not** `last_success_at`.
- A `latest_collection_incomplete` degraded reason applies when required successful baselines exist but a newer attempt is incomplete; it is *not* the current first-success-missing branch.

**Impact:** non-operational Network History status can affect aggregate Home Health. It must **not** erase AP-4 measurement facts or be silently interpreted as a physical outage. The Health model currently conflates prolonged first-success absence with short-term initialization. A dedicated truthful state (`degraded / no_complete_ap_history`, subject to Architect contract) is preferable to indefinite `initializing` if partial collection is actively making progress.

## 5. Devices / Current Device Context / type

**Identity evidence:** one Visitor Registry device and one authorized current client exist; a join by MAC across Registry and Current State returned `1` matching device, with the configured technical Site ID matching the pilot context. Current client cycles are complete-success and scoped to `Zefer_Parki`. Current client row is `authorized`, `active=1`; the client Traffic Total is cumulative bytes. The Visit is linked to its Registry device and initial snapshot (`has_device=1`, `has_snapshot=1`), but `start_ap_mac` in Visit row is **NULL**; any Visit historical AP display must preserve unknown rather than backfill an unsupported start AP.

**Device Type:** `visitor_registry.device_snapshots.device_type=unknown`, `visitor_devices.last_known_device_type=unknown`, `client_observations.device_type=unknown`, and `current_client_state.device_type=unknown`. The UI's `device_type_key` is normalized from that source field; it does not independently identify Android/iOS. `connect_device_type=ap` denotes connection category, **not phone platform**. `DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false` in production, so Fingerprint-derived device classification is not an available input to this path. Result: **expected source limitation; no evidence of an Admin rendering defect or cross-site identity mismatch**.

**Open item:** an authenticated Owner device-detail/current-context JSON should be read back to confirm representation and freshness; this was not obtainable via unauthenticated HTTP.

## 6. Omada webhook delivery → normalized event → Visit closure

- Runtime setting `OMADA_WEBHOOK_ENABLED=false` is confirmed. The deployed receiver route is `POST /api/integrations/omada/webhook`; with the feature disabled its guard returns `404` without normalizing the event.
- Normalized and raw webhook log files were not found at their default locations during audit. `visit_source_events` has **0** rows; one Visit remains `open`. No synthetic offline event or manual closure was attempted.
- The normalizer relies on **site-name → technical Site ID** mapping via `OMADA_WEBHOOK_SITE_ID_MAP_JSON`, which defaults to `{}`. An empty map resolves site names to `site_unresolved`, not to the intended Site ID. This setting was not explicitly present in the checked env.
- Receiver enforces `request.remote_addr` inclusion in `OMADA_WEBHOOK_ALLOWED_IPS` and then `OMADA_WEBHOOK_AUTH_MODE` (`ip_only`, `omada_payload_secret`, or `header_token`). Defaults are an **empty IP allowlist and `ip_only`**, which are not an activation-ready security posture.
- The present NPM `captivprod-navi.duckdns.org` proxy Host 4 forwards all paths to `172.18.0.1:18089`, which is guarded by NET-01. On that proxied hop Flask observes the **NPM source IP `172.18.0.2`**, not necessarily the original Omada address. Trusting `X-Forwarded-For` without a reviewed trust boundary is prohibited. A broad allowance for NPM IP alone would expose an unauthenticated webhook path to anyone able to reach the public NPM hostname if `ip_only` remains active.
- **Live Omada webhook registration/listener target and controller's ability to send `shardSecret` or a fixed header token were not independently confirmed.** Neither Omada settings nor NPM was changed. The code's `omada_payload_secret` comparator specifically expects JSON field **`shardSecret`**. Before activation confirm the controller delivers this exact field and can register the intended HTTPS URL.

**Minimum safe staged scheme to review:** controller-origin webhook with confirmed payload authentication, proper site mapping, size limit and event normalization; NPM route access controls with source traceability and no general-purpose weak IP-only public exposure; no relaxation of NET-01 or TLS. Specify source-IP semantics, secure delivery and rollback before separate Owner/Architect GO. Acceptance must involve a **genuine subsequent Owner-device offline event**, closure of the corresponding Visit and valid duration/final cumulative traffic, not manual DB edits.

## 7. AP Config Observations

`ap_config_snapshots=0` and exactly two initial config cycles were present:

| Start UTC | Finish UTC | Result | Items stored | Errors |
|---|---|---|---:|---:|
| 2026-10-16 13:06:36 | 13:06:37 | `failed`, `complete=0` | 0 | 4 |
| 2026-10-16 13:57:46 | 13:57:47 | `failed`, `complete=0` | 0 | 4 |

The AP worker initiates a config cycle at startup, then schedules the next at `monotonic + ap_config_interval_seconds` **after** that cycle. The configuration uses `21600` seconds (6 hours) by default, with no `OBSERVATION_AP_CONFIG_INTERVAL_SECONDS` environment override found. For the running service started at 13:57 UTC, the next round is **approximately 19:57:47 UTC / 23:57:47 Asia/Baku**, subject to scheduler drift, cycle completion and any service restart.

The collector's config sections include General, IP, Radio, OFDMA, Available Channels, v2 **`/override`**, and v2 **`/rf-scan-result`**. The two failed cycles happened before the successful pilot adoption; **there is no post-Adoption config-cycle result at the audit cutoff**. Consequently, successful config snapshot generation is **unverified**, not disproven. Treat a controller RF Scan API error as distinct from TLS failure. Do not force a scan, shorten polling intervals or create a synthetic snapshot. Inspect the next naturally scheduled cycle and its exact failed endpoint, if any.

## 8. Stage B — minimal remediation proposal only (NOT executed)

| Order | Exact proposed action | Security/operational impact | Restart? | Rollback / acceptance |
|---|---|---|---|---|
| B1 | After testing in isolated checkout, enable `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=true` **only on new `.99`** and explicitly render partial scope/coverage, not invented zero/complete traffic | Bounded read-only selection; may change Admin display semantics and load | Likely Portal restart for env composition | Revert flag; prove partial JSON contains actual per-AP Mbps and `source_cycle_partial` labels without regressions |
| B2 | Correct AP status-evidence quality semantics **only after establishing the exact origin/meaning of Current State warning counts**. Permit expected offline classification only with stringent cycle/site/identity/time checks and no unsafe warning suppression | Code/integrity contract; needs Tech Lead implementation TASK, RQA regression coverage | Portal deploy/restart after approval | Roll back exact release SHA; prove `complete_online_population` only for aligned 2-online/2-offline case; mismatch/unknown statuses remain unavailable |
| B3 | Refine Network History Health first-baseline reporting so persistent live partial cycles are differentiated from initialization; continue to expose latest attempt and missing complete-success baseline | Status semantics; no source mutations | If code modified, restart/deploy | Revert reviewed code; assert truthful `reason_code`, evidence timestamps and aggregate Health without hiding partial data |
| B4 | Keep History/Statistics/AP Traffic contract honest under partial source. Validate existing partial history overlays and required parameterization before exposing; no fabricated accepted buckets or full 24h stats | Bounded analytics read; may add query/CPU cost | Only if feature/config changed | Revert flag/code; prove aggregate math, cohort bounds, freshness, empty intervals and UI labels by authenticated API tests |
| B5 | For Visits, separately approve secure Omada webhook registration and delivery path: site-name map, NPM proxy trust boundary, exact source-IP allowlist and payload secret/header auth (confirmed controller capability), strict size, TLS, normalization | **High**: inbound event security and durable Visit closure; NPM/Omada/Portal settings affected | Portal restart for env-based flag; exact NPM/Omada changes require separate GO | Remove webhook registration, restore config/guards; require real owner offline → accepted normalized event → matched Visit closure; no cross-site closure |
| B6 | Do **not** activate Device Fingerprint simply to eliminate `unknown`. Verify desired product contract first; if approved later, integrate type from trustworthy fingerprint evidence with explicit provenance | Privacy, accuracy, attribution, extra CPU/I/O; separate project decision | Only upon separate approval | Keep disabled; unknown type remains valid if controller supplies no type |
| B7 | Allow naturally scheduled AP Config cycle; only if it fails post-Adoption, diagnose v2 endpoint-specific response and prepare narrow code fix | No immediate configuration change | None for observation | Expect valid hash/snapshot for online AP(s) or exact endpoint error; preserve next 6h cadence |

**Release governance:** any code change starts on a task branch from approved `captivprod/main` baseline and is reviewed/tested through Tech Lead/RQA/Owner; production deploy requires a separate GO. No edits to GitHub `main`, `.202`, `.222`, Cisco, NET-01, VLAN, SPAN, Sensor, or unrelated APs.

### Stage B acceptance requirements (not satisfied in Stage A)

1. Through an authorized Owner session, capture the **actual HTTP status and redacted JSON** for `home/health`, Home `current-traffic/summary`, Traffic `current`, `summary`, `history`, AP page, `online-guests`, `completed-sessions`, Devices list and Current Device Context.
2. For each Traffic API, compare directly with a pinned SQLite cycle and same evaluation instant. A 200 response containing unsupported `0` or `null` is **FAIL** when valid source facts should be represented.
3. UI JS must render the *same* evidence, rate units, coverage state and reasons without changing `null → 0`; show source freshness and online/offline population correctly.
4. When status alignment is unavailable, show only **measured partial** results; never claim full online AP coverage.
5. Verify Site/MAC identity and normal, documented `unknown` type unless an approved Fingerprint source actually supplies classification.
6. Verify real Omada event authorization/delivery, normalized accepted `client_offline`, and automatic closure of the owner Visit; preserve final traffic provenance and no false cross-site closure.
7. Allow the scheduled config cycle to happen, then verify Config Snapshot for an online AP or pin the exact v2/controller endpoint defect for an isolated fix.
8. Repeat Admin access/perimeter and regression checks after any activation; NET-01 must remain PASS.

## 9. Requested machine-readable disposition

```text
HOME_HEALTH_ROOT_CAUSE=AP_DYNAMIC_NEVER_COMPLETE_SUCCESS; network_history requires client+AP complete-success cycles; code-inferred reason_code=initializing while no AP success exists; authenticated Home Health JSON NOT_CAPTURED
HOME_TRAFFIC_ROOT_CAUSE=STRICT_CURRENT_TRAFFIC_SOURCE_GATE_REQUIRES_AP_DYNAMIC_SUCCESS_COMPLETE; 0 qualifying cycles; backend freshness_reason=no_complete_snapshot, Mbps=null
TRAFFIC_PAGE_ROOT_CAUSE=SAME_STRICT_GATE_PLUS_PARTIAL_COVERAGE_FLAG_DEFAULT_FALSE; historical strict coverage also insufficient; authenticated per-panel JSON NOT_CAPTURED
AP_TRAFFIC_ROOT_CAUSE=VALID_AP_RATES_PRESENT_BUT_STRICT_CYCLE_REJECTED; partial-mode rate evidence present; status evidence vetoed by Current State data_quality_warning_count>0
DEVICE_CONTEXT_ROOT_CAUSE=NO_IDENTITY_MISMATCH_FOUND; registry/current client match=1; current client authorized; Visit start AP missing; authenticated per-device JSON NOT_CAPTURED
DEVICE_TYPE_SOURCE=OMADA_AND_REGISTRY_DEVICE_TYPE_UNKNOWN; DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false; expected source limitation pending product policy
WEBHOOK_DELIVERY_STATE=DISABLED; default webhook route present but no accepted event/logs; site-name map absent/default empty; actual Omada registration NOT_VERIFIED
VISIT_CLOSURE_BLOCKER=NO_NORMALIZED_CLIENT_OFFLINE; visit_source_events=0; one Visit open
AP_CONFIG_SNAPSHOT_STATE=0_ROWS; TWO_PRE_ADOPTION_CONFIG_CYCLES_FAILED; POST_ADOPTION_SCHEDULED_CYCLE_NOT_YET_OBSERVED; expected next ~2026-10-16T19:57:47Z subject to restart

ROOT_CAUSE_CLASSIFICATION=MIXED: INCOMPLETE_AP_SOURCE_POPULATION + OVERLY_STRICT_DEFAULT_TRAFFIC_SELECTION + CURRENT_STATE_STATUS_EVIDENCE_QUALITY_VETO + MISSING_WEBHOOK_ACTIVATION + EXPECTED_FINGERPRINT_SOURCE_ABSENCE + PRE_ADOPTION_CONFIG_CYCLES
PROPOSED_MINIMAL_FIX=REVIEW_OPT_IN_PARTIAL_COVERAGE; REVIEW_SOURCE_QUALITY_CONTRACT_AND_HEALTH_REASON; VALIDATE_HISTORY_API_AND_BROWSER; SECURITY_DESIGN_AND_APPROVE_WEBHOOK; ALLOW_NATURAL_CONFIG_CYCLE; DO_NOT_FORCE_FINGERPRINT
SECURITY_IMPACT=LOW_TO_MODERATE_FOR_READ_ONLY_UI_POLICY; HIGH_FOR_WEBHOOK_INGRESS; STRICT_TLS_SOURCE_ADMISSION_NET01_MUST_REMAIN
RESTART_REQUIRED=NO_IN_STAGE_A; ENV_OR_CODE_CHANGES_IN_STAGE_B_REQUIRE_APPROVED_PORTAL_RESTART; WEBHOOK_NPM_AND_OMADA_CHANGES_SEPARATE_GO
ROLLBACK_PLAN=REVERT_EXACT_APPROVED_CONFIG_DIFF_AND_RELEASE_SHA; RESTORE_PRIOR_WEBHOOK_REGISTRATION_NPM_POLICY_IF_CHANGED; VALIDATE_NET01_AND_ADMIN_ACCESS; NO_DB_RESET

ADMIN_UI_FUNCTIONAL_ACCEPTANCE=HOLD
```

## 10. Limitations and evidence provenance

- **Actual authenticated Admin API/Browser response**: not collected. Public NPM access to `traffic/current` correctly returned HTTP 401 without session. No credentials were harvested, no authentication relaxed, and backend source projection is **not** mislabeled HTTP JSON.
- **Exact reason for Current State `data_quality_warning_count`**: needs per-cycle source/normalizer provenance; audit proved the warning blocks aligned status evidence but did not attribute each warning type to a specific AP condition.
- **Omada webhook registration, delivery authentication capability and network reachability**: not end-to-end probed because webhooks are disabled and Architect forbids mutation. App code/source and default NPM proxy path inspected read-only.
- **Live AP population changes**: early 1-online/3-offline and later 2-online/2-offline are distinct observations. Numbers in report are explicitly timestamped.
- **Git runtime**: deployed working tree HEAD checked against `b6152459421b48514ddc8af114bcc96e30351cf7`. No source modifications, deploy, or service restarts performed in this audit.
- **Local diagnostics**: small Python read-only scripts were staged **on the authorized Windows workstation**, piped into existing SSH using `sudo -n python3 -` or directly into the deployed venv with `PYTHONDONTWRITEBYTECODE=1`; **no audit scripts were written to production disk**. Production data was accessed through SQLite URI `mode=ro` with `PRAGMA query_only=ON`, without PRAGMA checkpoint or DDL. No user-private identifiers or webhook credentials are included here.

**Primary engineering recommendation:** do not conflate "collector partial" with "no traffic". Establish source-aligned, provenance-preserving partial traffic as an explicitly labeled operational mode, then solve its status-evidence warning gate. Webhook/Visit closure is a **separate security-sensitive activation** with its own approval, tests, and rollback. Until genuine authenticated JSON/UI and Visit Lifecycle acceptance are demonstrated, keep `ADMIN_UI_FUNCTIONAL_ACCEPTANCE=HOLD`.
