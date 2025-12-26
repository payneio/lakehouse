"""Aggregates events.jsonl into execution trace turns.

This module provides on-the-fly aggregation of raw events from events.jsonl
(written by hooks-logging in amplifier_core) into structured trace turns
for the frontend ExecutionPanel.

Single source of truth: events.jsonl is the only event storage.
Trace views are generated on-demand from this file.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..models.trace import TraceThinking
from ..models.trace import TraceTool
from ..models.trace import TraceTurn

logger = logging.getLogger(__name__)


def _parse_timestamp(ts: str) -> int:
    """Parse ISO timestamp to milliseconds since epoch.

    Args:
        ts: ISO format timestamp string (e.g., "2025-12-17T20:21:22.794+00:00")

    Returns:
        Milliseconds since epoch
    """
    try:
        # Parse ISO format with timezone
        dt = datetime.fromisoformat(ts)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


def _truncate(text: str, max_length: int = 1000) -> str:
    """Truncate text with indicator if too long.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation

    Returns:
        Original or truncated text with "... (truncated)" suffix
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "... (truncated)"


def aggregate_events_to_turns(events_file: Path) -> list[TraceTurn]:
    """Aggregate raw events from events.jsonl into UI-friendly turns.

    Parses the events file line by line and groups events into turns.
    Each turn starts with prompt:submit and ends with session:end.

    Args:
        events_file: Path to events.jsonl file

    Returns:
        List of TraceTurn objects ready for frontend consumption

    Event types handled:
        - prompt:submit: Start new turn with user message
        - tool:pre: Add tool to current turn
        - tool:post: Update tool with result and timing
        - thinking:delta: Record thinking block content
        - session:end: Complete current turn
    """
    if not events_file.exists():
        return []

    turns: list[TraceTurn] = []
    current_turn: TraceTurn | None = None

    try:
        with open(events_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping malformed line {line_num} in {events_file}: {e}")
                    continue

                event_type = event.get("event", "")
                data = event.get("data", {})
                ts = event.get("ts", "")

                if event_type == "prompt:submit":
                    # Start new turn
                    # If there's an unclosed turn, save it first
                    if current_turn is not None:
                        current_turn.status = "completed"
                        turns.append(current_turn)

                    current_turn = TraceTurn(
                        id=str(uuid4()),
                        user_message=data.get("prompt", ""),
                        status="active",
                        start_time=_parse_timestamp(ts),
                    )

                elif event_type == "tool:pre" and current_turn is not None:
                    # Add tool to current turn
                    tool_name = data.get("tool_name", "")
                    tool_input = data.get("tool_input", {})
                    parallel_group_id = data.get("parallel_group_id", "")

                    # Detect sub-agent calls (Task tool with subagent_type)
                    is_sub_agent = tool_name == "Task"
                    sub_agent_name = tool_input.get("subagent_type") if is_sub_agent else None

                    tool = TraceTool(
                        id=parallel_group_id or str(uuid4()),
                        name=tool_name,
                        parallel_group_id=parallel_group_id,
                        status="running",
                        start_time=_parse_timestamp(ts),
                        arguments=tool_input,
                        is_sub_agent=is_sub_agent,
                        sub_agent_name=sub_agent_name,
                    )
                    current_turn.tools.append(tool)

                elif event_type == "tool:post" and current_turn is not None:
                    # Find and update matching tool by tool_name + parallel_group_id
                    tool_name = data.get("tool_name", "")
                    parallel_group_id = data.get("parallel_group_id", "")

                    # Find matching tool (running status, same name and parallel_group_id)
                    tool = next(
                        (
                            t
                            for t in current_turn.tools
                            if t.name == tool_name
                            and t.parallel_group_id == parallel_group_id
                            and t.status in ("starting", "running")
                        ),
                        None,
                    )

                    if tool is not None:
                        end_time = _parse_timestamp(ts)
                        tool.status = "completed"
                        tool.end_time = end_time
                        tool.duration = round(end_time - tool.start_time, 2) if tool.start_time else None

                        # Handle result - can be dict with success/output/error or direct value
                        result = data.get("result", "")
                        if isinstance(result, dict):
                            # Extract child session ID for sub-agent (Task) tools
                            if tool.is_sub_agent and "session_id" in result:
                                tool.child_session_id = result.get("session_id")

                            if result.get("success", True):
                                tool.result = _truncate(str(result.get("output", "")))
                            else:
                                error_info = result.get("error", {})
                                error_msg = (
                                    error_info.get("message", str(error_info))
                                    if isinstance(error_info, dict)
                                    else str(error_info)
                                )
                                tool.error = _truncate(error_msg)
                                tool.status = "error"
                        else:
                            tool.result = _truncate(str(result))
                    else:
                        logger.debug(
                            f"No matching tool found for tool:post: {tool_name} (parallel_group_id={parallel_group_id})"
                        )

                elif event_type == "thinking:delta" and current_turn is not None:
                    # Record thinking block
                    thinking = TraceThinking(
                        id=str(uuid4()),
                        content=data.get("delta", ""),
                        timestamp=_parse_timestamp(ts),
                    )
                    current_turn.thinking.append(thinking)

                elif event_type == "session:end" and current_turn is not None:
                    # Complete current turn
                    current_turn.status = "completed"
                    current_turn.end_time = _parse_timestamp(ts)
                    turns.append(current_turn)
                    current_turn = None

        # Handle any unclosed turn at end of file
        if current_turn is not None:
            # Turn still in progress
            turns.append(current_turn)

    except Exception as e:
        logger.error(f"Failed to aggregate events from {events_file}: {e}")
        # Return whatever we've collected so far
        pass

    return turns
