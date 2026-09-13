# TASK-WEB-HOME-ONLINE-DEVICE-PRESENTATION-01 — Home Online Devices Presentation — FINAL

Status: CLOSED / MERGED / PRODUCTION CURRENT / OWNER VISUAL PASS
Updated: 2026-09-13

## Identity

```text
PR=#118
title=TASK-WEB-HOME-ONLINE-DEVICE-PRESENTATION-01: improve Online Devices presentation
baseline=488e75aa2d1b067ee27d8fbfff778d49901d9fdf
publication commit=892b66ad300ce9ad1b93ae4e0ce1cb235fb6c3cd
merge commit=2d87fd6d56f969492318e21c809086576b2b1ab1
accepted / publication tree=346c7f1f8ad6e91f36fbd572b7c8f6e7a22add11
changed files=2
diff stat=+132/-15
```

Changed implementation files:

```text
app/admin_web/static/admin.css
app/admin_web/static/admin.js
```

## Accepted Home Online Devices presentation

The Home Online Devices table replaced the expandable `Controller facts` detail
with direct compact presentation.

Current columns established by this task:

```text
Device / MAC
Auth
IP
AP
Band
RSSI
SNR
Uptime
Traffic
```

The task added:

- Authorized / Waiting presentation tones;
- 5 GHz / 2.4 GHz presentation tones;
- a five-segment RSSI presentation;
- human-readable controller uptime;
- human-readable total controller traffic.

Accepted RSSI colors:

```text
good    #10b956
warning #f2c20d
danger  #ed3038
```

This task did **not** introduce a Device Type contract. Device Type presentation
was deliberately deferred until one canonical backend/read-time normalization
contract existed.

That deferred dependency was later closed by:

```text
TASK-DEVICE-TYPE-NORMALIZATION-01 / PR #119
TASK-WEB-DEVICE-TYPE-PRESENTATION-01 / PR #120
```

## Acceptance

```text
Source review=PASS
narrow frontend gate=4/4 PASS
Owner visual acceptance=PASS
Windows Central Lab V7 strict=PASS
strict regressions=0
exact-artifact immutability=PASS
```

This FINAL records the accepted PR #118 stage. The current Home contract also
includes the later Device Type and SNR presentation work from PR #120.
