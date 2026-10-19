# TASK-TRAFFIC-00 — Traffic Section Foundation — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Status:** `DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Production activation:** `NOT GRANTED`  
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

Current `origin/main` проверен перед DRAFT:

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

Behavior:

```text
valid session + allowed Site + Traffic enabled
→ 200
```

```text
Traffic disabled
→ 404 not_found
```

```text
invalid Site
→ 400 invalid_request

forbidden Site
→ 403 site_forbidden

no session
→ 302 /admin/login?next=...
```

Использовать существующий Site/page security path, не создавать новый.

---

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

In `admin/base.html` add Site-aware link:

```text
Traffic
→ /admin/sites/{{ site_id }}/traffic
```

Visible only if:

```text
traffic_enabled == true
```

Active when:

```text
page.key == "traffic"
```

Existing Home/Devices/Visits/Observations behavior remains unchanged.

No `home.html` change.

---

## 11. Safe page context

Traffic page receives:

```text
page
site_id
username
csrf_token
runtime_state
traffic_enabled
traffic_refresh_seconds
traffic_request_timeout_seconds
```

Traffic dataset:

```text
data-page="traffic"
data-site-id="<authorized Site>"
data-api-base="/admin/api/v1/sites/<site_id>"
data-runtime-state="..."
data-traffic-enabled="true"
data-traffic-refresh-seconds="60"
data-traffic-request-timeout-seconds="20"
```

Never expose:

```text
DB paths
Omada URL/ID
OAuth secrets
Analytics bearer token
provider object
raw settings mapping
```

---

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

Zero registered panels:

```text
traffic-empty-state visible
Refresh disabled
no timer
no product fetch
```

First registered panel:

```text
empty state hidden
Refresh enabled
```

---

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

Recommended stable minimum:

```javascript
CaptivPortalTrafficCoordinator.registerPanel({
  key,
  autoRefresh,
  load,
  render,
  renderLoading,
  renderFailure
})
```

Semantics:

```text
key
→ unique stable panel id

autoRefresh
→ true / false

load(context)
→ async
→ obtains and validates panel product result
→ uses coordinator request helper

render(value)
→ accepted result presentation

renderLoading()
→ optional

renderFailure(failure)
→ panel-local product-safe failure
```

`TRAFFIC-00` does not define any product DTO.

---

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

Coordinator `requestJson(...)` owns bounded same-origin GET:

```text
method = GET
credentials = same-origin
cache = no-store
Accept = application/json
AbortController = coordinator-owned
timeout = traffic_request_timeout_seconds
```

Forbidden:

```text
absolute external product URL
Bearer
localStorage
sessionStorage
cross-origin request
```

---

## 24. Frontend failure classes

Foundation generic classifications:

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

Mapping:

```text
401 → session
403 → forbidden
404 → disabled
400 → invalid
429 → busy
503 query_deadline → timeout
other 503 → unavailable
network → unavailable
bad envelope → unexpected
```

Only safe fields may propagate:

```text
kind
HTTP status
error.code
Retry-After
```

No raw exception/SQL/provider text.

---

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

For:

```text
autoRefresh=true
```

successful execution:

```text
next eligible =
now + WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
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

---

## 27. Manual refresh

Existing `Refresh` button:

```text
coordinator.refreshAll(manual=true)
```

Rules:

- zero panels → no-op;
- no overlapping same-panel request;
- may supersede clean in-flight request;
- active Retry-After/backoff is respected;
- every eligible registered panel refreshes independently.

---

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
unique registration accepted
duplicate registration rejected

zero panels:
  empty state visible
  Refresh disabled
  no timer/fetch

first panel:
  empty state hidden
  Refresh enabled

manual refresh:
  registered panel executes
  no same-panel overlap

periodic:
  auto panel schedules with setTimeout
  manual-only panel does not auto schedule

hidden:
  abort + pause

visible:
  resume eligible

pagehide:
  terminal stop

generation:
  old completion ignored

panel failure:
  one 503 does not stop another

global:
  401/403 global pause

retry:
  429 Retry-After respected
  503/timeout bounded backoff
  success resets backoff
```

---

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

Verify:

```text
Traffic disabled
→ existing Admin behavior unchanged

Traffic enabled
→ existing Home/Devices/Visits/Observations still work

generic Refresh works on existing pages

Home dedicated coordinators remain Home owners

Traffic generic Admin controller does not attach second Refresh owner

Traffic coordinator does not run on non-Traffic pages
```

---

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

1. exact current baseline is used;
2. `AdminPage("traffic")` exists;
3. Site Traffic route exists;
4. Traffic nav is Site-aware;
5. repository default master flag is false;
6. enabled requires Admin enabled;
7. disabled hides nav and page;
8. enabled exposes safe empty page;
9. existing Admin auth/Site boundary reused;
10. safe dataset only;
11. refresh setting default 60 / bounds 60..300;
12. request timeout default 20 / bounds 5..60;
13. request timeout exceeds backend query deadline;
14. one Traffic coordinator owns page lifecycle;
15. generic Admin controller yields Traffic page ownership;
16. coordinator owns generation/abort/timeout/visibility/pagehide/backoff;
17. zero panels cause zero data requests and disabled Refresh;
18. one panel failure is isolated;
19. 401/403 can become global;
20. no Traffic product API exists;
21. no Traffic calculation/read service/DB/acquisition exists;
22. no direct Omada path exists;
23. no Home product change exists;
24. no new dependency exists;
25. Coder focused tests pass;
26. Central Lab shared-Admin regression is accepted;
27. production activation remains Owner-controlled.

---

## 53. Questions for Owner / Tech Lead review

### Q1 — refresh config

Proposed:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

with bounds above.

### Q2 — coordinator minimum contract

Proposed:

```text
registerPanel({
  key,
  autoRefresh,
  load,
  render,
  renderLoading,
  renderFailure
})
```

No product DTO/range semantics in Foundation.

### Q3 — generic JS handoff

Proposed:

```text
generic configure()
→ no Traffic Refresh ownership

Traffic coordinator
→ sole Traffic lifecycle owner
```

### Q4 — production exposure

Recommended:

```text
merge/deploy foundation dormant
WEB_ADMIN_TRAFFIC_ENABLED=false
```

until `TRAFFIC-01` passes acceptance.

---

## 54. Status / next action

```text
ARCHITECTURE:
DRAFT READY FOR OWNER + TECH LEAD REVIEW

IMPLEMENTATION:
NOT AUTHORIZED

NEXT:
review → corrections → FINAL → explicit Coder authorization
```

After merge/acceptance:

```text
rebind TRAFFIC-01
→ TRAFFIC-01 FINAL
```

**Status:** `DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`
