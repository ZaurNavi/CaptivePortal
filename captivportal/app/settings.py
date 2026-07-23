"""
Settings loader for Captive Portal.

Currently loads settings from config.py.
Designed to be extended later without changing the interface.
"""

from app.config import HOST, PORT, DEBUG, VERIFY_SSL, LOG_LEVEL


class Settings:
    """Application settings container."""
    
    def __init__(self):
        self.host = HOST
        self.port = PORT
        self.debug = DEBUG
        self.verify_ssl = VERIFY_SSL
        self.log_level = LOG_LEVEL
    
    def load(self) -> None:
        """
        Load settings from configuration source.
        
        Currently reads from config.py defaults.
        Will be extended to read from files/environment later.
        """
        # For v1.0, settings are already loaded from config.py in __init__
        pass
    
    def get(self, key: str):
        """Get a setting value by key."""
        return getattr(self, key, None)


# Global settings instance
settings = Settings()
