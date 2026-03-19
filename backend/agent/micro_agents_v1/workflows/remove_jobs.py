"""Remove Jobs workflow — delete jobs from the tracker.

Pipeline:
1. A ``JobResolver`` identifies which job(s) in the tracker the user
   wants to remove.
2. Matched jobs are programmatically deleted via ``remove_job``.
"""

from __future__ import annotations

import logging

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .registry import BaseWorkflow, WorkflowResult, register_workflow
from .resolvers import JobResolver

logger = logging.getLogger(__name__)


@register_workflow("remove_jobs")
class RemoveJobsWorkflow(BaseWorkflow):
    """Delete one or more jobs from the user's tracked jobs list — use when the user wants to remove, delete, or discard tracked jobs."""

    OUTPUTS = {
        "removed_jobs": "list[dict] — each with job_id, company, title",
        "failed": "list[dict] — removals that failed",
        "count": "int — number successfully removed",
    }

    def run(self) -> WorkflowResult:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Fetch tracker jobs
        self.event_bus.emit("text_delta", {"content": "Identifying which job(s) to remove...\n"})

        jobs_resp = self.tools.execute("list_jobs", {"limit": 50})
        if "error" in jobs_resp:
            self.event_bus.emit("text_delta", {"content": f"Error fetching jobs: {jobs_resp['error']}\n"})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data=jobs_resp,
                summary=f"Failed to fetch jobs: {jobs_resp['error']}",
            )

        tracker_jobs = jobs_resp.get("jobs", [])
        if not tracker_jobs:
            self.event_bus.emit("text_delta", {"content": "No jobs in the tracker to remove.\n"})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No jobs in tracker"},
                summary="No jobs in the tracker.",
            )

        # 2. Resolve which jobs to remove
        resolver = JobResolver(self.llm_config)
        resolved = resolver.resolve(
            user_message=user_message,
            jobs=tracker_jobs,
            conversation_context=conversation_context,
        )

        if not resolved:
            msg = "Couldn't determine which job(s) to remove. Please be more specific.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "Could not resolve jobs to remove"},
                summary=msg.strip(),
            )

        job_by_id = {j["id"]: j for j in tracker_jobs}

        # 3. Remove each matched job
        removed = []
        failed = []

        for match in resolved:
            job = job_by_id.get(match.job_id)
            if job is None:
                failed.append({"job_id": match.job_id, "reason": "not found"})
                continue

            job_label = f"{job['title']} at {job['company']}"
            self.event_bus.emit("text_delta", {"content": f"Removing **{job_label}**...\n"})

            result = self.tools.execute("remove_job", {"job_id": job["id"]})

            if "error" in result:
                logger.error("Failed to remove job %d: %s", job["id"], result["error"])
                failed.append({"job_id": job["id"], "label": job_label, "reason": result["error"]})
                self.event_bus.emit("text_delta", {"content": f"  Failed: {result['error']}\n"})
            else:
                removed.append(job)
                logger.info("Removed job %d: %s", job["id"], job_label)

        # 4. Summary
        if removed:
            names = ", ".join(f"{j['title']} at {j['company']}" for j in removed)
            summary = f"Removed {len(removed)} job(s): {names}."
        else:
            summary = "No jobs were removed."

        if failed:
            summary += f" ({len(failed)} failed.)"

        self.event_bus.emit("text_delta", {"content": f"\n{summary}\n"})

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=len(removed) > 0,
            data={
                "removed_jobs": removed,
                "failed": failed,
                "count": len(removed),
            },
            summary=summary,
        )
