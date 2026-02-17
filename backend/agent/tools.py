import json
import os
from datetime import date

import requests
from bs4 import BeautifulSoup

from backend.database import db
from backend.models.job import Job
from backend.agent.user_profile import read_profile, write_profile

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web using Tavily. This is a general-purpose web search, not specific to job listings. Use this for researching companies, reading articles, or finding information that isn't a job listing.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "job_search",
        "description": "Search dedicated job board APIs (Adzuna, JSearch) for real job listings. Use this when the user wants to find job openings. Returns structured job data including title, company, location, salary, and application URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Job search keywords (e.g., 'python developer', 'data scientist')",
                },
                "location": {
                    "type": "string",
                    "description": "Location filter (e.g., 'New York', 'London')",
                },
                "remote_only": {
                    "type": "boolean",
                    "description": "Filter for remote jobs only",
                },
                "salary_min": {
                    "type": "integer",
                    "description": "Minimum salary filter",
                },
                "salary_max": {
                    "type": "integer",
                    "description": "Maximum salary filter",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 10, max 20)",
                },
                "provider": {
                    "type": "string",
                    "enum": ["adzuna", "jsearch"],
                    "description": "Force a specific job search provider; defaults to whichever is configured (prefers JSearch if both available)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "scrape_url",
        "description": "Scrape a web page and return its text content. Use this to read job posting details from a URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to scrape",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "create_job",
        "description": "Add a new job application to the tracker. Use this after researching a job posting to save it.",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name"},
                "title": {"type": "string", "description": "Job title"},
                "url": {"type": "string", "description": "Job posting URL"},
                "status": {
                    "type": "string",
                    "enum": ["saved", "applied", "interviewing", "offer", "rejected"],
                    "description": "Application status (default: saved)",
                },
                "notes": {"type": "string", "description": "Notes about the job"},
                "salary_min": {"type": "integer", "description": "Minimum salary"},
                "salary_max": {"type": "integer", "description": "Maximum salary"},
                "location": {"type": "string", "description": "Job location"},
                "remote_type": {
                    "type": "string",
                    "enum": ["onsite", "hybrid", "remote"],
                    "description": "Remote work type",
                },
                "tags": {"type": "string", "description": "Comma-separated tags"},
                "contact_name": {"type": "string", "description": "Contact person name"},
                "contact_email": {"type": "string", "description": "Contact email"},
                "source": {"type": "string", "description": "Where the job was found"},
                "requirements": {"type": "string", "description": "Job requirements or qualifications, as a newline-separated list"},
                "nice_to_haves": {"type": "string", "description": "Nice-to-have qualifications, as a newline-separated list"},
                "job_fit": {"type": "integer", "description": "Job fit rating from 0-5 stars based on how well this job matches the user's profile (0 = poor fit, 5 = excellent fit). Always set this when creating a job and a user profile exists.", "minimum": 0, "maximum": 5},
            },
            "required": ["company", "title"],
        },
    },
    {
        "name": "read_user_profile",
        "description": "Read the user's profile document. This markdown document contains information about the user including their education, work experience, skills, interests, salary preferences, location preferences, and job search goals. Reference this when evaluating job fit.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "update_user_profile",
        "description": "Update the user's profile document. Use this when the user shares information about themselves that is relevant to their job search — education, work experience, skills, interests, salary preferences, location preferences, career goals, etc. Always read the current profile first, then merge new information into the existing content. Preserve all existing information unless the user explicitly corrects it.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full updated markdown content for the user profile. Must include ALL existing information plus any new details.",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "list_jobs",
        "description": "List and search jobs currently tracked in the application database. Use this to check what jobs are already saved, filter by status, or look up a specific company/title/URL before adding duplicates.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["saved", "applied", "interviewing", "offer", "rejected"],
                    "description": "Filter by application status",
                },
                "company": {
                    "type": "string",
                    "description": "Filter by company name (case-insensitive partial match)",
                },
                "title": {
                    "type": "string",
                    "description": "Filter by job title (case-insensitive partial match)",
                },
                "url": {
                    "type": "string",
                    "description": "Filter by job posting URL (exact or partial match)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of jobs to return (default 20)",
                },
            },
        },
    },
]


class AgentTools:
    def __init__(self, search_api_key="", adzuna_app_id="", adzuna_app_key="",
                 adzuna_country="us", jsearch_api_key=""):
        self.search_api_key = search_api_key
        self.adzuna_app_id = adzuna_app_id
        self.adzuna_app_key = adzuna_app_key
        self.adzuna_country = adzuna_country
        self.jsearch_api_key = jsearch_api_key

    def execute(self, tool_name, arguments):
        methods = {
            "web_search": self._web_search,
            "job_search": self._job_search,
            "scrape_url": self._scrape_url,
            "create_job": self._create_job,
            "list_jobs": self._list_jobs,
            "read_user_profile": self._read_user_profile,
            "update_user_profile": self._update_user_profile,
        }
        fn = methods.get(tool_name)
        if not fn:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return fn(**arguments)
        except Exception as e:
            return {"error": str(e)}

    def _web_search(self, query, num_results=5):
        if not self.search_api_key:
            return {"error": "SEARCH_API_KEY not configured"}
        num_results = min(num_results, 10)
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.search_api_key,
                "query": query,
                "max_results": num_results,
                "search_depth": "basic",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:500],
            })
        return {"results": results}

    # ------------------------------------------------------------------
    # Job search via Adzuna / JSearch
    # ------------------------------------------------------------------

    def _job_search(self, query, location=None, remote_only=False,
                    salary_min=None, salary_max=None, num_results=10,
                    provider=None):
        num_results = max(1, min(num_results, 20))

        has_adzuna = bool(self.adzuna_app_id and self.adzuna_app_key)
        has_jsearch = bool(self.jsearch_api_key)

        # Pick provider
        if provider == "adzuna":
            if not has_adzuna:
                return {"error": "Adzuna API keys not configured (ADZUNA_APP_ID, ADZUNA_APP_KEY)"}
        elif provider == "jsearch":
            if not has_jsearch:
                return {"error": "JSearch API key not configured (JSEARCH_API_KEY)"}
        else:
            # Auto-select: prefer JSearch, fall back to Adzuna
            if has_jsearch:
                provider = "jsearch"
            elif has_adzuna:
                provider = "adzuna"
            else:
                return {"error": "No job search API keys configured. Set JSEARCH_API_KEY or ADZUNA_APP_ID + ADZUNA_APP_KEY environment variables."}

        if provider == "adzuna":
            return self._search_adzuna(query, location, salary_min, salary_max, num_results)
        else:
            return self._search_jsearch(query, location, remote_only, num_results)

    def _search_adzuna(self, query, location, salary_min, salary_max, num_results):
        params = {
            "app_id": self.adzuna_app_id,
            "app_key": self.adzuna_app_key,
            "what": query,
            "results_per_page": num_results,
        }
        if location:
            params["where"] = location
        if salary_min is not None:
            params["salary_min"] = salary_min
        if salary_max is not None:
            params["salary_max"] = salary_max

        country = self.adzuna_country or "us"
        resp = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "company": r.get("company", {}).get("display_name", ""),
                "location": r.get("location", {}).get("display_name", ""),
                "url": r.get("redirect_url", ""),
                "description": (r.get("description", "") or "")[:500],
                "salary_min": r.get("salary_min"),
                "salary_max": r.get("salary_max"),
                "remote": None,
                "employment_type": r.get("contract_type"),
                "posted_date": (r.get("created") or "")[:10] or None,
                "source": "adzuna",
            })

        return {"results": results, "provider": "adzuna", "total": len(results)}

    def _search_jsearch(self, query, location, remote_only, num_results):
        search_query = query
        if location:
            search_query = f"{query} in {location}"

        params = {
            "query": search_query,
            "num_pages": 1,
        }
        if remote_only:
            params["remote_jobs_only"] = "true"

        resp = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            params=params,
            headers={
                "X-RapidAPI-Key": self.jsearch_api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("data", []):
            if len(results) >= num_results:
                break
            results.append({
                "title": r.get("job_title", ""),
                "company": r.get("employer_name", ""),
                "location": f"{r.get('job_city', '') or ''}, {r.get('job_state', '') or ''}".strip(", "),
                "url": r.get("job_apply_link") or r.get("job_google_link", ""),
                "description": (r.get("job_description", "") or "")[:500],
                "salary_min": r.get("job_min_salary"),
                "salary_max": r.get("job_max_salary"),
                "remote": r.get("job_is_remote", False),
                "employment_type": r.get("job_employment_type"),
                "posted_date": (r.get("job_posted_at_datetime_utc") or "")[:10] or None,
                "source": "jsearch",
            })

        return {"results": results, "provider": "jsearch", "total": len(results)}

    def _scrape_url(self, url):
        resp = requests.get(url, timeout=20, headers={"User-Agent": "JobAppHelper/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Truncate to ~4000 chars to fit in LLM context
        if len(text) > 4000:
            text = text[:4000] + "\n...(truncated)"
        return {"content": text, "url": url}

    def _create_job(self, **kwargs):
        job = Job(
            company=kwargs["company"],
            title=kwargs["title"],
            url=kwargs.get("url"),
            status=kwargs.get("status", "saved"),
            notes=kwargs.get("notes"),
            salary_min=kwargs.get("salary_min"),
            salary_max=kwargs.get("salary_max"),
            location=kwargs.get("location"),
            remote_type=kwargs.get("remote_type"),
            tags=kwargs.get("tags"),
            contact_name=kwargs.get("contact_name"),
            contact_email=kwargs.get("contact_email"),
            source=kwargs.get("source"),
            job_fit=kwargs.get("job_fit"),
            requirements=kwargs.get("requirements"),
            nice_to_haves=kwargs.get("nice_to_haves"),
        )
        db.session.add(job)
        db.session.commit()
        return job.to_dict()

    def _list_jobs(self, limit=20, status=None, company=None, title=None, url=None):
        query = Job.query
        if status:
            query = query.filter(Job.status == status)
        if company:
            query = query.filter(Job.company.ilike(f"%{company}%"))
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        if url:
            query = query.filter(Job.url.ilike(f"%{url}%"))
        jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
        return {"jobs": [j.to_dict() for j in jobs], "total": len(jobs)}

    def _read_user_profile(self):
        content = read_profile()
        return {"content": content}

    def _update_user_profile(self, content):
        write_profile(content)
        return {"status": "updated", "content": content}
