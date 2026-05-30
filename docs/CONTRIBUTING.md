# Contributing Guidelines

We welcome contributions from the community! Job_bro_AI is designed to be extensible, and we're excited to see how you'll help improve it.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the issue, not the person
- Help others learn and grow

---

## Ways to Contribute

### 1. Report Bugs 🐛

If you find a bug, please open an issue with:
- **Clear title**: Describe the problem in 1 sentence
- **Environment**: Python version, OS, how you installed Job_bro_AI
- **Steps to reproduce**: Exact steps to trigger the bug
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs/screenshots**: Relevant error messages or screenshots

**Issue Template:**
```markdown
## Bug Report

### Title
Clear, concise title here

### Environment
- Python Version: 3.11
- OS: Windows 10
- Installation: pip install -r requirements.txt

### Steps to Reproduce
1. ...
2. ...
3. ...

### Expected Behavior
What should happen

### Actual Behavior
What actually happens

### Logs
```
error message here
```

### Screenshots
(if applicable)
```

### 2. Request Features ✨

**Issue Template:**
```markdown
## Feature Request

### Description
What feature would you like?

### Motivation
Why is this important?

### Proposed Solution
How should it work?

### Alternatives Considered
Other approaches?

### Additional Context
Any other info?
```

### 3. Improve Documentation 📚

Documentation is just as important as code!

- Fix typos or unclear explanations
- Add examples or guides
- Improve diagrams
- Translate documentation

### 4. Fix Bugs or Add Features 💻

This is our primary contribution path.

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- Virtual environment (venv/virtualenv)
- Basic Git knowledge

### Local Development

1. **Fork the repository**
   ```bash
   # On GitHub, click "Fork"
   # Then clone your fork:
   git clone https://github.com/YOUR-USERNAME/Job_bro_AI.git
   cd Job_bro_AI
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies (including dev)**
   ```bash
   pip install -r requirements.txt
   # Note: Add development dependencies here if needed
   pip install pytest pytest-django flake8
   ```

4. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # Or for bugs:
   git checkout -b fix/bug-description
   ```

5. **Make your changes**
   - Write code following project style
   - Add tests for new functionality
   - Update documentation

6. **Test your changes**
   ```bash
   # Run unit tests
   python manage.py test
   
   # Run specific test module
   python manage.py test core.tests.TestProfileExtraction
   
   # Run with coverage
   coverage run --source='.' manage.py test
   coverage report
   ```

7. **Code style and linting**
   ```bash
   # Check code style
   flake8 core/ --max-line-length=100
   
   # Format code
   black core/ --line-length=100
   ```

8. **Commit with clear messages**
   ```bash
   git add .
   git commit -m "feature: Add new AI provider integration"
   # Or
   git commit -m "fix: Correct bug in job matching algorithm"
   ```

   **Commit message format:**
   ```
   <type>: <subject>
   
   <body>
   
   <footer>
   ```
   
   Types: `feature`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
   
   Example:
   ```
   feature: Add Groq provider support
   
   - Implement GroqProvider class
   - Add GROQ_API_KEY configuration
   - Add fallback handling for rate limits
   - Update documentation
   
   Fixes #123
   ```

9. **Push and create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```
   
   Then on GitHub:
   - Click "Compare & pull request"
   - Fill in PR template (see below)
   - Ensure CI checks pass

---

## Pull Request Process

### PR Requirements

- **Title**: Clear, descriptive PR title
- **Description**: Explain what, why, how
- **Linked Issues**: Reference related issues
- **Tests**: Include tests for new code
- **Documentation**: Update docs if needed
- **No breaking changes**: Without discussion first

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Related Issues
Fixes #123
Related to #456

## Testing
- [ ] Unit tests added
- [ ] Manual testing completed
- [ ] All tests passing

## Screenshots
(if UI changes)

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed self-review
- [ ] I have commented my code
- [ ] I have updated documentation
- [ ] No new warnings generated
- [ ] My changes don't break existing tests
```

### Review Process

1. **Automated checks run**:
   - Tests pass
   - Code style checks pass
   - No security issues

2. **Manual review**:
   - Maintainers review code
   - May request changes
   - Approve or request modifications

3. **Merge**:
   - After approval and checks pass
   - Commits squashed if needed
   - PR merged to main

---

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/)
- Use type hints (Python 3.11+)
- Maximum line length: 100 characters
- 4 spaces for indentation

### Example

```python
from typing import Optional, List
from django.db import models

def extract_skills(resume_text: str, max_skills: int = 20) -> List[str]:
    """
    Extract top skills from resume text.
    
    Args:
        resume_text: Full resume text content
        max_skills: Maximum number of skills to extract
    
    Returns:
        List of extracted skill names
    
    Raises:
        ValueError: If resume_text is empty
    """
    if not resume_text:
        raise ValueError("Resume text cannot be empty")
    
    # Processing logic here
    skills: List[str] = []
    return skills[:max_skills]
```

### Docstrings

Use Google-style docstrings:

```python
def generate_cover_letter(
    candidate: str,
    job_description: str,
    company_name: str,
) -> str:
    """
    Generate a personalized cover letter.
    
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
    ...
```

### Testing

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
    
    def test_empty_resume_raises_error(self):
        """Test that empty resume raises ValueError."""
        with self.assertRaises(ValueError):
            extract_skills("")
    
    def test_max_skills_limit(self):
        """Test that max_skills parameter is respected."""
        resume = "Python Django FastAPI Flask Celery Redis..."
        skills = extract_skills(resume, max_skills=3)
        
        self.assertEqual(len(skills), 3)
```

---

## Extending Job_bro_AI

### Adding a New LLM Provider

1. **Create provider class** in `core/llm.py`

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

2. **Add to router** in `core/llm.py`

```python
PROVIDERS = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "groq": GroqProvider,  # New!
}
```

3. **Add configuration** to `.env.example`

```env
# Groq API
GROQ_API_KEY=your_groq_api_key_here
```

4. **Write tests**

```python
def test_groq_provider():
    """Test Groq provider integration."""
    provider = GroqProvider("test-key")
    result = provider.call("test prompt", TestSchema)
    assert result.status == "success"
```

5. **Update documentation**

### Adding a New Job Source

1. **Create job source class** in `core/job_sources.py`

```python
class LinkedInJobSource(BaseJobSource):
    """LinkedIn job scraper."""
    
    def fetch(self, query: str, filters: dict) -> List[JobLead]:
        """Fetch jobs from LinkedIn."""
        ...
    
    def normalize(self, raw_job: dict) -> JobLead:
        """Normalize job data."""
        ...
```

2. **Register in router**

### Adding a New Channel

1. **Create handler** in `core/channels.py`
2. **Add webhook endpoint** in `core/urls.py`
3. **Write tests and documentation**

---

## Issue Labels

- `bug` - Bug reports
- `feature` - Feature requests
- `documentation` - Documentation
- `good first issue` - Good for newcomers
- `help wanted` - Need assistance
- `question` - Questions
- `enhancement` - Improvements
- `critical` - High priority

---

## Communication

- **GitHub Issues**: For bugs and features
- **GitHub Discussions**: For questions
- **Email**: arpanmajumdar952@gmail.com (maintainer)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Recognition

We recognize all contributors! Your name and contributions will be celebrated in:
- GitHub contributors page
- CONTRIBUTORS.md file
- Release notes

Thank you for contributing to Job_bro_AI! 🙌
