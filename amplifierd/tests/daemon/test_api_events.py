"""Tests for global events SSE endpoint."""

import pytest

from amplifierd.main import app
from amplifierd.models.events import GlobalEvent
from amplifierd.models.events import SessionCreatedEvent
from amplifierd.services.global_events import GlobalEventService


class TestGlobalEventsAPI:
    """Test global events SSE streaming."""

    @pytest.fixture(autouse=True)
    def cleanup_events(self):
        """Clean up event service between tests."""
        yield
        # Reset singleton for next test
        GlobalEventService._instance = None

    def test_events_router_registered(self):
        """Test that events router is registered."""
        routes = [route.path for route in app.routes]
        assert "/api/v1/events" in routes

    def test_event_models_validate(self):
        """Test that event models validate correctly."""
        # Test base event
        event = GlobalEvent(event_type="test:event", project_id="test-proj")
        assert event.event_type == "test:event"
        assert event.project_id == "test-proj"
        assert event.timestamp is not None

        # Test session created event
        session_event = SessionCreatedEvent(
            session_id="test-123",
            session_name="Test Session",
            project_id="test-project",
            is_unread=True,
            created_by="user",
        )
        assert session_event.event_type == "session:created"
        assert session_event.session_id == "test-123"

    def test_global_event_service_singleton(self):
        """Test that GlobalEventService is a singleton."""
        service1 = GlobalEventService.get_instance()
        service2 = GlobalEventService.get_instance()
        assert service1 is service2

    async def test_global_event_service_emit_and_subscribe(self):
        """Test that events can be emitted and received."""
        service = GlobalEventService.get_instance()

        # Subscribe to events
        queue = service.subscribe()

        # Emit an event
        event = SessionCreatedEvent(
            session_id="test-456",
            session_name="Test",
            project_id="test-proj",
            is_unread=False,
            created_by="automation",
        )
        await GlobalEventService.emit(event)

        # Receive the event
        received = await queue.get()
        assert received["event"] == "session:created"
        assert received["data"]["session_id"] == "test-456"

        # Cleanup
        service.unsubscribe(queue)
