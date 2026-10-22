# Omada Traffic Read Surface — Endpoint Inventory

**Project:** CaptivPortal  
**Research:** TRAFFIC-SOURCE-RESEARCH-01  
**Controller:** Omada Software Controller 5.14.32.3  
**Status:** Final inventory

| Endpoint | Method | Parameters | Scope | Unit / fields | Live status | Classification | Recommendation |
|---|---|---|---|---|---|---|---|
| `/openapi/v1/{omadacId}/sites/{siteId}/dashboard/traffic-activities` | GET | `start`, `end` | Site AP traffic history | `time`, `txData`, runtime `dxData` (Swagger says `rxData`), MB/bucket | VERIFIED | B | CONSIDER ADDING TO EXISTING ACQUISITION only after architecture review |
| `/openapi/v1/{omadacId}/sites/{siteId}/dashboard/traffic-distribution` | GET | `start`, `end` | Per-AP / switch range aggregate | traffic MB, proportion % | VERIFIED | B | RESEARCH FURTHER / likely derive from canonical history |
| `/openapi/v1/{omadacId}/sites/{siteId}/dashboard/wifi-summary` | GET | `start`, `end` | Site Wi-Fi summary | `totalTraffic` KB plus summary fields | VERIFIED | D | DO NOT USE as canonical Traffic source |
| `/openapi/v1/{omadacId}/sites/{siteId}/dashboard/most-active-eaps` | GET | `start`, `end` | AP ranking | traffic GB, projection status | VERIFIED | C | DO NOT USE as canonical source |
| `/openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/wired-uplink` | GET | AP MAC | AP current wired | bytes, packets, `activity` B/s, link rate/duplex | VERIFIED | A | REUSE EXISTING PERSISTED FACT |
| `/openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/lan-traffic-info` | GET | AP MAC | AP current Ethernet/LAN | RX/TX bytes, packets, drops, errors | VERIFIED | A | REUSE EXISTING PERSISTED FACT |
| `/openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}/radios` | GET | AP MAC | Per-radio current/cumulative accounting | RX/TX bytes/packets/drops/errors/retries | VERIFIED | A | REUSE EXISTING PERSISTED FACT |
| `/openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}` | GET | client MAC | Current client | `activity`, `trafficDown`, `trafficUp`, `rxRate`, `txRate`, `uptime`, `lastSeen` | VERIFIED | A/E by field | REUSE counters/activity; DO NOT USE PHY rates as throughput |
| `/openapi/v1/{omadacId}/sites/{siteId}/insight/past-connection` | GET | paging/search | Completed client connections | download/upload bytes, duration, first/last seen, SSID/AP/IP | VERIFIED | B | CONSIDER ADDING only for explicit future completed-connection use case |
| Public per-AP historical time-series endpoint | GET | — | AP historical time series | — | NOT FOUND | F | Use persisted Observation history |
| Public SSID Traffic current/history endpoint | GET | — | SSID | — | NOT FOUND | F | DO NOT USE / future dedicated research if needed |

## Runtime contract notes

1. `traffic-activities` Swagger names the receive-side field `rxData`; live runtime emitted `dxData`.
2. Monitor unit labels behave consistently with 1024-based scaling across KB/MB/GB projections.
3. `most-active-eaps.status` is projection-specific and must not be treated as AP inventory status.
4. Client snapshots and AP current source updates are Controller-published rather than changing on every fast poll.
5. LAN and radio surfaces can publish asynchronously.
6. Historical missing value buckets are not equivalent to zero traffic.
7. Observed granularity:
   - ≤26 h: 5-minute
   - 27–170 h: hourly
   - 171 h–120 d: daily
   - ≥121 d: weekly
