"""FixedPipelineAgent — main chat agent using structured routing + pipelines.

Replaces the monolithic ReAct loop with a routing agent that classifies
user intent, then dispatches to deterministic pipelines with scoped
micro-agent LLM calls.
"""

import logging
import time
from collections.abc import Generator

import dspy
from langchain_core.language_models import BaseChatModel

from backend.agent.base import Agent
from backend.agent.tools import AgentTools

from .context import RequestContext
from .dspy_lm import create_dspy_lm
from .pipelines import PIPELINE_REGISTRY
from .routing import route
from .streaming import yield_done, yield_error, yield_text

logger = logging.getLogger(__name__)


class FixedPipelineAgent(Agent):
    """Main chat agent — structured routing with deterministic pipelines."""

    def __init__(
        self,
        model: BaseChatModel,
        search_api_key: str = "",
        adzuna_app_id: str = "",
        adzuna_app_key: str = "",
        adzuna_country: str = "us",
        jsearch_api_key: str = "",
        conversation_id: int | None = None,
    ):
        self.model = model
        self.conversation_id = conversation_id

        # Create DSPy LM adapter (used via dspy.context in run())
        self._dspy_lm = create_dspy_lm(model)

        self.tools = AgentTools(
            search_api_key=search_api_key,
            adzuna_app_id=adzuna_app_id,
            adzuna_app_key=adzuna_app_key,
            adzuna_country=adzuna_country,
            jsearch_api_key=jsearch_api_key,
            conversation_id=conversation_id,
        )

    def run(self, messages: list[dict]) -> Generator[dict, None, None]:
        """Run the agent: route → acknowledge → execute pipeline → done."""
        # Use dspy.context so the LM is set per-thread without mutating
        # global DSPy state (avoids cross-thread RuntimeError).
        with dspy.context(lm=self._dspy_lm):
            yield from self._run_inner(messages)

    def _run_inner(self, messages: list[dict]) -> Generator[dict, None, None]:
        """Inner run logic, executed inside a dspy.context block."""
        full_text = ""

        try:
            # Step 1: Route the request
            routing_result = route(self.model, messages)
            logger.info("Routing result: type=%s, params=%s",
                       routing_result.request_type, routing_result.params)

            # Step 2: Stream acknowledgment
            if routing_result.acknowledgment:
                full_text += routing_result.acknowledgment
                yield yield_text(routing_result.acknowledgment)

            # Step 3: Build request context
            ctx = RequestContext(
                tools=self.tools,
                conversation_history=messages,
            )

            # Step 4: Dispatch to pipeline
            pipeline_fn = PIPELINE_REGISTRY.get(routing_result.request_type)
            if not pipeline_fn:
                logger.warning("Unknown pipeline: %s, falling back to general",
                             routing_result.request_type)
                pipeline_fn = PIPELINE_REGISTRY["general"]

            t0 = time.monotonic()
            for event in pipeline_fn(self.model, routing_result.params, ctx):
                # Accumulate text for the done event
                if event.get("event") == "text_delta":
                    full_text += event.get("data", {}).get("content", "")
                yield event
            elapsed = time.monotonic() - t0
            logger.info("Pipeline %s completed in %.2fs",
                       routing_result.request_type, elapsed)

        except Exception as exc:
            logger.exception("FixedPipelineAgent error")

            # Try to fall back to general pipeline
            try:
                if full_text:
                    full_text += "\n\n"
                fallback_text = "I encountered an issue, but let me try to help..."
                full_text += fallback_text
                yield yield_text(fallback_text)

                ctx = RequestContext(
                    tools=self.tools,
                    conversation_history=messages,
                )
                last_msg = ""
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        last_msg = msg["content"]
                        break

                general_fn = PIPELINE_REGISTRY["general"]
                for event in general_fn(self.model, {"question": last_msg, "needs_profile": True}, ctx):
                    if event.get("event") == "text_delta":
                        full_text += event.get("data", {}).get("content", "")
                    yield event
            except Exception as fallback_exc:
                logger.exception("Fallback also failed")
                yield yield_error(str(exc))
                return

        yield yield_done(full_text)
