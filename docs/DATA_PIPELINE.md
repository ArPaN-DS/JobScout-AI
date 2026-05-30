# Data Pipeline

## Overview

The Job_bro_AI data pipeline processes candidate profiles and jobs through multiple AI-powered stages to generate tailored applications.

---

## Complete Data Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          JOB_BRO_AI DATA PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────────┘


STAGE 1: INTAKE & PREPARATION
════════════════════════════════════════════════════════════════════════════════

┌──────────────────────────────────────┐
│   User Inputs                        │
├──────────────────────────────────────┤
│ • Resume (PDF/DOCX)                  │
│ • Job descriptions (text/URL)        │
│ • Preferences (location, salary)     │
│ • API keys (Gemini, OpenAI, etc)     │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Data Validation & Normalization                             │
├──────────────────────────────────────────────────────────────┤
│ • File format check (PDF → text extraction)                  │
│ • Character encoding validation                              │
│ • File size limits enforcement                               │
│ • Pydantic schema validation                                 │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Temporary Storage                                            │
├──────────────────────────────────────────────────────────────┤
│ • tmp_uploads/ directory                                     │
│ • tmp_uploads/resume.pdf → text cache                        │
│ • Staged for processing                                      │
└────────────────┬─────────────────────────────────────────────┘


STAGE 2: FEATURE EXTRACTION (AI-Powered)
════════════════════════════════════════════════════════════════════════════════

                 ▼
    ┌────────────────────────────┐
    │ Resume Text Extraction     │
    │ (evidence_scanner.py)      │
    ├────────────────────────────┤
    │ Input: Raw resume text     │
    │ Process:                   │
    │  • Parse structure         │
    │  • Extract entities        │
    │  • Identify sections       │
    │ Output: Structured data    │
    └────────────────┬───────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │Contact  │  │Experience│  │Education │
    │Info     │  │& Skills  │  │& Certs   │
    ├──────────┤  ├──────────┤  ├──────────┤
    │• Name    │  │• Title   │  │• Degree  │
    │• Email   │  │• Company │  │• School  │
    │• Phone   │  │• Duration│  │• Year    │
    │• Location│  │• Skills  │  │• Major   │
    │• Links   │  │• Achievements│• Certs │
    └──────────┘  └──────────┘  └──────────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ LLM-Powered Extraction               │
    │ (ai_service.py + llm.py)             │
    ├──────────────────────────────────────┤
    │ Input: Structured candidate data     │
    │ LLM Task:                            │
    │  1. Standardize job titles           │
    │  2. Categorize skills                │
    │  3. Extract achievements             │
    │  4. Identify certifications          │
    │  5. Validate completeness            │
    │ Provider Routing:                    │
    │  • Primary: Gemini                   │
    │  • Fallback: OpenAI, Claude, etc     │
    │ Output: Validated JSON               │
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────┐
    │ Schema Validation                    │
    │ (schemas.py - Pydantic)              │
    ├──────────────────────────────────────┤
    │ MasterProfile schema:                │
    │ {                                    │
    │   "name": "John Doe",                │
    │   "email": "john@example.com",       │
    │   "skills": [                        │
    │     {"name": "Python", "level": 5},  │
    │     {"name": "Django", "level": 4}   │
    │   ],                                 │
    │   "experience": [                    │
    │     {                                │
    │       "title": "Senior Dev",         │
    │       "company": "TechCorp",         │
    │       "duration": "3 years"          │
    │     }                                │
    │   ],                                 │
    │   ...                                │
    │ }                                    │
    └──────────────┬──────────────────────┘


STAGE 3: DATABASE STORAGE
════════════════════════════════════════════════════════════════════════════════

                   ▼
    ┌──────────────────────────────────────────────────┐
    │ CandidateProfile Model                           │
    ├──────────────────────────────────────────────────┤
    │ Database: SQLite (db.sqlite3)                    │
    │ Fields:                                          │
    │  • id: Primary key                               │
    │  • extracted_profile: Extracted AI data (JSON)   │
    │  • confirmed_profile: Human-reviewed data (JSON) │
    │  • full_name, email, phone, location             │
    │  • linkedin_url, github_url, portfolio_url       │
    │  • status: draft / review_required / ready       │
    │  • created_at, updated_at timestamps             │
    └──────────────┬───────────────────────────────────┘
                   │
     ┌─────────────┴────────────┐
     │                          │
     ▼                          ▼
    ┌──────────────────┐  ┌──────────────────┐
    │Human Review UI   │  │Evidence Claims   │
    ├──────────────────┤  ├──────────────────┤
    │• Edit extracted  │  │Store as separate │
    │  data            │  │Evidence records  │
    │• Confirm info    │  │for linking to    │
    │• Add missing     │  │job requirements  │
    │  items           │  └──────────────────┘
    │• Mark as ready   │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ confirmed_profile JSON       │
    │ (Human-verified data)        │
    └──────────────────────────────┘


STAGE 4: JOB DISCOVERY & MATCHING
════════════════════════════════════════════════════════════════════════════════

    Input: Job opportunities
    ┌──────────────────────────────────────┐
    │ Job Sources (job_sources.py)         │
    ├──────────────────────────────────────┤
    │ • Manual import (CSV/JSON)           │
    │ • Web scraping (Python JobSpy)       │
    │ • API integrations                   │
    │ • User copy-paste                    │
    └────────────────┬─────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ Job Lead Normalization               │
    ├──────────────────────────────────────┤
    │ • Standardize job data structure     │
    │ • Clean text and encoding            │
    │ • Extract key requirements           │
    │ • Generate fingerprint hash          │
    │ • Deduplicate identical jobs         │
    └────────────────┬─────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ JobLead Model (Database)             │
    ├──────────────────────────────────────┤
    │ Fields:                              │
    │  • title, company, location          │
    │  • description, requirements         │
    │  • salary_range, job_type            │
    │  • job_url, source                   │
    │  • fingerprint (dedup hash)          │
    │  • scraped_at, created_at            │
    └────────────────┬─────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ Job Preference Filtering             │
    ├──────────────────────────────────────┤
    │ CandidatePreference Model:           │
    │  • Preferred locations               │
    │  • Min/max salary                    │
    │  • Job types (Remote, On-site)       │
    │  • Excluded companies                │
    │  • Must-have skills                  │
    │  • Nice-to-have requirements         │
    └────────────────┬─────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ Initial Filtering                    │
    ├──────────────────────────────────────┤
    │ • Location match                     │
    │ • Salary range check                 │
    │ • Job type compatibility             │
    │ • Excluded company filter            │
    │ Output: Pre-filtered job leads       │
    └────────────────┬─────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ AI Relevance Scoring (ai_service.py) │
    ├──────────────────────────────────────┤
    │ LLM Task:                            │
    │  1. Read candidate profile           │
    │  2. Read job description             │
    │  3. Score skill alignment (0-100)    │
    │  4. Score experience match (0-100)   │
    │  5. Score growth potential (0-100)   │
    │ Scoring Model:                       │
    │  {                                   │
    │    "job_id": 123,                    │
    │    "match_score": 85,                │
    │    "skill_match": 90,                │
    │    "experience_match": 80,           │
    │    "growth_potential": 85,           │
    │    "reasoning": "Strong Python..."   │
    │  }                                   │
    │ Provider Routing: Gemini → OpenAI... │
    └────────────────┬─────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │ Ranked Job Queue                     │
    ├──────────────────────────────────────┤
    │ Order by:                            │
    │  1. Match score (descending)         │
    │  2. Date posted (recent first)       │
    │  3. Company preference               │
    │ Display in UI for user review        │
    └──────────────────────────────────────┘


STAGE 5: APPLICATION KIT GENERATION
════════════════════════════════════════════════════════════════════════════════

    User selects job → Request application kit
                     │
                     ▼
    ┌──────────────────────────────────────────┐
    │ Application Kit Builder (auto_applier.py)│
    ├──────────────────────────────────────────┤
    │ Input:                                   │
    │  • Selected JobLead                      │
    │  • Candidate MasterProfile               │
    │  • Evidence claims                       │
    └────────────────┬─────────────────────────┘
                     │
     ┌───────────────┼───────────────┬─────────────────┐
     │               │               │                 │
     ▼               ▼               ▼                 ▼
    ┌────────┐  ┌─────────┐  ┌──────────┐  ┌─────────────┐
    │Resume  │  │Cover    │  │Recruiter │  │Interview    │
    │Tailor  │  │Letter   │  │Message   │  │Prep Notes   │
    └────────┘  └─────────┘  └──────────┘  └─────────────┘
     │               │               │                 │
     ▼               ▼               ▼                 ▼
    ┌────────────────────────────────────────────────────────┐
    │ Each Component (resume_tailor.py, auto_applier.py)    │
    ├────────────────────────────────────────────────────────┤
    │ AI Task:                                               │
    │  1. Read candidate profile                             │
    │  2. Read job description                               │
    │  3. Extract key requirements                           │
    │  4. Find matching experience/skills                    │
    │  5. Generate customized component                      │
    │  6. Link evidence to requirements                      │
    │ Provider: Gemini → OpenAI (with fallback)              │
    └────────────────┬──────────────────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────────────────┐
    │ Generated Application Kit (JSON)                       │
    ├────────────────────────────────────────────────────────┤
    │ {                                                      │
    │   "resume": {                                          │
    │     "format": "ATS-optimized JSON",                    │
    │     "sections": {...},                                │
    │     "generated_at": "2026-05-31T10:30:00"              │
    │   },                                                   │
    │   "cover_letter": "Dear Hiring Manager...",            │
    │   "recruiter_message": "Hi [Recruiter Name]...",      │
    │   "follow_up_message": "Hello [Hiring Team]...",      │
    │   "interview_prep": {                                  │
    │     "likely_questions": [...],                         │
    │     "key_points_to_mention": [...],                    │
    │     "company_insights": {...}                          │
    │   },                                                   │
    │   "evidence_mapping": [                                │
    │     {                                                  │
    │       "requirement": "5+ years Python",                │
    │       "evidence": ["TechCorp role: 3 yrs Python"],     │
    │       "confidence": 0.95                               │
    │     }                                                  │
    │   ]                                                    │
    │ }                                                      │
    └────────────────┬──────────────────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────┐
    │ Application Model (Database)           │
    ├────────────────────────────────────────┤
    │ Fields:                                │
    │  • job_lead_id (FK)                    │
    │  • candidate_id (FK)                   │
    │  • status: draft / ready / submitted   │
    │  • kit_data (JSON)                     │
    │  • human_edits (JSON)                  │
    │  • screenshot (optional)               │
    │  • submitted_at (timestamp)            │
    │  • ai_metadata (model, tokens, etc)    │
    │  • error_message (if failed)           │
    └────────────────┬────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────┐
    │ Human Review (UI)                      │
    ├────────────────────────────────────────┤
    │ User can:                              │
    │  • View generated content              │
    │  • Edit all components                 │
    │  • Add/remove sections                 │
    │  • Regenerate specific parts           │
    │  • Save as draft                       │
    │  • Mark as ready                       │
    └────────────────┬────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────┐
    │ Submission                             │
    ├────────────────────────────────────────┤
    │ • Copy to clipboard OR                 │
    │ • Auto-submit (if job platform link)   │
    │ • Save as PDF/DOCX                     │
    │ • Archive in database                  │
    │ • Mark submitted with timestamp        │
    └────────────────────────────────────────┘


STAGE 6: TRACKING & ANALYTICS
════════════════════════════════════════════════════════════════════════════════

    ┌──────────────────────────────────────────┐
    │ Application Lifecycle Tracking            │
    ├──────────────────────────────────────────┤
    │ • Generated applications                  │
    │ • Draft applications                      │
    │ • Submitted applications                  │
    │ • Response received                       │
    │ • Interview scheduled                     │
    │ • Rejected / Accepted / Pending           │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────┐
    │ Analytics Dashboard                      │
    ├──────────────────────────────────────────┤
    │ • Application success rate                │
    │ • Average match score for applications    │
    │ • Time from job match to submission       │
    │ • Provider usage statistics               │
    │ • Cost tracking (tokens, API calls)       │
    │ • Most successful job sources             │
    │ • Best-matching job categories            │
    └──────────────────────────────────────────┘


STAGE 7: MULTI-CHANNEL DISTRIBUTION
════════════════════════════════════════════════════════════════════════════════

    Application ready for distribution
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
    ┌─────────┐  ┌──────────┐  ┌──────────┐
    │Web UI   │  │Telegram  │  │Discord   │
    │(Django) │  │Bot       │  │Webhook   │
    └────┬────┘  └────┬─────┘  └────┬─────┘
         │            │             │
         └────────────┼─────────────┘
                      │
                      ▼
    ┌──────────────────────────────────┐
    │ User Notifications               │
    ├──────────────────────────────────┤
    │ • Job match alerts               │
    │ • Application ready notification │
    │ • Interview reminders            │
    │ • Status updates                 │
    └──────────────────────────────────┘


ERROR HANDLING & RESILIENCE
════════════════════════════════════════════════════════════════════════════════

At any stage, if AI provider fails:

    Error occurs (Rate limit, quota, timeout, etc)
                     │
                     ▼
    ┌──────────────────────────────┐
    │ LLMRouter Error Handler      │
    ├──────────────────────────────┤
    │ • Classify error type        │
    │ • Implement backoff strategy │
    │ • Mark provider cooldown     │
    └────────────────┬─────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Retry enabled?         Other providers
         │                  enabled?
         ▼                       │
    Wait & Retry           Try next provider
    (exponential                │
     backoff)              (fallback logic)
                                 │
                          ┌──────┴───────┐
                          │              │
                      Success?      All failed?
                          │              │
                          ▼              ▼
                    Continue       User sees:
                    processing     • "Try again later"
                                   • "Enable another key"
                                   • "Turn on Ollama"
                                   • "Continue without AI"

```

---

## Data Transformations

### 1. Resume → Candidate Profile

```
Raw Resume Text
  └─ Parsing & Extraction (evidence_scanner.py)
      └─ Structured Data (JSON)
          └─ LLM Enhancement (ai_service.py)
              └─ Validated Schema (Pydantic)
                  └─ Confirmed Profile (Database)
```

### 2. Job Listing → Matched Job

```
Job Data (manual/scraped)
  └─ Normalization (job_sources.py)
      └─ Dedupe Check (fingerprint)
          └─ Preference Filtering
              └─ LLM Scoring (ai_service.py)
                  └─ Ranked Queue
                      └─ User Selection
```

### 3. Profile + Job → Application Kit

```
Candidate Profile + Job Description
  └─ Component Generation (auto_applier.py)
      ├─ Resume Tailoring (resume_tailor.py)
      ├─ Cover Letter Generation
      ├─ Recruiter Message Generation
      ├─ Follow-up Message Generation
      └─ Interview Prep Generation
          └─ Evidence Mapping (evidence_scanner.py)
              └─ Validated Application Kit
                  └─ Database Storage
                      └─ User Review & Submission
```

---

## Performance Metrics

### Processing Times (per stage, estimated)

| Stage | Operation | Time | Notes |
|-------|-----------|------|-------|
| Intake | Resume upload & parsing | 2-5s | Depends on file size |
| Extraction | LLM extraction | 10-20s | Depends on provider |
| Validation | Schema validation | 0.5-1s | Pydantic validation |
| Matching | Job scoring | 5-15s per job | Bulk scoring available |
| Kit Generation | Full application | 30-60s | Multiple LLM calls |
| Human Review | User interaction | Variable | No time limit |
| Submission | Database save | 0.1-0.5s | Quick local save |

### Data Volumes

- **Candidate Profile**: ~50-100 KB (JSON)
- **Single Job Lead**: ~5-10 KB
- **Application Kit**: ~20-50 KB (all components)
- **Database**: Grows with applications (~1-10 MB per year of use)

### Provider Costs (estimated per application)

- **Gemini**: $0.01-0.05 (free tier available)
- **OpenAI**: $0.05-0.15
- **Claude**: $0.10-0.20
- **Groq**: Free or minimal
- **Ollama**: Free (self-hosted)

---

## Caching Strategy

```
LLM Response Cache
  • Duration: 24 hours
  • Key: Hash of (profile, job, task)
  • Storage: In-memory or Redis

Job Match Cache
  • Duration: 12 hours
  • Key: Hash of (candidate_id, job_id)
  • Update: Manual refresh or schedule

Provider Health Cache
  • Duration: 5 minutes
  • Track: Rate limits, cooldowns, errors
  • Fallback: Use cached status
```

---

## Data Quality Assurance

### Validation Points

1. **Resume Upload**: File type, encoding, size
2. **Text Extraction**: Character count, language detection
3. **LLM Extraction**: Schema compliance, required fields
4. **Job Import**: Required fields, format validation
5. **Scoring**: Score range (0-100), confidence bounds
6. **Kit Generation**: All components present, not empty
7. **Storage**: Database constraints, foreign key integrity

### Quality Metrics

- **Extraction Accuracy**: Manual review sampling (target: >95%)
- **Matching Precision**: User feedback (target: >80% satisfaction)
- **Generation Quality**: User edit frequency (target: <30% edits)
- **Data Completeness**: Missing field tracking (target: <5%)

---

## Privacy & Data Handling

### Data Lifecycle

1. **Upload**: Staged in `tmp_uploads/`
2. **Processing**: In-memory processing, cached briefly
3. **Storage**: SQLite database, local storage
4. **Archival**: Indefinite storage (user-controlled)
5. **Deletion**: User-initiated cleanup

### Sensitive Data

- **Resume files**: Deleted after text extraction
- **API responses**: Cached responses don't include credentials
- **User credentials**: Never stored in plain text
- **PII**: Encrypted at rest (optional)
