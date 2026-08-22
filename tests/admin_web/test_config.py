from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings

from .conftest import SITE_ID, enabled_settings


def test_disabled_config_accepts_empty_credentials_and_sites():
    config = admin_web_config_from_settings({"web_admin_enabled": "false"})
    assert config.enabled is False
    assert config.username == ""
    assert config.password_hash == ""
    assert config.allowed_site_ids == frozenset()


@pytest.mark.parametrize(
    "key,value",
    [
        ("web_admin_username", ""),
        ("web_admin_username", " opérateur"),
        ("web_admin_allowed_site_ids", SITE_ID.upper()),
        ("web_admin_allowed_site_ids", " " + SITE_ID),
        ("web_admin_default_site_id", "f" * 24),
        ("web_admin_allowed_networks", "127.0.0.1"),
        ("web_admin_allowed_networks", "127.0.0.1/32,127.0.0.1/32"),
        ("web_admin_max_sessions", "0"),
        ("web_admin_session_idle_seconds", "59"),
        ("web_admin_session_absolute_seconds", "100"),
    ],
)
def test_enabled_config_rejects_invalid_security_values(key, value):
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings(enabled_settings(**{key: value}))


def test_invalid_hash_is_rejected_without_echo():
    secret = "plaintext-secret"
    with pytest.raises(AdminWebConfigError) as caught:
        admin_web_config_from_settings(
            enabled_settings(web_admin_password_hash=secret)
        )
    assert secret not in str(caught.value)


@pytest.mark.parametrize(
    "value",
    [
        "scrypt$foo$bar",
        "pbkdf2$foo$bar",
        "unknown:1$abcdefgh$" + "a" * 64,
        "scrypt:32768:8$abcdefgh$" + "a" * 128,
        "scrypt:32768:8:1:1$abcdefgh$" + "a" * 128,
        "scrypt:abc:8:1$abcdefgh$" + "a" * 128,
        "scrypt:01024:8:1$abcdefgh$" + "a" * 128,
        "scrypt:131072:8:1$abcdefgh$" + "a" * 128,
        "scrypt:32768:16:1$abcdefgh$" + "a" * 128,
        "scrypt:32768:8:4$abcdefgh$" + "a" * 128,
        "pbkdf2:sha1:600000$abcdefgh$" + "a" * 40,
        "pbkdf2:sha256:abc$abcdefgh$" + "a" * 64,
        "pbkdf2:sha256:99999$abcdefgh$" + "a" * 64,
        "pbkdf2:sha256:2000001$abcdefgh$" + "a" * 64,
        "pbkdf2:sha256:600000$$" + "a" * 64,
        "pbkdf2:sha256:600000$bad salt$" + "a" * 64,
        "pbkdf2:sha256:600000$abcdefgh$",
        "pbkdf2:sha256:600000$abcdefgh$" + "g" * 64,
        "pbkdf2:sha256:600000$abcdefgh$" + "A" * 64,
    ],
)
def test_malformed_or_unbounded_password_hash_is_rejected_without_echo(value):
    with pytest.raises(AdminWebConfigError) as caught:
        admin_web_config_from_settings(
            enabled_settings(web_admin_password_hash=value)
        )
    assert value not in str(caught.value)
    assert value not in repr(caught.value)


@pytest.mark.parametrize(
    "method",
    ["scrypt", "pbkdf2:sha256", "pbkdf2:sha384", "pbkdf2:sha512"],
)
def test_current_werkzeug_generated_password_hash_is_accepted(method):
    value = generate_password_hash("example password", method=method)
    config = admin_web_config_from_settings(
        enabled_settings(web_admin_password_hash=value)
    )
    assert config.password_hash == value


def test_config_repr_redacts_username_and_hash():
    config = admin_web_config_from_settings(enabled_settings())
    rendered = repr(config)
    assert config.username not in rendered
    assert config.password_hash not in rendered
    assert rendered.count("[REDACTED]") == 2
