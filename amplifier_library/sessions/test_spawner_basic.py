"""Basic validation tests for spawner module.

These tests verify the core functionality without requiring
amplifier-core or full integration setup.
"""


import pytest

from amplifier_library.sessions.spawner import _generate_child_session_id
from amplifier_library.sessions.spawner import _merge_configs


def test_generate_child_session_id():
    """Test child session ID generation with trace context."""
    parent_id = "abc123"
    agent_name = "bug-hunter"

    child_id = _generate_child_session_id(parent_id, agent_name)

    # Should have format: {parent}-{uuid}_agent-name
    assert child_id.startswith(parent_id + "-")
    assert child_id.endswith(f"_{agent_name}")

    # UUID part should be 16 hex chars
    parts = child_id.split("-")
    assert len(parts) >= 2
    uuid_part = parts[1].split("_")[0]
    assert len(uuid_part) == 16
    # Should be valid hex
    int(uuid_part, 16)


def test_merge_configs_simple():
    """Test simple config merging."""
    parent = {"session": {"orchestrator": "default", "timeout": 30}}
    agent = {"session": {"tools": ["debug"]}}

    merged = _merge_configs(parent, agent)

    # Parent values preserved
    assert merged["session"]["orchestrator"] == "default"
    assert merged["session"]["timeout"] == 30

    # Agent values added
    assert merged["session"]["tools"] == ["debug"]


def test_merge_configs_override():
    """Test config value override."""
    parent = {"session": {"timeout": 30}}
    agent = {"session": {"timeout": 60}}

    merged = _merge_configs(parent, agent)

    # Agent value overrides parent
    assert merged["session"]["timeout"] == 60


def test_merge_configs_nested():
    """Test deeply nested config merging."""
    parent = {
        "session": {"orchestrator": "default", "config": {"max_turns": 10, "verbose": True}},
        "providers": {"openai": {"model": "gpt-4"}},
    }

    agent = {
        "session": {"config": {"max_turns": 20}, "tools": ["debug"]},
        "providers": {"anthropic": {"model": "claude-3"}},
    }

    merged = _merge_configs(parent, agent)

    # Session orchestrator preserved
    assert merged["session"]["orchestrator"] == "default"

    # Session config partially overridden
    assert merged["session"]["config"]["max_turns"] == 20  # Overridden
    assert merged["session"]["config"]["verbose"] is True  # Preserved

    # Session tools added
    assert merged["session"]["tools"] == ["debug"]

    # Both providers present
    assert merged["providers"]["openai"]["model"] == "gpt-4"
    assert merged["providers"]["anthropic"]["model"] == "claude-3"


def test_merge_configs_list_replace():
    """Test that lists are replaced, not concatenated."""
    parent = {"session": {"tools": ["tool1", "tool2"]}}
    agent = {"session": {"tools": ["tool3"]}}

    merged = _merge_configs(parent, agent)

    # Agent list replaces parent list completely
    assert merged["session"]["tools"] == ["tool3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
