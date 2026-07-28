# Omada webhook receiver

The permanent receiver is embedded in the existing CaptivePortal Flask
process:

```text
POST /api/integrations/omada/webhook
```

It first persists an unchanged secret-safe raw record. A separate
processor then normalizes supported event strings without calling Omada
OpenAPI or changing authorization, retry, CAPPORT, and portal behavior.

## Configuration

The receiver reads these environment variables through the existing
settings layer:

```text
OMADA_WEBHOOK_ENABLED=false
OMADA_WEBHOOK_ALLOWED_IPS=
OMADA_WEBHOOK_AUTH_MODE=ip_only
OMADA_WEBHOOK_SHARED_SECRET=
OMADA_WEBHOOK_HEADER_TOKEN=
OMADA_WEBHOOK_MAX_BODY_BYTES=1048576
OMADA_WEBHOOK_LOG_FILE=/opt/CaptivePortal/logs/omada_webhook.log
OMADA_WEBHOOK_NORMALIZED_LOG_FILE=/opt/CaptivePortal/logs/omada_webhook_normalized.log
```

`OMADA_WEBHOOK_ALLOWED_IPS` is a comma-separated list of exact IPv4 or
IPv6 addresses. Whitespace is ignored. An empty list denies every
request. No controller IP or secret is committed to source control.

Supported authentication modes are:

- `ip_only`
- `omada_payload_secret`
- `header_token`

`omada_payload_secret` requires a non-empty
`OMADA_WEBHOOK_SHARED_SECRET` and compares it with the top-level
`shardSecret` JSON field. `header_token` requires a non-empty
`OMADA_WEBHOOK_HEADER_TOKEN` and compares it with the
`X-Omada-Webhook-Token` header. Both comparisons use
`hmac.compare_digest()`. Query-string authentication is not supported.

An unknown mode, invalid IP, invalid body-size limit, empty log path, or
missing secret for the selected secret mode stops application creation
with a controlled configuration error.

## Request-body boundary

The application rejects a declared `Content-Length` above the configured
limit before reading the body. Otherwise it reads at most
`OMADA_WEBHOOK_MAX_BODY_BYTES + 1` through Werkzeug's bounded
`request.stream`.

The receiver never reads the raw `wsgi.input` directly and never tries
to read beyond the request boundary declared by the WSGI server.
Framing errors where bytes on the connection exceed `Content-Length`
must be rejected by Nginx or the WSGI server. Chunked requests are
supported through a correctly terminated WSGI input stream.

## Journal contract

Accepted deliveries are synchronously appended as independent UTF-8
JSONL records. HTTP 204 is returned only after the append and flush
complete. The journal uses rotating files and creates the log file with
mode `0640` on POSIX. The configured parent log directory must already
exist.

Example with deliberately fake values:

```json
{"timestamp":"2026-07-28T12:30:02.950Z","level":"info","service":"captive_portal","module":"omada_webhook","event":"omada.webhook_received","schema_version":1,"webhook_id":"62dc9f43-40c7-4ef9-a886-6639ee29350e","received_at":"2026-07-28T12:30:02.950Z","source_ip":"192.0.2.10","http_method":"POST","request_path":"/api/integrations/omada/webhook","content_type":"application/json","content_length":65,"actual_body_length":65,"user_agent":"Omada Controller","query_parameters":{},"headers":{"Content-Type":"application/json"},"payload_sha256":"example-sha256","payload_format":"json","body_encoding":"utf-8","raw_body":"{\"shardSecret\":\"***REDACTED***\",\"event\":\"example\"}","raw_body_base64":null,"parsed_payload":{"shardSecret":"***REDACTED***","event":"example"},"parse_error":null,"decode_error":null}
```

The checksum is calculated from the exact original bytes. Sensitive
headers, query parameters, and recursive JSON fields are replaced with
`***REDACTED***`. If JSON redaction is needed, `raw_body` is rebuilt
from the safe payload so the original secret is not retained.

Rejected payloads are never written to this journal. Rejections and
write failures create secret-free structured events in the main
application log.

Every journal line is strict JSON. `NaN`, `Infinity`, and `-Infinity`
are classified as invalid JSON and stored as text. Serialization uses
`allow_nan=False` and ASCII escaping so a JSON surrogate escape cannot
produce an invalid UTF-8 journal line.

Repeated sensitive JSON keys are tracked while parsing. If any
sensitive key occurs, including an overwritten duplicate,
`raw_body` is rebuilt from the redacted payload.

## HTTP responses

```text
204  accepted and persisted
400  request body could not be read (invalid_request)
401  missing or invalid configured secret
403  source IP not allowed
404  module disabled
405  any non-POST method (Allow: POST)
413  declared or actual body exceeds the configured limit
500  accepted delivery could not be persisted or internal error
```

An unexpected receiver defect emits `omada.webhook_internal_error`
with only `webhook_id`, `source_ip`, and `error_type`. It is not
classified as a client rejection and does not include the payload or
exception message.

## Log-file ownership on the server

First verify the actual service identity:

```bash
sudo systemctl show captive-portal.service \
  -p User \
  -p Group \
  --no-pager
```

If the service runs as the current `admin:telemetry` identity, prepare
the existing log directory and files with that same ownership:

```bash
sudo test -d /opt/CaptivePortal/logs
sudo -u admin touch /opt/CaptivePortal/logs/omada_webhook.log
sudo -u admin touch /opt/CaptivePortal/logs/omada_webhook_normalized.log
sudo chown admin:telemetry \
  /opt/CaptivePortal/logs/omada_webhook.log \
  /opt/CaptivePortal/logs/omada_webhook_normalized.log
sudo chmod 0640 \
  /opt/CaptivePortal/logs/omada_webhook.log \
  /opt/CaptivePortal/logs/omada_webhook_normalized.log
```

If `systemctl show` reports a different user or group, substitute those
actual values. Do not create a root-owned `0640` file for an unprivileged
service. If the existing log directory is already writable by the
service identity, the receiver can create the file itself on the first
accepted webhook.

## Verification

Run the full automated checks before deployment:

```bash
pytest -q
python -m compileall -q app
```

Example local request in `ip_only` mode from an allowed source:

```bash
curl --fail-with-body \
  --request POST \
  --header 'Content-Type: application/json' \
  --data '{"event":"capture-test","unknown":{"value":42}}' \
  http://127.0.0.1:8088/api/integrations/omada/webhook \
  --write-out '%{http_code}\n'
```

The expected status is `204`, followed by exactly one new valid JSON
line in the configured journal.
