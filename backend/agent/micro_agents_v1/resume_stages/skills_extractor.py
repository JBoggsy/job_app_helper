"""Stage 2c: Skills & Credentials Extractor."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import dspy
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.llm.llm_factory import LLMConfig

from backend.telemetry.traced_module import TracedModule

from ..workflows._dspy_utils import build_lm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SkillsInfo(BaseModel):
    technical: list[str] = Field(
        default_factory=list,
        description="Technical or hard skills — software, tools, equipment, lab techniques, design software, instruments, machinery, etc.",
    )
    domain: list[str] = Field(
        default_factory=list,
        description="Domain-specific knowledge — areas of expertise, methodologies, specialisations (e.g. 'financial modelling', 'UX research', 'organic chemistry', 'contract law')",
    )
    interpersonal: list[str] = Field(
        default_factory=list,
        description="Soft / interpersonal skills — leadership, communication, teamwork, etc.",
    )
    other: list[str] = Field(
        default_factory=list,
        description="Skills that don't fit the above categories",
    )


class CertificationInfo(BaseModel):
    name: str = Field(description="Certification or licence name")
    issuer: str = Field(default="", description="Issuing organisation")
    date: str = Field(default="", description="Date earned")


class PublicationInfo(BaseModel):
    title: str = Field(description="Publication title")
    venue: str = Field(default="", description="Journal, conference, publisher, or gallery")
    date: str = Field(default="", description="Publication date")
    url: str = Field(default="", description="URL if available")


class SkillsCredentialsOutput(BaseModel):
    skills: SkillsInfo = Field(description="Categorised skills")
    certifications: list[CertificationInfo] = Field(default_factory=list, description="Professional certifications and licences")
    spoken_languages: list[str] = Field(default_factory=list, description="Human/spoken languages")
    publications: list[PublicationInfo] = Field(default_factory=list, description="Publications, papers, and creative works")


# ---------------------------------------------------------------------------
# DSPy Signature & Module
# ---------------------------------------------------------------------------

class SkillsExtractorSig(dspy.Signature):
    """Extract skills, certifications, publications, and spoken languages from resume sections.

    You are given the text of the skills, certifications, publications,
    and/or languages sections of a resume. The resume may be from ANY field
    or profession.

    Your task:
    1. **Skills** — Categorise into:
       - *technical*: hard skills, tools, software, equipment, instruments,
         lab techniques, design tools, machinery, etc.
       - *domain*: areas of expertise, methodologies, specialisations
         (e.g. 'financial modelling', 'UX research', 'organic chemistry').
       - *interpersonal*: soft skills like leadership, communication, etc.
       - *other*: anything that doesn't fit the above.
       Keep each entry concise (a few words, not long phrases).
    2. **Certifications** — Extract the name, issuing organisation, and
       date if listed. Include professional licences.
    3. **Publications** — Extract the title, venue (journal, conference,
       gallery, publisher), date, and URL if present.
    4. **Spoken languages** — Human/natural languages (e.g. English,
       Spanish), NOT programming languages. Only extract from a section that
       clearly refers to spoken languages.
    5. Use empty strings or empty lists for anything not found.
    6. Do not fabricate information.
    """

    section_text: str = dspy.InputField(
        desc="Combined text of the skills, certifications, publications, and languages sections"
    )
    extracted: SkillsCredentialsOutput = dspy.OutputField(
        desc="Structured skills, certifications, publications, and spoken languages"
    )


class SkillsExtractor(TracedModule, dspy.Module):
    """Extract skills, certifications, publications, and languages from resume sections."""

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.extractor = dspy.ChainOfThought(SkillsExtractorSig)

    def forward(self, section_text: str) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.extractor(section_text=section_text)

    def extract(self, section_text: str) -> SkillsCredentialsOutput:
        """Public API — returns structured skills and credentials."""
        if not section_text.strip():
            logger.info("SkillsExtractor: no input text, returning empty result")
            return SkillsCredentialsOutput(skills=SkillsInfo())

        result = self(section_text=section_text)
        output: SkillsCredentialsOutput = result.extracted
        total_skills = (
            len(output.skills.technical)
            + len(output.skills.domain)
            + len(output.skills.interpersonal)
            + len(output.skills.other)
        )
        logger.info(
            "SkillsExtractor: %d skills, %d certs, %d pubs, %d spoken languages",
            total_skills,
            len(output.certifications),
            len(output.publications),
            len(output.spoken_languages),
        )
        return output
