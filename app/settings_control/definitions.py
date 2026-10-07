"""One ordered domain-aware registry: twelve General and three Controller keys."""
from dataclasses import dataclass
from app import config


@dataclass(frozen=True, slots=True)
class SettingsDefinition:
    key: str
    repository_default_value: int | str
    min_value: int | None
    max_value: int | None
    display_label: str
    description: str
    semantic_validator: str
    consumer_enable_settings_dict_key: str
    group: str
    value_type: str = "integer"
    scope_type: str = "global"
    secret_class: str = "normal"
    editable: bool = True
    apply_requirement: str = "main_service_restart"
    activation_target: str = "captive-portal.service"
    domain: str = "general"
    settings_dict_key: str = ""
    environment_variable_name: str = ""
    presentation_type: str = "integer"
    required: bool = True


_ROWS = (
    ("DEVICE_PAGE_SIZE", 1, 500, "Device page size", "Devices per page.", "admin_web", "enabled"),
    ("VISIT_PAGE_SIZE", 1, 500, "Visit page size", "Visits per page.", "admin_web", "enabled"),
    ("OBSERVATION_PAGE_SIZE", 1, 500, "Observation page size", "Observations per page.", "admin_web", "enabled"),
    ("OBSERVATION_MAX_WINDOW_HOURS", 1, 168, "Observation window", "Maximum observation window in hours.", "admin_web", "enabled"),
    ("CURRENT_STATE_PAGE_SIZE", 1, 250, "Current state page size", "Current devices and APs per page.", "admin_web", "home_live_enabled"),
    ("HOME_TRAFFIC_PAGE_SIZE", 1, 250, "Home traffic page size", "Traffic APs per page.", "admin_web", "home_traffic_enabled"),
    ("HOME_LIVE_REFRESH_SECONDS", 60, 300, "Home live refresh", "Refresh interval in seconds.", "admin_web", "home_live_enabled"),
    ("HOME_TRAFFIC_REFRESH_SECONDS", 60, 300, "Home traffic refresh", "Refresh interval in seconds.", "admin_web", "home_traffic_enabled"),
    ("TRAFFIC_REFRESH_SECONDS", 60, 300, "Traffic refresh", "Refresh interval in seconds.", "admin_web", "traffic_enabled"),
    ("HOME_ACTIVITY_REFRESH_SECONDS", 60, 300, "Home activity refresh", "Refresh interval in seconds.", "home_activity", "home_activity_enabled"),
    ("HOME_HEALTH_REFRESH_SECONDS", 60, 300, "Home health refresh", "Refresh interval in seconds.", "home_health", "home_health_enabled"),
    ("HOME_AP_24H_REFRESH_SECONDS", 60, 600, "AP 24-hour refresh", "Refresh interval in seconds.", "home_ap_24h", "home_ap_24h_enabled"),
)


class SettingsDefinitionRegistry:
    def __init__(self):
        self.definitions = tuple(
            SettingsDefinition(
                "WEB_ADMIN_" + suffix,
                getattr(config, "DEFAULT_WEB_ADMIN_" + suffix), minimum, maximum,
                label, description, validator + "_config_from_settings",
                "web_admin_" + consumer,
                "pagination" if index < 6 else "refresh",
                settings_dict_key=("WEB_ADMIN_" + suffix).lower(),
                environment_variable_name="WEB_ADMIN_" + suffix,
            )
            for index, (suffix, minimum, maximum, label, description, validator, consumer)
            in enumerate(_ROWS)
        ) + tuple(SettingsDefinition(
            key, "", None, None, label, "Required shared Omada Controller configuration.",
            "omada_runtime_config", "", "controller", value_type="string", domain="controller",
            settings_dict_key=internal, environment_variable_name=key, presentation_type=presentation,
        ) for key, internal, label, presentation in (
            ("OMADA_URL", "omada_url", "Controller URL", "url"),
            ("OMADA_ID", "omada_id", "Controller ID", "string"),
            ("OMADA_CLIENT_ID", "client_id", "Client / Application ID", "string"),
        ))

    def __iter__(self):
        return iter(self.definitions)

    def get(self, key):
        return next((item for item in self if item.key == key), None)

    def for_domain(self, domain):
        return tuple(item for item in self if item.domain == domain)
