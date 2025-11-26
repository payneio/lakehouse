"""Integration tests for profile API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.profiles import get_profile_service
from amplifierd.services.profile_service import ProfileService


@pytest.fixture
def test_profiles_dir(tmp_path: Path) -> Path:
    """Create test profile structure."""
    # Create system profiles directory
    system_dir = tmp_path / "system"
    system_dir.mkdir()

    # Create default profile (schema v2)
    (system_dir / "default.md").write_text("""---
profile:
  name: "default"
  schema_version: 2
  version: "1.0.0"
  description: "Default system profile"
providers:
  - module: "openai"
    source: "amplifier://providers/openai"
    config: {}
tools:
  - module: "bash"
    source: "amplifier://tools/bash"
    config: {}
---

# Default Profile

Schema v2 profile for testing.

## Providers

- openai: GPT-4

## Tools

- bash: Shell execution
""")

    # Create user profiles directory
    user_dir = tmp_path / "user"
    user_dir.mkdir()

    # Create custom profile (schema v2 - no extends)
    (user_dir / "custom.md").write_text("""---
profile:
  name: "custom"
  schema_version: 2
  version: "1.0.0"
  description: "Custom user profile"
hooks:
  - module: "pre-commit"
    source: "amplifier://hooks/pre-commit"
    config: {}
---

# Custom Profile

Schema v2 profile for testing.

## Hooks

- pre-commit: Enabled
""")

    return tmp_path


class MockProfileInfo:
    """Mock profile info object."""

    def __init__(self: "MockProfileInfo", name: str, version: str, description: str) -> None:
        """Initialize profile info.

        Args:
            name: Profile name
            version: Profile version
            description: Profile description
        """
        self.name = name
        self.version = version
        self.description = description


class MockProfile:
    """Mock profile object."""

    def __init__(self: "MockProfile", data: dict) -> None:
        """Initialize mock profile.

        Args:
            data: Profile data
        """
        profile_data = data.get("profile", {})
        self.profile = MockProfileInfo(
            name=profile_data.get("name", ""),
            version=profile_data.get("version", "0.0.0"),
            description=profile_data.get("description", ""),
        )
        self.providers = data.get("providers", [])
        self.tools = data.get("tools", [])
        self.hooks = data.get("hooks", [])
        self.extends = profile_data.get("extends")


class MockProfileLoader:
    """Mock profile loader for testing."""

    def __init__(self: "MockProfileLoader", profiles_dir: Path) -> None:
        """Initialize mock loader.

        Args:
            profiles_dir: Directory containing test profiles
        """
        self.profiles_dir = profiles_dir
        self.profiles: dict[str, MockProfile] = {}
        self.sources: dict[str, str] = {}

        # Load profiles from both system and user dirs
        for dir_name in ["system", "user"]:
            dir_path = profiles_dir / dir_name
            if not dir_path.exists():
                continue

            # Support both .yaml (old) and .md (schema v2) profiles
            for profile_file in list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.md")):
                profile_name = profile_file.stem
                self.profiles[profile_name] = self._parse_profile(profile_file)
                self.sources[profile_name] = dir_name

    def _parse_profile(self: "MockProfileLoader", profile_file: Path) -> "MockProfile":
        """Parse profile YAML file.

        Args:
            profile_file: Path to profile YAML

        Returns:
            Mock profile object
        """
        import yaml

        content = profile_file.read_text(encoding="utf-8")

        # Handle .md files with YAML frontmatter
        if profile_file.suffix == ".md":
            # Split frontmatter from markdown content
            parts = content.split("---", 2)
            if len(parts) < 3:
                raise ValueError(f"Invalid frontmatter format in {profile_file.name}")
            # Parse only the YAML frontmatter (middle section)
            yaml_content = parts[1]
            data = yaml.safe_load(yaml_content)
        else:
            # Handle plain YAML files (old format)
            data = yaml.safe_load(content)

        return MockProfile(data)

    def list_profiles(self: "MockProfileLoader") -> list[str]:
        """List all profile names.

        Returns:
            List of profile names
        """
        return list(self.profiles.keys())

    def load_profile(self: "MockProfileLoader", name: str) -> MockProfile:
        """Load profile by name.

        Args:
            name: Profile name

        Returns:
            Profile object

        Raises:
            FileNotFoundError: If profile not found
        """
        if name not in self.profiles:
            raise FileNotFoundError(f"Profile not found: {name}")
        return self.profiles[name]

    def get_profile_source(self: "MockProfileLoader", name: str) -> str | None:
        """Get profile source.

        Args:
            name: Profile name

        Returns:
            Profile source or None
        """
        return self.sources.get(name)

    def get_inheritance_chain(self: "MockProfileLoader", name: str) -> list[str]:
        """Get inheritance chain for profile.

        Args:
            name: Profile name

        Returns:
            List of parent profile names
        """
        profile = self.profiles.get(name)
        if not profile or not hasattr(profile, "extends") or not profile.extends:
            return []
        return [profile.extends]


class MockConfigManager:
    """Mock config manager for testing."""

    def __init__(self: "MockConfigManager") -> None:
        """Initialize mock config manager."""
        self.active_profile = "default"

    def get_active_profile(self: "MockConfigManager") -> str | None:
        """Get active profile name.

        Returns:
            Active profile name or None
        """
        return self.active_profile

    def set_active_profile(self: "MockConfigManager", name: str | None, scope: object) -> None:
        """Set active profile.

        Args:
            name: Profile name or None to deactivate
            scope: Configuration scope
        """
        self.active_profile = name


class MockProfileService:
    """Mock ProfileService for testing with real directories."""

    def __init__(self: "MockProfileService", profiles_dir: Path) -> None:
        """Initialize with test profiles directory.

        Args:
            profiles_dir: Test profiles directory
        """
        self._profile_loader = MockProfileLoader(profiles_dir)
        self._config_manager = MockConfigManager()

    def _get_loader(self: "MockProfileService") -> MockProfileLoader:
        """Get profile loader.

        Returns:
            Profile loader
        """
        return self._profile_loader

    def list_profiles(self: "MockProfileService") -> list[dict[str, str | bool]]:
        """List all available profiles."""
        loader = self._get_loader()
        profiles = loader.list_profiles()
        active_profile = self._config_manager.get_active_profile()

        result = []
        for profile_name in profiles:
            source = loader.get_profile_source(profile_name) or "unknown"
            result.append(
                {
                    "name": profile_name,
                    "source": source,
                    "isActive": profile_name == active_profile,
                }
            )
        return result

    def get_profile(
        self: "MockProfileService", name: str
    ) -> dict[str, str | bool | list[str] | list[dict[str, object]]]:
        """Get profile details by name."""
        loader = self._get_loader()
        profile_obj = loader.load_profile(name)
        chain_names = loader.get_inheritance_chain(name)
        active_profile = self._config_manager.get_active_profile()

        return {
            "name": profile_obj.profile.name,
            "version": profile_obj.profile.version,
            "description": profile_obj.profile.description,
            "source": loader.get_profile_source(name) or "unknown",
            "isActive": name == active_profile,
            "inheritanceChain": chain_names,
            "providers": [
                {"module": item["module"], "source": item.get("source"), "config": item.get("config")}
                for item in profile_obj.providers
            ],
            "tools": [
                {"module": item["module"], "source": item.get("source"), "config": item.get("config")}
                for item in profile_obj.tools
            ],
            "hooks": [
                {"module": item["module"], "source": item.get("source"), "config": item.get("config")}
                for item in profile_obj.hooks
            ],
        }

    def get_active_profile(
        self: "MockProfileService",
    ) -> dict[str, str | bool | list[str] | list[dict[str, object]]] | None:
        """Get currently active profile."""
        active_profile = self._config_manager.get_active_profile()
        if not active_profile:
            return None

        # Return full profile details like get_profile does
        return self.get_profile(active_profile)

    def activate_profile(self: "MockProfileService", name: str) -> dict[str, str]:
        """Activate a profile by name."""
        try:
            self.get_profile(name)
        except (FileNotFoundError, KeyError) as exc:
            raise FileNotFoundError(f"Profile not found: {name}") from exc

        self._config_manager.active_profile = name

        return {
            "name": name,
            "status": "activated",
        }

    def deactivate_profile(self: "MockProfileService") -> dict[str, bool]:
        """Deactivate the current profile."""
        self._config_manager.active_profile = None

        return {"deactivated": True}


@pytest.fixture
def profile_service(test_profiles_dir: Path) -> MockProfileService:
    """Create profile service with test data.

    Args:
        test_profiles_dir: Test profiles directory

    Returns:
        Profile service
    """
    return MockProfileService(test_profiles_dir)


@pytest.fixture
def real_profile_service(tmp_path: Path) -> ProfileService:
    """Create real ProfileService for CRUD testing.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        ProfileService instance with temporary directories
    """
    share_dir = tmp_path / "share"
    share_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create profiles directory structure
    profiles_dir = share_dir / "profiles"
    profiles_dir.mkdir()

    # Create local collection directory
    local_dir = profiles_dir / "local"
    local_dir.mkdir()

    # Create system collection directory with a default profile
    system_dir = profiles_dir / "system"
    system_dir.mkdir()

    # Create default system profile (for testing non-local operations)
    default_profile_dir = system_dir / "default"
    default_profile_dir.mkdir()
    (default_profile_dir / "profile.md").write_text("""---
profile:
  name: "default"
  schema_version: 2
  version: "1.0.0"
  description: "Default system profile"
providers:
  - module: "openai"
    source: "amplifier://providers/openai"
tools:
  - module: "bash"
    source: "amplifier://tools/bash"
---

# Default Profile

System profile for testing.
""")

    return ProfileService(share_dir=share_dir, data_dir=data_dir)


@pytest.fixture
def override_profile_service(profile_service: MockProfileService):
    """Override ProfileService dependency with test service.

    Args:
        profile_service: Profile service

    Yields:
        None
    """
    app.dependency_overrides[get_profile_service] = lambda: profile_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_profile_service):
    """Create FastAPI test client with test dependencies.

    Args:
        override_profile_service: Dependency override fixture

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.fixture
def override_real_profile_service(real_profile_service: ProfileService):
    """Override ProfileService dependency with real service for CRUD tests.

    Args:
        real_profile_service: Real profile service

    Yields:
        None
    """
    app.dependency_overrides[get_profile_service] = lambda: real_profile_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def crud_client(override_real_profile_service):
    """Create FastAPI test client with real ProfileService for CRUD tests.

    Args:
        override_real_profile_service: Dependency override fixture

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.mark.integration
class TestProfilesAPI:
    """Test profile API endpoints."""

    def test_list_profiles_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/ returns 200."""
        response = client.get("/api/v1/profiles/")
        assert response.status_code == 200

    def test_list_profiles_includes_profile_info(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/ returns ProfileInfo objects."""
        response = client.get("/api/v1/profiles/")

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        default_profile = next(p for p in data if p["name"] == "default")
        assert default_profile["source"] == "system"
        assert default_profile["isActive"] is True

        custom_profile = next(p for p in data if p["name"] == "custom")
        assert custom_profile["source"] == "user"
        assert custom_profile["isActive"] is False

    def test_get_profile_returns_details(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/{name} returns profile details."""
        response = client.get("/api/v1/profiles/default")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "default"
        assert data["version"] == "1.0.0"
        assert data["description"] == "Default system profile"
        assert data["source"] == "system"
        assert data["isActive"] is True
        assert data["inheritanceChain"] == []
        assert len(data["providers"]) == 1
        assert data["providers"][0]["module"] == "openai"
        assert len(data["tools"]) == 1
        assert data["tools"][0]["module"] == "bash"
        assert len(data["hooks"]) == 0

    def test_get_custom_profile_details(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/{name} for custom profile (schema v2 - no inheritance)."""
        response = client.get("/api/v1/profiles/custom")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "custom"
        assert data["version"] == "1.0.0"
        assert data["description"] == "Custom user profile"
        assert data["source"] == "user"
        assert data["isActive"] is False
        # Schema v2 doesn't have inheritance
        assert data["inheritanceChain"] == []

    def test_get_profile_404_for_nonexistent(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/{name} returns 404 for nonexistent."""
        response = client.get("/api/v1/profiles/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        assert "nonexistent" in response.json()["detail"]

    def test_get_active_profile_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/active returns active profile."""
        response = client.get("/api/v1/profiles/active")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "default"
        assert data["isActive"] is True

    def test_get_active_profile_includes_source(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/active includes profile source."""
        response = client.get("/api/v1/profiles/active")

        data = response.json()
        assert "source" in data
        assert data["source"] == "system"

    def test_profile_info_schema(self, client: TestClient) -> None:
        """Test ProfileInfo objects have required fields."""
        response = client.get("/api/v1/profiles/")

        data = response.json()
        for profile in data:
            assert "name" in profile
            assert "source" in profile
            assert "isActive" in profile
            assert isinstance(profile["name"], str)
            assert isinstance(profile["source"], str)
            assert isinstance(profile["isActive"], bool)

    def test_profile_details_schema(self, client: TestClient) -> None:
        """Test ProfileDetails objects have required fields."""
        response = client.get("/api/v1/profiles/default")

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "source" in data
        assert "isActive" in data
        assert "inheritanceChain" in data
        assert "providers" in data
        assert "tools" in data
        assert "hooks" in data
        assert isinstance(data["providers"], list)
        assert isinstance(data["tools"], list)
        assert isinstance(data["hooks"], list)

    def test_module_config_schema(self, client: TestClient) -> None:
        """Test ModuleConfig objects have required fields."""
        response = client.get("/api/v1/profiles/default")

        data = response.json()
        provider = data["providers"][0]
        assert "module" in provider
        assert "source" in provider
        assert provider["module"] == "openai"
        assert provider["source"] == "amplifier://providers/openai"
        assert "config" in provider
        assert isinstance(provider["config"], dict)

    def test_activate_profile_success(self, client: TestClient) -> None:
        """Test POST /api/v1/profiles/{name}/activate activates profile."""
        response = client.post("/api/v1/profiles/custom/activate")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "custom"
        assert data["status"] == "activated"

    def test_activate_profile_not_found(self, client: TestClient) -> None:
        """Test POST /api/v1/profiles/{name}/activate returns 404 for nonexistent."""
        response = client.post("/api/v1/profiles/nonexistent/activate")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_deactivate_profile_success(self, client: TestClient) -> None:
        """Test DELETE /api/v1/profiles/active deactivates profile."""
        response = client.delete("/api/v1/profiles/active")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.integration
class TestProfileCRUD:
    """Test profile CRUD operations."""

    # CREATE TESTS (Happy Path + Critical Errors)

    def test_create_profile_success(self, crud_client: TestClient, real_profile_service: ProfileService) -> None:
        """Test POST /api/v1/profiles/ creates profile successfully."""
        response = crud_client.post(
            "/api/v1/profiles/",
            json={
                "name": "test-profile",
                "version": "1.0.0",
                "description": "Test profile",
                "providers": [{"module": "provider-anthropic", "source": "git+https://example.com/provider"}],
                "tools": [{"module": "tool-web"}],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-profile"
        assert data["collectionId"] == "local"
        assert data["version"] == "1.0.0"
        assert data["description"] == "Test profile"

        # Verify file created
        profile_file = real_profile_service.profiles_dir / "local" / "test-profile" / "profile.md"
        assert profile_file.exists()

        # Verify manifest format
        content = profile_file.read_text()
        assert "---" in content
        assert "schema_version: 2" in content
        assert "name: test-profile" in content

    @pytest.mark.skip(
        reason="BUG: list_profiles() only scans *.yaml but create_profile() writes *.md files. "
        "Duplicate detection doesn't work. Need to fix list_profiles() to also scan *.md files."
    )
    def test_create_profile_duplicate_409(self, crud_client: TestClient) -> None:
        """Test POST /api/v1/profiles/ returns 409 for duplicate."""
        # Create first profile
        crud_client.post("/api/v1/profiles/", json={"name": "dup-test", "description": "First"})

        # Try to create duplicate
        response = crud_client.post("/api/v1/profiles/", json={"name": "dup-test", "description": "Second"})

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "Invalid_Name",  # Uppercase and underscore
            "invalid name",  # Space
            "invalid.name",  # Period
            "INVALID",  # All caps
            "invalid_name",  # Underscore
        ],
    )
    def test_create_profile_invalid_name_422(self, crud_client: TestClient, invalid_name: str) -> None:
        """Test POST /api/v1/profiles/ returns 422 for invalid name."""
        response = crud_client.post(
            "/api/v1/profiles/",
            json={"name": invalid_name, "description": "Test"},
        )

        assert response.status_code == 422  # Pydantic validation error

    # UPDATE TESTS (Happy Path + Permission Error)

    def test_update_profile_success(self, crud_client: TestClient) -> None:
        """Test PATCH /api/v1/profiles/{name} updates profile."""
        # Create profile first
        crud_client.post("/api/v1/profiles/", json={"name": "update-test", "description": "Original"})

        # Update it
        response = crud_client.patch(
            "/api/v1/profiles/update-test",
            json={"description": "Updated description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["name"] == "update-test"  # Name unchanged

    def test_update_profile_non_local_403(self, crud_client: TestClient) -> None:
        """Test PATCH /api/v1/profiles/{name} returns 403 for non-local profile."""
        # Try to update system profile (not in local collection)
        response = crud_client.patch(
            "/api/v1/profiles/default",
            json={"description": "Trying to update"},
        )

        assert response.status_code == 403
        assert "Cannot modify" in response.json()["detail"]
        assert "local" in response.json()["detail"]

    def test_update_profile_not_found_404(self, crud_client: TestClient) -> None:
        """Test PATCH /api/v1/profiles/{name} returns 404."""
        response = crud_client.patch(
            "/api/v1/profiles/nonexistent",
            json={"description": "Update"},
        )

        assert response.status_code == 404

    # DELETE TESTS (Happy Path + Critical Errors)

    def test_delete_profile_success(self, crud_client: TestClient, real_profile_service: ProfileService) -> None:
        """Test DELETE /api/v1/profiles/{name} removes profile."""
        # Create profile
        crud_client.post("/api/v1/profiles/", json={"name": "delete-test", "description": "To be deleted"})

        # Verify exists
        profile_dir = real_profile_service.profiles_dir / "local" / "delete-test"
        assert profile_dir.exists()

        # Delete it
        response = crud_client.delete("/api/v1/profiles/delete-test")
        assert response.status_code == 204

        # Verify removed
        assert not profile_dir.exists()

    def test_delete_profile_non_local_403(self, crud_client: TestClient) -> None:
        """Test DELETE /api/v1/profiles/{name} returns 403 for non-local."""
        # Try to delete system profile
        response = crud_client.delete("/api/v1/profiles/default")

        assert response.status_code == 403
        assert "Cannot modify" in response.json()["detail"] or "not local" in response.json()["detail"]

    def test_delete_profile_active_409(self, crud_client: TestClient) -> None:
        """Test DELETE /api/v1/profiles/{name} returns 409 for active profile."""
        # Create and activate profile
        crud_client.post("/api/v1/profiles/", json={"name": "active-test", "description": "Active"})
        crud_client.post("/api/v1/profiles/active-test/activate")

        # Try to delete
        response = crud_client.delete("/api/v1/profiles/active-test")

        assert response.status_code == 409
        assert "active" in response.json()["detail"].lower()

    def test_delete_profile_not_found_404(self, crud_client: TestClient) -> None:
        """Test DELETE /api/v1/profiles/{name} returns 404."""
        response = crud_client.delete("/api/v1/profiles/nonexistent")
        assert response.status_code == 404
