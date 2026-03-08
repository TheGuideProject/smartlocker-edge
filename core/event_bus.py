"""
Event Bus - Internal Message System

The event bus is the central nervous system of the application.
When something happens (can removed, weight changed, mix started),
an Event is published to the bus. All interested parts of the system
(logger, sync queue, UI, inventory engine) receive the event.

This decouples components: the RFID driver doesn't need to know
about the UI or the sync queue. It just publishes an event.
"""

import logging
from typing import Callable, Dict, List, Optional
from core.event_types import Event, EventType

logger = logging.getLogger("smartlocker")

# Type alias for event handler functions
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Publish-subscribe event bus.

    Usage:
        bus = EventBus()

        # Subscribe to specific events
        bus.subscribe(EventType.CAN_REMOVED, my_handler_function)

        # Subscribe to ALL events
        bus.subscribe_all(my_global_handler)

        # Publish an event (all matching subscribers are called)
        bus.publish(Event(event_type=EventType.CAN_REMOVED, ...))
    """

    def __init__(self):
        # Handlers by event type
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        # Handlers that receive ALL events
        self._global_handlers: List[EventHandler] = []
        # Auto-incrementing sequence number
        self._sequence_counter = 0

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus: subscribed {handler.__name__} to {event_type.value}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a handler that receives ALL events."""
        self._global_handlers.append(handler)
        logger.debug(f"EventBus: subscribed {handler.__name__} to ALL events")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler from a specific event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def publish(self, event: Event) -> None:
        """
        Publish an event to all matching subscribers.

        Assigns a sequence number and calls all handlers.
        Handlers are called synchronously (in order of registration).
        """
        # Assign sequence number
        self._sequence_counter += 1
        event.sequence_num = self._sequence_counter

        logger.info(
            f"Event #{event.sequence_num}: {event.event_type.value} "
            f"[slot={event.slot_id}, tag={event.tag_id}]"
        )

        # Call type-specific handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"EventBus: handler {handler.__name__} failed "
                    f"on {event.event_type.value}: {e}"
                )

        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"EventBus: global handler {handler.__name__} failed: {e}"
                )

    def get_handler_count(self, event_type: Optional[EventType] = None) -> int:
        """Get number of registered handlers (for debugging)."""
        if event_type:
            return len(self._handlers.get(event_type, []))
        total = sum(len(h) for h in self._handlers.values())
        return total + len(self._global_handlers)
