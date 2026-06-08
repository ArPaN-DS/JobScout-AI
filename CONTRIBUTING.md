# Contributing to JobScout-AI

Thank you for your interest in helping make **JobScout-AI** the best open-source, self-hosted career agent! We welcome contributions from developers of all skill levels.

---

## ◆ Project Philosophy & Core Rules

Before writing any code, please keep our foundational guidelines in mind:
▪ **Local-First & Privacy-First:** All applicant resumes, credentials, and databases must reside locally. We never upload candidate PII to external clouds without consent.
▪ **Review-First by Default:** We automate the tedious parts (job discovery, matching, resume tailoring, drafting answers), but the human is always the pilot. The system preparing a kit should never auto-submit applications without explicit confirmation.
▪ **No Commits with Secrets/Private Data:** Never commit `.env` files, local SQLite databases (`db.sqlite3`), profile JSON exports, or PDF resumes. Our `.gitignore` is heavily strict to protect your data.
▪ **Adapter Pattern for Integrations:** All LLM models and scraping services must be behind adapters. This isolates breaking API changes and keeps the core orchestration logic clean.

---

## ◆ Development Setup in 5 Minutes

We have automated the onboarding process to make setup frictionless.

### 1. Fork and Clone
Fork the repository on GitHub, and clone it locally:
```bash
git clone https://github.com/YOUR-USERNAME/JobScout-AI.git
cd JobScout-AI
```

### 2. Run the Onboarding Runner Script
Our one-command runner script configures the virtual environment, installs dependencies, generates secure keys, and runs migrations automatically.

* **On Windows (PowerShell / CMD):**
  ```powershell
  # Double-click or run from terminal:
  .\setup.bat
  ```
* **On macOS / Linux (Terminal):**
  ```bash
  # Ensure the script is executable, then run:
  chmod +x setup.sh
  ./setup.sh
  ```

*The script will automatically create a default admin superuser (Username: `admin`, Password: `admin123`) so you can log in instantly.*

### 3. Create a Feature Branch
```bash
git checkout -b feature/your-awesome-feature
# Or for bug fixes:
git checkout -b fix/issue-description
```

---

## ◆ Verification & Testing

Always verify that the test suite passes before submitting your changes.

### Running Automated Tests
```bash
# Check Django settings integrity
python manage.py check

# Run all unit and workflow tests
python manage.py test
```

### Testing Production Deployment Rules
Ensure your changes do not violate basic security standards:
```bash
# On Windows:
$env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"
python manage.py check --deploy

# On macOS/Linux:
DJANGO_SETTINGS_MODULE="career_agent.deploy_settings" python manage.py check --deploy
```

---

## ◆ Coding & Style Standards

### Python Code Style
▪ Follow **PEP 8** style guidelines.
▪ Use **Type Hints** for all function signatures (Python 3.11+).
▪ Indentation: 4 spaces.
▪ Maximum line length: 100 characters.

<details>
<summary><b>▸ Click to view Python coding standards & Google-style docstring examples</b></summary>

### Google-Style Docstrings & Style Example
Document your functions using Google-style docstrings:
```python
from typing import Optional, List
from django.db import models

def encrypt_value(plain_text: str) -> str:
    """Encrypts a string and returns a web-safe base64 string.
    
    Args:
        plain_text: The raw string containing sensitive credential data.
        
    Returns:
        The symmetrically encrypted base64 ciphertext.
        
    Raises:
        ValueError: If encryption fails due to a missing key.
    """
    pass

def generate_cover_letter(
    candidate: str,
    job_description: str,
    company_name: str,
) -> str:
    """Generate a personalized cover letter.
    
    Args:
        candidate: Candidate's name
        job_description: Job requirements
        company_name: Target company name
    
    Returns:
        Generated cover letter text
    
    Raises:
        ValueError: If any required field is empty
        AIServiceError: If LLM call fails
    
    Example:
        >>> letter = generate_cover_letter(
        ...     "John Doe",
        ...     "5+ years Python...",
        ...     "TechCorp"
        ... )
        >>> len(letter) > 100
        True
    """
    pass
```

### Testing Pattern Example
Write tests for new functionality:
```python
from django.test import TestCase
from core.services import extract_skills

class SkillExtractionTestCase(TestCase):
    """Test skill extraction from resumes."""
    
    def test_extract_common_skills(self):
        """Test extraction of common programming skills."""
        resume = "I have Python and Django experience"
        skills = extract_skills(resume)
        
        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
```
</details>

---

## ◆ Extending the Codebase

<details>
<summary><b>▸ Click to view code examples for adding LLM Providers & Scrapers</b></summary>

### 1. Adding a New LLM Provider
To add support for a new LLM provider (e.g., DeepSeek, Groq, local models):
1. Implement your provider adapter in `core/llm.py` inheriting from `BaseLLMAdapter`.
2. Register the provider in the `LLMRouter` inside `core/llm.py`.
3. Add mock credentials to `.env.example` with detailed comments.
4. Write unit tests for your provider's responses and rate-limiting fallbacks.

```python
class GroqProvider(BaseLLMProvider):
    """Groq API provider implementation."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com"
        self.model = "mixtral-8x7b-32768"
    
    def call(self, prompt: str, schema: Type[T]) -> LLMResult:
        """Call Groq API."""
        try:
            response = self._make_request(prompt)
            return LLMResult(
                status="success",
                output=response,
                provider="groq"
            )
        except Exception as e:
            return self.handle_error(e)
```

### 2. Adding a New Job Board Source
To add a new scraping or search adapter (e.g., RSS feeds, company portals):
1. Subclass `BaseJobSource` in `core/sources/base.py`.
2. Implement the `fetch()` and `normalize()` methods.
3. Register the new source in the auto-queue ingestion scheduler.
</details>

---

## ◆ Submitting a Pull Request (PR)

1. Push your branch to your forked repository:
   ```bash
   git push origin feature/your-awesome-feature
   ```
2. Open a Pull Request against our `main` branch.
3. Complete the pull request checklist (our template will ask you to verify that linting, security checks, and unit tests have all passed).
4. A maintainer will review your changes and guide you through the merging process.

Thank you for dedicating your time to helping job hunters navigate the job search with dignity and privacy!
