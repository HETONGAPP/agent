"""
Storage Optimization Configuration
Centralized configuration for all storage optimizations
"""

import os
from typing import Dict, Any, Optional

class OptimizationConfig:
    """Storage optimization configuration"""
    
    # Batch write configuration
    BATCH_SIZE_DEFAULT = int(os.getenv("INFLUXDB_BATCH_SIZE", "500"))
    BATCH_SIZE_MIN = 100
    BATCH_SIZE_MAX = 2000
    BATCH_SIZE_ADJUST_INTERVAL = 60  # seconds
    
    # Retention policy (in days)
    RAW_DATA_RETENTION_DAYS = int(os.getenv("RAW_DATA_RETENTION_DAYS", "30"))
    DOWNSAMPLED_DATA_RETENTION_DAYS = int(os.getenv("DOWNSAMPLED_DATA_RETENTION_DAYS", "365"))
    ALARM_RETENTION_DAYS = int(os.getenv("ALARM_RETENTION_DAYS", "90"))
    DIAGNOSTIC_RETENTION_DAYS = int(os.getenv("DIAGNOSTIC_RETENTION_DAYS", "30"))
    
    # Downsampling configuration
    DOWNSAMPLING_ENABLED = os.getenv("DOWNSAMPLING_ENABLED", "true").lower() == "true"
    DOWNSAMPLING_INTERVALS = {
        "1m": {"retention_days": 7, "source": "raw"},
        "5m": {"retention_days": 30, "source": "raw"},
        "1h": {"retention_days": 90, "source": "5m"},
        "1d": {"retention_days": 365, "source": "1h"},
    }
    
    # Cache configuration
    CACHE_TYPE = os.getenv("CACHE_TYPE", "redis")  # redis or memory
    CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "60"))  # seconds
    CACHE_HISTORICAL_TTL = int(os.getenv("CACHE_HISTORICAL_TTL", "300"))  # seconds
    CACHE_REALTIME_TTL = int(os.getenv("CACHE_REALTIME_TTL", "10"))  # seconds
    
    # Redis configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # Connection pool configuration
    POOL_MAX_CONNECTIONS = int(os.getenv("INFLUXDB_POOL_MAX_CONNECTIONS", "10"))
    
    # Flush configuration
    FLUSH_INTERVAL = int(os.getenv("INFLUXDB_FLUSH_INTERVAL", "10"))  # seconds
    
    # Data cleanup configuration
    CLEANUP_ENABLED = os.getenv("DATA_CLEANUP_ENABLED", "true").lower() == "true"
    CLEANUP_INTERVAL = int(os.getenv("DATA_CLEANUP_INTERVAL", "3600"))  # seconds (1 hour)
    
    # Hot/Cold data separation
    HOT_DATA_DAYS = int(os.getenv("HOT_DATA_DAYS", "7"))  # days
    COLD_DATA_DAYS = int(os.getenv("COLD_DATA_DAYS", "90"))  # days
    
    # Archival configuration
    ARCHIVAL_ENABLED = os.getenv("ARCHIVAL_ENABLED", "false").lower() == "true"
    ARCHIVAL_INTERVAL = int(os.getenv("ARCHIVAL_INTERVAL", "86400"))  # seconds (1 day)
    ARCHIVAL_THRESHOLD_DAYS = int(os.getenv("ARCHIVAL_THRESHOLD_DAYS", "90"))  # days
    
    # Performance monitoring
    MONITORING_ENABLED = os.getenv("PERFORMANCE_MONITORING_ENABLED", "true").lower() == "true"
    MONITORING_INTERVAL = int(os.getenv("MONITORING_INTERVAL", "60"))  # seconds
    
    # Alert thresholds
    ALERT_STORAGE_USAGE_PERCENT = float(os.getenv("ALERT_STORAGE_USAGE_PERCENT", "80"))
    ALERT_WRITE_LATENCY_MS = float(os.getenv("ALERT_WRITE_LATENCY_MS", "1000"))
    ALERT_QUERY_LATENCY_MS = float(os.getenv("ALERT_QUERY_LATENCY_MS", "5000"))
    ALERT_CACHE_HIT_RATE_PERCENT = float(os.getenv("ALERT_CACHE_HIT_RATE_PERCENT", "50"))
    
    @classmethod
    def get_cache_config(cls) -> Dict[str, Any]:
        """Get cache configuration"""
        return {
            "cache_type": cls.CACHE_TYPE,
            "config": {
                "redis": {
                    "host": cls.REDIS_HOST,
                    "port": cls.REDIS_PORT,
                    "password": cls.REDIS_PASSWORD,
                    "db": cls.REDIS_DB,
                },
                "max_memory_size": 1000,
            },
            "default_ttl": cls.CACHE_DEFAULT_TTL,
        }
    
    @classmethod
    def get_retention_seconds(cls, retention_days: int) -> int:
        """Convert retention days to seconds"""
        return retention_days * 24 * 3600

