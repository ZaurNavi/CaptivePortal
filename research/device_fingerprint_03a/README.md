# Task-03A lab matrix tooling

This namespace contains operator-invoked, lab-only tooling for the
Multi-Platform Labeled Evidence Matrix. It is not imported by production
runtime code and does not implement classification or feature engineering.

The exporter reads the Task-01 SQLite database through its canonical read-only
boundary. A separately authorized environment record and a private staging
binding ledger are required. The ledger is never copied into the matrix.

The sealed dataset contains exactly:

- `manifest.json`
- `devices.jsonl`
- `device_states.jsonl`
- `samples.jsonl`
- `evidence.jsonl`
- `source_health.jsonl`
- `checksums.sha256`

Actual matrices and binding ledgers remain outside Git. Sealed matrices retain
normalized P1 evidence and provenance but exclude MAC, IP, raw headers, raw
packets, and person identity. The matrix retention is 180 days. A private
binding ledger has a maximum 30-day retention and should be deleted immediately
after successful sealing and verification.

Run the CLI as `python -m research.device_fingerprint_03a.cli`. Physical
calibration or collection requires the separate Owner-controlled
pre-collection environment gate.
