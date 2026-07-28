# Grafana Alloy: normalized Omada webhook journal

This fragment tails only the active live normalized journal:

```alloy
loki.source.file "omada_webhook_normalized" {
  targets = [
    {
      __path__ = "/opt/CaptivePortal/logs/omada_webhook_normalized.log",
    },
  ]
  encoding   = "UTF-8"
  forward_to = [loki.process.omada_webhook_normalized.receiver]

  file_match {
    enabled     = true
    sync_period = "10s"
  }
}

loki.process "omada_webhook_normalized" {
  // Replace `default` with the name of the existing loki.write component.
  forward_to = [loki.write.default.receiver]

  stage.json {
    expressions = {
      event_timestamp     = "timestamp",
      event_name          = "event",
      event_level         = "level",
      parse_status_value  = "parse_status",
      schema_version_value = "schema_version",
    }
  }

  stage.timestamp {
    source                        = "event_timestamp"
    format                        = "RFC3339Nano"
    action_on_failure             = "skip"
    action_on_duplicate_timestamp = "fudge"
  }

  stage.static_labels {
    values = {
      job     = "omada_webhook_normalized",
      service = "captive_portal",
      module  = "omada_webhook_normalizer",
    }
  }

  stage.labels {
    values = {
      event          = "event_name",
      level          = "event_level",
      parse_status   = "parse_status_value",
      schema_version = "schema_version_value",
    }
  }

  stage.label_keep {
    values = [
      "job",
      "service",
      "module",
      "event",
      "level",
      "parse_status",
      "schema_version",
    ]
  }
}
```

The snippet assumes that the existing Loki destination is declared as
`loki.write "default"`. Change only the receiver reference when the
installed component has another name. Do not add a second
`loki.write` block if the server already has one.

## Timestamp behavior

`stage.json` parses the JSONL line and extracts the normalized
`timestamp`. `stage.timestamp` uses it as the Loki event timestamp.
The normalized timestamp is RFC 3339 UTC with milliseconds, which is
accepted by `RFC3339Nano`.

Some diagnostic records intentionally contain `"timestamp": null`
when `received_at` is missing or invalid. `action_on_failure = "skip"`
keeps those diagnostics and uses their ingestion timestamp instead of
inventing an event time.

## Label cardinality

Only bounded fields are indexed as labels:

```text
job
service
module
event
level
parse_status
schema_version
```

The full JSON line remains available to LogQL (`| json`), but the
following values must remain log fields and must not become labels:

```text
client_mac
client_ip
ap_mac
source_ip
webhook_id
normalized_event_id
payload_sha256
raw_text
site
controller_name
```

This avoids creating a separate Loki stream for every client, webhook,
IP address, or installation-defined name.

## Backfill isolation

Live collection uses only the active file:

```text
/opt/CaptivePortal/logs/omada_webhook_normalized.log
```

Backfill output must be written outside that glob, for example:

```text
/opt/CaptivePortal/backfill/omada_webhook_normalized.20260728.jsonl
```

Rotated files such as `.log.1` remain local archives and are not live
Alloy targets. Reading renamed rotations as new paths can resend
already processed events. Recovery from raw archives must use the
explicit normalizer backfill workflow. Never write backfill output to
the active `omada_webhook_normalized.log`; otherwise the same
normalized event can be ingested twice.

## Validation on the server

After adding the fragment to the existing Alloy configuration:

```bash
alloy validate /etc/alloy/config.alloy
sudo systemctl reload alloy
sudo journalctl -u alloy -n 100 --no-pager
```

Then verify in Grafana Explore:

```logql
{job="omada_webhook_normalized"} | json
```

For a recognized event, the displayed Loki timestamp must equal the
JSON `timestamp`. Confirm that the stream labels do not contain MAC,
IP, `webhook_id`, or `normalized_event_id`.

Official Alloy references:

- <https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/>
- <https://grafana.com/docs/alloy/latest/reference/components/loki/loki.process/>
