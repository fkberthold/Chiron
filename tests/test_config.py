"""Tests for configuration management."""

from pathlib import Path

import pytest

from chiron.config import ChironConfig, get_config


def test_config_has_data_dir() -> None:
    """Config should have a data directory path."""
    config = get_config()
    assert config.data_dir is not None
    assert isinstance(config.data_dir, Path)


def test_config_data_dir_default() -> None:
    """Default data dir should be ~/.chiron."""
    config = get_config()
    assert config.data_dir == Path.home() / ".chiron"


def test_config_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config should respect CHIRON_DATA_DIR env var."""
    monkeypatch.setenv("CHIRON_DATA_DIR", "/tmp/chiron-test")
    # Force reload of config
    config = ChironConfig()
    assert config.data_dir == Path("/tmp/chiron-test")


def test_config_has_database_path() -> None:
    """Config should provide SQLite database path."""
    config = get_config()
    assert config.database_path.name == "chiron.db"
    assert config.database_path.parent == config.data_dir


def test_config_has_mcp_server_settings() -> None:
    """Config should have MCP server host and port."""
    config = get_config()
    assert config.mcp_host == "localhost"
    assert isinstance(config.mcp_port, int)
    assert 1024 <= config.mcp_port <= 65535
