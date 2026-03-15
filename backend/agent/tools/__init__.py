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
    job_documents.py    save_job_document, get_job_document

Key methods on AgentTools:
    execute(tool_name, arguments) -> dict
        Dispatch a tool call by name. Returns result dict or {"error": str}.
    get_tool_definitions() -> list[dict]
        Return tool metadata (name, description, args_schema) for all
        registered tools. Agent implementations use this to adapt tools
        to their specific LLM framework.
"""

import logging
import time
import uuid

from backend.agent.event_bus import EventBus

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
from .job_documents import JobDocumentsMixin
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
    JobDocumentsMixin,
):
    """Collection of tools available to agents.

    Constructor args:
        search_api_key:    Tavily API key
        rapidapi_key:      RapidAPI key (for JSearch, Active Jobs DB, LinkedIn Jobs)
        conversation_id:   Current conversation ID
        event_bus:         EventBus for auto-emitting tool_start/tool_result/tool_error
    """

    def __init__(self, search_api_key="", rapidapi_key="",
                 conversation_id=None, event_bus: EventBus | None = None):
        self.search_api_key = search_api_key
        self.rapidapi_key = rapidapi_key
        self.conversation_id = conversation_id
        self.event_bus = event_bus

    def execute(self, tool_name, arguments=None):
        """Execute a tool by name with error handling.

        Auto-emits tool_start/tool_result/tool_error events to the event
        bus if one is configured.

        Arguments are validated against the tool's args_schema (if any).
        For tools with no args_schema, any LLM-hallucinated arguments
        are ignored.  For tools with a schema, Pydantic validates and
        strips unknown fields before dispatch.
        """
        arguments = arguments or {}
        call_id = str(uuid.uuid4())[:8]

        # Auto-emit tool_start
        if self.event_bus:
            self.event_bus.emit("tool_start", {
                "id": call_id,
                "name": tool_name,
                "arguments": arguments,
            })

        t0 = time.monotonic()
        result = self._execute_inner(tool_name, arguments)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # Auto-emit tool_result or tool_error
        if self.event_bus:
            if "error" in result:
                self.event_bus.emit("tool_error", {
                    "id": call_id,
                    "name": tool_name,
                    "error": result["error"],
                })
            else:
                self.event_bus.emit("tool_result", {
                    "id": call_id,
                    "name": tool_name,
                    "result": result,
                })

        # Record to telemetry
        try:
            from backend.telemetry.collector import get_collector
            from backend.telemetry.context import current_run_id, current_trace_id
            collector = get_collector()
            if collector is not None:
                is_error = "error" in result
                collector.record_tool_call(
                    call_id=call_id,
                    run_id=current_run_id.get(),
                    module_trace_id=current_trace_id.get(),
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    duration_ms=duration_ms,
                    success=not is_error,
                    error=result.get("error") if is_error else None,
                )
        except Exception:
            logger.debug("Telemetry: failed to record tool call", exc_info=True)

        return result

    def _execute_inner(self, tool_name, arguments):
        """Core tool dispatch logic (no event emission)."""
        method = getattr(self, tool_name, None)
        if method is None or not hasattr(method, "_tool_description"):
            return {"error": f"Unknown tool: {tool_name}"}

        schema = getattr(method, "_tool_args_schema", None)
        try:
            if schema is None:
                return method()
            else:
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
        LLM framework (e.g. OpenAI function-calling format).
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
