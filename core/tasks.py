from django.conf import settings

from .ai_service import CareerAgentAI
from .cost_tracking import assert_within_budget, budget_status, estimate_cost_from_metadata
from .discovery import (
    archive_old_low_matches,
    archive_stale_leads,
    estimate_llm_cost_usd,
    get_matched_leads_for_kits,
    queue_stats,
    run_discovery,
)
from .job_runner import JobCancelledError, make_idempotency_key, run_tracked, update_progress
from .job_sources import create_application_from_lead
from .match_policy import thresholds_for_candidate
from .models import Application, JobLead
from .profile_readiness import assert_ready_for_kit_generation
from .profile_store import get_active_candidate, load_master_profile

try:
    from django_q.tasks import async_task
except Exception:  # pragma: no cover - django-q2 is optional in local dev
    async_task = None


def score_unscored_leads(limit: int = 10, pipeline_job=None) -> int:
    archive_stale_leads()
    profile = load_master_profile()
    candidate = get_active_candidate()
    thresholds = thresholds_for_candidate(candidate)
    leads = list(JobLead.objects.filter(status=JobLead.Status.NEW).exclude(description="")[:limit])
    scored = 0

    for index, lead in enumerate(leads, start=1):
        if pipeline_job:
            update_progress(pipeline_job, index - 1, f"Scoring {index}/{len(leads)}")
        assert_within_budget(estimate_cost_from_metadata({}, "job_match"))
        ai = CareerAgentAI()
        match = ai.match_job_to_profile(profile, lead.description)
        match_data = match.model_dump(mode="json")
        lead.record_score(match_data, ai_metadata=ai.last_metadata(), thresholds=thresholds)
        if thresholds.is_strong_match(match.match_score, match.confidence):
            application = create_application_from_lead(lead, profile_snapshot=profile.to_storage_dict())
            application.record_match(
                match_data,
                profile_snapshot=profile.to_storage_dict(),
                ai_metadata=ai.last_metadata(),
                thresholds=thresholds,
            )
        scored += 1

    if pipeline_job:
        update_progress(pipeline_job, len(leads), f"Scored {scored} lead(s).")
    return scored


def run_discovery_pipeline(*, score_after: bool = True, score_limit: int = 20, pipeline_job=None) -> dict:
    archive_old_low_matches()
    discovery_result = run_discovery()
    scored = 0
    if score_after:
        scored = score_unscored_leads(limit=score_limit, pipeline_job=pipeline_job)
    return {
        **discovery_result,
        "scored": scored,
        "queue": queue_stats(),
        "budget": budget_status(),
    }


def bulk_generate_kits(top_n: int = 3, pipeline_job=None) -> dict:
    candidate = get_active_candidate()
    assert_ready_for_kit_generation(candidate)
    profile = load_master_profile()
    profile_data = profile.to_storage_dict()
    leads = get_matched_leads_for_kits(limit=top_n)
    generated = 0
    errors: list[str] = []

    for index, lead in enumerate(leads, start=1):
        if pipeline_job:
            update_progress(pipeline_job, index - 1, f"Generating kit {index}/{len(leads)}")
        application = lead.applications.filter(status=Application.Status.MATCHED).first()
        if not application:
            application = create_application_from_lead(lead, profile_snapshot=profile_data)
            match_payload = (lead.ai_metadata or {}).get("match") or {}
            if match_payload:
                application.record_match(
                    match_payload,
                    profile_snapshot=profile_data,
                    thresholds=thresholds_for_candidate(candidate),
                )
        try:
            assert_within_budget(float(getattr(settings, "ESTIMATED_KIT_COST_USD", 0.02)))
            ai = CareerAgentAI()
            kit = ai.generate_application_kit(profile_data, lead.description)
            application.record_kit(kit.model_dump(mode="json"))
            metadata = ai.last_metadata()
            application.ai_metadata = {
                **(application.ai_metadata or {}),
                "kit_llm": metadata,
                "prompt_version": metadata.get("prompt_version"),
            }
            application.save(update_fields=["ai_metadata", "updated_at"])
            lead.status = JobLead.Status.KIT_READY
            lead.save(update_fields=["status", "updated_at"])
            generated += 1
        except JobCancelledError:
            raise
        except Exception as exc:
            errors.append(f"{lead.title}: {exc}")
            application.record_failure(exc)

    if pipeline_job:
        update_progress(pipeline_job, len(leads), f"Generated {generated} kit(s).")
    return {
        "requested": top_n,
        "generated": generated,
        "errors": errors,
        "cost_estimate": estimate_llm_cost_usd(kit_count=top_n),
        "budget": budget_status(),
    }


def tracked_score_unscored_leads(limit: int = 10) -> dict:
    key = make_idempotency_key("score", limit=limit)
    return run_tracked(
        "score",
        key,
        lambda job: {"scored": score_unscored_leads(limit=limit, pipeline_job=job)},
        progress_total=limit,
    )


def tracked_discovery_pipeline(score_limit: int = 20) -> dict:
    key = make_idempotency_key("discovery", score_limit=score_limit)
    return run_tracked(
        "discovery",
        key,
        lambda job: run_discovery_pipeline(score_after=True, score_limit=score_limit, pipeline_job=job),
        progress_total=score_limit,
        metadata={"score_limit": score_limit},
    )


def tracked_bulk_generate_kits(top_n: int = 3) -> dict:
    key = make_idempotency_key("bulk_kit", top_n=top_n)
    return run_tracked(
        "bulk_kit",
        key,
        lambda job: bulk_generate_kits(top_n=top_n, pipeline_job=job),
        progress_total=top_n,
    )


def enqueue_score_unscored_leads(limit: int = 10):
    if async_task is None:
        return tracked_score_unscored_leads(limit=limit)
    return async_task("core.tasks.tracked_score_unscored_leads", limit)


def enqueue_discovery_pipeline(score_limit: int = 20):
    if async_task is None:
        return tracked_discovery_pipeline(score_limit=score_limit)
    return async_task("core.tasks.tracked_discovery_pipeline", score_limit)


def enqueue_bulk_generate_kits(top_n: int = 3):
    if async_task is None:
        return tracked_bulk_generate_kits(top_n=top_n)
    return async_task("core.tasks.tracked_bulk_generate_kits", top_n)
