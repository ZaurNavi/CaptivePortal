# TASK-DEVICE-FINGERPRINT-03A-COLLECTION-EXECUTION-DRAFT

## Multi-Platform Labeled Evidence Matrix — Collection Execution Runbook

**Project:** CaptivPortal  
**Program:** Device Fingerprint  
**Parent contract:** `TASK-DEVICE-FINGERPRINT-03A-FINAL — Multi-Platform Labeled Evidence Matrix`  
**Prepared:** 2026-09-15  
**Status:** `FOR TECHLEAD10 EXECUTION / RUNBOOK REVIEW`  
**03A tooling:** `IMPLEMENTED / ACCEPTED / MERGED`  
**03A collection:** `PENDING`  
**Task-04:** `HOLD`  
**Coder:** `HOLD`  
**New development:** `NOT AUTHORIZED`  
**Deploy / production activation:** `NOT AUTHORIZED`  
**Collection:** `FORBIDDEN UNTIL PRE-COLLECTION ENVIRONMENT GATE PASS`

---

# 0. Execution Control Gate

```text
repository =
ZaurNavi/CaptivePortal

main HEAD =
ea5f16594d9d7a04c8f629d5329f3ea041b36d4e

main TREE =
66f9292c7843c4c3610060a72a8768ec5041080f

PR #125 =
MERGED

TASK-DEVICE-FINGERPRINT-03A TOOLING =
IMPLEMENTED / ACCEPTED / MERGED

REAL LABELED MATRIX =
NOT YET CREATED

TASK-04 =
HOLD
```

This document is an execution/runbook phase of the already accepted 03A
architecture.

It MUST NOT redesign 03A.

---

# 1. Frozen V1 Collection Contract

Do not change:

```text
12 mandatory physical devices

>= 48 sealed valid samples

>= 4 samples/device

>= 2 network epochs/device

2 Android smartphones
2 iOS smartphones

2 Android tablets
2 iPadOS tablets

2 Windows laptops
2 macOS laptops
```

Do not change:

```text
five production evidence schemas

ground-truth model

privacy boundaries

sealed dataset format

checksums contract

half-open sample windows

source-health point-event semantics
```

---

# 2. Canonical Execution Chain

```text
PRE-COLLECTION ENVIRONMENT GATE
        ↓
Gate C — Controlled Calibration
        ↓
Gate D — Full V1 Collection
        ↓
Gate E — Matrix Validation
        ↓
Gate F — Manual Ground Truth Audit
        ↓
Gate G — Task-04 Admission Review
        ↓
TASK-DEVICE-FINGERPRINT-03A = PASS
        ↓
TASK-DEVICE-FINGERPRINT-04 architecture may start
```

Task-04 remains HOLD until Gate G PASS.

---

# 3. Merged Tooling Source Of Truth

Accepted lab namespace:

```text
research/device_fingerprint_03a/
```

Merged files:

```text
README.md
cli.py
exporter.py
format.py
validator.py
```

Operator CLI:

```text
python -m research.device_fingerprint_03a.cli
```

Actual subcommands:

```text
validate-staging
export
seal
validate
summary
```

This runbook uses those commands exactly.

No new tooling is introduced here.

---

# 4. Tooling Operational Facts

Merged tooling enforces:

```text
all path arguments =
absolute paths

Task-01 DB =
read through canonical read-only/query-only boundary

output-dir =
must be absent or an empty safe directory

environment-record =
must exist as an absolute file path

samples in staging =
already sample-level sealed

export =
creates UNSEALED matrix manifest

seal =
requires --owner-verified

checksums =
written only during matrix seal

validate/summary =
strict canonical matrix validation/report
```

`--calibration` disables only full V1 coverage admission.

It does NOT disable format/privacy/checksum validation.

---

# 5. Two Different Sealing Moments

Do not confuse:

```text
SAMPLE-LEVEL SEAL
```

with:

```text
MATRIX-LEVEL SEAL
```

Before `validate-staging` / `export`, each accepted staging sample must already
contain:

```text
sample_status = sealed

sealed_at =
canonical UTC timestamp
```

This means Owner/operator has accepted the sample ground truth/context.

After export, the matrix manifest remains:

```text
sealed_at = null
```

until:

```text
cli seal --owner-verified
```

successfully validates the matrix and writes `checksums.sha256`.

---

# 6. PRE-COLLECTION ENVIRONMENT GATE — Objective

Before any physical sample collection, prove and record:

```text
exact Task-01 evidence DB/read boundary

exact tooling execution host

exact repository checkout

exact read-only DB access mode

exact staging location

exact private binding-ledger location

exact unsealed/sealed matrix location

ownership / access policy

available free space

Python/runtime availability

Site / SSID

five evidence-source availability

source-health evidence availability
```

No physical calibration starts before PASS.

---

# 7. Values Known From Repository

Repository default Task-01 DB path is:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3
```

However this is a repository default.

The effective deployed path may be overridden.

Therefore Gate requires:

```text
EFFECTIVE_TASK01_DB_PATH =
OWNER / SYSADMIN PRECHECK REQUIRED
```

Do NOT assume the repository default is the effective production path without
verification.

---

# 8. Environment Values That MUST Be Filled

Create an execution precheck record and fill:

```text
EXECUTION_HOST =
OWNER / SYSADMIN PRECHECK REQUIRED

REPO_ROOT =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

TASK01_DB_HOST =
OWNER / SYSADMIN PRECHECK REQUIRED

TASK01_DB_PATH =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

DB_ACCESS_MODE =
LOCAL_CANONICAL_READ_ONLY
or
AUTHORIZED_READ_ONLY_SNAPSHOT

STAGING_ROOT =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

BINDING_LEDGER_ROOT =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

UNSEALED_MATRIX_ROOT =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

SEALED_MATRIX_ROOT =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

ENVIRONMENT_RECORD =
OWNER / SYSADMIN PRECHECK REQUIRED
absolute path

SITE_ID =
6a64f17630da7c70d232187a

SSID =
Zefer_Parki

AVAILABLE_BYTES =
OWNER / SYSADMIN PRECHECK REQUIRED

LAB_OPERATOR_OS_USER =
OWNER / SYSADMIN PRECHECK REQUIRED

LAB_OPERATOR_GROUP =
OWNER / SYSADMIN PRECHECK REQUIRED
```

No guessed UID/GID/path is permitted.

---

# 9. Allowed DB Access Modes

Exactly one mode must be frozen before Gate PASS.

## Mode A — LOCAL_CANONICAL_READ_ONLY

Tooling runs on an Owner-authorized host that can read the live Task-01 DB using
the merged canonical:

```text
open_read_only
DeviceFingerprintReadService
```

Requirements:

```text
explicit Owner authorization for that host

no production DB mutation

exporter before/after durable DB fingerprint remains equal

PRAGMA query_only = 1
```

If the host is production:

```text
separate explicit Owner production-host read authorization =
MANDATORY
```

## Mode B — AUTHORIZED_READ_ONLY_SNAPSHOT

Sysadmin provides a consistent SQLite snapshot to the authorized lab execution
host.

Forbidden:

```text
blind copy of a live WAL-mode main DB file
without an approved consistent snapshot method
```

Exact snapshot method/path:

```text
OWNER / SYSADMIN PRECHECK REQUIRED
```

Snapshot must be made read-only to the lab operator after creation.

---

# 10. Environment Authorization Record

Execution artifact outside Git:

```text
environment-authorization.json
```

The merged exporter checks that the supplied environment-record file exists;
the content is manually reviewed by Owner + TechLead.

Recommended required execution fields:

```text
record_version

owner_environment_authorized

authorized_at

repository_head

repository_tree

execution_host

repo_root

task01_db_host

task01_db_path

db_access_mode

staging_root

binding_ledger_root

unsealed_matrix_root

sealed_matrix_root

lab_operator_os_user

lab_operator_group

site_id

ssid

available_bytes

source_precheck_result

sysadmin_precheck_result

techlead_environment_gate_result
```

No person identity is required; role identifiers are sufficient.

Gate PASS requires:

```text
owner_environment_authorized = true

techlead_environment_gate_result = PASS
```

---

# 11. Repository / Runtime Precheck

On the authorized execution host:

```bash
cd "<ABS_REPO_ROOT>"

git rev-parse HEAD
git rev-parse HEAD^{tree}

python3 --version

python -m research.device_fingerprint_03a.cli --help
```

Required exact Git output:

```text
HEAD =
ea5f16594d9d7a04c8f629d5329f3ea041b36d4e

TREE =
66f9292c7843c4c3610060a72a8768ec5041080f
```

Mismatch:

```text
BLOCKED
→ TechLead source rebind
```

Python must be the same accepted project runtime capable of importing the
merged repository.

No package installation is authorized by this runbook.

---

# 12. DB Path / Read Boundary Precheck

After Owner authorization, verify:

```text
DB path exists

regular file

not a symlink

readable by selected tooling execution identity
```

Then execute from exact merged repository:

```bash
TASK01_DB_PATH="<ABS_TASK01_DB_PATH>" python - <<'PY'
import os
from app.device_fingerprint.repository import open_read_only

db = os.environ["TASK01_DB_PATH"]
connection = open_read_only(db)
try:
    query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    print("query_only=", query_only)
    print("user_version=", user_version)
finally:
    connection.close()
PY
```

PASS:

```text
query_only = 1
user_version = 1
```

Any open/read/schema failure:

```text
BLOCKED
```

No write test is performed against the production DB.

---

# 13. Free Space / Ownership Precheck

Record, but do not guess:

```bash
df -h "<ABS_STAGING_ROOT>"
df -h "<ABS_UNSEALED_MATRIX_ROOT>"
df -h "<ABS_SEALED_MATRIX_ROOT>"
```

Actual:

```text
AVAILABLE_BYTES =
record exact result
```

There is no architecture-frozen byte threshold.

Therefore:

```text
TechLead must explicitly mark storage budget PASS
before collection
```

If no budget is approved:

```text
BLOCKED
```

Minimum access policy:

```text
private binding ledger =
read/write only by authorized lab operator
and explicitly authorized reviewers

staging =
write by authorized lab operator
read only by approved reviewers

sealed matrix =
after sealing, no in-place content editing

world-readable =
FORBIDDEN
```

Exact UID/GID/ACL/modes are Sysadmin precheck values, not guessed here.

---

# 14. Current Evidence Source Precheck — Exact Sources

Check these five exact production sources:

```text
dhcp
tcp_syn
tls_client
quic_client
portal_headers
```

Expected provenance:

```text
dhcp/tcp_syn/tls_client/quic_client:
producer_id = sensor-zefer-01
capture_source_id = zefer-span-01

portal_headers:
producer_id = portal-zefer-01
capture_source_id = zefer-portal-http-01

site_id =
6a64f17630da7c70d232187a
```

---

# 15. Read-Only Source Availability Command

Run ONLY after environment authorization:

```bash
TASK01_DB_PATH="<ABS_TASK01_DB_PATH>" python - <<'PY'
import os, json
from app.device_fingerprint.repository import open_read_only

SITE = "6a64f17630da7c70d232187a"
SOURCES = {
    "dhcp": ("sensor-zefer-01", "zefer-span-01"),
    "tcp_syn": ("sensor-zefer-01", "zefer-span-01"),
    "tls_client": ("sensor-zefer-01", "zefer-span-01"),
    "quic_client": ("sensor-zefer-01", "zefer-span-01"),
    "portal_headers": ("portal-zefer-01", "zefer-portal-http-01"),
}

connection = open_read_only(os.environ["TASK01_DB_PATH"])
try:
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 1

    for kind, (producer, capture) in SOURCES.items():
        evidence = connection.execute(
            "SELECT evidence_id,producer_id,capture_source_id,quality_state,observed_at "
            "FROM device_fingerprint_evidence "
            "WHERE site_id=? AND source_kind=? "
            "ORDER BY observed_at DESC,evidence_id DESC LIMIT 1",
            (SITE, kind),
        ).fetchone()

        health = connection.execute(
            "SELECT source_health_event_id,producer_id,capture_source_id,status,reason_code,observed_at "
            "FROM device_fingerprint_source_health_events "
            "WHERE site_id=? AND capture_source_id=? AND source_kind=? "
            "ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
            (SITE, capture, kind),
        ).fetchone()

        print(json.dumps({
            "source_kind": kind,
            "expected_producer_id": producer,
            "expected_capture_source_id": capture,
            "latest_evidence": dict(evidence) if evidence else None,
            "latest_source_health": dict(health) if health else None,
        }, sort_keys=True))
finally:
    connection.close()
PY
```

This does not generate traffic.

It observes the retained Task-01 evidence state only.

---

# 16. Source Availability Classification

For each source record exactly one result:

```text
PASS_OBSERVED
MISSING
BLOCKED
SPARSE_ACCEPTED
```

## PASS_OBSERVED

Requires:

```text
latest_evidence exists

producer_id matches expected

capture_source_id matches expected

quality_state is canonical
```

and no newer/equal explicit source-health point contradicts it with:

```text
unavailable
or
unsupported
```

A later evidence event after an older negative health point is accepted as proof
that the source subsequently produced evidence.

## BLOCKED

Any:

```text
provenance mismatch

DB/query failure

latest explicit negative health point
is at/after latest evidence

source health says unsupported
with no later evidence
```

## MISSING

```text
no retained evidence row exists
```

and availability cannot be proven.

## SPARSE_ACCEPTED

Only for:

```text
quic_client
```

when:

```text
retained valid evidence exists
but expected collection prevalence is sparse
```

This does NOT waive the final validator requirement that the sealed V1 matrix
contain valid QUIC evidence somewhere.

---

# 17. Source-Health Precheck

Required source-health scopes:

```text
zefer-span-01:
dhcp
tcp_syn
tls_client
quic_client

zefer-portal-http-01:
portal_headers
```

For each, record:

```text
latest point-event timestamp
status
reason_code
```

Do NOT infer a continuous interval.

Permanent:

```text
silence != unavailable
```

A missing source-health history:

```text
MISSING
→ TechLead review required
```

Environment Gate does not silently fabricate availability.

---

# 18. PRE-COLLECTION ENVIRONMENT GATE — PASS Checklist

All must be checked:

```text
[ ] Owner separately authorized collection environment.

[ ] Exact execution host frozen.

[ ] Exact Task-01 DB host/path frozen.

[ ] DB access mode frozen.

[ ] DB opens via canonical read-only/query-only boundary.

[ ] repository HEAD exact.

[ ] repository TREE exact.

[ ] Python imports merged tooling.

[ ] absolute staging root frozen.

[ ] absolute binding-ledger root frozen.

[ ] absolute unsealed-matrix root frozen.

[ ] absolute sealed-matrix root frozen.

[ ] environment-record absolute path exists.

[ ] actual UID/GID/access policy reviewed.

[ ] actual free space recorded and TechLead accepted.

[ ] Site = 6a64f17630da7c70d232187a.

[ ] SSID = Zefer_Parki.

[ ] dhcp source precheck PASS.

[ ] tcp_syn source precheck PASS.

[ ] tls_client source precheck PASS.

[ ] portal_headers source precheck PASS.

[ ] quic_client = PASS_OBSERVED or SPARSE_ACCEPTED.

[ ] required source-health scopes reviewed.

[ ] no automatic production deploy/config change was performed.

[ ] exact data-transfer mechanics frozen if DB is off-host snapshot.

[ ] TechLead environment gate result = PASS.
```

Any unchecked required item:

```text
NO COLLECTION
```

---

# 19. Owner Device Inventory — Fill Before Gate C/D

Status values:

```text
AVAILABLE
MISSING
TO SOURCE
```

Do not infer availability.

| CELL | PLANNER ALIAS | DEVICE # | AUTHORIZED? | MANUFACTURER | MODEL | OS FAMILY | OS VERSION | CAPTIVE CONTEXT AVAILABLE? | RANDOMIZED MAC AVAILABLE? | STATUS |
|---|---|---:|---|---|---|---|---|---|---|---|
| Android smartphone | AS-01 | 1 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| Android smartphone | AS-02 | 2 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| iOS smartphone | IS-01 | 1 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| iOS smartphone | IS-02 | 2 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| Android tablet | AT-01 | 1 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| Android tablet | AT-02 | 2 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| iPadOS tablet | IT-01 | 1 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| iPadOS tablet | IT-02 | 2 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| Windows laptop | WL-01 | 1 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| Windows laptop | WL-02 | 2 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| macOS laptop | ML-01 | 1 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |
| macOS laptop | ML-02 | 2 | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<FILL>` | `<YES/NO>` | `<YES/NO>` | `<AVAILABLE/MISSING/TO SOURCE>` |

Gate D cannot start until all 12 mandatory slots are:

```text
AVAILABLE
```

with collection authorization verified.

---

# 20. Ground-Truth Enrollment — Per Physical Device

Owner/operator performs in this order:

```text
1.
physically identify controlled/authorized device

2.
confirm:
collection_authorized = true

3.
record:
control_basis_gt =
owner_controlled
or
explicitly_authorized

4.
generate canonical lowercase UUID4:
lab_device_id

5.
verify:
device_class_gt

6.
verify:
manufacturer_gt

7.
verify:
model_gt

8.
open Settings/About

9.
verify:
os_family_gt
os_version_gt
os_major_gt

10.
generate:
ground_truth_state_id

11.
record verification methods

12.
record canonical ground-truth timestamps

13.
only after ground truth is fixed:
begin fingerprint sample collection
```

No fingerprint evidence is viewed to decide the label.

---

# 21. Canonical UUID / Timestamp Helpers

UUID4:

```bash
python -c "import uuid; print(uuid.uuid4())"
```

Canonical UTC milliseconds:

```bash
python -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f'{datetime.now(timezone.utc).microsecond//1000:03d}Z')"
```

Operator must verify final written value has exact:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

Do not hand-invent UUID spelling.

---

# 22. Ground-Truth Staging Files

Staging contains:

```text
devices.jsonl

device_states.jsonl

samples.jsonl

collection_bindings.jsonl
```

`collection_bindings.jsonl` is private and MUST NOT be copied into sealed matrix.

Before export, run:

```bash
python -m research.device_fingerprint_03a.cli validate-staging   --staging-dir "<ABS_STAGING_DIR>"
```

PASS is exit:

```text
0
```

with canonical JSON result containing counts.

Exit 2 / `invalid_matrix`:

```text
STOP
```

Do not bypass the validator.

---

# 23. Private Binding Ledger — Exact Operational Role

One binding row per sample contains:

```text
sample_id

lab_device_id

observed_mac

optional observed_ip
```

Binding is entered from the Owner-controlled device/network state.

It is NOT inferred from fingerprints.

MAC change:

```text
new sample_id

normally new network_epoch_id

same lab_device_id only after manual physical verification
```

Binding ledger remains outside Git and outside sealed matrix.

---

# 24. Gate C — Calibration Devices

Use exactly:

```text
1 Android smartphone

1 iOS smartphone

1 Windows laptop
```

No extension during calibration.

Gate C occurs only after:

```text
PRE-COLLECTION ENVIRONMENT GATE = PASS
```

---

# 25. Gate C — Calibration Run Sequence

For each calibration device:

```text
A.
complete ground-truth enrollment

B.
create at least one controlled sample

C.
record current MAC in private binding ledger

D.
create exact [start,end) window

E.
perform minimal controlled activity

F.
sample-level review

G.
mark sample:
sample_status = sealed
sealed_at = canonical UTC

H.
validate staging

I.
export calibration matrix

J.
matrix seal with:
--calibration
--owner-verified

K.
validate with:
--calibration

L.
summary with:
--calibration
```

Calibration uses a separate calibration matrix ID.

Calibration samples do not automatically count toward the final V1 matrix.

---

# 26. Gate C — Mandatory MAC-Rotation Mechanics Proof

At least one calibration device must support a controlled new MAC binding.

Required proof:

```text
same physical device

old sample:
lab_device_id = X
sample_id = A
network_epoch_id = E1
MAC = M1

controlled MAC rotation/new binding

new sample:
lab_device_id = SAME X
sample_id = B
network_epoch_id = normally E2
MAC = M2
```

Owner manually verifies physical identity.

Fingerprint similarity is NOT used.

If no calibration device can perform this proof:

```text
Gate C FAIL
→ STOP
→ TechLead review
```

---

# 27. Gate C — Mandatory Runtime Context Proof

On at least one supported calibration device collect separate samples for:

```text
captive_webview
or
captive_helper

VERSUS

normal_browser
```

Each has:

```text
new sample_id
```

If captive/helper is genuinely unsupported on selected device, another supported
calibration device must be used.

If none of the three controlled devices supports reproducible context variation:

```text
Gate C FAIL
→ TechLead review
```

No classifier accuracy is evaluated.

---

# 28. Gate C — Calibration Export Commands

Set execution variables only after Gate PASS:

```bash
REPO_ROOT="<ABS_REPO_ROOT>"
DB_PATH="<ABS_TASK01_DB_PATH>"
STAGING_DIR="<ABS_CALIBRATION_STAGING_DIR>"
OUTPUT_DIR="<ABS_EMPTY_CALIBRATION_OUTPUT_DIR>"
ENV_RECORD="<ABS_ENVIRONMENT_RECORD>"
MATRIX_ID="<UUID4>"
```

Validate staging:

```bash
cd "$REPO_ROOT"

python -m research.device_fingerprint_03a.cli validate-staging   --staging-dir "$STAGING_DIR"
```

Export:

```bash
python -m research.device_fingerprint_03a.cli export   --db-path "$DB_PATH"   --staging-dir "$STAGING_DIR"   --output-dir "$OUTPUT_DIR"   --environment-record "$ENV_RECORD"   --matrix-id "$MATRIX_ID"   --repository-head "ea5f16594d9d7a04c8f629d5329f3ea041b36d4e"   --repository-tree "66f9292c7843c4c3610060a72a8768ec5041080f"   --collection-procedure-version "1.0.0"   --ground-truth-policy-version "1.0.0"   --task01-retention-days 30
```

Matrix-level seal:

```bash
SEALED_AT="<YYYY-MM-DDTHH:MM:SS.mmmZ>"

python -m research.device_fingerprint_03a.cli seal   --matrix-dir "$OUTPUT_DIR"   --sealed-at "$SEALED_AT"   --owner-verified   --calibration
```

Validate:

```bash
python -m research.device_fingerprint_03a.cli validate   --matrix-dir "$OUTPUT_DIR"   --calibration
```

Summary:

```bash
python -m research.device_fingerprint_03a.cli summary   --matrix-dir "$OUTPUT_DIR"   --calibration
```

---

# 29. Gate C — PASS Checklist

```text
[ ] exactly 1 Android smartphone used

[ ] exactly 1 iOS smartphone used

[ ] exactly 1 Windows laptop used

[ ] staging validator PASS

[ ] private binding ledger maps each sample exactly once

[ ] exporter opens Task-01 read-only

[ ] [start,end) evidence assignment verified

[ ] source-health point snapshot exported

[ ] MAC absent from sealed evidence

[ ] client IP absent from sealed evidence

[ ] raw UA/Client Hints absent

[ ] matrix seal PASS

[ ] checksums.sha256 exists

[ ] calibration validate PASS

[ ] calibration summary PASS

[ ] >=1 controlled MAC rotation proof PASS

[ ] captive/helper vs normal-browser mechanics proof PASS

[ ] no production DB change

[ ] no production config/deploy change
```

Any mandatory FAIL:

```text
Gate C = FAIL
```

Tooling defect:

```text
STOP
RETURN TO TECHLEAD
```

Do not patch tooling from the runbook.

---

# 30. Exact Sample Collection Runbook

For EVERY sample:

```text
1.
identify physical device

2.
verify current lab_device_id

3.
verify current ground_truth_state_id

4.
verify collection_authorized

5.
read current Wi-Fi MAC from controlled device/network state

6.
record current MAC in PRIVATE collection_bindings.jsonl

7.
record mac_mode_gt

8.
establish/reuse network_epoch_id according to actual attachment

9.
record:
network_state_gt

10.
record:
runtime_context_gt

11.
record:
browser_family_gt

12.
record:
browser_version_major_gt when known

13.
record:
portal_entry_mode_gt

14.
capture exact window_start_utc

15.
perform ONLY minimal controlled activity for this sample type

16.
capture exact window_end_utc

17.
verify:
window_start < window_end
duration <= 600 seconds

18.
verify NO mid-window:
MAC change
OS change
browser/runtime change
physical-device change
network attachment identity change

19.
inspect sample ground truth/context

20.
if accepted:
sample_status = sealed
sealed_at = canonical UTC timestamp

21.
if invalid:
record canonical invalid reason OUTSIDE sealed samples.jsonl

22.
run validate-staging before export batch
```

---

# 31. Controlled Activity — Fresh Attach

For:

```text
network_state_gt =
fresh_attach
```

minimal procedure:

```text
1.
disconnect Wi-Fi

2.
verify intended controlled SSID

3.
connect/reconnect

4.
allow ordinary DHCP/network establishment

5.
enter the intended captive portal path

6.
complete the minimal portal interaction needed
for normal connectivity

7.
perform no unrelated browsing

8.
end sample when the intended context evidence window is complete
```

Natural expected evidence may include:

```text
dhcp
tcp_syn
tls_client
portal_headers
possibly quic_client
```

Do not require every source in the sample.

---

# 32. Controlled Activity — Captive Helper / WebView

For:

```text
runtime_context_gt =
captive_webview
or
captive_helper
```

procedure:

```text
use only the platform's naturally opened
captive/helper context

enter the portal normally

do not inject JavaScript

do not open unrelated sites

do not switch to normal browser mid-window
```

If helper closes and normal browser is opened:

```text
END current sample
START new sample
```

---

# 33. Controlled Activity — Normal Browser Revisit

For:

```text
network_state_gt =
same_attachment_revisit

runtime_context_gt =
normal_browser
```

procedure:

```text
keep same network attachment

open one Owner-approved normal browser

access the normal portal/login surface

allow minimal benign HTTPS connectivity
needed for the ordinary flow

do not switch browser mid-window
```

Browser change:

```text
new sample_id
```

---

# 34. QUIC Activity

QUIC is allowed to occur naturally.

Do NOT:

```text
generate synthetic QUIC traffic
solely to inflate coverage

run stress traffic

browse unrelated destinations
```

If an Owner/TechLead-approved benign endpoint naturally negotiates QUIC, it may
be part of minimal normal-browser connectivity.

Exact approved endpoint, if any:

```text
OWNER / TECHLEAD PRECHECK REQUIRED
```

Final full V1 matrix must still contain at least one valid:

```text
quic_client
```

event because the merged validator requires all five source kinds somewhere.

If QUIC spans fewer than three OS families, use the already accepted:

```text
quic_sparse
```

coverage limitation as appropriate.

If zero valid QUIC exists:

```text
Gate E V1 coverage FAIL
```

Do not fake coverage.

---

# 35. Forbidden Collection Activity

Do NOT use:

```text
port scan

active fingerprinting

JS fingerprinting

canvas/audio/WebGL

service discovery

heavy unrelated browsing

traffic flood

synthetic traffic solely to inflate source counts

random visitor devices

unapproved employee devices
```

---

# 36. Full V1 Device / Sample Planner

Planner aliases below are operational aliases only.

They are NOT `lab_device_id`.

| DEVICE | CELL | SAMPLE | EPOCH | NETWORK STATE | RUNTIME CONTEXT | BROWSER | MAC MODE | EXPECTED PORTAL MODE | STATUS |
|---|---|---:|---|---|---|---|---|---|---|
| AS-01 | Android smartphone | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-01 | Android smartphone | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-01 | Android smartphone | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-01 | Android smartphone | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-02 | Android smartphone | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-02 | Android smartphone | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-02 | Android smartphone | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AS-02 | Android smartphone | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-01 | iOS smartphone | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-01 | iOS smartphone | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-01 | iOS smartphone | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-01 | iOS smartphone | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-02 | iOS smartphone | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-02 | iOS smartphone | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-02 | iOS smartphone | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IS-02 | iOS smartphone | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-01 | Android tablet | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-01 | Android tablet | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-01 | Android tablet | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-01 | Android tablet | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-02 | Android tablet | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-02 | Android tablet | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-02 | Android tablet | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| AT-02 | Android tablet | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-01 | iPadOS tablet | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-01 | iPadOS tablet | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-01 | iPadOS tablet | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-01 | iPadOS tablet | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-02 | iPadOS tablet | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-02 | iPadOS tablet | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-02 | iPadOS tablet | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| IT-02 | iPadOS tablet | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-01 | Windows laptop | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-01 | Windows laptop | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-01 | Windows laptop | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-01 | Windows laptop | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-02 | Windows laptop | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-02 | Windows laptop | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-02 | Windows laptop | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| WL-02 | Windows laptop | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-01 | macOS laptop | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-01 | macOS laptop | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-01 | macOS laptop | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-01 | macOS laptop | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-02 | macOS laptop | S1 | E1 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-02 | macOS laptop | S2 | E1 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-02 | macOS laptop | S3 | E2 | fresh_attach | `<captive_webview|captive_helper IF supported; else normal_browser>` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |
| ML-02 | macOS laptop | S4 | E2 | same_attachment_revisit | `normal_browser` | `<OWNER FILL>` | `<OWNER FILL>` | `<omada_external_portal|capport_login>` | `<PENDING/SEALED/INVALID>` |

Rules:

```text
E1 and E2 must become distinct network_epoch_id values.

S1/S3 are fresh-attach slots.

S2/S4 are same-attachment revisit slots.

If captive/helper context is supported:
at least one captive/helper and one normal-browser sample are required.

If context unsupported:
record context_supported_gt=false
and do not fabricate captive context.
```

Additional valid samples beyond four/device are allowed if needed to satisfy
source/context coverage.

They do not reduce the 12-device requirement.

---

# 37. Gate D — Full Campaign Start Conditions

Before first Gate D sample:

```text
PRE-COLLECTION ENVIRONMENT GATE = PASS

Gate C = PASS

all 12 inventory slots = AVAILABLE

all 12 devices = collection authorized

ground truth enrolled

staging/binding paths prepared

no merged tooling defect open
```

Any false condition:

```text
Gate D BLOCKED
```

---

# 38. Invalid Sample Reasons — Exact Handling

Canonical reasons:

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

Invalid samples NEVER count toward 48.

---

# 39. binding_uncertain

Immediate:

```text
sample INVALID
```

Recollect only after exact binding is manually re-established.

Campaign STOP when:

```text
same MAC/time window is ambiguously claimed
by different physical devices

or

binding-ledger mechanics are systematically unreliable
```

Return to TechLead.

---

# 40. context_changed

Examples:

```text
browser changed

runtime context changed

MAC changed

OS state changed

network attachment unexpectedly changed
```

Immediate:

```text
sample INVALID
```

Recollect with a new sample.

Systematic procedure ambiguity:

```text
STOP calibration/campaign
→ TechLead review
```

---

# 41. window_too_long

If:

```text
duration > 600 seconds
```

Immediate:

```text
sample INVALID
```

No clipping.

Recollect as a new bounded sample.

---

# 42. evidence_missing

Do NOT invalidate merely because one optional source is absent.

Use `evidence_missing` when:

```text
the sample exports zero usable normalized evidence
```

or a sample-specific controlled action that should have produced its intended
portal evidence is proven not to have been captured due to collection failure.

Recollect allowed.

If repeated across controlled devices:

```text
STOP
→ source/environment/tooling investigation by TechLead
```

---

# 43. ground_truth_unverified

If any required manual ground-truth field cannot be verified:

```text
sample/device NOT ADMITTED
```

STOP collection for that device until reverified.

Do not infer from fingerprints.

---

# 44. source_schema_error

Any canonical production payload revalidation failure:

```text
sample INVALID

campaign STOP

RETURN TO TECHLEAD
```

Do not transform/fix the evidence in collection tooling.

---

# 45. privacy_violation

Any raw/private forbidden data found in sealed candidate:

```text
sample/matrix INVALID

campaign STOP

quarantine affected lab artifact

RETURN TO TECHLEAD
```

Do not proceed to Task-04.

---

# 46. operator_abort

Manual stop for:

```text
unexpected device state

physical interruption

incorrect procedure

operator uncertainty
```

Sample INVALID.

Recollect allowed once conditions are controlled.

---

# 47. Invalid Audit Accounting

Invalid samples stay OUT of sealed `samples.jsonl`.

For full export, pass aggregate canonical counts using repeated:

```text
--invalid-reason reason=count
```

Only accepted reason enum keys are allowed.

Example shape:

```bash
--invalid-reason context_changed=2 --invalid-reason operator_abort=1
```

Do not add zero-value arguments unless chosen execution convention requires
them.

No free-text invalid reason enters manifest.

---

# 48. Gate D — Full Collection PASS

Minimum before Gate E:

```text
12 distinct authorized physical devices

6 mandatory cells

>=2 physical devices/cell

>=4 sealed valid samples/device

>=2 network epochs/device

>=48 sealed valid samples

context variation PASS where supported

all sample windows <=600s

all staging samples canonical

all bindings unambiguous
```

This is campaign completion, not classifier acceptance.

---

# 49. Gate E — Full Matrix Export Variables

Create a NEW final V1 matrix ID:

```bash
MATRIX_ID="$(python -c 'import uuid; print(uuid.uuid4())')"
```

Freeze execution variables:

```bash
REPO_ROOT="<ABS_REPO_ROOT>"
DB_PATH="<ABS_TASK01_DB_PATH>"
STAGING_DIR="<ABS_FULL_V1_STAGING_DIR>"
OUTPUT_DIR="<ABS_EMPTY_FULL_V1_OUTPUT_DIR>"
ENV_RECORD="<ABS_ENVIRONMENT_RECORD>"
```

`OUTPUT_DIR` must be:

```text
nonexistent
or
empty safe directory
```

before export.

---

# 50. Gate E — Step 1 Validate Staging

```bash
cd "$REPO_ROOT"

python -m research.device_fingerprint_03a.cli validate-staging   --staging-dir "$STAGING_DIR"
```

PASS:

```text
exit 0
```

and returned counts match the intended final campaign.

Anything else:

```text
STOP
```

---

# 51. Gate E — Step 2 Export Unsealed Matrix

Use exact merged CLI:

```bash
python -m research.device_fingerprint_03a.cli export   --db-path "$DB_PATH"   --staging-dir "$STAGING_DIR"   --output-dir "$OUTPUT_DIR"   --environment-record "$ENV_RECORD"   --matrix-id "$MATRIX_ID"   --repository-head "ea5f16594d9d7a04c8f629d5329f3ea041b36d4e"   --repository-tree "66f9292c7843c4c3610060a72a8768ec5041080f"   --collection-procedure-version "1.0.0"   --ground-truth-policy-version "1.0.0"   --task01-retention-days 30   <INVALID-REASON-ARGS>   <LIMITATION-ARGS>
```

Allowed coverage limitation args are only the frozen enum, for example when
factually true:

```bash
--limitation quic_sparse
```

Do not declare a limitation merely to bypass a real defect.

Export success creates an UNSEALED matrix.

---

# 52. Gate E — Step 3 Pre-Seal Manual Review

Before matrix seal, Owner + TechLead verify:

```text
device inventory matches staging

sample count matches

matrix_id recorded

repository identity exact

invalid counts exact

known limitations factual

no visitor data

no person identity
```

Then generate exact matrix-level:

```text
SEALED_AT
```

canonical UTC milliseconds.

---

# 53. Gate E — Step 4 Matrix Seal

Full V1 seal does NOT use `--calibration`:

```bash
python -m research.device_fingerprint_03a.cli seal   --matrix-dir "$OUTPUT_DIR"   --sealed-at "$SEALED_AT"   --owner-verified
```

Seal internally performs validation, writes the checksum authority and
revalidates.

If sealing fails:

```text
STOP
```

Do not manually create/edit `checksums.sha256`.

---

# 54. Gate E — Step 5 Validate

```bash
python -m research.device_fingerprint_03a.cli validate   --matrix-dir "$OUTPUT_DIR"
```

Required canonical result:

```text
status = pass
coverage.v1_coverage_pass = true
```

---

# 55. Gate E — Step 6 Summary / Coverage Report

```bash
python -m research.device_fingerprint_03a.cli summary   --matrix-dir "$OUTPUT_DIR"
```

Capture stdout as an execution artifact OUTSIDE the sealed matrix, e.g.:

```text
coverage-report.json
```

The merged summary contains deterministic:

```text
coverage

sample_source_summary
```

It is descriptive.

It is NOT a classifier table.

---

# 56. Gate E — Exact Validation PASS Conditions

All must pass:

```text
[ ] status = pass

[ ] v1_coverage_pass = true

[ ] device_count_pass = true

[ ] sealed_sample_count_pass = true

[ ] mandatory_cells_pass = true

[ ] minimum_repetition_pass = true

[ ] runtime_variation_pass = true

[ ] all_source_kinds_pass = true

[ ] per_device_core_sources_pass = true

[ ] quic_coverage_pass = true

[ ] 0 schema failures

[ ] 0 binding collisions

[ ] 0 duplicate evidence assignment

[ ] 0 out-of-window evidence rows

[ ] 0 privacy canaries

[ ] checksums PASS

[ ] matrix exact file set PASS

[ ] Task-01 DB before/after fingerprint unchanged
```

Any FAIL:

```text
Gate E FAIL
```

Do not edit a sealed matrix in place.

---

# 57. QUIC Gate E Clarification

Merged validator requires:

```text
all five source kinds have valid evidence somewhere
```

Therefore:

```text
quic_sparse
```

may satisfy sparse OS-family spread, but it does NOT allow:

```text
zero valid quic_client rows
```

If zero valid QUIC rows:

```text
Gate E FAIL
→ additional controlled 03A collection required
```

No synthetic coverage inflation.

---

# 58. Gate F — Manual Ground Truth Audit

Owner + TechLead must audit:

```text
[ ] 100% devices.jsonl rows

[ ] 100% device_states.jsonl rows

[ ] collection_authorized = true for every device

[ ] control_basis_gt valid

[ ] manufacturer verified

[ ] model verified

[ ] device_class_gt verified

[ ] OS family verified

[ ] OS version/major verified

[ ] ground_truth_state belongs to correct lab_device_id

[ ] at least one sample manually checked per physical device

[ ] sample/device linkage verified

[ ] private binding linkage reviewed

[ ] no visitor device included

[ ] no person identity stored

[ ] invalid_sample_count reviewed

[ ] invalid_sample_reason_counts reviewed

[ ] known coverage limitations reviewed
```

Classifier output does not exist and is not used for audit.

Gate F result:

```text
PASS / FAIL
```

---

# 59. Gate G — Admission Review Package

Architect + TechLead receive exactly:

```text
sealed matrix_id

matrix path / custody location

checksums.sha256 PASS record

validator PASS output

coverage-report.json

device coverage table

sealed sample count

per-device sample/epoch table

per-source presence

sample_source_summary

source missingness summary

quality-state distribution

QUIC coverage:
valid row presence
OS-family spread
quic_sparse limitation if used

runtime-context variation summary

invalid sample counts/reasons

known limitations

Gate C result

Gate D result

Gate E result

Gate F audit result
```

No classifier metric.

---

# 60. Gate G — Decision

PASS requires:

```text
Gate C = PASS

Gate D = PASS

Gate E = PASS

Gate F = PASS

sealed matrix accepted

coverage limitations explicitly understood
```

Then:

```text
TASK-DEVICE-FINGERPRINT-03A = PASS

TASK-04 architecture MAY START
```

FAIL:

```text
additional controlled 03A collection required

TASK-04 remains HOLD
```

No Task-04 implementation begins automatically.

---

# 61. Actual Artifacts Created Outside Git

Execution creates these operational artifacts outside Git:

```text
environment-authorization.json

device-inventory record

Gate C calibration staging

Gate C private binding ledger

Gate C sealed calibration matrix

Gate C result report

full V1 staging

full V1 private binding ledger

sealed V1 matrix

validation-report.json

coverage-report.json

Gate D result report

Gate E result report

Gate F audit report

Gate G admission report
```

Actual matrix/binding data MUST NOT be committed to Git.

---

# 62. Sealed Matrix Exact Files

Only:

```text
manifest.json

devices.jsonl

device_states.jsonl

samples.jsonl

evidence.jsonl

source_health.jsonl

checksums.sha256
```

Do NOT place Gate reports inside the sealed matrix directory.

Do NOT place binding ledger inside it.

---

# 63. Binding Ledger Retention

Maximum:

```text
30 days
```

Preferred:

```text
delete immediately after
successful matrix seal + verification
```

Owner + TechLead must record deletion/custody decision.

---

# 64. Sealed Matrix Retention

Frozen:

```text
180 days
```

Extension requires explicit Owner + TechLead review.

No automatic indefinite retention.

---

# 65. Role Split

## Owner

```text
physical device authorization

physical ground truth

manufacturer/model verification

OS verification

physical MAC-rotation confirmation

sample ground-truth acceptance

matrix --owner-verified authority

Gate F ground-truth audit

collection-environment authorization
```

## TechLead10

```text
PRE-COLLECTION ENVIRONMENT GATE control

source availability review

tooling/source-contract verification

Gate C/D/E/F technical acceptance

STOP/RETURN decisions on defects

candidate matrix acceptance
```

## Sysadmin

Only when required:

```text
execution-host preparation

effective Task-01 DB path proof

read-only DB/snapshot access

filesystem path/access preparation

free-space proof

data-transfer mechanics

production-host read authorization implementation
after Owner approval
```

## 03A Tooling

```text
validate staging

read/export normalized Task-01 evidence

read source-health point events

de-identify

build unsealed matrix

seal

checksum

validate

summary
```

It does NOT establish ground truth.

## Architect

```text
preserve 03A architecture contract

review Gate G admission package

decide whether evidence matrix is sufficient
for Task-04 architecture to begin
with TechLead
```

## Coder

```text
NOT NEEDED for collection execution
```

If merged tooling defect is found:

```text
STOP
RETURN TO TECHLEAD
```

No ad hoc fix from runbook execution.

---

# 66. Tooling Defect Stop Conditions

STOP and return to TechLead if any:

```text
merged CLI command missing/broken

exporter writes Task-01 DB

read-only boundary fails

canonical schema validator rejects valid production source unexpectedly

MAC/IP appears in sealed evidence

raw private field appears

staging relationship validator defect

checksum/seal defect

coverage validator contradicts accepted 03A FINAL

research tooling requires app/** modification
```

Do not redesign 03A in execution.

---

# 67. Environment / Source Defect Stop Conditions

STOP before or during collection when:

```text
Task-01 DB path/access unresolved

source provenance mismatch

required Task-02 source unavailable/unsupported

portal_headers source unavailable

source-health read boundary unavailable

Site/SSID mismatch

binding ledger ambiguous

unauthorized device detected

production host used without explicit authorization
```

QUIC sparsity alone is not immediate STOP when retained/source capability is
proven, but final V1 still needs at least one valid QUIC row.

---

# 68. No New Development

This runbook authorizes NONE of:

```text
new Python code

classifier

Task-04

production schema change

Task-01/02/03 config change

new service

deploy

activation
```

Tooling is already merged.

---

# 69. No Collection Before Gate PASS

Permanent:

```text
NO DATA COLLECTION
UNTIL
PRE-COLLECTION ENVIRONMENT GATE = PASS
```

Synthetic unit-test fixtures already in Git are not physical collection.

---

# 70. Current Execution Status

```text
TASK =
TASK-DEVICE-FINGERPRINT-03A-COLLECTION-EXECUTION-DRAFT

03A TOOLING =
MERGED

03A COLLECTION =
PENDING

CURRENT NEXT GATE =
PRE-COLLECTION ENVIRONMENT GATE

TASK-04 =
HOLD

CODER =
HOLD

NO NEW DEVELOPMENT

NO DEPLOY

NO PRODUCTION ACTIVATION

NO COLLECTION UNTIL ENVIRONMENT GATE PASS
```

---

# 71. Immediate Next Action After TechLead Review

After this execution DRAFT receives TechLead PASS:

```text
Owner + TechLead + Sysadmin where required

fill environment-authorization/precheck record

resolve every OWNER / SYSADMIN PRECHECK REQUIRED field

execute read-only repository/DB/source checks

record source availability

freeze paths/access/data-transfer mechanics

issue:

PRE-COLLECTION ENVIRONMENT GATE =
PASS
or
BLOCKED
```

Only PASS unlocks Gate C physical calibration.

**End of TASK-DEVICE-FINGERPRINT-03A-COLLECTION-EXECUTION-DRAFT.**
