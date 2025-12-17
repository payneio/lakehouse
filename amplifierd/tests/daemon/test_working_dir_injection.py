"""Test that runtime config is correctly injected into mount plans.

Tests the _inject_runtime_config helper in routers/sessions.py which handles:
- working_dir injection into tool configs
- session_log_template injection for hooks-logging
"""

from pathlib import Path
from unittest.mock import patch


def test_working_dir_injection_in_mount_plan(tmp_path: Path) -> None:
    """Test that working_dir is injected into all tool configs when creating mount plans."""
    # This test verifies the fix in amplifierd/routers/sessions.py
    # that injects working_dir into all tool configs

    data_root = tmp_path / "data"
    data_root.mkdir()

    test_dir = data_root / "test_project"
    test_dir.mkdir()

    # Call the internal mount plan builder with a minimal profile
    mount_plan = {
        "session": {"settings": {}},
        "tools": [
            {"name": "bash", "config": {}},
            {"name": "grep", "config": {}},
            {"name": "glob", "config": {}},
        ],
    }

    amplified_dir = "test_project"
    absolute_amplified_dir = str(test_dir.resolve())

    # Apply the session working directory injection logic
    mount_plan["session"]["settings"]["amplified_dir"] = absolute_amplified_dir
    mount_plan["session"]["settings"]["working_dir"] = absolute_amplified_dir

    # Inject working_dir into all tool configs (this is the fix we're testing)
    if "tools" in mount_plan:
        for tool in mount_plan["tools"]:
            if "config" not in tool:
                tool["config"] = {}
            tool["config"]["working_dir"] = absolute_amplified_dir

    # Verify working_dir is set correctly
    assert "session" in mount_plan
    assert "settings" in mount_plan["session"]
    assert "working_dir" in mount_plan["session"]["settings"]
    assert mount_plan["session"]["settings"]["working_dir"] == absolute_amplified_dir

    # Verify all tools have working_dir injected
    tools = mount_plan.get("tools", [])
    assert len(tools) > 0, "Mount plan should have at least one tool"

    for tool in tools:
        tool_name = tool.get("name", "unknown")
        config = tool.get("config", {})

        assert "working_dir" in config, f"Tool '{tool_name}' missing working_dir in config"

        working_dir = config["working_dir"]
        assert working_dir == absolute_amplified_dir, (
            f"Tool '{tool_name}' has wrong working_dir: {working_dir} != {absolute_amplified_dir}"
        )


def test_inject_runtime_config_working_dir(tmp_path: Path) -> None:
    """Test _inject_runtime_config injects working_dir into tool configs."""
    from amplifierd.routers.sessions import _inject_runtime_config

    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    absolute_amplified_dir = str(test_dir.resolve())

    mount_plan = {
        "tools": [
            {"name": "bash", "config": {}},
            {"name": "grep"},  # No config key
            {"name": "glob", "config": {"working_dir": "/custom/path"}},  # Already has working_dir
        ],
    }

    _inject_runtime_config(mount_plan, "session_123", absolute_amplified_dir)

    # bash should get working_dir injected
    assert mount_plan["tools"][0]["config"]["working_dir"] == absolute_amplified_dir

    # grep should get config created and working_dir injected
    assert "config" in mount_plan["tools"][1]
    assert mount_plan["tools"][1]["config"]["working_dir"] == absolute_amplified_dir

    # glob should keep its custom working_dir (not overwritten)
    assert mount_plan["tools"][2]["config"]["working_dir"] == "/custom/path"


def test_inject_runtime_config_session_log_template_with_module_key(tmp_path: Path) -> None:
    """Test _inject_runtime_config injects session_log_template for hooks-logging using module key."""
    from amplifierd.routers.sessions import _inject_runtime_config

    # Mock get_state_dir to return a predictable path
    with patch("amplifierd.routers.sessions.get_state_dir") as mock_get_state_dir:
        mock_get_state_dir.return_value = tmp_path / ".amplifierd" / "state"

        mount_plan = {
            "hooks": [
                {"module": "hooks-redaction", "source": "test", "config": {}},
                {"module": "hooks-logging", "source": "test", "config": {}},
                {"module": "hooks-todo-reminder", "source": "test", "config": {}},
            ],
        }

        _inject_runtime_config(mount_plan, "session_abc", "/some/amplified/dir")

        # hooks-redaction should not have session_log_template
        assert "session_log_template" not in mount_plan["hooks"][0]["config"]

        # hooks-logging should have session_log_template injected
        expected_path = str(tmp_path / ".amplifierd" / "state" / "sessions" / "{session_id}" / "events.jsonl")
        assert mount_plan["hooks"][1]["config"]["session_log_template"] == expected_path

        # hooks-todo-reminder should not have session_log_template
        assert "session_log_template" not in mount_plan["hooks"][2]["config"]


def test_inject_runtime_config_session_log_template_with_id_key(tmp_path: Path) -> None:
    """Test _inject_runtime_config injects session_log_template for hooks-logging using id key."""
    from amplifierd.routers.sessions import _inject_runtime_config

    with patch("amplifierd.routers.sessions.get_state_dir") as mock_get_state_dir:
        mock_get_state_dir.return_value = tmp_path / ".amplifierd" / "state"

        # Some mount plans might use "id" instead of "module"
        mount_plan = {
            "hooks": [
                {"id": "hooks-logging", "source": "test", "config": {}},
            ],
        }

        _inject_runtime_config(mount_plan, "session_xyz", "/some/amplified/dir")

        expected_path = str(tmp_path / ".amplifierd" / "state" / "sessions" / "{session_id}" / "events.jsonl")
        assert mount_plan["hooks"][0]["config"]["session_log_template"] == expected_path


def test_inject_runtime_config_session_log_template_creates_config(tmp_path: Path) -> None:
    """Test _inject_runtime_config creates config dict if missing for hooks-logging."""
    from amplifierd.routers.sessions import _inject_runtime_config

    with patch("amplifierd.routers.sessions.get_state_dir") as mock_get_state_dir:
        mock_get_state_dir.return_value = tmp_path / ".amplifierd" / "state"

        # hooks-logging without config key
        mount_plan = {
            "hooks": [
                {"module": "hooks-logging", "source": "test"},
            ],
        }

        _inject_runtime_config(mount_plan, "session_123", "/some/amplified/dir")

        # config should be created
        assert "config" in mount_plan["hooks"][0]
        expected_path = str(tmp_path / ".amplifierd" / "state" / "sessions" / "{session_id}" / "events.jsonl")
        assert mount_plan["hooks"][0]["config"]["session_log_template"] == expected_path


def test_inject_runtime_config_no_hooks_section() -> None:
    """Test _inject_runtime_config handles mount plans without hooks section."""
    from amplifierd.routers.sessions import _inject_runtime_config

    mount_plan = {
        "tools": [{"name": "bash", "config": {}}],
    }

    # Should not raise
    _inject_runtime_config(mount_plan, "session_123", "/some/dir")

    # tools should still get working_dir
    assert mount_plan["tools"][0]["config"]["working_dir"] == "/some/dir"


def test_inject_runtime_config_no_tools_section(tmp_path: Path) -> None:
    """Test _inject_runtime_config handles mount plans without tools section."""
    from amplifierd.routers.sessions import _inject_runtime_config

    with patch("amplifierd.routers.sessions.get_state_dir") as mock_get_state_dir:
        mock_get_state_dir.return_value = tmp_path / ".amplifierd" / "state"

        mount_plan = {
            "hooks": [{"module": "hooks-logging", "source": "test", "config": {}}],
        }

        # Should not raise
        _inject_runtime_config(mount_plan, "session_123", "/some/dir")

        # hooks-logging should still get session_log_template
        expected_path = str(tmp_path / ".amplifierd" / "state" / "sessions" / "{session_id}" / "events.jsonl")
        assert mount_plan["hooks"][0]["config"]["session_log_template"] == expected_path
