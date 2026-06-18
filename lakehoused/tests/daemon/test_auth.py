"""Integration tests for the password login gate.

The autouse ``disable_auth_gate`` fixture (see tests/conftest.py) turns the gate
off by default; the ``gate_enabled`` fixture below re-enables it with a known
password so these tests can exercise the real enforcement path.
"""

import pytest
from fastapi.testclient import TestClient

from lakehoused.main import app


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def gate_enabled(monkeypatch: pytest.MonkeyPatch) -> str:
    """Enable the gate with a known password and return it."""
    password = "test-secret"
    monkeypatch.setattr("lakehoused.auth.get_auth_password", lambda: password)
    return password


@pytest.mark.integration
class TestAuthGate:
    """Test the password login gate."""

    def test_status_disabled_by_default(self, client: TestClient) -> None:
        """With no password configured, auth is reported as not required."""
        resp = client.get("/api/v1/auth/status")
        assert resp.status_code == 200
        assert resp.json() == {"auth_required": False}

    def test_status_enabled_when_configured(self, client: TestClient, gate_enabled: str) -> None:
        """With a password configured, auth is reported as required."""
        resp = client.get("/api/v1/auth/status")
        assert resp.status_code == 200
        assert resp.json() == {"auth_required": True}

    def test_login_wrong_password_rejected(self, client: TestClient, gate_enabled: str) -> None:
        """An incorrect password is rejected with 401."""
        resp = client.post("/api/v1/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401

    def test_login_correct_password_returns_token(self, client: TestClient, gate_enabled: str) -> None:
        """The correct password returns a non-empty session token."""
        resp = client.post("/api/v1/auth/login", json={"password": gate_enabled})
        assert resp.status_code == 200
        assert resp.json()["token"]

    def test_protected_endpoint_blocked_without_token(self, client: TestClient, gate_enabled: str) -> None:
        """API requests without a token are blocked when the gate is on."""
        assert client.get("/api/v1/status").status_code == 401

    def test_protected_endpoint_allowed_with_bearer_token(self, client: TestClient, gate_enabled: str) -> None:
        """A valid bearer token grants access."""
        token = client.post("/api/v1/auth/login", json={"password": gate_enabled}).json()["token"]
        resp = client.get("/api/v1/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_protected_endpoint_allowed_with_token_query_param(
        self, client: TestClient, gate_enabled: str
    ) -> None:
        """A valid token passed as a query param grants access (used by SSE)."""
        token = client.post("/api/v1/auth/login", json={"password": gate_enabled}).json()["token"]
        resp = client.get(f"/api/v1/status?token={token}")
        assert resp.status_code == 200

    def test_health_is_public_even_when_gated(self, client: TestClient, gate_enabled: str) -> None:
        """The health endpoint stays public so liveness probes never get 401."""
        assert client.get("/api/v1/health").status_code == 200
