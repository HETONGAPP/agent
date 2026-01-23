"""
Data collector module

Note: BMSCollector and PCSCollector have been moved to integration modules
For backward compatibility, imports are still provided here, but it's recommended to use:
- from src.integrations.bms import BMSCollector, BMSIntegration
- from src.integrations.pcs import PCSCollector, PCSIntegration
"""

from .base import BaseCollector
from .mock_collector import MockCollector

# Import from integration modules
try:
    from ..integrations.bms import BMSCollector
except ImportError:
    BMSCollector = None

try:
    from ..integrations.pcs import PCSCollector
except ImportError:
    PCSCollector = None

__all__ = [
    "BaseCollector",
    "BMSCollector",
    "PCSCollector",
    "MockCollector",
]
