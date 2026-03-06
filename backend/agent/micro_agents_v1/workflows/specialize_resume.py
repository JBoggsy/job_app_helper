"""Specialize Resume workflow — tailor the user's resume for a specific job.

Pipeline:
1. A ``JobResolver`` identifies which tracked job the user wants to
   specialize their resume for.
2. The user's resume, profile, and the target job's details are loaded.
3. A DSPy agent enters an interactive chain-of-thought loop with the
   user, suggesting concrete edits to tailor the resume for the target
   job (reordering experience, emphasising relevant skills, adjusting
   summary statement, etc.).
4. The conversation continues until the user is satisfied with the
   specialised version.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


@register_workflow("specialize_resume")
class SpecializeResumeWorkflow(BaseWorkflow):
    """Interactive resume specialization for a target job."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        # TODO: implement
        raise NotImplementedError("SpecializeResumeWorkflow is not yet implemented")
        yield  # noqa: unreachable
