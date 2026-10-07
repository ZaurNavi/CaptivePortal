"""One write-only Controller secret, in the existing Settings transaction domain.

Secret-bearing values are startup/mutation-local, never Admin projections. Paths
and Linux metadata policy are code-owned; the injectable filesystem boundary is
for disposable tests, not deployment configuration.
"""
import hmac
import json
import os
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .models import SettingsError, SettingsMutationResult, TARGET, utc_now
from .repository import canonical_json

SECRET_KEY = "OMADA_CLIENT_SECRET"
MASTER_KEY_PATH = "/etc/captiveportal/omada-controller-secret-master.key"
SETTINGS_DB_PATH = "/opt/CaptivePortal/data/settings.sqlite3"
SECRET_API_VERSION = "admin.settings.controller.secret.mutation.v1"
SALT = b"CaptivPortal.Stage4.ControllerSecret.v1"
FINGERPRINT_KIND = "hmac_sha256_controller_secret_v1"


def normalize_secret(value):
    try:
        if type(value) is not str:
            raise ValueError()
        value = value.strip()
        size = len(value.encode("utf-8"))
        if not 1 <= size <= 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise SettingsError("validation_failed", 422, ({"field": "secret", "reason": "invalid_secret"},)) from None


def valid_uuid4(value):
    try:
        parsed = uuid.UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


def derive_keys(master):
    if type(master) is not bytes or len(master) != 32:
        raise SettingsError("controller_secret_key_unavailable")
    try:
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        return tuple(HKDF(algorithm=SHA256(), length=32, salt=SALT, info=info).derive(master)
                     for info in (b"encryption", b"idempotency"))
    except Exception:
        raise SettingsError("controller_secret_key_unavailable") from None


def aad(version):
    if not valid_uuid4(version):
        raise SettingsError("controller_secret_integrity_failed")
    return b"CaptivPortal\x00OMADA_CLIENT_SECRET\x00" + version.encode("ascii") + b"\x00v1"


def encrypt_secret(value, encryption_key, version):
    value = normalize_secret(value).encode("utf-8")
    frame = len(value).to_bytes(4, "big") + value + os.urandom(4096 - len(value))
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        return nonce, AESGCM(encryption_key).encrypt(nonce, frame, aad(version))
    except Exception:
        raise SettingsError("controller_secret_integrity_failed") from None


def decrypt_secret(nonce, ciphertext, encryption_key, version):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if type(nonce) is not bytes or len(nonce) != 12 or type(ciphertext) is not bytes or len(ciphertext) != 4116:
            raise ValueError()
        frame = AESGCM(encryption_key).decrypt(nonce, ciphertext, aad(version))
        size = int.from_bytes(frame[:4], "big")
        if len(frame) != 4100 or not 1 <= size <= 4096:
            raise ValueError()
        value = frame[4:4 + size].decode("utf-8")
        if normalize_secret(value) != value:
            raise ValueError()
        return value
    except Exception:
        raise SettingsError("controller_secret_decrypt_failed") from None


def validate_file_metadata(metadata, *, uid, gid, mode=None, directory=False, size=None):
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected_type(metadata.st_mode) or metadata.st_uid != uid
            or (gid is not None and metadata.st_gid != gid)
            or (mode is not None and stat.S_IMODE(metadata.st_mode) != mode)
            or (mode is None and metadata.st_mode & 0o022)
            or (not directory and metadata.st_nlink != 1)
            or (size is not None and metadata.st_size != size)):
        raise SettingsError("controller_secret_permissions_invalid")


class SecretFilesystem:
    """No-follow opened-object checks. No permission/ownership repair authority."""

    @staticmethod
    def _ids():
        import grp
        import pwd
        return pwd.getpwnam("admin").pw_uid, grp.getgrnam("admin").gr_gid

    def _open(self, path, *, key=False):
        try:
            admin_uid, admin_gid = self._ids()
            parent = os.open(str(Path(path).parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                validate_file_metadata(os.fstat(parent), uid=0 if key else admin_uid,
                                       gid=admin_gid if key else None, mode=0o750 if key else None, directory=True)
                fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            finally:
                os.close(parent)
            try:
                validate_file_metadata(os.fstat(fd), uid=0 if key else admin_uid, gid=admin_gid,
                                       mode=0o640 if key else 0o600, size=32 if key else None)
            except Exception:
                os.close(fd)
                raise
            return fd
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("controller_secret_key_unavailable" if key else "controller_secret_permissions_invalid") from None

    def validate_db(self, path):
        if str(path) != SETTINGS_DB_PATH:
            raise SettingsError("controller_secret_permissions_invalid")
        fd = self._open(path)
        try:
            opened = os.fstat(fd)
            current = os.stat(path, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise SettingsError("controller_secret_permissions_invalid")
        finally:
            os.close(fd)

    def load_master_key(self):
        fd = self._open(MASTER_KEY_PATH, key=True)
        try:
            value = os.read(fd, 33)
            if len(value) != 32:
                raise SettingsError("controller_secret_key_unavailable")
            return value
        finally:
            os.close(fd)


def binding(db, generation):
    row = db.execute("SELECT secret_version_id FROM settings_secret_bindings WHERE generation_id=?", (generation,)).fetchone()
    return row[0] if row else None


def gc_secret_versions(db):
    db.execute("""DELETE FROM controller_secret_versions WHERE secret_version_id NOT IN (
        SELECT secret_version_id FROM settings_secret_bindings WHERE generation_id IN (
            (SELECT MAX(generation_id) FROM settings_generations),
            (SELECT effective_generation FROM settings_target_state WHERE target=?)))""", (TARGET,))


def validate_secret_history(db):
    if db.execute("SELECT 1 FROM settings_secret_bindings WHERE generation_id=0").fetchone():
        raise SettingsError("controller_secret_integrity_failed")
    for row in db.execute("SELECT secret_version_id FROM settings_secret_bindings UNION SELECT secret_version_id FROM controller_secret_versions"):
        if not valid_uuid4(row[0]):
            raise SettingsError("controller_secret_integrity_failed")
    head = db.execute("SELECT MAX(generation_id) FROM settings_generations").fetchone()[0]
    effective = db.execute("SELECT effective_generation FROM settings_target_state WHERE target=?", (TARGET,)).fetchone()[0]
    for generation in (head, effective):
        version = binding(db, generation)
        if version and not db.execute("SELECT 1 FROM controller_secret_versions WHERE secret_version_id=?", (version,)).fetchone():
            raise SettingsError("controller_secret_reference_missing")


@dataclass(frozen=True, slots=True, repr=False)
class OmadaClientSecretResolution:
    value: str = field(repr=False)
    source: str
    configured_generation: int | None
    secret_version_id: str | None = field(default=None, repr=False)

    def __repr__(self):
        return "OmadaClientSecretResolution([REDACTED])"

    __str__ = __repr__


class ControllerSecretRepository:
    def __init__(self, repository, filesystem=None, deployment_secret=None, deployment_source="repository_default"):
        self.repository = repository
        self.filesystem = filesystem or SecretFilesystem()
        self._deployment = OmadaClientSecretResolution(deployment_secret, deployment_source, None)

    def check_db(self):
        self.filesystem.validate_db(self.repository.db_path)
        with self.repository.transaction() as db:
            from .repository import _DDL
            self.repository._validate_schema(db, _DDL)
            self.repository._validate_history(db)
            validate_secret_history(db)

    def keys(self):
        self.check_db()
        return derive_keys(self.filesystem.load_master_key())

    def available(self):
        try:
            self.keys()
            return True
        except SettingsError:
            return False

    @staticmethod
    def value(db, version, encryption_key):
        row = db.execute("SELECT nonce,ciphertext FROM controller_secret_versions WHERE secret_version_id=?", (version,)).fetchone()
        if row is None:
            raise SettingsError("controller_secret_reference_missing")
        return decrypt_secret(row[0], row[1], encryption_key, version)

    def resolve(self, generation, base_settings, environment_names):
        with self.repository.transaction() as db:
            version = binding(db, generation)
        if version:
            encryption_key, _ = self.keys()
            with self.repository.transaction() as db:
                value = self.value(db, version, encryption_key)
            return OmadaClientSecretResolution(value, "managed_secret_override", generation, version)
        try:
            value = normalize_secret(self._deployment.value)
        except SettingsError:
            raise SettingsError("controller_secret_configuration_invalid") from None
        return OmadaClientSecretResolution(value, self._deployment.source, generation)

    def metadata(self, generation, effective_generation, deployment_source):
        # No decrypt/no value on the public boundary; availability validates key.
        with self.repository.transaction() as db:
            configured = binding(db, generation)
            effective = binding(db, effective_generation)
            validate_secret_history(db)
        try:
            normalize_secret(self._deployment.value)
            deployment_presence = "configured"
        except SettingsError:
            deployment_presence = "not_configured"
        return {"configured_presence": "configured" if configured else deployment_presence, "configured_source": "managed_secret_override" if configured else deployment_source,
                "persisted_secret_override_present": configured is not None,
                "pending_replacement": configured != effective,
                "secret_store_state": "available" if self.available() else "unavailable"}

    @staticmethod
    def audit(db, *, generation, parent, principal, source_ip, request_id, key, operation, previous, new, deployment_source):
        db.execute("""INSERT INTO settings_secret_mutation_audit (
            generation_id,parent_generation_id,principal_type,principal_name,source_ip,request_id,idempotency_key,
            timestamp_utc,scope_type,scope_id,setting_key,operation,previous_override_present,new_override_present,
            previous_source,new_source,apply_requirement,activation_target)
            VALUES(?,?,?,?,?,?,?,?,'global',NULL,'OMADA_CLIENT_SECRET',?,?,?,?,?,'main_service_restart','captive-portal.service')""",
            (generation, parent, principal.principal_type, principal.username, source_ip, request_id, key, utc_now(),
             operation, int(previous is not None), int(new is not None),
             "managed_secret_override" if previous else deployment_source,
             "managed_secret_override" if new else deployment_source))


def parse_secret_mutation(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    def constant(_value):
        raise ValueError()

    try:
        item = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        if type(item) is not dict:
            raise ValueError()
        if item.get("operation") == "replace_secret" and set(item) == {"operation", "secret"} and type(item["secret"]) is str:
            return item["operation"], normalize_secret(item["secret"])
        if item.get("operation") == "clear_secret_override" and set(item) == {"operation"}:
            return item["operation"], None
        raise ValueError()
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise SettingsError("invalid_request", 400) from None


class ControllerSecretMutationService:
    def __init__(self, secrets, read_service):
        self.secrets, self.read_service = secrets, read_service

    @staticmethod
    def replay(existing, fingerprint):
        if existing["request_fingerprint_kind"] != FINGERPRINT_KIND or not hmac.compare_digest(existing["request_fingerprint"], fingerprint):
            raise SettingsError("idempotency_conflict", 409)
        return SettingsMutationResult(200, json.loads(existing["result_response_json"]))

    def mutate(self, raw_body, *, principal, source_ip, request_id, idempotency_key, expected_generation):
        operation, value = parse_secret_mutation(raw_body)
        if not valid_uuid4(idempotency_key):
            raise SettingsError("invalid_request", 400)
        try:
            encryption_key, hmac_key = self.secrets.keys()
        except SettingsError as error:
            if error.code == "settings_store_unavailable":
                raise
            raise SettingsError("controller_secret_store_unavailable") from None
        canonical = {"api_version": SECRET_API_VERSION, "principal_type": principal.principal_type,
                     "principal_name": principal.username, "idempotency_key": idempotency_key, "operation": operation}
        if value is not None:
            canonical["secret"] = value
        fingerprint = hmac.digest(hmac_key, canonical_json(canonical).encode("utf-8"), "sha256").hex()
        repository = self.secrets.repository
        existing = repository.lookup_idempotency(principal, idempotency_key, "controller_secret")
        if existing:
            return self.replay(existing, fingerprint)
        with repository.transaction(write=True) as db:
            existing = repository.idempotency(db, principal, idempotency_key, "controller_secret")
            if existing:
                return self.replay(existing, fingerprint)
            parent = repository.head(db)
            if parent != expected_generation:
                raise SettingsError("stale_generation", 412)
            previous = binding(db, parent)
            changed = previous is not None if value is None else (
                previous is None or not hmac.compare_digest(value.encode("utf-8"), self.secrets.value(db, previous, encryption_key).encode("utf-8")))
            generation, new_version = parent, previous
            source = "environment" if SECRET_KEY in self.read_service.environment_names else "repository_default"
            if changed:
                if value is None:
                    from app.controllers.omada_config import build_omada_runtime_config
                    from app.exceptions import ConfigurationError
                    from .resolver import resolve_settings
                    candidate = resolve_settings(self.read_service.base_settings, self.read_service.environment_names,
                                                 repository.overrides(db, parent), parent)
                    try:
                        deployment_value = normalize_secret(self.secrets._deployment.value)
                        deployment_resolution = OmadaClientSecretResolution(
                            deployment_value, self.secrets._deployment.source, parent)
                        build_omada_runtime_config(candidate.values, secret_resolution=deployment_resolution)
                    except (SettingsError, ConfigurationError):
                        raise SettingsError("validation_failed", 422, ({"field": "secret", "reason": "deployment_configuration_invalid"},)) from None
                    new_version = None
                else:
                    new_version = str(uuid.uuid4())
                    nonce, ciphertext = encrypt_secret(value, encryption_key, new_version)
                    db.execute("INSERT INTO controller_secret_versions VALUES(?,'OMADA_CLIENT_SECRET',1,?,?,?)", (new_version, nonce, ciphertext, utc_now()))
                generation = repository.create_generation(db, parent=parent, principal=principal, request_id=request_id,
                    created_at=utc_now(), overrides=repository.overrides(db, parent), carry_secret=False)
                if new_version:
                    db.execute("INSERT INTO settings_secret_bindings VALUES(?,'OMADA_CLIENT_SECRET',?)", (generation, new_version))
                self.secrets.audit(db, generation=generation, parent=parent, principal=principal, source_ip=source_ip,
                    request_id=request_id, key=idempotency_key, operation=operation, previous=previous, new=new_version, deployment_source=source)
                gc_secret_versions(db)
            effective = repository.effective(db)
            latest = repository.latest_activation_result(db, generation)
            activation = "pending_main_restart" if changed else (
                "runtime_unavailable" if not self.read_service._adopted else "active" if generation == effective
                else "activation_failed" if latest == "failed" else "pending_main_restart")
            body = {"api_version": SECRET_API_VERSION, "request_id": request_id, "scope": {"type": "global"},
                    "resource": {"type": "omada_controller", "scope": "installation"}, "operation": operation,
                    "changed": changed, "configured_generation": generation, "effective_generation": effective,
                    "activation_state": activation, "restart_required": generation != effective}
            repository.save_idempotency(db, principal, idempotency_key, fingerprint, 201 if changed else 200, body,
                                        "controller_secret", FINGERPRINT_KIND)
            return SettingsMutationResult(201 if changed else 200, body)
