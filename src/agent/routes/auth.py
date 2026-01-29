"""
Authentication routes
User registration, login, logout, and user info endpoints
"""

import logging
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ...core.database import get_db_session, UserModel
from ...core.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    generate_user_id,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from ...core.verification import (
    get_verification_service,
    VERIFICATION_CODE_EXPIRE_MINUTES,
    VERIFICATION_CODE_RATE_LIMIT_MINUTES,
)
from ...email.client import EmailClient
from ...agent.dependencies import get_app_state

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


# Pydantic models
class SendVerificationCodeRequest(BaseModel):
    """Send verification code request model"""
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    """Verify code request model"""
    email: EmailStr
    verification_code: str


class UserRegister(BaseModel):
    """User registration request model"""
    username: str
    email: EmailStr
    password: str
    verification_code: str  # Email verification code
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login request model"""
    username: str
    password: str


class UserResponse(BaseModel):
    """User response model"""
    user_id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenData(BaseModel):
    """Token data model"""
    user_id: Optional[str] = None
    username: Optional[str] = None


# Dependency to get current user from token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db_session),
) -> UserModel:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP bearer credentials
        db: Database session
        
    Returns:
        UserModel instance
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    return user


# Optional dependency - returns None if not authenticated
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db_session),
) -> Optional[UserModel]:
    """
    Get current user if authenticated, None otherwise
    
    Args:
        credentials: Optional HTTP bearer credentials
        db: Database session
        
    Returns:
        UserModel instance or None
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def register_auth_routes(app):
    """Register authentication routes"""
    router = APIRouter(prefix="/api/auth", tags=["authentication"])

    @router.post("/send-verification-code")
    async def send_verification_code(
        request: SendVerificationCodeRequest,
        db: Session = Depends(get_db_session),
    ):
        """
        Send email verification code
        
        Args:
            request: Email address to send verification code to
            db: Database session
            
        Returns:
            Success message
            
        Raises:
            HTTPException: If email already registered or rate limited
        """
        # Check if email already exists
        existing_email = db.query(UserModel).filter(UserModel.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Get verification service
        verification_service = get_verification_service()
        
        # Check if code already exists (user might be requesting again)
        existing_code_key = f"verification_code:{request.email}"
        existing_code = None
        if verification_service.redis_client:
            try:
                existing_code = verification_service.redis_client.get(existing_code_key)
            except Exception:
                pass
        
        # Check rate limit
        is_rate_limited = verification_service.check_rate_limit(request.email)
        is_dev = os.getenv("ENVIRONMENT", "").lower() == "development" or os.getenv("DEBUG", "").lower() == "true"
        
        if is_rate_limited:
            # In dev mode, if code exists, return it instead of error
            if is_dev and existing_code:
                logger.info(f"[DEV] Rate limited, but returning existing code for {request.email}")
                return {
                    "message": f"Rate limited. Please wait {VERIFICATION_CODE_RATE_LIMIT_MINUTES} minute(s). Using existing code (dev mode).",
                    "email": request.email,
                    "verification_code": existing_code,  # Return existing code in dev mode
                }
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {VERIFICATION_CODE_RATE_LIMIT_MINUTES} minute(s) before requesting another code",
            )
        
        # Generate verification code
        code = verification_service.generate_code()
        
        # Store code in Redis
        if not verification_service.store_code(request.email, code):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Verification service temporarily unavailable",
            )
        
        # Set rate limit
        verification_service.set_rate_limit(request.email)
        
        # Send email with verification code
        try:
            app_state = get_app_state()
            email_service = app_state.get("email_service")
            
            # Log verification code for debugging (always log in development)
            is_dev = os.getenv("ENVIRONMENT", "").lower() == "development" or os.getenv("DEBUG", "").lower() == "true"
            if is_dev:
                logger.info(f"[DEV] Verification code for {request.email}: {code}")
            
            if email_service and email_service.email_client:
                email_body_html = f"""
                <html>
                <body>
                    <h2>Email Verification Code</h2>
                    <p>Your verification code is: <strong style="font-size: 24px; color: #3B82F6;">{code}</strong></p>
                    <p>This code will expire in {VERIFICATION_CODE_EXPIRE_MINUTES} minutes.</p>
                    <p>If you did not request this code, please ignore this email.</p>
                </body>
                </html>
                """
                
                email_body_text = f"""
Email Verification Code

Your verification code is: {code}

This code will expire in {VERIFICATION_CODE_EXPIRE_MINUTES} minutes.

If you did not request this code, please ignore this email.
                """
                
                from_addr = email_service.from_address
                from_name = email_service.from_name
                from_address = f"{from_name} <{from_addr}>"
                
                logger.info(f"Attempting to send verification code email to {request.email} from {from_address}")
                
                # Send email synchronously (verification codes should be sent immediately)
                success = email_service.email_client.send(
                    from_address=from_address,
                    to_addresses=[request.email],
                    subject="Email Verification Code",
                    body_text=email_body_text,
                    body_html=email_body_html,
                )
                
                if not success:
                    logger.error(f"Failed to send verification code email to {request.email}")
                    # In development, still return success with code in response
                    if is_dev:
                        logger.warning(f"[DEV] Email sending failed, but returning code in development mode")
                        return {
                            "message": "Verification code sent successfully (dev mode - check logs)",
                            "email": request.email,
                            "verification_code": code,  # Only in dev mode
                        }
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to send verification code email. Please check server logs.",
                    )
                
                logger.info(f"✓ Verification code email sent successfully to {request.email}")
            else:
                # Email service not configured
                logger.warning(f"Email service not configured or not initialized")
                logger.warning(f"Verification code for {request.email}: {code}")
                
                # In development, return code in response
                if is_dev:
                    logger.info(f"[DEV] Email service not available, returning code in response")
                    return {
                        "message": "Verification code generated (dev mode - email service not configured)",
                        "email": request.email,
                        "verification_code": code,  # Only in dev mode
                    }
                
                # In production, fail
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Email service not configured. Please contact administrator.",
                )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error sending verification code email: {e}", exc_info=True)
            # Delete stored code if email sending failed
            verification_service.delete_code(request.email)
            
            # In development, still return code
            is_dev = os.getenv("ENVIRONMENT", "").lower() == "development" or os.getenv("DEBUG", "").lower() == "true"
            if is_dev:
                logger.warning(f"[DEV] Email error occurred, but returning code in development mode")
                return {
                    "message": f"Verification code generated (dev mode - email error: {str(e)})",
                    "email": request.email,
                    "verification_code": code,  # Only in dev mode
                }
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification code email: {str(e)}",
            )
        
        return {
            "message": "Verification code sent",
            "email": request.email,
        }

    @router.post("/verify-code")
    async def verify_code(
        request: VerifyCodeRequest,
        db: Session = Depends(get_db_session),
    ):
        """
        Verify email verification code (without registering)
        
        Args:
            request: Email and verification code
            db: Database session
            
        Returns:
            Success message if code is valid
            
        Raises:
            HTTPException: If code is invalid or expired
        """
        # Check if email already exists
        existing_email = db.query(UserModel).filter(UserModel.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Verify code (don't delete yet, will be deleted during registration)
        verification_service = get_verification_service()
        
        # Normalize verification code (remove any whitespace, ensure it's a string)
        verification_code = str(request.verification_code).strip()
        
        logger.info(f"[STEP 1] Verifying code for {request.email}: code='{verification_code}' (len={len(verification_code)})")
        
        # Check if code exists in Redis first
        if verification_service.redis_client:
            key = f"verification_code:{request.email}"
            stored_code = verification_service.redis_client.get(key)
            logger.info(f"[STEP 1] Stored code in Redis for {request.email}: '{stored_code}'")
        
        if not verification_service.verify_code(request.email, verification_code, delete_after_verify=False):
            logger.warning(f"[STEP 1] Verification failed for {request.email} with code '{verification_code}'")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code. Please check the code and try again.",
            )
        
        logger.info(f"[STEP 1] Verification successful for {request.email}")
        
        # Return response in format expected by frontend ApiResponse
        return {
            "status": "success",
            "data": {
                "message": "Verification code verified successfully",
                "email": request.email,
                "verified": True,
            }
        }

    @router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
    async def register(
        user_data: UserRegister,
        db: Session = Depends(get_db_session),
    ):
        """
        Register a new user
        
        Args:
            user_data: User registration data
            db: Database session
            
        Returns:
            Token response with user info
            
        Raises:
            HTTPException: If username or email already exists
        """
        # Check if username already exists
        existing_user = db.query(UserModel).filter(UserModel.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        
        # Check if email already exists
        existing_email = db.query(UserModel).filter(UserModel.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Verify email verification code
        verification_service = get_verification_service()
        
        # Normalize verification code
        verification_code = str(user_data.verification_code).strip()
        
        logger.info(f"[REGISTER] Registering user {user_data.username} with email {user_data.email}, verifying code '{verification_code}'")
        
        # Check if code exists in Redis first
        if verification_service.redis_client:
            key = f"verification_code:{user_data.email}"
            stored_code = verification_service.redis_client.get(key)
            verified_key = f"verification_verified:{user_data.email}"
            verified_exists = verification_service.redis_client.exists(verified_key)
            logger.info(f"[REGISTER] Stored code in Redis: '{stored_code}', Verified flag exists: {verified_exists == 1}")
        
        # First check if code was already verified in step 1
        is_verified = verification_service.check_code_verified(user_data.email)
        logger.info(f"[REGISTER] Check verified flag for {user_data.email}: {is_verified}")
        
        if is_verified:
            logger.info(f"[REGISTER] Code already verified for {user_data.email}, proceeding with registration")
            # Clean up: delete the verification code and verified flag
            if verification_service.redis_client:
                verification_service.redis_client.delete(f"verification_code:{user_data.email}")
                verification_service.redis_client.delete(f"verification_verified:{user_data.email}")
        else:
            # Verify code (this will delete it)
            logger.info(f"[REGISTER] Code not verified yet, verifying now with code '{verification_code}'...")
            # Check if code still exists in Redis
            if verification_service.redis_client:
                key = f"verification_code:{user_data.email}"
                stored_code = verification_service.redis_client.get(key)
                logger.info(f"[REGISTER] Code in Redis before verification: '{stored_code}'")
            
            if not verification_service.verify_code(user_data.email, verification_code, delete_after_verify=True):
                logger.warning(f"[REGISTER] Verification failed for {user_data.email} with code '{verification_code}'")
                # Check what's in Redis after failed verification
                if verification_service.redis_client:
                    key = f"verification_code:{user_data.email}"
                    stored_code = verification_service.redis_client.get(key)
                    logger.warning(f"[REGISTER] Code in Redis after failed verification: '{stored_code}'")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification code. Please verify your email again.",
                )
            logger.info(f"[REGISTER] Code verified successfully for {user_data.email}")
        
        # Create new user
        user_id = generate_user_id()
        hashed_password = get_password_hash(user_data.password)
        
        new_user = UserModel(
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True,
            is_superuser=False,
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"New user registered: {user_data.username} ({user_id})")
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user_id, "username": user_data.username}
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                user_id=new_user.user_id,
                username=new_user.username,
                email=new_user.email,
                full_name=new_user.full_name,
                is_active=new_user.is_active,
                is_superuser=new_user.is_superuser,
                created_at=new_user.created_at,
                last_login=new_user.last_login,
            ),
        )

    @router.post("/login", response_model=TokenResponse)
    async def login(
        login_data: UserLogin,
        db: Session = Depends(get_db_session),
    ):
        """
        Login user and return access token
        
        Args:
            login_data: Login credentials
            db: Database session
            
        Returns:
            Token response with user info
            
        Raises:
            HTTPException: If credentials are invalid
        """
        # Find user by username or email
        # Check if input looks like an email (contains @)
        login_identifier = login_data.username.strip()
        is_email = '@' in login_identifier
        
        if is_email:
            # Try to find by email first
            user = db.query(UserModel).filter(UserModel.email == login_identifier).first()
            if not user:
                # If not found by email, try username (user might have email as username)
                user = db.query(UserModel).filter(UserModel.username == login_identifier).first()
        else:
            # Try to find by username first
            user = db.query(UserModel).filter(UserModel.username == login_identifier).first()
            if not user:
                # If not found by username, try email (user might have username that looks like email)
                user = db.query(UserModel).filter(UserModel.email == login_identifier).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"User logged in: {user.username} ({user.user_id})")
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user.user_id, "username": user.username}
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                last_login=user.last_login,
            ),
        )

    @router.post("/logout")
    async def logout(
        current_user: UserModel = Depends(get_current_user),
    ):
        """
        Logout user (client should discard token)
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            Success message
        """
        logger.info(f"User logged out: {current_user.username} ({current_user.user_id})")
        return {"message": "Successfully logged out"}

    @router.get("/me", response_model=UserResponse)
    async def get_current_user_info(
        current_user: UserModel = Depends(get_current_user),
    ):
        """
        Get current user information
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            User information
        """
        return UserResponse(
            user_id=current_user.user_id,
            username=current_user.username,
            email=current_user.email,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            is_superuser=current_user.is_superuser,
            created_at=current_user.created_at,
            last_login=current_user.last_login,
        )

    app.include_router(router)
