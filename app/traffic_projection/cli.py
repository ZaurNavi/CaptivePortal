"""Explicit worker/rebuild/repair commands; no action is implicit."""

from __future__ import annotations

import argparse
import logging

from app.settings import get_settings

from .config import traffic_projection_config_from_settings
from .models import PROJECTION_VERSION, validate_projection_version
from .service import TrafficProjectionService, writer_lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="traffic-projection")
    parser.add_argument(
        "--projection-version",
        default=PROJECTION_VERSION,
        type=validate_projection_version,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    commands.add_parser("build")
    commands.add_parser("mark-ready")
    commands.add_parser("activate")
    commands.add_parser("mark-failed")
    repair = commands.add_parser("repair-site")
    repair.add_argument("--site-id", required=True)
    rebuild_range = commands.add_parser("rebuild-range")
    rebuild_range.add_argument("--site-id", required=True)
    rebuild_range.add_argument("--from-utc", required=True)
    rebuild_range.add_argument("--to-utc", required=True)
    commands.add_parser("cleanup")
    args = parser.parse_args(argv)
    config = traffic_projection_config_from_settings(get_settings())
    if not config.enabled:
        parser.error("TRAFFIC_PROJECTION_ENABLED must be true")
    service = TrafficProjectionService(
        config,
        logger=logging.getLogger(__name__),
        projection_version=args.projection_version,
    )
    if args.command == "run":
        service.serve_forever()
    else:
        with writer_lock(config.writer_lock_path):
            service.initialize()
            if args.command == "build":
                service.worker_iteration()
            elif args.command == "mark-ready":
                service.mark_ready()
            elif args.command == "activate":
                service.activate()
            elif args.command == "mark-failed":
                service.fail_version()
            elif args.command == "repair-site":
                service.repair_site(args.site_id)
            elif args.command == "rebuild-range":
                service.rebuild_range(
                    args.site_id, from_utc=args.from_utc, to_utc=args.to_utc
                )
            else:
                service.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
