# Data Flow

This document gives the main runtime flows for the application. It is written for maintainers who need to understand where data enters, how it is transformed, and where it is persisted.

## Profile Extraction Flow

```mermaid
sequenceDiagram
    participant Browser
    participant Views as core.views
    participant Files as tmp_uploads
    participant AI as CareerAgentAI
    participant Schema as MasterProfile
    participant Store as profile_store
    participant DB as Database

    Browser->>Views: POST candidate document and manual fields
    Views->>Views: Validate size, suffix, and content type
    Views->>Files: Save temporary upload
    Views->>AI: Extract profile from document
    AI->>Schema: Validate structured profile
    Views->>Store: Save profile, document metadata, preferences
    Store->>DB: CandidateProfile, CandidateDocument, EvidenceSource, ProfileClaim
    Views-->>Browser: Redirect to review or return JSON error
```

Failure handling:

- Invalid uploads return user-safe validation errors.
- Extraction failures are formatted through `core.errors`.
- Temporary files and uploads must remain outside Git.

## Discovery and Scoring Flow

```mermaid
sequenceDiagram
    participant User
    participant Views as core.views
    participant Tasks as core.tasks
    participant Discovery as core.discovery
    participant Sources as source adapters
    participant AI as CareerAgentAI
    participant DB as Database

    User->>Views: Start discovery or bulk score
    Views->>Tasks: Enqueue tracked pipeline
    Tasks->>Discovery: Resolve config and run adapters
    Discovery->>Sources: Fetch raw jobs
    Sources-->>Discovery: Raw job payloads
    Discovery->>DB: Import normalized JobLead records
    Tasks->>AI: Score unscored leads
    AI-->>Tasks: MatchResult
    Tasks->>DB: Update lead and create matched applications
    Views-->>User: Queue and progress state
```

Control points:

- `archive_stale_leads` keeps old queue items from growing without review.
- `assert_within_budget` protects against unexpected LLM spend.
- `thresholds_for_candidate` controls lead and application status transitions.

## Application Kit Flow

```mermaid
flowchart TB
    ReadyProfile["Ready CandidateProfile"] --> Snapshot["Profile snapshot"]
    MatchedLead["Matched JobLead"] --> Description["Job description"]
    Snapshot --> Prompt["Application-kit prompt"]
    Description --> Prompt
    Prompt --> Router["LLMRouter"]
    Router --> Kit["ApplicationKit schema"]
    Kit --> Grounding["Grounding validation"]
    Grounding --> Application["Application record"]
    Application --> Review["Human review"]
    Review --> Submitted["User marks submitted"]
```

Persistence:

- `Application.profile_snapshot` preserves the candidate state used for generation.
- `Application.generated_kit` stores structured generated material.
- `Application.status` moves through matched, kit-ready, submitted, failed, or dismissed states.

## Channel Command Flow

```mermaid
flowchart LR
    Telegram["Telegram webhook"] --> View["Webhook view"]
    Discord["Discord interaction"] --> View
    View --> Adapter["Channel adapter"]
    Adapter --> Command["Command handler"]
    Command --> Domain["Queue, provider health, scoring, kit generation"]
    Domain --> Event["NotificationEvent"]
    Event --> Response["Channel response"]
```

Security controls:

- Channel users and destinations must be allowlisted.
- Secrets remain in environment variables.
- Channel payloads should not be committed or pasted into public issues.

## Error and Budget Flow

```mermaid
flowchart TB
    Request["User or task request"] --> Cost["Estimate cost"]
    Cost --> Budget{"Within daily budget?"}
    Budget -- "No" --> Block["Raise budget error"]
    Budget -- "Yes" --> Provider["Call provider"]
    Provider --> Result{"Success?"}
    Result -- "Yes" --> Record["Record usage metadata"]
    Result -- "No" --> Classify["Classify error"]
    Classify --> Cooldown["Cooldown or retry provider"]
    Cooldown --> Fallback["Try next provider"]
    Fallback --> Provider
```

The UI should show actionable errors without leaking credentials, raw provider payloads, or private prompt contents.
