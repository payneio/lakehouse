"""lakehoused - REST API daemon for the Lakehouse data platform.

This package provides a FastAPI-based daemon that exposes the Lakehouse
data platform (opencode-backed chat, sessions, projects) via REST API with
SSE streaming support.
"""

__version__ = "0.1.0"

# NOTE: intentionally does NOT import the FastAPI app here. Importing the package
# should be cheap and side-effect-free so lightweight consumers (e.g. the `lakehouse`
# CLI) don't boot the whole daemon (routers, models, logging). The daemon is launched
# via the explicit "lakehoused.main:app" uvicorn target (see __main__.py).
