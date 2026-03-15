"""Stage 2a: Contact & Summary Extractor."""

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

class ContactLink(BaseModel):
    """A labelled link or profile found in the resume header."""

    label: str = Field(description="What this link is (e.g. 'LinkedIn', 'GitHub', 'Portfolio', 'Behance', 'ORCID')")
    url: str = Field(description="The URL, handle, or identifier")


class ContactInfo(BaseModel):
    name: str = Field(default="", description="Full name")
    email: str = Field(default="", description="Email address")
    phone: str = Field(default="", description="Phone number")
    location: str = Field(default="", description="City, State or full address")
    links: list[ContactLink] = Field(
        default_factory=list,
        description="Professional links and profiles (e.g. LinkedIn, GitHub, portfolio, Behance, ORCID, etc.)",
    )


class ContactSummaryOutput(BaseModel):
    contact: ContactInfo = Field(description="Extracted contact information")
    summary: str = Field(default="", description="Professional summary or objective statement")


# ---------------------------------------------------------------------------
# DSPy Signature & Module
# ---------------------------------------------------------------------------

class ContactExtractorSig(dspy.Signature):
    """Extract contact information and professional summary from resume sections.

    You are given the text of the contact/header and summary sections of a
    resume. These sections often have messy formatting from PDF extraction —
    icons replaced with unicode characters, multi-column layouts merged into
    a single line, etc.

    Your task:
    1. Extract the person's full name, email, phone, and location.
    2. Extract any professional links or profiles (LinkedIn, GitHub,
       portfolio sites, Behance, ORCID, personal websites, etc.) as
       labelled link entries.
    3. If a professional summary or objective section is present, extract it
       as a clean paragraph.
    4. For URLs, include the full URL if present, or just the handle/username
       if only that is available.
    5. Use empty strings for any field not found — do not guess or fabricate.
    """

    section_text: str = dspy.InputField(
        desc="Combined text of the contact and summary sections from the resume"
    )
    extracted: ContactSummaryOutput = dspy.OutputField(
        desc="Structured contact information and professional summary"
    )


class ContactExtractor(TracedModule, dspy.Module):
    """Extract contact info and summary from resume header sections."""

    def __init__(self, llm_config: "LLMConfig"):
        super().__init__()
        self.llm_config = llm_config
        self.extractor = dspy.ChainOfThought(ContactExtractorSig)

    def forward(self, section_text: str) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.extractor(section_text=section_text)

    def extract(self, section_text: str) -> ContactSummaryOutput:
        """Public API — returns structured contact info and summary."""
        if not section_text.strip():
            logger.info("ContactExtractor: no input text, returning empty result")
            return ContactSummaryOutput(contact=ContactInfo())

        result = self(section_text=section_text)
        output: ContactSummaryOutput = result.extracted
        logger.info(
            "ContactExtractor: name=%r, email=%r, has_summary=%s",
            output.contact.name,
            output.contact.email,
            bool(output.summary),
        )
        return output
