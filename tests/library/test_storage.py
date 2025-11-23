"""
Unit tests for storage layer (paths and json_store).

Tests path resolution, JSON persistence, atomic writes, and retry logic.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from amplifier_library.storage import json_store
from amplifier_library.storage import paths


@pytest.mark.unit
class TestPaths:
    """Test path resolution functions."""

    def test_get_root_dir_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_root_dir returns default /data when env var not set."""
        monkeypatch.delenv("AMPLIFIERD_ROOT", raising=False)
        root = paths.get_root_dir()
        assert root == Path(".amplifierd").resolve()

    def test_get_root_dir_custom(self, mock_storage_env: Path) -> None:
        """Test get_root_dir respects AMPLIFIERD_ROOT environment variable."""
        root = paths.get_root_dir()
        assert root == mock_storage_env

    def test_get_config_dir_creates_directory(self, mock_storage_env: Path) -> None:
        """Test get_config_dir creates directory if it doesn't exist."""
        config_dir = paths.get_config_dir()
        assert config_dir.exists()
        assert config_dir.is_dir()
        assert config_dir.name == "config"
        assert "config" in str(config_dir)

    def test_get_share_dir_creates_directory(self, mock_storage_env: Path) -> None:
        """Test get_share_dir creates directory if it doesn't exist."""
        share_dir = paths.get_share_dir()
        assert share_dir.exists()
        assert share_dir.is_dir()
        assert share_dir.name == "share"
        assert "share" in str(share_dir)

    def test_get_state_dir_creates_directory(self, mock_storage_env: Path) -> None:
        """Test get_state_dir creates directory if it doesn't exist."""
        state_dir = paths.get_state_dir()
        assert state_dir.exists()
        assert state_dir.is_dir()
        assert state_dir.name == "state"
        assert "state" in str(state_dir)

    def test_get_log_dir_creates_directory(self, mock_storage_env: Path) -> None:
        """Test get_log_dir creates directory if it doesn't exist."""
        log_dir = paths.get_log_dir()
        assert log_dir.exists()
        assert log_dir.is_dir()
        assert log_dir.name == "amplifierd"
        assert "log" in str(log_dir)

    def test_paths_are_absolute(self, mock_storage_env: Path) -> None:
        """Test all path functions return absolute paths."""
        assert paths.get_root_dir().is_absolute()
        assert paths.get_config_dir().is_absolute()
        assert paths.get_share_dir().is_absolute()
        assert paths.get_state_dir().is_absolute()
        assert paths.get_log_dir().is_absolute()


@pytest.mark.unit
class TestJsonStore:
    """Test JSON storage operations."""

    def test_save_and_load_json(self, mock_storage_env: Path) -> None:
        """Test basic save and load operations."""
        test_data = {"id": "test-123", "name": "Test Session", "count": 42}

        json_store.save_json("test-key", test_data, category="test")
        loaded = json_store.load_json("test-key", category="test")

        assert loaded == test_data
        assert loaded["id"] == "test-123"
        assert loaded["count"] == 42

    def test_save_creates_category_directory(self, mock_storage_env: Path) -> None:
        """Test save_json creates category directory if it doesn't exist."""
        json_store.save_json("test", {"data": "value"}, category="newcat")

        cat_dir = paths.get_share_dir() / "newcat"
        assert cat_dir.exists()
        assert cat_dir.is_dir()

    def test_load_nonexistent_raises_error(self, mock_storage_env: Path) -> None:
        """Test load_json raises FileNotFoundError for nonexistent files."""
        with pytest.raises(FileNotFoundError, match="Storage file not found"):
            json_store.load_json("nonexistent-key", category="test")

    def test_save_invalid_key_raises_error(self, mock_storage_env: Path) -> None:
        """Test save_json rejects invalid keys with path separators."""
        with pytest.raises(ValueError, match="Invalid storage key"):
            json_store.save_json("invalid/key", {"data": "value"})

        with pytest.raises(ValueError, match="Invalid storage key"):
            json_store.save_json("invalid\\key", {"data": "value"})

    def test_save_sanitizes_datetime(self, mock_storage_env: Path) -> None:
        """Test save_json converts datetime objects to ISO strings."""
        from datetime import UTC
        from datetime import datetime

        dt = datetime(2025, 1, 20, 12, 0, 0, tzinfo=UTC)
        test_data = {"timestamp": dt, "name": "test"}

        json_store.save_json("datetime-test", test_data, category="test")
        loaded = json_store.load_json("datetime-test", category="test")

        assert isinstance(loaded["timestamp"], str)
        assert loaded["timestamp"] == "2025-01-20T12:00:00+00:00"

    def test_atomic_write_uses_temp_file(self, mock_storage_env: Path) -> None:
        """Test save_json uses atomic write with temp file."""
        json_store.save_json("atomic-test", {"data": "value"}, category="test")

        cat_dir = paths.get_share_dir() / "test"
        final_file = cat_dir / "atomic-test.json"
        temp_file = cat_dir / "atomic-test.json.tmp"

        assert final_file.exists()
        assert not temp_file.exists()  # Temp file should be cleaned up

    def test_list_stored_returns_keys(self, mock_storage_env: Path) -> None:
        """Test list_stored returns all matching keys."""
        json_store.save_json("session-1", {"id": "1"}, category="test")
        json_store.save_json("session-2", {"id": "2"}, category="test")
        json_store.save_json("config-1", {"id": "3"}, category="test")

        # List all
        all_keys = json_store.list_stored("*", category="test")
        assert len(all_keys) == 3
        assert "session-1" in all_keys
        assert "session-2" in all_keys

        # List with pattern
        session_keys = json_store.list_stored("session-*", category="test")
        assert len(session_keys) == 2
        assert "session-1" in session_keys
        assert "config-1" not in session_keys

    def test_delete_stored_removes_file(self, mock_storage_env: Path) -> None:
        """Test delete_stored removes file from disk."""
        json_store.save_json("delete-test", {"data": "value"}, category="test")
        assert json_store.exists("delete-test", category="test")

        json_store.delete_stored("delete-test", category="test")
        assert not json_store.exists("delete-test", category="test")

    def test_delete_nonexistent_raises_error(self, mock_storage_env: Path) -> None:
        """Test delete_stored raises FileNotFoundError for nonexistent files."""
        with pytest.raises(FileNotFoundError, match="Storage file not found"):
            json_store.delete_stored("nonexistent", category="test")

    def test_exists_returns_correct_status(self, mock_storage_env: Path) -> None:
        """Test exists returns True for existing files, False otherwise."""
        assert not json_store.exists("test-exists", category="test")

        json_store.save_json("test-exists", {"data": "value"}, category="test")
        assert json_store.exists("test-exists", category="test")

        json_store.delete_stored("test-exists", category="test")
        assert not json_store.exists("test-exists", category="test")

    def test_exists_with_invalid_key(self, mock_storage_env: Path) -> None:
        """Test exists returns False for invalid keys."""
        assert not json_store.exists("invalid/key", category="test")
        assert not json_store.exists("", category="test")

    def test_retry_on_io_error(self, mock_storage_env: Path) -> None:
        """Test save_json retries on I/O errors (cloud sync scenario)."""
        original_open = open
        call_count = [0]

        def mock_open_with_error(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call fails with errno 5 (I/O error)
                err = OSError("I/O error")
                err.errno = 5
                raise err
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_with_error):
            # Should succeed after retry
            json_store.save_json("retry-test", {"data": "value"}, category="test")

        # Verify retry happened
        assert call_count[0] == 2

        # Verify data was saved correctly
        loaded = json_store.load_json("retry-test", category="test")
        assert loaded["data"] == "value"
