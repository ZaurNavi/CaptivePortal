"""Site-scoped immutable query facade for Visit Lifecycle v1."""

from __future__ import annotations

import base64
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Any
from app.network_metadata.models import NetworkMetadataValidationError

from .models import (
    VisitPage,
    VisitObservationWindow,
    VisitQueryValidationError,
    VisitSourceEventRecord,
    normalize_utc,
    optional_mac,
    require_mac,
    require_text,
    protocol_visit_guard,
)
from .repository import VisitRepository


DEFAULT_LIMIT = 500
MAX_LIMIT = 2_000


class VisitLifecycleReadService:
    def __init__(self, repository: VisitRepository):
        self.repository = repository

    @contextmanager
    def analytics_read_connection(self):
        """Yield the lifecycle repository's read-only connection."""
        with self.repository.read_connection() as connection:
            yield connection

    def get_visit(self, site_id: str, visit_id: str):
        return self.repository.get_visit(
            _site(site_id),
            _uuid(visit_id, "visit_id"),
        )

    def get_open_visit(self, site_id: str, client_mac: str):
        return self.repository.get_open_visit(
            _site(site_id),
            _mac(client_mac, "client_mac"),
        )

    def visit_protocol_summary(self, site_id, device_id, visit_id):
        """Stored Visit knowledge only; never an NI02 query from HTTP."""
        site, device, visit_id = _site(site_id), _uuid(device_id, 'device_id'), _uuid(visit_id, 'visit_id')
        visit = self.repository.get_visit(site, visit_id)
        if visit is None or visit.device_id != device:
            return None
        return project_visit_protocol_summary(visit, self.repository.saved_protocol_summary(visit))

    def list_visits(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        status: str | None = None,
        client_mac: str | None = None,
        device_id: str | None = None,
        ssid: str | None = None,
        ap_mac: str | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> VisitPage:
        start = _time(from_utc, "from_utc")
        end = _time(to_utc, "to_utc")
        if start >= end:
            raise VisitQueryValidationError("from_utc must be before to_utc")
        return self._visit_page(
            site_id=_site(site_id),
            from_utc=start,
            to_utc=end,
            status=_status(status),
            client_mac=_optional_mac(client_mac, "client_mac"),
            device_id=_optional_uuid(device_id, "device_id"),
            ssid=_optional_text(ssid, "ssid"),
            ap_mac=_optional_mac(ap_mac, "ap_mac"),
            limit=_limit(limit),
            cursor=_decode_cursor(cursor, "visit"),
        )

    def list_device_visits(
        self,
        site_id: str,
        device_id: str,
        from_utc: str | None = None,
        to_utc: str | None = None,
        status: str | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> VisitPage:
        start = _optional_time(from_utc, "from_utc")
        end = _optional_time(to_utc, "to_utc")
        if start is not None and end is not None and start >= end:
            raise VisitQueryValidationError("from_utc must be before to_utc")
        return self._visit_page(
            site_id=_site(site_id),
            from_utc=start,
            to_utc=end,
            status=_status(status),
            client_mac=None,
            device_id=_uuid(device_id, "device_id"),
            ssid=None,
            ap_mac=None,
            limit=_limit(limit),
            cursor=_decode_cursor(cursor, "visit"),
        )

    def list_open_visits(
        self,
        site_id: str,
        client_mac: str | None = None,
        device_id: str | None = None,
        ssid: str | None = None,
        ap_mac: str | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> VisitPage:
        return self._visit_page(
            site_id=_site(site_id),
            from_utc=None,
            to_utc=None,
            status="open",
            client_mac=_optional_mac(client_mac, "client_mac"),
            device_id=_optional_uuid(device_id, "device_id"),
            ssid=_optional_text(ssid, "ssid"),
            ap_mac=_optional_mac(ap_mac, "ap_mac"),
            limit=_limit(limit),
            cursor=_decode_cursor(cursor, "visit"),
        )

    def list_unmatched_events(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        reason: str | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> VisitPage:
        start = _time(from_utc, "from_utc")
        end = _time(to_utc, "to_utc")
        if start >= end:
            raise VisitQueryValidationError("from_utc must be before to_utc")
        selected_limit = _limit(limit)
        rows = self.repository.list_unmatched_rows(
            site_id=_site(site_id),
            from_utc=start,
            to_utc=end,
            reason=_optional_text(reason, "reason"),
            cursor=_decode_cursor(cursor, "event"),
            limit=selected_limit + 1,
        )
        has_more = len(rows) > selected_limit
        visible = rows[:selected_limit]
        items = tuple(_source_event(row) for row in visible)
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_cursor(
                "event",
                str(last["processed_at"]),
                str(last["event_id"]),
            )
        return VisitPage(items=items, next_cursor=next_cursor)

    def observation_window(
        self,
        site_id: str,
        visit_id: str,
    ) -> VisitObservationWindow:
        visit = self.get_visit(site_id, visit_id)
        if visit is None:
            raise VisitQueryValidationError("visit does not exist")
        return VisitObservationWindow(
            site_id=visit.site_id,
            client_mac=visit.client_mac,
            from_utc=visit.started_at,
            to_utc=visit.closed_at,
        )

    def _visit_page(self, **query: Any) -> VisitPage:
        selected_limit = int(query.pop("limit"))
        rows = self.repository.list_visit_rows(
            **query,
            limit=selected_limit + 1,
        )
        has_more = len(rows) > selected_limit
        visible = rows[:selected_limit]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_cursor(
                "visit",
                last.started_at,
                last.visit_id,
            )
        return VisitPage(items=tuple(visible), next_cursor=next_cursor)


def project_visit_protocol_summary(visit, row):
    """Pure closed public projection, shared by lifecycle and Admin readers."""
    from app.network_metadata.validation import ni_timestamp, digest
    value = dict(type='VisitProtocolSummaryV1', schema_version=1, site_id=visit.site_id,
        device_id=visit.device_id, visit_id=visit.visit_id, visit_status=visit.status,
        started_at=visit.started_at, closed_at=visit.closed_at, summary_state='not_materialized',
        protocols=[], last_protocol_observation=None, evaluated_at=None, source_coverage='unknown',
        attribution_coverage='unknown', finalized_at=None, partial_reason='not_materialized',
        historical_completeness_claimed=False)
    try:
        if row is None:
            return value
        if row['summary_version'] != 1 or row['site_id'] != visit.site_id or row['device_id'] != visit.device_id or row['visit_guard'] != protocol_visit_guard(visit):
            value.update(summary_state='partial', partial_reason='visit_revision_changed')
            return value
        evaluated = _time(row['evaluated_at'], 'evaluated_at')
        lower = datetime.fromisoformat(visit.started_at.replace('Z', '+00:00'))
        upper = datetime.fromisoformat((visit.closed_at or evaluated).replace('Z', '+00:00'))
        if (row['summary_state'] not in {'pending','partial','active','unavailable','finalized'}
                or row['source_coverage'] not in {'unknown','bounded_partial','unavailable'}
                or row['attribution_coverage'] not in {'unknown','current_available','limited'}
                or row['partial_reason'] not in {'identity_unconfirmed','source_unavailable','no_confirmed_observation','late_unresolved','bounded_source','grace_elapsed_partial'}
                or (row['summary_state']=='finalized') != (row['finalized_at'] is not None)):
            raise ValueError()
        protocols = []
        for family in ('dns','tls','quic'):
            stamp, edge = row[family+'_at'], row[family+'_edge']
            if (stamp is None) != (edge is None):raise ValueError()
            if stamp is not None:
                digest(edge)
                if not lower <= ni_timestamp(stamp, canonical=True) < upper:raise ValueError()
                protocols.append(dict(protocol_id=family, last_observed_at=stamp))
        value.update(summary_state=row['summary_state'], protocols=protocols, evaluated_at=evaluated,
            source_coverage=row['source_coverage'], attribution_coverage=row['attribution_coverage'],
            finalized_at=None if row['finalized_at'] is None else _time(row['finalized_at'],'finalized_at'),
            partial_reason=row['partial_reason'])
        if protocols:
            value['last_protocol_observation'] = sorted(protocols, key=lambda r:(-ni_timestamp(r['last_observed_at'],canonical=True).timestamp(),r['protocol_id']))[0]
        return value
    except (KeyError, ValueError, TypeError, NetworkMetadataValidationError):
        value.update(summary_state='unavailable', protocols=[], last_protocol_observation=None, partial_reason='source_unavailable')
        return value


def project_visit_service_history(visit, rows, consumer, *, evaluated_now):
    """Only saved Visit data. Strict, privacy-safe labels and no completeness claim."""
    from datetime import timedelta
    from app.network_metadata.validation import ni_timestamp,digest,integer,canonical_uuid
    result=dict(type='VisitServiceHistoryV1',schema_version=1,site_id=visit.site_id,device_id=visit.device_id,
        visit_id=visit.visit_id,visit_status=visit.status,started_at=visit.started_at,closed_at=visit.closed_at,
        history_state='incomplete',partial_reason='not_materialized',evaluated_at=None,
        services=[],truncated=False,historical_completeness_claimed=False)
    try:
        if consumer is None:return result
        canonical_uuid(consumer['consumer_id']);canonical_uuid(consumer['source_stream_id'])
        digest(consumer['last_outbox_hash']);integer(consumer['last_outbox_seq'])
        ttl=consumer['history_ttl_days'];integer(ttl,1,365)
        result['evaluated_at']=_time(max((r['updated_at'] for r in rows),default=consumer['updated_at']),'updated_at')
        if visit.closed_at is not None and datetime.fromisoformat(visit.closed_at.replace('Z','+00:00'))+timedelta(days=ttl)<=datetime.fromisoformat(evaluated_now.replace('Z','+00:00')):
            result['partial_reason']='history_expired';return result
        if consumer['status'] not in {'processing','incomplete','unavailable'}:raise ValueError()
        result['partial_reason']='backfill_limited';result['truncated']=len(rows)>50
        lower=datetime.fromisoformat(visit.started_at.replace('Z','+00:00'))
        upper=datetime.fromisoformat((visit.closed_at or evaluated_now).replace('Z','+00:00'))
        for row in rows[:50]:
            if row['site_id']!=visit.site_id or row['device_id']!=visit.device_id or row['visit_id']!=visit.visit_id:raise ValueError()
            if row['visit_guard']!=protocol_visit_guard(visit):
                result['partial_reason']='visit_revision_changed';continue
            first=ni_timestamp(row['first_observed_at'],canonical=True);last=ni_timestamp(row['last_observed_at'],canonical=True)
            if not lower<=first<=last<upper:raise ValueError()
            integer(row['distinct_observation_count'],1)
            integer(row['taxonomy_version'],1);integer(row['ruleset_version'],1)
            digest(row['taxonomy_digest']);digest(row['ruleset_digest'])
            if row['status'] not in {'processing','confirmed','incomplete'}:raise ValueError()
            for key in ('service_id','service_label','organization_id','organization_label','taxonomy_id','ruleset_id'):
                if type(row[key]) is not str or not 1<=len(row[key])<=128 or any(ord(char)<32 for char in row[key]):raise ValueError()
            if row['finalized_at'] is None and row['generation_id']!=consumer['active_generation_id']:
                result['partial_reason']='lineage_pending';continue
            result['services'].append(dict(service_id=row['service_id'],display_name=row['service_label'],
                organization_id=row['organization_id'],organization_display_name=row['organization_label'],
                first_observed_at=row['first_observed_at'],last_observed_at=row['last_observed_at'],
                distinct_observation_count=row['distinct_observation_count'],status=row['status'],finalized_at=row['finalized_at'],
                taxonomy=dict(id=row['taxonomy_id'],version=row['taxonomy_version'],digest_sha256=row['taxonomy_digest']),
                ruleset=dict(id=row['ruleset_id'],version=row['ruleset_version'],digest_sha256=row['ruleset_digest']),
                provenance='materialized_ni04_strong_observation'))
        result['history_state']='processing' if visit.status=='open' or consumer['status']=='processing' else 'incomplete' if result['services'] else 'no_confirmed_observation'
        if result['partial_reason'] in {'visit_revision_changed','lineage_pending'}:result['history_state']='incomplete'
        if consumer['status']=='unavailable':result.update(history_state='unavailable',partial_reason='source_unavailable')
        return result
    except (KeyError,ValueError,TypeError,NetworkMetadataValidationError):
        result.update(history_state='unavailable',partial_reason='source_unavailable',services=[])
        return result


def _source_event(row: Any) -> VisitSourceEventRecord:
    value = dict(row)
    return VisitSourceEventRecord(
        event_id=value["event_id"],
        event_type=value["event_type"],
        site_id=value["site_id"],
        client_mac=value["client_mac"],
        controller_event_at=value["controller_event_at"],
        received_at=value["received_at"],
        client_ip=value["client_ip"],
        ssid=value["ssid"],
        ap_mac=value["ap_mac"],
        reported_connected_seconds=value[
            "reported_connected_seconds"
        ],
        reported_traffic_total_bytes=value[
            "reported_traffic_total_bytes"
        ],
        processing_result=value["processing_result"],
        visit_id=value["visit_id"],
        reason=value["reason"],
        first_processed_at=value["first_processed_at"],
        processed_at=value["processed_at"],
        pending_until=value["pending_until"],
    )


def _site(value: Any) -> str:
    try:
        return require_text(value, "site_id")
    except ValueError as exc:
        raise VisitQueryValidationError(str(exc)) from exc


def _uuid(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise VisitQueryValidationError(f"{name} must be a UUID")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise VisitQueryValidationError(f"{name} must be a UUID") from exc
    canonical = str(parsed)
    if value != canonical:
        raise VisitQueryValidationError(f"{name} must be canonical lowercase UUID")
    return canonical


def _optional_uuid(value: Any, name: str) -> str | None:
    return None if value is None else _uuid(value, name)


def _mac(value: Any, name: str) -> str:
    try:
        return require_mac(value, name)
    except ValueError as exc:
        raise VisitQueryValidationError(str(exc)) from exc


def _optional_mac(value: Any, name: str) -> str | None:
    if value is None:
        return None
    try:
        return optional_mac(value, name)
    except ValueError as exc:
        raise VisitQueryValidationError(str(exc)) from exc


def _time(value: Any, name: str) -> str:
    try:
        return normalize_utc(value, name)
    except ValueError as exc:
        raise VisitQueryValidationError(str(exc)) from exc


def _optional_time(value: Any, name: str) -> str | None:
    return None if value is None else _time(value, name)


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise VisitQueryValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _status(value: Any) -> str | None:
    if value is None:
        return None
    if value not in {"open", "closed"}:
        raise VisitQueryValidationError("status must be open or closed")
    return value


def _limit(value: Any) -> int:
    if type(value) is not int or value <= 0 or value > MAX_LIMIT:
        raise VisitQueryValidationError(
            f"limit must be between 1 and {MAX_LIMIT}"
        )
    return value


def _encode_cursor(kind: str, timestamp: str, identity: str) -> str:
    payload = json.dumps(
        [kind, timestamp, identity],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(
    value: Any,
    expected_kind: str,
) -> tuple[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise VisitQueryValidationError("cursor is malformed")
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded.decode("ascii"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise VisitQueryValidationError("cursor is malformed") from exc
    if (
        not isinstance(payload, list)
        or len(payload) != 3
        or payload[0] != expected_kind
        or not isinstance(payload[1], str)
        or not isinstance(payload[2], str)
    ):
        raise VisitQueryValidationError("cursor is malformed")
    timestamp = _time(payload[1], "cursor timestamp")
    identity = (
        _uuid(payload[2], "cursor visit_id")
        if expected_kind == "visit"
        else _optional_text(payload[2], "cursor event_id")
    )
    if identity is None:
        raise VisitQueryValidationError("cursor is malformed")
    if _encode_cursor(expected_kind, timestamp, identity) != value:
        raise VisitQueryValidationError("cursor is not canonical")
    return timestamp, identity
