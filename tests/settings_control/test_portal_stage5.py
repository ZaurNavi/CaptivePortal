"""Stage-5 + C1 disposable ordinary Settings proofs; no external I/O."""
import json
import logging
import uuid
from dataclasses import replace
from types import SimpleNamespace
import pytest

from app.admin_web.models import AdminPrincipal
from app.portal_presentation import (PORTAL_SETTING_DEFAULTS, PortalPresentationConfigV1,
    PortalPresentationConfigError, portal_validation_metadata, validate_portal_setting)
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.definitions import SettingsDefinitionRegistry
from app.settings_control.models import SettingsError
from app.settings_control.resolver import resolve_settings, freeze
from app.settings_control.services import parse_changes
from app.settings_control.validation import SettingsValidationService
from . import CONTROLLER_BASE, stack, mutation
from .stage4_helpers import secret_stack, secret_mutation


def portal_write(boot, changes=None, *, generation=0, key=None):
    return boot.admin_context.mutation_service.mutate(json.dumps({"changes": changes if changes is not None else [
        {"key": "PORTAL_UI_TITLE_AZ", "operation": "set", "value": "Yeni başlıq"}]}),
        principal=AdminPrincipal("operator"), source_ip="127.0.0.1", request_id=str(uuid.uuid4()),
        idempotency_key=key or str(uuid.uuid4()), expected_generation=generation, domain="portal")


def test_exact_definitions_defaults_metadata():
    registry = SettingsDefinitionRegistry()
    definitions = registry.for_domain("portal")
    assert [item.key for item in definitions] == list(PORTAL_SETTING_DEFAULTS)
    assert len(definitions) == 14 and len(registry.for_domain("general")) == 12 and len(registry.for_domain("controller")) == 3
    for item in definitions:
        assert item.repository_default_value == PORTAL_SETTING_DEFAULTS[item.key]
        assert item.settings_dict_key == item.key.lower() and item.environment_variable_name == item.key
        assert item.scope_type == "global" and item.secret_class == "normal" and item.editable
        assert item.value_type == "string" and item.apply_requirement == "main_service_restart"
        assert item.activation_target == "captive-portal.service"
        assert item.group == ("branding" if "_UI_" in item.key else "support")
        assert item.semantic_validator == "portal_presentation"
        if "_UI_" in item.key:
            kind, lang = item.key.split("_")[2:]
            language = {"AZ": "Azerbaijani", "RU": "Russian", "EN": "English"}[lang]
            label, description = {"TITLE": ("Portal title", "title"), "GREETING": ("Welcome text", "welcome text"),
                                  "DESCRIPTION": ("Guest description", "short guest description")}[kind]
            assert item.display_label == label + " — " + language
            assert item.description == f"Public {description} shown to guests in {language}."
            assert item.presentation_type == ("multiline_plain_text" if kind == "DESCRIPTION" else "plain_text")
        else:
            label, description, presentation = {
                "PHONE": ("Support phone", "phone number", "telephone"),
                "EMAIL": ("Support email", "email address", "email"),
                **{name + "_URL": (display + " support link", display + " support link", "restricted_url")
                   for name, display in (("WHATSAPP", "WhatsApp"), ("TELEGRAM", "Telegram"), ("FACEBOOK", "Facebook"))},
            }[item.key.removeprefix("PORTAL_SUPPORT_")]
            assert (item.display_label, item.description, item.presentation_type) == (label, f"Public {description} shown to guests.", presentation)
    assert portal_validation_metadata("PORTAL_UI_TITLE_EN") == {"type": "string", "required": True,
        "min_length": 1, "max_length": 80, "unicode_normalization": "NFC", "content": "plain_text",
        "line_policy": "single_line", "control_characters": "forbidden", "bidi_controls": "forbidden"}
    with pytest.raises(TypeError):
        PORTAL_SETTING_DEFAULTS["OTHER"] = "invalid"


@pytest.mark.parametrize("key", list(PORTAL_SETTING_DEFAULTS))
def test_default_and_metadata_are_single_source(key):
    assert validate_portal_setting(key, PORTAL_SETTING_DEFAULTS[key]) == PORTAL_SETTING_DEFAULTS[key]
    metadata = portal_validation_metadata(key)
    assert metadata["type"] == "string"
    assert metadata["required"] == ("_UI_" in key)
    if "_SUPPORT_" in key:
        assert validate_portal_setting(key, "") == ""


@pytest.mark.parametrize("field,maximum", [("TITLE", 80), ("GREETING", 120), ("DESCRIPTION", 400)])
@pytest.mark.parametrize("value", ["", " ", " leading", "trailing\u2003", "a\x00b", "a\x01b", "a\x85b",
                                  "a\rb", "a\tb", "a\u202eb", "a\u2066b", "e\u0301"])
def test_text_invalid(field, maximum, value):
    with pytest.raises(PortalPresentationConfigError):
        validate_portal_setting("PORTAL_UI_" + field + "_EN", value)


@pytest.mark.parametrize("field,maximum", [("TITLE", 80), ("GREETING", 120), ("DESCRIPTION", 400)])
def test_text_exact_unicode_boundaries(field, maximum):
    key = "PORTAL_UI_" + field + "_AZ"
    for value in ("Zəfər", "Добро пожаловать", "Welcome", "é", "<script>alert(1)</script>", "😀" * maximum):
        assert validate_portal_setting(key, value) == value
    with pytest.raises(PortalPresentationConfigError):
        validate_portal_setting(key, "x" * (maximum + 1))
    with pytest.raises(PortalPresentationConfigError) as error:
        validate_portal_setting(key, "e\u0301")
    assert error.value.reason == "non_canonical_unicode"


def test_line_contract():
    for kind in ("TITLE", "GREETING"):
        with pytest.raises(PortalPresentationConfigError):
            validate_portal_setting("PORTAL_UI_" + kind + "_EN", "a\nb")
    assert validate_portal_setting("PORTAL_UI_DESCRIPTION_EN", "a\nb\nc\nd") == "a\nb\nc\nd"
    with pytest.raises(PortalPresentationConfigError):
        validate_portal_setting("PORTAL_UI_DESCRIPTION_EN", "a\nb\nc\nd\ne")


@pytest.mark.parametrize("value", ["12345678", "+1234567", "+1234567890123456", "+1234-5678", "+12345678 ", "+12345678\r\n", "+１２３４５６７８"])
def test_phone_rejections(value):
    with pytest.raises(PortalPresentationConfigError): validate_portal_setting("PORTAL_SUPPORT_PHONE", value)


@pytest.mark.parametrize("value", ["no-at", "a@@b", "a @b", "Name <a@b.com>", "a@b.com\r\n", "a@b.com?subject=x", "a@b/com", "é@b.com", "mailto:a@b.com"])
def test_email_rejections(value):
    with pytest.raises(PortalPresentationConfigError): validate_portal_setting("PORTAL_SUPPORT_EMAIL", value)


@pytest.mark.parametrize("name,values", [
    ("WHATSAPP", ["https://wa.me/1234567", "https://wa.me/1234567890123456", "https://wa.me/12345678?x=1", "https://wa.me/12345678/extra"]),
    ("TELEGRAM", ["https://t.me/abcd", "https://t.me/username/extra", "https://t.me/username?x=1"]),
    ("FACEBOOK", ["https://facebook.com", "https://facebook.com/user?x=1", "https://facebook.com/user?locale=ru_RU&locale=en_US", "https://facebook.com/user?locale=bad", "https://facebook.com/" + "a" * 256]),
])
def test_social_path_rejections(name, values):
    for value in values:
        with pytest.raises(PortalPresentationConfigError): validate_portal_setting(f"PORTAL_SUPPORT_{name}_URL", value)


@pytest.mark.parametrize("host,path,name", [("wa.me", "12345678", "WHATSAPP"), ("t.me", "username", "TELEGRAM"), ("www.facebook.com", "user", "FACEBOOK")])
@pytest.mark.parametrize("shape", ["http://{host}/{path}", "https://user@{host}/{path}", "https://{host}:443/{path}",
    "https://{host}:8443/{path}", "https://{host}./{path}", "https://{host}/{path}#x", "//{host}/{path}",
    "https://127.0.0.1/{path}", "https://[::1]/{path}", "https://ｗa.me/{path}"])
def test_social_authority_rejections(host, path, name, shape):
    with pytest.raises(PortalPresentationConfigError): validate_portal_setting(f"PORTAL_SUPPORT_{name}_URL", shape.format(host=host, path=path))


def test_support_projection_and_valid_urls():
    values = {"portal_support_phone": "+1234 5678", "portal_support_email": "a._%+-@b-c.example"}
    candidate = PortalPresentationConfigV1.from_settings(values)
    assert candidate.support["phone_display"] == "+1234 5678" and candidate.support["phone_href"] == "tel:+12345678"
    assert candidate.support["email_href"] == "mailto:a._%+-@b-c.example"
    for key, value in (("WHATSAPP", "https://wa.me/12345678"), ("TELEGRAM", "https://t.me/username"),
                       ("FACEBOOK", "https://facebook.com/user"), ("FACEBOOK", "https://www.facebook.com/user?locale=en_US")):
        assert validate_portal_setting(f"PORTAL_SUPPORT_{key}_URL", value) == value


def test_resolution_and_clear_precedence(tmp_path):
    base = {**CONTROLLER_BASE, "web_admin_settings_enabled": True, "settings_db_path": str(tmp_path / "settings.sqlite3"),
            "portal_ui_title_az": "Deployment"}
    boot = bootstrap_settings_control(base_settings=base, explicit_environment_names={"PORTAL_UI_TITLE_AZ"}, logger=logging.getLogger("stage5"))
    original = boot.admin_context.read_service.read_portal()["settings"]
    assert original[0]["base_source"] == "environment" and original[0]["configured_value"] == "Deployment"
    assert original[1]["base_source"] == "repository_default"
    result = portal_write(boot)
    assert result.status == 201 and result.body["changed_keys"] == ["PORTAL_UI_TITLE_AZ"]
    portal_write(boot, [{"key": "PORTAL_UI_TITLE_AZ", "operation": "clear_override"}], generation=1)
    assert boot.admin_context.read_service.read_portal()["settings"][0]["configured_value"] == "Deployment"
    resolved = resolve_settings(CONTROLLER_BASE, set(), {}, 0)
    assert resolved.values["portal_ui_title_az"] == PORTAL_SETTING_DEFAULTS["PORTAL_UI_TITLE_AZ"]


def test_mutation_receipts_common_cas_and_exact_response(tmp_path):
    boot = stack(tmp_path)
    boot.activation_service.adopt(boot.runtime_settings, None)
    key = str(uuid.uuid4())
    changed = portal_write(boot, key=key)
    assert changed.status == 201
    assert set(changed.body) == {"api_version", "request_id", "scope", "resource", "changed", "changed_keys", "configured_generation", "effective_generation", "activation_state", "restart_required"}
    assert changed.body["resource"] == {"type": "guest_portal", "scope": "installation"}
    assert changed.body["activation_state"] == "pending_main_restart"
    noop = portal_write(boot, generation=1)
    assert noop.status == 200 and not noop.body["changed"] and noop.body["restart_required"]
    assert noop.body["changed_keys"] == [] and noop.body["activation_state"] == "pending_main_restart"
    mutation(boot, generation=1)
    replay = portal_write(boot, key=key)
    assert replay == changed
    with pytest.raises(SettingsError, match="stale_generation"): portal_write(boot, generation=1)
    with pytest.raises(SettingsError, match="idempotency_conflict"):
        portal_write(boot, [{"key": "PORTAL_UI_TITLE_AZ", "operation": "set", "value": "Different"}], key=key)
    with boot.admin_context.read_service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_mutation_audit WHERE setting_domain='portal'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM settings_idempotency WHERE mutation_domain='portal'").fetchone()[0] == 2


def test_full_14_batch_and_atomic_invalid_candidate(tmp_path):
    boot = stack(tmp_path)
    changes = [{"key": key, "operation": "set", "value": value} for key, value in PORTAL_SETTING_DEFAULTS.items()]
    assert portal_write(boot, changes).body["changed_keys"] == sorted(PORTAL_SETTING_DEFAULTS)
    repository = boot.admin_context.read_service.repository
    with repository.transaction() as db:
        before = [db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in ("settings_generations", "settings_mutation_audit", "settings_idempotency")]
    changes[-1]["value"] = "http://facebook.com/invalid"
    with pytest.raises(SettingsError, match="validation_failed"): portal_write(boot, changes, generation=1)
    with repository.transaction() as db:
        assert before == [db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in ("settings_generations", "settings_mutation_audit", "settings_idempotency")]
    service = boot.admin_context.mutation_service
    service.read_service.base_settings = {**service.read_service.base_settings, "portal_ui_greeting_ru": ""}
    # Shadowed persisted value is selected, not an invalid deployment value.
    assert portal_write(boot, generation=1).status == 201
    service.read_service.base_settings = {**service.read_service.base_settings, "portal_ui_title_en": ""}
    with pytest.raises(SettingsError):
        portal_write(boot, [{"key": "PORTAL_UI_TITLE_EN", "operation": "clear_override"}], generation=2)


@pytest.mark.parametrize("changes", [[{"key": "OTHER", "operation": "set", "value": "x"}],
    [{"key": "OMADA_ID", "operation": "set", "value": "x"}],
    [{"key": "PORTAL_UI_TITLE_AZ", "operation": "set", "value": 1}],
    [{"key": "PORTAL_UI_TITLE_AZ", "operation": "clear_override", "value": "x"}],
    [{"key": "PORTAL_UI_TITLE_AZ", "operation": "set", "value": "x"}] * 2])
def test_parser_closed(changes):
    with pytest.raises(SettingsError, match="invalid_request"): parse_changes(json.dumps({"changes": changes}), domain="portal")


def test_c1_no_secret_resolution_no_keys_and_inheritance(tmp_path, monkeypatch):
    boot, filesystem = secret_stack(tmp_path)
    secret_mutation(boot)
    service = boot.admin_context.mutation_service
    from app.settings_control.controller_secret import binding
    with service.repository.transaction() as db: parent_binding = binding(db, 1)
    reads = filesystem.key_reads
    def forbidden(*args, **kwargs): raise AssertionError("Portal must not access secret store")
    monkeypatch.setattr(service.secret_repository, "resolve", forbidden)
    monkeypatch.setattr(service.secret_repository, "keys", forbidden)
    filesystem.key_valid = False
    assert portal_write(boot, generation=1).status == 201
    with service.repository.transaction() as db: assert binding(db, 2) == parent_binding
    assert filesystem.key_reads == reads
    # General and Controller remain on the full secret path.
    with pytest.raises(AssertionError, match="secret store"): mutation(boot, generation=2)
    with pytest.raises(AssertionError, match="secret store"):
        service.mutate(json.dumps({"changes": [{"key": "OMADA_ID", "operation": "set", "value": "new"}]}),
            principal=AdminPrincipal("operator"), source_ip="127.0.0.1", request_id="r", idempotency_key=str(uuid.uuid4()), expected_generation=2, domain="controller")
    # Later startup still fails closed on the inherited binding.
    with pytest.raises(SettingsError, match="controller_secret_key_unavailable"):
        bootstrap_settings_control(base_settings={**CONTROLLER_BASE, "web_admin_settings_enabled": True,
            "settings_db_path": service.repository.db_path}, explicit_environment_names=set(), logger=logging.getLogger("stage5"), secret_filesystem=filesystem)


def test_c1_no_binding_and_complete_candidate_validation(tmp_path):
    boot = stack(tmp_path)
    portal_write(boot)
    with boot.admin_context.read_service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_secret_bindings").fetchone()[0] == 0
    snapshot = boot.resolved_snapshot
    validation = SettingsValidationService()
    for key, value in (("omada_url", "invalid"), ("omada_id", ""), ("client_id", "")):
        with pytest.raises(SettingsError) as error:
            validation.validate_portal_candidate(replace(snapshot, values=freeze({**snapshot.values, key: value})))
        assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
    for key in PORTAL_SETTING_DEFAULTS:
        with pytest.raises(SettingsError):
            validation.validate_portal_candidate(replace(snapshot, values=freeze({**snapshot.values, key.lower(): "invalid" if "_SUPPORT_" in key else ""})))


@pytest.mark.parametrize("key,value", [("omada_url", "invalid"), ("omada_id", ""), ("client_id", "")])
def test_c1_invalid_nonsecret_prerequisites_fail_atomically_at_mutation(tmp_path, key, value):
    boot = stack(tmp_path)
    service = boot.admin_context.mutation_service
    service.read_service.base_settings = {**service.read_service.base_settings, key: value}
    with pytest.raises(SettingsError) as error: portal_write(boot)
    assert error.value.status == 422
    assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
    assert service.repository.configured() == (0, {})
    with service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_mutation_audit").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM settings_idempotency").fetchone()[0] == 0


def test_read_adopted_pending_and_untrusted(tmp_path):
    boot = stack(tmp_path)
    read = boot.admin_context.read_service
    assert all(row["effective_value"] is None for row in read.read_portal()["settings"])
    boot.activation_service.adopt(boot.runtime_settings, None)
    portal_write(boot)
    body = read.read_portal()
    assert body["pending_setting_count"] == 1
    assert body["settings"][0]["effective_value"] == PORTAL_SETTING_DEFAULTS["PORTAL_UI_TITLE_AZ"]
    assert body["settings"][0]["pending_value"] == "Yeni başlıq"
    assert body["settings"][0]["last_changed_by"] == {"principal_type": "platform_operator", "principal_name": "operator"}
    assert all(row["pending_value"] is None for row in body["settings"][1:])
    read.repository.activation(1, True)  # Another process adopted; this process isn't that runtime.
    assert all(row["effective_value"] is None and row["pending_value"] is None for row in read.read_portal()["settings"])
