"""Scrape Job Posting workflow — extract structured info from a URL.

Pipeline:
1. The ``scrape_url`` tool fetches the page content.
2. A DSPy module extracts structured job fields (company, title,
   location, salary, requirements, nice-to-haves, description, etc.)
   from the raw page text.
3. If the user's profile is available, a brief fit assessment is
   generated.
4. The structured data and summary are returned so downstream workflows
   (e.g. ``add_to_tracker``) can consume them.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


@register_workflow("scrape_job_posting")
class ScrapeJobPostingWorkflow(BaseWorkflow):
    """Scrape a job posting URL and extract structured details."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        # TODO: implement
        raise NotImplementedError("ScrapeJobPostingWorkflow is not yet implemented")
        yield  # noqa: unreachable
