# CaptivPortal — TASK-DF-RICH-HINTS-01
## Coder Implementation Contract v1.0 — Observed Device Hints / All Existing Normalized Evidence

**Date:** 2026-10-17 (Asia/Baku)  
**Issued by:** Project Tech Lead  
**Recipient:** Coder  
**Status:** `CODER GO — IMPLEMENTATION IN ISOLATED PR ONLY`  
**Architecture:** Chief Architect Amendment v1.1 — **APPROVED**, supersedes v1 two-field UI scope  
**Source baseline:** `main@c6db833952d8daabb8fccedb03a774f9277850b6`  
**Exact source tree:** `a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92`  
**Production:** `NO CHANGE` · **Merge:** `OWNER GO REQUIRED`  
**Related independent task:** `TASK-DF-DIAGNOSTIC-ORIGIN-ATTRIBUTION-01` (P2 diagnostic provenance UI fix) — NOT included here.

## 0. Tech Lead disposition

**No additional Chief Architect questions block this task.** The current repository has been independently checked at the above HEAD in a **clean detached laboratory worktree**. The frozen R14 classifier and accepted source/knowledge semantics must not change. This is an **additive read-only presentation of persisted normalized observations**, not a more ambitious device identity classifier.

If `origin/main` moves before the Coder PR, pin the new head, document the delta, and ensure the five-file allowlist and existing behavior still hold. Do not make modifications in production or in another developer's dirty worktree.

## 1. Goal and non-goal

**Goal:** Add **Observed Device Hints / Наблюдаемые сведения** to the existing Admin **Device Card**. Show *all useful existing, exact-schema-validated normalized fields* retained for the selected device, grouped by source. Present prominent **reported model** and **reported OS major** (optional same-record platform); allow expansion of **All observed details**. Display data origin, source schema, quality, and observation timestamp; avoid false certainty and hidden staleness.

**Non-goals:** Classify/manufacturer inference, Android/iOS version verification, MAC/OUI→manufacturer mapping, model taxonomy changes, JA4→model claims, new acquisition/probes, new user history browser, raw packet inspector, new endpoint/dashboard, auto-enabling stopped Fingerprint services. Stored observations may be client-declared, spoofed, old or partial; never promote them to the authoritative `result.fingerprint`.

## 2. Authoritative input contracts

1. Chief Architect: `CAPTIVPORTAL-DF-RICH-HINTS-01-CHIEF-ARCHITECT-AMENDMENT-v1.1-2026-10-17` (**this is the controlling scope**).
2. Base Architect v1, **only to the extent not overridden by v1.1**, notably security, retention, R14 freezing, governance, no production GO.
3. Existing exact schema registry: `app/device_fingerprint/schema_registry.py`.
4. Existing integrity check: `app/device_fingerprint/payload_integrity.py:verify_persisted_payload`.
5. Existing RO SQLite boundary: `app/device_fingerprint/repository.py:open_read_only` and `app/device_fingerprint/read_service.py`.
6. Existing Site-scoped Admin device detail endpoint and query gate: `app/admin_web/query_service.py:device_detail`, `AdminQueryExecutionControls`.
7. Existing UI: `app/admin_web/static/admin.js:fingerprintCard` and `deviceDetail` rendering; current `result.fingerprint` remains authoritative and unchanged.

No silently invented fields, thresholds, permissions, or provenance interpretations.

## 3. Exact file allowlist

**Only these FIVE production files:**

- `app/device_fingerprint/read_service.py` — bounded, indexed read of latest retained evidence; use existing RO helper; enforce validator and retention.
- `app/admin_web/device_fingerprint_presentation.py` — deterministic projection into safe bounded `observed_device_hints` DTO, alongside (not replacing) existing fingerprint presentation.
- `app/admin_web/runtime.py` — optional read service composition with existing settings/path; fail open.
- `app/admin_web/query_service.py` — single optional additive field in existing `device_detail`; no list enrichment.
- `app/admin_web/static/admin.js` — compact reported-fields summary and collapsible per-source groups with safe DOM/text nodes.

**Additionally allowed:** focused tests in `tests/device_fingerprint/` and `tests/admin_web/`; one concise documentation change in `docs/modules/admin-web.md`.

**Forbidden:** edit `app/device_fingerprint/fusion.py`, `origin_assessment.py`, R14 policy/knowledge, schema validators/registry, evidence producers, classifiers, raw capture, DB schema/migration/index, config/feature flags, auth/visit/CAPPORT, Admin policy, systemd units, dependency manifests, production or source deployment. No CSS file change; reuse existing accessible presentation styles/classes. If an unavoidable requirement falls outside allowlist, **STOP / Tech Lead escalation**, do not expand scope yourself.

## 4. Existing route and authorization boundary

Implement within **the existing endpoint only**:

`GET /admin/api/v1/sites/<site_id>/devices/<device_id>`

Keep the existing `admin.read.device` authorization and Site/device resolution. Only after the authorized `device` resolves, consume **its canonical MAC** and **`device.site_first_seen_at`**. Reject cross-Site, invalid MAC, unknown Device ID; do not accept `site_id`, MAC, first-seen or evidence path from new query/body parameters. Use `device.canonical_mac`, not a transient IP, arbitrary user MAC, or cross-site lookup. No new endpoint or permission.

Run the optional evidence read within the **existing Admin query slot/deadline**, but isolate optional failure so `identity`, `latest_snapshot`, `recent_visits`, `latest_client_observation`, and `fingerprint` remain exactly as before. No evidence read from Home, Devices, online lists, or batch fingerprint compact enrichment.

## 5. Evidence read contract / SQL performance

Implement ONE bounded evidence phase on ONE `open_read_only` SQLite connection, no create-write or schema/index modification. The preexisting `device_fingerprint_evidence` table has `idx_df_evidence_site_mac_time` on `(site_id, observed_mac, observed_at, evidence_id)`; **do not use existing ascending history pagination as a substitute**.

**Deterministic selection:**

```sql
SELECT <only necessary columns>
FROM device_fingerprint_evidence
WHERE site_id = ?
  AND observed_mac = ?
  AND observed_at >= ?
  AND observed_at < ?
ORDER BY observed_at DESC, evidence_id DESC
LIMIT 256;
```

- Parameters are validated/canonicalized. Lower bound is the **later** of the existing retention cutoff and `site_first_seen_at` (same Site). Upper bound is a single pinned UTC as-of timestamp consistent with existing read/retention policy; do not accidentally discard a valid boundary event. Define exact `<`/`<=` behavior in tests.
- **Hard maximum 256 candidate rows total**, not per group; the same selection set is used by all five groups and prominent Portal field lookups. No unbounded `OFFSET`, multi-pass historical scans, SQL requests inside a row loop, full-table scans, N+1, async pollers, or per-kind retries.
- Use `EXPLAIN QUERY PLAN` in tests to prove the existing Site+MAC+time index is selected and the operation is bounded. Require fast cancellation/deadline checks, including during row materialization, and avoid busy-wait. Do not introduce write-bearing PRAGMAs/checkpoints. Reuse the RO helper and existing busy timeout. Existing helper's `PRAGMA query_only` is not a database mutation.
- Integrate existing `verify_persisted_payload(source_kind, feature_schema_version, payload_json, payload_sha256, frozen_registry)` **before** projection, including canonical JSON/integrity/digest/schema validation. No direct `json.loads`-and-display. Malformed, too-large or unsupported normalized records are not rendered. Never send `payload_json` to the browser. Bound validation/materialization and resulting DTO sizes, including TCP options; document actual caps measured in tests.
- Sort groups deterministically: `portal_headers`, `dhcp`, `tcp_syn`, `tls_client`, `quic_client`; at most FIVE. Select latest retained observation in the bounded candidate set per group; tie-break on `evidence_id DESC`. Report `not_observed_in_bounded_window` when group missing; do not pretend all history was examined.
- **Do not silently fallback** behind a corrupt/unsupported selected latest group record: mark that group `unavailable`/`unsupported`. Other independent groups should remain visible. For Portal, permitted separately selected newest non-null **valid** `model_family` and `os_major` may originate in *different* Portal rows within the SAME 256 rows, each with its own time/source/schema. Do not silently replace a selected corrupt or unsupported Portal record with earlier values; mark affected part unavailable rather than claim current evidence.
- If DB/file/lock/deadline/validation is unavailable, return an additive `state="unavailable"` object with safe generic reason/status only, **never throw away the existing Device Card**. Missing device/no evidence should be `no_evidence` or bounded not-observed, not fabricated Unknown physical type.

## 6. Source-by-source projection allowlist

Derive exact keys from registered schema validators — **not arbitrary JSON**. Show only already normalized values actually present (nullable values as `—`/`Not provided`), keep scalar types and bounded structured lists:

| Source/schema | Allowlisted normalized fields |
|---|---|
| `portal_headers/1` | `platform_family`, `mobile_boolean`, `browser_runtime_family`, `webview_or_captive_context`, `model_family`, `os_major`, `platform_source`, `mobile_source`, `runtime_source`, `context_source`, `model_source`, `os_major_source`, `ua_present`, `sec_ch_ua_present`, `sec_ch_ua_platform_present`, `sec_ch_ua_mobile_present`. |
| `portal_headers/2` | `model_family`, `os_major`, `form_factor_mobile`, `form_factor_tablet`, `form_factor_desktop`, `model_source`, `os_major_source`, `form_factors_source`. **No `platform_family` in schema v2**. |
| `dhcp/1` | `message_type`, bounded `parameter_request_list`, `option_order`, `vendor_class`, `client_identifier_kind` (**category only: absent/mac/opaque**, not the actual identifier), `maximum_message_size`, `rapid_commit_requested`, `capport_requested`, `ipv6_only_preferred_requested`, `hostname_present` (**boolean only**). |
| `tcp_syn/1` | `ip_version`, `observed_ttl`, `tcp_window`, `mss`, `window_scale`, `sack_permitted`, `timestamps_present`, `tcp_option_order`. |
| `tcp_syn/2` | `ip_version`, `observed_ttl`, `ip_option_length_bytes`, `ip_id_zero`, `ip_df`, `ip_reserved_flag`, `ip_ecn_bits`, `tcp_header_length_bytes`, `tcp_window`, `tcp_sequence_zero`, `tcp_ack_number_nonzero`, `tcp_ack_first_octet_lsb_set`, `tcp_urg_pointer_nonzero`, `tcp_fin`, `tcp_rst`, `tcp_push`, `tcp_urg`, `tcp_ns`, `tcp_ece`, `tcp_cwr`, `tcp_payload_present`, `tcp_option_records`. Records are **structured** and exact-schema-bounded (validator permits at most 40), including kind/length/state and explicitly admitted per-option attributes. |
| `tls_client/1` | `ja4`, `ja4_a`, `ja4_b`, `ja4_c`, `tls_version_family`, `client_alpns`, `ech_extension_present`, `grease_extension_present`. |
| `quic_client/1` | `ja4`, `ja4_a`, `ja4_b`, `ja4_c`, `quic_version`, `ech_extension_present`, `grease_extension_present`. |

Each source group must carry `source_kind`, **exact** `schema` (`kind/version`), `observed_at_utc`, `quality_state` (valid/partial/degraded), and distinguish `client_reported` for Portal/DHCP versus `network_observed` for TCP/TLS/QUIC. Source labels already normalized may be displayed; never expose arbitrary provenance metadata or file paths. JA4 is a network/client hello fingerprint, **not a verified model**.

**Privacy exclusions:** raw User-Agent, raw headers/Client Hints, private hostname or actual client identifier, MAC or IP duplication, URLs, packet bytes/payload, session contents, tokens/credentials, device/file paths, unrestricted JSON/debug dumps. Do not include `payload_sha256`, hidden database IDs or unrelated storage metadata in UI; validation uses them server-side only. Output via `textContent`/safe DOM text nodes; prevent XSS even if a string passes normalizer rules.

## 7. Additive response contract

Keep `result.fingerprint` **bit-for-bit unchanged** in all code paths. Add **one** sibling `result.observed_device_hints` with stable bounded DTO:

```json
{
  "observed_device_hints": {
    "state": "observed",
    "coverage": "bounded_latest_256",
    "trust": "observed_unverified",
    "reported_model": {
      "value": "Nokia G21", "source": "user_agent",
      "observed_at_utc": "2026-10-16T18:46:33.892Z", "schema": "portal_headers/1"
    },
    "reported_os": {
      "platform_family": "android", "os_major": 13, "source": "user_agent",
      "observed_at_utc": "2026-10-16T18:46:33.892Z", "schema": "portal_headers/1"
    },
    "sources": [
      {"source_kind": "portal_headers", "schema": "portal_headers/1",
       "state": "observed", "observed_at_utc": "2026-10-16T18:46:33.892Z",
       "quality_state": "valid", "fields": {"platform_family": "android", "model_family": "Nokia G21", "os_major": 13}}
    ]
  }
}
```

This example is illustrative, not a complete Portal payload. `sources` has at most five entries; missing kinds are either explicit `not_observed_in_bounded_window` placeholders or clearly distinguishable from errors. Top-level state: `observed|no_evidence|unavailable`. Per-source state: `observed|not_observed_in_bounded_window|unavailable|unsupported`. Absence of `reported_model`/`reported_os` should be represented unambiguously as null/absent — never derive from `result.fingerprint` or another source.

**Critical anti-synthesis rule:** `reported_os.platform_family` can be populated **only** if that same Portal record supplying `os_major` also contains a valid `platform_family`. Schema `/2` has no platform field; if major=13 from `/2`, show **“OS major: 13 (reported, platform not provided)”**, never “Android 13” based on earlier `/1`, another source, or canonical R14 platform. Per-field timestamp, schema, provenance remain paired with the record from which the field came.

Optional source failure never becomes an HTTP failure of an otherwise valid Device Card. Preserve existing site-safe, read-only, authorized response semantics and actual Date/UTC values. Do not represent historical evidence as a live sensor result.

## 8. UI / UX contract

Within the existing Device Card:

1. Create a small distinct section **“Observed Device Hints / Наблюдаемые сведения”** under the existing authoritative Fingerprint Information.
2. Prominent, easy-to-read rows: **Reported model**, **Reported OS / major**, optionally reported platform when same observation qualifies. Label **“Observed / unverified — device-reported or network-observed, not confirmed identity.”**
3. Native accessible `<details><summary>All observed details</summary>…</details>` (or equivalent existing safe DOM helpers) grouped by five source names; show human-friendly field names, exact source/schema, `observed_at` in UTC, quality and applicable origin category. Do not show huge concatenated hash/provenance strings or raw JSON.
4. Clearly explain bounded coverage: **“Latest up to 256 retained evidence records for this Site/device; earlier history not searched.”** Empty groups say **“Not observed in bounded window”**, not that the device lacks that protocol/feature. Distinguish unsupported schema, unavailable reader, quality=degraded.
5. Null/absent values are “— / Not provided”; visually and textually distinguish them from false/0. Keep 40 TCP option records as bounded legible structures (not silently drop) with expandable detail if needed.
6. Use only safe DOM text creation (`textContent` or existing `node()/definitionList()` helpers) and existing CSS/classes; responsive narrow screen test, focus/keyboard/collapsible semantics. No external dependency, front-end SPA, repeated network calls or polling.

## 9. Deterministic RED/GREEN acceptance matrix — Coder must implement

| ID | Required evidence / pass condition |
|---|---|
| A01 | Portal `/1` model, OS-major, platform, runtime/browser/flags, per-field `source` and UTC rendered; `result.fingerprint` exactly unchanged. |
| A02 | Portal `/2` with Nokia-like model+major+form factors rendered; `platform_family` absent stays absent; must not emit an inferred “Android 13”. |
| A03 | Model and OS from **different** eligible Portal records use separate `observed_at_utc`, `schema`, `source`; deterministic latest non-null within capped candidates. |
| A04 | DHCP `/1`: full bounded normalized list/booleans/category only; actual client identifier and hostname value never leaked. |
| A05 | TCP `/1` and `/2`: all admitted fields rendered; nested option records retained and bounded at schema maximum 40; no raw payload. |
| A06 | TLS+QUIC `/1`: JA4/components, version, flags, ALPNs; never label JA4 a device manufacturer/model. |
| A07 | All five groups shown in correct order; schema, source kind, `client_reported/network_observed`, UTC time and quality accurate. |
| A08 | Exact Site + canonical MAC + `site_first_seen_at` isolation; cross-Site/mismatch/reused/randomized-MAC safety; no query side-channel or leaked row. |
| A09 | 257+ interleaved rows => only latest 256 considered; same-time tie resolved by `evidence_id DESC`; missing group => `not_observed_in_bounded_window`. |
| A10 | Latest selected record has invalid JSON, bad SHA, duplicate keys, corrupted canonical bytes => that source unavailable, **no older fallback**; other source groups preserved. |
| A11 | Unknown schema/version => per-source `unsupported`, no nearby-version downgrade; different valid sources still displayed. |
| A12 | SQLite absent/busy/corrupt, read deadline, OS permission error => optional state unavailable; full Device Card + existing fingerprint still works, no stack/file-path/secret leak. |
| A13 | Untrusted strings, markup, delimiters, very long bounded valid strings => safe text, no DOM injection; false and 0 remain explicit, null not invented. |
| A14 | Existing endpoint and read permission unchanged; no evidence DB invocation for Home/Devices/list routes, no per-row reads; no new HTTP route/worker/config. |
| A15 | SQL planner uses `idx_df_evidence_site_mac_time`, exact row cap 256, bounded payload parsing/DTO, shared Admin deadline; no SQLite write/PRAGMA checkpoint. |
| A16 | Historical timestamps remain visible when Sensor/Evidence/Classification intentionally disabled; no auto-start or “live”/fresh claim. |
| A17 | Existing device identity, Visit/CAPPORT/Guest Auth, controller-first list precedence, R14 statuses/provenance and compact presentation unchanged; regressions green. |

**Test methodology:** tests first RED on old behavior, then GREEN after implementation, with simple synthetic SQLite fixtures, no real guest MAC in artifact/log output. Include deterministic SQL plan output, count of evidence SELECTs and rows/materializations; failure injection tests (sqlite busy, corrupted payload, deadline), and front-end DOM/XSS/responsive checks. Coder runs focused tests; **Tech Lead independently owns all full Windows/Linux/security/performance gates and release decision**.

## 10. Performance / HDD acceptance and failure isolation

The production evidence DB is multiple GB and the project is HDD/Small-I/O constrained. Avoid ORM/N+1 and extra DB startup churn. A single index-backed recent-256 query is mandatory. Require measured query count, fetched rows, max parsed bytes, worst-case DTO size and p50/p95 latency from a reproducible HDD-like isolated **laboratory** fixture. Numeric p95 threshold is NOT invented by Coder; Tech Lead compares to the current shared Admin request deadline and accepted lab benchmark, then decides. Aborted/busy queries return optional `unavailable` without increasing Guest Auth latency or prolonged locks. Do not run heavy online SQLite `integrity_check` during deployment.

## 11. Separate P2 diagnostic issue / concurrent PR rule

Previously handed out `TASK-DF-DIAGNOSTIC-ORIGIN-ATTRIBUTION-01` fixes confusing flattened `knowledge_source_expired` explanations. **It is a separate PR and must not be bundled with DF-RICH-HINTS-01.** Both may touch `app/admin_web/device_fingerprint_presentation.py` and `admin.js`; start from an isolated pinned branch and **rebase/resolve sequentially before merge**. No change to existing `result.fingerprint` in THIS task; no suppression of warnings or changes to frozen R14 claim semantics.

## 12. Deliverables / stop gates

Coder handoff must contain:

- Draft PR URL, exact branch, base HEAD+TREE and implementation HEAD+TREE; clean worktree, file allowlist report and `git diff --check`.
- Overview of new read method, indexed SQL, exact cutoff/identity semantics, validation path, group-selection rules, DTO and UI.
- RED→GREEN focused test results for A01–A17 (with any untested gate explicitly recorded), Windows & Linux runnable instructions, no hidden tests.
- Deterministic privacy proof and response/failure isolation snapshots; SQL `EXPLAIN QUERY PLAN`, query/fetch/materialization caps, lab timings, Admin route and list-route regression.
- Diff summary and merge/deployment/rollback notes (additive response is optional and no DB migrations). No production operations or auto-start.
- `P0=0, P1=0` claim backed by evidence, or explicit `HOLD` if unmet.

**HARD STOP** if implementation needs frozen R14 semantics, schema/validators, migration/index, producer change, new service/endpoint, secret exposure, UI guessing or unsafe read; request Tech Lead/Architect exception first. No silent scope expansion.

## 13. Authorization matrix

```text
TASK                             = DF-RICH-HINTS-01
ARCHITECT                        = Chief Architect v1 + APPROVED Amendment v1.1
TECH_LEAD_CODER_GO               = YES (isolated implementation and focused tests only)
REPOSITORY_BASE_HEAD             = c6db833952d8daabb8fccedb03a774f9277850b6
REPOSITORY_BASE_TREE             = a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92
SOURCE_GROUPS                    = portal_headers,dhcp,tcp_syn,tls_client,quic_client
EVIDENCE_CANDIDATE_CAP           = 256 TOTAL
SOURCE_GROUP_CAP                 = 5
ADDITIVE_DTO                     = result.observed_device_hints
AUTHORITATIVE_CLASSIFICATION    = result.fingerprint (UNCHANGED)
R14_CHANGE                       = NO
NEW_DB_SCHEMA_INDEX             = NO
NEW_ENDPOINT_OR_SERVICE         = NO
PRODUCTION_CHANGE               = NO
CODER_FULL_GATES                = NOT AUTHORIZED / TECH LEAD OWNS
MERGE                            = OWNER GO REQUIRED
```

**Tech Lead decision:** `CODER GO` for this exact bounded task. Do not merge or deploy until the independent Tech Lead gate and Owner decision.
