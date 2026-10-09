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
