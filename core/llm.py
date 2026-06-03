import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol

from django.conf import settings
from .resilience import circuit_breaker


class LLMTask(str, Enum):
    PROFILE_EXTRACT = "profile_extract"
    JOB_MATCH = "job_match"
    APPLICATION_KIT = "application_kit"
    JOB_EXTRACT = "job_extract"
    CRITIC_VALIDATE = "critic_validate"


@dataclass
class LLMRequest:
    task: LLMTask
    prompt: str
    temperature: float = 0.1
    response_mime_type: str = "application/json"


@dataclass
class LLMAttempt:
    provider: str
    model: str
    status: str
    latency_ms: int = 0
    error: str = ""
    retry_after_seconds: int | None = None
    token_usage: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    attempts: list[LLMAttempt]
    token_usage: dict[str, Any] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "token_usage": self.token_usage,
            "attempts": [attempt.to_public_dict() for attempt in self.attempts],
        }


@dataclass
class ProviderStatus:
    name: str
    model: str
    configured: bool
    enabled: bool
    reason: str = ""
    cooldown_remaining_seconds: int = 0


class LLMProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        rate_limited: bool = False,
        auth_error: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.rate_limited = rate_limited
        self.auth_error = auth_error
        self.retry_after_seconds = retry_after_seconds


class LLMExhaustedError(RuntimeError):
    def __init__(self, attempts: list[LLMAttempt]) -> None:
        self.attempts = attempts
        self.user_actions = [
            "Wait for a provider cooldown to reset.",
            "Enable another provider API key in .env.",
            "Turn on Ollama with a local model.",
            "Retry manually with a smaller job description.",
            "Continue without AI and fill the result manually.",
        ]
        super().__init__(
            "All configured LLM providers failed or are unavailable. "
            + " ".join(self.user_actions)
        )


class LLMProviderAdapter(Protocol):
    name: str
    model: str

    @property
    def enabled(self) -> bool:
        ...

    @property
    def configured(self) -> bool:
        ...

    def generate(self, request: LLMRequest) -> tuple[str, dict[str, Any]]:
        ...


def _json_request(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            **headers,
        },
        method="POST",
    )
    timeout = timeout or getattr(settings, "LLM_HTTP_TIMEOUT_SECONDS", 45)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        retry_after = _parse_retry_after(exc.headers.get("retry-after"))
        message = _extract_error_message(raw) or f"HTTP {exc.code}"
        raise LLMProviderError(
            message,
            retryable=exc.code >= 500 or exc.code in {408, 409, 425, 429},
            rate_limited=exc.code == 429,
            auth_error=exc.code in {401, 403},
            retry_after_seconds=retry_after,
        ) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise LLMProviderError(str(exc), retryable=True) from exc
    except json.JSONDecodeError as exc:
        raise LLMProviderError("Provider returned invalid JSON.", retryable=True) from exc


def _parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return max(0, int(float(value)))
    except ValueError:
        return None


def _extract_error_message(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:300]
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or payload)[:500]
    if error:
        return str(error)[:500]
    return str(payload.get("message") or payload.get("detail") or "")[:500]


class GeminiAdapter:
    name = "gemini"

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        if api_key:
            self.api_key = api_key
        else:
            from .models import SecureCredential
            self.api_key = SecureCredential.get_val("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def enabled(self) -> bool:
        return self.configured

    @property
    def client(self):
        if not self.api_key:
            raise LLMProviderError("GEMINI_API_KEY is not set.", auth_error=True, retryable=False)
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(self, request: LLMRequest) -> tuple[str, dict[str, Any]]:
        from google.genai import types

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=request.prompt,
                config=types.GenerateContentConfig(
                    response_mime_type=request.response_mime_type,
                    temperature=request.temperature,
                ),
            )
        except Exception as exc:
            raise _provider_error_from_exception(exc) from exc

        text = (response.text or "").strip()
        usage = {}
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            usage = {
                "prompt_tokens": getattr(usage_metadata, "prompt_token_count", None),
                "completion_tokens": getattr(usage_metadata, "candidates_token_count", None),
                "total_tokens": getattr(usage_metadata, "total_token_count", None),
            }
        return text, usage


class OpenAICompatibleAdapter:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        api_key_env: str,
        base_url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.api_key_env = api_key_env
        from .models import SecureCredential
        self.api_key = SecureCredential.get_val(api_key_env) or os.getenv(api_key_env)
        self.base_url = base_url.rstrip("/")
        self.extra_headers = extra_headers or {}

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def enabled(self) -> bool:
        return self.configured

    def generate(self, request: LLMRequest) -> tuple[str, dict[str, Any]]:
        if not self.api_key:
            raise LLMProviderError(f"{self.api_key_env} is not set.", auth_error=True, retryable=False)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
        }
        if request.response_mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        data = _json_request(
            f"{self.base_url}/chat/completions",
            payload,
            {
                "Authorization": f"Bearer {self.api_key}",
                **self.extra_headers,
            },
        )
        choices = data.get("choices") or []
        if not choices:
            raise LLMProviderError("Provider returned no choices.", retryable=True)
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        else:
            text = str(content or "")
        return text.strip(), data.get("usage") or {}


class AnthropicAdapter:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        if api_key:
            self.api_key = api_key
        else:
            from .models import SecureCredential
            self.api_key = SecureCredential.get_val("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def enabled(self) -> bool:
        return self.configured

    def generate(self, request: LLMRequest) -> tuple[str, dict[str, Any]]:
        if not self.api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not set.", auth_error=True, retryable=False)

        data = _json_request(
            "https://api.anthropic.com/v1/messages",
            {
                "model": self.model,
                "max_tokens": 4096,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            },
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        content = data.get("content") or []
        text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        usage = data.get("usage") or {}
        return text.strip(), usage


class OllamaAdapter:
    name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.model = model
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._enabled = getattr(settings, "OLLAMA_ENABLED", False) if enabled is None else enabled

    @property
    def configured(self) -> bool:
        return bool(self._enabled)

    @property
    def enabled(self) -> bool:
        return bool(self._enabled)

    def generate(self, request: LLMRequest) -> tuple[str, dict[str, Any]]:
        if not self.enabled:
            raise LLMProviderError("Ollama is disabled. Set OLLAMA_ENABLED=true.", retryable=False)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        if request.response_mime_type == "application/json":
            payload["format"] = "json"

        data = _json_request(f"{self.base_url}/api/chat", payload, {})
        message = data.get("message") or {}
        text = str(message.get("content") or "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
        }
        return text.strip(), usage

    def health(self) -> dict[str, Any]:
        request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                data = json.loads(response.read().decode("utf-8"))
            models = [item.get("name") for item in data.get("models", []) if item.get("name")]
            return {"ok": True, "models": models}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


class LLMRouter:
    _cooldowns: dict[tuple[str, str], float] = {}

    def __init__(self, adapters: list[LLMProviderAdapter] | None = None) -> None:
        self.adapters = adapters

    def generate(
        self,
        request: LLMRequest,
        blocked_providers: set[str] | None = None,
    ) -> LLMResult:
        adapters = self.adapters or build_provider_chain(request.task)
        attempts: list[LLMAttempt] = []
        blocked_providers = blocked_providers or set()

        for adapter in adapters:
            if adapter.name in blocked_providers:
                attempts.append(
                    LLMAttempt(adapter.name, adapter.model, "skipped", error="Provider blocked for this retry.")
                )
                continue

            # Check circuit breaker
            circuit_name = f"llm:{adapter.name}:{adapter.model}"
            if not circuit_breaker.is_available(circuit_name):
                cooldown = circuit_breaker.cooldown_remaining(circuit_name)
                attempts.append(
                    LLMAttempt(
                        adapter.name,
                        adapter.model,
                        "cooldown",
                        error="Provider circuit is open (cooling down after consecutive failures).",
                        retry_after_seconds=cooldown,
                    )
                )
                continue

            cooldown_remaining = self.cooldown_remaining(adapter.name, adapter.model)
            if cooldown_remaining > 0:
                attempts.append(
                    LLMAttempt(
                        adapter.name,
                        adapter.model,
                        "cooldown",
                        error="Provider is cooling down after a previous failure.",
                        retry_after_seconds=cooldown_remaining,
                    )
                )
                continue

            if not adapter.enabled:
                attempts.append(
                    LLMAttempt(adapter.name, adapter.model, "skipped", error="Provider is not configured.")
                )
                continue

            started = time.perf_counter()
            try:
                text, usage = adapter.generate(request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                circuit_breaker.record_success(circuit_name)
                attempts.append(
                    LLMAttempt(
                        adapter.name,
                        adapter.model,
                        "success",
                        latency_ms=latency_ms,
                        token_usage=usage,
                    )
                )
                return LLMResult(
                    text=text,
                    provider=adapter.name,
                    model=adapter.model,
                    attempts=attempts,
                    token_usage=usage,
                )
            except LLMProviderError as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                retry_after = exc.retry_after_seconds
                attempts.append(
                    LLMAttempt(
                        adapter.name,
                        adapter.model,
                        "failed",
                        latency_ms=latency_ms,
                        error=str(exc),
                        retry_after_seconds=retry_after,
                    )
                )
                circuit_breaker.record_failure(circuit_name, str(exc))
                if exc.auth_error:
                    blocked_providers.add(adapter.name)
                elif exc.rate_limited or exc.retryable:
                    cooldown = retry_after or getattr(settings, "LLM_PROVIDER_COOLDOWN_SECONDS", 90)
                    self.cooldown_provider(adapter.name, adapter.model, cooldown)
                continue
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                attempts.append(
                    LLMAttempt(
                        adapter.name,
                        adapter.model,
                        "failed",
                        latency_ms=latency_ms,
                        error=str(exc),
                    )
                )
                circuit_breaker.record_failure(circuit_name, str(exc))
                self.cooldown_provider(
                    adapter.name,
                    adapter.model,
                    getattr(settings, "LLM_PROVIDER_COOLDOWN_SECONDS", 90),
                )
                continue

        raise LLMExhaustedError(attempts)

    @classmethod
    def cooldown_provider(cls, provider: str, model: str, seconds: int) -> None:
        cls._cooldowns[(provider, model)] = time.time() + max(1, seconds)

    @classmethod
    def cooldown_remaining(cls, provider: str, model: str) -> int:
        remaining = cls._cooldowns.get((provider, model), 0) - time.time()
        return max(0, int(remaining))

    @classmethod
    def reset_cooldowns(cls) -> None:
        cls._cooldowns.clear()
        circuit_breaker._circuits.clear()


def build_provider_chain(task: LLMTask) -> list[LLMProviderAdapter]:
    order = getattr(settings, "LLM_PROVIDER_ORDER", [])
    adapters = _adapter_map(task)
    return [adapters[name] for name in order if name in adapters]


def provider_statuses(task: LLMTask = LLMTask.JOB_MATCH) -> list[ProviderStatus]:
    statuses: list[ProviderStatus] = []
    for adapter in build_provider_chain(task):
        configured = adapter.configured
        cooldown = LLMRouter.cooldown_remaining(adapter.name, adapter.model)
        reason = ""
        if not configured:
            reason = "Missing API key or disabled."
        elif cooldown:
            reason = "Cooling down after a provider failure."
        statuses.append(
            ProviderStatus(
                name=adapter.name,
                model=adapter.model,
                configured=configured,
                enabled=adapter.enabled and cooldown == 0,
                reason=reason,
                cooldown_remaining_seconds=cooldown,
            )
        )
    return statuses


def _adapter_map(task: LLMTask) -> dict[str, LLMProviderAdapter]:
    gemini_model = (
        getattr(settings, "GEMINI_PRO_MODEL", "gemini-2.5-pro")
        if task == LLMTask.APPLICATION_KIT
        else getattr(settings, "GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    )
    return {
        "gemini": GeminiAdapter(gemini_model),
        "openai": OpenAICompatibleAdapter(
            name="openai",
            model=getattr(settings, "OPENAI_MODEL", "gpt-4.1-mini"),
            api_key_env="OPENAI_API_KEY",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        ),
        "anthropic": AnthropicAdapter(getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-haiku-latest")),
        "xai": OpenAICompatibleAdapter(
            name="xai",
            model=getattr(settings, "XAI_MODEL", "grok-3-mini"),
            api_key_env="XAI_API_KEY",
            base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        ),
        "groq": OpenAICompatibleAdapter(
            name="groq",
            model=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key_env="GROQ_API_KEY",
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        ),
        "openrouter": OpenAICompatibleAdapter(
            name="openrouter",
            model=getattr(settings, "OPENROUTER_MODEL", "openrouter/auto"),
            api_key_env="OPENROUTER_API_KEY",
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Job_bro_AI"),
            },
        ),
        "deepseek": OpenAICompatibleAdapter(
            name="deepseek",
            model=getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
            api_key_env="DEEPSEEK_API_KEY",
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        ),
        "kimi": OpenAICompatibleAdapter(
            name="kimi",
            model=getattr(settings, "MOONSHOT_MODEL", "kimi-k2.5"),
            api_key_env="MOONSHOT_API_KEY",
            base_url=os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"),
        ),
        "qwen": OpenAICompatibleAdapter(
            name="qwen",
            model=getattr(settings, "DASHSCOPE_MODEL", "qwen-plus"),
            api_key_env="DASHSCOPE_API_KEY",
            base_url=os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
        ),
        "ollama": OllamaAdapter(
            getattr(settings, "OLLAMA_MODEL", "llama3.1"),
            getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
            getattr(settings, "OLLAMA_ENABLED", False),
        ),
    }


def _provider_error_from_exception(exc: Exception) -> LLMProviderError:
    message = str(exc)
    lowered = message.lower()
    return LLMProviderError(
        message,
        retryable=not any(marker in lowered for marker in ["api key", "permission", "unauthorized"]),
        rate_limited=any(marker in lowered for marker in ["429", "quota", "rate limit"]),
        auth_error=any(marker in lowered for marker in ["api key", "permission", "unauthorized", "403", "401"]),
    )
