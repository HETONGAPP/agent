"""
Mock data collector (for demo and testing)
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..models.alarm import Alarm, AlarmSeverity
from .base import BaseCollector

# Try to import BMSData from integration module
try:
    from ..integrations.bms import BMSData
except ImportError:
    BMSData = None  # BMSData not available


class MockCollector(BaseCollector):
    """Mock data collector that generates simulated data for demonstration"""

    def __init__(self, source: str = "BMS"):
        super().__init__(source)
        self._pack_ids = ["PACK_001", "PACK_002", "PACK_003"]
        self._alarm_types = [
            "Cell Voltage Deviation",
            "Over Temperature",
            "Under Temperature",
            "SOC Anomaly",
            "SOH Degradation",
        ]

    async def collect_alarms(self) -> List[Alarm]:
        """Generate mock alarm data"""
        alarms = []

        # Randomly generate 0-3 alarms
        num_alarms = random.randint(0, 3)

        for i in range(num_alarms):
            alarm_type = random.choice(self._alarm_types)
            severity = random.choice(
                [
                    AlarmSeverity.WARNING,
                    AlarmSeverity.CRITICAL,
                ]
            )

            alarm = Alarm(
                alarm_id=f"ALM_{random.randint(100, 999):03d}",
                alarm_type=alarm_type,
                severity=severity,
                timestamp=datetime.now() - timedelta(minutes=random.randint(0, 60)),
                source=self.source,
                metadata={
                    "pack_id": random.choice(self._pack_ids),
                    "value": round(random.uniform(0.1, 0.5), 2),
                },
            )
            alarms.append(alarm)

        return alarms

    async def get_context_data(self, alarm_id: str) -> Dict[str, Any]:
        """Get alarm context data"""
        pack_id = random.choice(self._pack_ids)
        bms_data = await self.get_bms_data(pack_id)

        return {
            "alarm_id": alarm_id,
            "pack_id": pack_id,
            "bms_data": bms_data.to_dict(),
            "history_count": random.randint(0, 5),
        }

    async def get_bms_data(self, pack_id: str) -> BMSData:
        """Generate mock BMS data"""
        # Generate 4 cell voltages (3.4V - 3.7V)
        cell_voltages = [round(random.uniform(3.4, 3.7), 2) for _ in range(4)]

        # Generate 4 temperatures (20°C - 30°C)
        temperatures = [round(random.uniform(20, 30), 1) for _ in range(4)]

        # Calculate maximum voltage difference
        max_delta_v = round(max(cell_voltages) - min(cell_voltages), 2)

        return BMSData(
            timestamp=datetime.now(),
            cell_voltages=cell_voltages,
            temperatures=temperatures,
            soc=round(random.uniform(50, 90), 1),
            soh=round(random.uniform(80, 100), 1),
            max_delta_v=max_delta_v,
            pack_id=pack_id,
        )
