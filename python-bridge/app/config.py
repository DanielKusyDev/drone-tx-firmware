"""
Application configuration using pydantic-settings.
"""

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    telemetry_port: str = Field(default="COM3", description="Serial port (e.g., COM3 or /dev/ttyUSB0)")
    baudrate: int = Field(default=115200, description="Serial baud rate (default: 115200)")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached singleton)."""
    return Settings()


# Global settings instance for convenience
settings = get_settings()
