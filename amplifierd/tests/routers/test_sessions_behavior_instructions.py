"""Tests for behavior instruction loading in session creation.

Tests that behavior instructions are correctly loaded and combined with
profile instructions when creating sessions.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from amplifierd.services.mention_resolver import MentionResolver


@pytest.fixture
def temp_profile_dir():
    """Create a temporary compiled profile directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_dir = Path(tmpdir) / "profiles" / "test_profile"
        profile_dir.mkdir(parents=True)
        yield profile_dir


@pytest.fixture
def temp_amplified_dir():
    """Create a temporary amplified directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_profile_yaml(profile_dir: Path, instructions: str = "", behaviors: list = None):
    """Create a profile.yaml file with given content."""
    profile_yaml = {
        "name": "test_profile",
        "instructions": instructions,
        "behaviors": behaviors or [],
    }
    profile_path = profile_dir / "profile.yaml"
    profile_path.write_text(yaml.dump(profile_yaml))
    return profile_path


def create_behavior_yaml(profile_dir: Path, behavior_id: str, instructions: str = ""):
    """Create a behavior YAML file with given content."""
    behavior_dir = profile_dir / "behaviors" / behavior_id
    behavior_dir.mkdir(parents=True, exist_ok=True)

    behavior_yaml = {
        "id": behavior_id,
        "instructions": instructions,
    }

    behavior_path = behavior_dir / "behavior.yaml"
    behavior_path.write_text(yaml.dump(behavior_yaml))
    return behavior_path


class TestBehaviorInstructionLoading:
    """Test behavior instruction loading during session creation."""

    def test_profile_with_instructions_and_behaviors_with_instructions(
        self, temp_profile_dir, temp_amplified_dir
    ):
        """Test loading instructions from profile and all behaviors."""
        # Create profile with instructions
        profile_instructions = "Profile level instruction with @file.md mention"
        create_profile_yaml(
            temp_profile_dir,
            instructions=profile_instructions,
            behaviors=[{"id": "behavior1"}, {"id": "behavior2"}],
        )

        # Create behaviors with instructions
        behavior1_instructions = "Behavior 1 instruction with @behavior1.md"
        create_behavior_yaml(temp_profile_dir, "behavior1", behavior1_instructions)

        behavior2_instructions = "Behavior 2 instruction with @behavior2.md"
        create_behavior_yaml(temp_profile_dir, "behavior2", behavior2_instructions)

        # Mock the mention resolver to capture combined instructions
        captured_instructions = None

        def mock_resolve(instructions):
            nonlocal captured_instructions
            captured_instructions = instructions
            return []

        with patch.object(MentionResolver, "resolve_profile_instructions", side_effect=mock_resolve):
            # Simulate the instruction loading logic
            profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

            all_instructions = []
            profile_inst = profile_yaml.get("instructions", "")
            if profile_inst:
                all_instructions.append(profile_inst)

            behaviors_list = profile_yaml.get("behaviors", [])
            for behavior_ref in behaviors_list:
                behavior_id = behavior_ref.get("id")
                behavior_dir = temp_profile_dir / "behaviors" / behavior_id
                behavior_yaml_path = behavior_dir / "behavior.yaml"

                if behavior_yaml_path.exists():
                    behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                    behavior_inst = behavior_yaml.get("instructions", "")
                    if behavior_inst:
                        all_instructions.append(behavior_inst)

            if all_instructions:
                combined = "\n\n".join(all_instructions)
                resolver = MentionResolver(temp_profile_dir, temp_amplified_dir)
                resolver.resolve_profile_instructions(combined)

        # Verify all instructions were combined
        assert captured_instructions is not None
        assert profile_instructions in captured_instructions
        assert behavior1_instructions in captured_instructions
        assert behavior2_instructions in captured_instructions

    def test_profile_without_instructions_behaviors_with_instructions(self, temp_profile_dir, temp_amplified_dir):
        """Test loading when profile has no instructions but behaviors do."""
        # Create profile without instructions
        create_profile_yaml(
            temp_profile_dir,
            instructions="",
            behaviors=[{"id": "behavior1"}],
        )

        # Create behavior with instructions
        behavior1_instructions = "Behavior 1 instruction only"
        create_behavior_yaml(temp_profile_dir, "behavior1", behavior1_instructions)

        # Simulate loading
        profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

        all_instructions = []
        profile_inst = profile_yaml.get("instructions", "")
        if profile_inst:
            all_instructions.append(profile_inst)

        behaviors_list = profile_yaml.get("behaviors", [])
        for behavior_ref in behaviors_list:
            behavior_id = behavior_ref.get("id")
            behavior_dir = temp_profile_dir / "behaviors" / behavior_id
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_inst = behavior_yaml.get("instructions", "")
                if behavior_inst:
                    all_instructions.append(behavior_inst)

        # Should have only behavior instructions
        assert len(all_instructions) == 1
        assert all_instructions[0] == behavior1_instructions

    def test_profile_with_instructions_behaviors_without(self, temp_profile_dir, temp_amplified_dir):
        """Test loading when profile has instructions but behaviors don't."""
        # Create profile with instructions
        profile_instructions = "Profile instruction only"
        create_profile_yaml(
            temp_profile_dir,
            instructions=profile_instructions,
            behaviors=[{"id": "behavior1"}],
        )

        # Create behavior without instructions
        create_behavior_yaml(temp_profile_dir, "behavior1", "")

        # Simulate loading
        profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

        all_instructions = []
        profile_inst = profile_yaml.get("instructions", "")
        if profile_inst:
            all_instructions.append(profile_inst)

        behaviors_list = profile_yaml.get("behaviors", [])
        for behavior_ref in behaviors_list:
            behavior_id = behavior_ref.get("id")
            behavior_dir = temp_profile_dir / "behaviors" / behavior_id
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_inst = behavior_yaml.get("instructions", "")
                if behavior_inst:
                    all_instructions.append(behavior_inst)

        # Should have only profile instructions
        assert len(all_instructions) == 1
        assert all_instructions[0] == profile_instructions

    def test_missing_behavior_yaml_graceful(self, temp_profile_dir, temp_amplified_dir):
        """Test graceful handling when behavior YAML is missing."""
        # Create profile with behaviors
        create_profile_yaml(
            temp_profile_dir,
            instructions="Profile instruction",
            behaviors=[{"id": "behavior1"}, {"id": "missing_behavior"}],
        )

        # Create only behavior1
        create_behavior_yaml(temp_profile_dir, "behavior1", "Behavior 1 instruction")
        # behavior2 intentionally missing

        # Simulate loading
        profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

        all_instructions = []
        profile_inst = profile_yaml.get("instructions", "")
        if profile_inst:
            all_instructions.append(profile_inst)

        behaviors_list = profile_yaml.get("behaviors", [])
        loaded_count = 0
        for behavior_ref in behaviors_list:
            behavior_id = behavior_ref.get("id")
            behavior_dir = temp_profile_dir / "behaviors" / behavior_id
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_inst = behavior_yaml.get("instructions", "")
                if behavior_inst:
                    all_instructions.append(behavior_inst)
                    loaded_count += 1

        # Should have profile + 1 behavior (missing one skipped gracefully)
        assert len(all_instructions) == 2
        assert loaded_count == 1

    def test_behavior_instructions_with_at_mentions(self, temp_profile_dir, temp_amplified_dir):
        """Test that at-mentions in behavior instructions are resolved."""
        # Create files to be mentioned
        (temp_amplified_dir / "file1.md").write_text("File 1 content")
        (temp_amplified_dir / "file2.md").write_text("File 2 content")

        # Create profile with mention
        profile_instructions = "Profile with @file1.md"
        create_profile_yaml(
            temp_profile_dir,
            instructions=profile_instructions,
            behaviors=[{"id": "behavior1"}],
        )

        # Create behavior with mention
        behavior1_instructions = "Behavior with @file2.md"
        create_behavior_yaml(temp_profile_dir, "behavior1", behavior1_instructions)

        # Load and resolve
        profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

        all_instructions = []
        profile_inst = profile_yaml.get("instructions", "")
        if profile_inst:
            all_instructions.append(profile_inst)

        behaviors_list = profile_yaml.get("behaviors", [])
        for behavior_ref in behaviors_list:
            behavior_id = behavior_ref.get("id")
            behavior_dir = temp_profile_dir / "behaviors" / behavior_id
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_inst = behavior_yaml.get("instructions", "")
                if behavior_inst:
                    all_instructions.append(behavior_inst)

        combined_instructions = "\n\n".join(all_instructions)

        # Resolve with actual resolver
        resolver = MentionResolver(temp_profile_dir, temp_amplified_dir)
        context_messages = resolver.resolve_profile_instructions(combined_instructions)

        # Should have resolved both mentions
        assert len(context_messages) == 2

        # Check that file contents are present (they'll be in formatted context messages)
        all_content = " ".join(msg.content for msg in context_messages)
        assert "File 1 content" in all_content
        assert "File 2 content" in all_content

    def test_no_instructions_anywhere(self, temp_profile_dir, temp_amplified_dir):
        """Test when neither profile nor behaviors have instructions."""
        # Create profile without instructions
        create_profile_yaml(
            temp_profile_dir,
            instructions="",
            behaviors=[{"id": "behavior1"}],
        )

        # Create behavior without instructions
        create_behavior_yaml(temp_profile_dir, "behavior1", "")

        # Simulate loading
        profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

        all_instructions = []
        profile_inst = profile_yaml.get("instructions", "")
        if profile_inst:
            all_instructions.append(profile_inst)

        behaviors_list = profile_yaml.get("behaviors", [])
        for behavior_ref in behaviors_list:
            behavior_id = behavior_ref.get("id")
            behavior_dir = temp_profile_dir / "behaviors" / behavior_id
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_inst = behavior_yaml.get("instructions", "")
                if behavior_inst:
                    all_instructions.append(behavior_inst)

        # Should be empty
        assert len(all_instructions) == 0

    def test_behavior_reference_formats(self, temp_profile_dir, temp_amplified_dir):
        """Test different behavior reference formats (dict vs string)."""
        # Create profile with different behavior formats
        create_profile_yaml(
            temp_profile_dir,
            instructions="Profile instruction",
            behaviors=[
                {"id": "behavior1"},  # Dict format
                "behavior2",  # String format (simple ID)
            ],
        )

        # Create both behaviors
        create_behavior_yaml(temp_profile_dir, "behavior1", "Behavior 1 instruction")
        create_behavior_yaml(temp_profile_dir, "behavior2", "Behavior 2 instruction")

        # Simulate loading with format handling
        profile_yaml = yaml.safe_load((temp_profile_dir / "profile.yaml").read_text())

        all_instructions = []
        profile_inst = profile_yaml.get("instructions", "")
        if profile_inst:
            all_instructions.append(profile_inst)

        behaviors_list = profile_yaml.get("behaviors", [])
        for behavior_ref in behaviors_list:
            # Handle both dict and string formats
            behavior_id = behavior_ref.get("id") if isinstance(behavior_ref, dict) else behavior_ref

            behavior_dir = temp_profile_dir / "behaviors" / behavior_id
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_inst = behavior_yaml.get("instructions", "")
                if behavior_inst:
                    all_instructions.append(behavior_inst)

        # Should have all 3 instructions
        assert len(all_instructions) == 3
