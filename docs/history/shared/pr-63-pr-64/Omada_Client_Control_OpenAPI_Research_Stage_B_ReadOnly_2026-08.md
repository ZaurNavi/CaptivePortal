# Omada Client Control OpenAPI Research — Stage B Interim Report

**Project:** CaptivPortal  
**Research:** Omada Client Control / Policy  
**Controller:** Omada Software Controller 5.14.31  
**Date:** 2026-08-14  
**Status:** Stage B read-only live verification complete

---

## 1. Scope

Stage B verified the Stage A findings against the live Omada Controller using the designated test OpenAPI application.

This stage was strictly read-only:

- OAuth `client_credentials`;
- client list;
- known/offline client detail;
- Rate Limit Profiles;
- Hotspot Authentication Records.

No client mutation was performed.

Secrets, access tokens and authorization headers are intentionally omitted.

---

## 2. OAuth client_credentials

Live request to the Controller succeeded.

Observed:

- HTTP status: `200`
- `errorCode: 0`
- message: `Open API Get Access Token successfully.`
- Access Token returned
- Refresh Token returned
- `expiresIn: 7200`
- `tokenType: bearer`

### Verdict

`client_credentials` compatibility on Omada Software Controller 5.14.31 is **LIVE VERIFIED**.

---

## 3. Client Detail — known/offline client

Test client:

`FA-D5-62-D4-EB-25`

Live result:

- HTTP `200`
- `errorCode: 0`
- `msg: Success.`
- client card returned successfully while `active=false`

Observed fields included:

- `mac`
- `name`
- `blocked`
- `active`
- `ipSetting`
- `rateLimit`
- `clientLockToApSetting`

Observed state:

- `blocked: false`
- `active: false`
- `ipSetting: {"useFixedAddr": false}`
- `clientLockToApSetting: {"enable": false}`

### Important finding

A known/offline client remains directly addressable through:

`GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}`

### Verdict

Known/offline client read-back is **LIVE VERIFIED**.

---

## 4. Runtime / Swagger divergence

Stage A Swagger described Rate Limit read-back using a nested structure containing:

- `mode`
- `rateLimitProfileId`
- `customRateLimit.*`

The live disabled-state response instead returned:

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

This is a material runtime/schema divergence.

Also observed:

- disabled `ipSetting` may serialize only `useFixedAddr`;
- disabled Lock-to-AP may serialize only `enable`.

### Conclusion

Swagger is not sufficient as the sole runtime response contract. Live read-back must be captured for each mutation scenario.

---

## 5. Client List

Initial request without paging returned HTTP `400`.

Swagger inspection confirmed required query parameters:

- `page`
- `pageSize`

`pageSize` documented range: `1–1000`.

The corrected request used:

- `page=1`
- `pageSize=100`
- `searchKey=FA-D5-62-D4-EB-25`

Live result:

- HTTP `200`
- `errorCode: 0`
- `totalRows: 0`
- returned rows: `0`

At the same time, direct Client Detail for that MAC succeeded and reported `active=false`.

### Finding

For this tested state:

- Client Detail returns the known/offline client;
- Client List does not return the same offline client.

### Verdict

Active-list vs known-client behavior is **LIVE VERIFIED for this offline state**.

---

## 6. Rate Limit Profiles

Live request:

`GET /openapi/v1/{omadacId}/sites/{siteId}/rate-limit-profiles`

Result:

- HTTP `200`
- `errorCode: 0`
- profiles: `1`

Observed profile:

- name: `По умолчанию`
- `defaultProfile: true`
- `downLimitEnable: false`
- `upLimitEnable: false`
- `downLimit: null`
- `upLimit: null`

### Finding

The default profile exists, but currently has no upload/download shaping enabled.

Disabled profile limits serialize as `null`, not `0`.

### Verdict

Rate Limit Profile read API is **LIVE VERIFIED**.

---

## 7. Hotspot Authentication Records

Swagger confirmed required query parameters:

- `page`
- `pageSize`

The endpoint supports `searchKey`, including matching on `client_mac`.

Live request was scoped to the designated test MAC.

Result:

- HTTP `200`
- `errorCode: 0`
- `msg: Success.`
- `totalRows: 0`
- returned rows: `0`

### Finding

The Authentication Records endpoint and corresponding OAuth permission are live-working.

However, no current matching auth record was returned for the designated stable MAC.

Therefore the runtime `auth record id` required by:

`POST /hotspot/authed-records/{id}/period`

has **not yet been obtained**.

### Verdict

Authentication Records read API: **LIVE VERIFIED**.

Authentication record identity / `id` shape for the test phone: **NOT YET OBSERVED**.

---

## 8. Stage B conclusions

The following are now live-verified on Controller 5.14.31:

- OAuth `client_credentials`;
- Access Token acceptance by OpenAPI;
- designated application read permissions;
- known/offline Client Detail;
- Client List with required pagination;
- distinction between active list and known/offline detail;
- Rate Limit Profile read API;
- Hotspot Authentication Records read API.

No mutation was executed.

---

## 9. Remaining items before mutation work

Before disruptive client-control tests:

1. owner must be physically present with the designated test phone;
2. stable MAC must be confirmed;
3. actual Pending Session Cleaner runtime parameters must be read from process environment;
4. baseline client state must be recorded;
5. normalized webhook journal must be used as T4 event-time source;
6. rollback must be defined before every mutation.

For `Modify Authentication Period`, a live auth record for the designated test MAC must first be created/observed so its record `id` can be captured.

---

## 10. Next phase

Recommended next controlled phase:

1. capture live baseline for the test phone;
2. verify Cleaner runtime parameters;
3. perform one mutation at a time;
4. record HTTP + `errorCode/msg`;
5. perform immediate Client Detail read-back;
6. verify physical effect where applicable;
7. capture normalized webhook event timing;
8. rollback;
9. verify restoration.

Suggested mutation order:

1. Rename Client
2. Custom Rate Limit
3. Rate Limit Profile
4. Lock-to-AP on the currently adopted AP, if safe
5. Reconnect
6. Block / Unblock
7. Hotspot Auth / Unauth
8. Modify Authentication Period after a matching auth record exists

The order prioritizes reversible and lower-impact actions before disruptive connectivity/authentication actions.

---

**Stage B read-only verdict:** COMPLETE  
**Next:** controlled mutation / effect-verification phase
