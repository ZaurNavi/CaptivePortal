# TASK-DTI-NI-04 — TECH LEAD ARCHITECTURE REVIEW R1
## Architect return: bounded repairs before Coder TASK

**Reviewed input:** `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md`, dated 2026-10-10 (6144 lines).  
**Pinned baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`, tree `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`.  
**Review disposition:** **SEMANTIC DIRECTION ACCEPTABLE / CONTRACT R1 REPAIR REQUIRED**.  
**Open P0:** 0. **Open P1:** 5.  
**Main NI-04 Coder:** HOLD. **NI-04A Coder:** HOLD until the repairs below are accepted and Owner authorizes a dedicated implementation TASK.  
**No source edits / Git mutation / production action authorized.**

## Accepted architecture: retain without redesign

- NI-04A first: protected NI-02B device-relative snapshot plus protected NI-01 DNS/SNI evidence read, followed by admission of local versioned recognition knowledge.
- Current NI-01/NI-02B storage and NI-03 API/semantics remain unchanged; no new traffic-store, parser family, metering service, external runtime calls, or direct database access from Admin/browser.
- Identity uses authoritative NI-02B Site+Device+event-time provenance; no IP-only service guess; safe failed/ambiguous/degraded states; no raw DNS/SNI in product outputs.
- Main NI-04 product work begins only after NI-04A acceptance. No merging or activation through this review.

## P1-01 — No concrete approved initial service-rule bundle / owner of admission

**Anchors:** §§17–18, 20–21, 133–134, 145–147.

The architecture explicitly requires **at least one real admitted Service and active Service rule**, but supplies no admitted service/hostname rule and no provenance evidence. The examples YouTube, WhatsApp, Telegram, etc. are explicitly *not* admitted. This would force Coder to select domains, classify services, and decide what constitutes proof — forbidden under Owner's workflow.

**Repair required:** either (A) supply an Architect/Tech Lead-approved, exact `InitialRecognitionKnowledgeManifestV1` + taxonomy/rules bundle with >=1 real service, including service/organization/category IDs and names, exact SNI/DNS hostname patterns and rule types, first-party or controlled evidence references, review/due dates, positive/near-match/CDN-negative fixtures; OR (B) explicitly split a **non-Coder research/admission gate** that must yield such an approved bundle **before** issuing the coding part of NI-04A. Distinguish which role is allowed to admit the knowledge. `Coder selects initial services/rules` is not an acceptable outcome.

**PASS:** exact approved knowledge input exists, or an explicit research/admission HOLD precedes the Coder implementation of bundle-dependent code; the code task will not make any semantic service-identification choice.

## P1-02 — Knowledge manifest and canonical version/digest contract incomplete

**Anchors:** §§16, 18–20, 34, 67–69, 133.

The document freezes `RecognitionTaxonomyContractV1` and `RecognitionRuleSetV1` fields, but **never freezes the complete top-level field schema of `InitialRecognitionKnowledgeManifestV1`**. `RecognitionKnowledgeSourceV1` is defined but not the envelope, source ordering, ID/version/digest, reference uniqueness, or validation constraints. `canonical-content SHA-256` lacks a byte-level recipe and digest-field exclusion, although hashes are binding cross-artifact identities. Knowledge- and rule-level review/due dates coexist without a precedence rule.

**Repair required:** freeze all manifest fields and validation invariants; define exact canonical serialization/ordering/UTF-8/JSON rules for all three artifacts, which digest field(s) are excluded from hash computation, permitted mutable fields, and equality/version rules; define missing/dangling refs, duplicate refs, and knowledge-vs-rule expiry precedence. Give one tiny canonical positive artifact example and one digest-invalid rejection example (synthetic names permitted here; real admitted rules are covered by P1-01).

**PASS:** two independent implementations generate identical digests and validation verdicts without guessing; invalid/expired material fails in a defined way.

## P1-03 — DNS→connection proof too weak/underspecified for false-positive claims

**Anchors:** §§9.3, 26–27, 29–30, 53, 60–61, 110–111.

Verified NI-01 schema: `network_metadata_dns` stores `dns_event_kind`, `dns_tx_id_decimal`, `rcode`, query and answer counts/truncation; `network_metadata_dns_queries` stores `ordinal, query_name, query_type`; **`network_metadata_dns_answers` stores only `ordinal, answer_type, answer_value`, without answer owner/query name**. Current proposed `RecognitionSourceEvidenceV1.dns` omits `dns_event_kind` and `rcode`. The proposed rule “a service-specific query and any A/AAAA answer in the same observation, plus a later outbound peer-IP match” does not in every case prove that the address answered *that particular query*. Additionally, the term “later eligible Device connection edge” is not constrained to an admitted connection family: NI-02B stores DNS/TLS/QUIC edges. A later DNS-to-resolver event must not count as a service connection. Shared CDN/IP reuse can yield ambiguous apparent correlations without an SNI.

**Repair required:** choose and freeze one safe V1 policy: (A) deterministic tightly constrained DNS-correlation admission with explicit `dns_event_kind`, response `rcode`, query-count/answer-count/truncation/answer-association admissibility, eligible subsequent connection edge families, same-device/site rules, multi-domain/shared-IP ambiguity exclusion and negative fixtures; OR (B) keep DNS-connected rule kinds defined but **not active/admitted in V1** until trustworthy association is demonstrable. Direct unique SNI Service recognition may remain enabled. Do not tell Coder to infer ownership links that current NI-01 schema does not store. Any change requiring a parent schema/semantic change must be returned as a separate HOLD rather than silently applied.

**PASS:** ambiguous DNS response, unrelated additional A/AAAA, DNS-to-resolver-only edge, and two candidate services sharing a peer IP cannot produce a false service resolution. Positive scenarios are reproducible using admitted source fields.

## P1-04 — Static collision rejection versus runtime ambiguity

**Anchors:** §§23, 29–30, 68, 109, 112, 122.

The startup validator rejects `duplicate/conflicting impossible static definitions`; separately the runtime semantics require equal-precedence service-rule collisions to produce `ambiguous` rather than an arbitrary winner. The boundary between **invalid rule bundle at admission** and **valid bundle with ambiguous observation at runtime** is not specified.

**Repair required:** define exact static duplicates/conflicts that make the whole bundle invalid, and exact valid overlapping rules/signals that must be retained and evaluated to `ambiguous`. Pin test pairs for both groups. Clarify whether identical match patterns targeting different services are prohibited at admission or deliberately accepted for runtime ambiguity. Do not let rule ID order choose a winner.

**PASS:** Coder can implement deterministic loader and runtime without guessing which collisions are legal.

## P1-05 — NI-04A code/validation boundary versus main NI-04 ownership

**Anchors:** §§7, 17–21, 68–72, 133–134, 145–147.

NI-04A explicitly may not implement the customer-visible Device Card/API/full NI-04 product. Nevertheless NI-04A is required to test admitted rules, specificity, near matches, and ambiguity, and its implementation boundary is not explicit about whether a production **pure rule loader/matcher** is included now or the same behavior is temporarily simulated only in tests and then independently reimplemented in main NI-04. That choice changes code ownership and duplication risk.

**Repair required:** freeze NI-04A deliverables file/module-boundary-wise at the architecture level: protected NI-01/NI-02B readers; taxonomy/knowledge/rules artifact validation; whether a reusable pure rule-matching kernel is permitted/required; which correlation/aggregation parts are deferred to main NI-04; no Admin Service API/UI and no user-data writer. Tests must exercise the same accepted production semantic kernel, not a divergent test-only approximation. Ensure no coder-owned architecture choices.

**PASS:** single semantic owner and exact sequence of deliverables; no duplicated rule engine or undefined test-only behavior.

## Required Architect response

Produce `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1-R1.md` as either a fully self-contained corrected revision, or an exact change addendum with normative supersession positions. Address R1-01 through R1-05 separately, with **PASS / HOLD** and evidence for each. Preserve all otherwise accepted invariants and the baseline unless independently shown to have moved.

If P1-01 requires independent evidence research, identify that separate admission gate and keep corresponding code Coder HOLD until its output is approved. No fabricated first-party knowledge or guessed hostname rules.

**Next governance:** Architect R1 → Tech Lead independent acceptance → exact NI-04A implementation TASK → explicit Owner authorization → Coder. The main NI-04 product TASK remains HOLD until NI-04A PASS.
