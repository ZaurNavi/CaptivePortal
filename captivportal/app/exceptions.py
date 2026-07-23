"""
Custom exceptions for Captive Portal.

All application-specific errors inherit from PortalError.
No external dependencies.
"""


class PortalError(Exception):
    """Base exception for all Captive Portal errors."""
    pass


class ConfigurationError(PortalError):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


class ControllerError(PortalError):
    """Raised when controller-related operations fail."""
    pass


class ClientNotFound(PortalError):
    """Raised when a client cannot be found."""
    pass


class AuthorizationFailed(PortalError):
    """Raised when authorization fails."""
    pass
