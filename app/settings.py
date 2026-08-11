"""
Settings module.

Currently reads settings from config.py.
Designed to be extended in future versions to read from files or environment.
"""

from app.config import (
    HOST, PORT, DEBUG, VERIFY_SSL, LOG_LEVEL,
    PORTAL_COUNTER_ENABLED, PORTAL_COUNTER_DB_PATH,
    PORTAL_COUNTER_TIMEZONE, PORTAL_COUNTER_API_ENABLED,
    PUBLIC_TRAFFIC_COUNTER_ENABLED, PUBLIC_TRAFFIC_SSID,
    PUBLIC_TRAFFIC_DB_PATH, PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS,
    PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS,
    AUTH_TELEMETRY_ENABLED, AUTH_TELEMETRY_LOG_PATH,
    AUTH_TELEMETRY_LEVEL, AUTH_TELEMETRY_SCHEMA_VERSION,
    AUTH_TELEMETRY_ROTATION_MAX_BYTES,
    AUTH_TELEMETRY_ROTATION_BACKUP_COUNT,
    VISITOR_SNAPSHOT_ENABLED, VISITOR_SNAPSHOT_LOG_FILE,
    VISITOR_SNAPSHOT_MAX_WORKERS, VISITOR_SNAPSHOT_MAX_PENDING,
    VISITOR_SNAPSHOT_MAX_JOB_AGE_SECONDS,
    VISITOR_SNAPSHOT_REQUEST_TIMEOUT_SECONDS,
    VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS,
    VISITOR_SNAPSHOT_ROTATION_MAX_BYTES,
    VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT,
    VISITOR_SNAPSHOT_SHUTDOWN_TIMEOUT_SECONDS,
    VISITOR_REGISTRY_ENABLED, VISITOR_REGISTRY_DB_PATH,
    VISITOR_REGISTRY_SCAN_INTERVAL_SECONDS,
    VISITOR_REGISTRY_SHUTDOWN_TIMEOUT_SECONDS,
    VISITOR_REGISTRY_MAX_LINE_BYTES,
    OBSERVATION_FOUNDATION_ENABLED, OBSERVATION_DB_PATH,
    OBSERVATION_DYNAMIC_RETENTION_DAYS,
    OBSERVATION_CONFIG_RETENTION_DAYS,
    OBSERVATION_CLEANUP_INITIAL_DELAY_SECONDS,
    OBSERVATION_CLEANUP_INTERVAL_SECONDS,
    OBSERVATION_CLEANUP_BATCH_SIZE,
    OBSERVATION_CLEANUP_MAX_DURATION_SECONDS,
    OBSERVATION_SHUTDOWN_TIMEOUT_SECONDS,
    CAPPORT_ENABLED, CAPPORT_SITE_ID, CAPPORT_PUBLIC_BASE_URL,
    CAPPORT_API_PATH, CAPPORT_LOGIN_PATH,
    CAPPORT_ALLOWED_CLIENT_NETWORKS,
    CAPPORT_CLIENT_CACHE_TTL_SECONDS,
    CAPPORT_FAILURE_CACHE_TTL_SECONDS,
    OMADA_WEBHOOK_ENABLED, OMADA_WEBHOOK_ALLOWED_IPS,
    OMADA_WEBHOOK_AUTH_MODE, OMADA_WEBHOOK_SHARED_SECRET,
    OMADA_WEBHOOK_HEADER_TOKEN, OMADA_WEBHOOK_MAX_BODY_BYTES,
    OMADA_WEBHOOK_LOG_FILE, OMADA_WEBHOOK_NORMALIZED_LOG_FILE,
    OMADA_URL, OMADA_ID, CLIENT_ID, CLIENT_SECRET,
    # pending session cleaner constants
    PENDING_SESSION_CLEANER_ENABLED,
    PENDING_SESSION_CLEANER_SSIDS,
    PENDING_SESSION_CLEANER_INITIAL_DELAY_SECONDS,
    PENDING_SESSION_CLEANER_SCAN_INTERVAL_SECONDS,
    PENDING_SESSION_CLEANER_MAX_SCAN_DURATION_SECONDS,
    PENDING_SESSION_CLEANER_MIN_UPTIME_SECONDS,
    PENDING_SESSION_CLEANER_PORTAL_GRACE_SECONDS,
    PENDING_SESSION_CLEANER_UPTIME_REGRESSION_TOLERANCE_SECONDS,
    PENDING_SESSION_CLEANER_REQUEST_TIMEOUT_SECONDS,
    PENDING_SESSION_CLEANER_GET_RETRY_DELAYS_SECONDS,
    PENDING_SESSION_CLEANER_VERIFY_DELAYS_SECONDS,
    PENDING_SESSION_CLEANER_PAGE_SIZE,
    PENDING_SESSION_CLEANER_MAX_PAGES,
    PENDING_SESSION_CLEANER_MAX_CLIENTS,
    PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN,
    PENDING_SESSION_CLEANER_ACTION_COOLDOWN_SECONDS,
    PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_MAC_PER_HOUR,
    PENDING_SESSION_CLEANER_LOG_FILE,
    PENDING_SESSION_CLEANER_ROTATION_MAX_BYTES,
    PENDING_SESSION_CLEANER_ROTATION_BACKUP_COUNT,
    PENDING_SESSION_CLEANER_SHUTDOWN_TIMEOUT_SECONDS,
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
        "public_traffic_counter_enabled": (
            PUBLIC_TRAFFIC_COUNTER_ENABLED
        ),
        "public_traffic_ssid": PUBLIC_TRAFFIC_SSID,
        "public_traffic_db_path": PUBLIC_TRAFFIC_DB_PATH,
        "public_traffic_scan_interval_seconds": (
            PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS
        ),
        "public_traffic_frontend_refresh_seconds": (
            PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS
        ),
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
        "visitor_snapshot_enabled": VISITOR_SNAPSHOT_ENABLED,
        "visitor_snapshot_log_file": VISITOR_SNAPSHOT_LOG_FILE,
        "visitor_snapshot_max_workers": (
            VISITOR_SNAPSHOT_MAX_WORKERS
        ),
        "visitor_snapshot_max_pending": (
            VISITOR_SNAPSHOT_MAX_PENDING
        ),
        "visitor_snapshot_max_job_age_seconds": (
            VISITOR_SNAPSHOT_MAX_JOB_AGE_SECONDS
        ),
        "visitor_snapshot_request_timeout_seconds": (
            VISITOR_SNAPSHOT_REQUEST_TIMEOUT_SECONDS
        ),
        "visitor_snapshot_retry_delays_seconds": (
            VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS
        ),
        "visitor_snapshot_rotation_max_bytes": (
            VISITOR_SNAPSHOT_ROTATION_MAX_BYTES
        ),
        "visitor_snapshot_rotation_backup_count": (
            VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT
        ),
        "visitor_snapshot_shutdown_timeout_seconds": (
            VISITOR_SNAPSHOT_SHUTDOWN_TIMEOUT_SECONDS
        ),
        "visitor_registry_enabled": VISITOR_REGISTRY_ENABLED,
        "visitor_registry_db_path": VISITOR_REGISTRY_DB_PATH,
        "visitor_registry_scan_interval_seconds": (
            VISITOR_REGISTRY_SCAN_INTERVAL_SECONDS
        ),
        "visitor_registry_shutdown_timeout_seconds": (
            VISITOR_REGISTRY_SHUTDOWN_TIMEOUT_SECONDS
        ),
        "visitor_registry_max_line_bytes": (
            VISITOR_REGISTRY_MAX_LINE_BYTES
        ),
        "observation_foundation_enabled": (
            OBSERVATION_FOUNDATION_ENABLED
        ),
        "observation_db_path": OBSERVATION_DB_PATH,
        "observation_dynamic_retention_days": (
            OBSERVATION_DYNAMIC_RETENTION_DAYS
        ),
        "observation_config_retention_days": (
            OBSERVATION_CONFIG_RETENTION_DAYS
        ),
        "observation_cleanup_initial_delay_seconds": (
            OBSERVATION_CLEANUP_INITIAL_DELAY_SECONDS
        ),
        "observation_cleanup_interval_seconds": (
            OBSERVATION_CLEANUP_INTERVAL_SECONDS
        ),
        "observation_cleanup_batch_size": (
            OBSERVATION_CLEANUP_BATCH_SIZE
        ),
        "observation_cleanup_max_duration_seconds": (
            OBSERVATION_CLEANUP_MAX_DURATION_SECONDS
        ),
        "observation_shutdown_timeout_seconds": (
            OBSERVATION_SHUTDOWN_TIMEOUT_SECONDS
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
        "omada_webhook_normalized_log_file": (
            OMADA_WEBHOOK_NORMALIZED_LOG_FILE
        ),
        "omada_url": OMADA_URL,
        "omada_id": OMADA_ID,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        # Pending Session Cleaner settings (raw strings from config.py; parsed by PendingSessionCleanerConfig)
        "pending_session_cleaner_enabled": PENDING_SESSION_CLEANER_ENABLED,
        "pending_session_cleaner_ssids": PENDING_SESSION_CLEANER_SSIDS,
        "pending_session_cleaner_initial_delay_seconds": PENDING_SESSION_CLEANER_INITIAL_DELAY_SECONDS,
        "pending_session_cleaner_scan_interval_seconds": PENDING_SESSION_CLEANER_SCAN_INTERVAL_SECONDS,
        "pending_session_cleaner_max_scan_duration_seconds": PENDING_SESSION_CLEANER_MAX_SCAN_DURATION_SECONDS,
        "pending_session_cleaner_min_uptime_seconds": PENDING_SESSION_CLEANER_MIN_UPTIME_SECONDS,
        "pending_session_cleaner_portal_grace_seconds": PENDING_SESSION_CLEANER_PORTAL_GRACE_SECONDS,
        "pending_session_cleaner_uptime_regression_tolerance_seconds": PENDING_SESSION_CLEANER_UPTIME_REGRESSION_TOLERANCE_SECONDS,
        "pending_session_cleaner_request_timeout_seconds": PENDING_SESSION_CLEANER_REQUEST_TIMEOUT_SECONDS,
        "pending_session_cleaner_get_retry_delays_seconds": PENDING_SESSION_CLEANER_GET_RETRY_DELAYS_SECONDS,
        "pending_session_cleaner_verify_delays_seconds": PENDING_SESSION_CLEANER_VERIFY_DELAYS_SECONDS,
        "pending_session_cleaner_page_size": PENDING_SESSION_CLEANER_PAGE_SIZE,
        "pending_session_cleaner_max_pages": PENDING_SESSION_CLEANER_MAX_PAGES,
        "pending_session_cleaner_max_clients": PENDING_SESSION_CLEANER_MAX_CLIENTS,
        "pending_session_cleaner_max_actions_per_scan": PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN,
        "pending_session_cleaner_action_cooldown_seconds": PENDING_SESSION_CLEANER_ACTION_COOLDOWN_SECONDS,
        "pending_session_cleaner_max_actions_per_mac_per_hour": PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_MAC_PER_HOUR,
        "pending_session_cleaner_log_file": PENDING_SESSION_CLEANER_LOG_FILE,
        "pending_session_cleaner_rotation_max_bytes": PENDING_SESSION_CLEANER_ROTATION_MAX_BYTES,
        "pending_session_cleaner_rotation_backup_count": PENDING_SESSION_CLEANER_ROTATION_BACKUP_COUNT,
        "pending_session_cleaner_shutdown_timeout_seconds": PENDING_SESSION_CLEANER_SHUTDOWN_TIMEOUT_SECONDS,
    }
