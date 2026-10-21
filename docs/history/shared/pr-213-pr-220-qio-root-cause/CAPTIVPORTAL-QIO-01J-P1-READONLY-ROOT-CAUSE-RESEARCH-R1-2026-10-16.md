# CaptivPortal — QIO-01J / Journald Producer Attribution
## Tech Lead Read-Only Research R1 — 2026-10-16 (Asia/Baku)

**Decision:** `PARTIAL_EVIDENCE / ROOT_CAUSE_HOLD / SYSADMIN_FULL_JOURNAL_READONLY_CAPTURE_REQUIRED / CODER_IMPLEMENTATION_HOLD`.

### 1. Purpose and normative scope

PERF-IO-QUIET v1.0 §4 QIO-01 identifies `systemd-journald.service` as the largest measured guest writer in QUIET-01: **1,982 guest cgroup block writes and 9.75 MB in 120 seconds** on 2026-10-15. This is **writer** attribution, NOT identification of the applications generating messages. The research goal is to name high-volume producers, distinguish useful/auth/audit/error telemetry from redundant empty successes, connect changes to block-I/O, and offer one narrow lab hypothesis without reducing log durability. This note does not authorize implementation, production changes or production profiling of QIO-02.

### 2. New read-only environment confirmation

Via the existing authorized Remote Desktop Commander → DESKTOP-7C8M3BS → PuTTY saved session `Ubunt` → Ubuntu VM (no credential material read):

- Host reported `local.domain.az`, account `admin`, date 2026-10-16 21:59:02 +04:00, `load average` **9.03 / 9.50 / 9.88** and >32 days uptime. This is **not quiet workload**, so it cannot serve as a matched baseline against QUIET-01.
- `captive-portal.service` and `systemd-journald.service`: `active`; production `/opt/CaptivePortal` Git `HEAD=e2cbd96916d8a81f07f0d79a1a745f593ccb5114`, tree `8c95448250d75b01580bfdd4c52a40cf71a288af`. GitHub main is independent, last observed at `516abc7f56cb9c60a0e450af109334f4949b3da9`.
- `id -nG` returned **`admin www-data docker telemetry`**. **Neither `adm` nor `systemd-journal` is present.** Unprivileged `journalctl --disk-usage` explicitly warned: **"You are currently not seeing messages from other users and the system. Users in groups 'adm', 'systemd-journal' can see all messages."** Total archived/active journal size reported 2.0G; size is not rate or physical IOPS.
- **Result: current journal message sample is *permission-truncated*. All unit rankings below describe only the accessible subset. It is invalid to infer system-wide top message producers from it.** `journalctl -q` suppressed the warning until access was checked explicitly; this finding supersedes any earlier assumption of complete journal coverage.

### 3. Bounded message samples — partial access only

Two bounded, fixed-date `journalctl --since=@… --until=@… -o json --no-pager` windows were aggregated remotely with `jq`, `sort`, `uniq`, without printing raw messages or capturing identifiers/tokens.

| Accessible `_SYSTEMD_UNIT` | 21:56–21:58 | 21:58–22:00 | Four-minute total |
|---|---:|---:|---:|
| captive-portal.service | 72 | 41 | 113 |
| fingerprint-evidence.service | 40 | 37 | 77 |
| traffic-projection.service | 7 | 10 | 17 |
| fingerprint-classification.service | 7 | 6 | 13 |
| **Accessible total** | **126** | **94** | **220** |

These rates must NOT be compared 1:1 to journald cgroup write IOPS. The accessible portal events were substantially HTTP access log lines, including CAPPORT, auth/session and public counter routes, plus functional warnings and completed background events. A derived *route prefix* aggregation was performed without printing client IP/MAC or request IDs. Auth/CAPPORT access logs **cannot be assumed redundant**.

For the **77 accessible `fingerprint-evidence.service` messages** in the same four-minute fixed window, `journalctl -u ... -o json | wc -l` and an explicit `_SYSTEMD_UNIT=...` query both returned **77**. Of these, `journalctl -u ... -o cat | jq -Rr fromjson?` recognized **42 standalone JSON messages**, leaving **35 non-JSON message lines**. Their content and usefulness are not fully classified; HTTP request logging is a plausible but not yet proven explanation. No raw non-JSON message content was exported. The following event/count distribution describes **only the 42 JSON telemetry events**, not all 77 lines.

The observed parsed structured events comprised 30 ingest completed, 6 ingest duplicate, 5 source-health completed, 1 retention completed. The structured event payload distributions were:

- 21 `ingest_completed` with `received=100, inserted=100, duplicate_noop=0` (**real processing**, not empty noise);
- 6 `ingest_completed` with `received=100, inserted=0, duplicate_noop=100` (fully duplicate batches);
- 3 `ingest_completed` with `received=1, inserted=1, duplicate_noop=0`;
- 6 `ingest_duplicate` with `duplicate_noop=100` (paired duplicate telemetry);
- 5 `source_health_completed` with nonzero inserts (3 ×1, 2 ×2);
- 1 `retention_completed` (operational).

The API source (`app/device_fingerprint/api.py` on `main@516abc...`) unconditionally emits an `ingest_completed` event following successful persistence, and emits an **additional** `ingest_duplicate` event when duplicate count is positive. `app/device_fingerprint/telemetry.py` uses `INFO` and emits JSON to `StreamHandler`. The duplicate extra event is a *possible* small log-reduction candidate, but its consumer semantics are NOT inventoried and ~6 examples/four minutes cannot explain the 1,982/120sec QUIET-01 journald writes. Removing it now is not justified.

### 4. Short journald block-I/O counter window — not physical HDD causality

Read-only sample of `/sys/fs/cgroup/system.slice/systemd-journald.service/io.stat`:

- **2026-10-16 22:08:58→22:09:10 AZST**, 12 seconds.
- On guest block-device cgroup entry `252:0`, `wios` increased **398001→398283 = +282**, i.e. **23.5 guest writes/sec**, and `wbytes` **1,910,960,128→1,912,266,752 = +1,306,624 B**.
- Entry `253:0` shows similar nested/layered accounting; **do not sum 252:0 and 253:0**.
- The `admin`-accessible journal showed only four messages in that matching 12-second window. **This mismatch is NOT proof of excessive writes-per-message**, because the journal reader is permission-restricted, journal metadata/writeback costs are unknown, and host HDD block attribution was not sampled.

### 5. Adversarial interpretations and safety constraints

1. The 1,982 writes baseline remains valid **for guest journald as a writer**, but **root cause remains unidentified**. Complete all-unit visibility is the missing evidence.
2. Counter differences, `journalctl` event counts, log file sizes, and system load cannot be substituted for synchronized host completed write IOPS or fsync/file attribution.
3. The captured time window includes active auth/producer work and high system load, not a matched quiet control.
4. Do not disable journald, globally increase log thresholds, change rate limiting, flush/durability/retention, cut security/auth/audit/failed health telemetry, or change producer logging formats without consumers and explicit admission.
5. QIO-01A and QIO-01D have existing, separate contracts; do not conflate or re-implement them. QIO-01D stays default OFF pending Grafana consumer-first migration.
6. No production source/config/DB/service mutation, restart, sudo, SysAdmin group membership change, privileged journal export, or new profiler was performed by Tech Lead.

### 6. Decision and exact next gate

**Architecture request:** **NOT YET.** Missing evidence is system-level journal visibility and operation-level causal attribution; no specific authoritative log/heartbeat semantics change has been selected. If later evidence selects suppression/aggregation of auth/audit/freshness/duplicate-ingest or other consumer-visible events, request a narrow Chief Architect contract *before* a Coder implementation task.

**SysAdmin request:** QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01, read-only, bounded, aggregated output only. Require complete journal privilege through an existing authorized operator session and at least two comparable low-load 120s samples with timestamped system-wide unit counts, safe event/priority distribution, journald cgroup wios/wbytes, service logs and host/QEMU write metrics **only where already available safely**. Protect raw messages and IDs; no changing privileges, journal config, or production state. Full journal access and matched timestamps are evidence gates, not grounds for riskier instrumentation.

**Coder implementation:** `HOLD`. No supported high-impact no-op producer established, no safe file allowlist or falsifiable H1 selected. After SysAdmin evidence, Tech Lead must independently determine one narrow, measured producer-specific lab hypothesis, consumer contract and (if necessary) architecture request; only then issue source-changing TASK.

```ini
TASK=QIO-01J
STAGE=P1_READONLY_ROOT_CAUSE
BASELINE_WRITER_JOURNALD=1982_GUEST_WIOS_PER_120S_2026-10-15
ACCESSIBLE_JOURNAL=PERMISSION_TRUNCATED
CURRENT_LOAD_NOT_QUIET=YES
PRODUCER_CAUSAL_ATTRIBUTION=INCOMPLETE
SYSADMIN_READONLY_CAPTURE=REQUIRED
ARCHITECT_REQUEST=NOT_REQUIRED_YET
CODER_IMPLEMENTATION=HOLD
PRODUCTION_MUTATIONS=NO
PRODUCTION_CONFIG_CHANGE=NO
PHYSICAL_HDD_SAVING=UNPROVEN
```
