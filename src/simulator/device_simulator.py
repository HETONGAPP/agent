#!/usr/bin/env python3
"""
Device Simulator for BMS and PCS
Continuously generates and publishes device data via MQTT
"""

import argparse
import json
import logging
import random
import sys
import time
import zoneinfo
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

# Load environment variables
load_dotenv()

try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("Error: paho-mqtt not installed. Please run: pip install paho-mqtt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Montreal timezone (EST/EDT, UTC-5 or UTC-4)
MONTREAL_TZ = zoneinfo.ZoneInfo("America/Montreal")


def format_montreal_time(utc_time):
    """Format UTC datetime to Montreal time for display"""
    if isinstance(utc_time, str):
        # Parse ISO format string
        if utc_time.endswith("Z"):
            utc_time = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        else:
            utc_time = datetime.fromisoformat(utc_time)
            if utc_time.tzinfo is None:
                utc_time = utc_time.replace(tzinfo=timezone.utc)

    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    elif utc_time.tzinfo != timezone.utc:
        utc_time = utc_time.astimezone(timezone.utc)

    montreal_time = utc_time.astimezone(MONTREAL_TZ)
    tz_name = "EST" if montreal_time.dst() is None else "EDT"
    return f"{montreal_time.strftime('%Y-%m-%d %H:%M:%S')} {tz_name}"


class DeviceSimulator:
    """Device simulator for BMS or PCS devices"""

    def __init__(
        self,
        device_type: str,
        device_id: str,
        site_id: Optional[str] = None,
        site_name: Optional[str] = None,
        broker_url: str = "mqtt://localhost:1883",
        username: Optional[str] = None,
        password: Optional[str] = None,
        interval: float = 5.0,  # seconds
    ):
        """
        Initialize device simulator

        Args:
            device_type: Device type (BMS or PCS)
            device_id: Device ID
            site_id: Site ID (optional)
            site_name: Site name (optional)
            broker_url: MQTT broker URL
            username: MQTT username (optional)
            password: MQTT password (optional)
            interval: Data publishing interval in seconds
        """
        self.device_type = device_type.upper()
        self.device_id = device_id
        self.site_id = site_id or "SITE_001"
        self.site_name = site_name or f"Site {site_id or '001'}"
        self.interval = interval
        self.running = False

        # Parse broker URL
        parsed = urlparse(broker_url)
        self.broker_host = parsed.hostname or "localhost"
        self.broker_port = parsed.port or 1883
        self.use_tls = parsed.scheme == "mqtts"

        # Initialize MQTT client
        self.client = mqtt.Client(client_id=f"{device_type}_{device_id}_simulator")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        if username and password:
            self.client.username_pw_set(username, password)

        if self.use_tls:
            self.client.tls_set()

        # Initialize device state
        self._init_device_state()

    def _init_device_state(self):
        """Initialize device state based on type"""
        if self.device_type == "BMS":
            # Initialize with a base voltage, then add small variations
            # Normal operation: cell voltages should be very close (< 0.05V deviation)
            base_voltage = random.uniform(3.5, 3.6)  # Base voltage for all cells
            self.state = {
                "soc": random.uniform(50, 90),
                "soh": random.uniform(80, 100),
                # Cell voltages with small deviation (normal: < 0.05V)
                "cell_voltages": [
                    base_voltage + random.uniform(-0.02, 0.02) for _ in range(4)
                ],
                "temperatures": [random.uniform(20, 30) for _ in range(4)],
            }
        elif self.device_type == "PCS":
            self.state = {
                "active_power": random.uniform(0, 100),
                "reactive_power": random.uniform(-10, 10),
                "voltage": random.uniform(380, 420),
                "current": random.uniform(0, 200),
                "frequency": random.uniform(49.5, 50.5),
                "efficiency": random.uniform(85, 98),
                "status": "running",
                "temperature": random.uniform(25, 45),
            }
        else:
            raise ValueError(f"Unsupported device type: {self.device_type}")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info(
                f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}"
            )
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection, return code: {rc}")

    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published, mid: {mid}")

    def _generate_bms_data(self) -> dict:
        """Generate BMS data with realistic variations"""
        # Gradually change SOC (simulate charging/discharging)
        soc_change = random.uniform(-0.5, 0.5)
        self.state["soc"] = max(0, min(100, self.state["soc"] + soc_change))

        # SOH slowly decreases over time
        soh_change = random.uniform(-0.01, 0)
        self.state["soh"] = max(0, min(100, self.state["soh"] + soh_change))

        # Cell voltages vary slightly
        # Normal operation: small variations to keep max_delta_v < 0.05V
        # Occasionally (5% chance) introduce larger deviation for testing
        if random.random() < 0.05:  # 5% chance of larger deviation
            # Simulate abnormal condition: one cell deviates more
            deviation = random.uniform(-0.05, 0.05)
            cell_idx = random.randint(0, len(self.state["cell_voltages"]) - 1)
            self.state["cell_voltages"][cell_idx] = max(
                3.0, min(4.2, self.state["cell_voltages"][cell_idx] + deviation)
            )
            # Other cells change slightly
            for i, v in enumerate(self.state["cell_voltages"]):
                if i != cell_idx:
                    self.state["cell_voltages"][i] = max(
                        3.0, min(4.2, v + random.uniform(-0.01, 0.01))
                    )
        else:
            # Normal operation: all cells vary slightly and stay close
            self.state["cell_voltages"] = [
                max(3.0, min(4.2, v + random.uniform(-0.01, 0.01)))
                for v in self.state["cell_voltages"]
            ]

        # Temperatures vary with SOC and time
        temp_base = 25 + (self.state["soc"] - 50) * 0.1
        self.state["temperatures"] = [
            max(15, min(50, temp_base + random.uniform(-2, 2))) for _ in range(4)
        ]

        # Calculate derived values
        max_voltage = max(self.state["cell_voltages"])
        min_voltage = min(self.state["cell_voltages"])
        max_delta_v = round(max_voltage - min_voltage, 3)
        max_temp = max(self.state["temperatures"])
        min_temp = min(self.state["temperatures"])

        return {
            "device_id": self.device_id,
            "device_type": "BMS",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "simulator",
            "site_id": self.site_id,
            "site_name": self.site_name,
            "data": {
                "cell_voltages": [round(v, 3) for v in self.state["cell_voltages"]],
                "temperatures": [round(t, 1) for t in self.state["temperatures"]],
                "soc": round(self.state["soc"], 1),
                "soh": round(self.state["soh"], 1),
                "max_delta_v": max_delta_v,
                "max_voltage": round(max_voltage, 3),
                "min_voltage": round(min_voltage, 3),
                "max_temperature": round(max_temp, 1),
                "min_temperature": round(min_temp, 1),
                "pack_id": f"PACK_{self.device_id}",
            },
            "metadata": {
                "simulator": True,
                "device_id": self.device_id,
            },
        }

    def _generate_pcs_data(self) -> dict:
        """Generate PCS data with realistic variations"""
        # Active power varies based on load
        power_change = random.uniform(-5, 5)
        self.state["active_power"] = max(
            0, min(100, self.state["active_power"] + power_change)
        )

        # Reactive power varies
        self.state["reactive_power"] = random.uniform(-10, 10)

        # Voltage varies slightly around nominal
        self.state["voltage"] = max(
            350, min(450, self.state["voltage"] + random.uniform(-2, 2))
        )

        # Current proportional to power
        if self.state["voltage"] > 0:
            self.state["current"] = (self.state["active_power"] * 1000) / (
                self.state["voltage"] * 1.732
            )  # 3-phase

        # Frequency varies slightly
        self.state["frequency"] = random.uniform(49.8, 50.2)

        # Efficiency varies with load
        load_factor = self.state["active_power"] / 100
        self.state["efficiency"] = 85 + (load_factor * 10) + random.uniform(-2, 2)
        self.state["efficiency"] = max(80, min(98, self.state["efficiency"]))

        # Temperature varies with power
        temp_base = 30 + (self.state["active_power"] / 100) * 15
        self.state["temperature"] = max(20, min(60, temp_base + random.uniform(-3, 3)))

        # Status changes occasionally
        if random.random() < 0.01:  # 1% chance
            self.state["status"] = random.choice(["running", "stopped", "fault"])

        return {
            "device_id": self.device_id,
            "device_type": "PCS",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "simulator",
            "site_id": self.site_id,
            "site_name": self.site_name,
            "data": {
                "active_power": round(self.state["active_power"], 2),
                "reactive_power": round(self.state["reactive_power"], 2),
                "voltage": round(self.state["voltage"], 1),
                "current": round(self.state["current"], 2),
                "frequency": round(self.state["frequency"], 2),
                "efficiency": round(self.state["efficiency"], 2),
                "status": self.state["status"],
                "temperature": round(self.state["temperature"], 1),
                "grid_connection_status": "connected"
                if self.state["status"] == "running"
                else "disconnected",
            },
            "metadata": {
                "simulator": True,
                "device_id": self.device_id,
            },
        }

    def _get_topic(self) -> str:
        """Get MQTT topic for this device"""
        return f"sites/{self.site_id}/data/{self.device_type.lower()}"

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            time.sleep(1)  # Wait for connection
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")

    def run(self):
        """Run simulator continuously"""
        if not self.connect():
            return

        self.running = True
        topic = self._get_topic()

        logger.info(
            f"Starting {self.device_type} simulator for device {self.device_id}"
        )
        logger.info(f"Publishing to topic: {topic}")
        logger.info(f"Interval: {self.interval} seconds")
        logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                # Generate data
                if self.device_type == "BMS":
                    data = self._generate_bms_data()
                elif self.device_type == "PCS":
                    data = self._generate_pcs_data()
                else:
                    logger.error(f"Unsupported device type: {self.device_type}")
                    break

                # Publish to MQTT
                payload = json.dumps(data, ensure_ascii=False)
                result = self.client.publish(topic, payload, qos=1)

                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    # Parse timestamp from data to display in Montreal time
                    timestamp_str = data.get("timestamp", "")
                    montreal_time_str = (
                        format_montreal_time(timestamp_str) if timestamp_str else "N/A"
                    )
                    logger.info(
                        f"Published {self.device_type} data: "
                        f"device_id={self.device_id}, "
                        f"time={montreal_time_str}, "
                        f"soc={data['data'].get('soc', 'N/A') if self.device_type == 'BMS' else 'N/A'}, "
                        f"power={data['data'].get('active_power', 'N/A') if self.device_type == 'PCS' else 'N/A'}kW"
                    )
                else:
                    logger.error(f"Failed to publish message, return code: {result.rc}")

                # Wait for next interval
                time.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping simulator...")
        finally:
            self.disconnect()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Device Simulator for BMS and PCS devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simulate BMS device
  %(prog)s --type BMS --device-id BMS_001

  # Simulate PCS device with custom site
  %(prog)s --type PCS --device-id PCS_001 --site-id SITE_002 --site-name "Data Center 2"

  # Simulate with custom interval
  %(prog)s --type BMS --device-id BMS_001 --interval 10

  # Simulate with MQTT authentication
  %(prog)s --type PCS --device-id PCS_001 --broker-url mqtt://broker:1883 --username user --password pass
        """,
    )

    parser.add_argument(
        "--type",
        choices=["BMS", "PCS"],
        required=True,
        help="Device type (BMS or PCS)",
    )
    parser.add_argument(
        "--device-id",
        required=True,
        help="Device ID (e.g., BMS_001, PCS_001)",
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help="Site ID (default: SITE_001)",
    )
    parser.add_argument(
        "--site-name",
        default=None,
        help="Site name (default: Site {site_id})",
    )
    parser.add_argument(
        "--broker-url",
        default=None,
        help="MQTT broker URL (default: from MQTT_BROKER_URL env or mqtt://localhost:1883)",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="MQTT username (default: from MQTT_USERNAME env)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="MQTT password (default: from MQTT_PASSWORD env)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Data publishing interval in seconds (default: 5.0)",
    )

    args = parser.parse_args()

    # Get broker URL from args or environment
    broker_url = args.broker_url or os.getenv(
        "MQTT_BROKER_URL", "mqtt://localhost:1883"
    )
    username = args.username or os.getenv("MQTT_USERNAME")
    password = args.password or os.getenv("MQTT_PASSWORD")

    # Create and run simulator
    simulator = DeviceSimulator(
        device_type=args.type,
        device_id=args.device_id,
        site_id=args.site_id,
        site_name=args.site_name,
        broker_url=broker_url,
        username=username,
        password=password,
        interval=args.interval,
    )

    simulator.run()


if __name__ == "__main__":
    import os
    from urllib.parse import urlparse

    # Make urlparse available for the class
    urlparse = urlparse
    main()
