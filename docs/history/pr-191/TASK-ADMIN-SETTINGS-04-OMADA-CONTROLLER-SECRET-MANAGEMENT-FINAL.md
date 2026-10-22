# TASK-ADMIN-SETTINGS-04 — OMADA CONTROLLER SECRET MANAGEMENT
## FINAL CANDIDATE FOR TECH LEAD IMPLEMENTATION-CONTRACT REVIEW

**Project:** CaptivPortal  
**Area:** Admin UI → Settings → Controller  
**Stage:** Stage 4 — Omada Controller Secret Management  
**Document type:** Implementation TASK  
**Prepared by:** Technical Developer Settings / Tech Lead  
**Status:** FINAL CANDIDATE — NOT YET CODER-AUTHORIZING AT DOCUMENT CREATION

---

# 0. AUTHORITATIVE BASELINE

Implementation MUST start from exactly:

```text
BASE_HEAD=
78296b2e9a35664c0d285cf0c7d22b2fa465311a

BASE_TREE=
f965d4604652db52d5f97b1f5d3abe36263ee78b
```

This is merged PR #187 / Stage-3 FIX2 and current accepted Stage-3 production baseline.

Before editing:

```text
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain
```

Required:

```text
HEAD == BASE_HEAD
TREE == BASE_TREE
worktree clean
```

If not exact:

```text
STOP
NO REBASE GUESS
NO PORTING TO ANOTHER BASELINE
RETURN EVIDENCE
```

---

# 1. NORMATIVE ARCHITECTURE

This TASK implements the combined accepted Stage-4 contract:

```text
CAPTIVPORTAL ADMIN SETTINGS
STAGE 4 — OMADA CONTROLLER SECRET MANAGEMENT
ARCHITECTURE CONTRACT v0.1

PLUS

BOUNDED R1
CAPTIVPORTAL-ADMIN-SETTINGS-STAGE-4-SECRET-MANAGEMENT-ARCHITECTURE-v0.1-R1-RU
```

Tech Lead architecture disposition:

```text
STAGE4_ARCHITECTURE=FINAL / ACCEPTED
OPEN_P0=0
OPEN_P1=0
```

Authority order:

```text
accepted architecture
>
this implementation TASK
>
roadmap
```

If this TASK appears to contradict the accepted architecture:

```text
STOP
RETURN EXACT CONTRADICTION
DO NOT IMPROVISE
```

---

# 2. IMPLEMENTATION GOAL

Add write-only management of exactly one secret:

```text
OMADA_CLIENT_SECRET
```

through:

```text
Admin UI
→ Settings
→ Controller
```

while preserving permanent no-read-back and Stage-3 adoption/I/O ordering.

End-state:

```text
deployment/environment secret
        OR
managed encrypted secret override
        ↓
one startup secret resolution
        ↓
one OmadaControllerRuntimeConfig
        ↓
one shared OmadaProvider
```

Managed secret mutation participates in the existing GLOBAL Settings generation chain.

---

# 3. EXACT IN SCOPE

Implement:

```text
1. encrypted managed OMADA_CLIENT_SECRET persistence
2. SettingsStore schema v2 → v3
3. generation → secret-version binding
4. secret-safe mutation audit
5. secret-safe idempotency fingerprinting
6. write-only replacement API
7. clear managed secret override
8. configured/effective/pending safe secret metadata
9. Controller read model v3
10. stronger independently assigned Admin secret-write capability
11. restart-based secret activation
12. startup managed-secret resolution
13. secret-store filesystem security validation
14. secret-store availability state
15. logical GC of unreferenced live secret versions
16. local break-glass clear command
17. browser replacement/clear UX
18. strict secret-taint protections
19. cryptography dependency declaration
20. Stage-4 documentation
```

---

# 4. EXACT OUT OF SCOPE

DO NOT implement:

```text
VERIFY_SSL mutation
secret read-back
secret reveal
secret export
secret history UI
secret rollback selector
generic secret vault
arbitrary secrets other than OMADA_CLIENT_SECRET
master-key rotation
Admin systemd/service control
restart button
hot reload
hot reconnect
hot provider recreation
Controller Test Connection
live credential validation
token reset
OAuth client creation/deletion
Omada-side mutation
multi-controller support
Site-scoped Controller settings
environment editor
systemd environment editor
Stage-5 Portal settings
automatic package install
automatic chmod/chown/chgrp repair
```

No production action is part of this Coder task.

---

# 5. PERMANENT SECRET NON-DISCLOSURE INVARIANT

Raw `OMADA_CLIENT_SECRET` MUST NEVER be returned or copied into:

```text
settings_overrides
ordinary SettingsDefinition
ordinary SettingReadModel
Controller GET JSON
mutation success JSON
mutation error JSON
HTML
JS bootstrap/model data
query string
URL fragment
cookies
localStorage
sessionStorage
history state
data-* attributes
audit scalar values
idempotency response
idempotency raw persisted payload
logs
structured logs
telemetry
metrics labels
trace metadata
exception text
debug repr
dataclass repr
secret fingerprint/prefix/suffix/length UI
```

There is no read-secret API.

---

# 6. AUTHORIZED PRODUCTION FILE SCOPE

Expected production/source files:

```text
requirements.txt
.env.example

app/config.py
app/settings.py
run.py

app/controllers/omada_config.py

app/settings_control/__init__.py
app/settings_control/models.py
app/settings_control/repository.py
app/settings_control/services.py
app/settings_control/bootstrap.py
app/settings_control/activation.py
app/settings_control/controller_secret.py          [NEW]
app/settings_control/secret_recovery.py            [NEW]

app/admin_web/capabilities.py                      [NEW]
app/admin_web/config.py
app/admin_web/models.py
app/admin_web/policy.py
app/admin_web/runtime.py
app/admin_web/controller_settings.py
app/admin_web/routes.py
app/admin_web/templates/admin/settings_controller.html
app/admin_web/static/controller_settings.js

docs/configuration.md
docs/deployment.md
docs/modules/admin-web.md
```

Tests under existing `tests/` plus new Stage-4 focused test files are authorized.

If another production file is required:

```text
STOP
RETURN:
FILE=
WHY_REQUIRED=
ARCHITECTURE_CLAUSE=
```

Do not silently widen scope.

---

# 7. NEW RUNTIME DEPENDENCY

Declare:

```text
cryptography>=3.4.8
```

in source dependency metadata.

Required compatibility floor:

```text
cryptography 3.4.8
```

Required primitives:

```text
cryptography.hazmat.primitives.ciphers.aead.AESGCM
cryptography.hazmat.primitives.kdf.hkdf.HKDF
cryptography.hazmat.primitives.hashes.SHA256
```

Do NOT:

```text
pip install
apt install
upgrade package
downgrade package
self-install at runtime
```

If the implementation environment does not already have a compatible package:

```text
STOP
RETURN ENVIRONMENT BLOCKER
```

---

# 8. ADMIN GLOBAL CAPABILITY MODEL

Create one code-owned capability module:

```text
app/admin_web/capabilities.py
```

It owns the exact recognized Stage-4 GLOBAL set:

```text
admin.read.settings.global
admin.write.settings.global
admin.read.settings.controller
admin.write.settings.controller
admin.write.settings.controller.secret
```

It also owns the Stage-3-compatible default grant:

```text
admin.read.settings.global
admin.write.settings.global
admin.read.settings.controller
admin.write.settings.controller
```

Default grant MUST NOT contain:

```text
admin.write.settings.controller.secret
```

Do not make recognized-capability set mean automatically granted capabilities.

---

# 9. `WEB_ADMIN_GLOBAL_CAPABILITIES`

Add deployment/startup configuration:

```text
WEB_ADMIN_GLOBAL_CAPABILITIES
```

Mapping into `get_settings()`:

```text
web_admin_global_capabilities
```

It is:

```text
environment/deployment controlled
NOT a SettingsDefinition
NOT SettingsStore writable
NOT Site-scoped
read at startup
NOT hot-reloaded
```

Repository/default value is the exact Stage-3-compatible four-capability list.

Canonical parser rules:

```text
comma-separated exact capability identifiers
ASCII only
1..16 tokens
no empty token
no duplicate token
no unknown token
no leading/trailing whitespace inside token
each token <=128 ASCII bytes
```

Malformed configuration:

```text
Admin Web configuration fails closed
```

Do not ignore unknown entries.

---

# 10. `AdminWebConfig`

Add:

```text
global_capabilities: frozenset[str]
```

`admin_web_config_from_settings()` validates/parses the startup configuration once.

No request-time environment read.

No route parses this environment value independently.

---

# 11. `AdminPrincipal` / SESSION MODEL

Extend `AdminPrincipal` with:

```text
global_capabilities: frozenset[str]
```

Constructor compatibility for unrelated Site-read tests MAY use an empty frozenset default, but an authenticated production login MUST explicitly capture:

```text
config.global_capabilities
```

into the principal.

`AdminSession` continues to contain the immutable principal.

At successful login:

```text
validated AdminWebConfig.global_capabilities
→ AdminPrincipal.global_capabilities
→ AdminSession.principal
```

Changing deployment capability config requires external process restart and a new login.

No hot capability resolution.

---

# 12. `authorize_global()` EXACT SEMANTICS

Return true only when all are true:

```text
principal is AdminPrincipal
principal.principal_type == "platform_operator"
requested capability is recognized
requested capability in principal.global_capabilities
```

Otherwise deny.

Site authorization outside this global capability change remains semantically unchanged.

Ordinary Controller write MUST NOT imply secret write.

---

# 13. SECRET CAPABILITY

Exact capability:

```text
admin.write.settings.controller.secret
```

Secret mutation requires:

```text
authenticated Admin session
+
admin.read.settings.controller
+
admin.write.settings.controller.secret
```

Ordinary Controller mutation continues to require:

```text
admin.write.settings.controller
```

No Site authorization participates in secret mutation.

---

# 14. SECRET DEFINITION

In `app/settings_control/controller_secret.py`, define a narrow code-owned immutable definition equivalent to:

```text
ControllerSecretDefinitionV1

key=OMADA_CLIENT_SECRET
scope=global
secret_class=write_only_secret
apply_requirement=main_service_restart
activation_target=captive-portal.service
```

It MUST NOT be iterable through `SettingsDefinitionRegistry`.

`SettingsDefinitionRegistry` remains exactly:

```text
15 ordinary definitions
```

Generic `SettingsMutationService` continues to reject `OMADA_CLIENT_SECRET`.

---

# 15. SETTINGSSTORE SCHEMA VERSION

Advance:

```text
SETTINGS_SCHEMA_VERSION
2 → 3
```

Fresh empty Store creates schema v3.

Production migration:

```text
v2 → v3
```

must be:

```text
single SQLite transaction
explicit
version checked
history preserving
fail closed on integrity/schema mismatch
```

Preserve the existing v1 upgrade path if current source supports it; a v1 Store upgraded by Stage-4 source must arrive at the same valid v3 schema without rewriting historical semantics.

No automatic v3 → v2 downgrade.

---

# 16. NEW TABLE — `controller_secret_versions`

Exact logical schema:

```text
secret_version_id TEXT PRIMARY KEY
setting_key TEXT NOT NULL CHECK(setting_key='OMADA_CLIENT_SECRET')
crypto_schema_version INTEGER NOT NULL CHECK(crypto_schema_version=1)
nonce BLOB NOT NULL CHECK(length(nonce)=12)
ciphertext BLOB NOT NULL CHECK(length(ciphertext)=4116)
created_at_utc TEXT NOT NULL
```

Rules:

```text
secret_version_id = canonical UUIDv4 string
rows are never UPDATEd
DELETE is allowed only through narrow repository lifecycle/GC code
no API exposes rows
```

Use an immutable UPDATE trigger if consistent with repository schema style.

Do NOT create a DELETE-blocking trigger because GC requires deletion.

---

# 17. NEW TABLE — `settings_secret_bindings`

Exact logical schema:

```text
generation_id INTEGER PRIMARY KEY
    REFERENCES settings_generations(generation_id)

setting_key TEXT NOT NULL
    CHECK(setting_key='OMADA_CLIENT_SECRET')

secret_version_id TEXT NOT NULL
```

Intentional:

```text
NO FK from secret_version_id
to controller_secret_versions
```

Historical generations may retain opaque version identity after live ciphertext row is logically deleted.

Rows are immutable.

Generation 0 MUST have no secret binding.

---

# 18. NEW TABLE — `settings_secret_mutation_audit`

Create immutable secret-safe audit rows containing only:

```text
audit_id
generation_id
parent_generation_id
principal_type
principal_name
source_ip
request_id
idempotency_key nullable
timestamp_utc
scope_type='global'
setting_key='OMADA_CLIENT_SECRET'
operation:
  replace_secret
  clear_secret_override
  clear_secret_override_recovery
previous_override_present
new_override_present
previous_source
new_source
apply_requirement='main_service_restart'
activation_target='captive-portal.service'
```

Use bounded CHECK constraints for fixed enums/boolean representation.

Audit MUST NOT contain:

```text
raw old/new secret
ciphertext
nonce
secret_version_id
secret length
prefix/suffix
secret hash
secret HMAC
request body
```

Semantic no-op produces no mutation-audit row.

---

# 19. IDEMPOTENCY SCHEMA V3

Evolve `settings_idempotency`:

Replace logical:

```text
request_payload_hash
```

with:

```text
request_fingerprint_kind
request_fingerprint
```

Allowed kinds:

```text
sha256_canonical_json_v1
hmac_sha256_controller_secret_v1
```

Allowed domains:

```text
general
controller
controller_secret
```

Retain:

```text
UNIQUE(
  principal_type,
  principal_name,
  scope_type,
  mutation_domain,
  idempotency_key
)
```

Retain bounded success response:

```text
result_response_json <= 65536 UTF-8 bytes
```

Migration of existing rows:

```text
request_fingerprint_kind=sha256_canonical_json_v1
request_fingerprint=old request_payload_hash
mutation_domain preserved
result_response_json byte-semantically preserved
```

Existing General/Controller replay behavior must remain unchanged.

---

# 20. V2 → V3 MIGRATION MUST NOT CREATE STATE

Migration creates:

```text
NO new Settings generation
NO secret binding
NO encrypted secret version
NO activation event
NO secret mutation audit
```

Preserve:

```text
generation ids
parent links
ordinary overrides
effective target state
activation events
ordinary mutation audit
Controller mutation audit
all successful idempotency rows
```

Do NOT import/copy current deployment `OMADA_CLIENT_SECRET` into encrypted storage.

---

# 21. SETTINGSSTORE HISTORY INTEGRITY V3

Schema/history validation must additionally verify:

```text
generation 0 has no managed-secret binding
binding key exactness
canonical UUID syntax of secret_version_id
nonce length = 12
ciphertext length = 4116
crypto_schema_version = 1
idempotency domains/kinds valid
ordinary foreign-key integrity unchanged
```

Historical binding to a no-longer-live secret row is allowed.

A managed secret version referenced by current:

```text
configured head
OR
effective generation
```

MUST have a live `controller_secret_versions` row.

No auto recreation of corrupt Store.

---

# 22. COMPLETE GENERATION SNAPSHOT

Every new Settings generation is a complete snapshot of:

```text
ordinary persisted overrides
+
managed-secret ownership state
```

Therefore ordinary General and Controller mutations MUST carry the parent secret binding unchanged.

Bind this at the repository generation-creation boundary so current/future ordinary mutation callers cannot forget to carry the secret state.

Secret mutation may explicitly choose:

```text
carry parent binding
bind version S
no binding
```

as appropriate.

Do not copy raw secret.

---

# 23. MASTER KEY CONSTANT

Canonical production path:

```text
/etc/captiveportal/omada-controller-secret-master.key
```

This is code-owned Stage-4 V1 policy.

It is:

```text
NOT Admin editable
NOT SettingsStore editable
NOT environment configurable
```

Application does not create/replace/rotate/chmod/chgrp/chown this key.

---

# 24. MASTER KEY FILE VALIDATION

Production key requirements:

```text
parent=/etc/captiveportal
parent type=directory
parent not symlink
parent owner=root
parent group=admin
parent mode=0750

key type=regular file
key not symlink
key owner=root
key group=admin
key mode=0640
key hard-link count=1
key size=exactly 32 bytes
```

Read exactly 32 raw bytes.

No:

```text
hex
base64
newline format
```

Use a no-follow/open+fstat style boundary where available so security validation is performed against the opened object rather than trusting a path-only stat race.

Implementation MUST remain testable without weakening production policy.

---

# 25. SETTINGS DB FILE SECURITY VALIDATION

For Stage-4 secret management, canonical production DB:

```text
/opt/CaptivePortal/data/settings.sqlite3
```

must satisfy:

```text
regular file
not symlink
owner=admin
group=admin
mode=0600
hard-link count=1
```

Parent `/opt/CaptivePortal/data`:

```text
actual directory
not symlink
owner=admin
group deployment-defined
group NOT writable
other NOT writable
setgid allowed
```

Application:

```text
VALIDATES ONLY
```

Application MUST NOT:

```text
chmod
chgrp
chown
silently repair
```

the DB or master key.

A test seam may inject filesystem metadata/security providers, but there must be no production Admin/API bypass of these checks.

---

# 26. CURRENT PRODUCTION PERMISSION FACT

Current accepted Stage-3 production observation:

```text
settings.sqlite3
owner=admin
group=telemetry
mode=0644

data parent
owner=admin
group=telemetry
mode=2750
```

This TASK does NOT change production.

Future Stage-4 production activation must perform an explicit operator-owned DB permission transition before managed-secret mutation is enabled:

```text
owner=admin
group=admin
mode=0600
```

Do not implement automatic repair.

---

# 27. SECRET STORE AVAILABILITY

Expose internal state:

```text
available
unavailable
```

`available` only when all required facts are trustworthy:

```text
SettingsStore schema/integrity valid
canonical DB path/file security PASS
parent path security PASS
master-key parent/key security PASS
key size PASS
crypto primitive initialization PASS
```

If any mandatory condition fails:

```text
secret_store_state=unavailable
secret mutation unavailable
```

Ordinary Stage-3 Settings may remain usable if their existing Store contract remains healthy.

---

# 28. CRYPTO KEY DERIVATION

From the exact 32-byte master key derive two distinct 32-byte subkeys.

Encryption:

```text
HKDF-SHA256(
    master_key,
    salt=b"CaptivPortal.Stage4.ControllerSecret.v1",
    info=b"encryption",
    length=32
)
```

Idempotency:

```text
HKDF-SHA256(
    master_key,
    salt=b"CaptivPortal.Stage4.ControllerSecret.v1",
    info=b"idempotency",
    length=32
)
```

Do not reuse one derived key for both purposes.

---

# 29. SECRET NORMALIZATION / VALIDATION

For `replace_secret`:

```text
input must be JSON string
normalize with Python str.strip()
leading/trailing Unicode whitespace removed
normalized UTF-8 byte length = 1..4096
```

Reject any contained code point:

```text
U+0000..U+001F
U+007F
```

No other:

```text
lowercasing
Unicode normalization
case normalization
silent truncation
```

Validation failure returns only safe field/reason metadata.

Never echo rejected value.

---

# 30. FIXED-SIZE PLAINTEXT FRAME

For normalized secret bytes:

```text
4 bytes unsigned big-endian secret byte length
+
secret UTF-8 bytes
+
CSPRNG random padding
```

Secret payload area after the four-byte length is exactly:

```text
4096 bytes
```

Total plaintext:

```text
4100 bytes
```

Padding MUST be random, not zero-filled.

---

# 31. AES-GCM ENCRYPTION

Use:

```text
AES-256-GCM
```

through approved `AESGCM`.

Per secret version:

```text
secret_version_id=UUIDv4
nonce=12 CSPRNG random bytes
ciphertext+tag length=4116 bytes
```

Canonical AAD:

```text
b"CaptivPortal\x00OMADA_CLIENT_SECRET\x00"
+
ASCII(secret_version_id)
+
b"\x00v1"
```

Decryption must authenticate AAD/tag and validate the decoded fixed frame and normalized secret.

No crypto exception text may escape the secret boundary.

---

# 32. INTERNAL SECRET-BEARING MODEL

Add immutable:

```text
OmadaClientSecretResolution
```

Conceptual fields:

```text
value
source
configured_generation
managed_secret_version_id nullable
```

Requirements:

```text
repr redacts value
str redacts value
never serialized to Admin
managed_secret_version_id internal only
```

Do not put raw secret into generic Settings snapshot/read models.

---

# 33. SECRET SOURCES / PRECEDENCE

Exact precedence:

```text
managed_secret_override
>
explicit process environment OMADA_CLIENT_SECRET
>
repository_default
```

Allowed source enum:

```text
managed_secret_override
environment
repository_default
```

No managed binding means deployment/base source controls.

Migration does not create managed ownership.

---

# 34. STARTUP SECRET RESOLUTION

Preserve exact startup ownership:

```text
get_settings()
→ deployment/environment base

bootstrap SettingsStore
→ exact configured generation G
→ ordinary overrides
→ secret binding for G

resolve ordinary non-secret Settings snapshot G

ControllerSecretResolver.resolve(
    generation=G,
    binding,
    deployment_base_secret,
    explicit_environment_names
)

→ ONE OmadaClientSecretResolution

ordinary resolved settings
+
secret resolution
→ ONE OmadaControllerRuntimeConfig

→ ONE shared OmadaProvider

→ raw-secret-free public Controller snapshot

→ durable Settings adoption

→ only then provider-capable workers / Controller I/O
```

No component independently re-reads secret store or environment after this composition boundary.

---

# 35. `OmadaControllerRuntimeConfig`

Preserve it as the one secret-bearing Controller runtime config.

Its `client_secret` remains `repr=False`.

Modify construction so Stage-4 startup can explicitly inject the resolved secret rather than taking managed material through the ordinary settings mapping.

Backward-compatible test/helper construction may remain where safe, but production `run.py` MUST use the Stage-4 resolution path.

No provider-side `get_settings()`.

---

# 36. PUBLIC EFFECTIVE SNAPSHOT

`OmadaControllerPublicConfigSnapshot` remains raw-secret-free.

It may expose only safe Client Secret effective facts:

```text
client_secret_presence
client_secret_source
effective_generation
```

Source admits:

```text
managed_secret_override
environment
repository_default
```

It MUST NOT contain:

```text
raw secret
secret_version_id
ciphertext
hash/HMAC
length
prefix/suffix
```

---

# 37. MANAGED-SECRET STARTUP FAILURE

If configured generation G has a managed secret binding, fail closed before provider construction/HTTP serving when any required managed-secret dependency fails, including:

```text
key unavailable
key metadata invalid
DB secret-security invalid
secret version missing
AES-GCM authentication failure
frame integrity failure
binding integrity failure
decoded secret invalid
```

Then:

```text
shared OmadaProvider NOT constructed
provider-capable workers NOT started
HTTP serving NOT started
effective_generation NOT advanced
NO fallback to environment/repository secret
```

---

# 38. SAFE ACTIVATION FAILURE CODES

Permit exact safe Stage-4 categories:

```text
controller_secret_key_unavailable
controller_secret_permissions_invalid
controller_secret_reference_missing
controller_secret_decrypt_failed
controller_secret_integrity_failed
controller_secret_configuration_invalid
```

Integrate with `SettingsActivationService.fail()` allowed codes.

Use positive in-process durable attestation only.

Process disappearance/timeouts do not fabricate activation failure.

---

# 39. NO MANAGED BINDING + SECRET STORE UNAVAILABLE

If configured head has no managed binding and deployment secret is locally valid:

```text
runtime may start normally
deployment/environment secret remains effective
secret_store_state=unavailable
secret mutation returns 503 controller_secret_store_unavailable
```

Missing master key MUST NOT become a mandatory runtime dependency before managed ownership exists.

---

# 40. NO CONTROLLER I/O BEFORE ADOPTION

Permanent Stage-3 invariant:

```text
candidate generation G
MUST NOT be used for Controller/OAuth network I/O
before durable adoption G
```

Allowed pre-adoption:

```text
local DB read
secret file read
decrypt
validation
OmadaControllerRuntimeConfig construction
OmadaProvider object construction
Observation local read-boundary preparation
Admin/Analytics local composition
```

Forbidden pre-adoption:

```text
OAuth token request
Controller HTTP request
get_sites
get_clients
reconnect
credential test
```

Do not undo FIX2 startup ordering.

---

# 41. SECRET REPOSITORY BOUNDARY

Implement:

```text
ControllerSecretRepository
```

as a narrow boundary over the same Settings SQLite transaction domain.

It owns:

```text
binding lookup
encrypted-version insert/select
secret-safe audit insert
live-version retention/GC
secret schema integrity helpers
```

Raw secret encryption/decryption must stay inside the Stage-4 secret boundary.

Do NOT create:

```text
second Settings DB
second generation chain
second CAS authority
second generic mutation subsystem
```

---

# 42. LIVE VERSION RETENTION

Live `controller_secret_versions` contains encrypted material only for versions referenced by:

```text
current configured head
and/or
current effective generation
```

Normal live maximum:

```text
1 when configured/effective use same managed version
2 when configured/effective require different managed versions
```

Unreferenced rows are logically deleted from the live table.

Do NOT claim forensic/cryptographic erase.

Historical DB/WAL/filesystem/snapshot/backup remnants are outside this guarantee.

---

# 43. SECRET REPLACE NO-OP / REUSE

For a new `replace_secret`:

If configured source is managed and normalized new secret equals current configured managed secret:

```text
semantic no-op
no generation
no new secret version
no audit
200
```

If it differs from configured secret but equals another retained live managed version, e.g. current effective version:

```text
MAY reuse that retained secret_version_id
```

Otherwise create:

```text
new UUIDv4 version
new nonce
new ciphertext
```

Use constant-time bytes comparison where practical.

If configured source is deployment/environment and submitted scalar happens to equal deployment secret:

```text
ownership changes to managed_secret_override
changed=true
new generation required
```

---

# 44. CLEAR OVERRIDE SEMANTICS

Operation:

```text
clear_secret_override
```

means:

```text
new generation has NO managed secret binding
→ ownership returns to deployment/environment layer
```

It does NOT:

```text
set empty secret
delete environment value
copy environment secret into secret table
modify systemd/env files
```

Before commit, validate resulting deployment fallback using the current startup base snapshot.

If fallback is absent/invalid:

```text
422 validation_failed
no generation
```

If there is no managed binding:

```text
semantic no-op
no generation
no secret audit
200
```

Ownership change managed → deployment is changed even if scalar happens to be equal.

---

# 45. SECRET-SAFE IDEMPOTENCY FINGERPRINT

Use HMAC-SHA256 with the derived idempotency key.

Canonical fingerprint message is canonical JSON UTF-8 of exactly:

For replace:

```json
{
  "api_version": "admin.settings.controller.secret.mutation.v1",
  "principal_type": "<principal type>",
  "principal_name": "<principal name>",
  "idempotency_key": "<UUID>",
  "operation": "replace_secret",
  "secret": "<normalized secret>"
}
```

For clear:

```json
{
  "api_version": "admin.settings.controller.secret.mutation.v1",
  "principal_type": "<principal type>",
  "principal_name": "<principal name>",
  "idempotency_key": "<UUID>",
  "operation": "clear_secret_override"
}
```

Persist only:

```text
request_fingerprint_kind=hmac_sha256_controller_secret_v1
request_fingerprint=<HMAC>
```

Never persist canonical message/raw secret/plain SHA256(secret).

Different Idempotency-Key values for same secret MUST yield unrelated persisted fingerprints.

---

# 46. IDEMPOTENT REPLAY

Lookup identity:

```text
principal_type
principal_name
scope_type=global
mutation_domain=controller_secret
Idempotency-Key
```

Existing record:

```text
same fingerprint
→ exact original success receipt
→ no head CAS
→ no decrypt
→ no version
→ no generation
→ no audit
→ no Controller I/O

different fingerprint
→ 409 idempotency_conflict
```

Replayed receipt remains bounded and secret-free.

---

# 47. WRITE-ONLY SECRET API

Exact route:

```text
POST /admin/api/v1/settings/controller/client-secret/generations
```

API version:

```text
admin.settings.controller.secret.mutation.v1
```

Exact transport:

```text
Content-Type: application/json
X-CSRF-Token: <session token>
If-Match: "settings-gN"
Idempotency-Key: canonical UUID
Content-Length required
no query parameters
body <=32768 bytes
one operation only
```

This route MUST be exempted from the generic form-POST boundary exactly like the existing Settings JSON mutation routes.

No mixed secret/non-secret batch.

---

# 48. STRICT SECRET JSON PARSER

Do not reuse any helper that persists/logs/hashes raw body generically.

Use strict duplicate-key-rejecting JSON parsing.

Replace exact body:

```json
{
  "operation": "replace_secret",
  "secret": "<new secret>"
}
```

Exact keys only.

Clear exact body:

```json
{
  "operation": "clear_secret_override"
}
```

No `secret` allowed for clear.

Reject:

```text
unknown fields
duplicate members
NaN/Infinity/non-JSON constants
wrong root type
wrong operation
wrong value type
```

Raw body is not logged.

---

# 49. SECRET API ERROR CONTRACT

Exact safe errors:

```text
400 invalid_request
400 invalid_csrf
401 authentication_required
403 controller_secret_forbidden
404 feature_disabled
409 idempotency_conflict
412 stale_generation
413 request_too_large
415 unsupported_media_type
422 validation_failed
428 precondition_required
503 settings_store_unavailable
503 controller_secret_store_unavailable
500 internal_error
```

Missing Content-Length:

```text
411 length_required
```

Validation details only use safe field/reason codes, e.g.:

```text
field=client_secret
reason=required
```

or:

```text
field=client_secret
reason=too_long
```

No rejected value echo.

---

# 50. SECRET MUTATION SUCCESS RECEIPT

Changed:

```text
201 Created
```

No-op/replay:

```text
200 OK
```

Exact shape:

```json
{
  "api_version": "admin.settings.controller.secret.mutation.v1",
  "request_id": "<uuid>",
  "scope": {"type": "global"},
  "resource": {
    "type": "omada_controller",
    "scope": "installation"
  },
  "operation": "replace_secret",
  "changed": true,
  "configured_generation": 42,
  "effective_generation": 41,
  "activation_state": "pending_main_restart",
  "restart_required": true
}
```

For clear:

```text
operation=clear_secret_override
```

Never include:

```text
secret
version id
hash/HMAC
length
prefix/suffix
ciphertext
nonce
```

Response serialization must remain <=65536 bytes.

---

# 51. REPLACE TRANSACTION ORDER

Preserve the architecture order:

```text
1 auth/capability/CSRF/header/body bounds
2 strict parse
3 normalize/validate secret in memory
4 load/validate master key
5 derive HMAC key
6 compute request HMAC
7 read-only idempotency lookup/replay/conflict
8 BEGIN IMMEDIATE
9 re-check idempotency
10 CAS global generation head
11 read parent secret binding
12 compare configured retained secret if needed
13 decide no-op/reuse/new version
14 encrypt/insert version if new
15 create normal Settings generation if changed
16 copy ordinary override snapshot
17 bind new secret ownership
18 secret-safe audit
19 calculate configured/effective retained ids
20 logically delete unreferenced live version rows
21 persist bounded idempotency receipt
22 COMMIT
```

No Controller/OAuth I/O.

---

# 52. CLEAR TRANSACTION ORDER

```text
1 auth/CSRF/header/body/idempotency validation
2 BEGIN IMMEDIATE
3 re-check idempotency
4 CAS global head
5 detect no managed binding → semantic no-op
6 resolve lower-precedence deployment secret from current startup base snapshot
7 local complete Controller validation
8 create generation
9 copy ordinary overrides
10 create NO secret binding
11 append secret-safe audit
12 GC unreferenced live versions while retaining current effective version
13 persist idempotency receipt
14 COMMIT
```

No environment/systemd mutation.

---

# 53. ACTIVATION TRANSACTION EXTENSION

On successful durable adoption G, in the SAME SettingsStore write transaction:

```text
append activation_result=adopted
update settings_target_state.effective_generation=G
compute secret versions referenced by:
  configured head
  new effective generation
logically delete all other live controller_secret_versions rows
COMMIT
```

On failed adoption:

```text
effective_generation unchanged
currently effective managed version remains live
```

No forensic-erasure claim.

---

# 54. PUBLIC CONTROLLER READ MODEL V3

Keep:

```text
GET /admin/api/v1/settings/controller
```

Change API version:

```text
admin.settings.controller.v2
→
admin.settings.controller.v3
```

Existing non-secret field meanings remain unchanged.

Top level additionally exposes:

```text
mutation_available
secret_mutation_available
```

These are infrastructure availability facts, not capability grants.

Preserve `pending_controller_setting_count`, but Stage 4 binds its exact meaning to:

```text
count(non-secret Controller fields with pending_value)
+
1 when client_secret.pending_replacement == true
```

When configured Store state is unavailable:

```text
pending_controller_setting_count = null
```

This prevents a secret-only pending change from being reported as `0 Controller fields pending`.

---

# 55. EXACT PUBLIC `client_secret` MODEL

Return exactly safe semantic fields equivalent to:

```json
{
  "display_label": "Client Secret",
  "value_type": "secret_write_only",
  "management_mode": "write_only",
  "configured_presence": "configured",
  "configured_source": "managed_secret_override",
  "effective_presence": "configured",
  "effective_source": "environment",
  "persisted_secret_override_present": true,
  "pending_replacement": true,
  "apply_requirement": "main_service_restart",
  "activation_target": "captive-portal.service",
  "secret_store_state": "available"
}
```

Allowed presence:

```text
configured
not_configured
null
```

Allowed source:

```text
managed_secret_override
environment
repository_default
null
```

Allowed boolean-or-null:

```text
persisted_secret_override_present
pending_replacement
```

Secret store:

```text
available
unavailable
```

Never expose secret/version/hash/HMAC/length/fingerprint.

---

# 56. `pending_replacement` EXACT MEANING

When Store is trustworthy, compare secret ownership identity at:

```text
configured_generation
vs
effective_generation
```

True if secret state differs by:

```text
source
OR
managed secret_version_id
```

Unrelated global generation changes alone MUST NOT set `pending_replacement=true`.

Version IDs remain internal and are never serialized.

---

# 57. RUNNING STORE OUTAGE

If process has a trustworthy effective public snapshot and SettingsStore later becomes unavailable:

```text
effective_presence/effective_source remain available

configured_presence=null
configured_source=null
persisted_secret_override_present=null
pending_replacement=null

store_state=unavailable
mutation_available=false
secret_mutation_available=false
```

Do not render cached configured secret state as current.

Only genuine `settings_store_unavailable` may use this effective-only degradation path.

Unexpected/malformed projection remains 503.

---

# 58. KEY/SECRET STORE OUTAGE WHILE RUNNING

If runtime already holds effective secret and master key later becomes unavailable:

```text
provider may continue with in-memory effective config
Controller GET retains safe effective facts
secret_store_state=unavailable
secret_mutation_available=false
secret POST → 503 controller_secret_store_unavailable
```

Do not hot-fallback/recreate provider.

---

# 59. ADMIN RUNTIME WIRING

Extend `SettingsAdminContext` / `AdminWebRuntime` only with narrow Stage-4 secret-management boundaries needed by:

```text
ControllerConfigurationReadService
secret mutation route
```

Do not expose raw secret-bearing objects on Admin runtime.

Admin runtime may receive:

```text
secret mutation service
secret store safe state/provider
safe configured secret metadata boundary
```

but NOT `OmadaClientSecretResolution.value`.

---

# 60. CONTROLLER PAGE AUTHORIZATION DATA

Template render must receive separately:

```text
controller_settings_write_allowed
controller_secret_write_allowed
```

The second is true only when principal has:

```text
admin.write.settings.controller.secret
```

and read access has already passed.

Do not infer it from ordinary Controller write.

---

# 61. CONTROLLER UI — SAFE SECRET ROW

Client Secret row renders:

```text
Configured presence
Configured source
Effective presence
Effective source
Persisted managed override presence
Pending restart/replacement status
Secret store availability
```

No textbox representing current value.

No masked existing secret.

No prefix/suffix/length/fingerprint.

Add source presentation:

```text
managed_secret_override → Managed secret override
```

---

# 62. REPLACE SECRET UX

Only when:

```text
principal secret capability=true
AND
model.secret_mutation_available=true
AND
ETag available
```

show/enable:

```text
Replace secret
```

Dedicated replacement UI has exactly two password fields:

```text
New Client Secret
Repeat Client Secret
```

Both:

```text
type=password
autocomplete=new-password
spellcheck=false
autocapitalize=off
autocorrect=off
```

Paste is allowed.

No prefill.

No server-supplied masked current value.

Two values must match before POST.

---

# 63. REPLACE CONFIRMATION

Before POST require explicit confirmation with semantics:

```text
Replace Client Secret?

The value cannot be read back later.
Credentials will not be tested against Omada.
The running Controller connection remains unchanged.
An external captive-portal.service restart is required.
```

Confirmation MUST NOT display the typed secret.

---

# 64. CLEAR UX

When:

```text
persisted_secret_override_present=true
AND
secret capability=true
AND
secret mutation infrastructure available
```

show:

```text
Use deployment secret
```

Confirmation must state:

```text
Managed Client Secret will be removed.
After the required external service restart,
the deployment/environment secret will be used.
No current secret will be displayed.
```

No ambiguous generic "Reset" label.

---

# 65. BROWSER SECRET LIFETIME

Application-controlled persistence MUST NOT place raw secret in:

```text
URL/query/fragment
localStorage
sessionStorage
cookies
history state
HTML/bootstrap JSON
data-* attributes
generic JS model
client telemetry/logging
application cache
```

On cancel:

```text
clear both inputs
drop app references
close UI
no request
```

On every completed POST attempt, including network failure:

```text
clear both inputs
drop app-held secret references
```

Use `finally`-equivalent cleanup.

Do not claim browser/password-manager/OS physical memory erasure.

---

# 66. UNCERTAIN NETWORK RETRY

The application may retain only:

```text
Idempotency-Key
```

in ephemeral page memory for the unresolved retry workflow.

It MUST NOT retain raw secret.

User must re-enter secret.

For uncertain network outcome:

```text
same Idempotency-Key MAY be reused
```

For:

```text
412 stale_generation
```

must:

```text
clear secret fields
discard old key
GET Controller v3
show conflict
require re-entry
use NEW Idempotency-Key
```

No automatic raw-secret resubmit.

---

# 67. POST-SUCCESS UI

After successful changed replace:

```text
Client Secret saved.

The running process still uses the current effective secret.
Credentials were not tested against Omada.
An externally performed captive-portal.service restart is required.
```

Then:

```text
clear secret fields/references
close replace UI
GET Controller v3
render returned configured/effective/pending state
```

No restart button.

Every success/replay must re-GET.

---

# 68. GENERIC CONTROLLER MUTATION MUST STAY SECRET-FREE

Existing:

```text
POST /admin/api/v1/settings/controller/generations
```

continues to accept exactly:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

It MUST reject:

```text
OMADA_CLIENT_SECRET
VERIFY_SSL
```

Do not route secret values through generic `SettingsMutationService`.

---

# 69. COMMON GLOBAL ETag / CAS

All General, Controller non-secret and Controller secret mutations share:

```text
"settings-g<configured_generation>"
```

A mutation in any domain may stale an open editor in another domain.

This is intentional.

No second secret generation counter.

---

# 70. BREAK-GLASS RECOVERY COMMAND

Implement module:

```text
python3 -m app.settings_control.secret_recovery \
  clear-omada-client-secret \
  --expected-generation <N>
```

Purpose:

```text
clear managed OMADA_CLIENT_SECRET binding
without reading/decrypting old secret
when normal service cannot start
```

Operational precondition:

```text
authorized local operator
captive-portal.service stopped
```

Command performs NO systemd start/stop/restart itself.

Before writing it MUST require:

```text
SettingsStore schema/integrity valid
Settings DB canonical path/file/parent security checks PASS
```

It does NOT require a usable master key because it never reads/decrypts the managed secret.
If DB security is invalid, operator must repair deployment permissions outside the application and retry.

It:

```text
opens existing SettingsStore
requires schema v3
CAS exact configured generation
requires current managed binding; if absent, exit safely with no generation
copies ordinary overrides
creates one new normal Settings generation
creates NO binding for new generation
writes secret-safe audit:
  operation=clear_secret_override_recovery
  principal_type=local_operator
  principal_name=current OS operator identity
  source_ip=local
logically GC unreferenced live versions while retaining current effective version
does NOT decrypt/read old managed secret
does NOT test Controller
does NOT modify deployment environment
does NOT require idempotency HMAC
```

Use a Linux OS identity source suitable for production; keep it injectable/testable.

Do not expose secret material on stdout/stderr.

---

# 71. RECOVERY / BACKUP SEMANTICS

No previous-secret selector/API.

Normal recovery:

```text
replace known-good secret
OR
clear managed override → deployment fallback
```

Operational recovery:

```text
restore coherent Settings DB
+
matching master key
```

No code in this TASK exports/backs up the master key.

Documentation must state:

```text
DB backup alone does not recover managed secret
key alone contains no secret
historical backup + matching key may decrypt historical ciphertext
backup retention/destruction is operational policy
```

---

# 72. DOCUMENTATION UPDATE

Update docs to describe:

```text
Stage-4 write-only Client Secret management
no read-back
Controller v3 read model
secret capability configuration
default capability behavior
master key production path/security
Settings DB v3/file-security requirement
migration/rollback requirement
restart activation
no live credential test
no Admin restart button
backup pair requirement
break-glass command
cryptography>=3.4.8
no forensic-erasure guarantee
```

Never include real production secret/key bytes.

`.env.example` may contain capability names but MUST NOT contain raw Omada secret material beyond the existing empty placeholder.

---

# 73. REQUIREMENTS / PRODUCTION COMPATIBILITY

`requirements.txt` must declare:

```text
cryptography>=3.4.8
```

Do not increase the minimum beyond 3.4.8 unless Tech Lead re-authorizes.

Implementation must work with Python/runtime APIs already used by the project and cryptography 3.4.8.

---

# 74. REQUIRED NEW / UPDATED TEST AREAS

Coder tests are deliberately TARGETED to Stage-4 implementation scope.

Coder is NOT responsible for full-repository regression.

Recommended focused files:

```text
tests/settings_control/test_controller_secret_crypto.py              [NEW]
tests/settings_control/test_controller_secret_repository.py          [NEW]
tests/settings_control/test_controller_secret_service.py             [NEW]
tests/settings_control/test_controller_secret_startup.py             [NEW]
tests/settings_control/test_secret_recovery.py                       [NEW]

tests/admin_web/test_controller_settings_stage4.py                   [NEW]
tests/admin_web/test_global_capabilities_stage4.py                   [NEW]

tests/settings_control/test_repository.py                            [UPDATE as needed]
tests/settings_control/test_services.py                              [UPDATE as needed]
tests/settings_control/test_bootstrap.py                             [UPDATE as needed]
tests/settings_control/test_run_integration.py                       [UPDATE as needed]

tests/admin_web/test_config.py                                      [UPDATE as needed]
tests/admin_web/test_settings_routes.py                              [UPDATE as needed]
tests/admin_web/test_controller_settings_stage3.py                   [UPDATE for V3 compatibility only]
tests/test_admin_controller_settings.py                             [UPDATE for V3 compatibility only]
tests/test_omada_configuration.py                                   [UPDATE as needed]
```

Do not make unrelated suites part of Coder's acceptance burden.

---

# 75. CRYPTO TESTS — MANDATORY

Cover:

```text
AESGCM/HKDF import
cryptography version compatibility evidence
32-byte key → exact derived key sizes
deterministic HKDF vector
encryption/decryption round-trip
nonce uniqueness
fixed plaintext frame = 4100
ciphertext = 4116
AAD exactness
wrong key failure
tampered ciphertext/tag failure
tampered nonce failure
AAD/version-id mismatch failure
secret length not inferable from ciphertext length
random padding differs
control character rejection
1-byte minimum
4096-byte maximum
>4096 rejection
Unicode UTF-8 byte-bound enforcement
```

No test should print raw secret.

---

# 76. FILE SECURITY TESTS — MANDATORY

Cover master key:

```text
correct metadata PASS
missing key
wrong size
wrong owner
wrong group
wrong mode
symlink
hard-link count !=1
non-regular file
bad parent type
bad parent owner/group/mode
```

Cover Settings DB:

```text
correct file/path PASS
wrong owner
wrong group
wrong mode
symlink
hard-link count !=1
non-regular file
writable parent group
writable parent other
setgid parent allowed
deployment-defined non-writable parent group allowed
```

Assert validator never chmod/chgrp/chown.

Use disposable/fake filesystem metadata or controlled Linux test environment; never mutate production.

---

# 77. SCHEMA / MIGRATION TESTS — MANDATORY

Cover:

```text
fresh DB creates v3
v2→v3 transaction
existing generations preserved
parent links preserved
ordinary overrides preserved
effective generation preserved
activation events preserved
ordinary audit preserved
Controller audit preserved
idempotency result_response_json preserved
old request payload hash becomes sha256 fingerprint kind/value
no migration-created generation
no migration-created secret row
no migration-created binding
no migration-created secret audit
generation0 has no binding
invalid current binding/version integrity fails closed
historical binding without live version permitted
Stage-3 source would reject v3 / documented downgrade boundary
```

Existing v1-upgrade compatibility must not regress.

---

# 78. GENERATION / ATOMICITY TESTS — MANDATORY

Cover:

```text
ordinary General mutation carries secret binding
ordinary Controller mutation carries secret binding
replace creates normal Settings generation
clear creates normal Settings generation
ownership change counts as changed even equal scalar
same configured managed secret is no-op
reuse retained effective version if implemented
crash/error before commit leaves no partial state
failure persisting receipt rolls back entire mutation
configured/effective managed versions may safely diverge
superseded pending row logically deleted
post-adoption old effective row logically deleted
failed adoption retains effective row
historical binding may outlive ciphertext row
```

---

# 79. IDEMPOTENCY TESTS — MANDATORY

Cover:

```text
same key + same normalized secret → exact replay
same key + different secret → 409
same secret + different key → different persisted HMAC fingerprints
fingerprint kind exact
domain=controller_secret
no raw canonical payload persisted
no raw secret persisted in idempotency
replay does not CAS current head
replay creates no generation/version/audit
receipt <=65536
General/Controller existing replay semantics unchanged
```

---

# 80. SECRET-TAINT SENTINEL TESTS — MANDATORY

Use a unique disposable sentinel raw secret.

Assert it is absent from:

```text
Controller GET text
secret POST success text
secret POST error text
HTML
JS fixture/bootstrap output
ordinary settings projections
settings_overrides
settings_secret_mutation_audit
settings_idempotency response
settings_idempotency request_fingerprint plaintext
application logs
telemetry fixtures
exception text
traceback text produced by handled failures
repr/str of secret-bearing models
metrics labels if touched
```

Also inspect the SQLite file bytes and assert the raw sentinel byte sequence is absent after a committed managed-secret replacement.

Ciphertext presence is expected; plaintext is not.

---

# 81. PUBLIC READ MODEL TESTS — MANDATORY

Cover Controller v3:

```text
api_version exact
existing non-secret V2 semantics preserved
client_secret exact safe field set
configured managed / effective environment → pending true
configured managed S2 / effective managed S1 → pending true
configured/effective same managed S1 → pending false
unrelated ordinary generation difference alone → pending false
clear pending → true when effective still managed
store outage → configured secret fields null, effective remains safe
key outage → secret_store unavailable while ordinary store may remain available
secret version id never serialized
secret hash/HMAC/length/prefix/suffix never serialized
mutation_available and secret_mutation_available independent
```

---

# 82. AUTHORIZATION TESTS — MANDATORY

Cover:

```text
default capability config = Stage-3 four caps
default excludes secret write
explicit five-cap grant accepted
malformed/unknown/duplicate/whitespace capability config fail closed
AdminPrincipal session captures startup capability snapshot
authorize_global checks principal grant
ordinary controller write does not imply secret write
secret write can exist without ordinary controller write
read capability still required for secret route
no Site context participates
capability change is not request-time reread
```

Existing Site-read authorization semantics must remain green in targeted affected tests.

---

# 83. HTTP SECRET ROUTE TESTS — MANDATORY

Cover:

```text
unauthenticated → 401
read without secret write → 403 controller_secret_forbidden
ordinary controller writer without secret write → 403
secret writer + read → permitted
feature disabled → 404
wrong CSRF → 400 invalid_csrf
missing Content-Length → 411
wrong media type → 415
body >32768 → 413
missing If-Match → 428
malformed If-Match → 400
stale If-Match → 412
bad Idempotency-Key → 400
query params → 400
duplicate JSON key → 400
unknown field → 400
replace missing secret → 400/422 according to exact parser-vs-validation boundary
empty/whitespace secret → 422
too-long secret → 422
clear with secret field → 400
replace success → 201
replace no-op → 200
clear success → 201
clear no-op → 200
same-key replay exact receipt
same-key different secret → 409
secret store unavailable → 503
settings store unavailable → 503
no raw secret in any response
```

---

# 84. UI TESTS — MANDATORY

Cover rendered/JS behavior for:

```text
read-only Controller user:
  safe secret status visible
  no Replace secret
  no Use deployment secret

ordinary Controller writer only:
  URL/ID/Client ID edit remains
  no secret controls

secret writer:
  secret controls independently appear
  ordinary fields may remain read-only if ordinary capability absent

two password fields
autocomplete=new-password
type=password
no prefill
paste not blocked
mismatch prevents POST
confirmation contains required warnings and no secret
success clears both fields
server validation error clears both fields
403/409/412/413/500/503 clears both fields
network failure clears both fields
cancel clears both fields
412 reloads Controller state and discards old retry key
network-uncertain workflow may retain only Idempotency-Key
no localStorage/sessionStorage/cookie/query-string/history usage
GET after success/replay
managed source label rendered safely
no secret length/mask/fingerprint
no restart button
```

---

# 85. STARTUP / ADOPTION TESTS — MANDATORY

Cover exact ordering/effects:

```text
environment-only secret + no master key:
  startup succeeds
  secret management unavailable
  provider gets deployment secret

managed secret + valid key/security:
  decrypt before provider construction
  provider gets managed secret

managed binding + missing key:
  fail closed before provider
  effective generation unchanged
  safe failure attested when possible

managed binding + wrong key:
  fail closed

managed binding + missing version row:
  fail closed

managed binding + tampered ciphertext/tag:
  fail closed

managed binding + DB file-security failure:
  fail closed

no managed binding + DB/key security failure:
  deployment secret may start
  secret management unavailable

provider-capable Controller/OAuth I/O before adoption:
  ZERO

Observation FIX2 preparation ordering remains:
  prepare read boundary
  Analytics
  Admin
  durable adoption
  provider-capable starts
  HTTP serve
```

Do not move Observation/Current-State/provider-capable starts back before adoption.

---

# 86. BREAK-GLASS TESTS — MANDATORY

Cover:

```text
exact CLI command/argument parsing
schema v3 required
CAS exact
binding exists → new generation + no new binding
ordinary overrides copied
secret-safe recovery audit exact
principal_type=local_operator
source_ip=local
old secret not decrypted
no master key required to clear binding
no Controller I/O
no systemd mutation
no environment mutation
current effective version retained if still referenced
unreferenced pending version logically deleted
no current binding → no write / controlled result
wrong expected generation → no write
stdout/stderr secret-free
```

---

# 87. Coder TARGETED TEST COMMANDS

Coder MUST run only targeted Stage-4/affected Settings/Admin tests, not the full repository.

Minimum intended command set:

```text
python -m pytest -q \
  tests/settings_control/test_controller_secret_crypto.py \
  tests/settings_control/test_controller_secret_repository.py \
  tests/settings_control/test_controller_secret_service.py \
  tests/settings_control/test_controller_secret_startup.py \
  tests/settings_control/test_secret_recovery.py \
  tests/settings_control/test_repository.py \
  tests/settings_control/test_services.py \
  tests/settings_control/test_bootstrap.py \
  tests/settings_control/test_run_integration.py \
  tests/admin_web/test_controller_settings_stage4.py \
  tests/admin_web/test_global_capabilities_stage4.py \
  tests/admin_web/test_config.py \
  tests/admin_web/test_settings_routes.py \
  tests/admin_web/test_controller_settings_stage3.py \
  tests/test_admin_controller_settings.py \
  tests/test_omada_configuration.py
```

If exact test filenames differ because Coder reasonably consolidates new tests, handoff must list the exact targeted commands actually run.

Coder MUST NOT use full-repository pytest as acceptance evidence for this TASK.

Full repository regression is Tech Lead responsibility after handoff.

---

# 88. STATIC / LOCAL CHECKS

Coder MUST run:

```text
python -m compileall -q app run.py

node --check app/admin_web/static/controller_settings.js

git diff --check
```

Also record:

```text
python -c "import cryptography; print(cryptography.__version__)"
```

and a safe primitive-import check.

No package installation.

---

# 89. SECRET-SAFE EVIDENCE RULE

Handoff MUST NOT contain:

```text
real OMADA_CLIENT_SECRET
master-key bytes
ciphertext copied from production
real secret HMAC
real encryption key
```

All crypto evidence uses disposable test values only.

Never copy production `/etc/default/captive-portal` secret content.

Never output master key.

---

# 90. DOCUMENTED PRODUCTION PRECONDITIONS — DO NOT EXECUTE

Coder only documents; does not perform:

```text
1. coherent pre-Stage4 v2 Settings DB backup
2. create/provision 32-byte production master key
3. /etc/captiveportal owner/mode preparation
4. master-key root:admin 0640
5. Settings DB admin:admin 0600
6. explicit WEB_ADMIN_GLOBAL_CAPABILITIES grant if owner wants secret-write UI
7. dependency version verification
8. controlled service restart
9. v2→v3 migration verification
10. authenticated Controller v3/UI acceptance
11. no-secret leakage/log checks
```

No production command execution by Coder.

---

# 91. ROLLBACK CONTRACT — DOCUMENT ONLY

Stage-4 code against schema v3 cannot be downgraded in place to Stage-3 code.

Production rollback requires:

```text
Stage-3 accepted code
+
pre-Stage4 v2 Settings DB restore
+
valid deployment/environment OMADA_CLIENT_SECRET
```

If managed secret had been used, historical Stage-4 DB/key pair may contain decryptable old ciphertext and must be handled under operational backup policy.

No automatic downgrade code.

---

# 92. STOP CONDITIONS

STOP and return evidence if any of these occur:

```text
baseline HEAD/TREE mismatch
dirty baseline before work
cryptography dependency absent/incompatible and tests cannot run
implementation requires package installation
implementation requires production chmod/chown/key creation
architecture requires another secret than OMADA_CLIENT_SECRET
need for hot reconnect/systemd control
need to expose current/previous raw secret
need to put raw secret into ordinary SettingsStore override
need to persist plain SHA256(secret)
cannot keep provider I/O post-adoption
schema migration cannot preserve existing idempotency response semantics
another production file outside authorized scope is required
new unrelated failing targeted test cannot be explained
secret sentinel appears in prohibited surface
```

Do not work around a stop condition silently.

---

# 93. BRANCH / COMMIT

Suggested branch:

```text
feature/admin-settings-04-controller-secret-management
```

Suggested single candidate commit subject:

```text
ADMIN-SETTINGS-04: add write-only Omada client secret management
```

At initial implementation handoff:

```text
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

---

# 94. REQUIRED HANDOFF

Return exactly enough evidence for independent Tech Lead source review:

```text
TASK=TASK-ADMIN-SETTINGS-04

BASE_HEAD=
BASE_TREE=

BRANCH=
CANDIDATE_COMMIT=
CANDIDATE_PARENT=
CANDIDATE_TREE=

WORKTREE_STATE=
GIT_STATUS_PORCELAIN=

CHANGED_FILES=
ADDITIONS=
DELETIONS=
CHANGED_FILES_LIST=

FULL_BASE_TO_CANDIDATE_PATCH_PATH=
FULL_PATCH_BYTES=
FULL_PATCH_SHA256=
PATCH_REVERSE_APPLY_CHECK=

SCHEMA_VERSION=
MIGRATION_V2_TO_V3=
MIGRATION_HISTORY_PRESERVATION=

CRYPTOGRAPHY_VERSION=
AESGCM_IMPORT=
HKDF_IMPORT=
SHA256_IMPORT=
CRYPTO_TARGETED_TESTS=

GLOBAL_CAPABILITY_DEFAULT=
SECRET_CAPABILITY=
SECRET_CAPABILITY_DEFAULT_GRANTED=

SECRET_STORE_DB_SECURITY=
MASTER_KEY_SECURITY=
SECRET_STORE_STATE_TESTS=

RAW_SECRET_IN_SETTINGS_OVERRIDES=
RAW_SECRET_IN_PUBLIC_API=
RAW_SECRET_IN_AUDIT=
RAW_SECRET_IN_IDEMPOTENCY_RESPONSE=
RAW_SECRET_IN_DB_FILE_SENTINEL_SCAN=
RAW_SECRET_IN_LOG_SENTINEL_SCAN=

PRE_ADOPTION_PROVIDER_CALLS=

CONTROLLER_READ_MODEL_VERSION=
SECRET_MUTATION_API=
BREAK_GLASS_COMMAND=

TARGETED_TEST_COMMANDS=
TARGETED_TEST_RESULT=

COMPILEALL=
NODE_CHECK=
GIT_DIFF_CHECK=

FULL_REPOSITORY_PYTEST=
NOT_RUN_BY_CODER_PER_TASK

OPEN_P0=
OPEN_P1=

PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

Attach:

```text
1. full handoff markdown
2. full BASE→CANDIDATE patch
```

---

# 95. ACCEPTANCE CRITERIA

Coder candidate is source-review eligible only if:

```text
exact baseline
clean one-commit candidate
authorized scope only
schema v3 migration exact
Stage-1/3 ordinary Settings behavior preserved in targeted tests
no secret read-back
no plaintext secret persistence
crypto/storage contract implemented
real capability separation implemented
secret mutation route exact
Controller v3 exact safe model
restart/adoption semantics preserved
zero provider/OAuth I/O pre-adoption
break-glass clear implemented secret-free
targeted tests PASS
static checks PASS
no open P0/P1 identified by Coder
```

---

# 96. GOVERNANCE GATE

At TASK issuance:

```text
LOCAL IMPLEMENTATION = GO
TARGETED CODER TESTING = GO

FULL REPOSITORY REGRESSION = TECH LEAD RESPONSIBILITY

PUSH = HOLD
PR = HOLD
MERGE = NO
DEPLOY = NO
PRODUCTION = NO
SYSTEMD ACTION = NO
PACKAGE INSTALL = NO
```

Coder stops after local candidate + targeted evidence.

Tech Lead then performs:

```text
source review
broad affected regression
full repository regression
publication gate
PR gate
merge gate
deployment gate
production acceptance
```

separately.
