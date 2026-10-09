"""Read-only Site/IP/event-time resolution with coverage-first precedence."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.device_fingerprint.validation import format_utc, parse_utc, validate_site_id
from app.device_fingerprint.models import DeviceFingerprintValidationError

from .models import NetworkMetadataAttributionResultV1, NetworkAttributionError, NetworkAttributionHorizonV1
from .repository import RETENTION_SECONDS
from .schema import validate_schema_contract
from .validation import read_query_values


def _read_coverage_is_continuous(connection, site, source, start, exact_end, floor_end):
    """Read-only T1 continuity over (confirmation, exact query instant]."""
    rows = connection.execute(
        "SELECT * FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_from<=? "
        "AND (coverage_until IS NULL OR coverage_until>?) ORDER BY coverage_from,coverage_id",
        (site, source, floor_end, start)).fetchall()
    through = parse_utc(start)
    for row in rows:
        beginning = parse_utc(row["coverage_from"])
        until = None if row["coverage_until"] is None else parse_utc(row["coverage_until"])
        if until is not None and until <= beginning:
            continue
        if (beginning > through or row["state"] != "usable"
                or (until is None and parse_utc(row["verified_through"]) < exact_end)):
            return False
        if until is None or until > exact_end:
            return True
        through = max(through, until)
    return False


class NetworkAttributionReadService:
    def __init__(self, config, *, clock=lambda: datetime.now(timezone.utc)):
        self.config, self.clock = config, clock

    def _open(self):
        paths = (Path(self.config.db_path), Path(self.config.db_path + "-wal"), Path(self.config.db_path + "-shm"))
        if sum(path.stat().st_size for path in paths if path.exists()) > self.config.max_db_bytes:
            raise NetworkAttributionError("attribution_store_unavailable")
        connection = sqlite3.connect(Path(self.config.db_path).resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=.5, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA busy_timeout=500")
            connection.execute("BEGIN")
            validate_schema_contract(connection)
            return connection
        except BaseException:
            connection.close()
            raise

    def get_authority_horizon(self, site_id):
        result = NetworkAttributionHorizonV1
        connection = None
        try:
            validate_site_id(site_id)
            if not self.config.enabled:
                return result("unavailable", site_id, reason="attribution_disabled")
            connection = self._open()
            row = connection.execute("SELECT first_usable_at,retained_from FROM authority_horizon WHERE site_id=?",
                                     (site_id,)).fetchone()
            if row is None:
                return result("unavailable", site_id, reason="authority_horizon_unavailable")
            first, retained = parse_utc(row[0]), parse_utc(row[1])
            if retained < first:
                raise NetworkAttributionError("authority_horizon_unavailable")
            return result("available", site_id, row[0], max(row[1], format_utc(self.clock() - timedelta(seconds=RETENTION_SECONDS))))
        except (sqlite3.Error, OSError, ValueError, NetworkAttributionError, DeviceFingerprintValidationError):
            return result("unavailable", site_id, reason="authority_horizon_unavailable")
        finally:
            if connection is not None:
                connection.close()

    def resolve_ipv4(self, site_id, ipv4, event_at):
        result = NetworkMetadataAttributionResultV1
        try:
            exact_query, floor_query = read_query_values(site_id, ipv4, event_at)
        except NetworkAttributionError:
            return result("invalid", "invalid_query")
        def result(state, reason=None, **values):
            values.setdefault("event_at", event_at)
            return NetworkMetadataAttributionResultV1(state, reason, **values)
        if not self.config.enabled:
            return result("unavailable", "attribution_disabled")
        connection = None
        try:
            connection = self._open()
            horizon = connection.execute("SELECT retained_from FROM authority_horizon WHERE site_id=?", (site_id,)).fetchone()
            if horizon is None:
                return result("unavailable", "authority_horizon_unavailable")
            retention = format_utc(self.clock() - timedelta(seconds=RETENTION_SECONDS))
            if exact_query < max(parse_utc(horizon[0]), parse_utc(retention)):
                return result("outside_historical_horizon", "outside_historical_horizon")
            coverage = connection.execute(
                "SELECT * FROM source_coverage WHERE site_id=? AND coverage_from<=? "
                "AND (coverage_until IS NULL OR ?<coverage_until)", (site_id, floor_query, floor_query)).fetchall()
            if not coverage or any(row["state"] != "usable" or
                                   (row["coverage_until"] is None and exact_query > parse_utc(row["verified_through"]))
                                   for row in coverage):
                return result("unavailable", "source_coverage_unavailable")
            sources = {row["capture_source_id"] for row in coverage}
            candidates = connection.execute(
                "SELECT * FROM binding_intervals WHERE site_id=? AND ipv4=? AND valid_from<=? AND ?<valid_until",
                (site_id, ipv4, floor_query, floor_query)).fetchall()
            for binding in candidates:
                if binding["capture_source_id"] not in sources:
                    return result("unavailable", "source_coverage_unavailable")
                # Mutable last_confirmed_at can be later than a historical query.
                # Consult immutable confirmations relevant at/before the event time.
                confirmation = connection.execute(
                    "SELECT max(f.event_at) FROM binding_fact_links l JOIN authority_facts f USING(fact_id) "
                    "WHERE l.binding_id=? AND f.message_type='ack' AND f.event_at<=?",
                    (binding["binding_id"], floor_query)).fetchone()[0]
                if confirmation is None or not _read_coverage_is_continuous(connection, site_id, binding["capture_source_id"], confirmation, exact_query, floor_query):
                    return result("unavailable", "source_coverage_gap")
            if len(candidates) > 1:
                return result("ambiguous", "multiple_authoritative_bindings")
            if not candidates:
                # A recovered source alone cannot prove an absence that crosses a
                # missed lifecycle gap. Use exact prior facts, never a nearest row.
                for source in sources:
                    boundary = connection.execute(
                        "SELECT max(event_at) FROM authority_facts WHERE site_id=? AND capture_source_id=? "
                        "AND event_at<=? AND (ipv4=? OR fact_id IN (SELECT last_fact_id FROM binding_intervals "
                        "WHERE site_id=? AND ipv4=?))", (site_id, source, floor_query, ipv4, site_id, ipv4)).fetchone()[0]
                    if boundary is None:
                        boundary = connection.execute("SELECT min(coverage_from) FROM source_coverage WHERE site_id=? "
                                                      "AND capture_source_id=? AND state='usable'", (site_id, source)).fetchone()[0]
                        boundary = max(boundary, horizon[0], retention) if boundary is not None else None
                    if boundary is None or not _read_coverage_is_continuous(connection, site_id, source, boundary, exact_query, floor_query):
                        return result("unavailable", "source_coverage_gap")
                return result("unattributed", "no_authoritative_binding")
            binding = candidates[0]
            return result("resolved", site_id=site_id, client_mac=binding["client_mac"], ipv4=ipv4,
                          event_at=event_at, binding_id=binding["binding_id"], valid_from=binding["valid_from"],
                          valid_until=binding["valid_until"], attribution_source="trusted_dhcp_v4")
        except (sqlite3.Error, OSError, ValueError, NetworkAttributionError, DeviceFingerprintValidationError):
            return result("unavailable", "attribution_store_unavailable")
        finally:
            if connection is not None:
                connection.close()
