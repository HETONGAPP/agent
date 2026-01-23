"""
Read-Write Separation
Separates read and write operations for better performance
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ReadWriteSeparation:
    """Manages read-write separation"""
    
    def __init__(self, write_client, read_client=None):
        """
        Initialize read-write separation
        
        Args:
            write_client: Client for write operations
            read_client: Optional separate client for read operations (defaults to write_client)
        """
        self.write_client = write_client
        self.read_client = read_client or write_client
    
    def write(self, *args, **kwargs):
        """Write operation - uses write client"""
        return self.write_client.write(*args, **kwargs)
    
    def query(self, *args, **kwargs):
        """Query operation - uses read client"""
        return self.read_client.query(*args, **kwargs)
    
    def get_read_client(self):
        """Get read client"""
        return self.read_client
    
    def get_write_client(self):
        """Get write client"""
        return self.write_client

