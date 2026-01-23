"""
Rate Limiter
Provides rate limiting for API endpoints
"""

import time
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import HTTPException, Request, Depends


class RateLimiter:
    """
    Simple in-memory rate limiter
    For production, consider using Redis-based rate limiting
    """

    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests per minute per client
        """
        self.requests_per_minute = requests_per_minute
        self._requests: Dict[str, list] = defaultdict(list)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request"""
        # Try to get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # If there's an API key, use it as identifier (more accurate)
        auth_header = request.headers.get("Authorization") or request.headers.get("X-API-Key")
        if auth_header:
            # Use a hash of the auth header as identifier
            import hashlib
            client_id = hashlib.md5(auth_header.encode()).hexdigest()
            return f"auth_{client_id}"
        
        return f"ip_{client_ip}"

    def is_allowed(self, request: Request) -> Tuple[bool, int]:
        """
        Check if request is allowed

        Args:
            request: FastAPI request

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        client_id = self._get_client_id(request)
        now = time.time()
        one_minute_ago = now - 60

        # Clean old requests
        self._requests[client_id] = [
            req_time for req_time in self._requests[client_id]
            if req_time > one_minute_ago
        ]

        # Check limit
        if len(self._requests[client_id]) >= self.requests_per_minute:
            return False, 0

        # Record request
        self._requests[client_id].append(now)

        remaining = self.requests_per_minute - len(self._requests[client_id])
        return True, remaining

    def check_rate_limit(self, request: Request):
        """
        Check rate limit and raise exception if exceeded

        Args:
            request: FastAPI request

        Raises:
            HTTPException: If rate limit exceeded
        """
        allowed, remaining = self.is_allowed(request)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                }
            )


# Global rate limiter instance
# Increased limit for frontend with multiple pages and real-time updates
_default_rate_limiter = RateLimiter(requests_per_minute=180)


def get_rate_limiter() -> RateLimiter:
    """Get default rate limiter"""
    return _default_rate_limiter


def rate_limit_dependency(request: Request, rate_limiter: RateLimiter = Depends(get_rate_limiter)):
    """FastAPI dependency for rate limiting"""
    rate_limiter.check_rate_limit(request)
    return True

