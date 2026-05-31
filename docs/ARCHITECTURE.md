# System Architecture

Job_bro_AI is a Django application organized around a local-first, review-first workflow. The system keeps candidate data local by default, routes AI work through explicit provider adapters, and records pipeline state so discovery, scoring, and kit generation are observable.

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Entry["Entry points"]
        Web["Django Web UI"]
        Telegram["Telegram webhook"]
        Discord["Discord interactions"]
        Admin["Django admin"]
    end

    subgraph App["Application layer"]
        Views["core.views"]
        Channels["core.channels"]
        Tasks["core.tasks"]
        Runner["core.job_runner"]
    end

    subgraph Domain["Domain services"]
        Profile["profile_store and profile_readiness"]
        Discovery["discovery and sources"]
        Matching["match_policy and scoring"]
        Kits["ai_service and resume_tailor"]
        Metrics["metrics and cost_tracking"]
    end

    subgraph AI["AI integration"]
        Prompts["core.prompts"]
        Router["core.llm LLMRouter"]
        Providers["Provider adapters"]
    end

    subgraph Data["Local data"]
        DB[("SQLite or configured database")]
        Uploads["tmp_uploads and media"]
    end

    Web --> Views
    Admin --> DB
    Telegram --> Channels
    Discord --> Channels
    Channels --> Views
    Views --> Tasks
    Tasks --> Runner
    Runner --> Domain
    Views --> Domain
    Domain --> AI
    Prompts --> Router
    Router --> Providers
    Domain --> DB
    Views --> Uploads
```

## Core Responsibilities

| Area | Modules | Responsibility |
|---|---|---|
| Configuration | `career_agent/settings.py`, `career_agent/deploy_settings.py` | Runtime settings, public deploy checks, provider defaults, local storage paths. |
| Web workflow | `core/views.py`, `templates/`, `static/` | Onboarding, profile review, queue management, provider settings, metrics, and application review. |
| Candidate model | `core/models.py`, `core/profile_store.py`, `core/profile_readiness.py` | Candidate profile persistence, evidence claims, preferences, readiness gates, and profile snapshots. |
| Job pipeline | `core/discovery.py`, `core/sources/`, `core/job_sources.py`, `core/tasks.py` | Source adapters, lead normalization, dedupe, scoring, tracked jobs, and kit generation. |
| AI orchestration | `core/ai_service.py`, `core/llm.py`, `core/prompts/`, `core/schemas.py` | Prompt construction, structured outputs, provider fallback, validation, and schema grounding. |
| Reliability | `core/resilience.py`, `core/errors.py`, `core/job_runner.py`, `core/logging_utils.py` | User-safe errors, retries, cancellation, progress state, and structured logging. |
| Observability | `core/metrics.py`, `core/cost_tracking.py` | Funnel statistics, recent pipeline state, LLM usage, and budget checks. |

## Request Flow

```mermaid
sequenceDiagram
    participant User
    participant Views as core.views
    participant Profile as Profile services
    participant Tasks as Pipeline tasks
    participant AI as CareerAgentAI
    participant LLM as LLMRouter
    participant DB as Database

    User->>Views: Upload document or update profile
    Views->>Profile: Save extracted and manual data
    Profile->>DB: Persist profile, documents, claims
    User->>Views: Run discovery or generate kit
    Views->>Tasks: Enqueue or run tracked task
    Tasks->>AI: Score lead or generate kit
    AI->>LLM: Structured provider request
    LLM-->>AI: Validated text or JSON response
    AI-->>Tasks: Schema-validated result
    Tasks->>DB: Update lead, application, usage, job state
    Views-->>User: Queue, application, or metrics update
```

## Design Principles

- Local-first: private candidate data, resumes, screenshots, and local databases are not repository assets.
- Review-first: the product prepares application material, but human review remains the public default.
- Provider isolation: API keys are opt-in and provider calls flow through a small adapter surface.
- Observable jobs: long-running work records status, progress, results, and failures through `PipelineJob`.
- Failure containment: user-facing errors are normalized, providers cool down on transient failures, and budget checks stop runaway usage.

## Extension Points

- Add a provider by implementing an adapter in `core/llm.py`, adding it to `_adapter_map`, and documenting the required environment variables.
- Add a job source by implementing `JobSourceAdapter` in `core/sources/` or wrapping a callable with `CallableSourceAdapter`.
- Add a workflow page by wiring a view in `core/views.py`, a route in `core/urls.py`, and a template under `templates/core/`.
- Add a tracked background action through `core/tasks.py` and wrap it with `run_tracked` from `core/job_runner.py`.

## Public Deployment Boundary

The repository is safe to publish only when credentials, databases, resumes, generated drafts, and local virtual environments are absent from Git. A public hosted instance needs additional authentication, per-user data isolation, HTTPS, secure cookies, and production settings.
