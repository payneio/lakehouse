"""Integration tests for module API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.modules import get_module_discovery_service


class MockModuleDiscoveryService:
    """Mock ModuleDiscoveryService for testing."""

    _mock_modules = {
        "openai": {
            "id": "openai",
            "type": "provider",
            "name": "OpenAI Provider",
            "location": "/path/to/providers/openai.py",
            "collection": "core",
            "description": "OpenAI LLM provider",
            "configSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "api_key": {"type": "string"},
                },
            },
        },
        "anthropic": {
            "id": "anthropic",
            "type": "provider",
            "name": "Anthropic Provider",
            "location": "/path/to/providers/anthropic.py",
            "collection": "core",
        },
        "bash": {
            "id": "bash",
            "type": "tool",
            "name": "Bash Tool",
            "location": "/path/to/tools/bash.py",
            "collection": "core",
            "description": "Execute bash commands",
        },
        "git": {
            "id": "git",
            "type": "tool",
            "name": "Git Tool",
            "location": "/path/to/tools/git.py",
            "collection": None,
        },
        "pre-commit": {
            "id": "pre-commit",
            "type": "hook",
            "name": "Pre-commit Hook",
            "location": "/path/to/hooks/pre-commit.py",
            "collection": "core",
        },
        "parallel": {
            "id": "parallel",
            "type": "orchestrator",
            "name": "Parallel Orchestrator",
            "location": "/path/to/orchestrators/parallel.py",
            "collection": "core",
            "description": "Run tasks in parallel",
            "configSchema": {
                "type": "object",
                "properties": {
                    "max_workers": {"type": "integer"},
                },
            },
        },
    }

    async def list_all_modules(self, type_filter: str | None = None) -> list[dict[str, Any]]:
        """List all modules with optional type filter."""
        modules = list(self._mock_modules.values())
        if type_filter:
            modules = [m for m in modules if m["type"] == type_filter]
        return modules

    async def list_providers(self) -> list[dict[str, Any]]:
        """List provider modules."""
        return [m for m in self._mock_modules.values() if m["type"] == "provider"]

    async def list_hooks(self) -> list[dict[str, Any]]:
        """List hook modules."""
        return [m for m in self._mock_modules.values() if m["type"] == "hook"]

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tool modules."""
        return [m for m in self._mock_modules.values() if m["type"] == "tool"]

    async def list_orchestrators(self) -> list[dict[str, Any]]:
        """List orchestrator modules."""
        return [m for m in self._mock_modules.values() if m["type"] == "orchestrator"]

    async def get_module_details(self, module_id: str) -> dict[str, Any]:
        """Get module details by ID."""
        if module_id in self._mock_modules:
            return self._mock_modules[module_id]
        raise ValueError(f"Module not found: {module_id}")

    async def add_module_source(self, module_id: str, source: str, scope: str = "project") -> dict[str, Any]:
        """Add source override for module."""
        if module_id == "error-module":
            raise Exception("Failed to add source")
        return {"module_id": module_id, "source": source, "scope": scope}

    async def update_module_source(self, module_id: str, source: str, scope: str = "project") -> dict[str, Any]:
        """Update source override for module."""
        return {"module_id": module_id, "source": source, "scope": scope}

    async def remove_module_source(self, module_id: str, scope: str = "project") -> dict[str, Any]:
        """Remove source override for module."""
        if module_id == "nonexistent":
            raise ValueError(f"Source override not found for {module_id}")
        return {"removed": True}


@pytest.fixture
def override_module_discovery_service():
    """Override ModuleDiscoveryService dependency with mock."""
    app.dependency_overrides[get_module_discovery_service] = lambda: MockModuleDiscoveryService()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_module_discovery_service):
    """Create FastAPI test client with mocked dependencies."""
    return TestClient(app)


@pytest.mark.integration
class TestModulesAPI:
    """Test module API endpoints."""

    def test_list_modules_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/ returns 200."""
        response = client.get("/api/v1/modules/")

        assert response.status_code == 200

    def test_list_modules_returns_all_types(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/ returns all module types."""
        response = client.get("/api/v1/modules/")

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6

        types = {m["type"] for m in data}
        assert "provider" in types
        assert "tool" in types
        assert "hook" in types
        assert "orchestrator" in types

    def test_list_modules_with_provider_filter(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/?type=provider filters by type."""
        response = client.get("/api/v1/modules/?type=provider")

        data = response.json()
        assert len(data) == 2
        assert all(m["type"] == "provider" for m in data)
        ids = {m["id"] for m in data}
        assert "openai" in ids
        assert "anthropic" in ids

    def test_list_modules_with_tool_filter(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/?type=tool filters by type."""
        response = client.get("/api/v1/modules/?type=tool")

        data = response.json()
        assert len(data) == 2
        assert all(m["type"] == "tool" for m in data)
        ids = {m["id"] for m in data}
        assert "bash" in ids
        assert "git" in ids

    def test_list_modules_with_hook_filter(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/?type=hook filters by type."""
        response = client.get("/api/v1/modules/?type=hook")

        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "hook"
        assert data[0]["id"] == "pre-commit"

    def test_list_modules_with_orchestrator_filter(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/?type=orchestrator filters by type."""
        response = client.get("/api/v1/modules/?type=orchestrator")

        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "orchestrator"
        assert data[0]["id"] == "parallel"

    def test_list_providers_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/providers returns 200."""
        response = client.get("/api/v1/modules/providers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(m["type"] == "provider" for m in data)

    def test_list_hooks_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/hooks returns 200."""
        response = client.get("/api/v1/modules/hooks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "hook"

    def test_list_tools_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/tools returns 200."""
        response = client.get("/api/v1/modules/tools")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(m["type"] == "tool" for m in data)

    def test_list_orchestrators_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/orchestrators returns 200."""
        response = client.get("/api/v1/modules/orchestrators")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "orchestrator"

    def test_get_module_returns_details(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/{id} returns module details."""
        response = client.get("/api/v1/modules/openai")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "openai"
        assert data["type"] == "provider"
        assert data["name"] == "OpenAI Provider"
        assert data["location"] == "/path/to/providers/openai.py"
        assert data["collection"] == "core"
        assert data["description"] == "OpenAI LLM provider"
        assert "configSchema" in data
        assert data["configSchema"]["type"] == "object"

    def test_get_module_without_collection(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/{id} for module without collection."""
        response = client.get("/api/v1/modules/git")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "git"
        assert data["collection"] is None

    def test_get_module_404_for_nonexistent(self, client: TestClient) -> None:
        """Test GET /api/v1/modules/{id} returns 404 for nonexistent."""
        response = client.get("/api/v1/modules/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_module_info_schema(self, client: TestClient) -> None:
        """Test ModuleInfo objects have required fields."""
        response = client.get("/api/v1/modules/")

        data = response.json()
        for module in data:
            assert "id" in module
            assert "type" in module
            assert "name" in module
            assert "location" in module
            assert isinstance(module["id"], str)
            assert isinstance(module["type"], str)
            assert isinstance(module["name"], str)
            assert isinstance(module["location"], str)
            assert module["type"] in ["provider", "hook", "tool", "orchestrator"]

    def test_module_details_schema(self, client: TestClient) -> None:
        """Test ModuleDetails objects have required fields."""
        response = client.get("/api/v1/modules/openai")

        data = response.json()
        assert "id" in data
        assert "type" in data
        assert "name" in data
        assert "location" in data
        assert "collection" in data
        assert "description" in data
        assert "configSchema" in data

    def test_module_with_minimal_details(self, client: TestClient) -> None:
        """Test module with minimal details (no description/schema)."""
        response = client.get("/api/v1/modules/anthropic")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "anthropic"
        assert data["type"] == "provider"
        assert "name" in data
        assert "location" in data

    def test_all_module_types_accessible(self, client: TestClient) -> None:
        """Test all module types are accessible via type-specific endpoints."""
        endpoints = [
            ("/api/v1/modules/providers", "provider"),
            ("/api/v1/modules/hooks", "hook"),
            ("/api/v1/modules/tools", "tool"),
            ("/api/v1/modules/orchestrators", "orchestrator"),
        ]

        for endpoint, expected_type in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0
            assert all(m["type"] == expected_type for m in data)

    def test_module_collection_metadata(self, client: TestClient) -> None:
        """Test modules include collection metadata where applicable."""
        response = client.get("/api/v1/modules/")

        data = response.json()
        core_modules = [m for m in data if m["collection"] == "core"]
        assert len(core_modules) == 5

        standalone_modules = [m for m in data if m["collection"] is None]
        assert len(standalone_modules) == 1
        assert standalone_modules[0]["id"] == "git"

    def test_add_module_source_success(self, client: TestClient) -> None:
        """Test POST /api/v1/modules/{module_id}/sources adds source override."""
        response = client.post(
            "/api/v1/modules/openai/sources",
            json={"source": "file:///custom/openai.py", "scope": "project"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["module_id"] == "openai"
        assert data["source"] == "file:///custom/openai.py"
        assert data["scope"] == "project"

    def test_add_module_source_failure(self, client: TestClient) -> None:
        """Test POST /api/v1/modules/{module_id}/sources returns 500 on error."""
        response = client.post(
            "/api/v1/modules/error-module/sources",
            json={"source": "file:///custom/error.py", "scope": "project"},
        )

        assert response.status_code == 500
        assert "failed to add source" in response.json()["detail"].lower()

    def test_update_module_source_success(self, client: TestClient) -> None:
        """Test PUT /api/v1/modules/{module_id}/sources updates source override."""
        response = client.put(
            "/api/v1/modules/openai/sources",
            json={"source": "file:///updated/openai.py", "scope": "project"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["module_id"] == "openai"
        assert data["source"] == "file:///updated/openai.py"
        assert data["scope"] == "project"

    def test_remove_module_source_success(self, client: TestClient) -> None:
        """Test DELETE /api/v1/modules/{module_id}/sources removes override."""
        response = client.delete("/api/v1/modules/openai/sources?scope=project")

        assert response.status_code == 200
        data = response.json()
        assert data["removed"] is True

    def test_remove_module_source_not_found(self, client: TestClient) -> None:
        """Test DELETE /api/v1/modules/{module_id}/sources returns 404."""
        response = client.delete("/api/v1/modules/nonexistent/sources?scope=project")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_add_provider_source_success(self, client: TestClient) -> None:
        """Test adding provider source via type-specific endpoint."""
        response = client.post(
            "/api/v1/modules/providers/test-provider/sources",
            json={"source": "/custom/provider", "scope": "project"},
        )
        assert response.status_code == 201

    def test_update_provider_source_success(self, client: TestClient) -> None:
        """Test updating provider source via type-specific endpoint."""
        response = client.put(
            "/api/v1/modules/providers/test-provider/sources",
            json={"source": "/new/provider", "scope": "project"},
        )
        assert response.status_code == 200

    def test_remove_provider_source_success(self, client: TestClient) -> None:
        """Test removing provider source via type-specific endpoint."""
        response = client.delete(
            "/api/v1/modules/providers/test-provider/sources",
            params={"scope": "project"},
        )
        assert response.status_code == 200

    def test_add_hook_source_success(self, client: TestClient) -> None:
        """Test adding hook source via type-specific endpoint."""
        response = client.post(
            "/api/v1/modules/hooks/test-hook/sources",
            json={"source": "/custom/hook", "scope": "project"},
        )
        assert response.status_code == 201

    def test_add_tool_source_success(self, client: TestClient) -> None:
        """Test adding tool source via type-specific endpoint."""
        response = client.post(
            "/api/v1/modules/tools/test-tool/sources",
            json={"source": "/custom/tool", "scope": "project"},
        )
        assert response.status_code == 201

    def test_add_orchestrator_source_success(self, client: TestClient) -> None:
        """Test adding orchestrator source via type-specific endpoint."""
        response = client.post(
            "/api/v1/modules/orchestrators/test-orchestrator/sources",
            json={"source": "/custom/orchestrator", "scope": "project"},
        )
        assert response.status_code == 201
