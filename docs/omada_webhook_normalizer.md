# Omada webhook normalizer

The normalizer is the second stage of the permanent Omada webhook
integration:

```text
Omada Controller
        |
        v
omada_webhook.log                 raw source of truth
        |
        v
pure normalizer
        |
        v
omada_webhook_normalized.log      one JSON event per text[] item
```

Raw capture is completed synchronously before normalization starts. If
normalization or the normalized journal fails after that point, the
receiver still returns its successful HTTP response. The raw record can
be processed later with the backfill CLI.

The normalizer does not call Omada OpenAPI, correlate authorization
sessions, change portal behavior, or claim that disconnect traffic is
Captive Portal traffic.

## Output

The live output path is configured with:

```text
OMADA_WEBHOOK_NORMALIZED_LOG_FILE=/opt/CaptivePortal/logs/omada_webhook_normalized.log
```

The file is strict UTF-8 JSON Lines, uses rotation compatible with the
raw journal, and is created with mode `0640` on POSIX. Python does not
run `chown`, `chgrp`, or `sudo`; the service identity and setgid log
directory provide the expected `admin:telemetry` ownership.

Every event contains the fixed common schema:

```json
{
  "timestamp": "2026-07-28T11:34:28.989Z",
  "level": "info",
  "service": "captive_portal",
  "module": "omada_webhook_normalizer",
  "event": "omada.client_online",
  "schema_version": 1,
  "normalized_event_id": "webhook-uuid:0",
  "webhook_id": "webhook-uuid",
  "text_index": 0,
  "text_count": 1,
  "received_at": "2026-07-28T11:34:28.989Z",
  "controller_timestamp": "2026-07-28T11:34:28.934Z",
  "controller_timestamp_ms": 1785238468934,
  "delivery_latency_ms": 55,
  "source_ip": "192.168.0.222",
  "site": "Home",
  "controller_name": "Omada Controller_051C41",
  "payload_sha256": "original-body-sha256",
  "parse_status": "parsed",
  "parse_reason": null,
  "parse_warnings": [],
  "raw_text": "original text[] item"
}
```

Supported event names are:

- `omada.client_online`
- `omada.client_offline`
- `omada.client_unauthorized`
- `omada.client_connection_failed`
- `omada.webhook_unclassified`

Each supported event type has a fixed type-specific schema. Missing
values are `null`; list fields are always arrays.

Every `omada.webhook_unclassified` additionally contains the following
fixed diagnostic fields:

```json
{
  "source_line_number": null,
  "source_line_sha256": null,
  "exception_type": null
}
```

Backfill diagnostics populate these fields without copying the source
line or an exception message.

## Parse contract

```text
parsed:
  recognized event with no warnings

partial:
  recognized event with one or more parse_warnings

unclassified:
  unusable text structure or unknown event format
  parse_reason contains the primary reason
```

MAC-only client and AP names are valid Omada fallbacks and do not create
warnings. A missing client IP is allowed but creates
`CLIENT_IP_MISSING`, because it reduces future correlation quality.
Offline channel, duration, and traffic can be absent without warnings.
Present but invalid duration or traffic is partial.

## Event handler registry

Recognized controller text is dispatched through the ordered Python
tuple `EVENT_HANDLERS`. Every registry entry contains an `event_name`,
a matcher, and a parser. The first matching entry wins. A matcher may
be a compiled-pattern adapter or a local match function when an event
has a stricter structural contract.

Adding another Omada event requires a local matcher, parser, and
registry entry. The central normalization flow does not contain
event-specific `if`/`elif` dispatch and does not load external YAML,
JSON, or plugin code.

## Connection failures

The normalizer supports two exact reasons observed in controller
messages:

```text
MAC block/MAC Filter/Lock To AP -> ACCESS_POLICY_BLOCKED
password was wrong             -> WRONG_PASSWORD
```

Both are normalized under the existing event:

```text
event=omada.client_connection_failed
failure_source=omada_controller
```

The reason comes directly from Omada Controller. The normalizer does
not infer why a password was wrong or which individual Omada policy
caused a blocked connection, and therefore does not claim broader or
more specific reasons. `controller_reason_raw` preserves the extracted
controller text, including its original case and internal spacing.
Matching is case-insensitive and whitespace-tolerant.

The supported occurrence form accepts either `time` or `times`,
independently of the count:

```text
N time in the last minute
N times in the last minute
```

It maps to `occurrence_count=N` and
`occurrence_window_seconds=60`. The supported count range is
`1..999999`. A recognized reason remains a
`omada.client_connection_failed` partial event when the channel,
count, or window is missing or invalid.

Unconfirmed reason variants remain `omada.webhook_unclassified`.
Additional semantic words after a recognized reason also prevent
classification. After the reason, only whitespace, punctuation around
the technical occurrence block, or a missing/damaged occurrence block
are accepted. The previously supported structural fallback
`N attempts recently` remains a partial event; arbitrary text merely
starting with a number is not treated as an occurrence block.

Traffic is reported by Omada for the Wi-Fi connection at disconnect.
It is stored as the original value plus
`reported_traffic_bytes_estimate`, calculated with binary multipliers,
`Decimal`, and `ROUND_HALF_UP`. It is not labelled as Captive Portal
traffic.

## Time contract

Controller timestamps accept an integer millisecond value or a string
containing only that integer. Values must fall between 2000-01-01 and
2100-01-01.

Negative latency is retained. Latency below `-100 ms` adds
`NEGATIVE_DELIVERY_LATENCY`; latency above `10000 ms` adds
`HIGH_DELIVERY_LATENCY`.

`received_at` is required as the canonical event time. Missing values
produce `RECEIVED_AT_MISSING`; invalid types, timezone-free datetimes,
and malformed values produce `RECEIVED_AT_INVALID`. Invalid values are
not copied into normalized `timestamp` or `received_at`. Valid values
are converted to `YYYY-MM-DDTHH:MM:SS.mmmZ`.

## Failure telemetry

After raw persistence, failures never add fake normalized events:

```text
omada.webhook_normalization_failed
omada.webhook_normalized_write_failed
```

The events contain only secret-safe identifiers, exception type, and an
error code. Exception messages, payload content, HTTP headers,
`shardSecret`, `raw_body`, and `raw_body_base64` are not copied into the
normalized journal.

## Backfill

Process an accumulated raw journal into a separate output:

```bash
python -m app.integrations.omada.normalize_log \
  --input /opt/CaptivePortal/logs/omada_webhook.log \
  --output /opt/CaptivePortal/logs/omada_webhook_normalized.backfill.log
```

An existing output is protected unless one explicit mode is selected:

```text
--overwrite
--append
```

The modes are mutually exclusive. Empty lines are skipped. A damaged
raw line produces a deterministic `INVALID_RAW_JSON` diagnostic using
only its line number and SHA-256; its raw bytes are never copied into
the normalized output.

An internal normalizer exception is different from invalid JSON. The
CLI writes a secret-safe `NORMALIZATION_FAILED` diagnostic, continues
with later lines, increments `Normalization failures`, and exits
nonzero after processing finishes. Exception messages and source
content are not copied.

The CLI prints:

```text
Raw records processed: 100
Text items processed: 126
Normalized events: 124
Partial events: 8
Unclassified events: 2
Invalid raw lines: 0
Normalization failures: 0
```

## Batch persistence semantics

`append_many()` keeps all events from one webhook contiguous with
respect to other application threads, but it is not an atomic
transaction.

```text
Batch is contiguous but not atomic.
Partial batch persistence is possible.
Recovery/backfill may create duplicate normalized_event_id.
Consumers must deduplicate by normalized_event_id.
```

For example, if the second append fails, the first event may already be
a complete valid JSONL line. The write error identifies the event that
failed. The raw journal remains the recovery source.

## Verification

```bash
pytest -q
python -m compileall -q app
git diff --check
```

Grafana Alloy collection for the live normalized journal is documented
separately in `docs/omada_webhook_alloy.md`. Alloy reads only the
active `.log`; rotated files are local archives. Backfill output must
not overwrite the active live journal.
