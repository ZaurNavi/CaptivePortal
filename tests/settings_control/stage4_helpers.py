"""Disposable Stage-4 inputs. No production paths, keys, credentials or I/O."""
import json
import logging
import uuid
from app.admin_web.models import AdminPrincipal
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.models import SettingsError
from . import CONTROLLER_BASE

SENTINEL = "STAGE4_DISPOSABLE_SECRET_NOT_DISCLOSED_29"


class DisposableFilesystem:
    def __init__(self):
        self.master = bytes(range(32))
        self.db_valid = True
        self.key_valid = True
        self.key_reads = 0

    def validate_db(self, path):
        if not self.db_valid:
            raise SettingsError("controller_secret_permissions_invalid")

    def load_master_key(self):
        self.key_reads += 1
        if not self.key_valid:
            raise SettingsError("controller_secret_key_unavailable")
        return self.master


def secret_stack(tmp_path, *, filesystem=None, **values):
    filesystem = filesystem or DisposableFilesystem()
    base = {**CONTROLLER_BASE, "web_admin_settings_enabled": True,
            "settings_db_path": str(tmp_path / "settings.sqlite3"), **values}
    boot = bootstrap_settings_control(base_settings=base, explicit_environment_names={"OMADA_CLIENT_SECRET"},
        logger=logging.getLogger("stage4"), secret_filesystem=filesystem)
    return boot, filesystem


def secret_mutation(boot, *, generation=0, key=None, value=SENTINEL, operation="replace_secret"):
    payload = {"operation": operation}
    if operation == "replace_secret":
        payload["secret"] = value
    return boot.admin_context.secret_mutation_service.mutate(json.dumps(payload), principal=AdminPrincipal("operator"),
        source_ip="127.0.0.1", request_id=str(uuid.uuid4()), idempotency_key=key or str(uuid.uuid4()), expected_generation=generation)
