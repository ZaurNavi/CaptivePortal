"""Administrative commands for the local public traffic counter."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from app import get_settings, logger

from .models import (
    BackfillIncompleteError,
    PublicTrafficConfig,
    TrafficSnapshot,
)
from .repository import PublicTrafficRepository
from .service import PublicTrafficService, format_traffic_bytes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Administer the public traffic counter"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser(
        "reset",
        help="Reset accumulated traffic aggregates",
    )
    target = reset.add_mutually_exclusive_group(required=True)
    target.add_argument("--ssid")
    target.add_argument("--all", action="store_true")
    reset.add_argument("--yes", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = PublicTrafficConfig.from_settings(get_settings())
        if not config.db_path or not config.timezone_name:
            raise ValueError("Traffic database configuration is empty")
        repository = PublicTrafficRepository(config.db_path)
        service = PublicTrafficService(
            config=config,
            repository=repository,
            logger=logger,
        )
        if not service.initialize():
            raise RuntimeError(
                "Public traffic storage is unavailable"
            )

        selected_ssid = None if args.all else args.ssid
        _print_preview(service, repository, selected_ssid)
        if not args.yes:
            print(
                "Reset was not performed: pass --yes to confirm.",
                file=sys.stderr,
            )
            return 2

        summary = service.reset(ssid=selected_ssid)
    except BackfillIncompleteError:
        print(
            "Reset was not performed: initial public traffic "
            "backfill is not complete.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        logger.exception("public_traffic_counter_reset_failed")
        print(
            f"Reset failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1

    if summary.scope == "all":
        logger.info(
            "public_traffic_counter_reset scope=all "
            "reset_at=%s affected_ssids=%s",
            summary.reset_at,
            summary.affected_ssids,
        )
        print(
            "Reset completed for all SSIDs; "
            f"affected SSIDs: {summary.affected_ssids}."
        )
    else:
        logger.info(
            "public_traffic_counter_reset scope=ssid ssid=%s "
            "reset_at=%s previous_today_bytes=%s "
            "previous_total_bytes=%s "
            "previous_sessions_today=%s "
            "previous_sessions_total=%s",
            summary.ssid,
            summary.reset_at,
            summary.previous_today_bytes,
            summary.previous_total_bytes,
            summary.previous_sessions_today,
            summary.previous_sessions_total,
        )
        print(f'Reset completed for SSID "{summary.ssid}".')
    return 0


def _print_preview(
    service: PublicTrafficService,
    repository: PublicTrafficRepository,
    ssid: str | None,
) -> None:
    local_date = service.local_date()
    if ssid is None:
        print("Reset scope: all")
        snapshots = repository.get_all_ssid_snapshots(local_date)
        if not snapshots:
            print("No stored SSID aggregates.")
        for snapshot in snapshots:
            _print_snapshot(f'SSID "{snapshot.ssid}"', snapshot)
    else:
        print(f'Reset scope: SSID "{ssid}"')
        _print_snapshot(
            None,
            repository.get_snapshot(
                ssid=ssid,
                local_date=local_date,
            ),
        )
    print(
        "WARNING: aggregated values will be irreversibly reset."
    )


def _print_snapshot(
    label: str | None,
    snapshot: TrafficSnapshot,
) -> None:
    if label is not None:
        print(f"{label}:")
    if not snapshot.available:
        print("Traffic statistics are not ready.")
        return
    print(
        "Today: "
        f"{format_traffic_bytes(snapshot.today_bytes)}; "
        f"sessions: {snapshot.completed_sessions_today}"
    )
    print(
        "Total: "
        f"{format_traffic_bytes(snapshot.total_bytes)}; "
        f"sessions: {snapshot.completed_sessions_total}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
