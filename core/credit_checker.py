import os
import logging
from django.utils import timezone
from .models import ProviderConfig

logger = logging.getLogger(__name__)


def check_balance(provider_config: ProviderConfig) -> dict:
    """
    Checks the balance for the given provider configuration.
    Since official APIs do not expose public endpoints for checking balance
    without custom web session credentials, we support:
      1. Mocked key checks (for testing and local simulation)
      2. Simulated status (returns OK balance to keep logic running)
      3. Verification of the API key availability
    """
    from .models import SecureCredential
    api_key_name = provider_config.api_key_name
    api_key = SecureCredential.get_val(api_key_name) or os.getenv(api_key_name)

    if not api_key:
        return {"ok": False, "error": f"API key {api_key_name} is not set."}

    # Testing & simulation support
    if api_key.startswith("mock-") or api_key == "test-key" or os.getenv("RUNNING_TESTS") == "true":
        if "exhausted" in api_key or "zero" in api_key:
            return {"ok": True, "balance": 0.0}
        if "low" in api_key:
            return {"ok": True, "balance": 0.5}
        return {"ok": True, "balance": 15.0}

    # For real keys, return a default simulated balance to keep system OK,
    # as providers do not offer a public programmatic balance query.
    return {"ok": True, "balance": 10.0, "simulated": True}


def is_credit_exhausted_error(error_message: str) -> bool:
    """
    Inspects an error message to determine if it indicates credit/quota exhaustion.
    """
    if not error_message:
        return False
    msg = error_message.lower()
    exhausted_keywords = [
        "insufficient_quota",
        "insufficient quota",
        "exceeded your current quota",
        "billing details",
        "credit limit",
        "out of credits",
        "quota exceeded",
        "credits exhausted",
        "zero balance",
        "credit balance",
        "no credit",
        "check your billing",
        "payment_required",
        "quota_exceeded",
        "billing_limit_reached",
        "credit_limit_reached",
    ]
    return any(kw in msg for kw in exhausted_keywords)
