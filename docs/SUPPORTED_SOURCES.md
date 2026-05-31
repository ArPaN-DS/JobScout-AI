# Supported Job Discovery Sources

Job_bro_AI uses a tiered discovery strategy. Prefer stable APIs and aggregators first, then use scraping-based sources selectively. Manual import is always available and is the safest fallback when a source is unstable.

## Tier A: APIs and Aggregators

| ID | Label | Notes |
|---|---|---|
| `jobspy` | JobSpy | Aggregates LinkedIn, Indeed, Glassdoor, and Google Jobs where supported. Respects freshness settings. |
| `remoteok` | RemoteOK | Public JSON API for remote roles. |
| `ycombinator` | Y Combinator Jobs | Public job feed. |
| `greenhouse` | Greenhouse boards | Company board integration for known Greenhouse hosts. |
| `lever` | Lever boards | Company board integration for known Lever hosts. |

## Tier B: Scraping-Based Sources

| ID | Label | Notes |
|---|---|---|
| `naukri` | Naukri | India-focused roles. |
| `internshala` | Internshala | Internship and early-career roles. |
| `foundit` | Foundit | India-focused roles. |
| `hirist` | Hirist | Technology roles in India. |
| `wellfound` | Wellfound | Startup roles for a limited query set. |
| `career_pages` | Career pages | Direct company page discovery. |

## Configuration

- Candidate preferences can define `discovery_sources` as comma-separated source IDs.
- `DISCOVERY_SOURCES=jobspy,remoteok` can limit sources globally.
- `job_freshness_hours` controls the maximum age for newly discovered leads.
- Source runs are recorded as `JobSourceRun` records for visibility.

## Operating Guidance

- Respect site terms, rate limits, and blocks.
- Disable scraping-based sources if they become noisy, blocked, or legally questionable for your use case.
- Prefer manual import for high-value jobs where automation would add risk.
- Keep `AUTO_SUBMIT_ENABLED=false` unless the operator has explicitly accepted the consequences.
