import os
import re
import asyncio
from pathlib import Path
import markdown2
from playwright.async_api import async_playwright

from django.conf import settings
from .llm import LLMRouter, LLMRequest, LLMTask
from .schemas import MasterProfile

def format_profile_as_markdown(profile: MasterProfile) -> str:
    """Compile the structured MasterProfile claims into a clean Markdown resume."""
    md = []
    
    # 1. Header (Identity & Contact)
    md.append(f"# {profile.name}")
    contact_parts = []
    if profile.email:
        contact_parts.append(profile.email)
    if profile.phone:
        contact_parts.append(profile.phone)
    if profile.location:
        contact_parts.append(profile.location)
    md.append(" | ".join(contact_parts))
    
    links = []
    if profile.linkedin_url:
        links.append(f"[LinkedIn]({profile.linkedin_url})")
    if profile.github_url:
        links.append(f"[GitHub]({profile.github_url})")
    if links:
        md.append(" | ".join(links))
    
    md.append("\n## TECHNICAL SKILLS")
    if profile.skills:
        md.append(", ".join(profile.skills))
    else:
        md.append("AI/ML, NLP, Python, Deep Learning")
        
    md.append("\n## PROFESSIONAL EXPERIENCE")
    for exp in profile.experience:
        md.append(f"### {exp.role}  {exp.company} ({exp.duration})")
        for hl in exp.highlights:
            md.append(f"- {hl}")
            
    if profile.domains:
        md.append("\n## CORE DOMAINS")
        md.append(", ".join(profile.domains))

    if profile.evidence_notes:
        md.append("\n## ADDITIONAL EXPERIENCE & HIGHLIGHTS")
        for note in profile.evidence_notes:
            md.append(f"- {note}")

    return "\n".join(md)


async def generate_tailored_resume(job: dict, master_profile: MasterProfile) -> str:
    """
    Assembles a Master Resume from verified claims, tailors it for a target job
    using LLMRouter, and renders a professional PDF using Playwright.
    
    Returns the relative path to the generated PDF.
    """
    # 1. Format the Master Resume as Markdown
    master_resume_md = format_profile_as_markdown(master_profile)

    # 2. Build the tailoring prompt
    prompt = f"""You are an expert technical recruiter and resume writer. 
I have a master resume and a target job description. 
Your task is to tailor the master resume for this specific job.

TARGET JOB:
Title: {job.get('title', 'AI/ML Engineer')}
Company: {job.get('company', 'Target Company')}
Description: {job.get('description', '')[:2000]}

MASTER RESUME:
{master_resume_md}

INSTRUCTIONS:
1. Do NOT hallucinate or invent any experience that is not in the Master Resume.
2. Under "PROFESSIONAL SUMMARY", write a concise 2-3 sentence summary that highlights keywords from the target job description.
3. Under "TECHNICAL SKILLS", reorder the skills to put the technologies mentioned in the target job description first.
4. Under "PROFESSIONAL EXPERIENCE", you may slightly reword bullet points to highlight the aspects most relevant to the target job, but do not change the facts, metrics, or technologies used.
5. Keep the CONTACT and EDUCATION sections exactly as they are.
6. Output ONLY the raw markdown of the final tailored resume. Do not wrap it in ```markdown blocks if possible, just pure markdown text.
"""

    print(f"  [Resume] Requesting tailoring via LLM Router for {job.get('company', 'job')}...")
    
    # 3. Call LLMRouter (takes advantage of fallback and configurations)
    try:
        router = LLMRouter()
        result = router.generate(
            LLMRequest(
                task=LLMTask.CRITIC_VALIDATE,
                prompt=prompt,
                temperature=0.2,
                response_mime_type="text/plain"
            )
        )
        tailored_markdown = result.text.strip()
    except Exception as e:
        print(f"   LLM tailoring failed: {e}. Falling back to default profile...")
        tailored_markdown = master_resume_md

    # Clean up formatting wrappers
    if tailored_markdown.startswith("```markdown"):
        tailored_markdown = tailored_markdown[11:]
    elif tailored_markdown.startswith("```"):
        tailored_markdown = tailored_markdown[3:]
    if tailored_markdown.endswith("```"):
        tailored_markdown = tailored_markdown[:-3]
    tailored_markdown = tailored_markdown.strip()

    # 4. Convert Markdown to HTML
    html_content = markdown2.markdown(tailored_markdown)
    
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 10.5pt; line-height: 1.35; color: #333; margin: 0; padding: 15px; }}
            h1 {{ font-size: 16pt; margin-top: 0; margin-bottom: 3px; color: #111; border-bottom: 2px solid #333; padding-bottom: 3px; text-transform: uppercase; }}
            h2 {{ font-size: 12pt; margin-top: 12px; margin-bottom: 4px; color: #222; border-bottom: 1px solid #ccc; padding-bottom: 2px; text-transform: uppercase; }}
            h3 {{ font-size: 10.5pt; margin-top: 6px; margin-bottom: 2px; color: #333; font-weight: bold; }}
            p {{ margin-top: 3px; margin-bottom: 3px; }}
            ul {{ margin-top: 3px; margin-bottom: 6px; padding-left: 15px; }}
            li {{ margin-bottom: 2px; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # 5. Compile to A4 PDF using Playwright
    media_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
    tailored_dir = media_dir / "tailored_resumes"
    tailored_dir.mkdir(parents=True, exist_ok=True)
    
    safe_company = "".join(c for c in job.get('company', 'company') if c.isalnum() or c in ("_", "-"))[:30]
    safe_title = "".join(c for c in job.get('title', 'title') if c.isalnum() or c in ("_", "-"))[:30]
    pdf_filename = f"Resume_{safe_company}_{safe_title}.pdf"
    pdf_path = tailored_dir / pdf_filename

    print(f"  [Resume] Rendering A4 PDF...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(styled_html)
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0.75in", "right": "0.75in", "bottom": "0.75in", "left": "0.75in"}
        )
        await browser.close()
        
    print(f"  [Resume] Saved tailored PDF to {pdf_path}")
    
    # Return the relative media path
    return os.path.join("tailored_resumes", pdf_filename)


async def compile_tailored_resume_to_pdf(app_record, profile) -> str:
    """
    Compiles the tailored_resume JSON inside an Application record
    together with the CandidateProfile contact info and spacing/theme preferences
    into a clean A4 PDF using Playwright.
    """
    tailored = app_record.tailored_resume or {}
    name = tailored.get("name") or profile.full_name or "Candidate Name"
    skills = tailored.get("skills") or []
    experience = tailored.get("experience") or []

    # Filter out skills and experience parts from markdown conversion to avoid double-processing,
    # or format them as markdown directly.
    # Note: we exclude headers and contact info because we render them manually.
    md = []
    
    # Skills section
    md.append("## TECHNICAL SKILLS")
    md.append(", ".join(skills))

    # Experience section
    md.append("\n## PROFESSIONAL EXPERIENCE")
    for exp in experience:
        comp = exp.get("company", "")
        role = exp.get("role", "")
        dur = exp.get("duration", "")
        hls = exp.get("highlights", [])
        md.append(f"### {role} at {comp} ({dur})")
        for hl in hls:
            md.append(f"- {hl}")

    from asgiref.sync import sync_to_async
    master_profile = await sync_to_async(profile.to_master_profile)()
    if master_profile.domains:
        md.append("\n## CORE DOMAINS")
        md.append(", ".join(master_profile.domains))

    tailored_markdown = "\n".join(md)

    # Convert Markdown to HTML
    html_content = markdown2.markdown(tailored_markdown)

    # Get styling preferences
    pref = getattr(profile, "preferences", None)
    theme = getattr(pref, "resume_theme", "modern_sans")
    font_size = getattr(pref, "resume_font_size", 10.5)
    line_height = getattr(pref, "resume_line_height", 1.35)
    margin_top = getattr(pref, "resume_margin_top", 0.75)
    margin_bottom = getattr(pref, "resume_margin_bottom", 0.75)
    margin_left = getattr(pref, "resume_margin_left", 0.75)
    margin_right = getattr(pref, "resume_margin_right", 0.75)

    # Set up theme CSS variables/rules
    font_family = "sans-serif"
    header_border = "2px solid #333"
    section_border = "1px solid #ccc"
    text_color = "#333"
    title_color = "#111"
    section_title_color = "#222"
    text_transform = "uppercase"

    if theme == "classic_serif":
        font_family = "Georgia, 'Times New Roman', Times, serif"
        header_border = "1px solid #111"
        section_border = "none"
        text_color = "#1a1a1a"
        title_color = "#000"
        section_title_color = "#000"
    elif theme == "minimalist":
        font_family = "'Courier New', Courier, monospace"
        header_border = "none"
        section_border = "none"
        text_color = "#222"
        title_color = "#000"
        section_title_color = "#444"
        text_transform = "none"
    else: # modern_sans
        font_family = "'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
        header_border = "2px solid #4f46e5"
        section_border = "1px solid #e2e8f0"
        text_color = "#1e293b"
        title_color = "#0f172a"
        section_title_color = "#334155"

    contact = []
    if profile.email: contact.append(profile.email)
    if profile.phone: contact.append(profile.phone)
    if profile.location: contact.append(profile.location)
    
    links = []
    if profile.linkedin_url: links.append(f"[LinkedIn]({profile.linkedin_url})")
    if profile.github_url: links.append(f"[GitHub]({profile.github_url})")
    
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: {font_family};
                font-size: {font_size}pt;
                line-height: {line_height};
                color: {text_color};
                margin: 0;
                padding: 10px;
            }}
            h1 {{
                font-size: 15pt;
                margin-top: 0;
                margin-bottom: 2px;
                color: {title_color};
                border-bottom: {header_border};
                padding-bottom: 2px;
                text-transform: uppercase;
                text-align: center;
            }}
            .contact-header {{
                text-align: center;
                font-size: 9pt;
                margin-bottom: 10px;
                color: #64748b;
            }}
            h2 {{
                font-size: 11pt;
                margin-top: 10px;
                margin-bottom: 3px;
                color: {section_title_color};
                border-bottom: {section_border};
                padding-bottom: 1px;
                text-transform: {text_transform};
                font-weight: 600;
            }}
            h3 {{
                font-size: 10pt;
                margin-top: 4px;
                margin-bottom: 1px;
                color: {text_color};
                font-weight: bold;
            }}
            p {{
                margin-top: 2px;
                margin-bottom: 2px;
            }}
            ul {{
                margin-top: 2px;
                margin-bottom: 4px;
                padding-left: 14px;
            }}
            li {{
                margin-bottom: 1px;
            }}
        </style>
    </head>
    <body>
        <h1>{name}</h1>
        <div class="contact-header">
            {" | ".join(contact)}
            {("<br>" + " | ".join(links)) if links else ""}
        </div>
        {html_content}
    </body>
    </html>
    """

    # Compile to A4 PDF using Playwright
    media_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
    tailored_dir = media_dir / "tailored_resumes"
    tailored_dir.mkdir(parents=True, exist_ok=True)

    pdf_filename = f"Resume_{app_record.id}.pdf"
    pdf_path = tailored_dir / pdf_filename

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(styled_html)
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={
                "top": f"{margin_top}in",
                "right": f"{margin_right}in",
                "bottom": f"{margin_bottom}in",
                "left": f"{margin_left}in"
            }
        )
        await browser.close()

    return os.path.join("tailored_resumes", pdf_filename)
