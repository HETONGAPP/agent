"""
Event Bus
Publish-subscribe pattern for decoupling services
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types"""
    DEVICE_DATA_RECEIVED = "device_data_received"
    ALARM_CREATED = "alarm_created"
    ALARM_UPDATED = "alarm_updated"
    DEVICE_STATUS_CHANGED = "device_status_changed"
    DEVICE_ADDED = "device_added"
    DEVICE_REMOVED = "device_removed"
    DIAGNOSTIC_CREATED = "diagnostic_created"
    STATS_UPDATED = "stats_updated"
    SITE_CREATED = "site_created"
    SITE_UPDATED = "site_updated"
    SITE_DELETED = "site_deleted"
    RULE_CREATED = "rule_created"
    RULE_UPDATED = "rule_updated"
    RULE_DELETED = "rule_deleted"


class EventBus:
    """
    Event bus for publish-subscribe pattern
    Decouples services by allowing them to communicate via events
    """

    def __init__(self):
        """Initialize event bus"""
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._async_subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 1000  # Keep last 1000 events for debugging

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable,
        async_handler: bool = False,
    ):
        """
        Subscribe to an event type

        Args:
            event_type: Type of event to subscribe to
            handler: Handler function (sync or async)
            async_handler: If True, handler is async and will be awaited

        Returns:
            Unsubscribe function
        """
        if async_handler:
            self._async_subscribers[event_type].append(handler)
        else:
            self._subscribers[event_type].append(handler)

        # Return unsubscribe function
        def unsubscribe():
            if async_handler:
                if handler in self._async_subscribers[event_type]:
                    self._async_subscribers[event_type].remove(handler)
            else:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)

        return unsubscribe

    async def publish(self, event_type: EventType, data: Any = None):
        """
        Publish an event to all subscribers

        Args:
            event_type: Type of event
            data: Event data
        """
        # Record event in history
        event_record = {
            "type": event_type.value,
            "data": data,
            "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else None,
        }
        self._event_history.append(event_record)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify sync subscribers
        for handler in self._subscribers[event_type]:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in sync event handler for {event_type.value}: {e}", exc_info=True)

        # Notify async subscribers
        for handler in self._async_subscribers[event_type]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in async event handler for {event_type.value}: {e}", exc_info=True)

    def get_subscriber_count(self, event_type: Optional[EventType] = None) -> int:
        """
        Get number of subscribers for an event type

        Args:
            event_type: Event type (if None, returns total count)

        Returns:
            Number of subscribers
        """
        if event_type:
            return len(self._subscribers[event_type]) + len(self._async_subscribers[event_type])
        else:
            total = sum(len(handlers) for handlers in self._subscribers.values())
            total += sum(len(handlers) for handlers in self._async_subscribers.values())
            return total

    def get_event_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get event history

        Args:
            event_type: Filter by event type (if None, returns all)
            limit: Maximum number of events to return

        Returns:
            List of event records
        """
        if event_type:
            filtered = [e for e in self._event_history if e["type"] == event_type.value]
        else:
            filtered = self._event_history

        return filtered[-limit:]

    def clear_history(self):
        """Clear event history"""
        self._event_history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            "total_subscribers": self.get_subscriber_count(),
            "subscribers_by_type": {
                event_type.value: self.get_subscriber_count(event_type)
                for event_type in EventType
            },
            "event_history_size": len(self._event_history),
            "total_events_published": len(self._event_history),
        }


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def set_event_bus(event_bus: EventBus):
    """Set global event bus instance"""
    global _event_bus
    _event_bus = event_bus








