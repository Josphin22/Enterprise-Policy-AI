import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthTokenResponse,
)
from app.core.security import hash_password, verify_password, create_access_token
from app.core.auth import get_current_user
from app.services.audit_service import log_audit_event

logger = logging.getLogger("enterprise_rag.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Register a new user account with default 'USER' privileges.
    Prevents self-escalation to ADMIN role.
    """
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    client_ip = request.client.host if request.client else None

    user = User(
        email=req.email,
        username=req.username,
        hashed_password=hash_password(req.password),
        role="USER",  # Strictly enforced default role
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        action="USER_REGISTER",
        user_id=user.id,
        user_email=user.email,
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email, "role": user.role},
        ip_address=client_ip,
    )

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return AuthTokenResponse(access_token=token, token_type="bearer", user=user)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    req: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate user credentials and return a signed JWT Bearer token.
    """
    client_ip = request.client.host if request.client else None
    email_clean = req.email.strip().lower()

    # 1. Login throttling / Lockout check (Phase 11)
    from app.services.auth_throttle_service import auth_throttle

    ip_key = f"ip:{client_ip}" if client_ip else "ip:unknown"
    email_key = f"email:{email_clean}"

    ip_locked, ip_remain = auth_throttle.is_locked_out(ip_key)
    email_locked, email_remain = auth_throttle.is_locked_out(email_key)

    if ip_locked or email_locked:
        wait_seconds = max(ip_remain, email_remain)
        log_audit_event(
            db=db,
            action="LOGIN_THROTTLED",
            user_email=email_clean,
            resource_type="auth",
            metadata={"reason": "too_many_failed_attempts", "retry_after_seconds": wait_seconds},
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {wait_seconds} seconds.",
            headers={"Retry-After": str(wait_seconds)},
        )

    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not user.hashed_password:
        auth_throttle.record_failed_attempt(ip_key)
        auth_throttle.record_failed_attempt(email_key)
        log_audit_event(
            db=db,
            action="LOGIN_FAILURE",
            user_email=email_clean,
            resource_type="auth",
            metadata={"reason": "user_not_found_or_no_password"},
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(req.password, user.hashed_password):
        auth_throttle.record_failed_attempt(ip_key)
        auth_throttle.record_failed_attempt(email_key)
        log_audit_event(
            db=db,
            action="LOGIN_FAILURE",
            user_id=user.id,
            user_email=user.email,
            resource_type="auth",
            metadata={"reason": "bad_password"},
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_audit_event(
            db=db,
            action="LOGIN_BLOCKED_INACTIVE",
            user_id=user.id,
            user_email=user.email,
            resource_type="auth",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact an administrator.",
        )

    # Reset failure throttle on successful authentication
    auth_throttle.reset(ip_key)
    auth_throttle.reset(email_key)

    log_audit_event(
        db=db,
        action="USER_LOGIN",
        user_id=user.id,
        user_email=user.email,
        resource_type="auth",
        metadata={"role": user.role},
        ip_address=client_ip,
    )

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return AuthTokenResponse(access_token=token, token_type="bearer", user=user)


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Log out currently authenticated user and record audit trail (Phase 11).
    """
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="USER_LOGOUT",
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="auth",
        ip_address=client_ip,
    )
    return {"success": True, "message": "Successfully logged out."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get profile information of the currently authenticated user.
    """
    return current_user

