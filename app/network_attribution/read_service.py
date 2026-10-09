"""Read-only Site/IP/event-time resolution with coverage-first precedence."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.device_fingerprint.validation import format_utc

from .models import NetworkMetadataAttributionResultV1, NetworkAttributionError
from .repository import RETENTION_SECONDS, coverage_is_continuous
from .schema import validate_schema_contract
from .validation import query_values


class NetworkAttributionReadService:
    def __init__(self, config, *, clock=lambda: datetime.now(timezone.utc)):
        self.config, self.clock = config, clock

    def resolve_ipv4(self, site_id, ipv4, event_at):
        result = NetworkMetadataAttributionResultV1
        try:
            query_values(site_id, ipv4, event_at)
        except NetworkAttributionError:
            return result("invalid", "invalid_query")
        if not self.config.enabled:
            return result("unavailable", "attribution_disabled")
        connection = None
        try:
            paths = (Path(self.config.db_path), Path(self.config.db_path + "-wal"), Path(self.config.db_path + "-shm"))
            if sum(path.stat().st_size for path in paths if path.exists()) > self.config.max_db_bytes:
                return result("unavailable", "attribution_store_unavailable")
            connection = sqlite3.connect(Path(self.config.db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=.5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA busy_timeout=500")
            connection.execute("BEGIN")
            validate_schema_contract(connection)
            horizon = connection.execute("SELECT retained_from FROM authority_horizon WHERE site_id=?", (site_id,)).fetchone()
            if horizon is None:
                return result("unavailable", "authority_horizon_unavailable")
            retention = format_utc(self.clock() - timedelta(seconds=RETENTION_SECONDS))
            if event_at < max(horizon[0], retention):
                return result("outside_historical_horizon", "outside_historical_horizon")
            coverage = connection.execute(
                "SELECT * FROM source_coverage WHERE site_id=? AND coverage_from<=? "
                "AND (coverage_until IS NULL OR ?<coverage_until)", (site_id, event_at, event_at)).fetchall()
            if not coverage or any(row["state"] != "usable" or
                                   (row["coverage_until"] is None and event_at > row["verified_through"])
                                   for row in coverage):
                return result("unavailable", "source_coverage_unavailable")
            sources = {row["capture_source_id"] for row in coverage}
            candidates = connection.execute(
                "SELECT * FROM binding_intervals WHERE site_id=? AND ipv4=? AND valid_from<=? AND ?<valid_until",
                (site_id, ipv4, event_at, event_at)).fetchall()
            for binding in candidates:
                if binding["capture_source_id"] not in sources:
                    return result("unavailable", "source_coverage_unavailable")
                # Mutable last_confirmed_at can be later than a historical query.
                # Consult immutable confirmations relevant at/before the event time.
                confirmation = connection.execute(
                    "SELECT max(f.event_at) FROM binding_fact_links l JOIN authority_facts f USING(fact_id) "
                    "WHERE l.binding_id=? AND f.message_type='ack' AND f.event_at<=?",
                    (binding["binding_id"], event_at)).fetchone()[0]
                if confirmation is None or not coverage_is_continuous(connection, site_id, binding["capture_source_id"], confirmation, event_at):
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
                        "WHERE site_id=? AND ipv4=?))", (site_id, source, event_at, ipv4, site_id, ipv4)).fetchone()[0]
                    if boundary is None:
                        boundary = connection.execute("SELECT min(coverage_from) FROM source_coverage WHERE site_id=? "
                                                      "AND capture_source_id=? AND state='usable'", (site_id, source)).fetchone()[0]
                        boundary = max(boundary, horizon[0], retention) if boundary is not None else None
                    if boundary is None or not coverage_is_continuous(connection, site_id, source, boundary, event_at):
                        return result("unavailable", "source_coverage_gap")
                return result("unattributed", "no_authoritative_binding")
            binding = candidates[0]
            return result("resolved", site_id=site_id, client_mac=binding["client_mac"], ipv4=ipv4,
                          event_at=event_at, binding_id=binding["binding_id"], valid_from=binding["valid_from"],
                          valid_until=binding["valid_until"], attribution_source="trusted_dhcp_v4")
        except (sqlite3.Error, OSError, ValueError, NetworkAttributionError):
            return result("unavailable", "attribution_store_unavailable")
        finally:
            if connection is not None:
                connection.close()
