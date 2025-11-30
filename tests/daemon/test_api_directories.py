"""API integration tests for directory browsing endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.directories import get_service
from amplifierd.services.amplified_directory_service import AmplifiedDirectoryService


@pytest.fixture
def test_root(tmp_path: Path) -> Path:
    """Create test root directory."""
    root = tmp_path / "test_root"
    root.mkdir()
    return root


@pytest.fixture
def mock_service(test_root: Path) -> AmplifiedDirectoryService:
    """Create real service with test root."""
    return AmplifiedDirectoryService(test_root)


@pytest.fixture
def override_service(mock_service: AmplifiedDirectoryService):
    """Override service dependency with test service."""
    app.dependency_overrides[get_service] = lambda: mock_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_service) -> TestClient:
    """FastAPI test client with mocked dependencies."""
    return TestClient(app)


@pytest.mark.integration
class TestDirectoriesAPI:
    """Test directory browsing API endpoints."""

    # --- List Directory Endpoint Tests ---

    def test_list_root_directories_success(self, client: TestClient, test_root: Path) -> None:
        """Test GET /api/v1/directories/list lists root level directories."""
        # Create test directories
        (test_root / "project1").mkdir()
        (test_root / "project2").mkdir()
        (test_root / "project3").mkdir()
        # Create a file to verify it's filtered
        (test_root / "file.txt").touch()

        response = client.get("/api/v1/directories/list")

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == ""
        assert data["parent_path"] is None
        assert set(data["directories"]) == {"project1", "project2", "project3"}

    def test_list_subdirectories_success(self, client: TestClient, test_root: Path) -> None:
        """Test listing directories within a subdirectory."""
        # Create nested structure
        parent = test_root / "parent"
        parent.mkdir()
        (parent / "child1").mkdir()
        (parent / "child2").mkdir()

        response = client.get("/api/v1/directories/list", params={"path": "parent"})

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == "parent"
        assert data["parent_path"] == ""
        assert set(data["directories"]) == {"child1", "child2"}

    def test_list_empty_directory(self, client: TestClient, test_root: Path) -> None:
        """Test list empty directory returns empty list."""
        (test_root / "empty").mkdir()

        response = client.get("/api/v1/directories/list", params={"path": "empty"})

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == "empty"
        assert data["parent_path"] == ""
        assert data["directories"] == []

    def test_list_filters_files(self, client: TestClient, test_root: Path) -> None:
        """Test that only directories are returned, not files."""
        (test_root / "dir1").mkdir()
        (test_root / "file1.txt").touch()
        (test_root / "file2.md").touch()

        response = client.get("/api/v1/directories/list")

        assert response.status_code == 200
        data = response.json()
        assert data["directories"] == ["dir1"]

    def test_list_filters_hidden_dirs(self, client: TestClient, test_root: Path) -> None:
        """Test that hidden directories are filtered."""
        (test_root / "visible").mkdir()
        (test_root / ".hidden").mkdir()
        (test_root / ".amplified").mkdir()
        (test_root / ".git").mkdir()

        response = client.get("/api/v1/directories/list")

        assert response.status_code == 200
        data = response.json()
        assert data["directories"] == ["visible"]

    def test_list_invalid_path_absolute(self, client: TestClient) -> None:
        """Test that absolute paths are rejected with 400."""
        response = client.get("/api/v1/directories/list", params={"path": "/absolute/path"})

        assert response.status_code == 400
        assert "absolute" in response.json()["detail"].lower()

    def test_list_invalid_path_traversal(self, client: TestClient) -> None:
        """Test that .. paths are rejected with 400."""
        response = client.get("/api/v1/directories/list", params={"path": "../escape"})

        assert response.status_code == 400
        assert ".." in response.json()["detail"]

    def test_list_nonexistent_path_404(self, client: TestClient) -> None:
        """Test that non-existent paths return 404."""
        response = client.get("/api/v1/directories/list", params={"path": "nonexistent"})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_parent_path_at_root(self, client: TestClient, test_root: Path) -> None:
        """Test that parent_path is null at root."""
        (test_root / "dir1").mkdir()

        response = client.get("/api/v1/directories/list")

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == ""
        assert data["parent_path"] is None

    def test_list_parent_path_in_subdir(self, client: TestClient, test_root: Path) -> None:
        """Test that parent_path is correct in subdirectories."""
        (test_root / "parent" / "child").mkdir(parents=True)

        response = client.get("/api/v1/directories/list", params={"path": "parent/child"})

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == "parent/child"
        assert data["parent_path"] == "parent"

    def test_list_parent_path_one_level_deep(self, client: TestClient, test_root: Path) -> None:
        """Test parent_path for directory one level deep."""
        (test_root / "single").mkdir()

        response = client.get("/api/v1/directories/list", params={"path": "single"})

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == "single"
        assert data["parent_path"] == ""

    def test_list_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that unexpected errors return 500."""
        original_validate = mock_service._validate_and_resolve_path

        def failing_validate(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        mock_service._validate_and_resolve_path = failing_validate

        try:
            response = client.get("/api/v1/directories/list", params={"path": "test"})

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service._validate_and_resolve_path = original_validate

    # --- Create Directory Endpoint Tests ---

    def test_create_directory_success(self, client: TestClient, test_root: Path) -> None:
        """Test POST /api/v1/directories/create creates new directory."""
        response = client.post("/api/v1/directories/create", json={"relative_path": "new_project"})

        assert response.status_code == 201
        data = response.json()
        assert data["created_path"] == "new_project"
        assert "absolute_path" in data
        assert (test_root / "new_project").exists()
        assert (test_root / "new_project").is_dir()

    def test_create_nested_directory(self, client: TestClient, test_root: Path) -> None:
        """Test creating directory with parent directories."""
        response = client.post("/api/v1/directories/create", json={"relative_path": "parent/child/grandchild"})

        assert response.status_code == 201
        data = response.json()
        assert data["created_path"] == "parent/child/grandchild"
        assert (test_root / "parent" / "child" / "grandchild").exists()

    def test_create_existing_directory_idempotent(self, client: TestClient, test_root: Path) -> None:
        """Test that creating existing directory is idempotent."""
        (test_root / "existing").mkdir()

        response = client.post("/api/v1/directories/create", json={"relative_path": "existing"})

        assert response.status_code == 201
        data = response.json()
        assert data["created_path"] == "existing"

    def test_create_invalid_path_absolute(self, client: TestClient) -> None:
        """Test that absolute paths are rejected with 400."""
        response = client.post("/api/v1/directories/create", json={"relative_path": "/absolute/path"})

        assert response.status_code == 400
        assert "absolute" in response.json()["detail"].lower()

    def test_create_invalid_path_traversal(self, client: TestClient) -> None:
        """Test that .. paths are rejected with 400."""
        response = client.post("/api/v1/directories/create", json={"relative_path": "../../escape"})

        assert response.status_code == 400
        assert ".." in response.json()["detail"]

    def test_create_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that unexpected errors during creation return 500."""
        original_validate = mock_service._validate_and_resolve_path

        def failing_validate(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        mock_service._validate_and_resolve_path = failing_validate

        try:
            response = client.post("/api/v1/directories/create", json={"relative_path": "error_test"})

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service._validate_and_resolve_path = original_validate

    # --- Integration Tests ---

    def test_list_after_create(self, client: TestClient) -> None:
        """Test that created directory appears in list."""
        # Create directory
        create_response = client.post("/api/v1/directories/create", json={"relative_path": "new_dir"})
        assert create_response.status_code == 201

        # List root
        list_response = client.get("/api/v1/directories/list")
        assert list_response.status_code == 200
        assert "new_dir" in list_response.json()["directories"]

    def test_navigate_created_directory(self, client: TestClient) -> None:
        """Test creating directory and listing its contents."""
        # Create parent
        client.post("/api/v1/directories/create", json={"relative_path": "parent"})

        # Create children
        client.post("/api/v1/directories/create", json={"relative_path": "parent/child1"})
        client.post("/api/v1/directories/create", json={"relative_path": "parent/child2"})

        # List parent
        response = client.get("/api/v1/directories/list", params={"path": "parent"})

        assert response.status_code == 200
        data = response.json()
        assert set(data["directories"]) == {"child1", "child2"}

    def test_create_multiple_levels(self, client: TestClient) -> None:
        """Test creating parent/child/grandchild and listing each level."""
        # Create nested structure
        client.post("/api/v1/directories/create", json={"relative_path": "level1/level2/level3"})

        # List root
        root_response = client.get("/api/v1/directories/list")
        assert "level1" in root_response.json()["directories"]

        # List level1
        level1_response = client.get("/api/v1/directories/list", params={"path": "level1"})
        assert "level2" in level1_response.json()["directories"]

        # List level2
        level2_response = client.get("/api/v1/directories/list", params={"path": "level1/level2"})
        assert "level3" in level2_response.json()["directories"]

    # --- Edge Cases ---

    def test_list_with_special_characters_in_names(self, client: TestClient, test_root: Path) -> None:
        """Test listing directories with special but valid characters."""
        (test_root / "project-123").mkdir()
        (test_root / "project_abc").mkdir()
        (test_root / "project.test").mkdir()

        response = client.get("/api/v1/directories/list")

        assert response.status_code == 200
        data = response.json()
        assert set(data["directories"]) == {"project-123", "project_abc", "project.test"}

    def test_create_with_special_characters(self, client: TestClient, test_root: Path) -> None:
        """Test creating directories with special but valid characters."""
        valid_names = [
            "project-with-dashes",
            "project_with_underscores",
            "project.with.dots",
        ]

        for name in valid_names:
            response = client.post("/api/v1/directories/create", json={"relative_path": name})
            assert response.status_code == 201, f"Failed for: {name}"
            assert (test_root / name).exists()

    def test_list_with_url_encoded_path(self, client: TestClient, test_root: Path) -> None:
        """Test listing directory with URL-encoded path."""
        (test_root / "path with spaces").mkdir()

        response = client.get("/api/v1/directories/list", params={"path": "path with spaces"})

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == "path with spaces"

    def test_create_with_spaces_in_name(self, client: TestClient, test_root: Path) -> None:
        """Test creating directory with spaces in name."""
        response = client.post("/api/v1/directories/create", json={"relative_path": "my project"})

        assert response.status_code == 201
        assert (test_root / "my project").exists()

    def test_list_deeply_nested_structure(self, client: TestClient, test_root: Path) -> None:
        """Test listing in deeply nested directory structure."""
        deep_path = test_root / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)
        (deep_path / "final").mkdir()

        response = client.get("/api/v1/directories/list", params={"path": "a/b/c/d/e"})

        assert response.status_code == 200
        data = response.json()
        assert data["directories"] == ["final"]
        assert data["parent_path"] == "a/b/c/d"

    def test_list_mixed_content(self, client: TestClient, test_root: Path) -> None:
        """Test listing directory with mix of files, visible dirs, and hidden dirs."""
        test_dir = test_root / "mixed"
        test_dir.mkdir()
        (test_dir / "visible1").mkdir()
        (test_dir / "visible2").mkdir()
        (test_dir / ".hidden").mkdir()
        (test_dir / "file.txt").touch()
        (test_dir / ".dotfile").touch()

        response = client.get("/api/v1/directories/list", params={"path": "mixed"})

        assert response.status_code == 200
        data = response.json()
        assert set(data["directories"]) == {"visible1", "visible2"}

    def test_create_then_navigate_full_workflow(self, client: TestClient) -> None:
        """Test complete workflow: create structure, navigate, verify."""
        # Create project structure
        client.post("/api/v1/directories/create", json={"relative_path": "myproject"})
        client.post("/api/v1/directories/create", json={"relative_path": "myproject/src"})
        client.post("/api/v1/directories/create", json={"relative_path": "myproject/tests"})
        client.post("/api/v1/directories/create", json={"relative_path": "myproject/docs"})

        # List root to find project
        root = client.get("/api/v1/directories/list").json()
        assert "myproject" in root["directories"]

        # Navigate into project
        project = client.get("/api/v1/directories/list", params={"path": "myproject"}).json()
        assert set(project["directories"]) == {"src", "tests", "docs"}
        assert project["parent_path"] == ""

        # Navigate into src
        src = client.get("/api/v1/directories/list", params={"path": "myproject/src"}).json()
        assert src["directories"] == []
        assert src["parent_path"] == "myproject"

    def test_list_empty_path_parameter(self, client: TestClient, test_root: Path) -> None:
        """Test that empty path parameter lists root."""
        (test_root / "test").mkdir()

        response = client.get("/api/v1/directories/list", params={"path": ""})

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == ""
        assert "test" in data["directories"]

    def test_list_file_returns_403(self, client: TestClient, test_root: Path) -> None:
        """Test that listing a file path returns 403."""
        (test_root / "file.txt").touch()

        response = client.get("/api/v1/directories/list", params={"path": "file.txt"})

        assert response.status_code == 403
        assert "not a directory" in response.json()["detail"].lower()

    def test_create_already_exists_with_content(self, client: TestClient, test_root: Path) -> None:
        """Test creating directory that already exists with content doesn't error."""
        existing = test_root / "existing"
        existing.mkdir()
        (existing / "child").mkdir()

        response = client.post("/api/v1/directories/create", json={"relative_path": "existing"})

        assert response.status_code == 201
        # Verify content is preserved
        assert (existing / "child").exists()

    def test_list_sorting_order(self, client: TestClient, test_root: Path) -> None:
        """Test that directories are returned in sorted order."""
        for name in ["zebra", "apple", "middle", "banana"]:
            (test_root / name).mkdir()

        response = client.get("/api/v1/directories/list")

        assert response.status_code == 200
        data = response.json()
        assert data["directories"] == ["apple", "banana", "middle", "zebra"]

    def test_roundtrip_create_list_navigate(self, client: TestClient) -> None:
        """Test complete roundtrip: create nested, list each level, verify structure."""
        # Create nested structure
        create_resp = client.post("/api/v1/directories/create", json={"relative_path": "a/b/c"})
        assert create_resp.status_code == 201

        # List root
        root = client.get("/api/v1/directories/list").json()
        assert "a" in root["directories"]
        assert root["parent_path"] is None

        # List a
        a_dir = client.get("/api/v1/directories/list", params={"path": "a"}).json()
        assert "b" in a_dir["directories"]
        assert a_dir["parent_path"] == ""

        # List b
        b_dir = client.get("/api/v1/directories/list", params={"path": "a/b"}).json()
        assert "c" in b_dir["directories"]
        assert b_dir["parent_path"] == "a"

        # List c (empty)
        c_dir = client.get("/api/v1/directories/list", params={"path": "a/b/c"}).json()
        assert c_dir["directories"] == []
        assert c_dir["parent_path"] == "a/b"
