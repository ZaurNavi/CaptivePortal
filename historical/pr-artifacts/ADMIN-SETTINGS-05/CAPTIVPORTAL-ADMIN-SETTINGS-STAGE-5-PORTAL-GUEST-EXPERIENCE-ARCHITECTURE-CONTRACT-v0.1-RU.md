# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS
### ARCHITECTURE CONTRACT v0.1
### DRAFT FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Область:** Admin UI → Settings → Portal → Guest Portal  
**Роль:** Architect  
**Baseline:** `main@c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9`  
**TREE:** `59df8aa855fe094e173db611fbbdf5714c229b86`  
**Статус:** `DRAFT FOR TECH LEAD REVIEW`  
**Implementation authorization:** `NO`  
**Coder:** `HOLD`  
**Production change:** `NO`

---

# 0. ЦЕЛЬ

Stage 5 вводит первый явно разрешённый writable-домен гостевого Portal UI поверх уже существующего Settings control plane.

Stage 5 НЕ превращает Settings в редактор `app/config.py`, process environment или произвольных portal-параметров.

Нормативная модель:

```text
explicit allowlist
→ existing SettingsStore
→ common immutable generation
→ atomic validation
→ audit
→ CAS / If-Match
→ idempotency
→ pending_main_restart
→ captive-portal.service restart outside Admin
→ exact startup composition
→ durable generation adoption
→ effective value
```

Stage 5 допускает только безопасное, публично отображаемое содержимое Guest Portal:

```text
branding text
welcome text
short guest description
bounded public support contacts
bounded public social links
```

Stage 5 НЕ меняет:

```text
Authorization semantics
CAPPORT protocol/network contract
Omada authorization
redirect contract
session duration
retry algorithm
cookies
CSRF
trusted proxy
network identity
Site scoping
public counter data semantics
operational workers
systemd
```

---

# 1. BASELINE / CURRENT-STATE FINDINGS

Baseline repository содержит:

```text
app/web/localization.py
```

с code-owned `PORTAL_TRANSLATIONS` для:

```text
az
ru
en
```

Текущие guest-facing branding fields:

```text
title
greeting
description
```

Текущий `portal.html` содержит hard-coded public support contacts:

```text
phone
email
WhatsApp URL
Telegram URL
Facebook URL
```

Ordinary Omada External Portal и CAPPORT login используют общий Portal rendering path и один `portal.html`.

Current Settings control plane уже поддерживает:

```text
GLOBAL generation chain
integer values
string values
common ETag
If-Match
idempotency
audit
restart-based adoption
domain-aware definitions
independently assigned global Admin capabilities
```

Current SettingsStore schema:

```text
v3
```

Current ordinary string-setting implementation специализирован под Controller normalization; Stage 5 поэтому требует bounded generalization string validation, но НЕ отдельную Settings subsystem.

---

# 2. ОСНОВНОЕ АРХИТЕКТУРНОЕ РЕШЕНИЕ

Stage 5 создаёт новый Settings domain:

```text
portal
```

и использует:

```text
ONE existing SettingsDefinitionRegistry
ONE existing SettingsStore
ONE global generation chain
ONE effective generation
ONE common ETag
ONE activation target
```

Не создаются:

```text
Portal settings DB
Portal generation table
Portal-specific CAS chain
Portal-specific audit store
Portal-specific restart mechanism
```

Canonical configuration chain:

```text
repository default
+
explicit process environment
+
persisted Settings override
        ↓
ResolvedSettingsSnapshot(G)
        ↓
PortalPresentationConfigV1
        ↓
shared Flask Guest Portal composition
        ├─ ordinary Omada External Portal /
        └─ CAPPORT login bridge /capport/login
        ↓
portal.html safe rendering
```

Permanent precedence:

```text
persisted Settings override
>
explicit process environment
>
repository default
```

---

# 3. EXACT STAGE-5 ALLOWLIST

Stage 5 admits exactly **14** GLOBAL non-secret values.

No other Portal/CAPPORT/Auth setting becomes writable.

Canonical keys:

```text
PORTAL_UI_TITLE_AZ
PORTAL_UI_TITLE_RU
PORTAL_UI_TITLE_EN

PORTAL_UI_GREETING_AZ
PORTAL_UI_GREETING_RU
PORTAL_UI_GREETING_EN

PORTAL_UI_DESCRIPTION_AZ
PORTAL_UI_DESCRIPTION_RU
PORTAL_UI_DESCRIPTION_EN

PORTAL_SUPPORT_PHONE
PORTAL_SUPPORT_EMAIL
PORTAL_SUPPORT_WHATSAPP_URL
PORTAL_SUPPORT_TELEGRAM_URL
PORTAL_SUPPORT_FACEBOOK_URL
```

---

# 4. EXACT DEFAULT VALUES

Repository defaults MUST preserve current visible Guest Portal content.

```text
PORTAL_UI_TITLE_AZ =
Zəfər Parkı

PORTAL_UI_TITLE_RU =
Zəfər Parkı

PORTAL_UI_TITLE_EN =
Zəfər Parkı
```

```text
PORTAL_UI_GREETING_AZ =
Xoş gəlmisiniz!

PORTAL_UI_GREETING_RU =
Добро пожаловать!

PORTAL_UI_GREETING_EN =
Welcome!
```

```text
PORTAL_UI_DESCRIPTION_AZ =
Parkımızın qonaqları üçün pulsuz
Wi-Fi!!

PORTAL_UI_DESCRIPTION_RU =
Бесплатный Wi-Fi
для гостей парка!!

PORTAL_UI_DESCRIPTION_EN =
Free Wi-Fi
for park guests!!
```

Support defaults:

```text
PORTAL_SUPPORT_PHONE =
+994 50 417 46 46

PORTAL_SUPPORT_EMAIL =
zaur.navi@gmail.com

PORTAL_SUPPORT_WHATSAPP_URL =
https://wa.me/994504174646

PORTAL_SUPPORT_TELEGRAM_URL =
https://t.me/ZaurNavi

PORTAL_SUPPORT_FACEBOOK_URL =
https://www.facebook.com/zaur.navi/?locale=ru_RU
```

Repository defaults MUST have one canonical code-owned definition source shared by:

```text
app/config.py fallback
SettingsDefinitionRegistry metadata
PortalPresentationConfigV1 tests
```

Independent duplicate literals are forbidden.

---

# 5. DEFINITION MATRIX

All 14 definitions:

```text
scope_type =
global

scope_id =
null

secret_class =
normal

editable =
true

apply_requirement =
main_service_restart

activation_target =
captive-portal.service

domain =
portal
```

## 5.1 Branding title

Keys:

```text
PORTAL_UI_TITLE_AZ
PORTAL_UI_TITLE_RU
PORTAL_UI_TITLE_EN
```

Definition:

```text
operator-facing name =
Portal title — Azerbaijani / Russian / English

value_type =
string

presentation_type =
plain_text

minimum =
1 Unicode code point

maximum =
80 Unicode code points

required =
true

consumer =
PortalPresentationConfigV1
```

## 5.2 Greeting

Keys:

```text
PORTAL_UI_GREETING_AZ
PORTAL_UI_GREETING_RU
PORTAL_UI_GREETING_EN
```

Definition:

```text
operator-facing name =
Welcome text — Azerbaijani / Russian / English

value_type =
string

presentation_type =
plain_text

minimum =
1 Unicode code point

maximum =
120 Unicode code points

required =
true

consumer =
PortalPresentationConfigV1
```

## 5.3 Description

Keys:

```text
PORTAL_UI_DESCRIPTION_AZ
PORTAL_UI_DESCRIPTION_RU
PORTAL_UI_DESCRIPTION_EN
```

Definition:

```text
operator-facing name =
Guest description — Azerbaijani / Russian / English

value_type =
string

presentation_type =
multiline_plain_text

minimum =
1 Unicode code point

maximum =
400 Unicode code points

maximum lines =
4

required =
true

consumer =
PortalPresentationConfigV1
```

## 5.4 Phone

```text
key =
PORTAL_SUPPORT_PHONE

operator-facing name =
Support phone

value_type =
string

presentation_type =
telephone

minimum =
0

maximum =
32 Unicode code points

required =
false
```

Empty value means:

```text
phone link not rendered
```

## 5.5 Email

```text
key =
PORTAL_SUPPORT_EMAIL

operator-facing name =
Support email

value_type =
string

presentation_type =
email

minimum =
0

maximum =
254 ASCII characters

required =
false
```

Empty means:

```text
email link not rendered
```

## 5.6 WhatsApp

```text
key =
PORTAL_SUPPORT_WHATSAPP_URL

operator-facing name =
WhatsApp support link

value_type =
string

presentation_type =
restricted_url

minimum =
0

maximum =
256 characters

required =
false
```

Empty means:

```text
WhatsApp icon/link not rendered
```

## 5.7 Telegram

```text
key =
PORTAL_SUPPORT_TELEGRAM_URL

operator-facing name =
Telegram support link

value_type =
string

presentation_type =
restricted_url

minimum =
0

maximum =
256 characters

required =
false
```

## 5.8 Facebook

```text
key =
PORTAL_SUPPORT_FACEBOOK_URL

operator-facing name =
Facebook support link

value_type =
string

presentation_type =
restricted_url

minimum =
0

maximum =
512 characters

required =
false
```

---

# 6. TEXT VALIDATION CONTRACT

For:

```text
title
greeting
description
```

the persisted/configured value MUST already satisfy:

```text
Unicode NFC
```

No silent Unicode normalization during mutation.

If candidate is not NFC:

```text
422 validation_failed
reason = non_canonical_unicode
```

Forbidden in all operator text:

```text
NUL
C0 control characters
C1 control characters
Unicode bidi override controls
Unicode bidi isolate controls
```

For title/greeting additionally forbidden:

```text
LF
CR
TAB
```

For description:

```text
LF allowed
CR forbidden
TAB forbidden
maximum 4 logical lines
```

All required text values:

```text
must not be empty
must not consist only of Unicode whitespace
must not start or end with Unicode whitespace
```

HTML syntax is not interpreted.

Values such as:

```text
<b>Hello</b>
<script>...</script>
```

are ordinary text and MUST render literally escaped, never as markup.

---

# 7. XSS / RENDERING CONTRACT

Stage 5 permits:

```text
plain text only
```

Forbidden:

```text
arbitrary HTML
Markdown-to-HTML
JavaScript
CSS
SVG supplied by operator
template fragments
data URLs
HTML entity decoding as markup
```

Server rendering:

```text
Jinja autoescape remains enabled
```

Client-side localization update:

```text
textContent only
```

Forbidden for Stage-5 values:

```text
innerHTML
outerHTML
insertAdjacentHTML
document.write
eval
new Function
```

The safe public presentation object MAY be serialized with Jinja `tojson`.

It MUST NOT be concatenated into executable JavaScript source.

---

# 8. SUPPORT PHONE VALIDATION

`PORTAL_SUPPORT_PHONE` may be empty.

Non-empty value must satisfy all:

```text
starts with "+"
contains only ASCII digits and ASCII spaces after "+"
after removing ASCII spaces:
    E.164 digit count = 8..15
no leading/trailing whitespace
no CR/LF/TAB/control chars
```

Canonical href is generated server-side/application-side as:

```text
tel:+<digits only>
```

The stored/display value remains the validated operator string.

The browser MUST NOT construct `tel:` from arbitrary unvalidated content.

---

# 9. SUPPORT EMAIL VALIDATION

`PORTAL_SUPPORT_EMAIL` may be empty.

Non-empty value:

```text
ASCII only
1..254 characters
exactly one "@"
non-empty local part
non-empty domain part
no spaces
no control chars
no CR/LF
no ":" before address parsing
domain labels use ASCII letters/digits/hyphen/dot only
local part restricted to:
A-Z a-z 0-9 . _ % + -
```

No display-name syntax:

```text
"Name <address@example.com>" = forbidden
```

No query injection:

```text
?subject=
?body=
```

Canonical href:

```text
mailto:<validated address>
```

---

# 10. RESTRICTED SUPPORT URL VALIDATION

All admitted social URLs:

```text
https only
absolute URL
no username
no password
no fragment
no control characters
no Unicode host
canonical ASCII hostname
```

## WhatsApp

Allowed exact host:

```text
wa.me
```

Allowed path:

```text
/[0-9]{8,15}
```

Forbidden:

```text
query
fragment
extra path segment
```

## Telegram

Allowed exact host:

```text
t.me
```

Allowed path:

```text
/[A-Za-z0-9_]{5,64}
```

Forbidden:

```text
query
fragment
extra path segment
```

## Facebook

Allowed hosts:

```text
facebook.com
www.facebook.com
```

Path:

```text
non-empty
maximum 256 characters
```

Query:

```text
empty
OR exactly one "locale" parameter
```

`locale` value syntax:

```text
[A-Za-z]{2,3}_[A-Za-z]{2,3}
```

Forbidden:

```text
other query parameters
fragment
userinfo
non-HTTPS scheme
redirector host
```

External links MUST retain:

```html
target="_blank"
rel="noopener noreferrer"
```

Stage 5 does NOT admit arbitrary external URL configuration.

---

# 11. SUPPORT SECTION RENDERING

Support section behavior:

```text
phone empty
→ no phone row

email empty
→ no email row

WhatsApp URL empty
→ no WhatsApp link

Telegram URL empty
→ no Telegram link

Facebook URL empty
→ no Facebook link
```

If all five support fields are empty:

```text
entire support section is not rendered
```

`supportTitle` remains code-owned localization in Stage 5 V1.

No separate `PORTAL_SUPPORT_ENABLED` feature toggle is introduced.

---

# 12. CURRENT CODE-OWNED PORTAL CONTENT NOT ADMITTED

The following remains code-owned in Stage 5:

```text
connection-state labels
WAITING
AUTHORIZING
VERIFYING
RESETTING
DISCOVERING_CLIENT
AUTHORIZED
RESET
FAILED
EXPIRED

waitingNote
discoveryNote
authorizedNote
retryButton
retryableFailure
expiredNote
finalFailure
pollingError
retryCheckError

supportTitle

language names / language selector
default language
success-page status text
designer/footer credit
logo SVG
favicon SVG
theme colors
CSS
layout
animation
progress percentages
```

Reason:

```text
status/error strings participate in trusted auth-state communication;
visual theme/assets require a separate branding/content architecture;
language policy is a separate product decision.
```

They are:

```text
DEFER TO LATER STAGE
```

not silently writable.

---

# 13. EXISTING PORTAL-RELATED CONFIGURATION INVENTORY

## 13.1 ADMIT TO STAGE 5

Exactly the 14 keys defined above.

These are new canonical configuration definitions created from currently code-owned Guest Portal presentation content.

## 13.2 DEFER TO LATER STAGE

```text
PORTAL_COUNTER_ENABLED
PORTAL_COUNTER_API_ENABLED
PORTAL_COUNTER_TIMEZONE

PUBLIC_TRAFFIC_COUNTER_ENABLED
PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS

portal counter visibility
public traffic visibility
language enable/disable
default language
theme/colors/logo
success-page localized content
footer/designer credit
```

Reason:

```text
these values are coupled to public data products,
feature controls, presentation policy, or broader branding behavior.
```

Feature-enable controls remain a later Settings stage.

## 13.3 PERMANENTLY DEPLOYMENT-OWNED / NOT ADMIN-EDITABLE IN THIS ROADMAP

```text
HOST
PORT
DEBUG
VERIFY_SSL

PORTAL_COUNTER_DB_PATH
PUBLIC_TRAFFIC_DB_PATH

log paths
database paths
TLS/private-key paths
bind addresses
proxy topology
trusted-hop count
```

These are infrastructure/security/storage ownership, not Guest Experience.

## 13.4 REQUIRES SEPARATE ARCHITECTURE BEFORE ADMISSION

```text
Authorization session TTL
Authorization retry cooldown
AuthWorker attempt/delay policy
Omada authorization behavior
redirect destination behavior
guest cookies
session properties
CSRF
trusted proxy/network assumptions
pending-session cleanup behavior
SSID/data-scope controls
public traffic semantic scope
CAPPORT configuration
```

---

# 14. CAPPORT ADMISSION DECISION

Stage 5 V1 admits:

```text
ZERO CAPPORT CONFIGURATION KEYS
```

This is explicit.

The shared Guest Portal presentation config MAY be displayed when the visitor reaches the same `portal.html` through:

```text
/capport/login
```

That does NOT make the presentation settings CAPPORT protocol settings.

## 14.1 Guest UX / presentation behavior

Stage-5 presentation fields:

```text
ALLOWED
```

only because they belong to the shared page after identity resolution.

## 14.2 Portal protocol behavior

```text
CAPPORT_ENABLED
CAPPORT_CLIENT_CACHE_TTL_SECONDS
CAPPORT_FAILURE_CACHE_TTL_SECONDS
```

Status:

```text
NOT ADMITTED
SEPARATE ARCHITECTURE REQUIRED
```

## 14.3 Network identity / URL contracts

```text
CAPPORT_SITE_ID
CAPPORT_PUBLIC_BASE_URL
CAPPORT_API_PATH
CAPPORT_LOGIN_PATH
CAPPORT_ALLOWED_CLIENT_NETWORKS
```

Status:

```text
NOT ADMITTED
```

## 14.4 DHCP/DNS/captive-detection behavior

Examples:

```text
DHCP option 114
DNS/captive detection dependencies
pre-auth reachability
certificate/hostname requirements
```

Status:

```text
OUT OF SETTINGS STAGE 5
INFRASTRUCTURE / EXTERNAL CONTRACT
```

## 14.5 Browser/OS external CAPPORT contract

RFC 8908/8910 response semantics, media types, user-portal URL, captive state and OS behavior:

```text
NOT ADMIN-EDITABLE
```

Future admission requires a dedicated CAPPORT architecture contract.

---

# 15. SCOPE MODEL

Stage 5 remains:

```text
GLOBAL-only
```

No Site-scoped settings.

A Stage-5 configured title/support value applies to every Guest Portal request served by this `captive-portal.service` runtime.

Stage 5 MUST NOT create:

```text
site_id column
site-specific override
Site inheritance
Site precedence
Site-specific generation
Site picker for Portal Settings
```

Site-scoped Portal branding belongs to future Stage 9 architecture.

---

# 16. RESOLUTION / OWNERSHIP

For every Stage-5 key:

```text
persisted override
>
explicit process environment
>
repository default
```

`explicit process environment` is determined from the exact environment-name membership captured once by `run.py` during Settings bootstrap.

Never infer source from scalar equality.

Reset:

```text
clear_override
```

means:

```text
delete the key from the NEW immutable generation override set
→ lower-precedence source regains ownership
```

Reset MUST NOT copy environment/default scalar into SettingsStore.

---

# 17. SETTINGS DEFINITION MODEL

Reuse:

```text
SettingsDefinitionRegistry
```

Do NOT create:

```text
PortalDefinitionRegistry
PortalSettingsRegistry
second definition source
```

Extend `SettingsDefinition` only as required for generic string metadata.

Stage-5 definitions must support at minimum:

```text
domain = portal
value_type = string
presentation_type
required
min_length
max_length
max_lines where applicable
semantic_validator identity
```

Integer-only assumptions in current General read model must be generalized rather than duplicated.

Controller-specific string normalization MUST NOT be reused for Portal strings.

Required validator ownership:

```text
portal_presentation_config / portal setting validators
```

Controller URL validation remains Controller-owned.

---

# 18. PORTAL RUNTIME CONFIG CONTRACT

Introduce one immutable internal value object:

```text
PortalPresentationConfigV1
```

It contains exactly:

```text
translations:
    az:
        title
        greeting
        description
    ru:
        title
        greeting
        description
    en:
        title
        greeting
        description

support:
    phone_display
    phone_href
    email
    email_href
    whatsapp_url
    telegram_url
    facebook_url
```

It contains no:

```text
Auth configuration
CAPPORT protocol configuration
session state
redirect URL
Site ID
Omada credentials
```

Canonical composition:

```text
run.py
→ Settings bootstrap / ResolvedSettingsSnapshot(G)
→ create_app(settings=exact resolved mapping)
→ PortalPresentationConfigV1.from_settings(...)
→ ordinary Portal + CAPPORT login rendering
```

---

# 19. SINGLE-SNAPSHOT CONSUMER RULE

After Stage 5, production main process MUST NOT independently resolve Stage-5 keys through:

```text
os.getenv()
get_settings()
app/config.py imported mutable-looking constants
```

after canonical Settings bootstrap.

Allowed:

```text
app/config.py defines repository defaults / initial env-derived base values
run.py captures base settings once
ResolvedSettingsSnapshot owns selected generation
create_app receives exact runtime settings mapping
PortalPresentationConfigV1 is built from that mapping
```

Forbidden inconsistency:

```text
Admin effective_generation = G
but portal template still reads old process value independently
```

---

# 20. EXACT CONSUMERS

## Ordinary External Portal

```text
GET /
→ PortalEntryHandler
→ portal.html
```

uses `PortalPresentationConfigV1`.

## CAPPORT login bridge

```text
GET /capport/login
→ shared PortalEntryHandler / portal.html
```

uses the SAME `PortalPresentationConfigV1`.

CAPPORT discovery/protocol state remains separate and unchanged.

## Controlled CAPPORT error rendering that uses portal.html

When current CAPPORT route renders the common `portal.html`, it receives the SAME safe presentation config.

## `/success`

Stage 5 V1:

```text
NOT A CONSUMER
```

Legacy `/success` content remains code-owned.

No implementation may silently extend Stage-5 ownership into `/success`.

---

# 21. ACTIVATION SEMANTICS

All 14 Stage-5 keys:

```text
apply_requirement =
main_service_restart

activation_target =
captive-portal.service
```

No:

```text
next_request activation
new_session_only activation
hot reload
file watcher
dynamic template reload from Settings DB
automatic restart
systemctl button
```

Saved generation `G` becomes effective only after the existing main-service startup adoption contract successfully adopts `G`.

---

# 22. EXISTING / NEW GUEST SESSION SEMANTICS

Because Stage-5 fields are presentation-only:

## Already authorized guest

```text
authorization state unchanged
Omada state unchanged
Visit unchanged
```

If they already have a loaded page:

```text
page retains old rendered text until navigation/reload
```

## PENDING guest with loaded page

```text
AuthSession and AuthWorker continue unchanged
loaded page retains old presentation
```

A service restart may naturally terminate process-local AuthSession state under existing lifecycle semantics; Stage 5 introduces no new preservation promise.

## New guest before restart

Receives:

```text
currently effective generation
```

not newly configured pending generation.

## New guest after successful restart/adoption

Receives:

```text
new effective generation
```

## Existing browser page

No push/hot update.

No Stage-5 polling endpoint.

---

# 23. AUTHORIZATION / AUTH FLOW SECURITY BOUNDARY

Stage 5 MUST NOT modify:

```text
AuthSession TTL
retry cooldown
AuthWorker attempts
readiness algorithm
Omada /auth request
authorization success criteria
authorization failure classification
pending cleaner protection
Visit opening semantics
redirect URL received from Omada External Portal
CAPPORT identity resolution
```

Presentation strings MUST NOT influence state machine decisions.

No parser may derive auth behavior from operator text.

---

# 24. REDIRECT DESTINATION DECISION

Stage 5 admits:

```text
NO redirect destination setting
```

Current incoming `redirectUrl` handling remains governed by the existing Portal/Auth contract.

Admin cannot configure:

```text
post-auth redirect
external landing URL
fallback redirect
arbitrary return URL
```

Any future redirect setting requires separate open-redirect/security architecture.

---

# 25. COOKIE / SESSION / CSRF DECISION

Stage 5 admits no setting affecting:

```text
guest cookie
Admin cookie
session TTL
session identifier
SameSite
Secure
HttpOnly
CSRF
pre-auth state
```

All remain outside Stage 5.

---

# 26. VALIDATION SERVICE

Mutation validation is:

```text
all-or-nothing
```

Candidate generation is accepted only when:

```text
all 14 registered Portal settings resolve
+
every changed setting passes primitive validation
+
every Portal setting passes semantic validation
+
whole PortalPresentationConfigV1 composes successfully
+
all already-required Settings candidate validation passes
```

On any failure:

```text
NO generation created
NO audit append
NO override mutation
NO idempotency success receipt
```

Response:

```text
422 validation_failed
```

with bounded non-sensitive reason.

---

# 27. CROSS-SETTING INVARIANTS

Text fields are independently required.

Support fields are independently optional.

Only cross-field invariant:

```text
if all five support fields are empty
→ support section hidden
```

There is NO requirement that at least one support contact be configured.

No coupling between:

```text
title
greeting
description
support fields
CAPPORT
Portal Counter
Public Traffic
```

---

# 28. SETTINGSSTORE SCHEMA

Stage 5 requires:

```text
SettingsStore schema v4
```

Reason:

current v3 constrains durable mutation/audit domain enums and must explicitly admit:

```text
portal
```

No new physical Settings database.

No new generation table.

No secret table change.

## v4 change scope

`settings_mutation_audit.setting_domain` admits:

```text
general
controller
portal
```

Ordinary secret audit remains in its existing dedicated secret boundary.

`settings_idempotency.mutation_domain` admits:

```text
general
controller
controller_secret
portal
```

`settings_overrides` already supports:

```text
integer
string
```

and does not require a new value-storage table.

Any current controller-specific string-history validator must become definition-owned/domain-aware so Portal strings are not passed through `normalize_controller_setting()`.

---

# 29. MIGRATION CONTRACT

Allowed migration:

```text
v3 → v4 only
```

Migration occurs through the existing SettingsRepository startup/schema-owner path.

Mandatory:

```text
single bounded migration transaction
preserve generation IDs
preserve target effective_generation
preserve all existing General overrides
preserve all Controller overrides
preserve secret bindings
preserve activation events
preserve audit
preserve idempotency
```

No Stage-5 default overrides are materialized during migration.

After migration, old generations that contain no Portal keys resolve Portal values from:

```text
environment
or repository default
```

according to normal precedence.

---

# 30. DOWNGRADE / ROLLBACK COMPATIBILITY

Before production migration v3→v4:

```text
verified Settings DB v3 backup required
```

Rollback to pre-Stage5 application code:

```text
MUST restore compatible pre-migration v3 Settings DB backup
```

In-place code downgrade against schema v4 is:

```text
NOT SUPPORTED
```

No automatic down-migration.

A code rollback MUST NOT silently ignore Portal overrides or cause older code to reinterpret v4 as v3.

---

# 31. COMMON GENERATION / ETAG

Portal mutations use the SAME global generation chain as General/Controller/Secret changes.

Example:

```text
current head = G12

Portal text Save
→ G13

Controller change afterward
→ G14
```

No parallel Portal generation number.

Common ETag:

```text
"settings-g<configured_generation>"
```

A stale Portal edit must fail if any domain created a newer global generation.

This preserves whole-control-plane CAS.

---

# 32. API CONTRACT

## Page

```text
GET /admin/settings/portal
```

## Read API

```text
GET /admin/api/v1/settings/portal
```

## Mutation API

```text
POST /admin/api/v1/settings/portal/generations
```

No:

```text
PUT
PATCH
DELETE
per-setting mutation endpoint
Site route
```

---

# 33. PORTAL READ API

Success:

```text
200 application/json
```

Top-level:

```text
api_version =
admin.settings.portal.v1

request_id
scope = {"type":"global"}
store_state
configured_generation
effective_generation
etag
restart_required
pending_setting_count
settings[]
```

Every field includes:

```text
key
display_label
description
group
value_type
presentation_type
scope_type
scope_id
editable
secret_class
default_value
base_source
base_value
persisted_override_value
configured_value
effective_value
pending_value
configured_generation
effective_generation
activation_state
apply_requirement
activation_target
validation
last_changed_at
last_changed_by
```

No Site context.

No operational Portal health is inferred.

Headers:

```text
Cache-Control: no-store
Pragma: no-cache
ETag: "settings-gN"
```

---

# 34. MUTATION API

Request JSON:

```json
{
  "changes": [
    {
      "key": "PORTAL_UI_GREETING_EN",
      "operation": "set",
      "value": "Welcome!"
    },
    {
      "key": "PORTAL_SUPPORT_FACEBOOK_URL",
      "operation": "clear_override"
    }
  ]
}
```

Allowed operations:

```text
set
clear_override
```

Maximum changes in one Portal mutation:

```text
14
```

Duplicate keys:

```text
400 invalid_request
```

Unknown key/domain mismatch:

```text
400 invalid_request
```

Required headers:

```text
Content-Type: application/json
If-Match: "settings-gN"
Idempotency-Key: valid existing Settings format
CSRF: existing Admin mutation contract
```

Success semantics reuse current common Settings mutation behavior.

---

# 35. RESET SEMANTICS

UI label:

```text
Reset to deployment/default
```

Operation:

```text
clear_override
```

Result:

```text
persisted override removed in new generation
configured value resolves from explicit environment if present
otherwise repository default
```

No value copying.

No history deletion.

---

# 36. AUTHORIZATION CAPABILITIES

Introduce exact capabilities:

```text
admin.read.settings.portal
admin.write.settings.portal
```

They are independently representable through current `AdminPrincipal.global_capabilities`.

Authorization:

```text
GET page / GET API
→ admin.read.settings.portal

POST mutation API
→ admin.write.settings.portal
AND admin.read.settings.portal
```

Write does not imply read automatically in policy.

---

# 37. DEFAULT GRANT POLICY

Stage-5 capabilities are added to the code-owned recognized capability universe.

They are NOT automatically added to:

```text
DEFAULT_GLOBAL_CAPABILITIES
```

and MUST NOT silently expand privileges of an existing deployment after code upgrade.

Therefore production Portal Settings is invisible/non-writable until deployment explicitly grants:

```text
admin.read.settings.portal
admin.write.settings.portal
```

through the existing Admin capability configuration mechanism.

These grant settings remain deployment-owned and are NOT writable from Admin Settings.

---

# 38. SESSION CAPTURE SEMANTICS

Admin global capabilities are captured into the authenticated `AdminPrincipal`.

Stage 5 does not add dynamic capability refresh.

A deployment capability change becomes available only through the existing Admin configuration/startup boundary.

Current process restart naturally invalidates process-local Admin sessions.

No Stage-5 mechanism mutates privileges inside an existing session.

---

# 39. UI INFORMATION ARCHITECTURE

Settings hierarchy:

```text
Settings
├─ General
├─ Controller
└─ Portal
   └─ Guest Portal
```

Canonical page:

```text
/admin/settings/portal
```

Top-level sidebar remains:

```text
Settings
```

Portal appears as secondary Settings navigation only when:

```text
WEB_ADMIN_SETTINGS_ENABLED=true
AND
principal has admin.read.settings.portal
```

Do not create an empty `Portal` section when capability is absent.

---

# 40. PORTAL SETTINGS UX

Page heading:

```text
Guest Portal
```

Subtitle:

```text
Global guest-facing presentation settings
```

Sections:

```text
Branding & welcome
Support contacts
```

Each setting shows:

```text
Configured
Effective
Source
Pending status where applicable
Reset action where persisted override exists
validation hint
```

When configured generation differs from effective generation:

```text
Saved successfully.
Pending captive-portal.service restart.
```

No wording may imply that Save immediately changed guest pages.

---

# 41. NO RESTART CONTROL

UI/API MUST NOT provide:

```text
Restart
Apply now
Reload
systemctl
systemd D-Bus
sudo
process signal
provider recreation
```

The Admin application has no systemd authority.

---

# 42. AUDIT CONTRACT

All Stage-5 values are:

```text
public guest-facing content
not secrets
```

Therefore ordinary immutable Settings audit may store:

```text
previous_persisted_override
new_persisted_override
previous_configured_value
new_configured_value
operation
principal
source IP
request ID
timestamp
generation
```

Full values are allowed in SettingsStore/audit because they are intentionally public Portal content.

However application logs and telemetry MUST NOT emit changed text/phone/email/URLs by default.

Logs may emit:

```text
setting key
generation
operation
validation reason code
principal identity under existing Admin audit policy
```

No request body logging.

No HTML rendering of audit values is added in Stage 5.

---

# 43. PRIVACY CLASSIFICATION

Support phone/email/social URLs are not secrets because they are rendered publicly to guests.

Architecture nevertheless treats them as:

```text
operator-controlled public contact data
```

Stage-5 UI should state:

```text
This value is publicly visible to guests.
```

No private credential or personal secret may be entered.

No special encrypted storage is used.

Stage 4 master key is irrelevant.

---

# 44. FAILURE SEMANTICS — SETTINGSSTORE UNAVAILABLE

If Settings product is enabled but SettingsStore is unavailable:

```text
/admin/settings/portal
→ bounded unavailable page

GET Portal Settings API
→ 503 settings_store_unavailable

POST Portal Settings mutation
→ 503 settings_store_unavailable
```

Existing Portal runtime continues according to the already-started runtime configuration.

SettingsStore read failure in Admin request MUST NOT break guest Portal/Auth.

---

# 45. INVALID PERSISTED PORTAL VALUE AT STARTUP

If store is available and configured generation contains an invalid Stage-5 Portal value:

```text
Settings candidate composition fails
```

The process MUST NOT:

```text
silently substitute env/default for that persisted key
silently drop only the Portal override
claim generation adopted
```

Use existing positive in-process Settings activation failure semantics where durable attribution is possible.

Do not advance effective generation.

No automatic rollback.

---

# 46. CONSUMER COMPOSITION FAILURE

If `PortalPresentationConfigV1` cannot compose from configured generation:

```text
generation adoption fails
```

and the new runtime must not serve guest requests while claiming that generation is effective.

This is a configuration adoption failure.

---

# 47. OPERATIONAL PORTAL DEGRADATION

Examples:

```text
Omada unreachable
counter DB unavailable
public traffic unavailable
network failure
browser closed
CAPPORT client discovery failure
```

are NOT by themselves:

```text
Settings activation failure
```

Permanent invariant:

```text
operational source degradation
!=
Settings activation failure
```

---

# 48. PARTIAL CONSUMER AVAILABILITY

All 14 Stage-5 definitions share one required consumer:

```text
PortalPresentationConfigV1
```

There is no per-language partial adoption.

If any required Stage-5 value is invalid:

```text
whole generation is not adopted
```

Optional empty support contacts are valid configured values, not disabled-consumer failures.

---

# 49. STAGE-4 RELATION

Stage 5:

```text
does NOT require managed OMADA_CLIENT_SECRET activation
does NOT require master key
does NOT mutate controller_secret_versions
does NOT mutate settings_secret_bindings
does NOT call ControllerSecretRepository
```

Production may legitimately have:

```text
Stage-4 code deployed
managed secret storage operational activation deferred
Stage-5 Portal settings code deployed/activated separately
```

No dependency exists between:

```text
Portal presentation mutation
and
Stage-4 master-key availability
```

---

# 50. CAPPORT FAILURE ISOLATION

Stage-5 presentation config is shared with CAPPORT login rendering, but:

```text
CAPPORT protocol service
must not gain SettingsStore request-time dependency
```

No CAPPORT request reads SQLite Settings directly.

It uses the already-adopted immutable startup `PortalPresentationConfigV1`.

Thus:

```text
SettingsStore later unavailable
→ CAPPORT/Portal continue with adopted in-memory configuration
```

---

# 51. BROWSER STORAGE

Stage-5 content may naturally exist in:

```text
rendered DOM
JavaScript in-memory translation object
browser page memory
```

Application MUST NOT additionally persist Stage-5 configuration into:

```text
cookies
localStorage
sessionStorage
IndexedDB
history state
service worker cache
```

Existing language-preference behavior is outside Stage-5 persistence ownership and must not be expanded to store settings content.

No guarantee is claimed about browser extensions, accessibility tooling, browser caches outside application control, screenshots or user-agent memory.

---

# 52. SUCCESS PAGE BOUNDARY

Current `/success` page contains separate code-owned translations.

Stage 5 V1 does not replatform that page.

Therefore:

```text
/success presentation ownership =
unchanged / code-owned
```

If future product work wants shared branding across both pages, it requires explicit follow-up admission.

Coder must not opportunistically refactor `/success`.

---

# 53. COUNTER / PUBLIC TRAFFIC BOUNDARY

Stage 5 does NOT admit:

```text
PORTAL_COUNTER_ENABLED
PORTAL_COUNTER_API_ENABLED
PORTAL_COUNTER_TIMEZONE
PUBLIC_TRAFFIC_COUNTER_ENABLED
PUBLIC_TRAFFIC_SSID
PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS
PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS
```

Reason:

```text
these affect data products, feature state, scope, polling or operational behavior
beyond pure Guest Portal content.
```

They remain owned by later product/operational Settings stages.

---

# 54. PENDING SESSION CLEANER BOUNDARY

No `PENDING_SESSION_CLEANER_*` key is admitted.

`PENDING_SESSION_CLEANER_PORTAL_GRACE_SECONDS` contains the word Portal but is:

```text
operational authorization-cleanup behavior
```

not Guest Portal presentation.

It belongs to later operational-module architecture.

---

# 55. AUTH SESSION CONSTANTS

Current:

```text
SESSION_TTL_SECONDS
SESSION_RETRY_COOLDOWN_SECONDS
```

and related Auth constants remain code-owned.

Stage 5 does not make them Settings.

Any future admission requires separate authorization/session-lifecycle review.

---

# 56. ACCEPTANCE INVARIANTS

```text
S5-I01
Exactly 14 Portal keys are writable.

S5-I02
No unregistered Portal/config/env key can be mutated.

S5-I03
Stage 5 remains GLOBAL-only.

S5-I04
No Site-scoped override exists.

S5-I05
All Portal values use persisted override > explicit env > repository default.

S5-I06
Reset clears override and returns ownership downward.

S5-I07
All 14 values require captive-portal.service restart.

S5-I08
Admin has no restart/systemd authority.

S5-I09
Portal runtime consumes the exact adopted startup snapshot.

S5-I10
No Stage-5 consumer performs independent get_settings/os.getenv after composition.

S5-I11
Ordinary / and CAPPORT login use the same PortalPresentationConfigV1.

S5-I12
No CAPPORT configuration key is admitted.

S5-I13
No Authorization semantic setting is admitted.

S5-I14
No redirect destination setting is admitted.

S5-I15
No cookie/session/CSRF setting is admitted.

S5-I16
Operator text is plain text only.

S5-I17
No arbitrary HTML/JS/CSS is accepted.

S5-I18
Client rendering uses textContent / safe Jinja serialization, never innerHTML.

S5-I19
Social URLs use exact restricted HTTPS host contracts.

S5-I20
All support fields may be empty; all empty hides support section.

S5-I21
Portal mutations use common global Settings generation and ETag.

S5-I22
Stale write after another-domain generation fails CAS.

S5-I23
Portal mutation is atomic all-or-nothing.

S5-I24
Portal read requires admin.read.settings.portal.

S5-I25
Portal mutation requires both read and write Portal capabilities.

S5-I26
Portal capabilities are independently assignable.

S5-I27
New Portal capabilities are not silently default-granted on upgrade.

S5-I28
SettingsStore schema becomes v4.

S5-I29
v3→v4 preserves all prior generations/history/secret bindings.

S5-I30
No Portal override is materialized during migration.

S5-I31
Rollback to pre-Stage5 code requires v3 DB restore.

S5-I32
Stage 5 does not depend on Stage-4 master key.

S5-I33
Stage 5 does not mutate managed Controller secret state.

S5-I34
SettingsStore request-time failure does not break already-started Guest Portal.

S5-I35
Invalid persisted Portal config cannot silently fall back while claiming adoption.

S5-I36
Operational Omada/CAPPORT/counter failure does not become Settings activation failure.

S5-I37
Loaded browser page is not hot-updated after Save/restart.

S5-I38
Existing AuthSession semantics are unchanged.

S5-I39
/success remains code-owned in V1.

S5-I40
Counter/Public Traffic/Pending Cleaner operational settings remain outside Stage 5.
```

---

# 57. MANDATORY TEST / ACCEPTANCE MATRIX

## Definition / registry

```text
exact 14 Portal definitions
no accidental extra writable keys
defaults equal canonical code defaults
domain = portal
GLOBAL scope only
normal/non-secret classification
```

## Resolution

```text
repository default
explicit env
persisted override
clear_override fallback
explicit env membership provenance
```

## Text validation

```text
valid AZ Unicode
valid RU Unicode
valid EN
NFC required
empty required text rejected
leading/trailing whitespace rejected
control characters rejected
bidi controls rejected
title newline rejected
greeting newline rejected
description LF accepted
description >4 lines rejected
max lengths exact boundaries
HTML-like text rendered literally
```

## Support validation

```text
phone default valid
phone empty valid
invalid phone rejected
email default valid
email empty valid
CRLF email injection rejected
WhatsApp exact host/path accepted
WhatsApp query rejected
Telegram exact host/path accepted
Telegram extra path/query rejected
Facebook allowed hosts accepted
Facebook arbitrary query rejected
http:// rejected
userinfo rejected
fragment rejected
lookalike hostname rejected
```

## Rendering

```text
ordinary / uses configured effective presentation
CAPPORT /capport/login uses same effective presentation
support empty rows hidden
all support empty hides support section
no innerHTML
no arbitrary operator HTML execution
no settings values persisted by application browser storage
```

## Generation

```text
Portal Save creates next common global generation
mixed Portal batch atomic
no-op semantics follow common Settings contract
If-Match stale failure
idempotency replay
idempotency conflict
pending_main_restart after change
effective remains old before restart
effective changes only after adopted startup
```

## Authorization

```text
no Portal read capability → page/API forbidden
read only → GET allowed, POST forbidden
write without read → POST forbidden
read+write → mutation allowed
existing default capabilities do not silently gain Portal rights
```

## Failure

```text
store unavailable
invalid persisted Portal value
PortalPresentationConfig composition failure
Omada operational failure independent from Settings activation
counter failure independent from Settings activation
```

## Migration

```text
empty v3 → v4
populated v3 → v4
existing General overrides preserved
Controller overrides preserved
secret bindings preserved
effective_generation preserved
audit/idempotency preserved
old generations resolve Portal defaults/env
pre-Stage5 binary + v4 not treated as supported downgrade
```

## Regression

```text
Portal authorization unchanged
CAPPORT protocol output unchanged
Omada authorization unchanged
Visit lifecycle unchanged
Pending Cleaner unchanged
Portal Counter semantics unchanged
Public Traffic semantics unchanged
Admin General Settings unchanged
Controller Settings unchanged
Stage-4 secret management unchanged
```

---

# 58. IMPLEMENTATION FORBIDDEN LIST

Coder MUST NOT implement/change:

```text
CAPPORT settings mutation

CAPPORT_ENABLED
CAPPORT_SITE_ID
CAPPORT_PUBLIC_BASE_URL
CAPPORT_API_PATH
CAPPORT_LOGIN_PATH
CAPPORT_ALLOWED_CLIENT_NETWORKS
CAPPORT cache TTLs

DHCP option 114
DNS captive detection
Nginx/proxy configuration
public hostname/certificate

AuthSession TTL
retry cooldown
AuthWorker algorithm
Omada authorization flow

post-auth redirect setting
redirect allowlist
external landing-page setting

cookies
CSRF
trusted proxy semantics

Site-scoped Portal settings
Site-specific branding
multi-Site inheritance

Portal Counter feature toggle
Public Traffic feature toggle
public-traffic SSID/scope
counter DB
traffic DB
timezone ownership

Pending Session Cleaner settings

arbitrary HTML
Markdown
custom JS
custom CSS
uploaded logo
uploaded favicon
file upload subsystem

success.html refactor

systemctl
restart button
reload button
hot reload
file watcher

second Settings DB
second generation chain
second audit subsystem
second idempotency subsystem

Stage-4 master-key changes
Controller secret state changes

unrelated visual redesign
```

---

# 59. UNRESOLVED ARCHITECTURE QUESTIONS

```text
OPEN P0 = 0
OPEN P1 = 0
```

Stage-5 V1 deliberately resolves ambiguity by keeping higher-risk categories outside the allowlist.

Anything not named in the exact 14-key allowlist is:

```text
NOT ADMITTED
```

unless a later accepted architecture explicitly admits it.

---

# 60. TECH LEAD REVIEW POINTS

Tech Lead should verify specifically:

```text
1. 14-key allowlist is sufficiently bounded.
2. portal domain addition correctly requires Settings schema v4.
3. common generation/ETag semantics remain intact.
4. Controller-specific string normalization is not reused for Portal strings.
5. global-only scope matches Stage-9 roadmap boundary.
6. presentation-only fields cannot influence Auth/CAPPORT state machines.
7. restricted support URL rules are narrow enough.
8. capability default-grant policy does not silently expand existing operator privileges.
9. restart/adoption semantics remain the existing main-service contract.
10. v3 backup/restore requirement is sufficient for downgrade safety.
11. Stage 4 managed-secret activation is not a dependency.
12. /success and public counter domains remain explicitly outside scope.
```

---

# 61. FINAL ARCHITECTURE DISPOSITION

```text
DOCUMENT =
CAPTIVPORTAL ADMIN SETTINGS
STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS
ARCHITECTURE CONTRACT v0.1

BASELINE =
main@c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9

TREE =
59df8aa855fe094e173db611fbbdf5714c229b86

STAGE_5_SCOPE =
GLOBAL GUEST PORTAL PRESENTATION / PUBLIC SUPPORT CONTENT ONLY

ADMITTED_KEYS =
14

CAPPORT_CONFIGURATION_ADMITTED =
NO

SITE_SCOPED_SETTINGS =
NO

AUTHORIZATION_BEHAVIOR_MUTATION =
NO

REDIRECT_MUTATION =
NO

HTML/JS/CSS_OPERATOR_CONTENT =
NO

SETTINGS_REGISTRY =
REUSE / EXTEND EXISTING SettingsDefinitionRegistry

SETTINGS_STORE =
REUSE EXISTING settings.sqlite3

SETTINGS_SCHEMA =
v4 REQUIRED

GENERATION_MODEL =
COMMON GLOBAL GENERATION

ETAG_MODEL =
COMMON "settings-gN"

PRECEDENCE =
persisted override
> explicit environment
> repository default

RESET =
clear persisted override

ACTIVATION =
main_service_restart

ACTIVATION_TARGET =
captive-portal.service

ADMIN_SYSTEMD_AUTHORITY =
NO

CAPABILITIES =
admin.read.settings.portal
admin.write.settings.portal

NEW_CAPABILITIES_DEFAULT_GRANTED =
NO

STAGE_4_MASTER_KEY_DEPENDENCY =
NO

STAGE_4_SECRET_STATE_MUTATION =
NO

OPEN_ARCH_P0 =
0

OPEN_ARCH_P1 =
0

ARCHITECTURE =
DRAFT FOR TECH LEAD REVIEW

IMPLEMENTATION TASK =
HOLD

CODER =
HOLD

PRODUCTION CHANGE =
NO
```

Следующий разрешённый шаг:

```text
Tech Lead
→ architecture review

if PASS:
→ Technical Developer prepares exact Stage-5 implementation TASK
→ Tech Lead implementation-contract review
→ only then Coder authorization
```
