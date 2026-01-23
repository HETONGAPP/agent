"""
Query Cache
Caching mechanism for database query results
Supports Redis (preferred) and in-memory fallback
"""

import logging
import json
import hashlib
import time
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta, UTC
from collections import OrderedDict

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache only")


class QueryCache:
    """
    Query result cache with Redis and in-memory support
    Features:
    - TTL-based expiration
    - LRU eviction for in-memory cache
    - Cache statistics
    - Automatic cleanup
    """

    def __init__(
        self,
        cache_type: str = "redis",
        config: Optional[Dict[str, Any]] = None,
        default_ttl: int = 60,  # Default 60 seconds
    ):
        """
        Initialize query cache

        Args:
            cache_type: Cache type ('redis' or 'memory')
            config: Cache configuration
            default_ttl: Default TTL in seconds
        """
        self.cache_type = cache_type
        self.config = config or {}
        self.default_ttl = default_ttl

        # In-memory cache (LRU with max size)
        self._memory_cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_memory_size = self.config.get("max_memory_size", 1000)

        # Redis client
        self._redis_client = None
        if cache_type == "redis" and REDIS_AVAILABLE:
            self._init_redis()

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

    def _init_redis(self):
        """Initialize Redis client"""
        if not REDIS_AVAILABLE:
            logger.warning(
                "⚠ Redis Python library not installed. Install with: pip install redis. "
                "Falling back to memory cache."
            )
            self._redis_client = None
            self.cache_type = "memory"
            return
        
        try:
            redis_config = self.config.get("redis", {})
            redis_host = redis_config.get("host", "localhost")
            # Ensure port is an integer
            redis_port = redis_config.get("port", 6379)
            if isinstance(redis_port, str):
                try:
                    redis_port = int(redis_port)
                except ValueError:
                    logger.warning(f"Invalid Redis port '{redis_port}', using default 6379")
                    redis_port = 6379
            redis_password = redis_config.get("password")
            # Ensure db is an integer
            redis_db = redis_config.get("db", 0)
            if isinstance(redis_db, str):
                try:
                    redis_db = int(redis_db)
                except ValueError:
                    logger.warning(f"Invalid Redis db '{redis_db}', using default 0")
                    redis_db = 0
            
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # Test connection
            self._redis_client.ping()
            logger.info(f"✓ Redis cache initialized (host={redis_host}, port={redis_port}, db={redis_db})")
        except redis.ConnectionError as e:
            logger.warning(
                f"⚠ Failed to connect to Redis at {redis_config.get('host', 'localhost')}:{redis_config.get('port', 6379)}: {e}. "
                f"Please check if Redis is running and accessible. Falling back to memory cache."
            )
            self._redis_client = None
            self.cache_type = "memory"
        except redis.AuthenticationError as e:
            logger.warning(
                f"⚠ Redis authentication failed: {e}. "
                f"Please check REDIS_PASSWORD environment variable. "
                f"Falling back to memory cache."
            )
            self._redis_client = None
            self.cache_type = "memory"
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages
            if "invalid username-password pair" in error_msg.lower() or "user is disabled" in error_msg.lower():
                logger.warning(
                    f"⚠ Redis authentication failed: {error_msg}. "
                    f"Please check REDIS_PASSWORD environment variable matches Redis server configuration. "
                    f"Falling back to memory cache."
                )
            elif "Connection refused" in error_msg or "Name or service not known" in error_msg:
                logger.warning(
                    f"⚠ Cannot connect to Redis at {redis_config.get('host', 'localhost')}:{redis_config.get('port', 6379)}: {error_msg}. "
                    f"Please check if Redis service is running. Falling back to memory cache."
                )
            else:
                logger.warning(
                    f"⚠ Failed to initialize Redis cache: {error_msg}. "
                    f"Falling back to memory cache."
                )
            self._redis_client = None
            self.cache_type = "memory"

    def _generate_key(self, query_type: str, params: Dict[str, Any]) -> str:
        """
        Generate cache key from query type and parameters

        Args:
            query_type: Type of query (e.g., 'alarms', 'devices', 'stats')
            params: Query parameters

        Returns:
            Cache key string
        """
        # Sort params for consistent key generation
        sorted_params = json.dumps(params, sort_keys=True)
        key_string = f"{query_type}:{sorted_params}"
        
        # Use SHA256 for shorter keys
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        return f"query_cache:{query_type}:{key_hash}"

    def get(
        self,
        query_type: str,
        params: Dict[str, Any],
    ) -> Optional[Any]:
        """
        Get cached query result

        Args:
            query_type: Type of query
            params: Query parameters

        Returns:
            Cached result or None
        """
        cache_key = self._generate_key(query_type, params)

        try:
            if self.cache_type == "redis" and self._redis_client:
                cached = self._redis_client.get(cache_key)
                if cached:
                    self._stats["hits"] += 1
                    return json.loads(cached)
                else:
                    self._stats["misses"] += 1
            else:
                # Memory cache
                if cache_key in self._memory_cache:
                    data, expiry = self._memory_cache[cache_key]
                    if expiry is None or time.time() < expiry:
                        # Move to end (LRU)
                        self._memory_cache.move_to_end(cache_key)
                        self._stats["hits"] += 1
                        return data
                    else:
                        # Expired, remove it
                        del self._memory_cache[cache_key]
                        self._stats["misses"] += 1
                else:
                    self._stats["misses"] += 1
        except Exception as e:
            logger.warning(f"Error getting from cache: {e}")
            self._stats["misses"] += 1

        return None

    def set(
        self,
        query_type: str,
        params: Dict[str, Any],
        data: Any,
        ttl: Optional[int] = None,
    ):
        """
        Cache query result

        Args:
            query_type: Type of query
            params: Query parameters
            data: Data to cache
            ttl: Time to live in seconds (default: self.default_ttl)
        """
        cache_key = self._generate_key(query_type, params)
        ttl = ttl or self.default_ttl

        try:
            if self.cache_type == "redis" and self._redis_client:
                self._redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(data, default=str),
                )
                self._stats["sets"] += 1
            else:
                # Memory cache with LRU eviction
                expiry = time.time() + ttl if ttl > 0 else None

                # Evict if cache is full
                if len(self._memory_cache) >= self._max_memory_size:
                    # Remove oldest entry (LRU)
                    self._memory_cache.popitem(last=False)
                    self._stats["evictions"] += 1

                self._memory_cache[cache_key] = (data, expiry)
                # Move to end (most recently used)
                self._memory_cache.move_to_end(cache_key)
                self._stats["sets"] += 1
        except Exception as e:
            logger.warning(f"Error setting cache: {e}")

    def invalidate(self, query_type: Optional[str] = None, pattern: Optional[str] = None):
        """
        Invalidate cache entries

        Args:
            query_type: Invalidate all entries of this type (if provided)
            pattern: Invalidate entries matching pattern (if provided)
        """
        try:
            if self.cache_type == "redis" and self._redis_client:
                if query_type:
                    # Delete all keys for this query type
                    pattern_key = f"query_cache:{query_type}:*"
                    keys = self._redis_client.keys(pattern_key)
                    if keys:
                        self._redis_client.delete(*keys)
                elif pattern:
                    keys = self._redis_client.keys(f"query_cache:*{pattern}*")
                    if keys:
                        self._redis_client.delete(*keys)
                else:
                    # Clear all query cache
                    keys = self._redis_client.keys("query_cache:*")
                    if keys:
                        self._redis_client.delete(*keys)
            else:
                # Memory cache
                keys_to_remove = []
                for key in self._memory_cache.keys():
                    if query_type and key.startswith(f"query_cache:{query_type}:"):
                        keys_to_remove.append(key)
                    elif pattern and pattern in key:
                        keys_to_remove.append(key)
                    elif not query_type and not pattern:
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    del self._memory_cache[key]
        except Exception as e:
            logger.warning(f"Error invalidating cache: {e}")

    def clear(self):
        """Clear all cache"""
        try:
            if self.cache_type == "redis" and self._redis_client:
                keys = self._redis_client.keys("query_cache:*")
                if keys:
                    self._redis_client.delete(*keys)
            else:
                self._memory_cache.clear()
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests * 100
            if total_requests > 0
            else 0
        )

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "evictions": self._stats["evictions"],
            "hit_rate": f"{hit_rate:.2f}%",
            "cache_type": self.cache_type,
            "memory_size": len(self._memory_cache) if self.cache_type == "memory" else None,
        }

    def cached(
        self,
        query_type: str,
        ttl: Optional[int] = None,
    ):
        """
        Decorator for caching function results

        Usage:
            @cache.cached("alarms", ttl=60)
            async def get_alarms(params):
                ...
        """
        def decorator(func: Callable):
            async def wrapper(*args, **kwargs):
                # Generate params from function arguments
                params = {}
                if args:
                    params["args"] = args
                if kwargs:
                    params.update(kwargs)

                # Try to get from cache
                cached_result = self.get(query_type, params)
                if cached_result is not None:
                    return cached_result

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                self.set(query_type, params, result, ttl)

                return result
            return wrapper
        return decorator

