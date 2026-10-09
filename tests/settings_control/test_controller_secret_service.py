from . import adopt
import hmac
import json
import uuid
from contextlib import contextmanager
import pytest
from app.settings_control.controller_secret import FINGERPRINT_KIND, binding, parse_secret_mutation
from app.settings_control.models import SettingsError
from .stage4_helpers import secret_stack, secret_mutation, SENTINEL


def test_replace_ownership_noop_replay_hmac_and_redaction(tmp_path, monkeypatch):
    boot, _ = secret_stack(tmp_path, client_secret=SENTINEL)
    adopt(boot)
    key = str(uuid.uuid4())
    first = secret_mutation(boot, key=key)
    assert first.status == 201 and first.body["changed"] and first.body["configured_generation"] == 1
    assert SENTINEL not in repr(first)
    noop = secret_mutation(boot, generation=1, value=" \t" + SENTINEL + "\n ")
    assert noop.status == 200 and not noop.body["changed"]
    other = secret_mutation(boot, generation=1)
    repository = boot.admin_context.read_service.repository
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM settings_secret_mutation_audit").fetchone()[0] == 1
        rows = db.execute("SELECT request_fingerprint_kind,request_fingerprint,result_response_json FROM settings_idempotency").fetchall()
        assert all(row[0] == FINGERPRINT_KIND and SENTINEL not in row[2] for row in rows)
        assert len({row[1] for row in rows}) == 3
    secrets = boot.admin_context.secret_mutation_service.secrets
    monkeypatch.setattr(secrets, "value", lambda *_a: pytest.fail("replay decrypt"))
    transaction = repository.transaction
    @contextmanager
    def readonly(*, write=False):
        assert not write
        with transaction() as db: yield db
    monkeypatch.setattr(repository, "transaction", readonly)
    replay = secret_mutation(boot, key=key, generation=0, value=" " + SENTINEL + " ")
    assert replay.status == 200 and replay.body == first.body
    with pytest.raises(SettingsError, match="idempotency_conflict"):
        secret_mutation(boot, key=key, value="different")


def test_fingerprint_exact_keyed_identity_not_plain_sha(tmp_path):
    from app.settings_control.repository import canonical_json
    from app.settings_control.controller_secret import SECRET_API_VERSION, derive_keys
    boot, filesystem = secret_stack(tmp_path)
    key = str(uuid.uuid4())
    secret_mutation(boot, key=key)
    payload = {"api_version": SECRET_API_VERSION, "principal_type": "platform_operator", "principal_name": "operator",
               "idempotency_key": key, "operation": "replace_secret", "secret": SENTINEL}
    import hashlib
    encoded = canonical_json(payload).encode()
    expected = hmac.digest(derive_keys(filesystem.master)[1], encoded, "sha256").hex()
    with boot.admin_context.read_service.repository.transaction() as db:
        fingerprint = db.execute("SELECT request_fingerprint FROM settings_idempotency").fetchone()[0]
        assert fingerprint == expected and fingerprint != hashlib.sha256(encoded).hexdigest()


def test_clear_ownership_noop_and_effective_retention(tmp_path):
    boot, _ = secret_stack(tmp_path)
    adopt(boot)
    noop = secret_mutation(boot, operation="clear_secret_override")
    assert not noop.body["changed"] and noop.status == 200
    secret_mutation(boot)
    repository = boot.admin_context.read_service.repository
    repository.activation(1, True)
    cleared = secret_mutation(boot, generation=1, operation="clear_secret_override")
    assert cleared.status == 201 and cleared.body["configured_generation"] == 2
    with repository.transaction() as db:
        assert binding(db, 2) is None and binding(db, 1) is not None
        assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 1
    repository.activation(2, True)
    with repository.transaction() as db: assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 0


def test_invalid_fallback_does_not_clear_managed_ownership(tmp_path):
    boot, _ = secret_stack(tmp_path)
    secret_mutation(boot)
    from dataclasses import replace
    service = boot.admin_context.secret_mutation_service.secrets
    service._deployment = replace(service._deployment, value="")
    with pytest.raises(SettingsError, match="validation_failed") as error:
        secret_mutation(boot, generation=1, operation="clear_secret_override")
    assert error.value.status == 422
    assert boot.admin_context.read_service.repository.configured()[0] == 1


@pytest.mark.parametrize("raw", ["[]", "null", "{", '{"operation":"replace_secret","secret":NaN}',
    '{"operation":"replace_secret","secret":Infinity}', '{"operation":"replace_secret","secret":-Infinity}',
    '{"operation":"replace_secret","secret":"a","secret":"b"}', '{"operation":"replace_secret","secret":1}',
    '{"operation":"clear_secret_override","secret":"x"}', '{"operation":"replace_secret","secret":"x","extra":1}',
    '{"operation":"read_secret"}', '{"operation":"replace_secret"}'])
def test_strict_secret_json(raw):
    with pytest.raises(SettingsError, match="invalid_request"): parse_secret_mutation(raw)


@pytest.mark.parametrize("boundary", ["db", "key"])
def test_availability_separate_from_general_mutation(tmp_path, boundary):
    from . import mutation
    boot, filesystem = secret_stack(tmp_path)
    if boundary == "db": filesystem.db_valid = False
    else: filesystem.key_valid = False
    assert not boot.admin_context.secret_metadata_service.available()
    with pytest.raises(SettingsError, match="controller_secret_store_unavailable"): secret_mutation(boot)
    assert mutation(boot).status == 201
