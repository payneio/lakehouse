"""API tests for mount plan endpoints."""

from datetime import UTC
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app


@pytest.fixture
def mock_mount_plan() -> dict:
    """Sample mount plan for testing.

    Returns:
        Sample mount plan dict with realistic data matching MountPlan model
    """
    return {
        "format_version": "1.0",
        "session": {
            "session_id": "preview_abc12345",
            "profile_id": "foundation/base",
            "created_at": datetime.now(UTC).isoformat(),
            "settings": {
                "bundle_name": "foundation/base",
            },
        },
        "mount_points": [
            {
                "mount_type": "embedded",
                "module_id": "foundation/base.agents.test-agent",
                "module_type": "agent",
                "content": "# Test Agent",
            },
        ],
    }


@pytest.fixture
def mock_bundle_manager(mock_mount_plan: dict) -> MagicMock:
    """Mock bundle manager for testing.

    Args:
        mock_mount_plan: Sample mount plan fixture

    Returns:
        Mock bundle manager
    """
    manager = MagicMock()

    async def mock_generate_mount_plan(*args, **kwargs):
        return mock_mount_plan

    manager.generate_mount_plan = mock_generate_mount_plan
    return manager


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client.

    Returns:
        Test client for making API requests
    """
    return TestClient(app)


@pytest.mark.integration
class TestMountPlansAPI:
    """Test mount plan API endpoints."""

    def test_generate_mount_plan_success(
        self, client: TestClient, mock_mount_plan: dict, mock_bundle_manager: MagicMock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate returns 201 with valid response."""
        with (
            patch("amplifier_library.bundles.LakehouseBundleManager", return_value=mock_bundle_manager),
            patch("amplifierd.config.loader.load_secrets") as mock_secrets,
        ):
            mock_secrets.return_value.api_keys = {}

            response = client.post(
                "/api/v1/mount-plans/generate",
                json={"bundle_name": "foundation/base", "amplified_dir": "/tmp/test"},
            )

            assert response.status_code == 201
            data = response.json()

            # Verify structure exists (exact fields depend on mount plan response model)
            assert data is not None

    def test_generate_mount_plan_missing_bundle(
        self, client: TestClient, mock_bundle_manager: MagicMock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate returns 404 for missing bundle."""

        async def raise_not_found(*args, **kwargs):
            raise FileNotFoundError("Bundle not found: nonexistent")

        mock_bundle_manager.generate_mount_plan = raise_not_found

        with (
            patch("amplifier_library.bundles.LakehouseBundleManager", return_value=mock_bundle_manager),
            patch("amplifierd.config.loader.load_secrets") as mock_secrets,
        ):
            mock_secrets.return_value.api_keys = {}

            response = client.post(
                "/api/v1/mount-plans/generate",
                json={"bundle_name": "nonexistent", "amplified_dir": "/tmp/test"},
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_generate_mount_plan_invalid_bundle(
        self, client: TestClient, mock_bundle_manager: MagicMock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate returns 400 for invalid bundle."""

        async def raise_value_error(*args, **kwargs):
            raise ValueError("Invalid bundle format")

        mock_bundle_manager.generate_mount_plan = raise_value_error

        with (
            patch("amplifier_library.bundles.LakehouseBundleManager", return_value=mock_bundle_manager),
            patch("amplifierd.config.loader.load_secrets") as mock_secrets,
        ):
            mock_secrets.return_value.api_keys = {}

            response = client.post(
                "/api/v1/mount-plans/generate",
                json={"bundle_name": "invalid//format", "amplified_dir": "/tmp/test"},
            )

            assert response.status_code == 400
            assert "invalid" in response.json()["detail"].lower()

    def test_generate_mount_plan_internal_error(
        self, client: TestClient, mock_bundle_manager: MagicMock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate returns 500 for unexpected errors."""

        async def raise_runtime_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        mock_bundle_manager.generate_mount_plan = raise_runtime_error

        with (
            patch("amplifier_library.bundles.LakehouseBundleManager", return_value=mock_bundle_manager),
            patch("amplifierd.config.loader.load_secrets") as mock_secrets,
        ):
            mock_secrets.return_value.api_keys = {}

            response = client.post(
                "/api/v1/mount-plans/generate",
                json={"bundle_name": "foundation/base", "amplified_dir": "/tmp/test"},
            )

            assert response.status_code == 500
            assert "failed to generate mount plan" in response.json()["detail"].lower()

    def test_generate_mount_plan_missing_bundle_name(self, client: TestClient) -> None:
        """Test POST /api/v1/mount-plans/generate returns 422 for missing bundle_name."""
        response = client.post("/api/v1/mount-plans/generate", json={})

        assert response.status_code == 422
