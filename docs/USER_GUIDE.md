# User Guide

Complete step-by-step guide for using Job_bro_AI to find and apply for jobs.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Setting Up Your Profile](#setting-up-your-profile)
3. [Searching for Jobs](#searching-for-jobs)
4. [Evaluating Job Matches](#evaluating-job-matches)
5. [Generating Applications](#generating-applications)
6. [Submitting Applications](#submitting-applications)
7. [Managing Your Applications](#managing-your-applications)
8. [Using Telegram Bot](#using-telegram-bot)
9. [Configuring Providers](#configuring-providers)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### First Time Setup

1. **Access the application**
   - Open browser to: `http://localhost:8000` (local) or your deployed URL
   - You'll see the home dashboard

2. **Create admin account** (if first time)
   ```bash
   python manage.py createsuperuser
   ```
   - Username: your choice
   - Email: your email
   - Password: secure password

3. **Log in**
   - Click "Admin" or navigate to `/admin/`
   - Enter your credentials

### Dashboard Overview

The dashboard shows:
- **Active candidate profiles**: Count of candidates
- **Available jobs**: Imported job leads
- **Generated applications**: Ready and submitted
- **Recent activity**: Latest matches and submissions
- **Provider status**: LLM providers availability

---

## Setting Up Your Profile

### Step 1: Navigate to Profile Section

1. Click **"Profile"** in main navigation
2. Click **"New Profile"** or select existing profile to edit

### Step 2: Upload Resume

1. Click **"Upload Resume"** button
2. Select PDF or DOCX file from computer
3. Click **"Extract Profile"**

The AI will analyze your resume and extract:
- Name, email, phone, location
- Work experience and companies
- Technical and soft skills
- Education and certifications
- LinkedIn/GitHub URLs

### Step 3: Review Extracted Profile

1. Review the automatically extracted information
2. Fields show as two columns:
   - **Left**: AI-extracted data (read-only initially)
   - **Right**: Your verified/edited data

3. **Edit profile details**:
   - Name, email, phone
   - Location and work authorization
   - Availability (start date)
   - Professional URLs (LinkedIn, GitHub, portfolio)

### Step 4: Review Skills

The AI extracted skills appear with proficiency levels:
- **1**: Beginner
- **2**: Intermediate
- **3**: Proficient
- **4**: Advanced
- **5**: Expert

**Edit skills**:
1. Click skill to edit or remove
2. Click **"Add Skill"** to add new ones
3. Set proficiency level (1-5)

### Step 5: Confirm Profile

1. Review all sections:
   - Personal info
   - Skills
   - Work experience
   - Education
   - Certifications

2. Click **"Confirm Profile"** button

3. Your profile is now ready for job matching!

### Pro Tips

- **Detailed profiles**: The more detailed your profile, the better job matches
- **Skills specificity**: Use exact technology names (e.g., "Python 3.11" not "Programming")
- **Years of experience**: Keep experience dates accurate for better matching
- **Hidden profile**: Set to inactive if you want to pause job search

---

## Searching for Jobs

### Option 1: Browse Available Jobs

1. Click **"Jobs"** in navigation
2. See list of imported job leads
3. Filter by:
   - **Company**: Filter by company name
   - **Location**: Filter by location
   - **Posted**: Show recent jobs (last week, month, etc.)
4. Click job title to view full details

### Option 2: Import New Jobs

1. Click **"Import Jobs"** button
2. Enter search criteria:
   - **Job Title**: e.g., "Python Developer", "Data Scientist"
   - **Location**: e.g., "San Francisco", "Remote"
   - **Keywords**: Optional additional keywords
   - **Days Back**: Only show jobs from last N days

3. Click **"Search"**
4. System searches multiple job sources
5. New jobs are automatically imported and deduplicated

### Job Details Page

When viewing a job, you see:
- **Full description**: Complete job posting
- **Requirements**: Key requirements extracted
- **Match score**: 0-100 score with your profile (if generated)
- **Company info**: Company name, size, location
- **Application kit**: Generated resume, cover letter, messages (if generated)

---

## Evaluating Job Matches

### Automatic Matching

1. Go to **"Jobs"** page
2. Click **"Score All Matches"** to batch evaluate
3. AI evaluates your profile against all available jobs
4. Each job gets a match score (0-100)

**Score breakdown:**
- **90-100**: Excellent match
- **75-89**: Good match
- **60-74**: Possible match
- **40-59**: Weak match
- **Below 40**: Not recommended

### Manual Job Evaluation

1. Click on specific job to view details
2. Click **"Evaluate Match"** button
3. AI analyzes your fit for this job
4. View detailed scoring:
   - Skill match percentage
   - Experience match
   - Growth potential
   - Detailed reasoning

### Filtering Jobs by Match Score

1. Go to **"Jobs"** page
2. Use filter: **"Minimum Match Score"**
3. Set threshold (e.g., only show 75+ matches)
4. Focus on high-potential opportunities

---

## Generating Applications

### Automatic Generation

1. Go to job detail page
2. Click **"Generate Application"** button
3. System generates:
   - **Tailored resume**: Customized for specific job
   - **Cover letter**: Personalized cover letter
   - **Recruiter message**: Professional outreach message
   - **Follow-up message**: LinkedIn/email follow-up
   - **Interview prep**: Common interview questions and answers

4. Process completes (typically 30-60 seconds)
5. Review generated materials

### Manual Generation (Step-by-Step)

If you want to generate only specific materials:

1. Go to job detail ' **"Application Kit"** section
2. Click **"Generate Resume"** to customize resume only
3. Click **"Generate Cover Letter"** to create cover letter
4. Click **"Generate Messages"** for recruiter messages
5. Click **"Generate Interview Prep"** for interview preparation

### Customizing Generated Content

After generation, you can edit:

1. **Resume**: 
   - Click "Edit Resume"
   - Modify sections as needed
   - Add/remove experiences
   - Adjust skill highlighting

2. **Cover Letter**:
   - Click "Edit Letter"
   - Personalize tone and details
   - Add specific examples
   - Match your writing style

3. **Messages**:
   - Click "Edit Message"
   - Adjust tone and length
   - Add personal touches
   - Ensure authenticity

### Viewing Evidence Mapping

The system shows how your skills map to job requirements:

1. View **"Evidence Mapping"** section
2. See which of your skills/experience map to job requirements
3. Identify gaps that might need attention
4. Use this to decide whether to apply

---

## Submitting Applications

### Before Submission

1. **Review generated materials**:
   - Resume looks good
   - Cover letter is personalized
   - No typos or formatting issues

2. **Check job application method**:
   - **Online form**: Direct application through company site
   - **Email**: Submit via email address
   - **LinkedIn**: Apply through LinkedIn job portal
   - **Recruiter**: Contact recruiter directly

3. **Prepare**: Have any additional documents ready (portfolio, certifications, etc.)

### Submit Through Platform

1. Go to application detail page
2. Click **"Submit Application"** button
3. Choose submission method:
   - **Mark as Submitted**: Track within platform (manual submission)
   - **Generate Submission Kit**: Download all materials
   - **Share via Link**: Generate sharable link for recruiter

4. If "Mark as Submitted":
   - Confirmation added to record
   - Date and time logged
   - Status updated to "Submitted"

### Manual Submission Process

For manual applications (required for most jobs):

1. Generate application materials (resume, cover letter)
2. Go to company job posting URL (from Job Lead)
3. Follow company's application process:
   - Fill out form with your information
   - Attach tailored resume
   - Paste/upload cover letter
   - Add any requested documents

4. **Submit application on company site**

5. **Update status in Job_bro_AI**:
   - Go to application record
   - Click **"Mark as Submitted"**
   - Optional: Add screenshot of confirmation
   - Click **"Save"**

### Tracking Submissions

1. Go to **"Applications"** page
2. Filter by status:
   - **Draft**: Not yet submitted
   - **Ready**: Generated, awaiting submission
   - **Submitted**: Sent to company
   - **Interviewed**: Phone/video interview completed
   - **Offered**: Received job offer

3. See submission date for each application
4. Track follow-up dates

---

## Managing Your Applications

### Application Dashboard

1. Click **"Applications"** in navigation
2. View all generated applications
3. See status, date, and match score for each

### Updating Application Status

1. Click application record
2. Update status dropdown:
   - **Draft**: Still editing
   - **Ready**: Generated, not submitted
   - **Submitted**: Sent to company
   - **Phone Interview**: First phone screen
   - **Technical Interview**: Coding/technical test
   - **Final Interview**: Last round interview
   - **Offered**: Received job offer
   - **Rejected**: Rejected by company
   - **Withdrawn**: You withdrew

3. Click **"Save"**

### Adding Notes

1. Open application record
2. Go to **"Notes"** section
3. Add any important information:
   - Interview date/time
   - Interviewer names
   - Key talking points
   - Follow-up reminders
   - Salary negotiation notes

4. Click **"Save Notes"**

### Adding Screenshots

1. Open application record
2. Go to **"Screenshots"** section
3. Click **"Upload Screenshot"**
4. Select image from computer
5. File uploaded and attached to record

Useful for:
- Job posting confirmation
- Application confirmation
- Interview calendar invite
- Offer letter

### Following Up

1. Track "Last Contact" date
2. Add **"Follow-up Date"** reminder
3. System can notify you when to follow up
4. Update status after each interaction

---

## Using Telegram Bot

### Initial Setup

1. Find bot on Telegram: `@job_bro_ai_bot` (or your deployed bot)
2. Click **"Start"** or send `/start`
3. Bot asks for your verification code
4. Get code from: Profile ' Settings ' **"Telegram Bot"** ' Show Code
5. Send code to bot on Telegram
6. Confirmation: " Account connected"

### Telegram Commands

**Start receiving job matches:**
```
/start - Initialize bot connection
/status - Check connection and last sync
/jobs - Get latest job matches
/apply - Generate application for job
/notifications - Toggle notifications on/off
/settings - Adjust bot settings
/help - Show available commands
```

### Job Recommendations via Telegram

1. Bot automatically sends new high-scoring jobs:
   - Receives matches when new jobs imported
   - Only sends jobs scoring 75+ (configurable)
   - Includes match score and brief summary

2. You can reply with:
   - **"Score"**: Detailed match analysis
   - **"Apply"**: Generate application
   - **"Pass"**: Skip this job
   - **"Later"**: Remind me tomorrow
   - **"Details"**: Full job description

### Generating Applications via Telegram

1. Bot sends job: " Python Developer - TechCorp (85/100)"
2. Reply: `apply`
3. Bot generates application (30-60 seconds)
4. Bot sends back:
   - Generated resume (link)
   - Cover letter (link)
   - Recruiter message (in chat)
5. You: "Thank you! Applied!"
6. Status updated in platform

### Managing Notifications

1. In Telegram, send: `/notifications`
2. Choose settings:
   - **All jobs**: Every job score 0+
   - **Good matches**: Only 75+
   - **Excellent matches**: Only 90+
   - **Off**: No notifications

3. Change frequency:
   - **Real-time**: Immediately
   - **Digest**: Once daily summary
   - **Weekly**: Every Sunday

---

## Configuring Providers

### LLM Providers Configuration

Different AI providers can be used. Configure in:
1. Go to **"Settings"** ' **"Providers"**
2. Add your API keys
3. Enable/disable providers

### Available Providers

1. **Gemini** (Google)
   - Set: `GEMINI_API_KEY`
   - Free tier available
   - Very capable model

2. **OpenAI** (ChatGPT/GPT-4)
   - Set: `OPENAI_API_KEY`
   - High quality output
   - Paid service

3. **Anthropic** (Claude)
   - Set: `ANTHROPIC_API_KEY`
   - Excellent reasoning
   - Premium service

4. **Open Router** (Multiple providers)
   - Set: `OPENROUTER_API_KEY`
   - Route to multiple models
   - Pay-per-use

5. **Groq** (Speed-focused)
   - Set: `GROQ_API_KEY`
   - Very fast inference
   - Growing model selection

6. **Ollama** (Local/Open source)
   - No API key needed
   - Run locally on your machine
   - Privacy-focused

### Testing Providers

1. Go to **"Settings"** ' **"Providers"**
2. Click **"Test"** next to provider
3. System sends test prompt
4. See response quality and speed
5. Use fastest, most reliable provider

### Provider Priority

System tries providers in order:
1. Primary provider (fastest/cheapest)
2. Secondary providers (if primary fails)
3. Fallback provider (always-working backup)

Set in Settings ' **"Provider Priority"**

---

## Troubleshooting

### Common Issues

#### 1. Resume Upload Fails

**Problem**: "Error uploading resume"

**Solutions**:
- File size: Ensure < 10MB
- File format: Use PDF or DOCX
- File type: Ensure real document (not corrupted)
- Try again: System may have temporary error

**To fix**:
```
1. Check file size: File ' Properties ' Size
2. Convert to PDF if needed (use Google Docs, etc.)
3. Wait 30 seconds and try again
4. Check browser console for errors (F12)
```

#### 2. Profile Extraction Shows Wrong Data

**Problem**: "AI extracted wrong name, skills, etc."

**Solutions**:
- AI misread resume: Manually correct in profile
- Format issues: Clean up resume formatting
- Ambiguous content: Make resume clearer

**To fix**:
```
1. Edit profile fields manually
2. Confirm/verify extracted data
3. System learns from corrections
```

#### 3. Job Matching Score is 0 or Too Low

**Problem**: "All jobs show low match scores"

**Solutions**:
- Incomplete profile: Add more skills/experience
- Specific job requirements: Job has very niche requirements
- Profile too broad: Narrow down to specific roles

**To fix**:
```
1. Go to Profile ' Review section
2. Add more detailed skills with levels
3. Ensure work experience is complete
4. Re-match jobs after updating profile
```

#### 4. LLM Provider Fails/Times Out

**Problem**: "OpenAI API key invalid" or "Request timeout"

**Solutions**:
- Invalid API key: Check key in settings
- Rate limited: Too many requests to provider
- Provider down: Provider service experiencing issues
- Poor connection: Internet connectivity issue

**To fix**:
```
1. Go to Settings ' Providers
2. Test each provider
3. Check API key (valid and not expired)
4. Wait 5 minutes (rate limit window)
5. Use different provider as fallback
```

#### 5. Can't Authenticate Telegram Bot

**Problem**: "Invalid verification code"

**Solutions**:
- Wrong code: Copy-paste the full code
- Expired code: Generate new code in platform
- Not connected yet: Ensure bot is activated

**To fix**:
```
1. Go to Settings ' Telegram ' Generate New Code
2. Copy full code
3. In Telegram: /start
4. Send code when bot asks
5. Confirm connection
```

#### 6. Generated Cover Letter is Too Generic

**Problem**: "Cover letter doesn't mention specific details"

**Solutions**:
- Edit manually after generation
- Add personal anecdotes
- Research company beforehand
- Customize for each application

**To fix**:
```
1. After generation, click "Edit Cover Letter"
2. Add specific company details
3. Personalize with your story
4. Save edited version
5. Copy to company application
```

#### 7. Application Submission Not Tracked

**Problem**: "Can't update application status"

**Solutions**:
- Not logged in: Log in again
- Database issue: Try later
- Cache: Clear browser cache and refresh

**To fix**:
```
1. Click "Mark as Submitted"
2. If fails, wait 10 seconds
3. Try again
4. If still fails: Clear browser cache (Ctrl+Shift+Del)
5. Refresh page and try again
```

#### 8. Can't Find Job I'm Looking For

**Problem**: "Job not imported into system"

**Solutions**:
- Not imported yet: Import manually
- Too old: Job posting expired
- Not available in sources: Try different source

**To fix**:
```
1. Click "Import Jobs"
2. Enter: Job Title, Location, Keywords
3. Click Search
4. Wait for import to complete
5. View newly imported jobs
```

### Checking System Health

#### Check LLM Provider Status

```
Settings ' Providers ' Click "Test" next to each
```

#### View Recent Errors

```
Admin ' Logs ' See recent application errors
```

#### Check Database Connection

```
Admin ' System Health ' Database Status
```

#### View Task Queue Status

```
Admin ' Tasks ' See pending/failed tasks
```

### Getting Help

1. **Check documentation**: [docs/](../README.md#documentation)
2. **Search existing issues**: [GitHub Issues](https://github.com/ArPaN-DS/Job_bro_AI/issues)
3. **Report bug**: [GitHub Issues -> New Issue](https://github.com/ArPaN-DS/Job_bro_AI/issues/new)
4. **Security issue**: Use a private maintainer channel or GitHub security advisory when available.

### Enable Debug Logging

For development/debugging:

1. Set in .env:
   ```
   DJANGO_DEBUG=True
   LOG_LEVEL=DEBUG
   ```

2. Check logs:
   ```
   tail -f logs/debug.log
   ```

3. Check console output for detailed error messages

---

## Best Practices

### For Better Job Matches

1.  **Complete profile**: Fill all sections
2.  **Accurate skills**: Use exact technology names
3.  **Clear experience**: Detail your accomplishments
4.  **Regular updates**: Keep profile current
5.  Don't: Leave fields blank or generic

### For Better Applications

1.  **Personalize materials**: Edit before sending
2.  **Proofread**: Check grammar and spelling
3.  **Research company**: Reference in cover letter
4.  **Follow instructions**: Read job posting carefully
5.  **Track everything**: Update application status
6.  Don't: Send generic applications

### For Success

1. " **Monitor metrics**: Track response rate
2. " **Follow up**: Contact recruiters after 1 week
3.  **Target strategically**: Focus on best matches
4. ' **Prepare**: Study company before interview
5.  **Network**: Reference from employees if possible
6. " **Iterate**: Refine approach based on results

---

## Keyboard Shortcuts

- `G` ' Go to Jobs page
- `P` ' Go to Profile page
- `A` ' Go to Applications page
- `S` ' Open Settings
- `?` ' Show this help menu

---

## Contacting Support

- **GitHub**: [ArPaN-DS/Job_bro_AI](https://github.com/ArPaN-DS/Job_bro_AI)
- **Issues**: [Report a bug](https://github.com/ArPaN-DS/Job_bro_AI/issues/new)

---

**Happy job hunting! **
