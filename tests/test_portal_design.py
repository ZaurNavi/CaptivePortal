from pathlib import Path


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
    assert (
        "Parkımızın qonaqları üçün pulsuz\nWi-Fi!!"
        in template
    )
    assert "white-space: pre-line;" in template
    assert "font-weight: 700;" in template


def test_portal_has_wifi_decor_support_and_compact_credit():
    template = read(PORTAL_TEMPLATE)

    assert template.count("portal-logo__wave") >= 4
    assert 'href="tel:+994504174646"' in template
    assert 'href="mailto:zaur.navi@gmail.com"' in template
    assert 'href="https://wa.me/994504174646"' in template
    assert 'href="https://t.me/ZaurNavi"' in template
    assert (
        'href="https://www.facebook.com/zaur.navi/'
        '?locale=ru_RU"'
        in template
    )
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
