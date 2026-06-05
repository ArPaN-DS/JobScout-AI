from typing import Any

from django.db import transaction

from .models import (
    CandidateDocument,
    CandidateLink,
    CandidatePreference,
    CandidateProfile,
    EvidenceSource,
    ProfileClaim,
    clean_json_list,
)
from .schemas import MasterProfile, normalize_claim


def profile_exists() -> bool:
    return CandidateProfile.objects.filter(is_active=True).exists()


def get_active_candidate() -> CandidateProfile | None:
    return CandidateProfile.active()


def load_master_profile() -> MasterProfile:
    candidate = get_active_candidate()
    if not candidate:
        raise FileNotFoundError("Please set up your Candidate Profile first.")
    return candidate.to_master_profile()


@transaction.atomic
def save_master_profile(
    profile: MasterProfile,
    *,
    manual_data: dict[str, Any] | None = None,
    document_info: dict[str, Any] | None = None,
) -> CandidateProfile:
    CandidateProfile.objects.filter(is_active=True).update(is_active=False)

    storage = profile.to_storage_dict()
    candidate = CandidateProfile.objects.create(
        is_active=True,
        status=CandidateProfile.Status.REVIEW_REQUIRED,
        full_name=profile.name,
        email=profile.email,
        phone=profile.phone,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        extracted_profile=storage,
    )
    candidate.apply_manual_fields(manual_data or {})
    candidate.save()

    document = None
    source_type = EvidenceSource.SourceType.AI_EXTRACTION
    source_label = "AI profile extraction"
    if document_info:
        document = CandidateDocument.objects.create(
            profile=candidate,
            document_type=document_info.get("document_type") or CandidateDocument.DocumentType.RESUME,
            original_filename=document_info.get("original_filename") or "uploaded-document",
            content_type=document_info.get("content_type") or "",
            size_bytes=document_info.get("size_bytes") or 0,
            status=CandidateDocument.Status.EXTRACTED,
            extracted_text_sample=document_info.get("extracted_text_sample") or "",
            extracted_data=storage,
        )
        source_type = (
            EvidenceSource.SourceType.RESUME_UPLOAD
            if document.document_type == CandidateDocument.DocumentType.RESUME
            else EvidenceSource.SourceType.DOCUMENT_UPLOAD
        )
        source_label = document.original_filename

    source = EvidenceSource.objects.create(
        profile=candidate,
        source_type=source_type,
        label=source_label,
        document=document,
        metadata={"origin": "profile_upload"},
    )
    _sync_links(candidate)
    _sync_preferences(candidate, storage.get("job_preferences") or {})
    _create_claims_from_profile(candidate, profile, source)
    return candidate


def update_candidate_links(candidate: CandidateProfile, data: dict[str, Any]) -> None:
    candidate.apply_manual_fields(data)
    candidate.save()
    _sync_links(candidate)


def update_candidate_preferences(candidate: CandidateProfile, data: dict[str, Any]) -> CandidatePreference:
    preferences = _sync_preferences(candidate, data)
    preferences.generate_queries()
    preferences.save(update_fields=["generated_queries", "updated_at"])
    return preferences


def confirm_claims(candidate: CandidateProfile, claim_ids: list[int] | None = None) -> int:
    queryset = candidate.claims.exclude(status=ProfileClaim.Status.REJECTED)
    if claim_ids is not None:
        queryset = queryset.filter(id__in=claim_ids)
    return queryset.update(status=ProfileClaim.Status.CONFIRMED)


def reject_claims(candidate: CandidateProfile, claim_ids: list[int]) -> int:
    if not claim_ids:
        return 0
    return candidate.claims.filter(id__in=claim_ids).update(status=ProfileClaim.Status.REJECTED)


def _sync_links(candidate: CandidateProfile) -> None:
    link_values = [
        (CandidateLink.LinkType.LINKEDIN, candidate.linkedin_url, "LinkedIn"),
        (CandidateLink.LinkType.GITHUB, candidate.github_url, "GitHub"),
        (CandidateLink.LinkType.PORTFOLIO, candidate.portfolio_url, "Portfolio"),
    ]
    for link_type, url, label in link_values:
        if not url:
            continue
        link, _ = CandidateLink.objects.get_or_create(
            profile=candidate,
            link_type=link_type,
            url=url,
            defaults={"label": label},
        )
        EvidenceSource.objects.get_or_create(
            profile=candidate,
            source_type=EvidenceSource.SourceType.LINK,
            label=label,
            uri=url,
            link=link,
        )


def _sync_preferences(candidate: CandidateProfile, data: dict[str, Any]) -> CandidatePreference:
    preferences, _ = CandidatePreference.objects.get_or_create(profile=candidate)
    preferences.target_roles = _read_list(data, "target_roles")
    preferences.target_locations = _read_list(data, "target_locations", "locations")
    preferences.remote_preferences = _read_list(data, "remote_preferences")
    preferences.salary_range = str(data.get("salary_range") or data.get("min_salary") or "").strip()
    preferences.experience_level = str(data.get("experience_level") or "").strip()
    preferences.work_authorization = str(data.get("work_authorization") or data.get("visa_status") or "").strip()
    preferences.availability = str(data.get("availability") or "").strip()
    preferences.blocked_companies = _read_list(data, "blocked_companies")
    preferences.must_have_skills = _read_list(data, "must_have_skills")
    preferences.auto_submit_enabled = bool(data.get("auto_submit_enabled") or data.get("auto_submit") or False)
    preferences.resume_source = str(data.get("resume_source") or "claims").strip()
    if data.get("min_match_score") not in (None, ""):
        preferences.min_match_score = _read_int(data.get("min_match_score"), preferences.min_match_score)
    if data.get("min_match_confidence") not in (None, ""):
        preferences.min_match_confidence = _read_int(
            data.get("min_match_confidence"),
            preferences.min_match_confidence,
        )
    if data.get("job_freshness_hours") not in (None, ""):
        preferences.job_freshness_hours = _read_int(
            data.get("job_freshness_hours"),
            preferences.job_freshness_hours,
        )
    if data.get("discovery_sources"):
        preferences.discovery_sources = _read_list(data, "discovery_sources")
        
    # PDF resume styling sync
    preferences.resume_theme = str(data.get("resume_theme") or "modern_sans").strip()
    if data.get("resume_font_size") not in (None, ""):
        try: preferences.resume_font_size = float(data.get("resume_font_size"))
        except (TypeError, ValueError): pass
    if data.get("resume_line_height") not in (None, ""):
        try: preferences.resume_line_height = float(data.get("resume_line_height"))
        except (TypeError, ValueError): pass
    if data.get("resume_margin_top") not in (None, ""):
        try: preferences.resume_margin_top = float(data.get("resume_margin_top"))
        except (TypeError, ValueError): pass
    if data.get("resume_margin_bottom") not in (None, ""):
        try: preferences.resume_margin_bottom = float(data.get("resume_margin_bottom"))
        except (TypeError, ValueError): pass
    if data.get("resume_margin_left") not in (None, ""):
        try: preferences.resume_margin_left = float(data.get("resume_margin_left"))
        except (TypeError, ValueError): pass
    if data.get("resume_margin_right") not in (None, ""):
        try: preferences.resume_margin_right = float(data.get("resume_margin_right"))
        except (TypeError, ValueError): pass
        
    preferences.generate_queries()
    preferences.save()
    return preferences



def _read_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, parsed))


def _read_list(data: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            return clean_json_list([item.strip() for item in value.split(",")])
        if isinstance(value, list):
            return clean_json_list(value)
    return []


def _create_claims_from_profile(candidate: CandidateProfile, profile: MasterProfile, source: EvidenceSource) -> None:
    for skill in profile.skills:
        _upsert_claim(candidate, source, ProfileClaim.Category.SKILL, skill)
    for domain in profile.domains:
        _upsert_claim(candidate, source, ProfileClaim.Category.DOMAIN, domain)
    for note in profile.evidence_notes:
        _upsert_claim(candidate, source, ProfileClaim.Category.EVIDENCE_NOTE, note)
    for item in profile.experience:
        value = " ".join(part for part in [item.role, item.company, item.duration] if part).strip()
        evidence = "; ".join(item.evidence or item.highlights)
        _upsert_claim(
            candidate,
            source,
            ProfileClaim.Category.EXPERIENCE,
            value or item.company or item.role,
            data=item.model_dump(mode="json"),
            evidence_text=evidence,
        )
    for label, value in [
        ("name", profile.name),
        ("email", profile.email),
        ("phone", profile.phone),
        ("linkedin_url", profile.linkedin_url),
        ("github_url", profile.github_url),
    ]:
        if value:
            _upsert_claim(
                candidate,
                source,
                ProfileClaim.Category.CONTACT if label in {"email", "phone"} else ProfileClaim.Category.IDENTITY,
                value,
                data={"field": label},
            )


def _upsert_claim(
    candidate: CandidateProfile,
    source: EvidenceSource,
    category: str,
    value: str,
    *,
    data: dict[str, Any] | None = None,
    evidence_text: str = "",
) -> None:
    text = str(value or "").strip()
    if not text:
        return
    ProfileClaim.objects.update_or_create(
        profile=candidate,
        category=category,
        normalized_value=normalize_claim(text),
        defaults={
            "source": source,
            "value": text,
            "data": data or {},
            "evidence_text": evidence_text,
            "status": ProfileClaim.Status.EVIDENCE_BACKED,
        },
    )
