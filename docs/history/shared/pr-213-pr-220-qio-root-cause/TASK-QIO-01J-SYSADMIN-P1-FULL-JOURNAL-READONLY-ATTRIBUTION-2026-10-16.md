# TASK-QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01
## Tech Lead → SysAdmin / Observability: bounded read-only journald producer attribution

**Date:** 2026-10-16 (Asia/Baku)  
**Status:** **READY FOR AUTHORIZED SYSADMIN READ-ONLY EXECUTION**. Does not authorize account/group changes, sudo installation, raw journal export, journald or producer configuration edits, restarts, retention changes, profiling, or deployment.

### A. Why this is required

QIO-01J investigates why `systemd-journald.service` accounted for **1,982 guest cgroup writes / 120 sec** in the QUIET-01 baseline of 2026-10-15. The Tech Lead's direct SSH account `admin` is not in the `adm` or `systemd-journal` group and `journalctl` explicitly warns that system/other-user messages are hidden. The partial 2026-10-16 samples are **not a complete journal producer ranking**. We need one complete, bounded, privileged **read-only attribution**, not a global logging fix.

### B. Boundaries and priority

- Host: CaptivPortal Ubuntu VM **192.168.0.202**, through an **existing authorized SysAdmin account/session** that can read the full system journal. Do not give ChatGPT a password or token; do not grant `admin` new group membership merely for this task.
- **First** check `date -Is`, `uptime`, and whether the machine is already overloaded; defer the heavy or long parts if VM is under acute pressure. A short indexed historical `journalctl` window is preferable to a full-journal scan.
- No file writes to production. No `journalctl --vacuum-*`, `--rotate`, `--flush`, `--sync`, reload/restart, rate-limit changes, `strace`, `perf`, file copy, retention edit or service change. Nothing in production's Git tree is to be modified.
- No raw `MESSAGE`, request IDs, producer IDs, MAC/IP, URL query strings, bearer tokens, TLS secret material, full process environments or credentials in the handoff. Aggregate on the machine; only non-sensitive counts/identifiers go into the report.

### C. Primary baseline-reconciliation evidence (low-impact, deterministic)

Obtain the **full** journal counts for these exact historical windows (Asia/Baku):

- `2026-10-16 21:56:00` through `21:58:00`
- `2026-10-16 21:58:00` through `22:00:00`

These were previously queried by restricted `admin`. Its partial counts were **126** and **94**; four-minute partial-unit totals: `captive-portal` 113, `fingerprint-evidence` 77, `traffic-projection` 17, `fingerprint-classification` 13. With full privileges, verify that the full total is at least as large and reveal the **top 25–30 units** by count. Capture:

1. Privilege proof (e.g. `id -nG` for the authorized operator or equivalent) and the absence of partial-journal warning; do not disclose credentials.
2. Total entries in each window, top `_SYSTEMD_UNIT` + `SYSLOG_IDENTIFIER` fallback by count, total `MESSAGE` byte volume by producer, and histogram by `PRIORITY`. Distinguish `UNKNOWN` units and system/kernel messages. Do not count a single journal entry twice.
3. For top five high-volume units only, distribution of **sanitized event types or stable template IDs**, INFO/DEBUG vs WARN/ERR vs auth/security/audit, repeated unchanged success/polling vs real changed state. If a template cannot be safely classified without raw content, label it `unclassified` and keep it local.
4. Report how many messages the unprivileged `admin` view hid in each window; this explains why prior visible events are incomplete.

**Example bounded commands for an already-authorized operator (adapt to actual operator elevation):**

```bash
# No persistent file written. Use an already-authorized journal reader.
date -Is
id -nG
uptime
journalctl --disk-usage

# Run these with existing root/systemd-journal authority; an operator may
# prepend sudo only if their own approved workflow provides that right.
# First window; use quotation to preserve the timestamp syntax.
journalctl --since='2026-10-16 21:56:00' --until='2026-10-16 21:58:00' \
  -q --no-pager -o json |
  jq -r '._SYSTEMD_UNIT // .SYSLOG_IDENTIFIER // "UNKNOWN"' |
  sort | uniq -c | sort -nr | head -30

# Overall count for the same exact window:
journalctl --since='2026-10-16 21:56:00' --until='2026-10-16 21:58:00' \
  -q --no-pager -o json | wc -l

# Repeat for 21:58:00–22:00:00; record exact filter, output totals and time.
# Safe priority histogram: no MESSAGE content printed.
journalctl --since='2026-10-16 21:56:00' --until='2026-10-16 21:58:00' \
  -q --no-pager -o json | jq -r '.PRIORITY // "UNKNOWN"' |
  sort | uniq -c | sort -nr
```

**Caution:** the existing `admin` session without full journal privileges is **not** an acceptable substitute. A lack of WARNING when using `-q` is not proof of access; check privilege explicitly.

### D. Conditional recent steady-state follow-up

If safe and authorized, capture **two additional 120-second low-load windows** at different times, *not* during startup, catch-up/maintenance or active auth peaks. Use the same whole-journal aggregations (not raw events). Align start/end clocks for:

- Guest journald cgroup `io.stat` **wios/wbytes**, with device major:minor and exact delta (layered entries not summed).
- Journal message count/bytes per producer and severity.
- Host Ubuntu-QEMU cgroup block writes and `/dev/sda` completed write counters/await/busy **only if the SysAdmin has an existing safe passive method and Owner permission covers it**; do not deploy probes, instrument production processes or infer exact host IOPS from guest entries.

Short log-count windows alone cannot prove physical HDD savings. If the full journal exposes a P0/P1 warning/error storm, label it as an incident first, not as an optimization target.

### E. Deliverables / exact decision gate

Return a single sanitized report containing: authorized capture scope + exact time windows + timezone; complete journal visibility proof; full unit counts and severity; top three **concrete repetitive event templates** with estimated volume and whether they are useful/mandatory; correlation limits; optional matched guest/host I/O; and whether a **single source-side harmless no-op** exists. Preserve sensitive raw logs **on the authorized system only** according to local policy; never attach them to the chat.

Tech Lead will select one narrow source-level hypothesis, audit Loki/Grafana and other consumers, decide whether a Chief Architect semantics contract is needed, and only then issue a file-allowlisted Coder TASK for isolated Laptop Lab. Without full producer evidence: `CODER=HOLD`.

```ini
TASK=QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01
RUN_MODE=BOUNDED_READONLY
PRIVILEGED_FULL_JOURNAL_VISIBILITY=REQUIRED
PRODUCTION_MUTATION=NO
CREDENTIAL_EXPOSURE=NO
PRODUCTION_PROFILE_HEAVY=NO
RAW_LOG_EXPORT=NO
OWNER_MERGE_OR_DEPLOY=NO
CODER_IMPLEMENTATION=HOLD_PENDING_EVIDENCE
ARCHITECT_REQUEST=DEFER_UNTIL_SEMANTIC_CHANGE_IDENTIFIED
```
