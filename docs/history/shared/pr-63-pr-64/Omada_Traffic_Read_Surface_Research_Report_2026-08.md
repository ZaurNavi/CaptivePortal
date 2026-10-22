# Omada Traffic Read Surface Research — Final Report

**Project:** CaptivPortal  
**Research ID:** `TRAFFIC-SOURCE-RESEARCH-01`  
**Area:** Admin Console → Traffic  
**Research:** Omada Traffic Read Surface Audit  
**Status:** **RESEARCH COMPLETE**  
**Implementation authorization:** **NOT GRANTED**  
**Traffic acquisition changes:** **NOT GRANTED**  
**Traffic schema changes:** **NOT GRANTED**  
**Production changes performed by this research:** **NONE**  
**Destructive Omada actions performed by this research:** **NONE**  
**Research window:** 2026-08-28 — 2026-08-29, Asia/Baku  
**Controller:** Omada Software Controller **5.14.32.3**

> Canonical architecture invariant preserved throughout this report:
>
> **acquisition ≠ analytics**
>
> Admin/Browser must read persisted CaptivPortal facts. This research does **not**
> authorize `Admin → Omada` or `Browser → Omada` as a production architecture.

---

# 1. Executive Summary

The research found **no superior native current-traffic primitive that justifies replacing CaptivPortal's existing Observation-based current Network Traffic architecture**.

The strongest result is that CaptivPortal already persists almost all useful current Omada traffic facts independently verified during this audit:

- AP wired uplink counters;
- AP wired activity;
- AP LAN byte/packet/drop/error counters;
- derived AP wired/LAN Mbps;
- per-radio byte/packet/drop/error/retry counters;
- derived radio Mbps;
- client `activity`;
- client `trafficDown` / `trafficUp`;
- client PHY `rxRate` / `txRate`;
- client association/radio/AP/SSID context.

Therefore, for **TRAFFIC-01 current Network Throughput**, the existing persisted path remains canonical:

```text
Omada
→ Observation acquisition
→ persisted AP facts
→ CurrentTrafficReadService / Analytics
→ Admin
```

No direct Site-wide current wireless/AP throughput endpoint was found in public OpenAPI. Omada does expose per-AP current primitives, but those primitives are already represented in CaptivPortal persistence.

The major genuinely new read surface is **Controller-native historical Site Traffic**:

```text
GET .../dashboard/traffic-activities?start=&end=
```

It returns range-aware traffic-volume buckets and automatically changes granularity from 5-minute to hourly, daily and weekly buckets. Its aggregate semantics were live-verified against AP LAN counters.

A native **per-AP historical time series** was not found in public OpenAPI. A per-AP **range aggregate** exists through `traffic-distribution`, but this is not a per-AP time series.

For clients:

- `trafficDown` / `trafficUp` are cumulative bytes for the **current Omada connection**, not lifetime counters for a MAC;
- on finalization, those values are copied exactly into a new `past-connection` record;
- a new connection starts its counters from new low values;
- the stable client object ID remains the same while completed connection records receive separate history IDs.

Client `activity` is a real data-traffic field, but it is only a **downlink point/short-window sample** published through a client snapshot that refreshes roughly every 30 seconds. There is no symmetric native current upload field in the tested public Client Detail contract. `rxRate` and `txRate` are PHY negotiation rates and must not be used as actual throughput.

No trustworthy stable public SSID traffic aggregate was found. No public SSID historical/current Traffic source should be assumed for `Zefer_Parki`.

The final research outcome is therefore a combination of:

- **Outcome A:** existing CaptivPortal traffic acquisition is sufficient for current Traffic;
- **Outcome D:** a useful native historical Site Traffic endpoint exists and should be considered during Historical Traffic architecture design, but it does not by itself justify replacing Observation history or adding a new acquisition path.

---

# 2. Environment

## 2.1 Controller

```text
Product:          Omada Software Controller
Version:          5.14.32.3
Controller URL:   https://192.168.0.222:8043
Omada ID:         fe6867ddf84e4c18c4e280e984e4266d
Site:             Home
Site ID:          6a64f17630da7c70d232187a
Test SSID:        Zefer_Parki
Timezone:         Asia/Baku (+04:00)
```

Authentication for public OpenAPI was performed through OAuth `client_credentials`.
Secrets, tokens, cookies and authorization-header values are intentionally omitted.

## 2.2 Topology boundary

Guest routing and DHCP are provided by **Cisco**, not an Omada Gateway.

Therefore:

- Omada Gateway WAN/DPI/Application Analytics must not be treated as authoritative Site Traffic for this deployment;
- Site Traffic discovered in AP/Monitor surfaces must be interpreted from the AP accounting layer actually observed;
- "Site Traffic" must not be relabeled as "Internet/WAN Traffic" without separate proof.

## 2.3 APs

### AP-1

```text
MAC:       EC-75-0C-18-6F-F8
IP:        192.168.0.50
Model:     EAP613(EU) v1.0
Firmware:  1.8.3 Build 20260617 Rel. 36045
```

### AP-2

```text
MAC:       DC-62-79-1B-4A-68
IP:        192.168.0.60
Model:     EAP613(EU) v1.0
Firmware:  1.8.3 Build 20260617 Rel. 36045
```

## 2.4 Controlled client

```text
MAC:       BE-00-7D-9B-04-2E
SSID:      Zefer_Parki
Latest IP: 192.168.11.163
Latest AP: AP-2 / DC-62-79-1B-4A-68
```

Only the owner's designated device was used for the natural/manual Wi-Fi reconnect test.

---

# 3. Methodology

The research used four evidence layers.

## 3.1 Local public OpenAPI / Swagger inspection

All 13 local Swagger groups were available:

```text
00 All
01 Account
02 Organization
03 Device
04 Site Setting
05 Client
06 Hotspot
07 Monitor
08 Maintenance
09 Insight
10 Msp
11 Log
12 Batch
```

Relevant schemas and GET operations were inspected locally on the actual Controller.

## 3.2 Live read-only API verification

Read-only GET calls were performed against:

- Monitor dashboard traffic endpoints;
- AP LAN/wired/radio endpoints;
- client detail;
- completed client connection history.

No Omada mutation API was used.

## 3.3 Passive / owner-controlled physical traffic tests

Traffic was generated using normal client activity, including Plex playback on the designated phone.

A manual Wi-Fi off/on cycle on the owner's device was used to determine client counter lifetime. No administrative reconnect endpoint was used.

## 3.4 CaptivPortal persisted-source inspection

Production SQLite databases were opened **read-only** and schemas/current rows were inspected for Observation, Current State and Visit-related traffic facts.

No database data or schema was modified.

---

# 4. Site Traffic

## 4.1 R1 — Site-level instantaneous throughput

**Result:** no direct native Site-wide current wireless/AP throughput endpoint was found in public OpenAPI 5.14.32.3.

The Monitor schema contains current/rate-like values in other domains, including Gateway/WAN usage, but those are not authoritative for this topology because Cisco, not an Omada Gateway, provides guest routing.

The Site Traffic endpoint found under Monitor:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/dashboard/traffic-activities
    ?start={unix_seconds}
    &end={unix_seconds}
```

is a **historical/range bucket volume endpoint**, not an instantaneous rate endpoint.

### Implication

The current CaptivPortal Site Traffic path remains preferable:

```text
persisted AP rates
→ CurrentTrafficReadService
→ Site aggregate
```

A Site current value could theoretically be constructed from native per-AP current values, but direct runtime aggregation from Omada would merely recreate logic already implemented against persisted facts and would violate the preferred acquisition/read separation if done from Admin.

### R1 verdict

```text
Direct native Site current wireless/AP throughput:
F — unavailable / not found
```

Architecture recommendation:

```text
REUSE EXISTING PERSISTED FACT
```

---

# 5. AP Traffic

## 5.1 R2 — Native AP current wired traffic

### Endpoint

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/wired-uplink
```

Relevant runtime/schema fields include:

```text
upBytes
downBytes
upPackets
downPackets
activity
rate
duplex
```

Swagger describes `activity` as:

```text
Change of (downBytes + upBytes) / time
```

in Bytes/s.

### Live behavior

Polling every 2 seconds showed that the Controller published new effective snapshots approximately every 30 seconds.

Examples after excluding an initial partial interval:

```text
counter-derived total avg: 0.817 Mbps
activity:                  0.847 Mbps

counter-derived total avg: 0.182 Mbps
activity:                  0.182 Mbps

counter-derived total avg: 0.068 Mbps
activity:                  0.066 Mbps
```

This supports:

```text
wiredUplink.activity
= Controller-derived interval average
  of aggregate wired UP + DOWN bytes
```

It is not a PHY rate.

Directional current Mbps is not directly exposed by this endpoint; directional rates must be derived from directional counter deltas, which CaptivPortal already does.

## 5.2 AP LAN traffic

### Endpoint

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/lan-traffic-info
```

Relevant fields:

```text
rx
tx
rxPkts
txPkts
rxDrops
txDrops
rxErrors
txErrors
```

Live comparison established, for synchronized samples:

```text
wired upBytes   == LAN tx
wired downBytes == LAN rx
wired upPackets == LAN txPkts
wired downPackets == LAN rxPkts
```

Observed direction:

```text
AP LAN RX = wired DOWN
AP LAN TX = wired UP
```

## 5.3 AP radio traffic

### Endpoint

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/radios
```

Per-radio data includes:

```text
rxBytes
txBytes
rxPackets
txPackets
rxDropPackets
txDropPackets
rxErrorPackets
txErrorPackets
rxRetryPackets
txRetryPackets
```

The radio counters are separate accounting facts from AP Ethernet/LAN counters.

A 180-second low-traffic AP-1 interval showed:

```text
LAN RX   +206,879 B
LAN TX   +131,097 B
RADIO RX +210 B
RADIO TX +6,966 B
```

Thus LAN and radio counters are not interchangeable duplicates.

## 5.4 Controlled client cross-layer direction test

During approximately 180 seconds of Plex playback through AP-2:

```text
CLIENT DOWN +73,369,368 B
CLIENT UP   + 2,110,550 B

RADIO TX    +72,038,832 B
RADIO RX    + 2,064,024 B

LAN RX      +72,426,709 B
LAN TX      + 2,339,880 B
```

Ratios:

```text
RADIO TX / CLIENT DOWN = 0.9819
RADIO RX / CLIENT UP   = 0.9780
RADIO TX / LAN RX      = 0.9946
RADIO RX / LAN TX      = 0.8821
```

The data experimentally supports:

```text
Internet/LAN
→ AP LAN RX
→ AP RADIO TX
→ client DOWN
```

and:

```text
client UP
→ AP RADIO RX
→ AP LAN TX
→ LAN/Internet
```

Small differences are expected because the accounting layers are not sampled atomically and include different protocol/service overheads.

## 5.5 R6 — AP historical traffic

No public per-AP historical **time-series** endpoint was found in the Device, Client or Monitor OpenAPI surfaces.

A per-AP **range aggregate** does exist:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/dashboard/traffic-distribution
    ?start=
    &end=
```

Therefore:

```text
Per-AP range aggregate: VERIFIED
Per-AP historical time series: NOT FOUND
```

---

# 6. Client Traffic

## 6.1 Client Detail

### Endpoint

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}
```

Important fields include:

```text
rxRate
txRate
activity
trafficDown
trafficUp
uptime
lastSeen
active
ssid
apName
apMac
radioId
channel
```

## 6.2 PHY rate vs actual traffic

Swagger semantics:

```text
rxRate = wireless uplink negotiation rate, Kbit/s
txRate = wireless downlink negotiation rate, Kbit/s
```

These are link/PHY rates, not application traffic throughput.

Live examples showed high `txRate` while `activity=0`.

Therefore:

```text
rxRate / txRate
must NOT be used as actual client traffic throughput
```

## 6.3 Client `activity`

Swagger identifies `activity` as real-time downlink traffic in Bytes/s.

Live testing found:

- Controller client snapshot values are published roughly every 30 seconds;
- `activity` does not equal the average counter delta over that entire publication interval;
- it can be 0 during sustained transfer;
- it can spike strongly at a snapshot moment;
- there is no symmetric `uploadActivity` field in the tested Client Detail contract.

During continuous Plex traffic:

```text
activity sample:          2.628 Mbps
counter avg down:         4.254 Mbps

activity sample:          0 Mbps
counter avg down:         5.478 Mbps

activity sample:          0.077 Mbps
counter avg down:         5.583 Mbps

activity sample:          22.972 Mbps
counter avg down:         3.632 Mbps
```

Conclusion:

```text
client activity
= point/short-window actual DOWNLINK sample
  carried in a ~30 s-published Controller client snapshot
```

It is not a symmetric bidirectional current-throughput contract.

## 6.4 R4 — Client traffic counter lifetime

Baseline before physical disconnect:

```text
client object id: 6a68d829b44c923b94931762
uptime:           1237 s
trafficDown:      655,714,003 B
trafficUp:         21,480,531 B
IP:               192.168.11.163
```

After the phone's Wi-Fi was manually turned off, the Controller continued returning a frozen current client object for several minutes:

```text
active=True
uptime=1237
trafficDown=655714003
trafficUp=21480531
```

When Controller finalization occurred, the current client became offline and a new `past-connection` record appeared:

```text
history id:  6a920b0bb2e4d67c5d27ff4e
download:    655,714,003 B
upload:       21,480,531 B
duration:    1237 s
firstSeen:   1787954414236
lastSeen:    1787955651778
IP:          192.168.11.163
SSID:        Zefer_Parki
deviceName:  AP-2
```

The values match exactly:

```text
live trafficDown == history download
live trafficUp   == history upload
live uptime      == history duration
live lastSeen    == history lastSeen
```

After Wi-Fi was enabled again, the same client object ID returned with a new connection:

```text
client object id: 6a68d829b44c923b94931762
uptime:           35 s
trafficDown:      6,035,752 B
trafficUp:          663,768 B
IP:               192.168.11.163
```

### R4 conclusion

`trafficDown` and `trafficUp` are cumulative byte counters for the **current Omada connection**. They are **not lifetime MAC counters**.

On connection finalization:

```text
trafficDown → past-connection.download
trafficUp   → past-connection.upload
uptime      → past-connection.duration
```

A new connection starts new counters.

The client object ID remained stable across the reconnect, while each completed connection receives its own history-record ID.

## 6.5 Offline freshness caveat

The client remained `active=true` with a frozen snapshot for more than five minutes after physical Wi-Fi disconnect.

At the final watch, `lastSeen` age was approximately 334.3 seconds before the Controller published `active=false` and created the history row.

Therefore:

```text
active=true
is not proof of immediate physical connectivity
```

and `active=false` timing must not be treated as an exact radio disconnect timestamp.

---

# 7. SSID Traffic

## 7.1 Public OpenAPI search

The public/local Swagger surfaces provide SSID configuration, client SSID attributes and SSID client distribution, but no stable public Traffic endpoint was found for:

```text
SSID current throughput
SSID historical throughput
SSID traffic volume series
```

Broad searches across Swagger groups and candidate UI-style names did not expose a public SSID traffic operation.

## 7.2 UI/private research

Controller JS assets were searched for candidate SSID traffic request names. No stable direct contract was recovered.

Earlier DevTools attempts did not produce a trustworthy reusable private endpoint, and further low-value private-API chasing was intentionally stopped.

### R9 verdict

```text
Trustworthy stable SSID-level Traffic:
F — unavailable / not found
```

Architecture recommendation:

```text
DO NOT USE
```

unless a future dedicated research task verifies a stable source.

---

# 8. Historical Traffic

## 8.1 R5 — Native Site historical Traffic

### Endpoint

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/dashboard/traffic-activities
    ?start={unix_seconds}
    &end={unix_seconds}
```

Runtime rows were observed as:

```json
{
  "time": 1787955000,
  "txData": 131.93,
  "dxData": 5.21
}
```

Important runtime/schema divergence:

```text
Swagger: rxData
Runtime: dxData
```

## 8.2 Units

Swagger describes traffic volume in MB.

Cross-endpoint comparisons showed binary-style conversion consistency:

```text
wifi-summary.totalTraffic / 1024
≈ traffic-activities MB
```

and:

```text
traffic-distribution MB / 1024
≈ most-active-eaps GB
```

The observed behavior is consistent with 1024-based unit scaling despite MB/KB/GB labels.

## 8.3 One-hour Site history example

12 five-minute AP buckets:

```text
sum txData = 1190.27 MB
sum dxData =  245.95 MB
total      = 1436.22 MB
```

Same interval via `traffic-distribution`:

```text
AP-1 = 957.34 MB
AP-2 = 478.86 MB
total = 1436.20 MB
```

Same interval via `wifi-summary.totalTraffic`:

```text
1,470,671.53 KB
/ 1024
= 1436.2027 MB
```

The three Monitor projections therefore describe the same underlying Site/AP traffic volume, subject to rounding.

## 8.4 Automatic historical granularity

Live range-threshold tests established the following observed contract on Controller 5.14.32.3:

```text
up to at least 26 hours        → 5-minute buckets
27 hours through 170 hours     → hourly buckets
171 hours through 120 days     → daily buckets
121 days and above             → weekly buckets
```

The boundaries above were tested at integer-hour/day ranges. Exact minute/second transitions were intentionally not pursued.

## 8.5 Aggregation conserves traffic volume

A 120-day request returned daily points:

```text
points:      120
populated:    35
txData:      625,685.98 MB
dxData:      218,149.04 MB
total:       843,835.02 MB
```

A 121-day request returned weekly points:

```text
points:       18
populated:     5
txData:      625,685.98 MB
dxData:      218,149.04 MB
total:       843,835.02 MB
```

The values were identical to 0.01 MB.

Therefore the granularity transition changes temporal resolution, not traffic-volume semantics.

## 8.6 Empty bucket behavior

Long-range requests may return timestamp-only rows:

```json
{
  "time": 1780257600
}
```

with no traffic values.

Examples:

```text
90-day request:
  90 buckets
  35 populated
  55 empty

180-day request:
  26 weekly buckets
   5 populated
  21 empty

365-day request:
  53 weekly buckets
   5 populated
  48 empty
```

Critical rule:

```text
missing txData/dxData != zero traffic
```

A missing value means no traffic value is present for that bucket. A future reader must not silently convert missing data into zero.

## 8.7 Actual populated history in this Controller

The earliest populated daily bucket found in the 90-day query was:

```text
2026-07-25 20:00:00 UTC
2026-07-26 00:00:00 Asia/Baku
```

This does **not** prove a fixed retention limit.

The Controller accepted requests up to at least 365 days and padded earlier periods with empty buckets, but the research environment did not contain older populated traffic values.

Therefore:

```text
API range capability: at least 365 days observed
actual retention policy: NOT VERIFIED
```

## 8.8 R6 — AP history

`traffic-distribution` provides per-AP total volume over a selected range, but no public per-AP time-series endpoint was found.

## 8.9 R7 — Client history

### Endpoint

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/insight/past-connection
```

The test MAC had 55 completed connection rows before the R4 test and 56 after finalization.

Historical rows include:

```text
id
mac
download
upload
duration
firstSeen
lastSeen
ssid
deviceName
ip
guest
```

This is **completed connection history**, not client throughput-over-time.

The current active connection is absent until it is finalized.

Observed history for the test MAC extended back to at least 2026-07-30. Exact retention policy was not determined.

`deviceName` is not an immutable AP identity; historic rows for the same client showed both an AP display name and an older MAC-like value.

---

# 9. Traffic Counter Semantics

## 9.1 AP Ethernet counters

```text
LAN RX = wired DOWN
LAN TX = wired UP
```

These are cumulative AP Ethernet counters.

## 9.2 Radio counters

Radio RX/TX are cumulative counters for the radio accounting layer and are not numerically identical to AP Ethernet counters.

## 9.3 Site historical direction

A controlled approximately 10-minute comparison produced:

```text
Σ AP LAN RX = 396,618,948 B
Σ AP LAN TX =  14,206,917 B
```

Site bucket total after observed unit conversion:

```text
traffic txData ≈ 405,977,170 B
traffic dxData ≈  13,767,803 B
```

Ratios:

```text
AP LAN RX / Site txData = 0.9769
AP LAN TX / Site dxData = 1.0319
```

The small mismatch is consistent with comparing arbitrary live-counter window boundaries against fixed Omada bucket boundaries.

Observed semantic mapping:

```text
traffic-activities.txData
≈ sum of AP LAN RX
≈ traffic delivered toward wireless clients

traffic-activities.dxData
≈ sum of AP LAN TX
≈ traffic received from wireless clients
```

Therefore Site `traffic-activities` is an aggregation of the AP Ethernet/LAN-side accounting layer.

It is not evidence of WAN-only, Gateway-only, guest-only or SSID-specific traffic.

## 9.4 Client counters

`trafficDown` and `trafficUp` are per-current-connection cumulative byte counters.

## 9.5 Client `activity`

Actual downlink point/short-window sample, not a full symmetric throughput contract.

## 9.6 PHY rates

`rxRate`, `txRate`, `maxTxRate` and link/port rates are not actual payload throughput.

---

# 10. UI / DevTools Findings

Useful public Monitor projections verified:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
dashboard/wifi-summary
dashboard/most-active-eaps
```

`traffic-distribution` returns AP/switch range traffic in MB plus percentage/proportion.

`wifi-summary.totalTraffic` matched the same Site range traffic after unit conversion. Caveat: the endpoint mixes a range traffic field with other summary fields that may be current-state-like.

`most-active-eaps` returns rounded AP ranking traffic in GB. Both online APs returned `status=0`, proving that this projection's `status` must not be reused as AP inventory status.

No private/internal UI traffic endpoint was adopted as a stable architecture source.

No trustworthy SSID traffic contract was recovered.

---

# 11. Comparison with CaptivPortal Existing Sources

## 11.1 AP Observation persistence

`observations.sqlite3 → ap_observations` persists:

```text
wired_up_bytes
wired_down_bytes
wired_up_packets
wired_down_packets
wired_activity_raw
wired_download_mbps
wired_upload_mbps

lan_rx_bytes
lan_tx_bytes
lan_rx_packets
lan_tx_packets
lan_rx_drop_packets
lan_tx_drop_packets
lan_rx_error_packets
lan_tx_error_packets
lan_rx_mbps
lan_tx_mbps

per-source observed timestamps
rate-quality reasons
```

This is stronger than the original minimum assumption: CaptivPortal already persists not only calculated Mbps but also native wired/LAN raw counters and native wired activity.

Example AP-2 persisted row:

```text
wired_up_bytes   = 1,356,886,129
wired_down_bytes = 8,921,207,098

lan_tx_bytes     = 1,356,886,129
lan_rx_bytes     = 8,921,207,098
```

AP-1 also showed small differences between wired and LAN raw snapshots when the source calls were taken at slightly different timestamps, consistent with asynchronous publication.

## 11.2 Radio Observation persistence

`ap_radio_observations` persists per-band:

```text
band
radio_id
channel/frequency/width
max_tx_rate
tx_power
wireless_mode
utilization fields
rx_bytes
tx_bytes
rx_packets
tx_packets
rx_drop_packets
tx_drop_packets
rx_error_packets
tx_error_packets
rx_retry_packets
tx_retry_packets
radio_rx_mbps
radio_tx_mbps
rate-quality reasons
```

Therefore the native radio accounting layer found during research is already persisted.

## 11.3 Client Observation persistence

`client_observations` persists:

```text
SSID / AP / radio / band / channel context
rx_rate
tx_rate
rssi
snr
uptime
last_seen_ms
auth_status
activity
active
traffic_down
traffic_up
down_packet
up_packet
```

Thus even native client `activity` and PHY rates are already captured.

## 11.4 Current State

`current_state.sqlite3 → current_client_state` persists:

```text
controller_traffic_down
controller_traffic_up
controller_traffic_total
```

plus current context.

## 11.5 Visit Lifecycle

`visits.sqlite3` contains:

```text
reported_traffic_total_bytes
reported_traffic_up_bytes
reported_traffic_down_bytes
```

and source-event traffic evidence.

These facts belong to Visit/guest-session accounting and are **not Network Throughput**.

They must remain semantically separate from AP LAN/radio/current Traffic.

## 11.6 R14 conclusion

The existing CaptivPortal acquisition model already captures the useful native **current** AP/client traffic primitives found in the audit.

The genuinely new native candidates are primarily:

1. Site historical `traffic-activities`;
2. per-AP range aggregate `traffic-distribution`;
3. completed client connection history `past-connection`;
4. duplicate Monitor summary/ranking projections.

None invalidates the current Observation-based Network Traffic architecture.

---

# 12. Source Classification

| Primitive | Evidence / meaning | Classification | Recommendation |
|---|---|---:|---|
| Site direct current wireless/AP throughput | No direct public endpoint found | **F** | **REUSE EXISTING PERSISTED FACT** |
| `dashboard/traffic-activities` | Site AP-traffic volume time series; range-aware buckets | **B** | **CONSIDER ADDING TO EXISTING ACQUISITION** only if Historical Traffic architecture review demonstrates benefit |
| `dashboard/traffic-distribution` | Per-AP range aggregate + proportion | **B** | **RESEARCH FURTHER** before product dependency |
| `wifi-summary.totalTraffic` | Duplicate Site range volume projection in KB | **D** | **DO NOT USE** as canonical source |
| `most-active-eaps.traffic` | Rounded per-AP ranking projection in GB | **C** | **DO NOT USE** as canonical source |
| `most-active-eaps.status` | Projection-specific status, not inventory status | **E** | **DO NOT USE** as AP inventory status |
| AP `wired-uplink` byte counters | AP Ethernet counters | **A** | **REUSE EXISTING PERSISTED FACT** |
| AP `wired-uplink.activity` | Controller interval-average aggregate wired rate | **A** | **REUSE EXISTING PERSISTED FACT** |
| AP `lan-traffic-info` counters | AP Ethernet RX/TX counters | **A** | **REUSE EXISTING PERSISTED FACT** |
| AP `/radios` traffic counters | Per-radio cumulative counters | **A** | **REUSE EXISTING PERSISTED FACT** |
| Client `trafficDown` / `trafficUp` | Current-connection cumulative bytes | **A** | **REUSE EXISTING PERSISTED FACT** |
| Client `activity` | Actual downlink point/short-window sample | **A** | **REUSE EXISTING PERSISTED FACT** only with explicit semantics |
| Client `rxRate` / `txRate` | Wi-Fi negotiated PHY rates | **E** | **DO NOT USE** as actual throughput |
| Client `past-connection` | Completed connection volume/history | **B** | **CONSIDER ADDING TO EXISTING ACQUISITION** only for explicit future need |
| Public per-AP historical time series | Not found | **F** | Use persisted Observation history |
| Public SSID Traffic current/history | Not found | **F** | **DO NOT USE** |
| Gateway current/WAN traffic in this topology | Omada Gateway semantics; Cisco is gateway | **E** | **DO NOT USE** as CaptivPortal Site Traffic |
| Visit `reported_traffic_*` relabeled as Network Traffic | Wrong semantic domain | **E** | Keep in Visit/Activity domain only |
| Private/internal UI API | Not established as stable Traffic contract | **G** | **RESEARCH FURTHER** only under separate authorization |

Classification legend:

```text
A — useful and already persisted by CaptivPortal
B — useful native source, but currently not persisted
C — useful only for diagnostics / observability
D — duplicate of existing CaptivPortal calculation/source
E — misleading for product use
F — unavailable / not found
G — semantics unresolved
```

---


## 12.1 R11 — Source stability summary

| Source family | Type | Stability assessment | Notes |
|---|---|---|---|
| `/openapi/v1/.../dashboard/*` | Public OpenAPI | Preferred / relatively stable | Live runtime still diverged from Swagger on `dxData` vs `rxData`; version-aware parsing/tests required |
| `/openapi/v1/.../aps/...` | Public OpenAPI | Preferred / relatively stable | Current AP facts already persisted by CaptivPortal |
| `/openapi/v1/.../clients/...` | Public OpenAPI | Preferred / relatively stable | Client publication is snapshot-based; field semantics must be respected |
| `/openapi/v1/.../insight/past-connection` | Public OpenAPI | Preferred over private API | Paged completed-connection history; exact retention not established |
| UI/private endpoints | Private/internal | Version-sensitive / unapproved | Research evidence only; no product dependency established |
| Gateway/DPI surfaces | Public but topology-inapplicable | Stable API does not make semantics applicable | Cisco is authoritative guest gateway in this deployment |

Authentication for useful public endpoints was verified through the existing OAuth `client_credentials` path. Request-limit ceilings for these read endpoints were not stress-tested because load testing was outside the research purpose.

## 12.2 R12 — Sampling and freshness summary

| Surface | Observed publication / bucket behavior | Freshness caveat |
|---|---|---|
| Client Detail current snapshot | effective changes roughly every 30 s | faster polling repeats the same Controller snapshot |
| Client `activity` | point/short-window downlink sample carried in client snapshot | can be 0 or bursty during sustained transfer |
| Client `trafficDown/trafficUp` | cumulative current-connection counters, refreshed with snapshot | use actual snapshot-change elapsed time, not polling interval |
| Client `active` | can remain stale `true` for >5 min after physical disconnect | not an immediate physical connectivity signal |
| AP `wired-uplink` | effective updates roughly every 30 s | `activity` tracks Controller interval average |
| AP LAN vs radio | each surface publishes independently | adjacent calls may be offset by ~seconds; do not assume atomic cross-layer snapshot |
| Site historical Traffic | explicit bucket timestamps | granularity depends on requested range; missing values are not zero |

Current AP endpoints do not provide a universal source-snapshot timestamp equivalent to CaptivPortal's own persisted `*_observed_at` fields. CaptivPortal persistence therefore adds useful quality/freshness observability that direct product reads from Omada would lose.

## 12.3 Required final metric matrix

| Metric | Omada source | Unit | Current / History | Exact meaning | CaptivPortal already persists? | Recommendation |
|---|---|---|---|---|---|---|
| Site Download | No direct native current Site rate; historical `traffic-activities.txData` | current: n/a; history: MB/bucket | Current: not found; History: yes | Historical traffic approximately equal to Σ AP LAN RX, i.e. traffic delivered toward wireless clients | **Yes**, underlying current/history AP Observation facts; native Monitor buckets themselves not persisted | **REUSE EXISTING PERSISTED FACT** for current; historical native source only **CONSIDER ADDING** after architecture review |
| Site Upload | No direct native current Site rate; runtime `traffic-activities.dxData` (Swagger `rxData`) | current: n/a; history: MB/bucket | Current: not found; History: yes | Historical traffic approximately equal to Σ AP LAN TX, i.e. traffic received from wireless clients | **Yes**, underlying AP Observation facts | Same as Site Download |
| AP Download | `/aps/{apMac}/wired-uplink.downBytes`; `/lan-traffic-info.rx` | bytes cumulative; derived Mbps in CaptivPortal | Current | AP Ethernet receive side / traffic toward wireless side; no separate native directional current Mbps field verified | **Yes** | **REUSE EXISTING PERSISTED FACT** |
| AP Upload | `/aps/{apMac}/wired-uplink.upBytes`; `/lan-traffic-info.tx` | bytes cumulative; derived Mbps in CaptivPortal | Current | AP Ethernet transmit side / traffic from wireless side toward LAN | **Yes** | **REUSE EXISTING PERSISTED FACT** |
| Client Download | Client Detail `activity` plus `trafficDown` | `activity`: B/s; `trafficDown`: bytes | Current | `activity` = point/short-window actual downlink sample; `trafficDown` = cumulative bytes for current connection | **Yes** | Persisted counter-delta remains canonical for symmetric product throughput |
| Client Upload | Client Detail `trafficUp`; no symmetric upload activity field found | bytes | Current | cumulative upload bytes for current connection | **Yes** | **REUSE EXISTING PERSISTED FACT** and derive rate from deltas |
| Client Traffic Volume | `trafficDown + trafficUp` | bytes | Current connection; finalized into history | volume accumulated within current Omada connection | **Yes** | **REUSE EXISTING PERSISTED FACT** |
| SSID Traffic | No trustworthy public traffic endpoint found | — | Current/History unavailable | no verified stable SSID aggregate | **No native source to persist** | **DO NOT USE** |
| Site History | `dashboard/traffic-activities` | MB/bucket | History | Controller-aggregated Site AP Ethernet/LAN-side traffic volume | Underlying AP Observation history: **Yes**; native buckets: **No** | **CONSIDER ADDING TO EXISTING ACQUISITION** only if superior to canonical Observation read model |
| AP History | No public per-AP time series; `traffic-distribution` only gives range aggregate | MB/range | Range aggregate only | per-AP share/volume for selected range, not time series | **Yes**, per-AP Observation history exists | Use persisted Observation history; native range aggregate is optional evidence |
| Client History | `insight/past-connection` | bytes per completed connection | History | completed connection download/upload volume + timing/context; not throughput time series | Observation snapshot history: **Yes**; native completed-connection rows: **No** | **CONSIDER ADDING** only for an explicit future completed-connection use case |


# 13. Architecture Recommendations

## 13.1 Current Traffic

For TRAFFIC-01 and current Network Throughput:

```text
REUSE EXISTING PERSISTED FACT
```

Do not add direct Admin or browser Omada calls.

Do not replace current wired/LAN source-family selection merely because Omada exposes alternate endpoint projections.

## 13.2 Historical Site Traffic

`traffic-activities` is the strongest new primitive found.

It provides native Site historical volume, automatic time-range aggregation and directionally coherent semantics against AP LAN counters.

Before making it a product dependency, Architect should compare it against the planned canonical Observation-based Historical Network Traffic read model on:

- semantic ownership;
- source-family selection;
- data-quality visibility;
- gap handling;
- query performance;
- Controller availability dependency;
- historical reproducibility;
- cross-surface consistency.

Recommendation:

```text
CONSIDER ADDING TO EXISTING ACQUISITION
```

only if that review demonstrates a concrete advantage.

## 13.3 Per-AP history

No native public per-AP historical time series was found.

The already persisted AP Observation history remains the natural source for AP history/share calculations unless a future stable primitive is discovered.

## 13.4 Client current throughput

For future TRAFFIC-07:

- do not use PHY `rxRate` / `txRate`;
- do not treat `activity` as a complete bidirectional throughput contract;
- continue using persisted cumulative client counters plus counter-delta logic when a symmetric Download/Upload current rate is required;
- use actual snapshot timestamps/elapsed time, not request polling interval.

## 13.5 Client completed history

`past-connection` is useful but semantically distinct from Visit Lifecycle.

It may be considered for future device/history diagnostics, but must not replace Visit Lifecycle without a separate product-semantic decision.

## 13.6 SSID Traffic

Do not design Traffic v1 around a native SSID Traffic primitive because no trustworthy stable source was found.

---

# 14. Unresolved Questions

The following remain intentionally unresolved.

## 14.1 AP counter reset boundaries

Not verified:

```text
AP reboot
Controller restart
firmware restart
counter overflow
long-term wrap behavior
```

AP/Radio counters were monotonic during the research window. No AP or Controller restart was performed.

## 14.2 Client roam behavior

Per-connection counter behavior across a natural AP roam was not isolated. Reconnect/offline→online reset behavior is verified.

## 14.3 Exact Site historical retention policy

The endpoint accepted at least 365-day requests, but older ranges were padded with empty buckets.

The earliest populated daily bucket in this Controller was 2026-07-26 00:00 Asia/Baku.

This does not distinguish retention limit from actual data-availability start.

## 14.4 Exact minute-level granularity boundaries

Only architecture-relevant integer-hour/day thresholds were measured.

## 14.5 Stable SSID Traffic

No public source found; private/UI source not verified.

## 14.6 Per-AP native history

No public time-series source found.

---

# 15. Final Outcome

## 15.1 Overall verdict

```text
CURRENT TRAFFIC:
Existing CaptivPortal Observation acquisition is sufficient.

SITE CURRENT:
No superior direct native Site-wide wireless/AP rate found.

AP CURRENT:
Native useful facts exist and are already persisted.

CLIENT CURRENT:
Native cumulative counters and activity exist and are already persisted.
No symmetric native actual current upload counterpart to client activity was found.

SITE HISTORY:
Native public Site traffic history exists and is useful.

AP HISTORY:
No public per-AP historical time series found.

CLIENT HISTORY:
Completed connection volume history exists, but not a client throughput time series.

SSID TRAFFIC:
No trustworthy stable public current/history source found.

ARCHITECTURE:
Do not replace Observation-based Network Traffic.
Do not add Admin/Browser direct Omada access.
```

## 15.2 Mandatory final answers Q1–Q10

### Q1. Нужен ли новый Omada acquisition source для TRAFFIC-01…06?

**Нет, как обязательный prerequisite — не нужен.**

Для current Traffic полезные AP primitives уже сохраняются в Observation.

Для historical Site Traffic найден новый native endpoint `traffic-activities`, но его использование должно пройти отдельное архитектурное сравнение с canonical Observation-based historical read model.

### Q2. Есть ли native actual per-client throughput, пригодный для TRAFFIC-07?

**Частично, но не как полный bidirectional contract.**

`activity` является native actual downlink point/short-window sample в Bytes/s.

Но публикация client snapshot примерно 30 s, значение bursty/point-like, может быть 0 во время устойчивого transfer, а симметричного current upload field не найдено.

Для полного Download + Upload текущая persisted counter-delta модель остаётся предпочтительной.

### Q3. Что именно означают client `traffic_down` / `traffic_up` / `traffic_total`?

`trafficDown` и `trafficUp` — cumulative byte counters **текущей Omada connection**.

Они не являются lifetime MAC counters.

При финализации:

```text
trafficDown → past-connection.download
trafficUp   → past-connection.upload
uptime      → past-connection.duration
```

Новая connection начинает новые counters.

`traffic_total` в CaptivPortal является суммарным представлением directional counters, а не отдельным lifetime primitive.

### Q4. Есть ли native historical Site Traffic?

**Да.**

```text
GET .../dashboard/traffic-activities?start=&end=
```

Возвращает Site AP-traffic volume time series с range-aware гранулярностью.

### Q5. Есть ли native historical AP Traffic?

**Не найден public per-AP time series.**

Есть per-AP range aggregate `dashboard/traffic-distribution`, но это не AP historical series over time.

### Q6. Есть ли native historical Client Traffic?

**Частично.**

`past-connection` предоставляет history завершённых connection с `download/upload/duration/firstSeen/lastSeen`, но не готовый client throughput time series по bucket'ам.

### Q7. Есть ли trustworthy SSID-level Traffic?

**Нет, не найден.**

Public OpenAPI stable Traffic source by SSID не обнаружен.

### Q8. Есть ли смысл менять текущую Observation-based Network Traffic architecture?

**Нет.**

Research подтвердил физическую и семантическую состоятельность существующих persisted AP LAN/radio/client facts.

### Q9. Какие найденные sources стоит добавить в существующий acquisition layer?

**Ни один не является обязательным.**

Кандидаты для отдельного architecture review:

1. `dashboard/traffic-activities` — если native Site history даст доказанное преимущество;
2. `past-connection` — только если нужен Controller-native completed connection history;
3. `traffic-distribution` — только если нужен native range aggregate rather than derivation from one canonical historical model.

Current AP/client primitives добавлять не требуется: они уже persisted.

### Q10. Какие sources категорически не следует использовать как product Traffic?

Не использовать как authoritative product Traffic:

- client `rxRate` / `txRate` as actual throughput;
- `maxTxRate` / port link speed / PHY capacity as traffic;
- channel/radio utilization as throughput;
- Omada Gateway WAN/DPI values as Site Traffic in the current Cisco-gateway topology;
- `most-active-eaps.status` as AP inventory status;
- private/internal UI APIs without separate architecture approval;
- missing historical buckets as numeric zero;
- Visit `reported_traffic_*` as Network Throughput;
- direct Browser/Admin → Omada calls.

---

# 16. Raw Evidence Appendix

## 16.1 Monitor historical one-hour cross-check

```text
traffic-activities:
txData total = 1190.27 MB
dxData total = 245.95 MB
total        = 1436.22 MB

traffic-distribution:
AP-1 = 957.34 MB
AP-2 = 478.86 MB
total = 1436.20 MB

wifi-summary.totalTraffic:
1,470,671.53 KB
/ 1024 = 1436.2027 MB
```

## 16.2 Per-AP ranking duplicate projection

```text
most-active-eaps:
AP-1 traffic = 0.93 GB
AP-2 traffic = 0.47 GB
```

Both APs were online while this projection returned `status=0`.

## 16.3 AP wired activity samples

```text
dt ≈ 31.10 s | counter avg total = 0.817 Mbps | activity = 0.847 Mbps
dt ≈ 31.08 s | counter avg total = 0.182 Mbps | activity = 0.182 Mbps
dt ≈ 29.06 s | counter avg total = 0.068 Mbps | activity = 0.066 Mbps
```

## 16.4 Controlled cross-layer Plex sample

```text
CLIENT DOWN +73,369,368
CLIENT UP   + 2,110,550
RADIO TX    +72,038,832
RADIO RX    + 2,064,024
LAN RX      +72,426,709
LAN TX      + 2,339,880
```

## 16.5 Site aggregate vs AP LAN sample

```text
AP1 ΔLAN RX =     665,692 B
AP1 ΔLAN TX =     431,715 B
AP2 ΔLAN RX = 395,953,256 B
AP2 ΔLAN TX =  13,775,202 B

Σ LAN RX = 396,618,948 B
Σ LAN TX =  14,206,917 B

Site traffic-activities:
txData = 387.17 MB
dxData =  13.13 MB
```

## 16.6 Client connection finalization proof

Live frozen current connection:

```text
id          = 6a68d829b44c923b94931762
uptime      = 1237
trafficDown = 655714003
trafficUp   = 21480531
lastSeen    = 1787955651778
```

New completed history row:

```text
id        = 6a920b0bb2e4d67c5d27ff4e
duration  = 1237
download  = 655714003
upload    = 21480531
lastSeen  = 1787955651778
IP        = 192.168.11.163
```

New live connection:

```text
same client object id
uptime      = 35
trafficDown = 6035752
trafficUp   = 663768
```

## 16.7 Historical granularity probes

```text
24 h  → 5-minute
25 h  → 5-minute
26 h  → 5-minute
27 h  → hourly

168 h → hourly
169 h → hourly
170 h → hourly
171 h → daily

120 d → daily
121 d → weekly
```

## 16.8 Daily → weekly traffic conservation

```text
120-day daily:
tx    625685.98 MB
dx    218149.04 MB
total 843835.02 MB

121-day weekly:
tx    625685.98 MB
dx    218149.04 MB
total 843835.02 MB
```

## 16.9 Long-range empty-bucket behavior

```text
90 days:  90 total / 35 populated / 55 empty
180 days: 26 total /  5 populated / 21 empty
365 days: 53 total /  5 populated / 48 empty
```

All contained the same populated traffic total:

```text
843,835.02 MB
```

## 16.10 Earliest populated daily Site bucket observed

```text
UTC:       2026-07-25T20:00:00Z
Asia/Baku: 2026-07-26 00:00:00 +04:00
```

## 16.11 CaptivPortal AP persisted evidence

Example AP-2 Observation:

```text
wired_up_bytes   = 1356886129
wired_down_bytes = 8921207098
wired_activity_raw = 2137

lan_rx_bytes = 8921207098
lan_tx_bytes = 1356886129

wired_download_mbps = 0.0097582600
wired_upload_mbps   = 0.0054837176
lan_rx_mbps         = 0.0097579701
lan_tx_mbps         = 0.0054835547
```

## 16.12 CaptivPortal radio persisted schema

Per band:

```text
rx_bytes
tx_bytes
rx_packets
tx_packets
rx_drop_packets
tx_drop_packets
rx_error_packets
tx_error_packets
rx_retry_packets
tx_retry_packets
radio_rx_mbps
radio_tx_mbps
```

## 16.13 CaptivPortal client persisted evidence

Latest test-client Observation included:

```text
ssid         = Zefer_Parki
ap_name      = AP-2
ap_mac       = DC:62:79:1B:4A:68
radio_id     = 0
band         = 2.4GHz
channel      = 11
rx_rate      = 1000
tx_rate      = 1000
activity     = 0
uptime       = 369
active       = 1
traffic_down = 89892679
traffic_up   = 2384564
```

---

# Handoff to Architect

Deliverables:

```text
1. Final research report
2. Sanitized raw evidence
3. Endpoint inventory
4. Final source classification
5. Final metric matrix / Q1-Q10 conclusions
6. Unresolved questions
```

Research conclusion does **not** authorize implementation.

Until Architect / Owner / Tech Lead review:

```text
Traffic implementation authorization = NOT GRANTED
Traffic acquisition changes          = NOT GRANTED
Traffic schema changes               = NOT GRANTED
```
