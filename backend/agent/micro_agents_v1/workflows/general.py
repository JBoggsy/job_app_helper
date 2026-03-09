"""General workflow — fallback ReAct-based workflow for unspecialised outcomes.

When no specialised workflow matches an outcome, the General workflow
handles it by spinning up a DSPy ``ReAct`` module with access to the
full agent tool-set.  The LLM reasons about what to do, calls tools as
needed, and produces a textual answer.

This is intentionally simple — it mirrors the behaviour of a standard
ReAct agent loop, just scoped to a single outcome rather than the whole
user request.

Tool calls are streamed to the user in real-time via SSE ``tool_start``
and ``tool_result`` events emitted by the event bus.
"""

from __future__ import annotations

import logging

import dspy

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_dspy_tools, build_lm
from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signature for the ReAct module
# ---------------------------------------------------------------------------


class GeneralTaskSig(dspy.Signature):
    """Complete a single task using the available tools.

    You are a helpful job-search and job-application assistant.  You
    have been given one specific task to accomplish.  Use the tools at
    your disposal to gather information, perform actions, and then
    provide a concise answer summarising what you did and what the user
    should know.
    """

    task: str = dspy.InputField(desc="Description of the task to accomplish")
    context: str = dspy.InputField(
        desc="Extra context: user profile, prior results, or parameters (may be empty)"
    )
    answer: str = dspy.OutputField(
        desc="A concise summary of what was done and any information the user needs"
    )


# ---------------------------------------------------------------------------
# General workflow
# ---------------------------------------------------------------------------


@register_workflow("general")
class GeneralWorkflow(BaseWorkflow):
    """Fallback workflow: uses a DSPy ReAct loop with the full tool-set."""

    OUTPUTS = {
        "answer": "str — the full text answer produced by the ReAct loop",
    }

    def __init__(
        self,
        outcome_id: int,
        params: dict,
        tools: AgentTools,
        llm_config: LLMConfig,
        outcome_description: str = "",
        **kwargs,
    ):
        super().__init__(outcome_id, params, tools, llm_config, outcome_description, **kwargs)

        # Build DSPy tools — tool events auto-emit via AgentTools.execute()
        self._dspy_tools = build_dspy_tools(tools)

        # Create the ReAct module
        self._react = dspy.ReAct(
            signature=GeneralTaskSig,
            tools=self._dspy_tools,
            max_iters=10,
        )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> WorkflowResult:
        """Execute the ReAct loop for this outcome.

        Tool events are auto-emitted by AgentTools.execute() via the
        event bus.
        """
        task = self.outcome_description or self.params.get("task", self.params.get("description", ""))
        context = ""
        if self.params:
            context = "Parameters: " + ", ".join(
                f"{k}={v}" for k, v in self.params.items()
            )

        try:
            lm = build_lm(self.llm_config)

            with dspy.context(lm=lm):
                prediction = self._react(task=task, context=context)

            answer = prediction.answer

            logger.info(
                "GeneralWorkflow completed outcome %d: %s",
                self.outcome_id,
                answer[:120],
            )

            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=True,
                data={"answer": answer},
                summary=answer,
            )

        except Exception as exc:
            logger.exception(
                "GeneralWorkflow failed for outcome %d", self.outcome_id
            )
            self.event_bus.emit("text_delta", {"content": f"Error on outcome {self.outcome_id}: {exc}\n"})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": str(exc)},
                summary=f"Failed: {exc}",
            )
