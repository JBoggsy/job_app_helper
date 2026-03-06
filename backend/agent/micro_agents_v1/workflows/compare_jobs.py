"""Compare Jobs workflow — side-by-side comparison of multiple jobs.

Pipeline:
1. A ``JobResolver`` (and/or ``SearchResultResolver``) identifies which
   jobs/results the user wants to compare.
2. Data for each job is gathered from tracker records and search results.
3. A DSPy module generates a structured comparison covering:
   compensation, location/remote, requirements overlap with user
   profile, fit scores, pros/cons for each position.
4. The comparison is streamed to the user as formatted markdown.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator

import dspy
from pydantic import BaseModel, Field

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow
from .resolvers import JobResolver, SearchResultResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signature
# ---------------------------------------------------------------------------


class JobComparison(BaseModel):
    """Comparison entry for a single job."""

    label: str = Field(description="Short label: 'Title at Company'")
    compensation: str = Field(description="Salary range summary or 'Not specified'")
    location_and_remote: str = Field(description="Location and remote-type summary")
    fit_score: str = Field(description="Fit score (0-5) or 'N/A' if unavailable")
    strengths: list[str] = Field(description="2-4 key strengths / pros")
    weaknesses: list[str] = Field(description="1-3 key weaknesses / cons")
    requirements_match: str = Field(
        description="Brief assessment of how well the user's profile matches this job's requirements"
    )


class CompareJobsSig(dspy.Signature):
    """Compare multiple jobs side-by-side for a job seeker.

    You are given JSON data for 2 or more jobs and the user's profile.
    Produce a structured comparison for each job plus an overall
    recommendation.

    Guidelines:
    - Be concise but specific — cite actual salary numbers, locations,
      and requirement keywords rather than generic statements.
    - Strengths/weaknesses should be relative to the user's profile and
      preferences (location, salary, remote work, skills).
    - The recommendation should clearly state which job(s) are the best
      fit and why, acknowledging trade-offs.
    """

    jobs_data: str = dspy.InputField(
        desc="JSON list of job objects to compare (tracker and/or search result data)"
    )
    user_profile: str = dspy.InputField(
        desc="The user's job search profile (may be empty)"
    )
    user_message: str = dspy.InputField(
        desc="The user's original comparison request for context"
    )
    comparisons: list[JobComparison] = dspy.OutputField(
        desc="One structured comparison per job"
    )
    recommendation: str = dspy.OutputField(
        desc="Overall recommendation: which job(s) are the best fit and why"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("compare_jobs")
class CompareJobsWorkflow(BaseWorkflow):
    """Compare multiple jobs or search results side-by-side."""

    def _configure_lm(self) -> dspy.LM:
        kwargs: dict = {}
        if self.llm_config.api_key:
            kwargs["api_key"] = self.llm_config.api_key
        if self.llm_config.api_base:
            kwargs["api_base"] = self.llm_config.api_base
        return dspy.LM(
            model=self.llm_config.model,
            max_tokens=self.llm_config.max_tokens,
            **kwargs,
        )

    def _gather_jobs(
        self, user_message: str, conversation_context: str,
    ) -> Generator[dict, None, list[dict]]:
        """Resolve jobs from both tracker and search results.

        Returns a unified list of job-data dicts (with a ``_source``
        field indicating ``"tracker"`` or ``"search_result"``).
        """
        yield {
            "event": "text_delta",
            "data": {"content": "Identifying which jobs to compare...\n"},
        }

        collected: list[dict] = []
        seen_keys: set[tuple] = set()  # (company_lower, title_lower) for dedup

        # --- Tracker jobs ---
        jobs_resp = self.tools.execute("list_jobs", {"limit": 50})
        tracker_jobs = jobs_resp.get("jobs", []) if "error" not in jobs_resp else []

        if tracker_jobs:
            resolver = JobResolver(self.llm_config)
            resolved = resolver.resolve(
                user_message=user_message,
                jobs=tracker_jobs,
                conversation_context=conversation_context,
                min_confidence=0.4,
            )
            job_by_id = {j["id"]: j for j in tracker_jobs}
            for match in resolved:
                job = job_by_id.get(match.job_id)
                if job:
                    key = (job["company"].lower(), job["title"].lower())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        collected.append({**job, "_source": "tracker"})

        # --- Search results ---
        sr_resp = self.tools.execute("list_search_results", {})
        search_results = sr_resp.get("results", []) if "error" not in sr_resp else []

        if search_results:
            resolver = SearchResultResolver(self.llm_config)
            resolved = resolver.resolve(
                user_message=user_message,
                search_results=search_results,
                conversation_context=conversation_context,
                min_confidence=0.4,
            )
            sr_by_id = {r["id"]: r for r in search_results}
            for match in resolved:
                sr = sr_by_id.get(match.result_id)
                if sr:
                    key = (sr["company"].lower(), sr["title"].lower())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        collected.append({**sr, "_source": "search_result"})

        return collected

    def run(self) -> Generator[dict, None, WorkflowResult]:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Gather jobs to compare
        jobs_to_compare = yield from self._gather_jobs(user_message, conversation_context)

        if len(jobs_to_compare) < 2:
            msg = (
                "Need at least 2 jobs to compare, but "
                + (f"only found {len(jobs_to_compare)}." if jobs_to_compare else "found none.")
                + " Please specify which jobs you'd like to compare.\n"
            )
            yield {"event": "text_delta", "data": {"content": msg}}
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "Not enough jobs to compare", "found": len(jobs_to_compare)},
                summary=msg.strip(),
            )

        labels = [f"{j['title']} at {j['company']}" for j in jobs_to_compare]
        yield {
            "event": "text_delta",
            "data": {"content": f"Comparing {len(jobs_to_compare)} jobs: {', '.join(labels)}...\n\n"},
        }

        # 2. Load user profile
        profile_resp = self.tools.execute("read_user_profile", {})
        user_profile = profile_resp.get("content", "")

        # 3. Run comparison
        lm = self._configure_lm()
        comparator = dspy.ChainOfThought(CompareJobsSig)

        with dspy.context(lm=lm):
            result = comparator(
                jobs_data=json.dumps(jobs_to_compare, default=str),
                user_profile=user_profile,
                user_message=user_message,
            )

        # 4. Format and stream the comparison
        for comp in result.comparisons:
            yield {
                "event": "text_delta",
                "data": {"content": f"### {comp.label}\n"},
            }
            yield {
                "event": "text_delta",
                "data": {"content": (
                    f"- **Compensation:** {comp.compensation}\n"
                    f"- **Location:** {comp.location_and_remote}\n"
                    f"- **Fit Score:** {comp.fit_score}\n"
                    f"- **Requirements Match:** {comp.requirements_match}\n"
                )},
            }
            if comp.strengths:
                yield {
                    "event": "text_delta",
                    "data": {"content": "- **Strengths:** " + "; ".join(comp.strengths) + "\n"},
                }
            if comp.weaknesses:
                yield {
                    "event": "text_delta",
                    "data": {"content": "- **Weaknesses:** " + "; ".join(comp.weaknesses) + "\n"},
                }
            yield {"event": "text_delta", "data": {"content": "\n"}}

        # Recommendation
        yield {
            "event": "text_delta",
            "data": {"content": f"### Recommendation\n{result.recommendation}\n"},
        }

        summary = f"Compared {len(jobs_to_compare)} jobs. {result.recommendation}"

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "jobs_compared": labels,
                "comparisons": [c.model_dump() for c in result.comparisons],
                "recommendation": result.recommendation,
            },
            summary=summary,
        )
