"""
Application configuration using pydantic-settings.

Simple configuration for serial port and PARAM communication.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telemetry UART settings
    telemetry_port: str = Field(
        default="COM3", description="Serial port (e.g., COM3 or /dev/ttyUSB0)"
    )
    baudrate: int = Field(default=115200, description="Serial baud rate")

    # PARAM UART settings
    param_timeout: float = Field(
        default=2.0, description="PARAM request timeout in seconds"
    )

    # Telemetry history
    history_size: int = Field(
        default=1000, description="Max telemetry packets to keep in history"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached singleton)."""
    return Settings()


# Global settings instance for convenience
settings = get_settings()
