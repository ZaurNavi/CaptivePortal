# CaptivPortal — TechLead23 / Fingerprint Wave 2
## Final narrow source correction — F2 coalescer fallback mode

**Date:** 2026-10-13 (Asia/Baku)  
**Original TASK:** `TASK-FP-IO-W2-IMPLEMENT-01`  
**Status:** `TECHLEAD_VERIFIED / ONE FINAL CORRECTION REQUIRED`  
**Baseline HEAD:** `385fecebd2bd8778c3a2034514d9e72587984753`  
**Baseline TREE:** `baefd2c4fbceff51aade93d840d93fc81a88fd58`

## Independent verification already performed by TechLead23

- Replacement full patch: **41,857 bytes**, SHA256 `d36375f03a49b5604da99ec2a927f6736fb7b1a24f9073658c6f29009d7d01e6` — verified against delivered file and worktree (`git apply --reverse --check`: PASS).
- Exact inventory: 5 modified Sensor sources + 1 added `ingress_coalescer.py`; no staged, no Git/production action; clean patch whitespace, Python AST PASS (18 modules).
- Applied the full patch to an **isolated read-only-review directory**, not the Coder worktree or production.
- Existing Fingerprint sensor/integration/fingerprint regression: 780 PASS.
- Prior independent option-on tests: 8 PASS, including group `ROLLBACK` on fault injected at the third INSERT, verifying no partial rows; before correction this fault left 2 partial rows.
- Extra adversarial SQLite tests: 5 PASS (atomic 32-row durability/restart, duplicate idempotency, preserving preceding durable row on rollback, F1 freshness memo rebuilding, unchanged legacy autocommit, invalid group protection); 1 reproducible failure described below.

## Reproducible failure / requirement violated

**Architect `ARCH-DEVICE-FINGERPRINT-IO-WAVE2-WRITE-PATH-CONTRACT-v1`, §4.7 and §11:** If the coalescer's **own logic** fails but the underlying spool remains usable, disable coalescing for the process and flush pending events through the **legacy immediate enqueue** path, using the same stable IDs.

In `app/device_fingerprint_sensor/ingress_coalescer.py`, current `_fallback_locked()` calls `_flush_locked()`; however `_flush_locked()` unconditionally invokes `_enqueue_locked(events, atomic_coalesced=True)`. Therefore the fallback incorrectly opts into the new group transaction. This is a **contractual fallback mismatch**, not an observed data loss or an atomicity regression.

**Independent injected test:** queue evidence `id=1`, induce an internal serializer error for `id=2`, trace `SensorSpool.enqueue(atomic_coalesced=...)`. Actual sequence: `[True, False]`, while contract-required legacy fallback is `[False, False]`. Both IDs persisted; wrong fallback branch definitively reproduced.

## Exact correction for Coder (one file, no redesign)

File: `app/device_fingerprint_sensor/ingress_coalescer.py`.

Keep **normal F2 `_flush_locked()` atomic by default**, but allow `_fallback_locked()` to ask for legacy enqueue explicitly. A minimal acceptable implementation is:

```python
# Existing normal flushes remain atomic_coalesced=True.
def _flush_locked(self, *, atomic_coalesced: bool = True) -> int:
    if not self._pending:
        return 0
    events = [event for _ordinal, event in self._pending]
    self._pending = []
    self._bytes, self._oldest = 0, None
    return self._enqueue_locked(events, atomic_coalesced=atomic_coalesced)

# In _fallback_locked(), after setting disabled / fault notification:
return self._flush_locked(atomic_coalesced=False)
```

Equivalent minimal source change is allowed, but **no refactor or other file edits**. Do not weaken or remove the fixed explicit `BEGIN IMMEDIATE / COMMIT / ROLLBACK` handling in SensorSpool for **normal** F2 groups. Do not change F1, L1, CAPPORT, Evidence Sink, config/flags, SQLite PRAGMAs, schema, ACK, TTL or capacity checks.

## Acceptance checks — performed by TechLead23, NOT Coder

1. Repeat injected coalescer-internal-fault test: pending flush must call `atomic_coalesced=False`, then submit current event on the legacy path (expected `[False, False]`); IDs/order unchanged.
2. Repeat injected third-INSERT spool failure: group transaction must roll back to 0 new rows; normal F2 flush uses `atomic_coalesced=True`.
3. Repeat **780** existing Fingerprint regression tests and independent option-on checks.
4. Run post-fix source integrity test; if clean, TechLead23 issues publication directive.

## Coder action and boundaries

Continue the **same dirty/uncommitted worktree**:
`/home/zaur_navi/captivportal-lab/worktrees/fp-io-w2-implement-01`.

Submit **one complete new replacement patch** against the pinned baseline, updated SHA256 and handoff. Do not send just the two-line partial diff.

`CODER=SOURCE_FIX_ONLY`  
`TESTS/QA=TECHLEAD23`  
`COMMIT/PUSH/PR/MERGE/DEPLOY=HOLD`  
`F2_PRODUCTION_ACTIVATION=HOLD (separate Owner authorization required)`
