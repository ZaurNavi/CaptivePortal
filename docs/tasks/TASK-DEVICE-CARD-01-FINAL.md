# TASK-DEVICE-CARD-01 — Current Device Context — FINAL

**Project:** CaptivPortal
**Area:** Admin Console → Devices → Device Detail
**Status:** `COMPLETE / PRODUCTION ACTIVE`
**Updated:** 2026-09-09

## 1. Final closure

```text
TASK-DEVICE-CARD-01=COMPLETE
IMPLEMENTATION=PASS
OWNER + TECH LEAD ACCEPTANCE=PASS
MERGE=COMPLETE
PRODUCTION DEPLOY=PASS
PRODUCTION ACTIVATION=PASS
```

Production feature state:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
```

Repository default remains:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
```

Repository default and production activation are separate facts.

## 2. Git / artifact identity

```text
repository=ZaurNavi/CaptivePortal
PR=#108 — TASK-DEVICE-CARD-01 — Current Device Context
PR base=3eac6f13d5f3966574f6d1b0a10f531d988f91ec
implementation commit=1a3f2b8a844f2ce1c26cbdd9e4c44d17a201ac14
accepted implementation tree=8f1342f0a0f1e8242642161e02b2f3276e6ddf51
merge / current main / production commit=7df71a8e807efd74b123117e78cb8d992c190fa1
previous production runtime=e32ade378bdbfc9f8458db9c18221958f4552718
```

PR #108 is merged.

## 3. Production

```text
host=192.168.0.202
repository=/opt/CaptivePortal
service=captive-portal.service
main / production=7df71a8e807efd74b123117e78cb8d992c190fa1
tree=8f1342f0a0f1e8242642161e02b2f3276e6ddf51
```

Rollout:

```text
previous production=e32ade378bdbfc9f8458db9c18221958f4552718
→ fast-forward to 7df71a8e807efd74b123117e78cb8d992c190fa1
→ first smoke with feature=false
→ separate feature activation=true
→ service active
→ Owner manual production Device Detail verification=PASS
```

Rollback was not required.

## 4. Product boundary

The existing Device Detail keeps historical information:

```text
Identity
Latest Site Snapshot
Latest Client Observation
Recent Visits
```

TASK-DEVICE-CARD-01 adds a separate read-only block:

```text
Current Device Context
```

with:

```text
Presence
Authorization
Network
Radio
Controller
Current Guest Traffic
Evidence / Freshness
```

Permanent:

```text
Historical Device Context != Current Device Context
```

Historical facts never substitute for missing/untrusted current evidence.

## 5. Canonical data path

```text
existing Site-safe Device boundary
→ resolve requested device inside Site
→ resolve canonical MAC server-side
→ CurrentStateReadService.get_current_client(...)
→ optional pinned exact-client CurrentGuestTrafficReadService
→ AdminQueryService.device_current_context(...)
→ strict Admin serializer
→ admin.device.current.v1
→ Device Detail
```

No Device Card request adds:

```text
browser → Omada
browser → Loki
browser → Grafana
browser → external Analytics API
Admin request → Omada
```

No new collector, DB, schema, index, migration, write path, worker or scheduler
was introduced.

## 6. Endpoint / authorization

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/current
```

Capability:

```text
admin.read.device
```

DTO:

```text
admin.device.current.v1
```

The device is first resolved through the existing Site-safe Device boundary.
Canonical MAC identity is server-side.

Query parameters are not part of the v1 endpoint contract.

## 7. Current State exact lookup

Canonical service addition:

```text
CurrentStateReadService.get_current_client(...)
```

The exact client row is exposed only from an accepted client snapshot that is:

```text
result=success
complete=true
fresh
correct Site
trusted canonical Site/SSID source scope
```

The lookup does not use historical Device/Visit/Observation data to reconstruct
current state.

## 8. Presence semantics

### Online

```text
fresh + complete managed Current State scope
+
matching current client row
→ presence=online
```

### Offline

```text
fresh + complete managed Current State scope
+
device is proven absent
→ presence=offline
```

Offline requires positive absence evidence.

### Unknown

```text
stale
unavailable
invalid timestamp
invalid/untrusted source scope
other untrusted current evidence
→ presence=unknown
```

Permanent:

```text
stale != offline
unavailable != offline
invalid timestamp != offline
historical absence/presence != current offline proof
```

## 9. Authorization semantics

Current authorization evidence is classified as:

```text
authorized
pending
other
unknown
```

This is Current State evidence, not historical Visit/Auth evidence.

Offline/unknown current state does not inherit an old authorization value from
history.

## 10. Current Guest Traffic

Traffic is applicable only to:

```text
presence=online
authorization=authorized
```

For current pending/other clients:

```text
traffic applicability=not_applicable
```

No fabricated rate is produced.

Exact-client traffic reuses the existing semantic owner:

```text
CurrentGuestTrafficReadService
```

with a pinned same-cycle exact-client read.

The exact-client projection reads the current accepted row and nearest previous
accepted row under the same Site/scope. It does not materialize the full Site
population.

## 11. Numeric zero

Numeric zero is evidence:

```text
0 Mbps
```

It is not:

```text
N/A
missing
unavailable
—
```

Permanent:

```text
0 != null
```

## 12. Traffic failure isolation

A technical Current Guest Traffic problem is local to the Traffic evidence.

Examples:

```text
source_unavailable
integrity_unavailable
query_deadline
```

Required behavior:

```text
Current endpoint remains a valid composed Current response
Presence retained
Authorization retained
Network retained
Radio retained
Controller retained
Traffic failure_reason populated locally
```

Traffic technical failure must not be rewritten as generic
`insufficient_data`.

## 13. Current State execution failure

If Current State itself cannot execute/read safely:

```text
Current endpoint → controlled source/query failure (503 where applicable)
```

The historical Device Card remains an independent path and Device Detail must
not be destroyed by Current failure.

## 14. Freshness / evidence

Current Device Context exposes separate evidence including:

```text
evaluated time
observed time
capture/age
freshness
freshness reason
managed Site/SSID scope
```

Current State freshness family remains:

```text
fresh
stale
unavailable
```

## 15. Invalid timestamp

Unsafe timestamp evidence is sanitized.

Canonical semantic outcome:

```text
HTTP semantic Current response remains safe
Presence=unknown
Observed=null / —
Age=null / —
Freshness=unavailable
Reason=invalid_timestamp
```

Invalid timestamps are not exposed as trusted Current evidence and never become
offline proof.

## 16. Frontend lifecycle

Current Device Context lifecycle:

```text
one load when Device Detail opens
manual Refresh
no automatic polling
no overlapping Current request
```

Historical and Current parts load independently.

Current failure:

```text
does not clear/destroy historical Device context
```

## 17. Acceptance

```text
Cross-surface focused gate=178 passed

Official Windows Central Full V6=PASS
strict regressions=0

Bounded exact-read/query-plan gate=PASS

Controlled Browser acceptance=PASS
```

Controlled Browser acceptance covered:

```text
online
pending
offline
stale
invalid timestamp
Current 503
Traffic failure
valid zero
manual Refresh
no Current overlap
no automatic polling
```

## 18. Production result

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
captive-portal.service=active
production deploy=PASS
production activation=PASS
Owner manual Web UI verification=PASS
rollback required=no
```

The feature is current production functionality.

## 19. Separate UI/design work

`TASK-WEB-DEVICE-UI-01` is explicitly outside this completed functional TASK.

Current status:

```text
TASK-WEB-DEVICE-UI-01=IN PROGRESS / LAB REVIEW PENDING
MERGED=NO
DEPLOYED=NO
ACCEPTED PRODUCTION BEHAVIOR=NO
```

It may change presentation such as compact Devices cards/list,
human-readable bytes/time/rates, status indicators and future Online-first UX.

Until separately accepted and deployed, those presentation changes must not be
described as current production behavior.

## 20. Final decision

```text
TASK-DEVICE-CARD-01=COMPLETE
DEVICE_CURRENT_CONTEXT=PRODUCTION ACTIVE
IMPLEMENTATION=PASS
ACCEPTANCE=PASS
MERGE=COMPLETE
PRODUCTION DEPLOY=PASS
PRODUCTION ACTIVATION=PASS

TASK-WEB-DEVICE-UI-01=NOT COMPLETE
```
