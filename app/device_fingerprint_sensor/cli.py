"""Opt-in sensor service entry point."""

from __future__ import annotations

import argparse
import signal
import socket
import time

from app.artifact_identity import ArtifactIdentityError, capture_loaded_artifact_identity

from .config import sensor_config_from_env
from .runtime import SensorRuntime
from .telemetry import SensorTelemetry, configure_sensor_logger


def wait_for_core(host: str, port: int, *, connect_timeout: float, poll_interval: float,
                  max_wait: float, monotonic=time.monotonic, sleep=time.sleep,
                  connector=socket.create_connection) -> bool:
    deadline = monotonic() + max_wait
    while True:
        try:
            connection = connector((host, port), timeout=connect_timeout)
            connection.close()
            return True
        except OSError:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return False
            sleep(min(poll_interval, remaining))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fingerprint-sensor")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    parser.parse_args(argv)
    config = sensor_config_from_env()
    if not config.enabled:
        return 0
    logger = configure_sensor_logger()
    try:
        identity = capture_loaded_artifact_identity("fingerprint-sensor.service")
    except ArtifactIdentityError:
        logger.error("fingerprint_sensor_startup_failed error_category=artifact_identity")
        return 1
    telemetry = SensorTelemetry(logger, runtime_fields=identity.safe_fields())
    if not wait_for_core(
        config.core_ready_host, config.core_ready_port,
        connect_timeout=config.core_ready_connect_timeout_seconds,
        poll_interval=config.core_ready_poll_interval_seconds,
        max_wait=config.core_ready_max_wait_seconds,
    ):
        telemetry.emit("fingerprint_sensor_startup_failed", runtime_state="unavailable", error_category="core_listener_unavailable")
        return 1
    runtime = SensorRuntime(config, telemetry=telemetry)
    try:
        runtime.initialize_transport()
        runtime.producer.read_credential()
        if not runtime.preflight_or_report():
            try:
                runtime.producer.deliver_once()
            except Exception:
                pass
            runtime.shutdown()
            return 1
        runtime.start()
        signal.signal(signal.SIGTERM, lambda *_args: runtime.stop_event.set())
        signal.signal(signal.SIGINT, lambda *_args: runtime.stop_event.set())
        while not runtime.stop_event.wait(1.0):
            pass
        return 0 if runtime.shutdown() else 1
    except Exception:
        telemetry.emit("fingerprint_sensor_startup_failed", runtime_state="unavailable", error_category="startup")
        try:
            runtime.shutdown()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
