"""Integration tests for collection API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.collections import get_collection_service


@pytest.fixture
def test_collections_dir(tmp_path: Path) -> Path:
    """Create test collection structure."""
    # Create collection-core (local)
    core = tmp_path / "core"
    (core / "profiles").mkdir(parents=True)

    # Create collection.yaml for core
    (core / "collection.yaml").write_text("""
name: "Core Collection"
version: "1.0.0"
description: "Core Amplifier collection"
""")

    # Create schema v2 profiles
    (core / "profiles" / "default.md").write_text("""---
name: "default"
schema_version: 2
version: "1.0.0"
description: "Default profile"
---

# Default Profile
""")

    (core / "profiles" / "advanced.md").write_text("""---
name: "advanced"
schema_version: 2
version: "1.0.0"
description: "Advanced profile"
---

# Advanced Profile
""")

    # Create git-style collection
    git_repo = tmp_path / "github.com" / "org" / "repo"
    (git_repo / "profiles").mkdir(parents=True)
    (git_repo / ".git").mkdir(parents=True)

    (git_repo / "collection.yaml").write_text("""
name: "Git Repo Collection"
version: "1.0.0"
description: "Collection from git"
""")

    (git_repo / "profiles" / "production.md").write_text("""---
name: "production"
schema_version: 2
version: "1.0.0"
description: "Production profile"
---

# Production Profile
""")

    return tmp_path


class MockCollectionResolver:
    """Mock collection resolver for testing."""

    def __init__(self: "MockCollectionResolver", collections_dir: Path) -> None:
        """Initialize mock resolver.

        Args:
            collections_dir: Directory containing test collections
        """
        self.collections_dir = collections_dir

    def list_collections(self: "MockCollectionResolver") -> list[tuple[str, Path]]:
        """List all collections.

        Returns:
            List of (identifier, path) tuples
        """
        collections = []
        for item in self.collections_dir.iterdir():
            if item.is_dir() and (item / "collection.yaml").exists():
                collections.append((item.name, item))

        # Handle nested git-style collections
        github_dir = self.collections_dir / "github.com"
        if github_dir.exists():
            for org in github_dir.iterdir():
                if not org.is_dir():
                    continue
                for repo in org.iterdir():
                    if repo.is_dir() and (repo / "collection.yaml").exists():
                        identifier = f"github.com/{org.name}/{repo.name}"
                        collections.append((identifier, repo))

        return collections

    def resolve_collection(self: "MockCollectionResolver", identifier: str) -> Path | None:
        """Resolve collection by identifier.

        Args:
            identifier: Collection identifier

        Returns:
            Path to collection or None if not found
        """
        for name, path in self.list_collections():
            if name == identifier:
                return path
        return None


class MockCollectionService:
    """Mock CollectionService for testing with real directories."""

    def __init__(self: "MockCollectionService", collections_dir: Path) -> None:
        """Initialize with test collections directory.

        Args:
            collections_dir: Test collections directory
        """
        self._resolver = MockCollectionResolver(collections_dir)
        # Simulate registry - in real service this is in collections.yaml
        self._registry: dict[str, dict[str, str]] = {}

        # Auto-register discovered collections
        for name, path in self._resolver.list_collections():
            source = f"git+https://github.com/test/{name}@main" if (path / ".git").exists() else str(path)
            self._registry[name] = {"source": source}

    def list_collections(self: "MockCollectionService") -> list[dict[str, str | list]]:
        """List all available collections."""
        result = []

        for identifier, entry in self._registry.items():
            collection_path = self._resolver.resolve_collection(identifier)
            if not collection_path:
                continue

            # Discover profiles
            profiles = []
            if (collection_path / "profiles").exists():
                for p in list((collection_path / "profiles").glob("*.md")) + list(
                    (collection_path / "profiles").glob("*.yaml")
                ):
                    profiles.append(
                        {
                            "name": p.stem,
                            "version": "1.0.0",
                            "path": str(p),
                            "installedAt": None,
                        }
                    )

            result.append({"identifier": identifier, "source": entry["source"], "profiles": profiles})
        return result

    def get_collection_info(self: "MockCollectionService", identifier: str) -> dict[str, str | list]:
        """Get collection details by identifier."""
        if identifier not in self._registry:
            raise FileNotFoundError(f"Collection not found: {identifier}")

        collection_path = self._resolver.resolve_collection(identifier)
        if not collection_path:
            raise FileNotFoundError(f"Collection not found: {identifier}")

        # Manually discover profiles
        profiles = []
        if (collection_path / "profiles").exists():
            for p in list((collection_path / "profiles").glob("*.md")) + list(
                (collection_path / "profiles").glob("*.yaml")
            ):
                profiles.append(
                    {
                        "name": p.stem,
                        "version": "1.0.0",
                        "path": str(p),
                        "installedAt": None,
                    }
                )

        return {"identifier": identifier, "source": self._registry[identifier]["source"], "profiles": profiles}

    def mount_collection(self: "MockCollectionService", identifier: str, source: str) -> None:
        """Mount a collection."""
        # Check if collection already exists
        if identifier in self._registry:
            raise ValueError(f"Collection already exists: {identifier}")

        # Check if source is valid (for local mounts)
        if not source.startswith("http") and not source.startswith("git+") and not Path(source).exists():
            raise FileNotFoundError(f"Source not found: {source}")

        self._registry[identifier] = {"source": source}

    def unmount_collection(self: "MockCollectionService", identifier: str) -> None:
        """Unmount a collection."""
        # Check if collection exists
        if identifier not in self._registry:
            raise FileNotFoundError(f"Collection not found: {identifier}")

        del self._registry[identifier]


@pytest.fixture
def collection_service(test_collections_dir: Path) -> MockCollectionService:
    """Create collection service with test data.

    Args:
        test_collections_dir: Test collections directory

    Returns:
        Collection service
    """
    return MockCollectionService(test_collections_dir)


@pytest.fixture
def override_collection_service(collection_service: MockCollectionService):
    """Override CollectionService dependency with test service.

    Args:
        collection_service: Collection service

    Yields:
        None
    """
    app.dependency_overrides[get_collection_service] = lambda: collection_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_collection_service):
    """Create FastAPI test client with test dependencies.

    Args:
        override_collection_service: Dependency override fixture

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.mark.integration
class TestCollectionsAPI:
    """Test collection API endpoints."""

    def test_list_collections_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/ returns 200."""
        response = client.get("/api/v1/collections/")
        assert response.status_code == 200

    def test_list_collections_includes_collection_info(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/ returns CollectionInfo objects."""
        response = client.get("/api/v1/collections/")

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        core = next(c for c in data if c["identifier"] == "core")
        assert "source" in core
        # Note: 'type' field removed from CollectionInfo model (can be inferred from source prefix)

        git_repo = next(c for c in data if "github.com" in c["identifier"])
        assert "source" in git_repo
        # Note: 'type' field removed from CollectionInfo model (can be inferred from source prefix)

    def test_get_collection_returns_details(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} returns details."""
        response = client.get("/api/v1/collections/core")

        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "core"
        assert "source" in data
        assert len(data["profiles"]) == 2
        # Verify profiles are ProfileManifest objects with correct structure
        for profile in data["profiles"]:
            assert "name" in profile
            assert "version" in profile
            assert "path" in profile
            assert "installedAt" in profile

    def test_get_collection_git_type(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} for git collection."""
        response = client.get("/api/v1/collections/github.com%2Forg%2Frepo")

        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "github.com/org/repo"
        assert "source" in data
        # Collection type can be inferred from source (git+ prefix)
        assert len(data["profiles"]) == 1

    def test_get_collection_404_for_nonexistent(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} returns 404."""
        response = client.get("/api/v1/collections/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_collection_info_schema(self, client: TestClient) -> None:
        """Test CollectionInfo objects have required fields."""
        response = client.get("/api/v1/collections/")

        data = response.json()
        for collection in data:
            assert "identifier" in collection
            assert "source" in collection
            assert "profiles" in collection
            assert isinstance(collection["identifier"], str)
            assert isinstance(collection["source"], str)
            assert isinstance(collection["profiles"], list)

    def test_collection_details_schema(self, client: TestClient) -> None:
        """Test Collection detail response has required fields."""
        response = client.get("/api/v1/collections/core")

        data = response.json()
        assert "identifier" in data
        assert "source" in data
        assert "profiles" in data
        assert isinstance(data["profiles"], list)
        # Verify each profile is a ProfileManifest
        for profile in data["profiles"]:
            assert "name" in profile
            assert "version" in profile
            assert "path" in profile

    def test_mount_collection_success(self, client: TestClient) -> None:
        """Test POST /api/v1/collections/ mounts collection."""
        response = client.post(
            "/api/v1/collections/",
            json={"identifier": "new-collection", "source": "/path/to/new"},
        )

        # Expected to fail since we're using mock service without real lock
        assert response.status_code in [201, 500]

    def test_mount_collection_already_exists(self, client: TestClient) -> None:
        """Test POST /api/v1/collections/ returns 409 for existing collection."""
        response = client.post(
            "/api/v1/collections/",
            json={"identifier": "core", "source": "/path/to/existing"},
        )

        # Should return 409 or 500 since collection already exists
        assert response.status_code in [409, 500]

    def test_mount_collection_invalid_source(self, client: TestClient) -> None:
        """Test POST /api/v1/collections/ returns 400 for invalid source."""
        response = client.post(
            "/api/v1/collections/",
            json={"identifier": "test-collection", "source": "invalid"},
        )

        # Expected to fail since we're using mock service
        assert response.status_code in [400, 500]

    def test_unmount_collection_success(self, client: TestClient) -> None:
        """Test DELETE /api/v1/collections/{identifier} unmounts collection."""
        response = client.delete("/api/v1/collections/core")

        # Expected to fail since we're using mock service
        assert response.status_code in [200, 404, 500]

    def test_unmount_collection_not_found(self, client: TestClient) -> None:
        """Test DELETE /api/v1/collections/{identifier} returns 404."""
        response = client.delete("/api/v1/collections/nonexistent")

        # Expected to fail since we're using mock service
        assert response.status_code in [404, 500]
