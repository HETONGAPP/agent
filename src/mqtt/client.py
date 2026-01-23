"""
MQTT Client for EMQX broker
Supports publishing and subscribing to MQTT topics
"""

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    MQTT Client for connecting to EMQX broker
    Supports publishing device data and subscribing to topics
    """

    def __init__(
        self,
        broker_url: str,
        client_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
    ):
        """
        Initialize MQTT client

        Args:
            broker_url: MQTT broker URL (e.g., mqtt://emqx:1883)
            client_id: Client ID
            username: Optional username for authentication
            password: Optional password for authentication
            keepalive: Keepalive interval in seconds
        """
        if not MQTT_AVAILABLE:
            raise ImportError(
                "paho-mqtt not installed, please run: pip install paho-mqtt"
            )

        # Parse broker URL
        parsed = urlparse(broker_url)
        self.broker_host = parsed.hostname or "localhost"
        self.broker_port = parsed.port or 1883
        self.use_tls = parsed.scheme == "mqtts" or parsed.scheme == "ssl"

        self.client_id = client_id
        self.username = username
        self.password = password
        self.keepalive = keepalive

        # Create MQTT client
        self.client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe

        # Set credentials if provided
        if username and password:
            self.client.username_pw_set(username, password)

        # Set TLS if needed
        if self.use_tls:
            self.client.tls_set()

        # Message handlers: {topic: handler_function}
        # Supports wildcard subscriptions (e.g., sites/+/data/+)
        self.message_handlers: Dict[str, Callable] = {}

        # Store subscriptions for reconnection: {topic: (handler, qos)}
        self._subscriptions: Dict[str, tuple] = {}

        self.connected = False
        self._reconnect_enabled = True
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_interval = 5  # seconds
        self._stop_reconnect = False

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """
        Check if topic matches pattern (supports MQTT wildcards: +, #)

        Args:
            topic: Actual topic (e.g., sites/SITE_001/data/bms)
            pattern: Pattern with wildcards (e.g., sites/+/data/+)

        Returns:
            True if topic matches pattern
        """
        # Exact match
        if topic == pattern:
            return True

        # Convert pattern to regex
        # + matches single level, # matches multiple levels
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        # Handle # wildcard (must be at end)
        if pattern.endswith("/#"):
            pattern_parts = pattern_parts[:-1]  # Remove #
            if len(topic_parts) < len(pattern_parts):
                return False
            # Match up to pattern length
            for i, pattern_part in enumerate(pattern_parts):
                if i >= len(topic_parts):
                    return False
                if pattern_part == "+":
                    continue  # + matches any single level
                if pattern_part != topic_parts[i]:
                    return False
            return True
        elif "#" in pattern:
            # # can only be at end
            return False

        # Handle + wildcard (single level)
        if len(pattern_parts) != len(topic_parts):
            return False

        for pattern_part, topic_part in zip(pattern_parts, topic_parts):
            if pattern_part == "+":
                continue  # + matches any single level
            if pattern_part != topic_part:
                return False

        return True

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logger.debug(
                f"✓ [MQTT] Connected to broker: {self.broker_host}:{self.broker_port}"
            )
            # Resubscribe to all topics on reconnect
            logger.debug(
                f"  [MQTT] Resubscribing to {len(self._subscriptions)} topics..."
            )
            for topic, (handler, qos) in self._subscriptions.items():
                try:
                    result, mid = self.client.subscribe(topic, qos)
                    if result == mqtt.MQTT_ERR_SUCCESS and handler:
                        self.message_handlers[topic] = handler
                        logger.debug(
                            f"  ✓ [MQTT] Resubscribed to topic: {topic} (QoS: {qos})"
                        )
                    else:
                        logger.warning(
                            f"  ⚠ [MQTT] Failed to resubscribe to {topic}, result: {result}"
                        )
                except Exception as e:
                    logger.warning(f"  ✗ [MQTT] Failed to resubscribe to {topic}: {e}")
            logger.debug(
                f"  [MQTT] Total handlers registered: {len(self.message_handlers)}"
            )
        else:
            self.connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorised",
                6: "Connection refused - network error",
                7: "Connection refused - connection timeout or network unreachable",
            }
            error_msg = error_messages.get(rc, f"Unknown error (code: {rc})")
            logger.error(
                f"✗ [MQTT] Failed to connect to broker {self.broker_host}:{self.broker_port}, "
                f"return code: {rc} - {error_msg}"
            )

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        if rc != 0:
            # Log at DEBUG level to reduce noise during normal reconnection attempts
            logger.debug(
                f"⚠ [MQTT] Unexpected disconnection from {self.broker_host}:{self.broker_port}, "
                f"return code: {rc}. Will attempt to reconnect..."
            )
            # Start reconnection thread if not already running
            if self._reconnect_enabled and not self._stop_reconnect:
                self._start_reconnect_thread()
        else:
            logger.debug("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = msg.payload.decode()

        # Extract key info for logging
        device_id = (
            payload.get("device_id", "N/A") if isinstance(payload, dict) else "N/A"
        )
        source = payload.get("source", "N/A") if isinstance(payload, dict) else "N/A"
        soc = (
            payload.get("data", {}).get("soc", "N/A")
            if isinstance(payload, dict)
            else "N/A"
        )

        logger.debug(
            f"📨 [MQTT] Message received - topic: {topic}, "
            f"device_id: {device_id}, source: {source}, soc: {soc}, "
            f"handlers: {len(self.message_handlers)} registered"
        )

        # Find matching handler (supports wildcard subscriptions)
        matched = False
        for subscribed_topic, handler in self.message_handlers.items():
            matches = self._topic_matches(topic, subscribed_topic)
            logger.debug(
                f"  [MQTT] Checking topic '{topic}' vs pattern '{subscribed_topic}': {matches}"
            )
            if matches:
                try:
                    logger.debug(
                        f"  ✓ [MQTT] Topic matched! Calling handler for '{subscribed_topic}'"
                    )
                    handler(topic, payload)
                    matched = True
                    logger.debug(f"  ✓ [MQTT] Handler completed for topic: {topic}")
                    break
                except Exception as e:
                    logger.error(
                        f"✗ [MQTT] Error in message handler for topic {subscribed_topic}: {e}",
                        exc_info=True,
                    )

        if not matched:
            logger.warning(
                f"⚠ [MQTT] No handler found for topic: {topic}, "
                f"registered handlers: {list(self.message_handlers.keys())}"
            )

    def _on_publish(self, client, userdata, mid):
        """Callback when message published"""
        logger.debug(f"Message published, mid: {mid}")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback when subscribed to topic"""
        logger.debug(f"[MQTT] Subscribed to topic, mid: {mid}, QoS: {granted_qos}")

    def _reconnect_loop(self):
        """Background thread for automatic reconnection"""
        reconnect_attempts = 0
        while not self._stop_reconnect and self._reconnect_enabled:
            if not self.connected:
                reconnect_attempts += 1
                # Log at DEBUG level to reduce log noise during normal operation
                logger.debug(
                    f"🔄 [MQTT] Reconnection attempt {reconnect_attempts} to "
                    f"{self.broker_host}:{self.broker_port}..."
                )
                try:
                    # Try to reconnect
                    self.client.reconnect()
                    time.sleep(2)  # Wait for connection

                    # If connected, resubscribe to all topics
                    if self.connected:
                        logger.debug(
                            f"✓ [MQTT] Reconnected successfully after {reconnect_attempts} attempts"
                        )
                        reconnect_attempts = 0  # Reset counter
                        for topic, (handler, qos) in self._subscriptions.items():
                            self.subscribe(topic, handler, qos)
                        break  # Exit reconnect loop
                except Exception as e:
                    logger.debug(f"[MQTT] Reconnection attempt failed: {e}")

                # Wait before next attempt (exponential backoff, max 30s)
                wait_time = min(self._reconnect_interval * (1.5 ** min(reconnect_attempts // 5, 3)), 30)
                time.sleep(wait_time)
            else:
                # Already connected, exit
                reconnect_attempts = 0
                break

    def _start_reconnect_thread(self):
        """Start reconnection thread if not already running"""
        if self._reconnect_thread is None or not self._reconnect_thread.is_alive():
            self._reconnect_thread = threading.Thread(
                target=self._reconnect_loop, daemon=True
            )
            self._reconnect_thread.start()

    def connect(self) -> bool:
        """
        Connect to MQTT broker

        Returns:
            True if connected successfully
        """
        try:
            self.client.connect(self.broker_host, self.broker_port, self.keepalive)
            self.client.loop_start()
            # Wait for connection with timeout (non-blocking check)
            import time
            max_wait = 5  # Maximum wait time in seconds
            wait_interval = 0.1  # Check every 100ms
            waited = 0
            while not self.connected and waited < max_wait:
                time.sleep(wait_interval)
                waited += wait_interval
            return self.connected
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}", exc_info=True)
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self._stop_reconnect = True
        self._reconnect_enabled = False
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.debug("Disconnected from MQTT broker")

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        """
        Publish message to topic

        Args:
            topic: MQTT topic
            payload: Message payload (dict, will be JSON encoded)
            qos: Quality of Service (0, 1, or 2)
            retain: Retain message flag

        Returns:
            True if published successfully
        """
        if not self.connected:
            logger.warning("Not connected to MQTT broker, cannot publish")
            return False

        try:
            message = json.dumps(payload)
            result = self.client.publish(topic, message, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}, return code: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}", exc_info=True)
            return False

    def subscribe(
        self,
        topic: str,
        handler: Optional[Callable] = None,
        qos: int = 1,
    ) -> bool:
        """
        Subscribe to topic

        Args:
            topic: MQTT topic (supports wildcards: +, #)
            handler: Optional callback function(topic, payload)
            qos: Quality of Service (0, 1, or 2)

        Returns:
            True if subscribed successfully
        """
        # Store subscription for reconnection
        if handler:
            self._subscriptions[topic] = (handler, qos)
            logger.debug(f"  [MQTT] Stored subscription for reconnection: {topic}")

        if not self.connected:
            logger.warning(
                f"⚠ [MQTT] Not connected to broker, cannot subscribe to {topic} now. "
                f"Will subscribe automatically when reconnected."
            )
            # Will subscribe automatically when reconnected
            return False

        try:
            result, mid = self.client.subscribe(topic, qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                if handler:
                    self.message_handlers[topic] = handler
                logger.debug(f"✓ [MQTT] Subscribed to topic: {topic} (QoS: {qos})")
                logger.debug(
                    f"  [MQTT] Total active handlers: {len(self.message_handlers)}"
                )
                return True
            else:
                logger.error(
                    f"✗ [MQTT] Failed to subscribe to {topic}, return code: {result}"
                )
                return False
        except Exception as e:
            logger.error(f"✗ [MQTT] Error subscribing to {topic}: {e}", exc_info=True)
            return False

    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from topic

        Args:
            topic: MQTT topic

        Returns:
            True if unsubscribed successfully
        """
        if not self.connected:
            return False

        try:
            result, mid = self.client.unsubscribe(topic)
            if result == mqtt.MQTT_ERR_SUCCESS:
                if topic in self.message_handlers:
                    del self.message_handlers[topic]
                logger.info(f"Unsubscribed from topic: {topic}")
                return True
            else:
                logger.error(
                    f"Failed to unsubscribe from {topic}, return code: {result}"
                )
                return False
        except Exception as e:
            logger.error(f"Error unsubscribing from {topic}: {e}", exc_info=True)
            return False

    def is_connected(self) -> bool:
        """Check if connected to broker"""
        # Check both internal state and actual client connection
        if not self.connected:
            return False
        # Also check if client thinks it's connected
        try:
            return self.client.is_connected()
        except AttributeError:
            # Fallback to internal state if method not available
            return self.connected
