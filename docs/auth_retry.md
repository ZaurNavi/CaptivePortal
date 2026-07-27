# Auth session retry

The portal keeps one `session_id` for the original authorization and all
manual retries. Each worker execution has its own `run_number` and internal
`run_token`; each manual retry also has a client-generated
`retry_request_id`.

## HTTP contract

```http
POST /auth/session/{session_id}/retry
Content-Type: application/json

{"retry_request_id": "UUID"}
```

The endpoint returns:

- `202` when a new run is accepted by the worker executor;
- `200` when a run is already active or the request UUID is a duplicate;
- `400` for a missing or invalid request UUID;
- `403` when the request IP does not own the session;
- `404` when the session does not exist;
- `409` when the current state is not retryable;
- `410` when the original session TTL has expired;
- `503` when a temporary worker submission failure occurs.

`retry_request_id` mappings remain in memory until the session is removed, so
the same request UUID is idempotent even after its run has finished. A request
UUID received while a run is already active is also bound to that active run.

## Runtime model

Auth sessions, run history, request-id mappings and locks are process-local.
The production web deployment must therefore use exactly one Python/WSGI
process (`workers=1`). Threads inside that process and the existing bounded
AuthWorker thread pool are supported.

A deployment with multiple WSGI processes requires shared session storage and
a cross-process atomic lock before it can be enabled.

An expired or otherwise finished run is no longer a current writable run,
even if its `run_number` and `run_token` still match the session fields. Late
provider responses are ignored and reported as `STALE_RUN_TOKEN`.

When cleanup is required, the user-visible state moves from `RESETTING`
directly to `FAILED`; a successful `unauthorize()` does not publish an
intermediate `RESET` state. The frontend still treats `RESET` as active for
compatibility with an in-flight response from an older server version.

## Telemetry

Every run ends with `auth.run_finished`. `auth.session_finished` is emitted
only for `AUTHORIZED`, `EXPIRED`, or a non-retryable final failure. Manual
runs additionally emit the `auth.retry_*` event family.

`run_token` is never exposed through HTTP or telemetry. The non-secret
`retry_request_id` is included in retry/run events for idempotency tracing.
