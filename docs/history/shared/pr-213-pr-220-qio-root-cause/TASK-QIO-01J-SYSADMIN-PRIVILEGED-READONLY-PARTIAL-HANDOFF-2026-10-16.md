# CaptivPortal — QIO-01J / SysAdmin privileged journal attribution

**Task:** `TASK-QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01`  
**Date/time:** 2026-10-16, Asia/Baku (UTC+04:00)  
**Host:** Ubuntu production VM `192.168.0.202`  
**Disposition:** `AUTHORIZED_FULL_JOURNAL_ACCESS=PASS; BOUNDED_READ=INCOMPLETE; ROOT_CAUSE=HOLD; CODER=HOLD`  
**Scope:** read-only. No production account, group, code, configuration, journal, or service changes.

## 1. Access and safety gate

- Authorized access path: Remote Desktop Commander → Windows workstation → existing PuTTY session `Ubunt` → `admin` → `sudo -n` (existing authorized policy).
- The existing `admin` user's groups are `admin www-data docker telemetry` and do **not** include `adm` or `systemd-journal`. Unprivileged journal view warns that system/other-user messages are hidden.
- `sudo -n -l` confirmed an existing `(root) NOPASSWD: ALL` permission; `sudo -n id -un` returned `root`, and final `sudo -n id -u` returned `0`. No new privilege, group or user was provisioned. A preparatory PuTTY session created on the Windows workstation was removed after discovering this existing path.
- `sudo -n journalctl --disk-usage` reported **4.0G** archived+active journal storage. The restricted user had reported **2.0G**; this is a visibility/size observation, not a measure of journal write rate.
- VM preflight at **23:17:24 AZST**: load `9.65/9.50/9.71`, PSI I/O `some avg10=76.39%`, `full avg10=57.83%`, memory available `5769 MiB`; `captive-portal.service` and `systemd-journald.service` active.
- Later load at **23:29:34 AZST**: `11.00/10.14/9.87`. Subsequent `full avg10` reached **68.28%** at 23:28:52 AZST. **Acute I/O pressure remains in effect.**

## 2. Fixed historical windows, full journal (Asia/Baku)

Requested exact half-open windows:

1. `W1 = [2026-10-16 21:56:00, 21:58:00)`; Unix epoch `[1792173360, 1792173480)`.
2. `W2 = [2026-10-16 21:58:00, 22:00:00)`.

Method: the root-authorized `journalctl --since=@... --until=@... -q --no-pager -o json` ran **only on the production guest**, with `nice -n 19`, `ionice -c3`, and a process timeout. The local Python consumer aggregated entries on the VM and printed only producer, sanitized severity/count/message byte totals, template-category/template-hash counts. Raw `MESSAGE`, host/client identities, request IDs, MACs, IPs, URLs or tokens **were not exported**. Entries were filtered in memory to the half-open epoch window.

**W1 was NOT completed.** The time-limited pipeline exited with `-9`, after 33.8 seconds. It emitted **195 parsed entries** (approx. 0.237 MB of JSON input processed) before forced termination. These numbers are **lower bounds / partial**, NOT complete producer totals. The previous restricted `admin` view held 126 records; at least 69 additional full-privilege entries appear in the captured partial sample, but the final hidden count is **unknown**. The exact W1 corpus was not exhaustively read.

**W2 was NOT attempted.** Under acute I/O pressure, repeating an incompleting historical journal scan would violate the task's low-impact constraint. Full W2 totals, hidden-message count, and producer ranking remain **UNKNOWN**. This is an explicitly recorded stop condition.

### W1 — producer counts and message bytes **only for captured partial sample**

| Producer | Entries | MESSAGE bytes | Observed PRIO |
|---|---:|---:|---|
| `captive-portal.service` | 72 | 6,987 | 72 INFO (`6`) |
| `fingerprint-evidence.service` | 40 | 10,656 | 40 INFO (`6`) |
| `snap.microk8s.daemon-kubelite.service` | 35 | 9,440 | 35 INFO (`6`) |
| `cron.service` | 17 | 1,225 | 16 INFO (`6`), 1 NOTICE (`5`) |
| `fingerprint-classification.service` | 7 | 1,027 | 7 INFO |
| `init.scope` | 7 | 495 | 7 INFO |
| `traffic-projection.service` | 7 | 4,474 | 7 INFO |
| `fingerprint-sensor.service` | 6 | 3,186 | 6 INFO |
| `snap.microk8s.daemon-containerd.service` | 3 | 677 | 3 INFO |
| `SYSLOG:CRON` | 1 | 52 | 1 INFO |
| **Sample aggregate** | **195** | **38,219** | **194 INFO, 1 NOTICE** |

Note: `_SYSTEMD_UNIT` was the primary attribution key; the `SYSLOG_IDENTIFIER` fallback was used only when no valid unit existed. Each journal entry was counted once. The sample's aggregate byte total is a sum of the per-unit captured `MESSAGE` UTF-8 bytes, not on-disk journal file usage and not IOPS. No kernel message was observed within this incomplete sample; this is **not proof** of absence from the complete W1 journal.

### W1 sanitized template observations (partial, not conclusions)

- `captive-portal.service`: 57 of 72 captured lines classified broadly as `http_access`, template/category ID `a66395390b18`. This groups HTTP access lines; it does **not** establish that all represent the same route or no-op. Auth/CAPPORT audit value must be protected.
- `fingerprint-evidence.service`: 18 access-log lines (`http_access`), 12 structured `device_fingerprint_ingest_completed` events with **positive inserts**, 3 structured `ingest_completed` with **zero inserts / positive duplicates**, 3 structured `ingest_duplicate` events, 3 `source_health_completed` with positive inserts, and 1 `retention_completed`. The two three-event duplicate classes are potential *overlapping informational telemetry* but no consumer-semantic proof or safe suppression admission exists.
- `snap.microk8s.daemon-kubelite.service`: 18 occurrences of one normalized hash `b8b298677b2f` (unclassified); 17 additional captured texts matched a coarse error/failure/exception keyword category. All 35 had journal **priority 6 (INFO)**. Their detailed semantics and incident status are **UNKNOWN**; do not classify them as innocuous success polling or suppress them.
- Other producers and stable hashes are in the command's transient aggregate only; no raw journal export was performed.

**No single proven harmless source-side no-op** can be recommended from this incomplete sample.

## 3. Live matched lightweight guest counters — not matched to W1/W2

Passive snapshot ending **2026-10-16 23:28:52 AZST** (UTC 19:28:52), duration **6.01 s**:

| Counter | Measured delta |
|---|---:|
| Guest `systemd-journald.service` cgroup `252:0`, `wios` | **+22 = 3.66 guest write ops/s** |
| Same cgroup `252:0`, `wbytes` | **+118,784 bytes** |
| Guest block device `/dev/vda`, completed writes | **+591 = 98.3 guest writes/s** |
| `/dev/vda`, written sectors (512-byte) | **+11,456** |
| `io.stat 253:0` | Mirrors +22 writes/+118,784 bytes; **nested layer, not added** |

At the end of this short snapshot, load was `11.21/10.04/9.82`, PSI I/O `some avg10=80.76%`, `full avg10=68.28%`. This snapshot demonstrates **current guest journald write activity**, not which processes produced its messages, not host HDD completed I/O, and not the 2026-10-15 QUIET-01 conditions. The 1,982 writes/120sec QUIET-01 baseline is not replaced or contradicted by this 6-second interval.

## 4. Tech Lead handoff / decision gate

```ini
TASK=TASK-QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01
RUN_MODE=BOUNDED_READONLY
AUTHORITY_PROOF=PASS_EXISTING_ADMIN_SUDO_ROOT
FULL_JOURNAL_ACCESS_CAPABILITY=PASS
W1_COMPLETE=NO_TIMEOUT
W1_CAPTURED_ENTRIES_LOWER_BOUND=195
W1_HIDDEN_ENTRIES_LOWER_BOUND=69
W2_COMPLETE=NO_NOT_ATTEMPTED_HIGH_IO_PRESSURE
COMPLETE_TOP_PRODUCERS=UNKNOWN
TEMPLATE_SEMANTICS=PARTIAL_UNCLASSIFIED
LIVE_GUEST_JOURNAL_CGROUP_WRITES_6S=22
MATCHED_PHYSICAL_HDD_CAUSALITY=NOT_MEASURED
SINGLE_SAFE_NOOP=NOT_PROVEN
PRODUCTION_MUTATION=NO
RAW_LOG_EXPORT=NO
CODER=HOLD
ROOT_CAUSE=HOLD
```

**Next safe action:** under a sufficiently lower-pressure period, repeat narrowly bounded full-journal queries for **both fixed historical windows**, without raw MESSAGE export; compute complete top 25–30 units, byte totals, priorities, templates of top five producers, and exact restricted-versus-full differences. Only after this, if safe, take two matched 120-second steady-state snapshots with journal counts and guest journald `io.stat` (and optionally host counters under separate safe permission). **Do not change logging or services to reduce load prior to producer/consumer review.**

**Stop reason:** the machine's exceptionally high I/O PSI and the incomplete first bounded query. Additional journal scans now risk exacerbating the problem and do not produce defensible full producer rankings.
