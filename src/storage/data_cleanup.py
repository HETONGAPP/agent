"""
Data Cleanup Service
Periodically cleans up expired data and deleted device data
"""

import logging
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any

from .optimization_config import OptimizationConfig

logger = logging.getLogger(__name__)


class DataCleanupService:
    """Service for cleaning up expired data"""
    
    def __init__(self, site_container_manager, device_registry=None):
        """
        Initialize data cleanup service
        
        Args:
            site_container_manager: SiteContainerManager instance
            device_registry: Optional DeviceRegistry instance
        """
        self.site_container_manager = site_container_manager
        self.device_registry = device_registry
        self.enabled = OptimizationConfig.CLEANUP_ENABLED
        self.interval = OptimizationConfig.CLEANUP_INTERVAL
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the cleanup service"""
        if not self.enabled:
            logger.info("Data cleanup service is disabled")
            return
        
        if self._running:
            logger.warning("Data cleanup service is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"✓ Data cleanup service started (interval: {self.interval}s)")
    
    async def stop(self):
        """Stop the cleanup service"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Data cleanup service stopped")
    
    async def _cleanup_loop(self):
        """Main cleanup loop"""
        while self._running:
            try:
                await self.cleanup_all_sites()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
            
            await asyncio.sleep(self.interval)
    
    async def cleanup_all_sites(self) -> Dict[str, Any]:
        """
        Cleanup data for all sites
        
        Returns:
            Cleanup statistics
        """
        stats = {
            "sites_processed": 0,
            "devices_cleaned": 0,
            "alarms_deleted": 0,
            "diagnostics_deleted": 0,
            "device_data_deleted": 0,
            "errors": 0,
        }
        
        if not self.site_container_manager:
            return stats
        
        try:
            # Get all site containers
            site_ids = self.site_container_manager.list_site_ids()
            
            for site_id in site_ids:
                try:
                    container = self.site_container_manager.get_container(site_id, auto_create=False)
                    if not container:
                        continue
                    
                    site_stats = await self.cleanup_site(container)
                    stats["sites_processed"] += 1
                    stats["devices_cleaned"] += site_stats.get("devices_cleaned", 0)
                    stats["alarms_deleted"] += site_stats.get("alarms_deleted", 0)
                    stats["diagnostics_deleted"] += site_stats.get("diagnostics_deleted", 0)
                    stats["device_data_deleted"] += site_stats.get("device_data_deleted", 0)
                except Exception as e:
                    logger.error(f"Error cleaning up site {site_id}: {e}", exc_info=True)
                    stats["errors"] += 1
            
            logger.info(f"Cleanup completed: {stats}")
        except Exception as e:
            logger.error(f"Error in cleanup_all_sites: {e}", exc_info=True)
            stats["errors"] += 1
        
        return stats
    
    async def cleanup_site(self, container) -> Dict[str, Any]:
        """
        Cleanup data for a specific site
        
        Args:
            container: SiteContainer instance
            
        Returns:
            Cleanup statistics
        """
        stats = {
            "devices_cleaned": 0,
            "alarms_deleted": 0,
            "diagnostics_deleted": 0,
            "device_data_deleted": 0,
        }
        
        try:
            # Cleanup expired alarms
            alarms_deleted = await self._cleanup_expired_alarms(container)
            stats["alarms_deleted"] = alarms_deleted
            
            # Cleanup expired diagnostics
            diagnostics_deleted = await self._cleanup_expired_diagnostics(container)
            stats["diagnostics_deleted"] = diagnostics_deleted
            
            # Cleanup deleted device data
            if self.device_registry:
                devices_cleaned, data_deleted = await self._cleanup_deleted_devices(container)
                stats["devices_cleaned"] = devices_cleaned
                stats["device_data_deleted"] = data_deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up site {container.site_id}: {e}", exc_info=True)
        
        return stats
    
    async def _cleanup_expired_alarms(self, container) -> int:
        """Cleanup expired alarms"""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(days=OptimizationConfig.ALARM_RETENTION_DAYS)
            deleted = container.delete_alarms(
                start_time=None,
                end_time=cutoff_time.isoformat(),
            )
            if deleted > 0:
                logger.info(f"Deleted {deleted} expired alarms from site {container.site_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error cleaning up expired alarms: {e}", exc_info=True)
            return 0
    
    async def _cleanup_expired_diagnostics(self, container) -> int:
        """Cleanup expired diagnostics"""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(days=OptimizationConfig.DIAGNOSTIC_RETENTION_DAYS)
            deleted = container.delete_diagnostics(
                start_time=None,
                end_time=cutoff_time.isoformat(),
            )
            if deleted > 0:
                logger.info(f"Deleted {deleted} expired diagnostics from site {container.site_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error cleaning up expired diagnostics: {e}", exc_info=True)
            return 0
    
    async def _cleanup_deleted_devices(self, container) -> tuple[int, int]:
        """
        Cleanup data for deleted devices
        
        Returns:
            Tuple of (devices_cleaned, data_deleted)
        """
        devices_cleaned = 0
        data_deleted = 0
        
        try:
            # Get all registered devices
            if not self.device_registry:
                return devices_cleaned, data_deleted
            
            registered_devices = self.device_registry.get_all_devices()
            registered_device_ids = {d.device_id for d in registered_devices}
            
            # Query all device_ids in the site's data
            # This is a simplified approach - in production, you might want to track device_ids separately
            # For now, we'll rely on InfluxDB's retention policy and manual cleanup
            
            # Note: Full implementation would require querying device_ids from InfluxDB
            # and comparing with registered devices
            
        except Exception as e:
            logger.error(f"Error cleaning up deleted devices: {e}", exc_info=True)
        
        return devices_cleaned, data_deleted

