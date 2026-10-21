# TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01 — Canonical Omada AP status semantics — DRAFT R2

**Project:** CaptivPortal  
**Area:** Current Network State → AP status semantics  
**Type:** Controlled live research + canonical semantic contract  
**Priority:** Prerequisite for `TASK-HOME-AP-24H-01`  
**Status:** DRAFT R2 — Owner / Tech Lead review required before Phase R live authorization  
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

# 2. Dependency relationship and mandatory phase split

This task is an explicit mandatory prerequisite for:

```text
TASK-HOME-AP-24H-01
```

HOME-AP-24H implementation MUST NOT start until this prerequisite closes.

This one TASK contains two strictly separated phases.

## Phase R — Research

Phase R contains ONLY:

```text
read-only precheck/sampling
explicitly authorized physical power-loss test
evidence capture/correlation
two independent outage/recovery runs
research conclusion A/B/C
```

Phase R MUST NOT:

```text
modify Current State code
create mapper code
commit mapper changes
modify HOME-AP-24H code
modify DB schema
change collector cadence
deploy semantic changes
```

Phase R ends only when Owner + Tech Lead accept exactly one research outcome:

```text
A
B
C
```

## Phase M — Mapper implementation

Phase M is permitted ONLY if:

```text
Outcome A = accepted by Owner + Tech Lead
```

Before accepted Outcome A:

```text
NO mapper commit
NO Current State status-code semantic change
NO HOME-AP-24H implementation
```

Phase M then:

1. creates/finalizes one shared mapper authority;
2. switches Current State normalization to that mapper;
3. proves the mapper contract with focused tests;
4. preserves existing Home Live product presentation;
5. passes the official exact-artifact gate;
6. hands the mapper location/API and accepted evidence to HOME-AP-24H architecture.

Phase M does NOT implement HOME-AP-24H.

Expected dependency flow:

```text
DRAFT R2
→ explicit Phase R live authorization
→ Phase R controlled experiment
→ evidence report
→ Owner + Tech Lead accept A/B/C

if A:
    Phase M mapper implementation
    → exact-artifact acceptance
    → mapper handoff
    → HOME-AP-24H FINAL

if B/C:
    HOME-AP-24H remains blocked
    → Architect/Tech Lead decides next semantic/foundation step
```

No storage/schema dependency is assumed in advance for Outcome B.

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

This DRAFT defines Phase R but does not authorize disruption.

Before the physical outage portion of Phase R, Owner must explicitly approve:

```text
Site
designated test AP
maintenance/disruption window
canonical power-loss action
operator performing the action
restore procedure
maximum dwell
```

The canonical primary outage action is:

```text
complete removal of electrical power / PoE from the designated test AP
```

until the AP is physically not operating.

This is the required ground truth for deciding the controller's AP-offline semantics.

Do NOT substitute as the primary proof:

```text
software reboot
uplink cable disconnect
controller-side disable
logical isolation
SSID disable
```

because those actions may represent different controller states.

They may be characterized later as optional transition experiments, but they cannot replace the two required power-loss outage runs.

The selected AP must be safe to disrupt for the test window.

If power removal could cause unacceptable guest/service impact, Phase R is postponed rather than tested with a weaker or ambiguous action.

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

# 12. Direct sampler constraints and source contract

Any temporary diagnostic sampler must be:

```text
read-only
Site-scoped
bounded
sanitized
target-MAC filtered only AFTER complete inventory retrieval
```

The sampler MUST use the same AP inventory source contract as production Current State:

```text
list_observation_access_points
```

through the same bounded paginated inventory semantics.

Preferred:

```text
reuse the existing read-only inventory/pagination logic
```

If direct reuse is impractical, a diagnostic wrapper MUST be strictly contract-equivalent.

It MUST NOT introduce a second definition of `complete inventory`.

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

A direct sample can support presence/absence semantics only when it satisfies the same production inventory completeness contract.

For every sample, verify all of the following:

```text
every required page request succeeded
pages are read sequentially starting at page 1
returned page number matches requested page
page size obeys the configured bound
total_rows is a non-negative integer
total_rows stays consistent across pages
accumulated row count never exceeds total_rows
pagination does not terminate early on an inconsistent short/empty page
configured max_pages is not exceeded
configured max_rows is not exceeded
no row-limit/page-limit truncation occurred
final accumulated row count == total_rows
```

Record at minimum:

```text
request_result
failure_category
page_size
pages_read
total_rows
rows_collected
max_pages
max_rows
inventory_complete
```

Only then:

```text
target_present=false
```

has semantic value.

If inventory collection is partial/failed/truncated:

```text
target AP missing
```

means nothing about AP availability.

Such a sample is source-unavailable/incomplete evidence only.

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

# 17. Clock authority contract

All latency/correlation evidence MUST use one trusted clock authority:

```text
production CaptivPortal host wall clock
```

Before Stage A / Phase R evidence capture:

1. record the production host UTC time;
2. record host timezone;
3. record NTP/time-synchronization state;
4. confirm the host clock is considered synchronized/usable for the experiment.

All research scripts/samplers run on that trusted host or timestamp their evidence from that host.

Operator physical action timestamps SHOULD be generated by the research script/tool on the production host, for example by an explicit:

```text
mark power_off
mark power_restored
```

operator action immediately before/after the physical action as defined by the runbook.

Do NOT use a phone/watch/manual local timestamp as the latency authority when a production-host marker can be generated.

Record:

```text
host_clock_state
operator action markers from host clock
direct sample timestamp from host clock
Current State capture_started_at
Current State capture_finished_at
```

All persisted/displayed experiment timestamps are canonical UTC.

Do not substitute:

```text
file mtime
Loki ingestion time
chat message time
phone clock
```

for the experiment clock authority.

If NTP/time state is not trustworthy:

```text
STOP before disruptive test
```

because controller/direct/Current-State latency would not be safely comparable.

# 18. Stage A — Phase R read-only precheck

Before physical disruption:

1. verify exact repository/deployed baseline;
2. verify production-host clock/NTP state per section 17;
3. verify Current State runtime is active/degraded but readable;
4. verify target Site identity;
5. verify target AP canonical MAC;
6. obtain a complete AP inventory through the section 12/14 inventory contract;
7. confirm target AP is present;
8. record current raw status;
9. record at least three stable direct samples;
10. record at least one complete successful Current State AP cycle containing the target;
11. verify no unrelated configuration/deployment change is planned during the experiment.

If baseline/clock/inventory is not stable:

```text
STOP
```

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

# 20. Stage B — Phase R outage run 1

After explicit Owner live-test approval:

1. generate the production-host `DISRUPTION_INITIATED` marker;
2. completely remove electrical power / PoE from the designated test AP;
3. once power removal is physically complete, generate the production-host `PHYSICALLY_UNAVAILABLE` marker;
4. confirm the target AP is physically not operating;
5. continue bounded direct inventory sampling;
6. allow Current State to continue its normal production cadence unchanged;
7. do not change collector settings;
8. observe until the evidence target or bounded Stage B stop condition is reached.

This complete power/PoE removal is the canonical primary outage test.

Reboot, uplink disconnect, controller disable or network isolation do not satisfy the primary outage-run requirement.

No unrelated Omada settings are changed.

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

1. ground truth is complete physical power/PoE loss;
2. direct inventory is complete under the production-equivalent pagination contract;
3. target AP remains present;
4. `status_code == X` in at least three consecutive direct samples;
5. stable duration is at least 30 seconds;
6. `X` was not observed in the stable-online baseline;
7. the same outage run contains at least **two consecutive** authoritative Current State AP inventory cycles:
   ```text
   kind='ap'
   result='success'
   complete=1
   ```
   where:
   ```text
   target AP is present
   raw status_code == X
   ```
8. both persisted cycles occur after the physical-unavailable marker and before restore initiation.

If controller detection latency or the bounded 10-minute dwell prevents obtaining two such cycles:

```text
do NOT weaken the rule
do NOT force Outcome A
return the run as inconclusive for mapper acceptance
```

This is only candidate evidence until the second independent outage run reproduces it.

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

# 24. Stage C — Phase R recovery run 1

1. generate the production-host `RECOVERY_INITIATED` marker;
2. restore electrical power / PoE to the designated AP;
3. once physical restore action is complete, generate the host `POWER_RESTORED` marker;
4. continue direct sampling;
5. wait for complete inventories;
6. record first reappearance if it had disappeared;
7. record first raw canonical-online status;
8. continue until at least three stable complete direct samples show recovered online state;
9. require at least one complete-success Current State AP cycle containing the target with canonical online raw status;
10. strongly prefer two consecutive complete-success recovered cycles when the bounded test window permits.

If even one authoritative recovered Current State cycle cannot be obtained within the bounded recovery window:

```text
the run is inconclusive for Outcome A
```

Record controller recovery latency separately from physical restore time.

# 25. Stage D — Phase R independent repetition

Repeat the complete power-loss + recovery sequence a second time after the AP is stable.

The second independent run is mandatory for accepting Outcome A or B.

It must reproduce:

```text
same complete power/PoE-loss ground truth
same production-equivalent inventory presence behavior
same stable offline code or same stable absence behavior
same Current State persistence behavior
same recovery semantics
```

For Outcome A, run 2 independently must satisfy the same:

```text
>= 3 stable direct samples
>= 30 s stable candidate status
>= 2 consecutive complete-success Current State outage cycles
>= 1 complete-success recovered online cycle
```

with two recovered cycles preferred when available.

Small timing differences are acceptable; semantic behavior must match.

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
- an individual AP row is positive-presence evidence, while complete successful inventory cycles also permit historical negative membership to be derived by set difference;
- negative membership is therefore available as evidence, but its physical meaning remains ambiguous;
- historical absence must be given an explicit semantic contract before it becomes outage evidence.

Pattern B therefore triggers an architecture return for semantics/foundation design, not an automatic storage-migration decision.

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

# 32. Phase M shared mapper authority

This section applies ONLY after Owner + Tech Lead accept Outcome A.

Phase M creates one shared pure semantic boundary, for example:

```text
app/current_state/ap_status.py
```

with a concept such as:

```text
classify_ap_status_code(raw_status)
```

Exact file/function naming is coder/Tech Lead controlled, but there must be one implementation authority.

Phase M consumer:

```text
Current State normalizer
```

Phase M MUST NOT implement HOME-AP-24H.

Instead Phase M handoff records:

```text
mapper file/module
public function/API
accepted raw-code mapping
candidate SHA
test evidence
```

The future HOME-AP-24H FINAL is responsible for importing this same shared mapper and proving that it does not duplicate the mapping table.

# 33. Historical compatibility rule

Existing historical rows may contain:

```text
status_code = X
status_classification = other
```

where Phase R later proves:

```text
X = offline
```

Do NOT backfill or rewrite historical DB rows merely to update semantics.

Phase M changes only new Current State normalization to use the shared mapper.

The accepted handoff MUST state that future HOME-AP-24H historical interpretation uses:

```text
canonical shared mapper(status_code)
```

rather than trusting source-era `status_classification`.

Stored historical classification remains source-era metadata.

Raw code + the accepted canonical mapper becomes the semantic authority for future AP-24H.

# 34. Current State and existing Home Live compatibility contract

Current State already models `offline` as a valid internal classification.

Therefore Outcome A / Phase M may legitimately make:

```text
CurrentApSummary.offline_count > 0
```

without schema change.

That internal semantic improvement MUST NOT redesign existing Home Live presentation in this TASK.

The current accepted Admin/Home Live compatibility contract remains:

```text
AP summary product "Other"
=
offline_count + other_count
```

and current AP product rows remain:

```text
Online  when internal status == online
Unknown when internal status == unknown
Other   for offline/other/non-online non-unknown status
```

Therefore Phase M acceptance requires:

- internal `offline_count` may become non-zero;
- Home Live summary still displays `offline + other` as `Other`;
- current AP product row for internal offline still displays `Other`;
- no new `Offline` Home Live UI state/label is introduced;
- Home Live payload/serializer contract otherwise remains unchanged.

HOME-AP-24H may later use canonical offline separately under its own FINAL contract.

Any unexpected product presentation change caused by the mapper must be returned to Tech Lead rather than patched silently.

# 35. Research outcome A — stable offline code

Outcome A requires:

```text
AP remains present in complete inventory during outage
same stable offline code reproduced in two complete power-loss runs
each outage run has >=2 consecutive complete-success Current State cycles with the same candidate code
each recovery run has >=1 complete-success Current State cycle with canonical online state
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
AP absent while physically power-off
AP reappears after recovery
no stable offline status row exists
```

Result:

```text
RESEARCH PASS / HOME-AP-24H DEPENDENCY REMAINS BLOCKED
```

Current State complete successful inventories already preserve enough positive set membership to derive historically:

```text
AP X present in complete inventory N
AP X absent from later complete inventory N+1
```

via set difference.

Therefore Outcome B does **not** predeclare that new persistence/schema is required.

The unresolved problem is primarily semantic:

```text
complete-inventory absence
may mean:
    physically offline
    removed
    moved/reassigned
    forgotten/unmanaged
    another controller lifecycle operation
```

Return to Architect/Tech Lead to decide what additional semantic/foundation contract can distinguish those cases safely.

A new persistence/schema contract MAY be needed, but only if the follow-up architecture proves it necessary.

No absence=offline rule is authorized by this DRAFT.

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

# 47. Phase M mapper focused test plan if Outcome A

These tests are authorized only after Outcome A is accepted and Phase M is separately started.

1. proven online code → `online`.
2. proven offline code → `offline`.
3. every unproven numeric code → `other`.
4. null/non-int → `unknown`.
5. bool is not accidentally accepted as int if existing strict-int contract forbids it.
6. Current State normalizer imports/uses the one shared mapper authority.
7. historical compatibility contract is documented for future AP-24H handoff; no historical DB rewrite occurs.
8. no schema change.
9. `CurrentApSummary.offline_count` can become non-zero.
10. existing Home Live summary still serializes `offline_count + other_count` as product `Other`.
11. existing Home Live AP row still serializes internal offline as product `Other`.
12. no new Home Live `Offline` presentation is introduced.
13. Current State summary invariants hold with non-zero offline count.
14. shared mapper module/API/location is included in the HOME-AP-24H architecture handoff.

There is intentionally NO Phase M test requiring a HOME-AP-24H code path because HOME-AP-24H implementation remains governance-blocked during this task.

The future HOME-AP-24H FINAL must test that it imports the shared mapper and contains no duplicate raw-code mapping.

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

# 49. Phase M exact-artifact gate

This section is inactive during Phase R.

Only after accepted Outcome A and separate Phase M start:

Coder runs focused/module tests for the mapper candidate.

Owner + Tech Lead perform the official exact-candidate acceptance:

1. full regression;
2. Current State status normalization tests;
3. exact shared-mapper contract from accepted live evidence;
4. Current State summary regression with non-zero offline count;
5. existing Admin/Home Live `Other = offline + other` regression;
6. existing current AP product-row `Other` regression;
7. schema-signature/version verification;
8. no unrelated Home/API semantic drift.

No production mapper deployment from research evidence alone without candidate-artifact acceptance.

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

# 52. Required Phase R research report conclusion

The final Phase R report MUST choose exactly one:

```text
A. VERIFIED — stable raw offline code; pure shared mapper is sufficient.

B. VERIFIED — tested physical power loss is represented by complete-inventory absence;
   HOME dependency remains blocked pending an additional semantic/foundation decision.
   New storage/schema is NOT assumed in advance.

C. NOT VERIFIED — controller semantics remain ambiguous/inconsistent.
```

No mixed wording such as:

```text
"probably offline"
"looks like 0 means offline"
```

is acceptable as canonical architecture evidence.

Only accepted A unlocks Phase M.

# 53. Acceptance — Outcome A

Outcome A is accepted only when all are true:

- two independent complete power-loss/recovery runs completed;
- direct inventories satisfy the production-equivalent completeness contract;
- same stable offline code repeated;
- each run has >=3 consecutive stable direct candidate samples;
- each run has >=30 seconds stable candidate status;
- stable online code reproduced before/after;
- candidate offline code not observed in stable online baseline;
- **each outage run** has >=2 consecutive complete-success Current State AP cycles with target present and the same raw offline candidate;
- **each recovery run** has >=1 complete-success Current State AP cycle with target present and canonical online raw status;
- two recovery cycles are preferred when bounded timing allows;
- trusted production-host clock/NTP evidence is recorded;
- operator/direct/Current-State timestamps use the same host clock authority;
- physical/controller transition latencies are documented;
- no source-failure interval was misclassified as AP outage;
- Owner + Tech Lead accept the evidence report.

If the bounded dwell cannot produce the required persistence evidence:

```text
Outcome A is NOT forced
```

and the run/report remains inconclusive or Outcome C as supported by evidence.

# 54. Acceptance — Outcome B

Outcome B is accepted when:

- two complete power-loss runs repeat AP disappearance from complete successful inventory;
- the inventory completeness contract is proven for the relevant direct samples;
- AP is positively present before outage and reappears after recovery;
- no reliable stable offline status row exists;
- historical complete-inventory set difference is documented as available evidence;
- the semantic ambiguity of absence is explicitly documented;
- no schema/storage requirement is asserted without separate architectural proof;
- Owner + Tech Lead accept the evidence.

Outcome B closes the observed controller behavior question but does NOT unlock HOME-AP-24H implementation by itself.

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

Only after:

```text
Phase R Outcome A accepted
+
Phase M mapper exact-artifact accepted
```

provide HOME-AP-24H Architect with:

- exact tested controller version;
- exact tested AP model/firmware;
- tested Site context;
- raw online code;
- raw offline code;
- unproven/transition codes retained as `other`;
- measured outage detection latency;
- measured recovery latency;
- whether AP remained inventory-present;
- shared mapper code location/contract;
- exact accepted mapper SHA;
- Current State schema version;
- proof that historical raw codes remain usable without backfill;
- Home Live compatibility regression result.

HOME-AP-24H FINAL must import/use that shared mapper and must test that no duplicate raw-code mapping exists in the AP-24H code path.

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

If the only reliable power-loss evidence is complete-inventory absence:

```text
do not create a fake status code
do not silently map absence to offline
```

Return to architecture.

Existing complete inventories already permit historical set-difference analysis.

The unresolved question is whether/when that absence is semantically authoritative for physical unavailability versus controller lifecycle changes.

HOME-AP-24H remains blocked until an explicit architecture decision resolves that semantic/foundation contract.

A persistence/schema change is possible but is NOT assumed mandatory in advance.

# 62. No implementation or live action from DRAFT R2

This DRAFT R2 does not authorize:

```text
Phase R physical AP disruption
Phase M code changes
branch creation
commit
push
PR
merge
production deployment
HOME-AP-24H implementation
```

Phase R live execution requires explicit Owner live-test authorization.

Phase M requires accepted Outcome A plus a separate implementation start decision.

# 63. Required next step

Return this DRAFT R2 to:

```text
Owner
Tech Lead
```

for review.

Next possible action is ONLY:

```text
explicit Owner authorization for Phase R controlled live test
```

After Phase R, produce the evidence report and obtain Owner + Tech Lead acceptance of A/B/C.

Only accepted Outcome A may unlock Phase M mapper implementation.

HOME-AP-24H implementation remains blocked throughout Phase R and Phase M and resumes only after the mapper artifact/handoff is accepted.

