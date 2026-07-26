"""Exceptions raised by the portal counter module."""


class PortalCounterError(Exception):
    """Base error for the portal counter."""


class PortalCounterUnavailableError(PortalCounterError):
    """The counter storage is unavailable."""
