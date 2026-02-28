"""Agent tool interfaces, implementations, and registration.

The AgentTools class provides tool implementations that agents invoke
during their run loops. Each tool is a method decorated with @agent_tool
and lives in its own module alongside its Pydantic input schema.

Consumers:
    - Agent implementations create AgentTools and call .execute()

Module layout:
    _registry.py        agent_tool decorator + _TOOL_REGISTRY
    web_search.py       web_search, web_research
    job_search.py       job_search
    scrape_url.py       scrape_url
    jobs.py             create_job, list_jobs, edit_job, remove_job, list_job_todos, add_job_todo, edit_job_todo, remove_job_todo
    profile.py          read_user_profile, update_user_profile
    resume.py           read_resume
    search_results.py   add_search_result, list_search_results

Key methods on AgentTools:
    execute(tool_name, arguments) -> dict
        Dispatch a tool call by name. Returns result dict or {"error": str}.
    get_tool_definitions() -> list[dict]
        Return tool metadata (name, description, args_schema) for all
        registered tools. Agent implementations use this to adapt tools
        to their specific LLM framework.
"""

import logging

# Mixin imports must come before AgentTools so that the @agent_tool
# decorators fire and populate _TOOL_REGISTRY before get_tool_definitions()
# could ever be called.
from ._registry import _TOOL_REGISTRY
from .job_search import JobSearchMixin
from .jobs import JobsMixin
from .profile import ProfileMixin
from .resume import ResumeMixin
from .scrape_url import ScrapeUrlMixin
from .search_results import SearchResultsMixin
from .web_search import WebSearchMixin

logger = logging.getLogger(__name__)


class AgentTools(
    WebSearchMixin,
    JobSearchMixin,
    ScrapeUrlMixin,
    JobsMixin,
    ProfileMixin,
    ResumeMixin,
    SearchResultsMixin,
):
    """Collection of tools available to agents.

    Constructor args:
        search_api_key:    Tavily API key
        adzuna_app_id:     Adzuna app ID
        adzuna_app_key:    Adzuna app key
        adzuna_country:    Adzuna country code (default "us")
        jsearch_api_key:   RapidAPI JSearch key
        conversation_id:   Current conversation ID
        event_callback:    Callable for SSE events (e.g. search_result_added)
    """

    def __init__(self, search_api_key="", adzuna_app_id="", adzuna_app_key="",
                 adzuna_country="us", jsearch_api_key="",
                 conversation_id=None, event_callback=None):
        self.search_api_key = search_api_key
        self.adzuna_app_id = adzuna_app_id
        self.adzuna_app_key = adzuna_app_key
        self.adzuna_country = adzuna_country
        self.jsearch_api_key = jsearch_api_key
        self.conversation_id = conversation_id
        self.event_callback = event_callback

    def execute(self, tool_name, arguments):
        """Execute a tool by name with error handling.

        Arguments are validated against the tool's args_schema (if any).
        For tools with no args_schema, any LLM-hallucinated arguments
        are ignored.  For tools with a schema, Pydantic validates and
        strips unknown fields before dispatch.
        """
        method = getattr(self, tool_name, None)
        if method is None or not hasattr(method, "_tool_description"):
            return {"error": f"Unknown tool: {tool_name}"}

        schema = getattr(method, "_tool_args_schema", None)
        try:
            if schema is None:
                # Tool takes no arguments — ignore anything the LLM sent
                return method()
            else:
                # Validate through Pydantic, which strips unknown fields
                # and raises on missing required fields
                validated = schema(**arguments)
                return method(**validated.model_dump())
        except Exception as e:
            logger.exception("Tool %s raised an exception", tool_name)
            return {"error": str(e)}

    def get_tool_definitions(self):
        """Return metadata for all registered tools.

        Returns a list of dicts, each with:
            - name: str — tool method name
            - description: str — LLM-facing description
            - args_schema: Pydantic BaseModel class or None

        Agent implementations use this to adapt tools to their specific
        LLM framework (e.g. LangChain StructuredTool, OpenAI function
        calling, etc.).
        """
        definitions = []
        for name in _TOOL_REGISTRY:
            method = getattr(self, name, None)
            if method is None:
                continue
            definitions.append({
                "name": name,
                "description": getattr(method, "_tool_description", ""),
                "args_schema": getattr(method, "_tool_args_schema", None),
            })
        return definitions
