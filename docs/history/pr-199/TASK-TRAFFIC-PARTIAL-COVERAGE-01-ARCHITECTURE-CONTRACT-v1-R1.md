# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — ARCHITECTURE CONTRACT v1-R1

**Project:** CaptivPortal  
**Type:** Focused architecture correction / existing AP Traffic products  
**Status:** `R1 CORRECTIONS ISSUED / READY FOR TECH LEAD RE-REVIEW`  
**Implementation authorization:** `NO`  
**Coder:** `HOLD — Tech Lead R1 acceptance required before implementation TASK`  
**Production change:** `NO`  
**Prepared:** 2026-10-11  
**Architecture owner:** CaptivPortal Architect  
**Supersedes:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1.md` only where this R1 explicitly changes semantics; all other v1 decisions are preserved  
**Review basis:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-TECHLEAD-ARCH-REVIEW-R1`  

---

## 0. Executive disposition

### 0.1 Owner proposal verdict

```text
OWNER PROPOSAL:
"confirmed Offline AP does not contribute to the sum of the remaining APs"

ARCHITECTURE VERDICT:
ACCEPT WITH LIMITS
```

The simple idea is accepted **as a read-time coverage rule**, not as a mutation of source facts.

A confirmed Offline AP may be excluded from the expected **currently-online measurement population** only when the authoritative Current State AP status is temporally aligned with the traffic sample and explicitly classifies that AP as `offline`.

The implementation MUST NOT:

```text
write a fake 0 Mbps for the Offline AP
replace NULL with 0 in Observation or Traffic Projection
rewrite source_unavailable to ok
mark an AP Offline from missing traffic alone
infer historical Offline retrospectively from a missing AP measurement
```

The selected architecture is option **3 — combination**:

```text
A. confirmed Offline + all confirmed Online APs measured
   + authoritative aligned Current State population proof
   => complete for the confirmed-online population

B. Online / other / unknown AP missing traffic,
   or status evidence is stale/unavailable,
   or population identity conflicts
   => measured subtotal only, explicitly partial

C. installed population is proven AND that population is fully measured
   => normal complete_installed result

   Installed-population proof is satisfied only by either:
   C1. legacy source cycle complete=1/result=success with full selected-source coverage; or
   C2. aligned_fresh Current State population matched to Observation rows, with full selected-source coverage of I.

   Observation result=partial + all observed rows measured + Current State unavailable
   DOES NOT prove installed population and remains partial_measured.

D. no trustworthy measured traffic
   => unavailable, never zero
```

### 0.2 Core implementation strategy

This TASK does **not** introduce:

```text
new collector
new packet source
new Omada request
new traffic database
new Observation schema
new Traffic Projection schema
new Current State schema
new background worker
new source-of-truth
```

The correction is confined to read/query/presentation semantics.

Current Traffic uses:

```text
existing AP-dynamic Observation facts
+
existing authoritative Current State AP status read boundary
```

Historical Traffic uses:

```text
existing strict Traffic Projection history
+
a bounded read-only overlay of already persisted partial AP-dynamic
Observation cycles
```

The historical overlay does **not** retroactively classify Offline from Current State. That is deliberate: Current State AP history has a short retention contract and must not become a time-dependent historical truth source. Historical partial cycles therefore remain explicitly partial measured evidence.

### 0.3 Final architecture status

```text
TASK = TASK-TRAFFIC-PARTIAL-COVERAGE-01

ARCHITECTURE_STATUS =
R1 CORRECTIONS ISSUED / READY FOR TECH LEAD RE-REVIEW

OWNER_ZERO_CONTRIBUTION_APPROACH =
ACCEPT WITH LIMITS

SELECTED_OPTION =
3 / COMBINATION

NEW_COLLECTOR = NO
NEW_SOURCE = NO
RAW_OBSERVATION_SCHEMA_CHANGE = NO
TRAFFIC_PROJECTION_SCHEMA_CHANGE = NO
CURRENT_STATE_SCHEMA_CHANGE = NO
NEW_DB = NO
BACKFILL_REQUIRED = NO

OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0

IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD
PRODUCTION_CHANGE = NO
```

---

## 0.4 R1 bounded correction disposition

Tech Lead Review R1 accepted the core architecture in principle and returned four P1 items plus one P2 clarification. This R1 is intentionally bounded and does **not** redesign option 3.

```text
P1-01 = CLOSED BY R1
  exact tri-state wire semantics for historical overlay presence/coverage

P1-02 = CLOSED BY R1
  exact directional/pair sample admission, denominators, total semantics and coverage ratio

P1-03 = CLOSED BY R1
  exact failure-state UI/statistics/comparison/AP-share behavior

P1-04 = CLOSED BY R1
  status_measurement_conflict added to the closed Current coverage-reason enum

P2-01 = CLOSED BY R1
  fully measured partial source cycle without installed-population proof remains partial_measured
```

Unchanged constraints:

```text
NEW COLLECTOR = NO
NEW DB = NO
NEW OMADA REQUEST = NO
OBSERVATION WRITER CHANGE = NO
TRAFFIC PROJECTION WRITER/SCHEMA CHANGE = NO
CURRENT STATE SCHEMA CHANGE = NO
FEATURE DEFAULT = OFF
CODER = HOLD
PRODUCTION = NO CHANGE
```

The canonical reading is this complete `v1-R1` document. Where wording differs from v1, R1 controls.

---

# 1. Scope and non-scope

## 1.1 In scope

This contract changes only the interpretation and presentation of existing AP Traffic evidence for:

```text
Home → Traffic Now
Traffic → Current Network Traffic
Traffic → Historical Network Traffic
Traffic → period-quality presentation
Traffic → AP-coverage presentation
```

It freezes:

- AP population authority for Current Traffic;
- confirmed Offline semantics;
- current partial-measurement aggregation;
- Wired/LAN source selection;
- freshness and temporal alignment;
- historical partial-cycle visibility;
- statistical rules for Average / Peak / comparison / AP share;
- Admin API compatibility;
- Home and Traffic UI copy;
- capacity limits;
- rollout and rollback;
- acceptance tests.

## 1.2 Explicitly out of scope

No semantic change is allowed to:

```text
Portal/Auth/CAPPORT
Omada Controller configuration or operations
Visitor Registry identity
Visit Lifecycle
Device Fingerprint
Fingerprint Sensor
Suricata
NI-01 / NI-02B / NI-03 / NI-04
Current Guest Traffic
Completed Guest Session Traffic
Public Traffic
Session Traffic
packet/SPAN/NetFlow traffic
```

No DTI/NI value may be used as fallback for this AP Traffic product.

---

# 2. Pinned baseline and verified current state

## 2.1 Repository / production pin

Verified again on 2026-10-11:

```text
repository = ZaurNavi/CaptivePortal
main HEAD  = e8061de9fbd6da8be5cd269779070a4db4d59d64
TREE       = d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
```

Production `/opt/CaptivePortal` was read-only verified at the same HEAD/TREE.

No source edit, Git mutation, database mutation, service restart or production action was performed during this architecture work.

## 2.2 Real AP-4 incident evidence

Read-only production evidence confirms the Architecture Request.

For AP-4:

```text
AP identity:
name = AP-4
model = EAP110-Outdoor
IP = 192.168.0.80
MAC = 0C:80:63:2F:FB:8D
```

Relevant Current State transitions:

```text
2026-10-10T09:58:02.044Z
status_code = 3
status_classification = other

2026-10-10T09:59:02.362Z
status_code = 0
status_classification = offline
```

The first incident partial AP-dynamic cycle began after that Offline evidence:

```text
cycle_id = c072c809-1d6a-4d87-9c3b-7d161857d480
started  = 2026-10-10T09:59:13.499Z
finished = 2026-10-10T09:59:26.816Z
result   = partial
complete = 0
items_seen   = 4
items_stored = 4
items_skipped = 0
error_count = 2
data_quality_warning_count = 0
```

Within that exact cycle:

```text
AP-1:
Wired pair = ok
LAN pair   = ok

AP-2:
Wired pair = ok
LAN pair   = ok

AP-3:
Wired pair = ok
LAN pair   = ok

AP-4:
Wired = NULL / source_unavailable
LAN   = NULL / source_unavailable
```

Therefore the source already contains the precise distinction required by the Owner proposal:

```text
confirmed AP status = Offline
AND
other AP traffic measurements remain valid
```

Recovery was also automatic at the source level:

```text
AP-4 Current State returned online:
2026-10-11T06:25:38.118Z

first later complete successful AP-dynamic cycle:
started  = 2026-10-11T06:26:26.986Z
finished = 2026-10-11T06:28:33.525Z
```

No software repair or data rewrite was needed.

## 2.3 Why current product hides these facts

Current `app/analytics/current_traffic.py` and `AnalyticsSourceGateway.current_traffic_data()` select only:

```text
state='completed'
complete=1
result='success'
```

The current validator also requires every stored AP row to have:

```text
partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

Thus the incident partial cycle cannot become the current Site Traffic snapshot.

Current Historical Traffic likewise operates primarily on complete successful AP-dynamic cycles.

## 2.4 Traffic Projection limitation relevant to this TASK

The current Traffic Projection schema already has cycle-level fields including:

```text
metric_facts_present
wired_complete
lan_complete
wired_pair_count
lan_pair_count
```

and a `traffic_projection_ap_cycles` table.

However the projection writer stores AP rows only when:

```text
projected.metric_facts_present == true
```

For the incident cycle, production read-only verification shows:

```text
source_result = partial
source_complete = 0
error_count = 2
metric_facts_present = 0
integrity_ok = 0
wired_pair_count = 3
lan_pair_count = 3
wired_download_mbps = NULL
wired_upload_mbps = NULL

traffic_projection_ap_cycles rows for that cycle = 0
```

Therefore:

```text
"change only a formula over existing projection rows"
```

is insufficient for historical recovery of the already persisted partial AP rates.

The raw partial AP facts are nevertheless present in `observations.sqlite3`.

This leads to the bounded historical read-overlay decision in Part 12.

---

# 3. Permanent semantic invariants

These invariants are normative.

```text
missing != 0
unknown != offline
stale status != offline
source_unavailable != ok
partial subtotal != full Site total
Offline exclusion != fake numeric zero
```

Also:

```text
Current AP status authority = Current State
Historical AP traffic fact authority = Observation / existing Traffic Projection
UI = consumer of a ready safe model
UI does not decide completeness
```

And:

```text
one product metric
→ one semantic owner
```

DTI/NI/SPAN/NetFlow do not become alternate traffic owners.

---

# 4. Selected option and rejected alternatives

## 4.1 Option 1 — Owner zero-contribution / online denominator alone

**Verdict: insufficient by itself.**

It correctly handles a confirmed Offline AP, but does not safely cover:

```text
AP is Online but traffic endpoint failed
AP state is other/unknown
Current State status is stale
Current State status unavailable
inventory/Observation population mismatch
counter_reset
no_baseline after recovery
```

Treating all those cases as zero would create false totals.

## 4.2 Option 2 — measured subtotal always

**Verdict: safe but unnecessarily pessimistic.**

It would show useful traffic but would continue labelling the AP-4 incident as partial even when Current State independently proves:

```text
3 APs Online
1 AP Offline
all 3 Online APs measured
```

That throws away already available authoritative status evidence.

## 4.3 Option 3 — combination

**Verdict: SELECTED.**

The word `observed` is **not** sufficient proof of the installed AP population. R1 freezes this precedence explicitly.

Exact rule:

```text
1. if source cycle complete=1/result=success
      AND selected source fully covers the full Observation population R:
       complete_installed

2. else if authoritative aligned_fresh Current State exists
      AND Current State installed population I matches Observation R
      AND selected source fully covers I:
       complete_installed

3. else if authoritative aligned_fresh Current State proves:
      R = I
      I = O ∪ F
      every non-Offline AP is explicitly Online
      every Online AP is measured
      every Offline AP has selected-source source_unavailable in both directions
      no population conflict exists
      temporal rules pass:
       complete_online_population

4. else if at least one trustworthy selected-source direction is measured:
       partial_measured

5. else:
       unavailable
```

Normative P2-01 case:

```text
Observation result=partial
all Observation AP Wired/LAN rates valid
Current State unavailable
=> partial_measured
```

Reason: all **observed** rows being measured does not prove that the observed rows equal the installed population when the source cycle itself is partial.

No fourth architecture is required.

---


# 5. Authority for AP Online / Offline

## 5.1 Sole authority

The sole allowed AP Online/Offline authority for this TASK is:

```text
app/current_state/
→ CurrentStateReadService
→ complete persisted AP inventory snapshot
```

Traffic code MUST NOT infer Offline from:

```text
missing AP Observation
wired endpoint failure
LAN endpoint failure
ping
last traffic rate
historical Registry data
AP name
IP address
traffic_projection row absence
```

## 5.2 Status classes

Current State's existing classification remains:

```text
online
offline
other
unknown
```

Traffic semantics:

```text
online  = confirmed Online
offline = confirmed Offline
other   = not Offline
unknown = not Offline
```

For denominator exclusion:

```text
only status_classification == "offline"
is excludable
```

`other` and `unknown` remain required/uncertain population members.

## 5.3 New protected Current State read boundary

A bounded read-only method is permitted and required:

```text
CurrentStateReadService.read_ap_status_evidence_at(
    site_id,
    traffic_finished_at
) -> CurrentApStatusEvidenceV1
```

This is an internal service boundary only.

It MUST NOT become a browser endpoint.

It reads only existing `current_state.sqlite3` facts and MUST NOT write/migrate that DB.

### Selection rule

Select the latest AP cycle satisfying all:

```text
site_id = requested Site
kind = ap
result = success
complete = true
capture_finished_at <= traffic_finished_at
```

Then:

```text
status_age_seconds =
traffic_finished_at - capture_finished_at
```

The status evidence is `aligned_fresh` only when:

```text
0 <= status_age_seconds
   <= CurrentStateConfig.ap_fresh_max_age_seconds
```

Current accepted default is 90 seconds.

No new status freshness configuration is introduced.

If the latest complete prior AP snapshot is older than that threshold:

```text
status_evidence_state = stale
```

and it MUST NOT be used to exclude an AP as Offline.

If no complete prior snapshot exists:

```text
status_evidence_state = unavailable
```

## 5.4 No future-state backfill

A Current State snapshot captured after the traffic cycle is forbidden as status evidence for that earlier traffic cycle.

Thus:

```text
future Offline
does not rewrite earlier traffic as Offline
```

and:

```text
future Online
does not erase an earlier confirmed Offline interval
```

## 5.5 Identity join

The only join key is:

```text
site_id + canonical AP MAC
```

Forbidden:

```text
name join
IP-only join
cross-Site MAC merge
```

---

# 6. Population model

For one Current Traffic evaluation define:

```text
R = set of valid AP MACs physically represented by the selected AP-dynamic cycle

I = set of AP MACs in aligned Current State AP inventory,
    when aligned status evidence is available

O = APs in I classified online
F = APs in I classified offline
X = APs in I classified other or unknown
```

For selected source family `S`:

```text
D(S) = APs with valid Download rate
U(S) = APs with valid Upload rate
P(S) = D(S) ∩ U(S)
```

## 6.1 Population-match states

Closed enum:

```text
matched
observation_only
inventory_only
mismatch
status_unavailable
```

If aligned Current State exists:

```text
observation_only = R - I
inventory_only   = I - R
```

If either set is non-empty:

```text
population_match_state = mismatch
```

and the result may not be promoted to any complete status through Current State.

## 6.2 Installed count

When aligned Current State exists:

```text
installed_ap_count = |I|
```

When it does not exist:

```text
installed_ap_count = null
```

The Observation-cycle population remains separately visible:

```text
observation_ap_count = |R|
```

## 6.3 Expected confirmed-online population

Only for an aligned/matched Current State snapshot with no `other/unknown` AP:

```text
confirmed_online_population = O
offline_population = F
```

A complete-online result requires exactly that population.

---

# 7. Traffic-source selection — Wired versus LAN

## 7.1 Permanent no-mixing rule

One Site sample uses exactly one source family:

```text
wired
OR
lan
```

Never:

```text
AP-1 Wired
+ AP-2 LAN
+ AP-3 Wired
```

within one Site total.

`source_mixing_allowed` remains:

```text
false
```

This preserves the existing product invariant and prevents double counting.

## 7.2 Current-cycle deterministic selection

For each source family compute valid pair count over valid cycle AP identities:

```text
wired_pairs = |P(wired)|
lan_pairs   = |P(lan)|
```

Selection order:

```text
1. if wired fully covers R:
       wired / primary_full_observation_coverage

2. else if LAN fully covers R:
       lan / fallback_full_observation_coverage

3. else if aligned/matched status exists,
        X is empty,
        wired fully covers O:
       wired / primary_full_online_coverage

4. else if aligned/matched status exists,
        X is empty,
        LAN fully covers O:
       lan / fallback_full_online_coverage

5. else if lan_pairs > wired_pairs:
       lan / fallback_higher_measured_coverage

6. else:
       wired / primary_preferred_tie_or_higher
```

This rule is closed and leaves no source choice to Coder.

## 7.3 Valid rate shape

Allowed rate reasons remain the existing set:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

For an `ok` direction:

```text
value must be finite
value >= 0
timestamp must be valid
timestamp must lie inside the source cycle
```

For a non-`ok` direction:

```text
numeric value MUST be NULL
```

A real numeric `0.0` with reason `ok` is a real measurement.

`NULL` is not a zero.

---

# 8. Traffic-specific admission of a partial AP-dynamic cycle

The architecture does **not** redefine Observation's global `complete` meaning.

Instead it introduces a separate read-time concept:

```text
traffic_admissible_cycle
```

## 8.1 Allowed lifecycle

A cycle may be considered only when:

```text
kind = ap_dynamic
state = completed
result in {success, partial}
finished_at is present
items_stored > 0
```

`failed`, `shutdown`, `running`, and `abandoned` cycles are not numeric traffic evidence.

## 8.2 Structural integrity gate

A `partial` source cycle is traffic-admissible only if all of the following pass:

```text
source_rows_reported is not NULL
source_rows_reported == items_seen
items_seen == items_stored
items_skipped == 0
data_quality_warning_count == 0
actual AP row count == items_stored

every AP row:
    site_id == requested Site
    cycle_id == selected cycle
    canonical AP MAC
    no duplicate AP MAC
    valid rate reason/value shape
    valid traffic timestamps when reason == ok
```

`error_count > 0` is allowed for `result=partial`.

That count remains evidence that the global source cycle was partial; it is never converted to success.

This exact policy admits the real AP-4 incident while still failing closed on identity/corruption cases.

## 8.3 Global AP flags

For coverage-aware traffic, these global row flags are evidence, not an automatic rejection:

```text
partial
overview_ok
wired_uplink_ok
lan_traffic_ok
radios_ok
```

A failed `radios` or `overview` endpoint does not by itself invalidate a separately valid Wired/LAN traffic pair.

A failed selected traffic endpoint is represented through its non-`ok` rate reason and missing value.

## 8.4 Structural corruption behavior

If the newest completed `success|partial` candidate cycle fails structural integrity:

```text
Current partial-coverage result = unavailable
```

Do not silently skip it and show an older numeric result as if nothing happened.

A newer source attempt that is merely:

```text
running
failed
shutdown
abandoned
```

may leave a prior admissible snapshot visible under the existing freshness rules, with latest-attempt metadata exposed.

---

# 9. Current Traffic result contract

## 9.1 New explicit metric

Coverage-aware mode has its own semantic identity:

```text
metric_version =
network_traffic_current_partial_coverage.v1
```

The legacy metric remains unchanged when coverage-aware mode is not requested.

## 9.2 Measurement-state enum

Exact closed enum:

```text
complete_installed
complete_online_population
partial_measured
unavailable
```

### `complete_installed`

Allowed when either:

```text
A. status evidence = aligned_fresh
   AND aligned Current State installed population I matches R
   AND selected source pair-valid set P(S) == I

OR

B. the source cycle itself has complete=1 AND result=success
   under the legacy contract
   AND selected source fully covers its full Observation population R
```

No missing AP contribution exists.

Precedence is explicit:

```text
source result=partial
+ all observed AP rows fully measured
+ Current State unavailable/stale/not matched
=> NOT complete_installed
=> partial_measured
```

A partial source cycle may reach `complete_installed` only through branch A, because aligned Current State independently proves the installed population.

### `complete_online_population`

Allowed only when all are true:

```text
aligned Current State status evidence = aligned_fresh
population match = matched
X = empty
selected source pair-valid set P(S) = O
R = I
I = O ∪ F
O ∩ F = empty

for every AP in F:
    selected-source Download reason == source_unavailable
    selected-source Upload reason   == source_unavailable
    no numeric selected-source rate exists
```

Additionally:

```text
source skew among measured Online APs <= configured max AP skew
```

An Offline AP is **excluded**, not materialized as zero.

### `partial_measured`

Returned when:

```text
some valid selected-source numeric evidence exists
but neither complete condition is satisfied
```

Examples:

```text
Online AP missing rate
other/unknown AP missing rate
status evidence stale
status evidence unavailable
population mismatch
counter_reset
no_baseline
source_unavailable without confirmed Offline
selected-source partial direction
```

### `unavailable`

Returned when:

```text
no trustworthy numeric selected-source evidence exists
OR selected cycle structurally fails
OR current traffic freshness becomes unavailable
OR timestamps are not safely comparable
```

## 9.3 Current traffic formulas

For selected source `S`:

```text
download_mbps =
sum(valid Download values from included measured APs)
if at least one valid Download exists
else NULL

upload_mbps =
sum(valid Upload values from included measured APs)
if at least one valid Upload exists
else NULL

total_mbps =
download_mbps + upload_mbps
if both are non-NULL
else NULL
```

For aligned Current State, an Observation AP not present in `I` is not included in a complete total.

A population mismatch forces `partial_measured` or `unavailable`.

## 9.4 True zero rule

A displayed zero is allowed only when at least one actual rate value:

```text
reason = ok
value = 0.0
```

and the resulting arithmetic sum is zero.

Forbidden:

```text
no AP values -> 0 Mbps
source_unavailable -> 0 Mbps
Offline AP synthetic rate -> 0 Mbps
```

## 9.5 Offline contribution semantics

Normative wording:

```text
Confirmed Offline AP contribution is ABSENT/EXCLUDED
from the confirmed-online population sum.

It is not a stored or synthesized numeric zero fact.
```

This is the safe architectural interpretation of Owner's phrase “Offline AP = plus zero”.

---

# 10. Current freshness and temporal coherence

## 10.1 Existing Traffic Now freshness policy remains

Do not create a new clock policy.

Continue using existing configured Current Traffic values:

```text
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS
```

Current defaults at the pinned baseline:

```text
fresh max age = 90s
stale/unavailable boundary = 180s
max AP source skew = 60s
```

## 10.2 Traffic freshness states

Closed enum remains:

```text
fresh
stale
unavailable
```

Meaning:

```text
fresh:
numeric result is current enough for normal presentation

stale:
numeric result may still be shown,
but UI must explicitly label it STALE

unavailable:
all Site numeric values become NULL
```

## 10.3 AP measurement skew

Only mutually comparable AP measurements may be added.

For all AP timestamps contributing to one Site sum:

```text
max(timestamp) - min(timestamp)
<= WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS
```

If the skew exceeds the limit:

```text
Site aggregate = unavailable
coverage reason = temporal_skew
```

Per-AP facts may remain diagnostically visible, but they are not summed.

This is stricter than merely colouring a skewed sum as partial.

## 10.4 Offline AP and skew

An excluded confirmed Offline AP has no traffic timestamp and therefore does not enter the skew calculation.

Skew is calculated across the actually measured APs of the selected population.

---

# 11. Current coverage DTO

The new public safe result is conceptually frozen as:

```text
CoverageAwareCurrentSiteTrafficV1
```

Minimum exact fields:

```json
{
  "metric_version": "network_traffic_current_partial_coverage.v1",
  "site_id": "<site>",
  "evaluated_at_utc": "<UTC>",

  "measurement_state": "complete_installed | complete_online_population | partial_measured | unavailable",
  "population_scope": "installed | confirmed_online | measured_only | none",

  "snapshot": {
    "cycle_id": "<id|null>",
    "started_at": "<UTC|null>",
    "finished_at": "<UTC|null>",
    "source_result": "success|partial|null",
    "source_complete": "<boolean>",
    "latest_attempt_state": "none|running|completed|abandoned",
    "latest_attempt_result": "success|partial|failed|shutdown|null",
    "latest_attempt_at": "<UTC|null>",
    "using_previous_snapshot": false,
    "observed_at": "<UTC|null>",
    "newest_observed_at": "<UTC|null>",
    "age_seconds": 0.0,
    "source_skew_seconds": 0.0,
    "freshness_status": "fresh|stale|unavailable",
    "freshness_reason": "<closed reason>"
  },

  "traffic": {
    "download_mbps": 0.0,
    "upload_mbps": 0.0,
    "total_mbps": 0.0,
    "unit": "Mbps"
  },

  "source_selection": {
    "primary_source": "wired",
    "selected_source": "wired|lan|null",
    "selection_reason": "<closed reason>",
    "source_mixing_allowed": false,
    "wired_pair_valid_ap_count": 0,
    "lan_pair_valid_ap_count": 0
  },

  "coverage": {
    "observation_ap_count": 0,
    "installed_ap_count": null,
    "online_ap_count": null,
    "offline_ap_count": null,
    "other_ap_count": null,
    "unknown_ap_count": null,

    "measured_pair_ap_count": 0,
    "measured_download_ap_count": 0,
    "measured_upload_ap_count": 0,
    "required_measurement_ap_count": null,
    "missing_required_ap_count": null,
    "offline_excluded_ap_count": 0,

    "observation_only_ap_count": 0,
    "inventory_only_ap_count": 0,
    "population_match_state": "matched|observation_only|inventory_only|mismatch|status_unavailable",

    "coverage_reasons": []
  },

  "status_evidence": {
    "state": "aligned_fresh|stale|unavailable|population_mismatch",
    "cycle_id": "<id|null>",
    "capture_started_at": "<UTC|null>",
    "capture_finished_at": "<UTC|null>",
    "age_at_traffic_seconds": null,
    "source_scope_hash": "<hash|null>"
  }
}
```

For `unavailable`:

```text
traffic.download_mbps = NULL
traffic.upload_mbps   = NULL
traffic.total_mbps    = NULL
```

## 11.1 Closed coverage reasons

V1 allowed reasons:

```text
complete_installed_population
complete_confirmed_online_population
confirmed_offline_excluded
online_measurement_missing
other_status_measurement_missing
unknown_status_measurement_missing
status_evidence_stale
status_evidence_unavailable
population_mismatch
no_valid_rate
missing_direction
no_baseline
counter_reset
gap_too_large
source_unavailable
invalid_elapsed
temporal_skew
source_cycle_partial
source_cycle_failed
source_integrity_unavailable
status_measurement_conflict
clock_anomaly
age_exceeded
```

A response may contain more than one reason where they describe independent dimensions.

No free-form Coder-defined reason strings are allowed.

`status_measurement_conflict` is mandatory when an AP is classified `offline` but its selected-source missing/invalid rate evidence is not the exact Offline-exclusion shape required by §9.2, including `counter_reset`, `no_baseline`, `gap_too_large`, `invalid_elapsed`, a numeric rate, or mixed/incompatible directional evidence. It prevents such a row from being silently treated as an ignorable Offline contribution.

---

# 12. Current per-AP Traffic read model

Coverage-aware AP page metric:

```text
network_traffic_current_ap_partial_coverage.v1
```

Existing paging, Site authorization and bounded page sizes remain.

Each Observation AP item adds only safe derived coverage context:

```json
{
  "ap_mac": "AA:BB:CC:DD:EE:FF",
  "name": "AP-x",
  "selected_source": "wired",
  "download_mbps": 1.0,
  "upload_mbps": 0.1,
  "total_mbps": 1.1,
  "download_reason": "ok",
  "upload_reason": "ok",
  "rate_status": "valid|partial|unavailable",
  "coverage_role": "measured|offline_excluded|missing|required_unknown|population_conflict",
  "status_classification": "online|offline|other|unknown|null",
  "observed_at": "<UTC|null>"
}
```

The AP page MUST NOT invent an AP row that does not exist in the Observation cycle.

The Home AP roster remains sourced from Current State.

---

# 13. Historical Traffic architecture

## 13.1 Critical decision

Historical Traffic does **not** use Current State AP status to retroactively promote old partial cycles to complete-online totals.

Reason:

```text
Current State AP history retention is intentionally short
(default 48h)

Traffic History product range is up to 7d

Using transient status history would make the same historical
traffic point change semantic quality merely because status
evidence aged out.
```

Therefore historical quality is stable and measurement-based.

## 13.2 Existing strict historical metric remains canonical

The following accepted strict contracts remain unchanged:

```text
network_traffic_history.v1
network_traffic_period_statistics.v1
network_traffic_peak_load.v1
network_traffic_by_ap.v1
network_traffic_ap_share.v1
```

Their formulas are not silently changed.

Complete successful projected traffic remains the canonical strict series.

## 13.3 New read-only partial overlay

Coverage-aware history adds:

```text
HistoricalTrafficPartialCoverageOverlayV1
metric_version =
network_traffic_partial_coverage_overlay.v1
```

It reads only already persisted raw partial AP-dynamic Observation cycles omitted from the current projection.

Flow:

```text
Traffic Projection strict history
        +
bounded read-only partial Observation evidence
        ↓
Historical Traffic safe composition
        ↓
Admin API
        ↓
Traffic graph / quality UI
```

No write occurs.

## 13.4 Exact read/service ownership

The implementation MUST use one semantic path; no test-only or Admin-only second engine is permitted.

Frozen internal boundaries:

```text
Current Traffic:
CurrentTrafficReadService.get_current_site_traffic_partial_coverage(...)
    -> AnalyticsSourceGateway.read_current_partial_traffic_evidence(...)
    -> CurrentStateReadService.read_ap_status_evidence_at(...)
    -> CoverageAwareCurrentSiteTrafficV1

Historical Traffic:
HistoricalTrafficReadService.get_site_history_partial_coverage(...)
    -> existing strict HistoricalTrafficReadService.get_site_history(...)
    -> PartialTrafficEvidenceReadBoundaryV1.read_partial_ap_traffic_evidence(...)
    -> HistoricalTrafficPartialCoverageOverlayV1
    -> one coverage-aware safe composition
```

`PartialTrafficEvidenceReadBoundaryV1` is owned by the Analytics/Traffic read layer.

When the active historical gateway is projection-backed, the existing `TrafficProjectionReadService` MUST implement that boundary by reading the configured Observation DB **read-only**; it MUST NOT ask the projection writer to materialize partial rows.

Required source-open semantics:

```text
SQLite mode = read-only
PRAGMA query_only = ON
existing busy/deadline handling applies
Site and range are mandatory
```

`TrafficProjectionReadService` already receives the Observation DB path for read composition; this TASK may reuse that dependency. It may not introduce a second Observation path alias.

Admin routes and browser code never open either database directly.

The pure validation/aggregation helpers used by Current and Historical partial evidence must be shared production code where their semantics are identical. Tests exercise those same helpers; there is no divergent test-only approximation.

## 13.5 Current read method ownership

Legacy:

```text
CurrentTrafficReadService.get_current_site_traffic(...)
```

remains the strict semantic owner for requests without `coverage_mode`.

Coverage-aware mode dispatches to the separate production method:

```text
CurrentTrafficReadService.get_current_site_traffic_partial_coverage(...)
```

The new method may reuse strict helpers, but it MUST NOT relax the legacy method's accepted-cycle predicates.

Likewise, the historical strict method remains unchanged and the new coverage-aware method composes it with the partial overlay.

## 13.6 Why an overlay rather than changing Traffic Projection storage

The current projection deliberately does not materialize AP rows when a cycle fails the current integrity contract.

Changing the projection writer/schema would:

```text
change durable derived semantics
require migration/versioning
require backfill/rebuild decisions
increase rollout/rollback risk
```

None of that is necessary for this incident.

A bounded read-only overlay can recover the already persisted AP-1/2/3 facts without changing the source or projection database.

This is the minimum safe architecture.

---

# 14. Historical partial-cycle admission

Only cycles satisfying:

```text
site_id = requested Site
kind = ap_dynamic
state = completed
result = partial
complete = 0
items_stored > 0
sample timestamp = finished_at
finished_at in requested range [from_utc, to_utc)
```

are candidates for the new overlay.

They must pass the same structural gate from §8.2.

A cycle failing structural identity/rate integrity produces:

```text
overlay integrity rejection
no numeric overlay sample
```

It never becomes zero.

## 14.1 Partial source selection

Historical overlay source selection is performed **once per product bucket**, not AP-by-AP and not by merging Wired and LAN values.

For all structurally admitted raw partial cycles whose `finished_at` falls inside one product bucket, compute per source family:

```text
full_cycle_count =
count(cycles where every Observation AP has a valid pair)

pair_opportunities =
sum(valid pair AP counts across admitted cycles)

direction_opportunities =
sum(valid Download AP counts + valid Upload AP counts across admitted cycles)
```

Let `N = admitted partial cycle count in the bucket`. Select exactly one bucket source:

```text
1. if wired_full_cycle_count == N:
       wired / primary_full_partial_bucket_coverage

2. else if lan_full_cycle_count == N:
       lan / fallback_full_partial_bucket_coverage

3. else if lan_full_cycle_count > wired_full_cycle_count:
       lan / fallback_more_full_partial_cycles

4. else if wired_full_cycle_count > lan_full_cycle_count:
       wired / primary_more_full_partial_cycles

5. else if lan_pair_opportunities > wired_pair_opportunities:
       lan / fallback_higher_partial_pair_coverage

6. else if wired_pair_opportunities > lan_pair_opportunities:
       wired / primary_higher_partial_pair_coverage

7. else if lan_direction_opportunities > wired_direction_opportunities:
       lan / fallback_higher_partial_direction_coverage

8. else:
       wired / primary_preferred_partial_tie_or_higher
```

The directional-opportunity tie-break exists only to make one-direction fixtures deterministic when pair coverage is tied. It does not permit source mixing.

All overlay subtotals in the bucket are then evaluated from that one selected source family.

Therefore:

```text
no per-AP Wired/LAN mixing
no per-cycle source switching inside one product bucket
no mixed-source bucket mean
Wired wins the final tie
```

There is no Offline promotion in Historical mode.

Thus for the AP-4 outage cycle:

```text
observed population = 4
selected-source pair-valid AP count = 3
historical cycle evidence = measured partial evidence
```

even though Current Traffic may contemporaneously classify the live result as complete for three confirmed Online APs. That difference is intentional.

---

# 15. Historical overlay bucket DTO and numeric semantics

## 15.1 Per-cycle selected-source directional sets

For each admitted partial cycle `c` after the bucket source `S` is frozen, define:

```text
R_c = all structurally valid Observation AP identities in cycle c

D_c = APs in R_c with selected-source Download reason=ok,
      finite non-negative Download value, and valid selected-source timestamp

U_c = APs in R_c with selected-source Upload reason=ok,
      finite non-negative Upload value, and valid selected-source timestamp

P_c = D_c ∩ U_c
```

Directional evidence is admitted independently. A coherent Total sample is stricter.

```text
download_subtotal_c = sum(Download over D_c) if D_c non-empty else NULL

upload_subtotal_c   = sum(Upload over U_c) if U_c non-empty else NULL

total_subtotal_c = download_subtotal_c + upload_subtotal_c
only when D_c = U_c = P_c and P_c is non-empty; otherwise NULL
```

This means:

```text
download-only evidence is allowed as Download evidence
upload-only evidence is allowed as Upload evidence
Total is never synthesized from different AP populations
Total is never synthesized from different cycle denominators
no valid direction => NULL, never 0 Mbps
```

## 15.2 Bucket means and exact denominators

For a bucket containing admitted cycles `C`:

```text
C_D = cycles where download_subtotal_c is non-NULL
C_U = cycles where upload_subtotal_c is non-NULL
C_T = cycles where total_subtotal_c is non-NULL

download_sample_count = |C_D|
upload_sample_count   = |C_U|
measured_sample_count = |C_T|
```

`measured_sample_count` is therefore the count of **coherent Total samples**, not merely cycles with any one-direction number.

Bucket values:

```text
download_mbps = arithmetic mean(download_subtotal_c for c in C_D)
                if C_D non-empty else NULL

upload_mbps   = arithmetic mean(upload_subtotal_c for c in C_U)
                if C_U non-empty else NULL

total_mbps    = arithmetic mean(total_subtotal_c for c in C_T)
                if C_T non-empty else NULL
```

Normative rule:

```text
bucket total_mbps MUST NOT be calculated as
download_mbps + upload_mbps
when C_D, C_U and C_T are not the same contributing cycle set.
```

The serializer therefore does not apply the instantaneous `download + upload = total` invariant to these independently-denominated historical bucket means.

## 15.3 Opportunity counts and coverage ratio

Across all admitted cycles in the bucket:

```text
observed_ap_opportunities = Σ |R_c|
measured_download_ap_opportunities = Σ |D_c|
measured_upload_ap_opportunities   = Σ |U_c|
measured_pair_ap_opportunities     = Σ |P_c|
```

Exact `coverage_ratio` semantics:

```text
coverage_ratio =
  measured_pair_ap_opportunities / observed_ap_opportunities
  when observed_ap_opportunities > 0
else NULL
```

It is specifically **pair coverage**, not a traffic percentage and not an average of per-cycle ratios. If the denominator is positive and no pair is valid, `coverage_ratio=0.0` is a legitimate coverage ratio; it does not mean `0 Mbps`.

`min_observed_ap_count` / `max_observed_ap_count` are the min/max `|R_c|`.
`min_measured_ap_count` / `max_measured_ap_count` are the min/max `|P_c|`.

## 15.4 Closed bucket-state enum

Exact closed enum:

```text
partial_measured
partial_directional
partial_unmeasured
```

Precedence:

```text
if measured_sample_count > 0:
    status = partial_measured
elif download_sample_count > 0 or upload_sample_count > 0:
    status = partial_directional
else:
    status = partial_unmeasured
```

`partial_unmeasured` is an evidence-only bucket. It is returned because a structurally admissible partial source cycle existed, but all three numeric fields are `NULL`. It MUST NOT draw a zero point.

## 15.5 Exact bucket DTO

```json
{
  "bucket_start_utc": "<UTC>",
  "bucket_end_utc": "<UTC>",
  "status": "partial_measured|partial_directional|partial_unmeasured",
  "download_mbps": "<number|null>",
  "upload_mbps": "<number|null>",
  "total_mbps": "<number|null>",
  "unit": "Mbps",
  "selected_source": "wired|lan",
  "selection_reason": "<closed reason from §14.1>",
  "partial_cycle_count": 1,
  "download_sample_count": 1,
  "upload_sample_count": 1,
  "measured_sample_count": 1,
  "observed_ap_opportunities": 4,
  "measured_download_ap_opportunities": 3,
  "measured_upload_ap_opportunities": 3,
  "measured_pair_ap_opportunities": 3,
  "min_observed_ap_count": 4,
  "max_observed_ap_count": 4,
  "min_measured_ap_count": 3,
  "max_measured_ap_count": 3,
  "coverage_ratio": 0.75,
  "reasons": ["source_cycle_partial", "source_unavailable"]
}
```

Bucket `reasons` is a de-duplicated ordered list drawn only from this closed set:

```text
source_cycle_partial
source_unavailable
missing_direction
no_valid_rate
no_baseline
counter_reset
gap_too_large
invalid_elapsed
```

Ordering is exactly the order above after filtering to reasons present in the bucket. No free-form strings.

These values remain **MEASURED PARTIAL SUBTOTALS**, not strict Site totals. The overlay is never mathematically merged into the existing strict bucket mean.

---


# 16. Historical statistics, Peak, comparisons and AP share

## 16.1 Fundamental rule

Do not average:

```text
strict complete 4-AP Site totals
+
partial measured 3-of-4 subtotals
```

and then call the result a complete Site average.

The architecture avoids that completely.

## 16.2 Period Average

Existing `network_traffic_period_statistics.v1` remains calculated from the existing strict accepted intervals only.

When the requested period contains any admitted partial overlay:

```text
period_coverage_state = partial
statistics_scope = complete_coverage_intervals_only
```

The numeric strict average may remain visible, but UI text MUST say:

```text
Average · complete-coverage intervals only
```

It may not be labelled as the complete period average.

If there are no strict accepted intervals:

```text
average values = NULL
status = insufficient_data
```

No average is calculated from partial subtotals.

## 16.3 Peak

Existing strict Peak calculation remains unchanged.

If partial overlay exists anywhere in the requested period, the strict Peak is not a proven full-period Peak.

UI label becomes:

```text
Max observed with complete AP coverage
```

not:

```text
Peak for the period
```

If no complete strict samples exist:

```text
strict Peak = NULL
```

The overlay may separately expose:

```text
max_partial_measured_total_mbps
```

labelled:

```text
Max measured during partial coverage
```

It is not compared numerically with strict Peak as if both shared the same denominator.

## 16.4 Period comparisons

Period-over-period percentage/comparison is allowed only if both compared periods satisfy all:

```text
strict statistics status = ok
no admitted partial overlay in either period
no partial-overlay capacity/unavailability state
no material strict coverage gap that already makes statistics partial
```

Otherwise the public comparison numeric value/delta/percentage fields are `NULL`. Exact coverage-aware `comparison_state` values are:

```text
unavailable_partial_coverage
unavailable_overlay_unavailable
unavailable_overlay_capacity_limited
unavailable_source_coverage_insufficient
```

Mapping:

```text
partial_coverage.status=ok and has_partial_measurements=true
  => unavailable_partial_coverage

partial_coverage.status=unavailable
  => unavailable_overlay_unavailable

partial_coverage.status=capacity_limited
  => unavailable_overlay_capacity_limited

partial_coverage.status=source_coverage_insufficient
  => unavailable_source_coverage_insufficient
```

UI copy is frozen in §25.

## 16.5 AP shares

A Site denominator built from missing AP traffic can overstate remaining AP shares.

Therefore when the requested range contains any admitted partial overlay:

```text
full-period AP share = unavailable
```

In `coverage_mode=partial_v1`, the public serializer MUST NOT expose strict share fractions as if they covered the whole requested period. If AP share was requested and coverage-aware mode does not allow a full-period share:

```text
ap_traffic_share.status = insufficient_data
all public download/upload/total share fractions = NULL
```

Exact `reason` mapping:

```text
partial_coverage.status=ok and has_partial_measurements=true
  => partial_ap_coverage
partial_coverage.status=unavailable
  => partial_coverage_unknown
partial_coverage.status=capacity_limited
  => partial_coverage_capacity_limited
partial_coverage.status=source_coverage_insufficient
  => source_coverage_insufficient
```

The internal strict result may still exist for diagnostics, but it is not the public full-period share.

Per-AP historical rate series may remain visible with their own evidence states.

## 16.6 No new transferred-byte total

This TASK does not convert Mbps samples into historical byte totals.

No new “period bytes transferred” metric is introduced.

---

# 17. Historical coverage extension envelope

Only in `coverage_mode=partial_v1`, the historical response adds the following exact envelope.

## 17.1 Exact wire types

```json
{
  "partial_coverage": {
    "metric_version": "network_traffic_partial_coverage_overlay.v1",
    "status": "ok|unavailable|capacity_limited|source_coverage_insufficient",
    "reason": "partial_measurements_present|no_partial_measurements|overlay_source_unavailable|overlay_capacity_limited|raw_observation_range_incomplete",
    "source_kind": "observation_ap_dynamic",
    "range_from_utc": "<UTC>",
    "range_to_utc": "<UTC>",
    "partial_cycle_count_examined": "<integer|null>",
    "partial_cycle_count_admitted": "<integer|null>",
    "partial_cycle_count_integrity_rejected": "<integer|null>",
    "partial_ap_rows_examined": "<integer|null>",
    "bucket_count_returned": 0,
    "buckets": [],
    "has_partial_measurements": "<boolean|null>",
    "source_coverage_insufficient": "<boolean|null>",
    "statistics_scope": "complete_coverage_intervals_only",
    "comparison_allowed": false,
    "ap_share_allowed": false
  }
}
```

`boolean|null` is the only tri-state representation. No string such as `unknown` is permitted for either tri-state field.

Semantics:

```text
true  = positively proven
false = positively disproven after complete bounded evaluation
null  = unknown / not asserted
```

## 17.2 Exact status matrix

### A. `status=ok`, partial evidence exists

```json
{
  "status": "ok",
  "reason": "partial_measurements_present",
  "has_partial_measurements": true,
  "source_coverage_insufficient": false,
  "buckets": ["<one or more partial bucket DTOs>"],
  "bucket_count_returned": ">0",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

All count fields are non-negative integers and describe the complete bounded evaluation.

### B. `status=ok`, no partial cycles in the fully covered range

```json
{
  "status": "ok",
  "reason": "no_partial_measurements",
  "has_partial_measurements": false,
  "source_coverage_insufficient": false,
  "buckets": [],
  "bucket_count_returned": 0
}
```

`comparison_allowed` and `ap_share_allowed` are then exact booleans copied from the existing strict product eligibility for the same requested period. They are never `null`.

### C. `status=unavailable`

```json
{
  "status": "unavailable",
  "reason": "overlay_source_unavailable",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

### D. `status=capacity_limited`

```json
{
  "status": "capacity_limited",
  "reason": "overlay_capacity_limited",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

No partial/truncated count is exposed as though it described the full request.

### E. `status=source_coverage_insufficient`

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_incomplete",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": true,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

Even if part of the requested range is readable, no numeric partial bucket from that incomplete range is exposed. Absence of returned buckets is not evidence of absence of partial cycles.

## 17.3 Numeric buckets in failure states

Exact rule:

```text
status = ok                           => buckets MAY contain exact §15 DTOs
status = unavailable                  => buckets MUST be []
status = capacity_limited             => buckets MUST be []
status = source_coverage_insufficient => buckets MUST be []
```

Strict projected historical data may remain independently available in all three non-`ok` overlay states if its own strict source remains sound.

---


# 18. Historical read bounds and performance

## 18.1 Product ranges stay unchanged

Only existing:

```text
24h
7d
```

ranges are supported.

Existing maximum history bucket count remains:

```text
720
```

## 18.2 Partial overlay hard caps

Coverage-aware partial evidence is bounded by:

```text
MAX_PARTIAL_CYCLES_PER_REQUEST = 10_080
MAX_PARTIAL_AP_ROWS_PER_REQUEST = 150_000
PARTIAL_AP_ROW_BATCH_SIZE = 2_000
PARTIAL_OVERLAY_LOCAL_TIME_BUDGET_SECONDS = 5
```

The implementation MUST use bounded indexed Site/time queries.

No OFFSET pagination scan.

No unbounded in-memory list of all AP rows.

Rows are streamed/processed in bounded batches into at most the existing history bucket count.

## 18.3 Capacity behavior

If any hard cap or the local 5-second overlay budget is exceeded, return exactly the §17.2-D envelope:

```text
partial_coverage.status = capacity_limited
partial_coverage.reason = overlay_capacity_limited
has_partial_measurements = NULL
source_coverage_insufficient = NULL
buckets = []
bucket_count_returned = 0
comparison_allowed = false
ap_share_allowed = false
```

Strict history remains independently usable. Partial data MUST NOT be silently truncated, and partial counts accumulated before the cap are not exposed as full-range counts.

## 18.4 Query concurrency

Use the existing Admin query concurrency and request deadline controls.

No new worker thread pool, queue, retry loop or background materializer is introduced.

## 18.5 Response size

The new historical overlay is sparse and may return at most one overlay entry per product bucket.

Existing Admin maximum response-size enforcement remains authoritative.

If safe response size would be exceeded:

```text
existing response-too-large behavior applies
```

Do not silently drop coverage metadata.

---

# 19. Raw Observation retention

Current Observation contract defaults dynamic retention to 180 days, which is greater than the 7-day Traffic product range.

This TASK does not change retention.

Coverage-aware historical reads must nevertheless report source range coverage.

If configured/available raw Observation coverage does not include the entire requested range `[from_utc,to_utc)`, return exactly the §17.2-E envelope:

```text
partial_coverage.status = source_coverage_insufficient
partial_coverage.reason = raw_observation_range_incomplete
has_partial_measurements = NULL
source_coverage_insufficient = true
buckets = []
bucket_count_returned = 0
comparison_allowed = false
ap_share_allowed = false
```

No numeric partial bucket from the covered sub-range is returned. The strict projection may still be returned under its own contract. The UI must not infer that missing overlay means no partial cycles.

---

# 20. Admin API compatibility

## 20.1 Backward compatibility principle

No existing client receives new partial semantics merely because this code is deployed.

Existing requests without the new parameter retain their current strict behavior.

## 20.2 New query mode

Exact opt-in query parameter:

```text
coverage_mode=partial_v1
```

Absence of `coverage_mode` means:

```text
legacy strict behavior
```

Any other value:

```text
400 invalid_request
```

When the feature is disabled and `partial_v1` is requested:

```text
404 not_found
```

following the current Admin feature-gate pattern.

## 20.3 Current Home summary endpoint

Existing route:

```http
GET /admin/api/v1/sites/<site_id>/current-traffic/summary
```

Coverage-aware request:

```http
GET /admin/api/v1/sites/<site_id>/current-traffic/summary?coverage_mode=partial_v1
```

Authorization remains:

```text
admin.read.overview
```

## 20.4 Current Traffic-page endpoint

Existing route:

```http
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Coverage-aware request:

```http
GET /admin/api/v1/sites/<site_id>/traffic/current?coverage_mode=partial_v1
```

Authorization remains:

```text
admin.read.context
```

## 20.5 Current per-AP endpoint

Existing route:

```http
GET /admin/api/v1/sites/<site_id>/current-traffic/aps
```

Coverage-aware request adds the same mode:

```text
cycle_id=<selected>
limit=<bounded>
cursor=<optional>
coverage_mode=partial_v1
```

Existing authorization remains unchanged.

## 20.6 Historical endpoint

Existing route:

```http
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Allowed query set is extended with:

```text
coverage_mode
```

Example:

```http
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h&coverage_mode=partial_v1
```

Existing `include` / `products` semantics remain unchanged.

The legacy request without `coverage_mode` remains byte/semantic compatible with current v1 contracts apart from non-semantic runtime metadata such as query duration.

## 20.7 No browser source fan-out

The browser still calls only Admin API.

Forbidden:

```text
browser → observations.sqlite3
browser → current_state.sqlite3
browser → Omada
browser → traffic_projection.sqlite3
```

---

# 21. Feature gate

Introduce one repository-default-off gate:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

Configuration path:

```text
process environment
→ app/config.py
→ app/settings.py:get_settings()
→ AdminWebConfig
```

No second hidden flag is allowed.

When disabled:

```text
legacy Current Traffic = unchanged
legacy Historical Traffic = unchanged
Home/Traffic JS does not request partial_v1
```

When enabled:

```text
Home and Traffic product requests use coverage_mode=partial_v1
```

The strict mode remains available for compatibility and diagnostics.

---

# 22. Home presentation contract

CaptivPortal Admin UI is currently English. The architecture therefore freezes English production copy while preserving the exact semantic equivalents required by the Tech Lead request.

## 22.1 Complete installed population

Example:

```text
Total traffic: 23 Mbps
Complete AP coverage · 4 of 4 APs measured
```

State:

```text
ready
```

## 22.2 Complete confirmed-online population

Example:

```text
Total traffic: 23 Mbps
3 Online / 4 total · 1 Offline excluded
```

Additional evidence text:

```text
All confirmed Online APs are measured.
```

Tooltip/help:

```text
Scope: confirmed Online APs.
Offline APs are excluded from the measurement population;
no zero traffic value is synthesized for them.
```

State:

```text
ready
```

This is the production equivalent of:

```text
Общий трафик: 23 Мбит/с
3 Online / 4 всего
```

## 22.3 Partial measured subtotal

Example:

```text
Measured traffic: 23 Mbps
Partial data · 3 of 4 APs measured
```

Reason detail examples:

```text
1 Online AP has no valid traffic measurement.
AP status is unknown.
AP status evidence is stale.
AP population does not match the traffic snapshot.
```

State:

```text
warning
```

This is the production equivalent of:

```text
Измеренный трафик: 23 Мбит/с
Частичные данные · 3 из 4 AP
```

## 22.4 Unavailable

Exact primary text:

```text
No reliable traffic data
```

Numeric cards:

```text
—
```

Never:

```text
0 Mbps
```

unless a real zero was measured.

## 22.5 Real zero

When valid measured rates sum to zero:

```text
Total traffic: 0 Mbps
```

or, for partial coverage:

```text
Measured traffic: 0 Mbps
Partial data · N of M APs measured
```

## 22.6 Stale

When numeric traffic is still inside the existing stale window:

```text
Traffic is stale
```

The existing age/observed timestamp remains visible.

A stale numeric value is not promoted to fresh merely because status evidence is available.

## 22.7 AP roster details

Exact semantic presentation:

```text
Online + measured
→ traffic value

Offline + excluded
→ "Offline · excluded from online traffic scope"
   traffic value = —

Online + missing
→ "Online · traffic measurement unavailable"

other / unknown + missing
→ "Status unknown · traffic measurement unavailable"

valid measured zero
→ 0 Mbps
```

---

# 23. Traffic page current presentation

The Traffic page uses the same coverage-aware Current Traffic DTO and the same four measurement states as Home.

No independent JS completeness logic is allowed.

Traffic-page current copy must match Home semantics:

```text
Total traffic
Measured traffic
Partial data
No reliable traffic data
Online / total / Offline excluded
STALE
```

A difference in visual layout is allowed; a difference in semantic wording is not.

---

# 24. Historical Traffic graph presentation

## 24.1 Visual evidence classes

The graph recognizes these evidence classes:

```text
Complete AP coverage
Measured partial coverage
Directional partial coverage
Partial coverage — no reliable traffic measurement
No reliable data
```

Normative meaning:

```text
complete series
= existing strict historical metric

partial_measured
= §15 bucket with at least one coherent Total sample

partial_directional
= §15 bucket with one or both directional means but no coherent Total sample

partial_unmeasured
= evidence-only partial bucket with all numeric fields NULL
```

Strict and partial evidence are never merged into one complete line.

## 24.2 Exact legend/tooltip rules

Legend labels:

```text
Complete AP coverage
Measured partial coverage
No reliable data
```

A `partial_directional` point/marker uses the `Measured partial coverage` legend family, but its tooltip MUST name the available direction explicitly:

```text
Measured download: <value> Mbps
Upload unavailable
Partial data
```

or:

```text
Download unavailable
Measured upload: <value> Mbps
Partial data
```

If both directional means exist but `total_mbps=NULL` because their contributing cycle/AP populations are incoherent:

```text
Measured download: <value> Mbps
Measured upload: <value> Mbps
Combined total unavailable
Partial data
```

For `partial_measured` with coherent Total:

```text
Measured traffic: <total_mbps> Mbps
Partial data · pair coverage <measured_pair_ap_opportunities>/<observed_ap_opportunities> AP opportunities
```

If min/max pair counts vary inside one bucket:

```text
Measured pair APs per sample: <min>–<max>
Observed APs per sample: <min>–<max>
```

## 24.3 Evidence-only partial bucket

For `partial_unmeasured`:

```text
Partial coverage — no reliable traffic measurement
```

No numeric point or zero line is drawn. The UI may render a non-numeric annotation/marker showing that a partial source cycle existed.

## 24.4 Complete + partial in the same bucket

Both pieces of evidence may exist for one time bucket. The API preserves both and the UI must not collapse them into one full-coverage mean. Exact tooltip text:

```text
This interval contains both complete and partial AP measurements.
```

## 24.5 Gap

No numeric strict or partial evidence and no `partial_unmeasured` evidence:

```text
No reliable data
```

The chart leaves a gap and MUST NOT draw a zero line.

---

# 25. Historical period UI

The following quality copy is normative for `coverage_mode=partial_v1`. Strict Average/Peak numeric fields remain governed by the unchanged strict metric. A non-`ok` overlay never erases a sound strict number, but it changes what that number may claim about the requested period.

## 25.1 `status=ok`, `has_partial_measurements=true`

```text
quality banner =
Partial AP coverage exists in this period.

Average label =
Average · complete-coverage intervals only

Peak label =
Max observed with complete AP coverage

Comparison =
Comparison unavailable because AP coverage is partial.

AP share =
AP share unavailable for the full period because AP coverage is partial.
```

`comparison_allowed=false`; public comparison numeric fields are `NULL`.
`ap_share_allowed=false`; public AP share fractions are `NULL`.

## 25.2 `status=ok`, `has_partial_measurements=false`

No partial-coverage warning is shown. Existing strict Average/Peak labels and eligibility remain unchanged. `comparison_allowed` and `ap_share_allowed` equal the deterministic existing strict eligibility.

## 25.3 `status=unavailable`

Exact visible copy:

```text
quality banner =
Partial-coverage evidence is unavailable for this period.

Average label when a strict numeric Average exists =
Average · complete-coverage intervals only · partial coverage not verified

Peak label when a strict numeric Peak exists =
Max observed with complete AP coverage · partial coverage not verified

Comparison =
Comparison unavailable because partial-coverage status is unknown.

AP share =
AP share unavailable because partial-coverage status is unknown.
```

If the strict Average/Peak itself is unavailable under its unchanged strict contract, retain the existing unavailable placeholder rather than fabricating a number.

## 25.4 `status=capacity_limited`

Exact visible copy:

```text
quality banner =
Partial-coverage evidence exceeded the bounded query limit for this period.

Average label when a strict numeric Average exists =
Average · complete-coverage intervals only · partial coverage not fully evaluated

Peak label when a strict numeric Peak exists =
Max observed with complete AP coverage · partial coverage not fully evaluated

Comparison =
Comparison unavailable because partial coverage could not be fully evaluated.

AP share =
AP share unavailable because partial coverage could not be fully evaluated.
```

## 25.5 `status=source_coverage_insufficient`

Exact visible copy:

```text
quality banner =
Partial-coverage evidence is unavailable for part of this period because raw Observation coverage is incomplete.

Average label when a strict numeric Average exists =
Average · complete-coverage intervals only · partial coverage not fully covered

Peak label when a strict numeric Peak exists =
Max observed with complete AP coverage · partial coverage not fully covered

Comparison =
Comparison unavailable because partial-coverage source coverage is incomplete.

AP share =
AP share unavailable because partial-coverage source coverage is incomplete.
```

For §§25.3–25.5:

```text
comparison_allowed = false
ap_share_allowed = false
comparison numeric fields = NULL
AP-share download/upload/total fractions = NULL
```

A strict Average/Peak displayed in these states is explicitly a **complete-coverage-only statistic**, never a proven whole-period statistic.

---


# 26. Recovery semantics

## 26.1 Offline → Online

When an AP returns Online, it immediately re-enters the required current measurement population.

Its first rate may validly be:

```text
no_baseline
counter_reset
```

During that condition:

```text
measurement_state = partial_measured
```

if other AP traffic is valid.

Do not reuse yesterday's/stale AP rate.

Do not keep the AP excluded merely because it was Offline one cycle ago.

## 26.2 Automatic full recovery

As soon as the returned AP supplies a valid selected-source pair in a comparable cycle:

```text
complete_installed
```

is restored automatically.

No manual data repair, DB update or cache purge is part of the design.

---

# 27. Site composition changes

## 27.1 AP added

If Current State and AP-dynamic population do not yet agree:

```text
population_match_state = mismatch
```

The result cannot be complete-online via status exclusion.

Measured traffic may be shown only as partial if its identity and rates are safe.

## 27.2 AP removed or moved to another Site

No prior Site status or Observation row may be joined across Site boundaries.

A row with the wrong Site is a structural integrity failure.

## 27.3 Same MAC in different Sites

All identity is:

```text
site_id + AP MAC
```

No cross-Site merge.

---

# 28. Failure isolation

A failure of coverage-aware AP Traffic MUST NOT break:

```text
Portal
Auth
CAPPORT
Current State collection
Observation collection
Traffic Projection writer
Guest/Session Traffic
NI
Fingerprint
```

## 28.1 Current partial-mode failure

If coverage-aware Current Traffic fails:

```text
that request → source_unavailable / safe unavailable result
```

Legacy strict mode remains logically independent.

## 28.2 Historical overlay failure

If the raw partial overlay fails:

```text
strict projected historical result may still be returned
partial_coverage = exact §17.2-C unavailable envelope
comparison_allowed = false
ap_share_allowed = false
partial buckets = []
```

No partial numeric data is fabricated. Strict Average/Peak may remain numerically accessible only under their unchanged strict contract and must use the exact §25.3 qualified labels.

## 28.3 Current State status-read failure

A Current State read failure disables only Offline promotion.

It does not erase a fully complete legacy AP traffic cycle.

A partial AP-dynamic cycle then remains:

```text
partial_measured
```

rather than becoming complete-online.

---

# 29. Persistence and retention

## 29.1 No new persistence

This TASK creates no durable traffic facts.

All coverage-aware values are read-time derived.

## 29.2 No source rewrite

Forbidden:

```text
UPDATE observations
UPDATE traffic_projection
UPDATE current_state
backfill fake AP rates
materialize Offline zeros
```

## 29.3 Historical reproducibility

A coverage-aware Historical response is reproducible from:

```text
strict projected history version
+
immutable completed partial Observation cycles still under source retention
+
frozen partial overlay algorithm version
```

If raw partial facts have legitimately aged out of retention:

```text
partial source coverage becomes insufficient
```

The system does not invent their prior content.

---

# 30. Allowed implementation surface

The Tech Lead implementation TASK may authorize bounded changes in:

```text
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/historical_traffic.py

app/traffic_projection/read_service.py
  # read-only support only; no writer/schema semantics

app/current_state/read_service.py
app/current_state/models.py
  # protected read DTO only; no collector/schema change

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

relevant tests
```

Minimal file consolidation is allowed by Tech Lead only when semantic ownership remains exactly as frozen here.

---

# 31. Protected components

This TASK MUST NOT change the semantic/write contracts of:

```text
app/observations/ap_worker.py
Observation repository/schema/writer
OmadaProvider and Omada request behavior

traffic_projection repository/schema/source projector/writer/service

Current State collector
Current State repository/schema
Current State status classification rules

Portal/Auth/CAPPORT
Registry
Visit Lifecycle
Fingerprint
Suricata/Fingerprint Sensor
NI-01/02B/03/04
Guest Traffic
Session Traffic
Public Traffic
```

If implementation evidence proves one of these protected boundaries must change, Coder must stop and return to Tech Lead/Architect.

---

# 32. Configuration compatibility

One new flag only:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

No DB migration.

No source retention change.

No polling cadence change.

No Omada API call-rate change.

No new systemd service.

No new port.

No new filesystem path.

---

# 33. Rollout

Implementation merge is not activation.

Required rollout sequence:

```text
1. implement + test with feature default false
2. Tech Lead review
3. Owner authorizes merge
4. deploy code with feature still false
5. Owner separately authorizes any production restart
6. restart only captive-portal.service if required by deployment
7. prove legacy strict Home/Traffic behavior unchanged while flag=false
8. prove Portal/Auth/CAPPORT baseline healthy
9. Owner authorizes activation
10. set WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=true
11. restart captive-portal.service under Owner authorization
12. verify Current partial_v1 on live safe data
13. verify Historical partial overlay
14. verify strict routes still preserve old semantics
15. verify no effect on projection/Observation/Current State writers
```

No `traffic_projection.service` restart is required by this architecture because its write path/schema is unchanged.

---

# 34. Rollback

Minimum semantic rollback:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
restart captive-portal.service
```

Then:

```text
Home/Traffic return to legacy strict requests
existing DBs remain untouched
no cleanup/backfill reversal is required
```

If code itself causes regression while the feature is disabled, use the normal reviewed application deployment rollback.

Never delete:

```text
observations.sqlite3
traffic_projection.sqlite3
current_state.sqlite3
```

as part of feature rollback.

---

# 35. Acceptance fixtures

Use deterministic synthetic fixture Site:

```text
site_id = aaaaaaaaaaaaaaaaaaaaaaaa
```

AP identities:

```text
AP-1 = 00:00:00:00:00:01
AP-2 = 00:00:00:00:00:02
AP-3 = 00:00:00:00:00:03
AP-4 = 00:00:00:00:00:04
```

Unless stated otherwise, selected source is Wired and all timestamps are within a 10-second skew.

Synthetic rates:

```text
AP-1 = 10 down / 1 up
AP-2 =  5 down / 1 up
AP-3 =  3 down / 1 up
AP-4 =  2 down / 1 up
```

Full total:

```text
Download = 20 Mbps
Upload   = 4 Mbps
Total    = 24 Mbps
```

Three-AP subtotal:

```text
Download = 18 Mbps
Upload   = 3 Mbps
Total    = 21 Mbps
```

---

# 36. Mandatory PASS/FAIL matrix

## T01 — all four APs Online and measured

Input:

```text
Current State:
4 online

Observation:
4/4 valid Wired pairs
```

Expected JSON core:

```json
{
  "measurement_state": "complete_installed",
  "population_scope": "installed",
  "traffic": {
    "download_mbps": 20.0,
    "upload_mbps": 4.0,
    "total_mbps": 24.0
  },
  "coverage": {
    "installed_ap_count": 4,
    "online_ap_count": 4,
    "offline_ap_count": 0,
    "measured_pair_ap_count": 4,
    "offline_excluded_ap_count": 0,
    "missing_required_ap_count": 0
  }
}
```

Visible:

```text
Total traffic: 24 Mbps
Complete AP coverage · 4 of 4 APs measured
```

PASS only if no partial warning is shown.

---

## T02 — AP-4 confirmed Offline, other three measured

Input:

```text
aligned Current State:
AP1 online
AP2 online
AP3 online
AP4 offline

Observation:
AP1/2/3 = valid
AP4 = source_unavailable for both selected directions
```

Expected:

```json
{
  "measurement_state": "complete_online_population",
  "population_scope": "confirmed_online",
  "traffic": {
    "download_mbps": 18.0,
    "upload_mbps": 3.0,
    "total_mbps": 21.0
  },
  "coverage": {
    "installed_ap_count": 4,
    "online_ap_count": 3,
    "offline_ap_count": 1,
    "measured_pair_ap_count": 3,
    "required_measurement_ap_count": 3,
    "missing_required_ap_count": 0,
    "offline_excluded_ap_count": 1
  }
}
```

Visible Current:

```text
Total traffic: 21 Mbps
3 Online / 4 total · 1 Offline excluded
```

Historical representation of the same source partial cycle:

```text
Measured partial coverage
3 of 4 APs measured
21 Mbps
```

It is not retroactively promoted to a strict historical complete point.

FAIL if AP-4 receives a stored/synthesized 0 Mbps rate.

---

## T03 — AP-4 Online but Wired/LAN missing

Input:

```text
AP4 status = online
AP4 selected-source reason = source_unavailable
AP1/2/3 valid
```

Expected:

```json
{
  "measurement_state": "partial_measured",
  "traffic": {
    "total_mbps": 21.0
  },
  "coverage": {
    "installed_ap_count": 4,
    "online_ap_count": 4,
    "measured_pair_ap_count": 3,
    "missing_required_ap_count": 1,
    "offline_excluded_ap_count": 0,
    "coverage_reasons": ["online_measurement_missing", "source_unavailable"]
  }
}
```

Visible:

```text
Measured traffic: 21 Mbps
Partial data · 3 of 4 APs measured
```

FAIL if:

```text
complete
4/4
24 Mbps
AP4=0
```

is reported.

---

## T04 — AP-4 Unknown/other or status evidence stale

Input variant A:

```text
AP4 status = unknown
```

Input variant B:

```text
AP4 status = other
```

Input variant C:

```text
last complete status snapshot older than AP fresh threshold
```

All with AP4 traffic missing and AP1/2/3 valid.

Expected:

```text
measurement_state = partial_measured
offline_excluded_ap_count = 0
total = 21 Mbps
```

Reason must identify:

```text
unknown_status_measurement_missing
OR other_status_measurement_missing
OR status_evidence_stale
```

Visible:

```text
Measured traffic: 21 Mbps
Partial data
```

No variant may become `complete_online_population`.

---

## T05 — no measured AP

Input:

```text
all selected-source rate reasons non-ok
no valid Download/Upload values
```

Expected:

```json
{
  "measurement_state": "unavailable",
  "traffic": {
    "download_mbps": null,
    "upload_mbps": null,
    "total_mbps": null
  }
}
```

Visible:

```text
No reliable traffic data
```

FAIL if `0 Mbps`.

Historical overlay branch for a structurally admissible partial cycle with all selected-source directions non-`ok`:

```json
{
  "status": "partial_unmeasured",
  "download_mbps": null,
  "upload_mbps": null,
  "total_mbps": null,
  "download_sample_count": 0,
  "upload_sample_count": 0,
  "measured_sample_count": 0,
  "coverage_ratio": 0.0
}
```

Visible historical result:

```text
Partial coverage — no reliable traffic measurement
```

The `0.0` above is only a proven **pair coverage ratio** with a positive observed-AP denominator; it is never rendered as traffic.

---

## T06 — actual measured zero

Input:

```text
4 valid AP pairs
all numeric values = 0.0
all reasons = ok
```

Expected:

```text
complete_installed
Download = 0
Upload = 0
Total = 0
```

Visible:

```text
Total traffic: 0 Mbps
```

PASS only because actual numeric zero facts exist.

---

## T07 — AP-4 returns; no_baseline / counter_reset

Phase 1:

```text
AP4 = online
AP1/2/3 = valid
AP4 = no_baseline
```

Expected:

```text
partial_measured
21 Mbps measured subtotal
no Offline exclusion
```

Phase 2:

```text
AP4 next valid pair = 2/1
```

Expected:

```text
complete_installed
24 Mbps
```

No stale AP4 rate may be reused between phases.

---

## T08 — Site AP composition changed

Variant A:

```text
Current State I = AP1/AP2/AP3/AP4/AP5
Observation R  = AP1/AP2/AP3/AP4
```

Expected:

```text
population_match_state = mismatch
measurement_state != complete_online_population
```

Variant B:

```text
Observation contains row whose site_id != requested Site
```

Expected Current:

```text
source integrity unavailable
no numeric Site aggregate
```

Variant C:

```text
same AP MAC exists in another Site
```

Expected:

```text
no cross-Site join
```

---

## T09 — timestamps not comparable

Variant A:

```text
selected AP rate source_skew > configured max
```

Expected:

```text
measurement_state = unavailable
traffic = null
coverage reason = temporal_skew
```

Variant B:

```text
selected traffic sample age > stale max
```

Expected:

```text
freshness = unavailable
traffic = null
```

Variant C:

```text
fresh < age <= stale
```

Expected:

```text
numeric value retained
freshness = stale
UI explicitly says STALE
```

No nonsimultaneous Site sum is allowed.

---

## T10 — Wired/LAN source selection

Variant A:

```text
Wired valid pairs = 3/4
LAN valid pairs   = 4/4
```

Expected:

```text
selected_source = lan
selection_reason = fallback_full_observation_coverage
complete_installed
```

Variant B:

```text
Wired valid pairs = 3
LAN valid pairs   = 2
```

Expected:

```text
selected_source = wired
partial unless Offline promotion rules fully pass
```

Variant C:

```text
some AP only Wired
different AP only LAN
neither family covers required population
```

Expected:

```text
NO per-AP source mixing
partial or unavailable
```

---

## T11 — historical 4 → 3 → 4 AP coverage

Fixture:

```text
bucket A = strict complete 4/4
bucket B = source partial 3/4
bucket C = strict complete 4/4
```

Expected graph:

```text
A = Complete AP coverage
B = Measured partial coverage
C = Complete AP coverage
```

Expected period semantics:

```json
{
  "status": "ok",
  "reason": "partial_measurements_present",
  "has_partial_measurements": true,
  "source_coverage_insufficient": false,
  "statistics_scope": "complete_coverage_intervals_only",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

UI:

```text
Partial AP coverage exists in this period.
Average · complete-coverage intervals only
Max observed with complete AP coverage
```

FAIL if the 3-AP subtotal is averaged into strict v1 statistics and labelled as a complete period average.

---

## T12 — duplicate MAC / corrupted row / bad Site / invalid rate

Any of:

```text
duplicate AP MAC within cycle
bad canonical MAC
wrong Site row
reason=ok + NULL value
reason!=ok + numeric value
invalid timestamp
row count != cycle metadata
items_skipped > 0
```

Expected Current:

```text
fail closed
no numeric aggregate from that cycle
```

Expected Historical overlay:

```text
cycle rejected from numeric overlay
integrity rejection count increments
no zero substitution
```

---

## T13 — backward compatibility and protected products

With:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

and requests without `coverage_mode`:

```text
existing strict Current Traffic semantics unchanged
existing strict Historical Traffic semantics unchanged
```

Required regression PASS:

```text
NI-03
NI-04 work boundaries
Guest Traffic
Session Traffic
Portal/Auth/CAPPORT
Current State collection
Observation collection
Traffic Projection
Fingerprint
```

No old API client receives partial semantics silently.

---

## T14 — automatic AP-4 recovery

Sequence:

```text
offline + source_unavailable
→ complete_online_population Current
→ AP becomes online
→ no_baseline/counter_reset
→ partial_measured
→ valid pair appears
→ complete_installed
```

Expected:

```text
no DB repair
no backfill
no manual cache invalidation
no service repair action
```

Only normal data acquisition is required.

---

# 37. Additional mandatory tests

## T15 — Offline status but incompatible traffic evidence

Input:

```text
AP4 status = offline
AP4 rate reason = counter_reset
```

Expected:

```text
NOT complete_online_population
partial_measured or unavailable
coverage_reasons contains exact wire value:
status_measurement_conflict
```

If other independent reasons apply they may also be present, but `status_measurement_conflict` is mandatory for this fixture.

An Offline status does not authorize ignoring arbitrary non-`source_unavailable` failures.

## T16 — future Offline snapshot

Traffic cycle finishes at T.

Only Offline Current State snapshot exists at T+30s.

Expected:

```text
that future snapshot is not used
no retroactive Offline promotion
```

## T17 — partial-overlay capacity limit

Input exceeds either overlay hard cap or the 5-second local overlay budget. Strict history source remains healthy and contains a numeric strict Average/Peak.

Exact wire assertion:

```json
{
  "status": "capacity_limited",
  "reason": "overlay_capacity_limited",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "statistics_scope": "complete_coverage_intervals_only",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

Visible result assertions:

```text
Partial-coverage evidence exceeded the bounded query limit for this period.
Average · complete-coverage intervals only · partial coverage not fully evaluated
Max observed with complete AP coverage · partial coverage not fully evaluated
Comparison unavailable because partial coverage could not be fully evaluated.
AP share unavailable because partial coverage could not be fully evaluated.
```

Strict Average/Peak numeric fields remain exactly their strict values if the strict source is sound. Comparison numeric fields and AP-share fractions are `NULL`. No truncated overlay is returned.

---

## T18 — raw partial source unavailable

Strict projection remains usable and contains a numeric strict Average/Peak.

Exact wire assertion:

```json
{
  "status": "unavailable",
  "reason": "overlay_source_unavailable",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "statistics_scope": "complete_coverage_intervals_only",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

Visible result assertions:

```text
Partial-coverage evidence is unavailable for this period.
Average · complete-coverage intervals only · partial coverage not verified
Max observed with complete AP coverage · partial coverage not verified
Comparison unavailable because partial-coverage status is unknown.
AP share unavailable because partial-coverage status is unknown.
```

FAIL if absence of overlay is stated as `no partial data`, or if `has_partial_measurements=false`.

---

## T19 — strict-only range

No partial cycles in range and raw source coverage is proven complete.

Expected exact overlay fields:

```json
{
  "status": "ok",
  "reason": "no_partial_measurements",
  "has_partial_measurements": false,
  "source_coverage_insufficient": false,
  "buckets": [],
  "bucket_count_returned": 0
}
```

`comparison_allowed` and `ap_share_allowed` equal the existing strict eligibility for the same fixture and are concrete booleans, never `null`. Existing chart/statistics wording remains unchanged.

---

## T20 — mixed complete + partial samples inside one graph bucket

Expected:

```text
strict complete bucket remains unchanged
partial overlay bucket is also returned
UI says: This interval contains both complete and partial AP measurements.
no merged complete mean is created
```

If the partial bucket has coherent Total samples, it follows `partial_measured`; if it has only directional evidence, it follows `partial_directional`; if it has no valid directions, it follows `partial_unmeasured`.

---

## T21 — raw source coverage insufficient

Requested range extends beyond raw Observation coverage while strict projection remains healthy.

Exact wire assertion:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_incomplete",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": true,
  "statistics_scope": "complete_coverage_intervals_only",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

Visible result assertions:

```text
Partial-coverage evidence is unavailable for part of this period because raw Observation coverage is incomplete.
Average · complete-coverage intervals only · partial coverage not fully covered
Max observed with complete AP coverage · partial coverage not fully covered
Comparison unavailable because partial-coverage source coverage is incomplete.
AP share unavailable because partial-coverage source coverage is incomplete.
```

No partial numeric bucket from the covered sub-range is returned.

---

## T22 — historical all directions unavailable

One structurally admissible partial cycle, observed AP count 4, selected source fixed, all Download/Upload reasons non-`ok`.

Expected:

```text
status = partial_unmeasured
download_mbps = NULL
upload_mbps = NULL
total_mbps = NULL
download_sample_count = 0
upload_sample_count = 0
measured_sample_count = 0
observed_ap_opportunities = 4
measured_pair_ap_opportunities = 0
coverage_ratio = 0.0
```

No 0 Mbps point.

---

## T23 — historical download-only evidence

One structurally admissible partial cycle:

```text
R={AP1,AP2,AP3,AP4}
D={AP1,AP2,AP3}
U={}
```

Expected:

```text
status = partial_directional
download_mbps = sum(AP1..AP3 Download)
upload_mbps = NULL
total_mbps = NULL
download_sample_count = 1
upload_sample_count = 0
measured_sample_count = 0
measured_download_ap_opportunities = 3
measured_upload_ap_opportunities = 0
measured_pair_ap_opportunities = 0
coverage_ratio = 0.0
```

Tooltip explicitly says `Upload unavailable`; no combined total.

---

## T24 — historical upload-only and different-valid-direction samples

Variant A, one cycle:

```text
D={}
U={AP1,AP2}
```

Expected `partial_directional`, Download `NULL`, Upload numeric, Total `NULL`.

Variant B, two cycles:

```text
cycle 1: D={AP1,AP2}, U={}
cycle 2: D={}, U={AP1,AP2,AP3}
```

Expected:

```text
download_sample_count = 1
upload_sample_count = 1
measured_sample_count = 0
download_mbps = cycle1 download subtotal
upload_mbps = cycle2 upload subtotal
total_mbps = NULL
```

FAIL if Download mean + Upload mean is emitted as Total.

---

## T25 — varying observed AP population inside one bucket

Two admitted cycles with the same selected source:

```text
cycle 1: |R|=4, |P|=3
cycle 2: |R|=5, |P|=4
```

Expected:

```text
observed_ap_opportunities = 9
measured_pair_ap_opportunities = 7
coverage_ratio = 7/9
min_observed_ap_count = 4
max_observed_ap_count = 5
min_measured_ap_count = 3
max_measured_ap_count = 4
```

`coverage_ratio` MUST NOT be `(3/4 + 4/5)/2`.

---


# 38. Real-incident replay acceptance

The implementation test suite MUST contain a deterministic fixture reproducing the production evidence shape, without embedding private production database files.

Essential fixture:

```text
Current State:
AP-4 offline shortly before traffic cycle

AP-dynamic cycle:
result=partial
complete=false
items_seen=4
items_stored=4
items_skipped=0
error_count=2
warnings=0

AP1/2/3:
Wired pair ok
LAN pair ok

AP4:
Wired source_unavailable
LAN source_unavailable
```

Current expected:

```text
complete_online_population
3 Online / 4 total
3 measured
1 Offline excluded
numeric subtotal from AP1/2/3
```

Historical expected:

```text
partial overlay
3 of 4 measured
numeric measured subtotal
strict statistics unchanged
```

This fixture is mandatory because it represents the incident that motivated the TASK.

---

# 39. Test gate

Minimum targeted suites:

```text
tests/analytics/**
tests/current_state/**
tests/admin_web/**
tests/traffic_projection/**
tests/observations/**
```

plus new focused tests for this TASK.

Full repository gate before handoff:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
git status --short
```

Tech Lead handoff must record exact:

```text
baseline SHA
implementation SHA
test counts
skips
failures
feature flag state
```

---

# 40. Compatibility proof obligations

Coder implementation is not complete until all are demonstrated:

```text
1. coverage_mode absent => legacy semantic behavior
2. feature=false => UI does not request partial_v1
3. no DB schema/user_version changes
4. no new Omada calls
5. no change to Observation writer
6. no change to Traffic Projection writer
7. no change to Current State collector/status classifier
8. no source-mixing across Wired/LAN within Site sample
9. no raw DB access from Admin route/browser
10. no fake zeros
11. no cross-Site AP joins
12. current query remains bounded
13. 24h/7d historical partial scan remains bounded
14. Portal/Auth/CAPPORT unaffected
```

---

# 41. Architecture rationale

The production failure is not a collection failure for the healthy APs.

It is a **consumer completeness policy problem**.

The source already says:

```text
AP-1 measured
AP-2 measured
AP-3 measured
AP-4 missing
cycle partial
```

Current State independently says:

```text
AP-4 Offline
```

The existing current/historical consumers discard too much useful evidence because they require a globally complete source cycle.

Therefore the correct minimal repair is not:

```text
new collector
new traffic source
new projection schema
fake zeros
```

It is:

```text
preserve source truth
+
add coverage-aware read semantics
+
make incompleteness explicit
```

The current product may safely use authoritative, temporally aligned Offline status to narrow the live expected population.

Historical product must remain more conservative because its status authority has different retention and must not be reconstructed.

This gives the Owner the desired practical behavior while preserving the project's permanent rule:

```text
missing / unknown / stale / unavailable != 0
```

---

# 41.1 R1 normative replacement index

For Tech Lead review, these are the only intentional semantic changes from v1:

```text
§0.1 / §4.3 / §9.2
  P2-01 precedence: source-partial + fully measured observed rows + no Current State proof => partial_measured.

§11.1 / T15
  Adds exact closed reason status_measurement_conflict.

§14.1 / §15 / T05 / T22–T25
  Freezes source tie-break for directional evidence, directional admission, coherent-total rule, per-direction denominators, measured_sample_count and coverage_ratio.

§16.4–16.5 / §17 / §18.3 / §19 / §24–25 / §28.2 / T17–T21
  Freezes historical overlay tri-state JSON, failure envelopes, comparison/AP-share suppression and exact visible copy.
```

Everything else remains as in v1 unless wording in this complete R1 document necessarily cross-references the corrected semantics.

---

# 42. Tech Lead implementation handoff boundaries

After Tech Lead accepts this Architecture Contract, the implementation TASK must be mechanically derivable from it.

Coder is allowed to choose:

```text
local function names
small private helper decomposition
test helper layout
non-semantic refactoring required by style/tests
```

Coder is NOT allowed to choose:

```text
which AP states count as Offline
whether stale status counts as Offline
whether NULL means 0
whether to mix Wired/LAN
whether to alter historical statistics with partial subtotals
which source owns AP status
whether to add a DB/collector
whether to change retention
API compatibility mode
public status enums
UI wording semantics
rollout/rollback strategy
capacity behavior
```

Any discovered requirement to change a protected contract returns to Tech Lead/Architect.

---

# 43. Final verdict

```text
TASK =
TASK-TRAFFIC-PARTIAL-COVERAGE-01

CONTRACT =
TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1

BASELINE =
main@e8061de9fbd6da8be5cd269779070a4db4d59d64
TREE d5503fe1f2b5774bbe55cb2d34dba63246f56f6f

TECH_LEAD_R1_CORE =
ACCEPTED IN PRINCIPLE

OWNER PROPOSAL =
ACCEPT WITH LIMITS

SELECTED ARCHITECTURE =
OPTION 3 / COMBINATION

R1_P1_01 = CLOSED BY ARCHITECT
R1_P1_02 = CLOSED BY ARCHITECT
R1_P1_03 = CLOSED BY ARCHITECT
R1_P1_04 = CLOSED BY ARCHITECT
R1_P2_01 = CLOSED BY ARCHITECT

CURRENT TRAFFIC =
confirmed Offline may be excluded from the confirmed-online population
only with authoritative temporally aligned Current State evidence;
a fully measured source-partial cycle without installed-population proof remains partial_measured

HISTORICAL TRAFFIC =
keep strict projection/statistics unchanged;
add bounded read-only partial Observation overlay;
freeze independent directional denominators and coherent Total samples;
never mix partial subtotals into strict period Average/Peak/AP-share semantics

HISTORICAL_UNKNOWN_PRESENCE_WIRE =
boolean|null; unknown = JSON null

SOURCE CHANGES = NONE
NEW COLLECTOR = NO
NEW OMADA REQUEST = NO
NEW DATABASE = NO
SCHEMA MIGRATION = NO
BACKFILL = NO
FEATURE GATE = WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false by default

OPEN_P0 = 0
OPEN_P1 = 0  # Architect-side after R1 corrections; awaiting Tech Lead acceptance
OPEN_P2 = 0  # Architect-side after R1 clarification; awaiting Tech Lead acceptance

ARCHITECTURE_STATUS =
R1 CORRECTIONS ISSUED / READY FOR TECH LEAD RE-REVIEW

READY_FOR_TECH_LEAD_IMPLEMENTATION_TASK =
NO — becomes YES only after Tech Lead accepts v1-R1

IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD
PRODUCTION_CHANGE = NO
```
