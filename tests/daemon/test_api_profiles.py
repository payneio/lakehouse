"""Integration tests for profile API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.profiles import get_profile_service


class MockProfileService:
    """Mock ProfileService for testing."""

    async def list_profiles(self) -> list[dict[str, Any]]:
        """List all profiles."""
        return [
            {
                "name": "default",
                "source": "system",
                "isActive": True,
            },
            {
                "name": "custom",
                "source": "user",
                "isActive": False,
            },
        ]

    async def get_profile(self, name: str) -> dict[str, Any]:
        """Get profile by name."""
        if name == "default":
            return {
                "name": "default",
                "version": "1.0.0",
                "description": "Default system profile",
                "source": "system",
                "isActive": True,
                "inheritanceChain": [],
                "providers": [
                    {
                        "module": "openai",
                        "source": "amplifier://providers/openai",
                        "config": {"model": "gpt-4"},
                    }
                ],
                "tools": [
                    {
                        "module": "bash",
                        "source": "amplifier://tools/bash",
                        "config": None,
                    }
                ],
                "hooks": [],
            }
        if name == "custom":
            return {
                "name": "custom",
                "version": "1.0.0",
                "description": "Custom user profile",
                "source": "user",
                "isActive": False,
                "inheritanceChain": ["default"],
                "providers": [],
                "tools": [],
                "hooks": [
                    {
                        "module": "pre-commit",
                        "source": "file:///path/to/hook",
                        "config": {"enabled": True},
                    }
                ],
            }
        raise FileNotFoundError(f"Profile not found: {name}")

    async def get_active_profile(self) -> dict[str, Any] | None:
        """Get active profile."""
        return {
            "name": "default",
            "source": "system",
            "isActive": True,
        }

    async def activate_profile(self, name: str) -> dict[str, Any]:
        """Activate a profile."""
        if name == "custom":
            return {"name": name, "status": "activated"}
        raise ValueError(f"Profile not found: {name}")

    async def deactivate_profile(self) -> dict[str, Any]:
        """Deactivate current profile."""
        return {"deactivated": True}


@pytest.fixture
def override_profile_service():
    """Override ProfileService dependency with mock."""
    app.dependency_overrides[get_profile_service] = lambda: MockProfileService()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_profile_service):
    """Create FastAPI test client with mocked dependencies."""
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

    def test_get_profile_with_inheritance(self, client: TestClient) -> None:
        """Test GET /api/v1/profiles/{name} includes inheritance chain."""
        response = client.get("/api/v1/profiles/custom")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "custom"
        assert data["inheritanceChain"] == ["default"]
        assert len(data["hooks"]) == 1
        assert data["hooks"][0]["module"] == "pre-commit"

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
        assert data["deactivated"] is True
