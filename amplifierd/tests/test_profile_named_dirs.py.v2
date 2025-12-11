"""Test that profile compilation creates profile-named directories."""

from pathlib import Path

import pytest

from amplifierd.models.profiles import ModuleConfig
from amplifierd.models.profiles import ProfileDetails
from amplifierd.models.profiles import SessionConfig
from amplifierd.services.profile_compilation import ProfileCompilationService
from amplifierd.services.ref_resolution import RefResolutionService


@pytest.fixture
def test_profile() -> ProfileDetails:
    """Create test profile with orchestrator and provider."""
    return ProfileDetails(
        name="test",
        schema_version=2,
        version="1.0.0",
        description="Test profile",
        collection_id="test-collection",
        source="test",
        is_active=False,
        session=SessionConfig(
            orchestrator=ModuleConfig(module="loop-streaming", source=None),
            context_manager=ModuleConfig(module="context-simple", source=None),
        ),
        providers=[
            ModuleConfig(module="provider-anthropic", source=None),
        ],
        tools=[
            ModuleConfig(module="tool-web", source=None),
        ],
        hooks=[],
        agents={},
        context={},
    )


def test_module_structure_uses_profile_names(tmp_path: Path, test_profile: ProfileDetails) -> None:
    """Test that _create_module_structure creates directories with profile names, not hashes."""
    # Setup: Create mock resolved assets
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Create mock orchestrator module in cache (with hash directory structure)
    orch_cache = cache_dir / "e9a407c4fbfe46ac"
    orch_cache.mkdir()
    orch_module = orch_cache / "amplifier_module_loop_streaming"
    orch_module.mkdir()
    (orch_module / "__init__.py").write_text("")

    # Create mock context-manager module
    ctx_cache = cache_dir / "1fbc77fd9e44"
    ctx_cache.mkdir()
    ctx_module = ctx_cache / "amplifier_module_context_simple"
    ctx_module.mkdir()
    (ctx_module / "__init__.py").write_text("")

    # Create mock provider module
    provider_cache = cache_dir / "a1b2c3d4e5f6"
    provider_cache.mkdir()
    provider_module = provider_cache / "amplifier_module_provider_anthropic"
    provider_module.mkdir()
    (provider_module / "__init__.py").write_text("")

    # Create mock tool module
    tool_cache = cache_dir / "f6e5d4c3b2a1"
    tool_cache.mkdir()
    tool_module = tool_cache / "amplifier_module_tool_web"
    tool_module.mkdir()
    (tool_module / "__init__.py").write_text("")

    # Prepare assets dict as if RefResolutionService resolved them
    assets = {
        "orchestrator": [orch_cache],
        "context-manager": [ctx_cache],
        "agents": [],
        "context": [],
        "providers": [provider_cache],
        "tools": [tool_cache],
        "hooks": [],
    }

    # Create compilation service
    target_dir = tmp_path / "compiled"
    target_dir.mkdir()

    ref_resolution = RefResolutionService(tmp_path)
    compilation_service = ProfileCompilationService(tmp_path, ref_resolution)

    # Execute
    compilation_service._create_module_structure(target_dir, assets, test_profile)

    # Verify: Directories should use profile names, NOT hash names
    assert (target_dir / "orchestrator" / "loop-streaming").is_dir(), "orchestrator should use profile name"
    assert not (target_dir / "orchestrator" / "e9a407c4fbfe46ac").exists(), "should not have hash directory"

    assert (target_dir / "context" / "context-simple").is_dir(), "context should use profile name"
    assert not (target_dir / "context" / "1fbc77fd9e44").exists(), "should not have hash directory"

    assert (target_dir / "providers" / "provider-anthropic").is_dir(), "provider should use profile name"
    assert not (target_dir / "providers" / "a1b2c3d4e5f6").exists(), "should not have hash directory"

    assert (target_dir / "tools" / "tool-web").is_dir(), "tool should use profile name"
    assert not (target_dir / "tools" / "f6e5d4c3b2a1").exists(), "should not have hash directory"

    # Verify modules are copied inside the named directories
    assert (
        target_dir / "orchestrator" / "loop-streaming" / "amplifier_module_loop_streaming" / "__init__.py"
    ).exists(), "module should be inside profile-named directory"
    assert (target_dir / "context" / "context-simple" / "amplifier_module_context_simple" / "__init__.py").exists(), (
        "module should be inside profile-named directory"
    )
    assert (
        target_dir / "providers" / "provider-anthropic" / "amplifier_module_provider_anthropic" / "__init__.py"
    ).exists(), "module should be inside profile-named directory"
    assert (target_dir / "tools" / "tool-web" / "amplifier_module_tool_web" / "__init__.py").exists(), (
        "module should be inside profile-named directory"
    )
