"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"
