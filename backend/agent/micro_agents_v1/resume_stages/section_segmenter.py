"""Stage 1: Section Segmenter — split raw resume text into classified sections."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

import dspy
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from backend.llm.llm_factory import LLMConfig

from backend.telemetry.traced_module import TracedModule

from ..workflows._dspy_utils import build_lm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SectionType(str, Enum):
    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    PUBLICATIONS = "publications"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"
    VOLUNTEER = "volunteer"
    OTHER = "other"


class ResumeSection(BaseModel):
    """A logical section of a resume with a title and content.

    This is the shared base model used by both the resume parsing
    pipeline and the specialize-resume workflow.
    """

    title: str = Field(description="Section heading (e.g. 'Experience', 'Skills')")
    content: str = Field(description="Full text content of this section")


class SegmentedResumeSection(ResumeSection):
    """A resume section enriched with classification metadata.

    Extends :class:`ResumeSection` with a ``section_type`` tag and
    preserves the original heading verbatim.  Used by the section
    segmenter stage of the resume parsing pipeline.

    The inherited ``title`` field is automatically populated from
    ``heading`` if not explicitly set.
    """

    section_type: SectionType = Field(description="Classified type of this section")
    heading: str = Field(description="Original heading text from the resume (e.g. 'Professional Experience')")
    title: str = Field(default="", description="Section heading (auto-populated from heading)")

    @model_validator(mode="after")
    def _sync_title_from_heading(self) -> "SegmentedResumeSection":
        if not self.title and self.heading:
            self.title = self.heading
        return self


class SectionSegmenterSig(dspy.Signature):
    """Segment raw resume text into classified sections.

    You are given raw text extracted from a resume PDF or DOCX file. The text
    may be messy — columns may have merged, headers may run into content, and
    formatting may be inconsistent.

    Your task:
    1. Identify all distinct sections in the resume (e.g. contact info,
       experience, education, skills, etc.).
    2. Classify each section using one of the allowed section types.
    3. Clean up the content of each section — fix obvious extraction artifacts
       like merged columns, broken lines, or garbled characters — while
       preserving the original meaning and structure (bullet points, dates,
       etc.).
    4. If a section doesn't clearly fit a specific type, use "other".
    5. Preserve ALL information from the original text. Do not omit any
       section, even if it seems minor.

    Allowed section types: contact, summary, experience, education, skills,
    projects, publications, certifications, languages, volunteer, other.
    """

    raw_text: str = dspy.InputField(desc="Raw text extracted from the resume document")
    sections: list[SegmentedResumeSection] = dspy.OutputField(
        desc="Ordered list of identified resume sections with cleaned content"
    )


class SectionSegmenter(TracedModule, dspy.Module):
    """Decompose raw resume text into typed, cleaned sections."""

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.segmenter = dspy.ChainOfThought(SectionSegmenterSig)

    def forward(self, raw_text: str) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.segmenter(raw_text=raw_text)

    def segment(self, raw_text: str) -> list[SegmentedResumeSection]:
        """Public API — returns a list of classified resume sections."""
        result = self(raw_text=raw_text)
        sections: list[SegmentedResumeSection] = result.sections
        type_counts = {}
        for s in sections:
            type_counts[s.section_type] = type_counts.get(s.section_type, 0) + 1
        logger.info(
            "SectionSegmenter produced %d section(s): %s",
            len(sections),
            {t.value: c for t, c in type_counts.items()},
        )
        return sections
