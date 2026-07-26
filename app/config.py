"""
Application configuration defaults.

This module stores default values for the application.
No Omada-specific settings here.
"""

# Server settings
HOST = "0.0.0.0"
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

# Omada OpenAPI settings
OMADA_URL = "https://192.168.0.222:8043"
OMADA_ID = "fe6867ddf84e4c18c4e280e984e4266d"
CLIENT_ID = "b121eeea3488478f84e2ad0c8e5bb851"       # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
CLIENT_SECRET = "4c94248473cb40c1b399d2732bdbcbe9" # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
