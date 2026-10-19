# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 4 — OMADA CONTROLLER SECRET MANAGEMENT
### АРХИТЕКТУРНЫЙ КОНТРАКТ v0.1
### DRAFT FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Область:** Admin UI → Settings → Controller  
**Этап:** Stage 4 — Omada Controller Secret Management  
**Роль:** Architect  
**Статус:** `DRAFT FOR TECH LEAD REVIEW`

---

# 0. AUTHORITY / BASELINE / GATE

Точный authoritative baseline:

```text
HEAD =
78296b2e9a35664c0d285cf0c7d22b2fa465311a

TREE =
f965d4604652db52d5f97b1f5d3abe36263ee78b

PR =
#187 merged

STAGE 3 =
PRODUCTION ACCEPTED
```

Текущий Stage-3 foundation считается замороженным:

```text
Stage 1:
SettingsStore
generations
activation
audit
idempotency
12 GLOBAL safe writable integer settings

Stage 2:
Controller read model

Stage 3:
writable non-secret Controller settings:
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

Stage 4 является только архитектурой.

```text
STAGE 4 IMPLEMENTATION TASK = HOLD
CODER = HOLD
PRODUCTION CHANGE = NO
SYSTEMD ACTION = NO
```

Если repository baseline изменится до подготовки implementation TASK:

```text
STOP
→ Tech Lead baseline reconciliation
```

Нельзя молча реализовывать этот контракт против другого HEAD/TREE.

---

# 1. SOURCE-VERIFIED CURRENT STATE

Текущий Stage-3 source подтверждает:

```text
SettingsStore schema = v2

SettingsDefinitionRegistry =
15 ordinary definitions
=
12 General integers
+
3 Controller strings

OMADA_CLIENT_SECRET
не является SettingsDefinition

Controller read API =
GET /admin/api/v1/settings/controller

Controller non-secret mutation API =
POST /admin/api/v1/settings/controller/generations

Controller write capability =
admin.write.settings.controller

global Settings ETag =
"settings-g<configured_generation>"
```

Текущий canonical runtime object:

```text
OmadaControllerRuntimeConfig
```

содержит:

```text
controller_url
controller_id
client_id
client_secret
verify_ssl
```

`client_secret` уже исключён из dataclass repr.

Текущий shared `OmadaProvider` получает только injected `OmadaControllerRuntimeConfig`.

Независимого provider-side `get_settings()` больше нет.

Stage 3 также уже гарантирует:

```text
provider-capable workers
НЕ выполняют Controller/OAuth I/O
до durable adoption generation G
```

Stage 4 не переоткрывает эти решения.

---

# 2. ТОЧНЫЙ SCOPE STAGE 4

Stage 4 добавляет только:

```text
write-only Admin replacement
для OMADA_CLIENT_SECRET

managed encrypted secret persistence

safe secret generation linkage

secret-safe idempotency

secret-safe audit

configured/effective/pending secret metadata

restart-based activation

clear managed secret override
→ fallback to deployment/environment secret

backup / recovery contract

strict browser secret handling
```

Stage 4 НЕ добавляет:

```text
secret read-back

secret reveal

secret export

secret history viewer

generic secret vault UI

VERIFY_SSL mutation

Admin systemd control

restart button

hot reconnect

hot provider recreation

Controller Test Connection

live credential validation

token reset UI

OAuth client create/delete

Omada-side configuration mutation

multi-controller support

Site-scoped Controller configuration

generic environment editor

Stage 5 Portal Settings
```

---

# 3. ОСНОВНОЕ АРХИТЕКТУРНОЕ РЕШЕНИЕ

Stage 4 использует:

```text
ONE existing SettingsStore SQLite
+
dedicated encrypted Controller secret tables
+
external host-local master key
```

То есть физически секретный ciphertext хранится в:

```text
/opt/CaptivePortal/data/settings.sqlite3
```

но логически raw secret принадлежит отдельному boundary:

```text
ControllerSecretRepository
```

а НЕ ordinary SettingsDefinition / settings_overrides.

Canonical chain:

```text
Admin secret mutation
        ↓
ControllerSecretMutationService
        ↓
one SettingsStore write transaction
        ├── encrypted secret version
        ├── normal Settings generation
        ├── generation→secret binding
        ├── secret-safe audit
        └── secret-safe idempotency receipt
        ↓
configured generation G
        ↓
external captive-portal.service restart
        ↓
startup secret resolution
        ↓
one OmadaClientSecretResolution
        ↓
one OmadaControllerRuntimeConfig
        ↓
shared OmadaProvider
        ↓
durable Settings adoption
        ↓
effective generation G
```

Permanent:

```text
RAW SECRET
NEVER enters:
settings_overrides
ordinary SettingsDefinition
normal SettingReadModel
Controller GET response
audit values
idempotency response
HTML
JavaScript bootstrap state
logs
telemetry
exception text
```

---

# 4. S4-01 — SECRET STORAGE OWNER

Canonical durable owner:

```text
ControllerSecretRepository
```

Logical responsibility:

```text
encrypted OMADA_CLIENT_SECRET versions only
```

Physical persistence:

```text
dedicated encrypted tables
inside the existing settings.sqlite3
```

Причина выбора:

```text
secret write
+
Settings generation
+
binding
+
audit
+
idempotency

могут commit'иться
одной SQLite transaction
```

Не создаются:

```text
second generic Settings DB
second generation chain
second CAS authority
second Settings mutation subsystem
```

`SettingsStore` остаётся единственным generation/CAS owner.

`ControllerSecretRepository` является узким secret-material boundary внутри того же durable SQLite transaction domain.

---

# 5. S4-02 — AT-REST PROTECTION

Raw UI-managed secret хранится:

```text
ENCRYPTED AT REST
```

Canonical algorithm:

```text
AES-256-GCM
```

Approved implementation primitive:

```text
cryptography.hazmat.primitives.ciphers.aead.AESGCM
```

Stage 4 явно разрешает dependency:

```text
cryptography
```

для стандартной authenticated encryption.

Самодельная криптография запрещена.

---

# 6. MASTER KEY

Canonical production master-key path:

```text
/etc/captiveportal/omada-controller-secret-master.key
```

Формат:

```text
exactly 32 raw random bytes
no hex
no base64
no newline
```

Генерация:

```text
CSPRNG
```

Runtime application:

```text
НЕ генерирует key автоматически
НЕ заменяет key
НЕ ротирует key
НЕ chmod/chown key
```

Master key provisioning является отдельным SysAdmin/deployment action перед production activation Stage 4.

---

# 7. MASTER-KEY FILE SECURITY

Production requirements:

```text
path =
/etc/captiveportal/omada-controller-secret-master.key

parent directory =
/etc/captiveportal

directory owner =
root

directory group =
admin

directory mode =
0750

key owner =
root

key group =
admin

key mode =
0640

key type =
regular file only

key size =
exactly 32 bytes

symlink =
forbidden

hard-link count =
1
```

Current service runtime identity:

```text
User=admin
Group=admin
```

Application reads the key but не имеет authority на его замену.

Путь master key не является Admin-editable.

Stage 4 V1 не вводит UI/config mutation master-key path.

---

# 8. KEY DERIVATION

Из 32-byte master key выводятся два независимых subkeys.

Canonical KDF:

```text
HKDF-SHA256
```

Encryption key:

```text
HKDF-SHA256(
    master_key,
    salt = b"CaptivPortal.Stage4.ControllerSecret.v1",
    info = b"encryption",
    length = 32
)
```

Idempotency HMAC key:

```text
HKDF-SHA256(
    master_key,
    salt = b"CaptivPortal.Stage4.ControllerSecret.v1",
    info = b"idempotency",
    length = 32
)
```

AES key и idempotency key не являются одним и тем же key material.

---

# 9. ENCRYPTED SECRET FRAME

Maximum normalized secret size:

```text
4096 UTF-8 bytes
```

Перед encryption строится fixed-size plaintext frame:

```text
4 bytes:
unsigned big-endian secret byte length

then:
normalized UTF-8 secret bytes

then:
CSPRNG random padding

until secret payload area =
exactly 4096 bytes
```

Total plaintext frame:

```text
4100 bytes
```

AES-GCM nonce:

```text
12 random bytes
```

AESGCM ciphertext, включая authentication tag:

```text
4116 bytes
```

Следовательно ciphertext length не раскрывает actual secret length.

---

# 10. SECRET VERSION AAD

Каждый secret version имеет internal:

```text
secret_version_id = UUIDv4
```

Canonical AES-GCM AAD:

```text
b"CaptivPortal\x00OMADA_CLIENT_SECRET\x00"
+
ASCII(secret_version_id)
+
b"\x00v1"
```

AAD не содержит secret.

Secret version ID не является hash/fingerprint secret value.

---

# 11. THREAT / DISCLOSURE MODEL

Если attacker получает только:

```text
settings.sqlite3
```

он может узнать:

```text
что managed secret override существует или существовал
opaque version IDs
generation linkage
change timestamps
safe actor/audit metadata
fixed-size ciphertext
```

Он НЕ получает:

```text
raw secret
secret prefix/suffix
secret length
reversible plaintext
offline-verifiable plain SHA-256 secret digest
```

Если attacker получает только:

```text
master-key file
```

он не получает secret material без SQLite ciphertext.

Если attacker получает одновременно:

```text
settings.sqlite3
+
matching master key
```

managed secrets могут быть decrypted.

Stage 4 не заявляет защиту от полного host/root compromise.

---

# 12. S4-03 — SECRET IDENTITY / REFERENCE MODEL

Raw secret НЕ входит в ordinary Settings generation values.

Stage 4 добавляет internal:

```text
secret_version_id
```

и immutable generation binding:

```text
configured generation G
→ OMADA_CLIENT_SECRET
→ secret version S
```

Generation linkage находится в:

```text
settings_secret_bindings
```

Raw secret value отсутствует в этой таблице.

Если generation не имеет managed secret override:

```text
settings_secret_bindings row отсутствует
```

и secret разрешается из deployment/environment layer.

---

# 13. SETTINGS GENERATION SNAPSHOT SEMANTICS

Каждая новая Settings generation является complete snapshot не только normal overrides, но и managed-secret ownership state.

Поэтому любое создание generation:

```text
General mutation
Controller non-secret mutation
Controller secret mutation
```

обязано:

```text
copy parent secret binding
```

если secret mutation специально его не меняет.

Generation 0:

```text
NO managed secret binding
```

Это означает:

```text
deployment/environment secret controls OMADA_CLIENT_SECRET
```

---

# 14. S4-04 — SECRET PRECEDENCE

Exact precedence:

```text
managed secret override
>
explicit process environment OMADA_CLIENT_SECRET
>
repository default
```

Canonical source enum для Client Secret:

```text
managed_secret_override
environment
repository_default
```

`managed_secret_override` существует только когда current configured generation имеет `settings_secret_bindings` row.

---

# 15. CLEAR / RESET SEMANTICS

Stage 4 допускает:

```text
clear_secret_override
```

Meaning:

```text
remove managed secret binding
for new configured generation

→ return ownership to deployment/environment layer
```

Это НЕ:

```text
delete OMADA_CLIENT_SECRET
set empty secret
copy environment secret into secret store
```

Clear mutation разрешена только если resulting fallback configuration локально валидна.

Если fallback secret отсутствует/пуст после current normalization:

```text
422 validation_failed
```

Новая generation не создаётся.

---

# 16. FIRST STAGE-4 TRANSITION FROM DEPLOYMENT SECRET

Migration НЕ копирует current environment secret в encrypted store.

До первого Admin replacement:

```text
configured secret source =
environment
или repository_default
```

После первого successful Admin replacement:

```text
configured secret source =
managed_secret_override
```

После `clear_secret_override`:

```text
configured source
возвращается к
environment / repository_default
```

Current raw deployment secret никогда не нужно вводить в Stage-4 migration.

---

# 17. SECRET VALIDATION

Stage 4 выбирает:

```text
LOCAL/SYNTACTIC VALIDATION ONLY
```

Live Omada credential test:

```text
NO
```

На Save НЕ выполняются:

```text
OAuth token request
Controller HTTP request
credential verification
/sites request
Test Connection
token reset
provider reconnect
```

Это сохраняет existing activation/I-O boundary.

---

# 18. SECRET NORMALIZATION

Canonical local normalization использует existing runtime semantic:

```text
Python str.strip()
```

То есть:

```text
leading/trailing Unicode whitespace
удаляется
```

После normalization:

```text
secret must be non-empty
UTF-8 encoded size = 1..4096 bytes
```

Дополнительно запрещены внутри normalized secret:

```text
U+0000..U+001F
U+007F
```

No other charset/case normalization is introduced.

Secret не lower-case'ится.

Secret не Unicode-normalize'ится.

Secret не truncates silently.

---

# 19. BAD BUT SYNTACTICALLY VALID SECRET

Stage 4 сознательно допускает ситуацию:

```text
secret syntactically valid
but wrong for Omada
```

Save может быть успешным.

После restart generation может быть successfully adopted локально.

Поздний OAuth failure является:

```text
operational Omada authentication failure
```

а НЕ:

```text
Settings activation_failed
```

Stage 4 не превращает Settings adoption в live Controller health test.

---

# 20. S4-05 — WRITE-ONLY API

Exact endpoint:

```text
POST /admin/api/v1/settings/controller/client-secret/generations
```

API version:

```text
admin.settings.controller.secret.mutation.v1
```

Content-Type:

```text
application/json
```

Maximum HTTP request body:

```text
32768 bytes
```

Maximum normalized secret:

```text
4096 UTF-8 bytes
```

Maximum operations per request:

```text
1
```

No mixed secret + non-secret batch.

---

# 21. REPLACE REQUEST

Canonical request:

```json
{
  "operation": "replace_secret",
  "secret": "<new secret>"
}
```

Exact top-level fields:

```text
operation
secret
```

Unknown fields rejected.

Duplicate JSON object members rejected.

`secret` must be JSON string.

---

# 22. CLEAR REQUEST

Canonical:

```json
{
  "operation": "clear_secret_override"
}
```

Exact fields:

```text
operation
```

`secret` is forbidden for clear operation.

---

# 23. REQUEST TRANSPORT RULES

Required headers:

```text
Content-Type: application/json
X-CSRF-Token: <current Admin session CSRF>
If-Match: "settings-gN"
Idempotency-Key: <UUID>
```

Missing `Content-Length`:

```text
411 length_required
```

Body > 32768:

```text
413 request_too_large
```

Wrong media type:

```text
415 unsupported_media_type
```

Missing If-Match:

```text
428 precondition_required
```

Stale global generation:

```text
412 stale_generation
```

No query parameters accepted.

---

# 24. S4-17 — AUTHORIZATION

Existing read capability remains:

```text
admin.read.settings.controller
```

Existing non-secret write capability remains:

```text
admin.write.settings.controller
```

Stage 4 introduces distinct stronger capability:

```text
admin.write.settings.controller.secret
```

Secret mutation endpoint requires BOTH:

```text
admin.read.settings.controller
+
admin.write.settings.controller.secret
```

`admin.write.settings.controller` alone does NOT permit secret replacement.

Current `platform_operator` may receive the new secret capability.

Site-scoped roles do not inherit it.

No Site authorization participates.

---

# 25. SECRET MUTATION SUCCESS RECEIPT

Changed mutation:

```text
201 Created
```

No-op:

```text
200 OK
```

Canonical bounded response:

```json
{
  "api_version": "admin.settings.controller.secret.mutation.v1",
  "request_id": "<uuid>",
  "scope": {
    "type": "global"
  },
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
operation = clear_secret_override
```

Response MUST NOT contain:

```text
secret
secret_version_id
secret hash
secret HMAC
secret length
prefix
suffix
ciphertext
nonce
```

Browser MUST re-GET Controller read model after every successful POST.

---

# 26. SECRET ERROR CONTRACT

Canonical errors:

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

Validation details may contain only safe reason codes, for example:

```json
{
  "field": "client_secret",
  "reason": "required"
}
```

или:

```json
{
  "field": "client_secret",
  "reason": "too_long"
}
```

Rejected value не echo'ится.

---

# 27. S4-06 — SECRET-SAFE IDEMPOTENCY

Raw secret НЕ участвует в persisted SHA-256 payload hash.

Secret mutation использует:

```text
HMAC-SHA256
```

с derived `idempotency` key.

Canonical request fingerprint message:

```text
canonical JSON UTF-8
of:

{
  "api_version": "admin.settings.controller.secret.mutation.v1",
  "principal_type": "...",
  "principal_name": "...",
  "idempotency_key": "...",
  "operation": "replace_secret",
  "secret": "<normalized secret>"
}
```

для replace.

Для clear поле `secret` отсутствует.

Persisted value:

```text
HMAC-SHA256(...)
```

Raw canonical message НЕ сохраняется.

---

# 28. WHY HMAC, NOT PLAIN HASH

Plain:

```text
SHA256(secret)
```

запрещён.

Причина:

```text
settings DB attacker
не должен получить offline secret-verification oracle
```

HMAC key находится только в external master-key domain.

Idempotency-Key включён в HMAC input, поэтому одинаковый secret под разными Idempotency-Key не создаёт одинаковый persisted fingerprint.

---

# 29. IDEMPOTENT REPLAY

Lookup identity:

```text
principal_type
+
principal_name
+
scope_type=global
+
mutation_domain=controller_secret
+
Idempotency-Key
```

Если record существует:

```text
same HMAC fingerprint
→ return exact original success receipt

different HMAC fingerprint
→ 409 idempotency_conflict
```

Successful replay выполняет:

```text
NO current-head CAS
NO new secret decrypt
NO new secret version
NO new generation
NO new audit
NO Controller I/O
```

Browser после replay всё равно выполняет GET Controller read model.

---

# 30. SETTINGS IDEMPOTENCY SCHEMA EVOLUTION

SettingsStore v3 generalizes current idempotency fields.

Canonical logical fields become:

```text
request_fingerprint_kind
request_fingerprint
```

Allowed fingerprint kinds:

```text
sha256_canonical_json_v1
hmac_sha256_controller_secret_v1
```

Allowed mutation domains:

```text
general
controller
controller_secret
```

Existing Stage-1/3 idempotency rows migrate as:

```text
request_fingerprint_kind =
sha256_canonical_json_v1

request_fingerprint =
existing request_payload_hash
```

Existing successful response bytes/semantics remain unchanged.

---

# 31. S4-09 — GENERATION SEMANTICS

Secret replacement создаёт NORMAL global Settings configured generation.

No separate secret-generation counter exists.

One mutation transaction atomically performs:

```text
optional new encrypted secret version S
+
new Settings generation G
+
complete copied ordinary overrides
+
generation→secret binding
+
secret-safe mutation audit
+
secret-safe idempotency receipt
+
secret-version GC
```

`configured_generation` remains common global Settings generation.

ETag remains:

```text
"settings-g<configured_generation>"
```

Unrelated General/Controller mutation therefore может stale secret form.

Это intentional.

---

# 32. SECRET VERSION REUSE / NO-OP

For a new replace request:

1. Compare against current configured managed secret, if one exists.

```text
same normalized secret
→ semantic no-op
→ no new generation
→ no new secret version
→ 200
```

2. If different from configured secret, but exactly equals another currently retained managed version, such as the current effective version:

```text
new generation MAY bind that existing retained secret_version_id
```

No duplicate ciphertext version required.

3. Otherwise:

```text
new UUIDv4 secret_version
+
new encrypted ciphertext
```

Secret comparison is in memory only and uses constant-time byte comparison where practical.

---

# 33. OWNERSHIP CHANGE IS NOT A NO-OP

If current configured source is:

```text
environment
```

and operator submits a managed secret whose scalar happens to equal environment secret:

```text
ownership changes:
deployment
→ managed_secret_override
```

Therefore:

```text
changed = true
new generation required
```

Similarly:

```text
managed override
→ clear override
```

creates a generation even if resulting fallback secret happens to have the same scalar value.

---

# 34. CROSS-CRASH ATOMICITY

Because encrypted secret rows and generation metadata are in the SAME SQLite DB transaction:

Crash before commit:

```text
NO new secret version
NO new generation
NO binding
NO audit
NO idempotency success
```

Crash after commit:

```text
ALL above state is durable
```

No cross-file two-phase commit is required for secret mutation.

Master key is read-only/static and never changed by the transaction.

---

# 35. SETTINGS SECRET BINDING TABLE

Stage 4 introduces:

```text
settings_secret_bindings
```

Logical schema:

```text
generation_id
    INTEGER PRIMARY KEY
    REFERENCES settings_generations(generation_id)

setting_key
    TEXT NOT NULL
    CHECK(setting_key='OMADA_CLIENT_SECRET')

secret_version_id
    TEXT NOT NULL
```

Important:

```text
NO foreign key
from historical binding
to controller_secret_versions
```

by design.

Reason:

```text
historical generation may retain opaque provenance
after old secret material has been securely destroyed
```

`settings_secret_bindings` rows are immutable.

---

# 36. ENCRYPTED SECRET VERSION TABLE

Stage 4 introduces:

```text
controller_secret_versions
```

Logical schema:

```text
secret_version_id
    TEXT PRIMARY KEY

setting_key
    TEXT NOT NULL
    CHECK(setting_key='OMADA_CLIENT_SECRET')

crypto_schema_version
    INTEGER NOT NULL
    CHECK(crypto_schema_version=1)

nonce
    BLOB NOT NULL
    CHECK(length(nonce)=12)

ciphertext
    BLOB NOT NULL
    CHECK(length(ciphertext)=4116)

created_at_utc
    TEXT NOT NULL
```

Rows are never updated.

Deletion is permitted only through secret-version lifecycle/GC repository methods.

No API exposes this table.

---

# 37. SECRET MATERIAL RETENTION

Stage 4 intentionally does NOT provide unlimited UI-managed secret history.

Encrypted secret versions retained are exactly those referenced by:

```text
current configured head
OR
current effective_generation
```

Therefore normal maximum retained material:

```text
1 version when configured == effective

2 versions while replacement is pending
```

If another replacement happens before restart:

```text
old pending version
becomes unreferenced
→ destroyed in the same mutation transaction
```

After successful adoption of new configured generation:

```text
previous effective version
becomes unreferenced
→ destroyed in the same activation transaction
```

Historical settings generations retain only opaque version IDs.

---

# 38. NO SECRET HISTORY ROLLBACK

Stage 4 V1 does NOT allow:

```text
"rollback to previous UI-managed secret"
without knowing/re-entering that secret
```

There is no:

```text
previous secret selector
secret history screen
rollback_secret_version API
```

Recovery is:

```text
replace with a known-good secret
OR
clear managed override → deployment/environment fallback
```

This minimizes durable secret history.

---

# 39. S4-14 — SECRET-SAFE AUDIT

Stage 4 adds:

```text
settings_secret_mutation_audit
```

Audit contains only:

```text
generation_id
parent_generation_id

principal_type
principal_name
source_ip
request_id
idempotency_key nullable

timestamp_utc

scope_type = global
setting_key = OMADA_CLIENT_SECRET

operation =
replace_secret
|
clear_secret_override
|
clear_secret_override_recovery

previous_override_present
new_override_present

previous_source
new_source

apply_requirement = main_service_restart
activation_target = captive-portal.service
```

Audit MUST NOT contain:

```text
old secret
new secret
ciphertext
nonce
secret_version_id
secret length
secret prefix
secret suffix
secret hash
secret HMAC
request body
```

Даже HMAC idempotency fingerprint не копируется в audit.

Audit rows immutable.

Semantic no-op не создаёт mutation-audit row.

---

# 40. S4-08 — PUBLIC SECRET STATE MODEL

Existing Controller GET path remains:

```text
GET /admin/api/v1/settings/controller
```

Schema version becomes:

```text
admin.settings.controller.v3
```

Existing non-secret Stage-3 field meanings остаются unchanged.

`client_secret` becomes exact safe model:

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

---

# 41. PUBLIC ENUMS

`configured_presence` / `effective_presence`:

```text
configured
not_configured
null
```

Source:

```text
managed_secret_override
environment
repository_default
null
```

`persisted_secret_override_present`:

```text
true
false
null
```

`pending_replacement`:

```text
true
false
null
```

`secret_store_state`:

```text
available
unavailable
```

Null means:

```text
that side cannot be truthfully determined
```

not `not_configured`.

---

# 42. `pending_replacement` EXACT SEMANTICS

When SettingsStore is available, compare secret ownership identity at:

```text
configured_generation
vs
effective_generation
```

`pending_replacement=true` if secret state differs by:

```text
source
OR
managed secret_version_id
```

Examples:

```text
effective environment
configured managed S1
→ true

effective managed S1
configured managed S2
→ true

effective managed S1
configured no managed binding/environment
→ true

effective managed S1
configured managed S1
→ false
even if unrelated global generation differs
```

Secret version ID is internal comparison material only.

It is NEVER serialized.

---

# 43. SETTINGSSTORE OUTAGE WHILE PROCESS IS RUNNING

If running process already has trustworthy effective Controller snapshot but SettingsStore becomes unavailable:

```text
effective_presence
effective_source
remain available
```

Configured/persisted secret fields become:

```text
configured_presence = null
configured_source = null
persisted_secret_override_present = null
pending_replacement = null
```

Secret mutation:

```text
unavailable
```

No cached configured secret state is presented as current.

This preserves Stage-3 outage semantics.

---

# 44. MASTER KEY UNAVAILABLE WHILE RUNNING

If process already adopted an effective secret and master key later becomes unreadable:

```text
running OmadaProvider may continue
with its already-held in-memory effective secret
```

Controller GET may still show:

```text
effective_presence
effective_source
```

Secret mutation becomes:

```text
503 controller_secret_store_unavailable
```

If configured head requires a managed secret, next restart will fail closed unless key availability is restored.

No runtime fallback to environment occurs merely because key disappeared.

---

# 45. S4-10 — ACTIVATION

Secret replacement uses the SAME Stage-3 activation model:

```text
save
→ configured generation G
→ pending_main_restart
→ external captive-portal.service restart
→ resolve exact generation G
→ decrypt exact configured secret if managed
→ build OmadaControllerRuntimeConfig(G)
→ compose provider-capable runtime with NO Controller I/O
→ durable adoption G
→ only then Controller/OAuth I/O allowed
```

No:

```text
Admin restart button
systemctl authority
hot reconnect
hot provider recreation
```

---

# 46. WHEN SECRET BECOMES EFFECTIVE

A newly stored managed secret becomes effective only when:

```text
new captive-portal.service process
has resolved/decrypted it
+
built the canonical OmadaControllerRuntimeConfig
+
constructed shared OmadaProvider
+
completed required pre-I/O composition
+
durably adopted the exact Settings generation
```

Save itself never changes effective secret.

---

# 47. S4-11 — STARTUP SECRET RESOLUTION

Canonical startup:

```text
1. get_settings()
   → deployment/environment base

2. bootstrap SettingsStore
   → exact configured generation G
   → ordinary overrides
   → secret binding for G

3. build non-secret ResolvedSettingsSnapshot(G)

4. ControllerSecretResolver.resolve(
       generation=G,
       binding,
       deployment_base_secret,
       explicit_environment_names
   )

5. produce ONE OmadaClientSecretResolution

6. build ONE OmadaControllerRuntimeConfig
   from:
   non-secret resolved settings
   +
   OmadaClientSecretResolution

7. create ONE shared OmadaProvider

8. create secret-free public Controller snapshot

9. durable Settings adoption

10. start provider-capable workers / serve
```

No component independently reads secret storage after this composition boundary.

---

# 48. `OmadaClientSecretResolution`

Canonical secret-bearing internal object:

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

Raw `value`:

```text
repr = redacted
str = redacted
```

`managed_secret_version_id` is internal-only.

This object is never exposed to Admin serialization.

---

# 49. GENERIC SETTINGS MAPPING BOUNDARY

Managed raw secret MUST NOT be inserted into:

```text
ordinary Settings persisted overrides
ordinary SettingReadModel
Admin configured projection
generic audit projection
```

Current deployment/environment secret may continue to exist in legacy startup `base_settings` as today.

Stage 4 does not widen that exposure.

Managed secret is resolved through the dedicated secret resolver and passed only into Controller runtime composition.

---

# 50. S4-12 — STARTUP FAILURE BEHAVIOR

If configured generation G contains managed secret binding, these are fail-closed startup conditions:

```text
master key missing
master key wrong type/size
master key symlink
master key permission/ownership invalid
secret version row missing
AES-GCM authentication failure
encrypted frame invalid
secret decoded value invalid
configured binding integrity failure
```

Then:

```text
shared OmadaProvider is NOT constructed

Controller-dependent workers are NOT started

HTTP serving is NOT started

effective_generation does NOT advance
```

No fallback to environment.

---

# 51. SAFE ACTIVATION FAILURE CODES

If G is known and failure can be durably reported:

```text
controller_secret_key_unavailable

controller_secret_permissions_invalid

controller_secret_reference_missing

controller_secret_decrypt_failed

controller_secret_integrity_failed

controller_secret_configuration_invalid
```

No error code contains secret material.

Existing A2 rule remains:

```text
activation_failed requires positive durable in-process attestation
```

Process disappearance / systemd failure / timeout alone does NOT fabricate `activation_failed`.

---

# 52. NO-MANAGED-SECRET KEY FAILURE

If configured generation has NO managed secret binding:

```text
master key unavailable
```

does NOT prevent runtime from using valid:

```text
environment
or repository default
```

secret.

Result:

```text
Portal/Omada runtime may start normally

secret management state = unavailable

secret mutation endpoint = 503
```

This avoids making Stage-4 key provisioning a new mandatory dependency before first managed replacement.

---

# 53. WRONG MANAGED SECRET AFTER ADOPTION

If secret decrypts/local-validates and generation G is adopted, but later Omada OAuth rejects it:

```text
effective_generation remains G
```

This is an operational Controller authentication failure.

No automatic:

```text
Settings rollback
environment fallback
secret fallback
generation rollback
```

---

# 54. SECRET VERSION GC DURING MUTATION

After creating a new configured head, the same write transaction calculates retained secret version IDs:

```text
secret version referenced by configured head
+
secret version referenced by current effective generation
```

All other encrypted secret versions are deleted.

Therefore pending-but-superseded secret material is destroyed immediately and atomically with the new mutation.

---

# 55. SECRET VERSION GC DURING ADOPTION

When `SettingsActivationService` durably adopts generation G:

same SQLite transaction also recomputes retained secret versions:

```text
configured head binding
+
new effective generation binding
```

Any previously effective but now unreferenced encrypted secret version is deleted before transaction commit.

Thus:

```text
activation commit
+
old-secret destruction
```

are atomic in SettingsStore.

---

# 56. S4-13 — NORMAL RECOVERY

If operator entered a bad secret but Admin runtime is available:

Option 1:

```text
Replace secret
→ known-good new secret
→ new generation
→ external restart
```

Option 2:

```text
Clear managed secret override
→ deployment/environment fallback
→ new generation
→ external restart
```

No old-secret read-back.

No automatic rollback.

---

# 57. EMERGENCY RECOVERY WHEN SERVICE CANNOT START

Stage 4 defines one local break-glass operation:

```text
clear OMADA_CLIENT_SECRET managed binding
without reading/decrypting the secret
```

Canonical recovery command identity:

```text
python3 -m app.settings_control.secret_recovery \
  clear-omada-client-secret \
  --expected-generation <N>
```

This command:

```text
MUST be executed only by an authorized local operator
with captive-portal.service stopped

performs NO systemd action itself

requires exact CAS against current configured generation

copies all ordinary overrides

creates a new normal Settings generation

removes managed secret binding

writes secret-safe recovery audit

does NOT read/decrypt old secret

does NOT test Controller

does NOT modify deployment environment
```

Next normal startup resolves deployment/environment fallback and validates it.

If fallback is invalid, startup still fails honestly.

---

# 58. NO PREVIOUS-SECRET ROLLBACK

Emergency recovery does NOT offer:

```text
rollback to historical managed secret
```

because historical encrypted secret material is not retained after it leaves configured/effective ownership.

Recovery means:

```text
replace
or
clear to deployment fallback
or
restore coherent backup
```

---

# 59. S4-15 — STRICT SECRET-TAINT BOUNDARY

Raw secret MUST NOT be passed to:

```text
logger arguments
structured logs
telemetry
metrics labels
trace metadata
audit
exception text
Flask error JSON
HTML rendering
JS bootstrap JSON
Controller read model
debug repr
dataclass repr
generic settings projection
idempotency response
```

Secret-bearing classes require redacted `repr`/`str`.

No exception may format a secret-bearing object.

Crypto failures are converted to bounded safe error codes.

---

# 60. REQUEST LOGGING

Secret mutation request body MUST NOT be logged.

Access log may contain only:

```text
HTTP method
path
status
response size
```

Never:

```text
request body
secret
query representation
headers containing secret
```

Secret is body-only.

It must never appear in URL/query string.

---

# 61. S4-16 — PROCESS MEMORY

Raw secret may exist in memory only in these boundaries:

```text
HTTP request parser during secret replacement

ControllerSecretMutationService
during validation/encryption/comparison

ControllerSecretRepository decrypt result
during startup resolution

OmadaClientSecretResolution

OmadaControllerRuntimeConfig

shared OmadaProvider
```

Background workers receive:

```text
provider abstraction
```

not raw secret.

Public snapshots never contain raw secret.

Stage 4 does NOT promise secure memory erasure in Python.

Instead:

```text
minimize copies
minimize lifetime
drop references promptly
never serialize/log
```

---

# 62. S4-18 — CONTROLLER UI

Existing page remains:

```text
/admin/settings/controller
```

Client Secret row shows only safe state.

Example:

```text
Client Secret

Configured:
Configured

Configured source:
Managed secret override

Effective:
Configured

Effective source:
Environment

Status:
Pending restart
```

No current secret textbox.

No masked current secret.

No prefix/suffix.

No value length.

---

# 63. REPLACE SECRET UX

User with:

```text
admin.read.settings.controller
+
admin.write.settings.controller.secret
```

sees:

```text
[Replace secret]
```

Click opens dedicated modal.

Modal has TWO fields:

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

Paste:

```text
ALLOWED
```

There is NO reveal-current-secret function.

There is NO prefill.

There is NO server-provided masked value.

---

# 64. SECRET CONFIRMATION UX

Before POST, UI requires explicit confirmation:

```text
Replace Client Secret?
```

Confirmation text communicates:

```text
the value cannot be read back later

Save does not test Controller credentials

the running Controller connection remains unchanged

external captive-portal.service restart is required
to make the new secret effective
```

Confirmation screen/dialog MUST NOT display the typed secret.

---

# 65. CLEAR OVERRIDE UX

When:

```text
persisted_secret_override_present = true
```

and principal has secret capability:

```text
[Use deployment secret]
```

may be shown.

Confirmation states:

```text
Managed Client Secret will be removed.

After the required external service restart,
the deployment/environment secret will be used.

No current secret will be displayed.
```

No generic label `Reset` without this explanation.

---

# 66. UI AFTER SUCCESS

Changed replace success:

```text
Client Secret saved.

The running process still uses the current effective secret.

Credentials were not tested against Omada.

An externally performed captive-portal.service restart is required.
```

UI then:

```text
clears both secret input fields
drops secret JS references
closes replacement modal
GETs /admin/api/v1/settings/controller
renders Controller v3 state
```

No restart button.

---

# 67. UI ON ERROR / STALE WRITE

On ANY completed POST attempt:

```text
success
validation failure
403
409
412
413
500
503
network error
```

the two input fields are cleared in `finally`.

For:

```text
412 stale_generation
```

UI:

```text
re-GET current Controller model
display conflict message
require operator to re-enter secret
use a new Idempotency-Key
```

No automatic resubmission with retained raw secret.

---

# 68. IDEMPOTENCY AFTER UNCERTAIN NETWORK RESULT

The browser may retain only the generated:

```text
Idempotency-Key
```

in ephemeral page memory for one retry workflow.

It MUST NOT retain the secret.

If network outcome is uncertain:

```text
secret fields are cleared
operator re-enters secret
same in-memory Idempotency-Key may be reused
```

Server HMAC comparison then safely determines:

```text
same request → replay
different secret → 409
```

No localStorage/sessionStorage is used.

---

# 69. S4-19 — BROWSER SAFETY

Raw secret MUST NOT be retained in:

```text
URL
query string
localStorage
sessionStorage
cookies
HTML bootstrap JSON
data-* attributes
browser logs
client telemetry
generic JS model
history state
```

Typed secret may exist only transiently in the two password inputs and local submit call stack.

After submit/cancel:

```text
input.value = ""
modal state cleared
references released
```

No claim of guaranteed memory erasure in browser JS.

---

# 70. CANCEL SEMANTICS

Cancel performs:

```text
no request
no mutation
no generation
no audit
no idempotency row
```

Both password fields are immediately cleared.

---

# 71. READ-ONLY USER BEHAVIOR

Principal with:

```text
admin.read.settings.controller
```

but without:

```text
admin.write.settings.controller.secret
```

sees safe Client Secret status only.

No:

```text
Replace secret
Use deployment secret
```

controls.

Direct POST still independently enforces capability.

---

# 72. S4-20 — ORDINARY SETTINGSSTORE RELATIONSHIP

Ordinary SettingsStore is allowed to know only safe secret metadata:

```text
whether generation has managed secret binding

opaque secret_version_id

configured generation linkage

effective generation linkage

source/presence metadata derivable from binding

encrypted ciphertext in dedicated secret table
```

Ordinary `settings_overrides` MUST NOT contain:

```text
OMADA_CLIENT_SECRET
raw secret
encrypted secret blob
secret ref disguised as normal string setting
```

`SettingsDefinitionRegistry` remains:

```text
15 ordinary definitions
```

Stage 4 does NOT add `OMADA_CLIENT_SECRET` as a normal SettingsDefinition.

---

# 73. DEDICATED SECRET DEFINITION BOUNDARY

Stage 4 introduces one code-owned narrow definition:

```text
ControllerSecretDefinitionV1
```

with exactly:

```text
key = OMADA_CLIENT_SECRET
scope = global
secret_class = write_only_secret
apply_requirement = main_service_restart
activation_target = captive-portal.service
```

It is not iterable as a normal SettingsDefinition.

Generic:

```text
SettingsMutationService
```

continues to reject `OMADA_CLIENT_SECRET`.

Secret mutation is handled only by:

```text
ControllerSecretMutationService
```

which reuses the same:

```text
SettingsRepository
generation head
CAS
activation target
idempotency persistence
```

This is a narrow secret path, not a second generic Settings system.

---

# 74. S4-21 — SETTINGSSTORE SCHEMA V3

Stage 4 advances:

```text
PRAGMA user_version
2
→
3
```

Schema v3 adds:

```text
controller_secret_versions

settings_secret_bindings

settings_secret_mutation_audit
```

and evolves:

```text
settings_idempotency
```

to generic request-fingerprint semantics plus:

```text
mutation_domain = controller_secret
```

No existing generation IDs are changed.

No activation history is rewritten.

No existing General/Controller audit semantics change.

---

# 75. V2 → V3 MIGRATION

Migration is:

```text
single SQLite transaction
explicit
version checked
history preserving
fail closed on integrity failure
```

Migration MUST preserve:

```text
generation 0
all generations
parent links
ordinary overrides
target effective_generation
activation events
General mutation audit
Controller non-secret mutation audit
all successful idempotency rows
```

Migration creates:

```text
NO fake Settings generation
NO secret binding
NO secret version
NO activation event
NO mutation audit
```

Current deployment secret remains deployment-controlled after migration.

---

# 76. SETTINGS IDENTITY MIGRATION

Existing idempotency rows migrate:

```text
mutation_domain general/controller
unchanged

request_payload_hash
→ request_fingerprint

request_fingerprint_kind =
sha256_canonical_json_v1
```

Existing result response bodies remain byte-semantically unchanged after canonical DB migration.

Secret domain later uses:

```text
hmac_sha256_controller_secret_v1
```

---

# 77. BACKWARD COMPATIBILITY / DOWNGRADE

Stage-3 code does NOT understand schema v3.

Therefore:

```text
in-place code downgrade
while keeping v3 Settings DB
= NOT SUPPORTED
```

Production Stage-4 activation requires pre-migration backup of the v2 Settings DB.

Rollback to Stage-3 code requires:

```text
restore pre-Stage4 v2 Settings DB backup
+
ensure valid deployment/environment OMADA_CLIENT_SECRET
```

No automatic v3→v2 downgrade.

---

# 78. S4-22 — DEPLOYMENT SECRET INTERACTION

Transition is exact:

```text
before first managed replacement
→ environment/repository secret

after managed replacement
→ managed_secret_override takes precedence

after clear_secret_override
→ environment/repository secret again
```

Environment secret is NOT deleted or modified by Admin.

Admin has no environment editor.

Admin does not write systemd files.

This preserves an explicit deployment fallback path.

---

# 79. S4-23 — BACKUP CONTRACT

A recoverable Stage-4 managed-secret backup requires BOTH:

```text
consistent Settings DB backup
+
matching 32-byte master key backup
```

Settings DB backup alone:

```text
does NOT constitute recoverable managed-secret backup
```

Master key alone:

```text
contains no managed secret
```

Production backup of SQLite must be:

```text
SQLite online backup API
OR
service-stopped coherent copy
```

not an unsafe raw copy that ignores active SQLite transaction state.

---

# 80. MASTER-KEY BACKUP

Master key backup:

```text
must preserve exact 32 bytes

must be stored separately from Git/repository

must have protection equal to or stronger than production key

must never be pasted into chat/ticket/log

must never be exposed through Admin UI
```

Runtime never exports the key.

---

# 81. RESTORE

Stage-4 restore procedure:

```text
1. restore coherent settings.sqlite3

2. restore matching master key
   with exact owner/mode/path

3. validate DB schema/integrity

4. validate key file structural security

5. if configured head references managed secret:
   decrypt/authenticate that exact secret version

6. only then continue Controller runtime composition
```

Wrong/missing key:

```text
fail closed
```

No fallback to environment if configured head explicitly references managed secret.

---

# 82. KEY ROTATION

Master-key rotation is:

```text
OUT OF STAGE 4 V1
```

No Admin key-rotation control.

No automatic key regeneration.

Future rotation requires a separate architecture because all retained configured/effective ciphertext would need authenticated re-encryption.

---

# 83. FILE / HOST SECURITY FOR SETTINGS DB

Once schema v3 may contain encrypted secrets, production preflight requires Settings DB to be:

```text
regular file
not symlink
owner = admin
group = admin
mode = 0600
```

Its parent directory must not be writable by untrusted users.

Stage 4 does not rely only on encryption.

Ciphertext at rest + filesystem permissions are both required.

---

# 84. SECRET STORE AVAILABILITY

`secret_store_state=available` requires at least:

```text
SettingsStore schema/integrity usable

master-key file structurally valid

master-key permission checks PASS
```

Mutation additionally requires successful crypto initialization.

If these cannot be trusted:

```text
secret_store_state = unavailable
```

No optimistic state.

---

# 85. NO READ-TIME SECRET DECRYPT FOR UI

Controller GET does NOT decrypt the managed secret merely to render status.

Configured secret status is derived from safe:

```text
generation binding presence
source
store state
```

Effective state comes from immutable runtime public snapshot.

Raw decrypt happens only when needed for:

```text
startup runtime composition
secret replacement comparison/encryption path
```

Never for ordinary GET.

---

# 86. PUBLIC EFFECTIVE SNAPSHOT

`OmadaControllerPublicConfigSnapshot` remains raw-secret-free.

For Client Secret it contains only effective safe facts equivalent to:

```text
client_secret_presence
client_secret_source
effective_generation
```

It MUST NOT gain:

```text
client_secret
secret_version_id
ciphertext
hash
length
```

`managed_secret_override` becomes an admitted `client_secret_source`.

---

# 87. S4-25 — NO SECRET READ API

Permanent:

```text
NO endpoint returns current secret
NO endpoint returns previous secret
NO capability grants secret read-back
NO debug endpoint returns secret
NO export endpoint returns secret
NO history endpoint returns secret
NO recovery endpoint returns secret
```

Recovery means:

```text
replace
clear override
restore backup
```

not read-back.

---

# 88. NO SECRET FINGERPRINT UI

Forbidden in public/read model:

```text
hash
HMAC
fingerprint
last 4 chars
first chars
length
masked string whose length reflects secret
opaque secret_version_id
```

The only state is semantic presence/source/pending metadata.

---

# 89. SECRET-SAFE TELEMETRY

Allowed telemetry:

```text
operation category
success/failure category
configured generation
activation state
request_id
principal type/name where existing Admin telemetry permits it
```

Forbidden:

```text
request body
raw secret
ciphertext
nonce
secret version ID
secret HMAC
secret length
```

---

# 90. NORMAL NON-SECRET CONTROLLER MUTATION

Existing endpoint remains:

```text
POST /admin/api/v1/settings/controller/generations
```

It continues to accept exactly:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

It MUST still reject:

```text
OMADA_CLIENT_SECRET
VERIFY_SSL
```

Secret is never smuggled through the normal Controller mutation route.

---

# 91. COMMON GENERATION ETag

Secret GET/mutation uses the same global head:

```text
ETag =
"settings-gN"
```

A General/non-secret Controller mutation may stale an open secret modal.

A secret mutation may stale an open General/non-secret Settings editor.

This is intentional because there is one global configured generation chain.

---

# 92. APPLY REQUIREMENT

For:

```text
OMADA_CLIENT_SECRET
```

exactly:

```text
apply_requirement =
main_service_restart

activation_target =
captive-portal.service
```

No hot apply in Stage 4.

---

# 93. NO CONTROLLER I/O BEFORE ADOPTION

The accepted Stage-3 invariant remains:

```text
candidate generation G
MUST NOT be used for Controller/OAuth external I/O
before durable adoption G
```

Secret decrypt / local provider construction is allowed before adoption.

Network/OAuth access is not.

---

# 94. SECRET STORE FAILURE AFTER SAVE BEFORE RESTART

If secret replacement committed successfully and then key/store becomes unavailable before restart:

```text
configured generation remains G
effective generation remains H

pending replacement remains configured
```

Next restart fails closed before Controller I/O.

No mutation is silently rolled back.

---

# 95. SECRET STORE FAILURE DURING MUTATION

If key/crypto/store unavailable before successful transaction commit:

```text
no generation
no secret version
no binding
no audit
no idempotency success receipt
```

Return:

```text
503 controller_secret_store_unavailable
```

If internal transaction failure occurs after BEGIN but before commit:

```text
rollback entire SQLite transaction
```

---

# 96. IDEMPOTENCY RESPONSE SIZE

Secret mutation receipt remains bounded and must satisfy existing durable idempotency response limit:

```text
<= 65536 bytes UTF-8 serialized
```

It contains no value-sized secret-dependent fields, so secret length cannot make the response exceed this bound.

If receipt persistence unexpectedly fails:

```text
entire mutation transaction rolls back
```

No committed generation without durable replay result.

---

# 97. SECRET-SAFE REQUEST PARSER

Secret route MUST NOT reuse any generic helper that:

```text
logs raw body
persists SHA-256(raw payload)
includes request body in exception
copies secret into generic change list telemetry
```

It may reuse:

```text
session authentication
CSRF validation
ETag parser
CAS/generation repository
bounded idempotency response persistence
```

but secret-tainted parsing/fingerprinting stays in the dedicated service boundary.

---

# 98. EXACT SECRET MUTATION TRANSACTION ORDER

For `replace_secret`:

```text
1. validate auth/capability/CSRF/headers/body bounds

2. parse strict JSON

3. normalize/validate secret in memory

4. load/validate master key

5. derive idempotency HMAC key

6. compute secret-safe request HMAC

7. lookup existing idempotency
   → replay/conflict if present

8. BEGIN IMMEDIATE SettingsStore transaction

9. re-check idempotency

10. CAS If-Match vs global head

11. read parent secret binding

12. compare against currently configured retained secret if needed

13. determine no-op / reusable retained version / new version

14. if new:
    encrypt fixed-size frame
    insert controller_secret_versions row

15. create normal Settings generation if changed

16. copy ordinary override snapshot

17. set new settings_secret_bindings row

18. append secret-safe audit

19. calculate configured/effective retained secret IDs

20. delete unreferenced encrypted versions

21. persist bounded idempotency receipt

22. COMMIT
```

No Controller I/O anywhere in this transaction.

---

# 99. EXACT CLEAR TRANSACTION ORDER

For `clear_secret_override`:

```text
1. normal auth/CSRF/header/body/idempotency validation

2. BEGIN IMMEDIATE

3. re-check idempotency

4. CAS global head

5. if no managed binding:
   semantic no-op

6. if managed binding:
   resolve lower-precedence deployment secret
   from current startup base snapshot

7. local validation of resulting complete Controller configuration

8. create new generation

9. copy ordinary overrides

10. create NO secret binding for new generation

11. append secret-safe audit

12. GC unreferenced encrypted secret versions
    while retaining current effective version if needed

13. persist idempotency receipt

14. COMMIT
```

No environment file is modified.

---

# 100. SETTINGS ACTIVATION TRANSACTION EXTENSION

On successful durable adoption G:

```text
append activation_result=adopted

update settings_target_state.effective_generation=G

compute secret versions referenced by:
configured head + new effective generation

delete all other controller_secret_versions

COMMIT
```

This ensures old effective secret material is destroyed atomically with successful generation adoption.

On failed adoption:

```text
effective generation does not advance
```

Current effective secret version therefore remains retained.

---

# 101. SCHEMA / INTEGRITY VALIDATION

SettingsStore schema v3 validation must verify:

```text
exact tables/columns/checks/triggers
generation root integrity
ordinary override integrity
secret-binding key exactness
UUID syntax for secret_version_id
nonce length
ciphertext fixed length
allowed crypto_schema_version
idempotency domain/fingerprint kinds
foreign keys for ordinary Settings history
```

Historical binding pointing to destroyed secret material is allowed.

But secret material referenced by current:

```text
configured head
or effective generation
```

must exist whenever managed source is required.

---

# 102. CORRUPTION BEHAVIOR

If schema/integrity corruption prevents trustworthy SettingsStore use:

```text
existing Stage-3 Settings fail-closed startup semantics remain
```

No auto recreation.

No deleting corrupt DB and starting fresh.

No secret fallback guess.

---

# 103. OPERATOR RECOVERY AUDIT

Break-glass clear operation creates normal generation and audit:

```text
operation =
clear_secret_override_recovery

principal_type =
local_operator

principal_name =
current OS operator identity

source_ip =
local
```

No idempotency HMAC is required for local one-shot recovery.

`--expected-generation` provides CAS.

The command does not read the old secret.

---

# 104. BACKUP CONSISTENCY AFTER SECRET REPLACEMENT

Because secret ciphertext and generation metadata are in one SQLite file:

```text
SQLite-consistent backup
```

automatically captures a coherent:

```text
generation
+
binding
+
ciphertext
+
audit
+
idempotency state
```

The external master key is static and must be backed up as its matching pair.

No second mutable secret DB needs cross-database transaction coordination.

---

# 105. PUBLIC `management_mode`

Controller top-level remains conceptually:

```text
management_mode = hybrid
```

because:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
= ordinary writable Settings

OMADA_CLIENT_SECRET
= write-only managed secret

VERIFY_SSL
= deployment/code controlled
```

Client-secret field itself declares:

```text
management_mode = write_only
```

---

# 106. STORE/MUTATION AVAILABILITY ON CONTROLLER READ

Controller v3 top-level should expose separately:

```text
mutation_available
```

for ordinary Controller settings and:

```text
secret_mutation_available
```

for Client Secret.

A missing/invalid master key may make:

```text
ordinary Controller mutation = available
secret mutation = unavailable
```

These states are intentionally independent.

---

# 107. UI CAPABILITY MATRIX

```text
read Controller only
→ sees Controller values + safe secret status
→ no edit controls

admin.write.settings.controller
→ may edit URL / Controller ID / Client ID
→ cannot replace secret

admin.write.settings.controller.secret
+ read capability
→ may Replace secret / Use deployment secret

both write capabilities
→ may use both independent mutation surfaces
```

No capability grants raw secret read.

---

# 108. TESTABLE ARCHITECTURE INVARIANTS

```text
S4-I01
OMADA_CLIENT_SECRET never becomes ordinary SettingsDefinition.

S4-I02
settings_overrides never contains OMADA_CLIENT_SECRET.

S4-I03
Managed secret ciphertext uses AES-256-GCM.

S4-I04
Master key is external to settings.sqlite3.

S4-I05
Master key is exactly 32 raw bytes.

S4-I06
Ciphertext length is fixed and does not reveal secret length.

S4-I07
Settings DB alone cannot verify guessed secrets through a plain secret hash.

S4-I08
Secret request idempotency uses keyed HMAC.

S4-I09
Idempotency HMAC includes Idempotency-Key.

S4-I10
Audit contains no secret/hash/HMAC/version ID/length.

S4-I11
Public API contains no raw secret.

S4-I12
Public API contains no secret fingerprint/prefix/suffix/length.

S4-I13
Secret replacement creates a normal global Settings generation.

S4-I14
Generation→secret linkage is opaque reference only.

S4-I15
General and non-secret Controller mutations carry forward secret binding.

S4-I16
Clear override returns ownership to deployment/environment secret.

S4-I17
Clear fails if resulting fallback configuration is locally invalid.

S4-I18
Migration does not import environment secret.

S4-I19
Migration creates no generation or activation event.

S4-I20
Replace operation performs no Controller/OAuth I/O.

S4-I21
Secret activation requires external main-service restart.

S4-I22
No provider-capable Controller I/O occurs before durable adoption.

S4-I23
Wrong but syntactically valid secret may adopt locally and fail operationally later.

S4-I24
Operational OAuth failure does not rewrite Settings activation history.

S4-I25
Managed-secret decrypt/reference failure fails startup closed.

S4-I26
Managed-secret failure never silently falls back to environment.

S4-I27
Missing master key does not block startup when no managed secret is configured.

S4-I28
Secret mutation has a distinct capability.

S4-I29
Non-secret Controller write capability does not grant secret write.

S4-I30
Existing secret is never prefilled.

S4-I31
UI has no secret reveal/read-back path.

S4-I32
Browser stores secret in no persistent client storage.

S4-I33
Secret inputs are cleared after every completed submit attempt and cancel.

S4-I34
Mutation success receipt never contains secret-dependent scalar data.

S4-I35
UI re-GETs Controller v3 after successful mutation/replay.

S4-I36
Secret version rows are retained only for current configured/effective ownership.

S4-I37
No secret history rollback exists without re-entering a known secret.

S4-I38
Old effective encrypted material is deleted atomically on successful adoption.

S4-I39
Superseded pending encrypted material is deleted atomically on later mutation.

S4-I40
Controller GET does not decrypt secret merely for presentation.

S4-I41
Master-key rotation is outside Stage 4 V1.

S4-I42
Settings schema becomes v3.

S4-I43
Stage-3 code cannot silently run against v3 DB.

S4-I44
Stage-3 rollback requires pre-migration v2 DB restore.

S4-I45
Recoverable backup requires Settings DB + matching master key.

S4-I46
No secret export endpoint exists.

S4-I47
No generic secret vault UI exists.

S4-I48
No Admin systemd authority is added.

S4-I49
No restart button is added.

S4-I50
No live Test Connection is added.
```

---

# 109. REQUIRED TEST MATRIX FOR FUTURE IMPLEMENTATION TASK

Future Technical Developer implementation TASK must include tests for at least:

## Crypto / storage

```text
fixed ciphertext length
nonce uniqueness
correct decrypt
wrong key failure
tampered ciphertext failure
tampered nonce failure
AAD/version mismatch failure
secret length not externally derivable from ciphertext size
```

## Permissions

```text
key symlink rejected
wrong key size rejected
wrong mode rejected
wrong owner/group rejected
non-regular key rejected
```

## Generation / atomicity

```text
replace commit atomic
clear commit atomic
crash before commit
crash after commit
general mutation carries binding
controller mutation carries binding
effective/configured secret refs diverge safely
activation GC
superseded pending GC
```

## Idempotency

```text
same key + same secret → replay
same key + different secret → 409
same secret + different keys → unrelated fingerprints
no raw secret in DB idempotency
no raw secret in response
```

## Public model

```text
configured/effective source
pending replacement
store outage
key outage
no secret/version/hash/length exposure
Controller v3 schema
```

## UI

```text
read-only user
non-secret writer
secret writer
two-entry match
paste allowed
no prefill
cancel clears
success clears
error clears
412 clears + reload
no localStorage/sessionStorage/cookie/query-string use
```

## Startup

```text
environment-only secret without master key
managed secret with valid key
managed secret + key missing
managed secret + wrong key
missing secret row
decrypt/tag failure
no Controller I/O before adoption
```

## Recovery / backup

```text
clear to valid deployment fallback
clear to invalid fallback rejected
break-glass clear generation/CAS/audit
restore matching DB+key
restore DB with wrong key fails closed
v3→Stage3 direct downgrade rejected
```

## Secret-taint sentinels

Raw test secret MUST be absent from:

```text
logs
telemetry
audit
idempotency response
Controller GET
HTML
JS fixture output
exceptions
tracebacks
repr/str
metrics labels
```

---

# 110. EXPLICIT OUT OF SCOPE

Stage 4 does NOT authorize:

```text
VERIFY_SSL mutation

secret read-back
secret reveal
secret export
secret history UI
secret rollback selector

master-key rotation
generic secret vault
arbitrary secrets other than OMADA_CLIENT_SECRET

Admin systemd control
restart button
hot reload
hot reconnect
hot provider recreation

Controller Test Connection
live credential verification
token reset
OAuth client management
Omada-side mutation

Site-scoped Controller settings
multi-controller

environment editor
systemd environment editor

Stage 5 Portal settings
```

---

# 111. OPEN ARCHITECTURE QUESTIONS

```text
OPEN_P0 = 0
OPEN_P1 = 0
```

Architecturally closed:

```text
S4-01 secret owner
= CLOSED

S4-02 at-rest protection
= CLOSED

S4-03 identity/reference
= CLOSED

S4-04 precedence
= CLOSED

S4-05 write-only API
= CLOSED

S4-06 idempotency
= CLOSED

S4-07 validation
= CLOSED

S4-08 public configured/effective/pending model
= CLOSED

S4-09 generation/atomicity
= CLOSED

S4-10 activation
= CLOSED

S4-11 startup resolution
= CLOSED

S4-12 failure semantics
= CLOSED

S4-13 recovery
= CLOSED

S4-14 audit
= CLOSED

S4-15 logging/telemetry/errors
= CLOSED

S4-16 process memory
= CLOSED

S4-17 authorization
= CLOSED

S4-18 UI/UX
= CLOSED

S4-19 browser safety
= CLOSED

S4-20 SettingsStore relationship
= CLOSED

S4-21 schema/migration
= CLOSED

S4-22 deployment interaction
= CLOSED

S4-23 backup/restore
= CLOSED

S4-24 file/host security
= CLOSED

S4-25 no secret read API
= CLOSED

S4-26 out of scope
= CLOSED
```

---

# 112. FINAL DISPOSITION

```text
TASK =
CAPTIVPORTAL ADMIN SETTINGS
STAGE 4
OMADA CONTROLLER SECRET MANAGEMENT

ARCHITECTURE =
DRAFT FOR TECH LEAD REVIEW

BASELINE =
main@78296b2e9a35664c0d285cf0c7d22b2fa465311a

TREE =
f965d4604652db52d5f97b1f5d3abe36263ee78b

SECRET STORAGE =
AES-256-GCM encrypted dedicated tables
inside existing SettingsStore SQLite

MASTER KEY =
external host-local 32-byte key
/etc/captiveportal/omada-controller-secret-master.key

RAW SECRET IN settings_overrides =
FORBIDDEN

RAW SECRET READ-BACK =
FORBIDDEN

PRECEDENCE =
managed_secret_override
>
environment
>
repository_default

WRITE API =
POST /admin/api/v1/settings/controller/client-secret/generations

WRITE CAPABILITY =
admin.write.settings.controller.secret

LIVE CREDENTIAL TEST =
NO

ACTIVATION =
main_service_restart

HOT RECONNECT =
NO

ADMIN SYSTEMD AUTHORITY =
NO

CLEAR OVERRIDE =
YES
→ return to deployment/environment secret

PREVIOUS MANAGED SECRET ROLLBACK =
NO

SETTINGSSTORE SCHEMA =
v2 → v3

CONTROLLER READ MODEL =
admin.settings.controller.v3

BACKUP =
Settings DB + matching master key

OPEN_P0 =
0

OPEN_P1 =
0

READY FOR TECH LEAD REVIEW =
YES

IMPLEMENTATION TASK =
HOLD

CODER =
HOLD

PRODUCTION CHANGE =
NO
```

Следующий разрешённый governance step:

```text
Tech Lead
→ Stage-4 architecture review
→ PASS или bounded architecture return

если PASS:
Technical Developer Settings
→ exact Stage-4 implementation TASK
→ Tech Lead implementation-contract review
→ only then possible Coder authorization
```
