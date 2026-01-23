"""
Batch Query Optimization
Optimizes database queries by batching and parallelizing
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, TypeVar, Awaitable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BatchQueryOptimizer:
    """
    Optimizes queries by batching and parallelizing
    """

    @staticmethod
    async def batch_query(
        queries: List[Callable[[], Awaitable[T]]],
        max_concurrent: int = 10,
    ) -> List[T]:
        """
        Execute multiple queries in parallel with concurrency limit

        Args:
            queries: List of async query functions
            max_concurrent: Maximum concurrent queries

        Returns:
            List of query results in the same order as queries
        """
        if not queries:
            return []

        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_with_limit(query_func: Callable[[], Awaitable[T]]) -> T:
            async with semaphore:
                return await query_func()

        # Execute all queries in parallel
        tasks = [execute_with_limit(query) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Query {i} failed: {result}", exc_info=True)
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    @staticmethod
    async def batch_query_sites(
        site_ids: List[str],
        query_func: Callable[[str], Awaitable[T]],
        max_concurrent: int = 10,
    ) -> Dict[str, T]:
        """
        Query multiple sites in parallel

        Args:
            site_ids: List of site IDs
            query_func: Async function that takes site_id and returns result
            max_concurrent: Maximum concurrent queries

        Returns:
            Dictionary mapping site_id to result
        """
        if not site_ids:
            return {}

        # Create query functions
        queries = [lambda sid=sid: query_func(sid) for sid in site_ids]

        # Execute in parallel
        results = await BatchQueryOptimizer.batch_query(queries, max_concurrent)

        # Map results to site IDs
        return {site_id: result for site_id, result in zip(site_ids, results) if result is not None}

    @staticmethod
    def merge_results(results: List[Dict[str, Any]], merge_key: str = "site_id") -> Dict[str, Any]:
        """
        Merge multiple query results

        Args:
            results: List of result dictionaries
            merge_key: Key to use for merging

        Returns:
            Merged result dictionary
        """
        merged = {}
        for result in results:
            if result and isinstance(result, dict):
                key = result.get(merge_key)
                if key:
                    merged[key] = result
        return merged


class IncrementalQuery:
    """
    Incremental query support - only query changed data
    """

    def __init__(self, last_query_time: Optional[datetime] = None):
        """
        Initialize incremental query

        Args:
            last_query_time: Timestamp of last query
        """
        self.last_query_time = last_query_time or datetime.utcnow()

    def get_time_range(self, lookback_seconds: int = 300) -> tuple[datetime, datetime]:
        """
        Get time range for incremental query

        Args:
            lookback_seconds: Lookback time in seconds

        Returns:
            Tuple of (start_time, end_time)
        """
        end_time = datetime.utcnow()
        start_time = self.last_query_time

        # Ensure start_time is not too far in the past
        min_start_time = end_time - timedelta(seconds=lookback_seconds)
        if start_time < min_start_time:
            start_time = min_start_time

        return start_time, end_time

    def update_last_query_time(self, query_time: Optional[datetime] = None):
        """
        Update last query time

        Args:
            query_time: Query time (defaults to now)
        """
        self.last_query_time = query_time or datetime.utcnow()


# Helper function for incremental alarm queries
async def get_alarms_since(
    site_id: Optional[str],
    since: datetime,
    container_manager: Optional[Any] = None,
    influx_client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Get alarms since a specific timestamp (incremental query)

    Args:
        site_id: Site ID (optional)
        since: Timestamp to query from
        container_manager: Site container manager
        influx_client: InfluxDB client

    Returns:
        List of alarms
    """
    from datetime import timedelta
    
    start_time = since.isoformat()
    end_time = (datetime.utcnow() + timedelta(days=1)).isoformat()

    if container_manager and site_id:
        # Use site container
        container = container_manager.get_container(site_id, auto_create=False)
        if container:
            return container.query_alarms(start_time=start_time, end_time=end_time, limit=10000)
    elif influx_client:
        # Use legacy mode
        return influx_client.query_alarms(start_time=start_time, end_time=end_time, site_id=site_id, limit=10000)

    return []

