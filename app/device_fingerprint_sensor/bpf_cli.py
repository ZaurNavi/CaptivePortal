"""Offline site artifact rendering/verification. No Sensor enabling or sockets."""
import argparse
import os
from pathlib import Path
import stat
import sys

from .config import parse_guest_cidrs
from .capture_filter import render_raw_capture_filter, verify_filter_bytes
from .models import SensorError


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise SensorError("invalid offline BPF arguments")


def _read_offline(path: Path, maximum: int) -> bytes:
    if not path.is_absolute():
        raise SensorError("offline artifact path must be absolute")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise SensorError("offline artifact must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino) or not stat.S_ISREG(opened.st_mode):
            raise SensorError("offline artifact changed")
        raw = os.read(fd, maximum + 1)
        after = path.lstat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise SensorError("offline artifact changed")
        return raw
    finally:
        os.close(fd)


def main(argv=None) -> int:
    parser = _Parser(prog="sensor-bpf-offline")
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render"); render.add_argument("--guest-cidrs", required=True)
    verify = commands.add_parser("verify"); verify.add_argument("--guest-cidrs", required=True)
    verify.add_argument("--artifact", required=True)
    try:
        args = parser.parse_args(argv)
        networks = parse_guest_cidrs(args.guest_cidrs)
        expected = render_raw_capture_filter(networks)
        if args.command == "render":
            sys.stdout.buffer.write(expected.encode("ascii") + b"\n")
        else:
            verify_filter_bytes(_read_offline(Path(args.artifact), len(expected) + 1), networks)
        return 0
    except (SensorError, OSError, ValueError):
        print("offline raw capture BPF operation failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
