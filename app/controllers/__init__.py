"""Controllers package exports and provider extensions."""

from app.controllers.base import ControllerInterface
from app.controllers.omada import OmadaProvider
from app.controllers.omada_pending_sessions import install_pending_session_methods

install_pending_session_methods(OmadaProvider)

from app.controllers.factory import create_controller  # noqa: E402

__all__ = [
    "ControllerInterface",
    "OmadaProvider",
    "create_controller",
]
