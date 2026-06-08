## 📤 Pull Request Description

Provide a clear summary of your changes, the motivation behind them, and what problems they resolve.

---

## 🛠️ Type of Change
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] 💡 New feature (non-breaking change which adds functionality)
- [ ] 🧼 Code style / Refactoring (formatting, renaming, restructuring)
- [ ] 📚 Documentation update (README, docs, docstrings)
- [ ] 🧪 Testing (adding or improving unit tests)

---

## 🧪 Testing and Verification Checklist

Please verify that all tests and checks pass before submitting your PR.

### 1. Automated Unit Tests
- [ ] I have run `python manage.py test` locally.
- [ ] All tests passed successfully.
- [ ] I have added new unit tests covering my changes (if applicable).

### 2. Django Configuration & Deploy Checks
- [ ] I have verified settings using `python manage.py check`.
- [ ] I have validated security defaults by running:
  ```bash
  # Windows:
  $env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"; python manage.py check --deploy
  # Unix/Linux:
  DJANGO_SETTINGS_MODULE="career_agent.deploy_settings" python manage.py check --deploy
  ```

### 3. Git Hygiene
- [ ] I have confirmed that no local `.env` files, SQLite databases, or private uploads are tracked via git (run `git status` to verify).

---

## 📖 Additional Documentation
- [ ] I have updated the relevant `.md` documentation in `docs/` (if applicable).
- [ ] I have updated `.env.example` (if adding new environment variables).
- [ ] I have followed the PEP 8 coding standards and added type hints.
