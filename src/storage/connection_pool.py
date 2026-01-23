"""
InfluxDB Connection Pool
Manages connection reuse and pooling for better performance
"""

import logging
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

try:
    from influxdb_client import InfluxDBClient as InfluxClient
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    InfluxClient = None


class InfluxDBConnectionPool:
    """
    Connection pool for InfluxDB clients
    Reuses connections to reduce overhead and improve performance
    """

    def __init__(self, max_connections: int = 5):
        """
        Initialize connection pool

        Args:
            max_connections: Maximum number of connections in pool
        """
        if not INFLUXDB_AVAILABLE:
            raise ImportError(
                "influxdb-client not installed, please run: pip install influxdb-client"
            )

        self.max_connections = max_connections
        self._pool: Dict[str, list] = {}  # Key: connection_key, Value: list of clients
        self._lock = threading.Lock()
        self._active_connections: Dict[str, int] = {}  # Track active connections per key
        self._connection_stats = {
            "created": 0,
            "reused": 0,
            "closed": 0,
        }

    def _generate_connection_key(self, url: str, token: str, org: str) -> str:
        """
        Generate unique key for connection parameters

        Args:
            url: InfluxDB URL
            token: Access token
            org: Organization name

        Returns:
            Connection key string
        """
        import hashlib
        key_string = f"{url}:{token[:8]}:{org}"  # Use first 8 chars of token for key
        return hashlib.md5(key_string.encode()).hexdigest()

    @contextmanager
    def get_client(self, url: str, token: str, org: str):
        """
        Get InfluxDB client from pool (context manager)

        Args:
            url: InfluxDB URL
            token: Access token
            org: Organization name

        Yields:
            InfluxDB client instance
        """
        connection_key = self._generate_connection_key(url, token, org)
        client = None

        try:
            with self._lock:
                # Try to get client from pool
                if connection_key in self._pool and self._pool[connection_key]:
                    client = self._pool[connection_key].pop()
                    self._connection_stats["reused"] += 1
                    logger.debug(
                        f"[ConnectionPool] Reusing InfluxDB connection (key: {connection_key[:8]})"
                    )
                else:
                    # Create new client
                    client = InfluxClient(url=url, token=token, org=org)
                    self._connection_stats["created"] += 1
                    logger.debug(
                        f"[ConnectionPool] Created new InfluxDB connection (key: {connection_key[:8]})"
                    )

                # Track active connections
                self._active_connections[connection_key] = (
                    self._active_connections.get(connection_key, 0) + 1
                )

            # Yield client
            yield client

        except Exception as e:
            logger.error(f"[ConnectionPool] Error with client: {e}", exc_info=True)
            # If error occurs, don't return to pool
            if client:
                try:
                    client.close()
                except Exception:
                    pass
                self._connection_stats["closed"] += 1
            raise
        finally:
            # Return client to pool
            if client:
                with self._lock:
                    self._active_connections[connection_key] = (
                        self._active_connections.get(connection_key, 1) - 1
                    )

                    # Check if pool for this key exists and has space
                    if connection_key not in self._pool:
                        self._pool[connection_key] = []

                    # Only return to pool if under max connections
                    pool_size = len(self._pool[connection_key])
                    if pool_size < self.max_connections:
                        # Verify client is still usable
                        try:
                            # Simple health check - try to ping
                            client.health()
                            self._pool[connection_key].append(client)
                            logger.debug(
                                f"[ConnectionPool] Returned client to pool (key: {connection_key[:8]}, "
                                f"pool_size: {len(self._pool[connection_key])})"
                            )
                        except Exception as e:
                            # Client is not healthy, close it
                            logger.warning(
                                f"[ConnectionPool] Client not healthy, closing: {e}"
                            )
                            try:
                                client.close()
                            except Exception:
                                pass
                            self._connection_stats["closed"] += 1
                    else:
                        # Pool is full, close the client
                        logger.debug(
                            f"[ConnectionPool] Pool full, closing client (key: {connection_key[:8]})"
                        )
                        try:
                            client.close()
                        except Exception:
                            pass
                        self._connection_stats["closed"] += 1

    def get_or_create_client(self, url: str, token: str, org: str) -> InfluxClient:
        """
        Get or create InfluxDB client (non-context manager version)
        Note: Client should be returned to pool manually or use get_client() context manager

        Args:
            url: InfluxDB URL
            token: Access token
            org: Organization name

        Returns:
            InfluxDB client instance
        """
        connection_key = self._generate_connection_key(url, token, org)

        with self._lock:
            # Try to get client from pool
            if connection_key in self._pool and self._pool[connection_key]:
                client = self._pool[connection_key].pop()
                self._connection_stats["reused"] += 1
                logger.debug(
                    f"[ConnectionPool] Reusing InfluxDB connection (key: {connection_key[:8]})"
                )
                return client

            # Create new client
            client = InfluxClient(url=url, token=token, org=org)
            self._connection_stats["created"] += 1
            logger.debug(
                f"[ConnectionPool] Created new InfluxDB connection (key: {connection_key[:8]})"
            )
            return client

    def return_client(self, client: InfluxClient, url: str, token: str, org: str):
        """
        Return client to pool

        Args:
            client: InfluxDB client instance
            url: InfluxDB URL (for connection key)
            token: Access token (for connection key)
            org: Organization name (for connection key)
        """
        connection_key = self._generate_connection_key(url, token, org)

        with self._lock:
            if connection_key not in self._pool:
                self._pool[connection_key] = []

            pool_size = len(self._pool[connection_key])
            if pool_size < self.max_connections:
                # Verify client is still usable
                try:
                    client.health()
                    self._pool[connection_key].append(client)
                    logger.debug(
                        f"[ConnectionPool] Returned client to pool (key: {connection_key[:8]}, "
                        f"pool_size: {len(self._pool[connection_key])})"
                    )
                except Exception as e:
                    logger.warning(f"[ConnectionPool] Client not healthy, closing: {e}")
                    try:
                        client.close()
                    except Exception:
                        pass
                    self._connection_stats["closed"] += 1
            else:
                logger.debug(
                    f"[ConnectionPool] Pool full, closing client (key: {connection_key[:8]})"
                )
                try:
                    client.close()
                except Exception:
                    pass
                self._connection_stats["closed"] += 1

    def close_all(self):
        """Close all connections in pool"""
        with self._lock:
            total_closed = 0
            for connection_key, clients in self._pool.items():
                for client in clients:
                    try:
                        client.close()
                        total_closed += 1
                    except Exception:
                        pass
                self._pool[connection_key] = []
            self._pool.clear()
            self._active_connections.clear()
            logger.info(f"[ConnectionPool] Closed {total_closed} pooled connections")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            total_pooled = sum(len(clients) for clients in self._pool.values())
            return {
                "max_connections": self.max_connections,
                "total_pooled": total_pooled,
                "active_connections": sum(self._active_connections.values()),
                "pool_keys": len(self._pool),
                "stats": self._connection_stats.copy(),
            }


# Global connection pool instance
_global_pool: Optional[InfluxDBConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool(max_connections: int = 5) -> InfluxDBConnectionPool:
    """
    Get or create global connection pool

    Args:
        max_connections: Maximum number of connections (only used on first call)

    Returns:
        Global InfluxDBConnectionPool instance
    """
    global _global_pool
    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                _global_pool = InfluxDBConnectionPool(max_connections=max_connections)
                logger.info(
                    f"[ConnectionPool] Initialized global connection pool (max_connections={max_connections})"
                )
    return _global_pool












