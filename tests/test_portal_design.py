from pathlib import Path
import re

from app.portal_presentation import PORTAL_SETTING_DEFAULTS


ROOT = Path(__file__).parents[1]
PORTAL_TEMPLATE = (
    ROOT / "app" / "web" / "templates" / "portal.html"
)
COUNTER_TEMPLATE = (
    ROOT
    / "app"
    / "web"
    / "templates"
    / "components"
    / "portal_counter.html"
)
COUNTER_STYLES = (
    ROOT
    / "app"
    / "web"
    / "static"
    / "css"
    / "portal_counter.css"
)
LOCALIZATION = ROOT / "app" / "web" / "localization.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_portal_uses_requested_flag_colors_and_copy():
    template = read(PORTAL_TEMPLATE)

    assert "color: #0092CC;" in template
    assert "color: #E4002B;" in template
    assert "color: #00B140;" in template
    assert PORTAL_SETTING_DEFAULTS["PORTAL_UI_DESCRIPTION_AZ"] == "Parkımızın qonaqları üçün pulsuz\nWi-Fi!!"
    assert "{{ portal_translations['az']['description'] }}" in template
    assert "white-space: pre-line;" in template
    assert "font-weight: 700;" in template


def test_portal_has_wifi_decor_support_and_compact_credit():
    template = read(PORTAL_TEMPLATE)

    assert template.count("portal-logo__wave") >= 4
    assert PORTAL_SETTING_DEFAULTS["PORTAL_SUPPORT_PHONE"] == "+994 50 417 46 46"
    assert PORTAL_SETTING_DEFAULTS["PORTAL_SUPPORT_EMAIL"] == "zaur.navi@gmail.com"
    assert PORTAL_SETTING_DEFAULTS["PORTAL_SUPPORT_WHATSAPP_URL"] == "https://wa.me/994504174646"
    assert PORTAL_SETTING_DEFAULTS["PORTAL_SUPPORT_TELEGRAM_URL"] == "https://t.me/ZaurNavi"
    assert PORTAL_SETTING_DEFAULTS["PORTAL_SUPPORT_FACEBOOK_URL"] == "https://www.facebook.com/zaur.navi/?locale=ru_RU"
    assert 'href="{{ portal_support.phone_href }}"' in template
    assert "{{ portal_support.phone_display }}" in template
    assert 'href="{{ portal_support.email_href }}"' in template
    assert "{{ portal_support.email }}" in template
    for field in ("whatsapp_url", "telegram_url", "facebook_url"):
        anchor = re.search(
            r'<a\b[^>]*href="\{\{ portal_support\.' + field + r' \}\}"[^>]*>',
            template,
            re.DOTALL,
        )
        assert anchor is not None
        assert 'target="_blank"' in anchor.group()
        assert 'rel="noopener noreferrer"' in anchor.group()
    assert 'aria-label="WhatsApp"' in template
    assert 'aria-label="Telegram"' in template
    assert 'aria-label="Facebook"' in template
    assert (
        "© Designer: Zaur Navi | "
        "Country should know its heroes."
        in template
    )


def test_counter_is_one_localized_panel():
    template = read(COUNTER_TEMPLATE)
    styles = read(COUNTER_STYLES)

    for label in ("Wi-Fi qoşulmaları", "Bu gün", "Ümumi"):
        assert label in template
    assert 'data-i18n="counterHeading"' in template
    assert 'data-i18n="counterToday"' in template
    assert 'data-i18n="counterTotal"' in template
    assert ".portal-counter-block {" in styles
    assert ".portal-counter {" in styles
    assert "border-radius: 14px;" in styles
    assert ".portal-counter__item {" in styles
    assert "text-align: center;" in styles
    assert (
        ".portal-counter__item + .portal-counter__item"
        in styles
    )
    assert "padding: 6px 8px;" in styles
    assert "grid-template-columns: 1fr;" not in styles


def test_failed_message_explains_how_to_reconnect():
    localization = read(LOCALIZATION)

    assert (
        "Qoşulmanı tamamlamaq mümkün olmadı. Wi-Fi şəbəkəsinə "
        in localization
    )
    assert (
        "Не удалось завершить подключение. Переподключитесь "
        in localization
    )
    assert (
        "We couldn’t complete the connection. Reconnect to Wi-Fi "
        in localization
    )
    assert "showError(texts.finalFailure);" in read(PORTAL_TEMPLATE)
