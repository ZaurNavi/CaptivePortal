"""NI03_TOP1_INDEX_V1: explicit offline maintenance under the NI02 writer lock.

Not called by readers or normal startup. No automatic repair/upgrade/downgrade.
The operator must stop ALL NI02/NI03/NI04 consumers before invoking this CLI.
"""
import argparse
import hashlib
import sqlite3
from pathlib import Path

from .models import ProjectionUnavailable
from .repository import ProjectionRepository
from .schema import INDEXES, _expected_signatures, _validate_schema, signature

OPERATION = "NI03_TOP1_INDEX_V1"
INDEX = "idx_projection_mac_family_event_latest"


def validate_index_version(connection, *, installed, integrity=True):
    """Only the exact old/new Core V2, with either complete optional extension."""
    core, _ = _expected_signatures()
    if not installed:
        core = tuple(row for row in core if row[1] != INDEX)
    return _validate_schema(connection, core, integrity=integrity)


def _records_digest(connection):
    """Streaming maintenance invariant, including extension and sqlite_sequence.

    No fact is rewritten. SELECT in stable rowid order keeps memory to one row;
    table names come only from the already validated closed schema signature.
    """
    result = hashlib.sha256()
    names = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in names:
        result.update(name.encode("utf-8") + b"\0")
        cursor = connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')
        try:
            for row in cursor:
                encoded = repr(tuple(row)).encode("utf-8")
                result.update(len(encoded).to_bytes(8, "big"))
                result.update(encoded)
        finally:
            cursor.close()
    return result.digest()


def migrate(config, *, direction, maintenance_confirmed=False, crash_point=lambda _: None):
    """Return True only for a committed transition; exact target is a no-op.

    Uses the *same* lock path and locking implementation as the sole NI02 writer,
    but cannot initialize/create a store, run retention, install extensions or
    perform the repository's normal checkpoint/capacity maintenance.
    """
    if (direction not in {"up", "down"} or maintenance_confirmed is not True
            or not config.enabled):
        raise ProjectionUnavailable()
    owner = ProjectionRepository(config)
    connection = None
    try:
        path = Path(config.db_path).resolve(strict=True)
        if not path.is_file():
            raise ProjectionUnavailable()
        owner._lock()
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
                                     isolation_level=None, timeout=.5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        installed = any(row[1] == INDEX for row in signature(connection))
        before_variant = validate_index_version(connection, installed=installed)
        if installed == (direction == "up"):
            connection.execute("COMMIT")
            return False
        before = _records_digest(connection)
        crash_point("preflight")
        if direction == "up":
            connection.execute(f"CREATE INDEX {INDEX} ON {INDEXES[INDEX]}")
        else:
            connection.execute(f"DROP INDEX {INDEX}")
        crash_point("index_changed")
        if (validate_index_version(connection, installed=not installed) != before_variant
                or _records_digest(connection) != before):
            raise ProjectionUnavailable()
        crash_point("postflight")
        connection.execute("COMMIT")
        crash_point("committed")
        return True
    except (sqlite3.Error, OSError, ValueError):
        raise ProjectionUnavailable() from None
    finally:
        if connection is not None:
            try:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
            finally:
                connection.close()
        owner.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=OPERATION + " (offline NI02 maintenance only)")
    parser.add_argument("direction", choices=("up", "down"))
    parser.add_argument("--maintenance-confirmed", action="store_true", required=True,
                        help="All NI02 writer and NI03/NI04 readers are stopped by the operator")
    args = parser.parse_args(argv)
    try:
        from .config import projection_config_from_env
        changed = migrate(projection_config_from_env(), direction=args.direction,
                          maintenance_confirmed=args.maintenance_confirmed)
        print(OPERATION + (":changed" if changed else ":unchanged"))
        return 0
    except Exception:
        print(OPERATION + ":unavailable")  # no paths, records or exception text
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
