"""
WebSocket Manager
Manages WebSocket connections and broadcasts events to connected clients
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket event types"""
    DEVICE_STATUS_CHANGED = "device_status_changed"
    DEVICE_ADDED = "device_added"
    DEVICE_REMOVED = "device_removed"
    DEVICE_UPDATED = "device_updated"  # Device information updated (metadata, integration_name, etc.)
    ALARM_CREATED = "alarm_created"
    ALARM_UPDATED = "alarm_updated"
    DIAGNOSTIC_CREATED = "diagnostic_created"
    STATS_UPDATED = "stats_updated"
    HEARTBEAT = "heartbeat"
    # Diagnostic agent events
    DIAGNOSTIC_TASK_CREATED = "diagnostic_task_created"
    DIAGNOSTIC_TASK_UPDATED = "diagnostic_task_updated"
    DIAGNOSTIC_AGENT_STATUS = "diagnostic_agent_status"
    DIAGNOSTIC_MESSAGE = "diagnostic_message"
    DIAGNOSTIC_COMPLETE = "diagnostic_complete"


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events"""

    def __init__(self):
        """Initialize WebSocket manager"""
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None):
        """
        Accept a new WebSocket connection

        Args:
            websocket: WebSocket connection
            client_id: Optional client identifier
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_metadata[websocket] = {
            "client_id": client_id or f"client_{id(websocket)}",
            "connected_at": datetime.utcnow().isoformat(),
            "subscribed_events": set(),
        }
        logger.info(f"WebSocket client connected: {self.connection_metadata[websocket]['client_id']}")

    async def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection

        Args:
            websocket: WebSocket connection to remove
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            client_id = self.connection_metadata.get(websocket, {}).get("client_id", "unknown")
            self.connection_metadata.pop(websocket, None)
            logger.info(f"WebSocket client disconnected: {client_id}")

            # Try to close the connection gracefully if it's still open
            try:
                # Check if websocket is still in a state that can be closed
                # FastAPI WebSocket has a client_state attribute
                if hasattr(websocket, 'client_state'):
                    state = websocket.client_state
                    # Only close if not already disconnected
                    if state.name != 'DISCONNECTED':
                        await websocket.close()
            except (WebSocketDisconnect, RuntimeError, ConnectionError):
                # Connection is already closed or closing, ignore
                pass
            except Exception as e:
                # Other errors, log at debug level
                logger.debug(f"Error closing WebSocket: {e}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection

        Args:
            message: Message to send
            websocket: Target WebSocket connection
        """
        # Check if connection is still active
        if websocket not in self.active_connections:
            logger.debug(f"Attempted to send message to inactive WebSocket connection")
            return
        
        try:
            await websocket.send_json(message)
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
            # Connection is closed or closing, just disconnect silently
            logger.debug(f"WebSocket connection closed: {e}")
            await self.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, event_type: EventType, data: Dict[str, Any], exclude: Optional[WebSocket] = None):
        """
        Broadcast a message to all connected clients

        Args:
            event_type: Type of event
            data: Event data
            exclude: Optional WebSocket connection to exclude from broadcast
        """
        if not self.active_connections:
            return

        message = {
            "type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        disconnected = set()
        # Create a copy of active_connections to avoid modification during iteration
        connections_to_broadcast = list(self.active_connections)
        
        for connection in connections_to_broadcast:
            if connection == exclude:
                continue

            # Check if client is subscribed to this event type
            subscribed_events = self.connection_metadata.get(connection, {}).get("subscribed_events", set())
            if subscribed_events and event_type.value not in subscribed_events:
                continue

            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                # Connection is closed or closing, mark for disconnection
                logger.debug(f"WebSocket connection closed during broadcast: {e}")
                disconnected.add(connection)
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {e}")
                disconnected.add(connection)

        # Remove disconnected connections
        for connection in disconnected:
            await self.disconnect(connection)

    async def subscribe(self, websocket: WebSocket, event_types: list[str]):
        """
        Subscribe a client to specific event types

        Args:
            websocket: WebSocket connection
            event_types: List of event types to subscribe to
        """
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["subscribed_events"] = set(event_types)
            await self.send_personal_message(
                {
                    "type": "subscription_confirmed",
                    "subscribed_events": event_types,
                },
                websocket,
            )

    async def handle_client_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Handle incoming message from client

        Args:
            websocket: WebSocket connection
            message: Message from client
        """
        message_type = message.get("type")

        if message_type == "subscribe":
            event_types = message.get("events", [])
            await self.subscribe(websocket, event_types)
        elif message_type == "ping":
            await self.send_personal_message({"type": "pong"}, websocket)
        else:
            logger.warning(f"Unknown message type from client: {message_type}")

    async def start_heartbeat(self, interval: int = 30):
        """
        Start heartbeat task to keep connections alive

        Args:
            interval: Heartbeat interval in seconds
        """
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval))

    async def stop_heartbeat(self):
        """Stop heartbeat task"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self, interval: int):
        """Heartbeat loop to send periodic ping messages"""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if self.active_connections:
                    await self.broadcast(EventType.HEARTBEAT, {"message": "ping"})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)





