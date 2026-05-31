"""Discovery pipeline: adapters  dedupe  JobLead  optional scoring."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from core.job_sources import deduplicate_jobs, import_job_lead
from core.logging_utils import get_logger
from core.match_policy import thresholds_for_candidate
from core.models import CandidatePreference, CandidateProfile, JobLead, JobSourceRun
from core.profile_store import get_active_candidate, load_master_profile
from core.sources.registry import DEFAULT_SOURCE_IDS, build_adapters

logger = get_logger(__name__)


def resolve_discovery_config(candidate: CandidateProfile | None = None) -> dict[str, Any]:
    candidate = candidate or get_active_candidate()
    hours_old = int(getattr(settings, "DEFAULT_JOB_FRESHNESS_HOURS", 24))
    enabled_sources = list(DEFAULT_SOURCE_IDS)
    queries: list[str] = []

    if candidate:
        try:
            pref = candidate.preferences
            hours_old = pref.job_freshness_hours or hours_old
            if pref.discovery_sources:
                enabled_sources = [s for s in pref.discovery_sources if s]
            pref.generate_queries()
            queries = list(pref.generated_queries or [])
        except CandidatePreference.DoesNotExist:
            pass

    if not queries:
        from core.job_sources import DEFAULT_SEARCH_QUERIES

        queries = list(DEFAULT_SEARCH_QUERIES)

    return {
        "hours_old": max(1, min(hours_old, 168)),
        "enabled_sources": enabled_sources,
        "queries": queries[: int(getattr(settings, "DISCOVERY_MAX_QUERIES", 12))],
    }


def run_discovery(
    *,
    hours_old: int | None = None,
    enabled_sources: list[str] | None = None,
    queries: list[str] | None = None,
) -> dict[str, Any]:
    """Run all enabled adapters sequentially (each with its own JobSourceRun)."""
    config = resolve_discovery_config()
    hours_old = hours_old if hours_old is not None else config["hours_old"]
    enabled_sources = enabled_sources or config["enabled_sources"]
    queries = queries or config["queries"]

    adapters = build_adapters(enabled_sources)
    results = []
    total_discovered = 0
    total_imported = 0

    for adapter in adapters:
        result = adapter.run(queries, hours_old, import_job_lead)
        results.append(
            {
                "source_id": result.source_id,
                "discovered": result.discovered_count,
                "imported": result.imported_count,
                "error": result.error,
            }
        )
        total_discovered += result.discovered_count
        total_imported += result.imported_count

    return {
        "hours_old": hours_old,
        "queries": len(queries),
        "sources_run": len(adapters),
        "total_discovered": total_discovered,
        "total_imported": total_imported,
        "results": results,
    }


def archive_stale_leads(hours_old: int | None = None) -> int:
    """Dismiss unscored leads older than freshness window."""
    config = resolve_discovery_config()
    hours = hours_old if hours_old is not None else config["hours_old"]
    cutoff = timezone.now() - timedelta(hours=hours)
    updated = JobLead.objects.filter(
        status=JobLead.Status.NEW,
        discovered_at__lt=cutoff,
    ).update(status=JobLead.Status.DISMISSED, error_message="Archived: outside freshness window")
    if updated:
        logger.info("Archived %s stale NEW leads (older than %sh)", updated, hours)
    return updated


def archive_old_low_matches(days: int = 7) -> int:
    cutoff = timezone.now() - timedelta(days=days)
    updated = JobLead.objects.filter(
        status=JobLead.Status.LOW_MATCH,
        discovered_at__lt=cutoff,
    ).update(status=JobLead.Status.DISMISSED, error_message="Archived: low match aged out")
    return updated


def queue_stats() -> dict[str, int]:
    rows = (
        JobLead.objects.exclude(status=JobLead.Status.DISMISSED)
        .values("status")
        .annotate(count=Count("id"))
    )
    stats = {row["status"]: row["count"] for row in rows}
    stats["total"] = sum(stats.values())
    return stats


def estimate_llm_cost_usd(*, match_count: int = 0, kit_count: int = 0) -> dict[str, float]:
    match_unit = float(getattr(settings, "ESTIMATED_MATCH_COST_USD", 0.002))
    kit_unit = float(getattr(settings, "ESTIMATED_KIT_COST_USD", 0.02))
    match_total = round(match_count * match_unit, 4)
    kit_total = round(kit_count * kit_unit, 4)
    return {
        "match_count": match_count,
        "kit_count": kit_count,
        "match_cost_usd": match_total,
        "kit_cost_usd": kit_total,
        "total_usd": round(match_total + kit_total, 4),
    }


def get_matched_leads_for_kits(limit: int = 5) -> list[JobLead]:
    """Leads with strong match that do not yet have a kit-ready application."""
    candidate = get_active_candidate()
    thresholds = thresholds_for_candidate(candidate)
    leads = (
        JobLead.objects.filter(status=JobLead.Status.MATCHED)
        .order_by("-match_score", "-discovered_at")
    )
    selected = []
    for lead in leads:
        if lead.match_score is None:
            continue
        if not thresholds.is_strong_match(lead.match_score, _lead_confidence(lead)):
            continue
        has_kit = lead.applications.filter(
            status__in=["kit_generated", "submitted", "auto_applied"]
        ).exists()
        if not has_kit:
            selected.append(lead)
        if len(selected) >= limit:
            break
    return selected


def _lead_confidence(lead: JobLead) -> int | None:
    match = (lead.ai_metadata or {}).get("match") or {}
    return match.get("confidence")


def recent_source_runs(limit: int = 15) -> list[JobSourceRun]:
    return list(JobSourceRun.objects.order_by("-started_at")[:limit])
