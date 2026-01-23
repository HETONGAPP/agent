"""
Downsampling Service
Automatically downsamples historical data to reduce storage
"""

import logging
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List

from .optimization_config import OptimizationConfig

logger = logging.getLogger(__name__)


class DownsamplingService:
    """Service for downsampling historical data"""
    
    def __init__(self, site_container_manager):
        """
        Initialize downsampling service
        
        Args:
            site_container_manager: SiteContainerManager instance
        """
        self.site_container_manager = site_container_manager
        self.enabled = OptimizationConfig.DOWNSAMPLING_ENABLED
        self.intervals = OptimizationConfig.DOWNSAMPLING_INTERVALS
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the downsampling service"""
        if not self.enabled:
            logger.info("Downsampling service is disabled")
            return
        
        if self._running:
            logger.warning("Downsampling service is already running")
            return
        
        self._running = True
        # Run downsampling daily
        self._task = asyncio.create_task(self._downsampling_loop())
        logger.info("✓ Downsampling service started")
    
    async def stop(self):
        """Stop the downsampling service"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Downsampling service stopped")
    
    async def _downsampling_loop(self):
        """Main downsampling loop - runs daily"""
        while self._running:
            try:
                await self.downsample_all_sites()
            except Exception as e:
                logger.error(f"Error in downsampling loop: {e}", exc_info=True)
            
            # Run once per day
            await asyncio.sleep(86400)  # 24 hours
    
    async def downsample_all_sites(self) -> Dict[str, Any]:
        """
        Downsample data for all sites
        
        Returns:
            Downsampling statistics
        """
        stats = {
            "sites_processed": 0,
            "intervals_created": 0,
            "errors": 0,
        }
        
        if not self.site_container_manager:
            return stats
        
        try:
            site_ids = self.site_container_manager.list_site_ids()
            
            for site_id in site_ids:
                try:
                    container = self.site_container_manager.get_container(site_id, auto_create=False)
                    if not container:
                        continue
                    
                    site_stats = await self.downsample_site(container)
                    stats["sites_processed"] += 1
                    stats["intervals_created"] += site_stats.get("intervals_created", 0)
                except Exception as e:
                    logger.error(f"Error downsampling site {site_id}: {e}", exc_info=True)
                    stats["errors"] += 1
            
            logger.info(f"Downsampling completed: {stats}")
        except Exception as e:
            logger.error(f"Error in downsample_all_sites: {e}", exc_info=True)
            stats["errors"] += 1
        
        return stats
    
    async def downsample_site(self, container) -> Dict[str, Any]:
        """
        Downsample data for a specific site
        
        Args:
            container: SiteContainer instance
            
        Returns:
            Downsampling statistics
        """
        stats = {
            "intervals_created": 0,
        }
        
        try:
            # Create downsampled buckets for each interval
            for interval_name, interval_config in self.intervals.items():
                try:
                    await self._create_downsampled_bucket(
                        container,
                        interval_name,
                        interval_config,
                    )
                    stats["intervals_created"] += 1
                except Exception as e:
                    logger.error(f"Error creating downsampled bucket {interval_name}: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error downsampling site {container.site_id}: {e}", exc_info=True)
        
        return stats
    
    async def _create_downsampled_bucket(
        self,
        container,
        interval_name: str,
        interval_config: Dict[str, Any],
    ):
        """
        Create downsampled bucket for a specific interval
        
        Args:
            container: SiteContainer instance
            interval_name: Interval name (e.g., "1m", "5m", "1h", "1d")
            interval_config: Interval configuration
        """
        # This is a placeholder - actual implementation would:
        # 1. Create a new bucket for downsampled data (e.g., site_{site_id}_1m)
        # 2. Set up continuous queries or tasks to aggregate data
        # 3. Configure retention policy for the downsampled bucket
        
        logger.debug(f"Creating downsampled bucket {interval_name} for site {container.site_id}")
        
        # Note: InfluxDB 2.x uses Tasks for downsampling
        # This would require InfluxDB Tasks API integration
        # For now, we'll log the intention
        
        retention_days = interval_config.get("retention_days", 30)
        source = interval_config.get("source", "raw")
        
        logger.info(
            f"Downsampling configuration for {interval_name}: "
            f"retention={retention_days} days, source={source}"
        )

