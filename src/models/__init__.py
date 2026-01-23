"""
Data models module
Defines all data structures and types

Note: BMSData and PCSData have been moved to integration modules
For backward compatibility, imports are still provided here, but it's recommended to use:
- from src.integrations.bms import BMSData
- from src.integrations.pcs import PCSData
"""

from .alarm import Alarm, AlarmSeverity
from .device_data import DeviceData, DeviceType, TMSData, UPSData
from .diagnostic import DiagnosticReport, RiskLevel

# Import from integration modules
try:
    from ..integrations.bms import BMSData
except ImportError:
    BMSData = None

try:
    from ..integrations.pcs import PCSData
except ImportError:
    # PCSData might still be in device_data for backward compatibility
    try:
        from .device_data import PCSData
    except ImportError:
        PCSData = None

__all__ = [
    "Alarm",
    "AlarmSeverity",
    "BMSData",
    "DeviceData",
    "DeviceType",
    "PCSData",
    "UPSData",
    "TMSData",
    "DiagnosticReport",
    "RiskLevel",
]
