"""Hook event vocabulary for lakehoused SSE streaming.

The opencode event translator (lakehoused.opencode.events) emits `hook:<event>`
SSE events for the names below. This module is just the shared vocabulary; there
is no hook registry (opencode owns the agent loop).
"""

DEFAULT_STREAMING_HOOKS = {
    "tool:pre",
    "tool:post",
    "thinking:delta",
    "approval:required",
}

__all__ = ["DEFAULT_STREAMING_HOOKS"]
