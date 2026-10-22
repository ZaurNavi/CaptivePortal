# DF-RICH-HINTS-01 — final local implementation handoff

Date: 2026-10-18 (Asia/Baku). **Ready for independent Tech Lead source/QA review; not publication/release acceptance.**

## Exact candidate

```text
ORIGINAL_BASE_HEAD=c6db833952d8daabb8fccedb03a774f9277850b6
ORIGINAL_BASE_TREE=a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92
REPINNED_BASE_HEAD=ae1f99491318e32e247ea5d5877d53650cc8d78e
REPINNED_BASE_TREE=52762edd947f180b8fdf14676e23031f6e54949b
HEAD=ae1f99491318e32e247ea5d5877d53650cc8d78e
HEAD_TREE=52762edd947f180b8fdf14676e23031f6e54949b
CANDIDATE_TREE=0156a78738ca413027cac06a204468ace5d610ff
BRANCH=task/df-rich-hints-01-main-integration
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/df-rich-hints-01-main-integration
WORKTREE_STATE=DIRTY; all 10 candidate files staged; NO COMMIT
PATCH=replacement.patch
PATCH_BYTES=61610
PATCH_SHA256=54ad19d2d1b22edf31cef955c329afe01dd1b1d7ac5cc6686681f6955490286e
STAT=10 files / 928 insertions / 5 deletions
```

`git write-tree` identifies the uncommitted candidate, not HEAD. Latest origin/main fetch matched the repinned base. Original dirty Coder worktree/branch `df-rich-hints-01` / `task/df-rich-hints-01` remains preserved at the original base. No reset, stash, rebase, history rewrite or changes to other worktrees were performed.

## Baseline advance / PR #222 integration

Main advanced during final verification by merge PR #222 only (8 files, +602/-21). The original TASK explicitly permits repinning; a new clean integration worktree was created from exact `ae1f994...`, and the additive hints delta was applied there. The accepted diagnostic source is inherited from main, not rebundled as this task's implementation.

Narrow conflict resolutions retained `DeviceFingerprintPresentationService.get_detail()` and the existing `device_detail` call to it, then appended the independent hints service/DTO. The entire accepted presentation file remains an exact byte prefix of the candidate file; removing only this task's six inserted query-service lines reproduces the accepted query service exactly. Classification reader, origin-diagnostic tests and all other protected modules remain byte-identical to the new base.

The original historical JS reference `22cdde5...` and PR222 span guard/canaries remain. Two rich-hints insertions are removed exactly, then an additional full-prefix comparison to accepted integration base `ae1f994...` protects *all* remaining bytes, including canonical Fingerprint/diagnostic UI. No old historical reference was replaced or hash loosened. NI03 asset and NI04 lifecycle/runtime guards remain intact.

## Exact changed files

Production (only the five authorized files):

1. `app/device_fingerprint/read_service.py` — single bounded indexed RO read, strict persisted integrity/schema validation and deterministic group/Portal selection.
2. `app/admin_web/device_fingerprint_presentation.py` — independent allowlisted bounded hints DTO; existing canonical presentation is untouched.
3. `app/admin_web/runtime.py` — optional configured reader composition. Retention uses the existing canonical Fingerprint integer parser, including raw env strings; no producer/security configuration or environment reread.
4. `app/admin_web/query_service.py` — one sibling field in authorized Device Detail, same resolved identity and actual shared deadline.
5. `app/admin_web/static/admin.js` — two additive insertions only: safe-text hints renderer and Device Card invocation.

New tests:

- `tests/device_fingerprint/test_observed_hints.py`
- `tests/admin_web/test_observed_device_hints.py`
- `tests/admin_web/test_observed_device_hints_frontend.py`

Existing test modified under explicit approval:

- `tests/admin_web/test_device_service_intelligence_frontend.py` — narrow two-insertion exception, strict full-prefix integration guard and negative canaries; existing PR222/NI03/NI04 checks preserved.

Documentation:

- `docs/modules/admin-web.md` — bounded display contract and approved native SQLite sidecar clarification.

No other production file, config flag, route, schema, index, dependency, unit, CSS, producer or classifier changes. Exact per-file SHA256 and protected baseline hashes: `integration-and-integrity.json`.

## Functional / read boundary

One connection via unchanged `open_read_only()` and one necessary-column SELECT:

```sql
SELECT source_kind,feature_schema_version,observed_at,quality_state,
       CASE WHEN length(CAST(payload_json AS BLOB))<=65536 THEN payload_json ELSE NULL END AS payload_json,
       payload_sha256
FROM device_fingerprint_evidence
WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<?
ORDER BY observed_at DESC,evidence_id DESC LIMIT 256
```

Lower bound: inclusive later of configured retention cutoff and resolved `site_first_seen_at`. Upper bound: exclusive single pinned millisecond UTC as-of. Uses existing `idx_df_evidence_site_mac_time`, no temporary sorting tree. No per-kind query, list enrichment, OFFSET, extra endpoint, polling or worker.

Before projection, exact `verify_persisted_payload` and frozen production registry validate canonical bytes/digest/schema. Transfer/parse cap 65,536 bytes per payload; at most 256 candidate validations (16 MiB absolute sum cap), five groups and 65,536-byte output DTO. Group order is Portal, DHCP, TCP SYN, TLS, QUIC. The latest selected bad/unsupported record is not replaced with older data. Portal field search conservatively stops and marks Portal unavailable if a required candidate cannot be verified; independent groups remain visible. No claim of exhaustive history.

Model and OS may use separate valid Portal observations with independent provenance; platform only accompanies the exact record supplying OS major. V2 therefore never inherits Android/iOS from Controller, R14 or another row. No model/manufacturer inference, JA4 identity claim or classification/status/support changes.

Device Detail authorization and identity resolution occur first. Optional read uses the same request slot/deadline. When less than the unchanged native busy-timeout budget remains, the optional read fails soft before opening/entering SQL. Progress and materialization deadline checks prevent late hints success; core HTTP card and existing fingerprint survive reader failures. Source metadata is allowlisted; no payload/hash/internal IDs, raw headers, opaque client identifiers, private hostnames or exception paths are exposed.

## Approved SQLite sidecars / A15

Tech Lead explicitly permits native coordination sidecars from the mandated `mode=ro` helper. The former strict no-sidecar test was replaced, not skipped/xfail'ed.

Both checkpointed and active-committed-WAL scenarios verify main SHA256, unchanged tables/indexes, exactly one SELECT, closed connection and rejected DML via the RO helper. Active WAL bytes/committed row remain unchanged. Negative canaries reject changed main bytes, injected application SQL or a changed schema. SHM size is not fixed as a universal constant. No application frames, manual checkpoint, journal/durability changes, immutable mode or manual sidecar management were introduced. The existing helper is byte-identical to base.

## Final affected focused verification

| Platform | PASS | FAIL | SKIP | Duration |
| --- | ---: | ---: | ---: | ---: |
| Linux Python 3.10.12 / SQLite 3.37.2 | 229 | 0 | 0 | 21.69 s |
| Windows Python 3.10.11 / SQLite 3.40.1 | 229 | 0 | 0 | 50.67 s |

229/229 literal test IDs paired, no duplicates or eligibility exclusions. Real stdout logs, JUnit and exact commands/environment: `linux-focused.log`, `windows-focused.log`, `linux-focused.xml`, `windows-focused.xml`, `linux-execution.json`, `windows-execution.json`.

Reproducible command runner: `verify_focused.py <source-root> <evidence-output> <fresh-basetemp>`, executed using each existing qualified interpreter. It runs only these affected modules, `-q -p no:cacheprovider`, external basetemp/JUnit/pycache:

```text
tests/device_fingerprint/test_observed_hints.py
tests/device_fingerprint/test_read_service.py
tests/admin_web/test_observed_device_hints.py
tests/admin_web/test_observed_device_hints_frontend.py
tests/admin_web/test_device_service_intelligence_frontend.py
tests/admin_web/test_device_protocol_intelligence_frontend.py
tests/admin_web/test_device_fingerprint_frontend.py
tests/admin_web/test_device_fingerprint_presentation.py
tests/admin_web/test_device_current_context_frontend.py
tests/admin_web/test_query_service.py
tests/admin_web/test_runtime.py
tests/admin_web/test_fingerprint_origin_diagnostics.py
tests/admin_web/test_fingerprint_origin_diagnostics_frontend.py
```

Linux/Windows compileall of all eight changed Python files: PASS. Linux/Windows Node syntax: PASS. Working/staged diff-check and patch reverse-apply check: PASS. No unstaged changes in final integration worktree; index tree matches candidate.

Inventory tooling note: Windows-native Git's working-tree view over UNC reported a mode-only `scripts/check.sh` difference. Canonical WSL Git reports no unstaged change, mode 100755 remains, and its bytes match base. The final integrity script therefore verifies the exact staged candidate plus actual file hashes, with canonical WSL checking the unstaged tree; no executable bit, source, assertion or global Git config was changed to hide that VFS-view discrepancy.

## Coder acceptance mapping

| IDs | Focused evidence |
| --- | --- |
| A01–A03 | Portal v1/v2 exact fields, independent source/time/schema; same-record OS, no synthesis; browser/DOM v1 and v2 |
| A04–A07 | Exact DHCP/TCP/TLS/QUIC fields, privacy categories/booleans, five-group order/quality/origin; 40 structured TCP options |
| A08–A09 | Site/MAC/first-seen/retention boundaries; inclusive lower/exclusive upper; 257+ rows and descending ID ties; bounded missing group |
| A10–A11 | Bad JSON, duplicate members, noncanonical bytes, SHA, oversized payload and unknown schema; no older fallback; other groups preserved |
| A12 | Missing/corrupt/busy DB, deadline and permission injection; actual HTTP 200 core card/fingerprint preserved, no paths/canaries leaked |
| A13 | Validated markup displayed literally through text nodes; false/0/null distinction; maximum-length lists/strings in Lab preview, no overflow |
| A14 | Existing authenticated route, 401/403 and resolved device scope; one optional invocation; no list/Home enrichment or extra browser calls |
| A15 | Existing index EXPLAIN, 256 cap, deadline, no application writes, byte/schema/WAL invariants and readonly DML rejection/canaries |
| A16 | Historical observation times explicit; no service-state/live claim, producer activation or restart |
| A17 | Existing canonical presentation/query/UI tests and PR222 diagnostics; frozen protected blob hashes and NI03/NI04 controls |

## Performance / resource evidence (bounded Lab, not independent acceptance)

`measure_read.py` builds a disposable 12,544-row file-backed WAL locality fixture (main 13,156,352 bytes; WAL 13,336,472 bytes). Each of two cases has 25 preserved samples, including first-run outliers. No cache flush, percentile tuning, discarded samples or invented release threshold.

| Case/platform | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: |
| No data / Linux | 0.837 | 1.478 | 9.092 |
| Dense 256 / Linux | 35.961 | 59.503 | 87.298 |
| No data / Windows | 1.358 | 2.240 | 12.570 |
| Dense 256 / Windows | 41.836 | 89.671 | 127.585 |

Every sample: exactly one connection, one SELECT, one closed connection. Dense case: exactly 256 fetched/validated rows, 62,719 aggregate payload bytes, largest single payload 4,988 bytes, measured DTO 11,576 bytes; empty DTO 1,017 bytes. Existing index selected, no application changes to main/WAL bytes. Raw samples and EXPLAIN: `linux-read-metrics.json`, `windows-read-metrics.json`.

These samples preceded only the final startup-retention parsing correction. All measured read/projection/query/JS source bytes match the final candidate; runtime composition is not invoked in this micro-probe. Exact source hashes and explicit applicability are recorded in `integration-and-integrity.json`. Final 229-case runs verify the actual corrected runtime. Metrics were not rerun merely to replace slower samples.

**Not physical HDD evidence:** WSL/host file-backed, OS-cache-affected fixture; not a multi-GB production replica or HDD emulator. Independent HDD-like PERF threshold/security/full-gate acceptance remains Tech Lead responsibility. No production savings claim.

## Real browser / security evidence

Isolated headless Chrome 155.0.8059.40, fresh profile, localhost-only synthetic preview using exact current admin.js/admin.css and adapter-generated DTOs. Portal v1/v2 at 1280x1000 and 375x900. Native keyboard expands/collapses outer and TCP details; all 40 options become visible; no horizontal page/field overflow; one mocked Device Detail fetch. V2 displays OS-major without invented platform. Six PNG screenshots and machine evidence: `browser/`. This is a component fixture, not signed-in production/Admin product acceptance.

Built-in browser initialization failed (missing kernel asset path); external headless fixture was used. Initial pre-integration harness keyboard test lacked headless focus/text setup; corrected harness passed without source UI edits. Earlier evidence/failed attempts remain in preceding handoff directories; no failure was hidden or production code adjusted to a harness artifact.

Source/security checks include safe DOM/XSS canary, exact allowlists/integrity, Site/ACL isolation, fail-soft private diagnostics, DML rejection, no new network request/polling and protected byte mapping. No independent full security certificate is claimed.

## Additional implementation correction / retained limitations

Final composition review found actual `get_settings()` retention values are env strings, not necessarily integers. A RED case confirmed string `"17"` was not parsed by the draft. The permitted runtime now reuses the existing canonical integer parser; both int/string valid values work, bool/float/malformed/out-of-range/None fail optional composition without disabling Admin. No config module or policy change.

Portal summary search is deliberately conservative on corrupt required older candidates, as documented above. Native SQLite sidecars remain allowed only within the bounded approved exception. No history beyond the cap is searched; historical data does not establish live pipeline health or confirmed physical identity.

KNOWN_OPEN_P0=0 / KNOWN_OPEN_P1=0 within the Coder-checked scope. No outstanding implementation-contract ambiguity. **FULL_ACCEPTANCE=PENDING_TECH_LEAD**, not unconditional Full Gate PASS.

## Review / deployment boundary

Independent full Windows/Linux/security/PERF and final product review are Tech Lead/Owner gates; Coder did not run them. Subsequent publication needs explicit disposition on this exact candidate and rechecking current main. No schema/data migration is needed for the additive optional field. Source rollback is possible under separate Owner production authority; no manual DB/WAL cleanup belongs to rollback.

```text
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
RESTART=NO
PRODUCTION_ACTION=NO
NEXT_ACTION=INDEPENDENT_TECH_LEAD_REVIEW
```
