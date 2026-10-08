import os
import stat
import uuid
from types import SimpleNamespace
import pytest
import cryptography
from app.settings_control.controller_secret import (
    SALT, aad, derive_keys, encrypt_secret, decrypt_secret, normalize_secret,
    validate_file_metadata, SecretFilesystem, OmadaClientSecretResolution,
)
from app.settings_control.models import SettingsError


def test_348_primitives_hkdf_vector_round_trip_and_redaction():
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    master = bytes(range(32))
    encryption, fingerprint = derive_keys(master)
    assert all(len(key) == 32 for key in (encryption, fingerprint)) and encryption != fingerprint
    # Fixed disposable vector, independently derived from HKDF extract/expand.
    assert encryption.hex() == "830789e98220fb3d7a5d8ab2ef13f0338664627c1a5e847d500f5cefa949fdaf"
    assert fingerprint.hex() == "441ca3b22426b5825ff78d57f0a0c270790628a8fccb80c7fd142e33c83e5c0d"
    assert encryption == HKDF(algorithm=SHA256(), length=32, salt=SALT, info=b"encryption").derive(master)
    assert tuple(int(part) for part in cryptography.__version__.split(".")[:3]) >= (3, 4, 8)
    version = str(uuid.uuid4())
    nonce, ciphertext = encrypt_secret("disposable-value", encryption, version)
    assert aad(version) == b"CaptivPortal\x00OMADA_CLIENT_SECRET\x00" + version.encode() + b"\x00v1"
    assert len(AESGCM(encryption).decrypt(nonce, ciphertext, aad(version))) == 4100
    assert decrypt_secret(nonce, ciphertext, encryption, version) == "disposable-value"
    resolution = OmadaClientSecretResolution("disposable-value", "environment", 0)
    assert "disposable-value" not in repr(resolution) + str(resolution)


@pytest.mark.parametrize("failure", ["import", "initialization"])
def test_aesgcm_failure_marks_store_unavailable_safely(tmp_path, monkeypatch, failure):
    import builtins
    from cryptography.hazmat.primitives.ciphers import aead
    from .stage4_helpers import secret_stack, secret_mutation, SENTINEL
    boot, _ = secret_stack(tmp_path)
    if failure == "import":
        original = builtins.__import__
        def blocked(name, *args, **kwargs):
            if name == "cryptography.hazmat.primitives.ciphers.aead":
                raise ImportError(SENTINEL)
            return original(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", blocked)
    else:
        def blocked(*_a, **_k):
            raise RuntimeError(SENTINEL)
        monkeypatch.setattr(aead, "AESGCM", blocked)
    metadata = boot.admin_context.secret_metadata_service
    assert metadata.available() is False
    assert metadata.metadata(0, 0, "environment")["secret_store_state"] == "unavailable"
    with pytest.raises(SettingsError) as error:
        secret_mutation(boot)
    assert error.value.code == "controller_secret_store_unavailable"
    assert SENTINEL not in str(error.value) + repr(error.value)


def test_availability_initializes_aesgcm_without_encrypting(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives.ciphers import aead
    from .stage4_helpers import secret_stack
    boot, filesystem = secret_stack(tmp_path)
    seen = []
    class InitOnly:
        def __init__(self, key):
            seen.append(key)
        def encrypt(self, *_a):
            pytest.fail("availability encryption")
        def decrypt(self, *_a):
            pytest.fail("availability decryption")
    monkeypatch.setattr(aead, "AESGCM", InitOnly)
    assert boot.admin_context.secret_metadata_service.available() is True
    assert seen == [derive_keys(filesystem.master)[0]]


@pytest.mark.parametrize("value", ["x", "x" * 4096, "é" * 2048, " \t a \n", "界"])
def test_fixed_length_and_randomized_padding(value):
    key, _ = derive_keys(bytes(32))
    version = str(uuid.uuid4())
    rows = [encrypt_secret(value, key, version) for _ in range(2)]
    assert rows[0][0] != rows[1][0] and rows[0][1] != rows[1][1]
    assert all(len(nonce) == 12 and len(ciphertext) == 4116 for nonce, ciphertext in rows)
    assert all(decrypt_secret(nonce, ciphertext, key, version) == value.strip() for nonce, ciphertext in rows)


@pytest.mark.parametrize("value", ["", "  ", "x" * 4097, "é" * 2049, "a\x00b", "a\x1fb", "a\x7fb", "a\nb", "\ud800", None, 1, False])
def test_invalid_secret_bounded_safe_failure(value):
    with pytest.raises(SettingsError, match="validation_failed"):
        normalize_secret(value)


@pytest.mark.parametrize("part", ["key", "nonce", "ciphertext", "version", "length", "frame"])
def test_authentication_and_frame_fail_closed(part):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key, _ = derive_keys(bytes(32))
    version = str(uuid.uuid4())
    nonce, ciphertext = encrypt_secret("synthetic", key, version)
    if part == "key": key = bytes(32)
    if part == "nonce": nonce = bytes(12)
    if part == "ciphertext": ciphertext = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    if part == "version": version = str(uuid.uuid4())
    if part == "length": ciphertext = ciphertext[:-1]
    if part == "frame": ciphertext = AESGCM(key).encrypt(nonce, b"\x00\x00\x00\x00" + bytes(4096), aad(version))
    with pytest.raises(SettingsError, match="controller_secret_decrypt_failed"):
        decrypt_secret(nonce, ciphertext, key, version)


@pytest.mark.parametrize("change", [{"st_uid": 8}, {"st_gid": 8}, {"st_mode": stat.S_IFREG | 0o644},
    {"st_nlink": 2}, {"st_mode": stat.S_IFLNK | 0o640}, {"st_mode": stat.S_IFIFO | 0o640}, {"st_size": 31}])
def test_key_metadata_matrix(change):
    values = dict(st_uid=0, st_gid=7, st_mode=stat.S_IFREG | 0o640, st_nlink=1, st_size=32)
    validate_file_metadata(SimpleNamespace(**values), uid=0, gid=7, mode=0o640, size=32)
    values.update(change)
    with pytest.raises(SettingsError, match="controller_secret_permissions_invalid"):
        validate_file_metadata(SimpleNamespace(**values), uid=0, gid=7, mode=0o640, size=32)


@pytest.mark.parametrize("change", [{"st_uid": 0}, {"st_gid": 8}, {"st_mode": stat.S_IFREG | 0o644},
    {"st_nlink": 2}, {"st_mode": stat.S_IFLNK | 0o600}, {"st_mode": stat.S_IFDIR | 0o600}])
def test_db_metadata_matrix(change):
    values = dict(st_uid=7, st_gid=7, st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_size=1)
    validate_file_metadata(SimpleNamespace(**values), uid=7, gid=7, mode=0o600)
    values.update(change)
    with pytest.raises(SettingsError):
        validate_file_metadata(SimpleNamespace(**values), uid=7, gid=7, mode=0o600)


@pytest.mark.parametrize("mode,gid,valid", [(0o2750, 99, True), (0o750, 7, True), (0o770, 7, False), (0o757, 7, False)])
def test_db_parent_setgid_and_deployment_group(mode, gid, valid):
    metadata = SimpleNamespace(st_uid=7, st_gid=gid, st_mode=stat.S_IFDIR | mode)
    if valid:
        validate_file_metadata(metadata, uid=7, gid=None, directory=True)
    else:
        with pytest.raises(SettingsError): validate_file_metadata(metadata, uid=7, gid=None, directory=True)


@pytest.mark.parametrize("change", [{"st_uid": 1}, {"st_gid": 9}, {"st_mode": stat.S_IFDIR | 0o770}, {"st_mode": stat.S_IFLNK | 0o750}])
def test_key_parent_security(change):
    values = dict(st_uid=0, st_gid=7, st_mode=stat.S_IFDIR | 0o750)
    values.update(change)
    with pytest.raises(SettingsError): validate_file_metadata(SimpleNamespace(**values), uid=0, gid=7, directory=True, mode=0o750)


def test_opened_object_nofollow_no_repairs(tmp_path, monkeypatch):
    if os.name != "posix": pytest.skip("Linux no-follow boundary")
    directory = tmp_path / "parent"
    directory.mkdir(mode=0o750)
    path = directory / "disposable-db"
    path.write_bytes(b"synthetic")
    path.chmod(0o600)
    fs = SecretFilesystem()
    monkeypatch.setattr(fs, "_ids", lambda: (os.getuid(), os.getgid()))
    for name in ("chmod", "chown", "chown"):
        monkeypatch.setattr(os, name, lambda *_a, **_k: pytest.fail("repair authority"))
    fd = fs._open(path)
    os.close(fd)
    link = directory / "link"
    link.symlink_to(path)
    with pytest.raises(SettingsError): fs._open(link)
    with pytest.raises(SettingsError): fs.validate_db(path)
    with pytest.raises(SettingsError): fs._open(directory / "missing", key=True)
