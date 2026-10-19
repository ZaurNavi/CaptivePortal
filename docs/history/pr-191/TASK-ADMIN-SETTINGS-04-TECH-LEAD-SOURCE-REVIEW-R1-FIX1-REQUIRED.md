# TASK-ADMIN-SETTINGS-04 — TECH LEAD SOURCE REVIEW R1
## FIX1 REQUIRED / CANDIDATE HOLD

**Task:** `TASK-ADMIN-SETTINGS-04`  
**Reviewed candidate:** `698ba5b03887c90181cf78d63e156a7a965fe802`  
**Parent:** `430acb4f235a606f05acc78e7f983824e4448644`  
**Tree:** `6933ebad3cf83ea9529744f0ad73f1c4697dbedc`  
**Baseline tree:** `06e0edf54f37e4b9a3d4c3b8f3a1f37b181c3b3b`  
**Disposition:** `HOLD / FIX1 REQUIRED`

## 1. Artifact identity / handoff integrity

Independently verified from the isolated Settings-04 worktree:

```text
HEAD=698ba5b03887c90181cf78d63e156a7a965fe802
PARENT=430acb4f235a606f05acc78e7f983824e4448644
TREE=6933ebad3cf83ea9529744f0ad73f1c4697dbedc
BRANCH=feature/admin-settings-04-controller-secret-management
WORKTREE=CLEAN
CHANGED_FILES=40
ADDITIONS=1730
DELETIONS=96
```

Uploaded full patch independently verified:

```text
PATCH_BYTES=159300
PATCH_SHA256=1594fe05a834692755a0b9565d3b679b915e4c4f10ecabd3dcc6caec7f210281
```

GitHub `main` remains the accepted rebased Stage-4 baseline:

```text
430acb4f235a606f05acc78e7f983824e4448644
```

No baseline drift.

## 2. Scope Extension 01

PASS.

The former temporary validation snapshot containing raw `client_secret` is removed.

`SettingsValidationService.validate()` now accepts the secret through the separate keyword-only resolution boundary and invokes the canonical Controller builder with:

```python
build_omada_runtime_config(
    snapshot.values,
    secret_resolution=secret_resolution,
)
```

No fallback reads raw `client_secret` from the ordinary Settings snapshot.

Bootstrap and ordinary Settings mutation callers supply the resolution separately.

## 3. Major accepted implementation areas

Source review found the following core Stage-4 directions correctly implemented:

```text
schema v3 / v2->v3 migration direction
encrypted secret table + generation binding
fixed-size AES-GCM ciphertext framing
HKDF-separated encryption/idempotency keys
HMAC idempotency fingerprint
secret-free ordinary Settings overrides
common global generation / ETag
managed > deployment fallback ownership
restart-based activation
post-adoption provider-I/O ordering retained
Controller read model v3
independent secret-write capability
write-only HTTP mutation route
safe secret UI fields
logical live-version GC
break-glass command boundary
cryptography>=3.4.8 declaration
```

These are not being reopened by FIX1.

## 4. P1-01 — required `ControllerSecretDefinitionV1` boundary is missing

The accepted implementation contract requires one narrow immutable code-owned secret definition equivalent to:

```text
ControllerSecretDefinitionV1

key=OMADA_CLIENT_SECRET
scope=global
secret_class=write_only_secret
apply_requirement=main_service_restart
activation_target=captive-portal.service
```

Independent source search found no:

```text
ControllerSecretDefinitionV1
write_only_secret
```

under `app/`.

The candidate instead hardcodes the secret key/apply target metadata in several Stage-4 paths.

Required FIX1:

- add the exact narrow immutable definition boundary;
- keep it outside `SettingsDefinitionRegistry`;
- keep the ordinary registry at exactly 15 definitions;
- use the definition as the canonical Stage-4 metadata owner where applicable;
- add a focused test proving its exact fields and that `OMADA_CLIENT_SECRET` remains absent from the ordinary registry.

This is a contract-completeness P1, not an architecture redesign.

## 5. P1-02 — Admin safe-metadata boundary currently retains raw deployment secret

Current bootstrap constructs:

```text
ControllerSecretRepository(..., deployment_secret=base_settings["client_secret"], ...)
```

and that repository retains:

```text
self._deployment = OmadaClientSecretResolution(raw_secret, ...)
```

The same raw-bearing repository object is then exposed as:

```text
SettingsAdminContext.secret_metadata_service
```

and passed into:

```text
ControllerConfigurationReadService.secret_metadata_service
```

The accepted TASK explicitly requires:

```text
Do not expose raw secret-bearing objects on Admin runtime.

Admin runtime may receive:
- secret mutation service
- secret store safe state/provider
- safe configured secret metadata boundary

but NOT OmadaClientSecretResolution.value.
```

The current metadata boundary is therefore not actually secret-free.

Required FIX1:

- separate safe Controller-secret metadata projection from the raw-bearing mutation/startup boundary;
- Admin read/runtime wiring must receive an object containing only safe facts required for:
  - binding/source/presence/pending computation;
  - secret-store availability;
- that safe metadata boundary must not retain the deployment secret or an `OmadaClientSecretResolution` containing its value;
- raw deployment fallback material may remain only inside an accepted secret-bearing startup/mutation boundary;
- ordinary Controller GET must still perform no secret decrypt.

Add a structural/sentinel test proving the Admin metadata boundary does not retain the raw disposable secret.

## 6. P1-03 — break-glass audit principal uses environment-spoofable identity

Current recovery implementation defaults to:

```python
getpass.getuser
```

for:

```text
principal_name
```

This does not meet the accepted requirement:

```text
principal_name = current OS operator identity
Use a Linux OS identity source suitable for production.
```

Independent proof in the Linux test environment:

```text
LOGNAME=spoofed_operator
USER=spoofed_operator

getpass.getuser()                    -> spoofed_operator
pwd.getpwuid(os.geteuid()).pw_name  -> actual effective OS user
```

Thus an environment variable can falsify recovery audit identity.

Required FIX1:

- use an authoritative Linux effective-UID identity source, e.g.
  `pwd.getpwuid(os.geteuid()).pw_name`;
- keep the identity provider injectable for tests;
- do not trust `USER`, `LOGNAME`, `LNAME`, or `USERNAME` as the production authority;
- add a regression proving spoofed environment names do not change the default recovery audit principal.

## 7. P1-04 — existing Controller browser regression is broken; mandatory Stage-4 UI behavior is not dynamically exercised

Tech Lead independently ran:

```text
tests/admin_web/test_controller_settings_stage3_frontend.py
```

on the candidate.

Result:

```text
8 FAILED
```

All eight scenarios fail because the real Stage-4 `controller_settings.js` unconditionally expects the new secret DOM nodes, while the existing executable Node harness still models the Stage-3 DOM/API and supplies no `controller-secret-*` elements:

```text
TypeError:
secretReplace.addEventListener(...)
Cannot read properties of undefined
```

The exact baseline `430acb4...` independently returns:

```text
8 PASSED
```

for the same test file.

Therefore these are candidate-introduced regression failures, not baseline debt.

Also, the new Stage-4 UI test currently uses primarily static source-string assertions. The implementation TASK requires behavior coverage for secret replace/clear/mismatch/cancel/success/errors/412/network-uncertain retry.

Required FIX1:

- update the existing executable Controller JS harness to Controller v3 and the new DOM while preserving all Stage-3 non-secret edit scenarios;
- existing `test_controller_settings_stage3_frontend.py` must return 8 PASS;
- add/extend executable JS behavior scenarios for:
  - secret writer vs ordinary writer/read-only user;
  - two secret inputs;
  - mismatch no POST;
  - replace confirmation;
  - clear confirmation;
  - cancel cleanup;
  - success cleanup + GET;
  - definitive HTTP error cleanup;
  - 412 reload + retry-key discard;
  - uncertain network cleanup + same-operation key retry;
- do not replace executable behavior evidence with source-string assertions alone.

## 8. P1-05 — `secret_store_state=available` does not prove AES-GCM primitive initialization

Accepted contract requires `available` only when:

```text
schema/integrity
DB filesystem security
master-key security/size
crypto primitive initialization
```

Current:

```text
ControllerSecretRepository.available()
→ keys()
→ derive_keys()
```

and `derive_keys()` initializes SHA256/HKDF, but does not import/instantiate `AESGCM`.

Therefore the read model can report:

```text
secret_store_state=available
```

without proving the encryption primitive required by secret mutation is actually initializable.

Required FIX1:

- make secret-store availability initialize/validate all required Stage-4 crypto primitives, including AESGCM with the derived encryption key;
- no encryption/network I/O is required merely to test primitive initialization;
- map failure to safe unavailable state;
- add a focused regression for crypto-initialization failure.

## 9. TL-FIX1-B1 — bind uncertain idempotency key to one operation

Current browser code retains one global:

```text
uncertainKey
```

after an uncertain network result.

If a replace becomes network-uncertain and the operator then performs clear, the old replace key can be reused for a different operation, correctly producing a server-side idempotency conflict but creating an avoidable broken retry workflow.

The accepted contract allows retaining the key only for the unresolved retry workflow.

FIX1 must bind retained retry identity to its operation:

```text
uncertainKey
+
uncertainOperation
```

or equivalent.

Reuse the old key only when retrying the same operation.

Changing operation, explicit cancel, stale-412, or any definitive server result must discard the old retry identity.

Cover this in the executable UI test.

## 10. Independent Tech Lead full repository regression

Per Owner process, Tech Lead — not Coder — ran the full repository suite on the exact immutable candidate.

Candidate result:

```text
5978 passed
1 skipped
26 failed
```

Tech Lead then created a detached exact-baseline worktree at:

```text
430acb4f235a606f05acc78e7f983824e4448644
TREE=06e0edf54f37e4b9a3d4c3b8f3a1f37b181c3b3b
```

and reran the non-frontend failure set.

Result:

```text
18 baseline failures reproduced
```

They include existing/current-main failures in:

```text
Admin Home traffic ordering
two historical-traffic EXPLAIN-plan expectations
Client-Hints probe tests
WSL artifact-identity runtime tests
```

Those 18 are not assigned to Stage-4 Coder as FIX1 work.

The eight Controller frontend failures are different:

```text
BASELINE: 8 PASS
CANDIDATE: 8 FAIL
```

Therefore Stage-4 introduces exactly the new full-regression delta identified in P1-04.

After FIX1, Tech Lead will rerun broad/full regression and require no Stage-4-introduced failures relative to exact baseline.

## 11. Static checks

Independently rechecked:

```text
git diff --check = PASS
node --check app/admin_web/static/controller_settings.js = PASS
```

Syntax/static validity does not clear the behavioral/frontend regression above.

## 12. Gate

```text
ARTIFACT_IDENTITY=PASS
PATCH_IDENTITY=PASS
BASELINE_DRIFT=NO
SCOPE_EXTENSION_01=PASS

OPEN_P0=0
OPEN_P1=5

P1-01=missing ControllerSecretDefinitionV1
P1-02=raw-bearing repository exposed as Admin metadata boundary
P1-03=recovery OS identity is environment-spoofable
P1-04=8 new Controller frontend regression failures / dynamic UI evidence incomplete
P1-05=secret-store availability does not validate AESGCM initialization

TL-FIX1-B1=uncertain retry key must be operation-bound

SOURCE_REVIEW=HOLD
CANDIDATE=NOT_ACCEPTED
FIX1=REQUIRED

CODER_TARGETED_FIX_TESTS=GO
FULL_REPOSITORY_PYTEST=TECH_LEAD ONLY

PUSH=HOLD
PR=HOLD
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO

PRODUCTION=STAGE3 / NO CHANGE
```

## 13. FIX1 candidate rule

Continue from the preserved clean candidate:

```text
FIX1_BASE=
698ba5b03887c90181cf78d63e156a7a965fe802
```

Do not reset/rewrite the accepted implementation commit.

Create one additional local FIX1 commit on the same branch.

Final FIX1 handoff must include:

```text
FIX1_COMMIT
FIX1_PARENT=698ba5b03887c90181cf78d63e156a7a965fe802
FIX1_TREE
clean worktree
changed files/stat
full original BASE 430acb4... -> FIX1 candidate patch
patch bytes/SHA256/reverse-check
targeted FIX1 commands/results
no full repository pytest
no push/PR/deploy
```
