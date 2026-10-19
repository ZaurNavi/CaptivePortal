# TASK-ADMIN-SETTINGS-02 — TECH LEAD BINDING SCOPE ADDENDUM TL-AS02-F1

**Task:** TASK-ADMIN-SETTINGS-02 — OMADA CONTROLLER READ MODEL  
**Status:** FINAL / BINDING  
**Baseline HEAD:** `9ca25fd3dc9d552d446be4669f2e67247dcb7a1b`  
**Baseline TREE:** `0ef5c4555fa254a8904f35e19c0570a5bbe8abe7`

---

## 1. Scope blocker disposition

Coder correctly identified an additional current-source call path:

```text
app/web/web.py:create_app(...)
→ if controller is None
→ create_controller()
```

The original authorized-file list omitted `app/web/web.py`.

This is a real implementation blocker because TASK-ADMIN-SETTINGS-02 makes:

```text
create_controller(runtime_config)
```

mandatory and forbids a production-reachable fallback:

```text
create_controller()
→ OmadaProvider()
→ get_settings()
```

---

## 2. Scope amendment

The following existing production file is now AUTHORIZED for bounded modification:

```text
app/web/web.py
```

No other scope expansion is implied.

Affected existing/new tests required to prove this fallback contract are also authorized.

---

## 3. Exact required fallback semantics

Preserve the existing public `create_app(..., controller=None, settings=None, ...)` compatibility boundary.

Do NOT remove the `controller=None` fallback merely to satisfy the new factory signature.

Required logic:

```text
if settings is None:
    settings = get_settings()

...

if controller is None:
    runtime_config = build/resolve OmadaControllerRuntimeConfig
                     FROM THAT SAME LOCAL settings MAPPING
    controller = create_controller(runtime_config)
```

Binding rules:

1. The fallback MUST use the already-resolved local `settings` mapping.
2. It MUST NOT call `get_settings()` a second time for Controller creation.
3. It MUST NOT read provider private fields.
4. It MUST NOT create a second configuration semantics/validator.
5. It MUST use the same canonical Omada runtime-config builder/validator used by `run.py`.
6. `create_controller(runtime_config)` remains mandatory.
7. `OmadaProvider(runtime_config)` remains mandatory.
8. No production-reachable `OmadaProvider()` / `create_controller()` zero-argument compatibility fallback is allowed.

---

## 4. Production path remains authoritative

Normal production composition remains:

```text
run.py
→ base_settings = get_settings()
→ Settings bootstrap
→ runtime settings
→ OmadaControllerRuntimeConfig
→ create_controller(runtime_config)
→ create_app(
       controller=shared_controller,
       settings=runtime_settings,
       ...
   )
```

Therefore the `app/web/web.py` automatic Controller fallback is a compatibility/composition fallback, not a second production configuration owner.

When `run.py` injects `controller`, `create_app()` MUST NOT rebuild Controller configuration.

---

## 5. Runtime-config vs provenance clarification

The secret-bearing:

```text
OmadaControllerRuntimeConfig
```

may be constructed from the already-resolved `settings` mapping without needing Admin-read provenance.

Provenance used by:

```text
OmadaControllerPublicConfigSnapshot.effective_source
```

remains owned by the main Stage-2 startup/read-model composition and the captured startup environment-name set.

Do NOT make `app/web/web.py` fabricate a Controller public snapshot merely because it must create a fallback provider.

Do NOT make the fallback inspect `os.environ` solely to support the Admin Controller read model.

The fallback's responsibility is only:

```text
same settings
→ same validation
→ same OmadaControllerRuntimeConfig
→ shared provider semantics
```

---

## 6. Portal/Auth semantic freeze

Modification of `app/web/web.py` is limited to Controller construction wiring.

Forbidden changes in this file under TL-AS02-F1:

```text
Portal route semantics
AuthSession/AuthWorker semantics
CAPPORT semantics
webhook behavior
portal counter behavior
public traffic behavior
device-fingerprint portal behavior
request/response contracts
token behavior
Omada network request behavior
```

Existing injection behavior must remain:

```text
controller supplied
→ use supplied controller exactly

controller None
→ construct exactly one controller from canonical runtime config
```

---

## 7. Required tests added to the TASK gate

Coder must prove:

```text
F1-01 create_app(controller=None, settings=<mapping>)
      builds canonical OmadaControllerRuntimeConfig from that mapping.

F1-02 create_app fallback invokes create_controller(runtime_config)
      exactly once.

F1-03 create_app fallback does NOT perform a second get_settings()
      when settings were explicitly supplied.

F1-04 create_app(settings=None, controller=None)
      performs the existing create_app settings fallback once,
      then derives Controller runtime config from that same mapping.

F1-05 create_app(controller=<injected>)
      does NOT build Controller runtime config
      and does NOT call create_controller().

F1-06 existing Portal/Auth/CAPPORT tests remain compatible.

F1-07 no zero-argument production create_controller() call remains
      in app/web/web.py or run.py.
```

Repository search after implementation must show no production call path equivalent to:

```text
create_controller()
```

for the Omada provider composition.

Test-local helper functions named `create_controller` are not violations.

---

## 8. Final disposition

```text
SCOPE BLOCKER =
RESOLVED

APP/WEB/WEB.PY =
AUTHORIZED — BOUNDED CONTROLLER WIRING ONLY

CREATE_APP FALLBACK =
PRESERVED

SECOND SETTINGS READ =
FORBIDDEN

PORTAL/AUTH SEMANTICS CHANGE =
FORBIDDEN

ARCHITECTURE RETURN =
NOT REQUIRED

CODER =
GO / RESUME TASK-ADMIN-SETTINGS-02

PRODUCTION =
NO CHANGE
```
