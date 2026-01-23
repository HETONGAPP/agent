"""
Data collector base class
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models.alarm import Alarm

# Try to import BMSData from integration module
try:
    from ..integrations.bms import BMSData
except ImportError:
    BMSData = None  # BMSData not available


class BaseCollector(ABC):
    """Base class for data collectors"""

    def __init__(self, source: str):
        """
        Initialize collector

        Args:
            source: Data source name (BMS, PCS, EMS)
        """
        self.source = source

    @abstractmethod
    async def collect_alarms(self) -> List[Alarm]:
        """
        Collect alarm data

        Returns:
            List of alarms
        """
        pass

    @abstractmethod
    async def get_context_data(self, alarm_id: str) -> Dict[str, Any]:
        """
        Get alarm context data

        Args:
            alarm_id: Alarm ID

        Returns:
            Context data dictionary
        """
        pass

    async def get_bms_data(self, pack_id: str) -> BMSData:
        """
        Get BMS data (only implemented by BMS collector)

        Args:
            pack_id: Battery pack ID

        Returns:
            BMS data
        """
        raise NotImplementedError("This collector does not support BMS data retrieval")
