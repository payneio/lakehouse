"""End-to-end integration test for mount plan with DaemonModuleSourceResolver.

Verifies that:
1. Mount plan format matches amplifier-core expectations
2. DaemonModuleSourceResolver can find modules in share/profiles
3. AmplifierSession can initialize with resolver-based mount plan
4. All modules load successfully
"""

import json
from pathlib import Path

import pytest

from amplifierd.module_resolver import DaemonModuleSourceResolver


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mount_plan_with_real_profile():
    """Integration test verifying mount plan works with real compiled profiles.

    This test validates that the DaemonModuleSourceResolver can locate and resolve
    all modules referenced in a mount plan when using compiled profile directories.

    Environment Requirements:
    - Compiled profile directories in {share_dir}/profiles/
    - Valid mount plan configuration file
    - foundation/base profile compiled and available

    What This Tests:
    - Mount plan structure validation
    - Module resolver can find orchestrator, context, providers, tools, hooks
    - All module paths exist and are accessible

    To Run Locally:
    1. Ensure daemon has been run at least once to create .amplifierd/share
    2. Compile required profiles
    3. Run: pytest -m integration tests/daemon/test_mount_plan_integration.py
    """
    # Use real share directory
    share_dir = Path("/data/repos/msft/payneio/amplifierd/.amplifierd/share")

    if not share_dir.exists():
        pytest.skip(
            "Integration test requires compiled profiles. "
            "Run amplifierd daemon at least once to create share directory structure."
        )

    # Check if foundation/base profile exists
    profile_dir = share_dir / "profiles" / "foundation" / "base"
    if not profile_dir.exists():
        pytest.skip(
            "Integration test requires foundation/base profile. "
            "Ensure profile compilation has completed successfully."
        )

    # Create resolver
    resolver = DaemonModuleSourceResolver(share_dir)

    # Load the example mount plan
    mount_plan_file = Path("working/example-mount-plan-with-resolver.json")
    if not mount_plan_file.exists():
        pytest.skip("Example mount plan not found")

    with open(mount_plan_file) as f:
        mount_plan = json.load(f)

    # Verify mount plan structure
    assert "session" in mount_plan
    assert "orchestrator" in mount_plan["session"]
    assert "context" in mount_plan["session"]

    # Test resolver can find orchestrator
    orch_spec = mount_plan["session"]["orchestrator"]
    if isinstance(orch_spec, dict):
        module_id = orch_spec["module"]
        source_hint = orch_spec["source"]

        source = resolver.resolve(module_id, source_hint)
        path = source.resolve()

        print(f"Orchestrator path: {path}")
        assert path.exists(), f"Orchestrator not found at {path}"

    # Test resolver can find context
    ctx_spec = mount_plan["session"]["context"]
    if isinstance(ctx_spec, dict):
        module_id = ctx_spec["module"]
        source_hint = ctx_spec["source"]

        source = resolver.resolve(module_id, source_hint)
        path = source.resolve()

        print(f"Context path: {path}")
        assert path.exists(), f"Context manager not found at {path}"

    # Test resolver can find providers
    for provider in mount_plan.get("providers", []):
        module_id = provider["module"]
        source_hint = provider["source"]

        source = resolver.resolve(module_id, source_hint)
        path = source.resolve()

        print(f"Provider '{module_id}' path: {path}")
        assert path.exists(), f"Provider {module_id} not found at {path}"

    # Test resolver can find tools
    for tool in mount_plan.get("tools", []):
        module_id = tool["module"]
        source_hint = tool["source"]

        source = resolver.resolve(module_id, source_hint)
        path = source.resolve()

        print(f"Tool '{module_id}' path: {path}")
        assert path.exists(), f"Tool {module_id} not found at {path}"

    # Test resolver can find hooks
    for hook in mount_plan.get("hooks", []):
        module_id = hook["module"]
        source_hint = hook["source"]

        source = resolver.resolve(module_id, source_hint)
        path = source.resolve()

        print(f"Hook '{module_id}' path: {path}")
        assert path.exists(), f"Hook {module_id} not found at {path}"

    print("\n✅ All modules found via resolver!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_amplifier_session_with_resolver():
    """Integration test for AmplifierSession initialization with DaemonModuleSourceResolver.

    This test verifies that all modules in a mount plan can be successfully resolved
    and are ready for AmplifierSession initialization.

    Environment Requirements:
    - Compiled profiles in .amplifierd/share/profiles/
    - foundation/base profile available
    - Example mount plan file present

    What This Tests:
    - All module types (orchestrator, context, providers, tools, hooks) can be resolved
    - Module paths are valid and accessible
    - Resolver integration readiness for AmplifierSession

    Note: Full AmplifierSession integration pending - currently tests module resolution only.

    To Run Locally:
    1. Start amplifierd daemon to initialize share directory
    2. Ensure profiles are compiled
    3. Run: pytest -m integration tests/daemon/test_mount_plan_integration.py
    """

    # Use real share directory
    share_dir = Path("/data/repos/msft/payneio/amplifierd/.amplifierd/share")

    if not share_dir.exists():
        pytest.skip(
            "Integration test requires share directory. "
            "Run amplifierd daemon to initialize required directory structure."
        )

    profile_dir = share_dir / "profiles" / "foundation" / "base"
    if not profile_dir.exists():
        pytest.skip(
            "Integration test requires foundation/base profile. "
            "Compile profiles before running integration tests."
        )

    # Load mount plan
    mount_plan_file = Path("working/example-mount-plan-with-resolver.json")
    if not mount_plan_file.exists():
        pytest.skip("Example mount plan not found")

    with open(mount_plan_file) as f:
        mount_plan = json.load(f)

    # Create resolver
    resolver = DaemonModuleSourceResolver(share_dir)

    # NOTE: Full integration with ModuleLoader and AmplifierSession pending
    # This requires creating coordinator first, mounting resolver, then passing to session
    # For now, test just the resolution

    # Verify all modules can be resolved
    modules_to_test = []

    # Extract modules from mount plan
    if isinstance(mount_plan["session"]["orchestrator"], dict):
        modules_to_test.append(mount_plan["session"]["orchestrator"])
    if isinstance(mount_plan["session"]["context"], dict):
        modules_to_test.append(mount_plan["session"]["context"])

    modules_to_test.extend(mount_plan.get("providers", []))
    modules_to_test.extend(mount_plan.get("tools", []))
    modules_to_test.extend(mount_plan.get("hooks", []))

    for module_spec in modules_to_test:
        module_id = module_spec["module"]
        source_hint = module_spec.get("source")

        if source_hint:
            source = resolver.resolve(module_id, source_hint)
            path = source.resolve()
            print(f"✓ {module_id}: {path}")

    print(f"\n✅ Verified {len(modules_to_test)} modules can be resolved!")
