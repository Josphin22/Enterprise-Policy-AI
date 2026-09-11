import re
import os
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any, Dict
import bcrypt
import jwt
from app.config import settings

logger = logging.getLogger("enterprise_rag.security")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as exc:
        logger.warning(f"Password verification error: {exc}")
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a signed JWT access token.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    token = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.
    Returns decoded claims dictionary or None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token has expired.")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug(f"Invalid JWT token: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Unexpected error decoding token: {exc}")
        return None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize and validate a filename against path traversal attacks.
    Raises ValueError if path traversal or dangerous patterns are detected.
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Invalid filename: filename must be a non-empty string.")

    # Detect directory traversal characters and null bytes
    if "\x00" in filename:
        raise ValueError("Invalid filename: null bytes detected.")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid filename: path traversal sequence detected.")

    # Strip any leading/trailing whitespace
    clean_name = filename.strip()
    # Extract purely the base name
    base_name = Path(clean_name).name

    # Check for safe characters: alphanumeric, underscores, hyphens, periods, spaces
    if not re.match(r"^[\w\s\.-]+$", base_name, re.UNICODE):
        # Fallback: remove forbidden characters
        base_name = re.sub(r"[^\w\s\.-]", "_", base_name)

    if not base_name or base_name.startswith("."):
        raise ValueError("Invalid filename: hidden or empty filename.")

    return base_name


def verify_safe_path(base_directory: Path, target_path: Path) -> bool:
    """
    Ensure the resolved target path is strictly contained within the base directory.
    Prevents path traversal and symlink escapes.
    """
    try:
        resolved_base = base_directory.resolve()
        resolved_target = target_path.resolve()
        return resolved_target.is_relative_to(resolved_base)
    except Exception:
        return False
