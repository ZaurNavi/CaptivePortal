# Device Fingerprint Portal Evidence

Status: **implemented; repository default disabled**.

TASK-DEVICE-FINGERPRINT-03 adds passive normalized evidence from the existing
Omada External Portal and resolved CAPPORT login requests. It reads only the
bounded `User-Agent`, `sec-ch-ua`, `sec-ch-ua-platform`, and
`sec-ch-ua-mobile` values. Raw headers, their hashes, cookies, authorization,
URLs, high-entropy Client Hints, and JavaScript fingerprint signals are never
queued, logged, or persisted.

Eligible requests are normalized in the request thread and handed off with
`put_nowait()` through a bounded 256-item FIFO. A non-blocking, 8192-entry,
six-hour coalescer prevents portal refresh floods. The daemon worker named
`device-fingerprint-portal` sends batches of at most 50 normalized P1 events to
the existing direct-TLS Task-01 API. Delivery, credential, CA, queue, parser,
and telemetry failures are contained and never change authorization results.

The producer identity is fixed to `portal-zefer-01`, capture source
`zefer-portal-http-01`, Site `6a64f17630da7c70d232187a`, guest CIDR
`192.168.8.0/22`, and optional corroborating SSID `Zefer_Parki`. The production
schema registry adds only `portal_headers/1`; no classifier, DB, API, collector,
or identity-linking model is introduced.

Configuration is isolated under `DEVICE_FINGERPRINT_PORTAL_*`; the default is
`DEVICE_FINGERPRINT_PORTAL_ENABLED=false`. The Bearer credential and CA trust
file remain external to Git. Production activation is a separate Owner action.
