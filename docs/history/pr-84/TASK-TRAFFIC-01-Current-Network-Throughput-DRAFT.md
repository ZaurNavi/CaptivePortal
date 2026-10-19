# TASK-TRAFFIC-01 — Current Network Throughput — DRAFT

**Проект:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Тип:** architecture / implementation TASK — DRAFT  
**Статус:** `DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch / code / commit / push / PR / merge authorization:** `NOT GRANTED BY THIS DRAFT`  
**Production activation:** отдельное Owner-controlled решение  
**Подготовлено:** 2026-08-29

---

# 0. Executive decision

`TRAFFIC-01` реализует первую продуктовую плашку нового самостоятельного раздела:

```text
Admin Console → Traffic
```

Плашка:

```text
Current Network Throughput
```

обязана показать:

```text
Download Now
Upload Now
Total Now
```

в:

```text
Mbps
```

и одновременно показать безопасное состояние evidence:

```text
selected source family
freshness
coverage
product-safe provenance / reason
```

Канонический calculation owner уже существует:

```text
CurrentTrafficReadService
```

Поэтому `TRAFFIC-01` НЕ создаёт:

```text
новый traffic calculation
новый serializer
новый collector
новую Traffic DB
новую source-family policy
новый Omada read path
```

Главное implementation решение DRAFT:

```text
CurrentTrafficReadService
        ↓
existing AdminQueryService.current_traffic_summary()
        ↓
existing serialize_current_traffic_summary()
        ├── existing Home Current Traffic endpoint
        └── NEW Traffic endpoint
             /admin/api/v1/sites/<site_id>/traffic/current
```

Таким образом Home и Traffic получают один и тот же immutable serialized product result.

---

# 1. Verified current repository baseline

Перед подготовкой DRAFT фактически проверен current repository.

```text
origin/main =
c719525a1a2a324a0959597c993b99a82bf465b0

tree =
2fd3de8d3ff82559d53e931c3911334ac61fc868
```

Current main commit:

```text
Merge pull request #82
Docs: canonicalize Central Lab testing ownership
```

Первый parent:

```text
f5887758898b512747d2ea8bd51763389230dc2d
```

PR #82 является documentation / agent-governance изменением и не изменяет Traffic runtime.

Последний runtime checkpoint непосредственно перед ним:

```text
f5887758898b512747d2ea8bd51763389230dc2d
TASK-HOME-AP-24H-TELEMETRY-01
```

---

# 2. Relevant merged history

Существующий Current Traffic foundation:

```text
PR #60
TASK-HOME-TRAFFIC-READ-01
merge:
f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0
```

Существующий Home Current Traffic product integration:

```text
PR #61
TASK-HOME-TRAFFIC-01
merge:
3e7ef39bf08c7ead2dd701232ddda8456fe75650
```

Позже Admin/Home развивался через отдельные increments:

```text
Home Activity
Home Health
AP 24H
AP 24H fixes
AP 24H telemetry
```

Current repository по-прежнему содержит существующий `CurrentTrafficReadService`, существующий Admin current-traffic query contract и существующий Home Current Traffic serializer/API integration.

Ни один из этих последующих increments не даёт оснований создавать новый Current Traffic semantic owner.

---

# 3. Master Roadmap binding

Этот TASK связан с утверждённой Master Roadmap.

Roadmap decision:

```text
TRAFFIC-00
Traffic Section Foundation
        ↓
TRAFFIC-01
Current Network Throughput
```

Следовательно:

```text
TRAFFIC-01 IMPLEMENTATION
=
BLOCKED BY TRAFFIC-00
```

на current baseline.

---

# 4. Factual prerequisite delta — TRAFFIC-00 отсутствует

На current main отсутствуют:

```text
WEB_ADMIN_TRAFFIC_ENABLED

AdminPage("traffic", ...)

/admin/sites/<site_id>/traffic

Traffic navigation entry

Traffic page/template shell

Traffic page frontend orchestration boundary
```

Current `pages.py` содержит только:

```text
HOME
DEVICES
DEVICE
VISITS
OBSERVATIONS
```

Следовательно этот DRAFT:

- может полностью зафиксировать architecture contract `TRAFFIC-01`;
- НЕ разрешает реализацию до merge + acceptance `TRAFFIC-00`;
- НЕ включает `TRAFFIC-00` files/scope молча.

Перед FINAL/implementation `TRAFFIC-01` должен быть rebound на exact accepted `TRAFFIC-00` merge SHA.

Если Owner решит объединить `TRAFFIC-00 + TRAFFIC-01`, это требует отдельного явного изменения Roadmap sequencing и нового review.

---

# 5. Purpose

Реализовать внутри уже существующего Traffic shell первую функциональную Site-level panel:

```text
Current Network Throughput
```

Пользователь должен быстро видеть:

```text
Download Now
Upload Now
Total Now
```

и понимать:

```text
какой source family использован
насколько evidence свежий
полное ли coverage
почему значение partial/unavailable при проблеме
```

TASK является functional product increment.

Final visual redesign всего Traffic раздела в него не входит.

---

# 6. Product meaning

`Current Network Throughput` означает:

```text
Current Site AP physical/network traffic evidence
```

Это не автоматически:

```text
Internet Traffic
WAN Traffic
Guest Traffic
Zefer_Parki Traffic
SSID Traffic
Billing Traffic
```

Mandatory helper meaning:

```text
Derived from persisted AP traffic counters.
May include local/service traffic and is not an Internet-only measurement.
```

Exact final localization/copy может позднее корректироваться Web Designer phase, но смысл менять нельзя.

---

# 7. Authoritative source

Единственный canonical source path:

```text
Omada current AP primitives
        ↓
existing Observation acquisition
        ↓
observations.sqlite3
        ↓
CurrentTrafficReadService
        ↓
AdminQueryService
        ↓
Admin API
        ↓
Traffic browser
```

Permanent:

```text
acquisition != product read
```

Запрещено:

```text
Browser → Omada
Admin request → Omada
Admin request → force Observation cycle
new Omada collector
new Current Traffic persistence
new Current Traffic DB
new rate calculation
new AP counter formula
new source selection algorithm
Loki/Grafana as product source
```

---

# 8. Existing CurrentTrafficReadService contract

Current service:

```python
CurrentTrafficReadService.get_current_site_traffic(
    site_id,
    *,
    evaluated_at_utc=None,
    fresh_max_age_seconds,
    stale_max_age_seconds,
    max_ap_skew_seconds,
    deadline=None,
)
```

Current implementation:

```text
bounded
Site-scoped
read-only
persisted Observation only
```

Canonical source machine enum:

```text
wired
lan
```

Primary:

```text
wired
```

Fallback:

```text
lan
```

Radio is excluded from Site Current Traffic total.

---

# 9. Current source-family selection must not change

Existing source selection remains authoritative.

Conceptually:

```text
wired full coverage
→ wired

else LAN full coverage
→ lan

else family with higher valid pair coverage

tie / wired higher
→ wired
```

One selected source family is used for the Site result.

Forbidden:

```text
AP-1 wired
+
AP-2 lan
→ Site total
```

No HTTP query parameter may allow a browser/caller to select source family.

---

# 10. Direction semantics

Existing accepted meaning remains:

```text
wired Download = wired_download_mbps
wired Upload   = wired_upload_mbps

lan Download   = lan_rx_mbps
lan Upload     = lan_tx_mbps
```

Research independently confirmed physical direction coherence:

```text
LAN RX ≈ RADIO TX ≈ CLIENT DOWN
CLIENT UP ≈ RADIO RX ≈ LAN TX
```

Small accounting differences between layers are normal because snapshots are not atomic and protocol/service overhead differs.

`wired_activity_raw` is diagnostic/cross-check evidence only.

It MUST NOT replace directional Download/Upload.

---

# 11. Exact reuse decision

## 11.1 Application/query method

NEW Traffic-specific `AdminQueryService` calculation method is NOT required.

Reuse:

```python
AdminQueryService.current_traffic_summary(
    principal,
    site_id,
)
```

Reason:

- already performs Site authorization;
- already uses shared Admin query execution controls;
- already calls canonical `CurrentTrafficReadService`;
- already maps service failures into safe Admin errors;
- already serializes with explicit allowlisted Traffic serializer.

Creating:

```text
traffic_current_summary()
```

with identical internal behavior would add duplicate semantic ownership without product benefit.

## 11.2 Serializer

A new Traffic serializer is NOT required.

Reuse:

```python
serialize_current_traffic_summary(...)
```

from:

```text
app/admin_web/current_traffic_serialization.py
```

Although the module docstring historically references Home Traffic v1, the actual serializer is already domain-neutral:

```text
CurrentSiteTraffic
→ explicit safe current Traffic DTO
```

No Home-specific UI fields are embedded in this summary DTO.

Therefore:

```text
Home Current Traffic
and
Traffic Current Network Throughput
```

must use the same serializer function.

No serializer copy is allowed.

---

# 12. Existing factual Home coupling

Current `AdminQueryService.current_traffic_summary()` uses policy values stored under existing legacy Admin config names:

```text
home_traffic_fresh_max_age_seconds
home_traffic_stale_max_age_seconds
home_traffic_max_ap_skew_seconds
```

Current accepted defaults:

```text
fresh max age = 90s
stale/unavailable boundary = 180s
max AP skew = 60s
```

For `TRAFFIC-01 v1` these values remain the one shared Current Traffic policy.

DO NOT introduce a second set such as:

```text
TRAFFIC_CURRENT_FRESH...
TRAFFIC_CURRENT_STALE...
```

because that would allow Home and Traffic to produce different freshness/value results from one source snapshot.

Legacy field naming is accepted as an implementation naming debt.

A future domain-neutral config rename, if desired, must be:

```text
semantic-preserving
backward-compatible
separately reviewed
```

and is not required by this TASK.

---

# 13. Mandatory cross-surface identity with Home

For identical:

```text
site_id
canonical complete cycle
evaluated_at policy context
fresh/stale thresholds
max AP skew
source selection
```

must hold:

```text
Traffic Section Current Network Throughput
=
Home Traffic Now
```

for:

```text
cycle_id
selected_source

download_mbps
upload_mbps
total_mbps

freshness_status
freshness_reason

coverage_status
coverage_reasons

source selection reason
relevant quality/provenance counters
```

No independent frontend calculation may recompute:

```text
Total = Download + Upload
```

from a different source contract.

The backend DTO already contains `total_mbps`; browser displays it.

---

# 14. Traffic page integration

Dependency:

```text
TRAFFIC-00 accepted Traffic page shell
```

Expected page:

```text
GET /admin/sites/<site_id>/traffic
```

Expected page key:

```text
traffic
```

`TRAFFIC-01` inserts its functional panel into that existing page.

Conceptual first panel:

```text
Current Network Throughput

[ Download Now ] [ Upload Now ] [ Total Now ]

Source: Wired / LAN fallback
Freshness: Fresh / Stale / Unavailable
Coverage: Complete / Partial / None
```

No historical graph in this TASK.

---

# 15. Exact new API endpoint

New Traffic product endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Query parameters:

```text
NONE
```

Any query parameter:

```text
400 invalid_request
```

Reason for new path:

1. Master Roadmap reserves `/traffic/...` namespace.
2. Existing endpoint:

```text
/admin/api/v1/sites/<site_id>/current-traffic/summary
```

is currently gated by:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED
```

and therefore cannot be the canonical Traffic Section route.
3. The new route reuses the same query method + same serializer rather than creating a second calculation.

Existing Home route remains unchanged.

---

# 16. Route/gate reuse architecture

Existing route helper currently ties Current Traffic HTTP exposure to:

```text
config.home_traffic_enabled
```

For the new Traffic route, preferred narrow refactor:

```text
domain-neutral current-Traffic HTTP execution helper
        │
        ├── Home gate:
        │   WEB_ADMIN_HOME_TRAFFIC_ENABLED
        │
        └── Traffic gate:
            WEB_ADMIN_TRAFFIC_ENABLED
```

Both gates then invoke the same operation:

```python
service.current_traffic_summary(
    g.admin_principal,
    selected_site,
)
```

and use the same:

```text
Admin authentication
Site resolver
AdminAccessPolicy
query semaphore
deadline
response-size enforcement
error mapping
telemetry shape
```

Do not duplicate the full route error-control block if a small parameterization of the existing helper can preserve Home behavior.

---

# 17. API envelope

Use existing Admin API success envelope.

`result` MUST be exactly the accepted output of:

```python
serialize_current_traffic_summary(...)
```

No Traffic-specific reinterpretation layer.

---

# 18. Immutable summary DTO

The current accepted serialized result is the basis of the TRAFFIC-01 API.

Conceptual exact structure:

```text
result
├── snapshot
├── freshness_policy
├── traffic
├── source_selection
└── coverage
```

## 18.1 `snapshot`

Product-safe/current source identity:

```text
source_kind
cycle_id
complete
evaluated_at
observed_at
newest_observed_at
age_seconds
source_skew_seconds
freshness_status
freshness_reason
latest_attempt_state
latest_attempt_result
latest_attempt_at
using_previous_complete_snapshot
selected_source
selection_reason
empty_population
```

No raw DB path.

No Omada token.

No provider payload.

No exception text.

## 18.2 `traffic`

```json
{
  "download_mbps": "<float|null>",
  "upload_mbps": "<float|null>",
  "total_mbps": "<float|null>",
  "unit": "Mbps"
}
```

Invariant:

```text
if Download and Upload both numeric
→ Total numeric and equal within accepted backend precision

if one direction missing
→ Total = null
```

## 18.3 `source_selection`

```text
primary_source = wired
selected_source = wired | lan | null
selection_reason
source_mixing_allowed = false
wired_pair_valid_ap_count
lan_pair_valid_ap_count
```

Browser MUST NOT expose a control that modifies this.

## 18.4 `coverage`

Includes:

```text
coverage_status
coverage_reasons
empty_population

total_ap_count
valid_rate_ap_count
valid_download_ap_count
valid_upload_ap_count
missing_rate_ap_count

stale_ap_count
unavailable_ap_count
reset_ap_count
gap_rejected_ap_count
no_baseline_ap_count
source_unavailable_ap_count
invalid_elapsed_ap_count
```

The first functional UI does not need to display every counter, but the API must preserve the existing safe contract for future evidence presentation.

---

# 19. Product-safe presentation mapping

## Source label

```text
selected_source= wired
→ Wired

selected_source=lan
→ LAN fallback

selected_source=null
→ Source unavailable
```

Selection reason may be shown as a secondary safe detail where useful.

Do not show a raw implementation phrase as the main customer-facing label when a clear safe label exists.

## Freshness

```text
fresh
→ Fresh

stale
→ Stale

unavailable
→ Unavailable
```

## Coverage

```text
complete
→ Complete

partial
→ Partial

none
→ Unavailable / No usable coverage
```

Final exact wording may be refined in Web Designer phase, but machine meaning remains unchanged.

---

# 20. Quality is part of TRAFFIC-01

TRAFFIC-01 is quality-aware from first implementation.

Never implement:

```text
12.4 Mbps
```

without the corresponding source state.

Minimum product distinctions:

```text
usable + fresh
stale
partial
unavailable
```

`TRAFFIC-09` later aggregates existing quality. It does not invent quality that was missing from TRAFFIC-01.

---

# 21. Freshness semantics

Current accepted policy:

```text
age <= fresh_max
→ fresh

fresh_max < age <= stale_max
→ stale

age > stale_max
→ unavailable
```

Clock/timestamp integrity anomaly may also yield:

```text
unavailable
```

When aggregate freshness is unavailable:

```text
download_mbps = null
upload_mbps = null
total_mbps = null
```

Do not display old values as current.

Stale values may remain visible only according to the existing accepted service contract and MUST be visibly marked `Stale`.

---

# 22. Coverage semantics

Current machine states:

```text
complete
partial
none
```

Typical reasons include:

```text
missing_direction
missing_pair
temporal_skew
no_valid_rate
empty_population
```

`partial` is a valid quality state and should not become an HTTP error merely because evidence is incomplete.

---

# 23. Zero semantics

Permanent rule:

```text
missing != 0
unavailable != 0
```

Valid zero:

```text
0.0 Mbps
+
accepted evidence
```

remains a real zero.

Special accepted empty AP population contract:

```text
empty_population=true
coverage=complete
selected_source=wired
Download=0.0
Upload=0.0
Total=0.0
```

This must not be converted into unavailable.

---

# 24. No complete snapshot

Existing service behavior is retained.

If no canonical complete-success AP dynamic cycle exists:

```text
HTTP 200
```

with product result representing:

```text
cycle_id = null
selected_source = null
coverage_status = none
freshness_status = unavailable
traffic values = null
selection_reason = no_complete_snapshot
freshness_reason = no_complete_snapshot
```

Reason:

```text
no trustworthy current snapshot
```

is a product quality state, not necessarily a DB/service exception.

Browser shows unavailable state and `—`, not `0 Mbps`.

---

# 25. Source integrity failure

Contradictory persisted facts, DB/schema failure or invalid source integrity:

```text
CurrentTrafficSourceUnavailable
→ AdminQueryUnavailable
→ HTTP 503 source_unavailable
```

Do not expose internal failure text.

Do not attempt fallback Omada calls.

---

# 26. HTTP failure/error mapping

Canonical Traffic current route behavior:

```text
401 authentication_required
→ Admin session absent/expired

403 site_forbidden
→ Site not authorized

404 not_found
→ WEB_ADMIN_TRAFFIC_ENABLED=false

400 invalid_request
→ invalid Site syntax / any forbidden query parameter

429 concurrency_limit
→ shared Admin query budget occupied
→ Retry-After: 1

503 query_deadline
→ shared query deadline exceeded

503 source_unavailable
→ Current Traffic source/service unavailable

503 response_too_large
→ serialized response exceeds Admin response budget

500 internal_error
→ unexpected sanitized internal route failure
```

No raw traceback/provider/SQLite text in API response.

---

# 27. Security / Site boundary

Reuse existing Admin security.

Mandatory:

```text
existing Admin session cookie
existing HTTPS requirement
existing allowed-source-network boundary
existing Site resolver
existing AdminAccessPolicy
same-origin GET API
no new browser token
```

Capability:

```text
admin.read.overview
```

for Site current summary.

No Analytics bearer token in browser.

No CSRF token required for this read-only GET.

No cross-Site cache or state.

---

# 28. Query / concurrency / response bounds

Reuse existing Admin controls.

Repository defaults currently include:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES = 2
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
WEB_ADMIN_MAX_RESPONSE_BYTES = 1048576
```

TRAFFIC-01 does not create another semaphore/deadline.

Current request:

```text
one Site summary
no AP list
no pagination
no historical range
```

Therefore no unbounded AP rows are exposed to browser.

Any future AP list/history belongs to later Traffic TASKs.

The backend uses the existing bounded CurrentTrafficReadService/read gateway contract over one canonical persisted AP cycle.

---

# 29. Refresh behavior

TRAFFIC-01 is a current snapshot reader.

Browser refresh:

```text
GET persisted current result
```

It NEVER triggers acquisition.

Preferred Traffic page operational behavior after `TRAFFIC-00`:

```text
manual Refresh button
+
periodic refresh
+
no overlapping same-panel request
+
AbortController ownership
+
generation protection
+
pause while document.hidden
+
bounded retry/backoff
```

These patterns should reuse the Traffic page orchestration contract created by `TRAFFIC-00`.

Recommended v1 page refresh cadence:

```text
default 60 seconds
allowed operational range 60..300 seconds
```

Recommended browser request timeout:

```text
default 20 seconds
must exceed WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

Important:

```text
Browser refresh cadence
!=
Observation acquisition cadence
```

Repeated browser reads may legitimately return the same `cycle_id`.

That is not an error.

---

# 30. Refresh configuration ownership prerequisite

Because `TRAFFIC-00` is not yet implemented, final ownership of Traffic-page presentation refresh settings must be established there.

Preferred foundation contract:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

These are page/orchestration settings, not source semantic policy.

They MUST NOT replace or duplicate:

```text
Current Traffic fresh/stale/skew policy
```

which remains shared with Home through the existing accepted policy.

If `TRAFFIC-00 FINAL` chooses different names or a shared page coordinator contract, `TRAFFIC-01 FINAL` must bind to that exact accepted implementation.

---

# 31. Feature activation

Master feature flag from Roadmap:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Repository-safe default:

```text
false
```

TRAFFIC-01 adds no subordinate per-panel feature flag.

Required invariant:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
```

Traffic feature flag controls Traffic product exposure only.

It does not disable:

```text
CurrentTrafficReadService
Observation
Analytics
Home Current Traffic
```

---

# 32. Home Traffic feature independence

Existing Home endpoint is currently controlled by:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED
```

New Traffic endpoint is controlled by:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

Required independent behavior:

```text
Home Traffic=false
Traffic=true
→ Traffic current endpoint may work

Home Traffic=true
Traffic=false
→ Home Current Traffic continues to work

both=true
→ both surfaces return semantically identical result
```

Shared backend service lifecycle must not depend on either individual presentation flag.

---

# 33. Failure isolation

Failure of `TRAFFIC-01` must not:

```text
break Traffic shell
break Home
break Home Current Traffic
change Observation collection
change Analytics readiness
affect Captive Portal/auth
affect Visit Lifecycle
```

Within Traffic page:

```text
Current Network Throughput unavailable
```

must remain a panel-level failure.

Later independent Traffic panels must remain able to load.

---

# 34. Minimal functional UI contract

TRAFFIC-01 must provide stable hooks for later visual design.

Recommended semantic hooks:

```text
traffic-current
traffic-current-state
traffic-current-state-title
traffic-current-state-message

traffic-current-download
traffic-current-upload
traffic-current-total

traffic-current-source
traffic-current-freshness
traffic-current-coverage

traffic-current-updated
```

Exact HTML wrappers/classes are implementation detail.

IDs/data hooks used by JS become contract and must be covered by frontend tests.

Functional layout may remain simple.

No final design redesign is required.

---

# 35. Functional panel states

Minimum visible states:

## Loading

```text
Loading current network throughput…
```

## Fresh + complete

Example:

```text
Download Now  12.4 Mbps
Upload Now     3.7 Mbps
Total Now     16.1 Mbps

Wired · Fresh · Complete
```

## Fresh + partial

Numeric directions are displayed only where numeric evidence exists.

Example:

```text
Download Now  12.4 Mbps
Upload Now     —
Total Now      —

Wired · Fresh · Partial
```

## Stale

Values may be displayed only if present in accepted DTO and clearly marked:

```text
Stale
```

## Unavailable

```text
—
Source unavailable / current evidence unavailable
```

No synthetic zero.

---

# 36. Product helper copy

Functional implementation should include a persistent compact helper:

```text
Derived from persisted AP traffic counters.
May include local/service traffic and is not an Internet-only measurement.
```

This is an existing accepted meaning and should remain semantically identical to Home Current Traffic.

---

# 37. Application/read architecture

No new backend layer is justified.

Required path:

```text
analytics_runtime.current_traffic_service
        ↓
AdminWebRuntime
        ↓
AdminQueryService.current_traffic_summary()
        ↓
serialize_current_traffic_summary()
        ↓
Traffic route
        ↓
Traffic frontend
```

Current Traffic service remains optional/fail-open relative to unrelated Admin/Analytics capabilities.

No loopback HTTP.

No duplicate source DB opening inside Traffic UI modules.

---

# 38. Runtime composition

Current Admin runtime already injects:

```text
analytics_runtime.current_traffic_service
→ AdminQueryService.current_traffic_read_service
```

TRAFFIC-01 does not require a second runtime service.

The Traffic route obtains the existing:

```text
runtime.query_service
```

after normal Admin/Site/feature gates.

---

# 39. Existing serializer is canonical Admin Current Traffic DTO

Current serializer already validates:

```text
source_kind
Site consistency
cycle identity
freshness enum
coverage enum
source enum
selection reason
count invariants
numeric finiteness
nonnegative values
total arithmetic consistency
empty population contract
no-snapshot contract
latest-attempt contract
```

TRAFFIC-01 must not weaken those validations for UI convenience.

---

# 40. Native Omada research endpoints — explicit non-dependency

TRAFFIC-01 does NOT call/use as product source:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
dashboard/wifi-summary
dashboard/most-active-eaps
```

They remain:

```text
research / validation / reference evidence
```

`traffic-activities` is historical volume buckets, not superior current directional Site throughput.

No acquisition change is justified by TRAFFIC-01.

---

# 41. Allowed implementation files — after TRAFFIC-00 acceptance

Exact list must be rebound to actual `TRAFFIC-00` merge, but expected allowlist is narrow.

Expected existing-file changes:

```text
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/traffic.html
```

Possible narrow changes only if required by accepted `TRAFFIC-00` composition:

```text
app/admin_web/pages.py
app/admin_web/config.py
app/settings.py
app/config.py
.env.example
app/admin_web/runtime.py
```

However these foundation/config files SHOULD already be completed by `TRAFFIC-00`.

If TRAFFIC-01 needs to create the Traffic page/nav/master flag itself:

```text
STOP
→ prerequisite TRAFFIC-00 is incomplete
```

Expected new tests:

```text
tests/admin_web/test_traffic_current.py
tests/admin_web/test_traffic_current_frontend.py
```

Existing Traffic tests may be extended where semantic equality is most naturally proven:

```text
tests/admin_web/test_home_traffic.py
```

but only narrowly and without changing Home product behavior.

---

# 42. Files expected to remain unchanged

No change should be required in:

```text
app/analytics/current_traffic.py
app/analytics/source_gateway.py
app/analytics/models.py
app/observations/**
```

No change should be required in:

```text
app/admin_web/current_traffic_serialization.py
app/admin_web/query_service.py
```

because the existing query method + serializer should be reused directly.

If implementation finds that modifying the canonical Current Traffic service/calculation is required:

```text
STOP
→ return factual contradiction for Architect/Tech Lead review
```

---

# 43. Forbidden files / scope

Do NOT change:

```text
app/controllers/omada*
OmadaProvider behavior
Observation collectors
Observation rate formulas
Observation schema
Current State acquisition/schema
Visit Lifecycle acquisition/schema
Auth/CAPPORT
Pending Session Cleaner
Loki
Grafana
Alloy
production systemd
reverse proxy
requirements/dependencies
```

Do not change Home template/layout for this TASK:

```text
app/admin_web/templates/admin/home.html
```

Do not redesign existing Home coordinator.

Do not introduce Traffic telemetry in Loki/Grafana as product dependency.

---

# 44. Coder focused/minimal tests

Coder test responsibility is limited to the TASK/module.

Expected focused command after actual test files exist:

```bash
python -m pytest -q \
  tests/admin_web/test_traffic_current.py \
  tests/admin_web/test_traffic_current_frontend.py
```

If narrow changes extend existing shared Current Traffic route/serializer tests:

```bash
python -m pytest -q \
  tests/admin_web/test_traffic_current.py \
  tests/admin_web/test_traffic_current_frontend.py \
  tests/admin_web/test_home_traffic.py
```

Only use the second form if `test_home_traffic.py` is directly modified or needed to prove non-regression of the shared helper.

Relevant static checks on changed code:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
python -m compileall -q app/admin_web

git diff --check
```

If frontend tests use the existing Node-based harness, run only the dedicated Traffic current frontend file according to repository test convention.

Coder does NOT run:

```text
unrelated Admin modules
cross-module suite
full repository pytest
Central Lab gate
```

---

# 45. Required automated cases

Focused tests must cover at minimum:

## Page/API activation

```text
Traffic flag false
→ Traffic current API 404

Traffic flag true
→ endpoint active

Home Traffic flag false + Traffic true
→ Traffic endpoint still works

Home Traffic true + Traffic false
→ existing Home endpoint still works
```

## Security

```text
no session → 401
forbidden Site → 403
unexpected query parameter → 400
same-origin browser contract
```

## Success DTO

```text
fresh complete wired
fresh complete lan fallback
partial
stale
no complete snapshot
empty population valid zero
```

## Errors

```text
query busy → 429 + Retry-After: 1
query deadline → 503 query_deadline
source integrity failure → 503 source_unavailable
response size enforcement
unexpected sanitized failure
```

## Browser

```text
loading
fresh/complete render
partial render
stale render
unavailable render
manual refresh
timer refresh
no overlap
hidden-tab pause
request abort/generation protection
accepted zero renders 0.0 Mbps
null renders —
```

---

# 46. Mandatory cross-surface equality test

This is a release-critical invariant.

With both product flags enabled and one identical fake/source result:

```text
GET /admin/api/v1/sites/<site_id>/current-traffic/summary
```

and:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

must return identical:

```text
result.snapshot
result.freshness_policy
result.traffic
result.source_selection
result.coverage
```

No normalization differences allowed.

Only outer route metadata may differ if existing generic envelope includes route-independent values such as request IDs outside `result`.

Recommended assertion:

```text
home_response["result"]
==
traffic_response["result"]
```

---

# 47. Central Lab acceptance

Owner + Tech Lead / Central Lab own official acceptance.

Required gates:

## A. Exact-artifact focused verification

Re-run the Coder-focused tests on the candidate artifact as appropriate.

## B. Cross-surface semantic equality

For identical persisted/source fixture or controlled source result:

```text
Home Current Traffic
=
Traffic Current Network Throughput
```

Verify:

```text
cycle_id
selected_source
Download
Upload
Total
freshness
coverage
selection reason
quality/provenance
```

## C. Feature independence

Verify:

```text
Home flag off / Traffic on
Home flag on / Traffic off
both on
both off
```

No shared service shutdown.

## D. Broader regression

Central Lab runs the approved broader/full repository gate for the exact candidate.

Pre-existing unrelated baseline failures are evaluated by differential policy and are not silently fixed inside TRAFFIC-01.

## E. Browser acceptance

Authenticated real Admin session:

```text
Traffic page loads
Current panel loads
manual refresh works
periodic refresh works
no Home UI change
no Omada request from browser
no stale data displayed as fresh
```

Official PASS/FAIL belongs to Owner + Tech Lead.

---

# 48. Deployment vs activation

Permanent:

```text
merge/deploy != activation
```

Repository default:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Preferred sequence:

```text
1. TRAFFIC-00 merged/deployed with Traffic master flag false.
2. TRAFFIC-01 merged/deployed with master flag still false.
3. Central Lab acceptance on exact candidate.
4. Owner enables WEB_ADMIN_TRAFFIC_ENABLED=true.
5. Controlled restart/reload according to normal production procedure.
6. Production verification.
```

No subordinate `TRAFFIC-01` feature flag is required.

To avoid accidental early exposure, Traffic master flag SHOULD remain false in production until `TRAFFIC-01` has passed acceptance, unless Owner explicitly accepts activation of the empty TRAFFIC-00 shell.

---

# 49. Production activation checks

After Owner-controlled activation:

```text
Traffic nav visible
Traffic page 200
Traffic current endpoint 200 or legitimate product-quality 200 state
Home remains unchanged
Home Traffic behavior unchanged
Observation continues accumulating
no new Omada request path from Admin
```

If source facts are currently unavailable, activation may legitimately show an unavailable Current Network Throughput panel without affecting portal/runtime.

---

# 50. Rollback

Fast operational rollback:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Expected result:

```text
Traffic nav/page/API exposure disabled
Home unchanged
CurrentTrafficReadService remains available to Home
Observation unchanged
no data migration required
```

Code rollback may revert only TRAFFIC-01 changes after disabling the master flag.

No DB rollback.

No schema rollback.

No Omada rollback.

---

# 51. Explicit out of scope

TRAFFIC-01 does NOT implement:

```text
TRAFFIC-00 foundation itself

Historical Network Traffic
24h / 7d graphs
Period Average/Peak
Peak Load Period
Traffic by AP history
AP Traffic Share
Online Guests Traffic
Guest Session Traffic
Consolidated Traffic Evidence panel
30-day range
Heatmap
Period Comparison

Home summary changes
Home Top Consumers
Home redesign

new Omada historical acquisition
traffic-activities product dependency
traffic-distribution product dependency
SSID Traffic
WAN/Gateway Traffic
billing
```

Also out of scope:

```text
AP current list inside Traffic page
```

unless later Roadmap TASK explicitly needs it.

TRAFFIC-01 is Site summary only.

---

# 52. No preliminary backend/refactor increment required

Current repository already contains:

```text
CurrentTrafficReadService
Admin runtime injection
AdminQueryService.current_traffic_summary()
explicit safe current Traffic serializer
shared query execution controls
Home reference implementation
```

Therefore no separate:

```text
TRAFFIC-01-READ
```

or backend calculation TASK is justified.

Only narrow HTTP/page integration is required after `TRAFFIC-00`.

---

# 53. Accepted factual deltas from original Roadmap assumptions

## Delta 1 — TRAFFIC-00 not yet implemented

Result:

```text
TRAFFIC-01 implementation blocked.
```

## Delta 2 — generic Current Traffic application contract already exists

The repository is further along than a naive new-page implementation would assume.

No new `AdminQueryService` read method is necessary.

## Delta 3 — current route gate is Home-specific

Existing:

```text
/current-traffic/summary
```

is gated by:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED
```

Therefore Traffic Section needs its own namespace route and Traffic feature gate.

## Delta 4 — Current Traffic policy config names remain Home-prefixed

Semantics are correct and already accepted.

For v1:

```text
reuse the same policy
do not duplicate policy
```

A naming cleanup is not required for product implementation.

---

# 54. Acceptance criteria

TRAFFIC-01 is accepted only if all are true:

1. `TRAFFIC-00` prerequisite is merged and accepted.
2. Exact implementation baseline is rebound before coding.
3. Traffic page contains functional Current Network Throughput panel.
4. `GET /admin/api/v1/sites/<site_id>/traffic/current` exists.
5. Endpoint uses existing `AdminQueryService.current_traffic_summary()`.
6. Endpoint returns existing `serialize_current_traffic_summary()` result.
7. No second traffic calculation exists.
8. No second Current Traffic freshness/source policy exists.
9. Home endpoint and Traffic endpoint produce identical `result` for identical source/context.
10. Source machine enum remains only `wired|lan|null`.
11. Browser cannot select source family.
12. Radio remains excluded from Site total.
13. `wired_activity_raw` is not used as directional traffic replacement.
14. Fresh/stale/partial/unavailable are correctly visible.
15. Missing/unavailable never becomes numeric zero.
16. Accepted `0.0 Mbps` remains a valid zero.
17. No Admin/Browser → Omada path exists.
18. No new DB/schema/collector exists.
19. Shared Admin concurrency/deadline/response bounds remain authoritative.
20. Failure of Current Network Throughput does not break Home/Portal/other Traffic shell.
21. Traffic flag and Home Traffic flag are independently product-gated.
22. Home UI/layout is unchanged.
23. Focused Coder tests pass.
24. Owner + Tech Lead / Central Lab issue official acceptance PASS.
25. Production activation remains a separate Owner-controlled action.

---

# 55. Unresolved questions requiring Owner / Tech Lead review

The semantic architecture has no unresolved A/B choice.

One prerequisite integration item must be finalized through `TRAFFIC-00`:

## Q1. Traffic page refresh settings ownership

Recommended foundation contract:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

or equivalent accepted `TRAFFIC-00` page-orchestration configuration.

Decision requirement:

```text
TRAFFIC-00 FINAL must establish exact field names/hooks
before TRAFFIC-01 FINAL implementation authorization.
```

This does NOT reopen Current Traffic source freshness policy.

## Q2. Sequencing confirmation

Roadmap already says:

```text
TRAFFIC-00 → TRAFFIC-01
```

Current repository confirms `TRAFFIC-00` is absent.

Therefore recommended decision:

```text
prepare / implement / accept TRAFFIC-00 first,
then rebind this TRAFFIC-01 DRAFT to its merge SHA.
```

If Owner wants a combined implementation instead, Roadmap sequencing must be explicitly amended before FINAL.

---

# 56. Recommended next action

Current DRAFT status:

```text
ARCHITECTURE:
READY FOR OWNER + TECH LEAD REVIEW

IMPLEMENTATION:
BLOCKED BY TRAFFIC-00

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED
```

Recommended project sequence:

```text
1. Review this TRAFFIC-01 DRAFT.
2. Prepare TRAFFIC-00 DRAFT.
3. Finalize + implement + accept TRAFFIC-00.
4. Re-check origin/main.
5. Rebind TRAFFIC-01 to exact TRAFFIC-00 merge SHA.
6. Apply review corrections.
7. Issue TRAFFIC-01 FINAL.
8. Only then authorize Coder.
```

---

# 57. Final DRAFT statement

`TRAFFIC-01` is deliberately a thin product integration over an already accepted semantic owner:

```text
CurrentTrafficReadService
```

The key design requirement is not to calculate Traffic again.

The implementation must make the new Traffic Section a second product consumer of exactly the same accepted Current Traffic result already used by Home:

```text
one source
one calculation
one serializer
two product surfaces
zero semantic drift
```

**Status:** `DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`
