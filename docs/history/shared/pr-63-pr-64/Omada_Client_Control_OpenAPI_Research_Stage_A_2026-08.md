# Omada Client Control OpenAPI Research — Stage A Interim Report

**Project:** CaptivPortal  
**Research:** Omada Client Control / Policy  
**Controller:** Omada Software Controller 5.14.31  
**Date:** 2026-08-14  
**Status:** Stage A complete — ready for Stage B (OAuth read-only live verification)

---

## 1. Purpose of Stage A

Stage A was limited to non-destructive reconnaissance:

- inventory the actual OpenAPI surface exposed by the production Omada Controller 5.14.31;
- identify direct client-control operations;
- identify indirect policy-related API groups;
- extract request schemas, read-back fields, permissions, documented errors and API-version information;
- classify unsupported / not-yet-found operations without performing live mutation;
- prepare a verification contract for Stage B/C/D work.

No production mutation was performed during Stage A.

---

## 2. Swagger inventory

The Controller exposes the following Swagger groups:

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

Root inventory:

- total operations: **641**
- mutations in `00 All`: **383**
- client/policy keyword candidates from initial broad filter: **208**

All 13 grouped Swagger documents returned HTTP 200 and valid JSON.

The apparent mutation count difference between `00 All` and the sum of named groups was investigated. The additional mutation operations were global webhook-management endpoints, not hidden client-control operations. Two additional read-only v2 topology endpoints were also present only in `00 All`.

---

## 3. Direct public Client OpenAPI surface

The following direct client operations are present in public OpenAPI v1.

### Read

- `GET /openapi/v1/{omadacId}/sites/{siteId}/clients`
  - Get client list

- `GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}`
  - Get client info

- `GET /openapi/v1/{omadacId}/sites/{siteId}/insight/past-connection`
  - Get client past connection list

### Mutations

- `POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/block`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/unblock`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/lock-to-ap`
- `PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/name`
- `PATCH /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/ratelimit`

Current evidence status for these operations is **SCHEMA_CONFIRMED** unless prior live evidence exists separately.

---

## 4. Hotspot / authentication OpenAPI surface

The Controller exposes:

- `GET /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records/{id}/period`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/auth`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/clients/{clientMac}/unauth`

Additional Hotspot APIs exist for local users and authentication surveys, but they are not direct endpoint-client control primitives.

---

## 5. Operations not found as direct public Client OpenAPI

No direct public endpoint was found in `05 Client` / `06 Hotspot` for:

- Disconnect / Kick
- Delete Client
- Reboot Client
- direct Client IP Setting mutation

Known prior probe of:

`POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/disconnect`

returned HTTP 404.

This is not yet sufficient to classify every possible Disconnect/Delete/Reboot behavior as unsupported, because UI/internal API correlation remains pending.

Current classification:

- Disconnect: direct public OpenAPI path not found; known `/disconnect` path returned 404.
- Delete Client: direct public OpenAPI path not found.
- Reboot Client: direct public OpenAPI path not found.
- Client IP Setting: read-back exists, but direct Client mutation path not found.

---

## 6. Lock-to-AP schema

Request:

```json
{
  "enable": true,
  "aps": [
    "AA-AA-AA-AA-AA-AA"
  ]
}
```

Schema facts:

- `enable` is required and boolean.
- `aps` is an array of AP MAC strings.
- AP MAC format is documented using uppercase letters and `-` separator.

Read-back fields:

- `clientLockToApSetting.enable`
- `clientLockToApSetting.aps`

Documented errors:

- `-41011` client does not exist
- `-41020` only wireless clients support Lock to AP
- `-41021` Lock-to-AP entry capacity reached
- `-41022` blocked clients cannot be locked to AP

Important interaction rule:

**Blocked client → Lock-to-AP is explicitly rejected by schema documentation.**

Multi-AP / roaming behavior remains NOT VERIFIED until the second EAP613 is adopted.

---

## 7. Client Name schema

Request:

```json
{
  "name": "..."
}
```

Schema facts:

- `name` is required.
- documented length: 1–128 characters.

Read-back:

- `name`

Open questions for live/UI work:

- empty-name behavior;
- Unicode handling;
- clear/reset semantics;
- persistence across reconnect/offline-online/controller restart.

---

## 8. Client Rate Limit schema

### Custom mode

`mode = 0`

Fields:

- `upEnable`
- `upUnit`
- `upLimit`
- `downEnable`
- `downUnit`
- `downLimit`

Units:

- `1 = Kbps`
- `2 = Mbps`

Range:

- `upLimit`: 1–1024
- `downLimit`: 1–1024

Current hypothesis for removing a custom limit:

- disable `upEnable` / `downEnable`

This must still be verified live; `0` is not permitted by the documented numeric range.

### Profile mode

`mode = 1`

Requires:

- `rateLimitProfileId`

Read-back:

- `rateLimit.mode`
- `rateLimit.rateLimitProfileId`
- `rateLimit.customRateLimit.*`

Documented errors:

- `-33732` Rate Limit profile does not exist
- `-41008` number of clients configured with Rate Limit reached the limit
- `-41011` client does not exist

The numerical capacity limit is not documented in the schema.

---

## 9. Rate Limit Profiles

Endpoints:

- `GET /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles`
- `POST /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles`
- `PUT /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}`
- `DELETE /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profile/{profileId}`

Profile fields:

- `profileId`
- `name`
- `downLimitEnable`
- `downLimit`
- `upLimitEnable`
- `upLimit`
- `defaultProfile` (read response)

Create-profile requirements:

- name required, 1–64 characters
- `downLimitEnable` required
- `upLimitEnable` required
- enabled limit value uses Kbps
- create range documented as 1–10485760 Kbps

Documented errors:

- `-33000` site does not exist
- `-33733` Rate Limit profile already exists
- `-33734` Rate Limit profile count reached the limit

Planned temporary research profile:

`RESEARCH_TEMP_RATE_LIMIT_2026_08`

It must not be assigned to production visitors and must be deleted after testing.

---

## 10. Authentication Period

Endpoint:

`POST /openapi/v1/{omadacId}/sites/{siteId}/hotspot/authed-records/{id}/period`

Request:

```json
{
  "period": 60000
}
```

Schema facts:

- `period` is required.
- unit: milliseconds.
- documented range:
  - minimum: 60,000 ms = 60 seconds
  - maximum: 86,400,000,000,000 ms = 1,000,000 days

Description uses wording equivalent to extending the valid time / extended timestamp.

Therefore exact runtime semantics still require live verification; it must not yet be interpreted as simply “set session duration to X”.

---

## 11. Client detail read-back contract

The following fields are explicitly available in client detail and will be used for verification:

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

`authStatus`:

- `0 = CONNECTED`
- `1 = PENDING`
- `2 = AUTHORIZED`
- `3 = AUTH-FREE`

### State

- `blocked`
- `active`
- `blockDisable`

### Fixed IP read model

- `ipSetting.useFixedAddr`
- `ipSetting.netId`
- `ipSetting.ip`

### Rate Limit

- `rateLimit.mode`
- `rateLimit.rateLimitProfileId`
- `rateLimit.customRateLimit.upEnable`
- `rateLimit.customRateLimit.upUnit`
- `rateLimit.customRateLimit.upLimit`
- `rateLimit.customRateLimit.downEnable`
- `rateLimit.customRateLimit.downUnit`
- `rateLimit.customRateLimit.downLimit`

### Lock-to-AP

- `clientLockToApSetting.enable`
- `clientLockToApSetting.aps`

### Link-rate clarification

- `rxRate` = wireless uplink negotiation rate in Kbit/s
- `txRate` = wireless downlink negotiation rate in Kbit/s

These are negotiated link rates, not proof of real throughput. They must not be used to verify Rate Limit effect.

---

## 12. Block / Unblock documented behavior

### Block

Permissions:

- `Site Clients Manager Modify`
- or `Site Insight Manager Modify`

Errors:

- `-41002` client does not exist
- `-41003` blocked-client capacity reached
- `-41023` clients locked to AP cannot be blocked
- `-41024` controller-installed device cannot be blocked
- `-41026` Easy Managed Switch cannot block clients

### Unblock

Permissions:

- `Site Clients Manager Modify`
- or `Site Insight Manager Modify`

Error:

- `-41004` client does not exist

Important interaction rule:

**Lock-to-AP client → Block is explicitly rejected by schema documentation.**

This complements the reverse `Blocked → Lock-to-AP` restriction.

---

## 13. Reconnect

Permission:

- `Site Clients Manager Modify`

Documented errors:

- `-41011` client does not exist
- `-41025` unable to reconnect wired client

Therefore the documented action is effectively wireless-client oriented on Controller 5.14.31.

Prior live evidence already exists for a pending wireless client:

- mutation accepted;
- client changed from `active=true` to `active=false`;
- client disappeared from active list;
- historical card remained.

A controlled Stage B/C/D series is still required for pending, authorized and non-captive scenarios defined in the research task.

---

## 14. Hotspot Auth / Unauth permissions and errors

### Auth

Permissions:

- `Site Clients Manager Modify`
- or `Site Hotspot Manager Modify`

Errors include:

- `-1005` operation forbidden
- `-1200` controller session/state error
- `-33004` conflicting site operation
- `-41009` failed to authorize client
- `-41010` client does not exist
- `-42003` operator does not exist
- `-42006` failed to log in
- `-44111` invalid grant type
- `-44112` access token expired
- `-7131` controller ID does not exist

### Unauth

Permissions:

- `Site Clients Manager Modify`
- or `Site Hotspot Manager Modify`

Errors include:

- `-1005`
- `-1200`
- `-33004`
- `-41006` client does not exist
- `-41017` unauth failed because gateway does not exist or is disconnected
- `-41018` unauth failed; retry after network recovery
- `-41019` client is being disconnected
- `-44111`
- `-44112`
- `-7131`

The production network currently uses Cisco routing/DHCP rather than a confirmed Omada Gateway.

Therefore `Unauth` dependency on Omada Gateway is a critical live-verification question. The existence of `-41017` is not proof that Unauth must fail in the current topology.

---

## 15. Read permissions

Client list / client detail:

- `Site Clients Manager View Only`
- or `Site Device Manager View Only`

Authentication records:

- `Site Hotspot Manager View Only`
- or `Site Insight Manager View Only`

Rate Limit Profiles read:

- `Site Settings Manager View Only`

Rate Limit Profiles create:

- `Site Settings Manager Modify`

Most direct client mutations require:

- `Site Clients Manager Modify`

Authentication-period mutation specifically requires:

- `Site Hotspot Manager Modify`

Swagger declares no standard OpenAPI `securitySchemes` for these groups; permission requirements are embedded in operation descriptions.

---

## 16. Batch OpenAPI

Endpoint:

`POST /openapi/v1/{omadacId}/batch`

Schema:

- `interrupt`: boolean, default behavior documented as true
- `actions`: up to 20 entries

Each action contains:

- `path`
- `method`
- `body`
- `query`

Allowed methods documented:

- POST
- PATCH
- PUT
- DELETE

File upload/download is not supported.

Documented errors:

- `-1001` invalid request parameters
- `-1600` unsupported request path
- `-1619` execution interrupted because previous action failed
- `-1620` action execution error
- `-44112` token expired
- `-44113` access token invalid
- `-7132` server receiving too many requests

No explicit permission is declared for the Batch endpoint itself.

Working hypothesis: permissions may be enforced per nested action. This remains NOT VERIFIED.

A schema inconsistency exists for `body`: OpenAPI type is shown as string while the description says it should be a JSON object and not a string. Live verification is required.

---

## 17. Indirect policy/control surface discovered

The Controller exposes public OpenAPI for the following policy domains.

### Bandwidth Control

Includes:

- global bandwidth-control state
- rule list
- create / modify / delete rules
- rule ordering
- SSID rate-limit configuration
- Rate Limit Profiles
- Gateway bandwidth-control objects

### Gateway QoS

Includes:

- bandwidth-control rules
- service profiles
- class rules
- outbound traffic tagging
- VoIP prioritization
- WAN-related QoS information

### ACL

Includes:

- EAP ACL
- Gateway ACL
- Switch ACL
- custom Gateway ACL
- ordering / hit-count operations

### MAC Filtering

Includes:

- global MAC-filter state
- allow/deny lists
- create / modify / delete filters
- SSID MAC-filter configuration

### IP-MAC Binding / DHCP

Includes:

- IP-MAC binding global state
- create / modify / delete binding
- batch-delete binding
- create DHCP reservation
- modify DHCP reservation
- export DHCP reservation to IP-MAC Binding

### Application Control

Includes:

- application catalogue
- families
- filters
- restrictions
- rules
- global status
- DPI data clear operation

These surfaces are candidates for a separate Network Policy / infrastructure-dependent subsystem and must not automatically be treated as direct per-client Client Control features.

---

## 18. Fixed IP finding

No direct Client mutation endpoint for `ipSetting` was found.

However, client detail exposes:

- `ipSetting.useFixedAddr`
- `ipSetting.netId`
- `ipSetting.ip`

The Site Setting API exposes DHCP reservation and IP-MAC Binding operations.

Production DHCP is provided by Cisco, not Omada Gateway.

Current classification:

**Infrastructure-dependent / not live-tested in production topology.**

Production Fixed IP mutation is not authorized for this research phase.

---

## 19. API version findings

Direct Client and Hotspot controls discovered so far use:

- `/openapi/v1/...`

Additional read-only topology endpoints exist in v2:

- `GET /openapi/v2/{omadacId}/sites/{siteId}/topology`
- `GET /openapi/v2/{omadacId}/sites/{siteId}/topology/devices/{mac}/clients`

No v2 direct mutation equivalent has yet been discovered for the direct client actions listed above.

---

## 20. Swagger error-contract finding

For the investigated direct mutations, formal HTTP responses expose only:

`HTTP 200: OK`

Operation-specific Omada errors are not represented as separate HTTP response codes; they are documented inside operation descriptions and are returned through response-body `errorCode/msg`.

Therefore:

**HTTP 200 is not success proof.**

Future live verification must check:

1. HTTP status
2. response-body `errorCode`
3. response-body `msg`
4. read-back
5. physical effect where applicable
6. event/webhook effect
7. rollback verification

---

## 21. Stage A current capability classification

| Capability | Stage A status |
|---|---|
| View client state | SCHEMA_CONFIRMED |
| Reconnect | SCHEMA_CONFIRMED + prior live evidence for pending wireless client |
| Block | SCHEMA_CONFIRMED |
| Unblock | SCHEMA_CONFIRMED |
| Authorize | SCHEMA_CONFIRMED |
| Unauthorize | SCHEMA_CONFIRMED |
| Custom Rate Limit | SCHEMA_CONFIRMED |
| Remove Rate Limit | likely represented by enable flags; live semantics NOT VERIFIED |
| Rate Limit Profile | SCHEMA_CONFIRMED |
| Lock-to-AP | SCHEMA_CONFIRMED |
| Unlock AP | schema strongly suggests `enable=false`; effect NOT VERIFIED |
| Rename | SCHEMA_CONFIRMED |
| Fixed IP | read model + infrastructure API discovered; direct client mutation not found |
| Read Auth Record | SCHEMA_CONFIRMED |
| Modify Auth Period | SCHEMA_CONFIRMED |
| Delete/Known Client | direct public OpenAPI not found |
| Reboot Client | direct public OpenAPI not found |
| Batch wrapper | SCHEMA_CONFIRMED |
| Batch client mutations | NOT VERIFIED |

---

## 22. Safety constraints carried into Stage B

- destructive/mutation tests only on the project owner's designated phone;
- stable MAC required for the main series;
- no visitor/staff/course-participant mutation;
- no destructive Batch tests until dedicated test clients exist;
- no production AP restart;
- no Controller restart;
- no Fixed IP production mutation;
- no live Reboot Client on ordinary phone;
- Pending Session Cleaner remains enabled;
- actual Cleaner process-environment values must be read before pending live scenarios;
- Visit Lifecycle is production-active;
- normalized webhook journal is the authoritative T4 timing source;
- mutations can create genuine offline/online events and close visits for the designated test MAC;
- secrets, access tokens and authorization headers must not be copied into the final report.

---

## 23. Exit criteria for Stage A

Stage A is considered complete because:

- full Swagger group inventory was obtained from the actual Controller;
- direct Client and Hotspot surfaces were enumerated;
- direct request schemas were extracted;
- read-back fields were identified;
- permissions were identified;
- operation-specific documented errors were extracted;
- indirect policy domains were discovered;
- unsupported/not-found direct operations were recorded without unsafe experimentation;
- Batch schema and errors were identified;
- v1/v2 presence was checked at the discovered surface level;
- a live-verification contract can now be defined.

---

# Stage B Entry

Stage B begins with **live but read-only OpenAPI verification** using the test OAuth application.

Planned first sequence:

1. obtain Access Token with `client_credentials`;
2. verify successful token response and expiry metadata;
3. `GET client list`;
4. `GET designated test client detail`;
5. `GET hotspot authentication records`;
6. `GET Rate Limit Profiles`;
7. verify actual permissions and response-body `errorCode/msg`;
8. record live response shapes without storing secrets/tokens.

No mutation is required to enter Stage B.

Subsequent controlled mutation work will proceed only when the owner is physically present with the designated test phone.

---

**Stage A verdict:** COMPLETE  
**Next:** Stage B — OAuth read-only live verification
