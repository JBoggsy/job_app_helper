"""Shared DSPy utilities for micro_agents_v1 workflows.

Helpers that multiple workflows (or stages) are likely to need when
interacting with DSPy.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import dspy

from backend.agent.tools import AgentTools

if TYPE_CHECKING:
    from backend.llm.llm_factory import LLMConfig


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
    ``AgentTools.execute()`` which handles validation and error capture.
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

        # Closure to capture current `name`
        def _make_fn(tool_name: str):
            def _fn(**kwargs):
                # DSPy ReAct may nest args under a 'kwargs' key — unwrap
                if "kwargs" in kwargs and len(kwargs) == 1:
                    kwargs = kwargs["kwargs"]
                result = agent_tools.execute(tool_name, kwargs)
                # Return a string representation so DSPy can include it
                # in the trajectory.
                return json.dumps(result, default=str)

            _fn.__name__ = tool_name
            _fn.__doc__ = description
            return _fn

        dspy_tools.append(
            dspy.Tool(
                func=_make_fn(name),
                name=name,
                desc=description,
                arg_desc=arg_desc if arg_desc else None,
                arg_types=arg_types if arg_types else None,
            )
        )

    return dspy_tools
