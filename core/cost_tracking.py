"""LLM usage accounting and daily budget guards."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import LLMUsageEvent


def estimate_cost_from_metadata(metadata: dict[str, Any], task_type: str = "") -> float:
    """Rough USD estimate from token_usage or task defaults."""
    usage = metadata.get("token_usage") or {}
    if isinstance(usage, dict) and usage:
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        total = input_tokens + output_tokens
        if total:
            return round(total * float(getattr(settings, "ESTIMATED_TOKEN_COST_USD_PER_1K", 0.0005)) / 1000, 6)

    if task_type == "application_kit" or task_type == "APPLICATION_KIT":
        return float(getattr(settings, "ESTIMATED_KIT_COST_USD", 0.02))
    if task_type in ("job_match", "JOB_MATCH"):
        return float(getattr(settings, "ESTIMATED_MATCH_COST_USD", 0.002))
    return float(getattr(settings, "ESTIMATED_MATCH_COST_USD", 0.002))


def record_llm_usage(
    metadata: dict[str, Any],
    *,
    task_type: str,
    related_type: str = "",
    related_id: int | None = None,
) -> LLMUsageEvent | None:
    if not metadata:
        return None
    provider = str(metadata.get("provider") or "unknown")
    model = str(metadata.get("model") or "")
    cost = estimate_cost_from_metadata(metadata, task_type)
    return LLMUsageEvent.objects.create(
        task_type=task_type,
        provider=provider,
        model=model,
        token_usage=metadata.get("token_usage") or {},
        estimated_cost_usd=cost,
        related_type=related_type,
        related_id=related_id,
    )


def daily_spend_usd() -> float:
    since = timezone.now() - timedelta(days=1)
    total = LLMUsageEvent.objects.filter(created_at__gte=since).aggregate(
        total=Sum("estimated_cost_usd")
    )["total"]
    return float(total or 0)


def budget_status() -> dict[str, Any]:
    limit = float(getattr(settings, "DAILY_LLM_BUDGET_USD", 2.0))
    spent = daily_spend_usd()
    remaining = max(0.0, round(limit - spent, 4))
    return {
        "daily_limit_usd": limit,
        "spent_usd": round(spent, 4),
        "remaining_usd": remaining,
        "over_budget": spent >= limit,
        "warning": spent >= limit * 0.8,
    }


def assert_within_budget(extra_usd: float = 0) -> None:
    status = budget_status()
    if status["spent_usd"] + extra_usd > status["daily_limit_usd"]:
        raise RuntimeError(
            f"Daily LLM budget exceeded (${status['spent_usd']:.2f} / "
            f"${status['daily_limit_usd']:.2f}). Try again tomorrow or raise DAILY_LLM_BUDGET_USD."
        )
