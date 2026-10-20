# TASK-OMADA-WEBHOOK-TRAFFIC-BYTES-01 — Omada Webhook `Bytes` Traffic Alias + Grafana Normalizer Health Polish — DRAFT

**Project:** CaptivPortal  
**Type:** corrective parser compatibility + engineering observability polish  
**Status:** **DRAFT — Owner / Tech Lead review required**  
**Implementation authorization:** NOT GRANTED  
**Production activation:** NOT GRANTED  
**Repository:** `ZaurNavi/CaptivePortal`  
**Exact verified baseline:** `origin/main@9faf31716f93f78325926c9294e9467838f22496`  
**Prepared:** 2026-08-27  
**Normalized webhook schema:** v1 — proposed to remain v1  
**Visit DB schema:** v2 — MUST remain unchanged

---

## 1. Problem statement

Production produced a real Omada offline webhook traffic representation:

```text
(... connected, 887Bytes)
```

The current normalizer accepts only:

```text
B | KB | MB | GB | TB
```

case-insensitively. Therefore `887Bytes` is currently retained as raw traffic but fails numeric traffic parsing, producing `TRAFFIC_INVALID` and making the recognized event `partial`.

The second operational problem is that Grafana Normalizer Health currently treats semantically different `partial` records too similarly. In particular:

```text
CLIENT_IP_MISSING
```

can be expected controller incompleteness, while:

```text
TRAFFIC_INVALID
DURATION_INVALID
```

represent actual parser/data-quality problems.

The corrective design must fix the confirmed `Bytes` representation and make Normalizer Health diagnostically useful without changing the normalized event semantics just for dashboard cosmetics.

---

## 2. Confirmed repository state

The DRAFT is written against:

```text
9faf31716f93f78325926c9294e9467838f22496
```

The current implementation is:

```text
app/integrations/omada/webhook_normalizer.py
```

and defines:

```text
SCHEMA_VERSION = 1
MAX_TRAFFIC_NUMBER_DIGITS = 24
```

Current traffic regex:

```regex
^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>B|KB|MB|GB|TB)$
```

with `re.IGNORECASE`.

Current multipliers:

```text
B  = 1
KB = 1024
MB = 1024^2
GB = 1024^3
TB = 1024^4
```

Current arithmetic uses `Decimal` and `ROUND_HALF_UP` to derive `reported_traffic_bytes_estimate`.

Recognized offline events already expose:

```text
reported_connected_raw
reported_connected_seconds
reported_traffic_raw
reported_traffic_value
reported_traffic_unit
reported_traffic_bytes_estimate
```

No new normalized field is required.

---

## 3. Confirmed raw-value contract

Current offline parsing does:

```python
traffic_raw = traffic_match.group("traffic").strip()
fields["reported_traffic_raw"] = traffic_raw
```

Therefore the raw-field contract is:

```text
controller traffic representation after existing outer trim
```

not canonicalized traffic text.

Examples that must preserve their representation:

```text
887Bytes  -> raw "887Bytes"
887bytes  -> raw "887bytes"
887 Bytes -> raw "887 Bytes"
```

The new parser must never rewrite raw `887Bytes` to `887B`.

---

## 4. Confirmed parse status / warnings contract

For recognized events the current normalizer aggregates parser warnings and timestamp warnings, removes duplicates, and applies:

```text
no warnings
→ parse_status = parsed
→ level = info
→ parse_reason = null

one or more warnings
→ parse_status = partial
→ level = warning
→ parse_reason = null
```

Unclassified diagnostic records use:

```text
parse_status = unclassified
parse_reason = <diagnostic reason>
level = warning
```

This TASK must preserve these normalizer semantics.

---

## 5. `CLIENT_IP_MISSING` decision

The current parser intentionally makes a recognized online/offline event `partial` when the controller supplied no IP:

```text
client_ip = null
parse_warnings contains CLIENT_IP_MISSING
```

Existing tests explicitly verify that an online event without IP remains classified as `omada.client_online`, with `parse_status=partial` and `parse_reason=null`.

### DRAFT decision

Do **not** change the normalizer contract for `CLIENT_IP_MISSING` solely for Grafana appearance.

It remains:

```text
parse_status = partial
parse_warnings contains CLIENT_IP_MISSING
level = warning
```

Grafana must interpret this warning separately from real parser/data-quality failures.

---

## 6. `TRAFFIC_INVALID` decision

If an offline traffic field is present but `_parse_traffic()` rejects it, current behavior remains:

```text
reported_traffic_raw = preserved trimmed source value
reported_traffic_value = null
reported_traffic_unit = null
reported_traffic_bytes_estimate = null
parse_warnings contains TRAFFIC_INVALID
parse_status = partial
```

If traffic is absent entirely, absence remains allowed and does not itself add `TRAFFIC_INVALID`.

---

## 7. Scope

### In scope

- support the confirmed input token `Bytes`;
- retain existing B/KB/MB/GB/TB behavior;
- preserve raw controller traffic representation;
- preserve current number grammar, case handling, whitespace handling, multipliers and rounding;
- preserve normalized schema v1;
- preserve normalizer warning aggregation;
- add deterministic parser and public normalization-path tests;
- add a production-like `(2m connected, 887Bytes)` regression;
- define a Grafana operational classification that separates expected partial from actionable warnings;
- verify Visit Lifecycle/Public Traffic compatibility;
- determine the real production Grafana change surface before FINAL.

### Out of scope

- general normalizer refactor;
- arbitrary traffic aliases;
- Omada Controller/config changes;
- webhook endpoint/security changes;
- Auth/CAPPORT changes;
- Visit start/matching/close/finalization/reconciliation/writer changes;
- Visit DB schema changes;
- Observation or Current State changes;
- Home Activity formula changes;
- Admin Console UI;
- general Grafana redesign;
- new high-cardinality Loki labels;
- historical data rewrite/backfill.

---

## 8. Exact traffic unit contract

### 8.1 Accepted units after correction

```text
B
Bytes
KB
MB
GB
TB
```

Matching remains **case-insensitive**.

Accepted examples:

```text
887B
887b
887Bytes
887bytes
887BYTES
887ByTeS
1KB
1kb
1MB
1mb
1GB
1gb
1TB
1tb
```

### 8.2 Singular `Byte`

DRAFT decision:

```text
Byte = unsupported
```

Therefore:

```text
887Byte
887byte
887BYTE
```

remain invalid and produce `TRAFFIC_INVALID` when present.

Rationale: only plural `Bytes` is confirmed by supplied production evidence. Adding singular `Byte` would be an unproven parser expansion.

---

## 9. Canonical unit mapping

`Bytes` is an **input alias**, not a new normalized unit.

Canonical output vocabulary remains:

```text
B
KB
MB
GB
TB
```

Required alias mapping:

```text
B     -> B
Bytes -> B
KB    -> KB
MB    -> MB
GB    -> GB
TB    -> TB
```

after case normalization.

Thus:

```text
input: 887Bytes
reported_traffic_unit: B
reported_traffic_bytes_estimate: 887
```

Do not output `reported_traffic_unit="BYTES"`.

---

## 10. Numeric, decimal and whitespace contract

Preserve current numeric grammar:

```regex
\d+(?:\.\d+)?
```

Accepted:

```text
0B
1B
887Bytes
0.5Bytes
15.43MB
001KB
```

Not accepted:

```text
.5MB
1.MB
+1MB
-1MB
1e3B
1,5MB
NaNMB
InfinityMB
```

Decimals remain valid for `Bytes` because this is an input-unit alias under the existing common traffic grammar. Existing `Decimal × multiplier → ROUND_HALF_UP` behavior remains.

Example:

```text
0.5Bytes -> 1 byte estimate
```

Existing optional whitespace between number and unit remains accepted because the current regex uses `\s*`:

```text
887Bytes
887 Bytes
887    Bytes
15.43 MB
```

Outer whitespace is removed by existing `.strip()`. Internal number/unit whitespace remains in `reported_traffic_raw`.

No whitespace is added inside unit tokens; forms such as `By tes` remain invalid.

---

## 11. Digit / overflow contract

Current normalizer limit remains:

```text
MAX_TRAFFIC_NUMBER_DIGITS = 24
```

A numeric portion containing more than 24 digits remains invalid. `Bytes` must pass through the same limit and exception guards.

### DRAFT decision on INT64

Do not introduce a new normalizer-wide INT64 cap in this corrective TASK.

The current normalizer does not impose that cap for every accepted traffic representation. Public Traffic separately rejects values outside `0..INT64_MAX`.

Changing the normalizer's extreme-value domain would be an additional hardening change unrelated to the confirmed `887Bytes` defect. If desired, address it separately.

---

## 12. Exact `887Bytes` result

For an otherwise complete recognized offline event:

```text
reported_traffic_raw = "887Bytes"
reported_traffic_value = 887
reported_traffic_unit = "B"
reported_traffic_bytes_estimate = 887
```

and:

```text
TRAFFIC_INVALID absent
```

If no independent warnings exist:

```text
parse_status = parsed
parse_reason = null
parse_warnings = []
level = info
schema_version = 1
```

---

## 13. Independent warning aggregation

The traffic correction removes only the false traffic warning.

Example:

```text
offline event
client IP absent
traffic = 887Bytes
```

must produce:

```text
reported_traffic_bytes_estimate = 887
TRAFFIC_INVALID absent
CLIENT_IP_MISSING present
parse_status = partial
level = warning
```

Likewise:

```text
CLIENT_IP_MISSING + DURATION_INVALID + valid 887Bytes
```

remains `partial`; Grafana must classify it as an actionable warning because a real warning is present.

---

## 14. Schema-version decision

DRAFT decision:

```text
normalized webhook SCHEMA_VERSION remains 1
```

Reason:

- no field added/removed/renamed;
- no field type changed;
- no event name changed;
- no parse-status semantic changed;
- canonical unit output remains existing `B|KB|MB|GB|TB`;
- only one confirmed input alias is accepted.

Visit DB remains schema v2 unchanged.

---

## 15. Data-flow impact

```text
Omada raw webhook
  -> raw webhook journal
  -> webhook normalizer
  -> offline traffic extraction
  -> raw value preserved
  -> Bytes alias canonicalized to B
  -> Decimal/binary multiplier/ROUND_HALF_UP
  -> normalized JSONL schema v1
  -> Visit/Public Traffic/Loki consumers
```

No Omada request is introduced.

---

## 16. Visit Lifecycle impact

Current Visit Lifecycle webhook reader consumes `omada.client_offline` and reads `reported_traffic_bytes_estimate` as terminal source metadata. It does not require `parse_status=parsed` and does not use `TRAFFIC_INVALID` for Visit identity or close matching.

Therefore today `887Bytes` can still participate in Visit finalization, but traffic metadata is null.

After correction:

```text
Visit matching/open/close/finalization = unchanged
terminal traffic source metadata      = may become 887 instead of null
```

Forbidden changes include Visit matching, start, close time, finalization drift policy, recovery, reconciliation, writer coordinator and schema.

---

## 17. Public Traffic impact

Public Traffic consumes future normalized offline records and accepts `reported_traffic_bytes_estimate` only when it is an integer in `0..INT64_MAX`.

Thus corrected future `887Bytes -> 887` becomes eligible traffic under existing SSID/time rules instead of being skipped as an invalid traffic value.

This is an intended source-quality improvement, not a Public Traffic formula/storage redesign.

---

## 18. Analytics / Home Activity impact

No Home Activity or Visit Analytics formula changes.

Prospectively, future offline source facts that previously had null traffic because of the unsupported `Bytes` spelling can carry the actual byte estimate. Downstream traffic history may therefore become more complete naturally through existing source-fact pipelines.

No historical correction is performed by this TASK.

---

## 19. Observation / Current State / Admin impact

Repository review did not identify `TRAFFIC_INVALID` or `CLIENT_IP_MISSING` as a control input for Observation, Current State or Admin Console logic.

No changes are proposed there.

---

## 20. Loki / Alloy boundary

The repository's normalized webhook Alloy configuration extracts/labels only bounded fields including:

```text
job
service
module
event
level
parse_status
schema_version
```

`parse_warnings` remains inside the JSON line and is queryable after `| json`.

DRAFT decision:

```text
NO Alloy label change
NO parse_warnings Loki label
NO MAC/IP Loki labels
```

Grafana classification should be derived at query/panel interpretation time.

---

## 21. Grafana source-of-truth investigation

At baseline `9faf317...`, the repository contains:

```text
docs/omada_webhook_alloy.md
outputs/omada-webhook-normalized.alloy
```

but no identified:

```text
Grafana dashboard JSON
Grafana dashboard provisioning
Normalizer Health panel JSON
Grafana alert rule for this panel
```

Repository tree/searches did not find a canonical dashboard source.

Therefore it is not safe to invent dashboard UID, panel ID, exact existing LogQL, transformations or alert binding in this DRAFT.

Before FINAL, Owner / Tech Lead should capture the real production panel/dashboard definition or establish that it is UI-managed production-only.

---

## 22. Grafana architecture boundary

Preferred minimal architecture:

```text
normalized schema unchanged
Alloy unchanged
Loki labels unchanged
Grafana interpretation changed
```

Depending on the real production panel, the eventual change may be limited to:

```text
LogQL query/queries
panel transformations
value/display mappings
panel thresholds/labels
```

No datasource redesign, new Loki pipeline or general dashboard redesign.

Alerting stays unchanged unless review proves an existing alert depends on the same mixed Partial classification.

---

## 23. Grafana Normalizer Health classification

### A. `healthy`

```text
parse_status == parsed
```

Meaning: recognized event, no normalizer warnings.

### B. `expected_partial`

```text
parse_status == partial
AND parse_warnings non-empty
AND every warning is in EXPECTED_INFORMATIONAL_WARNINGS
```

For this TASK the allowlist is exactly:

```text
CLIENT_IP_MISSING
```

Do not add other warnings to this informational allowlist without production evidence/review.

### C. `warning`

```text
parse_status == partial
AND at least one warning is not informational
```

Examples:

```text
TRAFFIC_INVALID
DURATION_INVALID
INVALID_CLIENT_MAC
INVALID_CLIENT_IP
SSID_MISSING
CHANNEL_INVALID
AP_MAC_MISSING
```

Recommended display meaning:

```text
Parser / data-quality warning
```

because the warning taxonomy also includes timing/correlation quality issues, not only regex errors.

### D. `unclassified`

```text
parse_status == unclassified
```

`parse_reason` remains the primary diagnostic reason.

### E. `unknown`

Use for missing/unsupported `parse_status`, failed JSON extraction or internally inconsistent records that cannot be classified safely.

Unknown must not be silently treated as healthy.

---

## 24. Grafana precedence

For mixed evidence, actionable warnings win over informational warnings.

Example:

```text
parse_status = partial
parse_warnings = [CLIENT_IP_MISSING, TRAFFIC_INVALID]
```

must classify as:

```text
warning
```

not `expected_partial`.

`CLIENT_IP_MISSING` remains visible but cannot hide a real parser/data warning.

---

## 25. Grafana query principle

`parse_status` is already a Loki label. `parse_warnings` is a JSON field, not a label.

Conceptual query flow:

```text
{job="omada_webhook_normalized"}
| json
| derive operational class from parse_status + parse_warnings
```

Exact production LogQL is intentionally not frozen until the actual panel is exported and its Grafana/Loki-supported syntax is verified.

---

## 26. No parser-semantic change for dashboard cosmetics

Forbidden shortcut:

```text
CLIENT_IP_MISSING -> parsed
```

solely to reduce the Partial count.

The correct boundary is:

```text
preserve semantic signal in normalized data
improve operational interpretation in Grafana
```

---

## 27. Warning taxonomy compatibility

No new warning code is introduced for a valid `Bytes` alias.

Do not add `TRAFFIC_BYTES_ALIAS` or similar. Successful parsing is normal behavior.

`parse_reason` semantics remain unchanged.

---

## 28. Backward compatibility matrix

| Input | Supported | Canonical unit | Multiplier |
|---|---:|---|---:|
| `1B` | yes | `B` | 1 |
| `1b` | yes | `B` | 1 |
| `1KB` | yes | `KB` | 1024 |
| `1MB` | yes | `MB` | 1024² |
| `1GB` | yes | `GB` | 1024³ |
| `1TB` | yes | `TB` | 1024⁴ |
| `15.43mb` | yes | `MB` | 1024² |
| `1 MB` | yes | `MB` | 1024² |
| `887Bytes` | **new yes** | `B` | 1 |
| `887bytes` | **new yes** | `B` | 1 |
| `887 Bytes` | **new yes** | `B` | 1 |
| `887Byte` | no | — | — |

Existing accepted inputs must preserve existing numerical results.

---

## 29. Malformed/unsupported behavior

Malformed present traffic remains:

```text
raw preserved
normalized traffic fields null
TRAFFIC_INVALID present
parse_status partial
```

Examples:

```text
many-MB
887Byte
1XB
-1MB
1e3B
```

---

## 30. Historical data / backfill

DRAFT decision:

```text
NO BACKFILL
```

Do not rewrite historical normalized logs, Visit rows, Public Traffic rows or Analytics history.

Historical `887Bytes` normalized records may remain `partial` with null estimate. New records after correction use the new parser.

If historical repair is later required, create a separate explicit backfill/reconciliation task.

---

## 31. Required code/config surfaces

Expected application code change:

```text
app/integrations/omada/webhook_normalizer.py
```

Expected tests/docs:

```text
tests/integrations/omada/test_webhook_normalizer.py
docs/omada_webhook_normalizer.md
docs/modules/omada-webhook-normalizer.md
```

Possible narrow downstream regression tests only:

```text
tests/visit_lifecycle/test_webhook_finalization.py
tests/test_public_traffic.py
```

No application changes expected in Visit/Public Traffic merely for the alias.

No change expected to:

```text
outputs/omada-webhook-normalized.alloy
```

Grafana production configuration is a separate operational surface because its source is not versioned in this repository at the verified baseline.

---

## 32. Deterministic parser tests

At minimum:

1. `887Bytes` accepted.
2. `887bytes` accepted.
3. mixed-case `887ByTeS` accepted.
4. `887 Bytes` accepted under existing whitespace rule.
5. `887Byte` rejected.
6. `887B` regression.
7. KB regression.
8. MB regression.
9. GB regression.
10. TB regression.
11. existing lowercase unit regression.
12. existing `15.43mb` decimal result unchanged.
13. `0.5Bytes` follows existing ROUND_HALF_UP.
14. malformed traffic remains `TRAFFIC_INVALID`.
15. unsupported unit remains `TRAFFIC_INVALID`.
16. >24-digit numeric portion remains invalid.
17. giant input remains bounded/non-infinite.

---

## 33. Required production-like public normalization test

Do not test only private `_parse_traffic()`.

Add a test through the public `normalize_webhook()` path with an offline text maximally close to production, for example:

```text
[client:<name/mac>] (IP: <valid-ip>) went offline
from SSID "<ssid>" on [ap:<name/mac>]
(2m connected, 887Bytes).
```

Expected:

```text
event = omada.client_offline
reported_connected_raw = "2m"
reported_connected_seconds = 120
reported_traffic_raw = "887Bytes"
reported_traffic_value = 887
reported_traffic_unit = "B"
reported_traffic_bytes_estimate = 887
TRAFFIC_INVALID absent
```

With no other warnings:

```text
parse_status = parsed
parse_reason = null
parse_warnings = []
```

---

## 34. Raw preservation tests

Prove that:

```text
887Bytes
887bytes
887 Bytes
```

remain exactly those values after the existing outer trim and are not rewritten to `887B` in `reported_traffic_raw`.

---

## 35. Independent warning tests

Case:

```text
offline with no IP
(2m connected, 887Bytes)
```

Expected:

```text
bytes_estimate = 887
TRAFFIC_INVALID absent
CLIENT_IP_MISSING present
parse_status = partial
```

Case:

```text
(1x connected, 887Bytes)
```

Expected:

```text
DURATION_INVALID present
TRAFFIC_INVALID absent
parse_status = partial
```

Case:

```text
(2m connected, many-MB)
```

Expected:

```text
TRAFFIC_INVALID present
```

---

## 36. Visit/Public Traffic regressions

### Visit Lifecycle

A normalized offline event carrying `reported_traffic_bytes_estimate=887` must preserve current Visit close/match behavior and store the traffic source fact where the current pipeline already does so.

No Visit semantic modification is allowed.

### Public Traffic

A normalized offline record with `reported_traffic_bytes_estimate=887` must remain accepted under current INT64/SSID/time rules.

Existing null/out-of-range skip behavior stays unchanged.

---

## 37. Grafana classification acceptance cases

| `parse_status` | `parse_warnings` | Expected operational class |
|---|---|---|
| `parsed` | `[]` | healthy |
| `partial` | `[CLIENT_IP_MISSING]` | expected_partial |
| `partial` | `[TRAFFIC_INVALID]` | warning |
| `partial` | `[CLIENT_IP_MISSING, TRAFFIC_INVALID]` | warning |
| `unclassified` | any | unclassified |
| missing/unknown | — | unknown |

These cases must be validated against the real production panel/query once its source is captured.

---

## 38. Grafana testability boundary

Because no versioned production Grafana dashboard is present in the repository, repository tests cannot truthfully claim to validate the production panel today.

Before FINAL, prefer one of:

### A. Export/capture dashboard/panel

Provide dashboard JSON or equivalent evidence. FINAL can then freeze exact LogQL/transformation/value mappings and test/acceptance steps.

### B. UI-managed production-only dashboard

If it remains production-only, FINAL should define Owner-controlled operational acceptance using known sample records/time windows and a dashboard backup/export before mutation.

Do not invent dashboard JSON.

---

## 39. Functional acceptance

Input:

```text
(... 2m connected, 887Bytes)
```

Required normalized result:

```text
reported_traffic_raw = "887Bytes"
reported_traffic_value = 887
reported_traffic_unit = "B"
reported_traffic_bytes_estimate = 887
TRAFFIC_INVALID absent
```

With no other warnings:

```text
parse_status = parsed
parse_reason = null
parse_warnings = []
schema_version = 1
```

---

## 40. Compatibility acceptance

Must preserve:

```text
B/KB/MB/GB/TB
case-insensitive matching
existing decimals
existing number/unit whitespace
binary multipliers
ROUND_HALF_UP
24-digit numeric guard
malformed warning behavior
```

No schema bump.

---

## 41. Downstream acceptance

Must demonstrate no semantic changes to:

```text
Auth
CAPPORT
Omada integration contract
Visit open/close/matching/finalization
Visit schema v2
Observation
Current State
Home Activity formulas
Admin UI
```

Allowed intended improvement:

```text
future 887Bytes -> future normalized traffic fact 887
```

---

## 42. Loki/Grafana acceptance

Alloy/Loki labels remain bounded and unchanged.

Grafana must show:

```text
parsed -> healthy
partial + only CLIENT_IP_MISSING -> expected/informational partial
partial + TRAFFIC_INVALID -> parser/data-quality warning
mixed informational + real warning -> warning
unclassified -> unclassified/diagnostic
missing/invalid classification -> unknown
```

No normalized warning is removed merely for presentation.

---

## 43. Rollback

### Parser

Schema remains v1; rollback requires no schema downgrade. Rollback simply makes future `Bytes` records invalid again. Already-produced corrected schema-v1 records remain valid.

### Grafana

Before any production panel change, export/backup current dashboard/panel. Rollback restores prior query/transformation/value mapping. No Loki data mutation and no Alloy rollback should be required.

---

## 44. Repository/action restrictions

This DRAFT does not authorize:

```text
repository modification
branch creation
commit/push
PR
merge
deploy
Grafana production change
backfill
```

---

## 45. Open questions for Owner / Tech Lead review

Only Grafana evidence gaps remain.

### Q1. Canonical production Grafana source

Where is it actually managed?

```text
Grafana UI
external dashboard JSON
external provisioning repository
other configuration source
```

### Q2. Exact Normalizer Health panel

Need capture:

```text
dashboard UID/name
panel ID/title
current LogQL
transformations
value mappings/thresholds
alert linkage
```

### Q3. Alerting

Does any alert depend on the existing mixed Partial classification? If yes, Owner / Tech Lead must explicitly decide whether it changes in the same TASK.

No parser-side architecture question remains.

---

## 46. Recommended FINAL direction after review

Unless production Grafana evidence contradicts this DRAFT, FINAL should preserve:

```text
Bytes accepted as input alias
Byte unsupported
Bytes canonicalized to B in normalized unit only
raw representation preserved
schema v1 unchanged
CLIENT_IP_MISSING remains partial in normalizer
Grafana separates informational partial from actionable warning
parse_warnings remains JSON, not Loki label
NO BACKFILL
Visit/Auth/Omada/Home Activity semantics unchanged
```

---

## 47. Required next step

Owner / Tech Lead reviews this DRAFT and, if possible, supplies/exports the current production Normalizer Health panel/dashboard evidence.

Then Architect prepares:

```text
TASK-OMADA-WEBHOOK-TRAFFIC-BYTES-01-FINAL.md
```

Only FINAL may be passed to coder/operator.
