# TASK-TRAFFIC-00 — Traffic Section Foundation — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Status:** `FINAL — READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL; REQUIRES SEPARATE OWNER AUTHORIZATION`  
**Production activation:** `NOT GRANTED; SEPARATE OWNER-CONTROLLED ACTION`  
**Date:** 2026-08-29

---

## 0. Executive decision

`TRAFFIC-00` создаёт только самостоятельную foundation-границу:

```text
Admin Console → Traffic
```

В scope:

```text
AdminPage: traffic
/admin/sites/<site_id>/traffic
Traffic navigation entry
Traffic template/page shell
WEB_ADMIN_TRAFFIC_ENABLED=false
safe Site-scoped page context
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS
one shared Traffic frontend coordinator
shared global loading/error boundary
shared panel region
```

Не в scope:

```text
Current Network Throughput
Historical Network Traffic
Traffic by AP
Online Guests
Guest Session Traffic
Traffic Evidence metrics
Traffic calculations
Traffic APIs with product data
new read model
new acquisition
new DB/schema
Omada calls
Home changes
```

Canonical outcome:

```text
one Traffic page
+
one Traffic page lifecycle owner
+
many future independently failing panels
+
zero product calculations in Foundation
```

---

## 1. Verified current baseline

Current `origin/main` проверен перед FINAL:

```text
main = c719525a1a2a324a0959597c993b99a82bf465b0
tree = 2fd3de8d3ff82559d53e931c3911334ac61fc868
```

Последний commit — PR #82:

```text
Docs: canonicalize Central Lab testing ownership
```

Runtime Traffic/Admin implementation этим PR не менялся.

На current main отсутствуют:

```text
WEB_ADMIN_TRAFFIC_ENABLED
AdminPage("traffic", ...)
app/admin_web/templates/admin/traffic.html
/admin/sites/<site_id>/traffic
Traffic navigation entry
dedicated Traffic frontend coordinator
```

Поэтому `TRAFFIC-00` — реальный отсутствующий prerequisite.

---

## 2. Roadmap binding

Canonical order:

```text
TRAFFIC-00
→ TRAFFIC-01
→ TRAFFIC-02-READ
→ TRAFFIC-02
→ ...
```

`TRAFFIC-00` остаётся отдельным acceptance unit.

Не включать сюда `TRAFFIC-01`.

После merge + Central Lab acceptance этого TASK `TRAFFIC-01` должен быть rebound на exact новый `origin/main` SHA/tree.

---

## 3. Goal

Foundation должен обеспечить:

1. отдельную Site-scoped Traffic page;
2. master product feature gate;
3. отсутствие Traffic exposure при disabled;
4. safe page context;
5. единый frontend lifecycle;
6. panel-level failure isolation;
7. отсутствие зависимости shell от конкретного Traffic data service;
8. отсутствие изменений Home.

---

## 4. Exact page identity

Добавить:

```python
TRAFFIC = AdminPage(
    "traffic",
    "Traffic",
    "admin/traffic.html",
)
```

Canonical:

```text
page.key = traffic
page.title = Traffic
template = admin/traffic.html
```

---

## 5. Exact HTML route

Добавить:

```text
GET /admin/sites/<site_id>/traffic
```

Canonical security / feature-gate ordering:

```text
authenticated Admin session
        ↓
resolve canonical Site context
        ↓
authorize admin.read.context
        ↓
check WEB_ADMIN_TRAFFIC_ENABLED
        ↓
render Traffic page
```

То есть master Traffic feature gate расположен **за существующей authentication/Site authorization boundary** и не создаёт альтернативный Site/security path.

Required outcomes:

```text
no session
→ 302 /admin/login?next=...

invalid Site syntax
→ 400 invalid_request

forbidden Site
→ 403 site_forbidden

authorized Site + Traffic disabled
→ 404 not_found

authorized Site + Traffic enabled
→ 200 Traffic page
```

Preferred implementation:

```text
narrow extension of existing _site_page(...)
with an optional feature gate
```

или эквивалентный минимальный helper, который всё равно использует существующие resolver/policy contracts.

Запрещено:

```text
Traffic-specific Site resolver
Traffic-specific authorization implementation
feature check before existing Site/security boundary
```

## 6. Security / Site boundary

Reuse existing:

```text
Admin session
HTTPS requirement
source-network allowlist
AdminSiteContextResolver
AdminAccessPolicy
admin.read.context
Site allowlist
CSP
Cache-Control: no-store
```

Forbidden:

```text
new auth mode
new token
browser bearer token
Traffic-specific Site resolver
provider credential in page context
```

---

## 7. Master feature flag

New repository setting:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Settings key:

```text
web_admin_traffic_enabled
```

`AdminWebConfig` field:

```text
traffic_enabled: bool
```

Rule:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
```

Traffic product flag controls product exposure only.

It MUST NOT start/stop:

```text
Observation
Analytics
CurrentTrafficReadService
Current State
Visit Lifecycle
Home
OmadaProvider
```

Canonical:

```text
Traffic product flag
!=
shared service lifecycle switch
```

---

## 8. Disabled behavior

When:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

required:

```text
Traffic nav absent
direct Traffic page → 404
Traffic coordinator inactive
no Traffic frontend work
```

Future `/traffic/...` product APIs must use the same master gate, but `TRAFFIC-00` adds no product API.

---

## 9. Enabled-but-empty behavior

With Traffic flag enabled before any later panel exists:

```text
Traffic page → 200
```

and only foundation-safe state is shown.

Recommended text:

```text
Traffic section is ready.
No Traffic panels are enabled yet.
```

Do not display fabricated:

```text
0 Mbps
No traffic
No clients
No history
```

because no product source has been read.

Recommended production state after merge:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

until at least `TRAFFIC-01` is accepted, unless Owner explicitly wants the empty shell exposed.

---

## 10. Navigation

В shared:

```text
admin/base.html
```

добавить Site-aware link:

```text
Traffic
→ /admin/sites/{{ site_id }}/traffic
```

Visible only if:

```text
traffic_enabled == true
```

Active only if:

```text
page.key == "traffic"
```

Critical shared-render invariant:

```text
AdminWebConfig.traffic_enabled
→ _site_page / shared render_admin_page(...)
→ every Site Admin page
→ admin/base.html
```

Следовательно `traffic_enabled` является **shared Admin page render context**, а не Traffic-page-only context.

При:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
```

Traffic link должен быть виден из:

```text
Home
Devices
Device
Visits
Observations
Traffic
```

При:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

link отсутствует на всех этих страницах.

Traffic-only orchestration values:

```text
traffic_refresh_seconds
traffic_request_timeout_seconds
```

могут выводиться как `data-*` только при:

```text
page.key == "traffic"
```

Existing navigation/Home layout semantics не меняются.

## 11. Safe page context

Shared render context for **all Site Admin pages**:

```text
traffic_enabled
```

Traffic page additionally receives:

```text
page
site_id
username
csrf_token
runtime_state
traffic_refresh_seconds
traffic_request_timeout_seconds
```

Traffic-page dataset only:

```text
data-page="traffic"
data-site-id="<authorized Site>"
data-api-base="/admin/api/v1/sites/<site_id>"
data-runtime-state="..."
data-traffic-enabled="true"
data-traffic-refresh-seconds="60"
data-traffic-request-timeout-seconds="20"
```

Do not emit Traffic refresh/timeout dataset to unrelated pages unless the existing common template requires harmless generic presence and tests prove unchanged behavior.

Never expose:

```text
DB paths
Omada URL/ID
OAuth secrets
Analytics bearer token
provider object
raw settings mapping
```

## 12. Refresh ownership — FINAL direction for review

`TRAFFIC-00` owns page-level orchestration settings:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

Bounds:

```text
refresh:
60 .. 300 seconds

request timeout:
5 .. 60 seconds
```

Required:

```text
traffic_request_timeout_seconds
>
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

These are browser/page settings only.

They are NOT:

```text
Observation cadence
Current Traffic fresh/stale policy
AP skew policy
historical bucket size
historical range
Visit freshness
```

---

## 13. Config plumbing

Expected path:

```text
app/config.py
→ app/settings.py
→ app/admin_web/config.py
→ AdminWebConfig
→ render_admin_page()
→ base.html dataset
→ Traffic coordinator
```

Add to `.env.example`:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

No production env change in this TASK.

---

## 14. No Traffic backend/runtime service

Do NOT create:

```text
TrafficRuntime
TrafficService
TrafficReadService
TrafficRepository
TrafficDatabase
```

No process worker.

No startup/shutdown dependency.

Foundation is Admin Web infrastructure only.

---

## 15. Traffic template

New:

```text
app/admin_web/templates/admin/traffic.html
```

Extends:

```text
admin/base.html
```

Required functional hooks:

```text
traffic-global-state
traffic-global-state-title
traffic-global-state-message
traffic-empty-state
traffic-panels
```

Reuse existing:

```text
refresh-button
```

No inline script.

No fake metric hooks such as Download/Upload/History; those belong to later TASK.

No final visual redesign.

---

## 16. Shared global vs panel state

`traffic-global-state` is only for page-wide conditions:

```text
session expired
Site forbidden
frontend orchestration integrity failure
```

Ordinary future panel failure:

```text
one panel 503 / timeout / invalid DTO
```

must remain panel-local.

Canonical:

```text
one panel failure
!=
Traffic page failure
```

---

## 17. Empty state

Initial coordinator state:

```text
0 registered panels
```

means:

```text
traffic-empty-state visible
Refresh disabled
no initial load
no timer
no product fetch
```

Coordinator registration is dynamic.

After the **first successful `registerPanel(...)`**:

```text
empty state hidden
Refresh enabled
panel becomes eligible for one initial load
```

No second `start()` call is required.

Canonical initial-load invariant:

```text
every successfully registered panel
→ one initial load
```

This is independent of:

```text
autoRefresh
```

Therefore:

```text
autoRefresh=true
→ initial load
→ subsequent periodic refresh

autoRefresh=false
→ initial load
→ no periodic refresh
→ later execution only through coordinator-owned manual/panel-specific trigger
```

Foundation intentionally does not add `loadOnInit`; initial load is default behavior.

## 18. Dedicated Traffic frontend coordinator

Create in:

```text
app/admin_web/static/admin.js
```

Canonical object:

```text
window.CaptivPortalTrafficCoordinator
```

This is presentation/orchestration infrastructure, not a semantic/read owner.

---

## 19. Generic Admin controller handoff

Current generic `admin.js` controller owns `refresh-button` for existing core pages.

Traffic page must have only one refresh owner.

Preferred narrow change in generic `configure()`:

```text
if context.page == "traffic"
→ return before generic Refresh/Load More handlers
```

Then:

```text
CaptivPortalTrafficCoordinator
```

is the sole Traffic page lifecycle owner.

No duplicate Refresh listener.

No duplicate lifecycle.

---

## 20. Coordinator ownership

Coordinator exclusively owns on Traffic page:

```text
panel registry
manual Refresh
periodic scheduler
panel eligibility
per-panel generation
per-panel in-flight ownership
AbortController creation
request timeout
hidden-tab pause
pagehide shutdown
generic retry/backoff
global 401/403 transition
panel failure isolation
```

Later panel TASK MUST NOT build a second:

```text
refresh timer
visibilitychange owner
pagehide owner
AbortController lifecycle owner
generation subsystem
generic backoff subsystem
```

---

## 21. Panel registration API

Foundation exposes a **minimal stable public API**.

Required public operations:

```javascript
registerPanel(spec)
refreshPanel(key, {manual: true})
refreshAll({manual: true})
```

Equivalent exact JS signatures are acceptable if semantics remain identical.

Recommended `registerPanel` spec:

```javascript
{
  key,
  autoRefresh,
  load,
  render,
  renderLoading,
  renderFailure
}
```

Semantics:

```text
key
→ unique stable panel id

autoRefresh
→ controls only subsequent periodic refresh

load(context)
→ async panel-owned product read/validation
→ must use coordinator-provided requestJson
→ must not create private fetch lifecycle

render(value)
→ accepted product result

renderLoading()
→ optional

renderFailure(failure)
→ panel-local safe failure UI
```

Mandatory future-control invariant:

```text
range selector / filter / panel button
→ refreshPanel(key, {manual: true})
→ coordinator
→ generation / eligibility / AbortController / timeout / backoff / requestJson
→ panel load
```

Forbidden:

```text
range selector → panel.load() directly
range selector → fetch() directly
```

`refreshPanel(...)` executes **only the selected registered panel**.

Other panels remain untouched.

It must preserve all same-panel:

```text
overlap protection
generation ownership
abort ownership
Retry-After/backoff rules
```

Public interface should be narrow, e.g.:

```javascript
window.CaptivPortalTrafficCoordinator = Object.freeze({
  registerPanel,
  refreshPanel,
  refreshAll,
})
```

Internal state such as controllers/timers/generation/failure counters remains private.

## 22. Coordinator load context

Panel loader receives only:

```text
siteId
apiBase
manual
generation
requestJson
```

Conceptual:

```javascript
{
  siteId,
  apiBase,
  manual,
  generation,
  requestJson
}
```

Panel never receives cookie/token/provider/DB handle.

---

## 23. Shared request helper

Traffic coordinator owns an **additive private request helper**.

Do NOT globally rewrite existing Admin:

```text
requestJson()
classifyHttp()
```

in a way that changes Devices/Visits/Observations/Home behavior.

Preferred:

```text
Traffic-private requestJson / classifyTrafficHttp
```

inside the Traffic coordinator, or additive shared helpers with proven call-site compatibility.

Traffic request helper performs:

```text
GET
credentials = same-origin
cache = no-store
Accept = application/json
AbortController = coordinator-owned
timeout = traffic_request_timeout_seconds
```

Defense-in-depth URL contract:

preferred input:

```text
relative Site Admin API path
```

or explicitly validate:

```text
resolved URL origin == window.location.origin
```

and that the request is inside expected Admin API namespace:

```text
/admin/api/v1/sites/<current site_id>/
```

Future panel must not be able to use this helper for arbitrary external URL.

Existing CSP remains unchanged; no new CSP relaxation is required.

Forbidden:

```text
cross-origin request
absolute external product URL
Bearer
localStorage
sessionStorage
panel-owned AbortController for the same request
```

## 24. Frontend failure classes

Traffic-private HTTP classification:

```text
session
forbidden
disabled
invalid
busy
timeout
unavailable
unexpected
```

Traffic mapping:

```text
401 → session
403 → forbidden
404 → disabled
400 → invalid
429 → busy
503 + error.code=query_deadline → timeout
other 503 → unavailable
network failure → unavailable
malformed Traffic response envelope → unexpected
```

This mapping is **additive and Traffic-local**.

It MUST NOT change outputs/semantics of the existing generic Admin `classifyHttp(...)` call sites.

Only safe fields may propagate:

```text
kind
HTTP status
error.code
Retry-After
```

No raw exception/SQL/provider/internal URL text.

## 25. Generation and in-flight ownership

Each panel has coordinator-owned:

```text
generation
controller
failure_count
next_eligible_at
```

Each new run:

```text
generation += 1
```

Old generation completion:

```text
ignored
```

At most one active execution per panel.

A new manual run may supersede a clean in-flight execution:

```text
abort reason = superseded
```

Superseded/hidden/pagehide aborts are neutral, not product errors.

---

## 26. Periodic refresh

`autoRefresh` controls only **post-initial periodic behavior**.

All panels receive one initial execution after successful registration.

For:

```text
autoRefresh=true
```

after successful initial/periodic execution:

```text
next eligible =
now + WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
```

For:

```text
autoRefresh=false
```

after initial execution:

```text
no periodic next execution
```

and future reload occurs only through:

```text
refreshPanel(...)
or
refreshAll(...)
```

Coordinator owns one page scheduler targeting earliest eligible periodic panel.

Use:

```text
window.setTimeout
```

Do not use:

```text
setInterval
```

## 27. Manual refresh

Public manual APIs:

```text
refreshAll({manual:true})
refreshPanel(key, {manual:true})
```

`Refresh` page button invokes:

```text
refreshAll({manual:true})
```

Panel-specific future controls invoke:

```text
refreshPanel(key, {manual:true})
```

Rules for both:

- zero panels → safe no-op for `refreshAll`;
- unknown panel key → reject safely / no execution;
- no same-panel overlap;
- may supersede a clean same-panel in-flight request according to coordinator contract;
- active `Retry-After` / backoff remains authoritative;
- manual/range-driven trigger does **not** bypass coordinator eligibility;
- `refreshPanel` never executes unrelated panels.

## 28. Retry/backoff

Generic retryable:

```text
busy
timeout
unavailable
```

Recommended deterministic delay:

```text
max(
  Retry-After,
  refresh_seconds * 2^(failure_count - 1)
)
```

Local exponential part capped at:

```text
300 seconds
```

Server Retry-After above 300 is still respected.

Success resets failure count.

No tight retry loop.

For `disabled` / `invalid` / contract-integrity failure, automatic retry may be suspended until manual refresh/page reload or panel-specific approved behavior.

---

## 29. Hidden/page lifecycle

When `document.hidden`:

```text
clear Traffic scheduler
abort in-flight Traffic panels
reason = hidden
no error rendering
```

When visible:

```text
re-evaluate eligibility
run overdue periodic panels
reschedule
```

On `pagehide`:

```text
stopped = true
clear timer
abort all
reason = pagehide
never schedule again
```

Coordinator is the only Traffic owner of these listeners.

---

## 30. Global failure behavior

Only true page-wide failures may promote global state:

```text
401 authentication_required
403 site_forbidden
```

On global failure:

```text
abort remaining Traffic panel work
pause automatic Traffic refresh
show traffic-global-state
preserve already-rendered independent panel data where safe
```

A panel 429/503/timeout never becomes global page failure.

---

## 31. Future refresh modes

Foundation supports:

```text
autoRefresh=true
autoRefresh=false
```

This is enough for:

```text
current panels → periodic
heavier historical/range panels → manual/range-driven if their TASK chooses
```

No separate scheduler per future panel.

---

## 32. No frontend product calculation

Foundation JS must not calculate:

```text
Mbps
bytes
average
peak
coverage
freshness
source family
share
client traffic
```

Allowed calculations are orchestration-only:

```text
timeout
retry eligibility
generation
registration state
```

---

## 33. No product API in TRAFFIC-00

New Traffic data endpoints:

```text
ZERO
```

Reserve future namespace:

```text
/admin/api/v1/sites/<site_id>/traffic/...
```

Expected first product endpoint belongs to `TRAFFIC-01`, not this TASK.

Do not create placeholder `/traffic/summary` or empty JSON API.

---

## 34. No source/read dependency

Traffic shell must not require:

```text
CurrentTrafficReadService
historical Traffic service
Current State service
Visit reader
OmadaProvider
```

to render.

Future panel availability is panel-local.

---

## 35. Home remains frozen

Do not change:

```text
admin/home.html
Home API contracts
Home Traffic behavior
Home Activity
Home Health
Home AP24
Home coordinator semantics
```

Only shared allowed UI change:

```text
base.html
```

for Traffic nav and Traffic-specific dataset plumbing.

---

## 36. Web Designer

Web Designer is not part of this TASK.

Foundation uses existing CSS primitives and simple functional layout.

Final Traffic visual design comes only after functional semantic/API acceptance.

---

## 37. Expected implementation files

Expected changed:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/base.html
```

New:

```text
app/admin_web/templates/admin/traffic.html
tests/admin_web/test_traffic_foundation.py
tests/admin_web/test_traffic_foundation_frontend.py
```

Expected unchanged:

```text
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/current_traffic_serialization.py
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.css
app/analytics/**
```

If an expected-unchanged file becomes necessary, Coder must report exact reason rather than silently expand scope.

---

## 38. Forbidden scope

No changes in:

```text
Observation
Current State
Analytics calculations
Visit Lifecycle
Auth/CAPPORT
OmadaProvider/controllers
Pending Session Cleaner
Visitor Registry
Loki/Grafana/Alloy
systemd
reverse proxy
requirements
DB schema
```

No dependency addition.

---

## 39. Focused config tests

Coder tests in TRAFFIC-00 files must prove:

```text
defaults:
traffic_enabled=false
traffic_refresh_seconds=60
traffic_request_timeout_seconds=20
```

Reject:

```text
refresh < 60
refresh > 300
timeout < 5
timeout > 60
timeout <= WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
Traffic enabled while Admin disabled
```

`.env.example` contains safe defaults.

---

## 40. Focused page tests

Required:

```text
Traffic disabled
→ nav absent
→ direct page 404

Traffic enabled
→ nav present
→ page 200
→ active nav state

no session
→ login redirect

invalid Site
→ 400

forbidden Site
→ 403
```

Retain:

```text
no-store
CSP
local admin.js
local admin.css
```

---

## 41. Safe-context/template tests

Page contains exact Traffic data attributes.

Page must not contain:

```text
secret
password hash
DB path
absolute provider URL
numeric Traffic metric placeholder
inline <script>
write controls
```

Foundation hooks must exist:

```text
traffic-global-state
traffic-empty-state
traffic-panels
```

---

## 42. Frontend coordinator focused tests

At minimum:

```text
registration:
  unique key accepted
  duplicate key rejected
  invalid spec rejected

zero panels:
  empty state visible
  Refresh disabled
  no timer/fetch

dynamic first registration:
  empty state hidden
  Refresh enabled
  no second coordinator start required

initial load:
  autoRefresh=true panel executes once initially
  autoRefresh=false panel ALSO executes once initially
  manual-only panel schedules no subsequent periodic timer

refreshPanel:
  selected panel executes
  other registered panels untouched
  same-panel overlap protection preserved
  generation/AbortController remain coordinator-owned
  active Retry-After/backoff cannot be bypassed

refreshAll:
  all eligible registered panels execute

periodic:
  auto panel schedules with setTimeout
  manual-only panel does not auto schedule after initial load

same-origin defense:
  external/wrong-origin URL rejected
  wrong Admin Site namespace rejected where applicable

lifecycle:
  hidden → abort + pause
  visible → resume eligible
  pagehide → terminal stop

generation:
  old completion ignored

panel failure:
  one 503 does not stop another panel

global:
  401/403 global pause

retry:
  429 Retry-After respected
  503/timeout bounded backoff
  success resets backoff

isolation:
  existing generic classifyHttp/requestJson behavior is unchanged
```

## 43. Coder test responsibility

Coder runs only focused/minimal TRAFFIC-00 tests:

```bash
python -m pytest -q   tests/admin_web/test_traffic_foundation.py   tests/admin_web/test_traffic_foundation_frontend.py
```

Relevant static checks:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app/admin_web app/config.py app/settings.py

git diff --check
```

Coder does NOT run existing Home Traffic/Home modules as regression gate.

Coder does NOT run cross-module/broader/full repository/Central Lab tests.

---

## 44. Central Lab acceptance

Official PASS/FAIL:

```text
Owner + Tech Lead / Central Lab
```

Because `TRAFFIC-00` changes shared Admin shell/config/routes/admin.js, Central Lab should additionally select relevant existing Admin regression, e.g.:

```text
tests/admin_web/test_admin_ui.py
tests/admin_web/test_admin_ui_frontend.py
tests/admin_web/test_routes.py
tests/admin_web/test_config.py
```

Exact official command belongs to Central Lab.

Broader/full regression is Central Lab-owned.

---

## 45. Central Lab invariants

Central Lab verifies:

```text
Traffic disabled
→ Traffic nav absent from Home/Devices/Visits/Observations

Traffic enabled
→ Traffic nav visible from Home
→ visible from Devices
→ visible from Visits
→ visible from Observations
→ active only on Traffic page

existing Home/Devices/Visits/Observations continue working

generic Refresh works on existing pages

existing generic classifyHttp/requestJson call-site behavior unchanged

Home dedicated coordinators remain Home owners

Traffic generic Admin controller does not attach second Refresh owner

Traffic coordinator does not run on non-Traffic pages

Traffic HTML feature gate occurs only after existing authentication/Site authorization path

zero-panel Traffic page performs no product request
```

## 46. Browser acceptance

Controlled enabled config:

```text
Traffic nav appears
Traffic page 200
correct Site retained
empty foundation state visible
Refresh disabled
no console exception
no product data request
```

With only TRAFFIC-00, opening Traffic page must NOT request:

```text
Omada
Analytics bearer API
/current-traffic/summary
/traffic/current
Observation product data
Loki/Grafana
```

Only page/static requests are expected.

---

## 47. Performance

Zero panels:

```text
zero Traffic data requests
zero DB queries
zero Omada calls
zero periodic product polling
```

Coordinator stays idle.

Hidden/stopped page:

```text
zero scheduled Traffic work
```

---

## 48. Accessibility

Retain:

```text
semantic heading
role=status global state
aria-live safe state messages
keyboard Refresh
existing skip link/nav semantics
```

No state conveyed by color alone.

---

## 49. Deployment vs activation

Permanent:

```text
merge/deploy != activation
```

Recommended:

```text
1. TRAFFIC-00 implementation
2. Coder focused tests
3. Central Lab acceptance
4. merge
5. deploy with WEB_ADMIN_TRAFFIC_ENABLED=false
6. keep dormant until later Traffic panel acceptance
```

Production activation is not required to accept foundation.

---

## 50. Rollback

Operational rollback:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Result:

```text
nav disappears
Traffic page 404
Traffic frontend exposure gone
shared services unchanged
Home unchanged
```

No DB/data/Omada rollback.

---

## 51. Future TRAFFIC-01 rebind

After accepted `TRAFFIC-00` merge:

1. fetch current `origin/main`;
2. record exact merge SHA/tree;
3. verify factual:
   - page key;
   - route;
   - template hooks;
   - master flag;
   - refresh config;
   - coordinator API;
4. rebind `TRAFFIC-01`;
5. replace tentative foundation assumptions;
6. apply accepted Tech Lead corrections:
   - exact Home↔Traffic equality only under fixed evaluation/source context;
   - Home cross-surface regression execution belongs to Central Lab;
7. issue `TRAFFIC-01 FINAL` only after that.

---

## 52. Acceptance criteria

`TRAFFIC-00` is accepted only if:

1. Exact implementation baseline equals approved current `origin/main`.
2. `AdminPage("traffic")` exists.
3. `/admin/sites/<site_id>/traffic` exists.
4. Route ordering is authentication → Site resolve → Site authorization → Traffic feature gate → render.
5. Traffic nav is Site-aware.
6. `traffic_enabled` is shared render context for all Site Admin pages.
7. Traffic enabled shows nav from Home/Devices/Visits/Observations and active state only on Traffic.
8. Traffic disabled hides nav from all Site Admin pages.
9. Repository default `WEB_ADMIN_TRAFFIC_ENABLED=false`.
10. Traffic enabled requires Admin enabled.
11. Traffic disabled direct authorized page returns 404.
12. Existing Admin auth/Site/security boundary is reused.
13. Traffic page exposes only safe Traffic runtime dataset.
14. `WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60`, bounds 60..300.
15. `WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20`, bounds 5..60.
16. Traffic request timeout exceeds Admin backend query deadline.
17. Generic Admin controller yields Traffic lifecycle ownership.
18. One Traffic coordinator owns page lifecycle.
19. Public coordinator API minimally provides registerPanel / refreshPanel / refreshAll or exact semantic equivalent.
20. Public API is protected/narrow; internal lifecycle state remains private.
21. Every registered panel gets one initial load independent of autoRefresh.
22. `autoRefresh=true` adds periodic refresh after initial load.
23. `autoRefresh=false` receives initial load but no periodic refresh.
24. `refreshPanel` executes only selected panel.
25. Future panel controls cannot bypass coordinator with direct load/fetch.
26. Coordinator owns generation/AbortController/timeout/visibility/pagehide/backoff.
27. `refreshPanel` and `refreshAll` respect Retry-After/backoff.
28. Zero panels cause zero product requests, zero timer and disabled Refresh.
29. One panel failure remains panel-local.
30. 401/403 may become page-global.
31. Traffic request/classifier implementation is additive and does not alter existing generic Admin classifier/request semantics.
32. Traffic request helper enforces same-origin / expected Admin Site API boundary.
33. No Traffic product data API exists.
34. No Traffic calculation/read service/DB/acquisition exists.
35. No direct Omada path exists.
36. No Home product/UI semantic change exists.
37. No new dependency exists.
38. Coder focused TRAFFIC-00 tests pass.
39. Central Lab shared-Admin/frontend regression passes or is accepted under differential policy.
40. Production activation remains a separate Owner-controlled action.

## 53. Final decisions after Tech Lead review

Tech Lead review resolved the remaining Foundation choices.

Canonical FINAL decisions:

### Refresh / timeout

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
range 60..300

WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
range 5..60
must exceed Admin backend query deadline
```

### Public coordinator API

Minimum stable contract:

```text
registerPanel(...)
refreshPanel(...)
refreshAll(...)
```

Internal lifecycle state remains private.

### Initial load

```text
every successful panel registration
→ one initial execution
```

`autoRefresh` controls only subsequent periodic execution.

### Generic JS isolation

```text
existing Admin classifyHttp/requestJson
→ unchanged semantics

Traffic coordinator
→ additive private request/classification lifecycle
```

### Shared navigation context

```text
traffic_enabled
→ every Site Admin page render
→ shared base.html
```

Traffic-only refresh/timeout dataset remains Traffic-page-specific.

### Security ordering

```text
authenticate
→ resolve Site
→ authorize Site/context
→ Traffic feature gate
→ render
```

### Production exposure

Recommended:

```text
merge/deploy TRAFFIC-00 dormant
WEB_ADMIN_TRAFFIC_ENABLED=false
```

until `TRAFFIC-01` is accepted unless Owner explicitly chooses otherwise.

## 54. Status / next action

```text
ARCHITECTURE:
FINAL

TECH LEAD DRAFT VERDICT:
PASS WITH TARGETED REVISION

MANDATORY TECH LEAD REVISIONS:
INCORPORATED

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS FINAL

NEXT ACTION:
Owner may explicitly authorize Coder implementation of TRAFFIC-00
```

After implementation:

```text
focused Coder tests
→ Owner + Tech Lead / Central Lab acceptance
→ merge
→ deploy dormant
→ fetch exact new origin/main SHA/tree
→ rebind TRAFFIC-01
→ apply accepted TRAFFIC-01 Tech Lead corrections
→ TRAFFIC-01 FINAL
```

Canonical Foundation principle:

```text
one Traffic page
one coordinator lifecycle owner
panel-specific execution only through coordinator
one initial load per registered panel
many independently failing future panels
zero Traffic product calculations in Foundation
```

**Status:** `FINAL — READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL`
