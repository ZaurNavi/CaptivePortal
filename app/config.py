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

# Authorization Technical Logging
AUTH_TELEMETRY_ENABLED = True
AUTH_TELEMETRY_LOG_PATH = "/opt/CaptivePortal/logs/auth_telemetry.log"
AUTH_TELEMETRY_LEVEL = "INFO"
AUTH_TELEMETRY_SCHEMA_VERSION = 1
AUTH_TELEMETRY_ROTATION_MAX_BYTES = 52428800
AUTH_TELEMETRY_ROTATION_BACKUP_COUNT = 10

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

# Omada OpenAPI settings
OMADA_URL = "https://192.168.0.222:8043"
OMADA_ID = "fe6867ddf84e4c18c4e280e984e4266d"
CLIENT_ID = "b121eeea3488478f84e2ad0c8e5bb851"       # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
CLIENT_SECRET = "4c94248473cb40c1b399d2732bdbcbe9" # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
