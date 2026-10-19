# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 4 — OMADA CONTROLLER SECRET MANAGEMENT
### ARCHИТЕКТУРНЫЙ КОНТРАКТ v0.1-R1
### BOUNDED R1 — FINAL CANDIDATE FOR TECH LEAD RE-REVIEW

**Проект:** CaptivPortal  
**Область:** Admin UI → Settings → Controller  
**Этап:** Stage 4 — Omada Controller Secret Management  
**Роль:** Architect  
**Статус:** `DRAFT FOR TECH LEAD RE-REVIEW`

---

# 0. BASELINE / НОРМАТИВНАЯ СВЯЗЬ С v0.1

Authoritative baseline:

```text
HEAD =
78296b2e9a35664c0d285cf0c7d22b2fa465311a

TREE =
f965d4604652db52d5f97b1f5d3abe36263ee78b
```

Tech Lead disposition:

```text
OVERALL DIRECTION = ACCEPTED
REDESIGN = NO
```

Этот R1 является **bounded revision** исходного:

```text
CAPTIVPORTAL ADMIN SETTINGS
STAGE 4 — OMADA CONTROLLER SECRET MANAGEMENT
ARCHITECTURE CONTRACT v0.1
```

R1 изменяет только:

```text
P1-01 — AUTHORIZATION MODEL
P1-02 — OLD SECRET "DESTRUCTION"
TL-S4-B1 — SETTINGS DB FILE SECURITY
TL-S4-B2 — BROWSER STORAGE CLAIM
TL-S4-B3 — CRYPTOGRAPHY DEPENDENCY
```

Все остальные решения v0.1 остаются нормативными и не переоткрываются.

Текущий gate:

```text
IMPLEMENTATION TASK = HOLD
CODER = HOLD
PRODUCTION CHANGE = NO
SYSTEMD ACTION = NO
```

---

# 1. P1-01 — AUTHORIZATION MODEL
## РЕШЕНИЕ: OPTION A — REAL STRONGER CAPABILITY

Stage 4 сохраняет отдельную capability:

```text
admin.write.settings.controller.secret
```

и делает её **реально независимо назначаемой** от:

```text
admin.write.settings.controller
```

Текущая модель:

```text
principal_type == platform_operator
+
capability in GLOBAL_SETTINGS_CAPABILITIES
```

больше не является достаточной global authorization model.

---

# 2. CAPABILITY ASSIGNMENT OWNER / SOURCE

Owner назначения global capabilities в Stage-4 V1:

```text
deployment / process configuration
```

Exact configuration key:

```text
WEB_ADMIN_GLOBAL_CAPABILITIES
```

Он:

```text
process-environment controlled
read once at Admin runtime startup
NOT Admin-Settings writable
NOT Site-scoped
NOT stored in SettingsStore
NOT hot-reloaded
```

Canonical syntax:

```text
comma-separated exact capability identifiers
```

Example Stage-3-compatible value:

```text
admin.read.settings.global,admin.write.settings.global,admin.read.settings.controller,admin.write.settings.controller
```

Example with Stage-4 secret-write authorization:

```text
admin.read.settings.global,admin.write.settings.global,admin.read.settings.controller,admin.write.settings.controller,admin.write.settings.controller.secret
```

Parser requirements:

```text
ASCII only
no empty token
no duplicate token
no unknown capability
no leading/trailing whitespace in token
maximum 16 global capabilities
maximum 128 ASCII bytes per capability token
```

Malformed or unknown capability configuration:

```text
Admin Web configuration fails closed
```

No unknown capability is ignored.

---

# 3. RECOGNIZED GLOBAL CAPABILITY SET

Stage-4 V1 recognized global capabilities are exactly:

```text
admin.read.settings.global

admin.write.settings.global

admin.read.settings.controller

admin.write.settings.controller

admin.write.settings.controller.secret
```

Code-owned recognized capability allowlist remains authoritative.

The current concept equivalent to:

```text
GLOBAL_SETTINGS_CAPABILITIES
```

may remain as the **recognized capability allowlist**, but it MUST NOT mean:

```text
all platform_operator principals automatically receive all capabilities
```

---

# 4. DEFAULT CAPABILITY SET FOR EXISTING PRODUCTION ADMIN

If:

```text
WEB_ADMIN_GLOBAL_CAPABILITIES
```

is not explicitly supplied, repository/default Stage-4 V1 capability set is exactly the Stage-3 behavior:

```text
admin.read.settings.global

admin.write.settings.global

admin.read.settings.controller

admin.write.settings.controller
```

It explicitly DOES NOT include:

```text
admin.write.settings.controller.secret
```

Therefore Stage-4 deployment preserves all existing Admin Settings access but secret replacement is fail-closed until deployment explicitly grants the new capability.

No migration implicitly grants secret-write authority.

---

# 5. `AdminPrincipal` REPRESENTATION

Stage-4 V1 principal representation becomes conceptually:

```text
AdminPrincipal {
    username
    principal_type
    global_capabilities: frozenset[str]
}
```

For the current single production Admin account:

```text
username
→ validated WEB_ADMIN_USERNAME

principal_type
→ platform_operator

global_capabilities
→ validated WEB_ADMIN_GLOBAL_CAPABILITIES snapshot
```

Capabilities are authorization metadata, not secret data.

---

# 6. AUTHENTICATED USER → CAPABILITY SET

Current Stage-4 V1 still has one configured Admin username/password identity.

After successful credential authentication:

```text
validated AdminWebConfig.global_capabilities
        ↓
captured into AdminPrincipal
        ↓
captured into AdminSession
```

No request-time environment re-read is permitted.

No route infers secret permission solely from:

```text
principal_type == platform_operator
```

---

# 7. `authorize_global()` SEMANTICS

Canonical Stage-4 global authorization:

```text
principal is valid AdminPrincipal
AND
principal.principal_type == "platform_operator"
AND
requested capability is in recognized global capability allowlist
AND
requested capability is in principal.global_capabilities
```

Otherwise:

```text
DENY
```

This makes:

```text
admin.write.settings.controller
```

and:

```text
admin.write.settings.controller.secret
```

independently representable and independently enforceable.

Site-read authorization semantics outside this bounded return remain unchanged.

---

# 8. SESSION CAPTURE SEMANTICS

Capabilities are immutable session-time authorization state.

Each `AdminSession` captures the exact `AdminPrincipal`, including:

```text
global_capabilities
```

at successful login.

A session does NOT re-resolve capabilities on every request.

This preserves deterministic session authorization and avoids partial hot changes.

---

# 9. CAPABILITY CHANGE SEMANTICS

Changing:

```text
WEB_ADMIN_GLOBAL_CAPABILITIES
```

requires:

```text
external captive-portal.service restart
+
new Admin login
```

because:

```text
configuration is startup-resolved
sessions are process-local
existing sessions are not dynamically rewritten
```

Stage 4 adds:

```text
NO Admin restart button
NO capability hot reload
NO capability mutation API
```

After process restart, previous in-memory Admin sessions cease to exist naturally.

Therefore new capability assignment is effective only in sessions created by the new process.

---

# 10. AUTHORIZATION FAIL-CLOSED RULES

Fail closed when:

```text
capability config malformed
unknown capability present
principal missing global_capabilities
requested capability unknown
principal type not platform_operator
session principal invalid
```

Absence of:

```text
admin.write.settings.controller.secret
```

always means:

```text
secret mutation forbidden
```

No fallback to ordinary Controller write permission.

---

# 11. BACKWARD COMPATIBILITY

Existing Stage-3 production behavior is preserved by default:

```text
existing Admin
retains:
admin.read.settings.global
admin.write.settings.global
admin.read.settings.controller
admin.write.settings.controller
```

New secret capability is opt-in:

```text
admin.write.settings.controller.secret
```

No existing login credential format changes.

No existing Site allowlist semantics change.

No principal database is introduced in Stage-4 V1.

No multi-user Admin account system is introduced.

---

# 12. SECRET ROUTE AUTHORIZATION

The write-only secret endpoint continues to require:

```text
authenticated Admin session
+
admin.read.settings.controller
+
admin.write.settings.controller.secret
```

The ordinary non-secret Controller endpoint continues to require:

```text
admin.write.settings.controller
```

Therefore these production authorization states are now representable:

```text
A.
read Controller only

B.
read Controller + edit non-secret Controller fields

C.
read Controller + replace Client Secret
   without ordinary Controller mutation authority

D.
read Controller + both ordinary and secret write authority
```

UI controls follow the same principal capability snapshot.

---

# 13. P1-01 DISPOSITION

```text
P1-01 = CLOSED

SELECTED MODEL =
OPTION A — REAL STRONGER CAPABILITY

CAPABILITY OWNER =
deployment / startup Admin configuration

ASSIGNMENT SOURCE =
WEB_ADMIN_GLOBAL_CAPABILITIES

DEFAULT EXISTING ADMIN =
all existing Stage-3 global Settings capabilities
WITHOUT secret-write capability

SESSION MODEL =
capability snapshot captured at login

CAPABILITY CHANGE =
restart + re-login

SECRET CAPABILITY =
independently assignable
```

---

# 14. P1-02 — OLD SECRET "DESTRUCTION"
## НОРМАТИВНАЯ КОРРЕКЦИЯ

Все формулировки v0.1 вида:

```text
securely destroyed

destroyed in same mutation transaction

old-secret destruction

destroyed atomically during adoption
```

заменяются.

Correct terminology:

```text
logically deleted from the live controller_secret_versions table
```

и:

```text
no longer retained as an addressable live managed-secret version
```

---

# 15. LIVE SECRET-VERSION RETENTION INVARIANT

Полезный live-state invariant сохраняется:

```text
controller_secret_versions
retains only encrypted versions referenced by:

current configured ownership
and/or
current effective ownership
```

Нормально:

```text
configured == effective
→ 1 live managed secret version

configured != effective
with different managed versions
→ at most 2 live managed secret versions
```

Когда version больше не referenced current configured/effective ownership:

```text
DELETE corresponding live row
inside the same SettingsStore transaction
```

где это предусмотрено v0.1.

Это **logical deletion from live relational state**.

---

# 16. SUPERSEDED PENDING SECRET

Если новый replacement supersedes ещё не activated pending secret:

```text
old pending version
becomes unreferenced by both
configured and effective ownership
```

Тогда в той же mutation transaction:

```text
its row is logically deleted
from controller_secret_versions
```

После commit этот version больше:

```text
не addressable
не selectable
не available through live secret repository
```

Но это НЕ forensic secure erase.

---

# 17. PREVIOUS EFFECTIVE SECRET AFTER ADOPTION

После durable adoption новой generation:

```text
old effective secret version
may become unreferenced
```

Тогда в той же activation transaction:

```text
its live controller_secret_versions row
is logically deleted
```

Нормативная формулировка:

```text
activation commit
+
logical deletion of unreferenced live secret-version row
are atomic in the live SettingsStore state
```

Нельзя говорить:

```text
cryptographically destroyed
securely erased from media
physically destroyed
```

---

# 18. FORENSIC ERASURE NON-GUARANTEE

Stage 4 V1 explicitly DOES NOT guarantee forensic secure erasure of historical secret material from:

```text
SQLite free pages

SQLite WAL remnants

SQLite journal remnants

filesystem free blocks

filesystem/media remnants

VM/storage snapshots

hypervisor snapshots

filesystem snapshots

historical Settings DB backups

off-host backups

backup media
```

SQLite DELETE guarantees logical relational deletion only.

It does not prove physical byte erasure.

---

# 19. STATIC MASTER KEY CONSEQUENCE

Stage 4 V1 uses one static external master key.

Therefore:

```text
historical Settings DB backup
+
matching master-key backup
```

may remain capable of decrypting managed secret ciphertext contained in that historical backup.

The live transaction cannot revoke already-created external copies.

This is accepted Stage-4 V1 behavior.

---

# 20. BACKUP RETENTION / DESTRUCTION OWNER

Backup retention, expiry and destruction are:

```text
OPERATIONAL SECURITY POLICY
OUTSIDE atomic Settings mutation/adoption transaction
```

The application cannot claim deletion of:

```text
old backups
VM snapshots
filesystem snapshots
offline copies
```

merely because a live `controller_secret_versions` row was deleted.

Production runbook must separately define backup retention/destruction policy.

That policy is not an Admin mutation operation.

---

# 21. TRUE CRYPTOGRAPHIC DESTRUCTION

If a future requirement demands:

```text
cryptographic destruction of one historical secret
even when old ciphertext copies remain
```

the current Stage-4 V1 design is insufficient because retained/historical ciphertext uses a static master-key lineage.

Such a requirement needs a different architecture, for example independent erasable per-version key material / envelope-key lifecycle.

That is explicitly:

```text
OUT OF STAGE 4 V1
```

No such guarantee is claimed here.

---

# 22. SECRET HISTORY / RECOVERY REMAINS UNCHANGED

Despite forensic-erasure clarification, Stage-4 product semantics remain:

```text
NO secret history UI
NO secret read-back
NO previous-secret selector
NO rollback to previous managed secret without knowing/re-entering it
```

Recovery remains:

```text
replace with known-good secret

OR

clear managed override
→ deployment/environment fallback

OR

restore an explicitly chosen coherent historical backup
with its matching master key
```

Backup restore is operational recovery, not live secret-history browsing.

---

# 23. P1-02 DISPOSITION

```text
P1-02 = CLOSED

LIVE ROW RETENTION =
only versions referenced by configured/effective ownership

UNREFERENCED VERSION =
logically deleted from live controller_secret_versions

FORENSIC SECURE ERASE =
NOT GUARANTEED

BACKUP DESTRUCTION =
operational policy outside Settings transaction

TRUE CRYPTOGRAPHIC DESTRUCTION =
OUT OF STAGE 4 V1
```

---

# 24. TL-S4-B1 — SETTINGS DB FILE SECURITY
## РЕШЕНИЕ: APPLICATION VALIDATES ONLY

Selected model:

```text
OPTION A
```

Application:

```text
VALIDATES Settings DB/path security
```

Application MUST NOT:

```text
chmod settings.sqlite3
chgrp settings.sqlite3
chown settings.sqlite3

chmod/chgrp/chown master-key file

silently repair filesystem permissions
```

Permission transition is deployment/operator ownership.

---

# 25. SETTINGS DB REQUIRED FILE SECURITY

For Stage-4 secret management, canonical DB:

```text
/opt/CaptivePortal/data/settings.sqlite3
```

must satisfy:

```text
regular file
not symlink

owner =
admin

group =
admin

mode =
0600

hard-link count =
1
```

No group/other read or write permission is accepted for Stage-4 secret-store availability.

---

# 26. SETTINGS DB PARENT PATH SECURITY

Canonical parent:

```text
/opt/CaptivePortal/data
```

must satisfy:

```text
actual directory
not symlink

owner =
admin

group =
deployment-defined
```

Group identity itself is not required to be `admin`, because current production uses:

```text
group=telemetry
```

However mandatory permission rule is:

```text
group MUST NOT have write permission
other MUST NOT have write permission
```

Setgid is allowed.

Current production parent:

```text
owner=admin
group=telemetry
mode=2750
```

is therefore structurally acceptable for Stage-4 parent-path security.

The DB file itself is not currently acceptable for secret management until explicit permission transition.

---

# 27. CURRENT PRODUCTION PERMISSION TRANSITION

Observed current production state:

```text
/opt/CaptivePortal/data/settings.sqlite3

owner=admin
group=telemetry
mode=0644
```

Stage 4 requires before first managed-secret write:

```text
owner=admin
group=admin
mode=0600
```

This is:

```text
explicit Stage-4 deployment precondition
```

and NOT:

```text
Stage-3 defect
```

Application architecture review does NOT authorize performing this mutation now.

---

# 28. `secret_store_state=available` BINDING

`secret_store_state=available` is allowed ONLY if all required conditions are trustworthy:

```text
SettingsStore schema/integrity valid

Settings DB canonical path valid

Settings DB is regular file

Settings DB is not symlink

Settings DB owner=admin

Settings DB group=admin

Settings DB mode=0600

Settings DB hard-link count=1

parent directory/path security checks PASS

master-key file structurally valid

master-key owner/group/mode checks PASS

master-key is regular file

master-key is not symlink

master-key hard-link count=1

master-key size=32 bytes

crypto initialization PASS
```

Otherwise:

```text
secret_store_state = unavailable
```

No optimistic `available`.

---

# 29. FILE-SECURITY FAILURE BEHAVIOR

If mandatory Settings DB file-security checks fail:

```text
ordinary Stage-3 SettingsStore
may still be logically readable according to existing behavior
```

but Stage-4 secret management is:

```text
UNAVAILABLE
```

Secret mutation endpoint returns safe:

```text
503 controller_secret_store_unavailable
```

and does not expose which filesystem metadata failed in the browser response.

Safe server logs may contain bounded reason code such as:

```text
settings_db_file_security_invalid
```

without secret data.

---

# 30. STARTUP WITH MANAGED SECRET + DB SECURITY FAILURE

If configured generation explicitly references a managed secret and Stage-4 DB file-security validation fails:

```text
startup fails closed
before managed secret resolution/provider construction
```

No fallback to:

```text
environment
repository_default
```

because configured ownership explicitly belongs to managed secret.

If no managed binding exists:

```text
deployment/environment secret may continue to drive runtime
```

while:

```text
secret_store_state = unavailable
secret mutation = unavailable
```

This matches existing Stage-4 fail-closed ownership semantics.

---

# 31. TL-S4-B1 DISPOSITION

```text
TL-S4-B1 = BOUND

APPLICATION FILE-PERMISSION AUTHORITY =
VALIDATE ONLY

APPLICATION chmod/chgrp/chown SETTINGS DB =
NO

APPLICATION chmod/chgrp/chown MASTER KEY =
NO

SECRET STORE AVAILABLE =
only after DB + key + schema + crypto security checks PASS

CURRENT PRODUCTION DB =
requires explicit Stage-4 deployment permission transition
before managed-secret write
```

---

# 32. TL-S4-B2 — BROWSER STORAGE CLAIM
## НОРМАТИВНОЕ УТОЧНЕНИЕ

Stage-4 browser guarantee is limited to:

```text
APPLICATION-CONTROLLED PERSISTENCE
```

The application MUST NOT intentionally persist raw secret in:

```text
URL
query string
URL fragment
localStorage
sessionStorage
cookies
history state
HTML/bootstrap JSON
data-* attributes
client telemetry
client logging
generic Controller JS model
application cache/state
```

---

# 33. PASSWORD FIELD / USER-AGENT BOUNDARY

Stage 4 retains:

```text
type=password
autocomplete=new-password
```

for both replacement fields.

This is an application hint to the user agent.

Stage 4 explicitly DOES NOT guarantee what external/browser-controlled components do, including:

```text
browser password manager
browser internal memory
browser extension
accessibility software
endpoint security software
OS input services
third-party tooling
```

If a browser/password manager chooses to offer or retain the new credential despite `autocomplete=new-password`, that behavior is outside CaptivPortal application control.

Stage 4 does not claim browser-level secure erasure.

---

# 34. APPLICATION-CONTROLLED CLEARING

CaptivPortal application code MUST:

On cancel:

```text
clear both password input values
clear application JS references
close replacement UI
send no request
```

On every completed submit attempt, including:

```text
success
validation failure
403
409
412
413
500
503
network failure
```

application code MUST in a `finally`-equivalent path:

```text
clear both input values
drop application-held secret references
```

No guarantee is made that JS engine/browser/OS has physically erased all memory copies.

---

# 35. UNCERTAIN NETWORK RETRY

Application may retain only:

```text
Idempotency-Key
```

in ephemeral application memory for retry.

Application MUST NOT retain:

```text
raw secret
```

for retry.

User must re-enter secret.

Same Idempotency-Key may be reused according to the accepted HMAC replay contract.

---

# 36. TL-S4-B2 DISPOSITION

```text
TL-S4-B2 = BOUND

NO APPLICATION-CONTROLLED SECRET PERSISTENCE =
REQUIRED

PASSWORD MANAGER / USER-AGENT PERSISTENCE =
OUTSIDE APPLICATION CONTROL

APPLICATION FIELD CLEARING =
REQUIRED

SECURE BROWSER MEMORY ERASURE CLAIM =
NO
```

---

# 37. TL-S4-B3 — CRYPTOGRAPHY DEPENDENCY

Stage 4 introduces one explicit runtime dependency:

```text
cryptography
```

Supported Stage-4 V1 floor:

```text
cryptography >= 3.4.8
```

Required APIs:

```text
cryptography.hazmat.primitives.ciphers.aead.AESGCM

cryptography.hazmat.primitives.kdf.hkdf.HKDF

cryptography.hazmat.primitives.hashes.SHA256
```

Production currently has:

```text
cryptography 3.4.8
```

which is the minimum supported Stage-4 V1 version.

---

# 38. CRYPTO COMPATIBILITY REQUIREMENT

Implementation MUST remain compatible with:

```text
cryptography 3.4.8
```

and MUST NOT rely on newer cryptography APIs without a later reviewed dependency change.

Mandatory implementation evidence before production eligibility:

```text
actual runtime cryptography version

successful import of AESGCM

successful import/use of HKDF

successful import/use of SHA256

AES-256-GCM encrypt/decrypt test

tampered ciphertext/tag rejection test

HKDF deterministic-vector test

Stage-4 targeted tests executed against supported dependency floor
or equivalent controlled compatibility evidence
```

---

# 39. NO PACKAGE INSTALL AUTHORITY

This architecture review authorizes:

```text
dependency requirement
```

It does NOT authorize:

```text
pip install
apt install
package upgrade
package downgrade
production package mutation
```

If implementation/deployment environment lacks a compatible dependency:

```text
PRODUCTION HOLD
→ separate deployment action / approval
```

No runtime self-install.

---

# 40. TL-S4-B3 DISPOSITION

```text
TL-S4-B3 = BOUND

DEPENDENCY =
cryptography

SUPPORTED FLOOR =
3.4.8

REQUIRED PRIMITIVES =
AESGCM
HKDF-SHA256

PACKAGE INSTALL AUTHORIZED BY THIS R1 =
NO

DEPLOYMENT DEPENDENCY EVIDENCE =
MANDATORY BEFORE PRODUCTION ELIGIBILITY
```

---

# 41. REPLACEMENT WORDING FOR AFFECTED v0.1 SECTIONS

Any v0.1 wording equivalent to:

```text
destroy old secret
securely destroy old secret
old-secret destruction
```

is superseded by:

```text
logically delete the unreferenced encrypted secret-version row
from the live controller_secret_versions table
```

Any wording equivalent to:

```text
browser never persists the secret
```

is superseded by:

```text
CaptivPortal application code never intentionally persists
the secret in application-controlled browser storage/state
```

Any wording implying:

```text
all platform_operator users automatically but independently
hold a stronger secret capability
```

is superseded by the explicit independently assigned global-capability model in this R1.

---

# 42. UPDATED ARCHITECTURE INVARIANTS

The following v0.1 invariants are replaced/qualified.

## S4-I28 / S4-I29 — AUTHORIZATION

```text
S4-I28-R1

Secret mutation requires independently assigned:
admin.write.settings.controller.secret.

S4-I29-R1

admin.write.settings.controller
does NOT imply
admin.write.settings.controller.secret.

The distinction is represented in AdminPrincipal.global_capabilities
and captured in AdminSession at login.
```

## S4-I32 — BROWSER

```text
S4-I32-R1

CaptivPortal application code does not intentionally persist
raw Client Secret in application-controlled browser persistence/state.

No guarantee is made about password managers,
browser internals, extensions, accessibility tools,
endpoint security software, or physical browser-memory erasure.
```

## S4-I36 — LIVE VERSION RETENTION

```text
S4-I36-R1

controller_secret_versions retains live encrypted secret material
only for versions referenced by current configured
and/or current effective ownership.

Unreferenced versions are logically deleted from the live table.
This is not a forensic secure-erasure guarantee.
```

## S4-I38 — POST-ADOPTION OLD VERSION

```text
S4-I38-R1

After successful adoption,
a previously effective secret version that is no longer referenced
by configured/effective ownership is logically deleted
from the live controller_secret_versions table
in the same SettingsStore transaction.

Historical SQLite/WAL/filesystem/backup remnants
are outside this logical-deletion guarantee.
```

## S4-I39 — SUPERSEDED PENDING VERSION

```text
S4-I39-R1

A superseded pending secret version that is no longer referenced
by configured/effective ownership is logically deleted
from the live controller_secret_versions table
in the same mutation transaction.

No forensic secure-erasure claim is made.
```

Additional invariants:

```text
S4-I51

secret_store_state=available requires
mandatory Settings DB filesystem-security validation PASS.

S4-I52

Application has no chmod/chgrp/chown authority
over Settings DB or master key.

S4-I53

Stage-4 deployment requires explicit pre-secret-write
Settings DB permission transition where current production
does not satisfy the file-security contract.

S4-I54

Stage 4 supports cryptography >= 3.4.8
and implementation must remain compatible with the 3.4.8 floor.

S4-I55

No package installation or dependency mutation
is authorized by architecture review.

S4-I56

Backup retention/destruction is an operational security policy
outside the atomic Settings transaction.

S4-I57

Historical backup + matching static master key
may remain capable of decrypting historical managed secret ciphertext.

S4-I58

Stage 4 V1 does not claim forensic or cryptographic erasure
of historical secret copies.
```

---

# 43. FROZEN / NOT REOPENED

The following v0.1 decisions remain unchanged:

```text
one existing SettingsStore SQLite transaction domain

dedicated ControllerSecretRepository

AES-256-GCM

fixed-size encrypted frame

external 32-byte master key

HKDF-separated encryption/idempotency keys

HMAC secret idempotency fingerprint

no raw secret hash in DB

managed override
>
environment
>
repository default

clear managed override
→ deployment fallback

LOCAL/SYNTACTIC validation only

NO live Controller credential test

dedicated write-only secret API

NO raw-secret read-back

normal global Settings generation

common global ETag

restart-based activation

NO Admin systemd authority

NO hot reconnect

fail closed when configured managed secret cannot resolve

NO environment fallback
when managed binding explicitly owns configured state

break-glass clear
with service stopped + CAS

Controller read model v3

SettingsStore schema v3

Stage-3 rollback requires pre-Stage4 v2 DB restore

master-key rotation OUT OF Stage 4 V1

no secret export/history/reveal
```

---

# 44. R1 FINAL DISPOSITION

```text
P1-01 =
CLOSED

SELECTED AUTH MODEL =
OPTION A — REAL STRONGER CAPABILITY

P1-02 =
CLOSED

SECRET VERSION REMOVAL =
LOGICAL DELETION FROM LIVE STORE
NO FORENSIC SECURE-ERASE CLAIM

TL-S4-B1 =
BOUND

SETTINGS DB SECURITY =
MANDATORY PART OF secret_store_state

APPLICATION FILE PERMISSION AUTHORITY =
VALIDATE ONLY

TL-S4-B2 =
BOUND

BROWSER GUARANTEE =
APPLICATION-CONTROLLED PERSISTENCE ONLY

TL-S4-B3 =
BOUND

CRYPTOGRAPHY FLOOR =
>= 3.4.8

OPEN_P0 =
0

OPEN_P1 =
0

ARCHITECTURE =
DRAFT FOR TECH LEAD RE-REVIEW

IMPLEMENTATION TASK =
HOLD

CODER =
HOLD

PRODUCTION CHANGE =
NO

SYSTEMD ACTION =
NO

PACKAGE INSTALL =
NO
```

Следующий разрешённый шаг:

```text
Tech Lead
→ bounded Stage-4 R1 re-review

if PASS:
→ Stage-4 Architecture FINAL / ACCEPTED
→ Technical Developer Settings prepares exact implementation TASK

until PASS:
IMPLEMENTATION TASK = HOLD
CODER = HOLD
PRODUCTION = NO CHANGE
```
