"""Profile readiness checks before high-cost AI workflows."""

from __future__ import annotations

from dataclasses import dataclass

from .models import CandidateProfile, ProfileClaim


@dataclass
class ReadinessItem:
    key: str
    label: str
    complete: bool
    detail: str = ""


@dataclass
class ProfileReadiness:
    ready: bool
    status: str
    items: list[ReadinessItem]
    blockers: list[str]

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "status": self.status,
            "items": [
                {"key": item.key, "label": item.label, "complete": item.complete, "detail": item.detail}
                for item in self.items
            ],
            "blockers": self.blockers,
        }


def assess_profile_readiness(candidate: CandidateProfile | None) -> ProfileReadiness:
    if candidate is None:
        return ProfileReadiness(
            ready=False,
            status="missing",
            items=[],
            blockers=["Create a candidate profile first."],
        )

    backed_skills = candidate.claims.filter(
        category=ProfileClaim.Category.SKILL,
        status__in=[ProfileClaim.Status.EVIDENCE_BACKED, ProfileClaim.Status.CONFIRMED],
    ).count()
    has_contact = bool(candidate.email or candidate.phone)
    has_document = candidate.documents.exists()
    preferences = getattr(candidate, "preferences", None)
    has_roles = bool(preferences and preferences.target_roles)
    has_locations = bool(preferences and preferences.target_locations)
    pending_claims = candidate.claims.exclude(
        status__in=[ProfileClaim.Status.CONFIRMED, ProfileClaim.Status.REJECTED]
    ).count()
    status_ready = candidate.status == CandidateProfile.Status.READY

    items = [
        ReadinessItem("document", "Resume or document uploaded", has_document),
        ReadinessItem("contact", "Contact email or phone set", has_contact),
        ReadinessItem("skills", "At least 3 evidence-backed skills", backed_skills >= 3, f"{backed_skills} skills"),
        ReadinessItem("roles", "Target roles configured", has_roles),
        ReadinessItem("locations", "Target locations configured", has_locations),
        ReadinessItem("review", "Claims reviewed and profile marked ready", status_ready),
        ReadinessItem(
            "claims_pending",
            "No pending claims awaiting review",
            pending_claims == 0,
            f"{pending_claims} pending" if pending_claims else "",
        ),
    ]

    blockers = [item.label for item in items if not item.complete]
    ready = not blockers

    return ProfileReadiness(
        ready=ready,
        status=candidate.status,
        items=items,
        blockers=blockers,
    )


def assert_ready_for_kit_generation(candidate: CandidateProfile | None) -> None:
    readiness = assess_profile_readiness(candidate)
    if readiness.ready:
        return
    raise ValueError(
        "Profile is not ready for kit generation. Complete: " + "; ".join(readiness.blockers[:4])
        + ("." if len(readiness.blockers) <= 4 else "; ")
    )
