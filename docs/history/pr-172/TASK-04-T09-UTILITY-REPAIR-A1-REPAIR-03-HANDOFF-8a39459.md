# TASK-04 / T-09 — UTILITY REPAIR A1 REPAIR-03

Implementation-only candidate for TechLead source review. One new follow-up commit; previous commits were not amended. No formal gate or real knowledge materialization was executed.

```ini
BASE_COMMIT=2ec36ce5a42060588320e126bdf4df4f80983de2
BASE_TREE=ee456a00b33de12995940cb352f449f460228d16
BRANCH=fix/task04-t09-utility-repair-a1
NEW_COMMIT_SHA=8a39459be3ce7ed40e325736034245f0025cf249
NEW_TREE_SHA=e2521f27c9f91978e381bce202ab3e3c83aa6dad
CHANGED_FILES=6
NEW_FILES=0
ADDITIONS=166
DELETIONS=7

SATORI_SOURCE_COMMIT=c5dfcfbff31620e35248aa86da0c67f2ad4982f5
SATORI_SOURCE_PATH=fingerprints/dhcp.xml
SATORI_SOURCE_BLOB_SHA1=a82926690c28d2147534f24bdbdbeb0d1a2970fb
SATORI_SOURCE_SHA256=4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14
SATORI_IMPORTER_VERSION=2
SOURCE_BYTES_CHANGED=NO

A1_FF1_REQUIRES_STRONG_DEVICE_CLASS=YES
A1_FF1_REQUIRES_STRONG_SMARTPHONE_CAPABILITY=YES
A1_FF1_REJECTS_SUPPORTING_ONLY_K1=YES
HISTORICAL_FF1_CHANGED_SEMANTICS=NO
HISTORICAL_FF2_CHANGED_SEMANTICS=NO

NARROW_VALIDATOR_SELF_CHECK=PASS
NEGATIVE_K1_STRUCTURES_CHECKED=11
AMBIGUOUS_STRONG_RECORDS_PRESERVED=YES
SOURCE_SPECIFIC_PROVENANCE_VERSION_CHECK=PASS
SOURCE_BLOB_AND_AUDIT_ANCHORS_UNCHANGED=YES
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
WORKTREE_CLEAN=YES

FORMAL_ENTRYPOINT_CALLS=0
PYTEST_RUN=NO
FORMAL_GATES_RUN=NO
FULL_REGRESSION_RUN=NO
CENTRAL_LAB_RUN=NO
REAL_K1_ARTIFACTS_MATERIALIZED=NO
PRODUCTION_ACTION=NO
PUSH=NO
PR=NO
MERGE=NO
```

## Repairs

- Restores the TechLead-supplied current upstream commit binding. Hashing the retained XML confirms the same source SHA256 and Git blob SHA-1; source bytes and numerical audit anchors are unchanged. No network retrieval or freshness claim was made.
- Adds source-specific Satori importer version `2`. Both external provenance construction and F-E5 exact provenance validation use it. K2B and K4 remain version `1`.
- A1 F-F1 now requires every represented admitted canonical device-class claim to be strong and requires at least one canonical strong smartphone capability. Existing manufacturer/model NO_CLAIM, platform ceiling and invalid-strong checks remain. Ambiguous groups are neither selected nor collapsed.

Historical F-F1 functions and anchors were compared with the parent AST and remain unchanged. The entire F-F2 file is byte-identical to the parent, including its A1 entrypoint. Other production files are outside the delta.

## Exact name-status and stat

```text
M app/device_fingerprint/fe5_external_knowledge.py
M app/device_fingerprint/ff1_evidence_adapter_contracts.py
M app/device_fingerprint/k1_satori_import.py
M tests/device_fingerprint_fe1/test_satori_import.py
M tests/device_fingerprint_fe5/test_fe5_external_knowledge.py
M tests/device_fingerprint_ff1/test_a1_admission.py

app/device_fingerprint/fe5_external_knowledge.py          | 13
app/device_fingerprint/ff1_evidence_adapter_contracts.py  | 9
app/device_fingerprint/k1_satori_import.py                | 6
tests/device_fingerprint_fe1/test_satori_import.py        | 14
tests/device_fingerprint_fe5/test_fe5_external_knowledge.py | 50
tests/device_fingerprint_ff1/test_a1_admission.py          | 81
6 files changed, 166 insertions(+), 7 deletions(-)

git status --porcelain: <empty>
```

## Verification boundary

Allowed narrow self-checks exercised private A1 validation helpers and generic schemas with synthetic inputs, the actual F-E5 provenance rejection expression without calling its gate, source-specific synthetic provenance construction, unchanged historical AST and XML hashes. Eleven negative K1 structures were checked. An initial self-check expected a private-helper reason for a manufacturer/model claim already rejected earlier by the generic dependency validator; the check was corrected to distinguish validation layers. No implementation weakening was required.

Syntax check used `C:/CaptivPortal-UI-Preview/.venv/Scripts/python.exe`, with `PYTHONPYCACHEPREFIX=C:/CaptivPortal-Lab/tmp/utility-repair-a1-repair03-pyc`:

```text
python -m compileall -q
  app/device_fingerprint/k1_satori_import.py
  app/device_fingerprint/fe5_external_knowledge.py
  app/device_fingerprint/ff1_evidence_adapter_contracts.py
  tests/device_fingerprint_fe1/test_satori_import.py
  tests/device_fingerprint_fe5/test_fe5_external_knowledge.py
  tests/device_fingerprint_ff1/test_a1_admission.py
```

Test source is prepared, NOT executed: current/wrong Satori version, unchanged source byte identities, supporting-only K1 rejection, missing strong smartphone rejection, every direct class requiring strong authority, valid NO_CLAIM/UNMAPPED with no promotion, preserved ambiguous strong classes, and existing invalid platform/manufacturer/model authority cases. No pytest pass count is claimed. Formal acceptance remains pending TechLead/Owner.

## Exact BASE-to-HEAD patch

[TASK-04-T09-UTILITY-REPAIR-A1-REPAIR-03_BASE-to-HEAD.patch](C:/CaptivPortal-Lab/artifacts/TASK-04-T09-UTILITY-REPAIR-A1-REPAIR-03_BASE-to-HEAD.patch)

```ini
PATCH_BYTES=17489
PATCH_SHA256=f71573df23fc63efa73ea1d8168f69440ecdb62e1355583889156be216274784
```

Binary-capable, full-index delta from exact BASE to new commit. Reverse-apply check passed without applying changes.

## Complete source delivery

- [k1_satori_import.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/k1_satori_import.py)
- [fe5_external_knowledge.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/fe5_external_knowledge.py)
- [ff1_evidence_adapter_contracts.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/ff1_evidence_adapter_contracts.py)
- [test_satori_import.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_fe1/test_satori_import.py)
- [test_fe5_external_knowledge.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_fe5/test_fe5_external_knowledge.py)
- [test_a1_admission.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_ff1/test_a1_admission.py)

Immutable archive exported directly from the new commit, containing exactly those six complete files, not raw XML or a generated corpus:

[TASK-04-T09-UTILITY-REPAIR-A1-REPAIR-03-source-8a39459.zip](C:/CaptivPortal-Lab/artifacts/TASK-04-T09-UTILITY-REPAIR-A1-REPAIR-03-source-8a39459.zip)

```ini
SOURCE_ZIP_BYTES=23346
SOURCE_ZIP_SHA256=0fc8cda4295febab24cdfb1a7acc3a291d3dd2acd042f7218958d34420bee194
```

No real retrieval timestamp, Owner decision, real K1 provenance/record set/KnowledgeBundle or formal manifest ID was fabricated. No Foundation/profile, GroundTruth or historical T-09 evidence change. Stop for TechLead review; subsequent real retrieval/provenance materialization belongs to TechLead.
