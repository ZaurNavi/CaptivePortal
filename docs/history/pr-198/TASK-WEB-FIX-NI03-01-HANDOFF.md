# TASK-WEB-FIX-NI03-01 — Implementation handoff

STATUS=READY_FOR_TECH_LEAD_REVIEW
BASE_HEAD=6a054130d7b43598549e3d4c14434b08d19c3e7b
BASE_TREE=ce527d665ab842fb6e7dd2dc4b78a3b0901a1c21
COMMIT=8257808fd972c859e947ae813455a954663d024b
PARENT=6a054130d7b43598549e3d4c14434b08d19c3e7b
TREE=d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
BRANCH=fix/web-ni03-network-protocol-presentation
WORKTREE=CLEAN
WORKTREE_PATH=C:/CaptivPortal-Lab/coder-web-fix-ni03-01

## Changes

Only three authorized files changed; 175 insertions / 13 deletions:

- [admin.css](C:/CaptivPortal-Lab/coder-web-fix-ni03-01/app/admin_web/static/admin.css): scoped section/card/status/chip styling, specified 12/6/4 grid allocation, 820px and 560px responsive layouts, long-text wrapping and compact existing state-panel.
- [device_protocol_intelligence.js](C:/CaptivPortal-Lab/coder-web-fix-ni03-01/app/admin_web/static/device_protocol_intelligence.js): six card/label/value DOM elements in the original order; protocol chips follow API order; status badges preserve the original labels and negative states; formatUtcDisplay produces DD.MM.YYYY, HH:mm:ss UTC, with original UTC in time.dateTime/title including Stale evidence.
- [device_protocol_intelligence.cjs](C:/CaptivPortal-Lab/coder-web-fix-ni03-01/tests/admin_web/device_protocol_intelligence.cjs): presentation assertions and DOM-stub text aggregation support; all prior refresh/timer/error/privacy/validation checks retained.

app/admin_web/templates/admin/device.html remains byte-identical: its section ID, heading, explanation, Refresh button, loading state and data container already satisfy the contract. Scoped CSS styles these existing elements; no template edit was required.

NO_EXTRAS=PASS
No backend, API, SQL, models, protocol classification, rights, flags or other Admin pages changed. No new files in the repository. No new infrastructure or dependency.

## Focused local verification

Environment: Windows, Python 3.10.11, Node v24.19.0.
Only the existing module test mechanism was used.

Commands:
- node --check app/admin_web/static/device_protocol_intelligence.js — PASS.
- node --check tests/admin_web/device_protocol_intelligence.cjs — PASS.
- C:/CaptivPortal-UI-Preview/.venv/Scripts/python.exe -m pytest -q tests/admin_web/test_device_protocol_intelligence_frontend.py --basetemp=C:/CaptivPortal-Lab/tmp/web-fix-ni03-01-tests-02 -o cache_dir=C:/CaptivPortal-Lab/tmp/web-fix-ni03-01-cache-02 --junitxml=C:/CaptivPortal-Lab/artifacts/TASK-WEB-FIX-NI03-01-focused-02.xml — 2 passed / 0 failed / 0 skipped.
- git diff --check — PASS before commit.
- git diff --check HEAD^ HEAD — PASS after commit.
- Exact source comparison before state/field/render helpers and from clearTimer through EOF — PASS: validate(), utc(), dictionaries, fetch/refresh/error handling/timers/retention unchanged.
- git apply --reverse --check of exported patch — PASS (check only, no application).

[Focused JUnit](C:/CaptivPortal-Lab/artifacts/TASK-WEB-FIX-NI03-01-focused-02.xml)

Proofs include six cards/order/classes; separate DNS/TLS/QUIC chips; an API order QUIC/DNS/TLS with different observation times preserved; microseconds hidden and originals retained; exact example 2026-10-10T08:07:45.327200Z displays 10.10.2026, 08:07:45 UTC; all date locations including stale message; status text/data-state and specified CSS colors; empty/identity_pending/degraded/unavailable states; existing manual refresh/coalescing/visibility/backoff/expiry/pagehide/timeout checks.

## Complete BASE-to-candidate patch

[Binary-capable full-index patch](C:/CaptivPortal-Lab/artifacts/TASK-WEB-FIX-NI03-01_BASE-to-CANDIDATE.patch)
BYTES=21433
SHA256=df814ec8bd26410d07344fbba0e71ac4b38a91756b8108ec5a661a2fb92c77f5

git diff --name-status:
M app/admin_web/static/admin.css
M app/admin_web/static/device_protocol_intelligence.js
M tests/admin_web/device_protocol_intelligence.cjs

git diff --stat:
3 files changed, 175 insertions(+), 13 deletions(-).

## Boundaries / pending review

This is a locally implemented review candidate, not a Tech Lead acceptance or official full-gate PASS.
No browser visual review or screenshots were performed; responsive rules were checked statically in the existing module contract.
Full regression/visual acceptance is Owner / Tech Lead responsibility.

PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
FULL_REGRESSION_RUN=NO
CENTRAL_LAB_RUN=NO
