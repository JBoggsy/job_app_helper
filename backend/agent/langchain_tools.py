"""LangChain StructuredTool wrappers around AgentTools.

This module creates Pydantic input models for each tool and a factory
function that wraps AgentTools methods as LangChain StructuredTool
instances. The business logic in AgentTools is completely unchanged —
only the registration layer is different.
"""

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from backend.agent.tools import AgentTools


# ---------------------------------------------------------------------------
# Pydantic input schemas (one per tool, matching TOOL_DEFINITIONS)
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


class UpdateUserProfileInput(BaseModel):
    """Input for update_user_profile tool."""

    content: str = Field(
        description="The full updated markdown content for the user profile. Must include ALL existing information plus any new details."
    )


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def create_langchain_tools(agent_tools: AgentTools) -> list[StructuredTool]:
    """Wrap each AgentTools method as a LangChain StructuredTool.

    The AgentTools instance is captured via closure so all business logic
    (API keys, DB access, app context) works unchanged.

    Each wrapper calls agent_tools.execute() which handles dispatch and
    error catching. Return values are JSON-serialized strings so that
    LangChain ToolMessage.content is always a string.

    Args:
        agent_tools: An initialised AgentTools instance.

    Returns:
        List of StructuredTool instances ready to pass to model.bind_tools().
    """

    # -- Tools with parameters ------------------------------------------

    def web_search(query: str, num_results: int = 5) -> str:
        result = agent_tools.execute("web_search", {"query": query, "num_results": num_results})
        return json.dumps(result)

    def job_search(
        query: str,
        location: Optional[str] = None,
        remote_only: Optional[bool] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        num_results: int = 10,
        provider: Optional[str] = None,
    ) -> str:
        args = {"query": query, "num_results": num_results}
        if location is not None:
            args["location"] = location
        if remote_only is not None:
            args["remote_only"] = remote_only
        if salary_min is not None:
            args["salary_min"] = salary_min
        if salary_max is not None:
            args["salary_max"] = salary_max
        if provider is not None:
            args["provider"] = provider
        result = agent_tools.execute("job_search", args)
        return json.dumps(result)

    def scrape_url(url: str) -> str:
        result = agent_tools.execute("scrape_url", {"url": url})
        return json.dumps(result)

    def create_job(**kwargs) -> str:
        # Strip None values so AgentTools sees only provided args
        args = {k: v for k, v in kwargs.items() if v is not None}
        result = agent_tools.execute("create_job", args)
        return json.dumps(result)

    def list_jobs(
        status: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        url: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        args = {"limit": limit}
        if status is not None:
            args["status"] = status
        if company is not None:
            args["company"] = company
        if title is not None:
            args["title"] = title
        if url is not None:
            args["url"] = url
        result = agent_tools.execute("list_jobs", args)
        return json.dumps(result)

    def update_user_profile(content: str) -> str:
        result = agent_tools.execute("update_user_profile", {"content": content})
        return json.dumps(result)

    # -- Parameterless tools --------------------------------------------

    def read_user_profile() -> str:
        result = agent_tools.execute("read_user_profile", {})
        return json.dumps(result)

    def read_resume() -> str:
        result = agent_tools.execute("read_resume", {})
        return json.dumps(result)

    # -- Build StructuredTool list --------------------------------------

    tools = [
        StructuredTool.from_function(
            func=web_search,
            name="web_search",
            description=(
                "Search the web using Tavily. This is a general-purpose web search, "
                "not specific to job listings. Use this for researching companies, "
                "reading articles, or finding information that isn't a job listing."
            ),
            args_schema=WebSearchInput,
        ),
        StructuredTool.from_function(
            func=job_search,
            name="job_search",
            description=(
                "Search dedicated job board APIs (Adzuna, JSearch) for real job listings. "
                "Use this when the user wants to find job openings. Returns structured "
                "job data including title, company, location, salary, and application URL."
            ),
            args_schema=JobSearchInput,
        ),
        StructuredTool.from_function(
            func=scrape_url,
            name="scrape_url",
            description=(
                "Scrape a web page and return its text content. "
                "Use this to read job posting details from a URL."
            ),
            args_schema=ScrapeUrlInput,
        ),
        StructuredTool.from_function(
            func=create_job,
            name="create_job",
            description=(
                "Add a new job application to the tracker. "
                "Use this after researching a job posting to save it."
            ),
            args_schema=CreateJobInput,
        ),
        StructuredTool.from_function(
            func=read_user_profile,
            name="read_user_profile",
            description=(
                "Read the user's profile document. This markdown document contains "
                "information about the user including their education, work experience, "
                "skills, interests, salary preferences, location preferences, and job "
                "search goals. Reference this when evaluating job fit."
            ),
        ),
        StructuredTool.from_function(
            func=update_user_profile,
            name="update_user_profile",
            description=(
                "Update the user's profile document. Use this when the user shares "
                "information about themselves that is relevant to their job search — "
                "education, work experience, skills, interests, salary preferences, "
                "location preferences, career goals, etc. Always read the current "
                "profile first, then merge new information into the existing content. "
                "Preserve all existing information unless the user explicitly corrects it."
            ),
            args_schema=UpdateUserProfileInput,
        ),
        StructuredTool.from_function(
            func=read_resume,
            name="read_resume",
            description=(
                "Read the user's uploaded resume. Returns the full parsed text of the "
                "resume file (PDF or DOCX). Use this to understand the user's detailed "
                "work history, skills, and qualifications when evaluating job fit or "
                "tailoring applications. Returns null if no resume is uploaded."
            ),
        ),
        StructuredTool.from_function(
            func=list_jobs,
            name="list_jobs",
            description=(
                "List and search jobs currently tracked in the application database. "
                "Use this to check what jobs are already saved, filter by status, or "
                "look up a specific company/title/URL before adding duplicates."
            ),
            args_schema=ListJobsInput,
        ),
    ]

    return tools
