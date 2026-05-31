"""Versioned prompt templates for LLM tasks."""

from __future__ import annotations

import json
from typing import Any

PROMPT_VERSION = "1.0.0"


def build_profile_extract_prompt(resume_text: str) -> str:
    return f"""
You are a careful technical recruiter. Extract the candidate profile from the resume text.

Rules:
- Return JSON only.
- Do not invent missing fields.
- Preserve exact company names, role titles, durations, skills, and experience highlights from the resume.
- Keep skills atomic, for example "Python" instead of "Python and Django".

JSON shape:
{{
  "name": "Full Name",
  "email": "Email Address",
  "phone": "Phone Number",
  "skills": ["Skill"],
  "experience": [
    {{
      "company": "Company Name",
      "role": "Job Title",
      "duration": "Start - End Date",
      "highlights": ["Evidence-backed resume bullet"],
      "evidence": ["Short quote or resume fact supporting the highlight"]
    }}
  ],
  "domains": ["Domain"],
  "job_preferences": {{
    "target_roles": [],
    "locations": [],
    "remote_preferences": [],
    "min_salary": "",
    "experience_level": "",
    "visa_status": "",
    "blocked_companies": [],
    "must_have_skills": []
  }},
  "evidence_notes": ["Important source facts from the resume"]
}}

Resume text:
{resume_text}
""".strip()


def build_job_match_prompt(profile_dict: dict[str, Any], job_description: str) -> str:
    return f"""
You are a conservative recruiting analyst. Compare the candidate profile with the job description.

Accuracy rules:
- Score only skills and experience explicitly present in the candidate profile.
- Do not give credit for adjacent or implied skills unless the profile states them directly.
- Put uncertain or weak evidence in risk_flags.
- Respect job_preferences as hard filters when the job conflicts with them.
- Keep the summary factual and concise.

JSON shape:
{{
  "match_score": 0,
  "summary": "Two factual sentences.",
  "matching_skills": ["Skill found in both job and profile"],
  "missing_skills": ["Important job skill not found in profile"],
  "confidence": 0,
  "risk_flags": ["Reason this match may be weaker than the score suggests"],
  "hard_filters": ["Deal-breaker mismatch, if any"],
  "why_apply": "One practical reason this role is worth applying to.",
  "salary_signal": "Salary or compensation signal if present.",
  "seniority_alignment": "How the role level aligns with the profile."
}}

Candidate profile JSON:
{json.dumps(profile_dict, ensure_ascii=False)}

Job description:
{job_description.strip()}
""".strip()


def build_application_kit_prompt(profile_dict: dict[str, Any], job_description: str) -> str:
    return f"""
You are a strict resume tailoring assistant. Build a targeted application kit.

Grounding rules:
- Use only facts present in the candidate profile JSON.
- Use exact skill strings from candidate_profile.skills. Do not create new skill names.
- Use exact company, role, and duration values from candidate_profile.experience.
- You may rephrase existing highlights for clarity, but you may not add new tools, metrics, employers, dates, or outcomes.
- If the job asks for a missing skill, do not include it in the resume.

JSON shape:
{{
  "tailored_resume": {{
    "name": "Candidate Name",
    "skills": ["Exact skill from candidate_profile.skills"],
    "experience": [
      {{
        "company": "Exact company from profile",
        "role": "Exact role from profile",
        "duration": "Exact duration from profile",
        "highlights": ["Rephrased but evidence-backed highlight"]
      }}
    ]
  }},
  "cover_letter": "Professional 3-paragraph cover letter grounded only in profile facts.",
  "recruiter_message": "Short LinkedIn or email message grounded only in profile facts.",
  "follow_up_message": "Short follow-up message after applying.",
  "interview_prep_notes": ["Concrete interview prep note based on job and profile"]
}}

Candidate profile JSON:
{json.dumps(profile_dict, ensure_ascii=False)}

Job description:
{job_description.strip()}
""".strip()


def build_critic_prompt(profile_dict: dict[str, Any], job_description: str, kit_dict: dict[str, Any]) -> str:
    return f"""
You are a strict hiring compliance reviewer. Audit the application kit against the candidate profile.

Rules:
- approved must be true only if every skill and experience entry in tailored_resume exists in the profile.
- Flag any invented metrics, employers, tools, or skills in issues.
- List specific unsupported_claims (exact strings) when present.
- Be conservative: if uncertain, set approved to false.

JSON shape:
{{
  "approved": true,
  "issues": ["Short issue description"],
  "unsupported_claims": ["Claim not backed by profile"]
}}

Candidate profile JSON:
{json.dumps(profile_dict, ensure_ascii=False)}

Job description:
{job_description.strip()}

Application kit JSON:
{json.dumps(kit_dict, ensure_ascii=False)}
""".strip()
