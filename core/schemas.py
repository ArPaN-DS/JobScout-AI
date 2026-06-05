import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_claim(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def clean_list(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean_text(value)
        key = normalize_claim(item)
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


class ExperienceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str = ""
    role: str = ""
    duration: str = ""
    highlights: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)

    @field_validator("company", "role", "duration", mode="before")
    @classmethod
    def _clean_string(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("highlights", "evidence", mode="before")
    @classmethod
    def _clean_highlights(cls, value: Any) -> list[str]:
        return clean_list(value)


class JobPreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_preferences: list[str] = Field(default_factory=list)
    min_salary: str = ""
    experience_level: str = ""
    visa_status: str = ""
    blocked_companies: list[str] = Field(default_factory=list)
    must_have_skills: list[str] = Field(default_factory=list)

    @field_validator("min_salary", "experience_level", "visa_status", mode="before")
    @classmethod
    def _clean_string(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator(
        "target_roles",
        "locations",
        "remote_preferences",
        "blocked_companies",
        "must_have_skills",
        mode="before",
    )
    @classmethod
    def _clean_lists(cls, value: Any) -> list[str]:
        return clean_list(value)


class MasterProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    email: str = ""
    phone: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    linkedin_url: str = ""
    github_url: str = ""
    job_preferences: JobPreferences = Field(default_factory=JobPreferences)
    evidence_notes: list[str] = Field(default_factory=list)

    @field_validator("name", "email", "phone", "linkedin_url", "github_url", mode="before")
    @classmethod
    def _clean_string(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("skills", "domains", "evidence_notes", mode="before")
    @classmethod
    def _clean_lists(cls, value: Any) -> list[str]:
        return clean_list(value)

    @field_validator("experience", mode="before")
    @classmethod
    def _clean_experience(cls, value: Any):
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        return value

    def known_skills(self) -> set[str]:
        return {normalize_claim(skill) for skill in self.skills}

    def known_experience_keys(self) -> set[tuple[str, str, str]]:
        return {
            (
                normalize_claim(item.company),
                normalize_claim(item.role),
                normalize_claim(item.duration),
            )
            for item in self.experience
        }

    def known_company_roles(self) -> set[tuple[str, str]]:
        return {
            (
                normalize_claim(item.company),
                normalize_claim(item.role),
            )
            for item in self.experience
        }

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    match_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    confidence: int = Field(default=70, ge=0, le=100)
    risk_flags: list[str] = Field(default_factory=list)
    hard_filters: list[str] = Field(default_factory=list)
    why_apply: str = ""
    salary_signal: str = ""
    seniority_alignment: str = ""

    @field_validator("summary", "why_apply", "salary_signal", "seniority_alignment", mode="before")
    @classmethod
    def _clean_summary(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("matching_skills", "missing_skills", "risk_flags", "hard_filters", mode="before")
    @classmethod
    def _clean_lists(cls, value: Any) -> list[str]:
        return clean_list(value)


class TailoredExperienceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str = ""
    role: str = ""
    duration: str = ""
    highlights: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("company", "role", "duration", mode="before")
    @classmethod
    def _clean_string(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("highlights", "evidence_refs", mode="before")
    @classmethod
    def _clean_highlights(cls, value: Any) -> list[str]:
        return clean_list(value)


class TailoredResume(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[TailoredExperienceItem] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("skills", mode="before")
    @classmethod
    def _clean_skills(cls, value: Any) -> list[str]:
        return clean_list(value)

    @field_validator("experience", mode="before")
    @classmethod
    def _clean_experience(cls, value: Any):
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        return value


class ApplicationKit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tailored_resume: TailoredResume
    cover_letter: str = Field(min_length=1)
    recruiter_message: str = ""
    follow_up_message: str = ""
    interview_prep_notes: list[str] = Field(default_factory=list)

    @field_validator("cover_letter", "recruiter_message", "follow_up_message", mode="before")
    @classmethod
    def _clean_cover_letter(cls, value: Any) -> str:
        return clean_text(value)

    @field_validator("interview_prep_notes", mode="before")
    @classmethod
    def _clean_notes(cls, value: Any) -> list[str]:
        return clean_list(value)


class AgentCriticIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "" # e.g. "hallucination", "missing_skill", "formatting", "tone"
    target: str = "" # e.g. "resume", "cover_letter", "general"
    fix_instruction: str = "" # specific prompt instruction for refinement

    @field_validator("type", "target", "fix_instruction", mode="before")
    @classmethod
    def _clean_strings(cls, value: Any) -> str:
        return clean_text(value)


class KitCriticVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    approved: bool = False
    issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    critic_issues: list[AgentCriticIssue] = Field(default_factory=list)

    @field_validator("issues", "unsupported_claims", mode="before")
    @classmethod
    def _clean_lists(cls, value: Any) -> list[str]:
        return clean_list(value)

    @field_validator("critic_issues", mode="before")
    @classmethod
    def _clean_critic_issues(cls, value: Any):
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        return value



class BaseJobExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    company: str = ""
    location: str = ""
    remote_type: str = ""
    salary_text: str = ""
    job_url: str = ""
    description: str = ""

    @field_validator(
        "title",
        "company",
        "location",
        "remote_type",
        "salary_text",
        "job_url",
        "description",
        mode="before",
    )
    @classmethod
    def _clean_string(cls, value: Any) -> str:
        return clean_text(value)


def validate_grounded_kit(profile: MasterProfile, kit: ApplicationKit) -> None:
    unsupported_skills = [
        skill
        for skill in kit.tailored_resume.skills
        if normalize_claim(skill) not in profile.known_skills()
    ]

    known_experiences = profile.known_experience_keys()
    known_company_roles = profile.known_company_roles()
    unsupported_experience = []
    for item in kit.tailored_resume.experience:
        key = (
            normalize_claim(item.company),
            normalize_claim(item.role),
            normalize_claim(item.duration),
        )
        company_role = (key[0], key[1])
        if key not in known_experiences and company_role not in known_company_roles:
            unsupported_experience.append(
                f"{item.role or 'Unknown role'} at {item.company or 'Unknown company'}"
            )

    if unsupported_skills or unsupported_experience:
        problems = []
        if unsupported_skills:
            problems.append("unsupported skills: " + ", ".join(unsupported_skills))
        if unsupported_experience:
            problems.append("unsupported experience entries: " + ", ".join(unsupported_experience))
        raise ValueError("Application kit contains claims not found in the candidate profile: " + "; ".join(problems))
