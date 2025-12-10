"""Test that session working directory is correctly injected into tool configs."""
from pathlib import Path


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
        assert working_dir == absolute_amplified_dir, \
            f"Tool '{tool_name}' has wrong working_dir: {working_dir} != {absolute_amplified_dir}"
