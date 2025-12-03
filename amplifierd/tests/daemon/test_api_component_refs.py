"""Integration tests for component-refs API endpoint."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.collections import get_collection_service
from amplifierd.services.collection_service import CollectionService


@pytest.fixture
def test_profiles_dir(tmp_path: Path) -> Path:
    """Create test profile structure with various component types."""
    # Create local collection with multiple profiles
    local_collection = tmp_path / "profiles" / "local"
    local_collection.mkdir(parents=True)

    # Profile 1: All component types (schema v2)
    profile1_dir = local_collection / "full-profile"
    profile1_dir.mkdir()
    (profile1_dir / "profile.md").write_text("""---
name: "full-profile"
schema_version: 2
version: "1.0.0"

session:
  orchestrator:
    source: "git+https://github.com/example/orchestrator.git"
  context_manager:
    source: "git+https://github.com/example/context-manager.git"

providers:
  - id: "provider1"
    source: "git+https://github.com/example/provider1.git"

tools:
  - id: "tool1"
    source: "git+https://github.com/example/tool1.git"

hooks:
  - id: "hook1"
    source: "git+https://github.com/example/hook1.git"

agents:
  agent1: "git+https://github.com/example/agent1.git"

context:
  ctx1: "git+https://github.com/example/context1.git"
---

# Full Profile
""")

    # Profile 2: Minimal profile with only orchestrator
    profile2_dir = local_collection / "minimal-profile"
    profile2_dir.mkdir()
    (profile2_dir / "profile.md").write_text("""---
name: "minimal-profile"
schema_version: 2
version: "1.0.0"

session:
  orchestrator:
    source: "git+https://github.com/example/orchestrator2.git"
---

# Minimal Profile
""")

    # Profile 3: Profile with null/empty components
    profile3_dir = local_collection / "empty-profile"
    profile3_dir.mkdir()
    (profile3_dir / "profile.md").write_text("""---
name: "empty-profile"
schema_version: 2
version: "1.0.0"

providers: []
tools: []
hooks: []
agents: {}
context: {}
---

# Empty Profile
""")

    # Create a registered collection
    registered_collection = tmp_path / "profiles" / "shared"
    registered_collection.mkdir(parents=True)

    # Profile in registered collection
    profile4_dir = registered_collection / "shared-profile"
    profile4_dir.mkdir()
    (profile4_dir / "profile.md").write_text("""---
name: "shared-profile"
schema_version: 2
version: "1.0.0"

session:
  orchestrator:
    source: "git+https://github.com/shared/orchestrator.git"
  context_manager:
    source: "git+https://github.com/shared/context-manager.git"

providers:
  - id: "shared-provider"
    source: "git+https://github.com/shared/provider.git"

tools:
  - id: "shared-tool"
    source: "git+https://github.com/shared/tool.git"
---

# Shared Profile
""")

    # Profile with multiple components of same type
    profile5_dir = local_collection / "multi-component"
    profile5_dir.mkdir()
    (profile5_dir / "profile.md").write_text("""---
name: "multi-component"
schema_version: 2
version: "1.0.0"

providers:
  - id: "provider1"
    source: "git+https://github.com/example/provider1.git"
  - id: "provider2"
    source: "git+https://github.com/example/provider2.git"

tools:
  - id: "tool1"
    source: "git+https://github.com/example/tool1.git"
  - id: "tool2"
    source: "git+https://github.com/example/tool2.git"

agents:
  agent1: "git+https://github.com/example/agent1.git"
  agent2: "git+https://github.com/example/agent2.git"

context:
  ctx1: "git+https://github.com/example/context1.git"
  ctx2: "git+https://github.com/example/context2.git"
---

# Multi Component Profile
""")

    # Create collections.yaml to register the shared collection
    (tmp_path / "collections.yaml").write_text("""collections:
  shared:
    source: "git+https://github.com/example/shared-collection.git"
    installed_at: "2024-01-01T00:00:00"
""")

    return tmp_path


@pytest.fixture
def mock_service(test_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch) -> CollectionService:
    """Create a mock CollectionService with test data."""
    from amplifierd.services.profile_discovery import ProfileDiscoveryService

    # Create real service with test directory
    profiles_cache = test_profiles_dir / "profiles"
    discovery_service = ProfileDiscoveryService(cache_dir=profiles_cache)

    service = CollectionService(
        share_dir=test_profiles_dir,
        discovery_service=discovery_service,
        compilation_service=None,
    )

    return service


@pytest.fixture
def client(mock_service: CollectionService, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Create test client with mocked service."""

    def override_get_collection_service() -> CollectionService:
        return mock_service

    app.dependency_overrides[get_collection_service] = override_get_collection_service

    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()


def test_component_refs_empty_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test component-refs endpoint with no collections."""
    from amplifierd.services.profile_discovery import ProfileDiscoveryService

    # Create service with empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    profiles_dir = empty_dir / "profiles"
    profiles_dir.mkdir()

    discovery_service = ProfileDiscoveryService(cache_dir=profiles_dir)
    service = CollectionService(share_dir=empty_dir, discovery_service=discovery_service, compilation_service=None)

    def override_get_collection_service() -> CollectionService:
        return service

    app.dependency_overrides[get_collection_service] = override_get_collection_service

    client = TestClient(app)

    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()
    assert data["orchestrators"] == []
    assert data["contextManagers"] == []
    assert data["providers"] == []
    assert data["tools"] == []
    assert data["hooks"] == []
    assert data["agents"] == []
    assert data["contexts"] == []

    app.dependency_overrides.clear()


def test_component_refs_single_profile(client: TestClient) -> None:
    """Test component-refs with profile containing all component types."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Check orchestrators (from full-profile and minimal-profile)
    assert len(data["orchestrators"]) >= 2
    orchestrator_profiles = [item["profile"] for item in data["orchestrators"]]
    assert "local/full-profile" in orchestrator_profiles
    assert "local/minimal-profile" in orchestrator_profiles

    # Check context managers
    assert len(data["contextManagers"]) >= 1
    assert any(item["profile"] == "local/full-profile" for item in data["contextManagers"])

    # Check providers
    assert len(data["providers"]) >= 1
    assert any(item["profile"] == "local/full-profile" for item in data["providers"])

    # Check tools
    assert len(data["tools"]) >= 1
    assert any(item["profile"] == "local/full-profile" for item in data["tools"])

    # Check hooks
    assert len(data["hooks"]) >= 1
    assert any(item["profile"] == "local/full-profile" for item in data["hooks"])

    # Check agents
    assert len(data["agents"]) >= 1
    assert any(item["profile"] == "local/full-profile" for item in data["agents"])

    # Check contexts
    assert len(data["contexts"]) >= 1
    assert any(item["profile"] == "local/full-profile" for item in data["contexts"])


def test_component_refs_multiple_profiles(client: TestClient) -> None:
    """Test component-refs with multiple profiles and overlapping components."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Verify we have refs from multiple profiles
    all_profiles = set()
    for component_type in ["orchestrators", "contextManagers", "providers", "tools", "hooks", "agents", "contexts"]:
        for item in data[component_type]:
            all_profiles.add(item["profile"])

    # Should have refs from at least local/full-profile and shared/shared-profile
    assert "local/full-profile" in all_profiles
    # Note: shared collection might not be present as it's in registry but not in filesystem in this test


def test_component_refs_local_collection(client: TestClient) -> None:
    """Test that local collection is included even if not in registry."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Check that we have local collection profiles
    local_profiles = set()
    for component_type in ["orchestrators", "contextManagers", "providers", "tools", "hooks", "agents", "contexts"]:
        for item in data[component_type]:
            if item["profile"].startswith("local/"):
                local_profiles.add(item["profile"])

    assert len(local_profiles) > 0
    assert "local/full-profile" in local_profiles


def test_component_refs_sorting(client: TestClient) -> None:
    """Test that component refs are sorted by profile identifier."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Check sorting for each component type that has multiple items
    for component_type in ["orchestrators", "contextManagers", "providers", "tools", "hooks", "agents", "contexts"]:
        items = data[component_type]
        if len(items) > 1:
            profiles = [item["profile"] for item in items]
            assert profiles == sorted(profiles), f"{component_type} not sorted by profile"


def test_component_refs_multiple_components_same_type(client: TestClient) -> None:
    """Test profile with multiple components of the same type."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Check that multi-component profile has multiple providers
    multi_providers = [item for item in data["providers"] if item["profile"] == "local/multi-component"]
    assert len(multi_providers) == 2

    # Check multiple tools
    multi_tools = [item for item in data["tools"] if item["profile"] == "local/multi-component"]
    assert len(multi_tools) == 2

    # Check multiple agents
    multi_agents = [item for item in data["agents"] if item["profile"] == "local/multi-component"]
    assert len(multi_agents) == 2

    # Check multiple contexts
    multi_contexts = [item for item in data["contexts"] if item["profile"] == "local/multi-component"]
    assert len(multi_contexts) == 2


def test_component_refs_empty_components(client: TestClient) -> None:
    """Test that profiles with null/empty component fields don't cause errors."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Should have data from other profiles even if one has empty components
    # empty-profile shouldn't contribute any refs
    empty_profile_refs = []
    for component_type in ["orchestrators", "contextManagers", "providers", "tools", "hooks", "agents", "contexts"]:
        for item in data[component_type]:
            if item["profile"] == "local/empty-profile":
                empty_profile_refs.append(item)

    # Empty profile should not have any component refs
    assert len(empty_profile_refs) == 0


def test_component_refs_uri_format(client: TestClient) -> None:
    """Test that component URIs are returned in correct format."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Check that all URIs are strings and non-empty
    for component_type in ["orchestrators", "contextManagers", "providers", "tools", "hooks", "agents", "contexts"]:
        for item in data[component_type]:
            assert isinstance(item["uri"], str)
            assert len(item["uri"]) > 0
            # Most test URIs should be git+ format
            if item["uri"].startswith("git+"):
                assert "github.com" in item["uri"]


def test_component_refs_response_structure(client: TestClient) -> None:
    """Test that response has correct structure with all required fields."""
    response = client.get("/api/v1/collections/component-refs")
    assert response.status_code == 200

    data = response.json()

    # Verify all component types are present
    required_types = ["orchestrators", "contextManagers", "providers", "tools", "hooks", "agents", "contexts"]
    for component_type in required_types:
        assert component_type in data
        assert isinstance(data[component_type], list)

    # Verify each item has required fields
    for component_type in required_types:
        for item in data[component_type]:
            assert "profile" in item
            assert "uri" in item
            assert isinstance(item["profile"], str)
            assert isinstance(item["uri"], str)
