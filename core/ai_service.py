import json
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Any, TypeVar

import pdfplumber
from django.conf import settings
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from .cost_tracking import assert_within_budget, record_llm_usage
from .logging_utils import get_logger

logger = get_logger(__name__)
from .llm import LLMExhaustedError, LLMRequest, LLMResult, LLMRouter, LLMTask
from .prompts.registry import (
    PROMPT_VERSION,
    build_application_kit_prompt,
    build_critic_prompt,
    build_job_match_prompt,
    build_profile_extract_prompt,
)
from .schemas import (
    ApplicationKit,
    BaseJobExtraction,
    KitCriticVerdict,
    MasterProfile,
    MatchResult,
    validate_grounded_kit,
)

load_dotenv()

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class AIResponseError(ValueError):
    pass


class KitValidationError(AIResponseError):
    """Raised when deterministic or critic validation rejects a kit."""


class CareerAgentAI:
    def __init__(
        self,
        api_key: str | None = None,
        flash_model: str | None = None,
        pro_model: str | None = None,
        max_attempts: int = 2,
        router: LLMRouter | None = None,
        critic_enabled: bool | None = None,
    ) -> None:
        self.api_key = api_key
        self.flash_model = flash_model or getattr(settings, "GEMINI_FLASH_MODEL", "gemini-2.5-flash")
        self.pro_model = pro_model or getattr(settings, "GEMINI_PRO_MODEL", "gemini-2.5-pro")
        self.max_attempts = max_attempts
        self.router = router or LLMRouter()
        self.critic_enabled = (
            critic_enabled
            if critic_enabled is not None
            else getattr(settings, "KIT_CRITIC_ENABLED", True)
        )
        self.last_result: LLMResult | None = None
        self.last_prompt_version = PROMPT_VERSION
        self._run_extras: dict[str, Any] = {}

    def extract_profile_from_document(self, document_path: str | Path) -> MasterProfile:
        resume_text = extract_document_text(document_path)
        return self._generate_json(
            task=LLMTask.PROFILE_EXTRACT,
            prompt=build_profile_extract_prompt(resume_text),
            schema=MasterProfile,
            temperature=0.1,
            purpose="profile extraction",
        )

    def extract_profile_from_pdf(self, pdf_path: str | Path) -> MasterProfile:
        return self.extract_profile_from_document(pdf_path)

    def match_job_to_profile(
        self,
        master_profile: dict[str, Any] | MasterProfile,
        job_description: str,
        *,
        compact: bool = False,
    ) -> MatchResult:
        profile = ensure_profile(master_profile)
        description = _compact_text(job_description) if compact else job_description
        assert_within_budget(float(getattr(settings, "ESTIMATED_MATCH_COST_USD", 0.002)))
        result = self._generate_json(
            task=LLMTask.JOB_MATCH,
            prompt=build_job_match_prompt(profile.to_storage_dict(), description),
            schema=MatchResult,
            temperature=0.1,
            purpose="job match",
            job_description=description,
            rebuild_prompt_fn=lambda desc: build_job_match_prompt(profile.to_storage_dict(), desc),
        )
        record_llm_usage(self.last_metadata(), task_type="job_match")
        return result

    def generate_application_kit(
        self,
        master_profile: dict[str, Any] | MasterProfile,
        job_description: str,
        *,
        compact: bool = False,
    ) -> ApplicationKit:
        profile = ensure_profile(master_profile)
        description = _compact_text(job_description) if compact else job_description
        assert_within_budget(float(getattr(settings, "ESTIMATED_KIT_COST_USD", 0.02)))
        kit = self._generate_json(
            task=LLMTask.APPLICATION_KIT,
            prompt=build_application_kit_prompt(profile.to_storage_dict(), description),
            schema=ApplicationKit,
            temperature=0.2,
            purpose="application kit generation",
            job_description=description,
            rebuild_prompt_fn=lambda desc: build_application_kit_prompt(profile.to_storage_dict(), desc),
        )
        validate_grounded_kit(profile, kit)

        critic_metadata: dict[str, Any] = {"skipped": True}
        if self.critic_enabled:
            verdict = self.critic_validate_kit(profile, job_description, kit)
            critic_metadata = verdict.model_dump(mode="json")
            if not verdict.approved:
                issues = verdict.issues or verdict.unsupported_claims or ["Critic rejected the kit."]
                raise KitValidationError(
                    "Application kit failed critic validation: " + "; ".join(issues[:5])
                )

        self._run_extras = {
            "prompt_version": PROMPT_VERSION,
            "critic": critic_metadata,
            "compact": compact,
        }
        record_llm_usage(self.last_metadata(), task_type="application_kit")
        return kit

    def critic_validate_kit(
        self,
        master_profile: dict[str, Any] | MasterProfile,
        job_description: str,
        kit: ApplicationKit,
    ) -> KitCriticVerdict:
        profile = ensure_profile(master_profile)
        return self._generate_json(
            task=LLMTask.CRITIC_VALIDATE,
            prompt=build_critic_prompt(
                profile.to_storage_dict(),
                job_description,
                kit.model_dump(mode="json"),
            ),
            schema=KitCriticVerdict,
            temperature=0.0,
            purpose="kit critic validation",
            job_description=job_description,
            rebuild_prompt_fn=lambda desc: build_critic_prompt(
                profile.to_storage_dict(),
                desc,
                kit.model_dump(mode="json"),
            ),
        )

    def last_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {"prompt_version": self.last_prompt_version}
        if self.last_result:
            metadata.update(self.last_result.metadata())
        metadata.update(self._run_extras)
        return metadata

    def _generate_json(
        self,
        task: LLMTask,
        prompt: str,
        schema: type[SchemaT],
        temperature: float,
        purpose: str,
        job_description: str | None = None,
        rebuild_prompt_fn: Any | None = None,
        has_compacted: bool = False,
    ) -> SchemaT:
        last_error: Exception | None = None
        current_prompt = prompt
        blocked_providers: set[str] = set()

        for attempt in range(1, self.max_attempts + 1):
            try:
                router = self.router
                if attempt > 1:
                    from .llm import build_provider_chain, LLMRouter, GeminiAdapter
                    base_adapters = self.router.adapters or build_provider_chain(task)
                    promoted_adapters = []
                    for adapter in base_adapters:
                        if isinstance(adapter, GeminiAdapter):
                            promoted_adapters.append(GeminiAdapter(model=self.pro_model, api_key=adapter.api_key))
                        else:
                            promoted_adapters.append(adapter)
                    router = LLMRouter(adapters=promoted_adapters)

                result = router.generate(
                    LLMRequest(
                        task=task,
                        prompt=current_prompt,
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                    blocked_providers=blocked_providers,
                )
            except LLMExhaustedError as exc:
                from .resilience import classify_error, ErrorType
                is_context_limit = False
                if classify_error(exc) == ErrorType.CONTEXT_LIMIT_EXCEEDED:
                    is_context_limit = True
                else:
                    for att in exc.attempts:
                        if att.error:
                            if classify_error(Exception(att.error)) == ErrorType.CONTEXT_LIMIT_EXCEEDED:
                                is_context_limit = True
                                break

                if is_context_limit and job_description and rebuild_prompt_fn and not has_compacted:
                    logger.warning(f"Context limit exceeded during {purpose}. Compacting and retrying...")
                    from .llm import LLMRouter
                    LLMRouter.reset_cooldowns()
                    default_limit = int(getattr(settings, "LLM_COMPACT_MAX_CHARS", 1500))
                    compact_limit = default_limit // 2
                    compacted_desc = _compact_text(job_description, max_chars=compact_limit)
                    new_prompt = rebuild_prompt_fn(compacted_desc)
                    return self._generate_json(
                        task=task,
                        prompt=new_prompt,
                        schema=schema,
                        temperature=temperature,
                        purpose=purpose,
                        job_description=compacted_desc,
                        rebuild_prompt_fn=rebuild_prompt_fn,
                        has_compacted=True,
                    )
                raise AIResponseError(str(exc)) from exc

            self.last_result = result
            raw_text = result.text.strip()
            try:
                parsed = extract_json_object(raw_text)
                return schema.model_validate(parsed)
            except (JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    f"Attempt {attempt} failed validation for schema {schema.__name__}. "
                    f"Error: {exc}. Provider: {result.provider}, Model: {result.model}. "
                    f"Raw text: {raw_text}"
                )
                # Do not block the provider so we can try its pro_model promotion on the next attempt
                # blocked_providers.add(result.provider)
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
        prompt_fn = lambda text: f"""
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
{text.strip()}
"""
        result = self._generate_json(
            task=LLMTask.JOB_EXTRACT,
            prompt=prompt_fn(raw_text),
            schema=BaseJobExtraction,
            temperature=0.1,
            purpose="job extraction",
            job_description=raw_text,
            rebuild_prompt_fn=prompt_fn,
        )
        return result.model_dump(mode="json")


def _compact_text(text: str, max_chars: int | None = None) -> str:
    limit = max_chars or int(getattr(settings, "LLM_COMPACT_MAX_CHARS", 1500))
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "\n\n[Description truncated for compact retry.]"


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
