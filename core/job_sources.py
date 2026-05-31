import asyncio
import re
import time
import random
import json
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from django.db import IntegrityError, transaction
from django.conf import settings

from .models import Application, JobLead, JobSourceRun, CandidatePreference
from .resilience import circuit_breaker

# 
# SEARCH QUERIES DEFAULT FALLBACK
# 

DEFAULT_SEARCH_QUERIES = [
    "NLP Engineer",
    "ML Engineer",
    "AI Engineer",
    "Machine Learning Engineer",
    "Generative AI Engineer",
    "GenAI Engineer",
    "NLP Researcher",
    "Deep Learning Engineer",
    "Speech AI Engineer",
    "AI Research Engineer",
    "LLM Engineer",
    "Data Scientist NLP",
]


@dataclass
class ImportedJob:
    title: str = ""
    company: str = ""
    location: str = ""
    remote_type: str = ""
    salary_text: str = ""
    job_url: str = ""
    description: str = ""
    source_type: str = "manual"
    source_name: str = ""
    external_id: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


def import_job_lead(job: ImportedJob) -> tuple[JobLead, bool]:
    fingerprint = JobLead.make_fingerprint(
        job.job_url,
        job.title,
        job.company,
        job.location,
    )
    defaults = {
        "source_type": job.source_type or "manual",
        "source_name": job.source_name,
        "external_id": job.external_id,
        "job_url": job.job_url or None,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "remote_type": job.remote_type,
        "salary_text": job.salary_text,
        "description": job.description,
        "raw_payload": job.raw_payload,
    }
    try:
        with transaction.atomic():
            lead, created = JobLead.objects.get_or_create(
                fingerprint=fingerprint,
                defaults=defaults,
            )
    except IntegrityError:
        lead = JobLead.objects.get(fingerprint=fingerprint)
        created = False
    return lead, created


def import_manual_job(data: dict[str, Any]) -> tuple[JobLead, bool]:
    return import_job_lead(
        ImportedJob(
            title=str(data.get("title", "")).strip(),
            company=str(data.get("company", "")).strip(),
            location=str(data.get("location", "")).strip(),
            remote_type=str(data.get("remote_type", "")).strip(),
            salary_text=str(data.get("salary_text", "")).strip(),
            job_url=str(data.get("job_url", "")).strip(),
            description=str(data.get("job_description") or data.get("description") or "").strip(),
            source_type=str(data.get("source_type") or "manual").strip(),
            source_name=str(data.get("source_name") or "Manual Import").strip(),
            external_id=str(data.get("external_id", "")).strip(),
            raw_payload={key: value for key, value in data.items() if key != "csrfmiddlewaretoken"},
        )
    )


def create_application_from_lead(lead: JobLead, profile_snapshot=None) -> Application:
    application = Application.objects.create(
        job_url=lead.job_url,
        job_description=lead.description,
        profile_snapshot=profile_snapshot,
        source_lead=lead,
    )
    return application


class JobSourceConnector:
    source_type = "base"
    source_name = "Base Connector"

    def fetch(self) -> list[ImportedJob]:
        raise NotImplementedError

    def run(self) -> JobSourceRun:
        source_run = JobSourceRun.objects.create(
            source_type=self.source_type,
            source_name=self.source_name,
        )
        try:
            jobs = self.fetch()
            imported = 0
            for job in jobs:
                _, created = import_job_lead(job)
                imported += int(created)
            source_run.finish(discovered_count=len(jobs), imported_count=imported)
        except Exception as exc:
            source_run.fail(exc)
        return source_run


# 
# TIER 1: JOBSPY (LinkedIn, Indeed, Glassdoor, Google Jobs)
# 

def search_jobspy(query: str, hours_old: int = 24, sites: list = None) -> list[dict]:
    """Search via jobspy  LinkedIn, Indeed, Glassdoor, Google Jobs."""
    if not circuit_breaker.is_available("jobspy"):
        return []

    jobs = []
    if sites is None:
        sites = ["linkedin", "indeed", "glassdoor", "google"]

    try:
        from jobspy import scrape_jobs
        results = scrape_jobs(
            site_name=sites,
            search_term=query,
            location="India",
            results_wanted=20,
            hours_old=hours_old,
            country_indeed="India",
        )
        for _, row in results.iterrows():
            if row.get("job_url") and row.get("title"):
                jobs.append({
                    "title": str(row.get("title", "")),
                    "company": str(row.get("company", "Unknown")),
                    "location": str(row.get("location", "India")),
                    "description": str(row.get("description", ""))[:2000],
                    "apply_url": str(row.get("job_url", "")),
                    "source": str(row.get("site", "jobspy")),
                    "posted": str(row.get("date_posted", "Recent")),
                })
        circuit_breaker.record_success("jobspy")
    except Exception as e:
        circuit_breaker.record_failure("jobspy", str(e))
        print(f"   jobspy error for '{query}': {e}")

    return jobs


# 
# TIER 1: NAUKRI (Scrapling-capable)
# 

def search_naukri(query: str) -> list[dict]:
    """Search Naukri.com using Scrapling Fetcher."""
    if not circuit_breaker.is_available("naukri"):
        return []

    jobs = []
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()

        query_slug = query.replace(" ", "-").lower()
        url = f"https://www.naukri.com/{query_slug}-jobs-in-india"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
        }
        
        response = fetcher.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return jobs

        # Scrapling parses into response elements automatically
        cards = response.css("article.job-tuple, article.jobTuple")[:15]
        for card in cards:
            try:
                title_el = card.css("a.title, a.jobTitle, h2.title")
                comp_el = card.css("a.subTitle, a.company, .companyInfo")
                loc_el = card.css(".location, .loc")
                link_el = card.css("a")

                title = title_el[0].text.strip() if title_el else ""
                company = comp_el[0].text.strip() if comp_el else "Unknown"
                location = loc_el[0].text.strip() if loc_el else "India"
                link = link_el[0].attrib.get("href") if link_el else ""

                if title and link:
                    if not link.startswith("http"):
                        link = "https://www.naukri.com" + link
                    jobs.append({
                        "title": title, "company": company, "location": location,
                        "description": f"{title} at {company}",
                        "apply_url": link, "source": "Naukri", "posted": "Recent",
                    })
            except Exception:
                continue

        circuit_breaker.record_success("naukri")
    except Exception as e:
        circuit_breaker.record_failure("naukri", str(e))
        print(f"   Naukri error: {e}")

    return jobs


# 
# TIER 1: INTERNSHALA (Scrapling-capable)
# 

def search_internshala(query: str) -> list[dict]:
    """Search Internshala using Scrapling Fetcher."""
    if not circuit_breaker.is_available("internshala"):
        return []

    jobs = []
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()

        query_slug = query.replace(" ", "-").lower()
        url = f"https://internshala.com/jobs/{query_slug}-jobs"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = fetcher.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return jobs

        cards = response.css("div.individual_internship, div.job-card")[:15]
        for card in cards:
            try:
                title_el = card.css(".job-title, .profile")
                comp_el = card.css(".company-name")
                link_el = card.css("a[href*='/job/detail/']")

                title = title_el[0].text.strip() if title_el else ""
                company = comp_el[0].text.strip() if comp_el else "Unknown"
                link = link_el[0].attrib.get("href") if link_el else ""

                if title and link:
                    if not link.startswith("http"):
                        link = "https://internshala.com" + link
                    jobs.append({
                        "title": title, "company": company, "location": "India",
                        "description": f"{title} at {company}",
                        "apply_url": link, "source": "Internshala", "posted": "Recent",
                    })
            except Exception:
                continue

        circuit_breaker.record_success("internshala")
    except Exception as e:
        circuit_breaker.record_failure("internshala", str(e))
        print(f"   Internshala error: {e}")

    return jobs


# 
# TIER 1: FOUNDIT
# 

def search_foundit(query: str) -> list[dict]:
    """Search Foundit.in (Monster India)."""
    if not circuit_breaker.is_available("foundit"):
        return []

    jobs = []
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()

        url = f"https://www.foundit.in/search/{query.replace(' ', '-').lower()}-jobs-in-india"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = fetcher.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return jobs

        cards = response.css("div.card, div.job-item")[:15]
        for card in cards:
            try:
                title_el = card.css(".title, .position, h2, h3")
                comp_el = card.css(".company")
                link_el = card.css("a[href*='/job/']")

                title = title_el[0].text.strip() if title_el else ""
                company = comp_el[0].text.strip() if comp_el else "Unknown"
                link = link_el[0].attrib.get("href") if link_el else ""

                if title and link:
                    if not link.startswith("http"):
                        link = "https://www.foundit.in" + link
                    jobs.append({
                        "title": title, "company": company, "location": "India",
                        "description": f"{title} at {company}",
                        "apply_url": link, "source": "Foundit", "posted": "Recent",
                    })
            except Exception:
                continue

        circuit_breaker.record_success("foundit")
    except Exception as e:
        circuit_breaker.record_failure("foundit", str(e))
        print(f"   Foundit error: {e}")

    return jobs


# 
# TIER 1: WELLFOUND
# 

def search_wellfound(query: str) -> list[dict]:
    """Search Wellfound (AngelList) startup jobs."""
    if not circuit_breaker.is_available("wellfound"):
        return []

    jobs = []
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()

        url = f"https://wellfound.com/jobs?q={query.replace(' ', '+')}&l=India"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = fetcher.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200 and "job" in response.text.lower():
            links = re.findall(r'href="(/jobs/[^"]+)"', response.text)
            for link in links[:15]:
                full_url = f"https://wellfound.com{link}"
                title = link.split("/")[-1].replace("-", " ").title()
                jobs.append({
                    "title": title, "company": "Startup (Wellfound)",
                    "location": "India / Remote",
                    "description": f"{query} role at startup",
                    "apply_url": full_url, "source": "Wellfound", "posted": "Recent",
                })
        circuit_breaker.record_success("wellfound")
    except Exception as e:
        circuit_breaker.record_failure("wellfound", str(e))
        print(f"   Wellfound error: {e}")

    return jobs


# 
# TIER 1: REMOTEOK
# 

async def search_remoteok(client: httpx.AsyncClient) -> list[dict]:
    """Search RemoteOK.com  free JSON API for remote jobs."""
    if not circuit_breaker.is_available("remoteok"):
        return []

    jobs = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = await client.get("https://remoteok.com/api", headers=headers, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            for item in data[1:]:
                title = item.get("position", "")
                tags = " ".join(item.get("tags", []))
                combined = f"{title} {tags} {item.get('description', '')}".lower()
                if any(kw in combined for kw in [
                    "machine learning", "ml ", "ai ", "nlp", "deep learning",
                    "data scien", "tensorflow", "pytorch", "llm", "genai",
                    "generative", "transformer", "neural", "computer vision"
                ]):
                    jobs.append({
                        "title": title,
                        "company": item.get("company", "Unknown"),
                        "location": "Remote",
                        "description": item.get("description", "")[:2000],
                        "apply_url": item.get("url", f"https://remoteok.com/remote-jobs/{item.get('slug', '')}"),
                        "source": "RemoteOK",
                        "posted": item.get("date", "Recent"),
                    })
        circuit_breaker.record_success("remoteok")
    except Exception as e:
        circuit_breaker.record_failure("remoteok", str(e))
        print(f"   RemoteOK error: {e}")

    return jobs


# 
# TIER 1: HIRIST (Scrapling-capable)
# 

def search_hirist(query: str) -> list[dict]:
    """Search Hirist.tech using Scrapling Fetcher."""
    if not circuit_breaker.is_available("hirist"):
        return []

    jobs = []
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()

        query_slug = query.replace(" ", "-").lower()
        url = f"https://www.hirist.tech/{query_slug}-jobs"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        response = fetcher.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return jobs

        cards = response.css(".job-card, .job-listing, .search-result")[:15]
        for card in cards:
            try:
                title_el = card.css(".title, .position, .job-name, a")
                comp_el = card.css(".company, .employer")
                link_el = card.css("a[href*='/job/']")

                title = title_el[0].text.strip() if title_el else ""
                company = comp_el[0].text.strip() if comp_el else "Unknown"
                link = link_el[0].attrib.get("href") if link_el else ""

                if title and link:
                    if not link.startswith("http"):
                        link = "https://www.hirist.tech" + link
                    jobs.append({
                        "title": title, "company": company, "location": "India",
                        "description": f"{title} at {company}",
                        "apply_url": link, "source": "Hirist", "posted": "Recent",
                    })
            except Exception:
                continue

        circuit_breaker.record_success("hirist")
    except Exception as e:
        circuit_breaker.record_failure("hirist", str(e))
        print(f"   Hirist error: {e}")

    return jobs


# 
# TIER 1: Y COMBINATOR
# 

async def search_yc_jobs(client: httpx.AsyncClient) -> list[dict]:
    """Search Y Combinator's Work at a Startup board."""
    if not circuit_breaker.is_available("ycombinator"):
        return []

    jobs = []
    try:
        url = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"
        headers = {
            "x-algolia-agent": "Algolia for JavaScript (4.14.2); Browser",
            "x-algolia-api-key": "NDYzMmI5MzQ2OGNlNDkzODlkNDQ1NmM5MTMzMWVjNmMxNjM4MTUyZGZiZGExMjkzMzc3NTk1NmI5NWMxNWI3NnRhZ0ZpbHRlcnM9JTVCJTIyaXNIaXJpbmclMjIlNUQmYW5hbHl0aWNzVGFncz0lNUIlMjJ3YWFzX2pvYnNfcXVlcnklMjIlNUQ=",
            "x-algolia-application-id": "45BWZJ1SGC",
        }
        payload = {
            "requests": [{
                "indexName": "WaaSJobs_production",
                "params": f"query=ML+AI+NLP&hitsPerPage=30&filters=isHiring:true"
            }]
        }
        r = await client.post(url, json=payload, headers=headers, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            hits = data.get("results", [{}])[0].get("hits", [])
            for hit in hits:
                title = hit.get("title", "")
                if any(kw in title.lower() for kw in [
                    "ml", "ai", "machine learning", "nlp", "data scien",
                    "deep learning", "generative", "llm", "research"
                ]):
                    company = hit.get("organizationName", "YC Startup")
                    slug = hit.get("slug", "")
                    jobs.append({
                        "title": title,
                        "company": f"{company} (YC)",
                        "location": hit.get("location", "Remote"),
                        "description": hit.get("description", "")[:2000],
                        "apply_url": f"https://www.workatastartup.com/jobs/{slug}" if slug else "",
                        "source": "Y Combinator",
                        "posted": "Recent",
                    })
        circuit_breaker.record_success("ycombinator")
    except Exception as e:
        circuit_breaker.record_failure("ycombinator", str(e))
        print(f"   Y Combinator error: {e}")

    return jobs


# 
# TIER 2: GREENHOUSE BOARDS
# 

GREENHOUSE_COMPANIES = [
    "openai", "anthropic", "huggingface", "databricks",
    "cloudflare", "stripe", "figma", "notion",
    "cockroachlabs", "hashicorp", "elastic", "confluent",
    "airtable", "asana", "brex", "plaid",
]


async def search_greenhouse_boards(client: httpx.AsyncClient) -> list[dict]:
    """Fetch jobs from Greenhouse boards."""
    if not circuit_breaker.is_available("greenhouse"):
        return []

    jobs = []
    async def fetch_company(company_slug: str):
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
            r = await client.get(url, timeout=10.0)
            if r.status_code != 200:
                return []

            data = r.json()
            company_jobs = []
            for job in data.get("jobs", []):
                title = job.get("title", "")
                combined = f"{title} {json.dumps(job.get('metadata', []))}".lower()
                if any(kw in combined for kw in [
                    "machine learning", "ml ", "ai ", "nlp", "data scien",
                    "deep learning", "generative", "llm", "research engineer",
                    "applied scientist", "inference", "model"
                ]):
                    loc = ""
                    if job.get("location", {}).get("name"):
                        loc = job["location"]["name"]

                    company_jobs.append({
                        "title": title,
                        "company": company_slug.replace("-", " ").title(),
                        "location": loc or "Unknown",
                        "description": (job.get("content", "") or "")[:2000],
                        "apply_url": job.get("absolute_url", ""),
                        "source": "Greenhouse",
                        "posted": job.get("updated_at", "Recent"),
                    })
            return company_jobs
        except Exception:
            return []

    results = await asyncio.gather(
        *[fetch_company(slug) for slug in GREENHOUSE_COMPANIES],
        return_exceptions=True
    )

    for result in results:
        if isinstance(result, list):
            jobs.extend(result)

    if jobs:
        circuit_breaker.record_success("greenhouse")
    return jobs


# 
# TIER 2: LEVER BOARDS
# 

LEVER_COMPANIES = [
    "netflix", "coinbase", "anduril", "scale",
    "weights-and-biases", "cohere", "together-ai",
    "midjourney", "perplexity-ai",
]


async def search_lever_boards(client: httpx.AsyncClient) -> list[dict]:
    """Fetch jobs from Lever boards."""
    if not circuit_breaker.is_available("lever"):
        return []

    jobs = []
    async def fetch_company(company_slug: str):
        try:
            url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
            r = await client.get(url, timeout=10.0)
            if r.status_code != 200:
                return []

            data = r.json()
            company_jobs = []
            for posting in data:
                title = posting.get("text", "")
                combined = f"{title} {posting.get('description', '')} {json.dumps(posting.get('categories', {}))}".lower()
                if any(kw in combined for kw in [
                    "machine learning", "ml ", "ai ", "nlp", "data scien",
                    "deep learning", "generative", "llm", "research",
                    "applied scientist", "inference"
                ]):
                    categories = posting.get("categories", {})
                    company_jobs.append({
                        "title": title,
                        "company": company_slug.replace("-", " ").title(),
                        "location": categories.get("location", "Unknown"),
                        "description": (posting.get("descriptionPlain", "") or "")[:2000],
                        "apply_url": posting.get("hostedUrl", posting.get("applyUrl", "")),
                        "source": "Lever",
                        "posted": "Recent",
                    })
            return company_jobs
        except Exception:
            return []

    results = await asyncio.gather(
        *[fetch_company(slug) for slug in LEVER_COMPANIES],
        return_exceptions=True
    )

    for result in results:
        if isinstance(result, list):
            jobs.extend(result)

    if jobs:
        circuit_breaker.record_success("lever")
    return jobs


# 
# TIER 3: COMPANY CAREER PAGES
# 

COMPANY_CAREER_PAGES = [
    {"name": "Sarvam AI",         "url": "https://www.sarvam.ai/careers"},
    {"name": "Krutrim",           "url": "https://krutrim.com/careers"},
    {"name": "Haptik",            "url": "https://haptik.ai/careers"},
    {"name": "Yellow.ai",         "url": "https://yellow.ai/company/careers"},
    {"name": "Murf AI",           "url": "https://murf.ai/careers"},
    {"name": "Uniphore",          "url": "https://www.uniphore.com/company/careers"},
    {"name": "Mad Street Den",    "url": "https://www.madstreetden.com/careers"},
    {"name": "Observe.AI",        "url": "https://www.observe.ai/company/careers"},
    {"name": "Sprinklr",          "url": "https://www.sprinklr.com/careers"},
    {"name": "Fractal Analytics",  "url": "https://fractal.ai/careers"},
    {"name": "Sigmoid",           "url": "https://www.sigmoid.com/careers"},
    {"name": "Tiger Analytics",   "url": "https://www.tigeranalytics.com/careers"},
    {"name": "Qure.ai",           "url": "https://qure.ai/careers"},
    {"name": "SigTuple",          "url": "https://sigtuple.com/careers"},
    {"name": "Pixis AI",          "url": "https://pixis.ai/careers"},
    {"name": "Arya.ai",           "url": "https://arya.ai/careers"},
    {"name": "CoRover.ai",        "url": "https://corover.ai/careers"},
    {"name": "Locus",             "url": "https://locus.sh/careers"},
    {"name": "Vernacular.ai",     "url": "https://vernacular.ai/careers"},
    {"name": "Neysa AI",          "url": "https://neysa.ai/careers"},
    {"name": "Flipkart",          "url": "https://www.flipkartcareers.com/#!/listing"},
    {"name": "Swiggy",            "url": "https://careers.swiggy.com/"},
    {"name": "Meesho",            "url": "https://www.meesho.io/careers"},
    {"name": "PhonePe",           "url": "https://www.phonepe.com/careers/"},
    {"name": "Razorpay",          "url": "https://razorpay.com/jobs/"},
    {"name": "CRED",              "url": "https://careers.cred.club/"},
    {"name": "Zomato",            "url": "https://www.zomato.com/careers"},
    {"name": "ShareChat",         "url": "https://sharechat.com/careers"},
    {"name": "Dream11",           "url": "https://www.dreamsports.group/careers"},
    {"name": "Hugging Face",      "url": "https://huggingface.co/jobs"},
    {"name": "Weights & Biases",  "url": "https://wandb.ai/careers"},
    {"name": "Cohere",            "url": "https://cohere.com/careers"},
    {"name": "Together AI",       "url": "https://www.together.ai/careers"},
    {"name": "Stability AI",      "url": "https://stability.ai/careers"},
    {"name": "Mistral AI",        "url": "https://mistral.ai/careers"},
    {"name": "Google AI",         "url": "https://careers.google.com/jobs/results/?q=ML+Engineer&location=India"},
    {"name": "Microsoft",         "url": "https://careers.microsoft.com/us/en/search-results?keywords=AI%20ML&location=India"},
    {"name": "Amazon AI",         "url": "https://www.amazon.jobs/en/search?category=machine-learning-science&country=IND"},
    {"name": "NVIDIA",            "url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q=AI+ML"},
    {"name": "IBM Research",      "url": "https://www.ibm.com/careers/search?field_keyword_08[0]=Artificial+Intelligence&country=IN"},
]


async def search_career_pages(client: httpx.AsyncClient) -> list[dict]:
    """Scrape company career pages  best effort extraction."""
    if not circuit_breaker.is_available("career_pages"):
        return []

    jobs = []
    async def check_page(company: dict):
        try:
            r = await client.get(
                company["url"],
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=12.0,
                follow_redirects=True,
            )
            if r.status_code != 200:
                return []

            text = r.text.lower()
            page_jobs = []

            ai_keywords = [
                "machine learning", "ml engineer", "ai engineer", "nlp",
                "data scientist", "deep learning", "generative ai", "genai",
                "llm", "research engineer", "speech", "computer vision",
                "applied scientist",
            ]

            has_ai_roles = any(kw in text for kw in ai_keywords)
            if has_ai_roles:
                page_jobs.append({
                    "title": f"AI/ML Roles at {company['name']}",
                    "company": company['name'],
                    "location": "India / Remote",
                    "description": f"AI/ML positions detected on {company['name']} career page. Visit directly.",
                    "apply_url": company["url"],
                    "source": "Career Page",
                    "posted": "Active",
                })
            return page_jobs
        except Exception:
            return []

    results = await asyncio.gather(
        *[check_page(c) for c in COMPANY_CAREER_PAGES],
        return_exceptions=True
    )

    for result in results:
        if isinstance(result, list):
            jobs.extend(result)

    circuit_breaker.record_success("career_pages")
    return jobs


# 
# ENHANCED DEDUPLICATION
# 

def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    """Normalize URLs and fuzzy match on normalized title + company."""
    seen_urls = set()
    seen_keys = set()
    unique = []

    for job in jobs:
        url = job.get("apply_url", "").strip()
        if not url:
            continue

        clean_url = re.sub(r'[?&](utm_\w+|ref|source|tracking|fbclid|gclid)=[^&]*', '', url)
        clean_url = clean_url.rstrip("?&")

        if clean_url in seen_urls:
            continue

        title_key = re.sub(r'[^a-z0-9]', '', job.get("title", "").lower())[:40]
        comp_key = re.sub(r'[^a-z0-9]', '', job.get("company", "").lower())[:30]
        fuzzy_key = f"{title_key}_{comp_key}"

        if fuzzy_key in seen_keys:
            continue

        seen_urls.add(clean_url)
        seen_keys.add(fuzzy_key)
        unique.append(job)

    return unique


# 
# MASTER PARALLEL SCRAPER ORCHESTRATOR
# 

async def collect_all_jobs(hours_old: int = 24) -> tuple[list[dict], dict]:
    """Collect jobs from ALL sources in parallel, using active CandidatePreferences if available."""
    pref = CandidatePreference.objects.filter(profile__is_active=True).first()
    search_queries = DEFAULT_SEARCH_QUERIES
    if pref and pref.generated_queries:
        search_queries = pref.generated_queries

    print(f"\n Collecting jobs using {len(search_queries)} queries...")
    all_jobs = []
    source_stats = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        loop = asyncio.get_event_loop()
        sync_tasks = []

        for query in search_queries:
            sync_tasks.append(("jobspy", query, loop.run_in_executor(None, search_jobspy, query, hours_old)))
            sync_tasks.append(("naukri", query, loop.run_in_executor(None, search_naukri, query)))
            sync_tasks.append(("internshala", query, loop.run_in_executor(None, search_internshala, query)))
            sync_tasks.append(("foundit", query, loop.run_in_executor(None, search_foundit, query)))
            sync_tasks.append(("hirist", query, loop.run_in_executor(None, search_hirist, query)))

            if query in ["ML Engineer", "AI Engineer", "NLP Engineer", "GenAI Engineer", "LLM Engineer", "Machine Learning Engineer"]:
                sync_tasks.append(("wellfound", query, loop.run_in_executor(None, search_wellfound, query)))

        async_tasks = [
            ("remoteok", "all", search_remoteok(client)),
            ("ycombinator", "all", search_yc_jobs(client)),
            ("greenhouse", "all", search_greenhouse_boards(client)),
            ("lever", "all", search_lever_boards(client)),
            ("career_pages", "all", search_career_pages(client)),
        ]

        # Process sync tasks
        for source, query, task in sync_tasks:
            try:
                result = await task
                if result:
                    all_jobs.extend(result)
                    source_stats[source] = source_stats.get(source, 0) + len(result)
            except Exception as e:
                print(f"     - {source}/{query}: {e}")
            await asyncio.sleep(random.uniform(0.1, 0.4))

        # Process async tasks
        for source, query, task in async_tasks:
            try:
                result = await task
                if result:
                    all_jobs.extend(result)
                    source_stats[source] = source_stats.get(source, 0) + len(result)
            except Exception as e:
                print(f"     - {source}: {e}")

    all_jobs = deduplicate_jobs(all_jobs)
    source_stats["_total_raw"] = sum(source_stats.values())
    source_stats["_total_deduped"] = len(all_jobs)

    return all_jobs, source_stats


# 
# UNIFIED MEGA CONNECTOR
# 

class MegaJobSourceConnector(JobSourceConnector):
    source_type = "mega"
    source_name = "Mega Autonomous Scraper"

    def fetch(self) -> list[ImportedJob]:
        # Run event loop synchronously inside the connector thread
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        jobs_dicts, stats = loop.run_until_complete(collect_all_jobs(hours_old=24))
        
        imported_jobs = []
        for j in jobs_dicts:
            imported_jobs.append(
                ImportedJob(
                    title=j["title"],
                    company=j["company"],
                    location=j["location"],
                    job_url=j["apply_url"],
                    description=j["description"],
                    source_type="scraped",
                    source_name=j["source"],
                    raw_payload=j,
                )
            )
        return imported_jobs
