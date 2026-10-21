# TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01 — Phase M Shared Mapper Implementation — FINAL

**Project:** CaptivPortal  
**Area:** Current State → canonical AP status semantics  
**Type:** Narrow corrective implementation contract  
**Status:** FINAL — Phase R Outcome A accepted; implementation start remains Owner / Tech Lead controlled  
**Implementation authorization:** NOT GRANTED BY THIS DOCUMENT  
**Production activation:** NOT GRANTED  
**Prepared:** 2026-08-28  
**Exact repository baseline:** `origin/main@bc929dbe7c1687415bd4eeda971dcbc9376d8bbc`  
**Research input:** `Omada_AP_Status_Semantics_Research_Report.md`  
**Research verdict:** `Phase R — ACCEPTED / Outcome A — VERIFIED`  
**Schema decision:** Current State schema v1 unchanged  
**Backfill:** NONE  

---

# 0. Executive decision

Phase R has closed the semantic uncertainty for the current production compatibility tuple.

Accepted canonical mapping:

```text
raw status == 1  → online
raw status == 0  → offline
other integer    → other
missing/unusable → unknown
```

Explicit accepted transition evidence:

```text
raw status == 3
→ other
```

`3` is a controller transition / missed-heartbeat state.

It is NOT canonical offline.

The designated AP remained present in complete successful Site AP inventories during physical power loss.

Therefore the accepted architecture is:

```text
one pure shared mapper
+
Current State normalizer uses it for new rows
+
future HOME-AP-24H imports the same mapper for historical raw status_code
+
NO DB/schema/storage foundation
+
NO backfill
```

Phase M is intentionally narrow.

It does NOT re-run status research.

It does NOT modify HOME-AP-24H.

It does NOT add version/model conditionals.

---

# 1. Accepted compatibility evidence

The accepted research authority is limited to the tested production tuple:

```text
Omada Controller:
5.14.32.3

AP:
EAP613(EU) v1.0

Firmware:
1.8.3 Build 20260617 Rel. 36045

Site:
Home
```

Accepted strict runs:

```text
Run #2
Run #3
```

Both independently showed:

```text
stable healthy:
1

loss transition:
3

stable controller-observed unavailable:
0

recovery:
1
```

Both contained authoritative persisted Current State outage evidence:

```text
current_state_cycles.kind='ap'
result='success'
complete=1

target AP present
status_code=0
```

Recovery was also confirmed by complete-success Current State cycles with:

```text
status_code=1
```

---

# 2. Canonical semantic meaning

The canonical mapper describes:

```text
controller-observed AP availability state
```

It does NOT claim:

```text
physical power state at the same instant
electrical SLA
instant link-loss detection
instant recovery
```

The controller has detection/recovery latency.

Canonical exact latency evidence comes from Run #3.

Physical power OFF:

```text
2026-08-27T22:06:58.426Z
```

Observed transition:

```text
1 → 3:
40.005 s < latency <= 50.128 s
```

First stable `0`:

```text
590.064 s < latency <= 599.960 s
```

So controller-observed offline appeared approximately:

```text
9m50s–10m00s
```

after physical power loss.

Physical power ON:

```text
2026-08-27T22:21:58.511Z
```

First recovered `1`:

```text
2026-08-27T22:24:38.435Z
```

approximately:

```text
2m30s–2m40s
```

later.

Run #2 remains accepted repeatability evidence but is NOT canonical numeric latency evidence because its retained report excerpt does not contain the exact host-side physical power-off marker.

---

# 3. Mapper authority

Create exactly one canonical pure mapper authority at:

```text
app/current_state/ap_status.py
```

Required public function:

```python
classify_ap_status_code(raw_status)
```

Required output domain:

```text
online
offline
other
unknown
```

Required semantics:

```text
type(raw_status) is int and raw_status == 1
→ online

type(raw_status) is int and raw_status == 0
→ offline

type(raw_status) is int and raw_status not in {0,1}
→ other

raw_status is None
→ unknown

raw_status is bool
→ unknown

raw_status is string/float/object/other unusable type
→ unknown
```

`3` therefore returns:

```text
other
```

No special-case transition branch is needed.

No model/version/FW conditional exists in the mapper.

---

# 4. Current State normalization boundary

Current baseline normalizer currently performs local mapping equivalent to:

```text
1 → online
other int → other
missing → unknown
```

Phase M replaces only that local classification expression with the shared mapper.

Required conceptual flow:

```text
status_raw = controller field
        ↓
existing strict integer sanitation
        ↓
status_code = int | None
        ↓
classify_ap_status_code(status_code)
        ↓
status_classification
```

The existing sanitation/warning behavior remains unchanged.

Examples:

```text
raw integer 1
→ status_code=1
→ online

raw integer 0
→ status_code=0
→ offline

raw integer 3
→ status_code=3
→ other

raw integer 99
→ status_code=99
→ other

raw "1"
→ status_code=None
→ unknown
→ existing data-quality warning remains

raw null
→ status_code=None
→ unknown
```

Do NOT broaden accepted source types.

---

# 5. No duplicate mapping authority

Forbidden after Phase M:

```text
if status_code == 0: ...
```

in any new HOME-AP-24H implementation.

Forbidden:

```text
not 1 → offline
```

Forbidden heuristics:

```text
lastSeen frozen → offline
uptime reset → offline
AP absence → offline
raw 3 → offline
```

Future HOME-AP-24H must import/use:

```text
app.current_state.ap_status.classify_ap_status_code
```

or an explicit package re-export of that same function.

No copied mapping table.

No equivalent local helper.

---

# 6. Historical compatibility

Phase M performs:

```text
NO BACKFILL
```

Existing historical rows remain byte-for-byte unchanged.

Example existing pre-mapper row:

```text
status_code=0
status_classification='other'
```

remains stored that way.

This is accepted.

For historical semantic consumers such as future HOME-AP-24H:

```text
raw status_code
+
shared mapper
```

is authoritative.

Source-era persisted:

```text
status_classification
```

does NOT override the shared mapper when raw `status_code` is available.

Thus historical `0` becomes semantically usable without rewriting history.

---

# 7. Current State schema compatibility

Current State repository already permits classification:

```text
offline
```

inside its v1 schema/domain.

Phase M MUST keep:

```text
PRAGMA user_version = 1
```

No:

```text
table
column
index
migration
retention change
```

is required.

Repository schema signature must remain unchanged.

---

# 8. Current State read-service compatibility

Current `CurrentApSummary` already separates internal counts:

```text
online_count
offline_count
other_count
unknown_count
```

After new rows are produced by the mapper:

```text
offline_count > 0
```

is expected and valid.

No new Current State read DTO is required.

No API contract change is required for this task.

No historical read-time rewrite of Current State APIs is required.

---

# 9. Existing Home Live product compatibility

Existing Home Live presentation MUST remain unchanged.

Current summary product contract is:

```text
product Other
=
offline_count + other_count
```

Current AP row product contract is:

```text
online  → Online
unknown → Unknown
offline → Other
other   → Other
```

Phase M MUST preserve both.

Therefore:

```text
Current State internal semantics improve
WITHOUT
introducing a new Home Live "Offline" product label
```

No Home Live redesign belongs to Phase M.

---

# 10. Compatibility scope

The mapper is canonical for the current production deployment because Outcome A was accepted for the tested tuple.

Do NOT describe the evidence as universally proven for:

```text
all Omada Controller versions
all AP models
all hardware revisions
all firmware versions
```

Do NOT add ad-hoc runtime branches such as:

```text
if model == EAP613...
if controller_version == ...
```

inside the mapper.

If the production compatibility tuple changes materially in the future:

```text
Controller version
AP model/hardware
firmware
```

Owner / Tech Lead should assess whether re-validation is required.

The current mapper remains simple until evidence requires a controlled compatibility decision.

---

# 11. Accepted inventory finding

Outcome A also proved:

```text
physical AP power loss
does NOT remove the AP
from complete successful Site AP inventory
```

for the tested tuple.

Accepted outage samples contained:

```text
inventory_complete=true
target_present=true
raw status=0
```

Therefore Phase M does NOT require:

```text
absence inference
negative-membership mapper
new persistence
Pattern B storage
```

AP absence remains semantically separate.

---

# 12. Files expected to change

Expected narrow implementation surface:

```text
NEW:
app/current_state/ap_status.py

MODIFY:
app/current_state/normalizer.py

TESTS:
tests/current_state/test_normalizer.py
tests/current_state/test_read_service.py
tests/admin_web/test_home_live.py
```

Optional only if package export is useful:

```text
app/current_state/__init__.py
```

No other production module should require modification.

If implementation requires materially more surface, return for architecture review.

---

# 13. Pure mapper tests

Mandatory focused tests:

```text
1  → online
0  → offline
3  → other
2  → other
99 → other
-1 → other

None    → unknown
True    → unknown
False   → unknown
"0"     → unknown
"1"     → unknown
0.0     → unknown
1.0     → unknown
object  → unknown
```

The key regression:

```text
3 != offline
```

must be explicit.

The key anti-pattern regression:

```text
any integer except 1
```

must NOT all map to offline.

---

# 14. Current State normalizer tests

Required:

```text
controller status 1
→ persisted status_code=1
→ status_classification=online

controller status 0
→ persisted status_code=0
→ status_classification=offline

controller status 3
→ persisted status_code=3
→ status_classification=other

controller status 2/99
→ other

missing status
→ unknown

unusable status "0"/"1"
→ status_code=None
→ unknown
→ existing warning behavior preserved
```

No AP identity/metadata normalization changes.

---

# 15. Persistence tests

Using the existing Current State schema:

1. publish complete-success AP cycle containing `offline`;
2. read it back safely;
3. `quick_check=ok`;
4. foreign keys valid;
5. schema version remains 1;
6. exact schema signature unchanged.

No migration code may appear.

---

# 16. Read-service tests

Required Current State behavior:

```text
latest complete cycle contains:
1 online
1 offline
1 other
1 unknown
```

Then:

```text
ap_total       = 4
online_count   = 1
offline_count  = 1
other_count    = 1
unknown_count  = 1
```

Count invariant remains valid.

Current AP page returns internal classification:

```text
offline
```

for the offline row.

---

# 17. Home Live compatibility tests

Mandatory regression acceptance:

Given Current State internal counts:

```text
offline_count = 2
other_count   = 3
```

existing Admin/Home Live summary still returns:

```text
Other = 5
```

not a separate Offline count.

For AP row serialization:

```text
status_classification=offline
→ product_status_classification=Other
```

Also verify:

```text
online  → Online
unknown → Unknown
other   → Other
```

No new Home Live UI label, DOM hook or API field.

---

# 18. Historical no-backfill tests

Create/seed a pre-mapper historical row:

```text
status_code=0
status_classification='other'
```

Phase M must not rewrite it.

Verify:

```text
stored value remains 'other'
```

Then separately prove:

```text
classify_ap_status_code(0) == 'offline'
```

This is the intended historical interpretation contract for future HOME-AP-24H.

---

# 19. No HOME-AP-24H implementation in Phase M

Phase M MUST NOT:

```text
create /home/ap-24h route
change Home template
change admin.js
change AP-24H feature flags
implement 24h aggregation
implement unavailable_seconds
add AP-24H tests
```

The only HOME-related deliverable is a handoff statement:

```text
shared mapper path/API
candidate commit SHA
accepted mapping contract
schema/backfill result
```

Future HOME implementation consumes that artifact.

---

# 20. Exact mapper handoff contract

After Phase M implementation candidate exists, coder handoff must record:

```text
mapper_module:
app/current_state/ap_status.py

mapper_api:
classify_ap_status_code(raw_status)

candidate_commit:
<SHA>

mapping:
1=online
0=offline
other_int=other
missing_or_unusable=unknown

transition:
3=other

schema_changed:
NO

backfill:
NO
```

HOME-AP-24H implementation stays blocked until Owner + Tech Lead accept this exact mapper artifact.

---

# 21. Focused coder test ownership

Coder runs focused/module tests for the candidate artifact.

Required families:

```text
mapper unit tests
Current State normalizer tests
Current State persistence/repository tests
Current State read-service tests
Admin Home Live serialization regressions
```

Coder does NOT perform the official full-repository Central Lab gate.

Coder does NOT physically power-cycle an AP.

Phase R already supplied live semantic evidence.

---

# 22. Central Lab exact-artifact acceptance

Official gate is owned by:

```text
Owner
Tech Lead
```

against the exact candidate commit.

Required:

1. exact candidate SHA recorded;
2. full repository regression;
3. mapper focused tests;
4. normalizer focused tests;
5. Current State repository/read-service regressions;
6. Home Live compatibility regression;
7. schema signature comparison;
8. `PRAGMA user_version=1`;
9. `PRAGMA quick_check=ok`;
10. `PRAGMA foreign_key_check` clean;
11. no new dependency;
12. no unapproved subsystem drift.

Only the exact accepted artifact may proceed to production rollout.

---

# 23. Production rollout precheck

Before deployment Owner records:

```text
current deployed SHA
candidate SHA

Current State:
runtime state
schema version
latest complete AP cycle
AP interval
history retention

Admin:
Home Live enabled/disabled state
```

No physical AP outage is required for Phase M rollout.

No setting change is required.

---

# 24. Production rollout

Expected rollout:

1. deploy exact accepted code artifact;
2. no DB migration;
3. restart application if normal deployment requires it;
4. wait for normal Current State AP collection;
5. confirm runtime healthy;
6. confirm new complete AP cycle persists normal `status=1 → online`;
7. confirm existing Home Live contract unchanged;
8. verify schema version/signature unchanged.

Do NOT create a new deliberate outage merely to prove `0` again.

The accepted Phase R report is the live semantic authority.

---

# 25. Production forward acceptance

Required:

```text
application starts normally
Current State runtime remains active/degraded according to existing contract
new AP rows with raw 1 persist as online
Home Live current AP summary remains product-compatible
Home Live AP rows remain product-compatible
no schema migration occurred
no historical rows rewritten
```

If a natural raw `0` occurs during observation, it should persist as `offline`; this is useful supporting evidence but is NOT required to intentionally trigger.

---

# 26. Rollback

Rollback is code-only.

Because there is:

```text
NO schema change
NO backfill
```

rollback requires:

1. restore previous application artifact;
2. restart normally if needed.

Rows created during the mapper deployment may contain:

```text
status_classification='offline'
```

The existing schema and read service already accept that value.

Do NOT mutate those rows during rollback.

Existing Home Live safely collapses offline to product `Other`.

---

# 27. Telemetry

No new telemetry is required solely for mapper classification.

Do NOT emit one log event per AP status mapping.

Existing Current State cycle telemetry remains sufficient.

If implementation adds telemetry anyway, it must be bounded and must not create AP-MAC high-cardinality operational noise.

---

# 28. Security / privacy

No new sensitive data.

No Omada credentials.

No raw token/logging changes.

No new endpoint.

No Admin authorization change.

---

# 29. Explicit non-goals

Phase M does NOT:

- re-run Phase R;
- power-cycle APs;
- change Current State DB schema;
- backfill history;
- add absence-based outage semantics;
- use `lastSeen` heuristic;
- use uptime heuristic;
- map `3` to offline;
- map every non-1 integer to offline;
- add version/model/FW branching;
- change Current State cadence;
- change Current State retention;
- change Observation;
- change Analytics;
- implement HOME-AP-24H;
- change Home Live presentation;
- change Auth;
- change Omada authorization;
- change Visit Lifecycle;
- change CAPPORT;
- change Public Traffic;
- change webhook schema;
- change Grafana/Loki/Alloy.

---

# 30. Architecture stop conditions

Return to Owner / Tech Lead if implementation appears to require:

```text
schema migration
new persistent table
status inference from AP absence
status inference from lastSeen
status inference from uptime
version/model conditional mapping
Home Live Offline UI
HOME-AP-24H code
collector cadence changes
new Omada call
new dependency
```

Do not expand scope silently.

---

# 31. Acceptance summary

Phase M is accepted only when the exact artifact proves:

```text
shared mapper:
1 → online
0 → offline
other int → other
missing/unusable → unknown

3 → other

Current State normalizer uses that mapper

new rows may persist offline

schema v1 unchanged

historical rows unchanged

Home Live:
offline + other → product Other
offline AP row → product Other

no HOME-AP-24H implementation
```

---

# 32. Required next step

This FINAL defines the implementation contract but does NOT start implementation.

Required sequence:

```text
1. Owner / Tech Lead explicitly authorize Phase M implementation start
2. Coder implements the narrow mapper task
3. Coder returns exact candidate artifact + focused test evidence
4. Owner + Tech Lead run official Central Lab gate
5. Accept shared mapper artifact/handoff
6. Only then HOME-AP-24H implementation becomes unblocked
```

No physical live outage test is part of Phase M.
