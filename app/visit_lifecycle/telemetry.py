"""Fail-open operational telemetry for Visit Lifecycle."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from app.auth_telemetry import get_auth_telemetry


class VisitTelemetry:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def emit(self, event: str, level: str = "info", **fields: Any) -> bool:
        if event == 'visit.service_linkage_sample' and not _valid_linkage_sample(fields):
            return False
        safe_fields = {
            key: value
            for key, value in fields.items()
            if _safe_field(key, value)
        }
        try:
            telemetry = get_auth_telemetry()
            method = getattr(telemetry, "safe_emit_system", None)
            if callable(method) and method(
                event,
                level=level,
                component="visit_lifecycle",
                **safe_fields,
            ):
                return True
        except Exception:
            pass
        try:
            numeric = getattr(logging, str(level).upper(), logging.INFO)
            details = " ".join(
                f"{key}={value}" for key, value in sorted(safe_fields.items())
            )
            self._logger.log(
                numeric,
                "%s%s",
                event,
                f" {details}" if details else "",
            )
            return True
        except Exception:
            return False


def _safe_field(key: str, value: Any) -> bool:
    lowered = key.lower()
    if any(token in lowered for token in (
        "token", "secret", "password", "cookie", "authorization", "raw",
    )):
        return False
    return value is None or type(value) in {str, int, float, bool}


LINKAGE_COUNTER_FIELDS = (
    'newly_staged_unique', 'later_attached_unique', 'expired_detached_unique',
    'rejected_old_first_delivery',
    'committed_batches', 'failed_passes', 'sample_failures', 'export_failures',
    'rejected_identity', 'rejected_lineage', 'rejected_future', 'rejected_conflict', 'rejected_sealed',
    'lag_le_30s', 'lag_le_60s', 'lag_le_300s', 'lag_le_900s', 'lag_le_1800s', 'lag_lt_3600s',
)
LINKAGE_BOUND = 10**12


def _valid_linkage_sample(fields):
    integers=set(LINKAGE_COUNTER_FIELDS)|{'sample_interval_seconds','still_unresolved','unresolved_sample_valid'}
    return (set(fields)==integers|{'restart_gap_possible','first_process_sample','counters_saturated','population_capped'}
        and all(type(fields[k]) is int and 0<=fields[k]<=LINKAGE_BOUND for k in integers)
        and fields['unresolved_sample_valid'] in (0,1)
        and all(type(fields[k]) is bool for k in ('restart_gap_possible','first_process_sample','counters_saturated','population_capped')))


class VisitServiceLinkageTelemetry:
    """Process-local committed deltas, disjoint buckets; never a lifetime rate.

    Each process starts a fresh window. A crash/restart may lose unexported
    deltas (including the commit-to-observer gap); every sample declares that
    limitation. Failed exports retain the window. No traffic identity escapes.
    """
    def __init__(self, telemetry, *, monotonic=time.monotonic):
        self.telemetry=telemetry
        self.clock=monotonic
        self.started=self.last_attempt=self.clock()
        self.first=True
        self.saturated=False
        self.counts=dict.fromkeys(LINKAGE_COUNTER_FIELDS,0)

    def _add(self,key):
        value=self.counts[key]+1
        self.saturated=self.saturated or value>LINKAGE_BOUND
        self.counts[key]=min(value,LINKAGE_BOUND)

    def failed(self):
        self._add('failed_passes')

    def committed(self, transitions):
        self._add('committed_batches')
        reasons={'identity_pending':'identity','no_visit':'identity','binding_changed':'identity',
            'lineage_pending':'lineage','future_event':'future','conflicting_fact':'conflict','sealed_visit':'sealed'}
        for old,new in transitions:
            if new['status']=='discarded':
                self._add('rejected_old_first_delivery')
                continue
            if new['visit_id'] is None and (old is None or old['pending_since'] is None):
                self._add('newly_staged_unique')
            if new['status']=='expired' and (old is None or old['status']!='expired'):
                self._add('expired_detached_unique')
            if (old is not None and old['visit_id'] is None and new['visit_id'] is not None
                    and old['linkage_attached_at'] is None and new['linkage_attached_at'] is not None):
                first=old['pending_since']
                if first is not None:
                    age=(datetime.fromisoformat(new['updated_at'].replace('Z','+00:00'))-
                        datetime.fromisoformat(first.replace('Z','+00:00'))).total_seconds()
                    if 0<=age<3600:
                        self._add('later_attached_unique')
                        for bound,key in ((30,'lag_le_30s'),(60,'lag_le_60s'),(300,'lag_le_300s'),
                                (900,'lag_le_900s'),(1800,'lag_le_1800s'),(3600,'lag_lt_3600s')):
                            if age<=bound:self._add(key);break
            if new['visit_id'] is None and new['reason'] in reasons and (
                    old is None or (old['visit_id'],old['reason'])!=(new['visit_id'],new['reason'])):
                self._add('rejected_'+reasons[new['reason']])

    def sample(self, repository, *, deadline):
        now=self.clock()
        if now-self.last_attempt<60:return
        self.last_attempt=now
        try:
            population=repository.service_unresolved_sample(deadline=deadline)
            valid=1
        except Exception:
            self._add('sample_failures');population=0;valid=0
        fields=dict(self.counts,sample_interval_seconds=min(int(max(0,now-self.started)),LINKAGE_BOUND),
            still_unresolved=population,unresolved_sample_valid=valid,restart_gap_possible=True,
            first_process_sample=self.first,counters_saturated=self.saturated,
            population_capped=population>100000)
        if self.telemetry.emit('visit.service_linkage_sample',**fields):
            self.counts=dict.fromkeys(LINKAGE_COUNTER_FIELDS,0)
            self.started=now;self.first=False;self.saturated=False
        else:self._add('export_failures')
