import pytest
from . import configuration, source_event, outcome, record


@pytest.mark.parametrize("changes,category", [({"src_ip": "10.73.0.9"}, "normalized"),
    ({"src_ip": "10.73.0.9", "dest_ip": "10.73.0.10"}, "normalized"),
    ({"src_ip": "192.0.2.90", "dest_ip": "203.0.113.90"}, "outside_intended_scope"),
    ({"src_ip": "2001:db8::7"}, "unsupported_address_family_for_scope"),
    ({"src_ip": None, "dest_ip": None}, "schema_invalid"), ({"src_ip": "bad"}, "schema_invalid"),
    ({"timestamp": "2025-12-31T23:59:59Z", "dns": "DO_NOT_PARSE"}, "pre_binding_event")])
def test_scope_before_sensitive_normalization(tmp_path, changes, category):
    result = outcome(configuration(tmp_path).capture_scope_binding, record(source_event(**changes)))
    assert result.category == category
    assert (result.normalized is not None) == (category == "normalized")


def test_vlan_is_not_scope_authority(tmp_path):
    result = outcome(configuration(tmp_path).capture_scope_binding,
        record(source_event(src_ip="192.0.2.90", dest_ip="203.0.113.90", vlan=[20])))
    assert result.category == "outside_intended_scope"
