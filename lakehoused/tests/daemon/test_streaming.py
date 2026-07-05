"""
Integration tests for SSE streaming.

Tests Server-Sent Events streaming functionality.
"""

import json

import pytest

from lakehoused.streaming import format_sse_event
from lakehoused.streaming import sse_event_stream
from lakehoused.streaming import wrap_execution_stream


@pytest.mark.integration
class TestSSEFormatting:
    """Test SSE event formatting."""

    def test_format_sse_event_basic(self) -> None:
        """Test format_sse_event creates properly formatted SSE."""
        event = format_sse_event("message", {"content": "Hello"})

        assert "event: message\n" in event
        assert "data:" in event
        assert "Hello" in event
        assert event.endswith("\n\n")

    def test_format_sse_event_with_json_data(self) -> None:
        """Test format_sse_event handles complex data."""
        data = {"type": "content", "content": "Test message", "metadata": {"model": "gpt-4"}}

        event = format_sse_event("message", data)

        assert "event: message\n" in event
        # Verify data is valid JSON
        json_line = [line for line in event.split("\n") if line.startswith("data:")][0]
        json_str = json_line.replace("data:", "").strip()
        parsed = json.loads(json_str)
        assert parsed == data

    def test_format_sse_event_error_type(self) -> None:
        """Test format_sse_event handles error events."""
        event = format_sse_event("error", {"error": "Something went wrong"})

        assert "event: error\n" in event
        assert "Something went wrong" in event

    def test_format_sse_event_done_type(self) -> None:
        """Test format_sse_event handles done events."""
        event = format_sse_event("done", {"type": "done"})

        assert "event: done\n" in event
        assert "data:" in event


@pytest.mark.integration
class TestSSEStreaming:
    """Test SSE streaming utilities."""

    @pytest.mark.asyncio
    async def test_sse_event_stream_formats_events(self) -> None:
        """Test sse_event_stream converts generator to SSE format."""

        async def test_generator():
            yield {"event": "message", "data": {"content": "First"}}
            yield {"event": "message", "data": {"content": "Second"}}
            yield {"event": "done", "data": {"type": "done"}}

        events = []
        async for event in sse_event_stream(test_generator()):
            events.append(event)

        assert len(events) == 3
        assert all("event:" in e for e in events)
        assert all("data:" in e for e in events)

    @pytest.mark.asyncio
    async def test_sse_event_stream_handles_errors(self) -> None:
        """Test sse_event_stream handles errors in generator."""

        async def failing_generator():
            yield {"event": "message", "data": {"content": "OK"}}
            raise ValueError("Simulated error")

        events = []
        async for event in sse_event_stream(failing_generator()):
            events.append(event)

        # Should yield the OK message plus an error event
        assert len(events) >= 1
        # Last event should be error
        assert "event: error" in events[-1]

    @pytest.mark.asyncio
    async def test_sse_event_stream_preserves_order(self) -> None:
        """Test sse_event_stream preserves event order."""

        async def ordered_generator():
            for i in range(5):
                yield {"event": "message", "data": {"index": i}}

        events = []
        async for event in sse_event_stream(ordered_generator()):
            events.append(event)

        # Extract index from each event
        for i, event in enumerate(events):
            json_line = [line for line in event.split("\n") if line.startswith("data:")][0]
            json_str = json_line.replace("data:", "").strip()
            data = json.loads(json_str)
            assert data["index"] == i


@pytest.mark.integration
class TestExecutionStreamWrapping:
    """Test execution stream wrapping."""

    @pytest.mark.asyncio
    async def test_wrap_execution_stream_yields_events(self, mock_amplifier_module) -> None:
        """Test wrap_execution_stream yields message and done events."""

        async def mock_token_stream():
            yield "This "
            yield "is "
            yield "the "
            yield "response"

        events = []
        async for event in wrap_execution_stream(mock_token_stream()):
            events.append(event)

        # Should yield 4 message events (one per token) and 1 done event
        assert len(events) == 5
        assert events[0]["event"] == "message"
        assert events[0]["data"]["content"] == "This "
        assert events[1]["data"]["content"] == "is "
        assert events[4]["event"] == "done"

    @pytest.mark.asyncio
    async def test_wrap_execution_stream_handles_errors(self) -> None:
        """Test wrap_execution_stream yields error event on failure."""

        async def failing_token_stream():
            yield "Starting..."
            raise RuntimeError("Execution failed")

        events = []
        async for event in wrap_execution_stream(failing_token_stream()):
            events.append(event)

        # Should yield message event then error event
        assert len(events) == 2
        assert events[0]["event"] == "message"
        assert events[1]["event"] == "error"
        assert "Execution failed" in events[1]["data"]["error"]

    @pytest.mark.asyncio
    async def test_wrap_execution_stream_event_structure(self, mock_amplifier_module) -> None:
        """Test wrap_execution_stream creates properly structured events."""

        async def mock_token_stream():
            yield "Test response"

        events = []
        async for event in wrap_execution_stream(mock_token_stream()):
            events.append(event)

        # Verify message event structure
        message_event = events[0]
        assert "event" in message_event
        assert "data" in message_event
        assert "type" in message_event["data"]
        assert "content" in message_event["data"]

        # Verify done event structure
        done_event = events[1]
        assert done_event["event"] == "done"
        assert done_event["data"]["type"] == "done"
