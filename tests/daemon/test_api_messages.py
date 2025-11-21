"""
Integration tests for messages API endpoints.

Tests message sending and transcript retrieval.
"""

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app


@pytest.fixture
def client(mock_storage_env):
    """Create FastAPI test client with isolated storage."""
    return TestClient(app)


@pytest.fixture
def session_id(client: TestClient) -> str:
    """Create a test session and return its ID."""
    response = client.post("/api/v1/sessions", json={"profile": "default", "context": {}})
    return response.json()["id"]


@pytest.mark.integration
class TestMessagesAPI:
    """Test message API endpoints."""

    def test_send_message_returns_201(self, client: TestClient, session_id: str) -> None:
        """Test POST /api/v1/sessions/{id}/messages creates message."""
        response = client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": "Hello, world!"})

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"
        assert data["content"] == "Hello, world!"
        assert "timestamp" in data

    def test_send_message_404_for_nonexistent_session(self, client: TestClient) -> None:
        """Test POST /messages returns 404 for nonexistent session."""
        response = client.post("/api/v1/sessions/nonexistent-id/messages", json={"content": "Test"})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_messages_returns_transcript(self, client: TestClient, session_id: str) -> None:
        """Test GET /api/v1/sessions/{id}/messages returns transcript."""
        # Send some messages first
        client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": "First message"})
        client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": "Second message"})

        # Get transcript
        response = client.get(f"/api/v1/sessions/{session_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"] == session_id
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "First message"
        assert data["messages"][1]["content"] == "Second message"

    def test_get_messages_empty_for_new_session(self, client: TestClient, session_id: str) -> None:
        """Test GET /messages returns empty transcript for new session."""
        response = client.get(f"/api/v1/sessions/{session_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []

    def test_get_messages_404_for_nonexistent_session(self, client: TestClient) -> None:
        """Test GET /messages returns 404 for nonexistent session."""
        response = client.get("/api/v1/sessions/nonexistent-id/messages")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_messages_preserve_order(self, client: TestClient, session_id: str) -> None:
        """Test messages are returned in order they were sent."""
        messages = ["First", "Second", "Third", "Fourth"]

        for msg in messages:
            client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": msg})

        response = client.get(f"/api/v1/sessions/{session_id}/messages")
        transcript = response.json()["messages"]

        for i, msg in enumerate(messages):
            assert transcript[i]["content"] == msg

    def test_messages_include_metadata(self, client: TestClient, session_id: str) -> None:
        """Test messages include timestamp and metadata."""
        response = client.post(f"/api/v1/sessions/{session_id}/messages", json={"content": "Test message"})

        data = response.json()
        assert "timestamp" in data
        assert "metadata" in data
        assert isinstance(data["metadata"], dict)

    def test_multiple_sessions_isolated(self, client: TestClient) -> None:
        """Test messages in different sessions are isolated."""
        # Create two sessions
        session1 = client.post("/api/v1/sessions", json={"profile": "default", "context": {}}).json()["id"]

        session2 = client.post("/api/v1/sessions", json={"profile": "default", "context": {}}).json()["id"]

        # Add messages to session1
        client.post(f"/api/v1/sessions/{session1}/messages", json={"content": "Session 1 message"})

        # Add messages to session2
        client.post(f"/api/v1/sessions/{session2}/messages", json={"content": "Session 2 message"})

        # Verify isolation
        transcript1 = client.get(f"/api/v1/sessions/{session1}/messages").json()
        transcript2 = client.get(f"/api/v1/sessions/{session2}/messages").json()

        assert len(transcript1["messages"]) == 1
        assert len(transcript2["messages"]) == 1
        assert transcript1["messages"][0]["content"] == "Session 1 message"
        assert transcript2["messages"][0]["content"] == "Session 2 message"
