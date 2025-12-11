"""
Shared pytest fixtures for amplifierd test suite.

Provides fixtures for:
- Temporary storage directories
- Session managers with isolated storage
- Mock amplifier-core sessions
- Sample data
"""

import sys
import tempfile
import types
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest


# Install mocks at module import time (before pytest collects tests)
def _setup_amplifier_mocks() -> None:
    """Setup mocks for amplifier-core libraries."""

    # Mock amplifier_profiles
    class MockProfileLoader:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize mock loader (accepts any arguments)."""

        def list_profiles(self) -> list[dict[str, Any]]:
            return []

        def get_profile(self, name: str) -> dict[str, Any]:
            raise FileNotFoundError(f"Profile not found: {name}")

    profiles_module = types.ModuleType("amplifier_profiles")
    profiles_module.ProfileLoader = MockProfileLoader  # type: ignore[attr-defined]
    sys.modules["amplifier_profiles"] = profiles_module

    # Mock amplifier_config
    class MockConfigManager:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize mock config manager (accepts any arguments)."""

        def get_active_profile(self) -> str | None:
            return None

    class MockConfigPaths:
        """Mock ConfigPaths for testing."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize mock paths."""

    config_module = types.ModuleType("amplifier_config")
    config_module.ConfigManager = MockConfigManager  # type: ignore[attr-defined]
    config_module.ConfigPaths = MockConfigPaths  # type: ignore[attr-defined]
    sys.modules["amplifier_config"] = config_module

    # Mock amplifier_collections
    class MockCollectionLock:
        """Mock CollectionLock for testing."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize mock lock."""

    def mock_discover_collection_resources(path: str) -> dict[str, Any]:
        return {
            "profiles": [],
            "agents": [],
            "modules": {"providers": [], "tools": [], "hooks": [], "orchestrators": []},
        }

    collections_module = types.ModuleType("amplifier_collections")
    collections_module.CollectionLock = MockCollectionLock  # type: ignore[attr-defined]
    collections_module.discover_collection_resources = mock_discover_collection_resources  # type: ignore[attr-defined]
    sys.modules["amplifier_collections"] = collections_module

    # Mock amplifier_module_resolution
    class MockStandardModuleSourceResolver:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize mock module resolver (accepts any arguments)."""

        def list_all_modules(self, type_filter: str | None = None) -> list[dict[str, Any]]:
            return []

        def list_providers(self) -> list[dict[str, Any]]:
            return []

        def list_hooks(self) -> list[dict[str, Any]]:
            return []

        def list_tools(self) -> list[dict[str, Any]]:
            return []

        def list_orchestrators(self) -> list[dict[str, Any]]:
            return []

        def get_module_details(self, module_id: str) -> dict[str, Any]:
            raise ValueError(f"Module not found: {module_id}")

    module_resolution = types.ModuleType("amplifier_module_resolution")
    module_resolution.StandardModuleSourceResolver = MockStandardModuleSourceResolver  # type: ignore[attr-defined]
    sys.modules["amplifier_module_resolution"] = module_resolution


# Call setup immediately when conftest.py is imported
_setup_amplifier_mocks()


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Create temporary storage directory for tests.

    Automatically cleaned up after test completes.

    Example:
        >>> def test_storage(temp_storage_dir):
        ...     file = temp_storage_dir / "test.json"
        ...     file.write_text('{"key": "value"}')
        ...     assert file.exists()
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_storage_env(temp_storage_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock AMPLIFIERD_HOME environment variable to use temp directory.

    This ensures tests use isolated storage and don't interfere with
    real data or other tests.

    Args:
        temp_storage_dir: Temporary directory fixture
        monkeypatch: pytest monkeypatch fixture

    Returns:
        Path to temporary storage directory

    Example:
        >>> def test_with_isolated_storage(mock_storage_env):
        ...     from amplifier_library.storage.paths import get_root_dir
        ...     root = get_root_dir()
        ...     assert root == mock_storage_env
    """
    monkeypatch.setenv("AMPLIFIERD_HOME", str(temp_storage_dir))
    return temp_storage_dir


@pytest.fixture
def session_manager(mock_storage_env: Path):
    """Create SessionManager with isolated storage.

    Uses temporary directory for storage, ensuring test isolation.

    Example:
        >>> def test_session_creation(session_manager):
        ...     session = session_manager.create_session(session_id="test", profile_name="default")
        ...     assert session.id is not None
    """
    from amplifier_library.sessions.manager import SessionManager

    # SessionManager expects a state directory and adds /sessions to it
    # To match what get_state_dir() returns, we need to pass state/ subdirectory
    state_dir = mock_storage_env / "state"
    return SessionManager(storage_dir=state_dir)


@pytest.fixture
def sample_session(session_manager):
    """Create a sample session for testing.

    Creates a session with default profile.

    Returns:
        Session object ready for testing

    Example:
        >>> def test_with_session(sample_session):
        ...     assert sample_session.profile_name == "default"
        ...     assert sample_session.message_count == 0
    """
    import uuid

    return session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="default")


@pytest.fixture
def mock_amplifier_module():
    """Mock the amplifier_core module to avoid actual LLM calls.

    Provides a mock AmplifierSession that returns predictable test data
    without making network requests.

    Example:
        >>> def test_execution(mock_amplifier_module):
        ...     from amplifier_core import AmplifierSession
        ...     session = AmplifierSession({"test": "config"})
        ...     # Returns mock data, no actual API calls
    """

    class MockCoordinator:
        """Mock coordinator with mount and capability methods."""

        def __init__(self):
            """Initialize with empty capabilities dict."""
            self._capabilities = {}

        async def mount(self, mount_point: str, module: Any) -> None:
            """Mock mount - does nothing."""

        def register_capability(self, name: str, value: Any) -> None:
            """Mock register_capability - stores in dict."""
            self._capabilities[name] = value

        def get_capability(self, name: str) -> Any:
            """Mock get_capability - retrieves from dict."""
            return self._capabilities.get(name)

    class MockAmplifierSession:
        """Mock AmplifierSession for testing without LLM API calls."""

        def __init__(self, config: dict[str, Any], *args: Any, **kwargs: Any) -> None:
            # Accept any config to avoid validation errors
            self.config = config
            self.args = args
            self.kwargs = kwargs
            self.messages: list[dict[str, str]] = []
            self.coordinator = MockCoordinator()  # Create instance

        async def initialize(self) -> None:
            """Mock initialization."""
            # No initialization needed for mock

        async def execute(self, prompt: str) -> str:
            """Mock execute method that returns predictable test content.

            Args:
                prompt: User prompt (stored but not used)

            Returns:
                Mock response string
            """
            self.messages.append({"role": "user", "content": prompt})
            return "This is a mocked response from amplifier-core."

        def get_transcript(self) -> list[dict[str, str]]:
            """Get conversation transcript.

            Returns:
                List of message dictionaries
            """
            return self.messages

    # Create mock module
    mock_module = types.ModuleType("amplifier_core")
    mock_module.AmplifierSession = MockAmplifierSession  # type: ignore

    # Add ModuleLoader mock (simple class that does nothing)
    class MockModuleLoader:
        def __init__(self, *args, **kwargs):
            """Mock ModuleLoader for testing."""
            self.args = args
            self.kwargs = kwargs

    mock_module.ModuleLoader = MockModuleLoader  # type: ignore

    # Inject into sys.modules
    sys.modules["amplifier_core"] = mock_module

    yield mock_module

    # Cleanup
    if "amplifier_core" in sys.modules:
        del sys.modules["amplifier_core"]


@pytest.fixture
def sample_context() -> dict[str, Any]:
    """Sample context data for testing.

    Returns:
        Dictionary with sample context values

    Example:
        >>> def test_with_context(sample_context):
        ...     assert "user_id" in sample_context
        ...     assert sample_context["environment"] == "test"
    """
    return {
        "user_id": "test-user-123",
        "environment": "test",
        "feature_flags": {
            "streaming": True,
            "debug_mode": True,
        },
        "metadata": {
            "client_version": "1.0.0",
            "test_run": True,
        },
    }


@pytest.fixture
def sample_messages() -> list[dict[str, str]]:
    """Sample message transcript for testing.

    Returns:
        List of message dictionaries

    Example:
        >>> def test_transcript(sample_messages):
        ...     assert len(sample_messages) == 3
        ...     assert sample_messages[0]["role"] == "user"
    """
    return [
        {"role": "user", "content": "Hello, can you help me?"},
        {"role": "assistant", "content": "Of course! What do you need help with?"},
        {"role": "user", "content": "I need to write a Python function."},
    ]
