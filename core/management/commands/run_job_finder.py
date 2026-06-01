import asyncio
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

from core.models import JobLead, Application, CandidateProfile, CandidatePreference
from core.job_sources import create_application_from_lead
from core.ai_service import CareerAgentAI
from core.match_policy import thresholds_for_candidate
from core.tasks import run_discovery_pipeline
from core.resume_tailor import generate_tailored_resume
from core.auto_applier import try_auto_apply
from core.resilience import circuit_breaker

class Command(BaseCommand):
    help = "Run the daily autonomous job finder, matching, resume tailoring, and auto-applying pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Scan and score jobs, but do not trigger Playwright auto-applying.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Limit the number of jobs to score and apply to in a single run.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        self.stdout.write(self.style.SUCCESS("[START] Job Finder & Auto-Applier Loop starting..."))

        # 1. Fetch active candidate profile and preferences
        profile = CandidateProfile.objects.filter(is_active=True).first()
        if not profile:
            self.stdout.write(self.style.ERROR("[ERROR] No active CandidateProfile found. Run onboarding setup first."))
            return

        pref = CandidatePreference.objects.filter(profile=profile).first()
        auto_submit = getattr(pref, "auto_submit_enabled", False)
        resume_src = getattr(pref, "resume_source", "claims")

        self.stdout.write(f"  [Profile] {profile.full_name}")
        self.stdout.write(f"  [Auto-Submit] {'ENABLED (Autonomous)' if auto_submit else 'DISABLED (Safety Mode)'}")
        self.stdout.write(f"  [Resume Source] {'DB Claims Assembled' if resume_src == 'claims' else 'Uploaded Document'}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.stdout.write("[Step 1] Running discovery pipeline (adapter-based ingest)...")
        discovery = run_discovery_pipeline(score_after=True, score_limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"  [OK] Imported {discovery['total_imported']} new leads from "
                f"{discovery['sources_run']} sources."
            )
        )

        thresholds = thresholds_for_candidate(profile)
        master_profile = profile.to_master_profile()
        matched_applications = list(
            Application.objects.filter(
                status=Application.Status.MATCHED,
                source_lead__status=JobLead.Status.MATCHED,
            )
            .select_related("source_lead")
            .order_by("-match_score")[:limit]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"[Step 2 Done] {len(matched_applications)} matched applications "
                f"(threshold score>={thresholds.min_match_score}, "
                f"confidence>={thresholds.min_match_confidence})."
            )
        )

        if not matched_applications:
            self.stdout.write(self.style.WARNING("[DONE] No jobs met the match threshold today. Complete."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Skipping resume tailoring and Playwright auto-applying."))
            for app in matched_applications:
                self.stdout.write(f"  [Dry Run Match] {app.source_lead.title} at {app.source_lead.company} ({app.match_score}%)")
            return

        # 5. Tailor & Auto-Apply Loop
        self.stdout.write("[Step 3] Generating tailored resumes and triggering Playwright auto-applier...")
        for app in matched_applications:
            lead = app.source_lead
            job_details = {
                "title": lead.title,
                "company": lead.company,
                "description": lead.description
            }

            # A. Generate Tailored Resume PDF
            try:
                self.stdout.write(f"  [Tailor] Tailoring resume for '{lead.company}'...")
                relative_pdf_path = loop.run_until_complete(
                    generate_tailored_resume(job_details, master_profile)
                )
                app.tailored_resume_pdf = relative_pdf_path
                app.status = Application.Status.KIT_GENERATED
                app.save()
            except Exception as ex:
                self.stdout.write(self.style.ERROR(f"  [Tailor] Failed: {ex}"))
                app.record_failure(ex)
                continue

            # B. Trigger Playwright Auto-Applier
            try:
                self.stdout.write(f"  [AutoApply] Running Playwright stealth browser for '{lead.company}'...")
                success, apply_status, screenshot_path, err = loop.run_until_complete(
                    try_auto_apply(
                        apply_url=lead.job_url,
                        pdf_path=relative_pdf_path,
                        profile_data=master_profile.to_storage_dict(),
                        auto_submit=auto_submit
                    )
                )

                app.screenshot = screenshot_path
                if success:
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Applied successfully to {lead.company}!"))
                    app.mark_submitted()
                    app.status = Application.Status.AUTO_APPLIED
                else:
                    self.stdout.write(self.style.WARNING(f"  [MANUAL] Form filled, manual submit required: {err}"))
                    app.status = Application.Status.MANUAL_REQUIRED
                    app.error_message = err

                app.save()

                # C. Dispatch Telegram/Discord Alert
                loop.run_until_complete(
                    send_pipeline_notification(app, auto_submit)
                )

            except Exception as ex:
                self.stdout.write(self.style.ERROR(f"  [FAIL] Playwright apply failed: {ex}"))
                app.record_failure(ex)

        self.stdout.write(self.style.SUCCESS("[DONE] Job Finder & Auto-Applier Loop Finished successfully!"))


# ─────────────────────────────────────────────
# NOTIFICATION DISPATCHER (Telegram & Discord support)
# ─────────────────────────────────────────────

async def send_pipeline_notification(app: Application, auto_submit: bool):
    """Sends detailed application match alert and tailored PDF file via Telegram/Discord hooks."""
    lead = app.source_lead
    pdf_local_path = os.path.join(settings.MEDIA_ROOT, app.tailored_resume_pdf) if app.tailored_resume_pdf else None
    
    score_label = "[HIGH]" if app.match_score >= 80 else "[MATCH]"
    status_label = "[AUTO-APPLIED]" if app.status == Application.Status.AUTO_APPLIED else "[MANUAL SUBMIT REQUIRED]"

    msg = (
        f"{score_label} <b>New Match Scored: {app.match_score}%</b>\n"
        f"Role: <b>{lead.title}</b>\n"
        f"Company: {lead.company}\n"
        f"Location: {lead.location}\n"
        f"Source: {lead.source_name}\n"
        f"Summary: {app.match_summary}\n\n"
        f"<b>Status: {status_label}</b>\n"
        f"<a href='{lead.job_url}'>Click here to view / submit</a>"
    )

    # 1. Telegram Push
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    allowed_chats = getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", [])
    
    if telegram_token and allowed_chats:
        try:
            import httpx
            # Make sure we import Telegram Bot or use direct HTTPS requests to bypass version conflicts
            async with httpx.AsyncClient() as client:
                for chat_id in allowed_chats:
                    if pdf_local_path and os.path.exists(pdf_local_path):
                        # Send as document with caption
                        url = f"https://api.telegram.org/bot{telegram_token}/sendDocument"
                        with open(pdf_local_path, "rb") as f:
                            files = {"document": (os.path.basename(pdf_local_path), f, "application/pdf")}
                            data = {"chat_id": chat_id, "caption": msg[:1024], "parse_mode": "HTML"}
                            await client.post(url, data=data, files=files, timeout=20.0)
                    else:
                        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                        data = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
                        await client.post(url, json=data, timeout=20.0)
        except Exception as e:
            print(f"  [WARN] Telegram notification failed: {e}")

    # 2. Discord Webhook Push
    discord_webhook = os.getenv("NOTIFICATION_WEBHOOK_URL")
    if discord_webhook:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                payload = {
                    "username": "AI Career Agent",
                    "embeds": [{
                        "title": f"{score_label} {app.match_score}% Match: {lead.title}",
                        "description": f"**Company:** {lead.company}\n**Location:** {lead.location}\n**Summary:** {app.match_summary}\n\n**Status:** {status_label}\n[Job Link]({lead.job_url})",
                        "color": 3066993 if app.match_score >= 80 else 15105570
                    }]
                }
                await client.post(discord_webhook, json=payload, timeout=20.0)
        except Exception as e:
            print(f"  [WARN] Discord notification failed: {e}")
