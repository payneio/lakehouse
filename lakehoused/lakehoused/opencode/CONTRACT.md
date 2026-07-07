# opencode backend — internal contract notes

Working notes for the Amplifier→opencode migration. The webapp SSE contract below is
what the **live** `SessionView.tsx` path actually reads (verified against `webapp/src`).
Translate opencode `/event` into exactly these emitter events.

## opencode event stream facts (verified against opencode 1.17.13)

- Subscribe to **`GET /global/event`**, NOT `/event`. `/event` is scoped to one instance
  (directory); one server serves many directories. `/global/event` frames are
  `{directory, payload: Event}` — unwrap `payload`. (See client.event_stream.)
- Streaming tokens arrive as **`message.part.delta`** events (NOT in the SDK 1.17.11 types;
  the running server emits them): `{sessionID, messageID, partID, field: "text"|"reasoning",
  delta}`. `field=="text"` -> `content`; `field=="reasoning"` -> `hook:thinking:delta`.
- `message.part.updated` with a text part carries the ACCUMULATED snapshot (and also echoes
  the user's input part) — do NOT use it for content; rely on `message.part.delta`.
- Tool calls: `message.part.updated` with `part.type=="tool"`, correlate by `part.callID`,
  `part.state.status` in pending|running|completed|error.
- `session.idle` (`properties.sessionID`) is the turn-done sentinel.
- httpx `aiter_lines()` stalls on this long-lived stream; use `aiter_bytes()` + manual framing.

## Emitter events the webapp consumes (live path)

```
user_message_saved          { content: string, timestamp: string }        # router-emitted
assistant_message_start     {}                                            # payload ignored; router-emitted
content                     { type: "content", content: string }          # streaming token; type MUST == "content"
assistant_message_complete  { content: string, timestamp: string }        # from session.idle (accumulated text)
hook:tool:pre               { hook_data: { tool_name, tool_input?, parallel_group_id? }, phase: "start" }
hook:tool:post              { hook_data: { tool_name, parallel_group_id?, result?, is_error? }, phase: "end" }
hook:thinking:delta         { hook_data: { delta: string }, phase: "start" }
hook:approval:required      { approval_id, prompt, options: string[], timeout? }   # flat form
execution_cancelled         {}                                            # payload ignored
execution_error             {}                                            # payload ignored
keepalive                   (ignored)
```

Notes:
- Tool pre/post correlate by `tool_name` + `parallel_group_id`. Use opencode tool `callID` as
  `parallel_group_id`.
- `hook:content_block:start/end` are NOT consumed by the webapp — do not emit.
- Only `hook:approval:required` is consumed; no granted/denied listeners.
- `message_deleted` subscription is currently inert in the webapp — ignore.

## Sub-agents (in-turn) render from tool events, not a hierarchy event

The webapp flags a sub-agent when `hook:tool:pre.hook_data.tool_name === "Task"` and reads
`tool_input.subagent_type` for the display name (`useExecutionState.ts`). So when opencode emits a
`task`-tool part, translate it to `tool_name: "Task"` with `tool_input.subagent_type = <agent name>`.
`toolPreview.ts` also reads these `tool_input` keys for previews: `command`, `file_path`, `pattern`,
`url`, `agent`, `todos`, `subagent_type`.

`ToolCall.childSessionId` is a stubbed webapp field (never populated) — ignore.
Session-tree view is REST-based on `session.parentSessionId` (not SSE).

## Approval response

`POST /api/v1/sessions/{id}/approval-response` body `{ approval_id, response }` where `response` is the
clicked option label. Map labels → opencode `POST /session/{id}/permissions/{permissionID}` body
`{ response: "once" | "always" | "reject" }`:  Allow→once, "Always Allow"→always, Deny→reject.
Offer options `["Allow", "Always Allow", "Deny"]`; `prompt` = permission title.

## events.jsonl (persisted trace, REST include_children)

`EventLogViewer` reads flat (no `hook_data` wrapper) records `{ event, lvl?, ts, data?, session_id? }`
and groups child sessions by parsing `session_id` as `{parent}-{span}_{agent-name}`. Write translated
events here per session so trace aggregation keeps working.
