"""Workflow registry — maps workflow names to workflow classes.

Each workflow is a callable that accepts a ``WorkflowAssignment`` and an
``AgentTools`` instance, executes whatever logic is needed, and returns a
``WorkflowResult``.  Workflows may also yield SSE-style event dicts to
stream progress to the user.

Usage::

    from backend.agent.micro_agents_v1.workflows.registry import (
        get_workflow, available_workflow_names,
    )

    workflow_cls = get_workflow("general")
    result = yield from workflow_cls(assignment, tools, llm_config).run()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agent.tools import AgentTools
    from backend.llm.llm_factory import LLMConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared data structure (also used by agent.py / WorkflowExecutor)
# ---------------------------------------------------------------------------


@dataclass
class WorkflowResult:
    """The output of a single workflow execution."""

    outcome_id: int
    success: bool
    data: dict = field(default_factory=dict)
    summary: str = ""


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class BaseWorkflow(ABC):
    """Interface that all workflows must satisfy.

    Subclasses implement ``run()`` as a generator that yields SSE event
    dicts and returns a ``WorkflowResult`` via ``StopIteration.value``
    (i.e. callers use ``result = yield from workflow.run()``).
    """

    def __init__(
        self,
        outcome_id: int,
        params: dict,
        tools: "AgentTools",
        llm_config: "LLMConfig",
        outcome_description: str = "",
    ):
        self.outcome_id = outcome_id
        self.params = params
        self.tools = tools
        self.llm_config = llm_config
        self.outcome_description = outcome_description

    @abstractmethod
    def run(self) -> Generator[dict, None, WorkflowResult]:
        """Execute the workflow, yielding SSE events and returning a result."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_WORKFLOW_REGISTRY: dict[str, type[BaseWorkflow]] = {}


def register_workflow(name: str):
    """Class decorator that registers a workflow under *name*."""

    def decorator(cls: type[BaseWorkflow]):
        if name in _WORKFLOW_REGISTRY:
            logger.warning("Overwriting workflow registration for %r", name)
        _WORKFLOW_REGISTRY[name] = cls
        return cls

    return decorator


def get_workflow(name: str) -> type[BaseWorkflow]:
    """Look up a workflow by registry key.

    Raises ``KeyError`` if the name is not registered.
    """
    return _WORKFLOW_REGISTRY[name]


def available_workflow_names() -> list[str]:
    """Return the names of all registered workflows."""
    return list(_WORKFLOW_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Auto-import workflow modules so their @register_workflow decorators fire.
# ---------------------------------------------------------------------------

from . import general as _general  # noqa: E402, F401
from . import job_search as _job_search  # noqa: E402, F401
from . import add_to_tracker as _add_to_tracker  # noqa: E402, F401
from . import edit_job as _edit_job  # noqa: E402, F401
from . import remove_jobs as _remove_jobs  # noqa: E402, F401
from . import specialize_resume as _specialize_resume  # noqa: E402, F401
from . import write_cover_letter as _write_cover_letter  # noqa: E402, F401
from . import scrape_job_posting as _scrape_job_posting  # noqa: E402, F401
from . import compare_jobs as _compare_jobs  # noqa: E402, F401
from . import prep_interview as _prep_interview  # noqa: E402, F401
from . import application_todos as _application_todos  # noqa: E402, F401
from . import update_profile as _update_profile  # noqa: E402, F401
