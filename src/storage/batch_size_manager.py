"""
Batch Size Manager
Dynamically adjusts batch size based on load
"""

import logging
import time
from typing import Optional
from collections import deque

from .optimization_config import OptimizationConfig

logger = logging.getLogger(__name__)


class BatchSizeManager:
    """Manages dynamic batch size adjustment based on load"""
    
    def __init__(self, initial_batch_size: Optional[int] = None):
        """
        Initialize batch size manager
        
        Args:
            initial_batch_size: Initial batch size (default: from config)
        """
        self.current_batch_size = initial_batch_size or OptimizationConfig.BATCH_SIZE_DEFAULT
        self.min_batch_size = OptimizationConfig.BATCH_SIZE_MIN
        self.max_batch_size = OptimizationConfig.BATCH_SIZE_MAX
        self.adjust_interval = OptimizationConfig.BATCH_SIZE_ADJUST_INTERVAL
        
        # Track write performance
        self.write_times: deque = deque(maxlen=100)  # Last 100 write operations
        self.buffer_sizes: deque = deque(maxlen=100)  # Last 100 buffer sizes
        self.last_adjust_time = time.time()
        
        # Performance metrics
        self.avg_write_time = 0.0
        self.avg_buffer_size = 0.0
        
    def record_write(self, write_time: float, buffer_size: int):
        """
        Record a write operation for performance tracking
        
        Args:
            write_time: Time taken for write operation (seconds)
            buffer_size: Number of points written
        """
        self.write_times.append(write_time)
        self.buffer_sizes.append(buffer_size)
        
        # Update averages
        if self.write_times:
            self.avg_write_time = sum(self.write_times) / len(self.write_times)
        if self.buffer_sizes:
            self.avg_buffer_size = sum(self.buffer_sizes) / len(self.buffer_sizes)
        
        # Check if adjustment is needed
        current_time = time.time()
        if current_time - self.last_adjust_time >= self.adjust_interval:
            self._adjust_batch_size()
            self.last_adjust_time = current_time
    
    def _adjust_batch_size(self):
        """Adjust batch size based on performance metrics"""
        if not self.write_times or not self.buffer_sizes:
            return
        
        # Calculate metrics
        avg_write_time = self.avg_write_time
        avg_buffer_size = self.avg_buffer_size
        
        # If write time is high and buffer is frequently full, increase batch size
        # If write time is low and buffer is rarely full, decrease batch size
        if avg_write_time > 0.5 and avg_buffer_size >= self.current_batch_size * 0.9:
            # High load, increase batch size
            new_size = min(int(self.current_batch_size * 1.2), self.max_batch_size)
            if new_size != self.current_batch_size:
                logger.info(f"📈 Increasing batch size: {self.current_batch_size} -> {new_size} "
                          f"(avg_write_time={avg_write_time:.3f}s, avg_buffer={avg_buffer_size:.0f})")
                self.current_batch_size = new_size
        elif avg_write_time < 0.1 and avg_buffer_size < self.current_batch_size * 0.5:
            # Low load, decrease batch size for lower latency
            new_size = max(int(self.current_batch_size * 0.8), self.min_batch_size)
            if new_size != self.current_batch_size:
                logger.info(f"📉 Decreasing batch size: {self.current_batch_size} -> {new_size} "
                          f"(avg_write_time={avg_write_time:.3f}s, avg_buffer={avg_buffer_size:.0f})")
                self.current_batch_size = new_size
    
    def get_batch_size(self) -> int:
        """Get current batch size"""
        return self.current_batch_size
    
    def get_stats(self) -> dict:
        """Get batch size statistics"""
        return {
            "current_batch_size": self.current_batch_size,
            "min_batch_size": self.min_batch_size,
            "max_batch_size": self.max_batch_size,
            "avg_write_time": self.avg_write_time,
            "avg_buffer_size": self.avg_buffer_size,
            "samples": len(self.write_times),
        }

