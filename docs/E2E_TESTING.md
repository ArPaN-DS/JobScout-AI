# E2E Testing

The project has two levels of end-to-end coverage: CI-safe workflow tests with mocked AI and optional local smoke tests using real providers.

## CI Workflow Tests

`core.tests_phase3.WorkflowE2ETests` runs on Django `LiveServerTestCase` with `CareerAgentAI` mocked. It does not require API keys.

```powershell
python manage.py test core.tests_phase3
```

Use this whenever changing views, workflow state, pipeline jobs, templates, or readiness logic.

## Manual Smoke Test

The manual smoke test uses a running local server and real credentials from `.env`.

Terminal 1:

```powershell
python manage.py runserver
```

Terminal 2:

```powershell
$env:E2E_RESUME_PATH="C:\path\to\resume.pdf"
$env:E2E_BASE_URL="http://127.0.0.1:8000"
python test_e2e.py
```

Run this before a public release, after prompt changes, after provider routing changes, or after workflow changes that affect resume upload, scoring, or kit generation.

## Safety Notes

- Use a synthetic or sanitized resume for smoke tests.
- Do not commit smoke-test resumes, screenshots, databases, or `.env` files.
- Prefer mocked tests for CI and real-provider smoke tests for release validation.
