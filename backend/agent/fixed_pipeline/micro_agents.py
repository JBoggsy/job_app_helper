"""Micro-agent base class and all micro-agent implementations.

Micro-agents are scoped LLM calls — each gets a focused prompt and produces
either structured output (via invoke) or streamed text (via stream).

Structured-output agents (QueryGeneratorAgent, EvaluatorAgent, etc.) delegate
to DSPy modules in dspy_modules.py. Text-streaming agents remain as direct
LangChain calls since DSPy streaming requires LiteLLM.
"""

import json
import logging
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agent.default.agent import _extract_text

from . import schemas
from .dspy_modules import (
    DetailExtractionModule,
    EvaluatorModule,
    FitEvaluatorModule,
    ProfileUpdateModule,
    QueryGeneratorModule,
    ResearchQueryModule,
    TodoGeneratorModule,
)

logger = logging.getLogger(__name__)


def _is_ollama(model: BaseChatModel) -> bool:
    """Check if the model is an Ollama instance."""
    return type(model).__name__ == "ChatOllama"


class BaseMicroAgent:
    """Base class for micro-agents.

    Provides invoke() for structured output and stream() for text streaming.
    """

    def __init__(self, model: BaseChatModel):
        self.model = model

    def invoke(self, system_prompt: str, user_message: str, output_schema=None) -> dict | str:
        """Single LLM call, optionally with structured output.

        For all providers, tries with_structured_output() first.
        - Non-Ollama (Anthropic, OpenAI, Gemini): retries once on failure,
          then lets the exception propagate.
        - Ollama: falls back to JSON-in-text parsing on failure, since many
          Ollama models don't support structured output reliably.
        """
        agent_name = type(self).__name__
        schema_name = output_schema.__name__ if output_schema else "none"
        logger.info("[%s] invoke start — schema=%s, user_msg=%s",
                    agent_name, schema_name, user_message[:150])

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        if not output_schema:
            response = self.model.invoke(messages)
            text = _extract_text(response.content)
            logger.info("[%s] invoke done — raw text, len=%d", agent_name, len(text))
            return text

        # Try native structured output first for all providers
        try:
            structured_model = self.model.with_structured_output(output_schema)
            result = structured_model.invoke(messages)
            logger.info("[%s] invoke done — structured output: %s", agent_name, type(result).__name__)
            return result
        except (NotImplementedError, AttributeError, TypeError) as e:
            # Model doesn't support structured output at all
            logger.info("[%s] structured output not supported: %s", agent_name, e)
        except Exception as e:
            if _is_ollama(self.model):
                # Ollama: fall through to JSON-in-text fallback
                logger.info("[%s] structured output failed (Ollama), falling back to JSON-in-text: %s",
                           agent_name, e)
            else:
                # Non-Ollama: retry once, then let it propagate
                logger.warning("[%s] structured output failed: %s — retrying once", agent_name, e)
                result = structured_model.invoke(messages)
                logger.info("[%s] invoke done (retry) — structured output: %s", agent_name, type(result).__name__)
                return result

        # JSON-in-text fallback (Ollama models or models lacking structured output)
        logger.info("[%s] using JSON-in-text fallback", agent_name)
        messages[0] = SystemMessage(
            content=system_prompt + "\n\nRespond with ONLY valid JSON matching the requested schema."
        )
        response = self.model.invoke(messages)
        text = _extract_text(response.content)
        result = self._parse_json_response(text, output_schema)
        logger.info("[%s] invoke done — parsed JSON fallback: %s", agent_name, type(result).__name__)
        return result

    def stream(self, system_prompt: str, user_message: str):
        """Stream LLM response, yielding text chunks.

        Yields (str) text pieces as they arrive.
        """
        agent_name = type(self).__name__
        logger.info("[%s] stream start — user_msg=%s", agent_name, user_message[:150])
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        total_len = 0
        for chunk in self.model.stream(messages):
            if chunk.content:
                text = _extract_text(chunk.content)
                if text:
                    total_len += len(text)
                    yield text
        logger.info("[%s] stream done — total_len=%d", agent_name, total_len)

    def _parse_json_response(self, text: str, schema=None):
        """Parse a JSON response from text, optionally validating against a schema."""
        # Strip markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON in the text
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                data = json.loads(match.group())
            else:
                # Try array
                match = re.search(r"\[[\s\S]*\]", cleaned)
                if match:
                    data = json.loads(match.group())
                else:
                    raise

        if schema:
            return schema.model_validate(data)
        return data


# ── Concrete micro-agents ───────────────────────────────────────────────

class AdvisorAgent(BaseMicroAgent):
    """General career advice and open-ended questions."""

    def run(self, system_prompt: str, user_message: str):
        """Stream advice text. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class AnalysisAgent(BaseMicroAgent):
    """Analyze tracked jobs against profile and question."""

    def run(self, system_prompt: str, user_message: str):
        """Stream analysis text. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class ProfileUpdateAgent(BaseMicroAgent):
    """Interpret natural-language profile updates. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.ProfileUpdateResult:
        """Return structured profile updates via DSPy."""
        return ProfileUpdateModule().run(system_prompt, user_message)


class TodoGeneratorAgent(BaseMicroAgent):
    """Generate application preparation todos. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.TodoGeneratorResult:
        """Return structured todo list via DSPy."""
        return TodoGeneratorModule().run(system_prompt, user_message)


class QueryGeneratorAgent(BaseMicroAgent):
    """Generate optimized job search queries. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.QueryGeneratorResult:
        """Return structured search queries via DSPy."""
        return QueryGeneratorModule().run(system_prompt, user_message)


class EvaluatorAgent(BaseMicroAgent):
    """Evaluate job results against user profile. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.JobEvaluationResult:
        """Return structured evaluations via DSPy."""
        return EvaluatorModule().run(system_prompt, user_message)


class DetailExtractionAgent(BaseMicroAgent):
    """Extract structured job details from raw data. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.JobDetails:
        """Return structured job details via DSPy."""
        return DetailExtractionModule().run(system_prompt, user_message)


class FitEvaluatorAgent(BaseMicroAgent):
    """Deep fit analysis with strengths and gaps. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.FitEvaluation:
        """Return structured fit evaluation via DSPy."""
        return FitEvaluatorModule().run(system_prompt, user_message)


class ResultsSummaryAgent(BaseMicroAgent):
    """Summarize job search results."""

    def run(self, system_prompt: str, user_message: str):
        """Stream summary text. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class AnalysisSummaryAgent(BaseMicroAgent):
    """Summarize job posting analysis."""

    def run(self, system_prompt: str, user_message: str):
        """Stream analysis summary. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class InterviewPrepAgent(BaseMicroAgent):
    """Generate interview preparation content."""

    def run(self, system_prompt: str, user_message: str):
        """Stream prep content. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class CoverLetterAgent(BaseMicroAgent):
    """Draft cover letters."""

    def run(self, system_prompt: str, user_message: str):
        """Stream cover letter. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class ResumeTailorAgent(BaseMicroAgent):
    """Suggest resume tailoring edits."""

    def run(self, system_prompt: str, user_message: str):
        """Stream resume suggestions. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class QuestionGeneratorAgent(BaseMicroAgent):
    """Predict interview questions."""

    def run(self, system_prompt: str, user_message: str):
        """Stream questions and frameworks. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class ComparisonAgent(BaseMicroAgent):
    """Side-by-side job comparison."""

    def run(self, system_prompt: str, user_message: str):
        """Stream comparison analysis. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class RankingAgent(BaseMicroAgent):
    """Score and rank jobs."""

    def run(self, system_prompt: str, user_message: str):
        """Stream ranking analysis. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)


class ResearchQueryAgent(BaseMicroAgent):
    """Generate research search queries. Delegates to DSPy module."""

    def run(self, system_prompt: str, user_message: str) -> schemas.SearchQueryList:
        """Return structured search queries via DSPy."""
        return ResearchQueryModule().run(system_prompt, user_message)


class ResearchSynthesizerAgent(BaseMicroAgent):
    """Synthesize research findings into a report."""

    def run(self, system_prompt: str, user_message: str):
        """Stream research report. Yields str chunks."""
        yield from self.stream(system_prompt, user_message)
