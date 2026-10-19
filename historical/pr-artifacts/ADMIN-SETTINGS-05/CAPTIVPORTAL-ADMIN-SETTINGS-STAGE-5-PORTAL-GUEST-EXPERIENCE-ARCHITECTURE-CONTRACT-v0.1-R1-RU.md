# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS
### ARCHITECTURE CONTRACT v0.1-R1
### BOUNDED NORMATIVE DISPOSITION FOR TECH LEAD RE-REVIEW

**Проект:** CaptivPortal  
**Область:** Admin UI → Settings → Portal → Guest Portal  
**Роль:** Architect  
**Baseline:** `main@c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9`  
**TREE:** `59df8aa855fe094e173db611fbbdf5714c229b86`  
**Parent document:** `CAPTIVPORTAL ADMIN SETTINGS — STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS — ARCHITECTURE CONTRACT v0.1`  
**Статус:** `DRAFT FOR TECH LEAD RE-REVIEW`  
**Implementation TASK:** `HOLD`  
**Coder:** `HOLD`  
**Production change:** `NO`

---

# 0. НАЗНАЧЕНИЕ R1

Этот документ является **bounded normative patch** к Architecture Contract v0.1.

Он закрывает только:

```text
P1-01 — Settings schema v4 / Stage-4 break-glass compatibility
P1-02 — PortalPresentationConfigV1 / code-owned localization composition
P1-03 — CAPPORT HTML vs JSON consumer boundary
P1-04 — Portal public API serialization + restricted URL port semantics
```

Все решения v0.1, не изменённые этим R1, остаются без изменений.

При конфликте формулировок:

```text
v0.1-R1
>
v0.1
```

---

# 1. SOURCE REVIEW CONFIRMATION

Baseline source подтверждает:

```text
app/settings_control/secret_recovery.py
→ SettingsRepository.open_existing_v3(...)

SettingsRepository.open_existing_v3(...)
→ принимает только PRAGMA user_version == 3
```

Следовательно исходный v0.1 действительно создавал несовместимость:

```text
Stage 5:
v3 → v4

но

Stage-4 recovery:
v3 only
```

Baseline также подтверждает:

```text
PORTAL_TRANSLATIONS
```

как один общий code-owned language object, в котором одновременно находятся:

```text
Stage-5 admitted:
title
greeting
description

и

code-owned trusted:
auth/progress/retry/error/support/counter presentation strings
```

CAPPORT `/capport/login` действительно имеет разные HTML и JSON ветки, а current common Settings mutation service уже различает:

```text
changed → 201
no-op → 200
```

и сохраняет idempotency response для точного replay.

R1 ниже фиксирует архитектуру без оставления этих решений Кодеру.

---

# 2. P1-01 — CLOSED
# STAGE-4 BREAK-GLASS RECOVERY AFTER SCHEMA v4

## 2.1 Final architecture direction

Выбран exact mechanism:

```text
CURRENT-SCHEMA-AWARE
EXISTING-ONLY
RECOVERY REPOSITORY OPEN
```

Canonical recovery open boundary:

```text
SettingsRepository.open_existing_for_recovery(db_path)
```

После Stage 5:

```text
SETTINGS_SCHEMA_VERSION = 4
```

и `open_existing_for_recovery(...)` должен принимать **ровно current schema version**, то есть для Stage-5 binary:

```text
PRAGMA user_version == 4
```

Он НЕ должен содержать hard-coded:

```text
v3
```

в имени или проверке.

---

# 3. RECOVERY OPEN SEMANTICS

`SettingsRepository.open_existing_for_recovery(db_path)` является отдельным repository-open mode.

Он MUST:

```text
open an already-existing Settings DB only

NOT create a DB

NOT initialize an empty DB

NOT migrate schema

NOT change PRAGMA user_version

NOT repair schema

NOT rebuild tables

NOT delete history
```

Перед возвратом usable repository он MUST validate current schema and integrity against the current application contract:

```text
PRAGMA user_version == SETTINGS_SCHEMA_VERSION

exact current Settings schema

required immutability triggers

PRAGMA quick_check = ok

foreign_key_check = clean

generation-0 invariant

settings_target_state invariant

ordinary Settings history validity

Controller secret history/reference validity
```

Any failure:

```text
settings_store_unavailable
or existing bounded Stage-4 secret-store error class where already normative
```

No raw SQLite exception/path is exposed.

---

# 4. RECOVERY FILESYSTEM SECURITY

Stage 5 MUST NOT weaken any accepted Stage-4 `SecretFilesystem` rules.

For recovery:

```text
Settings DB file/path validation =
MANDATORY
```

using the existing Stage-4 security policy:

```text
exact Settings DB path
regular file
not symlink
expected owner
required secure mode
safe parent directory
same opened inode/path object check
```

Normal Stage-4 master-key filesystem validation remains unchanged for secret-store operations that use the master key.

The break-glass **clear** operation preserves its accepted special property:

```text
NO secret decrypt
NO secret read-back
NO master-key bytes required
```

The recovery clear MUST remain possible specifically without decrypting the managed secret.

Therefore R1 does **not** introduce a new dependency:

```text
"master key must decrypt successfully before managed ownership may be cleared"
```

That would defeat the break-glass purpose.

Permanent distinction:

```text
Stage-4 normal managed-secret resolve/write
→ master-key security/availability required

Stage-4 break-glass clear
→ secure Settings DB validation required
→ no secret decryption
→ no master-key material read required
```

No Stage-5 code may relax the normal master-key path/owner/group/mode rules.

---

# 5. SERVICE-STOPPED RECOVERY BOUNDARY

Stage-4 break-glass remains:

```text
LOCAL OPERATOR ONLY
SERVICE MUST ALREADY BE STOPPED
```

The recovery command gains:

```text
NO systemd authority
NO stop/start authority
NO sudo orchestration
```

It does not stop or restart `captive-portal.service`.

Operational caller remains responsible for satisfying the stopped-service precondition before invoking recovery.

---

# 6. BREAK-GLASS CAS SEMANTICS

Recovery continues to require:

```text
--expected-generation N
```

Inside the one SettingsStore write transaction:

```text
parent = current configured head

if parent != expected_generation
→ 412 stale_generation
→ NO mutation
```

No retry with a silently refreshed generation.

No "clear latest regardless of head" mode.

---

# 7. BREAK-GLASS MUTATION SEMANTICS ON v4

If configured head `G` has no managed `OMADA_CLIENT_SECRET` binding:

```text
changed = false
configured_generation remains G
no new generation
no secret mutation audit row
```

If configured head `G` has managed secret ownership:

```text
create G+1
parent_generation_id = G
```

The new generation MUST copy **all ordinary overrides unchanged**, including every domain admitted by current schema:

```text
General overrides
Controller non-secret overrides
Portal Stage-5 overrides
future ordinary domains only if separately admitted later
```

The recovery generation changes only:

```text
managed OMADA_CLIENT_SECRET ownership
```

It MUST NOT:

```text
clear Portal overrides
clear General overrides
clear Controller overrides
rewrite their values
create ordinary-setting audit rows
alter effective_generation
alter previous generations
alter idempotency history
```

Secret binding for the new configured generation:

```text
NONE
```

Existing accepted secret-safe recovery audit remains:

```text
operation =
clear_secret_override_recovery
```

No raw secret enters that audit.

---

# 8. BREAK-GLASS HISTORY / SECRET VERSION RULE

R1 preserves Stage-4 accepted live-state semantics.

After recovery:

```text
controller_secret_versions
```

may undergo the existing logical GC policy so only secret versions referenced by current configured and/or effective ownership remain addressable live versions.

R1 does not change the Stage-4 rule that this is:

```text
logical live-state deletion
NOT forensic secure erasure
```

No history UI.

No old-secret selector.

No secret read-back.

---

# 9. RECOVERY OUTPUT

Recovery CLI output remains bounded and secret-safe.

Allowed success output is equivalent to:

```text
configured_generation=<N> changed=true|false
```

It MUST NOT print:

```text
secret
ciphertext
nonce
secret_version_id
master key
environment secret
decrypted value
```

---

# 10. P1-01 ACCEPTANCE MATRIX ADDITION

Stage-5 migration acceptance MUST include:

```text
R1-REC-01
populated v3 → v4 migration PASS

R1-REC-02
v4 database with General + Controller + Portal generations
opens through open_existing_for_recovery

R1-REC-03
v4 + managed secret binding + exact expected generation
break-glass clear PASS

R1-REC-04
Portal overrides survive recovery unchanged

R1-REC-05
General overrides survive recovery unchanged

R1-REC-06
Controller non-secret overrides survive recovery unchanged

R1-REC-07
secret binding cleared only for new configured generation

R1-REC-08
effective generation not advanced by recovery

R1-REC-09
stale expected generation → 412 / no mutation

R1-REC-10
no managed binding → no-op / no generation

R1-REC-11
immutable history/audit/idempotency preserved

R1-REC-12
DB permission/path validation remains mandatory

R1-REC-13
recovery performs no secret decrypt/read-back

R1-REC-14
v4 recovery requires no request-time Settings migration

R1-REC-15
schema version hard-code "v3" absent from current recovery-open contract
```

Mandatory gate:

```text
v4 + Stage-4 break-glass recovery = PASS
```

P1-01:

```text
CLOSED
```

---

# 11. P1-02 — CLOSED
# EXACT LOCALIZATION / PRESENTATION COMPOSITION MODEL

## 11.1 Permanent ownership split

`PORTAL_TRANSLATIONS` remains the canonical code-owned full localization catalog for all non-admitted strings.

Stage 5 replaces exactly these keys:

```text
title
greeting
description
```

for exactly:

```text
az
ru
en
```

No other `PORTAL_TRANSLATIONS` key becomes Settings-owned.

Permanent invariant:

```text
Stage-5 adopted values replace ONLY:
title
greeting
description

EVERY OTHER existing localization key remains code-owned
and semantically unchanged.
```

---

# 12. EXACT STARTUP COMPOSITION

Two immutable internal models are frozen.

## 12.1 PortalPresentationConfigV1

Settings-owned startup config contains only:

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

It is built exactly once from the adopted startup Settings snapshot.

It contains no code-owned auth/retry/status translations.

## 12.2 PortalTemplatePresentationV1

A second immutable **safe rendering projection** is built during Flask/Portal composition:

```text
PortalTemplatePresentationV1
```

It contains:

```text
translations =
FULL portal translation object

support =
validated safe support projection
```

Composition algorithm is normative:

```text
1. take the code-owned PORTAL_TRANSLATIONS catalog

2. create a new immutable rendering projection;
   do NOT mutate the module-level catalog in-place

3. preserve the exact existing language set:
   az
   ru
   en

4. preserve every existing code-owned key/value

5. overlay exactly:
   title
   greeting
   description

   from PortalPresentationConfigV1
   for each of az/ru/en

6. attach the validated support projection

7. freeze the resulting rendering object

8. reuse that same immutable object for every portal.html render
   during that process lifetime
```

No request-time dictionary merge.

No SettingsStore request-time read.

No request-time `get_settings()`.

No request-time `os.getenv()`.

---

# 13. TEMPLATE DELIVERY BOUNDARY

Every `portal.html` render receives:

```text
portal_translations =
PortalTemplatePresentationV1.translations

portal_support =
PortalTemplatePresentationV1.support
```

`portal_translations` therefore keeps the **same full logical language-object shape** currently consumed by portal JavaScript.

Stage 5 does NOT introduce:

```text
two competing translation objects
browser-side settings merge
browser-side fallback merge
request-time overlay
```

Portal JS continues to consume one full translation object.

---

# 14. INITIAL SERVER-RENDERED AZ CONTENT

Decision:

```text
INITIAL SERVER-RENDERED AZ
MUST USE ADOPTED STAGE-5 PRESENTATION
```

Before JavaScript executes, the following current AZ-visible elements:

```text
h1 portal title
greeting
description
```

MUST be rendered from:

```text
PortalTemplatePresentationV1.translations["az"]
```

They MUST NOT remain hard-coded Stage-5 defaults in the HTML template.

Therefore:

```text
JS disabled
slow JS
captive WebView before JS execution
```

still sees the adopted AZ Stage-5 content for these three fields.

Other server-rendered status/retry/error fallback strings remain code-owned.

---

# 15. HTML `<title>` DECISION

Stage 5 V1 does **NOT** make document `<title>` configurable.

It remains code-owned exactly:

```text
Zəfər Parkı - Wi-Fi
```

No active-language dynamic `<title>` logic is introduced.

No `PORTAL_UI_DOCUMENT_TITLE_*` setting exists.

Changing `PORTAL_UI_TITLE_AZ/RU/EN` changes the visible portal heading only, not the HTML document title.

Future document-title branding requires separate admission.

---

# 16. CODE-OWNED TRANSLATION PRESERVATION

The following remain sourced only from the code-owned catalog:

```text
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

counterHeading
counterToday
counterTotal
trafficHeading
trafficToday
trafficTotal
```

and every other existing non-admitted translation key.

Stage-5 implementation MUST NOT rename, remove, reinterpret, or make them writable.

Composition must fail closed during tests/development if the overlay would remove a code-owned key.

---

# 17. P1-02 ACCEPTANCE MATRIX ADDITION

```text
R1-LOC-01
full AZ translation keyset before/after Stage-5 overlay is identical

R1-LOC-02
full RU translation keyset before/after overlay is identical

R1-LOC-03
full EN translation keyset before/after overlay is identical

R1-LOC-04
only title/greeting/description values may differ

R1-LOC-05
WAITING unchanged

R1-LOC-06
AUTHORIZED unchanged

R1-LOC-07
retryButton unchanged

R1-LOC-08
retry/error notes unchanged

R1-LOC-09
counter/public presentation strings unchanged

R1-LOC-10
initial server-rendered AZ h1 uses adopted value

R1-LOC-11
initial server-rendered AZ greeting uses adopted value

R1-LOC-12
initial server-rendered AZ description uses adopted value

R1-LOC-13
HTML <title> remains exact code-owned "Zəfər Parkı - Wi-Fi"

R1-LOC-14
no request-time SettingsStore read

R1-LOC-15
no request-time getenv/get_settings for Stage-5 values

R1-LOC-16
portal JavaScript receives one full translation object
```

P1-02:

```text
CLOSED
```

---

# 18. P1-03 — CLOSED
# CAPPORT HTML VS JSON CONSUMER BOUNDARY

Permanent rule:

```text
PortalPresentationConfigV1
and
PortalTemplatePresentationV1

are presentation consumers ONLY
for response paths that render portal.html.
```

They are NOT CAPPORT protocol DTOs.

They are NOT CAPPORT JSON contracts.

---

# 19. EXACT HTML CONSUMERS

The following response classes MUST receive the same adopted `PortalTemplatePresentationV1`.

## 19.1 Ordinary Omada External Portal HTML

Any ordinary External Portal response path that renders:

```text
portal.html
```

uses the adopted presentation projection.

This includes normal portal-entry HTML and controlled portal HTML failure states that already use `portal.html`.

## 19.2 CAPPORT normal login HTML

For:

```text
GET /capport/login
```

when HTML is selected and client identity resolves into the common auth flow:

```text
PortalEntryHandler.open_portal(...)
→ portal.html
```

uses the same adopted projection.

## 19.3 CAPPORT discovery HTML

When `/capport/login` has not yet resolved the client and current code renders discovery mode using:

```text
portal.html
```

that HTML MUST receive the same adopted projection.

## 19.4 Controlled CAPPORT error HTML

When current CAPPORT controlled error handling renders:

```text
portal.html
```

it MUST receive the same adopted projection.

No separate hard-coded Stage-5 title/greeting/description may remain in those direct render branches.

---

# 20. EXACT NON-CONSUMERS

The following MUST NOT receive Stage-5 presentation fields.

## 20.1 CAPPORT captive-state API

```text
GET /capport/api
```

Response contract:

```text
UNCHANGED
```

Stage-5 fields:

```text
ABSENT
```

Media type:

```text
UNCHANGED
```

## 20.2 `/capport/login` explicit JSON mode

When request negotiation selects `application/json`, including:

```text
discovery JSON
AUTH_SESSION JSON
terminal discovery/error JSON
invalid-context JSON
other existing CAPPORT JSON envelopes
```

the response schemas remain:

```text
UNCHANGED
```

Stage-5 fields:

```text
ABSENT
```

No fields such as:

```text
title
greeting
description
support
phone
email
social URLs
```

may be added.

## 20.3 PortalEntryHandler structured result

```text
PortalEntryResult
```

remains Auth/session structured state.

It MUST NOT gain Stage-5 presentation fields merely to support HTML.

`prepare_portal()` is not a Stage-5 presentation consumer.

## 20.4 `/success`

```text
NON-CONSUMER
```

unchanged/code-owned.

## 20.5 Other non-portal responses

Any route that does not render `portal.html` is not a Stage-5 presentation consumer unless a later architecture explicitly admits it.

---

# 21. CAPPORT PROTOCOL INVARIANTS

Stage 5 MUST NOT change:

```text
CAPPORT application/json response schemas
CAPPORT JSON field names
CAPPORT JSON status semantics
CAPPORT captive-state semantics
CAPPORT user-portal-url semantics
CAPPORT media types
CAPPORT cache headers
CAPPORT identity resolution
CAPPORT retry/discovery protocol state
CAPPORT error codes
```

Permanent invariant:

```text
same adopted presentation for portal.html
!=
presentation fields added to CAPPORT JSON
```

---

# 22. UPDATED S5-I11

Original S5-I11 is replaced by:

```text
S5-I11-R1

Every response path that renders portal.html
uses the same immutable adopted PortalTemplatePresentationV1.

This includes:
- ordinary External Portal HTML;
- CAPPORT normal login HTML;
- CAPPORT discovery HTML rendered through portal.html;
- controlled CAPPORT error HTML rendered through portal.html.

CAPPORT JSON/API paths are non-consumers and contain zero Stage-5 presentation fields.
```

---

# 23. P1-03 ACCEPTANCE MATRIX ADDITION

```text
R1-CAP-01
ordinary External Portal HTML uses adopted title/greeting/description/support

R1-CAP-02
CAPPORT normal login HTML uses same adopted projection

R1-CAP-03
CAPPORT discovery HTML uses same adopted projection

R1-CAP-04
CAPPORT controlled error HTML using portal.html uses same adopted projection

R1-CAP-05
GET /capport/api response body unchanged

R1-CAP-06
GET /capport/api media type unchanged

R1-CAP-07
/capport/login discovery JSON contains no Stage-5 fields

R1-CAP-08
/capport/login AUTH_SESSION JSON contains no Stage-5 fields

R1-CAP-09
/capport/login terminal/error JSON contains no Stage-5 fields

R1-CAP-10
PortalEntryResult contains no presentation fields

R1-CAP-11
/success remains non-consumer

R1-CAP-12
HTML/JSON negotiation cannot leak support values into JSON envelopes
```

P1-03:

```text
CLOSED
```

---

# 24. P1-04 — CLOSED
# EXACT PUBLIC PORTAL SETTINGS SERIALIZATION

## 24.1 Group identifiers

Exactly two public group identifiers exist:

```text
branding
support
```

Mapping:

```text
PORTAL_UI_TITLE_AZ              → branding
PORTAL_UI_TITLE_RU              → branding
PORTAL_UI_TITLE_EN              → branding
PORTAL_UI_GREETING_AZ           → branding
PORTAL_UI_GREETING_RU           → branding
PORTAL_UI_GREETING_EN           → branding
PORTAL_UI_DESCRIPTION_AZ        → branding
PORTAL_UI_DESCRIPTION_RU        → branding
PORTAL_UI_DESCRIPTION_EN        → branding

PORTAL_SUPPORT_PHONE            → support
PORTAL_SUPPORT_EMAIL            → support
PORTAL_SUPPORT_WHATSAPP_URL     → support
PORTAL_SUPPORT_TELEGRAM_URL     → support
PORTAL_SUPPORT_FACEBOOK_URL     → support
```

No other group identifier is allowed in Stage 5 V1.

---

# 25. EXACT PUBLIC DESCRIPTION STRINGS

The SettingsDefinitionRegistry is the single source of these exact English API/UI metadata strings.

```text
PORTAL_UI_TITLE_AZ
Public portal title shown to guests in Azerbaijani.

PORTAL_UI_TITLE_RU
Public portal title shown to guests in Russian.

PORTAL_UI_TITLE_EN
Public portal title shown to guests in English.

PORTAL_UI_GREETING_AZ
Public welcome text shown to guests in Azerbaijani.

PORTAL_UI_GREETING_RU
Public welcome text shown to guests in Russian.

PORTAL_UI_GREETING_EN
Public welcome text shown to guests in English.

PORTAL_UI_DESCRIPTION_AZ
Public short guest description shown to guests in Azerbaijani.

PORTAL_UI_DESCRIPTION_RU
Public short guest description shown to guests in Russian.

PORTAL_UI_DESCRIPTION_EN
Public short guest description shown to guests in English.

PORTAL_SUPPORT_PHONE
Public support phone number shown to guests.

PORTAL_SUPPORT_EMAIL
Public support email address shown to guests.

PORTAL_SUPPORT_WHATSAPP_URL
Public WhatsApp support link shown to guests.

PORTAL_SUPPORT_TELEGRAM_URL
Public Telegram support link shown to guests.

PORTAL_SUPPORT_FACEBOOK_URL
Public Facebook support link shown to guests.
```

Frontend MUST NOT own a second description table.

---

# 26. EXACT PRESENTATION TYPES

```text
PORTAL_UI_TITLE_*
→ plain_text

PORTAL_UI_GREETING_*
→ plain_text

PORTAL_UI_DESCRIPTION_*
→ multiline_plain_text

PORTAL_SUPPORT_PHONE
→ telephone

PORTAL_SUPPORT_EMAIL
→ email

PORTAL_SUPPORT_WHATSAPP_URL
PORTAL_SUPPORT_TELEGRAM_URL
PORTAL_SUPPORT_FACEBOOK_URL
→ restricted_url
```

---

# 27. EXACT VALIDATION JSON — PLAIN TEXT TITLE

For every `PORTAL_UI_TITLE_*`:

```json
{
  "type": "string",
  "required": true,
  "min_length": 1,
  "max_length": 80,
  "unicode_normalization": "NFC",
  "content": "plain_text",
  "line_policy": "single_line",
  "control_characters": "forbidden",
  "bidi_controls": "forbidden"
}
```

---

# 28. EXACT VALIDATION JSON — PLAIN TEXT GREETING

For every `PORTAL_UI_GREETING_*`:

```json
{
  "type": "string",
  "required": true,
  "min_length": 1,
  "max_length": 120,
  "unicode_normalization": "NFC",
  "content": "plain_text",
  "line_policy": "single_line",
  "control_characters": "forbidden",
  "bidi_controls": "forbidden"
}
```

---

# 29. EXACT VALIDATION JSON — MULTILINE DESCRIPTION

For every `PORTAL_UI_DESCRIPTION_*`:

```json
{
  "type": "string",
  "required": true,
  "min_length": 1,
  "max_length": 400,
  "unicode_normalization": "NFC",
  "content": "plain_text",
  "line_policy": "lf_multiline",
  "max_lines": 4,
  "control_characters": "forbidden_except_lf",
  "bidi_controls": "forbidden"
}
```

No CR.

No TAB.

LF is the only admitted control character.

---

# 30. EXACT VALIDATION JSON — TELEPHONE

For `PORTAL_SUPPORT_PHONE`:

```json
{
  "type": "string",
  "required": false,
  "empty_allowed": true,
  "min_length": 0,
  "max_length": 32,
  "format": "support_phone_e164_display_v1",
  "href_scheme": "tel"
}
```

---

# 31. EXACT VALIDATION JSON — EMAIL

For `PORTAL_SUPPORT_EMAIL`:

```json
{
  "type": "string",
  "required": false,
  "empty_allowed": true,
  "min_length": 0,
  "max_length": 254,
  "format": "support_email_ascii_v1",
  "href_scheme": "mailto"
}
```

---

# 32. EXACT VALIDATION JSON — WHATSAPP

For `PORTAL_SUPPORT_WHATSAPP_URL`:

```json
{
  "type": "string",
  "required": false,
  "empty_allowed": true,
  "min_length": 0,
  "max_length": 256,
  "format": "restricted_https_url_v1",
  "scheme": "https",
  "allowed_hosts": ["wa.me"],
  "explicit_port": "forbidden",
  "userinfo": "forbidden",
  "fragment": "forbidden",
  "query_policy": "forbidden",
  "path_pattern": "/[0-9]{8,15}"
}
```

---

# 33. EXACT VALIDATION JSON — TELEGRAM

For `PORTAL_SUPPORT_TELEGRAM_URL`:

```json
{
  "type": "string",
  "required": false,
  "empty_allowed": true,
  "min_length": 0,
  "max_length": 256,
  "format": "restricted_https_url_v1",
  "scheme": "https",
  "allowed_hosts": ["t.me"],
  "explicit_port": "forbidden",
  "userinfo": "forbidden",
  "fragment": "forbidden",
  "query_policy": "forbidden",
  "path_pattern": "/[A-Za-z0-9_]{5,64}"
}
```

---

# 34. EXACT VALIDATION JSON — FACEBOOK

For `PORTAL_SUPPORT_FACEBOOK_URL`:

```json
{
  "type": "string",
  "required": false,
  "empty_allowed": true,
  "min_length": 0,
  "max_length": 512,
  "format": "restricted_https_url_v1",
  "scheme": "https",
  "allowed_hosts": ["facebook.com", "www.facebook.com"],
  "explicit_port": "forbidden",
  "userinfo": "forbidden",
  "fragment": "forbidden",
  "query_policy": "none_or_locale_only",
  "locale_pattern": "[A-Za-z]{2,3}_[A-Za-z]{2,3}",
  "path_policy": "non_empty_max_256"
}
```

---

# 35. RESTRICTED URL PORT SEMANTICS

Decision:

```text
EXPLICIT PORT IS FORBIDDEN
```

for all three social URL settings.

Therefore these are invalid:

```text
https://wa.me:443/994504174646
https://wa.me:8443/994504174646

https://t.me:443/ZaurNavi
https://t.me:8443/ZaurNavi

https://facebook.com:443/path
https://www.facebook.com:443/path
https://facebook.com:8443/path
```

Only implicit standard HTTPS origin is accepted.

Reason:

```text
the Stage-5 allowlist admits specific public service origins,
not arbitrary host+port endpoints.
```

Host comparison is against the exact admitted ASCII hostname after normal URL parsing.

Forbidden:

```text
trailing-dot host
Unicode lookalike host
userinfo
IPv4/IPv6 literal substitute
alternate port
scheme-relative URL
http
fragment
```

No silent canonical rewrite of an invalid URL into an accepted one.

---

# 36. PORTAL READ API VERSION

Read endpoint remains:

```text
GET /admin/api/v1/settings/portal
```

Canonical read API version:

```text
admin.settings.portal.v1
```

Each of the 14 settings exposes the exact metadata frozen in R1, including:

```text
group
description
presentation_type
validation
```

No frontend-owned metadata table is authoritative.

---

# 37. PORTAL MUTATION API VERSION

Mutation endpoint:

```text
POST /admin/api/v1/settings/portal/generations
```

Canonical mutation API version is:

```text
admin.settings.portal.mutation.v1
```

It is NOT:

```text
admin.settings.portal.v1
```

for mutation success/error envelopes.

---

# 38. EXACT POST SUCCESS BODY

For both changed and no-op successful Portal mutations, the JSON body contains **exactly**:

```json
{
  "api_version": "admin.settings.portal.mutation.v1",
  "request_id": "<original request UUID>",
  "scope": {
    "type": "global"
  },
  "resource": {
    "type": "guest_portal",
    "scope": "installation"
  },
  "changed": true,
  "changed_keys": [
    "PORTAL_UI_GREETING_EN"
  ],
  "configured_generation": 7,
  "effective_generation": 6,
  "activation_state": "pending_main_restart",
  "restart_required": true
}
```

Allowed top-level keys are exactly:

```text
api_version
request_id
scope
resource
changed
changed_keys
configured_generation
effective_generation
activation_state
restart_required
```

Mutation response contains NO:

```text
settings[]
fields
raw request echo
old values
new values
support values
translation values
```

The client performs a fresh GET when it needs the full read model.

---

# 39. CHANGED KEYS ORDER

`changed_keys` contains only keys whose persisted override state actually changed.

Ordering is deterministic:

```text
ascending canonical key order
```

Input JSON order is not authoritative.

No-op:

```text
changed_keys = []
```

---

# 40. HTTP STATUS SEMANTICS

## Changed mutation

If persisted override state changes:

```text
HTTP 201
changed = true
new configured generation created
activation_state = pending_main_restart
```

## Entire batch no-op

If resulting persisted override mapping equals current mapping:

```text
HTTP 200
changed = false
changed_keys = []
NO new generation
NO ordinary mutation audit row
successful idempotency receipt persisted
```

`configured_generation` remains the existing configured head.

`effective_generation` is the current durable target effective generation.

`restart_required` is exactly:

```text
configured_generation != effective_generation
```

For no-op, `activation_state` represents the current actual activation state of that configured generation under the existing Settings contract; it is NOT forcibly rewritten to `active`.

---

# 41. IDEMPOTENCY REPLAY IDENTITY

Idempotency identity remains scoped to:

```text
principal
GLOBAL scope
mutation_domain = portal
Idempotency-Key
```

Same key + same canonical request:

```text
returns the originally stored HTTP status
+
the originally stored JSON success body
```

This includes preserving the original:

```text
request_id
configured_generation
effective_generation
changed
changed_keys
activation_state
restart_required
```

Replay after later head advance MUST NOT become `412`.

Replay body is semantically identical to the original stored body.

Replay ETag is derived from the body being replayed:

```text
"settings-g<configured_generation>"
```

Same idempotency key + different canonical payload:

```text
409 idempotency_conflict
```

---

# 42. MUTATION RESPONSE HEADERS

Successful Portal mutation response:

```text
Content-Type: application/json
Cache-Control: no-store
Pragma: no-cache
ETag: "settings-g<configured_generation>"
```

This applies to:

```text
201 changed
200 no-op
successful idempotency replay
```

---

# 43. ERROR API VERSION

Portal read errors:

```text
api_version =
admin.settings.portal.v1
```

Portal mutation errors:

```text
api_version =
admin.settings.portal.mutation.v1
```

They reuse the already accepted bounded Settings error classes unless Stage-5 validation adds one of the already-contracted `validation_failed` reason codes.

No raw setting request body is returned in an error.

---

# 44. P1-04 ACCEPTANCE MATRIX ADDITION

```text
R1-API-01
all 14 keys expose exact frozen group identifier

R1-API-02
all 14 keys expose exact frozen description

R1-API-03
plain_text validation JSON exact

R1-API-04
multiline_plain_text validation JSON exact

R1-API-05
telephone validation JSON exact

R1-API-06
email validation JSON exact

R1-API-07
WhatsApp restricted_url validation JSON exact

R1-API-08
Telegram restricted_url validation JSON exact

R1-API-09
Facebook restricted_url validation JSON exact

R1-API-10
changed mutation → 201 + exact body keyset

R1-API-11
no-op → 200 + exact body keyset + changed_keys=[]

R1-API-12
mutation api_version = admin.settings.portal.mutation.v1

R1-API-13
read api_version = admin.settings.portal.v1

R1-API-14
mutation response contains no settings[]/field values

R1-API-15
idempotency replay returns original stored status/body

R1-API-16
idempotency replay after head advance does not return 412

R1-API-17
idempotency conflict → 409

R1-API-18
ETag equals response configured_generation

R1-URL-01
https://wa.me/994... accepted

R1-URL-02
https://wa.me:443/994... rejected

R1-URL-03
https://wa.me:8443/994... rejected

R1-URL-04
https://t.me/name accepted

R1-URL-05
https://t.me:443/name rejected

R1-URL-06
https://facebook.com/path accepted

R1-URL-07
https://facebook.com:443/path rejected

R1-URL-08
https://facebook.com:8443/path rejected

R1-URL-09
userinfo rejected

R1-URL-10
fragment rejected

R1-URL-11
lookalike/trailing-dot host rejected
```

P1-04:

```text
CLOSED
```

---

# 45. REPLACEMENT / ADDITIONAL INVARIANTS

The following R1 invariants are added to v0.1.

```text
S5-R1-I01
Stage-4 break-glass recovery remains operational on current Stage-5 schema v4.

S5-R1-I02
Recovery repository open is current-schema-aware, existing-only and non-migrating.

S5-R1-I03
Recovery CAS still requires exact expected configured generation.

S5-R1-I04
Recovery clears only managed secret ownership.

S5-R1-I05
Recovery preserves General, Controller and Portal ordinary overrides.

S5-R1-I06
Recovery does not decrypt/read/print the secret.

S5-R1-I07
Stage-5 adopted localization replaces exactly title/greeting/description.

S5-R1-I08
All non-admitted PORTAL_TRANSLATIONS keys remain code-owned and unchanged.

S5-R1-I09
One full immutable translation rendering object is composed at startup.

S5-R1-I10
Initial server-rendered AZ title/greeting/description use adopted values.

S5-R1-I11
HTML document <title> remains code-owned in Stage 5 V1.

S5-R1-I12
Only portal.html-rendering response paths consume Stage-5 presentation.

S5-R1-I13
CAPPORT JSON/API bodies contain zero Stage-5 presentation fields.

S5-R1-I14
CAPPORT media types remain unchanged.

S5-R1-I15
Portal read API metadata is fully server-owned and serialized.

S5-R1-I16
Portal mutation API version is admin.settings.portal.mutation.v1.

S5-R1-I17
Changed Portal mutation is HTTP 201.

S5-R1-I18
Portal no-op is HTTP 200 with no generation.

S5-R1-I19
Portal idempotency replay returns original stored status/body.

S5-R1-I20
Explicit URL port is forbidden for every admitted social URL.
```

---

# 46. R1 IMPLEMENTATION FORBIDDEN CLARIFICATIONS

In addition to the v0.1 forbidden list, Coder MUST NOT choose or implement:

```text
v3-only recovery after Stage-5 migration

automatic schema migration from the break-glass command

recovery that drops Portal overrides

recovery that requires secret decryption

request-time merge of Settings translations

browser-side merge of Settings translations

replacement of full PORTAL_TRANSLATIONS with only 3 keys

second independent JS translation object for Stage-5 values

dynamic Stage-5 HTML document <title>

Stage-5 fields in CAPPORT JSON

Stage-5 fields in CAPPORT /api payload

Stage-5 fields in PortalEntryResult

mutation response containing full setting values

implementation-selected group names

implementation-selected validation schema

implementation-selected mutation API version

accepting explicit :443 for social links

accepting arbitrary alternate HTTPS ports
```

---

# 47. UPDATED R1 DISPOSITION

```text
P1-01 =
CLOSED

P1-02 =
CLOSED

P1-03 =
CLOSED

P1-04 =
CLOSED

OPEN P0 =
0

OPEN P1 =
0
```

---

# 48. FINAL ARCHITECTURE STATUS

```text
DOCUMENT =
CAPTIVPORTAL ADMIN SETTINGS
STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS
ARCHITECTURE CONTRACT v0.1-R1

BASELINE =
main@c05d0fccfb1c0ed67a2e3fbd5d6f58ee2b2d2ed9

TREE =
59df8aa855fe094e173db611fbbdf5714c229b86

PARENT ARCHITECTURE =
v0.1

R1 TYPE =
BOUNDED NORMATIVE PATCH

STAGE-5 ALLOWLIST =
UNCHANGED / EXACT 14 KEYS

GLOBAL-ONLY =
UNCHANGED

CAPPORT CONFIGURATION MUTATION =
NO

AUTH/REDIRECT/SESSION MUTATION =
NO

SETTINGS SCHEMA =
v4

STAGE-4 BREAK-GLASS ON v4 =
REQUIRED / PRESERVED

LOCALIZATION COMPOSITION =
ONE STARTUP-DERIVED FULL IMMUTABLE PORTAL TEMPLATE PROJECTION

INITIAL AZ BRANDING =
ADOPTED STAGE-5 VALUES

HTML DOCUMENT TITLE =
CODE-OWNED / UNCHANGED

CAPPORT HTML portal.html PATHS =
STAGE-5 PRESENTATION CONSUMERS

CAPPORT JSON/API =
NON-CONSUMERS / UNCHANGED

PORTAL READ API =
admin.settings.portal.v1

PORTAL MUTATION API =
admin.settings.portal.mutation.v1

MUTATION CHANGED =
201

MUTATION NO-OP =
200

IDEMPOTENCY REPLAY =
ORIGINAL STORED STATUS + BODY

SOCIAL URL EXPLICIT PORT =
FORBIDDEN

OPEN_ARCH_P0 =
0

OPEN_ARCH_P1 =
0

ARCHITECTURE =
DRAFT FOR TECH LEAD RE-REVIEW

IMPLEMENTATION TASK =
HOLD

CODER =
HOLD

PRODUCTION CHANGE =
NO
```

---

# 49. NEXT GOVERNANCE STEP

```text
Tech Lead
→ re-review v0.1 + this v0.1-R1 bounded normative patch

if ARCHITECTURE PASS:
→ Technical Developer may prepare exact Stage-5 implementation TASK

until then:
IMPLEMENTATION TASK = HOLD
CODER = HOLD
PRODUCTION CHANGE = NO
```
