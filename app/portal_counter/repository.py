"""SQLite persistence for portal-open events."""

import sqlite3
from contextlib import closing
from pathlib import Path

from .models import RecordOpenResult


SCHEMA_VERSION = 1
DEFAULT_BUSY_TIMEOUT_MS = 250


class PortalCounterRepository:
    def __init__(
        self,
        db_path: str,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ):
        self.db_path = Path(db_path)
        self.busy_timeout_ms = min(
            DEFAULT_BUSY_TIMEOUT_MS,
            max(1, int(busy_timeout_ms)),
        )

    def migrate(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as connection:
            current_version = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]

            if current_version > SCHEMA_VERSION:
                raise RuntimeError(
                    "Portal counter database schema is newer "
                    "than this application"
                )

            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS portal_open_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    opened_at TEXT NOT NULL,
                    opened_day TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_portal_open_events_day
                ON portal_open_events(opened_day)
                """
            )
            connection.execute(
                f"PRAGMA user_version={SCHEMA_VERSION}"
            )
            connection.commit()

    def insert_open(
        self,
        session_id: str,
        opened_at: str,
        opened_day: str,
    ) -> RecordOpenResult:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO portal_open_events (
                    session_id,
                    opened_at,
                    opened_day
                )
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, opened_at, opened_day),
            )
            connection.commit()
            recorded = cursor.rowcount == 1

        return RecordOpenResult(
            recorded=recorded,
            duplicate=not recorded,
        )

    def get_counts(
        self,
        opened_day: str,
    ) -> tuple[int, int]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            today = connection.execute(
                """
                SELECT COUNT(*)
                FROM portal_open_events
                WHERE opened_day = ?
                """,
                (opened_day,),
            ).fetchone()[0]
            total = connection.execute(
                "SELECT COUNT(*) FROM portal_open_events"
            ).fetchone()[0]
            connection.rollback()

        return int(today), int(total)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000,
        )
        try:
            connection.execute(
                f"PRAGMA busy_timeout={self.busy_timeout_ms}"
            )
            connection.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            connection.close()
            raise
        return connection
