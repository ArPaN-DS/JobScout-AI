import pdfplumber
from google import genai
from google.genai import types
import json
import os
from dotenv import load_dotenv

load_dotenv()

def extract_profile_from_pdf(pdf_path):
    """
    Reads a PDF, extracts text, and uses Gemini to parse it into a structured JSON profile.
    """
    # 1. Extract text
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
    if not text.strip():
        raise ValueError("Could not extract text from the provided PDF.")

    # 2. Call Gemini
    # Requires GEMINI_API_KEY in .env
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert technical recruiter AI. Analyze the following resume text and extract the applicant's master profile.
    Return ONLY a valid JSON object matching the requested schema exactly. Do not include markdown blocks or any other text.
    
    Schema needed:
    {{
        "name": "Full Name",
        "email": "Email Address",
        "phone": "Phone Number",
        "skills": ["Skill 1", "Skill 2", ...],
        "experience": [
            {{
                "company": "Company Name",
                "role": "Job Title",
                "duration": "Start - End Date",
                "highlights": ["Bullet point 1", "Bullet point 2"]
            }}
        ],
        "domains": ["Domain 1 (e.g., Web Development)", "Domain 2 (e.g., Machine Learning)"]
    }}
    
    Resume Text:
    {text}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1 # Low temperature for more deterministic extraction
        ),
    )
    
    # Parse and return JSON
    text_response = response.text.strip()
    if text_response.startswith('```json'): text_response = text_response[7:]
    elif text_response.startswith('```'): text_response = text_response[3:]
    if text_response.endswith('```'): text_response = text_response[:-3]
    text_response = text_response.strip()

    try:
        profile_data = json.loads(text_response)
        return profile_data
    except Exception as e:
        raise ValueError(f"Failed to parse Gemini response into JSON: {str(e)}")


def match_job_to_profile(master_profile, job_description):
    """
    Sends the Job Description and Master Profile to Gemini Flash.
    Returns JSON containing Match Score, Summary, and Skill gaps.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert technical recruiter AI. Analyze the candidate's Master Profile against the provided Job Description.
    Return ONLY a valid JSON object matching the requested schema exactly. Do not include markdown blocks or any other text.
    
    Schema needed:
    {{
        "match_score": 85,  // an integer between 0 and 100
        "summary": "A 2-sentence summary of why this candidate is or isn't a good fit for this role based on their experience.",
        "matching_skills": ["Skill 1 from JD found in profile", "Skill 2"],
        "missing_skills": ["Skill 1 from JD NOT found in profile", "Skill 2"]
    }}
    
    Candidate Master Profile (JSON):
    {json.dumps(master_profile)}
    
    Job Description:
    {job_description}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2 # Slight variety but mostly factual
        ),
    )
    
    text_response = response.text.strip()
    if text_response.startswith('```json'): text_response = text_response[7:]
    elif text_response.startswith('```'): text_response = text_response[3:]
    if text_response.endswith('```'): text_response = text_response[:-3]
    text_response = text_response.strip()

    try:
        match_data = json.loads(text_response)
        return match_data
    except Exception as e:
        raise ValueError(f"Failed to parse Match results into JSON: {str(e)}\nRaw Response: {response.text}")

def generate_application_kit(master_profile, job_description):
    """
    Calls Gemini Pro to rewrite the Master Profile experiences prioritizing matching skills.
    Includes a strict system instruction to PREVENT hallucinations.
    Also generates a tailored Cover Letter.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert career agent and resume writer. I am giving you the candidate's Master Profile and a Job Description.
    Your task is to generate a tailored Application Kit consisting of a Tailored Resume and a Cover Letter.
    
    CRITICAL CONSTRAINT: You MUST NOT hallucinate, invent, or exaggerate any skills, experiences, or metrics that are not explicitly present in the Master Profile. You may only rephrase or reorder the existing points to better highlight alignment with the Job Description. If a required skill from the JD is missing from the Master Profile, DO NOT add it.
    
    Return ONLY a valid JSON object matching this exact schema:
    {{
        "tailored_resume": {{
            "name": "Candidate Name",
            "skills": ["Reordered skills prioritized for the JD"],
            "experience": [
                {{
                    "company": "Company",
                    "role": "Role",
                    "duration": "Duration",
                    "highlights": ["Rephrased highlight 1 tailored to JD", "Rephrased highlight 2..."]
                }}
            ]
        }},
        "cover_letter": "A professional 3-paragraph cover letter tailored to the job description, strictly based on the candidate's actual experience."
    }}
    
    Candidate Master Profile (JSON):
    {json.dumps(master_profile)}
    
    Job Description:
    {job_description}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-pro', # Use Pro for better reasoning and writing
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3 # Low temperature to enforce strict anti-hallucination
        ),
    )
    
    text_response = response.text.strip()
    if text_response.startswith('```json'): text_response = text_response[7:]
    elif text_response.startswith('```'): text_response = text_response[3:]
    if text_response.endswith('```'): text_response = text_response[:-3]
    text_response = text_response.strip()

    try:
        app_kit = json.loads(text_response)
        return app_kit
    except Exception as e:
        raise ValueError(f"Failed to parse Application Kit into JSON: {str(e)}\nRaw Response: {response.text}")
