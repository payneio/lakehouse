"""Basic validation tests for spawner module.

These tests verify the core functionality without requiring
amplifier-core or full integration setup. Uses Foundation's
deep_merge and generate_sub_session_id functions.
"""

import pytest
from amplifier_foundation import deep_merge
from amplifier_foundation import generate_sub_session_id


def test_generate_sub_session_id():
    """Test sub-session ID generation with trace context."""
    parent_id = "0000000000000000-abc123def456abcd_parent"
    agent_name = "bug-hunter"

    child_id = generate_sub_session_id(
        agent_name=agent_name,
        parent_session_id=parent_id,
    )

    # Should have format: {parent-span}-{child-span}_{agent-name}
    # Foundation extracts the child span from parent (abc123def456abcd) as our parent span
    assert child_id.endswith(f"_{agent_name}")

    # Should have two 16-char hex spans separated by -
    parts = child_id.split("_")
    assert len(parts) == 2
    spans = parts[0].split("-")
    assert len(spans) == 2
    # Each span should be 16 hex chars
    assert len(spans[0]) == 16
    assert len(spans[1]) == 16
    # Should be valid hex
    int(spans[0], 16)
    int(spans[1], 16)


def testdeep_merge_simple():
    """Test simple config merging."""
    parent = {"session": {"orchestrator": "default", "timeout": 30}}
    agent = {"session": {"tools": ["debug"]}}

    merged = deep_merge(parent, agent)

    # Parent values preserved
    assert merged["session"]["orchestrator"] == "default"
    assert merged["session"]["timeout"] == 30

    # Agent values added
    assert merged["session"]["tools"] == ["debug"]


def testdeep_merge_override():
    """Test config value override."""
    parent = {"session": {"timeout": 30}}
    agent = {"session": {"timeout": 60}}

    merged = deep_merge(parent, agent)

    # Agent value overrides parent
    assert merged["session"]["timeout"] == 60


def testdeep_merge_nested():
    """Test deeply nested config merging."""
    parent = {
        "session": {"orchestrator": "default", "config": {"max_turns": 10, "verbose": True}},
        "providers": {"openai": {"model": "gpt-4"}},
    }

    agent = {
        "session": {"config": {"max_turns": 20}, "tools": ["debug"]},
        "providers": {"anthropic": {"model": "claude-3"}},
    }

    merged = deep_merge(parent, agent)

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


def testdeep_merge_list_replace():
    """Test that lists are replaced, not concatenated."""
    parent = {"session": {"tools": ["tool1", "tool2"]}}
    agent = {"session": {"tools": ["tool3"]}}

    merged = deep_merge(parent, agent)

    # Agent list replaces parent list completely
    assert merged["session"]["tools"] == ["tool3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
