"""
Integration tests for session API endpoints.

Tests session CRUD operations via HTTP endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app


@pytest.fixture
def client(mock_storage_env):
    """Create FastAPI test client with isolated storage."""
    return TestClient(app)


@pytest.mark.integration
class TestSessionsAPI:
    """Test session API endpoints."""

    def test_create_session_returns_201(self, client: TestClient) -> None:
        """Test POST /api/v1/sessions creates session."""
        response = client.post("/api/v1/sessions", json={"profile": "default", "context": {}})

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["profile"] == "default"
        assert data["messageCount"] == 0

    def test_create_session_with_context(self, client: TestClient) -> None:
        """Test POST /api/v1/sessions stores context data."""
        context = {"user_id": "123", "environment": "test"}

        response = client.post("/api/v1/sessions", json={"profile": "test-profile", "context": context})

        assert response.status_code == 201
        data = response.json()
        assert data["context"] == context
        assert data["profile"] == "test-profile"

    def test_list_sessions_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions returns list."""
        # Create a session first
        client.post("/api/v1/sessions", json={"profile": "default", "context": {}})

        response = client.get("/api/v1/sessions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_sessions_includes_session_info(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions returns SessionInfo objects."""
        # Create session
        create_response = client.post("/api/v1/sessions", json={"profile": "test", "context": {}})
        session_id = create_response.json()["id"]

        # List sessions
        response = client.get("/api/v1/sessions")

        data = response.json()
        session = next(s for s in data if s["id"] == session_id)

        assert session["profile"] == "test"
        assert "createdAt" in session
        assert "updatedAt" in session
        assert session["messageCount"] == 0

    def test_get_session_returns_details(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions/{id} returns session details."""
        # Create session
        create_response = client.post("/api/v1/sessions", json={"profile": "default", "context": {"key": "value"}})
        session_id = create_response.json()["id"]

        # Get session
        response = client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["profile"] == "default"
        assert data["context"]["key"] == "value"

    def test_get_session_404_for_nonexistent(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions/{id} returns 404 for nonexistent session."""
        response = client.get("/api/v1/sessions/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_resume_session_returns_details(self, client: TestClient) -> None:
        """Test POST /api/v1/sessions/{id}/resume returns session details."""
        # Create session
        create_response = client.post("/api/v1/sessions", json={"profile": "default", "context": {}})
        session_id = create_response.json()["id"]

        # Resume session
        response = client.post(f"/api/v1/sessions/{session_id}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id

    def test_resume_session_404_for_nonexistent(self, client: TestClient) -> None:
        """Test POST /api/v1/sessions/{id}/resume returns 404 for nonexistent."""
        response = client.post("/api/v1/sessions/nonexistent-id/resume")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_session_returns_204(self, client: TestClient) -> None:
        """Test DELETE /api/v1/sessions/{id} deletes session."""
        # Create session
        create_response = client.post("/api/v1/sessions", json={"profile": "default", "context": {}})
        session_id = create_response.json()["id"]

        # Delete session
        response = client.delete(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 204

    def test_delete_session_actually_removes(self, client: TestClient) -> None:
        """Test DELETE /api/v1/sessions/{id} removes session from storage."""
        # Create session
        create_response = client.post("/api/v1/sessions", json={"profile": "default", "context": {}})
        session_id = create_response.json()["id"]

        # Delete session
        client.delete(f"/api/v1/sessions/{session_id}")

        # Verify deleted
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 404

    def test_delete_session_404_for_nonexistent(self, client: TestClient) -> None:
        """Test DELETE /api/v1/sessions/{id} returns 404 for nonexistent."""
        response = client.delete("/api/v1/sessions/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_session_lifecycle_via_api(self, client: TestClient) -> None:
        """Test complete session lifecycle through API."""
        # Create
        response = client.post("/api/v1/sessions", json={"profile": "test", "context": {"step": 1}})
        assert response.status_code == 201
        session_id = response.json()["id"]

        # Get
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["profile"] == "test"

        # List
        response = client.get("/api/v1/sessions")
        assert any(s["id"] == session_id for s in response.json())

        # Delete
        response = client.delete(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 404
