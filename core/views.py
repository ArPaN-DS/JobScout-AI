import json
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .channels import DiscordChannelAdapter, TelegramChannelAdapter, record_channel_event
from .ai_service import AIResponseError, CareerAgentAI, KitValidationError, extract_document_text
from .job_sources import create_application_from_lead, import_manual_job
from .llm import provider_statuses
from .match_policy import thresholds_for_candidate
from .models import Application, JobLead, safe_json_dict
from .profile_readiness import assess_profile_readiness, assert_ready_for_kit_generation
from .evidence_scanner import scan_local_folder
from .profile_store import (
    confirm_claims,
    get_active_candidate,
    load_master_profile,
    profile_exists,
    reject_claims,
    save_master_profile,
    update_candidate_links,
    update_candidate_preferences,
)
from .schemas import MasterProfile


def json_error(message, status=400, *, exc: Exception | None = None):
    if exc is None and isinstance(message, Exception):
        exc = message
        message = str(exc)
    if exc is not None:
        from .errors import format_user_error, exception_http_status

        payload = format_user_error(exc)
        return JsonResponse(
            {
                "success": False,
                "error": payload["message"],
                "error_detail": payload,
            },
            status=exception_http_status(exc) if status == 400 else status,
        )
    return JsonResponse({"success": False, "error": str(message)}, status=status)


def _validate_profile_upload(uploaded_file) -> None:
    max_mb = getattr(settings, "MAX_RESUME_UPLOAD_MB", 8)
    max_bytes = max_mb * 1024 * 1024

    if not uploaded_file:
        raise ValueError("No candidate document uploaded.")
    if uploaded_file.size > max_bytes:
        raise ValueError(f"Candidate document is too large. Maximum allowed size is {max_mb} MB.")
    allowed_suffixes = {".pdf", ".docx"}
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError("Candidate document must be a PDF or DOCX file.")
    if uploaded_file.content_type and uploaded_file.content_type not in {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        raise ValueError("Uploaded file does not look like a supported document.")


def _save_upload_temporarily(uploaded_file) -> Path:
    upload_dir = Path(getattr(settings, "UPLOAD_TEMP_DIR", settings.BASE_DIR / "tmp_uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(uploaded_file.name).suffix.lower() or ".pdf"
    temp_path = upload_dir / f"candidate_doc_{uuid4().hex}{suffix}"
    with temp_path.open("wb") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    return temp_path


def _exception_status(exc: Exception) -> int:
    from .errors import exception_http_status

    return exception_http_status(exc)


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _manual_profile_data(request) -> dict:
    return {
        "full_name": request.POST.get("full_name", "").strip(),
        "email": request.POST.get("email", "").strip(),
        "phone": request.POST.get("phone", "").strip(),
        "location": request.POST.get("location", "").strip(),
        "work_authorization": request.POST.get("work_authorization", "").strip(),
        "availability": request.POST.get("availability", "").strip(),
        "linkedin_url": request.POST.get("linkedin_url", "").strip(),
        "github_url": request.POST.get("github_url", "").strip(),
        "portfolio_url": request.POST.get("portfolio_url", "").strip(),
        "job_preferences": _preferences_data(request),
    }


def _preferences_data(request) -> dict:
    return {
        "target_roles": _csv_list(request.POST.get("target_roles", "")),
        "target_locations": _csv_list(request.POST.get("target_locations", request.POST.get("locations", ""))),
        "locations": _csv_list(request.POST.get("locations", "")),
        "remote_preferences": _csv_list(request.POST.get("remote_preferences", "")),
        "salary_range": request.POST.get("salary_range", request.POST.get("min_salary", "")).strip(),
        "min_salary": request.POST.get("min_salary", "").strip(),
        "experience_level": request.POST.get("experience_level", "").strip(),
        "work_authorization": request.POST.get("work_authorization", "").strip(),
        "visa_status": request.POST.get("visa_status", "").strip(),
        "availability": request.POST.get("availability", "").strip(),
        "blocked_companies": _csv_list(request.POST.get("blocked_companies", "")),
        "must_have_skills": _csv_list(request.POST.get("must_have_skills", "")),
        "resume_source": request.POST.get("resume_source", "claims").strip(),
        "min_match_score": request.POST.get("min_match_score", "").strip(),
        "min_match_confidence": request.POST.get("min_match_confidence", "").strip(),
        "job_freshness_hours": request.POST.get("job_freshness_hours", "").strip(),
        "discovery_sources": _csv_list(request.POST.get("discovery_sources", "")),
    }


def _workflow_context(candidate=None):
    candidate = candidate or get_active_candidate()
    readiness = assess_profile_readiness(candidate)
    thresholds = thresholds_for_candidate(candidate)
    return {
        "candidate": candidate,
        "readiness": readiness,
        "readiness_dict": readiness.to_dict(),
        "match_thresholds": thresholds,
    }


@require_http_methods(["GET", "POST"])
def profile_setup(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("resume") or request.FILES.get("document")
        temp_path = None

        try:
            _validate_profile_upload(uploaded_file)
            temp_path = _save_upload_temporarily(uploaded_file)

            ai = CareerAgentAI()
            profile = ai.extract_profile_from_document(temp_path)
            manual_data = _manual_profile_data(request)
            profile = MasterProfile.model_validate(
                {
                    **profile.to_storage_dict(),
                    "name": manual_data["full_name"] or profile.name,
                    "email": manual_data["email"] or profile.email,
                    "phone": manual_data["phone"] or profile.phone,
                    "linkedin_url": manual_data["linkedin_url"],
                    "github_url": manual_data["github_url"],
                    "job_preferences": manual_data["job_preferences"],
                }
            )
            try:
                extracted_text = extract_document_text(temp_path)
            except Exception:
                extracted_text = ""
            candidate = save_master_profile(
                profile,
                manual_data=manual_data,
                document_info={
                    "document_type": request.POST.get("document_type", "resume"),
                    "original_filename": uploaded_file.name,
                    "content_type": uploaded_file.content_type,
                    "size_bytes": uploaded_file.size,
                    "extracted_text_sample": extracted_text[:1200],
                },
            )
            local_project_path = request.POST.get("local_project_path", "").strip()
            if local_project_path:
                scan_local_folder(candidate, local_project_path)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Candidate profile saved for review.",
                    "data": profile.to_storage_dict(),
                    "candidate_id": candidate.id,
                }
            )
        except Exception as exc:
            return json_error(exc, status=_exception_status(exc))
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

    candidate = get_active_candidate()
    context = {"has_profile": bool(candidate), "candidate": candidate}
    context.update(_workflow_context(candidate))
    return render(request, "core/profile.html", context)


@require_http_methods(["GET", "POST"])
def job_discovery(request):
    if request.method == "POST":
        try:
            master_profile = load_master_profile()
        except FileNotFoundError as exc:
            return json_error(exc, status=400)

        job_url = request.POST.get("job_url", "").strip()
        job_description = request.POST.get("job_description", "").strip()

        if len(job_description) < 80:
            return json_error("Job description is too short to score accurately.", status=400)

        app_record = Application.objects.create(
            job_url=job_url,
            job_description=job_description,
            profile_snapshot=master_profile.to_storage_dict(),
        )

        try:
            thresholds = thresholds_for_candidate(get_active_candidate())
            ai = CareerAgentAI()
            match_results = ai.match_job_to_profile(master_profile, job_description)
            match_data = match_results.model_dump(mode="json")
            app_record.record_match(
                match_data,
                profile_snapshot=master_profile.to_storage_dict(),
                ai_metadata=ai.last_metadata(),
                thresholds=thresholds,
            )

            return JsonResponse(
                {
                    "success": True,
                    "data": match_data,
                    "app_id": app_record.id,
                    "status": app_record.status,
                    "thresholds": {
                        "min_match_score": thresholds.min_match_score,
                        "min_match_confidence": thresholds.min_match_confidence,
                    },
                }
            )
        except Exception as exc:
            app_record.record_failure(exc)
            return json_error(exc, status=_exception_status(exc))

    context = {"has_profile": profile_exists()}
    context.update(_workflow_context())
    return render(request, "core/jobs.html", context)


@require_POST
def generate_kit(request):
    app_id = request.POST.get("app_id")
    if not app_id:
        return json_error("Application ID missing.", status=400)

    try:
        app_record = Application.objects.get(id=app_id)
    except Application.DoesNotExist:
        return json_error("Application record not found.", status=404)

    compact = request.POST.get("compact") in ("1", "on", "true")

    try:
        from .cost_tracking import budget_status

        assert_ready_for_kit_generation(get_active_candidate())
        profile_data = app_record.profile_snapshot or load_master_profile().to_storage_dict()
        ai = CareerAgentAI()
        kit = ai.generate_application_kit(profile_data, app_record.job_description, compact=compact)
        kit_data = kit.model_dump(mode="json")
        app_record.record_kit(kit_data)
        app_record.error_message = ""
        kit_metadata = safe_json_dict(ai.last_metadata())
        if kit_metadata:
            merged = {**(app_record.ai_metadata or {}), "kit_llm": kit_metadata}
            if kit_metadata.get("critic"):
                merged["kit_critic"] = kit_metadata["critic"]
            if kit_metadata.get("prompt_version"):
                merged["prompt_version"] = kit_metadata["prompt_version"]
            app_record.ai_metadata = merged
            app_record.save(update_fields=["ai_metadata", "error_message", "updated_at"])

        return JsonResponse(
            {
                "success": True,
                "data": kit_data,
                "metadata": kit_metadata,
                "budget": budget_status(),
            }
        )
    except Exception as exc:
        app_record.record_failure(exc)
        return json_error(exc, exc=exc, status=_exception_status(exc))


@require_POST
def mark_submitted(request):
    app_id = request.POST.get("app_id")
    if not app_id:
        return json_error("Application ID missing.", status=400)

    try:
        app_record = Application.objects.get(id=app_id)
        app_record.mark_submitted()
        return JsonResponse({"success": True, "message": "Application tracked successfully."})
    except Application.DoesNotExist:
        return json_error("Application record not found.", status=404)
    except Exception as exc:
        return json_error(exc, status=_exception_status(exc))


@require_http_methods(["GET", "POST"])
def provider_settings(request):
    from .models import SecureCredential
    
    keys_to_manage = [
        ("GEMINI_API_KEY", "Google Gemini API Key"),
        ("OPENAI_API_KEY", "OpenAI API Key"),
        ("ANTHROPIC_API_KEY", "Anthropic Claude API Key"),
        ("GROQ_API_KEY", "Groq API Key"),
        ("OPENROUTER_API_KEY", "OpenRouter API Key"),
        ("XAI_API_KEY", "xAI Grok API Key"),
        ("DEEPSEEK_API_KEY", "DeepSeek API Key"),
    ]
    
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "save_keys":
            for key_name, _ in keys_to_manage:
                val = request.POST.get(key_name, "").strip()
                # If they passed a placeholder like "••••••••", it means they didn't edit it
                if val and not val.startswith("••••"):
                    SecureCredential.set_val(key_name, val)
                elif val == "":
                    # If they explicitly emptied the field, remove the key from database
                    SecureCredential.delete_key = SecureCredential.set_val(key_name, "")
            
            # Reset cooldowns on key update to try again immediately
            from .llm import LLMRouter
            LLMRouter.reset_cooldowns()
            return redirect("provider_settings")
            
    # Compile key status
    key_configs = []
    for key_name, label in keys_to_manage:
        db_val = SecureCredential.get_val(key_name)
        env_val = os.getenv(key_name)
        
        has_db = bool(db_val)
        has_env = bool(env_val)
        
        display_val = ""
        if has_db:
            display_val = "••••••••" + db_val[-4:] if len(db_val) > 4 else "••••••••"
        elif has_env:
            display_val = "••••••••" + env_val[-4:] if len(env_val) > 4 else "••••••••"
            
        key_configs.append({
            "name": key_name,
            "label": label,
            "has_db": has_db,
            "has_env": has_env,
            "display_val": display_val,
        })
        
    statuses = [status.__dict__ for status in provider_statuses()]
    return render(
        request,
        "core/provider_settings.html",
        {
            "provider_statuses": statuses,
            "provider_statuses_json": json.dumps(statuses, indent=2),
            "key_configs": key_configs,
        },
    )



@require_http_methods(["GET", "POST"])
def channel_settings(request):
    from .models import CandidatePreference
    candidate = get_active_candidate()
    if request.method == "POST":
        if candidate:
            preferences, _ = CandidatePreference.objects.get_or_create(profile=candidate)
            auto_submit = request.POST.get("auto_submit_enabled") == "on"
            preferences.auto_submit_enabled = auto_submit
            preferences.save(update_fields=["auto_submit_enabled", "updated_at"])
        return redirect("channel_settings")

    preferences = None
    if candidate:
        preferences = getattr(candidate, "preferences", None)
    
    auto_submit_enabled = False
    if preferences:
        auto_submit_enabled = preferences.auto_submit_enabled
    else:
        auto_submit_enabled = getattr(settings, "AUTO_SUBMIT_ENABLED", False)

    return render(
        request,
        "core/channel_settings.html",
        {
            "candidate": candidate,
            "telegram_enabled": bool(getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", [])),
            "discord_enabled": bool(getattr(settings, "DISCORD_ALLOWED_IDS", [])),
            "auto_submit_enabled": auto_submit_enabled,
        },
    )


@require_http_methods(["GET"])
def job_queue(request):
    from .discovery import estimate_llm_cost_usd, queue_stats, recent_source_runs, resolve_discovery_config
    from .sources.registry import DEFAULT_SOURCE_IDS, get_all_source_health

    status_filter = request.GET.get("status", "matched").strip() or "matched"
    queryset = JobLead.objects.exclude(status=JobLead.Status.DISMISSED)
    if status_filter != "all":
        queryset = queryset.filter(status=status_filter)
    leads = queryset.order_by("-match_score", "-discovered_at")[:100]

    new_count = JobLead.objects.filter(status=JobLead.Status.NEW).count()
    matched_count = JobLead.objects.filter(status=JobLead.Status.MATCHED).count()
    config = resolve_discovery_config()

    context = {
        "leads": leads,
        "has_profile": profile_exists(),
        "status_filter": status_filter,
        "queue_stats": queue_stats(),
        "source_health": get_all_source_health(config["enabled_sources"]),
        "recent_runs": recent_source_runs(12),
        "discovery_config": config,
        "default_source_ids": DEFAULT_SOURCE_IDS,
        "new_leads_count": new_count,
        "matched_leads_count": matched_count,
        "score_cost_preview": estimate_llm_cost_usd(match_count=min(new_count, 20)),
        "kit_cost_preview": estimate_llm_cost_usd(kit_count=min(matched_count, 5)),
    }
    context.update(_workflow_context())
    return render(request, "core/queue.html", context)


@require_POST
def run_discovery(request):
    from .tasks import enqueue_discovery_pipeline, tracked_discovery_pipeline

    score_limit = int(request.POST.get("score_limit", 20))
    async_mode = request.POST.get("async") == "on"
    try:
        if async_mode:
            task_id = enqueue_discovery_pipeline(score_limit=score_limit)
            payload = {"success": True, "async": True, "task_id": str(task_id)}
        else:
            payload = {"success": True, "async": False, "result": tracked_discovery_pipeline(score_limit=score_limit)}
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(payload)
        return redirect("job_queue")
    except Exception as exc:
        return json_error(exc, exc=exc, status=_exception_status(exc))


@require_POST
def bulk_score_leads(request):
    from .discovery import estimate_llm_cost_usd
    from .tasks import enqueue_score_unscored_leads, tracked_score_unscored_leads

    limit = max(1, min(int(request.POST.get("limit", 20)), 50))
    preview = estimate_llm_cost_usd(match_count=limit)
    if request.POST.get("preview_only") == "1":
        return JsonResponse({"success": True, "preview": preview})

    async_mode = request.POST.get("async") == "on"
    try:
        if async_mode:
            task_id = enqueue_score_unscored_leads(limit=limit)
            result = {"success": True, "async": True, "task_id": str(task_id), "preview": preview}
        else:
            result = {"success": True, **tracked_score_unscored_leads(limit=limit), "preview": preview}
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(result)
        return redirect("job_queue")
    except Exception as exc:
        return json_error(exc, exc=exc, status=_exception_status(exc))


@require_POST
def bulk_generate_kits_view(request):
    from .discovery import estimate_llm_cost_usd
    from .tasks import enqueue_bulk_generate_kits, tracked_bulk_generate_kits

    top_n = max(1, min(int(request.POST.get("top_n", 3)), 10))
    preview = estimate_llm_cost_usd(kit_count=top_n)
    if request.POST.get("preview_only") == "1":
        return JsonResponse({"success": True, "preview": preview})

    async_mode = request.POST.get("async") == "on"
    try:
        if async_mode:
            task_id = enqueue_bulk_generate_kits(top_n=top_n)
            result = {"success": True, "async": True, "task_id": str(task_id), "preview": preview}
        else:
            result = {"success": True, **tracked_bulk_generate_kits(top_n=top_n), "preview": preview}
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(result)
        return redirect("applications_dashboard")
    except Exception as exc:
        return json_error(exc, exc=exc, status=_exception_status(exc))


@require_http_methods(["GET"])
def discovery_status(request):
    from .cost_tracking import budget_status
    from .discovery import queue_stats, recent_source_runs, resolve_discovery_config
    from .metrics import recent_pipeline_jobs
    from .models import PipelineJob
    from .sources.registry import get_all_source_health

    config = resolve_discovery_config()
    active_jobs = PipelineJob.objects.filter(
        status__in=[PipelineJob.Status.QUEUED, PipelineJob.Status.RUNNING]
    ).order_by("-created_at")[:5]
    return JsonResponse(
        {
            "success": True,
            "queue": queue_stats(),
            "budget": budget_status(),
            "pipeline_jobs": [
                {
                    "id": job.id,
                    "kind": job.kind,
                    "status": job.status,
                    "progress_current": job.progress_current,
                    "progress_total": job.progress_total,
                    "progress_percent": job.progress_percent,
                    "message": job.message,
                }
                for job in active_jobs
            ],
            "recent_pipeline_jobs": recent_pipeline_jobs(6),
            "sources": get_all_source_health(config["enabled_sources"]),
            "recent_runs": [
                {
                    "source_type": run.source_type,
                    "status": run.status,
                    "discovered": run.discovered_count,
                    "imported": run.imported_count,
                    "error": (run.error_message or "")[:120],
                    "started_at": run.started_at.isoformat(),
                }
                for run in recent_source_runs(10)
            ],
            "config": config,
        }
    )


@require_http_methods(["POST"])
def import_job(request):
    lead, created = import_manual_job(request.POST)
    score_now = request.POST.get("score_now") == "on"
    if score_now and len(lead.description) >= 80:
        try:
            master_profile = load_master_profile()
            candidate = get_active_candidate()
            thresholds = thresholds_for_candidate(candidate)
            ai = CareerAgentAI()
            match = ai.match_job_to_profile(master_profile, lead.description)
            match_data = match.model_dump(mode="json")
            lead.record_score(match_data, ai_metadata=ai.last_metadata(), thresholds=thresholds)
            if thresholds.is_strong_match(match.match_score, match.confidence):
                application = create_application_from_lead(
                    lead,
                    profile_snapshot=master_profile.to_storage_dict(),
                )
                application.record_match(
                    match_data,
                    profile_snapshot=master_profile.to_storage_dict(),
                    ai_metadata=ai.last_metadata(),
                    thresholds=thresholds,
                )
        except Exception as exc:
            lead.status = JobLead.Status.FAILED
            lead.error_message = str(exc)
            lead.save(update_fields=["status", "error_message", "updated_at"])
            return json_error(exc, status=_exception_status(exc))
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "created": created, "lead_id": lead.id})
    return redirect("job_queue")


@require_POST
def dismiss_lead(request):
    lead_id = request.POST.get("lead_id")
    if not lead_id:
        return json_error("Lead ID missing.", status=400)
    try:
        lead = JobLead.objects.get(id=lead_id)
    except JobLead.DoesNotExist:
        return json_error("Job lead not found.", status=404)
    lead.dismiss()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "lead_id": lead.id})
    return redirect("job_queue")


@require_http_methods(["GET"])
def applications_dashboard(request):
    from .cost_tracking import budget_status

    applications = Application.objects.all().select_related("source_lead").order_by("-created_at")[:100]
    return render(
        request,
        "core/applications.html",
        {
            "applications": applications,
            "MEDIA_URL": settings.MEDIA_URL,
            "budget": budget_status(),
        },
    )


@require_http_methods(["GET"])
def metrics_dashboard(request):
    from .cost_tracking import budget_status
    from .metrics import funnel_stats, recent_pipeline_jobs

    return render(
        request,
        "core/metrics.html",
        {
            "funnel": funnel_stats(),
            "budget": budget_status(),
            "pipeline_jobs": recent_pipeline_jobs(12),
        },
    )


@require_POST
def cancel_pipeline_job(request, job_id: int):
    from .job_runner import cancel_job

    try:
        job = cancel_job(job_id)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True, "job_id": job.id, "status": job.status})
        return redirect("job_queue")
    except Exception as exc:
        return json_error(exc, exc=exc, status=404)


@require_http_methods(["GET"])
def profile_evidence(request):
    candidate = get_active_candidate()
    profile = candidate.to_master_profile() if candidate else None
    return render(
        request,
        "core/profile_evidence.html",
        {
            "candidate": candidate,
            "profile": profile,
            "profile_json": json.dumps(profile.to_storage_dict(), indent=2) if profile else "",
            "claims": candidate.claims.select_related("source").order_by("category", "value") if candidate else [],
            "documents": candidate.documents.order_by("-uploaded_at") if candidate else [],
            "links": candidate.links.order_by("link_type", "url") if candidate else [],
            "sources": candidate.evidence_sources.order_by("-created_at") if candidate else [],
        },
    )


@require_http_methods(["GET", "POST"])
def profile_review(request):
    candidate = get_active_candidate()
    if not candidate:
        return render(request, "core/profile_review.html", {"candidate": None})

    if request.method == "POST":
        action = request.POST.get("action", "")
        claim_ids = [int(value) for value in request.POST.getlist("claim_ids") if value.isdigit()]
        if action == "confirm_all":
            confirm_claims(candidate)
        elif action == "confirm_selected":
            confirm_claims(candidate, claim_ids)
        elif action == "reject_selected":
            reject_claims(candidate, claim_ids)
        if not candidate.claims.exclude(status__in=["confirmed", "rejected"]).exists():
            candidate.status = candidate.Status.READY
            candidate.save(update_fields=["status", "updated_at"])
        return redirect("profile_review")

    claims = candidate.claims.select_related("source").order_by("status", "category", "value")
    context = {"candidate": candidate, "claims": claims}
    context.update(_workflow_context(candidate))
    return render(request, "core/profile_review.html", context)


@require_http_methods(["GET", "POST"])
def onboarding_documents(request):
    return profile_setup(request)


@require_http_methods(["GET", "POST"])
def onboarding_links(request):
    candidate = get_active_candidate()
    if request.method == "POST":
        if not candidate:
            return json_error("Create a candidate profile before adding links.", status=400)
        update_candidate_links(candidate, _manual_profile_data(request))
        return redirect("profile_evidence")
    return render(request, "core/onboarding_links.html", {"candidate": candidate})


@require_http_methods(["GET", "POST"])
def onboarding_preferences(request):
    candidate = get_active_candidate()
    if request.method == "POST":
        if not candidate:
            return json_error("Create a candidate profile before adding preferences.", status=400)
        update_candidate_preferences(candidate, _preferences_data(request))
        return redirect("profile_evidence")
    
    preferences = None
    if candidate:
        preferences = getattr(candidate, "preferences", None)
    context = {"candidate": candidate, "preferences": preferences}
    context.update(_workflow_context(candidate))
    return render(request, "core/onboarding_preferences.html", context)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = message.get("text", "")
    result = TelegramChannelAdapter().handle(chat_id, text)
    record_channel_event("telegram", "command", chat_id, payload, result)
    response = {"ok": result.ok, "message": result.message}
    if chat_id:
        response = {"method": "sendMessage", "chat_id": chat_id, "text": result.message[:3900]}
    return JsonResponse(response)


@csrf_exempt
@require_POST
def discord_interactions(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"type": 4, "data": {"content": "Invalid JSON."}}, status=400)

    if payload.get("type") == 1:
        return JsonResponse({"type": 1})

    data = payload.get("data") or {}
    command = data.get("name", "")
    options = data.get("options") or []
    arg = " ".join(str(option.get("value", "")) for option in options).strip()
    member = payload.get("member") or {}
    user = member.get("user") or payload.get("user") or {}
    external_id = str(user.get("id") or payload.get("guild_id") or "")
    text = f"/{command} {arg}".strip()
    result = DiscordChannelAdapter().handle(external_id, text)
    record_channel_event("discord", "command", external_id, payload, result)
    return JsonResponse({"type": 4, "data": {"content": result.message[:1900]}})
