"""MicroAgentsV1Agent — workflow-orchestrated agent with DSPy micro-agents.

User requests are decomposed into discrete outcomes, each mapped to a
hand-crafted workflow and executed in dependency order.  Complex reasoning
steps within workflows are handled by small DSPy modules ("micro-agents").

Pipeline stages:
    1. Outcome Planner  — decompose user request into outcomes + dependency DAG
    2. Workflow Mapper   — match each outcome to a workflow, extract parameters
    3. Workflow Executor — run workflows in topological order, stream progress
    4. Result Collator   — synthesise a unified final response
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Generator

import dspy

from backend.agent.base import Agent
from backend.agent.event_bus import EventBus
from backend.agent.tools import AgentTools
from backend.agent.user_profile import read_profile
from backend.llm.llm_factory import LLMConfig
from backend.telemetry.context import telemetry_run

from .stages.outcome_planner import Outcome, OutcomePlanner
from .stages.result_collator import ResultCollator
from .stages.workflow_executor import WorkflowExecutor
from .stages.workflow_mapper import WorkflowAssignment, WorkflowMapper
from .workflows.registry import WorkflowResult, available_workflows_with_metadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Top-level agent
# ---------------------------------------------------------------------------

class MicroAgentsV1Agent(Agent):
    """Workflow-orchestrated agent with DSPy micro-agents.

    Composes four pipeline stages: OutcomePlanner → WorkflowMapper →
    WorkflowExecutor → ResultCollator.  Inherits from both the Agent ABC
    and dspy.Module, enabling sub-module discovery via
    ``named_sub_modules()`` / ``named_parameters()`` and save/load of
    optimised parameters across the full module tree.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        search_api_key: str = "",
        rapidapi_key: str = "",
        conversation_id: int | None = None,
    ):
        dspy.Module.__init__(self)
        self.llm_config = llm_config
        self.conversation_id = conversation_id
        self.event_bus = EventBus()

        # Shared tool interface
        self.tools = AgentTools(
            search_api_key=search_api_key,
            rapidapi_key=rapidapi_key,
            conversation_id=conversation_id,
            event_bus=self.event_bus,
        )

        # Pipeline stages
        self.outcome_planner = OutcomePlanner(llm_config)
        self.workflow_mapper = WorkflowMapper(llm_config)
        self.workflow_executor = WorkflowExecutor(self.tools, llm_config, self.event_bus)
        self.result_collator = ResultCollator(llm_config, self.event_bus)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _available_workflows() -> list[dict]:
        """Return metadata for all registered workflows."""
        return available_workflows_with_metadata()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, messages: list[dict]) -> Generator[dict, None, None]:
        from flask import current_app
        app = current_app._get_current_object()

        thread = threading.Thread(
            target=self._worker, args=(app, messages), daemon=True
        )
        thread.start()
        yield from self.event_bus.drain_blocking()
        thread.join()

    def _worker(self, app, messages):
        with app.app_context():
            try:
                self._pipeline(messages)
            except Exception as exc:
                logger.exception("MicroAgentsV1Agent error")
                self.event_bus.emit("error", {"message": str(exc)})
            finally:
                self.event_bus.close()

    def _pipeline(self, messages):
        user_message = messages[-1]["content"] if messages else ""
        user_profile = read_profile()
        full_text = ""

        with telemetry_run(self.conversation_id, user_message, "micro_agents_v1"):
            # --- Stage 1: Outcome Planning ---
            self.event_bus.emit("text_delta", {"content": "Thinking...\n\n"})
            full_text += "Thinking...\n\n"

            outcomes = self.outcome_planner.plan(
                user_message=user_message,
                conversation_history=messages,
                user_profile=user_profile,
            )

            logger.debug(
                "Planned outcomes: %s",
                [(o.id, o.description, o.depends_on) for o in outcomes],
            )

            # --- Stage 2: Workflow Mapping ---
            assignments = self.workflow_mapper.map(
                outcomes=outcomes,
                user_message=user_message,
                available_workflows=self._available_workflows(),
            )

            logger.debug(
                "Workflow assignments: %s",
                [
                    (a.outcome.id, a.workflow_name, a.params, a.deferred_params)
                    for a in assignments
                ],
            )

            # Inject recent conversation context into each assignment's
            # params so workflows/resolvers can handle relative references
            # like "the first one" or "the job we just discussed".
            _MAX_CONTEXT_MESSAGES = 10
            recent = messages[-(_MAX_CONTEXT_MESSAGES + 1) : -1]  # exclude current msg
            if recent:
                context_str = "\n".join(
                    f"{m['role']}: {m['content']}" for m in recent
                )
                for assignment in assignments:
                    assignment.params["conversation_context"] = context_str

            # --- Stage 3: Workflow Execution ---
            results = self.workflow_executor.execute(assignments)

            # --- Stage 4: Result Collation ---
            collated_text = self.result_collator.collate(
                results, user_message, assignments=assignments,
                user_profile=user_profile,
            )
            full_text += collated_text

        self.event_bus.emit("done", {"content": full_text})
