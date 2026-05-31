# Public Launch Checklist

Use this checklist before making the repository public or deploying a hosted instance.

## Repository Safety

- [ ] Run a secret scan across tracked and untracked project files.
- [ ] Confirm `.env`, SQLite databases, uploaded resumes, generated drafts, screenshots, profile exports, and local virtual environments are absent from Git.
- [ ] Confirm `.gitignore` excludes local-only files.
- [ ] Remove personal email addresses, phone numbers, private URLs, and real candidate examples.
- [ ] Verify docs use placeholders instead of real credentials or personal data.

## Application Safety

- [ ] Keep `AUTO_SUBMIT_ENABLED=false` as the public default.
- [ ] Confirm every LLM provider is opt-in through a user-owned key.
- [ ] Confirm provider errors do not leak keys or raw private prompts.
- [ ] Confirm Telegram and Discord allowlists are required before use.
- [ ] Confirm application generation remains review-first.

## Deployment Safety

- [ ] Set `DJANGO_DEBUG=false`.
- [ ] Set a long random `DJANGO_SECRET_KEY`.
- [ ] Restrict `DJANGO_ALLOWED_HOSTS`.
- [ ] Set `CSRF_TRUSTED_ORIGINS`.
- [ ] Use HTTPS and secure cookies.
- [ ] Run `python manage.py check --deploy`.
- [ ] Add authentication and per-user data isolation before serving multiple users.

## Verification

```powershell
python manage.py check
python manage.py test core
$env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"
python manage.py check --deploy
```
