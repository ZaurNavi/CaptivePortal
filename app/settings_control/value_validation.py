"""Definition-owned ordinary value validation shared by all Store boundaries."""
from app.controllers.omada_config import normalize_controller_setting
from app.exceptions import ConfigurationError
from app.portal_presentation import PortalPresentationConfigError, validate_portal_setting
from .models import SettingsError


def validate_setting_value(definition, value, *, durable=False):
    try:
        if definition.value_type == "integer":
            if type(value) is not int:
                raise SettingsError("validation_failed", 422, ({"key": definition.key, "reason": "integer_required"},))
            if not definition.min_value <= value <= definition.max_value:
                raise SettingsError("validation_failed", 422, ({"key": definition.key, "reason": "out_of_range"},))
            return value
        if definition.domain == "portal":
            return validate_portal_setting(definition.key, value)
        if definition.domain == "features":
            from .features import feature_boolean
            feature_boolean(value, definition.key)
            return value
        return normalize_controller_setting(definition.key, value)
    except PortalPresentationConfigError as error:
        raise SettingsError("settings_store_unavailable" if durable else "validation_failed",
                            503 if durable else 422, () if durable else ({"key": definition.key, "reason": error.reason},)) from None
    except ConfigurationError:
        raise SettingsError("settings_store_unavailable" if durable else "validation_failed", 503 if durable else 422,
                            () if durable else ({"key": definition.key,
                             "reason": "required" if not isinstance(value, str) or not value.strip() else "invalid_url"},)) from None
    except SettingsError:
        if durable:
            raise SettingsError("settings_store_unavailable") from None
        raise
