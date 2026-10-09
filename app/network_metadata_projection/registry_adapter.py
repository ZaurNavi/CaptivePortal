"""Projection-local adapter of the EXISTING read-only Registry boundary."""
from contextlib import closing
from app.visitor_registry.registry_models import RegistryConfig
from app.visitor_registry.registry_repository import VisitorRegistryRepository
from app.visitor_registry.registry_read_service import VisitorRegistryReadService
from app.visitor_registry.registry_service import VisitorRegistryService
from app.network_metadata.validation import canonical_uuid
from app.network_attribution.validation import canonical_mac
from .models import RegistryEvaluation, ProjectionConflict


class RegistryAdapter:
    def __init__(self, db_path):
        # No initialization, schema write, writer, provider, snapshot collector,
        # or Device ID generation. source_log_path is unused by this read object.
        config = RegistryConfig(False, db_path, "", 0, "UTC", 5, 10, 4194304)
        self.repository = VisitorRegistryRepository(config)
        self.reader = VisitorRegistryReadService(self.repository, VisitorRegistryService("UTC"), configured_enabled=False)

    def _trust_probe(self):
        # Metadata/singleton validation only, once for this batch. No whole-data
        # integrity or snapshot-count audit; no reader_state inventory scan.
        with closing(self.repository._connect(readonly=True)) as connection:
            connection.execute("BEGIN")
            if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
                return False
            self.repository._validate_schema(connection, audit_snapshot_counts=False)
            row = connection.execute("SELECT state FROM registry_state WHERE singleton_id=1").fetchone()
            return row is not None and row["state"] != "unavailable"

    def evaluate_many(self, macs, *, stop_event=None):
        requested = tuple(dict.fromkeys(macs))
        if not requested:
            return {}
        try:
            usable = self._trust_probe()
        except Exception:
            usable = False
        if not usable:
            return {mac: RegistryEvaluation("registry_unavailable", reason="registry_unavailable") for mac in requested}
        evaluations = {}
        for mac in requested:
            if stop_event is not None and stop_event.is_set():
                break
            evaluations[mac] = self._evaluate_point(mac)
        return evaluations

    def evaluate(self, mac):
        return self.evaluate_many((mac,))[mac]

    def _evaluate_point(self, mac):
        try:
            if canonical_mac(mac) != mac:
                raise ProjectionConflict("registry_identity_conflict")
            row = self.reader.get_device_by_mac(mac)
            if row is None:
                return RegistryEvaluation("not_yet_registry_resolved")
            if canonical_mac(row["mac"]) != mac:
                raise ProjectionConflict("registry_identity_conflict")
            device_id = canonical_uuid(row["device_id"])
            return RegistryEvaluation("authoritative", device_id, row.get("updated_at"))
        except ProjectionConflict:
            raise
        except Exception:
            # Exceptions/Registry JSON must never reach projection logs.
            return RegistryEvaluation("registry_unavailable", reason="registry_unavailable")
