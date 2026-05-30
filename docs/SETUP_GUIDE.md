# Setup & Installation Guide

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11 or higher** - [Download Python](https://www.python.org/downloads/)
- **pip** - Comes with Python
- **Git** - [Download Git](https://git-scm.com/)
- **At least 500MB of free disk space**
- **Internet connection** (for downloading packages and LLM API access)

---

## Installation Steps

### Step 1: Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/ArPaN-DS/Job_bro_AI.git
cd Job_bro_AI
```

### Step 2: Create Virtual Environment

**On Windows:**
```bash
python -m venv job_finder_env
.\job_finder_env\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv job_finder_env
source job_finder_env/bin/activate
```

### Step 3: Upgrade pip

```bash
python -m pip install --upgrade pip
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Django 5.2+ (web framework)
- Pydantic (data validation)
- pdfplumber & python-docx (document parsing)
- Various LLM provider SDKs
- django-q2 (async task queue)
- playwright (web automation, optional)

### Step 5: Configure Environment Variables

```bash
# Copy the example file
copy .env.example .env        # Windows
# OR
cp .env.example .env          # macOS/Linux
```

### Step 6: Edit `.env` Configuration

Open `.env` in your editor and configure:

#### Minimal Setup (Required)

```env
# Django Settings
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=your-very-long-random-secret-key-here-at-least-50-chars

# At least ONE LLM provider key (choose one or more)
GEMINI_API_KEY=your_gemini_key_here
# OR
# OPENAI_API_KEY=sk-proj-...
# OR
# ANTHROPIC_API_KEY=sk-ant-...
```

#### Get API Keys

**Google Gemini (Recommended - Free Tier)**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Get API Key"
3. Create new API key
4. Copy and paste to `.env`

**OpenAI / GPT**
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create new secret key
3. Copy and paste to `.env`

**Anthropic / Claude**
1. Go to [Anthropic Console](https://console.anthropic.com/account/keys)
2. Create new API key
3. Copy and paste to `.env`

#### Optional: Telegram Bot Setup

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ALLOWED_CHAT_IDS=123456789,987654321
```

How to get Telegram Bot Token:
1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow the prompts
4. Copy the token provided

#### Optional: Discord Bot Setup

```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_ALLOWED_IDS=987654321098765432,123456789012345678
```

#### Optional: Ollama (Local LLM - Privacy)

```env
OLLAMA_ENABLED=false
# After installing Ollama locally, set to true:
# OLLAMA_ENABLED=true
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1
```

### Step 7: Initialize Database

```bash
python manage.py migrate
```

This creates:
- SQLite database (`db.sqlite3`)
- Required database tables
- Initial schema

### Step 8: Create Admin User (Optional)

To access Django admin panel at `/admin`:

```bash
python manage.py createsuperuser
```

Follow the prompts to set username, email, and password.

### Step 9: Start Development Server

```bash
python manage.py runserver
```

Expected output:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### Step 10: Access the Application

Open your browser and go to:
```
http://localhost:8000
```

You should see the Job_bro_AI home page.

---

## Post-Installation Verification

### Check Installation

```bash
# Verify Django setup
python manage.py check

# Run tests
python manage.py test

# Production-style deployment check
$env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"  # Windows
# OR (macOS/Linux)
export DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"
python manage.py check --deploy
```

### Verify API Keys

1. Go to `http://localhost:8000/provider-settings`
2. You should see available LLM providers
3. Green checkmark ✓ = Key is valid
4. Red X = Key not configured or invalid

---

## Troubleshooting Installation

### Issue: "Python not found"

**Solution:**
- Ensure Python 3.11+ is installed
- On Windows, check "Add Python to PATH" during installation
- Restart terminal/IDE after installing Python

### Issue: "Module not found" after pip install

**Solution:**
```bash
# Ensure venv is activated
.\job_finder_env\Scripts\activate   # Windows
source job_finder_env/bin/activate  # macOS/Linux

# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# Use different port
python manage.py runserver 8001

# Or kill process using port 8000
# Windows: netstat -ano | findstr :8000
# macOS/Linux: lsof -i :8000
```

### Issue: "ModuleNotFoundError: No module named 'django'"

**Solution:**
```bash
# Verify requirements are installed
pip list | grep -i django

# If not installed, run
pip install -r requirements.txt

# Verify virtual environment is activated
which python   # Should show path inside job_finder_env
```

### Issue: "Secret key is not set"

**Solution:**
```bash
# Generate a secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Copy the output and paste into .env
DJANGO_SECRET_KEY=<paste_here>
```

---

## Configuration Details

### Django Settings Modes

**Development Mode:**
- `DJANGO_DEBUG=true`
- Detailed error messages
- Static files served automatically
- Hot reload enabled

**Production Mode:**
- `DJANGO_DEBUG=false`
- Use `deploy_settings.py`
- Requires static file collection
- HTTPS required

### LLM Provider Priority

The system tries providers in this order:

1. **Enabled** providers (API key configured)
2. **Available** providers (key is valid, not rate-limited)
3. **Primary** provider (based on cost/speed)
4. **Fallback** providers (in order)

### Database Options

**SQLite (Default - Recommended for Single User):**
- No setup required
- File-based: `db.sqlite3`
- Good for local development
- Limited concurrency

**PostgreSQL (For Deployment):**
- Install PostgreSQL server
- Configure in `.env`:
  ```env
  DATABASE_URL=postgresql://user:password@localhost/jobbroai
  ```
- Better for multiple concurrent users

---

## Running Background Tasks

### Automatic Mode (Recommended)

Django-Q2 runs automatically. To start the cluster:

```bash
# Terminal 1 - Run web server
python manage.py runserver

# Terminal 2 - Run task workers
python manage.py qcluster
```

Both need to run simultaneously for async tasks to work.

### Manual Mode

For testing without async:

```bash
# Run tasks synchronously (slower)
DJANGO_SETTINGS_MODULE=career_agent.settings python manage.py runserver
```

---

## Performance Optimization

### Enable Caching

Edit `.env`:
```env
# In-memory cache (fast)
CACHE_BACKEND=locmem

# Or Redis (better for production)
# CACHE_BACKEND=redis://127.0.0.1:6379/0
```

### Database Optimization

```bash
# Analyze and optimize database
python manage.py dbshell
ANALYZE;
VACUUM;
```

### Static Files

```bash
# Collect static files for production
python manage.py collectstatic --noinput
```

---

## Uninstallation

To completely remove Job_bro_AI:

```bash
# Deactivate virtual environment
deactivate

# Delete project directory
rm -rf Job_bro_AI          # macOS/Linux
rmdir /s Job_bro_AI        # Windows

# Delete virtual environment (if created separately)
rm -rf job_finder_env      # macOS/Linux
rmdir /s job_finder_env    # Windows
```

---

## Next Steps

1. **Upload Resume**: Go to Profile tab and upload a resume
2. **Configure Preferences**: Set job search filters
3. **Import Jobs**: Add job opportunities
4. **Generate Applications**: Let AI create application kits
5. **Review & Submit**: Human-in-the-loop review

See [USER_GUIDE.md](USER_GUIDE.md) for detailed usage instructions.

---

## Getting Help

- 📖 [Documentation](../docs/)
- 🐛 [Report Issues](https://github.com/ArPaN-DS/Job_bro_AI/issues)
- 💬 [Discussions](https://github.com/ArPaN-DS/Job_bro_AI/discussions)
- 📧 Email: arpanmajumdar952@gmail.com

---

## Security Notes

### Secret Key Generation

Generate a strong secret key:

```bash
# Option 1: Django utility
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Option 2: Python secrets
python -c "import secrets; print(secrets.token_urlsafe(50))"

# Option 3: Use online tool
# https://djecrety.ir/
```

### Best Practices

1. **Never commit `.env`** - It contains secrets
2. **Use strong passwords** for admin user
3. **Enable HTTPS** in production
4. **Regularly update** dependencies: `pip install -U -r requirements.txt`
5. **Backup database** regularly
6. **Rotate API keys** periodically
7. **Use environment-specific settings**

---

## Performance Metrics

Typical setup performance (on modern laptop):

| Operation | Time | Notes |
|-----------|------|-------|
| Application start | 2-3s | First time, Django initialization |
| Resume upload & parse | 2-5s | Depends on file size |
| LLM extraction | 10-20s | Depends on provider |
| Job scoring | 5-15s | Per job match |
| Application generation | 30-60s | Full kit generation |
| Database query | <100ms | Simple queries |
| Task queue processing | Async | Doesn't block UI |

---

## System Requirements Summary

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.11 | 3.12+ |
| RAM | 2 GB | 4+ GB |
| Disk | 500 MB | 2+ GB |
| Processor | Dual-core | Quad-core+ |
| OS | Any | Windows 10+ / macOS 10.14+ / Linux |

---

## Common Configuration Scenarios

### Scenario 1: Local Development

```env
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=dev-key-only-for-local
GEMINI_API_KEY=your_key
```

### Scenario 2: Privacy-Focused (Ollama Only)

```env
DJANGO_DEBUG=true
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

### Scenario 3: Multi-Provider Fallback

```env
DJANGO_DEBUG=false
GEMINI_API_KEY=key1
OPENAI_API_KEY=key2
ANTHROPIC_API_KEY=key3
```

---

## Environment Variables Reference

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| DJANGO_DEBUG | Yes | true | false in production |
| DJANGO_SECRET_KEY | Yes | random50char | Use strong key |
| GEMINI_API_KEY | No | ai-xxxxx | Free tier available |
| OPENAI_API_KEY | No | sk-proj-xxx | Pay-as-you-go |
| ANTHROPIC_API_KEY | No | sk-ant-xxx | Pay-as-you-go |
| TELEGRAM_BOT_TOKEN | No | 123456:ABC... | Optional |
| DISCORD_BOT_TOKEN | No | MTk4NjIyNDgzMjU4... | Optional |
| OLLAMA_ENABLED | No | false | Set true if local LLM |
| OLLAMA_BASE_URL | No | http://localhost:11434 | Local LLM endpoint |
| OLLAMA_MODEL | No | llama3.1 | LLM model name |

---

**Installation Complete!** 🎉

You're now ready to use Job_bro_AI. Start with uploading your resume and explore the features.
