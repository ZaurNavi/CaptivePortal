# TASK-OMADA-WEBHOOK-TRAFFIC-BYTES-01 — Omada Webhook `Bytes` Traffic Alias + Grafana Normalizer Health Polish — FINAL

**Project:** CaptivPortal  
**Type:** corrective parser compatibility + engineering observability polish  
**Status:** `FINAL SPECIFICATION`  
**Architecture direction:** `PASS`  
**Implementation authorization:** `NOT GRANTED BY THIS DOCUMENT`  
**Branch / code / commit / push / PR / merge:** `NOT GRANTED BY THIS DOCUMENT`  
**Production parser deployment:** `SEPARATE OWNER AUTHORIZATION REQUIRED`  
**Production Grafana modification:** `OWNER / TECH LEAD ONLY`  
**Repository:** `ZaurNavi/CaptivePortal`  
**Exact verified implementation baseline:** `origin/main@9faf31716f93f78325926c9294e9467838f22496`  
**Baseline re-check:** `2026-08-27` — unchanged  
**Normalized webhook schema:** `v1` — MUST remain unchanged  
**Visit DB schema:** `v2` — MUST remain unchanged  
**Production Grafana baseline:** dashboard id `30`, uid `captive-portal-auth-v3-fixed`, version `55`  
**Production dashboard title:** `Captive Portal — Welcome & Zefer_Parki`

---

# 0. Final executive decision

This FINAL closes the production parser defect where Omada can report offline traffic as:

```text
887Bytes
```

while the current normalizer accepts only:

```text
B
KB
MB
GB
TB
```

The final parser decision is:

```text
Bytes = supported input alias for canonical unit B
Byte  = unsupported
```

For:

```text
887Bytes
```

the normalized output MUST be:

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

If there are no independent warnings:

```text
parse_status = parsed
parse_reason = null
parse_warnings = []
level = info
schema_version = 1
```

The same task also corrects the interpretation of Normalizer Health in the captured production Grafana dashboard.

The normalizer contract itself is NOT changed for:

```text
CLIENT_IP_MISSING
```

It remains a real normalized warning and therefore keeps:

```text
parse_status = partial
level = warning
```

Grafana must distinguish that expected controller incompleteness from actionable parser/data-quality warnings and from unclassified diagnostic events.

No historical normalized data is rewritten.

---

# 1. Decisions closed by review

The following decisions are FINAL and MUST NOT be reopened during implementation unless the exact repository baseline directly contradicts them:

```text
1. Bytes is accepted as an input alias.
2. Byte remains unsupported.
3. Bytes canonicalizes to B.
4. reported_traffic_raw preserves the current trimmed source representation.
5. normalized webhook schema remains v1.
6. CLIENT_IP_MISSING remains a normalizer partial warning.
7. No Alloy/Loki label changes.
8. No backfill.
9. Visit semantics do not change.
10. Auth semantics do not change.
11. CAPPORT semantics do not change.
12. Home Activity formulas do not change.
13. Grafana production modification is Owner / Tech Lead owned.
14. Coder does not modify production Grafana.
15. No duplicate normalizer module document is created.
```

---

# 2. Exact repository baseline

Implementation, when separately authorized, MUST begin from:

```text
origin/main@9faf31716f93f78325926c9294e9467838f22496
```

At FINAL preparation this remains current `main`.

If `origin/main` changes before implementation authorization:

1. record the new exact SHA;
2. compare at minimum:
   - `app/integrations/omada/webhook_normalizer.py`;
   - `tests/integrations/omada/**`;
   - `app/visit_lifecycle/webhook_reader.py`;
   - `app/public_traffic/**`;
   - `docs/omada_webhook_normalizer.md`;
   - `outputs/omada-webhook-normalized.alloy`;
3. if parser/output/warning/downstream contracts changed, STOP for Tech Lead impact review;
4. otherwise rebind the execution baseline without reopening settled product decisions.

---

# 3. Confirmed current normalizer contract

Canonical implementation:

```text
app/integrations/omada/webhook_normalizer.py
```

Current constants include:

```text
SCHEMA_VERSION = 1
MAX_TRAFFIC_NUMBER_DIGITS = 24
```

Current traffic grammar is equivalent to:

```regex
^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>B|KB|MB|GB|TB)$
```

with case-insensitive matching.

Current binary multipliers:

```text
B  = 1
KB = 1024
MB = 1024^2
GB = 1024^3
TB = 1024^4
```

Current arithmetic uses:

```text
Decimal
ROUND_HALF_UP
```

and produces:

```text
reported_traffic_bytes_estimate
```

as integer bytes.

No new normalized field is needed.

---

# 4. Existing offline traffic fields

Recognized offline events already expose:

```text
reported_connected_raw
reported_connected_seconds
reported_traffic_raw
reported_traffic_value
reported_traffic_unit
reported_traffic_bytes_estimate
```

The task changes only accepted input spelling for one known unit alias.

It does NOT change output field names or types.

---

# 5. Raw-value contract

Current offline parsing stores:

```text
traffic_match.group("traffic").strip()
```

as:

```text
reported_traffic_raw
```

Therefore the canonical raw contract remains:

```text
controller traffic representation after the existing outer trim
```

Examples:

```text
887Bytes   -> reported_traffic_raw = "887Bytes"
887bytes   -> reported_traffic_raw = "887bytes"
887 Bytes  -> reported_traffic_raw = "887 Bytes"
```

Forbidden:

```text
reported_traffic_raw = "887B"
```

for an input that was actually `887Bytes`.

Canonicalization applies only to normalized semantic fields, not the raw representation.

---

# 6. Final traffic-unit contract

## 6.1 Accepted units

After the correction, accepted input unit spellings are:

```text
B
Bytes
KB
MB
GB
TB
```

Matching remains case-insensitive.

Required accepted variants include:

```text
887B
887b
887Bytes
887bytes
887BYTES
887ByTeS
887 Bytes
1KB
1kb
1MB
1mb
1GB
1gb
1TB
1tb
```

## 6.2 Unsupported singular alias

The singular spelling:

```text
Byte
```

remains unsupported.

Examples:

```text
887Byte
887byte
887BYTE
```

remain invalid present traffic representations and therefore produce `TRAFFIC_INVALID`.

Reason:

```text
production evidence confirms Bytes;
production evidence does not confirm Byte;
this TASK does not broaden the parser speculatively.
```

---

# 7. Canonical normalized unit mapping

Canonical output-unit vocabulary remains exactly:

```text
B
KB
MB
GB
TB
```

Alias mapping:

```text
input B      -> canonical B
input Bytes  -> canonical B
input KB     -> canonical KB
input MB     -> canonical MB
input GB     -> canonical GB
input TB     -> canonical TB
```

after case normalization.

Forbidden new canonical value:

```text
BYTES
Bytes
```

in `reported_traffic_unit`.

---

# 8. Number, decimal, whitespace and multiplier semantics

The task preserves current numeric syntax:

```regex
\d+(?:\.\d+)?
```

Examples accepted under the existing contract:

```text
0B
1B
887Bytes
0.5Bytes
15.43MB
001KB
```

Examples still unsupported:

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

Optional whitespace between numeric value and unit remains accepted:

```text
887Bytes
887 Bytes
887    Bytes
15.43 MB
```

Binary multiplier semantics remain unchanged.

Decimal handling remains uniform across every accepted unit, including `Bytes`.

Example:

```text
0.5Bytes
Decimal("0.5") * 1
ROUND_HALF_UP
-> 1 byte
```

No special integer-only rule is introduced for `Bytes`.

---

# 9. Digit / extreme-value contract

The existing limit remains:

```text
MAX_TRAFFIC_NUMBER_DIGITS = 24
```

A numeric portion with more than 24 digits remains invalid.

The new alias passes through the same protection.

Existing exception handling remains authoritative for:

```text
InvalidOperation
ValueError
OverflowError
non-finite float representation
```

No new global INT64 cap is added to the normalizer in this task.

Public Traffic already performs its own current INT64 acceptance check. Expanding this task into a cross-pipeline integer-domain change is forbidden.

---

# 10. Exact `887Bytes` output contract

For an otherwise complete recognized offline event containing:

```text
(... 2m connected, 887Bytes)
```

required fields:

```text
reported_connected_raw = "2m"
reported_connected_seconds = 120

reported_traffic_raw = "887Bytes"
reported_traffic_value = 887
reported_traffic_unit = "B"
reported_traffic_bytes_estimate = 887
```

and:

```text
TRAFFIC_INVALID absent
```

If no unrelated warnings exist:

```text
parse_status = "parsed"
parse_reason = null
parse_warnings = []
level = "info"
schema_version = 1
```

---

# 11. Parse status and independent-warning contract

Current recognized-event semantics remain:

```text
warnings empty
-> parse_status = parsed
-> level = info
-> parse_reason = null

warnings non-empty
-> parse_status = partial
-> level = warning
-> parse_reason = null
```

Unclassified diagnostics remain:

```text
parse_status = unclassified
parse_reason = diagnostic reason
level = warning
```

Successful parsing of `Bytes` removes only the false traffic warning.

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

remains `partial`.

No real warning may be hidden to force `parsed`.

---

# 12. `CLIENT_IP_MISSING` final semantic decision

Do NOT change the normalizer contract.

A recognized online/offline event with no client IP remains:

```text
client_ip = null
parse_warnings contains CLIENT_IP_MISSING
parse_status = partial
parse_reason = null
level = warning
```

Meaning:

```text
recognized event
+
controller/correlation data incomplete
```

It is not automatically a parser defect.

The diagnostic distinction is implemented in Grafana interpretation, not by weakening source semantics.

---

# 13. `TRAFFIC_INVALID` final semantic decision

If traffic text is present but cannot be parsed under the accepted grammar:

```text
reported_traffic_raw = preserved trimmed source
reported_traffic_value = null
reported_traffic_unit = null
reported_traffic_bytes_estimate = null
parse_warnings contains TRAFFIC_INVALID
parse_status = partial
```

Traffic entirely absent remains allowed under the current offline contract and does not itself add `TRAFFIC_INVALID`.

After this task, `Bytes` is no longer an invalid spelling.

---

# 14. Schema decision

Final decision:

```text
SCHEMA_VERSION remains 1
```

Reason:

- no field added;
- no field removed;
- no field renamed;
- no field type changed;
- no event name changed;
- no parse-status semantics changed;
- canonical unit vocabulary remains `B|KB|MB|GB|TB`;
- one confirmed input alias is added only.

Visit schema remains:

```text
v2
```

No migration is allowed.

---

# 15. Data-flow impact

```text
Omada raw webhook
  -> raw webhook journal
  -> webhook normalizer
  -> offline traffic extraction
  -> raw representation preserved
  -> Bytes alias canonicalized to B
  -> Decimal / binary multiplier / ROUND_HALF_UP
  -> normalized JSONL schema v1
  -> existing Visit / Public Traffic / Loki consumers
```

No Omada request is introduced.

---

# 16. Visit Lifecycle impact

Visit Lifecycle consumes normalized:

```text
omada.client_offline
```

and may read:

```text
reported_traffic_bytes_estimate
```

as terminal traffic source metadata.

The current matching/finalization path does not depend on `TRAFFIC_INVALID` as Visit identity.

Therefore current `887Bytes` behavior can still close a Visit while traffic metadata is null.

After the correction:

```text
Visit open/close/match/finalization semantics = unchanged
terminal reported traffic metadata            = may become 887 instead of null
```

Forbidden Visit changes:

```text
Visit start
Visit reuse
Visit close matching
close timestamp selection
finalization drift policy
reconciliation
writer coordinator
reader checkpoint semantics
Visit schema
```

---

# 17. Public Traffic impact

Public Traffic already consumes:

```text
reported_traffic_bytes_estimate
```

and independently validates its numeric domain.

Therefore future:

```text
887Bytes -> 887
```

becomes eligible traffic data under the existing SSID/time/INT64 contract.

This is an intended source-quality improvement.

No Public Traffic formula, DB schema or source-selection semantics change.

---

# 18. Analytics / Home Activity impact

No Analytics or Home Activity formula changes.

Prospective effect only:

```text
future offline source fact
that previously had null traffic due only to Bytes spelling
can now persist numeric traffic evidence
```

This may naturally improve future historical traffic completeness through existing pipelines.

No historical correction is performed.

---

# 19. Observation / Current State / Admin boundary

No changes to:

```text
Observation
Current State
Admin Console UI/API
```

are required by the parser correction.

`TRAFFIC_INVALID` and `CLIENT_IP_MISSING` remain engineering normalizer evidence, not control inputs for these product layers.

---

# 20. Loki / Alloy invariant

Existing normalized webhook ingestion labels remain unchanged:

```text
job
service
module
event
level
parse_status
schema_version
```

Do NOT add as Loki labels:

```text
parse_warnings
client_mac
client_ip
ssid
```

for this task.

`parse_warnings` remains inside the JSON log line.

No change to:

```text
outputs/omada-webhook-normalized.alloy
```

is required.

---

# 21. Loki 2.9.8 `parse_warnings` compatibility proof

This FINAL corrects an important assumption from the DRAFT.

## 21.1 Real normalized record representation

Captured real normalized production records store:

```json
"parse_warnings":["CLIENT_IP_MISSING"]
```

as a JSON array.

This is not a scalar string field.

## 21.2 Loki 2.9.x parser behavior

For Loki 2.9.x:

```text
plain | json
```

extracts scalar/nested properties but intentionally skips arrays.

Therefore this is NOT a valid architecture assumption:

```text
| json
| parse_warnings=...
```

when `parse_warnings` is an array.

Loki 2.9.x supports parameterized JSON extraction:

```logql
| json warnings="parse_warnings"
```

When the selected expression returns an array, Loki exposes the extracted label in JSON format.

For the real source shape:

```json
["CLIENT_IP_MISSING"]
```

canonical query-time label value becomes:

```text
["CLIENT_IP_MISSING"]
```

This is the FINAL compatible strategy.

## 21.3 Query-time extraction contract

When warning semantics are needed, use parameterized extraction, conceptually:

```logql
| json client_mac="client_mac", ssid="ssid", warnings="parse_warnings"
| __error__=""
```

Then apply exact/regex label filters to `warnings`.

Do not add an ingestion-time Loki label solely to solve this query.

---

# 22. Captured production Grafana source

This task is bound to the captured production dashboard:

```text
Title:      Captive Portal — Welcome & Zefer_Parki
UID:        captive-portal-auth-v3-fixed
Dashboard:  30
Version:    55
Grafana:    12.3.0 panel metadata
Datasource: Loki
```

The application repository is not treated as the canonical owner of this production dashboard.

For this task:

```text
captured/exported production dashboard v55
=
operational change baseline
```

No repository dashboard provisioning source is introduced.

---

# 23. Current Panel 48 baseline

Panel:

```text
id: 48
title: Partial / unknown
type: stat
```

Current query:

```logql
sum(count_over_time(
  {job="omada_webhook_normalized",
   parse_status=~"partial|unclassified"}
  | json
  | client_mac!~"${exclude_noisy_mac:raw}"
  | ssid=~"${traffic_ssid:raw}"
  [$__range]
))
```

Current problem:

```text
expected CLIENT_IP_MISSING-only partial
+
actionable partial warning
+
unclassified intent
```

are represented by one ambiguous stat concept.

Also, unclassified records cannot safely be SSID-attributed through normalized `ssid` if parsing did not produce that field.

---

# 24. FINAL target for Panel 48

Panel 48 becomes the fast actionable counter.

Keep:

```text
id = 48
type = stat
grid position
noValue behavior
existing thresholds:
  0 -> green
  1 -> orange
  20 -> red
```

Change title to:

```text
Parser / data warnings
```

Change description to the semantic equivalent of:

```text
Recognized partial events that contain at least one actionable
parser/data-quality warning.
CLIENT_IP_MISSING-only events and unclassified diagnostics are excluded.
```

## 24.1 Exact target query

```logql
sum(
  count_over_time(
    {job="omada_webhook_normalized",
     service="captive_portal",
     module="omada_webhook_normalizer",
     parse_status="partial"}
    | json client_mac="client_mac", ssid="ssid", warnings="parse_warnings"
    | __error__=""
    | client_mac!~"${exclude_noisy_mac:raw}"
    | ssid=~"${traffic_ssid:raw}"
    | warnings=~`\[.+\]`
    | warnings!=`["CLIENT_IP_MISSING"]`
    [$__range]
  )
)
```

## 24.2 Panel 48 semantics

Counted:

```text
partial + ["TRAFFIC_INVALID"]
partial + ["DURATION_INVALID"]
partial + ["CLIENT_IP_MISSING","TRAFFIC_INVALID"]
partial + any other non-empty warning array that is not exactly CLIENT_IP_MISSING-only
```

Not counted:

```text
parsed
partial + ["CLIENT_IP_MISSING"] only
unclassified
```

The panel therefore becomes actionable rather than an aggregate of unrelated meanings.

---

# 25. Current Panel 55 baseline

Panel:

```text
id: 55
title: Статусы разбора
type: barchart
```

Current query groups only by raw stream label:

```logql
sum by (parse_status) (
  count_over_time(
    {job="omada_webhook_normalized",
     service="captive_portal",
     module="omada_webhook_normalizer"}
    | json
    | client_mac!~"${exclude_noisy_mac:raw}"
    | ssid=~"${traffic_ssid:raw}"
    [$__range]
  )
)
```

This cannot distinguish:

```text
expected partial
vs
actionable partial
```

because both have raw:

```text
parse_status = partial
```

---

# 26. FINAL target for Panel 55

Panel 55 becomes the diagnostic distribution panel.

Keep:

```text
id = 55
title = Статусы разбора
type = barchart
grid position
existing palette-based presentation
```

Replace the single raw-status grouped query with four fixed semantic series.

Panel description MUST explicitly explain:

```text
Parsed, expected CLIENT_IP_MISSING-only partial,
actionable parser/data warnings, and unclassified diagnostics are separate.
Recognized classes follow the dashboard SSID/noisy-MAC filters.
Unclassified is intentionally a whole normalized-stream diagnostic count
because an unclassified record cannot be safely assigned to SSID/MAC
without re-parsing raw text.
```

No raw-text re-parsing is allowed merely to assign an unclassified record to an SSID.

---

# 27. Panel 55 query A — Parsed / healthy

Legend:

```text
Parsed / healthy
```

Exact query:

```logql
sum(
  count_over_time(
    {job="omada_webhook_normalized",
     service="captive_portal",
     module="omada_webhook_normalizer",
     parse_status="parsed"}
    | json client_mac="client_mac", ssid="ssid"
    | __error__=""
    | client_mac!~"${exclude_noisy_mac:raw}"
    | ssid=~"${traffic_ssid:raw}"
    [$__range]
  )
)
```

Meaning:

```text
recognized event with no warnings
within the selected recognized-event dashboard scope
```

---

# 28. Panel 55 query B — Expected partial

Legend:

```text
Expected partial / IP missing
```

Exact query:

```logql
sum(
  count_over_time(
    {job="omada_webhook_normalized",
     service="captive_portal",
     module="omada_webhook_normalizer",
     parse_status="partial"}
    | json client_mac="client_mac", ssid="ssid", warnings="parse_warnings"
    | __error__=""
    | client_mac!~"${exclude_noisy_mac:raw}"
    | ssid=~"${traffic_ssid:raw}"
    | warnings=`["CLIENT_IP_MISSING"]`
    [$__range]
  )
)
```

Meaning:

```text
recognized event
+
only known informational/controller-incompleteness warning
+
no actionable warning
```

The informational allowlist for this task is exactly:

```text
CLIENT_IP_MISSING
```

No additional warning may be silently added to this category.

---

# 29. Panel 55 query C — Parser / data warning

Legend:

```text
Parser / data warning
```

Exact query:

```logql
sum(
  count_over_time(
    {job="omada_webhook_normalized",
     service="captive_portal",
     module="omada_webhook_normalizer",
     parse_status="partial"}
    | json client_mac="client_mac", ssid="ssid", warnings="parse_warnings"
    | __error__=""
    | client_mac!~"${exclude_noisy_mac:raw}"
    | ssid=~"${traffic_ssid:raw}"
    | warnings=~`\[.+\]`
    | warnings!=`["CLIENT_IP_MISSING"]`
    [$__range]
  )
)
```

Meaning:

```text
recognized partial event
+
at least one warning outside the sole informational case
```

Mixed case:

```json
["CLIENT_IP_MISSING","TRAFFIC_INVALID"]
```

MUST land here.

Actionable warning always wins over informational warning.

---

# 30. Panel 55 query D — Unclassified / diagnostic

Legend:

```text
Unclassified / diagnostic
```

Exact query:

```logql
sum(
  count_over_time(
    {job="omada_webhook_normalized",
     service="captive_portal",
     module="omada_webhook_normalizer",
     parse_status="unclassified"}
    [$__range]
  )
)
```

Meaning:

```text
normalizer could not classify/fully interpret the webhook item
parse_reason remains the source diagnostic reason
```

This series intentionally does NOT apply:

```text
traffic_ssid
exclude_noisy_mac
```

because those parsed fields may not safely exist on an unclassified record.

Do NOT inspect/reparse `raw_text` in Grafana to guess SSID or MAC solely to force scope symmetry.

The legend/description must make the scope distinction explicit.

---

# 31. Grafana `unknown` semantics

No synthetic fifth normalized event class is introduced.

Canonical source statuses remain:

```text
parsed
partial
unclassified
```

Grafana query failures, JSON pipeline errors or no-data conditions are operational dashboard conditions, not new normalized events.

Therefore the ambiguous word:

```text
unknown
```

is removed from Panel 48's title.

An actual query/pipeline failure must remain visible as Grafana error/N/A and MUST NOT be converted into a healthy zero by a new data query trick.

`unclassified` remains the normalized diagnostic-failure category.

---

# 32. Grafana alerting decision

The captured dashboard v55 contains no panel alert object on Panel 48 or Panel 55 and no dashboard-level alert definition for these panels.

Final decision:

```text
NO alerting change in this TASK
```

Do not add:

```text
Grafana alert rule
notification route
contact point
threshold redesign
```

as part of this correction.

Panel 48's existing display thresholds remain presentation thresholds only.

---

# 33. Grafana provisioning / repository decision

Final boundary:

```text
production dashboard modification = Owner / Tech Lead operational action
```

This task does NOT create:

```text
Grafana provisioning files
repository dashboard JSON as a new runtime authority
new datasource
new Loki pipeline
new recording rule
```

Before production modification, Owner / Tech Lead must export/backup the exact current dashboard v55.

After modification, record:

```text
previous dashboard version = 55
resulting saved dashboard version
exact modified panel IDs = 48, 55
backup/export artifact
live acceptance evidence
```

---

# 34. Execution ownership split

## 34.1 Coder ownership

Coder scope, only after separate Owner implementation authorization:

```text
parser implementation
parser tests
normalizer regression tests
downstream regression evidence
exact patch/commit handoff
```

Coder is NOT authorized by this FINAL to:

```text
modify production Grafana
import/export production Grafana
change panel queries in production
change Loki/Alloy configuration
deploy parser to production
run backfill
```

## 34.2 Owner / Tech Lead ownership

Owner / Tech Lead owns:

```text
production dashboard backup/export
Panel 48 modification
Panel 55 modification
live LogQL validation
live Grafana acceptance
production parser deployment/rollback decisions
```

## 34.3 Knowledge Base Lead ownership

After code and production acceptance, Knowledge Base Lead reconciles documentation against accepted current state.

Canonical normalizer document is:

```text
docs/omada_webhook_normalizer.md
```

Do NOT create:

```text
docs/modules/omada-webhook-normalizer.md
```

or any second document with the same responsibility.

Broad KB reconciliation is post-acceptance and is not a Coder scope-expansion requirement.

---

# 35. Expected application code surface

Expected runtime implementation change:

```text
app/integrations/omada/webhook_normalizer.py
```

Expected test surface:

```text
tests/integrations/omada/test_webhook_normalizer.py
```

Narrow downstream regression test edits are permitted only if needed to prove compatibility, for example existing tests under:

```text
tests/visit_lifecycle/**
tests/test_public_traffic.py
```

No runtime application change is expected in Visit/Public Traffic merely for the alias.

No Alloy change.

No Admin change.

No Grafana repository change.

---

# 36. Documentation boundary

Canonical repository document:

```text
docs/omada_webhook_normalizer.md
```

No duplicate module document.

Final workflow preference:

```text
code acceptance
-> forward production acceptance
-> Grafana operational acceptance
-> Knowledge Base Lead reconciliation
```

If a narrow same-artifact documentation line is required by repository checks, it may update only the existing canonical document. It must not create a duplicate responsibility.

---

# 37. Required deterministic parser tests

At minimum:

1. `887Bytes` accepted.
2. `887bytes` accepted.
3. `887BYTES` accepted.
4. mixed-case `887ByTeS` accepted.
5. `887 Bytes` accepted under current whitespace rule.
6. `887Byte` rejected.
7. `887B` regression unchanged.
8. `1KB` regression unchanged.
9. `1MB` regression unchanged.
10. `1GB` regression unchanged.
11. `1TB` regression unchanged.
12. lowercase existing units unchanged.
13. existing decimal `15.43mb` result unchanged.
14. `0.5Bytes` follows current ROUND_HALF_UP.
15. malformed traffic remains `TRAFFIC_INVALID`.
16. unsupported unit remains `TRAFFIC_INVALID`.
17. >24-digit numeric portion remains invalid.
18. giant input remains bounded/non-infinite and does not raise outward.
19. raw representation remains preserved for `Bytes` variants.
20. schema version remains `1`.

---

# 38. Required public normalization-path test

Do NOT rely only on direct/private `_parse_traffic()` testing.

Use public:

```text
normalize_webhook()
```

with a production-like offline text containing:

```text
[client:<name/mac>] (IP: <valid-ip>) went offline
from SSID "<ssid>" on [ap:<name/mac>]
(2m connected, 887Bytes).
```

Required assertions:

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

If no other warnings:

```text
parse_status = parsed
parse_reason = null
parse_warnings = []
```

---

# 39. Required independent-warning tests

## 39.1 `CLIENT_IP_MISSING` + valid Bytes

Input concept:

```text
offline
no IP
(2m connected, 887Bytes)
```

Expected:

```text
reported_traffic_bytes_estimate = 887
TRAFFIC_INVALID absent
CLIENT_IP_MISSING present
parse_status = partial
```

## 39.2 Other warning + valid Bytes

Example:

```text
(1x connected, 887Bytes)
```

Expected:

```text
DURATION_INVALID present
TRAFFIC_INVALID absent
parse_status = partial
```

## 39.3 Invalid traffic regression

Example:

```text
(2m connected, many-MB)
```

Expected:

```text
TRAFFIC_INVALID present
reported_traffic_bytes_estimate = null
```

---

# 40. Required downstream regression evidence

## 40.1 Visit Lifecycle

Prove that a normalized offline event carrying:

```text
reported_traffic_bytes_estimate = 887
```

preserves existing Visit close/match behavior and stores the traffic source fact where current code already does so.

Do NOT modify Visit matching to satisfy this test.

## 40.2 Public Traffic

Prove that:

```text
omada.client_offline
reported_traffic_bytes_estimate = 887
```

remains accepted under existing SSID/time/INT64 rules.

Existing null/out-of-range skip behavior remains unchanged.

## 40.3 Negative architecture regression

No new call/control path may appear in:

```text
Auth
CAPPORT
Omada provider/controller contract
Observation
Current State
Home Activity
Admin Web
```

---

# 41. Coder targeted gate

When implementation is separately authorized, Coder must run focused tests sufficient for the changed surfaces.

At minimum:

```text
normalizer tests
webhook-related focused integration tests
Visit finalization regression relevant to traffic metadata
Public Traffic regression relevant to normalized offline traffic
```

Also:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
```

Coder returns exact:

```text
baseline SHA
candidate commit/patch identity
files changed
passed/skipped/failed
compileall
 diff-check
working tree state
```

Coder does not need to perform production Grafana work.

---

# 42. Exact-artifact / code acceptance — Gate A

This gate is independent from production observation and Grafana.

PASS requires all of the following on the exact candidate artifact:

```text
Bytes accepted
Byte rejected
Bytes -> canonical B
raw preserved
schema v1 unchanged
existing units unchanged
existing decimal/case/whitespace behavior unchanged
independent warnings preserved
no new normalizer warning code
no backfill code/path introduced
Visit semantics unchanged
Public Traffic semantics unchanged
no Alloy label/config change
no production Grafana change in code artifact
no duplicate docs/modules normalizer document
```

Required test evidence:

```text
focused Coder gate PASS
Tech Lead diff review PASS
Central Lab / official full exact-artifact regression PASS
compileall PASS
git diff --check PASS
```

No merge/production acceptance is implied solely by Gate A.

---

# 43. Forward production parser acceptance — Gate B

Owner-controlled and only after a separately authorized deployment.

This is prospective acceptance only.

Do NOT backfill old events.

## 43.1 Required evidence

Observe a NEW production normalized event produced by the corrected runtime from a real Omada offline webhook whose raw traffic representation is:

```text
<value>Bytes
```

For the original confirmed case shape, expected:

```text
reported_traffic_raw = "887Bytes"
reported_traffic_value = 887
reported_traffic_unit = "B"
reported_traffic_bytes_estimate = 887
TRAFFIC_INVALID absent
```

If there are no independent warnings:

```text
parse_status = parsed
```

If `CLIENT_IP_MISSING` or another unrelated warning exists:

```text
parse_status may remain partial
but TRAFFIC_INVALID must still be absent
```

## 43.2 If no new `Bytes` event occurs naturally

Do NOT fabricate production proof and do NOT rewrite history.

Record:

```text
Gate B = PENDING REAL BYTES EVIDENCE
```

This is not a code regression by itself if Gate A is green.

---

# 44. Grafana operational acceptance — Gate C

Owner / Tech Lead only.

Before any edit:

```text
export/backup dashboard id 30 / uid captive-portal-auth-v3-fixed / version 55
```

Then modify only Panels:

```text
48
55
```

under this task.

## 44.1 Loki array extraction proof in production

Before saving final production panel queries, use real normalized records and confirm parameterized extraction:

```logql
{job="omada_webhook_normalized",parse_status="partial"}
| json warnings="parse_warnings", client_mac="client_mac", ssid="ssid"
| __error__=""
| warnings!=""
```

Inspect a known `CLIENT_IP_MISSING` record and confirm the query-time value is represented as JSON-array text equivalent to:

```text
["CLIENT_IP_MISSING"]
```

This is an execution verification of the already-fixed Loki 2.9.8 strategy, not an architecture choice.

If the real production Loki returns a materially different representation:

```text
STOP
DO NOT improvise another production query
RETURN exact output to Tech Lead
```

## 44.2 Panel 48 acceptance

Known `CLIENT_IP_MISSING`-only partial events:

```text
must NOT increase Panel 48
```

Known actionable partial events such as `TRAFFIC_INVALID`:

```text
must increase Panel 48 within selected dashboard scope
```

Mixed:

```text
CLIENT_IP_MISSING + TRAFFIC_INVALID
```

must increase Panel 48.

## 44.3 Panel 55 acceptance

Panel 55 must expose separate series:

```text
Parsed / healthy
Expected partial / IP missing
Parser / data warning
Unclassified / diagnostic
```

No single raw `partial` bar may remain as the only partial interpretation.

## 44.4 Diagnostic-scope acceptance

`Unclassified / diagnostic` must be visibly documented as whole normalized-stream evidence rather than falsely SSID-attributed.

No raw-text re-parsing to guess SSID/MAC.

## 44.5 Query failure behavior

A malformed/broken LogQL query must surface as Grafana error/N/A.

It must not be hidden as a synthetic healthy zero.

## 44.6 Save evidence

Record:

```text
previous version = 55
new saved dashboard version
Panel 48 final query
Panel 55 final queries
screenshots or exported JSON evidence
selected time range
known sample record IDs/timestamps where practical
```

---

# 45. Backward compatibility matrix

| Input | Accepted | Canonical unit | Multiplier |
|---|---:|---|---:|
| `1B` | yes | `B` | 1 |
| `1b` | yes | `B` | 1 |
| `1KB` | yes | `KB` | 1024 |
| `1kb` | yes | `KB` | 1024 |
| `1MB` | yes | `MB` | 1024² |
| `1GB` | yes | `GB` | 1024³ |
| `1TB` | yes | `TB` | 1024⁴ |
| `15.43mb` | yes | `MB` | 1024² |
| `1 MB` | yes | `MB` | 1024² |
| `887Bytes` | **new yes** | `B` | 1 |
| `887bytes` | **new yes** | `B` | 1 |
| `887 Bytes` | **new yes** | `B` | 1 |
| `887Byte` | no | — | — |

Existing accepted inputs MUST preserve exact current numerical results.

---

# 46. Malformed / unsupported traffic

Malformed present traffic continues to produce:

```text
reported_traffic_raw = current trimmed source representation
reported_traffic_value = null
reported_traffic_unit = null
reported_traffic_bytes_estimate = null
TRAFFIC_INVALID present
parse_status = partial
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

# 47. Historical data / backfill

Final decision:

```text
NO BACKFILL
```

Do NOT rewrite:

```text
omada_webhook_normalized.log
rotated normalized logs
Visit rows
visit_source_events
Public Traffic rows
Analytics history
Loki history
```

Historical `887Bytes` events may remain:

```text
partial
TRAFFIC_INVALID
traffic estimate null
```

That is accepted historical evidence.

A future historical repair requires a separate explicit reconciliation/backfill task with duplicate-accounting safeguards.

---

# 48. Security / privacy invariants

No new secret or sensitive field.

Do not add to Grafana/Loki labels:

```text
credentials
tokens
cookies
authorization headers
client MAC
client IP
SSID
parse_warnings
```

No application credential or Omada secret is part of this task.

---

# 49. Rollback — parser

Because schema remains v1:

```text
no schema rollback
no DB migration rollback
```

Parser rollback only restores previous accepted-input behavior:

```text
future Bytes -> TRAFFIC_INVALID again
```

Already-produced corrected schema-v1 records remain valid and require no cleanup.

---

# 50. Rollback — Grafana

Before modification Owner / Tech Lead has the dashboard v55 backup/export.

Grafana rollback:

```text
restore previous Panel 48/55 definitions
or restore exported v55 dashboard according to normal Owner process
```

No Loki data mutation.

No Alloy rollback.

No application rollback required solely because Grafana presentation is rolled back.

---

# 51. Non-goals

Do NOT:

```text
change Omada Controller configuration
change webhook endpoint contract
change Auth
change CAPPORT
change Visit start/close/matching/finalization
change Visit schema v2
change Observation architecture
change Current State
change Home Activity formulas
change Admin Console UI
change security/authentication
perform generic normalizer refactor
add arbitrary unit aliases
add Byte support
add decimal-SI multipliers
add normalizer INT64 redesign
add new Loki labels
change Alloy pipeline
create Grafana provisioning
redesign whole Grafana dashboard
add alerts
backfill history
```

---

# 52. Open questions

```text
NONE
```

All architecture and execution ownership choices required for this task are closed.

If real production Loki 2.9.8 contradicts the proven parameterized-array extraction behavior during Gate C, that is not an open design choice: it is a STOP condition requiring evidence return to Tech Lead.

---

# 53. Stop conditions

STOP and return evidence if any of the following occurs:

```text
origin/main parser contract materially changed after baseline
Bytes cannot be added without output-schema change
canonical unit B behavior would change
Visit semantics would need modification
new schema migration becomes necessary
new Alloy label becomes necessary
production Loki parameterized array extraction differs materially
Panel 48/55 IDs no longer refer to the captured v55 roles
production dashboard has been materially redesigned since backup baseline
new dependency is required
```

Do not silently expand scope.

---

# 54. Required implementation handoff format

When implementation is separately authorized, Coder returns:

```text
BASELINE
IMPLEMENTED
NOT IMPLEMENTED
FILES CHANGED
PARSER CONTRACT
SCHEMA VERSION
TARGETED TESTS
DOWNSTREAM REGRESSIONS
COMPILEALL
DIFF CHECK
WORKING TREE
PATCH / COMMIT IDENTITY
RISKS / DEVIATIONS
GRAFANA ACTIONS: NONE BY CODER
PRODUCTION ACTIONS: NONE BY CODER
```

Any deviation from FINAL must be explicit.

---

# 55. Authorization state after FINAL

This document finalizes architecture only.

Current authorization remains:

```text
Implementation: NOT AUTHORIZED
Branch:         NOT AUTHORIZED
Commit/push/PR: NOT AUTHORIZED
Merge:          NOT AUTHORIZED
Deploy:         NOT AUTHORIZED
Grafana edit:   NOT AUTHORIZED BY THIS DOCUMENT
```

A separate explicit Owner instruction is required before Coder begins implementation.
