"""Central match threshold resolution for leads and applications."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .models import CandidatePreference, CandidateProfile


@dataclass(frozen=True)
class MatchThresholds:
    min_match_score: int
    min_match_confidence: int

    def is_strong_match(self, match_score: int | None, confidence: int | None) -> bool:
        if match_score is None:
            return False
        score_ok = match_score >= self.min_match_score
        confidence_value = 0 if confidence is None else confidence
        return score_ok and confidence_value >= self.min_match_confidence


def default_thresholds() -> MatchThresholds:
    return MatchThresholds(
        min_match_score=int(getattr(settings, "DEFAULT_MIN_MATCH_SCORE", 60)),
        min_match_confidence=int(getattr(settings, "DEFAULT_MIN_MATCH_CONFIDENCE", 50)),
    )


def thresholds_for_candidate(candidate: CandidateProfile | None) -> MatchThresholds:
    if candidate is None:
        return default_thresholds()
    preferences = getattr(candidate, "preferences", None)
    if preferences is None:
        try:
            preferences = candidate.preferences
        except CandidatePreference.DoesNotExist:
            return default_thresholds()
    return MatchThresholds(
        min_match_score=preferences.min_match_score,
        min_match_confidence=preferences.min_match_confidence,
    )


def classify_lead_status(match_score: int | None, confidence: int | None, thresholds: MatchThresholds) -> str:
    from .models import JobLead

    if thresholds.is_strong_match(match_score, confidence):
        return JobLead.Status.MATCHED
    return JobLead.Status.LOW_MATCH


def classify_application_status(match_score: int | None, confidence: int | None, thresholds: MatchThresholds) -> str:
    from .models import Application

    if thresholds.is_strong_match(match_score, confidence):
        return Application.Status.MATCHED
    return Application.Status.LOW_MATCH
