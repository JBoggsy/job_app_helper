"""Result Collator — synthesise workflow results into a final user response.

Given a list of :class:`WorkflowResult` objects and the original user
message, the collator produces a coherent, user-facing response that
summarises what was accomplished across all workflow executions.

This module is a DSPy module so it can be optimised via DSPy's prompt
tuning and few-shot bootstrapping.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator

import dspy

from backend.llm.llm_factory import LLMConfig

from ..workflows._dspy_utils import build_lm
from ..workflows.registry import WorkflowResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signature & module
# ---------------------------------------------------------------------------


class CollateResultsSig(dspy.Signature):
    """Synthesise workflow results into a coherent user-facing response.

    You are the final stage of an agentic pipeline.  Earlier stages have
    already decomposed the user's request into outcomes, mapped them to
    workflows, and executed those workflows.  You now have the results.

    Your job is to produce a single, natural-language response that:
    - Directly addresses the user's original message.
    - Summarises what was accomplished (or what failed and why).
    - Presents information clearly — use bullet points, headers, or other
      markdown formatting when it improves readability.
    - Omits internal pipeline details (outcome IDs, workflow names, etc.)
      unless they are meaningful to the user.
    - Is concise but complete — don't omit important results, but don't
      pad with unnecessary filler either.
    - If any outcomes failed, acknowledge the failure and explain what
      went wrong in user-friendly terms.
    """

    user_message: str = dspy.InputField(desc="The user's original message")
    workflow_results: str = dspy.InputField(
        desc=(
            "JSON list of workflow results, each with 'outcome_id', "
            "'success', 'data', and 'summary' fields"
        )
    )
    response: str = dspy.OutputField(
        desc="A coherent, user-facing response summarising the results"
    )


class ResultCollator(dspy.Module):
    """DSPy module that synthesises workflow results into a final response.

    Uses ``dspy.ChainOfThought`` so the LLM reasons about how best to
    present the combined results before producing the response text.
    """

    def __init__(self, llm_config: LLMConfig):
        super().__init__()
        self.llm_config = llm_config
        self.collator = dspy.ChainOfThought(CollateResultsSig)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_results(results: list[WorkflowResult]) -> str:
        """Serialise workflow results to a JSON string for the LLM."""
        return json.dumps(
            [
                {
                    "outcome_id": r.outcome_id,
                    "success": r.success,
                    "data": r.data,
                    "summary": r.summary,
                }
                for r in results
            ],
            indent=2,
        )

    # ------------------------------------------------------------------
    # DSPy forward
    # ------------------------------------------------------------------

    def forward(
        self,
        user_message: str,
        workflow_results: str,
    ) -> dspy.Prediction:
        """DSPy forward pass — invokes the chain-of-thought collator."""
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.collator(
                user_message=user_message,
                workflow_results=workflow_results,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collate(
        self,
        results: list[WorkflowResult],
        user_message: str,
    ) -> Generator[dict, None, None]:
        """Synthesise workflow results into a streamed user response.

        This is the primary public API.  It formats the results, calls
        ``forward()``, and yields SSE ``text_delta`` events containing
        the final response.

        Args:
            results: Completed :class:`WorkflowResult` objects from
                the Workflow Executor.
            user_message: The user's original message.

        Yields:
            SSE event dicts with ``event: text_delta``.
        """
        logger.info(
            "ResultCollator synthesising %d result(s) for: %s",
            len(results),
            user_message[:120],
        )

        prediction = self(
            user_message=user_message,
            workflow_results=self._format_results(results),
        )

        response: str = prediction.response

        logger.debug("ResultCollator response length: %d chars", len(response))

        yield {"event": "text_delta", "data": {"content": response}}
