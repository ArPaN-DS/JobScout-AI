# Top-Notch System Roadmap

A phased plan to evolve **Job_bro_AI** from a strong local MVP into a reliable, measurable, production-grade career agent"without sacrificing the review-first, privacy-first principles that make it trustworthy.

**North star:** *The best personal career agent you can self-host"high-quality kits, fresh relevant jobs, zero hallucinated claims, and clear proof that the workflow improves outcomes.*

**Non-goals (stay disciplined):**
- Fully unattended mass auto-submit to every ATS (legal, ethical, and reliability risk).
- Competing with LinkedIn as a job board.
- Multi-tenant SaaS before auth, isolation, and ops are solved.

---

## Guiding principles

| Principle | What top notch means |
|-----------|-------------------------|
| **Truthful AI** | Every skill in a kit traces to evidence; critic/validator blocks bad output. |
| **Human in the loop** | Default path: discover ' score ' generate ' **review** ' submit. |
| **Fail gracefully** | Scraping and LLMs fail often; users always get a clear next action. |
| **Measurable** | Track funnel metrics locally so you can improve match thresholds and prompts. |
| **Local-first** | Data stays on disk unless the user opts into sync/hosting. |
| **Boring ops** | One settings profile, structured logs, CI that mirrors production checks. |

---

## Current baseline (starting point)

| Area | Today |
|------|--------|
| Core workflow | Profile ' match ' kit ' mark submitted |
| LLM layer | Multi-provider router, fallback, cooldowns |
| Discovery | JobSpy + manual import + management commands |
| Tests | 16 unit tests (mostly mocked); manual `test_e2e.py` |
| Security | Review-first, `AUTO_SUBMIT_ENABLED=false`, deploy checklist |
| Gaps | No web auth, thin E2E/CI, scraping variance, monolithic views |

---

## Target maturity model

Use this ladder to decide when a phase is done.

| Level | Discovery | AI quality | Reliability | Product |
|-------|-----------|------------|-------------|---------|
| **L1 MVP** (now) | Manual + brittle scrape | Good prompts, basic grounding | Unit tests, print logs | Single user, localhost |
| **L2 Solid** | Scheduled ingest + dedupe | Validator + prompt versioning | E2E in CI, structured errors | Daily queue digest |
| **L3 Pro** | Source health dashboard | A/B prompts, cost caps | Metrics, alerts, job retries | Auth optional for LAN |
| **L4 Top notch** | Stable 24h fresh pipeline | Outcome-linked tuning | 99% actionable errors | Export + audit trail |

**Goal of this roadmap:** reach **L4** for a single power user; **L3** minimum for any public hosting.

---

## Phase 0 " Foundation cleanup (1"2 weeks)

*Unblock everything else. Low glamour, high leverage.*

### Deliverables

- [ ] **Repo hygiene:** Ensure `job_finder_env/`, `job_finder/`, `db.sqlite3`, `.env`, `media/` never appear in git; document one canonical venv path in README.
- [x] **Settings unification (partial):** CI runs `migrate` + `test` on `career_agent.settings`; deploy check still uses `deploy_settings`.
- [ ] **Pin dependencies:** `requirements.txt` ' locked versions (`requirements.lock` or `pip-tools`); document Python 3.11.
- [ ] **Split `core/views.py`:** Modules e.g. `views/profile.py`, `views/jobs.py`, `views/integrations.py`"same URLs, clearer ownership.
- [x] **Structured logging (partial):** `core/resilience.py` uses `logging`; `job_sources`/`auto_applier` still print.

### Success criteria

- Fresh clone ' `pip install` ' `migrate` ' `test` green in &lt; 15 minutes.
- No PII or secrets in `git status` on a dev machine.

---

## Phase 1 " Quality & trust (2"4 weeks)

*What makes outputs top notch for hiring"not just AI generated.*

### 1.1 Grounding & validation (harden)

- [x] **Two-pass kit generation:** Generate ' deterministic grounding ' `CRITIC_VALIDATE` (opt-out via `KIT_CRITIC_ENABLED`).
- [ ] **Claim-level citations:** Store `evidence_refs[]` per bullet in tailored experience (link to `ProfileClaim` or document snippet).
- [ ] **User diff UI:** Side-by-side: original profile bullet vs tailored bullet; accept/reject per bullet before kit is ready.
- [x] **Prompt registry:** `core/prompts/registry.py` (`PROMPT_VERSION=1.0.0`); logged in `Application.ai_metadata`.

### 1.2 Match engine precision

- [x] **Configurable thresholds:** `CandidatePreference.min_match_score` / `min_match_confidence` + env defaults.
- [ ] **Explainable match card:** Show *why* score (matching skills, gaps, risk flags) in queue UI"already in model, polish presentation.
- [x] **False positive capture (partial):** Not relevant dismisses leads (`dismiss_lead`); export for tuning still TODO.

### 1.3 Profile completeness score

- [x] **Readiness gate:** `assert_ready_for_kit_generation` blocks `/jobs/generate/` when incomplete.
- [x] **Onboarding checklist widget:** `templates/core/includes/readiness_checklist.html` on queue/preferences/profile.

### Success criteria

- Zero kits shipped with skills not in profile (enforced in tests).
- User can see prompt version + validator result for every application.

---

## Phase 2 " Discovery pipeline that survives reality (3"6 weeks)

*Finish v2 vision with realism: APIs first, scrape second.*

### 2.1 Ingest architecture

```text
Scheduler (django-q2 cron)
    ' JobSourceRun (per source)
        ' Adapters: jobspy | manual_import | rss/email (future)
        ' normalize ' JobLead (dedupe fingerprint)
        ' score_job_leads command
        ' Queue (status: new | low_match | matched)
```

- [x] **Adapter interface:** `core/sources/base.py` with `fetch()`, `health()`, `run()`.
- [x] **Per-source circuit breaker:** Health table on Auto Queue shows paused + cooldown.
- [x] **24-hour freshness:** `job_freshness_hours` preference; `archive_stale_leads` on score.
- [x] **JobSourceRun dashboard:** Recent runs + per-source stats on Auto Queue.

### 2.2 Scraping strategy (tiered)

| Tier | Method | When |
|------|--------|------|
| A | **JobSpy / public APIs** | Default; lowest maintenance |
| B | **User-pasted URL + fetch** | On-demand enrichment |
| C | **Playwright + LLM extract** | Only for allowed domains; cap daily calls |
| D | **Auto-submit** | Off by default; explicit opt-in per portal |

- [x] **Tiered sources:** JobSpy/APIs first; scrapers in Tier B (`docs/SUPPORTED_SOURCES.md`).
- [x] **Respect robots/ToS:** Documented in `docs/SUPPORTED_SOURCES.md`.

### 2.3 Queue UX (v2 daily digest)

- [x] **Auto-Queue tab:** Filters (matched/new/low/all), sort by score + date.
- [x] **Bulk actions:** Score all new, generate top kits, cost preview.
- [x] **AJAX/polling:** `queue.js` polls `/jobs/discovery-status/` every 30s; bulk forms via fetch.

### Success criteria

- Scheduled run completes daily without manual intervention 5 days in a row (on your machine).
- &lt; 10% duplicate leads in queue; low-match auto-archived.

---

## Phase 3 " Reliability & observability (2"3 weeks)

*Top notch = predictable when things break.*

### 3.1 Testing pyramid

| Layer | Target |
|-------|--------|
| Unit | 40+ tests: schemas, router, import dedupe, validators |
| Integration | Management commands with fixtures; mock HTTP for jobspy |
| E2E | CI job: Django live server + mocked `CareerAgentAI` (no real API keys) |
| Manual | `test_e2e.py` with real keys"documented weekly smoke |

- [x] **Coverage gate:** CI runs `coverage` 55% on core LLM/schemas/ai_service/errors/metrics (77%+ locally).
- [x] **Regression fixtures:** `core/fixtures/golden_match.json` + snapshot test.

### 3.2 Background jobs

- [x] **django-q2 tasks:** `tracked_*` wrappers with `PipelineJob` idempotency keys.
- [x] **User-visible job status:** Progress on Auto Queue + `/jobs/discovery-status/` + cancel.
- [x] **Cost accounting:** `LLMUsageEvent` + `DAILY_LLM_BUDGET_USD` + Metrics page.

### 3.3 Error UX

- [x] **No raw tracebacks in UI** for production via `core/errors.py` + `error_detail` JSON.
- [x] **Retry buttons:** Failed/matched apps " Retry kit + Compact retry (`LLM_COMPACT_MAX_CHARS`).

### Success criteria

- [x] CI green on Windows + Linux (matrix).
- Any failed scrape/LLM call leaves DB row + log line + user message (no silent skip).

---

## Phase 4 " Security & deploy readiness (2"4 weeks)

*Required before public or family sharing on a server.*

- [ ] **Authentication:** Django login + session; all workflow views protected.
- [ ] **Optional multi-profile:** One user, multiple `CandidateProfile` records (job search personas).
- [ ] **Encrypt secrets at rest:** API keys in DB encrypted with `FERNET_KEY` from env (not plain `.env` only).
- [ ] **Complete `PUBLIC_LAUNCH_CHECKLIST.md`** items; automate via `manage.py check --deploy` in CI.
- [ ] **Backup script:** `db.sqlite3` + `media/` + export profile JSON.
- [ ] **Rate limits:** Per-IP on webhooks and kit generation endpoints.

### Success criteria

- OWASP-minded pass: no open admin, CSRF on, secure cookies, allowlists on bots.
- Second user cannot read first users data (if multi-user added later).

---

## Phase 5 " Outcomes & top notch product loop (ongoing)

*Measure whether the system actually helps.*

### 5.1 Metrics (local analytics)

Track in DB or SQLite views:

| Metric | Why |
|--------|-----|
| Leads ingested / day | Discovery health |
| Match rate  threshold | Filter tuning |
| Kits generated / submitted | Funnel conversion |
| Time profile ' first submit | Onboarding friction |
| User-marked interview / offer | Outcome proxy |
| LLM cost / kit | Budget control |

- [ ] **Dashboard card:** Last 30 days funnel.
- [ ] **Export CSV** for personal analysis.

### 5.2 Continuous improvement

- [ ] Monthly prompt review using false-positive / not relevant exports.
- [ ] Provider benchmark script: same job, compare latency + score variance across providers.
- [ ] User feedback field on each application: quality 1"5.

### Success criteria

- You can answer: Did match score  X correlate with interviews? from your own data within 90 days.

---

## Phase 6 " Optional excellence (pick selectively)

| Feature | Value | Cost |
|---------|-------|------|
| PDF/DOCX export of tailored resume | High | Medium |
| Email digest (daily queue) | Medium | Low |
| Calendar reminders for follow-ups | Medium | Low |
| Resume keyword ATS checker (non-LLM) | Medium | Low |
| Mobile-friendly PWA | Medium | Medium |
| PostgreSQL + Redis for heavy users | Low early | Medium |

---

## Priority matrix (what to do first)

```
Impact '
    "  P1 Grounding+validator     P2 Queue+digest
    "  P0 Repo/settings/tests    P3 Observability
    "  P4 Auth (if hosting)       P6 PDF export
    """"""""""""""""""""""""""""""""""""' Effort
```

**Recommended order:** Phase 0 ' 1 ' 3 (tests) in parallel with 2 ' 4 (if hosting) ' 5.

---

## 90-day milestone sketch

| Month | Focus | Exit state |
|-------|-------|------------|
| **M1** | Phase 0 + Phase 1 validator + tests to 30+ | Trustworthy kits |
| **M2** | Phase 2 queue + scheduled discovery | Daily digest works |
| **M3** | Phase 3 CI E2E + metrics dashboard | Measurable funnel |
| **M3+** | Phase 4 if exposing to network | Safe hosting |

---

## Definition of top notch (checklist)

When all are true, the system is top notch **for its category** (local self-hosted agent):

- [ ] Profile cannot generate kits until evidence-reviewed and `ready`.
- [ ] Every kit skill is traceable to a claim or document.
- [ ] Discovery runs on a schedule with visible source health.
- [ ] Queue supports bulk prep with cost preview.
- [ ] CI runs deploy checks + E2E without real API keys.
- [ ] User sees actionable errors, never silent failures.
- [ ] Funnel metrics exist: ingest ' match ' kit ' submit ' outcome.
- [ ] Public hosting only with auth + checklist complete.
- [ ] Auto-submit remains off unless explicitly enabled with warnings.

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Scrapers break weekly | Adapters + circuit breaker + user paste fallback |
| LLM hallucination | Validator + critic pass + per-bullet review UI |
| API cost spike | Daily budget cap + bulk cost preview |
| Legal/ToS on scraping | Document supported sources; prefer JobSpy/APIs |
| Scope creep | Stick to phases; defer SaaS/multi-tenant |

---

## Related docs

- `v2_planning_and_cost.md.resolved` " original Phase 2 feature list
- `PUBLIC_LAUNCH_CHECKLIST.md` " hosting safety
- `SECURITY.md` " threat model assumptions
- `docs/ARCHITECTURE.md` " layer diagram to update as modules split

---

*Last updated: 2026-05-31. Revise quarterly based on funnel metrics and failure logs.*
