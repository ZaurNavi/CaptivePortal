"""One request, one bounded projection snapshot, no upstream queries/cache."""
import threading
from datetime import timedelta

from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.device_fingerprint.validation import validate_site_id
from app.network_attribution.validation import canonical_mac
from app.network_metadata.validation import canonical_uuid, ni_timestamp, ni_format_utc
from app.network_metadata.models import NetworkMetadataValidationError
from app.network_metadata_projection.models import ProjectionUnavailable, ProjectionValidationError
from .models import (
    PROTOCOLS, DeviceProtocolSummaryV1, ProtocolWindowV1, ProtocolCoverageV1,
    RecentProtocolV1, LastProtocolObservationV1, ProtocolValidationError,
    ProtocolUnavailable, ProtocolBusy, ProtocolDeadline, freshness, public_summary,
)

# Shared by all NI-03 service instances within this process, not a cache.
_READ_SLOTS = threading.BoundedSemaphore(2)
_COVERAGE = {
    "usable": ("usable", "usable", "usable"),
    "registry_degraded": ("degraded", "usable", "usable"),
    "attribution_unavailable": ("degraded", "usable", "degraded"),
    "source_unavailable": ("degraded", "unavailable", "unknown"),
    **{state: ("degraded", "degraded", "degraded") for state in
       ("capacity_waiting_reader", "capacity_halted", "blocked_conflict", "degraded")},
    **{state: ("degraded", "unknown", "unknown") for state in ("initializing", "stopping")},
}


class DeviceProtocolIntelligenceReadService:
    def __init__(self, projection_reader):
        self._reader = projection_reader

    def get_device_protocol_summary(self, site_id, device_id, client_mac, *, evaluated_at_utc, deadline):
        try:
            validate_site_id(site_id)
            canonical_uuid(device_id)
            if canonical_mac(client_mac) != client_mac:
                raise ValueError
            at = ni_timestamp(evaluated_at_utc, canonical=True)
        except Exception:
            raise ProtocolValidationError() from None
        if not _READ_SLOTS.acquire(blocking=False):
            raise ProtocolBusy()
        try:
            # The shared deadline's clock also owns the local five-second cap.
            bounded = QueryDeadline(min(deadline.expires_at, deadline.monotonic() + 5), deadline.monotonic)
            bounded.require_remaining()
            start, recent = at - timedelta(days=1), at - timedelta(hours=1)
            snapshot = self._reader.read_protocol_evidence_snapshot(
                site_id, device_id, client_mac, ni_format_utc(start), evaluated_at_utc,
                max_rows=20000, deadline=bounded)
            bounded.require_remaining()
            if set(snapshot) != {"runtime_state", "binding_state", "bound_device_id", "facts"}:
                raise ProtocolUnavailable()
            try:
                projection, source, attribution = _COVERAGE[snapshot["runtime_state"]]
                identity = {"authoritative": "authoritative", "not_yet_registry_resolved": "pending",
                            "registry_unavailable": "unavailable", None: "absent"}[snapshot["binding_state"]]
            except (KeyError, TypeError):
                raise ProtocolUnavailable() from None
            coverage = ProtocolCoverageV1("current_pipeline", source, attribution, projection, False)
            facts = snapshot["facts"]
            if len(facts) > 20000 or (identity != "authoritative" and facts):
                raise ProtocolUnavailable()
            if identity == "authoritative" and snapshot["bound_device_id"] != device_id:
                raise ProtocolUnavailable()
            if identity != "authoritative" and snapshot["bound_device_id"] is not None:
                raise ProtocolUnavailable()
            latest = {}
            ordered = []
            for row in facts:
                bounded.require_remaining()
                if set(row) != {"edge_id", "event_at", "source_event_family"}:
                    raise ProtocolUnavailable()
                protocol = row["source_event_family"]
                if protocol not in PROTOCOLS or not isinstance(row["edge_id"], str):
                    raise ProtocolUnavailable()
                event = ni_timestamp(row["event_at"], canonical=True)
                if not start <= event < at:
                    raise ProtocolUnavailable()
                rank = tuple(PROTOCOLS).index(protocol)
                ordered.append((event, rank, row["edge_id"], protocol))
                if event >= recent and (protocol not in latest or event > latest[protocol]):
                    latest[protocol] = event
            ordered.sort(key=lambda item: (at - item[0], item[1], item[2]))
            last = None if not ordered else LastProtocolObservationV1(
                ordered[0][3], PROTOCOLS[ordered[0][3]], ni_format_utc(ordered[0][0]))
            result = DeviceProtocolSummaryV1(
                1, site_id, device_id, evaluated_at_utc,
                ProtocolWindowV1(ni_format_utc(start), evaluated_at_utc, 86400, ni_format_utc(recent), 3600),
                "usable" if projection == "usable" and identity == "authoritative" else "degraded",
                "identity_pending" if identity != "authoritative" else "present" if last else "empty",
                identity, tuple(RecentProtocolV1(p, PROTOCOLS[p], ni_format_utc(t)) for p, t in
                    sorted(latest.items(), key=lambda item: (at - item[1], tuple(PROTOCOLS).index(item[0])))),
                last, "unavailable" if last is None else freshness((at - ordered[0][0]).total_seconds(), coverage), coverage)
            public_summary(result)
            return result
        except AnalyticsQueryDeadlineExceeded:
            raise ProtocolDeadline() from None
        except ProjectionValidationError:
            raise ProtocolValidationError() from None
        except ProjectionUnavailable:
            raise ProtocolUnavailable() from None
        except NetworkMetadataValidationError:
            raise ProtocolUnavailable() from None
        finally:
            _READ_SLOTS.release()
