"""
Alerting System
Complete monitoring and alerting system for storage performance
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, UTC

from .optimization_config import OptimizationConfig
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class AlertingSystem:
    """Complete alerting system for storage monitoring"""
    
    def __init__(self, performance_monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize alerting system
        
        Args:
            performance_monitor: Optional PerformanceMonitor instance
        """
        self.performance_monitor = performance_monitor
        self.alert_callbacks: List[Callable] = []
        self.alert_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Alert thresholds
        self.thresholds = {
            "storage_usage_percent": OptimizationConfig.ALERT_STORAGE_USAGE_PERCENT,
            "write_latency_ms": OptimizationConfig.ALERT_WRITE_LATENCY_MS,
            "query_latency_ms": OptimizationConfig.ALERT_QUERY_LATENCY_MS,
            "cache_hit_rate_percent": OptimizationConfig.ALERT_CACHE_HIT_RATE_PERCENT,
        }
        
        # Alert state tracking
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add alert callback function"""
        self.alert_callbacks.append(callback)
    
    def check_storage_usage(self, usage_percent: float, site_id: Optional[str] = None):
        """
        Check storage usage and alert if threshold exceeded
        
        Args:
            usage_percent: Storage usage percentage
            site_id: Optional site ID
        """
        threshold = self.thresholds["storage_usage_percent"]
        if usage_percent > threshold:
            alert_key = f"storage_usage_{site_id or 'global'}"
            if alert_key not in self.active_alerts:
                self._trigger_alert(
                    "high_storage_usage",
                    {
                        "metric": "storage_usage",
                        "value": usage_percent,
                        "threshold": threshold,
                        "site_id": site_id,
                        "message": f"Storage usage ({usage_percent:.2f}%) exceeds threshold ({threshold}%)",
                    },
                    alert_key,
                )
        else:
            # Clear alert if usage is below threshold
            alert_key = f"storage_usage_{site_id or 'global'}"
            if alert_key in self.active_alerts:
                self._clear_alert(alert_key)
    
    def check_write_latency(self, latency_ms: float):
        """Check write latency and alert if threshold exceeded"""
        threshold = self.thresholds["write_latency_ms"]
        if latency_ms > threshold:
            alert_key = "write_latency"
            if alert_key not in self.active_alerts:
                self._trigger_alert(
                    "high_write_latency",
                    {
                        "metric": "write_latency",
                        "value": latency_ms,
                        "threshold": threshold,
                        "message": f"Write latency ({latency_ms:.2f}ms) exceeds threshold ({threshold}ms)",
                    },
                    alert_key,
                )
        else:
            if alert_key in self.active_alerts:
                self._clear_alert(alert_key)
    
    def check_query_latency(self, latency_ms: float):
        """Check query latency and alert if threshold exceeded"""
        threshold = self.thresholds["query_latency_ms"]
        if latency_ms > threshold:
            alert_key = "query_latency"
            if alert_key not in self.active_alerts:
                self._trigger_alert(
                    "high_query_latency",
                    {
                        "metric": "query_latency",
                        "value": latency_ms,
                        "threshold": threshold,
                        "message": f"Query latency ({latency_ms:.2f}ms) exceeds threshold ({threshold}ms)",
                    },
                    alert_key,
                )
        else:
            if alert_key in self.active_alerts:
                self._clear_alert(alert_key)
    
    def check_cache_hit_rate(self, hit_rate: float):
        """Check cache hit rate and alert if threshold exceeded"""
        threshold = self.thresholds["cache_hit_rate_percent"]
        if hit_rate < threshold:
            alert_key = "cache_hit_rate"
            if alert_key not in self.active_alerts:
                self._trigger_alert(
                    "low_cache_hit_rate",
                    {
                        "metric": "cache_hit_rate",
                        "value": hit_rate,
                        "threshold": threshold,
                        "message": f"Cache hit rate ({hit_rate:.2f}%) below threshold ({threshold}%)",
                    },
                    alert_key,
                )
        else:
            if alert_key in self.active_alerts:
                self._clear_alert(alert_key)
    
    def _trigger_alert(self, alert_type: str, alert_data: Dict[str, Any], alert_key: str):
        """Trigger alert"""
        alert = {
            "type": alert_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": "warning",
            **alert_data,
        }
        
        self.active_alerts[alert_key] = alert
        self.alert_history.append(alert)
        
        # Keep only recent history
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        logger.warning(f"⚠ Alert: {alert['message']}")
        
        # Call callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert_type, alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}", exc_info=True)
    
    def _clear_alert(self, alert_key: str):
        """Clear active alert"""
        if alert_key in self.active_alerts:
            alert = self.active_alerts.pop(alert_key)
            logger.info(f"✓ Alert cleared: {alert.get('message', alert_key)}")
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get alert history"""
        return self.alert_history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get alerting statistics"""
        return {
            "active_alerts": len(self.active_alerts),
            "total_alerts": len(self.alert_history),
            "thresholds": self.thresholds,
        }

