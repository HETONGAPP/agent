"""
Optimization Manager
Manages all storage optimizations
"""

import logging
import asyncio
from typing import Optional

from .optimization_config import OptimizationConfig
from .batch_size_manager import BatchSizeManager
from .data_cleanup import DataCleanupService
from .downsampling import DownsamplingService
from .performance_monitor import PerformanceMonitor
from .data_archival import DataArchivalService
from .query_cache import QueryCache

logger = logging.getLogger(__name__)


class OptimizationManager:
    """Manages all storage optimizations"""
    
    def __init__(
        self,
        site_container_manager=None,
        device_registry=None,
    ):
        """
        Initialize optimization manager
        
        Args:
            site_container_manager: SiteContainerManager instance
            device_registry: Optional DeviceRegistry instance
        """
        self.site_container_manager = site_container_manager
        self.device_registry = device_registry
        
        # Initialize components
        self.batch_size_manager = BatchSizeManager()
        self.cache = QueryCache(**OptimizationConfig.get_cache_config())
        self.cleanup_service = DataCleanupService(site_container_manager, device_registry)
        self.downsampling_service = DownsamplingService(site_container_manager)
        self.performance_monitor = PerformanceMonitor()
        self.archival_service = DataArchivalService(site_container_manager)
        
        self._started = False
    
    async def start(self):
        """Start all optimization services"""
        if self._started:
            logger.warning("Optimization manager is already started")
            return
        
        logger.info("Starting storage optimization services...")
        
        # Start services
        await self.cleanup_service.start()
        await self.downsampling_service.start()
        await self.performance_monitor.start()
        await self.archival_service.start()
        
        self._started = True
        logger.info("✓ All optimization services started")
    
    async def stop(self):
        """Stop all optimization services"""
        if not self._started:
            return
        
        logger.info("Stopping storage optimization services...")
        
        await self.cleanup_service.stop()
        await self.downsampling_service.stop()
        await self.performance_monitor.stop()
        await self.archival_service.stop()
        
        self._started = False
        logger.info("All optimization services stopped")
    
    def get_batch_size(self) -> int:
        """Get current batch size"""
        return self.batch_size_manager.get_batch_size()
    
    def get_cache(self) -> QueryCache:
        """Get cache instance"""
        return self.cache
    
    def get_stats(self) -> dict:
        """Get optimization statistics"""
        return {
            "batch_size": self.batch_size_manager.get_stats(),
            "cache": self.cache.get_stats() if self.cache else None,
            "performance": self.performance_monitor.get_metrics() if self.performance_monitor.enabled else None,
            "started": self._started,
        }

