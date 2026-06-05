import hashlib
import json

from django.db import models
from django.utils import timezone

from .schemas import MasterProfile, normalize_claim


def safe_json_dict(value):
    if not isinstance(value, dict):
        return {}
    try:
        json.dumps(value)
    except TypeError:
        return {}
    return value


def clean_json_list(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    seen = set()
    for item in value:
        text = str(item or "").strip()
        key = normalize_claim(text)
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


class CandidateProfile(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW_REQUIRED = "review_required", "Review Required"
        READY = "ready", "Ready"

    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.REVIEW_REQUIRED,
        db_index=True,
    )
    full_name = models.CharField(max_length=240, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=240, blank=True)
    work_authorization = models.CharField(max_length=240, blank=True)
    availability = models.CharField(max_length=240, blank=True)
    linkedin_url = models.URLField(max_length=500, blank=True)
    github_url = models.URLField(max_length=500, blank=True)
    portfolio_url = models.URLField(max_length=500, blank=True)
    extracted_profile = models.JSONField(default=dict, blank=True)
    confirmed_profile = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "-updated_at"]),
            models.Index(fields=["status", "-updated_at"]),
        ]

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).order_by("-updated_at").first()

    def apply_manual_fields(self, data):
        field_map = {
            "full_name": "full_name",
            "name": "full_name",
            "email": "email",
            "phone": "phone",
            "location": "location",
            "work_authorization": "work_authorization",
            "visa_status": "work_authorization",
            "availability": "availability",
            "linkedin_url": "linkedin_url",
            "github_url": "github_url",
            "portfolio_url": "portfolio_url",
        }
        for source, target in field_map.items():
            value = str(data.get(source, "") or "").strip()
            if value:
                setattr(self, target, value)

    def to_master_profile(self) -> MasterProfile:
        data = safe_json_dict(self.extracted_profile).copy()
        data.update(safe_json_dict(self.confirmed_profile))

        if self.full_name:
            data["name"] = self.full_name
        if self.email:
            data["email"] = self.email
        if self.phone:
            data["phone"] = self.phone
        if self.linkedin_url:
            data["linkedin_url"] = self.linkedin_url
        if self.github_url:
            data["github_url"] = self.github_url

        claims = self.claims.filter(
            status__in=[
                ProfileClaim.Status.EVIDENCE_BACKED,
                ProfileClaim.Status.CONFIRMED,
            ]
        )
        skills = [claim.value for claim in claims.filter(category=ProfileClaim.Category.SKILL)]
        domains = [claim.value for claim in claims.filter(category=ProfileClaim.Category.DOMAIN)]
        notes = [claim.value for claim in claims.filter(category=ProfileClaim.Category.EVIDENCE_NOTE)]
        experiences = [
            claim.data
            for claim in claims.filter(category=ProfileClaim.Category.EXPERIENCE)
            if isinstance(claim.data, dict)
        ]

        if skills:
            data["skills"] = clean_json_list(skills)
        if domains:
            data["domains"] = clean_json_list(domains)
        if notes:
            data["evidence_notes"] = clean_json_list(notes)
        if experiences:
            data["experience"] = experiences

        if hasattr(self, "preferences"):
            data["job_preferences"] = self.preferences.to_storage_dict()

        return MasterProfile.model_validate(data)

    def __str__(self):
        return self.full_name or self.email or "Candidate Profile"


class CandidateDocument(models.Model):
    class DocumentType(models.TextChoices):
        RESUME = "resume", "Resume"
        COVER_LETTER = "cover_letter", "Cover Letter"
        CERTIFICATE = "certificate", "Certificate"
        PROJECT_SUMMARY = "project_summary", "Project Summary"
        PUBLICATION = "publication", "Publication"
        TRANSCRIPT = "transcript", "Transcript"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        EXTRACTED = "extracted", "Extracted"
        FAILED = "failed", "Failed"

    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=40, choices=DocumentType.choices, default=DocumentType.RESUME)
    original_filename = models.CharField(max_length=260)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    extracted_text_sample = models.TextField(blank=True)
    extracted_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename


class CandidateLink(models.Model):
    class LinkType(models.TextChoices):
        LINKEDIN = "linkedin", "LinkedIn"
        GITHUB = "github", "GitHub"
        PORTFOLIO = "portfolio", "Portfolio"
        OTHER = "other", "Other"

    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="links")
    link_type = models.CharField(max_length=40, choices=LinkType.choices)
    url = models.URLField(max_length=700)
    label = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("profile", "link_type", "url")

    def __str__(self):
        return self.label or self.url


class EvidenceSource(models.Model):
    class SourceType(models.TextChoices):
        RESUME_UPLOAD = "resume_upload", "Resume Upload"
        DOCUMENT_UPLOAD = "document_upload", "Document Upload"
        LINK = "link", "Link"
        LOCAL_FOLDER = "local_folder", "Local Folder"
        MANUAL = "manual", "Manual"
        AI_EXTRACTION = "ai_extraction", "AI Extraction"

    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="evidence_sources")
    source_type = models.CharField(max_length=40, choices=SourceType.choices)
    label = models.CharField(max_length=240)
    uri = models.CharField(max_length=700, blank=True)
    document = models.ForeignKey(CandidateDocument, null=True, blank=True, on_delete=models.SET_NULL)
    link = models.ForeignKey(CandidateLink, null=True, blank=True, on_delete=models.SET_NULL)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.label


class ProfileClaim(models.Model):
    class Category(models.TextChoices):
        IDENTITY = "identity", "Identity"
        CONTACT = "contact", "Contact"
        SKILL = "skill", "Skill"
        EXPERIENCE = "experience", "Experience"
        DOMAIN = "domain", "Domain"
        EDUCATION = "education", "Education"
        PROJECT = "project", "Project"
        LINK = "link", "Link"
        EVIDENCE_NOTE = "evidence_note", "Evidence Note"

    class Status(models.TextChoices):
        EXTRACTED = "extracted", "Extracted"
        EVIDENCE_BACKED = "evidence_backed", "Evidence Backed"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="claims")
    source = models.ForeignKey(EvidenceSource, null=True, blank=True, on_delete=models.SET_NULL, related_name="claims")
    category = models.CharField(max_length=40, choices=Category.choices)
    value = models.TextField()
    normalized_value = models.CharField(max_length=260, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    evidence_text = models.TextField(blank=True)
    confidence = models.PositiveSmallIntegerField(default=80)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.EXTRACTED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "category", "normalized_value")
        indexes = [
            models.Index(fields=["profile", "category", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.normalized_value:
            self.normalized_value = normalize_claim(self.value)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_category_display()}: {self.value[:80]}"


class CandidatePreference(models.Model):
    profile = models.OneToOneField(CandidateProfile, on_delete=models.CASCADE, related_name="preferences")
    target_roles = models.JSONField(default=list, blank=True)
    target_locations = models.JSONField(default=list, blank=True)
    remote_preferences = models.JSONField(default=list, blank=True)
    salary_range = models.CharField(max_length=160, blank=True)
    experience_level = models.CharField(max_length=120, blank=True)
    work_authorization = models.CharField(max_length=240, blank=True)
    availability = models.CharField(max_length=160, blank=True)
    blocked_companies = models.JSONField(default=list, blank=True)
    must_have_skills = models.JSONField(default=list, blank=True)
    generated_queries = models.JSONField(default=list, blank=True)
    auto_submit_enabled = models.BooleanField(default=False)
    resume_source = models.CharField(max_length=40, default="claims")
    min_match_score = models.PositiveSmallIntegerField(default=60)
    min_match_confidence = models.PositiveSmallIntegerField(default=50)
    job_freshness_hours = models.PositiveSmallIntegerField(default=24)
    discovery_sources = models.JSONField(default=list, blank=True)
    resume_theme = models.CharField(max_length=40, default="modern_sans")
    resume_font_size = models.FloatField(default=10.5)
    resume_line_height = models.FloatField(default=1.35)
    resume_margin_top = models.FloatField(default=0.75)
    resume_margin_bottom = models.FloatField(default=0.75)
    resume_margin_left = models.FloatField(default=0.75)
    resume_margin_right = models.FloatField(default=0.75)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_queries(self):
        roles = clean_json_list(self.target_roles)
        locations = clean_json_list(self.target_locations)
        queries = []
        if roles and locations:
            for role in roles:
                for location in locations:
                    queries.append(f"{role} {location}")
        else:
            queries = roles[:]
        if not queries and self.profile:
            skills = [
                claim.value
                for claim in self.profile.claims.filter(
                    category=ProfileClaim.Category.SKILL,
                    status__in=[ProfileClaim.Status.EVIDENCE_BACKED, ProfileClaim.Status.CONFIRMED],
                )[:5]
            ]
            queries = skills
        self.generated_queries = clean_json_list(queries)
        return self.generated_queries

    def to_storage_dict(self):
        if not self.generated_queries:
            self.generate_queries()
        return {
            "target_roles": clean_json_list(self.target_roles),
            "locations": clean_json_list(self.target_locations),
            "remote_preferences": clean_json_list(self.remote_preferences),
            "min_salary": self.salary_range,
            "experience_level": self.experience_level,
            "visa_status": self.work_authorization,
            "blocked_companies": clean_json_list(self.blocked_companies),
            "must_have_skills": clean_json_list(self.must_have_skills),
            "generated_queries": clean_json_list(self.generated_queries),
            "auto_submit_enabled": self.auto_submit_enabled,
            "resume_source": self.resume_source,
            "min_match_score": self.min_match_score,
            "min_match_confidence": self.min_match_confidence,
            "job_freshness_hours": self.job_freshness_hours,
            "discovery_sources": clean_json_list(self.discovery_sources),
            "resume_theme": self.resume_theme,
            "resume_font_size": self.resume_font_size,
            "resume_line_height": self.resume_line_height,
            "resume_margin_top": self.resume_margin_top,
            "resume_margin_bottom": self.resume_margin_bottom,
            "resume_margin_left": self.resume_margin_left,
            "resume_margin_right": self.resume_margin_right,
        }

    def __str__(self):
        return f"Preferences for {self.profile}"


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCRAPED = "scraped", "Scraped"
        LOW_MATCH = "low_match", "Low Match"
        MATCHED = "matched", "Matched"
        KIT_GENERATED = "kit_generated", "Kit Generated"
        SUBMITTED = "submitted", "Submitted"
        FAILED = "failed", "Failed"
        AUTO_APPLIED = "auto_applied", "Auto Applied"
        MANUAL_REQUIRED = "manual_required", "Manual Required"

    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="applications", null=True)
    job_url = models.URLField(max_length=500, blank=True, null=True)
    job_description = models.TextField()
    match_score = models.PositiveSmallIntegerField(null=True, blank=True)
    match_summary = models.TextField(blank=True)
    matching_skills = models.JSONField(default=list, blank=True)
    missing_skills = models.JSONField(default=list, blank=True)
    tailored_resume = models.JSONField(null=True, blank=True)
    cover_letter = models.TextField(null=True, blank=True)
    recruiter_message = models.TextField(blank=True)
    follow_up_message = models.TextField(blank=True)
    interview_prep_notes = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    tailored_resume_pdf = models.CharField(max_length=500, blank=True, null=True)
    screenshot = models.CharField(max_length=500, blank=True, null=True)
    profile_snapshot = models.JSONField(null=True, blank=True)
    ai_metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    submitted = models.BooleanField(default=False)
    date_submitted = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    source_lead = models.ForeignKey(
        "JobLead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["submitted", "-created_at"]),
        ]

    def record_match(self, match_data, profile_snapshot=None, ai_metadata=None, thresholds=None):
        from .match_policy import classify_application_status, default_thresholds

        self.match_score = match_data.get("match_score")
        self.match_summary = match_data.get("summary", "")
        self.matching_skills = match_data.get("matching_skills", [])
        self.missing_skills = match_data.get("missing_skills", [])
        active_thresholds = thresholds or default_thresholds()
        self.status = classify_application_status(
            self.match_score,
            match_data.get("confidence"),
            active_thresholds,
        )
        self.error_message = ""
        if profile_snapshot is not None:
            self.profile_snapshot = profile_snapshot
        self.ai_metadata = {
            **(self.ai_metadata or {}),
            "match_confidence": match_data.get("confidence"),
            "match_risk_flags": match_data.get("risk_flags", []),
            "match_hard_filters": match_data.get("hard_filters", []),
            "why_apply": match_data.get("why_apply", ""),
            "salary_signal": match_data.get("salary_signal", ""),
            "seniority_alignment": match_data.get("seniority_alignment", ""),
        }
        safe_metadata = safe_json_dict(ai_metadata)
        if safe_metadata:
            self.ai_metadata["match_llm"] = safe_metadata
        self.save(
            update_fields=[
                "profile",
                "match_score",
                "match_summary",
                "matching_skills",
                "missing_skills",
                "status",
                "error_message",
                "profile_snapshot",
                "ai_metadata",
                "updated_at",
            ]
        )

    def record_kit(self, kit_data):
        self.tailored_resume = kit_data.get("tailored_resume")
        self.cover_letter = kit_data.get("cover_letter")
        self.recruiter_message = kit_data.get("recruiter_message", "")
        self.follow_up_message = kit_data.get("follow_up_message", "")
        self.interview_prep_notes = kit_data.get("interview_prep_notes", [])
        self.status = self.Status.KIT_GENERATED
        self.error_message = ""
        self.save(
            update_fields=[
                "tailored_resume",
                "cover_letter",
                "recruiter_message",
                "follow_up_message",
                "interview_prep_notes",
                "status",
                "error_message",
                "updated_at",
            ]
        )

    def record_failure(self, message):
        self.status = self.Status.FAILED
        self.error_message = str(message)
        self.save(update_fields=["status", "error_message", "updated_at"])

    def mark_submitted(self):
        self.submitted = True
        self.date_submitted = timezone.now()
        self.status = self.Status.SUBMITTED
        self.save(update_fields=["submitted", "date_submitted", "status", "updated_at"])

    def __str__(self):
        label = self.job_url or self.job_description[:50] or "Untitled application"
        return f"App for {label[:50]} ({self.get_status_display()})"


class JobLead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        SCORED = "scored", "Scored"
        MATCHED = "matched", "Matched"
        LOW_MATCH = "low_match", "Low Match"
        DISMISSED = "dismissed", "Dismissed"
        KIT_READY = "kit_ready", "Kit Ready"
        APPLIED = "applied", "Applied"
        FAILED = "failed", "Failed"

    matched_profile = models.ForeignKey(CandidateProfile, on_delete=models.SET_NULL, related_name="matched_leads", null=True, blank=True)
    source_type = models.CharField(max_length=60, default="manual", db_index=True)
    source_name = models.CharField(max_length=120, blank=True)
    external_id = models.CharField(max_length=200, blank=True)
    job_url = models.URLField(max_length=700, blank=True, null=True)
    title = models.CharField(max_length=240, blank=True)
    company = models.CharField(max_length=240, blank=True)
    location = models.CharField(max_length=240, blank=True)
    remote_type = models.CharField(max_length=60, blank=True)
    salary_text = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    match_score = models.PositiveSmallIntegerField(null=True, blank=True)
    match_summary = models.TextField(blank=True)
    ai_metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "-discovered_at"]),
            models.Index(fields=["source_type", "-discovered_at"]),
            models.Index(fields=["company", "title"]),
        ]

    @staticmethod
    def make_fingerprint(job_url="", title="", company="", location="") -> str:
        if job_url:
            basis = f"url:{job_url.strip().lower()}"
        else:
            basis = "|".join(
                [
                    title.strip().lower(),
                    company.strip().lower(),
                    location.strip().lower(),
                ]
            )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if not self.fingerprint:
            self.fingerprint = self.make_fingerprint(
                self.job_url or "",
                self.title,
                self.company,
                self.location,
            )
        super().save(*args, **kwargs)

    def record_score(self, match_data, ai_metadata=None, thresholds=None):
        from .match_policy import classify_lead_status, default_thresholds

        self.match_score = match_data.get("match_score")
        self.match_summary = match_data.get("summary", "")
        active_thresholds = thresholds or default_thresholds()
        self.status = classify_lead_status(
            self.match_score,
            match_data.get("confidence"),
            active_thresholds,
        )
        self.error_message = ""
        self.ai_metadata = {
            **(self.ai_metadata or {}),
            "match": match_data,
        }
        safe_metadata = safe_json_dict(ai_metadata)
        if safe_metadata:
            self.ai_metadata["match_llm"] = safe_metadata
        self.save(update_fields=["matched_profile", "match_score", "match_summary", "status", "error_message", "ai_metadata", "updated_at"])

    def dismiss(self):
        self.status = self.Status.DISMISSED
        self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        label = self.title or self.job_url or "Untitled lead"
        company = f" at {self.company}" if self.company else ""
        return f"{label[:80]}{company}"


class JobSourceRun(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    source_type = models.CharField(max_length=60, db_index=True)
    source_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.STARTED,
        db_index=True,
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    discovered_count = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def finish(self, discovered_count=0, imported_count=0):
        self.status = self.Status.COMPLETED
        self.finished_at = timezone.now()
        self.discovered_count = discovered_count
        self.imported_count = imported_count
        self.save(update_fields=["status", "finished_at", "discovered_count", "imported_count"])

    def fail(self, exc):
        self.status = self.Status.FAILED
        self.finished_at = timezone.now()
        self.error_message = str(exc)
        self.save(update_fields=["status", "finished_at", "error_message"])


class NotificationEvent(models.Model):
    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        DISCORD = "discord", "Discord"
        EMAIL = "email", "Email"
        WEBHOOK = "webhook", "Webhook"
        WEB = "web", "Web"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    channel = models.CharField(max_length=20, choices=Channel.choices)
    event_type = models.CharField(max_length=80)
    recipient = models.CharField(max_length=160, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=["status", "sent_at", "error_message"])

    def mark_failed(self, exc):
        self.status = self.Status.FAILED
        self.error_message = str(exc)
        self.save(update_fields=["status", "error_message"])


class PipelineJob(models.Model):
    class Kind(models.TextChoices):
        DISCOVERY = "discovery", "Discovery"
        SCORE = "score", "Score Leads"
        BULK_KIT = "bulk_kit", "Bulk Kit Generation"
        GENERATE_KIT = "generate_kit", "Generate Kit"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    idempotency_key = models.CharField(max_length=48, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=240, blank=True)
    result = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["kind", "status", "-created_at"]),
        ]

    @property
    def progress_percent(self) -> int:
        if not self.progress_total:
            return 0
        return min(100, int(100 * self.progress_current / self.progress_total))


class LLMUsageEvent(models.Model):
    task_type = models.CharField(max_length=40, db_index=True)
    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=80, blank=True)
    token_usage = models.JSONField(default=dict, blank=True)
    estimated_cost_usd = models.FloatField(default=0)
    related_type = models.CharField(max_length=40, blank=True)
    related_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["task_type", "-created_at"]),
        ]


class SecureCredential(models.Model):
    name = models.CharField(max_length=120, unique=True, db_index=True)
    encrypted_value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_val(cls, name: str, default: str | None = None) -> str | None:
        try:
            cred = cls.objects.get(name=name)
            if not cred.encrypted_value:
                return default
            from .encryption import decrypt_value
            return decrypt_value(cred.encrypted_value)
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_val(cls, name: str, value: str):
        if not value:
            # Delete if empty/cleared
            cls.objects.filter(name=name).delete()
            return
        from .encryption import encrypt_value
        encrypted = encrypt_value(value)
        cls.objects.update_or_create(
            name=name,
            defaults={"encrypted_value": encrypted}
        )

    def __str__(self):
        return f"Secret: {self.name}"


class AgentRunLog(models.Model):
    class Status(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    job_lead = models.ForeignKey("JobLead", null=True, blank=True, on_delete=models.CASCADE, related_name="agent_logs")
    application = models.ForeignKey("Application", null=True, blank=True, on_delete=models.CASCADE, related_name="agent_logs")
    agent_name = models.CharField(max_length=80, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INFO, db_index=True)
    message = models.TextField()
    detail_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["agent_name", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.agent_name}][{self.get_status_display()}] {self.message[:60]}"


class CandidateQuestionAnswer(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name="qa_items")
    question_text = models.TextField()
    normalized_question = models.CharField(max_length=260, db_index=True)
    answer_text = models.TextField()
    category = models.CharField(max_length=80, default="general", db_index=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "normalized_question")

    def save(self, *args, **kwargs):
        if not self.normalized_question:
            self.normalized_question = normalize_claim(self.question_text)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Q: {self.question_text[:50]} -> A: {self.answer_text[:50]}"


class ProviderConfig(models.Model):
    class CreditStatus(models.TextChoices):
        OK = "ok", "OK"
        LOW = "low", "Low"
        EXHAUSTED = "exhausted", "Exhausted"
        UNKNOWN = "unknown", "Unknown"

    provider_name = models.CharField(max_length=80, unique=True, db_index=True)
    display_name = models.CharField(max_length=120)
    is_enabled = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveSmallIntegerField(default=0, db_index=True)
    api_key_name = models.CharField(max_length=80)
    base_url = models.URLField(max_length=500, blank=True)
    adapter_type = models.CharField(max_length=80, default="openai_compatible")
    credit_status = models.CharField(
        max_length=24,
        choices=CreditStatus.choices,
        default=CreditStatus.UNKNOWN,
        db_index=True,
    )
    estimated_balance_usd = models.FloatField(null=True, blank=True)
    last_balance_check = models.DateTimeField(null=True, blank=True)
    credit_exhausted_at = models.DateTimeField(null=True, blank=True)
    extra_headers = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    models = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["priority", "provider_name"]

    def __str__(self):
        return f"{self.display_name} ({self.provider_name})"

    def is_available(self) -> bool:
        if not self.is_enabled:
            return False
        if self.credit_status == self.CreditStatus.EXHAUSTED and self.credit_exhausted_at:
            elapsed = (timezone.now() - self.credit_exhausted_at).total_seconds()
            if elapsed < 3600:  # 1 hour cooldown
                return False
        return True

    def mark_credit_exhausted(self):
        self.credit_status = self.CreditStatus.EXHAUSTED
        self.credit_exhausted_at = timezone.now()
        self.save(update_fields=["credit_status", "credit_exhausted_at", "updated_at"])

    def mark_credit_ok(self, balance=None):
        self.credit_status = self.CreditStatus.OK
        self.credit_exhausted_at = None
        self.estimated_balance_usd = balance
        self.last_balance_check = timezone.now()
        self.save(
            update_fields=[
                "credit_status",
                "credit_exhausted_at",
                "estimated_balance_usd",
                "last_balance_check",
                "updated_at",
            ]
        )

    def cooldown_remaining(self) -> int:
        if self.credit_status == self.CreditStatus.EXHAUSTED and self.credit_exhausted_at:
            elapsed = (timezone.now() - self.credit_exhausted_at).total_seconds()
            return max(0, int(3600 - elapsed))
        return 0



