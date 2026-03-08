"""Edit Job workflow — modify a tracked job's fields.

Pipeline:
1. A ``JobResolver`` identifies which job in the tracker the user is
   referring to.
2. A DSPy module extracts the fields to be modified and their new values
   from the user's request.
3. The job is programmatically updated via ``edit_job``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from typing import Optional

import dspy
from pydantic import BaseModel, Field

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_lm
from .registry import BaseWorkflow, WorkflowResult, register_workflow
from .resolvers import JobResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signature
# ---------------------------------------------------------------------------

VALID_STATUSES = ["saved", "applied", "interviewing", "offer", "rejected"]
VALID_REMOTE_TYPES = ["onsite", "hybrid", "remote"]


class JobFieldUpdate(BaseModel):
    """A single field update to apply to a job."""

    field: str = Field(
        description=(
            "The job field to update. One of: company, title, url, status, "
            "notes, salary_min, salary_max, location, remote_type, tags, "
            "contact_name, contact_email, source, job_fit, requirements, "
            "nice_to_haves"
        )
    )
    value: str = Field(
        description=(
            "The new value for the field. Use the appropriate type: "
            "string for text fields, integer-as-string for salary/job_fit, "
            "one of [saved, applied, interviewing, offer, rejected] for status, "
            "one of [onsite, hybrid, remote] for remote_type."
        )
    )


class ExtractJobEditsSig(dspy.Signature):
    """Extract job field updates from the user's message.

    Given the user's request and the current state of a job, determine
    which fields should be changed and to what values.

    Guidelines:
    - Only include fields the user explicitly or implicitly wants changed.
    - For status changes, map natural language to valid statuses:
      saved, applied, interviewing, offer, rejected.
    - For remote_type, map to: onsite, hybrid, remote.
    - For salary fields, extract numeric values (salary_min, salary_max).
    - For job_fit, use an integer 0-5.
    - Preserve existing data — only change what the user asks for.
    """

    user_message: str = dspy.InputField(desc="The user's edit request")
    current_job: str = dspy.InputField(
        desc="JSON of the current job record being edited"
    )
    updates: list[JobFieldUpdate] = dspy.OutputField(
        desc="List of field updates to apply"
    )


# Integer fields that need type coercion
_INT_FIELDS = {"salary_min", "salary_max", "job_fit"}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("edit_job")
class EditJobWorkflow(BaseWorkflow):
    """Identify referenced job, extract field updates, and apply them."""

    def run(self) -> Generator[dict, None, WorkflowResult]:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Resolve the target job
        yield {
            "event": "text_delta",
            "data": {"content": "Identifying which job to edit...\n"},
        }

        job_id = self.params.get("job_id")
        job = None

        jobs_resp = self.tools.execute("list_jobs", {"limit": 50})
        tracker_jobs = jobs_resp.get("jobs", []) if "error" not in jobs_resp else []

        if job_id:
            for j in tracker_jobs:
                if j["id"] == int(job_id):
                    job = j
                    break

        if job is None and tracker_jobs:
            resolver = JobResolver(self.llm_config)
            resolved = resolver.resolve(
                user_message=user_message,
                jobs=tracker_jobs,
                conversation_context=conversation_context,
            )
            if resolved:
                for j in tracker_jobs:
                    if j["id"] == resolved[0].job_id:
                        job = j
                        break

        if job is None:
            msg = "Couldn't determine which job to edit. Please be more specific.\n"
            yield {"event": "text_delta", "data": {"content": msg}}
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "Could not resolve target job"},
                summary=msg.strip(),
            )

        job_label = f"{job['title']} at {job['company']}"
        yield {
            "event": "text_delta",
            "data": {"content": f"Editing **{job_label}**...\n"},
        }

        # 2. Extract field updates
        extractor = dspy.ChainOfThought(ExtractJobEditsSig)

        with dspy.context(lm=build_lm(self.llm_config)):
            result = extractor(
                user_message=user_message,
                current_job=json.dumps(job, default=str),
            )

        if not result.updates:
            msg = "Couldn't determine what changes to make. Please be more specific.\n"
            yield {"event": "text_delta", "data": {"content": msg}}
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No field updates extracted", "job": job},
                summary=msg.strip(),
            )

        # 3. Build edit_job kwargs and apply
        edit_kwargs: dict = {"job_id": job["id"]}
        for update in result.updates:
            field = update.field.strip()
            value = update.value
            # Coerce integer fields
            if field in _INT_FIELDS:
                try:
                    value = int(float(value))
                except (ValueError, TypeError):
                    logger.warning("Could not coerce %s=%r to int, skipping", field, value)
                    continue
            edit_kwargs[field] = value

        edit_result = self.tools.execute("edit_job", edit_kwargs)

        if "error" in edit_result:
            yield {
                "event": "text_delta",
                "data": {"content": f"Error: {edit_result['error']}\n"},
            }
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": edit_result["error"], "job": job},
                summary=f"Failed to edit {job_label}: {edit_result['error']}",
            )

        updated_job = edit_result.get("job", {})
        changed_fields = edit_result.get("updated_fields", list(edit_kwargs.keys()))

        yield {
            "event": "tool_result",
            "data": {
                "id": f"edit_job_{job['id']}",
                "name": "edit_job",
                "result": updated_job,
            },
        }

        changes_desc = ", ".join(
            f"{u.field} → {u.value}" for u in result.updates
        )
        summary = f"Updated {job_label}: {changes_desc}."

        yield {
            "event": "text_delta",
            "data": {"content": f"\n{summary}\n"},
        }

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "job": updated_job,
                "changes": [u.model_dump() for u in result.updates],
            },
            summary=summary,
        )
