"""Immutable startup feature preferences and registry-owned dependency graph.

No environment, Store, source-health or request-time reads occur here.
WEB_ADMIN_ENABLED is an outer composition gate, never a graph parent.
"""
from dataclasses import dataclass
from types import MappingProxyType
from .definitions import SettingsDefinitionRegistry
from .models import SettingsError


def feature_boolean(value, key):
    if type(value) is not str or value not in ("true", "false"):
        raise SettingsError("validation_failed", 422, ({"key": key, "reason": "boolean_required"},))
    return value == "true"


@dataclass(frozen=True, slots=True)
class AdminFeaturePlanV1:
    generation_id: int | None
    configured_values: object
    states: object
    blocked_by: object
    registry: object

    @classmethod
    def from_snapshot(cls, snapshot, registry=None):
        registry = registry or SettingsDefinitionRegistry()
        definitions = registry.for_domain("features")
        values = {item.key: feature_boolean(snapshot.values.get(item.settings_dict_key, "false"), item.key)
                  for item in definitions}
        by_key = {item.key: item for item in definitions}
        def ancestors(item):
            result = []
            for key in item.parent_feature_keys:
                for ancestor in (*ancestors(by_key[key]), key):
                    if ancestor not in result:
                        result.append(ancestor)
            return tuple(result)
        blocked = {item.feature_id: tuple(key for key in ancestors(item) if not values[key]) for item in definitions}
        states = {item.feature_id: "disabled" if not values[item.key] else
                  "dormant_parent_disabled" if blocked[item.feature_id] else "enabled" for item in definitions}
        return cls(snapshot.generation_id, MappingProxyType(values), MappingProxyType(states),
                   MappingProxyType(blocked), definitions)

    def configured_state(self, feature_id):
        return self.states[feature_id]

    def effective_state(self, feature_id):
        return self.states[feature_id]

    def enabled(self, feature_id):
        return self.effective_state(feature_id) == "enabled"

    def composition_settings(self, values):
        """Selected exposure, while keeping raw preferences in the snapshot."""
        admin = values.get("web_admin_enabled", "false") in (True, "true")
        result = dict(values)
        for item in self.registry:
            result[item.settings_dict_key] = "true" if admin and self.enabled(item.feature_id) else "false"
        return MappingProxyType(result)
