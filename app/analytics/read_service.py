"""Site-scoped, bounded read orchestration for Analytics quality v1."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .config import AnalyticsConfig
from .formulas import coverage, observation_coverage
from .models import (
    AnalyticsPage,
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
    AnalyticsVisitContext,
    CycleQualitySummary,
    FieldCompleteness,
    RegistryDeviceSummary,
    SafeSnapshotSummary,
    SourceFreshness,
    SourceQualitySummary,
    VisitQualityItem,
)
from .source_gateway import (
    AP_FIELDS,
    CLIENT_FIELDS,
    RADIO_FIELDS,
    AnalyticsPerformanceBudgetExceeded,
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    AnalyticsSourceUnavailable,
    QueryDeadline,
    SOURCE_SCHEMA_VERSIONS,
)
from .telemetry import AnalyticsTelemetry
from .validation import (
    AnalyticsQueryValidationError,
    decode_cursor,
    encode_cursor,
    format_utc,
    parse_utc,
    query_limit,
    query_range,
    require_site,
)


UTC = timezone.utc
QUALITY_MODE_STRICT = "strict_complete"
QUALITY_MODE_DIAGNOSTIC = "diagnostic_including_partial"
_METRIC_VERSION = "analytics-quality-v1"


class AnalyticsReadService:
    """Compose persisted source facts without any source write path."""

    def __init__(
        self,
        config: AnalyticsConfig,
        gateway: AnalyticsSourceGateway,
        *,
        telemetry: AnalyticsTelemetry | None = None,
        clock=lambda: datetime.now(UTC),
        monotonic=time.monotonic,
    ):
        self.config = config
        self.gateway = gateway
        self.telemetry = telemetry or AnalyticsTelemetry()
        self._clock = clock
        self._monotonic = monotonic

    def get_observation_cycle_quality(
        self,
        site_id: str,
        kind: str,
        from_utc: str,
        to_utc: str,
    ) -> AnalyticsResult[CycleQualitySummary]:
        site, start, end, _start_dt, _end_dt = self._query(
            site_id, from_utc, to_utc
        )
        started = self._monotonic()
        evaluation = self._now()
        deadline = self._deadline()
        try:
            self._require_enabled()
            raw = self.gateway.cycle_quality(
                site_id=site,
                kind=kind,
                from_utc=start,
                to_utc=end,
                deadline=deadline,
            )
        except AnalyticsQueryDeadlineExceeded:
            return self._failure_result(
                status="partial",
                reason="query_deadline",
                site=site,
                start=start,
                end=end,
                evaluation=evaluation,
                started=started,
                source_names=("observations",),
            )
        except AnalyticsSourceUnavailable:
            return self._failure_result(
                status="unavailable",
                reason="source_unavailable",
                site=site,
                start=start,
                end=end,
                evaluation=evaluation,
                started=started,
                source_names=("observations",),
            )
        completed = int(raw["completed"])
        summary = CycleQualitySummary(
            kind=kind,
            running=int(raw["running"]),
            completed=completed,
            abandoned=int(raw["abandoned"]),
            completed_complete=int(raw["completed_complete"]),
            completed_incomplete=int(raw["completed_incomplete"]),
            success=int(raw["success"]),
            partial=int(raw["partial"]),
            failed=int(raw["failed"]),
            shutdown=int(raw["shutdown"]),
            complete_ratio=(
                None if completed == 0
                else int(raw["completed_complete"]) / completed
            ),
            latest_accepted_at=raw["latest_accepted_at"],
        )
        status = "ok" if completed else "insufficient_data"
        return self._success_result(
            status=status,
            value=summary,
            site=site,
            start=start,
            end=end,
            evaluation=evaluation,
            started=started,
            source_names=("observations",),
            watermarks={"observations": raw["latest_accepted_at"]},
            rows_examined=int(raw["row_count"]),
            rows_accepted=int(raw["success"]),
            rows_rejected=int(raw["row_count"]) - int(raw["success"]),
            sample_size=completed,
            partial_cycles=int(raw["partial"]),
            failed_cycles=int(raw["failed"]),
            abandoned_cycles=int(raw["abandoned"]),
            reason=None if completed else "zero_denominator",
            filters={"kind": kind},
        )

    def get_field_completeness(
        self,
        site_id: str,
        source: str,
        from_utc: str,
        to_utc: str,
        fields: Sequence[str],
        *,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[tuple[FieldCompleteness, ...]]:
        site, start, end, _start_dt, _end_dt = self._query(
            site_id, from_utc, to_utc
        )
        mode = self._quality_mode(quality_mode)
        started = self._monotonic()
        evaluation = self._now()
        try:
            self._require_enabled()
            rows = self.gateway.field_completeness(
                site_id=site,
                source=source,
                from_utc=start,
                to_utc=end,
                fields=fields,
                quality_mode=mode,
                deadline=self._deadline(),
            )
        except ValueError as exc:
            raise AnalyticsQueryValidationError(str(exc)) from exc
        except AnalyticsQueryDeadlineExceeded:
            return self._failure_result(
                status="partial",
                reason="query_deadline",
                site=site,
                start=start,
                end=end,
                evaluation=evaluation,
                started=started,
                source_names=("observations",),
                quality_mode=mode,
            )
        except AnalyticsSourceUnavailable:
            return self._failure_result(
                status="unavailable",
                reason="source_unavailable",
                site=site,
                start=start,
                end=end,
                evaluation=evaluation,
                started=started,
                source_names=("observations",),
                quality_mode=mode,
            )
        values = tuple(
            FieldCompleteness(
                source=source,
                field=str(row["field"]),
                row_count=int(row["row_count"]),
                non_null_count=int(row["non_null_count"]),
                missing_count=(
                    int(row["row_count"]) - int(row["non_null_count"])
                ),
                coverage_ratio=(
                    None if int(row["row_count"]) == 0
                    else int(row["non_null_count"]) / int(row["row_count"])
                ),
            )
            for row in rows
        )
        common = rows[0]
        missing = sum(item.missing_count for item in values)
        status = (
            "partial" if mode == QUALITY_MODE_DIAGNOSTIC
            else "ok" if int(common["row_count"]) else "insufficient_data"
        )
        return self._success_result(
            status=status,
            value=values,
            site=site,
            start=start,
            end=end,
            evaluation=evaluation,
            started=started,
            source_names=("observations",),
            watermarks={"observations": common["latest_accepted_at"]},
            rows_examined=int(common["rows_examined"]),
            rows_accepted=int(common["row_count"]),
            rows_rejected=int(common["rows_rejected"]),
            sample_size=int(common["row_count"]),
            missing=missing,
            partial_cycles=int(common["partial_cycle_count"]),
            reason=(
                "diagnostic_partial_rows"
                if mode == QUALITY_MODE_DIAGNOSTIC
                else None if int(common["row_count"])
                else "zero_denominator"
            ),
            filters={"source": source, "fields": tuple(fields)},
            quality_mode=mode,
        )

    def list_visit_quality(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AnalyticsResult[AnalyticsPage[VisitQualityItem]]:
        site, start, end, _start_dt, _end_dt = self._query(
            site_id, from_utc, to_utc
        )
        if status not in {None, "open", "closed"}:
            raise AnalyticsQueryValidationError("status is invalid")
        count = query_limit(self.config, limit)
        decoded = decode_cursor(cursor)
        started = self._monotonic()
        evaluation = self._now()
        deadline = self._deadline()
        rows: tuple[Mapping[str, Any], ...] = ()
        unavailable: str | None = None
        try:
            self._require_enabled()
            rows = self.gateway.visit_quality_page(
                site_id=site,
                from_utc=start,
                to_utc=end,
                status=status,
                cursor=decoded,
                limit=count + 1,
                deadline=deadline,
            )
            visible = rows[:count]
            links = tuple(
                (str(row["initial_snapshot_id"]), str(row["client_mac"]))
                for row in visible
                if row["initial_snapshot_id"] is not None
            )
            resolved = self.gateway.resolved_snapshot_links(
                site_id=site, links=links, deadline=deadline
            )
        except AnalyticsQueryDeadlineExceeded:
            unavailable = "query_deadline"
            visible = rows[:count]
            resolved = None
        except AnalyticsSourceUnavailable:
            if not rows:
                return self._failure_result(
                    status="unavailable",
                    reason="source_unavailable",
                    site=site,
                    start=start,
                    end=end,
                    evaluation=evaluation,
                    started=started,
                    source_names=("visits", "registry"),
                )
            unavailable = "registry_unavailable"
            visible = rows[:count]
            resolved = None
        items = tuple(
            self._visit_item(
                row,
                snapshot_resolved=(
                    None if unavailable
                    else (
                        (
                            str(row["initial_snapshot_id"]),
                            str(row["client_mac"]),
                        ) in resolved.resolved_links
                        if row["initial_snapshot_id"] is not None
                        else False
                    )
                ),
            )
            for row in visible
        )
        next_cursor = None
        if len(rows) > count and visible:
            last = visible[-1]
            next_cursor = encode_cursor(
                str(last["started_at"]), str(last["visit_id"])
            )
        result_status = "partial" if unavailable else "ok"
        return self._success_result(
            status=result_status,
            value=AnalyticsPage(items=items, next_cursor=next_cursor),
            site=site,
            start=start,
            end=end,
            evaluation=evaluation,
            started=started,
            source_names=("visits", "registry"),
            watermarks={
                "visits": max(
                    (item.started_at for item in items), default=None
                ),
                "registry": (
                    None if resolved is None else resolved.watermark
                ),
            },
            rows_examined=len(rows),
            rows_accepted=len(items),
            rows_rejected=0,
            sample_size=len(items),
            reason=unavailable,
            filters={"status": status, "limit": count},
        )

    def get_visit_context(
        self,
        site_id: str,
        visit_id: str,
        evaluation_to_utc: str | None = None,
        gap_threshold_seconds: float | None = None,
    ) -> AnalyticsResult[AnalyticsVisitContext]:
        site = require_site(site_id)
        identifier = self._canonical_uuid(visit_id, "visit_id")
        started = self._monotonic()
        evaluation = (
            self._now() if evaluation_to_utc is None
            else format_utc(parse_utc(evaluation_to_utc, "evaluation_to_utc"))
        )
        deadline = self._deadline()
        try:
            self._require_enabled()
            row = self.gateway.visit_by_id(
                site_id=site, visit_id=identifier, deadline=deadline
            )
        except AnalyticsQueryDeadlineExceeded:
            return self._failure_result(
                status="partial",
                reason="query_deadline",
                site=site,
                start=evaluation,
                end=evaluation,
                evaluation=evaluation,
                started=started,
                source_names=("visits",),
            )
        except AnalyticsSourceUnavailable:
            return self._failure_result(
                status="unavailable",
                reason="source_unavailable",
                site=site,
                start=evaluation,
                end=evaluation,
                evaluation=evaluation,
                started=started,
                source_names=("visits",),
            )
        if row is None:
            return self._failure_result(
                status="insufficient_data",
                reason="visit_not_found",
                site=site,
                start=evaluation,
                end=evaluation,
                evaluation=evaluation,
                started=started,
                source_names=("visits",),
            )
        from_value = str(row["started_at"])
        end_value = str(row["closed_at"] or evaluation)
        from_dt = parse_utc(from_value, "visit.started_at")
        end_dt = parse_utc(end_value, "visit.evaluation_to")
        if end_dt < from_dt:
            raise AnalyticsQueryValidationError(
                "evaluation_to_utc precedes Visit start"
            )
        if end_dt - from_dt > timedelta(
            days=self.config.max_query_window_days
        ):
            raise AnalyticsQueryValidationError(
                "Visit observation window exceeds hard limit"
            )
        threshold = (
            self.config.quality_gap_threshold_seconds
            if gap_threshold_seconds is None
            else self._positive(gap_threshold_seconds, "gap_threshold_seconds")
        )
        device = None
        snapshot = None
        coverage_value = None
        partial_reason = None
        try:
            if row["device_id"] is not None:
                device_row = self.gateway.registry_device(
                    device_id=str(row["device_id"]), deadline=deadline
                )
                if device_row is not None:
                    device = self._registry_device(site, device_row)
            if row["initial_snapshot_id"] is not None:
                snapshot_row = self.gateway.snapshot_by_id(
                    site_id=site,
                    snapshot_id=str(row["initial_snapshot_id"]),
                    requested_mac=str(row["client_mac"]),
                    deadline=deadline,
                )
                if snapshot_row is not None:
                    snapshot = self._snapshot(snapshot_row)
        except AnalyticsQueryDeadlineExceeded:
            partial_reason = "query_deadline"
        except AnalyticsSourceUnavailable:
            partial_reason = "registry_unavailable"
        try:
            if partial_reason != "query_deadline":
                raw = self.gateway.observation_coverage(
                    site_id=site,
                    client_mac=str(row["client_mac"]),
                    from_utc=from_value,
                    to_utc=end_value,
                    gap_threshold_seconds=threshold,
                    deadline=deadline,
                )
                first = (
                    None if raw["first_observed_at"] is None
                    else parse_utc(raw["first_observed_at"], "first observation")
                )
                last = (
                    None if raw["last_observed_at"] is None
                    else parse_utc(raw["last_observed_at"], "last observation")
                )
                coverage_value = observation_coverage(
                    started_at=from_dt,
                    ended_at=end_dt,
                    sample_count=int(raw["sample_count"]),
                    first_observed_at=first,
                    last_observed_at=last,
                    max_gap_seconds=(
                        None if raw["max_gap_seconds"] is None
                        else float(raw["max_gap_seconds"])
                    ),
                    gap_count_over_threshold=int(
                        raw["gap_count_over_threshold"]
                    ),
                    gap_threshold_seconds=threshold,
                    visit_duration_seconds=row["duration_seconds"],
                    provisional=row["status"] == "open",
                )
        except AnalyticsQueryDeadlineExceeded:
            partial_reason = "query_deadline"
        except AnalyticsSourceUnavailable:
            partial_reason = partial_reason or "observations_unavailable"
        item = self._visit_item(
            row,
            snapshot_resolved=(
                None if partial_reason == "registry_unavailable"
                else snapshot is not None
            ),
        )
        context = AnalyticsVisitContext(
            visit=item,
            device=device,
            snapshot=snapshot,
            observation_coverage=coverage_value,
        )
        status = "partial" if partial_reason else (
            "insufficient_data"
            if coverage_value is not None and coverage_value.sample_count < 2
            else "ok"
        )
        return self._success_result(
            status=status,
            value=context,
            site=site,
            start=from_value,
            end=end_value,
            evaluation=evaluation,
            started=started,
            source_names=("visits", "registry", "observations"),
            watermarks={
                "visits": str(row["closed_at"] or row["started_at"]),
                "registry": (
                    None if snapshot is None else snapshot.captured_at
                ),
                "observations": (
                    None if coverage_value is None
                    else coverage_value.last_observed_at
                ),
            },
            rows_examined=1 + int(row["authorization_count"]),
            rows_accepted=(
                1 + (
                    0 if coverage_value is None
                    else coverage_value.sample_count
                )
            ),
            rows_rejected=0,
            sample_size=(
                0 if coverage_value is None else coverage_value.sample_count
            ),
            reason=(
                partial_reason
                or (
                    "observation_span_insufficient"
                    if coverage_value is not None
                    and coverage_value.sample_count < 2
                    else None
                )
            ),
            filters={"visit_id": identifier, "gap_threshold_seconds": threshold},
        )

    def get_source_quality(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        evaluation_at_utc: str,
    ) -> AnalyticsResult[SourceQualitySummary]:
        site, start, end, _start_dt, _end_dt = self._query(
            site_id, from_utc, to_utc
        )
        evaluation_dt = parse_utc(evaluation_at_utc, "evaluation_at_utc")
        evaluation = format_utc(evaluation_dt)
        started = self._monotonic()
        deadline = self._deadline()
        try:
            self._require_enabled()
        except AnalyticsSourceUnavailable:
            return self._failure_result(
                status="unavailable",
                reason="source_unavailable",
                site=site,
                start=start,
                end=end,
                evaluation=evaluation,
                started=started,
                source_names=("observations", "visits", "registry"),
            )
        cycles: dict[str, CycleQualitySummary] = {}
        completeness: dict[str, tuple[FieldCompleteness, ...]] = {}
        watermarks: dict[str, str | None] = {
            "observations": None, "visits": None, "registry": None,
        }
        unavailable: list[str] = []
        reason: str | None = None
        rows_examined = rows_accepted = rows_rejected = missing = 0
        partial_cycles = failed_cycles = abandoned_cycles = 0
        try:
            for kind in ("client", "ap_dynamic", "ap_config"):
                raw = self.gateway.cycle_quality(
                    site_id=site, kind=kind, from_utc=start,
                    to_utc=end, deadline=deadline,
                )
                cycles[kind] = self._cycle_summary(kind, raw)
                rows_examined += int(raw["row_count"])
                rows_accepted += int(raw["success"])
                rows_rejected += int(raw["row_count"]) - int(raw["success"])
                partial_cycles += int(raw["partial"])
                failed_cycles += int(raw["failed"])
                abandoned_cycles += int(raw["abandoned"])
            for source, fields in (
                ("client", tuple(sorted(CLIENT_FIELDS))),
                ("ap", tuple(sorted(AP_FIELDS))),
                ("radio", tuple(sorted(RADIO_FIELDS))),
            ):
                raw_fields = self.gateway.field_completeness(
                    site_id=site, source=source, from_utc=start, to_utc=end,
                    fields=fields, quality_mode=QUALITY_MODE_STRICT,
                    deadline=deadline,
                )
                values = tuple(
                    FieldCompleteness(
                        source=source,
                        field=str(item["field"]),
                        row_count=int(item["row_count"]),
                        non_null_count=int(item["non_null_count"]),
                        missing_count=(
                            int(item["row_count"])
                            - int(item["non_null_count"])
                        ),
                        coverage_ratio=(
                            None if int(item["row_count"]) == 0
                            else int(item["non_null_count"])
                            / int(item["row_count"])
                        ),
                    )
                    for item in raw_fields
                )
                completeness[source] = values
                if raw_fields:
                    common = raw_fields[0]
                    rows_examined += int(common["rows_examined"])
                    rows_accepted += int(common["row_count"])
                    rows_rejected += int(common["rows_rejected"])
                missing += sum(value.missing_count for value in values)
            observation_marks = self.gateway.observation_watermarks(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline
            )
            watermarks["observations"] = max(
                (value for value in observation_marks.values() if value),
                default=None,
            )
        except AnalyticsQueryDeadlineExceeded:
            reason = "query_deadline"
        except AnalyticsSourceUnavailable:
            unavailable.append("observations")

        visit_raw: Mapping[str, Any] | None = None
        event_quality: Mapping[str, Mapping[str, int]] = {
            "by_processing_result": {},
            "by_reason": {},
        }
        links: tuple[tuple[str, str], ...] = ()
        if reason != "query_deadline":
            try:
                visit_raw = self.gateway.visit_population(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline,
                )
                links = self.gateway.initial_snapshot_links(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline,
                )
                event_quality = self.gateway.source_event_quality(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline,
                )
                watermarks["visits"] = visit_raw["watermark"]
                rows_examined += int(visit_raw["total"]) + sum(
                    event_quality["by_processing_result"].values()
                )
                rows_accepted += int(visit_raw["total"])
            except AnalyticsQueryDeadlineExceeded:
                reason = "query_deadline"
            except AnalyticsPerformanceBudgetExceeded:
                reason = "performance_budget_exceeded"
            except AnalyticsSourceUnavailable:
                unavailable.append("visits")

        resolved_count: int | None = None
        if visit_raw is not None and reason != "query_deadline":
            try:
                resolved = self.gateway.resolved_snapshot_links(
                    site_id=site, links=links, deadline=deadline
                )
                resolved_count = resolved.matched_link_count
                watermarks["registry"] = self.gateway.registry_watermark(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline,
                )
            except AnalyticsQueryDeadlineExceeded:
                reason = "query_deadline"
            except AnalyticsSourceUnavailable:
                unavailable.append("registry")

        freshness = {
            source: SourceFreshness(
                source_name=source,
                status=(
                    "unavailable" if source in unavailable
                    else "insufficient_data" if watermark is None
                    else "ok"
                ),
                latest_timestamp=watermark,
                freshness_seconds=(
                    None if watermark is None else (
                        evaluation_dt
                        - parse_utc(watermark, f"{source} watermark")
                    ).total_seconds()
                ),
            )
            for source, watermark in watermarks.items()
        }
        if visit_raw is None:
            device_coverage = snapshot_links = auth_coverage = closed = None
            open_count = None
        else:
            total = int(visit_raw["total"])
            device_coverage = coverage(int(visit_raw["linked"]), total)
            snapshot_links = coverage(
                int(visit_raw["snapshot_linked"]), total
            )
            auth_coverage = coverage(
                int(visit_raw["authorization_attached"]), total
            )
            closed = coverage(int(visit_raw["closed_count"]), total)
            open_count = int(visit_raw["open_count"])
        resolved_coverage = (
            None if resolved_count is None
            else coverage(resolved_count, len(links))
        )
        summary = SourceQualitySummary(
            cycle_quality=cycles,
            freshness=freshness,
            field_completeness=completeness,
            device_link_coverage=device_coverage,
            initial_snapshot_link_coverage=snapshot_links,
            resolved_snapshot_coverage=resolved_coverage,
            authorization_attachment_coverage=auth_coverage,
            closed_visit_coverage=closed,
            open_visit_count=open_count,
            source_event_quality=event_quality,
            unavailable_sources=tuple(dict.fromkeys(unavailable)),
        )
        if len(unavailable) >= 2 and visit_raw is None:
            status = "unavailable"
            reason = reason or "source_unavailable"
        elif reason or unavailable:
            status = "partial"
            reason = reason or "source_unavailable"
        elif visit_raw is not None and int(visit_raw["total"]) == 0:
            status = "insufficient_data"
            reason = "zero_denominator"
        else:
            status = "ok"
        return self._success_result(
            status=status,
            value=summary,
            site=site,
            start=start,
            end=end,
            evaluation=evaluation,
            started=started,
            source_names=("observations", "visits", "registry"),
            watermarks=watermarks,
            rows_examined=rows_examined,
            rows_accepted=rows_accepted,
            rows_rejected=rows_rejected,
            sample_size=(0 if visit_raw is None else int(visit_raw["total"])),
            missing=missing,
            partial_cycles=partial_cycles,
            failed_cycles=failed_cycles,
            abandoned_cycles=abandoned_cycles,
            reason=reason,
            filters={},
        )

    def _query(
        self, site_id: str, from_utc: str, to_utc: str
    ) -> tuple[str, str, str, datetime, datetime]:
        site = require_site(site_id)
        start, end, start_dt, end_dt = query_range(
            self.config, from_utc, to_utc
        )
        return site, start, end, start_dt, end_dt

    def _deadline(self) -> QueryDeadline:
        return QueryDeadline.after(
            self.config.max_query_duration_seconds,
            monotonic=self._monotonic,
        )

    def _now(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise RuntimeError("Analytics clock must return datetime")
        return format_utc(value)

    def _require_enabled(self) -> None:
        if not self.config.enabled:
            raise AnalyticsSourceUnavailable("Analytics is disabled")

    @staticmethod
    def _quality_mode(value: str) -> str:
        if value not in {QUALITY_MODE_STRICT, QUALITY_MODE_DIAGNOSTIC}:
            raise AnalyticsQueryValidationError("quality_mode is invalid")
        return value

    @staticmethod
    def _positive(value: Any, name: str) -> float:
        if type(value) is bool:
            raise AnalyticsQueryValidationError(f"{name} must be positive")
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise AnalyticsQueryValidationError(
                f"{name} must be positive"
            ) from exc
        if not 0 < parsed < float("inf"):
            raise AnalyticsQueryValidationError(f"{name} must be positive")
        return parsed

    @staticmethod
    def _canonical_uuid(value: Any, name: str) -> str:
        if not isinstance(value, str):
            raise AnalyticsQueryValidationError(f"{name} must be UUID")
        try:
            canonical = str(uuid.UUID(value))
        except ValueError as exc:
            raise AnalyticsQueryValidationError(
                f"{name} must be UUID"
            ) from exc
        if canonical != value:
            raise AnalyticsQueryValidationError(
                f"{name} must be canonical UUID"
            )
        return canonical

    @staticmethod
    def _visit_item(
        row: Mapping[str, Any],
        *,
        snapshot_resolved: bool | None,
    ) -> VisitQualityItem:
        return VisitQualityItem(
            visit_id=str(row["visit_id"]),
            site_id=str(row["site_id"]),
            client_mac=str(row["client_mac"]),
            device_id=row["device_id"],
            initial_snapshot_id=row["initial_snapshot_id"],
            started_at=str(row["started_at"]),
            closed_at=row["closed_at"],
            status=str(row["status"]),
            authorization_count=(
                None if row.get("authorization_count") is None
                else int(row["authorization_count"])
            ),
            snapshot_resolved=snapshot_resolved,
        )

    @staticmethod
    def _snapshot(row: Mapping[str, Any]) -> SafeSnapshotSummary:
        return SafeSnapshotSummary(
            snapshot_id=str(row["snapshot_id"]),
            device_id=str(row["device_id"]),
            auth_session_id=str(row["auth_session_id"]),
            site_id=str(row["site_id"]),
            requested_mac=str(row["requested_mac"]),
            authorized_at=str(row["authorized_at"]),
            captured_at=str(row["captured_at"]),
            device_type=row["device_type"],
            ssid=row["ssid"],
            ap_mac=row["ap_mac"],
            radio_id=row["radio_id"],
            channel=row["channel"],
            rssi=row["rssi"],
            snr=row["snr"],
            traffic_down=row["traffic_down"],
            traffic_up=row["traffic_up"],
        )

    @staticmethod
    def _registry_device(
        requested_site: str,
        row: Mapping[str, Any],
    ) -> RegistryDeviceSummary:
        same_site = str(row["last_site_id"]) == requested_site
        return RegistryDeviceSummary(
            device_id=str(row["device_id"]),
            mac=str(row["mac"]),
            first_seen_at=str(row["first_seen_at"]),
            last_seen_at=str(row["last_seen_at"]),
            last_site_id=str(row["last_site_id"]),
            last_ip=row["last_ip"] if same_site else None,
            last_ssid=row["last_ssid"] if same_site else None,
            last_ap_name=row["last_ap_name"] if same_site else None,
            last_ap_mac=row["last_ap_mac"] if same_site else None,
            last_rssi=row["last_rssi"] if same_site else None,
            last_snr=row["last_snr"] if same_site else None,
            snapshot_count=int(row["snapshot_count"]),
            site_context_available=same_site,
        )

    @staticmethod
    def _cycle_summary(
        kind: str,
        raw: Mapping[str, Any],
    ) -> CycleQualitySummary:
        completed = int(raw["completed"])
        return CycleQualitySummary(
            kind=kind,
            running=int(raw["running"]),
            completed=completed,
            abandoned=int(raw["abandoned"]),
            completed_complete=int(raw["completed_complete"]),
            completed_incomplete=int(raw["completed_incomplete"]),
            success=int(raw["success"]),
            partial=int(raw["partial"]),
            failed=int(raw["failed"]),
            shutdown=int(raw["shutdown"]),
            complete_ratio=(
                None if completed == 0
                else int(raw["completed_complete"]) / completed
            ),
            latest_accepted_at=raw["latest_accepted_at"],
        )

    def _success_result(
        self,
        *,
        status: str,
        value: Any,
        site: str,
        start: str,
        end: str,
        evaluation: str,
        started: float,
        source_names: tuple[str, ...],
        watermarks: Mapping[str, str | None],
        rows_examined: int,
        rows_accepted: int,
        rows_rejected: int,
        sample_size: int,
        reason: str | None,
        filters: Mapping[str, Any],
        missing: int = 0,
        partial_cycles: int = 0,
        failed_cycles: int = 0,
        abandoned_cycles: int = 0,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[Any]:
        duration = max(0.0, (self._monotonic() - started) * 1000)
        result = AnalyticsResult(
            status=status,
            value=value,
            quality=AnalyticsQuality(
                quality_mode=quality_mode,
                reason=reason,
                accepted_rows=rows_accepted,
                rejected_rows=rows_rejected,
                missing_count=missing,
                partial_cycle_count=partial_cycles,
                failed_cycle_count=failed_cycles,
                abandoned_cycle_count=abandoned_cycles,
            ),
            provenance=AnalyticsProvenance(
                site_id=site,
                from_utc=start,
                to_utc=end,
                evaluation_at_utc=evaluation,
                computed_at_utc=self._now(),
                quality_mode=quality_mode,
                source_names=source_names,
                source_schema_versions={
                    source: SOURCE_SCHEMA_VERSIONS[source]
                    for source in source_names
                },
                source_watermarks=watermarks,
                source_rows_examined=rows_examined,
                source_rows_accepted=rows_accepted,
                source_rows_rejected=rows_rejected,
                sample_size=sample_size,
                missing_count=missing,
                partial_cycle_count=partial_cycles,
                failed_cycle_count=failed_cycles,
                abandoned_cycle_count=abandoned_cycles,
                filters=filters,
                metric_version=_METRIC_VERSION,
                query_duration_ms=duration,
            ),
        )
        self._emit(result, duration)
        return result

    def _failure_result(
        self,
        *,
        status: str,
        reason: str,
        site: str,
        start: str,
        end: str,
        evaluation: str,
        started: float,
        source_names: tuple[str, ...],
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[Any]:
        return self._success_result(
            status=status,
            value=None,
            site=site,
            start=start,
            end=end,
            evaluation=evaluation,
            started=started,
            source_names=source_names,
            watermarks={source: None for source in source_names},
            rows_examined=0,
            rows_accepted=0,
            rows_rejected=0,
            sample_size=0,
            reason=reason,
            filters={},
            quality_mode=quality_mode,
        )

    def _emit(self, result: AnalyticsResult[Any], duration: float) -> None:
        if result.quality.reason == "performance_budget_exceeded":
            event = "analytics.performance_budget_exceeded"
        else:
            event = {
                "ok": "analytics.query_completed",
                "partial": "analytics.query_completed",
                "insufficient_data": "analytics.query_insufficient_data",
                "unavailable": "analytics.query_unavailable",
            }[result.status]
        self.telemetry.emit(
            event,
            metric=result.provenance.metric_version,
            site_id=result.provenance.site_id,
            duration_ms=round(duration, 3),
            sample_size=result.provenance.sample_size,
            accepted_rows=result.provenance.source_rows_accepted,
            rejected_rows=result.provenance.source_rows_rejected,
            status=result.status,
            reason=result.quality.reason,
            quality_mode=result.quality.quality_mode,
        )
