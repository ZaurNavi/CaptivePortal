# TASK-DEVICE-FINGERPRINT-05-PERF-01 — LOCAL REVIEW HANDOFF

```text
TASK=TASK-DEVICE-FINGERPRINT-05-PERF-01
BASE_HEAD=97bd1cf924024a38cc3229bfd726a25fe6754b07
BASE_TREE=545a48caf86adc247083db611e87a8d36820f353
BRANCH=fix/device-fingerprint-05-perf01-request-validation
CANDIDATE_HEAD=0507a1fd66e84d00f105a53e6c36dec74ea14520
CANDIDATE_TREE=439ab64697f2fcdcd5e822527f287ca5404e45ba
CHANGED_FILES=12 (6 authorized production files + 6 authorized test files)
```

## IMPLEMENTATION_SUMMARY

- Exact KnowledgeBundle closure is fully validated once per RequestAssembly.
- Private frozen/slots proof binds the exact in-memory bundle/candidate pair using object identity, and is reused only by the request's OriginAssessment and Fusion paths.
- Public/direct KnowledgeBundle, OriginAssessment, Fusion and K1/K4 matcher entry points remain fail-closed.
- Private K1/K4 matching preserves the existing algorithms, including 36/28/24-bit precedence; no whole-record-set revalidation occurs in the validated matching path.
- All other OriginAssessment/Fusion schema, canonical and lineage checks remain. No schema, artifact identity rule, integration/persistence, lease/retry, worker, configuration or deployment change.
- Two repeated requests on the same service independently create proofs and each execute exactly one full validation. Proof is absent from compatibility-hook arguments, RequestAssemblyResult and semantic output artifacts.
- Existing incompatible/degraded K1 tests now intercept the actual private matcher, preserving their no-matching assertions.

## BASELINE_SEMANTIC_IDS

Captured before production source changes on the exact required base using the existing fixed fixture clock. OriginAssessment entries are ordered by origin_group.

```json
{
  "A_no_evidence": {
    "ClassificationRequestManifest": "ClassificationRequestManifest:v1:sha256:11cddc6cc4a59a284102d05624923cd6d29bd37399257e2f3bc8a8779b8bff93",
    "OriginAssessments": {
      "dhcp": "OriginAssessment:v1:sha256:86e15793c6f0bd4a8f9d184380804636f4ebb87bc545e95e7baa2a6d660e52d3",
      "mac_registry": "OriginAssessment:v1:sha256:ebecdce07f8997b9b7508ae427b6c74493f4cee86bf21956e80ac8d7b86ca3e5",
      "portal": "OriginAssessment:v1:sha256:4ad88b312d57df263a79f9d72d62acdb15f58942db7e2a592225d0a554c16e98",
      "quic": "OriginAssessment:v1:sha256:058f57e4ef5b0323119d28c09bd77f3f7ee44865b9a78429b92a72b749c3c75c",
      "tcp": "OriginAssessment:v1:sha256:d6b4217ef4878f8943f40cc841d4afa0506119374dfd75e390ca24926c59050a",
      "tls": "OriginAssessment:v1:sha256:a0f5b388f7360bd93001696a195e58435af33016a0fc140e72546ade153cfd4d"
    },
    "ClassificationResult": "ClassificationResult:v1:sha256:f2250e57ea2cf270c335d2acf4041be465aaedf5416f934be0d13ff7f720b5cb"
  },
  "B_dhcp": {
    "ClassificationRequestManifest": "ClassificationRequestManifest:v1:sha256:33a7b48dab2b796a0c6b47fabe11964cef3f3ac49b166639d1c6c0823a5b2667",
    "OriginAssessments": {
      "dhcp": "OriginAssessment:v1:sha256:1390bd7a0c43844eeb8c5e3209c782c1125ae569977567f305a3ba194fb15f2d",
      "mac_registry": "OriginAssessment:v1:sha256:0e4f8b2c64efabda9f449efb7f580f8444a27452c6f156d23338eefe977da687",
      "portal": "OriginAssessment:v1:sha256:d10c4aa382df2319bfb68dc660597d54f06a7fa0b7240c5690a0d062584a6480",
      "quic": "OriginAssessment:v1:sha256:4accc3c443b627ba228540ec059ba12c3bfde7795faceec942badef7e52e2041",
      "tcp": "OriginAssessment:v1:sha256:ccdd612e62744fa66f4fd20cdf93e61b46393c49e9c38fea514821d5c9ac7f11",
      "tls": "OriginAssessment:v1:sha256:16969f498a089885728c131e57af5688e5a6331f368a4eeb0d9ef7efcce65c36"
    },
    "ClassificationResult": "ClassificationResult:v1:sha256:2678b1d02b68515660f1bc89c5145bc8513260f3be668b8a5ae4fd2e654ac942"
  }
}
```

## POST_PATCH_SEMANTIC_IDS

Rebuilt after the repair with the same fixtures and fixed clock; regression assertions pin all 16 exact baseline IDs.

```json
{
  "A_no_evidence": {
    "ClassificationRequestManifest": "ClassificationRequestManifest:v1:sha256:11cddc6cc4a59a284102d05624923cd6d29bd37399257e2f3bc8a8779b8bff93",
    "OriginAssessments": {
      "dhcp": "OriginAssessment:v1:sha256:86e15793c6f0bd4a8f9d184380804636f4ebb87bc545e95e7baa2a6d660e52d3",
      "mac_registry": "OriginAssessment:v1:sha256:ebecdce07f8997b9b7508ae427b6c74493f4cee86bf21956e80ac8d7b86ca3e5",
      "portal": "OriginAssessment:v1:sha256:4ad88b312d57df263a79f9d72d62acdb15f58942db7e2a592225d0a554c16e98",
      "quic": "OriginAssessment:v1:sha256:058f57e4ef5b0323119d28c09bd77f3f7ee44865b9a78429b92a72b749c3c75c",
      "tcp": "OriginAssessment:v1:sha256:d6b4217ef4878f8943f40cc841d4afa0506119374dfd75e390ca24926c59050a",
      "tls": "OriginAssessment:v1:sha256:a0f5b388f7360bd93001696a195e58435af33016a0fc140e72546ade153cfd4d"
    },
    "ClassificationResult": "ClassificationResult:v1:sha256:f2250e57ea2cf270c335d2acf4041be465aaedf5416f934be0d13ff7f720b5cb"
  },
  "B_dhcp": {
    "ClassificationRequestManifest": "ClassificationRequestManifest:v1:sha256:33a7b48dab2b796a0c6b47fabe11964cef3f3ac49b166639d1c6c0823a5b2667",
    "OriginAssessments": {
      "dhcp": "OriginAssessment:v1:sha256:1390bd7a0c43844eeb8c5e3209c782c1125ae569977567f305a3ba194fb15f2d",
      "mac_registry": "OriginAssessment:v1:sha256:0e4f8b2c64efabda9f449efb7f580f8444a27452c6f156d23338eefe977da687",
      "portal": "OriginAssessment:v1:sha256:d10c4aa382df2319bfb68dc660597d54f06a7fa0b7240c5690a0d062584a6480",
      "quic": "OriginAssessment:v1:sha256:4accc3c443b627ba228540ec059ba12c3bfde7795faceec942badef7e52e2041",
      "tcp": "OriginAssessment:v1:sha256:ccdd612e62744fa66f4fd20cdf93e61b46393c49e9c38fea514821d5c9ac7f11",
      "tls": "OriginAssessment:v1:sha256:16969f498a089885728c131e57af5688e5a6331f368a4eeb0d9ef7efcce65c36"
    },
    "ClassificationResult": "ClassificationResult:v1:sha256:2678b1d02b68515660f1bc89c5145bc8513260f3be668b8a5ae4fd2e654ac942"
  }
}
```

```text
SEMANTIC_IDENTITY_MATCH=PASS (16/16)
FULL_KNOWLEDGE_VALIDATION_COUNT_PER_REQUEST=1
PUBLIC_K1_MATCHER_USED_BY_VALIDATED_REQUEST_PATH=NO
PUBLIC_K4_MATCHER_USED_BY_VALIDATED_REQUEST_PATH=NO
```

## FOCUSED_TEST_COMMAND

Working directory: C:\CaptivPortal-Lab\coder-task05-identity-session.
Runtime: C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe.
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\task05-perf01-pyc.

```text
python -m pytest -q
  tests/device_fingerprint_fe1/test_knowledge_artifacts.py
  tests/device_fingerprint_fe4/test_k4_ieee_import.py
  tests/device_fingerprint_fe7/test_knowledge_bundle.py
  tests/device_fingerprint_task04_t03/test_origin_assessment.py
  tests/device_fingerprint_task04_t04/test_fusion.py
  tests/device_fingerprint_task04_04d_request/test_request_assembly.py
  --basetemp=C:\CaptivPortal-Lab\tmp\task05-perf01-focused-20261004-02
  --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-PERF-01-focused-final.xml
```

```text
FOCUSED_TEST_RESULT=233 passed / 0 failed / 0 skipped (45.99s)
```

Initial focused run: 231 passed / 2 failed in newly added K1 tests because the fixture ArtifactContent was treated as a dict. Corrected only the test preparation to read semantic_payload; the complete authorized six-file rerun above is green.

## PY_COMPILE_RESULT

```text
python -m py_compile
  app/device_fingerprint/knowledge_bundle.py
  app/device_fingerprint/knowledge_artifacts.py
  app/device_fingerprint/k4_ieee_import.py
  app/device_fingerprint/origin_assessment.py
  app/device_fingerprint/fusion.py
  app/device_fingerprint/request_assembly.py

PY_COMPILE_RESULT=PASS
DIFF_CHECK_RESULT=PASS
WORKTREE_STATUS=CLEAN
git status --short=<empty>
```

## git diff --name-status BASE...HEAD

```text
M	app/device_fingerprint/fusion.py
M	app/device_fingerprint/k4_ieee_import.py
M	app/device_fingerprint/knowledge_artifacts.py
M	app/device_fingerprint/knowledge_bundle.py
M	app/device_fingerprint/origin_assessment.py
M	app/device_fingerprint/request_assembly.py
M	tests/device_fingerprint_fe1/test_knowledge_artifacts.py
M	tests/device_fingerprint_fe4/test_k4_ieee_import.py
M	tests/device_fingerprint_fe7/test_knowledge_bundle.py
M	tests/device_fingerprint_task04_04d_request/test_request_assembly.py
M	tests/device_fingerprint_task04_t03/test_origin_assessment.py
M	tests/device_fingerprint_task04_t04/test_fusion.py
```

## git diff --stat BASE...HEAD

```text
 app/device_fingerprint/fusion.py                   | 40 +++++++--
 app/device_fingerprint/k4_ieee_import.py           |  8 ++
 app/device_fingerprint/knowledge_artifacts.py      |  9 +++
 app/device_fingerprint/knowledge_bundle.py         | 24 ++++++
 app/device_fingerprint/origin_assessment.py        | 71 ++++++++++++----
 app/device_fingerprint/request_assembly.py         | 26 +++---
 .../test_knowledge_artifacts.py                    | 19 ++++-
 .../device_fingerprint_fe4/test_k4_ieee_import.py  | 15 +++-
 .../test_knowledge_bundle.py                       | 29 +++++++
 .../test_request_assembly.py                       | 94 ++++++++++++++++++++++
 .../test_origin_assessment.py                      | 43 +++++++++-
 tests/device_fingerprint_task04_t04/test_fusion.py | 27 +++++++
 12 files changed, 372 insertions(+), 33 deletions(-)
```

## Exact BASE-to-IMPLEMENTATION patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-PERF-01_BASE-to-IMPLEMENTATION.patch
PATCH_BYTES=40946
PATCH_SHA256=ab77782b7f2a123e39fb169004e6f6333e4dad4b523f1210369d540fd5da373b
PATCH_FORMAT=git diff --binary --full-index
REVERSE_APPLY_CHECK=PASS (git apply --reverse --check; no application performed)
```

The capture script, test results, patch and this handoff remain outside Git.

```text
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
FULL_TESTS_RUN=NO
CENTRAL_LAB_RUN=NO
PRODUCTION_ACTIONS=NO
PRODUCTION_BENCHMARK_RUN=NO
CANDIDATE_STATUS=READY_FOR_TECH_LEAD_REVIEW
```

No production performance improvement is claimed; broader Lab gates and production benchmarking belong to Tech Lead.
