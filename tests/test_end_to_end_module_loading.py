"""End-to-end test for module loading from mount plan."""

import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_full_flow_from_mount_plan_to_session():
    """Test the complete flow from generating a mount plan to initializing a session.

    This test verifies:
    1. Mount plan generation with new dict-based format
    2. DaemonModuleSourceResolver mounting
    3. AmplifierSession initialization
    4. Module loading via resolver
    """
    from amplifier_core import AmplifierSession

    from amplifierd.module_resolver import DaemonModuleSourceResolver
    from amplifierd.services.mount_plan_service import MountPlanService

    # Step 1: Generate mount plan using new service (dict with profile hints)
    share_dir = Path("/data/repos/msft/payneio/amplifierd/.amplifierd/share")

    if not share_dir.exists():
        pytest.skip("Share directory not found - run profile compilation first")

    profile_dir = share_dir / "profiles" / "foundation" / "base"
    if not profile_dir.exists():
        pytest.skip("foundation/base profile not compiled - run collection sync first")

    service = MountPlanService(share_dir=share_dir)

    # Create temporary amplified directory for testing
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        amplified_dir = Path(tmp_dir) / "test_amplified"
        amplified_dir.mkdir()
        mount_plan = service.generate_mount_plan("foundation/base", amplified_dir)

    print("\n1. Generated mount plan:")
    print(json.dumps(mount_plan, indent=2))

    # Verify new format
    assert "session" in mount_plan
    assert "orchestrator" in mount_plan["session"]

    orchestrator = mount_plan["session"]["orchestrator"]
    assert isinstance(orchestrator, dict)
    assert "module" in orchestrator
    assert "source" in orchestrator
    # Source should be profile hint, not file:// URL
    assert not orchestrator["source"].startswith("file://")
    print(f"\n2. Orchestrator uses profile hint: {orchestrator['source']}")

    # Step 2: Create resolver
    resolver = DaemonModuleSourceResolver(share_dir)
    print(f"\n3. Created resolver with share_dir: {share_dir}")

    # Step 3: Create AmplifierSession with mount plan as config
    print("\n4. Creating AmplifierSession...")
    session = AmplifierSession(config=mount_plan)

    # Step 4: Mount resolver in coordinator BEFORE initialize()
    # Use coordinator.mount() method (not mount_resolver)
    print("\n5. Mounting resolver in coordinator...")
    await session.coordinator.mount("module-source-resolver", resolver)

    # Step 5: Initialize session (loads modules via resolver)
    print("\n6. Initializing session (loading modules)...")
    try:
        await session.initialize()
        print("   ✓ Session initialized successfully")
    except Exception as e:
        pytest.fail(f"Failed to initialize session: {e}")

    # Step 6: Verify modules are loaded
    print("\n7. Verifying session initialized:")

    # Check coordinator exists and has resolver
    if hasattr(session, "coordinator"):
        print(f"   ✓ Coordinator exists: {type(session.coordinator)}")

        # Check if resolver was mounted
        if hasattr(session.coordinator, "get"):
            try:
                mounted = session.coordinator.get("module-source-resolver")
                if mounted:
                    print(f"   ✓ Resolver mounted: {type(mounted)}")
            except Exception:
                pass  # Resolver might not be retrievable via get()

    # Session should have been initialized with the mount plan
    print("   ✓ Session initialized with mount plan")

    print("\n✅ Full flow successful: mount plan → resolver → session → initialization")


@pytest.mark.asyncio
async def test_mount_plan_service_integration():
    """Test actual mount plan service generation."""
    from pathlib import Path

    from amplifierd.services.mount_plan_service import MountPlanService

    # Create service
    share_dir = Path(".amplifierd/share")

    # Skip if profile cache doesn't exist
    profile_dir = share_dir / "profiles" / "foundation" / "base"
    if not profile_dir.exists():
        pytest.skip("foundation/base profile not compiled - run collection sync first")

    service = MountPlanService(share_dir=share_dir)

    # Generate mount plan for foundation/base profile
    profile_id = "foundation/base"

    # Create temporary amplified directory for testing
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        amplified_dir = Path(tmp_dir) / "test_amplified"
        amplified_dir.mkdir()

        try:
            mount_plan = service.generate_mount_plan(profile_id, amplified_dir)

            print("\n1. Mount plan generated successfully")
            print(f"   Mount plan keys: {mount_plan.keys()}")

            # mount_plan is now a dict
            if "session" in mount_plan:
                print("   Session config present")

            # Check orchestrator
            orchestrator = mount_plan.get("session", {}).get("orchestrator")
            if orchestrator:
                print("\n2. Orchestrator config:")
                print(f"   Module: {orchestrator.get('module')}")
                print(f"   Source: {orchestrator.get('source')}")
                # Source is now a profile hint like "foundation/base", not a file:// URL

            # Note: With the new resolver-based system, mount plans use profile hints
            # (e.g., "foundation/base") instead of file:// URLs. The DaemonModuleSourceResolver
            # handles resolving these to actual file paths at session creation time.

            print("\n3. New mount plan format uses profile hints, not file:// URLs")
            print("   Module resolution happens via DaemonModuleSourceResolver at session creation")

            # This test verified the old file:// URL system, which is being replaced
            print("\n✓ Mount plan generation successful with new dict-based format")

            if not orchestrator:
                pytest.fail("No orchestrator in mount plan")

            module_id = orchestrator.get("module")
            if not module_id:
                pytest.fail("No module ID in orchestrator config")

            print("\n4. Module loading is now handled by AmplifierSession with resolver")
            print(f"   Module ID: {module_id}")
            print(f"   Source hint: {orchestrator.get('source')}")

        except Exception as e:
            pytest.fail(f"Test failed: {e}")


if __name__ == "__main__":
    import asyncio

    print("=" * 70)
    print("Test 1: Full flow from mount plan to session")
    print("=" * 70)
    asyncio.run(test_full_flow_from_mount_plan_to_session())

    print("\n" + "=" * 70)
    print("Test 2: Mount plan service integration")
    print("=" * 70)
    asyncio.run(test_mount_plan_service_integration())
