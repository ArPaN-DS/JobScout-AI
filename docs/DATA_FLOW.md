# Data Flow Diagram

## Overview

This document provides detailed data flow diagrams showing how information moves through the Job_bro_AI system across different operations and use cases.

---

## 1. Resume Upload & Profile Extraction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     RESUME UPLOAD FLOW                          │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ User Browser │
└──────┬───────┘
       │ 1. POST /upload-resume
       │ (multipart/form-data)
       ▼
┌─────────────────────────────┐
│ Django Web Server           │
│ (core/views.py:            │
│  ProfileUploadView)         │
└──────────────┬──────────────┘
       │ 2. Validate file type
       │    (PDF, DOCX)
       │ 3. Check file size
       │ 4. Store in tmp_uploads/
       ▼
┌─────────────────────────────┐
│ File Storage                │
│ tmp_uploads/resume.pdf      │
└──────────────┬──────────────┘
       │ 5. Extract text using pdfplumber
       │    or python-docx
       ▼
┌─────────────────────────────────────┐
│ core/evidence_scanner.py            │
│ extract_document_text()             │
├─────────────────────────────────────┤
│ • Parse PDF/DOCX structure          │
│ • Handle encoding issues            │
│ • Clean whitespace & formatting     │
│ • Identify sections                 │
└──────────────┬──────────────────────┘
       │ 6. Extracted text (string)
       │    ~5-10KB
       ▼
┌─────────────────────────────────────┐
│ core/ai_service.py                  │
│ extract_profile_from_document()     │
├─────────────────────────────────────┤
│ Create LLMRequest:                  │
│ {                                   │
│   "task": "EXTRACT_PROFILE",        │
│   "prompt": "Extract these fields",│
│   "input_text": "...resume...",    │
│   "schema": MasterProfile           │
│ }                                   │
└──────────────┬──────────────────────┘
       │ 7. Route to LLM provider
       ▼
┌─────────────────────────────────────┐
│ core/llm.py                         │
│ LLMRouter.route()                   │
├─────────────────────────────────────┤
│ Check enabled providers:            │
│ • Gemini?                           │
│ • OpenAI?                           │
│ • Claude?                           │
│ • Others?                           │
│                                     │
│ Return: LLMRequest with provider    │
└──────────────┬──────────────────────┘
       │ 8. Provider order:
       │    [Gemini, OpenAI, Claude, Groq]
       ▼
┌─────────────────────────────────────┐
│ Gemini API                          │
│ POST /v1beta/generateContent        │
├─────────────────────────────────────┤
│ Request:                            │
│ • Model: gemini-2.5-pro             │
│ • Prompt: extraction task           │
│ • Resume text: full content         │
│                                     │
│ Response: JSON with extracted data  │
└──────────────┬──────────────────────┘
       │ 9. LLMResult returned
       │    {
       │      "status": "success",
       │      "output": {...},
       │      "tokens_used": 450,
       │      "provider": "gemini",
       │      "timestamp": "..."
       │    }
       ▼
┌─────────────────────────────────────┐
│ core/ai_service.py                  │
│ _parse_response()                   │
├─────────────────────────────────────┤
│ • Extract JSON from response        │
│ • Parse error messages              │
│ • Handle edge cases                 │
└──────────────┬──────────────────────┘
       │ 10. Parsed data (dict)
       ▼
┌─────────────────────────────────────┐
│ core/schemas.py                     │
│ MasterProfile validation            │
├─────────────────────────────────────┤
│ Pydantic validation:                │
│ • Check required fields             │
│ • Validate data types               │
│ • Apply constraints                 │
│ • Raise ValidationError if invalid  │
│                                     │
│ Output: Validated MasterProfile     │
└──────────────┬──────────────────────┘
       │ 11. Valid profile object
       ▼
┌─────────────────────────────────────┐
│ core/models.py                      │
│ CandidateProfile.objects.create()   │
├─────────────────────────────────────┤
│ Create database record:             │
│ • extracted_profile: AI data (JSON) │
│ • status: "review_required"         │
│ • created_at: now()                 │
│                                     │
│ Return: CandidateProfile instance   │
└──────────────┬──────────────────────┘
       │ 12. SQL INSERT
       │     (db.sqlite3)
       ▼
┌─────────────────────────────────────┐
│ SQLite Database                     │
│ core_candidateprofile table         │
├─────────────────────────────────────┤
│ Record stored:                      │
│ • id: 1                             │
│ • extracted_profile: {...}  (JSON)  │
│ • confirmed_profile: {}     (JSON)  │
│ • status: review_required           │
│ • created_at: 2026-05-31T10:30:00  │
│ • updated_at: 2026-05-31T10:30:00  │
└──────────────┬──────────────────────┘
       │ 13. Response to browser
       ▼
┌─────────────────────────────────────┐
│ User Browser                        │
│ Profile Review Page                 │
├─────────────────────────────────────┤
│ Display extracted data in form:     │
│ ✎ [Full Name: John Doe]             │
│ ✎ [Email: john@example.com]         │
│ ✎ [Skills: Python, Django, ...]     │
│ ✎ [Experience: ...]                 │
│                                     │
│ Actions:                            │
│ [Confirm] [Edit] [Regenerate]       │
└─────────────────────────────────────┘
       │ 14. User clicks "Confirm"
       ▼
┌─────────────────────────────────────┐
│ core/models.py                      │
│ CandidateProfile.save()             │
├─────────────────────────────────────┤
│ Update database:                    │
│ • confirmed_profile: edited data    │
│ • status: "ready"                   │
│ • updated_at: now()                 │
└─────────────────────────────────────┘
       │
       ▼
   Ready for job matching!

```

---

## 2. Job Matching & Application Generation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              JOB MATCHING & APPLICATION FLOW                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│ Dashboard View       │
│ "Browse Jobs"        │
└──────────┬───────────┘
           │ 1. GET /jobs
           ▼
┌──────────────────────────────────────┐
│ Django Views                         │
│ (core/views.py: JobListView)         │
├──────────────────────────────────────┤
│ Query: JobLead.objects.all()         │
│ Order by: match_score DESC           │
│ Paginate: 20 per page                │
└──────────────┬───────────────────────┘
           │ 2. SQL SELECT
           │    (db.sqlite3)
           ▼
┌──────────────────────────────────────┐
│ SQLite Database                      │
│ core_joblead table                   │
├──────────────────────────────────────┤
│ Rows returned:                       │
│ [{                                   │
│   "id": 1,                           │
│   "title": "Senior Python Dev",      │
│   "company": "TechCorp",             │
│   "description": "We need...",       │
│   "requirements": "5+ years...",     │
│   "match_score": null  (not yet)     │
│ }, ...]                              │
└──────────────┬───────────────────────┘
           │ 3. Render in browser
           ▼
┌──────────────────────────────────────┐
│ User Browser                         │
│ Job List Page                        │
├──────────────────────────────────────┤
│ [1] Senior Python Dev - TechCorp     │
│     Location: San Francisco          │
│     [Score Job] [Preview]            │
│                                      │
│ [2] Full Stack Engineer - StartupXYZ │
│     Location: Remote                 │
│     [Score Job] [Preview]            │
│                                      │
│ ... more jobs ...                    │
└──────────────┬───────────────────────┘
           │ 4. User clicks "Score Job"
           ▼
┌──────────────────────────────────────┐
│ core/views.py: ScoreJobView          │
│ POST /jobs/{id}/score                │
├──────────────────────────────────────┤
│ Get job & candidate profile from DB  │
│ Create scoring request               │
└──────────────┬───────────────────────┘
           │ 5. Fetch job details
           │    and candidate data
           ▼
┌──────────────────────────────────────┐
│ core/ai_service.py                   │
│ evaluate_job_match()                 │
├──────────────────────────────────────┤
│ Create evaluation prompt:            │
│ "Given this candidate profile and    │
│  this job description, score the     │
│  match on: skill alignment (0-100),  │
│  experience match (0-100), growth    │
│  potential (0-100)"                  │
│                                      │
│ Include:                             │
│ • Candidate: skills, experience      │
│ • Job: requirements, description     │
│ • Preferences: filters to apply      │
└──────────────┬───────────────────────┘
           │ 6. Route to LLM
           ▼
┌──────────────────────────────────────┐
│ core/llm.py: LLMRouter               │
│ route_request()                      │
├──────────────────────────────────────┤
│ Provider selection:                  │
│ • Check GEMINI_API_KEY               │
│ • Check cooldown status              │
│ • Check rate limits                  │
│ • Select: Gemini                     │
└──────────────┬───────────────────────┘
           │ 7. Call Gemini API
           │    with scoring prompt
           ▼
┌──────────────────────────────────────┐
│ Google Gemini API                    │
│ Models: gemini-2.5-pro               │
├──────────────────────────────────────┤
│ Request:                             │
│ • Model: gemini-2.5-pro              │
│ • Prompt: evaluation task            │
│ • Temperature: 0.3 (low variance)    │
│                                      │
│ Response:                            │
│ {                                    │
│   "skill_match": 85,                 │
│   "experience_match": 90,            │
│   "growth_potential": 75,            │
│   "overall_score": 83,               │
│   "reasoning": "Strong Python..."    │
│ }                                    │
└──────────────┬───────────────────────┘
           │ 8. Parse response
           ▼
┌──────────────────────────────────────┐
│ core/ai_service.py                   │
│ _parse_response()                    │
├──────────────────────────────────────┤
│ • Extract JSON                       │
│ • Parse score fields                 │
│ • Validate ranges (0-100)            │
│ • Create MatchResult object          │
└──────────────┬───────────────────────┘
           │ 9. Store in database
           ▼
┌──────────────────────────────────────┐
│ core/models.py: JobLead              │
│ Update: match_score, reasoning       │
├──────────────────────────────────────┤
│ UPDATE core_joblead SET              │
│   match_score = 83,                  │
│   ai_metadata = {...}                │
│ WHERE id = 1                         │
└──────────────┬───────────────────────┘
           │ 10. Display result
           │     to user
           ▼
┌──────────────────────────────────────┐
│ User Browser                         │
│ Job Detail Page                      │
├──────────────────────────────────────┤
│ ★★★★ 83/100 Match Score             │
│                                      │
│ Skill Alignment: 85%                 │
│ Experience Match: 90%                │
│ Growth Potential: 75%                │
│                                      │
│ Reasoning: "You have strong Python   │
│ experience matching the role..."     │
│                                      │
│ [Generate Application] [Save] [Skip] │
└──────────────┬───────────────────────┘
           │ 11. User clicks
           │     "Generate Application"
           ▼
┌──────────────────────────────────────┐
│ core/views.py                        │
│ GenerateApplicationView              │
│ POST /jobs/{id}/generate-app         │
├──────────────────────────────────────┤
│ Enqueue background task:             │
│ • Job ID                             │
│ • Candidate ID                       │
│ • Generation task                    │
└──────────────┬───────────────────────┘
           │ 12. Task queued
           │     (django-q2)
           ▼
┌──────────────────────────────────────┐
│ Background Task Queue                │
│ (django-q2)                          │
└──────────────┬───────────────────────┘
           │ 13. Worker picks up task
           ▼
┌──────────────────────────────────────┐
│ core/tasks.py                        │
│ generate_application_kit()           │
├──────────────────────────────────────┤
│ Input:                               │
│ • candidate_profile (from DB)        │
│ • job_lead (from DB)                 │
│ • evidence_mapping (from DB)         │
│                                      │
│ Process:                             │
│ 1. Prepare context                   │
│ 2. Fetch candidate's master profile  │
│ 3. Load job requirements             │
│ 4. Get evidence claims               │
└──────────────┬───────────────────────┘
           │ 14. Spawn multiple
           │     concurrent AI tasks
           ▼
      ┌────┬────┬────┬─────┐
      │    │    │    │     │
      ▼    ▼    ▼    ▼     ▼
    ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐
    │1 │ │2 │ │3 │ │4 │ │5 │
    │  │ │  │ │  │ │  │ │  │
    └──┘ └──┘ └──┘ └──┘ └──┘
     │    │    │    │    │
     Task 1: Resume Tailoring
     • Customize resume for job
     • Highlight relevant skills
     • Optimize for ATS
     → LLM call
     ▼ → Tailored resume JSON

     Task 2: Cover Letter Generation
     • Write compelling letter
     • Personal touch
     • Company research
     → LLM call
     ▼ → Cover letter text

     Task 3: Recruiter Message
     • Professional outreach
     • Clear value prop
     • Call to action
     → LLM call
     ▼ → Recruiter message

     Task 4: Follow-up Message
     • Strategic follow-up
     • Non-pushy tone
     • Reference email
     → LLM call
     ▼ → Follow-up message

     Task 5: Interview Prep
     • Likely questions
     • Key talking points
     • Company insights
     → LLM call
     ▼ → Interview prep notes

      All tasks complete (parallel execution)
      │
      └────┬────┬────┬─────┘
           │
           ▼
┌──────────────────────────────────────┐
│ core/auto_applier.py                 │
│ assemble_kit()                       │
├──────────────────────────────────────┤
│ Combine all components into:         │
│ ApplicationKit {                     │
│   "resume": {...},                   │
│   "cover_letter": "...",             │
│   "recruiter_message": "...",        │
│   "follow_up_message": "...",        │
│   "interview_prep": {...},           │
│   "evidence_mapping": [...]          │
│ }                                    │
└──────────────┬───────────────────────┘
           │ 15. Validate kit
           ▼
┌──────────────────────────────────────┐
│ core/schemas.py                      │
│ validate_grounded_kit()              │
├──────────────────────────────────────┤
│ Check:                               │
│ • All components present             │
│ • No empty strings                   │
│ • Evidence properly linked           │
│ • Schema compliance                  │
│                                      │
│ Return: Valid ApplicationKit         │
└──────────────┬───────────────────────┘
           │ 16. Store in database
           ▼
┌──────────────────────────────────────┐
│ core/models.py: Application          │
│ objects.create()                     │
├──────────────────────────────────────┤
│ INSERT INTO core_application:        │
│ • job_lead_id: 1                     │
│ • candidate_id: 1                    │
│ • kit_data: {full kit JSON}          │
│ • status: "ready"                    │
│ • generated_at: now()                │
│ • ai_metadata: {model, tokens...}    │
└──────────────┬───────────────────────┘
           │ 17. Notify user
           │     (WebSocket/polling)
           ▼
┌──────────────────────────────────────┐
│ User Browser                         │
│ Application Ready Page               │
├──────────────────────────────────────┤
│ ✓ Application Kit Generated!         │
│                                      │
│ [Review Resume]                      │
│ [Review Cover Letter]                │
│ [Review Recruiter Message]           │
│ [Review Interview Prep]              │
│                                      │
│ [Edit] [Submit] [Save PDF] [Cancel]  │
└──────────────┬───────────────────────┘
           │ 18. User reviews
           │     and clicks
           │     "Submit"
           ▼
┌──────────────────────────────────────┐
│ core/models.py: Application          │
│ mark_submitted()                     │
├──────────────────────────────────────┤
│ UPDATE:                              │
│ • status: "submitted"                │
│ • submitted_at: now()                │
│ • user_edits: {if any}               │
│                                      │
│ Archive for tracking                 │
└──────────────┬───────────────────────┘
           │
           ▼
      Application saved
      and tracked!

```

---

## 3. Error Handling & Fallback Flow

```
┌─────────────────────────────────────────────────────────────────┐
│           LLM ERROR HANDLING & FALLBACK FLOW                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┐
│ LLM Request Initiated                │
│ (core/ai_service.py)                 │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ core/llm.py: LLMRouter               │
│ route_request()                      │
├──────────────────────────────────────┤
│ 1. Check enabled providers           │
│ 2. Get provider priority order       │
│ 3. Start with first provider         │
│    (e.g., Gemini)                    │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Provider 1: Gemini                   │
│ (Call API)                           │
├──────────────────────────────────────┤
│ Try:                                 │
│   • Set request timeout: 30s         │
│   • Call Gemini API                  │
│   • Get response                     │
│   • Check HTTP status code           │
│                                      │
│ Except:                              │
│   • Timeout Error                    │
│   • Network Error                    │
│   • API Error (status != 200)        │
└──────────────┬───────────────────────┘
           │
    ┌──────┴──────────────┐
    │                     │
Success?              Error?
    │                     │
    │ YES                 │ NO
    │                     │
    ▼                     ▼
Return          ┌──────────────────────┐
response        │ Parse error type     │
│               ├──────────────────────┤
│               │ Error Classification │
│               └──────────────────────┘
│                    │
│            ┌───────┼───────┬──────────┐
│            │       │       │          │
│       Rate   Quota  Server  Timeout  Auth
│      Limit  Error   Error   Error    Error
│            │       │       │          │
│            ▼       ▼       ▼          ▼
│        Cool- Skip   Retry  Retry   Fail
│        down  Prov.  Next   Next    Fast
│        │       │     Prov  Prov    │
│        │       │       │    │       │
│        └───────┴───────┼────┘       │
│                        │            │
│             ┌──────────┴────────┐   │
│             │                  │   │
│             ▼                  ▼   ▼
│      ┌─────────────────────────────────┐
│      │ Exponential Backoff Retry       │
│      ├─────────────────────────────────┤
│      │ Initial delay: 1s               │
│      │ Max retries: 3                  │
│      │ Multiplier: 2x                  │
│      │ Max delay: 30s                  │
│      │                                 │
│      │ Attempt 1: Retry after 1s       │
│      │ Attempt 2: Retry after 2s       │
│      │ Attempt 3: Retry after 4s       │
│      │ All failed: → Next provider     │
│      └────────────────┬────────────────┘
│                       │
└───────────────────────┤
                        │
                        ▼
              ┌─────────────────────────┐
              │ Provider 2: OpenAI      │
              │ (Call API)              │
              ├─────────────────────────┤
              │ Repeat same error       │
              │ handling logic          │
              │                         │
              │ Success? → Return       │
              │ Error? → Next provider  │
              └────────────────┬────────┘
                               │
                  ┌────────────┴──────────┐
                  │                       │
              Success?               Error?
                  │ YES                   │ NO
                  │                       │
                  ▼                       ▼
            Return result       Provider 3: Claude
                │               (Continue loop)
                │                       │
                │                  ┌────┴────┐
                │              S?      Error?
                │              │            │
                ▼              ▼            ▼
            [All Success]  Return    Provider 4, 5...

                           If ALL providers fail:
                           │
                           ▼
                ┌──────────────────────────────┐
                │ All Providers Failed         │
                ├──────────────────────────────┤
                │ Generate helpful error UI:   │
                │                              │
                │ ❌ Application generation    │
                │    failed.                   │
                │                              │
                │ Next steps:                  │
                │ 1. ⏱️  Wait 2 minutes and     │
                │       try again              │
                │ 2. 🔑 Enable another LLM     │
                │       provider               │
                │ 3. 🏠 Turn on local Ollama   │
                │ 4. 🔄 Retry manually         │
                │ 5. ⏭️  Continue without AI   │
                │       (manual entry)         │
                │                              │
                │ [Show detailed error log]    │
                └──────────────────────────────┘
                           │
                           ▼
                     User selects action

```

---

## 4. Multi-Channel Message Flow

```
┌─────────────────────────────────────────────────────────────────┐
│          TELEGRAM BOT MESSAGE HANDLING FLOW                     │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐
│ Telegram User            │
│ Sends Message: "/jobs"   │
└──────────────┬───────────┘
               │
               │ Telegram API
               │ forwards to webhook
               ▼
┌────────────────────────────────────────────┐
│ Django Webhook Endpoint                    │
│ POST /telegram/webhook                     │
│ (core/channels.py)                         │
├────────────────────────────────────────────┤
│ Receive JSON:                              │
│ {                                          │
│   "message": {                             │
│     "from": {"id": 123456789},             │
│     "text": "/jobs",                       │
│     "chat": {"id": 123456789}              │
│   }                                        │
│ }                                          │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ core/channels.py                           │
│ TelegramHandler.handle_message()           │
├────────────────────────────────────────────┤
│ 1. Extract user_id from message            │
│ 2. Check allowlist:                        │
│    if user_id not in ALLOWED_CHAT_IDS:     │
│      → Send "Access Denied"                │
│      → Log security event                  │
│      → Return 403                          │
│                                            │
│ 3. Parse command: "/jobs"                  │
│ 4. Route to handler                        │
└──────────────┬─────────────────────────────┘
               │
         Valid user
               │
               ▼
┌────────────────────────────────────────────┐
│ Command Router                             │
│ (core/channels.py: COMMAND_HANDLERS)       │
├────────────────────────────────────────────┤
│ Commands:                                  │
│ • /jobs → list recent jobs                 │
│ • /score → score a job                     │
│ • /apply → generate application            │
│ • /profile → show profile summary          │
│ • /settings → manage settings              │
│ • /help → show help                        │
│                                            │
│ Dispatch: handlers["/jobs"]()              │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ Handler Function                           │
│ handle_list_jobs()                         │
├────────────────────────────────────────────┤
│ 1. Query database for recent jobs          │
│    JobLead.objects.filter(               │
│      created_at__gte=today(),             │
│      match_score__gte=60                  │
│    ).order_by('-match_score')[:5]         │
│                                            │
│ 2. Format for Telegram:                    │
│    "Recent Top Jobs:"                      │
│    "1. Senior Python Dev @ TechCorp"       │
│       "📍 San Francisco"                   │
│       "⭐ 85/100 match"                    │
│    "2. Full Stack @ StartupXYZ"            │
│       "📍 Remote"                          │
│       "⭐ 78/100 match"                    │
│                                            │
│ 3. Add keyboard buttons:                   │
│    [/score 1] [/score 2] [/score 3]       │
│    [/apply 1] [/apply 2] [/apply 3]       │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ Telegram API Call                          │
│ sendMessage()                              │
├────────────────────────────────────────────┤
│ POST: https://api.telegram.org/            │
│       botTOKEN/sendMessage                 │
│                                            │
│ Payload:                                   │
│ {                                          │
│   "chat_id": 123456789,                    │
│   "text": "Recent Top Jobs: ...",          │
│   "reply_markup": {                        │
│     "keyboard": [[...buttons...]]          │
│   }                                        │
│ }                                          │
│                                            │
│ Response:                                  │
│ {"ok": true, "result": {...}}              │
└──────────────┬─────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Telegram User                            │
│ Receives formatted message with buttons  │
│                                          │
│ Recent Top Jobs:                         │
│ 1. Senior Python Dev @ TechCorp          │
│    📍 San Francisco                      │
│    ⭐ 85/100 match                       │
│ [/score 1] [/apply 1]                    │
│                                          │
│ 2. Full Stack @ StartupXYZ               │
│    📍 Remote                             │
│    ⭐ 78/100 match                       │
│ [/score 2] [/apply 2]                    │
│                                          │
│ User clicks: [/apply 1]                  │
└────────────────┬─────────────────────────┘
                 │
                 │ Telegram sends callback
                 ▼
        ┌────────────────────┐
        │ Repeat cycle       │
        │ with new command   │
        │ /apply 1           │
        │                    │
        │ → Background task  │
        │   enqueued         │
        │ → Generate app kit │
        │ → Send result      │
        │   back to user     │
        └────────────────────┘

```

---

## 5. Task Queue & Async Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│         DJANGO-Q2 BACKGROUND TASK PROCESSING FLOW              │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│ User Action      │
│ "Apply to Job"   │
└──────────┬───────┘
           │
           ▼
┌──────────────────────────────────────┐
│ core/views.py                        │
│ GenerateApplicationView              │
├──────────────────────────────────────┤
│ POST /jobs/{id}/generate-app         │
│                                      │
│ Instead of waiting:                  │
│ • Create Task object                 │
│ • Queue with django-q2               │
│ • Respond immediately to user        │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ core/tasks.py                        │
│ Queue task:                          │
│   async_task(                        │
│     'core.tasks.generate_app_kit',   │
│     job_id=123,                      │
│     candidate_id=456,                │
│     hook_failed='core.tasks.err_h'   │
│   )                                  │
├──────────────────────────────────────┤
│ Returns: Task ID (UUID)              │
│ Store in cache/session               │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Response to browser:                 │
│ "Application generation started!"    │
│ "Status: Pending..."                 │
│ [Refresh] [Go Back]                  │
└──────────────┬───────────────────────┘
           │
           │ Browser polls via AJAX
           │ GET /jobs/{id}/app-status
           ▼
┌──────────────────────────────────────┐
│ Task Queue (ORM Store)               │
│ core_task table                      │
├──────────────────────────────────────┤
│ {                                    │
│   "id": "abc-123-def",               │
│   "func": "core.tasks.gen_app_kit",  │
│   "args": "[123, 456]",              │
│   "kwargs": "{}",                    │
│   "created": "2026-05-31T10:30:00",  │
│   "started": null,                   │
│   "stopped": null,                   │
│   "result": null,                    │
│   "status": "pending"                │
│ }                                    │
└──────────────┬───────────────────────┘
           │
      django-q2 Cluster
           │
           ▼
┌──────────────────────────────────────┐
│ Task Worker (Process)                │
│ ORM Store Scheduler picks up task    │
├──────────────────────────────────────┤
│ 1. Get task from queue               │
│ 2. Update status: "started"          │
│ 3. Execute function:                 │
│    generate_app_kit(123, 456)         │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Task Execution                       │
│ (core/tasks.py:                      │
│  generate_app_kit)                   │
├──────────────────────────────────────┤
│ 1. Fetch job from DB                 │
│ 2. Fetch candidate from DB           │
│ 3. Get evidence claims               │
│ 4. Prepare context                   │
│ 5. Call AI services:                 │
│    • resume_tailor()                 │
│    • gen_cover_letter()              │
│    • gen_recruiter_msg()             │
│    • gen_interview_prep()            │
│    (These are concurrent/parallel)   │
│ 6. Assemble application kit          │
│ 7. Validate                          │
│ 8. Store in database                 │
│                                      │
│ Return: {                            │
│   "status": "success",               │
│   "application_id": 789,             │
│   "generated_at": "..."              │
│ }                                    │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Task Complete                        │
│ Update task in queue:                │
│ • status: "success"                  │
│ • result: {...}                      │
│ • stopped: now()                     │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Browser polling continues            │
│ GET /jobs/{id}/app-status            │
│                                      │
│ Response:                            │
│ {                                    │
│   "status": "success",               │
│   "application_id": 789              │
│ }                                    │
├──────────────────────────────────────┤
│ Browser redirects to:                │
│ /applications/789                    │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ User sees completed application      │
│ Ready for review & submission         │
└──────────────────────────────────────┘

If task fails:
           │
           ▼
┌──────────────────────────────────────┐
│ Exception during execution           │
├──────────────────────────────────────┤
│ Try-except catches error             │
│ Calls hook_failed:                   │
│   error_handler()                    │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Update task:                         │
│ • status: "failed"                   │
│ • result: {error details}            │
│ • error_message: str(exception)      │
└──────────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Notify user:                         │
│ "Application generation failed"      │
│ [Retry] [Manual Entry] [Help]        │
└──────────────────────────────────────┘

```

---

## Data Structure Examples

### MasterProfile JSON

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1-555-0123",
  "location": "San Francisco, CA",
  "work_authorization": "US Citizen",
  "availability": "2 weeks notice",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "github_url": "https://github.com/johndoe",
  "portfolio_url": "https://johndoe.dev",
  "skills": [
    {
      "name": "Python",
      "proficiency": 5,
      "years": 7,
      "evidence": ["TechCorp 3 years", "StartupXYZ 4 years"]
    },
    {
      "name": "Django",
      "proficiency": 4,
      "years": 5,
      "evidence": ["TechCorp: Built REST API"]
    }
  ],
  "experience": [
    {
      "title": "Senior Software Engineer",
      "company": "TechCorp",
      "start_date": "2021-01",
      "end_date": "2024-12",
      "description": "Lead full-stack development...",
      "achievements": [
        "Improved API performance by 40%",
        "Mentored 3 junior developers"
      ]
    }
  ],
  "education": [
    {
      "degree": "B.S. Computer Science",
      "school": "State University",
      "graduation_year": 2017,
      "gpa": "3.8"
    }
  ]
}
```

### Application Kit JSON

```json
{
  "job_id": 123,
  "resume": {
    "format": "ATS-optimized",
    "sections": {
      "header": "...",
      "summary": "...",
      "experience": [...],
      "skills": [...]
    }
  },
  "cover_letter": "Dear Hiring Manager, ...",
  "recruiter_message": "Hi [Name], ...",
  "follow_up_message": "Hello [Team], ...",
  "interview_prep": {
    "likely_questions": [...],
    "key_points": [...],
    "company_info": {...}
  },
  "evidence_mapping": [
    {
      "requirement": "5+ years Python",
      "evidence": ["7 years total: TechCorp (3yr), StartupXYZ (4yr)"],
      "confidence": 0.98
    }
  ]
}
```

---

## Key Takeaways

1. **Asynchronous Processing**: Long-running tasks use django-q2 to avoid blocking user experience
2. **Automatic Fallback**: LLM providers are tried in sequence with intelligent error handling
3. **Human-in-the-Loop**: At every stage, users can review and edit AI-generated content
4. **Multi-Channel Support**: Same data flows through Web UI, Telegram, Discord seamlessly
5. **Error Resilience**: Clear user guidance when failures occur
6. **Database Efficiency**: Indexed queries for fast access patterns
7. **Privacy**: All processing happens locally; no data sent to external services except LLM APIs
