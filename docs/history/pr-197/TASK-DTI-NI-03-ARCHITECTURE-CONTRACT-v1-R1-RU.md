# TASK-DTI-NI-03
## PROTOCOL INTELLIGENCE + DEVICE CARD P1
### ARCHITECTURE CONTRACT v1-R1
### TECH LEAD R1 — BOUNDED REPAIR ADDENDUM
### FOR TECH LEAD RE-REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Reviewed baseline:** `main@3467da8abd4ad4bb5b381a13e374e2e8faf4685e`  
**Reviewed TREE:** `2e3cb2b345af370275cb9b8fe35729f6f5218d35`  
**Parent artifact:** `TASK-DTI-NI-03-ARCHITECTURE-CONTRACT-v1-RU.md`  
**R1 scope:** `P1-01 / P1-02 only`  
**Implementation authorization:** `NO`  
**Coder:** `HOLD`  
**Production change:** `NO`

---

# 0. PRECEDENCE / NON-REOPEN RULE

Этот документ является нормативным addendum к:

```text
TASK-DTI-NI-03
ARCHITECTURE CONTRACT v1
```

При конфликте:

```text
v1-R1
>
v1
```

Все решения v1, не изменённые ниже, остаются в силе.

R1 НЕ переоткрывает:

```text
BOUNDED READ-TIME AGGREGATION
OVER NI-02B MATERIALIZED PROJECTION

NO new DB
NO writer
NO background service
NO checkpoint
NO durable summary history

Product Protocols =
dns / tls / quic

Summary window =
24h

Recent window =
60m

NI-02A authority
NI-02B projection semantics
Registry semantics
IPv6 admission
NI-04 scope
```

---

# 1. P1-01 — NI-02B CONFIGURATION HANDOFF TO ADMIN RUNTIME

## 1.1. Selected architecture

Выбран один authoritative mechanism:

```text
THE EXISTING NI-02B SYSTEMD ENVIRONMENT FILE
IS ALSO LOADED INTO captive-portal.service
FOR THE NI-03 READ CONSUMER.
```

Authoritative deployment file:

```text
/etc/captive-portal/network-metadata-projection.env
```

Existing NI-02B configuration owner remains:

```text
app/network_metadata_projection/config.py
projection_config_from_env()
```

NI-03 MUST NOT create:

```text
new projection configuration aliases
new independent DB-path setting
new independent enabled setting
new independent max-size setting
```

---

# 2. EXACT CONFIGURATION AUTHORITIES

The exact authorities are:

```text
NETWORK_METADATA_PROJECTION_ENABLED
→ /etc/captive-portal/network-metadata-projection.env
→ parsed by projection_config_from_env()
```

```text
NETWORK_METADATA_PROJECTION_DB_PATH
→ /etc/captive-portal/network-metadata-projection.env
→ parsed by projection_config_from_env()
```

```text
NETWORK_METADATA_PROJECTION_MAX_DB_BYTES
→ /etc/captive-portal/network-metadata-projection.env
→ parsed by projection_config_from_env()
```

Repository defaults remain those owned by:

```text
ProjectionConfig
+
projection_config_from_env()
```

No NI-03 module may freeze a second literal production DB path.

No NI-03 module may define:

```text
PROTOCOL_INTELLIGENCE_PROJECTION_DB_PATH
PROTOCOL_INTELLIGENCE_PROJECTION_ENABLED
PROTOCOL_INTELLIGENCE_PROJECTION_MAX_DB_BYTES
```

or any equivalent alias.

---

# 3. SYSTEMD HANDOFF — EXACT

NI-03 requires a deployment/systemd handoff for:

```text
captive-portal.service
```

Add exact drop-in:

```text
/etc/systemd/system/captive-portal.service.d/
20-network-metadata-projection-read.conf
```

with:

```ini
[Service]
EnvironmentFile=-/etc/captive-portal/network-metadata-projection.env
```

The leading:

```text
-
```

is intentional.

It means absence of the optional NI-02B environment file MUST NOT prevent
`captive-portal.service` itself from starting.

The existing:

```text
/etc/default/captive-portal
```

remains the ordinary CaptivPortal EnvironmentFile and remains authoritative
for the existing main-process configuration domains.

The NI-02B file is loaded additionally only so the main process can consume the
existing `NETWORK_METADATA_PROJECTION_*` configuration through the existing
NI-02B configuration owner.

---

# 4. ENVIRONMENT COLLISION RULE

The NI-02B environment file currently also carries reused upstream variable names.

Therefore production activation MUST perform a collision check before enabling
NI-03.

Permanent rule:

```text
NETWORK_METADATA_PROJECTION_*
MUST NOT be independently duplicated
in /etc/default/captive-portal.
```

For any other environment key present in BOTH:

```text
/etc/default/captive-portal

and

/etc/captive-portal/network-metadata-projection.env
```

the deployment gate MUST prove:

```text
effective values are semantically identical
```

before NI-03 activation.

If a duplicate non-projection key differs:

```text
ACTIVATION = HOLD
```

because the later systemd EnvironmentFile would otherwise create an unintended
main-process configuration override.

This collision gate is deployment validation.

It does NOT create a second source of truth.

The sole authority for:

```text
NETWORK_METADATA_PROJECTION_ENABLED
NETWORK_METADATA_PROJECTION_DB_PATH
NETWORK_METADATA_PROJECTION_MAX_DB_BYTES
```

remains:

```text
/etc/captive-portal/network-metadata-projection.env
```

---

# 5. MAIN-PROCESS CONFIGURATION COMPOSITION

When:

```text
WEB_ADMIN_ENABLED=true
AND
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true
```

the `captive-portal.service` startup composition MUST obtain NI-02B read
configuration by calling the existing:

```text
projection_config_from_env()
```

against the process environment produced by systemd.

No route-level environment read is allowed.

No request-time EnvironmentFile read is allowed.

No independent `os.getenv()` resolution in:

```text
route
AdminQueryService
DeviceProtocolIntelligenceReadService
template
JavaScript
```

is allowed.

The configuration is startup-derived and immutable for that
`captive-portal.service` process lifetime.

---

# 6. OPTIONAL-CONSUMER FAILURE BOUNDARY

NI-03 remains an optional read-only Admin product.

Therefore failure to obtain a usable NI-02B read configuration MUST NOT break:

```text
Guest Portal
CAPPORT
Authorization
existing Admin Web
existing Device Card
```

Exact startup behavior when NI-03 is enabled:

```text
projection_config_from_env() returns enabled=false
→ NI-03 dependency state = projection_disabled

projection_config_from_env() raises validation error
→ NI-03 dependency state = projection_configuration_unavailable

valid config + projection DB unavailable/untrusted
→ NI-03 dependency state = projection_store_unavailable
```

The main Admin application still starts.

The NI-03 endpoint translates all three dependency-unavailable states to the
already accepted safe API failure:

```text
HTTP 503
error = source_unavailable
```

No private configuration error is exposed to the browser.

---

# 7. EXACT MEANING OF "NI-02B DISABLED"

For NI-03, NI-02B is disabled only when the canonical startup-derived:

```text
ProjectionConfig.enabled == false
```

as returned by:

```text
projection_config_from_env()
```

This includes the default case where:

```text
NETWORK_METADATA_PROJECTION_ENABLED
```

is absent and the canonical NI-02B default resolves to:

```text
false
```

NI-03 MUST NOT infer enabled state from:

```text
DB file existence
DB file age
projection_runtime_state row
systemctl state
PID
socket
filesystem timestamp
```

The deployment configuration flag is the authority for enabled/disabled state.

---

# 8. OLD PROJECTION DB WHILE NI-02B IS DISABLED

If:

```text
ProjectionConfig.enabled == false
```

and an old:

```text
network_metadata_projection.sqlite3
```

still exists:

```text
NI-03 MUST NOT open it
NI-03 MUST NOT read historical edges from it
NI-03 MUST NOT present it as stale fallback
```

Result when NI-03 feature itself is enabled:

```text
HTTP 503 source_unavailable
```

This preserves the parent-v1 decision:

```text
deployment-disabled projection
!=
permission to read an old derived store
```

---

# 9. NI-03 FEATURE OFF

If:

```text
WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false
```

then:

```text
NI-03 server composition is absent/inert
NI-03 Device Card section is absent
NI-03 API remains unavailable according to parent-v1 feature-gate semantics
```

The presence or absence of the NI-02B EnvironmentFile does not activate NI-03.

Loading the optional systemd EnvironmentFile MUST NOT itself activate product
behavior.

---

# 10. `NETWORK_METADATA_PROJECTION_MAX_DB_BYTES`

NI-03 receives the canonical value only through the same `ProjectionConfig`.

NI-03 MUST NOT:

```text
change the cap
enforce a second writer-cap algorithm
repair capacity
checkpoint WAL
truncate WAL
change projection runtime state
```

The value is configuration provenance for the shared NI-02B read composition
and future safe diagnostics only.

NI-02B remains the sole writer/capacity owner.

---

# 11. NO `systemctl` IN APPLICATION REQUEST PATH

NI-03 MUST NOT determine NI-02B enabled/running state by:

```text
systemctl
systemd D-Bus
process enumeration
PID lookup
service status command
```

from the Admin request path.

The Admin application consumes:

```text
startup configuration
+
NI-02B projection-store runtime state
```

only.

Systemd inspection belongs to deployment/operations validation.

---

# 12. DEPLOYMENT OWNERSHIP

The systemd drop-in is an infrastructure/deployment artifact.

Ownership:

```text
Architect
→ freezes requirement and semantics

Tech Lead
→ includes exact deployment artifact/change in implementation/deployment contract

Coder
→ may add repository deployment artifact only if explicitly authorized by TASK

SysAdmin / DeployLead
→ installs/verifies production drop-in after Owner authorization
```

Application code MUST NOT create or modify:

```text
/etc/systemd/system/captive-portal.service.d/
```

at runtime.

---

# 13. PRODUCTION ACTIVATION SEQUENCE — R1 EXACT

After accepted NI-03 implementation is merged/deployed, production activation is
a separate Owner-authorized operation.

Exact sequence:

```text
1. Verify exact accepted Git HEAD/TREE.

2. Verify network-metadata-projection.service remains on its existing
   /etc/captive-portal/network-metadata-projection.env.

3. Install:
   /etc/systemd/system/captive-portal.service.d/
   20-network-metadata-projection-read.conf

4. Verify /etc/default/captive-portal does NOT define independent
   NETWORK_METADATA_PROJECTION_* duplicates.

5. Verify any other duplicate environment keys across the two EnvironmentFiles
   are semantically identical.
   Any mismatch → HOLD.

6. systemd daemon-reload.

7. Keep:
   WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false

8. Restart captive-portal.service.

9. Verify protected Portal/CAPPORT/Admin baseline behavior.

10. Verify the main process received the canonical NI-02B projection
    configuration without printing secret environment values.

11. Separately set:
    WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=true

12. Restart captive-portal.service.

13. Verify exact NI-03 Admin API/Device Card behavior.

14. Verify network-metadata-projection.service remains independently healthy
    or exposes its accepted degraded state without NI-03 mutating it.

15. Run the accepted NI-03 production smoke/privacy/concurrency checks.
```

The drop-in install and NI-03 product activation are separate steps.

---

# 14. PRODUCTION ROLLBACK — R1 EXACT

Fast product rollback:

```text
1. set:
   WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false

2. restart captive-portal.service

3. verify NI-03 section/API are no longer active

4. verify protected Portal/CAPPORT/Admin baseline
```

No NI-02B DB mutation.

No NI-02B service restart is required.

Full NI-03 infrastructure rollback, if required:

```text
1. feature OFF

2. remove:
   /etc/systemd/system/captive-portal.service.d/
   20-network-metadata-projection-read.conf

3. systemd daemon-reload

4. restart captive-portal.service

5. verify baseline

6. leave:
   /etc/captive-portal/network-metadata-projection.env
   network-metadata-projection.service
   projection DB
   unchanged
```

---

# 15. P1-01 ACCEPTANCE ADDITIONS

Mandatory acceptance:

```text
A1
NI-03 feature=false
→ captive-portal works
→ NI-03 not exposed

A2
NI-03 feature=true
+
projection env absent
→ main service starts
→ NI-03 = 503 source_unavailable

A3
NI-03 feature=true
+
NETWORK_METADATA_PROJECTION_ENABLED=false
+
old projection DB exists
→ DB is NOT opened
→ 503 source_unavailable

A4
NI-03 feature=true
+
canonical projection enabled=true
+
valid DB path
→ reader uses canonical ProjectionConfig.db_path

A5
NETWORK_METADATA_PROJECTION_DB_PATH present only in existing NI-02B env
→ no Admin alias required

A6
NETWORK_METADATA_PROJECTION_MAX_DB_BYTES comes from same canonical config
→ no second literal/default in NI-03

A7
duplicate NETWORK_METADATA_PROJECTION_* in /etc/default/captive-portal
→ activation FAIL/HOLD

A8
other duplicate env key differs across EnvironmentFiles
→ activation FAIL/HOLD

A9
no route/request-time getenv/file parse/systemctl

A10
projection config validation failure
→ Admin/core remain available
→ NI-03 503 source_unavailable

A11
drop-in rollback
→ captive-portal returns to old EnvironmentFile boundary
→ NI-02B service/store unchanged
```

---

# 16. P1-01 DISPOSITION

```text
P1-01 = RESOLVED
```

---

# 17. P1-02 — DEVICE_ID LOG PRIVACY VS CURRENT NGINX ACCESS LOG

## 17.1. Selected architecture

Выбран:

```text
OPTION A
```

The NI-03 no-`device_id` observability invariant is explicitly scoped to:

```text
APPLICATION / NI-03 TELEMETRY
```

It is NOT an absolute statement that no infrastructure log may contain the
route identifier.

The existing Admin reverse-proxy access log is admitted unchanged for NI-03 V1.

---

# 18. WHY OPTION A IS THE V1 CONTRACT

The frozen endpoint remains:

```text
GET /admin/api/v1/sites/<site_id>/devices/<device_id>/protocol-intelligence
```

Current Admin Nginx access logging records:

```text
$request_method
$uri
$server_protocol
```

under the existing:

```text
web_admin_safe
```

format.

Therefore the route's `device_id` is structurally present in infrastructure
access logging.

NI-03 V1 accepts this existing Admin reverse-proxy behavior rather than
introducing a special Nginx redaction path for one endpoint.

This does NOT authorize application-layer logging of `device_id`.

---

# 19. PRIVACY BOUNDARIES — EXACT

Three logging/telemetry domains are distinguished.

## 19.1. NI-03 application logs / metrics

MUST NOT contain:

```text
device_id
MAC
raw IP
port
DNS name
SNI
edge payload
protocol history for one Device
raw Registry row
NI-02A binding ID
```

Allowed bounded application context:

```text
request_id
Site ID
safe failure category
HTTP status class
row-count bucket
duration bucket
```

## 19.2. Browser / NI-03 client telemetry

MUST NOT emit:

```text
device_id
MAC
raw endpoint data
protocol-history payload
stack traces
```

through a new NI-03 telemetry channel.

The route URL used by the browser necessarily contains `device_id`; this is not
a separate client telemetry event.

## 19.3. Reverse-proxy / infrastructure access logging

The existing Nginx Admin access log MAY contain:

```text
device_id
```

only because it is embedded in the already-authorized Admin URI logged through:

```text
$uri
```

NI-03 does NOT add:

```text
$request_uri
query string logging
request body logging
response body logging
Authorization header logging
Cookie logging
```

to the Admin access-log contract.

Infrastructure access-log retention/access control remain governed by the
existing production logging/security policy.

---

# 20. NO NGINX CHANGE IN NI-03 R1

NI-03 R1 requires:

```text
NO Nginx route change
NO Nginx log-format change
NO endpoint rewrite
NO device_id redaction layer
```

The existing:

```text
/admin/
web_admin_safe
```

reverse-proxy logging contract remains unchanged.

Therefore:

```text
NGINX DEPLOYMENT ARTIFACT CHANGE = NO
NGINX RELOAD = NO
NGINX ROLLBACK = NOT REQUIRED
```

for NI-03 itself.

If a future policy requires:

```text
device_id MUST NOT appear in ANY infrastructure log
```

that is a separate architecture/security stage requiring either:

```text
reverse-proxy URI redaction
or
route identity redesign
```

and is OUT of NI-03 V1.

---

# 21. REPLACEMENT FOR v1 "OBSERVABILITY PRIVACY"

The parent-v1 observability privacy clause is replaced by:

```text
NI-03 application-generated logs, metrics and telemetry MUST NOT contain:

MAC
device_id
raw IP
port
DNS name
SNI
edge payload
protocol history list for one Device
raw Registry row
NI-02A binding ID.

Allowed application diagnostic context:

request_id
Site ID
safe failure category
row-count bucket
duration bucket
HTTP status class.

This prohibition applies to application/NI-03 telemetry and does not redefine
the existing reverse-proxy Admin access-log contract.

The existing Nginx web_admin_safe access log may record device_id as part of
$uri for the frozen Admin Device route.

NI-03 introduces no additional URI/query/body/header logging.
```

---

# 22. REPLACEMENT FOR v1 "ACCEPTANCE — PRIVACY"

The parent-v1 privacy acceptance clause is replaced by:

```text
APPLICATION/API/UI PRIVACY

Prove NI-03 public API payload, rendered product content,
application logs, application metrics and NI-03 telemetry do NOT expose/log:

DNS names
SNI
remote IP
remote port
MAC
edge_id
raw Registry row
NI-02A binding
raw projection runtime reason
device_id in application-generated log/metric fields.

API path identity is exempt only as required by the frozen route itself.

REVERSE-PROXY EXPECTATION

Prove the existing Nginx web_admin_safe access log remains unchanged and may
contain:

site_id
device_id

inside $uri.

Prove NI-03 introduces no:

$request_uri
query-string
request-body
response-body
Authorization-header
Cookie

logging.

The expected device_id occurrence in the existing reverse-proxy URI log is
NOT an NI-03 privacy-test failure.
```

---

# 23. APPLICATION ERROR LOGGING

When NI-03 handles:

```text
400
401
403
404
429
500
503
```

application logs MUST use:

```text
request_id
Site ID where safely available
safe error category
status class
```

and MUST NOT interpolate the full request path when that path contains
`device_id`.

Framework/default request logging under the application's direct control MUST
not introduce a second application-level raw-URI log for this endpoint.

The admitted raw URI occurrence remains only the existing reverse-proxy access
logging boundary unless a pre-existing framework log outside NI-03 already
exists and is governed separately.

---

# 24. P1-02 ACCEPTANCE ADDITIONS

Mandatory:

```text
B1
NI-03 API request succeeds
→ application NI-03 logs contain no device_id field/value

B2
NI-03 4xx/5xx request
→ application error log contains no raw path/device_id

B3
NI-03 metrics
→ no device_id label

B4
NI-03 browser telemetry
→ no device_id payload

B5
Nginx web_admin_safe
→ existing $uri behavior preserved
→ device_id in URI is explicitly accepted infrastructure logging

B6
no new $request_uri/query/body/header logging

B7
no Nginx configuration change required for NI-03

B8
privacy documentation/tests distinguish:
application telemetry
vs
reverse-proxy access logging
```

---

# 25. P1-02 DISPOSITION

```text
P1-02 = RESOLVED
```

---

# 26. R1 CONSOLIDATED INVARIANTS

```text
NI03-R1-I01
There is one NI-02B projection configuration authority.

NI03-R1-I02
NETWORK_METADATA_PROJECTION_* values are not duplicated into NI-03 aliases.

NI03-R1-I03
captive-portal.service receives NI-02B configuration from the existing
/etc/captive-portal/network-metadata-projection.env.

NI03-R1-I04
The existing projection_config_from_env() remains the canonical parser.

NI03-R1-I05
NI-02B disabled means canonical ProjectionConfig.enabled=false.

NI03-R1-I06
Old projection DB existence never implies enabled.

NI03-R1-I07
Disabled NI-02B projection DB is not opened as stale fallback.

NI03-R1-I08
Admin request path never queries systemd for NI-02B state.

NI03-R1-I09
Projection configuration failure degrades NI-03, not protected Portal/Admin core.

NI03-R1-I10
Systemd EnvironmentFile handoff is deployment-owned.

NI03-R1-I11
Application/NI-03 telemetry never logs device_id.

NI03-R1-I12
Existing Nginx Admin access logging may contain device_id only as part of $uri.

NI03-R1-I13
NI-03 introduces no new reverse-proxy query/body/header logging.

NI03-R1-I14
Absolute infrastructure-wide device_id redaction is OUT of NI-03 V1.
```

---

# 27. R1 IMPACT ON PARENT CONTRACT

Normatively amended parent sections:

```text
Admin runtime composition
NI-02B disabled semantics
production activation
rollback
observability privacy
privacy acceptance
```

Unchanged parent decisions include:

```text
NI-03 bounded read-time aggregation
DeviceProtocolSummaryV1
24h summary
60m Recent Protocols
fresh/recent/stale semantics
admin.read.device
frozen Admin endpoint
read-only NI-02B access
same-snapshot requirement
browser polling
query bounds
failure isolation
no new DB/service/writer
no NI-04 service recognition
```

---

# 28. FINAL R1 DISPOSITION

```text
TASK =
TASK-DTI-NI-03

ARCHITECTURE CONTRACT =
v1-R1

BASELINE =
main@3467da8abd4ad4bb5b381a13e374e2e8faf4685e

P1-01 =
RESOLVED

P1-02 =
RESOLVED

OPEN_P0 =
0

OPEN_P1 =
0

OPEN_P2 =
0

READY_FOR_TECH_LEAD_IMPLEMENTATION_CONTRACT =
YES

TECH_LEAD_RE-REVIEW =
PENDING

IMPLEMENTATION_AUTHORIZATION =
NO

CODER =
HOLD

PRODUCTION_CHANGE =
NO
```

---

# 29. NEXT GOVERNANCE STEP

```text
Architect
→ TASK-DTI-NI-03 Architecture Contract v1-R1

Tech Lead
→ bounded re-review

if PASS:

Tech Lead
→ exact implementation contract / Coder TASK

then and only then:

IMPLEMENTATION_AUTHORIZATION may change
CODER may leave HOLD
```
