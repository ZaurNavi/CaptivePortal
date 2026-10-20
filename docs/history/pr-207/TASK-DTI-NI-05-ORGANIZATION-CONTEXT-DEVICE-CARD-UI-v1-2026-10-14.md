# TASK-DTI-NI-05 — ORGANIZATION CONTEXT IN DEVICE CARD
## Coder implementation task v1 — Owner-accepted product scope

**Project:** CaptivPortal  
**Date:** 2026-10-14  
**Repository:** `ZaurNavi/CaptivePortal`  
**Verified code baseline:** `main@3b5f70cec467939995fecc7667169239000b7308`  
**Verified tree:** `5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b`  
**Status:** READY FOR CODER IMPLEMENTATION / tests / PR; **merge and production activation require separate Owner authorization**.  
**NI-06:** CANCELLED by Owner; never treat NI-06 as a prerequisite.  
**Architecture:** No new contract is requested: this is a narrowly scoped, bounded presentation/aggregation of the existing NI-04 read DTO. If source semantics or database/API expansion becomes necessary, STOP the affected scope and return a precise architecture question instead of silently extending it.

---

## 1. Objective

Enhance the existing Admin Web **Device Card → Service Intelligence** section with a visually polished **“Organizations · last 60 minutes”** presentation. Group confirmed, recent NI-04 services by their already-provided `organization_id`, display organization branding where approved, and show the member services with their own locally stored icons when available.

**Illustrative appearance (not factual activity):**

```text
Service Intelligence

Recent Services · last 60 minutes
  YouTube · Google · [last observed]
  Instagram · Meta · [last observed]
  WhatsApp · Meta · [last observed]

Organizations · last 60 minutes
  [Google G logo] Google                1 recognized service shown
      [YouTube icon] YouTube                  [last observed]

  [Meta logo]     Meta                  2 recognized services shown
      [Instagram icon] Instagram              [last observed]
      [WhatsApp icon]  WhatsApp               [last observed]

  Organizations are based only on recognized services shown in this 60-minute result.

Service Categories
Last Service Observation · last 24 hours
Freshness / coverage
```

Provide compact, legible, aesthetically coherent cards/rows with rounded icon tiles, whitespace, typographic hierarchy and responsive layout, using the existing Admin Web visual system. Do not merely append plain-text provider names.

## 2. Normative/current-state basis

- Accepted `DTI-NETWORK-INTELLIGENCE-PRIORITY-ADDENDUM-v0.2-FINAL-TECHLEAD-ACCEPTED.md`, sections 16–17 and stage NI-05: **organization summary / aggregation / Device Card projection**, consuming organization dimension from NI-04; **not** another recognition engine, rules engine, provider classifier or IP list.
- NI-04 already produces independent `organization_id`, `service_id`, `service_category_id` and their display labels from an admitted taxonomy. Example current taxonomy V2: `org.google` / Google and `org.meta` / Meta; `service.youtube`, `service.instagram`, `service.whatsapp`.
- Existing endpoint: `GET /admin/api/v1/sites/{site_id}/devices/{device_id}/service-intelligence`.
- `DeviceServiceSummaryV3` in materialized `serve` mode contains `recent_services` (up to 12 confirmed entries in a 60-minute window), each with `service_id`, `display_name`, `organization_id`, `organization_display_name`, `last_observed_at`, `support_state='directly_supported'`. Same organization fields are present in existing V2 DTO for other supported modes.
- `app/network_service_recognition/materialized_read_service.py` reads **only** NI-04 materialized SQLite in `serve`, without NI-01/NI-02B rereads on a Device Card request. Preserve this invariant.
- Admin Web currently renders four NI-04 cards via `app/admin_web/static/admin.js`; the section and its refresh hook live in `app/admin_web/templates/admin/device.html`. Existing static assets reside under `app/admin_web/static/icons/` and are repository-local, with provenance recorded in `icons/README.md`.
- Authoritative data semantics: an organization associated with an identified service is **not** evidence of all traffic to the organization's infrastructure or of actual media/app use. For example, YouTube → Google is service-operator taxonomy, not an independent attribution of every Google/Cloudflare IP.

## 3. Frozen product semantics — no ambiguity for Coder

### 3.1 Input and ownership

Use **only** the existing, already validated NI-04 service-intelligence response. No additional fetch, API route, SQL query, materialization worker, schema, table, backend aggregation or code changes to the recognition taxonomy/rules. Do not ingest external ASN/WHOIS or derive organization from IP/DNS/SNI in the browser.

Reuse the existing NI-04 fetch, validation, window, permission, Site/device scope and request lifecycle. Do not create an independent NI-05 polling loop, new refresh button, timer or network request.

### 3.2 Grouping and counts

1. Derive organizations in browser **after** the existing NI-04 response passes full validation.
2. Only use `v.recent_services` returned for that Device/Site and the **existing** 60-minute window; support state must be `directly_supported`, as validated upstream. Do not read extra `last_service_observation` when it falls outside the 60-minute window, and do not claim a 24-hour organizations list.
3. Group by **canonical `organization_id`**, not display name. Preserve the associated, already-validated `organization_display_name`; reject/handle any conflicting display names for the same ID as an invalid response rather than silently merging inconsistent data.
4. Within a group, show distinct `service_id` values only; the existing DTO contract already guarantees uniqueness. The number displayed is **“N recognized service(s) shown”**, **not** number of visits, connections, flows, hosts, packets, bytes, total applications or usage duration.
5. Organizations ordered by maximum `last_observed_at` descending, tie by `organization_id` ascending. Services retain the existing validated recent-services order (newest first; tie by `service_id`). Display the group's latest supported timestamp if useful, with the same time semantics as NI-04.
6. At most 12 input services and thus at most 12 groups; derive in memory in `O(12)` or equivalent strictly bounded work. No additional pagination, all-time totals, percentage shares or misleading charts. The response may omit additional supported services beyond the existing 12-entry cap, so **do not label the list exhaustive**.
7. No cross-Site, cross-device, cross-MAC or uncertain IP attribution. Nothing in this task alters NI-04/Registry evidence or confirmation rules.

### 3.3 Coverage/freshness and empty state

- Keep all existing NI-04 `coverageMessage`, `evidence_state`, `materialization`, `freshness_state`, stale-last-good handling, pending/unknown states and 15-minute expiry behavior unchanged. Positive, previously materialized results may remain visible while the pipeline is lagging, accompanied by existing coverage warnings; do not downgrade confirmed facts to speculative, or claim complete current activity.
- If `recent_services` is empty, show a small graceful empty card: **“No confirmed organizations from recent recognized services. This does not mean the device had no network activity.”** Do not display branded tiles with zero counts, and do not infer a negative activity verdict.
- If identity isn't authoritative or response validation fails, respect the existing NI-04 handling; no separate optimistic organization UI.
- Existing public API/DTO schema stays **exactly** V2/V3 (no additive field or version bump).

## 4. Visual UI / UX contract

### 4.1 Placement and hierarchy

Keep existing `#device-service-intelligence` section, `#device-service-content`, `#device-service-state`, `#device-service-refresh`, `data-materialization-mode` and all current JS/HTML hooks unchanged. Within the existing Service Intelligence `content-grid`, add an **Organizations · last 60 minutes** presentation immediately **after** Recent Services and before Service Categories; preserve the existing three other cards, their labels, and their full behavior. Expect five top-level blocks when the NI-04 payload is valid.

For each organization:

- Main row: visually distinct organization icon tile (about 36–44px), organization display name in strong text, small secondary **N recognized service(s) shown** counter; optional latest observed timestamp in understated text.
- Subrows or wrapped chips beneath: small service logo tile (about 20–28px), service display name and existing `last_observed_at` (human-friendly optional, absolute exact observation time still accessible). Do not make them clickable or imply navigation to external services.
- Maintain balanced padding, corner radius, border/divider treatment, spacing and responsive wrapping; avoid excessive nested cards, truncated critical names or horizontal overflow. Do not use color alone to communicate state. Mobile 320–375px single-column, tablet, desktop; honor reduced-motion preference if animations are introduced (prefer no animations).
- Keep the visual language consistent with `admin.css` variables `--ink`, `--muted`, `--line`, `--surface`, `--surface-soft`, `--radius`; don't redesign unrelated sections.

### 4.2 Brand/logo assets — **mandatory feature**

Use **repo-local, static, safe SVG (or otherwise approved local assets)** rather than dynamic favicons or remote image APIs/CDNs. Provide a small **explicit allowlist map** from trusted canonical IDs to bundled local file names, never paths/URLs derived from API display names or unvalidated `organization_id`/`service_id` input.

Minimum branded visual set in this task:

- Organization: **Google** (`org.google`, recognizable Google G) and **Meta** (`org.meta`, recognizable Meta brand symbol).
- Services: **YouTube** (`service.youtube`), **Instagram** (`service.instagram`), **WhatsApp** (`service.whatsapp`).
- All other known or unknown supported IDs: tasteful **generic local icon/monogram** fallback (e.g. a small abstract organization glyph, service tile), not a broken image or omitted icon. Further branded assets (Gmail, Google Drive, Microsoft, OpenAI, etc.) are optional only if proper provenance/usage terms are documented.

Suggested storage:

```text
app/admin_web/static/icons/organizations/google.svg
app/admin_web/static/icons/organizations/meta.svg
app/admin_web/static/icons/organizations/generic.svg
app/admin_web/static/icons/services/youtube.svg
app/admin_web/static/icons/services/instagram.svg
app/admin_web/static/icons/services/whatsapp.svg
app/admin_web/static/icons/services/generic.svg
```

Document every real brand asset in `app/admin_web/static/icons/README.md`: source/owner, official source URL, permitted use or brand guideline basis, any attribution obligations, alterations, version if known. **Do not invent a license**. Do not embed copyrighted logos sourced from random icon repositories without usage verification. If legitimate provenance for a required branded asset cannot be established, report the asset-specific blocker to Tech Lead/Owner and provide a visually attractive safe fallback; do not silently replace the logo with an externally fetched image. Existing Android icon provenance pattern is the model.

SVG hygiene: no embedded JavaScript/event handlers, no `<foreignObject>`, no remote stylesheet/font/image URL, no external links or active content, no network dependency and no loading through `innerHTML`. Add a fallback on image load error, and use same-origin paths generated or grounded via existing Flask static route. Keep all text legible without images; decorative logos are `alt=""` / `aria-hidden` when adjacent display name already labels the item.

### 4.3 Accessibility and security

- Use ordinary DOM creation (`document.createElement`, `textContent`, `appendChild`, `replaceChildren`) and static style classes. No `innerHTML`, inline JavaScript, external runtime JS/CSS, remote brand CDN, base64-injected HTML, or user-controlled CSS/asset paths.
- Use appropriate semantic headings, groups/lists and noninteractive elements; don't create keyboard-tab stops for noninteractive logos/chips. Preserve live-region behavior without extra announcement storms.
- Unknown logo or rejected image loads → generic icon, with no broken-image mark. No external images requested from browser.
- Ensure Site isolation, existing Admin auth/CSP and protected data boundaries remain intact.

## 5. Code scope

**Implementation allowed (narrow edits only):**

```text
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/device.html              [only if justified for presentation/hook]
app/admin_web/static/icons/README.md
app/admin_web/static/icons/organizations/*.svg         [new, local approved assets]
app/admin_web/static/icons/services/*.svg              [new, local approved assets]
tests/admin_web/device_service_intelligence.cjs
tests/admin_web/materialized_service_intelligence.cjs
tests/admin_web/test_device_service_intelligence_frontend.py
tests/admin_web/test_admin_ui.py                         [if template changed]
tests/admin_web/ni05_organization_context.cjs          [new, recommended]
```

Only touch additional NI-04 frontend tests if existing assertions depend on the former four-card layout and the minimal change is documented. No production changes to `app/network_service_recognition/**`, `app/network_metadata/**`, `app/network_metadata_projection/**`, `app/network_attribution/**`, Registry, settings, auth, routes, Admin QueryService, `run.py`, database schema or background workers. No dependency, migration, new environment variable or API version.

**Designer role boundary:** This is a Coder assignment. Existing *Web Designer* default `READ-only admin.js` rule does not prohibit Coder from making the explicitly scoped presentation change. Any separate designer handoff still follows its own PATCH/review rules; it must not directly commit/deploy.

## 6. Testing / evidence required

Deliver targeted automated tests plus visual acceptance evidence:

1. **Grouping:** Google containing 3 distinct recent supported services, Meta containing 2; counts/ordering/ties correct; no duplicate organizations; no cross-assignment of services.
2. **Minimum logos:** `org.google`, `org.meta`, `service.youtube`, `service.instagram`, `service.whatsapp` resolve to local allowlisted assets in DOM; unknown IDs use safe generic fallback; no remote URL requests; image load failure also falls back safely.
3. **Scope/semantics:** most recent >60m excluded; 24h `last_service_observation` outside recent window not included; exactly 12 input services; incomplete/limited coverage visibly qualified; do not imply total usage, share or time spent.
4. **States:** pending/absent identity; zero recent; `lagging`, `backfilling`, `unavailable`, `capacity_halted`, `conflict` materialization; refresh failed with 15-minute last-good expiry; malformed response; Site mismatch; unauthorized response and section disabled. No phantom positive groups.
5. **Lifecycle:** original NI-04 single fetch and auto-refresh cadence (120s, 300s, 600s backoff), manual refresh, `IntersectionObserver` visibility and `pagehide` cancellation remain intact. The organizations rendering does not make any extra call.
6. **Security:** hostile display text shown literally (DOM text only); no innerHTML/remote assets; no sensitive domains, raw IP/SNI/DNS, cookies or token leaks.
7. **Accessibility & responsive UI:** inspection at ~320px, 375px, 768px and desktop; logo fallback, icon/text readability, keyboard/navigation, long localized names, contrast, no overflow, minimal visual regression of existing cards.
8. **Performance:** bounded groups derived strictly from <=12 existing NI-04 DTO entries; **zero** new NI-04 DB reads, SQLite writes, worker or checkpoint changes; no new timers. Keep current backend materialized read test passing.
9. **Regression:** adapt existing frontend tests with prior four-card assumptions to the new five-card layout; rerun NI-04 V2 and V3 frontend tests and affected Python Admin tests. Record exact commands/results; classify unrelated baseline failures rather than introducing unrelated refactors.

If a test harness mocks `document.createElement`, extend that harness narrowly to support harmless SVG `<img>` elements and image fallback; do not loosen production validation.

## 7. Definition of Done

- One organization group card in **Device Card → Service Intelligence**, styled for desktop/mobile, rendered from existing response only.
- Branded visual assets for Google, Meta, YouTube, Instagram and WhatsApp present locally with verifiable provenance, or an explicit asset-specific exception raised to Owner/Tech Lead before PR approval.
- Deterministic grouping, correct confirmed-only semantics, sensible fallback for other organizations and empty/partial coverage.
- No backend changes, no new polling/API calls, no changed NI-04 data semantics, no adverse HDD I/O effect.
- Targeted automated tests passing, narrow diff, frontend preview evidence, `git diff --check` clean.
- Coder supplies: baseline SHA/tree, changed-file list, tests and results, asset provenance, screenshots or equivalent visual acceptance evidence, commit/PR link and any unresolved blockers.

## 8. Execution and release boundary

Coder may implement and submit **a PR**. **Do not merge/deploy/restart services or change production** without separate Owner instruction. Tech Lead reviews exact scope, test and visual evidence; Owner authorizes activation. Because no backend or database migration is authorized, rollback is front-end code/assets only and must preserve the previous NI-04 behavior.

**Owner decision:** NI-06 is cancelled; no transport-health feature is included in this or future NI-05 work.
