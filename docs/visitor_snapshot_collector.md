# Authorized Client Snapshot Collector

Status: superseded as normative contract
Current contract: [modules/authorized-client-snapshot.md](modules/authorized-client-snapshot.md)
Historical implementation details below are retained for reference.

Visitor Snapshot is a fail-open background subsystem. After an AuthRun
has been committed as `AUTHORIZED`, AuthWorker submits one immutable
request. The authorization result is never changed by submission,
controller, normalization, queue, telemetry, or journal failures.

The feature is disabled by default:

```text
VISITOR_SNAPSHOT_ENABLED=false
```

Production configuration is supplied by the process environment or
systemd. CaptivePortal does not automatically load `.env.example`.

## Data flow

```text
AuthWorker.finish_run(AUTHORIZED)
→ immutable AuthorizedClientSnapshotRequest
→ non-blocking bounded submit
→ OmadaProvider.get_client_snapshot()
→ strict normalization and recursive secret redaction
→ visitor_snapshots.log
```

The data journal contains only:

```text
visitor.client_snapshot.captured
visitor.client_snapshot.failed
```

Operational `visitor_snapshot_*` events use
`AuthorizationTelemetry.safe_emit_system()` and therefore remain
separate from the data journal. They never include the complete raw
controller result.

## Capacity and retry

Running capacity is `VISITOR_SNAPSHOT_MAX_WORKERS`; queued capacity is
`VISITOR_SNAPSHOT_MAX_PENDING`. Submit never waits for capacity.
A full queue creates a best-effort `queue_rejected` failed event without
calling Omada.

The provider is called at most three times: immediately, then after the
two configured retry delays. Transport exceptions, HTTP 408/429/5xx,
malformed successful responses, and Omada `-41011` are retryable.
Unknown nonzero Omada error codes are not assigned invented semantics
and are not retried.

For the permanent schema-v1 data contract, `attempts` is the number of
complete calls to `provider.get_client_snapshot()`. Each such provider
call includes the existing token flow and, when token acquisition
succeeds, the client GET. It must not be interpreted as only the number
of client GET requests.

`request_duration_ms` is the summed monotonic wall-clock duration of
those complete provider calls, including token acquisition and client
GET/response parsing, but excluding queue wait, retry sleep,
normalization, and JSONL writing.

## Identity and privacy

`snapshot_id` is UUIDv5 over `auth_session_id:canonical_mac`, using the
permanent schema-v1 namespace
`f69e1190-9a09-55fc-81c5-63fab0ce2703`.

The requested and returned MAC must match. Full device MAC, IP, SSID,
hostname, AP information, signal data, and the sanitized Omada result
may be stored. Token, client secret, authorization, cookie, and password
values are recursively replaced with `[REDACTED]`.

The JSONL writer uses UTF-8, strict JSON, compact records, rotation, and
POSIX mode `0640`. Invalid `NaN`, infinity, unsupported objects, and
unpaired Unicode surrogates produce `normalization_error`; the unsafe
raw result is not written.

## Lifecycle

`run.py` constructs one Omada Provider and shares it with AuthWorker,
CAPPORT, and Visitor Snapshot. On shutdown, the authorization executor
is drained before the snapshot collector stops accepting submissions.
Snapshot retry waits are interruptible and the collector shutdown is
bounded by `VISITOR_SNAPSHOT_SHUTDOWN_TIMEOUT_SECONDS`.
If accepted jobs remain at that deadline, the collector emits exactly
one `visitor_snapshot_drain_timeout` operational event before it signals
cancellation. The event contains only `component`, `timeout_seconds`,
and `unfinished_job_count`; it contains no client identifiers or raw
controller data.

The module does not add an API, frontend, database, Alloy, Loki,
Grafana, Nginx, or systemd change.
