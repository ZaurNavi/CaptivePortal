# TASK-TRAFFIC-08 — Completed Guest Session Traffic — ARCHITECTURAL DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Working roadmap item:** `TRAFFIC-08`  
**Working product name:** `Completed Guest Session Traffic`  
**Document state:** `ARCHITECTURAL DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Prepared:** 2026-09-03  
**Implementation authorization:** `NOT GRANTED`  
**Coder / branch / patch / PR / publication / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Proposed name / TASK ID

Working TASK:

```text
TASK-TRAFFIC-08 — Completed Guest Session Traffic
```

Architectural recommendation for the semantic owner:

```text
CompletedGuestSessionTrafficReadService
```

This name is intentionally Visit/session-specific.

It must NOT be confused with:

```text
HistoricalTrafficReadService
CurrentGuestTrafficReadService
VisitAnalyticsService aggregate traffic summary
Public Traffic Counter
```

This document is a DRAFT.

`TRAFFIC-08` is NOT canonical/frozen until Owner + Tech Lead approve the
architecture.

---

# 2. Repository / production baseline

Current `origin/main` was re-fetched before this DRAFT.

Canonical repository parent:

```text
main:
e196b042515498c5cd9143a9962f6aed90f31566

tree:
f88ee1f854135107c647ccd9d346be2b2ba504b9
```

Current main commit:

```text
Merge pull request #100
Docs: reconcile TRAFFIC-07 Online Guests Traffic production state
```

Functional TRAFFIC-07 production merge:

```text
HEAD:
6425988b5b4ec5ff38bf9c67c74846c3806f668f

tree:
b669f368b0062fcb100b24758cf05e2c4b500144
```

PR #100 is the current documentation/KB reconciliation layer on top of the
functional production merge.

Current KB explicitly states:

```text
No approved next Traffic TASK is currently assigned.
No TRAFFIC-08 is canonical change-intent.
```

Therefore this document creates only a proposed next architecture.

Before FINAL:

```text
re-fetch origin/main
re-pin exact SHA/tree
impact-review any drift
```

Before implementation authorization:

```text
repeat repository rebind
```

---

# 3. Architectural conclusion

The requested product is feasible with existing persisted foundations.

Recommended v1:

```text
NO new collector

NO query-time Omada

NO new database

NO source schema change

NO Current State acquisition change

NO Observation acquisition change
```

However the current persisted evidence does NOT support a universal claim of:

```text
exact packet-complete Download / Upload / Total bytes
for every completed guest session
```

The correct v1 product must instead expose:

```text
observed completed-session Traffic evidence
```

with an explicit quality model.

Canonical session identity:

```text
Visit Lifecycle Visit
```

Canonical directional Traffic evidence:

```text
Observation authorized client cumulative counters
interpreted as accepted within-Visit interval deltas
```

Controller-reported offline Traffic total:

```text
Visit.reported_traffic_total_bytes
```

is useful auxiliary evidence but is NOT a replacement for the canonical
session D/U/T metric.

Reason:

```text
Omada reports it for the Wi-Fi/controller connection at disconnect,
not explicitly for the Captive Portal Visit authorization interval.
```

---

# 4. Product goal

User-visible goal:

```text
Show completed guest Visits and the Traffic volume that CaptivPortal can
safely attribute to each completed Visit from persisted evidence.
```

The product should let an Admin answer:

```text
Which guest Visits completed in this period?

When did each Visit start/end?

How much Download / Upload / Total Traffic did CaptivPortal actually observe
inside that Visit?

How complete/trustworthy is the Traffic evidence for that Visit?
```

The product must not silently turn sampled/partial evidence into an exact usage
claim.

---

# 5. User-visible result

Recommended panel:

```text
Completed Guest Session Traffic
```

Recommended operator wording:

```text
Completed guest Visits and observed Traffic volume from persisted authorized
client evidence.

Traffic may be partial when session edges, counter resets, reconnects or
observation gaps prevent complete sampled coverage.
```

Recommended columns:

```text
Guest

Session Start

Session End

Duration

SSID

Download

Upload

Total

Evidence
```

Optional compact context:

```text
start AP → final AP
```

No chart is required in v1.

The primary representation is a historical table/list.

---

# 6. Exact semantic object: Completed Guest Session

Canonical v1:

```text
Completed Guest Session
=
one persisted Visit Lifecycle VisitRecord
with status='closed'
for the authorized canonical Site.
```

Identity:

```text
session_id = visit_id
```

NOT:

```text
client MAC alone

AuthSession

Omada connection

Current State row

Visitor Registry device_id

Public Traffic processed event
```

The Visit is the durable lifecycle object that owns:

```text
started_at
closed_at
status
close reason/source
Site
client MAC
start/final SSID
start/final AP
authorization attachments
offline event linkage
```

---

# 7. Session start

Canonical start:

```text
visit.started_at
```

Meaning:

```text
the Visit Lifecycle start timestamp created from the first accepted
authorization that opened this Visit.
```

Do not redefine session start as:

```text
first Observation sample

first Current State row

Wi-Fi association time

first packet

Public Traffic event
```

Those are different evidence types.

---

# 8. Session end

Canonical end:

```text
visit.closed_at
```

for:

```text
status='closed'
```

The close may come from normal/recovered Visit Lifecycle processing.

Displayable close provenance may include:

```text
close_reason
close_time_source
```

if useful for evidence diagnostics, but those fields do not create a different
session identity.

A Visit marked closed with structurally impossible/missing close evidence is an
integrity problem, not a normal zero-duration session.

---

# 9. Session duration

Canonical lifecycle duration:

```text
visit.duration_seconds
```

when safely present/validated.

Product code MUST NOT invent another authoritative duration if Visit Lifecycle
already owns the persisted duration.

For presentation only, start/end timestamps may be shown together.

If an impossible contradiction exists between:

```text
started_at
closed_at
duration_seconds
```

the read layer must fail closed according to the accepted Visit integrity
contract.

---

# 10. Completed-session historical cohort

TRAFFIC-08 is a completion-cohort product.

Selected range means:

```text
visit.closed_at ∈ [from_utc, to_utc)
```

NOT:

```text
visit.started_at ∈ [from_utc, to_utc)
```

This distinction is permanent for the proposed product.

A Visit may:

```text
start before the selected range

close inside the selected range
```

and still belongs to that completion cohort.

Its Traffic interval remains the Visit's full:

```text
started_at → closed_at
```

window.

The range selects completed sessions.

It does NOT clip the session Traffic interval to the range boundary.

---

# 11. Open Visits / incomplete lifecycle

Open Visit:

```text
status='open'
```

is NOT a Completed Guest Session.

It is excluded from TRAFFIC-08.

Therefore:

```text
open Visit
→ not shown as completed session
```

An incomplete lifecycle that cannot establish a safe closed Visit is not repaired
by Current State/Observation/Public Traffic heuristics.

No synthetic close time.

No implicit timeout close inside this read product.

---

# 12. Session without sufficient Traffic evidence

A closed Visit may be a perfectly valid completed session while Traffic evidence
is insufficient.

Example:

```text
Visit closed successfully

but
no accepted Observation interval exists
```

Required:

```text
session remains visible

Traffic values remain null

Traffic evidence status = insufficient_data
```

Session identity/lifecycle completeness and Traffic evidence completeness are
separate dimensions.

---

# 13. Source inventory — Visit Lifecycle

Role:

```text
AUTHORITATIVE completed-session identity/lifecycle source
```

Existing Visit record already persists:

```text
visit_id

site_id

client_mac

device_id (optional linkage)

initial_snapshot_id (optional linkage)

started_at

closed_at

status

close_reason

close_time_source

start_ssid / final_ssid

start_ap_mac / final_ap_mac

reported_connected_seconds

reported_traffic_total_bytes

reported_traffic_up_bytes

reported_traffic_down_bytes

duration_seconds

offline_event_id
```

Important current fact:

```text
one open Visit per Site + client MAC
```

is enforced by Visit Lifecycle storage.

One Visit may contain:

```text
multiple authorization events
```

Therefore Visit is stronger session identity than MAC or AuthSession alone.

---

# 14. Source inventory — Observation

Role:

```text
AUTHORITATIVE sampled directional Traffic evidence source
for TRAFFIC-08 v1
```

Current Observation client collector persists historical client rows for:

```text
wireless
active
authStatus==2
configured client/guest SSID scope
```

Relevant facts include:

```text
site_id
client_mac
observed_at
ssid
ap_mac
traffic_down
traffic_up
```

Existing index:

```text
idx_client_site_mac_time
(site_id, client_mac, observed_at, row_id)
```

supports bounded Visit-window reads.

Observation is historical measurement evidence.

It is not session identity owner.

---

# 15. Source inventory — Current State

Current State owns current Online Guest evidence and TRAFFIC-07.

For TRAFFIC-08:

```text
Current State is NOT an authoritative completed-session source.
```

It is not required for v1 Traffic calculation.

Reason:

```text
TRAFFIC-08 is historical/closed-Visit based

Observation already owns persisted historical authorized client evidence
```

No Current State fallback.

No attempt to stitch current snapshot history into old completed Visit traffic.

---

# 16. Source inventory — Visitor Registry

Visitor Registry owns durable device identity/history.

TRAFFIC-08 v1 does NOT require Registry to define a completed session.

Optional future use:

```text
display enrichment
stable device identity
```

But:

```text
device_id
```

MUST NOT replace:

```text
visit_id
```

as session identity.

Randomized MACs may be linked to one device later.

TRAFFIC-08 v1 does not merge their Visits.

Architect recommendation:

```text
Registry enrichment OUT OF v1
```

unless Owner explicitly requires a friendly device identity before FINAL.

---

# 17. Source inventory — AuthSession / authorization lifecycle

AuthSession is NOT the completed session identity.

Reason:

```text
one Visit may contain multiple authorization events
```

and process-local AuthSession lifetime is not the durable Visit lifecycle.

Authorization evidence is still useful as a segmentation boundary.

The existing persisted Visit authorization attachments may be used to avoid
bridging Traffic deltas across repeated authorization events.

No dependence on process-local AuthSession state.

---

# 18. Source inventory — existing Historical Traffic foundations

`HistoricalTrafficReadService` owns:

```text
Site/AP Network Traffic
```

It MUST remain untouched.

Completed Guest Session Traffic is a different metric family:

```text
Visit/session-attributed client Traffic
```

TRAFFIC-08 MUST NOT:

```text
allocate AP historical Traffic to sessions

reuse AP Share to estimate guest usage

force session totals to equal Site Traffic

add session semantics into HistoricalTrafficReadService
```

The existing Traffic historical browser scheduler may be reused.

The AP Network Traffic semantic owner must not be expanded.

---

# 19. Source inventory — CurrentGuestTrafficReadService

TRAFFIC-07-READ owns:

```text
near-current Online Guest rate
```

It does NOT own completed historical session volume.

Do not:

```text
integrate current Mbps over time

replay TRAFFIC-07 snapshots

reuse current cursor semantics as historical session identity
```

TRAFFIC-07-READ remains frozen/no-touch.

---

# 20. Source inventory — existing Visit Analytics

Current Analytics already contains valuable reusable primitives:

```text
Visit windows

Observation coverage over Visit windows

batch Visit observed Traffic calculation

counter-delta handling

Visit/Observation source provenance

read-only cross-source gateway
```

Existing:

```text
VisitAnalyticsService.get_visit_traffic_summary(...)
```

is an aggregate Visit Analytics metric.

It is NOT yet a per-session product contract.

Current aggregate Visit Analytics also uses existing cohort semantics that are
not the proposed:

```text
closed_at completion cohort
```

for TRAFFIC-08.

Therefore:

```text
REUSE primitives

DO NOT silently relabel current aggregate Visit Analytics as TRAFFIC-08
```

---

# 21. Source inventory — Public Traffic Counter

The repository already has:

```text
Public completed-session traffic counter
```

and:

```text
public_traffic.sqlite3
```

It must be inventoried explicitly.

Current purpose:

```text
aggregate completed public SSID traffic from normalized Omada offline events
```

It maintains:

```text
per-SSID/day aggregate traffic

completed-session counts

processed event deduplication
```

It is useful for the public aggregate counter.

It is NOT the canonical per-Visit TRAFFIC-08 source because its persistence is
not a Visit/Site/MAC session read model.

Its event storage is centered on:

```text
normalized_event_id
SSID
event traffic bytes
source offset
counted/skip reason
```

not:

```text
visit_id
Site + MAC Visit identity
directional D/U session evidence
```

TRAFFIC-08 MUST NOT mutate or repurpose Public Traffic storage.

---

# 22. Offline controller-reported Traffic evidence

Visit Lifecycle currently persists:

```text
reported_traffic_total_bytes
```

from normalized:

```text
omada.client_offline
```

evidence.

This is valuable evidence.

But its semantic is:

```text
Omada-reported Traffic for the Wi-Fi/controller connection at disconnect
```

not explicitly:

```text
Traffic accumulated only after Captive Portal Visit authorization
```

The controller connection may predate the Visit start.

Therefore v1 primary D/U/T MUST NOT substitute:

```text
reported_traffic_total_bytes
```

for Visit-attributed observed Traffic.

---

# 23. Directional reported Traffic limitation

Current normal Visit finalization stores:

```text
reported_traffic_total_bytes = numeric when reported

reported_traffic_up_bytes = null

reported_traffic_down_bytes = null
```

for the normal Omada offline path.

Therefore the existing offline report cannot provide canonical:

```text
Download
Upload
```

for TRAFFIC-08.

Do not invent a directional split.

Do not divide Total proportionally using Observation/AP ratios.

---

# 24. Proposed semantic owner

New owner:

```text
CompletedGuestSessionTrafficReadService
```

Conceptual responsibility:

```text
select completed Visit cohort

validate Visit identity/lifecycle

load persisted authorization boundaries if required

load existing Observation evidence

derive per-Visit observed D/U/T bytes

derive evidence/quality

paginate deterministically

return immutable semantic DTO
```

It is read-only.

It does not poll.

It does not write.

It does not own Visit persistence.

It does not own Observation persistence.

---

# 25. Why not VisitLifecycleReadService as owner

`VisitLifecycleReadService` owns lifecycle facts.

It should NOT absorb Observation counter arithmetic.

Otherwise Visit Lifecycle would become owner of a metric derived from another
source domain.

Recommended:

```text
VisitLifecycleReadService
→ lifecycle facts

CompletedGuestSessionTrafficReadService
→ cross-source session Traffic interpretation
```

---

# 26. Why not VisitAnalyticsService as the sole owner

`VisitAnalyticsService` already owns broad aggregate Visit Analytics.

It should remain reusable.

However TRAFFIC-08 needs a distinct contract for:

```text
per-session rows

completion cohort

cursor pinning

per-session evidence status

Admin Traffic product semantics
```

Architect recommendation:

```text
new CompletedGuestSessionTrafficReadService
using existing AnalyticsSourceGateway / Visit Analytics primitives
```

rather than altering old aggregate metrics into a new meaning.

Owner + Tech Lead may choose to place the class physically in `app/analytics`.

Semantic ownership remains distinct.

---

# 27. Proposed data flow

```text
Visit Lifecycle
(visits.sqlite3)
        |
        | closed Visit identity/window
        v
VisitLifecycleReadService / AnalyticsSourceGateway
        |
        +-------------------------------+
                                        |
Observation                              |
(observations.sqlite3)                   |
        |                               |
        | authorized client samples      |
        v                               v
AnalyticsSourceGateway batch primitives
        |
        v
CompletedGuestSessionTrafficReadService
        |
        v
AdminQueryService
        |
        v
Admin API
        |
        v
Traffic historical orchestration
        |
        v
Admin Console → Completed Guest Session Traffic
```

Auxiliary only:

```text
Visit reported_traffic_total_bytes
```

No Public Traffic join.

No Current State join.

No query-time Omada.

---

# 28. Correlation identity

Canonical cross-source correlation:

```text
Site
+
client MAC
+
Visit time window
+
Visit identity
```

Visit ID remains the product item identity.

Observation rows are attributable only when:

```text
observation.site_id == visit.site_id

observation.client_mac == visit.client_mac

observation.observed_at lies inside the accepted Visit window
```

This is correlation, not identity replacement.

---

# 29. Visit time window

For a closed Visit:

```text
session_start = visit.started_at

session_end = visit.closed_at
```

Observation sample inclusion:

```text
observed_at >= session_start
AND
observed_at <= session_end
```

Counter delta for an interval is accepted only when BOTH interval endpoints
belong to the same accepted session segment.

Never use a pre-Visit observation as the previous counter merely to fill the
start edge.

Never use a post-close observation as the next counter merely to fill the end
edge.

---

# 30. Multiple authorizations in one Visit

One Visit may contain multiple authorization records.

Repeated authorization does NOT create a new Completed Guest Session by itself.

However it creates a Traffic evidence boundary.

Recommended v1:

```text
each authorization timestamp after the Visit start
starts a new attribution segment
```

Do not compute a counter delta whose interval crosses an authorization boundary.

Reason:

```text
the interval cannot be proven wholly attributable to one continuous accepted
authorization segment.
```

After the boundary, later valid intervals may contribute normally.

---

# 31. Client MAC

MAC is necessary for Observation correlation.

MAC is NOT the session identity.

The session identity remains:

```text
visit_id
```

This matters because:

```text
one MAC may have many sequential Visits

one Visit may have multiple authorization events
```

No aggregation by MAC before session semantics are established.

---

# 32. Randomized MAC

A new/randomized MAC:

```text
different network identity
```

normally yields a separate Visit context.

Even if Registry later associates two MACs with one stable device:

```text
TRAFFIC-08 v1 does NOT merge those Visits.
```

No retrospective session stitching by device_id.

---

# 33. Reconnect behavior

If reconnect/reauthorization closes one Visit and opens another:

```text
two Visit IDs
→ two completed sessions
```

If a controller reconnect/reset occurs while the same Visit remains open:

```text
Visit identity remains one session
```

but counter continuity may break.

TRAFFIC-08 then:

```text
rejects the cross-reset interval

may resume accumulation from later valid intervals

marks evidence partial
```

No synthetic Visit split in the read layer.

---

# 34. AP roaming

AP change alone:

```text
does NOT create a session boundary
```

and does NOT invalidate client counter deltas.

The same Visit may move:

```text
AP-A → AP-B
```

Display may show:

```text
start AP → final AP
```

but Traffic remains Visit-centric.

No AP Traffic allocation.

---

# 35. SSID transition

SSID change inside one Visit is significant evidence.

Recommended v1:

```text
do not accept a delta interval that crosses an SSID transition
```

Reason:

```text
the client/controller context may have changed,
and the interval cannot be attributed safely to one stable guest context.
```

Subsequent valid intervals on the new accepted SSID may be accumulated.

Visit remains one Visit.

Evidence status becomes at least:

```text
partial
```

unless FINAL review proves a stronger safe rule.

---

# 36. Counter model

Canonical Observation counters:

```text
traffic_down
traffic_up
```

For two consecutive eligible samples inside one accepted segment:

```text
D0, U0 at t0
D1, U1 at t1
```

Directional delta candidate:

```text
ΔD = D1 - D0
ΔU = U1 - U0
```

Accepted only under the strict interval rules below.

---

# 37. Counter interval rules

Directional interval accepted when:

```text
both endpoint counters exist

current counter >= previous counter

0 < elapsed_seconds <= accepted gap threshold

same Site

same MAC

same Visit

same attribution segment

no authorization boundary crossed

no SSID boundary crossed
```

AP equality is NOT required.

Existing Analytics counter gap threshold:

```text
180 seconds
```

is the initial v1 candidate.

Architect recommendation:

```text
REUSE existing Analytics counter/gap quality contract
rather than create a second session-specific gap threshold.
```

---

# 38. Counter reset

If:

```text
current counter < previous counter
```

then:

```text
counter_reset
```

That interval contributes:

```text
null / nothing
```

to the observed sum.

No unsigned-wrap assumption.

No negative correction.

No clamp-to-zero.

Later valid intervals after the reset may contribute as a new segment.

Overall evidence becomes:

```text
partial
```

when usable evidence remains.

---

# 39. Missing first sample

Traffic between:

```text
visit.started_at
```

and:

```text
first accepted Observation sample
```

cannot be reconstructed from current v1 sources without introducing another
cross-source continuity assumption.

Therefore:

```text
start edge is unobserved
```

unless a future explicit anchor contract is approved.

Do NOT use a pre-Visit sample.

Do NOT treat missing start-edge Traffic as zero.

---

# 40. Missing final sample

Traffic between:

```text
last accepted Observation sample
```

and:

```text
visit.closed_at
```

may be unobserved.

Current Omada offline event supplies Total only, not canonical directional D/U.

Therefore it cannot safely fill directional end-edge bytes.

Do NOT infer D/U from the offline Total.

Do NOT treat final edge as zero.

---

# 41. Observation gaps

If consecutive sample elapsed exceeds the accepted gap threshold:

```text
gap interval rejected
```

No interpolation.

No average-rate multiplication.

No AP-level substitution.

Later valid intervals may resume.

Evidence becomes partial if any usable interval remains.

---

# 42. Traffic accumulation

For each direction:

```text
observed_download_bytes
=
SUM(accepted download deltas)

observed_upload_bytes
=
SUM(accepted upload deltas)
```

Canonical Total:

```text
observed_total_bytes
=
observed_download_bytes + observed_upload_bytes
```

only when both directional values are safely numeric according to the evidence
contract.

Backend Total is canonical.

Browser does not recompute semantic Total.

---

# 43. Metric version proposal

Working metric:

```text
network_traffic_completed_guest_session_observed_bytes.v1
```

Working session method:

```text
closed_visit_completion_cohort.v1
```

Working attribution method:

```text
visit_window_authorized_client_counter_interval_sum.v1
```

Working unit:

```text
bytes
```

These identifiers are DRAFT and require Owner + Tech Lead acceptance.

---

# 44. Meaning of numeric Traffic value

A numeric TRAFFIC-08 value means:

```text
bytes proven by accepted persisted Observation counter intervals
inside the completed Visit.
```

It does NOT automatically mean:

```text
exact complete byte count of the whole Visit
```

When evidence is partial:

```text
numeric positive value is an observed lower bound
```

because unobserved edges/gaps may contain additional bytes.

UI/helper text must communicate this.

---

# 45. Numeric zero

Unknown/unobserved Traffic must never become zero.

For v1, sampled Observation evidence cannot generally prove full-session zero
because session start/end edges are not exact directional anchors.

Therefore DRAFT recommendation:

```text
partial sampled evidence + accepted sum=0
→ value=null
NOT 0
```

Numeric zero may be exposed only if FINAL defines a condition that proves zero
for the whole claimed metric interval.

Architect recommendation for v1:

```text
do not claim full-session numeric zero from sampled Observation alone.
```

This requires explicit final review because it is stricter than simple delta
summation.

---

# 46. Controller-reported offline Total

Proposed semantic field, if retained internally:

```text
controller_reported_connection_total_bytes
```

Source:

```text
Visit.reported_traffic_total_bytes
```

It MUST remain separate from:

```text
observed_total_bytes
```

Do not use as fallback.

Do not require equality.

Do not renormalize observed D/U to it.

Do not infer D/U shares from it.

---

# 47. Should controller-reported Total be visible?

Architect recommendation:

```text
NO in v1 primary table
```

Reason:

```text
connection total and Visit-attributed observed Traffic answer different questions

showing both Total fields risks false equivalence
```

It may remain:

```text
diagnostic provenance

future detail view

Lab validation comparator
```

Owner + Tech Lead should explicitly confirm.

---

# 48. Existing Visit Analytics source comparison

Existing Analytics already compares:

```text
reported Traffic
vs
observed Traffic
```

and intentionally keeps those sources separate.

TRAFFIC-08 should preserve that precedent.

Do not collapse them into one "best available" Traffic number.

---

# 49. Proposed item evidence status

Working per-session status:

```text
traffic_evidence_status =
complete
partial
insufficient_data
```

This is Traffic evidence quality.

It is independent from:

```text
Visit lifecycle status
```

because every product item is already a closed Visit.

---

# 50. `complete` evidence proposal

`complete` does NOT mean packet-perfect/full wire capture.

It means:

```text
complete under the accepted sampled-evidence model
```

Draft conditions for both directions:

```text
at least one accepted interval

no rejected internal interval

no counter reset

no missing directional counter inside sampled sequence

no authorization-boundary-crossing delta

no SSID-boundary-crossing delta

max accepted/inter-sample gap within threshold

start edge gap within accepted edge threshold

end edge gap within accepted edge threshold
```

Important:

```text
even complete sampled evidence may still omit bytes between exact lifecycle
boundary and the nearest sample.
```

Therefore the UI must not call it:

```text
exact
billing-complete
packet-complete
```

Before FINAL, Owner + Tech Lead must decide whether `complete` is an acceptable
name or whether a more explicit:

```text
sampled_complete
```

identifier is preferable.

Architect recommendation:

```text
use machine status=complete
but expose helper text "complete sampled evidence"
```

---

# 51. `partial` evidence proposal

`partial` when:

```text
at least one usable accepted directional interval exists

but full sampled coverage conditions do not hold
```

Examples:

```text
start edge missing

end edge missing

gap too large

counter reset

authorization boundary

SSID transition

directional missing counter in some interval
```

Numeric positive observed bytes MAY be shown.

They mean:

```text
proven observed lower bound
```

Unknown remainder is not zero.

---

# 52. `insufficient_data` evidence proposal

`insufficient_data` when no usable Traffic value can safely be established.

Examples:

```text
no Observation sample

only one sample and no exact anchor

all intervals rejected

direction counters missing

all evidence isolated by resets/gaps
```

Required:

```text
D/U/Total = null
```

Session row remains visible.

---

# 53. Directional quality

D/U evidence can differ.

Recommended item fields:

```text
download_bytes
upload_bytes
total_bytes

download_evidence_status
upload_evidence_status
traffic_evidence_status
```

Example:

```text
Download = partial numeric

Upload = insufficient_data / null

Total = null
```

Do not assume missing Upload is zero.

---

# 54. Total quality

Total numeric only when:

```text
Download numeric
AND
Upload numeric
```

Total status:

```text
complete
```

only when both directions are complete.

If one or both directions are partial but both numeric:

```text
Total numeric
overall traffic_evidence_status=partial
```

If either direction is null:

```text
Total=null
```

---

# 55. Evidence provenance fields

Recommended internal/item provenance:

```text
sample_count

accepted_download_interval_count

accepted_upload_interval_count

rejected_gap_interval_count

counter_reset_count

authorization_boundary_count

ssid_transition_count

missing_download_counter_count

missing_upload_counter_count

first_observed_at

last_observed_at

start_edge_gap_seconds

end_edge_gap_seconds

max_inter_sample_gap_seconds
```

Not every field must be visible in the table.

They should be available to the semantic owner and serializer validation.

---

# 56. Session lifecycle quality fields

Recommended item lifecycle provenance:

```text
close_reason

close_time_source

authorization_count
```

Optional in UI Evidence detail.

No browser recomputation.

---

# 57. Historical/range semantics

Recommended product ranges:

```text
24h
7d
```

Default:

```text
24h
```

Range is page-lifetime only, consistent with existing independent Traffic range
behavior.

No storage in:

```text
localStorage
sessionStorage
cookie
profile
```

Reload resets to:

```text
24h
```

unless a later global Traffic UX amendment changes the whole product family.

---

# 58. Range anchor

Each root request resolves:

```text
evaluated_at_utc
```

and derives:

```text
24h:
[evaluated_at-24h, evaluated_at)

7d:
[evaluated_at-7d, evaluated_at)
```

This range applies to:

```text
closed_at completion cohort
```

Cursor chain pins the resolved absolute range.

Page 2 must not move the time window.

---

# 59. Sorting

Recommended fixed v1 sort:

```text
closed_at DESC
visit_id DESC
```

Reason:

```text
operator sees most recently completed sessions first

sorting does not require computing Traffic for the entire range population
```

No v1 sort by Total.

A Traffic-value sort would require evaluating the full completion cohort before
pagination and materially increase work.

Leave it out of v1.

---

# 60. Pagination

Recommended:

```text
default limit = 50
max limit = 200
```

Opaque keyset cursor pins at least:

```text
version

Site

range id

resolved from_utc

resolved to_utc

evaluated_at_utc

sort=closed_at_desc

last closed_at

last visit_id
```

Browser does not decode cursor.

No offset pagination.

---

# 61. Closed-cohort read requirement

Current generic Visit list filtering is start-time oriented.

TRAFFIC-08 requires a dedicated closed-completion cohort read:

```text
site_id
status='closed'
closed_at >= from_utc
closed_at < to_utc
ORDER BY closed_at DESC, visit_id DESC
```

Existing Visit DB already has:

```text
idx_visits_site_closed
(site_id, closed_at, visit_id)
```

Therefore DRAFT recommends:

```text
NO new Visit index initially
```

Use existing index and prove query plan.

---

# 62. Historical read layer choice

TRAFFIC-08 should NOT extend:

```text
HistoricalTrafficReadService
```

because that is AP Network Traffic.

TRAFFIC-08 should have:

```text
CompletedGuestSessionTrafficReadService
```

inside the Analytics/read-only domain.

This is a historical read service in lifecycle sense, but a separate metric
family.

No new database.

No new acquisition path.

---

# 63. Is separate TRAFFIC-08-READ needed?

Architect recommendation:

```text
NO separate roadmap TASK by default.
```

Instead implement TRAFFIC-08 in two internal phases:

```text
Phase A:
per-session read/semantic foundation

Phase B:
Admin product/application layer
```

Reason:

```text
the necessary acquisition/storage foundations already exist

the missing work is a bounded read projection + product surface
```

If Tech Lead determines Phase A is too large for one implementation unit, it may
be split operationally after architecture review.

Do not automatically create `TRAFFIC-08-READ` as a canonical roadmap item from
this DRAFT.

---

# 64. Proposed API

Working endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions
```

Allowed v1 query:

```text
range=24h|7d

limit

cursor
```

No:

```text
sort

MAC filter

SSID filter

AP filter

device filter
```

in v1.

Unknown/duplicate query shape:

```text
400 invalid_request
```

---

# 65. API root proposal

Conceptual:

```text
metric_version

session_method

attribution_method

unit

site_id

range:
  id
  from_utc
  to_utc
  evaluated_at_utc

status

quality:
  session_count_in_range
  complete_count
  partial_count
  insufficient_data_count

items

page:
  limit
  returned_count
  next_cursor
  sort
```

Whether population-wide quality counts are worth computing should be reviewed.

Architect recommendation for v1:

```text
do NOT require full-population Traffic quality counts
```

because that would force Traffic computation for every completed Visit before
pagination.

Instead:

```text
session_count_in_range
```

may be a cheap indexed Visit count.

Traffic-quality counts may be:

```text
page-local
```

and clearly labelled as page-local if included.

This differs intentionally from TRAFFIC-07 current product.

---

# 66. API item proposal

```text
visit_id

client_mac

name?  # only if sourced without new Registry join; otherwise null/out

started_at

closed_at

duration_seconds

start_ssid

final_ssid

start_ap_mac

final_ap_mac

download_bytes

upload_bytes

total_bytes

download_evidence_status

upload_evidence_status

traffic_evidence_status

evidence_reason_codes

sample_count

first_observed_at

last_observed_at
```

Do not expose raw counter values.

Do not expose DB paths/source JSON.

---

# 67. Product capability

The panel contains identifiable client/session history.

Recommended existing capability:

```text
admin.read.devices
```

Same conservative boundary as Online Guests Traffic.

Route MUST re-authorize:

```text
principal
+
canonical Site
+
admin.read.devices
```

Template visibility is not authorization.

No new RBAC capability in v1.

---

# 68. Feature flag

Working proposal:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

Dependencies at configuration level:

```text
WEB_ADMIN_ENABLED=true

WEB_ADMIN_TRAFFIC_ENABLED=true
```

Do not make the entire Admin runtime fail because an optional read dependency is
temporarily unavailable.

Runtime product state should follow the accepted optional-product pattern:

```text
disabled
active
unavailable
```

---

# 69. Runtime dependencies

Active product requires safely composed:

```text
VisitLifecycleReadService

ObservationReadService

AnalyticsSourceGateway or equivalent existing cross-source gateway

CompletedGuestSessionTrafficReadService
```

If active product read dependencies are unavailable:

```text
product unavailable
```

Other Admin/Traffic products remain operational.

No fallback to:

```text
Current State

Public Traffic

Omada
```

---

# 70. Admin query layer

Recommended:

```text
AdminQueryService.completed_guest_session_traffic(...)
```

Responsibilities:

```text
authorize

validate range/limit/cursor

use existing AdminQueryExecutionControls

invoke semantic owner

serialize/fail closed
```

Do not put Traffic arithmetic in AdminQueryService.

Admin deadline remains application-layer owner.

No new worker.

---

# 71. Traffic historical orchestration

TRAFFIC-08 is historical.

It should use the existing:

```text
TrafficHistoricalRequestBroker
+
CaptivPortalTrafficCoordinator
```

historical execution lane.

Permanent global page rules must remain:

```text
max historical Traffic HTTP requests in flight = 1

10-second Historical Request Admission Guard

waiting != loading

Retry-After/backoff remains stricter when applicable
```

TRAFFIC-08 MUST NOT bypass this lane with a private current-style request loop.

---

# 72. Separate endpoint and broker coalescing

TRAFFIC-08 should NOT be inserted into:

```text
/traffic/history?products=...
```

Reason:

```text
that endpoint is AP Network Traffic / HistoricalTrafficReadService semantics.
```

TRAFFIC-08 uses its own endpoint.

Therefore v1 broker behavior:

```text
same historical execution lane

same admission guard

NO cross-endpoint coalescing with AP Network Traffic products
```

A minimal broker extension may be required to schedule a distinct historical job
descriptor.

No second scheduler.

---

# 73. Independent range state

TRAFFIC-08 receives its own:

```text
24h | 7d
```

selector.

It does not mutate:

```text
History range

Statistics range

Peak range

Traffic by AP range

AP Share range
```

Its per-panel state should follow the accepted independent historical model:

```text
selected_range

applied_range

phase

last_successful_payload

last_error

intent_generation
```

---

# 74. Refresh behavior

TRAFFIC-08 should inherit the existing historical Traffic refresh lifecycle.

No product-specific timer.

Operations:

```text
initial load

range change

Global Traffic Refresh

pagination
```

must enter the historical broker/coordinator lane.

Do not create:

```text
new setInterval

new AbortController owner

new retry scheduler
```

Whether existing scheduled global Traffic refresh includes all historical panels
should be inherited, not redefined by TRAFFIC-08.

---

# 75. Pagination vs range refresh

Cursor chain belongs to one:

```text
Site + absolute completion range + evaluated_at
```

If range changes:

```text
discard cursor chain

load new first page
```

If Global Refresh resolves a new absolute window:

```text
discard cursor chain

load new first page
```

Never append page 2 from the old completion range to a new root.

Use coordinator generation/supersession.

---

# 76. UI placement

Recommended panel order:

```text
Current Network Throughput

Online Guests Traffic

Completed Guest Session Traffic

Network Traffic History

Period Statistics

Peak Load

Traffic by AP

AP Traffic Share
```

Rationale:

```text
Online Guests Traffic = current guest view

Completed Guest Session Traffic = historical guest view

then AP/network historical products
```

Owner + Tech Lead should confirm this ordering.

---

# 77. UI table

Recommended columns:

```text
Guest

Session Start

Session End

Duration

SSID

Download

Upload

Total

Evidence
```

Optional AP context:

```text
start AP → final AP
```

may be secondary text, not a mandatory primary column.

No chart in v1.

---

# 78. Guest identity display

Without Registry enrichment:

```text
client MAC
```

is guaranteed.

Friendly `name` is not guaranteed from Visit Lifecycle.

Architect recommendation:

```text
v1 primary Guest = MAC

do not add Registry join merely for display convenience
```

A future product-layer enrichment can be reviewed separately.

---

# 79. SSID display

If:

```text
start_ssid == final_ssid
```

show one SSID.

If different:

```text
start_ssid → final_ssid
```

and Evidence may indicate:

```text
SSID transition
```

Do not silently collapse changed SSID context.

---

# 80. Duration display

Use:

```text
duration_seconds
```

from Visit Lifecycle.

Format human-readable:

```text
seconds
minutes
hours
```

Presentation only.

Never use Traffic sample span as session duration.

---

# 81. Byte formatting

Canonical API value:

```text
integer bytes
```

UI may display IEC units:

```text
B
KiB
MiB
GiB
```

Preserve exact zero/null distinction.

No floating source value in API required.

---

# 82. Null vs zero UI

Required:

```text
null
→ —
```

Never:

```text
null → 0 B
```

If a future accepted metric can prove numeric zero:

```text
0
→ 0 B
```

Until the v1 zero-proof rule is frozen, no sampled unknown-zero should be
materialized.

---

# 83. Evidence display

Recommended machine:

```text
complete
partial
insufficient_data
```

Safe UI wording:

```text
Complete sampled evidence

Partial evidence

Insufficient data
```

Evidence details can list safe reason labels:

```text
Start edge not observed

End edge not observed

Observation gap

Counter reset

Repeated authorization

SSID transition

Counter unavailable
```

Do not expose raw SQL/internal exception text.

---

# 84. Empty state

If completion cohort has zero Visits:

```text
No completed guest sessions
```

This is a proven empty historical result.

Do NOT show:

```text
Traffic unavailable
```

merely because there are no sessions.

No pagination.

---

# 85. Source unavailable

If Visit source is unavailable:

```text
status=unavailable
items=[]
```

If Observation source is unavailable while completed Visit identity can be read:

Architectural choice is important.

Recommended v1:

```text
keep completed Visit rows visible

Traffic values=null

Traffic evidence=unavailable/insufficient_data

root status=partial or unavailable-by-traffic-source
```

This preserves valid lifecycle history without inventing Traffic.

Before FINAL, define exact root status vocabulary.

Architect recommendation:

```text
root status=partial
source availability fields identify Observation unavailable
```

because Visit identity remains valid.

---

# 86. Integrity failures

Examples:

```text
cross-Site row

malformed Visit identity

closed Visit with impossible timestamps

duplicate Visit ID

impossible cursor context

invalid persisted counter shape that violates source schema
```

Required:

```text
typed integrity failure

fail closed
```

No partial repair.

Safe source absence:

```text
!=
corrupt evidence
```

---

# 87. Public Traffic failure does not affect TRAFFIC-08

Public Traffic Counter:

```text
enabled/disabled/unavailable/reset
```

must not change TRAFFIC-08 per-Visit semantics.

No dependency.

This prevents a public aggregate reset from deleting Admin historical session
Traffic evidence.

---

# 88. Observation retention limitation

Observation historical dynamic evidence is retention-bounded.

A completed Visit may exist longer than the available Observation evidence.

Therefore:

```text
Visit identity may remain available

Traffic evidence may become partial/insufficient_data
```

Do not delete/hide the Visit merely because Observation evidence aged out.

This is expected long-term behavior unless a future rollup is designed.

---

# 89. Long session limitation

A completion cohort may contain a Visit that started long before the selected
completion range.

TRAFFIC-08 must still respect:

```text
full Visit start → close attribution window
```

but read work must remain bounded.

DRAFT leaves one explicit open architecture item:

```text
maximum supported Visit duration / source-row work budget
```

Do NOT invent a duration cap without PERF evidence.

Candidate should be established by:

```text
capacity fixture
query-plan proof
existing retention
10-second query deadline
```

before FINAL.

---

# 90. Existing indexes / no new index default

Current sources already provide:

Visit:

```text
idx_visits_site_closed
(site_id, closed_at, visit_id)
```

Observation:

```text
idx_client_site_mac_time
(site_id, client_mac, observed_at, row_id)
```

DRAFT policy:

```text
NO new index initially
```

Mandatory:

```text
EXPLAIN QUERY PLAN

capacity benchmark
```

If accepted PERF cannot pass:

```text
STOP

return profile/query-plan evidence

architecture review index need
```

No speculative index.

---

# 91. Batch query work shape

Reuse existing Analytics batch design.

Expected request:

```text
1. select up to page_size completed Visits by closed_at

2. load required persisted authorization boundaries in bounded batch

3. build Visit windows

4. load Observation evidence in batch windows

5. derive per-Visit quality/Traffic

6. serialize page
```

Do NOT perform:

```text
one SQLite connection per Visit

one full Observation history scan per Visit

N query-time Omada calls
```

Existing Analytics source gateway already uses Visit-window batching.

Reuse that pattern.

---

# 92. Bounds

DRAFT product bounds:

```text
ranges:
24h | 7d

default page:
50

max page:
200

sort:
closed_at DESC, visit_id DESC
```

No full-range materialization required for sort.

Traffic computation is required only for returned completed Visit page, not every
session in the selected range.

This is a key PERF boundary.

---

# 93. Range population count

Optional root:

```text
completed_session_count
```

may be computed with the indexed closed cohort.

It does not require Traffic evaluation for every session.

If included:

```text
count is completion-cohort count
```

not:

```text
page item count
```

Do not add population-wide Traffic evidence counts in v1 unless PERF demonstrates
they are cheap enough without full Traffic evaluation.

Architect recommendation:

```text
session count yes

Traffic quality counts page-local only
```

---

# 94. Query deadline

Reuse existing Admin/Analytics deadline model.

No new query deadline setting.

Existing Analytics:

```text
max query duration = 10s
```

is the current hard semantic/backend budget.

Admin Traffic request timeout remains its own existing browser/application layer.

TRAFFIC-08 MUST NOT solve PERF problems by increasing either timeout in this TASK.

---

# 95. PERF fixture proposal

Mandatory production-compatible capacity fixtures should include:

## P50

```text
50 completed Visits
realistic Observation windows
```

## P200

```text
200 completed Visits
```

## GAPS

```text
resets
missing counters
180s+ gaps
authorization boundaries
SSID transitions
```

## LONG

```text
long-duration completed Visits
bounded by retained evidence
```

## NOOBS

```text
completed Visits with no Observation evidence
```

## MIXED

```text
complete/partial/insufficient sessions
```

Also seed substantial unrelated:

```text
Visits

Observation rows
```

to prove index use.

---

# 96. PERF target proposal

Full authenticated Admin endpoint.

DRAFT hard targets:

```text
API50:
p95 <= 2.0s
max <= 3.0s

API200:
p95 <= 4.0s
max <= 6.0s
```

At least:

```text
10 measured runs each
```

Under unchanged:

```text
10s Analytics/query deadline
```

Additional:

```text
unexpected 5xx = 0

source writes = 0

query plan PASS

no multi-retention full scan

no N+1 DB connection pattern
```

These values are DRAFT and require Owner + Tech Lead acceptance.

---

# 97. Payload budget

DRAFT acceptance budget:

```text
API200 <= 256 KiB
```

This is an acceptance/optimization gate.

Existing platform hard response-size limit remains unchanged.

Do not add a new runtime payload limit merely for TRAFFIC-08.

---

# 98. Feature-off behavior

With:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

required:

```text
panel absent

frontend historical job not registered

route 404 after normal Admin boundary

semantic service not invoked by Traffic page

existing Traffic behavior unchanged
```

---

# 99. Product runtime unavailable

If enabled but required read composition is unavailable:

```text
product state=unavailable
```

Other Admin/Traffic products stay operational.

Do not fail portal authorization.

Do not fail the entire Admin runtime solely because optional TRAFFIC-08 is
unavailable.

---

# 100. Security

Required:

```text
authenticated Admin

canonical Site

admin.read.devices
```

Every API request repeats authorization.

No cross-Site:

```text
Visit

Observation

count

cursor

quality
```

Cursor is Site-bound.

---

# 101. Privacy

Do not expose by default:

```text
client IP

raw AuthSession IDs

raw authorization records

raw Observation counters

raw source cursor

DB paths

SQL

normalized webhook body

Portal secrets
```

MAC is already an accepted Admin device identity under `admin.read.devices`.

---

# 102. Telemetry

Safe aggregate fields:

```text
product=completed_guest_session_traffic

site_id

range

status

page_limit

returned_count

has_next_page

complete_page_count

partial_page_count

insufficient_page_count

request_duration_ms

response_bytes

failure_reason

cursor_used
```

Do NOT log:

```text
MAC list

visit IDs list

Traffic values per item

raw cursor

exception text

source counters
```

---

# 103. REUSE — Visit Lifecycle

REUSE:

```text
Visit identity

started_at

closed_at

status

duration_seconds

Site + MAC

start/final SSID

start/final AP

authorization attachments

offline event linkage

reported controller total as auxiliary evidence

idx_visits_site_closed
```

No writer change.

No lifecycle semantic change.

---

# 104. REUSE — Observation

REUSE:

```text
authorized client historical samples

traffic_down

traffic_up

SSID/AP context

client observed timestamps

idx_client_site_mac_time

existing retention
```

No collector change.

No schema change.

No new stored field in DRAFT.

---

# 105. REUSE — Analytics

REUSE:

```text
AnalyticsSourceGateway

Visit-window batching

Observation coverage logic

counter delta/gap safety patterns

QueryDeadline

read-only source composition

provenance/quality style
```

Do not duplicate the whole gateway in a new Traffic module.

---

# 106. REUSE — Admin

REUSE:

```text
AdminQueryExecutionControls

authentication/session

Site policy

admin.read.devices

safe serializer patterns

response envelope

feature-gated optional product state
```

---

# 107. REUSE — Traffic frontend infrastructure

REUSE:

```text
CaptivPortalTrafficCoordinator

TrafficHistoricalRequestBroker

10-second historical admission guard

max historical in-flight=1

independent page-local range state

Global Refresh lifecycle

generation/AbortController supersession

existing Traffic error/session handling
```

---

# 108. CHANGE REQUIRED — read semantics

New semantic DTO/service:

```text
CompletedGuestSessionTrafficReadService
```

Required:

```text
closed_at completion cohort

per-session Traffic result

per-direction evidence status

session evidence reasons

cursor

bounded pagination
```

This is the main semantic change of TRAFFIC-08.

---

# 109. CHANGE REQUIRED — closed cohort query

Current generic Visit list read is start-time oriented.

TRAFFIC-08 requires a dedicated read/gateway path for:

```text
closed Visit completion cohort
```

using existing:

```text
idx_visits_site_closed
```

No schema/index change should be necessary if query plan passes.

---

# 110. CHANGE REQUIRED — per-Visit quality detail

Existing aggregate Visit Traffic Analytics is not guaranteed to expose every
per-Visit rejection reason needed by the product.

TRAFFIC-08 may require bounded extensions to existing Analytics gateway result
shape for per-Visit:

```text
gap count

reset count

missing counter count

start/end edge gaps

authorization boundary count

SSID transition count
```

This is read-only query/projection work.

It must not change source storage.

---

# 111. CHANGE REQUIRED — authorization boundaries

If existing gateway Traffic delta logic does not segment by persisted Visit
authorization timestamps:

```text
add read-only segmentation in TRAFFIC-08 semantic path
```

No Visit writer change.

No AuthSession process-state dependency.

---

# 112. CHANGE REQUIRED — Admin product

Expected product work:

```text
feature flag

runtime optional product composition

AdminQueryService method

strict serializer

Admin route

Traffic template panel

JS historical panel logic

CSS

focused tests
```

---

# 113. CHANGE REQUIRED — historical broker support

Current broker is optimized around existing AP historical product requests.

TRAFFIC-08 may need a minimal new broker concept:

```text
non-coalescible custom historical job
```

with:

```text
same lane

same guard

same priority

same lifecycle owner
```

Do NOT create another scheduler.

Exact broker API is implementation design after architecture acceptance.

---

# 114. Explicit NO-TOUCH — Current State / TRAFFIC-07

No changes to:

```text
Current State collector

Current State DB/schema

CurrentStateReadService current semantics

CurrentGuestTrafficReadService

TRAFFIC-07 API/UI/continuity

Online Guest current product
```

TRAFFIC-08 does not extend current-rate semantics.

---

# 115. Explicit NO-TOUCH — Visit writer/schema

No changes to:

```text
Visit creation

Visit authorization attachment

Visit close matching

offline grace

Visit writer arbitration

Visit schema

Visit migrations

one-open-Visit-per-Site+MAC invariant
```

unless later evidence proves a hard blocker and a separate architecture amendment
is approved.

---

# 116. Explicit NO-TOUCH — Observation acquisition/schema

No changes to:

```text
Observation collector

Omada polling

Observation DB schema

retention

existing indexes
```

by default.

If PERF or evidence proves a new index is necessary:

```text
STOP / review
```

---

# 117. Explicit NO-TOUCH — Public Traffic

No changes to:

```text
Public Traffic worker

public_traffic.sqlite3

traffic_daily

processed_events

reset semantics

public portal API
```

TRAFFIC-08 does not consume Public Traffic as canonical per-session source.

---

# 118. Explicit NO-TOUCH — Visitor Registry

No:

```text
MAC merge

device merge

identity rewrite

Registry schema
```

for v1.

Registry enrichment is deferred unless explicitly accepted.

---

# 119. Explicit NO-TOUCH — HistoricalTrafficReadService

Do not modify AP Network Traffic semantic owner to understand Visits.

Do not add session Traffic to AP historical:

```text
products=
```

projection.

Separate endpoint/service.

---

# 120. Explicit NO-TOUCH — Omada

No:

```text
query-time OpenAPI

new webhook event

new polling endpoint

new client action
```

TRAFFIC-08 reads already persisted evidence only.

---

# 121. Recommended implementation decomposition

After architecture acceptance only:

## Phase A — Session read contract

```text
immutable DTOs

validation

metric/status/reason constants

closed-cohort cursor
```

## Phase B — Existing-source gateway extension

```text
closed Visit page query

authorization boundary read

Observation per-Visit batch evidence

quality breakdown
```

## Phase C — Semantic service

```text
CompletedGuestSessionTrafficReadService

D/U/T accumulation

quality states

fail-closed invariants
```

## Phase D — Backend product

```text
feature flag

runtime composition

AdminQueryService

serializer

route
```

## Phase E — Frontend product

```text
panel

independent range

historical broker job

table

pagination

evidence display
```

## Phase F — tests/PERF

```text
focused semantic

regression

Central Lab

query-plan

Linux PERF

payload

immutability
```

No Coder task is authorized by this decomposition yet.

---

# 122. Recommended metric acceptance examples

## A — Good sampled evidence

```text
closed Visit

multiple monotonic Observation samples

no gaps > threshold

no resets

no auth/SSID interval crossing

both D/U accepted
```

Expected:

```text
D/U numeric

Total numeric

evidence complete
```

subject to the final accepted meaning of "complete sampled evidence".

## B — Start edge missing

Expected:

```text
positive accepted deltas may remain numeric lower bound

evidence partial
```

Zero accepted sum:

```text
null unless zero proof is explicitly accepted
```

## C — Counter reset mid-Visit

Expected:

```text
reset interval excluded

later valid segment may resume

evidence partial
```

## D — No usable interval

Expected:

```text
D/U/Total=null

insufficient_data
```

---

# 123. Acceptance — lifecycle/session identity

Must prove:

```text
closed Visit is session identity

open Visit excluded

same MAC sequential Visits remain separate

multiple authorizations in one Visit do not duplicate session rows

randomized MAC Visits are not merged

AP roam does not create Visit split

SSID transition does not create synthetic Visit split
```

---

# 124. Acceptance — Traffic correlation

Must prove:

```text
Site isolation

exact MAC

exact Visit window

no pre-start delta

no post-close delta

no cross-Visit delta

no cross-authorization boundary delta

no cross-SSID boundary delta

AP roam allowed
```

---

# 125. Acceptance — counter safety

Must prove:

```text
monotonic accepted deltas

counter regression rejected

missing counter remains unknown

gap > threshold rejected

no negative values

no wrap assumption

no interpolation

no AP allocation
```

---

# 126. Acceptance — null/zero

Must prove:

```text
unknown Traffic != 0

missing first/final edge != 0

insufficient_data → null

partial accepted zero does not silently become full-session zero

numeric zero appears only under an explicitly proven FINAL rule
```

---

# 127. Acceptance — source separation

Must prove:

```text
observed D/U/T remains separate from controller-reported connection Total

Public Traffic aggregate not used as per-Visit source

Current State not used as historical fallback

HistoricalTrafficReadService not used for session attribution

Registry/AuthSession not required
```

---

# 128. Acceptance — historical range

Must prove:

```text
24h/7d selects closed_at completion cohort

session that starts before range but closes inside range is included

full Visit window used for Traffic evidence

cursor pins absolute completion range

range change resets cursor chain

other Traffic panel ranges unchanged
```

---

# 129. Acceptance — broker/coordinator

Must prove:

```text
TRAFFIC-08 uses existing historical execution lane

max historical in-flight remains 1

10s historical admission guard remains effective

no second scheduler

no private retry timer

range change / Global Refresh / pagination respect generation supersession

no cross-endpoint coalescing with AP history
```

---

# 130. Acceptance — serializer/API

Must prove:

```text
Site reauthorization

admin.read.devices

exact allowed query shape

opaque cursor

integer bytes

null preserved

safe evidence allowlists

fail closed on malformed internal DTO

no raw source metadata leakage
```

---

# 131. Acceptance — performance

Mandatory:

```text
query-plan PASS

API50 PERF PASS

API200 PERF PASS

long-session/source-density fixture PASS or accepted unsupported behavior

no source writes

payload budget PASS

exact candidate tree pinned
```

No timeout increase.

No speculative index.

---

# 132. Acceptance — regressions

At least:

```text
TRAFFIC-08 focused suite

Visit Lifecycle read regression

Visit Analytics regression

Observation read/gateway regression

Traffic historical broker regression

Independent ranges regression

Current Network Throughput

History

Statistics

Peak

Traffic by AP

AP Traffic Share

Online Guests Traffic

Admin auth/Site isolation
```

Candidate regressions:

```text
0
```

Official Central Lab strict regressions:

```text
0
```

---

# 133. Deployment strategy

If/when implemented:

```text
feature default false
```

First production deploy:

```text
FROM GIT

WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

Dormant acceptance first.

Important:

```text
no new worker
no new DB
```

so dormant deployment should have no new acquisition workload.

Activation remains separate.

---

# 134. Dormant acceptance

With feature false:

```text
service active

existing Traffic healthy

Visit Lifecycle healthy

Observation healthy

Online Guests Traffic healthy

Completed Session panel absent

direct product route 404

no new product request

no source writes

no new worker

no startup/runtime regression
```

---

# 135. Activation

Only after:

```text
all mandatory gates PASS

dormant production PASS

separate Owner activation authorization
```

enable:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

No combined deploy+activation.

---

# 136. Production browser acceptance

After activation:

```text
panel visible

default 24h

range 24h → 7d → 24h

other panel ranges unchanged

recent completed sessions ordered newest-first

MAC/session timestamps/duration visible

D/U/Total values or truthful nulls

Evidence labels

Load more if applicable

empty state if applicable

no current Online panel regression

Global Refresh works

no historical concurrency/admission regression
```

Synthetic reset/gap scenarios remain Lab-owned.

---

# 137. Rollback

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

No data rollback.

No DB migration rollback expected.

No source cleanup.

Code rollback only through approved Git deploy if needed.

---

# 138. Open architectural question 1 — product name

Options:

```text
Completed Guest Session Traffic

Completed Guest Visit Traffic

Completed Visit Traffic
```

Architect recommendation:

```text
Completed Guest Session Traffic
```

for operator-facing product.

Internally use:

```text
Visit
```

as exact lifecycle identity.

---

# 139. Open architectural question 2 — "complete" naming

Is machine:

```text
complete
```

acceptable when the metric is sampled and may not cover exact boundary bytes?

Options:

```text
complete

sampled_complete

complete_sampled_evidence
```

Architect recommendation:

```text
machine = complete

public wording = Complete sampled evidence
```

provided the FINAL explicitly states this is not billing/packet-exact.

---

# 140. Open architectural question 3 — zero proof

Current persisted sources do not obviously provide exact directional anchors at
both Visit boundaries.

Architect recommendation:

```text
v1 does NOT materialize sampled zero as full-session zero
unless exact zero-proof conditions are identified before FINAL.
```

Owner + Tech Lead must freeze the exact zero rule.

---

# 141. Open architectural question 4 — auxiliary offline Total

Should UI expose:

```text
Controller-reported connection Total
```

as a separate column/detail?

Architect recommendation:

```text
NO in primary v1 table
```

Keep it as provenance/comparison only.

---

# 142. Open architectural question 5 — Registry enrichment

Should Guest display use Registry/device identity?

Architect recommendation:

```text
DEFER

MAC-only v1
```

This avoids turning a Traffic TASK into identity-merging work.

---

# 143. Open architectural question 6 — exact edge quality threshold

Existing Analytics:

```text
counter/gap threshold = 180s
```

Candidate:

```text
reuse 180s for start/end sampled coverage quality
```

But this must be reviewed.

A bounded edge threshold is a quality label, not a claim that edge bytes were
measured.

---

# 144. Open architectural question 7 — long Visit bound

Need capacity evidence before freezing:

```text
max supported Visit duration
```

Options:

```text
no explicit duration cap, deadline/profile bounded

or

explicit supported duration cap
```

Architect recommendation:

```text
benchmark first

do not invent a duration limit in DRAFT
```

---

# 145. Open architectural question 8 — root source status

If:

```text
Visit source works

Observation unavailable
```

should root be:

```text
partial
```

with Visit rows retained, or:

```text
unavailable
```

Architect recommendation:

```text
partial
```

because completed-session identity remains authoritative and only Traffic evidence
is unavailable.

Exact API status matrix must be frozen before FINAL.

---

# 146. Open architectural question 9 — broker API

Current historical broker must keep ownership.

Need choose implementation shape:

```text
registerCustomHistoricalJob(...)
```

or equivalent.

Architectural invariant:

```text
same lane/guard/lifecycle

no new scheduler
```

Exact JS method name is not architectural.

---

# 147. Open architectural question 10 — PERF limits

DRAFT targets:

```text
API50 p95<=2s max<=3s

API200 p95<=4s max<=6s
```

Need validate against:

```text
real production Visit/Observation density
```

before FINAL.

No timeout increase.

---

# 148. Decision summary — REUSE

```text
Visit identity/lifecycle

Visit close index

Visit authorization attachments

Observation authorized client counters

Observation Site+MAC+time index

Analytics batch Visit-window reads

Analytics counter/gap safety

AdminQueryExecutionControls

Admin authentication/Site/capability

Traffic coordinator

Historical request broker

10-second historical admission guard

independent panel range state
```

---

# 149. Decision summary — CHANGE REQUIRED

```text
new per-session semantic read owner

closed-at completion cohort query

per-Visit evidence quality projection

authorization/SSID segmentation if missing from existing gateway

new Admin serializer/query/route

new feature flag

new historical Traffic panel

minimal historical broker custom-job support if required

focused tests / PERF
```

---

# 150. Decision summary — NO TOUCH

```text
Current State / TRAFFIC-07-READ

TRAFFIC-07 semantics

Visit writer/schema/close matching

Observation collector/schema/index by default

Visitor Registry identity model

AuthSession semantics

Public Traffic worker/schema/aggregates

HistoricalTrafficReadService AP Network Traffic

Omada acquisition

new collector

new DB

new scheduler

existing Traffic timeouts
```

---

# 151. Proposed architecture state

```text
TASK:
TASK-TRAFFIC-08 — Completed Guest Session Traffic

STATUS:
ARCHITECTURAL DRAFT

TASK DEVELOPMENT PARENT:
main@e196b042515498c5cd9143a9962f6aed90f31566

TREE:
f88ee1f854135107c647ccd9d346be2b2ba504b9

PRODUCTION FUNCTIONAL REFERENCE:
6425988b5b4ec5ff38bf9c67c74846c3806f668f

PRODUCTION TREE:
b669f368b0062fcb100b24758cf05e2c4b500144

SESSION IDENTITY:
closed Visit / visit_id

SESSION COHORT:
closed_at in selected 24h/7d range

PRIMARY TRAFFIC SOURCE:
Observation authorized client counters

PRIMARY METRIC:
observed completed-session D/U/T bytes

SEMANTIC OWNER:
proposed CompletedGuestSessionTrafficReadService

OFFLINE REPORTED TOTAL:
auxiliary connection evidence only
NO fallback/substitution

PUBLIC TRAFFIC:
existing aggregate source
NO per-Visit canonical role

CURRENT STATE:
NO role in v1 completed history

REGISTRY:
OUT / optional future enrichment

AUTHSESSION:
NOT session identity

HISTORICAL TRAFFIC OWNER:
UNCHANGED / AP Network Traffic only

NEW COLLECTOR:
NO

NEW DB:
NO

SOURCE SCHEMA CHANGE:
NO by default

NEW INDEX:
NO by default

RANGE:
24h | 7d independent

DEFAULT RANGE:
24h

PAGE:
50 default / 200 max

SORT:
closed_at DESC, visit_id DESC

HISTORICAL BROKER:
YES / existing lane

CROSS-ENDPOINT COALESCING:
NO v1

HISTORICAL ADMISSION GUARD:
UNCHANGED

QUERY-TIME OMADA:
NO

FEATURE FLAG:
proposed WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false

ACCESS:
proposed admin.read.devices

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

CODER AUTHORIZATION:
NOT GRANTED

PUBLICATION / MERGE / DEPLOY / ACTIVATION:
NOT AUTHORIZED
```

---

# 152. Next architecture step

Owner + Tech Lead review this DRAFT.

Required review should freeze at minimum:

```text
session identity = Visit

completion cohort = closed_at

new semantic owner

observed-byte metric wording

reported-total source separation

evidence status names

zero rule

edge/gap quality rule

long-session work bound

API route/query

range/broker integration

UI placement

PERF thresholds
```

Then:

```text
corrections if required

→ repository re-fetch/rebind

→ FINAL architecture

→ separate explicit Owner implementation authorization

→ Tech Lead implementation decomposition

→ Coder
```

No implementation may begin from this DRAFT.
