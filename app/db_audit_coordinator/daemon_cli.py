"""Explicit root-only pilot entry. No install, enable, reset or path override."""
import sys


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if args!=['run']:return 2
    try:
        from .live_profile import load_profile
        from .live_coordinator import LiveCoordinator
        subject=LiveCoordinator(load_profile())
        try:subject.serve()
        finally:subject.close()
        return 0
    except Exception:
        # No exception payload/source paths/identifiers are printed.
        return 3


if __name__=='__main__':raise SystemExit(main())
