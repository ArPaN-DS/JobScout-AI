from django.contrib import admin

from .models import (
    Application,
    CandidateDocument,
    CandidateLink,
    CandidatePreference,
    CandidateProfile,
    EvidenceSource,
    JobLead,
    JobSourceRun,
    PipelineJob,
    LLMUsageEvent,
    NotificationEvent,
    ProfileClaim,
)


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "status", "is_active", "updated_at")
    list_filter = ("status", "is_active", "created_at")
    search_fields = ("full_name", "email", "phone", "location")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CandidateDocument)
class CandidateDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "document_type", "original_filename", "status", "uploaded_at")
    list_filter = ("document_type", "status", "uploaded_at")
    search_fields = ("original_filename", "profile__full_name", "profile__email")
    readonly_fields = ("uploaded_at",)


@admin.register(CandidateLink)
class CandidateLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "link_type", "url", "created_at")
    list_filter = ("link_type", "created_at")
    search_fields = ("url", "label", "profile__full_name", "profile__email")
    readonly_fields = ("created_at",)


@admin.register(EvidenceSource)
class EvidenceSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "source_type", "label", "created_at")
    list_filter = ("source_type", "created_at")
    search_fields = ("label", "uri", "profile__full_name", "profile__email")
    readonly_fields = ("created_at",)


@admin.register(ProfileClaim)
class ProfileClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "category", "value_short", "status", "confidence", "updated_at")
    list_filter = ("category", "status", "created_at")
    search_fields = ("value", "evidence_text", "profile__full_name", "profile__email")
    readonly_fields = ("created_at", "updated_at", "normalized_value")

    def value_short(self, obj):
        return obj.value[:90]


@admin.register(CandidatePreference)
class CandidatePreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile",
        "min_match_score",
        "min_match_confidence",
        "experience_level",
        "updated_at",
    )
    search_fields = ("profile__full_name", "profile__email", "experience_level", "salary_range")
    readonly_fields = ("updated_at",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "match_score",
        "submitted",
        "created_at",
        "job_url_short",
    )
    list_filter = ("status", "submitted", "created_at")
    search_fields = ("job_url", "job_description", "match_summary")
    readonly_fields = ("created_at", "updated_at", "date_submitted")

    def job_url_short(self, obj):
        return (obj.job_url or "")[:80]


@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "match_score",
        "title",
        "company",
        "source_type",
        "discovered_at",
    )
    list_filter = ("status", "source_type", "remote_type", "discovered_at")
    search_fields = ("title", "company", "location", "job_url", "description")
    readonly_fields = ("fingerprint", "created_at", "updated_at")


@admin.register(JobSourceRun)
class JobSourceRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_type",
        "source_name",
        "status",
        "discovered_count",
        "imported_count",
        "started_at",
    )
    list_filter = ("status", "source_type", "started_at")
    readonly_fields = ("started_at", "finished_at")


@admin.register(PipelineJob)
class PipelineJobAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "progress_current", "progress_total", "message", "created_at")
    list_filter = ("kind", "status", "created_at")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at")


@admin.register(LLMUsageEvent)
class LLMUsageEventAdmin(admin.ModelAdmin):
    list_display = ("id", "task_type", "provider", "model", "estimated_cost_usd", "created_at")
    list_filter = ("task_type", "provider", "created_at")
    readonly_fields = ("created_at",)


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "event_type", "status", "recipient", "created_at")
    list_filter = ("channel", "status", "event_type", "created_at")
    search_fields = ("recipient", "event_type", "error_message")
    readonly_fields = ("created_at", "sent_at")
