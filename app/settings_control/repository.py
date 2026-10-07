"""SQLite-only SettingsStore: bounded connections, immutable history, one writer."""
import json
import sqlite3
from contextlib import contextmanager
from .definitions import SettingsDefinitionRegistry
from .models import SettingsError, TARGET, utc_now

SETTINGS_SCHEMA_VERSION = 2
SETTINGS_SQLITE_BUSY_TIMEOUT_MS = 1000
_V1_DDL = (
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
_AUDIT_TYPE_CHECK = """CHECK(
    (setting_domain='general' AND value_type='integer'
     AND typeof(previous_configured_value)='integer' AND typeof(new_configured_value)='integer'
     AND (previous_persisted_override IS NULL OR typeof(previous_persisted_override)='integer')
     AND (new_persisted_override IS NULL OR typeof(new_persisted_override)='integer'))
    OR (setting_domain='controller' AND value_type='string'
     AND typeof(previous_configured_value)='text' AND typeof(new_configured_value)='text'
     AND (previous_persisted_override IS NULL OR typeof(previous_persisted_override)='text')
     AND (new_persisted_override IS NULL OR typeof(new_persisted_override)='text')))"""
_DDL = tuple(
    sql.replace("value_type TEXT NOT NULL CHECK(value_type='integer'),\n        integer_value INTEGER NOT NULL",
                "value_type TEXT NOT NULL CHECK(value_type IN ('integer','string')),\n        integer_value INTEGER, string_value TEXT,\n        CHECK((value_type='integer' AND typeof(integer_value)='integer' AND string_value IS NULL)\n        OR (value_type='string' AND integer_value IS NULL AND typeof(string_value)='text'))")
    .replace("previous_persisted_override INTEGER, new_persisted_override INTEGER,\n        previous_configured_value INTEGER NOT NULL, new_configured_value INTEGER NOT NULL,",
             "setting_domain TEXT NOT NULL CHECK(setting_domain IN ('general','controller')),\n        value_type TEXT NOT NULL CHECK(value_type IN ('integer','string')),\n        previous_persisted_override, new_persisted_override,\n        previous_configured_value NOT NULL, new_configured_value NOT NULL,")
    .replace("UNIQUE(generation_id,setting_key))", _AUDIT_TYPE_CHECK + ", UNIQUE(generation_id,setting_key))")
    .replace("scope_type TEXT NOT NULL CHECK(scope_type='global'), idempotency_key TEXT NOT NULL,",
             "scope_type TEXT NOT NULL CHECK(scope_type='global'),\n        mutation_domain TEXT NOT NULL CHECK(mutation_domain IN ('general','controller')), idempotency_key TEXT NOT NULL,")
    .replace("UNIQUE(principal_type,principal_name,scope_type,idempotency_key)",
             "UNIQUE(principal_type,principal_name,scope_type,mutation_domain,idempotency_key)")
    for sql in _V1_DDL
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
                db.execute("PRAGMA user_version=2")
                db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global',?,'system','settings_bootstrap',NULL)", (utc_now(),))
                db.execute("INSERT INTO settings_target_state VALUES(?,NULL,NULL)", (TARGET,))
            elif version == 1:
                self._validate_schema(db, _V1_DDL)
                self._validate_history(db, legacy=True)
                self._migrate_v1(db)
            elif version != SETTINGS_SCHEMA_VERSION:
                raise SettingsError("settings_store_unavailable")
            self._validate_schema(db, _DDL)
            self._validate_history(db)

    @staticmethod
    def _validate_schema(db, ddl):
        expected = {statement.split()[2]: statement for statement in (*ddl, *_TRIGGERS)}
        actual = {row[0]: row[1] for row in db.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','trigger') AND name NOT LIKE 'sqlite_%'")}
        normalize = lambda value: " ".join(value.split())
        if actual.keys() != expected.keys() or any(normalize(actual[key]) != normalize(sql) for key, sql in expected.items()):
            raise SettingsError("settings_store_unavailable")

    @staticmethod
    def _migrate_v1(db):
        # Only leaf tables are replaced. Parent history/targets/events are untouched.
        for table in ("settings_overrides", "settings_mutation_audit", "settings_idempotency"):
            for action in ("update", "delete"):
                db.execute(f"DROP TRIGGER {table}_immutable_{action}")
            db.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")
            db.execute(next(sql for sql in _DDL if sql.startswith("CREATE TABLE " + table + " ")))
            columns = [row[1] for row in db.execute(f"PRAGMA table_info({table}_v1)")]
            additions = {"settings_overrides": {"string_value": "NULL"},
                         "settings_mutation_audit": {"setting_domain": "'general'", "value_type": "'integer'"},
                         "settings_idempotency": {"mutation_domain": "'general'"}}[table]
            target = columns + list(additions)
            db.execute(f"INSERT INTO {table} ({','.join(target)}) SELECT {','.join(columns + list(additions.values()))} FROM {table}_v1")
            db.execute(f"DROP TABLE {table}_v1")
            for statement in _TRIGGERS:
                if statement.startswith("CREATE TRIGGER " + table + "_"):
                    db.execute(statement)
        db.execute("PRAGMA user_version=2")

    def _validate_history(self, db, legacy=False):
        if db.execute("PRAGMA quick_check").fetchall()[0][0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise SettingsError("settings_store_unavailable")
        root = db.execute("SELECT * FROM settings_generations WHERE generation_id=0").fetchone()
        if root is None or root[1] is not None or root[2] != "global" or tuple(root)[4:] != ("system", "settings_bootstrap", None):
            raise SettingsError("settings_store_unavailable")
        if db.execute("SELECT 1 FROM settings_overrides WHERE generation_id=0").fetchone():
            raise SettingsError("settings_store_unavailable")
        if db.execute("SELECT COUNT(*) FROM settings_target_state WHERE target=?", (TARGET,)).fetchone()[0] != 1:
            raise SettingsError("settings_store_unavailable")
        for row in db.execute("SELECT setting_key,value_type,integer_value" + ("" if legacy else ",string_value") + " FROM settings_overrides"):
            definition = self.registry.get(row[0])
            if definition is None or row[1] != definition.value_type:
                raise SettingsError("settings_store_unavailable")
            if row[1] == "integer":
                if type(row[2]) is not int or not definition.min_value <= row[2] <= definition.max_value:
                    raise SettingsError("settings_store_unavailable")
            else:
                from app.controllers.omada_config import normalize_controller_setting
                from app.exceptions import ConfigurationError
                try:
                    if legacy or normalize_controller_setting(row[0], row[3]) != row[3]:
                        raise SettingsError("settings_store_unavailable")
                except ConfigurationError as exc:
                    raise SettingsError("settings_store_unavailable") from exc

    @staticmethod
    def head(db):
        # Reading the head under a transaction is not generation allocation.
        return db.execute("SELECT generation_id FROM settings_generations ORDER BY generation_id DESC LIMIT 1").fetchone()[0]

    @staticmethod
    def overrides(db, generation):
        return {row[0]: row[2] if row[1] == "integer" else row[3] for row in db.execute("SELECT setting_key,value_type,integer_value,string_value FROM settings_overrides WHERE generation_id=?", (generation,))}

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

    def create_generation(self, db, *, parent, principal, request_id, created_at, overrides):
        from app.controllers.omada_config import normalize_controller_setting
        from app.exceptions import ConfigurationError
        for key, value in overrides.items():
            definition = self.registry.get(key)
            if definition is None:
                raise SettingsError("settings_store_unavailable")
            if definition.value_type == "integer":
                if type(value) is not int or not definition.min_value <= value <= definition.max_value:
                    raise SettingsError("settings_store_unavailable")
            else:
                try:
                    if normalize_controller_setting(key, value) != value:
                        raise SettingsError("settings_store_unavailable")
                except ConfigurationError as exc:
                    raise SettingsError("settings_store_unavailable") from exc
        generation = db.execute("""INSERT INTO settings_generations
            (parent_generation_id,scope_type,created_at_utc,created_by_principal_type,created_by_principal_name,request_id)
            VALUES(?,'global',?,?,?,?)""", (parent, created_at, principal.principal_type, principal.username, request_id)).lastrowid
        db.executemany("INSERT INTO settings_overrides VALUES(?,?,?,?,?)", [
            (generation, key, "integer" if type(value) is int else "string",
             value if type(value) is int else None, value if type(value) is str else None)
            for key, value in sorted(overrides.items())])
        return generation

    @staticmethod
    def append_mutation_audit(db, *, generation, parent, principal, source_ip, request_id,
                              idempotency_key, timestamp, key, operation, previous_override,
                              new_override, previous_value, new_value, apply_requirement, activation_target,
                              domain="general", value_type="integer"):
        db.execute("""INSERT INTO settings_mutation_audit (
            generation_id,parent_generation_id,principal_type,principal_name,source_ip,request_id,
            idempotency_key,timestamp_utc,scope_type,scope_id,setting_key,operation,
            previous_persisted_override,new_persisted_override,previous_configured_value,new_configured_value,
            apply_requirement,activation_target,setting_domain,value_type) VALUES(?,?,?,?,?,?,?,?,'global',NULL,?,?,?,?,?,?,?,?,?,?)""", (
                generation, parent, principal.principal_type, principal.username, source_ip, request_id,
                idempotency_key, timestamp, key, operation, previous_override, new_override,
                previous_value, new_value, apply_requirement, activation_target, domain, value_type,
            ))

    @staticmethod
    def idempotency(db, principal, key, domain="general"):
        return db.execute("SELECT * FROM settings_idempotency WHERE principal_type=? AND principal_name=? AND scope_type='global' AND mutation_domain=? AND idempotency_key=?", (principal.principal_type, principal.username, domain, key)).fetchone()

    def lookup_idempotency(self, principal, key, domain="general"):
        # Ordinary read transaction: successful replay never needs writer ownership.
        with self.transaction() as db:
            row = self.idempotency(db, principal, key, domain)
            return dict(row) if row else None

    @staticmethod
    def save_idempotency(db, principal, key, payload_hash, status, body, domain="general"):
        serialized = canonical_json(body)
        if len(serialized.encode("utf-8")) > 65536:
            raise SettingsError("internal_error", 500)
        db.execute("""INSERT INTO settings_idempotency (
            principal_type,principal_name,scope_type,idempotency_key,request_payload_hash,
            result_http_status,result_response_json,result_generation,result_changed,created_at_utc,mutation_domain)
            VALUES(?,?,'global',?,?,?,?,?,?,?,?)""", (
                principal.principal_type, principal.username, key, payload_hash, status,
                serialized, body["configured_generation"], int(body["changed"]), utc_now(), domain,
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
