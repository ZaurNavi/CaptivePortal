# TASK-DEVICE-FINGERPRINT-03A-FINAL

## Multi-Platform Labeled Evidence Matrix

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-15  
**Status:** `FINAL — FOR TECHLEAD10 FINAL CONSISTENCY REVIEW`  
**Implementation-ready:** `CONTRACT COMPLETE / EXECUTION NOT AUTHORIZED`  
**Coder:** `HOLD`  
**Task-04:** `HOLD`  
**Production changes:** `NOT AUTHORIZED`

---

# 0. Final Architect Control Gate


```text
DEVICE-FINGERPRINT-00 = CLOSED / PASS
DEVICE-FINGERPRINT-01 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-02 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-03 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-03A = FINAL CONTRACT
DEVICE-FINGERPRINT-04 = HOLD
DEVICE-FINGERPRINT-05 = HOLD
DEVICE-FINGERPRINT-06 = HOLD
```

Architecture:

```text
03A =
LAB / RESEARCH DATASET

NO production DB/schema/API change

NO classifier

NO feature engineering

GROUND TRUTH separate from NORMALIZED EVIDENCE

actual matrices outside Git
```

Current gate:

```text
TECHLEAD10 FINAL CONSISTENCY REVIEW
```

Until TechLead10 FINAL PASS + separate Owner authorization:

```text
CODER = HOLD
TASK-04 = HOLD
NO IMPLEMENTATION
NO COLLECTION
NO DEPLOY
NO PRODUCTION ACTIVATION
```

---

# 1. Fresh Repository Baseline

```text
repository = ZaurNavi/CaptivePortal
main HEAD = 0355f236d4bc506426bea67c543289ce1b426046
main TREE = daa6b8e91c1bdd23f3e7d7a491ec95cb170ca780
PR #124 = MERGED
TASK-DEVICE-FINGERPRINT-03 = IMPLEMENTED / ACCEPTED / MERGED
```

Fresh source review confirms the merge commit and tree above.

TechLead10 must perform the normal fresh rebind before an implementation-ready FINAL.

---

# 2. Exact Goal

Create a controlled labeled matrix connecting:

```text
HUMAN-CONFIRMED GROUND TRUTH

↕

ACTUALLY OBSERVED NORMALIZED EVIDENCE
```

across multiple physical devices, device classes, OS families, browser/runtime contexts, network attachment epochs and repeated observations.

The matrix becomes the empirical input for future Task-04 architecture.

---

# 3. Permanent Four-Layer Model

```text
1. RAW ACQUISITION OBSERVATION
2. NORMALIZED EVIDENCE
3. DERIVED CLASSIFICATION
4. GROUND TRUTH
```

Task-03A MUST keep these layers separate.

---

# 4. RAW ACQUISITION OBSERVATION

Examples:

```text
Ethernet frames
DHCP/TCP packets
TLS/QUIC protocol messages
raw User-Agent
raw Client Hints
```

03A creates no new raw acquisition path and stores no raw acquisition artifact.

---

# 5. NORMALIZED EVIDENCE

03A consumes only Task-01 canonical normalized evidence produced by Tasks 02/03.

It preserves source payload semantics exactly and never edits evidence to match expected ground truth.

---

# 6. DERIVED CLASSIFICATION

In Task-03A:

```text
DERIVED CLASSIFICATION = ABSENT
```

Forbidden:

```text
device_class production inference
confidence score
classification weight
rule/model decision
classifier probability
```

Task-04 owns all derived classification.

---

# 7. GROUND TRUTH


Ground truth is manually verified lab truth for a physical test device whose
collection is explicitly authorized.

Admission requires:

```text
collection_authorized = true
```

with one exact control basis:

```text
owner_controlled

or

explicitly_authorized
```

No person/owner identity is stored in the matrix.

Ground truth MUST NOT be inferred from:

```text
UA
Client Hints
JA4
DHCP
TCP SYN
OUI
MAC similarity
existing device_type
```

---

# 8. Core Identity Invariants

```text
one fingerprint != one device
one UA != one device
one JA4 != one device
one MAC != permanent human identity
```

A physical test device is expected to produce multiple representations.

---

# 9. lab_device_id

03A introduces lab-only:

```text
lab_device_id = canonical lowercase UUID4
```

It represents one manually verified physical test device.

It is NOT a production device ID, visitor identity, person identity or MAC alias.

---

# 10. Manual Cross-MAC Ground Truth

Multiple samples with different MAC addresses MAY share one `lab_device_id` only when Owner manually confirms they are the same controlled physical device.

This is ground-truth labeling, not fingerprint-based identity resolution.

Automatic cross-MAC linking is forbidden.

---

# 11. Production Identity Boundary

03A creates NO production:

```text
MAC merge
identity-link table
visitor resolver
person identity
```

Task-05 remains future production identity-integration owner.

---

# 12. Existing Production Evidence Registry

Current merged production registry contains exactly:

```text
dhcp / 1
tcp_syn / 1
tls_client / 1
quic_client / 1
portal_headers / 1
```

03A consumes these five schemas only.

No new production evidence source kind is created.

---

# 13. Task-02 Provenance

```text
producer_id = sensor-zefer-01
capture_source_id = zefer-span-01
site_id = 6a64f17630da7c70d232187a
```

Participating source kinds:

```text
dhcp
tcp_syn
tls_client
quic_client
```

---

# 14. Task-03 Provenance

```text
producer_id = portal-zefer-01
capture_source_id = zefer-portal-http-01
site_id = 6a64f17630da7c70d232187a
source_kind = portal_headers
```

---

# 15. Exact DHCP Evidence Contract Consumed

```text
message_type
parameter_request_list
option_order
vendor_class
client_identifier_kind
maximum_message_size
rapid_commit_requested
capport_requested
ipv6_only_preferred_requested
hostname_present
```

---

# 16. Exact TCP SYN Evidence Contract Consumed

```text
ip_version
observed_ttl
tcp_window
mss
window_scale
sack_permitted
timestamps_present
tcp_option_order
```

Current V1 is IPv4.

---

# 17. Exact TLS Evidence Contract Consumed

```text
ja4
ja4_a
ja4_b
ja4_c
tls_version_family
client_alpns
ech_extension_present
grease_extension_present
```

No JA3 or SNI.

---

# 18. Exact QUIC Evidence Contract Consumed

```text
ja4
ja4_a
ja4_b
ja4_c
quic_version
ech_extension_present
grease_extension_present
```

---

# 19. Exact Portal Evidence Contract Consumed

`portal_headers/1` exact 16 fields:

```text
platform_family
mobile_boolean
browser_runtime_family
webview_or_captive_context
model_family
os_major
platform_source
mobile_source
runtime_source
context_source
model_source
os_major_source
ua_present
sec_ch_ua_present
sec_ch_ua_platform_present
sec_ch_ua_mobile_present
```

Raw UA/CH are not reconstructed.

---

# 20. Existing Read Boundary

03A uses Task-01 bounded read-only evidence access scoped by:

```text
site_id
observed_mac
from_utc
to_utc
optional source_kind
bounded pagination
```

03A does not create another evidence API.

---

# 21. Production Retention Constraint

Current Task-01 default P1 retention:

```text
30 days
```

03A does NOT increase production retention.

Every controlled sample must be exported before source evidence expires.

Operational target:

```text
export within 24 hours of collection
```

---

# 22. Architectural Storage Decision

Freeze:

```text
03A = LAB / RESEARCH DATASET
03A != PRODUCTION RUNTIME STATE
```

03A does NOT add a production DB, table or runtime schema.

---

# 23. No Production Schema Change

NO change to:

```text
device_fingerprint_evidence
device_fingerprint_source_health_events
Task-01 DB user_version
production EvidenceSchemaRegistry
Task-01 HTTP API
Task-02 payload schemas
Task-03 payload schema
```

Ground truth is never added to production evidence rows.

---

# 24. Repository Role

Repository may contain only:

```text
matrix format contract
lab exporter/validator tooling
controlled collection procedure
synthetic tests
documentation
```

Actual labeled matrices MUST NOT be committed to Git.

---

# 25. Frozen Lab-Only Repository Namespace / Import Direction


Accepted non-production namespace:

```text
research/device_fingerprint_03a/
```

Exact lab-tooling files:

```text
README.md
format.py
exporter.py
validator.py
cli.py
```

Dependency direction is one-way:

```text
research/device_fingerprint_03a/**
    MAY import
app.device_fingerprint canonical read/validation helpers
```

Allowed examples include:

```text
build_production_schema_registry

DeviceFingerprintReadService

open_read_only

canonical JSON helpers

canonical UUID/timestamp validation
where appropriate
```

Forbidden reverse dependency:

```text
app/**
run.py
deploy/**
```

MUST NOT import:

```text
research/**
```

No production runtime dependency on the 03A research namespace.

---

# 26. Actual Dataset Storage

Actual matrix data lives outside Git in a protected lab directory.

Proposed root:

```text
/opt/CaptivePortal/lab/device-fingerprint-03a/
```

No production service reads it automatically.

Exact host/path ownership is an Owner/TechLead operational decision before collection execution.

---

# 27. Matrix Version / Canonical UUID / Timestamp Contract


```text
matrix_format_version =
1

matrix_revision =
1
```

All matrix-generated UUID identifiers use:

```text
canonical lowercase UUID
```

This includes:

```text
matrix_id
lab_device_id
ground_truth_state_id
sample_id
collection_run_id
network_epoch_id
supersedes_matrix_id when non-null
```

New identifiers are UUID4 unless a source contract explicitly provides an
existing canonical UUID.

All matrix timestamps use EXACTLY:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

UTC only.

This includes matrix-generated:

```text
sealed_at
ground_truth_verified_at
state_verified_at
window_start_utc
window_end_utc
```

and imported canonical Task-01 timestamps retained in matrix records.

A sealed matrix is immutable.

Any content correction creates a NEW:

```text
matrix_id
```

---

# 28. Exact Sealed Dataset Files

```text
manifest.json
devices.jsonl
device_states.jsonl
samples.jsonl
evidence.jsonl
source_health.jsonl
checksums.sha256
```

No raw capture file.

No private MAC binding ledger inside the sealed dataset.

---

# 29. Private Staging Binding Ledger

Collection may use separate protected:

```text
collection_bindings.jsonl
```

It exists only to bind:

```text
sample_id
lab_device_id
current observed MAC
optional observed IP
```

for evidence export.

---

# 30. Binding Ledger Privacy / Retention

Binding ledger contains only controlled test-device bindings.

Forbidden:

```text
visitor MAC
person name
account identity
```

Maximum retention:

```text
30 days
```

Preferred:

```text
delete immediately after matrix seal + validation PASS
```

---

# 31. Sealed Matrix De-Identification

Sealed `evidence.jsonl` MUST NOT contain:

```text
observed_mac
observed_ip
```

Evidence is linked through:

```text
sample_id
lab_device_id
```

MAC remains staging-only collection identity.

---

# 32. Why MAC Is Excluded From Task-04 Dataset

MAC is not needed as a classifier feature and would permit identity memorization.

```text
MAC = collection binding only
MAC != training feature
```

---

# 33. Evidence Provenance Retained

Each sealed evidence row retains:

```text
evidence_id
source_event_id
producer_id
source_kind
source_subtype
extractor_name
extractor_version
feature_schema_version
rule_version
site_id
capture_source_id
observed_at
quality_state
privacy_class
payload
payload_sha256
ingested_at
sample_id
lab_device_id
```

---

# 34. Permanent Task-04 Label / Context / Provenance Leakage Boundary


Permanent invariant:

```text
GROUND TRUTH / COLLECTION CONTEXT
MUST NOT become classifier input feature
```

Without a future explicit Task-04 contract, these MUST NOT be direct classifier
inputs:

```text
device_class_gt
manufacturer_gt
model_gt
hardware_variant_gt
os_family_gt
os_version_gt
os_major_gt

browser_family_gt
browser_version_major_gt
runtime_context_gt
portal_entry_mode_gt
network_state_gt
mac_mode_gt
context_supported_gt

lab_device_id
ground_truth_state_id
sample_id
collection_run_id
network_epoch_id

evidence_id
source_event_id
producer_id
site_id
capture_source_id
ingested_at
payload_sha256

source_health_id
source_health_event_id
```

Ground-truth/context fields may be used for:

```text
label
grouping
stratification
audit
coverage analysis
```

`lab_device_id` is specifically retained as the physical-device grouping/split
key.

Provenance fields remain reproducibility/audit metadata.

Task-04 separately designs feature engineering from the normalized evidence
payload semantics.

---

# 35. Ground Truth Device Record


`devices.jsonl` required fields:

```text
matrix_format_version

lab_device_id

device_class_gt

manufacturer_gt

model_gt

collection_authorized

control_basis_gt

ground_truth_verified_at

ground_truth_verification_methods
```

Optional:

```text
hardware_variant_gt
```

Exact authorization:

```text
collection_authorized =
true

control_basis_gt =
owner_controlled
|
explicitly_authorized
```

No owner/person identity field is allowed.

---

# 36. device_class_gt

Allowed V1 labels:

```text
smartphone
tablet
laptop
```

These are manual ground-truth labels only.

---

# 37. Device State Record


`device_states.jsonl` required fields:

```text
matrix_format_version
ground_truth_state_id
lab_device_id
os_family_gt
os_version_gt
os_major_gt
state_verified_at
state_verification_methods
```

Optional:

```text
os_build_gt
```

`ground_truth_state_id` is:

```text
canonical lowercase UUID
```

and belongs to exactly one:

```text
lab_device_id
```

---

# 38. Why OS State Is Separate

One physical device may be observed before and after an OS update.

Same physical device:

```text
same lab_device_id
```

Changed OS state:

```text
new ground_truth_state_id
```

Old rows are not rewritten.

---

# 39. os_family_gt

Allowed:

```text
android
ios
ipados
windows
macos
chromeos
linux
```

ChromeOS/Linux are optional V1 extensions unless coverage requirements are separately satisfied.

---

# 40. Ground Truth Version Rules

`os_version_gt`:

```text
exact version shown by controlled device Settings/About
1..64 printable ASCII
```

`os_major_gt`:

```text
integer 1..99
```

and must agree with the verified version.

---

# 41. Manufacturer / Model Ground Truth

```text
manufacturer_gt = required, 1..64 printable ASCII
model_gt = required, 1..96 printable ASCII
```

These inventory facts are not automatically Task-04 classification targets.

---

# 42. Verification Methods

Allowed structured values:

```text
device_settings
device_about_page
physical_manufacturer_label
owner_purchase_record
```

OS state requires `device_settings` or `device_about_page`.

No fingerprint-based verification method is allowed.

---

# 43. Authorized Device Requirement


Every admitted physical device requires:

```text
collection_authorized =
true
```

and:

```text
control_basis_gt =
owner_controlled
or
explicitly_authorized
```

If collection authorization is false, absent or uncertain:

```text
NOT ADMITTED
```

No person/owner identity is stored in the dataset.

---

# 44. Sample Is The Main Observation Unit

One `sample_id` means:

```text
one physical lab device
one ground-truth OS state
one current MAC binding
one bounded time window
one runtime/browser context
one network-attachment context
```

A sample may contain many evidence rows from multiple sources.

---

# 45. Sample Identity


```text
sample_id =
canonical lowercase UUID4
```

One sample references exactly one:

```text
lab_device_id
ground_truth_state_id
```

---

# 46. Collection Run


```text
collection_run_id =
canonical lowercase UUID4
```

A run may contain multiple samples/devices and records
procedure/repository/environment provenance.

---

# 47. Sealed Sample Required Fields


`sealed samples.jsonl` contains exactly valid sealed sample records.

Required fields:

```text
matrix_format_version
sample_id
collection_run_id
lab_device_id
ground_truth_state_id
site_id
window_start_utc
window_end_utc
network_epoch_id
network_state_gt
runtime_context_gt
browser_family_gt
browser_version_major_gt
mac_mode_gt
portal_entry_mode_gt
context_supported_gt
sample_status
sealed_at
```

Exact sealed requirements:

```text
sample_status =
sealed

sealed_at =
required non-null canonical UTC timestamp
```

`browser_version_major_gt` may be null.

`draft` and `invalid` exist only in collection staging/audit and MUST NOT appear
in the sealed classifier matrix.

---

# 48. Sample Window — Exact Half-Open Interval


One evidence sample uses the exact half-open interval:

```text
[window_start_utc, window_end_utc)
```

Therefore:

```text
window_start_utc <= evidence.observed_at < window_end_utc
```

Duration:

```text
0 < duration <= 600 seconds
```

Longer test activity becomes another sample.

The 10-minute cap reduces unrelated traffic and keeps context reviewable.

---

# 49. Context Stability


Within one collection attempt do NOT change:

```text
physical device
OS state
browser/runtime context
current MAC binding
network attachment identity
```

Unexpected change:

```text
staging sample =
invalid
```

and a new sample must be started.

An invalid staging sample MUST NOT enter sealed:

```text
samples.jsonl
```

---

# 50. network_epoch_id


```text
network_epoch_id =
canonical lowercase UUID4
```

A controlled disconnect/reconnect creating a fresh network attachment creates a
new epoch.

Multiple browser-context samples may share one epoch only while the same
network attachment remains in force.

---

# 51. network_state_gt

Allowed:

```text
fresh_attach
same_attachment_revisit
```

---

# 52. runtime_context_gt

Allowed:

```text
captive_webview
captive_helper
normal_browser
```

This is operator-controlled ground-truth context, not copied from Task-03 output.

---

# 53. browser_family_gt

Allowed:

```text
android_webview
chrome
edge
firefox
safari
chromium_other
captive_helper
other
```

`other` is collection context only and is not automatically a production classifier label.

---

# 54. Browser Version

```text
browser_version_major_gt = integer 1..999 or null
```

Record only when easily verifiable from controlled browser settings/about.

---

# 55. mac_mode_gt

Allowed:

```text
global
randomized_stable
randomized_rotated
unknown
```

This is context metadata, not identity confidence.

---

# 56. portal_entry_mode_gt

Allowed:

```text
omada_external_portal
capport_login
```

---

# 57. Multiple Samples Per Device Are Mandatory

Task-03 proved header representation may change between captive WebView/helper and normal browser.

Therefore one physical device MUST have repeated samples.

No “canonical one fingerprint per device” row exists.

---

# 58. Minimum Repetition Per Device

For V1 admission each mandatory physical device requires:

```text
>= 4 sealed valid samples
>= 2 distinct network_epoch_id values
```

---

# 59. Required Runtime Variation

Where captive/helper and normal browser are both reproducibly available, the four-sample minimum MUST include both context families.

Recommended baseline:

```text
epoch 1:
  fresh attach + captive/helper
  same attachment + normal browser

epoch 2:
  fresh attach + captive/helper
  same attachment + normal browser
```

---

# 60. Unsupported Captive Context

If a device/platform cannot reproducibly expose captive helper/WebView:

```text
context_supported_gt = false
```

Do not fabricate a captive sample.

Still collect >=4 valid samples across >=2 epochs using available controlled contexts.

---

# 61. Browser Change

Changing browser/runtime family requires a NEW `sample_id`.

Same physical device may intentionally produce Chrome, Firefox and WebView samples.

---

# 62. Browser Version Change

Browser major update:

```text
new sample_id
```

OS state may remain the same if OS is unchanged.

---

# 63. OS Update

OS version change requires:

```text
new ground_truth_state_id
new sample_id
```

---

# 64. MAC Rotation

Randomized MAC change requires:

```text
new sample_id
normally new network_epoch_id
```

Owner manually binds the new MAC to the same `lab_device_id` in private staging.

No fingerprint-based linking.

---

# 65. Mandatory V1 Coverage

```text
SMARTPHONE:
2 Android
2 iOS

TABLET:
2 Android
2 iPadOS

LAPTOP:
2 Windows
2 macOS
```

Minimum physical devices:

```text
12
```

---

# 66. Why >=2 Devices Per Cell

One physical device per cell cannot separate device-specific quirks from platform/class evidence.

Two is still only a minimum empirical admission threshold, not proof of production classifier accuracy.

Task-04 may require more devices.

---

# 67. ChromeOS / Linux

```text
OPTIONAL V1 EXTENSION
```

If Task-04 later wants ChromeOS/Linux production labels, 03A must first reach >=2 independent physical devices per added target cell.

---

# 68. Minimum Sample Count

```text
12 mandatory devices × 4 samples = 48 sealed valid samples minimum
```

Invalid samples do not count.

---

# 69. Mandatory Coverage Cells

Each of these six cells needs >=2 distinct `lab_device_id`:

```text
Android smartphone
iOS smartphone
Android tablet
iPadOS tablet
Windows laptop
macOS laptop
```

---

# 70. Source Presence Is Context-Dependent

03A does NOT require every source in every sample.

Example:

```text
same_attachment_revisit may have no DHCP event
```

Missing evidence is not synthesized.

---

# 71. Five Source Families Matrix-Wide

For V1 overall PASS, matrix contains at least one valid event from each:

```text
dhcp
tcp_syn
tls_client
quic_client
portal_headers
```

---

# 72. Per-Device Core Evidence Coverage

Across all valid samples for every mandatory device require at least:

```text
portal_headers >= 1
dhcp >= 1
tcp_syn >= 1
tls_client >= 1
```

QUIC is not mandatory per physical device.

---

# 73. QUIC Coverage

Target V1:

```text
quic_client evidence from >=3 distinct os_family_gt values
```

If controlled clients cannot meet this, 03A may preserve the matrix only with an explicit `quic_sparse` limitation and Task-04 MUST treat QUIC as optional/sparse evidence unless TechLead accepts additional collection.

Do not fabricate unrelated traffic merely to improve coverage.

---

# 74. Sample Evidence Extraction

Exporter reads all Task-01 evidence for:

```text
site_id
private staging canonical MAC
window_start_utc
window_end_utc
```

using bounded pagination.

No evidence outside the window is attached.

---

# 75. Canonical Revalidation During Export

Every exported payload MUST pass current:

```text
build_production_schema_registry()
```

using its exact source kind/schema version.

Validation failure:

```text
sample export = FAIL
```

No silent copy.

---

# 76. Deterministic Evidence Ordering

```text
sample_id ASC
observed_at ASC
evidence_id ASC
```

Canonical JSON:

```text
UTF-8
ensure_ascii=true
allow_nan=false
sort_keys=true
separators=(",", ":")
```

---

# 77. Source Health Is Context, Not Ground Truth

Source-health points remain operational evidence.

They are not device labels and not classifier conclusions.

---

# 78. Source Health Source Mapping

Task-02:

```text
capture_source_id = zefer-span-01
source kinds = dhcp,tcp_syn,tls_client,quic_client
```

Task-03:

```text
capture_source_id = zefer-portal-http-01
source kind = portal_headers
```

---

# 79. Point Semantics Preserved

Task-01 health is point-event evidence.

03A MUST NOT turn it into a fabricated continuous interval.

```text
silence != unavailable
```

---

# 80. Source Health Snapshot Per Sample


For each source/sample capture point-event context:

```text
latest source-health event at/before sample start

all source-health events inside:
[window_start_utc, window_end_utc)

latest source-health event at/before sample end
```

Deduplicate identical source-health event IDs.

Task-01 stores point-events.

03A does NOT assume every point means a state transition.

No interval certainty is synthesized.

Permanent:

```text
silence != unavailable
```

---

# 81. source_health.jsonl

Each row carries:

```text
matrix_format_version
sample_id
lab_device_id
source_health_id
source_health_event_id
producer_id
site_id
capture_source_id
source_kind
status
reason_code
observed_at
ingested_at
point_roles
```

Allowed `point_roles`:

```text
latest_before_start
during_window
latest_at_end
```

---

# 82. Evidence Absence

If a source has zero sample evidence:

```text
evidence_count = 0
```

Do NOT transform it into:

```text
source unavailable
feature false
device lacks capability
```

---

# 83. Sample Source Summary — Derived Report Only


For all five source kinds, validator/report tooling deterministically computes
from `evidence.jsonl`:

```text
evidence_count
valid_count
partial_count
degraded_count
distinct_payload_sha256_count
first_observed_at
last_observed_at
```

This summary is:

```text
DERIVED REPORT METADATA
```

It is NOT:

```text
a new canonical dataset file

a persisted training feature

classifier confidence
```

Task-04 may recompute it from the sealed evidence if needed.

---

# 84. Conflicting Evidence

Conflicting normalized observations are preserved exactly.

Example:

```text
ground truth Android
portal_headers says linux in one context
```

03A keeps both facts and does not select a winner.

---

# 85. Partial Evidence

`quality_state=partial` is valid observed evidence, not ground-truth failure.

Do not discard it merely for incompleteness.

---

# 86. Degraded Evidence

Valid canonical `quality_state=degraded` rows are preserved and counted separately.

No classifier meaning is assigned.

---

# 87. Variant Counts

`distinct_payload_sha256_count` may describe how many normalized variants were seen.

It does NOT imply multiple devices.

---

# 88. Ground Truth Never Overwrites Evidence

Manual ground truth and observed evidence are stored separately even when they conflict.

No evidence “correction” based on expected label.

---

# 89. Evidence Never Overwrites Ground Truth

UA/JA4/DHCP/TCP evidence cannot revise manually verified ground-truth labels.

Suspected label error requires physical Owner re-verification.

---

# 90. Ground Truth Conflict

If manual records conflict:

```text
device/state = UNVERIFIED
excluded from PASS counts
```

No fingerprint majority vote.

---

# 91. Sample Status — Staging vs Sealed Dataset


Collection staging may represent:

```text
draft
invalid
sealed-ready
```

but canonical sealed:

```text
samples.jsonl
```

contains ONLY:

```text
sample_status =
sealed
```

Validator rule:

```text
sample_status != sealed
→ FAIL
```

`sealed_at` MUST be non-null and in the canonical matrix timestamp format.

Invalid/draft attempt details remain outside the sealed classifier matrix.

---

# 92. Sample Sealing


Owner/operator seals only after checking:

```text
physical device label
OS state
current MAC binding
window
runtime/browser context
network epoch
no mid-window context change
collection authorization
```

At seal:

```text
sample_status =
sealed

sealed_at =
canonical UTC timestamp
```

After sealing, correction requires a new sample/matrix supersession process.

---

# 93. Controlled Collection Procedure

Required:

```text
YES
```

Random production visitors are forbidden as 03A labeled subjects.

---

# 94. Owner / Authorized Operator Manual Enrollment


For each physical device Owner or explicitly authorized lab operator must:

```text
assign lab_device_id

verify device class

verify manufacturer/model

verify OS family/version in Settings/About

create ground_truth_state_id

confirm:
collection_authorized = true

record:
control_basis_gt =
owner_controlled
or
explicitly_authorized
```

No evidence-source observation is used to create these labels.

No person/owner identity is stored.

---

# 95. Before Each Sample

Manually record:

```text
physical lab device
current ground_truth_state_id
current Wi-Fi MAC in PRIVATE binding ledger
MAC mode
runtime/browser context
browser family/major when known
network state
window_start_utc
```

---

# 96. Fresh Attach Procedure

For `fresh_attach`:

```text
disconnect Wi-Fi
confirm intended test SSID
reconnect
allow normal DHCP/network establishment
trigger intended portal flow
perform only controlled browser/helper action
avoid unrelated browsing
```

---

# 97. WebView / Browser Variation

Separate samples for:

```text
captive WebView/helper where reproducible
normal browser
```

Optional second normal browser family is useful but not mandatory.

---

# 98. End Sample

Record:

```text
window_end_utc
duration <= 600s
context remained stable
```

Then mark draft sample ready for evidence export.

---

# 99. Manual Evidence Review Before Seal

Confirm:

```text
evidence belongs to intended sample
MAC binding was correct
ground truth remains correct
no visitor sample accidentally included
```

Only then seal.

---

# 100. Controlled Calibration Gate — Mechanics


Before the full 48-sample campaign, run limited procedure calibration using
exactly:

```text
1 Android smartphone
1 iOS smartphone
1 Windows laptop
```

Purpose:

```text
validate procedure
validate exporter
validate exact half-open sample windows
validate source-health snapshot
validate de-identification
validate sealing/checksums
observe source prevalence
```

Mandatory mechanics proof includes at least one controlled MAC rotation/new MAC
binding:

```text
new MAC
→ new sample_id
→ normally new network_epoch_id
→ SAME manually verified lab_device_id
```

No fingerprint similarity is used for that binding.

Also, on at least one supported controlled device, prove separate samples for:

```text
captive/helper context

vs

normal browser context
```

This is collection-mechanics calibration.

It is NOT classifier accuracy research.

---

# 101. Calibration May Adjust Mechanics Only

Calibration may adjust:

```text
operator checklist
sample timing within <=600s
export implementation mechanics
```

It may NOT silently change production schemas, ground-truth labels or semantic-layer boundaries.

---

# 102. Task-04 Structural Admission Criteria

03A may PASS to Task-04 architecture only when:

```text
mandatory device coverage = PASS
>=48 sealed samples = PASS
>=2 epochs/device = PASS
runtime variation = PASS where supported
all five source kinds exist somewhere = PASS
per-device core evidence coverage = PASS
ground truth audit = PASS
source-health context = captured
privacy/de-identification = PASS
checksums/validator = PASS
```

---

# 103. 03A PASS Is Not Classifier Accuracy

03A PASS means there is enough controlled empirical data to DESIGN Task-04.

It does NOT mean classifier accuracy or production confidence is proven.

---

# 104. Future Task-04 Split Rule

Future classifier evaluation MUST group by:

```text
lab_device_id
```

Never randomly split samples of the same physical device across train/test as independent devices.

This prevents device memorization leakage.

---

# 105. Same Device Across OS States

All samples/states of one `lab_device_id` stay in the same device-level evaluation group unless Task-04 explicitly designs a temporal-generalization experiment.

---

# 106. manifest.json


Required concepts:

```text
matrix_format_version
matrix_id
matrix_revision
sealed_at
repository_head
repository_tree
site_id
collection_procedure_version
ground_truth_policy_version
production_schema_registry
task01_retention_days
device_count
sealed_sample_count
evidence_count
source_health_count
invalid_sample_count
invalid_sample_reason_counts
known_coverage_limitations
supersedes_matrix_id
```

`invalid_sample_reason_counts` is a JSON object whose keys are limited to the
canonical exclusion enum:

```text
binding_uncertain
context_changed
window_too_long
evidence_missing
ground_truth_unverified
source_schema_error
privacy_violation
operator_abort
```

Values are non-negative integers.

No free-text invalid-sample reason.

`manifest.json` contains NO checksum map.

The sole checksum authority is:

```text
checksums.sha256
```

---

# 107. production_schema_registry Manifest Value

```text
[
  ["dhcp", 1],
  ["portal_headers", 1],
  ["quic_client", 1],
  ["tcp_syn", 1],
  ["tls_client", 1]
]
```

Sorted deterministically.

---

# 108. Repository Provenance

Current tooling baseline:

```text
HEAD = 0355f236d4bc506426bea67c543289ce1b426046
TREE = daa6b8e91c1bdd23f3e7d7a491ec95cb170ca780
```

Sealed matrix records the exact repository artifact actually used for export.

---

# 109. Exporter Is Read-Only

Forbidden against Task-01 DB:

```text
INSERT
UPDATE
DELETE
VACUUM
schema migration
retention change
```

No production evidence mutation.

---

# 110. Export Timing

Target:

```text
within 24h of sample collection
```

If required evidence has aged out:

```text
sample = FAIL / recollect
```

No reconstruction from raw logs/packets.

---

# 111. Source-Health Lab Read Boundary


Existing public Python read service exposes latest source-health point but not
the full bounded sample-window point-event history.

Lab-only tooling MAY use Task-01 existing read-only SQLite helper:

```text
open_read_only
```

to query only:

```text
device_fingerprint_source_health_events
```

for the bounded sample/source scope.

This is allowed dependency direction:

```text
research/**
→
app.device_fingerprint read helpers
```

No production API/read-service expansion is required.

---

# 112. Source-Health Query Bound


For each sample/source query only:

```text
one latest event at/before window_start_utc

all events where:
window_start_utc <= observed_at < window_end_utc

one latest event at/before window_end_utc
```

Strict:

```text
Site
+
capture_source_id
+
source_kind
```

scope.

No broad production source-health history dump.

---

# 113. Private Binding Query

Evidence extraction uses:

```text
site_id
private staging MAC
sample time window
```

Optional staging IP may be used only as manual consistency evidence and is excluded from sealed matrix.

---

# 114. Binding Collision Check

If two different `lab_device_id` samples claim the same Site+MAC with overlapping windows:

```text
FAIL
```

Owner must resolve the binding/timing ambiguity.

---

# 115. Evidence Assignment Uniqueness

One production `evidence_id` may belong to only one sealed sample within a matrix.

Duplicate assignment:

```text
matrix validation = FAIL
```

---

# 116. Source Counts Are Not Confidence

Evidence counts are descriptive collection metadata only.

Higher event count does not imply higher classification confidence.

---

# 117. Missingness Is First-Class

Never fill missing sources with:

```text
default fingerprint
zero vector meaning false
last-known sample evidence
```

Preserve zero count + source-health point context.

---

# 118. No Carry-Forward

Evidence from sample A is not copied into sample B even when same device/MAC/network epoch.

Each sample owns only timestamp-bounded evidence.

---

# 119. Portal Evidence Is Not Ground Truth

`portal_headers.platform_family=android` remains normalized evidence, not `os_family_gt`.

---

# 120. Existing Omada device_type Is Not Ground Truth

03A V1 does not use controller `device_type` / `device_type_key` as labels.

---

# 121. OUI Is Not Ground Truth

Manufacturer/model labels come from physical/device information, not OUI inference.

---

# 122. Sealed Matrix Privacy Class

The sealed matrix is:

```text
LAB P1-DERIVED DATASET
```

even after MAC/IP removal.

It is not public data.

---

# 123. Sealed Matrix Retention

```text
180 days from sealed_at
```

Before expiry, Owner + TechLead may explicitly extend retention if Task-04/05 still needs the exact matrix.

No indefinite automatic retention.

---

# 124. Binding Ledger Retention

```text
maximum 30 days
preferred delete immediately after seal/verification PASS
```

Never provided to Task-04 as classifier input.

---

# 125. Raw Retention

```text
PCAP = 0 durable
raw UA = 0 durable
raw Client Hints = 0 durable
SNI = 0 durable
DNS history = 0 durable
```

---

# 126. No Git Commit Of Actual Matrix

Forbidden in Git:

```text
actual devices.jsonl
actual device_states.jsonl
actual samples.jsonl
actual evidence.jsonl
actual source_health.jsonl
collection_bindings.jsonl
```

Only format/tooling/procedure/synthetic fixtures may be committed.

---

# 127. Task-04 Export Contract

Task-04 reads only a SEALED matrix whose validator and checksums PASS.

Task-04 MUST NOT silently query production DB to supplement one matrix experiment.

Expanded data requires a new matrix ID.

---

# 128. Task-04 Reader Files

```text
manifest.json
devices.jsonl
device_states.jsonl
samples.jsonl
evidence.jsonl
source_health.jsonl
```

Private bindings are excluded.

---

# 129. Reproducibility Provenance

Each sample/evidence is traceable through:

```text
matrix_id
sample_id
lab_device_id
ground_truth_state_id
collection_run_id
time window
runtime context
network epoch
repository HEAD/TREE
evidence_id/source_event_id
extractor/schema versions
payload_sha256
source-health IDs
```

---

# 130. Checksums — Sole Authority


The ONLY checksum authority is:

```text
checksums.sha256
```

It covers exactly:

```text
manifest.json
devices.jsonl
device_states.jsonl
samples.jsonl
evidence.jsonl
source_health.jsonl
```

It does NOT hash itself.

Each line format is EXACTLY:

```text
<lowercase_sha256><two spaces><filename>

```

where:

```text
lowercase_sha256 =
64 lowercase hexadecimal characters
```

Lines are sorted by:

```text
filename ASC
```

Any missing file, unexpected file entry, duplicate filename, noncanonical
digest, ordering mismatch or digest mismatch invalidates the matrix.

---

# 131. Deterministic JSONL

```text
one JSON object per line
UTF-8
ensure_ascii=true
sort_keys=true
compact separators
newline terminated
```

No free-text comments.

---

# 132. Device Schema Validation


Reject:

```text
unknown enum
missing/extra field
invalid/noncanonical UUID
invalid/noncanonical timestamp
non-printable label string
collection_authorized != true
control_basis_gt not in:
owner_controlled
explicitly_authorized
```

No best-effort coercion.

---

# 133. Sealed Sample Schema Validation


Reject:

```text
window_end_utc <= window_start_utc
duration > 600s
unknown device/state
state belongs to another device
invalid/noncanonical UUID
invalid/noncanonical timestamp
invalid context enum
invalid portal mode
sample_status != sealed
sealed_at == null
```

Canonical sealed matrix accepts NO `draft` or `invalid` sample row.

---

# 134. Evidence Schema Validation

Every row must satisfy:

```text
known production source_kind/version
canonical payload validator PASS
payload_sha256 matches canonical payload
sample exists
lab_device_id matches sample
```

---

# 135. Temporal Validation — Exact Sample Window


Require EXACTLY:

```text
window_start_utc <= evidence.observed_at < window_end_utc
```

Equivalent:

```text
[window_start_utc, window_end_utc)
```

This matches the existing Task-01 evidence read contract:

```text
observed_at >= from_utc
observed_at < to_utc
```

Out-of-window row:

```text
FAIL
```

No clipping/reassignment.

---

# 136. File-Level Semantic Separation

Ground truth:

```text
devices.jsonl
device_states.jsonl
samples.jsonl
```

Normalized evidence:

```text
evidence.jsonl
```

Operational source health:

```text
source_health.jsonl
```

No combined training row in 03A.

---

# 137. No Feature Table

03A does NOT create:

```text
X matrix
one-hot feature vectors
training CSV
pandas pickle
scaled feature set
```

Task-04 owns feature engineering.

---

# 138. No Weights / Confidence

03A assigns no source weights or confidence scores.

Ground truth is verified or not admitted.

---

# 139. Evidence Variation Is Expected

Same device may show multiple:

```text
JA4
portal runtime representations
DHCP variants
TCP SYN variants
```

across context/time/OS/browser changes.

Variation is preserved.

---

# 140. Task-03 WebView/Browser Requirement

For each device where supported, matrix review explicitly compares:

```text
captive/helper portal_headers
vs
normal-browser portal_headers
```

Differences are empirical evidence, not labeling errors.

---

# 141. PASS — Ground Truth Integrity

Required:

```text
all mandatory devices controlled/authorized
all device labels verified
all OS states verified
no visitor/person identity
no label inferred from fingerprints
```

---

# 142. PASS — Coverage

Required:

```text
12 mandatory physical devices
6 mandatory cells
>=2 physical devices/cell
>=4 sealed samples/device
>=2 network epochs/device
>=48 sealed valid samples
```

---

# 143. PASS — Evidence Coverage

Required:

```text
all five source kinds present somewhere
per mandatory device:
  portal_headers
  dhcp
  tcp_syn
  tls_client
present across its samples
```

QUIC follows section 73.

---

# 144. PASS — Context Variation

Where captive/helper and normal browser are both reproducibly available, both must be sampled.

Unsupported context must be explicitly marked rather than fabricated.

---

# 145. PASS — Privacy

Sealed matrix contains NO:

```text
MAC
client IP
raw UA
raw Client Hints
SNI
DNS history
cookie
authorization header
person name
```

---

# 146. PASS — Production Isolation

03A must cause NO:

```text
production DB write
schema migration
retention change
Authorization path change
new production service
new production HTTP endpoint
```

---

# 147. PASS — Reproducibility

```text
manifest complete
repository identity recorded
procedure version recorded
all IDs unique
checksums PASS
validator PASS
```

---

# 148. FAIL Conditions

Examples:

```text
missing mandatory platform cell
only one device in mandatory cell
ground-truth uncertainty
wrong MAC binding
overlapping binding ambiguity
visitor evidence included
raw sensitive data persisted
out-of-window evidence
canonical validation failure
checksum mismatch
production mutation
silent cross-MAC inference
classifier logic created early
```

---

# 149. Gate A — Lab Tool Focused Tests


Only after explicit Owner tooling implementation authorization.

Exact focused commands:

```bash
python -m pytest -q tests/device_fingerprint_matrix
```

```bash
python -m compileall -q \
  research/device_fingerprint_03a \
  tests/device_fingerprint_matrix
```

```bash
git diff --check
```

Gate A does NOT add full production regression while implementation remains
strictly outside `app/**`.

If implementation touches any:

```text
app/**
```

then:

```text
STOP
ARCHITECTURE BOUNDARY VIOLATION
```

Do not compensate by merely running more tests.

---

# 150. Gate B — Tech Lead Static / Source Review


Verify:

```text
NO production runtime dependency ON research/**

research/**
may import only approved canonical
app.device_fingerprint read/validation helpers

no production schema change

read-only evidence access

five source contracts exact

MAC/IP absent from sealed matrix

ground truth separate

no classifier logic

no feature-engineering table

sample window is [start,end)

sealed samples only

checksum contract exact

privacy/retention exact
```

If any production `app/**`, `run.py` or `deploy/**` imports `research/**`:

```text
FAIL
```

## PRE-COLLECTION ENVIRONMENT GATE — MANDATORY AFTER GATE B

Before any physical calibration or full collection, Owner must separately
authorize the exact collection environment.

Gate confirms real availability of:

```text
Task-01 canonical evidence store/read boundary
Task-02 network evidence sources
Task-03 portal_headers source
required Task-01 source-health evidence
controlled test SSID / Site
```

Merge/implementation status of Tasks 01/02/03 does NOT itself imply deploy,
activation or collection authorization.

Before PASS, allowed:

```text
03A tooling implementation
synthetic fixtures
Gate A
Gate B
```

Before PASS, forbidden:

```text
Gate C physical calibration
Gate D full collection
production deploy
production activation
```

Before physical collection begins, freeze and record:

```text
exact authorized host/environment
Task-01 evidence DB/read location
lab tooling execution host
protected staging/matrix paths
read-only data-transfer mechanics if any
Site/SSID
source availability expectations
```

If a production host is ever used for read-only collection/export:

```text
separate explicit Owner authorization =
REQUIRED
```

This FINAL does NOT grant that authorization.

---

# 151. Gate C — Controlled Calibration


PRE-COLLECTION ENVIRONMENT GATE must be:

```text
PASS
```

before this Gate may begin.

Use exactly:

```text
1 Android smartphone
1 iOS smartphone
1 Windows laptop
```

Prove:

```text
procedure
exporter
half-open windows/bindings
source-health point snapshot
de-identification
sealing/checksums
```

Mandatory calibration mechanics:

```text
>=1 controlled MAC rotation/new MAC binding
→ new sample_id
→ normally new network_epoch_id
→ same manually verified lab_device_id
```

Also prove on at least one supported device:

```text
captive/helper context
vs
normal browser context
```

This Gate validates mechanics, not classifier quality.

---

# 152. Gate D — Full V1 Collection


Required before start:

```text
PRE-COLLECTION ENVIRONMENT GATE =
PASS

Gate C =
PASS
```

Execute controlled campaign to reach mandatory:

```text
12-device
>=48 sealed-sample
```

coverage.

Owner or explicitly authorized lab operator performs physical labels.

No random production visitor collection.

---

# 153. Gate E — Matrix Validation

Required:

```text
0 schema failures
0 binding collisions
0 duplicate evidence assignment
0 unknown source/schema
0 privacy canaries
all checksums PASS
all admission counts PASS
```

---

# 154. Gate F — Manual Ground Truth Audit


Owner + TechLead audit:

```text
100% device rows
100% device-state rows
>=1 sample per physical device
collection_authorized/control_basis_gt
invalid_sample_count
invalid_sample_reason_counts
```

No classifier output may confirm labels.

No person/owner identity may be present.

---

# 155. Gate G — Task-04 Admission Review

Architect + TechLead review:

```text
coverage matrix
source missingness
variant counts
context variation
source-health context
class/platform balance
known limitations
```

Decision:

```text
PASS -> Task-04 architecture may begin
FAIL -> collect more 03A evidence
```

Task-04 implementation does not start automatically.

---

# 156. Production Regression Boundary


03A dataset collection is lab-only and MUST NOT alter production runtime.

Gate A does NOT require full production regression when implementation remains
inside the accepted non-production boundary.

If tooling implementation touches any production:

```text
app/**
```

then:

```text
STOP
ARCHITECTURE BOUNDARY VIOLATION
```

Do not proceed to collection.

Any later production-host read-only use requires the separate Owner
authorization defined by the PRE-COLLECTION ENVIRONMENT GATE.

---

# 157. Frozen NEW Repository Files


Accepted lab-only namespace:

```text
research/device_fingerprint_03a/README.md
research/device_fingerprint_03a/format.py
research/device_fingerprint_03a/exporter.py
research/device_fingerprint_03a/validator.py
research/device_fingerprint_03a/cli.py
```

Tests:

```text
tests/device_fingerprint_matrix/__init__.py
tests/device_fingerprint_matrix/test_format.py
tests/device_fingerprint_matrix/test_exporter.py
tests/device_fingerprint_matrix/test_validator.py
tests/device_fingerprint_matrix/test_privacy.py
```

Docs:

```text
docs/research/device-fingerprint-03a.md
```

No tooling under:

```text
app/**
```

---

# 158. Proposed MODIFY Files

Documentation/governance only:

```text
README.md
README_RU.md
docs/README.md
docs/architecture.md
docs/project-inventory.md
docs/module-index.md
```

No production config/env change required.

---

# 159. Explicit NO-TOUCH / Dependency Direction


Production runtime/config/deploy NO-TOUCH:

```text
run.py
app/**
deploy/**
.env.example
production SQLite schemas
systemd units
nginx
Omada configuration
Catalyst RSPAN
Task-02 sensor runtime/config
Task-03 portal runtime/config
```

Dependency direction:

```text
research/**
→
approved app.device_fingerprint validators/read helpers
```

Reverse direction is forbidden:

```text
app/**
run.py
deploy/**
→ research/**
```

Task-03A is read-only toward production evidence.

---

# 160. No New Runtime Config / Service

03A introduces no production env prefix, systemd unit, daemon, worker, HTTP endpoint or scheduled production job.

Collection/export is operator-invoked only.

---

# 161. Exporter Inputs


Explicit inputs:

```text
Task-01 DB path/read boundary
matrix staging directory
site_id
collection-run metadata
private binding ledger
sample definitions
repository HEAD/TREE
authorized environment record
```

No production secret is required.

The exporter does not imply permission to access a production host.

The PRE-COLLECTION ENVIRONMENT GATE supplies that authorization separately.

---

# 162. Exporter Output / Sealing

Exporter creates an UNSEALED matrix.

Validator + manual Owner verification create the sealed matrix.

Tool computes checksums but cannot declare ground truth true by itself.

---

# 163. No Auto-Label Assistance

Tool MUST NOT suggest:

```text
likely Android
probably laptop
JA4 matches iPhone
```

during labeling.

Ground truth must be recorded before fingerprint interpretation to avoid label contamination.

---

# 164. Device Inventory Privacy

Never store:

```text
owner name
phone number
account identifier
IMEI
serial number
SIM ICCID
personal hostname
person-linked asset tag
```

Manufacturer/model/OS are sufficient.

---

# 165. Controlled Network Behavior

Allowed controlled activity:

```text
Wi-Fi attach
captive portal flow
normal browser portal access
minimal benign connectivity needed for implemented evidence
```

No unrelated browsing to manufacture fingerprints.

---

# 166. Active Fingerprinting Forbidden

```text
port scan
JS probe
canvas/audio/WebGL
font enumeration
service discovery
device interrogation
```

03A remains passive/controlled observation.

---

# 167. Matrix Is Not Production Truth

Ground truth is exact for controlled lab samples only.

03A does not claim all devices of a platform resemble the lab devices.

Task-04 must evaluate generalization.

---

# 168. Coverage Limitation Codes

Manifest may include structured:

```text
no_chromeos
no_linux
quic_sparse
captive_context_unavailable
browser_diversity_limited
device_count_minimum_only
```

No uncontrolled free-text label required.

---

# 169. Task-04 Scope Must Follow Matrix Coverage

A production label unsupported by accepted 03A coverage cannot be claimed by Task-04.

Example:

```text
no sufficient ChromeOS labeled devices
-> no ChromeOS production classifier label
```

---

# 170. Source Eligibility Is Future Task-04 Work

03A records prevalence/missingness.

Task-04 later decides whether a source is mandatory, optional or ignored.

Sparse source != weak source.

Frequent source != strong source.

---

# 171. Ground Truth Correction

After seal, discovered labeling error creates a NEW matrix ID.

Old matrix is marked superseded and is excluded from new Task-04 experiments.

No in-place rewrite.

---

# 172. Matrix Supersession

Manifest:

```text
supersedes_matrix_id = UUID | null
```

Task-04 records the exact matrix ID used per experiment.

---

# 173. Source Schema Drift

If production evidence schema meaning changes during collection:

```text
STOP campaign for architecture review
```

Do not silently mix semantically different schema generations into one matrix.

---

# 174. Extractor Version Drift

Extractor versions/rule versions are retained in evidence provenance.

If meaning materially changes without schema change, TechLead decides whether collection must restart or split.

---

# 175. Site Scope

V1 matrix is single-Site:

```text
site_id = 6a64f17630da7c70d232187a
Site = Zefer_Parki
```

No multi-Site generalization claim.

---

# 176. Site Is Not A Feature

Future Task-04 MUST NOT use `site_id` as device-class feature in this single-Site dataset.

---

# 177. AP / SSID

AP MAC is not required in sealed matrix.

SSID semantic may be recorded in manifest as collection context, not classifier feature.

---

# 178. mac_mode_gt Research Role

`mac_mode_gt` is retained because randomized-MAC state can affect network evidence.

It remains context metadata, not identity confidence.

---

# 179. Quality-State Distribution

Per-source summaries preserve counts of:

```text
valid
partial
degraded
```

No confidence score is derived.

---

# 180. payload_sha256

Retained for provenance/variant counting only.

It is not device identity and must not be a direct Task-04 classifier feature.

---

# 181. Canonical Join Keys

```text
sample join = sample_id
physical-device grouping = lab_device_id
OS-state grouping = ground_truth_state_id
```

No MAC join exists in the sealed matrix.

---

# 182. Invalid Sample Audit


Invalid sample details remain outside the sealed classifier matrix.

`manifest.json` contains ONLY structured aggregate audit:

```text
invalid_sample_count
invalid_sample_reason_counts
```

Allowed reason keys:

```text
binding_uncertain
context_changed
window_too_long
evidence_missing
ground_truth_unverified
source_schema_error
privacy_violation
operator_abort
```

No free text.

No invalid sample row appears in sealed:

```text
samples.jsonl
```

---

# 183. No Free-Text Notes

Canonical matrix contains no uncontrolled free-text sample notes.

Research observations belong in separate reviewed reports.

---

# 184. Matrix Summary Report

After collection, Architect/TechLead may produce a separate descriptive report covering:

```text
coverage
source prevalence
context variation
missingness
known limitations
```

No classifier metrics.

---

# 185. No Accuracy Metrics In 03A

Forbidden as Task-03A outputs:

```text
accuracy
precision
recall
F1
ROC
confidence calibration
```

Those belong to Task-04.

---

# 186. Final Architecture Decision


Frozen:

```text
03A = lab/research dataset
NO production DB/schema/API changes
NO app runtime module
lab-only repository tooling
actual matrices outside Git
```

---

# 187. Final Ground Truth Model


Frozen:

```text
lab_device_id
ground_truth_state_id
sample_id
network_epoch_id
manual physical verification
manual cross-MAC binding only as lab truth
NO fingerprint-based identity merge
collection_authorized + control_basis_gt
```

---

# 188. Final V1 Coverage


Frozen minimum:

```text
12 physical devices
2 Android smartphones
2 iOS smartphones
2 Android tablets
2 iPadOS tablets
2 Windows laptops
2 macOS laptops
>=4 samples/device
>=2 network epochs/device
>=48 sealed samples
```

ChromeOS/Linux remain optional extensions.

---

# 189. Final Evidence Coverage


Frozen:

```text
five existing evidence schemas only
all five present somewhere
per mandatory device:
portal_headers
dhcp
tcp_syn
tls_client
present across sample set
QUIC = matrix-wide multi-platform target, not per-device mandatory
```

---

# 190. Final Matrix Files


Exact sealed structure:

```text
manifest.json
devices.jsonl
device_states.jsonl
samples.jsonl
evidence.jsonl
source_health.jsonl
checksums.sha256
```

No MAC/IP in sealed matrix.

---

# 191. Final Source-Health Semantics


Frozen point semantics:

```text
latest event at/before start
events inside [start,end)
latest event at/before end
NO inferred continuous interval
silence != unavailable
```

Use wording `source-health events`, not an assumption that every point is a
state transition.

---

# 192. Final Retention


Frozen:

```text
sealed matrix = 180 days
private binding = max 30 days, prefer delete after seal
raw = zero durable
actual matrix = NO Git
```

---

# 193. Final Lab Namespace


Accepted:

```text
research/device_fingerprint_03a/
```

No production runtime may depend on this namespace.

Lab tooling may import the approved canonical Task-01 read/validation helpers.

---

# 194. Final Calibration Set


Frozen:

```text
1 Android smartphone
1 iOS smartphone
1 Windows laptop
```

Calibration validates collection mechanics, including controlled MAC
rotation/new binding and captive/helper vs normal-browser variation where
supported.

It does NOT evaluate classifier quality.

---

# 195. Final Frozen Narrow Decisions


Frozen:

```text
lab repository namespace = research/device_fingerprint_03a/
sample interval = [start,end)
sealed samples only
canonical UUID/timestamp formats
12-device / 48-sample threshold
QUIC sparse rule
180-day matrix retention
source-health point-event read boundary
Gate A focused commands
PRE-COLLECTION ENVIRONMENT GATE
controlled collection mechanics
```

No broad research remains before TechLead10 FINAL consistency review.

---

# 196. FINAL Control Status


```text
TASK = TASK-DEVICE-FINGERPRINT-03A-FINAL
TITLE = Multi-Platform Labeled Evidence Matrix
REPOSITORY HEAD = 0355f236d4bc506426bea67c543289ce1b426046
REPOSITORY TREE = daa6b8e91c1bdd23f3e7d7a491ec95cb170ca780
ARCHITECTURE = PASS
TECHNICAL CONTRACT = COMPLETE
ARCHITECTURE DIRECTION = LAB / RESEARCH DATASET
PRODUCTION SCHEMA CHANGE = NO
PRODUCTION DB CHANGE = NO
PRODUCTION API CHANGE = NO
CLASSIFIER = NO
GROUND TRUTH = MANUALLY VERIFIED / COLLECTION-AUTHORIZED
CURRENT GATE = TECHLEAD10 FINAL CONSISTENCY REVIEW
TECHLEAD10 FINAL PASS = PENDING
OWNER TOOLING / EXECUTION AUTHORIZATION = NOT GRANTED
PRE-COLLECTION ENVIRONMENT GATE = NOT YET AUTHORIZED / NOT YET RUN
CODER = HOLD
TASK-04 = HOLD
NO IMPLEMENTATION
NO COLLECTION
NO BRANCH
NO COMMIT
NO PUSH
NO PR
NO DEPLOY
NO PRODUCTION ACTIVATION
```

---

# 197. Next Workflow


```text
TASK-DEVICE-FINGERPRINT-03A-FINAL
        ↓
TechLead10 FINAL consistency review
        ↓
FINAL PASS
        ↓
Owner explicit 03A tooling implementation authorization
        ↓
lab tooling implementation
        ↓
Gate A — focused tooling tests
        ↓
Gate B — static/source review
        ↓
Owner explicit collection-environment authorization
        ↓
PRE-COLLECTION ENVIRONMENT GATE
        ↓
Gate C — controlled physical calibration
        ↓
Gate D — full controlled collection
        ↓
Gate E — matrix validation
        ↓
Gate F — manual ground-truth audit
        ↓
Gate G — Task-04 admission review
        ↓
03A PASS
        ↓
TASK-04 architecture may begin
```

Until TechLead10 FINAL PASS + explicit Owner tooling authorization:

```text
CODER = HOLD
TASK-04 = HOLD
NO IMPLEMENTATION
NO COLLECTION
NO BRANCH
NO COMMIT
NO PUSH
NO PR
NO DEPLOY
NO PRODUCTION ACTIVATION
```

Even after tooling authorization:

```text
NO PHYSICAL COLLECTION
```

until:

```text
PRE-COLLECTION ENVIRONMENT GATE = PASS
```

**End of TASK-DEVICE-FINGERPRINT-03A-FINAL.**

---

