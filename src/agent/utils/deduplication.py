"""
Data deduplication utilities
"""
import logging
import time
from typing import Dict
from ...models.device_data import DeviceData

logger = logging.getLogger(__name__)


class DataDeduplicator:
    """Handles data deduplication to prevent duplicate processing"""
    
    def __init__(self, dedup_window: float = 3.0, cleanup_interval: float = 60.0):
        """
        Initialize deduplicator
        
        Args:
            dedup_window: Deduplication window in seconds (default: 3.0)
            cleanup_interval: Cleanup interval in seconds (default: 60.0)
        """
        self._processed_keys: Dict[str, float] = {}
        self._dedup_window = dedup_window
        self._dedup_cleanup_interval = cleanup_interval
        self._last_cleanup: float = time.time()
    
    def generate_key(self, device_data: DeviceData) -> str:
        """
        Generate deduplication key for device data
        
        Args:
            device_data: DeviceData to generate key for
            
        Returns:
            Deduplication key string
        """
        timestamp_seconds = int(device_data.timestamp.timestamp())
        return f"{device_data.device_id}:{timestamp_seconds}"
    
    def is_duplicate(self, device_data: DeviceData) -> bool:
        """
        Check if device data is a duplicate
        
        Args:
            device_data: DeviceData to check
            
        Returns:
            True if duplicate, False otherwise
        """
        dedup_key = self.generate_key(device_data)
        current_time = time.time()
        
        # Check if key exists and is within deduplication window
        if dedup_key in self._processed_keys:
            processing_time = self._processed_keys[dedup_key]
            if current_time - processing_time < self._dedup_window:
                return True
        
        # Cleanup old keys periodically
        if current_time - self._last_cleanup > self._dedup_cleanup_interval:
            self._cleanup_old_keys(current_time)
            self._last_cleanup = current_time
        
        # Mark as processed
        self._processed_keys[dedup_key] = current_time
        return False
    
    def _cleanup_old_keys(self, current_time: float):
        """Clean up old deduplication keys outside the window"""
        keys_to_remove = [
            key for key, processing_time in self._processed_keys.items()
            if current_time - processing_time > self._dedup_window
        ]
        for key in keys_to_remove:
            self._processed_keys.pop(key, None)
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old deduplication keys")
    
    def remove_device_keys(self, device_id: str):
        """
        Remove all deduplication keys for a specific device
        
        Args:
            device_id: Device ID to remove keys for
        """
        keys_to_remove = [k for k in self._processed_keys.keys() if k.startswith(f"{device_id}:")]
        for key in keys_to_remove:
            self._processed_keys.pop(key, None)
        
        if keys_to_remove:
            logger.debug(f"Removed {len(keys_to_remove)} deduplication keys for device {device_id}")
