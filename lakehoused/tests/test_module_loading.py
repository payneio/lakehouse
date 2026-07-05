"""Test module loading with mount plans.

This test verifies that the module loading system works correctly with
the mount plan format we generate.
"""

import sys
from pathlib import Path

import pytest


@pytest.fixture
def test_modules(tmp_path: Path) -> dict[str, Path]:
    """Create minimal test modules for testing module loading.

    Returns dict mapping module IDs to their parent directories.
    """
    modules = {}

    # Create orchestrator module
    orchestrator_parent = tmp_path / "orchestrator"
    orchestrator_parent.mkdir()
    orchestrator_module = orchestrator_parent / "amplifier_module_test_orchestrator"
    orchestrator_module.mkdir()

    orchestrator_init = orchestrator_module / "__init__.py"
    orchestrator_init.write_text("""
class TestOrchestrator:
    '''Minimal test orchestrator.'''
    async def initialize(self):
        pass

async def mount(coordinator, config=None):
    '''Test orchestrator mount function.'''
    orchestrator = TestOrchestrator()
    await orchestrator.initialize()
    await coordinator.mount('orchestrator', orchestrator)
""")
    modules["test-orchestrator"] = orchestrator_parent

    # Create context module
    context_parent = tmp_path / "context"
    context_parent.mkdir()
    context_module = context_parent / "amplifier_module_test_context"
    context_module.mkdir()

    context_init = context_module / "__init__.py"
    context_init.write_text("""
class TestContext:
    '''Minimal test context manager.'''
    async def initialize(self):
        pass

async def mount(coordinator, config=None):
    '''Test context mount function.'''
    context = TestContext()
    await context.initialize()
    await coordinator.mount('context', context)
""")
    modules["test-context"] = context_parent

    return modules


@pytest.mark.asyncio
async def test_module_loader_filesystem_discovery(test_modules):
    """Test that ModuleLoader can load a module from filesystem with correct search path."""
    import sys

    from amplifier_core import ModuleLoader

    # Get test module path from fixture
    parent_dir = test_modules["test-orchestrator"]

    # Verify the module exists
    module_dir = parent_dir / "amplifier_module_test_orchestrator"
    assert module_dir.exists(), f"Module directory not found: {module_dir}"
    assert (module_dir / "__init__.py").exists(), "Module __init__.py not found"

    # Add parent directory to sys.path so module can be imported
    parent_str = str(parent_dir)
    original_path = sys.path.copy()

    try:
        if parent_str not in sys.path:
            sys.path.insert(0, parent_str)

        # Create loader with search path pointing to parent directory
        # This is what mount plan service generates
        loader = ModuleLoader(search_paths=[parent_dir])

        # Try to load the module with ID "test-orchestrator"
        # This is what mount plan service puts in the mount plan
        mount_fn = await loader.load("test-orchestrator", config={})
        assert mount_fn is not None, "Module load returned None"
        assert callable(mount_fn), "Module load should return mount function"
        print("✓ Successfully loaded module 'test-orchestrator'")
        print(f"  Mount function: {mount_fn}")
    except Exception as e:
        pytest.fail(f"Failed to load module: {e}")
    finally:
        # Restore original sys.path
        sys.path = original_path


@pytest.mark.asyncio
async def test_module_loader_with_direct_import(test_modules):
    """Test direct import to understand what ModuleLoader is trying to do."""
    # Get test module path from fixture
    parent_dir = test_modules["test-orchestrator"]

    # Add to sys.path like ModuleLoader does
    parent_str = str(parent_dir)
    original_path = sys.path.copy()

    try:
        if parent_str not in sys.path:
            sys.path.insert(0, parent_str)

        # This is what ModuleLoader._load_filesystem does:
        # module_name = f"amplifier_module_{module_id.replace('-', '_')}"
        import amplifier_module_test_orchestrator

        assert hasattr(amplifier_module_test_orchestrator, "mount"), "Module missing mount function"
        print("✓ Direct import successful")
        print(f"  Module: {amplifier_module_test_orchestrator}")
        print(f"  Mount function: {amplifier_module_test_orchestrator.mount}")

    except ImportError as e:
        pytest.fail(f"Direct import failed: {e}")
    finally:
        # Restore original sys.path
        sys.path = original_path


@pytest.mark.asyncio
async def test_mount_plan_format(test_modules):
    """Test that our mount plan format works with AmplifierSession."""
    import sys

    from amplifier_core import AmplifierSession
    from amplifier_core import ModuleLoader

    # Get test module paths from fixture
    orchestrator_dir = test_modules["test-orchestrator"]
    context_dir = test_modules["test-context"]

    # Add directories to sys.path so modules can be imported
    original_path = sys.path.copy()

    try:
        for path_dir in [orchestrator_dir, context_dir]:
            path_str = str(path_dir)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)

        # This is the format our mount plan service generates
        mount_plan = {
            "session": {
                "orchestrator": {"module": "test-orchestrator", "source": f"file://{orchestrator_dir}", "config": {}},
                "context": {"module": "test-context", "source": f"file://{context_dir}", "config": {}},
            },
            "providers": [],
            "tools": [],
            "hooks": [],
        }

        # Create loader with search paths from mount plan
        search_paths = [orchestrator_dir, context_dir]
        loader = ModuleLoader(search_paths=search_paths)

        # Create session
        session = AmplifierSession(config=mount_plan, loader=loader, session_id="test_session")

        # Try to initialize
        try:
            await session.initialize()
            print("✓ Session initialized successfully")
        except Exception as e:
            pytest.fail(f"Session initialization failed: {e}")
        finally:
            await session.cleanup()
    finally:
        # Restore original sys.path
        sys.path = original_path
