"""Per-session assistant config (`assistant.json`), replacing `mount_plan.json`.

Holds the assistant identity + the opencode session binding for one lakehouse
session: {assistant_name, manifest_hash, opencode_session_id, directory, agent, model}.
Written at session creation, updated when the opencode session is created and when
the assistant is switched.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..storage.paths import get_state_dir

logger = logging.getLogger(__name__)

FILENAME = "assistant.json"


def config_path(session_id: str) -> Path:
    return get_state_dir() / "sessions" / session_id / FILENAME


def read(session_id: str) -> dict[str, Any] | None:
    path = config_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to read %s for %s: %s", FILENAME, session_id, e)
        return None


def write(
    session_id: str,
    *,
    assistant_name: str,
    manifest_hash: str,
    directory: str,
    agent: str | None,
    model: str | None,
    opencode_session_id: str | None = None,
) -> dict[str, Any]:
    path = config_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "assistant_name": assistant_name,
        "manifest_hash": manifest_hash,
        "directory": directory,
        "agent": agent,
        "model": model,
        "opencode_session_id": opencode_session_id,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def set_opencode_session_id(session_id: str, opencode_session_id: str) -> None:
    data = read(session_id) or {}
    data["opencode_session_id"] = opencode_session_id
    path = config_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
