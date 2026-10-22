# TASK-DTI-NI-04-ATTRIBUTION-RECOVERY — IMPLEMENTATION CONTRACT v1

**Role:** Tech Lead → Coder  
**Date:** 2026-10-13  
**Priority:** P1  
**Architecture authority:** `TASK-DTI-NI-04 — ATTRIBUTION RECOVERY / ARCHITECTURE CONTRACT v1` (reproduced verbatim in Annex A).  
**Frozen baseline:** HEAD `5c7b4c46afa5a57d55fe044c4326da3a10b9e145`, TREE `dec318cf1f813214d0879377180b095e843bb05c`.  
**Contract status:** COMPLETE / READY FOR OWNER AUTHORIZATION. **Implementation authorization: NO. Coder: HOLD. Production change: NO.**

## 0. Execution gate

This is the single comprehensive implementation assignment. **Do not start coding or alter production until Owner/Tech Lead explicitly changes `IMPLEMENTATION_AUTHORIZATION` to YES and releases `CODER = HOLD`.** The current request authorizes drafting the task, not bypassing the architect's explicit implementation gate. Once released, work in an isolated branch/worktree from the exact baseline; do not implement against a different HEAD without Tech Lead re-baselining. No direct production edits, restarts, systemd actions, database writes, or migrations as part of coding.

## 1. Required outcome

Fix semantic overreach: global NI-02B `attribution_unavailable` caused by pending observations must not veto independently verified, authoritative, device-bound NI-04 Service facts. Distinguish **global pipeline health**, **fact trust**, and **device-scoped coverage**. Continue to expose partial/unknown/unavailable coverage honestly, never infer negative activity claims from missing recognition. The frozen architecture in Annex A is normative and takes precedence over implementation convenience.

## 2. Exact change boundary

Allowed production code paths only:

- `app/network_metadata_projection/repository.py`
- `app/network_metadata_projection/service.py`
- `app/network_metadata_projection/recognition_read_service.py`
- `app/network_service_recognition/read_service.py`
- `app/network_service_recognition/models.py`
- `app/network_service_recognition/serialization.py`
- `app/admin_web/routes.py` (response wiring only)
- `app/admin_web/static/admin.js`
- directly related deterministic tests and documentation.

Do **not** modify NI-01 writer, NI-02A algorithm or schema, NI-02B schema, historical edges, checkpoint/edge identity, retry authority/retention, knowledge bundle/taxonomy/rules, CAPPORT/Auth, Fingerprint, Omada, NI-05 or NI-06. No new database, background service, migration, or new public route. Keep NI-03 V1 DTO/API/UI behavior identical. No import of NI-03 private `_COVERAGE` by NI-04.

## 3. Implementation work packages (mandatory, one atomic candidate)

### WP1 — NI-02B runtime `safe_reason` precision

Retain the existing runtime enum and global pending semantics. When `runtime_state=attribution_unavailable`, populate the existing `safe_reason` with **exactly** `pending_attribution` if unresolved retryable pending exists while the required authority/read path has been operationally demonstrated, or `attribution_authority_unavailable` when the required NI-02A authority/horizon/store read is currently untrustworthy. Do not infer authority availability from the absence of errors alone, and do not mislabel failures as pending-only. Preserve precedence for `blocked_conflict`, `capacity_halted`, `capacity_waiting_reader`, and `source_unavailable`. Existing legacy `(attribution_unavailable, NULL)` must remain readable and map conservatively to unknown, not usable. Do not change the meaning of any persisted edge or erase pending to change health. For success-state and empty-poll paths, preserve current transaction, durability, idle-write-reduction, source freshness and source-verified safeguards. Add bounded privacy-safe operational counters specified in Annex A §6.9 without changing persistence schema.

### WP2 — Projection recognition snapshot V2

Add an NI-04-only **`RecognitionProjectionSnapshotV2`** read boundary in `recognition_read_service.py`, with exact fields and semantics in Annex A §7.1: `schema_version=2`, `site_id`, `device_id`, `identity_binding_state`, `projection_runtime_state`, `projection_safe_reason`, `bound_device_id`, `facts[]`, `device_linked_pending_count`, `historical_window_completeness_claimed=false`. Read runtime/safe_reason, Site+MAC authoritative binding, qualifying materialized edges, and distinct linked pending IDs in the **same consistent bounded projection read snapshot**. A pending observation counts for this device **only** if a committed edge with the same observation ID establishes the exact requested Site+MAC and currently authoritative device ID, within the requested half-open 24h window. Both-pending/no-edge observations cannot be assigned. Unrelated Site/device pending never counts as device-linked. Preserve existing read deadline, capacity and response bounds; do not query NI-02A or infer from current IP. Expose no raw pending IDs/counts to public UI (public boolean only).

### WP3 — NI-04 owned V2 service read contract

Implement `ServiceRecognitionCoverageV2` exactly as Annex A §5.4 with `scope=confirmed_device_evidence`, four-state `source_state`, four-state `pipeline_attribution_state`, `device_evidence_binding_state=authoritative|none`, boolean `device_linked_pending`, `recognition_state=usable|limited|unavailable`, `historical_window_completeness_claimed=false`. NI-04 owns the state mapping in Annex A §10; remove dependency on NI-03 `_COVERAGE`. Preserve positive fact admission predicates P01–P13 in Annex A §5.2: exact Site and canonical MAC, authoritative bound device ID, outbound src/external edge, exact source provenance, retained direct SNI, unique active admitted rule, valid bundle identity/digests. Confirmed immutable facts remain visible under global pending, authority unavailable, and unrelated registry degradation when the exact source/identity/bundle validations succeed. Fail closed for unreadable/corrupt projection or required source, identity or provenance mismatch, invalid bundle, unsupported DTO, busy/deadline or response overflow. Never synthesize a service from SNI alone, pending, or IP. Do not claim complete historical coverage.

### WP4 — DTO, serialization, route

Publish **`DeviceServiceSummaryV2`**, `schema_version=2`, `api_version=admin.device.service-intelligence.v2`; keep GET `/admin/api/v1/sites/{site_id}/devices/{device_id}/service-intelligence` unchanged. Update `models.py`, `serialization.py` and minimal `routes.py` wiring consistently; make backend and frontend V2 an atomic release under the existing NI-04 feature gate. Preserve existing 429/503 bounded failure behavior and the **16-KiB complete envelope** ceiling. No dual-version guessing or silent fallback to V1; incompatible version/shape fails closed. Preserve existing product fields and admitted evidence behavior unless the architecture explicitly changes them; add only the V2 coverage and version semantics. Any implementation-detail field ordering, enum serialization or serializer signatures must follow repository conventions, with deterministic golden tests rather than coder-invented policy.

### WP5 — Admin UI

Render confirmed service cards independently of coverage warning; never suppress them because global runtime is degraded. Implement **exact** messages in Annex A §8.1–§8.5 for positive+partial, positive+authority unavailable, no-positive+partial, no-positive+authority unavailable, and bounded no-supported-service. Legacy NULL reason maps to unknown; never optimistic usable. Do not show raw MAC/IP/SNI, pending counts, or diagnostic identifiers. Do not show “No services used”, “No Internet activity” or claim device attribution unavailable from the global enum alone. Freshness reflects **age of latest confirmed service observation** independently of coverage: `fresh <=300s`, `recent <=3600s`, `stale <=86400s`, `unavailable` if no confirmed observation. A fresh fact stays fresh under degraded coverage.

### WP6 — Retry observability, without lifecycle redesign

Preserve independent src/dst temporal evaluation, non-pending snapshot freeze, exactly-once role edge creation, 30-second retry eligibility (not SLA), batch <=500, sub-batch <=256, terminal outcomes, 14-day retention, immutability, and fail-closed invalid/conflict behavior. Add only bounded counters `attribution_retry_attempted_roles`, `attribution_retry_resolved_roles`, `attribution_retry_terminal_roles`, `attribution_retry_still_unavailable_roles`, `attribution_retry_expired_unresolved`, `pending_attribution_count`, `pending_oldest_age_seconds`, `attribution_authority_unavailable_count`. Counters must not include IP, MAC, device_id, SNI, DNS name, binding_id or raw payload. Avoid high-cardinality labels and per-attempt DB writes. No new audit history is authorized.

## 4. Exact test and QA gates

Implement all **T01–T30** in Annex A §12 as deterministic automated tests, including the known-positive `service.youtube` authoritative outbound direct-SNI fixture; unrelated pending, device-linked pending, both-pending/no-edge, current authority unavailable, legacy NULL reason, identity/provenance failures, retry lifecycle and immutability, 14-day retention, telemetry privacy, NI-03 V1 compatibility, UI exact wording, freshness independence, 429/503, 16-KiB ceiling, Site isolation, source/bundle corruption, and historical non-mutation. Include a static test prohibiting NI-04 import of NI-03 private `_COVERAGE`. Test atomic feature-gate V2 frontend/backend behavior and rollback to V1 code without migration. Existing relevant regression suites must pass. No skipped/xfail test may be represented as PASS.

## 5. Evidence and deliverables required from Coder (after release)

Deliver **one** implementation branch and PR containing all WPs; exact baseline and resulting commit/tree; changed-file inventory; mapping WP1–WP6 and T01–T30 to concrete tests; commands and full pass/fail outputs; API V2 sanitized example; UI exact-message screenshots or DOM assertions; explicit privacy scan for telemetry/logging; proof NI-03 V1 unchanged; proof no schema/identity/retention changes; rollback steps. State open P0/P1/P2 and any deviation. Any ambiguity or required deviation from Annex A means STOP and return to Tech Lead/Architect, not an ad-hoc Coder decision.

## 6. Production activation gate (separate authorization)

No production deployment from this task alone. Before any separately approved activation, capture read-only before/after evidence from Annex A §14: runtime/safe_reason, pending count/oldest age/role distribution, retry counters, poll freshness, checkpoint progression, authoritative binding count, known-positive device result, NI-03 regression, NI-04 API/UI and restart count. Success means confirmed facts visible with truthful partial coverage and no false positives—not merely disappearance of `attribution_unavailable`. Rollback is existing NI-04 feature gate OFF or prior V1 app code; no DB rollback, purge, checkpoint reset, historical rebuild or NI-02A/NI-01 interruption.

## 7. Acceptance verdict

Tech Lead accepts only when all WPs and T01–T30 pass, all permanent invariants I01–I15 hold, API/UI V2 deploy atomically behind the feature gate, NI-03 V1 unchanged, and the complete evidence package is attached. **Until an explicit Owner/Tech Lead authorization: IMPLEMENTATION_AUTHORIZATION=NO; CODER=HOLD; PRODUCTION_CHANGE=NO; NI-05=HOLD; NI-06=HOLD.**

---

# ANNEX A — FROZEN ARCHITECTURE CONTRACT v1 (VERBATIM)

The following architect document is incorporated as the normative specification. If a short work-package description above conflicts with it, **Annex A controls** and Coder must escalate before coding.

# TASK-DTI-NI-04 — ATTRIBUTION RECOVERY
## ARCHITECTURE CONTRACT v1

**Проект:** CaptivPortal  
**Роль:** Architect  
**Дата:** 2026-10-13  
**Приоритет:** P1  
**Статус:** `COMPLETE / READY FOR TECH LEAD REVIEW`  

---

# 0. AUTHORITY / BASELINE / GATE

Точный проверенный repository / production baseline:

```text
HEAD =
5c7b4c46afa5a57d55fe044c4326da3a10b9e145

TREE =
dec318cf1f813214d0879377180b095e843bb05c
```

Production `/opt/CaptivePortal` read-only подтверждён на том же HEAD/TREE.

Этот документ является bounded архитектурным recovery-contract для:

```text
NI-02B attribution coverage semantics
        ↓
NI-04 Service Recognition read contract
        ↓
Admin UI → Devices → Service Intelligence
```

Он НЕ является Coder TASK и НЕ разрешает production change.

```text
IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD
PRODUCTION_CHANGE = NO
SYSTEMD_ACTION = NO
DB_MUTATION = NO
```

NI-05 и NI-06 остаются HOLD.

---

# 1. ROOT CAUSE — ARCHITECTURAL FINDING

Production diagnosis доказывает, что текущий симптом нельзя корректно описывать как:

```text
"device attribution is globally unavailable"
```

Фактическая ситуация состоит из двух разных истин:

```text
A. часть endpoint attribution остаётся unresolved/pending;
B. одновременно существуют уже materialized authoritative device edges,
   пригодные для подтверждённого NI-04 Service evidence.
```

Текущий NI-02B singleton `runtime_state=attribution_unavailable` является слишком грубым operational aggregate. NI-04 затем повторно использует глобальное состояние как device-scoped coverage через NI-03 `_COVERAGE` mapping.

Это приводит к semantic overreach:

```text
there is pending attribution somewhere
        ↓
whole projection runtime = attribution_unavailable
        ↓
NI-04 attribution_state = degraded
        ↓
Admin presents device-scoped attribution degradation
```

даже когда exact returned Service fact уже опирается на authoritative Site+MAC→device binding.

Архитектурный дефект:

```text
GLOBAL PIPELINE HEALTH
!=
TRUST OF A PARTICULAR MATERIALIZED DEVICE FACT
!=
DEVICE-SCOPED COVERAGE COMPLETENESS
```

Эти три измерения должны быть разделены.

---

# 2. PRODUCTION READ-ONLY EVIDENCE

Диагностика выполнялась без production writes/restarts/migrations.

## 2.1 Pending population

Во время первой фиксированной выборки:

```text
projection_runtime_state.runtime_state = attribution_unavailable
pending_attribution_count = 6162
```

Распределение:

```text
src=resolved     dst=unavailable  = 3141
src=unavailable  dst=resolved     = 2697
src=unavailable  dst=unavailable  = 324
```

То есть:

```text
5838 / 6162
```

pending observation уже имели одну authoritative/resolved endpoint-side.

Позднее в той же read-only diagnostic session pending вырос до:

```text
6677
```

с распределением:

```text
resolved/unavailable = 3435
unavailable/resolved = 2912
both unavailable      = 330
```

Следовательно это не статический legacy residue; pending активно создаются.

## 2.2 Age / retry

Самая старая наблюдавшаяся pending row:

```text
first_pending_at = 2026-10-12T21:41:52.416569Z
```

Новые pending создавались непосредственно во время диагностики 2026-10-13.

Подтверждено:

```text
6218 pending rows
had last_attempt_at > first_pending_at
```

Следовательно retry lifecycle реально работает.

Однако текущая V1 persistence НЕ хранит отдельную immutable историю каждого retry outcome.
Поэтому production DB позволяет доказать:

```text
retry attempts occurred
```

но не позволяет ретроспективно доказать полный исторический счёт:

```text
how many retries transitioned unavailable → resolved
```

без отдельного persisted audit contract.

Этот recovery task НЕ вводит такую историю.

## 2.3 Current mixed attribution proves mechanism is not globally dead

Свежие pending rows были созданы с exact state:

```text
src_snapshot_state = resolved
dst_snapshot_state = unavailable
```

и обратным вариантом:

```text
src_snapshot_state = unavailable
dst_snapshot_state = resolved
```

в одном current `prepare()` lifecycle.

Current implementation получает authority horizon перед endpoint evaluations. Поэтому наличие свежего resolved endpoint в том же attempt является достаточным behavioral proof:

```text
NI-02A / DHCP authority is not globally unavailable.
```

Прямой read-only `SELECT` из attribution DB не был получен из-за production filesystem permissions. Это ограничение диагностики фиксируется честно; оно не заменяется предположением.

## 2.4 Authoritative device population exists

Production projection store содержит:

```text
426 authoritative Site+MAC bindings
426 distinct bound device_id values
```

## 2.5 Confirmed Service evidence exists while global state is degraded

Bounded read-only sample последних 1000 authoritative outbound external TLS/QUIC edges был сопоставлен с retained NI-01 SNI через текущий admitted matcher.

Получено:

```text
unknown = 766
service_resolved = 4
```

Все четыре положительных события относятся к одному authoritative device и Service:

```text
service.youtube
```

с direct TLS/QUIC SNI evidence.

Следовательно production доказал ключевой случай:

```text
GLOBAL runtime_state = attribution_unavailable
AND
VALID authoritative device-bound Service evidence exists
```

## 2.6 Diagnostic conclusion

```text
ROOT_CAUSE_CLASS =
GLOBAL COVERAGE STATE OVER-APPLIED TO DEVICE-SCOPED PRODUCT SEMANTICS

GLOBAL NI-02A OUTAGE = NOT PROVEN / CONTRADICTED BY CURRENT MIXED RESOLUTION

CONFIRMED DEVICE-BOUND SERVICE EVIDENCE = YES

PENDING BACKLOG = REAL / GROWING
```

Следовательно исправление только вида:

```text
rename attribution_unavailable → usable
```

запрещено.

---

# 3. PERMANENT INVARIANTS

Ни один пункт этого recovery contract не изменяет следующие правила.

```text
I01  SNI alone never identifies a Device.
I02  Current IP alone never identifies a historical Device.
I03  MAC/device binding is never guessed.
I04  Positive NI-04 Service result requires authoritative device-bound edge.
I05  Pending is not deleted merely to improve health/status.
I06  Existing committed edge is immutable.
I07  Existing historical Service evidence is not rewritten.
I08  Missing evidence != no activity.
I09  Attribution/source failure != no Service activity.
I10  IP-only Service recognition remains forbidden.
I11  Site is mandatory at every join/read boundary.
I12  NI-04 never directly calls NI-02A to re-attribute old events.
I13  NI-04 never recomputes Site+IP→MAC authority.
I14  CAPPORT/Auth/Omada/Fingerprint remain failure-isolated.
I15  historical_window_completeness_claimed remains false in V1 recovery.
```

---

# 4. A1 — GLOBAL RUNTIME-STATE DECISION

## 4.1 Decision

The existing NI-02B runtime enum is preserved.

```text
runtime_state = attribution_unavailable
```

remains a valid global operational aggregate while any retryable attribution uncertainty exists.

It is NOT redefined as:

```text
all attribution unavailable
all devices unavailable
no authoritative edge usable
NI-04 positive facts invalid
```

Exact new meaning:

```text
attribution_unavailable =
projection currently has unresolved retryable attribution uncertainty
OR the attribution authority itself is currently unavailable.
```

The enum alone is therefore insufficient to determine device-scoped fact usability.

## 4.2 `safe_reason` becomes mandatory discriminator

No schema change is required because `projection_runtime_state.safe_reason` already exists.

When `runtime_state=attribution_unavailable`, accepted reasons are:

```text
pending_attribution
attribution_authority_unavailable
```

Semantics:

### `pending_attribution`

```text
At least one pending role exists,
but current projection/attribution pipeline has demonstrated an operational read path.

Some facts may be authoritative and usable.
Coverage is incomplete.
```

### `attribution_authority_unavailable`

```text
Current required NI-02A authority/horizon/store read cannot be trusted.

Already committed authoritative facts remain immutable/readable,
but current attribution coverage is unavailable.
```

Legacy rows:

```text
runtime_state=attribution_unavailable
safe_reason=NULL
```

map to:

```text
attribution cause = unknown
coverage = degraded/unknown
```

Never optimistically to usable.

## 4.3 Precedence

Existing stronger failures retain precedence:

```text
blocked_conflict
capacity_halted / capacity_waiting_reader
source_unavailable
```

No pending state may mask a real source/capacity/conflict failure.

## 4.4 Runtime state is not an evidence veto

Permanent rule:

```text
runtime_state alone MUST NOT veto an already committed,
independently validated authoritative edge.
```

This is additive clarification, not a relaxation of edge admission.

---

# 5. A2 — DEVICE-SCOPED COVERAGE CONTRACT

## 5.1 Separate fact trust from coverage

NI-04 shall evaluate two independent questions:

```text
Q1. Is this particular Service fact trustworthy?
Q2. Is Service/attribution coverage for the requested window complete enough
    to make a negative claim?
```

Q1 can be YES while Q2 is NO.

## 5.2 Positive fact trust predicate

A positive Service result is publishable iff ALL are true:

```text
P01 exact requested site_id validated
P02 requested client_mac canonical
P03 projection binding_state = authoritative
P04 bound_device_id == requested device_id
P05 edge.site_id == requested site_id
P06 edge belongs to requested client_mac
P07 edge.device_endpoint_role = src
P08 edge.direction = outbound
P09 edge.peer_scope = external
P10 source observation identity/provenance exactly matches edge
P11 SNI presence = observed_retained
P12 admitted active direct-SNI rule resolves uniquely
P13 bundle/taxonomy/ruleset identity and digest validate
```

No current global pending row can retroactively invalidate P01-P13.

## 5.3 Device-linked pending

Introduce an internal bounded concept:

```text
DeviceLinkedPendingV1
```

A pending observation is device-linked for a requested Device iff there is an already committed edge for that same `observation_id` whose:

```text
site_id = requested Site
client_mac = requested MAC
current Registry binding is authoritative
bound device_id = requested device_id
```

A both-pending observation with zero edge:

```text
MUST NOT be assigned to any Device.
```

Global pending belonging to another device:

```text
MUST NOT be represented as this Device's attribution failure.
```

## 5.4 NI-04 V2 coverage dimensions

NI-04 stops reusing NI-03 private `_COVERAGE` and owns a recognition-specific coverage model.

New public coverage object:

```text
ServiceRecognitionCoverageV2 {
    scope: "confirmed_device_evidence"

    source_state:
        usable | degraded | unavailable | unknown

    pipeline_attribution_state:
        usable | degraded | unavailable | unknown

    device_evidence_binding_state:
        authoritative | none

    device_linked_pending: boolean

    recognition_state:
        usable | limited | unavailable

    historical_window_completeness_claimed: false
}
```

No raw pending count is needed in public UI.

## 5.5 Meaning

### `device_evidence_binding_state=authoritative`

At least the materialized facts being returned are tied through authoritative Site+MAC/device identity.

It does NOT claim every network observation in the window was attributed.

### `device_linked_pending=true`

One or more unresolved pending observations in the window are linked to the same Device through another already-authoritative role edge.

This means:

```text
additional Device activity may be missing from the product result.
```

### Global unassigned pending

May degrade:

```text
pipeline_attribution_state
```

but does NOT change:

```text
device_evidence_binding_state
```

for a Device whose returned facts are authoritative.

---

# 6. A3 — PENDING LIFECYCLE

The accepted NI-02B R1 retry model remains intact.

## 6.1 Entry

For each independently evaluated endpoint role:

```text
resolved
→ materialize eligible edge immediately
→ role non-pending

unavailable
→ no edge for that role
→ persist pending role

ambiguous / unattributed / outside_historical_horizon /
unsupported_address_family / endpoint_absent
→ terminal non-resolved
→ role non-pending

invalid
→ contract conflict
→ no pending commit
```

## 6.2 Retry cadence

Existing values preserved:

```text
minimum retry eligibility = 30 seconds
selection batch <= 500 pending rows
processing sub-batch <= 256 dispositions
```

Important semantic clarification:

```text
30 seconds = next eligibility target
NOT guaranteed wall-clock retry latency.
```

Backlog may delay a retry.

## 6.3 Role selection

Only roles whose pending flag is 1 are re-evaluated.

A non-pending role is never re-queried during that pending lifecycle.

Its persisted snapshot remains lineage authority for later opposite-edge materialization.

## 6.4 Successful retry

If a pending role becomes resolved:

```text
create its edge exactly once
preserve existing opposite edge unchanged
clear that role's pending flag
remove pending row only if no pending roles remain
```

## 6.5 Terminal retry

If retry returns:

```text
ambiguous
unattributed
outside_historical_horizon
unsupported_address_family
endpoint_absent
```

then:

```text
no edge is fabricated
role becomes terminal/non-pending
pending row is removed only if no other pending role remains
```

## 6.6 Still unavailable

```text
state remains unavailable
pending stays durable
next_retry_at advances according to existing cadence
```

No attempt-count expiry is introduced.

## 6.7 Source disappeared / eligibility expired

When retry can no longer retrieve an eligible source observation:

```text
result = expired_unresolved
pending row may be removed
NO edge is fabricated
NO old opposite edge is rewritten
```

## 6.8 Retention

Existing 14-day sensitive/source horizon remains authoritative.

Pending does not survive beyond source eligibility/retention solely for health cosmetics.

No retention extension is introduced.

## 6.9 Telemetry additions

Because V1 does not persist retry history, add safe bounded operational counters only:

```text
attribution_retry_attempted_roles
attribution_retry_resolved_roles
attribution_retry_terminal_roles
attribution_retry_still_unavailable_roles
attribution_retry_expired_unresolved
pending_attribution_count
pending_oldest_age_seconds
attribution_authority_unavailable_count
```

Prohibited telemetry:

```text
IP
MAC
device_id
SNI
DNS name
binding_id
raw observation payload
```

No new DB/table is required.

---

# 7. A4 — NI-02B → NI-04 READ CONTRACT

## 7.1 New additive internal snapshot

Introduce:

```text
RecognitionProjectionSnapshotV2
```

NI-04-specific read boundary only.

Exact required fields:

```text
schema_version = 2
site_id
device_id
identity_binding_state
projection_runtime_state
projection_safe_reason
bound_device_id
facts[]
device_linked_pending_count
historical_window_completeness_claimed = false
```

`device_linked_pending_count` is bounded to the exact requested 24h window and exact requested authoritative Site+MAC/device relationship.

This is an internal diagnostic/coverage field, not evidence identity.

## 7.2 Query semantics

In the SAME projection read snapshot:

```text
1. read runtime_state + safe_reason
2. validate Site+MAC Registry binding
3. select authoritative recognition edge facts
4. count distinct pending observation_id values linked to those same
   Site+MAC/device facts inside the requested [from,to) window
```

No second current attribution lookup.

No NI-02A query.

No current-IP correlation.

## 7.3 Fact delivery matrix

### Case R1 — global usable

```text
confirmed facts → SHOW
coverage → usable where other dimensions usable
```

### Case R2 — global pending / `safe_reason=pending_attribution`

```text
confirmed authoritative facts → SHOW
pipeline attribution → degraded
device linked pending true/false as exact query proves
negative completeness claim → FORBIDDEN
```

### Case R3 — actual authority unavailable

```text
confirmed previously committed authoritative facts → SHOW
pipeline attribution → unavailable
negative completeness claim → FORBIDDEN
```

### Case R4 — pending belongs only to another Device

```text
requested Device confirmed facts → SHOW
device_linked_pending = false
```

Global pipeline may still be degraded, but UI must not say this Device's confirmed binding is unavailable.

### Case R5 — both endpoints pending / no edge

```text
no Device assignment
no Service result
no guessed Device attribution
```

### Case R6 — source store cannot validate required exact source evidence

```text
NO new Service result from that source fact
request = unavailable/fail-closed
```

### Case R7 — recognition bundle invalid/unavailable

```text
NO Service resolution
recognition = unavailable
request = fail-closed
```

## 7.4 Blocking rule

The following are NOT sufficient alone to block confirmed facts:

```text
runtime_state=attribution_unavailable
some unrelated pending row exists
device_linked_pending=true
registry_degraded elsewhere
```

Hard request failure is reserved for inability to validate the requested result safely, including:

```text
projection DB unreadable/corrupt
source DB unreadable for required refs
identity mismatch
edge/source integrity mismatch
bundle digest/shape invalid
deadline / busy / response bound failure
unsupported contract shape
```

---

# 8. A5 — ADMIN UI CONTRACT

The UI must present:

```text
confirmed fact
+
coverage warning
```

as separate concepts.

## 8.1 Positive + partial coverage

Exact primary message:

```text
Confirmed service evidence is shown. Attribution coverage is partial; additional activity may be missing.
```

Cards remain visible.

## 8.2 Positive + current authority unavailable

```text
Confirmed historical service evidence is shown. Current device attribution is unavailable; additional activity may be missing.
```

Cards remain visible.

## 8.3 No positive + partial coverage

```text
No supported service evidence is confirmed for this device in the current window. Attribution coverage is partial, so this is not evidence of no activity.
```

## 8.4 No positive + authority unavailable

```text
Service evidence cannot be fully evaluated because device attribution is currently unavailable.
```

## 8.5 Sufficient evaluated evidence + no supported service

Only when all required dimensions permit the claim:

```text
No supported services recognized in the current window. This does not prove no Internet services or network activity.
```

Because V2 still sets:

```text
historical_window_completeness_claimed = false
```

this statement means only:

```text
no supported positive recognition among safely evaluated device-bound evidence
```

not full network absence.

## 8.6 UI prohibitions

Never display global runtime enum as if it were a Device fact:

```text
"This device attribution is unavailable"
```

unless the device-scoped product coverage contract actually yields unavailable.

Never hide confirmed cards merely because coverage is degraded.

Never turn an empty list into:

```text
No services used
No Internet activity
```

## 8.7 Freshness

V2 `freshness_state` describes age of the latest confirmed Service observation only:

```text
fresh  <= 300s
recent <= 3600s
stale  <= 86400s
unavailable = no confirmed observation
```

Coverage degradation is rendered separately and MUST NOT downgrade a genuinely fresh fact from `fresh` to `recent`.

---

# 9. A6 — COMPATIBILITY / VERSIONING

## 9.1 NI-02B persistence

Unchanged:

```text
DB schema
edge schema
pending schema
edge identity
checkpoint identity
retention
retry authority
```

No migration.

## 9.2 NI-02B runtime enum

Unchanged.

Only `safe_reason` semantics are refined/additive.

## 9.3 NI-03

NI-03 public contract remains V1 and continues its existing coarse runtime-state mapping.

This task MUST NOT silently change NI-03 API or UI semantics.

NI-03 regression is mandatory.

## 9.4 NI-04 ownership

NI-04 MUST stop importing:

```text
app.network_protocol_intelligence.read_service._COVERAGE
```

Private NI-03 mapping is not a valid NI-04 semantic authority.

NI-04 owns its own explicit V2 mapping.

## 9.5 NI-04 DTO/API version

Public Service Intelligence response becomes:

```text
DeviceServiceSummaryV2
schema_version = 2
api_version = admin.device.service-intelligence.v2
```

The GET route remains:

```text
GET /admin/api/v1/sites/{site_id}/devices/{device_id}/service-intelligence
```

Route namespace does not need to change because the response advertises its exact product schema/API version.

Frontend and backend V2 must deploy atomically behind the existing NI-04 feature gate.

## 9.6 Rollback

Rollback to V1 application code requires:

```text
no DB rollback
no schema rollback
no data repair
```

because this recovery is read-contract/runtime-status only.

---

# 10. GLOBAL STATE MAPPING — CLOSED MATRIX

| NI-02B runtime | safe_reason | NI-04 pipeline attribution | Confirmed facts | Negative claim |
|---|---|---|---|---|
| usable | null | usable | show | bounded allowed |
| registry_degraded | null/registry reason | usable | show if exact Device binding authoritative | bounded allowed only if other coverage permits |
| attribution_unavailable | pending_attribution | degraded | show | forbidden as completeness claim |
| attribution_unavailable | attribution_authority_unavailable | unavailable | show already-confirmed facts | forbidden |
| attribution_unavailable | null/legacy | unknown | show already-confirmed facts | forbidden |
| source_unavailable | source_unavailable | unknown/unavailable | show only if exact source evidence required for response remains safely readable; otherwise request unavailable | forbidden |
| capacity_waiting_reader | reason | degraded | existing facts may remain readable | forbidden |
| capacity_halted | reason | degraded | existing facts may remain readable | forbidden |
| blocked_conflict | reason | degraded | pre-conflict immutable facts may remain readable if exact query is safe | forbidden |
| initializing/stopping | any | unknown | fail conservatively if exact snapshot cannot be validated | forbidden |

No matrix row authorizes constructing a new Device fact from pending data.

---

# 11. WHY WE DO NOT CHANGE ENDPOINT ATTRIBUTION IN THIS TASK

Production pending distribution strongly suggests many observations consist of:

```text
guest endpoint → resolved
external peer → unavailable
```

and the inverse for inbound traffic.

It may be tempting to stop asking NI-02A to attribute external peers.

That change is NOT part of this recovery contract.

Reason:

```text
accepted NI-02B architecture freezes independent endpoint evaluation
```

and peer-attribution lineage is an explicit existing contract.

Therefore:

```text
NO short-circuit external peer attribution
NO pending deletion based on peer_scope alone
NO reinterpretation unavailable → endpoint_absent/unattributed
```

Any future optimization of this behavior requires a separate frozen-contract change review.

---

# 12. ACCEPTANCE TEST MATRIX

## T01 — Global pending does not veto confirmed Service

Fixture:

```text
runtime=attribution_unavailable
safe_reason=pending_attribution
requested Device authoritative
valid outbound src edge
retained direct admitted YouTube SNI
```

Expected:

```text
service.youtube returned
availability=degraded
pipeline_attribution_state=degraded
confirmed card visible
```

## T02 — Pending belongs to another Device

Expected:

```text
requested Device device_linked_pending=false
confirmed facts unaffected
UI does not say requested Device attribution unavailable
```

## T03 — Both-pending observation has no edge

Expected:

```text
not assigned to any Device
no guessed Service
```

## T04 — Same Device linked pending

Expected:

```text
device_linked_pending=true
confirmed existing Service remains visible
partial-coverage wording exact
```

## T05 — Actual attribution authority unavailable + old confirmed edge

Expected:

```text
old confirmed Service visible
pipeline_attribution_state=unavailable
current-authority-unavailable warning
```

## T06 — Actual authority unavailable + no confirmed result

Expected:

```text
no positive Service
no "no services" claim
unknown/unavailable wording
```

## T07 — Legacy runtime attribution_unavailable + safe_reason NULL

Expected:

```text
pipeline attribution=unknown
never usable
positive immutable fact may remain visible
```

## T08 — Exact SNI without authoritative edge

Expected:

```text
no Service result
```

## T09 — Authoritative edge + missing/expired SNI

Expected:

```text
no positive Service
recognition limited
```

## T10 — IP/MAC guess regression

No current-IP or nearest-MAC fallback may create an edge/result.

## T11 — Retry remains unavailable

Expected:

```text
pending retained
no edge created
```

## T12 — Retry resolves

Expected:

```text
new role edge created once
existing opposite edge byte/semantic digest unchanged
pending flag cleared
```

## T13 — Retry terminal unattributed/ambiguous

Expected:

```text
no edge for terminal role
role non-pending
no fabricated identity
```

## T14 — Retry invalid

Expected:

```text
blocked conflict
no pending reinterpretation
```

## T15 — Source expired / no longer retrievable

Expected:

```text
expired_unresolved
pending removed only by legitimate lifecycle
no Service fabricated
```

## T16 — 14-day retention

Existing retention boundaries remain exact.

## T17 — Retry telemetry

Counters distinguish:

```text
attempted
resolved
terminal
still unavailable
expired unresolved
```

without identifiers.

## T18 — NI-03 regression

NI-03 existing V1 DTO/API behavior remains unchanged.

## T19 — NI-04 no dependency on NI-03 private `_COVERAGE`

Static/import test proves no NI-04 import of private NI-03 coverage mapping.

## T20 — UI positive + partial

Exact message from §8.1; cards stay visible.

## T21 — UI positive + unavailable

Exact message from §8.2; cards stay visible.

## T22 — UI no positive + partial

Exact message from §8.3; no activity claim absent.

## T23 — UI no positive + unavailable

Exact message from §8.4.

## T24 — freshness independence

Fresh confirmed result + degraded coverage remains:

```text
fresh
```

not silently `recent`.

## T25 — Bundle invalid

```text
HTTP/product unavailable
no guessed recognition
```

## T26 — Projection/source DB unreadable

No fabricated empty list.

## T27 — Deadline / busy

Existing bounded 429/503 semantics preserved.

## T28 — response size

16-KiB complete envelope ceiling preserved.

## T29 — Site isolation

Pending/facts from Site B cannot influence Device result for Site A except global pipeline state, and never become Site A evidence.

## T30 — Historical immutability

Recovery implementation performs no UPDATE/DELETE of historical edges solely to change coverage/result.

---

# 13. REQUIRED IMPLEMENTATION BOUNDARY FOR TECH LEAD TASK

One later Tech Lead implementation TASK may include only bounded changes in:

```text
app/network_metadata_projection/repository.py
app/network_metadata_projection/service.py
app/network_metadata_projection/recognition_read_service.py

app/network_service_recognition/read_service.py
app/network_service_recognition/models.py
app/network_service_recognition/serialization.py

app/admin_web/routes.py              [only response contract wiring as needed]
app/admin_web/static/admin.js

related deterministic tests/docs
```

It MUST NOT include:

```text
NI-01 writer changes
NI-02A attribution algorithm changes
DHCP authority schema changes
projection DB schema changes
new DB
new background service
recognition knowledge changes
new Service rules
CAPPORT/Auth changes
Fingerprint changes
Omada changes
NI-05/NI-06
```

---

# 14. OBSERVABILITY / PRODUCTION VERIFICATION GATE

Before activation Tech Lead must collect read-only before/after evidence for the exact candidate:

```text
projection runtime_state + safe_reason
pending count
oldest pending age
pending role distribution
retry telemetry counters
source poll freshness
projection checkpoint progress
authoritative binding count
known positive Service fixture/device
NI-03 regression
NI-04 API/UI result
service/process restart count
```

Acceptance is NOT:

```text
"attribution_unavailable disappeared"
```

Acceptance is:

```text
1. confirmed facts remain exactly trustworthy;
2. partial/unavailable coverage is represented truthfully;
3. no false positive is introduced;
4. pending lifecycle remains intact;
5. source/checkpoint progression remains healthy;
6. UI no longer equates global degradation with absence of Device evidence.
```

---

# 15. FAILURE / ROLLBACK

If V2 read/serialization/UI fails after an authorized deployment:

```text
1. disable existing NI-04 feature gate or rollback app code;
2. do not mutate projection data;
3. do not purge pending;
4. do not reset checkpoints;
5. do not rebuild historical edges;
6. NI-01/NI-02A/NI-02B continue independently.
```

Rollback needs no DB migration.

---

# 16. FROZEN-CONTRACT EXCEPTION STATUS

This contract does NOT request an exception to the frozen NI-02B endpoint-attribution algorithm.

Preserved:

```text
independent src/dst temporal attribution
pending retry semantics
immutable edge semantics
0/1/2 edge model
```

Bounded amendments are limited to:

```text
operational `safe_reason` precision
recognition-specific additive read snapshot V2
NI-04 coverage semantics V2
Admin presentation V2
retry observability
```

Therefore:

```text
NI02B_IDENTITY_AUTHORITY_CHANGE = NO
NI02B_SCHEMA_CHANGE = NO
OWNER_FROZEN_CONTRACT_EXCEPTION = NOT REQUIRED FOR THIS RECOVERY CONTRACT
```

Owner/Tech Lead approval is still required for implementation/deployment in the normal governance flow.

---

# 17. FINAL A1–A6 DECISIONS

```text
A1 GLOBAL RUNTIME STATE
KEEP attribution_unavailable as global operational aggregate.
Add exact safe_reason distinction.
Never use enum alone as per-Device evidence veto.

A2 DEVICE-SCOPED COVERAGE
Separate confirmed-fact authority from pipeline completeness.
Positive authoritative facts remain displayable under degraded coverage.
Add device_linked_pending and V2 recognition coverage.

A3 PENDING LIFECYCLE
Preserve existing R1 lifecycle/retry/retention exactly.
Add bounded safe telemetry only.
No cosmetic deletion and no retry guess.

A4 NI-02B → NI-04
Add RecognitionProjectionSnapshotV2.
No NI-02A query from NI-04.
No private NI-03 coverage reuse.
Confirmed facts survive global pending/current attribution outage when exact stored evidence remains verifiable.

A5 ADMIN UI
Show confirmed facts and coverage separately.
Never turn global degradation or empty result into "no activity".
Use exact messages in §8.

A6 COMPATIBILITY
No DB schema migration.
NI-03 V1 unchanged.
NI-04 public DTO/API becomes V2.
Same GET route; atomic backend/frontend rollout behind existing NI-04 feature gate.
```

---

# 18. FINAL STATUS

```text
TASK =
TASK-DTI-NI-04 — ATTRIBUTION RECOVERY

ARCHITECTURE_STATUS =
COMPLETE / READY FOR TECH LEAD REVIEW

PRODUCTION_ROOT_CAUSE_CLASS =
GLOBAL COVERAGE STATE OVER-APPLIED TO DEVICE-SCOPED PRODUCT SEMANTICS

PRODUCTION_PENDING =
CONFIRMED / ACTIVE / GROWING DURING DIAGNOSTIC WINDOW

AUTHORITATIVE DEVICE BINDINGS =
CONFIRMED

CONFIRMED DEVICE-BOUND SERVICE EVIDENCE =
CONFIRMED

GLOBAL ATTRIBUTION AUTHORITY DEAD =
NO / NOT SUPPORTED BY EVIDENCE

OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0

READY_FOR_TECH_LEAD_IMPLEMENTATION_CONTRACT = YES

IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD
PRODUCTION_CHANGE = NO
NI-05 = HOLD
NI-06 = HOLD
```

Tech Lead may now prepare one exact implementation TASK from this contract without delegating architecture choices to Coder.
