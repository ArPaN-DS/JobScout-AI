import os
import logging
from django.utils import timezone
from .models import ProviderConfig

logger = logging.getLogger(__name__)


def check_balance(provider_config: ProviderConfig) -> dict:
    """
    Validates the API key and checks credit status for the given provider config.
    Since official APIs do not expose public endpoints for checking credit balances
    programmatically using standard API keys alone, we verify key correctness
    and credit availability by performing a lightweight metadata/API call.
    """
    from .models import SecureCredential
    api_key_name = provider_config.api_key_name
    api_key = SecureCredential.get_val(api_key_name) or os.getenv(api_key_name)

    if not api_key:
        return {"ok": False, "error": f"API key {api_key_name} is not set."}

    # Testing & simulation support (mock keys)
    if api_key.startswith("mock-") or api_key == "test-key" or os.getenv("RUNNING_TESTS") == "true":
        if "exhausted" in api_key or "zero" in api_key:
            return {"ok": True, "balance": 0.0}
        if "low" in api_key:
            return {"ok": True, "balance": 0.5}
        return {"ok": True, "balance": None}

    # Real key validation!
    try:
        if provider_config.adapter_type == "gemini":
            from google import genai
            client = genai.Client(api_key=api_key)
            try:
                # Retrieve models list to verify auth and active status
                client.models.list()
            except Exception as exc:
                err_msg = str(exc)
                if any(m in err_msg.lower() for m in ["quota", "limit", "credit", "exhausted", "balance"]):
                    return {"ok": False, "error": f"Quota/Credit limit exceeded: {err_msg}", "exhausted": True}
                return {"ok": False, "error": f"Authentication failed: {err_msg}"}

        elif provider_config.adapter_type == "anthropic":
            # Anthropic does not support model list queries via API key.
            # Perform a lightweight 1-token messages API request.
            import urllib.request
            import urllib.error
            import json
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": provider_config.models[0] if provider_config.models else "claude-3-5-haiku-latest",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}]
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    response.read()
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                if exc.code in (401, 403):
                    return {"ok": False, "error": f"Authentication failed (HTTP {exc.code})"}
                elif exc.code == 402 or any(m in raw.lower() for m in ["quota", "credit", "limit", "exhausted", "balance"]):
                    return {"ok": False, "error": "Quota or credit limit exceeded", "exhausted": True}
                elif exc.code == 429:
                    return {"ok": False, "error": "Rate limit exceeded"}
                else:
                    return {"ok": False, "error": f"Anthropic verification failed (HTTP {exc.code}): {raw[:200]}"}

        elif provider_config.adapter_type == "ollama":
            # Test tags endpoint for local Ollama
            import urllib.request
            import json
            base_url = provider_config.base_url or "http://localhost:11434"
            try:
                req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=3) as response:
                    json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                return {"ok": False, "error": f"Failed to connect to local Ollama instance: {exc}"}

        else:
            # openai_compatible (OpenAI, Groq, DeepSeek, OpenRouter, xAI, Kimi, Qwen, etc.)
            import urllib.request
            import urllib.error
            import json
            base_url = (provider_config.base_url or "https://api.openai.com/v1").rstrip("/")
            url = f"{base_url}/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                **provider_config.extra_headers
            }
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    response.read()
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                if exc.code in (401, 403):
                    return {"ok": False, "error": f"Authentication failed (HTTP {exc.code})"}
                elif exc.code == 402 or any(m in raw.lower() for m in ["quota", "credit", "limit", "exhausted", "balance"]):
                    return {"ok": False, "error": "Quota or credit limit exceeded", "exhausted": True}
                elif exc.code == 429:
                    return {"ok": False, "error": "Rate limit or quota exceeded"}
                else:
                    return {"ok": False, "error": f"API check failed (HTTP {exc.code}): {raw[:200]}"}

        # Verification succeeded! Set balance to None to indicate "OK" state without dummy numbers.
        return {"ok": True, "balance": None}

    except Exception as e:
        return {"ok": False, "error": f"Verification error: {str(e)}"}


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
