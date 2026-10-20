# WEB-UX-PACK-02 / R2 — local implementation handoff

STATUS = READY_FOR_SOURCE_REVIEW; ASSET_WHITESPACE_DECISION_REQUIRED

Implementation is not committed or published. Source review / Owner acceptance remains pending.

## Identity

- Workspace: `C:\CaptivPortal-Lab\coder-task05-identity-session`
- Baseline / current HEAD: `c8d8d620dfed06caee92a498b891bf2faa37a6a9`
- Baseline / current HEAD tree: `be3470c378180aa215d527c6de6b686583ae0d79`
- origin/main was fetched and verified against this baseline before implementation.
- Worktree: DIRTY — exactly the review candidate, 22 changed paths below. New files have intent-to-add entries so the complete patch includes them; no files are staged as a publication commit.
- Implementation commit: NONE.

Input handoff ZIP: `C:\Users\Zaur Navi\Downloads\WEB-UX-PACK-02_CODER_HANDOFF_R2.zip`

Input ZIP SHA256: `983e08081786365fcfd1f14dccce5671aea4d427dcb96e84f41a5ebbace1e448`

## Complete replacement review patch

[WEB-UX-PACK-02_R2.patch](C:/CaptivPortal-Lab/artifacts/WEB-UX-PACK-02_R2.patch)

- Format: exact baseline-to-worktree unified diff, binary capable, full-index.
- Bytes: `98566`
- SHA256: `06b63816f61abf13d94353d0e74afe1e3bddb198326c131ea09333eec1fb6b83`
- Reverse-apply check: PASS (check only; patch was not reverse-applied).
- Aggregate: `22 files changed, 809 insertions(+), 131 deletions(-)`.

## Implemented

- Shared exact four-field Type projection; icon choice depends only on state/status/canonical identity, never display text or Controller guesses.
- Six original approved Type SVGs, 22×22 wrapper and image; exact title/accessible label, decorative inner image.
- Home Type icons; existing effective Platform precedence and Android icon-only treatment retained.
- Devices Type before Platform; Android icon plus original visible text. Raw Controller fields and Device Card presentation remain separate and unchanged for valid data.
- Devices enrichment on both context-enabled and legacy paths, Site-scoped to returned page MACs.
- Independent Device Inventory API/card: Site snapshot + non-null-device-id Visit population, unique device_id, earliest evidence timestamp, single evaluation clock, existing Registry IANA timezone. Search/Clear/Load more do not reload inventory; initial load and Refresh do. Failure is card-local.
- Single Home AP identity roster with exact MAC joins for client counts and traffic. No competing standalone Devices-by-AP / Traffic-by-AP cards or traffic pagination controls.
- AP bars use all available summary buckets for scaling. Missing matching count is zero only for an available client source; unavailable source shows neutral track and em dash. AP Unknown appears once above AP pagination.
- Traffic pages drain sequentially under one refresh generation; no partial-chain acceptance; stale generation/page failures cannot publish a partial map. Aggregate Traffic Now semantics, arrows and colors are unchanged.
- Desktop / intermediate / mobile Devices layouts; mobile retains the existing three-column shell and the Type → Platform → Activity → Stats detail order. No new feature flags.
- Relevant README/Admin Web documentation updated; local screenshots are synthetic visual QA, not production evidence.

## Authoritative TechLead refinement implemented

```text
MAX_PRODUCTION_READ_MACS = 250 (UNCHANGED)
DEVICES PAGE LIMIT = UNCHANGED (existing maximum 500)
MAX CHUNKS PER PAGE = 2
MAX MACS PER CHUNK = 250
NO N+1
NO PAGE LIMIT REDUCTION
NO GLOBAL READ-LIMIT INCREASE
NO SYNTHETIC UNAVAILABLE DUE ONLY TO PAGE SIZE
```

Exact bounded-batch cases exercised: page sizes 0, 100, 250, 251 and 500.

## Verification

Python: `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe` (3.10.11).

External pycache: `C:\CaptivPortal-Lab\tmp\web-ux-pack-02-pyc`.

Final narrow command, executed from the workspace:

```text
python -m pytest -q
  tests/admin_web/test_web_ux_pack_02.py
  tests/admin_web/test_device_fingerprint_presentation.py
  tests/admin_web/test_device_fingerprint_frontend.py
  tests/admin_web/test_query_service.py
  tests/admin_web/test_device_gateway.py
  tests/admin_web/test_admin_ui_frontend.py
  tests/admin_web/test_home_live.py
  tests/admin_web/test_home_traffic.py
  tests/admin_web/test_routes.py
  tests/admin_web/test_device_current_context_frontend.py
  tests/admin_web/test_runtime.py
  --basetemp C:\CaptivPortal-Lab\tmp\web-ux-pack-02-final
  --junitxml C:\CaptivPortal-Lab\artifacts\WEB-UX-PACK-02_R2-tests.xml
```

- R2-specific suite: 60 passed.
- Direct compatibility suites: 242 passed.
- Combined final result: **302 passed / 0 skipped / 0 failed / 0 errors**, 17.79 seconds.
- [Exact JUnit results](C:/CaptivPortal-Lab/artifacts/WEB-UX-PACK-02_R2-tests.xml).
- compileall on changed Python modules/tests, external pycache: PASS.
- `node --check app/admin_web/static/admin.js`: PASS.
- Six supplied SVG SHA256 identities and XML validity: PASS.
- Existing Android SVG unchanged: `2f2411f1f05522e90049f8cbb06105fb553057efeadf772cdcc3ae24bbc8a6cc`.
- Code/document/test diff-check excluding supplied SVG assets: PASS.
- **Full candidate diff-check: FAIL (exit 2), only five pre-existing asset-pack whitespace lines**, detailed below.
- Full repository suite / Central Lab: NOT RUN.

## Asset-pack consistency decision required

The following supplied assets contain a whitespace-only line 11. These exact source bytes were preserved, as required; no asset was normalized:

```text
app/admin_web/static/icons/device-types/type-laptop.svg:11
app/admin_web/static/icons/device-types/type-no-result.svg:11
app/admin_web/static/icons/device-types/type-smartphone.svg:11
app/admin_web/static/icons/device-types/type-tablet.svg:11
app/admin_web/static/icons/device-types/type-unresolved.svg:11
```

TechLead copy/paste:

> WEB-UX-PACK-02 R2 implementation and 302 narrow tests are complete. Full diff-check reports only five trailing-whitespace lines already present in the approved SVG pack. Exact approved SVG SHA256 values are preserved. Please authorize either an asset-only whitespace exception while retaining exact hashes, or asset normalization with new approved hashes. No asset modification was made independently. Commit/push/PR remain NO.

## Materialized visual evidence

Local disposable synthetic fixture only; no production database/service/access. Browser verification used the actual repository templates/CSS/JS and list/API composition, with synthetic read sources.

- [Home desktop — all six Type states, Platform treatments, Traffic Now, unified AP roster](C:/CaptivPortal-Lab/artifacts/web-ux-pack-02-home-desktop.jpg).
- [Devices desktop — Inventory, Type/Platform, normal rows](C:/CaptivPortal-Lab/artifacts/web-ux-pack-02-devices-desktop.jpg).
- [Devices mobile — one-column Inventory](C:/CaptivPortal-Lab/artifacts/web-ux-pack-02-devices-mobile.jpg).
- [Devices mobile rows — Type/Platform/Activity/Stats order](C:/CaptivPortal-Lab/artifacts/web-ux-pack-02-devices-mobile-rows.jpg).

Verified at 1600px, 1280px and 390px viewport widths: no horizontal overflow; Type wrappers/images 22×22. Search reduced the list to one exact MAC without changing Site inventory; Clear restored the list; Refresh requested inventory independently. Temporary browser viewport reset, preview tab closed and disposable server stopped.

Visual checks confirmed icon sizing, responsive layout and one AP identity owner; final aesthetic/product acceptance remains Owner-controlled.

## Exact changed-file inventory (`git diff --name-status`)

```text
M README.md
M app/admin_web/device_fingerprint_presentation.py
M app/admin_web/device_gateway.py
M app/admin_web/query_service.py
M app/admin_web/routes.py
M app/admin_web/runtime.py
M app/admin_web/static/admin.css
M app/admin_web/static/admin.js
A app/admin_web/static/icons/device-types/type-laptop.svg
A app/admin_web/static/icons/device-types/type-no-result.svg
A app/admin_web/static/icons/device-types/type-smartphone.svg
A app/admin_web/static/icons/device-types/type-tablet.svg
A app/admin_web/static/icons/device-types/type-unavailable.svg
A app/admin_web/static/icons/device-types/type-unresolved.svg
M app/admin_web/templates/admin/devices.html
M app/admin_web/templates/admin/home.html
M docs/modules/admin-web.md
M tests/admin_web/test_admin_ui_frontend.py
M tests/admin_web/test_device_fingerprint_presentation.py
M tests/admin_web/test_home_traffic.py
M tests/admin_web/test_query_service.py
A tests/admin_web/test_web_ux_pack_02.py
```

## Governance / boundary

```text
COMMIT = NO
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
PRODUCTION_ACCESS = NO
PRODUCTION_ACTION = NO
CLASSIFIER/FUSION/AUTH/CAPPORT_CHANGES = NO
DB_SCHEMA_OR_MIGRATION_CHANGE = NO
DEVICE_CARD_TEMPLATE_CHANGE = NO
GLOBAL_FINGERPRINT_READ_LIMIT_INCREASE = NO
PAGE_LIMIT_REDUCTION = NO
TEMP_DB/PYCACHE/SCREENSHOT/PREVIEW_ARTIFACTS_IN_PATCH = NO
KNOWN_REVIEW_BLOCKER = supplied SVG whitespace / exact-byte preservation decision
```
