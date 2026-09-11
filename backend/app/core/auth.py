import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User
from app.core.security import decode_access_token

logger = logging.getLogger("enterprise_rag.auth")

security_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extract authenticated user if valid Bearer token is provided.
    Returns None if no token or invalid token is supplied.
    Ensures backward compatibility with unauthenticated endpoints from Phases 1-7.
    """
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        return None

    user_identifier = payload.get("sub")
    if not user_identifier:
        return None

    user = db.query(User).filter(
        (User.id == user_identifier) | (User.email == user_identifier)
    ).first()
    if not user or not user.is_active:
        return None

    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Require a valid Bearer token and return the active authenticated User.
    Raises 401 Unauthorized if token is missing, invalid, or user is inactive.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_identifier = payload.get("sub")
    if not user_identifier:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Support looking up by user.id or user.email
    user = db.query(User).filter(
        (User.id == user_identifier) | (User.email == user_identifier)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact system administrator.",
        )

    return user


def require_roles(*allowed_roles: str):
    """
    Dependency factory ensuring authenticated user possesses one of the allowed roles.
    Raises 403 Forbidden if user role is not authorized.
    """
    def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "USER").upper()
        allowed = [r.upper() for r in allowed_roles]
        if user_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed)}.",
            )
        return current_user
    return _role_checker


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the authenticated user has the 'ADMIN' role.
    Raises 403 Forbidden if user is not an administrator.
    """
    if (current_user.role or "USER").upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required. Access denied.",
        )
    return current_user


def require_manager_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the authenticated user has either 'MANAGER' or 'ADMIN' role.
    Raises 403 Forbidden if user is a standard USER.
    """
    role = (current_user.role or "USER").upper()
    if role not in ("MANAGER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or administrative privileges required. Access denied.",
        )
    return current_user
