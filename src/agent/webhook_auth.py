"""
Webhook Authentication
Provides authentication for Grafana webhook endpoints
"""

import hmac
import hashlib
import logging
from typing import Optional
from fastapi import Request, HTTPException, Header

logger = logging.getLogger(__name__)


class WebhookAuth:
    """Webhook authentication handler"""

    @staticmethod
    def verify_signature(
        payload: bytes,
        signature: Optional[str],
        secret: Optional[str],
        algorithm: str = "sha256"
    ) -> bool:
        """
        Verify webhook signature

        Args:
            payload: Raw request payload
            signature: Signature from header (format: sha256=...)
            secret: Secret key for verification
            algorithm: Hash algorithm (sha256, sha1, etc.)

        Returns:
            True if signature is valid
        """
        if not secret:
            # If no secret configured, allow all requests (development mode)
            logger.warning("Webhook secret not configured, allowing all requests")
            return True

        if not signature:
            logger.warning("Webhook signature missing")
            return False

        # Extract hash from signature (format: sha256=...)
        if "=" in signature:
            sig_hash = signature.split("=", 1)[1]
        else:
            sig_hash = signature

        # Calculate expected signature
        if algorithm == "sha256":
            expected_hash = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha1":
            expected_hash = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha1
            ).hexdigest()
        else:
            logger.error(f"Unsupported algorithm: {algorithm}")
            return False

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_hash, sig_hash)

    @staticmethod
    async def verify_request(
        request: Request,
        secret: Optional[str] = None,
        header_name: str = "X-Grafana-Signature",
        algorithm: str = "sha256"
    ) -> bool:
        """
        Verify webhook request

        Args:
            request: FastAPI request object
            secret: Secret key (from environment or config)
            header_name: Header name containing signature
            algorithm: Hash algorithm

        Returns:
            True if request is authenticated
        """
        # Get signature from header
        signature = request.headers.get(header_name)

        # Read request body
        body = await request.body()

        # Verify signature
        return WebhookAuth.verify_signature(body, signature, secret, algorithm)


async def verify_webhook_auth(
    request: Request,
    x_grafana_signature: Optional[str] = Header(None, alias="X-Grafana-Signature"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> bool:
    """
    FastAPI dependency for webhook authentication
    Supports both signature-based and API key-based authentication

    Args:
        request: FastAPI request
        x_grafana_signature: Grafana signature header
        x_api_key: API key header

    Returns:
        True if authenticated

    Raises:
        HTTPException: If authentication fails
    """
    import os

    # Try API key authentication first
    api_key = os.getenv("WEBHOOK_API_KEY")
    if api_key:
        if x_api_key == api_key:
            return True
        if not x_api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required (X-API-Key header)"
            )
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Try signature-based authentication
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if webhook_secret:
        body = await request.body()
        if WebhookAuth.verify_signature(body, x_grafana_signature, webhook_secret):
            return True
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    # No authentication configured - allow in development
    logger.warning("No webhook authentication configured - allowing request (development mode)")
    return True












