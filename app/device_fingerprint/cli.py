"""Dedicated opt-in direct-TLS service entry point."""

from __future__ import annotations

import argparse
import json
import signal
from dataclasses import asdict

from app.artifact_identity import ArtifactIdentityError, capture_loaded_artifact_identity
from app.settings import get_settings

from .api import DeviceFingerprintSafeRequestHandler, create_device_fingerprint_app
from .config import device_fingerprint_config_from_settings
from .models import DeviceFingerprintError
from .repository import DeviceFingerprintRepository, writer_lock
from .schema import SCHEMA_VERSION
from .schema_registry import build_production_schema_registry
from .service import DeviceFingerprintRuntime
from .telemetry import DeviceFingerprintTelemetry, configure_device_fingerprint_logger
from .storage_v2 import RECOVERY_TRIGGERS, migrate_v1_to_v2, recover_database_generation

_HARD_CONTAINMENT_LOCKS: list[object] = []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="device-fingerprint")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    migration = commands.add_parser("migrate-v1-to-v2")
    migration.add_argument("--backup-path", required=True)
    recovery = commands.add_parser("recover-generation")
    recovery.add_argument("--trigger", required=True, choices=sorted(RECOVERY_TRIGGERS))
    args = parser.parse_args(argv)
    config = device_fingerprint_config_from_settings(get_settings())
    if args.command != "run":
        try:
            if args.command == "migrate-v1-to-v2":
                result = migrate_v1_to_v2(
                    config.db_path, writer_lock_path=config.writer_lock_path,
                    backup_path=args.backup_path, max_db_bytes=config.max_db_bytes,
                )
            else:
                result = recover_database_generation(
                    config.db_path, writer_lock_path=config.writer_lock_path,
                    trigger=args.trigger, max_db_bytes=config.max_db_bytes,
                )
            print(json.dumps(asdict(result), sort_keys=True))
            return 0
        except Exception:
            return 1
    if not config.enabled:
        return 0
    logger = configure_device_fingerprint_logger()
    try:
        identity = capture_loaded_artifact_identity("fingerprint-evidence.service")
    except ArtifactIdentityError:
        logger.error("device_fingerprint_startup_failed error_category=artifact_identity")
        return 1
    telemetry = DeviceFingerprintTelemetry(logger, runtime_fields=identity.safe_fields())
    repository = DeviceFingerprintRepository(config.db_path, max_db_bytes=config.max_db_bytes)
    runtime = DeviceFingerprintRuntime(config, repository, None, artifact_identity=identity, telemetry=telemetry)
    lock_context = writer_lock(config.writer_lock_path)
    lock_open = False

    def release_lock() -> None:
        nonlocal lock_open
        if lock_open:
            lock_context.__exit__(None, None, None)
            lock_open = False

    try:
        lock_context.__enter__()
        lock_open = True
        runtime.initialize()
        runtime.configure_registry(build_production_schema_registry())
        app = create_device_fingerprint_app(runtime, logger=logger)
        signal.signal(signal.SIGTERM, runtime.signal_stop)
        signal.signal(signal.SIGINT, runtime.signal_stop)
        runtime.start_maintenance()
        runtime.mark_ready()
        telemetry.emit(
            "device_fingerprint_service_started",
            runtime_state="ready",
            schema_version=SCHEMA_VERSION,
        )
        app.run(
            host=config.bind_address,
            port=config.port,
            debug=False,
            use_reloader=False,
            threaded=True,
            ssl_context=(config.tls_cert_path, config.tls_key_path),
            request_handler=DeviceFingerprintSafeRequestHandler,
        )
        return 0
    except SystemExit:
        raise
    except DeviceFingerprintError:
        telemetry.emit("device_fingerprint_product_health", runtime_state="unavailable", error_category="startup")
        return 1
    except Exception:
        telemetry.emit("device_fingerprint_product_health", runtime_state="unavailable", error_category="startup")
        return 1
    finally:
        if not runtime.finalize(release_lock=release_lock) and lock_open:
            _HARD_CONTAINMENT_LOCKS.append(lock_context)


if __name__ == "__main__":
    raise SystemExit(main())
