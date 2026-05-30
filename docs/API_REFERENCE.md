# API & Module Reference

This document provides detailed API reference for Job_bro_AI core modules and services.

---

## Table of Contents

- [Core Services](#core-services)
- [Models](#models)
- [Schemas](#schemas)
- [Views & URLs](#views--urls)
- [Utilities](#utilities)

---

## Core Services

### AIService (`core/ai_service.py`)

Main orchestrator for AI operations.

#### Class: `CareerAgentAI`

```python
class CareerAgentAI:
    """AI service for profile extraction, job matching, and application generation."""
    
    def __init__(
        self,
        api_key: str | None = None,
        flash_model: str | None = None,
        pro_model: str | None = None,
        max_attempts: int = 2,
        router: LLMRouter | None = None,
    ) -> None:
        """
        Initialize AI service.
        
        Args:
            api_key: Gemini API key (optional if using LLMRouter)
            flash_model: Fast model name (default: gemini-2.5-flash)
            pro_model: Powerful model name (default: gemini-2.5-pro)
            max_attempts: Max retry attempts
            router: Custom LLM router instance
        """
        ...
```

#### Methods

**extract_profile_from_document()**

```python
def extract_profile_from_document(
    self,
    document_path: str | Path
) -> MasterProfile:
    """
    Extract candidate profile from resume document.
    
    Args:
        document_path: Path to PDF/DOCX resume file
    
    Returns:
        MasterProfile object with extracted candidate data
    
    Raises:
        AIResponseError: If extraction fails
        ValidationError: If extracted data doesn't match schema
        FileNotFoundError: If document doesn't exist
    
    Example:
        >>> ai = CareerAgentAI()
        >>> profile = ai.extract_profile_from_document("resume.pdf")
        >>> print(profile.name)
        'John Doe'
    """
    ...
```

**generate_application_kit()**

```python
def generate_application_kit(
    self,
    profile: MasterProfile,
    job: JobLead,
    include_interview_prep: bool = True
) -> ApplicationKit:
    """
    Generate complete application kit for a job.
    
    Args:
        profile: Candidate profile
        job: Target job lead
        include_interview_prep: Whether to generate interview notes
    
    Returns:
        ApplicationKit with resume, cover letter, messages, interview prep
    
    Raises:
        AIResponseError: If generation fails
        ValidationError: If output doesn't match schema
    """
    ...
```

**evaluate_job_match()**

```python
def evaluate_job_match(
    self,
    profile: MasterProfile,
    job: JobLead
) -> MatchResult:
    """
    Score job match for a candidate.
    
    Args:
        profile: Candidate profile
        job: Job to evaluate
    
    Returns:
        MatchResult with scores and reasoning
    """
    ...
```

---

### LLM Router (`core/llm.py`)

Provider routing and fallback logic.

#### Class: `LLMRouter`

```python
class LLMRouter:
    """Routes LLM requests to enabled providers with fallback."""
    
    def route(
        self,
        request: LLMRequest
    ) -> LLMResult:
        """
        Route request to appropriate provider.
        
        Args:
            request: LLM request with prompt and schema
        
        Returns:
            LLMResult from successful provider
        
        Raises:
            LLMExhaustedError: If all providers fail
        """
        ...
    
    def add_provider(
        self,
        name: str,
        provider: BaseLLMProvider
    ) -> None:
        """
        Register a new provider.
        
        Args:
            name: Provider identifier
            provider: Provider instance
        """
        ...
    
    def get_active_providers(self) -> List[str]:
        """
        Get list of enabled providers.
        
        Returns:
            List of provider names with valid API keys
        """
        ...
```

---

### Evidence Scanner (`core/evidence_scanner.py`)

Extract candidate information from documents.

#### Function: `extract_document_text()`

```python
def extract_document_text(document_path: str | Path) -> str:
    """
    Extract text from PDF or DOCX document.
    
    Args:
        document_path: Path to PDF/DOCX file
    
    Returns:
        Extracted text content
    
    Raises:
        ValueError: If file format not supported
        FileNotFoundError: If file doesn't exist
    
    Example:
        >>> text = extract_document_text("resume.pdf")
        >>> len(text) > 100
        True
    """
    ...
```

#### Class: `EvidenceExtractor`

```python
class EvidenceExtractor:
    """Extract structured evidence claims from resume."""
    
    def extract_experience(
        self,
        resume_text: str
    ) -> List[ExperienceClaim]:
        """
        Extract work experience claims.
        
        Args:
            resume_text: Full resume text
        
        Returns:
            List of work experience claims
        """
        ...
    
    def extract_skills(
        self,
        resume_text: str
    ) -> List[SkillClaim]:
        """
        Extract technical and soft skills.
        
        Args:
            resume_text: Full resume text
        
        Returns:
            List of skill claims with proficiency
        """
        ...
```

---

### Resume Tailor (`core/resume_tailor.py`)

Customize resume for specific jobs.

#### Class: `ResumeTailor`

```python
class ResumeTailor:
    """Customize resume for specific job."""
    
    def tailor_resume(
        self,
        profile: MasterProfile,
        job: JobLead
    ) -> TailoredResume:
        """
        Generate ATS-optimized resume for job.
        
        Args:
            profile: Candidate master profile
            job: Target job
        
        Returns:
            Tailored resume in JSON format
        """
        ...
    
    def highlight_relevant_skills(
        self,
        profile: MasterProfile,
        job: JobLead
    ) -> List[str]:
        """
        Find skills matching job requirements.
        
        Args:
            profile: Candidate profile
            job: Target job
        
        Returns:
            List of relevant skill names
        """
        ...
```

---

### Auto Applier (`core/auto_applier.py`)

Generate application materials.

#### Function: `generate_cover_letter()`

```python
def generate_cover_letter(
    profile: MasterProfile,
    job: JobLead,
    router: LLMRouter
) -> str:
    """
    Generate personalized cover letter.
    
    Args:
        profile: Candidate profile
        job: Target job
        router: LLM router for generation
    
    Returns:
        Generated cover letter text
    """
    ...
```

#### Function: `generate_recruiter_message()`

```python
def generate_recruiter_message(
    profile: MasterProfile,
    job: JobLead,
    recruiter_name: str | None = None,
    router: LLMRouter | None = None
) -> str:
    """
    Generate outreach message to recruiter.
    
    Args:
        profile: Candidate profile
        job: Target job
        recruiter_name: Optional recruiter name for personalization
        router: LLM router
    
    Returns:
        Professional recruiter outreach message
    """
    ...
```

---

### Job Sources (`core/job_sources.py`)

Discover and manage job opportunities.

#### Class: `JobSourceRouter`

```python
class JobSourceRouter:
    """Route job searches to enabled sources."""
    
    def search(
        self,
        query: str,
        filters: JobSearchFilters | None = None
    ) -> List[JobLead]:
        """
        Search for jobs across sources.
        
        Args:
            query: Job search query
            filters: Optional search filters
        
        Returns:
            List of job leads
        """
        ...
    
    def deduplicate_jobs(
        self,
        jobs: List[JobLead]
    ) -> List[JobLead]:
        """
        Remove duplicate job listings.
        
        Args:
            jobs: Job list to deduplicate
        
        Returns:
            Deduplicated job list
        """
        ...
```

#### Class: `JobSpy Wrapper`

```python
class JobSpySource(BaseJobSource):
    """Python JobSpy job source wrapper."""
    
    def search(
        self,
        query: str,
        location: str | None = None,
        days_back: int = 7,
        max_results: int = 50
    ) -> List[JobLead]:
        """
        Search jobs using JobSpy.
        
        Args:
            query: Job title/keywords
            location: Job location filter
            days_back: Only jobs posted in last N days
            max_results: Maximum results to return
        
        Returns:
            List of job leads
        """
        ...
```

---

## Models

### CandidateProfile (`core/models.py`)

```python
class CandidateProfile(models.Model):
    """Stores candidate information."""
    
    class Status(models.TextChoices):
        DRAFT = "draft"
        REVIEW_REQUIRED = "review_required"
        READY = "ready"
    
    # Fields
    is_active: BooleanField  # Active candidate flag
    status: CharField         # Draft, review, or ready
    full_name: CharField      # Candidate name
    email: EmailField         # Email address
    phone: CharField          # Phone number
    location: CharField       # Current location
    linkedin_url: URLField    # LinkedIn profile
    github_url: URLField      # GitHub profile
    portfolio_url: URLField   # Portfolio website
    extracted_profile: JSONField  # AI extracted data
    confirmed_profile: JSONField  # Human-verified data
    notes: TextField          # User notes
    created_at: DateTimeField
    updated_at: DateTimeField
    
    # Methods
    @classmethod
    def active(cls) -> "CandidateProfile | None":
        """Get active candidate profile."""
        ...
    
    def to_master_profile(self) -> MasterProfile:
        """Convert to MasterProfile schema."""
        ...
    
    def apply_manual_fields(self, data: dict) -> None:
        """Apply manually entered fields."""
        ...
```

### JobLead (`core/models.py`)

```python
class JobLead(models.Model):
    """Job opportunity listing."""
    
    title: CharField           # Job title
    company: CharField         # Company name
    location: CharField        # Job location
    description: TextField     # Full job description
    requirements: TextField    # Job requirements
    salary_range: CharField    # Salary if available
    job_url: URLField         # Link to job posting
    source: CharField         # Source (LinkedIn, Indeed, etc.)
    posted_date: DateTimeField  # When job was posted
    match_score: IntegerField  # Relevance score (0-100)
    fingerprint: CharField    # Dedup hash
    ai_metadata: JSONField    # LLM analysis metadata
    created_at: DateTimeField
    updated_at: DateTimeField
```

### Application (`core/models.py`)

```python
class Application(models.Model):
    """Generated application for a job."""
    
    job_lead: ForeignKey      # Related job
    candidate: ForeignKey     # Related candidate
    status: CharField         # Draft, ready, submitted
    kit_data: JSONField       # Full application kit (resume, cover letter, etc.)
    human_edits: JSONField    # User edits to generated content
    screenshot: ImageField    # Optional screenshot of submission
    submitted_at: DateTimeField  # When submitted
    ai_metadata: JSONField    # Model, tokens, provider info
    error_message: TextField  # If generation failed
    created_at: DateTimeField
    updated_at: DateTimeField
```

---

## Schemas

### Pydantic Models (`core/schemas.py`)

#### MasterProfile

```python
class MasterProfile(BaseModel):
    """Candidate master profile schema."""
    
    name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    work_authorization: str | None = None
    availability: str | None = None
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    
    skills: list[Skill]
    experience: list[Experience]
    education: list[Education]
    certifications: list[Certification]
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "skills": [{"name": "Python", "level": 5}]
            }
        }
```

#### ApplicationKit

```python
class ApplicationKit(BaseModel):
    """Complete application kit for a job."""
    
    resume: TailoredResume
    cover_letter: str
    recruiter_message: str
    follow_up_message: str
    interview_prep: InterviewPrep
    evidence_mapping: list[EvidenceMapping]
    
    generated_at: datetime
    ai_metadata: AIMetadata | None = None
```

#### MatchResult

```python
class MatchResult(BaseModel):
    """Job match evaluation result."""
    
    job_id: int
    candidate_id: int
    overall_score: int  # 0-100
    skill_match: int    # 0-100
    experience_match: int  # 0-100
    growth_potential: int  # 0-100
    reasoning: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "overall_score": 85,
                "skill_match": 90,
                "experience_match": 80,
                "growth_potential": 75
            }
        }
```

---

## Views & URLs

### URL Routes (`core/urls.py`)

```
/                           → Home dashboard
/profile/                   → Candidate profile management
/profile/upload/            → Upload resume
/profile/<id>/             → View/edit profile
/jobs/                     → Browse jobs
/jobs/<id>/                → Job details
/jobs/<id>/score/          → Score job match
/jobs/<id>/apply/          → Generate application
/applications/             → View applications
/applications/<id>/        → Review application
/settings/providers/       → Configure LLM providers
/settings/channels/        → Configure Telegram/Discord
/admin/                    → Django admin panel
```

### API Endpoints (JSON)

```
GET  /api/candidates/              - List candidates
POST /api/candidates/              - Create candidate
GET  /api/candidates/{id}/         - Get candidate
PUT  /api/candidates/{id}/         - Update candidate

GET  /api/jobs/                    - List jobs
POST /api/jobs/                    - Create job lead
GET  /api/jobs/{id}/score/         - Score job match

GET  /api/applications/            - List applications
POST /api/applications/            - Create application
GET  /api/applications/{id}/       - Get application
PUT  /api/applications/{id}/submit - Submit application

GET  /api/health/                  - Health check
POST /api/providers/test/          - Test LLM provider
```

---

## Utilities

### Validation Utilities (`core/utils.py`)

```python
def validate_email(email: str) -> bool:
    """Validate email format."""
    ...

def normalize_skill_name(skill: str) -> str:
    """Normalize skill name for deduplication."""
    ...

def extract_requirements(
    job_description: str,
    max_items: int = 20
) -> List[str]:
    """Extract key requirements from job description."""
    ...
```

### Error Classes (`core/exceptions.py`)

```python
class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass

class AIResponseError(AIServiceError):
    """AI provider returned invalid response."""
    pass

class LLMExhaustedError(AIServiceError):
    """All LLM providers failed."""
    pass

class ProfileValidationError(AIServiceError):
    """Profile validation failed."""
    pass
```

---

## Task Queue (`core/tasks.py`)

Background task functions for django-q2.

```python
# Enqueue tasks like this:
from django_q.tasks import async_task

async_task(
    'core.tasks.generate_application_kit',
    job_id=123,
    candidate_id=456,
)
```

### Available Tasks

- `generate_application_kit()` - Generate full application
- `score_job_match()` - Score single job
- `batch_score_jobs()` - Score multiple jobs
- `extract_resume_async()` - Extract profile in background
- `send_telegram_notification()` - Send Telegram message
- `send_discord_notification()` - Send Discord message

---

## Channel Integration (`core/channels.py`)

Telegram and Discord message handling.

```python
class TelegramHandler:
    """Handle Telegram bot messages."""
    
    def handle_message(self, message: dict) -> dict:
        """Process incoming Telegram message."""
        ...
    
    def send_message(self, chat_id: int, text: str) -> bool:
        """Send message to Telegram chat."""
        ...

class DiscordHandler:
    """Handle Discord webhook messages."""
    
    def handle_webhook(self, payload: dict) -> dict:
        """Process Discord webhook."""
        ...
    
    def send_message(self, channel_id: int, text: str) -> bool:
        """Send message to Discord channel."""
        ...
```

---

## Environment Configuration

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for all configurable settings.

---

## Code Examples

### Extract profile from resume

```python
from core.ai_service import CareerAgentAI

ai = CareerAgentAI()
profile = ai.extract_profile_from_document("resume.pdf")
print(profile.name)
print(profile.skills)
```

### Score a job match

```python
from core.ai_service import CareerAgentAI
from core.models import CandidateProfile, JobLead

ai = CareerAgentAI()
candidate = CandidateProfile.objects.get(id=1)
job = JobLead.objects.get(id=1)

profile = candidate.to_master_profile()
match_result = ai.evaluate_job_match(profile, job)

print(f"Match Score: {match_result.overall_score}/100")
print(f"Reasoning: {match_result.reasoning}")
```

### Generate application

```python
from core.models import CandidateProfile, JobLead, Application
from django_q.tasks import async_task

candidate = CandidateProfile.objects.get(id=1)
job = JobLead.objects.get(id=1)

# Enqueue background task
task_id = async_task(
    'core.tasks.generate_application_kit',
    job_id=job.id,
    candidate_id=candidate.id,
)

# Check status later
from django_q.models import Task
task = Task.objects.get(id=task_id)
print(f"Status: {task.status}")  # started, success, failed
```

### Add custom provider

```python
from core.llm import LLMRouter, BaseLLMProvider

class CustomProvider(BaseLLMProvider):
    def call(self, prompt, schema):
        # Implementation
        return LLMResult(...)

router = LLMRouter()
router.add_provider("custom", CustomProvider("api-key"))
```

---

## Testing

Example tests for module functionality:

```python
from django.test import TestCase
from core.ai_service import CareerAgentAI
from core.models import CandidateProfile

class AIServiceTestCase(TestCase):
    
    def test_extract_profile(self):
        """Test profile extraction."""
        ai = CareerAgentAI()
        profile = ai.extract_profile_from_document("test_resume.pdf")
        
        self.assertIsNotNone(profile.name)
        self.assertGreater(len(profile.skills), 0)
    
    def test_invalid_file_raises_error(self):
        """Test that invalid file raises error."""
        ai = CareerAgentAI()
        
        with self.assertRaises(FileNotFoundError):
            ai.extract_profile_from_document("nonexistent.pdf")
```

---

## Performance Tips

1. **Batch operations**: Use `bulk_create()` for multiple objects
2. **Query optimization**: Use `select_related()` and `prefetch_related()`
3. **Caching**: Cache expensive LLM results
4. **Async tasks**: Use django-q2 for long-running operations
5. **Database indexes**: Already defined in models

---

## Debugging

Enable verbose logging:

```python
import logging
logging.getLogger('core.ai_service').setLevel(logging.DEBUG)
```

Check task queue status:

```bash
python manage.py shell
from django_q.models import Task
Task.objects.filter(status='failed').values()
```

---

**Need more help?** Check the [ARCHITECTURE.md](ARCHITECTURE.md) and [DATA_FLOW.md](DATA_FLOW.md) documents.
