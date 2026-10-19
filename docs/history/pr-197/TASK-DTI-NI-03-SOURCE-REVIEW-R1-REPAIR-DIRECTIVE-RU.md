# TASK-DTI-NI-03
## TECH LEAD SOURCE REVIEW R1 — REPAIR DIRECTIVE

**Project:** CaptivPortal  
**Reviewed candidate tree:** `ece007c668c22471f802251ac8369369ad7e278d`  
**Reviewed patch SHA256:** `ee9be3a5ac74ccd921ea7bfdb960b86f53e9a16c67d9127f5fd793dcef83373e`  
**Baseline:** `51deead342bd821b5c46fb75a7ceef37bef63e7c`  
**Architecture:** v1 + v1-R1, unchanged  
**Implementation contract:** v3  
**Production change:** NO  

```text
TECH_LEAD_SOURCE_REVIEW=HOLD

OPEN_P0=0
OPEN_P1=2
OPEN_P2=0

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO
```

The candidate is structurally good and remains the repair base.
Do NOT restart implementation from scratch.

Only the two repairs below are authorized.

---

# P1-01 — `availability_state` violates the frozen identity rule

## Current defect

Current semantic construction effectively does:

```text
availability_state = projection_state
```

Current server publication validation also requires:

```text
availability_state == coverage.projection_state
```

and the frontend validator mirrors the same rule.

That is wrong.

Frozen NI-03 architecture requires:

```text
availability_state=usable
ONLY WHEN

coverage.projection_state=usable
AND
identity_binding_state=authoritative
```

Otherwise:

```text
availability_state=degraded
```

Therefore this exact valid state MUST exist:

```text
runtime_state=usable

coverage.projection_state=usable
coverage.source_state=usable
coverage.attribution_state=usable

identity_binding_state=pending | unavailable | absent

evidence_state=identity_pending
freshness_state=unavailable

availability_state=degraded
```

Tech Lead reproduced the current defect directly from the candidate:

```text
usable identity_pending pending usable
```

The first value is currently `availability_state=usable`.
It MUST be `degraded`.

## Exact repair

Modify only the relevant NI-03 semantic/public/frontend files:

```text
app/network_protocol_intelligence/read_service.py
app/network_protocol_intelligence/models.py
app/admin_web/static/device_protocol_intelligence.js

tests/network_protocol_intelligence/test_read_service.py
tests/admin_web/test_device_protocol_intelligence.py
tests/admin_web/device_protocol_intelligence.cjs
```

### Semantic service

Compute:

```text
availability_state =
    usable
    iff
    projection_state == usable
    AND
    identity_binding_state == authoritative

else
    degraded
```

Do NOT change `coverage.projection_state`.

### Server publication validator

Remove the invalid invariant:

```text
availability_state == coverage.projection_state
```

Replace it with the exact expected-availability formula above.

The validator MUST reject both classes of contradiction:

```text
projection=usable
identity=pending/unavailable/absent
availability=usable
→ reject
```

and:

```text
projection=usable
identity=authoritative
availability=degraded
→ reject
```

For:

```text
projection=degraded
```

availability is always:

```text
degraded
```

regardless of identity state.

### Frontend validator

Use the identical cross-field formula.

Do NOT require:

```text
coverage.projection_state === availability_state
```

because the valid identity-pending state intentionally has:

```text
projection_state=usable
availability_state=degraded
```

### Required regression cases

Server semantic test:

```text
runtime=usable
binding=not_yet_registry_resolved
→ availability=degraded
→ projection=usable
→ evidence=identity_pending
→ freshness=unavailable
```

Repeat for:

```text
registry_unavailable
absent
```

Also prove:

```text
runtime=usable
binding=authoritative
→ availability=usable
```

Serializer must reject both invalid pairings listed above.

Frontend real-Node test must render the valid:

```text
projection usable + availability degraded + identity pending
```

shape and reject the invalid pairing.

API-level focused test must prove the same public DTO semantics.

No other freshness/coverage mapping changes are authorized.

---

# P1-02 — feature-OFF gate runs before frozen Site / permission / device-syntax gates

## Current defect

Current route starts effectively with:

```text
if not config.device_protocol_intelligence_enabled:
    return 404
```

before exact Site resolution and `admin.read.device` authorization.

Therefore, while NI-03 is disabled:

```text
invalid Site syntax
```

can incorrectly become:

```text
404
```

instead of frozen:

```text
400 invalid_request
```

and:

```text
forbidden Site
```

can incorrectly become:

```text
404
```

instead of:

```text
403 site_forbidden
```

Likewise a noncanonical/invalid `device_id` can be hidden behind the early
feature 404 instead of the frozen `400 invalid_request`.

Frozen route security/error order must be preserved.

## Exact repair

Modify:

```text
app/admin_web/routes.py
tests/admin_web/test_device_protocol_intelligence.py
```

Do NOT change capability definitions or Site resolver semantics.

For the NI-03 endpoint, the observable gate order must be:

```text
1. authenticated Admin session
   (existing decorator)

2. resolve exact Site through AdminSiteContextResolver
   invalid syntax → 400
   forbidden Site → 403

3. require admin.read.device for exact Site
   denied → 403

4. reject forbidden query/body input
   → 400

5. validate canonical device_id syntax
   → 400

6. if NI-03 feature is disabled
   → 404 not_found

7. require existing AdminQueryService
   unavailable → 503

8. call AdminQueryService.device_protocol_intelligence()

9. for enabled NI-03, existing Device gateway lookup occurs
   before the NI-03 semantic/projection read.
```

Use the existing canonical Device-ID helper/validation.
Do not invent another UUID parser.

The query service may retain defense-in-depth validation.

No projection read may occur before Site/capability/device authorization.

## Required route regressions

With NI-03 feature OFF:

```text
unauthenticated
→ 401

invalid Site syntax
→ 400

forbidden Site
→ 403

admin.read.device denied
→ 403

invalid/noncanonical device_id
→ 400

valid authorized Site + canonical device_id
→ 404
```

And prove:

```text
feature OFF
→ no NI-03 semantic/projection read
```

With feature ON, preserve existing:

```text
missing Device → 404
busy → 429 + Retry-After:1
deadline → 503 query_deadline
source unavailable → 503 source_unavailable
```

All error envelopes on this path remain:

```text
api_version=admin.device.protocol-intelligence.v1
```

---

# PRESERVED / NO REPAIR REQUESTED

Do NOT modify these accepted parts during R1:

```text
NI-02B schema
NI-02B writer
NI-02B checkpoint/retry/retention
same-snapshot SQL shape
20,000/20,001 bound
5s cancellable read
two-slot NI-03 semaphore
24h / 60m windows
DNS/TLS/QUIC vocabulary
freshness thresholds
coverage runtime mapping
Site-scoped Device lookup
ProjectionConfig/env handoff
systemd drop-in artifact
Settings → Features independence
API endpoint/path/version
16 KiB response cap
privacy boundary
Device Card field set
60s polling
one in-flight browser request
manual coalescing
10s AbortController timeout
60/120/300 backoff
15m last-good bound
deployment default-OFF
```

Do NOT touch:

```text
app/network_metadata_projection/read_service.py
deploy/network-metadata-projection/*
app/settings_control/*
app/config.py
app/settings.py
app/admin_web/runtime.py
```

unless the two exact repairs above prove impossible without doing so.
If impossible:

```text
STOP → TECH LEAD
```

Do not expand scope yourself.

---

# AUTHORIZED R1 TESTS

Run only the repair-relevant focused tests plus direct route regression:

```text
python -m pytest -q \
  tests/network_protocol_intelligence/test_read_service.py \
  tests/admin_web/test_device_protocol_intelligence.py \
  tests/admin_web/test_device_protocol_intelligence_frontend.py \
  tests/admin_web/test_routes.py
```

Also:

```text
python -m compileall -q \
  app/network_protocol_intelligence \
  app/admin_web/routes.py \
  tests/network_protocol_intelligence/test_read_service.py \
  tests/admin_web/test_device_protocol_intelligence.py \
  tests/admin_web/test_device_protocol_intelligence_frontend.py

node --check app/admin_web/static/device_protocol_intelligence.js

git diff --check
```

Linux WAL/concurrency rerun is NOT required for R1 unless
`app/network_metadata_projection/read_service.py` changes.
It must not change for this repair.

Do NOT run:

```text
full repository pytest
Central Lab official gate
production tests
production DB
production systemd
```

Tech Lead owns broader acceptance after source repair PASS.

---

# R1 HANDOFF REQUIRED

Return an uncommitted repaired candidate:

```text
TASK-DTI-NI-03 — R1 REVIEW CANDIDATE

BASE_HEAD=
51deead342bd821b5c46fb75a7ceef37bef63e7c

HEAD_REMAINS=
51deead342bd821b5c46fb75a7ceef37bef63e7c

REPAIRS=
P1-01 availability semantics
P1-02 route gate precedence

FILES_CHANGED_SINCE_PREVIOUS_CANDIDATE=
...

TESTS=
...

NEW_CANDIDATE_TREE=
...

NEW_PATCH_PATH=
...

NEW_PATCH_BYTES=
...

NEW_PATCH_SHA256=
...

PATCH_RECONSTRUCTION=PASS
PATCH_REVERSE_APPLY_CHECK=PASS

INDEX_STAGED_FILES=NONE

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO

NEXT_ACTION=
TECH LEAD R1 SOURCE REVIEW
```

No commit.

No push.

No PR.

---

# TECH LEAD R1 STATUS

```text
CURRENT_CANDIDATE=
NOT ACCEPTED

OPEN_P0=0
OPEN_P1=2
OPEN_P2=0

CODER_R1_REPAIR=GO

COMMIT=HOLD
PUSH=HOLD
PR=HOLD
DEPLOYMENT=HOLD
```
