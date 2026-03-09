"""Result Collator — synthesise workflow results into a final user response.

Given a list of :class:`WorkflowResult` objects and the original user
message, the collator produces a coherent, user-facing response that
summarises what was accomplished across all workflow executions.

Uses ``litellm.completion()`` with ``stream=True`` so that the response
is streamed token-by-token to the user rather than appearing all at once
after a long pause.
"""

from __future__ import annotations

import json
import logging

import litellm

from backend.agent.event_bus import EventBus
from backend.llm.llm_factory import LLMConfig

from ..stages.workflow_mapper import WorkflowAssignment
from ..workflows.registry import WorkflowResult, get_workflow

logger = logging.getLogger(__name__)

_COLLATION_SYSTEM_PROMPT = """\
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


class ResultCollator:
    """Synthesise workflow results into a streamed final response.

    Uses ``litellm.completion()`` with streaming so users see tokens
    incrementally instead of waiting for the full response.
    """

    def __init__(self, llm_config: LLMConfig, event_bus: EventBus | None = None):
        self.llm_config = llm_config
        self.event_bus = event_bus

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_results(
        results: list[WorkflowResult],
        assignments: list[WorkflowAssignment] | None = None,
    ) -> str:
        """Serialise workflow results to a JSON string for the LLM.

        When *assignments* is provided, each result is annotated with the
        workflow name and its declared output schema so the LLM knows
        exactly what each field in ``data`` represents.
        """
        assignment_map: dict[int, WorkflowAssignment] = {}
        if assignments:
            assignment_map = {a.outcome.id: a for a in assignments}

        entries = []
        for r in results:
            entry: dict = {
                "outcome_id": r.outcome_id,
                "success": r.success,
                "data": r.data,
                "summary": r.summary,
            }
            a = assignment_map.get(r.outcome_id)
            if a:
                entry["workflow"] = a.workflow_name
                try:
                    wf_cls = get_workflow(a.workflow_name)
                    outputs = getattr(wf_cls, "OUTPUTS", {})
                    if outputs:
                        entry["output_schema"] = outputs
                except KeyError:
                    pass
            entries.append(entry)

        return json.dumps(entries, indent=2)

    def _completion_kwargs(self) -> dict:
        """Build kwargs for ``litellm.completion()``."""
        kwargs: dict = {
            "model": self.llm_config.model,
            "max_tokens": self.llm_config.max_tokens,
            "stream": True,
        }
        if self.llm_config.api_key:
            kwargs["api_key"] = self.llm_config.api_key
        if self.llm_config.api_base:
            kwargs["api_base"] = self.llm_config.api_base
        return kwargs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collate(
        self,
        results: list[WorkflowResult],
        user_message: str,
        assignments: list[WorkflowAssignment] | None = None,
    ) -> str:
        """Synthesise workflow results into a streamed user response.

        Emits ``text_delta`` events to the event bus token-by-token.
        Returns the full accumulated text.

        Args:
            results: Completed :class:`WorkflowResult` objects from
                the Workflow Executor.
            user_message: The user's original message.
            assignments: Optional workflow assignments — when provided,
                each result is annotated with its workflow name and
                output schema for better collation.

        Returns:
            The full accumulated response text.
        """
        logger.info(
            "ResultCollator synthesising %d result(s) for: %s",
            len(results),
            user_message[:120],
        )

        formatted = self._format_results(results, assignments)

        messages = [
            {"role": "system", "content": _COLLATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"**User's original message:**\n{user_message}\n\n"
                    f"**Workflow results:**\n{formatted}"
                ),
            },
        ]

        response = litellm.completion(
            messages=messages,
            **self._completion_kwargs(),
        )

        full_text = ""
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                if self.event_bus:
                    self.event_bus.emit("text_delta", {"content": delta.content})
                full_text += delta.content

        return full_text
