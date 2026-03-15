"""Stage 3: Resume Assembler — merge extractor outputs into the final dict.

Handles merging, deduplication, and schema conformance. When the skills
section is empty, uses an LLM call to infer skills from experience highlights.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import dspy

from backend.telemetry.traced_module import TracedModule

from .contact_extractor import ContactSummaryOutput
from .experience_extractor import ExperienceEducationOutput
from .skills_extractor import SkillsCredentialsOutput, SkillsInfo

if TYPE_CHECKING:
    from backend.llm.llm_factory import LLMConfig

from ..workflows._dspy_utils import build_lm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM-based skill inference for gap-filling
# ---------------------------------------------------------------------------

class InferSkillsSig(dspy.Signature):
    """Infer professional skills from work experience highlights.

    You are given the bullet-point highlights from a person's work experience
    entries. No explicit skills section was found on their resume.

    Analyse the highlights and extract skills that are clearly demonstrated
    or mentioned. Categorise them into:
    - *technical*: hard skills, tools, software, equipment, techniques, etc.
    - *domain*: areas of expertise, methodologies, specialisations.
    - *interpersonal*: soft skills like leadership, communication, etc.
    - *other*: anything that doesn't fit the above.

    Only include skills that are clearly evidenced. Do not fabricate. Keep
    each entry concise.
    """

    experience_highlights: str = dspy.InputField(
        desc="Newline-separated bullet points from all work experience entries"
    )
    skills: SkillsInfo = dspy.OutputField(desc="Inferred skills categorised by type")


class SkillInferrer(TracedModule, dspy.Module):
    """Infer skills from experience highlights via LLM when no skills section exists."""

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.inferrer = dspy.ChainOfThought(InferSkillsSig)

    def forward(self, experience_highlights: str) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.inferrer(experience_highlights=experience_highlights)

    def infer(self, experience_education: ExperienceEducationOutput) -> SkillsInfo:
        """Extract skills from experience highlights."""
        all_highlights = "\n".join(
            h
            for entry in experience_education.experience
            for h in entry.highlights
        )
        if not all_highlights.strip():
            logger.info("SkillInferrer: no highlights to analyse")
            return SkillsInfo()

        result = self(experience_highlights=all_highlights)
        output: SkillsInfo = result.skills
        total = (
            len(output.technical) + len(output.domain)
            + len(output.interpersonal) + len(output.other)
        )
        logger.info("SkillInferrer: inferred %d skills from experience", total)
        return output


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------

class ResumeAssembler:
    """Merge the three extractor outputs into the final parsed resume dict."""

    def __init__(self, llm_config: Optional["LLMConfig"] = None):
        self.llm_config = llm_config

    def assemble(
        self,
        contact_summary: ContactSummaryOutput,
        experience_education: ExperienceEducationOutput,
        skills_credentials: SkillsCredentialsOutput,
    ) -> dict:
        result = {}

        # --- Contact info ---
        result["contact_info"] = contact_summary.contact.model_dump(exclude_defaults=False)
        if contact_summary.summary:
            result["summary"] = contact_summary.summary

        # --- Work experience ---
        result["work_experience"] = [
            entry.model_dump() for entry in experience_education.experience
        ]

        # --- Education ---
        result["education"] = [
            entry.model_dump() for entry in experience_education.education
        ]

        # --- Projects (only if non-empty) ---
        if experience_education.projects:
            result["projects"] = [
                entry.model_dump() for entry in experience_education.projects
            ]

        # --- Skills (with LLM gap-filling from experience if needed) ---
        skills_dict = skills_credentials.skills.model_dump()
        skills_dict = self._deduplicate_skills(skills_dict)
        if self._is_skills_empty(skills_dict) and self.llm_config is not None:
            logger.info("ResumeAssembler: skills empty, inferring from experience")
            inferred = SkillInferrer(self.llm_config).infer(experience_education)
            skills_dict = self._deduplicate_skills(inferred.model_dump())
        result["skills"] = skills_dict

        # --- Certifications (only if non-empty) ---
        if skills_credentials.certifications:
            result["certifications"] = [
                c.model_dump() for c in skills_credentials.certifications
            ]

        # --- Publications (only if non-empty) ---
        if skills_credentials.publications:
            result["publications"] = [
                p.model_dump() for p in skills_credentials.publications
            ]

        # --- Spoken languages (only if non-empty) ---
        if skills_credentials.spoken_languages:
            result["spoken_languages"] = skills_credentials.spoken_languages

        logger.info(
            "ResumeAssembler: final keys = %s", list(result.keys())
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _SKILL_CATEGORIES = ("technical", "domain", "interpersonal", "other")

    @classmethod
    def _deduplicate_skills(cls, skills: dict) -> dict:
        """Remove duplicate skills within and across categories."""
        seen: set[str] = set()
        for key in cls._SKILL_CATEGORIES:
            deduped = []
            for skill in skills.get(key, []):
                normalised = skill.strip().lower()
                if normalised and normalised not in seen:
                    seen.add(normalised)
                    deduped.append(skill.strip())
            skills[key] = deduped
        return skills

    @classmethod
    def _is_skills_empty(cls, skills: dict) -> bool:
        return all(
            len(skills.get(key, [])) == 0
            for key in cls._SKILL_CATEGORIES
        )
