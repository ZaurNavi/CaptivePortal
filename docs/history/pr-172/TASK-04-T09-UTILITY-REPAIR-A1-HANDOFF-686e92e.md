# TASK-04 / T-09 — UTILITY REPAIR A1

IMPLEMENTATION_STATUS=LOCAL_COMMIT_READY_FOR_SOURCE_REVIEW
REAL_ARTIFACT_MATERIALIZATION=PARTIAL_PENDING_AUTHORITATIVE_INPUTS

## Repository identity

```ini
BRANCH=fix/task04-t09-utility-repair-a1
WORKTREE=C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1
COMMIT_SHA=686e92e0d0d1cda92f736dd70fd0db2b44dac90b
PARENT_SHA=74f7c7add401e5fec0469d49770466c2747c03cf
TREE_SHA=734ada42c57a8ec6e80ab91b9b595971b072bdaf
CHANGED_FILES=8
NEW_FILES=1
INSERTIONS=182
DELETIONS=12
WORKTREE_CLEAN=YES
```

The historical checkout `C:\CaptivPortal-UI-Preview` remains clean at commit
`74f7c7add401e5fec0469d49770466c2747c03cf`, tree
`7e93a4863909c3e807a9d8239924d13e0a0d7f71`.

## Exact supplied source

```ini
SOURCE_INPUT_PATH=C:\CaptivPortal-Lab\inputs\task04\utility-repair-a1\satori-1c2f888238ca1e8ebb397b5cf87b240f91711a65\dhcp.xml
SOURCE_INPUT_BYTES=458578
SOURCE_INPUT_SHA256=4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14
SOURCE_GIT_BLOB_SHA1=a82926690c28d2147534f24bdbdbeb0d1a2970fb
SOURCE_UPSTREAM_COMMIT=1c2f888238ca1e8ebb397b5cf87b240f91711a65
SOURCE_UPSTREAM_PATH=fingerprints/dhcp.xml
OLD_K1_SOURCE_IDENTITY=xnih/satori@c5dfcfbff31620e35248aa86da0c67f2ad4982f5:fingerprints/dhcp.xml
NEW_K1_SOURCE_IDENTITY=xnih/satori@1c2f888238ca1e8ebb397b5cf87b240f91711a65:fingerprints/dhcp.xml
SOURCE_BYTES_CHANGED=NO
UPSTREAM_BINDING_CHANGED=YES
```

The supplied bytes, Git blob and SHA256 exactly match the historical XML.
No claim that these are changed XML bytes or that this proves a fresh retrieval
is made. The supplied upstream commit is Owner/TechLead authority, not a claim
of independently downloaded/verified upstream history.

The following audit was recomputed from this exact local file before the
repair and again through the repaired pinned importer:

```ini
K1_IMPORT_AUDIT_SUMMARY=RECOMPUTED
fingerprints_total=481
source_tests_total=2787
source_tests_accepted=903
source_tests_rejected=1884
canonical_records_unique=903
predicate_groups_total=448
ambiguous_predicate_groups=164
records_in_ambiguous_groups=619
```

## Bounded implementation

- K3 strong is admitted only for a declared canonical platform outcome whose
  conjunctive normalized predicates explicitly bind the same platform value,
  `platform_source=sec_ch_ua_platform`, and CH presence. UA and tablet rules
  remain supporting. The 13 rules and 21 retained vectors remain concrete;
  mobile/runtime inputs remain no-class vectors. No raw parsing added.
- K1 pins the supplied commit/path/bytes. Only explicit admitted device-class
  mappings gain strong base authority. Platform authority remains supporting;
  unmapped labels and manufacturer/model no-claim semantics remain unchanged.
  Predicate matching, ambiguity, source weights, and DHCP admission are unchanged.
- Satori provenance metadata uses the same source constants as the importer.
  The caller must still supply the genuine `retrieved_at_utc`. Freshness limits
  and fresh/stale/expired caps are unchanged.
- New builder
  `build_utility_repair_a1_evidence_adapter_contract_set_v1(registry)` changes
  only three ceilings: dhcp/1 and portal_headers/1,2. The historical
  `build_initial_evidence_adapter_contract_set_v1` remains byte-identical.
- The existing generic ClassificationPolicy builder produces a new identity
  with only the EACS reference changed. No fusion/support/status rules changed.
- Existing generic KnowledgeBundle construction supports replacement K1/K3
  artifacts with exact supplied unchanged K2B/K4 dependencies; its schema and
  code were not modified.
- The historical initial F-F1 test fixture now explicitly reconstructs its
  supporting-only K3 artifact; its historical ID was checked without executing
  that gate. No F-F1 production gate code was changed.

## Materialized candidate identities (not formal gate admissions)

```ini
NEW_K1_GOVERNANCE_ID=SourceGovernanceRecord:v1:sha256:65e3dfbac4b6de78a08584ae2392212fb438be3b9205d0c66863c2e88376b693
K3_RULE_SET_ID=K3PortalRuleSet:v1:sha256:93ea1f384efe7d1dbbc9c513d09d9e62bdddd9448c0ee070423bc4f54176ed1a
K3_PROVENANCE_ID=KnowledgeProvenanceManifest:v1:sha256:2998126f045d69bcc8d0352113b69aff1b0698f899f33d9dfa81a58b88fe497d
EVIDENCE_ADAPTER_CONTRACT_SET_ID=EvidenceAdapterContractSet:v1:sha256:c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f
CLASSIFICATION_POLICY_ID=ClassificationPolicy:v1:sha256:5d6c6edab7cfb88bcb42d4badf9bd53dc78f458eae12b4e8b05878fb7f3256c8
NEW_K1_PROVENANCE_ID=PENDING_CONFIRMED_RETRIEVED_AT_UTC
NEW_K1_CANONICAL_RECORD_SET_ID=PENDING_REAL_K1_PROVENANCE_REF
KNOWLEDGE_BUNDLE_ID=PENDING_REAL_K1_AND_UNCHANGED_K2B_K4_DEPENDENCIES
```

K3 provenance binds the actual new commit/tree above and the unchanged
ClassificationTaxonomy. The K1 audit self-check used an explicitly synthetic
provenance reference only to check importer structure/counts. That resulting
record-set identity is deliberately NOT reported as a real candidate artifact.
No retrieval timestamp, Owner decision or prerequisite gate identity was fabricated.

## Items requiring TechLead direction

1. For final real K1 provenance and record-set materialization, supply the
   authoritative `retrieved_at_utc` for the exact supplied source. Neither local
   file timestamps nor today's date are substituted for source retrieval.
2. For the real new KnowledgeBundle ID, supply the exact unchanged accepted
   K2B/K4 record sets, provenance, governance and freshness dependencies (or an
   explicitly authorized exact local input bundle). No old-file archaeology,
   source download, production/Foundation DB access or corpus reconstruction
   was performed to invent these inputs.
3. Existing `ff1_evidence_adapter_contracts.py` still requires the historical
   K3 identity/supporting-only K1/K3 and initial EACS matrix. Existing
   `ff2_classification_policy.py` still pins the historical EACS identity.
   The new A1 artifacts cannot satisfy those historical initial-admission
   anchors unchanged. This was established by source inspection only, not a
   gate execution. These gate modules were left unchanged; an authoritative
   new-candidate admission/revalidation direction is needed before formal
   TechLead gates. No generic validation or historical gate was weakened.

## Checks actually executed

No pytest, regression suite, formal Foundation gate or T-09 was run.

Permitted narrow implementation self-check: direct local Python calls to the
modified importer/builders/validator, with assertions for the recomputed audit,
all imported canonical strength assignments, K3 double-build/SET permutation,
five invalid strong-rule rejections, exact three-ceiling EACS delta, preserved
historical EACS/K3 identities, unchanged Satori freshness policy, and
ClassificationPolicy reference-only delta. Result: PASS. This is not an
official acceptance result, nor a pytest passed/skipped/failed count.

Interpreter: `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`.

Syntax-only compile command (PASS, cache outside repository):

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\utility-repair-a1-pyc'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m compileall -q app/device_fingerprint/evidence_adapter_contracts.py app/device_fingerprint/fe5_external_knowledge.py app/device_fingerprint/k1_satori_import.py app/device_fingerprint/k3_portal_rules.py tests/device_fingerprint_fe1/test_satori_import.py tests/device_fingerprint_fe3/test_k3_portal_rules.py tests/device_fingerprint_ff1/test_evidence_adapter_contracts.py tests/device_fingerprint_ff1/test_utility_repair_a1_contracts.py
```

`git diff --check` and committed BASE-to-HEAD diff check: PASS.
Prepared modified/new pytest files were not executed.

## Exact complete source files

These links provide complete files, not snippets or diffs:

- [evidence_adapter_contracts.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/evidence_adapter_contracts.py)
- [fe5_external_knowledge.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/fe5_external_knowledge.py)
- [k1_satori_import.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/k1_satori_import.py)
- [k3_portal_rules.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/app/device_fingerprint/k3_portal_rules.py)
- [test_satori_import.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_fe1/test_satori_import.py)
- [test_k3_portal_rules.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_fe3/test_k3_portal_rules.py)
- [test_evidence_adapter_contracts.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_ff1/test_evidence_adapter_contracts.py)
- [test_utility_repair_a1_contracts.py](C:/CaptivPortal-Lab/coder-task04-t09-utility-repair-a1/tests/device_fingerprint_ff1/test_utility_repair_a1_contracts.py)

## Exact BASE-to-implementation patch

[TASK-04-T09-UTILITY-REPAIR-A1_BASE-to-A1-686e92e.patch](C:/CaptivPortal-Lab/artifacts/TASK-04-T09-UTILITY-REPAIR-A1_BASE-to-A1-686e92e.patch)

```ini
PATCH_BYTES=18932
PATCH_SHA256=44ce2e69b84df269651f3cb0676347680607494345fbe86653008994fa1365b6
PATCH_FORMAT=git diff --binary --full-index
PATCH_BASE=74f7c7add401e5fec0469d49770466c2747c03cf
PATCH_HEAD=686e92e0d0d1cda92f736dd70fd0db2b44dac90b
```

Exact `git diff --name-status BASE HEAD`:

```text
M app/device_fingerprint/evidence_adapter_contracts.py
M app/device_fingerprint/fe5_external_knowledge.py
M app/device_fingerprint/k1_satori_import.py
M app/device_fingerprint/k3_portal_rules.py
M tests/device_fingerprint_fe1/test_satori_import.py
M tests/device_fingerprint_fe3/test_k3_portal_rules.py
M tests/device_fingerprint_ff1/test_evidence_adapter_contracts.py
A tests/device_fingerprint_ff1/test_utility_repair_a1_contracts.py
```

Diff stat:

```text
app/device_fingerprint/evidence_adapter_contracts.py              | 14 +++++
app/device_fingerprint/fe5_external_knowledge.py                   |  7 ++-
app/device_fingerprint/k1_satori_import.py                         |  9 ++-
app/device_fingerprint/k3_portal_rules.py                          | 17 +++++-
tests/device_fingerprint_fe1/test_satori_import.py                 | 31 ++++++++++
tests/device_fingerprint_fe3/test_k3_portal_rules.py                | 38 +++++++++++-
tests/device_fingerprint_ff1/test_evidence_adapter_contracts.py    |  9 ++-
tests/device_fingerprint_ff1/test_utility_repair_a1_contracts.py    | 69 ++++++++++++++++++++++
8 files changed, 182 insertions(+), 12 deletions(-)
```

`git status --short`: empty, both the new worktree and historical checkout.

## Boundaries

```ini
PRODUCTION_CODE_CHANGE=YES — bounded TASK-04 implementation repair only
FOUNDATION_RUNTIME_PROFILE_CHANGE=NO
PRODUCT_VALIDATION_POLICY_CHANGE=NO
R14_CHANGE=NO
GROUND_TRUTH_CHANGE=NO
LEGACY_TCP_FUSION_CHANGE=NO
JA4_SEMANTIC_CHANGE=NO
RAW_SATORI_XML_IN_GIT=NO
GENERATED_K1_CORPUS_IN_GIT=NO
RETRIEVAL_TIMESTAMP_FABRICATED=NO
FORMAL_GATES_RUN=NO
FULL_OR_REGRESSION_SUITE_RUN=NO
PRODUCTION_ACTION=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
```

HOLD for TechLead source review and the explicitly identified artifact/admission inputs.
