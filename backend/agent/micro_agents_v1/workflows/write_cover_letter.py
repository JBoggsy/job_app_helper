"""Write Cover Letter workflow — structured single-shot letter generation.

Pipeline:
1. A ``JobResolver`` identifies which tracked job the user is referring to.
2. The user's profile, resume, and the target job's details are loaded.
3. An outline step proposes the overall letter structure, section-specific
    points to hit based on user/job matches, and a short narrative thread.
4. First drafts for each section are generated in parallel using the outline
    and narrative, then assembled in the correct order into a rough draft.
5. A unification pass smooths transitions and continuity between sections.
6. A polish pass edits for spelling, grammar, and style.
7. The final cover letter is presented with a concise summary of key points.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging

import dspy
from pydantic import BaseModel, Field

from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_lm, load_job_context, load_user_context
from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signatures
# ---------------------------------------------------------------------------


class CoverLetterSectionPlan(BaseModel):
    """Plan for one section of the cover letter."""

    title: str = Field(description="Section heading or label")
    purpose: str = Field(description="What this section should accomplish")
    key_points: list[str] = Field(
        description="Specific points this section should cover"
    )


class GenerateOutlineSig(dspy.Signature):
    """Create a high-level outline and narrative for a tailored cover letter.

    Use the job details plus the candidate's profile/resume to propose:
    1. A concise narrative thread that ties the letter together.
    2. Ordered sections with clear purpose and concrete key points.
    3. Key match points that should stand out to the hiring manager.
    """

    user_message: str = dspy.InputField(
        desc="The user's original request/context for this letter"
    )
    job_context: str = dspy.InputField(desc="Target job details")
    user_context: str = dspy.InputField(desc="User profile and resume context")

    narrative: str = dspy.OutputField(
        desc="A short narrative thread for the letter (2-4 sentences)"
    )
    sections: list[CoverLetterSectionPlan] = dspy.OutputField(
        desc="Ordered section plan for the cover letter"
    )
    key_match_points: list[str] = dspy.OutputField(
        desc="Top user-job match points that should be highlighted"
    )


class DraftSectionSig(dspy.Signature):
    """Draft one section of a cover letter from an outline section.

    The section should align with the provided narrative and preserve a
    professional, specific, and human tone.
    """

    section_title: str = dspy.InputField(desc="Section label/title")
    section_purpose: str = dspy.InputField(desc="Goal of this section")
    section_key_points: str = dspy.InputField(
        desc="Line-delimited key points that must be included"
    )
    narrative: str = dspy.InputField(desc="Overall narrative thread")
    job_context: str = dspy.InputField(desc="Target job details")
    user_context: str = dspy.InputField(desc="User profile and resume context")
    user_message: str = dspy.InputField(
        desc="Original user request for style and constraints"
    )

    section_draft: str = dspy.OutputField(
        desc="Drafted prose for this section only"
    )


class UnifyDraftSig(dspy.Signature):
    """Merge section drafts into a coherent cover letter draft.

    Ensure transitions are smooth, the logic flows naturally, and the
    narrative thread remains consistent across sections.
    """

    narrative: str = dspy.InputField(desc="Overall narrative thread")
    outline_json: str = dspy.InputField(desc="JSON outline with section order")
    section_drafts_json: str = dspy.InputField(
        desc="JSON list of drafted sections in order"
    )
    user_message: str = dspy.InputField(desc="Original user request")

    unified_draft: str = dspy.OutputField(
        desc="Complete unified cover letter draft"
    )
    transition_notes: list[str] = dspy.OutputField(
        desc="Brief notes on continuity and transitions improved"
    )


class PolishLetterSig(dspy.Signature):
    """Polish a unified cover letter draft for grammar, style, and clarity.

    Keep the candidate voice intact while improving readability,
    correctness, and professional tone.
    """

    draft: str = dspy.InputField(desc="Unified draft of the cover letter")
    job_context: str = dspy.InputField(desc="Target job details")
    user_message: str = dspy.InputField(desc="Original user request/context")

    final_cover_letter: str = dspy.OutputField(
        desc="Final polished cover letter ready to send"
    )
    key_points_summary: list[str] = dspy.OutputField(
        desc="Key points successfully highlighted in the final letter"
    )
    edit_summary: str = dspy.OutputField(
        desc="One-sentence summary of polish/editing changes"
    )


@register_workflow("write_cover_letter")
class WriteCoverLetterWorkflow(BaseWorkflow):
    """Structured single-shot cover letter drafting for a target job."""

    OUTPUTS = {
        "cover_letter": "str — the final cover letter text",
        "job": "dict — the target job record",
        "outline": "dict — structure and narrative plan used for drafting",
        "key_points": "list[str] — main selling points highlighted in the letter",
    }

    # -- Helpers ------------------------------------------------------------

    # Job/user context loading delegated to shared helpers in _dspy_utils.py.

    @staticmethod
    def _default_sections(job: dict) -> list[CoverLetterSectionPlan]:
        """Fallback section plan if the outliner does not return one."""
        return [
            CoverLetterSectionPlan(
                title="Opening",
                purpose="Open with role intent and motivation",
                key_points=[
                    f"Apply for {job['title']} at {job['company']}",
                    "Concise hook for why this role is compelling",
                ],
            ),
            CoverLetterSectionPlan(
                title="Role Fit",
                purpose="Show match between experience and requirements",
                key_points=[
                    "Map prior experience to core requirements",
                    "Provide at least one specific, credible example",
                ],
            ),
            CoverLetterSectionPlan(
                title="Company Connection",
                purpose="Explain why this company/team is a strong fit",
                key_points=[
                    "Reference company mission/product/team context",
                    "Show how candidate strengths will add value",
                ],
            ),
            CoverLetterSectionPlan(
                title="Closing",
                purpose="Close confidently with a clear call to action",
                key_points=[
                    "Express enthusiasm and readiness to discuss",
                    "Professional sign-off",
                ],
            ),
        ]

    def _draft_section(
        self,
        lm: dspy.LM,
        section: CoverLetterSectionPlan,
        narrative: str,
        job_context: str,
        user_context: str,
        user_message: str,
    ) -> str:
        """Draft one cover letter section."""
        drafter = dspy.ChainOfThought(DraftSectionSig)
        with dspy.context(lm=lm):
            result = drafter(
                section_title=section.title,
                section_purpose=section.purpose,
                section_key_points="\n".join(section.key_points),
                narrative=narrative,
                job_context=job_context,
                user_context=user_context,
                user_message=user_message,
            )
        return result.section_draft

    def run(self) -> WorkflowResult:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Resolve the target job (required)
        job, job_context = load_job_context(
            self.tools, self.params, self.llm_config,
            user_message, conversation_context,
        )
        if not job:
            msg = "I need to know which job to target for this cover letter. Please specify the job.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No job resolved"},
                summary=msg.strip(),
            )

        job_label = f"{job['title']} at {job['company']}"
        self.event_bus.emit("text_delta", {"content": f"Targeting: **{job_label}**\n\n"})

        # 2. Load user context
        self.event_bus.emit("text_delta", {"content": "Loading your profile and resume context...\n"})
        user_context = load_user_context(self.tools)

        lm = build_lm(self.llm_config)

        # 3. Generate outline + narrative
        self.event_bus.emit("text_delta", {"content": "Generating outline and narrative...\n"})

        outliner = dspy.ChainOfThought(GenerateOutlineSig)
        with dspy.context(lm=lm):
            outline = outliner(
                user_message=user_message,
                job_context=job_context,
                user_context=user_context,
            )

        sections = list(outline.sections) if outline.sections else self._default_sections(job)
        narrative = outline.narrative.strip() if outline.narrative else ""
        key_match_points = list(outline.key_match_points) if outline.key_match_points else []

        outline_lines = ["## Letter Plan", ""]
        if narrative:
            outline_lines.append(f"**Narrative:** {narrative}")
            outline_lines.append("")

        for idx, section in enumerate(sections, start=1):
            points = "; ".join(section.key_points[:4]) if section.key_points else "No points provided"
            outline_lines.append(
                f"{idx}. **{section.title}** - {section.purpose}"
            )
            outline_lines.append(f"   Focus: {points}")

        outline_lines.append("")
        self.event_bus.emit("text_delta", {"content": "\n".join(outline_lines) + "\n"})

        # 4. Draft sections in parallel and assemble rough draft
        self.event_bus.emit("text_delta", {"content": "Drafting sections in parallel...\n"})

        section_drafts: dict[int, str] = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, max(1, len(sections)))
        ) as pool:
            futures: dict[concurrent.futures.Future, tuple[int, str]] = {
                pool.submit(
                    self._draft_section,
                    lm,
                    section,
                    narrative,
                    job_context,
                    user_context,
                    user_message,
                ): (idx, section.title)
                for idx, section in enumerate(sections)
            }

            for future in concurrent.futures.as_completed(futures):
                idx, title = futures[future]
                exc = future.exception()
                if exc:
                    logger.warning("Section drafting failed for '%s': %s", title, exc)
                    fallback = " ".join(sections[idx].key_points).strip()
                    section_drafts[idx] = fallback or f"[{title}]"
                else:
                    section_drafts[idx] = future.result().strip()

                self.event_bus.emit("text_delta", {"content": f"  drafted: {title}\n"})

        ordered_drafts = [section_drafts[i] for i in range(len(sections)) if section_drafts.get(i)]
        rough_draft = "\n\n".join(ordered_drafts).strip()

        if not rough_draft:
            msg = "I couldn't produce a usable draft for that job. Please try again.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "Failed to draft sections"},
                summary=msg.strip(),
            )

        # 5. Unify continuity and transitions
        self.event_bus.emit("text_delta", {"content": "Unifying draft for continuity...\n"})

        unifier = dspy.ChainOfThought(UnifyDraftSig)
        with dspy.context(lm=lm):
            unified = unifier(
                narrative=narrative,
                outline_json=json.dumps(
                    [s.model_dump() for s in sections], default=str,
                ),
                section_drafts_json=json.dumps(ordered_drafts, default=str),
                user_message=user_message,
            )

        unified_draft = unified.unified_draft.strip() if unified.unified_draft else rough_draft

        # 6. Polish grammar, spelling, and style
        self.event_bus.emit("text_delta", {"content": "Polishing grammar and style...\n\n"})

        polisher = dspy.ChainOfThought(PolishLetterSig)
        with dspy.context(lm=lm):
            polished = polisher(
                draft=unified_draft,
                job_context=job_context,
                user_message=user_message,
            )

        final_letter = polished.final_cover_letter.strip() if polished.final_cover_letter else unified_draft
        key_points = list(polished.key_points_summary) if polished.key_points_summary else key_match_points
        edit_summary = polished.edit_summary.strip() if polished.edit_summary else "Polished for clarity, grammar, and flow."

        # 7. Save + present final letter and key points
        save_resp = self.tools.execute("save_job_document", {
            "job_id": job["id"],
            "doc_type": "cover_letter",
            "content": final_letter,
            "edit_summary": edit_summary,
        })

        version_info = ""
        save_note = ""
        if "error" not in save_resp:
            version_info = f" (saved as v{save_resp['document']['version']})"
        else:
            save_note = f"\n\n_Note: unable to save this version ({save_resp['error']})._"

        points_text = (
            "\n".join(f"- {point}" for point in key_points)
            if key_points
            else "- Tailored to the role requirements and your background."
        )

        self.event_bus.emit("text_delta", {
            "content": (
                f"---\n\n"
                f"## Final Cover Letter{version_info}\n\n"
                f"{final_letter}\n\n"
                f"---\n\n"
                f"### Key Points Highlighted\n\n"
                f"{points_text}\n\n"
                f"*{edit_summary}*"
                f"{save_note}\n"
            ),
        })

        summary = f"Wrote cover letter for {job_label}{version_info}."
        if save_note:
            summary += " Draft generated but not saved."

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "cover_letter": final_letter,
                "job": job,
                "outline": {
                    "narrative": narrative,
                    "sections": [s.model_dump() for s in sections],
                },
                "key_points": key_points,
                "version_info": version_info,
            },
            summary=summary,
        )
