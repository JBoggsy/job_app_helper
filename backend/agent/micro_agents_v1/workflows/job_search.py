"""Job Search workflow — search job boards and return a curated list.

Pipeline:
1. A DSPy module generates 4–10 diverse search queries (full API param
   sets) from the user's request, expanding vague terms (e.g. "in the
   south" → GA, NC, SC, FL, etc.).
2. Queries are executed programmatically via the ``job_search`` and/or
   ``web_search`` tools.
3. Results are de-duplicated (by URL and company+title).
4. A DSPy evaluator scores each job on a 0–5 star scale with a short
   fit explanation, using the user's profile for context.
5. Jobs scoring < 3 stars are filtered out.
6. Qualifying jobs are added as search results via ``add_search_result``.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


@register_workflow("job_search")
class JobSearchWorkflow(BaseWorkflow):
    """Search job boards, evaluate fit, and return curated results."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        # TODO: implement
        raise NotImplementedError("JobSearchWorkflow is not yet implemented")
        yield  # noqa: unreachable — makes this a generator
