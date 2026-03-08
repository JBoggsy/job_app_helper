"""Workflow Mapper — match each outcome to a registered workflow.

Given a list of outcomes from the Outcome Planner and the set of available
workflows, the mapper selects the best workflow for each outcome and
extracts the parameters needed to execute it.

This module is a DSPy module so it can be optimised via DSPy's prompt
tuning and few-shot bootstrapping.
"""

from __future__ import annotations

import logging

import dspy
from pydantic import BaseModel, Field

from backend.llm.llm_factory import LLMConfig

from .outcome_planner import Outcome
from ..workflows._dspy_utils import build_lm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class _RawAssignment(BaseModel):
    """LLM-serialisable workflow mapping (DSPy output schema).

    Contains only primitive/JSON-safe types so DSPy can produce it
    directly from LLM output.  :class:`WorkflowAssignment` extends
    this with the resolved :class:`Outcome` object.
    """

    outcome_id: int = Field(description="The ID of the outcome being mapped")
    workflow_name: str = Field(
        description="The registry key of the workflow to handle this outcome"
    )
    params: dict = Field(
        default_factory=dict,
        description=(
            "Concrete parameters extracted from the user message that the "
            "workflow needs (e.g. search query, job ID).  Keys depend on "
            "the chosen workflow."
        ),
    )
    deferred_params: dict[str, list[int]] = Field(
        default_factory=dict,
        description=(
            "Map of parameter names that cannot be resolved yet to the "
            "outcome ID(s) whose results are needed to derive them.  "
            "E.g. {'job_id': [1]} means 'job_id' depends on outcome 1's result."
        ),
    )


class WorkflowAssignment(_RawAssignment):
    """Resolved assignment: raw mapping enriched with the full Outcome."""

    outcome: Outcome


class MapWorkflowsSig(dspy.Signature):
    """Map each outcome to the most appropriate workflow.

    You are given a list of outcomes (each with an ID and description) and
    a list of available workflow names.  For every outcome, choose the
    single best workflow and extract any parameters the workflow will need.

    Guidelines:
    - Every outcome must receive exactly one workflow assignment.
    - Prefer a specialised workflow when the outcome clearly matches its
      purpose.  Fall back to "general" only when no specialised workflow
      fits.
    - Extract concrete parameter values from the user message where
      possible.  For parameters that depend on earlier outcomes, add
      them to ``deferred_params`` as a mapping from the parameter name
      to the list of outcome IDs whose results are needed to resolve it.
    """

    user_message: str = dspy.InputField(desc="The user's latest message")
    outcomes: str = dspy.InputField(
        desc=(
            "JSON list of outcomes, each with 'id', 'description', and "
            "'depends_on' fields"
        )
    )
    available_workflows: str = dspy.InputField(
        desc="Comma-separated list of registered workflow names"
    )
    assignments: list[_RawAssignment] = dspy.OutputField(
        desc="One workflow assignment per outcome"
    )


class WorkflowMapper(dspy.Module):
    """DSPy module that maps outcomes to workflows.

    Uses ``dspy.ChainOfThought`` so the LLM reasons about which workflow
    best satisfies each outcome before producing the structured mapping.
    """

    def __init__(self, llm_config: LLMConfig):
        super().__init__()
        self.llm_config = llm_config
        self.mapper = dspy.ChainOfThought(MapWorkflowsSig)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_outcomes(outcomes: list[Outcome]) -> str:
        """Serialise outcomes to a JSON string for the LLM."""
        import json

        return json.dumps(
            [o.model_dump() for o in outcomes],
            indent=2,
        )

    # ------------------------------------------------------------------
    # DSPy forward
    # ------------------------------------------------------------------

    def forward(
        self,
        user_message: str,
        outcomes: str,
        available_workflows: str,
    ) -> dspy.Prediction:
        """DSPy forward pass — invokes the chain-of-thought mapper."""
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.mapper(
                user_message=user_message,
                outcomes=outcomes,
                available_workflows=available_workflows,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map(
        self,
        outcomes: list[Outcome],
        user_message: str,
        available_workflows: list[str],
    ) -> list[WorkflowAssignment]:
        """Map each outcome to a workflow.

        This is the primary public API.  It serialises the inputs, calls
        ``forward()``, and returns validated ``WorkflowAssignment`` objects.

        Args:
            outcomes: Outcomes from the Outcome Planner.
            user_message: The latest user message.
            available_workflows: Registry keys of workflows the executor
                can dispatch.

        Returns:
            A list of :class:`WorkflowAssignment` instances, one per outcome.
        """
        outcome_map = {o.id: o for o in outcomes}

        result = self(
            user_message=user_message,
            outcomes=self._format_outcomes(outcomes),
            available_workflows=", ".join(available_workflows),
        )

        assignments: list[WorkflowAssignment] = []
        for sa in result.assignments:
            outcome = outcome_map.get(sa.outcome_id)
            if outcome is None:
                logger.warning(
                    "WorkflowMapper returned unknown outcome_id %d — skipping",
                    sa.outcome_id,
                )
                continue
            assignments.append(
                WorkflowAssignment(
                    outcome=outcome,
                    **sa.model_dump(),
                )
            )

        logger.info(
            "WorkflowMapper produced %d assignment(s) for %d outcome(s)",
            len(assignments),
            len(outcomes),
        )
        for a in assignments:
            logger.debug(
                "  Outcome %d → workflow=%s params=%s deferred=%s",
                a.outcome.id,
                a.workflow_name,
                a.params,
                a.deferred_params,
            )

        return assignments
