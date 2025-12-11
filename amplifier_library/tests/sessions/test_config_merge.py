"""Unit tests for configuration merging in spawner module.

Tests the _merge_configs function which handles deep merging of
parent session configs with agent-specific overlay configs.
"""

import pytest

from amplifier_library.sessions.spawner import _merge_configs


class TestConfigMerging:
    """Test suite for config merging logic."""

    def test_merge_empty_configs(self):
        """Given empty parent and overlay configs
        When merging
        Then should return empty dict
        """
        result = _merge_configs({}, {})
        assert result == {}

    def test_merge_empty_parent(self):
        """Given empty parent and non-empty overlay
        When merging
        Then should return overlay config unchanged
        """
        overlay = {"session": {"tools": ["debug"]}}
        result = _merge_configs({}, overlay)
        assert result == overlay
        assert result is not overlay  # Should be a copy

    def test_merge_empty_overlay(self):
        """Given non-empty parent and empty overlay
        When merging
        Then should return parent config unchanged
        """
        parent = {"session": {"orchestrator": "default"}}
        result = _merge_configs(parent, {})
        assert result == parent
        assert result is not parent  # Should be a copy

    def test_merge_non_overlapping_keys(self):
        """Given parent and overlay with different keys
        When merging
        Then should combine both sets of keys
        """
        parent = {"session": {"orchestrator": "default"}}
        overlay = {"session": {"tools": ["debug"]}}

        result = _merge_configs(parent, overlay)

        assert result == {
            "session": {
                "orchestrator": "default",
                "tools": ["debug"],
            }
        }

    def test_scalar_override(self):
        """Given parent and overlay with same scalar key
        When merging
        Then overlay value should override parent
        """
        parent = {"session": {"timeout": 30}}
        overlay = {"session": {"timeout": 60}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["timeout"] == 60

    def test_list_replacement(self):
        """Given parent and overlay with same list key
        When merging
        Then overlay list should replace parent list (no concatenation)
        """
        parent = {"session": {"tools": ["read", "write"]}}
        overlay = {"session": {"tools": ["debug"]}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["tools"] == ["debug"]
        assert "read" not in result["session"]["tools"]

    def test_nested_dict_merge(self):
        """Given parent and overlay with nested dicts
        When merging
        Then should recursively merge nested structures
        """
        parent = {
            "session": {
                "orchestrator": "default",
                "llm": {
                    "model": "claude-3-5-sonnet-20241022",
                    "temperature": 0.7,
                },
            }
        }
        overlay = {
            "session": {
                "llm": {
                    "temperature": 0.9,  # Override
                    "max_tokens": 4096,  # Add
                }
            }
        }

        result = _merge_configs(parent, overlay)

        assert result == {
            "session": {
                "orchestrator": "default",
                "llm": {
                    "model": "claude-3-5-sonnet-20241022",  # Inherited
                    "temperature": 0.9,  # Overridden
                    "max_tokens": 4096,  # Added
                },
            }
        }

    def test_deep_nested_merge(self):
        """Given deeply nested parent and overlay configs
        When merging
        Then should handle arbitrary nesting depth
        """
        parent = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "parent",
                        "keep": "this",
                    }
                }
            }
        }
        overlay = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "overlay",
                    }
                }
            }
        }

        result = _merge_configs(parent, overlay)

        assert result["level1"]["level2"]["level3"]["value"] == "overlay"
        assert result["level1"]["level2"]["level3"]["keep"] == "this"

    def test_dict_replaces_scalar(self):
        """Given parent scalar and overlay dict at same key
        When merging
        Then overlay dict should replace parent scalar
        """
        parent = {"session": {"llm": "default"}}
        overlay = {"session": {"llm": {"model": "claude", "temperature": 0.7}}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["llm"] == {"model": "claude", "temperature": 0.7}

    def test_scalar_replaces_dict(self):
        """Given parent dict and overlay scalar at same key
        When merging
        Then overlay scalar should replace parent dict
        """
        parent = {"session": {"llm": {"model": "claude", "temperature": 0.7}}}
        overlay = {"session": {"llm": "override"}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["llm"] == "override"

    def test_none_values(self):
        """Given configs with None values
        When merging
        Then None should be treated as regular value
        """
        parent = {"session": {"value": "something"}}
        overlay = {"session": {"value": None}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["value"] is None

    def test_complex_real_world_merge(self):
        """Given realistic parent and agent overlay configs
        When merging
        Then should correctly combine all aspects
        """
        parent = {
            "session": {
                "orchestrator": "default",
                "timeout": 30,
                "llm": {
                    "model": "claude-3-5-sonnet-20241022",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                "tools": ["read", "write", "search"],
            },
            "module_source": {
                "type": "daemon-resolver",
                "share_dir": "/path/to/share",
            },
        }

        overlay = {
            "session": {
                "tools": ["debug", "test"],  # Replace tools list
                "llm": {
                    "temperature": 0.9,  # Override temp
                    "top_p": 0.95,  # Add new param
                },
                "context": "focused",  # Add new key
            }
        }

        result = _merge_configs(parent, overlay)

        # Verify structure
        assert result["session"]["orchestrator"] == "default"  # Inherited
        assert result["session"]["timeout"] == 30  # Inherited
        assert result["session"]["context"] == "focused"  # Added
        assert result["session"]["tools"] == ["debug", "test"]  # Replaced
        assert result["session"]["llm"]["model"] == "claude-3-5-sonnet-20241022"  # Inherited
        assert result["session"]["llm"]["temperature"] == 0.9  # Overridden
        assert result["session"]["llm"]["max_tokens"] == 4096  # Inherited
        assert result["session"]["llm"]["top_p"] == 0.95  # Added
        assert result["module_source"] == parent["module_source"]  # Unchanged

    def test_merge_does_not_mutate_inputs(self):
        """Given parent and overlay configs
        When merging
        Then should not mutate either input dict
        """
        parent = {"session": {"value": "parent"}}
        overlay = {"session": {"value": "overlay"}}

        parent_copy = parent.copy()
        overlay_copy = overlay.copy()

        _merge_configs(parent, overlay)

        assert parent == parent_copy
        assert overlay == overlay_copy

    def test_boolean_values(self):
        """Given configs with boolean values
        When merging
        Then booleans should be handled correctly
        """
        parent = {"session": {"enabled": True, "debug": False}}
        overlay = {"session": {"enabled": False}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["enabled"] is False
        assert result["session"]["debug"] is False

    def test_numeric_types(self):
        """Given configs with various numeric types
        When merging
        Then should preserve numeric types
        """
        parent = {"session": {"int_val": 42, "float_val": 3.14}}
        overlay = {"session": {"int_val": 100, "float_val": 2.71}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["int_val"] == 100
        assert result["session"]["float_val"] == 2.71
        assert isinstance(result["session"]["int_val"], int)
        assert isinstance(result["session"]["float_val"], float)

    def test_empty_nested_dicts(self):
        """Given configs with empty nested dicts
        When merging
        Then should handle empty dicts correctly
        """
        parent = {"session": {"nested": {}}}
        overlay = {"session": {"nested": {"key": "value"}}}

        result = _merge_configs(parent, overlay)

        assert result["session"]["nested"] == {"key": "value"}

    def test_list_of_dicts_replacement(self):
        """Given configs with lists of dicts
        When merging
        Then should replace entire list (no deep merging of list items)
        """
        parent = {
            "session": {
                "providers": [
                    {"name": "provider1", "config": {}},
                    {"name": "provider2", "config": {}},
                ]
            }
        }
        overlay = {"session": {"providers": [{"name": "new_provider", "config": {}}]}}

        result = _merge_configs(parent, overlay)

        assert len(result["session"]["providers"]) == 1
        assert result["session"]["providers"][0]["name"] == "new_provider"
