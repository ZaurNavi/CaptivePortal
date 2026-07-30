"""
Application configuration defaults.

This module stores default values for the application.
"""

import os

# Server settings
HOST = "127.0.0.1"
PORT = 8088

# Debug mode
DEBUG = False

# SSL verification
VERIFY_SSL = False

# Logging level
LOG_LEVEL = "INFO"

# Public Portal Open Counter
PORTAL_COUNTER_ENABLED = True
PORTAL_COUNTER_DB_PATH = "/opt/CaptivePortal/data/portal_counter.db"
PORTAL_COUNTER_TIMEZONE = "Asia/Baku"
PORTAL_COUNTER_API_ENABLED = True

# Public completed-session traffic counter
PUBLIC_TRAFFIC_COUNTER_ENABLED = os.getenv(
    "PUBLIC_TRAFFIC_COUNTER_ENABLED",
    "true",
)
PUBLIC_TRAFFIC_SSID = os.getenv(
    "PUBLIC_TRAFFIC_SSID",
    "Zefer_Parki",
)
PUBLIC_TRAFFIC_DB_PATH = os.getenv(
    "PUBLIC_TRAFFIC_DB_PATH",
    "/opt/CaptivePortal/data/public_traffic.sqlite3",
)
PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS = os.getenv(
    "PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS",
    "10",
)
PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS = os.getenv(
    "PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS",
    "60",
)

# Authorization Technical Logging
AUTH_TELEMETRY_ENABLED = True
AUTH_TELEMETRY_LOG_PATH = "/opt/CaptivePortal/logs/auth_telemetry.log"
AUTH_TELEMETRY_LEVEL = "INFO"
AUTH_TELEMETRY_SCHEMA_VERSION = 1
AUTH_TELEMETRY_ROTATION_MAX_BYTES = 52428800
AUTH_TELEMETRY_ROTATION_BACKUP_COUNT = 10

# Authorized Client Snapshot Collector (safe disabled default)
VISITOR_SNAPSHOT_ENABLED = os.getenv(
    "VISITOR_SNAPSHOT_ENABLED",
    "false",
)
VISITOR_SNAPSHOT_LOG_FILE = os.getenv(
    "VISITOR_SNAPSHOT_LOG_FILE",
    "/opt/CaptivePortal/logs/visitor_snapshots.log",
)
VISITOR_SNAPSHOT_MAX_WORKERS = os.getenv(
    "VISITOR_SNAPSHOT_MAX_WORKERS",
    "2",
)
VISITOR_SNAPSHOT_MAX_PENDING = os.getenv(
    "VISITOR_SNAPSHOT_MAX_PENDING",
    "100",
)
VISITOR_SNAPSHOT_MAX_JOB_AGE_SECONDS = os.getenv(
    "VISITOR_SNAPSHOT_MAX_JOB_AGE_SECONDS",
    "30",
)
VISITOR_SNAPSHOT_REQUEST_TIMEOUT_SECONDS = os.getenv(
    "VISITOR_SNAPSHOT_REQUEST_TIMEOUT_SECONDS",
    "5",
)
VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS = os.getenv(
    "VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS",
    "2,5",
)
VISITOR_SNAPSHOT_ROTATION_MAX_BYTES = os.getenv(
    "VISITOR_SNAPSHOT_ROTATION_MAX_BYTES",
    "52428800",
)
VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT = os.getenv(
    "VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT",
    "20",
)
VISITOR_SNAPSHOT_SHUTDOWN_TIMEOUT_SECONDS = os.getenv(
    "VISITOR_SNAPSHOT_SHUTDOWN_TIMEOUT_SECONDS",
    "90",
)

# RFC 8908/8910 CAPPORT
CAPPORT_ENABLED = True
CAPPORT_SITE_ID = "6a64f17630da7c70d232187a"
CAPPORT_PUBLIC_BASE_URL = "https://captivportal-navi.duckdns.org"
CAPPORT_API_PATH = "/capport/api"
CAPPORT_LOGIN_PATH = "/capport/login"
CAPPORT_ALLOWED_CLIENT_NETWORKS = ("192.168.1.0/24",)
CAPPORT_CLIENT_CACHE_TTL_SECONDS = 2
CAPPORT_FAILURE_CACHE_TTL_SECONDS = 2

# Omada webhook receiver
OMADA_WEBHOOK_ENABLED = os.getenv(
    "OMADA_WEBHOOK_ENABLED",
    "false",
)
OMADA_WEBHOOK_ALLOWED_IPS = os.getenv(
    "OMADA_WEBHOOK_ALLOWED_IPS",
    "",
)
OMADA_WEBHOOK_AUTH_MODE = os.getenv(
    "OMADA_WEBHOOK_AUTH_MODE",
    "ip_only",
)
OMADA_WEBHOOK_SHARED_SECRET = os.getenv(
    "OMADA_WEBHOOK_SHARED_SECRET",
    "",
)
OMADA_WEBHOOK_HEADER_TOKEN = os.getenv(
    "OMADA_WEBHOOK_HEADER_TOKEN",
    "",
)
OMADA_WEBHOOK_MAX_BODY_BYTES = os.getenv(
    "OMADA_WEBHOOK_MAX_BODY_BYTES",
    "1048576",
)
OMADA_WEBHOOK_LOG_FILE = os.getenv(
    "OMADA_WEBHOOK_LOG_FILE",
    "/opt/CaptivePortal/logs/omada_webhook.log",
)
OMADA_WEBHOOK_NORMALIZED_LOG_FILE = os.getenv(
    "OMADA_WEBHOOK_NORMALIZED_LOG_FILE",
    "/opt/CaptivePortal/logs/omada_webhook_normalized.log",
)

# Omada OpenAPI settings
OMADA_URL = "https://192.168.0.222:8043"
OMADA_ID = "fe6867ddf84e4c18c4e280e984e4266d"
CLIENT_ID = "b121eeea3488478f84e2ad0c8e5bb851"       # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
CLIENT_SECRET = "4c94248473cb40c1b399d2732bdbcbe9" # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
