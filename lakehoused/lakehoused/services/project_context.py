"""Build a session's project context: lakehouse primer + ancestor AGENTS.md chain.

When a chat runs in a project directory, lakehouse ingests context by walking from
the project directory up to the root of the data dir, collecting AGENTS.md /
.lakehouse/AGENTS.md files at each level, plus a built-in lakehouse primer. This
context is delivered to opencode as the prompt `system` field so it reaches the LLM
on every turn.

The assistant instruction is intentionally NOT included here: under the
opencode backend that instruction is owned by the opencode manifest/agent system
prompt, so re-injecting it would duplicate the assistant's own prompt.

Contract:
- Inputs: project directory, data-dir root (traversal boundary)
- Outputs: ordered context messages (ancestors first) / a joined system string
- Side effects: reads AGENTS.md files; may create share/lakehouse.md from the default
"""

from __future__ import annotations

import logging
from pathlib import Path

from lakehoused.models.context_messages import ContextMessage

logger = logging.getLogger(__name__)


def _get_lakehouse_context() -> str:
    """Load the lakehouse primer from the share directory.

    If the file doesn't exist in the share dir, create it from the default template
    packaged with the daemon.

    Returns:
        Lakehouse context string, or empty string if unavailable.
    """
    try:
        from lakehoused.storage import get_share_dir

        share_dir = get_share_dir()
        lakehouse_context_file = share_dir / "lakehouse.md"

        # If the user's lakehouse.md doesn't exist, create it from the default.
        if not lakehouse_context_file.exists():
            default_file = Path(__file__).parent.parent / "context" / "lakehouse_default.md"
            if default_file.exists():
                share_dir.mkdir(parents=True, exist_ok=True)
                lakehouse_context_file.write_text(
                    default_file.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                logger.info(f"Created lakehouse context from default: {lakehouse_context_file}")
            else:
                logger.warning("No default lakehouse context found")
                return ""

        return lakehouse_context_file.read_text(encoding="utf-8")
    except Exception as e:
        # In test environments, get_share_dir may return a Mock or other non-Path.
        # Log and continue without lakehouse context.
        logger.debug(f"Could not load lakehouse context: {e}")
        return ""


def build_project_context_messages(project_path: Path, data_dir: Path) -> list[ContextMessage]:
    """Build the project context messages for a session.

    Assembles, in order:
    1. The lakehouse primer (with any @mentions it contains resolved).
    2. The ancestor AGENTS.md chain from data_dir down to project_path (ancestors first,
       project last), deduplicated against files already pulled in via the primer.

    Args:
        project_path: The session's project directory (used for @mention resolution and
            as the innermost point of the ancestor walk).
        data_dir: The data-dir root; traversal stops here and it bounds @mention security.

    Returns:
        Ordered list of context messages (may be empty).
    """
    lakehouse_context = _get_lakehouse_context()

    try:
        from lakehoused.services.mention_resolver import MentionResolver

        resolver = MentionResolver(
            compiled_profile_dir=project_path,
            project_path=project_path,
            data_dir=data_dir,
        )

        messages: list[ContextMessage] = []
        resolved_paths: set[Path] = set()

        # 1. Lakehouse primer + any @mentions it references.
        if lakehouse_context.strip():
            primer_messages, resolved_paths = resolver.resolve_profile_instructions_with_paths(lakehouse_context)
            # resolve_profile_instructions_with_paths returns only the *resolved mentions*,
            # not the primer text itself, so include the primer body explicitly.
            messages.append(ContextMessage(role="developer", content=lakehouse_context))
            messages.extend(primer_messages)

        # 2. Ancestor AGENTS.md chain (data_dir -> project), excluding already-loaded files.
        ancestor_messages = resolver.resolve_agents_md_chain(exclude_paths=resolved_paths)
        if ancestor_messages:
            messages.extend(ancestor_messages)
            logger.info(f"Added {len(ancestor_messages)} context messages from ancestor AGENTS.md chain")

        return messages
    except Exception as e:
        logger.error(f"Failed to build project context: {e}", exc_info=True)
        return []


def build_project_context_system(project_path: Path, data_dir: Path) -> str | None:
    """Build the project context as a single system string for opencode.

    Args:
        project_path: The session's project directory.
        data_dir: The data-dir root (traversal boundary).

    Returns:
        The joined context string, or None if there is no context to inject.
    """
    messages = build_project_context_messages(project_path, data_dir)
    if not messages:
        return None
    joined = "\n\n".join(m.content for m in messages if m.content)
    return joined or None
