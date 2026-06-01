# E2E Testing

## CI (automated)

`core.tests_phase3.WorkflowE2ETests` runs on Django `LiveServerTestCase` with **mocked** `CareerAgentAI` — no API keys required.

```bash
python manage.py test core.tests_phase3
```

## Manual smoke (real providers)

Requires a running server and real credentials in `.env`:

```bash
python manage.py runserver
# separate terminal:
set E2E_RESUME_PATH=C:\path\to\resume.pdf
set E2E_BASE_URL=http://127.0.0.1:8000
python test_e2e.py
```

Run weekly or before releases when changing prompts or providers.
