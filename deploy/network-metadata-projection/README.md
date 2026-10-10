# NI-02B deployment artifacts — NOT production activation

The independent worker is OFF by default. Installing/enabling/starting it,
creating a production DB, or changing upstream services requires separate
Owner/Tech Lead authorization and capacity admission. No main Portal composition
is changed. Stop the auxiliary service to roll back; upstream stores are never
modified and the derived projection store must not be destructively recreated.

The service runs as admin with fingerprint-sensor supplementary group solely
for read access to the NI-02A store. Existing directory/file ACLs must allow
read access; do not grant upstream write ownership to this service.

SQLite uses WAL, FULL synchronous writes, a single writer lock and a combined
main/WAL/SHM/journal hard cap (default 16 GiB, admitted range 64 MiB–64 GiB).
Every write reserves the fixed 16 MiB transaction headroom. Held readers defer
capacity recovery; they do not justify skipping checkpoints or deleting live
evidence. Reader retention/timeout is a consumer operational responsibility.

NI-01 source endpoints and Device edges have a maximum 14-day sensitive
lifetime. DNS/SNI and raw EVE are not duplicated. Registry lookup is exact MAC
only; late binding never mutates edge identity. NI-02A read-query interoperability
preserves original event timestamps, without changing the authority writer.

Copy the example environment only through an approved deployment procedure;
there is no automated install/start action in this package. Required upstream
configuration names are reused, not aliased. The service has ordering-only
After dependencies, never Requires/BindsTo/PartOf relationships.

# NI-03 main-process read configuration (separate activation authorization)

The optional NI-03 Device Card reader is default-OFF:
`WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED=false`.
It is deployment-owned, not a writable Settings → Features preference.
The main process uses only `projection_config_from_env()` and the existing
`NETWORK_METADATA_PROJECTION_*` authority. Disabled projection configuration
does not open an old projection DB. Invalid configuration isolates NI-03;
the existing Portal/Admin core remains available.

For a separately authorized deployment, install the supplied
`captive-portal-network-metadata-projection-read.conf` as
`/etc/systemd/system/captive-portal.service.d/20-network-metadata-projection-read.conf`.
It contains only `[Service]` and
`EnvironmentFile=-/etc/captive-portal/network-metadata-projection.env`.
The application does not install this file or restart services.

Activation collision gate:

1. `/etc/default/captive-portal` MUST NOT independently define
   `NETWORK_METADATA_PROJECTION_*`.
2. Every other key shared by `/etc/default/captive-portal` and
   `/etc/captive-portal/network-metadata-projection.env` MUST have semantically
   identical effective values.
3. Any mismatch means `ACTIVATION=HOLD`.

Do not introduce another projection environment file. Install/reload/restart
and production smoke checks remain Tech Lead/Owner actions, not Coder actions.
