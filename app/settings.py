"""
Settings module.

Currently reads settings from config.py.
Designed to be extended in future versions to read from files or environment.
"""

from app.config import (
    HOST, PORT, DEBUG, VERIFY_SSL, LOG_LEVEL,
    PORTAL_COUNTER_ENABLED, PORTAL_COUNTER_DB_PATH,
    PORTAL_COUNTER_TIMEZONE, PORTAL_COUNTER_API_ENABLED,
    AUTH_TELEMETRY_ENABLED, AUTH_TELEMETRY_LOG_PATH,
    AUTH_TELEMETRY_LEVEL, AUTH_TELEMETRY_SCHEMA_VERSION,
    AUTH_TELEMETRY_ROTATION_MAX_BYTES,
    AUTH_TELEMETRY_ROTATION_BACKUP_COUNT,
    OMADA_URL, OMADA_ID, CLIENT_ID, CLIENT_SECRET
)
from app.logger import logger


def get_settings() -> dict:
    """
    Retrieve application settings.

    Returns:
        dict: Dictionary containing all application settings.
    """
    logger.debug("Loading settings from config")
    return {
        "host": HOST,
        "port": PORT,
        "debug": DEBUG,
        "verify_ssl": VERIFY_SSL,
        "log_level": LOG_LEVEL,
        "portal_counter_enabled": PORTAL_COUNTER_ENABLED,
        "portal_counter_db_path": PORTAL_COUNTER_DB_PATH,
        "portal_counter_timezone": PORTAL_COUNTER_TIMEZONE,
        "portal_counter_api_enabled": PORTAL_COUNTER_API_ENABLED,
        "auth_telemetry_enabled": AUTH_TELEMETRY_ENABLED,
        "auth_telemetry_log_path": AUTH_TELEMETRY_LOG_PATH,
        "auth_telemetry_level": AUTH_TELEMETRY_LEVEL,
        "auth_telemetry_schema_version": AUTH_TELEMETRY_SCHEMA_VERSION,
        "auth_telemetry_rotation_max_bytes": (
            AUTH_TELEMETRY_ROTATION_MAX_BYTES
        ),
        "auth_telemetry_rotation_backup_count": (
            AUTH_TELEMETRY_ROTATION_BACKUP_COUNT
        ),
        "omada_url": OMADA_URL,
        "omada_id": OMADA_ID,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
