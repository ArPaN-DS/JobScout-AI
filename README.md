# Job_bro_AI 🚀

Welcome to **Job_bro_AI**! This is a self-hosted, local-first, privacy-centric AI career agent designed to help you discover job leads, evaluate your fit, auto-tailor application materials (resumes, cover letters, outreach messages), and track your pipeline.

Our default mode of operation is **Review-First**: the system automates discovery, match-scoring, and kit preparation, but you remain in full control to review, edit, and click submit.

---

## 🚀 Welcome, Freshers & New Contributors!

If you are joining the project or picking up this work for the first time, this document is designed specifically for you. It explains how to get set up, how the modules interact, and how to verify that everything works correctly in under 15 minutes.

---

## 🛠️ Prerequisites

Before you get started, make sure you have:
1. **Python 3.11 or newer** installed.
2. **pip** (Python package installer).
3. **Git** configured on your local machine.
4. An **LLM API Key** (e.g., Google Gemini, OpenAI, or Anthropic) OR a local **Ollama** installation for local offline inference.

---

## ⚙️ Quick Start Installation Guide

Follow these steps to get a local development instance running on your machine:

### 1. Clone the Repository
```bash
git clone https://github.com/ArPaN-DS/Job_bro_AI.git
cd Job_bro_AI
```

### 2. Set Up a Virtual Environment
A virtual environment isolates this project's dependencies from your global python setup.

*   **On Windows (Powershell / CMD):**
    ```powershell
    python -m venv job_finder_env
    .\job_finder_env\Scripts\activate
    ```
*   **On macOS/Linux:**
    ```bash
    python3 -m venv job_finder_env
    source job_finder_env/bin/activate
    ```

### 3. Install Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create local environment settings
Copy the template `.env.example` file to `.env`:
```bash
# Windows (Powershell / CMD):
copy .env.example .env

# macOS/Linux:
cp .env.example .env
```

Open the newly created `.env` file in your editor. At a minimum, set:
```env
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=replace-this-with-a-long-random-secret-key-at-least-50-chars
FIELD_ENCRYPTION_KEY=your-fernet-key-here
```
*Note on keys & credentials:*
* Generate a secure `FIELD_ENCRYPTION_KEY` by running:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode('utf-8'))"`
* Once `FIELD_ENCRYPTION_KEY` is configured in `.env`, you can add and update your LLM provider API keys directly in the web dashboard under **Provider Settings**. Alternatively, you can set them as environment variables (e.g., `GEMINI_API_KEY=...`).

### 5. Initialize the Database
Run migrations to set up the local SQLite database (`db.sqlite3`):
```bash
python manage.py migrate
```

### 6. Create an Admin User (Optional)
To access the Django Admin Console to view database tables directly:
```bash
python manage.py createsuperuser
```

### 7. Run the Web Server and Background Workers
Because Job_bro_AI runs background AI scoring tasks, you need to run **two** terminals side-by-side:

*   **Terminal 1: Web Interface Server**
    ```bash
    # Activate virtual environment first
    python manage.py runserver
    ```
*   **Terminal 2: Background Task Worker (django-q2)**
    ```bash
    # Activate virtual environment first
    python manage.py qcluster
    ```

Open your browser and navigate to `http://127.0.0.1:8000/`.

### 8. Authenticate and Log In
To protect your private resume and data, Job_bro_AI requires user login:
* If you did not create a superuser in step 6, run:
  ```bash
  python manage.py createsuperuser
  ```
* Open `http://127.0.0.1:8000/` in your browser. You will be redirected to the secure login screen.
* Enter your superuser credentials, sign in, and you will be directed to the main career agent dashboard!

---

## 📂 Core Folder Structure

A quick guide to finding your way around the codebase:

-   [`career_agent/`](file:///d:/Job_finder_AI/career_agent/): Django project settings, deployment rules, and root URL routing.
-   [`core/`](file:///d:/Job_finder_AI/core/): Main application folder.
    -   [`core/models.py`](file:///d:/Job_finder_AI/core/models.py): Defines the database schema (Job leads, Candidate profiles, applications, LLM logs).
    -   [`core/views.py`](file:///d:/Job_finder_AI/core/views.py): Handles URL requests and renders dashboard views.
    -   [`core/ai_service.py`](file:///d:/Job_finder_AI/core/ai_service.py): High-level career agent AI orchestration.
    -   [`core/llm.py`](file:///d:/Job_finder_AI/core/llm.py): Low-level LLM router (handles API keys, providers, and circuit breakers).
    -   [`core/tasks.py`](file:///d:/Job_finder_AI/core/tasks.py): Background worker tasks.
    -   [`core/sources/`](file:///d:/Job_finder_AI/core/sources/): Modules scraping or fetching jobs from job boards.
-   [`templates/`](file:///d:/Job_finder_AI/templates/): HTML5 templates for views.
-   [`static/`](file:///d:/Job_finder_AI/static/): CSS styling, icons, and client-side JavaScript.

---

## 📚 Deep-Dive Documentation Index

To understand the internal subsystems in detail, please consult these manuals:

1.  **[System Architecture Guide](docs/ARCHITECTURE.md)**: Explains the MVT architecture, sequence request flows, and extension patterns.
2.  **[Data Pipeline Documentation](docs/DATA_PIPELINE.md)**: Details document extraction, Pydantic validation schemas, and deduplication.
3.  **[Detailed Runtime Data Flows](docs/DATA_FLOW.md)**: Sequence diagrams mapping exactly how variables and responses move through the code.
4.  **[Supported Discovery Sources](docs/SUPPORTED_SOURCES.md)**: Details the active job search feeds and how to configure them.
5.  **[E2E and Integration Testing Manual](docs/E2E_TESTING.md)**: Instructions on running local test suites.
6.  **[Setup Guide & Troubleshooting](docs/SETUP_GUIDE.md)**: Resolving common installation errors.
7.  **[User Guide & Playbook](docs/USER_GUIDE.md)**: How to make the best use of the application features.
8.  **[Deployment Playbook](docs/DEPLOYMENT.md)**: How to host the application securely in production.
9.  **[Feature Roadmap](docs/TOP_NOTCH_ROADMAP.md)**: Future milestones and priorities.

---

## 🧪 Verification & Local Testing

Before pushing any changes to Git, always run the test suite to ensure nothing is broken.

1.  **Check Django Settings Integrity:**
    ```bash
    python manage.py check
    ```
2.  **Run Django Automated Unit and Workflow Tests:**
    ```bash
    python manage.py test
    ```
3.  **Check Production Settings Security Defaults:**
    ```bash
    # On Windows:
    $env:DJANGO_SETTINGS_MODULE="career_agent.deploy_settings"
    python manage.py check --deploy
    ```

---

## 🔒 Public Repository Hygiene

To keep your private information secure, the `.gitignore` is configured to prevent committing sensitive files. Never disable these ignores or commit:
-   Your `.env` file (contains raw API keys).
-   Your local database file `db.sqlite3`.
-   Uploaded resume documents or generated PDF application drafts under `tmp_uploads/`.
-   Personal metadata profile exports.

Keep `.env.example` updated with mock placeholders when adding new environment configurations.

---

## 🤝 Contributing

We welcome your ideas! Please check out [CONTRIBUTING.md](CONTRIBUTING.md) for style conventions, test coverage thresholds, and pull request procedures.
