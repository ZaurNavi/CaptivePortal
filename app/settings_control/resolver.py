"""One resolver; explicit environment membership, never scalar-origin inference."""
from types import MappingProxyType
from .definitions import SettingsDefinitionRegistry
from .models import ResolvedSettingsSnapshot, SettingsError


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


def resolve_settings(base_settings, explicit_environment_names, overrides, generation_id, registry=None):
    registry = registry or SettingsDefinitionRegistry()
    if set(overrides) - {item.key for item in registry}:
        raise SettingsError("settings_store_unavailable")
    values = dict(base_settings)
    sources, base_values, persisted = {}, {}, {}
    for definition in registry:
        raw = base_settings.get(definition.settings_dict_key, definition.repository_default_value)
        if type(raw) is int:
            base = raw
        elif isinstance(raw, str) and raw.isascii() and raw.isdigit():
            base = int(raw)
        else:
            raise SettingsError("validation_failed", 422, ({"key": definition.key, "reason": "invalid_base_integer"},))
        sources[definition.key] = "environment" if definition.key in explicit_environment_names else "repository_default"
        base_values[definition.key] = base
        persisted[definition.key] = overrides.get(definition.key)
        values[definition.settings_dict_key] = overrides.get(definition.key, base)
    return ResolvedSettingsSnapshot(generation_id, freeze(values), freeze(sources), freeze(base_values), freeze(persisted))
