import json
from datetime import date

import requests
from bs4 import BeautifulSoup

from backend.database import db
from backend.models.job import Job

TOOL_DEFINITIONS = [
    {
        "name": "search_jobs",
        "description": "Search the web for job postings using Tavily search API. Use this to find job listings matching specific criteria.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding job postings",
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
            },
            "required": ["company", "title"],
        },
    },
    {
        "name": "list_jobs",
        "description": "List jobs currently tracked in the application database.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of jobs to return (default 20)",
                },
            },
        },
    },
]


class AgentTools:
    def __init__(self, search_api_key=""):
        self.search_api_key = search_api_key

    def execute(self, tool_name, arguments):
        methods = {
            "search_jobs": self._search_jobs,
            "scrape_url": self._scrape_url,
            "create_job": self._create_job,
            "list_jobs": self._list_jobs,
        }
        fn = methods.get(tool_name)
        if not fn:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return fn(**arguments)
        except Exception as e:
            return {"error": str(e)}

    def _search_jobs(self, query, num_results=5):
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
        )
        db.session.add(job)
        db.session.commit()
        return job.to_dict()

    def _list_jobs(self, limit=20):
        jobs = Job.query.order_by(Job.created_at.desc()).limit(limit).all()
        return {"jobs": [j.to_dict() for j in jobs]}
