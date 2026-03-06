"""Add to Tracker workflow — promote search results to tracked jobs.

Pipeline:
1. Fetch the conversation's search results via ``list_search_results``.
2. A ``SearchResultResolver`` identifies which search results the user
   wants added to the tracker.
3. Matched results are programmatically added to the job tracker via
   ``create_job``, copying over all available fields.
4. Each search result record is updated to mark it as added and link it
   to the new tracker job so the UI can reflect the change.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow
from .resolvers import SearchResultResolver

logger = logging.getLogger(__name__)

# Fields to copy from a SearchResult dict to create_job kwargs.
# Maps search-result key → create_job parameter name.
_PROMOTABLE_FIELDS = {
    "company": "company",
    "title": "title",
    "url": "url",
    "salary_min": "salary_min",
    "salary_max": "salary_max",
    "location": "location",
    "remote_type": "remote_type",
    "source": "source",
    "requirements": "requirements",
    "nice_to_haves": "nice_to_haves",
    "job_fit": "job_fit",
}


def _promote_search_result(tools: AgentTools, sr: dict) -> dict:
    """Create a Job from a search result and link them together.

    Returns the ``create_job`` tool result dict on success, or an error
    dict on failure.
    """
    from backend.database import db
    from backend.models.search_result import SearchResult

    # Build create_job kwargs from the search result
    kwargs = {}
    for sr_key, job_key in _PROMOTABLE_FIELDS.items():
        val = sr.get(sr_key)
        if val is not None:
            kwargs[job_key] = val

    # Include fit_reason as notes
    if sr.get("fit_reason"):
        kwargs["notes"] = sr["fit_reason"]

    result = tools.execute("create_job", kwargs)

    if "error" in result:
        return result

    # Link the search result to the new job
    job_id = result["job"]["id"]
    sr_record = db.session.get(SearchResult, sr["id"])
    if sr_record:
        sr_record.added_to_tracker = True
        sr_record.tracker_job_id = job_id
        db.session.commit()

    return result


@register_workflow("add_to_tracker")
class AddToTrackerWorkflow(BaseWorkflow):
    """Identify referenced search results and add them to the job tracker."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        yield {
            "event": "text_delta",
            "data": {"content": "Identifying which jobs to add to the tracker...\n"},
        }

        # 1. Fetch search results for this conversation
        sr_response = self.tools.execute("list_search_results", {})
        if "error" in sr_response:
            yield {
                "event": "text_delta",
                "data": {"content": f"Error fetching search results: {sr_response['error']}\n"},
            }
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data=sr_response,
                summary=f"Failed to fetch search results: {sr_response['error']}",
            )

        all_results = sr_response.get("results", [])
        if not all_results:
            yield {
                "event": "text_delta",
                "data": {"content": "No search results found in this conversation to add.\n"},
            }
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No search results in conversation"},
                summary="No search results found in this conversation.",
            )

        # Filter out results already in the tracker
        available = [r for r in all_results if not r.get("added_to_tracker")]
        if not available:
            yield {
                "event": "text_delta",
                "data": {"content": "All search results have already been added to the tracker.\n"},
            }
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=True,
                data={"added": [], "already_tracked": len(all_results)},
                summary="All search results were already in the tracker.",
            )

        # 2. Resolve which results the user wants
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        resolver = SearchResultResolver(self.llm_config)
        resolved = resolver.resolve(
            user_message=user_message,
            search_results=available,
            conversation_context=conversation_context,
        )

        if not resolved:
            yield {
                "event": "text_delta",
                "data": {"content": "Couldn't determine which search results to add. Please be more specific.\n"},
            }
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "Could not resolve search results from user message"},
                summary="Could not determine which search results to add to the tracker.",
            )

        # Build a lookup for quick access
        sr_by_id = {r["id"]: r for r in available}

        # 3. Promote each resolved result
        added_jobs = []
        skipped = []

        for match in resolved:
            sr = sr_by_id.get(match.result_id)
            if sr is None:
                logger.warning(
                    "Resolved result_id %d not found in available results",
                    match.result_id,
                )
                skipped.append({"result_id": match.result_id, "reason": "not found"})
                continue

            yield {
                "event": "text_delta",
                "data": {
                    "content": f"Adding **{sr['title']}** at **{sr['company']}** to tracker...\n",
                },
            }

            result = _promote_search_result(self.tools, sr)

            if "error" in result:
                logger.error(
                    "Failed to promote search result %d: %s",
                    sr["id"],
                    result["error"],
                )
                skipped.append({
                    "result_id": sr["id"],
                    "company": sr["company"],
                    "title": sr["title"],
                    "reason": result["error"],
                })
                yield {
                    "event": "text_delta",
                    "data": {
                        "content": f"  Failed: {result['error']}\n",
                    },
                }
            else:
                job = result["job"]
                added_jobs.append(job)
                logger.info(
                    "Promoted search result %d → job %d (%s at %s)",
                    sr["id"],
                    job["id"],
                    job["title"],
                    job["company"],
                )
                yield {
                    "event": "tool_result",
                    "data": {
                        "id": f"add_to_tracker_{sr['id']}",
                        "name": "create_job",
                        "result": job,
                    },
                }

        # 4. Build summary
        if added_jobs:
            names = ", ".join(
                f"{j['title']} at {j['company']}" for j in added_jobs
            )
            summary = f"Added {len(added_jobs)} job(s) to the tracker: {names}."
        else:
            summary = "No jobs were added to the tracker."

        if skipped:
            summary += f" ({len(skipped)} skipped due to errors.)"

        yield {
            "event": "text_delta",
            "data": {"content": f"\n{summary}\n"},
        }

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=len(added_jobs) > 0,
            data={
                "added_jobs": added_jobs,
                "skipped": skipped,
                "count": len(added_jobs),
            },
            summary=summary,
        )
