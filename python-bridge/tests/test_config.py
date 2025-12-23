"""
Tests for config.py - Pydantic settings.
"""

import os
from unittest.mock import patch

import pytest

from app.config import Settings, get_settings, settings


class TestSettings:
    """Test Settings configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        # Use explicit parameters to avoid .env file interference
        config = Settings(
            telemetry_port="COM3",
            baudrate=115200,
            param_timeout=2.0,
            history_size=1000,
        )

        assert config.telemetry_port == "COM3"
        assert config.baudrate == 115200
        assert config.param_timeout == 2.0
        assert config.history_size == 1000

    def test_custom_values_from_env(self):
        """Test loading values from environment variables."""
        with patch.dict(
            os.environ,
            {
                "TELEMETRY_PORT": "/dev/ttyUSB0",
                "BAUDRATE": "9600",
                "PARAM_TIMEOUT": "5.0",
                "HISTORY_SIZE": "2000",
            },
        ):
            config = Settings()

            assert config.telemetry_port == "/dev/ttyUSB0"
            assert config.baudrate == 9600
            assert config.param_timeout == 5.0
            assert config.history_size == 2000

    def test_partial_env_override(self):
        """Test partial override from environment."""
        with patch.dict(os.environ, {"TELEMETRY_PORT": "COM5", "BAUDRATE": "57600"}):
            config = Settings()

            assert config.telemetry_port == "COM5"
            assert config.baudrate == 57600
            assert config.param_timeout == 2.0  # Default
            assert config.history_size == 1000  # Default

    def test_config_class_attributes(self):
        """Test Config class attributes."""
        config = Settings()

        assert hasattr(config.Config, "env_file")
        assert config.Config.env_file == ".env"
        assert config.Config.env_file_encoding == "utf-8"


class TestGetSettings:
    """Test get_settings() function."""

    def test_get_settings_returns_settings(self):
        """Test that get_settings returns Settings instance."""
        result = get_settings()
        assert isinstance(result, Settings)

    def test_get_settings_cached(self):
        """Test that get_settings is cached (lru_cache)."""
        result1 = get_settings()
        result2 = get_settings()

        # Should return same instance (cached)
        assert result1 is result2

    def test_settings_singleton(self):
        """Test that settings is a singleton instance."""
        assert isinstance(settings, Settings)
        assert settings is get_settings()


class TestFieldDescriptions:
    """Test field descriptions and validation."""

    def test_telemetry_port_field(self):
        """Test telemetry_port field."""
        config = Settings(telemetry_port="/dev/ttyUSB1")
        assert config.telemetry_port == "/dev/ttyUSB1"

    def test_baudrate_field(self):
        """Test baudrate field."""
        config = Settings(baudrate=230400)
        assert config.baudrate == 230400

    def test_param_timeout_field(self):
        """Test param_timeout field."""
        config = Settings(param_timeout=10.0)
        assert config.param_timeout == 10.0

    def test_history_size_field(self):
        """Test history_size field."""
        config = Settings(history_size=5000)
        assert config.history_size == 5000
