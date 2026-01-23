"""
Query Optimizer
Optimizes queries for better performance using aggregation and caching
"""

import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, UTC

from .query_cache import QueryCache
from .optimization_config import OptimizationConfig
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Optimizes database queries"""
    
    def __init__(self, cache: Optional[QueryCache] = None, performance_monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize query optimizer
        
        Args:
            cache: Optional QueryCache instance
            performance_monitor: Optional PerformanceMonitor instance
        """
        self.cache = cache
        self.performance_monitor = performance_monitor
    
    def optimize_time_range(self, start_time: Optional[str], end_time: Optional[str]) -> tuple[str, str, str]:
        """
        Optimize time range for query based on data age
        
        Args:
            start_time: Start time string
            end_time: End time string
            
        Returns:
            Tuple of (optimized_start, optimized_end, interval)
        """
        if not start_time or not end_time:
            # Default to last 7 days
            end = datetime.now(UTC)
            start = end - timedelta(days=7)
            return start.isoformat(), end.isoformat(), "5m"
        
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            
            # Ensure timezone-aware
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=UTC)
            
            duration = end_dt - start_dt
            
            # Determine optimal interval based on duration
            if duration <= timedelta(days=1):
                interval = "1m"  # 1 minute for last 24 hours
            elif duration <= timedelta(days=7):
                interval = "5m"  # 5 minutes for last week
            elif duration <= timedelta(days=30):
                interval = "1h"  # 1 hour for last month
            elif duration <= timedelta(days=90):
                interval = "6h"  # 6 hours for last 3 months
            else:
                interval = "1d"  # 1 day for older data
            
            return start_time, end_time, interval
        except Exception as e:
            logger.warning(f"Error optimizing time range: {e}, using defaults")
            end = datetime.now(UTC)
            start = end - timedelta(days=7)
            return start.isoformat(), end.isoformat(), "5m"
    
    def should_use_cache(self, query_type: str, params: Dict[str, Any]) -> bool:
        """
        Determine if query should use cache
        
        Args:
            query_type: Type of query
            params: Query parameters
            
        Returns:
            True if cache should be used
        """
        if not self.cache:
            return False
        
        # Use cache for historical data queries
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                # Cache queries for data older than 1 hour
                age = datetime.now(UTC) - start_dt
                return age > timedelta(hours=1)
            except Exception:
                pass
        
        return False
    
    def get_cache_ttl(self, query_type: str, params: Dict[str, Any]) -> int:
        """
        Get cache TTL for query
        
        Args:
            query_type: Type of query
            params: Query parameters
            
        Returns:
            TTL in seconds
        """
        # Historical data: longer TTL
        start_time = params.get("start_time")
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                age = datetime.now(UTC) - start_dt
                if age > timedelta(days=7):
                    return OptimizationConfig.CACHE_HISTORICAL_TTL
            except Exception:
                pass
        
        # Real-time data: shorter TTL
        return OptimizationConfig.CACHE_REALTIME_TTL
    
    def optimize_aggregation(self, interval: str, metric: Optional[str] = None) -> str:
        """
        Optimize aggregation function based on metric type
        
        Args:
            interval: Time interval
            metric: Metric name
            
        Returns:
            Aggregation function name
        """
        # For most metrics, use mean for aggregation
        # For specific metrics, use appropriate function
        if metric in ["count", "events", "alarms"]:
            return "sum"
        elif metric in ["max_voltage", "max_temperature", "peak_power"]:
            return "max"
        elif metric in ["min_voltage", "min_temperature"]:
            return "min"
        else:
            return "mean"
    
    def measure_query_time(self, query_func):
        """
        Measure query execution time and record to performance monitor
        
        Args:
            query_func: Query function to measure
            
        Returns:
            Query result
        """
        start_time = time.time()
        try:
            result = query_func()
            elapsed_ms = (time.time() - start_time) * 1000
            
            if self.performance_monitor:
                self.performance_monitor.record_query_latency(elapsed_ms)
            
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            if self.performance_monitor:
                self.performance_monitor.record_query_latency(elapsed_ms)
            raise e

