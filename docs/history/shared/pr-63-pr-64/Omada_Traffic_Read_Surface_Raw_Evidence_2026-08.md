# Omada Traffic Read Surface — Sanitized Raw Evidence

**Project:** CaptivPortal  
**Research:** TRAFFIC-SOURCE-RESEARCH-01  
**Controller:** Omada Software Controller 5.14.32.3  
**Sensitive values:** OAuth secrets/tokens/cookies omitted

## E1 — Site history 1h
```text
traffic-activities: txData 1190.27 MB, dxData 245.95 MB, total 1436.22 MB
```

## E2 — Distribution same range
```text
AP-1 957.34 MB (66.66%)
AP-2 478.86 MB (33.34%)
total 1436.20 MB
```

## E3 — Wi-Fi summary same range
```text
totalTraffic 1,470,671.53 KB / 1024 = 1436.2027 MB
```

## E4 — AP wired activity
```text
31.10s: counter avg .817 Mbps / activity .847 Mbps
31.08s: counter avg .182 Mbps / activity .182 Mbps
29.06s: counter avg .068 Mbps / activity .066 Mbps
```

## E5 — Plex cross-layer
```text
CLIENT DOWN +73369368
CLIENT UP   +2110550
RADIO TX    +72038832
RADIO RX    +2064024
LAN RX      +72426709
LAN TX      +2339880
```

## E6 — Client finalization
```text
live trafficDown=655714003 → history download=655714003
live trafficUp=21480531    → history upload=21480531
live uptime=1237           → history duration=1237
live lastSeen=1787955651778 → history lastSeen=1787955651778
```

## E7 — New connection
```text
same client object id
uptime=35
trafficDown=6035752
trafficUp=663768
```

## E8 — Historical granularity
```text
26h → 5-minute
27h → hourly
170h → hourly
171h → daily
120d → daily
121d → weekly
```

## E9 — 120d vs 121d
```text
120d daily total = 843835.02 MB
121d weekly total = 843835.02 MB
```

## E10 — Long-range empties
```text
90d:  90 rows / 35 populated
180d: 26 rows / 5 populated
365d: 53 rows / 5 populated
```

## E11 — Persisted AP current facts
```text
wired_up_bytes
wired_down_bytes
wired_activity_raw
lan_rx_bytes
lan_tx_bytes
lan_rx_mbps
lan_tx_mbps
```

## E12 — Persisted radio facts
```text
rx_bytes
tx_bytes
rx_packets
tx_packets
drops/errors/retries
radio_rx_mbps
radio_tx_mbps
```

## E13 — Persisted client facts
```text
rx_rate
tx_rate
activity
uptime
last_seen_ms
active
traffic_down
traffic_up
SSID/AP/radio context
```
