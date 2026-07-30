"""Read-only administrative CLI for Visitor Device Registry."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app.settings import get_settings

from .registry_config import (
    registry_database_exists,
    registry_config_from_settings,
    registry_timezone_from_settings,
)
from .registry_models import RegistryConfigError
from .registry_read_service import VisitorRegistryReadService
from .registry_repository import VisitorRegistryRepository
from .registry_service import VisitorRegistryService


class CliArgumentError(ValueError):
    """An argparse validation error that can be rendered as JSON."""


class RegistryArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = RegistryArgumentParser(
        prog="python -m app.visitor_registry.cli",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status")
    _json_flag(status)

    stats = commands.add_parser("stats")
    stats.add_argument("--date", type=date.fromisoformat)
    _json_flag(stats)

    listing = commands.add_parser("list")
    _pagination(listing)
    listing.add_argument("--mac")
    listing.add_argument("--hostname")
    listing.add_argument("--ip")
    listing.add_argument("--ssid")
    listing.add_argument("--ap-mac")
    listing.add_argument("--device-type")
    listing.add_argument("--controller-client-id")
    listing.add_argument("--seen-from")
    listing.add_argument("--seen-to")
    _json_flag(listing)

    show = commands.add_parser("show")
    identity = show.add_mutually_exclusive_group(required=True)
    identity.add_argument("--mac")
    identity.add_argument("--device-id")
    _json_flag(show)

    snapshots = commands.add_parser("snapshots")
    identity = snapshots.add_mutually_exclusive_group(required=True)
    identity.add_argument("--mac")
    identity.add_argument("--device-id")
    _pagination(snapshots)
    _json_flag(snapshots)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    actual_argv = sys.argv[1:] if argv is None else argv
    try:
        args = parser.parse_args(actual_argv)
    except CliArgumentError as exc:
        return _error(str(exc), 2, "--json" in actual_argv)
    json_mode = bool(getattr(args, "json", False))
    try:
        settings = get_settings()
        config = registry_config_from_settings(settings)
        timezone_name = (
            _status_timezone(settings)
            if args.command == "status"
            else registry_timezone_from_settings(settings)
        )
        database_exists = bool(
            config.db_path.strip()
        ) and registry_database_exists(Path(config.db_path))
        if not database_exists and args.command != "status":
            raise FileNotFoundError("Visitor Registry database does not exist")
        repository = VisitorRegistryRepository(config)
        if database_exists:
            repository.validate_runtime_health()
        service = VisitorRegistryReadService(
            repository,
            VisitorRegistryService(timezone_name),
            configured_enabled=config.enabled,
        )
        payload = _execute(service, args)
    except RegistryConfigError as exc:
        return _error(str(exc), 1, json_mode)
    except (ValueError, FileNotFoundError) as exc:
        return _error(str(exc), 2, json_mode)
    except Exception as exc:
        return _error(
            f"Visitor Registry read failed: {type(exc).__name__}",
            1,
            json_mode,
        )
    _write(payload, json_mode)
    return 0


def _status_timezone(settings: dict[str, Any]) -> str:
    """Status remains available even when unrelated timezone is invalid."""
    try:
        return registry_timezone_from_settings(settings)
    except ValueError:
        return "UTC"


def _execute(
    service: VisitorRegistryReadService,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.command == "status":
        return service.get_status()
    if args.command == "stats":
        return service.get_stats(args.date)
    if args.command == "list":
        filters = {
            "mac": args.mac,
            "hostname": args.hostname,
            "ip": args.ip,
            "ssid": args.ssid,
            "ap_mac": args.ap_mac,
            "device_type": args.device_type,
            "controller_client_id": args.controller_client_id,
            "seen_from": args.seen_from,
            "seen_to": args.seen_to,
        }
        status = service.get_status()
        return {
            "devices": service.list_devices(
                filters,
                limit=args.limit,
                offset=args.offset,
            ),
            "limit": args.limit,
            "offset": args.offset,
            "partial": not status["initial_backfill_completed"],
        }
    device = (
        service.get_device_by_mac(args.mac)
        if args.mac
        else service.get_device_by_id(args.device_id)
    )
    if device is None:
        raise ValueError("Visitor device was not found")
    status = service.get_status()
    snapshots = service.list_device_snapshots(
        device["device_id"],
        limit=(10 if args.command == "show" else args.limit),
        offset=(0 if args.command == "show" else args.offset),
    )
    if args.command == "show":
        return {
            "device": device,
            "recent_snapshots": snapshots,
            "first_seen_semantics": (
                "earliest successful portal authorization with "
                "a captured snapshot"
            ),
            "last_seen_semantics": (
                "latest successful portal authorization with "
                "a captured snapshot"
            ),
            "partial": not status["initial_backfill_completed"],
        }
    return {
        "device_id": device["device_id"],
        "snapshots": snapshots,
        "limit": args.limit,
        "offset": args.offset,
        "partial": not status["initial_backfill_completed"],
    }


def _pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true")


def _write(payload: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        sys.stdout.write(
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        return
    for key, value in payload.items():
        if isinstance(value, (dict, list, tuple)):
            rendered = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
            )
        else:
            rendered = str(value)
        sys.stdout.write(f"{key}: {rendered}\n")
    if payload.get("partial"):
        sys.stderr.write(
            "WARNING: initial backfill is incomplete; results are partial\n"
        )


def _error(message: str, code: int, json_mode: bool) -> int:
    if json_mode:
        sys.stdout.write(
            json.dumps(
                {"error": message, "exit_code": code},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        )
    else:
        sys.stderr.write(f"ERROR: {message}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
