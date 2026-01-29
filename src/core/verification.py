"""
Email Verification Code Service
Generate, store, and verify email verification codes using Redis
"""

import logging
import secrets
import os
from typing import Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

# Verification code settings
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_EXPIRE_MINUTES = int(os.getenv("VERIFICATION_CODE_EXPIRE_MINUTES", "10"))  # 10 minutes default
VERIFICATION_CODE_RATE_LIMIT_MINUTES = int(os.getenv("VERIFICATION_CODE_RATE_LIMIT_MINUTES", "1"))  # 1 minute between requests


class VerificationCodeService:
    """Service for managing email verification codes"""
    
    def __init__(self, redis_client=None):
        """
        Initialize verification code service
        
        Args:
            redis_client: Redis client instance (optional, will try to create if not provided)
        """
        self.redis_client = redis_client
        if redis_client is None:
            self._init_redis_client()
    
    def _init_redis_client(self):
        """Initialize Redis client from environment"""
        try:
            import redis
            
            # Try to get Redis client from app state first
            try:
                from ...agent.dependencies import get_app_state
                app_state = get_app_state()
                # Check if there's a Redis client in app state (if available)
                # For now, create our own connection
            except ImportError:
                pass
            
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD", "")
            redis_db = int(os.getenv("REDIS_DB", "0"))
            
            if redis_password:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            else:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Verification code service initialized with Redis")
        except ImportError:
            logger.warning("Redis library not installed. Install with: pip install redis")
            self.redis_client = None
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for verification codes: {e}. Verification codes will not be persisted.")
            self.redis_client = None
    
    def generate_code(self) -> str:
        """
        Generate a random verification code
        
        Returns:
            6-digit verification code string
        """
        # Generate 6-digit code
        code = ''.join([str(secrets.randbelow(10)) for _ in range(VERIFICATION_CODE_LENGTH)])
        return code
    
    def store_code(self, email: str, code: str) -> bool:
        """
        Store verification code in Redis
        
        Args:
            email: Email address
            code: Verification code
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot store verification code")
            return False
        
        try:
            key = f"verification_code:{email}"
            # Store code with expiration
            self.redis_client.setex(
                key,
                VERIFICATION_CODE_EXPIRE_MINUTES * 60,
                code
            )
            logger.info(f"Verification code stored for {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to store verification code: {e}", exc_info=True)
            return False
    
    def verify_code(self, email: str, code: str, delete_after_verify: bool = True) -> bool:
        """
        Verify a verification code
        
        Args:
            email: Email address
            code: Verification code to verify
            delete_after_verify: If True, delete code after verification (default: True)
            
        Returns:
            True if code is valid, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot verify code")
            return False
        
        try:
            key = f"verification_code:{email}"
            stored_code = self.redis_client.get(key)
            
            if stored_code is None:
                logger.warning(f"No verification code found for {email} (key: {key})")
                return False
            
            # Normalize codes for comparison (strip whitespace, ensure string)
            stored_code = str(stored_code).strip()
            code = str(code).strip()
            
            logger.info(f"Verifying code for {email}: stored='{stored_code}' (len={len(stored_code)}), provided='{code}' (len={len(code)})")
            
            if stored_code != code:
                logger.warning(f"Invalid verification code for {email}: stored='{stored_code}' != provided='{code}'")
                return False
            
            # Code is valid
            if delete_after_verify:
                # Delete it (one-time use)
                self.redis_client.delete(key)
                logger.info(f"Verification code verified and deleted for {email}")
            else:
                # Mark as verified but keep code for registration
                verified_key = f"verification_verified:{email}"
                self.redis_client.setex(verified_key, VERIFICATION_CODE_EXPIRE_MINUTES * 60, "1")
                logger.info(f"Verification code verified for {email} (kept for registration). Code still in Redis: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to verify code: {e}", exc_info=True)
            return False
    
    def check_code_verified(self, email: str) -> bool:
        """
        Check if verification code has been verified (without deleting)
        
        Args:
            email: Email address
            
        Returns:
            True if code was verified, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            verified_key = f"verification_verified:{email}"
            exists = self.redis_client.exists(verified_key)
            return exists == 1
        except Exception as e:
            logger.error(f"Failed to check verification status: {e}", exc_info=True)
            return False
    
    def check_rate_limit(self, email: str) -> bool:
        """
        Check if email is rate limited (too many requests)
        
        Args:
            email: Email address
            
        Returns:
            True if rate limited, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            rate_limit_key = f"verification_rate_limit:{email}"
            exists = self.redis_client.exists(rate_limit_key)
            return exists == 1
        except Exception as e:
            logger.error(f"Failed to check rate limit: {e}", exc_info=True)
            return False
    
    def set_rate_limit(self, email: str):
        """
        Set rate limit for email (prevent too frequent requests)
        
        Args:
            email: Email address
        """
        if not self.redis_client:
            return
        
        try:
            rate_limit_key = f"verification_rate_limit:{email}"
            self.redis_client.setex(
                rate_limit_key,
                VERIFICATION_CODE_RATE_LIMIT_MINUTES * 60,
                "1"
            )
        except Exception as e:
            logger.error(f"Failed to set rate limit: {e}", exc_info=True)
    
    def delete_code(self, email: str):
        """
        Delete verification code for email
        
        Args:
            email: Email address
        """
        if not self.redis_client:
            return
        
        try:
            key = f"verification_code:{email}"
            self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete verification code: {e}", exc_info=True)


# Global instance
_verification_service: Optional[VerificationCodeService] = None


def get_verification_service(redis_client=None) -> VerificationCodeService:
    """Get or create verification code service instance"""
    global _verification_service
    if _verification_service is None:
        _verification_service = VerificationCodeService(redis_client)
    return _verification_service
