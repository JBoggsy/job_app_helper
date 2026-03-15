"""Common resolvers — shared DSPy modules for identifying entities.

Many workflows need to figure out which job(s) or search result(s) the
user is referring to.  Rather than re-implementing that logic in every
workflow, the resolvers here provide reusable DSPy modules that any
workflow can compose.

Usage::

    from backend.agent.micro_agents_v1.workflows.resolvers import (
        JobResolver,
        SearchResultResolver,
    )

    resolver = JobResolver(llm_config)
    job_ids = resolver.resolve(user_message, jobs)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import dspy
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.llm.llm_factory import LLMConfig

from backend.telemetry.traced_module import TracedModule

from ._dspy_utils import build_lm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job Resolver — identify tracker jobs the user is referring to
# ---------------------------------------------------------------------------


class ResolvedJob(BaseModel):
    """A single resolved job reference."""

    job_id: int = Field(description="The ID of the matched job in the tracker")
    confidence: float = Field(
        description="Confidence score 0.0-1.0 that this is the job the user means"
    )
    reason: str = Field(description="Brief explanation of why this job was matched")


class ResolveJobsSig(dspy.Signature):
    """Identify which job(s) in the tracker the user is referring to.

    You are given the user's message and a JSON list of jobs currently in
    their tracker.  Determine which job(s) the user is talking about.

    Guidelines:
    - Match based on company name, job title, URL, or any other identifying
      detail the user mentions.
    - If the user says "all jobs", "everything", etc., return all jobs. This
      does not apply to, e.g., "all of those jobs," which should be further
      resolved based on the context.
    - If the user refers to jobs by relative position ("the first one",
      "the last one I added"), use the list ordering (newest first).
    - Return an empty list if no jobs can be confidently matched.
    - Each match needs a confidence score (0.0-1.0) and a brief reason.
    """

    user_message: str = dspy.InputField(desc="The user's message referencing one or more jobs")
    conversation_context: str = dspy.InputField(
        desc="Recent conversation history for additional context (may be empty)"
    )
    jobs: str = dspy.InputField(desc="JSON list of jobs in the tracker (id, company, title, url, status, ...)")
    resolved_jobs: list[ResolvedJob] = dspy.OutputField(
        desc="List of matched jobs with confidence scores"
    )


class JobResolver(TracedModule, dspy.Module):
    """DSPy module that resolves user references to tracker jobs.

    Wraps a ``ChainOfThought`` predictor so the LLM reasons about which
    jobs match the user's description before producing structured output.
    """

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.resolver = dspy.ChainOfThought(ResolveJobsSig)

    def forward(
        self,
        user_message: str,
        conversation_context: str,
        jobs: str,
    ) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.resolver(
                user_message=user_message,
                conversation_context=conversation_context,
                jobs=jobs,
            )

    def resolve(
        self,
        user_message: str,
        jobs: list[dict],
        conversation_context: str = "",
        min_confidence: float = 0.5,
    ) -> list[ResolvedJob]:
        """Resolve user references to tracker jobs.

        Args:
            user_message: The user's latest message.
            jobs: List of job dicts (from ``list_jobs`` tool).
            conversation_context: Recent conversation history.
            min_confidence: Minimum confidence threshold for inclusion.

        Returns:
            List of :class:`ResolvedJob` instances above the confidence
            threshold, sorted by confidence descending.
        """
        if not jobs:
            return []

        result = self(
            user_message=user_message,
            conversation_context=conversation_context,
            jobs=json.dumps(jobs, default=str),
        )

        resolved = [
            r for r in result.resolved_jobs
            if r.confidence >= min_confidence
        ]
        resolved.sort(key=lambda r: r.confidence, reverse=True)
        return resolved


# ---------------------------------------------------------------------------
# Search Result Resolver — identify search results the user refers to
# ---------------------------------------------------------------------------


class ResolvedSearchResult(BaseModel):
    """A single resolved search result reference."""

    result_id: int = Field(description="The ID of the matched search result")
    confidence: float = Field(
        description="Confidence score 0.0–1.0 that this is the result the user means"
    )
    reason: str = Field(description="Brief explanation of why this result was matched")


class ResolveSearchResultsSig(dspy.Signature):
    """Identify which search result(s) the user is referring to.

    You are given the user's message and a JSON list of job search results
    from the current conversation.  Determine which result(s) the user is
    talking about.

    Guidelines:
    - Match based on company name, job title, position in the list, or any
      other identifying detail the user mentions.
    - If the user says "all of them", "the top ones", etc., interpret
      accordingly.
    - Return an empty list if no results can be confidently matched.
    """

    user_message: str = dspy.InputField(desc="The user's message referencing search results")
    conversation_context: str = dspy.InputField(
        desc="Recent conversation history for additional context (may be empty)"
    )
    search_results: str = dspy.InputField(
        desc="JSON list of search results (id, company, title, url, job_fit, ...)"
    )
    resolved_results: list[ResolvedSearchResult] = dspy.OutputField(
        desc="List of matched search results with confidence scores"
    )


class SearchResultResolver(TracedModule, dspy.Module):
    """DSPy module that resolves user references to search results.

    Similar to :class:`JobResolver` but operates on the conversation's
    search results rather than the job tracker.
    """

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.resolver = dspy.ChainOfThought(ResolveSearchResultsSig)

    def forward(
        self,
        user_message: str,
        conversation_context: str,
        search_results: str,
    ) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.resolver(
                user_message=user_message,
                conversation_context=conversation_context,
                search_results=search_results,
            )

    def resolve(
        self,
        user_message: str,
        search_results: list[dict],
        conversation_context: str = "",
        min_confidence: float = 0.5,
    ) -> list[ResolvedSearchResult]:
        """Resolve user references to search results.

        Args:
            user_message: The user's latest message.
            search_results: List of search result dicts.
            conversation_context: Recent conversation history.
            min_confidence: Minimum confidence threshold for inclusion.

        Returns:
            List of :class:`ResolvedSearchResult` instances above the
            confidence threshold, sorted by confidence descending.
        """
        if not search_results:
            return []

        result = self(
            user_message=user_message,
            conversation_context=conversation_context,
            search_results=json.dumps(search_results, default=str),
        )

        resolved = [
            r for r in result.resolved_results
            if r.confidence >= min_confidence
        ]
        resolved.sort(key=lambda r: r.confidence, reverse=True)
        return resolved
