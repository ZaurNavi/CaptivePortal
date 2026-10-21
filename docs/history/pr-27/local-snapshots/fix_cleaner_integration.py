#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            print(f"already patched: {path}")
            return
        raise SystemExit(f"anchor not found: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched: {path}")


omada = Path("app/controllers/omada.py")
text = omada.read_text(encoding="utf-8")

method = """    def _ensure_token_cache_state(self) -> None:
        # Support normal construction and tests using __new__.
        if hasattr(self, "_token_condition"):
            return
        self._token_condition = threading.Condition(
            threading.RLock()
        )
        self._cached_token = None
        self._cached_token_expires_at = 0.0
        self._token_refreshing = False

"""

token_def = (
    "    def _get_token("
    "self, *, force_refresh: bool = False"
    ") -> Result:\n"
)

if "    def _ensure_token_cache_state(self) -> None:\n" not in text:
    if token_def not in text:
        raise SystemExit("Omada _get_token definition not found")
    text = text.replace(token_def, method + token_def, 1)

old_body = """    def _get_token(self, *, force_refresh: bool = False) -> Result:
        # One atomic cache shared by AuthWorker and Cleaner threads.
        while True:
"""
new_body = """    def _get_token(self, *, force_refresh: bool = False) -> Result:
        # One atomic cache shared by AuthWorker and Cleaner threads.
        self._ensure_token_cache_state()
        while True:
"""
if old_body in text:
    text = text.replace(old_body, new_body, 1)
elif new_body not in text:
    raise SystemExit("Omada _get_token body anchor not found")

old_invalidate = """    def _invalidate_cached_token(self, token=None) -> None:
        with self._token_condition:
"""
new_invalidate = """    def _invalidate_cached_token(self, token=None) -> None:
        self._ensure_token_cache_state()
        with self._token_condition:
"""
if old_invalidate in text:
    text = text.replace(old_invalidate, new_invalidate, 1)
elif new_invalidate not in text:
    raise SystemExit("Omada invalidate anchor not found")

omada.write_text(text, encoding="utf-8")
print("patched: app/controllers/omada.py")

replace_once(
    Path("run.py"),
    '        telemetry=app.extensions["auth_telemetry"],\n',
    '        telemetry=app.extensions.get("auth_telemetry"),\n',
)

print("integration fix completed")
