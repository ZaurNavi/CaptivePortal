# TASK-ADMIN-SETTINGS-01 — TECH LEAD FINAL BINDING ADDENDUM TL-F1..TL-F5

**Project:** CaptivPortal  
**Area:** Admin UI → Settings  
**Applies to:** `TASK-ADMIN-SETTINGS-01 — SETTINGS FOUNDATION + SAFE ADMIN SETTINGS V1 — R1 FINAL CANDIDATE`  
**Status:** FINAL / BINDING / TECH LEAD ACCEPTED  
**Coder:** GO / AUTHORIZED FOR IMPLEMENTATION  
**Production:** NO CHANGE  
**Systemd:** NO ACTION  

**Accepted baseline:**

```text
HEAD=9af1cb158bfcfcb31d441caf71061c9aa2888b85
TREE=4850e322a4286880a32dbd995121a85bc85c9e99
```

The authoritative implementation contract is:

```text
TASK-ADMIN-SETTINGS-01 R1 FINAL CANDIDATE
+
THIS TL-F1..TL-F5 BINDING ADDENDUM
```

Together:

```text
FINAL / TECH LEAD ACCEPTED FOR CODER IMPLEMENTATION
```

If HEAD or TREE differs when Coder starts:

```text
STOP
→ report observed HEAD/TREE
→ Tech Lead baseline reconciliation
```

---

# TL-F1 — BOOTSTRAP GENERATION 0 SYSTEM IDENTITY

Generation `0` metadata is frozen exactly as:

```text
generation_id = 0
parent_generation_id = null
scope_type = "global"
created_at_utc = <canonical current UTC at schema initialization>
created_by_principal_type = "system"
created_by_principal_name = "settings_bootstrap"
request_id = null
```

Its persisted override set is empty.

Bootstrap target state:

```text
target = "captive-portal.service"
effective_generation = null
updated_at_utc = null
```

Generation `0`:

- is physical;
- is immutable;
- produces no `settings_mutation_audit` rows;
- produces no `settings_idempotency` row;
- is not attributed to `platform_operator`;
- MUST NOT use any alternate synthetic operator identity.

---

# TL-F2 — GLOBAL SETTINGS TEMPLATE / SCRIPT ISOLATION

`GET /admin/settings` is GLOBAL and MUST NOT synthesize Site context merely to reuse the existing Site-oriented Admin shell.

Required:

- no `AdminSiteContextResolver` call;
- no `resolver.default()` call;
- no synthetic `site_id`;
- no synthetic `default_site_id`;
- no fake `data-site-id`;
- no fake `/admin/api/v1/sites/<site_id>` API base;
- no Site authorization for Settings;
- authorization remains `authorize_global(...)`.

Use an explicit GLOBAL presentation branch in the already-authorized:

```text
app/admin_web/templates/admin/base.html
```

or equivalent behavior limited to authorized template files.

Return-to-product/Home navigation may point to:

```text
/admin/
```

and allow the existing `/admin/` route to perform its normal Site redirect.

The Settings page itself MUST NOT resolve a Site.

---

# TL-F3 — DO NOT RUN LEGACY `admin.js` AS SETTINGS CONTROLLER

Current:

```text
app/admin_web/static/admin.js
```

remains the controller for existing Site-scoped Admin pages and MUST NOT become the Settings controller.

For:

```text
page.key == "settings"
```

required:

- load dedicated `app/admin_web/static/settings.js`;
- existing `admin.js` is not required for Settings behavior;
- preferably do not load `admin.js` on Settings page at all;
- Settings page must not require dummy Site/page/pagination DOM merely to keep `admin.js` from failing.

Existing non-Settings pages continue loading `admin.js` unchanged.

`app/admin_web/static/admin.js` remains:

```text
DO NOT MODIFY
```

Focused UI coverage must prove:

```text
Settings page
→ settings.js present

Settings page
→ no dependency on Site-scoped admin.js runtime

ordinary existing Site page
→ admin.js behavior/loading unchanged
```

---

# TL-F4 — ONE EXISTING TEST MODIFICATION EXCEPTION

R1 states no existing test file modification is authorized.

One exact exception is pre-authorized, ONLY if required by the actual diff:

```text
tests/visitor_registry/test_snapshot_runtime.py
```

Reason:

its existing fake:

```text
create_app(*, controller, visitor_snapshot_collector)
```

models the old production factory signature and may not accept the new explicit:

```text
settings=settings
```

production injection.

Allowed modification is ONLY:

- update the test double to accept `settings=...`;
- update assertions needed to verify legitimate production settings injection.

Forbidden:

- adding production `inspect.signature()` compatibility behavior merely to accommodate this old test double;
- modifying any other existing test file without Tech Lead decision.

For any OTHER existing test file requiring source modification:

```text
STOP
→ report exact file/test/reason
→ Tech Lead decision
```

Existing tests may be RUN without modification.

---

# TL-F5 — STRICT JSON + MUTATION SUCCESS `settings` RESPONSE

## A. Strict JSON duplicate-member handling

Settings mutation JSON is strict.

Reject as:

```text
400 invalid_request
```

any JSON object containing duplicate member names, including:

```text
duplicate top-level "changes"
duplicate "key"
duplicate "operation"
duplicate "value"
```

Do NOT rely on normal last-member-wins JSON parsing.

Also reject non-standard numeric constants:

```text
NaN
Infinity
-Infinity
```

No parser extension may accept them.

## B. Mutation success `settings` field

For both:

```text
201 changed=true
200 changed=false
```

the success response field:

```text
settings
```

means:

```text
the complete ordered 12-item SettingReadModelV1 projection
as it existed for the accepted mutation result
```

Ordering is deterministic:

```text
canonical SettingsDefinitionRegistry order
```

The idempotency record MUST store enough of the original successful response to reproduce that exact representation.

A later idempotent replay returns the stored original success representation even when current:

- configured generation;
- effective generation;
- activation state;
- Settings values

have advanced.

The browser/UI performs a fresh GET after an ordinary successful Save to retrieve current state separately.

---

# IMPLEMENTATION AUTHORIZATION

Coder must use an isolated worktree from the exact accepted baseline.

Before source modification:

```bash
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Required:

```text
HEAD=9af1cb158bfcfcb31d441caf71061c9aa2888b85
TREE=4850e322a4286880a32dbd995121a85bc85c9e99
```

First implementation round:

```text
COMMIT = NO
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
PRODUCTION TEST = NO
SERVICE RESTART = NO
```

Coder implements only the files/scopes authorized by R1 plus the single TL-F4 test exception.

Coder runs only:

- R1 focused verification;
- exact directly affected existing tests;
- mandatory `compileall`;
- mandatory `git diff --check`.

Coder returns the complete R1 first-handoff evidence.

---

# CURRENT STATE

```text
TASK-ADMIN-SETTINGS-01
= PASS

TASK R1 + TL-F1..TL-F5
= FINAL / TECH LEAD ACCEPTED

ARCHITECT
= NO ACTION

TECHNICAL DEVELOPER SETTINGS
= NO FURTHER REVISION REQUIRED

CODER
= GO / AUTHORIZED FOR IMPLEMENTATION

COMMIT
= NO

PUSH
= NO

PR
= NO

PRODUCTION
= NO CHANGE

SYSTEMD
= NO ACTION
```

Next:

```text
Coder isolated-worktree implementation
→ focused verification
→ source/diff handoff
→ Tech Lead review
```
