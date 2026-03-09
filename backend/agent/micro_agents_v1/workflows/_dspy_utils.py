"""Shared DSPy utilities for micro_agents_v1 workflows.

Helpers that multiple workflows (or stages) are likely to need when
interacting with DSPy.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import dspy

from backend.agent.tools import AgentTools

if TYPE_CHECKING:
    from backend.llm.llm_factory import LLMConfig

logger = logging.getLogger(__name__)


def build_lm(llm_config: "LLMConfig") -> dspy.LM:
    """Build a ``dspy.LM`` from the project's ``LLMConfig``.

    Centralised here so every DSPy module and workflow avoids
    duplicating this construction logic.
    """
    kwargs: dict = {}
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key
    if llm_config.api_base:
        kwargs["api_base"] = llm_config.api_base
    return dspy.LM(
        model=llm_config.model,
        max_tokens=llm_config.max_tokens,
        **kwargs,
    )


def build_dspy_tools(agent_tools: AgentTools) -> list[dspy.Tool]:
    """Convert registered AgentTools into ``dspy.Tool`` instances.

    Each agent tool is wrapped in a plain function that DSPy's ReAct (or
    any other tool-using DSPy module) can call.  The wrapper delegates to
    ``AgentTools.execute()`` which handles validation, error capture, and
    auto-emission of tool_start/tool_result/tool_error events to the bus.
    """
    dspy_tools: list[dspy.Tool] = []

    for defn in agent_tools.get_tool_definitions():
        name = defn["name"]
        description = defn["description"]
        schema_cls = defn["args_schema"]  # Pydantic BaseModel or None

        # Build arg metadata from Pydantic schema (if any)
        arg_desc: dict[str, str] = {}
        arg_types: dict[str, Any] = {}
        if schema_cls is not None:
            for field_name, field_info in schema_cls.model_fields.items():
                arg_desc[field_name] = field_info.description or ""
                arg_types[field_name] = field_info.annotation

        # Closure to capture current `name` and whether it has a real
        # parameter called "kwargs" (to avoid false-positive unwrapping).
        has_kwargs_param = "kwargs" in arg_types if arg_types else False

        def _make_fn(tool_name: str, _has_kwargs_param: bool):
            def _fn(**kwargs):
                # Some LLMs nest all arguments under a "kwargs" key when
                # producing tool calls.  Unwrap this if (a) the only key
                # received is "kwargs", (b) its value is a dict, and
                # (c) the tool does not genuinely declare a parameter
                # named "kwargs".
                if (
                    not _has_kwargs_param
                    and len(kwargs) == 1
                    and "kwargs" in kwargs
                    and isinstance(kwargs["kwargs"], dict)
                ):
                    kwargs = kwargs["kwargs"]

                # Just call execute — events are auto-emitted by the bus
                result = agent_tools.execute(tool_name, kwargs)
                return json.dumps(result, default=str)

            _fn.__name__ = tool_name
            _fn.__doc__ = description
            return _fn

        dspy_tools.append(
            dspy.Tool(
                func=_make_fn(name, has_kwargs_param),
                name=name,
                desc=description,
                arg_desc=arg_desc if arg_desc else None,
                arg_types=arg_types if arg_types else None,
            )
        )

    return dspy_tools


# ---------------------------------------------------------------------------
# Shared context loaders for job-oriented workflows
# ---------------------------------------------------------------------------

# Default limits shared across workflows.  Individual callers can override.
RESUME_CONTEXT_MAX_CHARS = 3000
JOB_RESOLVER_MIN_CONFIDENCE = 0.3


def load_job_context(
    tools: AgentTools,
    params: dict,
    llm_config: "LLMConfig",
    user_message: str,
    conversation_context: str = "",
    *,
    min_confidence: float = JOB_RESOLVER_MIN_CONFIDENCE,
) -> tuple[dict | None, str]:
    """Resolve the target job and build a context string for prompts.

    Shared by any workflow that needs to identify which tracked job the
    user is referring to.  Resolution order:

    1. If ``params["job_id"]`` is present, look up by ID directly.
    2. Otherwise, use :class:`JobResolver` to match the user message
       against the tracked job list.

    Returns ``(job_dict, context_string)``.  Both are ``None``/empty
    when no job can be resolved.
    """
    from .resolvers import JobResolver  # deferred to avoid circular import

    job_id = params.get("job_id")
    job: dict | None = None

    jobs_resp = tools.execute("list_jobs", {"limit": 50})
    tracker_jobs = jobs_resp.get("jobs", []) if "error" not in jobs_resp else []

    if job_id and tracker_jobs:
        try:
            job_id_int = int(job_id)
        except (ValueError, TypeError):
            logger.warning("Non-numeric job_id '%s', skipping direct lookup", job_id)
            job_id_int = None
        if job_id_int is not None:
            for j in tracker_jobs:
                if j["id"] == job_id_int:
                    job = j
                    break

    if job is None and tracker_jobs:
        resolver = JobResolver(llm_config)
        resolved = resolver.resolve(
            user_message=user_message,
            jobs=tracker_jobs,
            conversation_context=conversation_context,
            min_confidence=min_confidence,
        )
        if resolved:
            matched_id = resolved[0].job_id
            for j in tracker_jobs:
                if j["id"] == matched_id:
                    job = j
                    break

    if job is None:
        return None, ""

    parts = [f"Role: {job['title']} at {job['company']}"]
    if job.get("location"):
        parts.append(f"Location: {job['location']}")
    if job.get("remote_type"):
        parts.append(f"Remote: {job['remote_type']}")
    if job.get("salary_min") or job.get("salary_max"):
        parts.append(
            "Salary: "
            f"{job.get('salary_min', 'unspecified')} – "
            f"{job.get('salary_max', 'unspecified')}"
        )
    if job.get("requirements"):
        parts.append(f"Requirements:\n{job['requirements']}")
    if job.get("nice_to_haves"):
        parts.append(f"Nice to haves:\n{job['nice_to_haves']}")

    return job, "\n".join(parts)


def load_user_context(
    tools: AgentTools,
    *,
    max_chars: int | None = RESUME_CONTEXT_MAX_CHARS,
) -> str:
    """Load user profile and resume into a single context string.

    Shared by any workflow that needs the user's background for prompt
    context.

    Args:
        tools: Agent tools instance (or ``_CachedTools`` proxy).
        max_chars: Maximum characters to include from the resume.
            Pass ``None`` for the full un-truncated resume (e.g. for
            claim validation where truncation causes false positives).
    """
    parts: list[str] = []

    profile_resp = tools.execute("read_user_profile", {})
    if profile := profile_resp.get("content", ""):
        parts.append(f"## User Profile\n{profile}")

    resume_resp = tools.execute("read_resume", {})
    if "error" not in resume_resp:
        if parsed := resume_resp.get("parsed"):
            raw = json.dumps(parsed, default=str)
            if max_chars is not None:
                raw = raw[:max_chars]
            parts.append(f"## Resume (parsed)\n{raw}")
        elif text := resume_resp.get("text"):
            if max_chars is not None:
                text = text[:max_chars]
            parts.append(f"## Resume\n{text}")

    return "\n\n".join(parts)
