# TECHLEAD22 — TASK-DTI-NI-04-UNIFIED55
## BOUNDED CONTRACT CLARIFICATION 01 — Service Category Cardinality

**Date:** 2026-10-12 (Asia/Baku)  
**Repository baseline:** `main@22cdde5d4168de02d142c840028a4d66167e47f7`  
**TREE:** `a783d1cb3b2f33107ba64878ae5d3d8b80463f38`  
**Worktree:** `C:\CaptivPortal-Lab\coder-dti-ni-04-unified55`  
**Status:** `CONTRACT INTERPRETATION PASS / CODER UNBLOCKED FOR THIS QUESTION`  
**Authority:** bounded Tech Lead interpretation of existing `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md` and normative `v1-R1`; no architecture redesign.

## 1. Decision

The phrase `service categories = 10 exact IDs` in architecture v1 §69 denotes the **closed permitted V1 category vocabulary**, **not** an obligation to serialize exactly 10 `ServiceCategoryTaxonV1` records inside each concrete `RecognitionTaxonomyContractV1`.

For a concrete valid production knowledge bundle containing at least one admitted Service:

```text
1 <= len(taxonomy.service_categories) <= 10

Every service_category_id is:
  - unique within taxonomy.service_categories;
  - a member of the exact closed V1 vocabulary;
  - in canonical service_category_id ASC array order.

Every taxonomy.services[i].service_category_id:
  - must refer to exactly one present service_category_id
    in the SAME exact taxonomy artifact.

Absent *unused* V1 categories are valid.
Present category IDs outside the V1 vocabulary are invalid.
A missing referenced category invalidates the whole artifact/bundle.
A duplicate category ID invalidates the whole artifact/bundle.
```

The ten allowed IDs, and no others, are:

```text
category.video_streaming
category.audio_streaming
category.messaging
category.social
category.cloud_storage
category.productivity_collaboration
category.gaming
category.software_distribution
category.web_search
category.other_supported
```

`category.other_supported` is **not** an unknown/unrecognized-traffic bucket: use it only for an independently admitted known Service that does not fit another V1 category, as stated in v1 §14.

## 2. Grounds

- Architecture v1 §14 explicitly enumerates a *closed vocabulary* of exactly ten valid category IDs.
- Architecture v1 §16 describes `service_categories` as a tuple of `ServiceCategoryTaxonV1` records, without requiring every allowed vocabulary member to be present.
- Normative R1 §3.5 requires canonical ordering and uniqueness, and every Service's reference to an existing category **in the same artifact**.
- Normative R1 §3.14 gives an expected-valid synthetic taxonomy containing exactly **one** category.
- Architect-accepted Lane A v1 concrete taxonomy contains exactly **three** categories: `category.audio_streaming`, `category.messaging`, `category.video_streaming`; five admitted Services reference these entries. It has semantic SHA-256 `7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278`, independently recomputed from its exact JSON.
- Literal `len(service_categories) == 10` would reject two normative positive examples and therefore contradict the accepted artifacts. It is forbidden.

## 3. Tests required of Coder

1. **PASS:** exact original Lane A taxonomy containing three categories (do not alter bytes, version or semantic digest).
2. **PASS:** normative R1 §3.14 synthetic taxonomy containing one category; expected digest remains unchanged.
3. **PASS:** a valid taxonomy with all ten distinct allowed category IDs, canonically ordered, and valid Service references.
4. **PASS:** any nonempty proper subset of the vocabulary when all Service references remain valid; missing unused categories are allowed.
5. **FAIL:** 11 categories; unknown category ID; duplicate category ID; unsorted category array; Service reference to a category not serialized in the same artifact.
6. **FAIL:** zero categories in a production bundle that must contain >=1 Service; no Service may exist without a valid category reference.
7. **FAIL:** silent autofill of absent categories, silent reordering of malformed stored JSON, silent repair, or any no-op mutation of immutable accepted Lane A bytes/digests.

## 4. Scope / permissions

```text
CATEGORY CARDINALITY INTERPRETATION = CLOSED
INPUT / CONTRACT BLOCKER = CLOSED
CODER MAY CONTINUE = YES, within already authorized Unified55 scope
ARCHITECTURE VERSION CHANGE = NO
LANE A ARTIFACT BYTE CHANGE = NO
LANE A VERSION/DIGEST CHANGE = NO
SOURCE EDIT BY TECHLEAD = NO
GIT COMMIT / PUSH / PR / MERGE BY TECHLEAD = NO
PRODUCTION / FLAG / SYSTEMD CHANGE = NO
```

This clarification does **not** waive any other admission, data provenance, security, resource or code review gates. Coder must include the contract clarification in final evidence/handoff.
