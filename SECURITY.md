# Security Policy for JobScout-AI

We take the security of your private career data, API credentials, and application materials very seriously. Since **JobScout-AI** operates locally on your machine, securing your environment is a shared responsibility.

---

## Public Repository Security Rules

To protect your personal data, never share or commit:
- Your local `.env` file (contains LLM API keys and secrets).
- Your local SQLite database `db.sqlite3` (contains candidate resumes, logs, and profile info).
- Exported JSON profile data.
- Uploaded resumes or generated application drafts (`tmp_uploads/` or `media/browser_sessions/`).

*If you accidentally commit any secrets or API keys, rotate them immediately!*

---

## Supported Versions

Security updates are actively applied to the following versions:

| Version | Supported |
| :--- | :--- |
| **v1.x (Active)** | Yes (Latest updates and patches) |
| **v0.x (Deprecated)** | No (Please upgrade to v1.x) |

---

## How to Report a Security Vulnerability

If you discover a security bug or potential vulnerability in **JobScout-AI**, please **do not open a public GitHub issue**. Doing so exposes users to risk before a patch can be developed.

Instead, please report vulnerabilities privately:

### 1. GitHub Private Security Advisory (Preferred)
Navigate to the **Security** tab of our GitHub repository, select **Advisories**, and click **Report a vulnerability**. This allows us to discuss and patch the issue in a secure environment.

### 2. Direct Private Contact
Alternatively, if the private advisory flow is unavailable, contact the primary maintainer directly at the security channel listed in the repository settings or email `arpan@example.com` (using GPG encryption if possible).

---

## Secure Deployment Checklist

Before exposing a JobScout-AI server over a local area network (LAN) or hosting it on a VPS:
1. Set `DJANGO_DEBUG=false` in your `.env`.
2. Generate a secure, 50+ character `DJANGO_SECRET_KEY` using `python generate_keys.py`.
3. Set `FIELD_ENCRYPTION_KEY` to encrypt API keys stored in the database.
4. Restrict `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to trusted domains only.
5. Enable HTTPS and secure cookies.
6. Verify your setup by running the deployment security checks:
   ```bash
   python manage.py check --deploy
   ```
