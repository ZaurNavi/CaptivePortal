# TASK-VISIT-FINALIZATION-DRIFT-01 — Visit Lifecycle Offline Finalization Corrective Patch — FINAL

**Project:** CaptivPortal  
**Type:** corrective production defect / architecture + implementation specification  
**Priority:** High  
**Status:** FINAL R2 — Tech Lead focused revision incorporated / coder-ready corrective specification  
**Implementation authorization:** NOT GRANTED BY THIS DOCUMENT  
**Production activation / recovery:** separate Owner-controlled action  
**Exact verified baseline:** `origin/main@f458df3b360bba89e9965a1edfdcc0d3af2f201c`  
**Prepared:** 2026-08-27  
**Affected subsystem:** Visit Lifecycle offline matching/finalization and controlled stale-open recovery  
**Downstream affected product:** Home Activity Authorized Visits / historical Visit quality  
**Schema decision:** **NO schema migration; Visit DB remains schema v2**
**Tech Lead R2 corrections:** WAL-safe backup / explicit DB target / bounded recovery / exact Home Activity coverage config / zero-auth fail-safe

---

# 0. Executive decision

A production defect is confirmed in Visit Lifecycle offline finalization.

The current matcher uses:

```text
reported_session_started_at =
    controller_event_at - reported_connected_seconds

drift =
    abs(reported_session_started_at - visit.started_at)
```

and permanently rejects an otherwise valid offline when:

```text
drift > VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS
```

Current production setting:

```text
300 seconds
```

Production evidence shows legitimate guest offline events with drift approximately:

```text
301–370 seconds
average ≈ 336 seconds
```

The safeguard therefore systematically converts real terminal evidence into:

```text
processing_result=unmatched
reason=stale_or_ambiguous
```

and leaves Visits open for days.

## FINAL correction

`reported_connected_seconds` is **not identity / matching authority**.

After this corrective patch:

```text
reported_connected_seconds
=
reported Omada session metadata
+
diagnostic quality evidence
```

It MUST NOT by itself reject an otherwise unambiguous offline event.

The new temporal matching authority is:

```text
exact Site
+
exact MAC
+
the unique open Visit
+
the latest confirmed authorization timestamp already attached to that Visit
+
offline controller/received time rules
+
existing SSID safety rule
```

Canonical temporal boundary:

```text
match_floor_at =
MAX(
    visit.started_at,
    MAX(visit_authorizations.authorized_at for that visit)
)
```

This prevents a delayed/old offline from closing a Visit after a newer successful authorization has already been attached.

The patch does **not**:

- change Home Activity from Visit openings to AuthSession/authorization counts;
- create Visits from offline-only evidence;
- increase the drift threshold as the primary fix;
- remove Site/MAC/time/SSID safeguards;
- fabricate timestamps or durations;
- reconstruct speculative historical Visits.

Historical repair is conservative and Owner-controlled.

---

# 1. Confirmed production defect

Production baseline:

```text
main@f458df3b360bba89e9965a1edfdcc0d3af2f201c
```

Observed Home Activity symptom:

```text
Today Authorized visits = 3
```

while read-only investigation found approximately:

```text
14 successful authorization records
13 distinct MACs
3 actual Visit openings
10 authorizations reused stale open Visits
```

The stale Visits include records opened on previous days.

For all 10 investigated stale-open Visits, persisted:

```text
omada.client_offline
```

events exist.

The evidence is therefore not missing at acquisition/normalization level.

The failure chain is:

```text
real guest authorization
→ Visit opened
→ real Omada offline persisted
→ matcher evaluates reported-duration drift
→ drift > 300 s
→ unmatched / stale_or_ambiguous
→ Visit stays open
→ same MAC returns later
→ successful authorization sees existing open Visit
→ authorization is attached as reused
→ no new Visit opening
→ Home Activity truthfully undercounts openings
```

Home Activity is not the source defect.

---

# 2. Current code root cause

At the verified baseline, `VisitLifecycleService.process_journal_line()` and pending retry pass:

```text
max_reported_duration_drift_seconds
```

into repository matching.

Current `_match_offline()`:

1. resolves close timestamp using controller time or received fallback;
2. for controller-time close computes reported session start;
3. rejects when drift exceeds threshold;
4. then performs SSID safeguard;
5. otherwise closes the Visit.

The current durable result is:

```text
unmatched / stale_or_ambiguous
```

for drift failure.

The existing single-open invariant then makes the defect self-sustaining.

---

# 3. Scope of this corrective patch

## In scope

1. Replace reported-duration drift as a blocking matching rule.
2. Add latest-authorization temporal protection.
3. Preserve Site/MAC/SSID/idempotency/clock safety.
4. Preserve received-time fallback only where it is not ambiguous.
5. Add drift observability without using drift as identity authority.
6. Add deterministic, read-first controlled recovery for already persisted stale opens.
7. Preserve Home Activity metric semantics.
8. Re-baseline Home Activity Visits coverage during production rollout.
9. Add targeted regressions.
10. Keep schema v2.

## Out of scope

- Home Activity metric redesign.
- AuthSession redesign.
- Visit identity redesign.
- Observation dependency for finalization.
- Omada API changes.
- Webhook normalization changes unless a factual parser defect is separately proven.
- Current State changes.
- Analytics formula changes.
- Traffic source redesign.
- derived Visit reconstruction from Observation.
- automatic startup repair.
- synthetic timeout close.
- new Visit status such as `abandoned`.
- tenant/RBAC work.

---

# 4. Permanent invariants preserved

## 4.1 Site isolation

An offline may affect only a Visit with exact resolved:

```text
event.site_id == visit.site_id
```

No Site guessing.

## 4.2 MAC identity

Exact canonical MAC match remains required.

## 4.3 Single-open invariant

Database invariant remains:

```text
at most one open Visit per (site_id, client_mac)
```

No change to partial unique index.

## 4.4 Confirmed authorization start

A Visit is still opened only from confirmed successful authorization.

No offline-only Visit creation.

## 4.5 Idempotency

One normalized:

```text
event_id
```

is processed once.

Replay MUST NOT:

- close twice;
- create a second Visit;
- duplicate Traffic;
- rewrite start evidence.

## 4.6 Immutable opening evidence

Never change existing:

```text
start_auth_session_id
start_auth_run_number
start_final_reason
started_at
```

## 4.7 No fabricated terminal evidence

Never manufacture:

```text
controller_event_at
received_at
reported_connected_seconds
reported_traffic_total_bytes
```

No guessed close time.

## 4.8 Lifecycle duration remains lifecycle duration

For a normally or recoverably closed Visit:

```text
duration_seconds =
floor(closed_at - started_at)
```

Do not replace lifecycle duration with Omada `reported_connected_seconds`.

---

# 5. Evidence classification after correction

## 5.1 Authoritative identity evidence

Required:

```text
resolved technical site_id
canonical client_mac
unique open Visit for Site+MAC
```

## 5.2 Authoritative temporal evidence

Preferred:

```text
controller_event_at
```

Temporal lower boundary:

```text
match_floor_at =
max(
    visit.started_at,
    latest attached successful authorization.authorized_at
)
```

The latest authorization is obtained only from persisted:

```text
visit_authorizations
```

for the exact Visit.

## 5.3 Supporting / quality evidence

These fields remain useful but are not identity authority:

```text
reported_connected_seconds
client_ip
ap_mac
reported_traffic_total_bytes
```

AP mismatch is not a blocker because roaming is valid.

## 5.4 Context safeguard

SSID remains a blocking context safeguard under the existing rule:

```text
known_ssids =
    visits.start_ssid
    +
    all non-null visit_authorizations.portal_ssid
```

If:

```text
offline.ssid != null
AND known_ssids is not empty
AND offline.ssid not in known_ssids
```

then:

```text
unmatched / ssid_changed
```

No change.

---

# 6. Latest authorization boundary

For every open Visit matcher evaluation, derive:

```text
authorization_count
latest_authorized_at
```

from the exact Visit.

## 6.1 Trusted authorization evidence

Trusted matching requires:

```text
authorization_count >= 1
latest_authorized_at != NULL
```

Canonical temporal boundary:

```text
latest_authorized_at =
MAX(visit_authorizations.authorized_at)

match_floor_at =
MAX(visit.started_at, latest_authorized_at)
```

## 6.2 Zero-authorization integrity anomaly

If:

```text
authorization_count == 0
```

the Visit has lost the persisted authorization evidence required by the lifecycle contract.

This is an integrity anomaly, not a normal single-authorization Visit.

FINAL behavior:

```text
do not derive trusted match_floor_at from visit.started_at alone
do not use controller-time automatic finalization
do not use received-time fallback
do not fabricate/reconstruct missing authorization rows
```

For an otherwise normalized offline against such an open Visit:

```text
processing_result = unmatched
reason = authorization_evidence_missing
```

Emit a bounded integrity/telemetry warning.

The Visit remains open for explicit investigation/recovery policy; this corrective TASK does not guess its logical boundary.

## Why this boundary exists

Scenario:

```text
Visit A opens at 10:00
old/offline evidence exists at 10:30
bug leaves Visit A open
new successful authorization attached at 12:00
old event is replayed/retried at 12:01
```

The old event:

```text
controller_event_at = 10:30
```

is before:

```text
match_floor_at = 12:00
```

and MUST NOT close the current logical Visit state.

This protection replaces the identity role previously assigned to reported duration.

---

# 7. Forward controller-time matching policy

This section applies only after §6 proves:

```text
authorization_count >= 1
latest_authorized_at != NULL
```

A zero-authorization Visit has already failed safe as:

```text
unmatched / authorization_evidence_missing
```

When valid:

```text
controller_event_at != NULL
```

## 7.1 Normal PASS

If:

```text
controller_event_at >= match_floor_at
```

then:

```text
closed_at = controller_event_at
close_time_source = controller
```

subject to:

```text
SSID safeguard
```

`reported_connected_seconds` does not block this close.

## 7.2 Controller time before temporal boundary

If:

```text
controller_event_at < match_floor_at
```

evaluate clock-skew fallback only under §8.

Otherwise:

```text
unmatched
reason=stale_or_ambiguous
```

## 7.3 No negative/clamped intervals

Still forbidden:

```text
closed_at < started_at
clamp(closed_at, started_at)
```

---

# 8. Received-time fallback — FINAL policy

The existing received-time fallback remains supported, but is made explicitly ambiguity-aware.

## 8.1 Controller time present but slightly before boundary

Fallback may be used only when all are true:

```text
authorization_count == 1

controller_event_at >=
    match_floor_at - VISIT_LIFECYCLE_MAX_OFFLINE_CLOCK_SKEW_SECONDS

received_at != NULL
received_at >= match_floor_at
```

Then:

```text
closed_at = received_at
close_time_source = received_clock_fallback
```

## 8.2 Controller time missing

When:

```text
controller_event_at == NULL
```

received-only fallback may close automatically only when:

```text
authorization_count == 1
received_at != NULL
received_at >= match_floor_at
```

Then:

```text
closed_at = received_at
close_time_source = received_clock_fallback
```

## 8.3 Reused/multi-authorization Visit

If:

```text
authorization_count > 1
```

and controller time cannot independently place the offline:

```text
controller_event_at >= match_floor_at
```

then received time alone is insufficient to prove whether the event belongs before or after the latest authorization.

Result:

```text
unmatched
reason=stale_or_ambiguous
```

This is an intentional fail-safe restriction.

## 8.4 Zero-authorization Visit

If:

```text
authorization_count == 0
```

received fallback is forbidden.

Controller-time automatic close is also forbidden by §6.2.

Result:

```text
unmatched
reason=authorization_evidence_missing
```

This state is an integrity anomaly and MUST NOT be treated as equivalent to `authorization_count == 1`.

## 8.5 Drift under received fallback

As before:

```text
reported_connected_seconds
```

is never a reject criterion when close time is based on received time.

---

# 9. `reported_connected_seconds` — FINAL semantic decision

## 9.1 It is not matching identity

Delete the blocking rule:

```text
drift > threshold
→ unmatched
```

An otherwise valid exact Site+MAC+time+SSID event MUST close even if drift is:

```text
301 s
370 s
600 s
1800 s
```

provided the authoritative matching evidence is unambiguous.

## 9.2 It remains persisted source metadata

On close, preserve:

```text
visits.reported_connected_seconds =
    event.reported_connected_seconds
```

No recomputation.

## 9.3 Diagnostic drift

When both are valid:

```text
controller_event_at
reported_connected_seconds
```

calculate for observability:

```text
reported_session_started_at =
    controller_event_at - reported_connected_seconds

reported_start_vs_visit_start_drift_seconds =
    abs(reported_session_started_at - visit.started_at)
```

This value is diagnostic only.

## 9.4 Existing configuration key

For backward-compatible corrective scope, retain:

```text
VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS
```

and existing config parsing.

In this corrective patch its runtime role changes to:

```text
diagnostic drift warning threshold
```

It MUST NOT gate matching/finalization.

Do not require a production env migration merely to apply the defect fix.

A future config-cleanup TASK may rename/deprecate this legacy key.

---

# 10. Forward outcome state machine

## Invalid Site / malformed normalized evidence

Unchanged:

```text
invalid
```

including existing:

```text
site_unresolved
```

## No open Visit

Unchanged:

```text
pending_match / no_open_visit
```

for configured grace.

After grace:

```text
unmatched / no_open_visit
```

No reconstructed Visit.

## Open Visit + safe match

```text
closed
visit_id=<exact visit>
reason=NULL
```

## Open Visit + zero authorization evidence

```text
unmatched
reason=authorization_evidence_missing
```

No controller/received automatic close.

## Open Visit + stale temporal evidence

```text
unmatched
reason=stale_or_ambiguous
```

## Open Visit + SSID conflict

```text
unmatched
reason=ssid_changed
```

---

# 11. Atomic forward finalization

Retain one transaction:

1. event-id idempotency check;
2. exact open Visit lookup Site+MAC;
3. load authorization temporal boundary;
4. resolve close time;
5. apply SSID safeguard;
6. calculate diagnostic drift if available;
7. insert/update source event as `closed`;
8. close Visit;
9. store final context/source facts;
10. commit;
11. reader checkpoint advances under existing reader contract.

Crash/replay semantics remain unchanged.

---

# 12. Telemetry for forward matching

Add bounded product-safe engineering telemetry.

Minimum:

```text
visit.offline_duration_drift
visit.closed
visit.offline_unmatched
```

For a controller event with reported duration, make available internally:

```text
duration_drift_seconds
duration_drift_threshold_seconds
duration_drift_exceeded
close_time_source
```

When:

```text
duration_drift_exceeded=true
```

the event still closes if matching evidence is safe.

Recommended event:

```text
visit.offline_duration_drift
level=warning
```

only when threshold is exceeded.

Do not log:

- raw controller payload;
- credentials;
- tokens.

Existing Site/MAC telemetry policy remains unchanged.

---

# 13. Why `300 → 600` is NOT the fix

Changing only:

```text
300 → 600
```

remains forbidden as the corrective architecture.

Reason:

- it preserves the incorrect assumption that reported duration is identity authority;
- future normal Omada drift may exceed the new threshold again;
- threshold growth cannot prove that a delayed event belongs to the latest authorization;
- latest authorization time is a stronger direct temporal boundary.

The 300-second value may remain as diagnostic warning threshold.

---

# 14. Historical recovery — architectural goal

Forward matching alone fixes new terminal events, but production already contains stale open Visits and persisted unmatched evidence.

Recovery is required as an explicit controlled capability.

Recovery MUST be:

```text
read-first
deterministic
Site-scoped
MAC-scoped
idempotent
Owner-controlled
not automatic at startup
```

Recovery MUST NOT:

- create a synthetic offline;
- use current wall clock as `closed_at`;
- create a Visit from offline-only evidence;
- move historical authorization rows between Visits;
- rewrite immutable Visit start evidence;
- delete unmatched events;
- split one stale Visit into speculative historical Visits.

---

# 15. Historical reconstruction decision

## FINAL decision

This corrective patch **does not reconstruct historical Visit segmentation**.

Example corrupted row:

```text
Visit started 14 Aug
authorization attached 27 Aug
```

Even if an offline existed between those dates, the patch will NOT manufacture a new 27 Aug Visit retrospectively by moving that authorization.

Reason:

```text
historical physical Visit segmentation is not fully provable
from the already-corrupted combined row in all cases
```

Therefore:

```text
historical Authorized Visits before a new proven coverage boundary
remain potentially undercounted
```

This is represented by Home Activity coverage, not by invented Visits.

---

# 16. Safe recovery candidate

For one currently open Visit, recovery first derives:

```text
authorization_count
latest_authorized_at =
MAX(all attached visit_authorizations.authorized_at)
```

Recovery eligibility requires:

```text
authorization_count >= 1
latest_authorized_at != NULL
```

If:

```text
authorization_count == 0
```

the Visit is NOT recoverable by this automatic recovery contract.

Report:

```text
recovery = skipped
reason = authorization_evidence_missing
```

Recovery searches existing persisted source events only.

A candidate MUST satisfy all:

```text
event_type = omada.client_offline

processing_result = unmatched

reason = stale_or_ambiguous

event.site_id = visit.site_id

event.client_mac = visit.client_mac

event.controller_event_at IS NOT NULL

event.controller_event_at >= latest_authorized_at

event.visit_id IS NULL

event.event_id is not already used by visits.offline_event_id

SSID safeguard passes under current Visit authorization context
```

Recovery deliberately requires controller time.

It does NOT use received-only fallback.

It does NOT use reported-duration drift as a blocker.

---

# 17. Recovery candidate ordering

For each open Visit, select the earliest safe terminal controller time after its latest authorization:

```text
ORDER BY controller_event_at ASC, event_id ASC
```

Rationale:

```text
first proven terminal event after latest authorization
=
earliest safe end of current corrupted open Visit
```

Do not choose a later event merely because its reported duration is closer.

---

# 18. Same-timestamp recovery ambiguity

If more than one eligible event has the exact earliest:

```text
controller_event_at
```

compare terminal evidence fields:

```text
site_id
client_mac
controller_event_at
client_ip
ssid
ap_mac
reported_connected_seconds
reported_traffic_total_bytes
```

## Semantic duplicates

If all values above are equal:

- treat them as semantic duplicates;
- choose deterministic lowest `event_id`;
- leave other duplicate rows unchanged;
- report duplicate count.

## Conflicting same-time evidence

If any terminal field conflicts:

```text
recovery = skipped
reason = ambiguous_same_timestamp_events
```

Do not choose arbitrarily.

---

# 19. Safe recovery APPLY transaction

For each candidate, revalidate inside the write transaction:

1. Visit still exists and is `open`.
2. Exact Site/MAC unchanged.
3. Recompute latest authorization timestamp.
4. Candidate still occurs at/after latest authorization.
5. Source event is still `unmatched/stale_or_ambiguous`.
6. Source event remains unlinked.
7. SSID safeguard still passes.
8. No conflicting earliest candidate appeared.
9. Close Visit from the real event.
10. Link the same existing event.
11. Commit.

No new source-event row is inserted.

---

# 20. Recovery persisted result

For an applied recovery:

## Source event

Update processing metadata only:

```text
processing_result = closed
visit_id = recovered visit_id
reason = NULL
processed_at = recovery execution time
last_match_attempt_at = recovery execution time
```

Preserve original evidence fields unchanged:

```text
event_id
event_type
site_id
client_mac
controller_event_at
received_at
client_ip
ssid
ap_mac
reported_connected_seconds
reported_traffic_total_bytes
source_identity
source offsets
first_processed_at
```

## Visit

Set:

```text
status = closed
closed_at = event.controller_event_at
close_reason = omada_client_offline_recovered
close_time_source = controller

final_ip = event.client_ip
final_ssid = event.ssid
final_ap_mac = event.ap_mac

reported_connected_seconds =
    event.reported_connected_seconds

reported_traffic_total_bytes =
    event.reported_traffic_total_bytes

reported_traffic_up_bytes = NULL
reported_traffic_down_bytes = NULL

duration_seconds =
    floor(closed_at - original visit.started_at)

offline_event_id = event.event_id
```

The separate close reason makes recovery persistently auditable without schema change.

---

# 21. Recovery rows that cannot be proven safe

If no candidate satisfies the full contract:

```text
DO NOT close
DO NOT fabricate
DO NOT delete
DO NOT reparent authorization evidence
```

Leave:

```text
Visit.status = open
```

and report a recovery skip reason.

Minimum report reasons:

```text
no_safe_offline_after_latest_authorization
ssid_conflict
ambiguous_same_timestamp_events
source_event_already_linked
visit_changed
```

These rows remain known integrity anomalies.

---

# 22. Recovery execution interface

Implement a bounded one-shot recovery interface.

Preferred module:

```text
app/visit_lifecycle/recovery.py
```

## 22.1 Mandatory DB target

For every dry-run/apply invocation:

```text
--db-path <absolute-path>
```

is mandatory.

The recovery tool MUST NOT obtain the mutation target from an implicit production default.

Examples:

```bash
python -m app.visit_lifecycle.recovery \
  --db-path /opt/CaptivePortal/data/visits.sqlite3 \
  --site-id <canonical-site-id> \
  --limit 500 \
  --dry-run
```

Apply is explicit:

```bash
python -m app.visit_lifecycle.recovery \
  --db-path /opt/CaptivePortal/data/visits.sqlite3 \
  --site-id <canonical-site-id> \
  --limit 500 \
  --apply
```

DB-path contract:

```text
absolute path required
resolve path before open
resolved path must already exist
resolved path must be a regular file
no SQLite auto-create
dry-run opens source with SQLite URI mode=ro
apply opens source with SQLite URI mode=rw
PRAGMA user_version MUST equal 2
required Visit schema objects MUST validate before any action
missing DB = hard fail
wrong/non-Visit DB = hard fail
wrong schema version = hard fail
```

Before performing the selected action the tool prints/returns:

```text
resolved_db_path
schema_version
mode
site_id
limit
```

No secrets.

## 22.2 Exact recovery bound

CLI option:

```text
--limit
```

Contract:

```text
default = 500
minimum = 1
maximum = 5000
```

`--limit` bounds the number of **open Visit rows examined** in one dry-run/apply invocation.

Canonical Visit-page ordering:

```sql
WHERE site_id = ?
  AND status = 'open'
ORDER BY started_at ASC, visit_id ASC
LIMIT <limit + 1>
```

The extra row is look-ahead only and is not evaluated/mutated in the current page.

Therefore:

```text
examined_count <= limit
truncated = true
```

iff the look-ahead row exists.

## 22.3 Deterministic continuation

Optional continuation arguments:

```text
--after-started-at <canonical UTC>
--after-visit-id <canonical UUID>
```

They MUST be supplied together or not at all.

Continuation query adds:

```sql
AND (
    started_at > ?
    OR (started_at = ? AND visit_id > ?)
)
```

using the same ascending ordering.

When `truncated=true`, output:

```text
next_after_started_at = started_at of last examined Visit
next_after_visit_id = visit_id of last examined Visit
```

When `truncated=false`:

```text
next_after_started_at = null
next_after_visit_id = null
```

`remaining_open_visit_count` means the exact number of still-open Visit rows for the same Site **strictly after the last examined key** at the time of that invocation.

It may include both recoverable and unrecoverable rows.

It MUST NOT be presented as `remaining_recoverable_count`.

Canonical output semantics:

```text
examined_count
truncated
remaining_open_visit_count
next_after_started_at
next_after_visit_id
```

This makes repeated bounded pages deterministic and prevents an unrecoverable oldest Visit from causing an endless first-page loop.

## 22.4 Modes

Rules:

```text
default action = dry-run
Site ID required for dry-run/apply
no all-sites implicit mutation
safe structured summary
non-zero exit on source/schema/storage/validation failure
```

No Omada call.

No web/API mutation route.

No automatic startup execution.

---

# 23. Recovery dry-run contract

Dry-run is read-only.

It returns at minimum:

```text
resolved_db_path
schema_version
site_id
evaluated_at
limit
examined_count
open_visit_count
recoverable_count
unrecoverable_count
semantic_duplicate_count
truncated
remaining_open_visit_count
next_after_started_at
next_after_visit_id
candidate list
skip-reason counts
```

Per candidate may expose internal operator-safe:

```text
visit_id
client_mac
started_at
latest_authorized_at
event_id
controller_event_at
legacy_processing_result
legacy_reason
reported_duration_drift_seconds
```

No secrets.

Dry-run MUST NOT change:

```text
visits
visit_authorizations
visit_source_events
visit_reader_state
PRAGMA user_version
```

---

# 24. Recovery apply operational safety

Production APPLY is Owner-controlled.

## 24.1 WAL-safe order

Required FINAL order:

1. run bounded dry-run page(s) with explicit `--db-path`;
2. record/review candidate and skip results;
3. stop `captive-portal.service`;
4. verify the service is inactive before backup;
5. create a **consistent SQLite backup** from the stopped source DB;
6. verify backup `PRAGMA quick_check` returns exactly `ok`;
7. verify backup `PRAGMA user_version` equals source version `2`;
8. run recovery `--apply` against the same explicit resolved source DB path;
9. run post-recovery read-only DB verification;
10. start `captive-portal.service`;
11. verify service/runtime and forward behavior.

A raw filesystem copy of a live WAL-mode database before stopping the writer is NOT an approved backup mechanism.

## 24.2 Canonical backup mechanism

The recovery module MUST expose a backup operation using Python stdlib SQLite Backup API:

```text
sqlite3.Connection.backup()
```

Operator form:

```bash
python -m app.visit_lifecycle.recovery \
  --db-path /opt/CaptivePortal/data/visits.sqlite3 \
  --backup-to /absolute/backup/path/visits-pre-recovery.sqlite3
```

Backup-mode rules:

```text
--db-path absolute/existing source required
--backup-to absolute path required
backup destination MUST NOT already exist
source opened without auto-create
source schema validated before backup
destination created only by the backup operation
backup verified read-only after completion
PRAGMA quick_check result MUST be exactly: ok
PRAGMA user_version MUST be: 2
verification failure = non-zero exit / APPLY blocked operationally
```

The tool prints/returns:

```text
resolved_db_path
resolved_backup_path
source_schema_version
backup_schema_version
quick_check
```

The service-inactive check remains an Owner/operator rollout gate; the recovery tool must not silently assume the writer is stopped.

Reason:

```text
no concurrent Visit writer
+
WAL-safe consistent backup
+
deterministic stable evidence snapshot
+
simpler forensic rollback
```

Dry-run may execute while the service is active because it is read-only.

No manual SQL edits are part of the approved recovery.

---

# 25. Recovery idempotency

Repeated dry-run:

```text
no changes
```

Repeated APPLY after a successful apply:

- already closed Visit is not a candidate;
- already linked event is not reused;
- no second mutation occurs.

Result is a no-op for already recovered rows.

---

# 26. DB / schema decision

## FINAL

```text
Visit DB schema remains version 2.
No migration.
No new table.
No new column.
No new index required by this task.
```

Reasons:

- required authorization timestamps already exist;
- source evidence already exists;
- `processing_result='closed'` already exists;
- `visits.close_reason` accepts recovery reason;
- `offline_event_id` / source-event `visit_id` already support linkage.

Schema/user_version regression tests are mandatory.

---

# 27. Home Activity — no metric change

Keep:

```text
Authorized Visits
=
verified Visit-opening authorizations
```

Do NOT change to:

```text
all authorization records
AuthSession count
unique MAC count
```

This defect is in Visit Lifecycle source state.

After a correct close:

```text
later successful authorization
→ no open Visit exists
→ a new Visit opens naturally
→ Home Activity increments naturally
```

No Home Activity workaround.

---

# 28. Historical Visits coverage — required correction

The previously proven Visits coverage boundary can no longer be treated as fully trustworthy for Visit openings after discovery of this defect.

Reason:

```text
successful authorizations inside the previously covered interval
were sometimes attached to stale Visits opened before the interval
```

Therefore production rollout MUST re-baseline:

```text
Home Activity visits_coverage_from_utc
```

without changing Home Activity code semantics.

## Production coverage procedure

The real configuration authority is:

```text
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON
```

For the **affected Site only**, update exactly:

```text
visits_coverage_from_utc
```

to:

```json
null
```

while preserving that Site's existing:

```text
timezone
traffic_coverage_from_utc
```

and preserving every other Site entry unchanged.

Canonical shape is the existing Site-context object; only one field changes.

Illustrative example when Traffic coverage is currently non-null:

```json
{
  "<affected-site-id>": {
    "timezone": "<preserve-existing-timezone>",
    "visits_coverage_from_utc": null,
    "traffic_coverage_from_utc": "2026-08-26T17:46:55.982Z"
  }
}
```

If the existing `traffic_coverage_from_utc` is JSON `null`, it remains JSON `null`.
The value MUST be preserved exactly; it is not replaced by a placeholder/string literal.

The object contract remains exactly the existing three keys:

```text
timezone
visits_coverage_from_utc
traffic_coverage_from_utc
```

Do NOT introduce a new standalone Visits coverage environment variable.

Do NOT replace the entire Site context JSON with a partial object that drops unrelated Site entries.

Until a new safe forward boundary is proven:

```text
affected Site visits_coverage_from_utc = null
```

Do NOT change `traffic_coverage_from_utc` as part of this defect unless separate Traffic evidence requires it.

## New proven Visits boundary

A new non-null Visits coverage boundary may be established only after:

1. corrected matcher is deployed;
2. controlled recovery has been applied or explicitly skipped for unsafe rows;
3. pre-fix stale open Visit population is proven no longer capable of absorbing new authorizations for the selected Site;
4. forward real-world authorization → offline → later authorization sequence passes.

If unresolved pre-fix stale open Visits remain capable of receiving new authorizations:

```text
visits_coverage_from_utc remains null
```

Do not claim Complete.

This is intentionally conservative.

---

# 29. Historical undercount decision

The corrective patch does not retroactively make already reused authorization records into Visit openings.

Therefore:

```text
historical periods affected by stale reuse
may remain undercounted
```

This is accepted as unrecoverable historical precision unless a future separately approved historical reconstruction task proves safe segmentation.

Do not manipulate Home Activity to hide that fact.

---

# 30. Traffic implications

Home Activity Traffic uses persisted offline source evidence and may include eligible:

```text
closed
unmatched
```

terminal events under its existing dedup/quality contract.

Recovery changes one existing event from:

```text
unmatched → closed
```

It MUST NOT create another traffic event.

Required invariant:

```text
same persisted event_id
same terminal source evidence
same semantic fingerprint
→ no Traffic double count
```

Recovery MUST NOT modify:

```text
controller_event_at
reported_traffic_total_bytes
SSID
MAC
Site
```

Home Activity Traffic code should require no semantic change.

Targeted regression must compare the same Activity interval before/after recovery and prove:

```text
traffic_bytes unchanged
eligible semantic event count remains logically deduplicated
no duplicate Traffic contribution
```

If current implementation behavior contradicts this, STOP and return evidence before altering Home Activity.

---

# 31. Visit Analytics implications

Recovered stale Visits may have a long lifecycle duration because their original `started_at` predates the safe recovered terminal event.

This is not rewritten.

They are distinguishable by:

```text
close_reason = omada_client_offline_recovered
```

This corrective task does NOT change Visit Analytics formulas.

Do not silently substitute reported connected seconds as lifecycle duration.

Historical interpretation of recovered rows must preserve the recovery close reason.

---

# 32. Fail-open / fail-safe behavior

## Portal/Auth

Any Visit finalization/recovery implementation failure remains fail-open relative to guest authorization.

Do not fail portal authorization because Visit tracking cannot write.

## Forward finalization

If source DB/write fails:

- preserve existing reader replay/checkpoint safety;
- do not fabricate closed state.

## Recovery

If any candidate is ambiguous:

```text
skip
```

not best-effort close.

If storage transaction fails:

```text
rollback candidate
```

No partial Visit/event link.

---

# 33. Implementation surface

Expected focused implementation area:

```text
app/visit_lifecycle/models.py
app/visit_lifecycle/repository.py
app/visit_lifecycle/service.py
app/visit_lifecycle/recovery.py        # new
```

Optional only if required for existing config/telemetry plumbing:

```text
app/visit_lifecycle/config.py
app/visit_lifecycle/telemetry.py
```

Tests:

```text
tests/visit_lifecycle/test_webhook_finalization.py
tests/visit_lifecycle/test_recovery.py             # new preferred
tests/visit_lifecycle/** focused repository/runtime tests
tests/analytics/test_home_activity.py               # regression only
```

Production/site config is an Owner rollout action, not hardcoded in code.

---

# 34. Forbidden implementation scope

Do not modify unless current facts prove a direct blocker and Tech Lead approves impact:

```text
app/auth/**
app/capport/**
app/current_state/**
app/observations/**
app/integrations/omada provider/client control
Visitor Registry schema
Snapshot schema
Home frontend
Admin API
Home Activity metric implementation
Traffic formulas
Grafana/Loki/Alloy
systemd unit definitions
Nginx
```

No new external dependency.

---

# 35. Existing configuration compatibility

Keep production-safe configuration compatible.

Existing:

```text
VISIT_LIFECYCLE_MAX_OFFLINE_CLOCK_SKEW_SECONDS
VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS
```

remain parseable.

Only the semantic role of reported-duration drift changes:

```text
blocking matcher threshold
→
diagnostic warning threshold
```

No production requirement to change:

```text
300
```

for the code fix to work.

---

# 36. Required targeted tests — forward matching

At minimum:

1. Normal exact Site+MAC controller-time offline closes.
2. Production-like drift `301 s` closes when evidence is otherwise safe.
3. Production-like drift `327 s` closes.
4. Production-like drift `344 s` closes.
5. Production-like drift `370 s` closes.
6. Very large reported-duration drift does not alone reject a safe controller event.
7. Drift threshold exceed emits diagnostic telemetry.
8. Reported duration is persisted unchanged.
9. Lifecycle duration remains `closed_at - started_at`.
10. Same MAC other Site is untouched.
11. Other MAC is untouched.
12. SSID mismatch remains `unmatched/ssid_changed`.
13. AP mismatch remains allowed.
14. Duplicate event remains idempotent.
15. No open Visit still uses persistent `pending_match`.
16. Pending retry uses same corrected matcher.
17. Grace expiry still becomes `unmatched/no_open_visit`.
18. No offline-only Visit reconstruction.

---

# 37. Required targeted tests — latest authorization safety

19. One opening authorization:
    `match_floor_at == started_at`.

20. Multiple attached authorizations:
    `match_floor_at == latest authorized_at`.

21. Offline controller time after latest authorization closes.

22. Offline controller time before latest authorization does not close.

23. Old offline replayed after a newer authorization cannot close current Visit.

24. High reported-duration drift cannot override the latest-auth temporal boundary.

25. A newer successful authorization is not ignored merely because the Visit originally started earlier.

26. Reauthorization after a legitimately closed Visit creates a new Visit.

27. Successful authorization while a genuinely still-open Visit has no terminal evidence preserves current reuse behavior.

---

# 38. Required targeted tests — received fallback

28. Single-authorization Visit with controller clock within allowed skew and valid received time preserves `received_clock_fallback`.

29. Single-authorization Visit with missing controller time and valid received time preserves fallback.

30. Multi-authorization Visit with controller before latest auth does NOT close from received fallback.

31. Multi-authorization Visit with missing controller time does NOT close from received-only evidence.

32. Invalid reverse interval is never clamped.

---

# 39. Required targeted tests — recovery dry-run

33. Dry-run is read-only.
34. Dry-run selects only open Visits.
35. Candidate must be `unmatched/stale_or_ambiguous`.
36. Candidate must have exact Site+MAC.
37. Candidate controller time must be at/after latest authorization.
38. Earlier unmatched events before latest authorization are ignored.
39. `no_open_visit` historical rows are not automatically promoted by this corrective recovery.
40. `ssid_changed` historical rows are not recovered.
41. Already linked events are excluded.
42. Earliest safe candidate is selected.
43. Semantic duplicate same-time events resolve deterministically.
44. Conflicting same-time events are skipped as ambiguous.

---

# 40. Required targeted tests — recovery APPLY

45. APPLY closes using real controller timestamp.
46. APPLY sets `close_reason=omada_client_offline_recovered`.
47. APPLY keeps `close_time_source=controller`.
48. APPLY preserves source evidence fields byte-for-byte/logically unchanged.
49. APPLY updates only source processing metadata/linkage.
50. APPLY never moves `visit_authorizations`.
51. APPLY never creates a new historical Visit.
52. APPLY never rewrites immutable opening evidence.
53. APPLY is idempotent.
54. Second APPLY is a no-op.
55. Candidate revalidated inside transaction.
56. Changed/closed Visit is skipped safely.
57. Storage failure rolls back event and Visit together.
58. Unrecoverable Visit remains open.
59. Schema user_version stays `2`.

---

# 41. Required downstream regressions

60. Home Activity Authorized Visits semantics unchanged.
61. Existing reused historical authorization does not become a fabricated opening.
62. After safe close, next real/fixture authorization opens a new Visit.
63. Home Activity then counts that new opening.
64. Traffic bytes for a recovered event are unchanged before/after reclassification.
65. No Traffic double counting.
66. Visit Analytics can still read recovered close reason.
67. Existing read service/cursor behavior unchanged.

---

# 42. Existing stale-safety tests

Do NOT simply delete current tests asserting stale-event safety.

Tests based solely on:

```text
reported duration drift > threshold
→ reject
```

must be replaced because that specific semantic is defective.

Equivalent safety must be preserved through tests for:

```text
event before latest authorization
event before current Visit
wrong Site
wrong MAC
SSID conflict
ambiguous received fallback
duplicate event
```

---

# 42A. Required Tech Lead hardening regressions

In addition to the existing test matrix, add explicit tests for the focused R2 corrections.

## A. Zero-authorization integrity

68. Open Visit with `authorization_count=0` + controller time after `visit.started_at` does NOT auto-close.
69. The same event becomes `unmatched/authorization_evidence_missing`.
70. Zero-auth Visit never uses received fallback.
71. Zero-auth Visit is excluded from automatic historical recovery.
72. Missing authorization evidence emits bounded integrity telemetry.

## B. Explicit DB target

73. Dry-run rejects missing `--db-path`.
74. Apply rejects missing `--db-path`.
75. Relative DB path is rejected.
76. Missing DB file hard-fails and is not created.
77. Wrong/non-Visit SQLite DB hard-fails.
78. `user_version != 2` hard-fails.
79. Resolved DB path and schema version are reported.
80. Dry-run source is opened read-only.
81. Apply uses existing `mode=rw` semantics without auto-create.

## C. Bounded recovery

82. `--limit` default is exactly `500`.
83. `--limit=1` accepted.
84. `--limit=5000` accepted.
85. `--limit=0` rejected.
86. `--limit=5001` rejected.
87. Ordering is exactly `started_at ASC, visit_id ASC`.
88. At most `limit` open Visits are examined.
89. Look-ahead row sets `truncated=true` without being evaluated.
90. Continuation arguments must be supplied as a pair.
91. Keyset continuation neither repeats nor skips an unchanged open Visit.
92. `remaining_open_visit_count` counts open rows after the last examined key, not recoverable rows.
93. Unrecoverable oldest rows do not cause an endless first-page loop.

## D. WAL-safe backup

94. Backup mode uses SQLite Backup API, not raw file copy.
95. Existing backup destination is rejected.
96. Backup source must exist and validate as schema v2.
97. Backup `PRAGMA quick_check` must return exactly `ok`.
98. Backup `PRAGMA user_version` must equal `2`.
99. Backup verification failure produces non-zero result.
100. Backup operation does not mutate source DB.

## E. Home Activity coverage configuration

101. Rollout config mutation changes only affected Site `visits_coverage_from_utc`.
102. Existing affected-Site `timezone` is preserved.
103. Existing affected-Site `traffic_coverage_from_utc` is preserved.
104. Other Site entries are preserved.
105. No standalone Visits coverage config variable is introduced.

---

# 43. Coder verification responsibility

Coder runs targeted/module regression only.

At minimum:

```text
Visit Lifecycle finalization tests
Visit Lifecycle repository tests
Visit Lifecycle runtime/reader tests
new recovery tests
Auth/Visit integration touching start/reuse
Home Activity targeted regressions
relevant Visit Analytics regressions
compileall
git diff --check
```

Record exact:

```text
baseline SHA
candidate SHA
Python version
passed
skipped
failed
```

Official full repository regression remains Central Lab responsibility on the exact candidate artifact.

---

# 44. Performance / boundedness

Forward matching adds only bounded metadata lookup for authorization evidence of one exact Visit.

Preferred query:

```text
SELECT COUNT(*), MAX(authorized_at)
FROM visit_authorizations
WHERE visit_id=?
```

Existing index:

```text
idx_visit_auth_visit_time
```

must be used/confirmed.

Recovery is one-shot and bounded by the exact §22 contract:

```text
--limit default 500
min 1
max 5000
open Visit ordering = started_at ASC, visit_id ASC
keyset continuation = --after-started-at + --after-visit-id
```

Do not scan unbounded full source history per HTTP/authorization request.

Recovery dry-run/apply evaluates at most `--limit` open Visit rows per invocation and may continue deterministically through explicit keyset pages.

Provide query-plan evidence for new forward authorization-boundary lookup.

---

# 45. Branch / baseline contract

Before implementation:

```bash
git fetch origin
git rev-parse origin/main
git status --short
```

Expected baseline at this specification:

```text
f458df3b360bba89e9965a1edfdcc0d3af2f201c
```

If `origin/main` is newer:

- pin exact new SHA;
- compare changes;
- if Visit Lifecycle / Home Activity / AuthWorker / webhook normalization changed, return Tech Lead impact review before coding.

Recommended branch:

```text
fix/visit-finalization-drift-v1
```

---

# 46. Production rollout — forward fix

Production actions are separate Owner authorization.

Before recovery mutation:

1. preserve current evidence;
2. do not manually edit Visit DB;
3. do not change drift threshold as workaround;
4. capture stale-open/unmatched baseline counts;
5. do NOT take an ad-hoc filesystem copy of the live WAL DB.

Deploy the corrected exact Central-Lab-approved artifact under the Owner-controlled deployment procedure.

The consistent pre-APPLY recovery backup is created only after service stop, exactly as §24/§47 require.

---

# 47. Production rollout — controlled recovery

FINAL order:

1. deploy the approved recovery-capable artifact;
2. run bounded `--dry-run` page(s) with mandatory explicit `--db-path`;
3. review candidate/unrecoverable/truncation/remaining results;
4. stop `captive-portal.service`;
5. verify `captive-portal.service` is inactive;
6. create the final consistent SQLite backup using the §24 SQLite Backup API operation;
7. verify backup `quick_check=ok` and `user_version=2`;
8. run bounded `--apply` page(s) against the same resolved `--db-path`;
9. verify DB invariants read-only after APPLY;
10. start `captive-portal.service`;
11. verify service/runtime;
12. perform forward physical acceptance.

If multiple bounded pages are required, use only the deterministic continuation keys returned by the preceding invocation.

No manual SQL.
No live-WAL raw filesystem backup.

---

# 48. Production Home Activity coverage action

At corrective rollout, edit only the affected Site entry inside:

```text
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON
```

Set:

```text
visits_coverage_from_utc = null
```

for that Site only.

Preserve exactly:

```text
timezone = existing value
traffic_coverage_from_utc = existing value
all other Site entries = unchanged
```

This is not a Home Activity code defect.

Traffic coverage remains independent.

Do not claim Visits `Complete` over the known-corrupted interval.

---

# 49. Production acceptance — physical forward sequence

Use a safe test guest/device.

Required sequence:

```text
successful authorization A
→ new Visit opens
→ real omada.client_offline E
→ E closes Visit
→ reported duration drift may exceed 300 and MUST NOT block close
→ successful authorization B after E
→ NEW Visit opens
```

Verify persisted:

```text
Visit A = closed
offline_event_id = E.event_id
close_time_source = controller or accepted single-auth fallback
Visit B.visit_id != Visit A.visit_id
Visit B.started_at = authorization B time
```

---

# 50. Production acceptance — stale accumulation

After deployment observation window:

- no new multi-day open Visit with a safe corresponding offline after latest authorization;
- no systematic `stale_or_ambiguous` caused solely by reported-duration drift;
- drift warnings may exist;
- legitimate `stale_or_ambiguous` remains for temporal ambiguity.

---

# 51. Production acceptance — recovery

Record:

```text
resolved_db_path
schema_version
limit
dry_run_open_visit_count
examined_count
recoverable_count
unrecoverable_count
applied_count
skipped_count
semantic_duplicate_count
truncated
remaining_open_visit_count
next_after_started_at
next_after_visit_id
backup_path
backup_quick_check
backup_user_version
```

After APPLY:

- every applied Visit is closed;
- every applied source event is linked once;
- no authorization row moved;
- no source evidence rewritten;
- no duplicate event inserted;
- schema v2 unchanged;
- unrecoverable rows remain untouched.

---

# 52. Production acceptance — Home Activity

After forward fix:

```text
real return after a legitimately closed Visit
→ creates new Visit
→ Authorized visits increases according to existing contract
```

Do not use all authorization records as expected count.

Historical pre-boundary undercount is accepted as partial/unproven, not repaired by UI math.

---

# 53. New Visits coverage proof

A new `visits_coverage_from_utc` may be established only after:

```text
correct matcher active
+
no pre-fix stale open can absorb a future authorization
+
physical forward acceptance PASS
```

Then record exact UTC boundary through existing Owner-controlled Home Activity configuration.

Until then:

```text
Visits coverage start = null
```

---

# 54. Rollback

## Code rollback

Code can be rolled back to prior runtime because:

```text
DB schema remains v2
no new required column/table/index
```

However rolling back code reintroduces defective drift-blocking semantics and is emergency-only.

## Recovery data

Do NOT reopen successfully recovered Visits merely because code is rolled back.

Recovery linked real persisted offline evidence; it is not synthetic data.

Backup remains the emergency forensic rollback point, not routine reverse migration.

## Coverage

Do not restore the disproven old Visits coverage boundary merely because code is rolled back.

---

# 55. Explicit non-goals

This TASK does NOT:

- prove exact historical headcount;
- rebuild every physical Visit since first deployment;
- infer Visit boundaries from traffic volume;
- infer Visit boundaries from Observation gaps;
- infer Visit boundaries from AP changes;
- treat reported connected seconds as exact duration;
- use current Omada state to repair history;
- close Visits at arbitrary timeout;
- add `abandoned` Visit status;
- change Visit DB schema;
- change Home Activity formula;
- change Traffic attribution;
- add an Admin recovery button;
- add recurring auto-repair worker.

---

# 56. Acceptance criteria

Implementation is ready for Tech Lead review when all are true:

1. Exact baseline pinned.
2. Reported-duration drift no longer blocks otherwise safe close.
3. Latest authorization time is part of temporal matching boundary.
4. Old event before latest authorization cannot close current Visit.
5. Site/MAC/SSID safeguards preserved.
6. Received fallback is ambiguity-aware.
7. AP mismatch remains non-blocking.
8. Drift remains persisted/observable source quality.
9. Existing config remains compatible.
10. No schema migration.
11. No new Omada call.
12. No Observation dependency.
13. Forward finalization remains atomic/idempotent.
14. Recovery defaults to dry-run.
15. Recovery APPLY is explicit and Site-scoped.
16. Recovery uses persisted controller-time evidence only.
17. Recovery uses earliest safe offline after latest authorization.
18. Historical authorization rows are never moved.
19. Historical Visits are not speculatively split.
20. Recovery close reason is auditable.
21. Unrecoverable rows are left untouched.
22. Home Activity Authorized Visits semantics unchanged.
23. Traffic does not double-count after event relinking.
24. Targeted regressions pass.
25. `compileall` passes.
26. `git diff --check` passes.
27. Working tree is clean.
28. Zero-authorization Visit fails safe and cannot auto-finalize.
29. Recovery requires explicit existing absolute `--db-path`.
30. Recovery `--limit` is exactly bounded by the §22 contract.
31. Production backup mechanism is SQLite Backup API after service stop.
32. Backup `quick_check=ok` and `user_version=2` are mandatory before APPLY.
33. Home Activity coverage mutation targets only affected Site `visits_coverage_from_utc` inside `WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON`.
34. Candidate is ready for Central Lab exact-artifact full regression.

---

# 57. Required coder handoff

Return:

```text
BASELINE
origin_main=<SHA>

BRANCH
<name>

COMMIT
<SHA>
<message>

ROOT CAUSE
confirmed / no new root-cause assumption

ARCHITECTURE
latest authorization temporal boundary implemented
reported duration drift blocking removed
received fallback ambiguity guard implemented
schema unchanged

RECOVERY
dry-run interface
apply interface
explicit resolved db_path
limit/default/min/max
ordering/continuation semantics
candidate algorithm
idempotency evidence
truncated/remaining evidence

BACKUP
mechanism=sqlite3.Connection.backup
backup_path=<absolute path used in acceptance rehearsal or test fixture>
quick_check=ok
source_user_version=2
backup_user_version=2

HOME_ACTIVITY_COVERAGE
config_key=WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON
affected_site=<site>
visits_coverage_from_utc action documented
timezone preserved
traffic_coverage_from_utc preserved
other Site entries preserved

FILES CHANGED

TEST COMMANDS

TEST RESULTS

QUERY PLAN
latest authorization lookup

SCHEMA
before user_version=2
after user_version=2

HOME ACTIVITY
Authorized Visits semantics changed: NO
Traffic semantics changed: NO

PROVIDER
Omada calls added: NO

REPOSITORY ACTIONS
Push: NO unless separately authorized
PR: NO unless separately authorized
Merge: NO
Deploy: NO

WORKING TREE
clean
```

---

# 58. Stop conditions

Coder MUST stop and return evidence if implementation requires any of:

- Visit schema v3;
- moving historical authorization rows between Visits;
- synthetic close timestamps;
- Observation-derived Visit reconstruction;
- Omada request from Visit recovery;
- Home Activity formula change;
- Traffic formula/dedup redesign;
- weakening Site/MAC identity;
- removing event idempotency;
- disabling SSID safeguard;
- automatic destructive recovery at startup.

Those require a new architecture review.

---

# 59. Final architectural statement

The defect exists because the old matching contract asked:

```text
“Does Omada's reported connected duration reproduce
our Visit opening timestamp within N seconds?”
```

That is not a reliable identity question.

The corrected contract asks:

```text
“Is this a terminal offline event for this exact Site+MAC,
and does its authoritative event time occur after the latest
confirmed authorization that belongs to the currently open Visit?”
```

That evidence is directly tied to the logical Visit state.

`reported_connected_seconds` remains valuable operational evidence,
but it no longer has authority to keep a real Visit permanently open.
