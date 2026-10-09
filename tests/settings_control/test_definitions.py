from app import config
from app.settings import get_settings
from app.settings_control.definitions import SettingsDefinitionRegistry


def test_exact_ordered_definitions_and_shared_defaults():
    expected = [
        ("DEVICE_PAGE_SIZE", 100, 1, 500, "enabled", "admin_web"),
        ("VISIT_PAGE_SIZE", 100, 1, 500, "enabled", "admin_web"),
        ("OBSERVATION_PAGE_SIZE", 100, 1, 500, "enabled", "admin_web"),
        ("OBSERVATION_MAX_WINDOW_HOURS", 24, 1, 168, "enabled", "admin_web"),
        ("CURRENT_STATE_PAGE_SIZE", 100, 1, 250, "home_live_enabled", "admin_web"),
        ("HOME_TRAFFIC_PAGE_SIZE", 100, 1, 250, "home_traffic_enabled", "admin_web"),
        ("HOME_LIVE_REFRESH_SECONDS", 60, 60, 300, "home_live_enabled", "admin_web"),
        ("HOME_TRAFFIC_REFRESH_SECONDS", 60, 60, 300, "home_traffic_enabled", "admin_web"),
        ("TRAFFIC_REFRESH_SECONDS", 60, 60, 300, "traffic_enabled", "admin_web"),
        ("HOME_ACTIVITY_REFRESH_SECONDS", 60, 60, 300, "home_activity_enabled", "home_activity"),
        ("HOME_HEALTH_REFRESH_SECONDS", 60, 60, 300, "home_health_enabled", "home_health"),
        ("HOME_AP_24H_REFRESH_SECONDS", 120, 60, 600, "home_ap_24h_enabled", "home_ap_24h"),
    ]
    registry = SettingsDefinitionRegistry()
    assert len(registry.definitions) == 46
    assert len(registry.for_domain("general")) == 12
    assert [item.key for item in registry.for_domain("general")] == [
        "WEB_ADMIN_" + suffix for suffix, *_ in expected
    ]
    assert [item.key for item in registry.for_domain("controller")] == ["OMADA_URL", "OMADA_ID", "OMADA_CLIENT_ID"]
    assert [item.key for item in registry.for_domain("portal")] == [
        "PORTAL_UI_TITLE_AZ",
        "PORTAL_UI_TITLE_RU",
        "PORTAL_UI_TITLE_EN",
        "PORTAL_UI_GREETING_AZ",
        "PORTAL_UI_GREETING_RU",
        "PORTAL_UI_GREETING_EN",
        "PORTAL_UI_DESCRIPTION_AZ",
        "PORTAL_UI_DESCRIPTION_RU",
        "PORTAL_UI_DESCRIPTION_EN",
        "PORTAL_SUPPORT_PHONE",
        "PORTAL_SUPPORT_EMAIL",
        "PORTAL_SUPPORT_WHATSAPP_URL",
        "PORTAL_SUPPORT_TELEGRAM_URL",
        "PORTAL_SUPPORT_FACEBOOK_URL",
    ]
    assert registry.get("OMADA_CLIENT_ID").settings_dict_key == "client_id"
    assert registry.get("OMADA_CLIENT_SECRET") is None
    assert registry.get("VERIFY_SSL") is None
    for index, (definition, (suffix, default, minimum, maximum, consumer, validator)) in enumerate(zip(registry, expected)):
        key = "WEB_ADMIN_" + suffix
        assert definition.key == definition.environment_variable_name == key
        assert definition.settings_dict_key == key.lower()
        assert definition.repository_default_value == default == getattr(config, "DEFAULT_" + key)
        assert (definition.min_value, definition.max_value) == (minimum, maximum)
        assert definition.semantic_validator == validator + "_config_from_settings"
        assert definition.consumer_enable_settings_dict_key == "web_admin_" + consumer
        assert definition.editable and definition.value_type == "integer"
        assert definition.scope_type == "global" and definition.secret_class == "normal"
        assert definition.apply_requirement == "main_service_restart"
        assert definition.activation_target == "captive-portal.service"
        assert definition.group == ("pagination" if index < 6 else "refresh")
    assert registry.get("WEB_ADMIN_ENABLED") is None
    assert registry.get("SETTINGS_DB_PATH") is None
    assert get_settings()["web_admin_settings_enabled"] == "false"
