# TASK-FP-IO-W2-IMPLEMENT-01 — F2 atomicity correction

SOURCE_IMPLEMENTATION=COMPLETE / TECHLEAD23_VERIFICATION_PENDING

Worktree: `/home/zaur_navi/captivportal-lab/worktrees/fp-io-w2-implement-01`

BASE_HEAD=385fecebd2bd8778c3a2034514d9e72587984753
BASE_TREE=baefd2c4fbceff51aade93d840d93fc81a88fd58
WORKTREE=DIRTY / UNCOMMITTED

## Correction scope

Only these two source files were edited in this correction:

- `app/device_fingerprint_sensor/spool.py`
- `app/device_fingerprint_sensor/ingress_coalescer.py`

`SensorSpool.enqueue(..., atomic_coalesced=False)` retains the existing default transaction path. Only the accumulated evidence flush in `IngressCoalescer._flush_locked()` opts into the new mode. The bounded group uses explicit `BEGIN IMMEDIATE`, the existing `INSERT OR IGNORE`, and `COMMIT`. A pre-commit exception rolls back the group. If rollback cannot clear the transaction, the connection is closed and discarded rather than left available to another caller.

The atomic branch admits evidence-only groups of at most 32 events and 262144 serialized bytes. With F1 enabled, timestamps of actually inserted rows are collected and applied to the stale memo only after COMMIT. Errors invalidate the memo to UNKNOWN; ignored duplicates do not update it.

Legacy/F1-only enqueue, source-health enqueue, oversized-event bypass, ACK, HTTP delivery, TTL filtering, purge and capacity authority remain on their existing paths. SQLite DELETE/FULL, schema, MAX_TRANSACTION_ROWS=100 and the coalescer 100ms limit are unchanged. No new flag or configuration was introduced. Evidence Sink was not changed. F2 production activation remains HOLD.

## Full replacement patch

Patch includes all six existing Wave 2 candidate files, against the exact BASE_HEAD, including the untracked coalescer:

- `app/device_fingerprint_sensor/config.py`
- `app/device_fingerprint_sensor/models.py`
- `app/device_fingerprint_sensor/runtime.py`
- `app/device_fingerprint_sensor/spool.py`
- `app/device_fingerprint_sensor/telemetry.py`
- `app/device_fingerprint_sensor/ingress_coalescer.py`

PATCH_PATH=C:\CaptivPortal-Lab\handoffs\fp-io-w2-f2-atomicity-correction-20261013\TASK-FP-IO-W2-IMPLEMENT-01-F2-ATOMICITY.patch
PATCH_BYTES=41857
PATCH_SHA256=d36375f03a49b5604da99ec2a927f6736fb7b1a24f9073658c6f29009d7d01e6
PATCH_STAT=6 files changed, 610 insertions(+), 26 deletions(-)

Prior handoff artifacts were not overwritten. Source metadata and patch hashing only; no executable verification was performed. TechLead23 owns independent tests, QA and acceptance.

TESTS_RUN=NO
QA_RUN=NO
COMPILE_RUN=NO
PROFILING_RUN=NO
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO

STOP / HANDOFF TO TECHLEAD23
