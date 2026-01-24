"""amplifierd - REST API daemon for amplifier-core.

This package provides a FastAPI-based daemon that exposes amplifier-core
functionality via REST API with SSE streaming support.
"""

__version__ = "0.1.0"

from .main import app

__all__ = ["app"]
