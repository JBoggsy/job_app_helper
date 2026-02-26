"""Job search sub-agent that finds, evaluates, and collects job listings.

This agent is invoked by the main agent's ``run_job_search`` tool. It makes
multiple search/scrape calls, evaluates each job against the user's profile,
and adds qualifying results (≥3 stars) to a per-conversation results list
via the ``add_search_result`` tool.

SSE events emitted (forwarded through the main agent's stream):
  - search_started:      sub-agent begins searching
  - search_progress:     brief status update (displayed as subtle chat text)
  - search_result_added: a new result was added to the panel
  - search_completed:    sub-agent finished
"""

import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage

from backend.agent.tools import AgentTools
from backend.agent.langchain_agent import (
    _ToolCallAccumulator,
    _accumulate_tool_call_chunk,
    _extract_text_from_chunk,
    _finalize_tool_calls,
)
from backend.agent.user_profile import read_profile
from backend.database import db
from backend.models.search_result import SearchResult
from backend.resume_parser import get_saved_resume, get_resume_text

logger = logging.getLogger(__name__)

# Tools the sub-agent may use (subset of AgentTools)
_SUB_AGENT_TOOL_NAMES = {
    "job_search", "web_search", "scrape_url",
    "read_user_profile", "read_resume",
}

JOB_SEARCH_MAX_ITERATIONS = 40
JOB_SEARCH_FIT_THRESHOLD = 3
JOB_SEARCH_DEFAULT_MAX_RESULTS = 25


JOB_SEARCH_SYSTEM_PROMPT = """You are a job search specialist agent. Your sole purpose is to find job listings that match the user's profile and preferences.

## Your Mission

You have been given a search request. Your job is to:
1. Execute multiple searches using varied queries (title variations, synonyms, related roles)
2. Evaluate each job found against the user's profile
3. Add qualifying jobs (rated ≥{fit_threshold} stars out of 5) to the results list using the `add_search_result` tool
4. Continue until you've thoroughly covered the search space

## User Profile
{user_profile}

## Resume
{resume_status}

## Available Tools

- **job_search**: Search job board APIs (JSearch, Adzuna) for real listings. Use varied queries.
- **web_search**: Search the web for job postings, company career pages, etc.
- **scrape_url**: Scrape a job posting URL to extract detailed information.
- **add_search_result**: Add a qualifying job to the results panel. Only add jobs rated ≥{fit_threshold}/5.
- **read_user_profile**: Re-read the user's profile for reference.
- **read_resume**: Read the user's resume for detailed qualifications.

## Search Strategy

1. **Start broad**: Search for the primary role/title the user is looking for
2. **Vary queries**: Try different title variations (e.g., "React Developer", "Frontend Engineer", "UI Developer")
3. **Try different locations**: If the user is flexible on location, search multiple areas
4. **Check web results**: Some jobs appear on company career pages but not job boards
5. **Scrape promising listings**: When a web search or job search returns a promising URL, scrape it for full details

## Evaluation Criteria (0-5 stars)

Rate each job based on how well it matches the user's profile:
- **5 stars**: Excellent fit — matches skills, experience level, salary, location, and career goals
- **4 stars**: Strong fit — matches most criteria with minor gaps
- **3 stars**: Decent fit — matches core requirements but has some mismatches
- **2 stars**: Weak fit — significant mismatches in key areas
- **1 star**: Poor fit — barely relevant
- **0 stars**: Not a fit — wrong field, level, or location entirely

Only add jobs rated ≥{fit_threshold} stars. For each added job, include a brief `fit_reason` explaining the rating.

## Result Limit

You may add up to {max_results} results. Stop searching once you reach this limit.

## When to Stop

Stop searching when:
- You've reached the result limit ({max_results})
- You've tried multiple query variations and are getting mostly duplicate results
- You've covered the major job boards and web sources for this search

## Output

When you're done searching, provide a brief summary of what you found — how many jobs total, how many were good fits, and any notable patterns (e.g., "Most positions require X", "Salary range is typically $Y-$Z")."""


class JobSearchSubAgentTools(AgentTools):
    """Extended AgentTools with the add_search_result tool for the sub-agent.

    This class adds the ability to write search results to the database
    and yield SSE events. It needs a conversation_id and an event queue
    to communicate results back to the main agent's stream.
    """

    def __init__(self, conversation_id, event_callback, max_results=JOB_SEARCH_DEFAULT_MAX_RESULTS,
                 **kwargs):
        super().__init__(**kwargs)
        self.conversation_id = conversation_id
        self.event_callback = event_callback
        self.max_results = max_results
        self.results_added = 0
        self.urls_seen = set()

        # Load existing URLs from this conversation for dedup
        existing = SearchResult.query.filter_by(conversation_id=conversation_id).all()
        for r in existing:
            if r.url:
                self.urls_seen.add(r.url)
        self.results_added = len(existing)

    def add_search_result(self, company, title, job_fit, url=None,
                          salary_min=None, salary_max=None, location=None,
                          remote_type=None, source=None, description=None,
                          requirements=None, nice_to_haves=None,
                          fit_reason=None):
        """Add a job to the search results panel."""
        if self.results_added >= self.max_results:
            return {"status": "limit_reached", "message": f"Result limit ({self.max_results}) reached. Stop searching."}

        # Deduplicate by URL
        if url and url in self.urls_seen:
            logger.info("add_search_result: skipping duplicate URL %s", url)
            return {"status": "duplicate", "message": f"Job at {url} already in results."}

        result = SearchResult(
            conversation_id=self.conversation_id,
            company=company,
            title=title,
            url=url,
            salary_min=salary_min,
            salary_max=salary_max,
            location=location,
            remote_type=remote_type,
            source=source,
            description=description,
            requirements=requirements,
            nice_to_haves=nice_to_haves,
            job_fit=job_fit,
            fit_reason=fit_reason,
        )
        db.session.add(result)
        db.session.commit()

        if url:
            self.urls_seen.add(url)
        self.results_added += 1

        result_dict = result.to_dict()
        self.event_callback({
            "event": "search_result_added",
            "data": result_dict,
        })

        logger.info("add_search_result: added result #%d — %s at %s (fit=%d)",
                     self.results_added, title, company, job_fit)
        return {"status": "added", "result_number": self.results_added, "id": result.id}

    def execute(self, tool_name, arguments):
        """Override execute to handle add_search_result specially."""
        if tool_name == "add_search_result":
            try:
                return self.add_search_result(**arguments)
            except Exception as e:
                logger.exception("add_search_result raised an exception")
                return {"error": str(e)}
        return super().execute(tool_name, arguments)

    def to_langchain_tools(self):
        """Build LangChain tools including add_search_result."""
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field
        from typing import Optional

        # Get base tools, filtered to sub-agent set
        base_tools = super().to_langchain_tools()
        filtered = [t for t in base_tools if t.name in _SUB_AGENT_TOOL_NAMES]

        # Add add_search_result tool
        class AddSearchResultInput(BaseModel):
            company: str = Field(description="Company name")
            title: str = Field(description="Job title")
            url: Optional[str] = Field(default=None, description="Job posting URL")
            salary_min: Optional[int] = Field(default=None, description="Minimum salary")
            salary_max: Optional[int] = Field(default=None, description="Maximum salary")
            location: Optional[str] = Field(default=None, description="Job location")
            remote_type: Optional[str] = Field(default=None, description="Remote type: remote, hybrid, or onsite")
            source: Optional[str] = Field(default=None, description="Where the job was found (jsearch, adzuna, web)")
            description: Optional[str] = Field(default=None, description="Brief job description summary")
            requirements: Optional[str] = Field(default=None, description="Key requirements, newline-separated")
            nice_to_haves: Optional[str] = Field(default=None, description="Nice-to-have qualifications, newline-separated")
            job_fit: int = Field(description="Job fit rating 0-5 based on user profile match")
            fit_reason: Optional[str] = Field(default=None, description="Brief explanation of the rating")

        def add_result_wrapper(**kwargs):
            args = {k: v for k, v in kwargs.items() if v is not None}
            try:
                result = self.add_search_result(**args)
            except Exception as e:
                logger.exception("add_search_result raised an exception")
                result = {"error": str(e)}
            return json.dumps(result)

        filtered.append(
            StructuredTool.from_function(
                func=add_result_wrapper,
                name="add_search_result",
                description=(
                    "Add a qualifying job to the search results panel. Only add jobs rated "
                    f"≥{JOB_SEARCH_FIT_THRESHOLD}/5 stars. Include structured data and a fit_reason."
                ),
                args_schema=AddSearchResultInput,
            )
        )

        return filtered


class LangChainJobSearchAgent:
    """Sub-agent that searches for jobs and populates the results panel.

    Yields SSE events that are forwarded through the main agent's stream.
    """

    def __init__(
        self,
        model: BaseChatModel,
        conversation_id: int,
        event_callback,
        max_results: int = JOB_SEARCH_DEFAULT_MAX_RESULTS,
        search_api_key: str = "",
        adzuna_app_id: str = "",
        adzuna_app_key: str = "",
        adzuna_country: str = "us",
        jsearch_api_key: str = "",
    ):
        self.conversation_id = conversation_id
        self.event_callback = event_callback

        self.agent_tools = JobSearchSubAgentTools(
            conversation_id=conversation_id,
            event_callback=event_callback,
            max_results=max_results,
            search_api_key=search_api_key,
            adzuna_app_id=adzuna_app_id,
            adzuna_app_key=adzuna_app_key,
            adzuna_country=adzuna_country,
            jsearch_api_key=jsearch_api_key,
        )
        self.lc_tools = self.agent_tools.to_langchain_tools()
        self.model_with_tools = model.bind_tools(self.lc_tools)

    def run(self, query, location=None, remote_only=False,
            salary_min=None, salary_max=None):
        """Run the job search loop.

        Args:
            query: Natural language search description
            location: Target location
            remote_only: Whether to filter for remote only
            salary_min: Minimum salary filter
            salary_max: Maximum salary filter

        Returns:
            Summary dict with total_found, results_added, summary text
        """
        # Build system prompt
        user_profile = read_profile()
        resume_info = get_saved_resume()
        resume_status = (
            f"Uploaded — {resume_info['filename']}" if resume_info else "No resume uploaded"
        )
        system_prompt = JOB_SEARCH_SYSTEM_PROMPT.format(
            user_profile=user_profile,
            resume_status=resume_status,
            fit_threshold=JOB_SEARCH_FIT_THRESHOLD,
            max_results=self.agent_tools.max_results,
        )

        # Build user message with search parameters
        search_parts = [f"Search request: {query}"]
        if location:
            search_parts.append(f"Location: {location}")
        if remote_only:
            search_parts.append("Remote only: yes")
        if salary_min:
            search_parts.append(f"Minimum salary: ${salary_min:,}")
        if salary_max:
            search_parts.append(f"Maximum salary: ${salary_max:,}")
        user_message = "\n".join(search_parts)

        lc_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        logger.info("JobSearchAgent started — query=%r location=%r", query, location)
        self.event_callback({
            "event": "search_started",
            "data": {"query": query},
        })

        full_text = ""

        for iteration in range(JOB_SEARCH_MAX_ITERATIONS):
            logger.info("JobSearch iteration %d/%d", iteration + 1, JOB_SEARCH_MAX_ITERATIONS)

            text_accum = ""
            accumulated_tool_calls: list[_ToolCallAccumulator] = []

            try:
                for chunk in self.model_with_tools.stream(lc_messages):
                    text = _extract_text_from_chunk(chunk)
                    if text:
                        text_accum += text
                        full_text += text

                    tc_chunks = getattr(chunk, "tool_call_chunks", None) or []
                    for tc_chunk in tc_chunks:
                        _accumulate_tool_call_chunk(accumulated_tool_calls, tc_chunk)

            except Exception as e:
                logger.error("JobSearch LLM stream error: %s", e)
                break

            final_tool_calls = _finalize_tool_calls(accumulated_tool_calls)

            if not final_tool_calls:
                # Sub-agent is done
                break

            # Build AIMessage
            ai_message = AIMessage(
                content=text_accum,
                tool_calls=[
                    {"id": tc.id, "name": tc.name, "args": tc.args}
                    for tc in final_tool_calls
                ],
            )
            lc_messages.append(ai_message)

            # Execute tools — emit progress events for user-facing visibility
            _progress_labels = {
                "web_search": "Searching the web...",
                "job_search": "Searching job boards...",
                "scrape_url": "Scraping job posting...",
                "add_search_result": "Evaluating candidate...",
            }
            for tc in final_tool_calls:
                logger.info("JobSearch tool call: %s", tc.name)

                label = _progress_labels.get(tc.name)
                if label:
                    self.event_callback({
                        "event": "search_progress",
                        "data": {"content": label},
                    })

                result = self.agent_tools.execute(tc.name, tc.args)

                lc_messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=tc.id,
                    )
                )

            # Check if result limit reached
            if self.agent_tools.results_added >= self.agent_tools.max_results:
                logger.info("JobSearch: result limit reached (%d)", self.agent_tools.max_results)
                break

        summary = {
            "results_added": self.agent_tools.results_added,
            "summary": full_text[-500:] if full_text else "Search completed.",
        }

        self.event_callback({
            "event": "search_completed",
            "data": {"results_added": self.agent_tools.results_added},
        })

        logger.info("JobSearchAgent finished — %d results added", self.agent_tools.results_added)
        return summary
