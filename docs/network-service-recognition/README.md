# NI-04 Unified55 — read-only Service Intelligence

Status: implementation candidate; not accepted for publication or activation.
Authority: Unified55 Implementation Contract v1, architecture v1 + normative R1,
and TechLead22 bounded category-cardinality clarification 01.

## Knowledge and claim boundary

55 entries are research/catalog scope, not 55 admitted recognitions.
`NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json` is the corrected immutable R1 catalog
(SHA256 `70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7`).
The runtime loader never reads this document or `unified55-launch-scope-v1.json`.
The latter reports all 55 rows separately: candidate hostname, semantic approval,
bundle admission, direct-SNI capability and non-admission reason.

Only the five exact Lane A rules are in the local runtime tuple. Exact first-party
Service-specific web hostname evidence is not proof of opening a native app,
sending a message or streaming media. Unknown/limited evidence is not inactivity.
X and VK remain ARCH_HOLD. ChatGPT repair is not rule admission. Additional actual
rules require a new reviewed immutable tuple and sources/negative fixtures, not
another matcher or API. Synthetic 55-Service tests never enter runtime knowledge.

Category vocabulary is closed to ten IDs; concrete artifacts contain 1..10
categories. Lane A retains three and R1 synthetic reference one. Every Service
references a present category. No autofill, silent repair or original-byte change.

## Immutable local tuple (all version 1)

| Artifact ID | Semantic SHA256 |
|---|---|
| captivportal.network-intelligence.recognition-taxonomy | 7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278 |
| captivportal.network-intelligence.recognition-knowledge | 7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210 |
| captivportal.network-intelligence.service-recognition | 46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a |

Raw byte identities are independently asserted in focused tests. Review interval:
2026-10-11T20:04:00.000000Z through 2027-01-09T20:04:00.000000Z (exclusive due).
Evaluation uses the earliest manifest/rule/referenced-source expiry. Artifact
validation is atomic and immutable, with exact cross-digests and closed schemas.

## Read and publication boundaries

1. Existing Admin authorization and Device gateway supply exact Site/Device/MAC.
2. NI-02B supplies one read-only snapshot with authoritative binding and bounded
   outbound external facts. No query-time IP reattribution.
3. Its transaction closes before NI-01 exact-ref batches open. NI-01 verifies
   provenance and retention; original DNS answer ordinals are preserved.
4. The entire cross-store set is verified before matching. Only retained direct
   TLS/QUIC SNI may positively resolve a Service. DNS cannot do so in V1.
5. Public DTOs expose labels and times, never protected DNS/SNI/endpoints/refs.

Global NI-04 active read slot: one. Deadline: min(shared deadline, five seconds).
Max 5000 facts/unique refs/ephemeral observations, batches of 256, 25000 hostname
scalars. Source overflow fails closed; only Recent Services may be truncated to
12 with recognition limited. Categories <=10. No cache of raw evidence, writes,
schema changes, source workers, new DB or new history storage.

GET-only route:
`/admin/api/v1/sites/<site_id>/devices/<device_id>/service-intelligence`.
No query/body/time parameters. Same Site and `admin.read.device`; authentication
precedes evidence access. Exact error codes, 429 Retry-After 1, no-store/no-cache,
16-KiB complete envelope ceiling (response_too_large). NI-03 remains independent.

Device Card is a separate Service Intelligence section. First read on visibility,
120-second refresh, one in-flight request with manual coalescing, 10-second timeout,
120/300/600-second failure backoff, hidden/pagehide suspension and terminal
401/403/404 stop. Last-good safe DTO expires at 900 seconds. No browser storage.
Rendering uses textContent and scoped responsive CSS; manual browser acceptance
is still required and is not inferred from Node tests.

## Deployment-owned main-process handoff — NOT executed

Default `WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED=false` flows through
app/config.py -> app/settings.py -> existing run.py/Admin composition. No second
feature flag, Settings mutation, new worker or run.py entrypoint is needed.

Before any separate Owner-authorized activation, Owner must arrange read-only
main-process access to the existing NI-01/NI-02B DBs and the existing environment
contracts `/etc/captive-portal/network-metadata.env` and
`/etc/captive-portal/network-metadata-projection.env`. These are parsed only by
`network_metadata_config_from_env()` and `projection_config_from_env()` from the
process environment; the application does not open/rewrite these env files.
Any systemd EnvironmentFile change, permissions check or restart requires a
separate deployment decision. Do not start source/projection writers in main.

Flag OFF constructs no NI-04 dependencies and shows no new section. When ON, bad
source configuration/artifact composition disables only NI-04 with a safe static
diagnostic. Existing Portal/Auth/CAPPORT/Admin/NI-03 readiness is unchanged.

Rollback is Owner-controlled: set this existing deployment-owned flag false and
adopt it through the separately approved restart flow. No DB migration/recovery
is necessary. If code rollback is needed after a future merge, Owner reverts the
exact future accepted publication commit(s) through Git; no deployment from this
uncommitted patch and no reset of unrelated history.

## Verification ownership

Coder focused scope: tests/network_service_recognition and the two new Admin
Python test files. `lab_acceptance.py` is prepared but NOT executed: native Linux
clean-tree, disposable real NI-01/NI-02B fixtures, 5000 TLS and 25000 DNS scalar
read cases, ten read samples, RSS delta <=64 MiB, p50/p95/max and DB immutability.
Owner/TL may explicitly run `python -m tests.network_service_recognition.lab_acceptance`
after assigning an immutable Lab candidate and confirming the environment.
This resource preparation does not claim writer-pressure or portal latency PASS.

Mandatory Owner/TL release checks still include native Linux focused execution,
real NI-01/NI-02B writer/read coexistence and capacity/checkpoint/retention pressure,
RSS/latency, non-feature Portal/Auth/CAPPORT differential latency/regression,
NI-03 compatibility, desktop/mobile browser/accessibility, and refreshed official
full test-set acceptance. Production is not a test/performance host.
No V7/full/Linux/PERF acceptance claim is made by this candidate.
