from dataclasses import FrozenInstanceError
import pytest
from app.admin_web.capabilities import DEFAULT_GLOBAL_CAPABILITIES, DEFAULT_GLOBAL_CAPABILITIES_TEXT, GLOBAL_CAPABILITIES, SECRET_WRITE_CAPABILITY, parse_global_capabilities
from app.admin_web.config import admin_web_config_from_settings, AdminWebConfigError
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from .conftest import enabled_settings


def test_exact_default_and_independent_secret_grant():
    assert len(DEFAULT_GLOBAL_CAPABILITIES) == 4 and SECRET_WRITE_CAPABILITY not in DEFAULT_GLOBAL_CAPABILITIES
    config = admin_web_config_from_settings(enabled_settings())
    assert config.global_capabilities == DEFAULT_GLOBAL_CAPABILITIES
    policy = AdminAccessPolicy(frozenset())
    assert not policy.authorize_global(AdminPrincipal("operator"), "admin.read.settings.controller")
    principal = AdminPrincipal("operator", global_capabilities=DEFAULT_GLOBAL_CAPABILITIES)
    assert policy.authorize_global(principal, "admin.write.settings.controller")
    assert not policy.authorize_global(principal, SECRET_WRITE_CAPABILITY)
    grants = {"admin.read.settings.controller", SECRET_WRITE_CAPABILITY}
    secret = AdminPrincipal("operator", global_capabilities=grants)
    grants.clear()
    assert policy.authorize_global(secret, SECRET_WRITE_CAPABILITY)
    assert not policy.authorize_global(secret, "admin.write.settings.controller")
    assert not policy.authorize_global(AdminPrincipal("operator", "site_operator", GLOBAL_CAPABILITIES), SECRET_WRITE_CAPABILITY)
    assert not policy.authorize_global(secret, "unknown")
    with pytest.raises(FrozenInstanceError): secret.global_capabilities = frozenset()


@pytest.mark.parametrize("value", ["", " ", DEFAULT_GLOBAL_CAPABILITIES_TEXT + ",", ",admin.read.settings.global",
    "admin.read.settings.global,admin.read.settings.global", "admin.read.settings.global, admin.write.settings.global",
    "ADMIN.READ.SETTINGS.GLOBAL", "x", "é", None, False, "x" * 129, ",".join(["x"] * 17)])
def test_malformed_grants_fail_closed(value):
    with pytest.raises(AdminWebConfigError): parse_global_capabilities(value)
    with pytest.raises(AdminWebConfigError): admin_web_config_from_settings(enabled_settings(web_admin_global_capabilities=value))


def test_explicit_grant_and_startup_snapshot():
    values = enabled_settings(web_admin_global_capabilities="admin.read.settings.controller," + SECRET_WRITE_CAPABILITY)
    config = admin_web_config_from_settings(values)
    values["web_admin_global_capabilities"] = DEFAULT_GLOBAL_CAPABILITIES_TEXT
    principal = AdminPrincipal(config.username, global_capabilities=config.global_capabilities)
    assert SECRET_WRITE_CAPABILITY in principal.global_capabilities
