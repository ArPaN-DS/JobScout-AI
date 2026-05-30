from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db.models import Count

from .ai_service import CareerAgentAI
from .llm import provider_statuses
from .models import Application, JobLead, NotificationEvent, safe_json_dict
from .profile_store import load_master_profile


@dataclass
class CommandResult:
    ok: bool
    message: str
    data: dict[str, Any] | None = None


class ChannelAdapter:
    name = "base"

    def is_allowed(self, external_id: str) -> bool:
        raise NotImplementedError

    def handle(self, external_id: str, text: str) -> CommandResult:
        if not self.is_allowed(external_id):
            return CommandResult(False, "This chat is not allowed. Add it to the channel allowlist.")
        return handle_command(text)


class TelegramChannelAdapter(ChannelAdapter):
    name = "telegram"

    def is_allowed(self, external_id: str) -> bool:
        return external_id in getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", [])


class DiscordChannelAdapter(ChannelAdapter):
    name = "discord"

    def is_allowed(self, external_id: str) -> bool:
        return external_id in getattr(settings, "DISCORD_ALLOWED_IDS", [])


def handle_command(text: str) -> CommandResult:
    normalized = (text or "").strip()
    if not normalized:
        return CommandResult(False, "Send a command like /status, /top, /providers, /score, /kit, or /submitted.")

    parts = normalized.split(maxsplit=1)
    command = parts[0].lower().lstrip("/")
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command in {"help", "start"}:
        return CommandResult(
            True,
            "Commands: /status, /top, /providers, /score <job text>, /kit <application_id>, "
            "/dismiss <lead_id>, /submitted <application_id>.",
        )
    if command == "status":
        return _status()
    if command in {"top", "jobs"}:
        return _top_jobs()
    if command in {"providers", "provider", "health"}:
        return _provider_health()
    if command == "dismiss":
        return _dismiss(arg)
    if command in {"submitted", "submit"}:
        return _mark_submitted(arg)
    if command == "score":
        return _score_text(arg)
    if command in {"kit", "generate"}:
        return _generate_kit(arg)
    if command in {"pause", "stop"}:
        return CommandResult(True, "Notifications paused for this channel in this session.")

    return CommandResult(False, "Unknown command. Send /help for available commands.")


def record_channel_event(channel: str, event_type: str, recipient: str, payload: dict[str, Any], result: CommandResult):
    event = NotificationEvent.objects.create(
        channel=channel,
        event_type=event_type,
        recipient=recipient,
        payload={"request": payload, "response": result.message, "data": result.data or {}},
        status=NotificationEvent.Status.SENT if result.ok else NotificationEvent.Status.SKIPPED,
    )
    if result.ok:
        event.mark_sent()
    return event


def _status() -> CommandResult:
    app_counts = Application.objects.values("status").annotate(total=Count("id"))
    lead_counts = JobLead.objects.values("status").annotate(total=Count("id"))
    message = "Status: "
    message += ", ".join(f"apps {row['status']}={row['total']}" for row in app_counts) or "apps=0"
    message += "; "
    message += ", ".join(f"leads {row['status']}={row['total']}" for row in lead_counts) or "leads=0"
    return CommandResult(True, message)


def _top_jobs() -> CommandResult:
    leads = JobLead.objects.exclude(match_score=None).order_by("-match_score", "-discovered_at")[:5]
    if not leads:
        return CommandResult(True, "No scored job leads yet.")
    lines = [
        f"#{lead.id} {lead.match_score}% - {lead.title or 'Untitled'} at {lead.company or 'Unknown'}"
        for lead in leads
    ]
    return CommandResult(True, "\n".join(lines))


def _provider_health() -> CommandResult:
    statuses = provider_statuses()
    lines = [
        f"{status.name}: {'ready' if status.enabled else 'off'} ({status.model})"
        + (f" - {status.reason}" if status.reason else "")
        for status in statuses
    ]
    return CommandResult(True, "\n".join(lines) or "No providers configured.")


def _dismiss(arg: str) -> CommandResult:
    if not arg.isdigit():
        return CommandResult(False, "Use /dismiss <lead_id>.")
    try:
        lead = JobLead.objects.get(id=int(arg))
    except JobLead.DoesNotExist:
        return CommandResult(False, "Job lead not found.")
    lead.dismiss()
    return CommandResult(True, f"Dismissed lead #{lead.id}.")


def _mark_submitted(arg: str) -> CommandResult:
    if not arg.isdigit():
        return CommandResult(False, "Use /submitted <application_id>.")
    try:
        application = Application.objects.get(id=int(arg))
    except Application.DoesNotExist:
        return CommandResult(False, "Application not found.")
    application.mark_submitted()
    return CommandResult(True, f"Marked application #{application.id} as submitted.")


def _score_text(arg: str) -> CommandResult:
    if len(arg) < 80:
        return CommandResult(False, "Use /score followed by the full job description.")
    profile = load_master_profile()
    ai = CareerAgentAI()
    result = ai.match_job_to_profile(profile, arg)
    match_data = result.model_dump(mode="json")
    application = Application.objects.create(
        job_description=arg,
        profile_snapshot=profile.to_storage_dict(),
    )
    application.record_match(match_data, profile_snapshot=profile.to_storage_dict(), ai_metadata=ai.last_metadata())
    return CommandResult(
        True,
        f"Application #{application.id}: {match_data['match_score']}% match. {match_data['summary']}",
        {"application_id": application.id, "match": match_data},
    )


def _generate_kit(arg: str) -> CommandResult:
    if not arg.isdigit():
        return CommandResult(False, "Use /kit <application_id>.")
    try:
        application = Application.objects.get(id=int(arg))
    except Application.DoesNotExist:
        return CommandResult(False, "Application not found.")
    profile_data = application.profile_snapshot or load_master_profile().to_storage_dict()
    ai = CareerAgentAI()
    kit = ai.generate_application_kit(profile_data, application.job_description)
    kit_data = kit.model_dump(mode="json")
    application.record_kit(kit_data)
    kit_metadata = safe_json_dict(ai.last_metadata())
    if kit_metadata:
        application.ai_metadata = {**(application.ai_metadata or {}), "kit_llm": kit_metadata}
        application.save(update_fields=["ai_metadata", "updated_at"])
    return CommandResult(True, f"Generated kit for application #{application.id}.")
