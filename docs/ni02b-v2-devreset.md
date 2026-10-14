# NI-02B External Peer V2 — implementation boundary

Baseline: `f324c1e157b71802acda14a797c0e0f6747b6276` / tree
`cbe9ac1d3efed53a3d66b60915b9f1c21e7caa5c`.

Normative priority: Architecture Exception v1 (SHA256
`565a2dc6cfab8021b79967bb4d40290449b57ad659e322d6ce7951723e863ee8`),
Implementation Contract v1, TechLead23 review. This is development tooling,
not authorization to reset, deploy, restart or activate production.

## WP0 authorized production-source inventory (before implementation)

- `app/network_metadata/projection_source.py`: event-time trust and one read-only reset snapshot.
- `app/network_metadata_projection/models.py`: V2 identity and NI-02B-local terminal.
- `app/network_metadata_projection/config.py`: closed explicit scope admission.
- `app/network_metadata_projection/schema.py`: exact fresh Core V2 and immutable reset floors.
- `app/network_metadata_projection/repository.py`: pin admission, floors distinct from processed checkpoints.
- `app/network_metadata_projection/service.py`: independent endpoint classification and floor consumption.
- `app/network_metadata_projection/cli.py`: composition only if required.
- `app/network_metadata_projection/read_service.py`: strict V2 status/read admission.
- `app/network_metadata_projection/recognition_read_service.py`: only required V2 interoperability.
- `app/network_metadata_projection/service_delivery_read_service.py`: strict V2 candidate admission.
- `app/network_metadata_projection/service_extension.py`: preserve Extension V1 over Core V2.
- `app/network_metadata_projection/validation.py`: only required closed validation.
- `app/network_metadata_projection/telemetry.py`: only required bounded safe reasons/counters.
- `app/network_protocol_intelligence/read_service.py`: only required V2 source admission, public V1 unchanged.
- `app/network_service_recognition/*`: only strictly necessary V2 interoperability, public V3 unchanged.
- `scripts/ni02b_v2_offline_bootstrap.py`: inert inspect/prepare/verify, no production switch.

Tests remain in existing focused test layouts. No Admin source, deployment files,
NI-01 writer, NI-02A, Fingerprint, Auth/CAPPORT, Registry or knowledge changes.
Any newly required production path outside this list requires TechLead approval.

## V1 → V2 reference matrix

| Boundary | Baseline assumption | V2 requirement |
| --- | --- | --- |
| models / service / repository | algorithm V1, emitted/run contract 1 | algorithm V2, contract 2 |
| schema / all inherited readers | Core signature and user_version 1 | exact Core V2, no migration/fallback |
| edge DTO | schema 1, same logical fields | schema 1 preserved; explicit projection contract 2 and closed terminal |
| pending | unavailable iff pending, closed snapshots | same invariants plus outside-guest terminal |
| feed candidate validator | projection contract 1 | projection contract 2; proven outbound guest source only |
| Extension V1 | separate 3-table signature | same extension version/signature, validated against exact Core V2 |
| NI-03 | inherits projection reader, public V1 | strict source V2, public V1 unchanged |
| NI-04 legacy / worker | inherits projection/recognition/delivery readers | strict source V2, unchanged matcher/coverage/public V3 |
| NI-04 serve | query-only materialization V1 | same V1 store/public V3; never source fallback |
| Admin | composed typed readers, no direct Core constant found | no source changes anticipated |

## Frozen operational boundaries

Scope admission is operator-provided pre-NAT guest-DHCP proof, not topology
discovery or public-Internet inference. Unknown scope blocks the entire affected
batch. Genuine guest DHCP gaps remain pending. Reset floors discard retained
normalized history; they are never evidence of processing.

Exactly NI-02B and NI-04 derived database groups may be selected by a separately
authorized operator. NI-01, NI-02A, Registry and all other stores are KEEP.
No executable destructive switch or service control is part of Coder tooling.
The two-store replacement is not atomic: interruption requires an offline hold
until both stores independently validate. Pre-V2 code is not a rollback target.

## Composition and scope proof

The independent NI-02B composition reads the explicit
`NETWORK_METADATA_PROJECTION_SCOPE_ADMISSION_JSON` operator statement only when
enabled. Disabled composition performs no admission/dependency I/O. There is no
fallback to current capture environment CIDRs, no public-IP shortcut and no
wildcard guest domain. Reordered object keys canonicalize deterministically;
duplicate members, NaN/Infinity, unrecognized keys, noncanonical CIDRs/UTC,
overlaps and unknown placement are rejected. The canonical statement and its
SHA256 are durably pinned; runs reference that admission through a foreign key.
Restart with changed proof rejects the store; topology requires re-admission.
The NI-02B-local projection result is explicitly `NetworkMetadataProjectionResultV2`;
the NI-01 source record remains V1 and the unchanged logical edge field shape
remains `DeviceNetworkMetadataEdgeV1` with `projection_contract_version=2`.

`tests/network_metadata_projection/support.py::scope_admission` and
`test_external_peer_v2.py::admitted_source` construct fully valid **synthetic**
examples from the exact disposable CaptureScopeBinding. No sample represents
current production topology. The operator must replace it with reviewed proof.
The complete canonical sample is
`tests/network_metadata_projection/fixtures/external_peer_scope_synthetic.json`.

Each generation is admitted, even when it has no rows. Each observation must
carry the exact binding's valid-from value and event time >= valid-from. Source
scope errors become `scope_admission_untrusted`; storage outages remain distinct.
The NI-02B-owned `EndpointDisposition` is not an NI-02A result and carries no
MAC/Device/binding for the outside terminal. In-guest authority rules are unchanged.

## Reset proof and transactions

`projection_scope_admission` pins the statement. `projection_source_reset_epoch`
pins epoch/time/admission/snapshot digest/count. `projection_source_reset_floors`
pins each generation, Site/source/scope/binding/valid-from, committed bounds and
the nullable exact retained normalized tail. These rows are immutable; exact
signature and closed-data validation are enforced by every projection reader.

Core schema, admission, epoch and all floors are committed in **one initial
transaction** by the offline bootstrap. Extension V1 is installed separately
under the same acquired writer lock; no PREPARED manifest is issued until both
stores validate. A crash at any stage leaves staging incomplete/offline, not a
permission to start it. No in-place V1 migration exists.

The source floor is never advanced. Source selection is strictly after
`max(floor, processed_checkpoint)`; the latter changes only with committed new
dispositions. The first floor-based commit verifies that boundary inside the
write transaction. Existing generation appends remain eligible, an empty tail
has no invented offset, and new generations start naturally. Canonical lineage
continues to validate when legitimate source retention removes old normalized
rows. No raw file size, source wall-clock cutoff or fabricated checkpoint is used.
Ordinary V2 writer startup refuses a store without an explicit bootstrap reset
epoch. Simply deleting the old derived DB and starting the service cannot
silently replay retained NI-01 history. A legitimately empty source snapshot
still has an explicit epoch with zero floors, not fabricated processing.

## Offline helper API (no execution authority)

Use the exact admitted interpreter from the repository root:

```text
python -m scripts.ni02b_v2_offline_bootstrap inspect|dry-run|prepare|verify
  --projection-target <absolute effective NI02B DB path>
  --materialization-target <absolute effective NI04 DB path>
  --keep-path <absolute effective protected DB path> [repeat for ALL protected stores]
```

- `inspect` (default) / `dry-run`: no writes, no SQLite connections or sidecar
  creation. Reports exact selected DB/sidecar groups, KEEP paths, quiescence
  prerequisite, and **unqualified on-disk header** versions. A WAL may contain
  newer state; this is not signature acceptance. Optional `--admission-file`
  validates the typed statement, not the physical topology.
- `prepare`: additionally requires `--source-path`, `--admission-file`, a new
  `--staging-dir`, `--writers-stopped` and `--readers-drained`. These flags are
  explicit operator assertions, **not** automatic proof that processes stopped.
  Only new staging files are written. Source must be in KEEP. Takes one query-only
  NI-01 transaction, creates fresh stores and immutable `prepared-pair.json`.
- `verify`: additionally requires `--manifest`, `--manifest-sha256` (reviewed and
  externally retained), and `--admission-file`. Re-reads both stores query-only,
  validates exact signatures/quick-check/FK/floors/emptiness and hashes/sizes.
  Symlinks, hardlinks, selected/protected aliases, nonempty WAL or journals,
  scope changes, malformed state or mismatched pair fail closed.

Verification never stops a process, switches/replaces a file or changes mode.
Query-only WAL validation can create SQLite's empty WAL/shared-index sidecars;
it never changes logical records. Outstanding WAL content is rejected, not
checkpointed. The externally retained manifest freezes database contents and
reset proof. Repeat prepare must use a **new** staging directory and epoch.

The source/target/KEEP inventory must originate from current effective config,
including NI-01, NI-02A, Registry, Auth/session/CAPPORT, Omada, Admin Settings and
all other stores. The helper cannot discover omitted consumers or prove physical
quiescence, mount topology or pre-NAT placement. Operator independent preflight
is mandatory; do not interpret a typed statement as auto-detected topology.

## Operator-only pair switch and rollback

No activate/delete/switch command is implemented. The separately approved
runbook owns these state transitions:

1. `PREPARED`: reviewed staging and externally retained manifest hash. Old stores
   remain untouched. NI-04 writer stopped first, NI-02B second; all NI readers
   drained, including transient Admin readers.
2. `REPLACED_NOT_STARTED`: operator replaces exactly the selected two DB groups,
   updates reviewed pair paths, independently records the new manifest hash.
   **Both readers and writers stay offline**, including after a one-file crash.
3. `VERIFIED`: qualified verification of both selected files as the same prepared
   pair; independent quiescence/KEEP checks and explicit Owner authority still
   required. No tool automatically starts services or interprets this as GO_SERVE.

Interruption: hold offline and reprepare/verify both stores with a newly approved
reset snapshot as necessary; never mix one old and one new DB. Preserve NI-01,
NI-02A, Registry and guest operations. No backup of discarded NI history is a
mandatory gate; exact paths and technical integrity are mandatory.

Start NI-02B V2 first, then NI-04 shadow against the fresh pair; confirm new-only
facts, genuine guest gaps and freshness. Owner-controlled 15-minute natural-load
acceptance and a separate GO_SERVE are mandatory. No pre-V2 rollback against V2
files. Disable NI readers/workers or forward-repair/reset under separate authority.

## Test ownership / honest limits

Local Coder targeted tests cover T01–T09/T11 deterministic portions, V2-01–V2-14,
closed versions, source concurrency, crashes, protected files and public API
compatibility. Existing guest-gap, temporal, capacity and immutable-edge checks
remain. The old frontend byte-identity test permits exactly the two authorized
projection status version-field changes; other NI-03/UI bytes remain frozen.

T10 / V2-15: the bounded disposable local load test reports timings/footprint
without claiming HDD or production acceptance. Physical HDD I/O, p95/p99 live
poll, 15-minute natural load, topology, deploy/reset/read-drain and activation
are pending Owner/TechLead operational gates. No Full Gate PASS, no universal
`usable`, no claimed disk recovery. DNS/SNI limits, real DHCP gaps and source
freshness remain independently visible. Full Project/Central gates belong to
TechLead, not Coder.
