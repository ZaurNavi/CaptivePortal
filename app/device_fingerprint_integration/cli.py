"""Authorized Task-05 auxiliary composition root; no listener or Omada provider."""

import argparse
import signal

from .runtime import create_worker


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fingerprint integration worker")
    parser.add_argument("command", choices=("run",))
    parser.parse_args(argv)
    from app.settings import get_settings
    worker = create_worker(get_settings())
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_args: worker.stop())
    worker.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
