"""Write Cover Letter workflow — interactively draft a cover letter.

Pipeline:
1. A ``JobResolver`` identifies which tracked job the cover letter is for.
2. The user's resume, profile, and the target job's details are loaded.
3. A DSPy agent orchestrates an interactive writing session, drafting
   the cover letter section by section, incorporating the user's feedback
   at each step.
4. The final cover letter is presented along with a summary of the job
   match points that were highlighted.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


@register_workflow("write_cover_letter")
class WriteCoverLetterWorkflow(BaseWorkflow):
    """Interactive cover letter writing for a target job."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        # TODO: implement
        raise NotImplementedError("WriteCoverLetterWorkflow is not yet implemented")
        yield  # noqa: unreachable
