---
name: 🐛 Bug Report
about: Create a report to help us improve JobScout-AI.
title: "[BUG] "
labels: bug
assignees: ''

---

## 🐛 Bug Report

### Environment Details
- **Operating System (OS):** [e.g., Windows 11, macOS Sequoia, Ubuntu 24.04]
- **Python Version:** [e.g., 3.11.2]
- **Django Version:** [e.g., 5.0]
- **Database:** SQLite (Local)

### 🤖 AI Provider & Model Configuration
- **Primary LLM Provider:** [e.g., Gemini, OpenAI, Groq, Ollama (Local)]
- **Model Name:** [e.g., gemini-2.5-flash, llama3.1]
- **Critic Enabled:** [Yes / No] (Is `KIT_CRITIC_ENABLED` set to True?)

### 🌐 Playwright Browser Automation Indicator
- **Did this occur during browser form-filling / automation?** [Yes / No / Not Applicable]
- **Browser Type:** [Chromium / Firefox / WebKit]
- **Headless Mode:** [Yes / No]
- **Playwright Log Snippet:** (If form-filling failed, paste relevant console prints from `media/browser_sessions/` if available, **redacting personal info**)

---

### Steps to Reproduce
1. Go to page '...'
2. Click on '...'
3. Upload resume / start discovery task
4. See error message

### Expected Behavior
Describe what should have occurred.

### Actual Behavior
Describe what actually happened (include screenshots if UI is broken).

### 📋 Runtime Logs
Paste your server logs or background task worker (`python manage.py qcluster`) outputs here. 
> [!WARNING]
> **Remove any API keys, phone numbers, email addresses, or personal resume details before posting!**

```text
# Paste server traceback or logs here
```
