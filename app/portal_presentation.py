"""Code-owned, validated plain-text guest presentation; no runtime I/O."""
from dataclasses import dataclass
import re
from types import MappingProxyType
import unicodedata
from urllib.parse import urlsplit


PORTAL_SETTING_DEFAULTS = MappingProxyType({
    "PORTAL_UI_TITLE_AZ": "Zəfər Parkı",
    "PORTAL_UI_TITLE_RU": "Zəfər Parkı",
    "PORTAL_UI_TITLE_EN": "Zəfər Parkı",
    "PORTAL_UI_GREETING_AZ": "Xoş gəlmisiniz!",
    "PORTAL_UI_GREETING_RU": "Добро пожаловать!",
    "PORTAL_UI_GREETING_EN": "Welcome!",
    "PORTAL_UI_DESCRIPTION_AZ": "Parkımızın qonaqları üçün pulsuz\nWi-Fi!!",
    "PORTAL_UI_DESCRIPTION_RU": "Бесплатный Wi-Fi\nдля гостей парка!!",
    "PORTAL_UI_DESCRIPTION_EN": "Free Wi-Fi\nfor park guests!!",
    "PORTAL_SUPPORT_PHONE": "+994 50 417 46 46",
    "PORTAL_SUPPORT_EMAIL": "zaur.navi@gmail.com",
    "PORTAL_SUPPORT_WHATSAPP_URL": "https://wa.me/994504174646",
    "PORTAL_SUPPORT_TELEGRAM_URL": "https://t.me/ZaurNavi",
    "PORTAL_SUPPORT_FACEBOOK_URL": "https://www.facebook.com/zaur.navi/?locale=ru_RU",
})


class PortalPresentationConfigError(ValueError):
    def __init__(self, key=None, reason="invalid_portal_configuration"):
        super().__init__(reason)
        self.key, self.reason = key, reason


class _FrozenJsonDict(dict):
    """Immutable mapping also supported by Jinja's JSON serializer."""
    def _reject(self, *args, **kwargs):
        raise TypeError("immutable Portal presentation")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _reject


def _freeze(value):
    if isinstance(value, dict):
        return _FrozenJsonDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def portal_validation_metadata(key):
    """A fresh public projection of the single server-owned validation contract."""
    if key not in PORTAL_SETTING_DEFAULTS:
        raise PortalPresentationConfigError(key, "unknown_key")
    if key.startswith("PORTAL_UI_"):
        kind = key.split("_")[2]
        result = {"type": "string", "required": True, "min_length": 1,
                  "max_length": {"TITLE": 80, "GREETING": 120, "DESCRIPTION": 400}[kind],
                  "unicode_normalization": "NFC", "content": "plain_text",
                  "line_policy": "lf_multiline" if kind == "DESCRIPTION" else "single_line",
                  "control_characters": "forbidden_except_lf" if kind == "DESCRIPTION" else "forbidden",
                  "bidi_controls": "forbidden"}
        if kind == "DESCRIPTION":
            result["max_lines"] = 4
        return result
    result = {"type": "string", "required": False, "empty_allowed": True, "min_length": 0}
    if key == "PORTAL_SUPPORT_PHONE":
        return dict(result, max_length=32, format="support_phone_e164_display_v1", href_scheme="tel")
    if key == "PORTAL_SUPPORT_EMAIL":
        return dict(result, max_length=254, format="support_email_ascii_v1", href_scheme="mailto")
    result.update(max_length=512 if key.endswith("FACEBOOK_URL") else 256,
                  format="restricted_https_url_v1", scheme="https", explicit_port="forbidden",
                  userinfo="forbidden", fragment="forbidden")
    if key.endswith("WHATSAPP_URL"):
        result.update(allowed_hosts=["wa.me"], query_policy="forbidden", path_pattern="/[0-9]{8,15}")
    elif key.endswith("TELEGRAM_URL"):
        result.update(allowed_hosts=["t.me"], query_policy="forbidden", path_pattern="/[A-Za-z0-9_]{5,64}")
    else:
        result.update(allowed_hosts=["facebook.com", "www.facebook.com"], query_policy="none_or_locale_only",
                      locale_pattern="[A-Za-z]{2,3}_[A-Za-z]{2,3}", path_policy="non_empty_max_256")
    return result


def validate_portal_setting(key, value):
    metadata = portal_validation_metadata(key)
    def fail(reason):
        raise PortalPresentationConfigError(key, reason)
    if type(value) is not str:
        fail("string_required")
    if not metadata["min_length"] <= len(value) <= metadata["max_length"]:
        fail("invalid_length")
    if not value:
        return value
    if value[0].isspace() or value[-1].isspace():
        fail("edge_whitespace")
    if key.startswith("PORTAL_UI_"):
        if unicodedata.normalize("NFC", value) != value:
            fail("non_canonical_unicode")
        multiline = metadata["line_policy"] == "lf_multiline"
        if any((ord(char) < 32 and not (char == "\n" and multiline)) or 127 <= ord(char) <= 159
               or ord(char) in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)) for char in value):
            fail("forbidden_character")
        if (not multiline and any(char in value for char in ("\u2028", "\u2029"))) or (multiline and len(value.split("\n")) > 4):
            fail("invalid_lines")
        return value
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        fail("forbidden_character")
    if key == "PORTAL_SUPPORT_PHONE":
        if not re.fullmatch(r"\+[0-9 ]+", value) or not 8 <= len(value[1:].replace(" ", "")) <= 15:
            fail("invalid_phone")
    elif key == "PORTAL_SUPPORT_EMAIL":
        if not value.isascii() or not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+", value):
            fail("invalid_email")
    else:
        try:
            parsed = urlsplit(value)
        except ValueError:
            fail("invalid_url")
        # Inspect the original authority, not a normalized hostname/port.
        if not value.startswith("https://") or parsed.netloc not in metadata["allowed_hosts"]:
            fail("invalid_url")
        if any(char.isspace() for char in value) or "#" in value or "\\" in value:
            fail("invalid_url")
        if metadata["query_policy"] == "forbidden":
            if "?" in value or not re.fullmatch(metadata["path_pattern"], parsed.path):
                fail("invalid_url")
        elif not parsed.path or len(parsed.path) > 256 or (
            "?" in value and not re.fullmatch(r"locale=[A-Za-z]{2,3}_[A-Za-z]{2,3}", parsed.query)
        ):
            fail("invalid_url")
    return value


@dataclass(frozen=True, slots=True)
class PortalPresentationConfigV1:
    translations: dict
    support: dict

    @classmethod
    def from_settings(cls, settings):
        values = {key: validate_portal_setting(key, settings.get(key.lower(), default))
                  for key, default in PORTAL_SETTING_DEFAULTS.items()}
        translations = {lang: {field: values[f"PORTAL_UI_{field.upper()}_{lang.upper()}"]
                               for field in ("title", "greeting", "description")} for lang in ("az", "ru", "en")}
        phone, email = values["PORTAL_SUPPORT_PHONE"], values["PORTAL_SUPPORT_EMAIL"]
        support = {"phone_display": phone, "phone_href": "tel:" + phone.replace(" ", "") if phone else "",
                   "email": email, "email_href": "mailto:" + email if email else "",
                   **{name + "_url": values[f"PORTAL_SUPPORT_{name.upper()}_URL"]
                      for name in ("whatsapp", "telegram", "facebook")}}
        return cls(_freeze(translations), _freeze(support))


@dataclass(frozen=True, slots=True)
class PortalTemplatePresentationV1:
    translations: dict
    support: dict

    @classmethod
    def compose(cls, candidate):
        from app.web.localization import PORTAL_TRANSLATIONS
        if not isinstance(candidate, PortalPresentationConfigV1) or set(candidate.translations) != {"az", "ru", "en"}:
            raise PortalPresentationConfigError()
        translations = {lang: dict(PORTAL_TRANSLATIONS[lang], **candidate.translations[lang])
                        for lang in ("az", "ru", "en")}
        return cls(_freeze(translations), candidate.support)
