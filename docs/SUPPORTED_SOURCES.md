# Supported Job Discovery Sources

Job_bro_AI uses a **tiered** discovery strategy. Prefer Tier A; use manual import for anything else.

## Tier A — APIs / aggregators (default)

| ID | Label | Notes |
|----|-------|-------|
| `jobspy` | JobSpy | LinkedIn, Indeed, Glassdoor, Google Jobs. Respects `hours_old` freshness. |
| `remoteok` | RemoteOK | Public JSON API. |
| `ycombinator` | Y Combinator | Public job feed. |
| `greenhouse` | Greenhouse | Known company boards. |
| `lever` | Lever | Known company boards. |

## Tier B — Scraping (higher breakage)

| ID | Label | Notes |
|----|-------|-------|
| `naukri` | Naukri | India-focused. |
| `internshala` | Internshala | Internships. |
| `foundit` | Foundit | India jobs. |
| `hirist` | Hirist | Tech roles India. |
| `wellfound` | Wellfound | Startup roles (subset of queries). |
| `career_pages` | Career pages | Direct company pages. |

## Manual import

Paste any job description on **Auto Queue** — no scraping required.

## Configuration

- **Preferences → Job Freshness:** max age for unscored leads (default 24h).
- **Preferences → Discovery Sources:** comma-separated source IDs.
- **Environment:** `DISCOVERY_SOURCES=jobspy,remoteok` to limit globally.

## Legal / ethical

- Use only for your own job search on a self-hosted instance.
- Respect site terms; reduce sources if you see blocks (circuit breaker will pause sources automatically).
- Do not enable `AUTO_SUBMIT_ENABLED` without reviewing each application.
