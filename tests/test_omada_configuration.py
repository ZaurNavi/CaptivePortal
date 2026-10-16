import importlib
import ssl
from unittest.mock import patch

import pytest

import app.config as config_module
import app.settings as settings_module
from app.controllers.omada import OmadaProvider
from app.controllers.omada_config import build_omada_runtime_config
from app.exceptions import ConfigurationError


OMADA_ENVIRONMENT_NAMES = (
    "OMADA_URL",
    "OMADA_ID",
    "OMADA_CLIENT_ID",
    "OMADA_CLIENT_SECRET",
)
TEST_SECRET = "unit-test-client-secret"
_POLICY_PATH = ""


@pytest.fixture(autouse=True)
def configuration_only_tls_boundary(tmp_path, monkeypatch):
    # These tests validate pure startup mapping, not filesystem/certificate
    # admission, which is exercised by test_omada_strict_tls with real fixtures.
    monkeypatch.setitem(globals(), "_POLICY_PATH", str(tmp_path / "approved.pem"))
    monkeypatch.setattr("app.controllers.omada._omada_ssl_context",
                        lambda policy: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))


def valid_settings(**overrides):
    settings = {
        "omada_url": "https://Omada:8043",
        "omada_id": "unit-test-omada-id",
        "client_id": "unit-test-client-id",
        "client_secret": TEST_SECRET,
        "verify_ssl": True,
        "omada_tls_trust_anchor_path": _POLICY_PATH,
        "omada_tls_trust_anchor_sha256": "0" * 64,
    }
    settings.update(overrides)
    return settings


@pytest.fixture
def load_settings_from_environment(monkeypatch):
    def load(values):
        for name in OMADA_ENVIRONMENT_NAMES:
            monkeypatch.delenv(name, raising=False)
        for name, value in values.items():
            monkeypatch.setenv(name, value)

        importlib.reload(config_module)
        importlib.reload(settings_module)
        return settings_module.get_settings()

    yield load

    monkeypatch.undo()
    importlib.reload(config_module)
    importlib.reload(settings_module)


def configuration_error(settings):
    with (
        patch("app.controllers.omada.requests.post") as request_post,
        patch("app.controllers.omada.requests.get") as request_get,
        pytest.raises(ConfigurationError) as exc_info,
    ):
        OmadaProvider(build_omada_runtime_config(settings))

    request_post.assert_not_called()
    request_get.assert_not_called()
    return str(exc_info.value)


def test_environment_values_map_to_existing_keys_and_strip_whitespace(
    load_settings_from_environment,
):
    settings = load_settings_from_environment(
        {
            "OMADA_URL": "  https://controller.invalid:8043/  ",
            "OMADA_ID": "  unit-test-omada-id  ",
            "OMADA_CLIENT_ID": "  unit-test-client-id  ",
            "OMADA_CLIENT_SECRET": f"  {TEST_SECRET}  ",
        }
    )

    assert settings["omada_url"] == "https://controller.invalid:8043/"
    assert settings["omada_id"] == "unit-test-omada-id"
    assert settings["client_id"] == "unit-test-client-id"
    assert settings["client_secret"] == TEST_SECRET


@pytest.mark.parametrize(
    ("internal_name", "external_name"),
    [
        ("omada_url", "OMADA_URL"),
        ("omada_id", "OMADA_ID"),
        ("client_id", "OMADA_CLIENT_ID"),
        ("client_secret", "OMADA_CLIENT_SECRET"),
    ],
)
def test_each_missing_required_value_is_rejected(
    internal_name,
    external_name,
):
    settings = valid_settings()
    settings[internal_name] = ""

    message = configuration_error(settings)

    assert message == f"Missing required configuration: {external_name}"
    assert TEST_SECRET not in message


def test_whitespace_only_required_value_is_rejected():
    message = configuration_error(
        valid_settings(client_secret=" \t ")
    )

    assert message == (
        "Missing required configuration: OMADA_CLIENT_SECRET"
    )


def test_multiple_missing_values_are_reported_in_fixed_external_order():
    message = configuration_error(
        valid_settings(
            omada_url=" ",
            omada_id="",
            client_id=None,
            client_secret="\t",
        )
    )

    assert message == (
        "Missing required configuration: OMADA_URL, OMADA_ID, "
        "OMADA_CLIENT_ID, OMADA_CLIENT_SECRET"
    )


def test_missing_values_are_reported_before_url_syntax_validation():
    message = configuration_error(
        valid_settings(
            omada_url="not-a-url",
            omada_id="",
            client_id=" ",
            client_secret=None,
        )
    )

    assert message == (
        "Missing required configuration: OMADA_ID, "
        "OMADA_CLIENT_ID, OMADA_CLIENT_SECRET"
    )


@pytest.mark.parametrize(
    "omada_url",
    [
        "ftp://controller.invalid",
        "https://",
        "https://user:password@controller.invalid",
        "https://controller.invalid/openapi",
        "https://controller.invalid?token=unit-test-query-secret",
        "https://controller.invalid#fragment",
        "https://controller.invalid:",
        "https://controller.invalid:0",
        "https://controller.invalid:not-a-port",
        "https://controller.invalid:65536",
        "https://controller.invalid//",
        "http://Omada:8043",
        "https://192.168.0.222:8043",
        "https://localhost:8043",
        "https://controller.invalid:8043",
    ],
)
def test_invalid_base_url_is_rejected_without_disclosure_or_network(
    omada_url,
):
    message = configuration_error(valid_settings(omada_url=omada_url))

    assert message == "Invalid configuration: OMADA_URL"
    assert omada_url not in message
    assert TEST_SECRET not in message


@pytest.mark.parametrize(
    ("omada_url", "normalized_url"),
    [
        ("https://Omada:8043", "https://Omada:8043"),
        (
            "https://omada:8043",
            "https://Omada:8043",
        ),
        (
            "https://OMADA:8043/",
            "https://Omada:8043",
        ),
    ],
)
def test_valid_configuration_creates_provider_without_network(
    omada_url,
    normalized_url,
):
    settings = valid_settings(
        omada_url=f"  {omada_url}  ",
        omada_id="  unit-test-omada-id  ",
        client_id="  unit-test-client-id  ",
        client_secret=f"  {TEST_SECRET}  ",
    )

    with (
        patch("app.controllers.omada.requests.post") as request_post,
        patch("app.controllers.omada.requests.get") as request_get,
    ):
        provider = OmadaProvider(build_omada_runtime_config(settings))

    request_post.assert_not_called()
    request_get.assert_not_called()
    assert provider._omada_url == normalized_url
    assert provider._omada_id == "unit-test-omada-id"
    assert provider._client_id == "unit-test-client-id"
    assert provider._client_secret == TEST_SECRET
