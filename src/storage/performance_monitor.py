"""
Performance Monitor
Monitors storage performance metrics and alerts on thresholds
"""

import logging
import asyncio
import time
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List, Callable
from collections import deque

from .optimization_config import OptimizationConfig

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitors storage performance metrics"""
    
    def __init__(self):
        """Initialize performance monitor"""
        self.enabled = OptimizationConfig.MONITORING_ENABLED
        self.interval = OptimizationConfig.MONITORING_INTERVAL
        
        # Metrics storage
        self.write_latencies: deque = deque(maxlen=1000)
        self.query_latencies: deque = deque(maxlen=1000)
        self.write_throughputs: deque = deque(maxlen=100)
        self.cache_hit_rates: deque = deque(maxlen=100)
        
        # Alert callbacks
        self.alert_callbacks: List[Callable] = []
        
        # Running state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add alert callback function"""
        self.alert_callbacks.append(callback)
    
    def record_write_latency(self, latency_ms: float):
        """Record write latency"""
        if self.enabled:
            self.write_latencies.append(latency_ms)
    
    def record_query_latency(self, latency_ms: float):
        """Record query latency"""
        if self.enabled:
            self.query_latencies.append(latency_ms)
    
    def record_write_throughput(self, points_per_second: float):
        """Record write throughput"""
        if self.enabled:
            self.write_throughputs.append(points_per_second)
    
    def record_cache_hit_rate(self, hit_rate: float):
        """Record cache hit rate"""
        if self.enabled:
            self.cache_hit_rates.append(hit_rate)
    
    async def start(self):
        """Start monitoring"""
        if not self.enabled:
            logger.info("Performance monitoring is disabled")
            return
        
        if self._running:
            logger.warning("Performance monitor is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"✓ Performance monitor started (interval: {self.interval}s)")
    
    async def stop(self):
        """Stop monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitor stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                metrics = self.get_metrics()
                self._check_alerts(metrics)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
            await asyncio.sleep(self.interval)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        metrics = {
            "timestamp": datetime.now(UTC).isoformat(),
            "write_latency": {
                "avg": self._avg(self.write_latencies),
                "max": max(self.write_latencies) if self.write_latencies else 0,
                "min": min(self.write_latencies) if self.write_latencies else 0,
                "samples": len(self.write_latencies),
            },
            "query_latency": {
                "avg": self._avg(self.query_latencies),
                "max": max(self.query_latencies) if self.query_latencies else 0,
                "min": min(self.query_latencies) if self.query_latencies else 0,
                "samples": len(self.query_latencies),
            },
            "write_throughput": {
                "avg": self._avg(self.write_throughputs),
                "current": self.write_throughputs[-1] if self.write_throughputs else 0,
            },
            "cache_hit_rate": {
                "avg": self._avg(self.cache_hit_rates),
                "current": self.cache_hit_rates[-1] if self.cache_hit_rates else 0,
            },
        }
        return metrics
    
    def _avg(self, values: deque) -> float:
        """Calculate average of deque values"""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    def _check_alerts(self, metrics: Dict[str, Any]):
        """Check metrics against alert thresholds"""
        # Check write latency
        avg_write_latency = metrics["write_latency"]["avg"]
        if avg_write_latency > OptimizationConfig.ALERT_WRITE_LATENCY_MS:
            self._trigger_alert(
                "high_write_latency",
                {
                    "metric": "write_latency",
                    "value": avg_write_latency,
                    "threshold": OptimizationConfig.ALERT_WRITE_LATENCY_MS,
                    "message": f"Write latency ({avg_write_latency:.2f}ms) exceeds threshold "
                              f"({OptimizationConfig.ALERT_WRITE_LATENCY_MS}ms)",
                }
            )
        
        # Check query latency
        avg_query_latency = metrics["query_latency"]["avg"]
        if avg_query_latency > OptimizationConfig.ALERT_QUERY_LATENCY_MS:
            self._trigger_alert(
                "high_query_latency",
                {
                    "metric": "query_latency",
                    "value": avg_query_latency,
                    "threshold": OptimizationConfig.ALERT_QUERY_LATENCY_MS,
                    "message": f"Query latency ({avg_query_latency:.2f}ms) exceeds threshold "
                              f"({OptimizationConfig.ALERT_QUERY_LATENCY_MS}ms)",
                }
            )
        
        # Check cache hit rate
        avg_cache_hit_rate = metrics["cache_hit_rate"]["avg"]
        if avg_cache_hit_rate < OptimizationConfig.ALERT_CACHE_HIT_RATE_PERCENT:
            self._trigger_alert(
                "low_cache_hit_rate",
                {
                    "metric": "cache_hit_rate",
                    "value": avg_cache_hit_rate,
                    "threshold": OptimizationConfig.ALERT_CACHE_HIT_RATE_PERCENT,
                    "message": f"Cache hit rate ({avg_cache_hit_rate:.2f}%) below threshold "
                              f"({OptimizationConfig.ALERT_CACHE_HIT_RATE_PERCENT}%)",
                }
            )
    
    def _trigger_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """Trigger alert callbacks"""
        alert = {
            "type": alert_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **alert_data,
        }
        
        logger.warning(f"⚠ Performance alert: {alert['message']}")
        
        for callback in self.alert_callbacks:
            try:
                callback(alert_type, alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}", exc_info=True)

