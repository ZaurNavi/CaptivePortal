import pytest
from app.settings_control.secret_recovery import clear_managed_secret
from app.settings_control.controller_secret import binding
from app.settings_control.models import SettingsError
from .stage4_helpers import secret_stack, secret_mutation


def test_recovery_without_key_or_decrypt_retains_effective(tmp_path):
    boot, filesystem = secret_stack(tmp_path)
    secret_mutation(boot)
    repository = boot.admin_context.read_service.repository
    repository.activation(1, True)
    filesystem.key_valid = False
    reads = filesystem.key_reads
    generation, changed = clear_managed_secret(repository, 1, filesystem=filesystem, operator=lambda: "local-test-operator", deployment_source="repository_default")
    assert (generation, changed) == (2, True) and filesystem.key_reads == reads
    with repository.transaction() as db:
        assert binding(db, 2) is None
        assert repository.effective(db) == 1
        assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 1
        audit = db.execute("SELECT * FROM settings_secret_mutation_audit ORDER BY audit_id DESC LIMIT 1").fetchone()
        assert audit["operation"] == "clear_secret_override_recovery"
        assert audit["principal_type"] == "local_operator" and audit["principal_name"] == "local-test-operator"
        assert audit["source_ip"] == "local" and audit["idempotency_key"] is None
    assert clear_managed_secret(repository, 2, filesystem=filesystem) == (2, False)
    assert filesystem.key_reads == reads
    with pytest.raises(SettingsError, match="stale_generation"):
        clear_managed_secret(repository, 1, filesystem=filesystem)


def test_recovery_refuses_bad_db_security_without_writes(tmp_path):
    boot, filesystem = secret_stack(tmp_path)
    secret_mutation(boot)
    filesystem.db_valid = False
    repository = boot.admin_context.read_service.repository
    with pytest.raises(SettingsError, match="controller_secret_permissions_invalid"):
        clear_managed_secret(repository, 1, filesystem=filesystem)
    assert repository.configured()[0] == 1


def test_default_recovery_identity_ignores_spoofed_environment(tmp_path, monkeypatch, capsys):
    import os
    if os.name != "posix":
        pytest.skip("Linux effective UID identity")
    import pwd
    from app.settings_control import secret_recovery
    from .stage4_helpers import SENTINEL
    boot, filesystem = secret_stack(tmp_path)
    secret_mutation(boot)
    for name in ("USER", "LOGNAME", "LNAME", "USERNAME"):
        monkeypatch.setenv(name, "spoofed-disposable-operator")
    expected = pwd.getpwuid(os.geteuid()).pw_name
    assert secret_recovery.effective_operator_name() == expected
    repository = boot.admin_context.read_service.repository
    monkeypatch.setattr(secret_recovery, "SecretFilesystem", lambda: filesystem)
    monkeypatch.setattr(secret_recovery.SettingsRepository, "open_existing_v3", lambda _path: repository)
    reads = filesystem.key_reads
    assert secret_recovery.main(["clear-omada-client-secret", "--expected-generation", "1"]) == 0
    with repository.transaction() as db:
        audit = db.execute("SELECT * FROM settings_secret_mutation_audit ORDER BY audit_id DESC LIMIT 1").fetchone()
        assert audit["principal_name"] == expected
        assert audit["principal_type"] == "local_operator"
    assert filesystem.key_reads == reads
    output = capsys.readouterr()
    assert output.out == "configured_generation=2 changed=true\n" and output.err == ""
    assert SENTINEL not in output.out + output.err
