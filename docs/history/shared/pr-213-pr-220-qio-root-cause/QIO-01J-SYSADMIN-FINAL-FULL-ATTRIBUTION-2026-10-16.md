# TASK-QIO-01J — SysAdmin FINAL: Full-Journal Producer Attribution

**Project:** CaptivPortal  
**Target:** Ubuntu production VM `192.168.0.202` (`local.domain.az`); KVM host `omv-hp` (`192.168.0.220`)  
**Captured:** 2026-10-16, Asia/Baku (AZST, UTC+04:00)  
**Status:** **EVIDENCE COLLECTION COMPLETE / ROOT-CAUSE DECISION RESERVED FOR TECH LEAD**  
**Execution:** authorized Owner high-I/O-pressure override; full privileged journal read via existing approved SSH session `Ubunt` (`admin` → `sudo -n` root); no password or private key transferred  
**Production modifications:** **0**; no restart, service stop, installation, journal configuration/retention change, repository change, database query, journal export, or instrumentation. Aggregation scripts were transmitted through SSH standard input and executed in memory. No raw journal messages, client identifiers, URLs, cookies, request IDs or secrets were exported.  

## 1. Decision summary

The previously missing privileged historical attribution **is now complete**. Both requested historical windows were read in a **single** bounded `journalctl` pass, with exit code `0`, unambiguous EOF, zero JSON parse errors, and an explicit half-open timestamp filter. The earlier P1 result of 195 messages was marked incomplete due to timeout; the new result **independently establishes that W1 truly contains 195 total journal entries**. W2 contains 191. There is no longer a full-journal access or enumeration gap for these time windows.

The simultaneous guest/host block-I/O series also completed two matched 120-second windows, and a separate 45-second host QEMU attribution sample identified the physical server's principal VM contributor. It shows the fundamental distinction between **journald as writer** and **services as journal-message producers**, and between guest block I/O and actual HDD I/O.

**Key finding:** During the new matched run, journald issued 754 and 1,209 guest block writes in the two windows, but fingerprint-evidence issued 6,750 and 1,254, respectively. Increased journald writes did **not** track increased physical HDD writes: guest journald writes rose from 754 to 1,209 while physical HDD completed write IOPS fell from 127.39 to 88.74. Thus there is no evidence that message-count suppression alone will fix the observed HDD pressure; in this live high-load state fingerprint evidence/sensor writes warrant independent investigation. That investigation is outside QIO-01J's logging-source change authority.

No log-suppression or application change is pre-approved by this research. The identified candidate actions are **narrow research hypotheses**, contingent on consumer semantics and Tech Lead decision.

## 2. Scope, authorization and pressure exception

**Source contract:** `TASK-QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01` and follow-on `TASK-QIO-01J-SYSADMIN-P2 — Condition-gated full-journal attribution (READ ONLY)`. The original P2 gate required PSI full avg10 <= 5% and some avg10 <=20% in two measurements. That gate was **not met**: at ~23:42 AZST, loadavg `9.33/10.06/10.03`, PSI some avg10 `67.15%` and full avg10 `49.28%`.

**Owner override:** Owner explicitly authorized continuing the investigation despite high load and prioritised completion. Record as `P2_CONTRACT_PRESSURE_GATE=HOLD_IO_PRESSURE; OWNER_OVERRIDE_HIGH_PRESSURE=YES; EXECUTED_READ_ONLY=YES`. The override does **not** retroactively make the P2 pressure gate PASS. Privilege was obtained without user/group changes: the pre-existing session's `sudo -n id -u` returned `0`. Production journald full `--disk-usage` was previously 4.0 GiB-ish while an unprivileged `admin` view showed 2.0G and warned of hidden records; disk usage was **not** used as a logging-rate measure.

During the collection: `systemd-journald.service` and `captive-portal.service` remained active. The historical scan ran at `ionice -c3`, `nice -n19` with a 300-second upper bound; completed in **5.05 s**. The live follow-up journal scan likewise finished in **0.94 s**. Full-archive crawling, raw exports, heavy tracing/profiling and production mutation were avoided.

## 3. Historical journal windows — full privileged coverage

Exact requested **half-open** intervals:

- **W1:** `[2026-10-16 21:56:00, 21:58:00)` AZST = epoch `[1792173360, 1792173480)`.
- **W2:** `[2026-10-16 21:58:00, 22:00:00)` AZST = epoch `[1792173480, 1792173600)`.

The source pass was `sudo -n journalctl -q --no-pager -o json --since=@1792173360 --until=@1792173600`, constrained by `timeout -k 5s 300s`, `ionice -c3` and `nice -n19`. The local streaming aggregator discarded any `__REALTIME_TIMESTAMP >= 1792173600*10^6` and assigned records by exact timestamp to one window only. All text was read/parsed on the VM; **only aggregates left it**.

| Integrity field | W1 | W2 |
|---|---:|---:|
| Full journal records | **195** | **191** |
| UTF-8 `MESSAGE` bytes | **38,219** | **40,798** |
| PRIORITY 6 / INFO | 194 | 190 |
| PRIORITY 5 / NOTICE | 1 | 1 |
| PRIORITY 0–4 / warning or higher | **0** | **0** |
| Earlier unprivileged `admin` count | 126 | 94 |
| Additional records exposed by root, vs earlier reference | **69** | **97** |
| `journalctl` exit | `0` | `0` (one joint process) |
| Aggregator exit | `0` | `0` |
| True EOF, timestamp bound checked | **YES** | **YES** |
| JSON decode errors | **0** | **0** |

**Total:** 386 entries / 79,017 UTF-8 MESSAGE bytes in four minutes. `HIDDEN_VS_RESTRICTED=EXACT_DELTA_AGAINST_RECORDED_PRIOR_WINDOW_COUNTS` (166 entries altogether), conditional on the previous restricted captures covering their full accessible subset and unchanged journal history; no 2nd unprivileged full scan was performed just to repeat those already documented baselines. Unknown/kernel-only entries are not silently double-counted. `KERNEL=0`, `UNKNOWN=0` in this captured sample; system events without `_SYSTEMD_UNIT` use `SYSLOG_IDENTIFIER` fallback.

### 3.1 Full producer counts and MESSAGE byte volumes

The requested TOP-30 is actually the **complete set of 14 distinct producer labels** across W1+W2. A zero means absent in that specific window; no other producers were found.

| Producer | W1 entries | W2 entries | 4-min total | 4-min MESSAGE bytes |
|---|---:|---:|---:|---:|
| `captive-portal.service` | 72 | 41 | **113** | 11,400 |
| `fingerprint-evidence.service` | 40 | 37 | **77** | **20,475** |
| `snap.microk8s.daemon-kubelite.service` | 35 | 36 | **71** | **19,022** |
| `cron.service` | 17 | 18 | **35** | 2,502 |
| `snap.microk8s.daemon-containerd.service` | 3 | 20 | **23** | 4,505 |
| `init.scope` | 7 | 12 | **19** | 1,483 |
| `traffic-projection.service` | 7 | 10 | **17** | **11,346** |
| `fingerprint-classification.service` | 7 | 6 | **13** | 1,928 |
| `fingerprint-sensor.service` | 6 | 4 | **10** | 5,845 |
| `systemd-logind.service` | 0 | 3 | 3 | 113 |
| `ssh.service` | 0 | 2 | 2 | 197 |
| `SYSLOG:CRON` | 1 | 0 | 1 | 52 |
| `user@0.service` | 0 | 1 | 1 | 96 |
| `SYSLOG:sshd` | 0 | 1 | 1 | 53 |
| **TOTAL** | **195** | **191** | **386** | **79,017** |

W1 INFO=194, NOTICE=1; W2 INFO=190, NOTICE=1. Non-INFO/NOTICE messages absent in this historical window **does not prove** there are no real operational errors: a service may log an error-like text at INFO.

### 3.2 Top producers' sanitized event/template breakdown

No route path, client identifier, message text or query string was returned. Template IDs are ephemeral SHA-256 digest prefixes of in-memory normalized text/type labels; grouping is descriptive, not a cryptographic attestation of equal raw messages.

| Unit | Sanitized type / template | W1 | W2 | Total | Risk/semantics |
|---|---|---:|---:|---:|---|
| captive-portal | `HTTP_ACCESS:GET:200` | 48 | 22 | **70** | HTTP request actually handled; cannot equate to harmless no-op (may include CAPPORT/auth) |
| captive-portal | `HTTP_ACCESS:GET:304` | 4 | 2 | **6** | Not-modified HTTP response; access audit/consumer needs review |
| captive-portal | `HTTP_ACCESS:POST:204` | 5 | 6 | **11** | Successful request, side effects/contract unknown; preserve |
| fingerprint-evidence | `HTTP_ACCESS:POST:200` | 18 | 17 | **35** | Ingest/API access; useful for tracing unless separately proven redundant |
| fingerprint-evidence | `device_fingerprint_ingest_completed:POSITIVE_INSERT` | 12 | 12 | **24** | Real inserted records; preserve |
| fingerprint-evidence | `device_fingerprint_ingest_completed:ALL_DUPLICATE` | 3 | 3 | **6** | Received duplicates, zero inserted; potential no-op outcome |
| fingerprint-evidence | `device_fingerprint_ingest_duplicate` | 3 | 3 | **6** | Extra explicit duplicate notification; potential overlap with preceding six |
| fingerprint-evidence | `device_fingerprint_source_health_completed:POSITIVE_INSERT` | 3 | 2 | **5** | Source health insert; preserve |
| fingerprint-evidence | `device_fingerprint_retention_completed` | 1 | 0 | 1 | Operational retention; preserve |
| microk8s kubelite | recurrent same-class unclassified template | 18 | 18 | **36** | Stable recurring INFO message; exact operational meaning remains unclassified |
| microk8s kubelite | two stable retry/error-word templates | 17 | 16 | **33** | Contains error-like and retry/backoff language but PRIORITY=INFO; potential service issue, **not** safe to suppress |
| microk8s kubelite | additional `failed-to` class | 0 | 1 | **1** | Possible operational failure; no suppression |
| cron | regular INFO units | 17 | 18 | **35** | Cron/maintenance provenance must be preserved |
| traffic-projection | `traffic_projection_product_health` | 3 | 4 | **7** | Product health evidence; not proven no-op |
| traffic-projection | `traffic_projection_worker_source_unavailable` | 2 | 1 | **3** | Important unavailable condition; preserve |
| traffic-projection | `traffic_projection_stale` | 1 | 1 | 2 | Important freshness degradation; preserve |
| traffic-projection | `traffic_projection_scan_failed` | 1 | 0 | 1 | Functional failure; preserve |
| traffic-projection | `traffic_projection_reconcile_completed` | 0 | 4 | 4 | Candidate to inspect for unchanged state, not yet classified |
| fingerprint-sensor | `fingerprint_delivery_retry` | 4 | 0 | 4 | Retry/error awareness; preserve |
| fingerprint-sensor | `fingerprint_sensor_metrics` | 2 | 0 | 2 | Periodic metrics, consumer review required |

The list above covers salient types of the top producers; the complete raw-source messages were kept local and not exported. `init.scope` and minor units have no evidence of safe no-op. In the full historical sample no `_SYSTEMD_UNIT`/`SYSLOG_IDENTIFIER` fallback double-counting occurred.

### 3.2a Top-five template evidence — exact counts, MESSAGE bytes and severity

For the five largest units in each window, all entries were assigned to a producer. The following breakdown provides representative **stable template groups**, and the residual is explicitly identified rather than silently dropped. Counts and bytes are from the complete parsed journal, not estimates. Except the specified `cron` notice, every row in these groups had journal priority `6` (INFO).

| Producer/template group | W1 count / bytes | W2 count / bytes | Priority / caution |
|---|---:|---:|---|
| captive-portal HTTP GET 200 | 48 / 4,390 | 22 / 2,082 | INFO; auth/CAPPORT semantics unknown |
| captive-portal HTTP GET 304 | 4 / 368 | 2 / 184 | INFO; request audit still relevant |
| captive-portal HTTP POST 204 | 5 / 470 | 6 / 564 | INFO; effect not established |
| captive-portal remainder, other text/events | 15 / 1,759 | 11 / 1,583 | INFO; not classified safe to remove |
| fingerprint-evidence HTTP POST 200 | 18 / 2,049 | 17 / 1,931 | INFO |
| fingerprint-evidence ingest completed, positive insert | 12 / 4,900 | 12 / 4,904 | INFO; real work |
| fingerprint-evidence ingest completed, all duplicate | 3 / 1,227 | 3 / 1,227 | INFO; zero insert |
| fingerprint-evidence extra ingest duplicate event | 3 / 933 | 3 / 933 | INFO; consumer audit |
| fingerprint-evidence source health, positive insert | 3 / 1,236 | 2 / 824 | INFO |
| fingerprint-evidence retention | 1 / 311 | 0 / 0 | INFO |
| kubelite repeating INFO/unclassified stable signature | 18 / 2,520 | 18 / 2,520 | INFO; semantic UNKNOWN |
| kubelite retry/error-text signature A | 9 / 3,960 | 7 / 3,080 | INFO; operationally relevant until proven otherwise |
| kubelite retry/error-text signature B | 8 / 2,960 | 9 / 3,330 | INFO; operationally relevant until proven otherwise |
| kubelite residual including `failed-to` occurrence | 0 / 0 | 2 / 652 | INFO; incident-first |
| cron, all messages (multiple templates) | 17 / 1,225 | 18 / 1,277 | INFO: 16/17, NOTICE: 1/1 respectively |
| fingerprint-classification (W1 TOP5), all unclassified text | 7 / 1,027 | 6 / 901 | INFO; no safe suppress claim |
| microk8s containerd (W2 TOP5), diverse one-off text | 3 / 677 | 20 / 3,828 | INFO; includes trigger-word `warning`, not a PRIORITY=WARNING event |

**Interpretation:** The W1 fifth-ranked `fingerprint-classification` and W2 fifth-ranked `cron` have been included, as have W2 fourth-ranked `containerd` and W1 fourth-ranked `cron`. `TEMPLATE_ID` samples for each major class were already hashed in-memory; no potentially sensitive raw message text was exported. Aggregating a whole unit into an `unclassified` template family does *not* imply that its messages are semantically identical.

### 3.3 Three concrete repetitive patterns for Tech Lead consideration

1. **Portal HTTP access logs:** 87 entries / 240 sec (70 GET 200, 6 GET 304, 11 POST 204). No guarantee that the routes are harmless or redundant: CAPPORT/auth/accountability and Loki/Grafana consumers may depend on them. **Classification: CANDIDATE_ONLY / NO SUPPRESSION GO.**
2. **MicroK8s kubelite recurring templates:** 36 recurring INFO/unclassified entries plus 33 retry/error-word entries and one failed-to pattern / 240 sec. Errors may be logged at INFO. These are **potential incident signals**, not routine success noise until diagnostics prove otherwise. **Classification: INCIDENT-REVIEW-FIRST / NO SUPPRESSION GO.**
3. **Fingerprint duplicate outcome telemetry:** six `ingest_completed` records with `inserted=0, duplicate_noop>0`, plus six dedicated `ingest_duplicate` messages / 240 sec (12 journal entries representing six duplicate-only outcomes if pairing verified under accepted code semantics). Plausible narrow source-side de-duplication of *extra* message after downstream consumer audit, but historical magnitude is small and cannot explain QUIET-01 journald 1,982 block writes / 120sec. **Classification: CONSUMER-AUDIT-REQUIRED / NO SUPPRESSION GO.**

`SINGLE_SOURCE_SIDE_HARMLESS_NOOP=NOT_PROVEN`: none of these is yet an authorized, consumer-safe logging change. Failed, stale, authentication, audit, source-health transitions, and persisted positive inserts must not be silently removed.

## 4. Matched live journal + guest disk + physical HDD samples

This is the new non-quiet live series, **not** a quiet apples-to-apples repeat of 2026-10-15 QUIET-01. Counters sampled by passive reads only. Two aligned windows were taken at exact absolute UTC boundary times:

- **LIVE1:** `[2026-10-16 19:53:30, 19:55:30)` UTC = `[23:53:30, 23:55:30)` AZST.
- **LIVE2:** `[2026-10-16 19:55:30, 19:57:30)` UTC = `[23:55:30, 23:57:30)` AZST.

Guest time alignment deviations were about 0.06–0.10 s; host boundaries were at the target seconds to ~0.02 s. This is sufficiently aligned for per-window comparisons, **not** syscall-to-block causal attribution.

### 4.1 Complete journal message counts for those exact windows

The bounded privileged `journalctl` live follow-up returned `RC=0`, `TRUE_EOF=True`, zero parse errors; its source query ran in 0.94 s and used the same half-open timestamp exclusion.

| Metric | LIVE1 | LIVE2 |
|---|---:|---:|
| Full journal messages | **170** | **212** |
| MESSAGE UTF-8 bytes | **37,198** | **36,542** |
| Priority 6 / INFO | 167 | 211 |
| Priority 5 / NOTICE | 3 | 1 |
| Priority 0–4 | 0 | 0 |
| fingerprint-evidence | 62 | 26 |
| microk8s kubelite | 39 | 37 |
| microk8s containerd | 2 | 45 |
| cron | 32 | 18 |
| captive-portal | 8 | 9 |
| fwupd-refresh | 0 | 49 |
| network-metadata `health_heartbeat` | 2 | 4 |

Second window included a **burst of 49 `fwupd-refresh` messages**: a maintenance/event spike; do not treat it as a reproducible steady-state per-minute rate. MicroK8s retry/error-word categories continued. `fingerprint-evidence` LIVE1 recorded positive inserts and duplicate-only outcomes; LIVE2 recorded source-health and duplicate signals. `health_heartbeat` messages did not prove unchanged state or lack of consumers.

### 4.2 Guest block I/O (`/dev/vda`; journald `io.stat`)

**Do not sum** `252:0` and `253:0`, which represent layered accounting of the same logical guest I/O. The table uses **252:0 only**.

| Guest metric | LIVE1 / 120s | LIVE2 / 120s |
|---|---:|---:|
| Completed `/dev/vda` write IOPS | **111.50** | **72.26** |
| `/dev/vda` write KiB/s | 1,074.36 | 709.00 |
| `/dev/vda` write await | **497.74 ms** | **169.29 ms** |
| `/dev/vda` busy | 85.41% | 62.24% |
| Guest CPU iowait | 34.40% | 19.08% |
| journald cgroup wios | **754** | **1,209** |
| journald cgroup wbytes | 3,416,064 | 5,427,200 |
| journald wios/s | **6.28** | **10.07** |
| captive-portal cgroup wios | 809 | 1,222 |
| fingerprint-evidence cgroup wios | **6,750** | **1,254** |
| fingerprint-sensor cgroup wios | **2,691** | **650** |
| network-metadata-projection cgroup wios | 268 | 451 |
| microk8s containerd cgroup wios | 32 | 252 |
| microk8s kubelite cgroup wios | 2 | 4 |

The fingerprint-evidence cgroup is the principal observed guest **write-IOPS contributor during LIVE1**; fingerprint-sensor is second among these sampled units. These counters do **not** mean journald is receiving these units' actual SQLite writes: their direct writes are independent of journal-text production. A previous low-workload baseline had fingerprint-evidence at only 13 writes in 120 sec. This mode shift is material and should be handled as a separate I/O investigation, not as journald producer attribution.

### 4.3 Matched host physical disk counters

| Physical `/dev/sda` metric | LIVE1 | LIVE2 |
|---|---:|---:|
| Completed write IOPS | **127.39** | **88.74** |
| Physical write await | **110.54 ms** | **75.50 ms** |
| Physical busy | **85.93%** | **65.00%** |
| Host-local journald cgroup wios (same window) | 491 | 907 |

Host-local journald is distinct from guest `systemd-journald`. Guest cgroup write IOPS cannot be assumed to reach the host HDD one-for-one, due to QEMU, qcow2, filesystem journaling, caching and request merging. The increasing *guest* journal wios (754 → 1,209) while physical HDD completed IOPS fell (127.39 → 88.74) is an especially important counterexample to conflating these layers.

### 4.4 Separate host attribution cross-check, 45 sec, after LIVE2

**2026-10-16 19:58:34.965–19:59:19.966 UTC**, independently sampled the correct **parent QEMU VM scope** `io.stat` on device `8:0`, not just a libvirt emulator child cgroup. The earlier two host samples had correct `/dev/sda` completed-write counts but their QEMU child-cgroup selection reported no per-VM data; that collector limitation is repaired by this separate parent-scope measurement:

| Layer | Writes over 45 s | Write IOPS | `wbytes` |
|---|---:|---:|---:|
| Ubuntu QEMU parent cgroup | **3,257** | **72.38** | 30,183,424 |
| Windows QEMU parent cgroup | 204 | 4.53 | 1,576,960 |
| Host-local journald | 217 | 4.82 | 970,752 |
| Physical HDD `/dev/sda` completed | **3,943** | **87.62** | `await=100.18ms`, busy=63.51% |

These are **not** the same window as LIVE1 or LIVE2 and do not give a mechanically exact additive partition: guest/host/sda accounting has different semantics. They confirm that Ubuntu's VM is a major source of host disk writes in this later window; Windows and host-local journald are separate contributors.

## 5. Evidence index and reproducibility

- **E01 – Privilege/current baseline:** `Ubunt` SSH as `admin`; `sudo -n id -u = 0`, no change of groups, `journalctl --disk-usage` privileged vs restricted prior warning; services `active`. Host date/time confirmed.
- **E02 – Historical full journal:** single `timeout 300s` `ionice -c3 nice -n19 sudo -n journalctl ... -o json` with fixed epochs. Exit `0`, true EOF, 386 valid JSON records, zero decode errors; locally in-memory aggregated; no source messages exported.
- **E03 – Full per-producer/top template ranking:** W1/W2 and 14 unit labels as in §§3.1–3.3; message bytes/severity and coarse sanitized template identifiers.
- **E04 – Guest live counters:** `/proc/diskstats`, `/proc/stat`, `/proc/pressure/io`, `/sys/fs/cgroup/system.slice/<unit>/io.stat`, two 120-second windows at UTC 19:53:30 and 19:55:30; unit `252:0` reported without adding `253:0`.
- **E05 – Host live physical counters:** `/proc/diskstats` on physical `sda` and host-local journald io.stat matched to E04 at 19:53:30 / 19:55:30 UTC.
- **E06 – Live journal:** privileged bounded `journalctl` scan of `[19:53:30,19:57:30)` UTC, success code `0`, true EOF, 170+212 entries, only in-memory classification leaving host.
- **E07 – QEMU scope cross-check:** correct parent paths `/sys/fs/cgroup/machine.slice/*Ubunt.scope/io.stat` and Windows counterpart, `8:0`, 45-second separately bracketed host capture, with simultaneous `/dev/sda`.

The data was not produced by an artificial stress workload. The Owner's high-I/O override is noted in §2. Commands ran read-only; there was no operational intervention to deliberately change the workload.

### 4.5 End-of-investigation service and pressure check

At **2026-10-17 00:03:25 AZST**, after all requested reads, the four sampled services were all still `active`: `captive-portal.service`, `systemd-journald.service`, `fingerprint-evidence.service`, `fingerprint-sensor.service`. Load averages were `3.24 / 4.53 / 6.58`; I/O PSI `some avg10=19.58%`, `full avg10=16.67%`. These numbers are a follow-up snapshot, not a causal claim that the diagnostic commands improved load.

## 6. Handoff / decision gate

```ini
TASK=TASK-QIO-01J-SYSADMIN-P1-FULL-JOURNAL-ATTRIBUTION-01
FOLLOW_ON=TASK-QIO-01J-SYSADMIN-P2-CONDITION-GATED-READONLY
P2_CONTRACT_PRESSURE_GATE=HOLD_IO_PRESSURE
OWNER_OVERRIDE_HIGH_PRESSURE=YES
P2_EXECUTION_SCOPE=AUTHORIZED_READONLY_OWNER_OVERRIDE
PRIVILEGED_FULL_JOURNAL_VISIBILITY=CONFIRMED_ROOT
WINDOW_W1_COMPLETE=YES
WINDOW_W2_COMPLETE=YES
JOURNALCTL_EXIT_W1_W2=0 (single combined bounded pass)
AGGREGATOR_EXIT_W1_W2=0
TRUE_EOF_CONFIRMED_W1_W2=YES
W1_TOTAL_ENTRIES=195
W2_TOTAL_ENTRIES=191
W1_MESSAGE_BYTES=38219
W2_MESSAGE_BYTES=40798
W1_W2_TOP_30_UNITS=ALL_14_LABELS_IN_SECTION_3_1
W1_W2_TOP_5_TEMPLATE_COUNTS_BYTES_SEVERITIES=SECTION_3_2
HIDDEN_VS_RESTRICTED=EXACT_DELTA_AGAINST_RECORDED_BASELINE_WITH_RETENTION_CAVEAT
MICROK8S_ERROR_LIKE_SEMANTICS=RETRY_OR_FAILURE_WORDS_PROVEN__OPERATIONAL_TRUTH_UNVERIFIED
MATCHED_GUEST_IO=MEASURED_2X120S
MATCHED_HOST_PHYSICAL_IO=MEASURED_2X120S
ADDITIONAL_HOST_QEMU_IO=MEASURED_45S_DIFFERENT_WINDOW
RAW_MESSAGE_EXPORTED=NO
PRODUCTION_MUTATION=NO
SAFE_SINGLE_SOURCE_NOOP=NOT_PROVEN
SYSADMIN_EVIDENCE_STATUS=COMPLETE_FOR_REQUESTED_WINDOWS_AND_CROSS_LAYER_COUNTERS
ROOT_CAUSE=NOT_CONCLUDED_BY_SYSADMIN
CODER=HOLD_PENDING_TECH_LEAD_CONSUMER_AND_SEMANTIC_REVIEW
NEXT=TECH_LEAD_REVIEW
```

**Specific Tech Lead review priorities:** (1) audit Loki/Grafana and any audit/auth/health consumers before touching portal HTTP access or fingerprint duplicate messages; (2) investigate MicroK8s retries as possible incident signals rather than noise; (3) treat unusually high fingerprint-evidence and fingerprint-sensor **direct block writes** as separate QIO/performance causes; (4) ensure one selected source-level hypothesis has a measurable physical-disk effect and explicit roll-back before issuing a lab Coder TASK. The SysAdmin evidence gate for the two specified historical windows and two matched current samples is now fully collected, with remaining **semantic** approvals properly owned by Tech Lead.
