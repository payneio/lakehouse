"""Tests for environment-variable overrides in secrets loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from lakehoused.config.loader import load_secrets


class TestAuthPasswordEnvOverride:
    """LAKEHOUSED_AUTH_PASSWORD lets a deployment inject the gate password."""

    def test_env_provides_password_without_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAKEHOUSED_AUTH_PASSWORD", "from-env")
        secrets = load_secrets(secrets_path=tmp_path / "missing.yaml")
        assert secrets.auth_password == "from-env"

    def test_env_overrides_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secrets_path = tmp_path / "secrets.yaml"
        secrets_path.write_text("auth_password: from-file\n")
        monkeypatch.setenv("LAKEHOUSED_AUTH_PASSWORD", "from-env")
        secrets = load_secrets(secrets_path=secrets_path)
        assert secrets.auth_password == "from-env"

    def test_file_used_when_env_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LAKEHOUSED_AUTH_PASSWORD", raising=False)
        secrets_path = tmp_path / "secrets.yaml"
        secrets_path.write_text("auth_password: from-file\n")
        secrets = load_secrets(secrets_path=secrets_path)
        assert secrets.auth_password == "from-file"

    def test_no_password_when_neither_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LAKEHOUSED_AUTH_PASSWORD", raising=False)
        secrets = load_secrets(secrets_path=tmp_path / "missing.yaml")
        assert secrets.auth_password is None


class TestApiKeyEnvOverride:
    """Provider API keys can come from the environment, overriding the file."""

    def test_env_provides_key_without_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        secrets = load_secrets(secrets_path=tmp_path / "missing.yaml")
        assert secrets.api_keys["provider-anthropic"] == "sk-from-env"

    def test_env_overrides_file_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secrets_path = tmp_path / "secrets.yaml"
        secrets_path.write_text("api_keys:\n  provider-openai: sk-from-file\n")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        secrets = load_secrets(secrets_path=secrets_path)
        assert secrets.api_keys["provider-openai"] == "sk-from-env"

    def test_file_key_kept_when_env_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        secrets_path = tmp_path / "secrets.yaml"
        secrets_path.write_text("api_keys:\n  provider-openai: sk-from-file\n")
        secrets = load_secrets(secrets_path=secrets_path)
        assert secrets.api_keys["provider-openai"] == "sk-from-file"
