"""
Sharding Strategy
Optimizes data sharding by time and device type
"""

import logging
from datetime import datetime, UTC
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ShardingStrategy:
    """Manages data sharding strategy"""
    
    @staticmethod
    def get_bucket_name(site_id: str, year: Optional[int] = None) -> str:
        """
        Get bucket name with optional year-based sharding
        
        Args:
            site_id: Site ID
            year: Optional year for time-based sharding
            
        Returns:
            Bucket name
        """
        if year:
            return f"site_{site_id}_{year}"
        return f"site_{site_id}"
    
    @staticmethod
    def get_year_from_timestamp(timestamp: datetime) -> int:
        """
        Get year from timestamp
        
        Args:
            timestamp: Datetime object
            
        Returns:
            Year
        """
        return timestamp.year
    
    @staticmethod
    def should_create_new_bucket(current_year: int, data_year: int) -> bool:
        """
        Determine if a new bucket should be created for the year
        
        Args:
            current_year: Current year
            data_year: Year of the data
            
        Returns:
            True if new bucket should be created
        """
        return data_year != current_year
    
    @staticmethod
    def get_device_type_bucket(site_id: str, device_type: str) -> str:
        """
        Get bucket name for device type sharding
        
        Args:
            site_id: Site ID
            device_type: Device type
            
        Returns:
            Bucket name
        """
        return f"site_{site_id}_{device_type.lower()}"

