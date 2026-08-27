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
    VISIT_LIFECYCLE_ENABLED, VISIT_LIFECYCLE_DB_PATH,
    VISIT_LIFECYCLE_WEBHOOK_SOURCE,
    VISIT_LIFECYCLE_SCAN_INTERVAL_SECONDS,
    VISIT_LIFECYCLE_RECONCILE_INTERVAL_SECONDS,
    VISIT_LIFECYCLE_MAX_LINE_BYTES,
    VISIT_LIFECYCLE_READER_MAX_LINES_PER_SCAN,
    VISIT_LIFECYCLE_READER_MAX_BYTES_PER_SCAN,
    VISIT_LIFECYCLE_READER_MAX_DURATION_SECONDS,
    VISIT_LIFECYCLE_RECONCILE_BATCH_SIZE,
    VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE,
    VISIT_LIFECYCLE_OFFLINE_MATCH_GRACE_SECONDS,
    VISIT_LIFECYCLE_START_BUSY_TIMEOUT_MS,
    VISIT_LIFECYCLE_START_WRITER_SLOT_WAIT_MS,
    VISIT_LIFECYCLE_READER_WRITER_SLOT_WAIT_MS,
    VISIT_LIFECYCLE_RECONCILIATION_WRITER_SLOT_WAIT_MS,
    VISIT_LIFECYCLE_SQLITE_BUSY_TIMEOUT_MS,
    VISIT_LIFECYCLE_START_MAX_ATTEMPTS,
    VISIT_LIFECYCLE_START_TOTAL_BUDGET_MS,
    VISIT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS,
    VISIT_LIFECYCLE_MAX_OFFLINE_CLOCK_SKEW_SECONDS,
    VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS,
    OBSERVATION_FOUNDATION_ENABLED, OBSERVATION_DB_PATH,
    OBSERVATION_DYNAMIC_RETENTION_DAYS,
    OBSERVATION_CONFIG_RETENTION_DAYS,
    OBSERVATION_CLEANUP_INITIAL_DELAY_SECONDS,
    OBSERVATION_CLEANUP_INTERVAL_SECONDS,
    OBSERVATION_CLEANUP_BATCH_SIZE,
    OBSERVATION_CLEANUP_MAX_DURATION_SECONDS,
    OBSERVATION_SHUTDOWN_TIMEOUT_SECONDS,
    OBSERVATION_CLIENT_ENABLED, OBSERVATION_SITE_IDS,
    OBSERVATION_CLIENT_SSIDS,
    OBSERVATION_CLIENT_INITIAL_DELAY_SECONDS,
    OBSERVATION_CLIENT_INTERVAL_SECONDS,
    OBSERVATION_REQUEST_TIMEOUT_SECONDS,
    OBSERVATION_CLIENT_PAGE_SIZE, OBSERVATION_CLIENT_MAX_PAGES,
    OBSERVATION_CLIENT_MAX_ROWS,
    OBSERVATION_AP_ENABLED, OBSERVATION_AP_INITIAL_DELAY_SECONDS,
    OBSERVATION_AP_INTERVAL_SECONDS,
    OBSERVATION_AP_INVENTORY_INTERVAL_SECONDS,
    OBSERVATION_AP_INVENTORY_MAX_STALE_SECONDS,
    OBSERVATION_AP_CONFIG_INTERVAL_SECONDS,
    OBSERVATION_AP_PAGE_SIZE, OBSERVATION_AP_MAX_PAGES,
    OBSERVATION_AP_MAX_ROWS,
    OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE,
    OBSERVATION_AP_CONFIG_MAX_REQUESTS_PER_CYCLE,
    OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS,
    OBSERVATION_AP_CONFIG_CYCLE_MAX_DURATION_SECONDS,
    OBSERVATION_RATE_MAX_GAP_SECONDS,
    CURRENT_STATE_ENABLED, CURRENT_STATE_DB_PATH,
    CURRENT_STATE_SITE_IDS, CURRENT_STATE_CLIENT_SSIDS_JSON,
    CURRENT_STATE_CLIENT_INITIAL_DELAY_SECONDS,
    CURRENT_STATE_CLIENT_INTERVAL_SECONDS,
    CURRENT_STATE_AP_INITIAL_DELAY_SECONDS,
    CURRENT_STATE_AP_INTERVAL_SECONDS,
    CURRENT_STATE_REQUEST_TIMEOUT_SECONDS,
    CURRENT_STATE_CLIENT_PAGE_SIZE, CURRENT_STATE_CLIENT_MAX_PAGES,
    CURRENT_STATE_CLIENT_MAX_ROWS,
    CURRENT_STATE_AP_PAGE_SIZE, CURRENT_STATE_AP_MAX_PAGES,
    CURRENT_STATE_AP_MAX_ROWS,
    CURRENT_STATE_CLIENT_FRESH_MAX_AGE_SECONDS,
    CURRENT_STATE_CLIENT_STALE_MAX_AGE_SECONDS,
    CURRENT_STATE_AP_FRESH_MAX_AGE_SECONDS,
    CURRENT_STATE_AP_STALE_MAX_AGE_SECONDS,
    CURRENT_STATE_HISTORY_RETENTION_HOURS,
    CURRENT_STATE_HISTORY_MAX_CLIENT_ROWS,
    CURRENT_STATE_CLEANUP_INITIAL_DELAY_SECONDS,
    CURRENT_STATE_CLEANUP_INTERVAL_SECONDS,
    CURRENT_STATE_CLEANUP_MAX_CYCLES_PER_RUN,
    CURRENT_STATE_CLEANUP_MAX_ROWS_PER_TRANSACTION,
    CURRENT_STATE_CLEANUP_MAX_DURATION_SECONDS,
    CURRENT_STATE_SQLITE_BUSY_TIMEOUT_MS,
    CURRENT_STATE_SHUTDOWN_TIMEOUT_SECONDS,
    ANALYTICS_FOUNDATION_ENABLED, ANALYTICS_WIRELESS_ENABLED,
    ANALYTICS_VISIT_ENABLED, ANALYTICS_DEFAULT_LIMIT,
    ANALYTICS_MAX_LIMIT, ANALYTICS_MAX_QUERY_WINDOW_DAYS,
    ANALYTICS_MAX_QUERY_DURATION_SECONDS,
    ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS,
    ANALYTICS_WIRELESS_MIN_SAMPLES,
    ANALYTICS_WIRELESS_MAX_WINDOW_DAYS,
    ANALYTICS_COUNTER_MAX_GAP_SECONDS,
    ANALYTICS_AP_JOIN_MAX_LAG_SECONDS,
    ANALYTICS_RSSI_THRESHOLD_DBM, ANALYTICS_SNR_THRESHOLD_DB,
    ANALYTICS_VISIT_MIN_COHORT_SIZE,
    ANALYTICS_VISIT_MAX_WINDOW_DAYS,
    ANALYTICS_API_ENABLED, ANALYTICS_API_BEARER_TOKEN,
    ANALYTICS_API_ALLOWED_NETWORKS, ANALYTICS_API_ALLOWED_SITE_IDS,
    ANALYTICS_API_MAX_CONCURRENT_REQUESTS,
    ANALYTICS_API_MAX_RESPONSE_BYTES,
    WEB_ADMIN_ENABLED, WEB_ADMIN_USERNAME, WEB_ADMIN_PASSWORD_HASH,
    WEB_ADMIN_ALLOWED_NETWORKS, WEB_ADMIN_ALLOWED_SITE_IDS,
    WEB_ADMIN_DEFAULT_SITE_ID, WEB_ADMIN_REQUIRE_HTTPS,
    WEB_ADMIN_SESSION_IDLE_SECONDS,
    WEB_ADMIN_SESSION_ABSOLUTE_SECONDS,
    WEB_ADMIN_LOGIN_WINDOW_SECONDS, WEB_ADMIN_LOGIN_MAX_FAILURES,
    WEB_ADMIN_LOGIN_LOCK_SECONDS, WEB_ADMIN_PREAUTH_CSRF_TTL_SECONDS,
    WEB_ADMIN_MAX_PREAUTH_STATES, WEB_ADMIN_MAX_SESSIONS,
    WEB_ADMIN_MAX_LOGIN_TRACKERS, WEB_ADMIN_MAX_POST_BYTES,
    WEB_ADMIN_MAX_QUERY_STRING_BYTES, WEB_ADMIN_MAX_USERNAME_CHARS,
    WEB_ADMIN_MAX_PASSWORD_CHARS, WEB_ADMIN_MAX_CSRF_CHARS,
    WEB_ADMIN_MAX_NEXT_CHARS, WEB_ADMIN_MAX_CURSOR_CHARS,
    WEB_ADMIN_MAX_FILTER_CHARS, WEB_ADMIN_MAX_CONCURRENT_QUERIES,
    WEB_ADMIN_MAX_QUERY_DURATION_SECONDS, WEB_ADMIN_MAX_RESPONSE_BYTES,
    WEB_ADMIN_DEVICE_PAGE_SIZE, WEB_ADMIN_VISIT_PAGE_SIZE,
    WEB_ADMIN_OBSERVATION_PAGE_SIZE,
    WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS,
    WEB_ADMIN_HOME_LIVE_ENABLED, WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS,
    WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS,
    WEB_ADMIN_CURRENT_STATE_PAGE_SIZE,
    WEB_ADMIN_HOME_TRAFFIC_ENABLED,
    WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS,
    WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS,
    WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE,
    WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS,
    WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS,
    WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS,
    WEB_ADMIN_HOME_ACTIVITY_ENABLED,
    WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS,
    WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS,
    WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON,
    WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS,
    WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS,
    WEB_ADMIN_HOME_HEALTH_ENABLED,
    WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS,
    WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS,
    WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS,
    CAPPORT_ENABLED, CAPPORT_SITE_ID, CAPPORT_PUBLIC_BASE_URL,
    CAPPORT_API_PATH, CAPPORT_LOGIN_PATH,
    CAPPORT_ALLOWED_CLIENT_NETWORKS,
    CAPPORT_CLIENT_CACHE_TTL_SECONDS,
    CAPPORT_FAILURE_CACHE_TTL_SECONDS,
    OMADA_WEBHOOK_ENABLED, OMADA_WEBHOOK_ALLOWED_IPS,
    OMADA_WEBHOOK_AUTH_MODE, OMADA_WEBHOOK_SHARED_SECRET,
    OMADA_WEBHOOK_HEADER_TOKEN, OMADA_WEBHOOK_MAX_BODY_BYTES,
    OMADA_WEBHOOK_LOG_FILE, OMADA_WEBHOOK_NORMALIZED_LOG_FILE,
    OMADA_WEBHOOK_SITE_ID_MAP_JSON,
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
        "visit_lifecycle_enabled": VISIT_LIFECYCLE_ENABLED,
        "visit_lifecycle_db_path": VISIT_LIFECYCLE_DB_PATH,
        "visit_lifecycle_webhook_source": (
            VISIT_LIFECYCLE_WEBHOOK_SOURCE
        ),
        "visit_lifecycle_scan_interval_seconds": (
            VISIT_LIFECYCLE_SCAN_INTERVAL_SECONDS
        ),
        "visit_lifecycle_reconcile_interval_seconds": (
            VISIT_LIFECYCLE_RECONCILE_INTERVAL_SECONDS
        ),
        "visit_lifecycle_max_line_bytes": (
            VISIT_LIFECYCLE_MAX_LINE_BYTES
        ),
        "visit_lifecycle_reader_max_lines_per_scan": (
            VISIT_LIFECYCLE_READER_MAX_LINES_PER_SCAN
        ),
        "visit_lifecycle_reader_max_bytes_per_scan": (
            VISIT_LIFECYCLE_READER_MAX_BYTES_PER_SCAN
        ),
        "visit_lifecycle_reader_max_duration_seconds": (
            VISIT_LIFECYCLE_READER_MAX_DURATION_SECONDS
        ),
        "visit_lifecycle_reconcile_batch_size": (
            VISIT_LIFECYCLE_RECONCILE_BATCH_SIZE
        ),
        "visit_lifecycle_pending_offline_batch_size": (
            VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE
        ),
        "visit_lifecycle_offline_match_grace_seconds": (
            VISIT_LIFECYCLE_OFFLINE_MATCH_GRACE_SECONDS
        ),
        "visit_lifecycle_start_busy_timeout_ms": (
            VISIT_LIFECYCLE_START_BUSY_TIMEOUT_MS
        ),
        "visit_lifecycle_start_writer_slot_wait_ms": (
            VISIT_LIFECYCLE_START_WRITER_SLOT_WAIT_MS
        ),
        "visit_lifecycle_reader_writer_slot_wait_ms": (
            VISIT_LIFECYCLE_READER_WRITER_SLOT_WAIT_MS
        ),
        "visit_lifecycle_reconciliation_writer_slot_wait_ms": (
            VISIT_LIFECYCLE_RECONCILIATION_WRITER_SLOT_WAIT_MS
        ),
        "visit_lifecycle_sqlite_busy_timeout_ms": (
            VISIT_LIFECYCLE_SQLITE_BUSY_TIMEOUT_MS
        ),
        "visit_lifecycle_start_max_attempts": (
            VISIT_LIFECYCLE_START_MAX_ATTEMPTS
        ),
        "visit_lifecycle_start_total_budget_ms": (
            VISIT_LIFECYCLE_START_TOTAL_BUDGET_MS
        ),
        "visit_lifecycle_shutdown_timeout_seconds": (
            VISIT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS
        ),
        "visit_lifecycle_max_offline_clock_skew_seconds": (
            VISIT_LIFECYCLE_MAX_OFFLINE_CLOCK_SKEW_SECONDS
        ),
        "visit_lifecycle_max_reported_duration_drift_seconds": (
            VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS
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
        "observation_client_enabled": OBSERVATION_CLIENT_ENABLED,
        "observation_site_ids": OBSERVATION_SITE_IDS,
        "observation_client_ssids": OBSERVATION_CLIENT_SSIDS,
        "observation_client_initial_delay_seconds": (
            OBSERVATION_CLIENT_INITIAL_DELAY_SECONDS
        ),
        "observation_client_interval_seconds": (
            OBSERVATION_CLIENT_INTERVAL_SECONDS
        ),
        "observation_request_timeout_seconds": (
            OBSERVATION_REQUEST_TIMEOUT_SECONDS
        ),
        "observation_client_page_size": OBSERVATION_CLIENT_PAGE_SIZE,
        "observation_client_max_pages": OBSERVATION_CLIENT_MAX_PAGES,
        "observation_client_max_rows": OBSERVATION_CLIENT_MAX_ROWS,
        "observation_ap_enabled": OBSERVATION_AP_ENABLED,
        "observation_ap_initial_delay_seconds": (
            OBSERVATION_AP_INITIAL_DELAY_SECONDS
        ),
        "observation_ap_interval_seconds": OBSERVATION_AP_INTERVAL_SECONDS,
        "observation_ap_inventory_interval_seconds": (
            OBSERVATION_AP_INVENTORY_INTERVAL_SECONDS
        ),
        "observation_ap_inventory_max_stale_seconds": (
            OBSERVATION_AP_INVENTORY_MAX_STALE_SECONDS
        ),
        "observation_ap_config_interval_seconds": (
            OBSERVATION_AP_CONFIG_INTERVAL_SECONDS
        ),
        "observation_ap_page_size": OBSERVATION_AP_PAGE_SIZE,
        "observation_ap_max_pages": OBSERVATION_AP_MAX_PAGES,
        "observation_ap_max_rows": OBSERVATION_AP_MAX_ROWS,
        "observation_ap_dynamic_max_requests_per_cycle": (
            OBSERVATION_AP_DYNAMIC_MAX_REQUESTS_PER_CYCLE
        ),
        "observation_ap_config_max_requests_per_cycle": (
            OBSERVATION_AP_CONFIG_MAX_REQUESTS_PER_CYCLE
        ),
        "observation_ap_cycle_max_duration_seconds": (
            OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS
        ),
        "observation_ap_config_cycle_max_duration_seconds": (
            OBSERVATION_AP_CONFIG_CYCLE_MAX_DURATION_SECONDS
        ),
        "observation_rate_max_gap_seconds": OBSERVATION_RATE_MAX_GAP_SECONDS,
        "current_state_enabled": CURRENT_STATE_ENABLED,
        "current_state_db_path": CURRENT_STATE_DB_PATH,
        "current_state_site_ids": CURRENT_STATE_SITE_IDS,
        "current_state_client_ssids_json": CURRENT_STATE_CLIENT_SSIDS_JSON,
        "current_state_client_initial_delay_seconds": (
            CURRENT_STATE_CLIENT_INITIAL_DELAY_SECONDS
        ),
        "current_state_client_interval_seconds": (
            CURRENT_STATE_CLIENT_INTERVAL_SECONDS
        ),
        "current_state_ap_initial_delay_seconds": (
            CURRENT_STATE_AP_INITIAL_DELAY_SECONDS
        ),
        "current_state_ap_interval_seconds": CURRENT_STATE_AP_INTERVAL_SECONDS,
        "current_state_request_timeout_seconds": (
            CURRENT_STATE_REQUEST_TIMEOUT_SECONDS
        ),
        "current_state_client_page_size": CURRENT_STATE_CLIENT_PAGE_SIZE,
        "current_state_client_max_pages": CURRENT_STATE_CLIENT_MAX_PAGES,
        "current_state_client_max_rows": CURRENT_STATE_CLIENT_MAX_ROWS,
        "current_state_ap_page_size": CURRENT_STATE_AP_PAGE_SIZE,
        "current_state_ap_max_pages": CURRENT_STATE_AP_MAX_PAGES,
        "current_state_ap_max_rows": CURRENT_STATE_AP_MAX_ROWS,
        "current_state_client_fresh_max_age_seconds": (
            CURRENT_STATE_CLIENT_FRESH_MAX_AGE_SECONDS
        ),
        "current_state_client_stale_max_age_seconds": (
            CURRENT_STATE_CLIENT_STALE_MAX_AGE_SECONDS
        ),
        "current_state_ap_fresh_max_age_seconds": (
            CURRENT_STATE_AP_FRESH_MAX_AGE_SECONDS
        ),
        "current_state_ap_stale_max_age_seconds": (
            CURRENT_STATE_AP_STALE_MAX_AGE_SECONDS
        ),
        "current_state_history_retention_hours": (
            CURRENT_STATE_HISTORY_RETENTION_HOURS
        ),
        "current_state_history_max_client_rows": (
            CURRENT_STATE_HISTORY_MAX_CLIENT_ROWS
        ),
        "current_state_cleanup_initial_delay_seconds": (
            CURRENT_STATE_CLEANUP_INITIAL_DELAY_SECONDS
        ),
        "current_state_cleanup_interval_seconds": (
            CURRENT_STATE_CLEANUP_INTERVAL_SECONDS
        ),
        "current_state_cleanup_max_cycles_per_run": (
            CURRENT_STATE_CLEANUP_MAX_CYCLES_PER_RUN
        ),
        "current_state_cleanup_max_rows_per_transaction": (
            CURRENT_STATE_CLEANUP_MAX_ROWS_PER_TRANSACTION
        ),
        "current_state_cleanup_max_duration_seconds": (
            CURRENT_STATE_CLEANUP_MAX_DURATION_SECONDS
        ),
        "current_state_sqlite_busy_timeout_ms": (
            CURRENT_STATE_SQLITE_BUSY_TIMEOUT_MS
        ),
        "current_state_shutdown_timeout_seconds": (
            CURRENT_STATE_SHUTDOWN_TIMEOUT_SECONDS
        ),
        "analytics_foundation_enabled": ANALYTICS_FOUNDATION_ENABLED,
        "analytics_wireless_enabled": ANALYTICS_WIRELESS_ENABLED,
        "analytics_visit_enabled": ANALYTICS_VISIT_ENABLED,
        "analytics_default_limit": ANALYTICS_DEFAULT_LIMIT,
        "analytics_max_limit": ANALYTICS_MAX_LIMIT,
        "analytics_max_query_window_days": (
            ANALYTICS_MAX_QUERY_WINDOW_DAYS
        ),
        "analytics_max_query_duration_seconds": (
            ANALYTICS_MAX_QUERY_DURATION_SECONDS
        ),
        "analytics_quality_gap_threshold_seconds": (
            ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
        ),
        "analytics_wireless_min_samples": (
            ANALYTICS_WIRELESS_MIN_SAMPLES
        ),
        "analytics_wireless_max_window_days": (
            ANALYTICS_WIRELESS_MAX_WINDOW_DAYS
        ),
        "analytics_counter_max_gap_seconds": (
            ANALYTICS_COUNTER_MAX_GAP_SECONDS
        ),
        "analytics_ap_join_max_lag_seconds": (
            ANALYTICS_AP_JOIN_MAX_LAG_SECONDS
        ),
        "analytics_rssi_threshold_dbm": ANALYTICS_RSSI_THRESHOLD_DBM,
        "analytics_snr_threshold_db": ANALYTICS_SNR_THRESHOLD_DB,
        "analytics_visit_min_cohort_size": (
            ANALYTICS_VISIT_MIN_COHORT_SIZE
        ),
        "analytics_visit_max_window_days": (
            ANALYTICS_VISIT_MAX_WINDOW_DAYS
        ),
        "analytics_api_enabled": ANALYTICS_API_ENABLED,
        "analytics_api_bearer_token": ANALYTICS_API_BEARER_TOKEN,
        "analytics_api_allowed_networks": (
            ANALYTICS_API_ALLOWED_NETWORKS
        ),
        "analytics_api_allowed_site_ids": (
            ANALYTICS_API_ALLOWED_SITE_IDS
        ),
        "analytics_api_max_concurrent_requests": (
            ANALYTICS_API_MAX_CONCURRENT_REQUESTS
        ),
        "analytics_api_max_response_bytes": (
            ANALYTICS_API_MAX_RESPONSE_BYTES
        ),
        "web_admin_enabled": WEB_ADMIN_ENABLED,
        "web_admin_username": WEB_ADMIN_USERNAME,
        "web_admin_password_hash": WEB_ADMIN_PASSWORD_HASH,
        "web_admin_allowed_networks": WEB_ADMIN_ALLOWED_NETWORKS,
        "web_admin_allowed_site_ids": WEB_ADMIN_ALLOWED_SITE_IDS,
        "web_admin_default_site_id": WEB_ADMIN_DEFAULT_SITE_ID,
        "web_admin_require_https": WEB_ADMIN_REQUIRE_HTTPS,
        "web_admin_session_idle_seconds": WEB_ADMIN_SESSION_IDLE_SECONDS,
        "web_admin_session_absolute_seconds": (
            WEB_ADMIN_SESSION_ABSOLUTE_SECONDS
        ),
        "web_admin_login_window_seconds": WEB_ADMIN_LOGIN_WINDOW_SECONDS,
        "web_admin_login_max_failures": WEB_ADMIN_LOGIN_MAX_FAILURES,
        "web_admin_login_lock_seconds": WEB_ADMIN_LOGIN_LOCK_SECONDS,
        "web_admin_preauth_csrf_ttl_seconds": (
            WEB_ADMIN_PREAUTH_CSRF_TTL_SECONDS
        ),
        "web_admin_max_preauth_states": WEB_ADMIN_MAX_PREAUTH_STATES,
        "web_admin_max_sessions": WEB_ADMIN_MAX_SESSIONS,
        "web_admin_max_login_trackers": WEB_ADMIN_MAX_LOGIN_TRACKERS,
        "web_admin_max_post_bytes": WEB_ADMIN_MAX_POST_BYTES,
        "web_admin_max_query_string_bytes": (
            WEB_ADMIN_MAX_QUERY_STRING_BYTES
        ),
        "web_admin_max_username_chars": WEB_ADMIN_MAX_USERNAME_CHARS,
        "web_admin_max_password_chars": WEB_ADMIN_MAX_PASSWORD_CHARS,
        "web_admin_max_csrf_chars": WEB_ADMIN_MAX_CSRF_CHARS,
        "web_admin_max_next_chars": WEB_ADMIN_MAX_NEXT_CHARS,
        "web_admin_max_cursor_chars": WEB_ADMIN_MAX_CURSOR_CHARS,
        "web_admin_max_filter_chars": WEB_ADMIN_MAX_FILTER_CHARS,
        "web_admin_max_concurrent_queries": (
            WEB_ADMIN_MAX_CONCURRENT_QUERIES
        ),
        "web_admin_max_query_duration_seconds": (
            WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
        ),
        "web_admin_max_response_bytes": WEB_ADMIN_MAX_RESPONSE_BYTES,
        "web_admin_device_page_size": WEB_ADMIN_DEVICE_PAGE_SIZE,
        "web_admin_visit_page_size": WEB_ADMIN_VISIT_PAGE_SIZE,
        "web_admin_observation_page_size": (
            WEB_ADMIN_OBSERVATION_PAGE_SIZE
        ),
        "web_admin_observation_max_window_hours": (
            WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS
        ),
        "web_admin_home_live_enabled": WEB_ADMIN_HOME_LIVE_ENABLED,
        "web_admin_home_live_refresh_seconds": WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS,
        "web_admin_home_live_request_timeout_seconds": WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS,
        "web_admin_current_state_page_size": WEB_ADMIN_CURRENT_STATE_PAGE_SIZE,
        "web_admin_home_traffic_enabled": WEB_ADMIN_HOME_TRAFFIC_ENABLED,
        "web_admin_home_traffic_refresh_seconds": WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS,
        "web_admin_home_traffic_request_timeout_seconds": WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS,
        "web_admin_home_traffic_page_size": WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE,
        "web_admin_home_traffic_fresh_max_age_seconds": WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS,
        "web_admin_home_traffic_stale_max_age_seconds": WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS,
        "web_admin_home_traffic_max_ap_skew_seconds": WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS,
        "web_admin_home_activity_enabled": WEB_ADMIN_HOME_ACTIVITY_ENABLED,
        "web_admin_home_activity_refresh_seconds": WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS,
        "web_admin_home_activity_request_timeout_seconds": WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS,
        "web_admin_home_activity_site_context_json": WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON,
        "web_admin_home_activity_traffic_fresh_max_age_seconds": WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS,
        "web_admin_home_activity_traffic_stale_max_age_seconds": WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS,
        "web_admin_home_health_enabled": WEB_ADMIN_HOME_HEALTH_ENABLED,
        "web_admin_home_health_refresh_seconds": WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS,
        "web_admin_home_health_request_timeout_seconds": WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS,
        "web_admin_home_health_auth_evidence_max_age_seconds": WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS,
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
        "omada_webhook_site_id_map_json": (
            OMADA_WEBHOOK_SITE_ID_MAP_JSON
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
