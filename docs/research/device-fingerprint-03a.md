# Device Fingerprint 03A research matrix

`TASK-DEVICE-FINGERPRINT-03A` provides lab-only tooling for a controlled,
manually labeled evidence matrix. It is a dataset-format and export foundation,
not a classifier, production feature, or production collection service.

## Boundaries

- Production code, schemas, APIs, retention, authorization, and deployment are
  unchanged.
- The dependency direction is `research/device_fingerprint_03a` toward approved
  `app.device_fingerprint` read and validation helpers only.
- The exporter uses read-only/query-only SQLite access and revalidates every
  payload against the frozen production schema registry.
- Only `dhcp/1`, `tcp_syn/1`, `tls_client/1`, `quic_client/1`, and
  `portal_headers/1` are accepted.
- Samples use exact half-open `[window_start_utc, window_end_utc)` windows of at
  most 600 seconds.
- Source-health records remain point events. Silence is not converted into an
  unavailable interval.

## Privacy and ground truth

Ground truth is manually established from controlled devices before fingerprint
interpretation. Physical grouping uses a random lab UUID. Cross-MAC binding is
manual and exists only in the private staging ledger. No fingerprint similarity
is used for identity or labeling.

Sealed matrices exclude MAC, IP, raw User-Agent, raw Client Hints, SNI, DNS
history, cookies, credentials, person identity, and personal device identifiers.
The private binding ledger is not checksummed into or copied to the sealed
matrix.

## Lifecycle

The exporter produces an unsealed package. Explicit manual Owner verification
is required before the sealing operation writes the canonical timestamp and the
sole checksum authority. Actual matrices live outside Git and expire 180 days
after sealing unless Owner and Tech Lead explicitly extend retention.

Physical calibration, collection, production-host access, deployment, and any
future classifier work require separate authorization.
