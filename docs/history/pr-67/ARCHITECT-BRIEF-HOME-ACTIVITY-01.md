# ARCHITECT BRIEF — HOME ACTIVITY PANEL

**Project:** CaptivPortal  
**Requested document:** `TASK-HOME-ACTIVITY-01-DRAFT.md`  
**Role:** Architect / Tech Lead  
**Status:** product direction approved by Owner; architecture and implementation specification not yet approved  
**Implementation / branch / commit / push / PR / merge / deployment / production authorization:** NOT GRANTED

## 1. Assignment

Inspect the current repository, actual `origin/main`, current production-relevant Home implementation and accepted Visit/Traffic boundaries. Then prepare one complete architecture DRAFT for a new Home panel.

Working task name:

`TASK-HOME-ACTIVITY-01 — Admin Console Home Visits and Traffic Summary — DRAFT`

This panel expands and supersedes the previously reserved narrow `HOME-TODAY-01`. Explain whether that old task name is renamed, absorbed or split; do not leave two ambiguous parallel tasks.

The DRAFT must be detailed enough to become coder-ready after one Owner/Tech Lead review without repeatedly reopening product semantics, time windows, sources, API, UI, security, performance, testing, rollout or rollback.

Do not implement code while preparing the DRAFT.

## 2. Required inspection

Inspect at minimum:

- current repository `AGENTS.md`;
- current `origin/main` and exact baseline SHA;
- current Admin Home template, JavaScript, CSS, routes, query service and runtime;
- Home Live and Home Traffic implementation;
- Visit Lifecycle storage/read contracts;
- Visit Analytics contracts and implemented methods;
- Public Traffic storage/read contracts, including any `today_bytes` bridge;
- Observation, Wireless Analytics and Current Traffic read boundaries;
- feature flags, Admin query slot, deadlines, response cap and refresh coordinator;
- current Admin/Home tests and real-Node frontend test contract.

Review these project specifications:

- `TASK-HOME-CURRENT-STATE-01-DRAFT`;
- `TASK-HOME-LIVE-01-FINAL`;
- `TASK-HOME-TRAFFIC-01-DRAFT / FINAL`;
- `TASK-VISIT-LIFECYCLE-01-FINAL`;
- `TASK-ANALYTICS-FOUNDATION-01-REV1`;
- `TASK-ANALYTICS-01A-READ-DATA-QUALITY`;
- `TASK-ANALYTICS-01B-WIRELESS-ANALYTICS`;
- `TASK-ANALYTICS-01C-VISIT-ANALYTICS`;
- `Admin_Console_Grafana_Commercial_Access_CaptivPortal`.

Record the baseline actually inspected. Do not copy an earlier task baseline.

## 3. Owner-approved panel concept

Create one Home panel with the working title `Visits and Traffic` (final visible wording may be localized/refined).

It contains two visually related sections showing the same two metrics:

1. successfully authorized Visits;
2. general observed guest-network traffic volume.

Do not call devices or Visits “people”. Avoid raw technical terms such as `AuthSession` in the UI.

### 3.1. Fixed left section — Today

The left side always represents the current Site-local calendar day:

`[00:00:00 Site local time, evaluated_at)`

It must:

- start at Site-local midnight;
- end at one captured `evaluated_at`;
- roll over automatically at the next local midnight;
- never mean “last 24 hours”;
- remain independent of the selection on the right;
- display exact effective boundaries.

### 3.2. Selectable right section

The right side shows the same metrics for a selected interval.

Use a Grafana-like time-picker interaction model, without copying Grafana styling or code.

Required quick ranges:

- Last 24 hours;
- Yesterday;
- Last 48 hours;
- Last 7 days;
- Current month;
- Last 30 days.

Required custom absolute range:

- From: date and time;
- To: date and time;
- Apply;
- Cancel;
- maximum duration: 31 days.

Lock exact semantics:

- rolling presets end at the captured `evaluated_at`;
- `Yesterday` is the previous completed Site-local calendar day;
- `Current month` starts at local midnight on the first day of the current Site-local month and ends at `evaluated_at`;
- custom input becomes an explicit half-open interval `[from,to)`;
- the accepted interval is always displayed in the panel.

Do not use ambiguous `1 day`; distinguish `Yesterday` from `Last 24 hours`.

The DRAFT must also define:

- canonical Site timezone source;
- missing/invalid timezone behavior;
- DST-forward and DST-backward behavior;
- invalid, reversed, future and over-31-day ranges;
- nonexistent and ambiguous local times;
- date-only inclusive/exclusive expectations;
- default right-side selection on fresh load;
- relative-range advancement on refresh;
- absolute-range stability;
- midnight rollover while the page remains open;
- one shared `evaluated_at` anchor for Visit and Traffic results.

## 4. Metric A — successfully authorized Visits

The Owner does not want unauthenticated associations, pending clients or failed connection attempts in this panel.

Product success unit:

`one Visit that reaches successful portal authorization`

Required invariants:

- count only after successful authorization;
- one Visit contributes at most one unit;
- retries, duplicate evidence and multiple AuthSessions inside one Visit do not increase the count;
- pending, failed, abandoned and never-authorized Visits do not contribute;
- raw Omada online-client counts do not contribute;
- the result is Site-scoped and has explicit guest SSID/source scope;
- zero is valid only after a successful query with no qualifying Visit;
- missing/unavailable evidence never becomes zero.

The Architect must explicitly choose and justify the cohort timestamp. Preferred product interpretation:

`attribute the Visit to the interval containing its first successful authorization timestamp`

This is not automatically the existing generic Visit-start cohort. Inspect whether current Visit Lifecycle/Analytics evidence can derive it correctly and efficiently.

Cover:

- Visit starts before the interval and authorizes inside it;
- Visit starts inside the interval and authorizes after it;
- Visit crosses midnight;
- first authorization exactly at `from` or `to`;
- reopened/reused Visit behavior under existing lifecycle rules;
- duplicate/out-of-order authorization evidence;
- currently open but authorized Visit;
- later Visit closure must not remove a previously successful unit.

If current persistence cannot support the preferred cohort without unsafe inference, identify the exact gap. Do not silently substitute AuthSession count or Visit-start count under the same label.

Lock one exact API field name, DTO meaning and visible label. Candidate visible wording: `Authorized visits`.

## 5. Metric B — general observed guest-network traffic

Product intent:

`an understandable Home-level total of general guest-network traffic volume for the same interval`

This is a summary indicator. It does not replace the future dedicated Traffic page, where AP/client/SSID breakdowns, charts, peaks, source reconciliation and stricter accuracy work belong.

Summary status does not permit misleading scope or fabricated precision.

Inspect and compare existing possible authorities:

- Public Traffic `today_bytes` and historical records;
- Visit Analytics traffic summary;
- Observation-derived traffic evidence;
- Wireless Analytics traffic evidence;
- `CurrentTrafficReadService`.

Preserve this accepted boundary: `CurrentTrafficReadService` is current AP physical/network traffic evidence and may include local/service traffic. It is not automatically guest-only, SSID-only, Internet-only or a historical byte-volume authority.

The DRAFT must state exactly:

- source DB/table/read service;
- what is summed;
- combined total versus download/upload directions;
- counter units and conversion;
- reset, wrap, AP restart, gaps and duplicate handling;
- Site/guest/SSID scope;
- whether local/service traffic is included;
- available retention for every range through 31 days;
- returned coverage/provenance;
- why the visible label is honest.

Primary UI value: `Traffic`, using adaptive B/KB/MB/GB units without false decimal precision. Download/upload may be secondary only if direction and source are trustworthy.

If the source is approximate but usable, define the approximation and visible `Estimated`/`Partial` behavior.

If no existing bounded source can honestly provide 31-day guest-network traffic, stop and define the smallest prerequisite foundation task. Do not:

- trigger Omada/provider from HTTP requests;
- sum instantaneous Mbps as byte totals without a reviewed integration method;
- change Observation acquisition/schema/worker inside an Admin UI task;
- add an index without query-plan and benchmark evidence;
- relabel AP-wide traffic as guest-only.

## 6. Presentation contract

Include a compact wireframe and exact states.

Desktop:

- one panel;
- Today on the left;
- selected period on the right;
- identical metric order.

Mobile/narrow:

- stack Today first and selected period second;
- preserve the visual relationship;
- no horizontal scrolling.

Minimum per side:

- period title;
- exact boundaries;
- Authorized visits;
- Traffic;
- freshness/coverage/quality note.

The picker must support:

- keyboard navigation and accessible labels;
- correct focus management;
- Escape/Cancel;
- Apply without issuing requests on every intermediate calendar click;
- visible validation errors;
- safe text rendering and no unsafe `innerHTML`.

Do not add graphs, per-client/AP details, distributions, peaks, new/returning analysis or duration analytics to this Home panel.

## 7. Independent data-quality states

Define independently for both metrics and both halves:

- loading;
- complete;
- partial;
- stale where meaningful;
- unavailable;
- forbidden;
- invalid range;
- true zero.

Required behavior:

- Visit failure does not erase Traffic;
- Traffic failure does not erase Visit count;
- selected-period failure does not erase Today;
- Today rollover does not modify an absolute selected range;
- an old response cannot overwrite a newer selection;
- partial coverage is visible;
- zero renders as zero, while missing/unavailable does not;
- source/evaluated boundaries remain inspectable;
- detailed internals stay in sanitized telemetry.

## 8. API/read architecture

Preferred boundary:

`persisted sources → existing or narrow read/Analytics service → AdminQueryService → authenticated Site-scoped Admin API → Home`

Required constraints:

- GET/read-only only;
- browser/Admin never calls Omada/provider;
- no DB writes from Admin requests;
- explicit DTO allowlist serialization;
- Site/capability checks before source access;
- canonical rejection of unknown/duplicate parameters;
- strict timezone/from/to/preset parsing;
- server-side 31-day limit;
- common Admin query slot, hard deadline and response cap;
- bounded SQL aggregation, no N+1 and no full-history Python materialization;
- no cross-Site/SSID leakage;
- no sensitive source payloads in errors or telemetry.

Choose and justify:

- one combined endpoint for Today plus selected period; or
- separate bounded endpoints coordinated by the frontend.

Account for independent failures, shared `evaluated_at`, browser concurrency, query-slot occupancy, response size, duplicate scans, capability boundaries, testing and rollback.

Define routes, parameters, DTOs, capabilities, HTTP statuses and canonical error codes. Grant no broader capability than necessary.

## 9. Frontend refresh integration

Integrate with the existing Home refresh coordinator. Do not create a separate overlapping polling loop.

Define:

- default load phase;
- manual Refresh;
- immediate request after Apply;
- AbortController/generation ownership;
- stale-response protection;
- browser concurrency including two tabs;
- 429/500/503/network backoff;
- whether manual refresh may bypass backoff;
- relative versus absolute range refresh;
- hidden-tab behavior;
- unload cleanup;
- bounded midnight rollover scheduling.

Preserve:

- no overlap;
- no stale overwrite;
- Home Live and Home Traffic failure isolation;
- current AP-page 403 behavior;
- no browser persistence unless separately reviewed.

Selection change must start a new generation, cancel obsolete work where possible and request only the accepted range.

## 10. Feature/configuration isolation

Propose a separate default-off flag. Candidate: `WEB_ADMIN_HOME_ACTIVITY_ENABLED=false`.

Define:

- dependency on Admin and Home Live;
- coexistence with Home Traffic enabled/disabled;
- optional/fail-open runtime composition;
- repository-safe defaults and bounds;
- request/refresh timeout;
- Site timezone configuration if no canonical setting exists.

Missing Activity sources must not make Admin, Home Live, Home Traffic, Analytics or Portal unavailable.

When disabled: no panel-specific timers, listeners, requests or source access.

## 11. Performance/storage evidence

Require representative production-sized evidence through 31 days:

- `EXPLAIN QUERY PLAN` for Visit aggregation;
- `EXPLAIN QUERY PLAN` for Traffic aggregation;
- row/materialization bounds;
- response below the Admin response cap;
- warm/cold Today, 24h, 7d and 31d measurements;
- concurrent Home and two-tab behavior;
- Admin query-slot occupancy.

Use current global deadlines/caps. Set p95 targets only after measuring actual plans.

If an index/rollup is required, prove it and put it in the correct prerequisite task rather than hiding schema work in frontend scope.

## 12. Security/privacy/telemetry

Define:

- authentication, Site access and capability ordering;
- disabled-feature response after security checks;
- GET/CSRF applicability;
- allowlisted DTO fields;
- sanitized structured telemetry;
- no MAC/IP/username/token/raw cursor/secrets in logs unless an accepted contract explicitly allows it;
- no DOM injection;
- no storage of private response data in the browser;
- bounded refresh abuse/backoff behavior.

## 13. Future coder test scope

Follow current `AGENTS.md`:

- coder runs targeted tests for the changed module;
- Owner/review side runs broader/full gates before production activation;
- do not require unrelated full-suite reruns from the coder unless current `AGENTS.md` explicitly requires them.

Targeted matrix must include:

### Visit

- one successful Visit = one unit;
- duplicates/multiple AuthSessions do not double count;
- pending/failed/never-authorized excluded;
- boundary inclusion at `from`, exclusion at `to`;
- cross-midnight and delayed authorization;
- open authorized Visit;
- Site/SSID isolation;
- successful empty query gives zero.

### Time

- Today and midnight rollover;
- Yesterday;
- rolling 24h/48h/7d/30d;
- Current month;
- custom range;
- exact 31-day maximum;
- invalid/future/reversed/too-long ranges;
- timezone and DST boundaries;
- shared `evaluated_at`.

### Traffic

- source scope and unit conversion;
- true zero;
- reset/wrap/restart handling where applicable;
- gaps/partial coverage;
- no AP-wide guest-only mislabel;
- no rate-as-byte-total error;
- bounded 31-day query.

### API/security

- authentication, Site and capability;
- disabled flag;
- malformed/unknown/duplicate parameters;
- serialization allowlist;
- deadline/query slot/response cap;
- unavailable/timeout/error classification;
- no Omada/provider calls;
- read-only proof.

### Frontend

- real Node execution, not skip due to missing Node;
- presets/custom picker and Apply/Cancel/accessibility;
- no request on intermediate calendar clicks;
- generation/abort/stale protection;
- no overlap and agreed concurrency;
- refresh/backoff/midnight behavior;
- independent metric/half states;
- zero versus missing/partial/unavailable;
- desktop/mobile layout;
- safe DOM rendering;
- disabled flow creates no requests/timers/listeners.

## 14. Deployment/rollback design

Preserve staged production sequencing:

1. merge reviewed code;
2. deploy with feature false;
3. verify existing Admin/Home Live/Home Traffic/Portal;
4. separate Owner authorization for activation;
5. activate;
6. perform real production reconciliation, p95 and browser checks.

Do not simulate production-only evidence locally.

Fast rollback is feature-flag disablement without disabling Current State, Home Live, Home Traffic, Observation, Visit Lifecycle or Analytics. No destructive data operation belongs in rollback.

## 15. Non-goals

Exclude:

- per-client/SSID/AP traffic UI;
- traffic charts and peaks;
- WAN utilization/Channel Load;
- new/returning, unique-device or Visit-duration analytics;
- Devices by AP — 24h;
- System Health;
- Omada control/write actions;
- new acquisition path;
- Observation worker/schema changes;
- broad Analytics refactor;
- Grafana/Loki queries from Home;
- browser persistence;
- WebSocket/SSE.

## 16. Hard stops

Stop and return an exact gap if:

- no persisted/derivable first-successful-authorization evidence exists;
- correct count requires AuthSession double counting;
- no honest 31-day guest-network traffic source exists;
- traffic requires new provider calls;
- queries cannot stay bounded under Admin limits;
- new schema/worker/collector/rollup/index is required without separate review;
- Site timezone cannot be determined safely;
- retention cannot cover an advertised range;
- Site/capability/privacy or refresh invariants would weaken.

For every gap provide the missing contract, affected modules, smallest prerequisite task, safely narrowed wording if any, and what must not be implemented yet.

## 17. Required Architect deliverable

Return one Markdown DRAFT containing:

1. exact baseline and dependencies;
2. repository findings and source truth table;
3. final metric/cohort semantics;
4. Site/timezone/range contract;
5. wireframe and responsive/accessibility contract;
6. feature/configuration contract;
7. routes, parameters, DTOs, capabilities and errors;
8. query/read-service design and no-Omada proof;
9. quality/provenance model;
10. refresh/concurrency/backoff/stale design;
11. performance/query-plan evidence plan;
12. targeted tests consistent with `AGENTS.md`;
13. allowed/forbidden file scope;
14. decomposition if a prerequisite foundation is required;
15. deployment/activation/rollback plan;
16. only genuine unresolved Owner decisions;
17. filename, size and SHA256.

The DRAFT is for review only. It must not authorize implementation, branch creation, commit, push, PR, merge, deployment, configuration change or activation.
