# Job_bro_AI: Local-First AI Career Agent

[![License](https://img.shields.io/badge/license-MIT-green)]() 
[![Django](https://img.shields.io/badge/Django-5.2-darkgreen)]() 
[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)]()

> **Job_bro_AI** is an intelligent, privacy-first career agent that helps job hunters prepare higher-quality applications through AI-powered resume analysis, job matching, and application kit generation.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Features](#core-features)
- [Provider Support](#provider-support)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Development](#development)
- [Security & Privacy](#security--privacy)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**Job_bro_AI** operates on a review-first workflow:

```
📄 AI discovers and prepares → 👤 Human reviews → ✅ Human submits
```

### Key Principles

- **🔒 Privacy First**: All user data stays local. Each user runs their own instance.
- **🎯 Review-Driven**: AI prepares everything, but humans remain in control.
- **🔄 Provider Agnostic**: Support for 10+ LLM providers with automatic fallback.
- **📱 Multi-Channel**: Telegram, Discord, and Web UI support.
- **🚀 Production Ready**: Designed for real-world deployment and reliability.

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Job_bro_AI System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   User Interfaces                        │  │
│  │  ┌─────────┬─────────────────┬────────────────────┐     │  │
│  │  │  Web UI │  Telegram Bot   │  Discord Webhook  │     │  │
│  │  └────┬────┴────┬────────────┴────┬───────────────┘     │  │
│  └───────┼─────────┼──────────────────┼──────────────────────┘  │
│          │         │                  │                        │
│  ┌───────┴─────────┴──────────────────┴──────────────────────┐  │
│  │              Django Application Layer                     │  │
│  │  ┌────────────┬─────────────┬──────────┬───────────────┐ │  │
│  │  │   Views    │   Models    │  Tasks   │   Channels   │ │  │
│  │  └────────────┴─────────────┴──────────┴───────────────┘ │  │
│  └──────────────────────┬──────────────────────────────────────┘  │
│                         │                                        │
│  ┌──────────────────────┴──────────────────────────────────────┐  │
│  │              Core AI Services Layer                        │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │              LLM Router & Providers               │   │  │
│  │  │  ┌─────────┬──────────┬────────┬────────────────┐ │   │  │
│  │  │  │ Gemini  │ OpenAI   │ Claude │ Others (10+)   │ │   │  │
│  │  │  └─────────┴──────────┴────────┴────────────────┘ │   │  │
│  │  │  • Fallback & Resilience Logic                    │   │  │
│  │  │  • Rate Limiting & Quota Management              │   │  │
│  │  │  • Error Handling & Retry Logic                  │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  │                                                             │  │
│  │  ┌──────────────┬──────────────┬──────────────────┐        │  │
│  │  │ Profile      │ Job Matching │ Resume Tailor &  │        │  │
│  │  │ Extraction   │ & Scoring    │ Application Kit  │        │  │
│  │  └──────────────┴──────────────┴──────────────────┘        │  │
│  │  • Evidence Scanning   • Job Source Integration            │  │
│  │  • Auto Application    • Manual Lead Import                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                         │                                        │
│  ┌──────────────────────┴──────────────────────────────────────┐  │
│  │                  Data Layer                               │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │     SQLite Database (SQLite 3)                      │  │  │
│  │  │  • Candidate Profiles     • Job Leads              │  │  │
│  │  │  • Applications           • Evidence               │  │  │
│  │  │  • Provider Settings      • Preferences            │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │                                                             │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Local File Storage (tmp_uploads/)                  │  │  │
│  │  │  • Resume PDFs/Docs        • Screenshots            │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Features

### 1. **Resume & Profile Extraction** 📄
- Extract candidate data from PDF/DOCX documents
- AI-powered information extraction with fallback validation
- Evidence-grounded profile storage with human review workflow
- Support for multiple file formats

### 2. **Job Matching & Scoring** 🎯
- Match candidate profiles against job descriptions
- AI-powered relevance scoring
- Filter by preferences (location, salary, role type, etc.)
- Deduplicated job lead import

### 3. **Smart Application Kit Generation** ✍️
Generate tailored, high-quality application materials:
- **Tailored Resume**: JSON format, optimized for the job
- **Cover Letter**: Personalized and compelling
- **Recruiter Message**: Professional outreach template
- **Follow-up Message**: Strategic follow-up script
- **Interview Prep**: Role-specific interview notes
- **Evidence Notes**: Links extracted experience to job requirements

### 4. **Multi-Provider Support** 🔀
Automatic routing and fallback across:
- Google Gemini
- OpenAI / GPT-4
- Anthropic / Claude
- xAI / Grok
- Groq
- OpenRouter
- DeepSeek
- Kimi / Moonshot
- Qwen / DashScope
- Local Ollama (optional)

**Fallback Logic**: Automatically handles provider errors, rate limits, quota failures, and cooldowns.

### 5. **Dashboard & Management** 📊
- **Queue Dashboard**: View pending jobs to review
- **Applications Dashboard**: Track submitted applications
- **Profile Evidence Dashboard**: Manage extracted skills and experience
- **Provider Settings**: Configure LLM API keys
- **Channel Settings**: Telegram/Discord webhook management
- **Preferences**: Set job search filters and criteria

### 6. **Multi-Channel Integration** 📱
- **Web UI** (Django): Full feature access via browser
- **Telegram Bot**: Receive job matches and manage applications
- **Discord Webhooks**: Integration with Discord servers
- **Allowlist-based Security**: Restrict bot access to authorized users/channels

### 7. **Advanced Job Sourcing** 🌐
- Manual job lead import with CSV/JSON support
- Automatic deduplication using fingerprints
- Job source integration (Python JobSpy)
- Web scraping support

### 8. **Resilience & Reliability** 🛡️
- Automatic retry with exponential backoff
- Provider rate limit handling
- Quota management across providers
- Graceful degradation when all providers fail
- Screenshot capture for application tracking

---

## Provider Support

### Quick Provider Status

All providers are **isolated and opt-in**. Missing API keys simply disable that provider.

| Provider | Status | Models | Cost | Best For |
|----------|--------|--------|------|----------|
| **Google Gemini** | ✅ Active | Flash, Pro | Free tier | Fast, reliable |
| **OpenAI** | ✅ Active | GPT-4, GPT-4 Turbo | Pay-as-you-go | Best quality |
| **Anthropic** | ✅ Active | Claude 3 | Pay-as-you-go | Strong reasoning |
| **xAI** | ✅ Active | Grok | API available | Novel approach |
| **Groq** | ✅ Active | Mixtral, LLaMA | Fast, free tier | Speed |
| **Ollama** | ✅ Active | Local models | Free (self-hosted) | Privacy, offline |
| **OpenRouter** | ✅ Active | 100+ models | Aggregator | Model variety |
| **DeepSeek** | ✅ Active | DeepSeek models | API available | Alternative |
| **Moonshot/Kimi** | ✅ Active | Kimi models | API available | Regional support |
| **DashScope/Qwen** | ✅ Active | Qwen models | API available | Alternative |

### Fallback Behavior

```
User Request
    ↓
[Check Enabled Providers]
    ↓
[Call Primary Provider] → Success? ✅ Return
    ↓
[Check for Failures]
    • Rate Limited?      → Cool down & retry
    • Quota Exceeded?    → Skip provider
    • Server Error?      → Try next provider
    • Network Error?     → Retry with backoff
    ↓
[Call Fallback Providers in Order] → Success? ✅ Return
    ↓
[All Failed?] → Return Clear UI Guidance:
    • "Wait [X] minutes and retry"
    • "Enable another API key"
    • "Turn on local Ollama"
    • "Retry manually"
    • "Continue without AI"
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- **At least one LLM API key** (Gemini recommended for free tier)

### Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ArPaN-DS/Job_bro_AI.git
   cd Job_bro_AI
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv job_finder_env
   
   # On Windows:
   .\job_finder_env\Scripts\activate
   
   # On macOS/Linux:
   source job_finder_env/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables**:
   ```bash
   copy .env.example .env
   # Or on macOS/Linux: cp .env.example .env
   ```

5. **Configure your `.env` file**:
   ```env
   # Django Configuration
   DJANGO_DEBUG=true
   DJANGO_SECRET_KEY=your-long-random-secret-key-here
   
   # LLM Provider Keys (add at least one)
   GEMINI_API_KEY=your_google_ai_studio_api_key
   # OPENAI_API_KEY=sk-...
   # ANTHROPIC_API_KEY=sk-ant-...
   
   # Optional: Local Ollama
   OLLAMA_ENABLED=false
   # OLLAMA_BASE_URL=http://localhost:11434
   # OLLAMA_MODEL=llama3.1
   
   # Optional: Telegram Bot
   TELEGRAM_BOT_TOKEN=
   TELEGRAM_ALLOWED_CHAT_IDS=
   
   # Optional: Discord Bot
   DISCORD_BOT_TOKEN=
   DISCORD_ALLOWED_IDS=
   ```

6. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

7. **Create superuser (optional, for admin panel)**:
   ```bash
   python manage.py createsuperuser
   ```

8. **Start development server**:
   ```bash
   python manage.py runserver
   ```

9. **Open in browser**:
   ```
   http://localhost:8000
   ```

### Verify Installation

```bash
# Check Django configuration
python manage.py check

# Run tests
python manage.py test

# Production-style deployment check
$env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"
python manage.py check --deploy
```

---

## Documentation

### User Guides
- **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** - Detailed installation and configuration
- **[USER_GUIDE.md](docs/USER_GUIDE.md)** - How to use the application
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Developer Documentation
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and components
- **[DATA_PIPELINE.md](docs/DATA_PIPELINE.md)** - Data flow and processing
- **[API_REFERENCE.md](docs/API_REFERENCE.md)** - Core modules and classes
- **[ADDING_PROVIDERS.md](docs/ADDING_PROVIDERS.md)** - How to add new LLM providers

### Deployment & Operations
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide
- **[ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)** - All configuration options

---

## Development

### Project Structure

```
Job_bro_AI/
├── career_agent/              # Django project settings
│   ├── settings.py            # Main Django configuration
│   ├── deploy_settings.py     # Production settings
│   ├── urls.py                # URL routing
│   ├── asgi.py & wsgi.py      # Application servers
│   └── static/                # CSS, JS, static assets
│
├── core/                       # Main application logic
│   ├── models.py              # Database models (Candidates, Applications, etc)
│   ├── views.py               # Django views & request handlers
│   ├── ai_service.py          # AI orchestration & extraction
│   ├── llm.py                 # LLM provider routing
│   ├── job_sources.py         # Job discovery & scraping
│   ├── resume_tailor.py       # Resume customization
│   ├── auto_applier.py        # Automated application submission
│   ├── evidence_scanner.py    # Profile evidence extraction
│   ├── profile_store.py       # Profile storage & retrieval
│   ├── channels.py            # Telegram/Discord integration
│   ├── schemas.py             # Pydantic data validation
│   ├── resilience.py          # Retry & error handling
│   ├── tasks.py               # Celery/async tasks
│   └── management/            # Custom Django commands
│
├── templates/                 # HTML templates
│   ├── base.html              # Base template
│   └── core/                  # App-specific templates
│
├── static/                    # CSS, JavaScript, images
│   └── css/
│
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md
│   ├── DATA_PIPELINE.md
│   ├── API_REFERENCE.md
│   └── ...
│
├── db.sqlite3                 # SQLite database (local)
├── requirements.txt           # Python dependencies
├── manage.py                  # Django CLI
├── .env.example               # Environment template
└── README.md                  # This file
```

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific test module
python manage.py test core.tests

# Run tests with verbose output
python manage.py test -v 2

# Run end-to-end tests (if available)
python test_e2e.py
```

### Code Style

The project follows Django and Python best practices:
- PEP 8 code formatting
- Type hints where applicable (Python 3.11+)
- Comprehensive docstrings
- Separation of concerns (models, views, services)

---

## Security & Privacy

### Local-First Privacy

✅ **All data stays on your machine** — No cloud sync unless you explicitly configure it.

### Security Best Practices

1. **Secret Management**:
   - Never commit `.env` files to Git
   - Use `.env.example` as a template only
   - Rotate API keys regularly

2. **API Key Safety**:
   - Each provider key is isolated
   - Failed provider doesn't expose other keys
   - Keys are never logged or sent between providers

3. **Database Security**:
   - Use strong `DJANGO_SECRET_KEY` in production
   - Enable HTTPS in production deployments
   - Restrict database access to application only

4. **Multi-Channel Security**:
   - Telegram/Discord use allowlist-based filtering
   - Only specified users/channels can trigger bots
   - Chat IDs are required in `.env` configuration

### Data Handling

- **Resume files** are stored locally and deleted after processing
- **Profile data** is stored in SQLite with optional encryption
- **Job matches** are stored with privacy preservation
- **No telemetry** or tracking is enabled by default

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Code style and standards
- Testing requirements
- Pull request process
- Issue reporting

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/Job_bro_AI.git
cd Job_bro_AI

# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
python manage.py test

# Commit and push
git add .
git commit -m "Feature: Add your feature"
git push origin feature/your-feature
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Support & Feedback

- 📝 **Issues**: Report bugs at [GitHub Issues](https://github.com/ArPaN-DS/Job_bro_AI/issues)
- 💬 **Discussions**: Ask questions at [GitHub Discussions](https://github.com/ArPaN-DS/Job_bro_AI/discussions)
- 📧 **Email**: Contact the maintainer

---

## Roadmap

- [ ] Mobile app (React Native)
- [ ] Database encryption at rest
- [ ] Advanced job filtering with ML
- [ ] Interview simulation with AI
- [ ] Email integration for job alerts
- [ ] LinkedIn profile auto-update
- [ ] Analytics dashboard for application success rates
- [ ] Batch application processing
- [ ] More LLM providers

---

**Made with ❤️ by [ArPaN-DS](https://github.com/ArPaN-DS)**

*Last Updated: May 2026*

## Public Safety

Before publishing or hosting, read:

- `SECURITY.md`
- `PUBLIC_LAUNCH_CHECKLIST.md`
- `.env.example`

Never commit `.env`, local SQLite databases, uploaded resumes, PDF/DOCX files,
or generated private profile data.

## Automation Boundary

The public default is review-first. The agent may prepare, score, draft, remind,
and track, but users should review every application before submitting.
`AUTO_SUBMIT_ENABLED` defaults to `false`.
