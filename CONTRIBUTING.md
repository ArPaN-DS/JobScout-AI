# Contributing

Thanks for helping make Job_bro_AI better for job hunters.

## Development Setup

```bash
python -m venv job_finder
.\job_finder\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py test
```

## Contribution Rules

- Keep the project local-first and privacy-first.
- Do not commit API keys, resumes, SQLite databases, or generated application
  drafts.
- Keep provider integrations isolated behind adapters.
- Prefer official APIs, RSS feeds, email alerts, and user-provided URLs before
  scraping job boards.
- Keep application submission review-first by default.

## Tests

Run:

```bash
python manage.py check
python manage.py test
```

Production-oriented checks can be run with:

```bash
$env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"
python manage.py check --deploy
```
