"""
Diagnostic Cache
Flexible caching mechanism for diagnostic reports with enhanced features
Supports Redis and in-memory cache with improved strategies
"""

import logging
import json
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, UTC
from collections import defaultdict

logger = logging.getLogger(__name__)


class DiagnosticCache:
    """
    Enhanced diagnostic cache with improved strategies
    Supports Redis (preferred) and in-memory fallback
    Features:
    - Risk-level based TTL
    - Cache statistics
    - Automatic cache cleanup
    - Cache warming support
    """

    def __init__(self, cache_type: str = "redis", config: Optional[Dict[str, Any]] = None):
        """
        Initialize cache

        Args:
            cache_type: Cache type ('redis' or 'memory')
            config: Cache configuration
        """
        self.cache_type = cache_type
        self.config = config or {}
        self._cache = None
        self._redis_client = None

        # Enhanced configuration
        self.default_ttl = self.config.get("default_ttl", 3600)  # 1 hour default
        self.risk_level_ttl = self.config.get("risk_level_ttl", {
            "HIGH": 7200,  # 2 hours for high risk
            "MEDIUM": 3600,  # 1 hour for medium risk
            "LOW": 1800,  # 30 minutes for low risk
        })
        self.max_cache_size = self.config.get("max_cache_size", 10000)  # Max entries
        self.enable_statistics = self.config.get("enable_statistics", True)
        self.cleanup_interval = self.config.get("cleanup_interval", 3600)  # 1 hour

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "by_risk_level": defaultdict(int),
        }
        self._last_cleanup = datetime.now(UTC)

        if cache_type == "redis":
            self._init_redis()
        elif cache_type == "memory":
            self._init_memory()
        else:
            logger.warning(f"Unknown cache type: {cache_type}, using memory cache")
            self._init_memory()

    def _init_redis(self):
        """Initialize Redis cache"""
        try:
            import redis

            redis_config = self.config.get("redis", {})
            self._redis_client = redis.Redis(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                password=redis_config.get("password"),
                db=redis_config.get("db", 0),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self._redis_client.ping()
            logger.info("Redis cache initialized with enhanced features")
        except ImportError:
            logger.warning("Redis not available, falling back to memory cache")
            self._init_memory()
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, falling back to memory cache")
            self._init_memory()

    def _init_memory(self):
        """Initialize in-memory cache with enhanced features"""
        self._cache = {}
        logger.info("Memory cache initialized with enhanced features")

    def _generate_key(self, alarm_id: str, context: Dict[str, Any]) -> str:
        """
        Generate cache key from alarm ID and context
        Enhanced with better hashing

        Args:
            alarm_id: Alarm ID
            context: Context dictionary

        Returns:
            Cache key string
        """
        # Create hash from context for consistent key generation
        # Include only relevant fields for better cache hits
        context_str = json.dumps(context, sort_keys=True, default=str)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]
        return f"diagnostic:{alarm_id}:{context_hash}"

    def _get_ttl_for_risk_level(self, risk_level: Optional[str] = None) -> int:
        """
        Get TTL based on risk level

        Args:
            risk_level: Risk level string (HIGH, MEDIUM, LOW)

        Returns:
            TTL in seconds
        """
        if risk_level and risk_level.upper() in self.risk_level_ttl:
            return self.risk_level_ttl[risk_level.upper()]
        return self.default_ttl

    async def get(self, alarm_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached diagnostic report

        Args:
            alarm_id: Alarm ID
            context: Context dictionary

        Returns:
            Cached diagnostic report dict or None
        """
        key = self._generate_key(alarm_id, context)

        try:
            if self.cache_type == "redis" and self._redis_client:
                cached = self._redis_client.get(key)
                if cached:
                    if self.enable_statistics:
                        self._stats["hits"] += 1
                    result = json.loads(cached)
                    # Track by risk level
                    if self.enable_statistics and "risk_level" in result:
                        self._stats["by_risk_level"][result.get("risk_level", "UNKNOWN")] += 1
                    return result
                else:
                    if self.enable_statistics:
                        self._stats["misses"] += 1
            else:
                # Memory cache
                if key in self._cache:
                    cached_data, expiry = self._cache[key]
                    if expiry is None or datetime.now(UTC) < expiry:
                        if self.enable_statistics:
                            self._stats["hits"] += 1
                        result = cached_data
                        # Track by risk level
                        if self.enable_statistics and "risk_level" in result:
                            self._stats["by_risk_level"][result.get("risk_level", "UNKNOWN")] += 1
                        return result
                    else:
                        # Expired, remove it
                        del self._cache[key]
                        if self.enable_statistics:
                            self._stats["misses"] += 1
                else:
                    if self.enable_statistics:
                        self._stats["misses"] += 1

            # Periodic cleanup for memory cache
            if self.cache_type == "memory":
                self._maybe_cleanup()

        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            if self.enable_statistics:
                self._stats["misses"] += 1

        return None

    async def set(
        self,
        alarm_id: str,
        context: Dict[str, Any],
        diagnostic_report: Dict[str, Any],
        ttl: Optional[int] = None,
    ):
        """
        Cache diagnostic report with risk-level based TTL

        Args:
            alarm_id: Alarm ID
            context: Context dictionary
            diagnostic_report: Diagnostic report dict
            ttl: Time to live in seconds (None for auto based on risk level)
        """
        key = self._generate_key(alarm_id, context)

        # Auto-determine TTL from risk level if not provided
        if ttl is None:
            risk_level = diagnostic_report.get("risk_level")
            ttl = self._get_ttl_for_risk_level(risk_level)

        try:
            if self.cache_type == "redis" and self._redis_client:
                # Check cache size before adding
                if self.max_cache_size > 0:
                    # Get approximate size (Redis doesn't have direct size limit, but we can track)
                    # For simplicity, we'll just set with TTL
                    pass

                self._redis_client.setex(key, ttl, json.dumps(diagnostic_report))
                if self.enable_statistics:
                    self._stats["sets"] += 1
            else:
                # Memory cache
                # Check cache size and evict if needed
                if self.max_cache_size > 0 and len(self._cache) >= self.max_cache_size:
                    self._evict_oldest()
                    if self.enable_statistics:
                        self._stats["evictions"] += 1

                expiry = None
                if ttl:
                    expiry = datetime.now(UTC) + timedelta(seconds=ttl)
                self._cache[key] = (diagnostic_report, expiry)
                if self.enable_statistics:
                    self._stats["sets"] += 1

        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    def _evict_oldest(self, count: int = 1):
        """Evict oldest entries from memory cache"""
        if not self._cache:
            return

        # Sort by expiry time (None = no expiry, treat as newest)
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1][1] if x[1][1] is not None else datetime.max.replace(tzinfo=UTC),
        )

        # Remove oldest entries
        for i in range(min(count, len(sorted_items))):
            key, _ = sorted_items[i]
            del self._cache[key]

    def _maybe_cleanup(self):
        """Periodically cleanup expired entries"""
        now = datetime.now(UTC)
        if (now - self._last_cleanup).total_seconds() < self.cleanup_interval:
            return

        if self.cache_type == "memory" and self._cache:
            expired_keys = [
                key
                for key, (_, expiry) in self._cache.items()
                if expiry is not None and now >= expiry
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        self._last_cleanup = now

    async def delete(self, alarm_id: str, context: Dict[str, Any]):
        """
        Delete cached diagnostic report

        Args:
            alarm_id: Alarm ID
            context: Context dictionary
        """
        key = self._generate_key(alarm_id, context)

        try:
            if self.cache_type == "redis" and self._redis_client:
                self._redis_client.delete(key)
            else:
                # Memory cache
                if key in self._cache:
                    del self._cache[key]
            if self.enable_statistics:
                self._stats["deletes"] += 1
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")

    async def clear(self):
        """Clear all cached diagnostic reports"""
        try:
            if self.cache_type == "redis" and self._redis_client:
                # Delete all keys matching pattern
                keys = self._redis_client.keys("diagnostic:*")
                if keys:
                    self._redis_client.delete(*keys)
            else:
                # Memory cache
                self._cache.clear()
            logger.info("Cache cleared")
            # Reset statistics
            self._stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "evictions": 0,
                "by_risk_level": defaultdict(int),
            }
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        if not self.enable_statistics:
            return {"enabled": False}

        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        stats = {
            "enabled": True,
            "cache_type": self.cache_type,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "evictions": self._stats["evictions"],
            "hit_rate": round(hit_rate, 2),
            "total_requests": total_requests,
            "by_risk_level": dict(self._stats["by_risk_level"]),
        }

        if self.cache_type == "memory":
            stats["cache_size"] = len(self._cache)
            stats["max_cache_size"] = self.max_cache_size

        return stats

    async def warm_cache(
        self, diagnostics: List[Dict[str, Any]], ttl: Optional[int] = None
    ):
        """
        Warm cache with pre-computed diagnostics

        Args:
            diagnostics: List of diagnostic dictionaries with alarm_id and context
            ttl: Optional TTL for all entries
        """
        logger.info(f"Warming cache with {len(diagnostics)} diagnostics")
        for diagnostic in diagnostics:
            alarm_id = diagnostic.get("alarm_id")
            context = diagnostic.get("context", {})
            diagnostic_report = diagnostic.get("diagnostic_report", diagnostic)

            if alarm_id:
                await self.set(alarm_id, context, diagnostic_report, ttl=ttl)
        logger.info("Cache warming completed")
