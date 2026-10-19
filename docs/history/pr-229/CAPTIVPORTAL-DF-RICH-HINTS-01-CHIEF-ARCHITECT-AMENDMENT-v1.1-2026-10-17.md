# CaptivPortal — DF-RICH-HINTS-01
## Chief Architect Amendment v1.1 — Show All Existing Normalized Device Observations

**Дата:** 2026-10-17 (Asia/Baku)  
**Статус:** **APPROVED — replaces the two-field UI scope of v1**  
**Адресат:** Project Tech Lead → один ограниченный Coder TASK  
**GitHub reference at review:** `main@c6db833952d8daabb8fccedb03a774f9277850b6` / `tree a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92`; Tech Lead repins before task.  
**Base document:** `CAPTIVPORTAL-DF-RICH-HINTS-ARCHITECT-IMPLEMENTATION-CONTRACT-v1-2026-10-17.md`. This v1.1 overrides its sections 1, 3–4, 6–7 **where scope conflicts**; unchanged security, R14, governance and no-production-GO rules remain in force.

## 1. Owner's clarified product intent

The **Observed Device Hints / Наблюдаемые сведения** block should show **all useful normalized fields already retained for this device**, not only `model_family` and `os_major`. This is an evidence display, **not** verification that the device truly is a given model or OS.

**Approved UI:** a few simple prominent rows (`reported model`, `reported OS/major` where available, optional platform) plus a **collapsible “All observed details”** area grouped by source. No new dashboard, history browser, packet analyzer, classifier, or front-end dependency. Empty or unavailable groups have honest states. Dates and provenance appear with each source group and with independently selected values where necessary.

## 2. Included source groups — exactly the current production schema registry

`app/device_fingerprint/schema_registry.py` admits the following normalized evidence schemas. **Display supported normalized values actually present; do not infer missing ones.** Fields are drawn from existing schema validators, not an unconstrained `payload_json` or new client probe.

| Source group | Supported schemas | Already-retained normalized fields to show when present |
|---|---|---|
| **Portal / Browser** | `portal_headers/1`, `/2` | Model family, OS major, reported platform where schema carries one, browser/runtime family, mobile flag, webview/captive context, form-factor indicators (v2), field-specific source labels and source-presence boolean flags (`ua_present`, `sec_ch_ua_*`). |
| **DHCP** | `dhcp/1` | `message_type`, `parameter_request_list`, `option_order`, `vendor_class`, `client_identifier_kind` **category only**, `maximum_message_size`, `rapid_commit_requested`, `capport_requested`, `ipv6_only_preferred_requested`, `hostname_present` **boolean only**. |
| **TCP SYN** | `tcp_syn/1`, `/2` | Observed IP version/TTL, TCP window, MSS, window scale, SACK/timestamp flags and option order (v1); v2 IP/TCP flags, header and option metadata, bounded `tcp_option_records` as structured attributes. No packet bytes. |
| **TLS Client** | `tls_client/1` | JA4 plus existing components, TLS version family, client ALPNs, ECH/GREASE extension-present flags. No hostnames or credentials. |
| **QUIC Client** | `quic_client/1` | JA4 plus components, QUIC version, ECH/GREASE extension-present flags. No contents of sessions or payload. |

For every displayed group include its **source kind**, **exact schema version**, **observed_at UTC**, **quality_state** (`valid`, `partial`, `degraded`). Client-reported (Portal / DHCP) and network-observed (TCP/TLS/QUIC) are distinguishable; `JA4` is *not* a device model. Optional source-specific provenance strings may be shown where already normalized. Null fields show `—`/`Not provided`, not invented values.

**Not equivalent to “everything on the network”:** no raw UA/header dump, IP or MAC duplication, opaque client identifier, HTTP URLs, packet bodies, session content, private hostnames, tokens, credentials, internal file paths, raw JSON, or arbitrary evidence metadata. Values must pass existing integrity + exact-schema validation, be bounded, and be rendered with safe text nodes.

## 3. One bounded read path; existing Device Card API

```
GET /admin/api/v1/sites/<site_id>/devices/<device_id>
  → existing admin.read.device + exact Site + resolved canonical MAC
  → existing Fingerprint Evidence SQLite (read-only)
  → bounded latest retained normalized evidence
  → existing integrity + schema validators
  → additive result.observed_device_hints
  → Device Card summary + collapsed source groups
```

- **No new endpoint**, service, database, schema, index, producer, packet-capture path, background worker, polling or feature flag.
- Exactly one evidence read phase when loading **Device Card**, never per row on Home/Devices. Use existing configured evidence DB path and retention window. Read via existing read-only connection helper; no create/open-write, no checkpoint/PRAGMA writes.
- **Selection is latest-observations, not all historical events.** Read the latest **at most 256** candidate evidence rows for the exact `(site_id, canonical_mac)` within the existing retention horizon using the existing Site+MAC+time index; order by `observed_at DESC, evidence_id DESC`. Keep at most the most recent admissible observation for each of the **five** source groups. For Portal, model and OS fields may each use their most recent non-null valid observation **within the same bounded candidate set**, with each field's own source/date. Limit total materialized payloads and enforce the existing Admin request deadline. **Do not claim all past observations were searched.**
- If 256 candidate rows do not contain a source group, report `not_observed_in_bounded_window`, **not** “the device lacks this capability”. The UI may say “Latest 256 retained evidence records (bounded view)” so coverage is honest. If a faster exact per-kind retrieval can be demonstrated without new indexes and within the same resource limits, Tech Lead may propose it as a small refinement before Coder GO; no unbounded per-kind scan.
- Continue the v1 guard against evidence predating the known Site-device identity (`site_first_seen_at`); do not join randomized or reused MACs into a proven physical device.
- If a **selected latest** record is corrupt/unsupported, mark that source `unavailable`/`unsupported`, don't silently substitute an older record as if it were current. Other independent groups remain present. Existing canonical `result.fingerprint` and entire Device Card must remain available on an optional-evidence failure.
- Do not infer that the pipeline is live because evidence exists; display actual observation timestamp. Services being intentionally stopped for Owner investigation are **not** a defect in this task and must not be restarted by Coder.

## 4. Additive DTO — compact and deterministic

Keep the existing `result.fingerprint` **unchanged**. Replace the two-field-only intent of v1 with a bounded additional object:

```json
"observed_device_hints": {
  "state": "observed",
  "coverage": "bounded_latest_256",
  "trust": "observed_unverified",
  "reported_model": {"value": "Nokia G21", "source": "user_agent", "observed_at_utc": "2026-10-16T18:46:33.892Z", "schema": "portal_headers/1"},
  "reported_os": {"platform_family": "android", "os_major": 13, "source": "user_agent", "observed_at_utc": "2026-10-16T18:46:33.892Z", "schema": "portal_headers/1"},
  "sources": [
    {"source_kind": "portal_headers", "schema": "portal_headers/1", "state": "observed", "observed_at_utc": "2026-10-16T18:46:33.892Z", "quality_state": "valid", "fields": {"platform_family": "android", "model_family": "Nokia G21", "os_major": 13}}
  ]
}
```

Illustrative **partial** JSON, not a complete `portal_headers/1` payload or a production record. At most **five** `sources` groups (one per currently registered source kind). For each group `fields` is a **bounded allowlisted projection of the validated normalized schema** (only keys present in the schema of that record; include scalar/list or schema-bounded nested option structures). Never send `payload_json` directly. `sources` are consistently ordered `portal_headers, dhcp, tcp_syn, tls_client, quic_client`; omitted groups are distinguishable from errors by group state or an explicit `not_observed_in_bounded_window` placeholder. State: `observed|no_evidence|unavailable`; individual source state: `observed|not_observed_in_bounded_window|unavailable|unsupported`.

`reported_os.platform_family` may come **only from the same Portal observation as its `os_major`**; `/2` supplies no platform, so render `OS major: 13` without guessing Android/iOS. Values are unverified observations even if the client claims Nokia. No R14 dimension/model/manufacturer update.

## 5. Allowed Coder TASK scope

Production allowlist (same five files as v1):

1. `app/device_fingerprint/read_service.py` — one bounded read method for latest evidence per Site+MAC, using existing index/integrity validator.
2. `app/admin_web/device_fingerprint_presentation.py` — map validated fields to bounded, safe UI DTO; do not alter canonical classifier presentation.
3. `app/admin_web/runtime.py` — compose optional evidence read adapter alongside current read services.
4. `app/admin_web/query_service.py` — only additive field in existing `device_detail` response, no list enrichment.
5. `app/admin_web/static/admin.js` — short visible summary + collapsed sections per source, HTML-escape by safe DOM/text APIs.

Focused tests in `tests/device_fingerprint/` and `tests/admin_web/`, plus a short edit to `docs/modules/admin-web.md` are allowed. **No schema, migrations, classification, source admission, runtime producer, security policy, auth/visit, unit files or production changes.** Tech Lead owns exact task and full Windows/Linux/security/PERF acceptance; Coder only focused tests.

## 6. Minimal deterministic acceptance

1. Portal v1 model/OS/browser/source flags all visible; v2 nullable model/major/form factors visible without invented platform; no raw headers.
2. For DHCP, TCP SYN v1/v2, TLS and QUIC, correctly display the existing validated normalized fields, schema/quality/time; nested TCP option records bounded and not silently dropped.
3. Model/OS from different Portal observations preserve separate timestamp/source; no cross-source invented claim; null/absent/stale/unsupported clearly marked.
4. Strict Site/MAC boundary, Site-first-seen boundary, candidate cap **256**, deterministic ordering/ties, retention, fast bounded SQL plan, no extra reads for Devices/Home; never list all historical rows.
5. Broken DB, malformed JSON, bad digest, unknown schema, busy or timeout: independent source state, fail-open Device Card, no leaking payloads or exception details.
6. Existing R14 result, controller-first behavior, device status, identity, Visit, CAPPORT/Auth untouched; zero new SQLite writes, services, feature flags or systemd mutations. Tech Lead independently tests performance on HDD-like Lab baseline.
7. UI remains readable on narrow screens; human-friendly prominent fields and optional details; show observation time even when services are intentionally offline.

## 7. Decision and release authority

```
TASK=DF-RICH-HINTS-01
ARCHITECT_AMENDMENT=v1.1
VERDICT=APPROVED
V1_TWO_FIELDS_ONLY=SUPERSEDED
SCOPE=ALL_SUPPORTED_NORMALIZED_FINGERPRINT_EVIDENCE_GROUPS
GROUPS=portal_headers,dhcp,tcp_syn,tls_client,quic_client
LATEST_EVIDENCE_CANDIDATE_CAP=256
NEW_DB=NO
NEW_SERVICE=NO
NEW_ENDPOINT=NO
NEW_PRODUCER=NO
R14_CLASSIFICATION_CHANGE=NO
CODER_TASK_PREPARATION=YES
CODER_GO=TECH_LEAD_SEPARATE_DECISION
FULL_GATES=TECH_LEAD
OWNER_MERGE=REQUIRED
PRODUCTION_CHANGES=NO
CURRENT_STOP=OWNER_INTENTIONAL
```

**Chief Architect:** don't turn this into new classification research. Display already-retained normalized facts accurately, safely and cheaply.
