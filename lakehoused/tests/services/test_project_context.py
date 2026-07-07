"""Tests for the project_context service (lakehouse primer + ancestor AGENTS.md chain)."""

from pathlib import Path

import pytest
from lakehoused.services import project_context
from lakehoused.services.project_service import PROJECT_MARKER_DIR


@pytest.fixture
def nested_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A data root with a root-level AGENTS.md and a nested project AGENTS.md.

    Patches out the lakehouse primer so tests focus on the ancestor-chain behavior.
    Returns (data_dir, project_path).
    """
    monkeypatch.setattr(project_context, "_get_lakehouse_context", lambda: "")

    data_dir = tmp_path / "data"
    project_path = data_dir / "projects" / "myproj"
    project_path.mkdir(parents=True)

    # Root-of-data-dir instructions (ancestor).
    (data_dir / PROJECT_MARKER_DIR).mkdir()
    (data_dir / PROJECT_MARKER_DIR / "AGENTS.md").write_text("ROOT_DATA_CONTEXT")

    # Project instructions (most specific).
    (project_path / PROJECT_MARKER_DIR).mkdir()
    (project_path / PROJECT_MARKER_DIR / "AGENTS.md").write_text("PROJECT_CONTEXT")

    return data_dir, project_path


def test_ancestor_chain_included_ancestors_first(nested_data_dir: tuple[Path, Path]) -> None:
    """The walk collects AGENTS.md from data root down to project, ancestors first."""
    data_dir, project_path = nested_data_dir

    system = project_context.build_project_context_system(project_path, data_dir)

    assert system is not None
    assert "ROOT_DATA_CONTEXT" in system
    assert "PROJECT_CONTEXT" in system
    # Ancestors (data root) must appear before the more specific project context.
    assert system.index("ROOT_DATA_CONTEXT") < system.index("PROJECT_CONTEXT")


def test_returns_none_when_no_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no primer and no AGENTS.md files, the system string is None."""
    monkeypatch.setattr(project_context, "_get_lakehouse_context", lambda: "")

    data_dir = tmp_path / "data"
    project_path = data_dir / "empty"
    project_path.mkdir(parents=True)

    assert project_context.build_project_context_system(project_path, data_dir) is None


def test_primer_body_included(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The lakehouse primer body itself is delivered as context."""
    monkeypatch.setattr(project_context, "_get_lakehouse_context", lambda: "PRIMER_BODY")

    data_dir = tmp_path / "data"
    project_path = data_dir / "proj"
    project_path.mkdir(parents=True)

    system = project_context.build_project_context_system(project_path, data_dir)

    assert system is not None
    assert "PRIMER_BODY" in system
