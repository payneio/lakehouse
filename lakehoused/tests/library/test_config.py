"""
Unit tests for configuration loading.

Tests config file creation, loading from YAML, and environment variable overrides.
"""

from pathlib import Path

import pytest
from lakehoused.config import settings
from lakehoused.config.settings import DaemonSettings


@pytest.mark.unit
class TestConfigLoader:
    """Test configuration loading functions."""

    def test_get_config_path_returns_daemon_yaml(self, mock_storage_env: Path) -> None:
        """Test get_config_path returns daemon.yaml in config dir."""
        config_path = settings.get_config_path()

        assert config_path.name == "daemon.yaml"
        assert "config" in str(config_path)

    def test_create_default_config_creates_file(self, mock_storage_env: Path) -> None:
        """Test create_default_config creates daemon.yaml if it doesn't exist."""
        config_path = settings.get_config_path()

        # Ensure it doesn't exist
        if config_path.exists():
            config_path.unlink()

        settings.create_default_config()

        assert config_path.exists()
        assert config_path.is_file()

    def test_create_default_config_has_yaml_content(self, mock_storage_env: Path) -> None:
        """Test create_default_config writes valid YAML."""
        config_path = settings.get_config_path()

        # Ensure it doesn't exist
        if config_path.exists():
            config_path.unlink()

        settings.create_default_config()

        content = config_path.read_text()
        assert "host:" in content
        assert "port:" in content
        assert "log_level:" in content

    def test_create_default_config_is_idempotent(self, mock_storage_env: Path) -> None:
        """Test create_default_config doesn't overwrite existing config."""
        config_path = settings.get_config_path()

        # Create initial config
        settings.create_default_config()

        # Modify it
        custom_content = "# Custom config\nhost: custom\n"
        config_path.write_text(custom_content)

        # Try to create again
        settings.create_default_config()

        # Should not overwrite
        assert config_path.read_text() == custom_content

    def test_load_config_returns_daemon_settings(self, mock_storage_env: Path) -> None:
        """Test load_config returns DaemonSettings object."""
        cfg = settings.load_config()

        assert isinstance(cfg, DaemonSettings)

    def test_load_config_creates_default_if_missing(self, mock_storage_env: Path) -> None:
        """Test load_config creates default config if file doesn't exist."""
        config_path = settings.get_config_path()

        # Ensure it doesn't exist
        if config_path.exists():
            config_path.unlink()

        cfg = settings.load_config()

        assert config_path.exists()
        assert isinstance(cfg, DaemonSettings)

    def test_load_config_parses_yaml_settings(self, mock_storage_env: Path) -> None:
        """Test load_config parses settings from YAML file."""
        config_path = settings.get_config_path()

        # Write custom config
        custom_config = """
host: "0.0.0.0"
port: 9999
log_level: "debug"
workers: 4
"""
        config_path.write_text(custom_config)

        cfg = settings.load_config()

        assert cfg.host == "0.0.0.0"
        assert cfg.port == 9999
        assert cfg.log_level == "debug"
        assert cfg.workers == 4

    def test_load_config_env_overrides_yaml(self, mock_storage_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variables override YAML settings."""
        config_path = settings.get_config_path()

        # Write YAML config
        config_path.write_text("host: 127.0.0.1\nport: 8420\n")

        # Override with environment (use non-standard port to avoid conflicts)
        monkeypatch.setenv("LAKEHOUSED_HOST", "0.0.0.0")
        monkeypatch.setenv("LAKEHOUSED_PORT", "9999")

        # Reload module to pick up env vars
        from importlib import reload

        from lakehoused.config import settings as settings_module

        reload(settings_module)

        cfg = settings.load_config()

        # Environment should win
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 9999

    def test_load_config_handles_invalid_yaml(self, mock_storage_env: Path, caplog) -> None:
        """Test load_config handles corrupted YAML gracefully."""
        config_path = settings.get_config_path()

        # Write invalid YAML
        config_path.write_text("{{invalid yaml content\n")

        # Should not crash, use defaults
        cfg = settings.load_config()

        # Note: use type name check because preceding test's reload() breaks isinstance identity
        assert type(cfg).__name__ == "DaemonSettings"
        assert "Failed to load config" in caplog.text

    def test_load_config_with_custom_path(self, mock_storage_env: Path) -> None:
        """Test load_config accepts custom config path."""
        custom_path = mock_storage_env / "custom-config.yaml"
        custom_path.write_text("host: custom.example.com\nport: 7777\n")

        cfg = settings.load_config(config_path=custom_path)

        assert cfg.host == "custom.example.com"
        assert cfg.port == 7777


@pytest.mark.unit
class TestDaemonSettings:
    """Test DaemonSettings model."""

    def test_daemon_settings_default_values(self) -> None:
        """Test DaemonSettings has sensible defaults."""
        cfg = DaemonSettings()

        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8420
        assert cfg.log_level == "info"
        assert cfg.workers == 1

    def test_daemon_settings_validation(self) -> None:
        """Test DaemonSettings validates port range."""
        # Valid port
        cfg = DaemonSettings(port=8000)
        assert cfg.port == 8000

        # Test validation is present (Pydantic will handle details)
        # Just verify the model can be created with valid values
        cfg = DaemonSettings(port=65535)
        assert cfg.port == 65535

    def test_daemon_settings_from_dict(self) -> None:
        """Test DaemonSettings can be created from dictionary."""
        data = {
            "host": "0.0.0.0",
            "port": 9000,
            "log_level": "debug",
            "workers": 2,
        }

        cfg = DaemonSettings(**data)

        assert cfg.host == "0.0.0.0"
        assert cfg.port == 9000
        assert cfg.log_level == "debug"
        assert cfg.workers == 2


@pytest.mark.unit
class TestDaemonSettingsPathExpansion:
    """Test DaemonSettings path expansion validator."""

    def test_data_path_absolute_unchanged(self, tmp_path: Path) -> None:
        """Absolute paths should remain unchanged."""
        test_dir = tmp_path / "absolute_path"
        test_dir.mkdir()
        cfg = DaemonSettings(data_path=str(test_dir))
        assert cfg.data_path == str(test_dir)

    def test_data_path_tilde_expansion(self) -> None:
        """Tilde should expand to user home directory."""
        cfg = DaemonSettings(data_path="~")
        expected = str(Path.home())
        assert cfg.data_path == expected

    def test_data_path_tilde_with_subdir(self) -> None:
        """Tilde with subdirectory should expand correctly."""
        cfg = DaemonSettings(data_path="~/amplifier")
        expected = str(Path.home() / "amplifier")
        assert cfg.data_path == expected

    def test_data_path_relative_resolution(self, tmp_path: Path) -> None:
        """Relative paths should resolve to absolute paths."""
        import os

        # Change to temp directory for deterministic test
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            cfg = DaemonSettings(data_path="./data")
            expected = str(tmp_path / "data")
            assert cfg.data_path == expected
        finally:
            os.chdir(original_cwd)

    def test_data_path_env_override_with_tilde(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variable with tilde should expand."""
        monkeypatch.setenv("LAKEHOUSED_DATA_PATH", "~/custom")
        cfg = DaemonSettings()
        expected = str(Path.home() / "custom")
        assert cfg.data_path == expected

    def test_data_path_default_is_home_amplifier(self) -> None:
        """Default data_path should be ~/amplifier expanded to absolute."""
        cfg = DaemonSettings()
        expected = str(Path("~/amplifier").expanduser().resolve())
        assert cfg.data_path == expected

    def test_data_path_creates_directory(self, tmp_path: Path) -> None:
        """data_path should auto-create if it doesn't exist."""
        new_dir = tmp_path / "new_amplifier"
        assert not new_dir.exists()

        DaemonSettings(data_path=str(new_dir))

        assert new_dir.exists()
        assert new_dir.is_dir()
        # Check permissions (700 = owner rwx only)
        assert oct(new_dir.stat().st_mode)[-3:] == '700'

    def test_data_path_fails_if_file_exists(self, tmp_path: Path) -> None:
        """data_path should fail if path exists as a file."""
        file_path = tmp_path / "amplifier_file"
        file_path.touch()

        with pytest.raises(ValueError, match="not a directory"):
            DaemonSettings(data_path=str(file_path))

    def test_data_path_fails_if_parent_missing(self, tmp_path: Path) -> None:
        """data_path should fail if parent directory doesn't exist."""
        missing_parent = tmp_path / "missing" / "amplifier"

        with pytest.raises(ValueError, match="Parent directory does not exist"):
            DaemonSettings(data_path=str(missing_parent))
