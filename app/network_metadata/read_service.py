"""Typed, strictly non-sensitive read-only keyset projection."""
import json
import sqlite3
from urllib.parse import quote
from app.device_fingerprint.validation import validate_site_id
from .models import NetworkMetadataValidationError, NetworkMetadataStorageUnavailable
from .validation import ni_timestamp, canonical_uuid, integer

COMMON_COLUMNS = ("observation_id", "event_at", "ingested_at", "site_id", "capture_source_id", "network_scope_id",
    "capture_scope_binding_schema_version", "capture_scope_binding_digest", "source_generation_id", "source_event_identity",
    "flow_id_decimal", "transaction_id_decimal", "sensitive_endpoint_presence_state", "ingest_run_id", "normalizer_version")
FAMILY_COLUMNS = {
    "dns": ("dns_event_kind", "dns_wire_id", "rcode", "query_names_presence_state", "answer_values_presence_state",
            "query_count_observed", "answer_count_observed", "queries_truncated", "answers_truncated"),
    "tls": ("tls_version", "sni_presence_state", "client_alpns_truncated", "server_alpns_truncated"),
    "quic": ("quic_version", "sni_presence_state")}


class NetworkMetadataReadService:
    def __init__(self, db_path):
        self.db_path = db_path

    def list_observations(self, site_id, from_utc, to_utc, *, family=None, limit=100, cursor=None):
        try:
            validate_site_id(site_id)
        except Exception:
            raise NetworkMetadataValidationError() from None
        try:
            start, end = ni_timestamp(from_utc, canonical=True), ni_timestamp(to_utc, canonical=True)
            if not 0 < (end - start).total_seconds() <= 30 * 86400:
                raise NetworkMetadataValidationError()
            integer(limit, 1, 500)
            if family is not None and (type(family) is not str or family not in FAMILY_COLUMNS):
                raise NetworkMetadataValidationError()
            if cursor is not None:
                if type(cursor) is not tuple or len(cursor) != 2:
                    raise NetworkMetadataValidationError()
                if not start <= ni_timestamp(cursor[0], canonical=True) < end:
                    raise NetworkMetadataValidationError()
                canonical_uuid(cursor[1], 5)
        except (ValueError, TypeError):
            raise NetworkMetadataValidationError() from None
        connection = None
        try:
            connection = sqlite3.connect("file:" + quote(self.db_path, safe="/") + "?mode=ro", uri=True, timeout=.5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=500")
            connection.execute("BEGIN")
            params, predicate = [site_id, from_utc, to_utc], "site_id=? AND event_at>=? AND event_at<?"
            if family:
                predicate += " AND source_event_family=?"
                params.append(family)
            if cursor:
                predicate += " AND (event_at,observation_id)>(?,?)"
                params.extend(cursor)
            params.append(limit + 1)
            rows = connection.execute("SELECT " + ",".join(COMMON_COLUMNS) +
                ",source_event_family,source_health_ref FROM network_metadata_observations WHERE " + predicate +
                " ORDER BY event_at,observation_id LIMIT ?", params).fetchall()
            items = []
            for row in rows[:limit]:
                item = {field: row[field] for field in COMMON_COLUMNS}
                item["family"] = kind = row["source_event_family"]
                health = connection.execute("SELECT evaluated_at,capture_health,metadata_output_health,metadata_ingest_health,reason_codes_json FROM network_metadata_source_health WHERE health_id=?", (row["source_health_ref"],)).fetchone()
                item["source_health"] = {field: health[field] for field in ("evaluated_at", "capture_health", "metadata_output_health", "metadata_ingest_health")}
                item["source_health"]["reason_codes"] = json.loads(health["reason_codes_json"])
                data = connection.execute("SELECT " + ",".join(FAMILY_COLUMNS[kind]) +
                    f" FROM network_metadata_{kind} WHERE observation_id=?", (row["observation_id"],)).fetchone()
                item["family_data"] = {field: bool(data[field]) if field.endswith("truncated") else data[field] for field in FAMILY_COLUMNS[kind]}
                if kind == "tls":
                    for side in ("client", "server"):
                        item["family_data"][side + "_alpns"] = [alpn[0] for alpn in connection.execute(
                            "SELECT alpn FROM network_metadata_tls_alpn WHERE observation_id=? AND side=? ORDER BY ordinal", (row["observation_id"], side))]
                items.append(item)
            return {"items": items, "next_cursor": (items[-1]["event_at"], items[-1]["observation_id"]) if len(rows) > limit else None}
        except (sqlite3.Error, KeyError, TypeError, ValueError):
            raise NetworkMetadataStorageUnavailable() from None
        finally:
            if connection is not None:
                connection.close()
