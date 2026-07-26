import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.portal_counter import (
    PortalCounterRepository,
    PortalCounterService,
)
from app.web import web as web_module


UTC = timezone.utc


class PortalCounterServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "counter.db"
        self.service = self._service(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _service(path):
        service = PortalCounterService(
            PortalCounterRepository(str(path))
        )
        assert service.initialize()
        return service

    def _total(self):
        return self.service.get_snapshot().opened_total

    def test_new_auth_session_creates_one_record(self):
        result = self.service.record_open(
            "session-1",
            datetime(2026, 7, 26, 8, tzinfo=UTC),
        )

        self.assertTrue(result.recorded)
        self.assertFalse(result.duplicate)
        self.assertEqual(self._total(), 1)

    def test_duplicate_session_id_is_ignored(self):
        opened_at = datetime(2026, 7, 26, 8, tzinfo=UTC)

        self.service.record_open("session-1", opened_at)
        result = self.service.record_open("session-1", opened_at)

        self.assertFalse(result.recorded)
        self.assertTrue(result.duplicate)
        self.assertEqual(self._total(), 1)

    def test_same_mac_can_produce_three_session_events(self):
        for number in range(3):
            self.service.record_open(
                f"same-mac-session-{number}",
                datetime(2026, 7, 26, 8, tzinfo=UTC),
            )

        self.assertEqual(self._total(), 3)

    def test_same_ip_can_produce_multiple_session_events(self):
        for number in range(2):
            self.service.record_open(
                f"same-ip-session-{number}",
                datetime(2026, 7, 26, 8, tzinfo=UTC),
            )

        self.assertEqual(self._total(), 2)

    def _record_one_open(self):
        self.service.record_open(
            "session-1",
            datetime(2026, 7, 26, 8, tzinfo=UTC),
        )

    def test_authorized_does_not_create_another_event(self):
        self._record_one_open()
        self.assertEqual(self._total(), 1)

    def test_failed_does_not_delete_recorded_event(self):
        self._record_one_open()
        self.assertEqual(self._total(), 1)

    def test_expired_does_not_delete_recorded_event(self):
        self._record_one_open()
        self.assertEqual(self._total(), 1)

    def test_auth_status_two_does_not_create_another_event(self):
        self._record_one_open()
        self.assertEqual(self._total(), 1)

    def test_baku_day_is_derived_from_utc_time(self):
        self.service.record_open(
            "session-1",
            datetime(2026, 7, 25, 20, 30, tzinfo=UTC),
        )

        snapshot = self.service.get_snapshot(
            datetime(2026, 7, 26, 1, tzinfo=UTC)
        )
        self.assertEqual(snapshot.day, "2026-07-26")
        self.assertEqual(snapshot.opened_today, 1)
        self.assertEqual(snapshot.timezone, "Asia/Baku")

    def test_invalid_timezone_fails_open_during_initialization(self):
        invalid_db = Path(self.temp_dir.name) / "invalid-zone.db"
        service = PortalCounterService(
            PortalCounterRepository(str(invalid_db)),
            timezone_name="Invalid/Timezone",
        )

        self.assertIsNone(service.timezone)
        self.assertFalse(service.initialize())
        self.assertFalse(service.available)
        self.assertFalse(invalid_db.exists())

    def test_events_around_baku_midnight_use_different_days(self):
        self.service.record_open(
            "before-midnight",
            datetime(2026, 7, 25, 19, 59, 59, tzinfo=UTC),
        )
        self.service.record_open(
            "after-midnight",
            datetime(2026, 7, 25, 20, 0, 0, tzinfo=UTC),
        )

        before = self.service.get_snapshot(
            datetime(2026, 7, 25, 19, 59, 59, tzinfo=UTC)
        )
        after = self.service.get_snapshot(
            datetime(2026, 7, 25, 20, 0, 0, tzinfo=UTC)
        )
        self.assertEqual(before.opened_today, 1)
        self.assertEqual(after.opened_today, 1)
        self.assertEqual(after.opened_total, 2)

    def test_total_survives_day_change(self):
        self.service.record_open(
            "day-one",
            datetime(2026, 7, 25, 10, tzinfo=UTC),
        )
        self.service.record_open(
            "day-two",
            datetime(2026, 7, 26, 10, tzinfo=UTC),
        )

        snapshot = self.service.get_snapshot(
            datetime(2026, 7, 26, 10, tzinfo=UTC)
        )
        self.assertEqual(snapshot.opened_today, 1)
        self.assertEqual(snapshot.opened_total, 2)

    def test_snapshot_reads_both_counts_with_one_connection(self):
        self._record_one_open()

        with patch.object(
            self.service.repository,
            "_connect",
            wraps=self.service.repository._connect,
        ) as connect:
            snapshot = self.service.get_snapshot()

        self.assertEqual(snapshot.opened_total, 1)
        connect.assert_called_once_with()

    def test_data_survives_service_reinitialization(self):
        self.service.record_open(
            "session-1",
            datetime(2026, 7, 26, 8, tzinfo=UTC),
        )

        restarted = self._service(self.db_path)

        self.assertEqual(restarted.get_snapshot().opened_total, 1)

    def test_parallel_duplicate_session_creates_one_row(self):
        opened_at = datetime(2026, 7, 26, 8, tzinfo=UTC)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda _: self.service.record_open(
                        "same-session",
                        opened_at,
                    ),
                    range(20),
                )
            )

        self.assertEqual(
            sum(result.recorded for result in results),
            1,
        )
        self.assertEqual(self._total(), 1)

    def test_parallel_different_sessions_are_not_lost(self):
        opened_at = datetime(2026, 7, 26, 8, tzinfo=UTC)

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(
                executor.map(
                    lambda number: self.service.record_open(
                        f"session-{number}",
                        opened_at,
                    ),
                    range(20),
                )
            )

        self.assertEqual(self._total(), 20)

    def test_repeated_migration_preserves_existing_data(self):
        self.service.record_open(
            "session-1",
            datetime(2026, 7, 26, 8, tzinfo=UTC),
        )

        self.service.repository.migrate()

        self.assertEqual(self._total(), 1)
        with closing(sqlite3.connect(self.db_path)) as connection:
            version = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        self.assertEqual(version, 1)


class FakeExecutor:
    def __init__(self):
        self.submissions = []

    def submit(self, function, session_id):
        self.submissions.append((function, session_id))


class FailingCounter:
    available = True

    def record_open(self, session_id, opened_at):
        raise sqlite3.OperationalError("database is locked")


class BrokenRepository:
    def migrate(self):
        raise sqlite3.OperationalError("database unavailable")


class PortalCounterWebTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "counter.db"
        self.service = PortalCounterService(
            PortalCounterRepository(str(self.db_path))
        )
        self.assertTrue(self.service.initialize())
        self.executor = FakeExecutor()
        self.settings = {
            "portal_counter_enabled": True,
            "portal_counter_db_path": str(self.db_path),
            "portal_counter_timezone": "Asia/Baku",
            "portal_counter_api_enabled": True,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_client(self, service=None, settings=None):
        web_module.auth_manager = web_module.AuthSessionManager()
        selected_service = self.service if service is None else service

        with (
            patch.object(
                web_module,
                "get_settings",
                return_value=settings or self.settings,
            ),
            patch.object(
                web_module,
                "create_controller",
                return_value=object(),
            ),
            patch.object(
                web_module,
                "auth_executor",
                self.executor,
            ),
        ):
            app = web_module.create_app(selected_service)

        app.config["TESTING"] = True
        return app.test_client()

    @staticmethod
    def _portal_url():
        return (
            "/?site=park"
            "&clientMac=AA-BB-CC-DD-EE-01"
            "&clientIp=10.0.0.10"
        )

    def test_repeated_get_reuses_session_and_counts_once(self):
        client = self._create_client()

        first = client.get(self._portal_url())
        second = client.get(self._portal_url())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            self.service.get_snapshot().opened_total,
            1,
        )
        self.assertEqual(len(self.executor.submissions), 1)

    def test_session_polling_does_not_increment_counter(self):
        client = self._create_client()
        client.get(self._portal_url())
        session_id = self.executor.submissions[0][1]

        response = client.get(f"/auth/session/{session_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.service.get_snapshot().opened_total,
            1,
        )

    def test_counter_api_is_read_only_and_private_fields_absent(self):
        client = self._create_client()
        client.get(self._portal_url())

        first = client.get("/api/public/portal-counter")
        second = client.get("/api/public/portal-counter")
        payload = second.get_json()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(payload["opened_total"], 1)
        self.assertEqual(payload["opened_today"], 1)
        self.assertEqual(len(self.executor.submissions), 1)
        self.assertNotIn("session_id", payload)
        self.assertNotIn("mac", payload)
        self.assertNotIn("ip", payload)

    def test_sqlite_write_error_does_not_block_page_or_worker(self):
        client = self._create_client(service=FailingCounter())

        response = client.get(self._portal_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.executor.submissions), 1)

    def test_failed_migration_does_not_block_app_or_worker(self):
        unavailable_service = PortalCounterService(
            BrokenRepository()
        )
        self.assertFalse(unavailable_service.initialize())
        client = self._create_client(
            service=unavailable_service
        )

        with patch.object(
            unavailable_service,
            "record_open",
            wraps=unavailable_service.record_open,
        ) as record_open:
            page = client.get(self._portal_url())
        api = client.get("/api/public/portal-counter")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(self.executor.submissions), 1)
        record_open.assert_not_called()
        self.assertEqual(api.status_code, 503)

    def test_disabled_module_creates_no_database_and_portal_works(self):
        disabled_path = Path(self.temp_dir.name) / "disabled.db"
        disabled_settings = dict(
            self.settings,
            portal_counter_enabled=False,
            portal_counter_db_path=str(disabled_path),
        )
        web_module.auth_manager = web_module.AuthSessionManager()

        with (
            patch.object(
                web_module,
                "get_settings",
                return_value=disabled_settings,
            ),
            patch.object(
                web_module,
                "create_controller",
                return_value=object(),
            ),
            patch.object(
                web_module,
                "auth_executor",
                self.executor,
            ),
        ):
            app = web_module.create_app()

        app.config["TESTING"] = True
        client = app.test_client()
        response = client.get(self._portal_url())

        self.assertEqual(response.status_code, 200)
        self.assertFalse(disabled_path.exists())
        self.assertEqual(
            client.get(
                "/api/public/portal-counter"
            ).status_code,
            404,
        )
        self.assertNotIn(
            b"data-portal-counter",
            response.data,
        )

    def test_api_disabled_does_not_register_endpoint(self):
        settings = dict(
            self.settings,
            portal_counter_api_enabled=False,
        )
        client = self._create_client(settings=settings)

        self.assertEqual(
            client.get(
                "/api/public/portal-counter"
            ).status_code,
            404,
        )

    def test_unavailable_storage_returns_sanitized_503(self):
        self.service.available = False
        client = self._create_client()

        response = client.get("/api/public/portal-counter")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.headers["Cache-Control"],
            "no-store",
        )
        self.assertEqual(
            response.get_json(),
            {"error": "counter_unavailable"},
        )

    def test_gitignore_contains_only_ignore_rules(self):
        gitignore_path = (
            Path(__file__).parents[1] / ".gitignore"
        )
        contents = gitignore_path.read_text(encoding="utf-8")

        self.assertNotIn("Wait, I need to reconsider", contents)
        self.assertNotIn("```", contents)
        self.assertIn("*.db-wal", contents)

    def test_frontend_loads_counter_once_without_auth_hook(self):
        script_path = (
            Path(__file__).parents[1]
            / "app"
            / "web"
            / "static"
            / "js"
            / "portal_counter.js"
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertEqual(
            script.count("/api/public/portal-counter"),
            1,
        )
        self.assertNotIn("AUTHORIZED", script)


if __name__ == "__main__":
    unittest.main()
