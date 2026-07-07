"""Translate opencode events into lakehouse EventQueueEmitter events.

Pure translation layer. `translate(event, state)` maps one opencode Event (as
delivered by the server /global/event demux) into a list of (emitter_event_type,
data) tuples matching the webapp SSE contract (see CONTRACT.md). It never emits
`assistant_message_complete` (the turn driver does that from accumulated text) and
`session.idle` is treated as the terminal signal by the driver, not here.

Verified opencode shapes (opencode 1.17.13):
- message.part.delta: {sessionID, messageID, partID, field: "text"|"reasoning", delta}
- message.part.updated: {part: Part}  (tool parts carry callID + state.status)
- permission.updated: Permission {id, sessionID, title, ...}
- session.error: {sessionID, error?}
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

# opencode tool name -> webapp tool_name. `task` must map to "Task" so the webapp
# flags it as a sub-agent (it reads tool_input.subagent_type).
_TOOL_NAME_MAP = {"task": "Task"}


@dataclass
class TurnState:
    """Per-turn mutable state for translation (tool pre/post correlation)."""

    tools_seen: set[str] = field(default_factory=set)


def _map_tool_input(tool: str, raw_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize opencode tool input to the keys the webapp preview/subagent code reads.

    webapp reads: command, file_path, pattern, url, agent, todos, subagent_type.
    opencode uses camelCase (filePath, ...) for some tools.
    """
    ti = dict(raw_input)
    if "filePath" in ti and "file_path" not in ti:
        ti["file_path"] = ti["filePath"]
    if tool == "task":
        # opencode's task tool carries the delegated agent name.
        agent = ti.get("subagent_type") or ti.get("subagentType") or ti.get("agent")
        if agent:
            ti["subagent_type"] = agent
    return ti


def _translate_tool_part(part: dict[str, Any], state: TurnState) -> list[tuple[str, dict[str, Any]]]:
    call_id = part.get("callID") or part.get("id") or ""
    tool = part.get("tool", "")
    st = part.get("state") or {}
    status = st.get("status")
    tool_name = _TOOL_NAME_MAP.get(tool, tool)
    tool_input = _map_tool_input(tool, st.get("input") or {})

    out: list[tuple[str, dict[str, Any]]] = []
    if call_id and call_id not in state.tools_seen and status in ("pending", "running", "completed", "error"):
        state.tools_seen.add(call_id)
        out.append(
            (
                "hook:tool:pre",
                {
                    "hook_event": "tool:pre",
                    "hook_data": {
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "parallel_group_id": call_id,
                    },
                    "phase": "start",
                },
            )
        )
    if status in ("completed", "error"):
        is_error = status == "error"
        result = st.get("error") if is_error else st.get("output")
        out.append(
            (
                "hook:tool:post",
                {
                    "hook_event": "tool:post",
                    "hook_data": {
                        "tool_name": tool_name,
                        "parallel_group_id": call_id,
                        "result": result,
                        "is_error": is_error,
                    },
                    "phase": "end",
                },
            )
        )
    return out


def _approval_data(perm: dict[str, Any]) -> dict[str, Any]:
    """Build the flat approval payload the webapp ApprovalDialog reads.

    Includes permission_id + session_id so the router can reply to opencode.
    Handles the 1.17.x `permission.asked` shape ({id, permission, metadata.command,
    patterns}) and the older `permission.updated` shape ({id, title}).
    """
    permission_type = perm.get("permission") or perm.get("type") or "action"
    detail = ""
    metadata = perm.get("metadata")
    if isinstance(metadata, dict) and metadata.get("command"):
        detail = str(metadata["command"])
    elif isinstance(perm.get("patterns"), list) and perm["patterns"]:
        detail = ", ".join(str(p) for p in perm["patterns"])
    prompt = perm.get("title") or (f"Allow {permission_type}: {detail}" if detail else f"Allow {permission_type}?")
    return {
        "approval_id": perm.get("id", ""),
        "prompt": prompt,
        "options": ["Allow", "Always Allow", "Deny"],
        "permission_id": perm.get("id", ""),
        "session_id": perm.get("sessionID", ""),
    }


def error_message(props: dict[str, Any]) -> str:
    """Extract a human-readable message from a session.error event's properties."""
    err = props.get("error")
    if isinstance(err, dict):
        data = err.get("data")
        if isinstance(data, dict) and "message" in data:
            return str(data["message"])
        return str(err.get("name") or err)
    return str(err) if err else "execution error"


def translate(event: dict[str, Any], state: TurnState) -> list[tuple[str, dict[str, Any]]]:
    """Map one opencode event to zero or more (emitter_event_type, data) tuples."""
    etype = event.get("type")
    props = event.get("properties")
    if not isinstance(props, dict):
        return []

    if etype == "message.part.delta":
        delta = props.get("delta")
        if not delta:
            return []
        field_name = props.get("field")
        if field_name == "text":
            return [("content", {"type": "content", "content": delta})]
        if field_name == "reasoning":
            return [
                (
                    "hook:thinking:delta",
                    {"hook_event": "thinking:delta", "hook_data": {"delta": delta}, "phase": "start"},
                )
            ]
        return []

    if etype == "message.part.updated":
        part = props.get("part")
        if isinstance(part, dict) and part.get("type") == "tool":
            return _translate_tool_part(part, state)
        return []

    # opencode 1.17.x emits "permission.asked"; older/SDK types use "permission.updated".
    if etype in ("permission.asked", "permission.updated"):
        return [("hook:approval:required", _approval_data(props))]

    # session.idle (terminal) and session.error are handled by the turn driver
    # (OpencodeRunner), not translated here.
    return []
