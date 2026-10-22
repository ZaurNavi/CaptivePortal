# Omada Client Control OpenAPI Research — Consolidated Final Report

**Project:** CaptivPortal  
**Research:** Omada Client Control / Policy  
**Controller:** Omada Software Controller 5.14.31  
**Primary AP under test:** TP-Link EAP613(EU) v1.0  
**Site:** Home  
**Research window:** 2026-08-14 — 2026-08-15 (Asia/Baku)  
**Status:** **CONSOLIDATED RESEARCH COMPLETE — schema inventory + read-only live verification + controlled mutation/effect verification**  
**Supersedes as a single source:**  
- `Omada_Client_Control_OpenAPI_Research_Stage_A_2026-08.md`
- `Omada_Client_Control_OpenAPI_Research_Stage_B_ReadOnly_2026-08.md`
- live controlled mutation/effect-verification session performed after Stage B

> This document intentionally omits OAuth client secrets, access tokens, cookies and authorization-header values.

---

## 1. Executive summary

The Omada Software Controller 5.14.31 exposes a substantial public OpenAPI surface for direct endpoint-client control.

The research established three evidence layers:

1. **Stage A — schema/documentation reconnaissance**
   - inventoried the controller Swagger surface;
   - extracted direct client-control endpoints;
   - extracted request schemas, permissions and documented Omada error codes;
   - identified operations not present as direct public Client OpenAPI;
   - separated direct Client Control from broader infrastructure/policy APIs.

2. **Stage B — live read-only verification**
   - verified OAuth `client_credentials`;
   - verified Client Detail, active Client List, Rate Limit Profile read and Hotspot Authentication Records;
   - identified material runtime/Swagger response-shape differences.

3. **Controlled mutation/effect verification**
   - used only the project owner's designated test phone;
   - verified Rename, Custom Rate Limit, Rate Limit Profile CRUD/application, Lock-to-AP configuration, Reconnect, Block/Unblock, Hotspot Unauth/Auth and Modify Authentication Period;
   - physically verified data-plane rate limiting and disruptive connectivity effects;
   - captured internal Omada UI API behavior where public OpenAPI rollback semantics were insufficient;
   - completed a final cleanup audit with no test configuration left behind.

The strongest product-ready findings are:

- **Rename Client works through public OpenAPI.**
- **Custom per-client Rate Limit works and physically enforces configured throughput.**
- **Rate Limit Profiles can be created, updated, assigned, read and deleted through public OpenAPI; profile shaping physically works.**
- **Reconnect physically disconnects a wireless client but does not guarantee that the client OS will reconnect automatically.**
- **Block physically removes the client from active access; Unblock only removes the prohibition and does not reconnect the client.**
- **Hotspot Unauth really revokes the Hotspot authorization record.**
- **Hotspot Auth can move a captured `PENDING` client to `AUTHORIZED` through OpenAPI, although an isolated “bypass CaptivPortal entirely” physical test was not obtained because the normal portal flow was active in the same race window.**
- **Authentication Period `period` means “extend current expiration by N milliseconds”: `new_end = old_end + period`.**
- **Lock-to-AP configuration and rollback work through public OpenAPI; physical roaming prevention between multiple APs remains unverified.**
- **Full removal of a client Custom Rate Limit back to `rateLimit.enable=false` was not achieved through the public `/ratelimit` endpoint; the Omada UI performs it through an internal `/api/v2/.../clients/{MAC}` endpoint.**

---

## 2. Evidence model and capability statuses

### 2.1 Evidence levels

| Level | Meaning |
|---|---|
| **A** | Controller documentation / operation description |
| **B** | OpenAPI/Swagger schema confirmed on the actual Controller |
| **C** | Live request accepted and verified through `HTTP + errorCode/msg + read-back` |
| **D** | Actual state/data-plane/physical effect verified where an effect is applicable |

Important:

```text
HTTP 200 alone is NOT success proof.
```

For Omada 5.14.31, many operation-specific failures are returned inside an HTTP 200 response using:

```text
errorCode
msg
```

### 2.2 Final capability statuses

| Status | Meaning |
|---|---|
| **VERIFIED_SAFE** | Live verified and suitable as a direct product primitive within normal validation/authorization rules |
| **VERIFIED_WITH_CONDITIONS** | Live verified, but important topology/runtime/rollback conditions remain |
| **SCHEMA_CONFIRMED** | Public OpenAPI exists and schema is known, but required live effect is not fully verified |
| **DOCUMENTED_ONLY** | Found in descriptions or adjacent APIs, not live verified |
| **INTERNAL_NOT_OPENAPI** | Observed in the Omada UI internal API rather than supported public OpenAPI |
| **UNSUPPORTED_ON_5_14_31** | No usable public direct operation found / known tested path unsupported |
| **UNSAFE_FOR_PRODUCT** | Operation should not be exposed without additional safety design |
| **NOT_APPLICABLE** | Does not apply to ordinary endpoint visitors in the current topology |

---

## 3. Research environment

### 3.1 Controller and network

- Omada Software Controller: **5.14.31**
- Controller address during research: `192.168.0.222:8043`
- Site: `Home`
- Test SSID: `Zefer_Parki`
- Guest client network: `192.168.1.0/24`
- Production guest routing/DHCP: **Cisco**, not an Omada Gateway
- Primary AP observed in the test series:
  - MAC: `EC-75-0C-18-6F-F8`
  - model family: EAP613

### 3.2 Test client identity

The originally known historical test identity was:

```text
FA-D5-62-D4-EB-25
```

Before mutation testing this card was verified as known/offline.

When the physical Moto G85 5G was connected for the controlled series, Android used the current private Wi-Fi identity:

```text
MAC: BE-00-7D-9B-04-2E
IP:  192.168.1.150
SSID: Zefer_Parki
AP:  EC-75-0C-18-6F-F8
```

The MAC and IP were confirmed on the phone before disruptive mutations.

### 3.3 Safety constraints applied

- mutations only on the owner's designated phone;
- no visitor/staff/third-party client mutations;
- no Controller restart;
- no production AP restart;
- no production Fixed IP mutation;
- no ordinary-client Reboot test;
- no destructive Batch test;
- no production code/configuration changes;
- Pending Session Cleaner remained enabled;
- rollback determined before each mutation when possible;
- temporary Rate Limit Profiles were deleted after testing;
- secrets/tokens were excluded from this report.

---

# Part I — Stage A: OpenAPI / Swagger reconnaissance

## 4. Swagger inventory

The Controller exposed these Swagger groups:

1. `00 All`
2. `01 Account`
3. `02 Organization`
4. `03 Device`
5. `04 Site Setting`
6. `05 Client`
7. `06 Hotspot`
8. `07 Monitor`
9. `08 Maintenance`
10. `09 Insight`
11. `10 Msp`
12. `11 Log`
13. `12 Batch`

Observed root inventory:

- total operations: **641**
- mutations in `00 All`: **383**
- initial broad client/policy keyword candidates: **208**

All 13 grouped Swagger documents returned valid JSON.

The apparent difference between `00 All` mutation counts and named groups was investigated. Additional mutations were global webhook-management operations, not hidden direct Client Control. Two additional read-only v2 topology endpoints also appeared in `00 All`.

---

## 5. Direct public Client OpenAPI surface

### 5.1 Reads

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/clients
GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}
GET /openapi/v1/{omadacId}/sites/{siteId}/insight/past-connection
```

### 5.2 Mutations

```text
POST  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/block
POST  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/unblock
POST  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
POST  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/lock-to-ap
PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/name
PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/ratelimit
```

---

## 6. Hotspot / authentication public surface

```text
GET  /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records
POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records/{id}/period
POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/auth
POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/unauth
```

Additional Hotspot APIs exist for users/surveys, but they are not direct endpoint-client control primitives.

---

## 7. Operations not found as direct public Client OpenAPI

No direct public Client/Hotspot endpoint was found for:

- `Disconnect / Kick`
- `Delete Client`
- ordinary endpoint `Reboot Client`
- direct Client IP Setting mutation

A prior exact probe:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/disconnect
```

returned HTTP `404`.

Final interpretation:

- public `Reconnect` is the supported direct wireless-disconnection primitive discovered;
- direct public Delete Client was not found;
- direct public ordinary-client Reboot was not found;
- client `ipSetting` is readable but no direct Client mutation endpoint was found.

UI/internal API behavior must be kept separate from public OpenAPI support.

---

## 8. Client Detail read-back contract

Observed/documented fields used in this research:

### Identity / association

- `mac`
- `name`
- `hostName`
- `ip`
- `ssid`
- `apName`
- `apMac`
- `uptime`

### Authentication

```text
authStatus:
0 = CONNECTED
1 = PENDING
2 = AUTHORIZED
3 = AUTH-FREE
```

### State

- `blocked`
- `active`
- `blockDisable`

### Fixed IP read model

- `ipSetting.useFixedAddr`
- `ipSetting.netId`
- `ipSetting.ip`

### Rate Limit

Swagger described a nested mutation-oriented structure, but the live Client Detail runtime response is materially different; see the runtime findings below.

### Lock-to-AP

- `clientLockToApSetting.enable`
- `clientLockToApSetting.aps`

### Link rates

- `rxRate` = wireless uplink negotiated rate in Kbit/s
- `txRate` = wireless downlink negotiated rate in Kbit/s

These are negotiated link rates, **not real traffic throughput**, and were not used as proof of Rate Limit enforcement.

---

## 9. Rename Client schema

Endpoint:

```text
PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/name
```

Request:

```json
{
  "name": "..."
}
```

Schema:

- required;
- documented length: 1–128 characters.

Live behavior is documented in Part III.

---

## 10. Custom Client Rate Limit schema

Endpoint:

```text
PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/ratelimit
```

### 10.1 Custom mode

```text
mode = 0
```

Documented logical fields:

- `upEnable`
- `upUnit`
- `upLimit`
- `downEnable`
- `downUnit`
- `downLimit`

Units:

```text
1 = Kbps
2 = Mbps
```

Documented client custom limit range:

```text
1–1024
```

The live Controller required these custom fields inside:

```json
{
  "mode": 0,
  "customRateLimit": {
    "upEnable": true,
    "upUnit": 2,
    "upLimit": 2,
    "downEnable": true,
    "downUnit": 2,
    "downLimit": 2
  }
}
```

A flat top-level form was rejected with:

```text
errorCode: -1001
msg: Invalid request parameters.
```

### 10.2 Profile mode

```text
mode = 1
```

Request requires:

```json
{
  "mode": 1,
  "rateLimitProfileId": "<profile-id>"
}
```

Documented errors include:

- `-33732` Rate Limit profile does not exist
- `-41008` number of clients configured with Rate Limit reached capacity
- `-41011` client does not exist

---

## 11. Rate Limit Profiles

Public endpoints:

```text
GET    /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles
POST   /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles
PUT    /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}
DELETE /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}
```

Fields:

- `profileId`
- `name`
- `downLimitEnable`
- `downLimit`
- `upLimitEnable`
- `upLimit`
- `defaultProfile` (response)

Create requirements:

- name: 1–64 chars;
- `downLimitEnable` required;
- `upLimitEnable` required;
- enabled limits are expressed in Kbps;
- documented enabled limit range: 1–10485760 Kbps.

Documented errors:

- `-33000` site does not exist
- `-33733` profile already exists
- `-33734` profile count capacity reached

---

## 12. Lock-to-AP schema

Endpoint:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/lock-to-ap
```

Documented request shape:

```json
{
  "enable": true,
  "aps": [
    "AA-AA-AA-AA-AA-AA"
  ]
}
```

Schema facts:

- `enable` required boolean;
- `aps` array of AP MACs;
- documented MAC format uses uppercase characters and `-`.

Documented errors:

- `-41011` client does not exist
- `-41020` only wireless clients support Lock-to-AP
- `-41021` Lock-to-AP capacity reached
- `-41022` blocked client cannot be locked

Interaction rule documented by Omada:

```text
Blocked client -> Lock-to-AP rejected
```

Block documentation contains the reverse conflict:

```text
Lock-to-AP client -> Block rejected (-41023)
```

---

## 13. Block / Unblock documented contract

### Block

Permissions:

- `Site Clients Manager Modify`
- or `Site Insight Manager Modify`

Errors:

- `-41002` client does not exist
- `-41003` blocked-client capacity reached
- `-41023` locked-to-AP client cannot be blocked
- `-41024` controller-installed device cannot be blocked
- `-41026` Easy Managed Switch cannot block clients

### Unblock

Permissions:

- `Site Clients Manager Modify`
- or `Site Insight Manager Modify`

Error:

- `-41004` client does not exist

---

## 14. Reconnect documented contract

Permission:

```text
Site Clients Manager Modify
```

Documented errors:

- `-41011` client does not exist
- `-41025` unable to reconnect wired client

This makes the public Reconnect primitive wireless-oriented in the documented 5.14.31 contract.

---

## 15. Hotspot Auth / Unauth permissions and documented errors

### Auth

Permission:

- `Site Clients Manager Modify`
- or `Site Hotspot Manager Modify`

Errors include:

- `-1005`
- `-1200`
- `-33004`
- `-41009` failed to authorize client
- `-41010` client does not exist
- `-42003` operator does not exist
- `-42006` failed to log in
- `-44111`
- `-44112`
- `-7131`

### Unauth

Permission:

- `Site Clients Manager Modify`
- or `Site Hotspot Manager Modify`

Errors include:

- `-1005`
- `-1200`
- `-33004`
- `-41006` client does not exist
- `-41017` gateway does not exist or is disconnected
- `-41018` retry after network recovery
- `-41019` client is being disconnected
- `-44111`
- `-44112`
- `-7131`

A key Stage A question was whether `Unauth` would fail in the current Cisco-gateway topology. Live testing later proved that it **does work** in the current deployment.

---

## 16. Authentication Period schema

Endpoint:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records/{id}/period
```

Request:

```json
{
  "period": 60000
}
```

Schema:

- required integer;
- milliseconds;
- minimum `60000`;
- maximum `86400000000000`.

Stage A description wording was compatible with “extend valid time”, but exact semantics were intentionally left unresolved until live testing.

Live semantics are established in Part III.

---

## 17. Read permissions

Client list/detail:

- `Site Clients Manager View Only`
- or `Site Device Manager View Only`

Authentication records:

- `Site Hotspot Manager View Only`
- or `Site Insight Manager View Only`

Rate Limit Profiles read:

- `Site Settings Manager View Only`

Rate Limit Profiles create/update/delete require settings modification privileges; create was documented as:

- `Site Settings Manager Modify`

Most direct client mutations:

- `Site Clients Manager Modify`

Authentication-period mutation:

- `Site Hotspot Manager Modify`

Permission descriptions are embedded in operation descriptions rather than represented as conventional OpenAPI `securitySchemes`.

---

## 18. Batch API

Endpoint:

```text
POST /openapi/v1/{omadacId}/batch
```

Schema:

- `interrupt`: boolean
- `actions`: maximum 20 entries

Each action:

- `path`
- `method`
- `body`
- `query`

Documented methods:

- POST
- PATCH
- PUT
- DELETE

Documented errors:

- `-1001` invalid request parameters
- `-1600` unsupported request path
- `-1619` interrupted because a prior action failed
- `-1620` action execution error
- `-44112` token expired
- `-44113` token invalid
- `-7132` too many requests

Schema inconsistency:

- OpenAPI type presents action `body` as a string;
- operation description says body should be a JSON object.

**Batch client mutation was not live-tested in this research.**

---

## 19. Indirect policy/control surfaces discovered

Public OpenAPI also exposes broader policy domains:

### Bandwidth Control
- global bandwidth-control state;
- rules;
- create/modify/delete/order rules;
- SSID rate-limit configuration;
- Rate Limit Profiles;
- Gateway bandwidth objects.

### Gateway QoS
- bandwidth rules;
- service profiles;
- class rules;
- outbound traffic marking;
- VoIP prioritization;
- WAN QoS information.

### ACL
- EAP ACL;
- Gateway ACL;
- Switch ACL;
- custom Gateway ACL;
- ordering/hit-count operations.

### MAC filtering
- global state;
- allow/deny lists;
- create/modify/delete filters;
- SSID MAC-filter configuration.

### IP-MAC Binding / DHCP
- binding state;
- create/modify/delete;
- batch delete;
- DHCP reservation;
- reservation modification;
- export reservation to IP-MAC Binding.

### Application Control
- application catalogue;
- families;
- filters;
- restrictions;
- rules;
- global status;
- DPI data clear.

These are **not automatically direct per-client Client Control features**. They belong to a potential later Network Policy / infrastructure-dependent subsystem.

---

## 20. Fixed IP finding

Client Detail can expose:

- `ipSetting.useFixedAddr`
- `ipSetting.netId`
- `ipSetting.ip`

No direct public Client mutation endpoint was found for this setting.

Site Setting APIs expose DHCP reservations and IP-MAC Binding.

Because production guest DHCP is Cisco-based, Fixed IP manipulation through Omada was not tested.

Final classification:

```text
Infrastructure-dependent / not live-tested in current topology.
```

---

## 21. API versions

Direct client and Hotspot controls in this report use:

```text
/openapi/v1/...
```

Additional read-only topology endpoints exist in public v2:

```text
GET /openapi/v2/{omadacId}/sites/{siteId}/topology
GET /openapi/v2/{omadacId}/sites/{siteId}/topology/devices/{mac}/clients
```

No equivalent public v2 direct client mutation set was discovered.

---

# Part II — Stage B: live read-only verification

## 22. OAuth `client_credentials`

Live token request succeeded:

- HTTP `200`
- `errorCode: 0`
- Access Token returned
- Refresh Token returned
- `expiresIn: 7200`
- `tokenType: bearer`

Later expiration behavior was also observed:

```text
errorCode: -44112
The access token has expired.
```

Re-acquiring an Access Token through `client_credentials` restored access.

Verdict:

```text
LIVE VERIFIED
```

---

## 23. Known/offline Client Detail

Historical test MAC:

```text
FA-D5-62-D4-EB-25
```

Live detail response while offline:

- HTTP `200`
- `errorCode: 0`
- client card returned;
- `blocked=false`
- `active=false`
- `ipSetting={"useFixedAddr":false}`
- `clientLockToApSetting={"enable":false}`

Disabled Rate Limit runtime form:

```json
{
  "enable": false,
  "upEnable": false,
  "upUnit": 1,
  "upLimit": 0,
  "downEnable": false,
  "downUnit": 1,
  "downLimit": 0
}
```

Finding:

```text
Known/offline Client Detail is addressable directly by MAC.
```

---

## 24. Client List behavior

The list endpoint requires pagination:

- `page`
- `pageSize`

An initial call without these parameters returned HTTP `400`.

Corrected request:

```text
page=1
pageSize=100
searchKey=FA-D5-62-D4-EB-25
```

returned:

- HTTP `200`
- `errorCode: 0`
- `totalRows: 0`

At the same time direct Client Detail returned the same MAC as a known offline card.

Finding:

```text
In the tested state, Client List behaves as active inventory,
while direct Client Detail can return a known/offline client.
```

---

## 25. Rate Limit Profiles read

Live read initially returned one profile:

```text
name: По умолчанию
defaultProfile: true
downLimitEnable: false
upLimitEnable: false
```

In the earlier Stage B disabled-profile response, numeric disabled values serialized as `null`.

Later live CRUD reads returned the default profile with only disabled flags and omitted unused numeric values.

Conclusion:

```text
Consumers must tolerate omitted/null disabled profile limit fields.
```

---

## 26. Hotspot Authentication Records read

The endpoint requires:

- `page`
- `pageSize`

and supports `searchKey`.

Stage B read for the historical test MAC returned:

- HTTP `200`
- `errorCode: 0`
- `totalRows: 0`

This verified the endpoint and permission, but no active auth record was available at that time.

Later controlled testing with the actual current test MAC returned a large historical record set and valid runtime `id` values, enabling Authentication Period testing.

---

## 27. Material runtime / Swagger divergences

### 27.1 Client Rate Limit read-back

Swagger described a nested structure.

Actual Client Detail returns a flat runtime form such as:

```json
{
  "enable": true,
  "upEnable": true,
  "upUnit": 2,
  "upLimit": 2,
  "downEnable": true,
  "downUnit": 2,
  "downLimit": 2
}
```

or, when disabled:

```json
{
  "enable": false,
  "upEnable": false,
  "upUnit": 1,
  "upLimit": 0,
  "downEnable": false,
  "downUnit": 1,
  "downLimit": 0
}
```

### 27.2 Lock-to-AP read-back

When disabled:

```json
{
  "enable": false
}
```

When enabled, runtime expanded `aps` to objects:

```json
{
  "enable": true,
  "aps": [
    {
      "name": "EC-75-0C-18-6F-F8",
      "mac": "EC-75-0C-18-6F-F8"
    }
  ]
}
```

while requests use MAC strings.

### 27.3 `ipSetting`

Disabled state may contain only:

```json
{
  "useFixedAddr": false
}
```

Conclusion:

```text
Swagger is necessary but insufficient as the sole runtime response contract.
```

---

# Part III — Controlled mutation / effect verification

## 28. Pending Session Cleaner effective settings

Before pending-state mutation tests, the production process environment was inspected.

Runtime environment explicitly contained:

```text
PENDING_SESSION_CLEANER_ENABLED=true
PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN=1
PENDING_SESSION_CLEANER_SSIDS=Zefer_Parki
```

The current code defaults, with no corresponding runtime overrides present, were:

```text
scan interval                 = 60 s
minimum uptime                = 120 s
portal grace                  = 45 s
uptime regression tolerance  = 5 s
action cooldown               = 180 s
max actions per scan          = 1
max actions per MAC per hour  = 3
```

The Cleaner was not disabled or reconfigured.

Pending Auth tests were performed before Cleaner interference.

---

## 29. Controlled live baseline

After the physical phone joined with its current private MAC:

```text
MAC:        BE-00-7D-9B-04-2E
IP:         192.168.1.150
SSID:       Zefer_Parki
AP MAC:     EC-75-0C-18-6F-F8
wireless:   true
blocked:    false
active:     true
authStatus: 2
rateLimit.enable: false
clientLockToApSetting.enable: false
```

The current phone identity was physically confirmed before mutations.

---

## 30. Rename Client

### Mutation

Original name:

```text
BE-00-7D-9B-04-2E
```

Temporary name:

```text
RESEARCH-MOTO-G85
```

Public endpoint:

```text
PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/name
```

Result:

```text
HTTP: 200
errorCode: 0
msg: Success.
```

Immediate read-back:

```text
name: RESEARCH-MOTO-G85
active: true
authStatus: 2
blocked: false
```

Persistence check after several seconds:

- Client Detail still returned the new name;
- Client List search by `RESEARCH-MOTO-G85` returned exactly the same MAC.

Rollback:

```text
PATCH name -> BE-00-7D-9B-04-2E
```

succeeded, and the original name was restored.

### Verdict

```text
VERIFIED_SAFE
Live state effect and rollback confirmed.
```

---

## 31. Custom per-client Rate Limit

### 31.1 Request-shape discovery

Incorrect flat request:

```json
{
  "mode": 0,
  "upEnable": true,
  "upUnit": 2,
  "upLimit": 2,
  "downEnable": true,
  "downUnit": 2,
  "downLimit": 2
}
```

returned:

```text
HTTP: 200
errorCode: -1001
msg: Invalid request parameters.
```

Correct runtime request:

```json
{
  "mode": 0,
  "customRateLimit": {
    "upEnable": true,
    "upUnit": 2,
    "upLimit": 2,
    "downEnable": true,
    "downUnit": 2,
    "downLimit": 2
  }
}
```

### 31.2 Physical 2/2 Mbps test

Mutation result:

```text
HTTP: 200
errorCode: 0
msg: Success.
```

Immediate Client Detail:

```json
{
  "enable": true,
  "upEnable": true,
  "upUnit": 2,
  "upLimit": 2,
  "downEnable": true,
  "downUnit": 2,
  "downLimit": 2
}
```

The Omada UI immediately displayed the limit created by OpenAPI.

Physical Speedtest on the same phone:

```text
Download: ~2 Mbps
Upload:   ~2 Mbps
```

This proves real data-plane shaping.

### 31.3 Public removal problem

A request with both directional controls disabled:

```json
{
  "mode": 0,
  "customRateLimit": {
    "upEnable": false,
    "upUnit": 2,
    "upLimit": 2,
    "downEnable": false,
    "downUnit": 2,
    "downLimit": 2
  }
}
```

was accepted but produced:

```json
{
  "enable": true,
  "upEnable": false,
  "upUnit": 2,
  "upLimit": 2,
  "downEnable": false,
  "downUnit": 2,
  "downLimit": 2
}
```

Adding top-level:

```json
{
  "enable": false,
  ...
}
```

was also accepted with `errorCode=0`, but `enable` remained `true`.

Therefore:

```text
The public /ratelimit endpoint can disable both directions,
but this did NOT restore the client read-back to global enable=false.
```

### 31.4 Omada UI internal API rollback

DevTools showed that the Omada UI performs full client-level disable through:

```text
PATCH /{omadacId}/api/v2/sites/{siteId}/clients/{clientMac}
```

with a payload containing:

```json
{
  "name": "BE-00-7D-9B-04-2E",
  "rateLimit": {
    "enable": false
  },
  "clientLockToApSetting": {
    "enable": false
  },
  "ipSetting": {
    "useFixedAddr": false
  }
}
```

After UI disable, public OpenAPI Client Detail again returned:

```json
{
  "enable": false,
  "upEnable": false,
  "upUnit": 1,
  "upLimit": 0,
  "downEnable": false,
  "downUnit": 1,
  "downLimit": 0
}
```

### Verdict

```text
Apply Custom Rate Limit: VERIFIED / Evidence D
Full public OpenAPI removal to enable=false: NOT VERIFIED
UI internal full-disable mechanism: INTERNAL_NOT_OPENAPI
Overall product status: VERIFIED_WITH_CONDITIONS
```

A production module must not assume that setting both directional flags false is identical to removing the Rate Limit configuration.

---

## 32. Rate Limit Profile — create, apply, physical effect, CRUD

### 32.1 Create temporary 5/5 Mbps profile

Temporary profile:

```text
RESEARCH_TEMP_RATE_LIMIT_2026_08
```

Created through public OpenAPI with:

```json
{
  "name": "RESEARCH_TEMP_RATE_LIMIT_2026_08",
  "downLimitEnable": true,
  "downLimit": 5000,
  "upLimitEnable": true,
  "upLimit": 5000
}
```

Result:

```text
HTTP: 200
errorCode: 0
```

Read-back:

```text
profileId: 6a7f836155a7613ec67f7846
downLimitEnable: true
downLimit: 5000
upLimitEnable: true
upLimit: 5000
defaultProfile: false
```

### 32.2 Apply profile to client

Request:

```json
{
  "mode": 1,
  "rateLimitProfileId": "6a7f836155a7613ec67f7846"
}
```

Result:

```text
HTTP: 200
errorCode: 0
```

Client Detail:

```json
{
  "rateLimitId": "6a7f836155a7613ec67f7846",
  "enable": true,
  "upEnable": false,
  "upUnit": 1,
  "upLimit": 0,
  "downEnable": false,
  "downUnit": 1,
  "downLimit": 0
}
```

Important runtime interpretation:

- `rateLimitId` and `enable=true` identify profile mode;
- Client Detail does not expand the effective profile's 5000/5000 values into the directional client fields.

Physical Speedtest:

```text
Download: ~5 Mbps
Upload:   ~5 Mbps
```

Therefore the profile was really enforced.

### 32.3 Profile CRUD update test

A second temporary profile was created:

```text
RESEARCH_TEMP_RATE_LIMIT_UPDATE_2026_08
```

Initial values:

```text
4000 / 4000 Kbps
```

Public:

```text
PUT /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}
```

updated it to:

```text
7000 / 7000 Kbps
```

with:

```text
HTTP: 200
errorCode: 0
```

Read-back confirmed the same `profileId` with the new values.

### 32.4 Cleanup

The 5/5 profile was detached from the test client by returning the client to `rateLimit.enable=false` through the known-good UI operation.

Both temporary profiles were deleted through public OpenAPI.

Final inventory:

```text
profiles total: 1
research profiles: 0
```

Only the original default profile remained.

### Verdict

```text
Rate Limit Profile GET:    VERIFIED
CREATE:                    VERIFIED
UPDATE (PUT):              VERIFIED
DELETE:                    VERIFIED
Assign to client:          VERIFIED
Physical shaping:          Evidence D
Overall:                   VERIFIED_SAFE as a profile-management primitive
```

Application to a client still inherits the general client Rate Limit full-disable caveat described above.

---

## 33. Lock-to-AP

### 33.1 Rollback-shape discovery

These disable requests were rejected:

```json
{
  "enable": false
}
```

and:

```json
{
  "enable": false,
  "aps": []
}
```

Both returned:

```text
errorCode: -1001
```

This disable request succeeded:

```json
{
  "enable": false,
  "aps": [
    "EC-75-0C-18-6F-F8"
  ]
}
```

### 33.2 Enable

The client was already associated to:

```text
EC-75-0C-18-6F-F8
```

Safe enable request:

```json
{
  "enable": true,
  "aps": [
    "EC-75-0C-18-6F-F8"
  ]
}
```

Result:

```text
HTTP: 200
errorCode: 0
```

Runtime read-back:

```json
{
  "enable": true,
  "aps": [
    {
      "name": "EC-75-0C-18-6F-F8",
      "mac": "EC-75-0C-18-6F-F8"
    }
  ]
}
```

The setting persisted after a delay.

The client remained:

```text
active=true
authStatus=2
blocked=false
```

Rollback with `enable=false` and the same non-empty AP list succeeded.

### Verdict

```text
Configuration/persistence/rollback: VERIFIED
Physical prevention of roaming between two APs: NOT VERIFIED
Overall: VERIFIED_WITH_CONDITIONS
```

A product implementation must preserve the discovered requirement that disable still needs a non-empty `aps` array on this runtime.

---

## 34. Reconnect

Reconnect had prior physical evidence for a pending wireless client.

The controlled series additionally tested an `AUTHORIZED` client.

### 34.1 Authorized-client test

Before:

```text
active: true
authStatus: 2
ip: 192.168.1.150
ssid: Zefer_Parki
apMac: EC-75-0C-18-6F-F8
```

Request:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
```

Result:

```text
HTTP: 200
errorCode: 0
```

Within approximately 1 second:

```text
active: false
authStatus: null
ip: null
ssid: null
apMac: null
uptime: null
```

The phone physically lost Wi-Fi access.

It did **not** automatically rejoin on the tested Android device even after an extended observation period.

The auth record at that time remained:

```text
valid=true
```

After manual rejoin the client returned to:

```text
active=true
authStatus=2
same IP
same SSID
same AP
new low uptime
```

### Semantics established

```text
Reconnect = force wireless association teardown.
It is NOT a guarantee that the client OS will automatically reconnect.
It is NOT the same as Hotspot Unauth.
```

### Verdict

```text
Pending wireless client:   Evidence D
Authorized wireless client: Evidence D
Automatic OS rejoin:        NOT guaranteed
Wired client behavior:      not tested; documented -41025
Non-captive SSID behavior:  not tested
Overall: VERIFIED_WITH_CONDITIONS
```

---

## 35. Block / Unblock

### 35.1 Unblock no-op / rollback probe

Calling public `Unblock` against an already unblocked client returned:

```text
HTTP: 200
errorCode: 0
blocked: false
```

and did not disrupt the session.

### 35.2 Block

Before:

```text
blocked: false
active: true
authStatus: 2
```

Public `Block` result:

```text
HTTP: 200
errorCode: 0
```

Within approximately 1 second:

```text
blocked: true
active: false
authStatus: null
ip: null
ssid: null
apMac: null
```

Physical observation:

```text
The phone immediately lost Internet access.
```

### 35.3 Unblock

Public `Unblock` result:

```text
HTTP: 200
errorCode: 0
```

State:

```text
blocked: false
active: false
```

The phone did **not** reconnect automatically.

At that time the prior Authentication Record could still be returned as `valid=true`.

After a manual Wi-Fi rejoin, the Captive Portal opened and normal portal authorization occurred before Internet access returned.

A subsequent auth-record read did **not** necessarily create a new record for that portal appearance; the prior current record could remain the latest valid record with its duration advanced.

### Important semantics

```text
Block:
  tears down current access and sets a persistent blocked state.

Unblock:
  only removes the blocked state.
  It does not reconnect the client.

authed-record.valid=true:
  must NOT be treated as sufficient proof that a future rejoin will skip captive flow.
```

### Verdict

```text
Block:   VERIFIED / Evidence D
Unblock: VERIFIED / state and physical recovery behavior confirmed
Overall: VERIFIED_SAFE with explicit UX/reconnect semantics
```

---

## 36. Hotspot Unauth

Before:

```text
active: true
authStatus: 2
blocked: false
```

Request:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/unauth
```

Result:

```text
HTTP: 200
errorCode: 0
msg: Success.
```

Within approximately 1 second:

```text
active: false
authStatus: null
blocked: false
```

Physical observation:

```text
The phone immediately lost Internet access.
```

The previously active Authentication Record changed from:

```text
valid=true
```

to:

```text
valid=false
```

and its `end` timestamp was moved to the actual early termination time.

This directly answers the Stage A Cisco-topology question:

```text
Hotspot Unauth DOES work in this production topology
even though guest routing/DHCP is provided by Cisco rather than an Omada Gateway.
```

### Semantics established

```text
Unauth != Block
Unauth != Reconnect

Unauth explicitly terminates the Hotspot authorization record.
```

### Verdict

```text
VERIFIED_SAFE / Evidence D
```

---

## 37. Hotspot Auth

A controlled race test was used to capture the short-lived pending state before the normal portal flow completed.

Preparation:

1. current authorized client was `Unauth`ed;
2. client went offline;
3. script polled Client Detail every ~0.2s;
4. owner manually rejoined `Zefer_Parki`;
5. script captured:

```text
active=true
authStatus=1
uptime=22
```

before the Pending Session Cleaner threshold.

The script immediately called:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/auth
```

Result:

```text
HTTP: 200
errorCode: 0
msg: Success.
```

Within approximately 0.5s:

```text
active=true
authStatus=2
blocked=false
same IP
same SSID
same AP
```

The state remained authorized at later checks.

### Important limitation

The normal CaptivPortal flow was also active in the same time window, and the owner later reported that normal authorization had also occurred around the test.

Therefore the research can safely conclude:

```text
OpenAPI Auth was accepted while the client was definitely PENDING,
and the controller state immediately became AUTHORIZED.
```

But it does **not** claim an isolated physical proof that:

```text
OpenAPI Auth alone bypassed the normal CaptivPortal flow
with the portal completely prevented from participating.
```

### Verdict

```text
PENDING -> AUTHORIZED controller transition: VERIFIED
Independent CaptivPortal-bypass physical proof: NOT isolated
Overall: VERIFIED_WITH_CONDITIONS
```

---

## 38. Authentication Record runtime behavior

During the live series, the current test MAC accumulated/returned real authentication records containing:

- `id`
- `name`
- `mac`
- `wireless`
- `ssid`
- `authType`
- `download`
- `upload`
- `duration`
- `start`
- `end`
- `valid`
- `adminName`
- `ip`

Typical active record:

```text
valid=true
authType=10
adminName=Portal
```

The normal authorization window was consistently:

```text
end - start = 28,800,000 ms = 8 hours
```

Historical records were returned with `valid=false`.

Important observed behavior:

- one portal/rejoin event does not necessarily imply one newly created record visible immediately;
- `valid=true` alone is not sufficient to infer future captive-flow behavior;
- `Unauth` reliably changes the current authorization to `valid=false`.

---

## 39. Modify Authentication Period — exact semantics

Active record used for the semantics test:

```text
id: 6a7f89d955a7613ec67f78f9
old window: 28,800,000 ms
```

Request:

```json
{
  "period": 600000
}
```

Result:

```text
HTTP: 200
errorCode: 0
msg: Success.
```

Read-back:

```text
old_end:       1786772057660
new_end:       1786772657660
end_delta_ms:  600000
new_window_ms: 29400000
```

Therefore exact runtime semantics on Controller 5.14.31 are:

```text
new_end = old_end + period
```

It does **not** mean:

- set total authorization duration to `period`;
- set expiration to `now + period`.

It means:

```text
extend the existing authorization expiration by period milliseconds.
```

The client remained:

```text
active=true
authStatus=2
```

during the extension.

### Cleanup

Because negative period rollback was not established, the test did not attempt to subtract 600000 ms.

Instead:

1. Hotspot `Unauth`;
2. normal portal reauthorization;
3. final read verified a new active record with:

```text
window_ms: 28800000
```

The temporary +10-minute extension was fully eliminated.

### Verdict

```text
VERIFIED
Semantics established exactly.
```

Product meaning:

```text
"Extend session by N"
```

is a valid direct interpretation.

```text
"Set session expiry to arbitrary timestamp"
```

is NOT established by this endpoint.

---

# Part IV — Internal Omada UI API observations

## 40. Internal client PATCH

The Omada web UI was observed through browser DevTools.

UI client modifications used an internal endpoint:

```text
PATCH /{omadacId}/api/v2/sites/{siteId}/clients/{clientMac}
```

This is **not** the public:

```text
/openapi/v1/...
```

contract.

### Rate Limit ON through UI

Example meaningful payload fragment:

```json
{
  "rateLimit": {
    "rateLimitId": "6a64f17630da7c70d2321882",
    "enable": true
  }
}
```

### Rate Limit OFF through UI

Meaningful payload fragment:

```json
{
  "rateLimit": {
    "enable": false
  }
}
```

The full observed UI payload also included current client fields such as:

```json
{
  "name": "BE-00-7D-9B-04-2E",
  "clientLockToApSetting": {
    "enable": false
  },
  "ipSetting": {
    "useFixedAddr": false
  }
}
```

### Classification

```text
INTERNAL_NOT_OPENAPI
```

This research used the UI itself for safe rollback, but does **not** authorize the future CaptivPortal product to call undocumented internal Omada endpoints.

The preferred product policy remains:

```text
Use supported public OpenAPI.
Treat private UI API only as research evidence of Controller capability,
not as a stable supported integration contract.
```

---

# Part V — Final capability matrix

## 41. Direct client-control matrix

| Capability | Public OpenAPI | Live result | Evidence | Final status |
|---|---|---|---|---|
| Read active client list | Yes | Works with required pagination | C | VERIFIED_SAFE |
| Read known/offline client | Yes | Direct detail works while list omits offline card | C | VERIFIED_SAFE |
| Rename Client | Yes | Apply, persistence, search, rollback | state effect | VERIFIED_SAFE |
| Custom Rate Limit apply | Yes | 2/2 Mbps read-back + physical 2/2 | D | VERIFIED_WITH_CONDITIONS |
| Fully remove Custom Rate Limit to `enable=false` | Public endpoint insufficient in tested forms | UI internal PATCH works | C | INTERNAL_NOT_OPENAPI for proven full-disable mechanism |
| Rate Limit Profile GET | Yes | Live | C | VERIFIED_SAFE |
| Rate Limit Profile CREATE | Yes | Live | C | VERIFIED_SAFE |
| Rate Limit Profile UPDATE | Yes | 4000/4000 -> 7000/7000 | C | VERIFIED_SAFE |
| Rate Limit Profile DELETE | Yes | Live cleanup | C | VERIFIED_SAFE |
| Apply Rate Limit Profile | Yes | 5/5 profile physically produced ~5/5 Mbps | D | VERIFIED_SAFE with client-disable caveat |
| Lock-to-AP enable | Yes | Applied and persisted | C | VERIFIED_WITH_CONDITIONS |
| Lock-to-AP disable | Yes | Works only with non-empty `aps` in tested runtime | C | VERIFIED_WITH_CONDITIONS |
| Multi-AP roaming prevention | N/A to one-AP test | Not physically tested | — | SCHEMA_CONFIRMED / future test |
| Reconnect pending wireless | Yes | Prior physical disconnect verified | D | VERIFIED_WITH_CONDITIONS |
| Reconnect authorized wireless | Yes | Physical disconnect verified | D | VERIFIED_WITH_CONDITIONS |
| Automatic client rejoin after Reconnect | No guarantee | Moto did not auto-rejoin | D observation | CONDITION |
| Block | Yes | `blocked=true`, active session removed, Internet lost | D | VERIFIED_SAFE |
| Unblock | Yes | `blocked=false`; no automatic reconnect | D observation | VERIFIED_SAFE |
| Hotspot Unauth | Yes | Client removed, Internet lost, auth record `valid=false` | D | VERIFIED_SAFE |
| Hotspot Auth | Yes | Captured PENDING -> AUTHORIZED immediately | C/state effect | VERIFIED_WITH_CONDITIONS |
| Modify Authentication Period | Yes | `new_end = old_end + period` | state effect | VERIFIED_SAFE as “extend session” |
| Direct Disconnect path | Not found | known `/disconnect` probe 404 | — | UNSUPPORTED_ON_5_14_31 as tested path |
| Delete/Known Client | Not found as direct public Client OpenAPI | Not tested through private UI API | — | UNSUPPORTED as direct public primitive |
| Reboot ordinary endpoint client | Not found | Not tested | — | NOT_APPLICABLE / unsupported direct primitive |
| Fixed IP direct Client mutation | Not found | Current DHCP is Cisco | — | Infrastructure-dependent |
| Batch client mutations | Generic Batch exists | Not live tested | B | SCHEMA_CONFIRMED only |
| Wired Reconnect | Public Reconnect documented error `-41025` | No managed wired test client | A/B | NOT VERIFIED / likely unsupported |
| Non-captive Reconnect behavior | Endpoint exists | No safe dedicated non-captive test SSID | — | NOT VERIFIED |

---

## 42. Product recommendation — Candidate v1

The following functions are strong candidates for a future CaptivPortal **Client Control v1**:

### Read / inspection
- client state;
- active/offline distinction;
- authentication state;
- block state;
- Rate Limit state;
- Lock-to-AP state;
- authentication record history.

### Direct actions
- Rename Client;
- Reconnect wireless client;
- Block;
- Unblock;
- Hotspot Unauth;
- Hotspot Auth with explicit pending-state validation;
- Extend Authentication Period;
- Apply Custom Rate Limit;
- Apply Rate Limit Profile;
- Rate Limit Profile CRUD;
- Lock-to-AP configuration with runtime validation.

---

## 43. Product recommendation — conditions and safeguards

### 43.1 General mutation guard

Every action should use:

```text
baseline
-> permission/action validation
-> mutation
-> check HTTP
-> check errorCode/msg
-> immediate Client Detail/read-back
-> verify expected state
-> user-visible result
-> rollback path where applicable
```

Never treat:

```text
HTTP 200
```

as success by itself.

### 43.2 Reconnect

UI/product text should not promise:

```text
"Reconnect the device automatically"
```

Better semantics:

```text
"Force Wi-Fi reconnect / disconnect current association"
```

because the client OS may remain disconnected until the user reconnects.

### 43.3 Block / Unblock

Unblock should not imply:

```text
"Restore connection now"
```

It only removes the blocked state.

### 43.4 Hotspot Unauth

This is the clearest public OpenAPI primitive for:

```text
revoke current Hotspot authorization
```

and should be kept distinct from Block.

### 43.5 Authentication Period

Expose as:

```text
Extend authorization by:
+10 minutes
+30 minutes
+1 hour
...
```

Do not represent the tested endpoint as:

```text
set absolute expiry
```

without further research.

### 43.6 Custom Rate Limit removal

This is the major product caveat.

The public endpoint successfully applies Custom Rate Limit, but the research did not establish a supported public call that fully returns:

```text
rateLimit.enable=false
```

The UI internal API can do it, but private API should not be adopted as a stable product contract without a separate explicit architecture decision.

Possible product strategies:

1. do not expose Custom Rate Limit until a supported full-clear method is found;
2. expose it only if rollback can be safely expressed through a supported profile/state design;
3. re-research newer Omada Controller/OpenAPI versions;
4. treat private UI API use as a separate high-risk compatibility adapter, not normal OpenAPI integration.

### 43.7 Lock-to-AP

Before general product exposure:

- add a real multi-AP roaming test;
- validate AP inventory before sending `aps`;
- preserve the runtime requirement for non-empty `aps` on disable;
- prevent Block and Lock-to-AP conflicts.

---

## 44. Candidate later / infrastructure-dependent

Keep outside initial direct Client Control:

- Fixed IP / DHCP reservation;
- IP-MAC Binding;
- ACL manipulation;
- MAC filtering;
- Gateway QoS;
- application control;
- broad SSID/global bandwidth policy.

These are infrastructure policy capabilities, not simple client controls.

In the current deployment, Cisco is the authoritative guest router/DHCP layer, so Omada Gateway-specific semantics must not be assumed.

---

## 45. Do not expose without additional research

- destructive Batch client actions;
- ordinary endpoint Reboot;
- Delete Client / historical client-card deletion;
- private/internal Omada UI API calls;
- multi-client mass block/disconnect operations;
- Fixed IP mutation in the current Cisco DHCP topology;
- operations against non-designated production visitors without product-level authorization/audit controls.

---

# Part VI — Final cleanup and post-test state

## 46. Cleanup audit

At the end of all controlled mutation tests, a final public OpenAPI audit returned:

### Client

```text
mac: BE-00-7D-9B-04-2E
name: BE-00-7D-9B-04-2E
blocked: false
active: true
authStatus: 2
ip: 192.168.1.150
ssid: Zefer_Parki
```

Rate Limit:

```json
{
  "enable": false,
  "upEnable": false,
  "upUnit": 1,
  "upLimit": 0,
  "downEnable": false,
  "downUnit": 1,
  "downLimit": 0
}
```

Lock-to-AP:

```json
{
  "enable": false
}
```

### Rate Limit Profiles

```text
profiles total: 1
research profiles: 0
```

Only:

```text
По умолчанию
defaultProfile=true
```

remained.

### Current authorization

```text
valid records: 1
window_ms: 28800000
```

The active authorization was restored to the normal **8-hour** window.

### Cleanup verdict

```text
PASS
```

No temporary Rename, Block, Rate Limit, Lock-to-AP setting, extended auth period or research Rate Limit Profile remained.

---

# Part VII — Unresolved research gaps

## 47. Remaining gaps

The following questions remain intentionally unresolved:

1. **Custom Rate Limit supported public full-clear**
   - find a public OpenAPI operation that restores `enable=false`, or confirm none exists on 5.14.31.

2. **Lock-to-AP physical roaming behavior**
   - requires at least two adopted APs with a safe test movement/roaming scenario.

3. **Hotspot Auth isolated portal-bypass test**
   - prevent/hold the normal CaptivPortal auth worker long enough to prove OpenAPI Auth alone provides end-to-end Internet access, without changing production behavior unsafely.

4. **Wired client behavior**
   - requires an Omada-managed wired client, not the current Cisco-switch/routing environment.

5. **Non-captive SSID Reconnect**
   - requires a dedicated safe non-captive laboratory SSID.

6. **Batch mutation**
   - requires dedicated disposable clients before destructive batching.

7. **Delete Client / Reboot Client**
   - no direct public primitives were discovered; UI correlation could be researched separately if product value justifies it.

8. **Fixed IP**
   - should be researched only in a topology where Omada is actually authoritative for DHCP/IP control.

9. **Event/webhook timing evidence**
   - the current controlled mutation series focused on OpenAPI state/read-back and physical effects; no claim is made here that every mutation has a separately correlated normalized-webhook T4 timestamp.

---

# Part VIII — Final verdict

## 48. Overall research conclusion

On **Omada Software Controller 5.14.31**, public OpenAPI is sufficient to build a substantial future **CaptivPortal Client Control** subsystem without relying on undocumented private endpoints for most core functions.

Strongly verified direct capabilities include:

```text
Read Client State
Rename
Reconnect
Block / Unblock
Hotspot Unauth
Rate Limit Profile CRUD
Rate Limit Profile assignment
Custom Rate Limit application
Authentication Period extension
Lock-to-AP configuration
```

Hotspot Auth is also live-working at the controller state-transition level, with one remaining isolation test if the product requires proof of a complete CaptivPortal bypass path.

The most important current public-API gap is:

```text
full removal of a client Custom Rate Limit back to
rateLimit.enable=false
```

which was proven through the Omada UI internal API but not through the tested public `/ratelimit` contract.

The controller also exposes many broader Network Policy capabilities, but they should remain architecturally separate from direct per-client controls.

**Final research status: COMPLETE for direct Client Control discovery and the authorized controlled mutation series, with explicit unresolved gaps listed above.**

---

## Appendix A — Key public endpoints

```text
GET    /openapi/v1/{omadacId}/sites/{siteId}/clients
GET    /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}

PATCH  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/name
PATCH  /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/ratelimit

POST   /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/block
POST   /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/unblock
POST   /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
POST   /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/lock-to-ap

GET    /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles
POST   /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles
PUT    /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}
DELETE /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}

GET    /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records
POST   /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records/{id}/period
POST   /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/auth
POST   /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/unauth

POST   /openapi/v1/{omadacId}/batch
```

---

## Appendix B — Key tested runtime request bodies

### Rename

```json
{
  "name": "RESEARCH-MOTO-G85"
}
```

### Custom Rate Limit — 2/2 Mbps

```json
{
  "mode": 0,
  "customRateLimit": {
    "upEnable": true,
    "upUnit": 2,
    "upLimit": 2,
    "downEnable": true,
    "downUnit": 2,
    "downLimit": 2
  }
}
```

### Apply Rate Limit Profile

```json
{
  "mode": 1,
  "rateLimitProfileId": "<profile-id>"
}
```

### Create Rate Limit Profile — 5/5 Mbps

```json
{
  "name": "RESEARCH_TEMP_RATE_LIMIT_2026_08",
  "downLimitEnable": true,
  "downLimit": 5000,
  "upLimitEnable": true,
  "upLimit": 5000
}
```

### Lock-to-AP enable

```json
{
  "enable": true,
  "aps": [
    "EC-75-0C-18-6F-F8"
  ]
}
```

### Lock-to-AP disable — tested working runtime form

```json
{
  "enable": false,
  "aps": [
    "EC-75-0C-18-6F-F8"
  ]
}
```

### Extend authentication by 10 minutes

```json
{
  "period": 600000
}
```

---

## Appendix C — Critical interpretation rules for future implementation

```text
HTTP 200 != success.
Always inspect errorCode/msg.
```

```text
Client List != all known clients.
Direct Client Detail can return an offline historical card.
```

```text
Reconnect != guaranteed automatic reconnect.
```

```text
Unblock != reconnect.
```

```text
Block != Hotspot Unauth.
```

```text
authed-record.valid=true != guarantee that a future rejoin skips captive flow.
```

```text
Authentication Period period = extension delta in milliseconds.
new_end = old_end + period.
```

```text
Profile-mode Client Detail may not expand effective profile bandwidth values.
Use the profile object itself as the authoritative configured profile values.
```

```text
Custom Rate Limit public apply is physically verified.
Public full-clear to rateLimit.enable=false remains unresolved.
```

```text
Omada UI private /api/v2 is evidence of capability,
not automatically an approved product integration contract.
```
