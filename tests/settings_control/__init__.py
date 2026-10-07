"""Synthetic disposable Settings V1 test helpers; no production access."""
import json
import logging
import uuid
from app.admin_web.models import AdminPrincipal
from app.settings_control.bootstrap import bootstrap_settings_control

CONTROLLER_BASE = {"omada_url": "https://controller.invalid", "omada_id": "installation",
                   "client_id": "application", "client_secret": "synthetic-secret", "verify_ssl": False}


def stack(tmp_path, **values):
    base = {**CONTROLLER_BASE, "web_admin_settings_enabled": "true", "settings_db_path": str(tmp_path / "settings.sqlite3")}
    base.update(values)
    return bootstrap_settings_control(base_settings=base, explicit_environment_names=frozenset(), logger=logging.getLogger("settings-test"))


def mutation(boot, *, generation=0, key=None, changes=None):
    changes = changes if changes is not None else [{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 120}]
    return boot.admin_context.mutation_service.mutate(json.dumps({"changes": changes}),
        principal=AdminPrincipal("operator"), source_ip="127.0.0.1", request_id=str(uuid.uuid4()),
        idempotency_key=key or str(uuid.uuid4()), expected_generation=generation)
