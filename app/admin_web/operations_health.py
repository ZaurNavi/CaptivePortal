"""Versioned app-health projection. Only trusted owner reports, never DB probes."""
import copy
from app.operations_health import unknown_evidence, validate, SENSOR_UNIT, NI02_UNIT
from app.device_fingerprint_sensor.operations_metadata import TTL, boot_ns


class SensorHealthEvidence:
    def __init__(self, reader, *, unit=SENSOR_UNIT, source="sensor_native.v2"):
        self.reader, self.last = reader, None
        self.unit, self.source = unit, source

    def collect(self, report, service, now):
        if type(report) is not dict:
            report = {}
        key = (service.get("main_pid"), service.get("started_at_utc"))
        current = None
        if report.get("status") == "fresh" and "health" in report:
            try:
                validate(report["health"], self.unit)
                if service.get("operational_state") != "running" or report["producer"]["pid"] != service.get("main_pid"):
                    raise ValueError()
                current = dict(evidence=dict(state=report["health"]["state"], source=self.source,
                    observed_at=report["observed_at"], received_at=now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    age=report["age"], ttl=int(TTL), reason=report["health"]["reason"]),
                    expires=report["expires_boottime_ns"], producer=report["producer"], key=key)
                if self.unit == NI02_UNIT:
                    from app.device_fingerprint_sensor.operations_metadata import parse_stamp
                    if (parse_stamp(report["observed_at"]) < parse_stamp(service["started_at_utc"])
                            or not 0 <= report["age"] <= TTL or type(report["expires_boottime_ns"]) is not int):
                        raise ValueError()
                    current["pending_count"] = report["health"]["pending_count"]
                if self.unit == SENSOR_UNIT:
                    from app.device_fingerprint_sensor.operations_metadata import parse_stamp, sensor_workload
                    # Workload is private, current-report evidence, not retained
                    # degradation or part of the seven-key public health DTO.
                    if (parse_stamp(report['observed_at']) >= parse_stamp(service['started_at_utc'])
                            and type(report['age']) in {int, float} and 0 <= report['age'] <= TTL
                            and type(report['expires_boottime_ns']) is int):
                        try:
                            current['workload'] = sensor_workload(report.get('workload'))
                        except (ValueError, TypeError, KeyError):
                            pass
                from app.operations_health import NI04_UNIT, TRAFFIC_UNIT
                if self.unit in {NI04_UNIT,TRAFFIC_UNIT}:
                    from app.operations_app_health import phase2_workload
                    from app.device_fingerprint_sensor.operations_metadata import parse_stamp
                    if (parse_stamp(report['observed_at']) >= parse_stamp(service['started_at_utc'])
                            and type(report['age']) in {int,float} and 0 <= report['age'] <= TTL
                            and type(report['expires_boottime_ns']) is int):
                        try:current['workload'] = phase2_workload(self.unit,report.get('workload'))
                        except (ValueError,TypeError,KeyError):pass
                self.last = copy.deepcopy(current)
            except Exception:
                current = None
        if current is None and self.last is not None:
            # Invalid newer data cannot erase confirmed degradation. Never
            # retain green on an invalid report or across an actual PID/boot.
            try:
                channel = self.reader.channel()
                uid = channel.sensor_uid if self.unit == SENSOR_UNIT else channel.uid
                producer = self.reader.identity(service["main_pid"], uid)
                if key != self.last["key"] or producer != self.last["producer"] or service["operational_state"] != "running":
                    self.last = None
                elif self.last["evidence"]["state"] in {"degraded", "unavailable"}:
                    current = copy.deepcopy(self.last)
                    if self.unit == NI02_UNIT:
                        current["pending_count"] = None  # Cached degradation is not current workload proof.
                    current.pop('workload', None)
            except Exception:
                self.last = None
        if current is not None:
            return current
        evidence = unknown_evidence("report_stale" if report.get("status") == "stale" else "report_unavailable")
        if report.get("status") == "stale":
            evidence["state"] = "stale"
        return dict(evidence=evidence, expires=None)


def project(record, *, stale=False, boottime=boot_ns):
    result = copy.deepcopy(record["evidence"])
    expiry = record["expires"]
    if expiry is not None:
        age = max(0.0, TTL - (expiry - boottime()) / 1_000_000_000)
        result["age"] = round(age, 3)
        if stale or age > TTL:
            result.update(state="stale", reason="report_stale")
    return result


def sensor_store_metadata(report, store, *, boottime=boot_ns):
    expiry = report.get("expires_boottime_ns")
    age = None if expiry is None else max(0.0, TTL - (expiry - boottime()) / 1_000_000_000)
    fresh = report.get("status") == "fresh" and age is not None and age <= TTL
    components = report.get("stores") or {}
    journal = components.get(store, {}).get("journal") if fresh else None
    return dict(source="sensor_metadata" if fresh else "none", state="fresh" if fresh else "stale" if age is not None or report.get("status") == "stale" else "unknown",
                age=None if age is None else round(age, 3), ttl=int(TTL)), (
                    journal["bytes"] if journal is not None and journal["presence"] != "unknown" else None)
