import asyncio
import json
import os
import time
import random
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Any

from django.conf import settings

# ─────────────────────────────────────────────
# ERROR CLASSIFICATION
# ─────────────────────────────────────────────

class ErrorType(Enum):
    TRANSIENT = "transient"          # Timeout, 503 → retry
    AUTH_REQUIRED = "auth_required"  # Login wall, 401 → try auto-login
    BOT_BLOCKED = "bot_blocked"     # CAPTCHA, Cloudflare → screenshot + skip
    PERMANENT = "permanent"         # 404, structure changed → log + skip
    UNKNOWN = "unknown"


def classify_error(error: Exception = None, status_code: int = None, page_content: str = "") -> ErrorType:
    """Classify an error into an actionable category."""
    content_lower = page_content.lower() if page_content else ""

    # Check page content signals
    if any(kw in content_lower for kw in ["captcha", "security check", "cloudflare", "verify you are human",
                                            "bot detection", "access denied", "blocked", "unusual traffic"]):
        return ErrorType.BOT_BLOCKED

    if any(kw in content_lower for kw in ["login", "sign in", "signin", "log in", "authentication required"]):
        return ErrorType.AUTH_REQUIRED

    # Check status codes
    if status_code:
        if status_code in (401, 403):
            return ErrorType.AUTH_REQUIRED
        if status_code in (429, 500, 502, 503, 504):
            return ErrorType.TRANSIENT
        if status_code in (404, 410):
            return ErrorType.PERMANENT

    # Check exception types
    if error:
        error_str = str(error).lower()
        if any(kw in error_str for kw in ["timeout", "timed out", "connection reset", "connection refused",
                                           "temporary", "retry", "too many requests"]):
            return ErrorType.TRANSIENT
        if any(kw in error_str for kw in ["captcha", "cloudflare", "blocked", "forbidden"]):
            return ErrorType.BOT_BLOCKED
        if any(kw in error_str for kw in ["not found", "404", "gone"]):
            return ErrorType.PERMANENT

    return ErrorType.UNKNOWN


# ─────────────────────────────────────────────
# EXPONENTIAL BACKOFF RETRY
# ─────────────────────────────────────────────

async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable_errors: tuple = (ErrorType.TRANSIENT, ErrorType.UNKNOWN),
    label: str = "operation"
) -> Any:
    """Execute an async function with exponential backoff retry."""
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            error_type = classify_error(error=e)

            if error_type not in retryable_errors or attempt == max_attempts:
                print(f"  ❌ [{label}] Failed after {attempt} attempts: {e}")
                raise

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if jitter:
                delay *= random.uniform(0.5, 1.5)

            print(f"  ⚡ [{label}] Attempt {attempt}/{max_attempts} failed ({error_type.value}). "
                  f"Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)

    raise last_exception


# ─────────────────────────────────────────────
# CIRCUIT BREAKER
# ─────────────────────────────────────────────

@dataclass
class CircuitState:
    failures: int = 0
    last_failure: Optional[datetime] = None
    is_open: bool = False
    opened_at: Optional[datetime] = None
    total_calls: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """
    Per-portal circuit breaker.
    Trips open after N consecutive failures to save API quota and avoid ip bans.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._circuits: dict[str, CircuitState] = {}

    def _get_state(self, portal: str) -> CircuitState:
        if portal not in self._circuits:
            self._circuits[portal] = CircuitState()
        return self._circuits[portal]

    def is_available(self, portal: str) -> bool:
        state = self._get_state(portal)
        if not state.is_open:
            return True

        if state.opened_at and (datetime.now() - state.opened_at).seconds >= self.recovery_timeout:
            state.is_open = False
            state.failures = 0
            print(f"  🔄 [{portal}] Circuit breaker reset (recovery timeout elapsed)")
            return True

        return False

    def record_success(self, portal: str):
        state = self._get_state(portal)
        state.failures = 0
        state.is_open = False
        state.total_calls += 1

    def record_failure(self, portal: str, error: str = ""):
        state = self._get_state(portal)
        state.failures += 1
        state.total_failures += 1
        state.total_calls += 1
        state.last_failure = datetime.now()

        if state.failures >= self.failure_threshold and not state.is_open:
            state.is_open = True
            state.opened_at = datetime.now()
            print(f"  🔴 [{portal}] Circuit OPEN — {state.failures} consecutive failures. "
                  f"Skipping for {self.recovery_timeout}s. Last error: {error[:80]}")


# Global circuit breaker instance
circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=300)


# ─────────────────────────────────────────────
# SCREENSHOT ON FAILURE
# ─────────────────────────────────────────────

async def screenshot_on_failure(page, portal: str, reason: str = "") -> Optional[str]:
    """Capture a page screenshot and save it to the Django media folder."""
    try:
        screenshots_dir = os.path.join(getattr(settings, "MEDIA_ROOT", "media"), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_portal = "".join(c for c in portal if c.isalnum() or c in ("_", "-"))[:30]
        filename = f"{safe_portal}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)

        await page.screenshot(path=filepath, full_page=False)
        print(f"  📸 Screenshot saved: {filepath}")
        
        # Return path relative to MEDIA_ROOT/media for easy URL rendering
        return os.path.join("screenshots", filename)
    except Exception as e:
        print(f"  ⚠️ Screenshot failed: {e}")
        return None
