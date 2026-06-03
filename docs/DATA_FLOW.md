# Job_bro_AI Runtime Data Flow Diagrams

This manual details the step-by-step runtime sequence flows for **Job_bro_AI**. It maps the interactions between the browser client, Django views, background worker tasks, the AI service, and the external LLM endpoints.

---

## 1. Candidate Onboarding & Profile Extraction Flow

This flow triggers when a user uploads their resume to extract and compile a structured profile.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator (Browser)
    participant Views as core.views.onboard_profile
    participant Files as OS Filesystem (tmp_uploads/)
    participant AI as core.ai_service (CareerAgentAI)
    participant Router as core.llm (LLMRouter)
    participant Schemas as core.schemas (MasterProfile)
    participant Store as core.profile_store (save_profile)
    participant DB as Database (SQLite)

    User->>Views: POST /onboard/ (File payload + preferences)
    activate Views
    Views->>Views: Validate file extension (.pdf/.docx) & limit (<10MB)
    
    Views->>Files: Save original document to tmp_uploads/
    activate Files
    Files-->>Views: Document absolute path
    deactivate Files
    
    Views->>Views: Extract raw text from file using pdfplumber/docx
    Views->>AI: extract_profile_from_document(raw_text)
    activate AI
    
    AI->>Router: request_structured_completion(prompt, MasterProfile)
    activate Router
    Router->>Router: Check daily budget limit
    Router->>Router: Query API (Gemini/OpenAI/Anthropic)
    Router-->>AI: Raw JSON string response
    deactivate Router
    
    AI->>Schemas: MasterProfile.model_validate_json(raw_json)
    activate Schemas
    Note over AI,Schemas: Ensures LLM output strictly matches Pydantic fields
    Schemas-->>AI: Validated MasterProfile Pydantic Object
    deactivate Schemas
    
    AI-->>Views: Return Pydantic MasterProfile Object
    deactivate AI

    Views->>Store: save_profile(candidate, master_profile_obj)
    activate Store
    Store->>DB: INSERT/UPDATE CandidateProfile record
    Store->>DB: INSERT CandidateDocument record (linked to file path)
    Store->>DB: INSERT EvidenceSource record
    Store->>DB: Bulk INSERT ProfileClaim records (atomized sentences)
    Store-->>Views: Success confirmation
    deactivate Store

    Views-->>User: Redirect to profile review view (/profile/)
    deactivate Views
```

---

## 2. Job Discovery & Scoring Flow

This sequence executes when the background queue or CLI command checks for new job leads and runs AI matching.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Scheduler
    participant Views as core.views.start_discovery
    participant Tasks as core.tasks.run_discovery_task
    participant Runner as core.job_runner.run_tracked
    participant Discov as core.discovery.resolve_discovery_config
    participant Adapters as core.sources (JobSourceAdapters)
    participant AI as core.ai_service (CareerAgentAI)
    participant DB as Database (SQLite)

    User->>Views: POST /queue/start-discovery/
    activate Views
    Views->>Tasks: Enqueue run_discovery_task (async job-id)
    Views-->>User: 200 OK (Job status polling endpoint)
    deactivate Views

    activate Tasks
    Tasks->>Runner: run_tracked(job_id, discovery_loop)
    activate Runner
    Runner->>DB: Update PipelineJob status to RUNNING

    Runner->>Discov: resolve_discovery_config(candidate)
    activate Discov
    Discov-->>Runner: List of active source IDs (e.g. ['jobspy', 'remoteok'])
    deactivate Discov

    loop For each source adapter ID
        Runner->>Adapters: Build adapter & call fetch()
        activate Adapters
        Adapters->>Adapters: Perform HTTP scraping or API call
        Adapters-->>Runner: Return list of RawJob structures
        deactivate Adapters
        
        loop For each RawJob
            Runner->>Runner: Generate dedupe fingerprint (SHA256)
            Runner->>DB: Check if fingerprint exists in JobLead
            alt Fingerprint is duplicate
                Runner->>Runner: Skip importing
            else Fingerprint is unique
                Runner->>DB: INSERT JobLead (status=NEW, fingerprint)
            end
        end
    end

    Note over Runner,AI: Phase 2: Scoring newly discovered leads
    Runner->>DB: Fetch unscored JobLeads (status=NEW)
    DB-->>Runner: List of leads to score

    loop For each unscored JobLead
        Runner->>AI: match_job_to_profile(profile, lead.description)
        activate AI
        AI->>AI: Send prompt to LLMRouter (MatchResult schema)
        AI-->>Runner: Return MatchResult (score, confidence, rationale)
        deactivate AI
        
        alt Score >= min_match_score AND Confidence >= min_match_confidence
            Runner->>DB: UPDATE JobLead status=MATCHED, score
            Runner->>DB: INSERT Application record (status=MATCHED)
        else Score is low
            Runner->>DB: UPDATE JobLead status=LOW_MATCH, score
        end
    end

    Runner->>DB: UPDATE PipelineJob status=COMPLETED, message="Finished"
    deactivate Runner
    deactivate Tasks
```

---

## 3. Application Kit Tailoring & Grounding Verification

This flow builds targeted resume data and cover letters while verifying claims against the candidate's original resume to eliminate hallucinations.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator (Browser)
    participant Views as core.views.generate_kit
    participant AI as core.ai_service (CareerAgentAI)
    participant Tailor as core.resume_tailor (ResumeTailor)
    participant DB as Database (SQLite)

    User->>Views: POST /applications/{id}/generate/
    activate Views
    Views->>DB: Check profile readiness blockers
    DB-->>Views: Ready (0 blockers)
    Views->>DB: Fetch Application and associated JobLead
    DB-->>Views: Application record details

    Views->>AI: generate_application_kit(profile, lead)
    activate AI
    
    AI->>Tailor: tailor_experience(experience_blocks, job_description)
    activate Tailor
    Tailor-->>AI: Tailored experience bullet points
    deactivate Tailor

    AI->>AI: Request Pydantic structured completion (ApplicationKit schema)
    AI->>DB: Fetch candidate ProfileClaims (original verified facts)
    DB-->>AI: List of claims (e.g. "Worked with Django", "Led team")
    
    AI->>AI: Run grounding check (validate_grounded_kit)
    Note over AI: Verifies that statements in cover letter<br/>are backed by candidate ProfileClaims
    
    alt Verification fails (hallucination detected)
        AI->>AI: Adjust prompt constraints and retry generation
    end

    AI-->>Views: Return validated ApplicationKit Pydantic Object
    deactivate AI

    Views->>DB: UPDATE Application status=KIT_READY, save kit JSON
    Views-->>User: Redirect to application details view (/applications/{id}/)
    deactivate Views
```

---

## 4. Resilience & Circuit Breaker Logic

This detail diagram shows how the system handles external LLM API outages using backoffs, cooldowns, and fallbacks.

```mermaid
flowchart TD
    Request["1. Application initiates LLMRouter Request"] --> Budget{"2. Check daily limit?"}
    
    Budget -- Limit exceeded --> RaiseBudgetError["Raise Budget Limit Error"]
    
    Budget -- Within budget --> GetProvider["3. Select Primary Provider"]
    
    GetProvider --> CheckCircuit{"4. Is Provider Circuit Open?"}
    
    CheckCircuit -- Open (On Cooldown) --> NextProvider["5. Try Fallback Provider"]
    NextProvider --> GetProvider
    
    CheckCircuit -- Closed (Healthy) --> CallAPI["6. Call Provider Endpoint"]
    
    CallAPI --> CheckSuccess{"7. API Call Successful?"}
    
    CheckSuccess -- Yes --> LogUsage["8. Log LLMUsageEvent & Return data"]
    
    CheckSuccess -- No (Exception) --> Classify["9. Classify Error (resilience.classify_error)"]
    
    Classify -- Transient (e.g. Timeout/503) --> RetryBackoff["10. Exponential Backoff Retry"]
    RetryBackoff --> CallAPI
    
    Classify -- Non-Transient (e.g. Auth/Permanent) --> IncFail["11. Increment Provider Fail Count"]
    
    IncFail --> CheckMaxFail{"12. Fail count >= 5?"}
    
    CheckMaxFail -- Yes --> TripCircuit["13. Trip Circuit (Open Circuit for 300s)"]
    TripCircuit --> NextProvider
    
    CheckMaxFail -- No --> NextProvider
    
    style CheckCircuit fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px
    style CheckSuccess fill:#e1f5fe,stroke:#01579b,stroke-width:1px
    style LogUsage fill:#d1c4e9,stroke:#512da8,stroke-width:1px
    style TripCircuit fill:#ffebee,stroke:#c62828,stroke-width:2px
```

---

## 5. Channel webhook entrypoint flow (Telegram/Discord)

```mermaid
sequenceDiagram
    autonumber
    actor Chat as Operator on Chat Platform
    participant Webhook as Telegram/Discord API
    participant View as core.views.webhook_receiver
    participant Channel as core.channels (ChannelAdapter)
    participant Tasks as core.tasks
    participant DB as Database (SQLite)

    Chat->>Webhook: Send command: "/status" or "/discovery"
    Webhook->>View: POST /webhooks/telegram/ or /webhooks/discord/
    activate View
    View->>DB: Query configuration details & allowlists
    DB-->>View: Verified chat user is allowlisted

    View->>Channel: parse_incoming_message(payload)
    activate Channel
    Channel->>Channel: Resolve command routing
    
    alt Command is /status
        Channel->>DB: Fetch latest Application stats & usage
        DB-->>Channel: Stats payload
        Channel-->>View: Formatted text response
    else Command is /discovery
        Channel->>Tasks: Enqueue run_discovery_task (async)
        Channel-->>View: Formatted message: "Started discovery task."
    end
    deactivate Channel

    View-->>Webhook: Return HTTP 200 OK (Response text)
    Webhook-->>Chat: Render bot response bubble
    deactivate View
```

---

## 6. Secure Login & Session Authentication Flow

This flow maps the authentication enforcement gate for users accessing any dashboard view.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator (Browser)
    participant Middleware as core.middleware (LoginRequiredMiddleware)
    participant Auth as Django Auth View (login)
    participant Template as templates.registration.login
    participant DB as Database (SQLite)
    participant Dashboard as core.views.job_queue

    User->>Middleware: GET /jobs/queue/ (Request Page)
    activate Middleware
    Note over Middleware: Intercepts request to verify session
    
    alt User is authenticated
        Middleware->>Dashboard: Allow access
        activate Dashboard
        Dashboard-->>User: Render Dashboard HTML
        deactivate Dashboard
    else User is NOT authenticated
        alt Request is AJAX/Fetch API
            Middleware-->>User: Return HTTP 401 JSON {"success": false, "error": "Authentication required."}
        else Request is normal browser page load
            Middleware-->>User: HTTP 302 Redirect to /accounts/login/?next=/jobs/queue/
            deactivate Middleware
            
            activate Auth
            Auth->>Template: Render login template
            Template-->>User: Display beautiful login form
            User->>Auth: POST /accounts/login/ (username + password)
            Auth->>DB: Query user records & verify credentials password hash
            DB-->>Auth: Verification successful
            Auth-->>User: HTTP 302 Redirect to original target (/jobs/queue/)
            deactivate Auth
        end
    end
```

---

## 7. Secure Database Keys Encryption & Decryption Flow

This flow details how API keys are encrypted at rest and dynamically decrypted during LLM calls.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator (Browser)
    participant View as core.views.provider_settings
    participant DB as Database (SQLite)
    participant Encryption as core.encryption (Fernet)
    participant Router as core.llm (LLMRouter)
    participant API as LLM Endpoint (Gemini/OpenAI)

    Note over User,View: Part A: Saving credentials
    User->>View: POST /settings/providers/ (action=save_keys, key_value)
    activate View
    View->>Encryption: encrypt_value(key_value)
    activate Encryption
    Note over Encryption: Symmetrically encrypts using FIELD_ENCRYPTION_KEY (AES-128)
    Encryption-->>View: Encrypted ciphertext string
    deactivate Encryption
    View->>DB: UPDATE SecureCredential (encrypted_value)
    DB-->>View: Success
    View-->>User: Redirect back to settings page (masked key shown)
    deactivate View

    Note over Router,API: Part B: Decrypting credentials for API call
    Router->>DB: SecureCredential.get_val(key_name)
    activate Router
    activate DB
    DB-->>Router: Encrypted ciphertext string
    deactivate DB
    
    alt Ciphertext exists in DB
        Router->>Encryption: decrypt_value(ciphertext)
        activate Encryption
        Encryption-->>Router: Plaintext API Key
        deactivate Encryption
    else No DB record
        Router->>Router: Fallback to environment variables (os.getenv)
    end
    
    Router->>API: Generate request using decrypted API Key
    activate API
    API-->>Router: Response payload
    deactivate API
    deactivate Router
```

