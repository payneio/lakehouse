"""Global event service for system-wide event emission.

This service provides a singleton EventQueueEmitter for global events that can be
subscribed to by multiple clients via the global SSE endpoint.
"""

import asyncio

from amplifierd.models.events import GlobalEvent
from amplifierd.streaming import EventQueueEmitter


class GlobalEventService:
    """Singleton service for global event emission."""

    _instance: EventQueueEmitter | None = None

    @classmethod
    def get_instance(cls) -> EventQueueEmitter:
        """Get the singleton EventQueueEmitter instance."""
        if cls._instance is None:
            cls._instance = EventQueueEmitter()
        return cls._instance

    @classmethod
    async def emit(cls, event: GlobalEvent) -> None:
        """Emit global event to all subscribers.

        Args:
            event: The event to emit
        """
        await cls.get_instance().emit(event.event_type, event.model_dump(mode="json"))

    @classmethod
    def subscribe(cls) -> asyncio.Queue:
        """Subscribe to global event stream.

        Returns:
            A queue that will receive all emitted events
        """
        return cls.get_instance().subscribe()

    @classmethod
    def unsubscribe(cls, queue: asyncio.Queue) -> None:
        """Unsubscribe from global event stream.

        Args:
            queue: The queue to unsubscribe
        """
        cls.get_instance().unsubscribe(queue)


def get_global_events() -> EventQueueEmitter:
    """Convenience function for dependency injection.

    Returns:
        The singleton EventQueueEmitter instance
    """
    return GlobalEventService.get_instance()
