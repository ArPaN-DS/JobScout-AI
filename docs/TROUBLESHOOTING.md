# Troubleshooting Guide

Common issues and solutions for Job_bro_AI.

---

## Database Issues

### SQLite Database Locked

**Problem**: "Database is locked" error

```
django.db.utils.OperationalError: database is locked
```

**Solution**:
```bash
# Kill existing connections
lsof | grep db.sqlite3
kill -9 <PID>

# Or delete WAL files
rm db.sqlite3-wal
rm db.sqlite3-shm

# Restart application
python manage.py runserver
```

### PostgreSQL Connection Refused

**Problem**: "Connection refused on port 5432"

**Solution**:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Test connection
psql -U jobbroai -d jobbroai -h localhost
```

### Migration Failed

**Problem**: "No such table: core_candidateprofile"

**Solution**:
```bash
# Run migrations
python manage.py migrate

# If still fails, reset migrations (dev only!)
python manage.py migrate core zero
python manage.py migrate core
```

---

## Resume Upload Issues

### File Upload Timeout

**Problem**: Upload takes too long or times out

**Solution**:
- Reduce file size: Compress PDF before upload
- Check internet: Verify connection speed
- Increase timeout in settings:
```python
# settings.py
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
```

### Unsupported File Format

**Problem**: "File format not supported"

**Solution**:
- Ensure file is PDF or DOCX
- Convert file:
  - PDF: Use any PDF tool
  - Word: Save as .docx (not .doc)
  - Other: Convert to PDF first

### Extracted Data is Incorrect

**Problem**: "AI extracted wrong information"

**Solution**:
```
1. Manually edit profile fields
2. Confirm/verify each section
3. System learns from corrections
4. Extract again if needed
```

---

## Job Import Issues

### No Jobs Found

**Problem**: "Zero jobs imported in search"

**Solution**:
```bash
# Check job sources
python manage.py shell
from core.job_sources import JobSourceRouter
router = JobSourceRouter()
jobs = router.search("Python Developer", location="Remote")
print(f"Found {len(jobs)} jobs")

# Verify API keys
import os
print(os.getenv('JOBSPY_API_KEY'))
```

### Duplicate Jobs Appearing

**Problem**: "Same job appears multiple times"

**Solution**:
```bash
# Deduplicate manually
python manage.py shell
from core.models import JobLead
from django.db.models import Count

duplicates = JobLead.objects.values('fingerprint').annotate(count=Count('id')).filter(count__gt=1)

for dup in duplicates:
    jobs = JobLead.objects.filter(fingerprint=dup['fingerprint'])
    keep = jobs.first()
    jobs.exclude(id=keep.id).delete()
```

### Job Source Error

**Problem**: "JobSpy API error" or "Source connection failed"

**Solution**:
```
1. Check API keys in settings
2. Verify internet connection
3. Check if source is down
4. Try different job source
5. Wait and retry
```

---

## LLM Provider Issues

### Invalid API Key

**Problem**: "API key invalid or expired"

**Solution**:
```python
# Test provider
from core.llm import LLMRouter

router = LLMRouter()
result = router.route({"prompt": "Hello"})
# Check which provider succeeded
```

**Fix**:
1. Go to Settings ' Providers
2. Verify API key is correct
3. Check expiration date
4. Generate new key if needed
5. Test provider

### Rate Limited

**Problem**: "Too many requests" or "Rate limit exceeded"

**Solution**:
```
1. Wait 60 seconds (rate limit window)
2. Use different provider
3. Reduce concurrent requests
4. Upgrade API plan
```

### Provider Timeout

**Problem**: "Request timeout after 30s"

**Solution**:
```python
# Increase timeout
# .env
LLM_TIMEOUT=60  # Default 30

# Or use faster provider
# Settings ' Providers ' Priority
# Move faster provider up
```

### All Providers Failed

**Problem**: "LLMExhaustedError: All providers failed"

**Solution**:
```bash
# Check all providers
Settings ' Providers ' Test each one

# Check credentials
echo $OPENAI_API_KEY
echo $GEMINI_API_KEY
echo $ANTHROPIC_API_KEY

# Verify internet
ping google.com

# Check if providers are down
# Visit: openai.com, gemini.google.com, etc.
```

---

## Profile Matching Issues

### Low Match Scores

**Problem**: "All jobs show 0-40% match"

**Solution**:
1. Review profile completeness
2. Add more skills (match algorithm looks at skills)
3. Add work experience
4. Match against specific job titles
5. Try re-matching

**Debug**:
```python
from core.ai_service import CareerAgentAI

ai = CareerAgentAI()
profile = {...}  # Your profile
job = {...}      # A job

result = ai.evaluate_job_match(profile, job)
print(result.reasoning)  # See why score is low
```

### Match Score Seems Wrong

**Problem**: "Job scored 95% but I'm not qualified"

**Solution**:
- Review score breakdown
- AI may weight certain skills heavily
- Manually verify before applying
- Give feedback to system

---

## Application Generation Issues

### Generation Takes Too Long

**Problem**: "Generating application... (2+ minutes)"

**Solution**:
```
1. First generation is slower (model loading)
2. Check: Is LLM provider slow?
3. Switch to faster provider:
   - Groq (fastest)
   - Gemini Flash (fast)
   - OpenAI (medium)
   - Claude (slower but better quality)
```

### Generated Content is Bad Quality

**Problem**: "Cover letter is generic/poor quality"

**Solution**:
```
1. Edit after generation (templates available)
2. Add personal details
3. Research company beforehand
4. Try different LLM provider
5. Try different prompt template
```

### Generation Fails with Error

**Problem**: "Error generating application"

**Solution**:
```bash
# Check logs
tail -f logs/error.log

# Check LLM provider
Settings ' Providers ' Test

# Check if job description is too long
# Some providers have token limits

# Try with different provider
```

---

## Telegram Bot Issues

### Bot Not Responding

**Problem**: "Telegram bot doesn't respond to commands"

**Solution**:
```bash
# Check bot configuration
Settings ' Telegram ' Verify token

# Restart bot
python manage.py shell
from core.channels import TelegramBot
bot = TelegramBot()
bot.start()

# Test connection
curl https://api.telegram.org/bot<TOKEN>/getMe
```

### Verification Code Incorrect

**Problem**: "Invalid code" when connecting Telegram

**Solution**:
```
1. Generate new verification code
2. Copy ENTIRE code (don't miss characters)
3. In Telegram: /start
4. Send code exactly as shown
```

### No Notifications Received

**Problem**: "Telegram not sending job updates"

**Solution**:
```
1. Check notifications are enabled
   Settings ' Telegram ' Notifications: ON
   
2. Check notification threshold
   Settings ' Telegram ' Min Score: 75
   
3. Verify jobs imported
   Jobs ' Count should > 0
   
4. Test notification
   Telegram: /test
```

---

## Performance Issues

### Application Slow

**Problem**: "Website loads slowly" or "Hangs"

**Solution**:
```bash
# Check running processes
top

# Check database queries
python manage.py shell
from django.test.utils import override_settings
from django.db import connection
from django.db import reset_queries

reset_queries()
# Run your operation
len(connection.queries)  # Number of DB queries

# Too many queries? Use select_related/prefetch_related
```

### High CPU Usage

**Problem**: "CPU usage 100%"

**Solution**:
```bash
# Check background workers
systemctl status jobbroai-worker

# Check process consuming CPU
top -o %CPU | head

# Reduce worker count
# .env
DJANGO_Q_WORKERS=2  # Instead of 4
```

### High Memory Usage

**Problem**: "Memory usage growing"

**Solution**:
```bash
# Check memory
free -h

# Monitor memory over time
watch -n 1 free -h

# Limit worker memory
# systemd service:
MemoryLimit=2G

# Restart worker
systemctl restart jobbroai-worker
```

---

## Static Files Issues

### CSS/Images Not Loading

**Problem**: "Styles look broken" or "Images missing"

**Solution**:
```bash
# Collect static files
python manage.py collectstatic --noinput

# Clear browser cache
# Ctrl + Shift + Delete

# Check Nginx config
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Authentication Issues

### Can't Log In

**Problem**: "Invalid credentials" or "Account locked"

**Solution**:
```bash
# Reset admin password
python manage.py changepassword admin

# Create new superuser
python manage.py createsuperuser

# Check user in database
python manage.py shell
from django.contrib.auth.models import User
User.objects.all()
```

### Session Expires Too Quickly

**Problem**: "Logged out after few minutes"

**Solution**:
```python
# .env
SESSION_COOKIE_AGE=86400  # 24 hours (default 2 weeks)
SESSION_EXPIRE_AT_BROWSER_CLOSE=False
```

---

## Email Issues

### Emails Not Sending

**Problem**: "Application notifications not received"

**Solution**:
```bash
# Test email configuration
python manage.py shell
from django.core.mail import send_mail

send_mail(
    'Test',
    'Test message',
    'from@example.com',
    ['to@example.com'],
)
```

**Check settings**:
```python
# .env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=smtp-user@example.com
EMAIL_HOST_PASSWORD=your_app_password
```

---

## Deployment Issues

### Application won't start

**Problem**: "ERROR ... failed to start"

**Solution**:
```bash
# Check for syntax errors
python manage.py check

# Check migrations
python manage.py migrate --plan

# Test server locally
python manage.py runserver

# Check Gunicorn logs
journalctl -u jobbroai -n 50
```

### Port Already in Use

**Problem**: "Address already in use"

**Solution**:
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
python manage.py runserver 8001
```

---

## Data Backup/Recovery

### Restore from Backup

```bash
# List backups
ls -lh /backups/jobbroai/

# Restore database
gunzip < /backups/jobbroai/db_20260531_020000.sql.gz | psql -U jobbroai jobbroai

# Verify restoration
python manage.py shell
from core.models import CandidateProfile
CandidateProfile.objects.count()
```

---

## Logging & Debug

### Enable Debug Logging

```python
# .env
DEBUG=True
LOG_LEVEL=DEBUG

# Check logs
tail -f logs/debug.log

# For specific module
import logging
logging.getLogger('core.ai_service').setLevel(logging.DEBUG)
```

### View Django Shell

```bash
python manage.py shell

# Test LLM
from core.llm import LLMRouter
router = LLMRouter()
print(router.get_active_providers())

# Check database
from core.models import JobLead, CandidateProfile
print(f"Jobs: {JobLead.objects.count()}")
print(f"Profiles: {CandidateProfile.objects.count()}")
```

---

## Getting Help

- **Documentation**: [docs/](../README.md#documentation)
- **GitHub Issues**: [Report issue](https://github.com/ArPaN-DS/Job_bro_AI/issues)
- **Security issue**: Use a private maintainer channel or GitHub security advisory when available.

---

**Still stuck? Enable debug logging and check the logs!**
