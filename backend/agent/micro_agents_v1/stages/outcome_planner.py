"""Outcome Planner — decompose a user request into outcomes with dependencies.

Given a user message, conversation history, and user profile, the planner
produces a list of discrete, action-oriented outcomes that together fulfil
the user's request.  Dependencies between outcomes form a DAG that the
downstream Workflow Executor uses to determine execution order.

This module is a DSPy module so it can be optimized via DSPy's prompt
tuning and few-shot bootstrapping.
"""

from __future__ import annotations

import logging

import dspy
from pydantic import BaseModel, Field

from backend.llm.llm_factory import LLMConfig
from backend.telemetry.traced_module import TracedModule

from ..workflows._dspy_utils import build_lm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Outcome(BaseModel):
    """A single desired outcome produced by the Outcome Planner."""

    id: int = Field(description="Unique sequential integer starting from 1")
    description: str = Field(
        description=(
            "A concise, action-oriented statement of the desired outcome. "
            "Should describe the concrete result the user expects."
        )
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description=(
            "IDs of other outcomes that must be completed before this one "
            "can begin. Empty list if the outcome has no prerequisites."
        ),
    )


# ---------------------------------------------------------------------------
# DSPy signature & module
# ---------------------------------------------------------------------------


class PlanOutcomesSig(dspy.Signature):
    """Decompose a user's request into a list of discrete outcomes.

    Analyse the user's message in the context of their conversation history
    and profile.  Produce an ordered list of outcomes — the concrete results
    the user expects — along with dependency edges that describe which
    outcomes must be completed before others can begin.

    Guidelines:
    - Each outcome should be a single, verifiable result (not a vague goal).
    - Keep the list minimal — only include outcomes that are necessary to
      satisfy the user's request.  Do not invent extra work.
    - Identify dependencies conservatively: only add a dependency when the
      earlier outcome's result is genuinely required as input.
    - If the request is simple and requires only one step, return a single
      outcome with no dependencies.
    - IDs must be sequential integers starting from 1.
    - depends_on must only reference IDs that appear earlier in the list.
    """

    user_message: str = dspy.InputField(desc="The user's latest message")
    conversation_history: str = dspy.InputField(
        desc=(
            "Previous messages in the conversation formatted as a "
            "multi-line string (role: content), or empty if this is "
            "the first message"
        )
    )
    user_profile: str = dspy.InputField(
        desc="The user's job-search profile (markdown with YAML frontmatter)"
    )
    outcomes: list[Outcome] = dspy.OutputField(
        desc="Ordered list of outcomes forming a dependency DAG"
    )


class OutcomePlanner(TracedModule, dspy.Module):
    """DSPy module that decomposes a user request into outcomes.

    Uses ``dspy.ChainOfThought`` so the LLM reasons step-by-step before
    producing the structured outcome list.
    """

    def __init__(self, llm_config: LLMConfig):
        super().__init__()
        self.llm_config = llm_config
        self.planner = dspy.ChainOfThought(PlanOutcomesSig)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_history(messages: list[dict]) -> str:
        """Format conversation messages into a readable multi-line string."""
        if not messages:
            return ""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def forward(
        self,
        user_message: str,
        conversation_history: str,
        user_profile: str,
    ) -> dspy.Prediction:
        """DSPy forward pass — invokes the chain-of-thought planner."""
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.planner(
                user_message=user_message,
                conversation_history=conversation_history,
                user_profile=user_profile,
            )

    def plan(
        self,
        user_message: str,
        conversation_history: list[dict],
        user_profile: str,
    ) -> list[Outcome]:
        """Decompose a user request into outcomes.

        This is the primary public API.  It formats the app's message
        list into a string, calls ``forward()``, and returns the
        validated outcome list.

        Args:
            user_message: The latest user message.
            conversation_history: Previous messages as ``[{"role": ..., "content": ...}, ...]``.
            user_profile: The user's job-search profile markdown.

        Returns:
            An ordered list of :class:`Outcome` instances.
        """
        result = self(
            user_message=user_message,
            conversation_history=self._format_history(conversation_history),
            user_profile=user_profile,
        )

        outcomes: list[Outcome] = result.outcomes
        logger.info(
            "OutcomePlanner produced %d outcome(s) for request: %s",
            len(outcomes),
            user_message[:120],
        )
        for o in outcomes:
            logger.debug("  Outcome %d: %s (depends_on=%s)", o.id, o.description, o.depends_on)

        return outcomes
