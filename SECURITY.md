# Security Policy

Job_bro_AI is local-first software that can process sensitive candidate data: resumes, employment history, contact details, job preferences, private application drafts, channel IDs, and LLM API keys. Treat every local deployment as a private data system.

## Public Repository Rules

- Never commit `.env`, local databases, uploaded documents, generated drafts, screenshots containing private data, or profile exports.
- Keep provider credentials in environment variables only.
- Use `.env.example` for placeholders and documentation, never for real values.
- Rotate any key that was ever pasted into a local file, terminal transcript, screenshot, issue, or commit.
- Keep local virtual environments ignored.

## Runtime Defaults

- `AUTO_SUBMIT_ENABLED=false` must remain the public default.
- LLM providers are opt-in through user-owned keys.
- Telegram and Discord integrations must use allowlists.
- Debug mode is acceptable only for local development.

## Before Hosting Publicly

- Set `DJANGO_DEBUG=false`.
- Set a long random `DJANGO_SECRET_KEY`.
- Restrict `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- Use HTTPS and secure cookies.
- Run `python manage.py check --deploy`.
- Add authentication, authorization, and per-user data isolation before allowing multiple users.
- Decide whether external LLM providers are acceptable for the data being processed.

## Reporting Security Issues

Use the repository's private security advisory flow if available, or contact the maintainer through a private channel. Do not open a public issue containing secrets, personal data, logs with credentials, resumes, or generated private application material.
