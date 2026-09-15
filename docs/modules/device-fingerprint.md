# Device Fingerprint Evidence

Status: **current; default disabled**.

TASK-DEVICE-FINGERPRINT-01 provides a passive, isolated foundation for storing
normalized mobile/personal-device fingerprint evidence. It does not ship a
sensor, capture packets, classify devices, link identities, call Omada, or
change Portal/Admin/Analytics behavior.

## Runtime boundary

For `TASK-DEVICE-FINGERPRINT-01`, the only authorized auxiliary entrypoint is:

```text
python3 -m app.device_fingerprint.cli run
```

It owns a dedicated direct-TLS Flask app at
`/api/internal/device-fingerprint/v1`, a schema-v1 SQLite writer and one bounded
retention thread. It is not registered into `run.py` or the main CaptivPortal
Flask app. The repository default `DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false`
exits normally before logger, identity, lock, database, thread, app, or listener
creation.

## Data and security

The database contains only normalized P1 device-evidence rows and immutable
point-in-time source-health rows. Evidence schemas are registered locally before
the registry is frozen; Task-02 registers four bounded network schemas and
Task-03 adds normalized `portal_headers/1`. Unknown
schemas fail closed. Retention is based on `observed_at` (configured
1–90 days for evidence and fixed 30 days for source health).

Every endpoint is protected by exact Bearer authentication and direct-peer CIDR
authorization. Producer identity is bound to one Site and capture source plus
configured guest CIDRs/source kinds. Proxy headers are ignored. Secrets, TLS
material, production producer records and production databases remain external
to Git.

The frozen initial deployment mapping (without its external secret) is
`sensor-zefer-01` → capture source `zefer-span-01` → Site
`6a64f17630da7c70d232187a`, guest CIDR `192.168.8.0/22`, with authorized source
kinds `dhcp`, `tcp_syn`, `tls_client`, and `quic_client`. The Task-02 sensor
captures raw DHCP/TCP through an attached kernel BPF and consumes minimized
TLS/QUIC EVE over a Unix datagram socket. Only normalized bounded envelopes are
written to its DELETE-journal transport spool; raw frames and EVE are never
durable.

The authoritative accepted design and verification contract is
`TASK-DEVICE-FINGERPRINT-01-FINAL.md`.
Task-02 extends only the reserved schema-registry boundary and is governed by
`TASK-DEVICE-FINGERPRINT-02-FINAL.md` plus FINAL ADDENDUM-1.
Task-03 reuses the same API/DB boundary through the isolated asynchronous portal
producer described in `docs/modules/device-fingerprint-portal.md`; it adds no
second database or classifier.
