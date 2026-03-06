"""Interview Prep workflow — generate tailored interview preparation.

Pipeline:
1. A ``JobResolver`` identifies which tracked job to prepare for.
2. The user's resume, profile, and the job's details are loaded.
3. A DSPy module generates tailored interview prep materials:
   - Likely interview questions (behavioural, technical, role-specific)
   - STAR-format answer suggestions based on the user's experience
   - Key topics to research about the company/role
   - Questions the user should ask the interviewer
4. Results are presented in an organised, actionable format.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


@register_workflow("prep_interview")
class PrepInterviewWorkflow(BaseWorkflow):
    """Generate interview preparation materials for a specific job."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        # TODO: implement
        raise NotImplementedError("PrepInterviewWorkflow is not yet implemented")
        yield  # noqa: unreachable
