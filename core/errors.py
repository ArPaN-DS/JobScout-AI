"""Map exceptions to safe, actionable API responses."""

from __future__ import annotations

from django.conf import settings

from .ai_service import AIResponseError, KitValidationError
from .llm import LLMExhaustedError


def format_user_error(exc: Exception) -> dict:
    """Build a JSON-safe error payload for web clients."""
    payload: dict = {
        "message": str(exc) or "Something went wrong.",
        "code": exc.__class__.__name__,
        "actions": [],
        "retryable": False,
        "compact_retry": False,
    }

    if isinstance(exc, LLMExhaustedError):
        payload["message"] = "All configured LLM providers failed or are unavailable."
        payload["actions"] = list(exc.user_actions)
        payload["retryable"] = True
        payload["compact_retry"] = True
    elif isinstance(exc, KitValidationError):
        payload["message"] = str(exc)
        payload["actions"] = [
            "Review your profile claims and confirm skills.",
            "Retry with a shorter job description (compact mode).",
        ]
        payload["retryable"] = True
        payload["compact_retry"] = True
    elif isinstance(exc, AIResponseError):
        payload["message"] = str(exc)
        payload["actions"] = [
            "Check provider API keys in Provider Settings.",
            "Retry in a few minutes if rate limited.",
        ]
        payload["retryable"] = True
    elif isinstance(exc, (ValueError, FileNotFoundError)):
        payload["message"] = str(exc)
        payload["actions"] = ["Fix the input and try again."]
    elif not settings.DEBUG:
        payload["message"] = _generic_message(exc)
        payload["actions"] = [
            "Retry the action.",
            "Check Provider Settings and profile readiness.",
            "See server logs if you run this instance locally.",
        ]
        payload["retryable"] = True
    else:
        payload["message"] = f"{exc.__class__.__name__}: {exc}"

    return payload


def _generic_message(exc: Exception) -> str:
    if isinstance(exc, AIResponseError):
        return str(exc)
    return "An unexpected error occurred. Please retry or check your configuration."


def exception_http_status(exc: Exception) -> int:
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return 400
    if isinstance(exc, (AIResponseError, LLMExhaustedError, KitValidationError)):
        return 502
    return 500
