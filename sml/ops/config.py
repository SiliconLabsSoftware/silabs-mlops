"""
Configuration module for the sml ops toolkit.

Loads environment variables from a `.env` file and exposes
application-wide configuration values such as ZeroBus endpoints, credentials,
workspace URLs, and table names. This module centralizes all environment-driven
settings so other components can access them in a consistent and secure way.
"""
import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Fallback to standard discovery if not found at root
    load_dotenv()


class Config:
    # ZeroBus configuration
    ZEROBUS_SERVER_ENDPOINT = os.getenv("ZEROBUS_SERVER_ENDPOINT")
    ZEROBUS_WORKSPACE_URL = os.getenv("ZEROBUS_WORKSPACE_URL")
    ZEROBUS_TABLE_NAME = os.getenv("ZEROBUS_TABLE_NAME")
    ZEROBUS_CLIENT_ID = os.getenv("ZEROBUS_CLIENT_ID")
    ZEROBUS_CLIENT_SECRET = os.getenv("ZEROBUS_CLIENT_SECRET")

    @classmethod
    def update(cls, **kwargs):
        """Update configuration values at runtime."""
        for key, value in kwargs.items():
            attr_name = key.upper()
            if hasattr(cls, attr_name):
                setattr(cls, attr_name, value)
            else:
                # Still allow adding new ZEROBUS keys even if not in the default list
                if attr_name.startswith("ZEROBUS_"):
                    setattr(cls, attr_name, value)

