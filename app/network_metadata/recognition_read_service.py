"""NI-01-owned protected evidence. Never use these DTOs in HTTP or logs."""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
from app.device_fingerprint.validation import validate_site_id
from .models import NetworkMetadataError, NetworkMetadataStorageUnavailable, NetworkMetadataValidationError
from .projection_source import NetworkMetadataProjectionSourceReadService
from .schema import validate_schema
from .validation import canonical_uuid, integer, text, ip


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionDnsQueryV1:
    ordinal: int
    query_name: str
    query_type: str


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionDnsAnswerV1:
    ordinal: int
    answer_type: str
    answer_value: str


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionDnsV1:
    family: str
    dns_event_kind: str
    rcode: str | None
    query_count_observed: int
    answer_count_observed: int
    queries_truncated: bool
    answers_truncated: bool
    query_names_presence_state: str
    answer_values_presence_state: str
    queries: tuple[RecognitionDnsQueryV1, ...]
    answers: tuple[RecognitionDnsAnswerV1, ...]


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionSniV1:
    sni: str | None
    sni_presence_state: str


@dataclass(frozen=True, slots=True, repr=False)
class RecognitionSourceEvidenceV1:
    schema_version: int
    site_id: str
    observation_id: str
    event_at: str
    source_event_family: str
    source_generation_id: str
    source_event_identity: str
    capture_source_id: str
    network_scope_id: str
    capture_scope_binding_digest: str
    sensitive_endpoint_presence_state: str
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    transport_protocol: str | None
    flow_id_decimal: str | None
    transaction_id_decimal: str | None
    dns: RecognitionDnsV1 | None
    tls: RecognitionSniV1 | None
    quic: RecognitionSniV1 | None


class NetworkMetadataRecognitionReadService(NetworkMetadataProjectionSourceReadService):
    def __init__(self, db_path, *, enabled=True):
        super().__init__(db_path)
        self.enabled = enabled

    def read_recognition_evidence(self, site_id, observation_refs, *, deadline):
        try:
            validate_site_id(site_id)
            if type(observation_refs) is not tuple or not 1 <= len(observation_refs) <= 256:
                raise ValueError
            if len(set(observation_refs)) != len(observation_refs):
                raise ValueError
            for ref in observation_refs:
                canonical_uuid(ref, 5)
        except Exception:
            raise NetworkMetadataValidationError() from None
        connection = None
        try:
            if not self.enabled:
                raise NetworkMetadataStorageUnavailable()
            deadline.require_remaining()
            connection = sqlite3.connect(Path(self.db_path).resolve().as_uri() + "?mode=ro",
                                         uri=True, timeout=.5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.set_progress_handler(lambda: int(deadline.expired()), 100)
            for pragma in ("query_only=ON", "foreign_keys=ON", "busy_timeout=500"):
                connection.execute("PRAGMA " + pragma)
            connection.execute("BEGIN")
            validate_schema(connection, writer=False)
            rows = connection.execute(
                "SELECT * FROM network_metadata_observations WHERE site_id=? AND observation_id IN (" +
                ",".join("?" for _ in observation_refs) + ") ORDER BY observation_id",
                (site_id, *observation_refs)).fetchall()
            if len(rows) != len(observation_refs):
                raise ValueError
            output, generations = [], {}
            for row in rows:
                deadline.require_remaining()
                generation_id = row["source_generation_id"]
                if generation_id not in generations:
                    generations[generation_id] = self._generation(connection, generation_id)
                source = self._record(connection, row, generations[generation_id])
                family = row["source_event_family"]
                payload = connection.execute(f"SELECT * FROM network_metadata_{family} WHERE observation_id=?",
                                             (row["observation_id"],)).fetchone()
                if payload is None:
                    raise ValueError
                dns = tls = quic = None
                if family == "dns":
                    queries = tuple(RecognitionDnsQueryV1(*item) for item in connection.execute(
                        "SELECT ordinal,query_name,query_type FROM network_metadata_dns_queries WHERE observation_id=? ORDER BY ordinal LIMIT 9",
                        (row["observation_id"],)))
                    answers = tuple(RecognitionDnsAnswerV1(*item) for item in connection.execute(
                        "SELECT ordinal,answer_type,answer_value FROM network_metadata_dns_answers WHERE observation_id=? ORDER BY ordinal LIMIT 33",
                        (row["observation_id"],)))
                    if len(queries) > 8 or len(answers) > 32:
                        raise ValueError
                    for state, children in ((payload["query_names_presence_state"], queries),
                                            (payload["answer_values_presence_state"], answers)):
                        if state not in {"observed_retained", "not_observed", "expired"} or state != "observed_retained" and children:
                            raise ValueError
                    # Unsupported answer types are omitted by NI-01, preserving
                    # original source ordinals. Gaps are valid; renumbering is not.
                    if [item.ordinal for item in queries] != list(range(len(queries))):
                        raise ValueError
                    for item in queries:
                        integer(item.ordinal, 0, 7)
                        text(item.query_name, 253, controls=True)
                        text(item.query_type, 32, controls=True)
                    for item in answers:
                        integer(item.ordinal, 0, 31)
                        if item.answer_type in {"A", "AAAA"}:
                            if ip(item.answer_value, 4 if item.answer_type == "A" else 6) != item.answer_value:
                                raise ValueError
                        elif item.answer_type == "CNAME":
                            text(item.answer_value, 253, controls=True)
                        else:
                            raise ValueError
                    for key in ("query_count_observed", "answer_count_observed"):
                        integer(payload[key])
                    for key in ("queries_truncated", "answers_truncated"):
                        integer(payload[key], 0, 1)
                    query_count, answer_count = payload["query_count_observed"], payload["answer_count_observed"]
                    if (bool(payload["queries_truncated"]) != (query_count > 8)
                            or bool(payload["answers_truncated"]) != (answer_count > 32)
                            or payload["query_names_presence_state"] == "observed_retained" and len(queries) != min(query_count, 8)
                            or payload["query_names_presence_state"] == "not_observed" and query_count != 0
                            or payload["answer_values_presence_state"] == "observed_retained" and not answers
                            or any(item.ordinal >= answer_count for item in answers)):
                        raise ValueError
                    if payload["dns_event_kind"] not in {"request", "response"}:
                        raise ValueError
                    if payload["rcode"] is not None:
                        text(payload["rcode"], 32, controls=True)
                    dns = RecognitionDnsV1("dns", payload["dns_event_kind"], payload["rcode"],
                        payload["query_count_observed"], payload["answer_count_observed"],
                        bool(payload["queries_truncated"]), bool(payload["answers_truncated"]),
                        payload["query_names_presence_state"], payload["answer_values_presence_state"], queries, answers)
                else:
                    state, sni = payload["sni_presence_state"], payload["sni"]
                    if state not in {"observed_retained", "not_observed", "expired"} or (
                            state == "observed_retained") != (type(sni) is str and bool(sni)):
                        raise ValueError
                    if state != "observed_retained" and sni is not None:
                        raise ValueError
                    if sni is not None:
                        text(sni, 253, controls=True)
                    if family == "tls":
                        tls = RecognitionSniV1(sni, state)
                    else:
                        quic = RecognitionSniV1(sni, state)
                common = {key: getattr(source, key) for key in RecognitionSourceEvidenceV1.__dataclass_fields__
                          if hasattr(source, key)}
                for key in ("flow_id_decimal", "transaction_id_decimal"):
                    value = row[key]
                    if value is not None and (type(value) is not str or not 1 <= len(value) <= 20 or not value.isascii()
                            or not value.isdecimal() or str(int(value)) != value or int(value) > 2**64 - 1):
                        raise ValueError
                output.append(RecognitionSourceEvidenceV1(**common, schema_version=1,
                    flow_id_decimal=row["flow_id_decimal"], transaction_id_decimal=row["transaction_id_decimal"],
                    dns=dns, tls=tls, quic=quic))
            deadline.require_remaining()
            return tuple(output)
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError, NetworkMetadataError):
            if deadline.expired():
                raise AnalyticsQueryDeadlineExceeded("Recognition read deadline exceeded") from None
            raise NetworkMetadataStorageUnavailable() from None
        finally:
            if connection is not None:
                connection.close()
