"""Update Profile workflow — interactively update the user's profile.

Pipeline:
1. The current user profile is loaded via ``read_user_profile``.
2. A DSPy module analyses the user's message and current profile to
   determine which sections need updating and what the new content
   should be.
3. Changes are applied via ``update_user_profile`` with section-level
   updates to preserve unrelated sections.
4. The updated profile is returned for confirmation.
"""

from __future__ import annotations

import logging
from typing import Optional

import dspy
from pydantic import BaseModel, Field

from backend.agent.user_profile import PROFILE_SECTIONS
from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_lm
from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signatures
# ---------------------------------------------------------------------------


class ProfileSectionUpdate(BaseModel):
    """An update to a single profile section."""

    section: str = Field(
        description=(
            "The profile section to update. One of: Summary, Education, "
            "Work Experience, Skills & Expertise, Fields of Interest, "
            "Salary Preferences, Location Preferences, Remote Work Preferences, "
            "Job Search Goals, Other Notes"
        )
    )
    new_content: str = Field(
        description=(
            "The complete new markdown content for this section. Must include "
            "ALL existing information that should be kept, plus the changes. "
            "Do not omit existing content unless the user asked to remove it."
        )
    )
    change_summary: str = Field(
        description="Brief description of what was changed in this section"
    )


class ExtractProfileUpdatesSig(dspy.Signature):
    """Determine what profile changes the user wants.

    Given the user's message, their current profile content, and
    optionally their resume data, determine which profile sections need
    updating and produce the new content for each.

    Guidelines:
    - Only update sections that the user's message relates to.
    - Preserve ALL existing content in a section unless the user
      explicitly asks to remove or replace something.
    - Merge new information with existing content naturally — don't
      duplicate items already present.
    - Use clean markdown formatting consistent with the existing style.
    - For salary/location/remote preferences, use the same format as
      existing entries.
    """

    user_message: str = dspy.InputField(
        desc="The user's request describing profile changes"
    )
    current_profile: str = dspy.InputField(
        desc="The full current profile markdown content"
    )
    resume_data: str = dspy.InputField(
        desc="User's resume data for reference (may be empty)"
    )
    updates: list[ProfileSectionUpdate] = dspy.OutputField(
        desc="List of section updates to apply"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("update_profile")
class UpdateProfileWorkflow(BaseWorkflow):
    """Update the user's job-search profile with new preferences, skills, experience, or goals — use when the user shares personal info that should be remembered."""

    OUTPUTS = {
        "applied": "list[str] — section names that were updated",
        "failed": "list[str] — sections that failed to update",
        "count": "int — number of sections successfully updated",
    }

    def run(self) -> WorkflowResult:
        user_message = self.outcome_description or self.params.get("user_message", "")

        # 1. Load current profile
        self.event_bus.emit("text_delta", {"content": "Reading your current profile...\n"})

        profile_resp = self.tools.execute("read_user_profile", {})
        current_profile = profile_resp.get("content", "")

        # Optionally load resume for context
        resume_resp = self.tools.execute("read_resume", {})
        resume_data = ""
        if "error" not in resume_resp:
            if resume_resp.get("parsed"):
                import json
                resume_data = json.dumps(resume_resp["parsed"], default=str)
            elif resume_resp.get("text"):
                resume_data = resume_resp["text"]

        # 2. Extract updates
        self.event_bus.emit("text_delta", {"content": "Determining what to update...\n"})

        extractor = dspy.ChainOfThought(ExtractProfileUpdatesSig)

        with dspy.context(lm=build_lm(self.llm_config)):
            result = extractor(
                user_message=user_message,
                current_profile=current_profile,
                resume_data=resume_data,
            )

        if not result.updates:
            msg = "Couldn't determine what profile changes to make. Please be more specific.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No profile updates extracted"},
                summary=msg.strip(),
            )

        # 3. Apply section-level updates
        applied = []
        failed = []

        for update in result.updates:
            section = update.section
            # Validate section name
            if section not in PROFILE_SECTIONS:
                logger.warning("Unknown profile section %r, skipping", section)
                failed.append({"section": section, "reason": "unknown section"})
                continue

            self.event_bus.emit("text_delta", {
                "content": f"Updating **{section}**: {update.change_summary}\n",
            })

            resp = self.tools.execute("update_user_profile", {
                "section": section,
                "content": update.new_content,
            })

            if "error" in resp:
                logger.error("Failed to update section %s: %s", section, resp["error"])
                failed.append({"section": section, "reason": resp["error"]})
                self.event_bus.emit("text_delta", {"content": f"  Failed: {resp['error']}\n"})
            else:
                applied.append({
                    "section": section,
                    "change": update.change_summary,
                })

        # 4. Summary
        if applied:
            sections_list = ", ".join(a["section"] for a in applied)
            summary = f"Updated {len(applied)} profile section(s): {sections_list}."
        else:
            summary = "No profile sections were updated."

        if failed:
            summary += f" ({len(failed)} failed.)"

        self.event_bus.emit("text_delta", {"content": f"\n{summary}\n"})

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=len(applied) > 0,
            data={
                "applied": applied,
                "failed": failed,
                "count": len(applied),
            },
            summary=summary,
        )
