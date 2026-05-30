import json
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Any, TypeVar

import pdfplumber
from django.conf import settings
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from .llm import LLMExhaustedError, LLMRequest, LLMResult, LLMRouter, LLMTask
from .schemas import ApplicationKit, BaseJobExtraction, MasterProfile, MatchResult, validate_grounded_kit

load_dotenv()

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class AIResponseError(ValueError):
    pass


class CareerAgentAI:
    def __init__(
        self,
        api_key: str | None = None,
        flash_model: str | None = None,
        pro_model: str | None = None,
        max_attempts: int = 2,
        router: LLMRouter | None = None,
    ) -> None:
        self.api_key = api_key
        self.flash_model = flash_model or getattr(settings, "GEMINI_FLASH_MODEL", "gemini-2.5-flash")
        self.pro_model = pro_model or getattr(settings, "GEMINI_PRO_MODEL", "gemini-2.5-pro")
        self.max_attempts = max_attempts
        self.router = router or LLMRouter()
        self.last_result: LLMResult | None = None

    def extract_profile_from_document(self, document_path: str | Path) -> MasterProfile:
        resume_text = extract_document_text(document_path)
        prompt = f"""
You are a careful technical recruiter. Extract the candidate profile from the resume text.

Rules:
- Return JSON only.
- Do not invent missing fields.
- Preserve exact company names, role titles, durations, skills, and experience highlights from the resume.
- Keep skills atomic, for example "Python" instead of "Python and Django".

JSON shape:
{{
  "name": "Full Name",
  "email": "Email Address",
  "phone": "Phone Number",
  "skills": ["Skill"],
  "experience": [
    {{
      "company": "Company Name",
      "role": "Job Title",
      "duration": "Start - End Date",
      "highlights": ["Evidence-backed resume bullet"],
      "evidence": ["Short quote or resume fact supporting the highlight"]
    }}
  ],
  "domains": ["Domain"],
  "job_preferences": {{
    "target_roles": [],
    "locations": [],
    "remote_preferences": [],
    "min_salary": "",
    "experience_level": "",
    "visa_status": "",
    "blocked_companies": [],
    "must_have_skills": []
  }},
  "evidence_notes": ["Important source facts from the resume"]
}}

Resume text:
{resume_text}
"""
        return self._generate_json(
            task=LLMTask.PROFILE_EXTRACT,
            prompt=prompt,
            schema=MasterProfile,
            temperature=0.1,
            purpose="profile extraction",
        )

    def extract_profile_from_pdf(self, pdf_path: str | Path) -> MasterProfile:
        return self.extract_profile_from_document(pdf_path)

    def match_job_to_profile(self, master_profile: dict[str, Any] | MasterProfile, job_description: str) -> MatchResult:
        profile = ensure_profile(master_profile)
        prompt = f"""
You are a conservative recruiting analyst. Compare the candidate profile with the job description.

Accuracy rules:
- Score only skills and experience explicitly present in the candidate profile.
- Do not give credit for adjacent or implied skills unless the profile states them directly.
- Put uncertain or weak evidence in risk_flags.
- Respect job_preferences as hard filters when the job conflicts with them.
- Keep the summary factual and concise.

JSON shape:
{{
  "match_score": 0,
  "summary": "Two factual sentences.",
  "matching_skills": ["Skill found in both job and profile"],
  "missing_skills": ["Important job skill not found in profile"],
  "confidence": 0,
  "risk_flags": ["Reason this match may be weaker than the score suggests"],
  "hard_filters": ["Deal-breaker mismatch, if any"],
  "why_apply": "One practical reason this role is worth applying to.",
  "salary_signal": "Salary or compensation signal if present.",
  "seniority_alignment": "How the role level aligns with the profile."
}}

Candidate profile JSON:
{json.dumps(profile.to_storage_dict(), ensure_ascii=False)}

Job description:
{job_description.strip()}
"""
        return self._generate_json(
            task=LLMTask.JOB_MATCH,
            prompt=prompt,
            schema=MatchResult,
            temperature=0.1,
            purpose="job match",
        )

    def generate_application_kit(
        self,
        master_profile: dict[str, Any] | MasterProfile,
        job_description: str,
    ) -> ApplicationKit:
        profile = ensure_profile(master_profile)
        prompt = f"""
You are a strict resume tailoring assistant. Build a targeted application kit.

Grounding rules:
- Use only facts present in the candidate profile JSON.
- Use exact skill strings from candidate_profile.skills. Do not create new skill names.
- Use exact company, role, and duration values from candidate_profile.experience.
- You may rephrase existing highlights for clarity, but you may not add new tools, metrics, employers, dates, or outcomes.
- If the job asks for a missing skill, do not include it in the resume.

JSON shape:
{{
  "tailored_resume": {{
    "name": "Candidate Name",
    "skills": ["Exact skill from candidate_profile.skills"],
    "experience": [
      {{
        "company": "Exact company from profile",
        "role": "Exact role from profile",
        "duration": "Exact duration from profile",
        "highlights": ["Rephrased but evidence-backed highlight"]
      }}
    ]
  }},
  "cover_letter": "Professional 3-paragraph cover letter grounded only in profile facts.",
  "recruiter_message": "Short LinkedIn or email message grounded only in profile facts.",
  "follow_up_message": "Short follow-up message after applying.",
  "interview_prep_notes": ["Concrete interview prep note based on job and profile"]
}}

Candidate profile JSON:
{json.dumps(profile.to_storage_dict(), ensure_ascii=False)}

Job description:
{job_description.strip()}
"""
        kit = self._generate_json(
            task=LLMTask.APPLICATION_KIT,
            prompt=prompt,
            schema=ApplicationKit,
            temperature=0.2,
            purpose="application kit generation",
        )
        validate_grounded_kit(profile, kit)
        return kit

    def last_metadata(self) -> dict[str, Any]:
        if not self.last_result:
            return {}
        return self.last_result.metadata()

    def _generate_json(
        self,
        task: LLMTask,
        prompt: str,
        schema: type[SchemaT],
        temperature: float,
        purpose: str,
    ) -> SchemaT:
        last_error: Exception | None = None
        current_prompt = prompt
        blocked_providers: set[str] = set()

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = self.router.generate(
                    LLMRequest(
                        task=task,
                        prompt=current_prompt,
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                    blocked_providers=blocked_providers,
                )
            except LLMExhaustedError as exc:
                raise AIResponseError(str(exc)) from exc

            self.last_result = result
            raw_text = result.text.strip()
            try:
                parsed = extract_json_object(raw_text)
                return schema.model_validate(parsed)
            except (JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                blocked_providers.add(result.provider)
                if attempt < self.max_attempts:
                    current_prompt = (
                        prompt
                        + "\n\nYour previous response failed validation. "
                        + f"Validation error: {exc}. Return corrected JSON only."
                    )
                    time.sleep(0.6 * attempt)

        provider = self.last_result.provider if self.last_result else "unknown provider"
        raise AIResponseError(f"{provider} {purpose} failed schema validation: {last_error}")

    def extract_job_from_text(self, raw_text: str, source_url: str = "") -> dict[str, Any]:
        prompt = f"""
Extract a job lead from the text below.

Rules:
- Return JSON only.
- Do not invent missing fields.
- Keep title, company, location, salary_text, and remote_type concise.

JSON shape:
{{
  "title": "Role title",
  "company": "Company",
  "location": "Location",
  "remote_type": "remote, hybrid, onsite, or unknown",
  "salary_text": "Salary text if present",
  "job_url": "URL if present",
  "description": "Cleaned full job description"
}}

Source URL:
{source_url}

Raw text:
{raw_text.strip()}
"""
        result = self._generate_json(
            task=LLMTask.JOB_EXTRACT,
            prompt=prompt,
            schema=BaseJobExtraction,
            temperature=0.1,
            purpose="job extraction",
        )
        return result.model_dump(mode="json")


def ensure_profile(profile: dict[str, Any] | MasterProfile) -> MasterProfile:
    if isinstance(profile, MasterProfile):
        return profile
    return MasterProfile.model_validate(profile)


def extract_pdf_text(pdf_path: str | Path) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError("Could not extract text from the provided PDF.")
    return text


def extract_docx_text(docx_path: str | Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError("DOCX support requires python-docx. Install requirements.txt first.") from exc

    document = Document(docx_path)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text).strip()
    if not text:
        raise ValueError("Could not extract text from the provided DOCX.")
    return text


def extract_document_text(document_path: str | Path) -> str:
    path = Path(document_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix == ".docx":
        return extract_docx_text(path)
    raise ValueError("Unsupported document type. Upload a PDF or DOCX file.")


def extract_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[index:])
                break
            except JSONDecodeError:
                continue
        else:
            raise

    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from the AI response.")
    return parsed
