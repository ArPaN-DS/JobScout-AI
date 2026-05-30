from .ai_service import CareerAgentAI
from .job_sources import create_application_from_lead
from .models import JobLead
from .profile_store import load_master_profile

try:
    from django_q.tasks import async_task
except Exception:  # pragma: no cover - django-q2 is optional in local dev
    async_task = None


def score_unscored_leads(limit: int = 10) -> int:
    profile = load_master_profile()
    scored = 0
    leads = JobLead.objects.filter(status=JobLead.Status.NEW).exclude(description="")[:limit]
    for lead in leads:
        ai = CareerAgentAI()
        match = ai.match_job_to_profile(profile, lead.description)
        match_data = match.model_dump(mode="json")
        lead.record_score(match_data, ai_metadata=ai.last_metadata())
        application = create_application_from_lead(lead, profile_snapshot=profile.to_storage_dict())
        application.record_match(
            match_data,
            profile_snapshot=profile.to_storage_dict(),
            ai_metadata=ai.last_metadata(),
        )
        scored += 1
    return scored


def enqueue_score_unscored_leads(limit: int = 10):
    if async_task is None:
        return score_unscored_leads(limit=limit)
    return async_task("core.tasks.score_unscored_leads", limit)
