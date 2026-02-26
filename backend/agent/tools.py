"""Agent tools with integrated LangChain StructuredTool generation.

Each tool is defined once: a decorated method on AgentTools with an
optional Pydantic input schema. The ``@agent_tool`` decorator captures
the tool name, LLM-facing description, and schema.  Call
``agent_tools.to_langchain_tools()`` to auto-generate LangChain
``StructuredTool`` instances — no separate wrapper file needed.
"""

import json
import logging
import random
import time
from typing import Optional

import cloudscraper
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from backend.database import db
from backend.job_enrichment import enrich_job_data
from backend.models.job import Job
from backend.models.search_result import SearchResult
from backend.agent.user_profile import read_profile, write_profile
from backend.resume_parser import get_resume_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool registration decorator
# ---------------------------------------------------------------------------

# Module-level list preserving definition order
_TOOL_REGISTRY: list[str] = []


def agent_tool(description: str, args_schema=None):
    """Mark a method as an agent tool with an LLM-facing description.

    Args:
        description: The tool description shown to the LLM.
        args_schema: Optional Pydantic BaseModel class for the input schema.
    """

    def decorator(method):
        method._tool_description = description
        method._tool_args_schema = args_schema
        _TOOL_REGISTRY.append(method.__name__)
        return method

    return decorator


# ---------------------------------------------------------------------------
# Pydantic input schemas
# ---------------------------------------------------------------------------


class WebSearchInput(BaseModel):
    """Input for web_search tool."""

    query: str = Field(description="Search query")
    num_results: int = Field(
        default=5, description="Number of results to return (default 5, max 10)"
    )


class JobSearchInput(BaseModel):
    """Input for job_search tool."""

    query: str = Field(
        description="Job search keywords (e.g., 'python developer', 'data scientist')"
    )
    location: Optional[str] = Field(
        default=None, description="Location filter (e.g., 'New York', 'London')"
    )
    remote_only: Optional[bool] = Field(
        default=None, description="Filter for remote jobs only"
    )
    salary_min: Optional[int] = Field(
        default=None, description="Minimum salary filter"
    )
    salary_max: Optional[int] = Field(
        default=None, description="Maximum salary filter"
    )
    num_results: int = Field(
        default=10, description="Number of results to return (default 10, max 20)"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Force a specific job search provider; defaults to whichever is configured (prefers JSearch if both available)",
    )


class ScrapeUrlInput(BaseModel):
    """Input for scrape_url tool."""

    url: str = Field(description="The URL to scrape")


class CreateJobInput(BaseModel):
    """Input for create_job tool."""

    company: str = Field(description="Company name")
    title: str = Field(description="Job title")
    url: Optional[str] = Field(default=None, description="Job posting URL")
    status: Optional[str] = Field(
        default=None,
        description="Application status (default: saved)",
    )
    notes: Optional[str] = Field(default=None, description="Notes about the job")
    salary_min: Optional[int] = Field(default=None, description="Minimum salary")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary")
    location: Optional[str] = Field(default=None, description="Job location")
    remote_type: Optional[str] = Field(
        default=None,
        description="Remote work type",
    )
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")
    contact_name: Optional[str] = Field(
        default=None, description="Contact person name"
    )
    contact_email: Optional[str] = Field(default=None, description="Contact email")
    source: Optional[str] = Field(
        default=None, description="Where the job was found"
    )
    requirements: Optional[str] = Field(
        default=None,
        description="Job requirements or qualifications, as a newline-separated list",
    )
    nice_to_haves: Optional[str] = Field(
        default=None,
        description="Nice-to-have qualifications, as a newline-separated list",
    )
    job_fit: Optional[int] = Field(
        default=None,
        description="Job fit rating from 0-5 stars based on how well this job matches the user's profile (0 = poor fit, 5 = excellent fit). Always set this when creating a job and a user profile exists.",
    )


class ListJobsInput(BaseModel):
    """Input for list_jobs tool."""

    status: Optional[str] = Field(
        default=None,
        description="Filter by application status",
    )
    company: Optional[str] = Field(
        default=None,
        description="Filter by company name (case-insensitive partial match)",
    )
    title: Optional[str] = Field(
        default=None,
        description="Filter by job title (case-insensitive partial match)",
    )
    url: Optional[str] = Field(
        default=None,
        description="Filter by job posting URL (exact or partial match)",
    )
    limit: int = Field(default=20, description="Max number of jobs to return (default 20)")


class RunJobSearchInput(BaseModel):
    """Input for run_job_search tool."""

    query: str = Field(
        description="Natural language description of what jobs to search for (e.g., 'React developer jobs', 'senior data scientist positions')"
    )
    location: Optional[str] = Field(
        default=None, description="Target location (e.g., 'Austin, TX', 'San Francisco')"
    )
    remote_only: Optional[bool] = Field(
        default=None, description="Only search for remote positions"
    )
    salary_min: Optional[int] = Field(
        default=None, description="Minimum salary filter"
    )
    salary_max: Optional[int] = Field(
        default=None, description="Maximum salary filter"
    )


class ListSearchResultsInput(BaseModel):
    """Input for list_search_results tool."""

    min_fit: Optional[int] = Field(
        default=None, description="Minimum job fit rating to include (0-5)"
    )


class UpdateUserProfileInput(BaseModel):
    """Input for update_user_profile tool."""

    content: str = Field(
        description="The full updated markdown content for the user profile. Must include ALL existing information plus any new details."
    )


# ---------------------------------------------------------------------------
# AgentTools
# ---------------------------------------------------------------------------


class AgentTools:
    def __init__(self, search_api_key="", adzuna_app_id="", adzuna_app_key="",
                 adzuna_country="us", jsearch_api_key="",
                 conversation_id=None, event_callback=None,
                 search_model=None, enrichment_model=None):
        self.search_api_key = search_api_key
        self.adzuna_app_id = adzuna_app_id
        self.adzuna_app_key = adzuna_app_key
        self.adzuna_country = adzuna_country
        self.jsearch_api_key = jsearch_api_key
        # For job search sub-agent
        self.conversation_id = conversation_id
        self.event_callback = event_callback
        self.search_model = search_model
        # For job enrichment (scrape + LLM extraction when adding jobs)
        self.enrichment_model = enrichment_model

    # -- Tool dispatch (used by agent loop for tool-call execution) -----

    def execute(self, tool_name, arguments):
        """Execute a tool by name with error handling."""
        method = getattr(self, tool_name, None)
        if method is None or not hasattr(method, "_tool_description"):
            logger.warning("Unknown tool requested: %s", tool_name)
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return method(**arguments)
        except Exception as e:
            logger.exception("Tool %s raised an exception", tool_name)
            return {"error": str(e)}

    # -- LangChain integration -----------------------------------------

    def to_langchain_tools(self):
        """Build LangChain StructuredTool list from ``@agent_tool`` methods.

        Returns:
            List of ``StructuredTool`` ready for ``model.bind_tools()``.
        """
        from langchain_core.tools import StructuredTool

        tools = []
        for name in _TOOL_REGISTRY:
            method = getattr(self, name)
            has_schema = getattr(method, "_tool_args_schema", None) is not None

            # Capture method in closure correctly
            if has_schema:
                def _make_wrapper(m):
                    def wrapper(**kwargs):
                        # Strip None values so method sees defaults
                        args = {k: v for k, v in kwargs.items() if v is not None}
                        try:
                            result = m(**args)
                        except Exception as e:
                            logger.exception("Tool %s raised an exception", m.__name__)
                            result = {"error": str(e)}
                        return json.dumps(result)
                    return wrapper
            else:
                def _make_wrapper(m):
                    def wrapper():
                        try:
                            result = m()
                        except Exception as e:
                            logger.exception("Tool %s raised an exception", m.__name__)
                            result = {"error": str(e)}
                        return json.dumps(result)
                    return wrapper

            tools.append(
                StructuredTool.from_function(
                    func=_make_wrapper(method),
                    name=name,
                    description=method._tool_description,
                    args_schema=getattr(method, "_tool_args_schema", None),
                )
            )

        return tools

    # -- Tool implementations ------------------------------------------

    @agent_tool(
        description=(
            "Search the web using Tavily. This is a general-purpose web search, "
            "not specific to job listings. Use this for researching companies, "
            "reading articles, or finding information that isn't a job listing."
        ),
        args_schema=WebSearchInput,
    )
    def web_search(self, query, num_results=5):
        if not self.search_api_key:
            return {"error": "SEARCH_API_KEY not configured"}
        num_results = min(num_results, 10)
        logger.info("web_search: query=%r num_results=%d", query, num_results)
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
        logger.info("web_search: returned %d results", len(results))
        return {"results": results}

    # ------------------------------------------------------------------
    # Job search via Adzuna / JSearch
    # ------------------------------------------------------------------

    @agent_tool(
        description=(
            "Search dedicated job board APIs (Adzuna, JSearch) for real job listings. "
            "Use this when the user wants to find job openings. Returns structured "
            "job data including title, company, location, salary, and application URL."
        ),
        args_schema=JobSearchInput,
    )
    def job_search(self, query, location=None, remote_only=False,
                   salary_min=None, salary_max=None, num_results=10,
                   provider=None):
        num_results = max(1, min(num_results, 20))
        logger.info("job_search: query=%r location=%r remote_only=%s provider=%s",
                    query, location, remote_only, provider)

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

        logger.info("adzuna search: returned %d results", len(results))
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

        logger.info("jsearch search: returned %d results", len(results))
        return {"results": results, "provider": "jsearch", "total": len(results)}

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
    ]

    def _build_browser_headers(self, ua):
        """Build realistic browser headers including Sec-* headers."""
        is_chrome = "Chrome" in ua
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        if is_chrome:
            headers["Sec-CH-UA"] = '"Chromium";v="133", "Not(A:Brand";v="99", "Google Chrome";v="133"'
            headers["Sec-CH-UA-Mobile"] = "?0"
            headers["Sec-CH-UA-Platform"] = '"Windows"' if "Windows" in ua else '"macOS"' if "Mac" in ua else '"Linux"'
        return headers

    @agent_tool(
        description=(
            "Scrape a web page and return its text content. "
            "Use this to read job posting details from a URL."
        ),
        args_schema=ScrapeUrlInput,
    )
    def scrape_url(self, url):
        logger.info("scrape_url: %s", url)

        # Strategy 1: cloudscraper session (handles Cloudflare challenges)
        text = self._scrape_with_cloudscraper(url)

        # Strategy 2: Tavily Extract API fallback
        if text is None and self.search_api_key:
            logger.info("scrape_url: trying Tavily extract fallback for %s", url)
            text = self._scrape_with_tavily(url)

        if text is None:
            return {"error": f"Failed to scrape {url} — all strategies returned 403/blocked"}

        # Truncate to ~4000 chars to fit in LLM context
        if len(text) > 4000:
            text = text[:4000] + "\n...(truncated)"
        logger.info("scrape_url: extracted %d chars from %s", len(text), url)
        return {"content": text, "url": url}

    def _scrape_with_cloudscraper(self, url):
        """Scrape using cloudscraper with realistic headers and retry logic."""
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
        )
        for attempt in range(3):
            try:
                ua = random.choice(self._USER_AGENTS)
                headers = self._build_browser_headers(ua)
                if attempt > 0:
                    time.sleep(1.5 + random.random() * 2)  # 1.5–3.5s delay between retries
                resp = scraper.get(url, timeout=20, headers=headers)
                resp.raise_for_status()
                return self._extract_text(resp.text)
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None) or getattr(e, "status_code", None)
                logger.info("scrape_url: cloudscraper attempt %d failed (%s) for %s", attempt + 1, status or e, url)
                if attempt == 2:
                    logger.warning("scrape_url: cloudscraper exhausted retries for %s", url)
        return None

    def _scrape_with_tavily(self, url):
        """Fallback: use Tavily Extract API to fetch page content."""
        try:
            resp = requests.post(
                "https://api.tavily.com/extract",
                json={"urls": url, "extract_depth": "basic"},
                headers={"Authorization": f"Bearer {self.search_api_key}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results and results[0].get("raw_content"):
                logger.info("scrape_url: Tavily extract succeeded for %s", url)
                return results[0]["raw_content"]
            logger.info("scrape_url: Tavily extract returned empty for %s", url)
        except Exception as e:
            logger.warning("scrape_url: Tavily extract failed for %s: %s", url, e)
        return None

    @staticmethod
    def _extract_text(html):
        """Parse HTML and return clean text content."""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    @agent_tool(
        description=(
            "Add a new job application to the tracker. "
            "Use this after researching a job posting to save it. "
            "If a URL is provided but some fields are missing, the system "
            "will automatically scrape the job posting to fill in details "
            "like salary, location, requirements, and tags."
        ),
        args_schema=CreateJobInput,
    )
    def create_job(self, **kwargs):
        logger.info("create_job: company=%r title=%r", kwargs.get("company"), kwargs.get("title"))

        # Attempt to enrich missing fields by scraping the job URL
        enriched = self._enrich_create_job_data(kwargs)

        job = Job(
            company=enriched["company"],
            title=enriched["title"],
            url=enriched.get("url"),
            status=enriched.get("status", "saved"),
            notes=enriched.get("notes"),
            salary_min=enriched.get("salary_min"),
            salary_max=enriched.get("salary_max"),
            location=enriched.get("location"),
            remote_type=enriched.get("remote_type"),
            tags=enriched.get("tags"),
            contact_name=enriched.get("contact_name"),
            contact_email=enriched.get("contact_email"),
            source=enriched.get("source"),
            job_fit=enriched.get("job_fit"),
            requirements=enriched.get("requirements"),
            nice_to_haves=enriched.get("nice_to_haves"),
        )
        db.session.add(job)
        db.session.commit()

        enrichment_status = enriched.get("_enrichment_status", "skipped")
        fields_enriched = enriched.get("_fields_enriched", [])
        logger.info("create_job: created job id=%d enrichment=%s fields=%s",
                    job.id, enrichment_status, fields_enriched)

        result = job.to_dict()
        if fields_enriched:
            result["_fields_enriched"] = fields_enriched
            result["_enrichment_status"] = enrichment_status
        return result

    def _enrich_create_job_data(self, kwargs):
        """Attempt to enrich job data via URL scraping + LLM extraction.

        Falls back to the original kwargs on any error.
        """
        try:
            return enrich_job_data(
                job_data=kwargs,
                search_api_key=self.search_api_key,
                llm_model=self.enrichment_model,
            )
        except Exception as e:
            logger.warning("create_job enrichment failed, using original data: %s", e)
            return kwargs

    @agent_tool(
        description=(
            "List and search jobs currently tracked in the application database. "
            "Use this to check what jobs are already saved, filter by status, or "
            "look up a specific company/title/URL before adding duplicates."
        ),
        args_schema=ListJobsInput,
    )
    def list_jobs(self, limit=20, status=None, company=None, title=None, url=None):
        logger.info("list_jobs: status=%s company=%s title=%s limit=%d", status, company, title, limit)
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
        logger.info("list_jobs: found %d jobs", len(jobs))
        return {"jobs": [j.to_dict() for j in jobs], "total": len(jobs)}

    @agent_tool(
        description=(
            "Read the user's profile document. This markdown document contains "
            "information about the user including their education, work experience, "
            "skills, interests, salary preferences, location preferences, and job "
            "search goals. Reference this when evaluating job fit."
        ),
    )
    def read_user_profile(self):
        content = read_profile()
        return {"content": content}

    @agent_tool(
        description=(
            "Update the user's profile document. Use this when the user shares "
            "information about themselves that is relevant to their job search — "
            "education, work experience, skills, interests, salary preferences, "
            "location preferences, career goals, etc. Always read the current "
            "profile first, then merge new information into the existing content. "
            "Preserve all existing information unless the user explicitly corrects it."
        ),
        args_schema=UpdateUserProfileInput,
    )
    def update_user_profile(self, content):
        logger.info("update_user_profile: writing %d chars", len(content))
        write_profile(content)
        return {"status": "updated", "content": content}

    @agent_tool(
        description=(
            "Read the user's uploaded resume. Returns the full parsed text of the "
            "resume file (PDF or DOCX). Use this to understand the user's detailed "
            "work history, skills, and qualifications when evaluating job fit or "
            "tailoring applications. Returns null if no resume is uploaded."
        ),
    )
    def read_resume(self):
        text = get_resume_text()
        if text is None:
            return {"content": None, "message": "No resume uploaded. The user can upload a resume via the Profile panel."}
        return {"content": text}

    @agent_tool(
        description=(
            "Launch a comprehensive job search using a specialized sub-agent. "
            "The sub-agent will search multiple job boards, evaluate each job against "
            "the user's profile, and add qualifying results (rated ≥3/5 stars) to a "
            "search results panel visible to the user. Use this whenever the user asks "
            "to find, search for, or discover job listings. The sub-agent runs "
            "autonomously and returns a summary of what it found. After receiving the "
            "summary, use list_search_results to review the full results and highlight "
            "the top 5 matches to the user."
        ),
        args_schema=RunJobSearchInput,
    )
    def run_job_search(self, query, location=None, remote_only=False,
                       salary_min=None, salary_max=None):
        if not self.conversation_id:
            return {"error": "Job search requires an active conversation."}
        if not self.event_callback:
            return {"error": "Job search event forwarding not configured."}

        from backend.agent.job_search_agent import LangChainJobSearchAgent

        # Use search-specific model if configured, otherwise fall back to main model
        model = self.search_model
        if model is None:
            return {"error": "No LLM model available for job search sub-agent."}

        agent = LangChainJobSearchAgent(
            model=model,
            conversation_id=self.conversation_id,
            event_callback=self.event_callback,
            search_api_key=self.search_api_key,
            adzuna_app_id=self.adzuna_app_id,
            adzuna_app_key=self.adzuna_app_key,
            adzuna_country=self.adzuna_country,
            jsearch_api_key=self.jsearch_api_key,
        )

        summary = agent.run(
            query=query,
            location=location,
            remote_only=remote_only or False,
            salary_min=salary_min,
            salary_max=salary_max,
        )
        return summary

    @agent_tool(
        description=(
            "List all job search results found in the current conversation's search "
            "results panel. Use this after run_job_search completes to review what was "
            "found and pick the top matches to highlight to the user."
        ),
        args_schema=ListSearchResultsInput,
    )
    def list_search_results(self, min_fit=None):
        if not self.conversation_id:
            return {"error": "No active conversation."}
        query = SearchResult.query.filter_by(conversation_id=self.conversation_id)
        if min_fit is not None:
            query = query.filter(SearchResult.job_fit >= min_fit)
        results = query.order_by(SearchResult.job_fit.desc(), SearchResult.created_at).all()
        return {
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
