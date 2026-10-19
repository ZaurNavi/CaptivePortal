# CaptivPortal — QIO-02 / P2 / H1 — Tech Lead → Coder R2 correction directive

**Status:** `RETURN_TO_CODER / NARROW TEST FIX ONLY`; disposable laptop Lab, Architecture v1.4 remains authoritative.  
**Incoming candidate TREE:** `7fc908e1e6e5b2ae96f00a50adc7bce321620c62`  
**Incoming patch SHA256:** `63ce6d7020ffa9e68e93711d9017e0d2cfbc5aa49dbfe097820ce584be09a742`.

Independent Tech Lead reproduced **126 Linux focused PASS** and **123 Windows focused PASS + 3 FAIL** on exact candidate. The failures are:

- `test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write[missing]`
- `test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write[replace]`
- `test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write[rename]`

All three attempt to unlink or rename the currently open archive inside proof injection, which Windows rejects with `WinError 32`. This occurs before the candidate validation function and is a test portability issue. Product behavior is not rejected by these results.

## R2 action

1. Fix **only** `tests/test_public_traffic.py`; do not modify `reader.py`, `repository.py`, library, SQLite modes, schema, or runtime configuration. Preserve all originally submitted C01–C20 assertions, especially real open-descriptor mutation/rotation under POSIX.
2. Add deterministic Windows-compatible injection at the same validation seam, e.g. mock `source.path.stat()` to raise `FileNotFoundError` or to return a mismatched signature, so fallback through the real `_verify_stable_retired_eof()` is actually exercised while an in-use file remains open. The Windows tests must verify absence of no-op and fallback legacy UPSERT, with durable state checks as relevant. Do not simply disable/xfail/deselect the scenarios or mark the full test as skipped.
3. On Linux keep actual unlink/rename/replace negative tests. Ensure both platform paths are named/explained in handoff and independently evidenced. Avoid sleep-based races; retain deterministic injection. A platform-specific split inside a test is acceptable if the Windows branch still asserts equivalent fail-closed contract.
4. Run **only** focused Linux+Windows Public Traffic tests and static compile/diff checks as Coder. Full Central/Windows/Linux suites, independent PERF, and acceptance remain Tech Lead's responsibility.
5. Report new uncommitted candidate tree from an external index, new replacement patch SHA256, exact changed file(s), Linux and Windows focused results, test inventory and logs, rollback. Preserve frozen base `191beda1f23f8f466d2431f42e57571815d85778`; no commit/push/PR/merge/deploy and no production access.

**STOP/ASK TL** if portable negative validation cannot be proved without changing the two production source files or weakening the Linux race coverage.

```ini
TASK=QIO02_P2_H1_CODER_R2
STATUS=AUTHORIZED_TEST_FIX_ONLY
PATCH_BASE=191beda1f23f8f466d2431f42e57571815d85778
ALLOWED_CHANGE=tests/test_public_traffic.py
SOURCE_RUNTIME_CHANGE=NO
FOCUSED_TESTS=LINUX_AND_WINDOWS_REQUIRED
FULL_SUITE=TECH_LEAD_OWNED
COMMIT_PUSH_PR_MERGE_DEPLOY=NO
```
