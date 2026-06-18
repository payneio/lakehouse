"""Simple password-based authentication for the lakehoused daemon.

A single shared password (no username) gates API access. The password is read
from ``~/.lakehoused/config/secrets.yaml`` under ``auth_password``. When no
password is configured, authentication is disabled and all requests pass
through unchanged.

This is a lightweight gate intended for a personal/local daemon, not a
multi-user authentication system.
"""

from __future__ import annotations

import secrets

from .config.loader import load_secrets

# A per-process session token. Clients exchange the password for this token at
# /api/v1/auth/login and present it on subsequent requests. Restarting the
# daemon invalidates outstanding tokens (clients simply log in again).
_SESSION_TOKEN = secrets.token_urlsafe(32)


def get_auth_password() -> str | None:
    """Return the configured gate password, or None if auth is disabled."""
    password = load_secrets().auth_password
    if password is None:
        return None
    password = password.strip()
    return password or None


def auth_required() -> bool:
    """Whether a password gate is configured."""
    return get_auth_password() is not None


def verify_password(password: str) -> bool:
    """Constant-time check of a candidate password against the configured one.

    Returns True when auth is disabled (no password configured).
    """
    configured = get_auth_password()
    if configured is None:
        return True
    return secrets.compare_digest(password, configured)


def get_session_token() -> str:
    """Return the current process session token."""
    return _SESSION_TOKEN


def verify_token(token: str | None) -> bool:
    """Constant-time check of a session token against this process's token."""
    if not token:
        return False
    return secrets.compare_digest(token, _SESSION_TOKEN)
