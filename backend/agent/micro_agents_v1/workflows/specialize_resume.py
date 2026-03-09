"""Specialize Resume workflow — tailor the user's resume for a specific job.

Pipeline:
1. A ``JobResolver`` identifies which tracked job the user is referring to.
2. The user's profile, their current resume, and the target job's details
   are loaded.  If a job-specific resume version already exists in the DB
   (via ``get_job_document``), that version is used as the starting point
   instead of the base resume.
3. Each section of the resume is evaluated independently against the user
   profile and job description.  A per-section critique provides concrete,
   actionable feedback (skills to highlight, experience to reorder or
   expand, language to align with the posting, content to trim, etc.).
4. The feedback from the previous step is applied to each section,
   producing revised drafts.
5. A unification and editing pass ensures the full resume reads
   coherently — no logical gaps, structural inconsistencies, or
   grammatical errors introduced during per-section revision.
6. A validation pass cross-checks every claim and data point in the
   resume against the user profile and the original request.  This step
   is critical: hallucinated or embellished claims could lead the user
   to unknowingly misrepresent themselves to potential employers.
7. The final specialised resume is saved as a versioned job document and
   presented with a concise summary of the changes made.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import dspy

from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_lm, load_job_context, load_user_context
from .registry import BaseWorkflow, WorkflowResult, register_workflow
from ..resume_stages import ResumeSection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signatures
# ---------------------------------------------------------------------------


class IdentifySectionsSig(dspy.Signature):
    """Parse a resume into its logical sections.

    Return every section with its heading and full content.  Preserve the
    original text exactly — do not edit or summarise.
    """

    resume_text: str = dspy.InputField(desc="The full resume text")

    sections: list[ResumeSection] = dspy.OutputField(
        desc="Ordered list of resume sections with their headings and content"
    )


class CritiqueSectionSig(dspy.Signature):
    """Evaluate one resume section against a job description and user profile.

    Provide concrete, actionable feedback: what to highlight, reorder,
    expand, trim, or rephrase so the section better targets the role.
    Do NOT fabricate experience or skills the user does not have.
    """

    section_title: str = dspy.InputField(desc="Section heading")
    section_content: str = dspy.InputField(desc="Current section text")
    job_context: str = dspy.InputField(desc="Target job details and requirements")
    user_context: str = dspy.InputField(desc="User profile and master resume")
    user_message: str = dspy.InputField(desc="Original user request for context")

    feedback: list[str] = dspy.OutputField(
        desc="Ordered list of actionable suggestions for this section (highest impact first)"
    )
    priority: str = dspy.OutputField(
        desc="One of 'high', 'medium', or 'low' — how much this section needs revision"
    )


class ReviseSectionSig(dspy.Signature):
    """Apply critique feedback to produce a revised resume section.

    Rules:
    - Apply the actionable suggestions faithfully.
    - Preserve the candidate's authentic voice and factual claims.
    - Do NOT invent experience, skills, or accomplishments.
    - Keep formatting consistent with the original section style.
    """

    section_title: str = dspy.InputField(desc="Section heading")
    section_content: str = dspy.InputField(desc="Current section text")
    feedback: str = dspy.InputField(desc="Line-delimited actionable feedback to apply")
    job_context: str = dspy.InputField(desc="Target job details")
    user_context: str = dspy.InputField(desc="User profile and master resume")

    revised_content: str = dspy.OutputField(
        desc="The revised section text with feedback applied"
    )
    changes_made: list[str] = dspy.OutputField(
        desc="Brief list of changes applied to this section"
    )


class UnifyResumeSig(dspy.Signature):
    """Merge revised sections into a coherent, polished resume.

    Ensure consistent formatting, smooth transitions between sections,
    no logical gaps, and no grammatical or structural errors.  The result
    must read as a single well-structured document, not a patchwork.
    """

    sections_json: str = dspy.InputField(
        desc="JSON list of {title, content} for each revised section, in order"
    )
    job_context: str = dspy.InputField(desc="Target job details")
    user_message: str = dspy.InputField(desc="Original user request")

    unified_resume: str = dspy.OutputField(
        desc="Complete unified resume text, ready to use"
    )
    editing_notes: list[str] = dspy.OutputField(
        desc="Brief notes on structural or grammatical fixes applied during unification"
    )


class ValidateClaimsSig(dspy.Signature):
    """Cross-check every claim in a resume against the user's profile and request.

    This is a safety-critical step.  Hallucinated or embellished claims
    could cause the user to unknowingly misrepresent themselves.

    For each claim, verify it is supported by the user profile, the
    original resume, or the user's explicit request.  Flag anything
    that cannot be verified.
    """

    resume: str = dspy.InputField(desc="The specialised resume to validate")
    user_context: str = dspy.InputField(
        desc="User profile and original/master resume — the source of truth"
    )
    user_message: str = dspy.InputField(
        desc="The user's original request (may contain explicit instructions)"
    )

    verified_claims: list[str] = dspy.OutputField(
        desc="Claims that are supported by the user profile or original resume"
    )
    flagged_claims: list[str] = dspy.OutputField(
        desc="Claims that could NOT be verified — potential hallucinations or embellishments"
    )
    validation_passed: bool = dspy.OutputField(
        desc="True if no flagged claims were found, False otherwise"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("specialize_resume")
class SpecializeResumeWorkflow(BaseWorkflow):
    """Structured single-shot resume specialisation for a target job."""

    OUTPUTS = {
        "resume": "str — the full specialised resume text",
        "job": "dict — the target job record",
        "changes": "list[str] — per-section change descriptions",
        "flagged_claims": "list — claims that couldn't be verified against the profile",
        "version_info": "str — version label (e.g. 'v2')",
    }

    # -- Helpers ------------------------------------------------------------
    # Job/user context loading delegated to shared helpers in _dspy_utils.py.

    def _load_resume_text(self, job: dict) -> tuple[str, str]:
        """Load the best available resume text for specialisation.

        Checks for an existing job-specific resume version first.
        Falls back to the user's master resume.

        Returns ``(resume_text, source_label)`` where *source_label*
        describes where the text came from (for progress messages).
        """
        # Try job-specific version first
        doc_resp = self.tools.execute(
            "get_job_document",
            {"job_id": job["id"], "doc_type": "resume"},
        )
        if "error" not in doc_resp:
            v = doc_resp["document"]["version"]
            return doc_resp["document"]["content"], f"job-specific resume (v{v})"

        # Fall back to master resume
        resume_resp = self.tools.execute("read_resume", {})
        if "error" not in resume_resp:
            if parsed := resume_resp.get("parsed"):
                return self._parsed_resume_to_text(parsed), "parsed resume"
            if text := resume_resp.get("text"):
                return text, "uploaded resume"

        return "", ""

    @staticmethod
    def _parsed_resume_to_text(parsed: dict) -> str:
        """Convert a parsed resume dict back into structured plain text.

        The downstream ``IdentifySectionsSig`` expects prose-like text
        with section headings.  Feeding it raw JSON produces poor section
        identification and garbled revisions.
        """
        lines: list[str] = []

        # Contact info
        if contact := parsed.get("contact_info"):
            if name := contact.get("name"):
                lines.append(name)
            contact_parts = []
            if email := contact.get("email"):
                contact_parts.append(email)
            if phone := contact.get("phone"):
                contact_parts.append(phone)
            if location := contact.get("location"):
                contact_parts.append(location)
            if contact_parts:
                lines.append(" | ".join(contact_parts))
            for link in contact.get("links", []):
                if isinstance(link, dict):
                    lines.append(f"{link.get('label', '')}: {link.get('url', '')}".strip(": "))
                else:
                    lines.append(str(link))
            lines.append("")

        # Summary
        if summary := parsed.get("summary"):
            lines.append("## Summary")
            lines.append(summary)
            lines.append("")

        # Work experience
        if experiences := parsed.get("work_experience"):
            lines.append("## Work Experience")
            for exp in experiences:
                title_line = exp.get("title", "")
                if company := exp.get("company"):
                    title_line += f" — {company}"
                if dates := exp.get("dates", exp.get("date_range")):
                    title_line += f" ({dates})"
                lines.append(title_line)
                for h in exp.get("highlights", []):
                    lines.append(f"  - {h}")
                lines.append("")

        # Education
        if education := parsed.get("education"):
            lines.append("## Education")
            for edu in education:
                degree_line = edu.get("degree", "")
                if inst := edu.get("institution"):
                    degree_line += f" — {inst}"
                if dates := edu.get("dates", edu.get("date_range")):
                    degree_line += f" ({dates})"
                lines.append(degree_line)
                if details := edu.get("details"):
                    lines.append(f"  {details}")
                lines.append("")

        # Projects
        if projects := parsed.get("projects"):
            lines.append("## Projects")
            for proj in projects:
                proj_line = proj.get("name", proj.get("title", ""))
                if desc := proj.get("description"):
                    proj_line += f" — {desc}"
                lines.append(proj_line)
                for h in proj.get("highlights", []):
                    lines.append(f"  - {h}")
                lines.append("")

        # Skills
        if skills := parsed.get("skills"):
            lines.append("## Skills")
            for category in ("technical", "domain", "interpersonal", "other"):
                skill_list = skills.get(category, [])
                if skill_list:
                    lines.append(f"  {category.title()}: {', '.join(skill_list)}")
            lines.append("")

        # Certifications
        if certs := parsed.get("certifications"):
            lines.append("## Certifications")
            for c in certs:
                if isinstance(c, dict):
                    lines.append(f"  - {c.get('name', c.get('title', str(c)))}")
                else:
                    lines.append(f"  - {c}")
            lines.append("")

        # Publications
        if pubs := parsed.get("publications"):
            lines.append("## Publications")
            for p in pubs:
                if isinstance(p, dict):
                    lines.append(f"  - {p.get('title', str(p))}")
                else:
                    lines.append(f"  - {p}")
            lines.append("")

        # Spoken languages
        if langs := parsed.get("spoken_languages"):
            lines.append("## Languages")
            lines.append(", ".join(langs))
            lines.append("")

        return "\n".join(lines).strip()

    def _critique_section(
        self,
        lm: dspy.LM,
        section: ResumeSection,
        job_context: str,
        user_context: str,
        user_message: str,
    ) -> dict:
        """Critique one resume section (safe for thread pool)."""
        critic = dspy.ChainOfThought(CritiqueSectionSig)
        with dspy.context(lm=lm):
            result = critic(
                section_title=section.title,
                section_content=section.content,
                job_context=job_context,
                user_context=user_context,
                user_message=user_message,
            )
        return {
            "title": section.title,
            "content": section.content,
            "feedback": list(result.feedback) if result.feedback else [],
            "priority": result.priority or "medium",
        }

    def _revise_section(
        self,
        lm: dspy.LM,
        critique: dict,
        job_context: str,
        user_context: str,
    ) -> dict:
        """Revise one resume section based on critique (safe for thread pool)."""
        reviser = dspy.ChainOfThought(ReviseSectionSig)
        with dspy.context(lm=lm):
            result = reviser(
                section_title=critique["title"],
                section_content=critique["content"],
                feedback="\n".join(critique["feedback"]),
                job_context=job_context,
                user_context=user_context,
            )
        return {
            "title": critique["title"],
            "content": result.revised_content.strip() if result.revised_content else critique["content"],
            "changes_made": list(result.changes_made) if result.changes_made else [],
        }

    # -- Main run -----------------------------------------------------------

    def run(self) -> WorkflowResult:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Resolve the target job (required)
        job, job_context = load_job_context(
            self.tools, self.params, self.llm_config,
            user_message, conversation_context,
        )
        if not job:
            msg = "I need to know which job to tailor your resume for. Please specify the job.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No job resolved"},
                summary=msg.strip(),
            )

        job_label = f"{job['title']} at {job['company']}"
        self.event_bus.emit("text_delta", {"content": f"Targeting: **{job_label}**\n\n"})

        # 2. Load resume (job-specific version preferred) + user context
        self.event_bus.emit("text_delta", {"content": "Loading your resume and profile...\n"})

        resume_text, resume_source = self._load_resume_text(job)
        if not resume_text:
            msg = "I couldn't find a resume to work with. Please upload your resume first.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No resume available"},
                summary=msg.strip(),
            )

        self.event_bus.emit("text_delta", {"content": f"Using {resume_source} as starting point.\n"})

        user_context = load_user_context(self.tools)
        lm = build_lm(self.llm_config)

        # 3. Identify resume sections
        self.event_bus.emit("text_delta", {"content": "Identifying resume sections...\n"})

        parser = dspy.ChainOfThought(IdentifySectionsSig)
        with dspy.context(lm=lm):
            parsed = parser(resume_text=resume_text)

        sections = list(parsed.sections) if parsed.sections else []
        if not sections:
            # Treat the whole resume as one section
            sections = [ResumeSection(title="Full Resume", content=resume_text)]

        self.event_bus.emit("text_delta", {
            "content": (
                f"Found {len(sections)} sections: "
                + ", ".join(s.title for s in sections)
                + "\n\n"
            ),
        })

        # 4. Critique each section in parallel
        self.event_bus.emit("text_delta", {"content": "Evaluating each section against the job requirements...\n"})

        critiques: dict[int, dict] = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, max(1, len(sections)))
        ) as pool:
            futures: dict[concurrent.futures.Future, tuple[int, str]] = {
                pool.submit(
                    self._critique_section,
                    lm, section, job_context, user_context, user_message,
                ): (idx, section.title)
                for idx, section in enumerate(sections)
            }
            for future in concurrent.futures.as_completed(futures):
                idx, title = futures[future]
                exc = future.exception()
                if exc:
                    logger.warning("Section critique failed for '%s': %s", title, exc)
                    critiques[idx] = {
                        "title": title,
                        "content": sections[idx].content,
                        "feedback": [],
                        "priority": "low",
                    }
                else:
                    critiques[idx] = future.result()
                priority = critiques[idx]["priority"]
                self.event_bus.emit("text_delta", {"content": f"  {title}: {priority} priority\n"})

        # 5. Revise each section in parallel
        self.event_bus.emit("text_delta", {"content": "\nApplying revisions to each section...\n"})

        revised: dict[int, dict] = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, max(1, len(sections)))
        ) as pool:
            futures_rev: dict[concurrent.futures.Future, tuple[int, str]] = {
                pool.submit(
                    self._revise_section,
                    lm, critiques[idx], job_context, user_context,
                ): (idx, critiques[idx]["title"])
                for idx in range(len(sections))
            }
            for future in concurrent.futures.as_completed(futures_rev):
                idx, title = futures_rev[future]
                exc = future.exception()
                if exc:
                    logger.warning("Section revision failed for '%s': %s", title, exc)
                    revised[idx] = {
                        "title": title,
                        "content": critiques[idx]["content"],
                        "changes_made": [],
                    }
                else:
                    revised[idx] = future.result()
                self.event_bus.emit("text_delta", {"content": f"  revised: {title}\n"})

        ordered_revisions = [revised[i] for i in range(len(sections))]

        # 6. Unification and editing pass
        self.event_bus.emit("text_delta", {"content": "\nUnifying and polishing the full resume...\n"})

        unifier = dspy.ChainOfThought(UnifyResumeSig)
        with dspy.context(lm=lm):
            unified = unifier(
                sections_json=json.dumps(
                    [{"title": r["title"], "content": r["content"]} for r in ordered_revisions],
                    default=str,
                ),
                job_context=job_context,
                user_message=user_message,
            )

        unified_resume = unified.unified_resume.strip() if unified.unified_resume else "\n\n".join(
            r["content"] for r in ordered_revisions
        )

        # 7. Validate claims against user profile (using full, un-truncated context)
        self.event_bus.emit("text_delta", {"content": "Validating all claims against your profile...\n\n"})

        full_user_context = load_user_context(self.tools, max_chars=None)
        validator = dspy.ChainOfThought(ValidateClaimsSig)
        with dspy.context(lm=lm):
            validation = validator(
                resume=unified_resume,
                user_context=full_user_context,
                user_message=user_message,
            )

        flagged = list(validation.flagged_claims) if validation.flagged_claims else []

        if flagged:
            flags_text = "\n".join(f"- ⚠️ {claim}" for claim in flagged)
            self.event_bus.emit("text_delta", {
                "content": (
                    f"### ⚠️ Flagged Claims\n\n"
                    f"The following could not be verified against your profile "
                    f"and may need your review:\n\n{flags_text}\n\n"
                ),
            })

        # 8. Save + present final resume
        all_changes = [
            change
            for r in ordered_revisions
            for change in r.get("changes_made", [])
        ]
        edit_summary = (
            f"Specialised for {job_label}" +
            (f" — {len(flagged)} claim(s) flagged for review" if flagged else "")
        )

        save_resp = self.tools.execute("save_job_document", {
            "job_id": job["id"],
            "doc_type": "resume",
            "content": unified_resume,
            "edit_summary": edit_summary,
        })

        version_info = ""
        save_note = ""
        if "error" not in save_resp:
            version_info = f" (saved as v{save_resp['document']['version']})"
        else:
            save_note = f"\n\n_Note: unable to save this version ({save_resp['error']})._"

        changes_text = (
            "\n".join(f"- {c}" for c in all_changes)
            if all_changes
            else "- Tailored content and emphasis to match the target role."
        )

        editing_notes = list(unified.editing_notes) if unified.editing_notes else []
        editing_text = (
            "\n".join(f"- {n}" for n in editing_notes)
            if editing_notes
            else ""
        )

        self.event_bus.emit("text_delta", {
            "content": (
                f"---\n\n"
                f"## Specialised Resume{version_info}\n\n"
                f"{unified_resume}\n\n"
                f"---\n\n"
                f"### Changes Made\n\n"
                f"{changes_text}\n\n"
                + (f"### Editing Notes\n\n{editing_text}\n\n" if editing_text else "")
                + f"*{edit_summary}*"
                + save_note
                + "\n"
            ),
        })

        summary = f"Specialised resume for {job_label}{version_info}."
        if flagged:
            summary += f" {len(flagged)} claim(s) flagged for review."
        if save_note:
            summary += " Draft generated but not saved."

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "resume": unified_resume,
                "job": job,
                "changes": all_changes,
                "flagged_claims": flagged,
                "version_info": version_info,
            },
            summary=summary,
        )
