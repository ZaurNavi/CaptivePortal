import json
import logging
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.auth.manager import AuthSessionManager
from app.auth.session import AuthStatus
from app.auth.worker import AuthWorker
from app.auth_telemetry import AuthorizationTelemetry
from app.auth_telemetry import events
from app.auth_telemetry.schemas import build_record
from app.models import Result


class AuthTelemetryUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "auth_telemetry.log"

    def tearDown(self):
        AuthorizationTelemetry(enabled=False, log_path="")
        self.temp_dir.cleanup()

    def service(self, **overrides):
        options = {
            "enabled": True,
            "log_path": str(self.path),
            "level": "DEBUG",
            "schema_version": 1,
            "rotation_max_bytes": 52_428_800,
            "rotation_backup_count": 10,
        }
        options.update(overrides)
        return AuthorizationTelemetry(**options)

    def records(self, path=None):
        selected = path or self.path
        return [
            json.loads(line)
            for line in selected.read_text(encoding="utf-8").splitlines()
        ]

    def test_valid_one_line_json_with_newline_and_utf8(self):
        service = self.service()
        self.assertTrue(
            service.safe_emit(
                "auth.test",
                "сессия-1",
                client_ip="192.168.0.10",
            )
        )
        raw = self.path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(raw.count(b"\n"), 1)
        decoded = raw.decode("utf-8")
        self.assertIn("сессия", decoded)
        json.loads(decoded)

    def test_common_schema_timestamp_and_level(self):
        self.service().safe_emit("auth.test", "s-1", "WARNING")
        record = self.records()[0]
        self.assertEqual(record["level"], "warning")
        self.assertEqual(record["service"], "captive_portal")
        self.assertEqual(record["module"], "auth_telemetry")
        self.assertEqual(record["event"], "auth.test")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["session_id"], "s-1")
        self.assertRegex(
            record["timestamp"],
            r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$",
        )

    def test_mac_is_full_and_normalized_while_ip_is_unchanged(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            client_mac="aa-bb.ccdd:ee ff",
            client_ip="2001:db8::42",
        )
        record = self.records()[0]
        self.assertEqual(record["client_mac"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(record["client_ip"], "2001:db8::42")

    def test_secret_fields_and_labeled_values_are_redacted(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            access_token="do-not-write",
            client_secret="do-not-write-either",
            error="access_token=also-secret request failed",
        )
        raw = self.path.read_text(encoding="utf-8")
        self.assertNotIn("do-not-write", raw)
        self.assertNotIn("also-secret", raw)
        record = self.records()[0]
        self.assertNotIn("access_token", record)
        self.assertNotIn("client_secret", record)

    def test_disabled_does_not_create_or_change_file(self):
        self.path.write_text("existing\n", encoding="utf-8")
        service = self.service(enabled=False)
        self.assertFalse(service.safe_emit("auth.test", "s-1"))
        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            "existing\n",
        )

    def test_initialization_and_write_errors_are_fail_open(self):
        with self.assertLogs("captivportal", level="ERROR") as captured:
            service = self.service(log_path=self.temp_dir.name)
        self.assertFalse(service.available)
        self.assertFalse(service.safe_emit("auth.test", "s-1"))
        self.assertEqual(len(captured.output), 1)
        self.assertIn(
            "auth_telemetry.initialization_failed",
            captured.output[0],
        )

    def test_reinitialization_has_one_handler_and_no_propagation(self):
        first = self.service()
        second = self.service()
        handlers = [
            handler
            for handler in second.logger.handlers
            if getattr(
                handler,
                "_captive_portal_auth_telemetry",
                False,
            )
        ]
        self.assertEqual(len(handlers), 1)
        self.assertFalse(first.logger.propagate)
        second.safe_emit("auth.test", "s-1")
        self.assertEqual(len(self.records()), 1)

    def test_long_multiline_error_is_single_line_and_truncated(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            "error",
            error=("ошибка\n\t\x00" + ("x" * 1000)),
        )
        raw = self.path.read_text(encoding="utf-8")
        self.assertEqual(raw.count("\n"), 1)
        record = self.records()[0]
        self.assertLessEqual(len(record["error"]), 512)
        self.assertNotRegex(record["error"], r"[\r\n\t\x00]")

    def test_concurrent_threads_never_mix_json_lines(self):
        service = self.service()

        def emit(index):
            for item in range(25):
                service.safe_emit(
                    "auth.test",
                    f"s-{index}",
                    sequence=item,
                )

        threads = [
            threading.Thread(target=emit, args=(index,))
            for index in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(self.records()), 200)

    def test_rotation_produces_readable_files(self):
        service = self.service(
            rotation_max_bytes=300,
            rotation_backup_count=3,
        )
        for index in range(30):
            service.safe_emit(
                "auth.rotation",
                f"s-{index}",
                error="x" * 80,
            )
        rotated = sorted(self.path.parent.glob("auth_telemetry.log.*"))
        self.assertTrue(rotated)
        for path in [self.path, *rotated]:
            self.assertTrue(os.access(path, os.R_OK))
            for line in path.read_text(encoding="utf-8").splitlines():
                json.loads(line)

    def test_info_level_excludes_debug(self):
        service = self.service(level="INFO")
        service.safe_emit("auth.debug", "s-1", "debug")
        service.safe_emit("auth.info", "s-1", "info")
        self.assertEqual(
            [record["event"] for record in self.records()],
            ["auth.info"],
        )

    def test_once_event_is_emitted_once(self):
        service = self.service()
        self.assertTrue(
            service.safe_emit_once(events.SESSION_FINISHED, "s-1")
        )
        self.assertFalse(
            service.safe_emit_once(events.SESSION_FINISHED, "s-1")
        )
        self.assertEqual(len(self.records()), 1)

    def test_required_fields_are_always_present(self):
        self.service().safe_emit("auth.test", "s-1")
        self.assertTrue({
            "timestamp",
            "level",
            "service",
            "module",
            "event",
            "schema_version",
            "session_id",
        }.issubset(self.records()[0]))

    def test_schema_version_is_one(self):
        self.service().safe_emit("auth.test", "s-1")
        self.assertEqual(self.records()[0]["schema_version"], 1)

    def test_timestamp_uses_utc_z_suffix(self):
        self.service().safe_emit("auth.test", "s-1")
        self.assertTrue(self.records()[0]["timestamp"].endswith("Z"))

    def test_level_is_lowercase(self):
        self.service().safe_emit("auth.test", "s-1", "CRITICAL")
        self.assertEqual(self.records()[0]["level"], "critical")

    def test_unicode_field_round_trips(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            omada_message="İcazə verildi — разрешено",
        )
        self.assertEqual(
            self.records()[0]["omada_message"],
            "İcazə verildi — разрешено",
        )

    def test_access_token_key_is_absent(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            accessToken="forbidden",
        )
        self.assertNotIn("forbidden", self.path.read_text("utf-8"))

    def test_client_secret_key_is_absent(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            CLIENT_SECRET="forbidden",
        )
        self.assertNotIn("forbidden", self.path.read_text("utf-8"))

    def test_ipv4_is_not_masked(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            client_ip="203.0.113.42",
        )
        self.assertEqual(
            self.records()[0]["client_ip"],
            "203.0.113.42",
        )

    def test_dotted_mac_is_normalized(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            client_mac="aabb.ccdd.eeff",
        )
        self.assertEqual(
            self.records()[0]["client_mac"],
            "AA:BB:CC:DD:EE:FF",
        )

    def test_colon_mac_remains_normalized(self):
        self.service().safe_emit(
            "auth.test",
            "s-1",
            client_mac="aa:bb:cc:dd:ee:ff",
        )
        self.assertEqual(
            self.records()[0]["client_mac"],
            "AA:BB:CC:DD:EE:FF",
        )

    def test_each_emit_adds_exactly_one_line(self):
        service = self.service()
        service.safe_emit("auth.one", "s-1")
        service.safe_emit("auth.two", "s-1")
        self.assertEqual(
            len(self.path.read_text("utf-8").splitlines()),
            2,
        )

    def test_file_is_append_only_across_reinitialization(self):
        self.service().safe_emit("auth.one", "s-1")
        self.service().safe_emit("auth.two", "s-2")
        self.assertEqual(
            [record["event"] for record in self.records()],
            ["auth.one", "auth.two"],
        )

    def test_handler_write_error_is_reported_and_once_can_retry(self):
        service = self.service()
        handler = next(
            handler
            for handler in service.logger.handlers
            if getattr(
                handler,
                "_captive_portal_auth_telemetry",
                False,
            )
        )
        original_stream = handler.stream

        class BrokenStream:
            def write(self, _value):
                raise OSError("disk full")

            def flush(self):
                return None

        handler.stream = BrokenStream()
        with self.assertLogs("captivportal", level="ERROR") as captured:
            self.assertFalse(
                service.safe_emit_once(
                    events.SESSION_FINISHED,
                    "s-retry",
                )
            )
            self.assertFalse(
                service.safe_emit_once(
                    events.SESSION_FINISHED,
                    "s-retry",
                )
            )
        self.assertEqual(len(captured.output), 1)
        self.assertIn("auth_telemetry.write_failed", captured.output[0])

        handler.stream = original_stream
        self.assertTrue(
            service.safe_emit_once(
                events.SESSION_FINISHED,
                "s-retry",
            )
        )
        self.assertEqual(len(self.records()), 1)

    def test_reserved_fields_cannot_be_overwritten(self):
        record = build_record(
            event="auth.real",
            session_id="real-session",
            level="warning",
            schema_version=1,
            fields={
                "timestamp": "fake",
                "level": "critical",
                "service": "other",
                "module": "other",
                "event": "auth.fake",
                "schema_version": 999,
                "session_id": "fake-session",
            },
        )
        self.assertNotEqual(record["timestamp"], "fake")
        self.assertEqual(record["level"], "warning")
        self.assertEqual(record["service"], "captive_portal")
        self.assertEqual(record["module"], "auth_telemetry")
        self.assertEqual(record["event"], "auth.real")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["session_id"], "real-session")


class SequenceProvider:
    def __init__(
        self,
        clients,
        auth_results=None,
        reset_result=None,
    ):
        self.clients = list(clients)
        self.auth_results = list(
            auth_results or [Result.ok()] * 3
        )
        self.reset_result = reset_result or Result.ok()
        self.get_client_calls = 0
        self.authorize_calls = 0
        self.unauthorize_calls = 0

    def get_client(self, **_kwargs):
        self.get_client_calls += 1
        if len(self.clients) > 1:
            return self.clients.pop(0)
        return self.clients[0]

    def authorize(self, **_kwargs):
        result = self.auth_results[
            min(self.authorize_calls, len(self.auth_results) - 1)
        ]
        self.authorize_calls += 1
        return result

    def unauthorize(self, **_kwargs):
        self.unauthorize_calls += 1
        return self.reset_result


def client_result(auth_status=0, active=True):
    return Result.ok(
        data={
            "http_status": 200,
            "error_code": 0,
            "authStatus": auth_status,
            "active": active,
        }
    )


class AuthWorkerTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "auth.log"
        self.telemetry = AuthorizationTelemetry(
            enabled=True,
            log_path=str(self.path),
            level="DEBUG",
            schema_version=1,
            rotation_max_bytes=1_000_000,
            rotation_backup_count=2,
        )
        import app.auth_telemetry.service as service_module
        service_module._service = self.telemetry
        self.manager = AuthSessionManager()
        self.patchers = [
            patch("app.auth.worker.MIN_INITIAL_DELAY_SECONDS", 0),
            patch("app.auth.worker.AUTH_FALLBACK_DELAY_SECONDS", 0),
            patch("app.auth.worker.CLIENT_READY_POLL_SECONDS", 0),
            patch("app.auth.worker.VERIFY_DELAY_SECONDS", 0),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        AuthorizationTelemetry(enabled=False, log_path="")
        self.temp_dir.cleanup()

    def session(self):
        session, _ = self.manager.create_or_get(
            site_id="park",
            client_mac="aa-bb-cc-dd-ee-ff",
            client_ip="192.168.1.10",
        )
        self.manager.claim_worker(session)
        return session

    def run_worker(self, provider):
        session = self.session()
        AuthWorker(provider, self.manager).process(session.session_id)
        records = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
        ]
        return session, records

    def final(self, records):
        finals = [
            record for record in records
            if record["event"] == events.SESSION_FINISHED
        ]
        self.assertEqual(len(finals), 1)
        return finals[0]

    def records(self):
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
        ]

    def test_already_authorized(self):
        session, records = self.run_worker(
            SequenceProvider([client_result(2, True)])
        )
        final = self.final(records)
        self.assertEqual(session.status, AuthStatus.AUTHORIZED)
        self.assertEqual(final["final_reason"], "ALREADY_AUTHORIZED")
        self.assertEqual(final["auth_attempts"], 0)
        self.assertEqual(final["level"], "info")
        self.assertEqual(
            sum(
                record["event"] == events.CLIENT_READY
                for record in records
            ),
            1,
        )

    def test_authorized_after_attempt(self):
        session, records = self.run_worker(
            SequenceProvider([
                client_result(0, True),
                client_result(2, True),
            ])
        )
        final = self.final(records)
        self.assertEqual(session.status, AuthStatus.AUTHORIZED)
        self.assertEqual(
            final["final_reason"],
            "AUTHORIZED_AFTER_ATTEMPT",
        )
        self.assertEqual(final["auth_attempts"], 1)

    def test_final_verification_success(self):
        provider = SequenceProvider([
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
                client_result(2, True),
            ])
        session, records = self.run_worker(provider)
        final = self.final(records)
        self.assertEqual(session.status, AuthStatus.AUTHORIZED)
        self.assertEqual(
            final["final_reason"],
            "AUTHORIZED_FINAL_VERIFY",
        )
        self.assertEqual(provider.authorize_calls, 3)
        self.assertEqual(provider.get_client_calls, 5)
        self.assertEqual(provider.unauthorize_calls, 0)

    def test_fallback_is_recorded_and_worker_continues(self):
        session, records = self.run_worker(
            SequenceProvider([
                client_result(0, False),
                client_result(2, True),
            ])
        )
        self.assertEqual(session.status, AuthStatus.AUTHORIZED)
        self.assertIn(
            events.FALLBACK_TRIGGERED,
            [record["event"] for record in records],
        )

    def test_exhausted_authorization_resets_session(self):
        provider = SequenceProvider([
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
            ])
        session, records = self.run_worker(provider)
        final = self.final(records)
        self.assertEqual(session.status, AuthStatus.RESET)
        self.assertEqual(
            final["final_reason"],
            "AUTH_EXHAUSTED_RESET_SUCCEEDED",
        )
        self.assertEqual(final["level"], "warning")
        self.assertIn("last_omada_error_code", final)
        self.assertNotIn("last_error_code", final)
        self.assertEqual(provider.authorize_calls, 3)
        self.assertEqual(provider.get_client_calls, 5)
        self.assertEqual(provider.unauthorize_calls, 1)

    def test_reset_failure_is_failed(self):
        provider = SequenceProvider(
            [
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
                client_result(0, True),
            ],
            reset_result=Result.fail(
                "UNAUTH_FAILED",
                "reset rejected",
                {"http_status": 500, "error_code": -1},
            ),
        )
        session, records = self.run_worker(provider)
        final = self.final(records)
        self.assertEqual(session.status, AuthStatus.FAILED)
        self.assertEqual(
            final["final_reason"],
            "RESET_REQUEST_FAILED",
        )
        self.assertEqual(final["level"], "error")

    def test_provider_exception_is_sanitized_and_worker_continues(self):
        class BrokenProvider(SequenceProvider):
            def get_client(self, **_kwargs):
                raise RuntimeError("boom\nsecond line")

        session, records = self.run_worker(
            BrokenProvider([client_result()])
        )
        self.assertIn(
            events.OMADA_UNAVAILABLE,
            [record["event"] for record in records],
        )
        self.assertTrue(self.path.read_text(encoding="utf-8").endswith("\n"))
        self.assertNotEqual(session.status, AuthStatus.WAITING)

    def test_real_worker_exception_emits_failed_final_event(self):
        session = self.session()
        worker = AuthWorker(
            SequenceProvider([client_result()]),
            self.manager,
        )
        with patch.object(
            worker,
            "_sleep_with_ttl_check",
            side_effect=RuntimeError("worker\nfailed"),
        ):
            worker.process(session.session_id)

        records = self.records()
        worker_exceptions = [
            record for record in records
            if record["event"] == events.WORKER_EXCEPTION
        ]
        self.assertEqual(len(worker_exceptions), 1)
        self.assertEqual(session.status, AuthStatus.FAILED)
        final = self.final(records)
        self.assertEqual(final["final_reason"], "WORKER_EXCEPTION")
        self.assertEqual(final["final_state"], "FAILED")
        self.assertEqual(final["level"], "error")

    def test_token_failure_emits_token_error_without_token_data(self):
        token_failure = Result.fail(
            error="TOKEN_FAILED",
            message="token request rejected",
            data={"http_status": 401, "error_code": -1},
        )
        _session, records = self.run_worker(
            SequenceProvider([token_failure])
        )
        token_events = [
            record for record in records
            if record["event"] == events.TOKEN_ERROR
        ]
        self.assertTrue(token_events)
        raw = self.path.read_text(encoding="utf-8").lower()
        self.assertNotIn("access_token", raw)
        self.assertNotIn("client_secret", raw)

    def test_expired_final_event_is_warning(self):
        session = self.session()
        session._created_monotonic -= 120
        AuthWorker(
            SequenceProvider([client_result()]),
            self.manager,
        ).process(session.session_id)
        final = self.final(self.records())
        self.assertEqual(final["final_state"], "EXPIRED")
        self.assertEqual(final["final_reason"], "SESSION_EXPIRED")
        self.assertEqual(final["level"], "warning")

    def test_progress_updates_use_session_id_contract(self):
        class IdOnlyManager(AuthSessionManager):
            def set_progress(self, session_or_id, progress):
                if not isinstance(session_or_id, str):
                    raise TypeError("set_progress requires session_id")
                return super().set_progress(session_or_id, progress)

        self.manager = IdOnlyManager()
        session, records = self.run_worker(
            SequenceProvider([
                client_result(0, True),
                client_result(2, True),
            ])
        )
        self.assertEqual(session.status, AuthStatus.AUTHORIZED)
        self.assertEqual(
            self.final(records)["final_reason"],
            "AUTHORIZED_AFTER_ATTEMPT",
        )

    def test_client_found_is_unknown_for_transport_failure(self):
        transport_failure = Result.fail(
            error="HTTP_ERROR",
            message="timeout",
            data={"http_status": 0, "error_code": 0},
        )
        self.assertIsNone(AuthWorker._client_found(transport_failure))

    def test_client_found_is_false_only_for_explicit_not_found(self):
        not_found = Result.fail(
            error="CLIENT_NOT_FOUND",
            message="client not found",
            data={"http_status": 404, "error_code": -4},
        )
        self.assertFalse(AuthWorker._client_found(not_found))

    def test_omada_unavailable_uses_operation_specific_counter(self):
        session = self.session()
        worker = AuthWorker(
            SequenceProvider([client_result()]),
            self.manager,
        )
        failure = Result.fail(
            error="HTTP_ERROR",
            message="timeout",
            data={"http_status": 0, "error_code": 0},
        )
        worker._emit_omada_unavailable(
            session,
            operation="readiness",
            result=failure,
            response_time_ms=10,
            operation_number=2,
        )
        worker._emit_omada_unavailable(
            session,
            operation="authorize",
            result=failure,
            response_time_ms=11,
            operation_number=3,
        )
        records = self.records()
        self.assertEqual(records[0]["readiness_check"], 2)
        self.assertNotIn("auth_attempt", records[0])
        self.assertEqual(records[1]["auth_attempt"], 3)
        self.assertNotIn("readiness_check", records[1])
        self.assertNotIn("attempt", records[0])
        self.assertNotIn("attempt", records[1])

    def test_unavailable_telemetry_does_not_block_authorization(self):
        import app.auth_telemetry.service as service_module
        unavailable = AuthorizationTelemetry(
            enabled=True,
            log_path=self.temp_dir.name,
        )
        self.assertFalse(unavailable.available)
        service_module._service = unavailable
        session = self.session()
        provider = SequenceProvider([client_result(2, True)])
        AuthWorker(provider, self.manager).process(session.session_id)
        self.assertEqual(session.status, AuthStatus.AUTHORIZED)


class AuthWorkerProductionContractTests(unittest.TestCase):
    def test_production_timing_and_attempt_constants_are_unchanged(self):
        import app.auth.worker as worker_module

        self.assertEqual(worker_module.MIN_INITIAL_DELAY_SECONDS, 5.0)
        self.assertEqual(worker_module.AUTH_FALLBACK_DELAY_SECONDS, 13.0)
        self.assertEqual(worker_module.CLIENT_READY_POLL_SECONDS, 3.0)
        self.assertEqual(worker_module.VERIFY_DELAY_SECONDS, 3.0)
        self.assertEqual(worker_module.MAX_AUTH_ATTEMPTS, 3)
        self.assertEqual(
            worker_module.SLEEP_CHECK_INTERVAL_SECONDS,
            0.25,
        )


class AuthTelemetryWebIntegrationTests(unittest.TestCase):
    def test_new_then_repeated_get_records_created_once_and_reused(self):
        import app.web.web as web_module

        class CapturingExecutor:
            def __init__(self):
                self.submitted = []

            def submit(self, function, session_id):
                self.submitted.append((function, session_id))

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "auth.log"
            settings = {
                "portal_counter_enabled": False,
                "portal_counter_db_path": str(
                    Path(temp_dir) / "counter.db"
                ),
                "portal_counter_timezone": "Asia/Baku",
                "portal_counter_api_enabled": False,
                "auth_telemetry_enabled": True,
                "auth_telemetry_log_path": str(log_path),
                "auth_telemetry_level": "DEBUG",
                "auth_telemetry_schema_version": 1,
                "auth_telemetry_rotation_max_bytes": 1_000_000,
                "auth_telemetry_rotation_backup_count": 2,
            }
            executor = CapturingExecutor()
            web_module.auth_manager = AuthSessionManager()
            with (
                patch.object(
                    web_module,
                    "get_settings",
                    return_value=settings,
                ),
                patch.object(
                    web_module,
                    "create_controller",
                    return_value=object(),
                ),
                patch.object(
                    web_module,
                    "auth_executor",
                    executor,
                ),
            ):
                app = web_module.create_app(
                    portal_counter_service=None
                )
                client = app.test_client()
                query = (
                    "/?site=park&clientMac=aa-bb-cc-dd-ee-ff"
                    "&clientIp=192.168.1.5"
                )
                self.assertEqual(client.get(query).status_code, 200)
                self.assertEqual(client.get(query).status_code, 200)

            records = [
                json.loads(line)
                for line in log_path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            created = [
                record for record in records
                if record["event"] == events.SESSION_CREATED
            ]
            reused = [
                record for record in records
                if record["event"] == events.SESSION_REUSED
            ]
            self.assertEqual(len(created), 1)
            self.assertEqual(len(reused), 1)
            self.assertEqual(len(executor.submitted), 1)
            AuthorizationTelemetry(enabled=False, log_path="")


if __name__ == "__main__":
    unittest.main()
