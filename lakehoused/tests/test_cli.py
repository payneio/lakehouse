"""Tests for the `lakehouse` CLI (init command)."""

from pathlib import Path

import httpx
import lakehoused.cli as cli_mod
import pytest
from click.testing import CliRunner
from lakehoused.cli import init


class FakeResp:
    """Minimal stand-in for httpx.Response."""

    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPError(f"status {self.status_code}")


@pytest.fixture
def fake_daemon(monkeypatch: pytest.MonkeyPatch):
    """Route the CLI's httpx calls to a configurable in-memory fake daemon."""
    state = {"root": "/data", "auth_required": False, "create_status": 201, "create_body": {}, "posts": []}

    def fake_get(url: str, **kwargs):
        if url.endswith("/api/v1/health"):
            return FakeResp(200)
        if url.endswith("/api/v1/auth/status"):
            return FakeResp(200, {"auth_required": state["auth_required"]})
        if url.endswith("/api/v1/status"):
            return FakeResp(200, {"rootDir": state["root"], "version": "0.1.0", "uptimeSeconds": 1})
        return FakeResp(404, text="not found")

    def fake_post(url: str, **kwargs):
        if url.endswith("/api/v1/auth/login"):
            return FakeResp(200, {"token": "tok"})
        if url.endswith("/api/v1/projects/"):
            state["posts"].append(kwargs.get("json"))
            return FakeResp(state["create_status"], state["create_body"], text=state["create_body"].get("detail", ""))
        return FakeResp(404, text="not found")

    monkeypatch.setattr(cli_mod, "base_url", lambda: "http://testhost:7777")
    monkeypatch.setattr(cli_mod.httpx, "get", fake_get)
    monkeypatch.setattr(cli_mod.httpx, "post", fake_post)
    # Ensure no ambient password leaks in for the auth-disabled cases.
    monkeypatch.setattr(cli_mod, "get_auth_password", lambda: None)
    return state


def test_init_registers_project(fake_daemon, tmp_path: Path) -> None:
    """init computes the relative path and POSTs a create for a dir under the root."""
    root = tmp_path / "data"
    (root / "proj").mkdir(parents=True)
    fake_daemon["root"] = str(root)
    fake_daemon["create_body"] = {"relative_path": "proj", "default_assistant": "foundation/base"}

    result = CliRunner().invoke(init, [str(root / "proj"), "--name", "My Project"])

    assert result.exit_code == 0, result.output
    assert "Initialized project 'proj'" in result.output
    # The daemon was asked to create + register the right relative path.
    assert fake_daemon["posts"] == [
        {"relative_path": "proj", "create_marker": True, "metadata": {"name": "My Project"}}
    ]


def test_init_rejects_dir_outside_root(fake_daemon, tmp_path: Path) -> None:
    """init errors when the target is not under the daemon's data root."""
    (tmp_path / "data").mkdir()
    (tmp_path / "outside").mkdir()
    fake_daemon["root"] = str(tmp_path / "data")

    result = CliRunner().invoke(init, [str(tmp_path / "outside")])

    assert result.exit_code == 1
    assert "not inside the daemon data root" in result.output
    assert fake_daemon["posts"] == []  # never attempted registration


def test_init_auth_required_without_password_errors(fake_daemon, tmp_path: Path) -> None:
    """init fails with a clear message when auth is required but no password is available."""
    root = tmp_path / "data"
    (root / "proj").mkdir(parents=True)
    fake_daemon["root"] = str(root)
    fake_daemon["auth_required"] = True  # and get_auth_password() -> None

    result = CliRunner().invoke(init, [str(root / "proj")])

    assert result.exit_code == 1
    assert "requires a password" in result.output
    assert fake_daemon["posts"] == []


def test_init_already_registered_is_friendly(fake_daemon, tmp_path: Path) -> None:
    """init reports (without failing) when the directory is already a project."""
    root = tmp_path / "data"
    (root / "proj").mkdir(parents=True)
    fake_daemon["root"] = str(root)
    fake_daemon["create_status"] = 400
    fake_daemon["create_body"] = {"detail": "Directory is already a project: proj"}

    result = CliRunner().invoke(init, [str(root / "proj")])

    assert result.exit_code == 0, result.output
    assert "already a registered project" in result.output
