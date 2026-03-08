"""Edit Cover Letter workflow — single-shot critique and revision.

Pipeline:
1. A ``JobResolver`` identifies which tracked job the cover letter targets
   (required — the job provides context for the critique).
2. The cover letter is loaded from ``params`` (user provides it) or from the
   DB via ``get_job_document`` (if a prior version was saved for this job).
3. The user's profile, resume, and the target job's details are loaded.
4. Three independent analysis passes run in parallel:
   a. **Structure pass** — checks that all key sections are present (opening
      hook, company connection, skills/experience match, closing CTA) and that
      the ordering is effective.
   b. **Content/fit pass** — cross-references job requirements against what the
      letter actually covers; identifies gaps and missed opportunities from the
      user's profile and resume.
   c. **Tone & length pass** — flags issues with formality, voice, filler
      phrases, passive constructions, and overall length.
5. A synthesis step ranks and bundles the findings into a prioritised critique.
6. A revision step applies the highest-impact improvements to produce an
   updated cover letter.
7. The revised letter is saved to the DB as a new version via
   ``save_job_document``, preserving full edit history.
8. The critique, revised letter, and a summary of changes are streamed to
   the user.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from collections.abc import Generator

import dspy

from ._dspy_utils import build_lm
from .registry import BaseWorkflow, WorkflowResult, register_workflow
from .resolvers import JobResolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signatures — analysis passes
# ---------------------------------------------------------------------------


class StructureAnalysisSig(dspy.Signature):
    """Analyse the structural quality of a cover letter.

    Check whether the four essential sections are present and ordered
    effectively: opening hook, company connection, skills/experience match,
    closing call-to-action.
    """

    cover_letter: str = dspy.InputField(desc="The cover letter text to analyse")
    job_context: str = dspy.InputField(desc="Target job details for context (may be empty)")

    section_inventory: str = dspy.OutputField(
        desc=(
            "Which key sections are present and which are missing: "
            "opening hook, company connection, skills/experience match, call-to-action"
        )
    )
    ordering_issues: str = dspy.OutputField(
        desc="Any ordering problems (e.g. 'skills listed before company interest'), or 'None'"
    )
    structure_issues: list[str] = dspy.OutputField(
        desc="Concrete structural issues, each phrased as an actionable fix"
    )


class ContentFitAnalysisSig(dspy.Signature):
    """Cross-reference a cover letter against the job and the user's background.

    Identify which requirements are addressed, which are missing, and which
    strengths from the user's profile could strengthen the letter but are not
    currently mentioned.
    """

    cover_letter: str = dspy.InputField(desc="The cover letter text to analyse")
    job_context: str = dspy.InputField(
        desc="Target job details including requirements (may be empty)"
    )
    user_context: str = dspy.InputField(
        desc="The user's profile and resume highlights (may be empty)"
    )

    covered_requirements: list[str] = dspy.OutputField(
        desc="Job requirements the letter explicitly addresses"
    )
    missed_requirements: list[str] = dspy.OutputField(
        desc="Job requirements not addressed in the letter"
    )
    missed_strengths: list[str] = dspy.OutputField(
        desc=(
            "User strengths from profile/resume that could strengthen "
            "the letter but are not currently mentioned"
        )
    )
    content_issues: list[str] = dspy.OutputField(
        desc="Specific content and fit issues, each phrased as an actionable fix"
    )


class ToneAnalysisSig(dspy.Signature):
    """Analyse the tone, voice, and length of a cover letter.

    Look for passive constructions, filler phrases, inconsistent formality,
    and whether the overall length is appropriate.
    """

    cover_letter: str = dspy.InputField(desc="The cover letter text to analyse")

    tone_assessment: str = dspy.OutputField(
        desc=(
            "Overall tone description "
            "(e.g. 'appropriately professional', 'too stiff and formal', 'too casual')"
        )
    )
    length_assessment: str = dspy.OutputField(
        desc="One of: 'too short', 'appropriate', or 'too long', with a brief explanation"
    )
    tone_issues: list[str] = dspy.OutputField(
        desc=(
            "Specific tone/voice/length issues (passive voice, clichés, filler phrases), "
            "each phrased as an actionable fix"
        )
    )


# ---------------------------------------------------------------------------
# DSPy signatures — synthesis and revision
# ---------------------------------------------------------------------------


class SynthesizeCritiqueSig(dspy.Signature):
    """Synthesize three analysis passes into a prioritized cover letter critique.

    Combine structure, content, and tone findings into a concise, actionable
    critique.  Rank suggestions by impact — lead with the most important change.
    Keep the tone encouraging; the goal is to help, not to discourage.

    Format the critique as numbered markdown suggestions (1 = highest impact).
    Each suggestion should have a short heading, a 1-2 sentence explanation,
    and where helpful a brief concrete example of the improvement.
    """

    structure_findings: str = dspy.InputField(desc="JSON: structure analysis results")
    content_findings: str = dspy.InputField(desc="JSON: content/fit analysis results")
    tone_findings: str = dspy.InputField(desc="JSON: tone and length analysis results")
    cover_letter: str = dspy.InputField(desc="The original letter, for reference")

    overall_assessment: str = dspy.OutputField(
        desc=(
            "2-3 sentence summary of the letter's overall strength and "
            "the single most important thing to fix"
        )
    )
    critique: str = dspy.OutputField(
        desc="Prioritized critique in markdown with numbered suggestions, highest impact first"
    )


class ReviseLetterSig(dspy.Signature):
    """Apply the top improvements from a critique to produce a revised cover letter.

    Rules:
    - Apply only the highest-impact suggestions from the critique.
    - Preserve the user's authentic voice and word choices where possible.
    - The result must be a complete, ready-to-send cover letter.
    - Keep length appropriate (typically 3-4 paragraphs).
    """

    cover_letter: str = dspy.InputField(desc="The original cover letter")
    critique: str = dspy.InputField(
        desc="Prioritized critique with numbered suggestions"
    )
    job_context: str = dspy.InputField(desc="Target job details (may be empty)")
    user_context: str = dspy.InputField(
        desc="User profile and resume highlights (may be empty)"
    )

    revised_letter: str = dspy.OutputField(
        desc="The complete revised cover letter — full text, ready to send"
    )
    changes_applied: list[str] = dspy.OutputField(
        desc="List of specific changes that were applied, each as a brief sentence"
    )
    edit_summary: str = dspy.OutputField(
        desc="One-sentence summary of the overall revision"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("edit_cover_letter")
class EditCoverLetterWorkflow(BaseWorkflow):
    """Single-shot cover letter critique and revision."""

    # -- Helpers ------------------------------------------------------------

    def _load_job_context(
        self, user_message: str, conversation_context: str,
    ) -> tuple[dict | None, str]:
        """Resolve the target job and build a context string for prompts.

        Returns ``(job_dict, job_context_string)``.  Both are empty/None if
        no job can be matched.
        """
        job_id = self.params.get("job_id")
        job: dict | None = None

        jobs_resp = self.tools.execute("list_jobs", {"limit": 50})
        tracker_jobs = jobs_resp.get("jobs", []) if "error" not in jobs_resp else []

        if job_id and tracker_jobs:
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
                min_confidence=0.3,
            )
            if resolved:
                matched_id = resolved[0].job_id
                for j in tracker_jobs:
                    if j["id"] == matched_id:
                        job = j
                        break

        if job is None:
            return None, ""

        parts = [f"Role: {job['title']} at {job['company']}"]
        if job.get("location"):
            parts.append(f"Location: {job['location']}")
        if job.get("remote_type"):
            parts.append(f"Remote: {job['remote_type']}")
        if job.get("requirements"):
            parts.append(f"Requirements:\n{job['requirements']}")
        if job.get("nice_to_haves"):
            parts.append(f"Nice to haves:\n{job['nice_to_haves']}")

        return job, "\n".join(parts)

    def _load_user_context(self) -> str:
        """Load profile and resume into a single context string for prompts."""
        parts: list[str] = []

        profile_resp = self.tools.execute("read_user_profile", {})
        if profile := profile_resp.get("content", ""):
            parts.append(f"## User Profile\n{profile}")

        resume_resp = self.tools.execute("read_resume", {})
        if "error" not in resume_resp:
            if parsed := resume_resp.get("parsed"):
                parts.append(
                    f"## Resume (parsed)\n{json.dumps(parsed, default=str)[:3000]}"
                )
            elif text := resume_resp.get("text"):
                parts.append(f"## Resume\n{text[:3000]}")

        return "\n\n".join(parts)

    # -- Analysis passes (synchronous, safe for thread pool) ----------------

    def _analyze_structure(
        self, lm: dspy.LM, cover_letter: str, job_context: str,
    ) -> dict:
        analyzer = dspy.ChainOfThought(StructureAnalysisSig)
        with dspy.context(lm=lm):
            result = analyzer(cover_letter=cover_letter, job_context=job_context)
        return {
            "section_inventory": result.section_inventory,
            "ordering_issues": result.ordering_issues,
            "structure_issues": result.structure_issues,
        }

    def _analyze_content_fit(
        self,
        lm: dspy.LM,
        cover_letter: str,
        job_context: str,
        user_context: str,
    ) -> dict:
        analyzer = dspy.ChainOfThought(ContentFitAnalysisSig)
        with dspy.context(lm=lm):
            result = analyzer(
                cover_letter=cover_letter,
                job_context=job_context,
                user_context=user_context,
            )
        return {
            "covered_requirements": result.covered_requirements,
            "missed_requirements": result.missed_requirements,
            "missed_strengths": result.missed_strengths,
            "content_issues": result.content_issues,
        }

    def _analyze_tone(self, lm: dspy.LM, cover_letter: str) -> dict:
        analyzer = dspy.ChainOfThought(ToneAnalysisSig)
        with dspy.context(lm=lm):
            result = analyzer(cover_letter=cover_letter)
        return {
            "tone_assessment": result.tone_assessment,
            "length_assessment": result.length_assessment,
            "tone_issues": result.tone_issues,
        }

    # -- Main run -----------------------------------------------------------

    def run(self) -> Generator[dict, None, WorkflowResult]:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")
        cover_letter = self.params.get("cover_letter", "")

        # 1. Resolve the target job (required)
        job, job_context = self._load_job_context(user_message, conversation_context)
        if not job:
            msg = "I need to know which job this cover letter is for. Please specify the job.\n"
            yield {"event": "text_delta", "data": {"content": msg}}
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No job resolved"},
                summary=msg.strip(),
            )

        job_label = f"{job['title']} at {job['company']}"
        yield {
            "event": "text_delta",
            "data": {"content": f"Targeting: **{job_label}**\n\n"},
        }

        # 2. Load cover letter from params or DB
        if not cover_letter:
            doc_resp = self.tools.execute(
                "get_job_document",
                {"job_id": job["id"], "doc_type": "cover_letter"},
            )
            if "error" not in doc_resp:
                cover_letter = doc_resp["document"]["content"]
                v = doc_resp["document"]["version"]
                yield {
                    "event": "text_delta",
                    "data": {"content": f"Loaded saved cover letter (v{v}).\n\n"},
                }

        if not cover_letter:
            msg = "No cover letter found. Please paste the cover letter you'd like me to edit.\n"
            yield {"event": "text_delta", "data": {"content": msg}}
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No cover letter provided"},
                summary=msg.strip(),
            )

        # 3. Load user context (profile + resume)
        user_context = self._load_user_context()

        # 4. Three parallel analysis passes
        yield {"event": "text_delta", "data": {"content": "Analysing your cover letter...\n"}}
        lm = build_lm(self.llm_config)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures: dict[concurrent.futures.Future, str] = {
                pool.submit(
                    self._analyze_structure, lm, cover_letter, job_context,
                ): "structure",
                pool.submit(
                    self._analyze_content_fit, lm, cover_letter, job_context, user_context,
                ): "content & fit",
                pool.submit(
                    self._analyze_tone, lm, cover_letter,
                ): "tone & length",
            }

            analysis_results: dict[str, dict] = {}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                exc = future.exception()
                if exc:
                    logger.warning("Analysis pass '%s' failed: %s", name, exc)
                    analysis_results[name] = {}
                else:
                    analysis_results[name] = future.result()
                yield {
                    "event": "text_delta",
                    "data": {"content": f"  {name} analysis complete\n"},
                }

        # 5. Synthesize critique
        yield {"event": "text_delta", "data": {"content": "\nSynthesising findings...\n\n"}}

        synthesizer = dspy.ChainOfThought(SynthesizeCritiqueSig)
        with dspy.context(lm=lm):
            synthesis = synthesizer(
                structure_findings=json.dumps(
                    analysis_results.get("structure", {}), default=str,
                ),
                content_findings=json.dumps(
                    analysis_results.get("content & fit", {}), default=str,
                ),
                tone_findings=json.dumps(
                    analysis_results.get("tone & length", {}), default=str,
                ),
                cover_letter=cover_letter,
            )

        yield {
            "event": "text_delta",
            "data": {
                "content": (
                    f"## Cover Letter Analysis\n\n"
                    f"{synthesis.overall_assessment}\n\n"
                    f"### Suggested Improvements\n\n"
                    f"{synthesis.critique}\n\n"
                ),
            },
        }

        # 6. Revise the letter
        yield {"event": "text_delta", "data": {"content": "Applying improvements...\n\n"}}

        reviser = dspy.ChainOfThought(ReviseLetterSig)
        with dspy.context(lm=lm):
            revision = reviser(
                cover_letter=cover_letter,
                critique=synthesis.critique,
                job_context=job_context,
                user_context=user_context,
            )

        # 7. Save to DB
        save_resp = self.tools.execute("save_job_document", {
            "job_id": job["id"],
            "doc_type": "cover_letter",
            "content": revision.revised_letter,
            "edit_summary": revision.edit_summary,
        })

        version_info = ""
        if "error" not in save_resp:
            version_info = f" (saved as v{save_resp['document']['version']})"

        # 8. Stream revised letter and changes
        changes_text = "\n".join(f"- {c}" for c in revision.changes_applied)
        yield {
            "event": "text_delta",
            "data": {
                "content": (
                    f"---\n\n"
                    f"## Revised Cover Letter{version_info}\n\n"
                    f"{revision.revised_letter}\n\n"
                    f"---\n\n"
                    f"### Changes Applied\n\n"
                    f"{changes_text}\n\n"
                    f"*{revision.edit_summary}*\n"
                ),
            },
        }

        summary = f"Critiqued and revised cover letter for {job_label}{version_info}."

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "cover_letter": revision.revised_letter,
                "job": job,
                "version_info": version_info,
                "changes_applied": revision.changes_applied,
            },
            summary=summary,
        )
