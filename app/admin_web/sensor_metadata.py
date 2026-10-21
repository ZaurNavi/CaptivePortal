"""Project trusted Sensor metadata into the unchanged V1 store DTO."""

import stat
from types import SimpleNamespace

from app.device_fingerprint_sensor.operations_metadata import SensorMetadataReader

SENSOR_STORES = frozenset({"network_attribution", "sensor_spool"})


def project_store(item, intent, path, now, report, builder, *, deadline, monotonic, cancel):
    components = report["stores"][item.id] if report["status"] == "fresh" else None
    keys = {path: "main", path + "-wal": "wal", path + "-shm": "shm"}
    def metadata_only(name):
        if components is None or components[keys[name]]["presence"] == "unknown":
            raise OSError()
        value = components[keys[name]]
        if value["presence"] == "absent":
            raise FileNotFoundError()
        return SimpleNamespace(st_mode=stat.S_IFREG, st_size=value["bytes"])
    row, _, partial = builder(item, intent, path, now, metadata_only, deadline=deadline,
        monotonic=monotonic, cancel=cancel, identity_available=False)
    if components is None:
        row.update(operational_state="stale" if report["status"] == "stale" else "unknown",
                   reason_code=report["reason"])
        partial = True
    elif any(r["presence"] == "unknown" for r in components.values()):
        reason = next(r["reason"] for r in components.values() if r["presence"] == "unknown")
        row.update(operational_state="unknown", reason_code={
            "permission_denied": "metadata_permission_boundary", "source_disabled": "metadata_source_disabled",
            "identity_collision": "storage_collision", "sample_timeout": "sample_timeout",
        }.get(reason, "metadata_unavailable"))
        partial = True
    # journal is intentionally NOT WAL/SHM nor added to V1 footprint. It remains
    # a separately typed component in the trusted report for the versioned DTO.
    return row, partial
