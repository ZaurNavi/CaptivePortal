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
    CAPPORT_ENABLED, CAPPORT_SITE_ID, CAPPORT_PUBLIC_BASE_URL,
    CAPPORT_API_PATH, CAPPORT_LOGIN_PATH,
    CAPPORT_ALLOWED_CLIENT_NETWORKS,
    CAPPORT_CLIENT_CACHE_TTL_SECONDS,
    CAPPORT_FAILURE_CACHE_TTL_SECONDS,
    OMADA_WEBHOOK_ENABLED, OMADA_WEBHOOK_ALLOWED_IPS,
    OMADA_WEBHOOK_AUTH_MODE, OMADA_WEBHOOK_SHARED_SECRET,
    OMADA_WEBHOOK_HEADER_TOKEN, OMADA_WEBHOOK_MAX_BODY_BYTES,
    OMADA_WEBHOOK_LOG_FILE,
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
        "capport_enabled": CAPPORT_ENABLED,
        "capport_site_id": CAPPORT_SITE_ID,
        "capport_public_base_url": CAPPORT_PUBLIC_BASE_URL,
        "capport_api_path": CAPPORT_API_PATH,
        "capport_login_path": CAPPORT_LOGIN_PATH,
        "capport_allowed_client_networks": (
            CAPPORT_ALLOWED_CLIENT_NETWORKS
        ),
        "capport_client_cache_ttl_seconds": (
            CAPPORT_CLIENT_CACHE_TTL_SECONDS
        ),
        "capport_failure_cache_ttl_seconds": (
            CAPPORT_FAILURE_CACHE_TTL_SECONDS
        ),
        "omada_webhook_enabled": OMADA_WEBHOOK_ENABLED,
        "omada_webhook_allowed_ips": OMADA_WEBHOOK_ALLOWED_IPS,
        "omada_webhook_auth_mode": OMADA_WEBHOOK_AUTH_MODE,
        "omada_webhook_shared_secret": (
            OMADA_WEBHOOK_SHARED_SECRET
        ),
        "omada_webhook_header_token": (
            OMADA_WEBHOOK_HEADER_TOKEN
        ),
        "omada_webhook_max_body_bytes": (
            OMADA_WEBHOOK_MAX_BODY_BYTES
        ),
        "omada_webhook_log_file": OMADA_WEBHOOK_LOG_FILE,
        "omada_url": OMADA_URL,
        "omada_id": OMADA_ID,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
