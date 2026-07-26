"""Internal exceptions for the telemetry package."""


class AuthTelemetryError(Exception):
    """Base exception used only inside the fail-open telemetry boundary."""
