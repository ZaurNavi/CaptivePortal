"""SQLite-only SettingsStore: bounded connections, immutable history, one writer."""
import json
import sqlite3
from contextlib import contextmanager
from .definitions import SettingsDefinitionRegistry
from .models import SettingsError, TARGET, utc_now

SETTINGS_SCHEMA_VERSION = 1
SETTINGS_SQLITE_BUSY_TIMEOUT_MS = 1000
_DDL = (
    """CREATE TABLE settings_generations (
        generation_id INTEGER PRIMARY KEY,
        parent_generation_id INTEGER REFERENCES settings_generations(generation_id),
        scope_type TEXT NOT NULL CHECK(scope_type='global'), created_at_utc TEXT NOT NULL,
        created_by_principal_type TEXT NOT NULL, created_by_principal_name TEXT NOT NULL,
        request_id TEXT)""",
    """CREATE TABLE settings_overrides (
        generation_id INTEGER NOT NULL REFERENCES settings_generations(generation_id),
        setting_key TEXT NOT NULL, value_type TEXT NOT NULL CHECK(value_type='integer'),
        integer_value INTEGER NOT NULL, PRIMARY KEY(generation_id,setting_key))""",
    """CREATE TABLE settings_target_state (
        target TEXT PRIMARY KEY, effective_generation INTEGER REFERENCES settings_generations(generation_id),
        updated_at_utc TEXT)""",
    """CREATE TABLE settings_activation_events (
        event_id INTEGER PRIMARY KEY, generation_id INTEGER NOT NULL REFERENCES settings_generations(generation_id),
        target TEXT NOT NULL, attempted_at_utc TEXT NOT NULL,
        activation_result TEXT NOT NULL CHECK(activation_result IN ('adopted','failed')),
        effective_generation_after_attempt INTEGER REFERENCES settings_generations(generation_id),
        safe_error_code TEXT)""",
    """CREATE TABLE settings_mutation_audit (
        audit_id INTEGER PRIMARY KEY, generation_id INTEGER NOT NULL REFERENCES settings_generations(generation_id),
        parent_generation_id INTEGER REFERENCES settings_generations(generation_id),
        principal_type TEXT NOT NULL, principal_name TEXT NOT NULL,
        source_ip TEXT NOT NULL, request_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
        timestamp_utc TEXT NOT NULL, scope_type TEXT NOT NULL CHECK(scope_type='global'), scope_id TEXT,
        setting_key TEXT NOT NULL, operation TEXT NOT NULL CHECK(operation IN ('set','clear_override')),
        previous_persisted_override INTEGER, new_persisted_override INTEGER,
        previous_configured_value INTEGER NOT NULL, new_configured_value INTEGER NOT NULL,
        apply_requirement TEXT NOT NULL, activation_target TEXT NOT NULL,
        UNIQUE(generation_id,setting_key))""",
    """CREATE TABLE settings_idempotency (
        idempotency_id INTEGER PRIMARY KEY, principal_type TEXT NOT NULL, principal_name TEXT NOT NULL,
        scope_type TEXT NOT NULL CHECK(scope_type='global'), idempotency_key TEXT NOT NULL,
        request_payload_hash TEXT NOT NULL, result_http_status INTEGER NOT NULL,
        result_response_json TEXT NOT NULL CHECK(length(CAST(result_response_json AS BLOB))<=65536),
        result_generation INTEGER NOT NULL REFERENCES settings_generations(generation_id),
        result_changed INTEGER NOT NULL CHECK(result_changed IN (0,1)), created_at_utc TEXT NOT NULL,
        UNIQUE(principal_type,principal_name,scope_type,idempotency_key))""",
)
_IMMUTABLE = (
    "settings_generations", "settings_overrides", "settings_activation_events",
    "settings_mutation_audit", "settings_idempotency",
)
_TRIGGERS = tuple(
    f"CREATE TRIGGER {table}_immutable_{action.lower()} BEFORE {action} ON {table} "
    "BEGIN SELECT RAISE(ABORT,'immutable settings history'); END"
    for table in _IMMUTABLE for action in ("UPDATE", "DELETE")
)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class SettingsRepository:
    def __init__(self, db_path, registry=None):
        self.db_path = str(db_path)
        self.registry = registry or SettingsDefinitionRegistry()
        self.initialize()

    @contextmanager
    def transaction(self, *, write=False):
        connection = None
        try:
            connection = sqlite3.connect(self.db_path, timeout=1, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={SETTINGS_SQLITE_BUSY_TIMEOUT_MS}")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            raise SettingsError("settings_store_unavailable") from exc
        except Exception:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def initialize(self):
        with self.transaction(write=True) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            if version == 0 and not tables:
                for statement in (*_DDL, *_TRIGGERS):
                    db.execute(statement)
                db.execute("PRAGMA user_version=1")
                db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global',?,'system','settings_bootstrap',NULL)", (utc_now(),))
                db.execute("INSERT INTO settings_target_state VALUES(?,NULL,NULL)", (TARGET,))
            elif version != SETTINGS_SCHEMA_VERSION:
                raise SettingsError("settings_store_unavailable")
            expected = {statement.split()[2]: statement for statement in (*_DDL, *_TRIGGERS)}
            actual = {row[0]: row[1] for row in db.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','trigger') AND name NOT LIKE 'sqlite_%'")}
            normalize = lambda value: " ".join(value.split())
            if actual.keys() != expected.keys() or any(normalize(actual[key]) != normalize(sql) for key, sql in expected.items()):
                raise SettingsError("settings_store_unavailable")
            if db.execute("PRAGMA quick_check").fetchall()[0][0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
                raise SettingsError("settings_store_unavailable")
            root = db.execute("SELECT * FROM settings_generations WHERE generation_id=0").fetchone()
            if root is None or root[1] is not None or root[2] != "global" or tuple(root)[4:] != ("system", "settings_bootstrap", None):
                raise SettingsError("settings_store_unavailable")
            if db.execute("SELECT 1 FROM settings_overrides WHERE generation_id=0").fetchone():
                raise SettingsError("settings_store_unavailable")
            if db.execute("SELECT COUNT(*) FROM settings_target_state WHERE target=?", (TARGET,)).fetchone()[0] != 1:
                raise SettingsError("settings_store_unavailable")
            for row in db.execute("SELECT setting_key,value_type,integer_value FROM settings_overrides"):
                definition = self.registry.get(row[0])
                if definition is None or row[1] != "integer" or type(row[2]) is not int or not definition.min_value <= row[2] <= definition.max_value:
                    raise SettingsError("settings_store_unavailable")

    @staticmethod
    def head(db):
        # Reading the head under a transaction is not generation allocation.
        return db.execute("SELECT generation_id FROM settings_generations ORDER BY generation_id DESC LIMIT 1").fetchone()[0]

    @staticmethod
    def overrides(db, generation):
        return {row[0]: row[1] for row in db.execute("SELECT setting_key,integer_value FROM settings_overrides WHERE generation_id=?", (generation,))}

    def configured(self):
        with self.transaction() as db:
            head = self.head(db)
            return head, self.overrides(db, head)

    @staticmethod
    def effective(db):
        return db.execute("SELECT effective_generation FROM settings_target_state WHERE target=?", (TARGET,)).fetchone()[0]

    @staticmethod
    def latest_activation_result(db, generation):
        row = db.execute("SELECT activation_result FROM settings_activation_events WHERE generation_id=? ORDER BY event_id DESC LIMIT 1", (generation,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def latest_setting_audit(db, key, generation):
        row = db.execute("SELECT timestamp_utc,principal_type,principal_name FROM settings_mutation_audit WHERE setting_key=? AND generation_id<=? ORDER BY audit_id DESC LIMIT 1", (key, generation)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_generation(db, *, parent, principal, request_id, created_at, overrides):
        generation = db.execute("""INSERT INTO settings_generations
            (parent_generation_id,scope_type,created_at_utc,created_by_principal_type,created_by_principal_name,request_id)
            VALUES(?,'global',?,?,?,?)""", (parent, created_at, principal.principal_type, principal.username, request_id)).lastrowid
        db.executemany("INSERT INTO settings_overrides VALUES(?,?,'integer',?)", [(generation, key, value) for key, value in sorted(overrides.items())])
        return generation

    @staticmethod
    def append_mutation_audit(db, *, generation, parent, principal, source_ip, request_id,
                              idempotency_key, timestamp, key, operation, previous_override,
                              new_override, previous_value, new_value, apply_requirement, activation_target):
        db.execute("""INSERT INTO settings_mutation_audit (
            generation_id,parent_generation_id,principal_type,principal_name,source_ip,request_id,
            idempotency_key,timestamp_utc,scope_type,scope_id,setting_key,operation,
            previous_persisted_override,new_persisted_override,previous_configured_value,new_configured_value,
            apply_requirement,activation_target) VALUES(?,?,?,?,?,?,?,?,'global',NULL,?,?,?,?,?,?,?,?)""", (
                generation, parent, principal.principal_type, principal.username, source_ip, request_id,
                idempotency_key, timestamp, key, operation, previous_override, new_override,
                previous_value, new_value, apply_requirement, activation_target,
            ))

    @staticmethod
    def idempotency(db, principal, key):
        return db.execute("SELECT * FROM settings_idempotency WHERE principal_type=? AND principal_name=? AND scope_type='global' AND idempotency_key=?", (principal.principal_type, principal.username, key)).fetchone()

    def lookup_idempotency(self, principal, key):
        # Ordinary read transaction: successful replay never needs writer ownership.
        with self.transaction() as db:
            row = self.idempotency(db, principal, key)
            return dict(row) if row else None

    @staticmethod
    def save_idempotency(db, principal, key, payload_hash, status, body):
        serialized = canonical_json(body)
        if len(serialized.encode("utf-8")) > 65536:
            raise SettingsError("settings_store_unavailable")
        db.execute("""INSERT INTO settings_idempotency (
            principal_type,principal_name,scope_type,idempotency_key,request_payload_hash,
            result_http_status,result_response_json,result_generation,result_changed,created_at_utc)
            VALUES(?,?,'global',?,?,?,?,?,?,?)""", (
                principal.principal_type, principal.username, key, payload_hash, status,
                serialized, body["configured_generation"], int(body["changed"]), utc_now(),
            ))

    def activation(self, generation, adopted, safe_error_code=None):
        with self.transaction(write=True) as db:
            previous = self.effective(db)
            now = utc_now()
            after = generation if adopted else previous
            db.execute("""INSERT INTO settings_activation_events
                (generation_id,target,attempted_at_utc,activation_result,effective_generation_after_attempt,safe_error_code)
                VALUES(?,?,?,?,?,?)""", (generation, TARGET, now, "adopted" if adopted else "failed", after, safe_error_code))
            if adopted:
                db.execute("UPDATE settings_target_state SET effective_generation=?,updated_at_utc=? WHERE target=?", (generation, now, TARGET))
