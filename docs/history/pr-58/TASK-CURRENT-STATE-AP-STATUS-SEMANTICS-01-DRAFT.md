# TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01 — Canonical Omada AP status semantics — DRAFT

**Project:** CaptivPortal  
**Area:** Current Network State → AP status semantics  
**Type:** Controlled live research + canonical semantic contract  
**Priority:** Prerequisite for `TASK-HOME-AP-24H-01`  
**Status:** DRAFT — Owner / Tech Lead review required  
**Implementation authorization:** NOT GRANTED  
**Live disruption authorization:** NOT GRANTED BY THIS DRAFT  
**Production activation:** NOT GRANTED  
**Prepared:** 2026-08-28  
**Exact repository baseline:** `origin/main@bc929dbe7c1687415bd4eeda971dcbc9376d8bbc`  

---

# 0. Executive decision

Current State already persists raw AP controller status:

```text
current_ap_state.status_code
```

and its schema already permits canonical classifications:

```text
online
offline
other
unknown
```

but the current normalizer intentionally proves only:

```text
status_code == 1 → online
other numeric code → other
missing/unusable → unknown
```

No current repository contract proves which Omada controller state means physical AP unavailable/offline.

`TASK-HOME-AP-24H-01` requires real outage periods and duration, so guessing the mapping is forbidden.

This task performs controlled live validation and produces one canonical shared semantic contract.

Primary desired outcome:

```text
raw Omada AP status
→ canonical online/offline/other/unknown
```

used by both:

```text
Current State collection
HOME-AP-24H historical interpretation
```

The research itself requires:

```text
NO new database
NO schema migration
NO collection-cadence change
NO retention change
```

because raw `status_code` is already persisted.

However the test MUST determine whether an unavailable AP remains present in a complete Omada AP inventory. If Omada removes it entirely, that is a different architectural outcome and may require a later explicit negative-presence/storage contract before full outage history can be produced.

---

# 1. Goal

Establish, with repeatable controlled physical evidence, the canonical meaning of Omada AP status data for CaptivPortal.

The research must answer:

1. what raw status is returned while a known AP is healthy/serving;
2. what raw status is returned while that AP is intentionally unavailable;
3. whether the AP remains in the Site AP inventory while unavailable;
4. what transient statuses appear during outage detection and recovery;
5. how quickly the controller changes state after physical disruption/recovery;
6. whether the same semantics repeat over at least two independent outage/recovery runs;
7. whether `last_seen`, uptime or another raw field is necessary to disambiguate status;
8. whether Current State persists the same raw status during complete successful cycles;
9. whether a pure status-code mapper is sufficient;
10. if not, what additional foundation dependency is actually required.

---

# 2. Dependency relationship

This task is an explicit mandatory prerequisite for:

```text
TASK-HOME-AP-24H-01
```

HOME-AP-24H implementation MUST NOT start until this task reaches an accepted outcome.

Expected dependency flow:

```text
AP semantics DRAFT
→ Owner / Tech Lead approval
→ controlled live experiment
→ evidence report
→ canonical semantic decision
→ focused mapper implementation if evidence permits
→ Central Lab / regression gate for mapper artifact
→ HOME-AP-24H FINAL
```

If the experiment proves that current persistence cannot represent outage evidence safely, HOME-AP-24H FINAL remains blocked until the additional dependency is designed and accepted.

---

# 3. Baseline truth

At DRAFT preparation:

```text
origin/main =
bc929dbe7c1687415bd4eeda971dcbc9376d8bbc
```

Before any live experiment or mapper implementation:

1. fetch `origin/main`;
2. record exact SHA;
3. verify changes affecting:
   - `app/current_state/**`;
   - `app/controllers/omada_observations.py`;
   - Omada provider composition;
   - Admin current-state serialization;
4. if raw AP inventory/status handling changed, return to Tech Lead for impact review.

---

# 4. Current repository semantic truth

Current State AP normalization reads raw aliases such as:

```text
status
statusCode
status_code
```

and currently maps:

```text
1            → online
other int    → other
non-int/null → unknown
```

Existing tests deliberately assert that values such as:

```text
0
2
99
```

are NOT silently classified as offline.

This conservative behavior remains authoritative until this task proves a new mapping.

---

# 5. Current schema compatibility

Current State schema v1 already contains:

```text
status_code INTEGER
status_classification TEXT
```

with allowed classification set including:

```text
offline
```

Therefore, if a stable raw offline code is proven, a mapper change can be implemented without schema migration.

No historical row rewrite is required because raw status codes are already stored.

HOME-AP-24H can interpret historical raw codes using the same canonical mapper.

---

# 6. Product meaning to prove

The target semantic is not:

```text
"AP electrically powered off at this exact millisecond"
```

The target semantic is:

```text
"Omada controller has canonically classified the AP as unavailable/offline"
```

Therefore any later HOME-AP-24H outage interval is a **controller-observed availability interval**, bounded by polling/detection latency.

The research report MUST measure controller detection/recovery latency so product documentation does not imply sub-poll physical precision.

---

# 7. Non-goals

This task does NOT:

- redesign Current State;
- add AP history storage;
- change Current State retention;
- increase polling cadence;
- change Observation collection;
- create AP Health scoring;
- define CPU/memory thresholds;
- define radio degradation thresholds;
- define wired-uplink degradation thresholds;
- change Home Live UI;
- implement HOME-AP-24H;
- change Omada authorization;
- change Visit Lifecycle;
- change webhook schema;
- change Grafana/Loki/Alloy;
- perform an uncontrolled production AP outage.

---

# 8. Required live-test authorization

This DRAFT defines a test procedure but does not authorize disruption.

Before live Stage B, Owner must explicitly approve:

```text
Site
designated test AP
maintenance/disruption window
physical action permitted
operator performing the action
```

The selected AP must be safe to disrupt for the test window.

If disrupting it could cause unacceptable guest/service impact, Stage B is postponed rather than tested on an arbitrary live AP.

---

# 9. Test target identity

Before testing, record immutable target identity:

```text
site_id
canonical ap_mac
controller-visible name
model
firmware version if available
controller version
```

MAC is the test identity authority.

AP name is not identity.

No second AP or unrelated device may be modified by the procedure.

---

# 10. Ground-truth states

Operator-controlled ground-truth phases are:

```text
ONLINE_STABLE
DISRUPTION_INITIATED
PHYSICALLY_UNAVAILABLE
RECOVERY_INITIATED
ONLINE_RECOVERED
```

The operator records UTC timestamps for physical actions.

These timestamps are research ground truth and are not automatically treated as controller-state timestamps.

---

# 11. Evidence channels

Use three independent evidence channels.

## A. Direct read-only Omada inventory sampling

Purpose:

```text
capture raw controller status transition at higher resolution
```

Use the existing read-only AP inventory provider contract where practical.

## B. Persisted Current State complete successful cycles

Purpose:

```text
prove the production persistence path captures the same status semantics
```

## C. Operator physical action log

Purpose:

```text
establish when the AP was intentionally made unavailable/restored
```

Observation Foundation may be inspected as supporting context, but Observation `partial` is not an AP offline authority.

---

# 12. Direct sampler constraints

Any temporary diagnostic sampler must be:

```text
read-only
Site-scoped
target-MAC filtered after complete inventory retrieval
bounded
sanitized
non-persistent beyond research artifact needs
```

It MUST NOT:

- authorize/deauthorize clients;
- reboot APs via undocumented APIs;
- change AP settings;
- change Omada configuration;
- write Current State DB;
- write Observation DB;
- expose tokens;
- dump full controller payloads unnecessarily.

A temporary script/tool is not committed unless separately approved.

---

# 13. Direct sampler frequency

Recommended research sampling interval:

```text
10 seconds
```

This is a temporary bounded research interval, NOT a production collector cadence.

If Site/controller scale makes 10-second full inventory reads inappropriate, Tech Lead may increase it before test execution.

Never decrease below 5 seconds without explicit review.

Each research state has a bounded maximum dwell; no infinite polling loop.

---

# 14. Complete direct inventory requirement

A direct sample can support absence semantics only if the AP inventory request is proven complete.

Record:

```text
request outcome
total_rows
pages read
row/page bounds
inventory_complete
```

If inventory collection is partial/failed:

```text
target AP missing
```

means nothing about AP availability.

Such a sample is source-unavailable evidence only.

---

# 15. Sanitized research sample schema

Recommended evidence row:

```json
{
  "sampled_at_utc": "...",
  "site_id": "...",
  "target_ap_mac": "AA:BB:CC:DD:EE:FF",
  "ground_truth_phase": "ONLINE_STABLE",
  "inventory_complete": true,
  "inventory_total_rows": 0,
  "target_present": true,
  "raw_status_type": "int|null|other",
  "raw_status_code": 1,
  "last_seen_ms": null,
  "controller_uptime": null,
  "uptime_raw": null,
  "request_result": "ok",
  "failure_category": null
}
```

No secrets, token, cookies or unrelated client data.

---

# 16. Current State evidence record

For each relevant Current State AP cycle, record only:

```text
cycle_id
capture_started_at
capture_finished_at
result
complete
source_rows_reported
items_seen
items_stored
error_count
unknown_status_count

and target AP row if present:
ap_mac
status_code
status_classification
last_seen_ms
controller_uptime
```

Only:

```text
kind='ap'
result='success'
complete=1
```

can prove a complete inventory state.

---

# 17. Clock contract

All experiment evidence is normalized to UTC.

Record:

```text
operator physical action timestamp
direct sample timestamp
Current State capture_started_at
Current State capture_finished_at
```

Do not substitute file mtime or log ingestion time for controller/inventory observation time.

---

# 18. Stage A — read-only precheck

Before physical disruption:

1. verify exact repository/deployed baseline;
2. verify Current State runtime is active/degraded but readable;
3. verify target Site identity;
4. verify target AP canonical MAC;
5. obtain a complete AP inventory;
6. confirm target AP is present;
7. record current raw status;
8. record at least three stable direct samples;
9. record at least one complete successful Current State AP cycle containing the target;
10. verify no unrelated configuration change is planned during the experiment.

If baseline is not stable:

```text
STOP
```

---

# 19. Stage A expected online baseline

Current repository expects healthy baseline evidence to include:

```text
status_code = 1
```

but the experiment should record rather than assume it.

Acceptance for baseline:

```text
>= 3 consecutive complete direct samples
same stable target presence
same stable raw online status
```

and at least one complete successful Current State cycle consistent with that state.

---

# 20. Stage B — outage run 1

After explicit Owner live-test approval:

1. record `DISRUPTION_INITIATED` UTC timestamp;
2. perform the approved physical action that makes the designated AP unable to serve normally;
3. record `PHYSICALLY_UNAVAILABLE` once the operator confirms the action is complete;
4. continue bounded direct sampling;
5. allow Current State to continue its normal production cadence unchanged;
6. do not change collector settings;
7. observe until one of the Stage B stop conditions is reached.

Preferred physical action is the simplest reversible action approved by Owner that establishes known AP unavailability.

No unrelated Omada settings are changed.

---

# 21. Outage-run evidence target

The research looks for one of three patterns.

## Pattern A — AP remains present with a stable different status

Example shape:

```text
present=true
status_code=X
```

repeated while physically unavailable.

This is the preferred path for a pure status-code offline mapping.

## Pattern B — AP disappears from complete inventory

Example:

```text
inventory_complete=true
target_present=false
```

repeated while physically unavailable.

This proves negative-presence behavior but does not create a historical Current State AP row under the existing schema.

## Pattern C — controller status is inconsistent/ambiguous

Examples:

- multiple unrelated codes with no stable state;
- AP alternates present/absent unpredictably;
- inventory frequently incomplete;
- status value overlaps stable online periods.

This does not support an offline mapping.

---

# 22. Stable offline-code candidate rule

A raw code `X` becomes a candidate offline code only when all are true:

1. ground truth is physically unavailable;
2. direct inventory is complete;
3. target AP remains present;
4. `status_code == X` in at least three consecutive direct samples;
5. stable duration is at least 30 seconds;
6. `X` was not observed in the stable-online baseline;
7. at least one complete successful Current State cycle persists raw `X` while the AP is physically unavailable.

This is only candidate evidence until the second independent outage run reproduces it.

---

# 23. Transition statuses

Codes observed only during:

```text
DISRUPTION_INITIATED → stable unavailable
or
RECOVERY_INITIATED → stable online
```

are transition codes.

Do not map them to offline merely because they occur near an outage.

Default classification for unproven transition codes remains:

```text
other
```

unless repeated evidence independently proves a stronger meaning.

---

# 24. Stage C — recovery run 1

1. record `RECOVERY_INITIATED` UTC timestamp;
2. restore the AP using the approved reversible action;
3. continue direct sampling;
4. wait for complete inventories;
5. record first reappearance if it had disappeared;
6. record first raw online status;
7. continue until at least three stable complete direct samples show recovered online state;
8. capture at least one complete successful Current State cycle showing the recovered state.

Record controller recovery latency separately from physical restore time.

---

# 25. Stage D — independent repetition

Repeat the controlled outage + recovery sequence a second time after the AP is stable.

The second run is mandatory for accepting an offline status mapping.

It must reproduce:

```text
same physical ground truth
same inventory presence behavior
same stable offline code or same stable absence behavior
same recovery semantics
```

Small timing differences are acceptable; semantic behavior must match.

---

# 26. Optional reboot characterization

A controlled AP reboot MAY be added only after the required physical-unavailability runs if Owner approves it.

Purpose:

```text
distinguish reboot/transitional controller statuses from stable offline status
```

A reboot state must not be used as the only proof of physical offline semantics.

If omitted, the main prerequisite can still close when two controlled unavailable/recovery runs are conclusive.

---

# 27. Controller/API failure negative control

The research must explicitly preserve this rule:

```text
Controller/API unavailable
≠ AP offline
```

If a direct sample fails because the Controller/API cannot be read:

```text
source evidence = unavailable
AP state = unknown
```

Do not use controller failure to validate AP status mapping.

No deliberate Controller outage is required for this task.

---

# 28. AP absence rule

Before this research closes, AP absence from complete inventory remains:

```text
unknown / not_in_complete_inventory
```

If Pattern B is repeatably observed during physical unavailability, the evidence report MUST say exactly:

```text
Omada represents tested physical unavailability by removing the AP from complete inventory
```

but this task must NOT silently change HOME-AP-24H to `absence=offline`.

Why:

- an AP can be removed/reassigned/adopted elsewhere;
- the current AP row schema persists positive rows, not explicit negative-membership events;
- historical absence must be modeled deliberately if it becomes authoritative outage evidence.

Pattern B therefore triggers an architecture return.

---

# 29. `last_seen` and uptime semantics

Fields such as:

```text
last_seen_ms
controller_uptime
uptime_raw
```

are supporting evidence only unless testing proves a deterministic required role.

Do not create heuristics such as:

```text
last_seen > N → offline
uptime reset → outage
```

without explicit evidence and separate contract.

The preferred mapper remains based on the controller status code when that is sufficient.

---

# 30. Detection latency measurements

For each outage run record:

```text
physical_unavailable_at
first_direct_offline_evidence_at
first_current_state_offline_evidence_at
```

Compute:

```text
direct_detection_latency_seconds
current_state_detection_latency_seconds
```

For recovery:

```text
physical_restore_at
first_direct_online_evidence_at
first_current_state_online_evidence_at
```

Compute equivalent recovery latency.

These measurements document resolution/latency; they do not alter production cadence.

---

# 31. Canonical mapper acceptance rule

A pure raw-status mapper may be approved only if the experiment proves a stable repeatable code mapping.

Minimum accepted contract:

```text
known online code(s)  → online
proven offline code(s) → offline
other integer codes   → other
missing/unusable      → unknown
```

No catch-all:

```text
not online → offline
```

is allowed.

---

# 32. Preferred shared mapper boundary

If Pattern A passes, implementation after research approval should create one shared pure semantic boundary, for example:

```text
app/current_state/ap_status.py
```

with a concept such as:

```text
classify_ap_status_code(raw_status)
```

Exact file/function naming is coder/Tech Lead controlled, but there must be one implementation authority.

Consumers:

```text
Current State normalizer
HOME-AP-24H historical query/read model
```

No duplicated mapping table.

---

# 33. Historical compatibility rule

Existing historical rows may contain:

```text
status_code = X
status_classification = other
```

where research later proves:

```text
X = offline
```

Do NOT backfill or rewrite historical DB rows merely to update semantics.

HOME-AP-24H uses:

```text
canonical shared mapper(status_code)
```

for historical interpretation.

Current State writer uses the same mapper for new rows after deployment.

Stored historical classification remains source-era metadata; raw code + canonical mapper is semantic authority for AP-24H.

---

# 34. Current State compatibility impact

Current State already models `offline` as a valid internal classification.

Therefore Pattern A mapper implementation is expected to require no schema version change.

Existing Admin Home Live product serialization currently does not need to be redesigned by this task.

Any unexpected current-state API/product behavior caused by the new mapper must be returned to Tech Lead rather than patched silently.

---

# 35. Research outcome A — stable offline code

Outcome A requires:

```text
AP remains present in complete inventory during outage
same stable offline code reproduced in two outage runs
Current State persists the code in complete-success cycles
online recovery is repeatable
```

Result:

```text
PASS — pure shared mapper sufficient
no schema/storage dependency
```

Then prepare/approve the focused mapper implementation artifact and, after its acceptance, proceed to HOME-AP-24H FINAL.

---

# 36. Research outcome B — AP disappears from complete inventory

Outcome B requires repeatable evidence that:

```text
complete inventory=true
AP present while online
AP absent while physically unavailable
AP reappears after recovery
no stable offline row exists
```

Result:

```text
RESEARCH PASS / HOME-AP-24H DEPENDENCY NOT CLOSED
```

Reason:

The controller semantics are understood, but current persisted AP rows do not store explicit negative presence for the missing AP.

Return to Architect/Tech Lead for a separate design such as explicit inventory-membership/absence evidence.

No such design is authorized by this DRAFT.

---

# 37. Research outcome C — ambiguous/inconsistent semantics

Examples:

- code changes are not repeatable;
- same candidate offline code appears during stable online state;
- inventory completeness cannot be proven;
- physical state and controller status do not correlate reliably;
- Current State persistence misses/normalizes evidence inconsistently.

Result:

```text
NOT VERIFIED
```

Do not create an offline mapper.

Return evidence and refine the research plan.

HOME-AP-24H remains blocked.

---

# 38. Research stop conditions

Immediately stop the disruptive portion if:

- unrelated network impact becomes unacceptable;
- test AP identity is uncertain;
- Controller/API health degrades unexpectedly;
- the operator cannot safely restore AP service;
- current production state differs from precheck assumptions;
- another deployment/configuration change begins during the window;
- the test starts affecting non-target AP configuration;
- evidence timestamps cannot be trusted.

Restore the AP first; analyze later.

---

# 39. Bounded outage dwell

No outage run should remain open indefinitely while waiting for a controller transition.

DRAFT bound:

```text
maximum physically unavailable dwell per run = 10 minutes
```

If no stable controller semantics appears within the bound:

1. restore the AP;
2. record the outcome as inconclusive/Pattern C;
3. do not extend the outage ad hoc.

Owner may approve a different bounded window before execution if controller detection characteristics justify it.

---

# 40. Recovery safety

The operator must have a documented way to restore the target AP before starting the outage run.

The live test is not started if restoration depends on the same unavailable path being tested and no alternate access exists.

No factory reset.

No forget/re-adopt unless a later separately approved experiment explicitly requires it.

---

# 41. No guest/client semantics changes

During this research:

- no client authorization rule changes;
- no captive portal changes;
- no SSID security change;
- no VLAN change;
- no rate-limit change;
- no client block/unblock;
- no Visit Lifecycle manipulation.

Guest effects caused solely by the approved AP outage are operational test impact, not a software change.

---

# 42. No collector configuration changes

Do NOT modify:

```text
CURRENT_STATE_AP_INTERVAL_SECONDS
CURRENT_STATE_HISTORY_RETENTION_HOURS
OBSERVATION_AP_INTERVAL_SECONDS
OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE
```

for the purpose of the research.

The direct temporary sampler provides higher-resolution research evidence without changing the production collector contract.

---

# 43. No database mutation

Research reads:

```text
Current State SQLite
```

in query-only/read-only mode.

No manual SQL UPDATE/INSERT/DELETE.

No backfill.

No migration.

No copied test rows into production DB.

---

# 44. Research artifact layout

Preferred evidence package:

```text
AP_Status_Semantics_Research_<date>/
  README.md
  direct_samples.jsonl
  current_state_cycles.csv
  operator_actions.csv
  analysis.md
  conclusion.md
```

Exact file format can vary, but raw/sanitized evidence and conclusion must be separable.

Tokens and full sensitive controller payloads are excluded.

---

# 45. Operator action log

Minimum fields:

```text
action_id
utc_timestamp
action
site_id
ap_mac
notes
```

Actions include:

```text
baseline_confirmed
disruption_initiated
physically_unavailable
recovery_initiated
online_recovered
run_completed
```

---

# 46. Evidence correlation table

For each transition, final report should correlate:

| Ground truth | Direct inventory | Raw status | Current State complete cycle | Canonical interpretation |
|---|---|---|---|---|
| stable online | present | code | row/code | online |
| outage transition | present/absent | code/null | row/absence | other/unknown until proven |
| stable unavailable | present/absent | code/null | row/absence | research result |
| recovery transition | present/absent | code/null | row/absence | other/unknown until proven |
| stable recovered | present | code | row/code | online |

No empty cell is silently inferred.

---

# 47. Mapper test plan if Outcome A

Focused tests after research approval:

1. proven online code → `online`.
2. proven offline code → `offline`.
3. every unproven numeric code → `other`.
4. null/non-int → `unknown`.
5. bool is not accidentally accepted as int if existing strict-int contract forbids it.
6. Current State normalizer uses shared mapper.
7. HOME-AP-24H query path uses same shared mapper.
8. historical raw offline code with old stored `other` classification maps to offline at read time.
9. no schema change.
10. existing Home Live serializer regression remains accepted.
11. Current State summary invariants still hold with non-zero offline count.

---

# 48. Semantics regression scope

Focused mapper implementation must not change:

```text
AP identity normalization
AP inventory paging
Current State cycle completeness
Current State retention
Current State freshness
client Current State semantics
Observation semantics
Home Traffic
Home Activity
Home Health
Visit Lifecycle
```

Unexpected diff outside the focused status path requires Tech Lead review.

---

# 49. Central Lab gate if mapper code is implemented

Coder runs focused/module tests.

Owner + Tech Lead Central Lab perform official exact-candidate acceptance:

1. full regression;
2. Current State status normalization tests;
3. Admin current-state serializer regression;
4. schema-signature/version verification;
5. no-write/read compatibility checks;
6. exact mapper contract tests from the accepted live evidence.

No production mapper deployment from research evidence alone without candidate-artifact acceptance.

---

# 50. Production activation boundary for mapper

If Outcome A leads to a mapper code change, production activation remains separate from this DRAFT.

Before activation record:

```text
accepted research report
exact mapper candidate SHA
Central Lab PASS
Current State schema version
current raw online status baseline
```

After activation confirm:

- stable online AP still maps online;
- no unrelated AP becomes falsely offline;
- Current State cycles remain complete/healthy;
- existing Home Live behavior remains accepted.

---

# 51. Rollback boundary

No schema migration means mapper rollback is code-only.

Rollback does not rewrite historical rows.

If a mapper is found unsafe:

```text
restore prior conservative mapping
```

which returns unproven codes to `other/unknown` rather than inventing offline.

HOME-AP-24H remains disabled/blocked until semantics are safe again.

---

# 52. Required research report conclusion

The final research report MUST choose exactly one:

```text
A. VERIFIED — stable raw offline code; shared mapper sufficient.

B. VERIFIED — physical unavailability is represented by complete-inventory absence;
   additional foundation/storage design required for historical outage state.

C. NOT VERIFIED — controller semantics remain ambiguous/inconsistent.
```

No mixed wording such as:

```text
"probably offline"
"looks like 0 means offline"
```

is acceptable as canonical architecture evidence.

---

# 53. Acceptance — Outcome A

Outcome A is accepted only when all are true:

- two independent outage/recovery runs completed;
- direct complete inventories captured;
- same stable offline code repeated;
- stable online code reproduced before/after;
- candidate offline code not observed in stable online baseline;
- Current State complete-success cycle persisted the raw offline code;
- physical/controller transition timestamps are documented;
- no source-failure interval was misclassified as AP outage;
- Owner + Tech Lead accept the evidence report.

---

# 54. Acceptance — Outcome B

Outcome B is accepted when:

- two runs repeat complete-inventory AP disappearance during physical outage;
- AP reappears after recovery;
- complete inventories are proven;
- no reliable stable offline status row exists;
- Current State persistence limitation is documented;
- Owner + Tech Lead accept the evidence.

Outcome B closes the research question but does NOT unlock HOME-AP-24H implementation by itself.

---

# 55. Acceptance — Outcome C

Outcome C requires no mapper change.

It is the correct result when evidence is insufficient.

HOME-AP-24H remains blocked.

A follow-up research revision must explain what new evidence could resolve the ambiguity.

---

# 56. Architecture invariant after this task

Whatever result occurs, CaptivPortal must preserve:

```text
source failure ≠ AP outage
partial inventory ≠ AP outage
Observation partial ≠ AP outage
unproven numeric status ≠ AP outage
```

Only an accepted canonical AP-state authority may produce offline/unavailable.

---

# 57. Expected happy-path canonical contract

If Outcome A succeeds, expected conceptual mapping becomes:

```text
raw status 1               → online
proven research status X   → offline
other integer              → other
missing/unusable           → unknown
```

`X` is intentionally not specified in this DRAFT.

It must come from live evidence.

---

# 58. HOME-AP-24H handoff contract

After accepted Outcome A and mapper implementation acceptance, provide HOME-AP-24H Architect with:

```text
research outcome
controller/AP versions tested
canonical online code set
canonical offline code set
unproven/transition codes observed
AP-present/absent behavior during outage
controller detection latency range
controller recovery latency range
shared mapper code location/contract
exact accepted mapper SHA
```

HOME-AP-24H FINAL then defines deterministic outage intervals/duration using that contract.

---

# 59. Architecture stop condition — version dependence

If the same controlled test produces different status semantics across:

```text
controller versions
AP models
firmware versions
```

then a global unconditional mapper is unsafe.

Return to Architect/Tech Lead.

Do not introduce model/version conditionals ad hoc without a separate approved compatibility contract.

---

# 60. Architecture stop condition — status collision

If a candidate offline code is also observed while the AP is stably serving normally:

```text
STOP mapping proposal
```

The code is not sufficient as a standalone offline semantic.

Supporting fields may be researched in R2 only after Tech Lead review; do not immediately invent compound heuristics.

---

# 61. Architecture stop condition — absence-only model

If the only reliable outage evidence is complete-inventory absence:

```text
STOP HOME-AP-24H FINALization
```

until an explicit architecture decision defines whether/how negative inventory membership is persisted/read historically.

This DRAFT does not pre-select that design.

---

# 62. No implementation from DRAFT

This document does not authorize:

```text
code change
branch
commit
push
PR
deploy
production config change
physical AP disruption
```

It defines the research contract for review.

---

# 63. Required next step

Return:

```text
TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01-DRAFT.md
```

to Owner / Tech Lead.

After architectural approval, Owner explicitly authorizes the live controlled test window and target AP.

Only after accepted live evidence may the canonical mapper be finalized/implemented.

HOME-AP-24H remains implementation-blocked until this prerequisite reaches an accepted outcome.
