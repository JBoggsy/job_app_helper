"""Stage 2b: Experience & Education Extractor."""

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

class WorkExperienceEntry(BaseModel):
    company: str = Field(description="Company, organisation, or employer name")
    title: str = Field(description="Job title or role")
    start_date: str = Field(default="", description="Start date (e.g. 'Jan 2020', '2020', '2020-01')")
    end_date: str = Field(default="", description="End date or 'Present'")
    highlights: list[str] = Field(default_factory=list, description="Key accomplishments as bullet points")


class EducationEntry(BaseModel):
    institution: str = Field(description="School or university name")
    degree: str = Field(description="Degree type (e.g. 'B.S.', 'Ph.D.', 'Diploma')")
    field: str = Field(default="", description="Field of study or major")
    start_date: str = Field(default="", description="Start date")
    end_date: str = Field(default="", description="End date or graduation year")
    gpa: str = Field(default="", description="GPA if listed")
    details: list[str] = Field(default_factory=list, description="Additional details, honors, coursework")


class ProjectEntry(BaseModel):
    name: str = Field(description="Project name")
    description: str = Field(default="", description="Brief project description")
    key_details: list[str] = Field(
        default_factory=list,
        description="Notable details — tools, technologies, materials, techniques, methods, or outcomes",
    )
    url: str = Field(default="", description="Project URL if listed")


class ExperienceEducationOutput(BaseModel):
    experience: list[WorkExperienceEntry] = Field(default_factory=list, description="Work experience entries")
    education: list[EducationEntry] = Field(default_factory=list, description="Education entries")
    projects: list[ProjectEntry] = Field(default_factory=list, description="Project entries")


# ---------------------------------------------------------------------------
# DSPy Signature & Module
# ---------------------------------------------------------------------------

class ExperienceEducationSig(dspy.Signature):
    """Extract work experience, education, and project entries from resume sections.

    You are given the text of the experience, education, projects, and/or
    volunteer sections of a resume. The resume may be from ANY field or
    profession — not just technology.

    Your task:
    1. Identify each distinct position, degree, or project entry.
    2. For work experience: extract company/organisation, title, start/end
       dates, and convert accomplishments into concise bullet-point highlights.
    3. For education: extract institution, degree type, field of study,
       dates, GPA (if listed), and any additional details (honors, relevant
       coursework, thesis title).
    4. For projects: extract the project name, description, and notable
       details (tools, technologies, materials, methods, techniques, or
       outcomes as appropriate for the field).
    5. Volunteer work should be included in the experience list with the
       organisation as the "company".
    6. Normalise dates to a readable format (e.g. "Jan 2020", "2020").
       Use "Present" for current positions.
    7. Preserve original meaning — do not fabricate information.
    """

    section_text: str = dspy.InputField(
        desc="Combined text of the experience, education, projects, and volunteer sections"
    )
    extracted: ExperienceEducationOutput = dspy.OutputField(
        desc="Structured work experience, education, and project entries"
    )


class ExperienceEducationExtractor(TracedModule, dspy.Module):
    """Extract experience, education, and project entries from resume sections."""

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.extractor = dspy.ChainOfThought(ExperienceEducationSig)

    def forward(self, section_text: str) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.extractor(section_text=section_text)

    def extract(self, section_text: str) -> ExperienceEducationOutput:
        """Public API — returns structured experience and education data."""
        if not section_text.strip():
            logger.info("ExperienceEducationExtractor: no input text, returning empty result")
            return ExperienceEducationOutput()

        result = self(section_text=section_text)
        output: ExperienceEducationOutput = result.extracted
        logger.info(
            "ExperienceEducationExtractor: %d experience, %d education, %d projects",
            len(output.experience),
            len(output.education),
            len(output.projects),
        )
        return output
