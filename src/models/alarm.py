"""
Alarm data model
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict


class AlarmSeverity(str, Enum):
    """Alarm severity level"""

    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"


class AlarmLevel(str, Enum):
    """Alarm level - indicates the scope of the alarm"""

    SYSTEM = "system_level"  # System-wide alarms (no specific site)
    SITE = "site_level"  # Site-level alarms (affects entire site)
    DEVICE = "device_level"  # Device-specific alarms (detailed device issues)


@dataclass
class Alarm:
    """Alarm data model"""

    alarm_id: str
    alarm_type: str
    severity: AlarmSeverity
    timestamp: datetime
    source: str  # Data source: BMS, PCS, EMS
    alarm_level: AlarmLevel = AlarmLevel.DEVICE  # Default to device level
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "alarm_id": self.alarm_id,
            "alarm_type": self.alarm_type,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "alarm_level": self.alarm_level.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alarm":
        """Create from dictionary"""
        # Handle alarm_level with backward compatibility
        alarm_level = data.get("alarm_level", "device_level")
        if isinstance(alarm_level, str):
            try:
                alarm_level = AlarmLevel(alarm_level)
            except ValueError:
                # Default to device_level for unknown values
                alarm_level = AlarmLevel.DEVICE
        elif not isinstance(alarm_level, AlarmLevel):
            alarm_level = AlarmLevel.DEVICE
        
        return cls(
            alarm_id=data["alarm_id"],
            alarm_type=data["alarm_type"],
            severity=AlarmSeverity(data["severity"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            alarm_level=alarm_level,
            metadata=data.get("metadata", {}),
        )
