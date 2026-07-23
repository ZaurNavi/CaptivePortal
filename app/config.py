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
VERIFY_SSL = True

# Logging level
LOG_LEVEL = "INFO"

# Omada OpenAPI settings
OMADA_URL = "https://192.168.0.222:8043"
OMADA_ID = "19b675f391ccf9ac0d9c435730051c41"
CLIENT_ID = "b121eeea3488478f84e2ad0c8e5bb851"       # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
CLIENT_SECRET = "4c94248473cb40c1b399d2732bdbcbe9" # <-- ЗАМЕНИ НА РЕАЛЬНЫЙ
