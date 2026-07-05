"""Test that runtime config is correctly injected into mount plans.

Tests LakehouseBundleManager.inject_runtime_config which handles:
- working_dir injection into tool configs
- allowed_write_paths injection for filesystem tools
- session_log_template injection for hooks-logging
"""

from pathlib import Path

from lakehoused.bundles import LakehouseBundleManager


def test_working_dir_injection_in_mount_plan(tmp_path: Path) -> None:
    """Test that working_dir is injected into all tool configs when creating mount plans."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    test_dir = data_root / "test_project"
    test_dir.mkdir()

    mount_plan = {
        "session": {"settings": {}},
        "tools": [
            {"name": "bash", "config": {}},
            {"name": "grep", "config": {}},
            {"name": "glob", "config": {}},
        ],
    }

    absolute_project_path = str(test_dir.resolve())

    # Apply the session working directory injection logic
    mount_plan["session"]["settings"]["project_path"] = absolute_project_path
    mount_plan["session"]["settings"]["working_dir"] = absolute_project_path

    # Inject working_dir into all tool configs
    if "tools" in mount_plan:
        for tool in mount_plan["tools"]:
            if "config" not in tool:
                tool["config"] = {}
            tool["config"]["working_dir"] = absolute_project_path

    # Verify working_dir is set correctly
    assert "session" in mount_plan
    assert "settings" in mount_plan["session"]
    assert "working_dir" in mount_plan["session"]["settings"]
    assert mount_plan["session"]["settings"]["working_dir"] == absolute_project_path

    # Verify all tools have working_dir injected
    tools = mount_plan.get("tools", [])
    assert len(tools) > 0, "Mount plan should have at least one tool"

    for tool in tools:
        tool_name = tool.get("name", "unknown")
        config = tool.get("config", {})

        assert "working_dir" in config, f"Tool '{tool_name}' missing working_dir in config"

        working_dir = config["working_dir"]
        assert working_dir == absolute_project_path, (
            f"Tool '{tool_name}' has wrong working_dir: {working_dir} != {absolute_project_path}"
        )


def test_inject_runtime_config_working_dir(tmp_path: Path) -> None:
    """Test inject_runtime_config injects working_dir into tool configs."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    absolute_project_path = str(test_dir.resolve())

    mount_plan = {
        "tools": [
            {"name": "bash", "config": {}},
            {"name": "grep"},  # No config key
            {"name": "glob", "config": {"working_dir": "/custom/path"}},  # Already has working_dir
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_123", absolute_project_path)

    # bash should get working_dir injected
    assert mount_plan["tools"][0]["config"]["working_dir"] == absolute_project_path

    # grep should get config created and working_dir injected
    assert "config" in mount_plan["tools"][1]
    assert mount_plan["tools"][1]["config"]["working_dir"] == absolute_project_path

    # glob should keep its custom working_dir (not overwritten)
    assert mount_plan["tools"][2]["config"]["working_dir"] == "/custom/path"


def test_inject_runtime_config_allowed_write_paths(tmp_path: Path) -> None:
    """Test inject_runtime_config injects allowed_write_paths for tool-filesystem."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    absolute_project_path = str(test_dir.resolve())

    mount_plan = {
        "tools": [
            {"module": "tool-filesystem", "source": "test", "config": {}},
            {"module": "tool-bash", "source": "test", "config": {}},  # Not filesystem
            {"module": "tool-filesystem", "source": "test", "config": {"allowed_write_paths": ["/custom"]}},
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_123", absolute_project_path)

    # tool-filesystem should get allowed_write_paths injected
    assert mount_plan["tools"][0]["config"]["allowed_write_paths"] == [absolute_project_path]

    # tool-bash should NOT get allowed_write_paths (not a filesystem tool)
    assert "allowed_write_paths" not in mount_plan["tools"][1]["config"]

    # tool-filesystem with explicit allowed_write_paths should keep its config (not overwritten)
    assert mount_plan["tools"][2]["config"]["allowed_write_paths"] == ["/custom"]


def test_inject_runtime_config_allowed_write_paths_by_source(tmp_path: Path) -> None:
    """Test inject_runtime_config detects filesystem tool by source field."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    absolute_project_path = str(test_dir.resolve())

    # Some mount plans might use source containing "filesystem" instead of module name
    mount_plan = {
        "tools": [
            {"id": "write_file", "source": "behaviors/filesystem/tools/tool-filesystem", "config": {}},
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_123", absolute_project_path)

    # Should detect filesystem tool by source and inject allowed_write_paths
    assert mount_plan["tools"][0]["config"]["allowed_write_paths"] == [absolute_project_path]


def test_inject_runtime_config_session_log_template_with_module_key(tmp_path: Path) -> None:
    """Test inject_runtime_config injects session_log_template for hooks-logging using module key."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    mount_plan = {
        "hooks": [
            {"module": "hooks-redaction", "source": "test", "config": {}},
            {"module": "hooks-logging", "source": "test", "config": {}},
            {"module": "hooks-todo-reminder", "source": "test", "config": {}},
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_abc", "/some/amplified/dir")

    # hooks-redaction should not have session_log_template
    assert "session_log_template" not in mount_plan["hooks"][0]["config"]

    # hooks-logging should have session_log_template injected
    expected_path = str(tmp_path / "state" / "sessions" / "{session_id}" / "events.jsonl")
    assert mount_plan["hooks"][1]["config"]["session_log_template"] == expected_path

    # hooks-todo-reminder should not have session_log_template
    assert "session_log_template" not in mount_plan["hooks"][2]["config"]


def test_inject_runtime_config_session_log_template_with_id_key(tmp_path: Path) -> None:
    """Test inject_runtime_config injects session_log_template for hooks-logging using id key."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    # Some mount plans might use "id" instead of "module"
    mount_plan = {
        "hooks": [
            {"id": "hooks-logging", "source": "test", "config": {}},
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_xyz", "/some/amplified/dir")

    expected_path = str(tmp_path / "state" / "sessions" / "{session_id}" / "events.jsonl")
    assert mount_plan["hooks"][0]["config"]["session_log_template"] == expected_path


def test_inject_runtime_config_session_log_template_singular_hook_logging(tmp_path: Path) -> None:
    """Test inject_runtime_config injects session_log_template for hook-logging (singular).

    The Foundation bundle system uses 'hook-logging' (singular) instead of 'hooks-logging' (plural).
    Both should be recognized and configured correctly.
    """
    manager = LakehouseBundleManager(home_dir=tmp_path)

    # Foundation bundles use singular "hook-logging"
    mount_plan = {
        "hooks": [
            {"module": "hook-redaction", "source": "software-developer", "config": {}},
            {"module": "hook-logging", "source": "software-developer", "config": {}},
            {"module": "hook-todo-reminder", "source": "software-developer", "config": {}},
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_abc", "/some/amplified/dir")

    # hook-redaction should not have session_log_template
    assert "session_log_template" not in mount_plan["hooks"][0]["config"]

    # hook-logging should have session_log_template injected
    expected_path = str(tmp_path / "state" / "sessions" / "{session_id}" / "events.jsonl")
    assert mount_plan["hooks"][1]["config"]["session_log_template"] == expected_path

    # hook-todo-reminder should not have session_log_template
    assert "session_log_template" not in mount_plan["hooks"][2]["config"]


def test_inject_runtime_config_session_log_template_creates_config(tmp_path: Path) -> None:
    """Test inject_runtime_config creates config dict if missing for hooks-logging."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    # hooks-logging without config key
    mount_plan = {
        "hooks": [
            {"module": "hooks-logging", "source": "test"},
        ],
    }

    manager.inject_runtime_config(mount_plan, "session_123", "/some/amplified/dir")

    # config should be created
    assert "config" in mount_plan["hooks"][0]
    expected_path = str(tmp_path / "state" / "sessions" / "{session_id}" / "events.jsonl")
    assert mount_plan["hooks"][0]["config"]["session_log_template"] == expected_path


def test_inject_runtime_config_no_hooks_section(tmp_path: Path) -> None:
    """Test inject_runtime_config handles mount plans without hooks section."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    mount_plan = {
        "tools": [{"name": "bash", "config": {}}],
    }

    # Should not raise
    manager.inject_runtime_config(mount_plan, "session_123", "/some/dir")

    # tools should still get working_dir
    assert mount_plan["tools"][0]["config"]["working_dir"] == "/some/dir"


def test_inject_runtime_config_no_tools_section(tmp_path: Path) -> None:
    """Test inject_runtime_config handles mount plans without tools section."""
    manager = LakehouseBundleManager(home_dir=tmp_path)

    mount_plan = {
        "hooks": [{"module": "hooks-logging", "source": "test", "config": {}}],
    }

    # Should not raise
    manager.inject_runtime_config(mount_plan, "session_123", "/some/dir")

    # hooks-logging should still get session_log_template
    expected_path = str(tmp_path / "state" / "sessions" / "{session_id}" / "events.jsonl")
    assert mount_plan["hooks"][0]["config"]["session_log_template"] == expected_path
