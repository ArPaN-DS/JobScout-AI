"""Local funnel metrics for the career agent workflow."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

from .cost_tracking import budget_status, daily_spend_usd
from .models import Application, JobLead, JobSourceRun, LLMUsageEvent, PipelineJob


def funnel_stats(days: int = 30) -> dict[str, Any]:
    since = timezone.now() - timedelta(days=days)
    leads = JobLead.objects.filter(created_at__gte=since)
    apps = Application.objects.filter(created_at__gte=since)

    lead_by_status = dict(
        leads.values("status").annotate(c=Count("id")).values_list("status", "c")
    )
    app_by_status = dict(
        apps.values("status").annotate(c=Count("id")).values_list("status", "c")
    )

    ingested = leads.count()
    scored = leads.exclude(match_score__isnull=True).count()
    matched = lead_by_status.get(JobLead.Status.MATCHED, 0) + lead_by_status.get(JobLead.Status.KIT_READY, 0)
    kits = app_by_status.get(Application.Status.KIT_GENERATED, 0) + app_by_status.get(
        Application.Status.AUTO_APPLIED, 0
    )
    submitted = apps.filter(submitted=True).count() + app_by_status.get(Application.Status.SUBMITTED, 0)

    conversion = {
        "ingested": ingested,
        "scored": scored,
        "matched": matched,
        "kits": kits,
        "submitted": submitted,
        "score_rate": _pct(scored, ingested),
        "match_rate": _pct(matched, scored),
        "kit_rate": _pct(kits, matched),
        "submit_rate": _pct(submitted, kits),
    }

    return {
        "period_days": days,
        "leads": lead_by_status,
        "applications": app_by_status,
        "conversion": conversion,
        "discovery_runs_7d": JobSourceRun.objects.filter(started_at__gte=timezone.now() - timedelta(days=7)).count(),
        "failed_applications_7d": apps.filter(
            status=Application.Status.FAILED,
            updated_at__gte=timezone.now() - timedelta(days=7),
        ).count(),
        "llm_events_24h": LLMUsageEvent.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=1)
        ).count(),
        "budget": budget_status(),
        "daily_spend_usd": daily_spend_usd(),
    }


def _pct(part: int, whole: int) -> float:
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


def recent_pipeline_jobs(limit: int = 8) -> list[dict[str, Any]]:
    jobs = PipelineJob.objects.order_by("-created_at")[:limit]
    return [
        {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "message": job.message,
            "error": (job.error_message or "")[:120],
            "created_at": job.created_at.isoformat(),
        }
        for job in jobs
    ]
