"""Code-owned global capabilities and exact startup grant parsing."""
DEFAULT_GLOBAL_CAPABILITIES = frozenset({
    "admin.read.settings.global", "admin.write.settings.global",
    "admin.read.settings.controller", "admin.write.settings.controller",
})
SECRET_WRITE_CAPABILITY = "admin.write.settings.controller.secret"
GLOBAL_CAPABILITIES = DEFAULT_GLOBAL_CAPABILITIES | {SECRET_WRITE_CAPABILITY,
    "admin.read.settings.portal", "admin.write.settings.portal"}
DEFAULT_GLOBAL_CAPABILITIES_TEXT = ",".join(sorted(DEFAULT_GLOBAL_CAPABILITIES))


def parse_global_capabilities(value):
    from .config import AdminWebConfigError
    if type(value) is not str or not value.isascii():
        raise AdminWebConfigError("WEB_ADMIN_GLOBAL_CAPABILITIES is invalid")
    tokens = value.split(",")
    if (not 1 <= len(tokens) <= 16 or len(set(tokens)) != len(tokens)
            or any(not 1 <= len(token) <= 128 or token not in GLOBAL_CAPABILITIES for token in tokens)):
        raise AdminWebConfigError("WEB_ADMIN_GLOBAL_CAPABILITIES is invalid")
    return frozenset(tokens)
