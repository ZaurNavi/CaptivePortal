# TASK-DEVICE-FINGERPRINT-03A-DRAFT

## Multi-Platform Labeled Evidence Matrix

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Prepared:** 2026-09-15  
**Status:** `FOR TECHLEAD10 SOURCE / ARCHITECTURE REVIEW`  
**Implementation-ready:** `NO`  
**Coder:** `HOLD`  
**Task-04:** `HOLD`  
**Production changes:** `NOT AUTHORIZED`

---

# 0. Architect Control Gate

```text
DEVICE-FINGERPRINT-00 = CLOSED / PASS
DEVICE-FINGERPRINT-01 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-02 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-03 = IMPLEMENTED / MERGED
DEVICE-FINGERPRINT-03A = THIS DRAFT
DEVICE-FINGERPRINT-04 = HOLD
DEVICE-FINGERPRINT-05 = HOLD
DEVICE-FINGERPRINT-06 = HOLD
```

Task-03A is a controlled empirical/lab stage before classification.

Task-03A is NOT a Classification Engine.

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

Ground truth is manually verified lab truth for Owner-controlled or explicitly Owner-authorized physical test devices.

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

# 25. Proposed Lab-Only Repository Namespace

Proposed new non-production namespace:

```text
research/device_fingerprint_03a/
```

Proposed files:

```text
README.md
format.py
exporter.py
validator.py
cli.py
```

This namespace MUST NOT be imported by `app/**` or `run.py`.

Because the current repository has no established `research/` runtime namespace, TechLead must source-bind this path before FINAL. A narrow path change is acceptable; moving 03A tooling into `app/**` is not.

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

# 27. Matrix Version

```text
matrix_format_version = 1
matrix_id = UUID4
matrix_revision = 1
```

A sealed matrix is immutable.

Any content correction creates a NEW `matrix_id`.

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

# 34. Provenance Is Not Classifier Feature

Task-04 MUST NOT use these as device features without a separate explicit contract:

```text
evidence_id
source_event_id
producer_id
site_id
capture_source_id
ingested_at
sample_id
lab_device_id
payload_sha256 itself
```

They are provenance/grouping metadata.

---

# 35. Ground Truth Device Record

`devices.jsonl` required fields:

```text
matrix_format_version
lab_device_id
device_class_gt
manufacturer_gt
model_gt
owner_controlled
ground_truth_verified_at
ground_truth_verification_methods
```

Optional:

```text
hardware_variant_gt
```

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

# 43. Owner-Controlled Requirement

Every device requires:

```text
owner_controlled = true
```

Unknown/uncontrolled device:

```text
NOT ADMITTED
```

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
sample_id = UUID4
```

One sample references exactly one:

```text
lab_device_id
ground_truth_state_id
```

---

# 46. Collection Run

```text
collection_run_id = UUID4
```

A run may contain multiple samples/devices and records procedure/repository/environment provenance.

---

# 47. Sample Required Fields

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

`browser_version_major_gt` may be null.

---

# 48. Sample Window

```text
0 < duration <= 600 seconds
```

Longer test activity becomes another sample.

The 10-minute cap reduces unrelated traffic and keeps context reviewable.

---

# 49. Context Stability

Within one sample do NOT change:

```text
physical device
OS state
browser/runtime context
current MAC binding
network attachment identity
```

Unexpected change:

```text
sample_status = invalid
```

and start a new sample.

---

# 50. network_epoch_id

```text
network_epoch_id = UUID4
```

A controlled disconnect/reconnect creating a fresh network attachment creates a new epoch.

Multiple browser-context samples may share one epoch.

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

For each source/sample capture:

```text
latest point at/before sample start
all health transitions inside sample window
latest point at/before sample end
```

Deduplicate identical health-event IDs.

No interval certainty is synthesized.

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

# 83. Sample Source Summary

For all five source kinds record descriptive:

```text
evidence_count
valid_count
partial_count
degraded_count
distinct_payload_sha256_count
first_observed_at
last_observed_at
```

No confidence meaning.

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

# 91. Sample Status

Allowed during collection:

```text
draft
sealed
invalid
```

Only `sealed` valid samples enter the classifier matrix.

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
```

After sealing, correction requires a new sample/matrix revision process.

---

# 93. Controlled Collection Procedure

Required:

```text
YES
```

Random production visitors are forbidden as 03A labeled subjects.

---

# 94. Owner Manual Enrollment

For each physical device Owner/operator must:

```text
assign lab_device_id
verify device class
verify manufacturer/model
verify OS family/version in Settings/About
create ground_truth_state_id
confirm authorized lab ownership/control
```

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

# 100. Controlled Calibration Gate

Before the full 48-sample campaign, run limited procedure calibration using:

```text
1 Android smartphone
1 iOS smartphone
1 Windows laptop
```

Purpose:

```text
validate procedure
validate exporter
validate windows/bindings
validate source-health snapshot
validate de-identification
observe source prevalence
```

Not classifier research.

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
known_coverage_limitations
file_sha256
supersedes_matrix_id
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

Existing public Python read service exposes latest health point but not full sample-window transition history.

Lab-only tooling MAY use Task-01 existing read-only SQLite connection helper to query only `device_fingerprint_source_health_events` for the bounded sample/source scopes.

No production API/read-service expansion is required.

---

# 112. Source-Health Query Bound

For each sample/source query only:

```text
one latest event before start
all events inside [start,end]
one latest event at/before end
```

Strict Site + capture_source + source_kind scope.

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

# 130. Checksums

`checksums.sha256` covers all sealed files except itself:

```text
manifest.json
devices.jsonl
device_states.jsonl
samples.jsonl
evidence.jsonl
source_health.jsonl
```

Any mismatch invalidates matrix.

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
invalid UUID/timestamp
non-printable label string
owner_controlled != true
```

No best-effort coercion.

---

# 133. Sample Schema Validation

Reject:

```text
end <= start
duration >600s
unknown device/state
state belongs to another device
invalid context enum
invalid portal mode
invalid sample status
```

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

# 135. Temporal Validation

Require:

```text
window_start <= evidence.observed_at <= window_end
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

If tooling implementation is later authorized, Coder runs focused tests under:

```text
tests/device_fingerprint_matrix/
```

Coverage:

```text
format schemas
ground-truth validation
sample temporal rules
de-identification
canonical payload revalidation
source-health snapshot
binding collision detection
evidence uniqueness
deterministic JSONL
checksums
privacy canaries
read-only DB behavior
```

Exact commands freeze after TechLead source review.

---

# 150. Gate B — Tech Lead Static / Source Review

Verify:

```text
no app runtime import
no production schema change
read-only evidence access
five source contracts exact
MAC/IP absent from sealed matrix
ground truth separate
no classifier logic
no feature-engineering table
privacy/retention exact
```

---

# 151. Gate C — Controlled Calibration

Use:

```text
1 Android smartphone
1 iOS smartphone
1 Windows laptop
```

Prove procedure, exporter, windows/bindings, source-health snapshot, de-identification and sealing/checksums.

---

# 152. Gate D — Full V1 Collection

Execute controlled campaign to reach mandatory 12-device / >=48-sample coverage.

Owner or explicitly authorized lab operator performs physical labels.

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
all invalid/excluded reason counts
```

No classifier output may confirm labels.

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

# 156. Production Regression

03A dataset collection is lab-only and should not alter production runtime.

If tooling implementation touches any production `app/**` runtime file:

```text
STOP
```

That is an architecture boundary violation.

---

# 157. Proposed NEW Repository Files

```text
research/device_fingerprint_03a/README.md
research/device_fingerprint_03a/format.py
research/device_fingerprint_03a/exporter.py
research/device_fingerprint_03a/validator.py
research/device_fingerprint_03a/cli.py

tests/device_fingerprint_matrix/__init__.py
tests/device_fingerprint_matrix/test_format.py
tests/device_fingerprint_matrix/test_exporter.py
tests/device_fingerprint_matrix/test_validator.py
tests/device_fingerprint_matrix/test_privacy.py

docs/research/device-fingerprint-03a.md
```

Exact non-production root needs TechLead PASS before FINAL.

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

# 159. Explicit NO-TOUCH

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

---

# 160. No New Runtime Config / Service

03A introduces no production env prefix, systemd unit, daemon, worker, HTTP endpoint or scheduled production job.

Collection/export is operator-invoked only.

---

# 161. Exporter Inputs

Conceptual explicit inputs:

```text
Task-01 DB path
matrix staging directory
site_id
collection-run metadata
private binding ledger
sample definitions
repository HEAD/TREE
```

No production secret is required.

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

Manifest/audit may retain only counts and structured exclusion reasons.

Allowed reasons:

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

# 186. TechLead10 Review — Architecture Decision

Please PASS/FIX:

```text
03A = lab/research dataset
NO production DB/schema changes
NO app runtime module
lab-only repository tooling
actual matrices outside Git
```

---

# 187. TechLead10 Review — Ground Truth Model

Please PASS/FIX:

```text
lab_device_id
ground_truth_state_id
sample_id
network_epoch_id
manual physical verification
manual cross-MAC binding only as lab truth
NO fingerprint-based identity merge
```

---

# 188. TechLead10 Review — V1 Coverage

Please PASS/FIX:

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

ChromeOS/Linux optional extension.

---

# 189. TechLead10 Review — Evidence Coverage

Please PASS/FIX:

```text
five existing sources only
all five present somewhere
per mandatory device:
portal_headers + dhcp + tcp_syn + tls_client
QUIC matrix-wide multi-platform target, not per-device mandatory
```

---

# 190. TechLead10 Review — Matrix Files

Please PASS/FIX:

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

# 191. TechLead10 Review — Source Health

Please PASS/FIX:

```text
point semantics preserved
latest-before-start
during-window
latest-at-end
NO inferred continuous interval
silence != unavailable
```

---

# 192. TechLead10 Review — Retention

Please PASS/FIX:

```text
sealed matrix = 180 days
private binding = max 30 days, preferably delete after seal
raw = zero durable
actual matrix = no Git
```

---

# 193. TechLead10 Review — Lab Namespace

Please source-bind whether:

```text
research/device_fingerprint_03a/
```

is acceptable.

If repository governance prefers another non-production namespace, return a narrow FIX.

Do NOT move tooling into `app/**`.

---

# 194. TechLead10 Review — Calibration

Please PASS/FIX calibration set:

```text
1 Android smartphone
1 iOS smartphone
1 Windows laptop
```

Calibration validates collection mechanics, not classifier quality.

---

# 195. DRAFT Open Items

No broad research requested.

Narrow decisions before FINAL:

```text
1. lab repository namespace
2. exact JSON schema implementation
3. 12-device / 48-sample threshold
4. QUIC sparse-coverage rule
5. 180-day sealed-matrix retention
6. source-health lab query boundary
7. focused Gate A commands
8. collection procedure wording
```

---

# 196. Control Status

```text
TASK = TASK-DEVICE-FINGERPRINT-03A-DRAFT
TITLE = Multi-Platform Labeled Evidence Matrix
REPOSITORY HEAD = 0355f236d4bc506426bea67c543289ce1b426046
REPOSITORY TREE = daa6b8e91c1bdd23f3e7d7a491ec95cb170ca780
ARCHITECTURE DIRECTION = LAB / RESEARCH DATASET
PRODUCTION SCHEMA CHANGE = NO
PRODUCTION DB CHANGE = NO
CLASSIFIER = NO
GROUND TRUTH = OWNER-CONTROLLED MANUAL
IMPLEMENTATION-READY = NO
CURRENT GATE = TECHLEAD10 SOURCE / ARCHITECTURE REVIEW
CODER = HOLD
TASK-04 = HOLD
PRODUCTION CHANGES = NOT AUTHORIZED
NO IMPLEMENTATION
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
TASK-DEVICE-FINGERPRINT-03A-DRAFT
        ↓
TechLead10 source / architecture review
        ↓
PASS or narrow FIX
        ↓
Architect + TechLead10
TASK-DEVICE-FINGERPRINT-03A-FINAL
        ↓
TechLead10 FINAL consistency PASS
        ↓
Owner explicit 03A tooling/execution authorization
        ↓
lab tooling implementation if required
        ↓
Gate A — focused tooling tests
        ↓
Gate B — static/source review
        ↓
Gate C — controlled calibration
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

Until explicit Owner authorization:

```text
CODER = HOLD
TASK-04 = HOLD
NO IMPLEMENTATION
NO BRANCH
NO COMMIT
NO PUSH
NO PR
NO DEPLOY
NO PRODUCTION ACTIVATION
```

**End of TASK-DEVICE-FINGERPRINT-03A-DRAFT.**
