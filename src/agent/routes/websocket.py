"""
WebSocket API routes
"""

import logging
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from ...agent.dependencies import get_app_state

logger = logging.getLogger(__name__)


def register_websocket_routes(app):
    """Register WebSocket routes"""
    
    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
    ):
        """
        WebSocket endpoint for real-time updates
        
        Supported events:
        - device_status_changed: Device status changed
        - device_added: New device registered
        - device_removed: Device unregistered
        - alarm_created: New alarm created
        - alarm_updated: Alarm updated
        - diagnostic_created: Diagnostic report created
        - stats_updated: Statistics updated
        
        Client can send:
        - {"type": "subscribe", "events": ["device_status_changed", ...]}
        - {"type": "ping"}
        """
        websocket_manager = get_app_state().get("websocket_manager")
        if not websocket_manager:
            await websocket.close(code=503, reason="WebSocket manager not initialized")
            return

        client_id = websocket.headers.get("x-client-id") or None
        await websocket_manager.connect(websocket, client_id)

        try:
            # Send welcome message
            await websocket_manager.send_personal_message(
                {
                    "type": "connected",
                    "message": "WebSocket connection established",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )

            # Listen for messages from client
            while True:
                try:
                    data = await websocket.receive_json()
                    await websocket_manager.handle_client_message(websocket, data)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    # Only send error message if connection is still active
                    if websocket in websocket_manager.active_connections:
                        try:
                            await websocket_manager.send_personal_message(
                                {
                                    "type": "error",
                                    "message": str(e),
                                },
                                websocket,
                            )
                        except Exception:
                            # If sending error message fails, connection is likely closed
                            pass
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await websocket_manager.disconnect(websocket)
    
    @app.websocket("/ws/diagnostics/{site_id}")
    async def diagnostic_websocket(
        websocket: WebSocket,
        site_id: str,
    ):
        """
        WebSocket endpoint for diagnostic agent real-time updates
        
        Subscribes to diagnostic events for a specific site:
        - diagnostic_task_created: Task list created
        - diagnostic_task_updated: Task status updated
        - diagnostic_agent_status: Agent status changed
        - diagnostic_message: General diagnostic messages
        - diagnostic_complete: Diagnostic completed
        """
        websocket_manager = get_app_state().get("websocket_manager")
        if not websocket_manager:
            await websocket.close(code=503, reason="WebSocket manager not initialized")
            return

        client_id = f"diagnostic_{site_id}_{id(websocket)}"
        await websocket_manager.connect(websocket, client_id)

        try:
            # Subscribe to diagnostic events
            diagnostic_events = [
                "diagnostic_task_created",
                "diagnostic_task_updated",
                "diagnostic_agent_status",
                "diagnostic_message",
                "diagnostic_complete",
            ]
            await websocket_manager.subscribe(websocket, diagnostic_events)

            # Send welcome message
            await websocket_manager.send_personal_message(
                {
                    "type": "connected",
                    "message": f"Diagnostic WebSocket connected for site {site_id}",
                    "site_id": site_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )

            # Listen for messages from client
            while True:
                try:
                    data = await websocket.receive_json()
                    await websocket_manager.handle_client_message(websocket, data)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    # Only send error message if connection is still active
                    if websocket in websocket_manager.active_connections:
                        try:
                            await websocket_manager.send_personal_message(
                                {
                                    "type": "error",
                                    "message": str(e),
                                },
                                websocket,
                            )
                        except Exception:
                            # If sending error message fails, connection is likely closed
                            pass
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Diagnostic WebSocket error: {e}")
        finally:
            await websocket_manager.disconnect(websocket)

