# Job_bro_AI: Personal AI Career Agent (Version 1)

Job_bro_AI is a highly tailored, local Python/Django application designed to act as a **Personal AI Job Assistant**. It strictly follows an **"AI prepares → Human reviews → Human submits"** philosophy to minimize manual job application fatigue while maintaining 100% accuracy and zero hallucinations.

## 🚀 Features (Version 1)

1. **Master Profile AI Extraction:**
   - Upload your highly unstructured PDF resume.
   - The system utilizes **Gemini 1.5 Flash** to silently extract your experiences, projects, matching skills, and domains into a structured "Master Profile".

2. **Job Discovery & Scoring Engine:**
   - Drop in any chaotic Job Description text.
   - The engine cross-references the job requirements against your Master Profile, generating a real-time **Match Score (0-100%)**, a match summary, and a precise breakdown of matching vs. missing skills.

3. **Zero-Hallucination Application Kit (Gemini Pro):**
   - Click "Generate Kit" to invoke **Gemini 1.5 Pro**.
   - The AI rewrites your specific resume bullet points to naturally align with the job's ATS keywords.
   - It drafts a highly personalized Cover Letter based *only* on your real extracted experience.
   - **Strict Constraint:** The AI is heavily prompted to NEVER invent fake skills or experiences.

4. **"Glassdoor" Error Transparency:**
   - Built-in UI architecture directly surfaces deeply nested Python/API exceptions completely transparently, making it impossible for network or quota errors to fail silently.

5. **Local SQLite Tracking:**
   - Click "Mark as Submitted" to drop the application, resume iteration, and cover letter into an offline SQLite database for future analysis.

---

## 🛠️ Technology Stack

- **Backend Framework:** Django (Python)
- **Database:** SQLite3
- **AI / LLM Integration:** Google GenAI SDK (`gemini-2.5-flash` for extraction/matching, `gemini-2.5-pro` for heavy reasoning & kit generation).
- **PDF Parsing:** `pdfplumber`
- **Frontend UI:** Vanilla HTML5, CSS3 (Custom Glassmorphism Design), Vanilla ES6 JavaScript (Fetch API/AJAX).
- **Network Routing:** `ngrok` (Exposing the local server).

---

## ⚙️ Installation & Setup (Local)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ArPaN-DS/Job_bro_AI.git
   cd Job_bro_AI
   ```

2. **Set up the Virtual Environment:**
   ```bash
   python -m venv job_finder
   # Windows:
   .\job_finder\Scripts\activate
   # Mac/Linux:
   source job_finder/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables:**
   - Create a `.env` file in the root directory.
   - Add your Gemini API Key:
     ```env
     GEMINI_API_KEY=your_google_ai_studio_api_key
     ```

5. **Run Database Migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Start the Django Server:**
   ```bash
   python manage.py runserver
   ```
   *Visit `http://localhost:8000` to access the dashboard.*

---

## 🔮 Roadmap (Phase 2: Automated Scraping Engine)

Version 2 (Upcoming) will handle automated Job hunting directly, removing the need for manual Job Description copying.

- **Background Workers:** Integration of `Celery` or Django Q.
- **24-Hour Job Stream:** Playwright-based scraper scripts specifically targeting roles posted in the **Last 24 Hours** on platforms like LinkedIn, Naukri, Glassdoor, and Indeed.
- **Multimodal Scraping:** Utilizing **Gemini 2.0 Flash Multimodal** to process raw HTML/dom snapshots rather than relying on brittle XPath/CSS selectors.
- **Auto-Filtering:** Jobs scoring below a 60% match threshold will be silently discarded into the background, maintaining a high-signal dashboard.

---
*Created by Arpan. Built for personal workflow optimization.*
