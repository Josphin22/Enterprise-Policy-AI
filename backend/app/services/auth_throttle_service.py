import time
import logging
from typing import Dict, Tuple
from app.config import settings

logger = logging.getLogger("enterprise_rag.security.throttle")


class AuthThrottleService:
    """
    In-memory rate limiter and failed-login throttling service (Phase 11).
    Tracks failed authentication attempts by key (IP / email) within a sliding window.
    Locks out repeated attackers without locking legitimate users out unnecessarily.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        lockout_duration_seconds: int = 900,  # 15 minutes
    ):
        self.max_attempts = max_attempts
        self.lockout_duration_seconds = lockout_duration_seconds
        # key -> (attempt_count, first_attempt_timestamp, lockout_until_timestamp)
        self._attempts: Dict[str, Tuple[int, float, float]] = {}

    def _cleanup_expired(self, current_time: float) -> None:
        """Prune entries whose lockout or tracking window has lapsed."""
        expired_keys = [
            k for k, (count, first_ts, lockout_until) in self._attempts.items()
            if current_time > lockout_until and (current_time - first_ts) > (self.lockout_duration_seconds * 2)
        ]
        for k in expired_keys:
            self._attempts.pop(k, None)

    def is_locked_out(self, key: str) -> Tuple[bool, int]:
        """
        Check if an identifier (IP address or email) is currently locked out.
        Returns: (is_locked, remaining_lockout_seconds)
        """
        now = time.time()
        self._cleanup_expired(now)

        entry = self._attempts.get(key.lower().strip())
        if not entry:
            return False, 0

        count, first_ts, lockout_until = entry
        if now < lockout_until:
            remaining = int(lockout_until - now)
            return True, max(remaining, 1)

        return False, 0

    def record_failed_attempt(self, key: str) -> Tuple[int, bool, int]:
        """
        Record a failed authentication attempt.
        Returns: (new_attempt_count, is_now_locked, remaining_lockout_seconds)
        """
        now = time.time()
        self._cleanup_expired(now)
        norm_key = key.lower().strip()

        entry = self._attempts.get(norm_key)
        if not entry:
            self._attempts[norm_key] = (1, now, 0.0)
            return 1, False, 0

        count, first_ts, lockout_until = entry

        # If already locked, remain locked
        if now < lockout_until:
            return count, True, int(lockout_until - now)

        new_count = count + 1
        if new_count >= self.max_attempts:
            lockout_time = now + self.lockout_duration_seconds
            self._attempts[norm_key] = (new_count, first_ts, lockout_time)
            logger.warning(
                f"Authentication throttled for key '{norm_key}': "
                f"{new_count} consecutive failures. Locked for {self.lockout_duration_seconds}s."
            )
            return new_count, True, self.lockout_duration_seconds

        self._attempts[norm_key] = (new_count, first_ts, 0.0)
        return new_count, False, 0

    def reset(self, key: str) -> None:
        """Reset failed attempt counters upon successful login."""
        norm_key = key.lower().strip()
        self._attempts.pop(norm_key, None)

    def reset_attempts(self, key: str) -> None:
        """Alias for reset."""
        self.reset(key)


# Global singleton instance configured from settings
auth_throttle = AuthThrottleService(
    max_attempts=settings.LOGIN_MAX_FAILED_ATTEMPTS,
    lockout_duration_seconds=settings.LOGIN_LOCKOUT_MINUTES * 60,
)
