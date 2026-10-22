# Omada AP Status Semantics Research Report

**Project:** CaptivPortal  
**Task:** `TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01`  
**Phase:** R — controlled live research  
**Technical outcome:** **A. VERIFIED — stable raw offline code; pure shared mapper is sufficient**  
**Formal acceptance:** pending Owner + Tech Lead acceptance  
**Research date:** 2026-08-28 (Asia/Baku); evidence timestamps are UTC.

---

## 1. Environment

Production research was performed read-only except for controlled PoE removal from AP2.

No CaptivPortal code, Current State schema, Observation configuration, polling cadence, retention, SSID, VLAN, captive portal, client authorization, or Omada Site configuration was changed.

```text
Timezone=Asia/Baku
NTP=yes
NTPSynchronized=yes

deployed HEAD:
bc929dbe7c1687415bd4eeda971dcbc9376d8bbc

Current State DB:
/opt/CaptivePortal/data/current_state.sqlite3

Current State schema_version:
1
```

The deployed HEAD matches the exact baseline named by the FINAL task.

---

## 2. Controller / AP versions

```text
Omada Software Controller: 5.14.32.3
Controller: https://192.168.0.222:8043
Omada ID: fe6867ddf84e4c18c4e280e984e4266d

Site: Home
Site ID: 6a64f17630da7c70d232187a
Region: Azerbaijan
Timezone: Asia/Baku
```

Test object:

```text
AP-2
MAC: DC-62-79-1B-4A-68
IP: 192.168.0.60
Model: EAP613(EU) v1.0
Firmware: 1.8.3 Build 20260617 Rel. 36045
Serial: 22487X1000729
```

AP1 was not disrupted.

---

## 3. API / endpoint used

Direct research sampling used:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/devices
```

AP2 was selected by exact MAC.

---

## 4. Inventory completeness

Each direct sample used paginated inventory retrieval and was accepted only when all pages were complete.

Observed Site inventory:

```text
inventory_total_rows=2
rows_received=2
inventory_complete=True
AP rows=2
```

During accepted outages:

```text
inventory_complete=True
AP2 present=True
```

Therefore physical power loss does **not** remove AP2 from Omada inventory.

---

## 5. Online baseline

Repeated healthy samples produced:

```text
raw status=1
AP present=True
inventory_complete=True
```

Current State independently persisted:

```text
status_code=1
status_classification=online
```

No stable online baseline contained raw `0`.

**Conclusion:**

```text
raw 1 = online
```

VERIFIED.

---

## 6. Run #1

Run #1 was exploratory supporting evidence only.

It showed:

```text
1 → 3 → 0 → 1
```

but only one authoritative Current State `status_code=0` cycle was retained before recovery.

Therefore Run #1 is not used as one of the two strict Outcome A acceptance runs.

---

## 7. Accepted outage Run #2

Direct sequence:

```text
1 → 3 → 0
```

Relevant direct timestamps:

```text
first POWER_OFF-phase sample: 2026-08-27T21:38:59.140Z
first raw=3:                  2026-08-27T21:39:29.140Z
first raw=0:                  2026-08-27T21:48:29.153Z
```

The precise Run #2 power-off marker is not printed in the retained text excerpt, so latency is reported as bounded/approximate.

AP2 remained present in complete inventory and `lastSeen` froze at:

```text
1787866696034
```

Authoritative Current State complete-success offline cycles:

```text
2026-08-27T21:48:50.839Z  status=0  class=other
2026-08-27T21:49:51.311Z  status=0  class=other
2026-08-27T21:50:55.350Z  status=0  class=other
2026-08-27T21:51:58.735Z  status=0  class=other
2026-08-27T21:52:58.993Z  status=0  class=other
```

All were:

```text
result=success
complete=1
reported=2
seen=2
stored=2
```

This exceeds the strict requirement for two consecutive authoritative outage cycles.

---

## 8. Recovery Run #2

Operator reported PoE restoration at approximately 21:52 UTC.

First direct recovered online sample:

```text
2026-08-27T21:53:49.161Z
raw=1
```

Current State recovery:

```text
2026-08-27T21:54:00.026Z  status=1  class=online
2026-08-27T21:55:00.565Z  status=1  class=online
2026-08-27T21:56:02.978Z  status=1  class=online
```

Run #2 therefore independently reproduced stable offline `0` and recovered online `1`.

---

## 9. Accepted outage Run #3

Run #3 used exact host-side phase markers:

```text
Start UTC:     2026-08-27T22:04:58.384Z
Power OFF UTC: 2026-08-27T22:06:58.426Z
Power ON UTC:  2026-08-27T22:21:58.511Z
Finish UTC:    2026-08-27T22:25:58.565Z
```

Baseline remained:

```text
complete=True
present=True
raw=1
```

Last direct `1` after power removal:

```text
2026-08-27T22:07:38.431Z
```

First direct `3`:

```text
2026-08-27T22:07:48.554Z
```

Thus `1 → 3` occurred within:

```text
40.005 s < latency <= 50.128 s
```

Last direct `3`:

```text
2026-08-27T22:16:48.490Z
```

First direct `0`:

```text
2026-08-27T22:16:58.386Z
```

Thus stable offline `0` appeared within:

```text
590.064 s < latency <= 599.960 s
```

after physical power removal, approximately 9m50s–10m00s.

Direct `0` then remained stable through the power-on marker, for roughly five minutes.

Authoritative Current State complete-success offline cycles included:

```text
2026-08-27T22:17:28.586Z  status=0  class=other
2026-08-27T22:18:29.673Z  status=0  class=other
2026-08-27T22:19:30.156Z  status=0  class=other
2026-08-27T22:20:30.443Z  status=0  class=other
2026-08-27T22:21:30.786Z  status=0  class=other
```

All occurred after physical power loss and before restore initiation.

---

## 10. Recovery Run #3

Power restored:

```text
2026-08-27T22:21:58.511Z
```

AP2 stayed raw `0` while booting/reconnecting.

Last direct `0`:

```text
2026-08-27T22:24:28.558Z
```

First direct recovered `1`:

```text
2026-08-27T22:24:38.435Z
```

Recovery transition occurred within:

```text
150.047 s < latency <= 159.924 s
```

after power restoration, approximately 2m30s–2m40s.

Current State recovery:

```text
2026-08-27T22:24:31.810Z  status=1  class=online
2026-08-27T22:25:32.128Z  status=1  class=online
```

---

## 11. Transition status

During the physical outage the operator observed Omada UI:

```text
ПРОПУЩЕНО СООБЩЕНИЕ HEARTBEAT
```

at the same time the direct API sampler showed:

```text
raw status=3
```

Therefore raw `3` is a missed-heartbeat / transition state, not the final offline code.

Recommended canonical treatment:

```text
raw 3 → other
```

---

## 12. Additional reboot / uplink tests

Not performed.

They were optional and are not required to prove the physical power-loss semantics established here.

No reboot/uplink-specific inference is made.

---

## 13. Evidence correlation

| Ground truth | Direct inventory | Raw | Current State | Canonical |
|---|---|---:|---|---|
| Stable healthy | complete, present | `1` | `1 / online` | online |
| Loss detection | complete, present | `3` | `3 / other` | other |
| Stable physical power loss | complete, present | `0` | repeated `0 / other` | offline |
| Boot/reconnect | complete, present | `0` until ready | may remain `0` | offline until controller reports online |
| Stable recovered | complete, present | `1` | `1 / online` | online |

`lastSeen` freezes during unavailability and resumes on recovery, but it is supporting evidence only.

A compound `status + lastSeen` heuristic is not required by the observed behavior.

---

## 14. Final Outcome

# A. VERIFIED

Two strict independent accepted runs are:

```text
Run #2
Run #3
```

Both demonstrate:

```text
stable online raw status  = 1
stable offline raw status = 0
transition raw status     = 3

AP remains present in complete inventory.
```

Both accepted outage runs contain multiple direct stable `0` samples and multiple complete-success Current State cycles with raw `status_code=0`.

Both recoveries return to complete-success Current State `status_code=1`.

No stable online baseline contained raw `0`.

No source/inventory failure was classified as AP outage.

**Technical Phase R conclusion:**

```text
A. VERIFIED — stable raw offline code; pure shared mapper is sufficient.
```

Formal TASK acceptance still requires Owner + Tech Lead acceptance of this report.

---

## 15. Recommended canonical interpretation

For the tested compatibility tuple:

```text
Omada Controller 5.14.32.3
EAP613(EU) v1.0
Firmware 1.8.3 Build 20260617 Rel. 36045
Site Home
```

recommended conceptual mapping:

```text
raw status == 1  → online
raw status == 0  → offline
other integer    → other
missing/unusable → unknown
```

Observed `3` remains `other`.

A pure status-code mapper is sufficient.

No schema migration is required because Current State already persists raw:

```text
current_ap_state.status_code
```

Existing historical rows with:

```text
status_code=0
status_classification=other
```

remain usable as raw evidence. No historical DB rewrite is authorized.

Architecture invariants remain:

```text
source failure ≠ AP outage
partial inventory ≠ AP outage
Observation partial ≠ AP outage
unproven numeric status ≠ AP outage
```

---

## 16. Acceptance checklist

| Requirement | Result |
|---|---|
| Two independent complete outage/recovery runs | PASS — Run #2 + Run #3 |
| Complete direct inventories | PASS |
| AP remains present during outage | PASS |
| Same stable offline code repeated | PASS — `0` |
| >=3 direct stable offline samples per accepted run | PASS |
| >=30 s stable offline per accepted run | PASS |
| Stable online before/after | PASS — `1` |
| Offline candidate absent from online baseline | PASS |
| >=2 complete-success Current State offline cycles each run | PASS |
| >=1 complete-success recovered online cycle each run | PASS |
| Production-host NTP evidence | PASS |
| Transition latency documented | PASS |
| No source failure misclassified | PASS |
| No schema/config/cadence mutation | PASS |
| Owner + Tech Lead acceptance | PENDING |

---

## 17. Handoff

Return to Owner / Tech Lead / Architect:

```text
Outcome A — VERIFIED

online  = raw 1
offline = raw 0
raw 3   = transition / missed-heartbeat → other

Powered-off AP remains in complete inventory.
Current State already persists the required raw code.
Pure shared mapper is sufficient.
No schema migration is required by Phase R.
```

This report authorizes no code change or production activation.

Only after Owner + Tech Lead accept Phase R may the separately controlled Phase M mapper work begin.

`TASK-HOME-AP-24H-01` remains blocked until the Phase M mapper artifact is accepted.

---

## Evidence sources

- `TASK-CURRENT-STATE-AP-STATUS-SEMANTICS-01-FINAL.md`
- AP2 direct baseline evidence
- Run #2 direct sampler log
- Production Current State read-only SQL evidence
- Run #3 direct sampler + Current State correlated log
- Production-host NTP / schema / repository precheck
- Operator UI observation correlating raw `3` with «ПРОПУЩЕНО СООБЩЕНИЕ HEARTBEAT»
