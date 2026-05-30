# System Architecture

## Overview

Job_bro_AI is built as a layered Django application with clear separation of concerns:

1. **Presentation Layer** - Web UI, Telegram Bot, Discord Webhooks
2. **Application Layer** - Django views, request handlers
3. **Business Logic Layer** - AI services, job matching, profile extraction
4. **LLM Integration Layer** - Provider routing and fallback
5. **Data Layer** - SQLite database, local file storage

---

## Detailed Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     User Interfaces & Entry Points                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌────────────────┐    ┌──────────────────┐      │
│  │   Web UI     │    │  Telegram Bot  │    │ Discord Webhooks │      │
│  │  (Django     │    │  (Channels)    │    │  (Channels)      │      │
│  │   Templates) │    └────────────────┘    └──────────────────┘      │
│  └──────────────┘                                                      │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
┌────────────────────────────────┴───────────────────────────────────────┐
│               Django Application Layer (core/)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     Django Views (views.py)                     │  │
│  │  • ProfileListView, ProfileDetailView                           │  │
│  │  • JobListView, ApplicationListView                             │  │
│  │  • ProviderSettingsView, PreferencesView                        │  │
│  │  • Dashboard Views, Admin Endpoints                             │  │
│  └──────────────┬───────────────────────────────────────────────────┘  │
│                 │                                                      │
│  ┌──────────────▼───────────────────────────────────────────────────┐  │
│  │              Channels Layer (channels.py)                       │  │
│  │  • TelegramHandler - Process incoming Telegram messages         │  │
│  │  • DiscordHandler - Process Discord webhooks                    │  │
│  │  • MessageRouter - Route commands to appropriate handlers       │  │
│  │  • AllowlistValidator - Security checks                         │  │
│  └──────────────┬───────────────────────────────────────────────────┘  │
│                 │                                                      │
│  ┌──────────────▼───────────────────────────────────────────────────┐  │
│  │              Admin & Configuration (admin.py)                   │  │
│  │  • CandidateProfileAdmin - Manage candidate data                │  │
│  │  • JobLeadAdmin - Review job listings                           │  │
│  │  • ApplicationAdmin - Track submissions                         │  │
│  │  • ProviderSettingsAdmin - Configure API keys                  │  │
│  └──────────────┬───────────────────────────────────────────────────┘  │
│                 │                                                      │
└─────────────────┼──────────────────────────────────────────────────────┘
                  │
┌─────────────────┴──────────────────────────────────────────────────────┐
│              Business Logic & AI Services Layer                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │            AI Service Orchestration (ai_service.py)            │  │
│  │                                                                 │  │
│  │  CareerAgentAI                                                  │  │
│  │  ├─ extract_profile_from_document()                            │  │
│  │  ├─ generate_application_kit()                                 │  │
│  │  ├─ evaluate_job_match()                                       │  │
│  │  ├─ rank_applications()                                        │  │
│  │  └─ validate_extraction()                                      │  │
│  └──────────────┬────────────────────────────────────────────────────┘  │
│                 │                                                      │
│  ┌──────────────▼────────────────────────────────────────────────────┐  │
│  │            Core Processing Services                            │  │
│  │                                                                 │  │
│  │  ┌──────────────────────┐   ┌─────────────────────────────┐  │  │
│  │  │ Profile Extraction   │   │ Resume Tailoring            │  │  │
│  │  │ (evidence_scanner.py)│   │ (resume_tailor.py)          │  │  │
│  │  │ • PDF/DOCX parsing   │   │ • ATS optimization          │  │  │
│  │  │ • Entity extraction  │   │ • Keyword matching          │  │  │
│  │  │ • Evidence linking   │   │ • Format customization      │  │  │
│  │  └──────────────────────┘   └─────────────────────────────┘  │  │
│  │                                                                 │  │
│  │  ┌──────────────────────┐   ┌─────────────────────────────┐  │  │
│  │  │ Job Matching         │   │ Application Generation      │  │  │
│  │  │ (job_sources.py)     │   │ (auto_applier.py)           │  │  │
│  │  │ • Job discovery      │   │ • Kit assembly              │  │  │
│  │  │ • Requirement match  │   │ • Template rendering        │  │  │
│  │  │ • Scoring & ranking  │   │ • Submission automation     │  │  │
│  │  └──────────────────────┘   └─────────────────────────────┘  │  │
│  │                                                                 │  │
│  │  ┌──────────────────────┐   ┌─────────────────────────────┐  │  │
│  │  │ Profile Management   │   │ Task Scheduling             │  │  │
│  │  │ (profile_store.py)   │   │ (tasks.py)                  │  │  │
│  │  │ • Store/retrieve     │   │ • Async job processing      │  │  │
│  │  │ • Versioning         │   │ • Background tasks          │  │  │
│  │  │ • Validation         │   │ • Scheduled cleanup         │  │  │
│  │  └──────────────────────┘   └─────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────────────┐
│              LLM Integration Layer (llm.py & Providers)                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    LLM Router (llm.py)                         │  │
│  │                                                                 │  │
│  │  LLMRouter                                                      │  │
│  │  ├─ route_request()     → Select provider                      │  │
│  │  ├─ fallback_logic()    → Try next provider                    │  │
│  │  ├─ handle_errors()     → Rate limits, quota, timeouts         │  │
│  │  ├─ cache_response()    → Cache responses                      │  │
│  │  └─ cooldown_manager()  → Manage provider cooldowns            │  │
│  └──────────────┬───────────────────────────────────────────────────┘  │
│                 │                                                      │
│                 ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                 Resilience Layer (resilience.py)              │  │
│  │                                                                 │  │
│  │  • Exponential backoff retry strategy                           │  │
│  │  • Circuit breaker pattern for failing providers                │  │
│  │  • Rate limit token bucket management                           │  │
│  │  • Health check & provider validation                           │  │
│  │  • Timeout and fallback orchestration                           │  │
│  └──────────────┬───────────────────────────────────────────────────┘  │
│                 │                                                      │
│                 ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │            Provider Implementations (10+ providers)            │  │
│  │                                                                 │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│  │  │   Gemini    │  │   OpenAI     │  │  Anthropic   │          │  │
│  │  │  Provider   │  │   Provider   │  │   Provider   │          │  │
│  │  └─────────────┘  └──────────────┘  └──────────────┘          │  │
│  │                                                                 │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│  │  │    Groq     │  │   OpenRouter │  │     Ollama   │          │  │
│  │  │  Provider   │  │   Provider   │  │   Provider   │          │  │
│  │  └─────────────┘  └──────────────┘  └──────────────┘          │  │
│  │                                                                 │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│  │  │   DeepSeek  │  │   xAI/Grok   │  │ Moonshot/Kimi│          │  │
│  │  │  Provider   │  │   Provider   │  │   Provider   │          │  │
│  │  └─────────────┘  └──────────────┘  └──────────────┘          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────────────┐
│                    Data Layer (models.py)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  SQLite Database Tables:                                                │
│  ├─ CandidateProfile       - Extracted candidate information           │
│  ├─ CandidatePreference    - Job search preferences & filters          │
│  ├─ CandidateLink          - Professional links (LinkedIn, GitHub)     │
│  ├─ JobLead                - Discovered/imported job listings          │
│  ├─ Application            - Generated application kits                │
│  ├─ ProviderSettings       - Configured LLM API keys                   │
│  ├─ ChannelSettings        - Telegram/Discord configuration            │
│  └─ TaskQueue              - Background task tracking (Django-Q2)      │
│                                                                         │
│  Local File Storage:                                                    │
│  ├─ tmp_uploads/           - Uploaded resume files (temp)              │
│  ├─ media/                 - Generated screenshots & documents          │
│  └─ db.sqlite3             - Main database file                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Views Layer (`core/views.py`)

Handles HTTP requests and responses:
- **ProfileListView**: Display all candidate profiles
- **JobListView**: Display job leads with matching scores
- **ApplicationListView**: Show generated applications
- **SettingsView**: Provider API keys and channel configuration
- **DashboardView**: Overview of pending items and status
- **AdminViews**: Manual operations and data management

### Services Layer

#### AIService (`core/ai_service.py`)
- Orchestrates all AI operations
- Implements error handling and retries
- Manages prompt engineering and schema validation
- Interfaces with LLM providers through router

#### LLMRouter (`core/llm.py`)
- Routes requests to enabled providers
- Implements fallback logic
- Manages rate limits and quotas
- Tracks provider health and cooldowns
- Implements caching for repeated queries

#### ResilienceLayer (`core/resilience.py`)
- Exponential backoff retry strategy
- Circuit breaker for failing providers
- Rate limit token bucket
- Health checks and provider status
- Timeout management

#### ProfileExtraction (`core/evidence_scanner.py`)
- Parses resume files (PDF, DOCX)
- Extracts candidate information
- Creates evidence claims
- Links experience to requirements
- Validates extraction quality

#### ResumeTailoring (`core/resume_tailor.py`)
- Customizes resume for specific jobs
- Optimizes for ATS scanning
- Highlights relevant experience
- Adjusts formatting and keywords
- Generates JSON and multiple formats

#### AutoApplication (`core/auto_applier.py`)
- Generates complete application kits
- Creates tailored resume
- Writes compelling cover letters
- Prepares recruiter messages
- Generates interview prep notes

#### JobMatching (`core/job_sources.py`)
- Discovers new job opportunities
- Imports manual job leads
- Scores job matches
- Deduplicates job listings
- Applies user preferences

#### ChannelHandlers (`core/channels.py`)
- Telegram bot message handling
- Discord webhook integration
- Command routing
- User allowlist validation
- Response formatting

### Models Layer (`core/models.py`)

Database schema for:
- Candidate profiles and preferences
- Job leads and applications
- Provider configurations
- Channel settings
- Task queues and audit logs

### Utilities & Schemas

#### Schemas (`core/schemas.py`)
- Pydantic models for data validation
- Type hints and constraints
- JSON schema generation
- Validation error handling

#### Utils (`core/utils.py`)
- Helper functions
- Text processing utilities
- File operations
- Logging and debugging

---

## Data Flow

### 1. Resume Upload & Profile Extraction

```
User uploads resume (PDF/DOCX)
    ↓
[views.py] Handle file upload
    ↓
[evidence_scanner.py] Extract text from document
    ↓
[ai_service.py] Send to LLM for extraction
    ↓
[llm.py] Route to provider (Gemini, OpenAI, etc.)
    ↓
[Provider API] Returns structured JSON
    ↓
[schemas.py] Validate extracted data
    ↓
[models.py] Store CandidateProfile in database
    ↓
User reviews extracted data (human-in-the-loop)
    ↓
[models.py] Confirm or edit profile
```

### 2. Job Matching & Application Generation

```
Job leads imported or discovered
    ↓
[job_sources.py] Normalize job data
    ↓
[models.py] Store in JobLead table
    ↓
[ai_service.py] Score against candidate profile
    ↓
[llm.py] Evaluate relevance (provider routing)
    ↓
User reviews job matches in dashboard
    ↓
User selects job for application
    ↓
[resume_tailor.py] Customize resume for job
    ↓
[auto_applier.py] Generate full application kit
    ↓
[ai_service.py] Create cover letter, recruiter message, etc.
    ↓
[models.py] Store Application with all components
    ↓
User reviews generated application
    ↓
User submits or edits before submitting
    ↓
[models.py] Mark as submitted with timestamp
```

### 3. Multi-Channel Interaction

```
User sends Telegram message / Discord message
    ↓
[channels.py] Webhook receives message
    ↓
[channels.py] Parse command and validate allowlist
    ↓
[views.py] Route to appropriate handler
    ↓
[ai_service.py] Process request (if AI needed)
    ↓
[llm.py] Get response from provider
    ↓
[channels.py] Format response for channel
    ↓
Send reply to Telegram/Discord
    ↓
User receives response with quick actions
```

---

## Provider Fallback Logic

```
┌─ User Request ──────────────────────┐
│                                     │
│  [Check Enabled Providers]          │
│         ↓                           │
│  [Primary: Gemini]                  │
│    Success? ──Y──> Return ✅        │
│         ↓ N                         │
│    Error Type?                      │
│      ├─ Rate Limited    ──> Cooldown│
│      ├─ Quota Exceeded  ──> Skip    │
│      ├─ Server Error    ──> Retry   │
│      └─ Network Error   ──> Retry   │
│         ↓                           │
│  [Fallback: OpenAI]                 │
│    Success? ──Y──> Return ✅        │
│         ↓ N                         │
│  [Fallback: Claude]                 │
│    Success? ──Y──> Return ✅        │
│         ↓ N                         │
│  [Fallback: Others...]              │
│    Success? ──Y──> Return ✅        │
│         ↓ N                         │
│                                     │
│  [All Failed]                       │
│    Return Clear UI Guidance:        │
│    • Retry in X minutes             │
│    • Enable another key             │
│    • Turn on Ollama                 │
│    • Continue without AI            │
│                                     │
└─────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. **Privacy-First Architecture**
- All data stays local by default
- No cloud sync without explicit configuration
- SQLite for easy backup and portability
- Optional encryption at rest

### 2. **Provider Agnosticism**
- Providers are pluggable
- Fallback is automatic and intelligent
- Each provider is isolated
- No vendor lock-in

### 3. **Human-in-the-Loop**
- AI prepares, humans review
- All generated content editable
- Manual override always possible
- Audit trail of changes

### 4. **Resilience & Reliability**
- Exponential backoff for retries
- Circuit breaker for failing providers
- Rate limit handling
- Graceful degradation

### 5. **Multi-Channel Support**
- Single backend, multiple frontends
- Web, Telegram, Discord
- Allowlist-based security
- Consistent data across channels

### 6. **Extensibility**
- Modular service architecture
- Easy to add new providers
- Plugin-style job sources
- Custom Django commands

---

## Extension Points

### Adding a New LLM Provider

1. Create provider class in `core/llm.py`
2. Implement `call()` and `handle_error()` methods
3. Add configuration to `.env.example`
4. Register in `LLMRouter.providers`
5. Add tests

### Adding a New Job Source

1. Create source class in `core/job_sources.py`
2. Implement `fetch()` and `normalize()` methods
3. Add scoring logic
4. Register in `JobSourceRouter`

### Adding a New Channel

1. Create handler in `core/channels.py`
2. Implement `handle_message()` method
3. Add webhook endpoint in `core/urls.py`
4. Create settings model
5. Add allowlist validation

---

## Performance Considerations

### Caching
- LLM responses cached for 24 hours
- Job matches cached for 12 hours
- Provider health status cached for 5 minutes

### Async Processing
- Resume extraction: Background task
- Application generation: Queue system
- Job matching: Batch processing

### Database Optimization
- Indexes on frequently queried fields
- Database query optimization
- Pagination for large result sets

---

## Security Considerations

### API Key Management
- Keys stored in `.env` (never in code)
- Never logged or sent between providers
- Rotated on schedule
- Per-provider isolation

### Database Security
- Strong `DJANGO_SECRET_KEY`
- HTTPS in production
- Limited query access
- SQL injection prevention via ORM

### Authentication & Authorization
- Allowlist validation for channels
- User-specific data isolation
- Admin interface security
- Session management

---

## Testing Architecture

### Unit Tests
- Test individual services
- Mock LLM providers
- Validate data models
- Test error handling

### Integration Tests
- Test end-to-end flows
- Real database interactions
- Multiple provider fallback
- Channel routing

### End-to-End Tests
- Full application workflow
- UI testing with Playwright
- Telegram/Discord simulation
- Production deployment validation
