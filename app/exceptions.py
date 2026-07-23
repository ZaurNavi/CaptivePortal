"""
Custom exceptions for the Captive Portal platform.

All application-specific errors inherit from PortalError.
Never use generic Exception - always use custom exceptions.
"""


class PortalError(Exception):
    """Base exception for all Captive Portal errors."""
    pass


class ConfigurationError(PortalError):
    """Raised when configuration is invalid or missing."""
    pass


class ControllerError(PortalError):
    """Raised when controller operations fail."""
    pass


class ClientNotFound(PortalError):
    """Raised when a client cannot be found."""
    pass


class AuthorizationFailed(PortalError):
    """Raised when authorization fails."""
    pass